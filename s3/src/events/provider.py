#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Azure Storage Provider related event handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from charms.data_platform_libs.v0.data_interfaces import ProviderData
from ops import Model

from core.context import Context
from events.base import BaseEventHandler
from utils.logging import WithLogging

if TYPE_CHECKING:
    from charm import S3IntegratorCharm


class S3ProviderData(ProviderData):
    """The Data abstraction of the provider side of Azure storage relation."""

    def __init__(self, model: Model, relation_name: str) -> None:
        super().__init__(model, relation_name)


class S3ProviderEvents(BaseEventHandler, WithLogging):
    """Class implementing S3 Integration event hooks."""

    def __init__(self, charm: S3IntegratorCharm, context: Context):
        super().__init__(charm, "s3-provider")

        self.charm = charm
        self.context = context

        # self.s3_provider_data = S3ProviderData(self.charm.model, S3_RELATION_NAME)
        # self.s3_provider = S3Provider(self.charm, S3_RELATION_NAME)

        # self.framework.observe(
        #     self.s3_provider.on.credentials_requested, self._on_credential_requested
        # )
