param(
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"

$projectRoot = (
    Resolve-Path (
        Join-Path $PSScriptRoot ".."
    )
).Path

$archive = Join-Path (
    [System.IO.Path]::GetTempPath()
) "monolith-source-update.tar.gz"

$excludedNames = @(
    ".git",
    ".venv*",
    ".verification",
    "__pycache__",
    "node_modules",
    "desktop/dist",
    ".env",
    ".env.*",
    "*.db*",
    "*.sqlite*",
    "*.pem",
    "*.key",
    "*.crt",
    "*.p12",
    "*.pfx",
    "*.bak",
    "*.backup",
    "*.dump",
    "*.zip",
    "*.tar*",
    "*.7z",
    "*.state*",
    "*_session.json*",
    "*_state.json*",
    "*pairing*.json*",
    "*token*.txt",
    "*token*.json",
    "credentials*.json",
    "secrets*.json",
    "window-state.json",
    "recovery",
    "backups",
    "captures",
    "screenshots",
    "*.log",
    "monolith.db*",
    "lg_tv_pairing.json",
    "lg_tv_pairing.sqlite",
    "apple_tv_pyatv.conf",
    "monolith_homekit.state",
    "motion_*_session.json*",
    "presence_state.json",
    "picnic_session.json",
    "picnic_state.json",
    "vapid_private_key.pem"
)

# Only relocated source files are removed; runtime files are never listed here.
$relocatedSourceFiles = @(
    "apple_tv.py",
    "camera_stream.py",
    "data_paths.py",
    "database.py",
    "devices.py",
    "homekit_config.py",
    "homepod.py",
    "icloud_planner.py",
    "lg_tv.py",
    "matterbridge.py",
    "network_monitor.py",
    "nintendo_switch.py",
    "pet_monitor.py",
    "package_monitor.py",
    "package_tracking.py",
    "pc_status.py",
    "picnic.py",
    "presence.py",
    "push_notifications.py",
    "raspberry_pi.py",
    "recipe_api.py",
    "sensors.py",
    "system_services.py",
    "weather.py",
    "wewash.py",
    "pair_apple_tv.py",
    "pair_lg_tv.py",
    "scan_apple.py",
    "TECH_STACK.md",
    "TODO.md"
)
$relocatedSourcePaths = ($relocatedSourceFiles | ForEach-Object {
    "/opt/monolith/$_"
}) -join " "

try {
    $tarArguments = @(
        "-czf",
        $archive
    )

    foreach ($name in $excludedNames) {
        $tarArguments += "--exclude=$name"
    }

    $tarArguments += @(
        "-C",
        $projectRoot,
        "."
    )

    & tar @tarArguments

    if ($LASTEXITCODE -ne 0) {
        throw "Quellcodearchiv konnte nicht erstellt werden."
    }

    & scp $archive "${Target}:monolith-source-update.tar.gz"

    if ($LASTEXITCODE -ne 0) {
        throw "Upload auf den Pi fehlgeschlagen."
    }

    & ssh $Target (
        "set -e; " +
        "tar -xzf ~/monolith-source-update.tar.gz " +
        "-C /opt/monolith; " +
        "rm -f $relocatedSourcePaths; " +
        "rm -f /opt/monolith/templates/telemetry_lab.html " +
        "/opt/monolith/static/telemetry-lab.css " +
        "/opt/monolith/static/telemetry-lab.js " +
        "/opt/monolith/prototypes/navigation-lab.html " +
        "/opt/monolith/test_telemetry_lab.py; " +
        "rm -f ~/monolith-source-update.tar.gz"
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Entpacken auf dem Pi fehlgeschlagen."
    }

    if ($InstallDependencies) {
        & ssh -t $Target (
            "sudo /opt/monolith/.venv/bin/python -m pip install " +
            "-r /opt/monolith/requirements.txt"
        )

        if ($LASTEXITCODE -ne 0) {
            throw "Installation der Abhängigkeiten fehlgeschlagen."
        }
    }

    & ssh -t $Target (
        "sudo install -o root -g root -m 0644 " +
        "/opt/monolith/deploy/monolith.service " +
        "/etc/systemd/system/monolith.service && " +
        "sudo install -o root -g root -m 0644 " +
        "/opt/monolith/deploy/monolith-homekit.service " +
        "/etc/systemd/system/monolith-homekit.service && " +
        "sudo systemctl daemon-reload && " +
        "sudo systemctl restart monolith.service " +
        "monolith-homekit.service"
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Neustart der Pi-Dienste fehlgeschlagen."
    }

    Start-Sleep -Seconds 10

    $response = Invoke-WebRequest -UseBasicParsing -Uri ("http://{0}:5000/" -f ($Target -split "@")[-1]) -TimeoutSec 15

    if ($response.StatusCode -ne 200) {
        throw "Dashboard-Test meldet HTTP $($response.StatusCode)."
    }

    Write-Host "MONOLITH erfolgreich auf den Pi übertragen."
}
finally {
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force
    }
}
