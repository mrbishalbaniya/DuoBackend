(function () {
  "use strict";

  function syncThemeFromPortal() {
    var resolved = document.documentElement.getAttribute("data-portal-theme") || "dark";
    if (resolved !== "light" && resolved !== "dark") resolved = "dark";
    document.documentElement.setAttribute("data-bs-theme", resolved);
    document.documentElement.style.colorScheme = resolved;
  }

  function enhanceSidebarDropdowns() {
    var sidebar = document.getElementById("jazzy-sidebar");
    if (!sidebar) {
      return;
    }

    var treeParents = sidebar.querySelectorAll(".nav-item.has-treeview > .nav-link");
    treeParents.forEach(function (link) {
      link.setAttribute("role", "button");
      link.setAttribute("aria-expanded", link.closest(".has-treeview").classList.contains("menu-open") ? "true" : "false");
    });

    sidebar.addEventListener("click", function (event) {
      var parentLink = event.target.closest(".nav-item.has-treeview > .nav-link");
      if (!parentLink) {
        return;
      }
      window.setTimeout(function () {
        var item = parentLink.closest(".nav-item.has-treeview");
        if (!item) {
          return;
        }
        parentLink.setAttribute("aria-expanded", item.classList.contains("menu-open") ? "true" : "false");
      }, 0);
    });
  }

  function setAccountMenuTitle() {
    var toggle = document.querySelector(".navbar-nav.ms-auto .nav-item.dropdown > a[title]");
    if (toggle && !toggle.getAttribute("title")) {
      toggle.setAttribute("title", "Account & Logout");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    syncThemeFromPortal();
    enhanceSidebarDropdowns();
    setAccountMenuTitle();
  });

  window.addEventListener("duo-portal-theme-change", syncThemeFromPortal);
})();
