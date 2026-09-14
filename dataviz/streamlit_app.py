"""
@File    :   streamlit_app.py
@Time    :   2020/08/11
@Author  :   Gabriel SURIER
@Purpose :   Streamlit dashboard visualizing daily store
             visits for a selected week, built with DuckDB and pandas.
"""

# ===============================================
# Global Package
# ===============================================
from pathlib import Path
from typing import Any

import altair as alt
import duckdb
import pandas as pd
import streamlit as st


from src.rfp_config import download_files, get_s3_client, get_workspace, settings

# ===============================================
# File variables
# ===============================================

# S3/MinIO client used once at import time to pull the latest parquet.
client = get_s3_client(settings)

STREAMLIT_WORKSPACE: str = "dataviz"
FILE_PATH_PRO_DATA: Path = settings.project_root / Path(STREAMLIT_WORKSPACE)
FILE_PATH_PARQUET: Path = (
    FILE_PATH_PRO_DATA / settings.file_path_pro_data / "dm_fact_visits.parquet"
)

# SQL views directory setup
sql_dir: Path = Path(__file__).resolve().parent / "sqlq"


# Maps raw parquet column names to the labels shown in tables/charts.
OUTPUT_ALIASES: dict[str, str] = {
    "OPEN_DT": "Open date",
    "DAILY_VISITS_NUM": "Visits",
    "AVG_DAILY_VISITS_NUM": "Average visits",
    "TOT_DAILY_VISITS_NUM": "Visits",
    "TOT_AVG_DAILY_VISITS_NUM": "Average visits",
    "PCT_CHANGE_NUM": "Door % change",
    "TOT_PCT_CHANGE_NUM": "Store % change",
}

# Column widths/formats for both the door and store tables.
TABLE_COLUMN_CONFIG: dict[str, Any] = {
    "Open date": st.column_config.DatetimeColumn(format="YYYY-MM-DD", width="small"),
    "Weekday": st.column_config.TextColumn(width="small"),
    "Visits": st.column_config.NumberColumn(width="small"),
    "Average visits": st.column_config.NumberColumn(width="small"),
    "Door % change": st.column_config.NumberColumn(width="small"),
    "Store % change": st.column_config.NumberColumn(width="small"),
}

# ===============================================
# Streamlit resources
# ===============================================


@st.cache_resource(ttl="1h")
def refresh_source_parquet() -> None:
    """Download the latest parquet from S3/MinIO, at most once per hour.

    Streamlit reruns the whole script on every widget interaction; without
    this cache, the file would be re-downloaded on each rerun even though
    the upstream Airflow pipeline only refreshes it periodically.
    """
    with get_workspace(STREAMLIT_WORKSPACE) as _workspace:
        download_files(
            client,
            bucket=settings.minio_bucket,
            prefix=f"rfp_fl001/{settings.file_path_pro_data}/dm_fact_visits.parquet",
            dest_dir=FILE_PATH_PRO_DATA / settings.file_path_pro_data,
        )


refresh_source_parquet()


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Connect to DuckDB.

    Function necessary for streamlit cache resource.

    Returns:
        duckdb.DuckDBPyConnection: a DuckDB connection cached by Streamlit.
    """
    return duckdb.connect()


con = get_connection()


@st.cache_data
def load_data(
    _db_con: duckdb.DuckDBPyConnection,
    parquet_file: str,
    file_fingerprint: float,  # pylint: disable=unused-argument
) -> pd.DataFrame:
    """Retrieve the 4-week rolling visit data from the parquet file.

    Args:
        _db_con: static argument for streamlit cache (unused as a cache key).
        parquet_file: path to the parquet file to load.
        file_fingerprint: mtime of the parquet file. parquet_file never
            changes, so this is what actually invalidates the cache when
            refresh_source_parquet() writes a new file to disk.

    Returns:
        pd.DataFrame: the loaded and door-labeled dataset.
    """
    with open(sql_dir / "v_dm_fact_visits.sql", encoding="UTF-8") as file:
        sql_query = file.read().replace("?", f"'{parquet_file}'")
    query = _db_con.execute(sql_query).df()
    return query


def add_weekday(df: pd.DataFrame, date_col: str) -> pd.Series | Any:
    """Derive a weekday name series from a datetime column.

    Args:
        df: dataframe containing the date column.
        date_col: name of the datetime column to derive the weekday from.

    Returns:
        pd.Series: weekday names (e.g. "Monday").
    """
    return df[date_col].dt.strftime("%A")


def build_week_table(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Build the display table for the selected week: one row per day.

    Args:
        df: dataframe already filtered to the selected week, with an
            OPEN_DT column.
        cols: metric columns to keep alongside OPEN_DT.

    Returns:
        pd.DataFrame: table with a Weekday column and aliased column names,
        sorted by date descending.
    """
    # One row per day here, so no aggregation is needed, just a sort
    # and a readable Weekday column next to the raw date.
    table_df = df[["OPEN_DT"] + cols].sort_values("OPEN_DT", ascending=False)
    table_df.insert(1, "Weekday", add_weekday(table_df, "OPEN_DT"))
    return table_df.rename(columns=OUTPUT_ALIASES)


def build_chart(df: pd.DataFrame, metric_col: str, title: str) -> alt.Chart:
    """Build a daily bar chart for the given metric over the selected week.

    Args:
        df: dataframe already filtered to the selected week, with an
            OPEN_DT column.
        metric_col: raw metric column name to plot.
        title: chart title displayed above the bars.

    Returns:
        alt.Chart: Altair bar chart with aliased axis and tooltip labels.
    """
    chart_df = df[["OPEN_DT", metric_col]].rename(
        columns={"OPEN_DT": "Open date", metric_col: OUTPUT_ALIASES[metric_col]}
    )
    # Weekday is added only for the tooltip, it never appears on an axis.
    chart_df["Weekday"] = add_weekday(chart_df, "Open date")

    chart: alt.Chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("Open date:T", axis=alt.Axis(format="%d %a"), title="Day"),
            y=alt.Y(f"{OUTPUT_ALIASES[metric_col]}:Q"),
            tooltip=list(chart_df.columns),
        )
        .properties(title=title, height=250)
    )
    return chart


