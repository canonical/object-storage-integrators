#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base utilities exposing common functionalities for all Events classes."""

from functools import wraps
from typing import Callable

from ops import EventBase, Model, Object, StatusBase
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus
from core.charm_config import get_charm_config
from constants import CREDENTIAL_FIELD, MANDATORY_OPTIONS
from utils.logging import WithLogging
from utils.secrets import decode_secret_key_with_retry


class BaseEventHandler(Object, WithLogging):
    """Base class for all Event Handler classes in the GCS Integrator."""

    def get_app_status(self, model, cfg_map) -> StatusBase:
        """Return the status of the charm."""
        missing = [opt for opt in MANDATORY_OPTIONS if not (cfg_map.get(opt) or "").strip()]
        if missing:
            self.logger.warning("Missing parameters: %s", missing)
            return BlockedStatus(f"Missing parameters: {missing}")

        try:
            decode_secret_key_with_retry(model, cfg_map.get("credentials"))
        except Exception as e:
            self.logger.warning(f"Error in decoding secret: {e}")
            return BlockedStatus(f"The credentials secret could not be decoded: {str(e)}")

        if not cfg_map.get("validate-credentials"):
            return ActiveStatus("ready")

        try:
            cfg = get_charm_config(self.charm)
        except Exception as e:
            self.logger.warning("Invalid config: %s", e)
            return BlockedStatus(str(e))

        ok, message = self._validate_online(cfg)
        if not ok:
            if "waiting for" in message or "permission" in message.lower():
                return WaitingStatus(message)
            return BlockedStatus(message)

        return ActiveStatus("ready")

    def _validate_online(self, cfg) -> tuple[bool, str]:
        """Pure online check. Accepts a CharmConfig; returns (ok, message)."""
        return cfg.access_google_apis(self.charm)

def compute_status(
    hook: Callable[[BaseEventHandler, EventBase], None],
) -> Callable[[BaseEventHandler, EventBase], None]:
    """Decorator to automatically compute statuses at the end of the hook."""

    @wraps(hook)
    def wrapper_hook(event_handler: BaseEventHandler, event: EventBase):
        """Return output after resetting statuses."""
        res = hook(event_handler, event)
        status = event_handler.get_app_status(
            event_handler.charm.model, event_handler.charm.config
        )
        if event_handler.charm.unit.is_leader():
            event_handler.charm.app.status = status
        event_handler.charm.unit.status = status
        return res

    return wrapper_hook
