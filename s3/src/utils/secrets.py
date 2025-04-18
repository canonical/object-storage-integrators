# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utility functions related to secrets."""

import logging

from ops import Model
from ops.model import ModelError, SecretNotFoundError

logger = logging.getLogger(__name__)


def decode_secret_key(model: Model, secret_id: str) -> tuple[str, str]:
    """Decode the secret with given secret_id and return the access and secret key in plaintext value.

    Args:
        model: juju model
        secret_id (str): The ID (URI) of the secret that contains the secret key

    Raises:
        ops.model.SecretNotFoundError: When either the secret does not exist or the secret
            does not have the secret-key in its content.
        ops.model.ModelError: When the permission to access the secret has not been granted
            yet.

    Returns:
        tuple[str, str]: The access and secret key in plain text.
    """
    try:
        secret_content = model.get_secret(id=secret_id).get_content(refresh=True)

        if not secret_content.get("access-key"):
            raise ValueError(f"The field 'access-key' was not found in the secret '{secret_id}'.")
        if not secret_content.get("secret-key"):
            raise ValueError(f"The field 'secret-key' was not found in the secret '{secret_id}'.")
        return secret_content["access-key"], secret_content["secret-key"]
    except SecretNotFoundError:
        raise SecretNotFoundError(f"The secret '{secret_id}' does not exist.")
    except ValueError as ve:
        raise SecretNotFoundError(ve)
    except ModelError as me:
        if "permission denied" in str(me):
            raise ModelError(f"Permission for secret '{secret_id}' has not been granted.")
        raise
