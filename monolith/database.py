import json
import sqlite3
import time

from monolith.data_paths import data_path

DATABASE_PATH = data_path("monolith.db")


# =============================================================
# CONNECTION
# =============================================================


def get_connection():
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    return connection


# =============================================================
# DATABASE SETUP
# =============================================================


def init_database():
    connection = get_connection()
    cursor = connection.cursor()

    # The dashboard and HomeKit bridge share this database. WAL lets feed
    # readers continue while another connection is writing sensor updates.
    cursor.execute("PRAGMA journal_mode=WAL")

    # Sensor-Verlauf
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sensor_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            temperature REAL,
            humidity REAL,
            recorded_at INTEGER NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_sensor_history_room_time
        ON sensor_history (
            room_id,
            recorded_at
        )
        """
    )

    # Wetter: ausgewählter Ort sowie normalisierte Stunden- und Tageswerte.
    # Die Zeitreihen dienen zugleich als Offline-Cache und als lokaler Verlauf.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS weather_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_location_id INTEGER NOT NULL UNIQUE,
            geocoding_provider TEXT NOT NULL DEFAULT 'open_meteo',
            postal_code TEXT,
            name TEXT NOT NULL,
            city TEXT,
            admin1 TEXT,
            country TEXT,
            country_code TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            elevation REAL,
            timezone TEXT NOT NULL,
            is_selected INTEGER NOT NULL DEFAULT 0
                CHECK (is_selected IN (0, 1)),
            last_synced_at INTEGER,
            last_sync_error TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    weather_location_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(weather_locations)")
    }
    if "geocoding_provider" not in weather_location_columns:
        cursor.execute(
            """
            ALTER TABLE weather_locations
            ADD COLUMN geocoding_provider TEXT NOT NULL DEFAULT 'open_meteo'
            """
        )
    if "postal_code" not in weather_location_columns:
        cursor.execute(
            "ALTER TABLE weather_locations ADD COLUMN postal_code TEXT"
        )
    if "city" not in weather_location_columns:
        cursor.execute(
            "ALTER TABLE weather_locations ADD COLUMN city TEXT"
        )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_weather_locations_selected
        ON weather_locations (is_selected DESC, updated_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS weather_hourly (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            observed_at TEXT NOT NULL,
            source TEXT NOT NULL CHECK (
                source IN ('current', 'history', 'forecast')
            ),
            temperature REAL,
            apparent_temperature REAL,
            relative_humidity REAL,
            precipitation_probability REAL,
            precipitation REAL,
            rain REAL,
            showers REAL,
            snowfall REAL,
            weather_code INTEGER,
            cloud_cover REAL,
            pressure_msl REAL,
            surface_pressure REAL,
            wind_speed REAL,
            wind_direction REAL,
            wind_gusts REAL,
            visibility REAL,
            uv_index REAL,
            is_day INTEGER,
            fetched_at INTEGER NOT NULL,
            UNIQUE (location_id, observed_at, source),
            FOREIGN KEY (location_id) REFERENCES weather_locations (id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_weather_hourly_location_time
        ON weather_hourly (location_id, observed_at ASC)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS weather_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER NOT NULL,
            forecast_date TEXT NOT NULL,
            source TEXT NOT NULL CHECK (source IN ('history', 'forecast')),
            weather_code INTEGER,
            temperature_max REAL,
            temperature_min REAL,
            apparent_temperature_max REAL,
            apparent_temperature_min REAL,
            sunrise TEXT,
            sunset TEXT,
            daylight_duration REAL,
            sunshine_duration REAL,
            uv_index_max REAL,
            precipitation_sum REAL,
            rain_sum REAL,
            showers_sum REAL,
            snowfall_sum REAL,
            precipitation_hours REAL,
            precipitation_probability_max REAL,
            wind_speed_max REAL,
            wind_gusts_max REAL,
            wind_direction_dominant REAL,
            fetched_at INTEGER NOT NULL,
            UNIQUE (location_id, forecast_date),
            FOREIGN KEY (location_id) REFERENCES weather_locations (id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_weather_daily_location_date
        ON weather_daily (location_id, forecast_date ASC)
        """
    )

    # Finanzen: wiederkehrende Monatswerte und einzelne Ausgaben
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_recurring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_type TEXT NOT NULL CHECK (
                entry_type IN ('income', 'fixed_expense')
            ),
            name TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            start_month TEXT NOT NULL,
            end_month TEXT,
            created_at INTEGER NOT NULL
        )
        """
    )

    finance_recurring_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(finance_recurring)"
        )
    }

    if "start_month" not in finance_recurring_columns:
        cursor.execute(
            "ALTER TABLE finance_recurring ADD COLUMN start_month TEXT"
        )
        cursor.execute(
            """
            UPDATE finance_recurring
            SET start_month = strftime(
                '%Y-%m',
                created_at,
                'unixepoch',
                'localtime'
            )
            WHERE start_month IS NULL
            """
        )

    if "end_month" not in finance_recurring_columns:
        cursor.execute(
            "ALTER TABLE finance_recurring ADD COLUMN end_month TEXT"
        )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            spent_on TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_finance_expenses_spent_on
        ON finance_expenses (spent_on DESC, id DESC)
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_month_transfers (
            month TEXT PRIMARY KEY,
            amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
            updated_at INTEGER NOT NULL
        )
        """
    )

    # Pakete und Statusverlauf
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            tracking_number TEXT NOT NULL UNIQUE,
            carrier TEXT NOT NULL,
            status TEXT NOT NULL,
            expected_delivery TEXT,
            destination_post_code TEXT,
            note TEXT,
            ship24_tracker_id TEXT,
            tracking_state TEXT NOT NULL DEFAULT 'pending',
            last_synced_at INTEGER,
            last_sync_error TEXT,
            ship24_courier_hint_applied INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )

    package_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(packages)")
    }

    package_migrations = {
        "destination_post_code": "TEXT",
        "ship24_tracker_id": "TEXT",
        "tracking_state": "TEXT NOT NULL DEFAULT 'pending'",
        "last_synced_at": "INTEGER",
        "ship24_courier_hint_applied": "INTEGER NOT NULL DEFAULT 0",
        "last_sync_error": "TEXT",
    }

    for column, definition in package_migrations.items():
        if column not in package_columns:
            cursor.execute(
                f"ALTER TABLE packages ADD COLUMN {column} {definition}"
            )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS package_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            detail TEXT,
            location TEXT,
            provider_event_id TEXT,
            occurred_at INTEGER,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (package_id) REFERENCES packages (id)
                ON DELETE CASCADE
        )
        """
    )

    history_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(package_history)")
    }

    history_migrations = {
        "location": "TEXT",
        "provider_event_id": "TEXT",
        "occurred_at": "INTEGER",
    }

    for column, definition in history_migrations.items():
        if column not in history_columns:
            cursor.execute(
                f"ALTER TABLE package_history ADD COLUMN {column} {definition}"
            )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_packages_status_updated
        ON packages (status, updated_at DESC)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_package_history_package_time
        ON package_history (package_id, created_at DESC, id DESC)
        """
    )

    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_package_history_provider_event
        ON package_history (provider_event_id)
        WHERE provider_event_id IS NOT NULL
        """
    )

    sensor_history_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(sensor_history)"
        )
    }

    if "pm25" not in sensor_history_columns:
        cursor.execute(
            "ALTER TABLE sensor_history ADD COLUMN pm25 REAL"
        )

    if "iai" not in sensor_history_columns:
        cursor.execute(
            "ALTER TABLE sensor_history ADD COLUMN iai INTEGER"
        )

    # Activity Feed
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            source_id TEXT,
            room TEXT,
            title TEXT NOT NULL,
            detail TEXT,
            created_at INTEGER NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_events_created_at
        ON events (
            created_at DESC
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_events_type_source_time
        ON events (
            event_type,
            source_id,
            created_at DESC
        )
        """
    )

    # Last known on/off state for devices whose current state must survive
    # service restarts. This is deliberately separate from the activity feed.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS device_states (
            device_id TEXT PRIMARY KEY,
            value INTEGER NOT NULL CHECK (value IN (0, 1)),
            updated_at INTEGER NOT NULL
        )
        """
    )

    # Netzwerk: eigener Verlauf, Geräte-Merkliste und Feed. Diese Daten
    # bleiben bewusst vom allgemeinen Aktivitätsfeed getrennt.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS network_traffic_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            download_bytes_per_second INTEGER NOT NULL DEFAULT 0,
            upload_bytes_per_second INTEGER NOT NULL DEFAULT 0,
            recorded_at INTEGER NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_network_traffic_time
        ON network_traffic_history (recorded_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS network_devices (
            mac TEXT PRIMARY KEY,
            name TEXT,
            first_seen INTEGER NOT NULL,
            last_seen INTEGER NOT NULL,
            last_online INTEGER,
            is_known INTEGER NOT NULL DEFAULT 0
                CHECK (is_known IN (0, 1)),
            is_important INTEGER NOT NULL DEFAULT 0
                CHECK (is_important IN (0, 1)),
            was_active INTEGER NOT NULL DEFAULT 0
                CHECK (was_active IN (0, 1)),
            interface_type TEXT,
            ip TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS network_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            title TEXT NOT NULL,
            detail TEXT,
            device_mac TEXT,
            dedupe_key TEXT,
            created_at INTEGER NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_network_events_time
        ON network_events (created_at DESC, id DESC)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS network_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at INTEGER NOT NULL
        )
        """
    )

    # Web-Push subscriptions are device-specific and contain no private
    # server key. The VAPID private key is stored separately in DATA_DIR.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            endpoint TEXT PRIMARY KEY,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            user_agent TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )

    # Pet: daily feeding plan, weight history and shopping list.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pet_feeding_times (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            time_of_day TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pet_feeding_completions (
            feeding_time_id INTEGER NOT NULL,
            completed_on TEXT NOT NULL,
            completed_at INTEGER NOT NULL,
            PRIMARY KEY (feeding_time_id, completed_on),
            FOREIGN KEY (feeding_time_id)
                REFERENCES pet_feeding_times (id)
                ON DELETE CASCADE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pet_feeding_notifications (
            feeding_time_id INTEGER NOT NULL,
            notification_date TEXT NOT NULL,
            sent_at INTEGER NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 1,
            last_sent_at INTEGER,
            acknowledged_at INTEGER,
            PRIMARY KEY (feeding_time_id, notification_date),
            FOREIGN KEY (feeding_time_id)
                REFERENCES pet_feeding_times (id)
                ON DELETE CASCADE
        )
        """
    )

    notification_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(pet_feeding_notifications)"
        )
    }

    if "attempt_count" not in notification_columns:
        cursor.execute(
            """
            ALTER TABLE pet_feeding_notifications
            ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 1
            """
        )

    if "last_sent_at" not in notification_columns:
        cursor.execute(
            """
            ALTER TABLE pet_feeding_notifications
            ADD COLUMN last_sent_at INTEGER
            """
        )
        cursor.execute(
            """
            UPDATE pet_feeding_notifications
            SET last_sent_at = sent_at
            WHERE last_sent_at IS NULL
            """
        )

    if "acknowledged_at" not in notification_columns:
        cursor.execute(
            """
            ALTER TABLE pet_feeding_notifications
            ADD COLUMN acknowledged_at INTEGER
            """
        )
        cursor.execute(
            """
            UPDATE pet_feeding_notifications
            SET acknowledged_at = sent_at
            WHERE acknowledged_at IS NULL
            """
        )

    # Provider acceptance is recorded per subscription. An unreachable local
    # acknowledgement endpoint must never trigger another accepted push.
    delivery_table_exists = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pet_push_deliveries'"
    ).fetchone() is not None
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pet_push_deliveries (
            feeding_time_id INTEGER NOT NULL,
            notification_date TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            status TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 1,
            updated_at INTEGER NOT NULL,
            next_attempt_at INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (feeding_time_id, notification_date, endpoint)
        )
        """
    )
    if not delivery_table_exists:
        # Preserve previous provider-accepted sends at upgrade, including
        # unacknowledged ones. Do not replay the current day's meals.
        cursor.execute(
            """
            INSERT INTO pet_push_deliveries (
                feeding_time_id, notification_date, endpoint,
                status, attempt_count, updated_at
            )
            SELECT n.feeding_time_id, n.notification_date, s.endpoint,
                   'accepted', n.attempt_count, n.sent_at
            FROM pet_feeding_notifications n
            CROSS JOIN push_subscriptions s
            """
        )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pet_weight_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weight_grams INTEGER NOT NULL CHECK (weight_grams > 0),
            recorded_on TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pet_weight_date
        ON pet_weight_entries (recorded_on ASC, id ASC)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pet_shopping_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            checked INTEGER NOT NULL DEFAULT 0
                CHECK (checked IN (0, 1)),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )

    # Essensplan: einfache, abhakbare Gerichte pro Kalenderwoche.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS meal_plan_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            name TEXT NOT NULL,
            checked INTEGER NOT NULL DEFAULT 0
                CHECK (checked IN (0, 1)),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_meal_plan_week
        ON meal_plan_items (week_start ASC, id ASC)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            recipe_json TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()


