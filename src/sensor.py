"""Sensor module for simulating hourly store visit attendance."""

from datetime import date

import numpy as np
from numpy.random import Generator


class AttendanceSensor:
    """
    AttendanceSensor :
    Creates an attendance sensor for counting door passages to simulate
    a number of visits per hour. The number of visits per hour is fix day by day
    """

    def __init__(
        self,
        avg_door_passes: int,
        std_door_passes: int,
    ) -> None:
        self.avg_door_passes = avg_door_passes
        self.std_door_passes = std_door_passes

    def hour_visits(
        self,
        open_date: str,
    ) -> list:
        """
        hour_visits :
        Define a list for the number of passage per hour
        """

        seed: int = date.fromisoformat(open_date).toordinal()
        rng_datas: Generator = np.random.default_rng(seed)
        list_visits_per_hour: list = [
            {"hour": hour, "nb_visits": int((np.round(nb_visits).astype(int)))}
            for hour, nb_visits in zip(
                range(8, 20),
                rng_datas.normal(
                    loc=self.avg_door_passes, scale=self.std_door_passes, size=12
                ),
            )
        ]
        # Adjust the visits per hour to have something that looks like reality
        for index in enumerate(list_visits_per_hour):
            hour = index[1]["hour"]
            visits_per_hour = index[1]["nb_visits"]

            if hour in range(8, 12):
                visits_per_hour *= 0.5

            if hour in range(12, 14):
                visits_per_hour *= 1.5

            if hour in range(14, 18):
                visits_per_hour *= 0.75

            if hour in range(18, 20):
                visits_per_hour *= 2

            index[1]["nb_visits"] = visits_per_hour

        visits_of_the_day: list = list_visits_per_hour

        return visits_of_the_day
