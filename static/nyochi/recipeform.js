// The recipe form: ingredient rows are added from a <template> (their prefix is the formset's next index),
// removed by ticking Django's own DELETE box, and every ingredient select becomes a searchable picker.
import { enhanceCombo, setChoices } from "./combo.js";
import { readJson } from "./ui.js";

const form = document.querySelector("[data-recipe-form]");
if (form) {
  const rows = form.querySelector("[data-rows]");
  const template = form.querySelector("[data-row-template]");
  const total = form.querySelector('input[name$="-TOTAL_FORMS"]');
  const prefix = total.name.replace("-TOTAL_FORMS", "");

  // every ingredient of the first row's <select> (they all hold the same options)
  const first = rows.querySelector("select[name$='-ingredient']") || template.content.querySelector("select");
  setChoices([...first.options].filter((o) => o.value).map((o) => ({ id: Number(o.value), name: o.text })));

  const wire = (row) => {
    enhanceCombo(row.querySelector("[data-combo]"));
    row.querySelector("[data-remove-row]").addEventListener("click", () => {
      const del = row.querySelector('input[name$="-DELETE"]');
      if (del) del.checked = true;
      row.classList.add("deleted");
      if (!rows.querySelector("[data-row]:not(.deleted)")) addRow();
    });
  };
  const addRow = () => {
    const index = Number(total.value);
    const html = template.innerHTML.replaceAll("__prefix__", index);
    const holder = document.createElement("div");
    holder.innerHTML = html;
    const row = holder.firstElementChild;
    rows.append(row);
    total.value = index + 1;
    wire(row);
    row.querySelector("input[type=text]")?.focus();
  };
  rows.querySelectorAll("[data-row]").forEach(wire);
  form.querySelector("[data-add-row]").addEventListener("click", addRow);
}
