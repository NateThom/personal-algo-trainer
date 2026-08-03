// Shared top nav, defined ONCE and injected into every page (DRY as pages grow).
// Built with DOM methods (no innerHTML) so there is no injection surface.
const NAV_PAGES = [
  { href: "/", label: "Solve" },
  { href: "/guide", label: "Guide" },
  { href: "/methodology", label: "Methodology" },
  { href: "/patterns", label: "Patterns" },
  { href: "/flashcards", label: "Flashcards" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/docs", label: "API Docs ↗", external: true },
];

function buildNav() {
  const nav = document.createElement("nav");
  nav.className = "topnav";

  const links = document.createElement("div");
  links.className = "navlinks";
  const here = window.location.pathname;
  for (const p of NAV_PAGES) {
    const a = document.createElement("a");
    a.href = p.href;
    a.textContent = p.label;
    if (p.external) {
      a.target = "_blank";
      a.rel = "noopener";
    } else if (p.href === here) {
      a.className = "active";
    }
    links.appendChild(a);
  }

  const actions = document.createElement("div");
  actions.className = "navactions";

  const reload = document.createElement("button");
  reload.id = "reload-btn";
  reload.type = "button";
  reload.textContent = "Reload problems";

  const btn = document.createElement("button");
  btn.id = "reset-btn";
  btn.className = "danger";
  btn.type = "button";
  btn.textContent = "Reset progress";

  actions.appendChild(reload);
  actions.appendChild(btn);
  nav.appendChild(links);
  nav.appendChild(actions);
  document.body.prepend(nav);
  return { resetBtn: btn, reloadBtn: reload };
}

function wireReload(btn) {
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      const r = await fetch("/api/reload", { method: "POST" });
      const { count } = await r.json();
      btn.textContent = `Reloaded (${count})`;
      setTimeout(() => window.location.reload(), 700);
    } catch (e) {
      alert("Reload failed: " + e.message);
      btn.disabled = false;
    }
  });
}

function wireReset(btn) {
  btn.addEventListener("click", async () => {
    const ok = window.confirm(
      "Reset ALL progress?\n\nThis clears your FSRS schedule, attempts, reviews, " +
      "and pattern mastery. Problems (including any AI-generated variants) are kept.\n\n" +
      "This cannot be undone."
    );
    if (!ok) return;
    btn.disabled = true;
    try {
      const r = await fetch("/api/reset", { method: "POST" });
      if (!r.ok) throw new Error("reset failed");
      window.location.reload();
    } catch (e) {
      alert("Reset failed: " + e.message);
      btn.disabled = false;
    }
  });
}

window.addEventListener("DOMContentLoaded", () => {
  const { resetBtn, reloadBtn } = buildNav();
  wireReset(resetBtn);
  wireReload(reloadBtn);
});