# =============================================================
# SENSOR HISTORY
# =============================================================


def save_sensor_snapshot(
    room_id,
    temperature,
    humidity,
    pm25=None,
    iai=None,
):
    timestamp = int(
        time.time()
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO sensor_history (
            room_id,
            temperature,
            humidity,
            pm25,
            iai,
            recorded_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            room_id,
            temperature,
            humidity,
            pm25,
            iai,
            timestamp,
        ),
    )

    connection.commit()
    connection.close()


def get_sensor_history(
    room_id,
    hours=24,
):
    minimum_timestamp = (
        int(time.time())
        - (hours * 3600)
    )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            temperature,
            humidity,
            pm25,
            iai,
            recorded_at
        FROM sensor_history
        WHERE
            room_id = ?
            AND recorded_at >= ?
        ORDER BY recorded_at ASC
        """,
        (
            room_id,
            minimum_timestamp,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        {
            "temperature": row[
                "temperature"
            ],
            "humidity": row[
                "humidity"
            ],
            "pm25": row[
                "pm25"
            ],
            "iai": row[
                "iai"
            ],
            "timestamp": row[
                "recorded_at"
            ],
        }
        for row in rows
    ]


def get_latest_sensor_values():
    connection = get_connection()
    cursor = connection.cursor()

    room_rows = cursor.execute(
        "SELECT DISTINCT room_id FROM sensor_history"
    ).fetchall()

    latest_values = {}

    for room_row in room_rows:
        room_id = room_row["room_id"]
        room_values = {
            "temperature": None,
            "humidity": None,
            "pm25": None,
            "iai": None,
            "timestamp": None,
        }

        for sensor_type in (
            "temperature",
            "humidity",
            "pm25",
            "iai",
        ):
            row = cursor.execute(
                f"""
                SELECT {sensor_type}, recorded_at
                FROM sensor_history
                WHERE
                    room_id = ?
                    AND {sensor_type} IS NOT NULL
                ORDER BY recorded_at DESC
                LIMIT 1
                """,
                (room_id,),
            ).fetchone()

            if row is None:
                continue

            room_values[sensor_type] = row[
                sensor_type
            ]

            timestamp = row[
                "recorded_at"
            ]

            if (
                room_values["timestamp"] is None
                or timestamp
                > room_values["timestamp"]
            ):
                room_values["timestamp"] = timestamp

        latest_values[room_id] = room_values

    connection.close()

    return latest_values


# =============================================================
# WEB PUSH
# =============================================================


def save_push_subscription(
    endpoint,
    p256dh,
    auth,
    user_agent=None,
    previous_endpoint=None,
):
    timestamp = int(time.time())
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO push_subscriptions (
            endpoint,
            p256dh,
            auth,
            user_agent,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(endpoint) DO UPDATE SET
            p256dh = excluded.p256dh,
            auth = excluded.auth,
            user_agent = excluded.user_agent,
            updated_at = excluded.updated_at
        """,
        (
            endpoint,
            p256dh,
            auth,
            user_agent,
            timestamp,
            timestamp,
        ),
    )
    if previous_endpoint and previous_endpoint != endpoint:
        connection.execute(
            """
            INSERT OR IGNORE INTO pet_push_deliveries (
                feeding_time_id, notification_date, endpoint,
                status, attempt_count, updated_at, next_attempt_at
            )
            SELECT feeding_time_id, notification_date, ?,
                   status, attempt_count, updated_at, next_attempt_at
            FROM pet_push_deliveries
            WHERE endpoint=? AND status IN ('accepted', 'sending', 'unknown')
            """,
            (endpoint, previous_endpoint),
        )
        connection.execute(
            "DELETE FROM push_subscriptions WHERE endpoint=?",
            (previous_endpoint,),
        )
    connection.commit()
    connection.close()


