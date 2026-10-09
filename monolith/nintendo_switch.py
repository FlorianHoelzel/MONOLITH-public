"""Read-only Switch status from the router inventory."""

import logging
import os
import threading
import time
from copy import deepcopy

from fritzconnection.lib.fritzhosts import FritzHosts

from monolith.devices import devices
from monolith.network_monitor import FRITZBOX_ADDRESS, FRITZBOX_USER, FRITZBOX_PASSWORD


SWITCH_MAC = os.getenv("NINTENDO_SWITCH_MAC", "").strip().upper().replace("-", ":")
SWITCH_IP = os.getenv("NINTENDO_SWITCH_IP", "").strip()
SWITCH_ROOM = (
    os.getenv("NINTENDO_SWITCH_ROOM", "").strip()
    or devices["device_console_01"]["room"]
)

CHECK_INTERVAL_SECONDS = 3
STALE_AFTER_SECONDS = 60


def network_status(snapshot):
    # A failed router inventory must never turn an unknown status into offline.
    if not snapshot.get("success") or not snapshot.get("inventory_available", False):
        return {"network_connected": None, "address": SWITCH_IP}
    for device in snapshot.get("devices", []):
        mac = str(device.get("mac") or "").upper().replace("-", ":")
        if (SWITCH_MAC and mac == SWITCH_MAC) or (not SWITCH_MAC and device.get("ip") == SWITCH_IP):
            return {"network_connected": bool(device.get("active")), "address": device.get("ip") or SWITCH_IP}
    return {"network_connected": None, "address": SWITCH_IP}


def status_label(status):
    if status.get("network_connected") is True:
        return "An"
    if status.get("network_connected") is False:
        return "Aus"
    return "Unbekannt"


class SwitchMonitor:
    def __init__(self, on_event=None):
        self.on_event = on_event
        self.last_known_state = None
        self.last_confirmed_at = None
        self.hosts = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.status = {
            "value": "Unbekannt",
            "network_connected": None,
            "address": SWITCH_IP,
        }

    def get_status(self):
        with self.lock:
            status = deepcopy(self.status)
            last_confirmed_at = self.last_confirmed_at
        if last_confirmed_at is not None and time.monotonic() - last_confirmed_at > STALE_AFTER_SECONDS:
            status.update(network_connected=None, value="Unbekannt", status_stale=True)
        return status

    def read_status(self):
        if not (FRITZBOX_ADDRESS and FRITZBOX_USER and FRITZBOX_PASSWORD and SWITCH_MAC):
            return {"network_connected": None, "address": SWITCH_IP}
        if self.hosts is None:
            self.hosts = FritzHosts(
                address=FRITZBOX_ADDRESS, user=FRITZBOX_USER,
                password=FRITZBOX_PASSWORD, timeout=2,
            )
        entry = self.hosts.get_specific_host_entry(SWITCH_MAC)
        active = entry.get("NewActive")
        if active in ("1", "0"):
            active = active == "1"
        if not isinstance(active, bool):
            active = None
        return {"network_connected": active, "address": entry.get("NewIPAddress") or SWITCH_IP}

    def refresh(self):
        status = self.get_status()
        try:
            observed = self.read_status()
        except Exception:
            observed = {"network_connected": None}
        if isinstance(observed.get("network_connected"), bool):
            status.update(observed)
            status["status_stale"] = False
            self.last_confirmed_at = time.monotonic()
        else:
            # Retain a confirmed state for brief router failures, but expire it.
            status["status_stale"] = True
        status["value"] = status_label(status)
        with self.lock:
            self.status = status
        current_state = status["network_connected"]
        if isinstance(current_state, bool):
            if self.last_known_state is not None and current_state != self.last_known_state and self.on_event:
                self.on_event(
                    event_type="device",
                    source_id="device_console_01",
                    room=SWITCH_ROOM,
                    title=f"{devices['device_console_01']['name']} " + ("eingeschaltet" if current_state else "ausgeschaltet"),
                )
            self.last_known_state = current_state

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, daemon=True, name="MONOLITH-Switch")
        self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            started_at = time.monotonic()
            try:
                self.refresh()
            except Exception as error:
                logging.getLogger(__name__).warning("Switch-Abfrage fehlgeschlagen (%s)", type(error).__name__)
            self.stop_event.wait(max(0.1, CHECK_INTERVAL_SECONDS - (time.monotonic() - started_at)))


switch_monitor = SwitchMonitor()


def get_switch_status():
    return switch_monitor.get_status()


def start_switch_monitor(on_event=None):
    switch_monitor.on_event = on_event
    switch_monitor.start()
