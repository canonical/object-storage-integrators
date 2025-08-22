#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import logging
import os
import random
import socket
import string
import subprocess
from pathlib import Path
from typing import Iterable

import jubilant
import pytest
from domain import S3ConnectionInfo
from helpers import create_bucket, delete_bucket, local_tmp_folder

MICROCEPH_REVISION = 1169

logger = logging.getLogger(__name__)
logging.getLogger("jubilant.wait").setLevel(logging.WARNING)


def pytest_addoption(parser):
    parser.addoption(
        "--keep-models",
        action="store_true",
        default=False,
        help="keep temporarily-created models",
    )


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
def juju(request: pytest.FixtureRequest):
    keep_models = bool(request.config.getoption("--keep-models"))

    with jubilant.temp_model(keep=keep_models) as juju:
        juju.wait_timeout = 10 * 60

        yield juju  # run the test

        if request.session.testsfailed:
            log = juju.debug_log(limit=30)
            print(log, end="")


@pytest.fixture(scope="module")
def host_ip() -> str:
    """The IP address of the host running these tests."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("1.1.1.1", 80))
        return s.getsockname()[0]


@pytest.fixture(scope="module")
def certs_path() -> Iterable[Path]:
    """A temporary directory to store certificates and keys."""
    with local_tmp_folder("temp-certs") as tmp_folder:
        yield tmp_folder


@pytest.fixture(scope="module")
def s3_info(host_ip: str, certs_path: Path) -> Iterable[S3ConnectionInfo]:
    """Return S3 credentials from environment if available; and if not, setup microceph and return S3 credentials."""
    if os.environ.get("S3_ACCESS_KEY") and os.environ.get("S3_SECRET_KEY"):
        yield S3ConnectionInfo(
            endpoint=os.environ.get("S3_ENDPOINT", ""),
            access_key=os.environ.get("S3_ACCESS_KEY", ""),
            secret_key=os.environ.get("S3_SECRET_KEY", ""),
            region=os.environ.get("S3_REGION", "us-east-1"),
            tls_ca_chain=os.environ.get("S3_TLS_CA", ""),
        )
    else:
        logger.info("Setting up TLS certificates")
        subprocess.run(
            ["openssl", "genrsa", "-out", str(certs_path / "ca.key"), "2048"], check=True
        )
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-new",
                "-nodes",
                "-key",
                str(certs_path / "ca.key"),
                "-days",
                "1024",
                "-out",
                str(certs_path / "ca.crt"),
                "-outform",
                "PEM",
                "-subj",
                f"/C=US/ST=Denial/L=Springfield/O=Dis/CN={host_ip}",
            ],
            check=True,
        )
        subprocess.run(
            ["openssl", "genrsa", "-out", str(certs_path / "server.key"), "2048"],
            check=True,
        )
        subprocess.run(
            [
                "openssl",
                "req",
                "-new",
                "-key",
                str(certs_path / "server.key"),
                "-out",
                str(certs_path / "server.csr"),
                "-subj",
                f"/C=US/ST=Denial/L=Springfield/O=Dis/CN={host_ip}",
            ],
            check=True,
        )

        with open(certs_path / "extfile.cnf", "w") as extfile:
            extfile.write(f"subjectAltName = DNS:{host_ip}, IP:{host_ip}")

        subprocess.run(
            [
                "openssl",
                "x509",
                "-req",
                "-in",
                str(certs_path / "server.csr"),
                "-CA",
                str(certs_path / "ca.crt"),
                "-CAkey",
                str(certs_path / "ca.key"),
                "-CAcreateserial",
                "-out",
                str(certs_path / "server.crt"),
                "-days",
                "365",
                "-extfile",
                str(certs_path / "extfile.cnf"),
            ],
        )

        logger.info("Setting up microceph")
        subprocess.run(
            ["sudo", "snap", "install", "microceph", "--revision", str(MICROCEPH_REVISION)],
            check=True,
        )
        try:
            subprocess.run(
                ["sudo", "microceph", "cluster", "bootstrap"],
                check=True,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as ex:
            logger.error(ex.stderr.decode())

        subprocess.run(
            ["sudo", "microceph", "disk", "add", "loop,1G,3"],
            check=True,
        )
        server_crt_base64 = subprocess.run(
            ["sudo", "base64", "-w0", str(certs_path / "server.crt")],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        server_key_base64 = subprocess.run(
            ["sudo", "base64", "-w0", str(certs_path / "server.key")],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        logger.info("Enabling rest gateway")
        subprocess.run(
            [
                "sudo",
                "microceph",
                "enable",
                "rgw",
                "--ssl-certificate",
                server_crt_base64,
                "--ssl-private-key",
                server_key_base64,
            ],
            check=True,
        )

        output = subprocess.run(
            [
                "sudo",
                "microceph.radosgw-admin",
                "user",
                "create",
                "--uid",
                "test",
                "--display-name",
                "test",
            ],
            capture_output=True,
            check=True,
            encoding="utf-8",
        ).stdout
        key = json.loads(output)["keys"][0]
        key_id = key["access_key"]
        secret_key = key["secret_key"]

        ca_crt_base64 = subprocess.run(
            ["sudo", "base64", "-w0", str(certs_path / "ca.crt")],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()

        yield S3ConnectionInfo(
            endpoint=f"https://{host_ip}",
            access_key=key_id,
            secret_key=secret_key,
            tls_ca_chain=ca_crt_base64,
            region="us-east-1",
        )

        subprocess.run(["sudo", "snap", "remove", "microceph", "--purge"], check=True)


@pytest.fixture(scope="module")
def bucket_name() -> str:
    return f"s3-integrator-{''.join(random.sample(string.ascii_lowercase, 6))}"


@pytest.fixture(scope="module")
def pre_created_bucket(s3_info, bucket_name):
    bucket = create_bucket(s3_info, bucket_name)
    assert bucket is not None
    yield bucket.name
    deleted = delete_bucket(s3_info, bucket_name)
    assert deleted
