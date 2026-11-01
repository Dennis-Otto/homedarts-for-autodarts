// The heatmap modes of the training card: beds, numbers and dart positions, of the session or a player.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, DEVICE, loadCards, makeHass, mount, settle, text, update, window, withLanguage } from "./dom.mjs";

await loadCards();

const SESSION = {
  "sensor.training_darts": { state: "6", attributes: { hits: { T20: 4, S20: 2 } } },
  "sensor.training_points": "280",
  "sensor.training_visits": "2",
  "switch.training_session": "on",
};
const PROFILES = {
  "sensor.player_profiles": {
    state: "2",
    attributes: {
      players: [
        { name: "Sam", darts_thrown: 0, hits: {} },
        { name: "Lea", hits: {} },
        { name: "Bo", darts_thrown: 3, hits: { S1: 3 } },
        { name: "Alex", darts_thrown: 9, hits: { T19: 6, D16: 3 } },
      ],
    },
  },
};
const GROUP = { target: "T20", darts: 40, offset_x: -6, offset_y: 2, r50: 38, r80: 61, change: -4 };

// A board that answers with the positions it logged; requests are kept in `asked`.
function board(asked, answers = {}) {
  return async (message) => {
    asked.push(message);
    const answer = answers[message.player ?? ""];
    if (answer instanceof Error) throw answer;
    return answer ?? { player: message.player ?? null, known: true, positions: [[0, 0.6], [0.02, 0.61]], spread: [GROUP] };
  };
}

const setup = (config = {}, callWS, states = {}) => {
  const hass = makeHass({ states: { ...SESSION, ...PROFILES, ...states }, ...(callWS ? { callWS } : {}) });
  return { hass, card: mount("homedarts-training-card", hass, config) };
};
const pressed = (card, group) =>
  $$(card, `.${group} button`).map((button) => [button.textContent, button.getAttribute("aria-pressed")]);
const click = (card, selector) => $(card, selector).dispatchEvent(new window.Event("click", { bubbles: true }));

test("the heatmap switches between beds, numbers and positions", async () => {
  const asked = [];
  const { card } = setup({}, board(asked));
  assert.deepEqual(pressed(card, "modes"), [
    ["Beds", "true"],
    ["Numbers", "false"],
    ["Positions", "false"],
    ["Aim", "false"],
  ]);
  assert.ok($(card, '.heat-layer path[d]'));
  assert.equal($(card, ".heat .groups").hidden, true);
  click(card, '[data-mode="numbers"]');
  assert.equal(pressed(card, "modes")[1][1], "true");
  // Numbers mode colours all four beds of the 20.
  assert.equal($$(card, ".heat-bed title").filter((title) => title.textContent.startsWith("20:")).length, 4);
  assert.equal(asked.length, 0);

  click(card, '[data-mode="positions"]');
  assert.deepEqual(asked, [{ type: "homedarts/positions", device_id: DEVICE }]);
  await settle();
  assert.equal($(card, "svg[role=img]").getAttribute("aria-label"), "Dartboard with the positions of the darts");
  assert.equal($$(card, ".heat-layer .position").length, 2);
  assert.ok($$(card, ".heat-layer .density rect").length > 10);
  assert.deepEqual([text(card, ".legend-min"), text(card, ".legend-max")], ["few", "many"]);
  assert.equal($(card, ".heat .groups").hidden, false);
  assert.equal(text(card, ".group-text"), "grouping 38 mm · 80 % within 61 mm · 6 mm left of center, 2 mm high");
  assert.equal(text(card, ".group-change"), "4 mm tighter");

  click(card, '[data-mode="beds"]');
  assert.deepEqual([text(card, ".legend-min"), $(card, ".heat .groups").hidden], ["1", true]);
  assert.equal($(card, "svg[role=img]").getAttribute("aria-label"), "Dartboard colored by how often each bed was hit");
});

