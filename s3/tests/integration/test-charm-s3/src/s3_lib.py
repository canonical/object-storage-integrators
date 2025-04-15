# Copyright 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

r"""A library for communicating with the S3 credentials providers and consumers.

This library provides the relevant interface code implementing the communication
specification for fetching, retrieving, triggering, and responding to events related to
the S3 provider charm and its consumers.

"""

import logging

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
LIBID = "fca396f6254246c9bfa565b1f85ab528"

# Increment this major API version when introducing breaking changes
LIBAPI = 1

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 0


logger = logging.getLogger(__name__)


S3_REQUIRED_OPTIONS = ["access-key", "secret-key"]


class BucketEvent(RelationEvent):
    """Base class for bucket events."""

    @property
    def bucket(self) -> str | None:
        """Returns the bucket was requested."""
        if not self.relation.app:
            return None

        return self.relation.data[self.relation.app].get("bucket", "")


class StorageConnectionInfoRequestedEvent(BucketEvent):
    """Event emitted when S3 credentials are requested on this relation."""

    pass


class StorageConnectionInfoChangedEvent(BucketEvent):
    """Event emitted when S3 credentials are changed for this relation."""

    pass


class StorageConnectionInfoGoneEvent(RelationEvent):
    """Event emitted when S3 credentials must be removed from this relation."""

    pass


class S3ProviderEvents(CharmEvents):
    """Events for the S3Provider side implementation."""

    storage_connection_info_requested = EventSource(StorageConnectionInfoRequestedEvent)


class S3RequirerEvents(CharmEvents):
    """Events for the S3Requirer side implementation."""

    s3_connection_info_changed = EventSource(StorageConnectionInfoChangedEvent)
    s3_connection_info_gone = EventSource(StorageConnectionInfoGoneEvent)


class S3RequirerData(RequirerData):
    """Requires-side data."""

    SECRET_FIELDS = ["access-key", "secret-key"]

    def __init__(self, model, relation_name: str, bucket: str | None = None):
        super().__init__(
            model,
            relation_name,
        )
        self.bucket = bucket


