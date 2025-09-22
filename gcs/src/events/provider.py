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
from ops import CharmBase, ActiveStatus

from constants import (
    GCS_RELATION_NAME,
    CREDENTIAL_FIELD,
    ALLOWED_OVERRIDES
)
from core.charm_config import get_charm_config
from core.context import Context
from events.base import BaseEventHandler, compute_status
from utils.logging import WithLogging
from utils.secrets import decode_secret_key_with_retry
from managers.gc_storage import GCStorageManager

from utils.secrets import normalize

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

    def _build_payload(self) -> Dict[str, str]:
        """
        Build the provider payload (non-secret + secret fields).
        Expectation: context.gc_storage returns an object with .to_dict()
        mapping keys precisely to the GcsContract (bucket, secret-key, storage-class, path).
        """
        context = Context(self.charm)
        cfg = get_charm_config(self.charm)
        if not cfg:
            return {}

        gc = context.gc_storage

        if gc:
            raw = gc.to_dict()
        else:
            raw = {
                "bucket": cfg.bucket,
                "storage-class": cfg.storage_class,
                "path": cfg.path or "",
            }

        secret_ref = (cfg.credentials or "").strip()
        if secret_ref:
            raw["secret-key"] = normalize(secret_ref)
        else:
            raw.pop("secret-key", None)

        return {k: v for k, v in raw.items() if v not in (None, "")}

    def _merge_requirer_override(self, relation, payload: Dict[str, str]) -> Dict[str, str]:
        """Optionally, override keys from the requirer (bucket, path, storage-class)."""
        if not payload or not relation or not relation.app:
            return payload
        remote = self.gcs_provider_data.fetch_relation_data([relation.id]).get(relation.id) if relation else None
        merged = dict(payload)
        for key in ALLOWED_OVERRIDES:
            if key in remote and remote[key]:
                merged[key] = remote[key]
                logger.info("Applied requirer override %r=%r", key, remote[key])
        return merged

    def _publish_to_relation(self, relation) -> None:
        if not self.charm.unit.is_leader() or relation is None:
            return
        base = self._build_payload()
        logger.info("base_payload %s", base)

        payload = self._merge_requirer_override(relation, base)
        self.gcs_provider_data.publish_payload(relation, payload)
        self.charm.unit.status = ActiveStatus("ready")
        logger.info("Published GCS payload to relation %s", relation.id)

    def _publish_to_all_relations(self) -> None:
        for rel in self.charm.model.relations.get(GCS_RELATION_NAME, []):
            self._publish_to_relation(rel)

    def _on_storage_connection_info_requested(self, event: StorageConnectionInfoRequestedEvent):
        self.logger.info("On storage-connection-info-requested")
        if not self.charm.unit.is_leader():
            return
        self._publish_to_relation(event.relation)

