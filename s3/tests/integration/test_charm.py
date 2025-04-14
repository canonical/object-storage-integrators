#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from pathlib import Path

import jubilant

S3 = "s3-integrator"
SECRET_LABEL = "s3-credentials-secret"

logger = logging.getLogger(__name__)


def test_deploy(juju: jubilant.Juju, s3_charm: Path, s3_info: dict, bucket_name: str) -> None:
    """Test initial setup."""
    logger.info("Deploying charm and creating secret")
    juju.deploy(s3_charm, app=S3, config={"endpoint": s3_info["endpoint"], "bucket": bucket_name})
    secret_id_raw = juju.cli(
        "add-secret",
        SECRET_LABEL,
        f"access-key={s3_info['access_key']}",
        f"secret-key={s3_info['secret_key']}",
    )
    secret_id = secret_id_raw.strip()
    logger.info(f"Created secret {secret_id}")

    status = juju.wait(jubilant.all_blocked, timeout=120)
    assert "Missing parameters" in status.apps[S3].app_status.message

    juju.cli("config", S3, f"credentials={secret_id}")


def test_grant_secret_active(juju: jubilant.Juju, bucket_name: str) -> None:
    """Test that once the charm is active once granted access to the secret."""
    juju.cli("grant-secret", SECRET_LABEL, S3)
    juju.wait(jubilant.all_active, timeout=120)

    task = juju.run(f"{S3}/0", "get-s3-connection-info", wait=10)
    assert task.return_code == 0
    assert task.results["bucket"] == bucket_name
