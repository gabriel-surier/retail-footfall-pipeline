/*
 ********************************************************************************
 Author  :  Gabriel SURIER
 Update  :  2026-08-10
 Purpose :  SQL QUERY to select all data from all csv files from data/01_raw.
            Work only in rfp_002_data_prep.py
            In a real case, we will use table name instead of a dataframe.
            For this specific case, it's just easier to compile data in-memory
            for the small dataset.
 ********************************************************************************
 */
        SELECT
             date_id AS DATE_ID
            ,sensor_id  AS SENSOR_ID
            ,coalesce(door_name,'#') AS DOOR_NAME_DESC
            ,coalesce("hour",-1) AS HOUR_NUM
            ,CAST(coalesce(visits_nb,0) AS INTEGER) AS VISITS_NUM
            ,open_date AS OPEN_DT
            ,cast( TEC_CREATION_TS AS TIMESTAMP(0)) AS TEC_SOURCE_TS
            ,current_timestamp::TIMESTAMP(0)  AS TEC_CREATION_TS
        FROM visits_df
        WHERE date_id IS NOT NULL
          AND sensor_ID IS NOT NULL
