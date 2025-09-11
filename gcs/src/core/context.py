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


class Context(WithLogging):
    """Properties and relations of the charm."""

    def __init__(self, model: Model, config: CharmConfig):
        self.model = model
        self.charm_config = config

    @property
    def gc_storage(self) -> Optional[GcsConnectionInfo]:
        """Return information related to GC Storage connection parameters."""
        if not (self.charm_config.bucket and self.charm_config.credentials):
            return None

        try:
            sa_json = decode_secret_key(self.model, normalize(self.charm_config.credentials))
        except (SecretNotFoundError, ModelError) as e:
            self.logger.info("GCS service-account secret not available yet: %s", e)
            return None
        except Exception as e:
            self.logger.warning("Failed to decode GCS service-account secret: %s", e)
            return None

        return GcsConnectionInfo(
            bucket=self.charm_config.bucket,
            sa_key=sa_json,
            storage_class=self.charm_config.storage_class or None,
            path=self.charm_config.path or "",
        )
