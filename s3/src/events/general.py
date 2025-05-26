#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""S3 Provider related event handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ops
from ops.charm import ConfigChangedEvent, StartEvent

from constants import S3_RELATION_NAME
from core.context import Context
from events.base import BaseEventHandler, compute_status
from managers.s3 import S3Manager
from s3_lib import S3ProviderData
from utils.logging import WithLogging

if TYPE_CHECKING:
    from charm import S3IntegratorCharm


class GeneralEvents(BaseEventHandler, WithLogging):
    """Class implementing S3 Integration event hooks."""

    def __init__(self, charm: S3IntegratorCharm, context: Context):
        super().__init__(charm, "general")

        self.charm = charm
        self.context = context

        self.s3_provider_data = S3ProviderData(self.charm.model, S3_RELATION_NAME)
        self.s3_manager = S3Manager(self.s3_provider_data)

        self.framework.observe(self.charm.on.start, self._on_start)
        self.framework.observe(self.charm.on.update_status, self._on_update_status)
        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.secret_changed, self._on_secret_changed)

    @compute_status
    def _on_start(self, _: StartEvent) -> None:
        """Handle the charm startup event."""
        pass

    @compute_status
    def _on_update_status(self, event: ops.UpdateStatusEvent):
        """Handle the update status event."""
        pass

    @compute_status
    def _on_config_changed(self, event: ConfigChangedEvent) -> None:  # noqa: C901
        """Event handler for configuration changed events."""
        # Only execute in the unit leader
        if not self.charm.unit.is_leader():
            return

        self.logger.debug(f"Config changed... Current configuration: {self.charm.config}")
        self.s3_manager.update(self.context.s3)

    @compute_status
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

        self.s3_manager.update(self.context.s3)
