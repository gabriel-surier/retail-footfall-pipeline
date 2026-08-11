/*
 ****************************************************************************************
 Author  :   Gabriel SURIER
 Update  :   2026-08-10
 Purpose :   SQL QUERY to create the window function to analyse the
             average evolution of daily visits (ex :we compare only
             the saturdays with saturdays.
             Work only in rfp_002_data_prep.py.
             Replace ? with fact_visits.parquet for testing.
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
