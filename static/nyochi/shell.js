// Every page: the phone "More" sheet, server messages as toasts, confirm-before-submit.
import { api, confirmDialog, dialog, h, icon, readJson, toast } from "./ui.js";

const sheet = document.querySelector("[data-more-sheet]");
const sheetBack = document.querySelector("[data-sheet-back]");
function setSheet(open) {
  sheet?.classList.toggle("open", open);
  sheetBack?.classList.toggle("open", open);
}
document.querySelector("[data-more]")?.addEventListener("click", () => setSheet(!sheet.classList.contains("open")));
sheetBack?.addEventListener("click", () => setSheet(false));

for (const m of readJson("flash") || []) toast(m.text, m.level === "error" || m.level === "warning");

// <form data-confirm="Delete “Soup”?" data-confirm-button="Delete"> asks first
document.addEventListener("submit", async (e) => {
  const form = e.target;
  const message = form.dataset?.confirm;
  if (!message || form.dataset.confirmed) return;
  e.preventDefault();
  const ok = await confirmDialog({ message, confirm: form.dataset.confirmButton || "Delete" });
  if (ok) {
    form.dataset.confirmed = "1";
    form.requestSubmit(e.submitter || undefined);
  }
});

// <form data-rename="Current name" data-rename-title="Rename aisle"> with a hidden name field and a [data-rename-btn]
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-rename-btn]");
  if (!btn) return;
  const form = btn.closest("form");
  const field = form.querySelector("[name=name]");
  const input = h("input.input", { type: "text", value: form.dataset.rename, maxLength: 200, "aria-label": "Name" });
  const go = () => { field.value = input.value; form.submit(); };
  const dlg = dialog({ title: form.dataset.renameTitle || "Rename", body: input, foot: [
    h("button.btn", { type: "button", onclick: () => dlg.close() }, "Cancel"),
    h("button.btn.btn-primary", { type: "button", onclick: go }, "Rename")] });
  input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); go(); } });
  input.select();
});
