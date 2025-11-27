# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import dataclasses

from charms.data_platform_libs.v0.data_interfaces import PrematureDataAccessError
from ops.testing import Relation, Secret

from events.provider import GCStorageProviderEvents

REL = "gcs-credentials"


def test_relation_when_requirer_overrides_values_then_relation_databag_includes_overriden_values(
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

    rel = Relation(
        REL,
        remote_app_name="requirer",
        remote_app_data={
            "requested-secrets": '["secret-key"]',
            "bucket": "override-b",
            "path": "ov/p",
            "storage-class": "ARCHIVE",
        },
    )
    state = dataclasses.replace(
        base_state, leader=True, secrets={credentials_secret}, relations=[rel]
    )

    out = ctx.run(ctx.on.relation_changed(rel), state)
    rel_out = out.get_relations(REL)[0]
    app_data = rel_out.local_app_data

    assert app_data["bucket"] == "override-b"
    assert app_data["path"] == "ov/p"
    assert app_data["storage-class"] == "ARCHIVE"
    assert len(app_data["secret-extra"]) == 27


def test_provider_when_relation_joined_and_requested_secrets_in_databag_then_provider_publish_data_to_relation_databag(
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

    rel = Relation(
        REL,
        remote_app_name="requirer",
        remote_app_data={
            "requested-secrets": '["secret-key"]',
            "bucket": "",
            "path": "",
            "storage-class": "",
        },
    )
    state = dataclasses.replace(
        base_state, leader=True, secrets={credentials_secret}, relations=[rel]
    )

    out = ctx.run(ctx.on.relation_changed(rel), state)
    rel_out = out.get_relations(REL)[0]
    app_data = rel_out.local_app_data
    assert app_data["bucket"] == "bucket-name"
    assert len(app_data["secret-extra"]) == 27


def test_provider_when_relation_joins_and_requested_secrets_are_not_written_by_requirer_then_provider_does_not_publish(
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
    rel = Relation(REL, remote_app_name="requirer", remote_app_data={})

    state = dataclasses.replace(base_state, leader=True, relations=[rel])

    out = ctx.run(ctx.on.relation_changed(rel), state)

    rel_out = out.get_relations(REL)[0]
    app_data = rel_out.local_app_data
    assert "bucket" not in app_data
    assert "secret-key" not in app_data


def test_provider_when_premature_data_access_error_then_event_is_deferred_and_no_data_written(
    metadata, actions, charm_config, base_state, mk_ctx, monkeypatch
):
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
        remote_app_data={
            "requested-secrets": '["secret-key"]',
            "bucket": "",
            "path": "",
            "storage-class": "",
        },
    )
    state = dataclasses.replace(
        base_state,
        leader=True,
        secrets={credentials_secret},
        relations=[rel],
    )

    def _raise_premature(self, relation):
        raise PrematureDataAccessError("test premature access")

    monkeypatch.setattr(GCStorageProviderEvents, "publish_to_relation", _raise_premature)

    out = ctx.run(ctx.on.relation_changed(rel), state)

    rel_out = out.get_relations(REL)[0]
    app_data = rel_out.local_app_data
    assert "bucket" not in app_data
    assert "secret-extra" not in app_data
    assert out.deferred
