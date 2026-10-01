// Team page: GLORY/GLORB toggle for the season rafters, and the Elo history chart.
(function () {
  "use strict";

  // ---- Season rafters ---------------------------------------------------
  const rafters = document.getElementById("season-rafters");
  if (rafters) {
    document.addEventListener("change", (e) => {
      if (e.target.name !== "team-metric") return;
      const metric = e.target.value;
      rafters.querySelectorAll(".banner").forEach((li) => {
        const raw = li.dataset[metric];
        const value = raw === "" ? null : Number(raw);
        li.classList.toggle("banner--empty", value === null);
        li.querySelector(".banner-value").textContent = value === null ? "—" : value.toFixed(2);
      });
      rafters.querySelectorAll(".banner").forEach((li, i) => li.style.setProperty("--i", i));
      rafters.classList.remove("is-rehanging");
      void rafters.offsetWidth; // restart the re-hang animation
      rafters.classList.add("is-rehanging");
    });
  }

  // ---- Elo chart --------------------------------------------------------
  const canvas = document.getElementById("elo-chart");
  if (!canvas) return;
  let series = [];
  try { series = JSON.parse(document.getElementById("elo-series").textContent); } catch (e) { /* empty chart */ }
  const frame = canvas.parentElement;

  if (typeof Chart === "undefined" || !series.length) {
    frame.insertAdjacentHTML("beforeend", '<p class="section-note">The Elo chart could not load. Check your connection and reload.</p>');
    canvas.remove();
    return;
  }

  const css = getComputedStyle(frame);
  const v = (name) => css.getPropertyValue(name).trim();
  const lineColor = v("--line");

  new Chart(canvas, {
    type: "line",
    data: {
      labels: series.map((d) => d.date),
      datasets: [{
        data: series.map((d) => d.elo),
        borderColor: lineColor,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: lineColor,
        tension: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: v("--ground-raised"),
          borderColor: v("--rule-strong"),
          borderWidth: 1,
          titleColor: v("--thread-dim"),
          bodyColor: v("--thread"),
          displayColors: false,
          callbacks: { label: (c) => "Elo " + Math.round(c.parsed.y) },
        },
      },
      scales: {
        x: {
          ticks: {
            color: v("--thread-dim"),
            maxTicksLimit: frame.clientWidth < 600 ? 4 : 8,
            maxRotation: 0,
            callback(value) { return this.getLabelForValue(value).slice(0, 7); },
          },
          grid: { display: false },
          border: { color: v("--rule-strong") },
        },
        y: {
          ticks: { color: v("--thread-dim"), maxTicksLimit: 6 },
          grid: { color: v("--rule") },
          border: { display: false },
        },
      },
    },
  });
})();
