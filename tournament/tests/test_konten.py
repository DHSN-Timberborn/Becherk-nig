"""Orga-Konten: Login → Orga-Übersicht, Rollen mit Bausteinen, Einladungen per Mail oder Link, Konto anlegen."""

from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tournament import rollen
from tournament.models import Einladung, Spiel, Team
from tournament.tests.test_views import turnier

PASSWORT = "Becher-Ball-2026!"


def rolle(name, *bausteine):
    gruppe = Group.objects.create(name=name)
    rollen.rechte_setzen(gruppe, bausteine)
    return gruppe


def konto(email, gruppe=None, **kwargs):
    u = User.objects.create_user(username=email, email=email, password=PASSWORT, is_staff=True, **kwargs)
    if gruppe:
        u.groups.add(gruppe)
    return u


class LoginTests(TestCase):
    def test_login_fuehrt_zur_orga_uebersicht(self):
        konto("helfer@example.de", rolle("Helfer"))
        r = self.client.post(reverse("orga_login"), {"username": "Helfer@Example.de", "password": PASSWORT})
        self.assertRedirects(r, reverse("orga_uebersicht"))
        r = self.client.get(reverse("orga_uebersicht"))
        self.assertContains(r, "Spielplan &amp; Ergebnisse")
        self.assertNotContains(r, "Benutzer &amp; Rollen")  # ohne den Baustein keine Kachel

    def test_erster_zugang_mit_benutzername(self):
        User.objects.create_superuser("orga", "o@example.de", PASSWORT)
        r = self.client.post(reverse("orga_login"), {"username": "orga", "password": PASSWORT})
        self.assertRedirects(r, reverse("orga_uebersicht"))
        self.assertContains(self.client.get(reverse("orga_uebersicht")), "Benutzer &amp; Rollen")

    def test_admin_login_und_orga_seiten_schicken_zum_orga_login(self):
        r = self.client.get(reverse("admin:login") + "?next=/admin/")
        self.assertRedirects(r, reverse("orga_login") + "?next=/admin/", fetch_redirect_response=False)
        r = self.client.get(reverse("orga_uebersicht"))
        self.assertRedirects(r, reverse("orga_login") + "?next=/orga/", fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse("startseite")), f'href="{reverse("orga_login")}"')

    def test_falsches_passwort(self):
        konto("a@example.de")
        r = self.client.post(reverse("orga_login"), {"username": "a@example.de", "password": "falsch"})
        self.assertContains(r, "stimmen nicht")


class RechteTests(TestCase):
    def setUp(self):
        self.t = turnier()
        for i in range(6):
            Team.objects.create(turnier=self.t, name=f"T{i}", kapitaen_name="K", kapitaen_email="k@example.de",
                                bezahlt=True)

    def test_ohne_baustein_nur_ansehen(self):
        self.client.force_login(konto("zuschauer@example.de", rolle("Zuschauer")))
        url = reverse("orga_spielplan") + f"?turnier={self.t.pk}"
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post(url, {"aktion": "erzeugen", "turnier": self.t.pk, "modus": "gruppen_ko",
                                   "anzahl_gruppen": 2, "beginn": "09:00", "slot_minuten": 20}, follow=True)
        self.assertContains(r, "fehlt deiner Rolle")
        self.assertFalse(Spiel.objects.exists())
        self.assertEqual(self.client.get(reverse("orga_rollen")).status_code, 403)
        self.assertEqual(self.client.get(reverse("orga_einladen")).status_code, 403)

    def test_mit_baustein_spielplan(self):
        self.client.force_login(konto("leitung@example.de", rolle("Turnierleitung", "spielplan")))
        self.client.post(reverse("orga_spielplan") + f"?turnier={self.t.pk}", {
            "aktion": "erzeugen", "turnier": self.t.pk, "modus": "gruppen_ko", "anzahl_gruppen": 2,
            "beginn": "09:00", "slot_minuten": 20})
        self.assertTrue(Spiel.objects.exists())


class RollenTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("orga", "o@example.de", PASSWORT))

    def test_rolle_anlegen_und_aendern(self):
        r = self.client.post(reverse("orga_rolle_neu"), {"name": "Kasse", "bausteine": ["teams"]})
        self.assertRedirects(r, reverse("orga_rollen"))
        kasse = Group.objects.get(name="Kasse")
        self.assertEqual(rollen.bausteine_von(kasse), ["teams"])
        rechte = {p.codename for p in kasse.permissions.all()}
        self.assertTrue({"change_team", "view_turnier", "view_spiel"} <= rechte)
        self.assertNotIn("change_spiel", rechte)

        self.client.post(reverse("orga_rolle", args=[kasse.pk]), {"name": "Kasse", "bausteine": ["teams", "spielplan"]})
        self.assertEqual(rollen.bausteine_von(kasse), ["teams", "spielplan"])
        self.client.post(reverse("orga_rolle", args=[kasse.pk]), {"name": "Kasse"})
        self.assertEqual(rollen.bausteine_von(kasse), [])
        self.assertIn("view_team", {p.codename for p in kasse.permissions.all()})  # ansehen bleibt

        r = self.client.post(reverse("orga_rolle_neu"), {"name": "kasse"})
        self.assertContains(r, "gibt es schon")

    def test_rolle_mit_mitgliedern_nicht_loeschen(self):
        kasse = rolle("Kasse")
        konto("k@example.de", kasse)
        self.client.post(reverse("orga_rolle_loeschen", args=[kasse.pk]))
        self.assertTrue(Group.objects.filter(pk=kasse.pk).exists())
        kasse.user_set.clear()
        self.client.post(reverse("orga_rolle_loeschen", args=[kasse.pk]))
        self.assertFalse(Group.objects.filter(pk=kasse.pk).exists())


