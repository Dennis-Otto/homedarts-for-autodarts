// The live card in a browser DOM: the visit on the board, statistics, games and controls.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  $,
  $$,
  DEVICE,
  READY,
  loadCards,
  makeHass,
  moreInfo,
  mount,
  text,
  update,
  window,
  withLanguage,
} from "./dom.mjs";

const { bedPath } = await loadCards();

const dart = (number, multiplier, bed, x, y) => ({ number, multiplier, bed, x, y });
const T20 = dart(20, 3, "Triple", 0.035, 0.608);
const S5 = dart(5, 1, "SingleOuter", -0.24, 0.76);
const BULL = dart(25, 2, "Double", 0.012, -0.02);
const visit = (throws, extra = {}) => ({
  state: String(throws.reduce((sum, item) => sum + item.number * item.multiplier, 0)),
  attributes: { throws, recent_visits: [], ...extra },
});
const setup = (states = {}, config = {}, options = {}) => {
  const hass = makeHass({ states: { ...READY, ...states }, ...options });
  return { hass, card: mount("homedarts-card", hass, config) };
};
const practice = (state, attributes) => ({ "sensor.practice_remaining": { state, attributes } });
const drill = (state, attributes) => ({ "sensor.practice_target": { state, attributes } });
const paths = (card, group) => $$(card, `.${group} path`).map((path) => path.getAttribute("d"));
const scores = (card) =>
  $$(card, ".player-score").map((row) => [row.className, ...[...row.children].map((cell) => cell.textContent)]);

test("the live card rejects a missing configuration", () => {
  const card = document.createElement("homedarts-card");
  assert.throws(() => card.setConfig(null), /Invalid configuration/);
  assert.throws(() => card.setConfig("homedarts"), /Invalid configuration/);
});

test("the card waits for both its configuration and Home Assistant", () => {
  const card = document.createElement("homedarts-card");
  card.hass = makeHass({ states: READY });
  assert.equal(card.shadowRoot.innerHTML, "");
  card.setConfig({});
  assert.equal(text(card, ".title"), "Dartboard");
});

test("without an Autodarts board the card asks for a device, in English and German", () => {
  const card = mount("homedarts-card", makeHass());
  assert.equal(text(card, ".message"), "No board found. Select a device in the card settings.");
  // Further updates of Home Assistant leave the message alone.
  const message = $(card, ".message");
  card.hass = makeHass();
  assert.equal($(card, ".message"), message);
  card.hass = withLanguage(makeHass(), "de");
  assert.equal(text(card, ".message"), "Kein Board gefunden. Wähle ein Gerät in den Karteneinstellungen.");
  // Once a board appears, the card is built.
  card.hass = makeHass({ states: READY });
  assert.equal(text(card, ".title"), "Dartboard");
  assert.equal($(card, ".message"), null);
});

test("a deleted board is not mistaken for an unreachable one", () => {
  const { card } = setup({}, { device_id: "removed-device" });
  assert.equal(text(card, ".message"), "No board found. Select a device in the card settings.");
  assert.equal($(card, ".pill"), null);
  // Hosts without a device registry trust the configured board.
  const hass = { ...makeHass({ states: READY }), devices: undefined };
  const bare = mount("homedarts-card", hass, { device_id: DEVICE });
  assert.equal(text(bare, ".title"), "HomeDarts");
  assert.equal(text(bare, ".pill"), "Ready – throw!");
});

test("the title is the configured title, the user's board name or the device name", () => {
  assert.equal(text(setup().card, ".title"), "Dartboard");
  assert.equal(text(setup({}, {}, { device: { name_by_user: "Garage" } }).card, ".title"), "Garage");
  assert.equal(text(setup({}, { title: "Pub" }, { device: { name_by_user: "Garage" } }).card, ".title"), "Pub");
  assert.equal(text(setup({}, {}, { device: { name: null } }).card, ".title"), "HomeDarts");
});

test("the status pill and colour follow the board", () => {
  const { hass, card } = setup();
  assert.equal(text(card, ".pill"), "Ready – throw!");
  // The theme's colours, with the card's own as fallback.
  assert.equal(card.style.getPropertyValue("--ad-status"), "var(--success-color, #43a047)");
  card.hass = update(hass, { "binary_sensor.local_connected": "off" });
  assert.equal(text(card, ".pill"), "Board unreachable");
  assert.equal(card.style.getPropertyValue("--ad-status"), "var(--error-color, #e53935)");
  card.hass = update(hass, { "sensor.num_throws": "3" });
  assert.equal(text(card, ".pill"), "Remove your darts");
  assert.equal(card.style.getPropertyValue("--ad-status"), "var(--amber-color, #fbc02d)");
  const pills = [
    [{ "binary_sensor.calibrating": "on" }, "Calibrating", "var(--purple-color, #8e24aa)"],
    [{ "sensor.local_status": "Starting" }, "Starting detection", "var(--warning-color, #fb8c00)"],
    [{ "sensor.local_status": "Stopping" }, "Stopping detection", "var(--warning-color, #fb8c00)"],
    [{ "binary_sensor.takeout_partial": "on" }, "Removing darts", "var(--amber-color, #fbc02d)"],
    [{ "binary_sensor.hand_detected": "on" }, "Hand at the board", "var(--amber-color, #fbc02d)"],
  ];
  for (const [states, pill, color] of pills) {
    card.hass = update(hass, states);
    assert.deepEqual([text(card, ".pill"), card.style.getPropertyValue("--ad-status")], [pill, color]);
  }
});

test("the current visit shows each dart, its points and where it landed", () => {
  const { card } = setup({ "sensor.local_visit_score": visit([T20, S5, BULL]), "sensor.num_throws": "3" });
  assert.equal(text(card, ".score"), "115");
  assert.equal(text(card, ".progress"), "Dart 3 of 3");
  assert.deepEqual(
    $$(card, ".slot").map((slot) => [slot.className, slot.querySelector(".segment").textContent]),
    [
      ["slot triple", "T20"],
      ["slot single", "S5"],
      ["slot bull latest", "Bull"],
    ]
  );
  assert.deepEqual(
    $$(card, ".slot .value").map((value) => value.textContent),
    ["60 points", "5 points", "50 points"]
  );
  assert.deepEqual(paths(card, "hits"), [bedPath("T20"), bedPath("SO5"), bedPath("Bull")]);
  const markers = $$(card, ".darts .dart");
  assert.deepEqual(
    markers.map((marker) => [marker.getAttribute("class"), marker.getAttribute("transform"), marker.textContent]),
    [
      ["dart", "translate(5.95 -103.36)", "1"],
      ["dart", "translate(-40.8 -129.2)", "2"],
      ["dart latest", "translate(2.04 3.4)", "3"],
    ]
  );
  assert.equal($(card, "svg").getAttribute("aria-label"), "Dartboard with the current visit: T20, S5, Bull");
});

