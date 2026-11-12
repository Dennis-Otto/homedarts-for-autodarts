// Playing comfort on the cards: setup hints, the bot, correcting and entering darts, and the bot in the lobby.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, DEVICE, READY, loadCards, makeHass, mount, settle, text, update, withLanguage } from "./dom.mjs";

const {
  aimBeds,
  boardSpot,
  callerCalls,
  callerState,
  callerText,
  cardForm,
  cricketView,
  gameView,
  hitBeds,
  lobbyChange,
  lobbyChoice,
  padBed,
  padHtml,
  padViewBox,
  practiceView,
  setupView,
  startGameData,
  summaryView,
} = await loadCards();

const T = (key) =>
  ({
    bot: "Bot",
    bot_level: "Level {level}",
    score_player: "Player",
    setup_leave: "leaves {leave}",
    setup_hint: "Set up",
    say_require: "{name}, you require {remaining}",
    say_require_alone: "You require {remaining}",
    say_setup: "{name}, leave yourself {leave}",
    say_setup_alone: "Leave yourself {leave}",
    correct_title: "Correct dart {dart}",
    enter_title: "Enter a dart",
    miss: "Miss",
    confirm: "Confirm?",
  })[key] ?? key;

// A match of Alex against the bot, and the sensors the scoreboard reads for it.
const SCORES = [
  { player: 1, name: "Alex", remaining: 169, legs: 0, sets: 0, average: 60 },
  { player: 2, name: null, remaining: 301, legs: 0, sets: 0, average: null, bot: true },
];
const practice = (attributes = {}, state = "169") => ({
  "sensor.practice_remaining": {
    state,
    attributes: {
      game: 301,
      player: 1,
      name: "Alex",
      scores: SCORES,
      bot: { player: 2, level: 60 },
      setup: { route: "T20 T20 S17", leave: 32 },
      ...attributes,
    },
  },
});
const visit = (...throws) => ({
  "sensor.local_visit_score": {
    state: String(throws.reduce((sum, dart) => sum + dart.number * dart.multiplier, 0)),
    attributes: { throws },
  },
});
const dart = (number, multiplier, extra = {}) => ({ number, multiplier, segment: "x", ...extra });

// -- views -------------------------------------------------------------------------

test("a setup takes the place of the checkout where none exists", () => {
  assert.deepEqual(setupView({ route: "T20 T20 S17", leave: 32 }), { route: ["T20", "T20", "S17"], leave: 32 });
  assert.equal(setupView({ route: "Z9", leave: 32 }), null);
  assert.equal(setupView({ route: "T20", leave: "32" }), null);
  assert.equal(setupView(null), null);
  const view = practiceView(practice()["sensor.practice_remaining"]);
  assert.deepEqual(view.setup, { route: ["T20", "T20", "S17"], leave: 32 });
  assert.equal(view.botLevel, 60);
  assert.equal(view.scores[1].bot, true);
  assert.equal("bot" in view.scores[0], false);
  // The board outlines the setup's first dart.
  assert.deepEqual(aimBeds({ mode: "x01", practice: view }), hitBeds("T20"));
  // Without a setup or a bot, the view has neither.
  const plain = practiceView(practice({ setup: null, bot: null })["sensor.practice_remaining"]);
  assert.equal("setup" in plain, false);
  assert.equal("botLevel" in plain, false);
  assert.deepEqual(aimBeds({ mode: "x01", practice: plain }), []);
});

test("the bot is named the bot on the chalkboard, in the bull-off and in the summary", () => {
  const cricket = cricketView({
    state: "unknown",
    attributes: {
      game: "cricket",
      player: 2,
      scores: [
        { player: 1, name: "Alex", marks: [0, 0, 0, 0, 0, 0, 0], points: 0 },
        { player: 2, name: null, marks: [3, 0, 0, 0, 0, 0, 0], points: 0, bot: true },
      ],
    },
  });
  assert.equal(cricket.scores[1].bot, true);
  const view = gameView((name) =>
    name === "practice"
      ? {
          state: "unknown",
          attributes: {
            game: 501,
            bull_off: {
              player: 2,
              name: null,
              throws: [
                { player: 1, name: "Alex", hit: "S20", distance: 80 },
                { player: 2, name: null, bot: true },
              ],
            },
          },
        }
      : undefined,
  );
  assert.equal(view.bullOff.throws[1].bot, true);
  const summary = summaryView({
    state: "0",
    attributes: {
      game: 301,
      winner: 2,
      summary: {
        game: 301,
        winner: 2,
        players: [
          { player: 1, name: "Alex", legs: 0, average: 50 },
          { player: 2, name: null, legs: 1, average: 70, bot: true },
        ],
      },
    },
  });
  assert.equal(summary.players[1].bot, true);
});

// -- caller ------------------------------------------------------------------------

test("the caller names the score to leave when no checkout exists", () => {
  const x01 = (attributes) => ({
    mode: "x01",
    practice: practiceView(practice(attributes)["sensor.practice_remaining"]),
  });
  const all = { call_checkouts: true };
  const before = callerState(visit(), x01({ player: 2, name: null, setup: null }));
  const alex = callerState(visit(), x01({}), before);
  assert.deepEqual(callerCalls(before, alex, all), [{ kind: "setup", name: "Alex", player: 1, players: 2, leave: 32 }]);
  assert.equal(callerText(callerCalls(before, alex, all)[0], T), "Alex, leave yourself 32");
  assert.deepEqual(callerCalls(before, alex, { call_checkouts: false }), []);
  // The bot at the board is called the bot.
  const bot = callerState(visit(), x01({ player: 2, name: null, checkout: "T20 T20 BULL", setup: null }), alex);
  const [call] = callerCalls(alex, bot, all);
  assert.deepEqual(call, { kind: "require", name: null, bot: true, player: 2, players: 2, remaining: 169 });
  assert.equal(callerText(call, T), "Bot, you require 169");
  // Alone, nobody needs a name.
  assert.equal(callerText({ kind: "setup", player: 1, players: 1, leave: 40 }, T), "Leave yourself 40");
});

