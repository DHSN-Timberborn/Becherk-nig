from datetime import time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tournament import ko, spielplan
from tournament.models import Spiel, Team, Turnier


class BeamerTests(TestCase):
    def setUp(self):
        # Spieltag heute ab 0:00 – so läuft der erste Slot schon
        self.t = Turnier.objects.create(
            name="Herbst-Cup", oeffentlich=True, datum=timezone.localdate(), beginn=time(0, 0), ort="Halle",
            meldeschluss=timezone.now() - timedelta(days=1), max_teams=8, startgebuehr_eur=0,
        )
        for i in range(4):
            Team.objects.create(turnier=self.t, name=f"Team {i}", kapitaen_name="K", kapitaen_email="k@example.de")
        spielplan.erzeugen(self.t)
        self.url = f"{reverse('beamer')}?turnier={self.t.pk}"

    def veroeffentlichen(self):
        self.t.spielplan_veroeffentlicht = True
        self.t.save()

    def test_erst_nach_veroeffentlichung(self):
        r = self.client.get(self.url)
        self.assertContains(r, "noch nicht veröffentlicht")
        self.assertNotContains(r, "Läuft")

    def test_tabelle_laufende_und_naechste_spiele(self):
        self.veroeffentlichen()
        r = self.client.get(self.url)
        self.assertContains(r, '<table class="tabelle">', html=False)
        self.assertContains(r, "Läuft · 0:00")
        self.assertContains(r, "Als Nächstes · 0:20")
        self.assertContains(r, 'data-neu-laden="30"', html=False)
        self.assertNotContains(r, "gewinnt!")
        self.assertNotContains(r, "example.de")  # öffentlich: keine E-Mails

    def test_siegerbanner_wenn_alle_spiele_beendet(self):
        self.veroeffentlichen()
        for s in self.t.spiele.all():  # das Team mit der kleineren ID gewinnt immer
            s.saetze_a, s.saetze_b = (2, 0) if s.team_a.pk < s.team_b.pk else (0, 2)
            s.status = Spiel.Status.BEENDET
            s.save()
        ko.aktualisieren(self.t)
        r = self.client.get(self.url)
        self.assertContains(r, "🏆 Team 0 gewinnt!")
        self.assertContains(r, "2. Team 1")
        self.assertNotContains(r, "Läuft ·")

    def test_gleichstand_um_platz_eins(self):
        t = Turnier.objects.create(
            name="Ring-Cup", oeffentlich=True, datum=timezone.localdate(), beginn=time(0, 0), ort="Halle",
            meldeschluss=timezone.now() - timedelta(days=1), max_teams=8,
        )
        x, y, z = (Team.objects.create(turnier=t, name=n, kapitaen_name="K", kapitaen_email="k@example.de")
                   for n in ("Xaver", "Yeti", "Zorro"))
        spielplan.erzeugen(t)
        t.spielplan_veroeffentlicht = True
        t.save()
        ring = {frozenset((x, y)): x, frozenset((y, z)): y, frozenset((x, z)): z}  # jeder schlägt einen
        for s in t.spiele.all():
            sieger = ring[frozenset((s.team_a, s.team_b))]
            s.saetze_a, s.saetze_b = (2, 0) if sieger == s.team_a else (0, 2)
            s.status = Spiel.Status.BEENDET
            s.save()
        r = self.client.get(f"{reverse('beamer')}?turnier={t.pk}")
        self.assertContains(r, "Xaver, Yeti und Zorro teilen sich Platz 1!")
        self.assertNotContains(r, "gewinnt!")

    def test_link_auf_der_orga_seite(self):
        self.client.force_login(User.objects.create_superuser("orga", "o@example.de", "x"))
        seite = f"{reverse('orga_spielplan')}?turnier={self.t.pk}"
        self.assertNotContains(self.client.get(seite), "Beamer →")  # erst nach der Veröffentlichung
        self.veroeffentlichen()
        self.assertContains(self.client.get(seite), "Beamer →")

        # nicht öffentlich: Die Seite würde still ein anderes Turnier zeigen – also kein Link, sondern ein Hinweis
        self.t.oeffentlich = False
        self.t.save()
        r = self.client.get(seite)
        self.assertNotContains(r, "Beamer →")
        self.assertContains(r, "Beamer: erst Turnier öffentlich schalten")