test("a dart beyond the board is drawn at its edge", () => {
  const { card } = setup({ "sensor.local_visit_score": visit([dart(6, 0, "Outside", 2, 0)]) });
  assert.equal($(card, ".darts .dart").getAttribute("transform"), "translate(221 0)");
  assert.deepEqual(paths(card, "hits"), [bedPath("M6")]);
  assert.equal($(card, ".slot").className, "slot miss latest");
  assert.equal(text(card, ".slot .segment"), "Miss");
});

test("without darts the board and slots are empty", () => {
  const { card } = setup({ "sensor.local_visit_score": visit([]) });
  assert.equal(text(card, ".score"), "0");
  assert.equal(text(card, ".progress"), "");
  assert.deepEqual(
    $$(card, ".slot").map((slot) => [slot.className, slot.querySelector(".segment").textContent]),
    [
      ["slot empty", "–"],
      ["slot empty", "–"],
      ["slot empty", "–"],
    ]
  );
  assert.deepEqual(paths(card, "hits"), []);
  assert.equal($(card, "svg").getAttribute("aria-label"), "Dartboard with the current visit");
  const idle = setup({ "sensor.local_visit_score": "unavailable" }).card;
  assert.equal(text(idle, ".score"), "–");
});

test("older integrations without dart details show the last segment", () => {
  const { hass, card } = setup({
    "sensor.local_visit_score": "unknown",
    "sensor.last_throw": "T20",
    "sensor.num_throws": "2",
  });
  assert.equal(text(card, ".score"), "60");
  assert.equal(text(card, ".progress"), "Dart 2 of 3");
  assert.deepEqual(
    $$(card, ".slot").map((slot) => [slot.className, slot.querySelector(".segment").textContent]),
    [
      ["slot unknown", "?"],
      ["slot triple latest", "T20"],
      ["slot empty", "–"],
    ]
  );
  assert.deepEqual(paths(card, "hits"), [bedPath("T20")]);
  // No throws and no markers without positions.
  assert.equal($$(card, ".darts .dart").length, 0);
  card.hass = update(hass, { "sensor.num_throws": "0" });
  assert.equal(text(card, ".score"), "–");
});

test("the last visits appear as coloured scores, newest first", () => {
  const recent = [
    { score: 180, darts: 3, segments: ["T20", "T20", "T20"] },
    { score: 45, darts: 3, segments: ["S20", "S5", "S20"] },
  ];
  const { hass, card } = setup({ "sensor.local_visit_score": visit([], { recent_visits: recent }) });
  assert.equal($(card, ".recent").hidden, false);
  assert.deepEqual(
    $$(card, ".recent-visit").map((item) => [item.textContent, item.getAttribute("style"), item.title]),
    [
      ["180", "--bucket:#ffd60a", "T20 · T20 · T20 = 180"],
      ["45", "--bucket:#8a8f98", "S20 · S5 · S20 = 45"],
    ]
  );
  card.hass = update(hass, { "sensor.local_visit_score": visit([]) });
  assert.equal($(card, ".recent").hidden, true);
  assert.equal($(setup({}, { show_recent: false }).card, ".recent"), null);
});

test("highlight marks every dart, the last one or none, and blinking can be switched off", () => {
  const states = { "sensor.local_visit_score": visit([T20, S5, BULL]) };
  assert.equal($(setup(states).card, ".hits").getAttribute("class"), "hits blink");
  assert.equal($(setup(states, { blink: false }).card, ".hits").getAttribute("class"), "hits");
  assert.deepEqual(paths(setup(states, { highlight: "last" }).card, "hits"), [bedPath("Bull")]);
  assert.deepEqual(paths(setup(states, { highlight: "none" }).card, "hits"), []);
});

test("markers, numbers, board style and layout follow the options", () => {
  const states = { "sensor.local_visit_score": visit([T20]) };
  const plain = setup(states, { show_markers: false, show_numbers: false, board_style: "flat" }).card;
  assert.equal($$(plain, ".darts .dart").length, 0);
  assert.equal($(plain, ".numbers"), null);
  assert.equal($(plain, ".face path").getAttribute("stroke"), null);
  assert.equal($(plain, ".face circle").getAttribute("fill"), "#212121");

  const classic = setup(states).card;
  assert.equal($$(classic, ".numbers text").length, 20);
  assert.equal($(classic, ".face path").getAttribute("stroke"), "#b8bcc2");
  assert.equal($(classic, ".layout").getAttribute("class"), "layout auto");
  assert.equal(classic.getCardSize(), 7);

  const board = setup(states, { layout: "board" }).card;
  assert.equal($(board, ".layout").getAttribute("class"), "layout board-only");
  const vertical = setup(states, { layout: "vertical" }).card;
  assert.equal($(vertical, ".layout").getAttribute("class"), "layout vertical");
  assert.equal(vertical.getCardSize(), 10);
});

test("session statistics show the training totals and when the session started", () => {
  const { card } = setup({
    "sensor.training_darts": "30",
    "sensor.training_points": "456",
    "sensor.training_average": "45.6",
    "sensor.training_triples": "4",
    "sensor.training_bulls": "1",
    "sensor.training_scores_180": "0",
    "sensor.training_started": "2026-09-26T14:30:00+00:00",
  });
  assert.deepEqual(
    $$(card, ".stat").map((stat) => [stat.dataset.stat, stat.querySelector(".value").textContent]),
    [
      ["darts", "30"],
      ["average", "45.6"],
      ["triples", "4"],
      ["bulls", "1"],
      ["max", "0"],
    ]
  );
  assert.match(text(card, ".since"), /^since 09\/26, 2:30\sPM$/);
});

