#!/usr/bin/env python3
# Copyright 2025
# SPDX-License-Identifier: Apache-2.0
import logging
from pathlib import Path

import jubilant
from test_config import _write_fake_sa

PROVIDER = "gcs-provider"
REQUIRER = "gcs-requirer"


logger = logging.getLogger(__name__)



def test_deploy_provider_then_status_is_blocked(juju: jubilant.Juju, gcs_charm: Path) -> None:
    """Test plain deployment of the charm."""
    logger.info("Deploying provider charm")
    juju.deploy(gcs_charm, app=PROVIDER, trust=True)
    status = juju.wait(
        lambda status: jubilant.all_blocked(status, PROVIDER) and jubilant.all_agents_idle(status),
        delay=5,
    )
    assert "Missing config" in status.apps[PROVIDER].app_status.message


def test_configure_provider_then_status_is_active(juju, gcs_charm, tmp_path: Path):
    logger.info("Configuring provider charm")
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


def test_deploy_requirer_then_status_is_waiting(
    juju: jubilant.Juju, gcs_charm: Path, requirer_charm: Path
) -> None:
    """Test plain deployment of the charm."""
    logger.info("Deploying requirer charm")
    juju.deploy(requirer_charm, app=REQUIRER)
    status = juju.wait(
        lambda st: jubilant.all_waiting(st, REQUIRER) and jubilant.all_agents_idle(st, REQUIRER),
        delay=5,
    )
    assert "Missing config" in status.apps[REQUIRER].app_status.message


def test_integrate_and_both_charms_are_active(
    juju: jubilant.Juju,
    gcs_charm,
):
    logger.info("Integrating provider and requirer charms")
    juju.integrate(f"{PROVIDER}:gcs-credentials", f"{REQUIRER}:gcs-credentials")

    juju.wait(
        lambda st: jubilant.all_active(st, PROVIDER, REQUIRER) and jubilant.all_agents_idle(st),
        delay=5,
    )

    st = juju.status()
    assert st.apps[PROVIDER].app_status.current == "active"
    assert st.apps[REQUIRER].app_status.current == "active"


def test_requirer_bucket_override_wins(
    juju: jubilant.Juju,
):
    logger.info("Testing bucket override")
    juju.config(REQUIRER, {"bucket": "overriden-bucket"})
    juju.wait(
        lambda st: jubilant.all_active(st, PROVIDER, REQUIRER) and jubilant.all_agents_idle(st),
        delay=5,
    )
    st = juju.status()
    msg = (st.apps[REQUIRER].units[f"{REQUIRER}/0"].workload_status.message or "").lower()
    assert "overriden-bucket".lower() in msg
