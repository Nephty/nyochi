// The season ribbon editor: pick a colour, click or drag over the months. Without JS each month is a plain <select>.
const ribbon = document.querySelector("[data-ribbon]");
if (ribbon) {
  const bar = document.querySelector("[data-brushbar]");
  const cells = [...ribbon.querySelectorAll(".m")];
  let brush = "in";
  let painting = false;
  let last = null; // index of the last painted month: a fast drag skips cells, so fill the ones in between
  ribbon.classList.add("js");
  if (bar) bar.hidden = false;

  const set = (cell, status) => {
    const select = cell.querySelector("select");
    select.value = status;
    cell.className = `m m-${status}`;
    cell.title = `${cell.title.split(":")[0]}: ${select.selectedOptions[0].text}`;
  };
  const paintTo = (i) => {
    const from = last === null ? i : last;
    for (let k = Math.min(from, i); k <= Math.max(from, i); k++) set(cells[k], brush);
    last = i;
  };
  cells.forEach((cell) => {
    cell.tabIndex = 0;
    cell.addEventListener("pointerdown", (e) => { e.preventDefault(); painting = true; last = null; paintTo(cells.indexOf(cell)); });
    cell.addEventListener("keydown", (e) => {
      const i = cells.indexOf(cell);
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); set(cell, brush); }
      else if (e.key === "ArrowRight") cells[Math.min(11, i + 1)].focus();
      else if (e.key === "ArrowLeft") cells[Math.max(0, i - 1)].focus();
    });
  });
  // dragging: follow the pointer across cells (works for touch too, where pointerenter doesn't fire)
  ribbon.addEventListener("pointermove", (e) => {
    if (!painting) return;
    const el = document.elementFromPoint(e.clientX, e.clientY)?.closest(".m");
    if (el && ribbon.contains(el)) paintTo(cells.indexOf(el));
  });
  ribbon.style.touchAction = "none";
  window.addEventListener("pointerup", (e) => {
    if (painting) {
      const el = document.elementFromPoint(e.clientX, e.clientY)?.closest(".m");
      if (el && ribbon.contains(el)) paintTo(cells.indexOf(el));
    }
    painting = false;
  });
  window.addEventListener("pointercancel", () => { painting = false; });

  bar?.querySelectorAll("[data-brush]").forEach((b) => b.addEventListener("click", () => {
    brush = b.dataset.brush;
    bar.querySelectorAll("[data-brush]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  }));
  bar?.querySelectorAll("[data-fill]").forEach((b) => b.addEventListener("click", () => cells.forEach((c) => set(c, b.dataset.fill))));
}
