#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The S3 Manager module that contains manager class and utilities specific to S3 cloud."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, cast

import boto3
from boto3.session import Session
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ParamValidationError,
    SSLError,
)

from core.domain import S3ConnectionInfo
from utils.logging import WithLogging

if TYPE_CHECKING:
    from types_boto3_s3.service_resource import Bucket, S3ServiceResource
else:
    S3ServiceResource = Any


class S3BucketError(Exception):
    """The bucket could not be fetched / created for it to be used."""

    pass


class S3Manager(WithLogging):
    """Manager class for S3 cloud related functions."""

    def __init__(self, conn_info: S3ConnectionInfo) -> None:
        self.conn_info: S3ConnectionInfo = conn_info

    @contextmanager
    def s3_resource(self) -> Generator[S3ServiceResource, None, None]:
        """Yield a boto3 S3 resource, handling TLS CA chain cleanup safely."""
        ca_file: str | None = None
        extra_args: dict[str, object] = {}

        if self.conn_info.get("tls-ca-chain"):
            ca_chain: list[str] = json.loads(self.conn_info["tls-ca-chain"])
            ca_chain_pem: str = "\n".join(ca_chain)
            tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".pem")
            tmp.write(ca_chain_pem)
            tmp.flush()
            tmp.close()
            ca_file = tmp.name

            extra_args["use_ssl"] = True
            extra_args["verify"] = ca_file
        if self.conn_info.get("region"):
            extra_args["region_name"] = self.conn_info.get("region")

        session: Session = boto3.Session(
            aws_access_key_id=self.conn_info.get("access-key"),
            aws_secret_access_key=self.conn_info.get("secret-key"),
        )
        resource = cast(
            S3ServiceResource,
            session.resource(
                service_name="s3",
                endpoint_url=self.conn_info.get("endpoint"),
                **extra_args,
            ),  # type: ignore
        )

        try:
            yield resource
        finally:
            if ca_file and os.path.exists(ca_file):
                os.remove(ca_file)

    def get_bucket(self, bucket_name: str) -> Bucket | None:
        """Fetch the bucket with given name from S3 cloud."""
        with self.s3_resource() as resource:
            bucket: Bucket = resource.Bucket(bucket_name)
            try:
                resource.meta.client.head_bucket(Bucket=bucket_name)
                return bucket
            except (
                ClientError,
                SSLError,
                ConnectTimeoutError,
                ParamValidationError,
                EndpointConnectionError,
            ) as e:
                self.logger.error(f"The bucket '{bucket_name}' can't be fetched; Response: {e}")
                return None

    def create_bucket(self, bucket_name: str, wait_until_exists: bool = True) -> Bucket:
        """Create a bucket with given name in the S3 cloud."""
        with self.s3_resource() as resource:
            bucket: Bucket = resource.Bucket(bucket_name)
            create_args = {}
            region = self.conn_info.get("region")
            if region and region != "us-east-1":
                create_args = {
                    "CreateBucketConfiguration": {"LocationConstraint": self.conn_info["region"]}
                }
            try:
                bucket.create(**create_args)  # type: ignore
                if wait_until_exists:
                    bucket.wait_until_exists()
                return bucket
            except (
                SSLError,
                ConnectTimeoutError,
                ClientError,
                ParamValidationError,
                EndpointConnectionError,
            ) as e:
                self.logger.error(f"Could not create the bucket '{bucket_name}'; Response: {e}")
                raise S3BucketError(
                    f"Could not create bucket '{bucket_name}' using provided configuration"
                )
