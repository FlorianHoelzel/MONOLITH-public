import glob
import os
import platform
import re
import shutil
import socket
import subprocess
import time
from datetime import datetime, timedelta, timezone


THROTTLE_FLAGS = {
    0: "Unterspannung erkannt",
    1: "CPU-Takt begrenzt",
    2: "Aktuell gedrosselt",
    3: "Temperaturgrenze erreicht",
    16: "Unterspannung seit dem Start",
    17: "Taktbegrenzung seit dem Start",
    18: "Drosselung seit dem Start",
    19: "Temperaturgrenze seit dem Start",
}


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except (OSError, UnicodeError):
        return None


def _parse_key_values(value, separator=":"):
    values = {}

    for line in (value or "").splitlines():
        key, marker, raw_value = line.partition(separator)

        if marker:
            values[key.strip()] = raw_value.strip()

    return values


def _read_os_release():
    values = _parse_key_values(
        _read_text("/etc/os-release"),
        separator="=",
    )

    return {
        key: value.strip('"')
        for key, value in values.items()
    }


def _read_uptime_seconds():
    value = _read_text("/proc/uptime")

    try:
        return max(0, int(float(value.split()[0])))
    except (AttributeError, IndexError, ValueError):
        return None


def _read_cpu_times():
    value = _read_text("/proc/stat")

    if not value:
        return None

    fields = value.splitlines()[0].split()

    if not fields or fields[0] != "cpu":
        return None

    try:
        times = [int(item) for item in fields[1:]]
    except ValueError:
        return None

    if len(times) < 4:
        return None

    idle = times[3] + (times[4] if len(times) > 4 else 0)
    return sum(times), idle


def _read_cpu_usage(sample_seconds=0.08):
    first = _read_cpu_times()

    if first is None:
        return None

    time.sleep(sample_seconds)
    second = _read_cpu_times()

    if second is None:
        return None

    total_delta = second[0] - first[0]
    idle_delta = second[1] - first[1]

    if total_delta <= 0:
        return None

    return round(
        max(
            0.0,
            min(100.0, 100 * (1 - idle_delta / total_delta)),
        ),
        1,
    )


def _read_load_average():
    try:
        values = os.getloadavg()
    except (AttributeError, OSError):
        return [None, None, None]

    return [round(value, 2) for value in values]


def _read_cpu_frequency_mhz():
    for path in (
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq",
        "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq",
    ):
        value = _read_text(path)

        try:
            return round(int(value) / 1000)
        except (TypeError, ValueError):
            continue

    cpuinfo = _read_text("/proc/cpuinfo") or ""
    match = re.search(
        r"^cpu MHz\s*:\s*([\d.]+)$",
        cpuinfo,
        flags=re.MULTILINE,
    )

    return round(float(match.group(1))) if match else None


def _read_memory():
    values = _parse_key_values(
        _read_text("/proc/meminfo")
    )

    def bytes_for(key):
        match = re.search(r"\d+", values.get(key, ""))
        return int(match.group()) * 1024 if match else None

    total = bytes_for("MemTotal")
    available = bytes_for("MemAvailable")
    swap_total = bytes_for("SwapTotal")
    swap_free = bytes_for("SwapFree")

    if total is None or available is None:
        return None, None

    used = max(0, total - available)
    memory = {
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "usage_percent": round(used / total * 100, 1) if total else 0,
    }

    swap = None

    if swap_total is not None and swap_free is not None:
        swap_used = max(0, swap_total - swap_free)
        swap = {
            "total_bytes": swap_total,
            "used_bytes": swap_used,
            "free_bytes": swap_free,
            "usage_percent": (
                round(swap_used / swap_total * 100, 1)
                if swap_total
                else 0
            ),
        }

    return memory, swap


def _read_temperature():
    candidates = glob.glob(
        "/sys/class/thermal/thermal_zone*/temp"
    )

    for path in candidates:
        value = _read_text(path)

        try:
            temperature = float(value)
        except (TypeError, ValueError):
            continue

        if temperature > 1000:
            temperature /= 1000

        if 0 <= temperature <= 120:
            return round(temperature, 1)

    return None


def _read_throttling():
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (
        FileNotFoundError,
        OSError,
        subprocess.TimeoutExpired,
    ):
        return None

    match = re.search(
        r"0x([0-9a-fA-F]+)",
        result.stdout,
    )

    if result.returncode != 0 or not match:
        return None

    raw_value = int(match.group(1), 16)
    issues = [
        label
        for bit, label in THROTTLE_FLAGS.items()
        if raw_value & (1 << bit)
    ]

    return {
        "raw": f"0x{raw_value:x}",
        "active": bool(raw_value & 0xF),
        "occurred": bool(raw_value & 0xF0000),
        "issues": issues,
    }


def _read_default_interface():
    value = _read_text("/proc/net/route") or ""

    for line in value.splitlines()[1:]:
        fields = line.split()

        if len(fields) > 3 and fields[1] == "00000000":
            try:
                flags = int(fields[3], 16)
            except ValueError:
                continue

            if flags & 0x2:
                return fields[0]

    return None


def _read_ipv4_address():
    connection = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )

    try:
        connection.connect(("192.0.2.1", 80))
        return connection.getsockname()[0]
    except OSError:
        return None
    finally:
        connection.close()


