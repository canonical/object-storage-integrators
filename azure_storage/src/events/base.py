#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base utilities exposing common functionalities for all Events classes."""

from functools import wraps
from typing import Callable

from ops import EventBase, Model, Object, StatusBase
from ops.model import ActiveStatus, BlockedStatus, ModelError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from constants import AZURE_MANDATORY_OPTIONS
from utils.logging import WithLogging
from utils.secrets import decode_secret_key


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    retry=retry_if_exception_type(ModelError),
    reraise=True,
)
def decode_secret_key_with_retry(model: Model, secret_id: str):
    """Try to decode the secret key, retry for 3 times before failing."""
    return decode_secret_key(model, secret_id)


class BaseEventHandler(Object, WithLogging):
    """Base class for all Event Handler classes in the Azure Storage Integrator."""

    def get_app_status(self, model, charm_config) -> StatusBase:
        """Return the status of the charm."""
        missing_options = []
        for config_option in AZURE_MANDATORY_OPTIONS:
            if not charm_config.get(config_option):
                missing_options.append(config_option)
        if missing_options:
            self.logger.warning(f"Missing parameters: {missing_options}")
            return BlockedStatus(f"Missing parameters: {missing_options}")
        try:
            decode_secret_key_with_retry(model, charm_config.get("credentials"))
        except Exception as e:
            self.logger.warning(f"Error in decoding secret: {e}")
            return BlockedStatus(str(e))

        return ActiveStatus()


def compute_status(
    hook: Callable[[BaseEventHandler, EventBase], None],
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
