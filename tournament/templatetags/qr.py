"""QR-Code als eingebettetes SVG – erzeugt auf dem Server mit segno, ohne fremden Dienst (Datenschutz)."""

import segno
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def qr_svg(daten, titel=""):
    """{% qr_svg url "Titel" %} – schwarz auf weiß mit Rand, damit Handys ihn auch im Dunkelmodus lesen."""
    qr = segno.make(daten, error="m")
    return mark_safe(qr.svg_inline(scale=5, border=3, dark="#000", light="#fff", title=titel or None, svgclass="qr", omitsize=True))  # viewBox statt fester Größe, CSS skaliert
