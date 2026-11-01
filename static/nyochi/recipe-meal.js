// The recipe page's "Add to the calendar": the meal dialog with this recipe, today, its meal type's slot.
import { readJson } from "./ui.js";
import { mealDialog } from "./meal-dialog.js";

const B = readJson("meal-boot");
document.querySelector("[data-add-meal]")?.addEventListener("click", () => {
  if (!B) return;
  mealDialog({ at: { day: B.today, slot: B.slot }, recipe: B.recipes[0].id, ctx: B,
    onDone: () => setTimeout(() => location.reload(), 900) });
});
