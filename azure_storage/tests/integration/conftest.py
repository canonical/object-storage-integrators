# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from platform import machine

import pytest


@pytest.fixture
def platform() -> str:
    """Fixture to provide the platform architecture for testing."""
    platforms = {
        "x86_64": "amd64",
        "aarch64": "arm64",
    }
    return platforms.get(machine(), "amd64")
