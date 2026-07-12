(function () {
  "use strict";

  var BRAND = { primary: "#e84a7a", accent: "#d4a574", love: "#ff4d6d", success: "#22c55e" };
  var charts = [];

  function chartColors() {
    var resolved = document.documentElement.getAttribute("data-portal-theme") || "dark";
    var dark = resolved !== "light";
    return { grid: dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)", text: dark ? "#b0b3ba" : "#6b7280" };
  }

  function destroyCharts() {
    charts.forEach(function (c) { c.destroy(); });
    charts = [];
  }

  function renderDashboard(data) {
    if (!data || !window.Chart) return;
    destroyCharts();
    var c = chartColors();
    var chartsData = data.charts || {};

    makeLineChart("chart-revenue", (chartsData.revenue || []).map(function (d) { return d.date; }),
      (chartsData.revenue || []).map(function (d) { return d.total; }), BRAND.primary, c);

    makeLineChart("chart-users", (chartsData.user_growth || []).map(function (d) { return d.date; }),
      (chartsData.user_growth || []).map(function (d) { return d.registrations; }), BRAND.accent, c);

    makeDoughnut("chart-platform", (chartsData.platform || []).map(function (d) { return d.platform || "unknown"; }),
      (chartsData.platform || []).map(function (d) { return d.count; }), c);

    makeDoughnut("chart-gender", (chartsData.gender || []).map(function (d) { return d.gender || "N/A"; }),
      (chartsData.gender || []).map(function (d) { return d.count; }), c);

    renderCities(chartsData.cities || []);
  }

  function makeLineChart(id, labels, values, color, c) {
    var el = document.getElementById(id);
    if (!el) return;
    charts.push(new Chart(el, {
      type: "line",
      data: { labels: labels, datasets: [{ data: values, borderColor: color, backgroundColor: color + "22", fill: true, tension: 0.35 }] },
      options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: c.text }, grid: { color: c.grid } }, y: { ticks: { color: c.text }, grid: { color: c.grid } } } }
    }));
  }

  function makeDoughnut(id, labels, values, c) {
    var el = document.getElementById(id);
    if (!el) return;
    charts.push(new Chart(el, {
      type: "doughnut",
      data: { labels: labels, datasets: [{ data: values, backgroundColor: [BRAND.primary, BRAND.love, BRAND.accent, BRAND.success, "#8b5cf6"] }] },
      options: { responsive: true, plugins: { legend: { position: "bottom", labels: { color: c.text, boxWidth: 12 } } } }
    }));
  }

  function renderCities(cities) {
    var list = document.getElementById("top-cities-list");
    if (!list) return;
    list.innerHTML = cities.map(function (c) {
      return '<li><span>' + (c.location || c.city || "—") + '</span><strong>' + (c.count || 0) + '</strong></li>';
    }).join("") || '<li>No data</li>';
  }

  function updateKpis(kpis) {
    if (!kpis) return;
    document.querySelectorAll("[data-field]").forEach(function (el) {
      var key = el.getAttribute("data-field");
      if (kpis[key] !== undefined) el.textContent = formatValue(key, kpis[key]);
    });
  }

  function formatValue(key, val) {
    if (key.indexOf("revenue") >= 0 || key === "wallet_balance") return Number(val).toLocaleString(undefined, { maximumFractionDigits: 2 });
    return val;
  }

  function loadActivity() {
    var timeline = document.getElementById("activity-timeline");
    if (!timeline) return;
    fetch("/api/portal/activity/", { credentials: "include" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        timeline.innerHTML = (data.activities || []).map(function (a) {
          var color = a.status === "warning" ? BRAND.accent : a.status === "success" ? BRAND.success : BRAND.primary;
          return '<li><span class="duo-timeline__dot" style="background:' + color + '"></span><div><strong>' + a.title + '</strong><div style="font-size:0.75rem;opacity:0.65">' + new Date(a.time).toLocaleString() + '</div></div></li>';
        }).join("") || '<li>No recent activity</li>';
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!document.getElementById("duo-dashboard")) return;
    loadDashboard();
    loadActivity();
    window.addEventListener("duo-portal-theme-change", function () {
      loadDashboard();
    });
  });

  function loadDashboard() {
    fetch("/api/portal/dashboard/", { credentials: "include" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        updateKpis(data.kpis);
        renderDashboard(data);
        var updated = document.getElementById("dashboard-updated-at");
        if (updated) updated.textContent = new Date().toLocaleTimeString();
      });
  }

  window.DuoCharts = { renderDashboard: renderDashboard, updateKpis: updateKpis };
})();
