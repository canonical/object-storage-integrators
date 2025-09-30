#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
"""A lightweight library for communicating between Cloud storages provider and requirer charms.

This library implements a common object-storage contract and the relation/event plumbing to publish
and consume storage connection info.


### Provider charm

A provider publishes the payload when the requirer asks for it. It is needed to wire the handlers and
emit on demand.

```
Example:
```python

from charms.data_platform_libs.v0.object_storage import (
    GcsStorageProviderData,
    StorageConnectionInfoRequestedEvent,
    StorageProviderEventHandlers,
)

class GCStorageProviderEvents(BaseEventHandler, ManagerStatusProtocol, WithLogging):

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

    def publish_to_relation(self, relation: Relation) -> None:
        if not self.charm.unit.is_leader() or relation is None:
            return
        base = self._build_payload()
        self.logger.info("base_payload %s", base)

        payload = self._merge_requirer_override(relation, base)
        self.gcs_provider_data.update_relation_data(relation.id, payload)
        self.logger.info("Published GCS payload to relation %s", relation.id)
        self._add_status(CharmStatuses.ACTIVE_IDLE.value)

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


if __name__ == "__main__":
    main(ExampleProviderCharm)
```

### Requirer charm

A requirer consumes the published fields and (optionally) provides overrides.

Provider charm.

An example of requirer charm is the following:

Example:
```python

from charms.data_platform_libs.v0.object_storage import (
    StorageRequires,
)

REL_NAME = "gcs-credentials"
BACKEND_NAME = "gcs"

class ExampleRequirerCharm(CharmBase):

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = REL_NAME,
    ):
        super().__init__(charm, "gcs-requirer")
        self.charm = charm
        self.relation_name = relation_name
        self.storage = StorageRequires(charm, relation_name, BACKEND_NAME, overrides={})
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


 if __name__ == "__main__":
    main(ExampleRequirerCharm)
```
"""

import logging
from dataclasses import dataclass
from typing import ClassVar, Dict, List, Literal, Optional

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
class _Contract:
    """Define Contract describing what the requirer and provider exchange in the Storage relation.

    Args:
        required_info: Keys that must be present in the provider's application
            databag before the relation is considered "ready". This may include
            non-secret fields such as bucket-name, container and secret fields
            such as secret-key, access-key.
        optional_info: Keys that must be optionally present in the provider's application
            databag. These are the non-secret fields such as storage-account, path, storage-class, etc.
        secret_fields: Keys in the provider's databag that represent Juju secret
            references (URIs, labels, or IDs). The library will automatically
            register and track these secrets for the requirer.
    """

    required_info: List[str]
    optional_info: List[str]
    secret_fields: List[str]


_CONTRACTS: Dict[Literal["gcs", "s3", "azure"], _Contract] = {
    "gcs": _Contract(
        required_info=["bucket", "secret-key"],
        optional_info=["storage-class", "path"],
        secret_fields=["secret-key"],
    ),
    "s3": _Contract(
        required_info=["bucket", "access-key", "secret-key"],
        optional_info=[
            "endpoint",
            "region",
            "path",
            "s3-uri-style",
            "storage-class",
            "s3-api-version",
        ],
        secret_fields=["access-key", "secret-key"],
    ),
    "azure": _Contract(
        required_info=["container", "storage-account", "secret-key"],
        optional_info=["path", "connection-protocol", "endpoint", "resource-group"],
        secret_fields=["secret-key"],
    ),
}


class ObjectStorageEvent(RelationEvent):
    """The class representing an object storage event."""

    pass


class StorageConnectionInfoRequestedEvent(ObjectStorageEvent):
    """The class representing an object storage connection info requested event."""

    pass


class StorageConnectionInfoChangedEvent(ObjectStorageEvent):
    """The class representing an object storage connection info changed event."""

    pass


class StorageConnectionInfoGoneEvent(RelationEvent):
    """The class representing an object storage connection info gone event."""

    pass


