"""Tabellenberechnung. Die Tabelle wird nie gespeichert, sondern aus beendeten Gruppenspielen berechnet.

Satz-Modus:   Siege, Satzdifferenz, Ballpunktdifferenz, direkter Vergleich
Punkte-Modus: Siege, Punktdifferenz, erzielte Punkte, direkter Vergleich
Becher-Modus: Siege, Becher-Differenz, getroffene Becher, direkter Vergleich
              (punkte_a/b = übrige Becher; Becher-Differenz = eigene minus gegnerische übrige Becher)
"""

from dataclasses import dataclass
from itertools import groupby

from .models import Spiel, Turnier


@dataclass
class Zeile:
    team: object
    sp: int = 0
    s: int = 0
    n: int = 0
    saetze_plus: int = 0
    saetze_minus: int = 0
    punkte_plus: int = 0
    punkte_minus: int = 0
    platz: int = 0
    # Teams, mit denen dieses Team auch nach dem direkten Vergleich gleichsteht (sonst leer).
    # Die Reihenfolge innerhalb so einer Gruppe ist nur alphabetisch – sportlich ist sie offen.
    gleichstand: tuple = ()
    becher: int = 0  # Becher pro Team (nur Becher-Modus)

    @property
    def pkt(self):
        """Becher-Modus: Sieg = 2 Punkte (Anzeige; gewertet wird nach Siegen)."""
        return 2 * self.s

    @property
    def getroffen(self):
        """Becher-Modus: beim Gegner getroffene Becher."""
        return self.sp * self.becher - self.punkte_minus

    @property
    def verloren(self):
        """Becher-Modus: eigene Becher, die der Gegner getroffen hat."""
        return self.sp * self.becher - self.punkte_plus

    @property
    def sd(self):
        return self.saetze_plus - self.saetze_minus

    @property
    def pd(self):
        return self.punkte_plus - self.punkte_minus


def _eintragen(zeilen, spiel, modus):
    a, b = zeilen[spiel.team_a], zeilen[spiel.team_b]
    pa, pb = spiel.punkte_a or 0, spiel.punkte_b or 0
    if modus == Turnier.Zaehlmodus.SAETZE:
        sa, sb = spiel.saetze_a or 0, spiel.saetze_b or 0
        a.saetze_plus += sa; a.saetze_minus += sb
        b.saetze_plus += sb; b.saetze_minus += sa
        a_gewinnt = sa > sb
    else:
        a_gewinnt = pa > pb
    a.punkte_plus += pa; a.punkte_minus += pb
    b.punkte_plus += pb; b.punkte_minus += pa
    a.sp += 1; b.sp += 1
    sieger, verlierer = (a, b) if a_gewinnt else (b, a)
    sieger.s += 1
    verlierer.n += 1


def _schluessel(zeile, modus):
    if modus == Turnier.Zaehlmodus.SAETZE:
        return (zeile.s, zeile.sd, zeile.pd)
    if modus == Turnier.Zaehlmodus.BECHER:
        return (zeile.s, zeile.pd, zeile.getroffen)
    return (zeile.s, zeile.pd, zeile.punkte_plus)


def _direkter_vergleich(zeilen, spiele, modus):
    """Gleichstand auflösen: Wertung nur aus den Spielen der punktgleichen Teams untereinander."""
    teams = {z.team for z in zeilen}
    mini = {t: Zeile(t, becher=zeilen[0].becher) for t in teams}
    for spiel in spiele:
        if spiel.team_a in teams and spiel.team_b in teams:
            _eintragen(mini, spiel, modus)
    sortiert = sorted(zeilen, key=lambda z: (*(-k for k in _schluessel(mini[z.team], modus)), str(z.team)))
    for _, gleich in groupby(sortiert, key=lambda z: _schluessel(mini[z.team], modus)):
        gleich = list(gleich)
        if len(gleich) > 1:
            for zeile in gleich:
                zeile.gleichstand = tuple(z.team for z in gleich)
    return sortiert


def berechnen(teams, spiele, zaehlmodus, becher=0):
    """Tabelle für `teams` aus `spiele`. Gezählt werden nur beendete Gruppenspiele zwischen diesen Teams.
    `becher`: Becher pro Team, nur im Becher-Modus (für die getroffenen Becher)."""
    zeilen = {t: Zeile(t, becher=becher) for t in teams}
    gewertet = [
        s for s in spiele
        if s.status == Spiel.Status.BEENDET and s.phase == Spiel.Phase.GRUPPE
        and s.team_a in zeilen and s.team_b in zeilen
    ]
    for spiel in gewertet:
        _eintragen(zeilen, spiel, zaehlmodus)

    vorsortiert = sorted(zeilen.values(), key=lambda z: (*(-k for k in _schluessel(z, zaehlmodus)), str(z.team)))
    tabelle = []
    for _, gleich in groupby(vorsortiert, key=lambda z: _schluessel(z, zaehlmodus)):
        gleich = list(gleich)
        tabelle += _direkter_vergleich(gleich, gewertet, zaehlmodus) if len(gleich) > 1 else gleich
    for platz, zeile in enumerate(tabelle, start=1):
        zeile.platz = platz
    return tabelle


def gruppentabellen(turnier):
    """[(gruppe, tabelle)] für alle Gruppen eines Turniers."""
    spiele = list(turnier.spiele.select_related("team_a", "team_b"))
    return [
        (gruppe, berechnen(list(gruppe.teams.all()), [s for s in spiele if s.gruppe_id == gruppe.pk],
                           turnier.zaehlmodus, turnier.becher))
        for gruppe in turnier.gruppen.order_by("name")
    ]


def endstand(turnier):
    """Plätze 1–3 als [(platz, team)], sobald sie feststehen, sonst [].

    Gruppen + K.-o.: Finale (1. und 2.) und Spiel um Platz 3, jeweils sobald beendet.
    Jeder gegen jeden: die Tabelle, sobald alle Spiele beendet sind. Echter Gleichstand teilt sich den Platz.
    """
    spiele = list(turnier.spiele.select_related("team_a", "team_b", "turnier"))
    if turnier.modus == Turnier.Modus.GRUPPEN_KO:
        finale = next((s for s in spiele if s.phase == Spiel.Phase.FINALE), None)
        if not finale or not finale.sieger:
            return []
        zweiter = finale.team_b if finale.sieger == finale.team_a else finale.team_a
        plaetze = [(1, finale.sieger), (2, zweiter)]
        platz_3 = next((s for s in spiele if s.phase == Spiel.Phase.PLATZ_3), None)
        if platz_3 and platz_3.sieger:
            plaetze.append((3, platz_3.sieger))
        return [(platz, team) for platz, team in plaetze if team]  # Team nach dem Spiel gelöscht

    if not spiele or any(s.status != Spiel.Status.BEENDET for s in spiele):
        return []
    plaetze = []
    for _, tabelle in gruppentabellen(turnier):
        platz_von = {z.team: z.platz for z in tabelle}
        for zeile in tabelle:
            platz = min(platz_von[t] for t in zeile.gleichstand or (zeile.team,))
            if platz <= 3:
                plaetze.append((platz, zeile.team))
    return plaetze
