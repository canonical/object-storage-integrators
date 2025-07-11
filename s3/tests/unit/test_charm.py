#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import base64
import dataclasses
import json
from pathlib import Path

import yaml
from ops import ActiveStatus, BlockedStatus
from ops.testing import Context, Secret, State, Relation
from pytest import fixture
import pytest

from src.charm import S3IntegratorCharm
from src.utils.secrets import decode_secret_key
from src.core.domain import parse_ca_chain

CONFIG = yaml.safe_load(Path("./config.yaml").read_text())
ACTIONS = yaml.safe_load(Path("./actions.yaml").read_text())
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())


@fixture()
def ctx() -> Context:
    ctx = Context(S3IntegratorCharm, meta=METADATA, config=CONFIG, actions=ACTIONS, unit_id=0)
    return ctx


@fixture()
def charm_configuration():
    """Enable direct mutation on configuration dict."""
    return json.loads(json.dumps(CONFIG))


@fixture
def base_state() -> State:
    return State(leader=True)


@fixture
def valid_ca_chain() -> bytes:
    return b"""-----BEGIN CERTIFICATE-----
    MIIDdTCCAl2gAwIBAgIUPf3+kJh2V3yGpG3Yw2iDL8Nv3dUwDQYJKoZIhvcNAQEL
    BQAwVTELMAkGA1UEBhMCVVMxCzAJBgNVBAgMAkNBMRMwEQYDVQQHDApTYW4gRnJh
    bmNpc2NvMQ0wCwYDVQQKDARUZXN0MQ0wCwYDVQQLDARUZXN0MQ0wCwYDVQQDDARU
    ZXN0MB4XDTI1MDcxMTE0MjAwMFoXDTI2MDcxMTE0MjAwMFowVTELMAkGA1UEBhMC
    VVMxCzAJBgNVBAgMAkNBMRMwEQYDVQQHDApTYW4gRnJhbmNpc2NvMQ0wCwYDVQQK
    DARUZXN0MQ0wCwYDVQQLDARUZXN0MQ0wCwYDVQQDDARUZXN0MIIBIjANBgkqhkiG
    9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtbP70X5uF64ZlKFFzy3R0YrF2XoPa+FqEZX2
    2Meo5uM8Q8rYOA6KJ0lHl7i99ewom0DeZzj4Iu6kAM5OHb9fp9PV7d8DN2fY7n95
    wv3pJmsU0gACksZ1Ept1Q0txjSBQ9bqAmB/9PjVgZ6xph8myoRByCrjXKMB6IQfn
    xi9FqRnKo/TF30B1NPAyJUmBWQkxSHADw4VvAY2r+J+m+g5RwP8co3y27iWbJX40
    0AxpsGEAglhMAVtt12afWYDPwGMO/EF7qC9t8rA3eQ65u6UGDAm6HCEBDpo8Hu1l
    UIEYVjSM6qf7FPZfg2tRQJ9jclxRKwOG4nJnnYJmLBJIl/04eQIDAQABo1MwUTAd
    BgNVHQ4EFgQUv1sfFGaV6C0kNEM4LJgSu5kAzGowHwYDVR0jBBgwFoAUv1sfFGaV
    6C0kNEM4LJgSu5kAzGowDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOC
    AQEAQxFfL9GKl15nZtYQPO8nW8WD+PpVEJeHykr3nEzG+Y0TfXswQsWmklrFPvUG
    klzE3tXtv83S7d9v6Obh2r2xtBGSE2c23nOedAyF3W0cog0bft27GDVfsI5Nyztr
    Sx+7MgYjX1zB+HRP8vEk+PzGw2buw9zR5V9cDJJ3qgJoVfnugL8HoZ2Jk3hv3ckc
    D6/TzH+HKylajc6dp9aVhA/2l/tkng18kJjElIhxMF4NWTzS9M8F4/lBaWNHjT99
    OAGZP0EuIEqIuf/Zo+uF+OJdzJavEmmpQ9szN7hM0YvZCTUOSPrBvEDRpjgF7mP8
    y+1t2W4HhFq2DAya9rjqLPX2vQ==
    -----END CERTIFICATE-----
    -----BEGIN CERTIFICATE-----
    MIIDdTCCAl2gAwIBAgIUONfUuuvzZLwGzyXtJ+LrjI+Cl/0wDQYJKoZIhvcNAQEL
    BQAwVTELMAkGA1UEBhMCVVMxCzAJBgNVBAgMAkNBMRMwEQYDVQQHDApTYW4gRnJh
    bmNpc2NvMQ0wCwYDVQQKDARUZXN0MQ0wCwYDVQQLDARUZXN0MQ0wCwYDVQQDDARU
    ZXN0MB4XDTI1MDcxMTE0MjAwMFoXDTI2MDcxMTE0MjAwMFowVTELMAkGA1UEBhMC
    VVMxCzAJBgNVBAgMAkNBMRMwEQYDVQQHDApTYW4gRnJhbmNpc2NvMQ0wCwYDVQQK
    DARUZXN0MQ0wCwYDVQQLDARUZXN0MQ0wCwYDVQQDDARUZXN0MIIBIjANBgkqhkiG
    9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnMd8Tcf8JmJsQf93fPxLwbSo0lPG7wDAlFAE
    CJyz20UkwZ8xj/JKZQO7cZ1DpG4OTLy9SLOeBlhnMEz7n0Z+QOgT0hFqUP5XcN7r
    WbdexBptFRv7L1Sh1ifA14RpOgqY2uGFRcKK4grtKBD1MK9ekkm4qG3z0IqZk1Ml
    cCc7O4j/NGmExrhBQF1WAFIUXa53cwNHxKOVb1N2xgIQ9VX5WBQ46F8ziX4aXhKU
    Gu1TxgnOL8hcESGUVX1y1sgob7uQgVrf+qkE4S+5S6FQdPY3DLzT1h9jPFOIbj4k
    T6qEG7/1JXUn9W3AFZgHAnzK7w/4IW70Gh4zuU03E/ZebTZDnwIDAQABo1MwUTAd
    BgNVHQ4EFgQU14R3q8YG46v+07WVe1ovk4n/4j0wHwYDVR0jBBgwFoAU14R3q8YG
    46v+07WVe1ovk4n/4j0wDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOC
    AQEAAHDxCC8JZ61KJ49Tj0dAKb7ojgu2+T1cQl5t9bCwglf6bMZ9JcICDXXMbdtB
    OunAfOaOwDeS4pVzthH+yN8qijWod6qHbJG6B8G5C5VOn85cyJ3keqjVQ5jpvC8l
    r9npfnwH1h5GzM6vNvlc5fjH85W8Igh7nQXy6RqnP+pvnW3qMPdD3DL4VVdrwkkk
    r1vmxeX12QxYMFwVu6eRwEj87lhtS+QTtK/AojEMp1rBOL6uafc80glAVjeX4N9r
    1HZgLRl6xkzP6uTI66GOkZWxM6kpXbEu/jNw9JDx6j1RUM2E4wETzOcsWzM5mtFY
    OQ4bq3kbJ6zPvF8RwDtuRSPtSA==
    -----END CERTIFICATE-----
    """


