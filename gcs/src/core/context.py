#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm Context definition and parsing logic."""

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from data_platform_helpers.advanced_statuses.protocol import StatusesState, StatusesStateProtocol
from ops import Object

from constants import STATUS_PEERS_RELATION_NAME
from utils.logging import WithLogging
from utils.secrets import decode_secret_key_with_retry

if TYPE_CHECKING:
    from charm import GCStorageIntegratorCharm

logger = logging.getLogger(__name__)


@dataclass
class GcsConnectionInfo:
    """Google Cloud Storage connection parameters."""

    bucket: str
    secret_key: str
    storage_class: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> dict:
        """Return a dict representation of the object."""
        d = {"bucket": self.bucket, "secret-key": self.secret_key}
        if self.storage_class:
            d["storage-class"] = self.storage_class
        if self.path:
            d["path"] = self.path
        return d


class Context(Object, WithLogging, StatusesStateProtocol):
    """Properties and relations of the charm."""

    def __init__(self, charm: "GCStorageIntegratorCharm"):
        super().__init__(charm, "charm_context")
        self.charm = charm
        self.charm_config = self.charm.config
        self.statuses = StatusesState(self, STATUS_PEERS_RELATION_NAME)

    @property
    def gc_storage(self) -> Optional[GcsConnectionInfo]:
        """Return information related to GC Storage connection parameters."""
        try:
            cfg = self.charm.config
            credentials = cfg.get("credentials")
            cred = str(credentials).strip()
            plaintext = decode_secret_key_with_retry(self.charm.model, cred)
        except Exception as exc:
            self.logger.error(exc)
            return None
        if isinstance(plaintext, (dict, list)):
            secret_str = json.dumps(plaintext)
        else:
            secret_str = str(plaintext)
        return GcsConnectionInfo(
            bucket=cfg.get("bucket"),
            secret_key=secret_str,
            storage_class=cfg.get("storage_class") or None,
            path=cfg.get("path") or None,
        )
