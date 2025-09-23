#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

import jubilant
import pytest


@pytest.fixture(scope="module")
def gcs_charm() -> Path:
    path = next(iter(Path.cwd().glob("*.charm")), None)
    if not path:
        raise FileNotFoundError("Could not find packed gcs-integrator charm.")
    return path


@pytest.fixture
def requirer_charm() -> Path:
    if not (
        path := next(iter((Path.cwd() / "tests/integration/requirer-charm").glob("*.charm")), None)
    ):
        raise FileNotFoundError("Could not find packed test charm.")

    return path


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest):
    keep = bool(request.config.getoption("--keep-models"))
    with jubilant.temp_model(keep=keep) as j:
        j.wait_timeout = 10 * 60
        yield j
        if request.session.testsfailed:
            print(j.debug_log(limit=50), end="")
