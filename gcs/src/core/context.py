#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm Context definition and parsing logic."""

from typing import Optional

from ops import ConfigData, Model
from ops.model import SecretNotFoundError, ModelError
from constants import GCS_MANDATORY_OPTIONS
from core.domain import GcsConnectionInfo
from utils.logging import WithLogging
from utils.secrets import decode_secret_key, normalize
from core.charm_config import CharmConfig
from dataclasses import dataclass


@dataclass
class GcsConnectionInfo:
    """Google Cloud Storage connection parameters."""

    bucket: str
    sa_key: str
    storage_class: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"bucket": self.bucket, "sa-key": self.sa_key}
        if self.storage_class:
            d["storage-class"] = self.storage_class
        if self.path:
            d["path"] = self.path
        return d


class Context(WithLogging):
    """Properties and relations of the charm."""

    def __init__(self, model: Model, config: CharmConfig):
        self.model = model
        self.charm_config = config

    @property
    def gc_storage(self) -> Optional[GcsConnectionInfo]:
        """Return information related to GC Storage connection parameters."""
        if not self.charm_config:
            return None
        # credentials must be juju secret ref ("secret:<id>")
        cred = str(self.charm_config.credentials).strip()
        return GcsConnectionInfo(
            bucket=self.charm_config.bucket,
            sa_key=cred,
            storage_class=self.charm_config.storage_class or None,
            path=self.charm_config.path or None,
        )