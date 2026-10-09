# MONOLITH – Tech-Stack

MONOLITH wird in lokalen Checkouts unter Windows entwickelt und läuft produktiv
auf einem Raspberry Pi. Das Backend verwendet Python, Flask und SQLite.
Das Dashboard nutzt HTML, CSS und JavaScript.

## Architektur

```text
Browser / PWA / Electron
         ↓ HTTPS über Caddy
Flask + Waitress auf Raspberry Pi
         ↓
SQLite + Geräte- und Cloud-Integrationen

Separate HomeKit-Bridge mit HAP-python
```

## Backend und Datenhaltung

- Python 3 in einer virtuellen Umgebung
- Flask 3 für Routing, Jinja2-Templates und die HTTP-/JSON-API
- Waitress als produktiver WSGI-Server
- `threading` und `asyncio` für Hintergrundüberwachung und Geräteprotokolle
- `python-dotenv` für lokale Konfiguration; systemd-EnvironmentFile auf dem Pi
- SQLite über die Python-Standardbibliothek, ohne ORM
- Ereignisse, Sensorverläufe, Gerätezustände, Planungs- und Finanzdaten in SQLite
- Separate Pairing-, Session- und Statusdateien für Integrationen

Die direkten Python-Abhängigkeiten und ihre Versionsbereiche stehen in
[requirements.txt](../requirements.txt): `aiowebostv`, `aiohttp`, `caldav`,
`Flask`, `fritzconnection`, `HAP-python`, `python-dotenv`, `requests`,
`python-picnic-api2`, `pyatv`, `pywebpush` und `waitress`.

## Bestehendes Dashboard

- HTML und Jinja2 unter `templates/`
- Eigenes CSS und Vanilla JavaScript unter `static/`
- Fetch API und regelmäßiges HTTP-Polling
- `localStorage` für lokale UI-Einstellungen
- Chart.js für Diagramme und Tabler Icons als Icon-Webfont
- Kein Bundler für dieses Frontend

## PWA und Benachrichtigungen

- Web App Manifest, App-Icons und Standalone-Darstellung
- Service Worker für App-Shell, statische Dateien und Push-Ereignisse
- Web Push mit `pywebpush`, gerätespezifischen Subscriptions und VAPID
- Declarative-Web-Push-Payloads und klassische Service-Worker-Verarbeitung
- Dynamische API-Daten werden nicht offline gespeichert
- Öffnen des Dashboards benötigt weiterhin Zugriff auf das Heimnetz

## Windows-Desktop-App

- Electron als Wrapper für das auf dem Pi laufende Dashboard
- Node.js und npm für Entwicklung und Build
- `electron-builder` mit NSIS für den Windows-Installer
- Context Isolation und Chromium-Sandbox
- Offline-Seite, native Benachrichtigungen und externe Links im Standardbrowser
- Standardadresse `https://monolith.local`, konfigurierbar über `MONOLITH_URL`

Details stehen in [desktop/README.md](../desktop/README.md).

## Geräte- und Cloud-Integrationen

| Integration | Technik |
|---|---|
| Apple TV und HomePod | `pyatv`, asyncio und Apple-Medienprotokolle |
| Apple HomeKit | Separater Dienst mit `HAP-python`; PIN in privater Konfiguration |
| LG webOS TV | `aiowebostv`, WebSockets und Wake-on-LAN |
| Matterbridge | WebSocket-Client mit `aiohttp` |
| FRITZ!Box | `fritzconnection` / TR-064 für Anwesenheit und Netzwerkinventar |
| Nintendo Switch | Netzwerkverbindung aus der FRITZ!Box, keine Nintendo-Anmeldung |
| Windows-PC | Netzwerkstatus und eigener authentifizierter PC-Agent |
| iCloud-Kalender | CalDAV mit `caldav` |
| Picnic | `python-picnic-api2` mit Zwei-Faktor-Authentifizierung |
| WeWash | HTTP-API über `requests` |
| Paketverfolgung | Ship24-API, Carrier-Erkennung und externe Trackinglinks |
| Kamera-Livebild | Lokaler RTSP-Stream über FFmpeg als MJPEG-Browser-Vorschau |

FFmpeg ist eine zusätzliche Systemabhängigkeit für die Kamera-Vorschau.
Die Verfügbarkeit einzelner Integrationen hängt von der privaten Konfiguration
und den erreichbaren Geräten beziehungsweise Diensten ab.

## Tests und Diagnose

- Python-Regressionstests unter `tests/` mit `unittest` und `unittest.mock`
- Temporäre SQLite-Datenbanken in Datenbanktests
- JavaScript-Web-Push-Tests mit dem integrierten Node.js-Test-Runner
- Manuelle FRITZ!Box-Diagnose unter `tools/check_fritz.py`

Testbefehle stehen in [README.md](../README.md). Es gibt keine CI/CD-Pipeline
im aktuellen Repository.

## Produktion und Deployment

- Raspberry Pi OS 64-bit
- `monolith.service` für das Dashboard, `monolith-homekit.service` für die Bridge
- Waitress auf Port `5000`; Caddy für lokales HTTPS mit interner CA
- Avahi/mDNS für die lokale Namensauflösung
- systemd-Hardening mit eigenem Benutzer und eingeschränktem Dateisystemzugriff
- Quellcode unter `/opt/monolith`, Laufzeitdaten unter `/var/lib/monolith`
- Private Konfiguration unter `/etc/monolith/monolith.env`
- GitHub-Repository zur Synchronisation der Entwicklungs-Checkouts
- Benutzergeführtes PowerShell-Deployment über SSH, SCP und TAR
- `pip` für Python-Abhängigkeiten
- Kein Docker oder Kubernetes; kein öffentlicher Router-Portforwarding-Zugriff

Git-Push und Pi-Deployment sind separate Schritte. Das Deployment überträgt
Quellcode und erhält die produktive Datenbank sowie Pairing- und Laufzeitdateien.
Details und die einmalige HomeKit-PIN-Migration stehen in
[PI_MIGRATION.md](../PI_MIGRATION.md).
