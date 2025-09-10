#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Google Cloud Storage Provider related event handlers."""
from typing import Dict

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
    requirer_override_field=OPTIONAL_OVERRIDE
)

class GCStorageProviderEvents(BaseEventHandler, WithLogging):
    """Class implementing GCS Integration event hooks."""

    def __init__(self, charm: CharmBase, context: Context):
        super().__init__(charm, "general")

        self.charm = charm
        self.context = context

        self.gcs_provides = StorageProvides(self.charm, GCS_RELATION_NAME, GCS_CONTRACT)

        self.framework.observe(
            self.gcs_provides.on.storage_connection_info_requested,
            self._on_storage_connection_info_requested,
        )
        self.framework.observe(self.charm.on.start, self._on_start)
        self.framework.observe(self.charm.on.update_status, self._on_update_status)
        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.secret_changed, self._on_secret_changed)

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
        mapping keys precisely to the contract (bucket, service-account-json-key, storage-class, path).
        """
        if not self.context.gc_storage:
            return {}
        return {k: v for k, v in self.context.gc_storage.to_dict().items() if v is not None}

    def _publish_all(self) -> None:
        """Publish to all current relations."""
        payload = self._build_payload()
        if not payload:
            return

        for relation in self.gcs_provides.relations:
            self.gcs_provides.publish_payload(relation, payload)

    @compute_status
    def _on_config_changed(self, event: ConfigChangedEvent) -> None:  # noqa: C901
        """Config changed → recompute and republish to all relations."""
        if not self.charm.unit.is_leader():
            return

        self.logger.debug(f"Config changed... Current configuration: {self.charm.config}")
        self._publish_all()

    @compute_status
    def _on_secret_changed(self, event: ops.SecretChangedEvent):
        """Rebuild and republish the changed secret."""

        if not self.charm.unit.is_leader():
            return

        # it may be "secret:<id>", id, or label
        configured = self.charm.config.get(CREDENTIAL_FIELD)
        if not configured:
            return

        cfg_norm = normalize(configured)
        if event.secret.id == cfg_norm or (event.secret.label and event.secret.label == configured):
            self._publish_all()

    def _on_storage_connection_info_requested(
        self, event: StorageConnectionInfoRequestedEvent
    ):
        """Requirer signaled readiness, publish data to just this relation."""
        if not self.charm.unit.is_leader():
            return

        payload = self._build_payload()
        if not payload:
            self.logger.warning("No GCS payload available yet; not publishing.")
            return

        # Optional override from requirer (bucket)
        # In the future automatic bucket creation may use overriden key by requirer
        remote_app = event.app
        overriden_key_by_requirer = GCS_CONTRACT.requirer_override_field
        req = dict(event.relation.data[remote_app]) if remote_app else {}
        if req.get(overriden_key_by_requirer):
            payload[overriden_key_by_requirer] = req[overriden_key_by_requirer]

        if event.relation.name == GCS_RELATION_NAME:
            self.gcs_provides.publish_payload(event.relation, payload)
