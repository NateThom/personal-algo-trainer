let current = null;      // current problem
let sessionId = null;    // last handoff session
let hintsUsed = 0;
let editor = null;

async function loadNext() {
  const r = await fetch("/api/next");
  const { problem } = await r.json();
  current = problem;
  if (!problem) {
    document.getElementById("title").textContent = "Nothing due — you're caught up!";
    document.getElementById("statement").textContent = "";
    return;
  }
  document.getElementById("title").textContent = problem.title;
  document.getElementById("statement").textContent = problem.statement;
  document.getElementById("pattern-badge").textContent = "";  // pattern hidden on purpose
  editor.setValue(problem.starter_code);
  document.getElementById("results").textContent = "";
  document.getElementById("handoff").disabled = true;
  document.getElementById("ingest").disabled = true;
  hintsUsed = 0;
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
  document.getElementById("results").textContent +=
    `\n\nSession written: sessions/session-${session_id}.json\n` +
    `In Claude Code, run the tutor on this session, then click "Ingest verdict".`;
  document.getElementById("ingest").disabled = false;
}

async function ingest() {
  const r = await fetch("/api/verdict/ingest", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (r.status === 409) {
    document.getElementById("results").textContent += "\n\nNo verdict yet — run the tutor first.";
    return;
  }
  const res = await r.json();
  document.getElementById("results").textContent +=
    `\n\nGRADE: ${res.grade}\nNext due: ${res.next_due}\nTutor: ${res.feedback}`;
  setTimeout(loadNext, 1500);
}

window.addEventListener("DOMContentLoaded", () => {
  editor = CodeMirror.fromTextArea(document.getElementById("editor"),
    { mode: "python", lineNumbers: true, indentUnit: 4 });
  document.getElementById("run").addEventListener("click", runTests);
  document.getElementById("handoff").addEventListener("click", handoff);
  document.getElementById("ingest").addEventListener("click", ingest);
  loadNext();
});
