#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""A charm for integrating object storage to a charmed application."""

import logging

import ops
import ops.charm
import ops.framework
import ops.lib
import ops.main
import ops.model
from events.general import GeneralEvents
from events.provider import AzureStorageProviderEvents
from events.actions import ActionEvents
from core.context import Context


logger = logging.getLogger(__name__)


class ObjectStorageIntegratorCharm(ops.charm.CharmBase):
    """Charm for object storage integrator service."""

    def __init__(self, *args) -> None:
        super().__init__(*args)

        # Context
        self.context = Context(model=self.model, config=self.config)

        # Event Handlers
        self.general_events = GeneralEvents(self, self.context)
        self.azure_storage_provider_events = AzureStorageProviderEvents(self, self.context)
        self.action_events = ActionEvents(self, self.context)


if __name__ == "__main__":
    ops.main.main(ObjectStorageIntegratorCharm)
