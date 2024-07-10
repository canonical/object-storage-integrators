#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Azure Storage Provider related event handlers."""


from charms.data_platform_libs.v0.object_storage import (
    AzureStorageProviderData,
    AzureStorageProviderEventHandlers,
    CredentialRequestedEvent,
)
from ops import CharmBase

from constants import AZURE_RELATION_NAME
from core.context import Context
from events.base import BaseEventHandler
from managers.object_storage import ObjectStorageManager
from utils.logging import WithLogging


class AzureStorageProviderEvents(BaseEventHandler, WithLogging):
    """Class implementing Azure Integration event hooks."""

    def __init__(self, charm: CharmBase, context: Context):
        super().__init__(charm, "azure-provider")

        self.charm = charm
        self.context = context

        self.azure_provider_data = AzureStorageProviderData(self.charm.model, AZURE_RELATION_NAME)
        self.azure_provider = AzureStorageProviderEventHandlers(
            self.charm, self.azure_provider_data
        )
        self.object_storage_manager = ObjectStorageManager(self.azure_provider_data)

        self.framework.observe(
            self.azure_provider.on.storage_connection_info_requested, self._on_azure_storage_connection_info_requested
        )

    def _on_azure_storage_connection_info_requested(self, event: CredentialRequestedEvent):
        """Handle the `credential-requested` event."""
        if not self.charm.unit.is_leader():
            return

        container_name = self.charm.config.get("container")
        assert container_name is not None

        self.object_storage_manager.update(self.context.azure_storage)
