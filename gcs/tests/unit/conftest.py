# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from copy import deepcopy
from pathlib import Path
import pytest
import yaml
from ops.testing import State


METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
CONFIG = yaml.safe_load(Path("./config.yaml").read_text())

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
def charm_configuration() -> dict:
    return deepcopy(CONFIG)

@pytest.fixture
def metadata() -> dict:
    return METADATA


@pytest.fixture
def rel_name() -> str:
    return REL_NAME

@pytest.fixture
def fake_sa() -> dict:
    return deepcopy(FAKE_SA)
