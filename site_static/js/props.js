// The Props page: switch the stat shown in every match, show only matches with
// lines for it (the default; ?lines=all shows every match), set match times in
// the visitor's time zone, and apply the hourly props-lines.json over the lines
// built into the page. The choice is kept in the URL (?stat=, ?lines=all).
(function () {
  "use strict";
  var filters = document.querySelector(".filter-line");
  if (!filters) return;
  filters.hidden = false;

  var picker = filters.querySelector('[data-filter="stat"]');
  var value = picker.querySelector(".picker-value");
  var radios = Array.prototype.slice.call(picker.querySelectorAll('input[type="radio"]'));
  var only = document.getElementById("pp-only");
  var matches = Array.prototype.slice.call(document.querySelectorAll(".pp-match"));
  var none = document.querySelector(".pp-none");
  var params = new URLSearchParams(location.search);

  function apply(stat, lines) {
    radios.forEach(function (r) {
      r.checked = r.value === stat;
      if (r.checked) value.textContent = r.parentNode.textContent.trim();
    });
    var shown = 0;
    matches.forEach(function (m) {
      m.querySelectorAll(".pp-stat").forEach(function (f) {
        f.hidden = f.getAttribute("data-stat") !== stat;
      });
      var hide = lines && m.getAttribute("data-lines-" + stat) === "0";
      m.hidden = hide;
      if (!hide) shown += 1;
    });
    if (none) none.hidden = !(lines && shown === 0 && matches.length);
    only.checked = lines;
    var q = new URLSearchParams(location.search);
    if (stat === radios[0].value) q.delete("stat"); else q.set("stat", stat);
    if (lines) q.delete("lines"); else q.set("lines", "all");
    var s = q.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash);
  }

  function current() {
    var r = radios.filter(function (x) { return x.checked; })[0];
    return r ? r.value : radios[0].value;
  }

  radios.forEach(function (r) {
    r.addEventListener("change", function () {
      apply(r.value, only.checked);
      picker.open = false;
    });
  });
  only.addEventListener("change", function () { apply(current(), only.checked); });
  document.addEventListener("click", function (e) {
    if (picker.open && !picker.contains(e.target)) picker.open = false;
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && picker.open) { picker.open = false; picker.querySelector("summary").focus(); }
  });

  var wanted = params.get("stat");
  var valid = radios.some(function (r) { return r.value === wanted; });
  apply(valid ? wanted : radios[0].value, params.get("lines") !== "all");

  // Local times: "Thursday 15 October, 20:00".
  var days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  document.querySelectorAll(".pp-when time").forEach(function (t) {
    var d = new Date(t.getAttribute("datetime"));
    if (isNaN(d)) return;
    t.textContent = days[d.getDay()] + " " + d.getDate() + " " + months[d.getMonth()] + ", " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  });
  // The hourly job rewrites props-lines.json: the newest lines priced against the
  // build's projections. Rebuild each line cell from it (the same markup as
  // line_cell in _props.html.j2), then each match's counts and the filters.
  var esc = PrometheusNames.esc;
  function cellHtml(c, app) {
    if (!c) {
      return '<td class="pp-line pp-line--none" data-app="' + esc(app) + '"><span class="muted">—</span></td>';
    }
    var title = "Over: ours " + c.over + (c.app_over != null ? ", " + c.label + " " + c.app_over : "") + (c.one_sided ? ". Over only" : "");
    var pick = c.side
      ? '<span class="pp-side">' + (c.side === "over" ? "O" : "U") + "</span>&#8201;" + esc(c.p_side)
      : '<span class="muted">—</span>';
    return '<td class="pp-line' + (c.clears ? " pp-line--clears" : "") + '" data-app="' + esc(app) + '" title="' + esc(title) + '">' +
      '<span class="pp-line-num">' + esc(c.line) + "</span>" +
      '<span class="pp-meter" style="--p: ' + Number(c.over) + "; --be: " + Number(c.break_even || 58) + '" aria-hidden="true"></span>' +
      '<span class="pp-pick">' + pick + "</span>" +
      '<span class="visually-hidden">' + (c.side ? ": " + esc(c.side) + ", " + esc(c.p_side) + " in 100" : "") + "</span></td>";
  }
  function applyLines(data) {
    if (!data || !data.lines) return;
    var byKey = {};
    data.lines.forEach(function (c) { byKey[[c.match, c.stat, c.player, c.app].join("|")] = c; });
    matches.forEach(function (m) {
      var id = m.getAttribute("data-match");
      m.querySelectorAll(".pp-stat").forEach(function (f) {
        var stat = f.getAttribute("data-stat");
        var n = 0;
        f.querySelectorAll("tr[data-player]").forEach(function (tr) {
          tr.querySelectorAll("td[data-app]").forEach(function (td) {
            var app = td.getAttribute("data-app");
            var c = byKey[[id, stat, tr.getAttribute("data-player"), app].join("|")];
            if (c) n += 1;
            td.outerHTML = cellHtml(c, app);
          });
        });
        m.setAttribute("data-lines-" + stat, String(n));
      });
    });
    if (read && data.at) {
      read.setAttribute("datetime", data.at.replace("Z", ":00Z"));
      setRead();
    }
    apply(current(), only.checked);
  }

  var read = document.querySelector(".pp-read");
  function setRead() {
    var r = new Date(read.getAttribute("datetime"));
    if (!isNaN(r)) read.textContent = r.getDate() + " " + months[r.getMonth()] + ", " + pad(r.getHours()) + ":" + pad(r.getMinutes());
  }
  if (read) setRead();
  if (matches.length) {
    fetch("props-lines.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(applyLines)
      .catch(function () {});
  }
})();
