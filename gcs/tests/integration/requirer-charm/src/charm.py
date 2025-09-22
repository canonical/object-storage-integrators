#!/usr/bin/env python3
# Copyright 2025
# SPDX-License-Identifier: Apache-2.0

import ops
from ops.main import main

from events.requirer import GcsRequirer
from events.general import GeneralEvents


class GcsRequirerTestCharm(ops.charm.CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.gcs = GcsRequirer(self)
        self.general = GeneralEvents(self, self.gcs)


if __name__ == "__main__":
    main(GcsRequirerTestCharm)