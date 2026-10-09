"""Dashboard entry point used by the Pi systemd service."""

from monolith.app import app, main


if __name__ == "__main__":
    main()
