#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Google Cloud Storage Provider related event handlers."""
import logging
from typing import Dict

import ops
from charms.data_platform_libs.v0.object_storage import (
    StorageProviderEventHandlers,
    StorageProviderData,
    GcsContract,
    StorageConnectionInfoRequestedEvent,
)
from ops import CharmBase, ActiveStatus, MaintenanceStatus
from ops.charm import ConfigChangedEvent, StartEvent

from constants import (
    GCS_RELATION_NAME,
    CREDENTIAL_FIELD,
)
from core.context import Context
from events.base import BaseEventHandler, compute_status
from utils.logging import WithLogging
from utils.secrets import decode_secret_key_with_retry
from managers.gc_storage import GCStorageManager

logger = logging.getLogger(__name__)

class GCStorageProviderEvents(BaseEventHandler, WithLogging):
    """Class implementing GCS Integration event hooks."""

    def __init__(self, charm: CharmBase):
        super().__init__(charm, "gc-storage-provider")
        self.charm = charm

        self.gcs_provider_data = StorageProviderData(self.charm.model, GCS_RELATION_NAME)
        self.gc_storage_manager = GCStorageManager(self.gcs_provider_data)

        self.gcs_provider = StorageProviderEventHandlers(
            self.charm, self.gcs_provider_data
        )

        self.framework.observe(
            self.gcs_provider.on.storage_connection_info_requested,
            self._on_storage_connection_info_requested,
        )
        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self.charm.on.start, self._on_start)

    def _build_payload(self) -> Dict[str, str]:
        """
        Build the provider payload (non-secret + secret fields).
        Expectation: context.gc_storage returns an object with .to_dict()
        mapping keys precisely to the GcsContract (bucket, secret-key, storage-class, path).
        """
        context = Context(self.charm.model)
        gc = context.gc_storage
        logger.info("gc_store: %s", gc)

        if gc:
            raw = gc.to_dict()
        else:
            cfg = self.charm.model.config
            secret_ref = cfg.get("credentials")
            plaintext = decode_secret_key_with_retry(self.model, secret_ref)
            raw = {
                "bucket": cfg.get("bucket"),
                "storage-class": cfg.get("storage-class"),
                "path": cfg.get("path") or "",
                "secret-key":plaintext,
            }

        compact = {k: v for k, v in (raw or {}).items() if v not in (None, "")}
        return compact

    def _merge_requirer_override(self, relation, payload: Dict[str, str]) -> Dict[str, str]:
        """Optionally, override keys from the requirer (bucket, path, storage-class)."""
        if not payload or not relation or not relation.app:
            return payload
        allowed = ["bucket", "storage-class", "path"]
        remote =(
            self.gcs_provider_data.fetch_relation_data()[relation.id]
            if relation
            else None
        )
        merged = dict(payload)
        for key in allowed:
            if key in remote and remote[key]:
                merged[key] = remote[key]
                logger.info("Applied requirer override %r=%r", key, remote[key])
        return merged

    def _publish_to_relation(self, relation) -> None:
        base = self._build_payload()
        logger.info("base_payload %s", base)

        payload = self._merge_requirer_override(relation, base)
        self.gcs_provider_data.publish_payload(relation, payload)
        self.charm.unit.status = ActiveStatus("published GCS credentials")
        logger.info("Published GCS payload to relation %s", relation.id)

    def _publish_to_all_relations(self) -> None:
        for rel in self.charm.model.relations.get(GCS_RELATION_NAME, []):
            self._publish_to_relation(rel)

    def _on_storage_connection_info_requested(self, event: StorageConnectionInfoRequestedEvent):
        self.logger.info("On storage-connection-info-requested")
        if not self.charm.unit.is_leader():
            return
        self._publish_to_relation(event.relation)

    def _on_config_changed(self, _: ConfigChangedEvent):
        if not self.charm.unit.is_leader():
            return
        self._publish_to_all_relations()

    def _on_leader_elected(self, _):
        if not self.charm.unit.is_leader():
            return
        self._publish_to_all_relations()

    def _on_start(self, _: StartEvent):
        if not self.charm.unit.is_leader():
            return
        self._publish_to_all_relations()