# =============================================================
# NETWORK
# =============================================================


def save_network_traffic(download_bps, upload_bps, recorded_at=None):
    timestamp = int(recorded_at or time.time())
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO network_traffic_history (
            download_bytes_per_second,
            upload_bytes_per_second,
            recorded_at
        ) VALUES (?, ?, ?)
        """,
        (
            max(0, int(download_bps or 0)),
            max(0, int(upload_bps or 0)),
            timestamp,
        ),
    )
    connection.execute(
        "DELETE FROM network_traffic_history WHERE recorded_at < ?",
        (timestamp - 24 * 60 * 60,),
    )
    connection.commit()
    connection.close()


def get_network_traffic(since_seconds=60 * 60, limit=240):
    cutoff = int(time.time()) - max(60, int(since_seconds))
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT download_bytes_per_second, upload_bytes_per_second, recorded_at
        FROM network_traffic_history
        WHERE recorded_at >= ?
        ORDER BY recorded_at DESC, id DESC
        LIMIT ?
        """,
        (cutoff, max(1, min(int(limit), 1440))),
    ).fetchall()
    connection.close()
    return [dict(row) for row in reversed(rows)]


def get_network_devices_memory():
    connection = get_connection()
    rows = connection.execute(
        "SELECT * FROM network_devices"
    ).fetchall()
    connection.close()
    return {
        row["mac"]: dict(row)
        for row in rows
    }


def remember_network_device(
    mac,
    name,
    active,
    interface_type=None,
    ip=None,
    known_on_create=False,
    important_on_create=False,
    observed_at=None,
):
    timestamp = int(observed_at or time.time())
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO network_devices (
            mac, name, first_seen, last_seen, last_online,
            is_known, is_important, was_active, interface_type, ip
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(mac) DO UPDATE SET
            name = excluded.name,
            last_seen = excluded.last_seen,
            last_online = CASE
                WHEN excluded.was_active = 1 THEN excluded.last_seen
                ELSE network_devices.last_online
            END,
            was_active = excluded.was_active,
            interface_type = excluded.interface_type,
            ip = excluded.ip
        """,
        (
            mac,
            name,
            timestamp,
            timestamp,
            timestamp if active else None,
            int(bool(known_on_create)),
            int(bool(important_on_create)),
            int(bool(active)),
            interface_type,
            ip,
        ),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM network_devices WHERE mac = ?",
        (mac,),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def update_network_device_flags(mac, is_known=None, is_important=None):
    assignments = []
    values = []
    if is_known is not None:
        assignments.append("is_known = ?")
        values.append(int(bool(is_known)))
    if is_important is not None:
        assignments.append("is_important = ?")
        values.append(int(bool(is_important)))
    if not assignments:
        return None

    values.append(mac)
    connection = get_connection()
    connection.execute(
        f"UPDATE network_devices SET {', '.join(assignments)} WHERE mac = ?",
        values,
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM network_devices WHERE mac = ?",
        (mac,),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def save_network_event(
    event_type,
    title,
    detail=None,
    severity="info",
    device_mac=None,
    dedupe_key=None,
    dedupe_seconds=0,
    created_at=None,
):
    timestamp = int(created_at or time.time())
    connection = get_connection()
    if dedupe_key and dedupe_seconds:
        existing = connection.execute(
            """
            SELECT id FROM network_events
            WHERE dedupe_key = ? AND created_at >= ?
            LIMIT 1
            """,
            (dedupe_key, timestamp - int(dedupe_seconds)),
        ).fetchone()
        if existing:
            connection.close()
            return False

    connection.execute(
        """
        INSERT INTO network_events (
            event_type, severity, title, detail,
            device_mac, dedupe_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            severity,
            title,
            detail,
            device_mac,
            dedupe_key,
            timestamp,
        ),
    )
    connection.execute(
        """
        DELETE FROM network_events
        WHERE id NOT IN (
            SELECT id FROM network_events
            ORDER BY created_at DESC, id DESC
            LIMIT 500
        )
        """
    )
    connection.commit()
    connection.close()
    return True


