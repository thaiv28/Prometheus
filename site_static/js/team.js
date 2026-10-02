// Team page: GLORY/Record switch for the season figure, and the Elo history figure drawn as SVG.
(function () {
  "use strict";

  const SVG = "http://www.w3.org/2000/svg";
  const el = (name, attrs, text) => {
    const node = document.createElementNS(SVG, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (text != null) node.textContent = text;
    return node;
  };

  // ---- Season figure ----------------------------------------------------
  const chart = document.getElementById("season-chart");
  const figMetric = document.querySelector(".season-fig-metric");
  if (chart) {
    document.addEventListener("change", (e) => {
      if (e.target.name !== "team-metric") return;
      chart.dataset.metric = e.target.value;
      if (figMetric) figMetric.textContent = e.target.closest("label").textContent.trim();
    });
  }

  // ---- Elo figure -------------------------------------------------------
  const plot = document.getElementById("elo-plot");
  if (!plot) return;
  let series = [];
  try { series = JSON.parse(document.getElementById("elo-series").textContent); } catch (e) { /* drawn empty */ }
  const readout = document.getElementById("elo-readout");
  if (!series.length) {
    plot.innerHTML = '<p class="chart-error">No Elo history is on record for this team.</p>';
    return;
  }

  const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  const points = series.map((d, i) => ({ i, t: Date.parse(d.date + "T00:00:00Z"), elo: d.elo, date: d.date }));
  const t0 = points[0].t;
  const t1 = Math.max(points[points.length - 1].t, t0 + 86400000);
  const lo = Math.min(1500, ...points.map((p) => p.elo));
  const hi = Math.max(1500, ...points.map((p) => p.elo));
  const yMin = Math.floor((lo - 20) / 50) * 50;
  const yMax = Math.ceil((hi + 20) / 50) * 50;
  const peak = points.reduce((a, b) => (b.elo > a.elo ? b : a));
  let cursor = null;
  let geom = null;

  function draw() {
    const w = plot.clientWidth;
    const h = plot.clientHeight - 6;
    if (!w) return;
    const padL = 40, padR = 8, padT = 18, padB = 22;
    const x = (t) => padL + ((t - t0) / (t1 - t0)) * (w - padL - padR);
    const y = (v) => padT + (1 - (v - yMin) / (yMax - yMin)) * (h - padT - padB);
    geom = { x, y, w, h, padT, padB };
    const svg = el("svg", { viewBox: `0 0 ${w} ${h}`, "aria-hidden": "true", focusable: "false" });

    const yStep = yMax - yMin > 400 ? 100 : 50;
    for (let v = Math.ceil(yMin / yStep) * yStep; v <= yMax; v += yStep) {
      const gy = Math.round(y(v)) + 0.5;
      svg.appendChild(el("line", { class: v === 1500 ? "base" : "grid", x1: padL, x2: w - padR, y1: gy, y2: gy }));
      svg.appendChild(el("text", { class: "label", x: padL - 6, y: gy + 4, "text-anchor": "end" }, String(v)));
    }
    svg.appendChild(el("line", { class: "axis", x1: padL, x2: w - padR, y1: h - padB + 0.5, y2: h - padB + 0.5 }));

    // Year ticks on 1 January.
    const y0 = new Date(t0).getUTCFullYear();
    const y1 = new Date(t1).getUTCFullYear();
    const span = y1 - y0 + 1;
    const every = w < 480 ? Math.ceil(span / 4) : span > 10 ? 2 : 1;
    for (let yr = y0 + 1; yr <= y1; yr++) {
      const tx = Math.round(x(Date.UTC(yr, 0, 1))) + 0.5;
      svg.appendChild(el("line", { class: "axis", x1: tx, x2: tx, y1: h - padB, y2: h - padB + 4 }));
      if ((yr - y0) % every === 0) svg.appendChild(el("text", { class: "label", x: tx, y: h - 4, "text-anchor": "middle" }, String(yr)));
    }
    if (span === 1 || y1 === y0) {
      svg.appendChild(el("text", { class: "label", x: padL, y: h - 4, "text-anchor": "start" }, String(y0)));
    }

    const d = points.map((p, k) => `${k ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.elo).toFixed(1)}`).join("");
    svg.appendChild(el("path", { class: "line", d }));

    const px = x(peak.t), py = y(peak.elo);
    svg.appendChild(el("circle", { class: "peak", cx: px, cy: py, r: 3 }));
    const right = px > w * 0.62;
    svg.appendChild(el("text", { class: "peak-label", x: px + (right ? -8 : 8), y: py - 6, "text-anchor": right ? "end" : "start" }, `peak ${Math.round(peak.elo)}`));

    if (cursor) {
      const cx = x(cursor.t), cy = y(cursor.elo);
      svg.appendChild(el("line", { class: "cursor", x1: cx, x2: cx, y1: padT - 6, y2: h - padB }));
      svg.appendChild(el("circle", { class: "cursor-dot", cx, cy, r: 3.5 }));
    }
    plot.replaceChildren(svg);
  }

  function setCursor(p) {
    cursor = p;
    readout.textContent = p ? `${dateFmt.format(new Date(p.t))}: Elo ${Math.round(p.elo)} after game ${p.i + 1} of ${points.length}` : "";
    draw();
  }

  function nearest(clientX) {
    const rect = plot.getBoundingClientRect();
    const mx = clientX - rect.left;
    let best = points[0], bestD = Infinity;
    for (const p of points) {
      const dd = Math.abs(geom.x(p.t) - mx);
      if (dd < bestD) { bestD = dd; best = p; }
    }
    return best;
  }

  plot.addEventListener("pointermove", (e) => { if (geom) setCursor(nearest(e.clientX)); });
  plot.addEventListener("pointerleave", () => setCursor(null));
  plot.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 10 : 1;
    let i = cursor ? cursor.i : points.length;
    if (e.key === "ArrowLeft") i = Math.max(0, i - step);
    else if (e.key === "ArrowRight") i = cursor ? Math.min(points.length - 1, i + step) : points.length - 1;
    else if (e.key === "Home") i = 0;
    else if (e.key === "End") i = points.length - 1;
    else if (e.key === "Escape") { setCursor(null); return; }
    else return;
    e.preventDefault();
    setCursor(points[i]);
  });
  plot.addEventListener("blur", () => setCursor(null));

  let timer;
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(draw, 120); });
  draw();
})();
