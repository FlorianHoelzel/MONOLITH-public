"""HomeKit entry point used by the Pi systemd service."""

import runpy


if __name__ == "__main__":
    runpy.run_module("monolith.homekit_bridge", run_name="__main__")
