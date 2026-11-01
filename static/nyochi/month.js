// The month on phones: a slider of months. The months before and after are fetched in the background (just their
// calendar, ?part=1) and drawn beside the one shown, so a swipe shows them at once; the header follows.
import { slider } from "./swipe.js";

const box = document.querySelector("[data-month-pages]");
if (box && matchMedia("(max-width: 760px)").matches) {
  const html = new Map([[box.firstElementChild.dataset.m, box.innerHTML]]);   // "YYYY-MM" -> its calendar
  const loading = new Set();
  let cur = box.firstElementChild.dataset.m;
  const shift = (m, d) => {
    const [y, mo] = m.split("-").map(Number);
    const t = new Date(y, mo - 1 + d, 1);
    return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}`;
  };
  const NAME = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" });
  const parse = (m) => {
    const t = document.createElement("template");
    t.innerHTML = html.get(m) || `<div class="mo-body loading" data-m="${m}"></div>`;
    return t.content.firstElementChild;
  };

  function load(m) {
    if (html.has(m) || loading.has(m)) return;
    loading.add(m);
    fetch(`${location.pathname}?m=${m}&part=1`, { credentials: "same-origin" })
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(r.status))))
      .then((text) => { html.set(m, text.trim()); months.refresh(); if (m === cur) head(); })
      .catch(() => { /* tried again on the next swipe */ })
      .finally(() => loading.delete(m));
  }
  function head() {
    const body = parse(cur);
    const [y, mo] = cur.split("-").map(Number);
    const title = body.dataset.title || NAME.format(new Date(y, mo - 1, 1));
    document.querySelector("[data-mo-title]").textContent = title;
    document.title = `${title} · Meals · Nyochi`;
    document.querySelector("[data-mo-planned]").textContent = body.dataset.planned || "";
    document.querySelector("[data-prev]").href = `?m=${shift(cur, -1)}`;
    document.querySelector("[data-next]").href = `?m=${shift(cur, 1)}`;
  }
  function moved() {
    head();
    [-2, -1, 1, 2].forEach((d) => load(shift(cur, d)));
  }

  const months = slider(box, { span: 3, fill: true, render: (o) => parse(shift(cur, o)), onMove: (d) => { cur = shift(cur, d); moved(); } });
  for (const [sel, d] of [["[data-prev]", -1], ["[data-next]", 1]]) {
    document.querySelector(sel).addEventListener("click", (e) => { e.preventDefault(); cur = shift(cur, d); moved(); months.refresh(); });
  }
  [-2, -1, 1, 2].forEach((d) => load(shift(cur, d)));
}
