# CLAUDE.md – Satzball

WebApp für interne Volleyball-Turniere an Hochschulen (entstanden an der DHSN Leipzig).
Open Source unter AGPL-3.0: Im Code und in den Seiten keine DHSN-spezifischen Texte, damit andere
Hochschulen Satzball nutzen können. Fußzeile verlinkt den Quellcode (`SATZBALL_QUELLCODE_URL`).

**Verbindlich:** `docs/konzept.md` (Anforderungen, Datenmodell, Spielplan-Logik) und
`docs/design.html` (UI-Entwurf, 8 Screens). Vor größeren Änderungen dort nachlesen.
Bei Unklarheiten oder Widersprüchen nachfragen statt annehmen.

## Leitprinzip

Einfach, kein Overengineering. Eine Person baut und betreibt das nebenher.
Jede Funktion muss sich gegen "geht auch mit einem Zettel" behaupten.

## Stack (fest)

- Python + Django, SQLite
- Server-gerenderte Django-Templates (`templates/`), schlankes CSS, optional htmx
- Django Admin als Orga-Backend
- Kein SPA-Framework, keine separate API, keine Nutzerkonten für Spieler
- Kapitäne bearbeiten ihr Team über einen geheimen Link (`Team.edit_token`)
- Deployment: ein Docker-Container auf privatem VPS, Gunicorn + WhiteNoise

## Struktur

- `config/` – Django-Projekt (Settings, URLs)
- `tournament/` – die eine App: Models, Admin, Views, Spielplan-Logik, Tests
- `templates/` – Seiten (`base.html`, `tournament/`, `mail/`)
- `static/` – `css/satzball.css` (Layout), `css/marke.css` (Schriften, Farben Light + Dark), `js/spieler.js`,
  `fonts/` (Barlow, lokal statt Google Fonts – Datenschutz)
- **Marke** (für Ableger wie Becherkönig, Fork `DHSN-Timberborn/…`): `config/marke.py` (`NAME`, als
  `settings.MARKE` und `{{ marke }}` überall statt „Satzball“), `static/css/marke.css`, `static/img/logo.svg`,
  `templates/marke/startseite_oben.html`, `startseite_unten.html` und `fuss.html` (in Satzball leer). Ein Ableger ersetzt
  nur diese Dateien; alles andere kommt per „Sync fork“. Neue Farben/Schriften immer als Variable in `marke.css`.
- `data/` – SQLite-Datei (`db.sqlite3`) und generierter `secret_key`; im Container
  `/app/data`, dort liegt das Volume `satzball-data`. Nicht ins Git.

Umgebungsvariablen (alle optional): `DJANGO_DEBUG` (lokal Standard `1`, im Container `0`),
`DJANGO_SECRET_KEY` (sonst aus `data/secret_key`), `DJANGO_ALLOWED_HOSTS`,
`DJANGO_CSRF_TRUSTED_ORIGINS` (z. B. `https://volleyball.example.de`, nötig hinter HTTPS-Proxy),
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`
(ohne `EMAIL_HOST` werden Mails nur in die Konsole/das Log geschrieben).
`DJANGO_HTTPS=1` (nur auf dem Server hinter Caddy mit Domain: vertraut `X-Forwarded-Proto`, Cookies nur über HTTPS).
`SATZBALL_VERANTWORTLICHER` (Datenschutzerklärung, Zeilen mit `|` getrennt – Betreiberdaten nicht im Code).
Betrieb: `compose.yaml` (fertige Images von ghcr.io + Caddy für HTTPS, Profile `satzball`/`becherkoenig`),
Anleitung `docs/betrieb.md`, Vorlagen `docs/satzball.env.example` und `docs/Caddyfile.example`.
`install.sh` richtet einen frischen Server per Konsolen-Fragen ein (Test in der CI über `SATZBALL_EINGABE`);
in `.env`-Dateien schreibt es jeden Wert in Anführungszeichen, weil Compose `$` und ` #` sonst auswertet.

## Fachliche Regeln

- Turniermodus pro Turnier: `jeder_gegen_jeden` oder `gruppen_ko`
- Bezeichnung der Spielorte pro Turnier (`Turnier.feldart`: Feld, Tisch, Platz): Templates nutzen
  `turnier.feld_name` („Tisch 1“) und `turnier.felder_text` („3 Tische“), nie fest „Feld“.
