// Small shared helpers: icons, element building, API calls, formatting, toasts, dialogs, saved preferences.
const ICONS = JSON.parse(document.getElementById("nyo-icons")?.textContent || "{}");

export function icon(name, cls = "") {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", `ic ${cls}`.trim());
  svg.setAttribute("viewBox", "0 -960 960 960");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", ICONS[name] || "");
  svg.append(path);
  return svg;
}

// h("div.a.b", {attrs / on*: handlers / dataset}, ...children). Children: strings, nodes, arrays, null.
export function h(tag, props = {}, ...children) {
  const [name, ...classes] = tag.split(".");
  const el = document.createElement(name || "div");
  if (classes.length) el.className = classes.join(" ");
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = `${el.className} ${value}`.trim();
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (key === "style" && typeof value === "object") Object.assign(el.style, value);
    else if (key in el && typeof value !== "string") el[key] = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || "";

// JSON in, JSON out. Throws Error(message) with the server's {"error": ...}; a ended session goes to the hub login.
export async function api(path, { method = "GET", body, query } = {}) {
  let url = path;
  if (query) url += `?${new URLSearchParams(query)}`;
  const options = { method, headers: { Accept: "application/json" }, credentials: "same-origin" };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
    options.headers["Content-Type"] = "application/json";
  }
  if (method !== "GET") options.headers["X-CSRFToken"] = CSRF;
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error("Network error: is the server reachable?");
  }
  let data = null;
  try { data = await response.json(); } catch { /* not JSON */ }
  if (response.status === 403 && data?.login) {
    location.href = data.login;
    throw new Error("Your session has ended");
  }
  if (!response.ok) throw new Error(data?.error || `Request failed (${response.status})`);
  return data;
}

const EURO = new Intl.NumberFormat("fr-BE", { style: "currency", currency: "EUR" });
export function money(value) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "–";
  return EURO.format(Number(value));
}

export function num(value) {
  const n = Number(value);
  return Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100);
}

const DAY = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
export function untilText(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const n = Math.round((date - today) / 86400000);
  if (n === 0) return "ends today";
  if (n === 1) return "ends tomorrow";
  return `until ${DAY.format(date)}`;
}

export const MONTH_LETTERS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

// Shopping's "is this a real deal?" chip
export function realChip(promo) {
  if (!promo?.verdict) return null;
  const pct = Math.round(promo.real_percent);
  const text = promo.verdict === "real" ? "real deal" : promo.verdict === "usual" ? "usual price" : `${pct} % under usual`;
  const title = promo.usual_price != null
    ? `Per item with the deal: ${Math.abs(pct)} % ${promo.real_percent >= 0 ? "under" : "above"} the usual price, ${money(promo.usual_price)} (median of the last 90 days).`
    : "";
  return h(`span.real.${promo.verdict}`, { title }, text);
}

export function storeChip(store, label) {
  return h(`span.chip.store-${store}`, {}, label || store);
}

export function toast(message, bad = false) {
  const box = document.getElementById("toasts");
  if (!box) return;
  const el = h(`div.toast${bad ? ".bad" : ""}`, { role: "status" }, icon(bad ? "error" : "check"), message);
  box.append(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; }, bad ? 5200 : 2600);
  setTimeout(() => el.remove(), bad ? 5600 : 3000);
}

export function debounce(fn, ms = 250) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

export const prefs = {
  get(key, fallback) {
    try { const v = localStorage.getItem(`nyochi:${key}`); return v === null ? fallback : JSON.parse(v); }
    catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(`nyochi:${key}`, JSON.stringify(value)); } catch {}
  },
};

// A <dialog> with head / body / foot, removed from the page when closed.
export function dialog({ title, body, foot, wide = false, onClose }) {
  const close = () => dlg.close();
  const dlg = h("dialog", { style: wide ? { maxWidth: "min(720px, calc(100vw - 2rem))" } : null },
    h("div.dlg", {},
      h("div.dlg-head", {}, h("h2", {}, title),
        h("button.btn.btn-ghost.btn-icon", { type: "button", "aria-label": "Close", onclick: close }, icon("close"))),
      h("div.dlg-body", {}, body),
      foot ? h("div.dlg-foot", {}, foot) : null));
  dlg.addEventListener("close", () => { dlg.remove(); onClose?.(); });
  dlg.addEventListener("click", (e) => { if (e.target === dlg) close(); });
  document.body.append(dlg);
  dlg.showModal();
  return dlg;
}

// Ask before doing something that can't be undone. Resolves true / false.
export function confirmDialog({ title = "Are you sure?", message, confirm = "Delete", danger = true }) {
  return new Promise((resolve) => {
    let answer = false;
    const dlg = dialog({
      title,
      body: h("p.confirm-msg", {}, message),
      foot: [
        h("button.btn", { type: "button", onclick: () => dlg.close() }, "Cancel"),
        h(`button.btn${danger ? ".btn-danger.solid" : ".btn-primary"}`, { type: "button", onclick: () => { answer = true; dlg.close(); } }, confirm),
      ],
      onClose: () => resolve(answer),
    });
  });
}

export function sw(label, help, checked, onchange) {
  const input = h("input", { type: "checkbox", checked: !!checked, onchange: (e) => onchange?.(e.target.checked) });
  return h("label.switch", {}, input, h("span.track"), h("span.txt", {}, label, help ? h("small", {}, help) : null));
}

export function readJson(id) {
  try { return JSON.parse(document.getElementById(id)?.textContent || "null"); } catch { return null; }
}