def get_network_events(limit=50):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, event_type, severity, title, detail, device_mac, created_at
        FROM network_events
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (max(1, min(int(limit), 200)),),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def get_network_state(key, default=None):
    connection = get_connection()
    row = connection.execute(
        "SELECT value FROM network_state WHERE key = ?",
        (key,),
    ).fetchone()
    connection.close()
    return row["value"] if row else default


def set_network_state(key, value, updated_at=None):
    timestamp = int(updated_at or time.time())
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO network_state (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, None if value is None else str(value), timestamp),
    )
    connection.commit()
    connection.close()


def get_push_subscription(endpoint):
    connection = get_connection()
    row = connection.execute(
        """
        SELECT endpoint, p256dh, auth
        FROM push_subscriptions
        WHERE endpoint = ?
        """,
        (endpoint,),
    ).fetchone()
    connection.close()

    if row is None:
        return None

    return {
        "endpoint": row["endpoint"],
        "keys": {
            "p256dh": row["p256dh"],
            "auth": row["auth"],
        },
    }


def get_push_subscriptions():
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT endpoint, p256dh, auth
        FROM push_subscriptions
        ORDER BY created_at ASC
        """
    ).fetchall()
    connection.close()

    return [
        {
            "endpoint": row["endpoint"],
            "keys": {
                "p256dh": row["p256dh"],
                "auth": row["auth"],
            },
        }
        for row in rows
    ]


def delete_push_subscription(endpoint):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM push_subscriptions WHERE endpoint = ?",
        (endpoint,),
    )
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


# =============================================================
# PET
# =============================================================


def get_pet_data(completed_on):
    connection = get_connection()

    feeding_rows = connection.execute(
        """
        SELECT
            feeding.id,
            feeding.label,
            feeding.time_of_day,
            completion.completed_at
        FROM pet_feeding_times AS feeding
        LEFT JOIN pet_feeding_completions AS completion
            ON completion.feeding_time_id = feeding.id
            AND completion.completed_on = ?
        ORDER BY feeding.time_of_day ASC, feeding.id ASC
        """,
        (completed_on,),
    ).fetchall()
    weight_rows = connection.execute(
        """
        SELECT id, weight_grams, recorded_on, created_at
        FROM pet_weight_entries
        ORDER BY recorded_on ASC, id ASC
        """
    ).fetchall()
    shopping_rows = connection.execute(
        """
        SELECT id, name, checked, created_at, updated_at
        FROM pet_shopping_items
        ORDER BY checked ASC, created_at DESC, id DESC
        """
    ).fetchall()
    connection.close()

    return {
        "feeding_times": [
            {
                "id": row["id"],
                "label": row["label"],
                "time_of_day": row["time_of_day"],
                "completed": row["completed_at"] is not None,
                "completed_at": row["completed_at"],
            }
            for row in feeding_rows
        ],
        "weights": [
            {
                "id": row["id"],
                "weight_grams": row["weight_grams"],
                "recorded_on": row["recorded_on"],
                "created_at": row["created_at"],
            }
            for row in weight_rows
        ],
        "shopping_items": [
            {
                "id": row["id"],
                "name": row["name"],
                "checked": bool(row["checked"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in shopping_rows
        ],
    }


def create_pet_feeding_time(label, time_of_day):
    timestamp = int(time.time())
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO pet_feeding_times (
            label,
            time_of_day,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (label, time_of_day, timestamp, timestamp),
    )
    entry_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return entry_id


def delete_pet_feeding_time(entry_id):
    connection = get_connection()
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM pet_feeding_times WHERE id = ?",
        (entry_id,),
    )
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


def set_pet_feeding_completed(entry_id, completed_on, completed):
    timestamp = int(time.time())
    connection = get_connection()
    cursor = connection.cursor()
    exists = cursor.execute(
        "SELECT 1 FROM pet_feeding_times WHERE id = ?",
        (entry_id,),
    ).fetchone()

    if exists is None:
        connection.close()
        return False

    if completed:
        cursor.execute(
            """
            INSERT INTO pet_feeding_completions (
                feeding_time_id,
                completed_on,
                completed_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(feeding_time_id, completed_on) DO UPDATE SET
                completed_at = excluded.completed_at
            """,
            (entry_id, completed_on, timestamp),
        )
    else:
        cursor.execute(
            """
            DELETE FROM pet_feeding_completions
            WHERE feeding_time_id = ? AND completed_on = ?
            """,
            (entry_id, completed_on),
        )

    connection.commit()
    connection.close()
    return True


def get_due_pet_feedings(
    notification_date,
    current_time,
    include_notified=False,
):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT
            feeding.id,
            feeding.label,
            feeding.time_of_day,
            COALESCE(notification.attempt_count, 0) AS attempt_count
        FROM pet_feeding_times AS feeding
        LEFT JOIN pet_feeding_completions AS completion
            ON completion.feeding_time_id = feeding.id
            AND completion.completed_on = ?
        LEFT JOIN pet_feeding_notifications AS notification
            ON notification.feeding_time_id = feeding.id
            AND notification.notification_date = ?
        WHERE
            feeding.time_of_day <= ?
            AND completion.feeding_time_id IS NULL
            AND (
                notification.feeding_time_id IS NULL
                OR ?
            )
        ORDER BY feeding.time_of_day ASC, feeding.id ASC
        """,
        (
            notification_date,
            notification_date,
            current_time,
            include_notified,
        ),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def claim_pet_push_delivery(entry_id, notification_date, endpoint, timestamp):
    # Commit the claim BEFORE the HTTP request. Competing monitors, a restart,
    # or a failed DB write after acceptance cannot resend the same delivery.
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO pet_push_deliveries (
                    feeding_time_id, notification_date, endpoint,
                    status, attempt_count, updated_at
                ) VALUES (?, ?, ?, 'sending', 1, ?)
                ON CONFLICT(feeding_time_id, notification_date, endpoint)
                DO UPDATE SET status = 'sending',
                    attempt_count = attempt_count + 1,
                    updated_at = excluded.updated_at
                WHERE status = 'retry' AND next_attempt_at <= ?
                    AND attempt_count < 6
                """,
                (entry_id, notification_date, endpoint, timestamp, timestamp),
            )
            if cursor.rowcount == 0:
                return None
            return connection.execute(
                """
                SELECT attempt_count FROM pet_push_deliveries
                WHERE feeding_time_id=? AND notification_date=? AND endpoint=?
                """,
                (entry_id, notification_date, endpoint),
            ).fetchone()["attempt_count"]
    finally:
        connection.close()


def finish_pet_push_delivery(
    entry_id, notification_date, endpoint, status, timestamp, retry_after=0,
):
    connection = get_connection()
    try:
        with connection:
            connection.execute(
                """
                UPDATE pet_push_deliveries
                SET status=?, updated_at=?, next_attempt_at=?
                WHERE feeding_time_id=? AND notification_date=? AND endpoint=?
                """,
                (status, timestamp, timestamp + retry_after,
                 entry_id, notification_date, endpoint),
            )
    finally:
        connection.close()


def mark_pet_feeding_notified(entry_id, notification_date):
    timestamp = int(time.time())
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO pet_feeding_notifications (
            feeding_time_id,
            notification_date,
            sent_at,
            attempt_count,
            last_sent_at,
            acknowledged_at
        )
        VALUES (?, ?, ?, 1, ?, NULL)
        ON CONFLICT(feeding_time_id, notification_date) DO UPDATE SET
            attempt_count = attempt_count + 1,
            last_sent_at = excluded.last_sent_at
        """,
        (entry_id, notification_date, timestamp, timestamp),
    )
    connection.commit()
    connection.close()


