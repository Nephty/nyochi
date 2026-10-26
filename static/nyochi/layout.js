// The shop layout editor: one location at a time. Left: the walking route (drag, or ↑ ↓) with what sits in each
// aisle. Right: which aisle each ingredient category is in, and exceptions for single ingredients. One Save.
import { enhanceCombo, setChoices } from "./combo.js";
import { api, confirmDialog, h, icon, readJson, toast } from "./ui.js";

const E = readJson("layout-data");
const mount = document.querySelector("[data-layout]");
const tabs = document.querySelector("[data-loc-tabs]");

if (E && mount) {
  const aisleName = Object.fromEntries(E.aisles.map((a) => [a.id, a.name]));
  const catName = Object.fromEntries(E.categories.map((c) => [c.value, c.label]));
  setChoices(E.ingredients.map((i) => ({ id: i.id, name: i.name })));
  let current = null;       // location id
  let st = null;            // the edited layout {route, mappings, overrides}
  let saved = "";
  let dragged = null;

  const snapshot = () => JSON.stringify(st);
  const dirty = () => snapshot() !== saved;
  const urlFor = (kind, id) => E.urls[kind].replace("/0/", `/${id}/`);

  async function open(id) {
    if (current !== null && dirty() && !(await confirmDialog({ title: "Unsaved changes", message: "Discard the changes you made to this location’s layout?", confirm: "Discard" }))) return;
    current = id;
    const src = E.layouts[id];
    st = { route: [...src.route], mappings: { ...src.mappings }, overrides: src.overrides.map((o) => ({ ...o })) };
    saved = src.configured ? snapshot() : "";
    tabs.querySelectorAll("[data-loc]").forEach((b) => b.classList.toggle("on", Number(b.dataset.loc) === id));
    render();
  }
  tabs.querySelectorAll("[data-loc]").forEach((b) => b.addEventListener("click", () => open(Number(b.dataset.loc))));
  window.addEventListener("beforeunload", (e) => { if (current !== null && dirty()) { e.preventDefault(); e.returnValue = ""; } });

  function move(index, delta) {
    const to = index + delta;
    if (to < 0 || to >= st.route.length) return;
    st.route.splice(to, 0, st.route.splice(index, 1)[0]);
    render();
  }
  function removeFromRoute(id) {
    st.route = st.route.filter((a) => a !== id);
    for (const c of Object.keys(st.mappings)) if (st.mappings[c] === id) delete st.mappings[c];
    st.overrides = st.overrides.filter((o) => o.aisle_id !== id);
    render();
  }

  function stopCard(id, index) {
    const cats = Object.entries(st.mappings).filter(([, a]) => a === id).map(([c]) => c);
    const ex = st.overrides.filter((o) => o.aisle_id === id);
    const card = h("li.stop-card", { draggable: E.canEdit, dataset: { id } },
      h("span.grip", { title: "Drag to reorder" }, icon("drag_indicator")),
      h("span.stop", {}, index + 1),
      h("span.nm", {}, aisleName[id]),
      E.canEdit ? h("span.btns", {},
        h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", "aria-label": `Move ${aisleName[id]} earlier`, disabled: index === 0, onclick: () => move(index, -1) }, icon("arrow_upward")),
        h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", "aria-label": `Move ${aisleName[id]} later`, disabled: index === st.route.length - 1, onclick: () => move(index, 1) }, icon("arrow_downward")),
        h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", "aria-label": `Take ${aisleName[id]} off this route`, title: "Not in this location", onclick: () => removeFromRoute(id) }, icon("close"))) : null,
      h("span.holds", {}, cats.map((c) => h("span.chip", {}, catName[c])), ex.map((o) => h("span.chip.ex", { title: "Exception" }, o.name))));
    if (E.canEdit) {
      card.addEventListener("dragstart", (e) => { dragged = id; card.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(id)); });
      card.addEventListener("dragend", () => { dragged = null; card.classList.remove("dragging"); mount.querySelectorAll(".over").forEach((x) => x.classList.remove("over")); });
      card.addEventListener("dragover", (e) => { if (dragged !== null && dragged !== id) { e.preventDefault(); card.classList.add("over"); } });
      card.addEventListener("dragleave", () => card.classList.remove("over"));
      card.addEventListener("drop", (e) => {
        e.preventDefault();
        if (dragged === null || dragged === id) return;
        st.route.splice(st.route.indexOf(dragged), 1);
        st.route.splice(st.route.indexOf(id), 0, dragged);
        render();
      });
    }
    return card;
  }

  function render() {
    const off = E.aisles.filter((a) => !st.route.includes(a.id));
    const others = E.locations.filter((l) => l.id !== current);
    const savebar = h("div.savebar" + (dirty() ? ".is-dirty" : ""), {},
      h("span.dirty", {}, "Unsaved changes"),
      h("span.muted.sm", {}, dirty() ? "" : "Saved"),
      h("span.spacer"),
      E.canEdit && others.length ? h("select.select", { style: { width: "auto" }, "aria-label": "Copy the layout of another location",
        onchange: async (e) => {
          const from = Number(e.target.value); e.target.value = "";
          if (!from) return;
          if (!(await confirmDialog({ title: "Copy a layout", message: `Replace this location’s layout with the one of “${E.locations.find((l) => l.id === from).name}”?`, confirm: "Copy", danger: false }))) return;
          try { await api(urlFor("copy", current), { method: "POST", body: { from } }); location.reload(); } catch (err) { toast(err.message, true); }
        } }, h("option", { value: "" }, "Copy from…"), others.map((l) => h("option", { value: l.id }, l.name))) : null,
      E.canEdit ? h("button.btn.btn-primary", { type: "button", disabled: !dirty() && saved !== "", onclick: save }, icon("check"), "Save layout") : null);

    const route = h("ol.route", {}, st.route.map(stopCard));
    const left = h("div.stack", {},
      h("section.panel", {}, h("div.panel-head", {}, h("h2", {}, "Walking route"), h("span.muted.sm", { style: { marginLeft: "auto" } }, "in the order you reach them")),
        h("div.panel-body", {}, st.route.length ? route : h("p.muted", { style: { margin: 0 } }, "No aisle on this route. Add aisles above, then place them here."),
          off.length ? h("div", { style: { marginTop: "1rem" } }, h("div.label", { style: { marginBottom: ".4rem" } }, "Not in this location"),
            h("div.bank", {}, off.map((a) => E.canEdit ? h("button.pill", { type: "button", onclick: () => { st.route.push(a.id); render(); } }, icon("add"), a.name) : h("span.tagpill", {}, a.name)))) : null)));

    const select = (value, onchange) => h("select.select", { onchange, disabled: !E.canEdit, "aria-label": "Aisle" },
      h("option", { value: "" }, "Elsewhere (not placed)"),
      st.route.map((a) => h("option", { value: a, selected: a === value }, aisleName[a])));
    const catRows = E.categories.map((c) => h("div.crow", {}, h("span", {}, catName[c.value]),
      select(st.mappings[c.value], (e) => { if (e.target.value) st.mappings[c.value] = Number(e.target.value); else delete st.mappings[c.value]; render(); })));

    const exceptions = h("div", {}, st.overrides.map((o, i) => h("div.override-row", {}, h("b", {}, o.name),
      select(o.aisle_id, (e) => { o.aisle_id = Number(e.target.value) || o.aisle_id; render(); }),
      E.canEdit ? h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", "aria-label": `Remove the exception for ${o.name}`, onclick: () => { st.overrides.splice(i, 1); render(); } }, icon("close")) : null)));
    let addBox = null;
    if (E.canEdit && st.route.length) {
      const sel = h("select", {}, h("option", { value: "" }, ""), E.ingredients.map((i) => h("option", { value: i.id }, i.name)));
      const box = h("div.combo", {}, sel);
      const aisleSel = h("select.select", { "aria-label": "Aisle for the exception" }, st.route.map((a) => h("option", { value: a }, aisleName[a])));
      const add = h("button.btn.btn-sm", { type: "button", onclick: () => {
        const id = Number(sel.value);
        if (!id) { toast("Pick an ingredient first.", true); return; }
        const name = E.ingredients.find((i) => i.id === id).name;
        const aisle = Number(aisleSel.value);
        const existing = st.overrides.find((o) => o.ingredient_id === id);
        if (existing) existing.aisle_id = aisle; else st.overrides.push({ ingredient_id: id, name, aisle_id: aisle });
        render();
      } }, icon("add"), "Add");
      addBox = h("div.override-row", {}, box, aisleSel, add);
      queueMicrotask(() => enhanceCombo(box, { allowCreate: false }));
    }
    const right = h("div.stack", {},
      h("section.panel", {}, h("div.panel-head", {}, h("h2", {}, "Where things are")),
        h("div.panel-body", {}, h("div.catmap", {}, catRows),
          h("p.help", { style: { margin: ".8rem 0 0" } }, "Anything not placed goes to the end of the list, under “Elsewhere”."))),
      h("section.panel", {}, h("div.panel-head", {}, h("h2", {}, "Exceptions")),
        h("div.panel-body", {}, h("p.help", { style: { marginTop: 0 } }, "For the odd one out: the olives that live with the tins, not the vegetables."), exceptions, addBox)));

    mount.replaceChildren(h("div.lay", {}, left, right), savebar);
  }

  async function save() {
    try {
      await api(urlFor("layout", current), { method: "POST", body: { route: st.route, mappings: st.mappings, overrides: st.overrides.map((o) => ({ ingredient_id: o.ingredient_id, aisle_id: o.aisle_id })) } });
      E.layouts[current] = { configured: true, route: [...st.route], mappings: { ...st.mappings }, overrides: st.overrides.map((o) => ({ ...o })) };
      saved = snapshot();
      toast("Layout saved.");
      render();
    } catch (err) { toast(err.message, true); }
  }

  const first = Number(new URLSearchParams(location.search).get("loc")) || E.locations[0]?.id;
  if (first) open(first);
}
