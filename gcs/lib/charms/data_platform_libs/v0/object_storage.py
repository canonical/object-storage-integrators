#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""
A lightweight library for communicating between GCS (Google Cloud Storage) provider and requirer charms.

This library implements a common object-storage contract and the relation/event plumbing to publish
and consume GCS connection info.



### Provider charm

A provider publishes the payload when the requirer asks for it. It is needed to wire the handlers and
emit on demand. The RESOURCE_FIELD class attribute of GcsStorageProviderData must be provided by requirer, otherwise the provider will not publish any payload.

```
class GcsStorageProviderData(StorageProviderData):

    RESOURCE_FIELD = "requested-secrets"
```

Example:
```python

from charms.data_platform_libs.v0.object_storage import (
    StorageConnectionInfoRequestedEvent,
    GcsStorageProviderData,
    StorageProviderEventHandlers,
)

class ExampleProviderCharm(CharmBase):

    def __init__(self, charm: "GCStorageIntegratorCharm", context: Context):
        self.name = "gc-storage-provider"
        super().__init__(charm, self.name)
        self.charm = charm
        self.state = context

        self.gcs_provider_data = GcsStorageProviderData(self.charm.model, GCS_RELATION_NAME)
        self.gcs_provider = StorageProviderEventHandlers(self.charm, self.gcs_provider_data)

        self.framework.observe(
            self.gcs_provider.on.storage_connection_info_requested,
            self._on_storage_connection_info_requested,
        )
        self.framework.observe(
            self.charm.on[GCS_RELATION_NAME].relation_broken, self._on_gcs_relation_broken
        )

    def _build_payload(self) -> Dict[str, str]:
        cfg = self.charm.config
        if not self.state.gc_storage:
            return {}

        self._clear_status()

        raw_data = self.state.gc_storage.to_dict()

        secret_ref = (cfg.get("credentials") or "").strip()

        raw_data["secret-key"] = normalize(secret_ref)

        return {k: v for k, v in raw_data.items() if v not in (None, "")}

    def _merge_requirer_override(self, relation, payload: Dict[str, str]) -> Dict[str, str]:
        if not payload or not relation or not relation.app:
            return payload
        remote = (
            self.gcs_provider_data.fetch_relation_data([relation.id]).get(relation.id)
            if relation
            else None
        )
        merged = dict(payload)
        for key in ALLOWED_OVERRIDES:
            if key in remote and remote[key]:
                merged[key] = remote[key]
                logger.info("Applied requirer override %r=%r", key, remote[key])
        return merged

    def publish_to_relation(self, relation, event=None) -> None:
        if not self.charm.unit.is_leader() or relation is None:
            return
        base = self._build_payload()
        logger.info("base_payload %s", base)

        payload = self._merge_requirer_override(relation, base)


        self.gcs_provider_data.publish_payload(relation, payload)
        logger.info("Published GCS payload to relation %s", relation.id)
        self._add_status(CharmStatuses.ACTIVE_IDLE.value)

    def publish_to_all_relations(self, event) -> None:
        for rel in self.charm.model.relations.get(GCS_RELATION_NAME, []):
            self.publish_to_relation(rel, event)

    def _on_storage_connection_info_requested(self, event: StorageConnectionInfoRequestedEvent):
        self.logger.info("On storage-connection-info-requested")
        if not self.charm.unit.is_leader():
            return

        self.publish_to_relation(event.relation, event)

    def _on_gcs_relation_broken(self, event: StorageConnectionInfoRequestedEvent):
        self.logger.info("On gcs relation broken")
        if not self.charm.unit.is_leader():
            return
        self.publish_to_relation(event.relation, event)

if __name__ == "__main__":
    main(ExampleProviderCharm)
```

### Requirer charm

A requirer consumes the published fields and (optionally) provides overrides. The requirer must write REQUIRED_FIELDS into its app databag using overrides to influence the provider payload.
Provider charm.

An example of requirer charm is the following:

Example:
```python

from charms.data_platform_libs.v0.object_storage import (
    StorageRequires,
    GcsContract,
)

class ExampleRequirerCharm(CharmBase):


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
        payload = overrides
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

 if __name__ == "__main__":
    main(ExampleRequirerCharm)
```
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, ClassVar
from charms.data_platform_libs.v0.data_interfaces import (
    EventHandlers,
    ProviderData,
    RequirerData,
    RequirerEventHandlers,
)
from ops import Model
from ops.charm import (
    CharmBase,
    CharmEvents,
    RelationBrokenEvent,
    RelationChangedEvent,
    RelationEvent,
    RelationJoinedEvent,
    SecretChangedEvent,
)
from ops.framework import EventSource, ObjectEvents
from ops.model import Relation
from ops.model import Secret, SecretNotFoundError

