import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const path = "../../site_static/js/fresh.js";
function fresh() { delete require.cache[require.resolve(path)]; return require(path); }

test("load rejects wrong builds, empty maps, failures and missing bases", async () => {
  const original = global.fetch;
  try {
    global.fetch = async (url, options) => {
      assert.equal(url, "fresh.json");
      assert.equal(options.cache, "no-store");
      return { ok: true, json: async () => ({ base: "old", teams: { A: 2 }, players: {} }) };
    };
    assert.equal(await fresh().load("new"), null);
    assert.equal(await fresh().load(undefined), null);
    global.fetch = async () => ({ ok: true, json: async () => ({ base: "new", teams: {}, players: {} }) });
    assert.equal(await fresh().load("new"), null);
    global.fetch = async () => { throw Error("offline"); };
    assert.equal(await fresh().load("new"), null);
    const overlay = { base: "new", teams: {}, players: { one: 1 } };
    global.fetch = async () => ({ ok: true, json: async () => overlay });
    assert.deepEqual(await fresh().load("new"), overlay);
  } finally { global.fetch = original; }
});

test("apply changes only now rows, using team names or player slugs", () => {
  const { apply } = fresh();
  const overlay = { teams: { A: 2 }, players: { one: -3 } };
  const rows = [
    { teamname: "A", slug: "one", now: true, elo: 1500, forge: 1510, form: 10 },
    { teamname: "A", slug: "one", now: false, elo: 1490, forge: 1500 },
    { teamname: "B", now: true, elo: 1400 },
  ];
  assert.equal(apply(rows, overlay), true);
  assert.equal(rows[0].elo, 1502);
  assert.equal(rows[0].forge, 1512);
  assert.equal(rows[0].form, 10);
  assert.equal(rows[1].elo, 1490);
  assert.equal(rows[1].forge, 1500);
  assert.equal(rows[2].elo, 1400);
  apply(rows, overlay, "player");
  assert.equal(rows[0].elo, 1499);
  assert.equal(rows[0].forge, 1509);
  assert.equal(rows[1].elo, 1490);
});
