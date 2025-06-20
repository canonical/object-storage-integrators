#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Azure Storage manager."""
from azure.storage.blob import ContainerClient

from core.domain import AzureConnectionInfo
from utils.logging import WithLogging

class AzureStorageManager(WithLogging):
    """Azure manager class."""

    def __init__(self, relation_data):
        self.relation_data = relation_data

    def update(self, azure_connection_info: AzureConnectionInfo):
        """Update the contents of the relation data bag."""
        if len(self.relation_data.relations) > 0 and azure_connection_info:
            for relation in self.relation_data.relations:
                self.relation_data.update_relation_data(
                    relation.id, azure_connection_info.to_dict()
                )

    def create_container(self, connection_info: AzureConnectionInfo):
        """Create a container in Azure Storage."""
        connection_string = f"DefaultEndpointsProtocol=https;AccountName={connection_info.storage_account};AccountKey={connection_info.secret_key};EndpointSuffix=core.windows.net"

        try:
            container_client = ContainerClient.from_connection_string(
                conn_str=connection_string, container_name=connection_info.container, retry_total=3
            )
            container_client.create_container()
            self.logger.info(f"Container '{connection_info.container}' created successfully.")
        except Exception as e:
            self.logger.error(f"Failed to create container: {e}")