def acknowledge_pet_feeding_notification(
    entry_id,
    notification_date,
):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE pet_feeding_notifications
        SET acknowledged_at = ?
        WHERE
            feeding_time_id = ?
            AND notification_date = ?
        """,
        (
            int(time.time()),
            entry_id,
            notification_date,
        ),
    )
    acknowledged = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return acknowledged


def create_pet_weight(weight_grams, recorded_on):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO pet_weight_entries (
            weight_grams,
            recorded_on,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (weight_grams, recorded_on, int(time.time())),
    )
    entry_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return entry_id


def delete_pet_weight(entry_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM pet_weight_entries WHERE id = ?",
        (entry_id,),
    )
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


def create_pet_shopping_item(name):
    timestamp = int(time.time())
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO pet_shopping_items (
            name,
            checked,
            created_at,
            updated_at
        )
        VALUES (?, 0, ?, ?)
        """,
        (name, timestamp, timestamp),
    )
    entry_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return entry_id


def set_pet_shopping_item_checked(entry_id, checked):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE pet_shopping_items
        SET checked = ?, updated_at = ?
        WHERE id = ?
        """,
        (int(bool(checked)), int(time.time()), entry_id),
    )
    updated = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return updated


def delete_pet_shopping_item(entry_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM pet_shopping_items WHERE id = ?",
        (entry_id,),
    )
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


# =============================================================
# MEAL PLAN
# =============================================================


def get_meal_plan_items(week_starts):
    starts = list(week_starts)

    if not starts:
        return []

    placeholders = ", ".join("?" for _ in starts)
    connection = get_connection()
    rows = connection.execute(
        f"""
        SELECT id, week_start, name, checked, created_at, updated_at
        FROM meal_plan_items
        WHERE week_start IN ({placeholders})
        ORDER BY week_start ASC, id ASC
        """,
        starts,
    ).fetchall()
    connection.close()

    return [
        {
            **dict(row),
            "checked": bool(row["checked"]),
        }
        for row in rows
    ]


def create_meal_plan_item(week_start, name):
    timestamp = int(time.time())
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO meal_plan_items (
            week_start,
            name,
            checked,
            created_at,
            updated_at
        )
        VALUES (?, ?, 0, ?, ?)
        """,
        (week_start, name, timestamp, timestamp),
    )
    entry_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return entry_id


def set_meal_plan_item_checked(entry_id, checked):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE meal_plan_items
        SET checked = ?, updated_at = ?
        WHERE id = ?
        """,
        (int(bool(checked)), int(time.time()), entry_id),
    )
    updated = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return updated


def move_meal_plan_item(entry_id, week_start):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE meal_plan_items
        SET week_start = ?, updated_at = ?
        WHERE id = ? AND checked = 0
        """,
        (week_start, int(time.time()), entry_id),
    )
    updated = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return updated


def delete_meal_plan_item(entry_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM meal_plan_items WHERE id = ?",
        (entry_id,),
    )
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


def get_saved_recipes():
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, source_id, title, recipe_json, created_at, updated_at
        FROM saved_recipes
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    connection.close()

    recipes = []
    for row in rows:
        try:
            recipe = json.loads(row["recipe_json"])
        except (TypeError, ValueError):
            continue

        recipe["bookmark_id"] = row["id"]
        recipe["source_id"] = row["source_id"]
        recipes.append(recipe)

    return recipes


