from django.apps import AppConfig
from django.conf import settings


class TournamentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tournament'
    # Überschrift im Admin – Ableger wie Becherkönig heißen dort so wie in config/marke.py
    verbose_name = settings.MARKE
