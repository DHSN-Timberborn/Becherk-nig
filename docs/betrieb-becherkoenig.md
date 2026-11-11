# Becherkönig – Betrieb neben Satzball

Becherkönig läuft auf demselben Server wie Satzball, im selben `compose.yaml` und hinter demselben Caddy.
Die Anleitung steht in [`betrieb.md`](betrieb.md) – hier nur, was für Becherkönig dazukommt.
Die Datenbanken sind getrennt: Teams, Turniere und Orga-Zugänge von Becherkönig sieht Satzball nicht und umgekehrt.

| | Satzball | Becherkönig |
|---|---|---|
| Image | `ghcr.io/kootaro05/satzball` | `ghcr.io/dhsn-timberborn/becherkoenig` |
| Container | `satzball` | `becherkoenig` |
| Daten-Volume | `satzball-data` | `becherkoenig-data` |
| Umgebungsvariablen | `/opt/satzball/satzball.env` | `/opt/satzball/becherkoenig.env` |
| Adresse mit Domain (Beispiel) | `https://volleyball.example.de/` | `https://bierpong.example.de/` |
| Adresse ohne Domain | `http://<IP>/` | `http://<IP>:8080/` |
| Orga | `…/admin/` | `…/admin/` (eigener Zugang) |

## Einschalten

In `/opt/satzball/.env` muss `becherkoenig` mit in den Profilen stehen:

```bash
echo "COMPOSE_PROFILES=satzball,becherkoenig" | sudo tee /opt/satzball/.env
```

In `becherkoenig.env` (Vorlage `docs/satzball.env.example`) unbedingt:

- eigene Domain in `DJANGO_ALLOWED_HOSTS` und `DJANGO_CSRF_TRUSTED_ORIGINS`
- **AGPL:** `SATZBALL_QUELLCODE_URL=https://github.com/DHSN-Timberborn/Becherkoenig` – der Link „Quellcode“ in der
  Fußzeile muss auf den Fork zeigen, nicht auf Satzball
- `DEFAULT_FROM_EMAIL=Becherkönig <adresse@domain>`
- `SATZBALL_VERANTWORTLICHER=…` – kann eine andere Person sein als bei Satzball

Im `Caddyfile` den Block `bierpong.example.de` (bzw. `:8080` ohne Domain) behalten, dann:

```bash
cd /opt/satzball && sudo docker compose up -d && sudo docker compose restart caddy
```

```bash
sudo docker exec -it becherkoenig python manage.py createsuperuser
```

Sicherung per Cronjob wie in `betrieb.md` (Zeile mit `becherkoenig`).

## Update

Neue Funktionen kommen aus Satzball. Zuerst auf GitHub im Fork **„Sync fork“ → „Update branch“** klicken und warten,
bis der Lauf unter *Actions* für `main` grün ist – erst dann gibt es das neue Becherkönig-Image. Danach auf dem Server
wie in `betrieb.md` unter „Update einspielen“.

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

Probelauf:

```bash
sudo docker exec becherkoenig python manage.py testturnier --teams 8 --zaehlmodus becher --spielplan
```

Das Testturnier startet mit den Satzball-Vorgaben („Feld“, Schiris an, 20 € Startgebühr). Damit es nach Bierpong
aussieht, danach im Admin beim Testturnier „Bezeichnung: Tisch“ wählen und „Schiris einteilen“ ausschalten –
beides gilt sofort auch für den schon erzeugten Spielplan.

Nach dem Turnier: Aktion „Teamdaten löschen (Datenschutz)“ wie bei Satzball.
