// The meal dialog: add or change one meal of the calendar (a recipe with portions, free text, or a leftovers meal),
// with its leftovers for a later day. Used by the week page (meals.js) and the recipe page's "Add to the calendar".
import { api, confirmDialog, dialog, h, icon, money, toast } from "./ui.js";

export const STEPS = [0.25, 0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10];
export const mult = (m) => String(Math.round(m * 100) / 100);
export const TEXT_IDEAS = ["Restaurant", "Takeaway", "At friends’", "Something simple", "Fasting"];
const DAY = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short" });

export const parseDay = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };
export const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const addDays = (iso, n) => { const d = parseDay(iso); d.setDate(d.getDate() + n); return isoDay(d); };
export const dayText = (iso) => DAY.format(parseDay(iso));
export const mealUrl = (urls, id, action) => urls.meal.replace("{id}", id).replace("{action}", action);

// How well a recipe suits a slot: its meal type first, then in season, then the name.
export function rankFor(recipes, slot, q = "") {
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  return recipes
    .filter((r) => words.every((w) => r.name.toLowerCase().includes(w)))
    .map((r) => ({ r, fit: slot.meals.includes(r.meal) ? 1 : 0 }))
    .sort((a, b) => (b.fit - a.fit) || (Number(b.r.inSeason) - Number(a.r.inSeason)) || a.r.name.localeCompare(b.r.name))
    .map((x) => x.r);
}

/**
 * meal: an existing meal (edit) or null (add). at: {day, slot} for a new one. recipe: a recipe id to start from.
 * ctx: {recipes, slots, urls, meals (to name a leftovers' source), canEdit}. onDone({meals, deleted}).
 */
