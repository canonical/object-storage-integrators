#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Google Cloud Storage Provider related event handlers."""
import logging
from typing import Dict, Optional

import ops
from charms.data_platform_libs.v0.object_storage import (
    StorageProviderData,
    StorageProviderEventHandlers,
    GcsProviderContract,
    StorageConnectionInfoRequestedEvent,
)
from ops import CharmBase, ActiveStatus, MaintenanceStatus
from ops.charm import ConfigChangedEvent, StartEvent

from constants import (
    GCS_RELATION_NAME,
    OPTIONAL_OVERRIDE,
    CREDENTIAL_FIELD,
)
from core.context import Context
from events.base import BaseEventHandler, compute_status
from utils.logging import WithLogging
from utils.secrets import normalize, decode_secret_key
from managers.gc_storage import GCStorageManager

logger = logging.getLogger(__name__)

class GCStorageProviderEvents(BaseEventHandler, WithLogging):
    """Class implementing GCS Integration event hooks."""

    def __init__(self, charm: CharmBase):
        super().__init__(charm, "gc-storage-provider")
        self.charm = charm
        self.contract = GcsProviderContract(**{OPTIONAL_OVERRIDE: ""})
        self.gcs_provider_data = StorageProviderData(self.charm.model, GCS_RELATION_NAME, self.contract)
        self.gcs_provider = StorageProviderEventHandlers(
            self.charm, self.gcs_provider_data, self.contract
        )

        self.gc_storage_manager = GCStorageManager(self.gcs_provider_data)

        self.framework.observe(
            self.gcs_provider.on.storage_connection_info_requested,
            self._on_storage_connection_info_requested,
        )
        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self.charm.on.start, self._on_start)

    def _ctx(self) -> Optional[Context]:
        return getattr(self.charm, "context", None)

    def _build_payload(self) -> Dict[str, str]:
        """
        Build the provider payload (non-secret + secret fields).
        Expectation: context.gc_storage returns an object with .to_dict()
        mapping keys precisely to the contract (bucket, secret-key, storage-class, path).
        """
        ctx = self._ctx()
        gc = getattr(ctx, "gc_storage", None) if ctx else None
        logger.info("gc_store: %s", gc)

        if gc:
            raw = gc.to_dict()
        else:
            cfg = self.charm.model.config
            cred = cfg.get("credentials")
            sid = normalize(cred)
            plaintext_secret = decode_secret_key(self.charm.model, sid)
            raw = {
                "bucket": cfg.get("bucket"),
                "storage-class": cfg.get("storage-class") or "STANDARD",
                "path": cfg.get("path") or "",
                "secret-key": plaintext_secret,
            }

        compact = {k: v for k, v in (raw or {}).items() if v not in (None, "")}
        return self._filter_to_contract(compact)


    def _filter_to_contract(self, payload: Dict[str, str]) -> Dict[str, str]:
        allowed = set(self.contract.required_info) | set(self.contract.optional_info) | set(self.contract.secret_fields)
        return {k: v for k, v in payload.items() if k in allowed}

    def _merge_requirer_override(self, relation, payload: Dict[str, str]) -> Dict[str, str]:
        """Optionally override keys from the requirer (bucket)."""
        if not payload or not relation or not relation.app:
            return payload
        allowed = set(self.contract.overrides.keys())
        if not allowed:
            return payload

        remote = relation.data.get(relation.app, {})
        merged = dict(payload)
        for key in allowed:
            if key in remote and remote[key]:
                merged[key] = remote[key]
                logger.info("Applied requirer override %r=%r", key, remote[key])
        return merged

    def _validate_payload(self, payload: Dict[str, str]) -> Optional[str]:
        """Return an error message if payload is incomplete, else None."""
        if not payload:
            return "empty payload"
        if "bucket" not in payload or not payload.get("bucket"):
            return "missing required 'bucket'"
        return None

    def _publish_to_relation(self, relation) -> None:
        base = self._build_payload()
        logger.info("base_payload %s", base)

        payload = self._merge_requirer_override(relation, base)
        if err := self._validate_payload(payload):
            logger.warning("No GCS payload available yet (%s), not publishing.", err)
            self.charm.unit.status = MaintenanceStatus(f"waiting for GCS config: {err}")
            return

        # Library creates/updates a provider-owned Secret for CREDENTIAL_FIELD,
        # grants it to the relation, and writes back only the reference + non-secret keys.
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