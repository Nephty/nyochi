// The shopping list planner: recipes (or the meal plan's days) and items added by hand; the server builds the receipt.
import { api, debounce, h, icon, money, prefs, readJson, toast } from "./ui.js";
import { receiptText, renderReceipt } from "./receipt.js";
import { pager } from "./swipe.js";

const P = readJson("plan-data");
const root = document.querySelector("[data-plan]");
if (P && root) {
  const $ = (s) => root.querySelector(s);
  const byId = new Map(P.recipes.map((r) => [r.id, r]));

  const saved = prefs.get("plan", {});
  // From the meal plan (P.covers): exactly its recipes and portions; otherwise what was left here, plus ?recipe=
  const sel = new Map(P.covers ? [] : Object.entries(saved.sel || {}).map(([k, v]) => [Number(k), v]).filter(([k]) => byId.has(k)));
  for (const { id, mult } of P.preselect) if (byId.has(id) && (P.covers || !sel.has(id))) sel.set(id, mult);
  const extras = P.covers ? [] : (saved.extras || []).filter((x) => typeof x === "string");
  let covers = P.covers;
  const f = { q: "", sale: false };
  let location = saved.location && P.locations.some((l) => l.id === saved.location) ? saved.location : null;
  let lastReceipt = null;

  const persist = () => prefs.set("plan", { sel: Object.fromEntries(sel), extras, location });

  // ---- recipes
  $("#plan-ings").append(...P.ingredients.map((name) => h("option", { value: name })));
  $("[data-q]").addEventListener("input", (e) => { f.q = e.target.value.toLowerCase().trim(); draw(); });
  $("[data-sale]").addEventListener("click", () => { f.sale = !f.sale; draw(); });

  const matches = (r) => (!f.q || f.q.split(/\s+/).every((w) => r.name.toLowerCase().includes(w))) && (!f.sale || r.promos > 0);

  function card(r) {
    const on = sel.has(r.id);
    return h("div.pcard" + (on ? ".sel" : ""), { dataset: { id: r.id }, role: "button", tabindex: 0,
      onclick: (e) => { if (e.target.closest(".qty-ctl")) return; setSel(r.id, !on); },
      onkeydown: (e) => { if ((e.key === "Enter" || e.key === " ") && !e.target.closest(".qty-ctl")) { e.preventDefault(); setSel(r.id, !on); } } },
      h("label.chk", {}, h("input", { type: "checkbox", checked: on, tabIndex: -1, "aria-label": `Add ${r.name}`, onclick: (e) => e.stopPropagation(), onchange: (e) => setSel(r.id, e.target.checked) }), h("span", {}, icon("check"))),
      h("div.nm", {}, r.name),
      h("div.qty-ctl", {},
        h("button.btn.btn-sm.btn-icon", { type: "button", "aria-label": "Fewer portions", onclick: () => step(r.id, -1) }, icon("remove")),
        h("span.v", { title: "Portions" }, `×${mult(sel.get(r.id) ?? 1)}`),
        h("button.btn.btn-sm.btn-icon", { type: "button", "aria-label": "More portions", onclick: () => step(r.id, 1) }, icon("add"))),
      h("div.meta", {}, [
        h("span", {}, `${r.count} item${r.count === 1 ? "" : "s"}`),
        r.cost != null ? h("span.tag.soft", { title: `${r.priced} of ${r.count} priced` }, `≈ ${money(r.cost)}`) : null,
        r.promos ? h("span.chip.good", {}, `${r.promos} on sale`) : null,
      ].filter(Boolean)));
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
    $("[data-sale]").setAttribute("aria-pressed", String(f.sale));
    const rows = P.recipes.filter(matches).sort((a, b) => a.name.localeCompare(b.name));
    $("[data-list]").replaceChildren(h("div.plan-list", {}, rows.map(card)));
    $("[data-empty]").classList.toggle("hidden", rows.length > 0);
    $("[data-badge]").textContent = sel.size + extras.length;
    drawPicked();
  }

  // ---- items added by hand
  const itemInput = $("[data-item]");
  $("[data-add]").addEventListener("submit", (e) => {
    e.preventDefault();
    const name = itemInput.value.replace(/\s+/g, " ").trim();
    if (!name) return;
    if (!extras.some((x) => x.toLowerCase() === name.toLowerCase())) extras.push(name);
    itemInput.value = "";
    afterChange();
  });
  const removeExtra = (name) => { extras.splice(extras.indexOf(name), 1); afterChange(); };

  function drawPicked() {
    const banner = $("[data-covers]");
    banner.classList.toggle("hidden", !covers);
    if (covers) banner.replaceChildren(icon("calendar_month"), h("b", {}, covers.label),
      h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", "aria-label": "Forget the days", onclick: () => { covers = null; drawPicked(); } }, icon("close")));
    $("[data-picked]").replaceChildren(
      ...[...sel].map(([id, m]) => h("span.chip", { style: { cursor: "pointer" }, title: "Remove", onclick: () => setSel(id, false) },
        icon("menu_book"), `${byId.get(id).name}${m !== 1 ? ` ×${mult(m)}` : ""}`, icon("close"))),
      ...extras.map((name) => h("span.chip", { style: { cursor: "pointer" }, title: "Remove", onclick: () => removeExtra(name) }, name, icon("close"))));
  }

  // ---- shop
  const locSel = $("[data-location]");
  locSel.append(h("option", { value: "" }, "By category"), ...P.locations.map((l) => h("option", { value: l.id, selected: l.id === location }, l.name)));
  locSel.addEventListener("change", () => { location = locSel.value ? Number(locSel.value) : null; persist(); loadReceipt(); });
  if (!P.locations.length) locSel.closest(".plan-bar").hidden = true;

  // ---- the receipt
  const box = $("[data-receipt]");
  const actions = $("[data-actions]");
  const body = () => ({ recipes: [...sel].map(([id, mult]) => ({ id, mult })), extras, location });
  let seq = 0;
  async function loadReceipt() {
    if (!sel.size && !extras.length) {
      lastReceipt = null;
      actions.hidden = true;
      renderReceipt(box, { sections: [], totals: { lines: 0 }, location: null }, { title: "Shopping list", emptyTitle: "Empty list" });
      return;
    }
    const mine = ++seq;
    try {
      const data = await api(P.urls.receipt, { method: "POST", body: body() });
      if (mine !== seq) return;
      lastReceipt = data;
      actions.hidden = false;
      renderReceipt(box, data, { title: $("[data-name]").value.trim() || "Shopping list" });
    } catch (err) { if (mine === seq) toast(err.message, true); }
  }
  const loadSoon = debounce(loadReceipt, 150);

  $("[data-save]")?.addEventListener("click", async (e) => {
    e.currentTarget.disabled = true;
    try {
      const made = await api(P.urls.save, { method: "POST", body: { ...body(), name: $("[data-name]").value, covers } });
      prefs.set("plan", {});
      window.location.href = made.url;
    } catch (err) { toast(err.message, true); e.currentTarget.disabled = false; }
  });
  $("[data-copy]").addEventListener("click", async () => {
    if (!lastReceipt) return;
    try { await navigator.clipboard.writeText(receiptText(lastReceipt, $("[data-name]").value.trim() || "Shopping list")); toast("Copied"); }
    catch { toast("Your browser wouldn’t let me copy.", true); }
  });
  $("[data-print]").addEventListener("click", () => window.print());
  $("[data-name]").addEventListener("input", (e) => {
    const t = box.querySelector(".rcpt-title");
    if (t) t.textContent = e.target.value.trim() || "Shopping list";
  });

  const pane = (name) => {
    root.dataset.pane = name;
    root.querySelectorAll("[data-pane-btn]").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.paneBtn === name)));
  };
  root.querySelectorAll("[data-pane-btn]").forEach((b) => b.addEventListener("click", () => pane(b.dataset.paneBtn)));
  if (covers) pane("list");   // from the meal plan: the list is what you came for
  // phones: swipe between the two panes
  const phone = matchMedia("(max-width: 760px)");
  pager($(".plan-left"), { go: () => pane("list"), canPrev: () => false, canNext: () => phone.matches });
  pager($(".plan-right"), { go: () => pane("add"), canNext: () => false, canPrev: () => phone.matches });

  draw();
  loadSoon();
}
