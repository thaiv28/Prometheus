// Rankings page: filters, sorting, URL state, the distribution figure,
// and the in-place re-rank. Data and column config are embedded as JSON by build_site.py.
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const readJSON = (id) => { try { return JSON.parse($(id).textContent); } catch (e) { return null; } };

  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
  const SVG = "http://www.w3.org/2000/svg";

  const rows = readJSON("#rows-data") || [];
  const config = readJSON("#page-config") || { columns: [] };
  const valueKey = config.valueKey;
  const valueCol = config.columns.find((c) => c.key === valueKey) || { digits: 2, label: "Score" };
  // Rating pages (Elo, GlorELO+) list teams on the Elo scale; the others list team-seasons scored 0-100.
  const isRating = config.kind === "rating";
  const noun = isRating ? "teams" : "team-seasons";
  const metricName = (document.querySelector("h1")?.firstChild?.textContent || "").trim();
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const totalCols = config.columns.length + config.columns.filter((c) => c.bar).length;

  // A fixed value domain for bars and the figure, so filtered views keep their place on the scale.
  const allValues = rows.map((r) => Number(r[valueKey])).filter(Number.isFinite);
  const dataMin = Math.min(...allValues);
  const dataMax = Math.max(...allValues);
  const domain = isRating
    ? [Math.floor(dataMin / 100) * 100, Math.ceil(dataMax / 100) * 100]
    : [Math.min(0, Math.floor(dataMin / 10) * 10), Math.max(100, Math.ceil(dataMax / 10) * 10)];
  const scale = (v) => Math.max(0, Math.min(100, ((v - domain[0]) / (domain[1] - domain[0])) * 100));

  const state = { years: new Set(), leagues: new Set(), search: "", sort: { key: "rank", dir: "asc" } };

  const tbody = $("#rows");
  const countEl = $(".count");
  const descEl = $("#table-desc");
  const clearBtn = $(".clear-filters");
  const searchInput = $("#team-search");
  const distEl = $("#dist");
  const numberFormat = new Intl.NumberFormat("en-US");
  const rowKey = (r) => `${r.slug}|${isRating ? r.league : r.year}`;

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
      const av = a[key], bv = b[key];
      if (typeof av === "string" || typeof bv === "string") {
        return sign * String(av).localeCompare(String(bv), undefined, { sensitivity: "base", numeric: true }) || a.rank - b.rank;
      }
      return sign * ((av ?? -Infinity) - (bv ?? -Infinity)) || a.rank - b.rank;
    });
  }

  // ---- Table -----------------------------------------------------------
  const leagueMark = (code, showCode) =>
    `<span class="league" data-league="${esc(code)}"><span class="league-mark" aria-hidden="true"></span>${showCode ? esc(code) : `<span class="visually-hidden">${esc(code)}</span>`}</span>`;

  // On narrow screens the league and year columns hide; they reappear under the team name.
  function teamMeta(r) {
    return isRating
      ? `<span class="team-meta">${leagueMark(r.league, true)}</span>`
      : `<span class="team-meta">${leagueMark(r.league, false)}<span>${esc(r.year)}</span></span>`;
  }

  function cellHtml(r, col) {
    const cls = col.wideOnly ? " wide-only" : col.phoneHide ? " phone-hide" : "";
    switch (col.type) {
      case "rank":
        return `<td class="num rank">${r.rank}</td>`;
      case "team":
        return `<td class="team"><a href="teams/${encodeURIComponent(r.slug)}.html">${esc(r.teamname)}</a>${teamMeta(r)}</td>`;
      case "number": {
        const bar = col.bar
          ? `<td class="bar-col" aria-hidden="true"><span class="bar" style="--v:${scale(Number(r[col.key])).toFixed(1)}"></span></td>`
          : "";
        return `${bar}<td class="num${col.key === valueKey ? " value" : ""}${cls}">${formatNumber(r[col.key], col)}</td>`;
      }
      case "league":
        return `<td class="${cls.trim()}">${leagueMark(r.league, true)}</td>`;
      case "date":
        return `<td class="num year${cls}">${esc(r[col.key])}</td>`;
      default:
        return `<td class="num year${cls}">${esc(r[col.key])}</td>`;
    }
  }

  function renderTable(list) {
    if (!list.length) {
      tbody.innerHTML = `<tr><td class="empty" colspan="${totalCols}">No ${noun} match these filters. <button type="button" class="clear-filters" data-clear>Clear filters</button></td></tr>`;
      return;
    }
    tbody.innerHTML = sorted(list)
      .map((r) => `<tr data-key="${esc(rowKey(r))}" data-value="${esc(r[valueKey])}">${config.columns.map((c) => cellHtml(r, c)).join("")}</tr>`)
      .join("");
  }

  // ---- Signature motion: rows keep their identity and slide to their new place.
  function snapshot() {
    const pos = new Map();
    const vh = window.innerHeight;
    for (const tr of tbody.rows) {
      const top = tr.getBoundingClientRect().top;
      if (top > vh + 40) break;
      if (top > -40 && tr.dataset.key) pos.set(tr.dataset.key, top);
    }
    return pos;
  }

  function slide(before) {
    if (!before || !before.size || reduceMotion.matches) return;
    const vh = window.innerHeight;
    // Read every position first, then write, so the browser lays out once.
    const moves = [];
    for (const tr of tbody.rows) {
      const top = tr.getBoundingClientRect().top;
      if (top > vh + 40 || moves.length > 80) break;
      const old = before.get(tr.dataset.key);
      if (old !== undefined && Math.abs(old - top) >= 1) moves.push([tr, Math.max(-vh, Math.min(vh, old - top))]);
    }
    if (!moves.length) return;
    moves.forEach(([tr, dy]) => { tr.style.transform = `translateY(${dy}px)`; });
    requestAnimationFrame(() => requestAnimationFrame(() => {
      moves.forEach(([tr]) => {
        tr.classList.add("is-moving");
        tr.style.transform = "";
        tr.addEventListener("transitionend", () => tr.classList.remove("is-moving"), { once: true });
      });
    }));
  }

  // ---- Distribution figure --------------------------------------------
  let distState = { list: [], traced: null };

  function niceStep(span) {
    const raw = span / 6;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    return [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  }

  function el(name, attrs, text) {
    const node = document.createElementNS(SVG, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (text != null) node.textContent = text;
    return node;
  }

  function drawDist() {
    if (!distEl) return;
    const list = distState.list;
    const w = distEl.clientWidth;
    const h = distEl.clientHeight;
    if (!w) return;
    const top = 16, base = h - 20;
    const x = (v) => (scale(v) / 100) * w;
    const svg = el("svg", { viewBox: `0 0 ${w} ${h}`, "aria-hidden": "true", focusable: "false" });

    const bins = Math.max(20, Math.min(90, Math.round(w / 9)));
    const counts = new Array(bins).fill(0);
    const vals = list.map((r) => Number(r[valueKey])).filter(Number.isFinite);
    vals.forEach((v) => { counts[Math.min(bins - 1, Math.floor((scale(v) / 100) * bins))]++; });
    const maxCount = Math.max(1, ...counts);
    const bw = w / bins;
    counts.forEach((c, i) => {
      if (!c) return;
      const bh = Math.max(1, ((base - top) * c) / maxCount);
      svg.appendChild(el("rect", { x: (i * bw + 0.5).toFixed(1), y: (base - bh).toFixed(1), width: Math.max(1, bw - 1.5).toFixed(1), height: bh.toFixed(1), fill: "var(--ink-2)" }));
    });

    svg.appendChild(el("line", { class: "axis", x1: 0, x2: w, y1: base + 0.5, y2: base + 0.5 }));
    const step = niceStep(domain[1] - domain[0]);
    for (let t = Math.ceil(domain[0] / step) * step; t <= domain[1] + 1e-9; t += step) {
      const tx = x(t);
      svg.appendChild(el("line", { class: "axis", x1: tx, x2: tx, y1: base, y2: base + 4 }));
      const anchor = tx < 12 ? "start" : tx > w - 12 ? "end" : "middle";
      svg.appendChild(el("text", { class: "axis-label", x: tx, y: h - 2, "text-anchor": anchor }, String(Math.round(t * 10) / 10)));
    }

    if (vals.length) {
      const sortedVals = vals.slice().sort((a, b) => a - b);
      const mid = sortedVals.length / 2;
      const median = sortedVals.length % 2 ? sortedVals[Math.floor(mid)] : (sortedVals[mid - 1] + sortedVals[mid]) / 2;
      const mx = x(median);
      svg.appendChild(el("line", { class: "median", x1: mx, x2: mx, y1: top - 4, y2: base }));
      const label = `median ${median.toFixed(isRating ? 0 : 1)}`;
      svg.appendChild(el("text", { class: "median-label", x: mx + (mx > w - 110 ? -5 : 5), y: top - 5, "text-anchor": mx > w - 110 ? "end" : "start" }, label));
    }

    const t = distState.traced;
    if (t) {
      const tx = x(t.value);
      svg.appendChild(el("line", { class: "trace", x1: tx, x2: tx, y1: top - 6, y2: base + 4 }));
      const right = tx > w * 0.6;
      svg.appendChild(el("text", { class: "trace-label", x: tx + (right ? -6 : 6), y: base - 6, "text-anchor": right ? "end" : "start" }, t.label));
    }
    distEl.replaceChildren(svg);
  }

  function trace(tr) {
    $$("tr.is-traced", tbody).forEach((r) => r.classList.remove("is-traced"));
    if (!tr || !tr.dataset.key) { distState.traced = null; drawDist(); return; }
    tr.classList.add("is-traced");
    const name = tr.querySelector("td.team a")?.textContent || "";
    const value = Number(tr.dataset.value);
    distState.traced = { value, label: `${name} ${formatNumber(value, valueCol)}` };
    drawDist();
  }

  // ---- Caption and controls -------------------------------------------
  function describeYears(set) {
    const ys = [...set].map(Number).sort((a, b) => a - b);
    if (!ys.length) return "";
    const contiguous = ys.every((y, i) => i === 0 || y === ys[i - 1] + 1);
    if (ys.length === 1) return String(ys[0]);
    if (contiguous) return `${ys[0]}–${ys[ys.length - 1]}`;
    return ys.length > 4 ? `${ys.length} selected years` : ys.join(", ");
  }

  function describeView() {
    const leagues = [...state.leagues].sort();
    const leaguePart = !leagues.length ? "all" : leagues.length > 4 ? `${leagues.length} leagues’` : leagues.join(", ");
    let s = `${metricName}, ${leaguePart} ${noun}`;
    const years = describeYears(state.years);
    if (years) s += isRating ? ` last active in ${years}` : `, ${years}`;
    if (state.search.trim()) s += `, names containing “${state.search.trim()}”`;
    return s;
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
    clearBtn.hidden = !(state.years.size || state.leagues.size || state.search);
    descEl.textContent = describeView();
    countEl.textContent = count === rows.length
      ? `${numberFormat.format(rows.length)} shown.`
      : `${numberFormat.format(count)} of ${numberFormat.format(rows.length)} shown.`;
  }

  let started = false;
  function update() {
    const before = started ? snapshot() : null;
    const list = filtered();
    renderTable(list);
    slide(before);
    distState = { list, traced: null };
    drawDist();
    renderControls(list.length);
    writeUrl();
    started = true;
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
        // Text columns start A to Z; rank starts at 1; numbers and dates start highest first.
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

  tbody.addEventListener("mouseover", (e) => {
    const tr = e.target.closest("tr");
    if (tr && !tr.classList.contains("is-traced")) trace(tr);
  });
  tbody.addEventListener("mouseleave", () => trace(null));
  tbody.addEventListener("focusin", (e) => trace(e.target.closest("tr")));
  tbody.addEventListener("focusout", (e) => { if (!tbody.contains(e.relatedTarget)) trace(null); });

  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawDist, 120); });

  if (searchInput) {
    searchInput.form.addEventListener("submit", (e) => e.preventDefault());
    searchInput.addEventListener("input", () => { state.search = searchInput.value; update(); });
  }

  readUrl();
  if (searchInput) searchInput.value = state.search;
  update();
})();