- Zählmodus pro Turnier:
  - `saetze`: `gewinnsaetze` 1/2/3 = Best of 1/3/5, `punkte_pro_satz`, `punkte_entscheidungssatz`
  - `punkte`: keine Sätze und keine Zielpunktzahl (z. B. auf Zeit), mehr Punkte gewinnt, kein Unentschieden.
    „Ein Satz bis 25“ ist Satz-Modus mit Best of 1. Im Admin graut `admin_turnier.js` die Satz-Felder aus.
  - `becher` (z. B. Bierpong): `punkte_a/b` = übrige Becher (0 bis `Turnier.becher`), mehr gewinnt, kein Gleichstand
    (Verlängerung). Getroffene Becher = `becher` − übrige des Gegners. `admin_turnier.js` graut `becher` außerhalb
    des Becher-Modus aus. Kurzbezeichnung für Kopfzeilen: `Turnier.zaehlweise_kurz`.
- Spiel speichert `saetze_a/b` und `punkte_a/b` (Satz-Modus: Ballpunkt-Summe, optional).
  Keine Punkte je Satz (bewusst entschieden).
- K.-o.-Spiele dürfen ohne Teams angelegt werden; dann zeigen `platzhalter_a/b`
  z. B. "1. Gruppe B". Ein beendetes Spiel braucht beide Teams.
- Die Tabelle wird **nie gespeichert**, sondern aus beendeten Spielen berechnet.
- Tabellenwertung:
  - Satz-Modus: Siege, Satzdifferenz, Ballpunktdifferenz, direkter Vergleich
  - Punkte-Modus: Siege, Punktdifferenz, erzielte Punkte, direkter Vergleich
  - Becher-Modus: Siege (angezeigt als Pkt, Sieg = 2), Becher-Differenz (= `pd`), getroffene Becher
    (`Zeile.getroffen`), direkter Vergleich. Bester Gruppenzweiter analog pro Spiel (`ko._schnitt`).
- Paarungen per Kreismethode. Ungerade Teamzahl → "spielfrei" (bei einer Gruppe pfeift das spielfreie Team).
  2 Felder, kein Team doppelt im selben Slot.
- Nur bestätigte **und** bezahlte Teams kommen in den Spielplan (`Team.objects.im_spielplan()`).
- **Startgebühr pro Team oder pro Person** (`Turnier.gebuehr_pro_person`, Vorgabe pro Team): Was ein Team zahlt, steht in
  `Team.startgebuehr` (pro Person: Betrag × aktuell eingetragene Spieler, `Team.anzahl_spieler` nutzt `_anzahl_spieler`
  aus `.annotate()`), Text für Mails `Team.startgebuehr_text`, Einheit für Startseite/Anmeldung `Turnier.gebuehr_einheit`.
  Templates mit Team zeigen nie `turnier.startgebuehr_eur` als Betrag. `zahlungsuebersicht` und CSV rechnen pro Team.
- **PayPal** (`Turnier.paypal_link`, optional, nur `https://` zu paypal.me/paypal.com – geprüft in `Turnier.clean`):
  Kapitänsseite zeigt bei offener Zahlung (nicht auf der Warteliste) Knopf + aufklappbaren QR-Code mit `Team.paypal_url`
  (bei `paypal.me/<name>` mit Betrag des Teams, z. B. `/20EUR`). QR-Code als SVG auf dem Server (`segno`,
  `{% load qr %}{% qr_svg url %}`), kein fremder Dienst.
- **Ohne Startgebühr** (`Turnier.kostenlos`, Gebühr 0 – auch die Vorgabe): Ein Startplatz ist sofort bestätigt
  (`Team.save()`), `unbezahlte_teams()` ist leer, Zahlungsteile (Startseite, Anmeldung, Kapitänsseiten, Mails,
  Admin-Kacheln) sind ausgeblendet; Filter „Unbezahlt“ lässt sie aus, CSV zeigt „–“ statt „nein“. Ändert die Orga die Gebühr im Admin, wird der Status aller Teams mit
  Startplatz neu berechnet. Tests, die die Bezahl-Logik prüfen, brauchen deshalb eine Gebühr > 0.
