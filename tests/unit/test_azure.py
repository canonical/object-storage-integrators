# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from asyncio.log import logger

from ops.model import BlockedStatus
from ops.testing import Harness

from charm import AzureStorageIntegratorCharm


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(AzureStorageIntegratorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.charm = self.harness.charm

    def test_on_start(self):
        """Checks that the charm started in blocked status for missing parameters."""
        self.harness.set_leader(True)
        self.charm.on.config_changed.emit()
        self.charm.on.start.emit()
        # check that the charm is in blocked status
        logger.info(f"Status: {self.harness.model.unit.status}")
        self.assertTrue(isinstance(self.harness.model.unit.status, BlockedStatus))

    def test_on_config_changed(self):
        """Checks that configuration parameters are correctly stored in the databag."""
        # ensure that the peer relation databag is empty

        # trigger the leader_elected and config_changed events
        self.harness.set_leader(True)

        self.harness.update_config({"storage-account": "storage-account"})
        self.harness.update_config({"container": "container"})
        self.harness.update_config({"path": "some/path"})

        self.assertEqual(self.harness.charm.config["storage-account"], "storage-account")
        self.assertEqual(self.harness.charm.config["container"], "container")
        self.assertEqual(self.harness.charm.config["path"], "some/path")
