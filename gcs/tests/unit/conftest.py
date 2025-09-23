# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from ops.testing import Context, State

from src.charm import GCStorageIntegratorCharm

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
CONFIG_SCHEMA = yaml.safe_load(Path("./config.yaml").read_text())
ACTIONS = yaml.safe_load(Path("./actions.yaml").read_text())

REL_NAME = "gcs-credentials"

FAKE_SA = {
    "type": "service_account",
    "project_id": "test-proj",
    "private_key_id": "abc",
    "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
    "client_email": "sa@test.iam.gserviceaccount.com",
    "token_uri": "https://oauth2.googleapis.com/token",
}


@pytest.fixture
def base_state() -> State:
    return State()


@pytest.fixture
def charm_config() -> dict:
    # this is the SCHEMA (has 'options')
    return deepcopy(CONFIG_SCHEMA)


@pytest.fixture
def metadata():
    # Context expects actions under top-level "actions"
    return deepcopy(METADATA)


@pytest.fixture
def actions() -> dict:
    return deepcopy(ACTIONS)


@pytest.fixture
def rel_name() -> str:
    return REL_NAME


@pytest.fixture
def fake_sa() -> dict:
    return deepcopy(FAKE_SA)


def _mk_ctx(meta, actions, cfg_schema, unit_id=0):
    return Context(
        GCStorageIntegratorCharm,
        meta=meta,
        config=cfg_schema,
        actions=actions,
        unit_id=unit_id,
    )


@pytest.fixture
def mk_ctx():
    return _mk_ctx
