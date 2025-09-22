# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import dataclasses
from unittest.mock import patch, PropertyMock

from ops.testing import Context, Relation, State
from ops.model import ActiveStatus

from src.charm import GCStorageIntegratorCharm


REL = "gcs-credentials"


def _mk_ctx(meta, cfg, unit_id=0):
    return Context(GCStorageIntegratorCharm, meta=meta, config=cfg, unit_id=unit_id)


def _with_cfg(charm_configuration, *, bucket="my-bucket", cred="secret:any",
              storage_class="", path=""):
    cfg = dict(charm_configuration)
    cfg["options"]["bucket"]["default"] = bucket
    cfg["options"]["credentials"]["default"] = cred
    cfg["options"]["storage-class"]["default"] = storage_class
    cfg["options"]["path"]["default"] = path
    return cfg


class DummyGC:
    """Minimal GCStorage object with to_dict() the provider expects."""
    def __init__(self, *, bucket, secret="{}", storage_class=None, path=""):
        self.bucket = bucket
        self.secret = secret
        self.storage_class = storage_class
        self.path = path

    def to_dict(self):
        d = {"bucket": self.bucket, "secret-key": self.secret}
        if self.storage_class:
            d["storage-class"] = self.storage_class
        if self.path:
            d["path"] = self.path
        return d


@patch("src.events.provider.Context.gc_storage",
       new_callable=PropertyMock,
       return_value=DummyGC(bucket="config-bucket", secret='{"k":"v"}', storage_class=None, path=""))
def test_relation_when_relation_joined_then_publishes_creds(_gc, metadata, charm_configuration, base_state: State):
    cfg = _with_cfg(charm_configuration, bucket="config-bucket", cred="secret:any")

    ctx = _mk_ctx(metadata, cfg, unit_id=0)
    state = dataclasses.replace(base_state, leader=True)

    rel = Relation(endpoint=REL, remote_app_data={})
    state = dataclasses.replace(state, relations=[rel])

    out = ctx.run(ctx.on.relation_changed(rel), state)

    published = out.get_relation(rel.id).local_app_data
    assert published["bucket"] == "config-bucket"
    assert "storage-class" not in published
    assert "path" not in published
    assert "secret-key" in published
    assert isinstance(out.unit_status, ActiveStatus)
    assert "ready" in (out.unit_status.message or "").lower()



@patch("src.events.provider.Context.gc_storage",
       new_callable=PropertyMock,
       return_value=DummyGC(bucket="config-bucket", secret='{"k":"v"}', storage_class="STANDARD", path="cfg/p"))
def test_relation_when_relation_joined_and_bucket_override_requested_then_bucket_overriden(_gc, metadata, charm_configuration, base_state: State):
    cfg = _with_cfg(charm_configuration, bucket="config-bucket", cred="secret:any")

    ctx = _mk_ctx(metadata, cfg, unit_id=0)
    state = dataclasses.replace(base_state, leader=True)

    rel = Relation(endpoint=REL, remote_app_data={"bucket": "relation-bucket"})
    state = dataclasses.replace(state, relations=[rel])

    out = ctx.run(ctx.on.relation_changed(rel), state)
    published = out.get_relation(rel.id).local_app_data
    assert published["bucket"] == "relation-bucket"    # override applied
    assert "secret-key" in published



@patch("src.events.provider.Context.gc_storage",
       new_callable=PropertyMock,
       return_value=DummyGC(bucket="config-bucket", secret='{"k":"v"}'))
def test_relation_when_unit_is_non_leader_then_do_not_publish(_gc, metadata, charm_configuration, base_state: State):
    cfg = _with_cfg(charm_configuration, bucket="config-bucket", cred="secret:any")

    ctx = _mk_ctx(metadata, cfg, unit_id=0)
    state = dataclasses.replace(base_state, leader=False)

    rel = Relation(endpoint=REL, remote_app_data={})
    state = dataclasses.replace(state, relations=[rel])

    out = ctx.run(ctx.on.relation_changed(rel), state)
    assert out.get_relation(rel.id).local_app_data == {}  # leader gating


@patch("src.events.provider.Context.gc_storage",
       new_callable=PropertyMock,
       return_value=DummyGC(bucket="cfg-bucket", secret='{"k":"v"}',
                             storage_class="STANDARD", path="cfg/prefix"))
def test_relation_when_relation_joined_and_storage_class_and_path_overrides_requested_then_override_those_values(_gc, metadata, charm_configuration, base_state: State):
    cfg = _with_cfg(charm_configuration, bucket="cfg-bucket", cred="secret:any",
                    storage_class="STANDARD", path="cfg/prefix")

    ctx = _mk_ctx(metadata, cfg, unit_id=0)
    state = dataclasses.replace(base_state, leader=True)

    rel = Relation(endpoint=REL, remote_app_data={
        "bucket": "req-bucket",
        "storage-class": "COLDLINE",
        "path": "req/prefix",
    })
    state = dataclasses.replace(state, relations=[rel])

    out = ctx.run(ctx.on.relation_changed(rel), state)
    published = out.get_relation(rel.id).local_app_data
    assert published["bucket"] == "req-bucket"
    assert published["storage-class"] == "COLDLINE"
    assert published["path"] == "req/prefix"
    assert "secret-key" in published



@patch("src.events.provider.Context.gc_storage",
       new_callable=PropertyMock,
       return_value=DummyGC(bucket="cfg-bucket", secret='{"k":"v"}', storage_class=None, path=""))
def test_relation_if_optional_values_are_not_Set_then_do_not_publish_empty_values(_gc, metadata, charm_configuration, base_state: State):
    cfg = _with_cfg(charm_configuration, bucket="cfg-bucket", cred="secret:any",
                    storage_class="", path="")

    ctx = _mk_ctx(metadata, cfg, unit_id=0)
    state = dataclasses.replace(base_state, leader=True)

    rel = Relation(endpoint=REL, remote_app_data={})
    state = dataclasses.replace(state, relations=[rel])

    out = ctx.run(ctx.on.relation_changed(rel), state)
    published = out.get_relation(rel.id).local_app_data
    assert "storage-class" not in published
    assert "path" not in published
    assert published["bucket"] == "cfg-bucket"
    assert "secret-key" in published