def save_recipe_bookmark(source_id, title, recipe):
    timestamp = int(time.time())
    recipe_json = json.dumps(
        recipe,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO saved_recipes (
            source_id,
            title,
            recipe_json,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            title = excluded.title,
            recipe_json = excluded.recipe_json,
            updated_at = excluded.updated_at
        """,
        (source_id, title, recipe_json, timestamp, timestamp),
    )
    row = cursor.execute(
        "SELECT id FROM saved_recipes WHERE source_id = ?",
        (source_id,),
    ).fetchone()
    connection.commit()
    connection.close()
    return row["id"]


def delete_recipe_bookmark(bookmark_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM saved_recipes WHERE id = ?",
        (bookmark_id,),
    )
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


# =============================================================
# DEVICE STATES
# =============================================================


def save_device_state(
    device_id,
    value,
):
    timestamp = int(time.time())

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO device_states (
            device_id,
            value,
            updated_at
        )
        VALUES (?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (
            device_id,
            int(bool(value)),
            timestamp,
        ),
    )

    connection.commit()
    connection.close()


def get_device_states():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT device_id, value
        FROM device_states
        """
    )

    rows = cursor.fetchall()
    connection.close()

    return {
        row["device_id"]: bool(row["value"])
        for row in rows
    }


# =============================================================
# EVENTS
# =============================================================


def save_event(
    event_type,
    title,
    source_id=None,
    room=None,
    detail=None,
    created_at=None,
):
    if created_at is None:
        timestamp = int(
            time.time()
        )

    else:
        timestamp = int(
            created_at
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO events (
            event_type,
            source_id,
            room,
            title,
            detail,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            source_id,
            room,
            title,
            detail,
            timestamp,
        ),
    )

    connection.commit()

    event_id = (
        cursor.lastrowid
    )

    connection.close()

    return event_id


def get_recent_events(
    limit=30,
    before_timestamp=None,
    before_id=None,
):
    limit = max(
        1,
        min(limit, 100),
    )

    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT
            id,
            event_type,
            source_id,
            room,
            title,
            detail,
            created_at
        FROM events
    """

    parameters = []

    if (
        before_timestamp is not None
        and before_id is not None
    ):
        query += """
        WHERE
            created_at < ?
            OR (
                created_at = ?
                AND id < ?
            )
        """

        parameters.extend((
            before_timestamp,
            before_timestamp,
            before_id,
        ))

    query += """
        ORDER BY
            created_at DESC,
            id DESC
        LIMIT ?
    """

    parameters.append(limit)

    try:
        cursor.execute(
            query,
            parameters,
        )
        rows = cursor.fetchall()
    finally:
        connection.close()

    return [
        {
            "id": row["id"],
            "event_type": row[
                "event_type"
            ],
            "source_id": row[
                "source_id"
            ],
            "room": row["room"],
            "title": row["title"],
            "detail": row["detail"],
            "timestamp": row[
                "created_at"
            ],
        }
        for row in rows
    ]


def get_events_since(
    event_type,
    since_timestamp,
    source_id=None,
    limit=500,
):
    limit = max(
        1,
        min(limit, 1000),
    )

    connection = get_connection()
    cursor = connection.cursor()

    query = """
        SELECT
            id,
            event_type,
            source_id,
            room,
            title,
            detail,
            created_at
        FROM events
        WHERE event_type = ?
          AND created_at >= ?
    """
    parameters = [
        event_type,
        int(since_timestamp),
    ]

    if source_id:
        query += " AND source_id = ?"
        parameters.append(source_id)

    query += """
        ORDER BY
            created_at DESC,
            id DESC
        LIMIT ?
    """
    parameters.append(limit)

    cursor.execute(
        query,
        parameters,
    )
    rows = cursor.fetchall()
    connection.close()

    return [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "source_id": row["source_id"],
            "room": row["room"],
            "title": row["title"],
            "detail": row["detail"],
            "timestamp": row["created_at"],
        }
        for row in rows
    ]


# =============================================================
# FINANCES
# =============================================================


def create_finance_recurring(
    entry_type,
    name,
    amount_cents,
    start_month=None,
):
    if start_month is None:
        start_month = time.strftime("%Y-%m")

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO finance_recurring (
            entry_type,
            name,
            amount_cents,
            start_month,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            entry_type,
            name,
            amount_cents,
            start_month,
            int(time.time()),
        ),
    )
    entry_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return entry_id


def delete_finance_recurring(entry_id, effective_month=None):
    connection = get_connection()
    cursor = connection.cursor()

    row = cursor.execute(
        "SELECT start_month FROM finance_recurring WHERE id = ?",
        (entry_id,),
    ).fetchone()

    if row is None:
        connection.close()
        return False

    if effective_month is None or effective_month <= row["start_month"]:
        cursor.execute(
            "DELETE FROM finance_recurring WHERE id = ?",
            (entry_id,),
        )
    else:
        end_month = _finance_month_from_index(
            _finance_month_index(effective_month) - 1
        )
        cursor.execute(
            """
            UPDATE finance_recurring
            SET end_month = ?
            WHERE id = ?
            """,
            (end_month, entry_id),
        )

    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


def create_finance_expense(name, amount_cents, spent_on):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO finance_expenses (
            name,
            amount_cents,
            spent_on,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            name,
            amount_cents,
            spent_on,
            int(time.time()),
        ),
    )
    entry_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return entry_id


def delete_finance_expense(entry_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM finance_expenses WHERE id = ?",
        (entry_id,),
    )
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


def set_finance_transfer(month, amount_cents):
    connection = get_connection()
    cursor = connection.cursor()

    if amount_cents == 0:
        cursor.execute(
            "DELETE FROM finance_month_transfers WHERE month = ?",
            (month,),
        )
    else:
        cursor.execute(
            """
            INSERT INTO finance_month_transfers (
                month,
                amount_cents,
                updated_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(month) DO UPDATE SET
                amount_cents = excluded.amount_cents,
                updated_at = excluded.updated_at
            """,
            (month, amount_cents, int(time.time())),
        )

    connection.commit()
    connection.close()


def get_finances(month):
    connection = get_connection()
    cursor = connection.cursor()

    recurring_rows = cursor.execute(
        """
        SELECT id, entry_type, name, amount_cents, start_month, end_month
        FROM finance_recurring
        WHERE start_month <= ?
        ORDER BY entry_type ASC, created_at ASC, id ASC
        """
        ,
        (month,),
    ).fetchall()

    expense_rows = cursor.execute(
        """
        SELECT id, name, amount_cents, spent_on
        FROM finance_expenses
        WHERE substr(spent_on, 1, 7) <= ?
        ORDER BY spent_on ASC, id ASC
        """,
        (month,),
    ).fetchall()

    transfer_rows = cursor.execute(
        """
        SELECT month, amount_cents
        FROM finance_month_transfers
        WHERE month <= ?
        ORDER BY month ASC
        """,
        (month,),
    ).fetchall()

    connection.close()

    all_recurring = [dict(row) for row in recurring_rows]
    recurring = [
        row
        for row in all_recurring
        if row["end_month"] is None or row["end_month"] >= month
    ]
    all_expenses = [dict(row) for row in expense_rows]
    transfers_by_month = {
        row["month"]: row["amount_cents"]
        for row in transfer_rows
    }
    expenses = [
        row
        for row in all_expenses
        if row["spent_on"][:7] == month
    ]
    income_cents = sum(
        row["amount_cents"]
        for row in recurring
        if row["entry_type"] == "income"
    )
    fixed_expense_cents = sum(
        row["amount_cents"]
        for row in recurring
        if row["entry_type"] == "fixed_expense"
    )
    variable_expense_cents = sum(
        row["amount_cents"]
        for row in expenses
    )

    first_months = [
        row["start_month"]
        for row in all_recurring
    ] + [
        row["spent_on"][:7]
        for row in all_expenses
    ] + list(transfers_by_month)
    carried_over_cents = 0

    if first_months:
        first_month = min(first_months)
        first_index = _finance_month_index(first_month)
        requested_index = _finance_month_index(month)
        expenses_by_month = {}

        for row in all_expenses:
            expense_month = row["spent_on"][:7]
            expenses_by_month[expense_month] = (
                expenses_by_month.get(expense_month, 0)
                + row["amount_cents"]
            )

        running_balance = 0

        for month_index in range(first_index, requested_index):
            calculation_month = _finance_month_from_index(
                month_index
            )
            running_balance += sum(
                row["amount_cents"]
                for row in all_recurring
                if (
                    row["entry_type"] == "income"
                    and row["start_month"] <= calculation_month
                    and (
                        row["end_month"] is None
                        or row["end_month"] >= calculation_month
                    )
                )
            )
            running_balance -= sum(
                row["amount_cents"]
                for row in all_recurring
                if (
                    row["entry_type"] == "fixed_expense"
                    and row["start_month"] <= calculation_month
                    and (
                        row["end_month"] is None
                        or row["end_month"] >= calculation_month
                    )
                )
            )
            running_balance -= expenses_by_month.get(
                calculation_month,
                0,
            )
            running_balance += transfers_by_month.get(
                calculation_month,
                0,
            )

        carried_over_cents = (
            running_balance
            + transfers_by_month.get(month, 0)
        )

    return {
        "month": month,
        "recurring": recurring,
        "expenses": expenses,
        "summary": {
            "income_cents": income_cents,
            "fixed_expense_cents": fixed_expense_cents,
            "variable_expense_cents": variable_expense_cents,
            "manual_transfer_cents": transfers_by_month.get(month, 0),
            "carried_over_cents": carried_over_cents,
            "available_cents": (
                carried_over_cents
                + income_cents
                - fixed_expense_cents
                - variable_expense_cents
            ),
        },
    }


def _finance_month_index(month):
    year, month_number = (int(part) for part in month.split("-"))
    return year * 12 + month_number - 1


def _finance_month_from_index(month_index):
    year, zero_based_month = divmod(month_index, 12)
    return f"{year:04d}-{zero_based_month + 1:02d}"


# =============================================================
# PACKAGES
# =============================================================


def get_packages():
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT
            id,
            name,
            tracking_number,
            carrier,
            status,
            expected_delivery,
            destination_post_code,
            note,
            ship24_tracker_id,
            tracking_state,
            last_synced_at,
            last_sync_error,
            ship24_courier_hint_applied,
            created_at,
            updated_at
        FROM packages
        ORDER BY
            CASE WHEN status = 'delivered' THEN 1 ELSE 0 END,
            updated_at DESC,
            id DESC
        """
    ).fetchall()

    packages = []

    for row in rows:
        package = dict(row)
        history_rows = connection.execute(
            """
            SELECT
                status,
                detail,
                location,
                occurred_at,
                created_at
            FROM package_history
            WHERE package_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 12
            """,
            (row["id"],),
        ).fetchall()
        package["history"] = [dict(item) for item in history_rows]
        packages.append(package)

    connection.close()
    return packages


def create_package(
    name,
    tracking_number,
    carrier,
    status,
    expected_delivery=None,
    note=None,
    destination_post_code=None,
):
    timestamp = int(time.time())
    connection = get_connection()
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO packages (
            name,
            tracking_number,
            carrier,
            status,
            expected_delivery,
            destination_post_code,
            note,
            tracking_state,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (
            name,
            tracking_number,
            carrier,
            status,
            expected_delivery,
            destination_post_code,
            note,
            timestamp,
            timestamp,
        ),
    )
    package_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO package_history (
            package_id,
            status,
            detail,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (package_id, status, "Sendung hinzugefügt", timestamp),
    )
    connection.commit()
    connection.close()
    return package_id


def set_package_tracker(package_id, tracker_id, courier_hint_applied=False):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE packages
        SET
            ship24_tracker_id = ?,
            ship24_courier_hint_applied = ?,
            tracking_state = 'active',
            last_sync_error = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        (
            tracker_id,
            int(bool(courier_hint_applied)),
            int(time.time()),
            package_id,
        ),
    )
    updated = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return updated