test("without an average sensor the average is computed from points and darts", () => {
  const { hass, card } = setup({
    "sensor.training_darts": "30",
    "sensor.training_points": "450",
    "sensor.training_started": "unknown",
  });
  assert.equal(text(card, '[data-stat="average"] .value'), "45.0");
  assert.equal(text(card, ".since"), "");
  card.hass = update(hass, { "sensor.training_darts": "0" });
  assert.equal(text(card, '[data-stat="average"] .value'), "–");
  assert.equal(text(card, '[data-stat="triples"] .value'), "–");
});

test("statistics, connection and controls can be hidden", () => {
  const bare = setup({}, { show_stats: false, show_connection: false, show_controls: false }).card;
  assert.equal($(bare, ".session"), null);
  assert.equal($(bare, ".footer"), null);
  const chipsOnly = setup({}, { show_controls: false }).card;
  assert.equal($$(chipsOnly, ".chip").length, 3);
  assert.equal($(chipsOnly, ".controls"), null);
  const controlsOnly = setup({}, { show_connection: false }).card;
  assert.equal($(controlsOnly, ".chips"), null);
  assert.equal($$(controlsOnly, ".controls button").length, 3);
});

test("connection chips show the links and a camera problem, and open more-info", () => {
  const { hass, card } = setup({ "binary_sensor.realtime_connected": "off" });
  assert.deepEqual(
    $$(card, ".chip").map((chip) => [chip.className, chip.textContent, chip.dataset.entity]),
    [
      ["chip on", "Board Manager", "binary_sensor.dartboard_local_connected"],
      ["chip off", "Realtime", "binary_sensor.dartboard_realtime_connected"],
      ["chip on", "Cameras", "binary_sensor.dartboard_cameras_active"],
    ]
  );
  const opened = moreInfo(card);
  $$(card, ".chip")[1].click();
  $(card, ".chips").click();
  assert.deepEqual(opened, ["binary_sensor.dartboard_realtime_connected"]);

  // Beside the colour, the class draws the dot's shape for every state, and the name says
  // the state in Home Assistant's words: those of connectivity, and of running for cameras.
  const named = (states, options) =>
    $$(setup(states, {}, options).card, ".chip").map((chip) => [chip.className, chip.getAttribute("aria-label")]);
  const every = (state) => ({
    "binary_sensor.local_connected": state,
    "binary_sensor.realtime_connected": state,
    "binary_sensor.cameras_active": state,
  });
  for (const [state, cls, link, cameras] of [
    ["on", "chip on", "Connected", "Running"],
    ["off", "chip off", "Disconnected", "Not running"],
    ["unavailable", "chip off unavailable", "Unavailable", "Unavailable"],
    ["unknown", "chip off unavailable", "Unknown", "Unknown"],
  ]) {
    assert.deepEqual(named(every(state)), [
      [cls, `Board Manager: ${link}`],
      [cls, `Realtime: ${link}`],
      [cls, `Cameras: ${cameras}`],
    ]);
  }
  assert.deepEqual(
    named(every("off"), { language: "de" }).map(([, name]) => name),
    ["Board Manager: Getrennt", "Echtzeit: Getrennt", "Kameras: Außer Betrieb"]
  );
  assert.deepEqual(
    named(every("on"), { language: "fr" }).map(([, name]) => name),
    ["Board Manager\u00a0: Connecté", "Temps réel\u00a0: Connecté", "Caméras\u00a0: En cours"]
  );
  // The live card's chips have no tooltip; the camera problem says itself in its text.
  assert.equal($(card, ".chip").title, "");

  card.hass = update(hass, { "binary_sensor.camera_problem": "on" });
  assert.deepEqual(
    $$(card, ".chip").map((chip) => [chip.className, chip.textContent, chip.getAttribute("aria-label")]).at(-1),
    ["chip alert", "Check cameras", null]
  );
  assert.equal(text(card, ".pill"), "Check cameras");

  // Entities the board lacks have no chip.
  const hassWithout = makeHass({ states: { "binary_sensor.local_connected": "on" } });
  const lean = mount("homedarts-card", hassWithout);
  assert.deepEqual(
    $$(lean, ".chip").map((chip) => chip.textContent),
    ["Board Manager"]
  );
});

test("the detection button stops and starts detection with the switch", () => {
  const { hass, card } = setup();
  const toggle = $(card, '[data-action="toggle"]');
  assert.equal(toggle.textContent, "Stop detection");
  assert.equal(toggle.classList.contains("stop"), true);
  assert.equal(toggle.disabled, false);
  toggle.click();
  card.hass = update(hass, { "switch.detection": "off" });
  assert.equal(text(card, ".pill"), "Detection stopped");
  assert.equal(toggle.textContent, "Start detection");
  assert.equal(toggle.classList.contains("stop"), false);
  toggle.click();
  assert.deepEqual(hass.calls, [
    ["switch", "turn_off", { entity_id: "switch.dartboard_detection" }],
    ["switch", "turn_on", { entity_id: "switch.dartboard_detection" }],
  ]);
});

test("without a detection switch the button follows the board status, so detection also stops", () => {
  const { "switch.detection": _, ...states } = READY;
  const hass = makeHass({ states });
  const card = mount("homedarts-card", hass);
  const toggle = $(card, '[data-action="toggle"]');
  // The board detects darts: the button stops detection.
  assert.deepEqual([toggle.textContent, toggle.classList.contains("stop")], ["Stop detection", true]);
  toggle.click();
  assert.deepEqual(hass.calls, [["button", "press", { entity_id: "button.dartboard_stop" }]]);
  // Stopped, it starts it again.
  card.hass = update(hass, { "sensor.local_status": "Stopped" });
  assert.deepEqual([toggle.textContent, toggle.classList.contains("stop")], ["Start detection", false]);
  toggle.click();
  assert.deepEqual(hass.calls.at(-1), ["button", "press", { entity_id: "button.dartboard_start" }]);
});

test("controls are disabled while the board is offline or lacks the entity", () => {
  const offline = setup({ "binary_sensor.local_connected": "off" }).card;
  assert.deepEqual(
    $$(offline, ".controls button").map((button) => button.disabled),
    [true, true, true]
  );
  const lean = mount("homedarts-card", makeHass({ states: { "binary_sensor.local_connected": "on" } }));
  assert.deepEqual(
    $$(lean, ".controls button").map((button) => [button.textContent, button.disabled]),
    [
      ["Stop detection", true],
      ["Reset detection", true],
      ["Calibrate", true],
    ]
  );
});

