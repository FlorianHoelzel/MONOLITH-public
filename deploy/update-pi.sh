#!/usr/bin/env bash
set -euo pipefail

app_dir="/opt/monolith"

cd "${app_dir}"
git pull --ff-only
"${app_dir}/.venv/bin/python" -m pip install -r requirements.txt
sudo systemctl restart monolith monolith-homekit
sudo systemctl --no-pager --full status monolith monolith-homekit