def set_package_courier_hint_applied(package_id):
    connection = get_connection()
    connection.execute(
        """
        UPDATE packages
        SET ship24_courier_hint_applied = 1
        WHERE id = ?
        """,
        (package_id,),
    )
    connection.commit()
    connection.close()


def set_package_sync_error(package_id, message):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE packages
        SET
            tracking_state = 'error',
            last_sync_error = ?,
            last_synced_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            str(message)[:300],
            int(time.time()),
            int(time.time()),
            package_id,
        ),
    )
    connection.commit()
    connection.close()


def get_packages_for_sync(
    package_id=None,
    refresh_interval_seconds=None,
    urgent_refresh_interval_seconds=None,
    now=None,
):
    connection = get_connection()
    query = """
        SELECT
            id,
            name,
            tracking_number,
            destination_post_code,
            carrier,
            ship24_tracker_id,
            ship24_courier_hint_applied,
            status,
            last_synced_at
        FROM packages
        WHERE status != 'delivered'
    """
    parameters = []

    if package_id is not None:
        query += " AND id = ?"
        parameters.append(package_id)
    elif (
        refresh_interval_seconds is not None
        and urgent_refresh_interval_seconds is not None
    ):
        current_time = int(time.time() if now is None else now)
        query += """
            AND (
                last_synced_at IS NULL
                OR last_synced_at <= ? - CASE
                    WHEN status IN (
                        'out_for_delivery',
                        'failed_attempt',
                        'ready_for_pickup',
                        'exception'
                    ) THEN ?
                    ELSE ?
                END
            )
        """
        parameters.extend((
            current_time,
            int(urgent_refresh_interval_seconds),
            int(refresh_interval_seconds),
        ))

    query += " ORDER BY last_synced_at ASC, id ASC"
    rows = connection.execute(query, parameters).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def sync_package_tracking(
    package_id,
    status,
    expected_delivery,
    events,
):
    timestamp = int(time.time())
    connection = get_connection()
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()
    current = cursor.execute(
        "SELECT status, expected_delivery FROM packages WHERE id = ?",
        (package_id,),
    ).fetchone()

    if current is None:
        connection.close()
        return False

    current_expected_delivery = current["expected_delivery"]
    next_expected_delivery = (
        expected_delivery
        if expected_delivery is not None
        else current_expected_delivery
    )
    changed = (
        current["status"] != status
        or current_expected_delivery != next_expected_delivery
    )

    cursor.execute(
        """
        UPDATE packages
        SET
            status = ?,
            expected_delivery = ?,
            tracking_state = 'active',
            last_synced_at = ?,
            last_sync_error = NULL,
            updated_at = CASE WHEN ? THEN ? ELSE updated_at END
        WHERE id = ?
        """,
        (
            status,
            next_expected_delivery,
            timestamp,
            int(changed),
            timestamp,
            package_id,
        ),
    )

    for event in events:
        cursor.execute(
            """
            INSERT OR IGNORE INTO package_history (
                package_id,
                status,
                detail,
                location,
                provider_event_id,
                occurred_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                package_id,
                event["status"],
                event.get("detail"),
                event.get("location"),
                event["event_id"],
                event.get("occurred_at"),
                event.get("occurred_at") or timestamp,
            ),
        )

    connection.commit()
    connection.close()
    return True


def update_package(
    package_id,
    status,
    expected_delivery=None,
    note=None,
):
    timestamp = int(time.time())
    connection = get_connection()
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()
    current = cursor.execute(
        "SELECT status FROM packages WHERE id = ?",
        (package_id,),
    ).fetchone()

    if current is None:
        connection.close()
        return False

    cursor.execute(
        """
        UPDATE packages
        SET status = ?, expected_delivery = ?, note = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            expected_delivery,
            note,
            timestamp,
            package_id,
        ),
    )

    if current["status"] != status:
        cursor.execute(
            """
            INSERT INTO package_history (
                package_id,
                status,
                detail,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (package_id, status, "Status geändert", timestamp),
        )

    connection.commit()
    connection.close()
    return True


def delete_package(package_id):
    connection = get_connection()
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM packages WHERE id = ?",
        (package_id,),
    )
    deleted = cursor.rowcount > 0
    connection.commit()
    connection.close()
    return deleted


# =============================================================
# WEATHER
# =============================================================


WEATHER_HOURLY_COLUMNS = (
    "temperature",
    "apparent_temperature",
    "relative_humidity",
    "precipitation_probability",
    "precipitation",
    "rain",
    "showers",
    "snowfall",
    "weather_code",
    "cloud_cover",
    "pressure_msl",
    "surface_pressure",
    "wind_speed",
    "wind_direction",
    "wind_gusts",
    "visibility",
    "uv_index",
    "is_day",
)

WEATHER_DAILY_COLUMNS = (
    "weather_code",
    "temperature_max",
    "temperature_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "sunrise",
    "sunset",
    "daylight_duration",
    "sunshine_duration",
    "uv_index_max",
    "precipitation_sum",
    "rain_sum",
    "showers_sum",
    "snowfall_sum",
    "precipitation_hours",
    "precipitation_probability_max",
    "wind_speed_max",
    "wind_gusts_max",
    "wind_direction_dominant",
)


def set_weather_location(location):
    timestamp = int(time.time())
    connection = get_connection()
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()
    cursor.execute("UPDATE weather_locations SET is_selected = 0")
    cursor.execute(
        """
        INSERT INTO weather_locations (
            provider_location_id,
            geocoding_provider,
            postal_code,
            name,
            city,
            admin1,
            country,
            country_code,
            latitude,
            longitude,
            elevation,
            timezone,
            is_selected,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(provider_location_id) DO UPDATE SET
            geocoding_provider = excluded.geocoding_provider,
            postal_code = excluded.postal_code,
            name = excluded.name,
            city = excluded.city,
            admin1 = excluded.admin1,
            country = excluded.country,
            country_code = excluded.country_code,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            elevation = excluded.elevation,
            timezone = excluded.timezone,
            is_selected = 1,
            updated_at = excluded.updated_at
        """,
        (
            location["provider_location_id"],
            location.get("geocoding_provider", "open_meteo"),
            location.get("postal_code"),
            location["name"],
            location.get("city"),
            location.get("admin1"),
            location.get("country"),
            location.get("country_code"),
            location["latitude"],
            location["longitude"],
            location.get("elevation"),
            location["timezone"],
            timestamp,
            timestamp,
        ),
    )
    row = cursor.execute(
        """
        SELECT * FROM weather_locations
        WHERE provider_location_id = ?
        """,
        (location["provider_location_id"],),
    ).fetchone()
    connection.commit()
    connection.close()
    return dict(row)


def get_selected_weather_location():
    connection = get_connection()
    row = connection.execute(
        """
        SELECT * FROM weather_locations
        WHERE is_selected = 1
        ORDER BY updated_at DESC
        LIMIT 1
        """
    ).fetchone()
    connection.close()
    return dict(row) if row is not None else None


def mark_weather_sync(location_id, error=None):
    timestamp = int(time.time())
    connection = get_connection()
    connection.execute(
        """
        UPDATE weather_locations
        SET
            last_synced_at = CASE WHEN ? IS NULL THEN ? ELSE last_synced_at END,
            last_sync_error = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (error, timestamp, error, timestamp, location_id),
    )
    connection.commit()
    connection.close()


def save_weather_data(location_id, weather_data):
    fetched_at = int(time.time())
    connection = get_connection()
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()

    hourly_rows = list(weather_data.get("hourly", []))
    current = weather_data.get("current")
    if current:
        current_row = dict(current)
        current_row["source"] = "current"
        hourly_rows.append(current_row)

    hourly_placeholders = ", ".join("?" for _ in WEATHER_HOURLY_COLUMNS)
    hourly_updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in WEATHER_HOURLY_COLUMNS
    )
    for row in hourly_rows:
        cursor.execute(
            f"""
            INSERT INTO weather_hourly (
                location_id,
                observed_at,
                source,
                {", ".join(WEATHER_HOURLY_COLUMNS)},
                fetched_at
            )
            VALUES (?, ?, ?, {hourly_placeholders}, ?)
            ON CONFLICT(location_id, observed_at, source) DO UPDATE SET
                {hourly_updates},
                fetched_at = excluded.fetched_at
            """,
            (
                location_id,
                row["time"],
                row["source"],
                *(row.get(column) for column in WEATHER_HOURLY_COLUMNS),
                fetched_at,
            ),
        )

    daily_placeholders = ", ".join("?" for _ in WEATHER_DAILY_COLUMNS)
    daily_updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in WEATHER_DAILY_COLUMNS
    )
    for row in weather_data.get("daily", []):
        cursor.execute(
            f"""
            INSERT INTO weather_daily (
                location_id,
                forecast_date,
                source,
                {", ".join(WEATHER_DAILY_COLUMNS)},
                fetched_at
            )
            VALUES (?, ?, ?, {daily_placeholders}, ?)
            ON CONFLICT(location_id, forecast_date) DO UPDATE SET
                source = excluded.source,
                {daily_updates},
                fetched_at = excluded.fetched_at
            """,
            (
                location_id,
                row["date"],
                row["source"],
                *(row.get(column) for column in WEATHER_DAILY_COLUMNS),
                fetched_at,
            ),
        )

    # Keep a useful local archive without allowing the database to grow forever.
    cursor.execute(
        """
        DELETE FROM weather_hourly
        WHERE location_id = ?
          AND observed_at < datetime('now', '-90 days', 'localtime')
        """,
        (location_id,),
    )
    cursor.execute(
        """
        DELETE FROM weather_daily
        WHERE location_id = ?
          AND forecast_date < date('now', '-365 days', 'localtime')
        """,
        (location_id,),
    )
    cursor.execute(
        """
        UPDATE weather_locations
        SET last_synced_at = ?, last_sync_error = NULL, updated_at = ?
        WHERE id = ?
        """,
        (fetched_at, fetched_at, location_id),
    )
    connection.commit()
    connection.close()


