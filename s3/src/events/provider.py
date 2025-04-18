#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""S3 Provider related event handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from constants import S3_RELATION_NAME
from core.context import Context
from events.base import BaseEventHandler
from managers.s3 import S3Manager
from s3_lib import (
    S3ProviderData,
    S3ProviderEventHandlers,
    StorageConnectionInfoRequestedEvent,
)
from utils.logging import WithLogging

if TYPE_CHECKING:
    from charm import S3IntegratorCharm


class S3ProviderEvents(BaseEventHandler, WithLogging):
    """Class implementing S3 Integration event hooks."""

    def __init__(self, charm: S3IntegratorCharm, context: Context):
        super().__init__(charm, "s3-provider")

        self.charm = charm
        self.context = context
        self.s3_provider_data = S3ProviderData(self.charm.model, S3_RELATION_NAME)
        self.s3_provider = S3ProviderEventHandlers(self.charm, self.s3_provider_data)
        self.s3_manager = S3Manager(self.s3_provider_data)
        self.framework.observe(
            self.s3_provider.on.storage_connection_info_requested,
            self._on_s3_connection_info_requested,
        )

    def _on_s3_connection_info_requested(self, _: StorageConnectionInfoRequestedEvent) -> None:
        """Handle the `storage-connection-info-requested` event."""
        self.logger.info("On storage-connection-info-requested")
        if not self.charm.unit.is_leader():
            return

        bucket_name = self.charm.config.get("bucket")
        if not bucket_name:
            self.logger.warning("Bucket is setup by the requirer application!")

        self.s3_manager.update(self.context.s3)
