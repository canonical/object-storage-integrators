#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from pathlib import Path
from typing import Iterable

import pytest
import yaml
from ops.testing import Context, State
from pydantic import ValidationError
from pytest import fixture

from src.charm import S3IntegratorCharm
from src.core.domain import CharmConfig

logger = logging.getLogger(__name__)

CONFIG = yaml.safe_load(Path("./config.yaml").read_text())
ACTIONS = yaml.safe_load(Path("./actions.yaml").read_text())
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())


@fixture()
def ctx() -> Context:
    ctx = Context(S3IntegratorCharm, meta=METADATA, config=CONFIG, actions=ACTIONS, unit_id=0)
    return ctx


@fixture
def base_state() -> State:
    return State(leader=True)


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
