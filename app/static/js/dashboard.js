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

  // Competitor coverage — grouped bar (sources + mentions)
  const cov = data.coverage_per_competitor || {};
  const covNames = Object.keys(cov);
  if (covNames.length) {
    Plotly.newPlot("competitor_coverage", [
      {
        type: "bar",
        name: "sources",
        x: covNames,
        y: covNames.map(n => cov[n].sources),
        marker: { color: "#10b981" },
      },
      {
        type: "bar",
        name: "mentions",
        x: covNames,
        y: covNames.map(n => cov[n].mentions),
        marker: { color: "#6366f1" },
      },
    ], { ...LAYOUT, title: "Competitor coverage", barmode: "group" }, { displayModeBar: false });
  } else {
    document.getElementById("competitor_coverage").innerHTML =
      '<div class="text-xs text-gray-500 p-4">No competitor pages scraped for this analysis.</div>';
  }

  // Sentiment per competitor — bar
  const cs = data.avg_sentiment_per_competitor || {};
  const csNames = Object.keys(cs);
  if (csNames.length) {
    Plotly.newPlot("competitor_sentiment", [{
      type: "bar",
      x: csNames,
      y: csNames.map(n => cs[n]),
      marker: { color: csNames.map(n => cs[n] >= 0 ? "#10b981" : "#ef4444") },
    }], {
      ...LAYOUT,
      title: "Avg sentiment of mentions on each competitor's pages",
      yaxis: { range: [-1, 1], zeroline: true, zerolinecolor: "#4b5563" },
    }, { displayModeBar: false });
  } else {
    document.getElementById("competitor_sentiment").innerHTML =
      '<div class="text-xs text-gray-500 p-4">No scored mentions from competitor pages yet.</div>';
  }

  // Top entities per competitor — heatmap
  const tep = data.top_entities_per_competitor || { competitors: [], entities: [], matrix: [] };
  if (tep.competitors.length && tep.entities.length) {
    Plotly.newPlot("competitor_entities", [{
      type: "heatmap",
      x: tep.competitors,
      y: tep.entities,
      z: tep.matrix,
      colorscale: "Viridis",
      hoverongaps: false,
      colorbar: { tickfont: { color: "#e5e7eb" } },
    }], {
      ...LAYOUT,
      title: "Top entities per competitor",
      margin: { ...LAYOUT.margin, l: 160, b: 120 },
      xaxis: { tickangle: -30 },
    }, { displayModeBar: false });
  } else {
    document.getElementById("competitor_entities").innerHTML =
      '<div class="text-xs text-gray-500 p-4">No competitor entity data yet.</div>';
  }

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
