// Live results series pages (live-results/<match>.html): each map's figure,
// drawn at the column's full width as Figure 1 on the watch page, and read at
// any moment. The build's SVG (fixed width) stays for readers without JS; this
// redraws it at the real size (and again on resize) from the figure's series
// in game seconds (data-trace, written by prometheus/site/live_results.py).
// Pointer or arrow keys (Shift for 5 minutes) move a ledger-blue rule; beside it
// the game time, our call, Kalshi and the gold lead then, also read aloud from
// a hidden live region.
(function () {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  // The value held at s by a step series of [seconds, value] (null before it starts).
  const at = (pts, s) => {
    let v = null;
    for (const [t, x] of pts) {
      if (t <= s) v = x;
      else break;
    }
    return v;
  };
  const nearest = (pts, s) => {
    let best = null, gap = Infinity;
    for (const p of pts) {
      const d = Math.abs(p[0] - s);
      if (d < gap) { gap = d; best = p; }
    }
    return best && gap <= 45 ? best[1] : null;
  };
  const clock = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  const in100 = (p) => (p == null ? "—" : String(Math.round(100 * p)));
  const gold = (g) => `${g >= 0 ? "+" : "−"}${(Math.abs(g) / 1000).toFixed(1)}k`;
  const el = (tag, attrs, text) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (text != null) e.textContent = text;
    return e;
  };

  // The figure's geometry at a width in CSS pixels.
  function layout(d, w) {
    const padL = 34, padR = 10, top = 10;
    const chanceH = w < 600 ? 170 : 260;
    const bottom = top + chanceH;
    const goldTop = bottom + 12, goldBottom = goldTop + (w < 600 ? 34 : 48);
    const x = (s) => padL + ((w - padL - padR) * Math.min(s, d.span)) / d.span;
    const y = (p) => bottom - chanceH * p;
    return { w, h: goldBottom + 22, padL, padR, top, bottom, goldTop, goldBottom, x, y };
  }

  // A step line through [seconds, value] points, held to the end; a null value
  // (a quote too thin to call a price) leaves a gap.
  function stepPath(pts, g, span) {
    let path = "";
    let open = false;
    pts.forEach(([s, v], i) => {
      const end = i + 1 < pts.length ? pts[i + 1][0] : Math.max(span, s);
      if (v == null) { open = false; return; }
      path += open ? `V${g.y(v).toFixed(1)}` : `M${g.x(s).toFixed(1)},${g.y(v).toFixed(1)}`;
      path += `H${g.x(end).toFixed(1)}`;
      open = true;
    });
    return path;
  }

  function draw(d, g) {
    const svg = el("svg", { class: "lr-plot", viewBox: `0 0 ${g.w} ${g.h}`, width: g.w, height: g.h, tabindex: "0", role: "img" });
    const line = (cls, x1, x2, y1, y2) => svg.appendChild(el("line", { class: cls, x1, x2, y1, y2 }));
    const label = (x, y, anchor, text) => svg.appendChild(el("text", { class: "label", x, y, "text-anchor": anchor }, text));
    line("grid", g.padL, g.w - g.padR, g.top, g.top);
    line("base", g.padL, g.w - g.padR, g.y(0.5), g.y(0.5));
    line("axis", g.padL, g.w - g.padR, g.bottom, g.bottom);
    label(g.padL - 6, g.top + 4, "end", "100");
    label(g.padL - 6, g.y(0.5) + 4, "end", "50");
    label(g.padL - 6, g.bottom + 4, "end", "0");

    // Gold lead: one column per reading, up when the first team leads.
    const mid = Math.round((g.goldTop + g.goldBottom) / 2) + 0.5;
    const max = Math.max(1000, ...d.gold.map(([, v]) => Math.abs(v)));
    line("grid", g.padL, g.w - g.padR, mid, mid);
    label(g.padL - 6, g.goldTop + 8, "end", `+${(max / 1000).toFixed(0)}k`);
    label(g.padL - 6, g.goldBottom, "end", `−${(max / 1000).toFixed(0)}k`);
    const col = Math.max(1, Math.min(4, ((g.w - g.padL - g.padR) / Math.max(1, d.gold.length)) * 0.7));
    for (const [s, v] of d.gold) {
      const hh = ((Math.abs(v) / max) * (g.goldBottom - g.goldTop)) / 2;
      svg.appendChild(el("rect", { class: "gold", x: (g.x(s) - col / 2).toFixed(1), y: (v > 0 ? mid - hh : mid).toFixed(1), width: col.toFixed(1), height: Math.max(0.5, hh).toFixed(1) }));
    }

    // Minute ticks under the gold lead.
    const every = [300, 600, 900].find((st) => d.span / st <= (g.w < 600 ? 6 : 12)) || 1200;
    for (let s = 0; s <= d.span; s += every) {
      const xx = Math.round(g.x(s)) + 0.5;
      line("axis", xx, xx, g.goldBottom + 2, g.goldBottom + 6);
      label(xx, g.goldBottom + 18, "middle", `${s / 60}′`);
    }

    if (d.market.length) svg.appendChild(el("path", { class: "mkt", d: stepPath(d.market, g, d.span) }));
    if (d.calls.length) {
      svg.appendChild(el("path", { class: "ours", d: stepPath(d.calls, g, d.span) }));
      const [s0, p0] = d.calls[0];
      svg.appendChild(el("circle", { class: d.pre ? "call call--pre" : "call", cx: g.x(s0), cy: g.y(p0), r: 3.5 }));
      const [s1, p1] = d.calls[d.calls.length - 1];
      svg.appendChild(el("circle", { class: "call", cx: g.x(s1), cy: g.y(p1), r: 3.5 }));
    }
    return svg;
  }

  document.querySelectorAll(".lr-map[data-trace]").forEach((fig) => {
    let d;
    try { d = JSON.parse(fig.dataset.trace); } catch (e) { return; }
    const wrap = fig.querySelector(".lr-plot-wrap");
    const readout = fig.querySelector(".lr-readout");
    const label = wrap.querySelector("svg").getAttribute("aria-label");
    const team = fig.dataset.team;
    const tip = document.createElement("div");
    tip.className = "chance-tip";
    tip.setAttribute("aria-hidden", "true");
    tip.hidden = true;
    let g = null, svg = null, rule = null, dot = null, s = null, width = 0;

    function show() {
      if (!svg) return;
      if (s == null) {
        rule.style.display = dot.style.display = "none";
        tip.hidden = true;
        readout.textContent = "";
        return;
      }
      const x = g.x(s);
      rule.setAttribute("x1", x);
      rule.setAttribute("x2", x);
      rule.style.display = "";
      const ours = at(d.calls, s);
      if (ours != null) {
        dot.setAttribute("cx", x);
        dot.setAttribute("cy", g.y(ours));
        dot.style.display = "";
      } else dot.style.display = "none";
      const lead = nearest(d.gold, s);
      const lines = [
        clock(s),
        `Ours ${in100(ours)}`,
        `Kalshi ${in100(at(d.market, s))}`,
        lead == null ? null : `${team} ${gold(lead)} gold`,
      ].filter(Boolean);
      tip.replaceChildren(...lines.map((l, i) => {
        const e = document.createElement(i ? "span" : "b");
        e.textContent = l;
        return e;
      }));
      // Beside the rule, flipped to its left near the right edge.
      tip.style.left = tip.style.right = "";
      if (x > g.w - 150) tip.style.right = `${Math.round(g.w - x + 10)}px`;
      else tip.style.left = `${Math.round(x + 10)}px`;
      tip.hidden = false;
      readout.textContent = lines.join(" · ");
    }

    function render() {
      const w = Math.round(wrap.clientWidth);
      if (!w || w === width) return;
      width = w;
      g = layout(d, w);
      svg = draw(d, g);
      svg.setAttribute("aria-label", label);
      rule = svg.appendChild(el("line", { class: "cursor", y1: g.top, y2: g.goldBottom }));
      dot = svg.appendChild(el("circle", { class: "cursor-dot", r: 3.5 }));
      svg.addEventListener("pointermove", (e) => {
        const px = e.clientX - svg.getBoundingClientRect().left;
        s = Math.max(0, Math.min(d.span, ((px - g.padL) / (g.w - g.padL - g.padR)) * d.span));
        show();
      });
      svg.addEventListener("pointerleave", () => { s = null; show(); });
      svg.addEventListener("blur", () => { s = null; show(); });
      svg.addEventListener("keydown", (e) => {
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
        e.preventDefault();
        const step = (e.shiftKey ? 300 : 30) * (e.key === "ArrowRight" ? 1 : -1);
        s = Math.max(0, Math.min(d.span, (s == null ? 0 : s) + step));
        show();
      });
      wrap.replaceChildren(svg, tip);
      show();
    }

    render();
    if (window.ResizeObserver) new ResizeObserver(render).observe(wrap);
  });
})();