// -- the pad ---------------------------------------------------------------------------

test("the pad corrects a dart or enters one, with the next player and the undo behind a second tap", () => {
  assert.deepEqual([padBed(1, 20), padBed(2, 16), padBed(3, 19)], ["S20", "D16", "T19"]);
  const html = padHtml({ dart: 2, multiplier: 3 }, { t: T });
  const pad = document.createElement("div");
  pad.innerHTML = html;
  assert.equal(pad.querySelector(".section-label").textContent, "Correct dart 2");
  assert.equal(pad.querySelector('[aria-pressed="true"]').textContent, "T");
  assert.equal(pad.querySelectorAll(".pad-number").length, 20);
  assert.equal(pad.querySelector(".pad-number").dataset.value, "T1");
  assert.deepEqual(
    [...pad.querySelectorAll(".pad-extra button")].map((button) => [button.dataset.pad, button.textContent]),
    [
      ["bed", "25"],
      ["bed", "Bull"],
      ["bed", "Miss"],
      ["cancel", "pad_cancel"],
    ],
  );
  pad.innerHTML = padHtml({ dart: null, multiplier: 1, undo: true, confirm: "undo", disabled: true }, { t: T });
  assert.equal(pad.querySelector(".section-label").textContent, "Enter a dart");
  assert.deepEqual(
    [...pad.querySelectorAll(".secondary")].map((button) => button.textContent),
    ["next_player", "↶ Confirm?"],
  );
  assert.equal(
    [...pad.querySelectorAll("button")].every((button) => button.disabled),
    true,
  );
  pad.innerHTML = padHtml({ dart: null, multiplier: 2, confirm: "next" }, { t: T });
  assert.deepEqual(
    [...pad.querySelectorAll(".secondary")].map((button) => button.textContent),
    ["Confirm?"],
  );
});

// -- the scoreboard --------------------------------------------------------------------

const ENTRY = "01JENTRY";
const setup = (states = {}, config = {}, options = {}) => {
  const hass = makeHass({
    states: { ...READY, ...practice(), ...visit(), ...states },
    device: { primary_config_entry: ENTRY },
    ...options,
  });
  return { hass, card: mount("homedarts-scoreboard-card", hass, config) };
};
const chips = (card) =>
  $$(card, ".visit .dart").map((chip) => [chip.tagName.toLowerCase(), chip.className, chip.dataset.dart ?? null]);
const actions = (hass) =>
  hass.calls.filter(([domain]) => domain === "homedarts").map(([, service, data]) => [service, data]);

test("the scoreboard shows the setup and the bot's level", () => {
  const { card } = setup();
  assert.equal(text(card, ".player.active .route"), "T20T20S17leaves 32");
  assert.equal($(card, ".setup").getAttribute("title"), "No checkout with the darts left: set up the next visit");
  assert.deepEqual(
    $$(card, ".player .name").map((name) => name.textContent),
    ["Alex", "Bot Level 60"],
  );
});

test("a tap on a dart of the visit corrects it", () => {
  const throws = [
    dart(20, 3, { dart: 1 }),
    dart(20, 1, { dart: 2, corrected: true }),
    dart(5, 1, { dart: 3, manual: true }),
  ];
  const { hass, card } = setup(visit(...throws));
  assert.deepEqual(chips(card), [
    ["button", "dart tappable", "1"],
    ["button", "dart corrected tappable", "2"],
    ["button", "dart manual tappable", "3"],
  ]);
  // Each shows a pencil at its top right: a tap edits it.
  assert.equal($$(card, ".visit button.dart > .cue.edit").length, 3);
  assert.equal($(card, ".pad-area").hidden, true);
  // A screen reader hears the dart and what a tap does.
  assert.equal($(card, '[data-dart="2"]').getAttribute("aria-label"), "S20 20 – Correct dart 2");
  // It starts with the words the tile shows, kept apart, so voice control finds it by them.
  assert.equal($(card, '[data-dart="2"]').textContent.replace(/\s+/g, " ").trim(), "S20 20");
  $(card, '[data-dart="2"]').click();
  assert.equal($(card, ".pad-area").hidden, false);
  assert.equal(text(card, ".pad .section-label"), "Correct dart 2");
  assert.equal(text(card, '.pad [aria-pressed="true"]'), "S");
  assert.equal($(card, '[data-dart="2"]').classList.contains("picked"), true);
  $(card, '[data-pad="multiplier"][data-value="3"]').click();
  assert.equal($(card, '.pad-number[data-value="T20"]') !== null, true);
  $(card, '.pad-number[data-value="T20"]').click();
  assert.deepEqual(actions(hass), [["correct_dart", { config_entry_id: ENTRY, dart: 2, segment: "T20" }]]);
  assert.equal($(card, ".pad-area").hidden, true);
  // A second tap on the dart closes the pad again, and so does cancel.
  $(card, '[data-dart="1"]').click();
  assert.equal(text(card, '.pad [aria-pressed="true"]'), "T");
  $(card, '[data-dart="1"]').click();
  assert.equal($(card, ".pad-area").hidden, true);
  $(card, '[data-dart="3"]').click();
  $(card, '[data-pad="cancel"]').click();
  assert.equal($(card, ".pad-area").hidden, true);
  // A dart that left the visit closes its pad.
  $(card, '[data-dart="3"]').click();
  card.hass = update(hass, visit(...throws.slice(0, 2)));
  assert.equal($(card, ".pad-area").hidden, true);
});

// A board laid out as a square of 460 pixels at (100, 50): a pixel is a millimetre.
const laidOut = (element, width = 460, height = 460) => {
  element.getBoundingClientRect = () => ({ left: 100, top: 50, width, height });
  return element;
};
// A tap at a point of the board, in millimetres from its centre with y up.
const tapAt = (element, x, y) =>
  element.dispatchEvent(new window.MouseEvent("click", { bubbles: true, clientX: 330 + x, clientY: 280 - y }));

