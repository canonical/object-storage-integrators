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
CONSUMER = "consumer"
SECRET_LABEL = "s3-creds-secret-provider"


logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def allowed_bucket(s3_root_user):
    bucket_name = "yesbucket"
    bucket = create_bucket(s3_root_user, bucket_name)
    assert bucket is not None
    yield bucket.name
    deleted = delete_bucket(s3_root_user, bucket_name)
    assert deleted


@pytest.fixture(scope="module")
def allowed_path():
    return "yespath"


@pytest.fixture(scope="module")
def denied_bucket(s3_root_user):
    bucket_name = "nobucket"
    bucket = create_bucket(s3_root_user, bucket_name)
    assert bucket is not None
    yield bucket.name
    deleted = delete_bucket(s3_root_user, bucket_name)
    assert deleted


@pytest.fixture(scope="module")
def denied_path():
    return "nopath"


@pytest.fixture(scope="module")
def bucket_to_create():
    return "foo-bucket"


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
    juju: jubilant.Juju, s3_charm: Path, s3_root_user: S3ConnectionInfo, platform: str
) -> None:
    """Test deploying the charm with minimal setup."""
    logger.info("Deploying S3 charm with configured credentials...")
    juju.deploy(
        s3_charm,
        app=S3,
        config={"endpoint": s3_root_user.endpoint, "tls-ca-chain": s3_root_user.tls_ca_chain},
        constraints={"arch": platform},
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


def test_deploy_consumer_charm(juju: jubilant.Juju, test_charm: Path, platform: str) -> None:
    """Deploy a consumer / requirer charm."""
    logger.info(f"Deploying consumer charm {CONSUMER}...")
    juju.deploy(test_charm, app=CONSUMER, constraints={"arch": platform})
    status = juju.wait(
        lambda status: jubilant.all_waiting(status, CONSUMER)
        and jubilant.all_agents_idle(status, CONSUMER),
        delay=5,
    )
    assert "Waiting for relation" in status.apps[CONSUMER].app_status.message


def test_configure_s3_integrator_with_list_objectsv2_denied(
    juju: jubilant.Juju,
    s3_user_with_listobjectsv2_disabled: S3ConnectionInfo,
    denied_bucket: str,
    denied_path: str,
):
    """Configure the s3-integrator charm with an IAM user for which listobjectsv2 is disabled."""
    juju.update_secret(
        SECRET_LABEL,
        {
            "access-key": s3_user_with_listobjectsv2_disabled.access_key,
            "secret-key": s3_user_with_listobjectsv2_disabled.secret_key,
        },
    )
    juju.wait(
        lambda status: jubilant.all_active(status, S3) and jubilant.all_agents_idle(status, S3),
        delay=5,
    )
    juju.config(S3, {"bucket": denied_bucket, "path": denied_path})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status, S3) and jubilant.all_agents_idle(status, S3),
        delay=5,
    )
    assert "Could not ensure bucket" in status.apps[S3].app_status.message


def test_integrate_s3_integrator_with_list_objectsv2_denied(
    juju: jubilant.Juju,
) -> None:
    """Integrate the consumer charm with the S3 charm, where the IAM user has listobjectsv2 disabled."""
    juju.integrate(S3, CONSUMER)
    juju.wait(
        lambda status: jubilant.all_blocked(status, S3)
        and jubilant.all_active(status, CONSUMER)
        and jubilant.all_agents_idle(status, S3, CONSUMER),
        delay=5,
    )

    # The consumer2 charm should not have been provided the S3 data,
    # because s3-integrator cannot ensure the bucket is ready for use
    result = juju.run(f"{CONSUMER}/0", "get-s3-connection-info").results
    assert not any(
        key in result for key in ["access-key", "secret-key", "bucket", "endpoint", "tls-ca-chain"]
    )
    juju.remove_relation(S3, CONSUMER)
    status = juju.wait(
        lambda status: jubilant.all_blocked(status, S3)
        and jubilant.all_waiting(status, CONSUMER)
        and jubilant.all_agents_idle(status, S3, CONSUMER),
        delay=5,
    )
    assert "Waiting for relation" in status.apps[CONSUMER].app_status.message


def test_configure_s3_integrator_with_list_objectsv2_allowed(
    juju: jubilant.Juju,
    s3_user_with_listobjectsv2_enabled: S3ConnectionInfo,
    allowed_bucket: str,
    allowed_path: str,
):
    """Configure the s3-integrator charm with an IAM user for which listobjectsv2 is enabled."""
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


