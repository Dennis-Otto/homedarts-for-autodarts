// A dartboard without Autodarts on the cards: its status, the keypad on the live card and
// the scoreboard, the status card with nothing to show, and the dashboard without a board view.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, READY, loadCards, makeHass, mount, text, update, withLanguage } from "./dom.mjs";

const { dashboardStrategy } = await loadCards();

const ENTRY = "01JMANUAL";
// The entities a dartboard without Autodarts has for the cards: no connection, detection,
// cameras or manual entry switch.
const MANUAL = {
  "sensor.local_status": "manual",
  "sensor.practice_remaining": {
    state: "501",
    attributes: {
      game: 501,
      player: 1,
      name: "Alex",
      scores: [
        { player: 1, name: "Alex", remaining: 501, legs: 0, sets: 0, average: null },
        { player: 2, name: "Sam", remaining: 501, legs: 0, sets: 0, average: null },
      ],
    },
  },
  "sensor.training_darts": "0",
};
const visit = (...throws) => ({
  "sensor.local_visit_score": {
    state: String(throws.reduce((sum, dart) => sum + dart.number * dart.multiplier, 0)),
    attributes: { throws },
  },
});
const dart = (number, multiplier, extra = {}) => ({ number, multiplier, segment: "x", manual: true, ...extra });
const board = (states = {}, options = {}) =>
  makeHass({ states: { ...MANUAL, ...visit(), ...states }, device: { primary_config_entry: ENTRY }, ...options });
const actions = (hass) =>
  hass.calls.filter(([domain]) => domain === "homedarts").map(([, service, data]) => [service, data]);

test("a dartboard without Autodarts asks for the darts, and says when the visit is complete", () => {
  const hass = board();
  const card = mount("homedarts-scoreboard-card", hass);
  assert.equal(text(card, ".pill"), "Enter your darts");
  // The pill keeps the width of the longest words it takes on such a board.
  assert.equal($(card, ".pill").dataset.widest, "Enter your darts");
  card.hass = update(hass, visit(dart(20, 3, { dart: 1 }), dart(20, 3, { dart: 2 })));
  assert.equal(text(card, ".pill"), "Enter your darts");
  card.hass = update(hass, visit(dart(20, 3, { dart: 1 }), dart(20, 3, { dart: 2 }), dart(20, 1, { dart: 3 })));
  assert.equal(text(card, ".pill"), "Visit complete");
  assert.match(card.style.getPropertyValue("--ad-status"), /amber/);
  // In German, too.
  const german = mount("homedarts-scoreboard-card", withLanguage(board(), "de"));
  assert.equal(text(german, ".pill"), "Darts eingeben");
  assert.equal($(german, ".pill").dataset.widest, "Aufnahme komplett");
});

test("the scoreboard of a dartboard without Autodarts has the keypad, unless its settings switch it off", () => {
  const hass = board();
  const card = mount("homedarts-scoreboard-card", hass);
  // No keypad option and no manual entry switch: the keypad is how darts come at all.
  assert.equal($(card, ".pad-area").hidden, false);
  assert.equal(text(card, ".pad .section-label"), "Enter a dart");
  $(card, '[data-pad="multiplier"][data-value="3"]').click();
  $(card, '.pad-number[data-value="T20"]').click();
  assert.deepEqual(actions(hass), [["throw_dart", { config_entry_id: ENTRY, segment: "T20" }]]);
  // Every dart is entered by hand, so only a correction and the bot's darts stand out.
  card.hass = update(hass, visit(dart(20, 3, { dart: 1 }), dart(5, 1, { dart: 2, corrected: true })));
  assert.deepEqual(
    $$(card, ".visit .dart").map((item) => item.className),
    ["dart tappable", "dart corrected tappable", "dart empty"],
  );
  // A screen at the board without touch, such as a TV, switches it off.
  const tv = mount("homedarts-scoreboard-card", hass, { keypad: false });
  assert.equal($(tv, ".pad-area").hidden, true);
  // With Autodarts, the keypad stays an option for darts the board missed.
  const detected = mount(
    "homedarts-scoreboard-card",
    makeHass({ states: { ...READY, ...visit(dart(20, 3, { dart: 1 })) } }),
    { keypad: true },
  );
  assert.equal($(detected, ".pad-area").hidden, true);
  assert.equal($(detected, ".visit .dart").className, "dart manual tappable");
});