def build_column_order(show_open_date_col: bool, pct_label: str) -> list[str]:
    """Build the column display order for a week table.

    Args:
        show_open_date_col: whether the "Open date" column should be shown.
        pct_label: aliased name of the metric-specific percent change column.

    Returns:
        list[str]: ordered column names to pass to st.dataframe.
    """
    # "Open date" stays in the dataframe either way, we just choose
    # whether to include it in the visible column order.
    leading = ["Open date"] if show_open_date_col else []
    return leading + ["Weekday", "Visits", "Average visits", pct_label]


def render_table(df: pd.DataFrame, subheader: str, column_order: list[str]) -> None:
    """Render a subheader and its week table in the current Streamlit column.

    Args:
        df: table to display, already built with build_week_table.
        subheader: subheader text shown above the table.
        column_order: visible column order for this table.
    """
    st.subheader(subheader)
    st.dataframe(
        df,
        use_container_width=True,
        height=250,
        hide_index=True,
        column_order=column_order,
        column_config=TABLE_COLUMN_CONFIG,
    )


def render_chart_row(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    door_data: pd.DataFrame,
    store_data: pd.DataFrame,
    door_metric: str,
    store_metric: str,
    door_title: str,
    store_title: str,
) -> None:
    """Render a door/store chart pair side by side in two Streamlit columns.

    Args:
        door_data: door-level dataframe filtered to the selected week.
        store_data: store-level dataframe filtered to the selected week.
        door_metric: raw metric column to plot for the door chart.
        store_metric: raw metric column to plot for the store chart.
        door_title: title displayed above the door chart.
        store_title: title displayed above the store chart.
    """
    left_col, right_col = st.columns(2)
    with left_col:
        st.altair_chart(
            build_chart(door_data, door_metric, door_title), use_container_width=True
        )
    with right_col:
        st.altair_chart(
            build_chart(store_data, store_metric, store_title), use_container_width=True
        )


# ===============================================
# Main code
# ===============================================

dm_fact_visits_df = load_data(
    con, str(FILE_PATH_PARQUET), FILE_PATH_PARQUET.stat().st_mtime
)
door_sensor_list: tuple[int, ...] = tuple(
    sorted(dm_fact_visits_df["SENSOR_ID"].astype(int).unique())
)

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
    ].copy()
    daily_door_visits_df["OPEN_DT"] = pd.to_datetime(daily_door_visits_df["OPEN_DT"])

    CAP_DOOR_NAME: str = str(
        daily_door_visits_df["DOOR_NAME_DESC"].iloc[0]
    ).capitalize()

    # Store rows repeat once per sensor, so we dedupe on OPEN_DT to get
    # one row per day at store level instead of one per door.
    store_df = dm_fact_visits_df.drop_duplicates(subset="OPEN_DT").copy()
    store_df["OPEN_DT"] = pd.to_datetime(store_df["OPEN_DT"])

    # Weeks are sorted ascending, so the most recent week is last.
    # We default to it instead of guessing "now" against the dataset.
    weeks = sorted(daily_door_visits_df["OPEN_DT"].dt.to_period("W").unique())
    selected_week = st.sidebar.selectbox(
        "Week",
        weeks,
        index=len(weeks) - 1,
        format_func=lambda p: f"{p.start_time:%d %b} - {p.end_time:%d %b %Y}",
    )

    week_door_df = daily_door_visits_df[
        daily_door_visits_df["OPEN_DT"].dt.to_period("W") == selected_week
    ]
    week_store_df = store_df[store_df["OPEN_DT"].dt.to_period("W") == selected_week]

    output_door_df = build_week_table(
        week_door_df, ["DAILY_VISITS_NUM", "AVG_DAILY_VISITS_NUM", "PCT_CHANGE_NUM"]
    )
    output_store_df = build_week_table(
        week_store_df,
        ["TOT_DAILY_VISITS_NUM", "TOT_AVG_DAILY_VISITS_NUM", "TOT_PCT_CHANGE_NUM"],
    )

    # "Open date" is kept in the data either way, only hidden by default.
    show_open_date = st.checkbox("Show open date column", value=False)
    door_column_order = build_column_order(show_open_date, "Door % change")
    store_column_order = build_column_order(show_open_date, "Store % change")

    col_door, col_store = st.columns(2)
    with col_door:
        render_table(output_door_df, f"{CAP_DOOR_NAME} door", door_column_order)
    with col_store:
        render_table(output_store_df, "Store total", store_column_order)

    render_chart_row(
        week_door_df,
        week_store_df,
        "DAILY_VISITS_NUM",
        "TOT_DAILY_VISITS_NUM",
        f"{CAP_DOOR_NAME} - {OUTPUT_ALIASES['DAILY_VISITS_NUM']}",
        OUTPUT_ALIASES["TOT_DAILY_VISITS_NUM"],
    )
    render_chart_row(
        week_door_df,
        week_store_df,
        "AVG_DAILY_VISITS_NUM",
        "TOT_AVG_DAILY_VISITS_NUM",
        f"{CAP_DOOR_NAME} - {OUTPUT_ALIASES['AVG_DAILY_VISITS_NUM']}",
        f"Store {OUTPUT_ALIASES['TOT_AVG_DAILY_VISITS_NUM']}",
    )
else:
    st.info("Select a door to analyse")
