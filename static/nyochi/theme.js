// Resolve the theme onto <html data-theme> and wire every toggle button.
const KEY = "nyochi-theme";
const root = document.documentElement;
const media = matchMedia("(prefers-color-scheme: dark)");

function stored() {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

function apply(theme) {
  root.setAttribute("data-theme", theme);
  window.dispatchEvent(new CustomEvent("nyo:theme", { detail: theme }));
}

if (!root.hasAttribute("data-theme")) apply(media.matches ? "dark" : "light");
media.addEventListener("change", (e) => { if (!stored()) apply(e.matches ? "dark" : "light"); });

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-theme-toggle]");
  if (!btn) return;
  const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
  try { localStorage.setItem(KEY, next); } catch {}
  apply(next);
});
