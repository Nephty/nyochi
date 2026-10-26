// Pick Shopping products for an ingredient: search Shopping (through our server), add to the list; the form
// submits one hidden "link" input per product ("store|code") and a "preferred" radio.
import { api, debounce, h, icon, money, readJson, realChip, storeChip, untilText } from "./ui.js";

const root = document.querySelector("[data-picker]");
const chosen = root?.querySelector("[data-chosen]");
const search = root?.querySelector("[data-search]");
const results = root?.querySelector("[data-results]");

if (root && chosen && search && results) {
  const items = new Map(); // key -> link json (as the server gave it, or as search returned it)
  for (const l of readJson("links-data") || []) items.set(l.key, l);

  function card(l) {
    const promo = l.promo;
    return h("div.linkcard" + (promo ? ".promo" : ""), { dataset: { key: l.key } },
      h("input", { type: "hidden", name: "link", value: l.key }),
      h("div", {}, h("div.nm", {}, l.name || l.key)),
      h("div.px", {}, l.price != null ? h("div.now", {}, money(l.price)) : null, l.package_size ? h("small", {}, l.package_size) : null),
      h("div.sub", {}, storeChip(l.store, l.store_label),
        promo ? h("span.tag", {}, (promo.titles || "Promotion").slice(0, 40)) : null,
        promo ? realChip(promo) : null,
        promo?.until ? h("span", {}, untilText(promo.until)) : null),
      h("div.acts", {},
        h("label.switch", {}, h("input", { type: "radio", name: "preferred", value: l.key, checked: !!l.preferred }), h("span.track"), h("span.txt", {}, "Preferred")),
        h("button.btn.btn-sm.btn-danger", { type: "button", onclick: () => { items.delete(l.key); draw(); } }, icon("link_off"), "Remove")));
  }
  function draw() {
    chosen.replaceChildren(...(items.size ? [...items.values()].map(card)
      : [h("p.muted", { style: { margin: 0 } }, "No product linked yet.")]));
    // exactly one preferred when there are links
    const radios = [...chosen.querySelectorAll('input[name="preferred"]')];
    if (radios.length && !radios.some((r) => r.checked)) radios[0].checked = true;
  }

  async function run() {
    const q = search.value.trim();
    if (q.length < 2) { results.replaceChildren(); return; }
    results.replaceChildren(h("div.picker-empty", {}, "Searching…"));
    try {
      const { rows } = await api("/shopping/search/", { query: { q } });
      if (search.value.trim() !== q) return;
      results.replaceChildren(...(rows.length ? rows.map((r) => {
        const added = items.has(r.key);
        return h("button" + (added ? ".added" : ""), { type: "button", disabled: added,
          onclick: () => {
            items.set(r.key, {
              key: r.key, store: r.store, store_label: r.store_label, name: r.name, package_size: r.package_size, price: r.price,
              preferred: items.size === 0, url: r.url,
              promo: r.on_promotion ? { titles: r.promo_titles, until: r.promo_until, verdict: r.real_percent == null ? "" : r.real_percent >= 10 ? "real" : r.real_percent < 3 ? "usual" : "some", real_percent: r.real_percent, usual_price: r.usual_price } : null,
            });
            draw(); results.replaceChildren(); search.value = ""; search.focus();
          } },
          h("span.nm", {}, r.name),
          h("b", {}, r.price != null ? money(r.price) : "–"),
          h("span.sub", {}, storeChip(r.store, r.store_label), r.package_size ? h("span", {}, r.package_size) : null,
            r.on_promotion ? h("span.tag", {}, (r.promo_titles || "Promotion").slice(0, 36)) : null, added ? h("span", {}, "already linked") : null));
      }) : [h("div.picker-empty", {}, "Nothing found. Shopping searches the names of products it has fetched.")]));
    } catch (err) {
      results.replaceChildren(h("div.notice.bad", {}, icon("cloud_off"), h("span", {}, err.message)));
    }
  }
  search.addEventListener("input", debounce(run, 280));
  search.addEventListener("keydown", (e) => { if (e.key === "Enter") e.preventDefault(); });
  draw();
}