test("a new palette colours the darts anew, without a new request", async () => {
  const asked = [];
  const { card } = setup({ mode: "positions" }, board(asked));
  await settle();
  const fills = () => new Set($$(card, ".heat-layer .density rect").map((cell) => cell.getAttribute("fill").slice(0, 1)));
  assert.deepEqual(fills(), new Set(["#"]));
  card.setConfig({ device_id: DEVICE, mode: "positions", heatmap_palette: "thermal" });
  await settle();
  assert.deepEqual(fills(), new Set(["h"]));
  assert.equal(asked.length, 1);
});

test("positions load again only when a visit was booked", async () => {
  const asked = [];
  const { hass, card } = setup({ mode: "positions" }, board(asked));
  await settle();
  assert.equal(asked.length, 1);
  card.hass = update(hass, { "sensor.training_points": "300" });
  await settle();
  assert.equal(asked.length, 1);
  card.hass = update(hass, { "sensor.training_visits": "3" });
  await settle();
  assert.equal(asked.length, 2);
});

test("a failed request keeps the last drawing and asks again with the next update", async () => {
  const asked = [];
  const answers = {};
  const { hass, card } = setup({ mode: "positions" }, board(asked, answers));
  await settle();
  assert.equal($$(card, ".heat-layer .position").length, 2);
  // Home Assistant restarts right after a visit: the request for its positions fails.
  answers[""] = new Error("connection lost");
  const booked = update(hass, { "sensor.training_visits": "3" });
  card.hass = booked;
  await settle();
  assert.equal(asked.length, 2);
  // The darts drawn before stay, and the card does not claim that there are none.
  assert.equal($$(card, ".heat-layer .position").length, 2);
  assert.notEqual(text(card, ".heat .groups"), "No dart positions yet.");
  assert.equal(text(card, ".group-text"), "grouping 38 mm · 80 % within 61 mm · 6 mm left of center, 2 mm high");
  // The next update asks again and draws what the board logged meanwhile.
  answers[""] = { positions: [[0, 0.6], [0.02, 0.61], [0.1, 0.5]], spread: [GROUP] };
  card.hass = update(booked, { "sensor.training_points": "300" });
  await settle();
  assert.equal(asked.length, 3);
  assert.deepEqual(asked.at(-1), { type: "homedarts/positions", device_id: DEVICE });
  assert.equal($$(card, ".heat-layer .position").length, 3);
  // Once answered, the same visit is not asked for again.
  card.hass = update(booked, { "sensor.training_points": "310" });
  await settle();
  assert.equal(asked.length, 3);
});

test("a request that fails after a newer one started leaves that one alone", async () => {
  const asked = [];
  const pending = [];
  const callWS = (message) => {
    asked.push(message);
    return new Promise((resolve, reject) => pending.push({ resolve, reject }));
  };
  const { hass, card } = setup({ mode: "positions" }, callWS);
  const booked = update(hass, { "sensor.training_visits": "3" });
  card.hass = booked;
  assert.equal(asked.length, 2);
  pending[0].reject(new Error("connection lost"));
  await settle();
  // The newer request still counts as on its way: the next update asks for nothing.
  card.hass = update(booked, { "sensor.training_points": "300" });
  await settle();
  assert.equal(asked.length, 2);
  pending[1].resolve({ positions: [[0, 0.6]], spread: [] });
  await settle();
  assert.equal($$(card, ".heat-layer .position").length, 1);
});

// The visit sensor: the darts on the board with their number in the visit, and the recent visits.
const visit = (throws, recent = []) => ({
  "sensor.local_visit_score": { state: "0", attributes: { throws, recent_visits: recent } },
});
const booked = (time) => ({ time, score: 60, darts: 3, segments: ["S20", "S20", "S20"] });
const pins = (card) => $$(card, ".heat-layer .position.live").map((pin) => [pin.getAttribute("cx"), pin.getAttribute("cy")]);
const dots = (card) => $$(card, ".heat-layer .position:not(.live)").length;

