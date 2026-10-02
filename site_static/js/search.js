// Header search: suggests teams as you type and goes to the team's page.
// The index (teams.json) is fetched on first focus. Without JS, or when nothing
// matches, the form submits to the Elo register, which lists every team.
(function () {
  "use strict";

  const form = document.querySelector(".index-search");
  const input = form && form.querySelector("input");
  const list = form && form.querySelector(".index-search-results");
  if (!input || !list) return;

  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
  const fold = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const root = form.dataset.root || "";
  const LIMIT = 8;

  let teams = null;
  let loading = null;
  let matches = [];
  let active = -1;

  function load() {
    if (!loading) {
      loading = fetch(form.dataset.index)
        .then((r) => (r.ok ? r.json() : []))
        .then((data) => { teams = data.map((t) => ({ ...t, key: fold(t.n) })); })
        .catch(() => { teams = []; });
    }
    return loading;
  }

  // The exact name, then names starting with the query, then a word in the name
  // starting with it, then anywhere. Ties keep the index order: major-league teams
  // first, then the most recently active.
  function find(query) {
    const q = fold(query.trim());
    if (!q || !teams) return [];
    const out = [];
    for (const t of teams) {
      const at = t.key.indexOf(q);
      if (at < 0) continue;
      const rank = t.key === q ? -1 : at === 0 ? 0 : /[\s.\-]/.test(t.key[at - 1]) ? 1 : 2;
      out.push([rank, out.length, t]);
    }
    return out.sort((a, b) => a[0] - b[0] || a[1] - b[1]).slice(0, LIMIT).map((x) => x[2]);
  }

  function render() {
    if (!matches.length) {
      list.hidden = !input.value.trim() || !teams;
      list.innerHTML = list.hidden ? "" : `<li class="index-search-empty">No team named “${esc(input.value.trim())}”. Press Enter to search the Elo register.</li>`;
    } else {
      list.hidden = false;
      list.innerHTML = matches
        .map((t, i) =>
          `<li role="option" id="team-opt-${i}" aria-selected="${i === active}">` +
          `<a href="${esc(root)}teams/${encodeURIComponent(t.s)}.html" tabindex="-1">` +
          `<span class="index-search-name">${esc(t.n)}</span>` +
          `<span class="index-search-meta"><span class="league" data-league="${esc(t.l)}"><span class="league-mark" aria-hidden="true"></span>${esc(t.l)}</span> ${esc(String(t.d).slice(0, 4))}</span>` +
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
    location.href = `${root}teams/${encodeURIComponent(pick.s)}.html`;
  });

  // Keep focus in the input while a suggestion is clicked.
  list.addEventListener("mousedown", (e) => e.preventDefault());
  input.addEventListener("blur", close);
})();
