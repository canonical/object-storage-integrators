# Copyright 2025
# SPDX-License-Identifier: Apache-2.0
import subprocess

architecture = subprocess.run(
    ["dpkg", "--print-architecture"], capture_output=True, check=True, encoding="utf-8"
).stdout.strip()
