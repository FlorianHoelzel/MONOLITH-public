# MONOLITH auf dem Raspberry Pi

## Zielbild

- Der PC bleibt die Entwicklungsumgebung.
- Der Pi führt MONOLITH und die HomeKit-Bridge rund um die Uhr als systemd-Dienste aus.
- Quellcode liegt auf dem Pi unter `/opt/monolith`.
- Veränderliche Daten liegen getrennt unter `/var/lib/monolith`.
- Geheimnisse liegen unter `/etc/monolith/monolith.env` und nie in Git.

## Voraussetzungen

- Raspberry Pi OS 64-bit (Bookworm oder neuer)
- SSH-Zugriff auf den Pi
- feste DHCP-Zuweisung für den Pi in der FRITZ!Box
- Python 3, Git und ein eigenes Git-Remote für den Quellcode

## Einmaliger Umzug

1. Auf dem PC ein Git-Repository anlegen und in ein privates Remote pushen.
2. Auf dem Pi das Repository nach `/opt/monolith` klonen.
3. Auf dem Pi `sudo bash /opt/monolith/deploy/install-pi.sh` ausführen.
4. Die vorhandene `.env` als `/etc/monolith/monolith.env` übertragen.
5. Folgende Laufzeitdateien nach `/var/lib/monolith` übertragen:
   - `monolith.db`
   - `apple_tv_pyatv.conf`
   - `lg_tv_pairing.json`
   - `monolith_homekit.state`
   - `presence_state.json`
   - `picnic_session.json`
   - `picnic_state.json`
6. Besitzer setzen:

   ```bash
   sudo chown monolith:monolith /var/lib/monolith/*
   sudo chmod 600 /var/lib/monolith/*
   ```

7. Dienste einschalten:

   ```bash
   sudo systemctl enable --now monolith monolith-homekit
   ```

8. Dashboard unter `http://<pi-ip>:5000` testen und anschließend in der FRITZ!Box den Namen `monolith` vergeben.
9. Die lokale Kurzadresse einrichten:

   ```bash
   sudo bash /opt/monolith/deploy/setup-local-url.sh
   ```

   Danach ist das Dashboard im lokalen Netz zusätzlich unter `http://monolith.local` erreichbar. Die feste IP-Adresse bleibt unverändert.

10. Lokales HTTPS einrichten:

   ```bash
   sudo bash /opt/monolith/deploy/setup-local-https.sh
   ```

   Danach ist MONOLITH unter `https://monolith.local` erreichbar. Das von Caddy erzeugte öffentliche Stammzertifikat kann im Heimnetz unter `http://monolith.local:5000/static/monolith-local-ca.crt` heruntergeladen werden. Auf iPhone und iPad muss das Profil anschließend unter **Einstellungen > Allgemein > VPN und Geräteverwaltung** installiert und unter **Einstellungen > Allgemein > Info > Zertifikatsvertrauenseinstellungen** vollständig vertraut werden.

Vor dem Kopieren der Datenbank und Zustandsdateien MONOLITH auf dem PC beenden. Dadurch entsteht ein konsistenter Übergabestand und nicht zwei Instanzen schreiben gleichzeitig Ereignisse.

## Weiterentwicklung vom PC

Neue Installationen benötigen einen eigenen HomeKit-PIN in der privaten
Konfiguration (`HOMEKIT_PIN`, Format `XXX-XX-XXX`).

Für den aktuellen direkten SSH-Workflow genügt auf dem PC:

```powershell
.\deploy\deploy-to-pi.ps1 -Target "user@your-pi.local"
```

Das Skript überträgt ausschließlich Quellcode, startet beide Pi-Dienste neu und prüft anschließend das Dashboard. `.env`, Datenbank, Pairings und Statusdateien werden ausdrücklich ausgeschlossen. Wenn sich `requirements.txt` geändert hat:

```powershell
.\deploy\deploy-to-pi.ps1 -Target "user@your-pi.local" -InstallDependencies
```

## Automatische Paketverfolgung

Der Tab `Pakete` verwendet Ship24 für dienstleisterübergreifende Statusupdates.
Der API-Schlüssel gehört ausschließlich in `/etc/monolith/monolith.env`:

```dotenv
SHIP24_API_KEY="apik_..."
PACKAGE_REFRESH_INTERVAL_SECONDS="900"
```

