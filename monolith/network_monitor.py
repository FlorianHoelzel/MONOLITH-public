import json
import os
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone

from dotenv import load_dotenv
from fritzconnection.lib.fritzhosts import FritzHosts
from fritzconnection.lib.fritzstatus import FritzStatus
from fritzconnection.lib.fritzwlan import FritzWLAN

from monolith.devices import devices
from monolith.database import (
    get_network_devices_memory,
    get_network_events,
    get_network_state,
    get_network_traffic,
    remember_network_device,
    save_network_event,
    save_network_traffic,
    set_network_state,
    update_network_device_flags,
)


load_dotenv()


FRITZBOX_ADDRESS = os.getenv("FRITZBOX_ADDRESS", "").strip()
FRITZBOX_USER = os.getenv("FRITZBOX_USER", "").strip()
FRITZBOX_PASSWORD = os.getenv("FRITZBOX_PASSWORD", "")

REFRESH_INTERVAL_SECONDS = max(
    10,
    int(os.getenv("NETWORK_REFRESH_INTERVAL_SECONDS", "15")),
)
CACHE_SECONDS = max(3, min(REFRESH_INTERVAL_SECONDS, 10))


def _normalize_mac(value):
    value = str(value or "").strip().replace("-", ":").upper()
    return value if len(value) == 17 else ""


