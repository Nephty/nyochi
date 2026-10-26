// Every page: the phone "More" sheet, server messages as toasts, confirm-before-submit, the share dialog.
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

// <button data-share="recipe:12" data-name="Soup">
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-share]");
  if (btn) openShare(btn.dataset.share, btn.dataset.name || "");
});

function openShare(spec, name) {
  const [kind, id] = spec.split(":");
  const url = `/share/${kind}/${id}/`;
  const list = h("div");
  const input = h("input.input", { type: "text", placeholder: "Username", autocomplete: "off", "aria-label": "Username" });
  const error = h("div.formerr.hidden");
  const draw = (users) => {
    list.replaceChildren(...(users.length
      ? users.map((u) => h("div.userrow", {}, h("span.avatar", {}, u.username[0].toUpperCase()), h("b", {}, u.username),
          h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", style: { marginLeft: "auto" }, title: "Stop sharing", "aria-label": `Stop sharing with ${u.username}`,
            onclick: () => act({ remove_user_id: u.id }) }, icon("close"))))
      : [h("p.muted", {}, "Not shared with anyone yet. People you add can see and edit it, but only you can delete it.")]));
  };
  const act = async (payload) => {
    error.classList.add("hidden");
    try {
      const data = await api(url, { method: "POST", body: payload });
      draw(data.users);
      input.value = "";
    } catch (err) {
      error.replaceChildren(icon("error"), err.message);
      error.classList.remove("hidden");
    }
  };
  const add = () => input.value.trim() && act({ add_username: input.value.trim() });
  input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); add(); } });
  dialog({
    title: `Share${name ? ` “${name}”` : ""}`,
    body: [list, h("div.row", {}, input, h("button.btn.btn-primary", { type: "button", onclick: add }, icon("person_add"), "Add")), error],
  });
  api(url).then((data) => draw(data.users)).catch((err) => { error.replaceChildren(icon("error"), err.message); error.classList.remove("hidden"); });
  setTimeout(() => input.focus(), 50);
}

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
