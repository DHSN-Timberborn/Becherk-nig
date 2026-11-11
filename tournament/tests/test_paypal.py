"""PayPal-Link am Turnier: Bezahl-Knopf und QR-Code mit dem Betrag des Teams auf der Kapitänsseite."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from tournament.tests.test_gebuehr_pro_person import team_mit
from tournament.tests.test_views import turnier


class PaypalLinkTests(TestCase):
    def test_paypal_me_bekommt_den_betrag_des_teams(self):
        t = turnier(startgebuehr_eur=20, paypal_link="https://paypal.me/orga-cup")
        team = team_mit(t, "Bit Blockers", 4)
        self.assertEqual(team.paypal_url, "https://paypal.me/orga-cup/20EUR")
        t.startgebuehr_eur, t.gebuehr_pro_person = Decimal("2.50"), True
        t.save()
        team.refresh_from_db()
        self.assertEqual(team.paypal_url, "https://paypal.me/orga-cup/10EUR")  # 4 × 2,50
        t.startgebuehr_eur = Decimal("1.25")
        t.save()
        team.refresh_from_db()
        self.assertEqual(team.paypal_url, "https://paypal.me/orga-cup/5EUR")
        team.spieler.first().delete()
        self.assertEqual(team.paypal_url, "https://paypal.me/orga-cup/3.75EUR")  # 3 × 1,25

    def test_andere_paypal_links_bleiben_unveraendert(self):
        t = turnier(paypal_link="https://www.paypal.com/pools/c/abc123")
        self.assertEqual(team_mit(t, "A", 2).paypal_url, "https://www.paypal.com/pools/c/abc123")
        t.paypal_link = "https://paypal.me/orga-cup/15EUR"  # Betrag schon im Link: so lassen
        t.save()
        self.assertEqual(team_mit(t, "B", 2).paypal_url, "https://paypal.me/orga-cup/15EUR")
        t.paypal_link = ""
        t.save()
        self.assertEqual(team_mit(t, "C", 2).paypal_url, "")

    def test_nur_paypal_adressen_erlaubt(self):
        t = turnier()
        for link in ("https://paypal.me/orga", "https://www.paypal.me/orga", "https://www.paypal.com/paypalme/orga"):
            t.paypal_link = link
            t.full_clean()
        for link in ("https://paypal.me.betrug.example/orga", "http://paypal.me/orga", "https://example.de/paypal"):
            t.paypal_link = link
            with self.assertRaises(ValidationError, msg=link):
                t.full_clean()

    def test_kapitaensseite_zeigt_knopf_und_qr_code(self):
        t = turnier(startgebuehr_eur=20, paypal_link="https://paypal.me/orga-cup")
        team = team_mit(t, "Bit Blockers", 2)
        url = reverse("team_bearbeiten", args=[team.edit_token])
        r = self.client.get(url)
        self.assertContains(r, 'href="https://paypal.me/orga-cup/20EUR"')
        self.assertContains(r, "Mit PayPal zahlen · 20 €")
        self.assertContains(r, 'class="qr"><title>PayPal-Link als QR-Code</title>', html=False)
        self.assertContains(r, "Herbst-Cup 2026 – Bit Blockers")

        team.bezahlt = True
        team.save()
        self.assertNotContains(self.client.get(url), "Mit PayPal zahlen")  # bezahlt: kein Knopf mehr

    def test_ohne_link_oder_auf_der_warteliste_kein_knopf(self):
        t = turnier(startgebuehr_eur=20)
        team = team_mit(t, "Ohne Link", 2)
        self.assertNotContains(self.client.get(reverse("team_bearbeiten", args=[team.edit_token])), "PayPal zahlen")
        t.paypal_link = "https://paypal.me/orga-cup"
        t.save()
        wartet = team_mit(t, "Wartet", 2, status="warteliste")
        self.assertNotContains(self.client.get(reverse("team_bearbeiten", args=[wartet.edit_token])), "PayPal zahlen")
