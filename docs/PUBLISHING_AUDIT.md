# Prüfung vor der GitHub-Veröffentlichung

Stand: 9. Oktober 2026.

## Ergebnis und Umfang

Der öffentliche Quellstand umfasst einschließlich der ergänzten MIT-Lizenz 121 Dateien. Geprüft wurden Backend,
HomeKit-Bridge, Frontend, Templates, Tests, Konfigurationsbeispiele, Deployment,
Desktop-Wrapper, Lockdatei, Dokumentation, Bilder, Bild-/Schriftmetadaten,
Git-Autoren und gespeicherte Git-Objekte sowie Veröffentlichungskopie und ZIP.

Es wurden keine echten Zugangsdaten, API-Schlüssel, privaten Schlüssel,
persönlichen Konto-/Kontaktangaben, produktiven IP-/MAC-Adressen,
Geräteseriennummern oder gespeicherten privaten Kalender-, Finanz-, Haustier-
oder Bestelldaten im finalen Quellstand gefunden. Die Prüfung kombiniert
manuelle Sichtung, strukturierte Auswertung und Musterprüfungen; sie ist keine
Garantie gegen jede denkbare unbekannte Geheimnisform.

## Bereinigungen und konkrete Ergebnisse

| Bereich | Ergebnis |
| --- | --- |
| Namen und Profile | Neutrale Personen- und Gerätebezeichnungen; Anwesenheitsprofile verwenden generische Geräte statt einer persönlichen Telefon-/Uhrenzuordnung. |
| Geräte und Räume | Alle 20 Gerätenamen und Raumzuordnungen sind neutrale Beispiele. Interne IDs verwenden `device_*`; HomeKit-Namen, Netzwerklabels und Geräteereignisse folgen diesen Beispielen. |
| Kamera | Neutrale Kamerabezeichnung; RTSP-Adresse, Benutzername und Passwort sind leer. |
| Picnic, iCloud und andere Integrationen | Kontofelder, Passwörter, API-Schlüssel und Gerätekennungen sind leer. Session-/Pairing-Dateien sind nicht getrackt. |
| Adressen | Nur Beispiel-, Loopback-, Bind- und Broadcast-Adressen. Alle fünf vorkommenden MAC-Adressen sind synthetische Testwerte. |
| Testdaten | Auffällige Paket-, Stadtteil-, Termin-, Finanz- und Gewichtsbeispiele neutralisiert. Die verbleibenden Orte, Beträge und Daten sind ausdrücklich Testfixtures und keine vorkonfigurierte Haushaltsdatenbank. |
| Dokumentation und Kommentare | Frühere konkrete Geräte-Raumzuordnungen und Aussagen zu persönlicher Nutzung entfernt. Unterstützte Integrationen und allgemeine Installationsanleitungen bleiben dokumentiert. |
| Private Dateien | Keine echte `.env`, Datenbank, Pairing-Datei, privater Schlüssel, Logdatei, Sicherung oder Screenshot im Quellarchiv. Ignore- und Deployment-Archivregeln schließen diese Dateitypen aus. |
| ZIP-Metadaten | Feste Dateizeitstempel statt lokaler Bearbeitungszeiten; keine Benutzer-/Besitzerkennungen oder `.git`-Dateien im Archiv. |
| Lokale Vorschau | Isolierte Daten, keine geerbten Gerätezugangsdaten; der tatsächliche Entwicklungsrechnername wird in Systemstatus-Antworten durch `demo-host` ersetzt. |

Die Räume und Integrationstypen dienen als öffentliches Beispielschema. Sie
enthalten keinen Grundriss, Standort, tatsächlichen Gerätebestand oder
persönliche Gerätekonfiguration. Drittanbieter-Autoren, öffentliche
Dienstadressen und erforderliche Lizenz-/Herkunftshinweise bleiben erhalten.
Eine E-Mail-Adresse in der npm-Lockdatei gehört zu einem Abhängigkeitshinweis
des Paketautors. Die Lockdatei verweist ausschließlich auf das öffentliche
npm-Registry.

