import unittest

from garmin_mcp_server import _body_battery_levels


class BodyBatteryLevelsTests(unittest.TestCase):
    def test_filters_null_and_malformed_points(self):
        values = [
            [1000, None],
            [2000, 72],
            [3000, 0],
            [4000],
            None,
            {"value": 65},
            [5000, "64"],
            [6000, True],
            (7000, 61.5),
        ]

        self.assertEqual(_body_battery_levels(values), [72, 0, 61.5])

    def test_empty_and_all_null_values_are_safe(self):
        self.assertEqual(_body_battery_levels(None), [])
        self.assertEqual(_body_battery_levels([[1000, None], [2000, None]]), [])


if __name__ == "__main__":
    unittest.main()
