// The aim map of the training card: the points per dart of every aim point, from the error
// model of Home Assistant, computed in a Web Worker, with the best aim and the beds it beats.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, DEVICE, loadCards, makeHass, mount, settle, text, window, withLanguage } from "./dom.mjs";

const { NUMBERS, aimDraws, aimField, aimHtml, aimRequest, aimRows, aimSegment, aimSummaryHtml, aimView, offsetText } =
  await loadCards();

// The same numbers as tests/test_aim.py: Home Assistant and the card agree to the last digit.
const BOARD_SUM = 1213944;
const BOARD_MOMENTS = [-6705061, -1380490];
const MODEL = { offset_x: 0, offset_y: 0, sd_x: 20, sd_y: 20, correlation: 0 };
const EXPECTED = { T20: 18.047, T19: 18.507, BULL: 16.353 };
// What Home Assistant sends for a player with that spread.
const AIM = {
  darts: 140,
  needed: 30,
  ...MODEL,
  offset_x: -6,
  offset_y: 2,
  best: { bed: "T19", x: -34, y: -96, expected: 18.871, compared: EXPECTED },
};
const GEOMETRY = aimRequest(MODEL).geometry;
const UI = {
  t: (key) =>
    ({
      aim_best: "Best aim · {points} points per dart",
      aim_points: "{points} points per dart",
      aim_model: "From {darts} darts at a treble: spread {across} across, {up} up and down",
      unit_mm: "{value} mm",
      spread_left: "{distance} left of center",
      spread_high: "{distance} high",
      spread_centered: "centered",
    })[key],
  format: (value, digits = 0) => value.toFixed(digits),
  label: (key) => (key === "BULL" ? "Bull" : key),
};

// The points per dart of the field at a point of its grid.
const at = (field, x, y) => {
  const side = (field.size - 1) / 2;
  return field.field[(y / field.grid + side) * field.size + x / field.grid + side];
};

const SESSION = {
  "sensor.training_darts": { state: "6", attributes: { hits: { T20: 4, S20: 2 } } },
  "switch.training_session": "on",
};
const PROFILES = {
  "sensor.player_profiles": {
    state: "1",
    attributes: { players: [{ name: "Alex", darts_thrown: 400, hits: { T20: 30 } }] },
  },
};

// A board that answers with an aim model; requests are kept in `asked`.
function board(asked, aim = AIM) {
  return async (message) => {
    asked.push(message);
    return { player: message.player ?? null, known: true, positions: [[0, 0.6]], spread: [], aim };
  };
}

function setup(config = {}, aim = AIM, language = "en") {
  const asked = [];
  const hass = withLanguage(makeHass({ states: { ...SESSION, ...PROFILES }, callWS: board(asked, aim) }), language);
  const card = mount("homedarts-training-card", hass, { mode: "aim", player: "Alex", ...config });
  return { asked, hass, card };
}

// A Web Worker that runs the card's script in this process, from the address of its blob.
const blobs = new Map();
const workers = [];
class FakeWorker {
  constructor(url) {
    this.url = url;
    this.terminated = false;
    workers.push(this);
    this.ready = blobs.get(url).text().then((source) => {
      const scope = { postMessage: (message) => this.onmessage({ data: message }) };
      new Function("self", source)(scope);
      this.scope = scope;
    });
  }

  postMessage(message) {
    this.ready.then(() => this.scope.onmessage({ data: structuredClone(message) }));
  }

  terminate() {
    this.terminated = true;
  }
}

function withWorkers(Worker, run) {
  const saved = { Worker: window.Worker, create: window.URL.createObjectURL, revoke: window.URL.revokeObjectURL };
  const revoked = [];
  window.Worker = Worker;
  window.URL.createObjectURL = (blob) => {
    const url = `blob:aim-${blobs.size}`;
    blobs.set(url, blob);
    return url;
  };
  window.URL.revokeObjectURL = (url) => revoked.push(url);
  return run(revoked).finally(() => {
    window.Worker = saved.Worker;
    window.URL.createObjectURL = saved.create;
    window.URL.revokeObjectURL = saved.revoke;
  });
}

