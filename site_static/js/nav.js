// Header menus (Teams, Players): <details> elements that open on click and work
// without JS. This closes the other menu when one opens, and closes an open menu
// on a click elsewhere or on Escape, returning focus to its name.
(function () {
  "use strict";

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
