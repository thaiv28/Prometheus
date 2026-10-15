import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

function render(a, b, calibration) {
  const rows = [a, b].map((r) => ({ ...r, now: true }));
  const elements = {
    "#rows-data": { textContent: JSON.stringify(rows) },
    "#page-config": { textContent: JSON.stringify({ weights: { elo: .005, crossRegionElo: .008, internationalCalibration: calibration } }) },
    "#matchup-a": { value: a.teamname, addEventListener() {} },
    "#matchup-b": { value: b.teamname, addEventListener() {} },
    "#matchup-result": {}, "#matchup-note": {},
    ".matchup-bar-a": { style: { setProperty() {} } },
  };
  vm.runInNewContext(fs.readFileSync(new URL("../../site_static/js/forecast.js", import.meta.url), "utf8"), {
    document: { querySelector: (selector) => elements[selector] },
  });
  return elements;
}

test("international head-to-head uses artifact coefficients and reverses with teams", () => {
  const a = { teamname: "A", league: "LCK", elo: 1600, forge: 1600 };
  const b = { teamname: "B", league: "LPL", elo: 1500, forge: 1500 };
  const model = { slope: .01, effects: { LCK: .2, LPL: -.2 } };
  const forward = render(a, b, model), reverse = render(b, a, model);
  assert.equal(forward["#matchup-result"].textContent, "80 times in 100");
  assert.equal(reverse["#matchup-result"].textContent, "20 times in 100");
  assert.match(forward["#matchup-note"].textContent, /International matchup/);
  assert.equal(render(a, { ...b, league: "LCK" }, model)["#matchup-result"].textContent, "62 times in 100");
  assert.equal(render(a, b, null)["#matchup-result"].textContent, "69 times in 100");
});
