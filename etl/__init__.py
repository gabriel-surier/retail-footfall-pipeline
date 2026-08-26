"""
@File    :   __init__.py
@Time    :   2026-08-26
@Author  :   Gabriel SURIER
@Purpose :  Provides application settings (via pydantic-settings) and a workspace
            context manager used by all ETL scripts to read/write intermediate
            files, either persisted locally in debug mode or ephemeral in prod.
"""

import logging
import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

from pydantic import Field
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

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env"
    )

    project_root: Path = Path(__file__).resolve().parent.parent
    run_id: str = Field(default="local", alias="AIRFLOW_CTX_DAG_RUN_ID")

    file_path_raw_data: str = "01_raw"
    file_path_inter_data: str = "02_interim"
    file_path_pro_data: str = "03_processed"
    debug: bool = False
    data_load_mod: str = "DELTA"
    data_load_delta: int = 2
    api_base_url: str = "http://127.0.0.1:8000"
    minio_root_user: str = ""
    minio_root_password: str = ""
    minio_bucket: str = ""
    minio_endpoint: str = "http://minio:9000"
    data_load_init_date: date = date(2026, 1, 1)
    environment: str = "DEV"

settings: Settings = Settings()

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
    if settings.environment=="DEV":
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