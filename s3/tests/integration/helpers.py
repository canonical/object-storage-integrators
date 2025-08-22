#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import json
import logging

import boto3
import jubilant
from botocore.exceptions import ClientError, ConnectTimeoutError, ParamValidationError, SSLError

logger = logging.getLogger(__name__)


def get_bucket(s3_info: dict, bucket_name: str):
    """Fetch the bucket with given name from S3 cloud."""
    session = boto3.Session(
        aws_access_key_id=s3_info.get("access-key"),
        aws_secret_access_key=s3_info.get("secret-key"),
    )
    resource = session.resource(
        "s3",
        endpoint_url=s3_info.get("endpoint"),
    )
    bucket = resource.Bucket(bucket_name)
    try:
        resource.meta.client.head_bucket(Bucket=bucket_name)
        return bucket
    except (ClientError, SSLError, ConnectTimeoutError, ParamValidationError) as e:
        logger.error(f"Could not fetch the bucket '{bucket_name}'; Response: {e}")
        return None


def create_bucket(s3_info: dict, bucket_name: str):
    """Fetch the bucket with given name from S3 cloud."""
    session = boto3.Session(
        aws_access_key_id=s3_info.get("access-key"),
        aws_secret_access_key=s3_info.get("secret-key"),
    )
    resource = session.resource(
        "s3",
        endpoint_url=s3_info.get("endpoint"),
    )

    bucket = resource.Bucket(bucket_name)
    create_args = {}
    region = s3_info.get("region")
    if region and region != "us-east-1":
        create_args = {"CreateBucketConfiguration": {"LocationConstraint": s3_info["region"]}}
    try:
        bucket.create(**create_args)
        logger.info(f"Bucket '{bucket_name}' created successfully")
        return bucket
    except (SSLError, ConnectTimeoutError, ClientError, ParamValidationError) as e:
        logger.error(f"Could not create the bucket '{bucket_name}'; Response: {e}")
        return None


def delete_bucket(s3_info: dict, bucket_name: str) -> bool:
    """Delete the bucket with given name from S3 cloud."""
    session = boto3.Session(
        aws_access_key_id=s3_info.get("access-key"),
        aws_secret_access_key=s3_info.get("secret-key"),
    )
    resource = session.resource(
        "s3",
        endpoint_url=s3_info.get("endpoint"),
    )

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
