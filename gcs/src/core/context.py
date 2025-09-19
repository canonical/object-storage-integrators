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
from utils.secrets import decode_secret_key_with_retry
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

    def __init__(self, model: Model):
        self.model = model

    @property
    def gc_storage(self) -> Optional[GcsConnectionInfo]:
        """Return information related to GC Storage connection parameters."""
        cfg = CharmConfig.from_charm(self)
        if not cfg or not cfg.bucket or not cfg.credentials:
            logger.warning("charm_config not set")
            return None

        cred = str(cfg.credentials).strip()
        plaintext = decode_secret_key_with_retry(self.model, cred)
        return GcsConnectionInfo(
            bucket=cfg.bucket,
            secret_key=plaintext,
            storage_class=cfg.storage_class or None,
            path=cfg.path or None,
        )