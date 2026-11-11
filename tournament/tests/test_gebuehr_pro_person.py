"""Startgebühr pro Person (Turnier.gebuehr_pro_person): ein Team zahlt Betrag × eingetragene Spieler."""

from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from tournament.models import Spieler, Team
from tournament.tests.test_views import anmeldedaten, turnier


def team_mit(t, name, spieler, **kwargs):
    team = Team.objects.create(turnier=t, name=name, kapitaen_name="K", kapitaen_email="k@example.de", **kwargs)
    for i in range(spieler):
        Spieler.objects.create(team=team, vorname=f"S{i}", nachname="X")
    return team


class GebuehrProPersonTests(TestCase):
    def test_betrag_pro_team_oder_pro_person(self):
        t = turnier(startgebuehr_eur=5, max_spieler=None)
        team = team_mit(t, "Becher Bros", 4)
        self.assertEqual(team.startgebuehr, Decimal(5))  # Vorgabe: pro Team
        self.assertEqual(team.startgebuehr_text, "5 €")
        t.gebuehr_pro_person = True
        t.save()
        team.refresh_from_db()
        self.assertEqual(team.startgebuehr, Decimal(20))
        self.assertEqual(team.startgebuehr_text, "20 € (4 × 5 € pro Person)")

    def test_zahlungsuebersicht_rechnet_pro_person(self):
        t = turnier(startgebuehr_eur=Decimal("2.50"), gebuehr_pro_person=True, max_spieler=None)
        team_mit(t, "Bezahlt", 4, bezahlt=True)
        team_mit(t, "Offen", 3)
        team_mit(t, "Wartet", 6, status=Team.Status.WARTELISTE)
        u = t.zahlungsuebersicht()
        self.assertEqual(u["eingegangen"], Decimal("10"))   # 4 × 2,50
        self.assertEqual(u["erwartet"], Decimal("17.50"))   # (4 + 3) × 2,50, Warteliste nicht
        self.assertEqual(u["unbezahlt"], 1)

    def test_seiten_und_mail_zeigen_pro_person(self):
        t = turnier(startgebuehr_eur=5, gebuehr_pro_person=True, max_spieler=None)
        r = self.client.get(reverse("startseite"))
        self.assertContains(r, "pro Person")
        self.assertNotContains(r, "pro Team")
        r = self.client.get(reverse("anmelden"))
        self.assertContains(r, "Startgebühr 5 € pro Person")

        spieler = (("Lena", "H"), ("Max", "M"), ("Kim", "N"))
        self.client.post(reverse("anmelden"), anmeldedaten(spieler=spieler))
        self.assertIn("Startgebühr: 15 € (3 × 5 € pro Person)", mail.outbox[0].body)

        team = Team.objects.get(name="Bit Blockers")
        r = self.client.get(reverse("team_bearbeiten", args=[team.edit_token]))
        self.assertContains(r, '<span class="zahl">15 €</span>', html=False)
        self.assertContains(r, "3 Spieler × 5 € pro Person")
        self.assertContains(r, "15 € offen")

    def test_pro_team_bleibt_wie_bisher(self):
        t = turnier(startgebuehr_eur=20)
        r = self.client.get(reverse("startseite"))
        self.assertContains(r, "pro Team")
        self.client.post(reverse("anmelden"), anmeldedaten())
        self.assertIn("Startgebühr: 20 €. Sobald", mail.outbox[0].body)
        self.assertNotIn("pro Person", mail.outbox[0].body)
        self.assertFalse(t.gebuehr_pro_person)
