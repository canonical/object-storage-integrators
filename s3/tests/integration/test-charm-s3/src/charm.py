#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.


"""Application charm that connects to object storage provider charm.

This charm is meant to be used only for testing
the s3 requires-provides relation.
"""

import logging

from s3_lib import S3Requires, StorageConnectionInfoChangedEvent, StorageConnectionInfoGoneEvent
from ops.charm import CharmBase, RelationJoinedEvent
from ops import ActionEvent, main
from ops.model import ActiveStatus, WaitingStatus

logger = logging.getLogger(__name__)

PEER = "application-peers"

FIRST_RELATION = "first-s3-credentials"
SECOND_RELATION = "second-s3-credentials"
BUCKET_NAME = "test-bucket"


class ApplicationCharm(CharmBase):
    """Application charm that relates to S3 integrator."""

    def __init__(self, *args):
        super().__init__(*args)

        # Default charm events.
        self.framework.observe(self.on.start, self._on_start)

        # Events related to the requested database
        # (these events are defined in the database requires charm library).

        self.first_s3_client = S3Requires(self, FIRST_RELATION)
        self.second_s3_client = S3Requires(self, SECOND_RELATION, bucket=BUCKET_NAME)

        # add relation
        self.framework.observe(
            self.first_s3_client.on.s3_connection_info_changed,
            self._on_first_storage_connection_info_changed,
        )
        self.framework.observe(
            self.second_s3_client.on.s3_connection_info_changed,
            self._on_second_storage_connection_info_changed,
        )

        self.framework.observe(
            self.on[FIRST_RELATION].relation_joined, self._on_first_relation_joined
        )
        self.framework.observe(
            self.on[SECOND_RELATION].relation_joined, self._on_second_relation_joined
        )

        self.framework.observe(
            self.first_s3_client.on.s3_connection_info_gone,
            self._on_first_storage_connection_info_gone,
        )
        self.framework.observe(
            self.second_s3_client.on.s3_connection_info_gone,
            self._on_second_storage_connection_info_gone,
        )
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.get_first_s3_action, self._on_get_first_s3_action)
        self.framework.observe(self.on.get_second_s3_action, self._on_get_second_s3_action)

    def _on_start(self, _) -> None:
        """Only sets an waiting status."""
        self.unit.status = WaitingStatus("Waiting for relation")

    def _on_first_relation_joined(self, _: RelationJoinedEvent):
        """On s3 credential relation joined."""
        logger.info("Relation_1 joined...")
        self.unit.status = ActiveStatus()

    def _on_second_relation_joined(self, _: RelationJoinedEvent):
        """On s3 credential relation joined."""
        logger.info("Relation_2 joined...")
        self.unit.status = ActiveStatus()

    def _on_first_storage_connection_info_changed(self, e: StorageConnectionInfoChangedEvent):
        credentials = self.first_s3_client.get_s3_connection_info()
        logger.info(f"Relation_1 credentials changed. New credentials: {credentials}")

    def _on_second_storage_connection_info_changed(self, e: StorageConnectionInfoChangedEvent):
        credentials = self.second_s3_client.get_s3_connection_info()
        logger.info(f"Relation_2 credentials changed. New credentials: {credentials}")

    def _on_first_storage_connection_info_gone(self, _: StorageConnectionInfoGoneEvent):
        logger.info("Relation_1 credentials gone...")
        self.unit.status = WaitingStatus("Waiting for relation")

    def _on_second_storage_connection_info_gone(self, _: StorageConnectionInfoGoneEvent):
        logger.info("Relation_2 credentials gone...")
        self.unit.status = WaitingStatus("Waiting for relation")

    def _on_get_first_s3_action(self, event: ActionEvent) -> None:
        event.set_results(self.first_s3_client.get_s3_connection_info())

    def _on_get_second_s3_action(self, event: ActionEvent) -> None:
        event.set_results(self.second_s3_client.get_s3_connection_info())

    def _on_update_status(self, _):
        first_info = self.first_s3_client.get_s3_connection_info()
        logger.info(f"First s3 client info: {first_info}")
        second_info = self.second_s3_client.get_s3_connection_info()
        logger.info(f"Second s3 client info: {second_info}")


if __name__ == "__main__":
    main(ApplicationCharm)
