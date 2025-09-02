#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging
from typing import Dict

import yaml
from juju.action import Action
from juju.unit import Unit
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)


def is_relation_joined(ops_test: OpsTest, endpoint_one: str, endpoint_two: str) -> bool:
    """Check if a relation is joined.

    Args:
        ops_test: The ops test object passed into every test case
        endpoint_one: The first endpoint of the relation
        endpoint_two: The second endpoint of the relation
    """
    for rel in ops_test.model.relations:
        endpoints = [endpoint.name for endpoint in rel.endpoints]
        if endpoint_one in endpoints and endpoint_two in endpoints:
            return True
    return False


def is_relation_broken(ops_test: OpsTest, endpoint_one: str, endpoint_two: str) -> bool:
    """Check if a relation is broken.

    Args:
        ops_test: The ops test object passed into every test case
        endpoint_one: The first endpoint of the relation
        endpoint_two: The second endpoint of the relation
    """
    for rel in ops_test.model.relations:
        endpoints = [endpoint.name for endpoint in rel.endpoints]
        if endpoint_one not in endpoints and endpoint_two not in endpoints:
            return True
    return False


async def run_charm_action(unit: Unit, charm_action: str, **params) -> dict:
    """Assert that the action is run successfully and returns the results.

    Args:
        unit: The unit to run the action on.
        charm_action: The action to run.
        params: The parameters to pass to the action.

    Raises:
        AssertionError if the action did not complete successfully.

    Returns:
        The results of the action.
    """
    action: Action = await unit.run_action(charm_action, **params)
    action = await action.wait()
    assert action.status == "completed", f"Action {charm_action} failed: {action.results}"
    return action.results


async def get_relation_data(
    ops_test: OpsTest,
    application_name: str,
    relation_name: str,
) -> list:
    """Returns a list that contains the relation-data.

    Args:
        ops_test: The ops test framework instance
        application_name: The name of the application
        relation_name: name of the relation to get connection data from
    Returns:
        a list that contains the relation-data
    """
    # get available unit id for the desired application
    units_ids = [
        app_unit.name.split("/")[1]
        for app_unit in ops_test.model.applications[application_name].units
    ]
    assert len(units_ids) > 0
    unit_name = f"{application_name}/{units_ids[0]}"
    raw_data = (await ops_test.juju("show-unit", unit_name))[1]
    if not raw_data:
        raise ValueError(f"no unit info could be grabbed for {unit_name}")
    data = yaml.safe_load(raw_data)
    # Filter the data based on the relation name.
    relation_data = [v for v in data[unit_name]["relation-info"] if v["endpoint"] == relation_name]
    if len(relation_data) == 0:
        raise ValueError(
            f"no relation data could be grabbed on relation with endpoint {relation_name}"
        )

    return relation_data


async def get_application_data(
    ops_test: OpsTest,
    application_name: str,
    relation_name: str,
) -> Dict:
    """Returns the application data bag of a given application and relation.

    Args:
        ops_test: The ops test framework instance
        application_name: The name of the application
        relation_name: name of the relation to get connection data from
    Returns:
        a dictionary that contains the application-data
    """
    relation_data = await get_relation_data(ops_test, application_name, relation_name)
    application_data = relation_data[0]["application-data"]
    return application_data


async def get_juju_secret(ops_test: OpsTest, secret_uri: str) -> Dict[str, str]:
    """Retrieve juju secret."""
    secret_unique_id = secret_uri.split("/")[-1]
    complete_command = f"show-secret {secret_uri} --reveal --format=json"
    _, stdout, _ = await ops_test.juju(*complete_command.split())
    return json.loads(stdout)[secret_unique_id]["content"]["Data"]


async def add_juju_secret(
    ops_test: OpsTest, charm_name: str, secret_label: str, data: Dict[str, str]
) -> str:
    """Add a new juju secret."""
    key_values = " ".join([f"{key}={value}" for key, value in data.items()])
    command = f"add-secret {secret_label} {key_values}"
    _, stdout, _ = await ops_test.juju(*command.split())
    secret_uri = stdout.strip()
    command = f"grant-secret {secret_label} {charm_name}"
    _, stdout, _ = await ops_test.juju(*command.split())
    return secret_uri


async def update_juju_secret(
    ops_test: OpsTest, charm_name: str, secret_label: str, data: Dict[str, str]
) -> str:
    """Update the given juju secret."""
    key_values = " ".join([f"{key}={value}" for key, value in data.items()])
    command = f"update-secret {secret_label} {key_values}"
    retcode, stdout, stderr = await ops_test.juju(*command.split())
    if retcode != 0:
        logger.warning(
            f"Update Juju secret exited with non zero status. \nSTDOUT: {stdout.strip()} \nSTDERR: {stderr.strip()}"
        )
