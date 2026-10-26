// The shopping list as a till receipt: sections in walking order (numbered stops when a shop layout is chosen),
// each line with what to buy in Shopping. Used by the Plan screen and by saved lists.
import { h, icon, money, num, realChip, storeChip, untilText } from "./ui.js";

const SEASON_TEXT = { in: "in season", early: "early season", late: "late season", out: "out of season" };

export function receiptText(data, title) {
  const out = [title];
  for (const s of data.sections) {
    out.push("", s.stop ? `${s.stop}. ${s.title}` : s.title);
    for (const l of s.lines) out.push(`- ${l.amount != null ? `${num(l.amount)} ${l.unit} ` : ""}${l.name}`);
  }
  return out.join("\n");
}

function line(l, opts) {
  const buy = l.buy;
  const promo = buy?.promo;
  const check = opts.checkable
    ? h("label.chk", {}, h("input", { type: "checkbox", checked: l.checked, "aria-label": `Got ${l.name}`, onchange: (e) => opts.onCheck?.(l, e.target.checked) }), h("span", {}, icon("check")))
    : null;
  return h("div.rline" + (l.checked ? ".done" : "") + (check ? "" : ".nochk"), { dataset: { id: l.id ?? "" } },
    check,
    h("div.nm", {}, h("span.t", {}, l.name),
      l.season && l.season !== "unknown" ? h(`span.chip.season-${l.season}`, {}, SEASON_TEXT[l.season]) : null,
      opts.onDelete && l.id ? h("button.btn.btn-ghost.btn-sm.btn-icon.del", { type: "button", "aria-label": `Remove ${l.name}`, onclick: () => opts.onDelete(l) }, icon("close")) : null),
    h("div.qty", {}, l.amount != null ? `${num(l.amount)} ${l.unit}` : ""),
    l.sources?.length ? h("div.src", {}, `for ${l.sources.join(", ")}`) : null,
    buy ? h("div.buy", {},
      storeChip(buy.store, buy.store_label),
      h("span.pn", { title: buy.name }, `${buy.packs > 1 ? `${buy.packs} × ` : ""}${buy.name}`),
      promo ? h("span.tag", { title: promo.titles }, (promo.titles || "Promotion").slice(0, 28)) : null,
      promo ? realChip(promo) : null,
      promo?.until ? h("span.muted", {}, untilText(promo.until)) : null,
      h("span.cost", { title: buy.exact ? "" : "The pack size can’t be compared with the amount: counted as one pack." }, `${buy.exact ? "" : "≈ "}${money(buy.cost)}`),
    ) : null);
}

export function renderReceipt(box, data, opts = {}) {
  const routed = !!data.location;
  const t = data.totals;
  const sections = data.sections.map((s) => h("section.rsec", {},
    s.stop ? h("span.stop", {}, s.stop) : null,
    h("div.rsec-h", {}, h("span", {}, s.title), h("span.n", {}, `${s.lines.length}`)),
    s.lines.map((l) => line(l, opts))));
  const hasPrices = t.priced > 0;
  box.replaceChildren(h("div.receipt", {}, h("div.rcpt" + (routed ? ".routed" : ""), {},
    h("div.rcpt-head", {}, h("span", {}, "Nyochi"), h("span", {}, new Date().toLocaleDateString("en-GB", { day: "numeric", month: "short" }))),
    opts.title ? h("div.rcpt-title", {}, opts.title) : null,
    h("div.rcpt-sub", {}, [
      `${t.lines} item${t.lines === 1 ? "" : "s"}`,
      routed ? ` · in the order of ${data.location.name}` : " · grouped by category",
      opts.progress ? ` · ${opts.progress.done} of ${opts.progress.total} in the cart` : "",
    ].join("")),
    opts.progress ? h("div.progress.thin", { style: { marginTop: ".6rem" } }, h("div", { style: { width: `${opts.progress.total ? (100 * opts.progress.done) / opts.progress.total : 0}%` } })) : null,
    data.sections.length ? sections : h("div.rcpt-empty", {}, icon("shopping_basket"), h("b", {}, opts.emptyTitle || "Nothing here yet"), h("span", {}, opts.emptyText || "")),
    data.sections.length && (hasPrices || data.shopping?.configured) ? h("div.rtotals", {},
      hasPrices ? [
        h("div.ln", {}, h("span", {}, `Priced (${t.priced} of ${t.lines} items)`), h("span", {}, money(t.cost))),
        t.saving > 0 ? h("div.ln.save", {}, h("span", {}, "Promotions on the way"), h("span", {}, `− ${money(t.saving)}`)) : null,
        h("div.ln.total", {}, h("span", {}, t.saving > 0 ? "After promotions" : "Estimated total"), h("span", {}, money(t.after_deals))),
        t.unpriced ? h("div.note", {}, `${t.unpriced} item${t.unpriced === 1 ? " has" : "s have"} no linked product, so it isn’t counted.`) : null,
      ] : h("div.note", {}, "Link ingredients to Shopping products to see prices and promotions here."),
      data.shopping?.configured && !data.shopping.reachable ? h("div.note", {}, "Shopping can’t be reached right now: these are the last prices we have.") : null,
      data.stores?.length > 1 ? h("div.rstores", {}, data.stores.map((s) => h(`span.chip.store-${s.store}`, { title: `${s.label} has a product for ${s.lines} of these items` }, `${s.label} · ${s.lines} items · ${money(s.cost)}`))) : null,
    ) : null,
    data.sections.length ? h("div.rcpt-foot", { dataset: { barcode: "" } }) : null,
  )));
  box.querySelector("[data-barcode]")?.insertAdjacentHTML("beforeend", BARCODE);
}

const BARCODE = '<svg class="barcode" viewBox="0 0 120 30" preserveAspectRatio="none" aria-hidden="true" fill="currentColor"><rect x="0" width="2" height="30"/><rect x="4" width="1" height="30"/><rect x="7" width="3" height="30"/><rect x="12" width="1" height="30"/><rect x="15" width="2" height="30"/><rect x="19" width="4" height="30"/><rect x="25" width="1" height="30"/><rect x="28" width="2" height="30"/><rect x="32" width="1" height="30"/><rect x="35" width="3" height="30"/><rect x="40" width="1" height="30"/><rect x="43" width="2" height="30"/><rect x="47" width="1" height="30"/><rect x="50" width="4" height="30"/><rect x="56" width="1" height="30"/><rect x="59" width="2" height="30"/><rect x="63" width="3" height="30"/><rect x="68" width="1" height="30"/><rect x="71" width="2" height="30"/><rect x="75" width="1" height="30"/><rect x="78" width="3" height="30"/><rect x="83" width="2" height="30"/><rect x="87" width="1" height="30"/><rect x="90" width="4" height="30"/><rect x="96" width="1" height="30"/><rect x="99" width="2" height="30"/><rect x="103" width="1" height="30"/><rect x="106" width="3" height="30"/><rect x="111" width="1" height="30"/><rect x="114" width="2" height="30"/><rect x="118" width="2" height="30"/></svg>';
