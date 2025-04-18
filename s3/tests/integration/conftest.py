#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import os
import random
import string
import subprocess
from pathlib import Path

import jubilant
import pytest

logger = logging.getLogger(__name__)


@pytest.fixture
def s3_charm() -> Path:
    """Path to the packed s3-integrator charm."""
    if not (path := next(iter(Path.cwd().glob("*.charm")), None)):
        raise FileNotFoundError("Could not find packed s3-integrator charm.")

    return path


@pytest.fixture
def test_charm() -> Path:
    if not (
        path := next(iter((Path.cwd() / "tests/integration/test-charm-s3").glob("*.charm")), None)
    ):
        raise FileNotFoundError("Could not find packed test charm.")

    return path


@pytest.fixture(scope="module")
def juju():
    with jubilant.temp_model() as juju:
        yield juju


@pytest.fixture(scope="module")
def s3_info() -> dict[str, str]:
    """S3 object storage info."""
    logger.info("Retrieving s3 creds")

    if os.environ.get("SUBSTRATE", "microk8s") == "vm":
        return {
            "endpoint": "http://localhost:80",
            "access-key": "foo",
            "secret-key": "bar",
        }

    else:
        setup_minio_output = (
            subprocess.check_output(
                "./tests/integration/setup/setup_minio.sh | tail -n 1", shell=True, stderr=None
            )
            .decode("utf-8")
            .strip()
        )

        logger.info(f"Minio output:\n{setup_minio_output}")
        endpoint, access_key, secret_key = setup_minio_output.strip().split(",")

        return {
            "endpoint": endpoint,
            "access-key": access_key,
            "secret-key": secret_key,
        }


@pytest.fixture(scope="module")
def bucket_name() -> str:
    return f"bucket-{''.join(random.sample(string.ascii_lowercase, 6))}"
