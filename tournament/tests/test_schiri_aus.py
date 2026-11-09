from datetime import date, datetime, time, timezone

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tournament import spielplan
from tournament.models import Spiel, Team, Turnier


class OhneSchiriTests(TestCase):
    def setUp(self):
        self.t = Turnier.objects.create(
            name="Pong-Cup", datum=date(2026, 11, 14), beginn=time(18, 0), ort="Keller", max_teams=8,
            meldeschluss=datetime(2026, 10, 31, tzinfo=timezone.utc),
            anzahl_felder=1,  # so ist in jedem Slot ein Team frei, das pfeifen kann
        )
        for i in range(5):
            Team.objects.create(turnier=self.t, name=f"Team {i}", kapitaen_name="K", kapitaen_email="k@example.de",
                                status=Team.Status.BESTAETIGT, bezahlt=True)
        self.client.force_login(User.objects.create_superuser("orga", "o@example.de", "x"))

    def schiris(self):
        return list(self.t.spiele.order_by("pk").values_list("schiri_team", flat=True))

    def admin_speichern(self, mit_schiri):
        """Turnier über das Admin-Formular speichern (wie die Orga), nur der Haken ändert sich."""
        gruppe = self.t.gruppen.get()
        daten = {
            "name": self.t.name, "datum": "2026-11-14", "beginn": "18:00", "ort": self.t.ort, "startgebuehr_eur": "0",
            "meldeschluss_0": "31.10.2026", "meldeschluss_1": "23:59", "max_teams": "8",
            "pflicht_spieler": "2", "min_spieler": "6", "max_spieler": "10", "modus": "jeder_gegen_jeden",
            "anzahl_felder": "1", "slot_minuten": "20", "zaehlmodus": "saetze", "gewinnsaetze": "2",
            "punkte_pro_satz": "25", "punkte_entscheidungssatz": "15", "becher": "10",
            "gruppen-TOTAL_FORMS": "1", "gruppen-INITIAL_FORMS": "1",
            "gruppen-0-id": str(gruppe.pk), "gruppen-0-turnier": str(self.t.pk), "gruppen-0-name": gruppe.name,
        }
        if mit_schiri:
            daten["mit_schiri"] = "on"
        return self.client.post(reverse("admin:tournament_turnier_change", args=[self.t.pk]), daten, follow=True)

    def test_spielplan_ohne_schiris(self):
        self.t.mit_schiri = False
        self.t.save()
        spielplan.erzeugen(self.t)
        self.assertEqual(set(self.schiris()), {None})
        seite = self.client.get(f"{reverse('orga_spielplan')}?turnier={self.t.pk}")
        self.assertNotContains(seite, "Schiri:")
        self.assertContains(seite, "ohne Schiris")
        druck = self.client.get(f"{reverse('orga_spielplan_druck')}?turnier={self.t.pk}")
        self.assertNotContains(druck, "Schiri:")

        spielplan.schiris_neu(self.t)  # z. B. nach dem Verschieben per Drag & Drop
        self.assertEqual(set(self.schiris()), {None})

    def test_umschalten_im_admin_wirkt_auf_offene_spiele(self):
        spielplan.erzeugen(self.t)
        self.assertNotIn(None, self.schiris())
        beendet = self.t.spiele.order_by("uhrzeit", "feld").first()
        beendet.saetze_a, beendet.saetze_b, beendet.status = 2, 0, Spiel.Status.BEENDET
        beendet.save()
        schiri_beendet = beendet.schiri_team_id

        r = self.admin_speichern(mit_schiri=False)
        self.assertContains(r, "Schiris bei allen offenen Spielen ausgetragen.")
        self.assertEqual(self.t.spiele.exclude(pk=beendet.pk).exclude(schiri_team=None).count(), 0)
        beendet.refresh_from_db()
        self.assertEqual(beendet.schiri_team_id, schiri_beendet)  # beendete Spiele behalten ihren Schiri

        r = self.admin_speichern(mit_schiri=True)
        self.assertContains(r, "Schiris der offenen Spiele neu eingeteilt.")
        self.assertNotIn(None, self.schiris())