// Waits until the field of the card arrived, from the page or from a worker.
async function drawn(card) {
  for (let round = 0; round < 50 && !$(card, ".heat-layer .aim-best"); round += 1) await settle();
  assert.ok($(card, ".heat-layer .aim-best"), "the aim map was drawn");
}

test("the board of the aim map is the board of Home Assistant", () => {
  let total = 0;
  let momentX = 0;
  let momentY = 0;
  for (let y = -170; y <= 170; y += 1) {
    for (let x = -170; x <= 170; x += 1) {
      const [number, multiplier] = aimSegment(x, y, GEOMETRY);
      total += number * multiplier;
      momentX += x * number * multiplier;
      momentY += y * number * multiplier;
    }
  }
  assert.equal(total, BOARD_SUM);
  assert.deepEqual([momentX, momentY], BOARD_MOMENTS);
  // The rings up the 20, as the Board Manager draws them, and the board's end.
  const up = [7, 8, 17, 18, 97, 98, 107, 108, 160, 161, 170, 171].map((y) => aimSegment(0, y, GEOMETRY));
  assert.deepEqual(up, [
    [25, 2],
    [25, 1],
    [25, 1],
    [20, 1],
    [20, 1],
    [20, 3],
    [20, 3],
    [20, 1],
    [20, 1],
    [20, 2],
    [20, 2],
    [0, 0],
  ]);
  // A point exactly between two sectors lies in the even one, as Python rounds halves.
  const diagonals = [
    [50, 50],
    [-50, 50],
    [50, -50],
    [-50, -50],
  ].map(([x, y]) => aimSegment(x, y, GEOMETRY)[0]);
  assert.deepEqual(diagonals, [18, 12, 2, 7]);
  // Every number in its place, with the 6 on the right and the 3 at the bottom.
  assert.deepEqual(aimSegment(102, 0, GEOMETRY), [6, 3]);
  assert.deepEqual(aimSegment(0, -102, GEOMETRY), [3, 3]);
  assert.deepEqual(GEOMETRY.numbers, NUMBERS);
});

test("the draws are fixed and standard normal", () => {
  const draws = aimDraws(1000);
  assert.equal(draws.length, 2000);
  assert.ok(Math.abs(draws[0] - 3.8989492070408103) < 1e-12 && draws[1] === 0);
  const xs = draws.filter((_, index) => index % 2 === 0);
  const ys = draws.filter((_, index) => index % 2 === 1);
  for (const values of [xs, ys]) {
    assert.ok(Math.abs(values.reduce((sum, value) => sum + value, 0) / 1000) < 0.01);
    assert.ok(Math.abs(values.reduce((sum, value) => sum + value * value, 0) / 1000 - 1) < 0.02);
  }
});

test("the points per dart are those of Home Assistant", () => {
  const field = aimField(aimRequest(MODEL));
  assert.equal(field.size, 171);
  assert.equal(field.grid, 2);
  const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-4, `${actual} is not ${expected}`);
  close(at(field, 0, 102), EXPECTED.T20);
  close(at(field, -32, -98), EXPECTED.T19);
  close(at(field, 0, 0), EXPECTED.BULL);
  // The best aim of Home Assistant is the best point of the whole grid.
  close(at(field, -34, -96), 18.871);
  close(field.high, 18.871);
  // Off the board, nothing.
  assert.equal(at(field, 170, 170), -1);
  // Far off the board, every draw misses it.
  const lost = aimField(aimRequest({ ...MODEL, offset_x: 600 }));
  assert.equal(lost.high, 0);
  assert.equal(aimHtml(lost, AIM.best).match(/<rect/g), null);
});