def _truthy(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {
        "1", "true", "yes", "on", "up", "connected", "enabled",
    }


def _number(value, default=None):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _iso_timestamp(timestamp):
    if not timestamp:
        return None
    return datetime.fromtimestamp(
        int(timestamp),
        tz=timezone.utc,
    ).isoformat().replace("+00:00", "Z")


def _friendly_error(error):
    name = error.__class__.__name__
    if isinstance(error, (TimeoutError, ConnectionError)):
        return "Zeitüberschreitung bei der FRITZ!Box-Abfrage"
    return f"FRITZ!Box-Abfrage fehlgeschlagen ({name})"


def _configured_devices():
    result = {}

    def add(mac, ip, name, room=None, device_type=None, important=False):
        normalized_mac = _normalize_mac(mac)
        entry = {
            "name": name,
            "room": room,
            "device_type": device_type,
            "important": bool(important),
        }
        if normalized_mac:
            result[("mac", normalized_mac)] = entry
        if ip:
            result[("ip", str(ip).strip())] = entry

    add(
        os.getenv("PC_MAC"),
        os.getenv("PC_IP"),
        devices["device_computer_01"]["name"],
        devices["device_computer_01"]["room"],
        "computer",
        True,
    )
    add(
        os.getenv("LG_TV_MAC"),
        os.getenv("LG_TV_IP"),
        devices["device_display_01"]["name"],
        devices["device_display_01"]["room"],
        "television",
    )
    add(None, os.getenv("HOMEPOD_IP"), devices["device_speaker_01"]["name"], devices["device_speaker_01"]["room"], "speaker")
    add(None, os.getenv("APPLE_TV_IP"), devices["device_media_01"]["name"], devices["device_media_01"]["room"], "media")
    add(
        os.getenv("NINTENDO_SWITCH_MAC", ""),
        os.getenv("NINTENDO_SWITCH_IP", ""),
        devices["device_console_01"]["name"],
        os.getenv("NINTENDO_SWITCH_ROOM", "").strip() or devices["device_console_01"]["room"],
        "console",
    )

    try:
        from monolith.presence import PEOPLE

        for person in PEOPLE.values():
            for device in person.get("devices", []):
                add(
                    device.get("mac"),
                    device.get("ip"),
                    f"{person.get('name', '')} {device.get('name', 'Gerät')}".strip(),
                    None,
                    device.get("id"),
                )
    except (ImportError, AttributeError):
        pass

    important_macs = {
        _normalize_mac(value)
        for value in os.getenv("NETWORK_IMPORTANT_MACS", "").split(",")
        if _normalize_mac(value)
    }
    for mac in important_macs:
        result.setdefault(("mac", mac), {
            "name": None,
            "room": None,
            "device_type": None,
            "important": True,
        })["important"] = True

    return result


def _get_value(data, *keys, default=None):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def _normalize_wlan_network(service, info, clients):
    band_value = str(_get_value(
        info,
        "NewOperatingFrequencyBand",
        "NewX_AVM-DE_FrequencyBand",
        default="",
    )).lower()
    ap_type = str(_get_value(info, "NewX_AVM-DE_APType", default="")).lower()
    ssid = str(_get_value(info, "NewSSID", default="WLAN"))
    is_guest = (
        "guest" in ap_type
        or "gast" in ssid.lower()
        or (service == 3 and not band_value)
    )

    if "6" in band_value:
        band = "6 GHz"
    elif "5" in band_value or service == 2:
        band = "5 GHz"
    elif "2" in band_value or service == 1:
        band = "2,4 GHz"
    else:
        band = "Gastnetz" if is_guest else f"WLAN {service}"

    return {
        "service": service,
        "band": band,
        "ssid": ssid,
        "enabled": _truthy(_get_value(info, "NewEnable", "NewStatus")),
        "channel": _number(_get_value(info, "NewChannel")),
        "guest": is_guest,
        "client_count": sum(1 for item in clients if _truthy(item.get("status"))),
        "utilization_percent": _number(_get_value(
            info,
            "NewX_AVM-DE_ChannelUtilization",
            "NewX_AVM-DE_Utilization",
        )),
    }


def _normalize_mesh(topology):
    raw_nodes = topology.get("nodes", []) if isinstance(topology, dict) else []
    nodes = {}
    interface_owner = {}

    for raw in raw_nodes:
        uid = str(raw.get("uid") or "")
        if not uid:
            continue
        interfaces = raw.get("node_interfaces") or []
        for interface in interfaces:
            if interface.get("uid"):
                interface_owner[str(interface["uid"])] = uid
        nodes[uid] = {
            "id": uid,
            "name": raw.get("device_name") or raw.get("device_model") or "Netzwerkgerät",
            "model": raw.get("device_model"),
            "manufacturer": raw.get("device_manufacturer"),
            "mac": _normalize_mac(raw.get("device_mac_address")),
            "role": raw.get("device_role"),
            "mesh": _truthy(raw.get("is_meshed") or raw.get("device_is_meshed")),
            "repeater": "repeater" in str(raw.get("device_model") or "").lower(),
            "children": [],
        }

    adjacency = {uid: [] for uid in nodes}
    seen_links = set()
    for raw in raw_nodes:
        for interface in raw.get("node_interfaces") or []:
            for link in interface.get("node_links") or []:
                left = str(link.get("node_1_uid") or "")
                right = str(link.get("node_2_uid") or "")
                left = nodes.get(left) and left or interface_owner.get(
                    str(link.get("node_interface_1_uid") or ""), left
                )
                right = nodes.get(right) and right or interface_owner.get(
                    str(link.get("node_interface_2_uid") or ""), right
                )
                if left not in nodes or right not in nodes or left == right:
                    continue
                key = tuple(sorted((left, right)))
                if key in seen_links:
                    continue
                seen_links.add(key)
                connection = {
                    "type": link.get("type") or interface.get("type"),
                    "state": link.get("state"),
                    "max_rx_kbit": _number(link.get("max_data_rate_rx")),
                    "max_tx_kbit": _number(link.get("max_data_rate_tx")),
                }
                adjacency[left].append((right, connection))
                adjacency[right].append((left, connection))

    root_id = next((
        uid for uid, node in nodes.items()
        if str(node.get("role") or "").lower() in {"master", "mesh_master", "gateway"}
    ), None)
    if not root_id:
        root_id = next((
            uid for uid, node in nodes.items()
            if "fritz!box" in str(node.get("model") or node.get("name") or "").lower()
            and not node.get("repeater")
        ), None)
    if not root_id and nodes:
        root_id = max(nodes, key=lambda uid: len(adjacency[uid]))

    visited = set()

    def build(uid, parent=None, connection=None):
        visited.add(uid)
        item = dict(nodes[uid])
        item["connection"] = connection
        item["children"] = [
            build(child_id, uid, child_connection)
            for child_id, child_connection in adjacency[uid]
            if child_id != parent and child_id not in visited
        ]
        return item

    roots = []
    if root_id:
        roots.append(build(root_id))
    for uid in nodes:
        if uid not in visited:
            roots.append(build(uid))

    access_points = {}

    def collect_access_points(node):
        for child in node.get("children", []):
            if child.get("mac"):
                access_points[child["mac"]] = node.get("name")
            collect_access_points(child)

    for root in roots:
        collect_access_points(root)

    repeaters = [
        {"id": node["id"], "name": node["name"]}
        for node in nodes.values()
        if node.get("repeater")
    ]
    return {
        "roots": roots,
        "node_count": len(nodes),
        "repeaters": repeaters,
        "access_points": access_points,
    }


class NetworkMonitor:
    def __init__(self):
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.running = False
        self.last_refresh_monotonic = 0
        self.last_result = None
        self.status = None
        self.hosts = None

    @property
    def configured(self):
        return bool(FRITZBOX_ADDRESS and FRITZBOX_USER and FRITZBOX_PASSWORD)

    def _connect(self):
        if not self.configured:
            raise RuntimeError("FRITZ!Box-Zugangsdaten fehlen")
        if self.status is None or self.hosts is None:
            kwargs = {
                "address": FRITZBOX_ADDRESS,
                "user": FRITZBOX_USER,
                "password": FRITZBOX_PASSWORD,
                "timeout": 6.0,
            }
            self.status = FritzStatus(**kwargs)
            self.hosts = FritzHosts(fc=self.status.fc)

    @staticmethod
    def _try(getter, default=None):
        try:
            return getter()
        except Exception:
            return default

    def _load_wlan(self):
        networks = []
        clients_by_mac = {}
        for service in range(1, 5):
            try:
                wlan = FritzWLAN(fc=self.status.fc, service=service)
                info = wlan.get_info()
                clients = wlan.get_hosts_info()
            except Exception:
                continue
            networks.append(_normalize_wlan_network(service, info, clients))
            for client in clients:
                mac = _normalize_mac(client.get("mac"))
                if not mac:
                    continue
                network = networks[-1]
                clients_by_mac[mac] = {
                    "band": network["band"],
                    "ssid": network["ssid"],
                    "signal_dbm": _number(client.get("signal")),
                    "speed_mbit": _number(client.get("speed")),
                    "wlan_service": service,
                }
        return networks, clients_by_mac

    def _record_events(self, result, old_memory, initialized):
        now = result["collected_at_unix"]
        internet = result["internet"]
        previous_connected = get_network_state("internet_connected")
        current_connected = "1" if internet.get("connected") else "0"
        if internet.get("available"):
            if previous_connected is not None and previous_connected != current_connected:
                connected = current_connected == "1"
                save_network_event(
                    "internet_restored" if connected else "internet_lost",
                    "Internetverbindung wiederhergestellt" if connected else "Internetverbindung verloren",
                    "Die FRITZ!Box meldet wieder eine aktive Verbindung."
                    if connected else "Die FRITZ!Box meldet keine aktive Internetverbindung.",
                    "success" if connected else "critical",
                    dedupe_key=f"internet:{current_connected}",
                    dedupe_seconds=60,
                    created_at=now,
                )
            set_network_state("internet_connected", current_connected, now)

        current_ip = internet.get("ipv4") or ""
        previous_ip = get_network_state("external_ipv4")
        if initialized and previous_ip and current_ip and previous_ip != current_ip:
            save_network_event(
                "external_ip_changed",
                "Öffentliche IPv4-Adresse geändert",
                f"Neue Adresse: {current_ip}",
                "info",
                dedupe_key=f"ipv4:{current_ip}",
                dedupe_seconds=300,
                created_at=now,
            )
        set_network_state("external_ipv4", current_ip, now)

        for device in result["devices"]:
            old = old_memory.get(device["mac"])
            if initialized and old is None and not device["monolith"]:
                save_network_event(
                    "new_device",
                    "Neues Gerät im Heimnetz",
                    f"{device['name']} ({device.get('ip') or 'ohne IP-Adresse'})",
                    "warning",
                    device["mac"],
                    dedupe_key=f"new:{device['mac']}",
                    dedupe_seconds=7 * 24 * 60 * 60,
                    created_at=now,
                )
            if (
                old
                and bool(old.get("is_important"))
                and bool(old.get("was_active"))
                and not device["active"]
            ):
                save_network_event(
                    "important_device_offline",
                    "Wichtiges Gerät offline",
                    device["name"],
                    "critical",
                    device["mac"],
                    dedupe_key=f"important-offline:{device['mac']}",
                    dedupe_seconds=30 * 60,
                    created_at=now,
                )

        update_version = result["router"].get("update_available") or ""
        previous_update = get_network_state("fritzos_update") or ""
        if update_version and update_version != previous_update:
            save_network_event(
                "fritzos_update",
                "FRITZ!OS-Update verfügbar",
                f"Version {update_version} kann installiert werden.",
                "warning",
                dedupe_key=f"update:{update_version}",
                dedupe_seconds=7 * 24 * 60 * 60,
                created_at=now,
            )
        set_network_state("fritzos_update", update_version, now)

        current_repeaters = {
            item["id"]: item["name"]
            for item in result["mesh"].get("repeaters", [])
        }
        previous_repeaters_raw = get_network_state("mesh_repeaters", "{}")
        try:
            previous_repeaters = json.loads(previous_repeaters_raw)
        except (TypeError, ValueError):
            previous_repeaters = {}
        if initialized and result["mesh"].get("available"):
            for repeater_id, repeater_name in previous_repeaters.items():
                if repeater_id not in current_repeaters:
                    save_network_event(
                        "mesh_node_offline",
                        "Mesh-Knoten nicht erreichbar",
                        repeater_name,
                        "critical",
                        dedupe_key=f"mesh-offline:{repeater_id}",
                        dedupe_seconds=30 * 60,
                        created_at=now,
                    )
            set_network_state("mesh_repeaters", json.dumps(current_repeaters), now)

    def _collect(self):
        self._connect()
        now = int(time.time())
        errors = []

        try:
            connected = self.status.is_connected
            internet_status_available = True
        except Exception as error:
            connected = False
            internet_status_available = False
            errors.append(_friendly_error(error))
        linked = self._try(lambda: self.status.is_linked, None)
        ipv4 = self._try(lambda: self.status.external_ip)
        ipv6 = self._try(lambda: self.status.external_ipv6)
        uptime = self._try(lambda: self.status.device_uptime)
        connection_uptime = self._try(lambda: self.status.connection_uptime)
        transmission = self._try(lambda: self.status.transmission_rate, (0, 0))
        max_rates = self._try(lambda: self.status.max_bit_rate, (None, None))
        device_info = self._try(lambda: self.status.get_device_info())
        update_available = self._try(lambda: self.status.update_available, "")

        try:
            raw_hosts = self.hosts.get_hosts_info()
            inventory_available = True
        except Exception as error:
            raw_hosts = []
            inventory_available = False
            errors.append(_friendly_error(error))

        wlan_networks, wlan_clients = self._load_wlan()
        raw_mesh = self._try(lambda: self.hosts.get_mesh_topology(), {})
        mesh = _normalize_mesh(raw_mesh)
        mesh["available"] = bool(raw_mesh)

        configured = _configured_devices()
        old_memory = get_network_devices_memory()
        initialized = get_network_state("inventory_initialized") == "1"
        devices = []

        for host in raw_hosts:
            mac = _normalize_mac(host.get("mac"))
            if not mac:
                continue
            ip = str(host.get("ip") or "").strip()
            active = _truthy(host.get("status"))
            integration = configured.get(("mac", mac)) or configured.get(("ip", ip))
            old = old_memory.get(mac)
            important = bool(integration and integration.get("important"))
            memory = remember_network_device(
                mac,
                str(host.get("name") or (integration or {}).get("name") or mac),
                active,
                host.get("interface_type"),
                ip,
                known_on_create=not initialized or bool(integration),
                important_on_create=important,
                observed_at=now,
            )
            wlan = wlan_clients.get(mac, {})
            interface = str(host.get("interface_type") or "").strip()
            connection_type = "wlan" if wlan or "802.11" in interface.lower() or "wlan" in interface.lower() else "lan"
            devices.append({
                "name": str(host.get("name") or (integration or {}).get("name") or "Unbenanntes Gerät"),
                "active": active,
                "ip": ip or None,
                "mac": mac,
                "connection_type": connection_type,
                "interface": interface or None,
                "band": wlan.get("band"),
                "ssid": wlan.get("ssid"),
                "signal_dbm": wlan.get("signal_dbm"),
                "speed_mbit": wlan.get("speed_mbit"),
                "access_point": mesh.get("access_points", {}).get(mac),
                "first_seen": _iso_timestamp(memory.get("first_seen") if memory else now),
                "last_seen": _iso_timestamp(memory.get("last_online") if memory else (now if active else None)),
                "known": bool(memory and memory.get("is_known")),
                "important": bool(memory and memory.get("is_important")),
                "new": bool(memory and not memory.get("is_known") and memory.get("first_seen", 0) >= now - 24 * 60 * 60),
                "monolith": bool(integration),
                "monolith_name": (integration or {}).get("name"),
                "room": (integration or {}).get("room"),
                "device_type": (integration or {}).get("device_type"),
                "previously_active": bool(old and old.get("was_active")),
            })

        devices.sort(key=lambda item: (not item["active"], item["name"].casefold()))
        upload_bps = max(0, _number(transmission[0], 0))
        download_bps = max(0, _number(transmission[1], 0))
        save_network_traffic(download_bps, upload_bps, now)

        online = [item for item in devices if item["active"]]
        result = {
            "success": bool(raw_hosts or device_info or connected),
            "configured": True,
            "inventory_available": inventory_available,
            "collected_at": _iso_timestamp(now),
            "collected_at_unix": now,
            "errors": list(dict.fromkeys(errors)),
            "internet": {
                "connected": bool(connected),
                "available": internet_status_available,
                "linked": linked,
                "ipv4": ipv4 or None,
                "ipv6": ipv6 or None,
                "connection_uptime_seconds": _number(connection_uptime),
            },
            "connection": {
                "download_bytes_per_second": download_bps,
                "upload_bytes_per_second": upload_bps,
                "max_download_bits_per_second": _number(max_rates[1]),
                "max_upload_bits_per_second": _number(max_rates[0]),
            },
            "router": {
                "model": getattr(device_info, "model_name", None) if device_info else None,
                "software_version": getattr(device_info, "software_version", None) if device_info else None,
                "hardware_version": getattr(device_info, "hardware_version", None) if device_info else None,
                "uptime_seconds": _number(uptime),
                "update_available": update_available or None,
            },
            "home_network": {
                "known_devices": len(devices),
                "active_devices": len(online),
                "wlan_devices": sum(1 for item in online if item["connection_type"] == "wlan"),
                "lan_devices": sum(1 for item in online if item["connection_type"] == "lan"),
                "unknown_devices": sum(1 for item in devices if not item["known"]),
                "new_devices": sum(1 for item in devices if item["new"]),
            },
            "traffic_history": get_network_traffic(),
            "devices": devices,
            "mesh": mesh,
            "wlan": wlan_networks,
            "events": [],
        }
        result["mesh"].pop("access_points", None)
        self._record_events(result, old_memory, initialized)
        if inventory_available:
            set_network_state("inventory_initialized", "1", now)
        result["events"] = get_network_events()
        result.pop("collected_at_unix", None)
        for device in result["devices"]:
            device.pop("previously_active", None)
        return result

    def refresh(self, force=False):
        with self.lock:
            age = time.monotonic() - self.last_refresh_monotonic
            if self.last_result is not None and not force and age < CACHE_SECONDS:
                return deepcopy(self.last_result)
            try:
                result = self._collect()
            except Exception as error:
                self.status = None
                self.hosts = None
                result = {
                    "success": False,
                    "inventory_available": False,
                    "configured": self.configured,
                    "error": "FRITZ!Box-Zugangsdaten fehlen"
                    if not self.configured else _friendly_error(error),
                    "collected_at": _iso_timestamp(time.time()),
                    "internet": {"connected": False, "available": False},
                    "connection": {},
                    "router": {},
                    "home_network": {},
                    "traffic_history": get_network_traffic(),
                    "devices": [],
                    "mesh": {"available": False, "roots": [], "node_count": 0},
                    "wlan": [],
                    "events": get_network_events(),
                }
            self.last_result = result
            self.last_refresh_monotonic = time.monotonic()
            return deepcopy(result)

    def start(self):
        with self.lock:
            if self.running:
                return
            self.running = True
            self.stop_event.clear()
            self.thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="MONOLITH-Network",
            )
            self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            self.refresh(force=True)
            self.stop_event.wait(REFRESH_INTERVAL_SECONDS)


network_monitor = NetworkMonitor()


def get_network_status(force=False):
    return network_monitor.refresh(force=force)


def set_network_device_flags(mac, is_known=None, is_important=None):
    normalized = _normalize_mac(mac)
    if not normalized:
        return None
    updated = update_network_device_flags(
        normalized,
        is_known=is_known,
        is_important=is_important,
    )
    if updated and network_monitor.last_result:
        for device in network_monitor.last_result.get("devices", []):
            if device.get("mac") == normalized:
                device["known"] = bool(updated.get("is_known"))
                device["important"] = bool(updated.get("is_important"))
                device["new"] = not device["known"] and device.get("new", False)
                break
    return updated


def start_network_monitor():
    network_monitor.start()
