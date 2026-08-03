"""
@File    :   rfp_002_data_prep.py
@Time    :   2020/08/01
@Author  :   Gabriel SURIER
@Purpose :   Prepare the data before inserting into duckdb
             Here we need to analyze all files data to retrieve
             the provoked data quality problems
"""


from pathlib import Path
import pandas as pd
import duckdb
import os
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


# This query harmonize all data to do all the calculations

data_quality_query_one = '''
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
'''

# We put this in a .parquet file in a processing folder.
# If data volume grow, we switch to Database (like DuckDB or PostgreSQL)
# Here we do a simple "upsert" with a drop duplicate.
# In a real environment we will have a data wharehouse

parquet_files: list= [parquet_file for parquet_file in Path(interim_data_dir).glob("*.parquet")]
new_interim_df = duckdb.query(data_quality_query_one).df()
fact_visits_file=f"{interim_data_dir}/fact_visits.parquet"

if  fact_visits_file in parquet_files:
    fact_visits_df = pd.read_parquet(fact_visits_file)
    updt_fact_visits_df = pd.concat([fact_visits_df, new_interim_df], ignore_index=True)
    updt_fact_visits_df.drop_duplicates()
    updt_fact_visits_df.to_parquet(fact_visits_file)
else:
    new_interim_df.to_parquet(fact_visits_file)
    updt_fact_visits_df=new_interim_df
# Check date formats
if DEBUG:
    print(updt_fact_visits_df.head())


#This query detect abnormal number of visits

data_quality_query_two ='''
WITH daily_analyze AS (
        SELECT
             DATE_ID
            ,SENSOR_ID
            ,OPEN_DT
            ,SUM(VISITS_NUM) AS DAILY_VISITS_NUM
            ,dayname(OPEN_DT) DAY_OF_WEEK
        FROM updt_fact_visits_df 
        GROUP BY DATE_ID,SENSOR_ID,OPEN_DT,DAY_OF_WEEK 
), avg_daily_visits AS (
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
            ,ROUND(ABS((AVG_DAILY_VISITS_NUM-DAILY_VISITS_NUM)/DAILY_VISITS_NUM) *100,2) PCT_CHANGE
         FROM daily_analyze   
)  
     SELECT * FROM avg_daily_visits  order by OPEN_DT DESC

'''


# We put this in a .parquet file in a proceesed folder.


proc_parquet_files: list= [pf for pf in Path(processed_data_dir).glob("*.parquet")]
new_processed_df = duckdb.query(data_quality_query_two).df()
v_fact_visits_file=f"{processed_data_dir}/v_fact_visits.parquet"

if  v_fact_visits_file in proc_parquet_files:
    v_fact_visits_df = pd.read_parquet(v_fact_visits_file)
    updt_fact_visits_df = pd.concat([v_fact_visits_df, new_processed_df], ignore_index=True)
    updt_fact_visits_df.drop_duplicates()
    updt_fact_visits_df.to_parquet(v_fact_visits_file)
else:
    new_processed_df.to_parquet(v_fact_visits_file)
    updt_fact_visits_df=new_processed_df
# Check date formats
if DEBUG:
    print(updt_fact_visits_df.head())