export function mealDialog({ meal = null, at = {}, recipe = null, ctx, onDone }) {
  const byId = new Map(ctx.recipes.map((r) => [r.id, r]));
  const slotOf = (v) => ctx.slots.find((s) => s.value === v) || ctx.slots.at(-1);
  const st = {
    day: meal?.day || at.day, slot: meal?.slot || at.slot || "dinner",
    mode: meal ? (meal.kind === "text" ? "text" : "recipe") : "recipe",
    recipe: meal?.recipe ?? recipe, mult: meal?.mult ?? 1, text: meal?.kind === "text" ? meal.title : "", note: meal?.note || "",
    leftovers: null, q: "",
  };
  const leftoversNow = meal ? ctx.meals.find((m) => m.leftover_of === meal.id) : null;
  if (leftoversNow) st.leftovers = { day: leftoversNow.day, slot: leftoversNow.slot };
  const isLeft = meal?.kind === "leftovers";
  const ro = !ctx.canEdit;

  const body = h("div.md");
  const dayIn = h("input.input", { type: "date", value: st.day, required: true, disabled: ro, onchange: (e) => { st.day = e.target.value || st.day; draw(); } });
  const slotIn = h("select.select", { disabled: ro, onchange: (e) => { st.slot = e.target.value; draw(); } },
    ctx.slots.map((s) => h("option", { value: s.value, selected: s.value === st.slot }, s.label)));
  const search = h("input.input", { type: "search", placeholder: "Search your recipes", "aria-label": "Search recipes", oninput: (e) => { st.q = e.target.value; drawList(); } });
  const list = h("div.md-list");
  const pane = h("div.md-pane");

  function drawList() {
    // once a recipe is chosen the list folds away; typing in the search brings it back
    list.classList.toggle("hidden", !!st.recipe && !st.q);
    const slot = slotOf(st.slot);
    const rows = rankFor(ctx.recipes, slot, st.q).slice(0, st.q ? 40 : 12);
    list.replaceChildren(...(rows.length ? rows.map((r) => h("button.md-opt" + (r.id === st.recipe ? ".on" : ""), {
      type: "button", onclick: () => { st.recipe = r.id; st.q = ""; search.value = ""; draw(); } },
      h("span.nm", {}, r.name),
      h("span.meta", {}, slot.meals.includes(r.meal) ? null : h("span.chip", {}, "other meal type"),
        r.inSeason ? h("span.chip.season-in", {}, "in season") : null,
        r.promos ? h("span.chip.good", {}, `${r.promos} on sale`) : null,
        h("span", {}, icon("schedule"), `${r.prep + r.cook} min`)))) : [h("p.muted.sm", {}, "No recipe matches.")]));
  }

  function stepper() {
    const go = (dir) => {
      let i = STEPS.findIndex((s) => s >= st.mult);
      if (i < 0) i = STEPS.length - 1;
      st.mult = STEPS[Math.max(0, Math.min(STEPS.length - 1, i + dir))];
      draw();
    };
    return h("div.qty-ctl", {},
      h("button.btn.btn-sm.btn-icon", { type: "button", disabled: ro, "aria-label": "Fewer portions", onclick: () => go(-1) }, icon("remove")),
      h("span.v", { title: "Portions: ×1 is the recipe as written" }, `×${mult(st.mult)}`),
      h("button.btn.btn-sm.btn-icon", { type: "button", disabled: ro, "aria-label": "More portions", onclick: () => go(1) }, icon("add")));
  }

  function leftoversField() {
    const on = !!st.leftovers;
    const targets = [];
    for (let i = 0; i <= 3; i++) for (const s of ctx.slots) {
      const d = addDays(st.day, i);
      if (i === 0 && ctx.slots.indexOf(s) <= ctx.slots.indexOf(slotOf(st.slot))) continue;
      targets.push({ day: d, slot: s.value, label: `${dayText(d)} · ${s.label}` });
    }
    const key = (t) => `${t.day}|${t.slot}`;
    const select = h("select.select.sm", { disabled: ro, onchange: (e) => { const [day, slot] = e.target.value.split("|"); st.leftovers = { day, slot }; } },
      targets.map((t) => h("option", { value: key(t), selected: on && key(t) === key(st.leftovers) }, t.label)));
    const toggle = h("label.switch", {}, h("input", { type: "checkbox", checked: on, disabled: ro, onchange: (e) => {
      if (e.target.checked) {
        const next = targets.find((t) => t.day === addDays(st.day, 1) && t.slot === st.slot) || targets[0];
        st.leftovers = { day: next.day, slot: next.slot };
        if (st.mult < 2) st.mult = st.mult * 2; // cook for both meals
      } else st.leftovers = null;
      draw();
    } }), h("span.track"), h("span.txt", {}, "Leftovers for later", h("small", {}, on ? "Cooked once, bought once: the portions cover both." : "Cook more and eat it again another day.")));
    return h("div.md-left", {}, toggle, on ? select : null);
  }

  function draw() {
    slotIn.value = st.slot;
    const r = byId.get(st.recipe);
    let content;
    if (isLeft) {
      const src = ctx.meals.find((m) => m.id === meal.leftover_of);
      content = h("p.md-src", {}, icon("restaurant"), "Leftovers of ", h("b", {}, meal.title || "a meal"),
        src ? ` (${dayText(src.day)}, ${slotOf(src.slot).label.toLowerCase()})` : "", ". Bought with that meal.");
    } else if (st.mode === "text") {
      content = h("div.field", {}, h("label.label", {}, "What you eat"),
        h("input.input", { type: "text", maxLength: 200, value: st.text, disabled: ro, placeholder: "Restaurant, takeaway…", oninput: (e) => { st.text = e.target.value; } }),
        h("div.pills", {}, TEXT_IDEAS.map((t) => h("button.pill", { type: "button", disabled: ro, onclick: () => { st.text = t; draw(); } }, t))));
    } else {
      search.placeholder = r ? "Search for another recipe" : "Search your recipes";
      content = h("div.md-recipe", {},
        r ? h("div.md-chosen", {}, h("div", {}, h("b", {}, r.name),
              h("div.meta", {}, r.inSeason ? h("span.chip.season-in", {}, "in season") : null,
                r.cost != null ? h("span.tag.soft", {}, `≈ ${money(r.cost * st.mult)}`) : null,
                r.lastCooked ? h("span.muted.sm", {}, `last cooked ${dayText(r.lastCooked)}`) : null)),
              stepper())
          : h("p.muted.sm", { style: { margin: 0 } }, "Pick a recipe:"),
        ro ? null : h("div.search", {}, icon("search"), search), ro ? null : list,
        r ? leftoversField() : null);
      drawList();
    }
    pane.replaceChildren(content);
  }

  const modeSeg = isLeft ? null : h("div.seg", { role: "group", "aria-label": "Kind of meal" },
    [["recipe", "menu_book", "Recipe"], ["text", "edit_note", "Free text"]].map(([v, ic, label]) => h("button", {
      type: "button", "aria-pressed": String(st.mode === v), disabled: ro,
      onclick: (e) => { st.mode = v; e.currentTarget.parentNode.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === e.currentTarget))); draw(); } }, icon(ic), label)));

  body.append(
    h("div.md-when", {}, h("div.field", {}, h("label.label", {}, "Day"), dayIn), h("div.field", {}, h("label.label", {}, "Meal"), slotIn)),
    modeSeg, pane,
    h("div.field", {}, h("label.label", {}, "Note"), h("input.input", { type: "text", maxLength: 200, value: st.note, disabled: ro, placeholder: "Optional: who cooks, a side dish…", oninput: (e) => { st.note = e.target.value; } })));
  draw();

  async function save() {
    const payload = { day: st.day, slot: st.slot, note: st.note };
    if (meal) payload.id = meal.id;
    if (!isLeft) {
      if (st.mode === "text") {
        if (!st.text.trim()) { toast("Write what you eat, or pick a recipe.", true); return; }
        payload.text = st.text;
        payload.leftovers = null;
      } else {
        if (!st.recipe) { toast("Pick a recipe first.", true); return; }
        Object.assign(payload, { recipe: st.recipe, mult: st.mult, leftovers: st.leftovers });
      }
    }
    try {
      const res = await api(ctx.urls.save, { method: "POST", body: payload });
      dlg.close();
      onDone?.(res);
      toast(meal ? "Meal changed" : `Added to ${dayText(st.day)}`);
    } catch (err) { toast(err.message, true); }
  }
  async function remove() {
    const ok = await confirmDialog({ title: "Remove this meal?", message: meal.kind === "recipe" && leftoversNow ? "Its leftovers go too." : "It is taken off the calendar.", confirm: "Remove" });
    if (!ok) return;
    try { const res = await api(mealUrl(ctx.urls, meal.id, "delete"), { method: "POST", body: {} }); dlg.close(); onDone?.({ meals: [], deleted: res.deleted }); }
    catch (err) { toast(err.message, true); }
  }
  async function cooked() {
    try { const res = await api(mealUrl(ctx.urls, meal.id, "cooked"), { method: "POST", body: { cooked: !meal.cooked } }); dlg.close(); onDone?.(res); }
    catch (err) { toast(err.message, true); }
  }

  const cookUrl = meal?.kind === "recipe" && meal.recipe ? `${ctx.urls.cook.replace("{id}", meal.recipe)}?meal=${meal.id}` : null;
  const dlg = dialog({
    title: meal ? (ro ? "Meal" : "Change the meal") : "Add a meal", wide: true, body,
    foot: [
      h("div.left", {},
        meal && !ro ? h("button.btn.btn-ghost.btn-danger", { type: "button", onclick: remove }, icon("delete"), "Remove") : null,
        meal && !ro && meal.kind !== "text" ? h("button.btn.btn-ghost", { type: "button", onclick: cooked }, icon(meal.cooked ? "undo" : "done_all"), meal.cooked ? "Not cooked" : "Mark cooked") : null),
      cookUrl ? h("a.btn", { href: cookUrl }, icon("cooking"), "Start cooking") : null,
      h("button.btn", { type: "button", onclick: () => dlg.close() }, ro ? "Close" : "Cancel"),
      ro ? null : h("button.btn.btn-primary", { type: "button", onclick: save }, icon("check"), meal ? "Save" : "Add"),
    ],
  });
  // focus the search with a mouse; on a phone that would open the keyboard over the sheet
  if (!meal && !recipe && !ro && matchMedia("(hover: hover)").matches) setTimeout(() => search.focus(), 50);
  return dlg;
}
