#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Definition of various model classes."""


from dataclasses import dataclass


@dataclass
class AzureConnectionInfo:
    """Azure connection parameters."""

    connection_protocol: str
    container: str
    storage_account: str
    secret_key: str
    path: str = None

    @property
    def endpoint(self):
        """The endpoint constructed from the other parameters."""
        if self.connection_protocol.lower() in ("wasb", "wasbs"):
            return f"{self.connection_protocol}://{self.container}@{self.storage_account}.blob.core.windows.net/"
        elif self.connection_protocol.lower() in ("abfs", "abfss"):
            return f"{self.connection_protocol}://{self.container}@{self.storage_account}.dfs.core.windows.net/"
        return ""

    def to_dict(self) -> dict:
        """Return the Azure connection parameters as a dictionary."""
        data = {
            "connection-protocol": self.connection_protocol,
            "container": self.container,
            "storage-account": self.storage_account,
            "secret-key": self.secret_key,
            "endpoint": self.endpoint,
        }
        if self.path:
            data["path"] = self.path
        return data