- Team-Status: Anmeldung → `angemeldet` (Platz frei) oder `warteliste` (voll).
  **Bezahlt = bestätigt:** Setzt die Orga `bezahlt`, wird ein angemeldetes Team automatisch
  `bestaetigt` (in `Team.save()`); wird `bezahlt` zurückgenommen, wieder `angemeldet`.
  Warteliste und Absage ändert das nicht. Kapitän kann bis Meldeschluss abmelden (`abgesagt`).
  Warteliste in Anmelde-Reihenfolge (`Team.angemeldet_am`, dann pk; `Team.REIHENFOLGE`, `wartelisten_platz`).
  Neue Anmeldungen stellen sich hinten an, solange jemand wartet (`Turnier.neue_auf_warteliste`).
  Nachrücken: Orga per Knopf in der Kachel „Warteliste“ (nächstes Team) bzw. Admin-Aktion, oder automatisch,
  wenn `Turnier.warteliste_automatisch` gesetzt ist
  (`tournament/warteliste.py`: nach Abmeldung, Absage/Löschen im Admin, mehr Plätzen). Das nachgerückte
  Team bekommt immer eine Mail.
- Unbezahlt (Kachel im Admin): vor dem Meldeschluss Knopf „Erinnerung schicken“ (`Turnier.zahlungserinnerung_am`),
  danach Knopf „auf die Warteliste setzen“ – unbezahlte Teams ans **Ende** der Warteliste (`angemeldet_am` = jetzt,
  alter Zeitpunkt in der Notiz), Mail an sie, danach normales Nachrücken. Beides nur per Knopf, nie automatisch.
- Zahlungs-Tracking im Admin (Teamliste): Haken "bezahlt" und Zahlungsart direkt in der Liste,
  Kennzahlen aus `Turnier.zahlungsuebersicht()` (erwartet = Gebühr × Teams mit Startplatz),
  Filter "Unbezahlt (mit Startplatz)", Aktion "Von der Warteliste nachrücken".
  Aktion "Als CSV exportieren" (Abrechnung, folgt den Filtern): Semikolon + BOM für Excel; Zellen, die mit
  = + - @ beginnen, bekommen ein `'` davor (sonst führt Excel Teamnamen aus dem Formular als Formel aus).
- Sichtbarkeit: Besucher sehen nur Turniere mit `Turnier.oeffentlich` (Standard aus, die Orga schaltet frei).
  Öffentliche Seiten nutzen `Turnier.aktuelles(nur_oeffentliche=True)`, Orga/Admin sehen alle.
- Turnier-Wahl (öffentlich): `views.gewaehltes_turnier(request)` – `?turnier=<id>` (in der Session gemerkt),
  sonst das aktuelle öffentliche Turnier. Liste unter `/turniere/`; bei einem anderen als dem aktuellen Turnier zeigt
  `base.html` einen Hinweis (Block `banner`, auf Orga- und Kapitänsseiten leer).
- **Orga-Konten** (`tournament/konten.py`, `tournament/rollen.py`): Login unter `/orga/login/` (E-Mail oder Benutzername),
  danach Orga-Übersicht `/orga/`; `/admin/login/` leitet dorthin um. Orga-Seiten nutzen `konten.orga_required`.
  Rollen = Django-Gruppen mit Bausteinen per Checkbox (`rollen.BAUSTEINE`: turniere, teams, spielplan, benutzer;
  ansehen dürfen alle, `rollen.ANSEHEN`); geprüft mit `rollen.darf(user, baustein)`. Spielplan erzeugen/verschieben/
  veröffentlichen und Ergebnisse eintragen brauchen „spielplan“. Neue Konten nur per `Einladung` (7 Tage, einmal,
  per Mail oder Link): Person legt Name, E-Mail (= Benutzername, klein), optional Telefon (`OrgaProfil`) und Passwort
  fest, bekommt `is_staff` + die Rolle. Schritt-Formulare: `<form data-schritte>` + `static/js/schritte.js`
  (ohne JS alle Schritte sichtbar). Superuser ändern nur Superuser; das eigene Konto kann man nicht sperren.
- Admin-Optik: `templates/admin/base_site.html` lädt `marke.css` und `static/css/admin.css`; admin.css legt nur
  Djangos CSS-Variablen auf die Marken-Farben (`--ac`, `--ink` …) und setzt Rundungen – Ableger bekommen so ihre
  Farben auch im Admin. Hell/Dunkel folgt dem Gerät (Djangos Umschalter ausgeblendet). Die App-Überschrift im Admin
  ist `settings.MARKE` (`tournament/apps.py`). Turnier im Punkte-Modus: `static/js/admin_turnier.js` graut Satz-Felder aus
  (bewusst nicht `disabled`, sonst fehlen die Werte beim Speichern).
