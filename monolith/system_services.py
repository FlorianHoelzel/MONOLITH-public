import json
import os
import platform
import re
import socket
import subprocess
from datetime import datetime, timezone


SERVICE_DEFINITIONS = (
    {
        "id": "monolith",
        "name": "MONOLITH",
        "unit": "monolith.service",
        "description": "Dashboard und API",
        "icon": "ti-layout-dashboard",
    },
    {
        "id": "homekit",
        "name": "HomeKit Bridge",
        "unit": "monolith-homekit.service",
        "description": "Apple Home Integration",
        "icon": "ti-home-link",
    },
    {
        "id": "matterbridge",
        "name": "Matterbridge",
        "unit": os.getenv(
            "MATTERBRIDGE_SERVICE_NAME",
            "robovac-matterbridge.service",
        ),
        "description": "Matter Gerätebrücke",
        "icon": "ti-circuit-switch-open",
    },
)

SYSTEMD_PROPERTIES = (
    "Id",
    "LoadState",
    "ActiveState",
    "SubState",
    "MainPID",
    "ActiveEnterTimestamp",
    "ActiveEnterTimestampMonotonic",
    "MemoryCurrent",
    "NRestarts",
)

STATUS_LABELS = {
    "active": "Aktiv",
    "inactive": "Gestoppt",
    "failed": "Fehler",
    "activating": "Startet",
    "deactivating": "Stoppt",
    "reloading": "Lädt neu",
    "unknown": "Nicht verfügbar",
}

JOURNAL_CURSOR_PATTERN = re.compile(
    r"^[A-Za-z0-9;:=_\-\.]+$"
)
ANSI_ESCAPE_PATTERN = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))"
)


def _parse_systemctl_output(output):
    properties = {}

    for line in output.splitlines():
        key, separator, value = line.partition("=")

        if separator:
            properties[key] = value

    return properties


