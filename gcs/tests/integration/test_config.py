#!/usr/bin/env python3
# Copyright 2025
# SPDX-License-Identifier: Apache-2.0
import json
import logging
from pathlib import Path

import jubilant

APP = "gcs-provider"

logger = logging.getLogger(__name__)


def _write_fake_sa(tmp: Path) -> Path:
    p = tmp / "sa.json"
    p.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "offline-tests",
                "private_key_id": "abc123",
                "private_key": "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n",
                "client_email": "tester@offline-tests.iam.gserviceaccount.com",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
    )
    return p


def test_provider_config_when_deploy_then_missing_config_is_reported_in_status(
    juju: jubilant.Juju, gcs_charm: Path
) -> None:
    logger.info("Deploying charm and creating secret")
    juju.deploy(gcs_charm, app=APP, trust=True)
    status = juju.wait(
        lambda status: jubilant.all_blocked(status) and jubilant.all_agents_idle(status), delay=5
    )
    assert "Missing config" in status.apps[APP].app_status.message
    assert "Missing config" in status.apps[APP].units[f"{APP}/0"].workload_status.message


def test_provider_config_when_configure_provider_then_status_is_active(
    juju, gcs_charm, tmp_path: Path
):
    sa_file = _write_fake_sa(tmp_path)
    content = Path(sa_file).read_text()
    secret_uri = juju.add_secret("gcs-cred-dummy", {"secret-key": content})
    juju.cli("grant-secret", "gcs-cred-dummy", APP)
    juju.config(
        APP,
        {
            "bucket": "valid-bucket-name",
            "credentials": secret_uri,
        },
    )
    juju.wait(lambda s: jubilant.all_active(s, APP) and jubilant.all_agents_idle(s, APP), delay=5)
    juju.cli("remove-secret", secret_uri)


def test_provider_config_when_remove_credentials_config_then_status_is_set_to_blocked(
    juju: jubilant.Juju,
) -> None:
    """Test the charm behavior when non-existent secret URI is given as credentials."""
    secret_uri = juju.add_secret(name="nonexistent_secret", content={"foo": "bar"})
    juju.cli("remove-secret", secret_uri)
    juju.config(APP, {"credentials": secret_uri})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status) and jubilant.all_agents_idle(status), delay=5
    )
    assert "does not exist" in status.apps[APP].app_status.message
    assert "does not exist" in status.apps[APP].units[f"{APP}/0"].workload_status.message


def test_provider_config_when_secret_not_granted_then_status_is_waiting(
    juju, gcs_charm, tmp_path: Path
):
    sa_file = _write_fake_sa(tmp_path)
    content = Path(sa_file).read_text()
    secret_uri = juju.add_secret("gcs-cred-dummy", {"secret-key": content})

    juju.config(
        APP,
        {
            "bucket": "valid-bucket-name",
            "credentials": secret_uri,
        },
    )
    status = juju.wait(
        lambda s: jubilant.all_blocked(s, APP) and jubilant.all_agents_idle(s, APP), delay=5
    )
    assert "has not been granted to the charm" in status.apps[APP].app_status.message
    juju.cli("remove-secret", secret_uri)


def test_provider_config_when_invalid_bucket_then_status_is_set_to_blocked(
    juju: jubilant.Juju, gcs_charm: Path, tmp_path: Path
):
    sa_file = _write_fake_sa(tmp_path)
    content = Path(sa_file).read_text()
    secret_uri = juju.add_secret("gcs-cred-dummy", {"secret-key": content})
    juju.cli("grant-secret", "gcs-cred-dummy", APP)
    juju.config(
        APP,
        {
            "bucket": "Bad_Bucket?Nope",
            "credentials": secret_uri,
        },
    )
    st = juju.wait(
        lambda s: jubilant.all_blocked(s, APP) and jubilant.all_agents_idle(s, APP), delay=5
    )
    msg = (st.apps[APP].app_status.message or "").lower()
    assert "bucket" in msg and ("invalid" in msg or "empty or invalid" in msg)
