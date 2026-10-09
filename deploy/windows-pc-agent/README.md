# MONOLITH PC-Agent

Der Windows-Agent meldet neben der Erreichbarkeit des PCs auch die aktive
Windows-Mediensitzung an MONOLITH. Unterstützte Angaben sind Wiedergabestatus,
Titel, Künstler, Album und Quellanwendung.

## Voraussetzungen

- Windows 10 ab Build 17763 oder Windows 11
- Python 3.14
- Derselbe geheime `PC_AGENT_TOKEN` auf dem PC und in
  `/etc/monolith/monolith.env` auf dem Raspberry Pi

## Installation auf dem PC

Den folgenden Befehl in einer PowerShell mit Administratorrechten ausführen:

```powershell
.\deploy\windows-pc-agent\install.ps1
```

Das Skript fragt den bestehenden `PC_AGENT_TOKEN` verdeckt ab, installiert die
Windows-Medienabhängigkeiten und ersetzt die geplante Aufgabe `PC Agent`. Das
Token wird nicht in den Quellcode geschrieben. Es liegt in
`%LOCALAPPDATA%\MONOLITH\pc-agent-token.txt` und ist nur für das eigene
Windows-Benutzerkonto lesbar.

Die Aufgabe läuft bei der Anmeldung in der interaktiven Sitzung des aktuellen
Benutzers. Das ist erforderlich, weil Windows den globalen Medienstatus nicht
aus einem Dienst oder einer System-Sitzung bereitstellt. Der Task zeigt danach
auf:

```text
C:\Projects\MONOLITH\deploy\windows-pc-agent\pc_agent.py
```

Auf dem Pi werden zusätzlich folgende Werte benötigt:

```dotenv
PC_AGENT_TOKEN=<gleiches geheimes Token wie auf dem PC>
PC_CHECK_INTERVAL_SECONDS=5
```

Danach MONOLITH mit dem normalen Deployment-Skript bereitstellen. Das Skript
kopiert die geheime Pi-Konfiguration nicht und überschreibt sie nicht.

## Was erkannt wird

- Wiedergabe läuft, pausiert oder ist gestoppt
- Titel, Künstler und Album, sofern die App diese Daten meldet
- Quellanwendung wie Spotify, VLC oder ein Browser

Die Abfrage ist nur lesend. Falls eine Anwendung keine Windows-Mediensitzung
anlegt, kann der Agent deren Wiedergabe nicht erkennen.
