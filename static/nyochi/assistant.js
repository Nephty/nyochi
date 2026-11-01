// The meal assistant: fills the chosen days and meals with recipes, scored in the browser from the same data as Plan
// (season, Shopping promotions, cost, times, tags) plus the calendar's history. Swap, lock or skip each proposal,
// then add them all to the calendar (and go on to the shopping list).
import { api, dialog, h, icon, prefs, readJson, sw, toast } from "./ui.js";
import { STEPS, addDays, dayText, mult, parseDay } from "./meal-dialog.js";

const B = readJson("assistant-data");
const root = document.querySelector("[data-assistant]");

const FACTORS = [
  ["season", "In season", "Recipes whose main ingredients are in season now."],
  ["promos", "On sale", "Recipes with ingredients on promotion in Shopping."],
  ["fresh", "Not had recently", "Keep away from what was cooked or planned in the last two weeks."],
  ["variety", "Variety", "Not the same recipe twice, nor the same main ingredient two days running."],
  ["effort", "Quick on weekdays", "Short recipes Monday to Friday, longer ones at the weekend."],
];

if (B && root) {
  const $ = (s) => root.querySelector(s);
  const byId = new Map(B.recipes.map((r) => [r.id, r]));
  const slotOf = (v) => B.slots.find((s) => s.value === v);
  const end = addDays(B.start, B.n - 1);
  const days = Array.from({ length: B.n }, (_, i) => addDays(B.start, i));
  const opts = prefs.get("assist", {});
  const st = {
    slots: Array.isArray(opts.slots) && opts.slots.length ? opts.slots.filter((s) => slotOf(s)) : ["lunch", "dinner"],
    factors: Object.assign({ season: true, promos: true, fresh: true, variety: true, effort: true }, opts.factors || {}),
    tags: (opts.tags || []).filter((t) => B.tags.some((x) => x.id === t)),
    mult: opts.mult || 1,
  };
  const keep = () => prefs.set("assist", { slots: st.slots, factors: st.factors, tags: st.tags, mult: st.mult });
  const cells = new Map(); // "day|slot" -> {recipe, locked, skipped, excluded: Set}
  const key = (day, slot) => `${day}|${slot}`;
  const planned = (day, slot) => B.meals.filter((m) => m.day === day && m.slot === slot);

  // ---- side panel (the preferences fold away on phones)
  const prefsBox = root.querySelector("[data-prefs]");
  if (prefsBox && matchMedia("(min-width: 761px)").matches) prefsBox.open = true;
  $("[data-start]").value = B.start;
  const daysSel = $("[data-days]");
  if (![...daysSel.options].some((o) => Number(o.value) === B.n)) daysSel.append(h("option", { value: B.n }, `${B.n} days`));
  daysSel.value = String(B.n);
  const reload = () => { location.search = `?start=${$("[data-start]").value || B.start}&days=${daysSel.value}`; };
  $("[data-start]").addEventListener("change", reload);
  daysSel.addEventListener("change", reload);
  $("[data-slots]").append(...B.slots.map((s) => h("button.pill", { type: "button", "aria-pressed": String(st.slots.includes(s.value)), onclick: (e) => {
    st.slots = st.slots.includes(s.value) ? st.slots.filter((x) => x !== s.value) : B.slots.map((x) => x.value).filter((v) => v === s.value || st.slots.includes(v));
    e.currentTarget.setAttribute("aria-pressed", String(st.slots.includes(s.value)));
    keep(); fill(); } }, icon(s.icon), s.label)));
  $("[data-factors]").append(...FACTORS.map(([k, label, help]) => sw(label, help, st.factors[k], (on) => { st.factors[k] = on; keep(); fill(true); })),
    h("div.field", { style: { marginTop: ".4rem" } }, h("label.label", { for: "as-mult" }, "Portions"),
      h("select.select.sm", { id: "as-mult", onchange: (e) => { st.mult = Number(e.target.value); keep(); draw(); } },
        STEPS.map((s) => h("option", { value: s, selected: s === st.mult }, `×${mult(s)}`)))));
  if (B.tags.length) $("[data-tags]").append(...B.tags.map((t) => h("button.pill", { type: "button", "aria-pressed": String(st.tags.includes(t.id)), onclick: (e) => {
    st.tags = st.tags.includes(t.id) ? st.tags.filter((x) => x !== t.id) : [...st.tags, t.id];
    e.currentTarget.setAttribute("aria-pressed", String(st.tags.includes(t.id)));
    keep(); fill(true); } }, t.name)));
  else $("[data-tags]").append(h("span.muted.sm", {}, "No tags yet"));

  // ---- scoring
  const dist = (a, b) => Math.abs((parseDay(a) - parseDay(b)) / 86400000);
  const weekend = (iso) => [0, 6].includes(parseDay(iso).getDay());
  function context(except) {
    // every recipe on a day: the calendar's (history + this range) and the proposals so far, minus the cell scored
    const out = B.history.map((x) => ({ day: x.day, recipe: x.recipe }));
    for (const [k, c] of cells) if (k !== except && c.recipe && !c.skipped) out.push({ day: k.split("|")[0], recipe: c.recipe });
    return out;
  }
  function score(r, day, slot, ctx) {
    const why = [];
    let s = 0;
    const f = st.factors;
    if (f.season && r.inSeason) { s += 3; why.push("in season"); }
    if (f.promos && r.promos) { s += Math.min(r.promos, 3); why.push(`${r.promos} on sale`); }
    const dates = ctx.filter((x) => x.recipe === r.id).map((x) => x.day).concat(r.lastCooked ? [r.lastCooked] : []);
    const near = dates.length ? Math.min(...dates.map((d) => dist(d, day))) : Infinity;
    if (f.fresh) {
      if (near <= 14) s -= (15 - near) / 3;
      else if (!r.lastCooked && !dates.length) { s += 0.5; why.push("not cooked yet"); }
      else if (near >= 21) why.push(near === Infinity ? "" : `not had for ${Math.floor(near / 7)} weeks`);
    }
    if (f.variety) {
      // each repeat in the range costs more, and a repeat the day before or after even more
      const again = ctx.filter((x) => x.recipe === r.id && x.day >= B.start && x.day <= end);
      s -= 6 * again.length;
      if (again.some((x) => dist(x.day, day) <= 1)) s -= 6;
      const mains = new Set(r.main.map((m) => m.id));
      const close = ctx.filter((x) => x.recipe !== r.id && dist(x.day, day) <= 1);
      const clash = close.some((x) => byId.get(x.recipe)?.main.some((m) => mains.has(m.id)));
      if (clash) s -= 2;
    }
    if (f.effort && (slot === "lunch" || slot === "dinner")) {
      const t = r.prep + r.cook;
      if (!weekend(day) && t > 40) s -= (t - 40) / 20;
      else if (!weekend(day) && t <= 30) why.push(`quick (${t} min)`);
      if (weekend(day) && t >= 60) { s += 1; why.push("a weekend project"); }
    }
    const tagHits = st.tags.filter((t) => r.tags.includes(t)).length;
    if (tagHits) { s += 2 * tagHits; why.push(B.tags.filter((t) => st.tags.includes(t.id) && r.tags.includes(t.id)).map((t) => t.name).join(", ")); }
    return { s, why: why.filter(Boolean) };
  }
  const candidates = (slot) => B.recipes.filter((r) => slotOf(slot).meals.includes(r.meal));
  function ranked(day, slot) {
    const ctx = context(key(day, slot));
    const c = cells.get(key(day, slot));
    return candidates(slot).filter((r) => !c?.excluded.has(r.id))
      .map((r) => ({ r, ...score(r, day, slot, ctx) }))
      // a little chance, and "Suggest again" steers away from what the slot had
      .map((x) => ({ ...x, j: x.s + Math.random() * 3 - (c?.prev === x.r.id ? 8 : 0) }))
      .sort((a, b) => b.j - a.j);
  }
  function pick(day, slot) {
    const c = cells.get(key(day, slot));
    c.recipe = ranked(day, slot)[0]?.r.id ?? null;
  }

  // ---- filling: every open cell of the chosen meals, day by day; `all` also redoes the unlocked proposals
  function fill(all = false) {
    for (const day of days) for (const slot of st.slots) {
      const k = key(day, slot);
      if (planned(day, slot).length) { cells.delete(k); continue; }
      if (!cells.has(k)) cells.set(k, { recipe: null, locked: false, skipped: false, excluded: new Set() });
      const c = cells.get(k);
      if (c.locked || c.skipped) continue;
      c.prev = all ? c.recipe : null;
      if (all || !c.recipe) c.recipe = null;
    }
    for (const [k] of cells) { const [d, s] = k.split("|"); if (!st.slots.includes(s) || !days.includes(d)) cells.delete(k); }
    for (const day of days) for (const slot of st.slots) {
      const c = cells.get(key(day, slot));
      if (c && !c.locked && !c.skipped && !c.recipe) pick(day, slot);
    }
    draw();
  }

  function chooseDialog(day, slot) {
    const rows = ranked(day, slot).sort((a, b) => b.s - a.s);
    const dlg = dialog({
      title: `${dayText(day)} · ${slotOf(slot).label}`, wide: true,
      body: h("div.md-list", { style: { maxHeight: "60vh" } }, rows.map(({ r, why }) => h("button.md-opt", { type: "button", onclick: () => {
        const c = cells.get(key(day, slot));
        Object.assign(c, { recipe: r.id, locked: true, skipped: false });
        dlg.close(); draw();
      } }, h("span.nm", {}, r.name), h("span.meta", {}, why.map((w) => h("span.chip", {}, w)), h("span", {}, icon("schedule"), `${r.prep + r.cook} min`))))),
    });
  }

  // ---- the grid: a row per day, a column per chosen meal
  const grid = $("[data-grid]");
  function draw() {
    grid.style.setProperty("--cols", st.slots.length || 1);
    const head = [h("div.as-h"), ...st.slots.map((s) => h("div.as-h", {}, icon(slotOf(s).icon), slotOf(s).label))];
    const rows = days.flatMap((day) => [
      h(`div.as-day${day === B.today ? ".today" : ""}`, {}, h("b", {}, dayText(day)), weekend(day) ? h("span.muted.sm", {}, "weekend") : null),
      ...st.slots.map((slot) => {
        // every cell: its meal's name (shown on phones, where each day is a list) and what goes there
        const cell = (cls, ...body) => h(`div.as-cell${cls}`, {}, h("span.as-k", {}, icon(slotOf(slot).icon), slotOf(slot).label), h("div.as-body", {}, ...body));
        const there = planned(day, slot);
        if (there.length) return cell(".planned", there.map((m) => h("div.as-card.planned", {}, h("span.nm", {}, m.name), h("span.muted.sm", {}, "already planned"))));
        const c = cells.get(key(day, slot));
        if (!candidates(slot).length) return cell(".none", h("span.muted.sm", {}, `No ${slotOf(slot).label.toLowerCase()} recipe yet`));
        if (!c || c.skipped || !c.recipe) {
          return cell(".skipped", h("button.btn.btn-ghost.btn-sm", { type: "button", onclick: () => { if (c) { c.skipped = false; c.excluded.clear(); pick(day, slot); draw(); } } }, icon("add"), "Suggest one"));
        }
        const r = byId.get(c.recipe);
        const { why } = score(r, day, slot, context(key(day, slot)));
        return cell("", h(`div.as-card${c.locked ? ".locked" : ""}`, {},
          h("div.as-what", {},
            h("button.nm", { type: "button", title: "Choose another recipe", onclick: () => chooseDialog(day, slot) }, r.name),
            why.length ? h("div.why", {}, why.slice(0, 3).map((w) => h("span.chip", {}, w))) : null),
          h("div.acts", {},
            h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", title: c.locked ? "Unlock" : "Lock: keep it when suggesting again", "aria-label": c.locked ? "Unlock" : "Lock", "aria-pressed": String(c.locked), onclick: () => { c.locked = !c.locked; draw(); } }, icon(c.locked ? "lock" : "lock_open")),
            h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", title: "Swap for the next best", "aria-label": "Swap", disabled: c.locked, onclick: () => { c.excluded.add(c.recipe); pick(day, slot); draw(); } }, icon("shuffle")),
            h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", title: "Leave this meal empty", "aria-label": "Leave empty", onclick: () => { c.skipped = true; c.locked = false; draw(); } }, icon("close")))));
      }),
    ]);
    grid.replaceChildren(...head, ...rows);
    const n = proposals().length;
    $("[data-count]").textContent = `${n} meal${n === 1 ? "" : "s"} proposed${st.mult !== 1 ? `, ×${mult(st.mult)} each` : ""}`;
    root.querySelectorAll("[data-add], [data-add-shop]").forEach((b) => { b.disabled = !n; });
  }
  const proposals = () => [...cells].filter(([, c]) => c.recipe && !c.skipped).map(([k, c]) => {
    const [day, slot] = k.split("|");
    return { day, slot, recipe: c.recipe, mult: st.mult };
  });

  $("[data-roll]").addEventListener("click", () => {
    const before = new Map([...cells].map(([k, c]) => [k, c.recipe]));
    for (const c of cells.values()) if (!c.locked) c.excluded.clear();
    fill(true);
    const changed = [...cells].filter(([k, c]) => c.recipe && c.recipe !== before.get(k)).length;
    const open = [...cells.values()].filter((c) => !c.locked && !c.skipped).length;
    toast(!open ? "Everything is locked or left empty: nothing to suggest again." : changed ? `${changed} new suggestion${changed === 1 ? "" : "s"}.` : "No other recipe fits better: add recipes or loosen a preference.", !open || !changed);
  });
  async function add(thenShop) {
    const list = proposals();
    if (!list.length) return;
    try {
      await api(B.urls.bulk, { method: "POST", body: { meals: list } });
      prefs.set("assist", { slots: st.slots, factors: st.factors, tags: st.tags, mult: st.mult });
      location.href = thenShop ? `${B.urls.shop}?start=${B.start}&end=${end}` : `${B.urls.week}?week=${B.start}`;
    } catch (err) { toast(err.message, true); }
  }
  $("[data-add]")?.addEventListener("click", () => add(false));
  $("[data-add-shop]")?.addEventListener("click", () => add(true));

  fill();
}
