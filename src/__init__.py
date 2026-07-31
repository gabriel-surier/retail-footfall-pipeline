"""
@File    :   __init__.py
@Time    :   2020/07/30
@Author  :   Gabriel SURIER
@Purpose :   Declare base app for api usage
"""

from src.sensor import AttendanceSensor


def create_app() -> dict:
    """
    Create the data for all doors sensor in the store
    4 doors for this store so 4 sensors
    """
    door_name = ["north", "south", "east", "west"]
    door_avg_visit = [100, 250, 150, 400]
    door_std_visit = [25, 75, 40, 100]
    pct_dysfunction = [0.05, 0.08, 0.1, 0.075]
    pct_breakdown = [0.01, 0.03, 0.05, 0.02]

    door_dict: dict = {}

    for i in enumerate(door_name):
        index = i[0]
        door_dict[door_name[index]] = AttendanceSensor(
            door_avg_visit[index],
            door_std_visit[index],
            pct_dysfunction[index],
            pct_breakdown[index],
        )
    return door_dict
