from datetime import date, datetime, time, timezone

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from tournament import ko, spielplan
from tournament.models import Gruppe, Spiel, Team, Turnier
from tournament.tabelle import gruppentabellen


class BecherModusTests(TestCase):
    def setUp(self):
        self.t = Turnier.objects.create(
            name="Pong-Cup", datum=date(2026, 11, 14), beginn=time(18, 0), ort="Keller", max_teams=8,
            meldeschluss=datetime(2026, 10, 31, tzinfo=timezone.utc), zaehlmodus=Turnier.Zaehlmodus.BECHER,
            becher=10,
        )
        self.gruppe = Gruppe.objects.create(turnier=self.t, name="A")
        self.teams = {n: Team.objects.create(turnier=self.t, name=n, kapitaen_name="K", kapitaen_email="k@example.de",
                                             gruppe=self.gruppe, status=Team.Status.BESTAETIGT, bezahlt=True)
                      for n in ["Adler", "Zebra", "Chaos", "Delta"]}

    def spiel(self, a, b, pa, pb):
        """Beendetes Gruppenspiel; pa/pb = übrige Becher."""
        return Spiel.objects.create(turnier=self.t, gruppe=self.gruppe, team_a=self.teams[a], team_b=self.teams[b],
                                    punkte_a=pa, punkte_b=pb, status=Spiel.Status.BEENDET)

    def test_wertung_siege_differenz_dann_getroffene_becher(self):
        self.spiel("Adler", "Delta", 3, 0)  # Δ +3, 10 getroffen
        self.spiel("Chaos", "Delta", 5, 2)  # Δ +3, nur 8 getroffen (auf Zeit, beide haben noch Becher)
        self.spiel("Zebra", "Delta", 1, 0)  # Δ +1
        [(_, tabelle)] = gruppentabellen(self.t)
        # Im Punkte-Modus läge Chaos vorn (mehr eigene Punkte), hier zählen die getroffenen Becher
        self.assertEqual([z.team.name for z in tabelle], ["Adler", "Chaos", "Zebra", "Delta"])
        adler, delta = tabelle[0], tabelle[-1]
        self.assertEqual((adler.pkt, adler.getroffen, adler.verloren, adler.pd), (2, 10, 7, 3))
        self.assertEqual((delta.pkt, delta.getroffen, delta.verloren, delta.pd), (0, 21, 28, -7))

    def test_direkter_vergleich(self):
        # Zebra und Adler: je 2 Siege, gleiche Differenz und gleich viele Treffer – Zebra hat Adler geschlagen
        self.spiel("Zebra", "Adler", 2, 0)
        self.spiel("Chaos", "Zebra", 2, 0)
        self.spiel("Zebra", "Delta", 2, 0)
        self.spiel("Adler", "Chaos", 2, 0)
        self.spiel("Adler", "Delta", 2, 0)
        [(_, tabelle)] = gruppentabellen(self.t)
        self.assertEqual([z.team.name for z in tabelle[:2]], ["Zebra", "Adler"])
        self.assertEqual((tabelle[0].pd, tabelle[0].getroffen), (tabelle[1].pd, tabelle[1].getroffen))

    def test_ergebnis_pruefen(self):
        spiel = Spiel(turnier=self.t, gruppe=self.gruppe, team_a=self.teams["Adler"], team_b=self.teams["Zebra"],
                      status=Spiel.Status.BEENDET)
        for pa, pb, fehler in [(None, 0, "beider Teams"), (11, 0, "nur 10 Becher"), (2, 2, "Verlängerung")]:
            spiel.punkte_a, spiel.punkte_b = pa, pb
            with self.assertRaisesMessage(ValidationError, fehler):
                spiel.full_clean()
        spiel.punkte_a, spiel.punkte_b = 0, 4  # Verlierer hat keinen Becher mehr
        spiel.full_clean()
        self.assertEqual(spiel.sieger, self.teams["Zebra"])

    def test_ergebnis_eintragen_und_anzeigen(self):
        self.t.oeffentlich = True
        self.t.save()
        spielplan.erzeugen(self.t)
        self.t.spielplan_veroeffentlicht = True
        self.t.save()
        self.client.force_login(User.objects.create_superuser("orga", "o@example.de", "x"))
        spiel = self.t.spiele.first()
        url = reverse("orga_ergebnis", args=[spiel.pk])
        r = self.client.get(url)
        self.assertContains(r, 'name="punkte_a"')
        self.assertContains(r, 'max="10"')  # Zähler endet bei der Becherzahl
        self.assertContains(r, "Wie viele Becher stehen noch?")
        self.assertNotContains(r, 'name="saetze_a"')

        r = self.client.post(url, {"punkte_a": "3", "punkte_b": "3"}, follow=True)
        self.assertContains(r, "Verlängerung")
        self.client.post(url, {"punkte_a": "3", "punkte_b": "0"})
        spiel.refresh_from_db()
        self.assertEqual((spiel.status, spiel.punkte_a, spiel.punkte_b), (Spiel.Status.BEENDET, 3, 0))

        r = self.client.get(reverse("tabelle"))
        self.assertContains(r, 'title="Becher-Differenz">Δ</th>', html=False)
        self.assertContains(r, "<td><b>2</b></td><td>10</td><td>7</td><td>+3</td>", html=False)
        self.assertContains(r, "Sortiert nach Punkten, Δ, getroffenen Bechern")
        r = self.client.get(reverse("spielplan"))
        self.assertContains(r, "10 Becher")
        self.assertContains(r, "Becher übrig")


class BecherKoTests(TestCase):
    def test_bester_zweiter_nach_getroffenen_bechern_pro_spiel(self):
        t = Turnier.objects.create(
            name="Pong-Cup", datum=date(2026, 11, 14), beginn=time(18, 0), ort="Keller", max_teams=12,
            meldeschluss=datetime(2026, 10, 31, tzinfo=timezone.utc), modus=Turnier.Modus.GRUPPEN_KO,
            zaehlmodus=Turnier.Zaehlmodus.BECHER, becher=6,
        )
        for i in range(9):
            Team.objects.create(turnier=t, name=f"Team {i}", kapitaen_name="K", kapitaen_email="k@example.de",
                                status=Team.Status.BESTAETIGT, bezahlt=True)
        spielplan.erzeugen(t, anzahl_gruppen=3)
        zweite = {}
        for gruppe in t.gruppen.order_by("name"):
            erster, zweiter, dritter = gruppe.teams.order_by("pk")
            zweite[gruppe.name] = zweiter
            # Der Zweite gewinnt nur gegen den Dritten, immer mit +2 Bechern Differenz.
            # Gruppe C trifft dabei 6 Becher (2:0), A und B nur 4 (4:2, auf Zeit).
            treffer = (2, 0) if gruppe.name == "C" else (4, 2)
            for s in t.spiele.filter(gruppe=gruppe):
                paar = {s.team_a, s.team_b}
                sieger = erster if erster in paar else zweiter
                s.punkte_a, s.punkte_b = (2, 0) if sieger == s.team_a else (0, 2)
                if paar == {zweiter, dritter}:
                    s.punkte_a, s.punkte_b = treffer if s.team_a == zweiter else treffer[::-1]
                s.status = Spiel.Status.BEENDET
                s.save()
        ko.aktualisieren(t)
        halbfinale = [s for s in spielplan.mit_titeln(t) if s.phase == Spiel.Phase.HALBFINALE]
        self.assertIn(zweite["C"], {s.team_a for s in halbfinale} | {s.team_b for s in halbfinale})
