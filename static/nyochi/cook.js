// The cooking guide (templates/recipes/cook.html): a "get ready" page, then the steps one by one, then "done".
// Position: -1 = get ready, 0..n-1 = the steps, n = done. It is remembered per recipe in this browser.
// The progress bar has one segment per step and a flag over each step that uses an appliance (oven, stove, fridge...).
import { h, icon, num, readJson, toast } from "./ui.js";

const R = readJson("cook");
const root = document.querySelector("[data-cook]");

if (R && root) {
  const steps = R.steps;
  const n = steps.length;
  const KEY = `nyochi-cook-${R.id}`;
  const stage = root.querySelector("[data-stage]");
  const progress = root.querySelector("[data-progress]");
  const count = root.querySelector("[data-count]");
  const prevBtn = root.querySelector("[data-prev]");
  const nextBtn = root.querySelector("[data-next]");
  const timersBox = root.querySelector("[data-timers]");

  const read = (fallback) => { try { return JSON.parse(localStorage.getItem(KEY)) ?? fallback; } catch { return fallback; } };
  const saved = read({});
  let pos = Number.isInteger(saved.pos) && saved.pos >= -1 && saved.pos <= n ? saved.pos : -1;
  const resumed = pos > -1 && pos < n;
  const ticked = new Set(saved.ticked || []); // ingredients ticked on the get-ready page
  const store = () => { try { localStorage.setItem(KEY, JSON.stringify({ pos, ticked: [...ticked] })); } catch { /* private mode */ } };

  const applianceText = (a) => (a ? `${a.label}${a.setting ? ` · ${a.setting}` : ""}` : "");
  const amount = (i) => (i.amount != null ? `${num(i.amount)} ${i.unit}`.trim() : "");

  // ------------------------------------------------------------------ timers (keep running while you move on)
  const timers = new Map(); // step index -> {total, left, running, at}
  let audio = null;
  function beep() {
    try {
      audio ||= new AudioContext();
      [0, 0.35, 0.7].forEach((t) => {
        const o = audio.createOscillator(), g = audio.createGain();
        o.frequency.value = 880; o.connect(g); g.connect(audio.destination);
        g.gain.setValueAtTime(0.0001, audio.currentTime + t);
        g.gain.exponentialRampToValueAtTime(0.3, audio.currentTime + t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + t + 0.28);
        o.start(audio.currentTime + t); o.stop(audio.currentTime + t + 0.3);
      });
    } catch { /* no audio */ }
    navigator.vibrate?.([300, 150, 300]);
  }
  const left = (t) => (t.running ? Math.max(0, t.left - (Date.now() - t.at) / 1000) : t.left);
  const clock = (s) => { s = Math.ceil(s); const m = Math.floor(s / 60); return `${m}:${String(s % 60).padStart(2, "0")}`; };
  function startTimer(i) {
    const t = timers.get(i) || { total: steps[i].minutes * 60, left: steps[i].minutes * 60, running: false, at: 0 };
    if (t.left <= 0) t.left = t.total;
    t.running = true; t.at = Date.now();
    timers.set(i, t);
    audio ||= (() => { try { return new AudioContext(); } catch { return null; } })(); // unlocked by this click
    draw();
  }
  function pauseTimer(i) {
    const t = timers.get(i);
    if (t) { t.left = left(t); t.running = false; }
    draw();
  }
  function resetTimer(i) { timers.delete(i); draw(); }
  setInterval(() => {
    for (const [i, t] of timers) {
      if (t.running && left(t) <= 0) {
        t.left = 0; t.running = false; t.done = true;
        beep();
        toast(`Time’s up: step ${i + 1}`);
      }
    }
    if (timers.size) { drawTimers(); drawTimerCard(); }
  }, 250);

  function drawTimers() {
    timersBox.replaceChildren(...[...timers].map(([i, t]) => h(`button.tpill${t.done ? ".done" : t.running ? ".run" : ""}`, {
      type: "button", title: `Step ${i + 1}`, onclick: () => go(i),
    }, icon("timer"), h("span", {}, `${i + 1}`), h("b", {}, t.done ? "done" : clock(left(t))))));
  }
  function drawTimerCard() {
    const box = stage.querySelector("[data-timer]");
    if (!box) return;
    const t = timers.get(pos);
    box.querySelector("[data-clock]").textContent = clock(t ? left(t) : steps[pos].minutes * 60);
    const ring = box.querySelector("[data-ring]");
    if (ring) ring.style.setProperty("--p", t ? 1 - left(t) / t.total : 0);
  }

  // ------------------------------------------------------------------ progress bar with flags
  function drawProgress() {
    const pct = pos < 0 ? 0 : pos >= n ? 100 : ((pos + 0.5) / n) * 100;
    const setupEnd = steps.filter((s) => s.phase === "setup").length;
    progress.replaceChildren(
      h("div.pbar", { role: "progressbar", "aria-valuemin": 0, "aria-valuemax": n, "aria-valuenow": Math.max(0, Math.min(pos + 1, n)) },
        h("div.fill", { style: { width: `${pct}%` } }),
        steps.map((s, i) => h(`button.seg${i < pos ? ".past" : i === pos ? ".now" : ""}`, {
          type: "button", style: { left: `${(i / n) * 100}%`, width: `${100 / n}%` }, title: `Step ${i + 1}`, "aria-label": `Go to step ${i + 1}`, onclick: () => go(i),
        })),
        setupEnd > 0 && setupEnd < n ? h("span.phase-cut", { style: { left: `${(setupEnd / n) * 100}%` } }) : null),
      h("div.flags", {}, steps.map((s, i) => s.appliance ? h(`button.flag.ware-${s.appliance.key}${i < pos ? ".past" : i === pos ? ".now" : ""}`, {
        type: "button", style: { left: `${((i + 0.5) / n) * 100}%` }, title: `Step ${i + 1}: ${applianceText(s.appliance)}`, onclick: () => go(i),
      }, icon(s.appliance.icon), h("span", {}, s.appliance.label)) : null)),
      h("div.plabels", {},
        setupEnd > 0 ? h("span", { style: { left: "0", width: `${(setupEnd / n) * 100}%` } }, "Ingredient set-up") : null,
        setupEnd < n ? h("span", { style: { left: `${(setupEnd / n) * 100}%`, width: `${((n - setupEnd) / n) * 100}%` } }, "Preparation") : null));
  }

  // ------------------------------------------------------------------ the pages
  function readyPage() {
    const ware = R.kitchenware;
    return h("div.cook-ready", {},
      h("div.cook-card.ready", {},
        h("div.eyebrow", {}, "Before you start"),
        h("h2", {}, "Get everything ready"),
        h("div.ready-grid", {},
          h("section", {}, h("h3", {}, "Ingredients"),
            R.ingredients.length ? h("ul.ready-ings", {}, R.ingredients.map((ing, k) => {
              const id = `ing-${k}`;
              return h(`li${ticked.has(k) ? ".ok" : ""}`, {},
                h("input", { type: "checkbox", id, checked: ticked.has(k), onchange: (e) => { e.target.checked ? ticked.add(k) : ticked.delete(k); e.target.closest("li").classList.toggle("ok", e.target.checked); store(); } }),
                h("label", { for: id }, h("span.nm", {}, ing.main ? icon("star_fill", "star-main") : null, ing.name), h("span.qty", {}, amount(ing))));
            })) : h("p.muted", {}, "No ingredients listed.")),
          h("section", {},
            ware.length ? [h("h3", {}, "Kitchenware"), h("ul.ware-list", {}, ware.map((k) => h(`li.ware.ware-${k.key}`, {},
              h("span.ware-ic", {}, icon(k.icon)), h("span.nm", {}, k.label), k.setting ? h("span.set", {}, k.setting) : null)))] : null,
            R.tools.length ? [h("h3", {}, "Tools"), h("ul.tool-list", {}, R.tools.map((t) => h("li", {}, t)))] : null,
            !ware.length && !R.tools.length ? h("p.muted", {}, "No tools listed.") : null)),
        n ? null : h("p.muted", {}, "This recipe has no steps yet.")));
  }

  function summary(i, label) {
    if (i < 0 || i >= n) {
      const text = i < 0 ? "Get everything ready" : "Done";
      return h(`button.peek.${label === "Previous" ? "prev" : "next"}`, { type: "button", onclick: () => go(i) },
        h("span.k", {}, label), h("span.t", {}, text));
    }
    const s = steps[i];
    return h(`button.peek.${label === "Previous" ? "prev" : "next"}`, { type: "button", onclick: () => go(i) },
      h("span.k", {}, `${label} · step ${i + 1}`,
        s.appliance ? h(`span.mini-flag.ware-${s.appliance.key}`, {}, icon(s.appliance.icon), s.appliance.label) : null),
      h("span.t", {}, s.text));
  }

  function stepPage() {
    const s = steps[pos];
    const t = timers.get(pos);
    return h("div.cook-step", {},
      h(`div.cook-card.step.phase-${s.phase}`, {},
        h("div.step-head", {},
          h("span.eyebrow", {}, s.phase_label),
          h("span.bign", {}, String(pos + 1))),
        s.appliance ? h(`div.ware-banner.ware-${s.appliance.key}`, {}, h("span.ware-ic", {}, icon(s.appliance.icon)),
          h("div", {}, h("b", {}, s.appliance.label), s.appliance.setting ? h("span", {}, s.appliance.setting) : null)) : null,
        h("p.step-text", {}, s.text),
        s.minutes ? h("div.timer-card", { dataset: { timer: "" } },
          h("div.ring", { dataset: { ring: "" } }, h("span", { dataset: { clock: "" } }, clock(t ? left(t) : s.minutes * 60))),
          h("div.timer-acts", {},
            t?.running ? h("button.btn", { type: "button", onclick: () => pauseTimer(pos) }, icon("pause"), "Pause")
              : h("button.btn.btn-tag", { type: "button", onclick: () => startTimer(pos) }, icon("play_arrow"), t && !t.done ? "Resume" : `Start ${s.minutes} min`),
            t ? h("button.btn.btn-ghost", { type: "button", onclick: () => resetTimer(pos) }, icon("restart_alt"), "Reset") : null)) : null),
      h("div.peeks", {}, summary(pos - 1, "Previous"), summary(pos + 1, "Next")));
  }

  function donePage() {
    return h("div.cook-done", {}, h("div.cook-card.done", {},
      h("span.done-ic", {}, icon("done_all")),
      h("h2", {}, "All done"),
      h("p.muted", {}, `${R.name}: enjoy it.`),
      h("div.row", { style: { justifyContent: "center", gap: ".5rem", marginTop: "1rem" } },
        h("a.btn", { href: R.url }, icon("menu_book"), "Back to the recipe"),
        h("button.btn.btn-ghost", { type: "button", onclick: () => { ticked.clear(); go(-1); } }, icon("restart_alt"), "Start over"))));
  }

  function draw() {
    stage.replaceChildren(pos < 0 ? readyPage() : pos >= n ? donePage() : stepPage());
    drawProgress();
    drawTimers();
    drawTimerCard();
    count.textContent = pos < 0 ? `${n} step${n === 1 ? "" : "s"}` : pos >= n ? "Done" : `Step ${pos + 1} of ${n}`;
    prevBtn.disabled = pos < 0;
    nextBtn.disabled = pos >= n;
    nextBtn.querySelector("span").textContent = pos < 0 ? "Start" : pos === n - 1 ? "Finish" : "Next";
    stage.scrollTop = 0;
  }

  function go(i) {
    pos = Math.max(-1, Math.min(n, i));
    store();
    draw();
  }

  prevBtn.addEventListener("click", () => go(pos - 1));
  nextBtn.addEventListener("click", () => go(pos + 1));
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, select")) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); go(pos + 1); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); go(pos - 1); }
  });
  // swipe on phones
  let x0 = null;
  stage.addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  stage.addEventListener("touchend", (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    x0 = null;
    if (Math.abs(dx) > 70) go(pos + (dx < 0 ? 1 : -1));
  });

  // keep the screen on while cooking
  let lock = null;
  const wake = async () => { try { lock = await navigator.wakeLock?.request("screen"); } catch { /* not allowed */ } };
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && (!lock || lock.released)) wake(); });
  wake();

  draw();
  if (resumed) toast(`Picked up at step ${pos + 1}`);
}
