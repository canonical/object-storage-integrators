# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest

from src.core.charm_config import CharmConfig


def test_valid_minimal_config():
    cfg = CharmConfig(
        bucket="my-bucket", credentials="secret:abc", path="tmp", storage_class="STANDARD"
    )
    assert cfg.bucket == "my-bucket"
    assert cfg.credentials == "secret:abc"
    assert cfg.path == "tmp"
    assert cfg.storage_class == "STANDARD"


@pytest.mark.parametrize(
    "bucket,ok",
    [
        ("a-b", True),
        ("abc", True),
        ("a" * 63, True),
        ("ab", False),
        ("A-b", False),
        ("abc_", False),
        ("-abc", False),
        ("abc-", False),
        ("a" * 64, False),
    ],
)
def test_bucket_rules(bucket, ok):
    base = {"credentials": "secret:any"}
    if ok:
        assert CharmConfig(bucket=bucket, **base).bucket == bucket
    else:
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
def test_storage_class_normalization(val, expected):
    cfg = CharmConfig(
        bucket="abc", credentials="s", **({"storage-class": val} if val is not None else {})
    )
    assert cfg.storage_class == expected


@pytest.mark.parametrize("bad", ["FASTLINE", "coolline", "STANDARD-IA", "X"])
def test_storage_class_invalid(bad):
    with pytest.raises(Exception):
        CharmConfig(bucket="abc", credentials="s", **{"storage-class": bad})


@pytest.mark.parametrize(
    "path,ok",
    [
        ("", True),
        ("dir/sub/file-01.ext", True),
        ("a" * 1024, True),
        ("/leading/slash", False),
        ("nul\x00byte", False),
        ("a" * 1025, False),
    ],
)
def test_path_rules(path, ok):
    if ok:
        assert CharmConfig(bucket="abc", credentials="s", path=path).path == path
    else:
        with pytest.raises(Exception):
            CharmConfig(bucket="abc", credentials="s", path=path)
