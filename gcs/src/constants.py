# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""File containing constants to be used in the charm."""

GCS_RELATION_NAME = "gcs-credentials"

GCS_MANDATORY_OPTIONS = ["bucket", "credentials"]

KEYS_LIST = ["sa-key"]
OPTIONAL_OVERRIDE = "bucket"
CREDENTIAL_FIELD = "credentials"