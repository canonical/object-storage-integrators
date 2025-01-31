#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Application charm that connects to object storage provider charm.

This charm is meant to be used only for testing
the azure storage requires-provides relation.
"""

import logging

from charms.data_platform_libs.v0.azure_storage import (
    AzureStorageRequires,
    StorageConnectionInfoChangedEvent,
    StorageConnectionInfoGoneEvent,
)
from ops.charm import CharmBase, RelationJoinedEvent
from ops.main import main
from ops.model import ActiveStatus, WaitingStatus

logger = logging.getLogger(__name__)

PEER = "application-peers"

FIRST_RELATION = "first-azure-storage-credentials"
SECOND_RELATION = "second-azure-storage-credentials"
CONTAINER_NAME = "test-bucket"


class ApplicationCharm(CharmBase):
    """Application charm that relates to Object Storage integrator."""

    def __init__(self, *args):
        super().__init__(*args)

        # Default charm events.
        self.framework.observe(self.on.start, self._on_start)

        # Events related to the requested database
        # (these events are defined in the database requires charm library).

        self.first_azure_client = AzureStorageRequires(self, FIRST_RELATION)
        self.second_azure_client = AzureStorageRequires(
            self, SECOND_RELATION, container=CONTAINER_NAME
        )

        # add relation
        self.framework.observe(
            self.first_azure_client.on.storage_connection_info_changed,
            self._on_first_storage_connection_info_changed,
        )
        self.framework.observe(
            self.second_azure_client.on.storage_connection_info_changed,
            self._on_second_storage_connection_info_changed,
        )

        self.framework.observe(
            self.on[FIRST_RELATION].relation_joined, self._on_first_relation_joined
        )
        self.framework.observe(
            self.on[SECOND_RELATION].relation_joined, self._on_second_relation_joined
        )

        self.framework.observe(
            self.first_azure_client.on.storage_connection_info_gone,
            self._on_first_storage_connection_info_gone,
        )
        self.framework.observe(
            self.second_azure_client.on.storage_connection_info_gone,
            self._on_second_storage_connection_info_gone,
        )
        self.framework.observe(self.on.update_status, self._on_update_status)

    def _on_start(self, _) -> None:
        """Only sets an waiting status."""
        self.unit.status = WaitingStatus("Waiting for relation")

    def _on_first_relation_joined(self, _: RelationJoinedEvent):
        """On Azure credential relation joined."""
        logger.info("Relation_1 joined...")
        self.unit.status = ActiveStatus()

    def _on_second_relation_joined(self, _: RelationJoinedEvent):
        """On azure credential relation joined."""
        logger.info("Relation_2 joined...")
        self.unit.status = ActiveStatus()

    def _on_first_storage_connection_info_changed(self, e: StorageConnectionInfoChangedEvent):
        credentials = self.first_azure_client.get_azure_storage_connection_info()
        logger.info(f"Relation_1 credentials changed. New credentials: {credentials}")

    def _on_second_storage_connection_info_changed(self, e: StorageConnectionInfoChangedEvent):
        credentials = self.second_azure_client.get_azure_storage_connection_info()
        logger.info(f"Relation_2 credentials changed. New credentials: {credentials}")

    def _on_first_storage_connection_info_gone(self, _: StorageConnectionInfoGoneEvent):
        logger.info("Relation_1 credentials gone...")
        self.unit.status = WaitingStatus("Waiting for relation")

    def _on_second_storage_connection_info_gone(self, _: StorageConnectionInfoGoneEvent):
        logger.info("Relation_2 credentials gone...")
        self.unit.status = WaitingStatus("Waiting for relation")

    @property
    def _peers(self):
        """Retrieve the peer relation (`ops.model.Relation`)."""
        return self.model.get_relation(PEER)

    def _on_update_status(self, _):
        first_info = self.first_azure_client.get_azure_storage_connection_info()
        logger.info(f"First Azure client info: {first_info}")
        second_info = self.second_azure_client.get_azure_storage_connection_info()
        logger.info(f"Second Azure client info: {second_info}")


if __name__ == "__main__":
    main(ApplicationCharm)
