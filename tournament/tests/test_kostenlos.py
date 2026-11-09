from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from tournament import warteliste
from tournament.models import Team, Turnier
from tournament.tests.test_views import anmeldedaten


class OhneStartgebuehrTests(TestCase):
    def setUp(self):
        self.t = Turnier.objects.create(
            name="Pong-Cup", oeffentlich=True, datum=timezone.localdate() + timedelta(days=30), ort="Keller",
            meldeschluss=timezone.now() + timedelta(days=10), max_teams=2, anmeldung_offen=True,
            min_spieler=2, startgebuehr_eur=0, zahlungsinfo="IBAN DE00 1234",
        )

    def team(self, name, **kwargs):
        return Team.objects.create(turnier=self.t, name=name, kapitaen_name="K", kapitaen_email=f"{name}@example.de",
                                   **kwargs)

    def test_anmeldung_ist_sofort_bestaetigt_ohne_zahlungsteile(self):
        self.assertContains(self.client.get(reverse("startseite")), "kostenlos")
        self.assertNotContains(self.client.get(reverse("anmelden")), "Startgebühr")

        r = self.client.post(reverse("anmelden"), anmeldedaten(), follow=True)
        team = Team.objects.get()
        self.assertEqual(team.status, Team.Status.BESTAETIGT)
        self.assertEqual(list(Team.objects.im_spielplan()), [team])
        for text in ("Zahlung offen", "Startgebühr", "IBAN"):
            self.assertNotContains(r, text)
        self.assertNotIn("Startgebühr", mail.outbox[0].body)
        self.assertIn("Bestätigt", mail.outbox[0].body)

        r = self.client.get(reverse("team_bearbeiten", args=[team.edit_token]))
        for text in ("Startgebühr", ">Bezahlt<", "IBAN"):
            self.assertNotContains(r, text)

    def test_admin_ohne_zahlungskacheln_und_erinnerungen(self):
        self.team("Alpha")
        self.client.force_login(User.objects.create_superuser("orga", "o@example.de", "x"))
        r = self.client.get(reverse("admin:tournament_team_changelist"), {"turnier__id__exact": self.t.pk})
        self.assertNotContains(r, "Startgebühren eingegangen")
        self.assertContains(r, "Ohne Startgebühr: Teams mit Startplatz sind automatisch bestätigt.")
        self.assertEqual(list(self.t.unbezahlte_teams()), [])
        r = self.client.get(reverse("admin:tournament_team_changelist"),
                            {"turnier__id__exact": self.t.pk, "zahlung": "unbezahlt"})
        self.assertEqual(r.context["cl"].result_count, 0)

        r = self.client.post(reverse("admin:tournament_team_changelist"), {
            "action": "als_csv", "_selected_action": [t.pk for t in self.t.teams.all()],
        })
        zeile = r.content.decode("utf-8").splitlines()[1].split(";")
        self.assertEqual((zeile[6], zeile[7]), ("0,00", "–"))  # Startgebühr, Bezahlt
        self.assertEqual(warteliste.an_zahlung_erinnern(self.t, None), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_nachgerueckt_ist_bestaetigt_und_mail_ohne_gebuehr(self):
        self.team("Alpha")
        wartend = self.team("Wartend", status=Team.Status.WARTELISTE)
        warteliste.nachruecken(wartend, RequestFactory().get("/"))
        wartend.refresh_from_db()
        self.assertEqual(wartend.status, Team.Status.BESTAETIGT)
        [nachricht] = mail.outbox
        self.assertNotIn("Startgebühr", nachricht.body)

    def test_gebuehr_im_admin_aendern_rechnet_status_neu(self):
        self.t.startgebuehr_eur = 20
        self.t.save()
        offen = self.team("Offen")
        bezahlt = self.team("Bezahlt", bezahlt=True)
        wartend = self.team("Wartend", status=Team.Status.WARTELISTE)
        self.assertEqual(offen.status, Team.Status.ANGEMELDET)
        self.client.force_login(User.objects.create_superuser("orga", "o@example.de", "x"))

        def speichern(gebuehr):
            return self.client.post(reverse("admin:tournament_turnier_change", args=[self.t.pk]), {
                "name": self.t.name, "oeffentlich": "on", "datum": self.t.datum.isoformat(), "ort": self.t.ort,
                "startgebuehr_eur": gebuehr, "meldeschluss_0": timezone.localtime(self.t.meldeschluss).strftime("%d.%m.%Y"),
                "meldeschluss_1": "23:59", "anmeldung_offen": "on", "max_teams": "2", "pflicht_spieler": "2",
                "min_spieler": "2", "max_spieler": "10", "modus": "jeder_gegen_jeden", "anzahl_felder": "2", "feldart": "feld",
                "slot_minuten": "20", "mit_schiri": "on", "zaehlmodus": "saetze", "gewinnsaetze": "2",
                "punkte_pro_satz": "25", "punkte_entscheidungssatz": "15", "becher": "10",
                "gruppen-TOTAL_FORMS": "0", "gruppen-INITIAL_FORMS": "0",
            })

        self.assertEqual(speichern("0").status_code, 302)
        for team in (offen, bezahlt, wartend):
            team.refresh_from_db()
        self.assertEqual((offen.status, bezahlt.status, wartend.status),
                         (Team.Status.BESTAETIGT, Team.Status.BESTAETIGT, Team.Status.WARTELISTE))

        speichern("15")  # Gebühr wieder eingeführt: wer nicht bezahlt hat, ist nur noch angemeldet
        offen.refresh_from_db()
        bezahlt.refresh_from_db()
        self.assertEqual((offen.status, bezahlt.status), (Team.Status.ANGEMELDET, Team.Status.BESTAETIGT))
