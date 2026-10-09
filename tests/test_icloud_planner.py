import os
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from monolith.icloud_planner import (
    _event_from_component,
    get_icloud_planner,
)


class DateProperty:
    def __init__(self, value):
        self.dt = value


class PlannerNormalizationTests(unittest.TestCase):
    def test_serializes_all_day_event(self):
        component = {
            "uid": "event-1",
            "summary": "Ganztägiger Testtermin",
            "dtstart": DateProperty(
                date(2020, 9, 25)
            ),
            "dtend": DateProperty(
                date(2020, 9, 26)
            ),
        }

        event = _event_from_component(
            component,
            "Privat",
        )

        self.assertTrue(event["all_day"])
        self.assertEqual(
            event["start"],
            "2020-09-25",
        )
        self.assertEqual(
            event["calendar"],
            "Privat",
        )

    def test_uses_duration_when_end_is_missing(self):
        starts_at = datetime(
            2020,
            9,
            25,
            10,
            30,
        )
        component = {
            "uid": "event-2",
            "summary": "Termin",
            "dtstart": DateProperty(starts_at),
            "duration": DateProperty(
                timedelta(minutes=45)
            ),
        }

        event = _event_from_component(
            component,
            "Arbeit",
        )

        self.assertEqual(
            event["end"],
            "2020-09-25T11:15:00",
        )

    def test_unconfigured_account_returns_setup_state(self):
        clean_environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("ICLOUD_")
        }

        with patch.dict(
            os.environ,
            clean_environment,
            clear=True,
        ):
            result = get_icloud_planner(
                date(2020, 9, 1),
                date(2020, 10, 1),
                force_refresh=True,
            )

        self.assertTrue(result["success"])
        self.assertFalse(result["configured"])
        self.assertEqual(
            result["calendar"]["status"],
            "setup",
        )

if __name__ == "__main__":
    unittest.main()
