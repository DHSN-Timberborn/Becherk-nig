// Admin "Turnier": Felder ausgrauen, die im gewählten Zählmodus nicht gelten
// (Satz-Felder nur im Satz-Modus, Becherzahl nur im Becher-Modus).
// Bewusst nicht "disabled": gesperrte Felder würden beim Speichern nicht mitgeschickt.
document.addEventListener("DOMContentLoaded", function () {
  var modus = document.getElementById("id_zaehlmodus");
  if (!modus) return;
  var gilt = {
    gewinnsaetze: "saetze", punkte_pro_satz: "saetze", punkte_entscheidungssatz: "saetze", becher: "becher",
  };

  function aktualisieren() {
    Object.keys(gilt).forEach(function (name) {
      var feld = document.getElementById("id_" + name);
      if (!feld) return;
      var aus = modus.value !== gilt[name];
      feld.setAttribute("aria-disabled", aus ? "true" : "false");
      feld.tabIndex = aus ? -1 : 0;
      var zeile = feld.closest(".form-row") || feld.closest(".fieldBox");
      if (zeile) zeile.classList.toggle("satzball-aus", aus);
    });
  }

  modus.addEventListener("change", aktualisieren);
  aktualisieren();
});