class EinladungTests(TestCase):
    def setUp(self):
        self.leitung = rolle("Turnierleitung", "turniere", "teams", "spielplan", "benutzer")
        self.helfer = rolle("Helfer", "spielplan")
        self.chef = konto("chef@example.de", self.leitung, first_name="Maxi")
        self.client.force_login(self.chef)

    def test_einladung_als_link(self):
        r = self.client.post(reverse("orga_einladen"), {"rolle": self.helfer.pk, "weg": "link", "email": "x@y.de"})
        e = Einladung.objects.get()
        self.assertEqual((e.rolle, e.email, e.erstellt_von), (self.helfer, "", self.chef))
        self.assertRedirects(r, reverse("orga_einladung", args=[e.pk]))  # Neuladen erzeugt keine zweite
        self.assertContains(self.client.get(r.url), reverse("einladung_annehmen", args=[e.token]))
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(self.client.get(reverse("orga_benutzer")), "Link zum Teilen")

    def test_einladung_per_mail(self):
        r = self.client.post(reverse("orga_einladen"), {"rolle": self.helfer.pk, "weg": "mail", "email": ""})
        self.assertContains(r, "Bitte die E-Mail-Adresse angeben")
        r = self.client.post(reverse("orga_einladen"), {"rolle": self.helfer.pk, "weg": "mail", "email": "Chef@example.de"})
        self.assertContains(r, "gibt es schon ein Konto")
        self.client.post(reverse("orga_einladen"), {"rolle": self.helfer.pk, "weg": "mail", "email": "Neu@Example.de"})
        e = Einladung.objects.get()
        self.assertEqual(e.email, "neu@example.de")
        self.assertEqual(mail.outbox[0].to, ["neu@example.de"])
        self.assertIn(reverse("einladung_annehmen", args=[e.token]), mail.outbox[0].body)
        self.assertIn("„Helfer“", mail.outbox[0].body)

    def test_konto_anlegen_ueber_link(self):
        e = Einladung.objects.create(rolle=self.helfer, erstellt_von=self.chef)
        self.client.logout()
        url = reverse("einladung_annehmen", args=[e.token])
        self.assertContains(self.client.get(url), "als <b>Helfer</b>", html=False)
        daten = {"vorname": "Lena", "nachname": "Hoffmann", "email": "Lena@Example.de", "telefon": "0171 123",
                 "passwort1": PASSWORT, "passwort2": "anders"}
        self.assertContains(self.client.post(url, daten), "stimmen nicht überein")
        daten["passwort2"] = PASSWORT
        r = self.client.post(url, daten)
        self.assertRedirects(r, reverse("orga_uebersicht"))
        lena = User.objects.get(email="lena@example.de")
        self.assertEqual((lena.username, lena.get_full_name(), lena.is_staff, lena.is_superuser),
                         ("lena@example.de", "Lena Hoffmann", True, False))
        self.assertEqual(list(lena.groups.all()), [self.helfer])
        self.assertEqual(lena.orga_profil.telefon, "0171 123")
        self.assertContains(self.client.get(reverse("orga_uebersicht")), "Hallo Lena")

        self.client.logout()  # Link funktioniert nur einmal
        self.assertEqual(self.client.get(url).status_code, 410)
        self.assertEqual(self.client.post(url, {**daten, "email": "zwei@example.de"}).status_code, 410)
        self.assertEqual(User.objects.filter(is_staff=True).count(), 2)

    def test_per_mail_eingeladen_bleibt_die_adresse(self):
        e = Einladung.objects.create(rolle=self.helfer, email="neu@example.de")
        self.client.logout()
        self.client.post(reverse("einladung_annehmen", args=[e.token]), {
            "vorname": "N", "nachname": "Eu", "email": "fremd@example.de", "passwort1": PASSWORT, "passwort2": PASSWORT})
        self.assertTrue(User.objects.filter(email="neu@example.de").exists())
        self.assertFalse(User.objects.filter(email="fremd@example.de").exists())

    def test_abgelaufen_oder_zurueckgezogen(self):
        alt = Einladung.objects.create(rolle=self.helfer, gueltig_bis=timezone.now() - timedelta(minutes=1))
        weg = Einladung.objects.create(rolle=self.helfer)
        self.client.post(reverse("orga_einladung_widerrufen", args=[weg.pk]))
        self.client.logout()
        self.assertContains(self.client.get(reverse("einladung_annehmen", args=[alt.token])), "nicht mehr gültig",
                            status_code=410)
        self.assertEqual(self.client.get(reverse("einladung_annehmen", args=[weg.token])).status_code, 404)

    def test_benutzer_bearbeiten(self):
        helfer = konto("h@example.de", self.helfer)
        url = reverse("orga_benutzer_bearbeiten", args=[helfer.pk])
        self.client.post(url, {"rolle": self.leitung.pk, "aktiv": ""})
        helfer.refresh_from_db()
        self.assertEqual((list(helfer.groups.all()), helfer.is_active), ([self.leitung], False))
        r = self.client.post(reverse("orga_benutzer_bearbeiten", args=[self.chef.pk]), {"rolle": self.leitung.pk})
        self.assertContains(r, "eigene Konto kann man nicht sperren")
        boss = User.objects.create_superuser("boss", "b@example.de", PASSWORT)
        self.assertEqual(self.client.get(reverse("orga_benutzer_bearbeiten", args=[boss.pk])).status_code, 403)
