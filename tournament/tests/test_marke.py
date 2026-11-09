from datetime import time, timedelta

from django.contrib.auth.models import User
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tournament import spielplan
from tournament.models import Team, Turnier


class FeldartTests(TestCase):
    def setUp(self):
        self.t = Turnier.objects.create(
            name="Pong-Cup", oeffentlich=True, datum=timezone.localdate() + timedelta(days=3), beginn=time(18, 0),
            ort="Keller", meldeschluss=timezone.now() + timedelta(days=1), max_teams=8, anzahl_felder=3,
            feldart=Turnier.Feldart.TISCH,
        )
        for i in range(4):
            Team.objects.create(turnier=self.t, name=f"Team {i}", kapitaen_name="K", kapitaen_email="k@example.de")
        spielplan.erzeugen(self.t)
        self.t.spielplan_veroeffentlicht = True
        self.t.save()

    def test_einzahl_und_mehrzahl(self):
        self.assertEqual((self.t.feld_name, self.t.felder_text), ("Tisch", "3 Tische"))
        self.t.anzahl_felder = 1
        self.assertEqual(self.t.felder_text, "1 Tisch")
        self.t.feldart, self.t.anzahl_felder = Turnier.Feldart.PLATZ, 2
        self.assertEqual(self.t.felder_text, "2 Plätze")
        self.t.feldart = Turnier.Feldart.FELD
        self.assertEqual(self.t.felder_text, "2 Felder")

    def test_seiten_sagen_tisch(self):
        self.assertContains(self.client.get(reverse("startseite")), "3 Tische")
        r = self.client.get(reverse("spielplan"))
        self.assertContains(r, "Tisch 1 ·")
        self.assertNotContains(r, "Feld 1")
        self.assertContains(self.client.get(reverse("beamer")), "Tisch 1 ·")
        self.client.force_login(User.objects.create_superuser("orga", "o@example.de", "x"))
        self.assertContains(self.client.get(f"{reverse('orga_spielplan_druck')}?turnier={self.t.pk}"), "<th>Tisch 1</th>",
                            html=False)
        orga = self.client.get(f"{reverse('orga_spielplan')}?turnier={self.t.pk}")
        self.assertContains(orga, "Tisch 1")
        spiel = self.t.spiele.first()
        self.assertContains(self.client.get(reverse("orga_ergebnis", args=[spiel.pk])), f"Tisch {spiel.feld} ·")

    def test_konflikt_meldung(self):
        a, b = self.t.spiele.order_by("uhrzeit", "feld")[:2]
        b.feld = a.feld
        b.save()
        meldungen = spielplan.konflikte(self.t.spiele.select_related("turnier"))
        self.assertTrue(any(f"Tisch {a.feld} ist doppelt belegt." in m for m in meldungen))


# Die Tests lesen den Namen aus config/marke.py statt „Satzball“ fest zu erwarten –
# so laufen sie unverändert auch in Ablegern wie Becherkönig.
MARKE = settings.MARKE


class MarkeTests(TestCase):
    def test_name_aus_config_marke(self):
        r = self.client.get(reverse("startseite"))
        self.assertContains(r, f"<title>{MARKE}</title>", html=False)
        self.assertContains(r, f"{MARKE} ist Open Source")
        self.assertContains(r, "css/marke.css")

    @override_settings(MARKE="Testmarke")
    def test_name_kommt_aus_der_marke(self):
        r = self.client.get(reverse("startseite"))
        self.assertContains(r, "<title>Testmarke</title>", html=False)
        self.assertContains(r, "Testmarke ist Open Source")
        self.assertNotContains(r, f"<title>{MARKE}")
        self.assertNotContains(r, f"{MARKE} ist Open Source")
