(function () {
  "use strict";

  const BRAND = {
    primary: "#e84a7a",
    accent: "#d4a574",
    love: "#ff4d6d",
    grid: "rgba(255,255,255,0.06)",
    text: "#b0b3ba",
  };

  function initThemeToggle() {
    const app = document.getElementById("duo-analytics-app");
    const btn = document.getElementById("theme-toggle");
    if (!app || !btn) return;
    btn.addEventListener("click", function () {
      const isDark = app.getAttribute("data-theme") !== "light";
      app.setAttribute("data-theme", isDark ? "light" : "dark");
      btn.textContent = isDark ? "Dark mode" : "Light mode";
      updateChartThemes(isDark ? "light" : "dark");
    });
  }

  let charts = [];

  function chartDefaults(theme) {
    const isLight = theme === "light";
    return {
      color: isLight ? "#4b5563" : BRAND.text,
      grid: isLight ? "rgba(0,0,0,0.06)" : BRAND.grid,
    };
  }

  function updateChartThemes(theme) {
    const c = chartDefaults(theme);
    charts.forEach(function (chart) {
      if (chart.options.scales) {
        Object.values(chart.options.scales).forEach(function (scale) {
          if (scale.ticks) scale.ticks.color = c.color;
          if (scale.grid) scale.grid.color = c.grid;
        });
      }
      chart.update();
    });
  }

  async function fetchJson(url) {
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) return null;
    return res.json();
  }

  function initRevenueChart(data) {
    const el = document.getElementById("revenue-chart");
    if (!el || !window.Chart) return;
    const labels = (data || []).map(function (d) { return d.date; });
    const values = (data || []).map(function (d) { return d.total; });
    const c = chartDefaults("dark");
    charts.push(new Chart(el, {
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
    const el = document.getElementById("activity-chart");
    if (!el || !window.Chart) return;
    const c = chartDefaults("dark");
    charts.push(new Chart(el, {
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
    const el = document.getElementById("funnel-chart");
    if (!el || !window.Chart) return;
    const c = chartDefaults("dark");
    const labels = (stages || []).map(function (s) { return s.stage; });
    const values = (stages || []).map(function (s) { return s.count; });
    charts.push(new Chart(el, {
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
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(proto + "//" + window.location.host + "/ws/analytics/");
    ws.onmessage = function (event) {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "metrics" && data.metrics) {
          updateLiveKpis(data.metrics);
        }
      } catch (_e) { /* ignore */ }
    };
    ws.onclose = function () {
      setTimeout(connectRealtime, 5000);
    };
  }

  function updateLiveKpis(metrics) {
    const online = document.querySelector('[data-kpi="users.online"]');
    if (online && metrics.online_users !== undefined) {
      online.textContent = metrics.online_users;
    }
    const revenue = document.querySelector('[data-kpi="revenue.today"]');
    if (revenue && metrics.revenue_today !== undefined) {
      revenue.textContent = metrics.revenue_today.toFixed(2);
    }
    if (charts[1] && metrics) {
      charts[1].data.datasets[0].data = [
        metrics.new_registrations || 0,
        metrics.new_messages || 0,
        metrics.new_matches || 0,
        metrics.online_users || 0,
      ];
      charts[1].update();
    }
  }

  document.addEventListener("DOMContentLoaded", async function () {
    initThemeToggle();
    initActivityChart();

    const [revenue, funnel, executive] = await Promise.all([
      fetchJson("/api/analytics/revenue/timeseries/?period=30d"),
      fetchJson("/api/analytics/funnel/?period=30d"),
      fetchJson("/api/analytics/dashboard/executive/"),
    ]);

    initRevenueChart(revenue ? revenue.timeseries : []);
    initFunnelChart(funnel ? funnel.stages : []);

    if (executive && charts[1]) {
      charts[1].data.datasets[0].data = [
        executive.users.dau,
        executive.users.wau,
        executive.users.mau,
        executive.users.online,
      ];
      charts[1].update();
    }

    connectRealtime();
  });
})();
