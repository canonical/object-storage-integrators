#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm Context definition and parsing logic."""

from typing import Optional

from ops import ConfigData, Model

from constants import AZURE_MANDATORY_OPTIONS
from core.domain import AzureConnectionInfo
from utils.logging import WithLogging
from utils.secrets import decode_secret


class Context(WithLogging):
    """Properties and relations of the charm."""

    def __init__(self, model: Model, config: ConfigData):
        self.model = model
        self.charm_config = config

    @property
    def azure_storage(self) -> Optional[AzureConnectionInfo]:
        """Return information related to Azure Storage connection parameters."""
        for opt in AZURE_MANDATORY_OPTIONS:
            if self.charm_config.get(opt) is None:
                return None

        storage_account_secret = None
        service_principal_secret = None
        try:
            secret = decode_secret(self.model, self.charm_config.get("credentials"))
            storage_account_secret = secret.get("secret-key")
            service_principal_secret = secret.get("client-secret")
        except Exception as e:
            self.logger.warning(str(e))

        secret_key = ""
        if bool(storage_account_secret) != bool(service_principal_secret):
            secret_key = storage_account_secret or service_principal_secret

        return AzureConnectionInfo(
            connection_protocol=self.charm_config.get("connection-protocol"),
            container=self.charm_config.get("container"),
            storage_account=self.charm_config.get("storage-account"),
            endpoint=self.charm_config.get("endpoint"),
            resource_group=self.charm_config.get("resource-group"),
            path=self.charm_config.get("path"),
            secret_key=secret_key,
            tenant_id=self.charm_config.get("tenant-id") if service_principal_secret else None,
            client_id=self.charm_config.get("client-id") if service_principal_secret else None,
            subscription_id=self.charm_config.get("subscription-id")
            if service_principal_secret
            else None,
        )