test("a failing service call is left to Home Assistant's own error toast", async () => {
  const { hass, card } = setup();
  const failed = [];
  card.hass = {
    ...hass,
    callService: (...call) => {
      failed.push(call);
      return Promise.reject(new Error("Board unreachable"));
    },
  };
  $(card, '[data-action="toggle"]').click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(failed, [["switch", "turn_off", { entity_id: "switch.dartboard_detection" }]]);
});

test("reset and calibration need a second tap within four seconds", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { hass, card } = setup();
  const reset = $(card, '[data-action="reset"]');
  const calibrate = $(card, '[data-action="calibrate"]');
  reset.click();
  assert.equal(reset.textContent, "Confirm?");
  assert.equal(reset.classList.contains("confirm"), true);
  assert.deepEqual(hass.calls, []);
  reset.click();
  assert.deepEqual(hass.calls, [["button", "press", { entity_id: "button.dartboard_reset" }]]);
  assert.equal(reset.textContent, "Reset detection");
  assert.equal(reset.classList.contains("confirm"), false);

  // A first tap expires after four seconds.
  calibrate.click();
  t.mock.timers.tick(3999);
  assert.equal(calibrate.textContent, "Confirm?");
  t.mock.timers.tick(1);
  assert.equal(calibrate.textContent, "Calibrate");
  calibrate.click();
  assert.equal(hass.calls.length, 1);

  // Tapping another action asks again for that one.
  reset.click();
  assert.equal(calibrate.textContent, "Calibrate");
  assert.equal(reset.textContent, "Confirm?");
  reset.click();
  assert.deepEqual(hass.calls.at(-1), ["button", "press", { entity_id: "button.dartboard_reset" }]);
});

test("removing the card forgets a pending confirmation", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { hass, card } = setup();
  $(card, '[data-action="reset"]').click();
  card.remove();
  document.body.append(card);
  // The button no longer asks for a confirmation that would not come.
  assert.deepEqual(
    [text(card, '[data-action="reset"]'), $(card, '[data-action="reset"]').classList.contains("confirm")],
    ["Reset detection", false]
  );
  $(card, '[data-action="reset"]').click();
  assert.deepEqual(hass.calls, []);
  assert.equal(text(card, '[data-action="reset"]'), "Confirm?");
});

test("a card in the editor preview ignores taps", () => {
  const { hass, card } = setup({ "sensor.local_visit_score": visit([T20]) });
  assert.equal(card.preview, false);
  card.preview = true;
  assert.equal(card.preview, true);
  const opened = moreInfo(card);
  for (const action of ["toggle", "reset", "reset", "calibrate"]) $(card, `[data-action="${action}"]`).click();
  $(card, ".chip").click();
  $(card, "svg").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  assert.deepEqual(hass.calls, []);
  assert.deepEqual(opened, []);
  assert.equal(text(card, '[data-action="reset"]'), "Reset detection");
});

test("the board is a picture: a tap opens nothing, the chips open their entity's details", () => {
  const { card } = setup({ "sensor.local_visit_score": visit([]) });
  const svg = $(card, "svg");
  assert.equal(svg.getAttribute("role"), "img");
  assert.equal(svg.hasAttribute("tabindex"), false);
  const events = [];
  document.addEventListener("hass-more-info", (event) => events.push(event), { once: true });
  const opened = moreInfo(card);
  svg.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  assert.deepEqual(opened, []);
  $(card, ".chip").click();
  const id = opened[0];
  assert.equal(opened.length, 1);
  // The event leaves the shadow root for Home Assistant's dialog.
  assert.equal(events.length, 1);
  assert.deepEqual([events[0].bubbles, events[0].composed, events[0].detail], [true, true, { entityId: id }]);
});

test("the card redraws only when a state it shows changes", () => {
  const { hass, card } = setup({ "sensor.training_visits": "10" });
  $(card, ".title").textContent = "stale";
  const quiet = update(hass, { "sensor.training_visits": "11" });
  card.hass = quiet;
  assert.equal(text(card, ".title"), "stale");
  card.hass = update(quiet, { "sensor.local_status": "Takeout in progress" });
  assert.equal(text(card, ".title"), "Dartboard");
  assert.equal(text(card, ".pill"), "Removing darts");

  // A new language or configuration builds the card again.
  $(card, ".title").textContent = "stale";
  card.hass = withLanguage(update(quiet, { "sensor.local_status": "Takeout in progress" }), "de");
  assert.equal(text(card, ".title"), "Dartboard");
  assert.equal(text(card, ".pill"), "Darts werden entnommen");
  card.setConfig({ title: "Pub" });
  assert.equal(text(card, ".title"), "Pub");
});

test("the card speaks German", () => {
  const { card } = setup(
    {
      "sensor.local_visit_score": visit([T20]),
      "sensor.training_average": "45.6",
      "sensor.training_started": "2026-09-26T14:30:00+00:00",
    },
    {},
    { language: "de-DE" }
  );
  assert.equal(text(card, ".pill"), "Bereit – wirf!");
  assert.equal(text(card, ".visit-label"), "Aktuelle Aufnahme");
  assert.equal(text(card, ".progress"), "Dart 1 von 3");
  assert.equal(text(card, ".slot .value"), "60 Punkte");
  assert.equal(text(card, '[data-stat="average"] .value'), "45,6");
  assert.equal(text(card, ".since"), "seit 26.09., 14:30");
  assert.deepEqual(
    $$(card, ".controls button").map((button) => button.textContent),
    ["Erkennung stoppen", "Erkennung zurücksetzen", "Kalibrieren"]
  );
});

test("Home Assistant without a locale uses its language setting", () => {
  const states = {
    ...READY,
    "sensor.training_average": "45.6",
    "sensor.training_started": "2026-09-26T14:30:00+00:00",
  };
  const german = mount("homedarts-card", { ...makeHass({ states }), locale: undefined, language: "de" });
  assert.equal(text(german, ".pill"), "Bereit – wirf!");
  assert.equal(text(german, '[data-stat="average"] .value'), "45,6");
  assert.equal(text(german, ".since"), "seit 26.09., 14:30");
  const unset = mount("homedarts-card", { ...makeHass({ states }), locale: undefined, language: undefined });
  assert.equal(text(unset, ".pill"), "Ready – throw!");
});

