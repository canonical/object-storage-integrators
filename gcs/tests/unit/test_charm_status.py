# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import dataclasses

from ops.model import ActiveStatus, BlockedStatus
from ops.testing import Secret

REL = "gcs-credentials"


def test_missing_config_yields_blocked(metadata, actions, charm_config, base_state, mk_ctx):
    ctx = mk_ctx(metadata, actions, charm_config)
    out = ctx.run(ctx.on.start(), base_state)
    assert isinstance(out.unit_status, BlockedStatus)
    assert "Missing config(s)" in (out.unit_status.message or "").lstrip()


def test_valid_config_yields_active(metadata, actions, charm_config, base_state, mk_ctx):
    credentials_secret = Secret(
        tracked_content={
            "secret-key": "secret-key",
        }
    )
    charm_config["options"]["bucket"]["default"] = "bucket-name"
    charm_config["options"]["credentials"]["default"] = credentials_secret.id
    ctx = mk_ctx(metadata, actions, charm_config)
    state_in = dataclasses.replace(base_state, secrets={credentials_secret})

    state_out = ctx.run(ctx.on.start(), state_in)
    assert state_out.unit_status == ActiveStatus()
