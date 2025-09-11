#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Definition of various model classes."""

from dataclasses import dataclass


@dataclass
class GcsConnectionInfo:
    """Google Cloud Storage connection parameters."""

    bucket: str
    sa_key: str
    storage_class: str
    path: str = None

    def to_dict(self) -> dict:
        """Return the GCS connection parameters as a dictionary."""
        data = {
            "bucket": self.bucket,
            "sa-key": self.sa_key,
        }
        if self.storage_class:
            data["storage-class"] = self.storage_class
        if self.path:
            data["path"] = self.path
        return data
