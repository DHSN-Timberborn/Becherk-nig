# Satzball – Betrieb auf dem Server

Satzball läuft als fertiges Docker-Image (`ghcr.io/kootaro05/satzball`, von der CI nach jedem grünen Lauf auf
`main` gebaut) hinter **Caddy**. Caddy holt und erneuert das HTTPS-Zertifikat selbst. Optional läuft auf
demselben Server der Bierpong-Ableger **Becherkönig** mit eigener Datenbank und eigener Domain.
Alles steht in `compose.yaml`; die Daten liegen in den Volumes `satzball-data` und `becherkoenig-data`.

Erprobt auf Debian 12. Als `root` angemeldet entfällt das `sudo` vor den Befehlen.

> **Tipp zum Einfügen ins Terminal:** Befehle einzeln einfügen. Dateien mit `nano` bearbeiten
> (speichern **Strg + O**, **Enter**, beenden **Strg + X**).

## Voraussetzungen

- Ein Server mit offenen Ports **80** und **443** (für Becherkönig ohne Domain zusätzlich **8080**).
  Läuft dort schon ein Webserver (nginx, Apache), muss er weg – Caddy braucht diese Ports.
- Pro App eine **Domain mit DNS-Eintrag (Typ A)** auf die Server-IP. Prüfen:
  `getent hosts volleyball.example.de` muss die Server-IP zeigen. Ohne Domain geht es auch – dann nur über
  `http://<IP>` und ohne HTTPS (siehe unten).
## Installation mit dem Skript (empfohlen)

Auf einem frischen Debian/Ubuntu-Server reicht ein Befehl:

```bash
curl -fsSL https://raw.githubusercontent.com/Kootaro05/Satzball/main/install.sh | sudo bash
```

Das Skript installiert bei Bedarf Docker und git und fragt dann in der Konsole: Becherkönig dazu ja/nein,
Domains (leer = nur über die IP), Verantwortliche/r für die Datenschutzerklärung, SMTP-Zugang (optional),
Orga-Zugang mit Passwort und ob ein Testturnier angelegt werden soll. Danach schreibt es alles nach
`/opt/satzball`, startet die Container, legt den Orga-Zugang an und richtet die tägliche Sicherung ein.
Am Ende steht, unter welcher Adresse es weitergeht. Alles lässt sich später wie unten beschrieben ändern.
Bricht das Skript ab (z. B. weil ghcr.io kurz nicht antwortet), einfach noch einmal starten: Es fragt nach,
richtet neu ein und lässt vorhandene Daten stehen. Erst nach einer vollständigen Einrichtung verweigert es einen
zweiten Lauf (Datei `/opt/satzball/.eingerichtet`).

## Einmalig einrichten (von Hand)

Was das Skript macht, Schritt für Schritt. Vorher Docker mit Compose und git installieren:

```bash
curl -fsSL https://get.docker.com | sudo sh
```

```bash
sudo apt install -y git
```

**1. Dateien holen**

```bash
sudo git clone https://github.com/Kootaro05/Satzball.git /opt/satzball && cd /opt/satzball
```

**2. Welche Apps laufen sollen** – nur Satzball, oder Satzball und Becherkönig:

```bash
echo "COMPOSE_PROFILES=satzball,becherkoenig" | sudo tee .env
```

**3. Umgebungsvariablen** – eine Datei pro App, aus derselben Vorlage:

```bash
sudo cp docs/satzball.env.example satzball.env && sudo chmod 600 satzball.env
```

```bash
sudo nano satzball.env
```

Werte eintragen. Stolperfallen:

- **`$`, `#` und Anführungszeichen:** Compose liest `$` als Variable und ` #` als Kommentar. Enthält ein Wert
  (z. B. ein Passwort) solche Zeichen, ihn in einfache Anführungszeichen setzen: `EMAIL_HOST_PASSWORD='ab$c #1'`.
- **Absender** in der Form `DEFAULT_FROM_EMAIL=Name <adresse@domain>`. Als Adresse das Postfach von
  `EMAIL_HOST_USER` nehmen, fremde Absender lehnen die meisten Anbieter ab.
