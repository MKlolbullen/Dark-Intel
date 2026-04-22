const PALETTE = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];
const LAYOUT = {
  paper_bgcolor: "#111827",
  plot_bgcolor: "#111827",
  font: { color: "#e5e7eb", family: "ui-sans-serif" },
  margin: { l: 50, r: 20, t: 40, b: 50 },
};

(async function () {
  const status = document.getElementById("status");
  status.textContent = "Scoring sentiment and aggregating… this can take a minute on a fresh analysis.";

  const res = await fetch(`/api/analysis/${window.ANALYSIS_ID}/charts`);
  if (!res.ok) {
    status.textContent = `Failed to load charts (${res.status}).`;
    return;
  }
  const data = await res.json();
  status.textContent = "";

  // Source mix — pie
  const mixKinds = Object.keys(data.source_mix || {});
  Plotly.newPlot("source_mix", [{
    type: "pie",
    labels: mixKinds,
    values: mixKinds.map(k => data.source_mix[k]),
    marker: { colors: PALETTE },
    hole: 0.4,
  }], { ...LAYOUT, title: "Sources by channel" }, { displayModeBar: false });

  // Average sentiment by kind — bar
  const avg = data.avg_sentiment_by_kind || {};
  const avgKinds = Object.keys(avg);
  Plotly.newPlot("avg_sentiment", [{
    type: "bar",
    x: avgKinds,
    y: avgKinds.map(k => avg[k]),
    marker: { color: avgKinds.map(k => avg[k] >= 0 ? "#10b981" : "#ef4444") },
  }], {
    ...LAYOUT,
    title: "Average sentiment by channel",
    yaxis: { range: [-1, 1], zeroline: true, zerolinecolor: "#4b5563" },
  }, { displayModeBar: false });

  // Sentiment distribution — histogram-ish bar
  const dist = data.sentiment_distribution || { bins: [], counts: [] };
  Plotly.newPlot("sentiment_dist", [{
    type: "bar",
    x: dist.bins,
    y: dist.counts,
    marker: { color: "#6366f1" },
  }], { ...LAYOUT, title: "Sentiment distribution" }, { displayModeBar: false });

  // Top entities — horizontal bar
  const top = (data.top_entities || []).slice().reverse();
  Plotly.newPlot("top_entities", [{
    type: "bar",
    orientation: "h",
    y: top.map(([name, _]) => name),
    x: top.map(([_, count]) => count),
    marker: { color: "#8b5cf6" },
  }], {
    ...LAYOUT,
    title: "Top entities by mention",
    margin: { ...LAYOUT.margin, l: 140 },
  }, { displayModeBar: false });

  // Mentions over time — line
  const tl = data.mentions_over_time || { days: [], counts: [] };
  Plotly.newPlot("timeline", [{
    type: "scatter",
    mode: "lines+markers",
    x: tl.days,
    y: tl.counts,
    line: { color: "#06b6d4" },
  }], { ...LAYOUT, title: "Mentions over time" }, { displayModeBar: false });
})();
