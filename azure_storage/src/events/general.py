#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Azure Storage Provider related event handlers."""

import ops
from charms.data_platform_libs.v0.azure_storage import AzureStorageProviderData
from ops import CharmBase
from ops.charm import ConfigChangedEvent, StartEvent

from constants import AZURE_RELATION_NAME, LEGACY_AZURE_RELATION_NAME
from core.context import Context
from events.base import BaseEventHandler, compute_status, defer_on_premature_data_access_error
from managers.azure_storage import AzureStorageManager
from utils.logging import WithLogging


class GeneralEvents(BaseEventHandler, WithLogging):
    """Class implementing Azure Integration event hooks."""

    def __init__(self, charm: CharmBase, context: Context):
        super().__init__(charm, "general")

        self.charm = charm
        self.context = context

        self.azure_provider_data = AzureStorageProviderData(self.charm.model, AZURE_RELATION_NAME)
        self.azure_storage_manager = AzureStorageManager(self.azure_provider_data)

        # DEPRECATED: This code is here only for backward compatibility.
        # TODO (azure-interface): Remove this once all users have migrated to the new azure storage interface
        self.legacy_azure_provider_data = AzureStorageProviderData(
            self.charm.model, LEGACY_AZURE_RELATION_NAME
        )
        self.legacy_azure_storage_manager = AzureStorageManager(self.legacy_azure_provider_data)
        self.framework.observe(
            self.charm.on[LEGACY_AZURE_RELATION_NAME].relation_joined, self._log_deprecation_notice
        )

        self.framework.observe(self.charm.on.start, self._on_start)
        self.framework.observe(self.charm.on.update_status, self._on_update_status)
        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.secret_changed, self._on_secret_changed)

    def _log_deprecation_notice(self, *args) -> None:
        """Log a deprecation notice for legacy interface.

        TODO (azure-interface): Remove this once all users have migrated to the new azure storage interface
        """
        self.logger.warning(
            "The interface 'azure' has been deprecated. Please use 'azure_storage' interface instead."
        )

    @compute_status
    def _on_start(self, _: StartEvent) -> None:
        """Handle the charm startup event."""
        pass

    @compute_status
    def _on_update_status(self, event: ops.UpdateStatusEvent):
        """Handle the update status event."""
        pass

    @compute_status
    @defer_on_premature_data_access_error
    def _on_config_changed(self, event: ConfigChangedEvent) -> None:  # noqa: C901
        """Event handler for configuration changed events."""
        # Only execute in the unit leader
        if not self.charm.unit.is_leader():
            return

        self.logger.debug(f"Config changed... Current configuration: {self.charm.config}")
        self.azure_storage_manager.update(self.context.azure_storage)

        # TODO (azure-interface): Remove this once all users have migrated to the new azure storage interface
        self.legacy_azure_storage_manager.update(self.context.azure_storage)

    @compute_status
    @defer_on_premature_data_access_error
    def _on_secret_changed(self, event: ops.SecretChangedEvent):
        """Handle the secret changed event.

        When a secret is changed, it is first checked that whether this particular secret
        is used in the charm's config. If yes, the secret is to be updated in the relation
        databag.
        """
        # Only execute in the unit leader
        if not self.charm.unit.is_leader():
            return

        if not self.charm.config.get("credentials"):
            return

        secret = event.secret
        if self.charm.config.get("credentials") != secret.id:
            return

        self.azure_storage_manager.update(self.context.azure_storage)

        # TODO (azure-interface): Remove this once all users have migrated to the new azure storage interface
        self.legacy_azure_storage_manager.update(self.context.azure_storage)
