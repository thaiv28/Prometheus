// Run with `node --test tests/js` (tests/test_js.py runs it under pytest).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const { fold, slugify, rank } = require("../../site_static/js/names.js");
const slugs = JSON.parse(readFileSync(new URL("./slugs.json", import.meta.url)));

test("slugify matches build_site._slugify", () => {
  for (const { name, slug } of slugs) assert.equal(slugify(name), slug, name);
});

test("fold drops accents and case", () => {
  assert.equal(fold("Ünited ÉSPORTS"), "united esports");
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
