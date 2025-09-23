# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""File containing constants to be used in the charm."""

GCS_RELATION_NAME = "gcs-credentials"
CREDENTIAL_FIELD = "credentials"
ALLOWED_OVERRIDES = ["bucket", "storage-class", "path"]
MANDATORY_OPTIONS = ["bucket", "credentials"]
STATUS_PEERS_RELATION_NAME = "status-peers"
