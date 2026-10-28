// The Live home: every match in progress as one register, from live/index.json
// (the collector's latest numbers, not held back: nothing is being watched
// here). Each match's row opens it on watch.html. Text goes in through
// textContent, never innerHTML.
(function () {
  "use strict";

  const root = document.getElementById("live-overview");
  if (!root) return;
  const L = PrometheusLive;
  const $ = (id) => document.getElementById(id);
  const h = (tag, attrs, ...kids) => {
    const node = document.createElement(tag);
    for (const k in attrs || {}) {
      if (k === "class") node.className = attrs[k];
      else if (k in node) node[k] = attrs[k];
      else node.setAttribute(k, attrs[k]);
    }
    for (const kid of kids) if (kid != null) node.append(kid);
    return node;
  };

  const POLL_MS = 2000;
  const QUIET_MS = 60000;
  const RETRY_MS = 15000;
  const STALE_MS = 45000;
  const MAJORS = ["LCK", "LPL", "LEC", "LCS"];

  const table = $("matches");
  let index = null;
  let lifecycle = [];
  let failed = false;
  let skew = 0;
  let timer = null;
  const upcoming = document.getElementById("upcoming-section");
  const fixtureRows = upcoming ? [...upcoming.querySelectorAll("tr.fx")] : [];
  const shownLive = new Set();

  function updateUpcoming(matches) {
    for (const row of fixtureRows) {
      if (L.fixtureOnLive((row.dataset.teams || "").split("|"), row.dataset.start, matches)) shownLive.add(row);
      row.toggleAttribute("data-on-live", shownLive.has(row));
    }
    document.dispatchEvent(new Event("fixtures:refilter"));
  }

  async function poll() {
    clearTimeout(timer);
    try {
      const res = await fetch(root.dataset.index, { cache: "no-store" });
      const date = Date.parse(res.headers.get("Date"));
      if (!Number.isNaN(date)) skew = date - Date.now();
      if (res.status === 404 || res.status === 403) index = { matches: [] };
      else if (!res.ok) throw new Error(res.status);
      else index = await res.json();
      try {
        const states = await fetch("live/lifecycle.json", { cache: "no-store" });
        if (states.ok) lifecycle = Object.values((await states.json()).series || {});
      } catch (_) { /* Keep the last confirmed states if this read fails. */ }
      failed = false;
    } catch (e) {
      failed = true;
    }
    render();
    const live = index && L.liveMatches(index).length;
    if (!document.hidden) timer = setTimeout(poll, failed ? RETRY_MS : live ? POLL_MS : QUIET_MS);
  }
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) clearTimeout(timer);
    else poll();
  });

  const watchUrl = (m) => `watch.html?match=${encodeURIComponent(m.id)}`;
  const ago = (ms) => {
    const s = Math.max(0, Math.round(ms / 1000));
    return s < 90 ? `${s} s ago` : `${Math.round(s / 60)} min ago`;
  };
  const startFormat = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/Los_Angeles", timeZoneName: "short" });
  const muted = (text) => h("span", { class: "muted" }, text);

  // Rows are rebuilt on each read; the status line also every second.
  function render(rows = true) {
    if (!index) {
      if (failed) $("matches-caption").textContent = "Feed unreachable.";
      return;
    }
    const matches = L.liveMatches(index, MAJORS).filter((m) => !lifecycle.some((s) => s.id === m.id && s.status === "completed"));
    const age = Date.now() + skew - (L.time(index.published_at) || 0);
    const n = matches.length;
    root.hidden = !n;
    const stale = failed || (n > 0 && age > STALE_MS);
    $("matches-caption").textContent = [
      "Matches in progress",
      failed ? "; feed unreachable." : stale ? `; stalled, last update ${ago(age)}.` : ".",
      index.note ? ` ${index.note}` : "",
    ].join("");
    $("matches-cap").classList.toggle("is-stale", stale);
    if (!rows) return;
    const recent = lifecycle.filter((m) => L.time(m.start) >= Date.now() + skew - 7 * 86400000);
    updateUpcoming([...matches, ...recent]);
    table.hidden = !n;
    [...table.tBodies].forEach((b) => b.remove());
    for (const m of matches) table.appendChild(row(m));
  }

  // One match: a tbody with its row, and a second line of figures for phones.
  function row(m) {
    const g = m.game || {};
    const t = g.teams || [];
    const call = L.summaryCall(g);
    const waiting = m.status === "waiting";
    const series = m.series || {};
    const q = waiting ? (series.kalshi ? L.quoteAt([series.kalshi], Infinity) : null) : g.market ? L.quoteAt([g.market], Infinity) : null;
    const p = waiting ? L.in100(series.ours) : call ? L.in100(call.p) : null;
    const fav = p == null ? 0 : p > 50 ? 1 : p < 50 ? 2 : 0;
    // Team names are the row's links, so the match opens from the keyboard too.
    const team = (i) => h("a", { class: "lm-name", href: watchUrl(m), title: (m.teams[i] && m.teams[i].name) || "" }, (m.teams[i] && m.teams[i].name) || "?");
    const clock = m.status === "waiting" ? "Waiting" : g.ended_at ? "Ended" : L.clock(g.clock ?? g.clock_estimate) ?? "—";
    const bar = h("span", { class: "fx-bar", style: `--p:${p ?? 50}` }, q ? h("span", { class: "fx-mkt", style: `--m:${L.in100(q.mid)}` }) : null);
    if (p == null) bar.classList.add("is-empty");
    bar.title = [p != null ? `Ours ${p}–${100 - p}, ${waiting ? "series" : call.note}` : "No call yet", q ? `Kalshi ${L.in100(q.mid)}–${100 - L.in100(q.mid)}` : "No Kalshi price"].join("; ");
    const stats = [
      ["Gold", L.goldLeader(t, m.teams)],
      ["Kills", L.pair(t[0] && t[0].kills, t[1] && t[1].kills)],
      ["Towers", L.pair(t[0] && t[0].towers, t[1] && t[1].towers)],
      ["Dragons", L.pair(t[0] && t[0].dragons, t[1] && t[1].dragons)],
      ["Barons", L.pair(t[0] && t[0].barons, t[1] && t[1].barons)],
    ];
    const statCell = ([, v], i) => h("td", { class: `num lm-stat${i >= 2 ? " lm-wide" : ""}` }, v ?? muted("—"));
    const score = Array.isArray(m.score) ? `${m.score[0]}–${m.score[1]}` : "—";
    const main = h("tr", { class: "lm" },
      h("td", { class: "lm-clock" }, h("span", { class: "lm-time" }, clock), h("span", { class: "lm-map" }, waiting ? (m.start && !(m.score || []).some((x) => x > 0) ? startFormat.format(new Date(m.start)) : "") : `Map ${g.number ?? "?"}`)),
      h("td", { class: "lm-league wide-only" }, h("span", { class: "league", "data-league": m.league }, h("span", { class: "league-mark", "aria-hidden": "true" }), m.league)),
      h("td", { class: `lm-team lm-team--1${fav === 1 ? " fav" : ""}` }, team(0)),
      h("td", { class: `num lm-p${fav === 1 ? " fav" : ""}` }, p == null ? muted("—") : String(p)),
      h("td", { class: "lm-bar-col" }, bar),
      h("td", { class: `num lm-p lm-p--2${fav === 2 ? " fav" : ""}` }, p == null ? muted("—") : String(100 - p)),
      h("td", { class: `lm-team lm-team--2${fav === 2 ? " fav" : ""}` }, team(1)),
      h("td", { class: "num lm-opt lm-kalshi" }, q ? String(L.in100(q.mid)) : muted("—")),
      h("td", { class: "num lm-series", title: m.best_of ? `Best of ${m.best_of}` : "" }, score),
      ...stats.map(statCell),
    );
    // Phones: one line of figures under the match (only Kalshi before it starts).
    const kalshi = q ? [h("span", { class: "lm-k" }, "Kalshi"), ` ${L.in100(q.mid)}`] : [];
    const line = h("tr", { class: "lm-line" }, h("td", { colspan: "14" }, ...(waiting ? kalshi : [
      h("span", { class: "lm-k" }, "Series"), ` ${score}`,
      ...(q ? [" · ", ...kalshi] : []),
      ...stats.flatMap(([k, v]) => [" · ", h("span", { class: "lm-k" }, k), " ", v ?? "—"])])));
    const body = h("tbody", { class: "lm-match", "data-league": m.league }, main, waiting && !q ? null : line);
    body.addEventListener("click", (e) => { if (!e.target.closest("a")) location.href = watchUrl(m); });
    return body;
  }

  setInterval(() => { if (!document.hidden && index) render(false); }, 1000);
  poll();
})();
