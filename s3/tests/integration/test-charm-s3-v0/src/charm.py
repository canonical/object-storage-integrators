#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.


"""Application charm that connects to object storage provider charm.

This charm is meant to be used only for testing
the s3 requires-provides relation.
"""

import logging

from charms.data_platform_libs.v0.s3 import (
    CredentialsChangedEvent,
    CredentialsGoneEvent,
    S3Requirer,
)
from ops import ActionEvent, main
from ops.charm import CharmBase, RelationJoinedEvent
from ops.model import ActiveStatus, WaitingStatus

logger = logging.getLogger(__name__)

S3_RELATION_NAME = "s3-credentials"


class ApplicationCharm(CharmBase):
    """Application charm that relates to S3 integrator."""

    def __init__(self, *args):
        super().__init__(*args)

        # Default charm events.
        self.framework.observe(self.on.start, self._on_start)

        # Events related to the requested database
        # (these events are defined in the database requires charm library).
        self.s3_requirer = S3Requirer(self, S3_RELATION_NAME)

        # add relation
        self.framework.observe(
            self.s3_requirer.on.credentials_changed,
            self._on_storage_connection_info_changed,
        )
        self.framework.observe(self.on[S3_RELATION_NAME].relation_joined, self._on_relation_joined)

        self.framework.observe(
            self.s3_requirer.on.credentials_gone,
            self._on_storage_connection_info_gone,
        )

        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(
            self.on.get_s3_connection_info_action, self._on_get_s3_connection_info_action
        )

    def _on_start(self, _) -> None:
        """Only sets an waiting status."""
        if self.model.get_relation(S3_RELATION_NAME):
            self.unit.status = ActiveStatus()
        else:
            self.unit.status = WaitingStatus("Waiting for relation")

    def _on_relation_joined(self, _: RelationJoinedEvent):
        """On s3 credential relation joined."""
        logger.info("S3 relation joined...")
        self.unit.status = ActiveStatus()

    def _on_storage_connection_info_changed(self, e: CredentialsChangedEvent):
        credentials = self.s3_requirer.get_s3_connection_info()
        logger.info(f"S3 credentials changed. New credentials: {credentials}")

    def _on_storage_connection_info_gone(self, _: CredentialsGoneEvent):
        logger.info("S3 credentials gone...")
        self.unit.status = WaitingStatus("Waiting for relation")

    def _on_get_s3_connection_info_action(self, event: ActionEvent) -> None:
        event.set_results(self.s3_requirer.get_s3_connection_info())

    def _on_update_status(self, _):
        s3_info = self.s3_requirer.get_s3_connection_info()
        logger.info(f"S3 client info: {s3_info}")


if __name__ == "__main__":
    main(ApplicationCharm)
