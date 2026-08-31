"""
@File    :   settings_st.py
@Time    :   2020/08/31
@Author  :   Gabriel SURIER
@Purpose :   Move pydentic parameters for dataviz app.
            Add logging
"""

import logging
from datetime import date
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger: logging.Logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Import Settings from .env file with pydantic settings
    """

    project_root: Path = Path(__file__).resolve().parent.parent
    model_config = SettingsConfigDict(env_file=project_root / ".env")

    file_path_pro_data: str = "data/03_processed"
    debug: bool = False
    minio_bucket: str = ""

    # Unused
    file_path_raw_data: str = "01_raw"
    file_path_inter_data: str = "02_interim"
    data_load_mod: str = "DELTA"
    data_load_delta: int = 2
    api_base_url: str = "http://127.0.0.1:8000"
    minio_root_user: str = ""
    minio_root_password: str = ""
    minio_endpoint: str = "http://minio:9000"
    data_load_init_date: date = date(2026, 1, 1)
    environment: str = "DEV"
    python_version: float = 3.12
    app_port: int = 8002
    host_port: int = 8002


settings: Settings = Settings()


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
