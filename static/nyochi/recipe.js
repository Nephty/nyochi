// The recipe page (templates/recipes/detail.html): how many portions (a recipe is written for one; amounts, costs and
// the estimate follow, and "Start cooking" takes the number along), and prices entered by hand for the ingredients
// Shopping can't price (saved per ingredient and unit: recipes/models.py UnitPrice).
import { money, num, readJson } from "./ui.js";
import { priceDialog } from "./unit-price.js";

const B = readJson("recipe-boot");
if (B) {
  // ------------------------------------------------------------------ portions
  const KEY = `nyochi-portions-${B.id}`;
  const box = document.querySelector("[data-portions]");
  let portions = 1;
  try { portions = Math.min(20, Math.max(1, Number(localStorage.getItem(KEY)) || 1)); } catch { /* private mode */ }

  const plural = (n) => `${n} portion${n === 1 ? "" : "s"}`;
  function scale() {
    box.querySelector("[data-portions-v]").textContent = plural(portions);
    box.querySelector('[data-step="-1"]').disabled = portions <= 1;
    box.querySelector('[data-step="1"]').disabled = portions >= 20;
    document.querySelectorAll("[data-amount]").forEach((el) => { el.textContent = `${num(Number(el.dataset.amount) * portions)} ${el.dataset.unit}`.trim(); });
    document.querySelectorAll("[data-cost]").forEach((el) => { el.textContent = `≈ ${money(Number(el.dataset.cost) * portions)} here`; });
    document.querySelectorAll("[data-share]").forEach((el) => { el.textContent = money(Number(el.dataset.share) * portions); });
    const total = document.querySelector("[data-total]");
    if (total) {
      total.textContent = `≈ ${money(Number(total.dataset.total) * portions)}`;
      const per = document.querySelector("[data-per-portion]");
      per.hidden = portions === 1;
      per.textContent = `for ${plural(portions)} · ${money(Number(total.dataset.total))} each`;
    }
    document.querySelectorAll("a[data-cook]").forEach((a) => { a.href = `${B.cookUrl}?portions=${portions}`; });
  }
  box.hidden = false;
  box.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => {
    portions = Math.min(20, Math.max(1, portions + Number(b.dataset.step)));
    try { localStorage.setItem(KEY, String(portions)); } catch { /* private mode */ }
    scale();
  }));
  // the steps panel's own "Start cooking" link takes the portions too
  document.querySelectorAll(`a[href="${B.cookUrl}"]`).forEach((a) => { a.dataset.cook = ""; });
  scale();

  // ------------------------------------------------------------------ prices entered by hand
  const rows = new Map(B.prices.map((p) => [String(p.ingredient), p]));
  document.querySelectorAll("[data-price]").forEach((btn) => {
    const row = rows.get(btn.dataset.price);
    if (!row) { btn.disabled = true; return; }   // you can't change this ingredient
    btn.hidden = false;
    btn.addEventListener("click", () => priceDialog(row, B));
  });
}