## Bilder und verbleibende Herkunftsangaben

Das unbenutzte Wolkenbild und eine nur noch vorab gecachte Hintergrundgrafik
wurden entfernt. Die Sternengrafik wird unter `/design-lab` verwendet.
Die verbleibenden Bilder zeigen abstrakte Grafiken und enthalten keine
gefundenen EXIF-/GPS- oder PNG-Textmetadaten. Die Schriften enthalten ihre
öffentlichen Hersteller-/Lizenzangaben.

**Logo und verwendete Sternengrafik enthalten weiterhin C2PA-Herkunftsmetadaten:**
Bildgenerator-/Softwareangaben, Erstellungszeitpunkte, Manifest-/Instanz-IDs
und öffentliche Signierzertifikate. Die strukturiert ausgelesenen Manifeste
enthielten keine gefundenen persönlichen Kontoangaben, Benutzerpfade oder
Prompts. Diese Herkunftsmetadaten wurden nicht entfernt; freigegeben war die
Entfernung unbenutzter Bilder. Die Erstellungszeitpunkte sind damit weiterhin
aus diesen zwei Bilddateien auslesbar.

## Git und Veröffentlichungskopien

Zum Abschluss der ursprünglichen Prüfung enthielten beide Repositories jeweils
einen neutralen Initial-Commit und kein Remote. Frühere Commitstände, Reflogs und interne Git-Snapshot-Referenzen wurden
entfernt, anschließend nicht mehr referenzierte Objekte bereinigt. Auch die
verbleibenden gespeicherten Git-Blobs wurden auf entfernte Angaben geprüft.

Die separate Veröffentlichungskopie liegt unter
`.verification/github-public-source`, das ZIP daneben. Inhalt und Dateiliste
entsprechen dem finalen Quellstand. Nicht einfach den gesamten Arbeitsordner
als Archiv hochladen: `.venv`, `.verification` und lokale Caches enthalten
Entwicklungs-/Testartefakte und können lokale Pfade enthalten. Sie sind vom
Git-Quellstand und vom vorbereiteten Quellcode-ZIP ausgeschlossen.

Neue Quellkopien lassen sich mit `python -m tools.prepare_public_source`
erzeugen. Das Werkzeug prüft private Dateinamen und typische Secret-Signaturen,
übernimmt keine Git-Historie und überschreibt keine vorhandene Kopie.
Neue Dateien und neu gebaute Installer müssen erneut geprüft werden.
Es sind aktuell keine fertigen Desktop-Installer vorhanden.

## Verifikation und Grenzen

- 166 Python-Regressionstests und 7 Node-Web-Push-Tests erfolgreich.
- Betroffene Kamera-/Ereignistests nach den letzten Beschriftungsänderungen erneut erfolgreich.
- Syntax, neue Geräte-IDs und verwendete Bildreferenzen geprüft.
- Tests mit `PYTHON_DOTENV_DISABLED=1` und isolierten temporären Daten ausgeführt.
- Automatisierte Tests starteten keine persistenten Dashboard- oder HomeKit-Dienste.
- Die lokale Durchsichtsvorschau wurde auf ausdrücklichen Wunsch separat gestartet.
- Während der ursprünglichen Prüfung kein Deployment oder GitHub-Upload ausgeführt.

Die öffentliche Ausgabe ist für eine neue Installation vorgesehen. Die
neutralisierten Geräte-/Profilkennungen und Haustiertabellen übernehmen keine
Daten aus älteren Installationen; dafür wäre eine gesonderte Migration nötig.

Anschließend wurde der geprüfte Stand auf ausdrücklichen Wunsch nach
`https://github.com/FlorianHoelzel/MONOLITH-public` hochgeladen. Die ebenfalls
ausdrücklich gewählte MIT-Lizenz wurde danach ergänzt; diese Folgeänderung
enthält nur Lizenz- und Dokumentationsangaben sowie Paketmetadaten.
Öffentliches Quellcodehosting ändert nichts daran, dass
das Dashboard im vertrauenswürdigen lokalen Netz betrieben werden soll.
