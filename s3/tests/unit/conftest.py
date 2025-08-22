#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from pathlib import Path

import yaml
from ops.testing import PeerRelation, State
from pytest import fixture

CONFIG = yaml.safe_load(Path("./config.yaml").read_text())
ACTIONS = yaml.safe_load(Path("./actions.yaml").read_text())
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())


@fixture()
def charm_configuration():
    """Enable direct mutation on configuration dict."""
    return json.loads(json.dumps(CONFIG))


@fixture
def base_state() -> State:
    status_peers = PeerRelation(endpoint="status-peers")
    return State(
        leader=True,
        relations=[
            status_peers,
        ],
    )


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
