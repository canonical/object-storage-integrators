#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""File containing all possible statuses for S3 Integrator charm."""

from enum import Enum

from data_platform_helpers.advanced_statuses.models import StatusObject


class CharmStatuses(Enum):
    """Generic status objects related to the charm."""

    ACTIVE_IDLE = StatusObject(status="active", message="")


class ConfigStatuses(Enum):
    """Status objects related to config options."""

    @staticmethod
    def missing_config_parameters(fields: list[str]) -> StatusObject:
        """Some of the mandatory config values are missing."""
        fields_str = ", ".join(f"'{field}'" for field in fields)
        return StatusObject(
            status="blocked",
            message=f"Missing config(s): {fields_str}",
            action=f"Set config(s): {fields_str}",
        )

    @staticmethod
    def invalid_config_parameters(fields: list[str]) -> StatusObject:
        """Some of the config values are invalid."""
        fields_str = ", ".join(f"'{field}'" for field in fields)
        return StatusObject(
            status="blocked",
            message=f"Invalid config(s): {fields_str}",
            action=f"Fix invalid config(s): {fields_str}",
        )

    @staticmethod
    def secret_does_not_exist(secret_id: str) -> StatusObject:
        """The secret does not exist in the model."""
        return StatusObject(
            status="blocked",
            message=f"The secret '{secret_id}' does not exist",
            action=f"Make sure the secret {secret_id} exists in this Juju model",
        )

    @staticmethod
    def field_missing_in_secret(secret_id: str, fields: list[str]) -> StatusObject:
        """Some mandatory fields are missing in the secret content."""
        fields_str = ", ".join(f"'{field}'" for field in fields)
        return StatusObject(
            status="blocked",
            message=f"The secret '{secret_id}' is missing mandatory field(s): {fields_str}",
            action="Add the missing fields to the secret with: juju update-secret secret_id field=value",
        )

    @staticmethod
    def secret_not_granted(secret_id: str, app_name: str) -> StatusObject:
        """The secret has not been granted to the charm."""
        return StatusObject(
            status="blocked",
            message=f"The secret '{secret_id}' has not been granted to the charm",
            action=f"Run: juju grant-secret {secret_id} {app_name}",
        )

    @staticmethod
    def secret_cannot_be_decoded(secret_id: str) -> StatusObject:
        """The secret cannot be decoded."""
        return StatusObject(
            status="blocked",
            message=f"The secret '{secret_id}' could not be decoded",
            action="Check Juju logs for more detail",
        )


class BucketStatuses(Enum):
    """Status objects related to S3 buckets."""

    @staticmethod
    def bucket_unavailable(bucket_names: list[str]) -> StatusObject:
        """The bucket is not available for use."""
        buckets_str = ", ".join(f"'{bucket_name}'" for bucket_name in bucket_names)
        return StatusObject(
            status="blocked",
            message=f"Could not fetch or create bucket(s): {buckets_str}",
            action="Make sure the bucket name and S3 credentials are valid.",
        )

    @staticmethod
    def bucket_name_invalid(bucket_names: list[str]) -> StatusObject:
        """The bucket name is not valid."""
        buckets_str = ", ".join(f"'{bucket_name}'" for bucket_name in bucket_names)
        return StatusObject(
            status="blocked",
            message=f"Invalid name for bucket(s): {buckets_str}",
            action="Make sure the bucket name is valid.",
        )

    @staticmethod
    def creating_bucket(bucket_name: str) -> StatusObject:
        """The bucket is being created."""
        return StatusObject(
            status="maintenance",
            message=f"Creating bucket: '{bucket_name}'...",
            running="blocking",
        )