# The unique Charmhub library identifier, never change it
# # TODO: a new library ID should be generated
LIBID = "fca396f6254246c9bfa5650000000000"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class StorageContract:
    """Contract describing what the requirer and provider exchange in the Storage relation.

    Args:
        required_info: Keys that must be present in the provider's application
            databag before the relation is considered "ready". These are usually
            non-secret fields such as bucket-name, container.
        optional_info: Keys that must be optionally present in the provider's application
            databag. These are the non-secret fields such as storage-account, path, storage-class, etc.
        secret_fields: Keys in the provider's databag that represent Juju secret
            references (URIs, labels, or IDs). The library will automatically
            register and track these secrets for the requirer.
        **overrides: Optional keyword-value overrides that the
            requirer may set to signal preferences (for example, a preferred
            container/bucket name, region, or storage class).
    """

    required_info: List[str]
    optional_info: List[str]
    secret_fields: List[str]
    overrides: Dict[str, str] = field(default_factory=dict)

    def __init__(self, required_info: List[str], optional_info: List[str], secret_fields: List[str], **overrides: str) -> None:
        object.__setattr__(self, "required_info", required_info)
        object.__setattr__(self, "optional_info", optional_info)
        object.__setattr__(self, "secret_fields", secret_fields)
        object.__setattr__(self, "overrides", overrides)


@dataclass(frozen=True)
class GcsContract(StorageContract):
    """GCS-specific contract for the GCS."""
    def __init__(self, **overrides: str):
        required_info = [
            "bucket",
        ]
        optional_info = [
            "storage-class",
            "path",
        ]
        secret_fields = [
            "secret-key"
        ]
        super().__init__(required_info=required_info, optional_info=optional_info, secret_fields=secret_fields, **overrides)


class ObjectStorageEvent(RelationEvent):
    pass

class StorageConnectionInfoRequestedEvent(ObjectStorageEvent):
    pass


class StorageConnectionInfoChangedEvent(ObjectStorageEvent):
    pass


class StorageConnectionInfoGoneEvent(RelationEvent):
    pass


class StorageProviderEvents(CharmEvents):
    """Events for the StorageProvider side implementation."""
    storage_connection_info_requested = EventSource(StorageConnectionInfoRequestedEvent)


class StorageRequirerEvents(CharmEvents):
    """Events for the StorageRequirer side implementation."""

    storage_connection_info_changed = EventSource(StorageConnectionInfoChangedEvent)
    storage_connection_info_gone = EventSource(StorageConnectionInfoGoneEvent)


class StorageRequirerData(RequirerData):
    SECRET_FIELDS: ClassVar[List[str]] = []

    @classmethod
    def configure_from_contract(cls, contract: StorageContract) -> None:
        cls.SECRET_FIELDS = list(contract.secret_fields)

    def __init__(self, model, relation_name: str, contract: StorageContract):
        self.contract = contract
        self._secret_fields = list(type(self).SECRET_FIELDS)
        super().__init__(model, relation_name)


