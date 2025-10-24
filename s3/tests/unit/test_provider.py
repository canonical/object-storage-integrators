#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import base64
import dataclasses
import json
from pathlib import Path
from unittest.mock import patch

import yaml
from ops import ActiveStatus, BlockedStatus
from ops.testing import Context, Relation, Secret, State

from src.charm import S3IntegratorCharm
from src.core.domain import parse_ca_chain
from src.utils.secrets import decode_secret_key

CONFIG = yaml.safe_load(Path("./config.yaml").read_text())
ACTIONS = yaml.safe_load(Path("./actions.yaml").read_text())
METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
S3_LIB_VERSION_FIELD = "lib-version"


@patch("utils.secrets.decode_secret_key_with_retry", decode_secret_key)
@patch("events.provider.S3ProviderEvents.ensure_bucket", return_value=True)
def test_provider_data_no_config_bucket_and_no_bucket_requests(
    mock_ensure_bucket,
    charm_configuration: dict,
    base_state: State,
    valid_ca_chain: bytes,
) -> None:
    """Check the char behavior when bucket is not set in config and no bucket is requested by consumer."""
    # Given
    credentials_secret = Secret(
        tracked_content={"access-key": "my-access-key", "secret-key": "my-secret-key"}
    )
    charm_configuration["options"]["credentials"]["default"] = credentials_secret.id

    # This CA chain is valid
    ca_chain_encoded = base64.b64encode(valid_ca_chain).decode()
    charm_configuration["options"]["tls-ca-chain"]["default"] = ca_chain_encoded
    ctx = Context(
        S3IntegratorCharm,
        meta=METADATA,
        config=charm_configuration,
        actions=ACTIONS,
        unit_id=0,
    )

    # Given
    state_in = dataclasses.replace(base_state, secrets=[credentials_secret])

    # When
    state_out = ctx.run(ctx.on.config_changed(), state_in)

    # Then
    assert isinstance(state_out.unit_status, ActiveStatus)

    relations = list(state_out.relations)
    s3_provider_relation = Relation(
        endpoint="s3-credentials",
        remote_app_data={
            "requested-secrets": '["foobar"]',
            S3_LIB_VERSION_FIELD: "1.0",
        },  # No bucket request from requirer
    )
    relations.append(s3_provider_relation)

    # Given
    state_in = dataclasses.replace(state_out, relations=relations)

    # When
    state_out = ctx.run(ctx.on.relation_changed(s3_provider_relation), state_in)

    # Then
    provider_data = state_out.get_relation(s3_provider_relation.id).local_app_data
    assert "bucket" not in provider_data
    assert provider_data["access-key"] == "my-access-key"
    assert provider_data["secret-key"] == "my-secret-key"
    assert provider_data["tls-ca-chain"] == json.dumps(parse_ca_chain(valid_ca_chain.decode()))


@patch("utils.secrets.decode_secret_key_with_retry", decode_secret_key)
@patch("events.provider.S3ProviderEvents.ensure_bucket", return_value=False)
def test_provider_when_ensure_bucket_unsuccessful(
    mock_ensure_bucket,
    charm_configuration: dict,
    base_state: State,
    valid_ca_chain: bytes,
) -> None:
    """Check charm behavior when the ensure_bucket operation by s3-integrator is unsuccessful."""
    # Given
    credentials_secret = Secret(
        tracked_content={"access-key": "my-access-key", "secret-key": "my-secret-key"}
    )
    charm_configuration["options"]["bucket"]["default"] = "config-bucket"
    charm_configuration["options"]["credentials"]["default"] = credentials_secret.id

    # This CA chain is valid
    ca_chain_encoded = base64.b64encode(valid_ca_chain).decode()
    charm_configuration["options"]["tls-ca-chain"]["default"] = ca_chain_encoded
    ctx = Context(
        S3IntegratorCharm,
        meta=METADATA,
        config=charm_configuration,
        actions=ACTIONS,
        unit_id=0,
    )

    # Given
    state_in = dataclasses.replace(base_state, secrets=[credentials_secret])

    # When
    state_out = ctx.run(ctx.on.config_changed(), state_in)

    # Then
    assert isinstance(state_out.unit_status, BlockedStatus)
    assert "Could not ensure bucket(s): 'config-bucket'" in state_out.unit_status.message

    relations = list(state_out.relations)
    s3_provider_relation = Relation(
        endpoint="s3-credentials",
        remote_app_data={"bucket": "relation-bucket", "requested-secrets": '["foobar"]'},
    )
    relations.append(s3_provider_relation)

    # Given
    state_in = dataclasses.replace(state_out, relations=relations)

    # When
    state_out = ctx.run(ctx.on.relation_changed(s3_provider_relation), state_in)

    # Then
    provider_data = state_out.get_relation(s3_provider_relation.id).local_app_data
    assert provider_data == {}


