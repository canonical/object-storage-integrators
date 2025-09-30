#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

import jubilant
import pytest

# def pytest_addoption(parser):
#    parser.addoption(
#        "--keep-models",
#        action="store_true",
#        default=False,
#        help="keep temporarily-created models",
#    )


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
    try:
        keep = bool(request.config.getoption("--keep-models"))
    except Exception:
        keep = False
    with jubilant.temp_model(keep=keep) as juju:
        juju.wait_timeout = 10 * 60
        yield juju
        if request.session.testsfailed:
            log = juju.debug_log(limit=30)
            print(log, end="")
