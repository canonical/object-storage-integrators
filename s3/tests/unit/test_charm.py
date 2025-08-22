#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import dataclasses
from pathlib import Path
from unittest.mock import patch

import yaml
from ops import ActiveStatus, BlockedStatus
from ops.testing import Context, Secret, State

from src.charm import S3IntegratorCharm
from src.utils.secrets import decode_secret_key

CONFIG = yaml.safe_load(Path("./config.yaml").read_text())
ACTIONS = yaml.safe_load(Path("./actions.yaml").read_text())
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())


def test_on_start_blocked(base_state: State) -> None:
    """Check that the charm starts in blocked status by default."""
    # Given
    ctx = Context(S3IntegratorCharm, meta=METADATA, config=CONFIG, actions=ACTIONS, unit_id=0)
    state_in = base_state

    # When
    state_out = ctx.run(ctx.on.start(), state_in)

    # Then
    assert isinstance(status := state_out.unit_status, BlockedStatus)
    assert "Missing config(s): 'credentials'" in status.message


@patch("utils.secrets.decode_secret_key_with_retry", decode_secret_key)
@patch("managers.s3.S3Manager.get_bucket", return_value="test-bucket")
def test_on_start_ok(mock_get_bucket, charm_configuration: dict, base_state: State) -> None:
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
