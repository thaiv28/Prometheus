// Run with `node --test tests/js` (tests/test_js.py runs it under pytest).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const { fold, slugify, rank, esc, leagueMark } = require("../../site_static/js/names.js");
const slugs = JSON.parse(readFileSync(new URL("./slugs.json", import.meta.url)));

test("slugify matches build_site._slugify", () => {
  for (const { name, slug } of slugs) assert.equal(slugify(name), slug, name);
});

test("fold drops accents and case", () => {
  assert.equal(fold("Ünited ÉSPORTS"), "united esports");
  assert.equal(fold("LØS"), "los");
  assert.equal(fold("Sørby eSport"), "sorby esport");
});

const items = (names) => names.map((n) => ({ n, key: fold(n) }));

test("rank puts the exact name, then prefixes, then word starts, then anywhere", () => {
  const list = items(["Gen.G Scholars", "Bigen", "Team Gen", "Gen.G", "General"]);
  assert.deepEqual(rank(list, "gen.g", 8).map((x) => x.n), ["Gen.G", "Gen.G Scholars"]);
  assert.deepEqual(rank(list, "gen", 8).map((x) => x.n), ["Gen.G Scholars", "Gen.G", "General", "Team Gen", "Bigen"]);
});

test("rank keeps index order on ties and respects the limit", () => {
  const list = items(["Viper", "Viper", "Vipers", "Viper Night Raider"]);
  const top = rank(list, "viper", 3);
  assert.equal(top.length, 3);
  assert.equal(top[0], list[0]);
  assert.equal(top[1], list[1]);
});

test("rank ignores blank queries and accents in the query", () => {
  assert.deepEqual(rank(items(["T1"]), "   ", 8), []);
  assert.deepEqual(rank(items(["Ünited Esports"]), "unit", 8).map((x) => x.n), ["Ünited Esports"]);
});

test("esc escapes every HTML-special character and blanks null", () => {
  assert.equal(esc(`<a href="x" title='y'>&</a>`), "&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;");
  assert.equal(esc(null), "");
  assert.equal(esc(undefined), "");
  assert.equal(esc(0), "0");
});

test("leagueMark shows the code or hides it for screen readers, escaped", () => {
  assert.equal(
    leagueMark("LCK", true),
    '<span class="league" data-league="LCK"><span class="league-mark" aria-hidden="true"></span>LCK</span>',
  );
  assert.match(leagueMark('<x"', false), /data-league="&lt;x&quot;".*visually-hidden">&lt;x&quot;</);
});
