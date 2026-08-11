"""
@File    :   rfp_002_data_prep.py
@Time    :   2020/08/01
@Author  :   Gabriel SURIER
@Purpose :   Prepare the data before inserting into duckdb
             Here we need to analyze all files data to retrieve
             the provoked data quality problems
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
import pandas as pd
import duckdb

from dotenv import load_dotenv

load_dotenv()


# ===============================================
# ENVIRONMENT VAR
# ===============================================
class Settings(BaseSettings):
    """
    Import Settings from .env file with pydantic settings
    """

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parent / ".env")

    file_path_raw_data: str = "01_raw"
    file_path_inter_data: str = "02_interim"
    file_path_pro_data: str = "03_processed"
    debug: bool = False
    data_load_mod: str = "INIT"


settings = Settings()

print(settings.file_path_raw_data)
FILE_PATH_RAW_DATA: str = settings.file_path_raw_data
FILE_PATH_INTER_DATA: str = settings.file_path_inter_data
FILE_PATH_PRO_DATA: str = settings.file_path_pro_data
DEBUG: bool = settings.debug
DATA_LOAD_MOD: str = settings.data_load_mod

# ===============================================
# FILE VAR
# ===============================================

raw_data_dir: Path = Path(__file__).resolve().parent / FILE_PATH_RAW_DATA
interim_data_dir: Path = Path(__file__).resolve().parent / FILE_PATH_INTER_DATA
processed_data_dir: Path = Path(__file__).resolve().parent / FILE_PATH_PRO_DATA
sql_dir: Path = Path(__file__).resolve().parent / "sqlq"
INTERIM_FILE_NAME: str = "dwh_fact_visits"
PROCESSED_FILE_NAME: str = "dm_fact_visits"

# ===============================================
# DATA PREP VAR
# ===============================================

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

    if data_file_path.exists():
        f_df = pd.read_parquet(data_file_path)
        updt_f_df = pd.concat([f_df, df_to_parquet], ignore_index=True).drop_duplicates(
            subset=["DATE_ID", "SENSOR_ID"], keep="last"
        )

        updt_f_df.to_parquet(data_file_path)
    else:
        df_to_parquet.to_parquet(data_file_path)
        updt_f_df = df_to_parquet
    # Check date formats
    if DEBUG:
        print(
            f"File correctly write in : \n{data_file_path}\n\nVerify date format :"
            f" \n\n{updt_f_df.head(10)} \n"
        )


# ===============================================
# MAIN CODE
# ===============================================


# This query harmonize all data to do all the calculations
# Reference : sqlq/dwh_fact_visits.sql

with open(f"{sql_dir}/{INTERIM_FILE_NAME}.sql", encoding="UTF-8") as file:
    QUERY_ONE = file.read()
    file.close()

# We put this in a .parquet file in a processing folder.

updt_dwh_fact_visits_df = duckdb.query(QUERY_ONE).df()
generate_parquet(INTERIM_FILE_NAME, interim_data_dir, updt_dwh_fact_visits_df)


# This query detect abnormal number of visits
# Reference : sqlq/dm_fact_visits.sql
# We can put parquet file or updt_dwh_fact_visits_df,
# With big dataset I prefer the parquet for performance.


with open(f"{sql_dir}/{PROCESSED_FILE_NAME}.sql", encoding="UTF-8") as file:
    QUERY_TWO = file.read()
    file.close()
PARQUET_FILE_PATH: str = f"{interim_data_dir}/{INTERIM_FILE_NAME}.parquet"


# We put this in a .parquet file in a proceesed folder.

updt_dm_fact_visits_df = duckdb.execute(QUERY_TWO, [PARQUET_FILE_PATH]).df()
generate_parquet(PROCESSED_FILE_NAME, processed_data_dir, updt_dm_fact_visits_df)
