// Schritt-für-Schritt-Formulare: <form data-schritte> mit <fieldset class="schritt" data-titel="…">.
// Ohne JavaScript sind alle Schritte untereinander zu sehen; mit JavaScript immer nur einer, mit Weiter/Zurück.
// Felder mit data-zeigen-wenn="name=wert" erscheinen nur, wenn das Auswahlfeld „name“ den Wert „wert“ hat.
document.querySelectorAll("form[data-schritte]").forEach(function (form) {
  var schritte = Array.prototype.slice.call(form.querySelectorAll(".schritt"));
  var weiter = form.querySelector("[data-weiter]");
  var zurueck = form.querySelector("[data-zurueck]");
  var senden = form.querySelector("[data-senden]");
  var anzeige = form.querySelector("[data-schritt-anzeige]");
  var balken = form.querySelector("[data-schritt-balken]");
  var aktuell = 0;

  // Nach einem Fehler vom Server direkt beim ersten Schritt mit Fehler weitermachen
  for (var i = 0; i < schritte.length; i++) {
    if (schritte[i].querySelector(".fehler li, .errorlist li")) { aktuell = i; break; }
  }

  function zeigen() {
    schritte.forEach(function (s, i) { s.hidden = i !== aktuell; });
    var letzter = aktuell === schritte.length - 1;
    zurueck.hidden = aktuell === 0;
    weiter.hidden = letzter;
    senden.hidden = !letzter;
    if (anzeige) anzeige.textContent = "Schritt " + (aktuell + 1) + " von " + schritte.length + " · " + schritte[aktuell].dataset.titel;
    if (balken) balken.style.width = ((aktuell + 1) / schritte.length * 100) + "%";
    var erstes = schritte[aktuell].querySelector("input:not([type=hidden]):not([disabled]), select, textarea");
    if (erstes && form.dataset.gestartet) erstes.focus();
  }

  function gueltig() {
    var felder = schritte[aktuell].querySelectorAll("input, select, textarea");
    for (var i = 0; i < felder.length; i++) {
      if (!felder[i].closest("[hidden]") && !felder[i].checkValidity()) { felder[i].reportValidity(); return false; }
    }
    return true;
  }

  function sichtbarkeit() {
    form.querySelectorAll("[data-zeigen-wenn]").forEach(function (el) {
      var teile = el.dataset.zeigenWenn.split("=");
      var gewaehlt = form.querySelector("[name='" + teile[0] + "']:checked");
      el.hidden = !gewaehlt || gewaehlt.value !== teile[1];
    });
  }

  form.addEventListener("change", sichtbarkeit);
  sichtbarkeit();

  if (schritte.length < 2) return;
  weiter.addEventListener("click", function () {
    if (gueltig()) { aktuell++; form.dataset.gestartet = "1"; zeigen(); }
  });
  zurueck.addEventListener("click", function () { aktuell--; form.dataset.gestartet = "1"; zeigen(); });
  // Enter in einem Feld: nicht absenden, sondern zum nächsten Schritt
  form.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && e.target.tagName === "INPUT" && aktuell < schritte.length - 1) {
      e.preventDefault();
      weiter.click();
    }
  });
  form.classList.add("schritte--aktiv");
  zeigen();
});