class S3RequirerEventHandlers(RequirerEventHandlers):
    """Event handlers for for requirer side of S3 relation."""

    on = S3RequirerEvents()  # type: ignore

    def __init__(self, charm: CharmBase, relation_data: S3RequirerData):
        super().__init__(charm, relation_data)

        self.relation_name = relation_data.relation_name
        self.charm = charm
        self.local_app = self.charm.model.app
        self.local_unit = self.charm.unit

        self.framework.observe(
            self.charm.on[self.relation_name].relation_joined, self._on_relation_joined_event
        )
        self.framework.observe(
            self.charm.on[self.relation_name].relation_changed, self._on_relation_changed_event
        )

        self.framework.observe(
            self.charm.on[self.relation_name].relation_broken,
            self._on_relation_broken_event,
        )

    def _on_relation_joined_event(self, event: RelationJoinedEvent) -> None:
        """Event emitted when the S3 relation is joined."""
        logger.info(f"S3 relation ({event.relation.name}) joined...")
        if self.bucket is None:
            self.bucket = f"relation-{event.relation.id}"
        event_data = {"bucket": self.bucket}
        self.relation_data.update_relation_data(event.relation.id, event_data)

    def get_s3_connection_info(self) -> dict[str, str]:
        """Return the S3 connection info as a dictionary."""
        for relation in self.relations:
            if relation and relation.app:
                info = self.relation_data.fetch_relation_data([relation.id])[relation.id]
                if not set(S3_REQUIRED_OPTIONS) - set(info):
                    continue
                return info
        return {}

    def _on_relation_changed_event(self, event: RelationChangedEvent) -> None:
        """Notify the charm about the presence of S3 credentials."""
        logger.info(f"S3 relation ({event.relation.name}) changed...")

        diff = self._diff(event)
        if any(newval for newval in diff.added if self.relation_data._is_secret_field(newval)):
            self.relation_data._register_secrets_to_relation(event.relation, diff.added)

        # check if the mandatory options are in the relation data
        contains_required_options = True
        credentials = self.get_s3_connection_info()
        missing_options = []
        for configuration_option in S3_REQUIRED_OPTIONS:
            if configuration_option not in credentials:
                contains_required_options = False
                missing_options.append(configuration_option)

        # emit credential change event only if all mandatory fields are present
        if contains_required_options:
            getattr(self.on, "s3_connection_info_changed").emit(
                event.relation, app=event.app, unit=event.unit
            )
        else:
            logger.warning(
                f"Some mandatory fields: {missing_options} are not present, do not emit credential change event!"
            )

    def _on_secret_changed_event(self, event: SecretChangedEvent) -> None:
        """Event handler for handling a new value of a secret."""
        if not event.secret.label:
            return

        relation = self.relation_data._relation_from_secret_label(event.secret.label)
        if not relation:
            logging.info(
                f"Received secret {event.secret.label} but couldn't parse, seems irrelevant."
            )
            return

        if event.secret.label != self.relation_data._generate_secret_label(
            relation.name,
            relation.id,
            "extra",
        ):
            logging.info("Secret is not relevant for us.")
            return

        if relation.app == self.charm.app:
            logging.info("Secret changed event ignored for Secret Owner")

        remote_unit = None
        for unit in relation.units:
            if unit.app != self.charm.app:
                remote_unit = unit

        # check if the mandatory options are in the relation data
        contains_required_options = True
        credentials = self.get_s3_connection_info()
        missing_options = []
        for configuration_option in S3_REQUIRED_OPTIONS:
            if configuration_option not in credentials:
                contains_required_options = False
                missing_options.append(configuration_option)

        # emit credential change event only if all mandatory fields are present
        if contains_required_options:
            getattr(self.on, "s3_connection_info_changed").emit(
                relation, app=relation.app, unit=remote_unit
            )
        else:
            logger.warning(
                f"Some mandatory fields: {missing_options} are not present, do not emit credential change event!"
            )

    def _on_relation_broken_event(self, event: RelationBrokenEvent) -> None:
        """Event handler for handling relation_broken event."""
        logger.info("S3 relation broken...")
        getattr(self.on, "s3_connection_info_gone").emit(
            event.relation, app=event.app, unit=event.unit
        )

    @property
    def relations(self) -> list[Relation]:
        """The list of Relation instances associated with this relation_name."""
        return list(self.charm.model.relations[self.relation_name])


class S3Requires(S3RequirerData, S3RequirerEventHandlers):
    """The requirer side of S3 relation."""

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str,
        container: str | None = None,
    ):
        S3RequirerData.__init__(self, charm.model, relation_name, container)
        S3RequirerEventHandlers.__init__(self, charm, self)


class S3ProviderData(ProviderData):
    """The Data abstraction of the provider side of S3 relation."""

    def __init__(self, model: Model, relation_name: str) -> None:
        super().__init__(model, relation_name)


class S3ProviderEventHandlers(EventHandlers):
    """The event handlers related to provider side of S3 relation."""

    on = S3ProviderEvents()  # type: ignore

    def __init__(self, charm: CharmBase, relation_data: S3ProviderData, unique_key: str = ""):
        super().__init__(charm, relation_data, unique_key)
        self.relation_data = relation_data

    def _on_relation_changed_event(self, event: RelationChangedEvent):
        if not self.charm.unit.is_leader():
            return
        diff = self._diff(event)
        if "bucket" in diff.added:
            self.on.storage_connection_info_requested.emit(
                event.relation, app=event.app, unit=event.unit
            )


class S3Provides(S3ProviderData, S3ProviderEventHandlers):
    """The provider side of the S3 relation."""

    def __init__(self, charm: CharmBase, relation_name: str) -> None:
        S3ProviderData.__init__(self, charm.model, relation_name)
        S3ProviderEventHandlers.__init__(self, charm, self)
