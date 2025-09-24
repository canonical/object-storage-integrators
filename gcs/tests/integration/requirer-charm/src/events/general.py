#!/usr/bin/env python3
# Copyright 2025
# SPDX-License-Identifier: Apache-2.0

import logging

import ops
from charms.data_platform_libs.v0.object_storage import GcsContract
from ops.charm import CharmBase, ConfigChangedEvent, StartEvent
from ops.framework import Object

from events.requirer import GcsRequirer

logger = logging.getLogger(__name__)


class GeneralEvents(Object):
    """Lifecycle helper."""

    def __init__(self, charm: CharmBase, gcs_requirer: GcsRequirer):
        super().__init__(charm, "general")
        self.charm = charm
        self.gcs = gcs_requirer

        self.framework.observe(self.charm.on.start, self._on_start)
        self.framework.observe(self.charm.on.update_status, self._on_update_status)
        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.secret_changed, self._on_secret_changed)

    def _on_start(self, _: StartEvent):
        self.gcs.refresh_status()

    def _on_update_status(self, _: ops.UpdateStatusEvent):
        self.gcs.refresh_status()

    def _on_config_changed(self, event: ConfigChangedEvent):
        if self.charm.unit.is_leader():
            ov = self.gcs.overrides_from_config()
            self.contract = GcsContract(**ov)
            self.gcs.storage.contract = self.contract
            self.gcs.apply_overrides(ov)

    def _on_secret_changed(self, event: ops.SecretChangedEvent):
        self.gcs.handle_secret_changed(event)
