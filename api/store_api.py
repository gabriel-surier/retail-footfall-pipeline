"""
@File    :   store_api.py
@Time    :   2026/07/30
@Author  :   Gabriel SURIER
@Purpose :   Create API for simulate provider data app
Update   :   2026/08/31 : add health endpoint for CD
         :   add init file and Docker encapsulation
"""

import logging
from datetime import date

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette import status
from src import create_app

door_dict: dict = create_app()

app = FastAPI()

@app.get("/door-health")
def get_health():
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "responseCode": status.HTTP_200_OK,
            "responseMessage": "Endpoint related to provider door visits is online",
        }
    )


@app.get("/door-visits")
def get_visits(open_date: str, door_name: str) -> JSONResponse:
    """
    get visits by date and door name
    :param open_date: yyyy-mm-dd format
    :param door_name: [north, south, east, west]
    :return: JSON response with visits data or error message
    """
    try:
        visits = door_dict[door_name].get_hour_visits(open_date)
    except (ValueError, KeyError) as e:

        if door_name not in door_dict:
            error_message = f"The door {door_name} does not exist in the database"
        else:
            error_message = (
                f"Error on input date {open_date}, date format is yyyy-mm-dd"
            )

        logging.error("%s, Error : %s", error_message, e)

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "responseCode": status.HTTP_400_BAD_REQUEST,
                "errorMessage": error_message,
            },
        )

    if date.fromisoformat(open_date).weekday() == 6:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "responseCode": status.HTTP_400_BAD_REQUEST,
                "errorMessage": "Error, weekday selected is a Sunday, no data provided",
            },
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "responseCode": status.HTTP_200_OK,
            "responseMessage": f"Successfully fetched visits for the day {open_date} "  # \
            f"and the {door_name} door",
            "sensor_visits": {
                "door_name": door_name,
                "open_date": open_date,
                "datas": visits,
            },
        },
    )