test("accent and highlight colours accept only real colours", (t) => {
  globalThis.CSS = { supports: (property, value) => property === "color" && value === "#123456" };
  t.after(() => delete globalThis.CSS);
  const custom = setup({}, { accent_color: "#123456", highlight_color: "url(https://example.com/x)" }).card;
  assert.equal(custom.style.getPropertyValue("--ad-accent"), "#123456");
  assert.equal(custom.style.getPropertyValue("--ad-highlight"), "#ffd60a");
  const plain = setup().card;
  assert.equal(plain.style.getPropertyValue("--ad-accent"), "var(--primary-color)");
});

test("an X01 leg alone shows the darts, the average and the checkout route", () => {
  const { hass, card } = setup(
    practice("40", { game: 501, checkout: "D20", darts: 9, average: 153.67, player: 1, scores: [] })
  );
  assert.equal($(card, ".practice").hidden, false);
  assert.equal(text(card, ".practice-title"), "Practice 501");
  assert.equal(text(card, ".practice-meta"), "9 darts · Ø 153.7");
  assert.equal(text(card, ".practice-remaining"), "40");
  assert.deepEqual(
    $$(card, ".practice-route .bed").map((bed) => bed.textContent),
    ["D20"]
  );
  assert.equal($(card, ".practice-route").title, "Checkout: D20");
  assert.equal($(card, ".scoreboard").hidden, true);
  assert.deepEqual(paths(card, "aim"), [bedPath("D20")]);

  card.hass = update(hass, practice("501", { game: 501, darts: 0, scores: [] }));
  assert.equal(text(card, ".practice-meta"), "");
  assert.equal(text(card, ".practice-route"), "");
  card.hass = update(hass, practice("32", { checkout: "D16", darts: 3, scores: [] }));
  assert.equal(text(card, ".practice-title"), "Practice");
  assert.equal(text(card, ".practice-meta"), "3 darts");
  card.hass = update(hass, practice("unknown", { game: null }));
  assert.equal($(card, ".practice").hidden, true);
});

test("an X01 match shows every player with legs, sets and averages", () => {
  const { hass, card } = setup(
    practice("140", {
      game: 501,
      player: 2,
      name: null,
      checkout: "T20 T20 D10",
      legs_to_win: 3,
      sets_to_win: 2,
      scores: [
        { player: 1, name: "Alex", remaining: 81, legs: 2, sets: 1, average: 84.2 },
        { player: 2, name: null, remaining: 140, legs: 1, sets: 0, average: 60 },
      ],
    })
  );
  assert.equal(text(card, ".practice-meta"), "Player 2 to throw");
  assert.equal($(card, ".scoreboard").hidden, false);
  assert.deepEqual(scores(card), [
    ["player-score", "Alex", "Legs 2 · Sets 1 · Ø 84.2", "81"],
    ["player-score active", "Player 2", "Legs 1 · Sets 0 · Ø 60.0", "140"],
  ]);
  assert.deepEqual(
    $$(card, ".practice-route .bed").map((bed) => bed.textContent),
    ["T20", "T20", "D10"]
  );
  assert.deepEqual(paths(card, "aim"), [bedPath("T20")]);
  card.hass = update(
    hass,
    practice("140", {
      game: 501,
      player: 1,
      name: "Alex",
      scores: [
        { player: 1, name: "Alex", remaining: 81, average: 84.2 },
        { player: 2, name: "Sam", remaining: 140 },
      ],
    })
  );
  assert.equal(text(card, ".practice-meta"), "Alex to throw");
  assert.deepEqual(scores(card), [
    ["player-score active", "Alex", "Ø 84.2", "81"],
    ["player-score", "Sam", "", "140"],
  ]);
});

test("a won match names the winner and nobody aims any more", () => {
  const scoresOf = (name) => [
    { player: 1, name, remaining: 0, legs: 3, sets: 0, average: null },
    { player: 2, name: "Sam", remaining: 60, legs: 1, sets: 0, average: null },
  ];
  const { hass, card } = setup(
    practice("0", { game: 301, player: 1, won: true, winner: 1, legs_to_win: 3, scores: scoresOf("Alex") })
  );
  assert.equal(text(card, ".practice-meta"), "");
  // The winner keeps the legs of the deciding set: the match ended 3 : 1.
  assert.equal(text(card, ".practice-route .note.won"), "Alex wins the match 3 : 1!");
  assert.deepEqual(scores(card), [
    ["player-score winner", "Alex Winner", "Legs 3", "0"],
    ["player-score", "Sam", "Legs 1", "60"],
  ]);
  assert.deepEqual(paths(card, "aim"), []);
  card.hass = update(
    hass,
    practice("0", { game: 301, player: 1, won: true, winner: 1, legs_to_win: 3, scores: scoresOf(null) })
  );
  assert.equal(text(card, ".practice-route .note.won"), "Player 1 wins the match 3 : 1!");
  // With sets, the sets tell the result.
  const sets = [
    { player: 1, name: "Alex", remaining: 60, legs: 1, sets: 1, average: null },
    { player: 2, name: "Sam", remaining: 0, legs: 2, sets: 2, average: null },
  ];
  card.hass = update(hass, practice("0", { game: 301, winner: 2, legs_to_win: 2, sets_to_win: 2, scores: sets }));
  assert.equal(text(card, ".practice-route .note.won"), "Sam wins the match 2 : 1!");
});

