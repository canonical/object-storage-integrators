# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""GCS charm configuration validation."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

import ops
from ops.model import SecretNotFoundError, ModelError

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError
from pydantic.functional_validators import field_validator
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.cloud import storage

from utils.secrets import decode_secret_key_with_retry

logger = logging.getLogger(__name__)


class CharmConfigInvalidError(Exception):
    """Configuration is invalid."""

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)


def to_kebab(name: str) -> str:
    """Convert snake_case to kebab-case for config aliases."""
    return name.replace("_", "-")


_ALLOWED_CLASSES = {"STANDARD", "NEARLINE", "COLDLINE", "ARCHIVE"}

# bucket: 3–63 chars, lowercase letters/digits/hyphens,
# must start and end with a letter or digit
_BUCKET_RX = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61})[a-z0-9]$")


class GCSConfig(BaseModel):
    """Basic Config Validation.

    Args:
        bucket (StrictStr): Target GCS bucket. Syntax checks: (3–63, lowercase, digits, hyphens).
        credentials (StrictStr): Juju Secret (id or label) that contains a service-account JSON (validated online).
        storage_class (StrictStr): Optional storage class (STANDARD|NEARLINE|COLDLINE|ARCHIVE).
        path (StrictStr): Optional object prefix <=1024 bytes UTF-8, no NULL, no leading slash (/).
    """

    model_config = ConfigDict(alias_generator=to_kebab)
    bucket: StrictStr = Field(..., description="Target GCS bucket (3–63, lowercase/digits/hyphens)")
    credentials: StrictStr = Field(
        ..., description="Juju secret id/label holding service-account JSON"
    )
    storage_class: Optional[StrictStr] = Field(
        default="", description="GCS class (STANDARD|NEARLINE|COLDLINE|ARCHIVE)"
    )
    path: StrictStr = Field(default="", description="Object prefix inside the bucket")

    @field_validator("bucket")
    @classmethod
    def _bucket_syntax(cls, v: str) -> str:
        if not _BUCKET_RX.fullmatch(v):
            raise ValueError(
                "bucket must be 3–63 characters: lowercase letters, digits, or hyphens; "
                "must start/end with a letter or digit"
            )
        return v

    @field_validator("storage_class")
    @classmethod
    def _storage_class_allowed(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        if v not in _ALLOWED_CLASSES:
            raise ValueError("storage-class must be one of: STANDARD, NEARLINE, COLDLINE, ARCHIVE")
        return v

    @field_validator("path")
    @classmethod
    def _path_rules(cls, v: str) -> str:
        if v == "":
            return v
        if "\x00" in v:
            raise ValueError("path must not contain NULL bytes")
        if len(v.encode("utf-8")) > 1024:
            raise ValueError("path must be ≤ 1024 bytes (UTF-8)")
        if not re.fullmatch(r"[A-Za-z0-9._\-/ ]+", v):
            raise ValueError("path contains unsupported characters (allow letters, digits, . _ - / space)")
        if v.startswith("/"):
            raise ValueError("path must not start with '/'")
        return v


@dataclass
class CharmConfig:
    """Runtime view of validated GCS configuration including advanced validation."""
    bucket: str
    credentials: str
    storage_class: str
    path: str


    def __init__(self, *, gcs_config: GCSConfig):
        """Initialize a new instance of the CharmConfig class.

        Args:
            gcs_config: GCS Integrator configuration.
        """
        self.bucket = gcs_config.bucket
        self.credentials = gcs_config.credentials
        self.storage_class = gcs_config.storage_class
        self.path = gcs_config.path

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "CharmConfig":
        """Build from charm.config, raising aggregated errors on invalid offline config."""
        try:
            return cls(gcs_config=GCSConfig(**dict(charm.model.config.items()))) # type: ignore[arg-type]
        except ValidationError as exc:
            err_fields: list[str] = []
            for err in exc.errors():
                loc = err.get("loc")
                if loc:
                    # collect field names from location
                    err_fields.extend(map(str, loc))
                else:
                    # details can be put in the ctx
                    ctx = err.get("ctx") or {}
                    if "error" in ctx:
                        err_fields.extend(str(ctx["error"]).split())
            err_fields.sort()
            err_field_str = ", ".join(f"'{f}'" for f in err_fields)
            raise CharmConfigInvalidError(
                f"The following configurations are not valid: [{err_field_str}]"
            ) from exc

    def online_validate(self, charm: ops.CharmBase) -> tuple[bool, str]:
        """Run online checks:
        1) Validate the service account JSON by obtaining an OAuth token (WhoAmI).
        2) Validate the bucket by fetching metadata with devstorage.read_only.

        Returns:
            (ok, message): True if both checks pass, else False and a reason.
        """
        try:
            secret_ref = charm.model.config.get("credentials").strip()
            plaintext = decode_secret_key_with_retry(charm.model, secret_ref)
        except SecretNotFoundError:
            return False, "waiting for secret grant: service-account-json-secret"
        except Exception as e:
            return False, f"invalid service-account secret: {e}"

        # Token Validation (WhoAmI)
        try:
            creds = service_account.Credentials.from_service_account_info(
                plaintext, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            creds.refresh(Request())
            r = requests.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"access_token": creds.token},
                timeout=10,
            )
            r.raise_for_status()
        except Exception as e:
            return False, f"service account validation failed: {e}"

        # Validate Bucket existence
        try:
            ro_creds = service_account.Credentials.from_service_account_info(
                plaintext, scopes=["https://www.googleapis.com/auth/devstorage.read_only"]
            )
            ro_creds.refresh(Request())
            client = storage.Client(project=plaintext.get("project_id"), credentials=ro_creds)
            client.get_bucket(self.bucket)
        except Exception as e:
            return False, f"bucket validation failed: {e}"

        return True, "gcs config valid"
