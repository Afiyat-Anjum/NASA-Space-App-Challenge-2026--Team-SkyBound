let currentMode = "harmonised";
let staticBundle = null;

function setMode(mode) {
  currentMode = mode;
  document.getElementById("btnHarm").classList.toggle("active", mode === "harmonised");
  document.getElementById("btnRaw").classList.toggle("active", mode === "raw");
  refreshDashboard();
}

async function loadData(country, targetDate) {
  try {
    const [mRes, aRes, dRes] = await Promise.all([
      fetch("/api/metrics"),
      fetch(`/api/anomaly?country=${encodeURIComponent(country)}&target_date=${targetDate}&mode=${currentMode}`),
      fetch(`/api/daily/${encodeURIComponent(country)}`)
    ]);
    if (mRes.ok && aRes.ok && dRes.ok) {
      return { metrics: await mRes.json(), anomaly: await aRes.json(), daily: await dRes.json() };
    }
  } catch (e) {}

  if (!staticBundle) {
    const res = await fetch("../demo_fixtures/web_static_cache.json");
    staticBundle = await res.json();
  }
  const daily = staticBundle.daily[country] || [];
  return { metrics: staticBundle.metrics, anomaly: null, daily };
}

async function refreshDashboard() {
  const country = document.getElementById("countrySelect").value;
  const targetDate = document.getElementById("dateInput").value;
  const { metrics, anomaly, daily } = await loadData(country, targetDate);

  const cm = (metrics.by_country && metrics.by_country[country]) || metrics;
  document.getElementById("metricsRow").innerHTML = `
    <div class="metric-card"><div class="metric-label">Raw MODIS vs VIIRS (r)</div><div class="metric-value">${cm.r_raw.toFixed(4)}</div></div>
    <div class="metric-card"><div class="metric-label">Harmonised MODIS vs VIIRS (r)</div><div class="metric-value">${cm.r_harmonised.toFixed(4)}</div></div>
    <div class="metric-card"><div class="metric-label">Sensor Overlap Days</div><div class="metric-value">${cm.overlap_days.toLocaleString()}</div></div>
    <div class="metric-card"><div class="metric-label">Spatial Grid &amp; Confidence</div><div class="metric-value">${metrics.cell_size_km} km | &ge;${metrics.confidence_min}</div></div>
  `;

  if (anomaly && anomaly.status === "OK") {
    document.getElementById("anomalyBox").innerHTML =
      `<strong>Is this unusual? ${anomaly.verdict}</strong> — On <strong>${anomaly.date}</strong> in <strong>${country.replace("_", " ")}</strong>, activity was <strong>${anomaly.current_value.toLocaleString()}</strong> (<strong>${anomaly.percentile}th percentile</strong> vs. &plusmn;7-day baseline median ${anomaly.baseline_median}, 90th pct ${anomaly.baseline_p90}).`;
  }

  const valKey = currentMode === "harmonised" ? "harmonised_count" : "raw_count";
  const years = [...new Set(daily.map(d => d.year))].sort();
  const doys = Array.from({ length: 365 }, (_, i) => i + 1);
  const zGrid = years.map(y => {
    const row = new Array(365).fill(0);
    daily.filter(d => d.year === y).forEach(d => { if (d.doy >= 1 && d.doy <= 365) row[d.doy - 1] = d[valKey]; });
    return row;
  });

  Plotly.newPlot("calendarChart", [{
    z: zGrid, x: doys, y: years, type: "heatmap", colorscale: "YlOrRd"
  }], { paper_bgcolor: "#181c26", plot_bgcolor: "#181c26", font: { color: "#f3f4f6" }, margin: { t: 10, l: 45, r: 10, b: 35 } }, { responsive: true });

  Plotly.newPlot("seriesChart", [{
    x: daily.map(d => d.date), y: daily.map(d => d[valKey]), type: "scatter", mode: "lines", line: { color: "#fd8d3c", width: 1.2 }
  }], { paper_bgcolor: "#181c26", plot_bgcolor: "#181c26", font: { color: "#f3f4f6" }, margin: { t: 10, l: 45, r: 10, b: 35 } }, { responsive: true });
}

document.getElementById("countrySelect").addEventListener("change", refreshDashboard);
document.getElementById("dateInput").addEventListener("change", refreshDashboard);
refreshDashboard();
