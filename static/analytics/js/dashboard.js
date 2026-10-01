(function () {
  "use strict";

  var BRAND = {
    primary: "#e84a7a",
    accent: "#d4a574",
    love: "#ff4d6d",
    success: "#22c55e",
    warning: "#f59e0b",
    error: "#ef4444",
    tertiary: "#8b5cf6",
    grid: "rgba(255,255,255,0.06)",
    text: "#b0b3ba",
  };
  window.DuoAnalyticsBrand = BRAND;

  var PERIOD_LABELS = { "7d": "7 days", "30d": "30 days", "90d": "90 days" };
  var VALID_MODULES = ["overview", "revenue", "users", "matching", "chat", "funnel", "retention", "forecast", "security", "maps", "system"];
  // Report types the export endpoint understands; other tabs export the executive report.
  var EXPORTABLE = ["revenue", "users", "matching", "chat", "funnel", "retention", "forecast", "security", "maps", "system"];

  var overviewCharts = {};
  var currentModule = "overview";
  var currentPeriod = "30d";
  var loadToken = 0;
  var failures = [];
  var ws = null;
  var wsRetryMs = 5000;

  function getTheme() {
    return document.documentElement.getAttribute("data-portal-theme") === "light" ? "light" : "dark";
  }

  function chartDefaults(theme) {
    var isLight = theme === "light";
    return {
      color: isLight ? "#4b5563" : BRAND.text,
      grid: isLight ? "rgba(0,0,0,0.06)" : BRAND.grid,
    };
  }

  function storage(key, value) {
    try {
      if (value === undefined) return window.localStorage.getItem(key);
      window.localStorage.setItem(key, value);
    } catch (_e) { /* storage unavailable */ }
    return null;
  }

  /* ---------- status banner ---------- */

  function showStatus(message) {
    var el = document.getElementById("analytics-status");
    if (!el) return;
    el.textContent = message;
    el.hidden = !message;
  }

  function reportFailures() {
    if (!failures.length) {
      showStatus("");
      return;
    }
    showStatus("Some data could not be loaded: " + failures.join("; ") + ". Use Refresh to try again.");
  }

  async function fetchJson(url) {
    try {
      var res = await fetch(url, { credentials: "include", headers: { Accept: "application/json" } });
      if (!res.ok) {
        var reason = res.status === 401 || res.status === 403 ? "permission denied" : "HTTP " + res.status;
        failures.push(url.split("?")[0].replace("/api/analytics/", "") + " (" + reason + ")");
        return null;
      }
      return await res.json();
    } catch (_e) {
      failures.push(url.split("?")[0].replace("/api/analytics/", "") + " (network error)");
      return null;
    }
  }

  function periodQuery() {
    return "?period=" + encodeURIComponent(currentPeriod);
  }

  /* ---------- theme ---------- */

  function applyChartTheme(chart, c) {
    if (chart.options.scales) {
      Object.values(chart.options.scales).forEach(function (scale) {
        if (scale.ticks) scale.ticks.color = c.color;
        if (scale.grid && scale.grid.display !== false) scale.grid.color = c.grid;
      });
    }
    if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
      chart.options.plugins.legend.labels.color = c.color;
    }
    chart.update();
  }

  function applyChartGlobals(theme) {
    if (!window.Chart) return;
    var c = chartDefaults(theme);
    Chart.defaults.color = c.color;
    Chart.defaults.borderColor = c.grid;
  }

  function setTheme(theme) {
    applyChartGlobals(theme);
    var app = document.getElementById("duo-analytics-app");
    if (!app) return;
    app.setAttribute("data-theme", theme);
    var c = chartDefaults(theme);
    Object.values(overviewCharts).forEach(function (chart) { applyChartTheme(chart, c); });
    if (window.DuoAnalyticsModules) window.DuoAnalyticsModules.refreshThemes();
  }

  // Follow the admin portal theme (top-bar theme menu: light / dark / system).
  function initThemeSync() {
    setTheme(getTheme());
    if (!("MutationObserver" in window)) return;
    new MutationObserver(function () {
      var app = document.getElementById("duo-analytics-app");
      var next = getTheme();
      if (app && app.getAttribute("data-theme") !== next) setTheme(next);
    }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-portal-theme"] });
  }

  /* ---------- overview charts ---------- */

  function baseScales(c, opts) {
    opts = opts || {};
    return {
      x: { ticks: { color: c.color, maxTicksLimit: 8, font: { size: 10 } }, grid: opts.xGrid === false ? { display: false } : { color: c.grid } },
      y: { beginAtZero: true, ticks: { color: c.color, font: { size: 10 } }, grid: opts.yGrid === false ? { display: false } : { color: c.grid } },
    };
  }

  function ensureRevenueChart() {
    if (overviewCharts.revenue) return overviewCharts.revenue;
    var el = document.getElementById("revenue-chart");
    if (!el || !window.Chart) return null;
    var c = chartDefaults(getTheme());
    overviewCharts.revenue = new Chart(el, {
      type: "line",
      data: { labels: [], datasets: [{ label: "Revenue", data: [], borderColor: BRAND.primary, backgroundColor: "rgba(232,74,122,0.12)", fill: true, tension: 0.35 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: baseScales(c) },
    });
    return overviewCharts.revenue;
  }

  function ensureActivityChart() {
    if (overviewCharts.activity) return overviewCharts.activity;
    var el = document.getElementById("activity-chart");
    if (!el || !window.Chart) return null;
    var c = chartDefaults(getTheme());
    overviewCharts.activity = new Chart(el, {
      type: "bar",
      data: { labels: ["DAU", "WAU", "MAU", "Online"], datasets: [{ data: [0, 0, 0, 0], backgroundColor: [BRAND.primary, BRAND.love, BRAND.accent, BRAND.success], borderRadius: 8 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: baseScales(c, { xGrid: false }) },
    });
    return overviewCharts.activity;
  }

  function ensureFunnelChart() {
    if (overviewCharts.funnel) return overviewCharts.funnel;
    var el = document.getElementById("funnel-chart");
    if (!el || !window.Chart) return null;
    var c = chartDefaults(getTheme());
    overviewCharts.funnel = new Chart(el, {
      type: "bar",
      data: { labels: [], datasets: [{ data: [], backgroundColor: "rgba(212,165,116,0.5)", borderColor: BRAND.accent, borderWidth: 1, borderRadius: 6 }] },
      options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: baseScales(c, { yGrid: false }) },
    });
    return overviewCharts.funnel;
  }

  function setKpi(key, text) {
    document.querySelectorAll('[data-kpi="' + key + '"]').forEach(function (el) { el.textContent = text; });
  }

  function num(v, digits) {
    if (v === null || v === undefined || v === "") return "—";
    var n = Number(v);
    if (isNaN(n)) return String(v);
    return n.toLocaleString(undefined, { maximumFractionDigits: digits === undefined ? 2 : digits });
  }

  function fillOverviewKpis(ex) {
    if (!ex) return;
    var r = ex.revenue || {}, u = ex.users || {}, e = ex.engagement || {}, o = ex.operations || {};
    setKpi("revenue.today", num(r.today));
    var delta = document.querySelector('[data-kpi="revenue.today_change_pct"]');
    if (delta) {
      var pct = Number(r.today_change_pct || 0);
      delta.textContent = num(pct) + "% vs yesterday";
      delta.classList.toggle("positive", pct >= 0);
      delta.classList.toggle("negative", pct < 0);
    }
    setKpi("revenue.mrr", num(r.mrr));
    setKpi("revenue.arr", num(r.arr));
    setKpi("revenue.failed_payments", num(r.failed_payments));
    setKpi("users.total", num(u.total));
    setKpi("users.online", num(u.online));
    setKpi("users.dau_wau_mau", num(u.dau) + " / " + num(u.wau) + " / " + num(u.mau));
    setKpi("users.premium", num(u.premium));
    setKpi("users.retention_rate", num(u.retention_rate) + "%");
    setKpi("users.churn_rate", num(u.churn_rate) + "%");
    setKpi("users.ltv_arpu", num(u.ltv) + " / " + num(u.arpu));
    setKpi("engagement.total_matches", num(e.total_matches));
    setKpi("engagement.total_messages", num(e.total_messages));
    setKpi("operations.verification_queue", num(o.verification_queue));
  }

  async function loadOverview(token) {
    var q = periodQuery();
    var results = await Promise.all([
      fetchJson("/api/analytics/revenue/timeseries/" + q),
      fetchJson("/api/analytics/funnel/" + q),
      fetchJson("/api/analytics/dashboard/executive/" + q),
    ]);
    if (token !== loadToken) return;
    var revenue = results[0], funnel = results[1], executive = results[2];

    var badge = document.getElementById("revenue-period-badge");
    if (badge) badge.textContent = PERIOD_LABELS[currentPeriod] || currentPeriod;

    var rc = ensureRevenueChart();
    if (rc) {
      var ts = (revenue && revenue.timeseries) || [];
      rc.data.labels = ts.map(function (d) { return d.date; });
      rc.data.datasets[0].data = ts.map(function (d) { return d.total; });
      rc.update();
    }

    var fc = ensureFunnelChart();
    if (fc) {
      var stages = (funnel && funnel.stages) || [];
      fc.data.labels = stages.map(function (s) { return s.stage.replace(/_/g, " "); });
      fc.data.datasets[0].data = stages.map(function (s) { return s.count; });
      fc.update();
    }

    var ac = ensureActivityChart();
    if (executive) {
      fillOverviewKpis(executive);
      if (ac) {
        ac.data.datasets[0].data = [executive.users.dau, executive.users.wau, executive.users.mau, executive.users.online];
        ac.update();
      }
    }
  }

  /* ---------- realtime ---------- */

  function setLive(online) {
    var badge = document.getElementById("live-badge");
    if (!badge) return;
    badge.textContent = online ? "Live" : "Offline";
    badge.classList.toggle("is-offline", !online);
  }

  function updateLiveKpis(m) {
    if (m.online_users !== undefined) setKpi("users.online", num(m.online_users));
    if (m.revenue_today !== undefined) setKpi("revenue.today", num(m.revenue_today));
    if (m.verification_queue !== undefined) setKpi("operations.verification_queue", num(m.verification_queue));
    if (m.failed_payments !== undefined) setKpi("revenue.failed_payments", num(m.failed_payments));
    var ac = overviewCharts.activity;
    if (ac && m.online_users !== undefined) {
      ac.data.datasets[0].data[3] = m.online_users;
      ac.update("none");
    }
  }

  function connectRealtime() {
    if (!("WebSocket" in window)) return setLive(false);
    var proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    try {
      ws = new WebSocket(proto + "//" + window.location.host + "/ws/analytics/");
    } catch (_e) {
      setLive(false);
      return;
    }
    ws.onopen = function () { wsRetryMs = 5000; setLive(true); };
    ws.onmessage = function (event) {
      try {
        var data = JSON.parse(event.data);
        if (data.type === "metrics" && data.metrics) updateLiveKpis(data.metrics);
      } catch (_e) { /* ignore malformed frames */ }
    };
    ws.onclose = function (event) {
      setLive(false);
      // 4401/4403: not authenticated or not staff. Retrying cannot succeed.
      if (event.code === 4401 || event.code === 4403) return;
      setTimeout(connectRealtime, wsRetryMs);
      wsRetryMs = Math.min(wsRetryMs * 2, 60000);
    };
  }

  /* ---------- modules ---------- */

  var MODULE_ENDPOINTS = {
    revenue: { url: "/api/analytics/revenue/", loader: "loadRevenue" },
    users: { url: "/api/analytics/users/", loader: "loadUsers" },
    matching: { url: "/api/analytics/matching/", loader: "loadMatching" },
    chat: { url: "/api/analytics/chat/", loader: "loadChat" },
    funnel: { url: "/api/analytics/funnel/", loader: "loadFunnel" },
    retention: { url: "/api/analytics/retention/", loader: "loadRetention" },
    forecast: { url: "/api/analytics/forecast/", loader: "loadForecast" },
    security: { url: "/api/analytics/security/", loader: "loadSecurity", extra: "/api/analytics/fraud/" },
    maps: { url: "/api/analytics/maps/", loader: "loadMaps" },
    system: { url: "/api/analytics/system/", loader: "loadSystem" },
  };

  async function loadModule(module) {
    var token = ++loadToken;
    failures = [];
    var section = document.getElementById("section-" + module);
    if (section) section.classList.add("is-loading");
    try {
      if (module === "overview") {
        await loadOverview(token);
      } else {
        var config = MODULE_ENDPOINTS[module];
        if (config && window.DuoAnalyticsModules) {
          var q = periodQuery();
          var results = await Promise.all([
            fetchJson(config.url + q),
            config.extra ? fetchJson(config.extra + q) : Promise.resolve(null),
          ]);
          if (token !== loadToken) return;
          var loader = window.DuoAnalyticsModules[config.loader];
          if (loader) {
            try {
              loader(results[0], results[1]);
            } catch (err) {
              failures.push(module + " (render error)");
              if (window.console) console.error("Analytics render failed for " + module, err);
            }
          }
        }
      }
    } finally {
      if (token === loadToken) {
        if (section) section.classList.remove("is-loading");
        reportFailures();
      }
    }
  }

  function switchModule(module) {
    if (VALID_MODULES.indexOf(module) === -1) module = "overview";
    currentModule = module;
    document.querySelectorAll(".module-tab").forEach(function (tab) {
      var active = tab.getAttribute("data-module") === module;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    document.querySelectorAll(".analytics-section").forEach(function (section) {
      var active = section.getAttribute("data-module") === module;
      section.classList.toggle("is-active", active);
      section.hidden = !active;
    });
    if (window.location.hash.slice(1) !== module) {
      try { history.replaceState(null, "", "#" + module); } catch (_e) { /* ignore */ }
    }
    loadModule(module);
  }

  function initTabs() {
    document.querySelectorAll(".module-tab").forEach(function (tab) {
      tab.addEventListener("click", function () { switchModule(tab.getAttribute("data-module")); });
    });
    window.addEventListener("hashchange", function () {
      var m = window.location.hash.slice(1);
      if (m && m !== currentModule) switchModule(m);
    });
  }

  function initPeriodFilter() {
    var select = document.getElementById("period-filter");
    if (!select) return;
    var saved = storage("duoAnalyticsPeriod");
    if (saved && PERIOD_LABELS[saved]) select.value = saved;
    currentPeriod = select.value;
    select.addEventListener("change", function () {
      currentPeriod = select.value;
      storage("duoAnalyticsPeriod", currentPeriod);
      loadModule(currentModule);
    });
  }

  function initActions() {
    var refresh = document.getElementById("refresh-btn");
    if (refresh) {
      refresh.addEventListener("click", function () {
        loadModule(currentModule);
        if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: "refresh" }));
      });
    }
    var exportBtn = document.getElementById("export-btn");
    var exportFmt = document.getElementById("export-format");
    if (exportBtn) {
      exportBtn.addEventListener("click", async function () {
        var type = EXPORTABLE.indexOf(currentModule) !== -1 ? currentModule : "executive";
        var fmt = exportFmt ? exportFmt.value : "pdf";
        var url = "/api/analytics/exports/?type=" + encodeURIComponent(type) +
          "&format=" + encodeURIComponent(fmt) + "&period=" + encodeURIComponent(currentPeriod);
        var label = exportBtn.textContent;
        exportBtn.disabled = true;
        exportBtn.textContent = "Exporting…";
        try {
          var res = await fetch(url, { credentials: "include" });
          if (!res.ok) {
            var detail = "HTTP " + res.status;
            try { detail = (await res.json()).detail || detail; } catch (_e) { /* not JSON */ }
            showStatus("Export failed: " + detail);
            return;
          }
          var blob = await res.blob();
          var name = type + "_report." + fmt;
          var cd = res.headers.get("Content-Disposition") || "";
          var match = cd.match(/filename="?([^";]+)"?/);
          if (match) name = match[1];
          var link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = name;
          document.body.appendChild(link);
          link.click();
          setTimeout(function () { URL.revokeObjectURL(link.href); link.remove(); }, 1000);
        } catch (_e) {
          showStatus("Export failed: network error.");
        } finally {
          exportBtn.disabled = false;
          exportBtn.textContent = label;
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initThemeSync();
    initTabs();
    initPeriodFilter();
    initActions();
    ensureActivityChart();
    switchModule(window.location.hash.slice(1) || "overview");
    connectRealtime();
  });
})();
