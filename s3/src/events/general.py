#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""S3 Provider related event handlers."""

from data_platform_helpers.advanced_statuses.components import ComponentStatuses
from data_platform_helpers.advanced_statuses.models import StatusObject, StatusObjectList
import ops
from ops import ActiveStatus, BlockedStatus, CharmBase
from ops.charm import ConfigChangedEvent, StartEvent
from pydantic import ValidationError

from constants import S3_RELATION_NAME
from core.context import Context
from core.domain import CharmConfig
from events.base import BaseEventHandler, compute_status
from managers.s3 import S3Manager
from s3_lib import S3ProviderData
from utils.logging import WithLogging
from data_platform_helpers.advanced_statuses.protocol import ManagerStatusProtocol
from data_platform_helpers.advanced_statuses.types import Scope

from utils.secrets import decode_secret_key


class GeneralEvents(BaseEventHandler, WithLogging, ManagerStatusProtocol):
    """Class implementing S3 Integration event hooks."""

    def __init__(self, charm: CharmBase, context: Context):
        super().__init__(charm, "general")

        self.charm = charm
        self.context = context
        self.component_statuses = ComponentStatuses(
            self,
            name="s3-integrator",
            status_relation_name="status-peers",
        )
        self.s3_provider_data = S3ProviderData(self.charm.model, S3_RELATION_NAME)
        self.s3_manager = S3Manager(self.s3_provider_data)

        self.framework.observe(self.charm.on.start, self._on_start)
        self.framework.observe(self.charm.on.update_status, self._on_update_status)
        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.secret_changed, self._on_secret_changed)

    def _on_start(self, _: StartEvent) -> None:
        """Handle the charm startup event."""
        pass

    def _on_update_status(self, event: ops.UpdateStatusEvent):
        """Handle the update status event."""
        pass

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:  # noqa: C901
        """Event handler for configuration changed events."""
        # Only execute in the unit leader
        if not self.charm.unit.is_leader():
            return

        self.logger.debug(f"Config changed... Current configuration: {self.charm.config}")
        self.s3_manager.update(self.context.s3)

    def _on_secret_changed(self, event: ops.SecretChangedEvent):
        """Handle the secret changed event.

        When a secret is changed, it is first checked that whether this particular secret
        is used in the charm's config. If yes, the secret is to be updated in the relation
        databag.
        """
        # Only execute in the unit leader
        if not self.charm.unit.is_leader():
            return

        if not self.charm.config.get("credentials"):
            return

        secret = event.secret
        if self.charm.config.get("credentials") != secret.id:
            return

        self.s3_manager.update(self.context.s3)

    def compute_statuses(self, scope: Scope) -> list[StatusObject]:
        """Return the status of the charm."""
        try:
            # Check mandatory args and config validation
            charm_config = CharmConfig(**self.charm.config)  # type: ignore

        except ValidationError as ex:
            self.logger.warning(str(ex))
            missing = [error["loc"][0] for error in ex.errors() if error["type"] == "missing"]
            invalid = [error["loc"][0] for error in ex.errors() if error["type"] != "missing"]

            statuses: list[StatusObject] = []
            if missing:
                statuses.append(
                    StatusObject(status=BlockedStatus(f"Missing parameters: {sorted(missing)}"))
                )
            if invalid:
                statuses.append(
                    StatusObject(status=BlockedStatus(f"Invalid parameters: {sorted(invalid)}"))
                )

            return statuses
        try:
            decode_secret_key(self.charm.model, charm_config.credentials)
        except Exception as e:
            self.logger.warning(f"Error in decoding secret: {e}")
            return [StatusObject(status=BlockedStatus(str(e)))]

        return [StatusObject(status=ActiveStatus("running"))]
