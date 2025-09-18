#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""S3 Provider related event handlers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from data_platform_helpers.advanced_statuses.models import StatusObject
from data_platform_helpers.advanced_statuses.protocol import ManagerStatusProtocol
from data_platform_helpers.advanced_statuses.types import Scope

from constants import S3_RELATION_NAME
from core.context import Context
from core.domain import BUCKET_REGEX
from events.base import BaseEventHandler
from events.statuses import BucketStatuses, CharmStatuses
from managers.s3 import S3BucketError, S3Manager
from s3_lib import (
    S3ProviderData,
    S3ProviderEventHandlers,
    StorageConnectionInfoGoneEvent,
    StorageConnectionInfoRequestedEvent,
)

if TYPE_CHECKING:
    from charm import S3IntegratorCharm


class S3ProviderEvents(BaseEventHandler, ManagerStatusProtocol):
    """Class implementing S3 Integration event hooks."""

    def __init__(self, charm: S3IntegratorCharm, context: Context):
        self.name = "s3-provider"
        super().__init__(charm, self.name)

        self.charm = charm
        self.state = context
        self.s3_provider_data = S3ProviderData(self.charm.model, S3_RELATION_NAME)
        self.s3_provider = S3ProviderEventHandlers(self.charm, self.s3_provider_data)
        self.framework.observe(
            self.s3_provider.on.storage_connection_info_requested,
            self._on_s3_connection_info_requested,
        )
        self.framework.observe(
            self.charm.on[S3_RELATION_NAME].relation_broken, self._on_s3_relation_broken
        )

    def _on_s3_connection_info_requested(self, event: StorageConnectionInfoRequestedEvent) -> None:
        """Handle the `storage-connection-info-requested` event."""
        self.logger.info("On storage-connection-info-requested")
        if not self.charm.unit.is_leader():
            return

        self.reconcile_buckets()

    def _on_s3_relation_broken(self, event: StorageConnectionInfoGoneEvent) -> None:
        """Handle the `relation-broken` event for S3 relation."""
        self.logger.info("On s3 relation broken")
        if not self.charm.unit.is_leader():
            return

        self.reconcile_buckets()

    def get_requested_relation_buckets(self) -> dict[str, dict[str, str]]:
        """Return requested buckets and paths from each relation_id of the client relation."""
        return {
            rel_id: {"bucket": data.get("bucket", ""), "path": data.get("path", "")}
            for rel_id, data in self.s3_provider_data.fetch_relation_data(
                fields=["bucket", "path"]
            ).items()
        }

    def ensure_bucket(self, s3_manager: S3Manager, bucket_name: str) -> bool:
        """Try to fetch the bucket, and if not found, try to create and and verify it got created."""
        if s3_manager.get_bucket(bucket_name=bucket_name):
            return True

        try:
            self._add_status(
                status=BucketStatuses.creating_bucket(bucket_name=bucket_name),
                is_running_status=True,
            )
            s3_manager.create_bucket(bucket_name=bucket_name, wait_until_exists=True)
            return True
        except S3BucketError:
            return False

    def _add_status(self, status: StatusObject, is_running_status: bool = False) -> None:
        for scope in ("app", "unit"):
            if is_running_status:
                self.charm.status.set_running_status(
                    status=status,
                    scope=scope,
                    component_name=self.name,
                )
            else:
                self.state.statuses.add(status=status, scope=scope, component=self.name)

    def _clear_status(self) -> None:
        for scope in ("app", "unit"):
            self.state.statuses.clear(scope=scope, component=self.name)

    def reconcile_buckets(self) -> None:
        """Reconcile creation of buckets and providing them to clients."""
        if not self.charm.unit.is_leader() or not self.state.s3:
            return

        self._clear_status()
        s3_manager = S3Manager(self.state.s3)

        config_bucket_value = self.state.s3.get("bucket", "")
        config_path_value = self.state.s3.get("path", "")
        missing_buckets = []
        invalid_buckets = []
        config_bucket_available = False

        if config_bucket_value:
            config_bucket_available = self.ensure_bucket(
                s3_manager=s3_manager, bucket_name=config_bucket_value
            )
            if not config_bucket_available:
                missing_buckets.append(config_bucket_value)

        relation_bucket_requests = self.get_requested_relation_buckets()
        for relation_id, request in relation_bucket_requests.items():
            relation_bucket_value = request.get("bucket", "")
            relation_path_value = request.get("path", "")
            relation_data = self.state.s3

            if config_bucket_value and not config_bucket_available:
                continue

            if not config_bucket_value and relation_bucket_value:
                relation_bucket_valid = re.match(BUCKET_REGEX, relation_bucket_value)
                if not relation_bucket_valid and relation_bucket_value not in invalid_buckets:
                    invalid_buckets.append(relation_bucket_value)
                    continue
                relation_bucket_available = self.ensure_bucket(
                    s3_manager=s3_manager, bucket_name=relation_bucket_value
                )
                if not relation_bucket_available and relation_bucket_value not in missing_buckets:
                    missing_buckets.append(relation_bucket_value)
                    continue
                relation_data = relation_data | {"bucket": relation_bucket_value}

            if not config_path_value and relation_path_value:
                relation_data = relation_data | {"path": relation_path_value}

            self.s3_provider_data.update_relation_data(relation_id, relation_data)

        self._handle_status(missing_buckets, invalid_buckets)

    def _handle_status(self, missing_buckets: list[str], invalid_buckets: list[str]):
        """Internal method that handles the status for missing or invalid buckets."""
        if missing_buckets:
            self._add_status(BucketStatuses.bucket_unavailable(bucket_names=missing_buckets))
        if invalid_buckets:
            self._add_status(BucketStatuses.bucket_name_invalid(bucket_names=invalid_buckets))

        if not missing_buckets and not invalid_buckets:
            self._add_status(CharmStatuses.ACTIVE_IDLE.value)

    def get_statuses(self, scope: Scope, recompute: bool = False) -> list[StatusObject]:
        """Return the list of statuses for this component."""
        if not recompute:
            return self.state.statuses.get(scope=scope, component=self.name)

        status_list: list[StatusObject] = []
        if not self.state.s3:
            return status_list

        requested_buckets = [
            request.get("bucket", "")
            for request in self.get_requested_relation_buckets().values()
            if request.get("bucket", "")
        ]

        config_bucket = self.state.s3.get("bucket")
        if config_bucket and config_bucket not in requested_buckets:
            requested_buckets.insert(0, config_bucket)

        s3_manager = S3Manager(self.state.s3)
        missing_buckets = [
            bucket_name
            for bucket_name in requested_buckets
            if not s3_manager.get_bucket(bucket_name=bucket_name)
        ]
        if missing_buckets:
            status_list.append(BucketStatuses.bucket_unavailable(bucket_names=missing_buckets))
        else:
            status_list.append(CharmStatuses.ACTIVE_IDLE.value)

        return status_list