def _parse_integer(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_process_memory_bytes(pid):
    if not pid or pid <= 0:
        return None

    try:
        with open(
            f"/proc/{pid}/status",
            "r",
            encoding="utf-8",
        ) as status_file:
            for line in status_file:
                if not line.startswith("VmRSS:"):
                    continue

                fields = line.split()

                if len(fields) < 2:
                    return None

                return int(fields[1]) * 1024
    except (OSError, ValueError):
        return None

    return None


def _calculate_uptime_seconds(properties):
    entered_at = _parse_integer(
        properties.get(
            "ActiveEnterTimestampMonotonic"
        )
    )

    if not entered_at:
        return None

    try:
        with open(
            "/proc/uptime",
            "r",
            encoding="utf-8",
        ) as uptime_file:
            system_uptime_microseconds = int(
                float(
                    uptime_file.read().split()[0]
                )
                * 1_000_000
            )
    except (OSError, ValueError, IndexError):
        return None

    return max(
        0,
        (
            system_uptime_microseconds
            - entered_at
        )
        // 1_000_000,
    )


def _service_payload(definition, properties=None):
    properties = properties or {}
    load_state = properties.get(
        "LoadState",
        "unknown",
    )
    active_state = properties.get(
        "ActiveState",
        "unknown",
    )

    if load_state == "not-found":
        active_state = "unknown"

    pid = _parse_integer(
        properties.get("MainPID")
    )
    memory_bytes = _parse_integer(
        properties.get("MemoryCurrent")
    )

    if (
        memory_bytes is None
        and active_state == "active"
    ):
        memory_bytes = _read_process_memory_bytes(pid)

    return {
        **definition,
        "state": active_state,
        "status_label": STATUS_LABELS.get(
            active_state,
            "Unbekannt",
        ),
        "sub_state": properties.get(
            "SubState"
        ) or None,
        "pid": pid,
        "memory_bytes": memory_bytes,
        "restart_count": _parse_integer(
            properties.get("NRestarts")
        ),
        "started_at": properties.get(
            "ActiveEnterTimestamp"
        ) or None,
        "uptime_seconds": (
            _calculate_uptime_seconds(
                properties
            )
            if active_state == "active"
            else None
        ),
    }


def _read_systemd_service(definition):
    try:
        result = subprocess.run(
            [
                "systemctl",
                "show",
                definition["unit"],
                "--no-pager",
                f"--property={','.join(SYSTEMD_PROPERTIES)}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (
        FileNotFoundError,
        OSError,
        subprocess.TimeoutExpired,
    ):
        return _service_payload(
            definition
        )

    return _service_payload(
        definition,
        _parse_systemctl_output(
            result.stdout
        ),
    )


def _service_name_for_unit(unit):
    for definition in SERVICE_DEFINITIONS:
        if definition["unit"] == unit:
            return definition["name"]

    return unit


def _normalize_journal_message(value):
    if isinstance(value, list):
        try:
            value = bytes(value).decode(
                "utf-8",
                errors="replace",
            )
        except (TypeError, ValueError):
            value = "Binäre Protokollzeile"

    message = str(value or "")
    message = ANSI_ESCAPE_PATTERN.sub(
        "",
        message,
    )
    message = re.sub(
        r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
        "",
        message,
    )

    return message[:4000]


def _parse_journal_entry(line):
    try:
        entry = json.loads(line)
    except (TypeError, ValueError):
        return None

    timestamp = _parse_integer(
        entry.get("__REALTIME_TIMESTAMP")
    )
    unit = (
        entry.get("_SYSTEMD_UNIT")
        or entry.get("_SYSTEMD_USER_UNIT")
        or "system"
    )
    priority = _parse_integer(
        entry.get("PRIORITY")
    )

    return {
        "cursor": entry.get("__CURSOR"),
        "timestamp": (
            datetime.fromtimestamp(
                timestamp / 1_000_000,
                tz=timezone.utc,
            ).isoformat()
            if timestamp is not None
            else None
        ),
        "unit": unit,
        "service": _service_name_for_unit(unit),
        "priority": (
            priority
            if priority is not None
            else 6
        ),
        "message": _normalize_journal_message(
            entry.get("MESSAGE")
        ),
    }


def _compact_journal_entries(entries):
    compacted = []
    last_purifier_messages = {}
    last_lg_tv_messages = {}

    for entry in entries:
        message = entry["message"].strip()

        if (
            "MONOLITH SYNC" in message
            or (
                message
                and set(message) == {"="}
            )
            or message.startswith(
                "[sensor_hallway_pm25]"
            )
            or message.startswith(
                "[sensor_hallway_iai]"
            )
        ):
            continue

        if message.startswith(
            "[device_air_filter_01_"
        ):
            timestamp = entry.get("timestamp")
            current_time = None

            if timestamp:
                try:
                    current_time = (
                        datetime.fromisoformat(
                            timestamp
                        ).timestamp()
                    )
                except ValueError:
                    pass

            previous_time = (
                last_purifier_messages.get(
                    message
                )
            )

            if (
                current_time is not None
                and previous_time is not None
                and current_time - previous_time < 60
            ):
                continue

            last_purifier_messages[message] = (
                current_time
            )

        if message.startswith("[LG TV]"):
            timestamp = entry.get("timestamp")
            current_time = None

            if timestamp:
                try:
                    current_time = (
                        datetime.fromisoformat(
                            timestamp
                        ).timestamp()
                    )
                except ValueError:
                    pass

            previous_time = last_lg_tv_messages.get(
                message
            )

            if (
                current_time is not None
                and previous_time is not None
                and current_time - previous_time < 300
            ):
                continue

            last_lg_tv_messages[message] = current_time

        compacted.append(entry)

    return compacted


def get_system_service_logs(cursor=None, line_count=100):
    systemd_available = (
        os.name == "posix"
        and os.path.isdir("/run/systemd/system")
    )

    if not systemd_available:
        return {
            "success": True,
            "supported": False,
            "cursor": None,
            "entries": [],
        }

    valid_cursor = (
        cursor
        if (
            cursor
            and len(cursor) <= 1024
            and JOURNAL_CURSOR_PATTERN.fullmatch(
                cursor
            )
        )
        else None
    )
    command = [
        "journalctl",
        "--no-pager",
        "--quiet",
        "--output=json",
    ]

    for definition in SERVICE_DEFINITIONS:
        command.extend([
            "--unit",
            definition["unit"],
        ])

    if valid_cursor:
        command.extend([
            "--after-cursor",
            valid_cursor,
        ])
    else:
        command.extend([
            "--lines",
            str(
                max(
                    1,
                    min(line_count, 200),
                )
            ),
        ])

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (
        FileNotFoundError,
        OSError,
        subprocess.TimeoutExpired,
    ):
        return {
            "success": False,
            "supported": True,
            "cursor": valid_cursor,
            "entries": [],
            "error": "Journal konnte nicht gelesen werden.",
        }

    if result.returncode != 0:
        return {
            "success": False,
            "supported": True,
            "cursor": valid_cursor,
            "entries": [],
            "error": "Keine Berechtigung für das Systemjournal.",
        }

    raw_entries = []

    for line in result.stdout.splitlines():
        parsed = _parse_journal_entry(line)

        if parsed is not None:
            raw_entries.append(parsed)

    next_cursor = valid_cursor

    if raw_entries:
        next_cursor = raw_entries[-1]["cursor"]

    entries = _compact_journal_entries(
        raw_entries
    )

    return {
        "success": True,
        "supported": True,
        "cursor": next_cursor,
        "entries": entries,
    }


def get_system_services():
    systemd_available = (
        os.name == "posix"
        and os.path.isdir("/run/systemd/system")
    )

    if systemd_available:
        services = [
            _read_systemd_service(definition)
            for definition in SERVICE_DEFINITIONS
        ]
        source = "systemd"
    else:
        services = [
            _service_payload(definition)
            for definition in SERVICE_DEFINITIONS
        ]
        services[0].update({
            "state": "active",
            "status_label": "Entwicklung",
            "sub_state": "running",
            "pid": os.getpid(),
        })
        source = "development"

    active_count = sum(
        service["state"] == "active"
        for service in services
    )
    unavailable_count = sum(
        service["state"] == "unknown"
        for service in services
    )

    if active_count == len(services):
        health = "healthy"
    elif unavailable_count == len(services):
        health = "unavailable"
    else:
        health = "degraded"

    return {
        "success": True,
        "checked_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "host": socket.gethostname(),
        "platform": platform.system(),
        "source": source,
        "summary": {
            "active": active_count,
            "total": len(services),
            "health": health,
        },
        "services": services,
    }
