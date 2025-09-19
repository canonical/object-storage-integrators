
#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

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

    def __init__(self, model, relation_name: str,  contract: StorageContract):
        super().__init__(
            model,
            relation_name,
        )
        self.contract = contract
        self._secret_fields = list(contract.secret_fields or [])
        type(self).SECRET_FIELDS = list(self._secret_fields)


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

        existing_data = self.relation_data.fetch_relation_data([relation_id])[relation_id]
        existing_data.update({k: v for k, v in overrides.items() if v is not None})
        self.relation_data.update_relation_data(relation_id, existing_data)

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
        # TODO: add missing fields

        if self._all_required_present(event.relation):
            getattr(self.on, "storage_connection_info_changed").emit(
                event.relation, app=event.app, unit=event.unit
            )
        else:
            logger.warning(
                f"Some mandatory fields does not exist: do not emit credential change event!"
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
        # TODO: add missing fields
        if self._all_required_present(relation):
            getattr(self.on, "storage_connection_info_changed").emit(
                relation, app=relation.app, unit=remote_unit
            )
        else:
            logger.warning(
                f"Some mandatory fields are missing: do not emit credential change event!"
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


