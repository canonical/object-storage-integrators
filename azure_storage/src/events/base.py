#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base utilities exposing common functionalities for all Events classes."""

from functools import wraps
from typing import Callable

from ops import EventBase, Object, StatusBase
from ops.model import ActiveStatus, BlockedStatus

from constants import AZURE_MANDATORY_OPTIONS, AZURE_SERVICE_PRINCIPAL_OPTIONS
from utils.logging import WithLogging
from utils.secrets import decode_secret


class BaseEventHandler(Object, WithLogging):
    """Base class for all Event Handler classes in the Azure Storage Integrator."""

    def get_app_status(self, model, charm_config) -> StatusBase:
        """Return the status of the charm."""
        missing_options = [opt for opt in AZURE_MANDATORY_OPTIONS if not charm_config.get(opt)]
        if missing_options:
            msg = f"Missing parameters: {missing_options}"
            self.logger.warning(msg)
            return BlockedStatus(msg)

        try:
            secret = decode_secret(model, charm_config.get("credentials"))
            storage_account_secret = secret.get("secret-key")
            service_principal_secret = secret.get("client-secret")
        except Exception as e:
            self.logger.warning(f"Error in decoding secret: {e}")
            return BlockedStatus(str(e))

        if storage_account_secret and service_principal_secret:
            msg = "Both secret-key and client-secret are present in the secret."
            self.logger.warning(msg)
            return BlockedStatus(msg)
        if not storage_account_secret and not service_principal_secret:
            msg = "Neither secret-key nor client-secret are present in the secret."
            self.logger.warning(msg)
            return BlockedStatus(msg)

        if service_principal_secret:
            missing_sp_options = [
                opt for opt in AZURE_SERVICE_PRINCIPAL_OPTIONS if not charm_config.get(opt)
            ]
            if missing_sp_options:
                msg = f"Missing parameters: {missing_sp_options} for service principal."
                self.logger.warning(msg)
                return BlockedStatus(msg)

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
