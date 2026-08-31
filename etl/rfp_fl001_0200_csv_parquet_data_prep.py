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


import pandas as pd
import duckdb

from src.config_s3 import get_s3_client, upload_file
from etl import settings, get_workspace

# ===============================================
# FILE VAR
# ===============================================


INTERIM_FILE_NAME: str = "dwh_fact_visits"
PROCESSED_FILE_NAME: str = "dm_fact_visits"

sql_dir: Path = Path(__file__).resolve().parent / "sqlq"

with get_workspace() as workspace:
    raw_data_dir = workspace / settings.file_path_raw_data
    interim_data_dir = workspace / settings.file_path_inter_data
    processed_data_dir = workspace / settings.file_path_pro_data
    PARQUET_INT_FILE_PATH = interim_data_dir / f"{INTERIM_FILE_NAME}.parquet"
    PARQUET_PRO_FILE_PATH: Path = processed_data_dir / f"{PROCESSED_FILE_NAME}.parquet"


SQL_INT_FILE_PATH: Path = sql_dir / f"{INTERIM_FILE_NAME}.sql"
SQL_PRO_FILE_PATH: Path = sql_dir / f"{PROCESSED_FILE_NAME}.sql"


# ===============================================
# FILE VAR
# ===============================================

# Get S3 client

client = get_s3_client(settings)

# Get all data in one dataframe


csv_files = [str(f) for f in Path(raw_data_dir).glob("*.csv") if f.stat().st_size > 0]

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
    sql_file_path: Path, file_name: str, dir_path: Path, parquet_file_path: Path | None
) -> None:
    """
    Generate a parquet file  with a specific name in a selected file path
    :param file_name: output file name
    :param dir_path: output directory path
    :param sql_file_path: input SQL file path
    :param parquet_file_path: input parquet file path to read SQL data
    :return: None
    """
    with open(sql_file_path, encoding="UTF-8") as file:
        if parquet_file_path:
            sql_query = file.read().replace("?", f"'{parquet_file_path.as_posix()}'")
        else:
            sql_query = file.read()
    df_to_parquet = duckdb.query(sql_query).df()
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


if __name__ == "__main__":
    BUCK_FLOW_NAME: str = "rfp_fl001"
    generate_parquet(SQL_INT_FILE_PATH, INTERIM_FILE_NAME, interim_data_dir, None)
    generate_parquet(
        SQL_PRO_FILE_PATH,
        PROCESSED_FILE_NAME,
        processed_data_dir,
        PARQUET_INT_FILE_PATH,
    )
    upload_file(
        client,
        PARQUET_INT_FILE_PATH,
        settings.minio_bucket,
        f"{BUCK_FLOW_NAME}/{settings.file_path_inter_data}",
    )

    upload_file(
        client,
        processed_data_dir / f"{PROCESSED_FILE_NAME}.parquet",
        settings.minio_bucket,
        f"{BUCK_FLOW_NAME}/{settings.file_path_pro_data}",
    )
