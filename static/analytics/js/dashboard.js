(function () {
  "use strict";

  var BRAND = {
    primary: "#e84a7a",
    accent: "#d4a574",
    love: "#ff4d6d",
    grid: "rgba(255,255,255,0.06)",
    text: "#b0b3ba",
  };
  window.DuoAnalyticsBrand = BRAND;

  var overviewCharts = [];
  var loadedModules = {};
  var currentModule = "overview";
  var currentPeriod = "30d";

  function getTheme() {
    var app = document.getElementById("duo-analytics-app");
    return app && app.getAttribute("data-theme") === "light" ? "light" : "dark";
  }

  function chartDefaults(theme) {
    var isLight = theme === "light";
    return {
      color: isLight ? "#4b5563" : BRAND.text,
      grid: isLight ? "rgba(0,0,0,0.06)" : BRAND.grid,
    };
  }

  function updateChartThemes(theme) {
    var c = chartDefaults(theme);
    overviewCharts.forEach(function (chart) {
      if (chart.options.scales) {
        Object.values(chart.options.scales).forEach(function (scale) {
          if (scale.ticks) scale.ticks.color = c.color;
          if (scale.grid) scale.grid.color = c.grid;
        });
      }
      chart.update();
    });
    if (window.DuoAnalyticsModules) window.DuoAnalyticsModules.refreshThemes();
  }

  function initThemeToggle() {
    var app = document.getElementById("duo-analytics-app");
    var btn = document.getElementById("theme-toggle");
    if (!app || !btn) return;
    btn.addEventListener("click", function () {
      var isDark = app.getAttribute("data-theme") !== "light";
      app.setAttribute("data-theme", isDark ? "light" : "dark");
      btn.textContent = isDark ? "Dark mode" : "Light mode";
      updateChartThemes(isDark ? "light" : "dark");
    });
  }

  async function fetchJson(url) {
    var res = await fetch(url, { credentials: "include" });
    if (!res.ok) return null;
    return res.json();
  }

  function periodQuery() {
    return "?period=" + encodeURIComponent(currentPeriod);
  }

  function initRevenueChart(data) {
    var el = document.getElementById("revenue-chart");
    if (!el || !window.Chart) return;
    var labels = (data || []).map(function (d) { return d.date; });
    var values = (data || []).map(function (d) { return d.total; });
    var c = chartDefaults(getTheme());
    overviewCharts.push(new Chart(el, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Revenue",
          data: values,
          borderColor: BRAND.primary,
          backgroundColor: "rgba(232,74,122,0.12)",
          fill: true,
          tension: 0.35,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: c.color }, grid: { color: c.grid } },
          y: { ticks: { color: c.color }, grid: { color: c.grid } },
        },
      },
    }));
  }

  function initActivityChart() {
    var el = document.getElementById("activity-chart");
    if (!el || !window.Chart) return;
    var c = chartDefaults(getTheme());
    overviewCharts.push(new Chart(el, {
      type: "bar",
      data: {
        labels: ["DAU", "WAU", "MAU", "Online"],
        datasets: [{
          data: [0, 0, 0, 0],
          backgroundColor: [BRAND.primary, BRAND.love, BRAND.accent, "#22c55e"],
          borderRadius: 8,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: c.color }, grid: { display: false } },
          y: { ticks: { color: c.color }, grid: { color: c.grid } },
        },
      },
    }));
  }

  function initFunnelChart(stages) {
    var el = document.getElementById("funnel-chart");
    if (!el || !window.Chart) return;
    var c = chartDefaults(getTheme());
    var labels = (stages || []).map(function (s) { return s.stage; });
    var values = (stages || []).map(function (s) { return s.count; });
    overviewCharts.push(new Chart(el, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: "rgba(212,165,116,0.5)",
          borderColor: BRAND.accent,
          borderWidth: 1,
          borderRadius: 6,
        }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: c.color }, grid: { color: c.grid } },
          y: { ticks: { color: c.color }, grid: { display: false } },
        },
      },
    }));
  }

  function connectRealtime() {
    var proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    var ws = new WebSocket(proto + "//" + window.location.host + "/ws/analytics/");
    ws.onmessage = function (event) {
      try {
        var data = JSON.parse(event.data);
        if (data.type === "metrics" && data.metrics) updateLiveKpis(data.metrics);
      } catch (_e) { /* ignore */ }
    };
    ws.onclose = function () { setTimeout(connectRealtime, 5000); };
  }

  function updateLiveKpis(metrics) {
    var online = document.querySelector('[data-kpi="users.online"]');
    if (online && metrics.online_users !== undefined) online.textContent = metrics.online_users;
    var revenue = document.querySelector('[data-kpi="revenue.today"]');
    if (revenue && metrics.revenue_today !== undefined) revenue.textContent = metrics.revenue_today.toFixed(2);
    if (overviewCharts[0] && metrics.online_users !== undefined) {
      overviewCharts[0].data.datasets[0].data[3] = metrics.online_users;
      overviewCharts[0].update();
    }
  }

  async function loadOverview() {
    var q = periodQuery();
    var revenue = await fetchJson("/api/analytics/revenue/timeseries/" + q);
    var funnel = await fetchJson("/api/analytics/funnel/" + q);
    var executive = await fetchJson("/api/analytics/dashboard/executive/" + q);

    if (overviewCharts[1] && revenue) {
      overviewCharts[1].data.labels = (revenue.timeseries || []).map(function (d) { return d.date; });
      overviewCharts[1].data.datasets[0].data = (revenue.timeseries || []).map(function (d) { return d.total; });
      overviewCharts[1].update();
    } else if (!overviewCharts[1]) {
      initRevenueChart(revenue ? revenue.timeseries : []);
    }

    if (overviewCharts[2] && funnel) {
      overviewCharts[2].data.labels = (funnel.stages || []).map(function (s) { return s.stage; });
      overviewCharts[2].data.datasets[0].data = (funnel.stages || []).map(function (s) { return s.count; });
      overviewCharts[2].update();
    } else if (!overviewCharts[2]) {
      initFunnelChart(funnel ? funnel.stages : []);
    }

    if (executive && overviewCharts[0]) {
      overviewCharts[0].data.datasets[0].data = [
        executive.users.dau,
        executive.users.wau,
        executive.users.mau,
        executive.users.online,
      ];
      overviewCharts[0].update();
    }
  }

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
    if (module === "overview") {
      await loadOverview();
      return;
    }
    var config = MODULE_ENDPOINTS[module];
    if (!config || !window.DuoAnalyticsModules) return;

    var q = periodQuery();
    var data = await fetchJson(config.url + q);
    var extra = null;
    if (config.extra) extra = await fetchJson(config.extra + q);

    var loader = window.DuoAnalyticsModules[config.loader];
    if (!loader) return;

    if (module === "security") loader(data, extra);
    else loader(data);

    loadedModules[module] = true;
  }

  function switchModule(module) {
    currentModule = module;
    document.querySelectorAll(".module-tab").forEach(function (tab) {
      tab.classList.toggle("is-active", tab.getAttribute("data-module") === module);
    });
    document.querySelectorAll(".analytics-section").forEach(function (section) {
      var active = section.getAttribute("data-module") === module;
      section.classList.toggle("is-active", active);
      section.hidden = !active;
    });
    loadModule(module);
  }

  function initTabs() {
    document.querySelectorAll(".module-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        switchModule(tab.getAttribute("data-module"));
      });
    });
  }

  function initPeriodFilter() {
    var select = document.getElementById("period-filter");
    if (!select) return;
    select.addEventListener("change", function () {
      currentPeriod = select.value;
      loadedModules = {};
      if (window.DuoAnalyticsModules) window.DuoAnalyticsModules.destroyAll();
      overviewCharts.forEach(function (chart) { chart.destroy(); });
      overviewCharts = [];
      initActivityChart();
      switchModule(currentModule);
    });
  }

  document.addEventListener("DOMContentLoaded", async function () {
    initThemeToggle();
    initTabs();
    initPeriodFilter();
    initActivityChart();
    await loadOverview();
    connectRealtime();
  });
})();
