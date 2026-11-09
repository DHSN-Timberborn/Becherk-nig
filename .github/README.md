# 🍺 Becherkönig

**Turnierplanung für Bierpong-Turniere – Anmeldung, Spielplan, Becher-Tabelle und Beamer-Ansicht.**

Becherkönig ist der Bierpong-Ableger von [Satzball](https://github.com/Kootaro05/Satzball), der Turnier-App für
Volleyball an Hochschulen. Die ganze Technik kommt aus Satzball, Becherkönig bringt nur sein eigenes Aussehen mit.

---

## ✨ Was Becherkönig kann

| | |
|---|---|
| 📝 **Anmeldung ohne Konto** | Team mit beliebig vielen Mitspielern anmelden (4 empfohlen), Bearbeitungslink per Mail, Altersbestätigung ab 16 |
| 🍻 **Becher-Wertung** | Eingetragen werden die übrigen Becher; Sieg = 2 Punkte, dann Becher-Differenz und getroffene Becher |
| 🗓️ **Spielplan per Knopfdruck** | Jeder gegen jeden oder Gruppen + K.-o., auf mehrere Tische verteilt, per Drag & Drop anpassbar |
| 📺 **Beamer-Ansicht** | Tabelle, laufende und nächste Spiele, Siegerbanner – aktualisiert sich selbst |
| 💶 **Startgebühr optional** | Kostenlose Turniere sind sofort bestätigt, mit Gebühr gibt es Zahlungs-Tracking |
| 🖨️ **Druckansicht** | Spielplan zum Aushängen |

Alle Einstellungen gelten pro Turnier: Zählmodus „Becher-Modus“, Bezeichnung „Tisch“, Schiris aus,
Pflicht 1 Spieler / empfohlen 4 / ohne Obergrenze, Mindestalter 16.

## 🔁 Verhältnis zu Satzball

Becherkönig ist ein Fork von Satzball. Er unterscheidet sich nur in diesen Dateien:

| Datei | Inhalt |
|---|---|
| `config/marke.py` | Name „Becherkönig“ |
| `static/css/marke.css` | Rot, Oswald, eckige Karten |
| `static/fonts/oswald-*.woff2` | Schrift Oswald (lokal, [SIL Open Font License](../static/fonts/OFL-Oswald.txt)) |
| `static/img/logo.svg` | Becher mit Ball |
| `templates/marke/` | Startseite und Fußzeile |
| `.github/README.md` | diese Datei |

**Neue Funktionen und Fehlerkorrekturen gehören nach Satzball** und kommen per „Sync fork“ hierher.
Hier im Fork wird nur das Aussehen geändert – so gibt es beim Sync keine Konflikte.

## 🚀 Lokal starten und betreiben

Genau wie Satzball, siehe [README von Satzball](../README.md) und [`docs/betrieb.md`](../docs/betrieb.md).
Auf dem Server `SATZBALL_QUELLCODE_URL` auf dieses Repository setzen (Link „Quellcode“ in der Fußzeile, AGPL).

## 📜 Lizenz

Becherkönig basiert auf Satzball, Copyright © 2026 [TetraMedia](https://tetramedia.de).
Design und Bilder der Bierpong-Seite: Leon Scholle (Timberborn-Volleys), beigesteuert unter derselben Lizenz.

Open Source unter der [GNU Affero General Public License v3.0](../LICENSE). Wer eine veränderte Version als
Webseite betreibt, muss den Nutzern den geänderten Quellcode zugänglich machen.

Bitte trinkt verantwortungsvoll – Spaß geht vor Promille. 🍻
