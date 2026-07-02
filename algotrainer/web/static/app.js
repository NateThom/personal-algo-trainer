let current = null;      // current problem
let sessionId = null;    // last handoff session
let hintsUsed = 0;
let nextHintTier = 0;
let editor = null;
let pollTimer = null;

async function checkVerdict() {
  if (!sessionId) { clearInterval(pollTimer); return; }
  const r = await fetch(`/api/verdict/status?session_id=${sessionId}`);
  const { ready } = await r.json();
  if (ready) {
    clearInterval(pollTimer);
    const b = document.getElementById("ingest");
    b.disabled = false;
    b.textContent = "Verdict ready — ingest";
  }
}

function renderPoolBanner(pool) {
  const el = document.getElementById("pool-banner");
  if (!pool) { el.hidden = true; el.textContent = ""; return; }
  const parts = [];
  if (pool.unseen === 0) {
    parts.push(
      `You've seen every problem in this problem's pattern pool (${pool.total} total) — ` +
      `ask the Claude tutor to generate a variant (see the Guide), then click Reload problems.`
    );
  }
  if (pool.needs_more > 0) {
    parts.push(
      `This pattern needs ${pool.needs_more} more instance(s) before it can reach the ` +
      `mastery gate.`
    );
  }
  if (!parts.length) { el.hidden = true; el.textContent = ""; return; }
  el.hidden = false;
  el.textContent = parts.join(" ");
}

async function loadNext() {
  const r = await fetch("/api/next");
  const { problem } = await r.json();
  current = problem;
  if (!problem) {
    document.getElementById("title").textContent = "Nothing due — you're caught up!";
    document.getElementById("statement").textContent = "";
    document.getElementById("seen-badge").textContent = "";
    document.getElementById("pool-banner").hidden = true;
    return;
  }
  document.getElementById("title").textContent = problem.title;
  document.getElementById("statement").textContent = problem.statement;
  document.getElementById("seen-badge").textContent = problem.seen_count === 0
    ? "🆕 New"
    : `🔁 Review · seen ${problem.seen_count}×`;
  renderPoolBanner(problem.pattern_pool);
  editor.setValue(problem.starter_code);
  document.getElementById("results").textContent = "";
  document.getElementById("handoff").disabled = true;
  document.getElementById("ingest").disabled = true;
  document.getElementById("ingest").textContent = "Ingest verdict";
  clearInterval(pollTimer);
  hintsUsed = 0;
  nextHintTier = 0;
  document.getElementById("hints").innerHTML = "";
  document.getElementById("hint").disabled = false;
}

async function runTests() {
  const r = await fetch("/api/judge", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ problem_id: current.id, code: editor.getValue() }),
  });
  const res = await r.json();
  window._lastPassed = res.passed;
  document.getElementById("results").textContent =
    (res.passed ? "ALL TESTS PASSED\n\n" : "SOME TESTS FAILED\n\n") +
    (res.error ? "Error: " + res.error + "\n" : "") +
    res.cases.map((c, i) =>
      `#${i + 1} ${c.passed ? "ok" : "FAIL"} args=${JSON.stringify(c.args)} ` +
      `expected=${JSON.stringify(c.expected)} got=${JSON.stringify(c.got)}` +
      (c.error ? " err=" + c.error : "")).join("\n");
  document.getElementById("handoff").disabled = false;
}

async function handoff() {
  const recall = {
    pattern: document.getElementById("r-pattern").value,
    approach: document.getElementById("r-approach").value,
    complexity: document.getElementById("r-complexity").value,
  };
  const r = await fetch("/api/session", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      problem_id: current.id, code: editor.getValue(), recall,
      judge_passed: !!window._lastPassed, hints_used: hintsUsed,
    }),
  });
  const { session_id } = await r.json();
  sessionId = session_id;
  localStorage.setItem("algotrainer.sessionId", session_id);
  document.getElementById("results").textContent +=
    `\n\nSession written: sessions/session-${session_id}.json\n` +
    `In Claude Code, run the tutor on this session, then click "Ingest verdict".`;
  document.getElementById("ingest").disabled = false;
  document.getElementById("copy-cmd").disabled = false;
  clearInterval(pollTimer);
  pollTimer = setInterval(checkVerdict, 5000);
}

