"""
@File    :   test_sensor.py
@Time    :   2020/8/26
@Author  :   Gabriel SURIER
@Purpose :   Unit tests on AttendanceSensor for ci
"""

import unittest
from datetime import date

from src.sensor import AttendanceSensor  # pylint: disable=import-error


class TestAttendanceSensor(unittest.TestCase):
    """
    Define the test class for the AttendanceSensor.
    Those tests check the behaviours of the 2 methods.
    """

    def test_weekdays_open(self):
        """
        Unit test for open weekdays
        :return: OK or Failed subtests list: (i=26) if it's Sunday
        """
        for test_day in range(20, 26):
            with self.subTest(i=test_day):
                visit_sensor = AttendanceSensor(avg_door_passes=100, std_door_passes=25)
                visit_count = visit_sensor.simulate_hour_visits(
                    date(2026, 7, test_day).strftime("%Y-%m-%d")
                )
                print(visit_count)
                self.assertFalse(visit_count[0] == -1)

    def test_sunday_closed(self):
        """
        Unit test for checking if a sunday return no datas
        :return: OK or AssertionError: {'hour': n, 'visits_nb': n } != -1 if it's not a Sunday
        """
        visit_sensor = AttendanceSensor(avg_door_passes=100, std_door_passes=25)
        visit_count = visit_sensor.simulate_hour_visits("2026-07-26")
        self.assertEqual(visit_count[0], -1)

    def test_with_breakdown(self):
        """
        Unit test for checking if a breakdown return no datas
        :return: OK AssertionError: None != 'yourValue' or AssertionError: 'valueOfDate' != None
        """
        visit_sensor = AttendanceSensor(
            avg_door_passes=100, std_door_passes=25, pct_breakdown=10
        )
        index_hour = 8  # represent hour = 16
        visit_count = visit_sensor.get_hour_visits("2026-03-20")
        self.assertEqual(visit_count[index_hour]["visits_nb"], None)

    def test_with_dysfunction(self):
        """
        Unit test for checking if a breakdown return no datas
        :return: OK or AssertionError: 'valueOfDate' != 'yourValue'
        """
        visit_sensor = AttendanceSensor(
            avg_door_passes=100, std_door_passes=25, pct_dysfunction=10
        )
        index_hour = 0  # represent hour = 8
        visit_count = visit_sensor.get_hour_visits("2026-07-02")
        self.assertEqual(visit_count[index_hour]["visits_nb"], 19.0)


if __name__ == "__main__":
    unittest.main()
