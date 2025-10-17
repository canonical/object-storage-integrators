#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from ops import ActiveStatus, BlockedStatus
from ops.testing import Context, Relation, Secret, State

from src.charm import AzureStorageIntegratorCharm
from src.utils.secrets import decode_secret_key

CONFIG = yaml.safe_load(Path("./config.yaml").read_text())
ACTIONS = yaml.safe_load(Path("./actions.yaml").read_text())
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())


def test_on_start_blocked(base_state: State) -> None:
    """Check that the charm starts in blocked status by default."""
    # Given
    ctx = Context(
        AzureStorageIntegratorCharm, meta=METADATA, config=CONFIG, actions=ACTIONS, unit_id=0
    )
    state_in = base_state

    # When
    state_out = ctx.run(ctx.on.start(), state_in)

    # Then
    assert isinstance(status := state_out.unit_status, BlockedStatus)
    assert "Missing parameters" in status.message


@patch("events.base.decode_secret_key_with_retry", decode_secret_key)
def test_on_start_ok(charm_configuration: dict, base_state: State) -> None:
    """Check that the charm starts in active status if everything is ok."""
    # Given
    credentials_secret = Secret(
        tracked_content={
            "secret-key": "secretkey",
        }
    )
    charm_configuration["options"]["container"]["default"] = "container-name"
    charm_configuration["options"]["storage-account"]["default"] = "stoacc"
    charm_configuration["options"]["credentials"]["default"] = credentials_secret.id
    ctx = Context(
        AzureStorageIntegratorCharm,
        meta=METADATA,
        config=charm_configuration,
        actions=ACTIONS,
        unit_id=0,
    )
    state_in = dataclasses.replace(base_state, secrets={credentials_secret})

    # When
    state_out = ctx.run(ctx.on.start(), state_in)

    # Then
    assert state_out.unit_status == ActiveStatus()


@patch("events.base.decode_secret_key_with_retry", decode_secret_key)
@patch("ops.framework.EventBase.defer")
def test_provider_data_premature_data_access_error(
    mock_event_defer: MagicMock,
    charm_configuration: dict,
    base_state: State,
) -> None:
    """Check the behavior when provider attempts to write data before relation handshake is complete."""
    # Given
    credentials_secret = Secret(
        tracked_content={
            "secret-key": "secretkey",
        }
    )
    charm_configuration["options"]["container"]["default"] = "container-name"
    charm_configuration["options"]["storage-account"]["default"] = "stoacc"
    charm_configuration["options"]["credentials"]["default"] = credentials_secret.id

    ctx = Context(
        AzureStorageIntegratorCharm,
        meta=METADATA,
        config=charm_configuration,
        actions=ACTIONS,
        unit_id=0,
    )
    azure_provider_relation = Relation(
        endpoint="azure-storage-credentials",
        remote_app_data={
            "requested-secrets": '["secret-key"]'
        },  # No 'container' from the requirer
    )
    relations = [
        azure_provider_relation,
    ]

    # Given
    state_in = dataclasses.replace(base_state, secrets=[credentials_secret], relations=relations)

    # When
    state_out = ctx.run(ctx.on.relation_changed(azure_provider_relation), state_in)
    ctx.run(ctx.on.config_changed(), state_out)

    # Since the provider attempted to write data before relation handshake is complete,
    # the `config-changed` event should have been deferred.
    mock_event_defer.assert_called_once()


@patch("events.base.decode_secret_key_with_retry", decode_secret_key)
def test_provider_data_happy_path(
    charm_configuration: dict,
    base_state: State,
) -> None:
    """Check the behavior when provider writes data to databag only after relation handshake is complete."""
    # Given
    credentials_secret = Secret(
        tracked_content={
            "secret-key": "secretkey",
        }
    )
    charm_configuration["options"]["container"]["default"] = "container-name"
    charm_configuration["options"]["storage-account"]["default"] = "stoacc"
    charm_configuration["options"]["credentials"]["default"] = credentials_secret.id

    ctx = Context(
        AzureStorageIntegratorCharm,
        meta=METADATA,
        config=charm_configuration,
        actions=ACTIONS,
        unit_id=0,
    )
    azure_provider_relation = Relation(
        endpoint="azure-storage-credentials",
        remote_app_data={
            "requested-secrets": '["secret-key"]',
            "container": "dummy-name",
        },  # No 'container' from the requirer
    )
    relations = [
        azure_provider_relation,
    ]

    # Given
    state_in = dataclasses.replace(base_state, secrets=[credentials_secret], relations=relations)

    # When
    state_mid = ctx.run(ctx.on.relation_changed(azure_provider_relation), state_in)
    state_out = ctx.run(ctx.on.config_changed(), state_mid)

    provider_data = state_out.get_relation(azure_provider_relation.id).local_app_data
    assert provider_data["container"] == "container-name"
    assert provider_data["storage-account"] == "stoacc"
    assert provider_data["connection-protocol"] == "abfss"
    assert "secret-extra" in provider_data