async function ingest() {
  document.getElementById("ingest").disabled = true;
  const r = await fetch("/api/verdict/ingest", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (r.status === 409) {
    document.getElementById("results").textContent += "\n\nNo verdict yet — run the tutor first.";
    document.getElementById("ingest").disabled = false;
    return;
  }
  const res = await r.json();
  document.getElementById("results").textContent +=
    `\n\nGRADE: ${res.grade}\nNext due: ${res.next_due}\nTutor: ${res.feedback}`;
  localStorage.removeItem("algotrainer.sessionId");
  sessionId = null;
  clearInterval(pollTimer);
  document.getElementById("copy-cmd").disabled = true;
  loadMastery();
  loadDashboard();
  setTimeout(loadNext, 1500);
}

async function copyTutorCommand() {
  await navigator.clipboard.writeText(
    `Use the algotrainer-tutor skill to grade session ${sessionId}.`);
  const b = document.getElementById("copy-cmd");
  b.textContent = "Copied!";
  setTimeout(() => { b.textContent = "Copy tutor command"; }, 1500);
}

function restoreSession() {
  sessionId = localStorage.getItem("algotrainer.sessionId");
  if (sessionId) {
    document.getElementById("ingest").disabled = false;
    document.getElementById("copy-cmd").disabled = false;
    clearInterval(pollTimer);
    pollTimer = setInterval(checkVerdict, 5000);
  }
}

async function getHint() {
  const r = await fetch("/api/hint", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ problem_id: current.id, tier: nextHintTier }),
  });
  const { hint, has_more } = await r.json();
  if (hint == null) { document.getElementById("hint").disabled = true; return; }
  const div = document.createElement("div");
  div.className = "hint-item";
  div.textContent = `Hint ${nextHintTier + 1}: ${hint}`;
  document.getElementById("hints").appendChild(div);
  nextHintTier += 1;
  hintsUsed += 1;
  if (!has_more) document.getElementById("hint").disabled = true;
}

async function loadMastery() {
  const r = await fetch("/api/mastery");
  const { patterns } = await r.json();
  const body = document.getElementById("mastery-body");
  if (!patterns.length) { body.textContent = "No data yet — solve a problem."; return; }
  body.innerHTML = patterns.map(p =>
    `<div class="mrow${p.mastered ? " mastered" : ""}">` +
    `<span class="mname">${p.name}</span>` +
    `<span class="mscore">score ${p.mastery_score.toFixed(2)}</span>` +
    `<span class="mbreadth">breadth ${p.transfer_breadth}</span>` +
    (p.memorization_trap ? `<span class="mtrap">⚠ memorizing, not recognizing</span>` : "") +
    (p.mastered ? `<span class="mgate">✓ mastered</span>` : "") +
    `</div>`).join("");
}

async function loadDashboard() {
  const r = await fetch("/api/dashboard");
  const d = await r.json();
  const mastered = d.patterns.filter(p => p.mastered).length;
  document.getElementById("stats").textContent =
    `${d.due_count} due · ${d.total_problems} problems · ${mastered}/${d.patterns.length} patterns mastered`;
}

window.addEventListener("DOMContentLoaded", async () => {
  editor = CodeMirror.fromTextArea(document.getElementById("editor"),
    { mode: "python", lineNumbers: true, indentUnit: 4 });
  document.getElementById("hint").addEventListener("click", getHint);
  document.getElementById("run").addEventListener("click", runTests);
  document.getElementById("handoff").addEventListener("click", handoff);
  document.getElementById("ingest").addEventListener("click", ingest);
  document.getElementById("copy-cmd").addEventListener("click", copyTutorCommand);
  await loadNext();
  restoreSession();
  loadMastery();
  loadDashboard();
});
