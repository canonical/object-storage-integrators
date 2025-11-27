#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base utilities exposing common functionalities for all Events classes."""

from functools import wraps
from typing import TYPE_CHECKING, Callable

from charms.data_platform_libs.v0.data_interfaces import PrematureDataAccessError
from ops import EventBase, Object

from utils.logging import WithLogging

if TYPE_CHECKING:
    from charm import GCStorageIntegratorCharm


class BaseEventHandler(Object, WithLogging):
    """Base class for all Event Handler classes in the GCS Integrator."""

    charm: "GCStorageIntegratorCharm"


def defer_on_premature_data_access_error(
    hook: Callable,
) -> Callable[[BaseEventHandler, EventBase], None]:
    """Decorator to defer hook if PrematureDataAccessError is raised."""

    @wraps(hook)
    def wrapper_hook(event_handler: BaseEventHandler, event: EventBase):
        """Defer the event when PrematureDataAccessError is raised, proceed with normal hook otherwise."""
        try:
            return hook(event_handler, event)
        except PrematureDataAccessError:
            event_handler.logger.warning(
                "Deferring the event because of premature data access error..."
            )
            event.defer()
            return None

    return wrapper_hook
