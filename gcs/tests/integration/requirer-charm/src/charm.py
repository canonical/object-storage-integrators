#!/usr/bin/env python3
# Copyright 2025
# SPDX-License-Identifier: Apache-2.0

import ops
from ops.main import main

from events.general import GeneralEvents
from events.requirer import GcsRequirerEvents


class GcsRequirerTestCharm(ops.charm.CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.gcs_requirer_events = GcsRequirerEvents(self)
        self.general_events = GeneralEvents(self)


if __name__ == "__main__":
    main(GcsRequirerTestCharm)
