#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""S3 Provider related event handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import ops
from data_platform_helpers.advanced_statuses.models import StatusObject
from data_platform_helpers.advanced_statuses.protocol import ManagerStatusProtocol
from data_platform_helpers.advanced_statuses.types import Scope
from ops.charm import ConfigChangedEvent, StartEvent
from pydantic import ValidationError

from core.context import Context
from core.domain import CharmConfig
from events.base import BaseEventHandler, defer_on_premature_data_access_error
from events.statuses import CharmStatuses, ConfigStatuses
from utils.secrets import (
    SecretDecodeError,
    SecretDoesNotExistError,
    SecretFieldMissingError,
    SecretNotGrantedError,
    decode_secret_key_with_retry,
)

if TYPE_CHECKING:
    from charm import S3IntegratorCharm


class GeneralEvents(BaseEventHandler, ManagerStatusProtocol):
    """Class implementing S3 Integration event hooks."""

    def __init__(self, charm: S3IntegratorCharm, context: Context):
        self.name = "general"
        super().__init__(charm, self.name)

        self.charm = charm
        self.state = context

        self.framework.observe(self.charm.on.start, self._on_start)
        self.framework.observe(self.charm.on.update_status, self._on_update_status)
        self.framework.observe(self.charm.on.config_changed, self._on_config_changed)
        self.framework.observe(self.charm.on.secret_changed, self._on_secret_changed)

    def _on_start(self, _: StartEvent) -> None:
        """Handle the charm startup event."""
        pass

    @defer_on_premature_data_access_error
    def _on_update_status(self, event: ops.UpdateStatusEvent) -> None:
        """Handle the update status event."""
        self.charm.s3_provider_events.reconcile_buckets()

    @defer_on_premature_data_access_error
    def _on_config_changed(self, event: ConfigChangedEvent) -> None:  # noqa: C901
        """Event handler for configuration changed events."""
        # Only execute in the unit leader
        if not self.charm.unit.is_leader():
            return
        self.logger.debug(f"Config changed... Current configuration: {self.charm.config}")
        self.charm.s3_provider_events.reconcile_buckets()

    @defer_on_premature_data_access_error
    def _on_secret_changed(self, event: ops.SecretChangedEvent) -> None:
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

        self.charm.s3_provider_events.reconcile_buckets()

    def get_statuses(self, scope: Scope, recompute: bool = False) -> list[StatusObject]:
        """Return the list of statuses for this component."""
        charm_config = self.charm.config
        status_list = []
        try:
            # Check mandatory args and config validation
            CharmConfig(**charm_config)
        except ValidationError as ex:
            self.logger.warning(str(ex))
            missing = [str(error["loc"][0]) for error in ex.errors() if error["type"] == "missing"]
            invalid = [str(error["loc"][0]) for error in ex.errors() if error["type"] != "missing"]

            if missing:
                status_list.append(ConfigStatuses.missing_config_parameters(fields=missing))
            if invalid:
                status_list.append(ConfigStatuses.invalid_config_parameters(fields=invalid))

        if not (credentials := charm_config.get("credentials", "")):
            return status_list

        try:
            decode_secret_key_with_retry(self.charm.model, cast(str, credentials))
        except SecretFieldMissingError as e:
            status_list.append(
                ConfigStatuses.field_missing_in_secret(
                    secret_id=e.secret_id, fields=e.missing_fields
                )
            )
        except SecretDoesNotExistError as e:
            status_list.append(ConfigStatuses.secret_does_not_exist(secret_id=e.secret_id))
        except SecretNotGrantedError as e:
            status_list.append(
                ConfigStatuses.secret_not_granted(
                    secret_id=e.secret_id, app_name=self.model.app.name
                )
            )
        except SecretDecodeError as e:
            status_list.append(ConfigStatuses.secret_cannot_be_decoded(secret_id=e.secret_id))

        return status_list or [CharmStatuses.ACTIVE_IDLE.value]
