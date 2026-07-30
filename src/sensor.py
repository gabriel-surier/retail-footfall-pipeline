"""
@File    :   sensor.py
@Time    :   2020/8/25
@Author  :   Gabriel SURIER
@Purpose :   Declare AttendanceSensor to simulate datas
"""

from datetime import date
import sys

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
        pct_dysfunction: float = 0.05,
        pct_breakdown: float = 0.015,
    ) -> None:
        self.avg_door_passes = avg_door_passes
        self.std_door_passes = std_door_passes
        self.pct_dysfunction = pct_dysfunction
        self.pct_breakdown = pct_breakdown

    def simulate_hour_visits(
        self,
        open_date: str,
    ) -> list:
        """
        hour_visits :
        Define a list for the number of passage per hour
        """

        open_date_iso: date = date.fromisoformat(open_date)
        week_day: int = date.weekday(open_date_iso)
        seed: int = open_date_iso.toordinal()
        rng_datas: Generator = np.random.default_rng(seed)
        list_visits_per_hour: list = [
            {"hour": hour, "visits_nb": int((np.round(visits_nb).astype(int)))}
            for hour, visits_nb in zip(
                range(8, 20),
                rng_datas.normal(
                    loc=self.avg_door_passes, scale=self.std_door_passes, size=12
                ),
            )
        ]
        # Adjust the visits per hour to have something that looks like reality
        for index in enumerate(list_visits_per_hour):
            hour = index[1]["hour"]
            visits_per_hour = index[1]["visits_nb"]

            if hour in range(8, 12):
                visits_per_hour *= 0.5

            if hour in range(12, 14):
                visits_per_hour *= 1.5

            if hour in range(14, 18):
                visits_per_hour *= 0.75

            if hour in range(18, 20):
                visits_per_hour *= 2

            index[1]["visits_nb"] = visits_per_hour

        # If it's sunday the store is closed.
        if week_day == 6:
            visits_of_the_day = [-1]
        else:
            visits_of_the_day = list_visits_per_hour

        return visits_of_the_day

    def get_hour_visits(self, open_date: str) -> list:
        """
        Return the number of visits per hour with
        simulated null or count errors
        """
        np.random.seed(seed=date.fromisoformat(open_date).toordinal())
        rng_dysfunction = np.random.random()
        rng_hour: int = int(np.random.randint(low=0, high=12))

        day_visits_nb = self.simulate_hour_visits(open_date)

        if day_visits_nb[0] != -1:
            # Simulate a sensor dysfunction
            if rng_dysfunction < self.pct_dysfunction:
                day_visits_nb[rng_hour]["visits_nb"] *= 0.1
            # Simulate a sensor breakdown
            if rng_dysfunction < self.pct_breakdown:
                day_visits_nb[rng_hour]["visits_nb"] = None

        return day_visits_nb


if __name__ == "__main__":
    if len(sys.argv) > 1:
        year, month, day = [int(v) for v in sys.argv[1].split("-")]
    else:
        year, month, day = 2026, 7, 30
    queried_date = date(year, month, day).strftime("%Y-%m-%d")

    sensor = AttendanceSensor(avg_door_passes=100, std_door_passes=25)
    print(sensor.get_hour_visits(queried_date))