@patch("utils.secrets.decode_secret_key_with_retry", decode_secret_key)
@patch("managers.s3.S3Manager.get_bucket", return_value=True)
def test_provider_config_bucket_takes_priority_over_relation_bucket(
    mock_get_bucket,
    charm_configuration: dict,
    base_state: State,
    valid_ca_chain: bytes,
) -> None:
    """Check that bucket requested over the relation takes priority over the one in config."""
    # Given
    credentials_secret = Secret(
        tracked_content={"access-key": "my-access-key", "secret-key": "my-secret-key"}
    )
    charm_configuration["options"]["bucket"]["default"] = "config-bucket"
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
    assert isinstance(state_out.unit_status, ActiveStatus)

    s3_provider_relation = Relation(
        endpoint="s3-credentials",
        remote_app_data={"bucket": "relation-bucket", "requested-secrets": '["foobar"]'},
    )

    # Given
    state_in = dataclasses.replace(state_out, relations=[s3_provider_relation])

    # When
    state_out = ctx.run(ctx.on.relation_changed(s3_provider_relation), state_in)

    # Then
    provider_data = state_out.get_relation(s3_provider_relation.id).local_app_data
    assert provider_data["bucket"] == "config-bucket"
    assert provider_data["access-key"] == "my-access-key"
    assert provider_data["secret-key"] == "my-secret-key"
    assert provider_data["tls-ca-chain"] == json.dumps(parse_ca_chain(valid_ca_chain.decode()))


@patch("utils.secrets.decode_secret_key_with_retry", decode_secret_key)
@patch("managers.s3.S3Manager.get_bucket", return_value=True)
def test_provider_compatibility_with_requirer_v0(
    mock_get_bucket,
    charm_configuration: dict,
    base_state: State,
    valid_ca_chain: bytes,
) -> None:
    """Check that the provider still works when requirer side uses v0 of S3 lib."""
    # Given
    credentials_secret = Secret(
        tracked_content={"access-key": "my-access-key", "secret-key": "my-secret-key"}
    )
    charm_configuration["options"]["bucket"]["default"] = "config-bucket"
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
    assert isinstance(state_out.unit_status, ActiveStatus)

    s3_provider_relation = Relation(
        endpoint="s3-credentials",
        # v0 does not have 'requested-secrets' and also puts a dummy name as 'bucket'
        remote_app_data={"bucket": "relation-17"},
        local_app_data={"lib-version": "1.0"},
    )

    # Given
    state_in = dataclasses.replace(state_out, relations=[s3_provider_relation])

    # When
    state_out = ctx.run(ctx.on.relation_changed(s3_provider_relation), state_in)

    # Then
    provider_data = state_out.get_relation(s3_provider_relation.id).local_app_data
    assert provider_data["bucket"] == "config-bucket"
    assert provider_data["access-key"] == "my-access-key"
    assert provider_data["secret-key"] == "my-secret-key"
    assert provider_data["tls-ca-chain"] == json.dumps(parse_ca_chain(valid_ca_chain.decode()))
