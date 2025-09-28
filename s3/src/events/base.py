#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base utilities exposing common functionalities for all Events classes."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Callable

from ops import EventBase, Object

from s3_lib import PrematureDataAccessError
from utils.logging import WithLogging

if TYPE_CHECKING:
    from charm import S3IntegratorCharm


class BaseEventHandler(Object, WithLogging):
    """Base class for all Event Handler classes in the S3 Integrator."""

    charm: S3IntegratorCharm


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
