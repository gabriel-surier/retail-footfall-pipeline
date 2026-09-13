/*
 ********************************************************************************
 Author  :  Gabriel SURIER
 Update  :  2026-09-13
 Purpose :  SQL QUERY to select datas from the fact datamart.
            The 4-week rolling daily average is pre-computed upstream by a window
            function; this query only maps sensor IDs to door names and drops the
            warm-up period before that rolling average is stable.
            In a IT structure, we use dimensions table instead the case when.
 ********************************************************************************
 */

SELECT
     DATE_ID
    ,SENSOR_ID
    ,CASE WHEN SENSOR_ID=1 THEN 'north'
          WHEN SENSOR_ID=2 THEN 'south'
          WHEN SENSOR_ID=3 THEN 'east'
          ELSE 'west'
     END AS DOOR_NAME_DESC
    ,DAY_OF_WEEK
    ,OPEN_DT
    ,DAILY_VISITS_NUM
    ,AVG_DAILY_VISITS_NUM
    ,PCT_CHANGE_NUM
    ,TOT_DAILY_VISITS_NUM
    ,TOT_AVG_DAILY_VISITS_NUM
    ,TOT_PCT_CHANGE_NUM
FROM read_parquet(?)
-- We need 4 weeks to have good analyzes from
-- window function
WHERE date_trunc('week', OPEN_DT) > (
    SELECT date_trunc('week', MIN(OPEN_DT)) + INTERVAL 4 WEEK
    FROM read_parquet(?)
)
ORDER BY DATE_ID DESC