test("a leg shot, a bust, double in and a dead end each explain the route", () => {
  const leg = (state, attributes) => practice(state, { game: 501, player: 1, scores: [], ...attributes });
  const { hass, card } = setup(leg("0", { won: true }));
  assert.equal(text(card, ".practice-route .note.won"), "Game shot!");
  assert.deepEqual(paths(card, "aim"), []);

  // A bust ends the visit; the route of the next one follows after the takeout.
  card.hass = update(hass, leg("100", { bust: true, checkout: "T20 D20" }));
  assert.equal(text(card, ".practice-route .note.bust"), "Bust – the score stays");
  assert.deepEqual($$(card, ".practice-route .bed"), []);
  assert.deepEqual(paths(card, "aim"), [bedPath("T20")]);

  card.hass = update(hass, leg("501", { opened: false }));
  assert.equal(text(card, ".practice-route"), "Start with a double");
  assert.equal(paths(card, "aim").length, 21);
  assert.ok(paths(card, "aim").includes(bedPath("Bull")));

  card.hass = update(hass, leg("169", {}));
  assert.equal(text(card, ".practice-route"), "No checkout possible");
  assert.deepEqual(paths(card, "aim"), []);

  // Without double out, three darts finish up to 180; above, nobody expects a checkout.
  card.hass = update(hass, leg("175", { double_out: false }));
  assert.equal(text(card, ".practice-route"), "No checkout possible");
  card.hass = update(hass, leg("171", {}));
  assert.equal(text(card, ".practice-route"), "");
  card.hass = update(hass, leg("301", {}));
  assert.equal(text(card, ".practice-route"), "");
});

test("Around the Clock shows the next number and aims at all of its beds", () => {
  const { hass, card } = setup({
    ...drill("7", { drill: "around_the_clock", progress: 6, targets: 21, darts: 12, hit_rate: 50 }),
    // A training game comes before a practice leg.
    ...practice("501", { game: 501, scores: [] }),
  });
  assert.equal(text(card, ".practice-title"), "Around the Clock");
  assert.equal(text(card, ".practice-meta"), "6 / 21 · 12 darts · 50% hits");
  assert.equal(text(card, ".practice-remaining"), "7");
  assert.equal(text(card, ".practice-route"), "");
  assert.equal($(card, ".scoreboard").hidden, true);
  assert.deepEqual(paths(card, "aim"), ["SI7", "SO7", "T7", "D7"].map(bedPath));

  // The last target is the bull, where the outer bull counts as well.
  card.hass = update(hass, drill("25", { drill: "around_the_clock", progress: 20, darts: 0 }));
  assert.equal(text(card, ".practice-remaining"), "Bull (25/50)");
  assert.equal(text(card, ".practice-meta"), "20 / 21 · 0 darts · – hits");
  assert.deepEqual(paths(card, "aim"), [bedPath("Bull"), bedPath("25")]);

  card.hass = update(hass, drill("unknown", { drill: "around_the_clock", finished: true, progress: 21, darts: 30 }));
  assert.equal(text(card, ".practice-remaining"), "✓");
  assert.equal(text(card, ".practice-route .note.won"), "Done in 30 darts");
  assert.deepEqual(paths(card, "aim"), []);
});

test("the doubles training aims at the double to hit", () => {
  const { card } = setup(drill("D16", { drill: "doubles", progress: 15, darts: 40, hit_rate: 37.5 }));
  assert.equal(text(card, ".practice-title"), "Doubles training");
  assert.equal(text(card, ".practice-remaining"), "D16");
  assert.equal(text(card, ".practice-meta"), "15 / 21 · 40 darts · 38% hits");
  assert.deepEqual(paths(card, "aim"), [bedPath("D16")]);
});

test("the checkout training shows the finish, the route and the attempts", () => {
  const finish = (attributes) =>
    drill("81", { drill: "checkout", remaining: 81, checkout: "T15 D18", attempts: 4, successes: 1, ...attributes });
  const { hass, card } = setup(finish({ attempt_visit: 2, attempt_visits: 3, rate: 25 }));
  assert.equal(text(card, ".practice-title"), "Checkout training");
  assert.equal(text(card, ".practice-remaining"), "81");
  assert.equal(text(card, ".practice-meta"), "Visit 2 / 3 · 1 / 4 checked out · 25% · Best –");
  assert.deepEqual(
    $$(card, ".practice-route .bed").map((bed) => bed.textContent),
    ["T15", "D18"]
  );
  assert.deepEqual(paths(card, "aim"), [bedPath("T15")]);

  card.hass = update(hass, finish({ bust: true, rate: null }));
  assert.equal(text(card, ".practice-meta"), "Visit 1 / 3 · 1 / 4 checked out · – % · Best –");
  assert.equal(text(card, ".practice-route .note.bust"), "Bust – the score stays");
  assert.equal($$(card, ".practice-route .bed").length, 0);

  card.hass = update(hass, finish({ won: true, remaining: 0, checkout: null }));
  assert.equal(text(card, ".practice-remaining"), "0");
  assert.equal(text(card, ".practice-route .note.won"), "Game shot!");

  card.hass = update(hass, drill("unknown", { drill: "checkout" }));
  assert.equal(text(card, ".practice-remaining"), "–");
});

test("Bob's 27 shows the score and the round, and how it ended", () => {
  const { hass, card } = setup(drill("D3", { drill: "bobs_27", score: 27, progress: 2, targets: 21, darts: 6 }));
  assert.equal(text(card, ".practice-title"), "Bob's 27");
  assert.equal(text(card, ".practice-meta"), "27 points · Round 3 / 21");
  assert.equal(text(card, ".practice-remaining"), "D3");
  assert.deepEqual(paths(card, "aim"), [bedPath("D3")]);

  const finished = { drill: "bobs_27", finished: true, progress: 21, targets: 21, darts: 63 };
  card.hass = update(hass, drill("unknown", { ...finished, score: 150, results: [{ completed: true, score: 150 }] }));
  assert.equal(text(card, ".practice-meta"), "150 points · Round 21 / 21");
  assert.equal(text(card, ".practice-route .note.won"), "Done with 150 points");
  card.hass = update(hass, drill("unknown", { ...finished, score: -3, results: [{ completed: false }] }));
  assert.equal(text(card, ".practice-route .note.bust"), "Below zero – the next dart starts again");
  card.hass = update(hass, drill("unknown", { drill: "bobs_27", progress: 0 }));
  assert.equal(text(card, ".practice-meta"), "– points · Round 1 / 21");
});

