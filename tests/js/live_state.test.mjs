// The live page's state reading (site_static/js/live_state.js).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const L = require("../../site_static/js/live_state.js");

const T0 = Date.parse("2026-10-07T20:00:00Z");
const at = (s) => new Date(T0 + s * 1000).toISOString();
const team = (gold, kills) => ({ gold, kills, towers: 0, dragons: 0, barons: 0, inhibitors: 0 });
const state = {
  status: "live",
  match: { teams: [{ name: "A" }, { name: "B" }] },
  game: {
    number: 1,
    pregame: { p: 0.6, by: "FORGE" },
    frames: [
      { at: at(20), clock: 20, teams: [team(3000, 1), team(2900, 0)] },
      { at: at(0), clock: 0, teams: [team(2500, 0), team(2500, 0)] },
      { at: at(10), clock: 10, teams: [team(2700, 0), team(2700, 0)] },
    ],
    market: [
      { at: at(1), bid: 0.58, ask: 0.6 },
      { at: at(16), bid: 0.4, ask: 0.6 },
    ],
    calls: [{ minute: 10, p: 0.7, at: at(15) }],
    winner: 0,
    ended_at: at(25),
  },
};

test("release holds back everything after the cutoff, winner included", () => {
  const v = L.release(state, T0 + 12000);
  assert.deepEqual(v.game.frames.map((f) => f.clock), [0, 10]);
  assert.equal(v.game.market.length, 1);
  assert.equal(v.game.calls.length, 0);
  assert.equal(v.game.winner, null);
  assert.equal(v.game.ended, false);
  assert.equal(v.game.held, 1);
  const all = L.release(state, T0 + 30000);
  assert.equal(all.game.winner, 0);
  assert.equal(all.game.ended, true);
  assert.equal(all.game.calls.length, 1);
});

test("release keeps a state with no game", () => {
  assert.equal(L.release({ status: "idle", game: null }, T0).game, null);
});

test("axis maps wall time to game clock, holding a paused clock", () => {
  const frames = [
    { at: at(0), clock: 600 },
    { at: at(10), clock: 610 },
    { at: at(70), clock: 610 }, // a minute's pause
  ];
  const ax = L.axis(frames);
  assert.equal(ax.mode, "clock");
  assert.equal(ax.x(T0 + 5000), 605);
  assert.equal(ax.x(T0 + 40000), 610);
  assert.equal(ax.x(T0 + 75000), 615);
});

test("axis falls back to time since the first reading without a clock", () => {
  const ax = L.axis([{ at: at(5), clock: null }, { at: at(15), clock: 30 }]);
  assert.equal(ax.mode, "elapsed");
  assert.equal(ax.x(T0 + 15000), 10);
});

test("safeUrl accepts a match file or one of its finished maps, nothing else", () => {
  assert.equal(L.safeUrl("live/123.json"), "live/123.json");
  assert.equal(L.safeUrl("live/123/map4.json"), "live/123/map4.json");
  assert.equal(L.safeUrl("live/123/../x.json"), null);
  assert.equal(L.safeUrl("https://x/live/1.json"), null);
});

test("axis uses the estimated game time, so a pause takes no width", () => {
  const ax = L.axis([
    { at: at(0), clock: null, clock_estimate: 900 },
    { at: at(10), clock: null, clock_estimate: 910 },
    { at: at(210), clock: null, clock_estimate: 910 },
    { at: at(220), clock: null, clock_estimate: 920 },
  ]);
  assert.equal(ax.mode, "estimated");
  assert.equal(ax.x(T0 + 110000), 910);
  assert.equal(ax.x(T0 + 220000), 920);
});

test("currentCall prefers the newest checkpoint, then the pre-game call", () => {
  assert.equal(L.currentCall(L.release(state, T0).game).kind, "pregame");
  assert.equal(L.currentCall(L.release(state, T0 + 20000).game).p, 0.7);
  assert.equal(L.currentCall({ calls: [], pregame: null }), null);
});

