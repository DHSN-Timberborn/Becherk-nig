"""Datenmodell laut docs/konzept.md: Turnier, Team, Spieler, Gruppe, Spiel.

Die Tabelle (Platzierung) wird nicht gespeichert, sondern aus beendeten Spielen berechnet.
"""

import secrets
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.template.defaultfilters import floatformat
from django.utils import timezone


def _euro(betrag):
    """Betrag wie in den Templates (floatformat:"-2"): „20“, „7,50“."""
    return floatformat(betrag, "-2")


# Erlaubte Ziele für Turnier.paypal_link – unter „PayPal“ soll kein fremder Link landen.
PAYPAL_HOSTS = {"paypal.me", "paypal.com"}

# Vorgabe für Turnier.pflicht_spieler (darunter kann ein Team nicht antreten).
# min_spieler am Turnier ist nur eine Empfehlung.
MIN_SPIELER = 2


def neuer_edit_token():
    # 24 Zufallsbytes -> 32 URL-sichere Zeichen
    return secrets.token_urlsafe(24)


class Turnier(models.Model):
    class Modus(models.TextChoices):
        JEDER_GEGEN_JEDEN = "jeder_gegen_jeden", "Jeder gegen jeden"
        GRUPPEN_KO = "gruppen_ko", "Gruppen + K.-o."

    class Zaehlmodus(models.TextChoices):
        SAETZE = "saetze", "Satz-Modus"
        PUNKTE = "punkte", "Punkte-Modus (ohne Sätze, mehr Punkte gewinnt)"
        BECHER = "becher", "Becher-Modus (z. B. Bierpong: mehr übrige Becher gewinnt)"

    class Gewinnsaetze(models.IntegerChoices):
        BEST_OF_1 = 1, "Best of 1"
        BEST_OF_3 = 2, "Best of 3"
        BEST_OF_5 = 3, "Best of 5"

    name = models.CharField(max_length=100)
    oeffentlich = models.BooleanField(
        "öffentlich sichtbar", default=False,
        help_text="Erst dann sehen Besucher das Turnier (Startseite, Turnierliste, Anmeldung). "
                  "Entwürfe und Testturniere ausgeschaltet lassen.",
    )
    datum = models.DateField()
    beginn = models.TimeField(null=True, blank=True, help_text="Startzeit am Spieltag, z. B. 9:30.")
    ort = models.CharField(max_length=200)
    startgebuehr_eur = models.DecimalField("Startgebühr (€)", max_digits=6, decimal_places=2, default=0)
    gebuehr_pro_person = models.BooleanField(
        "Startgebühr pro Person", default=False,
        help_text="Aus: Betrag gilt pro Team. An: pro eingetragenem Spieler (z. B. Bierpong) – ein Team zahlt Betrag × Spielerzahl.",
    )
    zahlungsinfo = models.TextField(
        blank=True, help_text="Wie gezahlt wird (IBAN, PayPal, Bar-Termine). Erscheint nach der Anmeldung.",
    )
    paypal_link = models.URLField(
        "PayPal-Link", blank=True,
        help_text="Optional, z. B. https://paypal.me/eure-orga – Kapitäne bekommen dann einen Bezahl-Knopf und QR-Code "
                  "mit dem Betrag ihres Teams. Auch nachträglich möglich.",
    )
    meldeschluss = models.DateTimeField()
    max_teams = models.PositiveSmallIntegerField("max. Teams")
    pflicht_spieler = models.PositiveSmallIntegerField(
        "Pflicht: mind. Spieler pro Team", default=MIN_SPIELER, validators=[MinValueValidator(1)],
        help_text="Mit weniger Spielern lehnt das Formular die Anmeldung ab.",
    )
    min_spieler = models.PositiveSmallIntegerField(
        "empfohlene Spielerzahl", default=6,
        help_text="Nur ein Hinweis im Formular – weniger Spieler (ab der Pflichtzahl) sind erlaubt.",
    )
    max_spieler = models.PositiveSmallIntegerField(
        "max. Spieler pro Team", default=10, null=True, blank=True, help_text="Leer = keine Obergrenze.",
    )
    mindestalter = models.PositiveSmallIntegerField(
        "Mindestalter", null=True, blank=True, validators=[MinValueValidator(1)],
        help_text="Leer = keine Altersgrenze. Sonst bestätigt der Kapitän bei der Anmeldung (und beim Ändern der "
                  "Spielerliste), dass alle Spieler so alt sind – z. B. 16 bei Bier.",
    )
    anmeldung_offen = models.BooleanField("Anmeldung offen", default=False)
    modus = models.CharField(max_length=20, choices=Modus.choices, default=Modus.JEDER_GEGEN_JEDEN)
    class Feldart(models.TextChoices):
        FELD = "feld", "Feld"
        TISCH = "tisch", "Tisch"
        PLATZ = "platz", "Platz"

    FELD_MEHRZAHL = {"feld": "Felder", "tisch": "Tische", "platz": "Plätze"}

    anzahl_felder = models.PositiveSmallIntegerField("Anzahl Felder", default=2, help_text="bzw. Tische oder Plätze")
    feldart = models.CharField(
        "Bezeichnung", max_length=10, choices=Feldart.choices, default=Feldart.FELD,
        help_text="Wie die Spielorte heißen, z. B. Tisch beim Bierpong.",
    )
    slot_minuten = models.PositiveSmallIntegerField("Slotlänge (min)", default=20)
    mit_schiri = models.BooleanField(
        "Schiris einteilen", default=True,
        help_text="Aus: Spiele ohne Schiri (z. B. Bierpong). Umschalten wirkt sofort auf alle offenen Spiele.",
    )
    spielplan_veroeffentlicht = models.BooleanField("Spielplan veröffentlicht", default=False)
    zahlungserinnerung_am = models.DateTimeField(
        "zuletzt an Zahlung erinnert", null=True, blank=True, editable=False,
    )
    warteliste_automatisch = models.BooleanField(
        "Warteliste automatisch nachrücken lassen", default=False,
        help_text="Wird ein Platz frei, rückt das erste Team der Warteliste nach und bekommt eine Mail. "
                  "Sonst entscheidet die Orga über die Aktion „Von der Warteliste nachrücken“.",
    )
    teamdaten_geloescht_am = models.DateField(
        "Teamdaten gelöscht am", null=True, blank=True, editable=False,
        help_text="Spieler und Kapitänsdaten sind gelöscht; Teamnamen und Ergebnisse bleiben.",
    )
    zaehlmodus = models.CharField("Zählmodus", max_length=10, choices=Zaehlmodus.choices, default=Zaehlmodus.SAETZE)
    gewinnsaetze = models.PositiveSmallIntegerField(
        "Gewinnsätze", choices=Gewinnsaetze.choices, default=Gewinnsaetze.BEST_OF_3,
        help_text="Nur im Satz-Modus.",
    )
    punkte_pro_satz = models.PositiveSmallIntegerField(
        "Punkte pro Satz", default=25, help_text="Nur im Satz-Modus.",
    )
    punkte_entscheidungssatz = models.PositiveSmallIntegerField(
        "Punkte Entscheidungssatz", default=15, help_text="Nur im Satz-Modus.",
    )
    becher = models.PositiveSmallIntegerField(
        "Becher pro Team", default=10, validators=[MinValueValidator(1)],
        help_text="Nur im Becher-Modus. Eingetragen wird, wie viele Becher jedes Team am Ende noch stehen hat.",
    )

    class Meta:
        verbose_name = "Turnier"
        verbose_name_plural = "Turniere"
        ordering = ["-datum"]

    def __str__(self):
        return self.name

    @classmethod
    def aktuelles(cls, nur_oeffentliche=False):
        """Das nächste anstehende Turnier, sonst das zuletzt gelaufene.
        Öffentliche Seiten fragen mit nur_oeffentliche=True, die Orga sieht alle."""
        turniere = cls.objects.filter(oeffentlich=True) if nur_oeffentliche else cls.objects.all()
        heute = timezone.localdate()
        return turniere.filter(datum__gte=heute).order_by("datum").first() or turniere.first()

    @property
    def feld_name(self):
        """"Feld", "Tisch" oder "Platz"."""
        return self.get_feldart_display()

    @property
    def felder_text(self):
        """z. B. "2 Felder" oder "1 Tisch"."""
        n = self.anzahl_felder
        return f"{n} {self.feld_name if n == 1 else self.FELD_MEHRZAHL[self.feldart]}"

    @property
    def zaehlweise_kurz(self):
        """Für Kopfzeilen, z. B. "Best of 3", "Punkte-Modus" oder "10 Becher"."""
        if self.zaehlmodus == self.Zaehlmodus.SAETZE:
            return self.get_gewinnsaetze_display()
        if self.zaehlmodus == self.Zaehlmodus.BECHER:
            return f"{self.becher} Becher"
        return "Punkte-Modus"

    @property
    def vorbei(self):
        return self.datum < timezone.localdate()

    @property
    def meldeschluss_vorbei(self):
        return timezone.now() >= self.meldeschluss

    @property
    def anmeldung_moeglich(self):
        return self.anmeldung_offen and not self.meldeschluss_vorbei

    @property
    def tage_bis_meldeschluss(self):
        return max((timezone.localtime(self.meldeschluss).date() - timezone.localdate()).days, 0)

    @property
    def belegte_plaetze(self):
        return self.teams.filter(status__in=Team.STARTPLATZ_STATUS).count()

    @property
    def freie_plaetze(self):
        return max(self.max_teams - self.belegte_plaetze, 0)

    @property
    def kostenlos(self):
        """Ohne Startgebühr: Teams mit Startplatz sind sofort bestätigt, Zahlungsteile werden ausgeblendet."""
        return not self.startgebuehr_eur

    def unbezahlte_teams(self):
        """Teams mit Startplatz, deren Startgebühr noch fehlt – in Anmelde-Reihenfolge (ohne Gebühr keine)."""
        if self.kostenlos:
            return self.teams.none()
        return self.teams.filter(status__in=Team.STARTPLATZ_STATUS, bezahlt=False).order_by(*Team.REIHENFOLGE)

    @property
    def warteliste_anzahl(self):
        return self.teams.filter(status=Team.Status.WARTELISTE).count()

    @property
    def neue_auf_warteliste(self):
        """Neue Anmeldungen stellen sich hinten an, solange alle Plätze belegt sind oder schon jemand wartet."""
        return self.freie_plaetze == 0 or self.warteliste_anzahl > 0

    @property
    def gebuehr_einheit(self):
        """„pro Person“ oder „pro Team“ – für Startseite und Anmeldung."""
        return "pro Person" if self.gebuehr_pro_person else "pro Team"

    def zahlungsuebersicht(self):
        """Kennzahlen für die Orga (Screen 06). Erwartet wird die Gebühr aller Teams mit Startplatz."""
        teams = list(self.teams.only("status", "bezahlt", "turnier").annotate(_anzahl_spieler=models.Count("spieler")))
        startplatz = [t for t in teams if t.hat_startplatz]
        bezahlt = [t for t in teams if t.bezahlt]
        return {
            "eingegangen": sum((t.startgebuehr for t in bezahlt), Decimal(0)),
            "erwartet": sum((t.startgebuehr for t in startplatz), Decimal(0)),
            "unbezahlt": 0 if self.kostenlos else sum(1 for t in startplatz if not t.bezahlt),
            "warteliste": sum(1 for t in teams if t.status == Team.Status.WARTELISTE),
        }

    def teamdaten_loeschen(self):
        """Datenschutz: Spieler, Kapitänsdaten und Notizen löschen, Bearbeitungslinks ungültig machen.
        Auch das Änderungsprotokoll des Admins zu diesen Teams und Spielern (enthält Namen) wird gelöscht.
        Teamnamen und Ergebnisse bleiben."""
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType

        spieler = Spieler.objects.filter(team__turnier=self)
        for model, ids in [(Team, self.teams.values_list("pk", flat=True)), (Spieler, spieler.values_list("pk", flat=True))]:
            LogEntry.objects.filter(
                content_type=ContentType.objects.get_for_model(model), object_id__in=[str(pk) for pk in ids],
            ).delete()
        spieler.delete()
        for team in self.teams.all():
            Team.objects.filter(pk=team.pk).update(
                kapitaen_name="", kapitaen_email="", notiz="", edit_token=neuer_edit_token(),
            )
        self.teamdaten_geloescht_am = timezone.localdate()
        self.save(update_fields=["teamdaten_geloescht_am"])

    def clean(self):
        if self.paypal_link:
            teile = urlsplit(self.paypal_link)
            if teile.scheme != "https" or (teile.hostname or "").removeprefix("www.") not in PAYPAL_HOSTS:
                raise ValidationError({"paypal_link": "Bitte einen PayPal-Link (https://paypal.me/… oder https://www.paypal.com/…)."})
        pflicht = self.pflicht_spieler or 1
        if self.min_spieler is not None and self.min_spieler < pflicht:
            raise ValidationError({"min_spieler": f"Mindestens {pflicht} – so viele Spieler sind Pflicht."})
        if self.max_spieler is not None and self.max_spieler < pflicht:
            raise ValidationError({"max_spieler": f"Mindestens {pflicht} – so viele Spieler sind Pflicht."})
        if self.min_spieler is not None and self.max_spieler is not None and self.min_spieler > self.max_spieler:
            raise ValidationError({"max_spieler": "Muss mindestens so groß sein wie die empfohlene Spielerzahl."})
        if self.pk and self.zaehlmodus == self.Zaehlmodus.BECHER and self.becher:
            # Sonst rechnet die Tabelle mit negativen getroffenen Bechern.
            zu_viele = self.spiele.filter(
                models.Q(punkte_a__gt=self.becher) | models.Q(punkte_b__gt=self.becher), status="beendet",
            ).first()
            if zu_viele:
                raise ValidationError({"becher": (
                    f"Das Spiel {zu_viele} hat schon mehr als {self.becher} übrige Becher eingetragen – "
                    "erst das Ergebnis korrigieren."
                )})


