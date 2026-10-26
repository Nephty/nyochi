// Client-side filtering of a list of cards: text, one-of pills, a toggle. Remembers the meal pill.
import { prefs } from "./ui.js";

const root = document.querySelector("[data-filter-list]");
if (root) {
  const q = root.querySelector("[data-filter-q]");
  const meals = [...root.querySelectorAll("[data-filter-meal]")];
  const season = root.querySelector("[data-filter-season]");
  const cats = [...root.querySelectorAll("[data-filter-cat]")];
  const items = [...root.querySelectorAll("[data-item]")];
  const groups = [...root.querySelectorAll("[data-group]")];
  const count = root.querySelector("[data-count]");
  const empty = root.querySelector("[data-empty]");
  const key = location.pathname;
  const state = { meal: prefs.get(`${key}:meal`, ""), season: false, cat: "" };

  function apply() {
    const words = (q?.value || "").toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const el of items) {
      const text = el.dataset.text || "";
      const ok = words.every((w) => text.includes(w))
        && (!state.meal || el.dataset.meal === state.meal)
        && (!state.season || el.dataset.season === "1")
        && (!state.cat || el.dataset.cat === state.cat);
      el.classList.toggle("hidden", !ok);
      shown += ok;
    }
    for (const g of groups) g.classList.toggle("hidden", !g.querySelector("[data-item]:not(.hidden)"));
    meals.forEach((b) => b.classList.toggle("on", b.dataset.filterMeal === state.meal));
    cats.forEach((b) => b.classList.toggle("on", b.dataset.filterCat === state.cat));
    season?.setAttribute("aria-pressed", String(state.season));
    if (count) count.textContent = shown === items.length ? `${items.length} in total` : `${shown} of ${items.length}`;
    empty?.classList.toggle("hidden", shown > 0);
  }
  q?.addEventListener("input", apply);
  meals.forEach((b) => b.addEventListener("click", () => { state.meal = b.dataset.filterMeal; prefs.set(`${key}:meal`, state.meal); apply(); }));
  cats.forEach((b) => b.addEventListener("click", () => { state.cat = b.dataset.filterCat; apply(); }));
  season?.addEventListener("click", () => { state.season = !state.season; apply(); });
  apply();
}
