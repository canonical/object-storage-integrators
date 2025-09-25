# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utility functions related to secrets."""

from ops.model import Model, ModelError, SecretNotFoundError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed


class SecretDoesNotExistError(SecretNotFoundError):
    """The secret does not exist in Juju model."""

    def __init__(self, message: str, secret_id: str):
        super().__init__(message)
        self.secret_id = secret_id


class SecretFieldMissingError(ValueError):
    """A mandatory field is missing in the secret content."""

    def __init__(self, message: str, secret_id: str, missing_fields: list[str]):
        super().__init__(message)
        self.secret_id = secret_id
        self.missing_fields = missing_fields


class SecretNotGrantedError(ModelError):
    """The secret has not been granted to the charm."""

    def __init__(self, message: str, secret_id: str):
        super().__init__(message)
        self.secret_id = secret_id


class SecretDecodeError(ModelError):
    """The secret could not be decoded from the Secret ID."""

    def __init__(self, message: str, secret_id: str):
        super().__init__(message)
        self.secret_id = secret_id


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    retry=retry_if_exception_type(SecretNotGrantedError),
    reraise=True,
)
def decode_secret_key_with_retry(model: Model, secret_id: str):
    """Try to decode the secret key, retry for 3 times before failing."""
    return decode_secret_key(model, secret_id)


def normalize(secret_uri: str) -> str:
    """Normalize the secret URI."""
    return (
        secret_uri.split("secret:", 1)[1].strip()
        if secret_uri.startswith("secret:")
        else secret_uri
    )


def decode_secret_key(model: Model, secret_id: str) -> str:
    """Decode the secret with given secret_id and return the access and secret key in plaintext value.

    Args:
        model: juju model
        secret_id (str): The ID (URI) of the secret that contains the secret key

    Raises:
        SecretDoesNotExistError: When either the secret does not exist
        SecretFieldMissingError: When the secret does not have required fields in its content.
        SecretNotGrantedError: When the secret has not been granted to the charm.
        SecretDecodeError: When decoding the secret fails due to some reason different from above.

    Returns:
        str: The secret key in plain text.
    """
    try:
        secret_content = model.get_secret(id=secret_id).get_content(refresh=True)

        missing_fields = []
        if not secret_content.get("secret-key"):
            missing_fields.append("secret-key")

        if missing_fields:
            raise SecretFieldMissingError(
                f"Some required fields are missing in the secret '{secret_id}'.",
                secret_id=secret_id,
                missing_fields=missing_fields,
            )

        return secret_content["secret-key"]
    except SecretFieldMissingError:
        raise
    except (SecretNotFoundError, ValueError):
        raise SecretDoesNotExistError(
            f"The secret '{secret_id}' does not exist.", secret_id=secret_id
        )
    except ModelError as me:
        if "permission denied" in str(me):
            raise SecretNotGrantedError(
                f"Permission for secret '{secret_id}' has not been granted.", secret_id=secret_id
            )
        raise SecretDecodeError(f"Could not decode secret '{secret_id}'.", secret_id=secret_id)
    except Exception:
        raise SecretDecodeError(f"Could not decode secret '{secret_id}'.", secret_id=secret_id)
