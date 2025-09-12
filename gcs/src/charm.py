#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""A charm for integrating Google Cloud storage to a charmed application."""

import logging
from typing import Optional

import ops
from ops.model import BlockedStatus, ActiveStatus

from core.context import Context
from core.charm_config import CharmConfig, CharmConfigInvalidError
from events.provider import GCStorageProviderEvents

logger = logging.getLogger(__name__)


class GCStorageIntegratorCharm(ops.charm.CharmBase):
    """Charm for Google Cloud storage integrator service."""

    def __init__(self, *args) -> None:
        super().__init__(*args)

        self.framework.observe(self.on.start, self._sync_state)
        self.framework.observe(self.on.update_status, self._sync_state)
        self.framework.observe(self.on.config_changed, self._sync_state)

        self._charm_config = self.get_charm_config()
        self.context = Context(self.model, self._charm_config)
        self.provider = GCStorageProviderEvents(self)

    def _sync_state(self, _=None):
        """Ensure the charm's state matches the desired config."""
        cfg = self.get_charm_config()
        if not cfg:
            return

        # Online checks
        ok, message = cfg.online_validate(self)
        if not ok:
            if "waiting for" in message or "permission" in message.lower():
                self.unit.status = ops.model.WaitingStatus(message)
            else:
                self.unit.status = BlockedStatus(message)
            return

        self._charm_config = cfg
        self.context = Context(self.model, cfg)
        self.unit.status = ActiveStatus("ready")

    def get_charm_config(self) -> Optional[CharmConfig]:
        try:
            return CharmConfig.from_charm(self)
        except CharmConfigInvalidError as e:
            self.unit.status = BlockedStatus(e.msg)
            return None


if __name__ == "__main__":
    ops.main.main(GCStorageIntegratorCharm)
