(function () {
  "use strict";

  function forceDarkTheme() {
    document.documentElement.setAttribute("data-bs-theme", "dark");
    try {
      localStorage.setItem("jazzmin-theme-mode", "dark");
    } catch (_error) {
      /* ignore storage errors */
    }
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
    forceDarkTheme();
    enhanceSidebarDropdowns();
    setAccountMenuTitle();
  });
})();
