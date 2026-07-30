from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from datetime import date

from starlette import status

from src import create_app

door_dict: dict = create_app()

app=FastAPI()

@app.get("/GET_VISITS/")

def get_visits(
        open_date: str,
        door_name:str
) -> JSONResponse:
    visits = door_dict[door_name].get_hour_visits(open_date)
    if date.fromisoformat(open_date).weekday() == 6:
        return JSONResponse(status_code=500, content={"responseCode": 500,
                                                      "responseMessage": "Error, weekday selected is a Sunday, no data provided"})
    else:
        return JSONResponse(status_code=200, content={
            "responseCode": 200,
            "responseMessage": f"Successfully fetched visits for the day {open_date} and the {door_name} door",
            "sensor_visits" : {
            "door_name": door_name,"open_date" : open_date, "datas": visits}
                                                      }
                            )
