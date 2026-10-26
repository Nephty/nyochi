// Plan: pick recipes (everything is filtered here, in the browser), the receipt on the right is built by the server.
import { api, debounce, h, icon, money, prefs, readJson, toast } from "./ui.js";
import { receiptText, renderReceipt } from "./receipt.js";

const P = readJson("plan-data");
const root = document.querySelector("[data-plan]");
if (P && root) {
  const $ = (s) => root.querySelector(s);
  const byId = new Map(P.recipes.map((r) => [r.id, r]));
  const ingName = new Map(P.ingredients.map((i) => [i.id, i.name]));
  const ingByName = new Map(P.ingredients.map((i) => [i.name.toLowerCase(), i.id]));
  const MEAL = { breakfast: "breakfast_dining", full_meal: "restaurant", snack: "cookie", desert: "cake" };

  const saved = prefs.get("plan", {});
  const sel = new Map(Object.entries(saved.sel || {}).map(([k, v]) => [Number(k), v]).filter(([k]) => byId.has(k)));
  for (const id of P.preselect) if (byId.has(id) && !sel.has(id)) sel.set(id, 1);
  const f = { q: "", meal: "", season: false, inc: [], exc: [], tags: [], prep: null, cook: null };
  let location = saved.location && P.locations.some((l) => l.id === saved.location) ? saved.location : null;
  let lastReceipt = null;

  const persist = () => prefs.set("plan", { sel: Object.fromEntries(sel), location });

  // ---- filters
  const mealBox = $("[data-meals]");
  mealBox.append(...[{ value: "", label: "All" }, ...P.meals].map((m) => h("button.pill" + (m.value === "" ? ".on" : ""), { type: "button", dataset: { meal: m.value }, onclick: () => { f.meal = m.value; draw(); } }, m.label)));
  $("[data-tags]").append(...P.tags.map((t) => h("button.pill", { type: "button", dataset: { tag: t.id }, onclick: () => { toggle(f.tags, t.id); draw(); } }, t.name)));
  if (!P.tags.length) $("[data-tags]").append(h("span.muted.sm", {}, "No tags yet"));
  $("#plan-ings").append(...P.ingredients.map((i) => h("option", { value: i.name })));

  const toggle = (arr, v) => { const i = arr.indexOf(v); if (i >= 0) arr.splice(i, 1); else arr.push(v); };
  function chipInput(box, arr, cls) {
    const input = box.querySelector("input");
    const add = () => {
      const id = ingByName.get(input.value.trim().toLowerCase());
      if (id && !arr.includes(id)) { arr.push(id); input.value = ""; draw(); }
    };
    input.addEventListener("change", add);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } });
    return () => box.querySelectorAll(".chip").forEach((c) => c.remove()) || arr.forEach((id) => box.insertBefore(
      h(`span.chip.${cls}`, { title: "Click to remove", onclick: () => { arr.splice(arr.indexOf(id), 1); draw(); } }, ingName.get(id), icon("close")), input));
  }
  const drawInc = chipInput($("[data-inc]"), f.inc, "inc");
  const drawExc = chipInput($("[data-exc]"), f.exc, "ex");
  $("[data-q]").addEventListener("input", (e) => { f.q = e.target.value.toLowerCase().trim(); draw(); });
  $("[data-season]").addEventListener("click", () => { f.season = !f.season; draw(); });
  $("[data-max-prep]").addEventListener("input", (e) => { f.prep = e.target.value === "" ? null : Number(e.target.value); draw(); });
  $("[data-max-cook]").addEventListener("input", (e) => { f.cook = e.target.value === "" ? null : Number(e.target.value); draw(); });
  $("[data-more-btn]").addEventListener("click", () => { const m = $("[data-more]"); m.classList.toggle("hidden"); $("[data-more-btn]").setAttribute("aria-pressed", String(!m.classList.contains("hidden"))); });
  $("[data-clear]").addEventListener("click", () => { f.inc.length = f.exc.length = f.tags.length = 0; f.prep = f.cook = null; $("[data-max-prep]").value = $("[data-max-cook]").value = ""; draw(); });

  function matches(r) {
    if (f.q) {
      const hay = `${r.name} ${r.ing.map((i) => ingName.get(i) || "").join(" ")}`.toLowerCase();
      if (!f.q.split(/\s+/).every((w) => hay.includes(w))) return null;
    }
    if (f.meal && r.meal !== f.meal) return null;
    if (f.exc.some((i) => r.ing.includes(i))) return null;
    if (f.prep !== null && r.prep > f.prep) return null;
    if (f.cook !== null && r.cook > f.cook) return null;
    let score = f.inc.filter((i) => r.ing.includes(i)).length + f.tags.filter((t) => r.tags.includes(t)).length;
    return { score, wanted: f.inc.length + f.tags.length > 0 };
  }

  // ---- the recipe list
  function card(r, info) {
    const on = sel.has(r.id);
    const el = h("div.pcard" + (on ? ".sel" : "") + (info.wanted && !info.score ? ".dim" : ""), { dataset: { id: r.id }, role: "button", tabindex: 0,
      onclick: (e) => { if (e.target.closest(".qty-ctl")) return; setSel(r.id, !on); },
      onkeydown: (e) => { if ((e.key === "Enter" || e.key === " ") && !e.target.closest(".qty-ctl")) { e.preventDefault(); setSel(r.id, !on); } } },
      h("label.chk", {}, h("input", { type: "checkbox", checked: on, tabIndex: -1, "aria-label": `Select ${r.name}`, onclick: (e) => e.stopPropagation(), onchange: (e) => setSel(r.id, e.target.checked) }), h("span", {}, icon("check"))),
      h("div", {}, h("div.nm", {}, r.name)),
      h("div.qty-ctl", {},
        h("button.btn.btn-sm.btn-icon", { type: "button", "aria-label": "Fewer portions", onclick: () => step(r.id, -1) }, icon("remove")),
        h("span.v", { title: "Portion multiplier" }, `×${mult(sel.get(r.id) ?? 1)}`),
        h("button.btn.btn-sm.btn-icon", { type: "button", "aria-label": "More portions", onclick: () => step(r.id, 1) }, icon("add"))),
      h("div.meta", {},
        h("span", {}, icon(MEAL[r.meal] || "restaurant")),
        h("span", {}, icon("schedule"), `${r.prep + r.cook} min`),
        r.inSeason ? h("span.chip.season-in", {}, "in season") : null,
        r.cost != null ? h("span.tag.soft", { title: `${r.priced} of ${r.count} ingredients priced` }, `≈ ${money(r.cost)}`) : null,
        r.promos ? h("span.chip.good", {}, `${r.promos} on sale`) : null,
        info.score ? h("span.why", {}, `${info.score} match${info.score === 1 ? "" : "es"}`) : null));
    return el;
  }
  const mult = (m) => String(Math.round(m * 100) / 100).replace(/^0\./, "0.");
  const STEPS = [0.25, 0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10];
  function step(id, dir) {
    const cur = sel.get(id) ?? 1;
    let i = STEPS.findIndex((s) => s >= cur);
    if (i < 0) i = STEPS.length - 1;
    i = Math.max(0, Math.min(STEPS.length - 1, i + dir));
    sel.set(id, STEPS[i]);
    afterChange();
  }
  function setSel(id, on) { if (on) sel.set(id, sel.get(id) ?? 1); else sel.delete(id); afterChange(); }
  function afterChange() { persist(); draw(); loadReceipt(); }

  function draw() {
    mealBox.querySelectorAll(".pill").forEach((b) => b.classList.toggle("on", b.dataset.meal === f.meal));
    root.querySelectorAll("[data-tag]").forEach((b) => b.classList.toggle("on", f.tags.includes(Number(b.dataset.tag))));
    $("[data-season]").setAttribute("aria-pressed", String(f.season));
    drawInc(); drawExc();
    const n = f.inc.length + f.exc.length + f.tags.length + (f.prep !== null) + (f.cook !== null);
    $("[data-filter-n]").textContent = n ? `(${n})` : "";
    let rows = P.recipes.map((r) => ({ r, info: matches(r) })).filter((x) => x.info);
    rows.sort((a, b) => (b.info.score - a.info.score) || (f.season ? Number(b.r.inSeason) - Number(a.r.inSeason) : 0) || a.r.name.localeCompare(b.r.name));
    const list = $("[data-list]");
    list.replaceChildren();
    let lastMeal = null;
    const wrap = h("div.plan-list");
    for (const { r, info } of rows) {
      if (!f.meal && !f.season && !info.wanted && r.meal !== lastMeal) {
        lastMeal = r.meal;
        wrap.append(h("div.plan-meal", {}, icon(MEAL[r.meal] || "restaurant"), P.meals.find((m) => m.value === r.meal)?.label || r.meal));
      }
      wrap.append(card(r, info));
    }
    list.append(wrap);
    $("[data-empty]").classList.toggle("hidden", rows.length > 0);
    $("[data-badge]").textContent = sel.size;
    drawPicked();
  }

  function drawPicked() {
    $("[data-picked]").replaceChildren(...[...sel].map(([id, m]) => h("span.chip", { style: { cursor: "pointer" }, title: "Remove from the plan", onclick: () => setSel(id, false) },
      `${byId.get(id).name}${m !== 1 ? ` ×${mult(m)}` : ""}`, icon("close"))));
  }

  // ---- location
  const locSel = $("[data-location]");
  locSel.append(h("option", { value: "" }, "Group by category (no shop)"), ...P.locations.map((l) => h("option", { value: l.id, selected: l.id === location }, l.name)));
  if (!P.locations.length) locSel.append(h("option", { disabled: true }, "Add a shop to follow its aisles"));
  locSel.addEventListener("change", () => { location = locSel.value ? Number(locSel.value) : null; persist(); loadReceipt(); });

  // ---- the receipt
  const box = $("[data-receipt]");
  const actions = $("[data-actions]");
  let seq = 0;
  async function loadReceipt() {
    if (!sel.size) {
      lastReceipt = null;
      actions.hidden = true;
      renderReceipt(box, { sections: [], totals: { lines: 0 }, location: null }, { title: "Your list", emptyTitle: "Pick a recipe", emptyText: "Its ingredients are added up here, in the order you walk the shop." });
      return;
    }
    const mine = ++seq;
    try {
      const data = await api(P.urls.receipt, { method: "POST", body: { recipes: [...sel].map(([id, mult]) => ({ id, mult })), location } });
      if (mine !== seq) return;
      lastReceipt = data;
      actions.hidden = false;
      renderReceipt(box, data, { title: `${sel.size} recipe${sel.size === 1 ? "" : "s"}` });
    } catch (err) { if (mine === seq) toast(err.message, true); }
  }
  const loadSoon = debounce(loadReceipt, 150);

  $("[data-save]").addEventListener("click", async (e) => {
    e.currentTarget.disabled = true;
    try {
      const made = await api(P.urls.save, { method: "POST", body: { recipes: [...sel].map(([id, mult]) => ({ id, mult })), location, name: $("[data-name]").value } });
      prefs.set("plan", {});
      location_href(made.url);
    } catch (err) { toast(err.message, true); e.currentTarget.disabled = false; }
  });
  const location_href = (u) => { window.location.href = u; };
  $("[data-copy]").addEventListener("click", async () => {
    if (!lastReceipt) return;
    try { await navigator.clipboard.writeText(receiptText(lastReceipt, "Shopping list")); toast("Copied: paste it anywhere."); }
    catch { toast("Your browser wouldn’t let me copy.", true); }
  });
  $("[data-print]").addEventListener("click", () => window.print());

  root.querySelectorAll("[data-pane-btn]").forEach((b) => b.addEventListener("click", () => {
    root.dataset.pane = b.dataset.paneBtn;
    root.querySelectorAll("[data-pane-btn]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  }));

  draw();
  loadSoon();
}