class StorageRequirerEventHandlers(RequirerEventHandlers):
    """Event handlers for requirer side of Storage relation."""

    on = StorageRequirerEvents()  # pyright: ignore[reportAssignmentType]

    def __init__(
        self, charm: CharmBase, relation_data: StorageRequirerData, contract: StorageContract
    ):
        super().__init__(charm, relation_data)

        self.relation_name = relation_data.relation_name
        self.charm = charm
        self.local_app = self.charm.model.app
        self.local_unit = self.charm.unit
        self.contract = contract

        self.framework.observe(
            self.charm.on[self.relation_name].relation_joined, self._on_relation_joined_event
        )
        self.framework.observe(
            self.charm.on[self.relation_name].relation_changed, self._on_relation_changed_event
        )
        self.framework.observe(self.charm.on.secret_changed, self._on_secret_changed_event)

        self.framework.observe(
            self.charm.on[self.relation_name].relation_broken,
            self._on_relation_broken_event,
        )

    def _all_required_present(self, relation) -> bool:
        info = self.get_storage_connection_info(relation)
        return all(k in info for k in (self.contract.required_info + self.contract.secret_fields))

    def _missing_fields(self, relation) -> List[str]:
        info = self.get_storage_connection_info(relation)
        missing = []
        for k in (self.contract.required_info + self.contract.secret_fields):
            if k not in info:
                missing.append(k)
        return missing

    def _register_new_secrets(self, event: RelationChangedEvent):
        diff = self._diff(event)
        added_keys = set(diff.added) if isinstance(diff.added, (set, list, tuple)) else set(
            getattr(diff.added, "keys", lambda: [])())
        changed_keys = set(diff.changed.keys()) if hasattr(diff, "changed") and isinstance(diff.changed,
                                                                                           dict) else set()
        candidate_keys = added_keys | changed_keys
        if not candidate_keys:
            return

        # Get keys which are declared as secret in the contract
        secret_keys = [k for k in candidate_keys if self.relation_data._is_secret_field(k)]
        if not secret_keys:
            return

        self.relation_data._register_secrets_to_relation(event.relation, secret_keys)

    def write_overrides(
        self,
        overrides: Dict[str, str],
        relation_id: Optional[int] = None,
    ) -> None:
        """Write/merge override keys into the requirer app-databag."""
        if not overrides:
            return
        if not self.charm.unit.is_leader():
            return

        payload = {k: v for k, v in overrides.items() if v is not None}
        self.relation_data.update_relation_data(relation_id, payload)

    def _on_relation_joined_event(self, event: RelationJoinedEvent) -> None:
        """Requirer may override some fields using the override keys (optional in the requirer charm)."""
        logger.info(f"Storage relation ({event.relation.name}) joined...")
        if self.contract.overrides:
            self.write_overrides(self.contract.overrides, relation_id=event.relation.id)

    def get_storage_connection_info(self, relation) -> Dict[str, str]:
        """Return the storage connection info as a dictionary."""
        if relation and relation.app:
            info = self.relation_data.fetch_relation_data([relation.id])[relation.id]
            return info
        return {}

    def _on_relation_changed_event(self, event: RelationChangedEvent) -> None:
        """This method validates the required fields present in the relation data."""
        logger.info("Storage relation (%s) changed", event.relation.name)
        self._register_new_secrets(event)

        if self._all_required_present(event.relation):
            getattr(self.on, "storage_connection_info_changed").emit(
                event.relation, app=event.app, unit=event.unit
            )
        else:
            missing = self._missing_fields(event.relation)
            logger.warning(
                "Some mandatory fields: %s are not present, do not emit credential change event!", ",".join(missing)
            )

    def _on_secret_changed_event(self, event: SecretChangedEvent):
        """Event handler for handling a new value of a secret."""
        if not event.secret.label:
            return
        relation = self.relation_data._relation_from_secret_label(event.secret.label)
        if not relation:
            logger.info(
                "Received secret-changed for label %s, but no matching relation was found; ignoring.",
                event.secret.label,
            )
            return
        if relation.app == self.charm.app:
            logging.info("Secret changed event ignored for Secret Owner")

        remote_unit = None
        for unit in relation.units:
            if unit.app != self.charm.app:
                remote_unit = unit

        if self._all_required_present(relation):
            getattr(self.on, "storage_connection_info_changed").emit(
                relation, app=relation.app, unit=remote_unit
            )
        else:
            missing = self._missing_fields(relation)
            logger.warning(
                "Some mandatory fields: %s are not present, do not emit credential change event!", ",".join(missing)
            )

    def _on_relation_broken_event(self, event: RelationBrokenEvent) -> None:
        """Event handler for handling relation_broken event."""
        logger.info("Storage relation broken...")
        getattr(self.on, "storage_connection_info_gone").emit(event.relation, app=event.app, unit=event.unit)

    @property
    def relations(self) -> List[Relation]:
        """The list of Relation instances associated with this relation_name."""
        return list(self.charm.model.relations[self.relation_name])


class StorageRequires(StorageRequirerData, StorageRequirerEventHandlers):
    """The requirer side of Storage relation."""
    def __init__(self, charm: CharmBase, relation_name: str, contract: StorageContract):
        StorageRequirerData.configure_from_contract(contract)
        StorageRequirerData.__init__(self, charm.model, relation_name, contract)
        StorageRequirerEventHandlers.__init__(self, charm, self, contract)


class StorageProviderData(ProviderData):
    """The Data abstraction of the provider side of storage relation."""

    def __init__(self, model: Model, relation_name: str) -> None:
        super().__init__(model, relation_name)

    def publish_payload(self, relation: Relation, payload: Dict[str, str]) -> None:
        self.update_relation_data(relation.id, payload)

class StorageProviderEventHandlers(EventHandlers):
    """The event handlers related to the provider side of Storage relation."""
    on = StorageProviderEvents()

    def __init__(
        self,
        charm: CharmBase,
        relation_data: StorageProviderData,
        unique_key: str = "",
    ):
        super().__init__(charm, relation_data, unique_key)
        self.relation_data = relation_data

    def _on_relation_changed_event(self, event: RelationChangedEvent):
        if not self.charm.unit.is_leader():
            return

        self.on.storage_connection_info_requested.emit(event.relation, app=event.app, unit=event.unit)

class StorageProvides(StorageProviderData, StorageProviderEventHandlers):
    """The provider side of the Storage relation."""
    def __init__(self, charm: CharmBase, relation_name: str) -> None:
        StorageProviderData.__init__(self, charm.model, relation_name)
        StorageProviderEventHandlers.__init__(self, charm, self)


class GcsStorageProviderData(StorageProviderData):
    """The resource field should be provided by requirer, otherwise provider will not publish any payload."""

    RESOURCE_FIELD = "requested-secrets"