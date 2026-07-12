(function () {
  "use strict";

  var palette, input, results, commands = [], selected = 0;

  function openPalette() {
    if (!palette) return;
    palette.hidden = false;
    input.value = "";
    selected = 0;
    renderResults("");
    input.focus();
    loadCommands();
  }

  function closePalette() {
    if (palette) palette.hidden = true;
  }

  function loadCommands() {
    if (commands.length) return;
    fetch("/api/portal/commands/", { credentials: "include" })
      .then(function (r) { return r.json(); })
      .then(function (data) { commands = data.commands || []; renderResults(""); });
  }

  function renderResults(q) {
    if (!results) return;
    var filtered = commands.filter(function (c) {
      return !q || c.label.toLowerCase().indexOf(q.toLowerCase()) >= 0;
    }).slice(0, 12);
    results.innerHTML = filtered.map(function (c, i) {
      return '<li><a href="' + c.url + '" class="' + (i === selected ? "is-selected" : "") + '">' +
        '<i class="' + (c.icon || "fas fa-arrow-right") + '"></i><span>' + c.label + '</span></a></li>';
    }).join("");
  }

  document.addEventListener("DOMContentLoaded", function () {
    palette = document.getElementById("command-palette");
    input = document.getElementById("command-palette-input");
    results = document.getElementById("command-palette-results");
    if (!palette || !input) return;

    document.querySelectorAll("[data-close-palette]").forEach(function (el) {
      el.addEventListener("click", closePalette);
    });

    input.addEventListener("input", function () {
      selected = 0;
      renderResults(input.value);
    });

    input.addEventListener("keydown", function (e) {
      var links = results.querySelectorAll("a");
      if (e.key === "ArrowDown") { e.preventDefault(); selected = Math.min(selected + 1, links.length - 1); renderResults(input.value); }
      if (e.key === "ArrowUp") { e.preventDefault(); selected = Math.max(selected - 1, 0); renderResults(input.value); }
      if (e.key === "Enter" && links[selected]) { window.location.href = links[selected].href; }
      if (e.key === "Escape") closePalette();
    });

    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openPalette();
      }
      if (e.key === "Escape") closePalette();
    });

    var searchInput = document.getElementById("global-search-input");
    if (searchInput) {
      searchInput.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
          e.preventDefault();
          openPalette();
        }
      });
    }
  });
})();
