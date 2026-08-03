// Flashcard study session: fetches due cards, runs one at a time (MCQ /
// flip-and-rate / type-and-diff depending on card_type), submits reviews.
// Built with DOM methods (textContent) for anything derived from pattern-doc
// free text — same convention as patterns_detail.js.
let queue = [];
const docCache = new Map(); // pattern id -> full /api/patterns/<id> doc

function patternIdFromPath() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts.length > 1 ? parts[parts.length - 1] : null;
}

async function fetchDoc(pattern) {
  if (!docCache.has(pattern)) {
    const doc = await (await fetch(`/api/patterns/${encodeURIComponent(pattern)}`)).json();
    docCache.set(pattern, doc);
  }
  return docCache.get(pattern);
}

function clearBody() {
  const body = document.getElementById("session-body");
  body.textContent = "";
  return body;
}

function ratingRow(onRate) {
  const row = document.createElement("div");
  row.className = "rating-row";
  for (const [label, value] of [["Again", 1], ["Hard", 2], ["Good", 3], ["Easy", 4]]) {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.addEventListener("click", () => onRate(value));
    row.appendChild(btn);
  }
  return row;
}

async function submitReview(card, payload) {
  const res = await fetch("/api/flashcards/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pattern: card.pattern, card_type: card.card_type, ...payload }),
  });
  return res.json();
}

function renderRecognition(card, body) {
  const q = document.createElement("p");
  q.className = "lede";
  q.textContent = card.signal;
  body.appendChild(q);

  const options = document.createElement("div");
  options.className = "mcq-options";
  for (const opt of card.options) {
    const btn = document.createElement("button");
    btn.textContent = opt.name;
    btn.addEventListener("click", async () => {
      [...options.children].forEach((b) => (b.disabled = true));
      const result = await submitReview(card, { selected: opt.id });
      const feedback = document.createElement("p");
      feedback.className = result.correct ? "note" : "note mtrap";
      feedback.textContent = result.correct
        ? "Correct."
        : `Not quite — this was ${card.pattern_name}.`;
      body.appendChild(feedback);
      const next = document.createElement("button");
      next.textContent = "Next";
      next.addEventListener("click", advance);
      body.appendChild(next);
    });
    options.appendChild(btn);
  }
  body.appendChild(options);
}

function revealComplexity(doc, body) {
  const p = document.createElement("p");
  p.textContent = `Time: ${doc.complexity.time || "?"}  ·  Space: ${doc.complexity.space || "?"}`;
  body.appendChild(p);
  if (doc.complexity.notes) {
    const notes = document.createElement("p");
    notes.className = "note";
    notes.textContent = doc.complexity.notes;
    body.appendChild(notes);
  }
}

function revealGotchas(doc, body) {
  const ul = document.createElement("ul");
  for (const g of doc.gotchas) {
    const li = document.createElement("li");
    li.textContent = g;
    ul.appendChild(li);
  }
  body.appendChild(ul);
}

function renderFlipCard(card, body, reveal) {
  const front = document.createElement("p");
  front.className = "lede";
  front.textContent = card.pattern_name;
  body.appendChild(front);

  const show = document.createElement("button");
  show.textContent = "Show answer";
  show.addEventListener("click", async () => {
    show.remove();
    const doc = await fetchDoc(card.pattern);
    reveal(doc, body);
    body.appendChild(ratingRow(async (rating) => {
      await submitReview(card, { rating });
      advance();
    }));
  });
  body.appendChild(show);
}

function renderDiff(ops) {
  const pre = document.createElement("pre");
  pre.className = "diff-view";
  for (const op of ops) {
    for (const line of op.reference) {
      const div = document.createElement("div");
      div.className = `diff-line diff-${op.op === "equal" ? "equal" : "reference"}`;
      div.textContent = (op.op === "equal" ? "  " : "- ") + line;
      pre.appendChild(div);
    }
    if (op.op !== "equal") {
      for (const line of op.typed) {
        const div = document.createElement("div");
        div.className = "diff-line diff-typed";
        div.textContent = "+ " + line;
        pre.appendChild(div);
      }
    }
  }
  return pre;
}

function renderTemplate(card, body) {
  const front = document.createElement("p");
  front.className = "lede";
  front.textContent = `${card.pattern_name} — type the template from memory`;
  body.appendChild(front);

  const box = document.createElement("textarea");
  box.className = "flashcard-code";
  box.rows = 12;
  body.appendChild(box);

  const check = document.createElement("button");
  check.textContent = "Check";
  check.addEventListener("click", async () => {
    check.disabled = true;
    const res = await fetch("/api/flashcards/diff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pattern: card.pattern, code: box.value }),
    });
    const { ops } = await res.json();
    box.remove();
    check.remove();
    body.appendChild(renderDiff(ops));
    body.appendChild(ratingRow(async (rating) => {
      await submitReview(card, { rating });
      advance();
    }));
  });
  body.appendChild(check);
}

function renderCard(card) {
  const body = clearBody();
  document.getElementById("session-progress").textContent =
    `${queue.length + 1} card${queue.length === 0 ? "" : "s"} remaining`;
  if (card.card_type === "recognition") {
    renderRecognition(card, body);
  } else if (card.card_type === "complexity") {
    renderFlipCard(card, body, revealComplexity);
  } else if (card.card_type === "gotcha") {
    renderFlipCard(card, body, revealGotchas);
  } else if (card.card_type === "template") {
    renderTemplate(card, body);
  }
}

function advance() {
  const card = queue.shift();
  if (!card) {
    const body = clearBody();
    const done = document.createElement("p");
    done.className = "lede";
    done.textContent = "Session complete.";
    body.appendChild(done);
    document.getElementById("session-progress").textContent = "";
    return;
  }
  renderCard(card);
}

async function startSession() {
  const filterPattern = patternIdFromPath();
  const { cards } = await (await fetch("/api/flashcards/due")).json();
  queue = filterPattern ? cards.filter((c) => c.pattern === filterPattern) : cards;
  document.getElementById("due-count").textContent = `${queue.length} due`;
  document.getElementById("start-btn").hidden = queue.length === 0;
  document.getElementById("empty-note").hidden = queue.length > 0;
}

function wireStart() {
  document.getElementById("start-btn").addEventListener("click", () => {
    document.getElementById("start-btn").hidden = true;
    advance();
  });
}

window.addEventListener("DOMContentLoaded", () => {
  wireStart();
  startSession();
});