test("the darts of the current visit show at once while the session logs them", async () => {
  const asked = [];
  const throws = [
    { segment: "T20", dart: 1, x: 0, y: 0.6 },
    // A dart the board no longer counts to the visit, the bot's, one far off the board,
    // and darts without a position.
    { segment: "S5", x: -0.1, y: 0.8 },
    { segment: "S1", dart: 2, x: 0.1, y: 0.7, bot: true },
    { segment: "MISS", dart: 2, x: 3.5, y: 0 },
    { segment: "S19", dart: 2, manual: true },
    { segment: "S3", dart: 2, x: 0.2 },
  ];
  const { hass, card } = setup({ mode: "positions" }, board(asked), visit(throws));
  // The dart shows before the logged positions arrive, and counts for the density.
  assert.deepEqual(pins(card), [["0", "-102"]]);
  assert.ok($$(card, ".heat-layer .density rect").length > 10);
  assert.equal(text(card, ".legend-max"), "many");
  await settle();
  assert.deepEqual([dots(card), pins(card).length], [2, 1]);
  // The next dart joins the visit without asking the board again.
  let next = update(hass, visit([...throws, { segment: "D16", dart: 3, x: -0.55, y: -0.8 }]));
  card.hass = next;
  await settle();
  assert.deepEqual(pins(card), [["0", "-102"], ["-93.5", "136"]]);
  assert.equal(asked.length, 1);
  // Other darts change nothing: neither the drawing nor the questions.
  const layer = $(card, ".heat-layer").firstElementChild;
  next = update(next, { "sensor.local_visit_score": { state: "3", attributes: { throws: [...throws, { segment: "D16", dart: 3, x: -0.55, y: -0.8 }, { segment: "S7" }], recent_visits: [] } } });
  card.hass = next;
  assert.equal($(card, ".heat-layer").firstElementChild, layer);
  // A player's darts count once their visit is booked, like their hits.
  click(card, '[data-source="Alex"]');
  await settle();
  assert.deepEqual(pins(card), []);
  click(card, '[data-source=""]');
  await settle();
  assert.equal(pins(card).length, 2);
  // Outside a session nothing is logged, so nothing shows live.
  card.hass = update(next, { "switch.training_session": "off" });
  assert.deepEqual(pins(card), []);
});

test("a visit booked at the takeout loads again and keeps its darts on the board meanwhile", async () => {
  const pending = [];
  const asked = (message) => new Promise((resolve) => pending.push({ message, resolve }));
  const darts = [
    { segment: "T20", dart: 1, x: 0, y: 0.6 },
    { segment: "T20", dart: 2, x: 0.02, y: 0.61 },
    { segment: "S20", dart: 3, x: 0.05, y: 0.8 },
  ];
  const { hass, card } = setup({ mode: "positions" }, asked, {
    ...visit(darts, [booked("2026-09-28T08:03:06+00:00")]),
    "sensor.training_started": "2026-09-28T08:02:20+00:00",
  });
  pending[0].resolve({ positions: [[0.3, 0.3]], spread: [] });
  await settle();
  assert.deepEqual([dots(card), pins(card).length], [1, 3]);
  // New darts and more visits leave the logged positions as they are.
  let next = update(hass, { "sensor.training_visits": "3" });
  card.hass = next;
  assert.equal(pending.length, 1);
  // The takeout books the visit: the recent visits list it, and the board is empty.
  next = update(next, visit([], [booked("2026-09-28T08:03:31+00:00"), booked("2026-09-28T08:03:06+00:00")]));
  card.hass = next;
  assert.equal(pending.length, 2);
  // Until the logged darts arrive, the visit stays on the board.
  assert.deepEqual([dots(card), pins(card).length], [1, 3]);
  pending[1].resolve({ positions: [[0.3, 0.3], [0, 0.6], [0.02, 0.61], [0.05, 0.8]], spread: [] });
  await settle();
  assert.deepEqual([dots(card), pins(card).length], [4, 0]);
  // An undone visit leaves the recent visits and the log again; a new session starts empty.
  next = update(next, visit(darts, [booked("2026-09-28T08:03:06+00:00")]));
  card.hass = next;
  assert.equal(pending.length, 3);
  next = update(next, { "sensor.training_started": "2026-09-28T09:00:00+00:00", ...visit([], []) });
  card.hass = next;
  assert.equal(pending.length, 4);
  // An answer for a key the card moved past is dropped; the newest one shows.
  pending[3].resolve({ positions: [], spread: [] });
  await settle();
  assert.equal(text(card, ".heat .groups"), "No dart positions yet.");
  pending[2].resolve({ positions: [[0.3, 0.3]], spread: [] });
  await settle();
  assert.equal(dots(card), 0);
});

