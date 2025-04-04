#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging
from pathlib import Path

import pytest
import yaml
from pytest_operator.plugin import OpsTest

from .helpers import (
    add_juju_secret,
    get_application_data,
    get_juju_secret,
    get_relation_data,
    is_relation_broken,
    is_relation_joined,
    update_juju_secret,
)

logger = logging.getLogger(__name__)

CHARM_METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
CHARM_NAME = CHARM_METADATA["name"]

TEST_APP_METADATA = yaml.safe_load(
    Path("./tests/integration/test-charm-azure/metadata.yaml").read_text()
)
TEST_APP_NAME = TEST_APP_METADATA["name"]


APPS = [CHARM_NAME, TEST_APP_NAME]
FIRST_RELATION = "first-azure-storage-credentials"
SECOND_RELATION = "second-azure-storage-credentials"


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
@pytest.mark.skip_if_deployed
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the charm and deploy 1 units for provider and requirer charm."""
    # Build and deploy charm from local source folder
    azure_charm = await ops_test.build_charm(".")
    test_charm = await ops_test.build_charm("./tests/integration/test-charm-azure/")

    await asyncio.gather(
        ops_test.model.deploy(azure_charm, application_name=CHARM_NAME, num_units=1),
        ops_test.model.deploy(test_charm, application_name=TEST_APP_NAME, num_units=1),
    )

    # Reduce the update_status frequency until the cluster is deployed
    async with ops_test.fast_forward():
        await ops_test.model.block_until(
            lambda: len(ops_test.model.applications[CHARM_NAME].units) == 1
        )

        await ops_test.model.block_until(
            lambda: len(ops_test.model.applications[TEST_APP_NAME].units) == 1
        )
        await asyncio.gather(
            ops_test.model.wait_for_idle(
                apps=[CHARM_NAME],
                status="blocked",
                timeout=1000,
            ),
            ops_test.model.wait_for_idle(
                apps=[TEST_APP_NAME],
                status="waiting",
                raise_on_blocked=True,
                timeout=1000,
            ),
        )

    assert len(ops_test.model.applications[CHARM_NAME].units) == 1

    for unit in ops_test.model.applications[CHARM_NAME].units:
        assert unit.workload_status == "blocked"

    assert len(ops_test.model.applications[TEST_APP_NAME].units) == 1


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_config_options(ops_test: OpsTest):
    """Tests the correct handling of configuration parameters."""
    secret_uri = await add_juju_secret(
        ops_test,
        charm_name=CHARM_NAME,
        secret_label="test-secret",
        data={"secret-key": "new-test-secret-key"},
    )
    configuration_parameters = {
        "storage-account": "stoacc",
        "path": "/test/path_1/",
        "container": "test-container",
        "credentials": secret_uri,
    }
    # apply new configuration options
    await ops_test.model.applications[CHARM_NAME].set_config(configuration_parameters)
    # wait for active status
    await ops_test.model.wait_for_idle(apps=[CHARM_NAME], status="active", timeout=1000)
    # test the returns
    azure_storage_integrator_unit = ops_test.model.applications[CHARM_NAME].units[0]
    action = await azure_storage_integrator_unit.run_action(
        action_name="get-azure-storage-connection-info"
    )
    action_result = await action.wait()
    configured_options = action_result.results
    # test the correctness of the configuration fields
    assert configured_options["storage-account"] == "stoacc"
    assert configured_options["path"] == "/test/path_1/"
    assert configured_options["secret-key"] == "**********"


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_relation_creation(ops_test: OpsTest):
    """Relate charms and wait for the expected changes in status."""
    await ops_test.model.integrate(CHARM_NAME, f"{TEST_APP_NAME}:{FIRST_RELATION}")

    async with ops_test.fast_forward():
        await ops_test.model.block_until(
            lambda: is_relation_joined(ops_test, FIRST_RELATION, FIRST_RELATION) == True  # noqa: E712
        )

        await ops_test.model.wait_for_idle(apps=APPS, status="active")
    await ops_test.model.wait_for_idle(apps=APPS, status="active")
    # test the content of the relation data bag

    relation_data = await get_relation_data(ops_test, TEST_APP_NAME, FIRST_RELATION)
    application_data = await get_application_data(ops_test, TEST_APP_NAME, FIRST_RELATION)
    logger.info(relation_data)
    logger.info(application_data)

    # check correctness for some fields
    assert "secret-extra" in application_data
    assert "container" in application_data
    assert application_data["container"] == "test-container"
    assert application_data["storage-account"] == "stoacc"
    assert application_data["path"] == "/test/path_1/"
    secret_uri = application_data["secret-extra"]
    secret_data = await get_juju_secret(ops_test, secret_uri)
    assert secret_data["secret-key"] == "new-test-secret-key"

    # update container name and check if the change is propagated in the relation databag
    new_container_name = "new-container-name"
    params = {"container": new_container_name}
    await ops_test.model.applications[CHARM_NAME].set_config(params)
    # wait for active status
    await ops_test.model.wait_for_idle(apps=[CHARM_NAME], status="active")
    application_data = await get_application_data(ops_test, TEST_APP_NAME, FIRST_RELATION)
    # check bucket name
    assert application_data["container"] == new_container_name

    # check that container name set in the requirer application is correct
    await ops_test.model.add_relation(CHARM_NAME, f"{TEST_APP_NAME}:{SECOND_RELATION}")
    # wait for relation joined
    async with ops_test.fast_forward():
        await ops_test.model.block_until(
            lambda: is_relation_joined(ops_test, SECOND_RELATION, SECOND_RELATION) == True  # noqa: E712
        )
        await ops_test.model.wait_for_idle(apps=APPS, status="active")

    # read data of the second relation
    application_data = await get_application_data(ops_test, TEST_APP_NAME, SECOND_RELATION)
    assert "secret-extra" in application_data
    assert "container" in application_data
    # check correctness of connection parameters in the relation databag
    assert application_data["container"] == new_container_name
    assert application_data["storage-account"] == "stoacc"
    assert application_data["path"] == "/test/path_1/"

    secret_uri = application_data["secret-extra"]
    secret_data = await get_juju_secret(ops_test, secret_uri)
    assert secret_data["secret-key"] == "new-test-secret-key"


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_secret_updated(ops_test: OpsTest):
    """Tests the update of secret-key via Juju secret."""
    secret_uri = await update_juju_secret(
        ops_test,
        charm_name=CHARM_NAME,
        secret_label="test-secret",
        data={"secret-key": "has-been-changed"},
    )
    # wait for active status
    await ops_test.model.wait_for_idle(apps=[CHARM_NAME], status="active", timeout=1000)
    # test the returns
    azure_storage_integrator_unit = ops_test.model.applications[CHARM_NAME].units[0]
    action = await azure_storage_integrator_unit.run_action(
        action_name="get-azure-storage-connection-info"
    )
    action_result = await action.wait()
    configured_options = action_result.results
    # test the correctness of the configuration fields
    assert configured_options["storage-account"] == "stoacc"
    assert configured_options["path"] == "/test/path_1/"
    assert configured_options["secret-key"] == "**********"

    # test the content of the relation data bag
    relation_data = await get_relation_data(ops_test, TEST_APP_NAME, FIRST_RELATION)
    application_data = await get_application_data(ops_test, TEST_APP_NAME, FIRST_RELATION)
    logger.info(relation_data)
    logger.info(application_data)

    # check correctness for some fields
    assert "secret-extra" in application_data
    assert "container" in application_data
    assert application_data["container"] == "new-container-name"
    assert application_data["storage-account"] == "stoacc"
    assert application_data["path"] == "/test/path_1/"
    secret_uri = application_data["secret-extra"]
    secret_data = await get_juju_secret(ops_test, secret_uri)
    assert secret_data["secret-key"] == "has-been-changed"


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_config_reset_container(ops_test: OpsTest):
    """Tests the correct handling of configuration parameters."""
    configuration_parameters = {
        "container": "",
    }
    # apply new configuration options
    await ops_test.model.applications[CHARM_NAME].set_config(configuration_parameters)

    # wait for idle status
    await ops_test.model.wait_for_idle(apps=[CHARM_NAME], timeout=1000)
    assert ops_test.model.applications[CHARM_NAME].units[0].workload_status == "blocked"

    configuration_parameters = {
        "container": "reconfigured-container",
    }
    # apply new configuration options
    await ops_test.model.applications[CHARM_NAME].set_config(configuration_parameters)

    # wait for idle status
    await ops_test.model.wait_for_idle(apps=[CHARM_NAME], timeout=1000, status="active")
    assert ops_test.model.applications[CHARM_NAME].units[0].workload_status == "active"


@pytest.mark.group(1)
async def test_relation_broken(ops_test: OpsTest):
    """Remove relation and wait for the expected changes in status."""
    # Remove relations
    await ops_test.model.applications[CHARM_NAME].remove_relation(
        f"{TEST_APP_NAME}:{FIRST_RELATION}", CHARM_NAME
    )
    await ops_test.model.block_until(
        lambda: is_relation_broken(ops_test, FIRST_RELATION, FIRST_RELATION) is True
    )
    await ops_test.model.applications[CHARM_NAME].remove_relation(
        f"{TEST_APP_NAME}:{SECOND_RELATION}", CHARM_NAME
    )
    await ops_test.model.block_until(
        lambda: is_relation_broken(ops_test, SECOND_RELATION, SECOND_RELATION) is True
    )
    # test correct application status
    async with ops_test.fast_forward():
        await asyncio.gather(
            ops_test.model.wait_for_idle(
                apps=[CHARM_NAME], status="active", raise_on_blocked=True
            ),
            ops_test.model.wait_for_idle(
                apps=[TEST_APP_NAME], status="waiting", raise_on_blocked=True
            ),
        )
