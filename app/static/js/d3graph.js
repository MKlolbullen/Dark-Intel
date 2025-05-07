const colorMap = {
  PAGE: "#64748b", ORG: "#2563eb", PERSON: "#16a34a",
  GPE: "#9333ea", PRODUCT: "#d97706", GENERIC: "#525252"
};

let theme = localStorage.getItem("theme") || "dark";
setTheme(theme);

document.getElementById("toggleTheme").onclick = () => {
  theme = theme === "dark" ? "light" : "dark";
  setTheme(theme);
};

function setTheme(t) {
  localStorage.setItem("theme", t);
  document.documentElement.classList.toggle("dark", t === "dark");
  document.body.className = t === "dark" ? "bg-gray-900 text-white" : "bg-white text-black";
}

document.getElementById("reload").onclick = drawGraph;

async function drawGraph() {
  const svg = d3.select("#graph").html("");
  const tooltip = d3.select("#tooltip");
  const width = +svg.node().getBoundingClientRect().width;
  const height = +svg.node().getBoundingClientRect().height;

  const [nodes, edges] = await Promise.all([
    fetch("/api/nodes").then(r => r.json()),
    fetch("/api/edges").then(r => r.json())
  ]);

  const nodeById = {};
  nodes.forEach((n, i) => nodeById[n.id] = { ...n, index: i });

  const links = edges.map(e => ({
    source: nodeById[e.source_id],
    target: nodeById[e.target_id],
    relation: e.relation
  }));

  const sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).distance(120).strength(1))
    .force("charge", d3.forceManyBody().strength(-400))
    .force("center", d3.forceCenter(width / 2, height / 2));

  const link = svg.append("g")
    .selectAll("line")
    .data(links).enter()
    .append("line")
    .attr("stroke", "#aaa");

  const linkLabel = svg.append("g")
    .selectAll("text")
    .data(links).enter()
    .append("text")
    .text(d => d.relation)
    .attr("font-size", 10)
    .attr("fill", "#888");

  const node = svg.append("g")
    .selectAll("circle")
    .data(nodes).enter()
    .append("circle")
    .attr("r", 12)
    .attr("fill", d => colorMap[d.kind] || "#999")
    .call(drag(sim))
    .on("mouseover", (e, d) => {
      tooltip.style("left", `${e.pageX + 10}px`)
             .style("top", `${e.pageY}px`)
             .text(`${d.name} (${d.kind})`)
             .classed("hidden", false);
    })
    .on("mouseout", () => tooltip.classed("hidden", true));

  sim.on("tick", () => {
    link
      .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);

    node
      .attr("cx", d => d.x).attr("cy", d => d.y);

    linkLabel
      .attr("x", d => (d.source.x + d.target.x) / 2)
      .attr("y", d => (d.source.y + d.target.y) / 2);
  });
}
drawGraph();

function drag(sim) {
  return d3.drag()
    .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
    .on("end", (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; });
}

document.getElementById("askForm").onsubmit = async ev => {
  ev.preventDefault();
  const q = document.getElementById("question").value.trim();
  if (!q) return;
  const res = await fetch("/", { method: "POST", body: new URLSearchParams({ question: q }) });
  const html = await res.text();
  const doc = new DOMParser().parseFromString(html, "text/html");
  const ans = doc.querySelector("p")?.innerText || "No answer.";
  document.getElementById("summary").innerText = ans;
};
