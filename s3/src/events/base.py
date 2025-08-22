#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Base utilities exposing common functionalities for all Events classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ops import Object

from utils.logging import WithLogging

if TYPE_CHECKING:
    from charm import S3IntegratorCharm


class BaseEventHandler(Object, WithLogging):
    """Base class for all Event Handler classes in the S3 Integrator."""

    charm: S3IntegratorCharm
