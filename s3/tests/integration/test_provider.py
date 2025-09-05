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
from helpers import delete_bucket, get_bucket

S3 = "s3"
CONSUMER1 = "consumer1"
CONSUMER2 = "consumer2"
CONSUMER3 = "consumer3"
SECRET_LABEL = "s3-creds-secret-provider"
INVALID_BUCKET = "random?invali!dname"


logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def config_bucket_name_1(s3_info):
    bucket_name = "s3-integrator-config-bucket1"
    yield bucket_name
    delete_bucket(s3_info=s3_info, bucket_name=bucket_name)


@pytest.fixture(scope="module")
def config_bucket_name_2(s3_info):
    bucket_name = "s3-integrator-config-bucket2"
    yield bucket_name
    delete_bucket(s3_info=s3_info, bucket_name=bucket_name)


@pytest.fixture(scope="module")
def relation_bucket_name_1(s3_info):
    bucket_name = "s3-integrator-relation-bucket1"
    yield bucket_name
    delete_bucket(s3_info=s3_info, bucket_name=bucket_name)


@pytest.fixture(scope="module")
def relation_bucket_name_2(s3_info):
    bucket_name = "s3-integrator-relation-bucket2"
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


def test_deploy(juju: jubilant.Juju, s3_charm: Path, s3_info: S3ConnectionInfo) -> None:
    """Test deploying the charm with minimal setup, without specifying config bucket."""
    logger.info("Deploying S3 charm with configured credentials...")
    juju.deploy(
        s3_charm,
        app=S3,
        config={"endpoint": s3_info.endpoint, "tls-ca-chain": s3_info.tls_ca_chain},
    )
    secret_uri = juju.add_secret(
        SECRET_LABEL, {"access-key": s3_info.access_key, "secret-key": s3_info.secret_key}
    )
    juju.cli("grant-secret", SECRET_LABEL, S3)
    juju.config(S3, {"credentials": secret_uri})
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )


def test_deploy_consumer1(juju: jubilant.Juju, test_charm: Path) -> None:
    """Deploy a consumer / requirer charm."""
    logger.info(f"Deploying consumer charm {CONSUMER1}...")
    juju.deploy(test_charm, app=CONSUMER1)
    status = juju.wait(
        lambda status: jubilant.all_waiting(status, CONSUMER1)
        and jubilant.all_agents_idle(status, CONSUMER1),
        delay=5,
    )
    assert "Waiting for relation" in status.apps[CONSUMER1].app_status.message


def test_integrate_s3_and_consumer1(juju: jubilant.Juju, s3_info: S3ConnectionInfo) -> None:
    """Integrate S3 charm with consumer charm, without consumer requesting specific bucket."""
    juju.integrate(S3, CONSUMER1)
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )
    result = juju.run(f"{CONSUMER1}/0", "get-s3-connection-info").results
    # In this case, the consumer should be provided with the connection info without a specific bucket
    assert result == {
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain),
    }


def test_add_bucket_config_option(
    juju: jubilant.Juju, s3_info: S3ConnectionInfo, config_bucket_name_1: str
) -> None:
    """Test provider data shared to consumer charm when bucket option is configured on S3 charm."""
    assert not get_bucket(s3_info=s3_info, bucket_name=config_bucket_name_1)
    juju.config(S3, {"bucket": config_bucket_name_1})
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )
    result = juju.run(f"{CONSUMER1}/0", "get-s3-connection-info").results
    # The consumer should be provided with the connection info, including the bucket from the S3 charm config
    assert result == {
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "bucket": config_bucket_name_1,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain),
    }
    # The bucket should also have been created by the S3 charm
    assert get_bucket(s3_info=s3_info, bucket_name=config_bucket_name_1)


