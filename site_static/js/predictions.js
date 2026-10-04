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

  // ---- Filters (Predictions page) -------------------------------------------
  const line = $(".filter-line");
  if (!line) return;
  line.hidden = false;
  const picker = $(".picker", line);
  const search = $("#filter-search");
  const clearBtn = $(".clear-filters", line);
  const known = new Set($$("input[type=checkbox]", picker).map((cb) => cb.value));
  const state = { leagues: new Set(), search: "" };

  const params = new URLSearchParams(location.search);
  (params.get("leagues") || "").split(",").filter((l) => known.has(l)).forEach((l) => state.leagues.add(l));
  state.search = params.get("search") || "";
  search.value = state.search;

  function writeUrl() {
    const q = new URLSearchParams();
    if (state.leagues.size) q.set("leagues", [...state.leagues].join(","));
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
    value.textContent = chosen.length ? (chosen.length > 3 ? `${chosen.length} selected` : chosen.join(", ")) : value.dataset.all;
    clearBtn.hidden = !(state.leagues.size || state.search);
    writeUrl();
  }

  picker.addEventListener("change", (e) => {
    if (e.target.type !== "checkbox") return;
    if (e.target.checked) state.leagues.add(e.target.value);
    else state.leagues.delete(e.target.value);
    apply();
  });
  $(".picker-shortcut", picker).addEventListener("click", (e) => {
    state.leagues = new Set(e.currentTarget.dataset.select.split(",").filter((l) => known.has(l)));
    apply();
  });
  search.addEventListener("input", () => { state.search = search.value; apply(); });
  clearBtn.addEventListener("click", () => {
    state.leagues.clear();
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
