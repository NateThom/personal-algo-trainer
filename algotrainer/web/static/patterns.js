// Pattern library index: fetches /api/patterns and renders a card grid.
// Built with DOM methods (textContent) — never innerHTML of doc content.
function buildCard(p) {
  const a = document.createElement("a");
  a.className = "pattern-card";
  a.href = `/patterns/${p.id}`;

  const title = document.createElement("h3");
  title.textContent = p.name;
  a.appendChild(title);

  const summary = document.createElement("p");
  summary.className = "pattern-card-summary";
  summary.textContent = p.summary || "No reference doc yet.";
  a.appendChild(summary);

  const tag = document.createElement("span");
  tag.className = p.has_doc ? "tag tag-documented" : "tag tag-stub";
  tag.textContent = p.has_doc ? "documented" : "stub";
  a.appendChild(tag);

  return a;
}

async function loadPatterns() {
  const grid = document.getElementById("pattern-grid");
  const res = await fetch("/api/patterns");
  const { patterns } = await res.json();
  grid.textContent = "";
  for (const p of patterns) {
    grid.appendChild(buildCard(p));
  }
}

window.addEventListener("DOMContentLoaded", loadPatterns);
