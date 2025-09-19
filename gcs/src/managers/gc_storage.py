#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Google Cloud Storage manager."""

from utils.logging import WithLogging


class GCStorageManager(WithLogging):
    """Manager class."""

    def __init__(self, relation_data):
        self.relation_data = relation_data

    def update(self, gcs_connection_info):
        """Update the contents of the relation data bag."""
        if len(self.relation_data.relations) > 0 and gcs_connection_info:
            for relation in self.relation_data.relations:
                self.relation_data.update_relation_data(
                    relation.id, gcs_connection_info.to_dict()
                )
