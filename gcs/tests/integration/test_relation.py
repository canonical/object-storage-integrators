#!/usr/bin/env python3
# Copyright 2025
# SPDX-License-Identifier: Apache-2.0
import logging
from pathlib import Path

import jubilant
from conftest import ensure_deployed, integrate_once
from test_config import _write_fake_sa

PROVIDER = "gcs-provider"
REQUIRER = "gcs-requirer"


logger = logging.getLogger(__name__)


def test_provider_when_deploy_then_status_is_blocked(juju: jubilant.Juju, gcs_charm: Path) -> None:
    """Test plain deployment of the charm."""
    logger.info("Deploying provider charm")
    ensure_deployed(juju, gcs_charm, app=PROVIDER, trust=True)
    status = juju.wait(
        lambda status: jubilant.all_blocked(status, PROVIDER) and jubilant.all_agents_idle(status),
        delay=5,
    )
    assert "Missing config" in status.apps[PROVIDER].app_status.message


def test_provider_when_configure_then_status_is_active(juju, gcs_charm, tmp_path: Path):
    logger.info("Configuring provider charm")
    ensure_deployed(juju, gcs_charm, app=PROVIDER, trust=True)
    sa_file = _write_fake_sa(tmp_path)
    content = Path(sa_file).read_text()
    secret_uri = juju.add_secret("gcs-cred-dummy", {"secret-key": content})

    juju.cli("grant-secret", "gcs-cred-dummy", PROVIDER)
    juju.config(
        PROVIDER,
        {
            "bucket": "valid-bucket-name",
            "credentials": secret_uri,
        },
    )
    juju.wait(
        lambda s: jubilant.all_active(s, PROVIDER) and jubilant.all_agents_idle(s, PROVIDER),
        delay=5,
    )


def test_requirer_when_deploy_then_status_is_waiting(
    juju: jubilant.Juju, gcs_charm: Path, requirer_charm: Path
) -> None:
    """Test plain deployment of the charm."""
    logger.info("Deploying requirer charm")
    ensure_deployed(juju, gcs_charm, app=PROVIDER, trust=True)
    ensure_deployed(juju, requirer_charm, app=REQUIRER, trust=True)
    status = juju.wait(
        lambda st: jubilant.all_waiting(st, REQUIRER) and jubilant.all_agents_idle(st, REQUIRER),
        delay=5,
    )
    assert "waiting for gcs-credentials relation" in status.apps[REQUIRER].app_status.message


def test_relation_when_integrate_then_both_charms_are_active(
    juju: jubilant.Juju, gcs_charm, requirer_charm
):
    ensure_deployed(juju, gcs_charm, app=PROVIDER, trust=True)
    ensure_deployed(juju, requirer_charm, app=REQUIRER, trust=True)
    logger.info("Integrating provider and requirer charms")
    integrate_once(juju, f"{PROVIDER}:gcs-credentials", f"{REQUIRER}:gcs-credentials")
    juju.wait(
        lambda st: jubilant.all_active(st, PROVIDER, REQUIRER) and jubilant.all_agents_idle(st),
        delay=5,
    )

    st = juju.status()
    assert st.apps[PROVIDER].app_status.current == "active"
    assert st.apps[REQUIRER].app_status.current == "active"


def test_relation_when_requirer_overrides_bucket_then_relation_includes_overriden_bucket(
    juju: jubilant.Juju, gcs_charm, requirer_charm
):
    ensure_deployed(juju, gcs_charm, app=PROVIDER, trust=True)
    ensure_deployed(juju, requirer_charm, app=REQUIRER, trust=True)
    integrate_once(juju, f"{PROVIDER}:gcs-credentials", f"{REQUIRER}:gcs-credentials")
    logger.info("Testing bucket override")
    juju.config(REQUIRER, {"bucket": "overriden-bucket"})
    juju.wait(
        lambda st: jubilant.all_active(st, PROVIDER, REQUIRER) and jubilant.all_agents_idle(st),
        delay=5,
    )
    st = juju.status()
    msg = (st.apps[REQUIRER].units[f"{REQUIRER}/0"].workload_status.message or "").lower()
    assert "overriden-bucket".lower() in msg
