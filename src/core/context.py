#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm Context definition and parsing logic."""

from ops import ConfigData, Model

from constants import AZURE_MANDATORY_OPTIONS
from core.domain import AzureConnectionInfo
from utils.logging import WithLogging
from utils.secrets import decode_secret_key


class Context(WithLogging):
    """Properties and relations of the charm."""

    def __init__(self, model: Model, config: ConfigData):
        self.model = model
        self.charm_config = config

    @property
    def azure_storage(self):
        """Return information related to Azure Storage connection parameters."""
        for opt in AZURE_MANDATORY_OPTIONS:
            if self.charm_config.get(opt) is None:
                return {}

        credentials = self.charm_config.get("credentials")
        try:
            secret_key = decode_secret_key(self.model, credentials)
        except Exception as e:
            self.logger.warning(str(e))
            secret_key = ""

        return AzureConnectionInfo(
            connection_protocol=self.charm_config.get("connection-protocol"),
            container=self.charm_config.get("container"),
            storage_account=self.charm_config.get("storage-account"),
            secret_key=secret_key,
            path=self.charm_config.get("path"),
        )