def test_requirer_detects_change_in_bucket_config(
    juju: jubilant.Juju, s3_info: S3ConnectionInfo, config_bucket_name_2: str
) -> None:
    """Test if the bucket information is propagated to the consumer charm when 'bucket' config is changed in S3 charm."""
    assert not get_bucket(s3_info=s3_info, bucket_name=config_bucket_name_2)
    juju.config(S3, {"bucket": config_bucket_name_2})
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )
    result = juju.run(f"{CONSUMER1}/0", "get-s3-connection-info").results
    # The consumer should now be provided with the connection info including the new bucket
    assert result == {
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "bucket": config_bucket_name_2,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain),
    }
    # The new bucket should also have been created by the S3 charm
    assert get_bucket(s3_info=s3_info, bucket_name=config_bucket_name_2)


def test_requirer_asks_for_invalid_bucket(juju: jubilant.Juju, s3_info) -> None:
    """Test S3 charm behavior when a consumer charm related to it asks for an invalid bucket."""
    juju.config(CONSUMER1, {"bucket": INVALID_BUCKET})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status, S3) and jubilant.all_agents_idle(status),
        delay=5,
    )
    # The S3 charm goes to the blocked state with appropriate message
    assert "Could not fetch or create bucket" in status.apps[S3].app_status.message
    assert (
        "Could not fetch or create bucket"
        in status.apps[S3].units[f"{S3}/0"].workload_status.message
    )

    # The invalid bucket is not created in the S3 cloud
    assert not get_bucket(s3_info=s3_info, bucket_name=INVALID_BUCKET)

    # The invalid bucket is therefore not shared by S3 charm to the consumer
    result = juju.run(f"{CONSUMER1}/0", "get-s3-connection-info").results
    assert result.get("bucket") != INVALID_BUCKET


def test_consumer1_asks_for_valid_bucket(
    juju: jubilant.Juju, s3_info: S3ConnectionInfo, relation_bucket_name_1: str
) -> None:
    """Test S3 charm behavior when a consumer charm related to it asks for a valid bucket."""
    juju.config(CONSUMER1, {"bucket": relation_bucket_name_1})
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )
    # The bucket from the relation should now take priority over the one in config
    # and therefore, it should be shared to the consumer instead of the bucket in config
    result = juju.run(f"{CONSUMER1}/0", "get-s3-connection-info").results
    assert result == {
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "bucket": relation_bucket_name_1,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain),
    }

    # The bucket asked by the consumer should have been created in the S3 cloud
    assert get_bucket(s3_info=s3_info, bucket_name=relation_bucket_name_1)


def test_deploy_consumer2(juju: jubilant.Juju, test_charm: Path) -> None:
    """Deploy a new instance of consumer."""
    logger.info(f"Deploying consumer charm {CONSUMER2}...")
    juju.deploy(test_charm, app=CONSUMER2)
    status = juju.wait(
        lambda status: jubilant.all_waiting(status, CONSUMER2)
        and jubilant.all_agents_idle(status, CONSUMER2),
        delay=5,
    )
    assert "Waiting for relation" in status.apps[CONSUMER2].app_status.message


def test_integrate_s3_and_consumer2_without_bucket_request(
    juju: jubilant.Juju,
    s3_info: S3ConnectionInfo,
    config_bucket_name_2: str,
    relation_bucket_name_1: str,
) -> None:
    """Integrate the new consumer charm with the same S3 charm, where the new consumer charm does not ask for bucket."""
    juju.integrate(S3, CONSUMER2)
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )

    # The consumer2 charm should be provided with the bucket in config, because it did not ask for a specific bucket
    result = juju.run(f"{CONSUMER2}/0", "get-s3-connection-info").results
    assert result == {
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "bucket": config_bucket_name_2,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain),
    }
    assert get_bucket(s3_info=s3_info, bucket_name=config_bucket_name_2)

    # However, the consumer1 charm should be unaffected by this -- it will still keep on seeing the bucket requested by it
    result = juju.run(f"{CONSUMER1}/0", "get-s3-connection-info").results
    assert result == {
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "bucket": relation_bucket_name_1,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain),
    }
    assert get_bucket(s3_info=s3_info, bucket_name=relation_bucket_name_1)


