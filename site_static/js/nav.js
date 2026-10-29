// Header menus (Teams, Players): <details> elements that open on click and work
// without JS. This closes the other menu when one opens, and closes an open menu
// on a click elsewhere or on Escape, returning focus to its name.
(function () {
  "use strict";

  const search = document.querySelector(".index-search");
  const root = search ? search.dataset.root : "";
  // A red dot on Predictions while a match is on. An index the collector
  // stopped updating (10 minutes, by the server's clock) shows none.
  let served = NaN;
  fetch(root + "live/index.json", { cache: "no-store" })
    .then((r) => {
      served = Date.parse(r.headers.get("Date"));
      return r.ok ? r.json() : null;
    })
    .then((data) => {
      if (!data || !Array.isArray(data.matches) || !data.matches.some((m) => ["live", "paused", "between_games"].includes(m.status))) return;
      if (!(served - Date.parse(data.published_at) < 600000)) return;
      const link = [...document.querySelectorAll("nav a")].find((a) => a.getAttribute("href") === root + "predictions.html");
      if (!link) return;
      const dot = document.createElement("span");
      dot.className = "nav-live";
      dot.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.className = "visually-hidden";
      label.textContent = " (match live now)";
      link.append(dot, label);
      link.classList.add("is-live");
    }).catch(() => {});

  const menus = [...document.querySelectorAll(".nav-menu")];
  if (!menus.length) return;

  menus.forEach((menu) => menu.addEventListener("toggle", () => {
    if (menu.open) menus.forEach((m) => { if (m !== menu) m.open = false; });
  }));

  document.addEventListener("click", (e) => {
    menus.forEach((m) => { if (m.open && !m.contains(e.target)) m.open = false; });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const open = menus.find((m) => m.open);
    if (open) { open.open = false; open.querySelector("summary").focus(); }
  });
})();
