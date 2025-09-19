# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utility functions related to secrets."""

import logging

from typing import Optional
import ops
from ops.model import ModelError, Model
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    retry=retry_if_exception_type(ModelError),
    reraise=True,
)
def decode_secret_key_with_retry(model: Model, sa_ref: str) -> Optional[str]:
    return _decode_secret_key(model, normalize(sa_ref))


def _decode_secret_key(model: ops.Model, secret_id: str) -> Optional[str]:
    content = model.get_secret(id=secret_id).get_content(refresh=True)
    if "secret-key" not in content:
        raise ops.model.SecretNotFoundError(
            f"The field 'secret-key' was not found in the secret '{secret_id}'."
        )
    return content["secret-key"]

def normalize(secret_uri: str) -> str:
    return secret_uri.split("secret:", 1)[1].strip() if secret_uri.startswith("secret:") else secret_uri

