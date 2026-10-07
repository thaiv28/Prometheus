// Name helpers shared by the header search and the rankings registers, and
// tested under Node (tests/js). No DOM access here.
const PrometheusNames = (function () {
  "use strict";

  // Lower case without accents, for matching names as typed. Letters such as ø
  // have no accent to strip, so they are spelled out (as schedule.fold does).
  const PLAIN = { "ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "đ": "d", "ł": "l", "þ": "th" };
  const fold = (s) =>
    String(s).toLowerCase().replace(/[øæœßđłþ]/g, (c) => PLAIN[c]).normalize("NFD").replace(/[̀-ͯ]/g, "");

  // Same as build_site._slugify, so a name links to its page.
  const slugify = (name) =>
    String(name).toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "team";

  // Best matches for a query among items with a folded `key`: the exact name, then
  // names starting with the query, then a word in the name starting with it, then
  // anywhere. Ties keep the items' order.
  function rank(items, query, limit) {
    const q = fold(query.trim());
    if (!q) return [];
    const out = [];
    for (const item of items) {
      const at = item.key.indexOf(q);
      if (at < 0) continue;
      const score = item.key === q ? -1 : at === 0 ? 0 : /[\s.\-]/.test(item.key[at - 1]) ? 1 : 2;
      out.push([score, out.length, item]);
    }
    return out.sort((a, b) => a[0] - b[0] || a[1] - b[1]).slice(0, limit).map((x) => x[2]);
  }

  return { fold, slugify, rank };
})();

if (typeof module === "object" && module.exports) module.exports = PrometheusNames;