- `SHIP24_API_KEY` wird im Ship24-Dashboard erzeugt und niemals an den Browser
  ausgeliefert.
- `PACKAGE_REFRESH_INTERVAL_SECONDS` ist optional und beträgt standardmäßig
  900 Sekunden. Werte unter 300 Sekunden werden auf 300 begrenzt.
- MONOLITH übermittelt die Sendungsnummer und optional die Empfänger-PLZ an
  Ship24, damit der Paketdienst erkannt und der Verlauf abgerufen werden kann.

Nach dem Ergänzen der Variablen den normalen MONOLITH-Dienst neu starten.

## Nintendo Switch

Die konfigurierte Konsole verwendet den FRITZ!Box-Netzwerkstatus.
Die Karte zeigt die von der FRITZ!Box gemeldete Netzwerkverbindung als An/Aus;
sie bestätigt nicht, ob gerade gespielt wird. `NINTENDO_SWITCH_MAC`,
`NINTENDO_SWITCH_IP` und `NINTENDO_SWITCH_ROOM` konfigurieren das Gerät über
die private Umgebung. Bei unklaren Routerabfragen bleibt der letzte Status
kurz erhalten und wird nach spätestens 60 Sekunden ohne Bestätigung unbekannt.
Eine Nintendo-Anmeldung oder ein zusätzlicher Dienst ist nicht erforderlich.

## Kamera-Livebild

Der Kamera-Tab wandelt einen lokalen RTSP-Stream mit FFmpeg in eine
Browser-Vorschau um. Die RTSP-Adresse und Zugangsdaten gehören ausschließlich
in `/etc/monolith/monolith.env`:

```dotenv
CAMERA_NAME="Wohnzimmer"
CAMERA_RTSP_URL="rtsp://kamera-ip:8554/ch2"
CAMERA_RTSP_USERNAME="..."
CAMERA_RTSP_PASSWORD="..."
CAMERA_PREVIEW_FPS="10"
CAMERA_PREVIEW_WIDTH="1280"
CAMERA_PREVIEW_QUALITY="5"
CAMERA_MAX_VIEWERS="2"
```

- Für die Dashboard-Vorschau wird der 720p-Kanal empfohlen.
- Zugangsdaten werden nie an den Browser ausgeliefert.
- Der FFmpeg-Prozess läuft nur, solange der Kamera-Tab sichtbar ist.
- `CAMERA_PREVIEW_QUALITY` verwendet die FFmpeg-JPEG-Skala. Kleinere Werte
  liefern höhere Qualität und benötigen mehr Bandbreite.

Nach dem Ergänzen der Variablen den normalen MONOLITH-Dienst neu starten.

## iCloud-Kalender

Der Planer liest Kalender per CalDAV. Die Zugangsdaten gehören ausschließlich
in `/etc/monolith/monolith.env`:

```dotenv
ICLOUD_USERNAME="name@example.com"
ICLOUD_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
ICLOUD_CALENDAR_NAMES="Privat,Familie"
ICLOUD_CACHE_SECONDS="300"
```

- `ICLOUD_APP_PASSWORD` ist ein eigenes App-spezifisches Passwort, nicht das
  normale Apple-Account-Passwort.
- `ICLOUD_CALENDAR_NAMES` ist optional. Ohne Wert werden alle erreichbaren
  iCloud-Kalender angezeigt.

Nach dem Ergänzen der Variablen den normalen Dienst neu starten. Da für den
Planer die Python-CalDAV-Abhängigkeit benötigt wird, die erste Bereitstellung
mit `-InstallDependencies` ausführen.

Beim Neustart beziehungsweise bei der Installation fragt `sudo` nach dem Pi-Passwort.

Alternativ können Änderungen später über ein eigenes Git-Remote verteilt werden. Auf dem Pi aktualisiert dann:

```bash
cd /opt/monolith
bash deploy/update-pi.sh
```

Die Dateien in `/var/lib/monolith` und `/etc/monolith` werden dabei nicht verändert.

Der private VAPID-Schlüssel für Web Push wird beim ersten Aktivieren automatisch unter `/var/lib/monolith/vapid_private_key.pem` erzeugt. Er gehört zu den Laufzeitdaten und darf nicht aus einer lokalen Entwicklungsumgebung auf den Pi kopiert werden.

