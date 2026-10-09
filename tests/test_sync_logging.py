import unittest
from unittest.mock import patch

from monolith import app as monolith_app


class SyncLoggingTest(unittest.TestCase):
    def setUp(self):
        self.purifier = monolith_app.devices[
            "device_air_filter_01"
        ]
        self.original_active = self.purifier[
            "active"
        ]
        self.was_observed = (
            "purifier:active"
            in monolith_app.observed_states
        )

    def tearDown(self):
        self.purifier["active"] = (
            self.original_active
        )

        if self.was_observed:
            monolith_app.observed_states.add(
                "purifier:active"
            )
        else:
            monolith_app.observed_states.discard(
                "purifier:active"
            )

    def test_identical_purifier_state_is_not_logged(self):
        self.purifier["active"] = True
        monolith_app.observed_states.add(
            "purifier:active"
        )

        with patch("builtins.print") as output:
            response = monolith_app.app.test_client().post(
                "/api/sync",
                json={
                    "device_air_filter_01_active": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        output.assert_not_called()

    def test_quiet_sensor_still_updates_value(self):
        original_value = monolith_app.sensors[
            "hallway"
        ]["pm25"]

        try:
            with patch("builtins.print") as output:
                result = monolith_app.update_sensor(
                    "sensor_hallway_pm25",
                    37,
                    log_update=False,
                    log_unchanged=False,
                )

            self.assertEqual(
                result,
                ("hallway", "pm25"),
            )
            self.assertEqual(
                monolith_app.sensors[
                    "hallway"
                ]["pm25"],
                37,
            )
            output.assert_not_called()
        finally:
            monolith_app.sensors[
                "hallway"
            ]["pm25"] = original_value

    def test_first_running_washer_state_is_logged_and_persisted(self):
        washer = monolith_app.devices["device_washer_01"]
        original_value = washer["value"]
        state_key = "washer:in_use"
        was_observed = state_key in monolith_app.observed_states

        try:
            washer["value"] = False
            monolith_app.observed_states.discard(state_key)

            with (
                patch("monolith.app.create_device_event") as create_event,
                patch("monolith.app.save_device_state") as save_state,
            ):
                response = monolith_app.app.test_client().post(
                    "/api/sync",
                    json={"device_washer_01_in_use": True},
                )

            self.assertEqual(response.status_code, 200)
            create_event.assert_called_once_with(
                "device_washer_01",
                False,
                True,
            )
            save_state.assert_called_once_with(
                "device_washer_01",
                True,
            )
        finally:
            washer["value"] = original_value
            if was_observed:
                monolith_app.observed_states.add(state_key)
            else:
                monolith_app.observed_states.discard(state_key)

    def test_first_idle_washer_state_is_only_persisted(self):
        washer = monolith_app.devices["device_washer_01"]
        original_value = washer["value"]
        state_key = "washer:in_use"
        was_observed = state_key in monolith_app.observed_states

        try:
            washer["value"] = False
            monolith_app.observed_states.discard(state_key)

            with (
                patch("monolith.app.create_device_event") as create_event,
                patch("monolith.app.save_device_state") as save_state,
            ):
                response = monolith_app.app.test_client().post(
                    "/api/sync",
                    json={"device_washer_01_in_use": False},
                )

            self.assertEqual(response.status_code, 200)
            create_event.assert_not_called()
            save_state.assert_called_once_with(
                "device_washer_01",
                False,
            )
        finally:
            washer["value"] = original_value
            if was_observed:
                monolith_app.observed_states.add(state_key)
            else:
                monolith_app.observed_states.discard(state_key)

    def test_pc_status_can_update_standard_device(self):
        pc = monolith_app.devices[
            "device_computer_01"
        ]
        original_value = pc["value"]

        try:
            with (
                patch(
                    "monolith.app.create_device_event"
                ),
                patch(
                    "monolith.app.save_device_state"
                ) as save_state,
            ):
                result = (
                    monolith_app.update_standard_device(
                        "device_computer_01",
                        True,
                    )
                )

            self.assertTrue(result)
            self.assertTrue(pc["value"])
            save_state.assert_not_called()
        finally:
            pc["value"] = original_value

    def test_identical_lg_tv_status_is_not_logged(self):
        device_id = "device_display_01"
        device = monolith_app.devices[device_id]
        original_device = device.copy()
        state_key = f"device:{device_id}"
        was_observed = (
            state_key in monolith_app.observed_states
        )
        status = {
            "value": True,
            "connected": True,
            "power_state": "An",
            "app": "youtube.leanback.v4",
            "app_name": "YouTube",
            "volume": 12,
            "muted": False,
        }

        try:
            device.update(status)
            monolith_app.observed_states.add(state_key)

            with patch("builtins.print") as output:
                monolith_app.update_lg_tv_status(status)

            output.assert_not_called()
        finally:
            device.clear()
            device.update(original_device)

            if was_observed:
                monolith_app.observed_states.add(
                    state_key
                )
            else:
                monolith_app.observed_states.discard(
                    state_key
                )


if __name__ == "__main__":
    unittest.main()
