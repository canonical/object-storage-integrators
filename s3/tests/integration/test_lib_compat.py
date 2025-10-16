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
from domain import S3ConnectionInfo
from helpers import delete_bucket, get_bucket

REQUIRER_V0 = "requirer-v0"
REQUIRER_V1 = "requirer-v1"
S3_INTEGRATOR_V0 = "s3-integrator-v0"
S3_INTEGRATOR_V1 = "s3-integrator-v1"

SECRET_LABEL = "s3-creds-secret-provider"
INVALID_BUCKET = "random?invali!dname"
S3_LIB_VERSION_FIELD = "lib-version"


logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def config_bucket_name(s3_info):
    bucket_name = "s3-integrator-config-bucket"
    yield bucket_name
    delete_bucket(s3_info=s3_info, bucket_name=bucket_name)


@pytest.fixture(scope="module")
def relation_bucket_name(s3_info):
    bucket_name = "s3-integrator-relation-bucket"
    yield bucket_name
    delete_bucket(s3_info=s3_info, bucket_name=bucket_name)


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


def test_deploy_provider_v1(
    juju: jubilant.Juju, s3_charm: Path, s3_info: S3ConnectionInfo, config_bucket_name: str
) -> None:
    """Test deploying s3-integrator that uses LIBAPI=1."""
    logger.info("Deploying S3 charm with configured credentials...")
    juju.deploy(
        s3_charm,
        app=S3_INTEGRATOR_V1,
        config={
            "endpoint": s3_info.endpoint,
            "tls-ca-chain": s3_info.tls_ca_chain,
            "bucket": config_bucket_name,
        },
    )
    secret_uri = juju.add_secret(
        SECRET_LABEL, {"access-key": s3_info.access_key, "secret-key": s3_info.secret_key}
    )
    juju.cli("grant-secret", SECRET_LABEL, S3_INTEGRATOR_V1)
    juju.config(S3_INTEGRATOR_V1, {"credentials": secret_uri})
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )
    assert get_bucket(s3_info=s3_info, bucket_name=config_bucket_name)


def test_deploy_requirer_v0(juju: jubilant.Juju, test_charm_s3_v0):
    """Deploy a consumer / requirer charm that uses S3 lib v0 (LIBAPI=0)."""
    logger.info(f"Deploying consumer charm {REQUIRER_V0}...")
    juju.deploy(test_charm_s3_v0, app=REQUIRER_V0)
    status = juju.wait(
        lambda status: jubilant.all_waiting(status, REQUIRER_V0)
        and jubilant.all_agents_idle(status, REQUIRER_V0),
        delay=5,
    )
    assert "Waiting for relation" in status.apps[REQUIRER_V0].app_status.message


def test_integrate_provider_v1_requirer_v0(
    juju: jubilant.Juju, s3_info: S3ConnectionInfo, config_bucket_name
) -> None:
    """Integrate S3 charm with requirer charm (which uses s3 LIBAPI=0), to test compatibility."""
    juju.integrate(S3_INTEGRATOR_V1, REQUIRER_V0)
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )
    result = juju.run(f"{REQUIRER_V0}/0", "get-s3-connection-info").results
    result.pop(S3_LIB_VERSION_FIELD, None)
    result.pop("data", None)

    # In this case, the consumer should be provided with the connection info with bucket from config option
    # This is because the s3 LIBAPI=0 sets `bucket=relation-xxx` automatically which should be ignored by s3 LIBAPI=1
    assert result == {
        "bucket": config_bucket_name,
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain).replace('"', "'"),
    }


def test_deploy_provider_v0(
    juju: jubilant.Juju, s3_info: S3ConnectionInfo, config_bucket_name: str
) -> None:
    """Test deploying s3-integrator from 1/stable that uses s3 lib LIBAPI=0."""
    logger.info("Deploying S3 charm with configured credentials...")
    juju.deploy(
        "s3-integrator",
        app=S3_INTEGRATOR_V0,
        channel="1/stable",
        config={
            "endpoint": s3_info.endpoint,
            "tls-ca-chain": s3_info.tls_ca_chain,
            "bucket": config_bucket_name,
        },
    )
    juju.wait(
        lambda status: jubilant.all_blocked(status, S3_INTEGRATOR_V0)
        and jubilant.all_agents_idle(status, S3_INTEGRATOR_V0),
        delay=5,
    )
    juju.run(
        f"{S3_INTEGRATOR_V0}/0",
        action="sync-s3-credentials",
        params={"access-key": s3_info.access_key, "secret-key": s3_info.secret_key},
    )
    juju.wait(
        lambda status: jubilant.all_active(status, S3_INTEGRATOR_V0)
        and jubilant.all_agents_idle(status, S3_INTEGRATOR_V0),
        delay=5,
    )


def test_deploy_requirer_v1(juju: jubilant.Juju, test_charm):
    """Deploy a consumer / requirer charm that uses S3 lib v1 (LIBAPI=1)."""
    logger.info(f"Deploying consumer charm {REQUIRER_V1}...")
    juju.deploy(test_charm, app=REQUIRER_V1)
    status = juju.wait(
        lambda status: jubilant.all_waiting(status, REQUIRER_V1)
        and jubilant.all_agents_idle(status, REQUIRER_V1),
        delay=5,
    )
    assert "Waiting for relation" in status.apps[REQUIRER_V1].app_status.message


def test_integrate_provider_v0_requirer_v1(
    juju: jubilant.Juju, s3_info: S3ConnectionInfo, config_bucket_name
) -> None:
    """Integrate s3-integrator (1/stable) with requirer charm (which uses s3 LIBAPI=0), to test compatibility."""
    juju.integrate(S3_INTEGRATOR_V0, REQUIRER_V1)
    juju.wait(
        lambda status: jubilant.all_active(status, S3_INTEGRATOR_V0, REQUIRER_V1)
        and jubilant.all_agents_idle(status, S3_INTEGRATOR_V0, REQUIRER_V1),
        delay=5,
    )
    result = juju.run(f"{REQUIRER_V1}/0", "get-s3-connection-info").results
    result.pop(S3_LIB_VERSION_FIELD, None)
    result.pop("data", None)

    assert result == {
        "bucket": config_bucket_name,
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain),
    }
