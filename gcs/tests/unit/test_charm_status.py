# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import dataclasses

from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Secret

REL = "gcs-credentials"


def test_config_when_missing_mandatory_configuration_then_status_set_to_blocked(
    metadata, actions, charm_config, base_state, mk_ctx
):
    ctx = mk_ctx(metadata, actions, charm_config)
    out = ctx.run(ctx.on.config_changed(), base_state)
    assert isinstance(out.unit_status, BlockedStatus)
    assert "Missing config(s)" in (out.unit_status.message or "").lstrip()


def test_config_when_valid_configuration_then_status_set_to_active(
    metadata, actions, charm_config, base_state, mk_ctx
):
    credentials_secret = Secret(
        tracked_content={
            "secret-key": "secret-key",
        }
    )
    charm_config["options"]["bucket"]["default"] = "bucket-name"
    charm_config["options"]["credentials"]["default"] = credentials_secret.id
    ctx = mk_ctx(metadata, actions, charm_config)
    state_in = dataclasses.replace(base_state, secrets={credentials_secret})

    state_out = ctx.run(ctx.on.config_changed(), state_in)
    assert state_out.unit_status == ActiveStatus()


def test_config_when_invalid_configuration_then_status_set_to_blocked(
    metadata, actions, charm_config, base_state, mk_ctx
):
    credentials_secret = Secret(
        tracked_content={
            "secret-key": "secret-key",
        }
    )
    charm_config["options"]["bucket"]["default"] = "bu_?7-name"
    charm_config["options"]["credentials"]["default"] = credentials_secret.id
    ctx = mk_ctx(metadata, actions, charm_config)
    state_in = dataclasses.replace(base_state, secrets={credentials_secret})

    state_out = ctx.run(ctx.on.config_changed(), state_in)
    assert state_out.unit_status == BlockedStatus("Invalid config(s): 'bucket'")
