// Header search: suggests teams and players as you type and goes to their page.
// The indexes (teams.json, players.json) are fetched on first focus. Without JS, or
// when nothing matches, the form submits to the team Elo register.
(function () {
  "use strict";

  const form = document.querySelector(".index-search");
  const input = form && form.querySelector("input");
  const list = form && form.querySelector(".index-search-results");
  if (!input || !list) return;

  const { fold, rank, esc, ROLES, leagueMark } = PrometheusNames;
  const root = form.dataset.root || "";
  const LIMIT = 8;

  let teams = null; // teams, then players: { n, s, l, d, kind, key, ... }
  let loading = null;
  let matches = [];
  let active = -1;

  function load() {
    if (!loading) {
      const get = (url) => (url ? fetch(url).then((r) => (r.ok ? r.json() : [])).catch(() => []) : Promise.resolve([]));
      loading = Promise.all([get(form.dataset.index), get(form.dataset.players)]).then(([t, p]) => {
        teams = [
          ...t.map((x) => ({ ...x, kind: "team", key: fold(x.n) })),
          ...p.map((x) => ({ ...x, kind: "player", key: fold(x.n) })),
        ];
      });
    }
    return loading;
  }

  // Ranked by PrometheusNames.rank; ties keep the index order: teams before
  // players, major leagues first, then the most recently active.
  const find = (query) => (teams ? rank(teams, query, LIMIT) : []);

  const href = (t) => `${root}${t.kind === "player" ? "players" : "teams"}/${encodeURIComponent(t.s)}.html`;
  const mark = (l) => leagueMark(l, true);
  // Teams: league and last year. Players: role and last team.
  const meta = (t) =>
    t.kind === "player"
      ? `${mark(t.l)} ${esc(ROLES[t.r] || t.r)}, ${esc(t.t)}`
      : `${mark(t.l)} ${esc(String(t.d).slice(0, 4))}`;

  function render() {
    if (!matches.length) {
      list.hidden = !input.value.trim() || !teams;
      list.innerHTML = list.hidden ? "" : `<li class="index-search-empty">No team or player named “${esc(input.value.trim())}”. Press Enter to search the team Elo register.</li>`;
    } else {
      list.hidden = false;
      list.innerHTML = matches
        .map((t, i) =>
          `<li role="option" id="team-opt-${i}" aria-selected="${i === active}">` +
          `<a href="${esc(href(t))}" tabindex="-1">` +
          `<span class="index-search-name">${esc(t.n)}</span>` +
          `<span class="index-search-meta">${meta(t)}</span>` +
          `</a></li>`)
        .join("");
    }
    input.setAttribute("aria-expanded", String(!list.hidden && matches.length > 0));
    if (active >= 0) input.setAttribute("aria-activedescendant", `team-opt-${active}`);
    else input.removeAttribute("aria-activedescendant");
  }

  function update() {
    matches = find(input.value);
    active = -1;
    render();
  }

  function close() {
    matches = [];
    active = -1;
    list.hidden = true;
    list.innerHTML = "";
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  input.addEventListener("focus", () => { load().then(() => { if (input.value.trim()) update(); }); });
  input.addEventListener("input", () => { load().then(update); });

  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!matches.length) return;
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      active = (active + step + matches.length + 1) % (matches.length + 1);
      if (active === matches.length) active = -1;
      render();
    } else if (e.key === "Escape") {
      if (!list.hidden) { e.preventDefault(); close(); }
    }
  });

  // Enter opens the highlighted team, or the best match; with no match the form
  // submits to the Elo register search.
  form.addEventListener("submit", (e) => {
    const pick = matches[active >= 0 ? active : 0];
    if (!pick) return;
    e.preventDefault();
    location.href = href(pick);
  });

  // Keep focus in the input while a suggestion is clicked.
  list.addEventListener("mousedown", (e) => e.preventDefault());
  input.addEventListener("blur", close);
})();