def test_consumer2_asks_for_valid_bucket(
    juju: jubilant.Juju,
    s3_info: S3ConnectionInfo,
    relation_bucket_name_1: str,
    relation_bucket_name_2: str,
) -> None:
    """Test the S3 charm behavior when consumer2 starts asking for a custom bucket."""
    juju.config(CONSUMER2, {"bucket": relation_bucket_name_2})
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )

    # The bucket asked by consumer2 over the relation should take priority over the one in config
    result = juju.run(f"{CONSUMER2}/0", "get-s3-connection-info").results
    assert result == {
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "bucket": relation_bucket_name_2,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain),
    }

    # The bucket asked by consumner2 should have been created in the S3 cloud
    assert get_bucket(s3_info=s3_info, bucket_name=relation_bucket_name_2)

    # However, the consumer1 charm should be unaffected by this -- it will still keep on seeing the bucket requested by it
    result = juju.run(f"{CONSUMER1}/0", "get-s3-connection-info").results
    assert result == {
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "bucket": relation_bucket_name_1,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain),
    }
    assert get_bucket(s3_info=s3_info, bucket_name=relation_bucket_name_1)


def test_deploy_consumer3_with_s3_lib_v0(juju: jubilant.Juju, test_charm_s3_v0):
    """Deploy a consumer / requirer charm that uses S3 v0 (LIBAPI=0)."""
    logger.info(f"Deploying consumer charm {CONSUMER3}...")
    juju.deploy(test_charm_s3_v0, app=CONSUMER3)
    status = juju.wait(
        lambda status: jubilant.all_waiting(status, CONSUMER3)
        and jubilant.all_agents_idle(status, CONSUMER3),
        delay=5,
    )
    assert "Waiting for relation" in status.apps[CONSUMER3].app_status.message


def test_integrate_s3_and_consumer3_with_s3_lib_v0(
    juju: jubilant.Juju, s3_info: S3ConnectionInfo, config_bucket_name_2
) -> None:
    """Integrate S3 charm with consumer3 charm (which uses s3 LIBAPI=0), to test compatibility."""
    juju.integrate(S3, CONSUMER3)
    juju.wait(
        lambda status: jubilant.all_active(status) and jubilant.all_agents_idle(status), delay=5
    )
    result = juju.run(f"{CONSUMER3}/0", "get-s3-connection-info").results

    # In this case, the consumer should be provided with the connection info with bucket from config option
    # This is because the s3 LIBAPI=0 sets `bucket=relation-xxx` automatically which should be ignored by s3 LIBAPI=1
    assert result == {
        "bucket": config_bucket_name_2,
        "access-key": s3_info.access_key,
        "secret-key": s3_info.secret_key,
        "endpoint": s3_info.endpoint,
        "tls-ca-chain": b64_to_ca_chain_json_dumps(s3_info.tls_ca_chain).replace('"', "'"),
    }
    assert get_bucket(s3_info=s3_info, bucket_name=config_bucket_name_2)


def test_both_consumers_ask_valid_buckets_but_keys_are_invalid(juju: jubilant.Juju):
    """Test the S3 charm behavior when multiple consumers are related to it, all of them asking for buckets, but keys are invalid."""
    juju.cli("update-secret", SECRET_LABEL, "access-key=foo", "secret-key=bar")
    juju.config(CONSUMER1, {"bucket": "consumer1-bucket"})
    juju.config(CONSUMER2, {"bucket": "consumer2-bucket"})
    status = juju.wait(
        lambda status: jubilant.all_blocked(status, S3)
        and jubilant.all_active(status, CONSUMER1, CONSUMER2)
        and jubilant.all_agents_idle(status),
        delay=5,
    )

    # The charm should stay in blocked state, with appropriate message
    assert all(
        phrase in status.apps[S3].app_status.message
        for phrase in ["Could not fetch or create bucket", "consumer1-bucket", "consumer2-bucket"]
    )
    assert all(
        phrase in status.apps[S3].units[f"{S3}/0"].workload_status.message
        for phrase in ["Could not fetch or create bucket", "consumer1-bucket", "consumer2-bucket"]
    )
