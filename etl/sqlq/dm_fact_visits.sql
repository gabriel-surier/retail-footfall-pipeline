/*
 ****************************************************************************************
 Author  :   Gabriel SURIER
 Update  :   2026-08-10
 Purpose :   SQL QUERY to create the window function to analyse the
             average evolution of daily visits (ex :we compare only
             the saturdays with saturdays.
             Work only in rfp_fl001_0200_csv_parquet_data_prep.py
 ****************************************************************************************
 */
WITH daily_analyze AS (
        SELECT
             DATE_ID
            ,SENSOR_ID
            ,OPEN_DT
            ,SUM(VISITS_NUM) AS DAILY_VISITS_NUM
            ,dayname(OPEN_DT) DAY_OF_WEEK
        FROM read_parquet(?)
        GROUP BY DATE_ID,SENSOR_ID,OPEN_DT,DAY_OF_WEEK
)
   , avg_daily_visits AS (
        SELECT
             DATE_ID
            ,SENSOR_ID
            ,DAY_OF_WEEK
            ,OPEN_DT
            ,DAILY_VISITS_NUM
            -- ROWS framing assumes fixed sensors with continuous daily data.
            -- A sensor with data gaps would silently skew the rolling window.
            ,AVG(DAILY_VISITS_NUM) OVER (
                PARTITION BY DAY_OF_WEEK,SENSOR_ID
                ORDER BY OPEN_DT
                ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
            ) AS AVG_DAILY_VISITS_NUM
            -- NULL baseline or a real 0 baseline both return NULL,
            -- never a fake "no change" result.
            ,CASE WHEN AVG(DAILY_VISITS_NUM) OVER (
                    PARTITION BY DAY_OF_WEEK,SENSOR_ID
                    ORDER BY OPEN_DT
                    ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
                 ) > 0
                THEN ROUND((DAILY_VISITS_NUM-AVG_DAILY_VISITS_NUM)/AVG_DAILY_VISITS_NUM*100,2)
                ELSE NULL
             END AS PCT_CHANGE_NUM
         FROM daily_analyze
)
   , tot_daily_visits AS (
        SELECT
             DATE_ID
            ,SUM(DAILY_VISITS_NUM) AS TOT_DAILY_VISITS_NUM
            -- Sum of per sensor averages, valid only while sensors
            -- stay fixed and share the same date history.
            ,SUM(AVG_DAILY_VISITS_NUM) AS TOT_AVG_DAILY_VISITS_NUM
        FROM avg_daily_visits
        GROUP BY DATE_ID
)
   , tot_pct_visits AS (
        SELECT
             DATE_ID
            ,TOT_DAILY_VISITS_NUM
            ,TOT_AVG_DAILY_VISITS_NUM
            -- NULL baseline or a real 0 baseline both return NULL,
            -- never a fake "no change" result.
            ,CASE WHEN TOT_AVG_DAILY_VISITS_NUM > 0
                THEN ROUND((TOT_DAILY_VISITS_NUM-TOT_AVG_DAILY_VISITS_NUM)/TOT_AVG_DAILY_VISITS_NUM*100,2)
                ELSE NULL
             END AS TOT_PCT_CHANGE_NUM
        FROM tot_daily_visits
)
     SELECT
             adv.DATE_ID
            ,adv.SENSOR_ID
            ,adv.DAY_OF_WEEK
            ,adv.OPEN_DT
            ,adv.DAILY_VISITS_NUM
            ,COALESCE(ROUND(adv.AVG_DAILY_VISITS_NUM),0) AS AVG_DAILY_VISITS_NUM
            ,adv.PCT_CHANGE_NUM
            ,tot.TOT_DAILY_VISITS_NUM
            ,COALESCE(ROUND(tot.TOT_AVG_DAILY_VISITS_NUM),0) AS TOT_AVG_DAILY_VISITS_NUM
            ,tot.TOT_PCT_CHANGE_NUM
     FROM
         avg_daily_visits adv
         LEFT JOIN tot_pct_visits tot ON adv.DATE_ID=tot.DATE_ID
         ORDER BY adv.OPEN_DT, adv.SENSOR_ID