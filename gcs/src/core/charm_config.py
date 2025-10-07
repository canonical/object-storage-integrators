#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""GCS charm configuration validation."""

import logging
import re
from enum import StrEnum
from typing import Optional

from charms.data_platform_libs.v0.data_models import BaseConfigModel
from pydantic import ConfigDict, Field, StrictStr, field_validator

logger = logging.getLogger(__name__)


class CharmConfigInvalidError(Exception):
    """Configuration is invalid."""

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)


class StorageClass(StrEnum):
    """Type of storage classes supported by GCS."""

    STANDARD = "STANDARD"
    NEARLINE = "NEARLINE"
    COLDLINE = "COLDLINE"
    ARCHIVE = "ARCHIVE"


# bucket: 3–63 chars, lowercase letters/digits/hyphens,
# must start and end with a letter or digit
_BUCKET_RX = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{1,61})[a-z0-9]$")


class CharmConfig(BaseConfigModel):
    """Basic Config Validation.

    Args:
        bucket (StrictStr): Target GCS bucket. Syntax checks: (3–63, lowercase, digits, hyphens).
        credentials (StrictStr): Juju Secret (id or label) that contains a service-account JSON (validated online).
        storage_class (StrictStr): Optional storage class (STANDARD|NEARLINE|COLDLINE|ARCHIVE).
        path (StrictStr): Optional object prefix <=1024 bytes UTF-8, no NULL, no leading slash (/).
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    bucket: StrictStr = Field(
        ..., description="Target GCS bucket (3–63, lowercase/digits/hyphens)"
    )
    credentials: StrictStr = Field(
        ..., description="Juju secret id/label holding service-account JSON"
    )
    storage_class: Optional[StrictStr] = Field(
        default=StorageClass.STANDARD,
        alias="storage-class",
        description="GCS class (STANDARD|NEARLINE|COLDLINE|ARCHIVE)",
    )
    path: StrictStr = Field(default="", description="Object prefix inside the bucket")

    @field_validator("bucket")
    @classmethod
    def _bucket_syntax(cls, v: str) -> str:
        if not _BUCKET_RX.fullmatch(v):
            raise ValueError(
                "bucket must be 3–63 characters: lowercase letters, digits, or hyphens; "
                "must start/end with a letter or digit"
            )
        return v

    @field_validator("storage_class")
    @classmethod
    def _storage_class_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        allowed = {sc.value for sc in StorageClass}
        v_up = v.upper()
        if v_up not in allowed:
            raise ValueError(f"storage-class must be one of: {', '.join(sorted(allowed))}")
        return v_up

    @field_validator("path")
    @classmethod
    def _path_rules(cls, v: str) -> str:
        if v == "":
            return v
        if "\x00" in v:
            raise ValueError("path must not contain NULL bytes")
        if len(v.encode("utf-8")) > 1024:
            raise ValueError("path must be ≤ 1024 bytes (UTF-8)")
        if not re.fullmatch(r"[A-Za-z0-9._\-/ ]+", v):
            raise ValueError(
                "path contains unsupported characters (allow letters, digits, . _ - / space)"
            )
        if v.startswith("/"):
            raise ValueError("path must not start with '/'")
        return v
