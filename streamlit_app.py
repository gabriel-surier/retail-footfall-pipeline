"""
@File    :   streamlit_app.py
@Time    :   2020/08/11
@Author  :   Gabriel SURIER
@Purpose :   Streamlit dashboard visualizing daily store
             visits, built with DuckDB and pandas.
"""

# ===============================================
# Global Package
# ===============================================
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
import altair as alt
import streamlit as st
import duckdb
import pandas as pd


# ===============================================
# ENVIRONMENT VAR
# ===============================================
class Settings(BaseSettings):
    """
    Import Settings from .env file with pydantic settings
    """

    model_config = SettingsConfigDict(env_file=".env")

    file_path_pro_data: str = "data/03_processed"
    debug: bool = False

    # Unused
    file_path_raw_data: str = ""
    file_path_inter_data: str = ""
    data_load_mod: str = ""
    data_load_init_date: str = ""
    api_base_url: str = ""


settings = Settings()

# ===============================================
# File variables
# ===============================================

FILE_PATH_PRO_DATA: Path = (
    Path(__file__).resolve().parent
    / "etl"
    / settings.file_path_pro_data
    / "dm_fact_visits.parquet"
)
DEBUG: bool = settings.debug

# ===============================================
# Streamlit resources
# ===============================================


#
@st.cache_resource
def get_connection():
    """
    Connect to DuckDB
    Function necessary for streamlit cache resource
    :return: return duckdb connection and set up in st cache
    """
    return duckdb.connect()


# DB cache
con = get_connection()


@st.cache_data
def load_data(_db_con, parquet_file: str) -> pd.DataFrame:
    """
    Retrieve the data from parquet file and put it in the streamlit cache
    :param _db_con: static argument for streamlit
    :param parquet_file: file to load
    :return: return a pandas dataframe
    """
    # We use case when statement to retrieve doors name
    # In reality case we use a db reference table with star/snowflake schemas around fact table
    return _db_con.execute(f"""
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
            ,PCT_CHANGE
            ,TOT_DAILY_VISITS_NUM
            ,TOT_AVG_DAILY_VISITS_NUM
            ,TOT_PCT_CHANGE
        FROM read_parquet('{parquet_file}')
        WHERE DAILY_VISITS_NUM<>0
        ORDER BY DATE_ID DESC
    """).df()


# ===============================================
# Main code
# ===============================================

# Data preparation for data viz
dm_fact_visits_df = load_data(con, str(FILE_PATH_PRO_DATA))
door_sensor_list: tuple = tuple(sorted(dm_fact_visits_df["SENSOR_ID"].unique()))


# Streamlit output
st.title("Daily store visits dashboard")


option = st.selectbox(
    "Which door do you want to analyse ?",
    door_sensor_list,
    index=None,
    placeholder="Choose a door sensor to analyse",
)

if option is not None:
    daily_door_visits_df = dm_fact_visits_df.loc[
        dm_fact_visits_df.SENSOR_ID == option
    ].sort_values(by=["DATE_ID"], ascending=False)
    st.dataframe(daily_door_visits_df)

    DOOR_NAME: str = str(daily_door_visits_df["DOOR_NAME_DESC"].iloc[0])
    st.title(f"Daily {DOOR_NAME} door visits")

    chart = (
        alt.Chart(daily_door_visits_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("OPEN_DT:T", axis=alt.Axis(format="%d %b", tickCount="day")),
            y="DAILY_VISITS_NUM:Q",
            tooltip=["OPEN_DT", "DAILY_VISITS_NUM"],
        )
        .properties(title=f"Daily {DOOR_NAME} visits")
    )

    st.altair_chart(chart, use_container_width=True)

else:
    st.info("Select a door to analyse")
