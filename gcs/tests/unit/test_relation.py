# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import dataclasses
from unittest.mock import patch, PropertyMock

from ops.testing import Context, Relation, State, Secret
from ops.model import ActiveStatus

from src.charm import GCStorageIntegratorCharm


REL = "gcs-credentials"


def test_requirer_overrides_win(metadata, actions, charm_config, base_state, mk_ctx):
    credentials_secret = Secret(
        tracked_content={
            "secret-key": "secret-key",
        }
    )
    charm_config["options"]["bucket"]["default"] = "bucket-name"
    charm_config["options"]["credentials"]["default"] = credentials_secret.id
    ctx = mk_ctx(metadata, actions, charm_config)

    rel = Relation(
        REL,
        remote_app_name="requirer",
        remote_app_data={"bucket": "override-b", "path": "ov/p", "storage-class": "ARCHIVE"},
    )
    state = dataclasses.replace(base_state, leader=True, secrets={credentials_secret}, relations=[rel])

    out = ctx.run(ctx.on.relation_changed(rel), state)
    rel_out = out.get_relations(REL)[0]
    app_data = rel_out.local_app_data

    assert app_data["bucket"] == "override-b"
    assert app_data["path"] == "ov/p"
    assert app_data["storage-class"] == "ARCHIVE"
    assert len(app_data["secret-key"]) == 20

def test_provider_puts_data_to_relation_databag(metadata, actions, charm_config, base_state, mk_ctx):
    credentials_secret = Secret(
        tracked_content={
            "secret-key": "secret-key",
        }
    )
    charm_config["options"]["bucket"]["default"] = "bucket-name"
    charm_config["options"]["credentials"]["default"] = credentials_secret.id
    ctx = mk_ctx(metadata, actions, charm_config)

    rel = Relation(
        REL,
        remote_app_name="requirer",
        remote_app_data={"bucket": "", "path": "", "storage-class": ""},
    )
    state = dataclasses.replace(base_state, leader=True, secrets={credentials_secret}, relations=[rel])

    out = ctx.run(ctx.on.relation_changed(rel), state)
    rel_out = out.get_relations(REL)[0]
    app_data = rel_out.local_app_data

    assert app_data["bucket"] == "bucket-name"
    assert len(app_data["secret-key"]) == 20

