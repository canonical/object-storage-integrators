#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm Context definition and parsing logic."""

from typing import Optional

from ops import ConfigData, Model
from ops.model import SecretNotFoundError, ModelError
from constants import GSC_MANDATORY_OPTIONS
from core.domain import GcsConnectionInfo
from utils.logging import WithLogging
from utils.secrets import decode_secret_key, normalize
from charm_config import CharmConfig


class Context(WithLogging):
    """Properties and relations of the charm."""

    def __init__(self, model: Model, config: CharmConfig):
        self.model = model
        self.config = config

    @property
    def gc_storage(self) -> Optional[GcsConnectionInfo]:
        """Return information related to GC Storage connection parameters."""
        cfg = self.config
        if cfg is None:
            return None

        try:
            sa_json = decode_secret_key(self.model, normalize(cfg.service_account_json_secret))
        except (SecretNotFoundError, ModelError) as e:
            self.logger.info("GCS service-account secret not available yet: %s", e)
            return None
        except Exception as e:
            self.logger.warning("Failed to decode GCS service-account secret: %s", e)
            return None

        return GcsConnectionInfo(
            bucket=cfg.bucket,
            service_account_json_key_secret=sa_json,
            storage_class=cfg.storage_class or None,
            path=cfg.path or "",
        )