test("the heatmap shows a player's own darts", async () => {
  const asked = [];
  const { card } = setup({}, board(asked));
  // Players who threw no dart are not offered.
  assert.deepEqual(pressed(card, "sources"), [
    ["Session", "true"],
    ["Alex", "false"],
    ["Bo", "false"],
  ]);
  click(card, '[data-source="Alex"]');
  assert.deepEqual(pressed(card, "sources")[1], ["Alex", "true"]);
  const titles = $$(card, ".heat-bed title").map((title) => title.textContent);
  assert.ok(titles.some((title) => title.startsWith("T19: 6 hits")));
  assert.ok(!titles.some((title) => title.startsWith("T20")));
  assert.deepEqual(
    $$(card, ".top-row").map((row) => row.textContent),
    ["T196× · 67%", "D163× · 33%"]
  );
  click(card, '[data-mode="positions"]');
  assert.deepEqual(asked, [{ type: "homedarts/positions", device_id: DEVICE, player: "Alex" }]);
  click(card, '[data-source=""]');
  assert.deepEqual(asked.at(-1), { type: "homedarts/positions", device_id: DEVICE });
  await settle();
  assert.equal($$(card, ".heat-layer .position").length, 2);
});

test("the player of the configuration comes first, known or not", async () => {
  const asked = [];
  const answers = { Kim: { player: "Kim", known: false, positions: [], spread: [] } };
  const { card } = setup({ mode: "positions", player: " Kim " }, board(asked, answers));
  assert.deepEqual(pressed(card, "sources"), [
    ["Session", "false"],
    ["Alex", "false"],
    ["Bo", "false"],
    ["Kim", "true"],
  ]);
  await settle();
  assert.deepEqual(asked, [{ type: "homedarts/positions", device_id: DEVICE, player: "Kim" }]);
  assert.equal(text(card, ".heat .groups"), "No dart positions yet.");
  assert.equal(text(card, ".legend-max"), "–");
  assert.equal($$(card, ".top-row").length, 0);
});

test("without switches, a player or positions the heatmap still draws", async () => {
  const asked = [];
  const answers = { "": new Error("gone") };
  const { card } = setup({ mode: "positions", show_heatmap_controls: false }, board(asked, answers), {
    "sensor.player_profiles": { state: "0", attributes: {} },
  });
  assert.equal($(card, ".modes"), null);
  assert.equal($(card, ".sources"), null);
  await settle();
  // A board that cannot answer, such as one being removed, has not said that it has no
  // positions: the heatmap waits for them.
  assert.equal(asked.length, 1);
  assert.equal($(card, ".heat .groups").hidden, true);
  assert.equal(text(card, ".heat .groups"), "");
  // Without the WebSocket, the heatmap waits for positions.
  const plain = setup({ mode: "positions" }).card;
  assert.equal($$(plain, ".heat-layer .position").length, 0);
  assert.equal($(plain, ".heat .groups").hidden, true);
  assert.equal($(plain, ".sources").hidden, false);
  // A player without profiles shows no hits.
  const lonely = setup({ player: "Kim" }, undefined, { "sensor.player_profiles": { state: "0", attributes: {} } }).card;
  assert.deepEqual(pressed(lonely, "sources"), [
    ["Session", "false"],
    ["Kim", "true"],
  ]);
  assert.equal($$(lonely, ".heat-bed").length, 0);
  // An unknown mode in the configuration shows the beds.
  assert.equal($(setup({ mode: "rings" }).card, '[data-mode="beds"]').getAttribute("aria-pressed"), "true");
});

