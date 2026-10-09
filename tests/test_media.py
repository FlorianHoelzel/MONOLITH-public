import unittest
from unittest.mock import AsyncMock, Mock, patch

from monolith import app as monolith
from monolith.homepod import HomePodMonitor


class MediaArtworkTests(unittest.TestCase):
    device_id = "device_media_01"

    def setUp(self):
        self.previous_url = monolith.devices[
            self.device_id
        ].get("artwork_url")

        with monolith.media_artwork_lock:
            self.previous_cache = (
                monolith.media_artwork_cache.get(
                    self.device_id
                )
            )

    def tearDown(self):
        monolith.devices[
            self.device_id
        ]["artwork_url"] = self.previous_url

        with monolith.media_artwork_lock:
            if self.previous_cache is None:
                monolith.media_artwork_cache.pop(
                    self.device_id,
                    None,
                )
            else:
                monolith.media_artwork_cache[
                    self.device_id
                ] = self.previous_cache

    def test_artwork_is_served_with_a_versioned_url(self):
        monolith.update_media_artwork(
            self.device_id,
            {
                "bytes": b"album-cover",
                "mimetype": "image/jpeg",
            },
        )

        artwork_url = monolith.devices[
            self.device_id
        ]["artwork_url"]
        response = monolith.app.test_client().get(
            artwork_url
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"album-cover")
        self.assertEqual(response.mimetype, "image/jpeg")
        self.assertIn("private", response.headers["Cache-Control"])

    def test_invalid_artwork_clears_the_cached_image(self):
        monolith.update_media_artwork(
            self.device_id,
            {
                "bytes": b"not-an-image",
                "mimetype": "text/plain",
            },
        )

        self.assertIsNone(
            monolith.devices[
                self.device_id
            ]["artwork_url"]
        )
        response = monolith.app.test_client().get(
            f"/api/media/artwork/{self.device_id}"
        )
        self.assertEqual(response.status_code, 404)


class HomePodFeedTests(unittest.TestCase):
    def setUp(self):
        self.device_id = "device_speaker_01"
        self.device = monolith.devices[self.device_id]
        self.original_device = self.device.copy()
        self.original_states = monolith.apple_media_feed_states.copy()
        self.original_observed = monolith.observed_states.copy()
        monolith.apple_media_feed_states.pop(self.device_id, None)
        self.events = patch("monolith.app.save_event").start()
        self.clock = patch("monolith.app.time.monotonic", return_value=0).start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        self.device.clear()
        self.device.update(self.original_device)
        monolith.apple_media_feed_states.clear()
        monolith.apple_media_feed_states.update(self.original_states)
        monolith.observed_states.clear()
        monolith.observed_states.update(self.original_observed)

    def status(self, playing=True, connected=True, state=None):
        monolith.update_homepod_status({
            "connected": connected,
            "playing": playing,
            "playback_state": state or ("playing" if playing else "paused"),
            "title": "Einmal um die Welt" if playing else None,
        })

    def test_disconnect_and_recovery_do_not_create_pause_start_pair(self):
        self.status()
        self.clock.return_value = 3
        self.status(False, connected=False, state="unknown")
        self.clock.return_value = 30
        self.status()
        self.events.assert_not_called()

    def test_short_pause_and_track_change_do_not_create_events(self):
        self.status()
        self.clock.return_value = 3
        self.status(False)
        self.clock.return_value = 6
        self.status()
        self.events.assert_not_called()

    def test_confirmed_pause_and_resume_are_logged_once(self):
        self.status()
        self.clock.return_value = 3
        self.status(False)
        self.clock.return_value = 12
        self.status(False)
        self.events.assert_not_called()
        self.clock.return_value = 13
        self.status(False)
        self.status(False)
        self.status()
        self.status()
        self.assertEqual(
            [call.kwargs["title"] for call in self.events.call_args_list],
            ["Pausiert", "Wiedergabe gestartet"],
        )
        self.assertEqual(self.events.call_args.kwargs["detail"], "Einmal um die Welt")

    def test_unknown_status_resets_pause_confirmation(self):
        self.status()
        self.clock.return_value = 3
        self.status(False)
        self.clock.return_value = 20
        self.status(False, state="unknown")
        self.clock.return_value = 30
        self.status(False)
        self.events.assert_not_called()
        self.clock.return_value = 40
        self.status(False)
        self.events.assert_called_once()

    def test_first_valid_status_is_a_baseline(self):
        self.status(False, connected=False, state="unknown")
        self.status()
        self.events.assert_not_called()

    def test_apple_tv_keeps_its_three_minute_pause_confirmation(self):
        device_id = "device_media_01"
        device = monolith.devices[device_id]
        monolith.apple_media_feed_states.pop(device_id, None)
        for now, playing in [(0, True), (3, False), (13, False), (183, False)]:
            self.clock.return_value = now
            monolith.update_apple_media_feed_state(
                device_id, device, {}, playing,
                pause_confirm_seconds=monolith.APPLE_TV_FEED_PAUSE_CONFIRM_SECONDS,
            )
            if now < 183:
                self.events.assert_not_called()
        self.events.assert_called_once()

    def test_apple_tv_power_off_is_logged_immediately(self):
        device_id = "device_media_01"
        device = monolith.devices[device_id]
        monolith.apple_media_feed_states[device_id] = {
            "active": True, "pause_started_at": None,
        }
        monolith.update_apple_media_feed_state(
            device_id, device, {"power_state": "off"}, False,
            pause_confirm_seconds=monolith.APPLE_TV_FEED_PAUSE_CONFIRM_SECONDS,
        )
        self.events.assert_called_once()


class HomePodMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_metadata_failure_is_not_reported_as_paused(self):
        monitor = HomePodMonitor(Mock())
        connection = Mock()
        connection.metadata.playing = AsyncMock(side_effect=RuntimeError("timeout"))
        connection.close.return_value = None
        with patch("monolith.homepod.pyatv.connect", new=AsyncMock(return_value=connection)):
            self.assertIsNone(await monitor._get_playback(Mock()))
        connection.close.assert_called_once()

    async def test_failed_metadata_publishes_unknown_status(self):
        callback = Mock()
        monitor = HomePodMonitor(callback)
        with (
            patch.object(monitor, "_get_playback", new=AsyncMock(return_value=None)),
            patch("builtins.print"),
        ):
            await monitor._publish_config(Mock())
        status = callback.call_args.args[0]
        self.assertFalse(status["connected"])
        self.assertEqual(status["playback_state"], "unknown")
        self.assertEqual(status["value"], "Unbekannt")


if __name__ == "__main__":
    unittest.main()
