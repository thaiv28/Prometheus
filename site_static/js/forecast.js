// GlorELO+ page: the head-to-head box. Ratings are on the Elo scale, so the chance
// that A beats B on a neutral side is 1 / (1 + 10^((B - A) / 400)).
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  let rows = [];
  try { rows = JSON.parse($("#rows-data").textContent); } catch (e) { return; }
  const rating = new Map(rows.map((r) => [r.teamname, Number(r.glorelo)]));

  const a = $("#matchup-a");
  const b = $("#matchup-b");
  const out = $("#matchup-result");
  const bar = $(".matchup-bar-a");
  if (!a || !b || !out) return;

  function update() {
    if (a.value === b.value) {
      out.textContent = "Pick two different teams.";
      if (bar) bar.style.setProperty("--p", 50);
      return;
    }
    const p = 1 / (1 + Math.pow(10, (rating.get(b.value) - rating.get(a.value)) / 400));
    const pct = Math.round(p * 100);
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
