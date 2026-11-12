"""Orga-Konten: eigener Login, Orga-Übersicht, Rollen (Bausteine per Checkbox), Benutzer und Einladungen.

Rollen sind Django-Gruppen (tournament/rollen.py). Neue Konten entstehen nur über Einladungen: per Mail oder als Link
zum selbst Teilen. Wer eingeladen wird, legt Name, E-Mail, optional Telefon und Passwort selbst fest.
"""

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, password_validation
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST

from . import rollen
from .models import EINLADUNG_GUELTIG_TAGE, Einladung, OrgaProfil, Turnier

User = get_user_model()

# Orga-Seiten: angemeldet und Orga-Konto (is_staff). Sonst zum Orga-Login statt zum Admin-Login.
orga_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url="orga_login")


def _nur_mit(baustein):
    """Seite nur für Konten mit diesem Baustein (Superuser dürfen alles)."""
    def dekorator(view):
        @orga_required
        def gepruefte_view(request, *args, **kwargs):
            if not rollen.darf(request.user, baustein):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return gepruefte_view
    return dekorator


# --------------------------------------------------------------------------------------------- Login und Übersicht

class OrgaLoginForm(AuthenticationForm):
    """Anmeldung mit E-Mail (eingeladene Konten) oder Benutzername (z. B. der erste Zugang aus install.sh)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "E-Mail oder Benutzername"

    def clean_username(self):
        name = self.cleaned_data["username"].strip()
        return name.lower() if "@" in name else name  # Konten aus Einladungen heißen wie ihre E-Mail (klein)


class OrgaLogin(LoginView):
    template_name = "tournament/konten/login.html"
    authentication_form = OrgaLoginForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return reverse("orga_uebersicht")


@orga_required
def uebersicht(request):
    u = request.user
    return render(request, "tournament/konten/uebersicht.html", {
        "turnier": Turnier.aktuelles(),
        "darf": {schluessel: rollen.darf(u, schluessel) for schluessel in rollen.BAUSTEINE},
        "rolle": ", ".join(g.name for g in u.groups.all()) or ("Superuser" if u.is_superuser else "ohne Rolle"),
    })


# ------------------------------------------------------------------------------------------------------- Rollen

class RolleForm(forms.Form):
    name = forms.CharField(label="Name der Rolle", max_length=150,
                           help_text="z. B. „Kasse“, „Turnierleitung“, „Helfer am Tisch“")
    bausteine = forms.MultipleChoiceField(
        label="Was darf diese Rolle?", required=False, widget=forms.CheckboxSelectMultiple,
        choices=[(s, titel) for s, (titel, _, _) in rollen.BAUSTEINE.items()],
    )

    def __init__(self, *args, gruppe=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.gruppe = gruppe

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        andere = Group.objects.filter(name__iexact=name)
        if self.gruppe:
            andere = andere.exclude(pk=self.gruppe.pk)
        if andere.exists():
            raise ValidationError("Eine Rolle mit diesem Namen gibt es schon.")
        return name


@_nur_mit("benutzer")
def rollen_liste(request):
    gruppen = Group.objects.order_by("name").prefetch_related("permissions__content_type")
    return render(request, "tournament/konten/rollen.html", {
        "rollen": [(g, [rollen.BAUSTEINE[s][0] for s in rollen.bausteine_von(g)], g.user_set.count()) for g in gruppen],
    })


@_nur_mit("benutzer")
def rolle_bearbeiten(request, pk=None):
    gruppe = get_object_or_404(Group, pk=pk) if pk else None
    initial = {"name": gruppe.name, "bausteine": rollen.bausteine_von(gruppe)} if gruppe else {}
    form = RolleForm(request.POST or None, initial=initial, gruppe=gruppe)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            gruppe = gruppe or Group()
            gruppe.name = form.cleaned_data["name"]
            gruppe.save()
            rollen.rechte_setzen(gruppe, form.cleaned_data["bausteine"])
        messages.success(request, f"Rolle „{gruppe.name}“ gespeichert.")
        return redirect("orga_rollen")
    return render(request, "tournament/konten/rolle_form.html", {
        "form": form, "gruppe": gruppe,
        "bausteine": [(s, titel, text) for s, (titel, text, _) in rollen.BAUSTEINE.items()],
        "gewaehlt": form["bausteine"].value() or [],
    })


@require_POST
@_nur_mit("benutzer")
def rolle_loeschen(request, pk):
    gruppe = get_object_or_404(Group, pk=pk)
    if gruppe.user_set.exists():
        messages.error(request, f"„{gruppe.name}“ hat noch Mitglieder – erst ihnen eine andere Rolle geben.")
    else:
        gruppe.delete()
        messages.success(request, f"Rolle „{gruppe.name}“ gelöscht.")
    return redirect("orga_rollen")


# ----------------------------------------------------------------------------------------------------- Benutzer

class BenutzerForm(forms.Form):
    rolle = forms.ModelChoiceField(label="Rolle", queryset=Group.objects.order_by("name"), widget=forms.RadioSelect,
                                   empty_label=None)
    aktiv = forms.BooleanField(label="Konto aktiv (kann sich anmelden)", required=False)


@_nur_mit("benutzer")
def benutzer_liste(request):
    konten = User.objects.filter(is_staff=True).order_by("-is_active", "first_name", "last_name", "email") \
        .prefetch_related("groups").select_related("orga_profil")
    einladungen = [e for e in Einladung.objects.select_related("rolle").filter(angenommen_von=None) if e.offen]
    for e in einladungen:
        e.link = request.build_absolute_uri(reverse("einladung_annehmen", args=[e.token]))
    return render(request, "tournament/konten/benutzer.html", {"konten": konten, "einladungen": einladungen})


@_nur_mit("benutzer")
def benutzer_bearbeiten(request, pk):
    konto = get_object_or_404(User, pk=pk, is_staff=True)
    if konto.is_superuser and not request.user.is_superuser:
        raise PermissionDenied  # Superuser ändern nur Superuser
    form = BenutzerForm(request.POST or None, initial={"rolle": konto.groups.first(), "aktiv": konto.is_active})
    if request.method == "POST" and form.is_valid():
        if konto == request.user and not form.cleaned_data["aktiv"]:
            form.add_error("aktiv", "Das eigene Konto kann man nicht sperren.")
        else:
            konto.groups.set([form.cleaned_data["rolle"]])
            konto.is_active = form.cleaned_data["aktiv"]
            konto.save(update_fields=["is_active"])
            messages.success(request, f"{konto.get_full_name() or konto.email} gespeichert.")
            return redirect("orga_benutzer")
    return render(request, "tournament/konten/benutzer_form.html", {"form": form, "konto": konto})


@require_POST
@_nur_mit("benutzer")
def zugangslink(request, pk):
    """„Passwort vergessen“: Einmal-Link zum Setzen eines neuen Passworts – zum selbst Weiterschicken, ohne SMTP.
    Djangos Passwort-Token: verfällt nach PASSWORD_RESET_TIMEOUT und sobald das Passwort geändert wurde."""
    konto = get_object_or_404(User, pk=pk, is_staff=True)
    if konto.is_superuser and not request.user.is_superuser:
        raise PermissionDenied
    link = request.build_absolute_uri(reverse("orga_passwort_neu", kwargs={
        "uidb64": urlsafe_base64_encode(force_bytes(konto.pk)), "token": default_token_generator.make_token(konto),
    }))
    return render(request, "tournament/konten/zugangslink.html", {
        "konto": konto, "link": link, "tage": settings.PASSWORD_RESET_TIMEOUT // 86400,
    })


class PasswortNeu(PasswordResetConfirmView):
    template_name = "tournament/konten/passwort_neu.html"
    post_reset_login = True
    post_reset_login_backend = "django.contrib.auth.backends.ModelBackend"
    success_url = reverse_lazy("orga_uebersicht")

    def form_valid(self, form):
        messages.success(self.request, "Neues Passwort gespeichert – du bist angemeldet.")
        return super().form_valid(form)


class EinladenForm(forms.Form):
    rolle = forms.ModelChoiceField(label="Rolle", queryset=Group.objects.order_by("name"), widget=forms.RadioSelect,
                                   empty_label=None)
    weg = forms.ChoiceField(label="Wie soll die Einladung ankommen?", widget=forms.RadioSelect, initial="link", choices=[
        ("link", "Link selbst teilen – z. B. per WhatsApp oder Signal"),
        ("mail", "Per E-Mail schicken"),
    ])
    email = forms.EmailField(label="E-Mail-Adresse", required=False)

    def clean(self):
        daten = super().clean()
        if daten.get("weg") == "mail":
            email = (daten.get("email") or "").strip().lower()
            if not email:
                self.add_error("email", "Bitte die E-Mail-Adresse angeben.")
            elif User.objects.filter(email__iexact=email).exists():
                self.add_error("email", "Mit dieser E-Mail-Adresse gibt es schon ein Konto.")
            daten["email"] = email
        else:
            daten["email"] = ""
        return daten


@_nur_mit("benutzer")
def einladen(request):
    if not Group.objects.exists():
        messages.warning(request, "Lege zuerst eine Rolle an – jede Einladung gehört zu einer Rolle.")
        return redirect("orga_rolle_neu")
    form = EinladenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        einladung = Einladung.objects.create(rolle=form.cleaned_data["rolle"], email=form.cleaned_data["email"],
                                             erstellt_von=request.user)
        link = request.build_absolute_uri(reverse("einladung_annehmen", args=[einladung.token]))
        if einladung.email:
            text = render_to_string("mail/einladung.txt", {
                "einladung": einladung, "link": link, "von": request.user, "tage": EINLADUNG_GUELTIG_TAGE,
                "marke": settings.MARKE,
            })
            send_mail("Einladung ins Orga-Team", text, None, [einladung.email])
        # Weiterleiten, damit Neuladen keine zweite Einladung erzeugt
        return redirect("orga_einladung", pk=einladung.pk)
    return render(request, "tournament/konten/einladen.html", {"form": form, "tage": EINLADUNG_GUELTIG_TAGE})


@_nur_mit("benutzer")
def einladung_zeigen(request, pk):
    """Ergebnis nach dem Einladen: Link zum Kopieren (solange die Einladung offen ist)."""
    einladung = get_object_or_404(Einladung.objects.select_related("rolle"), pk=pk, angenommen_von=None)
    if not einladung.offen:
        messages.info(request, "Diese Einladung ist abgelaufen.")
        return redirect("orga_benutzer")
    return render(request, "tournament/konten/eingeladen.html", {
        "einladung": einladung, "tage": EINLADUNG_GUELTIG_TAGE,
        "link": request.build_absolute_uri(reverse("einladung_annehmen", args=[einladung.token])),
    })


@require_POST
@_nur_mit("benutzer")
def einladung_widerrufen(request, pk):
    einladung = get_object_or_404(Einladung, pk=pk, angenommen_von=None)
    einladung.delete()
    messages.success(request, "Einladung zurückgezogen – der Link funktioniert nicht mehr.")
    return redirect("orga_benutzer")


# ----------------------------------------------------------------------------------- Einladung annehmen (öffentlich)

class KontoForm(forms.Form):
    vorname = forms.CharField(label="Vorname", max_length=150)
    nachname = forms.CharField(label="Nachname", max_length=150)
    email = forms.EmailField(label="E-Mail-Adresse", help_text="Damit meldest du dich später an.")
    telefon = forms.CharField(label="Telefon (optional)", max_length=30, required=False,
                              help_text="Nur für die Orga sichtbar, z. B. für Rückfragen am Turniertag.")
    passwort1 = forms.CharField(label="Passwort", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    passwort2 = forms.CharField(label="Passwort wiederholen", strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, einladung, **kwargs):
        super().__init__(*args, **kwargs)
        self.einladung = einladung
        if einladung.email:  # per Mail eingeladen: Adresse steht fest
            self.fields["email"].initial = einladung.email
            self.fields["email"].disabled = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise ValidationError("Mit dieser E-Mail-Adresse gibt es schon ein Konto.")
        return email

    def clean(self):
        daten = super().clean()
        p1, p2 = daten.get("passwort1"), daten.get("passwort2")
        if p1 and p2 and p1 != p2:
            self.add_error("passwort2", "Die beiden Passwörter stimmen nicht überein.")
        elif p1 and daten.get("email"):
            probe = User(username=daten["email"], email=daten["email"], first_name=daten.get("vorname", ""),
                         last_name=daten.get("nachname", ""))
            try:
                password_validation.validate_password(p1, probe)
            except ValidationError as fehler:
                self.add_error("passwort1", fehler)
        return daten


def einladung_annehmen(request, token):
    einladung = Einladung.objects.select_related("rolle").filter(token=token).first()
    if not einladung or not einladung.offen:
        return render(request, "tournament/konten/einladung_ungueltig.html", status=410 if einladung else 404)
    if request.user.is_authenticated:
        return render(request, "tournament/konten/einladung_ungueltig.html", {"angemeldet": True}, status=409)
    form = KontoForm(request.POST or None, einladung=einladung)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            # Einladung sperren, damit derselbe Link nicht zweimal ein Konto anlegt
            einladung = Einladung.objects.select_for_update().get(pk=einladung.pk)
            if not einladung.offen:
                return render(request, "tournament/konten/einladung_ungueltig.html", status=410)
            konto = User.objects.create_user(username=d["email"], email=d["email"], password=d["passwort1"],
                                             first_name=d["vorname"], last_name=d["nachname"], is_staff=True)
            konto.groups.add(einladung.rolle)
            OrgaProfil.objects.create(user=konto, telefon=d["telefon"])
            einladung.angenommen_von = konto
            einladung.save(update_fields=["angenommen_von"])
        login(request, konto, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Willkommen im Orga-Team, {konto.first_name}! Du bist als „{einladung.rolle}“ angemeldet.")
        return redirect("orga_uebersicht")
    return render(request, "tournament/konten/konto_anlegen.html", {"form": form, "einladung": einladung})