- Spielerzahl pro Turnier: Pflicht sind mindestens `pflicht_spieler` (Vorgabe `MIN_SPIELER` = 2, kleinster Wert 1),
  höchstens `max_spieler` (leer = keine Obergrenze). `min_spieler` ist nur eine **Empfehlung** (gelber Hinweis im
  Formular, keine Ablehnung) und liegt zwischen Pflicht- und Höchstzahl. Bierpong z. B.: Pflicht 1, empfohlen 4, ohne Obergrenze.
- Mindestalter pro Turnier (`Turnier.mindestalter`, leer = keins, z. B. 16 bei Bier): Pflicht-Haken „Alle Spieler im
  Team sind mindestens X Jahre alt“ bei der Anmeldung und beim Ändern der Spielerliste (`forms.AlterForm`,
  `templates/tournament/_alter.html`); Startseite zeigt „Teilnahme ab X Jahren“. Gespeichert wird nur die Einstellung.
- Spielernamen sind **öffentlich** (Teamliste). E-Mail und Zahlungsstatus sehen nur Orga und Kapitän.
- Spiel-Phase (`Spiel.phase`): Gruppenspiel, Viertelfinale, Halbfinale, Spiel um Platz 3, Finale.
  K.-o.-Spiele haben keine Gruppe.
- Spielplan (`tournament/spielplan.py`, Orga-Seite `/orga/spielplan/`):
  - Jeder gegen jeden = eine Gruppe "A". Gruppen + K.-o.: 2–4 Gruppen, Vorschlag max. 5 Teams pro Gruppe,
    Orga wählt; Teams werden zufällig gelost.
  - K.-o.: 2 Gruppen → Halbfinale 1. A–2. B, 1. B–2. A; 3 Gruppen → Gruppensieger + bester Zweiter
    ins Halbfinale; 4 Gruppen → Top 2 ins Viertelfinale. Danach Spiel um Platz 3 und Finale (ein Slot).
    K.-o.-Spiele haben Platzhalter; die Teams trägt die Orga im Admin ein.
  - Slots: Startzeit (`Turnier.beginn`) + Index × `slot_minuten`; Gruppen rundenweise verzahnt.
  - Schiri (`schiris_zuteilen`): bei mehreren Gruppen bevorzugt ein freies Team aus einer anderen Gruppe (neutral);
    aus der eigenen Gruppe nur, wenn es seltener gepfiffen hat oder sonst keins frei ist. Bei einer Gruppe das
    spielfreie Team der Runde. Bei Gleichstand pfeift, wer später seltener frei ist (gleichmäßige Verteilung).
    K.-o.-Spiele bekommen keinen automatischen Schiri. `Turnier.mit_schiri` aus (z. B. Bierpong): gar keine Schiris;
    Umschalten im Admin trägt sie bei allen offenen Spielen aus (`schiris_austragen`) bzw. teilt sie neu ein,
    beendete behalten ihren. Bei „aus“ lässt `schiris_neu` von Hand gesetzte Schiris (z. B. Finale) stehen.
    Nach jedem Verschieben werden die Schiris der offenen Spiele neu verteilt (`schiris_neu`).
  - Neu erzeugen nur, solange es keine Ergebnisse gibt; zieht die Veröffentlichung zurück.
- Team löschen (im Admin) → `spielplan.umplanen`: Beendete Spiele bleiben (zählen aber nicht mehr in
  der Tabelle), offene Spiele der betroffenen Gruppe werden ohne das Team neu gepaart, alle offenen
  Spiele rücken ab dem nächsten freien Slot lückenlos auf, K.-o. danach.
- Tabelle: `tournament/tabelle.py` (`berechnen`, `gruppentabellen`), zählt nur beendete Gruppenspiele.
  `Zeile.gleichstand` nennt die Teams, die auch der direkte Vergleich nicht trennt (nur bei Ringschluss ab 3 Teams).
- K.-o.-Runde füllt sich automatisch (`tournament/ko.py`, nach jedem gespeicherten Ergebnis in Orga-Seite
  und Admin): Platzhalter wie "1. Gruppe A", "Bester Gruppenzweiter" (Schnitt pro Spiel), "Sieger HF 1".
  Offene K.-o.-Spiele folgen Korrekturen, beendete bleiben. Manuell setzen = Platzhalter leeren.
  Echter Gleichstand um einen K.-o.-Platz wird nie alphabetisch vergeben: Platz bleibt leer,
  `ko.offene_entscheidungen` → Hinweis „Entscheidungssatz spielen“ (Meldung + Kasten auf der Orga-Spielplanseite).
