// Fixture registers (Predictions page and home): set each match's time in the
// visitor's time zone and regroup the days by local date ("Today, Saturday
// 3 October"), mark upcoming matches that have already started, and, where the
// page has a filter line, filter by league and team with the state in the URL.
// Without JS the registers show every match in UTC, grouped by UTC date.
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const fold = PrometheusNames.fold;
  const tables = $$(".register--fixtures");
  if (!tables.length) return;

  const timeFormat = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
  const dayFormat = new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long" });
  const dayKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const now = new Date();
  const relative = { [dayKey(now)]: "Today" };
  relative[dayKey(new Date(now.getTime() + 864e5))] = "Tomorrow";
  relative[dayKey(new Date(now.getTime() - 864e5))] = "Yesterday";

  // ---- Local times and days -------------------------------------------------
  tables.forEach((table) => {
    $$(".fx-tz", table).forEach((el) => el.remove());
    const rows = $$("tr.fx", table);
    const cols = $(".fx-day-row th", table).colSpan;
    const upcoming = !table.classList.contains("register--results");
    $$("tbody.fx-day", table).forEach((tb) => tb.remove());
    let body = null;
    let key = null;
    rows.forEach((tr) => {
      const start = new Date(tr.dataset.start.replace("Z", ":00Z"));
      if (Number.isNaN(start.getTime())) return;
      const k = dayKey(start);
      if (k !== key) {
        key = k;
        body = document.createElement("tbody");
        body.className = "fx-day";
        body.dataset.day = k;
        const head = document.createElement("tr");
        head.className = "fx-day-row";
        const th = document.createElement("th");
        th.scope = "rowgroup";
        th.colSpan = cols;
        th.textContent = relative[k] ? `${relative[k]}, ${dayFormat.format(start)}` : dayFormat.format(start);
        head.appendChild(th);
        body.appendChild(head);
        table.appendChild(body);
      }
      const time = $("time", tr);
      if (time) time.textContent = timeFormat.format(start);
      if (upcoming && start <= now) {
        tr.classList.add("fx-started");
        time.title = "Started; the result comes with the next update";
      }
      body.appendChild(tr);
    });
  });

  // ---- Kalshi prices refreshed between builds ---------------------------------
  // An hourly job rewrites kalshi.json; apply it over the prices in the page
  // (the caret on the bar, the Kalshi pair and link, the tooltips), and say in
  // the upcoming register's caption when the prices were read.
  const stampFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
  const stamp = (iso) => stampFormat.format(new Date(iso.replace("Z", ":00Z")));
  // Results pages have no upcoming register, so nothing to refresh.
  const upcomingTables = tables.filter((t) => !t.classList.contains("register--results"));
  (upcomingTables.length ? fetch("kalshi.json", { cache: "no-store" }) : Promise.resolve(null))
    .then((r) => (r && r.ok ? r.json() : null))
    .then((data) => {
      if (!data || !data.matches) return;
      $$("tr.fx[data-match]").forEach((tr) => {
        const m = data.matches[tr.dataset.match];
        if (!m) return;
        const bar = $(".fx-bar", tr);
        if (bar) {
          let caret = $(".fx-mkt", bar);
          if (!caret) {
            caret = document.createElement("span");
            caret.className = "fx-mkt";
            bar.appendChild(caret);
          }
          caret.style.setProperty("--m", m.p1);
          const col = bar.parentElement;
          col.title = `${col.title.split("; Kalshi")[0]}; Kalshi ${m.p1}–${m.p2}, ${stamp(m.at)}`;
        }
        const cell = $(".fx-market", tr);
        if (cell) {
          const pair = `${m.p1}–${m.p2}`;
          cell.textContent = "";
          if (m.url) {
            const a = document.createElement("a");
            a.href = m.url;
            a.textContent = pair;
            a.setAttribute("aria-label", `Kalshi’s market: ${pair}`);
            cell.appendChild(a);
          } else {
            cell.textContent = pair;
          }
          cell.title = `As of ${stamp(m.at)}${m.url ? "; opens the match on Kalshi" : ""}`;
        }
      });
      tables
        .filter((t) => !t.classList.contains("register--results"))
        .forEach((t) => {
          const cap = $("figcaption", t.closest("figure") || document.createElement("div"));
          if (!cap) return;
          let note = $(".kalshi-asof", cap);
          if (!note) {
            note = document.createElement("span");
            note.className = "kalshi-asof";
            // Before a trailing link (home's "Every prediction"), else at the end.
            const link = $("a:not(.note-ref)", cap);
            cap.insertBefore(note, link);
            cap.insertBefore(document.createTextNode(" "), link ? link : note);
          }
          note.textContent = `Kalshi prices as of ${stamp(data.at)}.`;
        });
    })
    .catch(() => {});

  // ---- Filters (Predictions page) -------------------------------------------
  const line = $(".filter-line");
  if (!line) return;
  line.hidden = false;
  const picker = $(".picker", line);
  const search = $("#filter-search");
  const clearBtn = $(".clear-filters", line);
  const known = new Set($$("input[type=checkbox]", picker).map((cb) => cb.value));
  // With no leagues in the URL the registers show the major leagues and
  // international events; ?leagues=all shows every league.
  const shortcuts = $$(".picker-shortcut", picker);
  const majors = new Set((shortcuts[0]?.dataset.select || "").split(",").filter((l) => known.has(l)));
  const isMajors = (set) => set.size === majors.size && [...set].every((l) => majors.has(l));
  const state = { leagues: new Set(majors), search: "" };

  const params = new URLSearchParams(location.search);
  const asked = params.get("leagues");
  if (asked === "all") state.leagues.clear();
  else if (asked) state.leagues = new Set(asked.split(",").filter((l) => known.has(l)));
  state.search = params.get("search") || "";
  search.value = state.search;

  function writeUrl() {
    const q = new URLSearchParams();
    if (!state.leagues.size) q.set("leagues", "all");
    else if (!isMajors(state.leagues)) q.set("leagues", [...state.leagues].join(","));
    if (state.search.trim()) q.set("search", state.search.trim());
    const qs = q.toString();
    history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
  }

  function apply() {
    const query = fold(state.search.trim());
    tables.forEach((table) => {
      let shown = 0;
      const total = $$("tr.fx", table).length;
      $$("tbody.fx-day", table).forEach((tb) => {
        let any = false;
        $$("tr.fx", tb).forEach((tr) => {
          const ok = (!state.leagues.size || state.leagues.has(tr.dataset.league))
            && (!query || fold(tr.dataset.teams).includes(query));
          tr.hidden = !ok;
          if (ok) { any = true; shown += 1; }
        });
        tb.hidden = !any;
      });
      const which = table.id;
      const count = $(`[data-count-for="${which}"]`);
      if (count) count.textContent = shown === total ? `${total.toLocaleString()} shown.` : `${shown.toLocaleString()} of ${total.toLocaleString()} shown.`;
      const empty = $(`[data-empty-for="${which}"]`);
      if (empty) empty.hidden = shown > 0;
      // The last visible row closes the register with the heavy rule.
      $$("tr.fx-last", table).forEach((tr) => tr.classList.remove("fx-last"));
      const visible = $$("tr.fx:not([hidden])", table);
      if (visible.length) visible[visible.length - 1].classList.add("fx-last");
    });
    $$("input[type=checkbox]", picker).forEach((cb) => { cb.checked = state.leagues.has(cb.value); });
    const value = $(".picker-value", picker);
    const chosen = [...state.leagues];
    value.textContent = isMajors(state.leagues) ? value.dataset.majors
      : chosen.length ? (chosen.length > 3 ? `${chosen.length} selected` : chosen.join(", ")) : value.dataset.all;
    clearBtn.hidden = isMajors(state.leagues) && !state.search;
    writeUrl();
  }

  picker.addEventListener("change", (e) => {
    if (e.target.type !== "checkbox") return;
    if (e.target.checked) state.leagues.add(e.target.value);
    else state.leagues.delete(e.target.value);
    apply();
  });
  shortcuts.forEach((b) => b.addEventListener("click", (e) => {
    state.leagues = new Set(e.currentTarget.dataset.select.split(",").filter((l) => known.has(l)));
    apply();
  }));
  search.addEventListener("input", () => { state.search = search.value; apply(); });
  clearBtn.addEventListener("click", () => {
    state.leagues = new Set(majors);
    state.search = "";
    search.value = "";
    apply();
  });
  document.addEventListener("click", (e) => { if (picker.open && !picker.contains(e.target)) picker.open = false; });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && picker.open) { picker.open = false; $("summary", picker).focus(); }
  });

  apply();
})();