Die Annahme einer Futtererinnerung durch den Push-Anbieter wird pro Subscription
in `pet_push_deliveries` gespeichert. Fehlende Rückmeldungen an den nur im
Heimnetz erreichbaren Pi lösen keine erneute Nachricht aus. Nur ausdrücklich
abgewiesene Anfragen (HTTP 429/5xx) werden mit Wartezeit erneut versucht.
Bei einem Timeout mit unklarem Annahmestatus wird keine zweite Nachricht
gesendet; die entsprechende Logmeldung unterscheidet diesen Fall vom Erfolg.
Ein bereits reservierter Versand bleibt auch nach einem Dienstneustart
reserviert, damit ein Absturz nach Annahme keinen doppelten Push erzeugt.

Die verschlüsselte Nachricht enthält das Declarative-Web-Push-Format, sodass
iOS ab 18.4 sie auch ohne laufenden Service Worker anzeigen kann. Die Anzeige
braucht keine Verbindung zum Pi; Öffnen des Dashboards und Synchronisieren
einer geänderten Subscription benötigen weiterhin das Heimnetz. Apple darf
wartende Erinnerungen bis zu sechs Stunden nach ihrer Fälligkeit aufbewahren.
Fokus-Modi und die iOS-Mitteilungseinstellungen bestimmen die sichtbare Anzeige.

Gezielte Regressionstests: `.\.venv\Scripts\python.exe -m unittest tests.test_pet tests.test_push_notifications`
und `node --test tests/test_web_push.cjs`.

## Anwesenheitserkennung

MONOLITH identifiziert persönliche Geräte anhand ihrer WLAN-MAC-Adresse.
Auf iPhone und Apple Watch sollte die private WLAN-Adresse für das Heimnetz
auf **Statisch/Fest** stehen. Nach einer Änderung muss die aktuelle Adresse
in der privaten `PRESENCE_PERSON_*`-Konfiguration eingetragen werden. Ein beliebiger aktiver Routereintrag
oder ein zuhause gebliebenes iPad wird nicht automatisch einer Person zugeordnet.

Die Erkennung liest die aktuelle IP-Adresse und bekannte MAC-Aliasse aus der
FRITZ!Box. Auf dem Pi wird zusätzlich die Erreichbarkeit über Ping und eine
frische ARP-Nachbartabelle geprüft; nur die passende MAC-Adresse bestätigt
die Anwesenheit. Alle persönlichen Geräte müssen mindestens 20 Minuten
durchgehend offline sein, bevor Abwesenheit gemeldet wird. Unklare Abfragen
und Dienstneustarts setzen diesen Timer zurück. Die Ankunftszeit bleibt bei
kurzen Aussetzern unverändert.

## Diagnose und Backup

Die HomeKit-Bridge speichert pro Bewegungsmelder die letzte Bewegung und
den Feed-Status der laufenden Sitzung in
`/var/lib/monolith/motion_<raum>_session.json` (bedroom, kitchen, hallway,
livingroom). Dienstneustarts behalten dadurch alle Bewegungssitzungen bei.
Erst nach mindestens 3 Minuten ohne Bewegung (Wohnzimmer: 15 Minuten)
erzeugt die nächste Bewegung einen neuen Feed-Eintrag. Die Dateien entstehen
automatisch und werden beim Deployment nicht überschrieben.

```bash
journalctl -u monolith -u monolith-homekit -f
systemctl status monolith monolith-homekit
sudo python3 -c "import sqlite3; source = sqlite3.connect('/var/lib/monolith/monolith.db'); target = sqlite3.connect('/var/lib/monolith/monolith.db.backup'); source.backup(target); target.close(); source.close()"
```

Kein Portforwarding aus dem Internet auf Port 80, 443 oder 5000 einrichten. MONOLITH ist ausschließlich im lokalen Heimnetz erreichbar.

Die Datenbank verwendet WAL, damit Feed-Abfragen parallel zu Schreibzugriffen
laufen können. `monolith.db-wal` und `monolith.db-shm` sind Laufzeitdateien und
werden nicht deployed. Für Backups bei laufenden Diensten die SQLite-Backup-API
wie oben verwenden; eine Kopie nur von `monolith.db` kann aktuelle Änderungen
auslassen.
