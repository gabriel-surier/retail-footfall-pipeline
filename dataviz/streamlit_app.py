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
from typing import Literal
import tempfile

import altair as alt
import streamlit as st
import duckdb
import pandas as pd


from src.rfp_config import get_s3_client, download_file, settings

# ===============================================
# File variables
# ===============================================

client = get_s3_client(settings)
print(f"{settings.file_path_pro_data}/dm_fact_visits.parquet")
print(f"test : {settings.minio_bucket}")
FILE_PATH_PRO_DATA: Path = Path(tempfile.gettempdir()) / "dm_fact_visits.parquet"
download_file(
    client,
    bucket=settings.minio_bucket,
    key=f"rfp_fl001/{settings.file_path_pro_data}/dm_fact_visits.parquet",
    local_path=FILE_PATH_PRO_DATA,
)

DEBUG: bool = settings.debug

# ===============================================
# Streamlit resources
# ===============================================


@st.cache_resource
def get_connection():
    """
    Connect to DuckDB
    Function necessary for streamlit cache resource
    :return: return duckdb connection and set up in st cache
    """
    return duckdb.connect()


con = get_connection()


@st.cache_data
def load_data(_db_con, parquet_file: str) -> pd.DataFrame:
    """
    Retrieve the data from parquet file and put it in the streamlit cache
    :param _db_con: static argument for streamlit
    :param parquet_file: file to load
    :return: return a pandas dataframe
    """
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
        -- We need 4 week to have good analyzes from
        -- window function
        WHERE date_trunc('week', OPEN_DT) > (
        SELECT date_trunc('week', MIN(OPEN_DT)) + INTERVAL 4 WEEK
        FROM read_parquet('{parquet_file}')
        )
        ORDER BY DATE_ID DESC
    """).df()


# ===============================================
# Main code
# ===============================================

dm_fact_visits_df = load_data(con, str(FILE_PATH_PRO_DATA))
door_sensor_list: tuple = tuple(sorted(dm_fact_visits_df["SENSOR_ID"].unique()))

st.title("Store visits dashboard")

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

    DOOR_NAME: str = str(daily_door_visits_df["DOOR_NAME_DESC"].iloc[0])
    CAP_DOOR_NAME: str = DOOR_NAME.capitalize()

    OUTPUT_ALIASES = {
        "OPEN_DT": "Open date",
        "DAILY_VISITS_NUM": "Visits",
        "AVG_DAILY_VISITS_NUM": "Average visits",
        "TOT_DAILY_VISITS_NUM": "Visits",
        "TOT_AVG_DAILY_VISITS_NUM": "Average visits",
        "PCT_CHANGE": "Door % change",
        "TOT_PCT_CHANGE": "Store % change",
    }

    now = pd.Timestamp.now()

    df_all = daily_door_visits_df.copy()
    df_all["OPEN_DT"] = pd.to_datetime(df_all["OPEN_DT"])

    output_door_df = (
        df_all[["OPEN_DT", "DAILY_VISITS_NUM", "AVG_DAILY_VISITS_NUM", "PCT_CHANGE"]]
        .sort_values("OPEN_DT", ascending=False)
        .rename(columns=OUTPUT_ALIASES)
    )

    store_df = dm_fact_visits_df.copy()
    store_df["OPEN_DT"] = pd.to_datetime(store_df["OPEN_DT"])
    store_df = store_df.drop_duplicates(subset="OPEN_DT")[
        [
            "OPEN_DT",
            "TOT_DAILY_VISITS_NUM",
            "TOT_AVG_DAILY_VISITS_NUM",
            "TOT_PCT_CHANGE",
        ]
    ].sort_values("OPEN_DT", ascending=False)

    output_store_df = store_df.rename(columns=OUTPUT_ALIASES)

    view = st.sidebar.radio(
        "View", ["Year (by month)", "Month (by week)", "Week (by day)"]
    )

    if view == "Month (by week)":
        months = sorted(df_all["OPEN_DT"].dt.to_period("M").unique())
        default_month = pd.Period(now, "M")
        default_idx = months.index(default_month)
        selected_month = st.sidebar.selectbox(
            "Month",
            months,
            index=default_idx,
            format_func=lambda p: p.strftime("%B %Y"),
        )
    elif view == "Week (by day)":
        weeks = sorted(df_all["OPEN_DT"].dt.to_period("W").unique())
        default_week = pd.Period(now, "W")
        default_idx = weeks.index(default_week)
        selected_week = st.sidebar.selectbox(
            "Week",
            weeks,
            index=default_idx,
            format_func=lambda p: f"{p.start_time:%d %b} - {p.end_time:%d %b %Y}",
        )

    def filter_period(
        df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, str, str, Literal["month", "week", "day"]]:
        """
        Filter df to the selected view's period and return grouping code, date format, tick unit

        :param df: dataframe with an OPEN_DT column
        :return: filtered df, period code, date format, tick unit
        """
        tick: Literal["month", "week", "day"]
        if view == "Year (by month)":
            df = df[df["OPEN_DT"].dt.year == now.year]
            period, fmt, tick = "M", "%b", "month"
        elif view == "Month (by week)":
            df = df[df["OPEN_DT"].dt.to_period("M") == selected_month]
            period, fmt, tick = "W", "%d %b", "week"
        else:
            df = df[df["OPEN_DT"].dt.to_period("W") == selected_week]
            period, fmt, tick = "D", "%a %d", "day"
        return df, period, fmt, tick

    def build_table(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        """
        Build the display table for the current view: filter by period,
        keep given cols, apply aliases

        :param df: dataframe with an OPEN_DT column
        :param cols: metric columns to keep alongside OPEN_DT
        :return: filtered dataframe with aliased column names, sorted by date descending
        """
        filtered_df, _, _, _ = filter_period(df)
        return (
            filtered_df[["OPEN_DT"] + cols]
            .sort_values("OPEN_DT", ascending=False)
            .rename(columns=OUTPUT_ALIASES)
        )

    show_avg = view == "Week (by day)"

    door_cols = ["DAILY_VISITS_NUM"] + (
        ["AVG_DAILY_VISITS_NUM"] + ["PCT_CHANGE"] if show_avg else []
    )
    store_cols = ["TOT_DAILY_VISITS_NUM"] + (
        ["TOT_AVG_DAILY_VISITS_NUM"] + ["TOT_PCT_CHANGE"] if show_avg else []
    )

    output_door_df = build_table(df_all, door_cols)
    output_store_df = build_table(store_df, store_cols)

    def build_chart(df: pd.DataFrame, metric_col: str, short_title: str) -> alt.Chart:
        """
        Build a bar chart for the given metric, grouped and filtered to
        the currently selected view's period

        :param df: dataframe with an OPEN_DT column
        :param metric_col: raw metric column name to aggregate and plot
        :param short_title: chart title displayed above the bars
        :return: Altair bar chart aggregated by period with aliased axis and tooltip labels
        """
        df, period, fmt, tick = filter_period(df)

        grp = (
            df.groupby(df["OPEN_DT"].dt.to_period(period))[metric_col]
            .sum()
            .reset_index()
        )
        grp["Period"] = (
            grp["OPEN_DT"].dt.to_timestamp()
            if period in ("M", "D")
            else grp["OPEN_DT"].dt.start_time
        )
        grp = grp.rename(columns={metric_col: OUTPUT_ALIASES[metric_col]}).drop(
            columns="OPEN_DT"
        )

        x_enc = alt.X(
            "Period:T",
            axis=alt.Axis(format=fmt, tickCount=tick),
            title=view.split("(")[0].strip(),
        )

        return (
            alt.Chart(grp)
            .mark_bar()
            .encode(
                x=x_enc,
                y=alt.Y(f"{OUTPUT_ALIASES[metric_col]}:Q"),
                tooltip=list(grp.columns),
            )
            .properties(title=short_title, height=250)
        )

    col_door, col_store = st.columns(2)
    with col_door:
        st.subheader(f"{CAP_DOOR_NAME} door")
        st.dataframe(
            output_door_df,
            use_container_width=True,
            height=250,
            hide_index=True,
            column_config={
                "Open date": st.column_config.DatetimeColumn(
                    "Open date", format="YYYY-MM-DD"
                ),
            },
        )
    with col_store:
        st.subheader("Store total")
        st.dataframe(
            output_store_df,
            use_container_width=True,
            height=250,
            hide_index=True,
            column_config={
                "Open date": st.column_config.DatetimeColumn(
                    "Open date", format="YYYY-MM-DD"
                ),
            },
        )
    with col_door:
        st.altair_chart(
            build_chart(
                df_all,
                "DAILY_VISITS_NUM",
                f"{CAP_DOOR_NAME} - {OUTPUT_ALIASES['DAILY_VISITS_NUM']}",
            ),
            use_container_width=True,
        )
    with col_store:
        st.altair_chart(
            build_chart(
                store_df, "TOT_DAILY_VISITS_NUM", OUTPUT_ALIASES["TOT_DAILY_VISITS_NUM"]
            ),
            use_container_width=True,
        )

    if show_avg:
        col_door, col_store = st.columns(2)
        with col_door:
            st.altair_chart(
                build_chart(
                    df_all,
                    "AVG_DAILY_VISITS_NUM",
                    f"{CAP_DOOR_NAME} - {OUTPUT_ALIASES['AVG_DAILY_VISITS_NUM']}",
                ),
                use_container_width=True,
            )
        with col_store:
            st.altair_chart(
                build_chart(
                    store_df,
                    "TOT_AVG_DAILY_VISITS_NUM",
                    f"Store {OUTPUT_ALIASES["TOT_AVG_DAILY_VISITS_NUM"]}",
                ),
                use_container_width=True,
            )
else:
    st.info("Select a door to analyse")
