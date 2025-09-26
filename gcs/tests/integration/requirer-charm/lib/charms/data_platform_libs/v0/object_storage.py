#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""A lightweight library for communicating between GCS (Google Cloud Storage) provider and requirer charms.

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
        self.contract = GcsContract()
        self.storage = StorageRequires(charm, relation_name, self.contract)
        self.framework.observe(
            self.storage.on.storage_connection_info_changed, self._on_conn_info_changed
        )
        self.framework.observe(
            self.storage.on.storage_connection_info_gone, self._on_conn_info_gone
        )
        self.framework.observe(
            self.storage.on[self.relation_name].relation_joined, self._on_relation_joined
        )

        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)

        self._last_sent_overrides: Dict[str, str] = {}

    def _on_config_changed(self, _):
        ov = self.overrides_from_config()
        self.apply_overrides(ov)
        self.refresh_status()

    def _on_relation_joined(self, event):
        ov = self.overrides_from_config()
        self.apply_overrides(ov, relation_id=event.relation.id)

    def _on_conn_info_changed(self, event):
        payload = self._load_payload(event.relation)
        bucket = payload.get("bucket")
        secret_content = payload.get("secret-key")

        missing = [k for k, v in (("bucket", bucket), ("secret-key", secret_content)) if not v]
        if missing:
            self.charm.unit.status = BlockedStatus("missing data: " + ", ".join(missing))

Return:
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

Return:
        if self._any_relation_ready():
            self.charm.unit.status = ActiveStatus("gcs ok")
        else:
            self.charm.unit.status = WaitingStatus("waiting for GCS credentials")

    def overrides_from_config(self) -> Dict[str, str]:
        c = self.charm.config
        bucket = (c.get("bucket") or "").strip()

        return {"bucket": bucket} if bucket != "" else {"bucket": ""}

    def apply_overrides(
        self, overrides: Dict[str, str], relation_id: Optional[int] = None
    ) -> None:
        if not overrides or not self.charm.unit.is_leader():
            return
        if overrides == self._last_sent_overrides:
            return
        if not overrides:
            overrides = {"bucket": ""}

        payload = self._as_relation_strings(overrides)
        try:
            if relation_id is not None:
                self.storage.write_overrides(payload, relation_id=relation_id)

Return:
            rels = self.charm.model.relations.get(self.relation_name, [])
            if not rels:
                logger.debug("apply_overrides: no relations for %r", self.relation_name)

