#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from pathlib import Path

import jubilant
import pytest
from helpers import delete_bucket, get_bucket

S3 = "s3-integrator"
SECRET_LABEL = "s3-creds-secret-config"
TEST_CHARM = "test-app"
TEST_CHARM_FIRST_ENDPOINT = "first-s3-credentials"
TEST_CHARM_SECOND_ENDPOINT = "second-s3-credentials"
SECOND_ENDPOINT_BUCKET = "test-bucket"

INVALID_CONFIG_BUCKET = "random?invali!dname"

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def config_bucket_name(s3_info):
    bucket_name = "s3-integrator-config-bucket"
    yield bucket_name
    delete_bucket(s3_info=s3_info, bucket_name=bucket_name)


def test_deploy(juju: jubilant.Juju, s3_charm: Path) -> None:
    """Test plain deployment of the charm."""
    logger.info("Deploying charm and creating secret")
    juju.deploy(s3_charm, app=S3)
    status = juju.wait(
        lambda status: jubilant.all_blocked(status) and jubilant.all_agents_idle(status), delay=5
    )
    assert "Missing config" in status.apps[S3].app_status.message
    assert "Missing config" in status.apps[S3].units[f"{S3}/0"].workload_status.message


def test_config_credentials_secret_does_not_exist(juju: jubilant.Juju) -> None:
    """Test the charm behavior when non-existent secret URI is given as credentials."""
    # Create a secret for secret URI and immediately delete so that it doesn't exist
    secret_uri = juju.add_secret(name="nonexistent_secret", content={"foo": "bar"})
    juju.cli("remove-secret", secret_uri)
    juju.config(S3, {"credentials": secret_uri})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status) and jubilant.all_agents_idle(status), delay=5
    )
    assert "does not exist" in status.apps[S3].app_status.message
    assert "does not exist" in status.apps[S3].units[f"{S3}/0"].workload_status.message


def test_config_credentials_secret_not_granted(juju: jubilant.Juju) -> None:
    """Test the charm behavior secret provided as credentials is not granted to the charm."""
    secret_uri = juju.add_secret(name="nongranted_secret", content={"foo": "bar"})
    juju.config(S3, {"credentials": secret_uri})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status) and jubilant.all_agents_idle(status), delay=5
    )
    assert "has not been granted" in status.apps[S3].app_status.message
    assert "has not been granted" in status.apps[S3].units[f"{S3}/0"].workload_status.message


def test_config_credentials_secret_missing_fields(juju: jubilant.Juju) -> None:
    """Test the charm behavior when required fields are missing in the secret given as credentials."""
    secret_uri = juju.add_secret(name=SECRET_LABEL, content={"foo": "bar"})
    juju.cli("grant-secret", secret_uri, S3)
    juju.config(S3, {"credentials": secret_uri})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status) and jubilant.all_agents_idle(status), delay=5
    )
    assert "is missing mandatory field" in status.apps[S3].app_status.message
    assert "is missing mandatory field" in status.apps[S3].units[f"{S3}/0"].workload_status.message


def test_config_credentials_valid_secret_keys(juju: jubilant.Juju, s3_info: dict) -> None:
    """Test the charm behavior when all required fields are present in the secret given as credentials."""
    juju.config(S3, {"endpoint": s3_info["endpoint"]})
    juju.wait(
        lambda status: jubilant.all_blocked(status) and jubilant.all_agents_idle(status), delay=5
    )
    juju.cli(
        "update-secret",
        SECRET_LABEL,
        f"access-key={s3_info['access-key']}",
        f"secret-key={s3_info['secret-key']}",
    )
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )


def test_config_invalid_bucket_name_valid_keys(juju: jubilant.Juju) -> None:
    """Test the charm behavior when the keys are valid but the bucket name is invalid."""
    juju.config(S3, {"bucket": INVALID_CONFIG_BUCKET})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status) and jubilant.all_agents_idle(status), delay=5
    )
    assert "Invalid config" in status.apps[S3].app_status.message
    assert "Invalid config" in status.apps[S3].units[f"{S3}/0"].workload_status.message


def test_config_valid_bucket_name_invalid_keys(
    juju: jubilant.Juju, s3_info, config_bucket_name
) -> None:
    """Test the charm behavior when the keys are invalid but the bucket name is valid."""
    juju.cli("update-secret", SECRET_LABEL, "access-key=foo", "secret-key=bar")
    status = juju.wait(
        lambda status: jubilant.all_blocked(status) and jubilant.all_agents_idle(status), delay=5
    )
    juju.config(S3, {"bucket": config_bucket_name})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status) and jubilant.all_agents_idle(status), delay=5
    )
    assert "Could not fetch or create bucket" in status.apps[S3].app_status.message
    assert (
        "Could not fetch or create bucket"
        in status.apps[S3].units[f"{S3}/0"].workload_status.message
    )
    assert not get_bucket(s3_info=s3_info, bucket_name=config_bucket_name)


def test_config_valid_bucket_name_valid_keys_creates_bucket(
    juju: jubilant.Juju, s3_info: dict, config_bucket_name
) -> None:
    """Test if the bucket is created automatically when valid bucket name and keys are provided in config."""
    assert not get_bucket(s3_info=s3_info, bucket_name=config_bucket_name)
    juju.cli(
        "update-secret",
        SECRET_LABEL,
        f"access-key={s3_info['access-key']}",
        f"secret-key={s3_info['secret-key']}",
    )
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )
    assert get_bucket(s3_info=s3_info, bucket_name=config_bucket_name)


def test_config_existing_bucket_name_valid_keys(juju: jubilant.Juju, pre_created_bucket) -> None:
    """Test that the charm still works with an existing bucket provided to the config with valid keys."""
    juju.config(S3, {"bucket": pre_created_bucket})
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )
