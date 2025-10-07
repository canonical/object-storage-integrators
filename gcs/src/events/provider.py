#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Google Cloud Storage Provider related event handlers."""

from typing import TYPE_CHECKING, Dict

from charms.data_platform_libs.v0.object_storage import (
    GcsStorageProviderEventHandlers,
    StorageConnectionInfoRequestedEvent,
)
from data_platform_helpers.advanced_statuses.models import StatusObject
from data_platform_helpers.advanced_statuses.protocol import ManagerStatusProtocol
from data_platform_helpers.advanced_statuses.types import Scope
from ops import Relation

from constants import ALLOWED_OVERRIDES, GCS_RELATION_NAME
from core.context import Context
from core.statuses import CharmStatuses
from events.base import BaseEventHandler
from utils.logging import WithLogging

if TYPE_CHECKING:
    from charm import GCStorageIntegratorCharm


class GCStorageProviderEvents(BaseEventHandler, ManagerStatusProtocol, WithLogging):
    """Class implementing GCS Integration event hooks."""

    def __init__(self, charm: "GCStorageIntegratorCharm", context: Context):
        self.name = "gc-storage-provider"
        super().__init__(charm, self.name)
        self.charm = charm
        self.state = context

        self.gcs_provider = GcsStorageProviderEventHandlers(self.charm)

        self.framework.observe(
            self.gcs_provider.on.storage_connection_info_requested,
            self._on_storage_connection_info_requested,
        )
        self.framework.observe(
            self.charm.on[GCS_RELATION_NAME].relation_broken, self._on_gcs_relation_broken
        )

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

    def _build_payload(self) -> Dict[str, str]:
        """Build the provider payload (non-secret + secret fields)."""
        if not self.state.gc_storage:
            return {}

        raw_data = self.state.gc_storage.to_dict()

        return {k: v for k, v in raw_data.items() if v not in (None, "")}

    def _merge_requirer_override(
        self, relation: Relation, payload: Dict[str, str]
    ) -> Dict[str, str]:
        """Optionally, override keys from the requirer (bucket, path, storage-class)."""
        if not payload or not relation or not relation.app:
            return payload
        remote = (
            self.gcs_provider.relation_data.fetch_relation_data([relation.id]).get(relation.id)
            if relation
            else None
        )
        merged = dict(payload)

        for key in remote:
            if remote[key] and key in ALLOWED_OVERRIDES:
                merged[key] = remote[key]
                self.logger.info("Applied requirer override %r=%r", key, remote[key])
        return merged

    def publish_to_relation(self, relation: Relation) -> None:
        """Publish the payload to the relation."""
        if not self.charm.unit.is_leader() or relation is None:
            return
        self._clear_status()
        base = self._build_payload()
        self.logger.info("base_payload %s", base)

        payload = self._merge_requirer_override(relation, base)
        self.gcs_provider.relation_data.update_relation_data(relation.id, payload)
        self.logger.info("Published GCS payload to relation %s", relation.id)
        self._add_status(CharmStatuses.ACTIVE_IDLE.value)

    def publish_to_all_relations(self) -> None:
        """Publish the payload to all relations."""
        for rel in self.charm.model.relations.get(GCS_RELATION_NAME, []):
            self.publish_to_relation(rel)

    def _on_storage_connection_info_requested(
        self, event: StorageConnectionInfoRequestedEvent
    ) -> None:
        self.logger.info("On storage-connection-info-requested")
        if not self.charm.unit.is_leader():
            return

        self.publish_to_relation(event.relation)

    def _on_gcs_relation_broken(self, event: StorageConnectionInfoRequestedEvent) -> None:
        self.logger.info("On gcs relation broken")
        if not self.charm.unit.is_leader():
            return
        self.publish_to_relation(event.relation)

    def get_statuses(self, scope: Scope, recompute: bool = False) -> list[StatusObject]:
        """Return the list of statuses for this component."""
        if not recompute:
            return self.state.statuses.get(scope=scope, component=self.name)

        status_list: list[StatusObject] = []
        if not self.state.gc_storage:
            return status_list

        status_list.append(CharmStatuses.ACTIVE_IDLE.value)

        return status_list
