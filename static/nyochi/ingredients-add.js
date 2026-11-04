// "Add several" on the Ingredients page: one name per line (or separated by commas), all in one category; their seasons
// and products are filled in later, one by one.
import { api, dialog, h, icon, readJson } from "./ui.js";

const D = readJson("several-data");
if (D) {
  document.querySelectorAll("[data-add-several]").forEach((b) => b.addEventListener("click", open));
}

function open() {
  const names = h("textarea.textarea", { rows: 8, placeholder: "Leek\nChickpeas\nCumin", "aria-label": "Names, one per line" });
  const category = h("select.select", { "aria-label": "Category" },
    D.categories.map((c) => h("option", { value: c.key, selected: c.key === D.default }, c.label)));
  const err = h("div.formerr.hidden");
  const count = h("span.muted.sm");
  const list = () => names.value.split(/[\n,;]+/).map((s) => s.trim()).filter(Boolean);
  names.addEventListener("input", () => { const n = list().length; count.textContent = n ? `${n} name${n === 1 ? "" : "s"}` : ""; });
  const add = async () => {
    if (!list().length) { err.textContent = "Write at least one name."; err.classList.remove("hidden"); return; }
    try {
      await api(D.url, { method: "POST", body: { names: list(), category: category.value } });
      location.reload();
    } catch (e) { err.textContent = e.message; err.classList.remove("hidden"); }
  };
  const dlg = dialog({
    title: "Add several ingredients",
    body: h("div.stack", { style: { gap: ".8rem" } },
      h("label.field", {}, h("span.label", {}, "Names, one per line"), names),
      h("label.field", {}, h("span.label", {}, "Category"), category),
      err),
    foot: [count, h("button.btn", { type: "button", style: { marginLeft: "auto" }, onclick: () => dlg.close() }, "Cancel"),
      h("button.btn.btn-primary", { type: "button", onclick: add }, icon("add"), "Add")],
  });
  names.focus();
}
