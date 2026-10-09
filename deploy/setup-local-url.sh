#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Bitte mit sudo ausführen: sudo bash deploy/setup-local-url.sh"
    exit 1
fi

app_dir="/opt/monolith"
avahi_config="/etc/avahi/avahi-daemon.conf"
proxy_binary="/usr/lib/systemd/systemd-socket-proxyd"

if [[ ! -x "${proxy_binary}" ]]; then
    echo "${proxy_binary} fehlt; Port 80 kann nicht eingerichtet werden."
    exit 1
fi

if [[ ! -f "${avahi_config}" ]]; then
    echo "${avahi_config} fehlt; Avahi/mDNS ist nicht installiert."
    exit 1
fi

if ! grep -Eq '^[[:space:]]*host-name=monolith[[:space:]]*$' "${avahi_config}"; then
    if [[ ! -f "${avahi_config}.monolith-backup" ]]; then
        cp --preserve=all "${avahi_config}" "${avahi_config}.monolith-backup"
    fi

    if grep -Eq '^[[:space:]]*#?[[:space:]]*host-name=' "${avahi_config}"; then
        sed -i -E '0,/^[[:space:]]*#?[[:space:]]*host-name=.*/s//host-name=monolith/' "${avahi_config}"
    else
        sed -i '/^[[:space:]]*\[server\][[:space:]]*$/a host-name=monolith' "${avahi_config}"
    fi
fi

install -o root -g root -m 0644 \
    "${app_dir}/deploy/monolith-http.socket" \
    /etc/systemd/system/monolith-http.socket
install -o root -g root -m 0644 \
    "${app_dir}/deploy/monolith-http.service" \
    /etc/systemd/system/monolith-http.service

systemctl daemon-reload
systemctl restart avahi-daemon.service
systemctl enable --now monolith-http.socket

echo "MONOLITH ist im lokalen Netz unter http://monolith.local erreichbar."