test("Cricket alone counts the closed numbers and shows the marks", () => {
  const marks = [3, 3, 3, 1, 0, 0, 0];
  const cricket = (attributes) =>
    practice("unknown", {
      game: "cricket",
      target: "T17",
      darts: 12,
      mpr: 1.5,
      player: 1,
      scores: [{ player: 1, name: null, marks, points: 0, mpr: 1.5 }],
      ...attributes,
    });
  const { hass, card } = setup(cricket({}));
  assert.equal(text(card, ".practice-title"), "Cricket");
  assert.equal(text(card, ".practice-meta"), "12 darts · MPR 1.50");
  assert.equal(text(card, ".practice-remaining"), "3/7");
  assert.equal(text(card, ".practice-route .bed"), "T17");
  assert.equal($(card, ".scoreboard").hidden, false);
  assert.equal($(card, ".practice .cricket thead"), null);
  assert.deepEqual(
    $$(card, ".practice .cricket tr").map((row) => [row.className, row.textContent]),
    [
      ["closed", "20Ⓧ"],
      ["closed", "19Ⓧ"],
      ["closed", "18Ⓧ"],
      ["target", "17/"],
      ["", "16"],
      ["", "15"],
      ["", "Bull"],
      ["detail", "MPR1.50"],
    ]
  );
  // Screen readers hear the marks, not the chalk signs.
  assert.deepEqual(
    $$(card, ".practice .cricket td span").slice(0, 4).map((mark) => mark.getAttribute("aria-label")),
    ["Closed", "Closed", "Closed", "1 mark"]
  );
  assert.deepEqual(paths(card, "aim"), [bedPath("T17")]);

  card.hass = update(hass, cricket({ mpr: null, darts: 3, won: true }));
  assert.equal(text(card, ".practice-meta"), "3 darts");
  assert.equal(text(card, ".practice-route .note.won"), "Game shot!");
  assert.deepEqual(paths(card, "aim"), []);
  card.hass = update(hass, cricket({ darts: 0, target: "BULL", scores: [] }));
  assert.equal(text(card, ".practice-meta"), "");
  assert.equal(text(card, ".practice-remaining"), "0/7");
  assert.equal($(card, ".scoreboard").hidden, true);
  assert.deepEqual(paths(card, "aim"), [bedPath("Bull"), bedPath("25")]);
});

test("a Cricket match shows the points, the player at the board and the winner", () => {
  const players = (first) => [
    { player: 1, name: first, marks: [3, 3, 3, 3, 3, 3, 3], points: 60, legs: 1, sets: 1, mpr: 2.4 },
    { player: 2, name: "Sam", marks: [3, 2, 1, 0, 0, 0, 0], points: 20, legs: 0, sets: 0, mpr: null },
  ];
  const cricket = (attributes) =>
    practice("unknown", {
      game: "cricket",
      target: "T19",
      player: 2,
      name: "Sam",
      points: 20,
      legs_to_win: 2,
      sets_to_win: 2,
      scores: players("Alex"),
      ...attributes,
    });
  const { hass, card } = setup(cricket({}));
  assert.equal(text(card, ".practice-meta"), "Sam to throw");
  assert.equal(text(card, ".practice-remaining"), "20");
  assert.deepEqual(
    $$(card, ".practice .cricket thead th").map((cell) => [cell.className, cell.textContent]),
    [
      ["aim", ""],
      ["", "Alex"],
      ["active", "Sam"],
    ]
  );
  const rows = $$(card, ".practice .cricket tbody tr").map((row) => [row.className, row.textContent]);
  assert.deepEqual(rows.slice(0, 2), [
    ["closed", "20ⓍⓍ"],
    ["target", "19ⓍX"],
  ]);
  assert.deepEqual(rows.slice(7), [
    ["total", "Points6020"],
    ["detail", "MPR2.40–"],
    ["detail", "Legs10"],
    ["detail", "Sets10"],
  ]);

  const won = [
    { ...players("Alex")[0], legs: 2, sets: 2 },
    { ...players("Alex")[1], legs: 1, sets: 1 },
  ];
  card.hass = update(hass, cricket({ winner: 1, won: true, target: null, scores: won }));
  assert.equal(text(card, ".practice-meta"), "");
  assert.equal(text(card, ".practice-route .note.won"), "Alex wins the match 2 : 1!");
  // Who won is said, not only shown by colour.
  assert.equal($(card, ".practice .cricket thead th.winner").textContent, "Alex Winner");
  assert.deepEqual(paths(card, "aim"), []);
  card.hass = update(hass, cricket({ winner: 1, legs_to_win: 1, sets_to_win: 1, scores: players(null) }));
  assert.equal(text(card, ".practice-route .note.won"), "Player 1 wins the match!");
  assert.equal($$(card, ".practice .cricket tbody tr").length, 9);
  // Between two numbers, before the next target is known, nothing is outlined.
  card.hass = update(hass, cricket({ target: null }));
  assert.equal(text(card, ".practice-route"), "");
  // A winner the scores do not list is named by number.
  card.hass = update(hass, cricket({ winner: 3 }));
  assert.equal(text(card, ".practice-route .note.won"), "Player 3 wins the match!");
});

test("the bull-off shows who throws and how close each dart landed", () => {
  const bullOff = (player, name) =>
    practice("501", {
      game: 501,
      bull_off: {
        player,
        name,
        throws: [
          { player: 1, name: "Alex", hit: "S20", distance: 12.4 },
          { player: 2, name: null, hit: null, distance: null },
        ],
      },
    });
  const { hass, card } = setup(bullOff(2, "Sam"));
  assert.equal(text(card, ".practice-title"), "Bull-off");
  assert.equal(text(card, ".practice-meta"), "Sam to throw");
  assert.equal(text(card, ".practice-remaining"), "Bull");
  assert.equal(text(card, ".practice-route"), "Closest to the bull starts");
  assert.deepEqual(scores(card), [
    ["player-score", "Alex", "12.4 mm", "S20"],
    ["player-score active", "Player 2", "", "–"],
  ]);
  assert.deepEqual(paths(card, "aim"), [bedPath("Bull"), bedPath("25")]);
  card.hass = update(hass, bullOff(1, null));
  assert.equal(text(card, ".practice-meta"), "Player 1 to throw");

  // A tie throws again; the bullseye beats the outer bull, measured or not.
  card.hass = update(
    hass,
    practice("501", {
      game: 501,
      bull_off: {
        player: 3,
        rethrow: true,
        throws: [
          { player: 3, name: "Kim", hit: "25", distance: 10.2 },
          { player: 1, name: "Alex", hit: "BULL", distance: null },
        ],
      },
    })
  );
  assert.equal(text(card, ".practice-route .note.rethrow"), "Tie – throw again");
  assert.deepEqual(scores(card), [
    ["player-score active", "Kim", "10.2 mm", "25"],
    ["player-score winner", "Alex Winner", "leads", "Bull"],
  ]);
});