test("a tap on the board of the pad says where the dart is", () => {
  // A pixel of the square board is a millimetre; 170 mm is the edge of the double ring.
  const svg = laidOut(document.createElement("div"));
  assert.deepEqual(boardSpot(svg, { clientX: 330, clientY: 280 }), [0, 0]);
  assert.deepEqual(boardSpot(svg, { clientX: 330 + 17, clientY: 280 - 102 }), [0.1, 0.6]);
  // A wide element draws the board in its middle, as tall as the element.
  laidOut(svg, 920, 460);
  assert.deepEqual(boardSpot(svg, { clientX: 100 + 460 - 34, clientY: 280 + 170 }), [-0.2, -1]);
  // A board that is not laid out has no spot.
  assert.equal(boardSpot(laidOut(svg, 0, 0), { clientX: 1, clientY: 1 }), null);
  // Zoomed in, the view keeps to the board, five times larger at most, and a middle
  // that is no number is the bull.
  assert.deepEqual(padViewBox({ scale: 2, x: 500, y: -500 }), { x: 0, y: -230, size: 230 });
  assert.deepEqual(padViewBox({ scale: 9, x: Number.NaN, y: "far" }), { x: -46, y: -46, size: 92 });
  assert.deepEqual(padViewBox({ scale: 1 }), { x: -230, y: -230, size: 460 });

  const html = padHtml(
    { dart: 2, multiplier: 1, board: true, pins: [{ x: 0, y: 0.6, seen: false }, { x: 0.02, y: 0.8, seen: true }] },
    { t: T }
  );
  const pad = document.createElement("div");
  pad.innerHTML = html;
  // The board instead of the numbers, the multipliers and the bulls.
  assert.equal(pad.querySelector(".pad-numbers"), null);
  assert.equal(pad.querySelector('[data-pad="multiplier"]'), null);
  assert.equal(pad.querySelector('[data-pad="board"]').getAttribute("aria-pressed"), "true");
  assert.equal(pad.querySelector(".pad-board").dataset.pad, "spot");
  assert.equal(pad.querySelector(".pad-board").getAttribute("aria-label"), "pad_spot");
  assert.equal(pad.querySelector(".pad-hint").textContent, "pad_spot_hint");
  // The whole board, and a switch to zoom in.
  assert.equal(pad.querySelector(".pad-board").getAttribute("viewBox"), "-230 -230 460 460");
  const zoom = pad.querySelector('[data-pad="zoom"]');
  assert.deepEqual(
    [zoom.getAttribute("aria-label"), zoom.getAttribute("title"), zoom.getAttribute("aria-pressed"), zoom.textContent],
    ["pad_zoom", "pad_zoom", "false", ""]
  );
  // A magnifier with a plus: a circle, its handle, and two strokes.
  assert.equal(zoom.querySelector("path").getAttribute("d"), "M14.5 14.5 20 20M7 10h6M10 7v6");
  assert.deepEqual(
    [...pad.querySelectorAll(".spot")].map((spot) => [spot.getAttribute("class"), spot.getAttribute("cy")]),
    [
      ["spot", "-102"],
      ["spot seen", "-136"],
    ]
  );
  assert.equal(pad.querySelector(".spot.seen title").textContent, "pad_seen");
  assert.deepEqual(
    [...pad.querySelectorAll(".pad-extra button")].map((button) => button.dataset.pad),
    ["cancel"]
  );
  // While the bot throws, the board takes no taps.
  pad.innerHTML = padHtml({ dart: null, multiplier: 1, board: true, pins: [], disabled: true }, { t: T });
  assert.equal(pad.querySelector(".pad-board").dataset.pad, undefined);
  assert.equal(pad.querySelector(".pad-board").classList.contains("disabled"), true);
  assert.equal(pad.querySelector('[data-pad="board"]').disabled, true);
});

test("the pad's board corrects a dart or enters one where it is", () => {
  const throws = [dart(20, 3, { dart: 1, x: 0, y: 0.6 }), dart(20, 3, { dart: 2, x: 0.02, y: 0.8 }), dart(5, 1, { dart: 3 })];
  const { hass, card } = setup(visit(...throws));
  $(card, '[data-dart="2"]').click();
  // Keys or board: one of the two is chosen, the keys at first.
  assert.deepEqual(
    [$(card, '[data-pad="keys"]').getAttribute("aria-pressed"), $(card, '[data-pad="board"]').getAttribute("aria-pressed")],
    ["true", "false"]
  );
  assert.equal($(card, ".pad .segmented.view").getAttribute("aria-label"), "Enter with");
  $(card, '[data-pad="board"]').click();
  assert.equal($(card, '[data-pad="board"]').getAttribute("aria-pressed"), "true");
  // The darts with a position show; the dart being corrected where the board saw it.
  assert.deepEqual(
    $$(card, ".pad-board .spot").map((spot) => spot.getAttribute("class")),
    ["spot", "spot seen"]
  );
  // Not laid out yet, a tap says nothing, and neither does a tap beside the board.
  tapAt($(card, ".pad-board"), 0, 136);
  $(card, ".pad-hint").click();
  assert.deepEqual(actions(hass), []);
  tapAt(laidOut($(card, ".pad-board")), 0, 136);
  assert.deepEqual(actions(hass), [["correct_dart", { config_entry_id: ENTRY, dart: 2, x: 0, y: 0.8 }]]);
  assert.equal($(card, ".pad-area").hidden, true);
  // The board stays the pad's view for the next dart, and a tap on the seen spot counts too.
  $(card, '[data-dart="1"]').click();
  tapAt(laidOut($(card, ".pad-board")), 0, 102);
  assert.deepEqual(actions(hass).at(-1), ["correct_dart", { config_entry_id: ENTRY, dart: 1, x: 0, y: 0.6 }]);
  // Back to the keys.
  $(card, '[data-dart="1"]').click();
  $(card, '[data-pad="keys"]').click();
  assert.equal($(card, ".pad-board"), null);
  assert.equal($$(card, ".pad-number").length, 20);

  // The keypad enters darts where they are.
  const keypad = setup({ "switch.practice_manual_entry": "on" }, { keypad: true });
  $(keypad.card, '[data-pad="board"]').click();
  tapAt(laidOut($(keypad.card, ".pad-board")), -34, -170);
  assert.deepEqual(actions(keypad.hass), [["throw_dart", { config_entry_id: ENTRY, x: -0.2, y: -1 }]]);
  assert.equal($(keypad.card, ".pad-board") !== null, true);
});

