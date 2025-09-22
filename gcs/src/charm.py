#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""A charm for integrating Google Cloud storage to a charmed application."""

import logging

import ops
from events.provider import GCStorageProviderEvents
from events.general import GeneralEvents

logger = logging.getLogger(__name__)


class GCStorageIntegratorCharm(ops.charm.CharmBase):
    """Charm for Google Cloud storage integrator service."""

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.provider = GCStorageProviderEvents(self)
        self.general_events = GeneralEvents(self)


if __name__ == "__main__":
    ops.main.main(GCStorageIntegratorCharm)
