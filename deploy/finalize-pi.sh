#!/usr/bin/env bash
set -euo pipefail

env_source="${1:?Provide the private environment file path}"
runtime_archive="${2:?Provide the runtime archive path}"
config_file="/etc/monolith/monolith.env"
data_dir="/var/lib/monolith"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Bitte mit sudo ausführen."
    exit 1
fi

test -s "${env_source}"
test -s "${runtime_archive}"
test -x /opt/monolith/.venv/bin/python

install -o root -g monolith -m 0640 \
    "${env_source}" \
    "${config_file}"

# Auf Windows war der Speicherpfad relativ zum Projekt. Auf dem Pi
# gehören veränderliche Pairing-Daten in das separate Datenverzeichnis.
if grep -q '^APPLE_TV_STORAGE_FILE=' "${config_file}"; then
    sed -i \
        's|^APPLE_TV_STORAGE_FILE=.*|APPLE_TV_STORAGE_FILE=/var/lib/monolith/apple_tv_pyatv.conf|' \
        "${config_file}"
else
    echo 'APPLE_TV_STORAGE_FILE=/var/lib/monolith/apple_tv_pyatv.conf' \
        >> "${config_file}"
fi

tar -xzf "${runtime_archive}" -C "${data_dir}"
chown -R monolith:monolith "${data_dir}"
chmod 0750 "${data_dir}"
find "${data_dir}" -maxdepth 1 -type f -exec chmod 0600 {} +

runuser -u monolith -- \
    /opt/monolith/.venv/bin/python -c \
    "import sqlite3; c=sqlite3.connect('/var/lib/monolith/monolith.db'); assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'; c.close()"

systemctl enable --now monolith.service monolith-homekit.service
systemctl is-active --quiet monolith.service
systemctl is-active --quiet monolith-homekit.service

for attempt in {1..30}; do
    if curl --fail --silent http://127.0.0.1:5000/ >/dev/null; then
        break
    fi

    if [[ "${attempt}" -eq 30 ]]; then
        echo "Dashboard war nach 30 Sekunden nicht erreichbar."
        exit 1
    fi

    sleep 1
done

rm -f -- "${env_source}" "${runtime_archive}"

echo "MONOLITH_CUTOVER_OK"
systemctl --no-pager --full status monolith.service monolith-homekit.service
