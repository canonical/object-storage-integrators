#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import base64
import dataclasses
import logging
from pathlib import Path
from typing import Iterable
from unittest.mock import patch

import pytest
import yaml
from ops import BlockedStatus
from ops.testing import Context, Secret, State
from pydantic import ValidationError

from src.charm import S3IntegratorCharm
from src.core.domain import CharmConfig
from src.utils.secrets import decode_secret_key

logger = logging.getLogger(__name__)

CONFIG = yaml.safe_load(Path("./config.yaml").read_text())
ACTIONS = yaml.safe_load(Path("./actions.yaml").read_text())
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())


def check_valid_values(field: str, accepted_values: Iterable) -> None:
    """Check the correctness of the passed values for a field."""
    flat_config_options = {
        option_name: mapping.get("default") for option_name, mapping in CONFIG["options"].items()
    }
    for value in accepted_values:
        try:
            CharmConfig(**{**flat_config_options, **{field: value}})
        except ValidationError as ex:
            assert not any(field in error["loc"] for error in ex.errors())


def check_invalid_values(field: str, erroneus_values: Iterable) -> None:
    """Check the incorrectness of the passed values for a field."""
    flat_config_options = {
        option_name: mapping.get("default") for option_name, mapping in CONFIG["options"].items()
    }
    logger.info(flat_config_options)

    for value in erroneus_values:
        with pytest.raises(ValidationError) as excinfo:
            CharmConfig(**{**flat_config_options, **{field: value}})
        assert any(field in error["loc"] for error in excinfo.value.errors())


@patch("utils.secrets.decode_secret_key_with_retry", decode_secret_key)
def test_secret_does_not_exist(charm_configuration: dict, base_state: State) -> None:
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
@patch("utils.secrets.decode_secret_key_with_retry", decode_secret_key)
def test_invalid_ca_chain(charm_configuration: dict, base_state: State, invalid_ca_chain) -> None:
    """Check that the charm starts in blocked status if given invalid CA chain."""
    # Given
    credentials_secret = Secret(
        tracked_content={
            "access-key": "accesskey",
            "secret-key": "secretkey",
        }
    )
    charm_configuration["options"]["bucket"]["default"] = "bucket-name"
    charm_configuration["options"]["credentials"]["default"] = credentials_secret.id

    # This CA chain is invalid
    charm_configuration["options"]["tls-ca-chain"]["default"] = invalid_ca_chain

    ctx = Context(
        S3IntegratorCharm, meta=METADATA, config=charm_configuration, actions=ACTIONS, unit_id=0
    )
    state_in = dataclasses.replace(base_state, secrets={credentials_secret})

    # When
    state_out = ctx.run(ctx.on.config_changed(), state_in)

    # Then
    assert isinstance(status := state_out.unit_status, BlockedStatus)
    assert "Invalid config(s): 'tls-ca-chain'" in status.message


def test_values_delete_older() -> None:
    """Check experimental-delete-older-than-days."""
    # Given
    erroneus_values = map(str, [0, -2147483649, -34, 9223372036854775807])
    valid_values = map(
        str,
        [
            42,
            1000,
            1,
        ],
    )

    # When
    # Then
    check_invalid_values("experimental-delete-older-than-days", erroneus_values)
    check_valid_values("experimental-delete-older-than-days", valid_values)


def test_values_credentials() -> None:
    """Check credentials secret uri form factor."""
    # Given
    erroneus_values = ["", "secret-label"]
    valid_values = ["secret:1a2b3c4d5e6f7g8h9i0j"]
    check_invalid_values("credentials", erroneus_values)
    check_valid_values("credentials", valid_values)