test("an answer for a player the card no longer shows is dropped", async () => {
  let release;
  const asked = [];
  const slow = async (message) => {
    asked.push(message);
    if (message.player === "Alex") await new Promise((resolve) => (release = resolve));
    return { positions: [[0.5, 0.5]], spread: [] };
  };
  const { card } = setup({ mode: "positions" }, slow);
  click(card, '[data-source="Alex"]');
  click(card, '[data-source=""]');
  await settle();
  release();
  await settle();
  assert.equal(asked.length, 3);
  assert.equal($$(card, ".heat-layer .position").length, 1);
  assert.equal($(card, ".heat-layer .position").getAttribute("cx"), "85");
  // Clicks beside the buttons change nothing.
  click(card, ".modes");
  click(card, ".sources");
  assert.equal(asked.length, 3);
});

test("the heatmap switches speak German", () => {
  const hass = withLanguage(makeHass({ states: { ...SESSION, ...PROFILES } }), "de");
  const card = mount("homedarts-training-card", hass, {});
  assert.deepEqual(
    pressed(card, "modes").map(([name]) => name),
    ["Felder", "Zahlen", "Positionen", "Zielpunkt"]
  );
  assert.equal(pressed(card, "sources")[0][0], "Session");
  assert.equal($(card, ".modes").getAttribute("aria-label"), "Trefferbild");
  assert.equal($(card, ".sources").getAttribute("aria-label"), "Wessen Darts");
});

test("a new configuration shows its own mode and player", () => {
  const { hass, card } = setup({ mode: "numbers" });
  click(card, '[data-mode="beds"]');
  $(card, '[data-source="Alex"]').focus();
  click(card, '[data-source="Alex"]');
  // The button keeps the focus and its place, for keyboards and fingers.
  assert.equal(card.shadowRoot.activeElement.dataset.focus, "source:Alex");
  card.setConfig({ type: "custom:homedarts-training-card", mode: "numbers" });
  card.hass = hass;
  assert.equal($(card, '[data-mode="numbers"]').getAttribute("aria-pressed"), "true");
  assert.equal($(card, '[data-source=""]').getAttribute("aria-pressed"), "true");
});

test("positions without a known aim have no groupings to show", async () => {
  const answers = { "": { positions: [[0.1, 0.2]], spread: [] } };
  const { card } = setup({ mode: "positions" }, board([], answers));
  await settle();
  assert.equal($$(card, ".heat-layer .position").length, 1);
  assert.equal($(card, ".heat .groups").hidden, true);
});

test("positions stay unloaded without a heatmap, and a late answer waits for its mode", async () => {
  const asked = [];
  // Without the heatmap, positions are neither asked for nor drawn.
  const hidden = setup({ show_heatmap: false, mode: "positions" }, board(asked)).card;
  await settle();
  assert.deepEqual(asked, []);
  assert.equal($(hidden, ".heat-layer"), null);
  // An answer that arrives after a switch to beds leaves the beds on the board.
  const pending = [];
  const { card } = setup({}, (message) => new Promise((resolve) => pending.push({ message, resolve })));
  click(card, '[data-mode="positions"]');
  click(card, '[data-mode="beds"]');
  pending[0].resolve({ positions: [[0, 0.6]], spread: [] });
  await settle();
  assert.equal($$(card, ".heat-layer .position").length, 0);
  assert.ok($(card, ".heat-layer path.heat-bed"));
  assert.equal(text(card, ".legend-min"), "1");
  // Back in positions mode, the answer shows without asking again.
  click(card, '[data-mode="positions"]');
  assert.equal(pending.length, 1);
  assert.equal($$(card, ".heat-layer .position").length, 1);
  // An answer after the heatmap was switched off is kept, and drawn nowhere.
  const late = [];
  const off = setup({ mode: "positions" }, () => new Promise((resolve) => late.push(resolve))).card;
  off.setConfig({ type: "custom:homedarts-training-card", mode: "positions", show_heatmap: false });
  off.hass = makeHass({ states: { ...SESSION, ...PROFILES }, callWS: () => new Promise(() => {}) });
  late[0]({ positions: [[0, 0.6]], spread: [] });
  await settle();
  assert.equal($(off, ".heat-layer"), null);
});

