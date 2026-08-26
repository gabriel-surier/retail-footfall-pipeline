"""
@File    :   config_s3.py
@Time    :   2026-08-26
@Author  :   Gabriel SURIER
@Purpose :   S3/MinIO client utilities for the RFP ETL pipeline.
"""

from pathlib import Path
from typing import Any

import boto3


def get_s3_client(settings: Any) -> Any:
    """Create and return a boto3 S3 client configured for MinIO.
    Args:
        settings: Object exposing minio_endpoint, minio_root_user and
            minio_root_password attributes.

    Returns:
        A configured boto3 S3 client.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_root_user,
        aws_secret_access_key=settings.minio_root_password,
    )


def upload_file(client: Any, local_path: Path, bucket: str, prefix: str) -> str:
    """Upload a local file to an S3 bucket under the given prefix.

    Args:
        client: A boto3 S3 client.
        local_path: Path to the local file to upload.
        bucket: Target S3 bucket name.
        prefix: Key prefix under which the file will be stored.

    Returns:
        The full S3 key of the uploaded file.
    """
    key = f"{prefix}/{local_path.name}"
    client.upload_file(str(local_path), bucket, key)
    return key


def download_file(client: Any, bucket: str, key: str, local_path: Path) -> None:
    """Download a file from an S3 bucket to a local path.

    Args:
        client: A boto3 S3 client.
        bucket: Source S3 bucket name.
        key: S3 object key to download.
        local_path: Local destination path.
    """
    client.download_file(bucket, key, str(local_path))


def list_csv_files_s3(client: Any, bucket: str, prefix: str) -> list[str]:
    """List non-empty CSV file keys in an S3 bucket under a given prefix.

    Args:
        client: A boto3 S3 client.
        bucket: S3 bucket name to search.
        prefix: Key prefix to filter objects.

    Returns:
        A list of S3 keys ending in '.csv' with a non-zero size.
    """
    paginator = client.get_paginator("list_objects_v2")
    csv_files: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".csv") and obj["Size"] > 0:
                csv_files.append(key)
    return csv_files
