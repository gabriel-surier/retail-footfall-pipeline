"""
@File    :   rfp_002_data_prep.py
@Time    :   2026-08-01
@Author  :   Gabriel SURIER
@Purpose :   Prepare the data before inserting into duckdb
             Here we need to analyze all files data to retrieve
             the provoked data quality problems
@Refacto :  2026-08-26 :
            - renaming rfp_fl001_0200_csv_parquet_extract_data.py to respect the new
            data convention
            - modify pydantic implementation
            - switching to minio S3 to separate data ETL and visualization
"""

from pathlib import Path
from datetime import date

import pandas as pd
import duckdb

from pydantic_settings import BaseSettings, SettingsConfigDict
from etl.rfp_fl001_9999_config_s3 import get_s3_client, upload_file, list_csv_files_s3



# ===============================================
# ENVIRONMENT VAR
# ===============================================
class Settings(BaseSettings):
    """
    Import Settings from .env file with pydantic settings
    """

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env"
    )

    file_path_raw_data: Path = Path("data/01_raw")
    file_path_inter_data: Path = Path("data/02_interim")
    file_path_pro_data: Path = Path("data/03_processed")
    debug: bool = False
    data_load_mod: str = "DELTA"
    data_load_delta: int = 2
    api_base_url: str = "http://127.0.0.1:8000"
    minio_root_user: str = ""
    minio_root_password: str = ""
    minio_bucket: str = ""
    minio_endpoint: str = "http://minio:9000"
    data_load_init_date: date = date(2026, 1, 1)


settings = Settings()


# ===============================================
# FILE VAR
# ===============================================

raw_data_dir: Path = Path(__file__).resolve().parent / settings.file_path_raw_data

interim_data_dir: Path = Path(__file__).resolve().parent / settings.file_path_inter_data
processed_data_dir: Path = Path(__file__).resolve().parent / settings.file_path_pro_data
sql_dir: Path = Path(__file__).resolve().parent / "sqlq"


INTERIM_FILE_NAME: str = "dwh_fact_visits"
PROCESSED_FILE_NAME: str = "dm_fact_visits"

SQL_INT_FILE_PATH: Path = sql_dir / f"{INTERIM_FILE_NAME}.sql"
SQL_PRO_FILE_PATH: Path = sql_dir / f"{PROCESSED_FILE_NAME}.sql"

PARQUET_INT_FILE_PATH: Path = (
    settings.file_path_inter_data / f"{INTERIM_FILE_NAME}.parquet"
)
PARQUET_PRO_FILE_PATH: Path = (
    settings.file_path_pro_data / f"{PROCESSED_FILE_NAME}.parquet"
)


# ===============================================
# FILE VAR
# ===============================================

# Get S3 client

client = get_s3_client(settings)

# Get all data in one dataframe

csv_files = list_csv_files_s3(
    client, settings.minio_bucket, settings.file_path_raw_data
)
# csv_files = [str(f) for f in Path(raw_data_dir).glob("*.csv") if f.stat().st_size > 0]

# Raise error if no files are found. In reality cases, we will push an e-mail and log it in a table.

if not csv_files:
    raise FileNotFoundError(f"ERROR : No files found in {raw_data_dir}")

# Load all csv in a dataframe : visits_df, uses in dwh_fact_visits.sql.
visits_df = duckdb.execute(
    "SELECT * FROM read_csv(?, union_by_name=true)", [csv_files]
).df()


# ===============================================
# FUNCTIONS
# ===============================================


def generate_parquet(
    file_name: str, dir_path: Path, df_to_parquet: pd.DataFrame
) -> None:
    """
    Generate a parquet file  with a specific name in a selected file path
    :param file_name:
    :param dir_path:
    :param df_to_parquet:
    :return: None
    """

    data_file_path: Path = Path(dir_path) / f"{file_name}.parquet"

    # 2026-08-24: Fix output data by correcting hour concatenation
    if file_name[:2] == "dm":
        pandas_subset = ["DATE_ID", "SENSOR_ID"]
    else:
        pandas_subset = ["DATE_ID", "SENSOR_ID", "HOUR_NUM"]

    if data_file_path.exists():
        f_df = pd.read_parquet(data_file_path)

        updt_f_df = pd.concat([f_df, df_to_parquet], ignore_index=True).drop_duplicates(
            subset=pandas_subset, keep="last"
        )

        updt_f_df.to_parquet(data_file_path)
    else:
        df_to_parquet.to_parquet(data_file_path)
        updt_f_df = df_to_parquet
    # Check date formats
    if settings.debug:
        print(
            f"File correctly write in : \n{data_file_path}\n\nVerify date format :"
            f" \n\n{updt_f_df.head(10)} \n"
        )


# ===============================================
# MAIN CODE
# ===============================================


# This query harmonize all data to do all the calculations
# Reference : sqlq/dwh_fact_visits.sql


with open(SQL_INT_FILE_PATH, encoding="UTF-8") as file:
    QUERY_ONE = file.read()
    file.close()

# We put this in a .parquet file in a processing folder.

updt_dwh_fact_visits_df = duckdb.query(QUERY_ONE).df()
generate_parquet(INTERIM_FILE_NAME, interim_data_dir, updt_dwh_fact_visits_df)
upload_file(
    client, PARQUET_INT_FILE_PATH, settings.minio_bucket, settings.file_path_inter_data
)

# This query detect abnormal number of visits
# Reference : sqlq/dm_fact_visits.sql
# We can put parquet file or updt_dwh_fact_visits_df,
# With big dataset I prefer the parquet for performance.


with open(SQL_PRO_FILE_PATH, encoding="UTF-8") as file:
    QUERY_TWO = file.read()

if __name__ == "__main__":
    query_two_filled = QUERY_TWO.replace("?", f"'{PARQUET_INT_FILE_PATH.as_posix()}'")
    updt_dm_fact_visits_df = duckdb.sql(query_two_filled).df()
    generate_parquet(PROCESSED_FILE_NAME, processed_data_dir, updt_dm_fact_visits_df)
    upload_file(
        client,
        PARQUET_PRO_FILE_PATH,
        settings.minio_bucket,
        settings.file_path_pro_data,
    )
