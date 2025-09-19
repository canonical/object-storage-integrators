#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Google Cloud Storage general event handlers."""

import ops
from charms.data_platform_libs.v0.object_storage import StorageProviderData
from ops import CharmBase, BlockedStatus
from ops.charm import ConfigChangedEvent, StartEvent

from constants import GCS_RELATION_NAME
from core.context import Context
from core.charm_config import CharmConfig
from events.base import BaseEventHandler, compute_status
from managers.gc_storage import GCStorageManager
from utils.logging import WithLogging
from utils.secrets import normalize


class GeneralEvents(BaseEventHandler, WithLogging):
    """Class implementing GCS Integration event hooks."""

    def __init__(self, charm: CharmBase):
        super().__init__(charm, "general")

        self.charm = charm
        self.gcs_provider_data = StorageProviderData(self.charm.model, GCS_RELATION_NAME)
        self.gc_storage_manager = GCStorageManager(self.gcs_provider_data)
        self.framework.observe(self.charm.on.start, self._on_start)
        self.framework.observe(self.charm.on.update_status, self._on_update_status)
        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.secret_changed, self._on_secret_changed)

    def _ctx(self) -> Context:
        return Context(self.charm.model)

    @compute_status
    def _on_start(self, _: StartEvent) -> None:
        """Handle the charm startup event."""
        pass

    @compute_status
    def _on_update_status(self, event: ops.UpdateStatusEvent):
        """Handle the update status event."""
        pass

    @compute_status
    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        """Event handler for the configuration changed events."""
        if not self.charm.unit.is_leader():
            return

        context = self._ctx()
        if not context:
            return

        self.logger.debug(f"Config changed. Current configuration: {self.charm.config}")
        self.gc_storage_manager.update(context.gc_storage)

    @compute_status
    def _on_secret_changed(self, event: ops.SecretChangedEvent):
        """Handle the secret changed event.

        When a secret is changed, it is first checked that whether this particular secret
        is used in the charm's config. If yes, the secret is to be updated in the relation
        databag.
        """
        if not self.charm.unit.is_leader():
            return
        cfg = CharmConfig.from_charm(self)
        if not cfg:
            return
        secret = event.secret
        ref = normalize(str(cfg.credentials))
        if not ref:
            return

        context = self._ctx()
        if not context:
            return

        # match either by id or label
        if secret.id != ref and (secret.label or "") != ref:
            return

        self.gc_storage_manager.update(context.gc_storage)

