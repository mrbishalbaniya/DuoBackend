(function () {
  "use strict";

  var BRAND = Object.assign({
    primary: "#e84a7a",
    accent: "#d4a574",
    love: "#ff4d6d",
    success: "#22c55e",
    warning: "#f59e0b",
    error: "#ef4444",
    tertiary: "#8b5cf6",
  }, window.DuoAnalyticsBrand || {});

  var moduleCharts = {};
  var mapInstance = null;
  var mapLayer = null;

  function theme() {
    var app = document.getElementById("duo-analytics-app");
    return app && app.getAttribute("data-theme") === "light" ? "light" : "dark";
  }

  function chartColors() {
    var isLight = theme() === "light";
    return {
      color: isLight ? "#4b5563" : "#b0b3ba",
      grid: isLight ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.06)",
    };
  }

  function esc(v) {
    return String(v).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function fmtNum(v) {
    if (v === null || v === undefined || v === "") return "—";
    if (typeof v === "number") return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return String(v);
  }

  function fmtPct(v) {
    if (v === null || v === undefined || v === "") return "—";
    return fmtNum(Number(v)) + "%";
  }

  function humanize(v) {
    if (v === null || v === undefined || v === "") return "Unknown";
    return String(v).replace(/[_-]+/g, " ").replace(/\b\w/g, function (ch) { return ch.toUpperCase(); });
  }

  var GENDER_LABELS = {
    M: "Male", MALE: "Male", F: "Female", FEMALE: "Female",
    O: "Other", OTHER: "Other", NB: "Non-binary", "NON-BINARY": "Non-binary",
  };

  function fmtMoney(v) {
    if (v === null || v === undefined) return "—";
    return Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function renderKpis(containerId, items) {
    var el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = items.map(function (item) {
      return '<article class="analytics-kpi-card">' +
        '<span class="kpi-label">' + esc(item.label) + '</span>' +
        '<strong class="kpi-value">' + esc(item.value === null || item.value === undefined ? "—" : item.value) + '</strong>' +
        (item.delta ? '<span class="kpi-delta">' + esc(item.delta) + '</span>' : '') +
        '</article>';
    }).join("");
  }

  function renderTable(containerId, headers, rows) {
    var el = document.getElementById(containerId);
    if (!el) return;
    if (!rows.length) {
      el.innerHTML = '<p class="analytics-empty">No data for this period.</p>';
      return;
    }
    var head = '<thead><tr>' + headers.map(function (h) { return '<th>' + esc(h) + '</th>'; }).join("") + '</tr></thead>';
    var body = '<tbody>' + rows.map(function (row) {
      return '<tr>' + row.map(function (cell) { return '<td>' + esc(cell === null || cell === undefined ? "—" : cell) + '</td>'; }).join("") + '</tr>';
    }).join("") + '</tbody>';
    el.innerHTML = '<table class="analytics-table">' + head + body + '</table>';
  }

  function destroyChart(key) {
    if (moduleCharts[key]) {
      moduleCharts[key].destroy();
      delete moduleCharts[key];
    }
  }

  function makeChart(key, canvasId, config) {
    var canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return null;
    destroyChart(key);
    var c = chartColors();
    config.options = config.options || {};
    config.options.responsive = true;
    config.options.maintainAspectRatio = false;
    if (config.type === "pie" || config.type === "doughnut") {
      // Chart.js sizes round charts from a positioned parent with a fixed height.
      if (!canvas.parentNode.classList.contains("analytics-chart-box")) {
        var box = document.createElement("div");
        box.className = "analytics-chart-box";
        canvas.parentNode.insertBefore(box, canvas);
        box.appendChild(canvas);
      }
      config.options.cutout = config.options.cutout || (config.type === "doughnut" ? "65%" : undefined);
      if (!config.options.plugins) config.options.plugins = {};
      if (!config.options.plugins.legend) {
        config.options.plugins.legend = { position: "bottom", labels: { color: c.color, boxWidth: 10, font: { size: 11 }, padding: 10 } };
      } else if (config.options.plugins.legend.labels) {
        config.options.plugins.legend.labels.color = c.color;
        config.options.plugins.legend.labels.boxWidth = config.options.plugins.legend.labels.boxWidth || 10;
        config.options.plugins.legend.labels.font = config.options.plugins.legend.labels.font || { size: 11 };
      }
    }
    if (config.options.scales) {
      Object.values(config.options.scales).forEach(function (scale) {
        if (scale.ticks) {
          scale.ticks.color = c.color;
          scale.ticks.font = scale.ticks.font || { size: 10 };
          scale.ticks.maxTicksLimit = scale.ticks.maxTicksLimit || 8;
        }
        if (scale.grid) scale.grid.color = scale.grid.display === false ? scale.grid.color : c.grid;
      });
    }
    moduleCharts[key] = new Chart(canvas, config);
    return moduleCharts[key];
  }

  function palette(n) {
    var colors = [BRAND.primary, BRAND.accent, BRAND.love, BRAND.success, BRAND.warning, BRAND.tertiary];
    var out = [];
    for (var i = 0; i < n; i++) out.push(colors[i % colors.length]);
    return out;
  }

  window.DuoAnalyticsModules = {
    destroyAll: function () {
      Object.keys(moduleCharts).forEach(destroyChart);
      if (mapInstance) {
        mapInstance.remove();
        mapInstance = null;
        mapLayer = null;
      }
    },

    refreshThemes: function () {
      var c = chartColors();
      Object.values(moduleCharts).forEach(function (chart) {
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
      });
    },

    loadRevenue: function (data) {
      if (!data) return;
      renderKpis("revenue-kpis", [
        { label: "Gross Revenue", value: fmtMoney(data.totals.gross_revenue) },
        { label: "Net Revenue", value: fmtMoney(data.totals.net_revenue) },
        { label: "Subscriptions", value: fmtMoney(data.totals.subscriptions) },
        { label: "Wallet Top-ups", value: fmtMoney(data.totals.wallet_topups) },
        { label: "Refunds", value: fmtMoney(data.totals.refunds) },
        { label: "Transactions", value: fmtNum(data.totals.transactions) },
      ]);

      var ts = data.timeseries || [];
      makeChart("revenue-ts", "revenue-module-chart", {
        type: "line",
        data: {
          labels: ts.map(function (d) { return d.date; }),
          datasets: [{ label: "Revenue", data: ts.map(function (d) { return d.total; }), borderColor: BRAND.primary, backgroundColor: "rgba(232,74,122,0.12)", fill: true, tension: 0.35 }],
        },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } }, y: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

      var plans = data.by_plan || [];
      makeChart("revenue-plan", "revenue-plan-chart", {
        type: "doughnut",
        data: {
          labels: plans.map(function (p) { return humanize(p.plan_id || "Other"); }),
          datasets: [{ data: plans.map(function (p) { return p.revenue; }), backgroundColor: palette(plans.length) }],
        },
        options: { responsive: true, plugins: { legend: { position: "bottom", labels: { color: chartColors().color } } } },
      });

      renderTable("revenue-plan-table", ["Plan", "Revenue", "Count"], plans.map(function (p) {
        return [humanize(p.plan_id || "Other"), fmtMoney(p.revenue), fmtNum(p.count)];
      }));
    },

    loadUsers: function (data) {
      if (!data) return;
      renderKpis("users-kpis", [
        { label: "Profiles", value: fmtNum(data.totals.profiles) },
        { label: "Verified", value: fmtNum(data.totals.verified) },
        { label: "Onboarded", value: fmtNum(data.totals.onboarded) },
        { label: "Premium", value: fmtNum(data.totals.premium) },
        { label: "Verification Rate", value: fmtPct(data.totals.verification_rate) },
        { label: "Premium Conversion", value: fmtPct(data.totals.premium_conversion) },
      ]);

      var growth = data.growth || [];
      makeChart("users-growth", "users-growth-chart", {
        type: "line",
        data: { labels: growth.map(function (d) { return d.date; }), datasets: [{ data: growth.map(function (d) { return d.registrations; }), borderColor: BRAND.primary, backgroundColor: "rgba(232,74,122,0.12)", fill: true, tension: 0.35 }] },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } }, y: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

      // Stored values mix codes and words ("M", "male"); merge them under one label.
      var genderTotals = {};
      (data.segmentation.gender || []).forEach(function (g) {
        var key = String(g.gender || "").trim().toUpperCase();
        var label = GENDER_LABELS[key] || humanize(g.gender);
        genderTotals[label] = (genderTotals[label] || 0) + g.count;
      });
      var gender = Object.keys(genderTotals).map(function (k) { return { gender: k, count: genderTotals[k] }; })
        .sort(function (a, b) { return b.count - a.count; });
      makeChart("users-gender", "users-gender-chart", {
        type: "pie",
        data: { labels: gender.map(function (g) { return g.gender; }), datasets: [{ data: gender.map(function (g) { return g.count; }), backgroundColor: palette(gender.length) }] },
        options: { responsive: true, plugins: { legend: { position: "bottom", labels: { color: chartColors().color } } } },
      });

      var age = data.segmentation.age_buckets || {};
      makeChart("users-age", "users-age-chart", {
        type: "bar",
        data: { labels: Object.keys(age), datasets: [{ data: Object.values(age), backgroundColor: BRAND.accent, borderRadius: 8 }] },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { display: false } }, y: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

      var platform = data.segmentation.platform || [];
      makeChart("users-platform", "users-platform-chart", {
        type: "doughnut",
        data: { labels: platform.map(function (p) { return humanize(p.platform); }), datasets: [{ data: platform.map(function (p) { return p.count; }), backgroundColor: palette(platform.length) }] },
        options: { responsive: true, plugins: { legend: { position: "bottom", labels: { color: chartColors().color } } } },
      });
    },

    loadMatching: function (data) {
      if (!data) return;
      renderKpis("matching-kpis", [
        { label: "Swipes", value: fmtNum(data.totals.swipes) },
        { label: "Matches", value: fmtNum(data.totals.matches) },
        { label: "Likes", value: fmtNum(data.totals.likes) },
        { label: "Superlikes", value: fmtNum(data.totals.superlikes) },
        { label: "Acceptance Rate", value: fmtPct(data.rates.acceptance_rate) },
        { label: "Avg Compatibility", value: fmtNum(data.averages.compatibility_score) },
      ]);

      var actions = data.distribution.swipes_by_action || [];
      makeChart("matching-swipes", "matching-swipes-chart", {
        type: "bar",
        data: { labels: actions.map(function (a) { return humanize(String(a.action).toLowerCase()); }), datasets: [{ data: actions.map(function (a) { return a.count; }), backgroundColor: palette(actions.length), borderRadius: 8 }] },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { display: false } }, y: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

      var daily = data.distribution.matches_by_day || [];
      makeChart("matching-daily", "matching-daily-chart", {
        type: "line",
        data: { labels: daily.map(function (d) { return d.date; }), datasets: [{ data: daily.map(function (d) { return d.matches; }), borderColor: BRAND.love, backgroundColor: "rgba(255,77,109,0.12)", fill: true, tension: 0.35 }] },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } }, y: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

      renderTable("matching-metrics-table", ["Metric", "Value"], [
        ["Profile Views", fmtNum(data.totals.profile_views)],
        ["Skips", fmtNum(data.totals.skips)],
        ["Rejection Rate", fmtPct(data.rates.rejection_rate)],
        ["Profile View Rate", fmtPct(data.rates.profile_view_rate)],
        ["Time to Match (hrs)", fmtNum(data.averages.time_to_match_hours)],
      ]);
    },

    loadChat: function (data) {
      if (!data) return;
      renderKpis("chat-kpis", [
        { label: "Messages Sent", value: fmtNum(data.totals.messages_sent) },
        { label: "Conversations", value: fmtNum(data.totals.conversations) },
        { label: "Active Conversations", value: fmtNum(data.totals.active_conversations) },
        { label: "Read Rate", value: fmtPct(data.rates.read_rate) },
        { label: "Delivery Rate", value: fmtPct(data.rates.delivery_rate) },
        { label: "Avg Reply (min)", value: fmtNum(data.averages.reply_time_min) },
      ]);

      var timeline = data.timeline || [];
      makeChart("chat-timeline", "chat-timeline-chart", {
        type: "line",
        data: { labels: timeline.map(function (d) { return d.date; }), datasets: [{ data: timeline.map(function (d) { return d.messages; }), borderColor: BRAND.primary, backgroundColor: "rgba(232,74,122,0.12)", fill: true, tension: 0.35 }] },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } }, y: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

      makeChart("chat-types", "chat-types-chart", {
        type: "doughnut",
        data: {
          labels: ["Text", "Images", "Voice", "System"],
          datasets: [{ data: [data.totals.text, data.totals.images, data.totals.voice, data.totals.system], backgroundColor: palette(4) }],
        },
        options: { responsive: true, plugins: { legend: { position: "bottom", labels: { color: chartColors().color } } } },
      });

    },

    loadFunnel: function (data) {
      if (!data) return;
      renderKpis("funnel-kpis", [
        { label: "Entered Funnel", value: fmtNum(data.total_entered) },
        { label: "Overall Conversion", value: fmtPct(data.overall_conversion) },
      ]);

      var stages = data.stages || [];
      makeChart("funnel-module", "funnel-module-chart", {
        type: "bar",
        data: {
          labels: stages.map(function (s) { return humanize(s.stage); }),
          datasets: [{ data: stages.map(function (s) { return s.count; }), backgroundColor: "rgba(212,165,116,0.55)", borderColor: BRAND.accent, borderWidth: 1, borderRadius: 6 }],
        },
        options: { indexAxis: "y", responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } }, y: { ticks: { color: chartColors().color }, grid: { display: false } } } },
      });

      renderTable("funnel-stages-table", ["Stage", "Count", "Rate %", "Drop-off %"], stages.map(function (s) {
        return [humanize(s.stage), fmtNum(s.count), fmtPct(s.rate), fmtPct(s.drop_off)];
      }));
    },

    loadRetention: function (data) {
      if (!data) return;
      renderKpis("retention-kpis", [
        { label: "Returning (7d)", value: fmtNum(data.summary.returning_users) },
        { label: "Inactive", value: fmtNum(data.summary.inactive_users) },
        { label: "Lost Users", value: fmtNum(data.summary.lost_users) },
        { label: "Retention (7d)", value: fmtPct(data.summary.retention_rate_7d) },
        { label: "Churn Rate", value: fmtPct(data.summary.churn_rate) },
      ]);

      var cohorts = data.cohorts || [];
      var periods = ["day_1", "day_7", "day_30", "day_90", "day_180", "day_365"];
      var matrix = document.getElementById("retention-cohort-matrix");
      if (!matrix) return;
      if (!cohorts.length) {
        matrix.innerHTML = '<p class="analytics-empty">No signup cohorts in this period.</p>';
        return;
      }

      var header = '<thead><tr><th>Cohort</th><th>Size</th>' +
        periods.map(function (p) { return '<th>' + p.replace("day_", "D") + '</th>'; }).join("") + '</tr></thead>';
      var rows = cohorts.map(function (c) {
        return '<tr><td>' + esc(c.cohort_date) + '</td><td>' + esc(c.size) + '</td>' +
          periods.map(function (p) {
            var cell = (c.periods && c.periods[p]) ? Number(c.periods[p].rate) || 0 : 0;
            var intensity = Math.max(0, Math.min(100, cell));
            return '<td class="cohort-cell" style="--cohort-intensity:' + intensity + '">' + cell + '%</td>';
          }).join("") + '</tr>';
      }).join("");
      matrix.innerHTML = '<table class="analytics-table cohort-table">' + header + '<tbody>' + rows + '</tbody></table>';
    },

    loadForecast: function (data) {
      if (!data) return;
      var p = data.predictions || {};
      renderKpis("forecast-kpis", [
        { label: "Churn Risk Users", value: fmtNum(p.churn_risk_users) },
        { label: "Premium Candidates", value: fmtNum(p.premium_conversion_candidates) },
        { label: "Inactive 30d", value: fmtNum(p.inactive_users_30d) },
        { label: "Renewal Likelihood", value: fmtPct(p.renewal_likelihood_pct) },
        { label: "Fraud Risk Score", value: fmtNum(p.fraud_risk_score) },
      ]);

      var fc = data.revenue_forecast || [];
      makeChart("forecast-revenue", "forecast-revenue-chart", {
        type: "line",
        data: { labels: fc.map(function (d) { return d.date; }), datasets: [{ data: fc.map(function (d) { return d.predicted_revenue; }), borderColor: BRAND.tertiary, borderDash: [5, 5], tension: 0.3 }] },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } }, y: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

      var trending = data.trending_features || [];
      var trendPanel = document.getElementById("forecast-trending-chart");
      if (trendPanel) {
        var trendWrap = trendPanel.parentNode;
        var trendEmpty = trendWrap.querySelector(".analytics-empty");
        if (trendEmpty) trendEmpty.remove();
        trendPanel.hidden = !trending.length;
        if (!trending.length) trendWrap.insertAdjacentHTML("beforeend", '<p class="analytics-empty">No tracked activity in the last two weeks.</p>');
      }
      makeChart("forecast-trending", "forecast-trending-chart", {
        type: "bar",
        data: { labels: trending.map(function (t) { return humanize(t.feature); }), datasets: [{ data: trending.map(function (t) { return t.growth_pct; }), backgroundColor: BRAND.accent, borderRadius: 8 }] },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { display: false } }, y: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

    },

    loadSecurity: function (data, fraud) {
      if (!data) return;
      renderKpis("security-kpis", [
        { label: "Failed Logins", value: fmtNum(data.totals.failed_logins) },
        { label: "Security Events", value: fmtNum(data.totals.security_events) },
        { label: "User Reports", value: fmtNum(data.totals.user_reports) },
        { label: "Multi-device Users", value: fmtNum(data.totals.multi_device_users) },
        { label: "Blocked Users", value: fmtNum(data.totals.blocked_users) },
        { label: "Suspicious Activity", value: fmtNum(data.suspicious_activity) },
        { label: "Fraud Risk Score", value: fraud ? fmtNum(fraud.risk_score) + " / 100" : "—" },
      ]);

      var events = data.events_by_type || [];
      makeChart("security-events", "security-events-chart", {
        type: "bar",
        data: { labels: events.map(function (e) { return humanize(e.event_type); }), datasets: [{ data: events.map(function (e) { return e.count; }), backgroundColor: BRAND.error, borderRadius: 8 }] },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { display: false } }, y: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

      var signals = (fraud && fraud.signals) || {};
      makeChart("security-fraud", "security-fraud-chart", {
        type: "bar",
        data: {
          labels: ["Fake Profile Reports", "Suspicious Logins", "Rapid-swipe Accounts"],
          datasets: [{ data: [signals.fake_profile_reports || 0, signals.bot_detection_hits || 0, signals.rapid_swipe_accounts || 0], backgroundColor: palette(3), borderRadius: 8 }],
        },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { display: false } }, y: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

    },

    loadMaps: function (data) {
      if (!data) return;
      renderKpis("maps-kpis", [
        { label: "Users with Location", value: fmtNum(data.total_with_location) },
        { label: "Heatmap Zones", value: fmtNum((data.heatmap_zones || []).length) },
        { label: "Top Locations", value: fmtNum((data.popular_locations || []).length) },
      ]);

      var countries = data.country_distribution || [];
      makeChart("maps-country", "maps-country-chart", {
        type: "bar",
        data: { labels: countries.slice(0, 10).map(function (c) { return c.country; }), datasets: [{ data: countries.slice(0, 10).map(function (c) { return c.count; }), backgroundColor: BRAND.primary, borderRadius: 8 }] },
        options: { indexAxis: "y", responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { color: chartColors().grid } }, y: { ticks: { color: chartColors().color }, grid: { display: false } } } },
      });

      var cities = data.city_distribution || data.popular_locations || [];
      renderTable("maps-locations-table", ["Location", "Users"], cities.slice(0, 15).map(function (c) {
        return [c.location || c.city || "—", fmtNum(c.count)];
      }));

      var mapEl = document.getElementById("analytics-map");
      if (!mapEl || !window.L) return;
      if (mapInstance) {
        mapInstance.remove();
        mapInstance = null;
      }
      mapInstance = L.map(mapEl, { scrollWheelZoom: false }).setView([27.7, 85.3], 7);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
        className: "duo-map-tiles",
      }).addTo(mapInstance);

      var zones = data.heatmap_zones || [];
      var bounds = [];
      zones.forEach(function (zone) {
        if (zone.lat == null || zone.lng == null || isNaN(zone.lat) || isNaN(zone.lng)) return;
        var radiusMeters = Math.max(2500, (zone.radius_km || 8) * 1000);
        var color = zone.level === "viral" ? BRAND.love : zone.level === "trending" ? BRAND.primary : zone.level === "high" ? BRAND.accent : "#6b7280";
        var circle = L.circle([zone.lat, zone.lng], {
          radius: radiusMeters,
          color: color,
          fillColor: color,
          fillOpacity: 0.38,
          weight: 1,
        }).addTo(mapInstance);
        circle.bindTooltip(
          "<strong>" + esc(zone.name || "Zone") + "</strong><br>" +
          "Score: " + (zone.score || 0) + "<br>" +
          "Active users: " + (zone.active_users || 0) + "<br>" +
          "Matches: " + (zone.matches || 0) + " · Messages: " + (zone.messages || 0),
          { sticky: true }
        );
        bounds.push([zone.lat, zone.lng]);
      });
      if (bounds.length === 1) {
        mapInstance.setView(bounds[0], 10);
      } else if (bounds.length > 1) {
        mapInstance.fitBounds(bounds, { padding: [36, 36], maxZoom: 11 });
      }
      setTimeout(function () { if (mapInstance) mapInstance.invalidateSize(); }, 200);
    },

    loadSystem: function (data) {
      if (!data) return;
      var res = data.resources || {};
      renderKpis("system-kpis", [
        { label: "API Latency", value: fmtNum(data.api.response_time_ms) + " ms" },
        { label: "API Status", value: humanize(data.api.status) },
        { label: "CPU", value: fmtPct(res.cpu_pct) },
        { label: "Memory", value: fmtPct(res.memory_pct) },
        { label: "Storage", value: fmtPct(res.storage_usage_pct) },
        { label: "DB Engine", value: humanize(data.database.engine) },
      ]);

      makeChart("system-resources", "system-resources-chart", {
        type: "bar",
        data: { labels: ["CPU", "Memory", "Storage"], datasets: [{ data: [res.cpu_pct, res.memory_pct, res.storage_usage_pct], backgroundColor: [BRAND.primary, BRAND.accent, BRAND.warning], borderRadius: 8 }] },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: chartColors().color }, grid: { display: false } }, y: { max: 100, ticks: { color: chartColors().color }, grid: { color: chartColors().grid } } } },
      });

      renderTable("system-status-table", ["Service", "Status", "Details"], [
        ["Database", data.database.healthy ? "Healthy" : "Down", data.database.latency_ms + " ms"],
        ["Cache", data.cache.healthy ? "Healthy" : "Down", data.cache.backend],
        ["Redis", data.redis.healthy ? "Healthy" : "Not configured", data.redis.configured ? "Configured" : "Missing REDIS_URL"],
        ["WebSocket", data.websocket.channels_enabled ? "Enabled" : "Disabled", data.websocket.backend || "—"],
      ]);
    },
  };
})();
