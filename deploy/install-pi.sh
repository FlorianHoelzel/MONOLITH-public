#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Bitte mit sudo ausführen: sudo bash deploy/install-pi.sh"
    exit 1
fi

app_dir="/opt/monolith"
data_dir="/var/lib/monolith"
config_dir="/etc/monolith"
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "${source_dir}/requirements.txt" ]]; then
    echo "requirements.txt fehlt im Quellverzeichnis ${source_dir}."
    exit 1
fi

apt-get update
apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    ffmpeg \
    python3-dev \
    python3-venv

if ! id monolith >/dev/null 2>&1; then
    useradd --system --home-dir "${data_dir}" --shell /usr/sbin/nologin monolith
fi

install -d -o root -g root -m 0755 "${app_dir}"
if [[ "${source_dir}" != "${app_dir}" ]]; then
    cp -a "${source_dir}/." "${app_dir}/"
fi

install -d -o monolith -g monolith -m 0750 "${data_dir}"
install -d -o root -g monolith -m 0750 "${config_dir}"

python3 -m venv "${app_dir}/.venv"
"${app_dir}/.venv/bin/python" -m pip install --upgrade pip
"${app_dir}/.venv/bin/python" -m pip install -r "${app_dir}/requirements.txt"

if [[ ! -f "${config_dir}/monolith.env" ]]; then
    install -o root -g monolith -m 0640 \
        "${app_dir}/.env.example" \
        "${config_dir}/monolith.env"
    echo "Konfiguration angelegt: ${config_dir}/monolith.env"
fi

install -o root -g root -m 0644 \
    "${app_dir}/deploy/monolith.service" \
    /etc/systemd/system/monolith.service
install -o root -g root -m 0644 \
    "${app_dir}/deploy/monolith-homekit.service" \
    /etc/systemd/system/monolith-homekit.service
install -o root -g root -m 0644 \
    "${app_dir}/deploy/monolith-http.socket" \
    /etc/systemd/system/monolith-http.socket
install -o root -g root -m 0644 \
    "${app_dir}/deploy/monolith-http.service" \
    /etc/systemd/system/monolith-http.service

systemctl daemon-reload

echo
echo "Installation vorbereitet. Nächste Schritte:"
echo "1. ${config_dir}/monolith.env ausfüllen"
echo "2. Laufzeitdateien nach ${data_dir} kopieren"
echo "3. sudo systemctl enable --now monolith monolith-homekit"
echo "4. Optional: sudo bash deploy/setup-local-url.sh für http://monolith.local"
