// The month on phones: swipe it sideways for the next or previous month.
import { pager } from "./swipe.js";

const page = document.querySelector("[data-month-page]");
if (page && matchMedia("(max-width: 760px)").matches) {
  pager(page, { go: (dir) => {
    location.href = document.querySelector(dir > 0 ? "[data-next]" : "[data-prev]").href;
    return "away";
  } });
}
