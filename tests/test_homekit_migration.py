import importlib.util
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "homekit_pin_migration",
    Path(__file__).resolve().parents[1] / "deploy" / "migrate-homekit-pin.py",
)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class HomeKitPinMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = Path(self.directory.name) / "private.env"
        self.recovery = Path(self.directory.name) / "pin"
        self.recovery.write_text("135-79-246", encoding="utf-8")

    def test_recovery_after_source_was_replaced_preserves_other_settings(self):
        self.environment.write_text("OTHER=value\nHOMEKIT_PIN=invalid\n", encoding="utf-8")
        self.assertTrue(migration.migrate(None, self.environment, self.recovery))
        self.assertEqual(self.environment.read_text(encoding="utf-8"),
                         "OTHER=value\nHOMEKIT_PIN=invalid\nHOMEKIT_PIN=135-79-246\n")
        self.assertFalse(migration.migrate(None, self.environment, self.recovery))

    def test_existing_valid_pin_is_preserved(self):
        original = 'HOMEKIT_PIN="246-80-135"\n'
        self.environment.write_text(original, encoding="utf-8")
        self.assertFalse(migration.migrate(None, self.environment, self.recovery))
        self.assertEqual(self.environment.read_text(encoding="utf-8"), original)

    def test_invalid_recovery_does_not_modify_configuration(self):
        self.environment.write_text("OTHER=value\n", encoding="utf-8")
        self.recovery.write_text("private-invalid-value", encoding="utf-8")
        with self.assertRaises(RuntimeError) as error:
            migration.migrate(None, self.environment, self.recovery)
        self.assertNotIn("private-invalid-value", str(error.exception))
        self.assertEqual(self.environment.read_text(encoding="utf-8"), "OTHER=value\n")

    def test_legacy_source_migration_remains_supported(self):
        source = Path(self.directory.name) / "old_bridge.py"
        source.write_text('HOMEKIT_PIN = b"135-79-246"\n', encoding="utf-8")
        self.assertTrue(migration.migrate(source, self.environment))
        self.assertEqual(self.environment.read_text(encoding="utf-8"), "HOMEKIT_PIN=135-79-246\n")
