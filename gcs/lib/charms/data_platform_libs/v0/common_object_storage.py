#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from typing import Dict, List, Optional, NamedTuple, Iterable
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

# The unique Charmhub library identifier, never change it
# # TODO: a new library ID should be generated
LIBID = "fca396f6254246c9bfa5650000000000"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1


logger = logging.getLogger(__name__)


class StorageContract(NamedTuple):
    """Contract describing what the requirer and provider exchange in the Storage relation.

    Args:
        required_info: Keys that must be present in the provider's application
            databag before the relation is considered "ready". These are usually
            non-secret fields such as storage-account, bucket-name, storage-class etc.
        secret_fields: Keys in the provider's databag that represent Juju secret
            references (URIs, labels, or IDs). The library will automatically
            register and track these secrets for the requirer.
        requirer_overrides: Optional mapping of key/value overrides that the
            requirer may write into its own application databag to signal
            preferences (for example, a preferred container/bucket name,
            region, or storage class). Providers can check these and adapt
            the payload accordingly. Defaults to None
    """

    required_info: List[str]
    secret_fields: List[str]
    requirer_overrides: Optional[Dict[str, str]] = None


class ObjectStorageEvent(RelationEvent):
    pass


class ContainerEvent(ObjectStorageEvent):
    """Base class for object storage events."""

    @property
    def container(self) -> Optional[str]:
        """Returns the container name."""
        if not self.relation.app:
            return None

        return self.relation.data[self.relation.app].get("container", "")


class StorageConnectionInfoRequestedEvent(ContainerEvent):
    pass


class StorageConnectionInfoChangedEvent(ContainerEvent):
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

    def __init__(self, model, relation_name: str,  contract: StorageContract):
        super().__init__(
            model,
            relation_name,
        )
        self.contract = contract
        self._secret_fields = list(contract.secret_fields or [])

    @property
    def secret_fields(self) -> List[str]:
        """Always return a list (empty on Juju 2)"""
        return list(self._secret_fields) if self.secrets_enabled else []


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

    def _all_required_present(self, relation: Relation) -> bool:
        info = self.relation_data.fetch_relation_data([relation.id]).get(relation.id, {})
        return all(k in info for k in self.contract.required_info)

    def _register_new_secrets(self, event: RelationChangedEvent):
        diff = self._diff(event)
        if any(new_val for new_val in diff.added if self.relation_data._is_secret_field(new_val)):
            self.relation_data._register_secrets_to_relation(event.relation, diff.added)

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

        target_relations = (
            [self._relation_by_id(relation_id)] if relation_id is not None else self.relations
        )
        for rel in filter(None, target_relations):
            current = dict(rel.data[self.local_app])
            current.update({k: v for k, v in overrides.items() if v is not None})
            rel.data[self.local_app].update(current)

    def _relation_by_id(self, relation_id: int):
        for r in self.relations:
            if r.id == relation_id:
                return r
        return None

    def _on_relation_joined_event(self, event: RelationJoinedEvent) -> None:
        """Requirer signals readiness by writing the requirer_overrides (if defined)."""
        logger.info(f"Storage relation ({event.relation.name}) joined...")
        if self.contract.requirer_overrides:
            self.write_overrides(self.contract.requirer_overrides, relation_id=event.relation.id)

    def _on_relation_changed_event(self, event: RelationChangedEvent) -> None:
        """Notify the charm about the presence of Storage credentials."""
        logger.info(f"Storage relation ({event.relation.name}) changed...")
        self._register_new_secrets(event)

        info = self.relation_data.fetch_relation_data([event.relation.id]).get(event.relation.id, {})
        required = set(self.contract.required_info)
        present = set(info.keys())
        missing = sorted(required - present)

        if not missing:
            self.on.storage_connection_info_changed.emit(
                event.relation, app=event.app, unit=event.unit
            )
        else:
            logger.warning(
                "Storage relation (%s) missing required fields: %s",
                event.relation.name,
                ", ".join(missing),
            )

    def _on_secret_changed_event(self, event: SecretChangedEvent):
        """Event handler for handling a new value of a secret."""
        if not event.secret.label:
            return
        relation = self.relation_data._relation_from_secret_label(event.secret.label)
        if not relation:
            return
        if self._all_required_present(relation):
            getattr(self.on, "storage_connection_info_changed").emit(
                relation, app=relation.app, unit=None
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
    def __init__(self, model: Model, relation_name: str, contract: StorageContract) -> None:
        super().__init__(model, relation_name)
        self.contract = contract

    def publish_payload(self, relation: Relation, payload: Dict[str, str]) -> None:
        self._update_relation_data(relation, payload)


class StorageProviderEventHandlers(EventHandlers):
    """The event handlers related to provider side of Storage relation."""
    on = StorageProviderEvents()

    def __init__(
        self,
        charm: CharmBase,
        relation_data: StorageProviderData,
        contract: StorageContract,
        unique_key: str = "",
    ):
        super().__init__(charm, relation_data, unique_key)
        self.relation_data = relation_data
        self.contract = contract

    def _on_relation_changed_event(self, event: RelationChangedEvent):
        if not self.charm.unit.is_leader():
            return

        diff = self._diff(event)

        if diff.added or diff.changed:
            credentials = self.relation_data.fetch_relation_data([event.relation.id])[event.relation.id]

            # Emit only if all required fields are present
            if all(opt in credentials for opt in self.contract.required_info):
                self.on.storage_connection_info_requested.emit(
                    event.relation, app=event.app, unit=event.unit
                )
            else:
                logger.debug(
                    f"Missing required options: "
                    f"{[opt for opt in self.contract.required_info if opt not in credentials]}"
                )

class StorageProvides(StorageProviderData, StorageProviderEventHandlers):
    """The provider side of the Storage relation."""
    def __init__(self, charm: CharmBase, relation_name: str, contract: StorageContract) -> None:
        StorageProviderData.__init__(self, charm.model, relation_name, contract)
        StorageProviderEventHandlers.__init__(self, charm, self, contract)

