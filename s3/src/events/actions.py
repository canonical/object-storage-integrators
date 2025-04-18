#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Action related event handlers."""

from ops import CharmBase
from ops.charm import ActionEvent

from core.context import Context
from events.base import BaseEventHandler
from utils.logging import WithLogging


class ActionEvents(BaseEventHandler, WithLogging):
    """Class implementing charm action event hooks."""

    def __init__(self, charm: CharmBase, context: Context):
        super().__init__(charm, "action-events")

        self.charm = charm
        self.context = context

        self.framework.observe(
            self.charm.on.get_s3_connection_info_action,
            self.on_get_connection_info_action,
        )

    def on_get_connection_info_action(self, event: ActionEvent):
        """Handle the action `get_connection_info`."""
        if not self.context.s3:
            event.fail("Credentials are not set!")
            return

        results = self.context.s3
        results = {k: v for k, v in results.items() if v is not None}
        if "access-key" in results:
            results["access-key"] = "**********"
        if "secret-key" in results:
            results["secret-key"] = "**********"
        event.set_results(results)