// A card on a screen of this width.
const onScreen = (card, width) => {
  card.getBoundingClientRect = () => ({ left: 0, top: 0, width, height: 800 });
  $(card, ".scoreboard").getBoundingClientRect = () => ({ left: 0, top: 0, width, height: 800 });
  return card;
};
const viewBox = (card) => $(card, ".pad-board").getAttribute("viewBox");
// The zoom switch: a magnifier, what it does next and whether it is zoomed in. Its name
// stays the same, its state is pressed or not.
const zoomSwitch = (card) => {
  const zoom = $(card, '[data-pad="zoom"]');
  assert.equal(zoom.getAttribute("aria-label"), "Zoom");
  assert.equal(zoom.querySelectorAll("svg path").length, 1);
  return [zoom.getAttribute("title"), zoom.getAttribute("aria-pressed")];
};
// A finger on the board: its id and where it is on the screen.
const touch = (element, type, pointerId, clientX, clientY, pointerType = "touch") =>
  element.dispatchEvent(new window.PointerEvent(type, { bubbles: true, cancelable: true, pointerId, pointerType, clientX, clientY }));

test("on a phone the board opens zoomed in on where the board saw the dart", () => {
  const throws = [dart(20, 3, { dart: 1, x: 0, y: 0.6 }), dart(20, 3, { dart: 2, x: 0.02, y: 0.8 }), dart(5, 1, { dart: 3 })];
  const { hass, card } = setup(visit(...throws));
  onScreen(card, 390);
  $(card, '[data-dart="2"]').click();
  $(card, '[data-pad="board"]').click();
  // Two and a half times larger around the dart; its pins keep their size.
  assert.equal(viewBox(card), "-88.6 -228 184 184");
  assert.deepEqual(
    $$(card, ".pad-board .spot").map((spot) => spot.getAttribute("r")),
    ["3.2", "5.2"]
  );
  assert.deepEqual(zoomSwitch(card), ["Whole board", "true"]);
  // A tap in the middle of the board is where the board saw the dart.
  tapAt(laidOut($(card, ".pad-board")), 0, 0);
  assert.deepEqual(actions(hass), [["correct_dart", { config_entry_id: ENTRY, dart: 2, x: 0.02, y: 0.8 }]]);
  // Another dart opens around its own spot; one without a position shows all of it.
  $(card, '[data-dart="1"]').click();
  assert.equal(viewBox(card), "-92 -194 184 184");
  $(card, '[data-dart="3"]').click();
  assert.equal(viewBox(card), "-230 -230 460 460");
  // The switch shows the whole board and zooms in again.
  $(card, '[data-dart="1"]').click();
  $(card, '[data-pad="zoom"]').click();
  assert.deepEqual([viewBox(card), ...zoomSwitch(card)], ["-230 -230 460 460", "Zoom", "false"]);
  $(card, '[data-pad="zoom"]').click();
  assert.equal(viewBox(card), "-92 -194 184 184");
  // Back to the keys and to the board: zoomed in again, while a wide card shows all of it.
  $(card, '[data-pad="keys"]').click();
  $(card, '[data-pad="board"]').click();
  assert.equal(viewBox(card), "-92 -194 184 184");
  onScreen(card, 1000);
  $(card, '[data-pad="keys"]').click();
  $(card, '[data-pad="board"]').click();
  assert.equal(viewBox(card), "-230 -230 460 460");
  // A phone on its side is wide but low: zoomed in, too.
  const height = Object.getOwnPropertyDescriptor(window, "innerHeight");
  Object.defineProperty(window, "innerHeight", { value: 393, configurable: true });
  try {
    $(card, '[data-pad="keys"]').click();
    $(card, '[data-pad="board"]').click();
    assert.equal(viewBox(card), "-92 -194 184 184");
  } finally {
    if (height) Object.defineProperty(window, "innerHeight", height);
    else delete window.innerHeight;
  }

  // The keypad opens the whole board also on a phone, and its switch zooms in on the
  // last dart with a position, near the edge of the board as far as the board goes, or
  // on the bull.
  const keypad = setup(
    { "switch.practice_manual_entry": "on", ...visit(dart(20, 3, { dart: 1, x: 0, y: 1.3 })) },
    { keypad: true }
  );
  onScreen(keypad.card, 390);
  $(keypad.card, '[data-pad="board"]').click();
  assert.equal(viewBox(keypad.card), "-230 -230 460 460");
  $(keypad.card, '[data-pad="zoom"]').click();
  assert.equal(viewBox(keypad.card), "-92 -230 184 184");
  keypad.card.hass = update(keypad.hass, visit());
  $(keypad.card, '[data-pad="zoom"]').click();
  $(keypad.card, '[data-pad="zoom"]').click();
  assert.equal(viewBox(keypad.card), "-92 -92 184 184");
});

