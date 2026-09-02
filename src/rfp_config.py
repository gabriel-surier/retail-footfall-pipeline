"""
@File    :   rfp_config.py
@Time    :   2026-08-26
@Author  :   Gabriel SURIER
@Purpose :   S3/MinIO client utilities for the RFP ETL pipeline.
            Provides application settings (via pydantic-settings) and a workspace
            context manager used by all ETL scripts to read/write intermediate
            files, either persisted locally in debug mode or ephemeral in prod.
Update  :   2026-09-01 : rename to rfp_config.py and add etl config for central configuration.
"""

from typing import Any, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
import logging
import tempfile
import boto3


from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger: logging.Logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file.

    Attributes:
        project_root: Absolute path to the project root directory.
        run_id: Identifier isolating the workspace of a single pipeline
            run. Reads AIRFLOW_CTX_DAG_RUN_ID when orchestrated by
            Airflow, falls back to "local" for manual runs.
        file_path_raw_data: Sub-path or prefix used for raw data.
        file_path_inter_data: Sub-path or prefix used for interim data.
        file_path_pro_data: Sub-path or prefix used for processed data.
        debug: Whether debug mode is enabled (persistent workspace, verbose logs).
        data_load_mod: Data load mode (e.g. "DELTA" or "FULL").
        data_load_delta: Number of days to load in delta mode.
        api_base_url: Base URL of the source API.
        minio_root_user: MinIO root username.
        minio_root_password: MinIO root password.
        minio_bucket: Target MinIO bucket name.
        minio_endpoint: MinIO endpoint URL.
        data_load_init_date: Initial date used for full data loads.
    """

    # --- Environment path config ---

    project_root: Path = Path(__file__).resolve().parent.parent
    model_config = SettingsConfigDict(env_file=project_root / ".env")

    # --- Python config ---

    python_version: float

    # --- File path config ---

    file_path_raw_data: str
    file_path_inter_data: str
    file_path_pro_data: str

    # --- Debug config ---

    debug: bool = False

    # --- Data config ---

    data_load_mod: str
    data_load_delta: int
    data_load_init_date: date

    # --- API config ---

    api_base_url: str
    app_port: int
    host_port: int

    # --- minio config ---

    minio_root_user: str
    minio_root_password: str
    minio_bucket: str
    minio_endpoint: str
    environment: str

    # --- Airflow config ---

    run_id: str = Field(default="local", alias="AIRFLOW_CTX_DAG_RUN_ID")
    airflow_version: str
    airflow_port: int
    airflow_user: str
    postgres_password: SecretStr
    postgres_db: str
    airflow_admin_user: str
    airflow_admin_password: SecretStr
    airflow_admin_email: str


settings: Settings = Settings()  # noqa

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@contextmanager
def get_workspace() -> Iterator[Path]:
    """Provide a working directory shared across the tasks of a run.

    In debug mode, creates a persistent directory under the project
    root so files can be inspected manually during development. In
    normal mode, uses a directory under the system temp root, named
    after settings.run_id, shared across all tasks of the same run so
    intermediate files don't need to round-trip through MinIO between
    pipeline steps.

    Yields:
        Path to the shared working directory for this run.
    """
    if settings.environment == "DEV":
        workspace = settings.project_root / "etl" / "tmp"
        logger.info("Development mode active: persistent workspace at %s", workspace)
    else:
        workspace = Path(tempfile.gettempdir()) / "rfp_etl" / settings.run_id
        logger.info("Run %s: shared workspace at %s", settings.run_id, workspace)

    for sub_dir in (
        settings.file_path_raw_data,
        settings.file_path_inter_data,
        settings.file_path_pro_data,
    ):
        (workspace / sub_dir).mkdir(parents=True, exist_ok=True)

    yield workspace


def get_s3_client(s3_settings: Any) -> Any:
    """Create and return a boto3 S3 client configured for MinIO.
    Args:
        s3_settings: Object exposing minio_endpoint, minio_root_user and
            minio_root_password attributes.

    Returns:
        A configured boto3 S3 client.
    """
    return boto3.client(
        "s3",
        endpoint_url=s3_settings.minio_endpoint,
        aws_access_key_id=s3_settings.minio_root_user,
        aws_secret_access_key=s3_settings.minio_root_password,
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
