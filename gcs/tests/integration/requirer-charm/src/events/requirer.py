#!/usr/bin/env python3
# Copyright 2025
# SPDX-License-Identifier: Apache-2.0
import json
import logging
from typing import Dict, Optional, Mapping, Any

import ops
from ops.charm import CharmBase
from ops.framework import Object
from ops.model import ActiveStatus, WaitingStatus, BlockedStatus, RelationDataTypeError
from charms.data_platform_libs.v0.object_storage import (
    StorageRequires,
    GcsContract,
)

logger = logging.getLogger(__name__)
REL_NAME = "gcs-credentials"


class GcsRequirer(Object):
    """Requirer-side helper which listens to lib events and sets status directly."""

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = REL_NAME,
    ):
        super().__init__(charm, "gcs-requirer")
        self.charm = charm
        self.relation_name = relation_name
        ov = self.overrides_from_config()
        self.contract = GcsContract(**ov)
        self.storage = StorageRequires(charm, relation_name, self.contract)
        self.framework.observe(self.storage.on.storage_connection_info_changed, self._on_conn_info_changed)
        self.framework.observe(self.storage.on.storage_connection_info_gone, self._on_conn_info_gone)
        self.framework.observe(self.storage.on[self.relation_name].relation_joined, self._on_relation_joined)



    def _on_relation_joined(self, event):
        ov = self.overrides_from_config()
        self.apply_overrides(ov, relation_id=event.relation.id)

    def _on_conn_info_changed(self, event):
        payload = self._load_payload(event.relation)
        storage_class = payload.get("storage-class", "") or ""
        path = payload.get("path", "") or ""
        bucket = payload.get("bucket")
        secret_content = payload.get("secret-key")

        missing = [k for k, v in (("bucket", bucket), ("secret-key", secret_content)) if not v]
        if missing:
            self.charm.unit.status = BlockedStatus("missing data: " + ", ".join(missing))
            return

        self.charm.unit.status = ActiveStatus(f"gcs ok: bucket={bucket}")

    def _on_conn_info_gone(self, event):
        """If any relation still works, stay Active, otherwise Waiting."""
        if self._any_relation_ready(exclude_relation_id=event.relation.id):
            self.charm.unit.status = ActiveStatus("gcs credentials available")
        else:
            self.charm.unit.status = WaitingStatus("gcs credentials not available")



    def refresh_status(self):
        rels = self.charm.model.relations.get(self.relation_name, [])
        if not rels:
            self.charm.unit.status = WaitingStatus(f"waiting for {self.relation_name} relation")
            return
        if self._any_relation_ready():
            self.charm.unit.status = ActiveStatus("gcs ok")
        else:
            self.charm.unit.status = WaitingStatus("waiting for GCS credentials")

    def overrides_from_config(self) -> Dict[str, str]:
        c = self.charm.config
        bucket = (c.get("bucket") or "").strip()

        ov: Dict[str, str] = {}
        if bucket:
            ov["bucket"] = bucket

        return ov

    def apply_overrides(self, overrides: Dict[str, str], relation_id: Optional[int] = None) -> None:
        if not overrides or not self.charm.unit.is_leader():
            return
        payload = self._as_relation_strings(overrides)
        try:
            if relation_id is not None:
                self.storage.write_overrides(payload, relation_id=relation_id)
                return

            rels = self.charm.model.relations.get(self.relation_name, [])
            if not rels:
                logger.debug("apply_overrides: no relations for %r", self.relation_name)
                return

            for rel in rels:
                self.storage.write_overrides(payload, relation_id=rel.id)

        except RelationDataTypeError as e:
            types = {k: type(v).__name__ for k, v in overrides.items()}
            logger.exception(
                "apply_overrides: non-string in overrides; raw types=%r; payload=%r", types, payload
            )
            self.charm.unit.status = BlockedStatus(f"invalid override value type: {e}")
            raise

    def handle_secret_changed(self, event: ops.SecretChangedEvent):
        changed_id = event.secret.id or ""
        if not changed_id:
            return
        for rel in self.charm.model.relations.get(self.relation_name, []):
            secret_id = self._field_from_payload(rel, "secret-key")
            if secret_id == changed_id:
                self.refresh_status()
                break



    def _any_relation_ready(self, exclude_relation_id: Optional[int] = None) -> bool:
        for rel in self.charm.model.relations.get(self.relation_name, []):
            if exclude_relation_id is not None and rel.id == exclude_relation_id:
                continue
            if not rel.app:
                continue
            bucket = self._field_from_payload(rel, "bucket")
            secret_content = self._field_from_payload(rel, "secret-key")
            if bucket and secret_content:
                return True
        return False

    def _load_payload(self, relation) -> Dict[str, str]:
        if not relation:
            return {}
        return self.storage.get_storage_connection_info(relation)

    def _field_from_payload(self, relation, key: str) -> Optional[str]:
        val = self._load_payload(relation).get(key)
        return val if isinstance(val, str) and val.strip() else None

    @staticmethod
    def _as_relation_strings(d: Mapping[str, Any]) -> dict[str, str]:
        """Convert any mapping to str->str suitable for relation data."""
        out: dict[str, str] = {}
        for k, v in d.items():
            if v is None:
                continue
            if isinstance(v, str):
                out[k] = v
                continue
            try:
                out[k] = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                out[k] = str(v)
        return out


