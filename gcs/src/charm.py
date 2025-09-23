#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""A charm for integrating Google Cloud storage to a charmed application."""

import logging

import ops
from data_platform_helpers.advanced_statuses.handler import StatusHandler
from events.provider import GCStorageProviderEvents
from events.general import GeneralEvents
from core.context import Context

logger = logging.getLogger(__name__)


class GCStorageIntegratorCharm(ops.charm.CharmBase):
    """Charm for Google Cloud storage integrator service."""

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.context = Context(self)
        self.provider_events = GCStorageProviderEvents(self, self.context)
        self.general_events = GeneralEvents(self, self.context)
        self.status = StatusHandler(  # priority order
            self,
            self.general_events,
            self.provider_events,
        )



if __name__ == "__main__":
    ops.main.main(GCStorageIntegratorCharm)
