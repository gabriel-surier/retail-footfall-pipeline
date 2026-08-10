"""
@File    :   rfp_002_data_prep.py
@Time    :   2020/08/01
@Author  :   Gabriel SURIER
@Purpose :   Prepare the data before inserting into duckdb
             Here we need to analyze all files data to retrieve
             the provoked data quality problems
"""

from pathlib import Path
import os

import pandas as pd
import duckdb

from dotenv import load_dotenv

load_dotenv()

# ===============================================
# ENVIRONMENT VAR
# ===============================================
FILE_PATH_RAW_DATA = os.getenv("FILE_PATH_RAW_DATA")
FILE_PATH_INTER_DATA = os.getenv("FILE_PATH_INTER_DATA")
FILE_PATH_PRO_DATA = os.getenv("FILE_PATH_PRO_DATA")

DEBUG = os.getenv("DEBUG")

DATA_LOAD_MOD = os.getenv("DATA_LOAD_MOD")
# ===============================================
# FILE VAR
# ===============================================

raw_data_dir: str = f"{Path(__file__).resolve().parent}{FILE_PATH_RAW_DATA}"
interim_data_dir: str = f"{Path(__file__).resolve().parent}{FILE_PATH_INTER_DATA}"
processed_data_dir: str = f"{Path(__file__).resolve().parent}{FILE_PATH_PRO_DATA}"

# ===============================================
# DATA PREP VAR
# ===============================================

# Get all data in one dataframe

csv_files = [f for f in Path(raw_data_dir).glob("*.csv") if f.stat().st_size > 0]

# Raise error if no files are found. In reality cases, we will push an e-mail and log it in a table.

if not csv_files:
    raise FileNotFoundError(f"ERROR : No files found in {raw_data_dir}")

visits_df = pd.concat([pd.read_csv(f) for f in csv_files])

# ===============================================
# FUNCTIONS
# ===============================================


def generate_parquet(
    file_name: str, dir_path: str, df_to_parquet: pd.DataFrame
) -> None:
    """
    Generate a parquet file  with a specific name in a selected file path
    :param file_name:
    :param dir_path:
    :param df_to_parquet:
    :return: None
    """

    data_file_path = Path(dir_path) / f"{file_name}.parquet"

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

QUERY_ONE = """
        SELECT
             date_id AS DATE_ID
            ,sensor_id  AS SENSOR_ID
            ,coalesce(door_name,'#') AS DOOR_NAME_DESC
            ,coalesce("hour",-1) AS HOUR_NUM 
            ,CAST(coalesce(visits_nb,0) AS INTEGER) AS VISITS_NUM
            ,strptime(open_date, '%Y-%m-%d') AS OPEN_DT
            ,cast( TEC_CREATION_TS AS TIMESTAMP(0)) AS TEC_SOURCE_TS
            ,current_timestamp::TIMESTAMP(0)  AS TEC_CREATION_TS
        FROM visits_df 
        WHERE date_id IS NOT NULL 
          AND sensor_ID IS NOT NULL      
"""

# We put this in a .parquet file in a processing folder.
# If data volume grow, we switch to Database (like DuckDB or PostgreSQL)
# Here we do a simple "upsert" with a drop duplicate.
# In a real environment we will have a data wharehouse

updt_fact_visits_df = duckdb.query(QUERY_ONE).df()
generate_parquet("fact_visits", interim_data_dir, updt_fact_visits_df)


# This query detect abnormal number of visits

QUERY_TWO = """
WITH daily_analyze AS (
        SELECT
             DATE_ID
            ,SENSOR_ID
            ,OPEN_DT
            ,SUM(VISITS_NUM) AS DAILY_VISITS_NUM
            ,dayname(OPEN_DT) DAY_OF_WEEK
        FROM updt_fact_visits_df 
        GROUP BY DATE_ID,SENSOR_ID,OPEN_DT,DAY_OF_WEEK 
)
   , avg_daily_visits AS (
        SELECT
             DATE_ID
            ,SENSOR_ID
            ,DAY_OF_WEEK
            ,OPEN_DT
            ,DAILY_VISITS_NUM
            , AVG(DAILY_VISITS_NUM) OVER (
            PARTITION BY DAY_OF_WEEK,SENSOR_ID
            ORDER BY OPEN_DT 
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
            ) AS AVG_DAILY_VISITS_NUM
            ,COALESCE(ROUND(
                (DAILY_VISITS_NUM-AVG_DAILY_VISITS_NUM)/COALESCE(AVG_DAILY_VISITS_NUM,1) *100,2
            ) ,0) AS PCT_CHANGE
         FROM daily_analyze   order by OPEN_DT DESC
)  
   , tot_daily_visits AS (
        SELECT 
             DATE_ID
            ,SUM(DAILY_VISITS_NUM) AS TOT_DAILY_VISITS_NUM
            ,SUM(AVG_DAILY_VISITS_NUM) AS TOT_AVG_DAILY_VISITS_NUM
            ,COALESCE(ROUND(  ((TOT_DAILY_VISITS_NUM-TOT_AVG_DAILY_VISITS_NUM)
                                   /COALESCE(TOT_AVG_DAILY_VISITS_NUM,1) *100),2),0) AS TOT_PCT_CHANGE
        FROM avg_daily_visits
        GROUP BY DATE_ID
)
     SELECT 
             avg.DATE_ID
            ,avg.SENSOR_ID
            ,avg.DAY_OF_WEEK
            ,avg.OPEN_DT
            ,avg.DAILY_VISITS_NUM
            ,COALESCE(ROUND(avg.AVG_DAILY_VISITS_NUM),0) AS AVG_DAILY_VISITS_NUM
            ,avg.PCT_CHANGE
            ,tot.TOT_DAILY_VISITS_NUM
            ,COALESCE(ROUND(tot.TOT_AVG_DAILY_VISITS_NUM),0) AS TOT_AVG_DAILY_VISITS_NUM
            ,tot.TOT_PCT_CHANGE
     FROM 
         avg_daily_visits avg 
         LEFT JOIN tot_daily_visits tot on avg.DATE_ID=tot.DATE_ID
         ORDER BY avg.OPEN_DT, avg.SENSOR_ID 

"""

# We put this in a .parquet file in a proceesed folder.

updt_v_fact_visits_df = duckdb.query(QUERY_TWO).df()
generate_parquet("v_fact_visits", processed_data_dir, updt_v_fact_visits_df)
