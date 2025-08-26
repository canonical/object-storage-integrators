#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import base64
import json
import logging
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

import boto3
import jubilant
from botocore.exceptions import ClientError, ConnectTimeoutError, ParamValidationError, SSLError
from domain import S3ConnectionInfo

logger = logging.getLogger(__name__)


@contextmanager
def s3_resource(conn_info: S3ConnectionInfo):
    """Yield a boto3 S3 resource, handling TLS CA chain cleanup safely."""
    ca_file = None
    extra_args = {}

    # Handle TLS CA chain if provided (base64-encoded string)
    if conn_info.tls_ca_chain:
        decoded = base64.b64decode(conn_info.tls_ca_chain).decode("utf-8")
        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".pem")
        tmp.write(decoded)
        tmp.flush()
        tmp.close()
        ca_file = tmp.name

        extra_args["use_ssl"] = True
        extra_args["verify"] = ca_file
    if conn_info.region:
        extra_args["region_name"] = conn_info.region

    session = boto3.Session(
        aws_access_key_id=conn_info.access_key,
        aws_secret_access_key=conn_info.secret_key,
    )
    resource = session.resource(
        "s3",
        endpoint_url=conn_info.endpoint,
        **extra_args,
    )

    try:
        yield resource
    finally:
        if ca_file and os.path.exists(ca_file):
            os.remove(ca_file)


def get_bucket(s3_info: S3ConnectionInfo, bucket_name: str):
    """Fetch the bucket with given name from S3 cloud."""
    with s3_resource(conn_info=s3_info) as resource:
        bucket = resource.Bucket(bucket_name)
        try:
            resource.meta.client.head_bucket(Bucket=bucket_name)
            return bucket
        except (ClientError, SSLError, ConnectTimeoutError, ParamValidationError) as e:
            logger.error(f"Could not fetch the bucket '{bucket_name}'; Response: {e}")
            return None


def create_bucket(s3_info: S3ConnectionInfo, bucket_name: str):
    """Fetch the bucket with given name from S3 cloud."""
    with s3_resource(conn_info=s3_info) as resource:
        bucket = resource.Bucket(bucket_name)
        create_args = {}
        region = s3_info.region
        if region and region != "us-east-1":
            create_args = {"CreateBucketConfiguration": {"LocationConstraint": region}}
        try:
            bucket.create(**create_args)
            bucket.wait_until_exists()
            logger.info(f"Bucket '{bucket_name}' created successfully")
            return bucket
        except (SSLError, ConnectTimeoutError, ClientError, ParamValidationError) as e:
            logger.error(f"Could not create the bucket '{bucket_name}'; Response: {e}")
            return None


def delete_bucket(s3_info: S3ConnectionInfo, bucket_name: str) -> bool:
    """Delete the bucket with given name from S3 cloud."""
    with s3_resource(conn_info=s3_info) as resource:
        bucket = resource.Bucket(bucket_name)
        try:
            # Ensure the bucket is empty before deleting
            bucket.objects.all().delete()
            bucket.delete()
            logger.info(f"Bucket '{bucket_name}' deleted successfully")
            return True
        except (SSLError, ConnectTimeoutError, ClientError, ParamValidationError) as e:
            logger.error(f"Could not delete the bucket '{bucket_name}'; Response: {e}")
            return False


def get_application_data(juju: jubilant.Juju, app_name: str, relation_name: str) -> dict:
    """Retrieves the application data from a specific relation.

    Args:
        juju: The Juju client object used to execute CLI commands.
        app_name: The name of the Juju application.
        relation_name: The name of the relation endpoint to query.

    Returns:
        A dictionary containing the application data for the specified relation.

    Raises:
        ValueError: If no relation data can be found for the specified
            relation endpoint.
    """
    unit_name = f"{app_name}/0"
    command_stdout = juju.cli("show-unit", unit_name, "--format=json")
    result = json.loads(command_stdout)

    relation_data = [
        v for v in result[unit_name]["relation-info"] if v["endpoint"] == relation_name
    ]

    if len(relation_data) == 0:
        raise ValueError(
            f"No relation data could be grabbed on relation with endpoint {relation_name}"
        )

    return {relation["relation-id"]: relation["application-data"] for relation in relation_data}


@contextmanager
def local_tmp_folder(name: str = "tmp"):
    if (tmp_folder := Path.cwd() / name).exists():
        shutil.rmtree(tmp_folder)
    tmp_folder.mkdir()

    yield tmp_folder

    shutil.rmtree(tmp_folder)