class Gruppe(models.Model):
    turnier = models.ForeignKey(Turnier, on_delete=models.CASCADE, related_name="gruppen")
    name = models.CharField(max_length=20, help_text="z. B. A, B, …")

    class Meta:
        verbose_name = "Gruppe"
        verbose_name_plural = "Gruppen"
        ordering = ["turnier", "name"]
        constraints = [
            models.UniqueConstraint(fields=["turnier", "name"], name="gruppe_name_eindeutig_pro_turnier"),
        ]

    def __str__(self):
        return f"Gruppe {self.name}"


class TeamQuerySet(models.QuerySet):
    def im_spielplan(self):
        """Nur bestätigte und bezahlte Teams kommen in den Spielplan (ohne Startgebühr: alle bestätigten)."""
        return self.filter(status=Team.Status.BESTAETIGT).filter(
            models.Q(bezahlt=True) | models.Q(turnier__startgebuehr_eur=0),
        )


class Team(models.Model):
    class Status(models.TextChoices):
        ANGEMELDET = "angemeldet", "Angemeldet"
        BESTAETIGT = "bestaetigt", "Bestätigt"
        WARTELISTE = "warteliste", "Warteliste"
        ABGESAGT = "abgesagt", "Abgesagt"

    class Zahlungsart(models.TextChoices):
        BAR = "bar", "Bar"
        UEBERWEISUNG = "ueberweisung", "Überweisung"
        PAYPAL = "paypal", "PayPal"

    turnier = models.ForeignKey(Turnier, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField("Teamname", max_length=100)
    # Leer nur nach dem Löschen der Teamdaten (Datenschutz); im Anmeldeformular Pflicht.
    kapitaen_name = models.CharField("Kapitän", max_length=100, blank=True)
    kapitaen_email = models.EmailField("E-Mail Kapitän", blank=True)
    edit_token = models.CharField(max_length=64, unique=True, default=neuer_edit_token, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ANGEMELDET)
    bezahlt = models.BooleanField(default=False)
    bezahlt_am = models.DateField("bezahlt am", null=True, blank=True)
    zahlungsart = models.CharField(max_length=20, choices=Zahlungsart.choices, blank=True)
    notiz = models.TextField(blank=True)
    gruppe = models.ForeignKey(Gruppe, on_delete=models.SET_NULL, null=True, blank=True, related_name="teams")
    angemeldet_am = models.DateTimeField("angemeldet am", auto_now_add=True)

    # Teams mit diesem Status belegen einen der max_teams Plätze.
    STARTPLATZ_STATUS = [Status.ANGEMELDET, Status.BESTAETIGT]
    # Wer zuerst kommt: Anmeldezeit, bei gleicher Zeit (z. B. Altdaten) die laufende Nummer
    REIHENFOLGE = ["angemeldet_am", "pk"]

    objects = TeamQuerySet.as_manager()

    class Meta:
        verbose_name = "Team"
        verbose_name_plural = "Teams"
        ordering = ["turnier", "name"]
        constraints = [
            models.UniqueConstraint(fields=["turnier", "name"], name="teamname_eindeutig_pro_turnier"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Bezahlt heißt bestätigt (Entscheidung Orga) – ohne Startgebühr ist ein Startplatz sofort bestätigt.
        # Warteliste und Absage bleiben unberührt.
        self.bezahlt_am = (self.bezahlt_am or timezone.localdate()) if self.bezahlt else None
        if self.bezahlt or self.turnier.kostenlos:
            if self.status == self.Status.ANGEMELDET:
                self.status = self.Status.BESTAETIGT
        elif self.status == self.Status.BESTAETIGT:
            self.status = self.Status.ANGEMELDET
        super().save(*args, **kwargs)

    @property
    def hat_startplatz(self):
        return self.status in self.STARTPLATZ_STATUS

    @property
    def anzahl_spieler(self):
        anzahl = getattr(self, "_anzahl_spieler", None)  # aus .annotate(), spart Abfragen in Listen
        return self.spieler.count() if anzahl is None else anzahl

    @property
    def startgebuehr(self):
        """Betrag, den dieses Team zahlt: pro Team fest, pro Person × eingetragene Spieler (aktueller Stand)."""
        gebuehr = self.turnier.startgebuehr_eur
        return gebuehr * self.anzahl_spieler if self.turnier.gebuehr_pro_person else gebuehr

    @property
    def paypal_url(self):
        """PayPal-Link des Turniers; bei paypal.me/<name> mit dem Betrag des Teams („…/20EUR“, „…/7.50EUR“)."""
        link = self.turnier.paypal_link
        if not link:
            return ""
        teile = urlsplit(link)
        pfad = [t for t in teile.path.split("/") if t]
        if (teile.hostname or "").removeprefix("www.") == "paypal.me" and len(pfad) == 1 and self.startgebuehr > 0:
            betrag = f"{self.startgebuehr:.2f}".removesuffix(".00")
            return f"https://paypal.me/{pfad[0]}/{betrag}EUR"
        return link

    @property
    def startgebuehr_text(self):
        """„20 €“ bzw. „20 € (4 × 5 € pro Person)“ – für Kapitänsseite und Mails."""
        betrag = f"{_euro(self.startgebuehr)} €"
        if self.turnier.gebuehr_pro_person:
            betrag += f" ({self.anzahl_spieler} × {_euro(self.turnier.startgebuehr_eur)} € pro Person)"
        return betrag

    @property
    def startplatz_nr(self):
        """Laufende Nummer unter den Teams mit Startplatz (in Anmelde-Reihenfolge)."""
        if not self.hat_startplatz:
            return None
        return self._vor_mir().filter(status__in=self.STARTPLATZ_STATUS).count() + 1

    @property
    def wartelisten_platz(self):
        """Platz auf der Warteliste (1 = rückt als Nächstes nach), sonst None."""
        if self.status != self.Status.WARTELISTE:
            return None
        return self._vor_mir().filter(status=self.Status.WARTELISTE).count() + 1

    def _vor_mir(self):
        """Teams desselben Turniers, die sich früher angemeldet haben."""
        return Team.objects.filter(turnier_id=self.turnier_id).filter(
            models.Q(angemeldet_am__lt=self.angemeldet_am) | models.Q(angemeldet_am=self.angemeldet_am, pk__lt=self.pk)
        )

    def clean(self):
        if self.gruppe_id and self.turnier_id and self.gruppe.turnier_id != self.turnier_id:
            raise ValidationError({"gruppe": "Die Gruppe gehört zu einem anderen Turnier."})


class Spieler(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="spieler")
    vorname = models.CharField(max_length=100)
    nachname = models.CharField(max_length=100)
    studiengang = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Spieler"
        verbose_name_plural = "Spieler"
        ordering = ["team", "nachname", "vorname"]

    def __str__(self):
        return f"{self.vorname} {self.nachname}"


class Spiel(models.Model):
    class Status(models.TextChoices):
        GEPLANT = "geplant", "Geplant"
        BEENDET = "beendet", "Beendet"

    class Phase(models.TextChoices):
        GRUPPE = "gruppe", "Gruppenspiel"
        VIERTELFINALE = "viertelfinale", "Viertelfinale"
        HALBFINALE = "halbfinale", "Halbfinale"
        PLATZ_3 = "platz_3", "Spiel um Platz 3"
        FINALE = "finale", "Finale"

    turnier = models.ForeignKey(Turnier, on_delete=models.CASCADE, related_name="spiele")
    gruppe = models.ForeignKey(
        Gruppe, on_delete=models.CASCADE, null=True, blank=True, related_name="spiele",
        help_text="Leer bei K.-o.-Spielen.",
    )
    phase = models.CharField(max_length=20, choices=Phase.choices, default=Phase.GRUPPE)
    runde = models.PositiveSmallIntegerField(default=1)
    feld = models.PositiveSmallIntegerField(default=1)
    uhrzeit = models.TimeField(null=True, blank=True)
    # Wird ein Team gelöscht, bleibt das Spiel ohne Team stehen (Umplanen: siehe CLAUDE.md).
    team_a = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Team A",
    )
    team_b = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Team B",
    )
    # Für K.-o.-Spiele, solange die Teams noch nicht feststehen, z. B. "1. Gruppe B".
    platzhalter_a = models.CharField("Platzhalter A", max_length=50, blank=True)
    platzhalter_b = models.CharField("Platzhalter B", max_length=50, blank=True)
    saetze_a = models.PositiveSmallIntegerField("Sätze A", null=True, blank=True)
    saetze_b = models.PositiveSmallIntegerField("Sätze B", null=True, blank=True)
    # Satz-Modus: Ballpunkte gesamt (optional). Punkte-Modus: Punkte des einen Satzes.
    punkte_a = models.PositiveSmallIntegerField("Punkte A", null=True, blank=True)
    punkte_b = models.PositiveSmallIntegerField("Punkte B", null=True, blank=True)
    schiri_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Schiri",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.GEPLANT)

    class Meta:
        verbose_name = "Spiel"
        verbose_name_plural = "Spiele"
        ordering = ["turnier", "uhrzeit", "feld"]

    def __str__(self):
        a = self.team_a or self.platzhalter_a or "?"
        b = self.team_b or self.platzhalter_b or "?"
        return f"{a} – {b}"

    @property
    def sieger(self):
        """Siegerteam eines beendeten Spiels, sonst None."""
        if self.status != self.Status.BEENDET:
            return None
        if self.turnier.zaehlmodus == Turnier.Zaehlmodus.SAETZE:
            a, b = self.saetze_a, self.saetze_b
        else:
            a, b = self.punkte_a, self.punkte_b
        if a is None or b is None or a == b:
            return None
        return self.team_a if a > b else self.team_b

    def clean(self):
        fehler = {}
        teams = [t for t in (self.team_a, self.team_b, self.schiri_team) if t]
        if any(t.turnier_id != self.turnier_id for t in teams):
            fehler["__all__"] = "Alle Teams müssen zum Turnier des Spiels gehören."
        if self.team_a_id and self.team_a_id == self.team_b_id:
            fehler["team_b"] = "Ein Team kann nicht gegen sich selbst spielen."
        if self.schiri_team_id and self.schiri_team_id in (self.team_a_id, self.team_b_id):
            fehler["schiri_team"] = "Das Schiri-Team darf nicht selbst spielen."
        if self.gruppe_id and self.gruppe.turnier_id != self.turnier_id:
            fehler["gruppe"] = "Die Gruppe gehört zu einem anderen Turnier."
        if self.gruppe_id and self.phase != self.Phase.GRUPPE:
            fehler["gruppe"] = "K.-o.-Spiele gehören zu keiner Gruppe."
        if self.status == self.Status.BEENDET and not fehler:
            fehler.update(self._ergebnis_fehler())
        if fehler:
            raise ValidationError(fehler)

    def _ergebnis_fehler(self):
        if not (self.team_a_id and self.team_b_id):
            return {"status": "Ein beendetes Spiel braucht beide Teams."}
        if self.turnier.zaehlmodus == Turnier.Zaehlmodus.SAETZE:
            ziel = self.turnier.gewinnsaetze
            a, b = self.saetze_a, self.saetze_b
            if a is None or b is None:
                return {"saetze_a": "Bitte die Sätze beider Teams eintragen."}
            if max(a, b) != ziel or min(a, b) >= ziel:
                return {"saetze_a": f"Genau ein Team muss {ziel} Sätze gewinnen."}
        else:
            a, b = self.punkte_a, self.punkte_b
            if a is None or b is None:
                if self.turnier.zaehlmodus == Turnier.Zaehlmodus.BECHER:
                    return {"punkte_a": "Bitte für beide Teams wählen, wie viele Becher noch stehen."}
                return {"punkte_a": "Bitte die Punkte beider Teams eintragen."}
            if self.turnier.zaehlmodus == Turnier.Zaehlmodus.BECHER:
                if max(a, b) > self.turnier.becher:
                    return {"punkte_a": f"Es gibt nur {self.turnier.becher} Becher pro Team."}
                if a == b:
                    return {"punkte_a": "Gleichstand gibt es nicht – bitte Verlängerung spielen und das Ergebnis eintragen."}
            if a == b:
                return {"punkte_a": "Im Punkte-Modus gibt es kein Unentschieden."}
        return {}


# ---------------------------------------------------------------------------------------------------------------
# Orga-Konten: Einladungen und Profil (Telefon). Rollen sind Django-Gruppen, siehe tournament/rollen.py.

EINLADUNG_GUELTIG_TAGE = 7


def _einladung_ablauf():
    return timezone.now() + timedelta(days=EINLADUNG_GUELTIG_TAGE)


class Einladung(models.Model):
    """Einmal-Link zum Anlegen eines Orga-Kontos mit fester Rolle – per Mail verschickt oder selbst geteilt."""
    token = models.CharField(max_length=64, unique=True, default=neuer_edit_token, editable=False)
    rolle = models.ForeignKey("auth.Group", on_delete=models.CASCADE, related_name="einladungen")
    email = models.EmailField("E-Mail", blank=True, help_text="Leer = Link wird selbst geteilt (z. B. per Messenger).")
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    gueltig_bis = models.DateTimeField(default=_einladung_ablauf)
    angenommen_von = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name="einladung")

    class Meta:
        verbose_name = "Einladung"
        verbose_name_plural = "Einladungen"
        ordering = ["-erstellt_am"]

    def __str__(self):
        return f"Einladung als {self.rolle} ({self.email or 'Link'})"

    @property
    def offen(self):
        """Noch nicht benutzt und nicht abgelaufen."""
        return self.angenommen_von_id is None and self.gueltig_bis > timezone.now()


class OrgaProfil(models.Model):
    """Zusätzliche Angaben zu einem Orga-Konto (nur für die Orga sichtbar)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orga_profil")
    telefon = models.CharField("Telefon", max_length=30, blank=True)

    class Meta:
        verbose_name = "Orga-Profil"
        verbose_name_plural = "Orga-Profile"

    def __str__(self):
        return str(self.user)