test("Shanghai shows the round, the points and the number to hit", () => {
  const shanghai = (scoresList, attributes = {}) =>
    practice("unknown", {
      game: "shanghai",
      round: 3,
      rounds: 7,
      target: "3",
      points: 45,
      player: 1,
      name: "Alex",
      scores: scoresList,
      ...attributes,
    });
  const both = [
    { player: 1, name: "Alex", points: 45, legs: 1, sets: 0 },
    { player: 2, name: "Sam", points: 30, legs: 0, sets: 0 },
  ];
  const { hass, card } = setup(shanghai(both, { legs_to_win: 2, sets_to_win: 2 }));
  assert.equal(text(card, ".practice-title"), "Shanghai");
  assert.equal(text(card, ".practice-meta"), "Round 3/7 · Alex to throw");
  assert.equal(text(card, ".practice-remaining"), "45");
  assert.equal(text(card, ".practice-route .bed"), "3");
  assert.deepEqual(scores(card), [
    ["player-score active", "Alex", "Legs 1 · Sets 0", "45"],
    ["player-score", "Sam", "Legs 0 · Sets 0", "30"],
  ]);
  assert.deepEqual(paths(card, "aim"), ["SI3", "SO3", "T3", "D3"].map(bedPath));

  card.hass = update(hass, shanghai([both[0]], { rounds: null }));
  assert.equal(text(card, ".practice-meta"), "");
  assert.equal($(card, ".scoreboard").hidden, true);
  card.hass = update(hass, shanghai(both, { winner: 2, won: true }));
  assert.equal(text(card, ".practice-route .note.won"), "Sam wins the match!");
  assert.equal(scores(card)[1][0], "player-score winner");
  card.hass = update(hass, shanghai([{ player: 1, points: 45 }, { player: 2, points: 30 }], { winner: 2 }));
  assert.equal(text(card, ".practice-route .note.won"), "Player 2 wins the match!");
  card.hass = update(hass, shanghai(both, { won: true }));
  assert.equal(text(card, ".practice-route .note.won"), "Game shot!");
});

test("Halve-It names any double, any treble or the bull as the target", () => {
  const halveIt = (target) =>
    practice("unknown", { game: "halve_it", round: 2, rounds: 9, target, points: 40, player: 1, scores: [] });
  const { hass, card } = setup(halveIt("D"));
  assert.equal(text(card, ".practice-title"), "Halve-It");
  assert.equal(text(card, ".practice-route .bed"), "Any double");
  assert.equal(paths(card, "aim").length, 21);
  card.hass = update(hass, halveIt("T"));
  assert.equal(text(card, ".practice-route .bed"), "Any treble");
  assert.equal(paths(card, "aim").length, 20);
  // The bull round counts both bull beds, whether the target reads 25 or BULL.
  card.hass = update(hass, halveIt("25"));
  assert.equal(text(card, ".practice-route .bed"), "Bull (25/50)");
  assert.deepEqual(paths(card, "aim"), [bedPath("Bull"), bedPath("25")]);
  card.hass = update(hass, halveIt("BULL"));
  assert.equal(text(card, ".practice-route .bed"), "Bull");
  assert.deepEqual(paths(card, "aim"), [bedPath("Bull"), bedPath("25")]);
  card.hass = update(hass, halveIt(null));
  assert.equal(text(card, ".practice-route"), "");
  assert.deepEqual(paths(card, "aim"), []);
});

test("Killer shows the phases, the lives and the doubles a killer hunts", () => {
  const players = [
    { player: 1, name: "Alex", number: 7, lives: 3, killer: true },
    { player: 2, name: "Sam", number: 12, lives: 2, killer: false },
    { player: 3, name: null, number: 5, lives: 0, killer: false },
  ];
  const killer = (attributes) =>
    practice("unknown", { game: "killer", player: 1, name: "Alex", scores: players, ...attributes });
  const { hass, card } = setup(killer({ phase: "choose", scores: [{ player: 1 }, { player: 2 }] }));
  assert.equal(text(card, ".practice-title"), "Killer");
  assert.equal(text(card, ".practice-remaining"), "?");
  assert.equal(text(card, ".practice-route"), "Throw for your number");
  assert.deepEqual(paths(card, "aim"), []);

  card.hass = update(hass, killer({}));
  assert.equal(text(card, ".practice-remaining"), "7");
  assert.equal(text(card, ".practice-route"), "Killer – hit the others' doubles");
  assert.deepEqual(paths(card, "aim"), [bedPath("D12")]);
  assert.deepEqual(scores(card), [
    ["player-score active", "Alex", "7 · Killer", "♥♥♥"],
    ["player-score", "Sam", "12", "♥♥"],
    ["player-score out", "Player 3", "5 · out", "✕"],
  ]);

  card.hass = update(hass, killer({ player: 2, name: "Sam", target: "D12" }));
  assert.equal(text(card, ".practice-remaining"), "12");
  assert.equal(text(card, ".practice-route .bed"), "D12");
  assert.deepEqual(paths(card, "aim"), [bedPath("D12")]);

  card.hass = update(hass, killer({ player: 4, name: null }));
  assert.equal(text(card, ".practice-remaining"), "–");
  card.hass = update(hass, killer({ needs_players: 2, scores: [players[0]] }));
  assert.equal(text(card, ".practice-route"), "Killer needs at least two players");
  assert.deepEqual(paths(card, "aim"), []);
});

test("the practice game can be hidden", () => {
  const { card } = setup(practice("40", { game: 501, checkout: "D20", scores: [] }), { show_practice: false });
  assert.equal($(card, ".practice"), null);
  assert.deepEqual(paths(card, "aim"), []);
});

test("the live card offers its editor, a stub configuration and a grid size", () => {
  const Card = customElements.get("homedarts-card");
  assert.deepEqual(Card.getStubConfig(makeHass({ states: READY })), { device_id: DEVICE });
  assert.deepEqual(Card.getStubConfig(makeHass()), {});
  assert.deepEqual(Card.getStubConfig({}), {});
  assert.deepEqual(setup().card.getGridOptions(), { columns: 12, min_columns: 6 });
});