Return:
            for rel in rels:
                self.storage.write_overrides(payload, relation_id=rel.id)

        except RelationDataTypeError as e:
            types = {k: type(v).__name__ for k, v in overrides.items()}
            logger.exception(
                "apply_overrides: non-string in overrides; raw types=%r; payload=%r",
                types,
                payload,
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

 if __name__ == "__main__":
    main(ExampleRequirerCharm)
```
"""

import logging
from dataclasses import dataclass, field
from typing import ClassVar, Dict, List, Optional

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
from ops.framework import EventSource
from ops.model import Relation

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
    """Define Contract describing what the requirer and provider exchange in the Storage relation.

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

    def __init__(
        self,
        required_info: List[str],
        optional_info: List[str],
        secret_fields: List[str],
        **overrides: str,
    ) -> None:
        object.__setattr__(self, "required_info", required_info)
        object.__setattr__(self, "optional_info", optional_info)
        object.__setattr__(self, "secret_fields", secret_fields)
        object.__setattr__(self, "overrides", overrides)


@dataclass(frozen=True)
class GcsContract(StorageContract):
    """Define GCS-specific contract for the GCS.

    This contract defines the shape of storage connection information that a
    requirer/provider pair must exchange when integrating with GCS. It encodes:

    Args:
        required_info (list[str]): Names of required, non-secret fields. Defaults to
            ["bucket"].
        optional_info (list[str]): Names of optional, non-secret fields. Defaults to
            ["storage-class", "path"].
        secret_fields (list[str]): Names of required/optional *secret* fields that must
            be transported and stored securely. Defaults to ["secret-key"].
    """

    def __init__(self, **overrides: str):
        """Initialize a GCS contract, optionally overriding the default schema.

        Args:
            overrides: Requirer can override some common keys which may include:
                - bucket
                - storage-class
                - path
        """
        required_info = [
            "bucket",
        ]
        optional_info = [
            "storage-class",
            "path",
        ]
        secret_fields = ["secret-key"]
        super().__init__(
            required_info=required_info,
            optional_info=optional_info,
            secret_fields=secret_fields,
            **overrides,
        )


class ObjectStorageEvent(RelationEvent):
    pass


class StorageConnectionInfoRequestedEvent(ObjectStorageEvent):
    pass


class StorageConnectionInfoChangedEvent(ObjectStorageEvent):
    pass


class StorageConnectionInfoGoneEvent(RelationEvent):
    pass


class StorageProviderEvents(CharmEvents):
    """Define events emitted by the provider side of a storage relation.

    These events are produced by a charm that provides storage connection
    information to requirers (an object-storage integrator). Providers
    should observe these and respond by publishing the current connection
    details per relation.

    Events:
        storage_connection_info_requested (StorageConnectionInfoRequestedEvent):
            Fired by a requirer to request/refresh storage connection info.
            Providers are expected to (re)publish all relevant relation data
            and secrets for the requesting relation.
    """

    storage_connection_info_requested = EventSource(StorageConnectionInfoRequestedEvent)


class StorageRequirerEvents(CharmEvents):
    """Define events emitted by the requirer side of a storage relation.

    These events are produced by a charm that consumes storage connection
    information. Requirers should react by updating their application config,
    restarting services, etc.

    Events:
        storage_connection_info_changed (StorageConnectionInfoChangedEvent):
            Fired when the provider publishes new or updated connection info.
            Handlers should read relation data/secrets and apply changes.

        storage_connection_info_gone (StorageConnectionInfoGoneEvent):
            Fired when previously available connection info has been removed or
            invalidated (e.g., relation departed, secret revoked). Handlers
            should gracefully degrade and update
            status accordingly.
    """

    storage_connection_info_changed = EventSource(StorageConnectionInfoChangedEvent)
    storage_connection_info_gone = EventSource(StorageConnectionInfoGoneEvent)


class StorageRequirerData(RequirerData):
    """Helper for managing requirer-side storage connection data and secrets.

    This class encapsulates reading/writing relation data, tracking which
    fields are considered secret, and mapping secret fields to Juju secret
    labels/IDs. It is typically configured from a StorageContract
    so different backends (S3, Azure, GCS) can reuse the same flow.

    Class Args:
        SECRET_FIELDS (list[str]): Names of fields that must be stored as
            secrets rather than plain relation data. Populated by
            method configure_from_contract. This field should be filled up
            if any secrets is requested by requirer.
        SECRET_LABEL_MAP (dict[str, str]): Optional mapping from secret field
            name to a stable label/alias to use when creating/looking up Juju
            secrets. This is emptied to remove `provided-secrets` fields from
            requirer relation databag which is unnecessary for object storage integrators.
    """

    SECRET_FIELDS: ClassVar[List[str]] = []
    SECRET_LABEL_MAP = {}

    @classmethod
    def configure_from_contract(cls, contract: StorageContract) -> None:
        """Configure class-level secret handling from a storage contract.

        Copies contract.secret_fields into the class variable
        SECRET_FIELDS, so future instances know which fields must be
        read from or written to Juju secrets.

        Args:
            contract (StorageContract): The contract whose secret_fields
                define which fields are secret on the requirer side.
        """
        cls.SECRET_FIELDS = list(contract.secret_fields)

    def __init__(self, model, relation_name: str, contract: StorageContract):
        """Create a new requirer data manager for a given relation.

        Initializes the instance with the provided contract using the
        current class-level SECRET_FIELDS.

        Args:
            model: The Juju model instance from the charm.
            relation_name (str): Relation endpoint name used by this requirer.
            contract (StorageContract): Contract describing required/optional/
                secret fields for this backend.

        """
        self.contract = contract
        self._secret_fields = list(type(self).SECRET_FIELDS)
        super().__init__(model, relation_name)


class StorageRequirerEventHandlers(RequirerEventHandlers):
    """Bind the requirer lifecycle to the relation's events.

    Validates that all required and secret fields are present, registers newly discovered secret
    keys, and emits higher-level requirer events.

    Emits:
        StorageRequirerEvents.storage_connection_info_changed:
            When all required + secret fields are present or become present.
        StorageRequirerEvents.storage_connection_info_gone:
            When the relation is broken (connection info no longer available).

    Args:
        relation_name (str): Name of the relation endpoint.
        contract (StorageContract): Contract describing required/optional/secret fields.
        relation_data (StorageRequirerData): Helper for relation data and secrets.
    """

    on = StorageRequirerEvents()  # pyright: ignore[reportAssignmentType]

    def __init__(
        self, charm: CharmBase, relation_data: StorageRequirerData, contract: StorageContract
    ):
        """Initialize the requirer event handlers.

        Subscribes to relation_joined, relation_changed, relation_broken,
        and secret_changed events to coordinate data and secret flow.

        Args:
            charm (CharmBase): The parent charm instance.
            relation_data (StorageRequirerData): Requirer-side relation data helper.
            contract (StorageContract): Storage contract for validation and overrides.
        """
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
        for k in self.contract.required_info + self.contract.secret_fields:
            if k not in info:
                missing.append(k)
        return missing

    def _register_new_secrets(self, event: RelationChangedEvent):
        diff = self._diff(event)
        added_keys = (
            set(diff.added)
            if isinstance(diff.added, (set, list, tuple))
            else set(getattr(diff.added, "keys", lambda: [])())
        )
        changed_keys = (
            set(diff.changed.keys())
            if hasattr(diff, "changed") and isinstance(diff.changed, dict)
            else set()
        )
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
        """Write/merge override keys into the requirer app databag.

        Only the leader writes. ``None`` values are ignored.

        Args:
            overrides (dict[str, str]): Keys/values to merge into app databag.
            relation_id (int | None): Specific relation id to target; if omitted,
                applies to all active relations for this endpoint.
        """
        if not overrides:
            return
        if not self.charm.unit.is_leader():
            return

        payload = {k: v for k, v in overrides.items() if v is not None}
        self.relation_data.update_relation_data(relation_id, payload)

    def _on_relation_joined_event(self, event: RelationJoinedEvent) -> None:
        """Handle relation-joined, apply optional requirer-side overrides."""
        logger.info(f"Storage relation ({event.relation.name}) joined...")
        if self.contract.overrides:
            self.write_overrides(self.contract.overrides, relation_id=event.relation.id)

    def get_storage_connection_info(self, relation) -> Dict[str, str]:
        """Assemble the storage connection info for a relation.

        Combines the provider-published relation data and any readable secrets
        to produce a flat dictionary usable by the requirer.

        Args:
            relation: Relation object to read from.

        Returns:
            dict[str, str]: Connection info (may be empty if relation/app does not exist).
        """
        if relation and relation.app:
            info = self.relation_data.fetch_relation_data([relation.id])[relation.id]
            return info
        return {}

    def _on_relation_changed_event(self, event: RelationChangedEvent) -> None:
        """Validate fields on relation-changed and emit requirer events."""
        logger.info("Storage relation (%s) changed", event.relation.name)
        self._register_new_secrets(event)

        if self._all_required_present(event.relation):
            getattr(self.on, "storage_connection_info_changed").emit(
                event.relation, app=event.app, unit=event.unit
            )
        else:
            missing = self._missing_fields(event.relation)
            logger.warning(
                "Some mandatory fields: %s are not present, do not emit credential change event!",
                ",".join(missing),
            )

    def _on_secret_changed_event(self, event: SecretChangedEvent):
        """React to secret changes by re-validating and emitting if complete."""
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
                "Some mandatory fields: %s are not present, do not emit credential change event!",
                ",".join(missing),
            )

    def _on_relation_broken_event(self, event: RelationBrokenEvent) -> None:
        """Emit gone when the relation is broken."""
        logger.info("Storage relation broken...")
        getattr(self.on, "storage_connection_info_gone").emit(
            event.relation, app=event.app, unit=event.unit
        )

    @property
    def relations(self) -> List[Relation]:
        """List active relations for this endpoint."""
        return list(self.charm.model.relations[self.relation_name])


class StorageRequires(StorageRequirerData, StorageRequirerEventHandlers):
    """Combine StorageRequirerData and StorageRequirerEventHandlers into a single helper."""

    def __init__(self, charm: CharmBase, relation_name: str, contract: StorageContract):
        """Initialize the requirer helper.

        Args:
            charm (CharmBase): Parent charm.
            relation_name (str): Relation endpoint name.
            contract (StorageContract): Storage contract for validation and secrets.
        """
        StorageRequirerData.configure_from_contract(contract)
        StorageRequirerData.__init__(self, charm.model, relation_name, contract)
        StorageRequirerEventHandlers.__init__(self, charm, self, contract)


class StorageProviderData(ProviderData):
    """Responsible for publishing provider-owned connection information to the relation databag."""

    def __init__(self, model: Model, relation_name: str) -> None:
        """Initialize the provider data helper.

        Args:
            model (Model): The Juju model instance.
            relation_name (str): Provider relation endpoint name.
        """
        super().__init__(model, relation_name)

    def publish_payload(self, relation: Relation, payload: Dict[str, str]) -> None:
        """Publish connection info into the provider app databag.

        Args:
            relation (Relation): Target relation to update.
            payload (dict[str, str]): Key/value pairs to write.
        """
        self.update_relation_data(relation.id, payload)


class StorageProviderEventHandlers(EventHandlers):
    """Listen for requirer changes and emits a higher-level events."""

    on = StorageProviderEvents()

    def __init__(
        self,
        charm: CharmBase,
        relation_data: StorageProviderData,
        unique_key: str = "",
    ):
        """Initialize provider event handlers.

        Args:
            charm (CharmBase): Parent charm.
            relation_data (StorageProviderData): Provider data helper.
            unique_key (str): Optional key used by the base handler for
                idempotency or uniq semantics.
        """
        super().__init__(charm, relation_data, unique_key)
        self.relation_data = relation_data

    def _on_relation_changed_event(self, event: RelationChangedEvent):
        """Emit a request for connection info when the requirer changes."""
        if not self.charm.unit.is_leader():
            return

        self.on.storage_connection_info_requested.emit(
            event.relation, app=event.app, unit=event.unit
        )


class StorageProvides(StorageProviderData, StorageProviderEventHandlers):
    """Combine StorageProviderData and StorageProviderEventHandlers."""

    def __init__(self, charm: CharmBase, relation_name: str) -> None:
        """Initialize the provider helper.

        Args:
            charm (CharmBase): Parent charm.
            relation_name (str): Provider relation endpoint name.
        """
        StorageProviderData.__init__(self, charm.model, relation_name)
        StorageProviderEventHandlers.__init__(self, charm, self)


class GcsStorageProviderData(StorageProviderData):
    """Define the resource fields which is provided by requirer, otherwise provider will not publish any payload.

    A requirer must first advertises a field via the
    RESOURCE_FIELD key so the provider can publish the appropriate
    payload. This is a  protection mechanism which is implemented in data interfaces not to publish data to a unready requirer.
    If the requirer put the data defined as RESOURCE FIELD, this means requirer is ready to get the data.

    Attributes:
        RESOURCE_FIELD (str): Relation key name the requirer uses to declare a RESOURCE_FIELD
        which is hardcoded to requested-secrets as they always published.

    """

    RESOURCE_FIELD = "requested-secrets"
