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


data_dir = f"{Path(__file__).resolve().parent}/data/raw"

print(data_dir)

visits_df = pd.concat([pd.read_csv(csv_file) for csv_file in Path(data_dir).glob("*.csv")])
#This query detect abnormal number of visits
data_quality_query_one = '''
WITH VISITS_QUALITY AS (
        SELECT
             date_id AS DATE_ID
            ,sensor_id  AS SENSOR_ID
            ,coalesce(door_name,'#') AS DOOR_NAME_DESC
            ,coalesce("hour",-1) AS HOUR_NUM 
            ,CAST(coalesce(visits_nb,0) AS INTEGER) AS VISITS_NUM
            ,open_date AS OPEN_DT            
        FROM visits_df 
        WHERE date_id IS NOT NULL 
          AND sensor_ID IS NOT NULL
)       SELECT * FROM VISITS_QUALITY WHERE VISITS_NUM <10 and VISITS_NUM > 0

'''

#This query detect abnormal number of visits
data_quality_query_two = '''
'''

data_quality_df = duckdb.query(data_quality_query_one)

print(data_quality_df)
daily_visits_query = '''
WITH VISITS_QUALITY AS (
        SELECT
             date_id AS DATE_ID
            ,sensor_id  AS SENSOR_ID
            ,coalesce(door_name,'#') AS DOOR_NAME_DESC
            ,coalesce("hour",-1) AS HOUR_NUM 
            ,CAST(coalesce(visits_nb,0) AS INTEGER) AS VISITS_NUM
            ,open_date AS OPEN_DT            
        FROM visits_df 
        WHERE date_id IS NOT NULL 
          AND sensor_ID IS NOT NULL
)
        SELECT 
             DATE_ID
            ,sum(VISITS_NUM) AS DAILY_VISITS_NUM
            ,OPEN_DT
        FROM VISITS_QUALITY
        GROUP BY DATE_ID,OPEN_DT
        ORDER BY DATE_ID
'''

daily_visits_df = duckdb.query(daily_visits_query)

#print(daily_visits_df)