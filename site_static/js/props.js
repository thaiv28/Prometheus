// The Props page: switch the stat shown in every match, show only matches with
// lines for it (the default; ?lines=all shows every match), and set match times
// in the visitor's time zone. The choice is kept in the URL (?stat=, ?lines=all).
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
  var read = document.querySelector(".pp-read");
  if (read) {
    var r = new Date(read.getAttribute("datetime"));
    if (!isNaN(r)) read.textContent = r.getDate() + " " + months[r.getMonth()] + ", " + pad(r.getHours()) + ":" + pad(r.getMinutes());
  }
})();
