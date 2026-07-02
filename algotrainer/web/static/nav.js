// Shared top-nav behavior: wire the "Reset progress" button on any page.
window.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("reset-btn");
  if (!btn) return;
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
      // Reload so every panel reflects the cleared state.
      window.location.reload();
    } catch (e) {
      alert("Reset failed: " + e.message);
      btn.disabled = false;
    }
  });
});
