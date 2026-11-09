# Becherkönig – Betrieb neben Satzball

Becherkönig läuft genau wie Satzball (siehe [`betrieb.md`](betrieb.md)) – nur mit eigenen Namen, damit beide
**auf demselben VPS** nebeneinander laufen können, ohne sich zu stören:

| | Satzball | Becherkönig |
|---|---|---|
| Code | `/opt/satzball` | `/opt/becherkoenig` |
| Image und Container | `satzball` | `becherkoenig` |
| Port (nur lokal) | `127.0.0.1:8000` | `127.0.0.1:8001` |
| Daten-Volume | `satzball-data` | `becherkoenig-data` |
| Umgebungsvariablen | `/etc/satzball.env` | `/etc/becherkoenig.env` |
| nginx | `sites-available/satzball` | `sites-available/becherkoenig` |
| Domain (Beispiel) | `volleyball.example.de` | `bierpong.example.de` |

Die Datenbanken sind getrennt: Teams, Turniere und Orga-Zugänge von Becherkönig sehen in Satzball niemand
und umgekehrt. Für Voraussetzungen (Pakete, DNS) und Hintergründe gilt `betrieb.md`; hier stehen die
Befehle fertig für Becherkönig. Die Domain `bierpong.example.de` überall durch eure ersetzen.

## Einmalig einrichten

**1. DNS:** Typ-A-Eintrag für die neue Domain auf die Server-IP. Prüfen:

```bash
getent hosts bierpong.example.de
```

**2. Code holen und Image bauen**

```bash
sudo git clone https://github.com/DHSN-Timberborn/Becherkoenig.git /opt/becherkoenig
```

```bash
cd /opt/becherkoenig && sudo docker build -t becherkoenig .
```

**3. Umgebungsvariablen anlegen** (Vorlage wie bei Satzball)

```bash
sudo cp docs/satzball.env.example /etc/becherkoenig.env && sudo chmod 600 /etc/becherkoenig.env
```

```bash
sudo nano /etc/becherkoenig.env
```

Wie bei Satzball ausfüllen (ohne Anführungszeichen), dabei unbedingt:

- `DJANGO_ALLOWED_HOSTS=bierpong.example.de` und `DJANGO_CSRF_TRUSTED_ORIGINS=https://bierpong.example.de`
- **AGPL:** `SATZBALL_QUELLCODE_URL=https://github.com/DHSN-Timberborn/Becherkoenig` (Zeile einkommentieren) –
  der Link „Quellcode“ in der Fußzeile muss auf den Fork zeigen, nicht auf Satzball.
- `DEFAULT_FROM_EMAIL=Becherkönig <adresse@domain>` – Adresse wieder das Postfach von `EMAIL_HOST_USER`.
- `SATZBALL_VERANTWORTLICHER=…` – wer für diese Seite verantwortlich ist (kann eine andere Person sein als bei Satzball).

**4. Container starten**

```bash
sudo docker run -d --name becherkoenig --restart unless-stopped -p 127.0.0.1:8001:8000 -v becherkoenig-data:/app/data --env-file /etc/becherkoenig.env --log-opt max-size=10m --log-opt max-file=3 becherkoenig
```

Im Container lauscht die App weiter auf 8000, nach außen (nur lokal) auf 8001. Prüfen, erwartet `HTTP/1.1 200 OK`:

```bash
curl -sI -H "Host: bierpong.example.de" http://127.0.0.1:8001/ | head -1
```

**5. Orga-Zugang anlegen** – eigener Zugang, unabhängig von Satzball

```bash
sudo docker exec -it becherkoenig python manage.py createsuperuser
```

## nginx und HTTPS

```bash
sudo nano /etc/nginx/sites-available/becherkoenig
```

```nginx
server {
    listen 80;
    server_name bierpong.example.de;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/becherkoenig /etc/nginx/sites-enabled/becherkoenig
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

```bash
sudo certbot --nginx --redirect -d bierpong.example.de
```

Beide Container nur lokal erreichbar? Erwartet `127.0.0.1:8000` und `127.0.0.1:8001`, nie `0.0.0.0`:

```bash
sudo ss -tlnp | grep -E ':(8000|8001) '
```

## Update einspielen

Neue Funktionen kommen aus Satzball. Deshalb zuerst auf GitHub im Fork **„Sync fork“ → „Update branch“**
klicken und warten, bis der Testlauf unter *Actions* für `main` grün ist. Dann:

```bash
cd /opt/becherkoenig && sudo git pull
```

```bash
sudo docker build -t becherkoenig .
```

```bash
sudo docker exec becherkoenig python manage.py sicherung
```

```bash
sudo docker stop becherkoenig && sudo docker rm becherkoenig
```

```bash
sudo docker run -d --name becherkoenig --restart unless-stopped -p 127.0.0.1:8001:8000 -v becherkoenig-data:/app/data --env-file /etc/becherkoenig.env --log-opt max-size=10m --log-opt max-file=3 becherkoenig
```

## Sicherung

Täglich per Cronjob (`sudo crontab -e`), zehn Minuten nach Satzball:

```cron
40 3 * * * docker exec becherkoenig python manage.py sicherung >/dev/null
```

Wiederherstellen wie in `betrieb.md`, nur mit `becherkoenig` und `becherkoenig-data` statt `satzball`.

## Ein Bierpong-Turnier anlegen

Im Admin unter Turniere anlegen und diese Werte setzen:

| Feld | Wert |
|---|---|
| Zählmodus | Becher-Modus, Becher pro Team z. B. 10 |
| Bezeichnung | Tisch (Anzahl Felder = Anzahl Tische) |
| Schiris einteilen | aus |
| Pflicht / empfohlen / max. Spieler | 1 / 4 / leer |
| Mindestalter | 16 |
| Startgebühr | 0 € für kostenlos, sonst Betrag (dann mit Zahlungs-Tracking) |
| Öffentlich sichtbar | an, sobald es losgehen soll |

Probelauf wie bei Satzball, nur mit Becher-Modus:

```bash
sudo docker exec becherkoenig python manage.py testturnier --teams 8 --zaehlmodus becher --spielplan
```

Nach dem Turnier: Aktion „Teamdaten löschen (Datenschutz)“ wie bei Satzball.

## Logs

```bash
sudo docker logs -f becherkoenig
```