def get_weather_data(location_id):
    connection = get_connection()
    current_row = connection.execute(
        """
        SELECT * FROM weather_hourly
        WHERE location_id = ? AND source = 'current'
        ORDER BY fetched_at DESC, observed_at DESC
        LIMIT 1
        """,
        (location_id,),
    ).fetchone()
    hourly_rows = connection.execute(
        """
        SELECT * FROM weather_hourly
        WHERE location_id = ? AND source != 'current'
        ORDER BY observed_at ASC
        """,
        (location_id,),
    ).fetchall()
    daily_rows = connection.execute(
        """
        SELECT * FROM weather_daily
        WHERE location_id = ?
        ORDER BY forecast_date ASC
        """,
        (location_id,),
    ).fetchall()
    connection.close()

    def serialize_hourly(row):
        data = {column: row[column] for column in WEATHER_HOURLY_COLUMNS}
        data.update({
            "time": row["observed_at"],
            "source": row["source"],
        })
        return data

    def serialize_daily(row):
        data = {column: row[column] for column in WEATHER_DAILY_COLUMNS}
        data.update({
            "date": row["forecast_date"],
            "source": row["source"],
        })
        return data

    return {
        "current": serialize_hourly(current_row) if current_row else None,
        "hourly": [serialize_hourly(row) for row in hourly_rows],
        "daily": [serialize_daily(row) for row in daily_rows],
    }
