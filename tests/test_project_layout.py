"""Protect service entry points and resource paths after moving the backend."""

import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch

from monolith import app as backend


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProjectLayoutTests(unittest.TestCase):
    def test_dashboard_entry_point_exports_the_backend_app_and_start_function(self):
        entry = runpy.run_path(str(PROJECT_ROOT / "app.py"))
        self.assertIs(entry["app"], backend.app)
        self.assertIs(entry["main"], backend.main)

    def test_homekit_entry_point_runs_the_moved_bridge(self):
        # Replace the runner so no driver, socket or pairing state is created.
        with patch("runpy.run_module") as runner:
            runpy.run_path(str(PROJECT_ROOT / "homekit_bridge.py"), run_name="__main__")
        runner.assert_called_once_with("monolith.homekit_bridge", run_name="__main__")

    def test_resources_and_default_data_directory_still_use_the_project_root(self):
        self.assertEqual(Path(backend.app.template_folder), PROJECT_ROOT / "templates")
        self.assertEqual(Path(backend.app.static_folder), PROJECT_ROOT / "static")
        with patch.dict(os.environ, {}, clear=True):
            paths = runpy.run_path(str(PROJECT_ROOT / "monolith" / "data_paths.py"))
        self.assertEqual(paths["DATA_DIR"], PROJECT_ROOT)

    def test_configured_runtime_directory_remains_independent_of_source_location(self):
        directory = PROJECT_ROOT / ".verification" / "runtime"
        with patch.dict(os.environ, {"MONOLITH_DATA_DIR": str(directory)}):
            paths = runpy.run_path(str(PROJECT_ROOT / "monolith" / "data_paths.py"))
        self.assertEqual(paths["data_path"]("monolith.db"), directory / "monolith.db")
