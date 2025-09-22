# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from src.charm import GCStorageIntegratorCharm
from ops.testing import Context
from src.charm import GCStorageIntegratorCharm
import pytest
from src.core.charm_config import (
    GCSConfig,
    CharmConfig,
    CharmConfigInvalidError,
)


def _mk_ctx(meta, cfg):
    return Context(GCStorageIntegratorCharm, meta=meta, config=cfg, unit_id=0)


class DummyCharm:
    def __init__(self, config: dict):
        self.config = config

def test_from_charm_when_given_valid_maps_fields_then_get_expected_charm_config():
    charm = DummyCharm(
        {
            "bucket": "my-bucket",
            "credentials": "secret:abc",
            "storage-class": "nearline",
            "path": "prefix/sub.dir-01",
        }
    )
    cfg = CharmConfig.from_charm(charm)
    assert cfg.bucket == "my-bucket"
    assert cfg.credentials == "secret:abc"
    assert cfg.storage_class == "NEARLINE"
    assert cfg.path == "prefix/sub.dir-01"


def test_from_charm_when_optional_fields_are_not_provided_then_default_values_are_returned():
    charm = DummyCharm(
        {
            "bucket": "abc-123",
            "credentials": "secret:any",
        }
    )
    cfg = CharmConfig.from_charm(charm)
    assert cfg.storage_class is None
    assert cfg.path == ""


@pytest.mark.parametrize(
    "bucket, ok",
    [
        ("a-b", True),
        ("abc", True),
        ("abc-123", True),
        ("a"*63, True),
        ("ab", False),
        ("A-b", False),
        ("abc_", False),
        ("-abc", False),
        ("abc-", False),
        ("a"*64, False),
    ],
)
def test_bucket_syntax_when_various_values_provided_then_return_exception_for_wrong_config_values(bucket, ok):
    base = {
        "credentials": "secret:any",
        "storage-class": "STANDARD",
        "path": "",
    }
    charm = DummyCharm({"bucket": bucket, **base})
    if ok:
        cfg = CharmConfig.from_charm(charm)
        assert cfg.bucket == bucket
    else:
        with pytest.raises(CharmConfigInvalidError) as ei:
            CharmConfig.from_charm(charm)
        assert "bucket" in str(ei.value).lower()


@pytest.mark.parametrize(
    "val, expected",
    [
        ("STANDARD", "STANDARD"),
        ("nearline", "NEARLINE"),
        ("ColdLine", "COLDLINE"),
        ("archive", "ARCHIVE"),
        ("", None),
        (None, None),
    ],
)
def test_storage_class_when_valid_and_normalized_values_given_then_return_expected(val, expected):
    charm = DummyCharm(
        {"bucket": "my-bucket", "credentials": "secret:any", "storage-class": val or ""}
    )
    cfg = CharmConfig.from_charm(charm)
    assert cfg.storage_class == expected


@pytest.mark.parametrize("val", ["FASTLINE", "coolline", "STANDARD-IA", "X"])
def test_storage_class_when_invalid_values_provided_then_return_exception(val):
    charm = DummyCharm(
        {"bucket": "my-bucket", "credentials": "secret:any", "storage-class": val}
    )
    with pytest.raises(CharmConfigInvalidError) as ei:
        CharmConfig.from_charm(charm)
    assert "storage-class" in str(ei.value).lower()


@pytest.mark.parametrize(
    "path, ok",
    [
        ("", True),
        ("dir/sub/file.name-01 ext", True),
        ("a"*1024, True),
        ("/leading/slash", False),
        ("nul\x00byte", False),
        ("a" * 1025, False),
    ],
)
def test_path_rules_when_wrong_values_provided_then_return_exception(path, ok):
    base = {"bucket": "my-bucket", "credentials": "secret:any"}
    cfg = {"path": path, **base}
    charm = DummyCharm(cfg)
    if ok:
        out = CharmConfig.from_charm(charm)
        assert out.path == path
    else:
        with pytest.raises(CharmConfigInvalidError) as ei:
            CharmConfig.from_charm(charm)
        assert "path" in str(ei.value).lower()


@pytest.mark.parametrize(
    "config, missing_fields",
    [
        ({"bucket": "my-bucket"}, ["credentials"]),
        ({"credentials": "secret:any"}, ["bucket"]),
        ({}, ["bucket", "credentials"]),
    ],
    ids=["no-cred", "no-bucket", "both-missing"],
)
def test_required_fields_when_missing_fields_exists_then_aggregate_error_message(config, missing_fields):
    charm = DummyCharm(config)
    with pytest.raises(CharmConfigInvalidError) as ei:
        CharmConfig.from_charm(charm)
    msg = str(ei.value).lower()
    for fld in missing_fields:
        assert fld in msg


def test_multiple_field_errors_then_aggregated_errors():
    charm = DummyCharm(
        {
            "bucket": "A_bad",
            "credentials": "secret:any",
            "storage-class": "FASTLINE",
            "path": "/starts/with/slash",
        }
    )
    with pytest.raises(CharmConfigInvalidError) as ei:
        CharmConfig.from_charm(charm)
    msg = str(ei.value).lower()
    for fld in ("bucket", "storage-class", "path"):
        assert fld in msg


