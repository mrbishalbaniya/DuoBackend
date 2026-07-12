(function () {
  "use strict";

  function connect() {
    var proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    var ws;
    try {
      ws = new WebSocket(proto + "//" + window.location.host + "/ws/analytics/");
    } catch (e) {
      return;
    }

    ws.onmessage = function (event) {
      try {
        var data = JSON.parse(event.data);
        if (data.type === "metrics" && data.metrics) {
          updateLive(data.metrics);
        }
      } catch (_e) { /* ignore */ }
    };

    ws.onclose = function () {
      setTimeout(connect, 5000);
    };
  }

  function updateLive(metrics) {
    var fields = {
      online_users: metrics.online_users,
      matches_today: metrics.new_matches,
      messages_today: metrics.new_messages,
      todays_revenue: metrics.revenue_today,
    };
    Object.keys(fields).forEach(function (key) {
      var el = document.querySelector('[data-field="' + key + '"]');
      if (el && fields[key] !== undefined) {
        el.textContent = key.indexOf("revenue") >= 0 ? Number(fields[key]).toFixed(2) : fields[key];
      }
    });

    var status = document.getElementById("portal-live-status");
    if (status) status.textContent = "Live · " + new Date().toLocaleTimeString();
  }

  document.addEventListener("DOMContentLoaded", connect);
})();
