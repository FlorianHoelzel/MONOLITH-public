import os
import threading

from monolith.database import (
    get_packages_for_sync,
    save_event,
    set_package_sync_error,
    set_package_courier_hint_applied,
    set_package_tracker,
    sync_package_tracking,
)
from monolith.package_tracking import (
    PACKAGE_STATUSES,
    PackageTrackingError,
    configure_ship24_tracker_courier,
    fetch_ship24_tracking,
    register_ship24_tracker,
    ship24_is_configured,
    track_ship24_shipment,
)


PACKAGE_REFRESH_INTERVAL_SECONDS = max(
    300,
    int(os.getenv("PACKAGE_REFRESH_INTERVAL_SECONDS", "900")),
)
PACKAGE_URGENT_REFRESH_INTERVAL_SECONDS = max(
    120,
    int(os.getenv("PACKAGE_URGENT_REFRESH_INTERVAL_SECONDS", "300")),
)
PACKAGE_MONITOR_TICK_SECONDS = max(
    30,
    int(os.getenv("PACKAGE_MONITOR_TICK_SECONDS", "60")),
)

_refresh_lock = threading.Lock()
_monitor_started = False


def refresh_packages(package_id=None, force=False, live=False):
    if not ship24_is_configured():
        return {
            "configured": False,
            "updated": 0,
            "errors": [],
        }

    if not _refresh_lock.acquire(blocking=False):
        return {
            "configured": True,
            "busy": True,
            "updated": 0,
            "errors": [],
        }

    updated = 0
    live_fallbacks = 0
    errors = []

    try:
        packages = get_packages_for_sync(
            package_id,
            refresh_interval_seconds=(
                None if package_id is not None or force
                else PACKAGE_REFRESH_INTERVAL_SECONDS
            ),
            urgent_refresh_interval_seconds=(
                None if package_id is not None or force
                else PACKAGE_URGENT_REFRESH_INTERVAL_SECONDS
            ),
        )

        for package in packages:
            try:
                tracker_id = package.get("ship24_tracker_id")

                tracking = None

                if live or not tracker_id:
                    tracking = track_ship24_shipment(
                        package["tracking_number"],
                        f"monolith-package-{package['id']}",
                        package["name"],
                        package.get("destination_post_code"),
                        package.get("carrier"),
                    )
                    tracker_id = tracking.get("tracker_id") or tracker_id

                if not tracker_id:
                    tracker_id = register_ship24_tracker(
                        package["tracking_number"],
                        f"monolith-package-{package['id']}",
                        package["name"],
                        package.get("destination_post_code"),
                        package.get("carrier"),
                    )

                if package.get("ship24_tracker_id") != tracker_id:
                    set_package_tracker(
                        package["id"],
                        tracker_id,
                        courier_hint_applied=bool(package.get("carrier") == "dhl"),
                    )
                    package["ship24_courier_hint_applied"] = bool(
                        package.get("carrier") == "dhl"
                    )

                if (
                    tracker_id
                    and not package.get("ship24_courier_hint_applied")
                ):
                    try:
                        configure_ship24_tracker_courier(
                            tracker_id,
                            package.get("carrier"),
                        )
                    except PackageTrackingError:
                        # Keep serving any existing tracking results even if
                        # Ship24 no longer allows editing this tracker.
                        pass
                    finally:
                        # A tracker which already has results may no longer be
                        # editable. Do not hammer Ship24 with the same PATCH on
                        # every background refresh in that case.
                        set_package_courier_hint_applied(package["id"])

                if tracking is None:
                    tracking = fetch_ship24_tracking(tracker_id)

                if tracking.get("used_per_call"):
                    live_fallbacks += 1

                if (
                    not tracking.get("events")
                    and tracking.get("status") == "announced"
                    and package["status"] != "announced"
                ):
                    tracking["status"] = package["status"]

                sync_package_tracking(
                    package["id"],
                    tracking["status"],
                    tracking.get("expected_delivery"),
                    tracking.get("events", []),
                )
                updated += 1

                if package["status"] != tracking["status"]:
                    latest_event = next(
                        iter(tracking.get("events", [])),
                        {},
                    )
                    save_event(
                        event_type="package",
                        source_id=f"package:{package['id']}",
                        room=None,
                        title=(
                            f"{package['name']}: "
                            f"{PACKAGE_STATUSES[tracking['status']]}"
                        ),
                        detail=latest_event.get("detail"),
                    )

            except PackageTrackingError as error:
                set_package_sync_error(package["id"], str(error))
                errors.append({
                    "package_id": package["id"],
                    "message": str(error),
                })

    finally:
        _refresh_lock.release()

    return {
        "configured": True,
        "busy": False,
        "updated": updated,
        "live_fallbacks": live_fallbacks,
        "errors": errors,
    }


def start_package_monitor():
    global _monitor_started

    if _monitor_started:
        return

    _monitor_started = True

    def monitor_loop():
        while True:
            try:
                refresh_packages()
            except Exception as error:
                print(f"[PACKAGES] Aktualisierung fehlgeschlagen: {error}")

            threading.Event().wait(PACKAGE_MONITOR_TICK_SECONDS)

    thread = threading.Thread(
        target=monitor_loop,
        name="monolith-package-monitor",
        daemon=True,
    )
    thread.start()
