// The Lists page on a phone: swipe a list left to archive it (or, in the archive, to bring it back).
import { icon } from "./ui.js";
import { row } from "./swipe.js";

const archived = new URLSearchParams(location.search).get("tab") === "archived";
const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
for (const card of document.querySelectorAll(".lcard[data-archive]")) {
  row(card, { left: {
    icon: icon(archived ? "unarchive" : "archive"), label: archived ? "Restore" : "Archive", tone: "neutral", out: true,
    run: () => {
      const form = Object.assign(document.createElement("form"), { method: "post", action: card.dataset.archive });
      form.append(Object.assign(document.createElement("input"), { type: "hidden", name: "csrfmiddlewaretoken", value: csrf }));
      document.body.append(form);
      form.submit();
    },
  } });
}