test("a finger aims with the loupe and sets the dart where it lets go", () => {
  const throws = [dart(20, 1, { dart: 1, x: 0.02, y: 0.8 })];
  const { hass, card } = setup(visit(...throws));
  onScreen(card, 1000);
  $(card, '[data-dart="1"]').click();
  $(card, '[data-pad="board"]').click();
  const board = laidOut($(card, ".pad-board"));
  const loupe = $(card, ".loupe");
  assert.equal(loupe.hidden, true);
  // Beside the board nothing happens.
  touch($(card, ".pad-hint"), "pointerdown", 1, 330, 280);
  assert.equal(loupe.hidden, true);
  // On the board, the loupe shows the spot under the finger two and a half times larger,
  // above the finger.
  touch(board, "pointerdown", 1, 330, 280);
  assert.equal(loupe.hidden, false);
  assert.equal(loupe.querySelector("svg").getAttribute("viewBox"), "-92 -92 184 184");
  // It shows the pins of the board as the board does: the dashed ring where the board
  // saw the dart, not a black disc. The board zoomed in never draws over the keys.
  assert.equal(loupe.querySelectorAll(".spot.seen").length, 1);
  const style = $(card, "style").textContent;
  assert.match(style, /:is\(\.pad-board, \.loupe\) \.spot \{ fill: #3182ce;/);
  assert.match(style, /:is\(\.pad-board, \.loupe\) \.spot\.seen \{ fill: none;/);
  assert.match(style, /\.pad-board \{\s*width: [^;]+; height: auto; aspect-ratio: 1; margin-inline: auto; overflow: hidden;/);
  assert.deepEqual([loupe.style.left, loupe.style.top], ["264px", "124px"]);
  // It follows the finger; without room above, it goes beside the finger, to its left
  // at the right edge.
  touch(board, "pointermove", 1, 347, 100);
  assert.equal(loupe.querySelector("svg").getAttribute("viewBox"), "-75 -272 184 184");
  assert.deepEqual([loupe.style.left, loupe.style.top], ["371px", "34px"]);
  touch(board, "pointermove", 1, 950, 100);
  assert.deepEqual([loupe.style.left, loupe.style.top], ["794px", "34px"]);
  touch(board, "pointermove", 1, 347, 100);
  // New states leave the pad as it is while the finger is on it.
  card.hass = update(hass, { ...visit(...throws), "sensor.training_darts": "7" });
  assert.equal($(card, ".pad-board"), board);
  // Where it lets go, the dart is; the click after it counts once.
  touch(board, "pointerup", 1, 347, 178);
  tapAt(board, 17, 102);
  assert.deepEqual(actions(hass), [["correct_dart", { config_entry_id: ENTRY, dart: 1, x: 0.1, y: 0.6 }]]);
  assert.equal(loupe.hidden, true);

  // A finger taken away by the browser sets nothing; a mouse clicks as before.
  $(card, '[data-dart="1"]').click();
  const again = laidOut($(card, ".pad-board"));
  touch(again, "pointerdown", 2, 330, 280);
  touch(again, "pointercancel", 2, 330, 280);
  assert.equal(loupe.hidden, true);
  touch(again, "pointerup", 2, 330, 280);
  touch(again, "pointermove", 3, 330, 280);
  touch(again, "pointerdown", 4, 330, 280, "mouse");
  assert.equal(loupe.hidden, true);
  assert.equal(actions(hass).length, 1);
  card._touched = 0;
  tapAt(again, 0, 0);
  assert.deepEqual(actions(hass).at(-1), ["correct_dart", { config_entry_id: ENTRY, dart: 1, x: 0, y: 0 }]);
  // A board that is not laid out shows no loupe and sets nothing.
  $(card, '[data-dart="1"]').click();
  const hidden = $(card, ".pad-board");
  touch(hidden, "pointerdown", 5, 330, 280);
  assert.equal(loupe.hidden, true);
  touch(hidden, "pointerup", 5, 330, 280);
  assert.equal(actions(hass).length, 2);
});

test("two fingers zoom the board and move it, and set no dart", () => {
  const { hass, card } = setup({ "switch.practice_manual_entry": "on" }, { keypad: true });
  onScreen(card, 1000);
  $(card, '[data-pad="board"]').click();
  const board = laidOut($(card, ".pad-board"));
  // One finger enters a dart where it lets go; the click the browser sends after it
  // counts once.
  touch(board, "pointerdown", 1, 330, 280);
  touch(board, "pointerup", 1, 330, 280);
  tapAt(board, 0, 0);
  assert.deepEqual(actions(hass), [["throw_dart", { config_entry_id: ENTRY, x: 0, y: 0 }]]);
  hass.calls.length = 0;
  // Two fingers on the same spot, then apart: the board zooms from there.
  touch(board, "pointerdown", 1, 330, 280);
  touch(board, "pointerdown", 2, 330, 280);
  touch(board, "pointermove", 2, 331, 280);
  assert.equal(board.getAttribute("viewBox"), "-230 -230 460 460");
  touch(board, "pointerup", 1, 330, 280);
  touch(board, "pointerup", 2, 331, 280);
  touch(board, "pointerdown", 1, 230, 280);
  touch(board, "pointerdown", 2, 430, 280);
  // A second finger ends aiming: no loupe.
  assert.equal($(card, ".loupe").hidden, true);
  // Twice as far apart is twice as large, and the spot between them stays between them.
  touch(board, "pointermove", 2, 630, 280);
  assert.equal(board.getAttribute("viewBox"), "-165 -115 230 230");
  // A third finger changes nothing.
  touch(board, "pointerdown", 3, 100, 100);
  touch(board, "pointermove", 1, 230, 280);
  assert.equal(board.getAttribute("viewBox"), "-165 -115 230 230");
  touch(board, "pointerup", 1, 230, 280);
  touch(board, "pointerup", 2, 630, 280);
  touch(board, "pointerup", 3, 100, 100);
  assert.deepEqual(actions(hass), []);
  // The zoom stays, and the switch shows the whole board again.
  assert.equal(viewBox(card), "-165 -115 230 230");
  assert.deepEqual(zoomSwitch(card), ["Whole board", "true"]);
  // Far apart, five times larger at most; close together, the whole board.
  const next = laidOut($(card, ".pad-board"));
  touch(next, "pointerdown", 1, 320, 280);
  touch(next, "pointerdown", 2, 340, 280);
  touch(next, "pointermove", 2, 1000, 280);
  assert.equal(next.getAttribute("viewBox").split(" ")[2], "92");
  touch(next, "pointermove", 2, 330, 280);
  assert.equal(next.getAttribute("viewBox"), "-230 -230 460 460");
  touch(next, "pointerup", 1, 320, 280);
  touch(next, "pointerup", 2, 330, 280);
  assert.deepEqual(zoomSwitch(card), ["Zoom", "false"]);
  // A board that is not laid out does not zoom.
  const flat = $(card, ".pad-board");
  flat.getBoundingClientRect = () => ({ left: 0, top: 0, width: 0, height: 0 });
  touch(flat, "pointerdown", 1, 320, 280);
  touch(flat, "pointerdown", 2, 340, 280);
  touch(flat, "pointermove", 2, 400, 280);
  assert.equal(flat.getAttribute("viewBox"), "-230 -230 460 460");
});

test("the bot's darts, darts of an ended visit and a preview stay as they are", () => {
  const bot = dart(20, 3, { dart: 1, bot: true, x: 0, y: 0.6 });
  const { hass, card } = setup(visit(bot, dart(1, 1)));
  assert.deepEqual(chips(card), [
    ["div", "dart bot", null],
    ["div", "dart", null],
    ["div", "dart empty", null],
  ]);
  const off = mount("homedarts-scoreboard-card", hass, { corrections: false });
  off.hass = update(hass, visit(dart(20, 3, { dart: 1 })));
  assert.deepEqual(chips(off), [
    ["div", "dart", null],
    ["div", "dart empty", null],
    ["div", "dart empty", null],
  ]);
  const preview = setup(visit(dart(20, 3, { dart: 1 }))).card;
  preview.preview = true;
  preview.hass = update(hass, { ...visit(dart(20, 3, { dart: 1 })), "sensor.training_darts": "1" });
  assert.equal(chips(preview)[0][0], "div");
  preview._pickDart(1);
  preview._padAction("bed", "T20");
  assert.equal($(preview, ".pad-area").hidden, true);
  assert.deepEqual(actions(hass), []);
  // A dart that is gone opens nothing.
  card._pickDart(3);
  assert.equal($(card, ".pad-area").hidden, true);
});

test("the keypad enters darts while manual entry is on", () => {
  const { hass, card } = setup({ "switch.practice_manual_entry": "off" }, { keypad: true });
  assert.equal($(card, ".pad-area").hidden, true);
  card.hass = update(hass, { "switch.practice_manual_entry": "on" });
  assert.equal(text(card, ".pad .section-label"), "Enter a dart");
  $(card, '[data-pad="multiplier"][data-value="3"]').click();
  $(card, '.pad-number[data-value="T20"]').click();
  // Every dart starts from a single again.
  assert.equal(text(card, '.pad [aria-pressed="true"]'), "S");
  $(card, '[data-value="BULL"]').click();
  $(card, '[data-value="MISS"]').click();
  assert.deepEqual(actions(hass), [
    ["throw_dart", { config_entry_id: ENTRY, segment: "T20" }],
    ["throw_dart", { config_entry_id: ENTRY, segment: "BULL" }],
    ["throw_dart", { config_entry_id: ENTRY, segment: "MISS" }],
  ]);
  // The next player needs a second tap.
  hass.calls.length = 0;
  $(card, '[data-pad="next"]').click();
  assert.equal(text(card, '[data-pad="next"]'), "Confirm?");
  assert.deepEqual(actions(hass), []);
  $(card, '[data-pad="next"]').click();
  assert.deepEqual(actions(hass), [["next_player", { config_entry_id: ENTRY }]]);
  assert.equal(text(card, '[data-pad="next"]'), "Next player");
  // The last visit beside the darts undoes it, as without the keypad, while no dart
  // is on the board; the keypad keeps its keys whatever happened before.
  assert.equal($(card, '[data-pad="undo"]'), null);
  const entering = { "switch.practice_manual_entry": "on" };
  card.hass = update(hass, { ...entering, ...practice({ undo: true }) });
  assert.equal($(card, '.pad [data-pad="undo"]'), null);
  $(card, '.visit [data-pad="undo"]').click();
  assert.equal(text(card, ".visit .sum"), "Undo?–");
  $(card, '.visit [data-pad="undo"]').click();
  assert.deepEqual(actions(hass).at(-1), ["undo_visit", { config_entry_id: ENTRY }]);
  card.hass = update(hass, { ...entering, ...practice({ undo: true }), ...visit(dart(20, 1, { dart: 1 })) });
  assert.equal($(card, '[data-pad="undo"]'), null);
});

test("while the bot throws the keypad waits, and it makes room for the other screens", () => {
  const states = {
    "switch.practice_manual_entry": "on",
    "select.practice_game": { state: "301", attributes: { options: ["off", "301"] } },
    ...practice({ player: 2, name: null }),
  };
  const { hass, card } = setup(states, { keypad: true });
  assert.equal(
    $$(card, ".pad button").every((button) => button.disabled),
    true,
  );
  // In the bull-off, too.
  card.hass = update(hass, {
    "sensor.practice_remaining": {
      state: "unknown",
      attributes: {
        game: 301,
        bull_off: {
          player: 2,
          throws: [
            { player: 1, name: "Alex" },
            { player: 2, bot: true },
          ],
        },
      },
    },
  });
  assert.equal(
    $$(card, ".pad button").every((button) => button.disabled),
    true,
  );
  card.hass = update(hass, practice());
  assert.equal(
    $$(card, ".pad button").some((button) => button.disabled),
    false,
  );
  // The new game screen takes the room of the visit and the pad.
  $(card, ".lobby-toggle").click();
  assert.equal($(card, ".pad-area").hidden, true);
  $(card, '[data-lobby="close"]').click();
  assert.equal($(card, ".pad-area").hidden, false);
});

test("without the keypad, a tap on the last visit beside the darts undoes it", () => {
  const last = {
    "sensor.local_visit_score": {
      state: "0",
      attributes: { throws: [], recent_visits: [{ score: 85, segments: ["T20", "S20", "S5"] }] },
    },
  };
  const { hass, card } = setup({ ...practice({ undo: true }), ...last });
  const tile = () => $(card, '.visit [data-pad="undo"]');
  const shown = () => [tile().className, text(card, ".visit .sum"), tile().getAttribute("aria-label")];
  // It takes the place of a button of its own, so nothing below the darts appears.
  assert.equal($(card, ".pad-area").hidden, true);
  assert.deepEqual(shown(), ["sum last tappable", "Last85", "Undo last visit: 85"]);
  assert.equal(tile().querySelectorAll(".cue.undo").length, 1);
  tile().click();
  assert.deepEqual(shown(), ["sum last tappable confirm", "Undo?85", "Confirm?"]);
  assert.deepEqual(actions(hass), []);
  tile().click();
  assert.deepEqual(actions(hass), [["undo_visit", { config_entry_id: ENTRY }]]);
  // A dart on the board, or corrections switched off, leave the tile as it is.
  card.hass = update(hass, { ...practice({ undo: true }), ...visit(dart(20, 1, { dart: 1 })) });
  assert.equal(tile(), null);
  const off = mount("homedarts-scoreboard-card", hass, { corrections: false });
  off.hass = update(hass, { ...practice({ undo: true }), ...last });
  assert.equal($(off, '[data-pad="undo"]'), null);
  assert.equal(text(off, ".visit .sum"), "Last85");
  // A board without a config entry sends the actions without one; an unknown last
  // visit still undoes.
  const alone = mount(
    "homedarts-scoreboard-card",
    makeHass({ states: { ...READY, ...practice({ undo: true }), ...visit() } }),
  );
  assert.equal(text(alone, ".visit .sum"), "Last–");
  $(alone, '[data-pad="undo"]').click();
  $(alone, '[data-pad="undo"]').click();
  assert.deepEqual(alone._hass.calls.at(-1), ["homedarts", "undo_visit", {}]);
});

test("the pad speaks German", () => {
  const { card } = setup(
    { "switch.practice_manual_entry": "on", ...visit(dart(20, 1, { dart: 1 })) },
    { keypad: true },
    { language: "de" },
  );
  assert.equal(text(card, ".pad .section-label"), "Dart eingeben");
  assert.equal($(card, '[data-pad="multiplier"][data-value="3"]').getAttribute("aria-label"), "Triple");
  $(card, '[data-dart="1"]').click();
  assert.equal(text(card, ".pad .section-label"), "Dart 1 korrigieren");
  assert.equal(text(card, '[data-pad="cancel"]'), "Abbrechen");
  assert.equal(text(card, ".player.active .route"), "T20T20S17Rest 32");
});

test("the editor has a section for correcting and entering darts", () => {
  // The form speaks the language of the page.
  mount("homedarts-scoreboard-card", makeHass({ states: READY })).remove();
  const Card = customElements.get("homedarts-scoreboard-card");
  const form = Card.getConfigForm();
  const section = form.schema.find((field) => field.name === "input_section");
  assert.deepEqual([section.type, section.flatten], ["expandable", true]);
  assert.equal(form.computeLabel(section), "Correcting and entering darts");
  assert.match(form.computeHelper(section), /^Tap a dart of the visit/);
  const [corrections, keypad] = section.schema[0].schema;
  assert.deepEqual([corrections.default, keypad.default], [true, false]);
  assert.equal(
    form.computeHelper(keypad),
    "Shows while Practice manual entry is on, and always on a dartboard without Autodarts.",
  );
  assert.equal(typeof cardForm, "function");
});

// -- the lobby -------------------------------------------------------------------------

const BOARD = {
  game: "501",
  players: 1,
  names: ["Alex", "", "", ""],
  legs: 1,
  sets: 1,
  starts: [],
};
const GAMES = ["301", "501", "cricket", "shanghai", "doubles"];

test("the new game screen seats the bot at its level", () => {
  let choice = lobbyChoice({ ...BOARD, bot: 80 }, GAMES);
  assert.equal(choice.bot, 80);
  assert.equal("bot" in lobbyChoice(BOARD, GAMES), false);
  assert.equal(lobbyChoice({ ...BOARD, bot: 200 }, GAMES).bot, 120);
  assert.equal("bot" in lobbyChoice({ ...BOARD, bot: 10 }, GAMES), false);
  assert.deepEqual(startGameData(choice), {
    game: "501",
    players: ["Alex"],
    legs: 1,
    sets: 1,
    bull_off: false,
    in_mode: "straight",
    out_mode: "double",
    bull_mode: "25_50",
    max_rounds: 0,
    bot_level: 80,
  });
  choice = lobbyChange(choice, "bot", "raise");
  choice = lobbyChange(choice, "bot", "raise");
  choice = lobbyChange(choice, "bot", "raise");
  assert.equal(choice.bot, 110);
  choice = lobbyChange(lobbyChange(choice, "bot", "raise"), "bot", "raise");
  assert.equal(choice.bot, 120);
  choice = lobbyChange(choice, "bot", "remove");
  assert.equal(choice.bot, 0);
  // Removed, the bot leaves the game, and it cannot get weaker or come back twice.
  assert.equal(startGameData(choice).bot_level, 0);
  assert.equal(lobbyChange(choice, "bot", "lower").bot, 0);
  choice = lobbyChange(choice, "bot", "add");
  assert.equal(choice.bot, 60);
  assert.equal(lobbyChange(choice, "bot", "add").bot, 60);
  assert.equal(
    lobbyChange(
      lobbyChange(lobbyChange(lobbyChange(choice, "bot", "lower"), "bot", "lower"), "bot", "lower"),
      "bot",
      "lower",
    ).bot,
    20,
  );
  assert.equal(lobbyChange(choice, "bot", "unknown").bot, 60);
  // With the bot, three players at most; four players leave no seat for it.
  let full = { ...choice, players: ["A", "B", "C"], starts: [0, 0, 0] };
  assert.deepEqual(lobbyChange(full, "add", "D").players, ["A", "B", "C"]);
  full = lobbyChange({ ...full, bot: 0 }, "add", "D");
  assert.equal(lobbyChange(full, "bot", "add").bot, 0);
  // Three players and the bot make two teams.
  const teams = { ...choice, players: ["A", "B", "C"], starts: [0, 0, 0], teams: true };
  assert.deepEqual(startGameData(teams), {
    game: "501",
    players: ["A", "B", "C"],
    legs: 1,
    sets: 1,
    bull_off: false,
    in_mode: "straight",
    out_mode: "double",
    bull_mode: "25_50",
    max_rounds: 0,
    bot_level: 60,
    teams: true,
  });
  // The bot plays no party or training games, and no tournament.
  assert.equal("bot_level" in startGameData({ ...choice, game: "shanghai" }), false);
  assert.equal(startGameData({ ...choice, game: "shanghai", players: [] }).legs, undefined);
  assert.equal(startGameData({ ...choice, game: "cricket", players: [] }).legs, 1);
});

const PEOPLE_BOARD = {
  "sensor.local_visit_score": { state: "0", attributes: { throws: [] } },
  "select.practice_game": { state: "off", attributes: { options: ["off", "501", "shanghai"] } },
  "number.practice_players": "1",
  "number.practice_legs": "1",
  "number.practice_sets": "1",
  "switch.practice_double_out": "on",
  "switch.practice_double_in": "off",
  "switch.practice_bull_off": "off",
  "sensor.practice_remaining": "unknown",
};

function withNames(hass, names) {
  names.forEach((name, index) => {
    const id = `text.dartboard_practice_player_${index + 1}`;
    hass.entities[id] = { entity_id: id, platform: "homedarts", device_id: DEVICE, translation_key: "practice_player" };
    hass.states[id] = { entity_id: id, state: name, attributes: {} };
  });
  return hass;
}

test("the bot's seat on the new game screen", async () => {
  const hass = withNames(
    makeHass({
      states: { ...READY, ...PEOPLE_BOARD, "number.practice_bot_level": "70" },
      device: { primary_config_entry: ENTRY },
    }),
    ["Alex"],
  );
  const card = mount("homedarts-scoreboard-card", hass);
  $(card, ".lobby-toggle").click();
  assert.deepEqual(
    $$(card, ".lobby-player .who").map((name) => name.textContent),
    ["Alex", "Bot"],
  );
  assert.equal(text(card, ".lobby-player.bot .lobby-start b"), "70");
  assert.equal($(card, '[data-lobby="bot"][data-value="lower"]').getAttribute("aria-label"), "Weaker bot");
  $(card, '[data-lobby="bot"][data-value="raise"]').click();
  assert.equal(text(card, ".lobby-player.bot .lobby-start b"), "80");
  $(card, '[data-lobby="bot"][data-value="remove"]').click();
  assert.equal($(card, ".lobby-player.bot"), null);
  assert.equal(text(card, ".suggestion.bot"), "+ Bot");
  $(card, ".suggestion.bot").click();
  assert.equal(text(card, ".lobby-player.bot .lobby-start b"), "60");
  // A game of one player and the bot is a match: legs and sets, and the bull-off; X01
  // has its round limit besides.
  assert.equal($$(card, ".stepper").length, 3);
  // Party games have no seat for the bot.
  $(card, '[data-lobby="game"][data-value="shanghai"]').click();
  assert.equal($(card, ".lobby-player.bot"), null);
  assert.equal($(card, ".suggestion.bot"), null);
  $(card, '[data-lobby="game"][data-value="501"]').click();
  $(card, ".lobby .start").click();
  assert.deepEqual(actions(hass).at(-1), [
    "start_game",
    {
      game: "501",
      players: ["Alex"],
      config_entry_id: ENTRY,
      legs: 1,
      sets: 1,
      bull_off: false,
      in_mode: "straight",
      out_mode: "double",
      bull_mode: "25_50",
      max_rounds: 0,
      bot_level: 60,
    },
  ]);
  await settle();
  // In German.
  card.hass = withLanguage(update(hass, { "number.practice_bot_level": "20" }), "de");
  $(card, ".lobby-toggle").click();
  assert.equal($(card, '[data-lobby="bot"][data-value="lower"]').disabled, true);
  assert.equal($(card, '[data-lobby="bot"][data-value="raise"]').getAttribute("aria-label"), "Stärkerer Bot");
  assert.equal($(card, '[data-lobby="bot"][data-value="remove"]').getAttribute("aria-label"), "Bot entfernen");
});

test("the pad sits beside the scores and keeps the focus on the button that was pressed", () => {
  const { hass, card } = setup({ "switch.practice_manual_entry": "on" }, { keypad: true, full_height: true });
  // The full-height scoreboard lays the pad beside the scores in landscape.
  assert.equal($(card, ".scoreboard").classList.contains("with-pad"), true);
  const pressedFocus = (selector) => {
    const button = $(card, selector);
    button.focus();
    button.click();
    return card.shadowRoot.activeElement.dataset.focus;
  };
  assert.equal(pressedFocus('[data-pad="multiplier"][data-value="2"]'), "multiplier:2");
  assert.equal(pressedFocus('[data-pad="next"]'), "next:");
  assert.equal(pressedFocus('[data-pad="next"]'), "next:");
  // The undo of the last visit beside the darts is no pad beside the scores.
  card.hass = update(hass, { ...practice({ undo: true }), "switch.practice_manual_entry": "off" });
  assert.equal(pressedFocus('.visit [data-pad="undo"]'), "undo:");
  assert.equal($(card, ".scoreboard").classList.contains("with-pad"), false);
});
