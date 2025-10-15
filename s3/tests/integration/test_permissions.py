#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import base64
import json
import logging
import re
from pathlib import Path

import jubilant
import pytest
from conftest import S3ConnectionInfo
from helpers import create_bucket, delete_bucket, get_bucket

S3 = "s3"
CONSUMER1 = "consumer1"
CONSUMER2 = "consumer2"
CONSUMER3 = "consumer3"
SECRET_LABEL = "s3-creds-secret-provider"
INVALID_BUCKET = "random?invali!dname"


logger = logging.getLogger(__name__)


# @pytest.fixture(scope="module")
def allowed_bucket(s3_root_user):
    bucket_name = "yesbucket"
    bucket = create_bucket(s3_root_user, bucket_name)
    assert bucket is not None
    yield bucket.name
    deleted = delete_bucket(s3_root_user, bucket_name)
    assert deleted


# @pytest.fixture(scope="module")
def allowed_path():
    return "yespath"


# @pytest.fixture(scope="module")
def denied_bucket(s3_root_user):
    bucket_name = "nobucket"
    bucket = create_bucket(s3_root_user, bucket_name)
    assert bucket is not None
    yield bucket.name
    deleted = delete_bucket(s3_root_user, bucket_name)
    assert deleted


# @pytest.fixture(scope="module")
def denied_path():
    return "nopath"


def b64_to_ca_chain_json_dumps(ca_chain: str) -> str:
    """Validate the `tls-ca-chain` config option."""
    if not ca_chain:
        return ""
    decoded_value = base64.b64decode(ca_chain).decode("utf-8")
    chain_list = re.findall(
        pattern="(?=-----BEGIN CERTIFICATE-----)(.*?)(?<=-----END CERTIFICATE-----)",
        string=decoded_value,
        flags=re.DOTALL,
    )
    if not chain_list:
        raise ValueError("No certificate found in chain file")
    return json.dumps(chain_list)


def test_deploy_s3_integrator(
    juju: jubilant.Juju, s3_charm: Path, s3_root_user: S3ConnectionInfo
) -> None:
    """Test deploying the charm with minimal setup, without specifying config bucket."""
    logger.info("Deploying S3 charm with configured credentials...")
    juju.deploy(
        s3_charm,
        app=S3,
        config={"endpoint": s3_root_user.endpoint, "tls-ca-chain": s3_root_user.tls_ca_chain},
    )
    secret_uri = juju.add_secret(
        SECRET_LABEL,
        {"access-key": s3_root_user.access_key, "secret-key": s3_root_user.secret_key},
    )
    juju.cli("grant-secret", SECRET_LABEL, S3)
    juju.config(S3, {"credentials": secret_uri})
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )


def test_deploy_consumer_charm(juju: jubilant.Juju, test_charm: Path) -> None:
    """Deploy a consumer / requirer charm."""
    logger.info(f"Deploying consumer charm {CONSUMER1}...")
    juju.deploy(test_charm, app=CONSUMER1)
    status = juju.wait(
        lambda status: jubilant.all_waiting(status, CONSUMER1)
        and jubilant.all_agents_idle(status, CONSUMER1),
        delay=5,
    )
    assert "Waiting for relation" in status.apps[CONSUMER1].app_status.message


def test_configure_s3_integrator_with_list_objectsv2_denied(
    juju: jubilant.Juju,
    s3_user_with_listobjectsv2_disabled: S3ConnectionInfo,
    denied_bucket: str,
    denied_path: str,
):
    juju.update_secret(
        SECRET_LABEL,
        {
            "access-key": s3_user_with_listobjectsv2_disabled.access_key,
            "secret-key": s3_user_with_listobjectsv2_disabled.secret_key,
        },
    )
    juju.config(S3, {"bucket": denied_bucket, "path": denied_path})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status, S3) and jubilant.all_agents_idle(status, S3),
        delay=5,
    )
    assert "Could not ensure bucket" in status.apps[S3].app_status.message


# Integrate consumer -- consumer does not get data


def test_configure_s3_integrator_with_list_objectsv2_allowed(
    juju: jubilant.Juju,
    s3_user_with_listobjectsv2_enabled: S3ConnectionInfo,
    allowed_bucket: str,
    allowed_path: str,
):
    juju.update_secret(
        SECRET_LABEL,
        {
            "access-key": s3_user_with_listobjectsv2_enabled.access_key,
            "secret-key": s3_user_with_listobjectsv2_enabled.secret_key,
        },
    )
    juju.config(S3, {"bucket": allowed_bucket, "path": allowed_path})
    juju.wait(
        lambda status: jubilant.all_active(status, S3) and jubilant.all_agents_idle(status, S3),
        delay=5,
    )


# Integrate consumer -- consumer gets data
