#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import dataclasses
import json
from pathlib import Path

import pytest
import yaml
from ops import ActiveStatus, BlockedStatus
from ops.testing import ActionFailed, Context, Secret, State
from pytest import fixture

from src.charm import S3IntegratorCharm

CONFIG = yaml.safe_load(Path("./config.yaml").read_text())
ACTIONS = yaml.safe_load(Path("./actions.yaml").read_text())
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())


@fixture()
def ctx() -> Context:
    ctx = Context(S3IntegratorCharm, meta=METADATA, config=CONFIG, actions=ACTIONS, unit_id=0)
    return ctx


@fixture()
def charm_configuration():
    """Enable direct mutation on configuration dict."""
    return json.loads(json.dumps(CONFIG))


@fixture
def base_state() -> State:
    return State(leader=True)


def test_on_start_blocked(ctx: Context[S3IntegratorCharm], base_state: State) -> None:
    """Check that the charm starts in blocked status by default."""
    # Given
    state_in = base_state

    # When
    state_out = ctx.run(ctx.on.start(), state_in)

    # Then
    assert isinstance(status := state_out.unit_status, BlockedStatus)
    assert "credentials" in status.message


def test_on_start_no_secret_access_blocked(charm_configuration: dict, base_state: State) -> None:
    """Check that the charm starts in blocked status if not granted secret access."""
    # Given
    charm_configuration["options"]["bucket"]["default"] = "bucket-name"
    # This secret does not exist
    charm_configuration["options"]["credentials"]["default"] = "secret:1a2b3c4d5e6f7g8h9i0j"
    ctx = Context(
        S3IntegratorCharm, meta=METADATA, config=charm_configuration, actions=ACTIONS, unit_id=0
    )
    state_in = base_state

    # When
    state_out = ctx.run(ctx.on.start(), state_in)

    # Then
    assert isinstance(status := state_out.unit_status, BlockedStatus)
    assert "does not exist" in status.message


def test_on_start_ok(charm_configuration: dict, base_state: State) -> None:
    """Check that the charm starts in active status if everything is ok."""
    # Given
    credentials_secret = Secret(
        tracked_content={
            "access-key": "accesskey",
            "secret-key": "secretkey",
        }
    )
    charm_configuration["options"]["bucket"]["default"] = "bucket-name"
    charm_configuration["options"]["credentials"]["default"] = credentials_secret.id
    ctx = Context(
        S3IntegratorCharm, meta=METADATA, config=charm_configuration, actions=ACTIONS, unit_id=0
    )
    state_in = dataclasses.replace(base_state, secrets={credentials_secret})

    # When
    state_out = ctx.run(ctx.on.start(), state_in)

    # Then
    assert state_out.unit_status == ActiveStatus()


def test_on_action_credentials_not_set(ctx: Context[S3IntegratorCharm], base_state: State) -> None:
    """Check that relating the charm toggle TLS mode in the databag."""
    # Given
    state_in = base_state

    # When
    with pytest.raises(ActionFailed) as excinfo:
        ctx.run(ctx.on.action("get-s3-connection-info"), state_in)

    # Then
    assert excinfo.value.message == "Credentials are not set!"


def test_on_action_get_credentials(charm_configuration: dict, base_state: State) -> None:
    # Given
    credentials_secret = Secret(
        tracked_content={
            "access-key": "accesskey",
            "secret-key": "secretkey",
        }
    )
    bucket = "bucket-name"
    charm_configuration["options"]["bucket"]["default"] = bucket
    charm_configuration["options"]["credentials"]["default"] = credentials_secret.id
    ctx = Context(
        S3IntegratorCharm, meta=METADATA, config=charm_configuration, actions=ACTIONS, unit_id=0
    )
    state_in = dataclasses.replace(base_state, secrets={credentials_secret})

    # When
    ctx.run(ctx.on.action("get-s3-connection-info"), state_in)

    # Then
    assert ctx.action_results
    assert ctx.action_results["bucket"] == bucket