def _read_network():
    interface = _read_default_interface()

    if not interface:
        return {
            "interface": None,
            "ipv4": _read_ipv4_address(),
            "rx_bytes": None,
            "tx_bytes": None,
        }

    def counter(name):
        value = _read_text(
            f"/sys/class/net/{interface}/statistics/{name}"
        )
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return {
        "interface": interface,
        "ipv4": _read_ipv4_address(),
        "rx_bytes": counter("rx_bytes"),
        "tx_bytes": counter("tx_bytes"),
    }


def _usage_state(value, warning=85, critical=95):
    if value is None:
        return "unknown"
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "healthy"


def _temperature_state(value):
    return _usage_state(value, warning=70, critical=80)


def _make_check(identifier, label, value, detail, state, icon):
    return {
        "id": identifier,
        "label": label,
        "value": value,
        "detail": detail,
        "state": state,
        "icon": icon,
    }


def _health_checks(temperature, storage, throttling, reboot_required):
    temperature_state = _temperature_state(temperature)
    storage_state = _usage_state(
        storage.get("usage_percent") if storage else None
    )

    checks = [
        _make_check(
            "temperature",
            "Temperatur",
            f"{temperature:.1f} °C" if temperature is not None else "Nicht verfügbar",
            "Unter 70 °C liegt der Pi im grünen Bereich.",
            temperature_state,
            "ti-temperature",
        ),
        _make_check(
            "throttling",
            "Spannung und Takt",
            (
                "Drosselung aktiv"
                if throttling and throttling["active"]
                else "Früheres Ereignis"
                if throttling and throttling["occurred"]
                else "Unauffällig"
                if throttling is not None
                else "Nicht verfügbar"
            ),
            (
                ", ".join(throttling["issues"])
                if throttling and throttling["issues"]
                else "Keine Unterspannung oder thermische Drosselung erkannt."
            ),
            (
                "critical"
                if throttling and throttling["active"]
                else "warning"
                if throttling and throttling["occurred"]
                else "healthy"
                if throttling is not None
                else "unknown"
            ),
            "ti-bolt",
        ),
        _make_check(
            "storage",
            "Systemspeicher",
            (
                f"{storage['usage_percent']:.1f} % belegt"
                if storage
                else "Nicht verfügbar"
            ),
            "Ab 85 % Belegung wird eine Warnung angezeigt.",
            storage_state,
            "ti-device-sd-card",
        ),
        _make_check(
            "reboot",
            "Systemneustart",
            "Erforderlich" if reboot_required else "Nicht erforderlich",
            (
                "Ein installiertes Update benötigt einen Neustart."
                if reboot_required
                else "Keine ausstehenden Neustarts erkannt."
            ),
            "warning" if reboot_required else "healthy",
            "ti-refresh-alert",
        ),
    ]

    return checks


def get_raspberry_pi_status():
    os_release = _read_os_release()
    uptime_seconds = _read_uptime_seconds()
    memory, swap = _read_memory()
    temperature = _read_temperature()
    throttling = _read_throttling()
    network = _read_network()
    disk_path = "/" if os.name == "posix" else os.path.abspath(os.sep)

    try:
        disk = shutil.disk_usage(disk_path)
        storage = {
            "path": disk_path,
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "usage_percent": round(disk.used / disk.total * 100, 1),
        }
    except OSError:
        storage = None

    reboot_required = os.path.exists("/var/run/reboot-required")
    checks = _health_checks(
        temperature,
        storage,
        throttling,
        reboot_required,
    )
    check_states = [check["state"] for check in checks]

    if "critical" in check_states:
        health_state = "critical"
        health_label = "Handlungsbedarf"
    elif "warning" in check_states:
        health_state = "warning"
        health_label = "Hinweis prüfen"
    elif all(state == "unknown" for state in check_states):
        health_state = "unknown"
        health_label = "Nicht verfügbar"
    else:
        health_state = "healthy"
        health_label = "System stabil"

    load_average = _read_load_average()
    booted_at = (
        datetime.now(timezone.utc) - timedelta(seconds=uptime_seconds)
        if uptime_seconds is not None
        else None
    )
    model = (
        (_read_text("/proc/device-tree/model") or "").rstrip("\x00")
        or platform.machine()
        or "Unbekannt"
    )

    return {
        "success": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source": "raspberry-pi" if os.name == "posix" else "development",
        "health": {
            "state": health_state,
            "label": health_label,
        },
        "identity": {
            "hostname": socket.gethostname(),
            "model": model,
            "operating_system": (
                os_release.get("PRETTY_NAME")
                or platform.platform()
            ),
            "kernel": platform.release(),
            "architecture": platform.machine(),
        },
        "metrics": {
            "cpu": {
                "usage_percent": _read_cpu_usage(),
                "logical_cores": os.cpu_count(),
                "frequency_mhz": _read_cpu_frequency_mhz(),
                "load_1": load_average[0],
                "load_5": load_average[1],
                "load_15": load_average[2],
            },
            "temperature": {
                "celsius": temperature,
                "state": _temperature_state(temperature),
            },
            "memory": memory,
            "swap": swap,
            "storage": storage,
            "network": network,
            "uptime_seconds": uptime_seconds,
            "booted_at": booted_at.isoformat() if booted_at else None,
        },
        "checks": checks,
    }
