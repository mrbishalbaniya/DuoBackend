(function () {
  "use strict";

  var STORAGE_KEY = "duo-portal-theme";
  var mediaQuery = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function getStoredPreference() {
    var stored = localStorage.getItem(STORAGE_KEY);
    return stored === "light" || stored === "dark" || stored === "system" ? stored : "dark";
  }

  function resolveTheme(preference) {
    if (preference === "system" && mediaQuery) {
      return mediaQuery.matches ? "dark" : "light";
    }
    return preference === "light" ? "light" : "dark";
  }

  function applyTheme(preference) {
    var resolved = resolveTheme(preference);
    var html = document.documentElement;
    html.setAttribute("data-portal-theme", resolved);
    html.setAttribute("data-bs-theme", resolved);
    html.setAttribute("data-portal-theme-pref", preference);
    html.style.colorScheme = resolved;

    var icon = document.getElementById("theme-menu-icon");
    if (icon) {
      icon.className = resolved === "dark" ? "fas fa-sun" : "fas fa-moon";
    }

    document.querySelectorAll("[data-theme-choice]").forEach(function (btn) {
      var active = btn.getAttribute("data-theme-choice") === preference;
      btn.classList.toggle("is-active", active);
      var check = btn.querySelector(".duo-portal-theme-option__check");
      if (check) check.hidden = !active;
    });

    window.dispatchEvent(new CustomEvent("duo-portal-theme-change", {
      detail: { preference: preference, resolved: resolved },
    }));
  }

  function setThemePreference(preference) {
    localStorage.setItem(STORAGE_KEY, preference);
    applyTheme(preference);
  }

  function initTheme() {
    var preference = getStoredPreference();
    applyTheme(preference);

    document.querySelectorAll("[data-theme-choice]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        setThemePreference(btn.getAttribute("data-theme-choice"));
        var themePanel = document.getElementById("theme-panel");
        if (themePanel) themePanel.hidden = true;
      });
    });

    if (mediaQuery && mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", function () {
        if (getStoredPreference() === "system") applyTheme("system");
      });
    }
  }

  function initSidebar() {
    var shell = document.getElementById("duo-portal-shell");
    var collapseBtn = document.getElementById("sidebar-collapse");
    var mobileBtn = document.getElementById("mobile-sidebar-toggle");
    var SIDEBAR_KEY = "duo-portal-sidebar";

    function setSidebarCollapsed(collapsed) {
      if (!shell) return;
      shell.classList.toggle("is-collapsed", collapsed);
      document.documentElement.setAttribute(
        "data-portal-sidebar",
        collapsed ? "collapsed" : "expanded"
      );
      localStorage.setItem(SIDEBAR_KEY, collapsed ? "collapsed" : "expanded");
      if (collapseBtn) {
        collapseBtn.setAttribute(
          "aria-label",
          collapsed ? "Expand sidebar" : "Collapse sidebar"
        );
        var icon = collapseBtn.querySelector("i");
        if (icon) {
          icon.className = collapsed ? "fas fa-angles-right" : "fas fa-angles-left";
        }
      }
      if (!collapsed) {
        openActiveNavGroup();
      }
    }

    function openActiveNavGroup() {
      var activeLink = document.querySelector(".duo-portal-nav-link.is-active");
      if (!activeLink) return;
      var activeGroup = activeLink.closest(".duo-portal-nav-group");
      if (!activeGroup) return;
      activeGroup.classList.remove("is-collapsed");
      var toggle = activeGroup.querySelector(".duo-portal-nav-group__toggle");
      if (toggle) toggle.setAttribute("aria-expanded", "true");
    }

    // Default collapsed; only expand if user previously chose expanded.
    var stored = localStorage.getItem(SIDEBAR_KEY);
    setSidebarCollapsed(stored !== "expanded");

    if (collapseBtn && shell) {
      collapseBtn.addEventListener("click", function () {
        setSidebarCollapsed(!shell.classList.contains("is-collapsed"));
      });
    }
    if (mobileBtn && shell) {
      mobileBtn.addEventListener("click", function () {
        shell.classList.toggle("is-mobile-open");
      });
    }

    document.querySelectorAll(".duo-portal-nav-group__toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var group = btn.closest(".duo-portal-nav-group");
        if (!group) return;
        var collapsed = group.classList.toggle("is-collapsed");
        btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
      });
    });
  }

  function initDropdowns() {
    setupDropdown("notifications-btn", "notifications-panel");
    setupDropdown("profile-menu-btn", "profile-panel");
    setupDropdown("theme-menu-btn", "theme-panel");
  }

  function setupDropdown(btnId, panelId) {
    var btn = document.getElementById(btnId);
    var panel = document.getElementById(panelId);
    if (!btn || !panel) return;
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      panel.hidden = !panel.hidden;
    });
    document.addEventListener("click", function () {
      panel.hidden = true;
    });
  }

  function initGlobalSearch() {
    var input = document.getElementById("global-search-input");
    var results = document.getElementById("global-search-results");
    if (!input || !results) return;

    var timer;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        fetchSearch(input.value, results);
      }, 250);
    });

    input.addEventListener("focus", function () {
      if (input.value.length >= 2) results.hidden = false;
    });
  }

  function fetchSearch(q, container) {
    if (!q || q.length < 2) {
      container.hidden = true;
      return;
    }
    fetch("/api/portal/search/?q=" + encodeURIComponent(q), { credentials: "include" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        container.innerHTML = (data.results || []).map(function (item) {
          return '<a class="duo-portal-search__result" href="' + item.url + '">' +
            '<i class="' + item.icon + '"></i><div><strong>' + item.title + '</strong>' +
            '<div style="font-size:0.75rem;opacity:0.7">' + item.subtitle + '</div></div></a>';
        }).join("") || '<div style="padding:1rem">No results</div>';
        container.hidden = false;
      });
  }

  function loadNotifications() {
    var list = document.getElementById("notifications-list");
    var count = document.getElementById("notifications-count");
    if (!list) return;
    fetch("/api/portal/notifications/", { credentials: "include" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var items = data.notifications || [];
        if (count) count.style.display = items.length ? "flex" : "none";
        list.innerHTML = items.map(function (n) {
          return '<a href="' + n.url + '" class="duo-portal-dropdown__item">' +
            '<i class="fas fa-circle" style="color:var(--duo-' + (n.type === "error" ? "error" : "warning") + ')"></i>' +
            '<div><strong>' + n.title + '</strong><div style="font-size:0.75rem">' + n.body + '</div></div></a>';
        }).join("") || '<div style="padding:1rem">No notifications</div>';
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSidebar();
    initTheme();
    initDropdowns();
    initGlobalSearch();
    loadNotifications();
  });

  window.DuoPortal = {
    applyTheme: applyTheme,
    setThemePreference: setThemePreference,
    getStoredPreference: getStoredPreference,
    resolveTheme: resolveTheme,
    fetchSearch: fetchSearch,
  };
})();
