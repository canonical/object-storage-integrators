#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""A charm for integrating Google Cloud storage to a charmed application."""

import logging
import ops
from ops.model import BlockedStatus, ActiveStatus

from core.context import Context
from core.charm_config import CharmConfig, CharmConfigInvalidError
from events.provider import GCStorageProviderEvents
from constants import GCS_MANDATORY_OPTIONS

logger = logging.getLogger(__name__)


class GCStorageIntegratorCharm(ops.charm.CharmBase):
    """Charm for Google Cloud storage integrator service."""

    def __init__(self, *args) -> None:
        super().__init__(*args)

        self.framework.observe(self.on.start, self._sync_state)
        self.framework.observe(self.on.update_status, self._sync_state)
        self.framework.observe(self.on.config_changed, self._sync_state)

        self._charm_config: CharmConfig | None = None
        self.context: Context | None = None

        self.provider = GCStorageProviderEvents(self, lambda: self.context)

    def _sync_state(self, _=None):
        """Ensure the charm's state matches the desired config."""
        try:
            # Basic/offline validation
            cfg = CharmConfig.from_charm(self)
        except CharmConfigInvalidError as e:
            self.unit.status = BlockedStatus(e.msg)
            return

        missing = [k for k in GCS_MANDATORY_OPTIONS
                   if not (self.model.config.get(k) or "").strip()]
        if missing:
            self.unit.status = BlockedStatus(
                f"missing required config: {', '.join(missing)}"
            )
            return

        # Online checks
        ok, message = cfg.online_validate(self)
        if not ok:
            self.unit.status = BlockedStatus(message)
            return

        self._charm_config = cfg
        self.context = Context(model=self.model, config=cfg)
        self.unit.status = ActiveStatus("ready")



if __name__ == "__main__":
    ops.main.main(GCStorageIntegratorCharm)
