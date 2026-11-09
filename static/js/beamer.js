// Beamer-Ansicht: alle 30 s den neuen Stand holen und nur den Inhalt austauschen.
// Ein normales Neuladen würde den Vollbildmodus beenden. Ohne JavaScript lädt <noscript> die Seite neu.
(function () {
  var sekunden = Number(document.getElementById("beamer").dataset.neuLaden) || 30;

  setInterval(function () {
    fetch(location.href, { cache: "no-store" })
      .then(function (antwort) { return antwort.ok ? antwort.text() : null; })
      .then(function (html) {
        if (!html) return;
        var neu = new DOMParser().parseFromString(html, "text/html").getElementById("beamer");
        var alt = document.getElementById("beamer");
        if (neu && alt) {
          alt.replaceWith(neu);
          vollbildKnopf();
        }
      })
      .catch(function () {});  // kurz kein Netz: beim nächsten Mal wieder versuchen
  }, sekunden * 1000);

  function vollbildKnopf() {
    var knopf = document.querySelector("[data-vollbild]");
    if (!knopf || !document.documentElement.requestFullscreen) return;
    knopf.hidden = false;
    knopf.addEventListener("click", function () { document.documentElement.requestFullscreen(); });
  }
  vollbildKnopf();
})();