- Endstand auf der Startseite (`tabelle.endstand`, nur bei veröffentlichtem Spielplan): Gruppen + K.-o. aus Finale
  und Spiel um Platz 3, sobald beendet; Jeder gegen jeden aus der Tabelle, sobald alle Spiele beendet sind
  (echter Gleichstand teilt sich den Platz).
- Öffentlich `/spielplan/` (Screen 05): Spiele nach Uhrzeit und Feld, Ergebnisse. Gruppentabellen auf
  eigener Seite `/tabelle/` (Abweichung vom Design, damit der Menüpunkt aktiv markiert wird).
  Untere Navigation mit Inline-SVG-Symbolen. "Läuft" = erster Slot mit offenen Spielen, sobald seine Startzeit am Spieltag erreicht ist
  (folgt dem echten Stand, nicht nur der Uhr). Nur sichtbar, wenn
  `Turnier.spielplan_veroeffentlicht`. Keine E-Mails oder Zahlungsdaten auf öffentlichen Seiten.
- Datenschutz nach dem Turnier: Admin-Aktion "Teamdaten löschen" (`Turnier.teamdaten_loeschen`), erst nach
  dem Turniertag, mit Bestätigung. Löscht Spieler, Kapitänsdaten, Notizen und das Admin-Protokoll
  dazu, macht Links ungültig;
  Teamnamen und Ergebnisse bleiben. Deshalb sind `kapitaen_name/-email` im Model optional
  (im Anmeldeformular Pflicht).
- Befehle: `testturnier [--teams N] [--spielplan] [--bierpong]` (Probelauf; `--bierpong`: Becher, Tische, ohne Schiri, Bierpong-Teamnamen,
  kostenlos, ab 16), `sicherung [--behalten N]`
  (SQLite-Backup nach `data/sicherungen/`).
- Beamer-Ansicht `/beamer/` (öffentlich wie die Tabelle, erst nach Veröffentlichung; Link „Beamer →“ auf der
  Orga-Spielplanseite): eigenständige Großbild-Seite mit Gruppentabellen, „Läuft“ und „Als Nächstes“
  (`views._slots`, auch vom Spielplan genutzt) und Siegerbanner aus `tabelle.endstand`. `static/js/beamer.js` holt
  alle 30 s den Stand und tauscht nur `#beamer` aus – ein Neuladen würde den Vollbildmodus beenden.
- Druckansicht zum Aushang: `/orga/spielplan/druck/` (eigenständige Seite, schwarz-weiß, A4; Link auf der
  Orga-Spielplanseite). Ziel: Plan mit bis zu 16 Zeit-Slots auf einer Seite.
- Ergebnis eintragen: `/orga/spiel/<id>/`, Satz-Modus Sätze (+ optional Ballpunkte gesamt),
  Punkte-Modus Punktzähler, Becher-Modus je Team Knöpfe 0 bis Becherzahl für die übrigen Becher (`_becher_wahl.html`, ohne JS).
- Abweichung vom Design: "Ergebnis eintragen" zeigt im Punkte-Modus Punktzähler
  (z. B. 25 : 21 mit +/- Buttons) statt Sätzen.

## Konventionen

- Fachbegriffe und Feldnamen auf Deutsch wie im Konzept (ohne Umlaute: `kapitaen`, `bestaetigt`).
- Validierung in `Model.clean()`, damit Admin und Formulare sie gemeinsam nutzen.
- Spielplan- und Tabellenlogik als reine Funktionen mit Unit-Tests.

## Abhängigkeiten und CI

- `requirements.txt` mit **exakten** Versionen. Updates kommen als Dependabot-PR (`.github/dependabot.yml`,
  monatlich gebündelt; Django bleibt auf LTS 5.2).
- `.github/workflows/tests.yml` läuft bei jedem PR und Push auf `main`: Docker-Image bauen, Tests im Image,
  Container starten und Seiten abrufen. Nur mergen, wenn der Lauf grün ist.
- Nach grünem Lauf auf `main` veröffentlicht derselbe Workflow das Image als `ghcr.io/<besitzer>/<repo>:latest`
  (und `:<commit>`); ein Fork baut automatisch sein eigenes. Das Paket muss auf GitHub einmal öffentlich gestellt werden.

## Befehle

```bash
python manage.py runserver
python manage.py makemigrations tournament
python manage.py test
docker build -t satzball .
docker run -p 8000:8000 -v satzball-data:/app/data satzball
```
