from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    # Ein Login für alle: der Admin schickt zum Orga-Login (danach Orga-Übersicht statt „keine Berechtigung“)
    path("admin/login/", RedirectView.as_view(pattern_name="orga_login", query_string=True)),
    path("admin/", admin.site.urls),
    path("", include("tournament.urls")),
]
