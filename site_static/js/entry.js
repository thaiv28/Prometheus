// Team and player pages: the game log. The page embeds its newest series
// (#games-data); "Show every series" fetches the rest from the page's JSON file.
// Shapes are documented in prometheus/gamelog.py.
(function () {
  "use strict";

  // ---- On this page: mark the section in view --------------------------
  const tocLinks = [...document.querySelectorAll(".entry-contents a[href^='#']")];
  const sections = [...new Set(tocLinks.map((a) => a.hash.slice(1)))].map((id) => document.getElementById(id)).filter(Boolean);
  if (sections.length && "IntersectionObserver" in window) {
    const visible = new Set();
    const mark = () => {
      const current = sections.find((s) => visible.has(s)) || null;
      for (const a of tocLinks) {
        if (current && a.hash === "#" + current.id) a.setAttribute("aria-current", "location");
        else a.removeAttribute("aria-current");
      }
    };
    // A section counts as in view while it crosses the band just under the top of the window.
    const observer = new IntersectionObserver((entries) => {
      for (const e of entries) (e.isIntersecting ? visible.add(e.target) : visible.delete(e.target));
      mark();
    }, { rootMargin: "-15% 0px -70% 0px" });
    sections.forEach((s) => observer.observe(s));
  }

  // ---- Game log ----------------------------------------------------------
  const holder = document.getElementById("games-data");
  const body = document.getElementById("games-rows");
  if (!holder || !body) return;
  let data;
  try { data = JSON.parse(holder.textContent); } catch (e) { return; }

  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
  const slugify = PrometheusNames.slugify;
  const isPlayer = data.kind === "player";
  const cols = isPlayer ? 9 : 8;
  const KALSHI = "https://kalshi.com/markets/kxlolgame/league-of-legends-game/";
  const METHOD = { F: "FORGE", E: "Elo", X: "Elo, across leagues" };
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const years = new Map((data.years || []).map((y) => [y[0], y]));

  const day = (d) => `${+d.slice(8, 10)} ${MONTHS[+d.slice(5, 7) - 1]}`;
  const minus = (s) => s.replace("-", "−");
  const signed = (v) => (v == null ? '<span class="muted">—</span>' : v > 0 ? `+${Math.round(v)}` : Math.round(v) === 0 ? "0" : minus(String(Math.round(v))));
  const length = (t) => `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
  const teamLink = (name) => `<a href="../teams/${esc(slugify(name))}.html">${esc(name)}</a>`;
  // Just the mark; the league's name is its tooltip and is read out.
  const leagueMark = (l) => `<span data-league="${esc(l)}" title="${esc(l)}"><span class="league-mark" aria-hidden="true"></span><span class="visually-hidden">${esc(l)}</span></span>`;

  function call(p, m) {
    if (p == null) return '<span class="muted">—</span>';
    // The JSON leaves out the method when it is FORGE.
    const how = METHOD[m || "F"];
    return m && m !== "F" ? `<i title="By ${how}">${p}</i>` : `<span title="By ${how}">${p}</span>`;
  }

  function kalshi(s) {
    if (s.k == null) return "";
    const label = `Kalshi’s last price before the series: ${s.k} in 100`;
    return s.kt ? `<a href="${KALSHI}${esc(s.kt.toLowerCase())}" title="${label}; opens the match on Kalshi">${s.k}</a>` : `<span title="${label}">${s.k}</span>`;
  }

  function result(won, score) {
    const mark = won === 1 ? '<b class="log-w">W</b>' : won === 0 ? '<span class="log-l">L</span>' : '<span class="log-l">D</span>';
    return score ? `${mark} <span class="log-score">${score}</span>` : mark;
  }

  function five(ro) {
    if (!ro || !ro.length) return "";
    // Each name carries its separator, so a lineup wraps after a dot and never
    // inside a name; the title keeps a name that is cut short readable.
    return '<span class="log-five">' + ro.map((i, k) => {
      const [name, slug] = data.players[i];
      const label = slug ? `<a href="../players/${esc(slug)}.html" title="${esc(name)}">${esc(name)}</a>` : `<span title="${esc(name)}">${esc(name)}</span>`;
      return `<span class="log-p">${label}${k < ro.length - 1 ? '<span class="log-sep" aria-hidden="true">·</span>' : ""}</span>`;
    }).join(" ") + "</span>";
  }

  const sameFive = (a, b) => a && b && a.length === b.length && a.every((x, i) => x === b[i]);
  const aura = (a) => (a == null ? "" : a > 0 ? `+${a.toFixed(1)}` : minus(a.toFixed(1)));

  // One series: a row of its own, then a row per game when it ran past one game.
  function seriesRows(s) {
    const won = s.w > s.x ? 1 : s.w < s.x ? 0 : null;
    const single = s.g.length === 1 && s.w + s.x === 1;
    const g0 = s.g[0];
    const opp = `<td class="team log-opp">${leagueMark(s.l)}<span class="log-vs">v</span> ${teamLink(s.o)}</td>`;
    const res = `<td class="log-result">${result(single ? g0.r : won, single ? "" : `${s.w}–${s.x}`)}</td>`;
    const sideNote = single ? ` title="${g0.s === "B" ? "Blue" : "Red"} side, ${length(g0.t)}"` : "";
    let head = `<tr class="log-series${single ? " log-single" : ""}"><td class="num year log-date"${sideNote}>${day(s.d)}</td>`;
    if (isPlayer) head += `<td class="team log-team">${teamLink(data.teams[s.tm])}</td>`;
    head += opp + res;
    if (isPlayer) {
      head += `<td class="log-champ">${single ? esc(g0.c || "") : ""}</td><td class="num log-aura">${single ? aura(g0.a) : ""}</td>`;
    } else {
      head += `<td class="num log-len">${single ? length(g0.t) : ""}</td>`;
    }
    head += `<td class="num log-call">${call(s.p, s.m)}</td><td class="num log-mkt">${kalshi(s)}</td>`;
    head += `<td class="num log-elo" title="${s.e != null ? `Elo ${s.e} after` : ""}">${signed(s.de)}</td>`;
    if (!isPlayer) head += `<td class="log-roster">${five(g0.ro)}</td>`;
    head += "</tr>";
    if (single) return head;

    return head + s.g.map((g, i) => {
      let row = `<tr class="log-game" title="${g.s === "B" ? "Blue" : "Red"} side, ${length(g.t)}"><td class="log-gameno">Game ${i + 1}</td>`;
      if (isPlayer) row += "<td></td>";
      row += `<td class="log-side">${g.s === "B" ? "Blue" : "Red"} side${isPlayer ? `, ${length(g.t)}` : ""}</td>`;
      row += `<td class="log-result">${result(g.r, "")}</td>`;
      if (isPlayer) row += `<td class="log-champ">${esc(g.c || "")}</td><td class="num log-aura">${aura(g.a)}</td>`;
      else row += `<td class="num log-len">${length(g.t)}</td>`;
      row += `<td class="num log-call">${call(g.p, g.m)}</td><td class="num log-mkt"></td>`;
      row += `<td class="num log-elo" title="${g.e != null ? `Elo ${g.e} after` : ""}">${signed(g.de)}</td>`;
      if (!isPlayer) row += `<td class="log-roster">${i > 0 && !sameFive(g.ro, g0.ro) ? five(g.ro) : ""}</td>`;
      return row + "</tr>";
    }).join("");
  }

  function yearRow(year) {
    const y = years.get(year);
    const rec = y ? `<span class="log-year-rec">${y[1]}–${y[2]} in series, ${y[3]}–${y[4]} in games</span>` : "";
    return `<tr class="log-year" id="games-${year}"><th scope="rowgroup" colspan="${cols}">${year}${rec}</th></tr>`;
  }

  function render(series) {
    let html = "";
    let year = null;
    for (const s of series) {
      const y = s.d.slice(0, 4);
      if (y !== year) { html += yearRow(y); year = y; }
      html += seriesRows(s);
    }
    body.innerHTML = html;
  }

  render(data.series);

  // ---- Every series, on request --------------------------------------
  const button = document.getElementById("games-all");
  const caption = document.getElementById("games-cap-count");
  const index = document.getElementById("games-years");
  let loading = null;

  function loadAll() {
    if (!data.src) return Promise.resolve();
    if (!loading) {
      if (button) { button.disabled = true; button.textContent = "Loading every series…"; }
      loading = fetch(data.src)
        .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then((full) => {
          data.players = full.players || data.players;
          data.teams = full.teams || data.teams;
          render(full.series);
          data.src = null;
          if (button) button.closest(".log-more").remove();
          if (caption) caption.textContent = caption.dataset.all;
        })
        .catch(() => {
          loading = null;
          if (button) { button.disabled = false; button.textContent = "Couldn’t load the games. Try again"; }
        });
    }
    return loading;
  }

  if (button) button.addEventListener("click", () => loadAll());
  if (index) {
    index.addEventListener("click", (e) => {
      const link = e.target.closest("a[href^='#games-']");
      if (!link || document.getElementById(link.hash.slice(1))) return;
      e.preventDefault();
      loadAll().then(() => {
        const target = document.getElementById(link.hash.slice(1));
        if (target) { history.replaceState(null, "", link.hash); target.scrollIntoView(); }
      });
    });
  }
})();
