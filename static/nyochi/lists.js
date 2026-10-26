// A saved list: tick items off as you shop, walk the shop in the order of a chosen location, add what's missing.
import { api, h, readJson, toast } from "./ui.js";
import { receiptText, renderReceipt } from "./receipt.js";

const D = readJson("list-data");
const box = document.querySelector("[data-receipt]");
if (D && box) {
  let data = D.receipt;
  let location = D.location;
  const name = document.querySelector("h1").textContent.trim();

  function recount() {
    const lines = data.sections.flatMap((s) => s.lines);
    data.progress = { done: lines.filter((l) => l.checked).length, total: lines.length };
  }
  function draw(focusId) {
    recount();
    renderReceipt(box, data, {
      checkable: D.canEdit, progress: data.progress, title: name,
      emptyTitle: "Nothing on this list", emptyText: D.canEdit ? "Add something below." : "",
      onCheck: async (l, checked) => {
        l.checked = checked;
        draw(l.id);
        try { await api(`/lists/item/${l.id}/check/`, { method: "POST", body: { checked } }); }
        catch (err) { l.checked = !checked; draw(l.id); toast(err.message, true); }
      },
      onDelete: D.canEdit ? async (l) => {
        try { data = await api(`/lists/item/${l.id}/delete/`, { method: "POST" }); draw(); } catch (err) { toast(err.message, true); }
      } : null,
    });
    if (focusId) box.querySelector(`[data-id="${focusId}"] input`)?.focus();
  }

  const loc = document.querySelector("[data-location]");
  loc.append(h("option", { value: "" }, "Category (no shop)"), ...D.locations.map((l) => h("option", { value: l.id, selected: l.id === location }, l.name)));
  loc.addEventListener("change", async () => {
    location = loc.value ? Number(loc.value) : null;
    try {
      data = D.canEdit
        ? await api(`/lists/${D.id}/location/`, { method: "POST", body: { location } })
        : await api(`/lists/${D.id}/receipt/`, { query: location ? { location } : {} });
      draw();
    } catch (err) { toast(err.message, true); }
  });

  document.querySelector("[data-uncheck]")?.addEventListener("click", async () => {
    try { await api(`/lists/${D.id}/uncheck/`, { method: "POST" }); data.sections.forEach((s) => s.lines.forEach((l) => { l.checked = false; })); draw(); }
    catch (err) { toast(err.message, true); }
  });
  document.querySelector("[data-copy]")?.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(receiptText(data, name)); toast("Copied: paste it anywhere."); }
    catch { toast("Your browser wouldn’t let me copy.", true); }
  });
  document.querySelector("[data-print]")?.addEventListener("click", () => window.print());

  document.querySelector("[data-add]")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = e.target.querySelector("input");
    const text = input.value.trim();
    if (!text) return;
    try {
      data = await api(`/lists/${D.id}/items/`, { method: "POST", body: { name: text } });
      input.value = "";
      draw();
    } catch (err) { toast(err.message, true); }
  });
  draw();
}
