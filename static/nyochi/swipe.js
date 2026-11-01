// Swipes on touch screens (a family component: the same file in Shopping, Nyochi, Home and Admin, no imports).
//   pager(el, {go, canPrev, canNext}): el follows the finger sideways; let go past a quarter of its width (or flick)
//     and it slides out, go(-1 | 1) runs, the new content slides in. go() returns "away" when it leaves the page.
//   row(el, {right, left}): a list row slides to uncover what letting go will do; right / left =
//     {icon: Element, label, tone: "ok" | "danger" | "neutral", out: true to slide away (removals), run()}.
//     Returns the wrapper to put in the row's place.
// Only touch and pen drive them (a mouse keeps clicking), vertical scrolling stays the browser's, the screen edges
// stay the system's back gesture, and the click that ends a drag is swallowed.
const EDGE = 22;
const SKIP = "input, textarea, select, [contenteditable], .stepper, [data-noswipe]";
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

function track(el, { move, end }) {
  el.style.touchAction = "pan-y";
  let s = null;
  el.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse" || !e.isPrimary || e.swipeTaken || e.target.closest(SKIP)) return;
    e.swipeTaken = true;   // a row inside a pager: the innermost one takes the gesture
    if (e.clientX < EDGE || e.clientX > innerWidth - EDGE) return;
    s = { x: e.clientX, y: e.clientY, t: e.timeStamp, id: e.pointerId, dir: null, dx: 0, lastX: e.clientX, lastT: e.timeStamp, v: 0 };
  });
  el.addEventListener("pointermove", (e) => {
    if (!s || e.pointerId !== s.id) return;
    const dx = e.clientX - s.x, dy = e.clientY - s.y;
    if (!s.dir) {
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
      s.dir = Math.abs(dx) > Math.abs(dy) * 1.2 ? "x" : "y";
      if (s.dir === "x") try { el.setPointerCapture(e.pointerId); } catch { /* gone */ }
    }
    if (s.dir !== "x") return;
    const dt = e.timeStamp - s.lastT;
    if (dt > 0) s.v = (e.clientX - s.lastX) / dt;
    s.lastX = e.clientX; s.lastT = e.timeStamp; s.dx = dx;
    move(dx);
  });
  const finish = (e, cancelled) => {
    if (!s || e.pointerId !== s.id) return;
    const st = s;
    s = null;
    if (st.dir !== "x") return;
    const stop = (c) => { c.stopPropagation(); c.preventDefault(); };
    el.addEventListener("click", stop, { capture: true, once: true });
    setTimeout(() => el.removeEventListener("click", stop, { capture: true }), 350);
    end(cancelled ? 0 : st.dx, cancelled ? 0 : st.v);
  };
  el.addEventListener("pointerup", (e) => finish(e, false));
  el.addEventListener("pointercancel", (e) => finish(e, true));
}

export function pager(el, { go, canPrev = () => true, canNext = () => true }) {
  const width = () => el.getBoundingClientRect().width || innerWidth;
  const set = (x, fade, ms) => {
    el.style.transition = ms && !still() ? `transform ${ms}ms ease, opacity ${ms}ms ease` : "none";
    el.style.transform = x ? `translateX(${x}px)` : "";
    el.style.opacity = fade === 1 ? "" : String(fade);
  };
  track(el, {
    move(dx) {
      const blocked = dx > 0 ? !canPrev() : !canNext();
      const x = blocked ? dx / 4 : dx;
      set(x, 1 - Math.min(Math.abs(x) / width(), 1) * 0.4, 0);
    },
    async end(dx, v) {
      const dir = dx < 0 ? 1 : -1;
      const far = Math.abs(dx) > width() / 4 || (Math.abs(v) > 0.4 && Math.abs(dx) > 30);
      if (!dx || !far || !(dir > 0 ? canNext() : canPrev())) { set(0, 1, 200); return; }
      set(-dir * width(), 0, 170);
      await wait(still() ? 0 : 170);
      if ((await go(dir)) === "away") return;
      set(dir * width() * 0.35, 0, 0);
      el.getBoundingClientRect();   // apply before sliding in
      set(0, 1, 220);
    },
  });
  return el;
}

export function row(el, { right = null, left = null }) {
  const side = (a, cls) => {
    const s = document.createElement("span");
    s.className = `sw-act ${cls} ${a ? `tone-${a.tone || "neutral"}` : ""}`;
    if (a) s.append(a.icon || "", a.label || "");
    return s;
  };
  const r = side(right, "r"), l = side(left, "l");
  const bg = document.createElement("div");
  bg.className = "sw-bg";
  bg.setAttribute("aria-hidden", "true");
  bg.append(r, l);
  const wrap = document.createElement("div");
  wrap.className = "sw-wrap";
  wrap.setAttribute("role", "presentation");
  el.replaceWith?.(wrap);
  wrap.append(bg, el);
  el.classList.add("sw-row");
  const reach = () => Math.min(110, el.getBoundingClientRect().width * 0.3);
  const set = (x, ms) => {
    el.style.transition = ms && !still() ? `transform ${ms}ms ease` : "none";
    el.style.transform = x ? `translateX(${x}px)` : "";
  };
  track(el, {
    move(dx) {
      const a = dx > 0 ? right : left;
      const x = a ? dx : dx / 5;
      wrap.classList.add("sw-moving");
      wrap.dataset.side = dx > 0 ? "r" : "l";
      wrap.classList.toggle("sw-armed", !!a && Math.abs(dx) >= reach());
      set(x, 0);
    },
    async end(dx) {
      const a = dx > 0 ? right : left;
      const go = a && Math.abs(dx) >= reach();
      wrap.classList.remove("sw-armed");
      if (go && a.out) {
        set(Math.sign(dx) * el.getBoundingClientRect().width, 180);
        await wait(still() ? 0 : 180);
      } else {
        set(0, 200);
        await wait(still() ? 0 : 200);
      }
      wrap.classList.remove("sw-moving");
      if (go) {
        try { await a.run(); } catch { /* the action reports its own errors */ }
        if (a.out) set(0, 0);   // the row is redrawn by the action; if not (error), it comes back
      }
    },
  });
  return wrap;
}
