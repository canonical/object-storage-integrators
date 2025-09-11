#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Google Cloud Storage Provider related event handlers."""
from typing import Dict, Optional

import ops
from charms.data_platform_libs.v0.common_object_storage import (
    StorageProvides,
    StorageContract,
    StorageConnectionInfoRequestedEvent,
)
from ops import CharmBase
from ops.charm import ConfigChangedEvent, StartEvent

from constants import (
    GCS_RELATION_NAME,
    KEYS_LIST,
    GCS_MANDATORY_OPTIONS,
    OPTIONAL_OVERRIDE,
    CREDENTIAL_FIELD,
)
from core.context import Context
from events.base import BaseEventHandler, compute_status
from utils.logging import WithLogging
from utils.secrets import normalize


GCS_CONTRACT = StorageContract(
    required_info=GCS_MANDATORY_OPTIONS,
    secret_fields=KEYS_LIST,
)

class GCStorageProviderEvents(BaseEventHandler, WithLogging):
    """Class implementing GCS Integration event hooks."""

    def __init__(self, charm: CharmBase):
        super().__init__(charm, "general")
        self.charm = charm
        self.gcs_provides = StorageProvides(self.charm, GCS_RELATION_NAME, GCS_CONTRACT)

        self.framework.observe(
            self.gcs_provides.on.storage_connection_info_requested,
            self._on_storage_connection_info_requested,
        )
        self.framework.observe(self.charm.on.start, self._on_start)
        self.framework.observe(self.charm.on.update_status, self._on_update_status)
        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.secret_changed, self._on_secret_changed)

    def _ctx(self) -> Optional[Context]:
        return getattr(self.charm, "context", None)

    @compute_status
    def _on_start(self, _: StartEvent) -> None:
        """Handle the charm startup event."""
        pass

    @compute_status
    def _on_update_status(self, event: ops.UpdateStatusEvent):
        """Handle the update status event."""
        pass

    def _build_payload(self) -> Dict[str, str]:
        """
        Build the provider payload (non-secret + secret fields).
        Expectation: context.gc_storage returns an object with .to_dict()
        mapping keys precisely to the contract (bucket, sa-key, storage-class, path).
        """
        context = self._ctx()
        if not context or not context.gc_storage:
            return {}
        return {k: v for k, v in context.gc_storage.to_dict().items() if v is not None}

    def _merge_requirer_override(self, relation, payload: Dict[str, str]) -> Dict[str, str]:
        """Optionally merge a single override key from the requirer (bucket)."""
        if not payload or not relation.app:
            return payload
        if not OPTIONAL_OVERRIDE:
            return payload

        req_data = dict(relation.data.get(relation.app, {}))
        override_value = req_data.get(OPTIONAL_OVERRIDE)
        if override_value:
            payload[OPTIONAL_OVERRIDE] = override_value
        return payload

    def _publish_all(self) -> None:
        """Publish to all current relations."""
        for relation in self.gcs_provides.relations:
            payload = self._build_payload_for_relation(relation)
            payload = self._merge_requirer_override(relation, payload)
            if payload:
                self.gcs_provides.publish_payload(relation, payload)

    @compute_status
    def _on_config_changed(self, event: ConfigChangedEvent) -> None:  # noqa: C901
        """Recompute and republish to all relations."""
        if not self.charm.unit.is_leader():
            return

        self.logger.debug(f"Config changed. Current configuration: {self.charm.config}")
        self._publish_all()

    @compute_status
    def _on_secret_changed(self, event: ops.SecretChangedEvent):
        """Rebuild and republish the changed secret."""

        if not self.charm.unit.is_leader():
            return

        configured = self.charm.config.get(CREDENTIAL_FIELD)
        if not configured:
            return

        cfg_norm = normalize(configured)
        if event.secret.id == cfg_norm:
            self._publish_all()

    def _on_storage_connection_info_requested(
        self, event: StorageConnectionInfoRequestedEvent
    ):
        """Publish data to the relation as the requirer signaled its readiness."""
        if not self.charm.unit.is_leader():
            return

        payload = self._build_payload()
        payload = self._merge_requirer_override(event.relation, payload)
        if not payload:
            self.logger.warning("No GCS payload available yet, not publishing.")
            return
        if event.relation.name == GCS_RELATION_NAME:
            self.gcs_provides.publish_payload(event.relation, payload)
