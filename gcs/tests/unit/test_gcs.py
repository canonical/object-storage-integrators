# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
import unittest.mock
from asyncio.log import logger

from ops.model import BlockedStatus
from ops.testing import Harness

from charm import AzureStorageIntegratorCharm
from core.domain import AzureConnectionInfo
from utils.secrets import decode_secret_key


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

    @unittest.mock.patch("events.base.decode_secret_key_with_retry", decode_secret_key)
    def test_on_config_changed(self):
        """Checks that configuration parameters are correctly stored in the databag."""
        # trigger the leader_elected and config_changed events
        self.harness.set_leader(True)

        self.harness.update_config({"storage-account": "storage-account"})
        self.harness.update_config({"container": "container"})
        self.harness.update_config({"credentials": "secret:sdfasdfadfasdf"})
        self.harness.update_config({"path": "some/path"})

        self.assertEqual(self.harness.charm.config["storage-account"], "storage-account")
        self.assertEqual(self.harness.charm.config["container"], "container")
        self.assertEqual(self.harness.charm.config["path"], "some/path")

        self.assertIsNotNone(self.harness.charm.context.azure_storage)
        self.assertEqual(type(self.harness.charm.context.azure_storage), AzureConnectionInfo)

    def test_azure_storage_info_none(self):
        """Checks that context.azure_storage returns None when mandatory configs are not set."""
        self.harness.update_config({"storage-account": None})
        self.assertIsNone(self.harness.charm.context.azure_storage)
