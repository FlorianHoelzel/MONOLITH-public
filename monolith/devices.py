# Neutrale Beispielgeräte mit gemischter Raumzuordnung.
devices = {

    "device_light_01": {
        "name": "Leselampe",
        "room": "Schlafzimmer",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_light_02": {
        "name": "Wandleuchte",
        "room": "Flur",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_light_03": {
        "name": "Küchenlicht",
        "room": "Küche",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_light_04": {
        "name": "Lichtband",
        "room": "Balkon",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_light_05": {
        "name": "Deckenleuchte",
        "room": "Schlafzimmer",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_display_01": {
        "name": "Bildschirm",
        "room": "Schlafzimmer",
        "type": "media",
        "icon": "ti ti-device-tv",
        "value": "Unbekannt",
        "connected": False,
        "power_state": "Unbekannt",
        "app": None,
        "app_name": None,
        "volume": None,
        "muted": None,
        "status_source": "webos",
    },

    "device_console_01": {
        "name": "Spielebox",
        "room": "Schlafzimmer",
        "type": "console",
        "icon": "ti ti-device-gamepad-2",
        "value": "Unbekannt",
        "read_only": True,
        "status_source": "nintendo_switch",
        "network_connected": None,
    },

    "device_computer_01": {
        "name": "Arbeitsrechner",
        "room": "Schlafzimmer",
        "type": "switch",
        "icon": "ti ti-device-desktop",
        "value": False,
        "read_only": True,
        "status_source": "pc_agent",
    },

    "device_vacuum_01": {
        "name": "Saugroboter",
        "room": "Flur",
        "type": "vacuum",
        "icon": "ti ti-robot",
        "value": "Unbekannt",
    },

    "device_light_06": {
        "name": "Außenlicht",
        "room": "Balkon",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_light_07": {
        "name": "Pendelleuchte",
        "room": "Wohnzimmer",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_media_01": {
        "name": "Medienbox",
        "room": "Wohnzimmer",
        "type": "media",
        "icon": "ti ti-device-tv",
        "read_only": True,
        "status_source": "pyatv",
        "value": "Paused",
        "connected": False,
        "playing": False,
        "power_state": "unknown",
        "playback_state": "paused",
        "title": None,
        "artist": None,
        "artwork_url": None,
        "address": None,
        "identifier": None,
        "model": None,
        "operating_system": None,
        "version": None,
        "last_seen": None,
        "error": None,
    },

    "device_light_08": {
        "name": "Regallicht",
        "room": "Wohnzimmer",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_speaker_01": {
        "name": "Audiostation",
        "room": "Schlafzimmer",
        "type": "media",
        "icon": "ti ti-device-speaker",
        "read_only": True,
        "status_source": "pyatv",
        "value": "Paused",
        "connected": False,
        "playing": False,
        "playback_state": "paused",
        "title": None,
        "artist": None,
        "artwork_url": None,
        "address": None,
        "identifier": None,
        "model": None,
        "operating_system": None,
        "version": None,
        "last_seen": None,
        "error": None,
    },

    "device_washer_01": {
        "name": "Waschstation",
        "room": "Wäschekeller",
        "type": "washer",
        "icon": "ti ti-wash-dry-1",
        "read_only": True,
        "status_source": "pi_homekit",
        "value": False,
        "remaining": 0,
    },

    "device_air_filter_01": {
        "name": "Luftfilter",
        "room": "Wohnzimmer",
        "type": "air_purifier",
        "icon": "ti ti-wind",
        "read_only": True,
        "active": False,
        "state": "off",
        "speed": 0,
    },

    "device_light_09": {
        "name": "Weglicht",
        "room": "Balkon",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_light_10": {
        "name": "Akzentleuchte",
        "room": "Küche",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_light_11": {
        "name": "Orientierungslicht",
        "room": "Flur",
        "type": "light",
        "icon": "ti ti-bulb",
        "value": False,
    },

    "device_dryer_01": {
        "name": "Trocknungsgerät",
        "room": "Küche",
        "type": "dryer",
        "icon": "ti ti-wash-dry-1",
        "read_only": True,
        "status_source": "wewash",
        "configured": False,
        "connected": False,
        "available_dryers": None,
        "active_dryer": None,
        "value": "unknown",
    },
}