- **Verantwortlicher** für die Datenschutzerklärung: `SATZBALL_VERANTWORTLICHER=Name | Straße | PLZ Ort | E-Mail: …`
  (jedes `|` wird ein Zeilenumbruch).

Für Becherkönig dasselbe mit `becherkoenig.env`, dabei:

- eigene Domain in `DJANGO_ALLOWED_HOSTS` und `DJANGO_CSRF_TRUSTED_ORIGINS`
- **AGPL:** `SATZBALL_QUELLCODE_URL=https://github.com/DHSN-Timberborn/Becherkoenig` – der Link „Quellcode“
  muss auf den Fork zeigen
- `DEFAULT_FROM_EMAIL=Becherkönig <adresse@domain>`

**4. Caddy** – Domains eintragen, nicht benötigte Blöcke löschen:

```bash
sudo cp docs/Caddyfile.example Caddyfile && sudo nano Caddyfile
```

**5. Starten** – lädt die Images und holt die Zertifikate (dauert beim ersten Mal etwas):

```bash
sudo docker compose up -d
```

Prüfen, erwartet `HTTP/2 200`:

```bash
curl -sI https://volleyball.example.de/ | head -1
```

**6. Orga-Zugang anlegen** (Benutzername und Passwort vergibst du selbst), je App einmal:

```bash
sudo docker exec -it satzball python manage.py createsuperuser
```

```bash
sudo docker exec -it becherkoenig python manage.py createsuperuser
```

Danach `https://volleyball.example.de/orga/` aufrufen und anmelden. Weitere Leute lädst du dort unter
**Benutzer & Rollen** ein: erst eine Rolle anlegen (was darf sie?), dann per E-Mail oder Link einladen – die Person
legt Name, E-Mail, Telefon (optional) und Passwort selbst fest. Der Link gilt 7 Tage und nur einmal.

**7. Tägliche Sicherung** per Cronjob (`sudo crontab -e`), Zeilen für nicht genutzte Apps weglassen:

```cron
30 3 * * * docker exec satzball python manage.py sicherung >/dev/null
40 3 * * * docker exec becherkoenig python manage.py sicherung >/dev/null
```

### Ohne Domain (nur über die IP)

Zum Ausprobieren oder im Uni-Netz ohne Domain: In `Caddyfile` statt der Domain-Blöcke die Blöcke `:80`
(Satzball) und `:8080` (Becherkönig) aus der Vorlage nehmen. In den `.env`-Dateien
`DJANGO_ALLOWED_HOSTS=<IP>`, `DJANGO_HTTPS=0` und die Zeile `DJANGO_CSRF_TRUSTED_ORIGINS` weglassen.
Erreichbar dann unter `http://<IP>/` bzw. `http://<IP>:8080/`. Ohne HTTPS gehen Passwörter unverschlüsselt
durchs Netz – für echte Turniere eine Domain nehmen.

`DJANGO_HTTPS=1` (mit Domain) ist wichtig: Daran vertraut Django dem Header `X-Forwarded-Proto` von Caddy und
schickt Cookies nur über HTTPS. Die App-Container haben keinen eigenen Port nach außen, nur Caddy.

## Update einspielen

Vorher auf GitHub prüfen, dass der Testlauf („Tests“ unter *Actions*) für `main` grün ist – erst dann gibt es
das neue Image. Für Becherkönig vorher im Fork „Sync fork“ und dort auf den grünen Lauf warten.

```bash
cd /opt/satzball && sudo git pull
```

```bash
sudo docker exec satzball python manage.py sicherung
```

```bash
sudo docker compose pull && sudo docker compose up -d
```

`git pull` holt nur `compose.yaml` und die Vorlagen; eure `.env`-Dateien und das `Caddyfile` bleiben unberührt.
Die Container führen beim Start automatisch `migrate` aus. Nach jeder Änderung an einer `.env`-Datei reicht
`sudo docker compose up -d`, nach einer Änderung am `Caddyfile` `sudo docker compose restart caddy`.

## Mailversand prüfen

```bash
sudo docker exec satzball python manage.py sendtestemail deine-adresse@example.de
```

