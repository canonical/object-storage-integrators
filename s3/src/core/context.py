#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm Context definition and parsing logic."""

from typing import cast

from ops import ConfigData, Model

from core.domain import CharmConfig, S3ConnectionInfo
from utils.logging import WithLogging
from utils.secrets import decode_secret_key


class Context(WithLogging):
    """Properties and relations of the charm."""

    def __init__(self, model: Model, config: ConfigData):
        self.model = model
        self.charm_config = config

    @property
    def s3(self) -> S3ConnectionInfo | None:
        """Return information related to S3 connection parameters."""
        try:
            validated_config = CharmConfig(**self.charm_config)  # type: ignore
            credentials = validated_config.credentials
            access_key, secret_key = decode_secret_key(self.model, credentials)
        except Exception as exc:
            self.logger.exception(exc)
            return None

        s3 = cast(
            S3ConnectionInfo,
            validated_config.model_dump(mode="json", exclude_none=True, by_alias=True),
        )

        s3["access-key"] = access_key
        s3["secret-key"] = secret_key

        return s3
