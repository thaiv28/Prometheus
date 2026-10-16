// The live page's reading of live/state.json, kept free of the DOM so it is
// tested under Node (tests/js). live.js draws what this returns.
//
// Everything in the state carries a wall-clock time (`at`, ISO 8601, UTC);
// `release` gives the state as of a cutoff (the page uses everything received).
const PrometheusLive = (function () {
  "use strict";

  // Quotes with a wider bid-ask spread are too thin to call a price (as in
  // prometheus/markets.py).
  const MAX_SPREAD = 0.1;

  const time = (iso) => {
    const t = Date.parse(iso);
    return Number.isNaN(t) ? null : t;
  };
  const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

  // The state as of `cutoff` (ms since the epoch): frames, quotes and calls made
  // by then, and the winner only once the map's end has been released.
  function release(state, cutoff) {
    const game = state && state.game;
    if (!game) return { ...state, game: null };
    const upTo = (items) => (Array.isArray(items) ? items : []).filter((x) => {
      const t = time(x && x.at);
      return t != null && t <= cutoff;
    });
    const frames = upTo(game.frames).sort((a, b) => time(a.at) - time(b.at));
    const ended = game.ended_at != null && time(game.ended_at) != null && time(game.ended_at) <= cutoff;
    return {
      ...state,
      game: {
        ...game,
        frames,
        market: upTo(game.market).sort((a, b) => time(a.at) - time(b.at)),
        calls: upTo(game.calls).sort((a, b) => a.minute - b.minute),
        winner: ended ? game.winner : null,
        ended,
        held: (Array.isArray(game.frames) ? game.frames.length : 0) - frames.length,
      },
    };
  }

  // The figure's x: seconds of game clock when every released frame has one,
  // else the collector's estimated game time when every frame has that (mode
  // "estimated"), otherwise seconds since the first frame. Returns
  // { mode, x(at ms) }. Between two clocked frames a time maps linearly, so a
  // quote read during a pause lands on the paused clock and a pause takes no width.
  function axis(frames) {
    const read = (key) => frames.map((f) => ({ t: time(f.at), c: num(f[key]) })).filter((p) => p.t != null);
    const all = (ps) => ps.length > 0 && ps.every((p) => p.c != null);
    let pts = read("clock");
    let mode = "clock";
    if (!all(pts)) {
      pts = read("clock_estimate");
      mode = "estimated";
    }
    if (!all(pts)) {
      const t0 = pts.length ? pts[0].t : null;
      return { mode: "elapsed", x: (t) => (t0 == null || t == null ? null : Math.max(0, (t - t0) / 1000)) };
    }
    return {
      mode,
      x(t) {
        if (t == null) return null;
        if (t <= pts[0].t) return Math.max(0, pts[0].c - (pts[0].t - t) / 1000);
        for (let i = 1; i < pts.length; i++) {
          const a = pts[i - 1], b = pts[i];
          if (t <= b.t) {
            const span = b.t - a.t;
            return span > 0 ? a.c + ((b.c - a.c) * (t - a.t)) / span : b.c;
          }
        }
        const last = pts[pts.length - 1];
        return last.c + (t - last.t) / 1000;
      },
    };
  }

  // Our latest call: the newest checkpoint released, or the pre-game one.
  function currentCall(game) {
    if (!game) return null;
    const calls = game.calls || [];
    if (calls.length) return { ...calls[calls.length - 1], kind: "checkpoint" };
    if (game.pregame && num(game.pregame.p) != null) return { ...game.pregame, kind: "pregame" };
    return null;
  }

  // Kalshi's quote at time t: the last one read by then, if its spread is usable.
  function quoteAt(quotes, t) {
    let q = null;
    for (const x of quotes || []) {
      if (time(x.at) <= t) q = x;
      else break;
    }
    if (!q) return null;
    const bid = num(q.bid), ask = num(q.ask);
    if (bid == null || ask == null || ask < bid || ask - bid > MAX_SPREAD) return null;
    return { at: q.at, bid, ask, mid: (bid + ask) / 2 };
  }

  // '28.5k' (one decimal, as the broadcast shows gold); null -> null.
  const gold = (v) => (num(v) == null ? null : `${(v / 1000).toFixed(1)}k`);
  // '14:05' from seconds.
  const clock = (s) => {
    if (num(s) == null) return null;
    const t = Math.max(0, Math.floor(s));
    return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
  };
  // A chance in 0–1 as a whole number in 100.
  const in100 = (p) => (num(p) == null ? null : Math.round(100 * p));

  // ---- Match summaries (live/index.json) ------------------------------------
  // Each match in progress: { id, url, league, event, best_of, teams, score,
  // status, game: { number, blue, clock, at, pregame, call, market, teams,
  // winner, ended_at } }, with the feed's latest numbers.

  // Matches to list: in progress, majors first in their usual order, then the
  // rest by league, keeping the index's order within a league.
  function liveMatches(index, majors = []) {
    const list = (index && Array.isArray(index.matches) ? index.matches : [])
      .filter((m) => m && m.id && m.status !== "idle" && m.status !== "unavailable");
    const rank = (lg) => {
      const i = majors.indexOf(lg);
      return i < 0 ? majors.length : i;
    };
    return list
      .map((m, i) => ({ m, i }))
      .sort((a, b) => rank(a.m.league) - rank(b.m.league) || String(a.m.league).localeCompare(String(b.m.league)) || a.i - b.i)
      .map((x) => x.m);
  }

  // A match file's path from the index: relative, under live/, a .json file.
  // A match file, or one finished map of it (live/<match>/map<n>.json).
  const safeUrl = (u) => (typeof u === "string" && /^live\/[\w-]+(\/map\d+)?\.json$/.test(u) ? u : null);

  // Our call on a summary's game: the latest checkpoint, else the pre-game one,
  // with the note shown beside it.
  function summaryCall(game) {
    if (!game) return null;
    if (game.call && num(game.call.p) != null) return { p: game.call.p, note: `at ${game.call.minute}′`, by: game.call.by };
    if (game.pregame && num(game.pregame.p) != null) return { p: game.pregame.p, note: "before the map", by: game.pregame.by };
    return null;
  }

  // '7–5' from two numbers; a dash for a missing one.
  const pair = (a, b) => `${num(a) == null ? "—" : a}–${num(b) == null ? "—" : b}`;
  // The first team's gold lead: '+2.4k', '−0.8k' or 'even'; null when missing.
  function goldLead(teams) {
    const a = teams && teams[0] && num(teams[0].gold);
    const b = teams && teams[1] && num(teams[1].gold);
    if (a == null || b == null) return null;
    const d = a - b;
    if (Math.abs(d) < 50) return "even";
    return `${d > 0 ? "+" : "−"}${(Math.abs(d) / 1000).toFixed(1)}k`;
  }
  // The gold lead named for the team that has it: 'T1 +2.4k', 'even', or null.
  function goldLeader(teams, names) {
    const a = teams && teams[0] && num(teams[0].gold);
    const b = teams && teams[1] && num(teams[1].gold);
    if (a == null || b == null) return null;
    const d = a - b;
    if (Math.abs(d) < 50) return "even";
    return `${short(names && names[d > 0 ? 0 : 1])} +${(Math.abs(d) / 1000).toFixed(1)}k`;
  }
  // A team's short name: its code when the feed gives one.
  const short = (team) => (team && (team.code || team.name)) || "?";

  return { MAX_SPREAD, time, release, axis, currentCall, quoteAt, gold, clock, in100, liveMatches, safeUrl, summaryCall, pair, goldLead, goldLeader, short };
})();

if (typeof module === "object" && module.exports) module.exports = PrometheusLive;