test("an aim model needs its numbers and a best aim", () => {
  const view = aimView(AIM);
  assert.equal(view.key, "-6|2|20|20|0");
  assert.deepEqual(view.best, { bed: "T19", x: -34, y: -96, expected: 18.871 });
  // The best bed is not compared with itself.
  assert.deepEqual(
    view.compared.map(({ bed }) => bed),
    ["T20", "BULL"]
  );
  assert.deepEqual(aimView(undefined), { darts: 0, needed: 30, model: null, key: null, best: null, compared: [] });
  assert.equal(aimView({ darts: 12, needed: 30 }).darts, 12);
  assert.equal(aimView({ darts: -1, needed: "30" }).darts, 0);
  for (const broken of [
    { sd_x: 0 },
    { sd_y: -1 },
    { correlation: 1 },
    { offset_x: "1" },
    { best: null },
    { best: { ...AIM.best, bed: 19 } },
    { best: { ...AIM.best, x: 1.5 } },
    { best: { ...AIM.best, expected: null } },
  ]) {
    assert.equal(aimView({ ...AIM, ...broken }).model, null, JSON.stringify(broken));
  }
  // Compared beds without numbers are left out.
  const partial = aimView({ ...AIM, best: { ...AIM.best, compared: { T20: 18, BULL: "x" } } });
  assert.deepEqual(partial.compared, [{ bed: "T20", expected: 18 }]);
  assert.deepEqual(aimView({ ...AIM, best: { ...AIM.best, compared: undefined } }).compared, []);
});

test("the map colors the best part of the board and rings the best aim", () => {
  const field = aimField(aimRequest(MODEL));
  const html = aimHtml(field, AIM.best);
  const cells = html.match(/<rect /g).length;
  assert.ok(cells > 100 && cells < 2600, `${cells} cells`);
  assert.match(html, /<circle class="aim-best" cx="-34" cy="96" r="7"\/>/);
  assert.match(html, /filter="url\(#ad-density\)"/);
  // The cells lie on the grid of 6 mm through the middle of the board.
  assert.match(html, /<rect x="-3" y="-3" width="6" height="6"/);
});

test("the summary names the best aim and how much less the other beds score", () => {
  const view = aimView(AIM);
  assert.deepEqual(aimRows(view, UI), [
    { bed: "T19", text: "Best aim · 18.9 points per dart", change: "" },
    { bed: "T20", text: "18.0 points per dart", change: "-0.8" },
    { bed: "BULL", text: "16.4 points per dart", change: "-2.5" },
  ]);
  // A bed that scores as much as the best, to a tenth, shows no difference.
  const even = aimView({ ...AIM, best: { ...AIM.best, compared: { T20: 18.86 } } });
  assert.equal(aimRows(even, UI)[1].change, "");
  const html = aimSummaryHtml(view, UI);
  assert.match(html, /<span class="group-target">Bull<\/span>/);
  assert.match(html, /<span class="group-change worse">-2.5<\/span>/);
  assert.match(
    html,
    /From 140 darts at a treble: spread 20 mm across, 20 mm up and down · 6 mm left of center, 2 mm high/
  );
  assert.equal(offsetText(UI, { offset_x: 0, offset_y: 0 }), "centered");
});

test("the training card draws the aim map of a player", async () => {
  const { asked, card } = setup();
  // Only the aim map asks for the aim model.
  assert.deepEqual(asked, [{ type: "homedarts/positions", device_id: DEVICE, player: "Alex", aim: true }]);
  assert.equal($(card, '[data-mode="aim"]').getAttribute("aria-pressed"), "true");
  await drawn(card);
  assert.equal(
    $(card, "svg[role=img]").getAttribute("aria-label"),
    "Dartboard colored by the points per dart at each aim point, with a ring at the best aim"
  );
  assert.ok($$(card, ".heat-layer .density rect").length > 100);
  assert.deepEqual([text(card, ".legend-min"), text(card, ".legend-max")], ["11.3", "18.9"]);
  assert.equal($(card, ".heat .groups").hidden, false);
  assert.deepEqual(
    $$(card, ".heat .group").map((group) => group.dataset.target),
    ["T19", "T20", "BULL"]
  );
  assert.equal(text(card, ".group-text"), "Best aim · 18.9 points per dart");
  assert.equal(text(card, ".aim-model").startsWith("From 140 darts at a treble: spread 20 mm across"), true);
  // Screen readers get the same as a list.
  assert.deepEqual(
    $$(card, ".heat-list li").map((item) => item.textContent),
    ["T19: Best aim · 18.9 points per dart", "T20: 18.0 points per dart", "Bull: 16.4 points per dart"]
  );
  // Back to positions and beds, and to the aim map again, which keeps its field; the answer
  // with the aim model serves the positions, too.
  $(card, '[data-mode="positions"]').dispatchEvent(new window.Event("click", { bubbles: true }));
  assert.equal($(card, ".heat-layer .aim-best"), null);
  $(card, '[data-mode="beds"]').dispatchEvent(new window.Event("click", { bubbles: true }));
  assert.equal($(card, ".heat .groups").hidden, true);
  $(card, '[data-mode="aim"]').dispatchEvent(new window.Event("click", { bubbles: true }));
  assert.ok($(card, ".heat-layer .aim-best"));
  assert.equal(asked.length, 1);
});

