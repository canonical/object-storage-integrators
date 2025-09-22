# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import json

from ops.testing import Secret
from ops.model import ActiveStatus

from src.charm import GCStorageIntegratorCharm
import dataclasses
import pytest
from unittest.mock import patch
from ops.testing import Context
from ops.model import BlockedStatus
from src.charm import GCStorageIntegratorCharm


REL = "gcs-credentials"


def _mk_ctx(meta, cfg):
    return Context(GCStorageIntegratorCharm, meta=meta, config=cfg, unit_id=0)

@pytest.mark.parametrize(
    "cfg_updates, expected_status_cls, expected_msg_contains",
    [
        ({}, BlockedStatus, "credentials"),
        ({"bucket": {"default": ""}}, BlockedStatus, "credentials"),
        ({"credentials": {"default": ""}}, BlockedStatus, "credentials"),
        ({"bucket": {"default": ""}, "credentials": {"default": ""}}, BlockedStatus, "credentials"),
    ],
    ids=["no-config", "no-cred", "only-cred-missing", "both-missing"],
)
def test_startup_when_missing_config_values_are_given_then_set_blocked_status(metadata, charm_configuration, base_state,
                                           cfg_updates, expected_status_cls, expected_msg_contains):
    for key, sub in cfg_updates.items():
        charm_configuration["options"][key]["default"] = sub["default"]

    ctx = Context(GCStorageIntegratorCharm, meta=metadata, config=charm_configuration, unit_id=0)
    out = ctx.run(ctx.on.start(), base_state)
    assert isinstance(out.unit_status, expected_status_cls)
    assert expected_msg_contains in (out.unit_status.message or "").lower()


@patch("events.base.decode_secret_key_with_retry", return_value="ok")  # <-- PATCH WHERE USED
@patch("core.context.decode_secret_key_with_retry", return_value="{}")  # Context.gc_storage
@patch("core.charm_config.decode_secret_key_with_retry")               # online_validate
@patch("core.charm_config.requests.get")                               # tokeninfo http
@patch("core.charm_config.service_account.Credentials.refresh", return_value=None)
@patch("core.charm_config.storage.Client.lookup_bucket", return_value=object())
def test_config_when_all_config_values_are_ok_then_sets_active_status(_lookup, _refresh, mock_req_get, mock_dec_cfg, _dec_ctx, _dec_base,
                               metadata, charm_configuration, base_state, fake_sa):
    mock_req_get.return_value.raise_for_status.return_value = None
    mock_dec_cfg.return_value = fake_sa

    sa = Secret(tracked_content={"secret-key": json.dumps(fake_sa)})

    charm_configuration["options"]["bucket"]["default"] = "my-bucket"
    charm_configuration["options"]["credentials"]["default"] = sa.id  # e.g. 'secret:abcd'

    ctx = Context(GCStorageIntegratorCharm, meta=metadata, config=charm_configuration, unit_id=0)
    out = ctx.run(ctx.on.config_changed(), dataclasses.replace(base_state, secrets={sa}))
    assert isinstance(out.unit_status, ActiveStatus)


@patch("events.base.decode_secret_key_with_retry", side_effect=Exception("boom"))
def test_get_app_status_when_secret_decoding_failed_then_set_blocked_status(_dec, metadata, charm_configuration, base_state):
    charm_configuration["options"]["bucket"]["default"] = "my-bucket"
    charm_configuration["options"]["credentials"]["default"] = "secret:any"
    ctx = _mk_ctx(metadata, charm_configuration)
    out = ctx.run(ctx.on.config_changed(), base_state)
    assert isinstance(out.unit_status, BlockedStatus)
    assert "credentials secret could not be decoded" in (out.unit_status.message or "").lower()