Kommt die Mail an, funktioniert SMTP. Danach einmal ein Testteam über die Seite anmelden: Die Mail mit
dem Bearbeitungslink muss ankommen. Landen Mails im Spam, fehlen meist SPF/DKIM-Einträge der
Absender-Domain (Hilfe des Mail-Anbieters).

Typischer Fehler: `SMTPSenderRefused … MAIL command parameter unrecognized` → `DEFAULT_FROM_EMAIL` hat
nicht die Form `Name <adresse@domain>` oder enthält Anführungszeichen.

## Sicherung

```bash
sudo docker exec satzball python manage.py sicherung
```

```bash
sudo docker cp satzball:/app/data/sicherungen ./sicherungen
```

Der erste Befehl legt `/app/data/sicherungen/db-….sqlite3` an, der zweite kopiert die Sicherungen vom
Container auf den Server. Es bleiben die 14 neuesten Sicherungen (`--behalten N`, `--behalten 0` behält alle).
Für Becherkönig überall `becherkoenig` statt `satzball`, beim Image `ghcr.io/dhsn-timberborn/becherkoenig`.

**Wiederherstellen** – mit dem App-Image kopieren, damit die Datei dem App-Benutzer gehört
(als root hineinkopiert könnte die App sie nicht mehr schreiben):

```bash
sudo docker exec satzball ls /app/data/sicherungen
```

```bash
sudo docker compose stop satzball
```

```bash
sudo docker run --rm -v satzball-data:/app/data ghcr.io/kootaro05/satzball cp /app/data/sicherungen/db-2026-11-14-033000.sqlite3 /app/data/db.sqlite3
```

```bash
sudo docker compose start satzball
```

Eine heruntergeladene Sicherung vorher zurück ins Volume legen:
`sudo docker cp db-….sqlite3 satzball:/app/data/sicherungen/` (geht auch bei gestopptem Container).

## Probelauf

```bash
sudo docker exec satzball python manage.py testturnier --teams 10 --spielplan
```

Legt ein Turnier „Probelauf …“ für heute an: öffentlich sichtbar, 10 bezahlte Teams, 2 noch offene,
Spielplan veröffentlicht. Für „Gruppen + K.-o.“ braucht es mindestens 6 Teams.
Mails gehen an `@example.invalid` und kommen nicht an. Das Testturnier ist bis zum Löschen das
„aktuelle“ Turnier auf der Startseite – danach im Admin löschen.

## Neues Turnier

Im Admin anlegen und **„öffentlich sichtbar“** anhaken – sonst sehen Besucher es nicht
(Entwürfe bleiben so unsichtbar).

## Nach dem Turnier (Datenschutz)

Im Admin unter Turniere das Turnier auswählen → Aktion „Teamdaten löschen (Datenschutz)“.
Löscht Spieler, Kapitänsdaten, Notizen und das Admin-Änderungsprotokoll zu diesen Teams und macht die
Bearbeitungslinks ungültig; Teamnamen und Ergebnisse bleiben. Geht erst nach dem Turniertag und fragt
vorher nach.

Gut zu wissen:

- Die gelöschten Daten stecken noch in den **Sicherungen**, bis diese rotiert sind (bei täglicher
  Sicherung und `--behalten 14` also höchstens 14 Tage).
- Ohne `EMAIL_HOST` stehen die Mails samt **Bearbeitungslink** im Container-Log (`docker logs`).
  Für den echten Betrieb SMTP eintragen.

## Logs

```bash
sudo docker logs -f satzball
```

```bash
sudo docker logs -f caddy
```

Die App-Logs enthalten keine Zugriffe (Gunicorn schreibt kein Access-Log), sondern nur Start-Meldungen und
Fehler, z. B. „Mail für Team 12 konnte nicht verschickt werden“. Caddy schreibt in der Vorlage ebenfalls kein
Access-Log; im Caddy-Log stehen Meldungen zu Start und Zertifikaten und bei Fehlern (z. B. App nicht erreichbar)
der betroffene Aufruf samt IP-Adresse. So beschreibt es auch die Datenschutzerklärung – wer im `Caddyfile` ein
Access-Log (`log`) einschaltet, muss dort Speicherdauer und Zweck nachtragen. `compose.yaml` begrenzt jedes Container-Log auf 30 MB, ältere Einträge löscht Docker selbst.
