#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base utilities exposing common functionalities for all Events classes."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Callable

from ops import EventBase, Object, StatusBase
from ops.model import ActiveStatus, BlockedStatus
from pydantic import ValidationError

from core.domain import CharmConfig
from utils.logging import WithLogging
from utils.secrets import decode_secret_key

if TYPE_CHECKING:
    from charm import S3IntegratorCharm


class BaseEventHandler(Object, WithLogging):
    """Base class for all Event Handler classes in the S3 Integrator."""

    charm: S3IntegratorCharm

    def get_app_status(self, model, charm_config) -> StatusBase:
        """Return the status of the charm."""
        try:
            # Check mandatory args and config validation
            CharmConfig(**charm_config)

        except ValidationError as ex:
            self.logger.warning(str(ex))
            missing = [error["loc"][0] for error in ex.errors() if error["type"] == "missing"]
            invalid = [error["loc"][0] for error in ex.errors() if error["type"] != "missing"]

            statuses = []
            if missing:
                statuses.append(f"Missing parameters: {sorted(missing)}")
            if invalid:
                statuses.append(f"Invalid parameters: {sorted(invalid)}")

            return BlockedStatus(" ".join(statuses))
        try:
            decode_secret_key(model, charm_config.get("credentials"))
        except Exception as e:
            self.logger.warning(f"Error in decoding secret: {e}")
            return BlockedStatus(str(e))

        return ActiveStatus()


def compute_status(
    hook: Callable,
) -> Callable[[BaseEventHandler, EventBase], None]:
    """Decorator to automatically compute statuses at the end of the hook."""

    @wraps(hook)
    def wrapper_hook(event_handler: BaseEventHandler, event: EventBase):
        """Return output after resetting statuses."""
        res = hook(event_handler, event)
        if event_handler.charm.unit.is_leader():
            event_handler.charm.app.status = event_handler.get_app_status(
                event_handler.charm.model, event_handler.charm.config
            )
        event_handler.charm.unit.status = event_handler.get_app_status(
            event_handler.charm.model, event_handler.charm.config
        )
        return res

    return wrapper_hook
