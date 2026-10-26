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
  // The rows of the list: matching ingredients, then "Create" when what was typed isn't an exact match.
  // The first row is highlighted as you type, so Enter takes the best match; Create must be chosen on purpose.
  let options = [];
  function build() {
    const q = input.value.trim().toLowerCase();
    shown = registry.filter((i) => !q || i.name.toLowerCase().includes(q)).slice(0, 40);
    const exact = registry.some((i) => i.name.toLowerCase() === q);
    options = shown.map((item) => ({ kind: "item", item }));
    if (allowCreate && q && !exact) options.push({ kind: "create", name: input.value.trim() });
  }
  function draw() {
    const rows = options.map((o, idx) => o.kind === "item"
      ? h("div.combo-opt", { role: "option", class: idx === active ? "active" : "", onmousedown: (e) => { e.preventDefault(); pick(o.item); } }, o.item.name)
      : h("div.combo-opt.create", { role: "option", class: idx === active ? "active" : "", onmousedown: (e) => { e.preventDefault(); create(o.name); } }, icon("add"), `Create “${o.name}”`));
    list.replaceChildren(...(rows.length ? rows : [h("div.combo-opt", {}, "No ingredient yet. Type a name to create one.")]));
    list.classList.remove("hidden");
    input.setAttribute("aria-expanded", "true");
    list.children[active]?.scrollIntoView({ block: "nearest" });
  }
  function render(highlightFirst) {
    build();
    active = highlightFirst && options.length ? 0 : Math.min(active, options.length - 1);
    draw();
  }
  const choose = (o) => { if (o) (o.kind === "item" ? pick(o.item) : create(o.name)); };
  input.addEventListener("focus", () => { input.select(); active = -1; render(false); });
  // Clicking a field that still shows the chosen name selects it, so typing replaces it instead of appending to it;
  // clicking an already-focused field (focus doesn't fire again) also reopens the list.
  input.addEventListener("click", () => {
    if (input.value && input.value === selectedName()) input.select();
    if (list.classList.contains("hidden")) { active = -1; render(false); }
  });
  input.addEventListener("input", () => render(true));
  input.addEventListener("blur", () => setTimeout(() => { close(); input.value = selectedName(); }, 120));
  input.addEventListener("keydown", (e) => {
    const open = !list.classList.contains("hidden");
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) { render(false); return; }
      active = Math.max(0, Math.min(options.length - 1, active + (e.key === "ArrowDown" ? 1 : -1)));
      draw();
    } else if (e.key === "Enter") {
      if (open) { e.preventDefault(); choose(options[active]); }
    } else if (e.key === "Escape") { close(); input.value = selectedName(); }
  });
  return input;
}