def test_on_start_blocked(ctx: Context[S3IntegratorCharm], base_state: State) -> None:
    """Check that the charm starts in blocked status by default."""
    # Given
    state_in = base_state

    # When
    state_out = ctx.run(ctx.on.start(), state_in)

    # Then
    assert isinstance(status := state_out.unit_status, BlockedStatus)
    assert "credentials" in status.message


def test_on_start_no_secret_access_blocked(charm_configuration: dict, base_state: State) -> None:
    """Check that the charm starts in blocked status if not granted secret access."""
    # Given
    charm_configuration["options"]["bucket"]["default"] = "bucket-name"
    # This secret does not exist
    charm_configuration["options"]["credentials"]["default"] = "secret:1a2b3c4d5e6f7g8h9i0j"
    ctx = Context(
        S3IntegratorCharm, meta=METADATA, config=charm_configuration, actions=ACTIONS, unit_id=0
    )
    state_in = base_state

    # When
    state_out = ctx.run(ctx.on.start(), state_in)

    # Then
    assert isinstance(status := state_out.unit_status, BlockedStatus)
    assert "does not exist" in status.message


@pytest.mark.parametrize(
    "invalid_ca_chain",
    [
        "foobar-random-string",
        "-----BEGIN CERTIFICATE-----\nasdfasdf\n-----END CERTIFICATE-----",  # invalid because not base64-encoded
        base64.b64encode(
            b"-----BEGIN RANDOM-----\nasdfasdf\n-----END RANDOM-----"
        ).decode(),  # invalid because not in PEM format
    ],
)
@patch("events.base.decode_secret_key_with_retry", decode_secret_key)
def test_invalid_ca_chain(charm_configuration: dict, base_state: State, invalid_ca_chain) -> None:
    """Check that the charm starts in blocked status if not granted secret access."""
    # Given
    charm_configuration["options"]["bucket"]["default"] = "bucket-name"
    charm_configuration["options"]["credentials"]["default"] = "secret:1a2b3c4d5e6f7g8h9i0j"

    # This CA chain is invalid
    charm_configuration["options"]["tls-ca-chain"]["default"] = invalid_ca_chain

    ctx = Context(
        S3IntegratorCharm, meta=METADATA, config=charm_configuration, actions=ACTIONS, unit_id=0
    )
    state_in = base_state

    # When
    state_out = ctx.run(ctx.on.config_changed(), state_in)

    # Then
    assert isinstance(status := state_out.unit_status, BlockedStatus)
    assert "Invalid parameters: ['tls-ca-chain']" in status.message


