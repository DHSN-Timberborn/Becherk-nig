#!/usr/bin/env bash
# shellcheck disable=SC1111  # deutsche Anführungszeichen „…“ in Meldungen sind gewollt
# Satzball (optional mit Becherkönig) auf einem frischen Debian/Ubuntu-Server installieren.
#
#   curl -fsSL https://raw.githubusercontent.com/Kootaro05/Satzball/main/install.sh | sudo bash
#
# Fragt alles Nötige in der Konsole ab, schreibt die Konfiguration nach /opt/satzball, startet die Container
# (compose.yaml mit Caddy), legt den Orga-Zugang an und richtet die tägliche Sicherung ein. Details: docs/betrieb.md
#
# Nur für Tests: SATZBALL_ZIEL (Ordner), SATZBALL_QUELLE (Git-Repo), SATZBALL_EINGABE (Antworten aus Datei).
set -euo pipefail

ZIEL=${SATZBALL_ZIEL:-/opt/satzball}
QUELLE=${SATZBALL_QUELLE:-https://github.com/Kootaro05/Satzball.git}
exec 3<"${SATZBALL_EINGABE:-/dev/tty}"

fett() { printf '\n\033[1m%s\033[0m\n' "$*" >&2; }
hinweis() { printf '  %s\n' "$*" >&2; }
fehler() { printf '\n\033[31mFehler: %s\033[0m\n' "$*" >&2; exit 1; }

# frage "Text" [Vorgabe] – gibt die Antwort aus (leer → Vorgabe)
frage() {
  local antwort
  if [ -n "${2:-}" ]; then printf '  %s [%s]: ' "$1" "$2" >&2; else printf '  %s: ' "$1" >&2; fi
  IFS= read -r antwort <&3 || true
  printf '%s' "${antwort:-${2:-}}"
}
pflicht() {
  local antwort=""
  while [ -z "$antwort" ]; do antwort=$(frage "$@"); done
  printf '%s' "$antwort"
}
ja() { [[ $(frage "$1 (j/n)" "$2") =~ ^[jJyY] ]]; }
geheim() {
  local antwort
  printf '  %s: ' "$1" >&2
  IFS= read -rs antwort <&3 || true
  printf '\n' >&2
  printf '%s' "$antwort"
}
# Zeile für eine .env-Datei. Compose liest $ als Variable und " #" als Kommentar – deshalb immer in Anführungszeichen.
env_zeile() {
  local wert=$2
  if [[ $wert != *"'"* ]]; then
    printf "%s='%s'\n" "$1" "$wert"
  else
    wert=${wert//\"/\\\"}
    wert=${wert//\$/\$\$}
    printf '%s="%s"\n' "$1" "$wert"
  fi
}

# ---------------------------------------------------------------------------------------------------------------
[ "$(id -u)" -eq 0 ] || fehler "Bitte mit sudo bzw. als root starten."
command -v apt-get >/dev/null || fehler "Das Skript ist für Debian/Ubuntu gedacht (apt-get fehlt). Siehe docs/betrieb.md."
[ ! -e "$ZIEL/.env" ] || fehler "$ZIEL ist schon eingerichtet. Für ein Update siehe docs/betrieb.md („Update einspielen“)."

fett "Satzball – Installation"
hinweis "Alle Fragen lassen sich später in $ZIEL ändern. Eingabe in [Klammern] = Vorschlag, mit Enter übernehmen."

fett "1/6  Programme"
fehlend=()
command -v git >/dev/null || fehlend+=(git)
command -v curl >/dev/null || fehlend+=(curl)
command -v crontab >/dev/null || fehlend+=(cron)
if [ ${#fehlend[@]} -gt 0 ]; then
  hinweis "Installiere ${fehlend[*]} …"
  apt-get update -qq && apt-get install -y -qq "${fehlend[@]}" >/dev/null
fi
if ! docker compose version >/dev/null 2>&1; then
  hinweis "Installiere Docker (offizielles Skript von get.docker.com) …"
  curl -fsSL https://get.docker.com | sh >/dev/null
fi
hinweis "git, Docker und Compose sind da."

fett "2/6  Apps und Adressen"
mit_becher=nein
ja "Bierpong-Version Becherkönig zusätzlich installieren?" "n" && mit_becher=ja
ip=$(hostname -I 2>/dev/null | awk '{print $1}')
ip=$(pflicht "Öffentliche IP-Adresse dieses Servers" "$ip")
hinweis "Mit Domain gibt es HTTPS automatisch; der DNS-Eintrag (Typ A) muss dafür schon auf $ip zeigen."
hinweis "Ohne Domain (leer lassen) läuft Satzball unter http://$ip/ und Becherkönig unter http://$ip:8080/."
domain_satzball=$(frage "Domain für Satzball, z. B. volleyball.example.de")
domain_becher=""
[ "$mit_becher" = ja ] && domain_becher=$(frage "Domain für Becherkönig, z. B. bierpong.example.de")
for d in $domain_satzball $domain_becher; do
  aufgeloest=$(getent ahostsv4 "$d" | awk 'NR==1 {print $1}' || true)
  if [ "$aufgeloest" != "$ip" ]; then
    hinweis "Achtung: $d zeigt auf „${aufgeloest:-nichts}“, nicht auf $ip – dann klappt das Zertifikat nicht."
    ja "Trotzdem weiter? (Caddy versucht es später automatisch erneut)" "n" || fehler "Abgebrochen. DNS-Eintrag prüfen."
  fi
done

fett "3/6  Verantwortlich (für die Datenschutzerklärung)"
v_name=$(pflicht "Name")
v_strasse=$(pflicht "Straße und Hausnummer")
v_ort=$(pflicht "PLZ und Ort")
v_mail=$(pflicht "E-Mail")

fett "4/6  Mailversand (Bestätigungen mit Bearbeitungslink an die Kapitäne)"
mit_mail=nein
if ja "SMTP-Zugang jetzt eintragen? Ohne landen Mails nur im Log" "j"; then
  mit_mail=ja
  smtp_host=$(pflicht "SMTP-Server, z. B. smtp.example.de")
  smtp_port=$(pflicht "Port" "587")
  smtp_user=$(pflicht "Benutzer bzw. Absender-Adresse")
  smtp_pw=$(geheim "Passwort (wird nicht angezeigt)")
fi

fett "5/6  Orga-Zugang (für /admin/$( [ "$mit_becher" = ja ] && printf ', gilt für beide Apps'))"
orga_name=$(pflicht "Benutzername" "orga")
orga_mail=$(pflicht "E-Mail")
while true; do
  orga_pw=$(geheim "Passwort (mind. 10 Zeichen, wird nicht angezeigt)")
  if [ ${#orga_pw} -lt 10 ]; then hinweis "Zu kurz."; continue; fi
  [ "$(geheim "Passwort wiederholen")" = "$orga_pw" ] && break
  hinweis "Die Passwörter stimmen nicht überein."
done

fett "6/6  Zum Ausprobieren"
mit_test=nein
ja "Testturnier anlegen (öffentlich sichtbar, später im Admin löschen)?" "j" && mit_test=ja

# ---------------------------------------------------------------------------------------------------------------
fett "Einrichten in $ZIEL"
if [ -d "$ZIEL/.git" ]; then
  git -C "$ZIEL" pull -q --ff-only
else
  git clone -q "$QUELLE" "$ZIEL"
fi
cd "$ZIEL"

profile=satzball
[ "$mit_becher" = ja ] && profile=satzball,becherkoenig
echo "COMPOSE_PROFILES=$profile" > .env

# schreibe_env <datei> <domain> <absendername> [quellcode-url]
schreibe_env() {
  {
    echo "# Angelegt von install.sh – Erklärungen in docs/satzball.env.example"
    if [ -n "$2" ]; then
      env_zeile DJANGO_ALLOWED_HOSTS "$2"
      env_zeile DJANGO_CSRF_TRUSTED_ORIGINS "https://$2"
      env_zeile DJANGO_HTTPS 1
    else
      env_zeile DJANGO_ALLOWED_HOSTS "$ip"
      env_zeile DJANGO_HTTPS 0
    fi
    env_zeile SATZBALL_VERANTWORTLICHER "$v_name | $v_strasse | $v_ort | E-Mail: $v_mail"
    if [ -n "${4:-}" ]; then env_zeile SATZBALL_QUELLCODE_URL "$4"; fi
    if [ "$mit_mail" = ja ]; then
      env_zeile EMAIL_HOST "$smtp_host"
      env_zeile EMAIL_PORT "$smtp_port"
      env_zeile EMAIL_USE_TLS 1
      env_zeile EMAIL_HOST_USER "$smtp_user"
      env_zeile EMAIL_HOST_PASSWORD "$smtp_pw"
      env_zeile DEFAULT_FROM_EMAIL "$3 <$smtp_user>"
    fi
  } > "$1"
  chmod 600 "$1"
}
schreibe_env satzball.env "$domain_satzball" "Satzball"
touch becherkoenig.env && chmod 600 becherkoenig.env
[ "$mit_becher" = ja ] && schreibe_env becherkoenig.env "$domain_becher" "Becherkönig" "https://github.com/DHSN-Timberborn/Becherkoenig"

{
  echo "# Angelegt von install.sh – Vorlage mit Erklärungen: docs/Caddyfile.example"
  printf '%s {\n\treverse_proxy satzball:8000\n}\n' "${domain_satzball:-:80}"
  if [ "$mit_becher" = ja ]; then
    printf '\n%s {\n\treverse_proxy becherkoenig:8000\n}\n' "${domain_becher:-:8080}"
  fi
} > Caddyfile

if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  hinweis "Firewall (ufw): öffne Ports 80 und 443 …"
  ufw allow 80/tcp >/dev/null && ufw allow 443 >/dev/null
  if [ "$mit_becher" = ja ] && [ -z "$domain_becher" ]; then ufw allow 8080/tcp >/dev/null; fi
fi

hinweis "Lade die Images und starte die Container (beim ersten Mal 1–2 Minuten) …"
docker compose up -d --quiet-pull

apps=(satzball)
[ "$mit_becher" = ja ] && apps+=(becherkoenig)
for app in "${apps[@]}"; do
  for _ in $(seq 1 60); do
    docker exec "$app" python manage.py migrate --check >/dev/null 2>&1 && break
    sleep 2
  done
  docker exec "$app" python manage.py migrate --check >/dev/null 2>&1 || fehler "$app startet nicht. Log: docker logs $app"

  # Orga-Zugang: Passwort über stdin, damit es weder in der Prozessliste noch in einer Datei steht
  printf '%s\n%s\n%s\n' "$orga_name" "$orga_mail" "$orga_pw" | docker exec -i "$app" python manage.py shell -c "
import sys
from django.contrib.auth import get_user_model
name, mail, pw = (sys.stdin.readline().rstrip('\n') for _ in range(3))
u, _ = get_user_model().objects.get_or_create(username=name)
u.email, u.is_staff, u.is_superuser = mail, True, True
u.set_password(pw)
u.save()
" >/dev/null
  hinweis "$app läuft, Orga-Zugang „$orga_name“ angelegt."

  if [ "$mit_test" = ja ]; then
    extra=()
    [ "$app" = becherkoenig ] && extra=(--bierpong)
    # Nur zum Ausprobieren – ein Fehler hier (z. B. Fork noch nicht synchronisiert) bricht die Installation nicht ab
    if docker exec "$app" python manage.py testturnier --teams 8 --spielplan "${extra[@]}" >/dev/null; then
      hinweis "$app: Testturnier angelegt."
    else
      hinweis "$app: Testturnier konnte nicht angelegt werden – später von Hand, siehe docs/betrieb.md („Probelauf“)."
    fi
  fi
done

# Tägliche Sicherung (14 Stück bleiben), alte Satzball-Zeilen ersetzen
{
  crontab -l 2>/dev/null | grep -v "manage.py sicherung" || true
  echo "30 3 * * * docker exec satzball python manage.py sicherung >/dev/null"
  if [ "$mit_becher" = ja ]; then echo "40 3 * * * docker exec becherkoenig python manage.py sicherung >/dev/null"; fi
} | crontab -
hinweis "Tägliche Sicherung um 3:30 Uhr eingerichtet."

adresse() { if [ -n "$1" ]; then printf 'https://%s/' "$1"; else printf 'http://%s%s/' "$ip" "$2"; fi; }
fett "Fertig! Weiter geht es unter:"
hinweis "Satzball:     $(adresse "$domain_satzball" "")admin/"
[ "$mit_becher" = ja ] && hinweis "Becherkönig:  $(adresse "$domain_becher" ":8080")admin/"
hinweis "Anmelden mit „$orga_name“ und deinem Passwort."
[ -n "$domain_satzball$domain_becher" ] && hinweis "Das HTTPS-Zertifikat holt Caddy beim ersten Aufruf – kann eine Minute dauern."
[ -z "$domain_satzball" ] && hinweis "Ohne Domain läuft alles ohne HTTPS – für echte Turniere eine Domain eintragen (docs/betrieb.md)."
[ "$mit_test" = ja ] && hinweis "Das Testturnier ist auf der Startseite zu sehen; nach dem Ausprobieren im Admin löschen."
[ "$mit_mail" = nein ] && hinweis "Mail später eintragen: $ZIEL/satzball.env, danach: cd $ZIEL && docker compose up -d"
printf '\n' >&2
