// Build-relative results overlay, shared by registers, matchups and home tables.
const PrometheusFresh = (function () {
  "use strict";
  let pending;
  async function load(base) {
    if (!base) return null;
    try {
      pending ||= fetch("fresh.json", { cache: "no-store" }).then((r) => r.ok ? r.json() : null);
      const overlay = await pending;
      if (!overlay || overlay.base !== base || !overlay.teams || !overlay.players
          || !Object.keys(overlay.teams).length && !Object.keys(overlay.players).length) return null;
      return overlay;
    } catch (e) { return null; }
  }

  function apply(rows, overlay, entity = "team") {
    let changed = false;
    const deltas = entity === "player" ? overlay.players : overlay.teams;
    for (const row of rows) {
      const key = entity === "player" ? row.slug : row.teamname;
      const delta = deltas?.[key];
      if (!row.now || !Number.isFinite(delta) || !delta) continue;
      for (const field of ["elo", "forge"]) {
        if (Number.isFinite(row[field])) { row[field] += delta; changed = true; }
      }
    }
    return changed;
  }

  const stampFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
  const stamp = (iso) => stampFormat.format(new Date(iso.replace("Z", ":00Z")));

  // Jinja/Python round uses ties to even; keep the home values consistent.
  function rounded(value) {
    const floor = Math.floor(value);
    return value - floor === 0.5 ? floor + (floor % 2) : Math.round(value);
  }

  function homeTables() {
    for (const table of document.querySelectorAll("table[data-through]")) {
      load(table.dataset.through).then((overlay) => {
        if (!overlay) return;
        let changed = false;
        const rows = Array.from(table.tBodies[0].rows);
        for (const row of rows) {
          const delta = row.dataset.player ? overlay.players[row.dataset.player] : overlay.teams[row.dataset.team];
          if (!Number.isFinite(delta) || !delta) continue;
          changed = true;
          for (const cell of row.querySelectorAll("[data-value]")) {
            const value = Number(cell.dataset.value) + delta;
            cell.dataset.value = value;
            cell.textContent = rounded(value);
          }
          const value = Number(row.querySelector(".value").dataset.value);
          const [lo, hi] = JSON.parse(table.dataset.domain);
          row.querySelector(".bar").style.setProperty("--v", ((value - lo) / (hi - lo) * 100).toFixed(1));
        }
        if (!changed) return;
        rows.sort((a, b) => Number(b.querySelector(".value").dataset.value) - Number(a.querySelector(".value").dataset.value));
        rows.forEach((row, i) => {
          row.querySelector(".rank").textContent = i + 1;
          table.tBodies[0].appendChild(row);
        });
        if (overlay.results_through) {
          // Before the caption's trailing link ("See every team"), as on Predictions.
          const cap = table.closest("figure").querySelector("figcaption");
          const link = cap.querySelector("a");
          cap.insertBefore(document.createTextNode(`Results through ${stamp(overlay.results_through)}. `), link);
        }
      });
    }
  }
  if (typeof document !== "undefined") homeTables();
  return { load, apply, stamp };
})();
if (typeof module !== "undefined") module.exports = PrometheusFresh;
