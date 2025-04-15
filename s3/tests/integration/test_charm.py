#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from pathlib import Path

import jubilant

S3 = "s3-integrator"
SECRET_LABEL = "s3-credentials-secret"
TEST_CHARM = "test-app"
TEST_CHARM_FIRST_ENDPOINT = "first-s3-credentials"
TEST_CHARM_SECOND_ENDPOINT = "second-s3-credentials"
SECOND_ENDPOINT_BUCKET = "test-bucket"

logger = logging.getLogger(__name__)


def test_deploy(juju: jubilant.Juju, s3_charm: Path, s3_info: dict, bucket_name: str) -> None:
    """Test initial setup."""
    logger.info("Deploying charm and creating secret")
    juju.deploy(s3_charm, app=S3, config={"endpoint": s3_info["endpoint"], "bucket": bucket_name})
    secret_id_raw = juju.cli(
        "add-secret",
        SECRET_LABEL,
        f"access-key={s3_info['access-key']}",
        f"secret-key={s3_info['secret-key']}",
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


def test_provider_default_bucket(
    juju: jubilant.Juju, test_charm: Path, bucket_name: str, s3_info: dict
) -> None:
    """Test that a default bucket name configured takes precedence over the required ones."""
    logger.info("Deploying test charm")
    juju.deploy(test_charm, app=TEST_CHARM)
    juju.integrate(S3, f"{TEST_CHARM}:{TEST_CHARM_FIRST_ENDPOINT}")
    juju.integrate(S3, f"{TEST_CHARM}:{TEST_CHARM_SECOND_ENDPOINT}")
    juju.wait(jubilant.all_active, timeout=120)

    task = juju.run(f"{TEST_CHARM}/0", "get-first-s3")
    assert task.return_code == 0
    assert task.results["bucket"] == bucket_name
    assert task.results["secret-key"] == s3_info["secret-key"]

    task = juju.run(f"{TEST_CHARM}/0", "get-second-s3")
    assert task.return_code == 0
    assert task.results["bucket"] == bucket_name
    assert task.results["secret-key"] == s3_info["secret-key"]


def test_provider_reset_bucket(juju: jubilant.Juju, s3_info: dict) -> None:
    """Test that apps can require a specific bucket name.

    We test that a config-changed event is correctly propagated to the requirers.
    """
    logger.info("Reverting default bucket configuration")
    juju.cli("config", S3, "--reset", "bucket")
    juju.wait(jubilant.all_active, timeout=120)

    task = juju.run(f"{TEST_CHARM}/0", "get-second-s3")
    assert task.return_code == 0
    assert task.results["bucket"] == SECOND_ENDPOINT_BUCKET
    assert task.results["secret-key"] == s3_info["secret-key"]


def test_provider_secret_changed(juju: jubilant.Juju) -> None:
    """Test that a credential change in the user secret gets propagated to requirers."""
    logger.info("Mutating secret")
    juju.cli("update-secret", SECRET_LABEL, "access-key=haschanged", "secret-key=haschanged")
    juju.wait(jubilant.all_active, timeout=120)

    task = juju.run(f"{TEST_CHARM}/0", "get-second-s3")
    assert task.return_code == 0
    assert task.results["bucket"] == SECOND_ENDPOINT_BUCKET
    assert task.results["access-key"] == "haschanged"
    assert task.results["secret-key"] == "haschanged"


def test_relation_broken(juju: jubilant.Juju) -> None:
    """Test that after relation broken, the charm stays in active-idle."""
    logger.info("Removing relations")
    juju.remove_relation(S3, f"{TEST_CHARM}:{TEST_CHARM_FIRST_ENDPOINT}")
    juju.remove_relation(S3, f"{TEST_CHARM}:{TEST_CHARM_SECOND_ENDPOINT}")
    juju.wait(lambda status: status.apps[S3].is_active, timeout=120)
