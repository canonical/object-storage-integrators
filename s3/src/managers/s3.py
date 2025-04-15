#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""S3 manager."""

from core.domain import S3ConnectionInfo
from s3_lib import S3ProviderData
from utils.logging import WithLogging


class S3Manager(WithLogging):
    """S3 manager class."""

    def __init__(self, relation_data: S3ProviderData) -> None:
        self.relation_data = relation_data

    def update(self, s3_connection_info: S3ConnectionInfo | None) -> None:
        """Update the contents of the relation data bag."""
        if len(self.relation_data.relations) > 0 and s3_connection_info:
            for relation in self.relation_data.relations:
                self.relation_data.update_relation_data(relation.id, dict(s3_connection_info))
