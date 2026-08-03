"""
@File    :   rfp_001_extract_data.py
@Time    :   2020/8/31
@Author  :   Gabriel SURIER
@Purpose :   Create csv dataset for storing sensor data month by month
            here they are stocked in data/raw, but in a real environment,
            we will use S3 or maybe an ODS in a database.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
import os
import calendar

import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ===============================================
# ENVIRONMENT VAR
# ===============================================
FILE_PATH_RAW_DATA = os.getenv("FILE_PATH_RAW_DATA")

API_BASE_URL = os.getenv("API_BASE_URL")

DATA_LOAD_MOD = os.getenv("DATA_LOAD_MOD")
DATA_LOAD_INIT_DATE: str = str(os.getenv("DATA_LOAD_INIT_DATE"))

DEBUG = os.getenv("DEBUG")

# ===============================================
# FILE VAR
# ===============================================


ref_door: dict = {
    "sensors_referential": [
        {"sensor_id": 1, "door_name": "north"},
        {"sensor_id": 2, "door_name": "south"},
        {"sensor_id": 3, "door_name": "east"},
        {"sensor_id": 4, "door_name": "west"},
    ]
}
df_door_id = pd.DataFrame(ref_door["sensors_referential"])

# Make a delta load mod for orchestration
start_date: date = date(2026, 1, 1)  # default for initialize date type
if DATA_LOAD_MOD == "INIT":
    start_date = date.fromisoformat(DATA_LOAD_INIT_DATE)
else:
    start_date = date.today().replace(day=1)
END_DATE: date = date.today()
current_timestamp_str: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
raw_data_file_path = Path(__file__).resolve().parent

# ===============================================
# EXTRACT PIPELINE
# ===============================================


def is_last_day_of_month(current_date: date) -> bool:
    """
    From a given date, determine if it is the last day of the month
    :param current_date:
    :return:
    """
    last_day_of_month = calendar.monthrange(current_date.year, current_date.month)[1]
    return current_date.day == last_day_of_month


def extract_date_id(business_date: str) -> int:
    """
    Retrieve the date id for a given business date
    :param business_date:
    :return: date id
    """
    date_id = int(
        business_date.split("-")[0]
        + business_date.split("-")[1]
        + business_date.split("-")[2]
    )
    return date_id


def extract_by_date(business_date: str, door_name: str) -> pd.DataFrame:
    """
    Retrieve the data frame from the given business date and door name
    :param business_date:
    :param door_name:
    :return: dataframe sensor_df
    """
    # declare variables
    get_url = (
        f"{API_BASE_URL}/door-visits?open_date={business_date}&door_name={door_name}"
    )
    date_id = extract_date_id(business_date)
    # api call
    response_dict = requests.get(get_url, timeout=300).json()
    # pandas dataframe construction
    sensor_df = pd.DataFrame(response_dict["sensor_visits"]["datas"])

    sensor_df["open_date"] = business_date
    sensor_df["TEC_CREATION_TS"] = current_timestamp_str
    sensor_df.insert(0, "door_name", door_name)
    sensor_df = sensor_df.merge(df_door_id, on="door_name")

    sensor_df.insert(0, "date_id", date_id)
    sensor_df = sensor_df[
        [
            "date_id",
            "sensor_id",
            "door_name",
            "hour",
            "visits_nb",
            "open_date",
            "TEC_CREATION_TS",
        ]
    ]
    return sensor_df


def create_csv_by_month(starting_date: date, end_date: date) -> None:
    """
    Create csv file month by month from start date to end date
    :param starting_date:
    :param end_date:
    :return: None
    """
    output_df = pd.DataFrame()
    current_date = starting_date
    while current_date <= end_date:
        business_date = current_date.strftime("%Y-%m-%d")
        if current_date.weekday() != 6:
            for door_name in enumerate(ref_door["sensors_referential"]):
                door_name = door_name[1]["door_name"]
                sensor_df = extract_by_date(business_date, door_name)
                output_df = pd.concat([output_df, sensor_df], ignore_index=True)
            if is_last_day_of_month(current_date):
                month_id = str(extract_date_id(business_date))[:6]
                with open(
                    f"{raw_data_file_path}{FILE_PATH_RAW_DATA}store_data_{month_id}.csv",
                    "w",
                    encoding="UTF-8",
                ) as file:
                    output_df.to_csv(file, index=False)
                    file.close()

                output_df = pd.DataFrame()

        current_date += timedelta(days=1)


if __name__ == "__main__":
    create_csv_by_month(start_date, END_DATE)
