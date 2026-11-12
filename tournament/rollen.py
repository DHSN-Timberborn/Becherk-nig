"""Rollen für Orga-Konten: wenige fertige Bausteine statt Djangos langer Rechteliste.

Eine Rolle ist eine Django-Gruppe. Jeder Baustein steht für eine feste Menge Django-Rechte; ansehen dürfen alle
Orga-Konten immer (ANSEHEN). Ein Baustein gilt als gewählt, wenn die Gruppe alle seine Rechte hat.
"""

from django.contrib.auth.models import Permission
from django.db.models import Q

# Ansehen dürfen alle Orga-Konten (Admin-Listen, Orga-Seiten)
ANSEHEN = [
    "tournament.view_turnier", "tournament.view_team", "tournament.view_spieler",
    "tournament.view_spiel", "tournament.view_gruppe",
]

# Schlüssel: (Titel, Beschreibung, Rechte)
BAUSTEINE = {
    "turniere": (
        "Turniere & Einstellungen",
        "Turniere anlegen, ändern und löschen – Startgebühr, PayPal-Link, Anmeldung, Sichtbarkeit.",
        ["tournament.add_turnier", "tournament.change_turnier", "tournament.delete_turnier"],
    ),
    "teams": (
        "Teams & Zahlungen",
        "Teams und Spieler bearbeiten, „bezahlt“ setzen, Warteliste, CSV-Export, Teamdaten löschen.",
        ["tournament.add_team", "tournament.change_team", "tournament.delete_team",
         "tournament.add_spieler", "tournament.change_spieler", "tournament.delete_spieler"],
    ),
    "spielplan": (
        "Spielplan & Ergebnisse",
        "Spielplan erzeugen, Spiele verschieben, veröffentlichen und Ergebnisse eintragen.",
        ["tournament.add_spiel", "tournament.change_spiel", "tournament.delete_spiel",
         "tournament.add_gruppe", "tournament.change_gruppe", "tournament.delete_gruppe"],
    ),
    "benutzer": (
        "Benutzer & Rollen",
        "Rollen anlegen und ändern, Leute einladen, Konten sperren. Wer das darf, kann sich jede Rolle geben.",
        ["auth.view_user", "auth.change_user", "auth.view_group", "auth.add_group", "auth.change_group",
         "auth.delete_group"],
    ),
}

# Prüfen, ob jemand etwas darf: ein Recht pro Baustein reicht
LEITRECHT = {
    "turniere": "tournament.change_turnier",
    "teams": "tournament.change_team",
    "spielplan": "tournament.change_spiel",
    "benutzer": "auth.change_user",
}


def _permissions(namen):
    bedingung = Q(pk__in=[])
    for name in namen:
        app, codename = name.split(".")
        bedingung |= Q(content_type__app_label=app, codename=codename)
    return Permission.objects.filter(bedingung)


def rechte_setzen(gruppe, bausteine):
    """Rechte der Rolle genau auf ANSEHEN + die gewählten Bausteine setzen."""
    namen = list(ANSEHEN)
    for schluessel in bausteine:
        namen += BAUSTEINE[schluessel][2]
    gruppe.permissions.set(_permissions(namen))


def bausteine_von(gruppe):
    """Schlüssel der Bausteine, deren Rechte die Rolle alle hat."""
    vorhanden = {f"{p.content_type.app_label}.{p.codename}" for p in gruppe.permissions.select_related("content_type")}
    return [s for s, (_, _, rechte) in BAUSTEINE.items() if set(rechte) <= vorhanden]


def darf(user, baustein):
    return user.is_active and user.has_perm(LEITRECHT[baustein])