test("quoteAt drops quotes with too wide a spread", () => {
  const q = L.quoteAt(state.game.market, T0 + 5000);
  assert.ok(Math.abs(q.mid - 0.59) < 1e-9);
  assert.equal(L.quoteAt(state.game.market, T0 + 20000), null);
  assert.equal(L.quoteAt(state.game.market, T0), null);
});

test("formats", () => {
  assert.equal(L.gold(28512), "28.5k");
  assert.equal(L.gold(null), null);
  assert.equal(L.clock(905), "15:05");
  assert.equal(L.in100(0.634), 63);
});

test("liveMatches lists matches in progress, majors first", () => {
  const index = {
    matches: [
      { id: "a", league: "LPL" },
      { id: "b", league: "CBLOL" },
      { id: "c", league: "LCK" },
      { id: "d", league: "LCK", status: "idle" },
      { id: "e", league: "LPL" },
    ],
  };
  assert.deepEqual(L.liveMatches(index, ["LCK", "LPL", "LEC", "LCS"]).map((m) => m.id), ["c", "a", "e", "b"]);
  assert.deepEqual(L.liveMatches(null), []);
});

test("safeUrl keeps match files under live/ only", () => {
  assert.equal(L.safeUrl("live/lck-t1-gen.json"), "live/lck-t1-gen.json");
  assert.equal(L.safeUrl("https://evil.example/x.json"), null);
  assert.equal(L.safeUrl("live/../x.json"), null);
});

test("summaryCall, pair and goldLead", () => {
  assert.deepEqual(L.summaryCall({ call: { minute: 15, p: 0.7 } }), { p: 0.7, note: "at 15′", by: undefined });
  assert.equal(L.summaryCall({ pregame: { p: 0.6, by: "FORGE" } }).note, "before the map");
  assert.equal(L.summaryCall({}), null);
  assert.equal(L.pair(7, null), "7–—");
  assert.equal(L.goldLead([{ gold: 30400 }, { gold: 28000 }]), "+2.4k");
  assert.equal(L.goldLead([{ gold: 28000 }, { gold: 28800 }]), "−0.8k");
  assert.equal(L.goldLead([{ gold: 28000 }, { gold: 28020 }]), "even");
  assert.equal(L.short({ name: "T1 Esports", code: "T1" }), "T1");
});

test("goldLeader names the team ahead", () => {
  const names = [{ name: "T1" }, { name: "Gen.G", code: "GEN" }];
  assert.equal(L.goldLeader([{ gold: 30400 }, { gold: 28000 }], names), "T1 +2.4k");
  assert.equal(L.goldLeader([{ gold: 28000 }, { gold: 28800 }], names), "GEN +0.8k");
  assert.equal(L.goldLeader([{ gold: 28000 }, { gold: 28020 }], names), "even");
});


test("Coming up waits for the same started series on Live", () => {
  const m = { id: "riot-id", status: "live", start: at(0), teams: [{name:"Cloud9"}, {name:"Karmine Corp"}] };
  const check = (match) => L.fixtureOnLive(["Karmine Corp", "Cloud9"], at(0), L.liveMatches({matches:[match]}));
  assert.equal(check(m), true);
  for (const status of ["waiting", "idle", "unavailable"]) assert.equal(check({...m, status}), false);
  assert.equal(check({...m, status:"between_games"}), true);
  assert.equal(check({...m, start:at(86400)}), false);
  assert.equal(check({...m, teams:[{name:"T1"},{name:"Cloud9"}]}), false);
  assert.equal(check({...m, start:null}), true); // compatible with an older worker
  assert.equal(L.fixtureOnLive(["Cloud9"], at(0), [m]), false);
});


test("Coming up recognizes confirmed finished series after an index clears", () => {
  const done = {status:"completed", start:at(0), teams:[{name:"Karmine Corp"}, {name:"MVK Esports"}]};
  assert.equal(L.fixtureOnLive(["MVK Esports", "Karmine Corp"], at(0), [done]), true);
  assert.equal(L.fixtureOnLive(["MVK Esports", "Karmine Corp"], at(86400), [done]), false);
});