test("without enough darts at a treble, the card says how many are missing", async () => {
  const { card } = setup({}, { darts: 12, needed: 30 });
  await settle();
  assert.equal($(card, ".heat-layer").children.length, 0);
  assert.equal(text(card, ".heat .groups"), "The aim map needs 30 darts aimed at a treble, 18 more to go.");
  assert.deepEqual([text(card, ".legend-min"), text(card, ".legend-max")], ["–", "–"]);
  // A model that came without its numbers needs at least one more dart.
  const odd = setup({}, { darts: 40, needed: 30, sd_x: 0 }).card;
  await settle();
  assert.equal(text(odd, ".heat .groups"), "The aim map needs 30 darts aimed at a treble, 1 more to go.");
  const german = setup({}, { darts: 29, needed: 30 }, "de").card;
  await settle();
  assert.equal(text(german, ".heat .groups"), "Die Zielkarte braucht 30 Darts auf ein Triple, noch 1.");
  assert.equal($(german, '[data-mode="aim"]').textContent, "Zielpunkt");
});

test("until the positions arrive, the aim map stays empty", () => {
  const hass = makeHass({ states: { ...SESSION, ...PROFILES }, callWS: () => new Promise(() => {}) });
  const card = mount("homedarts-training-card", hass, { mode: "aim" });
  assert.equal($(card, ".heat .groups").hidden, true);
  assert.equal($(card, ".heat-layer").children.length, 0);
  assert.equal($(card, ".heat-list").children.length, 0);
});

// The next darts of Alex: new positions, and the card asks for them again.
const nextDarts = (hass, darts) => ({
  ...hass,
  states: {
    ...hass.states,
    "sensor.dartboard_player_profiles": {
      ...hass.states["sensor.dartboard_player_profiles"],
      attributes: { players: [{ name: "Alex", darts_thrown: darts, hits: { T20: 30 } }] },
    },
  },
});

// A worker that answers only when the test lets it.
class HeldWorker extends FakeWorker {
  constructor(url) {
    super(url);
    this.held = [];
  }

  postMessage(message) {
    this.held.push(message);
  }

  answer(index) {
    return this.ready.then(() => this.scope.onmessage({ data: structuredClone(this.held[index]) }));
  }
}

