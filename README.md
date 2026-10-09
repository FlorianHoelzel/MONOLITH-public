# MONOLITH

Smart-Home- und Alltagsdashboard mit Flask, SQLite, HomeKit und einer optionalen
Desktop-App. Diese Ausgabe enthält neutrale Personen, neutrale Beispieldaten und keine Produktionskonfiguration oder bisherige Git-Historie.

## Vorbereitung

Python 3.13 oder neuer verwenden (für die Picnic-Abhängigkeit erforderlich).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Eigene Zugangsdaten und Geräteadressen nur in `.env` eintragen. Die beiden
generischen Personen werden über `PRESENCE_PERSON_*` konfiguriert.
Die Gerätekarten zeigen einen beispielhaften Haushalt; ihre Zuordnung kann
in `monolith/devices.py`, `monolith/sensors.py` und den Templates angepasst werden.
Die Geräte-IDs (`device_*`) sind neutrale Beispielkennungen. Für eine eigene
Installation die Zuordnung im Backend und in der HomeKit-Bridge gemeinsam
anpassen. Ohne Konfiguration verbinden sich Geräteintegrationen nicht mit
einem Heimgerät.

## Projektstruktur

- `monolith/`: Backend und Integrationen
- `app.py`, `homekit_bridge.py`: Dienst-Einstiegspunkte
- `templates/`, `static/`: Dashboard und PWA
- `desktop/`: optionaler Electron-Wrapper
- `tools/`: Diagnose und Pairing, z. B. `python -m tools.scan_apple`
- `deploy/`: Installation und Deployment für einen eigenen Raspberry Pi
- `tests/`: Regressionstests
- `docs/`: technische Dokumentation

## Tests

```powershell
$env:PYTHON_DOTENV_DISABLED = "1"
$env:MONOLITH_DATA_DIR = Join-Path $PWD ".verification/test-data"
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
node --test tests/test_web_push.cjs
```

## Eigener Pi

Installation und Laufzeitpfade: [PI_MIGRATION.md](PI_MIGRATION.md).
Deployment erfordert einen ausdrücklich angegebenen eigenen SSH-Zielhost:

```powershell
./deploy/deploy-to-pi.ps1 -Target "user@your-pi.local"
```

Bei geänderten Python-Abhängigkeiten `-InstallDependencies` ergänzen.
Datenbanken und private Konfiguration bleiben vom Quellcode getrennt.
Das Dashboard ist für ein vertrauenswürdiges Heimnetz vorgesehen; keine
öffentliche Router-Portfreigabe einrichten.

## Veröffentlichung und Lizenz

Dies ist eine lokal vorbereitete Kopie; sie wurde noch nicht hochgeladen.
Vor Veröffentlichung eine Lizenz für den eigenen Code auswählen.
Vorhandene Lizenz- und Herkunftshinweise zu Schriften und des im Design Lab verwendeten Shaders bleiben erhalten.
