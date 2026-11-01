// Swipes on touch screens (a family component: the same file in Shopping, Nyochi, Home and Admin, no imports).
//   snap(el, {onChange, onSettle, fit}): el is a row of full-width panels the browser scrolls sideways (CSS scroll snap), so
//     the next panel is already there under the finger. onChange(i) fires as soon as panel i is the one mostly shown,
//     onSettle(i) once the scroll has stopped (and the finger is up). Returns {index(), go(i, smooth)}.
//   slider(el, {render, has, onMove, span}): an endless snap: render(offset) for the `span` items before and after the
//     current one (has(offset) false: none that way), so a fast series of flicks never waits. onMove(d) fires live as
//     the item in view changes (d can be more than 1); once the scroll is still the panels are re-centred on it.
//     refresh() redraws them (data arrived, something changed). Returns {refresh, current()}.
//   row(el, {right, left}): a list row slides to uncover what letting go will do; right / left =
//     {icon: Element, label, tone: "ok" | "danger" | "neutral", out: true to slide away (removals), run()}.
//     Returns the wrapper to put in the row's place.
// Rows: touch and pen only (a mouse keeps clicking), vertical scrolling stays the browser's, the screen edges stay the
// system's back gesture, the click that ends a drag is swallowed. Snaps are plain scrolling: they work everywhere.
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

export function snap(el, { onChange, onSettle, fit = true } = {}) {
  el.classList.add("sw-snap");
  const at = () => Math.round(el.scrollLeft / (el.clientWidth || 1));
  let cur = at(), dirty = false, touching = false, timer = 0;
  // as tall as the panel in view (fit: false when the panels scroll inside a fixed height)
  const size = () => { if (fit && el.children[cur]) el.style.height = `${el.children[cur].offsetHeight}px`; };
  if (fit) {
    const ro = new ResizeObserver(size);
    const watch = () => { ro.disconnect(); [...el.children].forEach((c) => ro.observe(c)); size(); };
    new MutationObserver(watch).observe(el, { childList: true });
    watch();
  }
  const settle = () => {
    clearTimeout(timer);
    if (!dirty || touching) return;
    dirty = false;
    onSettle?.(at());
  };
  el.addEventListener("scroll", () => {
    dirty = true;
    const i = at();
    if (i !== cur) { cur = i; size(); onChange?.(i); }
    clearTimeout(timer);
    timer = setTimeout(settle, 160);   // browsers without "scrollend"
  }, { passive: true });
  el.addEventListener("scrollend", settle);
  el.addEventListener("touchstart", () => { touching = true; }, { passive: true });
  el.addEventListener("touchend", () => { touching = false; clearTimeout(timer); timer = setTimeout(settle, 160); }, { passive: true });
  return {
    index: at,
    busy: () => dirty || touching,
    go(i, smooth = true) {
      cur = i;
      size();
      el.scrollTo({ left: i * el.clientWidth, behavior: smooth && !still() ? "smooth" : "instant" });
    },
  };
}

export function slider(el, { render, has = () => true, onMove, fit = true, span = 6 }) {
  let mid = 0, at = 0, pending = false;
  const build = () => {
    pending = false;
    const offsets = [0];
    for (let o = -1; o >= -span && has(o); o--) offsets.unshift(o);
    for (let o = 1; o <= span && has(o); o++) offsets.push(o);
    mid = at = offsets.indexOf(0);
    el.replaceChildren(...offsets.map((o) => {
      const panel = document.createElement("div");
      panel.className = "sw-panel";
      panel.append(render(o));
      return panel;
    }));
    s.go(mid, false);
  };
  el.classList.add("sw-slide");
  const s = snap(el, {
    fit,
    // live: the item in view changed by d (a fast flick can pass several); the page follows at once
    onChange(i) { const d = i - at; at = i; if (d) onMove(d); },
    // once still: re-centre the window of panels on the new item (never under a finger or a running scroll)
    onSettle() { if (at !== mid || pending) build(); },
  });
  build();
  return { refresh: () => { if (s.busy()) pending = true; else build(); }, current: () => el.children[at] };
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
