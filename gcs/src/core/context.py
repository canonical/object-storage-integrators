#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm Context definition and parsing logic."""
import json
import logging
from typing import Optional

from ops.charm import CharmBase
from ops.model import SecretNotFoundError
from utils.logging import WithLogging
from utils.secrets import decode_secret_key_with_retry
from core.charm_config import CharmConfig
from dataclasses import dataclass
from core.charm_config import CharmConfigInvalidError, get_charm_config

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

    def __init__(self, charm: CharmBase):
        self.charm = charm

    @property
    def gc_storage(self) -> Optional[GcsConnectionInfo]:
        """Return information related to GC Storage connection parameters."""
        cfg = get_charm_config(self.charm)
        if not cfg:
            logger.warning("charm_config not set")
            return None
        if not cfg.bucket or not cfg.credentials:
            logger.warning("bucket and credentials not set")
            return None
        cred = str(cfg.credentials).strip()
        try:
            plaintext = decode_secret_key_with_retry(self.charm.model, cred)
        except SecretNotFoundError:
            logger.warning("waiting for secret grant: service-account-json-secret")
            return None
        except Exception as e:
            logger.warning("invalid service-account secret: %s", e)
            return None
        if isinstance(plaintext, (dict, list)):
            secret_str = json.dumps(plaintext)
        else:
            secret_str = str(plaintext)
        return GcsConnectionInfo(
            bucket=cfg.bucket,
            secret_key=secret_str,
            storage_class=cfg.storage_class or None,
            path=cfg.path or None,
        )