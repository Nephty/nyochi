// The recipe form's steps, kitchenware and tools editors. They keep their state in JS and write it as JSON into the
// form's hidden steps_json / kitchenware_json / tools_json fields (cleaned again by recipes/kitchen.py on save).
import { h, icon, readJson } from "./ui.js";

const K = readJson("kitchen");
const form = document.querySelector("[data-recipe-form]");
const phasesBox = form?.querySelector("[data-phases]");

if (form && K && phasesBox) {
  const field = (name) => form.querySelector(`[name="${name}_json"]`);
  const load = (name) => { try { return JSON.parse(field(name).value || "[]"); } catch { return []; } };
  const WARE = Object.fromEntries(K.kitchenware.map((w) => [w.key, w]));
  const PHASES = K.phases.map((p) => p.key);

  // steps: one flat list, set-up first then preparation; moving a step past its phase's edge changes its phase
  let steps = load("steps").map((s) => ({ ...s }));
  let ware = load("kitchenware");
  let tools = load("tools");
  let focusAfter = null; // [index, selector] to focus after a redraw

  const order = () => steps.sort((a, b) => PHASES.indexOf(a.phase) - PHASES.indexOf(b.phase));
  const save = () => {
    field("steps").value = JSON.stringify(steps.filter((s) => s.text.trim()));
    field("kitchenware").value = JSON.stringify(ware);
    field("tools").value = JSON.stringify(tools);
  };

  function move(i, dir) {
    const s = steps[i];
    const j = i + dir;
    const p = PHASES.indexOf(s.phase);
    const edge = j < 0 || j >= steps.length || steps[j].phase !== s.phase;
    if (edge) {
      const np = p + dir;
      if (np < 0 || np >= PHASES.length) return;
      s.phase = PHASES[np]; // stays at the same spot in the flat list: last of set-up / first of preparation
    } else {
      [steps[i], steps[j]] = [steps[j], steps[i]];
    }
    order();
    focusAfter = [steps.indexOf(s), "textarea"];
    drawSteps();
  }

  function addStep(phase, after = null) {
    const step = { phase, text: "", appliance: "", minutes: null };
    if (after === null) {
      const last = steps.map((s) => s.phase).lastIndexOf(phase);
      const firstLater = steps.findIndex((s) => PHASES.indexOf(s.phase) > PHASES.indexOf(phase));
      steps.splice(last >= 0 ? last + 1 : firstLater >= 0 ? firstLater : steps.length, 0, step);
    } else {
      steps.splice(after + 1, 0, step);
    }
    focusAfter = [steps.indexOf(step), "textarea"];
    drawSteps();
  }

  const grow = (ta) => { ta.style.height = "auto"; ta.style.height = `${ta.scrollHeight + 2}px`; };

  function stepCard(s, i, n) {
    const first = i === 0;
    const last = i === steps.length - 1;
    const ta = h("textarea.textarea", {
      rows: 2, maxLength: 2000, placeholder: s.phase === "setup" ? "Peel and dice the onions…" : "Sweat the onions in the butter…",
      "aria-label": `Step ${n}`,
      oninput: (e) => { s.text = e.target.value; grow(e.target); save(); },
      onkeydown: (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); addStep(s.phase, i); } },
    }, s.text);
    const appliance = h("select.select.sm", {
      "aria-label": "Uses", onchange: (e) => { s.appliance = e.target.value; save(); drawStepIcons(); },
    }, h("option", { value: "" }, "No appliance"), K.kitchenware.map((w) => h("option", { value: w.key, selected: s.appliance === w.key }, w.label)));
    const minutes = h("input.input.sm.min", {
      type: "number", min: 1, max: 1440, inputmode: "numeric", placeholder: "min", value: s.minutes ?? "", "aria-label": "Timer in minutes",
      oninput: (e) => { s.minutes = e.target.value ? Number(e.target.value) : null; save(); },
    });
    const card = h("li.step-e", { dataset: { i } },
      h("span.n", {}, String(n)),
      h("div.body", {}, ta,
        h("div.step-tools", {},
          h("span.uses", {}, s.appliance ? icon(WARE[s.appliance]?.icon || "kitchen") : icon("kitchen")), appliance,
          h("span.uses", {}, icon("timer")), minutes,
          h("span.grow"),
          h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", title: "Move up", "aria-label": "Move up", disabled: first && s.phase === PHASES[0], onclick: () => move(i, -1) }, icon("arrow_upward")),
          h("button.btn.btn-ghost.btn-sm.btn-icon", { type: "button", title: "Move down", "aria-label": "Move down", disabled: last && s.phase === PHASES.at(-1), onclick: () => move(i, 1) }, icon("arrow_downward")),
          h("button.btn.btn-ghost.btn-sm.btn-icon.del", { type: "button", title: "Remove step", "aria-label": "Remove step", onclick: () => { steps.splice(i, 1); save(); drawSteps(); } }, icon("close")))));
    requestAnimationFrame(() => grow(ta));
    return card;
  }

  function drawStepIcons() {
    phasesBox.querySelectorAll(".step-e").forEach((card) => {
      const s = steps[Number(card.dataset.i)];
      card.querySelector(".uses").replaceChildren(icon(WARE[s.appliance]?.icon || "kitchen"));
      card.classList.toggle("has-ware", !!s.appliance);
    });
  }

  function drawSteps() {
    let n = 0;
    phasesBox.replaceChildren(...K.phases.map((p) => {
      const list = h("ol.steps-e", {});
      steps.forEach((s, i) => { if (s.phase === p.key) list.append(stepCard(s, i, ++n)); });
      return h(`div.phase-e.phase-${p.key}`, {},
        h("h3.phase-h", {}, p.label),
        list.children.length ? list : h("p.muted.sm.empty", {}, "No steps."),
        h("button.btn.btn-sm", { type: "button", onclick: () => addStep(p.key) }, icon("add"), "Add a step"));
    }));
    drawStepIcons();
    if (focusAfter) {
      const [i, sel] = focusAfter;
      focusAfter = null;
      phasesBox.querySelector(`.step-e[data-i="${i}"] ${sel}`)?.focus();
    }
    save();
  }

  // kitchenware: a tile per appliance; switched on, it asks for its setting (oven temperature, heat...)
  const wareBox = form.querySelector("[data-ware]");
  function drawWare() {
    wareBox.replaceChildren(...K.kitchenware.map((w) => {
      const entry = ware.find((x) => x.key === w.key);
      const usedBySteps = steps.some((s) => s.appliance === w.key);
      const toggle = h("button.ware-t", {
        type: "button", "aria-pressed": String(!!entry),
        title: usedBySteps && !entry ? "A step uses it: it is listed anyway" : null,
        onclick: () => {
          if (entry) ware = ware.filter((x) => x.key !== w.key);
          else ware.push({ key: w.key, setting: "" });
          save(); drawWare();
          if (!entry) wareBox.querySelector(`[data-set="${w.key}"]`)?.focus();
        },
      }, icon(w.icon), h("span", {}, w.label), usedBySteps && !entry ? h("small", {}, "in a step") : null);
      const setting = entry ? h("input.input.sm", {
        type: "text", maxLength: 80, value: entry.setting, placeholder: w.hint || "Setting", "aria-label": `${w.label} setting`,
        dataset: { set: w.key }, oninput: (e) => { entry.setting = e.target.value; save(); },
      }) : null;
      return h(`div.ware-c${entry ? ".on" : ""}`, {}, toggle, setting);
    }));
  }
  phasesBox.addEventListener("change", drawWare);

  // tools: chips, plus a field with suggestions (Enter or comma adds)
  const toolsBox = form.querySelector("[data-tools]");
  function drawTools() {
    const add = (value) => {
      for (const raw of value.split(",")) {
        const name = raw.trim().replace(/\s+/g, " ").slice(0, 80);
        if (name && !tools.some((t) => t.toLowerCase() === name.toLowerCase())) tools.push(name);
      }
      save(); drawTools();
      toolsBox.querySelector("input")?.focus();
    };
    const input = h("input.input", {
      type: "text", list: "tool-suggest", placeholder: "Add a tool: knife, whisk, grater…", maxLength: 80, "aria-label": "Add a tool",
      onkeydown: (e) => {
        if ((e.key === "Enter" || e.key === ",") && e.target.value.trim()) { e.preventDefault(); add(e.target.value); }
        else if (e.key === "Enter") e.preventDefault();
        else if (e.key === "Backspace" && !e.target.value && tools.length) { tools.pop(); save(); drawTools(); toolsBox.querySelector("input")?.focus(); }
      },
      onchange: (e) => { if (e.target.value.trim()) add(e.target.value); },
    });
    toolsBox.replaceChildren(
      h("div.tool-chips", {}, tools.map((t, i) => h("span.tool-chip", {}, t,
        h("button", { type: "button", "aria-label": `Remove ${t}`, onclick: () => { tools.splice(i, 1); save(); drawTools(); } }, icon("close"))))),
      input,
      h("datalist", { id: "tool-suggest" }, K.tools.filter((t) => !tools.includes(t)).map((t) => h("option", { value: t }))));
  }

  order();
  drawSteps();
  drawWare();
  drawTools();
  form.addEventListener("submit", save);
}
