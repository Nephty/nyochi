// An ingredient picker over a <select>: type to filter, arrows + Enter to choose, "Create “x”" when nothing matches.
// The <select> stays in the form (it is what gets submitted); this only drives it.
import { api, h, icon, toast } from "./ui.js";

export const registry = []; // [{id, name, category?}], shared by every combo on the page, grows when one is created

export function setChoices(list) {
  registry.length = 0;
  registry.push(...list);
}

export function enhanceCombo(box, { allowCreate = true } = {}) {
  const select = box.querySelector("select");
  if (!select || box.dataset.enhanced) return;
  box.dataset.enhanced = "1";
  select.classList.add("hidden");
  const input = h("input.select", { type: "text", placeholder: select.dataset.placeholder || "Choose or create an ingredient…", autocomplete: "off", "aria-label": "Ingredient", role: "combobox", "aria-expanded": "false" });
  const list = h("div.combo-list.hidden", { role: "listbox" });
  box.append(input, list);
  let active = -1;
  let shown = [];

  const selectedName = () => select.options[select.selectedIndex]?.value ? select.options[select.selectedIndex].text : "";
  input.value = selectedName();
  if (select.closest(".irow")?.classList.contains("invalid") && !select.value) input.classList.add("bad");

  function close() { list.classList.add("hidden"); input.setAttribute("aria-expanded", "false"); active = -1; }
  function pick(item) {
    let option = [...select.options].find((o) => o.value === String(item.id));
    if (!option) { option = new Option(item.name, item.id); select.append(option); }
    select.value = String(item.id);
    input.value = item.name;
    input.classList.remove("bad");
    select.dispatchEvent(new Event("change", { bubbles: true }));
    close();
  }
  async function create(name) {
    try {
      const made = await api("/ingredients/quick/", { method: "POST", body: { name } });
      if (!registry.some((i) => i.id === made.id)) registry.push({ id: made.id, name: made.name });
      pick(made);
      toast(made.existing ? `“${made.name}” already existed: using it.` : `Created the ingredient “${made.name}”. Add its seasons and products later.`);
    } catch (err) { toast(err.message, true); }
  }
  function render() {
    const q = input.value.trim().toLowerCase();
    shown = registry.filter((i) => !q || i.name.toLowerCase().includes(q)).slice(0, 40);
    const exact = registry.some((i) => i.name.toLowerCase() === q);
    list.replaceChildren(
      ...shown.map((item, idx) => h("div.combo-opt", { role: "option", class: idx === active ? "active" : "", onmousedown: (e) => { e.preventDefault(); pick(item); } }, item.name)),
      allowCreate && q && !exact ? h("div.combo-opt.create", { role: "option", onmousedown: (e) => { e.preventDefault(); create(input.value.trim()); } }, icon("add"), `Create “${input.value.trim()}”`) : null,
    );
    if (!shown.length && !(allowCreate && q)) list.replaceChildren(h("div.combo-opt", {}, "No ingredient yet. Type a name to create one."));
    list.classList.remove("hidden");
    input.setAttribute("aria-expanded", "true");
  }
  input.addEventListener("focus", () => { input.select(); render(); });
  input.addEventListener("input", () => { active = -1; render(); });
  input.addEventListener("blur", () => setTimeout(() => { close(); input.value = selectedName(); }, 120));
  input.addEventListener("keydown", (e) => {
    const opts = [...list.children];
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (list.classList.contains("hidden")) render();
      active = Math.max(0, Math.min(shown.length - 1, active + (e.key === "ArrowDown" ? 1 : -1)));
      opts.forEach((o, i) => o.classList.toggle("active", i === active));
      opts[active]?.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      if (!list.classList.contains("hidden")) {
        e.preventDefault();
        if (active >= 0 && shown[active]) pick(shown[active]);
        else if (shown.length === 1) pick(shown[0]);
        else if (allowCreate && input.value.trim() && !registry.some((i) => i.name.toLowerCase() === input.value.trim().toLowerCase())) create(input.value.trim());
        else { const exact = registry.find((i) => i.name.toLowerCase() === input.value.trim().toLowerCase()); if (exact) pick(exact); }
      }
    } else if (e.key === "Escape") { close(); input.value = selectedName(); }
  });
  return input;
}
