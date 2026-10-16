// The live page: polls live/index.json and the watched match's file, shows every
// number as it arrives, and draws the stream, the reading, Figure 1
// (win chance over the game: our calls and Kalshi's price, gold lead below) and
// the scoreline. Text goes in through textContent, never innerHTML.
(function () {
  "use strict";

  const root = document.getElementById("live");
  if (!root) return;
  const L = PrometheusLive;
  const $ = (id) => document.getElementById(id);
  const SVG = "http://www.w3.org/2000/svg";
  const svgEl = (name, attrs, text) => {
    const node = document.createElementNS(SVG, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (text != null) node.textContent = text;
    return node;
  };
  const h = (tag, attrs, ...kids) => {
    const node = document.createElement(tag);
    for (const k in attrs || {}) {
      if (k === "class") node.className = attrs[k];
      else if (k in node && k !== "list") node[k] = attrs[k];
      else node.setAttribute(k, attrs[k]);
    }
    for (const kid of kids) if (kid != null) node.append(kid);
    return node;
  };
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private window */ } },
  };

  const POLL_MS = 5000;
  const RETRY_MS = 15000;
  // With no game in the feed, look again once a minute.
  const QUIET_MS = 60000;
  // A state file older than this is called stalled.
  const STALE_MS = 45000;

  const MAJORS = ["LCK", "LPL", "LEC", "LCS"];

  let streams = [];
  try { streams = JSON.parse($("live-streams").textContent); } catch (e) { /* no picker */ }

  // ---- State --------------------------------------------------------------
  let index = null;        // live/index.json: every match in progress
  let matches = [];        // its live matches, in display order
  let matchId = new URLSearchParams(location.search).get("match") || store.get("live.match");
  let state = null;        // the chosen match's file
  let failed = false;      // the last read failed
  let skew = 0;            // server clock minus ours, from the Date header
  let pollTimer = null;
  let cursor = null;       // index of the traced frame, or null for the latest
  let view = null;         // the released state now shown
  let geom = null;         // the figure's scales, for pointer reading
  let teamSlugs = null;    // folded team name -> page slug
  let mapPick = null;      // a finished map being viewed (its number), or null for the current one
  let mapAsked = Number(new URLSearchParams(location.search).get("map")) || null; // ?map=4, opened once listed
  const mapFiles = {};     // finished map files by url, read once each

  // A missing file (before the collector runs, or with no game on) is no game,
  // not a failure: null.
  async function read(url) {
    const res = await fetch(url, { cache: "no-store" });
    const date = Date.parse(res.headers.get("Date"));
    if (!Number.isNaN(date)) skew = date - Date.now();
    if (res.status === 404 || res.status === 403) return null;
    if (!res.ok) throw new Error(res.status);
    return res.json();
  }

  async function poll() {
    clearTimeout(pollTimer);
    try {
      index = (await read(root.dataset.index)) || { matches: [] };
      matches = L.liveMatches(index, MAJORS);
      // Keep the chosen match while it's in progress; otherwise take the first.
      if (!matches.some((m) => m.id === matchId) && matches.length) selectMatch(matches[0].id, { quiet: true });
      const m = matches.find((x) => x.id === matchId);
      const url = m && L.safeUrl(m.url);
      const next = url ? await read(url) : null;
      if (!m || (next && next.match && next.match.id === matchId) || !next) state = next;
      failed = false;
      const listed = mapAsked && state && state.match && (state.match.maps || []).some((x) => x.number === mapAsked && L.safeUrl(x.url));
      if (listed) { const n = mapAsked; mapAsked = null; await pickMap(n); }
    } catch (e) {
      failed = true;
    }
    lastStrip = null;
    tick();
    if (!document.hidden) pollTimer = setTimeout(poll, failed ? RETRY_MS : matches.length ? POLL_MS : QUIET_MS);
  }
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) clearTimeout(pollTimer);
    else poll();
  });

  const now = () => Date.now() + skew;

  // ---- Matches ---------------------------------------------------------------
  // Choosing a match swaps the odds, scoreline and figure, and the stream to the
  // match's league (unless a co-stream is on: it may cover any league).
  function selectMatch(id, opts = {}) {
    const changed = id !== matchId;
    matchId = id;
    store.set("live.match", id);
    const url = new URL(location.href);
    url.searchParams.set("match", id);
    history.replaceState(null, "", url);
    if (changed) {
      state = null;
      cursor = null;
      lastKey = null;
      mapPick = null;
    }
    const m = matches.find((x) => x.id === id);
    if (m && (!stream || stream.group !== "Co-streams")) setStream(officialFor(m.league) || stream, false);
    if (changed && !opts.quiet) poll();
  }

  // ---- Streams ---------------------------------------------------------
  const pick = $("stream-pick");
  const frame = $("stream-frame");
  let stream = null;

  const officialFor = (league) => streams.find((s) => s.group !== "Co-streams" && (s.leagues || []).includes(league));
  // A co-stream the viewer chose stays on; otherwise the match's league's own.
  function streamFor(league) {
    const saved = streams.find((s) => s.key === store.get("live.stream"));
    if (saved && saved.group === "Co-streams") return saved;
    return officialFor(league) || saved || streams[0] || null;
  }

  function embedUrl(s) {
    if (s.youtube) return `https://www.youtube.com/embed/live_stream?channel=${encodeURIComponent(s.youtube)}&autoplay=1&mute=1`;
    if (s.twitch) return `https://player.twitch.tv/?channel=${encodeURIComponent(s.twitch)}&parent=${encodeURIComponent(location.hostname)}&autoplay=true&muted=true`;
    return null;
  }

  function setStream(s, remember) {
    if (!s || (stream && stream.key === s.key)) return;
    stream = s;
    if (remember) store.set("live.stream", s.key);
    if (pick) pick.value = s.key;
    const src = embedUrl(s);
    frame.replaceChildren(src
      ? h("iframe", { src, title: `${s.name}, live`, allow: "autoplay; fullscreen; picture-in-picture; encrypted-media", allowFullscreen: true, referrerPolicy: "strict-origin-when-cross-origin" })
      : h("p", { class: "plate-empty" }, "This stream can’t be embedded."));
  }

  // Choosing a league's own stream also brings up that league's match, if one
  // is in progress and the current match is from another league.
  if (pick) pick.addEventListener("change", () => {
    const s = streams.find((x) => x.key === pick.value);
    setStream(s, true);
    const leagues = s && s.group !== "Co-streams" ? s.leagues || [] : [];
    const cur = matches.find((m) => m.id === matchId);
    if (leagues.length && !(cur && leagues.includes(cur.league))) {
      const other = matches.find((m) => leagues.includes(m.league));
      if (other) selectMatch(other.id);
    }
  });

  const matchPick = $("match-pick");
  matchPick.addEventListener("change", () => selectMatch(matchPick.value));

  // ---- Fit and full screen ------------------------------------------------
  // On desktop the stream is sized so the stage and the odds beside it fit the
  // window without scrolling. Full screen shows only the stage; the control bar
  // and the odds float over the video on any movement, fading after IDLE_MS.
  const stage = $("stage");
  const stageOdds = $("stage-odds-body");
  const glass = $("stage-glass");
  const fullBtn = root.querySelector(".view-btn--full");
  const IDLE_MS = 3000;
  const isFull = () => document.fullscreenElement === stage;
  if (!stage.requestFullscreen) fullBtn.hidden = true;

  function fitStage() {
    const watch = root.querySelector(".live-watch");
    const top = watch.getBoundingClientRect().top + window.scrollY;
    const bar = $("stage-bar").offsetHeight;
    root.style.setProperty("--fit-h", `${Math.max(240, window.innerHeight - top - bar - 16)}px`);
  }
  function markFull() {
    fullBtn.setAttribute("aria-pressed", String(isFull()));
    fullBtn.title = isFull() ? "Exit full screen" : "Full screen";
    fullBtn.querySelector(".visually-hidden").textContent = fullBtn.title;
  }
  fullBtn.addEventListener("click", () =>
    (isFull() ? document.exitFullscreen() : stage.requestFullscreen()).catch(() => {}));

  let idleTimer;
  const keepAwake = () =>
    (stage.matches(":hover") && !glass.matches(":hover")) ||
    (document.activeElement && document.activeElement.tagName === "SELECT" && stage.contains(document.activeElement));
  function wake() {
    if (!isFull()) return;
    stage.classList.add("is-awake");
    clearTimeout(idleTimer);
    idleTimer = setTimeout(function sleep() {
      // Stay up while the pointer is on the bar or the odds, or a control has focus.
      if (keepAwake()) idleTimer = setTimeout(sleep, IDLE_MS);
      else stage.classList.remove("is-awake");
    }, IDLE_MS);
  }
  glass.addEventListener("pointermove", wake);
  glass.addEventListener("pointerdown", wake);
  stage.addEventListener("keydown", wake);
  document.addEventListener("fullscreenchange", () => {
    stage.classList.toggle("is-full", isFull());
    markFull();
    if (isFull()) { copyOdds(); wake(); } else stage.classList.remove("is-awake");
  });
  // The overlay shows a copy of the odds table, refreshed with it.
  function copyOdds() {
    if (!isFull()) return;
    const copy = root.querySelector(".live-reading").cloneNode(true);
    copy.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));
    copy.removeAttribute("aria-labelledby");
    stageOdds.replaceChildren(copy);
  }

  // ---- Teams ---------------------------------------------------------------
  // Team names link to their pages when the header search's index knows them.
  async function loadTeams() {
    if (teamSlugs) return;
    teamSlugs = new Map();
    try {
      const res = await fetch(root.dataset.teams);
      for (const t of await res.json()) teamSlugs.set(PrometheusNames.fold(t.n), t.s);
      lastKey = null;
      tick();
    } catch (e) { /* names stay plain */ }
  }
  function teamName(team, cls) {
    const name = (team && team.name) || "?";
    const slug = teamSlugs && teamSlugs.get(PrometheusNames.fold(name));
    return slug ? h("a", { href: `teams/${slug}.html`, class: cls || "" }, name) : h("span", { class: cls || "" }, name);
  }

  // ---- Rendering -------------------------------------------------------------
  const status = $("live-status");
  const gameEl = $("live-game");
  const idleEl = $("live-idle");
  const facts = $("live-facts");
  const ago = (ms) => {
    const s = Math.max(0, Math.round(ms / 1000));
    return s < 90 ? `${s} s ago` : `${Math.round(s / 60)} min ago`;
  };
  let lastKey = null;

  // ---- The match strip ------------------------------------------------------
  // Every match in progress, always in view, each with its clock, score and both
  // odds; the watched one shows its file's numbers, the others
  // the feed's latest. The same list fills the bar's Match select (full screen).
  const strip = $("match-strip");
  const list = $("match-list");
  let lastStrip = null;
  function chipNumbers(m) {
    const cur = state && state.match && state.match.id === m.id ? L.release(state, Infinity) : null;
    if (m.id === matchId && cur && cur.game) {
      const g = cur.game;
      const last = g.frames[g.frames.length - 1];
      const c = L.currentCall(g);
      return {
        clock: g.ended ? "Ended" : last ? L.clock(L.axis(g.frames).x(L.time(last.at))) : "—",
        p: c ? c.p : null,
        q: L.quoteAt(g.market, Infinity),
        score: cur.match.score,
        won: g.ended && (g.winner === 0 || g.winner === 1) ? `${L.short(cur.match.teams[g.winner])} won map ${g.number}` : null,
      };
    }
    const g = m.game || {};
    const c = L.summaryCall(g);
    return { clock: g.ended_at ? "Ended" : L.clock(g.clock) ?? "—", p: c ? c.p : null, q: g.market ? L.quoteAt([g.market], Infinity) : null, score: m.score };
  }
  function renderStrip() {
    strip.hidden = !matches.length;
    const nums = matches.map((m) => [m, chipNumbers(m)]);
    const key = JSON.stringify(nums.map(([m, n]) => [m.id, n.clock, n.p, n.q && n.q.mid, n.score, n.won])) + matchId;
    if (key === lastStrip) return;
    lastStrip = key;
    list.replaceChildren(...nums.map(([m, n]) => {
      const p = L.in100(n.p);
      const mid = n.q ? L.in100(n.q.mid) : null;
      const score = Array.isArray(n.score) ? `${n.score[0]}–${n.score[1]}` : "v";
      const a = h("a", { class: "match-chip", href: `watch.html?match=${encodeURIComponent(m.id)}` },
        h("span", { class: "chip-top" },
          h("span", { class: "league", "data-league": m.league }, h("span", { class: "league-mark", "aria-hidden": "true" }), m.league),
          h("span", { class: "chip-clock" }, n.clock)),
        h("span", { class: "chip-teams" }, L.short(m.teams[0]), " ", h("b", {}, score), " ", L.short(m.teams[1])),
        h("span", { class: "chip-bar fx-bar", style: `--p:${p ?? 50}` }, mid != null ? h("span", { class: "fx-mkt", style: `--m:${mid}` }) : null),
        h("span", { class: "chip-odds" }, n.won || `${p ?? "—"} ours · ${mid ?? "—"} Kalshi`));
      if (p == null) a.querySelector(".chip-bar").classList.add("is-empty");
      if (m.id === matchId) a.setAttribute("aria-current", "true");
      a.addEventListener("click", (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault();
        selectMatch(m.id);
      });
      return h("li", {}, a);
    }));
    matchPick.replaceChildren(...matches.map((m) =>
      h("option", { value: m.id, selected: m.id === matchId }, `${m.league} · ${L.short(m.teams[0])} v ${L.short(m.teams[1])}`)));
    fitStage();
  }

  // ---- Maps of the series ------------------------------------------------
  // Every map the match file lists: finished ones open their saved file (final
  // scoreline, our calls and Kalshi over the whole map); the current one is live.
  const mapsEl = $("live-maps");
  function mapEntry() {
    const maps = (state && state.match && state.match.maps) || [];
    return mapPick == null ? null : maps.find((m) => m.number === mapPick && L.safeUrl(m.url));
  }
  async function pickMap(number) {
    mapPick = number;
    const url = new URL(location.href);
    if (number == null) url.searchParams.delete("map"); else url.searchParams.set("map", number);
    history.replaceState(null, "", url);
    cursor = null;
    lastKey = null;
    const entry = mapEntry();
    if (entry && !mapFiles[entry.url]) {
      try { mapFiles[entry.url] = await read(L.safeUrl(entry.url)); } catch (e) { mapFiles[entry.url] = null; }
    }
    tick();
  }
  function renderMaps() {
    if (!mapsEl) return;
    const maps = (state && state.match && state.match.maps) || [];
    mapsEl.hidden = maps.length < 2;
    const teams = (state && state.match && state.match.teams) || [];
    mapsEl.replaceChildren(h("span", { class: "maps-label" }, "Maps"), ...maps.map((m) => {
      const on = m.current ? mapPick == null : mapPick === m.number;
      const won = m.winner === 0 || m.winner === 1 ? ` · ${L.short(teams[m.winner])}` : "";
      const b = h("button", { type: "button", class: `map-btn${on ? " is-on" : ""}`, "aria-pressed": String(on) }, `Map ${m.number}${m.current ? " · now" : won}`);
      b.addEventListener("click", () => pickMap(m.current ? null : m.number));
      return b;
    }));
  }

  // What the page shows: the current map, or a finished one with the series as it is now.
  function shown() {
    const entry = mapEntry();
    const past = entry && mapFiles[entry.url];
    if (!past) return { file: state, past: false };
    return { file: { ...past, match: { ...past.match, score: state.match.score, series: state.match.series, maps: state.match.maps } }, past: true };
  }

  function tick() {
    const match = state && state.match;
    const live = !!match && state.status !== "idle" && state.status !== "unavailable";
    // The stream plays with or without a game in the feed; without one, the odds
    // column says so, the scoreline and figure hide, and the next matches show.
    if (gameEl.hidden) { gameEl.hidden = false; root.classList.add("is-on"); fitStage(); }
    gameEl.classList.toggle("is-quiet", !live);
    facts.hidden = !live;
    idleEl.hidden = live;
    if (!stream) setStream(streamFor(live ? match.league : null), false);
    if (!live) {
      status.textContent = failed && !state
        ? "Feed unreachable."
        : (state && state.status === "unavailable" ? "Feed unavailable." : "");
      status.classList.toggle("is-stale", failed && !state);
      renderStrip();
      return;
    }
    loadTeams();
    const { file, past } = shown();
    // Every number shows as soon as it arrives.
    view = L.release(file, Infinity);
    setStatus(past);
    renderMaps();
    const g = view.game;
    const key = [state.published_at, g && g.frames.length, g && g.market.length, g && g.calls.length, g && g.ended, cursor, teamSlugs && teamSlugs.size, mapPick].join("|");
    renderStrip();
    if (key === lastKey) return;
    lastKey = key;
    renderFacts(view);
    fitStage();
    renderReading(view);
    drawFigure();
    renderBoard();
  }
  setInterval(() => { if (!document.hidden) tick(); }, 1000);

  function setStatus(past) {
    const age = now() - (L.time(state.published_at) || 0);
    const parts = [];
    if (past) {
      const g = view.game;
      status.textContent = "Final.";
      status.classList.remove("is-stale");
      return;
    }
    if (failed) parts.push("Feed unreachable.");
    if (state.status === "paused") parts.push("Paused.");
    if (state.status === "between_games") parts.push("Between maps.");
    parts.push(age > STALE_MS ? `Stalled: last update ${ago(age)}.` : `Updated ${ago(age)}.`);
    if (state.note) parts.push(state.note);
    status.textContent = parts.join(" ");
    status.classList.toggle("is-stale", failed || age > STALE_MS);
  }

  function renderFacts(v) {
    const m = v.match, g = v.game;
    const items = [
      h("span", { class: "league", "data-league": m.league }, h("span", { class: "league-mark", "aria-hidden": "true" }), m.event || m.league),
    ];
    if (g) items.push(h("span", {}, `Map ${g.number}`));
    if (g && (g.blue === 0 || g.blue === 1)) {
      const blue = m.teams[g.blue], red = m.teams[1 - g.blue];
      items.push(h("span", {}, teamName(blue), h("span", { class: "side" }, " blue"), ", ", teamName(red), h("span", { class: "side" }, " red")));
    }
    facts.replaceChildren(...items);
  }

  // One odds row: label, the first team's chance, the duel bar, the second's.
  function oddsRow(label, note, p, opts = {}) {
    const a = L.in100(p);
    const cells = a == null
      ? [h("td", { class: "num odds-p" }, h("span", { class: "muted" }, "—")),
         h("td", { class: "odds-bar-col", colspan: "2" }, h("span", { class: "odds-bar is-empty" })),
         h("td", { class: "num odds-p" }, h("span", { class: "muted" }, "—"))]
      : [h("td", { class: `num odds-p${a > 50 ? " fav" : ""}` }, String(a)),
         h("td", { class: "odds-bar-col", colspan: "2" }, h("span", { class: "odds-bar", style: `--p:${a}` })),
         h("td", { class: `num odds-p${a < 50 ? " fav" : ""}` }, String(100 - a))];
    // A market row links to the market on Kalshi when the state gives its page.
    const name = opts.href
      ? h("a", { class: "odds-name", href: opts.href, rel: "noopener", title: "This market on Kalshi" }, label)
      : h("span", { class: "odds-name" }, label);
    const head = h("th", { scope: "row" }, name, " ", h("span", { class: "odds-note" }, note));
    return h("tr", { class: opts.cls || "" }, head, ...cells);
  }

  function renderReading(v) {
    const m = v.match, g = v.game;
    $("odds-team-1").replaceChildren(teamName(m.teams[0]));
    $("odds-team-2").replaceChildren(teamName(m.teams[1]));
    // A finished map has no live odds: the result replaces them.
    const result = $("odds-result");
    const won = g && g.ended && (g.winner === 0 || g.winner === 1);
    const over = !!g && (won || (v.status === "between_games" && g.frames.length > 0));
    result.hidden = true;

    const calls = (g && g.calls) || [];
    const call = calls[calls.length - 1];
    const q = g && L.quoteAt(g.market, Infinity);
    const pre = (g && g.pregame) || {};
    const preQ = pre.market ? L.quoteAt([pre.market], Infinity) : null;
    const group = (title, rows) => [h("tr", { class: "odds-group" }, h("th", { scope: "rowgroup", colspan: "5" }, title)), ...rows];
    // The live group carries the estimated game time of the latest frame.
    const last = g && g.frames.length ? g.frames[g.frames.length - 1] : null;
    const at = last ? L.clock(L.axis(g.frames).x(L.time(last.at))) : null;
    // A finished map: its length and who won, in the odds' own columns.
    const final = () => {
      const side = (i) => h("td", { class: `num odds-p odds-final${won && g.winner === i ? " fav" : ""}` },
        won ? (g.winner === i ? "Won" : "Lost") : "");
      const row = won
        ? h("tr", { class: "odds-result-row" }, h("th", { scope: "row" }, h("span", { class: "odds-name" }, `Map ${g.number}`)),
            side(0), h("td", { class: "odds-bar-col", colspan: "2" }), side(1))
        : h("tr", { class: "odds-result-row" }, h("td", { colspan: "5", class: "odds-pending" }, "Result pending"));
      return group(at ? `Final · ${at}` : "Final", [row]);
    };
    $("odds").tBodies[0].replaceChildren(...(over ? final() : group(at ? `Live · ${at}` : "Live", [
      oddsRow("Ours", "", call && call.p, { cls: "odds-ours" }),
      oddsRow("Kalshi", "", q && q.mid, { href: g && g.market_url }),
    ])));
    $("odds").tBodies[1].replaceChildren(...group("Before the map", [
      oddsRow(pre.by || "FORGE", "", pre.p),
      oddsRow("Kalshi", "", preQ && preQ.mid, { href: g && g.market_url }),
    ]));
    // The series: our FORGE call and Kalshi's, under its score.
    const s = m.series || {};
    const sq = s.kalshi ? L.quoteAt([s.kalshi], Infinity) : null;
    const score = Array.isArray(m.score) ? ` ${m.score[0]}–${m.score[1]}` : "";
    $("odds").tBodies[2].replaceChildren(...group(`Series${score}`, [
      oddsRow(s.by || "FORGE", "", s.ours),
      oddsRow("Kalshi", "", sq && sq.mid, { href: s.kalshi_url }),
    ]));
    copyOdds();
  }

  // ---- Scoreline ---------------------------------------------------------
  const FIELDS = ["gold", "kills", "towers", "dragons", "barons", "inhibitors"];
  function renderBoard() {
    const g = view.game, m = view.match;
    const body = $("board").tBodies[0];
    const frames = g ? g.frames : [];
    const f = frames.length ? frames[cursor == null ? frames.length - 1 : Math.min(cursor, frames.length - 1)] : null;
    const when = $("board-when");
    if (!f) when.textContent = "Scoreline";
    else {
      const ax = L.axis(frames);
      const x = L.clock(ax.x(L.time(f.at)));
      when.textContent =
        ax.mode === "clock" ? `Scoreline at ${x}` : ax.mode === "estimated" ? `Estimated game time ${x}` : `Scoreline, ${x} in`;
    }
    const order = g && (g.blue === 0 || g.blue === 1) ? [g.blue, 1 - g.blue] : [0, 1];
    const rows = order.map((i, k) => {
      const t = (f && f.teams && f.teams[i]) || {};
      const o = (f && f.teams && f.teams[1 - i]) || {};
      const cells = FIELDS.map((key) => {
        const v = t[key];
        const shown = key === "gold" ? L.gold(v) : typeof v === "number" ? String(v) : null;
        const lead = typeof v === "number" && typeof o[key] === "number" && v > o[key];
        return h("td", { class: `num${lead ? " lead" : ""}${key === "inhibitors" ? " phone-hide" : ""}` }, shown ?? h("span", { class: "muted" }, "—"));
      });
      const side = g && (g.blue === 0 || g.blue === 1) ? (k === 0 ? "Blue" : "Red") : "—";
      return h("tr", {}, h("td", { class: "side-cell" }, side), h("th", { scope: "row" }, teamName(m.teams[i])), ...cells);
    });
    body.replaceChildren(...rows);
  }

  // ---- Figure 1 ------------------------------------------------------------
  const plot = $("chance-plot");
  const readout = $("chance-readout");

  function drawFigure() {
    const g = view.game, m = view.match;
    const team = m.teams[0].name;
    const frames = g ? g.frames : [];
    const ax = L.axis(frames);
    $("chance-caption").textContent = `${team}’s chance to win the map.`;
    const w = plot.clientWidth, hgt = plot.clientHeight;
    if (!w || !hgt) return;
    const padL = 34, padR = 14, padT = 16, padB = 20;
    const chanceBottom = Math.round(hgt * 0.68);
    const goldTop = chanceBottom + 30;
    const goldBottom = hgt - padB;
    const times = frames.map((f) => L.time(f.at));
    const xs = times.map((t) => ax.x(t));
    const lastX = xs.length ? xs[xs.length - 1] : 0;
    const span = Math.max(20 * 60, Math.ceil((lastX + 60) / 300) * 300);
    const x = (s) => padL + (Math.max(0, s) / span) * (w - padL - padR);
    const y = (p) => padT + (1 - p) * (chanceBottom - padT);
    const goldMax = Math.max(3000, ...frames.map((f) => Math.abs(goldGap(f) ?? 0)));
    const goldMid = (goldTop + goldBottom) / 2;
    const gy = (v) => goldMid - (v / goldMax) * ((goldBottom - goldTop) / 2);
    geom = { x, xs, padL, w };

    const svg = svgEl("svg", { viewBox: `0 0 ${w} ${hgt}`, "aria-hidden": "true", focusable: "false" });
    // Chance grid: 0, 25, 50 (dashed), 75, 100.
    for (const p of [0, 0.25, 0.5, 0.75, 1]) {
      const yy = Math.round(y(p)) + 0.5;
      svg.appendChild(svgEl("line", { class: p === 0.5 ? "base" : p === 0 ? "axis" : "grid", x1: padL, x2: w - padR, y1: yy, y2: yy }));
      if (p !== 0.25 && p !== 0.75) svg.appendChild(svgEl("text", { class: "label", x: padL - 6, y: yy + 4, "text-anchor": "end" }, String(100 * p)));
    }
    // Minute ticks every 5 (10 past 40 minutes), and the checkpoint minutes.
    // Minute ticks at 5, 10, 15 or 30 minutes, whichever gives eight or fewer.
    const every = [300, 600, 900, 1800].find((st) => span / st <= 8) || 3600;
    for (let s = 0; s <= span; s += every) {
      const xx = Math.round(x(s)) + 0.5;
      svg.appendChild(svgEl("line", { class: "axis", x1: xx, x2: xx, y1: chanceBottom, y2: chanceBottom + 4 }));
      svg.appendChild(svgEl("text", { class: "label", x: xx, y: chanceBottom + 15, "text-anchor": "middle" }, `${s / 60}′`));
    }
    if (ax.mode === "clock") {
      for (const minute of [10, 15, 20]) {
        const xx = Math.round(x(minute * 60)) + 0.5;
        svg.appendChild(svgEl("line", { class: "checkpoint", x1: xx, x2: xx, y1: padT, y2: chanceBottom }));
      }
    }

    // Gold lead: one column per frame, up when the first team is ahead.
    const zero = Math.round(goldMid) + 0.5;
    svg.appendChild(svgEl("line", { class: "grid", x1: padL, x2: w - padR, y1: zero, y2: zero }));
    const kLabel = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v / 1000).toFixed(0)}k`;
    svg.appendChild(svgEl("text", { class: "label", x: padL - 6, y: goldTop + 8, "text-anchor": "end" }, kLabel(goldMax)));
    svg.appendChild(svgEl("text", { class: "label", x: padL - 6, y: goldBottom, "text-anchor": "end" }, kLabel(-goldMax)));
    const colW = Math.max(1, Math.min(3, ((w - padL - padR) / Math.max(1, frames.length)) * 0.7));
    frames.forEach((f, i) => {
      const v = goldGap(f);
      if (v == null) return;
      const top = Math.min(gy(v), goldMid), bottom = Math.max(gy(v), goldMid);
      svg.appendChild(svgEl("rect", { class: "gold", x: (x(xs[i]) - colW / 2).toFixed(1), y: top.toFixed(1), width: colW.toFixed(1), height: Math.max(0.5, bottom - top).toFixed(1) }));
    });

    // Kalshi: the spread as a band and the middle as a stepped line, to now.
    const quotes = g ? g.market : [];
    const xNow = xs.length ? lastX : 0;
    let mid = "";
    quotes.forEach((q, i) => {
      const t = L.time(q.at);
      const x0 = ax.x(t);
      const x1 = i + 1 < quotes.length ? ax.x(L.time(quotes[i + 1].at)) : xNow;
      if (x0 == null || x1 == null || x1 < x0) return;
      const ok = L.quoteAt([q], Infinity);
      if (!ok) return;
      svg.appendChild(svgEl("rect", { class: "mkt-band", x: x(x0).toFixed(1), y: y(ok.ask).toFixed(1), width: Math.max(0.5, x(x1) - x(x0)).toFixed(1), height: Math.max(0.5, y(ok.bid) - y(ok.ask)).toFixed(1) }));
      mid += `${mid ? "L" : "M"}${x(x0).toFixed(1)},${y(ok.mid).toFixed(1)}H${x(x1).toFixed(1)}`;
    });
    if (mid) svg.appendChild(svgEl("path", { class: "mkt", d: mid }));

    // Our calls: pre-game at 0, then each checkpoint, held as a step until the next.
    const calls = [];
    if (g && g.pregame && L.in100(g.pregame.p) != null) calls.push({ s: 0, p: g.pregame.p, label: "pre" });
    for (const c of (g && g.calls) || []) {
      const s = ax.mode === "clock" ? c.minute * 60 : ax.x(L.time(c.at));
      if (s != null) calls.push({ s, p: c.p, label: `${c.minute}′` });
    }
    if (calls.length) {
      let d = "";
      calls.forEach((c, i) => {
        const x1 = i + 1 < calls.length ? calls[i + 1].s : Math.max(xNow, c.s);
        d += `${i ? "V" : "M"}${i ? y(c.p).toFixed(1) : `${x(c.s).toFixed(1)},${y(c.p).toFixed(1)}`}H${x(x1).toFixed(1)}`;
      });
      svg.appendChild(svgEl("path", { class: "ours", d }));
      // Points and labels only on the pre-game call and the latest one; the line
      // carries the rest, and tracing reads any moment.
      calls.forEach((c, i) => {
        if (i !== 0 && i !== calls.length - 1) return;
        const cx = x(c.s), cy = y(c.p);
        svg.appendChild(svgEl("circle", { class: i === 0 && c.label === "pre" ? "call call--pre" : "call", cx, cy, r: 3.5 }));
        const above = c.p < 0.85;
        svg.appendChild(svgEl("text", { class: "call-label", x: cx + 6, y: above ? cy - 10 : cy + 18, "text-anchor": "start" }, w < 520 && c.label !== "pre" ? String(L.in100(c.p)) : `${c.label} ${L.in100(c.p)}`));
      });
    }

    // Now: where the released game stands.
    if (xs.length) {
      const xx = Math.round(x(xNow)) + 0.5;
      svg.appendChild(svgEl("line", { class: "now", x1: xx, x2: xx, y1: padT - 6, y2: chanceBottom }));
      svg.appendChild(svgEl("line", { class: "now", x1: xx, x2: xx, y1: goldTop, y2: goldBottom }));
      svg.appendChild(svgEl("text", { class: "now-label", x: xx, y: padT - 8, "text-anchor": "middle" }, "now"));
    }

    // The traced frame.
    if (cursor != null && frames[cursor]) {
      const s = xs[cursor];
      const xx = Math.round(x(s)) + 0.5;
      svg.appendChild(svgEl("line", { class: "cursor", x1: xx, x2: xx, y1: padT, y2: goldBottom }));
      const q = L.quoteAt(quotes, times[cursor]);
      if (q) svg.appendChild(svgEl("circle", { class: "cursor-dot", cx: xx, cy: y(q.mid), r: 3 }));
    }
    plot.replaceChildren(svg);
    if (!frames.length) plot.appendChild(h("p", { class: "chance-empty" }, "Starts with the map."));
    plot.setAttribute("aria-label", figureLabel(team, calls, quotes));
    readTrace();
  }

  function goldGap(f) {
    const a = f && f.teams && f.teams[0] && f.teams[0].gold;
    const b = f && f.teams && f.teams[1] && f.teams[1].gold;
    return typeof a === "number" && typeof b === "number" ? a - b : null;
  }

  function figureLabel(team, calls, quotes) {
    const last = calls[calls.length - 1];
    const q = L.quoteAt(quotes, Infinity);
    return `${team}’s chance to win the map. ${last ? `Our latest call ${L.in100(last.p)} in 100.` : "No call yet."} ${q ? `Kalshi ${L.in100(q.mid)}.` : ""} Use the left and right arrow keys to read moments of the game.`;
  }

  function readTrace() {
    const g = view.game;
    plot.querySelectorAll(".chance-tip").forEach((el) => el.remove());
    if (cursor == null || !g || !g.frames[cursor]) { readout.textContent = ""; return; }
    const f = g.frames[cursor];
    const ax = L.axis(g.frames);
    const t = L.time(f.at);
    const q = L.quoteAt(g.market, t);
    const gap = goldGap(f);
    // Our call then: the newest made by that moment, else the pre-game one.
    const made = (g.calls || []).filter((c) => L.time(c.at) != null && L.time(c.at) <= t);
    const call = made.length ? made[made.length - 1] : g.pregame;
    const ours = call && L.in100(call.p) != null ? L.in100(call.p) : "—";
    const code = L.short(view.match.teams[0]);
    const lines = [
      L.clock(ax.x(t)),
      `Ours ${ours}`,
      `Kalshi ${q ? L.in100(q.mid) : "—"}`,
      gap == null ? null : `${code} ${gap >= 0 ? "+" : "−"}${L.gold(Math.abs(gap))} gold`,
    ].filter(Boolean);
    readout.textContent = lines.join(" · ");
    // The same reading beside the traced rule, flipped to its left near the edge.
    if (!geom) return;
    const cx = geom.x(geom.xs[cursor]);
    const tip = h("div", { class: "chance-tip", "aria-hidden": "true" },
      h("b", {}, lines[0]), ...lines.slice(1).map((l) => h("span", {}, l)));
    if (cx > geom.w - 150) tip.style.right = `${Math.round(geom.w - cx + 10)}px`;
    else tip.style.left = `${Math.round(cx + 10)}px`;
    plot.appendChild(tip);
  }

  function setCursor(i) {
    cursor = i;
    tick();
  }
  plot.addEventListener("pointermove", (e) => {
    if (!geom || !geom.xs.length) return;
    const mx = e.clientX - plot.getBoundingClientRect().left;
    let best = 0, bestD = Infinity;
    geom.xs.forEach((s, i) => {
      const d = Math.abs(geom.x(s) - mx);
      if (d < bestD) { bestD = d; best = i; }
    });
    if (best !== cursor) setCursor(best);
  });
  plot.addEventListener("pointerleave", () => setCursor(null));
  plot.addEventListener("blur", () => setCursor(null));
  plot.addEventListener("keydown", (e) => {
    const n = view && view.game ? view.game.frames.length : 0;
    if (!n) return;
    const step = e.shiftKey ? 30 : 6;
    let i = cursor == null ? n - 1 : cursor;
    if (e.key === "ArrowLeft") i = Math.max(0, i - step);
    else if (e.key === "ArrowRight") i = Math.min(n - 1, i + step);
    else if (e.key === "Home") i = 0;
    else if (e.key === "End") i = n - 1;
    else if (e.key === "Escape") { setCursor(null); return; }
    else return;
    e.preventDefault();
    setCursor(i);
  });

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { fitStage(); lastKey = null; tick(); }, 120);
  });

  markFull();
  poll();
})();
