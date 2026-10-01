// Rankings page: filters, sorting, URL state, and the top-ten rafters.
// Data and column config are embedded in the page as JSON by build_site.py.
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const readJSON = (id) => { try { return JSON.parse($(id).textContent); } catch (e) { return null; } };

  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);

  const rows = readJSON("#rows-data") || [];
  const config = readJSON("#page-config") || { columns: [] };
  const valueKey = config.valueKey;
  const valueCol = config.columns.find((c) => c.key === valueKey) || { digits: 2 };
  const isElo = valueKey === "elo";

  const state = {
    years: new Set(),
    leagues: new Set(),
    search: "",
    sort: { key: "rank", dir: "asc" },
  };

  const tbody = $("#rows");
  const rafters = $("#rafters");
  const countEl = $(".count");
  const clearBtn = $(".clear-filters");
  const searchInput = $("#team-search");
  const numberFormat = new Intl.NumberFormat("en-US");

  function formatNumber(v, col) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "—";
    const s = n.toFixed(col.digits ?? 2);
    if (!col.signed) return s;
    return n > 0 ? "+" + s : s.replace("-", "−");
  }

  // ---- URL state -------------------------------------------------------
  function readUrl() {
    const q = new URLSearchParams(location.search);
    (q.get("years") || "").split(",").filter(Boolean).forEach((y) => state.years.add(y));
    (q.get("leagues") || "").split(",").filter(Boolean).forEach((l) => state.leagues.add(l));
    state.search = q.get("search") || "";
    const sort = (q.get("sort") || "").split(":");
    if (config.columns.some((c) => c.key === sort[0])) {
      state.sort = { key: sort[0], dir: sort[1] === "desc" ? "desc" : "asc" };
    }
  }

  function writeUrl() {
    const q = new URLSearchParams();
    if (state.years.size) q.set("years", [...state.years].join(","));
    if (state.leagues.size) q.set("leagues", [...state.leagues].join(","));
    if (state.search) q.set("search", state.search);
    if (state.sort.key !== "rank" || state.sort.dir !== "asc") q.set("sort", state.sort.key + ":" + state.sort.dir);
    const qs = q.toString();
    history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
  }

  // ---- Data ------------------------------------------------------------
  function filtered() {
    const term = state.search.trim().toLowerCase();
    const out = rows.filter((r) =>
      (!state.years.size || state.years.has(String(r.year))) &&
      (!state.leagues.size || state.leagues.has(String(r.league))) &&
      (!term || String(r.teamname).toLowerCase().includes(term))
    );
    // Rank is position by the page's value within the current view, independent of the sort column.
    out.sort((a, b) => Number(b[valueKey]) - Number(a[valueKey]));
    return out.map((r, i) => ({ ...r, rank: i + 1 }));
  }

  function sorted(list) {
    const { key, dir } = state.sort;
    const sign = dir === "asc" ? 1 : -1;
    return list.slice().sort((a, b) => {
      let av = a[key], bv = b[key];
      if (typeof av === "string" || typeof bv === "string") {
        return sign * String(av).localeCompare(String(bv), undefined, { sensitivity: "base", numeric: true });
      }
      return sign * ((av ?? -Infinity) - (bv ?? -Infinity)) || a.rank - b.rank;
    });
  }

  // ---- Rendering -------------------------------------------------------
  function cell(r, col) {
    const html = cellHtml(r, col);
    if (col.wideOnly) return html.replace("<td", "<td data-wide-only");
    if (col.phoneHide) return html.replace("<td", "<td data-phone-hide");
    return html;
  }

  // On narrow screens the league and year columns hide; they reappear under the team name.
  function teamMeta(r) {
    // Metric pages cover four leagues with distinct hues, so the swatch alone identifies the league there.
    const code = isElo ? esc(r.league) : `<span class="visually-hidden">${esc(r.league)}</span>`;
    const league = `<span class="league-tag" data-league="${esc(r.league)}">${code}</span>`;
    return `<span class="team-meta">${league}${isElo ? "" : `<span>${esc(r.year)}</span>`}</span>`;
  }

  function cellHtml(r, col) {
    switch (col.type) {
      case "rank":
        return `<td class="rank">${r.rank}</td>`;
      case "team":
        return `<td class="team"><div class="team-line"><a href="teams/${encodeURIComponent(r.slug)}.html">${esc(r.teamname)}</a>${teamMeta(r)}</div></td>`;
      case "number":
        return `<td class="num${col.key === valueKey ? " value" : ""}">${formatNumber(r[col.key], col)}</td>`;
      case "league":
        return `<td><span class="league-tag" data-league="${esc(r.league)}">${esc(r.league)}</span></td>`;
      default:
        return `<td class="muted">${esc(r[col.key])}</td>`;
    }
  }

  function renderTable(list) {
    if (!list.length) {
      tbody.innerHTML = `<tr><td class="empty" colspan="${config.columns.length}">No teams match these filters. <button type="button" class="clear-filters" data-clear>Clear filters</button></td></tr>`;
      return;
    }
    tbody.innerHTML = sorted(list)
      .map((r) => `<tr>${config.columns.map((c) => cell(r, c)).join("")}</tr>`)
      .join("");
  }

  let lastTopKey = null;
  function renderRafters(list) {
    const top = list.slice(0, 10);
    const key = top.map((r) => r.slug + r.year).join("|");
    if (key === lastTopKey) return;
    const firstRender = lastTopKey === null;
    lastTopKey = key;

    rafters.innerHTML = top.map((r, i) => {
      const value = Number(r[valueKey]);
      const meta = isElo ? r.league : `${r.year} · ${r.league}`;
      const label = `#${r.rank} ${r.teamname}, ${meta}, ${valueCol.label} ${formatNumber(value, valueCol)}`;
      return `<li class="banner" data-league="${esc(r.league)}" style="--i:${i}">
        <a class="banner-link" href="teams/${encodeURIComponent(r.slug)}.html" aria-label="${esc(label)}">
          <span class="banner-felt"><span class="banner-numeral">${r.rank}</span></span>
          <span class="banner-caption">
            <span class="banner-title">${esc(r.teamname)}</span>
            <span class="banner-meta">${esc(meta)}</span>
            <span class="banner-value">${formatNumber(value, valueCol)}</span>
          </span>
        </a></li>`;
    }).join("");

    if (!firstRender) {
      rafters.classList.remove("is-rehanging");
      void rafters.offsetWidth; // restart the animation
      rafters.classList.add("is-rehanging");
    }
  }

  function renderControls(count) {
    $$(".picker").forEach((picker) => {
      const set = state[picker.dataset.filter];
      $$("input[type=checkbox]", picker).forEach((cb) => { cb.checked = set.has(cb.value); });
      const valueEl = $(".picker-value", picker);
      const values = [...set].sort((a, b) => (picker.dataset.filter === "years" ? b - a : a.localeCompare(b)));
      valueEl.textContent = values.length ? (values.length > 3 ? `${values.length} selected` : values.join(", ")) : valueEl.dataset.all;
    });
    $$("th[data-key]").forEach((th) => {
      const active = th.dataset.key === state.sort.key;
      th.setAttribute("aria-sort", active ? (state.sort.dir === "asc" ? "ascending" : "descending") : "none");
    });
    const anyFilter = state.years.size || state.leagues.size || state.search;
    clearBtn.hidden = !anyFilter;
    const noun = isElo ? "teams" : "team-seasons";
    countEl.textContent = count === rows.length
      ? `${numberFormat.format(rows.length)} ${noun}`
      : `${numberFormat.format(count)} of ${numberFormat.format(rows.length)} ${noun}`;
  }

  function update() {
    const list = filtered();
    renderTable(list);
    renderRafters(list);
    renderControls(list.length);
    writeUrl();
  }

  function clearFilters() {
    state.years.clear();
    state.leagues.clear();
    state.search = "";
    if (searchInput) searchInput.value = "";
    update();
  }

  // ---- Events ----------------------------------------------------------
  document.addEventListener("change", (e) => {
    const picker = e.target.closest(".picker");
    if (!picker || e.target.type !== "checkbox") return;
    const set = state[picker.dataset.filter];
    e.target.checked ? set.add(e.target.value) : set.delete(e.target.value);
    update();
  });

  document.addEventListener("click", (e) => {
    const shortcut = e.target.closest(".picker-shortcut");
    if (shortcut) {
      state.leagues = new Set(shortcut.dataset.select.split(","));
      update();
      return;
    }
    if (e.target.closest(".clear-filters")) { clearFilters(); return; }

    const th = e.target.closest("th[data-key]");
    if (th) {
      const key = th.dataset.key;
      if (state.sort.key === key) {
        state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
      } else {
        // Text columns start A→Z; rank starts at #1; numbers start highest first.
        const type = th.dataset.type;
        state.sort = { key, dir: type === "number" || type === "date" ? "desc" : "asc" };
      }
      update();
      return;
    }

    // Close open pickers when clicking elsewhere.
    $$(".picker[open]").forEach((p) => { if (!p.contains(e.target)) p.open = false; });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const open = $(".picker[open]");
    if (open) { open.open = false; $("summary", open).focus(); }
  });

  $$(".picker").forEach((p) => p.addEventListener("toggle", () => {
    if (p.open) $$(".picker[open]").forEach((o) => { if (o !== p) o.open = false; });
  }));

  if (searchInput) {
    searchInput.form.addEventListener("submit", (e) => e.preventDefault());
    searchInput.addEventListener("input", () => { state.search = searchInput.value; update(); });
  }

  readUrl();
  if (searchInput) searchInput.value = state.search;
  update();
})();
