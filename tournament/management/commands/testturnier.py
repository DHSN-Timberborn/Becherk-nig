"""Testturnier für den Probelauf anlegen: python manage.py testturnier [--teams 10] [--spielplan] [--bierpong]"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tournament import spielplan
from tournament.models import Spieler, Team, Turnier

TEAMNAMEN = [
    "Bit Blockers", "Null Pointer Smash", "Satzweise Genial", "Pritsch Perfect", "Netzwerk",
    "Block Chain", "Lob & Order", "Ace of Bases", "Baggerfahrer", "Mittelblock Mafia",
    "Smash Bros", "Aufschlag Ahoi", "Die Netzroller", "Libero Liebe", "Pritschmeister", "Return 0",
]
# Das erste Testteam ist immer das Team des Satzball-Autors – verewigt im Probelauf.
TIMBERBORN = {
    "name": "Timberborn-Volleys",
    "kapitaen": "Maxim Stremel (Coach)",
    "spieler": [("Maxim", "Stremel"), ("Leon", "P."), ("Martin", "K."),
                ("Max", "K."), ("Leon", "S."), ("Oliver", "M.")],
}
VORNAMEN = ["Lena", "Max", "Kim", "Jonas", "Mia", "Paul", "Emma", "Noah", "Lea", "Finn", "Sara", "Tom"]
# Für --bierpong (gleich viele wie TEAMNAMEN, damit --teams überall dieselbe Grenze hat)
BIERPONG_TEAMNAMEN = [
    "Becher Bros", "Ping Pong Prost", "Die Treffsicheren", "Hopfenhelden", "Cup Cakes",
    "Schaumschläger", "Die Abräumer", "Becherjäger", "Zielwasser", "Pong Dynastie",
    "Last Cup Standing", "Wurfmaschinen", "Die Nachfüller", "Ball im Glas", "Bierbarone", "Rebound Rangers",
]
NACHNAMEN = ["Hoffmann", "Meier", "Nguyen", "Schulz", "Wolf", "Becker", "Krüger", "Yilmaz", "Lange", "Weber"]


class Command(BaseCommand):
    help = "Legt ein Testturnier mit bestätigten und bezahlten Teams an (für den Probelauf)."

    def add_arguments(self, parser):
        parser.add_argument("--teams", type=int, default=10, help="Bezahlte Teams (Standard: 10)")
        parser.add_argument("--modus", choices=Turnier.Modus.values, default=Turnier.Modus.GRUPPEN_KO)
        parser.add_argument("--zaehlmodus", choices=Turnier.Zaehlmodus.values, default=Turnier.Zaehlmodus.SAETZE)
        parser.add_argument("--spielplan", action="store_true", dest="mit_spielplan",
                            help="Spielplan erzeugen und veröffentlichen")
        parser.add_argument("--bierpong", action="store_true",
                            help="Bierpong-Werte: Becher-Modus, Tische, ohne Schiri, kostenlos, ab 16, 4 Spieler")

    @transaction.atomic
    def handle(self, *args, teams, modus, zaehlmodus, mit_spielplan, bierpong, **options):
        namen = [TIMBERBORN["name"]] + (BIERPONG_TEAMNAMEN if bierpong else TEAMNAMEN)
        if not 2 <= teams <= len(namen) - 2:
            raise CommandError(f"--teams muss zwischen 2 und {len(namen) - 2} liegen.")
        jetzt = timezone.localtime()
        beginn = (jetzt + timedelta(minutes=30 - jetzt.minute % 30)).time().replace(second=0, microsecond=0)
        werte = dict(
            startgebuehr_eur=20, zaehlmodus=zaehlmodus, ort="Campus-Halle",
            zahlungsinfo="Testturnier – bitte nichts überweisen.",
        )
        offen = 2  # zwei unbezahlte Teams zum Testen des Zahlungs-Trackings
        if bierpong:
            werte = dict(
                startgebuehr_eur=0, zaehlmodus=Turnier.Zaehlmodus.BECHER, ort="Mensa",
                feldart=Turnier.Feldart.TISCH, mit_schiri=False, mindestalter=16,
                pflicht_spieler=1, min_spieler=4, max_spieler=None,
            )
            offen = 0  # kostenlos: jeder Startplatz ist sofort bestätigt
        turnier = Turnier.objects.create(
            name=f"Probelauf {jetzt:%d.%m.%Y %H:%M}", oeffentlich=True, datum=jetzt.date(), beginn=beginn,
            meldeschluss=jetzt + timedelta(days=1), max_teams=teams + 2, anmeldung_offen=True, modus=modus, **werte,
        )
        zufall = random.Random()
        # Teams mit Startplatz: die ersten `teams` bezahlt, `offen` weitere unbezahlt
        for i, name in enumerate(namen[:teams + offen]):
            team = Team.objects.create(
                turnier=turnier, name=name,
                kapitaen_name=TIMBERBORN["kapitaen"] if i == 0 else f"Kapitän {i + 1}",
                kapitaen_email=f"team{i + 1}@example.invalid", bezahlt=i < teams,
                zahlungsart=Team.Zahlungsart.BAR if i < teams else "",
            )
            spieler = TIMBERBORN["spieler"] if i == 0 else [
                (zufall.choice(VORNAMEN), zufall.choice(NACHNAMEN)) for _ in range(4 if bierpong else 6)
            ]
            for vorname, nachname in spieler:
                Spieler.objects.create(team=team, vorname=vorname, nachname=nachname)

        if bierpong:
            self.stdout.write(f"Bierpong-Turnier „{turnier}“ (id {turnier.pk}) mit {teams} Teams angelegt.")
        else:
            self.stdout.write(f"Turnier „{turnier}“ (id {turnier.pk}) mit {teams} bezahlten und 2 offenen Teams angelegt.")
        if mit_spielplan:
            try:
                spielplan.erzeugen(turnier)
            except spielplan.SpielplanFehler as fehler:
                # CommandError rollt die Transaktion zurück – es bleibt kein halbes Testturnier stehen.
                raise CommandError(f"Spielplan nicht möglich: {fehler} Mehr Teams angeben (--teams).") from fehler
            turnier.spielplan_veroeffentlicht = True
            turnier.save(update_fields=["spielplan_veroeffentlicht"])
            self.stdout.write(f"Spielplan erzeugt und veröffentlicht: {turnier.spiele.count()} Spiele ab {beginn:%H:%M}.")
        self.stdout.write(self.style.SUCCESS("Fertig. Nach dem Probelauf das Turnier im Admin löschen."))
