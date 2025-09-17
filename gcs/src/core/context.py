#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm Context definition and parsing logic."""
import logging
from typing import Optional

from ops import ConfigData, Model
from ops.model import SecretNotFoundError, ModelError
from core.domain import GcsConnectionInfo
from utils.logging import WithLogging
from utils.secrets import decode_secret_key, normalize
from core.charm_config import CharmConfig
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class GcsConnectionInfo:
    """Google Cloud Storage connection parameters."""

    bucket: str
    secret_key: str
    storage_class: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"bucket": self.bucket, "secret-key": self.secret_key}
        if self.storage_class:
            d["storage-class"] = self.storage_class
        if self.path:
            d["path"] = self.path
        return d


class Context(WithLogging):
    """Properties and relations of the charm."""

    def __init__(self, model: Model, charm_config: CharmConfig):
        self.model = model
        self.charm_config = charm_config

    @property
    def gc_storage(self) -> Optional[GcsConnectionInfo]:
        """Return information related to GC Storage connection parameters."""
        cfg = self.charm_config
        if not cfg or not cfg.bucket or not cfg.credentials:
            logger.warning("charm_config not set")
            return None

        cred = str(self.charm_config.credentials).strip()
        try:
            ref = normalize(cred)
            plaintext = decode_secret_key(self.model, ref)
        except (SecretNotFoundError, ModelError, Exception) as e:
            self.logger.warning("Failed to resolve credentials: %s", e)
            return None

        return GcsConnectionInfo(
            bucket=self.charm_config.bucket,
            secret_key=plaintext,
            storage_class=self.charm_config.storage_class or None,
            path=self.charm_config.path or None,
        )