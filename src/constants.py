# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""File containing constants to be used in the charm."""

# TODO (azure-interface): Remove this once all users migrate to the new azure storage interface
LEGACY_AZURE_RELATION_NAME = "azure-credentials"

AZURE_RELATION_NAME = "azure-storage-credentials"

AZURE_MANDATORY_OPTIONS = ["container", "storage-account", "credentials", "connection-protocol"]

KEYS_LIST = ["secret-key"]
