import unittest

from monolith.homekit_config import read_homekit_pin


class HomeKitConfigurationTests(unittest.TestCase):
    def test_configured_pin_is_encoded_for_hap(self):
        self.assertEqual(read_homekit_pin({"HOMEKIT_PIN": " 135-79-246 "}), b"135-79-246")

    def test_missing_or_malformed_pin_fails_without_exposing_input(self):
        for value in ("", "12345678", "secret-test-value", "１２３-４５-６７８"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as error:
                    read_homekit_pin({"HOMEKIT_PIN": value})
                if value:
                    self.assertNotIn(value, str(error.exception))
        with self.assertRaises(ValueError):
            read_homekit_pin({})
