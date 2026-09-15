/*
 ********************************************************************************
 Author  :  Gabriel SURIER
 Update  :  2026-08-10
 Purpose :  SQL QUERY to select all data from all csv files from data/01_raw.
            Work only in rfp_fl001_0200_csv_parquet_data_prep.py
            In a real case, we will use table name instead of a dataframe.
            For this specific case, it's just easier to compile data in-memory
            for the small dataset.
 Details  : Number -1 is used to normalise null value from integer
            Character '#' is used to normalise null value from varchar
            Number 0 on VISITS_NUM is a deliberate choice, not a
            neutral sentinel : it behaves as a real zero in downstream
            sums and rolling averages, so a sensor with missing data
            shows up as an activity drop instead of being silently
            excluded
            TEC_SOURCE_TS   : Extraction date from the source
            TEC_CREATION_TS : Creation date of the line for this dataset
 ********************************************************************************
 */
        SELECT
             date_id AS DATE_ID
            ,sensor_id AS SENSOR_ID
            ,coalesce("hour",-1) AS HOUR_ID
            ,coalesce(door_name,'#') AS DOOR_NAME_DESC
            ,CAST(coalesce(visits_nb,0) AS INTEGER) AS VISITS_NUM
            ,open_date AS OPEN_DT
            ,cast(TEC_CREATION_TS AS TIMESTAMP(0)) AS TEC_SOURCE_TS
            ,current_timestamp::TIMESTAMP(0) AS TEC_CREATION_TS
        FROM visits_df
        WHERE date_id IS NOT NULL
          AND sensor_id IS NOT NULL
