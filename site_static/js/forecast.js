// GlorELO+ page: the head-to-head box. Between teams from the same league the chance
// that A beats B on a neutral side is 1 / (1 + e^(-w * (A - B))) on GlorELO+ ratings.
// Between leagues Form doesn't compare, so it comes from the Elo gap alone, on its
// own curve. Both weights are embedded in the page config by build_site.py.
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  let rows = [];
  let config = {};
  try {
    rows = JSON.parse($("#rows-data").textContent);
    config = JSON.parse($("#page-config").textContent);
  } catch (e) { return; }
  const weights = config.weights || {};
  // Head to head is for today, so only the "now" rows count.
  const teams = new Map(rows.filter((r) => r.now).map((r) => [r.teamname, r]));

  const a = $("#matchup-a");
  const b = $("#matchup-b");
  const out = $("#matchup-result");
  const bar = $(".matchup-bar-a");
  const note = $("#matchup-note");
  if (!a || !b || !out) return;

  function chance(x, y) {
    const sameLeague = x.league === y.league;
    if (note) note.hidden = sameLeague;
    const gap = sameLeague
      ? weights.elo * (Number(x.glorelo) - Number(y.glorelo))
      : weights.crossRegionElo * (Number(x.elo) - Number(y.elo));
    return 1 / (1 + Math.exp(-gap));
  }

  function update() {
    if (a.value === b.value) {
      out.textContent = "Pick two different teams.";
      if (note) note.hidden = true;
      if (bar) bar.style.setProperty("--p", 50);
      return;
    }
    const pct = Math.round(chance(teams.get(a.value), teams.get(b.value)) * 100);
    // One game is never certain; don't print 0 or 100.
    out.textContent = pct >= 100 ? "more than 99 times in 100"
      : pct <= 0 ? "less than once in 100"
      : `${pct} ${pct === 1 ? "time" : "times"} in 100`;
    if (bar) bar.style.setProperty("--p", pct);
  }

  a.addEventListener("change", update);
  b.addEventListener("change", update);
  update();
})();
