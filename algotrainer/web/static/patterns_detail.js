// Pattern detail page: reads the pattern id from the URL path, fetches
// /api/patterns/<id>, and renders with DOM methods (textContent) — the
// doc content is untrusted-ish free text, never injected as innerHTML.

function patternIdFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts[parts.length - 1];
}

function section(titleText) {
  const sec = document.createElement("section");
  const h2 = document.createElement("h2");
  h2.textContent = titleText;
  sec.appendChild(h2);
  return sec;
}

function bulletList(items) {
  const ul = document.createElement("ul");
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = item;
    ul.appendChild(li);
  }
  return ul;
}

function renderNotFound(body, pid) {
  document.getElementById("pattern-title").textContent = "Pattern not found";
  const p = document.createElement("p");
  p.textContent = `No pattern with id "${pid}" exists.`;
  body.appendChild(p);
}

function renderPattern(body, p, nameToId) {
  document.getElementById("pattern-title").textContent = p.name;

  const summary = document.createElement("p");
  summary.className = "lede";
  summary.textContent = p.summary || "No reference doc has been written for this pattern yet.";
  body.appendChild(summary);

  if (p.recognize_when.length) {
    const sec = section("Recognize when");
    sec.appendChild(bulletList(p.recognize_when));
    body.appendChild(sec);
  }

  if (p.complexity && (p.complexity.time || p.complexity.space)) {
    const sec = section("Complexity");
    const pre = document.createElement("p");
    pre.textContent = `Time: ${p.complexity.time || "?"}  ·  Space: ${p.complexity.space || "?"}`;
    sec.appendChild(pre);
    if (p.complexity.notes) {
      const notes = document.createElement("p");
      notes.className = "note";
      notes.textContent = p.complexity.notes;
      sec.appendChild(notes);
    }
    body.appendChild(sec);
  }

  if (p.template) {
    const sec = section("Template");
    const pre = document.createElement("pre");
    pre.className = "code-template";
    pre.textContent = p.template;
    sec.appendChild(pre);
    body.appendChild(sec);
  }

  if (p.gotchas.length) {
    const sec = section("Gotchas");
    sec.appendChild(bulletList(p.gotchas));
    body.appendChild(sec);
  }

  if (p.examples.length) {
    const sec = section("Examples");
    sec.appendChild(bulletList(p.examples));
    body.appendChild(sec);
  }

  if (p.confusable.length) {
    const sec = section("Often confused with");
    const div = document.createElement("div");
    div.className = "confusable-links";
    for (const name of p.confusable) {
      const targetId = nameToId.get(name);
      const el = targetId ? document.createElement("a") : document.createElement("span");
      if (targetId) el.href = `/patterns/${targetId}`;
      el.textContent = name;
      div.appendChild(el);
    }
    sec.appendChild(div);
    body.appendChild(sec);
  }

  if (p.seed_examples.length) {
    const sec = section("Seed problems using this pattern");
    sec.appendChild(bulletList(p.seed_examples));
    body.appendChild(sec);
  }
}

async function loadPattern() {
  const pid = patternIdFromPath();
  const body = document.getElementById("pattern-body");
  const [detailRes, listRes] = await Promise.all([
    fetch(`/api/patterns/${encodeURIComponent(pid)}`),
    fetch("/api/patterns"),
  ]);
  if (detailRes.status === 404) {
    renderNotFound(body, pid);
    return;
  }
  const p = await detailRes.json();
  const { patterns } = await listRes.json();
  const nameToId = new Map(patterns.map((x) => [x.name, x.id]));
  renderPattern(body, p, nameToId);
}

window.addEventListener("DOMContentLoaded", loadPattern);
