// The ingredient page: its prices entered by hand (per unit), added, changed or removed in the price dialog.
import { readJson } from "./ui.js";
import { priceDialog } from "./unit-price.js";

const B = readJson("price-boot");
if (B) {
  const base = { ingredient: B.ingredient, name: B.name };
  document.querySelector("[data-price-add]")?.addEventListener("click", () => {
    const unit = B.units.find((u) => u.id === B.unit) || B.units[0];
    const manual = B.prices.find((p) => p.unit === unit.id);   // already priced: change it
    priceDialog({ ...base, unit: unit.id, abbr: unit.abbr, manual }, B);
  });
  document.querySelectorAll("[data-price-edit]").forEach((btn) => btn.addEventListener("click", () => {
    const manual = B.prices.find((p) => p.unit === Number(btn.dataset.priceEdit));
    priceDialog({ ...base, unit: manual.unit, abbr: manual.abbr, manual }, B);
  }));
}