def test_on_start_ok(charm_configuration: dict, base_state: State) -> None:
    """Check that the charm starts in active status if everything is ok."""
    # Given
    credentials_secret = Secret(
        tracked_content={
            "access-key": "accesskey",
            "secret-key": "secretkey",
        }
    )
    charm_configuration["options"]["bucket"]["default"] = "bucket-name"
    charm_configuration["options"]["credentials"]["default"] = credentials_secret.id
    ctx = Context(
        S3IntegratorCharm, meta=METADATA, config=charm_configuration, actions=ACTIONS, unit_id=0
    )
    state_in = dataclasses.replace(base_state, secrets={credentials_secret})

    # When
    state_out = ctx.run(ctx.on.start(), state_in)

    # Then
    assert state_out.unit_status == ActiveStatus()


@patch("events.base.decode_secret_key_with_retry", decode_secret_key)
def test_provider_valid_parameters(
    charm_configuration: dict, base_state: State, valid_ca_chain: bytes
) -> None:
    """Check that the charm starts in blocked status if not granted secret access."""
    # Given
    credentials_secret = Secret(
        tracked_content={"access-key": "my-access-key", "secret-key": "my-secret-key"}
    )
    charm_configuration["options"]["bucket"]["default"] = "bucket-name"
    charm_configuration["options"]["credentials"]["default"] = credentials_secret.id

    # This CA chain is valid
    ca_chain_encoded = base64.b64encode(valid_ca_chain).decode()
    charm_configuration["options"]["tls-ca-chain"]["default"] = ca_chain_encoded
    ctx = Context(
        S3IntegratorCharm, meta=METADATA, config=charm_configuration, actions=ACTIONS, unit_id=0
    )
    # Given
    state_in = dataclasses.replace(base_state, secrets=[credentials_secret])

    # When
    state_out = ctx.run(ctx.on.config_changed(), state_in)

    # Then
    assert isinstance(status := state_out.unit_status, ActiveStatus)

    s3_provider_relation = Relation(
        endpoint="s3-credentials", remote_app_data={"bucket": "test-bucket"}
    )

    # Given
    state_in = dataclasses.replace(state_out, relations=[s3_provider_relation])

    # When
    state_out = ctx.run(ctx.on.relation_changed(s3_provider_relation), state_in)

    # Then
    provider_data = state_out.get_relation(s3_provider_relation.id).local_app_data
    assert provider_data["bucket"] == "test-bucket"
    assert provider_data["access-key"] == "my-access-key"
    assert provider_data["secret-key"] == "my-secret-key"
    assert provider_data["tls-ca-chain"] == json.dumps(parse_ca_chain(valid_ca_chain.decode()))