test("the density of the positions is drawn once per answer, not with every update", async () => {
  const { hass, card } = setup({ mode: "positions" }, board([]));
  await settle();
  const layer = $(card, ".heat-layer");
  const drawn = layer.innerHTML;
  const first = layer.firstElementChild;
  // Other state changes keep the drawing as it is.
  card.hass = update(hass, { "sensor.training_points": "300" });
  assert.equal(layer.innerHTML, drawn);
  assert.equal(layer.firstElementChild, first);
});

test("a player's most hit beds are shares of the hits the profile counted", () => {
  // Darts from before an upgrade count in darts_thrown but have no hits.
  const profiles = {
    "sensor.player_profiles": {
      state: "1",
      attributes: { players: [{ name: "Alex", darts_thrown: 5000, hits: { T20: 6, S20: 3, MISS: 3 } }] },
    },
  };
  const { card } = setup({ player: "Alex" }, undefined, profiles);
  assert.deepEqual(
    $$(card, ".top-row .count").map((count) => count.textContent),
    ["6× · 50%", "3× · 25%"]
  );
});

test("the hits of every bed can be read and tapped, not only hovered", () => {
  const { hass, card } = setup();
  // A list for screen readers, most hit first, every bed once.
  assert.deepEqual(
    $$(card, ".heat-list li").map((item) => item.textContent),
    ["T20: 4 hits · 66.7%", "S20: 2 hits · 33.3%"]
  );
  const caption = $(card, ".heat-caption");
  assert.equal(caption.getAttribute("aria-live"), "polite");
  assert.equal(caption.textContent, "");
  // A tap on a bed tells its hits; a tap beside the beds clears it.
  $(card, ".heat-layer path.heat-bed").dispatchEvent(new window.Event("click", { bubbles: true }));
  assert.equal(caption.textContent, "T20: 4 hits · 66.7%");
  $(card, ".heat-frame svg").dispatchEvent(new window.Event("click", { bubbles: true }));
  assert.equal(caption.textContent, "");
  $(card, ".heat-layer path.heat-bed").dispatchEvent(new window.Event("click", { bubbles: true }));
  // New hits change the board, and the told hits go.
  card.hass = update(hass, { "sensor.training_darts": { state: "7", attributes: { hits: { T20: 5, S20: 2 } } } });
  assert.equal(caption.textContent, "");
  card.hass = update(hass, { "sensor.training_visits": "3" });
  assert.equal(caption.textContent, "");
  // In numbers mode every number is listed once; positions have no beds to list.
  click(card, '[data-mode="numbers"]');
  assert.deepEqual(
    $$(card, ".heat-list li").map((item) => item.textContent),
    ["20: 6 hits · 100.0%"]
  );
  click(card, '[data-mode="positions"]');
  assert.deepEqual($$(card, ".heat-list li"), []);
});

test("darts beyond the board and its number ring are not drawn, logged or live", async () => {
  // The edge of the number ring is 225 mm from the bull, 1.32 as positions count.
  const logged = [
    [0, 1.3],
    [0.95, 0.95],
    [2.5, 0],
  ];
  const throws = [
    { segment: "S20", dart: 1, x: 1.2, y: 0.5 },
    { segment: "MISS", dart: 2, x: 1, y: 1 },
  ];
  const { card } = setup({ mode: "positions" }, board([], { "": { positions: logged, spread: [] } }), visit(throws));
  await settle();
  assert.deepEqual(
    $$(card, ".heat-layer .position:not(.live)").map((dot) => [dot.getAttribute("cx"), dot.getAttribute("cy")]),
    [["0", "-221"]]
  );
  assert.deepEqual(pins(card), [["204", "-85"]]);
  // No density far off the board either.
  const cells = $$(card, ".heat-layer .density rect").map((cell) => Math.hypot(Number(cell.getAttribute("x")), Number(cell.getAttribute("y"))));
  assert.ok(Math.max(...cells) < 225 + 40);
  // A board that only logged darts beyond its edge has no positions to show.
  const { card: missed } = setup({ mode: "positions" }, board([], { "": { positions: [[2.5, 0]], spread: [] } }));
  await settle();
  assert.ok($$(missed, ".empty-hint").some((hint) => hint.textContent === "No dart positions yet."));
  assert.equal($$(missed, ".heat-layer .position").length, 0);
});
