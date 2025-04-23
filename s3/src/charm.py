#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""A charm for sharing s3 complaint object storage credentials to a charmed application."""

import logging

from ops import CharmBase, main

from core.context import Context
from events.general import GeneralEvents
from events.provider import S3ProviderEvents

logger = logging.getLogger(__name__)


class S3IntegratorCharm(CharmBase):
    """Charm for S3 integrator service."""

    # config_type = CharmConfig

    def __init__(self, *args) -> None:
        super().__init__(*args)

        # Context
        self.context = Context(model=self.model, config=self.config)

        # Event Handlers
        self.general_events = GeneralEvents(self, self.context)
        self.s3_provider_events = S3ProviderEvents(self, self.context)


if __name__ == "__main__":
    main(S3IntegratorCharm)
