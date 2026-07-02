// Dedicated dashboard: due queue, per-pattern mastery table, error journal.
function tile(label, value) {
  return `<div class="tile"><div class="tile-val">${value}</div>` +
         `<div class="tile-label">${label}</div></div>`;
}

function statusCell(p) {
  if (p.memorization_trap) return `<span class="mtrap">⚠ memorizing</span>`;
  if (p.mastered) return `<span class="mgate">✓ mastered</span>`;
  return `<span class="mprog">in progress</span>`;
}

async function loadDashboard() {
  const d = await (await fetch("/api/dashboard")).json();
  const mastered = d.patterns.filter((p) => p.mastered).length;

  document.getElementById("stats").textContent =
    `${d.due_count} due · ${d.total_problems} problems · ${mastered}/${d.patterns.length} mastered`;

  document.getElementById("tiles").innerHTML =
    tile("Due now", d.due_count) +
    tile("Problems", d.total_problems) +
    tile("Patterns tracked", d.patterns.length) +
    tile("Patterns mastered", mastered);

  const rows = document.getElementById("mastery-rows");
  if (!d.patterns.length) {
    rows.innerHTML = `<tr><td colspan="8">No data yet — solve a problem.</td></tr>`;
  } else {
    rows.innerHTML = d.patterns.map((p) =>
      `<tr class="${p.mastered ? "mastered" : ""}">` +
      `<td>${p.name}</td>` +
      `<td>${p.mastery_score.toFixed(2)}</td>` +
      `<td>${p.transfer_breadth}</td>` +
      `<td>${(p.pattern_id_accuracy * 100).toFixed(0)}%</td>` +
      `<td>${(p.optimal_rate * 100).toFixed(0)}%</td>` +
      `<td>${p.attempts}</td>` +
      `<td>${p.instances}` +
      (p.needs_more > 0 ? ` <span class="mgenmore" title="Needs ${p.needs_more} more instance(s) to reach the mastery gate">⚙ generate more</span>` : "") +
      `</td>` +
      `<td>${statusCell(p)}</td>` +
      `</tr>`).join("");
  }

  const ec = d.error_counts || {};
  const keys = Object.keys(ec);
  document.getElementById("error-body").innerHTML = keys.length
    ? keys.sort((a, b) => ec[b] - ec[a])
        .map((k) => `<div class="erow"><span>${k}</span><span>${ec[k]}</span></div>`).join("")
    : "No errors logged yet.";
}

window.addEventListener("DOMContentLoaded", loadDashboard);