test("the live card of a dartboard without Autodarts enters darts and has no footer", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const hass = board();
  const card = mount("homedarts-card", hass);
  assert.equal(text(card, ".pill"), "Enter your darts");
  // There are no connections to show and no detection to control.
  assert.equal($(card, ".footer").hidden, true);
  assert.equal($(card, ".pad-area").hidden, false);
  assert.equal(text(card, ".pad .section-label"), "Enter a dart");
  $(card, '[data-value="BULL"]').click();
  assert.deepEqual(actions(hass), [["throw_dart", { config_entry_id: ENTRY, segment: "BULL" }]]);
  // A tap on a dart corrects it, and the keypad comes back after the correction.
  card.hass = update(hass, visit(dart(25, 2, { dart: 1 })));
  $(card, '[data-dart="1"]').click();
  assert.equal(text(card, ".pad .section-label"), "Correct dart 1");
  $(card, '[data-pad="cancel"]').click();
  assert.equal(text(card, ".pad .section-label"), "Enter a dart");
  // The next player needs a second tap, which times out.
  hass.calls.length = 0;
  $(card, '[data-pad="next"]').click();
  assert.equal(text(card, '[data-pad="next"]'), "Confirm?");
  t.mock.timers.tick(4000);
  assert.equal(text(card, '[data-pad="next"]'), "Next player");
  $(card, '[data-pad="next"]').click();
  $(card, '[data-pad="next"]').click();
  assert.deepEqual(actions(hass), [["next_player", { config_entry_id: ENTRY }]]);
  // The last visit can be undone while no dart of the next one is in; the key keeps its
  // place meanwhile, and says why it waits.
  assert.equal($(card, '[data-pad="undo"]').disabled, true);
  assert.equal($(card, '[data-pad="undo"]').title, "Takes back the last visit until a dart of the next one is entered");
  const undoable = {
    ...visit(),
    "sensor.practice_remaining": {
      ...MANUAL["sensor.practice_remaining"],
      attributes: { ...MANUAL["sensor.practice_remaining"].attributes, undo: true },
    },
  };
  card.hass = update(hass, undoable);
  $(card, '.pad [data-pad="undo"]').click();
  $(card, '.pad [data-pad="undo"]').click();
  assert.deepEqual(actions(hass).at(-1), ["undo_visit", { config_entry_id: ENTRY }]);
  card.hass = update(hass, { ...undoable, ...visit(dart(20, 1, { dart: 1 })) });
  assert.equal($(card, '[data-pad="undo"]').disabled, true);
  // Switched off in the card's settings, and in the preview of the card editor, it stays away.
  assert.equal($(mount("homedarts-card", hass, { keypad: false }), ".pad-area").hidden, true);
  const preview = document.createElement("homedarts-card");
  preview.setConfig({ type: "custom:homedarts-card" });
  preview.preview = true;
  preview.hass = hass;
  document.body.append(preview);
  assert.equal($(preview, ".pad-area").hidden, true);
});

test("the live card of a board with Autodarts has the keypad as an option", () => {
  const hass = makeHass({ states: { ...READY, ...visit(), "switch.practice_manual_entry": "off" } });
  const card = mount("homedarts-card", hass, { keypad: true });
  assert.equal($(card, ".footer").hidden, false);
  assert.equal($(card, ".pad-area").hidden, true);
  card.hass = update(hass, { "switch.practice_manual_entry": "on" });
  assert.equal($(card, ".pad-area").hidden, false);
  // Without the option, the board's darts are corrected only.
  assert.equal($(mount("homedarts-card", card._hass), ".pad-area").hidden, true);
});

// An Autodarts board without cameras yet, as Board Manager 2.1 reports it: no camera running,
// the detection stopped. Its darts come from the keypad, as tests/test_board_manager_2_1.py
// counts them for the board's training.
test("the scoreboard of an Autodarts board without cameras enters darts with the keypad", () => {
  const states = {
    ...READY,
    ...MANUAL,
    ...visit(),
    "binary_sensor.cameras_active": "off",
    "switch.detection": "off",
    "sensor.local_status": "stopped",
    "switch.practice_manual_entry": "on",
  };
  const hass = makeHass({ states, device: { primary_config_entry: ENTRY } });
  const card = mount("homedarts-scoreboard-card", hass, { keypad: true });
  assert.equal($(card, ".pad-area").hidden, false);
  assert.equal(text(card, ".pad .section-label"), "Enter a dart");
  $(card, '[data-pad="multiplier"][data-value="3"]').click();
  $(card, '.pad-number[data-value="T20"]').click();
  assert.deepEqual(actions(hass), [["throw_dart", { config_entry_id: ENTRY, segment: "T20" }]]);
  // Without Practice manual entry, or without the option, there is no keypad.
  card.hass = update(hass, { "switch.practice_manual_entry": "off" });
  assert.equal($(card, ".pad-area").hidden, true);
  assert.equal($(mount("homedarts-scoreboard-card", hass), ".pad-area").hidden, true);
});

test("the status card of a dartboard without Autodarts says why it has nothing to show", () => {
  const card = mount("homedarts-status-card", board());
  assert.equal(text(card, ".pill"), "Enter your darts");
  assert.equal($(card, ".manual-note").hidden, false);
  assert.match(text(card, ".manual-note"), /^This dartboard has no Autodarts: its darts are entered on the keypad/);
  for (const part of [".detection", ".info", ".controls"]) assert.equal($(card, part).hidden, true, part);
  // A board with Autodarts shows all of it.
  const detected = mount("homedarts-status-card", makeHass({ states: READY }));
  assert.equal($(detected, ".manual-note").hidden, true);
  assert.equal($(detected, ".detection").hidden, false);
});

test("the dashboard of a dartboard without Autodarts has no board view", () => {
  const entity = (entity_id, translation_key) => ({ entity_id, translation_key, device_id: "dev1", platform: "homedarts" });
  const entities = [
    entity("sensor.garage_darts", "training_darts"),
    entity("sensor.garage_status", "local_status"),
  ];
  const hass = (status) => ({
    locale: { language: "en" },
    entities: Object.fromEntries(entities.map((item) => [item.entity_id, item])),
    devices: { dev1: { id: "dev1", name: "Garage" } },
    states: { "sensor.garage_status": { entity_id: "sensor.garage_status", state: status, attributes: {} } },
  });
  const paths = (status) => dashboardStrategy(hass(status)).views.map((view) => view.path);
  assert.deepEqual(paths("manual"), ["live", "scoreboard", "training", "overlay"]);
  assert.deepEqual(paths("throw"), ["live", "scoreboard", "training", "board", "overlay"]);
});