test("the aim map takes the palette of the card", () => {
  const field = aimField(aimRequest(aimView(AIM).model));
  assert.match(aimHtml(field, AIM.best), /fill="#f1e323" fill-opacity="0\.95"/);
  assert.match(aimHtml(field, AIM.best, "thermal"), /fill="hsl\(\d+, 90%, 55%\)" fill-opacity="0\.\d+"/);
  assert.doesNotMatch(aimHtml(field, AIM.best), /hsl\(/);
});

test("a Web Worker computes the map, with the numbers of the card", async () => {
  await withWorkers(FakeWorker, async (revoked) => {
    const { card, hass } = setup();
    await drawn(card);
    assert.equal(workers.length, 1);
    assert.deepEqual(revoked, [workers[0].url]);
    const direct = aimField(aimRequest(aimView(AIM).model));
    assert.equal($$(card, ".heat-layer .density rect").length, aimHtml(direct, AIM.best).match(/<rect /g).length);
    // The same model needs no new map.
    card.hass = nextDarts(hass, 401);
    await settle();
    assert.equal(workers.length, 1);
    // The worker ends with the card; a card that returns keeps its map.
    card.remove();
    assert.equal(workers[0].terminated, true);
    document.body.append(card);
    card.hass = nextDarts(hass, 402);
    await drawn(card);
    assert.equal(workers.length, 1);
  });
});

test("a newer model replaces a map that was still on its way", async () => {
  await withWorkers(HeldWorker, async () => {
    let aim = AIM;
    const hass = makeHass({
      states: { ...SESSION, ...PROFILES },
      callWS: async () => ({ player: "Alex", known: true, positions: [], spread: [], aim }),
    });
    const card = mount("homedarts-training-card", hass, { mode: "aim", player: "Alex" });
    await settle();
    const [worker] = workers.slice(-1);
    assert.equal(worker.held.length, 1);
    aim = { ...AIM, sd_x: 30, sd_y: 30, best: { ...AIM.best, x: -40, y: -90 } };
    card.hass = nextDarts(hass, 403);
    await settle();
    assert.equal(worker.held.length, 2);
    // The first map arrives late and is not drawn.
    await worker.answer(0);
    await settle();
    assert.equal($(card, ".heat-layer .aim-best"), null);
    await worker.answer(1);
    await drawn(card);
    assert.equal($(card, ".aim-best").getAttribute("cx"), "-40");
  });
});

test("the last map stays until the map of a new model arrives", async () => {
  await withWorkers(HeldWorker, async () => {
    let aim = AIM;
    const hass = makeHass({
      states: { ...SESSION, ...PROFILES },
      callWS: async () => ({ player: "Alex", known: true, positions: [], spread: [], aim }),
    });
    const card = mount("homedarts-training-card", hass, { mode: "aim", player: "Alex" });
    await settle();
    const [worker] = workers.slice(-1);
    await worker.answer(0);
    await drawn(card);
    const before = $(card, ".heat-layer").innerHTML;
    const legend = text(card, ".legend-max");
    // The next visit changes the model: the old map stays while the worker works.
    aim = { ...AIM, sd_x: 30, sd_y: 30, best: { ...AIM.best, x: -40, y: -90, expected: 15.5 } };
    card.hass = nextDarts(hass, 406);
    await settle();
    assert.equal(worker.held.length, 2);
    assert.equal($(card, ".heat-layer").innerHTML, before);
    assert.equal(text(card, ".legend-max"), legend);
    assert.equal(text(card, ".group-text"), "Best aim · 15.5 points per dart");
    await worker.answer(1);
    await settle();
    assert.equal($(card, ".aim-best").getAttribute("cx"), "-40");
    // The session has a map of its own: the map of Alex does not stay for it.
    aim = { ...AIM, sd_x: 40, sd_y: 40, best: { ...AIM.best, x: -20, y: 0 } };
    $(card, '[data-source=""]').dispatchEvent(new window.Event("click", { bubbles: true }));
    await settle();
    assert.equal(worker.held.length, 3);
    assert.equal($(card, ".heat-layer .aim-best"), null);
    await worker.answer(2);
    await drawn(card);
    assert.equal($(card, ".aim-best").getAttribute("cx"), "-20");
  });
});

test("a map on its way when the card leaves comes anew when it returns", async () => {
  await withWorkers(HeldWorker, async () => {
    const { card, hass } = setup();
    await settle();
    const [held] = workers.slice(-1);
    card.remove();
    assert.equal(held.terminated, true);
    await settle();
    assert.equal($(card, ".heat-layer .aim-best"), null);
    window.Worker = FakeWorker;
    document.body.append(card);
    card.hass = nextDarts(hass, 404);
    await drawn(card);
    assert.equal(workers.at(-1) instanceof HeldWorker, false);
  });
});

test("without a worker of its own, the card computes the map itself", async () => {
  // A worker that fails to start, as under a strict content security policy.
  class FailingWorker extends FakeWorker {
    postMessage() {
      queueMicrotask(() => this.onerror(new window.Event("error")));
    }
  }
  await withWorkers(FailingWorker, async () => {
    const { card, hass } = setup();
    await drawn(card);
    const [failed] = workers.slice(-1);
    assert.equal(failed.terminated, true);
    // Later maps come from the card too.
    card.hass = nextDarts(hass, 405);
    await settle();
    assert.equal(workers.at(-1), failed);
  });
  // A page that allows no workers at all.
  class Refused {
    constructor() {
      throw new Error("refused");
    }
  }
  await withWorkers(Refused, async () => {
    const { card } = setup();
    await drawn(card);
  });
});
