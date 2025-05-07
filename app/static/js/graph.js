
/* ---------- color palette per node kind ---------- */
const COLORS = { PAGE:"#64748b", ORG:"#2563eb", PERSON:"#16a34a",
                 GPE:"#9333ea", PRODUCT:"#d97706", GENERIC:"#525252" };

/* ---------- Drawflow init ---------- */
const canvas = new Drawflow(document.getElementById("df"), { nav:true });
canvas.start();

/* ---------- helper to create node HTML ---------- */
function nodeHTML(label, kind){
  const c = COLORS[kind] || COLORS.GENERIC;
  return `<div style="background:${c}" class="rounded-xl px-3 py-2 shadow text-white">
            <span class="text-xs opacity-70">${kind}</span><br>
            <span class="font-semibold">${label}</span>
          </div>`;
}

/* ---------- load initial graph ---------- */
async function loadGraph(){
  const [nodes, edges] = await Promise.all([
    fetch("/api/nodes").then(r=>r.json()),
    fetch("/api/edges").then(r=>r.json())
  ]);

  // map DB id → drawflow id
  const idMap = {};
  nodes.forEach((n,i)=>{
    idMap[n.id] = canvas.addNode(n.name,1,1,n.x||100,n.y||100,"node",{},
                                 nodeHTML(n.name,n.kind));
  });
  edges.forEach(e=>{
    canvas.addConnection(idMap[e.source_id], idMap[e.target_id],
                         "output_1","input_1");
  });
}
loadGraph();

/* ---------- ask AI directly from graph page ---------- */
document.getElementById("askForm").addEventListener("submit", async ev=>{
  ev.preventDefault();
  const q = document.getElementById("question").value.trim();
  if(!q) return;
  // POST to back‑end / (reuse existing route)
  const formData = new URLSearchParams({question:q});
  const res = await fetch("/", {method:"POST", body:formData});
  const html = await res.text();
  const parser = new DOMParser();
  const answer = parser.parseFromString(html, "text/html")
                       .querySelector("p")?.innerText || "No answer.";
  document.getElementById("summary").innerText = answer;
});

/* ---------- toggles ---------- */
const left = document.getElementById("left");
const right = document.getElementById("right");
document.getElementById("toggleLeft").onclick = ()=>left.classList.toggle("hidden");
document.getElementById("toggleRight").onclick = ()=>right.classList.toggle("hidden");

/* ---------- canvas theme toggle ---------- */
let light = false;
document.getElementById("toggleMode").onclick = ()=>{
  light = !light;
  document.getElementById("df").classList.toggle("bg-gray-200", light);
  document.getElementById("df").classList.toggle("bg-gray-900", !light);
  // grid overlay
  document.getElementById("df").style.backgroundImage =
    light
    ? "linear-gradient(90deg,#ddd 1px,transparent 1px),linear-gradient(#ddd 1px,transparent 1px)"
    : "linear-gradient(90deg,#222 1px,transparent 1px),linear-gradient(#222 1px,transparent 1px)";
};

/* ---------- default canvas styling ---------- */
document.getElementById("df").classList.add("bg-gray-900");
document.getElementById("df").style.backgroundSize="20px 20px";
document.getElementById("df").style.backgroundImage=
  "linear-gradient(90deg,#222 1px,transparent 1px),linear-gradient(#222 1px,transparent 1px)";
