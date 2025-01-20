#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Azure Storage Provider related event handlers."""

from charms.data_platform_libs.v0.azure_storage import (
    AzureStorageProviderData,
    AzureStorageProviderEventHandlers,
    StorageConnectionInfoRequestedEvent,
)
from ops import CharmBase

from constants import AZURE_RELATION_NAME, LEGACY_AZURE_RELATION_NAME
from core.context import Context
from events.base import BaseEventHandler
from managers.azure_storage import AzureStorageManager
from utils.logging import WithLogging


class AzureStorageProviderEvents(BaseEventHandler, WithLogging):
    """Class implementing Azure Integration event hooks."""

    def __init__(self, charm: CharmBase, context: Context):
        super().__init__(charm, "azure-storage-provider")

        self.charm = charm
        self.context = context

        self.azure_provider_data = AzureStorageProviderData(self.charm.model, AZURE_RELATION_NAME)
        self.azure_provider = AzureStorageProviderEventHandlers(
            self.charm, self.azure_provider_data
        )
        self.azure_storage_manager = AzureStorageManager(self.azure_provider_data)
        self.framework.observe(
            self.azure_provider.on.storage_connection_info_requested,
            self._on_azure_storage_connection_info_requested,
        )

        # DEPRECATED: This code is here only for backward compatibility.
        # TODO (azure-interface): Remove this once all users have migrated to the new azure storage interface
        self.legacy_azure_provider_data = AzureStorageProviderData(
            self.charm.model, LEGACY_AZURE_RELATION_NAME
        )
        self.legacy_azure_provider = AzureStorageProviderEventHandlers(
            self.charm, self.legacy_azure_provider_data
        )
        self.legacy_azure_storage_manager = AzureStorageManager(self.legacy_azure_provider_data)
        self.framework.observe(
            self.legacy_azure_provider.on.storage_connection_info_requested,
            self._on_azure_storage_connection_info_requested,
        )

    def _on_azure_storage_connection_info_requested(
        self, event: StorageConnectionInfoRequestedEvent
    ):
        """Handle the `storage-connection-info-requested` event."""
        self.logger.info("On storage-connection-info-requested")
        if not self.charm.unit.is_leader():
            return

        container_name = self.charm.config.get("container")
        # assert container_name is not None
        if not container_name:
            self.logger.warning("Container is setup by the requirer application!")

        # TODO (azure-interface): Remove this once all users have migrated to the new azure storage interface
        self.legacy_azure_storage_manager.update(self.context.azure_storage)

        self.azure_storage_manager.update(self.context.azure_storage)
