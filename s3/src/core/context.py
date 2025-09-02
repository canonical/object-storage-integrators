#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm Context definition and parsing logic."""

from typing import TYPE_CHECKING, cast

from data_platform_helpers.advanced_statuses.protocol import StatusesState, StatusesStateProtocol
from ops import Object

from constants import STATUS_PEERS_RELATION_NAME
from core.domain import CharmConfig, S3ConnectionInfo
from utils.logging import WithLogging
from utils.secrets import decode_secret_key

if TYPE_CHECKING:
    from charm import S3IntegratorCharm


class Context(Object, WithLogging, StatusesStateProtocol):
    """Properties and relations of the charm."""

    def __init__(self, charm: "S3IntegratorCharm"):
        super().__init__(charm, "charm_context")
        self.charm = charm
        self.charm_config = charm.config
        self.statuses = StatusesState(self, STATUS_PEERS_RELATION_NAME)

    @property
    def s3(self) -> S3ConnectionInfo | None:
        """Return information related to S3 connection parameters."""
        try:
            validated_config = CharmConfig(**self.charm_config)  # type: ignore
            credentials = validated_config.credentials
            access_key, secret_key = decode_secret_key(self.charm.model, credentials)
        except Exception as exc:
            self.logger.error(exc)
            return None

        s3 = cast(
            S3ConnectionInfo,
            validated_config.model_dump(mode="json", exclude_none=True, by_alias=True),
        )

        s3["access-key"] = access_key
        s3["secret-key"] = secret_key

        return s3
