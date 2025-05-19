# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utility functions related to secrets."""

import logging

import ops
import ops.charm
import ops.framework
import ops.lib
import ops.main
import ops.model

logger = logging.getLogger(__name__)


def decode_secret(model: ops.Model, secret_id: str) -> dict:
    """Decode the secret with given secret_id and return the content as dictionary.

    Args:
        model: juju model
        secret_id (str): The ID (URI) of the secret that contains the secret key

    Raises:
        ops.model.SecretNotFoundError: When either the secret does not exist or the secret
            does not have the secret-key in its content.
        ops.model.ModelError: When the permission to access the secret has not been granted
            yet.

    Returns:
        dict: The content of the secret as a dictionary.
    """
    try:
        return model.get_secret(id=secret_id).get_content(refresh=True)
    except ops.model.SecretNotFoundError:
        raise ops.model.SecretNotFoundError(f"The secret '{secret_id}' does not exist.")
    except ValueError as ve:
        raise ops.model.SecretNotFoundError(ve)
    except ops.model.ModelError as me:
        if "permission denied" in str(me):
            raise ops.model.ModelError(
                f"Permission for secret '{secret_id}' has not been granted."
            )
        raise
