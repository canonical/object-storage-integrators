#!/usr/bin/env python3
# Copyright 2025
# SPDX-License-Identifier: Apache-2.0
import logging
from typing import Dict, Optional

from charms.data_platform_libs.v0.object_storage import (
    GcsStorageRequires,
)
from ops.charm import CharmBase
from ops.framework import Object
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus

logger = logging.getLogger(__name__)
REL_NAME = "gcs-credentials"
BACKEND_NAME = "gcs"


class GcsRequirerEvents(Object):
    """Requirer-side helper which listens to lib events and sets status directly."""

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = REL_NAME,
    ):
        super().__init__(charm, "gcs-requirer")
        self.charm = charm
        self.relation_name = relation_name
        self.storage = GcsStorageRequires(
            charm, relation_name, overrides=self.overrides_from_config()
        )
        self.framework.observe(
            self.storage.on.storage_connection_info_changed, self._on_conn_info_changed
        )
        self.framework.observe(
            self.storage.on.storage_connection_info_gone, self._on_conn_info_gone
        )

        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)

        self.framework.observe(self.charm.on.start, lambda e: self.refresh_status())
        self.framework.observe(self.charm.on.update_status, lambda e: self.refresh_status())

    def _on_config_changed(self, _):
        self.storage.set_overrides(self.overrides_from_config(), push=True)
        self.refresh_status()

    def _on_conn_info_changed(self, event):
        payload = self._load_payload(event.relation)
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

        return {"bucket": bucket} if bucket != "" else {"bucket": ""}

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