def test_integrate_s3_integrator_with_list_objectsv2_allowed(
    juju: jubilant.Juju,
    s3_user_with_listobjectsv2_enabled: S3ConnectionInfo,
    allowed_bucket: str,
    allowed_path: str,
) -> None:
    """Integrate the consumer charm with the S3 charm, where the IAM user has listobjectsv2 enabled."""
    juju.integrate(S3, CONSUMER)
    juju.wait(
        lambda status: jubilant.all_active(status, S3, CONSUMER)
        and jubilant.all_agents_idle(status, S3, CONSUMER),
        delay=5,
    )

    # The consumer2 charm should have been provided with the S3 data,
    result = juju.run(f"{CONSUMER}/0", "get-s3-connection-info").results
    assert result == {
        "access-key": s3_user_with_listobjectsv2_enabled.access_key,
        "secret-key": s3_user_with_listobjectsv2_enabled.secret_key,
        "endpoint": s3_user_with_listobjectsv2_enabled.endpoint,
        "bucket": allowed_bucket,
        "path": allowed_path,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(
            s3_user_with_listobjectsv2_enabled.tls_ca_chain
        ),
    }

    juju.remove_relation(S3, CONSUMER)
    status = juju.wait(
        lambda status: jubilant.all_active(status, S3)
        and jubilant.all_waiting(status, CONSUMER)
        and jubilant.all_agents_idle(status, S3, CONSUMER),
        delay=5,
    )
    assert "Waiting for relation" in status.apps[CONSUMER].app_status.message


def test_configure_s3_integrator_with_create_bucket_denied(
    juju: jubilant.Juju, s3_user_with_createbucket_disabled: S3ConnectionInfo, bucket_to_create
):
    """Configure the s3-integrator charm with an IAM user for which CreateBucket is disabled."""
    juju.update_secret(
        SECRET_LABEL,
        {
            "access-key": s3_user_with_createbucket_disabled.access_key,
            "secret-key": s3_user_with_createbucket_disabled.secret_key,
        },
    )
    juju.config(S3, {"bucket": bucket_to_create, "path": allowed_path})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status, S3) and jubilant.all_agents_idle(status, S3),
        delay=5,
    )
    assert "Could not ensure bucket" in status.apps[S3].app_status.message


def test_integrate_s3_integrator_with_create_bucket_denied(
    juju: jubilant.Juju,
) -> None:
    """Integrate the consumer charm with the S3 charm, where the IAM user has CreateBucket disabled."""
    juju.integrate(S3, CONSUMER)
    juju.wait(
        lambda status: jubilant.all_blocked(status, S3)
        and jubilant.all_active(status, CONSUMER)
        and jubilant.all_agents_idle(status, S3, CONSUMER),
        delay=5,
    )

    # The consumer2 charm should not have been provided the S3 data,
    # because s3-integrator cannot create the bucket
    result = juju.run(f"{CONSUMER}/0", "get-s3-connection-info").results
    assert not any(
        key in result for key in ["access-key", "secret-key", "bucket", "endpoint", "tls-ca-chain"]
    )
    juju.remove_relation(S3, CONSUMER)
    status = juju.wait(
        lambda status: jubilant.all_blocked(status, S3)
        and jubilant.all_waiting(status, CONSUMER)
        and jubilant.all_agents_idle(status, S3, CONSUMER),
        delay=5,
    )
    assert "Waiting for relation" in status.apps[CONSUMER].app_status.message


def test_configure_s3_integrator_with_create_bucket_allowed(
    juju: jubilant.Juju,
    s3_root_user,
    s3_user_with_createbucket_enabled: S3ConnectionInfo,
    bucket_to_create,
    allowed_path,
):
    """Configure the s3-integrator charm with an IAM user for which CreateBucket is enabled."""
    juju.update_secret(
        SECRET_LABEL,
        {
            "access-key": s3_user_with_createbucket_enabled.access_key,
            "secret-key": s3_user_with_createbucket_enabled.secret_key,
        },
    )
    juju.config(S3, {"bucket": bucket_to_create, "path": allowed_path})
    juju.wait(
        lambda status: jubilant.all_active(status, S3) and jubilant.all_agents_idle(status, S3),
        delay=5,
    )
    assert get_bucket(s3_info=s3_root_user, bucket_name=bucket_to_create)


def test_integrate_s3_integrator_with_create_bucket_allowed(
    juju: jubilant.Juju,
    s3_user_with_createbucket_enabled: S3ConnectionInfo,
    bucket_to_create: str,
    allowed_path: str,
) -> None:
    """Integrate the consumer charm with the S3 charm, where the IAM user has CreateBucket enabled."""
    juju.integrate(S3, CONSUMER)
    juju.wait(
        lambda status: jubilant.all_active(status, S3, CONSUMER)
        and jubilant.all_agents_idle(status, S3, CONSUMER),
        delay=5,
    )

    # The consumer charm should have been provided with the S3 data,
    result = juju.run(f"{CONSUMER}/0", "get-s3-connection-info").results
    assert result == {
        "access-key": s3_user_with_createbucket_enabled.access_key,
        "secret-key": s3_user_with_createbucket_enabled.secret_key,
        "endpoint": s3_user_with_createbucket_enabled.endpoint,
        "bucket": bucket_to_create,
        "path": allowed_path,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_user_with_createbucket_enabled.tls_ca_chain),
    }
