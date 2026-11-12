from django.contrib.auth.views import LogoutView
from django.urls import path

from . import konten, orga, views

urlpatterns = [
    path("", views.startseite, name="startseite"),
    path("turniere/", views.turniere, name="turniere"),
    path("teams/", views.teamliste, name="teamliste"),
    path("spielplan/", views.spielplan, name="spielplan"),
    path("tabelle/", views.tabelle, name="tabelle"),
    path("beamer/", views.beamer, name="beamer"),
    path("anmelden/", views.anmelden, name="anmelden"),
    path("datenschutz/", views.datenschutz, name="datenschutz"),
    path("team/<str:token>/", views.team_bearbeiten, name="team_bearbeiten"),
    path("team/<str:token>/angemeldet/", views.team_angemeldet, name="team_angemeldet"),
    path("team/<str:token>/abmelden/", views.team_abmelden, name="team_abmelden"),
    path("orga/", konten.uebersicht, name="orga_uebersicht"),
    path("orga/login/", konten.OrgaLogin.as_view(), name="orga_login"),
    path("orga/logout/", LogoutView.as_view(next_page="startseite"), name="orga_logout"),
    path("orga/rollen/", konten.rollen_liste, name="orga_rollen"),
    path("orga/rollen/neu/", konten.rolle_bearbeiten, name="orga_rolle_neu"),
    path("orga/rollen/<int:pk>/", konten.rolle_bearbeiten, name="orga_rolle"),
    path("orga/rollen/<int:pk>/loeschen/", konten.rolle_loeschen, name="orga_rolle_loeschen"),
    path("orga/benutzer/", konten.benutzer_liste, name="orga_benutzer"),
    path("orga/benutzer/<int:pk>/", konten.benutzer_bearbeiten, name="orga_benutzer_bearbeiten"),
    path("orga/benutzer/einladen/", konten.einladen, name="orga_einladen"),
    path("orga/einladung/<int:pk>/", konten.einladung_zeigen, name="orga_einladung"),
    path("orga/einladung/<int:pk>/zurueckziehen/", konten.einladung_widerrufen, name="orga_einladung_widerrufen"),
    path("einladung/<str:token>/", konten.einladung_annehmen, name="einladung_annehmen"),
    path("orga/benutzer/<int:pk>/zugangslink/", konten.zugangslink, name="orga_zugangslink"),
    path("passwort/<uidb64>/<token>/", konten.PasswortNeu.as_view(), name="orga_passwort_neu"),
    path("orga/spielplan/", orga.spielplan_seite, name="orga_spielplan"),
    path("orga/spielplan/druck/", orga.spielplan_druck, name="orga_spielplan_druck"),
    path("orga/spiel/<int:pk>/", orga.ergebnis_seite, name="orga_ergebnis"),
]
