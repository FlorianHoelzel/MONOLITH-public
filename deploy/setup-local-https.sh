#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Bitte mit sudo ausführen: sudo bash deploy/setup-local-https.sh"
    exit 1
fi

app_dir="/opt/monolith"
avahi_config="/etc/avahi/avahi-daemon.conf"
caddyfile_source="${app_dir}/deploy/Caddyfile"
caddyfile_target="/etc/caddy/Caddyfile"
caddy_root_cert="/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt"
download_cert="${app_dir}/static/monolith-local-ca.crt"

if [[ ! -f "${caddyfile_source}" ]]; then
    echo "${caddyfile_source} fehlt. Bitte zuerst den aktuellen MONOLITH-Code deployen."
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

apt-get update
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg

if ! command -v caddy >/dev/null 2>&1; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        > /etc/apt/sources.list.d/caddy-stable.list
    chmod o+r \
        /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
        /etc/apt/sources.list.d/caddy-stable.list
    apt-get update
    apt-get install -y caddy
fi

install -o root -g root -m 0644 \
    "${caddyfile_source}" \
    "${caddyfile_target}"

caddy validate --config "${caddyfile_target}" --adapter caddyfile

systemctl disable --now monolith-http.socket 2>/dev/null || true
systemctl stop monolith-http.service 2>/dev/null || true
systemctl restart avahi-daemon.service
systemctl enable --now caddy.service

for _ in {1..20}; do
    if [[ -f "${caddy_root_cert}" ]]; then
        break
    fi
    sleep 1
done

if [[ ! -f "${caddy_root_cert}" ]]; then
    echo "Caddys lokales Stammzertifikat wurde nicht erzeugt."
    journalctl -u caddy.service -n 30 --no-pager
    exit 1
fi

install -o monolith -g monolith -m 0644 \
    "${caddy_root_cert}" \
    "${download_cert}"

curl --fail --silent --show-error \
    --cacert "${caddy_root_cert}" \
    --resolve monolith.local:443:127.0.0.1 \
    https://monolith.local/ \
    >/dev/null

echo
echo "MONOLITH ist lokal über https://monolith.local erreichbar."
echo "iPhone-Zertifikat:"
echo "http://monolith.local:5000/static/monolith-local-ca.crt"
