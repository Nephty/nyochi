// The meal calendar's week: days × slots on a desktop (drag a meal to move it); on a phone, a day strip and one day.
// Meals change through the meal dialog (meal-dialog.js); the summary under the grid follows every change.
import { api, dialog, euroDate, h, icon, money, readJson, toast } from "./ui.js";
import { addDays, dayText, mealDialog, mealUrl, mult, parseDay } from "./meal-dialog.js";
import { slider } from "./swipe.js";

const B = readJson("meals-data");
const root = document.querySelector("[data-week]");

if (B && root) {
  let meals = B.meals;
  const byId = new Map(B.recipes.map((r) => [r.id, r]));
  const ctx = { recipes: B.recipes, slots: B.slots, urls: B.urls, canEdit: B.canEdit, get meals() { return meals; } };
  const WEEKDAY = new Intl.DateTimeFormat("en-GB", { weekday: "short" });
  const LONG = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long" });

  function merge(res) {
    const gone = new Set(res.deleted || []);
    const fresh = new Map((res.meals || []).map((m) => [m.id, m]));
    meals = meals.filter((m) => !gone.has(m.id) && !fresh.has(m.id)).concat([...fresh.values()]);
    draw();
  }
  const open = (meal, at = {}) => mealDialog({ meal, at, ctx, onDone: merge });

  function card(m) {
    const r = m.recipe ? byId.get(m.recipe) : null;
    const el = h(`div.mc.k-${m.kind}${m.cooked ? ".cooked" : ""}`, {
      role: "button", tabindex: 0, draggable: B.canEdit ? "true" : null, dataset: { id: m.id },
      title: m.note || null,
      onclick: () => open(m), onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(m); } },
      ondragstart: (e) => { e.dataTransfer.setData("text/plain", String(m.id)); e.dataTransfer.effectAllowed = "move"; el.classList.add("dragging"); },
      ondragend: () => el.classList.remove("dragging"),
    },
      h("span.nm", {}, m.cooked ? icon("done_all") : null, m.name),
      h("span.meta", {},
        m.kind === "recipe" && m.mult !== 1 ? h("b", {}, `×${mult(m.mult)}`) : null,
        r?.inSeason ? h("span.mk.season", { title: "Main ingredients in season" }, icon("eco")) : null,
        r?.promos ? h("span.mk.sale", { title: `${r.promos} ingredient${r.promos === 1 ? "" : "s"} on sale` }, icon("sell")) : null,
        m.leftovers.length ? h("span.mk", { title: "Makes leftovers" }, icon("restart_alt")) : null,
        m.note ? h("span.note", {}, m.note) : null));
    return el;
  }

  function dropZone(el, day, slot) {
    if (!B.canEdit) return;
    el.addEventListener("dragover", (e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; el.classList.add("over"); });
    el.addEventListener("dragleave", () => el.classList.remove("over"));
    el.addEventListener("drop", async (e) => {
      e.preventDefault();
      el.classList.remove("over");
      const id = Number(e.dataTransfer.getData("text/plain"));
      const m = meals.find((x) => x.id === id);
      if (!m || (m.day === day && m.slot === slot)) return;
      try { merge(await api(mealUrl(B.urls, id, "move"), { method: "POST", body: { day, slot } })); }
      catch (err) { toast(err.message, true); }
    });
  }

  let lists = [...B.lists];
  function listFor(day) { return lists.find((l) => l.from <= day && day <= l.to); }

  function draw() {
    const cells = [h("div.wk-corner")];
    B.slots.forEach((s, i) => cells.push(h("div.wk-slot", { style: { gridRow: i + 2 } }, icon(s.icon), h("span", {}, s.label))));
    B.days.forEach((d, c) => {
      const list = listFor(d.iso);
      const dayMeals = meals.filter((m) => m.day === d.iso);
      cells.push(h(`div.wk-day${d.today ? ".today" : ""}${dayMeals.length ? "" : ".none"}`, { style: { gridColumn: c + 2 } },
        h("span.wd", {}, WEEKDAY.format(parseDay(d.iso))), h("b.dn", {}, String(parseDay(d.iso).getDate())),
        list ? h("a.bought", { href: list.url, title: `Shopped for in “${list.name}”` }, icon("shopping_basket")) : null));
      B.slots.forEach((s, i) => {
        const here = meals.filter((m) => m.day === d.iso && m.slot === s.value);
        const cell = h(`div.wk-cell${here.length ? "" : ".empty"}${d.today ? ".today" : ""}`, { style: { gridColumn: c + 2, gridRow: i + 2 } },
          here.map(card),
          B.canEdit ? h("button.add", { type: "button", title: `Add ${s.label.toLowerCase()}`, "aria-label": `Add ${s.label.toLowerCase()} on ${dayText(d.iso)}`, onclick: () => open(null, { day: d.iso, slot: s.value }) }, icon("add")) : null);
        dropZone(cell, d.iso, s.value);
        cells.push(cell);
      });
    });
    root.replaceChildren(...cells);
    drawPhone();
    drawSummary();
  }

  // ---- phone: the seven days of the week shown (a dot per meal), then one day slot by slot. The days are a slider:
  // the day before and the day after are already drawn beside it, and a neighbouring week is loaded in the background
  // (once) as soon as the day shown is two days or less from it, so a swipe never waits.
  const phone = document.querySelector("[data-phone]");
  const loaded = new Set([B.days[0].iso]);   // the Mondays whose meals are here
  const loading = new Map();
  let focus = B.days.some((d) => d.iso === B.focus) ? B.focus : (B.days.find((d) => d.today) || B.days[0]).iso;
  const mondayOf = (iso) => addDays(iso, -((parseDay(iso).getDay() + 6) % 7));
  const SHORT = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });

  function loadWeek(mon) {
    if (loaded.has(mon) || loading.has(mon)) return;
    loading.set(mon, api(B.urls.weekData, { query: { start: mon } }).then((w) => {
      loaded.add(mon);
      const have = new Set(meals.map((m) => m.id));
      meals = meals.concat(w.meals.filter((m) => !have.has(m.id)));
      const known = new Set(lists.map((l) => l.id));
      lists = lists.concat(w.lists.filter((l) => !known.has(l.id)));
      drawPhone();
    }).catch(() => { /* tried again on the next swipe */ }).finally(() => loading.delete(mon)));
  }
  const around = () => [-2, 0, 2].forEach((o) => loadWeek(mondayOf(addDays(focus, o))));

  function dayPanel(iso) {
    const ready = loaded.has(mondayOf(iso));
    const list = listFor(iso);
    return h(`div.pw-page${ready ? "" : ".loading"}`, {},
      h("div.pw-day", {}, h("h2", {}, LONG.format(parseDay(iso))),
        list ? h("a.bought", { href: list.url, title: `Shopped for in “${list.name}”` }, icon("shopping_basket")) : null),
      h("div.pw-slots", {}, B.slots.map((s) => {
        const here = ready ? meals.filter((m) => m.day === iso && m.slot === s.value) : [];
        return h(`section.pw-slot${here.length ? "" : ".free"}`, {},
          h("div.pw-k", {}, icon(s.icon), h("span", {}, s.label),
            B.canEdit && ready ? h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", "aria-label": `Add ${s.label.toLowerCase()}`, onclick: () => open(null, { day: iso, slot: s.value }) }, icon("add")) : null),
          here.length ? h("div.pw-meals", {}, here.map(card)) : null);
      })));
  }

  const strip = h("div.pw-strip", { role: "tablist" });
  const dayBox = h("div.pw-days");
  phone?.append(strip, dayBox);
  const days = phone ? slider(dayBox, { span: 7, render: (o) => dayPanel(addDays(focus, o)), onMove: (d) => { focus = addDays(focus, d); moved(); } }) : null;
  const nav = document.querySelector(".pw-nav");

  function drawStrip() {
    const mon = mondayOf(focus);
    strip.replaceChildren(...Array.from({ length: 7 }, (_, i) => {
      const iso = addDays(mon, i);
      const n = meals.filter((m) => m.day === iso).length;
      return h(`button.pw-d${iso === focus ? ".on" : ""}${iso === B.today ? ".today" : ""}`, { type: "button", role: "tab", "aria-selected": String(iso === focus), onclick: () => jump(iso) },
        h("span.wd", {}, WEEKDAY.format(parseDay(iso))), h("b", {}, String(parseDay(iso).getDate())),
        h("span.dots", {}, Array.from({ length: Math.min(n, 4) }, () => h("i"))));
    }));
    if (!nav) return;
    const thisWeek = mon === mondayOf(B.today);
    nav.querySelector("[data-wk-title]").textContent = thisWeek ? "This week" : `Week of ${SHORT.format(parseDay(mon))}`;
    nav.querySelector("[data-wk-range]").textContent = `${SHORT.format(parseDay(mon))} – ${SHORT.format(parseDay(addDays(mon, 6)))}`;
  }
  function moved() {
    drawStrip();
    around();
  }
  function jump(iso) {
    if (iso === focus) return;
    focus = iso;
    moved();
    days.refresh();
  }
  function drawPhone() {
    if (!phone) return;
    drawStrip();
    days.refresh();
  }
  if (phone && nav) {
    nav.querySelector("[data-wk-prev]").addEventListener("click", (e) => { e.preventDefault(); jump(addDays(focus, -7)); });
    nav.querySelector("[data-wk-next]").addEventListener("click", (e) => { e.preventDefault(); jump(addDays(focus, 7)); });
    nav.querySelector(".pw-ttl").addEventListener("click", (e) => { e.preventDefault(); jump(B.today); });
  }
  if (phone) around();

  // under the grid: how much is planned, what it costs, what two recipes share
  const summary = document.querySelector("[data-summary]");
  const weekMeals = () => meals.filter((m) => m.day >= B.days[0].iso && m.day <= B.days[6].iso);
  function drawSummary() {
    const meals = weekMeals();
    const cooking = meals.filter((m) => m.kind === "recipe");
    const cost = cooking.reduce((sum, m) => sum + (byId.get(m.recipe)?.cost ?? 0) * m.mult, 0);
    const priced = cooking.filter((m) => byId.get(m.recipe)?.cost != null).length;
    const empty = B.days.filter((d) => !meals.some((m) => m.day === d.iso)).length;
    const uses = new Map();
    for (const m of cooking) {
      const r = byId.get(m.recipe);
      for (const i of r?.ing || []) {
        if (!uses.has(i)) uses.set(i, new Set());
        uses.get(i).add(r.name);
      }
    }
    const shared = [...uses].filter(([, rs]) => rs.size > 1).sort((a, b) => b[1].size - a[1].size);
    summary.replaceChildren(...[
      h("section.panel.wk-stats", {}, h("div.panel-body", {},
        h("div.stat", {}, h("b", {}, String(meals.length)), h("span", {}, `meal${meals.length === 1 ? "" : "s"} planned`)),
        h("div.stat", {}, h("b", {}, String(cooking.length)), h("span", {}, "to cook")),
        h("div.stat", {}, h("b", {}, priced ? `≈ ${money(cost)}` : "–"), h("span", {}, !cooking.length ? "ingredients" : !priced ? "no Shopping prices linked" : priced < cooking.length ? `for the ${priced} of ${cooking.length} priced` : "ingredients, at Shopping prices")),
        h("div.stat", {}, h("b", {}, String(empty)), h("span", {}, `empty day${empty === 1 ? "" : "s"}`)))),
      shared.length ? h("section.panel.wk-shared", {},
        h("div.panel-head", {}, h("h2", {}, "Bought once, used twice"), h("span.muted.sm", {}, "ingredients more than one of this week's recipes use")),
        h("div.panel-body", {}, h("ul.shared", {}, shared.slice(0, 12).map(([i, rs]) => h("li", {}, h("b", {}, B.ingredients[i] || "?"), h("span.muted", {}, [...rs].join(" · "))))))) : null].filter(Boolean));
  }

  // Shopping list for a range of days -> the list planner, preset
  document.querySelectorAll("[data-shop]").forEach((b) => b.addEventListener("click", () => {
    const first = B.days.find((d) => d.iso >= B.today)?.iso || B.days[0].iso;
    const from = h("input.input", { type: "date", value: first });
    const to = h("input.input", { type: "date", value: B.days.at(-1).iso });
    const count = h("p.muted.sm", { style: { margin: 0 } });
    const recount = () => {
      const n = meals.filter((m) => m.kind === "recipe" && m.day >= from.value && m.day <= to.value).length;
      const inWeek = from.value >= B.days[0].iso && to.value <= B.days.at(-1).iso;
      count.textContent = !from.value || !to.value || !inWeek ? "" : `${n} meal${n === 1 ? "" : "s"} to cook.`;
    };
    from.addEventListener("input", recount); to.addEventListener("input", recount); recount();
    const dlg = dialog({
      title: "Shopping list for these days",
      body: [h("div.md-when", {}, h("div.field", {}, h("label.label", {}, "From"), euroDate(from)), h("div.field", {}, h("label.label", {}, "To"), euroDate(to))), count],
      foot: [h("button.btn", { type: "button", onclick: () => dlg.close() }, "Cancel"),
        h("button.btn.btn-primary", { type: "button", onclick: () => {
          if (!from.value || !to.value) return;
          location.href = `${B.urls.shop}?start=${from.value}&end=${to.value}`;
        } }, icon("add_shopping_cart"), "Make the list")],
    });
  }));

  draw();
}
