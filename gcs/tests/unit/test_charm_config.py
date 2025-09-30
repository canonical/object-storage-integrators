# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest

from src.core.charm_config import CharmConfig


def test_config_when_valid_config_given_then_cfg_is_loaded():
    cfg = CharmConfig(
        bucket="my-bucket", credentials="secret:abc", path="tmp", storage_class="STANDARD"
    )
    assert cfg.bucket == "my-bucket"
    assert cfg.credentials == "secret:abc"
    assert cfg.path == "tmp"
    assert cfg.storage_class == "STANDARD"


@pytest.mark.parametrize(
    "bucket",
    [
        "a-b",
        "abc",
        "a" * 63,
    ],
)
def test_bucket_rules_when_valid_bucket_name_given_than_cfg_loaded(bucket):
    base = {"credentials": "secret:any"}
    assert CharmConfig(bucket=bucket, **base).bucket == bucket


@pytest.mark.parametrize(
    "bucket",
    [
        "ab",
        "A-b",
        "abc_",
        "-abc",
        "abc-",
        "a" * 64,
    ],
)
def test_bucket_rules_when_invlid_bucket_name_given_then_raise(bucket):
    base = {"credentials": "secret:any"}
    with pytest.raises(Exception):
        CharmConfig(bucket=bucket, **base)


@pytest.mark.parametrize(
    "val,expected",
    [
        ("STANDARD", "STANDARD"),
        ("nearline", "NEARLINE"),
        ("ColdLine", "COLDLINE"),
        ("archive", "ARCHIVE"),
        ("", None),
        (None, None),
    ],
)
def test_storage_class_when_lowercase_given_then_always_return_uppercase(val, expected):
    cfg = CharmConfig(
        bucket="abc", credentials="s", **({"storage-class": val} if val is not None else {})
    )
    assert cfg.storage_class == expected


@pytest.mark.parametrize("bad", ["FASTLINE", "coolline", "STANDARD-IA", "X"])
def test_storage_class_when_invalid_value_given_then_raise(bad):
    with pytest.raises(Exception):
        CharmConfig(bucket="abc", credentials="s", **{"storage-class": bad})


@pytest.mark.parametrize(
    "path",
    [
        "",
        "dir/sub/file-01.ext",
        "a" * 1024,
    ],
)
def test_path_rules_when_valid_values_given_then_charm_config_loaded(path):
    assert CharmConfig(bucket="abc", credentials="s", path=path).path == path


@pytest.mark.parametrize(
    "path",
    [
        "/leading/slash",
        "nul\x00byte",
        "a" * 1025,
    ],
)
def test_path_rules_when_invalid_config_given_then_raise(path):
    with pytest.raises(Exception):
        CharmConfig(bucket="abc", credentials="s", path=path)
