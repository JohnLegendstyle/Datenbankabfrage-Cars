# Cars · Charakter-Datenbank

Eine Website mit Python/Flask, einer echten SQLite-Datenbank und einer Such-API.
HTML, CSS und JavaScript bleiben in drei getrennten Dateien. Die Figuren stehen
nicht mehr als JavaScript-Liste im Browser: Jede Suche wird auf dem Server als
parametrisierte SQL-Abfrage ausgeführt.

## Lokal starten (Mac)

Im Projektordner:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Danach http://localhost:8000 öffnen. Ein Doppelklick auf `index.html` reicht bei
einer Website mit Datenbank nicht mehr. Die Datenbank entsteht beim ersten Start
automatisch unter `data/cars.sqlite3`.

## Railway

Das bestehende GitHub-Repository mit dem Web-Service verbunden lassen. Railway
verwendet die `Dockerfile` und die Einstellungen aus `railway.toml`:

- Build: Dockerfile im Hauptverzeichnis.
- Start: `sh start.sh` (Gunicorn, ein Prozess mit vier Threads).
- Port: Railway-Variable `PORT`, automatisch ausgewertet.
- Healthcheck: `/api/health`.
- Root Directory: Hauptverzeichnis des Repositorys.

### Dauerhafter Speicher

Im Railway-Projekt ein **Volume an den bestehenden Web-Service hängen** und als
**Mount Path `/data`** eintragen. Danach die vorgemerkten Änderungen bereitstellen.
Ein vorhandenes Volume lässt sich verwenden, wenn es an diesen Service gebunden
ist. Ein eventuell vorhandenes Datenbank-Volume eines anderen Services nicht
verschieben oder überschreiben.

Railway stellt `RAILWAY_VOLUME_MOUNT_PATH` bereit. Die Anwendung nutzt diesen
Pfad automatisch; damit liegt die Datei unter `/data/cars.sqlite3`. Keine weitere
Datenbank und keine Zugangsdaten erforderlich. Eine zuvor gesetzte Variable
`DATA_DIR` würde den Volume-Pfad überschreiben und sollte entfernt oder ebenfalls
auf `/data` gesetzt werden.

`/api/health` muss nach erfolgreicher Bereitstellung `status: "ok"` und
`persistent: true` zurückgeben. Ohne Volume funktioniert der lesbare Katalog,
die SQLite-Datei wird aber bei einem neuen Deployment aus dem mitgelieferten
Katalog neu aufgebaut. Ein `persistent: false` bestätigt also keine dauerhafte
Speicherung. Die Volume-Erstellung ist eine Einstellung im Railway-Dashboard;
`railway.toml` erstellt kein Volume.

Volumes können Kosten nach dem vorhandenen Railway-Tarif verursachen. Diese
Anwendung braucht für ihren Katalog nur wenige Megabyte. Bei SQLite mit Volume
bleibt es bei einer Instanz; horizontale Replikate teilen diese Datei nicht.

## Katalog und Quellen

`catalog/characters.json` enthält den recherchierten Stand, Quellen pro Figur,
Wiki-Revisionsnummern, Bilder, alternative Namen und Auftritte. Die Filmlisten
stammen aus den drei Cars-Filmkategorien des Pixar Cars Wiki. Die Serien werden
über die Kategorie `Cars on the Road characters` und Figuren-/Besetzungslisten
der veröffentlichten Cars-Toons-Episoden ergänzt. Zusätzlich enthalten sind
Hook und das Geisterlicht, Miss Fritter’s Racing Skoool, die Cars-Beiträge aus
Pixar Popcorn und LEGO Pixar: Bricktoons.

Gruppenartikel mit mehreren benannten Figuren werden in einzelne Karten
aufgeteilt. Diese verwenden ein gemeinsames Bild und weisen darauf hin. Reine
Gruppen, unbenannte Nebenfiguren und Artikel ohne belegten Figurenbezug werden
ausgeschlossen. Die Quelle enthält auch benannte Hintergrundfiguren und nur
erwähnte Figuren. Das ist ein nachvollziehbarer Community-Katalog, keine von
Disney bestätigte vollständige Liste. Englische Originalnamen bleiben erhalten;
deutsche Namen werden als Alias erfasst, soweit in der Quelle angegeben.

`catalog/import-report.json` dokumentiert Umfang und ausgeschlossene Einträge.
`catalog/overrides.json` enthält gezielte Namens-/Bildkorrekturen und die bereits
vorhandenen deutschen Beschreibungen. Es werden keine vollständigen Artikeltexte
übernommen. Wiki-Metadaten: CC BY-SA gemäß
https://pixarcars.fandom.com/ . Bilder unterliegen den Bedingungen ihrer jeweiligen
Quelldatei, meist Disney/Pixar. Die Angabe einer Bildquelle ist keine Lizenz zur
beliebigen kommerziellen Verwendung.

Die Bilder werden direkt von den Quellservern geladen. Bei fehlenden oder später
nicht mehr erreichbaren Bildern bleibt die Karte sichtbar und zeigt einen Hinweis.
Bei der Erstprüfung am 24.09.2026 hat der Wiki-Bildserver automatisierte Abrufe
mit einer Cloudflare-Prüfung blockiert. Die Erreichbarkeit dieser Bilder im
Nutzerbrowser ist daher nicht bestätigt. Für 24 Hauptfiguren sind stattdessen
erreichbare Bildquellen von Disney und Pixar hinterlegt.

### Daten aktualisieren

```sh
pip install -r requirements-import.txt
python tools/import_catalog.py --cache .import-cache-neu
python -m unittest discover -s tests -v
```

Ein neuer Cache-Ordner lädt aktuelle Quelldaten. Der Import braucht Netzwerkanbindung
und erfolgt bewusst vor einem Commit, nicht bei jedem Serverstart. Anschließend
die geänderten Katalogdateien prüfen, committen und pushen.

Beim Start prüft die Anwendung den Katalog-Hash. Unveränderte Daten werden nicht
erneut importiert. Ein neuer Katalog wird in einer Transaktion übernommen.
Die Datenbankdatei wird dabei nicht gelöscht. Entfernte Wiki-Einträge werden
ausgeblendet. Manuelle Änderungen an mitgelieferten Wiki-Einträgen können durch
ein Katalog-Update überschrieben werden; Korrekturen daher in `overrides.json`
pflegen. Andere Tabellen und selbst angelegte Datensätze bleiben erhalten.

## API

```text
GET /api/characters?q=Hook&media=cars-2&sort=name&page=1&limit=24
GET /api/media
GET /api/health
```

Suchfelder: Name, Aliasse, Fahrzeugtyp, Modell. Groß-/Kleinschreibung und Akzente
werden normalisiert. Sortierung: `featured`, `name`, `name-desc`. Seitengröße:
1 bis 60. Ungültige Parameter liefern HTTP 400. Die API ist ausschließlich lesend.
Die Datenbankdatei, Quellcode, Katalogdateien und Git-Metadaten werden nicht als
öffentliche Dateien ausgeliefert.

## Tests

```sh
python -m unittest discover -s tests -v
```

Geprüft werden Alias-/Akzentsuche, Film- und Serienfilter, Pagination, Eingabeprüfung,
SQL-Injection-Eingaben, Schutz interner Dateien, Neustart-Persistenz sowie ein
Rollback bei fehlerhaften Katalog-Updates.
