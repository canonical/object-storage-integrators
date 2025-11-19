#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import os
import re
from pathlib import Path
from platform import machine

import architecture
import jubilant
import pytest
from jubilant import CLIError

SUPPORTED_BASES_TO_SERIES = {
    "23.04": "lunar",
    "24.04": "noble",
    "25.04": "plucky",
}

_SUPPORTED_LIST: str = ", ".join(SUPPORTED_BASES_TO_SERIES.keys())


def _normalize_base(v: str | None) -> str:
    """Normalize a base string to the canonical "YY.MM" form.

    Accepts "YY.MM" or "ubuntu@YY.MM". If the input is false, returns "24.04".

    Args:
        v: Raw value from CHARM_UBUNTU_BASE.

    Returns:
        Canonical base string in "YY.MM" form.

    Raises:
        RuntimeError: If the value does not match the expected format.
    """
    if not v:
        return "24.04"
    m = re.fullmatch(r"(?:ubuntu@)?(\d{2}\.\d{2})", v.strip())
    if not m:
        raise RuntimeError(f"Invalid CHARM_UBUNTU_BASE: {v!r} (allowed: {_SUPPORTED_LIST})")
    return m.group(1)


@pytest.fixture
def ubuntu_base() -> str:
    """Normalized Ubuntu base as "YY.MM".

    Reads CHARM_UBUNTU_BASE from the environment and normalizes it. Defaults to "24.04".
    """
    return _normalize_base(os.environ.get("CHARM_UBUNTU_BASE"))


@pytest.fixture
def gcs_charm(ubuntu_base: str) -> Path:
    """Path to the locally packed provider charm for the selected base.

    Expected filename format: gcs_integrator_ubuntu@<base>-<arch>.charm

    Args:
        ubuntu_base: Canonical "YY.MM" base string.

    Returns:
        The local charm path (as a Path).
    """
    arch = architecture.architecture  # "amd64"
    charm = Path(f"./gcs-integrator_ubuntu@{ubuntu_base}-{arch}.charm")
    if not charm.exists():
        raise FileNotFoundError(
            f"Charm not found at {charm}. Did you pack it for base={ubuntu_base}, arch={arch}?"
        )
    return charm


def _local(charm: str | Path) -> str:
    """Return an absolute path for a local charm file.

    Resolving to an absolute path.
    Only local .charm files are expected here.
    """
    return str(Path(charm).resolve())


def ensure_deployed(juju, charm: str | Path, app: str, **kwargs) -> None:
    """Deploy an application if needed, then wait until agents are idle.

    If it is already deployed, it will be skipped.

    Args:
        juju: Jubilant controller handle.
        charm: Local charm path
        app: Application name to deploy as.
        **kwargs: Extra keyword arguments forwarded to juju.deploy().
    """
    try:
        juju.deploy(_local(charm), app=app, **kwargs)
    except CLIError as e:
        if "already exists" not in (e.stderr or "") and "application already exists" not in (
            e.stderr or ""
        ):
            raise
    juju.wait(lambda s: jubilant.all_agents_idle(s, app), delay=5)


def integrate_once(juju, provider_ep: str, requirer_ep: str) -> None:
    """Integrate provider and requirer charms. If they are already integrated, do nothing.

    Args:
        juju: Jubilant controller handle.
        provider_ep: Local charm path.
        requirer_ep: Local charm path.
    """
    st = juju.status()
    prov_app, prov_ep = provider_ep.split(":")
    req_app, _ = requirer_ep.split(":")

    for rel in st.apps[prov_app].relations.get(prov_ep, []):
        if rel.related_app == req_app:
            return

    juju.integrate(provider_ep, requirer_ep)


@pytest.fixture
def platform() -> str:
    """Fixture to provide the platform architecture for testing."""
    platforms = {
        "x86_64": "amd64",
        "aarch64": "arm64",
    }
    return platforms.get(machine(), "amd64")


@pytest.fixture(scope="session")
def requirer_charm() -> Path:
    """Path to the locally packed test requirer charm."""
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
