// The "price by hand" dialog: what an amount of an ingredient costs when no Shopping product can price it ("€10 for
// 100 tbsp"), saved per ingredient and unit (recipes/models.py UnitPrice). Used by the recipe page (row: one recipe
// ingredient, with its amount) and the ingredient page (row without an amount).
// row: {ingredient, name, amount?, unit, abbr, manual?: {unit, paid, for}, hint?: {paid, for, name, size}}
import { api, dialog, h, icon, money, num } from "./ui.js";

export function priceDialog(row, { units, priceUrl }) {
  const start = row.manual || { paid: "", for: row.amount || 1, unit: row.unit };
  const paid = h("input.input", { type: "number", min: "0.01", step: "0.01", inputmode: "decimal", value: start.paid, "aria-label": "Price in euros", required: true });
  const amount = h("input.input", { type: "number", min: "0.001", step: "any", inputmode: "decimal", value: start.for, "aria-label": "Amount", required: true });
  const unit = h("select.select", { "aria-label": "Unit" },
    units.map((u) => h("option", { value: u.id, selected: u.id === start.unit }, `${u.abbr} (${u.name})`)));
  const result = h("div.price-result", { "aria-live": "polite" });
  const err = h("div.formerr.hidden");

  const unitOf = (id) => units.find((u) => u.id === Number(id));
  function preview() {
    const p = Number(paid.value), a = Number(amount.value), u = unitOf(unit.value), r = unitOf(row.unit);
    if (!(p > 0 && a > 0)) { result.replaceChildren(); return; }
    const per = p / a;
    if (!row.amount) { result.replaceChildren(h("b", {}, `${money(per)} per ${u.abbr}`)); return; }
    // the recipe's amount in the unit priced: the same unit, or one of the same kind (tbsp from a price per litre)
    const here = u.id === r.id ? row.amount * per
      : u.factor && r.factor && u.dimension === r.dimension && u.dimension !== "other" ? row.amount * r.factor / u.factor * per : null;
    result.replaceChildren(
      h("span", {}, `${money(per)} per ${u.abbr}`),
      here != null ? h("b", {}, `${money(here)} for ${num(row.amount)} ${row.abbr}`)
        : h("span.bad", {}, `Can’t turn ${u.abbr} into ${row.abbr}: price it per ${row.abbr}.`));
  }
  [paid, amount, unit].forEach((el) => el.addEventListener("input", preview));

  const hint = row.hint ? h("button.btn.btn-sm.hint", { type: "button", onclick: () => {
    paid.value = row.hint.paid;
    if (row.hint.for) { amount.value = row.hint.for; unit.value = row.unit; }
    preview();
    (row.hint.for ? paid : amount).focus();
  } }, icon("sell"), `${row.hint.name}: ${money(row.hint.paid)}${row.hint.size ? ` / ${row.hint.size}` : ""}`) : null;

  async function send(body) {
    try {
      await api(priceUrl, { method: "POST", body: { ingredient: row.ingredient, ...body } });
      location.reload();
    } catch (e) { err.textContent = e.message; err.classList.remove("hidden"); }
  }
  const save = () => {
    if (!(Number(paid.value) > 0 && Number(amount.value) > 0)) { err.textContent = "Give a price and an amount."; err.classList.remove("hidden"); return; }
    // a new unit replaces the price being edited (€10 for 1 l instead of €0.10 per tbsp)
    send({ unit: Number(unit.value), paid: paid.value, for: amount.value, replaces: row.manual && row.manual.unit !== Number(unit.value) ? row.manual.unit : null });
  };
  const form = h("form.price-form", { onsubmit: (e) => { e.preventDefault(); save(); } },
    hint ? h("div.field", {}, h("span.label", {}, "Linked product"), hint) : null,
    h("div.price-line", {},
      h("label.field", {}, h("span.label", {}, "Price (€)"), paid),
      h("span.for", {}, "for"),
      h("label.field", {}, h("span.label", {}, "Amount"), amount),
      h("label.field", {}, h("span.label", {}, "Unit"), unit)),
    result, err,
    h("p.price-note", {}, icon("info"), "Saved for every recipe with this ingredient. Shopping doesn’t update it."),
    h("button.hidden", { type: "submit" }));
  const dlg = dialog({
    title: `Price of ${row.name}`,
    body: form,
    foot: [
      row.manual ? h("button.btn.btn-ghost.btn-danger", { type: "button", style: { marginRight: "auto" }, onclick: () => send({ unit: row.manual.unit, remove: true }) }, icon("delete"), "Remove") : null,
      h("button.btn", { type: "button", onclick: () => dlg.close() }, "Cancel"),
      h("button.btn.btn-primary", { type: "button", onclick: save }, icon("check"), "Save"),
    ],
  });
  preview();
  paid.focus();
}
