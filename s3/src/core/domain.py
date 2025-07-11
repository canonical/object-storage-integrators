#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Definition of various model classes."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
from typing import Annotated, Literal, TypedDict

from charms.data_platform_libs.v0.data_models import BaseConfigModel
from pydantic import BeforeValidator, Field, field_validator

S3ConnectionInfo = TypedDict(
    "S3ConnectionInfo",
    {
        "access-key": str,
        "secret-key": str,
        "region": str,
        "storage-class": str,
        "attributes": str,
        "bucket": str,
        "endpoint": str,
        "path": str,
        "s3-api-version": str,
        "s3-uri-style": str,
        "tls-ca-chain": str,
        "delete-older-than-days": str,
    },
    total=False,
)
SECRET_REGEX = re.compile("secret:[a-z0-9]{20}")
# Should cover most of the naming rules
# https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html#general-purpose-bucket-names
# Also allows empty string with |^$
BUCKET_REGEX = re.compile(r"(?!(^xn--|.+-s3alias$))^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$|^$")

logger = logging.getLogger(__name__)


def nullify_empty_string(in_str: str) -> str | None:
    """Replace empty str with None."""
    if not in_str:
        return None
    return in_str


def parse_ca_chain(ca_chain_pem: str) -> list[str]:
    """Returns list of certificates based on a PEM CA Chain file.

    Args:
        ca_chain_pem (str): String containing list of certificates.
        This string should look like:
            -----BEGIN CERTIFICATE-----
            <cert 1>
            -----END CERTIFICATE-----
            -----BEGIN CERTIFICATE-----
            <cert 2>
            -----END CERTIFICATE-----

    Returns:
        list: List of certificates
    """
    chain_list = re.findall(
        pattern="(?=-----BEGIN CERTIFICATE-----)(.*?)(?<=-----END CERTIFICATE-----)",
        string=ca_chain_pem,
        flags=re.DOTALL,
    )
    if not chain_list:
        raise ValueError("No certificate found in chain file")
    return chain_list


class CharmConfig(BaseConfigModel):
    """Manager for the structured configuration."""

    endpoint: Annotated[str | None, BeforeValidator(nullify_empty_string)]
    bucket: Annotated[str | None, BeforeValidator(nullify_empty_string)] = Field(
        None, pattern=BUCKET_REGEX
    )
    region: Annotated[str | None, BeforeValidator(nullify_empty_string)]
    path: Annotated[str | None, BeforeValidator(nullify_empty_string)]
    attributes: Annotated[str | None, BeforeValidator(nullify_empty_string)]
    s3_uri_style: Annotated[str | None, BeforeValidator(nullify_empty_string)] = Field(
        alias="s3-uri-style",
    )
    storage_class: Annotated[str | None, BeforeValidator(nullify_empty_string)] = Field(
        alias="storage-class"
    )
    # TODO(tls): validate ca chain format
    tls_ca_chain: Annotated[str | None, BeforeValidator(nullify_empty_string)] = Field(
        alias="tls-ca-chain"
    )
    s3_api_version: Annotated[Literal["2", "4", None], BeforeValidator(nullify_empty_string)] = (
        Field(
            None,
            alias="s3-api-version",
        )
    )
    experimental_delete_older_than_days: int | None = Field(
        None,
        alias="experimental-delete-older-than-days",
        gt=0,
        le=9999999,
        serialization_alias="delete-older-than-days",
    )
    credentials: str = Field(pattern=SECRET_REGEX, exclude=True)

    @field_validator("tls_ca_chain")
    @classmethod
    def validate_tls_ca_chain(cls, value: str) -> str | None:
        if value is None:
            return None
        try:
            decoded_value = base64.b64decode(value).decode("utf-8")
        except (TypeError, binascii.Error) as e:
            raise ValueError("The given TLS CA chain is not a valid base64 encoded string")

        chain_list = parse_ca_chain(decoded_value)
        return json.dumps(chain_list)
