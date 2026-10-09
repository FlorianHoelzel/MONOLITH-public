"""Exercise the real motion switch without starting the HomeKit driver."""
import ast
import json
import math
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests


class FakeAccessory:
    def __init__(self, driver, display_name, aid):
        self.display_name = display_name

    def add_preload_service(self, name):
        return Mock()


def load_motion_switch(directory):
    # The module creates its driver at import time. Compile only the actual
    # class so tests cannot open sockets or touch pairing / runtime files.
    source = (Path(__file__).resolve().parents[1] / "monolith" / "homekit_bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                and n.name == "MotionTriggerSwitch")
    namespace = {
        "Accessory": FakeAccessory, "CATEGORY_SWITCH": 8,
        "data_path": lambda name: Path(directory) / name,
        "json": json, "math": math, "os": os, "tempfile": tempfile,
        "time": time, "requests": requests,
        "MONOLITH_EVENT_API": "http://unused.invalid/api/event",
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), source, "exec"), namespace)
    return namespace["MotionTriggerSwitch"]


class MotionSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.switch_class = load_motion_switch(self.directory.name)
        self.post = patch.object(requests, "post", return_value=Mock()).start()
        self.addCleanup(patch.stopall)
        patch.object(time, "time", return_value=1000).start()

    def switch(self, source="motion_livingroom"):
        timeout = 900 if source == "motion_livingroom" else 180
        return self.switch_class(None, "Motion", source, source, timeout, 9)

    def test_restart_keeps_session_and_last_extension(self):
        self.switch().set_state(True)
        with patch.object(time, "time", return_value=1800):
            self.switch().set_state(True)
        with patch.object(time, "time", return_value=2600):
            restarted = self.switch()
            self.assertEqual(restarted.last_motion, 1800)
            restarted.set_state(True)
        self.assertEqual(self.post.call_count, 1)
        restarted.on_characteristic.set_value.assert_called_once_with(False)

    def test_expired_session_creates_event_after_restart(self):
        self.switch().set_state(True)
        with patch.object(time, "time", return_value=1900):
            self.switch().set_state(True)
        self.assertEqual(self.post.call_count, 2)

    def test_failed_event_is_retried_after_restart(self):
        self.post.side_effect = requests.ConnectionError("offline")
        self.switch().set_state(True)
        restarted = self.switch()
        self.assertFalse(restarted.session_logged)
        self.post.side_effect = None
        restarted.set_state(True)
        self.assertTrue(self.switch().session_logged)
        self.assertEqual(self.post.call_count, 2)

    def test_invalid_state_is_ignored(self):
        path = Path(self.directory.name) / "motion_livingroom_session.json"
        for contents in ('broken', 'null', '{"last_motion": "1000", "session_logged": true}',
                         '{"last_motion": NaN, "session_logged": true}'):
            with self.subTest(contents=contents):
                path.write_text(contents, encoding="utf-8")
                self.assertIsNone(self.switch().last_motion)

    def test_reset_does_not_extend_session(self):
        switch = self.switch()
        switch.set_state(True)
        with patch.object(time, "time", return_value=1500):
            switch.set_state(False)
        self.assertEqual(self.switch().last_motion, 1000)
        self.assertEqual(self.post.call_count, 1)

    def test_all_rooms_resume_and_expire_independently(self):
        sources = ("motion_bedroom", "motion_kitchen", "motion_hallway", "motion_livingroom")
        for source in sources:
            with self.subTest(source=source):
                self.switch(source).set_state(True)
                with patch.object(time, "time", return_value=1100):
                    restarted = self.switch(source)
                    self.assertEqual(restarted.last_motion, 1000)
                    self.assertTrue(restarted.session_logged)
                    restarted.set_state(True)
        self.assertEqual(self.post.call_count, 4)
        self.assertEqual(len(list(Path(self.directory.name).iterdir())), 4)
        with patch.object(time, "time", return_value=1280):
            for source in sources:
                self.switch(source).set_state(True)
        # Three normal rooms expire at 180 seconds, living room stays active.
        self.assertEqual(self.post.call_count, 7)
        # Each room retains its own most recent movement time.
        with patch.object(time, "time", return_value=1300):
            self.switch("motion_kitchen").set_state(True)
        self.assertEqual(self.switch("motion_kitchen").last_motion, 1300)
        self.assertEqual(self.switch("motion_bedroom").last_motion, 1280)

    def test_write_failure_does_not_prevent_switch_reset(self):
        switch = self.switch()
        with patch.object(os, "replace", side_effect=OSError("read-only")):
            switch.set_state(True)
        switch.on_characteristic.set_value.assert_called_once_with(False)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
