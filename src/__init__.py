fr"""
@File    :   __init__.py
@Time    :   2020/07/30
@Author  :   Gabriel SURIER
@Purpose :   Declare base app for api usage 
"""
from datetime import date

from src.sensor import AttendanceSensor

def create_app() -> dict:
    """
    Create the data for all doors sensor in the store
    4 doors for this store so 4 sensors
    """
    door_name = ["north", "south", "east", "west"]
    door_avg_visit = [100,250,150,400]
    door_std_visit = [25,75,40,100]
    pct_dysfunction= [0.05,0.08,0.1,0.075]
    pct_breakdown = [0.01,0.03,0.05,0.02]

    door_dict = dict()

    for i in range(len(door_name)):
        door_dict[door_name[i]] = AttendanceSensor(
            door_avg_visit[i],
            door_std_visit[i],
            pct_dysfunction[i],
            pct_breakdown[i],
        )
    return door_dict