class StorageProviderEvents(CharmEvents):
    """Define events emitted by the provider side of a storage relation.

    These events are produced by a charm that provides storage connection
    information to requirers (an object-storage integrator). Providers
    should observe these and respond by publishing the current connection
    details per relation.

    Events:
        storage_connection_info_requested (StorageConnectionInfoRequestedEvent):
            Fired on the provider side to request/refresh storage connection info.
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
            Fired on the requirer side when the provider publishes new or updated connection info.
            Handlers should read relation data/secrets and apply changes.

        storage_connection_info_gone (StorageConnectionInfoGoneEvent):
            Fired on the requirer side when previously available connection info has been removed or
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
    labels/IDs. It is typically configured from a Contract
    so different backends (S3, Azure, GCS) can reuse the same flow.
    """

    SECRET_FIELDS: ClassVar[List[str]] = []
    SECRET_LABEL_MAP = {}

    def __init__(
        self,
        model: Model,
        relation_name: str,
        backend: Literal["gcs", "s3", "azure"],
    ) -> None:
        """Create a new requirer data manager for a given relation.

        Initializes the instance with the provided backend using the
        available contract.

        Args:
            model: The Juju model instance from the charm.
            relation_name : Relation endpoint name used by this requirer.
            backend: Backend name used by this requirer.
        """
        contract = _CONTRACTS.get(backend)
        if not contract:
            raise ValueError(f"Unsupported backend {backend!r}")

        # PASS secret-fields PER INSTANCE; do not touch class variables.
        super().__init__(
            model=model,
            relation_name=relation_name,
            additional_secret_fields=list(contract.secret_fields),
        )
        self.contract = contract


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
        charm (CharmBase): The charm being configured.
        relation_data (StorageRequirerData): Helper for relation data and secrets.
        overrides (Dict): The key-value pairs that being overridden in the relation data.
    """

    on = StorageRequirerEvents()  # pyright: ignore[reportAssignmentType]

    def __init__(
        self, charm: CharmBase, relation_data: StorageRequirerData, overrides: Dict[str, str]
    ):
        """Initialize the requirer event handlers.

        Subscribes to relation_joined, relation_changed, relation_broken,
        and secret_changed events to coordinate data and secret flow.

        Args:
            charm (CharmBase): The parent charm instance.
            relation_data (StorageRequirerData): Requirer-side relation data helper.
            overrides (Dict): The key-value pairs that being overridden in the relation data.
        """
        super().__init__(charm, relation_data)

        self.relation_name = relation_data.relation_name
        self.charm = charm
        self.local_app = self.charm.model.app
        self.local_unit = self.charm.unit
        self.contract = relation_data.contract
        self.overrides = overrides

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

    def _all_required_info_present(self, relation: Relation) -> bool:
        info = self.get_storage_connection_info(relation)
        return all(k in info for k in self.contract.required_info)

    def _missing_fields(self, relation: Relation) -> List[str]:
        info = self.get_storage_connection_info(relation)
        missing = []
        for k in self.contract.required_info:
            if k not in info:
                missing.append(k)
        return missing

    def _register_new_secrets(self, event: RelationChangedEvent) -> None:
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
        if self.overrides:
            self.write_overrides(self.overrides, relation_id=event.relation.id)

    def get_storage_connection_info(self, relation: Relation) -> Dict[str, str]:
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

        if self._all_required_info_present(event.relation):
            getattr(self.on, "storage_connection_info_changed").emit(
                event.relation, app=event.app, unit=event.unit
            )
        else:
            missing = self._missing_fields(event.relation)
            logger.warning(
                "Some mandatory fields: %s are not present, do not emit credential change event!",
                ",".join(missing),
            )

    def _on_secret_changed_event(self, event: SecretChangedEvent) -> None:
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

        if self._all_required_info_present(relation):
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

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str,
        backend: Literal["gcs", "s3", "azure"],
        overrides: Dict[str, str] | None = None,
    ) -> None:
        """Initialize the requirer helper.

        Args:
            charm (CharmBase): Parent charm.
            relation_name (str): Relation endpoint name.
            backend: Backend name used by this requirer.
            overrides: Optional overrides.
        """
        StorageRequirerData.__init__(self, charm.model, relation_name, backend)
        StorageRequirerEventHandlers.__init__(self, charm, self, overrides or {})


class StorageProviderData(ProviderData):
    """Responsible for publishing provider-owned connection information to the relation databag."""

    def __init__(self, model: Model, relation_name: str) -> None:
        """Initialize the provider data helper.

        Args:
            model (Model): The Juju model instance.
            relation_name (str): Provider relation endpoint name.
        """
        super().__init__(model, relation_name)


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

    def _on_relation_changed_event(self, event: RelationChangedEvent) -> None:
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
