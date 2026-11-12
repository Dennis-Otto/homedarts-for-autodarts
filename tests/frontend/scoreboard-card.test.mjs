// The scoreboard card in a browser DOM: every game, the visit and the caller.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, READY, loadCards, makeHass, mount, text, update, window } from "./dom.mjs";

await loadCards();

const dart = (number, multiplier) => ({ number, multiplier, bed: multiplier === 3 ? "Triple" : "SingleOuter" });
const T20 = dart(20, 3);
const visit = (...throws) => ({
  "sensor.local_visit_score": {
    state: String(throws.reduce((sum, item) => sum + item.number * item.multiplier, 0)),
    attributes: { throws },
  },
});
const PLAYERS = [
  { player: 1, name: "Alex", remaining: 501, legs: 0, sets: 0, average: null },
  { player: 2, name: "Sam", remaining: 301, legs: 0, sets: 0, average: null },
];
const game = (attributes, state = String(attributes.remaining ?? "unknown")) => ({
  "sensor.practice_remaining": {
    state,
    attributes: { game: 501, player: 1, name: "Alex", scores: PLAYERS, ...attributes },
  },
});
const STATS = {
  "sensor.training_darts": "24",
  "sensor.training_average": "55.75",
  "sensor.training_highest_visit": "140",
  "sensor.training_scores_180": "0",
  "sensor.training_streak": "3",
  "sensor.darts_today": { state: "60", attributes: { goal: 120 } },
};
const setup = (states = {}, config = {}, options = {}) => {
  const hass = makeHass({ states: { ...READY, ...visit(), ...states }, ...options });
  return { hass, card: mount("homedarts-scoreboard-card", hass, config) };
};
const sum = (card) => [...$(card, ".visit .sum").children].map((part) => part.textContent);
const facts = (card) => $$(card, ".facts span").map((fact) => fact.textContent);
const slots = (card) =>
  $$(card, ".visit .dart").map((slot) => [
    slot.className,
    slot.querySelector(".segment").textContent,
    slot.querySelector(".points").textContent,
  ]);

// Speech and sound as a browser offers them, recorded.
const spoken = [];
class Utterance {
  constructor(words) {
    this.text = words;
    this.lang = "";
  }
}
const speech = {
  speak: (utterance) => spoken.push([utterance.text, utterance.lang]),
  cancel: () => spoken.push(["cancel"]),
};
const contexts = [];
class FakeAudioContext {
  constructor() {
    contexts.push(this);
    this.currentTime = 2;
    this.destination = { name: "speakers" };
    this.resumed = 0;
    this.tones = [];
  }

  resume() {
    this.resumed += 1;
  }

  createOscillator() {
    const tone = {
      frequency: {},
      connect: (node) => {
        tone.output = node;
        return node;
      },
      start: (at) => (tone.start = at),
      stop: (at) => (tone.stop = at),
    };
    this.tones.push(tone);
    return tone;
  }

  createGain() {
    const ramp = [];
    return {
      ramp,
      gain: {
        setValueAtTime: (value, at) => ramp.push([value, Number(at.toFixed(2))]),
        exponentialRampToValueAtTime: (value, at) => ramp.push([value, Number(at.toFixed(2))]),
      },
      connect(node) {
        this.output = node;
        return node;
      },
    };
  }
}
window.speechSynthesis = speech;
globalThis.SpeechSynthesisUtterance = Utterance;
const tap = (card) => $(card, ".caller-toggle").click();
const said = () => spoken.splice(0).map(([words]) => words);

test("between games the scoreboard shows the visit and the session", () => {
  const { card } = setup({ ...visit(T20), ...STATS });
  assert.equal(text(card, ".title"), "Dartboard");
  assert.equal(text(card, ".meta"), "Training");
  assert.equal($(card, ".banner").hidden, true);
  assert.equal(text(card, ".main .label"), "Current visit");
  assert.equal(text(card, ".main .big"), "60");
  assert.deepEqual(facts(card), [
    "24 Darts",
    "55.8 3-dart avg.",
    "140 Highest visit",
    "0 180s",
    "3 days in a row",
    "60 / 120 darts today",
  ]);
  assert.equal($(card, ".visit").getAttribute("class"), "visit");
  assert.deepEqual(slots(card), [
    ["dart", "T20", "60"],
    ["dart empty", "–", ""],
    ["dart empty", "–", ""],
  ]);
  // The big number is the visit; beside the darts is the last one, still unknown here.
  assert.deepEqual(sum(card), ["Last", "–"]);
  assert.equal(text(card, ".pill"), "Ready – throw!");
  assert.equal(card.style.getPropertyValue("--ad-status"), "var(--success-color, #43a047)");
});

test("between games the facts leave out what is unknown", () => {
  const { hass, card } = setup({
    ...STATS,
    "sensor.local_visit_score": "unavailable",
    "sensor.training_streak": "1",
    "sensor.darts_today": "35",
  });
  assert.equal(text(card, ".main .big"), "–");
  assert.deepEqual(facts(card).slice(4), ["1 day in a row", "35 darts today"]);
  card.hass = update(hass, { "sensor.training_streak": "0", "sensor.darts_today": "unavailable" });
  assert.equal(facts(card).length, 4);
});

test("an X01 match shows every player, the legs and sets to win and the visit", () => {
  const { card } = setup({
    ...visit(T20, dart(20, 1)),
    ...game({ remaining: 81, checkout: "T15 D18", legs_to_win: 3, sets_to_win: 2 }),
  });
  assert.equal(text(card, ".title"), "Practice 501");
  assert.equal(text(card, ".meta"), "3 legs per set · 2 sets to win");
  assert.equal($(card, ".main .players").getAttribute("class"), "players n2");
  assert.deepEqual(
    $$(card, ".main .player").map((tile) => [tile.className, tile.querySelector(".name").textContent]),
    [
      ["player active", "Alex"],
      ["player", "Sam"],
    ]
  );
  assert.equal($(card, ".visit").getAttribute("class"), "visit");
  assert.deepEqual(slots(card), [
    ["dart", "T20", "60"],
    ["dart", "S20", "20"],
    ["dart empty", "–", ""],
  ]);
  assert.deepEqual(sum(card), ["Visit", "80"]);
});

test("the winner of a match gets the banner", () => {
  const { card } = setup({ ...game({ remaining: 0, won: true, winner: 1 }, "0") });
  assert.equal($(card, ".banner").hidden, false);
  assert.equal(text(card, ".banner"), "Alex wins the match!");
  assert.equal($(card, ".main .player.winner .name").textContent, "Alex Winner");
});

test("Cricket, party games, the bull-off and training games get their own boards", () => {
  const { hass, card } = setup({
    ...game({ game: "cricket", target: "T20", scores: [{ player: 1, marks: [2, 0, 0, 0, 0, 0, 0], points: 0 }] }),
    "sensor.practice_target": { state: "unknown", attributes: { drill: null } },
  });
  assert.equal(text(card, ".title"), "Cricket");
  assert.equal($$(card, ".main table.cricket tbody tr").length, 8);
  assert.equal(text(card, ".main .aim"), "T20");

  card.hass = update(hass, game({ game: "killer", phase: "choose", scores: [{ player: 1 }, { player: 2 }] }));
  assert.equal(text(card, ".title"), "Killer");
  assert.equal(text(card, ".main .player.active .route"), "Throw for your number");

  card.hass = update(hass, game({ game: "shanghai", round: 4, rounds: 7, target: "4", points: 12 }));
  assert.equal(text(card, ".meta"), "Round 4/7");

  card.hass = update(
    hass,
    game({ bull_off: { player: 1, throws: [{ player: 1, name: "Alex", hit: "BULL", distance: 8.6 }] } })
  );
  assert.equal(text(card, ".title"), "Bull-off");
  assert.equal(text(card, ".meta"), "Closest to the bull starts");
  assert.equal(text(card, ".main .big"), "Bull");
  assert.equal(text(card, ".main .details"), "8.6 mm");
  assert.equal($(card, ".banner").hidden, true);

  card.hass = update(hass, {
    "sensor.practice_target": { state: "D5", attributes: { drill: "doubles", progress: 4, targets: 21, darts: 9 } },
  });
  assert.equal(text(card, ".title"), "Doubles training");
  assert.equal(text(card, ".main .big"), "D5");
  assert.equal($(card, ".main .big").className, "big");
  // The bull of Around the Clock reads in smaller type to fit the screen.
  card.hass = update(hass, {
    "sensor.practice_target": { state: "25", attributes: { drill: "around_the_clock", progress: 20, targets: 21 } },
  });
  assert.equal(text(card, ".main .big"), "Bull (25/50)");
  assert.equal($(card, ".main .big").className, "big long");
  card.hass = update(hass, {
    "sensor.practice_target": { state: "D5", attributes: { drill: "doubles", progress: 4, targets: 21, darts: 9 } },
  });
  assert.deepEqual(sum(card), ["Last", "–"]);
});

test("status, visit and full height follow the options", () => {
  const plain = setup({}, { show_status: false, show_visit: false }).card;
  assert.equal($(plain, ".pill"), null);
  assert.equal($(plain, ".visit"), null);
  assert.equal($(plain, ".scoreboard").getAttribute("class"), "scoreboard");
  assert.equal(text(plain, ".title"), "Dartboard");
  // Only scores of a full-height scoreboard scroll; then a keyboard can scroll them too.
  assert.equal($(plain, ".main").getAttribute("tabindex"), null);
  const full = setup({}, { full_height: true }).card;
  assert.equal($(full, ".scoreboard").getAttribute("class"), "scoreboard full");
  const scores = $(full, ".main");
  assert.deepEqual(
    ["tabindex", "role", "aria-label"].map((name) => scores.getAttribute(name)),
    ["0", "region", "Scoreboard"]
  );
  assert.equal(full.getCardSize(), 8);
  assert.deepEqual(full.getGridOptions(), { columns: "full", min_columns: 6 });
  // A phone's browser bar must not cut off the bottom of a full-height scoreboard.
  const style = $(full, "style").textContent;
  assert.ok(style.indexOf("min-height: calc(100vh") < style.indexOf("min-height: calc(100dvh"));
});

test("the scoreboard speaks German", () => {
  const { card } = setup({ ...STATS, ...game({ remaining: 81, legs_to_win: 3 }) }, {}, { language: "de" });
  assert.equal(text(card, ".title"), "Übungsspiel 501");
  assert.equal(text(card, ".meta"), "3 Legs pro Satz");
  assert.deepEqual(sum(card), ["Zuletzt", "–"]);
  assert.equal(text(card, ".pill"), "Bereit – wirf!");
});

test("an X01 leg alone explains double in, and the visit reads a dash while unknown", () => {
  const alone = (attributes) => game({ scores: [], name: null, ...attributes });
  const { hass, card } = setup({ ...alone({ remaining: 501, opened: false }), "sensor.local_visit_score": "unknown" });
  assert.equal(text(card, ".main .route"), "Start with a double");
  assert.deepEqual(sum(card), ["Last", "–"]);
  // Darts on the board with a score not known yet.
  card.hass = update(hass, { "sensor.local_visit_score": { state: "unknown", attributes: { throws: [T20] } } });
  assert.deepEqual(sum(card), ["Visit", "–"]);
  card.hass = update(hass, { "sensor.local_visit_score": "unknown" });
  card.hass = update(hass, alone({ game: null, remaining: 170 }));
  assert.equal(text(card, ".title"), "Practice");
  assert.equal(text(card, ".main .route"), "No checkout possible");
});

test("a party of eight fills two rows of four tiles", () => {
  const names = ["Alex", "Sam", "Kim", "Lea", "Mia", "Leo", "Zoe", "Ben"];
  const scores = names.map((name, index) => ({ player: index + 1, name, points: 10 * index, hits: index }));
  const { card } = setup(game({ game: "count_up", round: 1, rounds: 8, scores }));
  assert.equal($(card, ".main .players").className, "players n8");
  assert.deepEqual(
    $$(card, ".main .player .name").map((name) => name.textContent),
    names
  );
});

test("party games on the scoreboard show lives, targets and the winner", () => {
  const killers = [
    { player: 1, name: "Alex", number: 7, lives: 3, killer: true, legs: 1, sets: 0 },
    { player: 2, name: "Sam", number: 12, lives: 0, killer: false, legs: 0, sets: 1 },
  ];
  const killer = (attributes) =>
    game({ game: "killer", scores: killers, legs_to_win: 2, sets_to_win: 2, ...attributes });
  // Alex took the second set with two legs.
  const won = [
    { ...killers[0], legs: 2, sets: 2 },
    { ...killers[1], legs: 0, sets: 1 },
  ];
  const tiles = (card) =>
    $$(card, ".main .player").map((tile) => [
      tile.className,
      tile.querySelector(".big").className,
      tile.querySelector(".big").textContent,
      tile.querySelector(".route").textContent,
      tile.querySelector(".details").textContent,
    ]);
  const { hass, card } = setup(killer({}));
  assert.equal(text(card, ".meta"), "2 legs per set · 2 sets to win");
  assert.deepEqual(tiles(card), [
    [
      "player active",
      "big lives",
      "♥♥♥",
      "Killer – hit the others' doubles",
      "Legs 1 · Sets 0 · 7 · Killer",
    ],
    ["player out", "big lives", "✕", "", "Legs 0 · Sets 1 · 12 · out"],
  ]);
  // Hearts are read as lives, not as heart symbols.
  assert.deepEqual(
    $$(card, ".main .big.lives").map((big) => [big.getAttribute("role"), big.getAttribute("aria-label")]),
    [
      ["img", "3 lives"],
      ["img", "0 lives"],
    ]
  );
  card.hass = update(hass, killer({ scores: [{ ...killers[0], lives: 1 }, killers[1]] }));
  assert.equal($(card, ".main .big.lives").getAttribute("aria-label"), "1 life");
  card.hass = update(hass, killer({ target: "D12" }));
  assert.equal(tiles(card)[0][3], "D12");
  card.hass = update(hass, killer({ needs_players: 2 }));
  assert.equal(tiles(card)[0][3], "Killer needs at least two players");
  card.hass = update(hass, killer({ won: true }));
  assert.equal(tiles(card)[0][3], "Game shot!");
  card.hass = update(hass, killer({ winner: 1, scores: won }));
  assert.equal(tiles(card)[0][0], "player winner");
  assert.equal(text(card, ".banner"), "Alex wins the match 2 : 1!");

  const halveIt = (target) => game({ game: "halve_it", target, points: 40, scores: [{ player: 1, points: 40 }] });
  card.hass = update(hass, halveIt("D"));
  assert.deepEqual(tiles(card), [["player", "big", "40", "Any double", ""]]);
  card.hass = update(hass, halveIt("T"));
  assert.equal(tiles(card)[0][3], "Any treble");
  card.hass = update(hass, halveIt("25"));
  assert.equal(tiles(card)[0][3], "Bull (25/50)");
});

test("Cricket on the scoreboard shows legs, sets, the winner and a game shot", () => {
  const players = [
    { player: 1, name: "Alex", marks: [3, 3, 3, 3, 3, 3, 3], points: 60, legs: 1, sets: 1, mpr: 2.4 },
    { player: 2, name: "Sam", marks: [3, 2, 1, 0, 0, 0, 0], points: 20, legs: 0, sets: 0, mpr: null },
  ];
  const cricket = (attributes) =>
    game({ game: "cricket", target: "T19", scores: players, legs_to_win: 2, sets_to_win: 2, ...attributes });
  const { hass, card } = setup(cricket({ player: 2 }));
  const rows = () => $$(card, ".main tbody tr").map((row) => [row.className, row.textContent]);
  assert.deepEqual(rows().slice(-4), [
    ["total", "Points6020"],
    ["detail", "MPR2.40–"],
    ["detail", "Legs10"],
    ["detail", "Sets10"],
  ]);
  assert.deepEqual(
    $$(card, ".main thead th").map((cell) => [cell.className, cell.textContent]),
    [
      ["aim", "T19"],
      ["", "Alex"],
      ["active", "Sam"],
    ]
  );
  const won = [
    { ...players[0], legs: 2, sets: 2 },
    { ...players[1], legs: 0, sets: 0 },
  ];
  card.hass = update(hass, cricket({ winner: 1, won: true, scores: won }));
  assert.equal(text(card, ".banner"), "Alex wins the match 2 : 0!");
  assert.equal(text(card, ".main thead .aim"), "");
  assert.equal($(card, ".main thead th.winner").textContent, "Alex Winner");
  card.hass = update(hass, cricket({ scores: players.slice(0, 1), won: true }));
  assert.equal(text(card, ".main thead .aim"), "Game shot!");
});

test("the checkout training shows a dash without a target, and the game shot", () => {
  const checkout = (attributes) => ({
    "sensor.practice_target": {
      state: "unknown",
      attributes: { drill: "checkout", attempts: 1, successes: 0, ...attributes },
    },
  });
  const { hass, card } = setup(checkout({}));
  assert.equal(text(card, ".title"), "Checkout training");
  assert.equal(text(card, ".main .big"), "–");
  card.hass = update(hass, checkout({ remaining: 0, won: true, successes: 1 }));
  assert.equal(text(card, ".main .big"), "0");
  assert.equal(text(card, ".main .route"), "Game shot!");
});

// Sound is unlocked once per page, so the caller tests build on each other in order.

// An X01 visit as the practice sensor counts it: the remaining score after the darts it counted.
const x01 = (remaining, keys = [], attributes = {}) => game({ remaining, visit: keys, ...attributes });

test("a 180 brings confetti over the scoreboard, also without the caller, unless switched off", () => {
  const { hass, card } = setup(x01(501));
  const moment = () => $(card, ".celebrate .moment");
  assert.equal($(card, ".celebrate").getAttribute("aria-hidden"), "true");
  assert.equal(moment(), null);
  let next = update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  card.hass = next;
  assert.deepEqual([moment().className, moment().dataset.round, $$(card, ".celebrate i").length], ["moment max", "1", 36]);
  // The next 180 starts afresh.
  next = update(next, { ...visit(), ...x01(321, []) });
  card.hass = next;
  card.hass = update(next, { ...visit(T20, T20, T20), ...x01(141, ["T20", "T20", "T20"]) });
  assert.equal(moment().dataset.round, "2");
  // Switched off, and in the preview of the card picker, nothing is celebrated.
  for (const [config, preview] of [
    [{ celebrations: false }, false],
    [{}, true],
  ]) {
    const other = setup(x01(501), config);
    other.card.preview = preview;
    other.card.hass = update(other.hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
    assert.equal($(other.card, ".celebrate").children.length, 0);
  }
});

test("the caller is off by default and says nothing", () => {
  const { hass, card } = setup(game({ remaining: 501 }));
  assert.equal($(card, ".caller-toggle"), null);
  card.hass = update(hass, visit(T20, T20, T20));
  assert.deepEqual(spoken, []);
});

test("a tap switches the caller on, even without Web Audio, and a second tap mutes it", () => {
  const { hass, card } = setup(x01(501), { caller: true });
  const button = $(card, ".caller-toggle");
  // The label stays; the pressed state and the speaker tell whether the caller is on.
  const state = () => [button.getAttribute("aria-pressed"), button.textContent, button.title];
  assert.deepEqual(state(), ["false", "🔇Caller", "Tap to switch the caller on or off"]);
  assert.equal(button.querySelector(".caller-icon").getAttribute("aria-hidden"), "true");
  card.hass = update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  assert.deepEqual(spoken, []);

  tap(card);
  assert.deepEqual(spoken.splice(0), [["Caller on", "en"]]);
  assert.deepEqual(state(), ["true", "🔊Caller", "Tap to switch the caller on or off"]);
  card.hass = update(hass, visit());
  card.hass = update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  // Without an audio context the fanfare stays silent.
  assert.deepEqual(said(), ["180"]);
  assert.equal(contexts.length, 0);

  tap(card);
  assert.deepEqual(spoken.splice(0), [["cancel"]]);
  assert.deepEqual(state(), ["false", "🔇Caller", "Tap to switch the caller on or off"]);
});

test("the caller unlocks the prefixed audio context of Safari and plays a fanfare for 180", () => {
  window.webkitAudioContext = FakeAudioContext;
  const { hass, card } = setup(x01(501), { caller: true });
  tap(card);
  assert.equal(contexts.length, 1);
  assert.equal(contexts[0].resumed, 1);
  card.hass = update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  assert.deepEqual(said(), ["Caller on", "180"]);
  const tones = contexts[0].tones;
  assert.deepEqual(
    tones.map((tone) => [tone.frequency.value, tone.type, Number(tone.start.toFixed(2)), Number(tone.stop.toFixed(2))]),
    [
      [523.25, "triangle", 2, 3],
      [659.25, "triangle", 2.14, 3.14],
      [783.99, "triangle", 2.28, 3.28],
      [1046.5, "triangle", 2.42, 3.42],
    ]
  );
  assert.deepEqual(tones[0].output.ramp, [
    [0.0001, 2],
    [0.25, 2.02],
    [0.0001, 2.3],
  ]);
  assert.deepEqual(tones[3].output.ramp.at(-1), [0.0001, 3.32]);
  assert.equal(tones[3].output.output, contexts[0].destination);
  tap(card);
  said();
});

test("later taps resume the one shared audio context, and the voice speaks the card's language", () => {
  window.AudioContext = FakeAudioContext;
  const { hass, card } = setup({}, { caller: true });
  // Without a locale the caller speaks Home Assistant's language, or English.
  card.hass = { ...hass, locale: undefined, language: "de" };
  tap(card);
  assert.equal(contexts.length, 1);
  assert.equal(contexts[0].resumed, 2);
  assert.deepEqual(spoken.splice(0), [["Caller an", "de"]]);
  tap(card);
  said();
  card.hass = { ...hass, locale: undefined, language: undefined };
  tap(card);
  assert.deepEqual(spoken.splice(0), [["Caller on", "en"]]);
  tap(card);
  said();
  // A regional variant keeps its voice; Italian gets the English words, so an English voice.
  for (const [lang, voice] of [
    ["en-GB", "en-GB"],
    ["de-CH", "de-CH"],
    ["nl-BE", "nl-BE"],
    ["fr", "fr"],
    ["es-419", "es-419"],
    ["it", "en"],
  ]) {
    card.hass = { ...hass, locale: { language: lang }, language: lang };
    tap(card);
    assert.equal(spoken.splice(0)[0][1], voice, lang);
    tap(card);
    said();
  }
});

test("the caller calls what counts: a visit's score, what a player requires, busts and the match", () => {
  const { hass, card } = setup(x01(501), { caller: true });
  tap(card);
  said();
  let next = update(hass, { ...visit(T20, dart(5, 1), dart(1, 1)), ...x01(435, ["T20", "S5", "S1"]) });
  card.hass = next;
  assert.deepEqual(said(), ["66"]);

  next = update(next, { ...visit(), ...x01(40, [], { player: 2, name: "Sam", checkout: "D20" }) });
  card.hass = next;
  assert.deepEqual(said(), ["Sam, you require 40"]);

  // A bust is "No score", without the sum of its darts before it.
  next = update(next, {
    ...visit(dart(20, 1), dart(20, 1), dart(5, 1)),
    ...x01(40, ["S20", "S20", "S5"], { player: 2, name: "Sam", checkout: "D20", bust: true }),
  });
  card.hass = next;
  assert.deepEqual(said(), ["No score"]);

  next = update(next, { ...visit(), ...x01(40, [], { player: 2, name: "Sam", checkout: "D20" }) });
  card.hass = next;
  assert.deepEqual(said(), ["Sam, you require 40"]);
  next = update(next, {
    ...visit(dart(20, 2)),
    ...x01(0, ["D20"], { player: 2, name: "Sam", won: true, winner: 2 }),
  });
  card.hass = next;
  assert.deepEqual(said(), ["Game shot, and the match, Sam!"]);
  tap(card);
  said();
});

test("the caller counts a visit from where it started, also after a state it missed", () => {
  // Alex alone; the takeout after the 140 goes by unseen, as on a tablet that woke up.
  const alone = (remaining, keys, from) => x01(remaining, keys, { visit_from: from, scores: [PLAYERS[0]] });
  const { hass, card } = setup(alone(501, [], 501), { caller: true });
  tap(card);
  said();
  let next = update(hass, { ...visit(T20, T20, dart(20, 1)), ...alone(361, ["T20", "T20", "S20"], 501) });
  card.hass = next;
  assert.deepEqual(said(), ["140"]);
  const one = dart(1, 1);
  next = update(next, { ...visit(one, one, one), ...alone(358, ["S1", "S1", "S1"], 361) });
  card.hass = next;
  assert.deepEqual(said(), ["3"]);
  tap(card);
  said();
});

test("a scoreboard that comes back calls and celebrates nothing that happened while it was away", () => {
  const ways = {
    // Away on another view: Home Assistant gives the card the new states once it is back.
    "another view": (card, states) => {
      card.remove();
      document.body.append(card);
      card.hass = states;
    },
    // Some dashboards give a card the new states while it is away.
    "states while away": (card, states) => {
      card.remove();
      card.hass = states;
      document.body.append(card);
    },
    // The connection drops and comes back, first with the states from before it dropped.
    "a lost connection": (card, states) => {
      const before = card._hass;
      card.hass = { ...before, connected: false };
      card.hass = { ...before, connected: false };
      card.hass = { ...before, connected: true };
      card.hass = states;
    },
  };
  for (const [way, away] of Object.entries(ways)) {
    const { hass, card } = setup(x01(40, [], { checkout: "D20" }), { caller: true });
    tap(card);
    said();
    // Meanwhile Alex threw the match.
    const won = update(hass, { ...visit(dart(20, 2)), ...x01(0, ["D20"], { won: true, winner: 1 }) });
    away(card, won);
    assert.deepEqual(said(), [], way);
    assert.equal($(card, ".celebrate").children.length, 0, way);
    // What happens after the return is called and celebrated again.
    const next = update(won, { ...visit(), ...x01(501, []) });
    card.hass = next;
    card.hass = update(next, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
    assert.deepEqual(said(), ["180"], way);
    assert.equal($(card, ".celebrate .moment").className, "moment max", way);
    tap(card);
    said();
  }
});

test("a connection that drops while nothing changes loses no call", () => {
  const { hass, card } = setup(x01(501), { caller: true });
  tap(card);
  said();
  card.hass = { ...hass, connected: false };
  card.hass = { ...hass, connected: true };
  // Home Assistant fetches every state anew after it reconnected.
  card.hass = update(hass, {});
  card.hass = update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  assert.deepEqual(said(), ["180"]);
  tap(card);
  said();
  // A scoreboard that leaves before it saw Home Assistant comes back as a new one.
  const bare = mount("homedarts-scoreboard-card");
  bare.remove();
  document.body.append(bare);
  bare.hass = hass;
  assert.ok($(bare, ".main"));
});

test("a scoreboard that comes back to an unchanged game calls the very next dart", async () => {
  const { hass, card } = setup(x01(40, [], { checkout: "D20" }), { caller: true });
  tap(card);
  said();
  // Away on another view and back between two darts: Home Assistant has no new states.
  card.remove();
  document.body.append(card);
  await new Promise((resolve) => setTimeout(resolve));
  card.hass = update(hass, { ...visit(dart(20, 2)), ...x01(0, ["D20"], { won: true, winner: 1 }) });
  assert.deepEqual(said(), ["Game shot, and the match, Alex!"]);
  assert.ok($(card, ".celebrate").children.length > 0);
  tap(card);
  said();
});

test("two scoreboards of one board in a view call every call once", () => {
  // A large scoreboard and a smaller one beside it, both with the caller; one tap unlocks both.
  const { hass, card } = setup(x01(501), { caller: true });
  const beside = mount("homedarts-scoreboard-card", hass, { caller: true, full_height: false });
  tap(card);
  said();
  const show = (states) => {
    card.hass = states;
    beside.hass = states;
    return said();
  };
  let next = update(hass, { ...visit(T20, T20, dart(20, 1)), ...x01(361, ["T20", "T20", "S20"]) });
  assert.deepEqual(show(next), ["140"]);
  next = update(next, { ...visit(), ...x01(40, [], { player: 2, name: "Sam", checkout: "D20" }) });
  assert.deepEqual(show(next), ["Sam, you require 40"]);
  next = update(next, {
    ...visit(dart(20, 1), dart(20, 1), dart(5, 1)),
    ...x01(40, ["S20", "S20", "S5"], { player: 2, name: "Sam", checkout: "D20", bust: true }),
  });
  assert.deepEqual(show(next), ["No score"]);
  // A call that only the card beside makes is still made, once.
  card.setConfig({ type: "custom:homedarts-scoreboard-card", caller: true, call_checkouts: false });
  next = update(next, { ...visit(), ...x01(40, [], { player: 2, name: "Sam", checkout: "D20" }) });
  card.hass = next;
  assert.deepEqual(said(), []);
  beside.hass = next;
  assert.deepEqual(said(), ["Sam, you require 40"]);
  tap(card);
  said();
  beside.remove();
});

test("before the opening double a visit is no score, and without double out 180 can be required", () => {
  const { hass, card } = setup(x01(501, [], { opened: false }), { caller: true });
  tap(card);
  said();
  let next = update(hass, {
    ...visit(T20, T20, T20),
    ...x01(501, ["T20", "T20", "T20"], { opened: false }),
  });
  card.hass = next;
  // No fanfare for darts that did not count.
  assert.deepEqual(said(), ["No score"]);
  next = update(next, { ...visit(), ...x01(180, [], { player: 2, name: "Sam", checkout: "T20 T20 T20" }) });
  card.hass = next;
  assert.deepEqual(said(), ["Sam, you require 180"]);
  tap(card);
  said();
});

test("Cricket calls the marks of a visit, not points", () => {
  const players = [
    { player: 1, name: "Alex", marks: [0, 0, 0, 0, 0, 0, 0], points: 0 },
    { player: 2, name: "Sam", marks: [0, 0, 0, 0, 0, 0, 0], points: 0 },
  ];
  const cricket = (keys) => game({ game: "cricket", target: "T20", scores: players, visit: keys });
  const { hass, card } = setup(cricket([]), { caller: true });
  tap(card);
  said();
  card.hass = update(hass, { ...visit(T20, dart(19, 1), dart(3, 1)), ...cricket(["T20", "S19", "S3"]) });
  assert.deepEqual(said(), ["4 marks"]);
  tap(card);
  said();
});

test("alone, the caller calls the requirement without a name and the leg", () => {
  const alone = (attributes) => game({ scores: [], name: null, ...attributes });
  const { hass, card } = setup(alone({ remaining: 60 }), { caller: true }, { language: "de" });
  tap(card);
  assert.deepEqual(spoken.splice(0), [["Caller an", "de"]]);
  let next = update(hass, alone({ remaining: 40, checkout: "D20" }));
  card.hass = next;
  assert.deepEqual(said(), ["Du brauchst 40"]);
  next = update(next, { ...visit(dart(20, 2)), ...alone({ remaining: 0, won: true, visit: ["D20"] }) });
  card.hass = next;
  assert.deepEqual(said(), ["Game shot, und das Leg!"]);
  tap(card);
  said();
});

test("the bull round of Halve-It counts both bull beds, on the board and in the call", () => {
  const halveIt = (keys) =>
    game({ game: "halve_it", round: 9, rounds: 9, target: "25", points: 40, scores: [{ player: 1, points: 40 }], visit: keys });
  const { hass, card } = setup(halveIt([]), { caller: true });
  assert.equal(text(card, ".main .route"), "Bull (25/50)");
  tap(card);
  said();
  card.hass = update(hass, { ...visit(dart(25, 1), dart(25, 2), dart(20, 1)), ...halveIt(["25", "BULL", "S20"]) });
  assert.deepEqual(said(), ["75"]);
  tap(card);
  said();
});

test("each kind of call can be switched off", () => {
  const options = { caller: true, call_scores: false, call_checkouts: false, call_results: false, call_sounds: false };
  const { hass, card } = setup(x01(100), options);
  tap(card);
  said();
  let next = update(hass, { ...visit(T20, T20, T20), ...x01(100, ["T20", "T20", "T20"], { bust: true }) });
  card.hass = next;
  next = update(next, { ...visit(), ...x01(40, [], { player: 2, checkout: "D20" }) });
  card.hass = next;
  card.hass = update(next, x01(0, ["D20"], { player: 2, won: true, winner: 2 }));
  assert.deepEqual(said(), []);

  const sounds = setup(x01(501), { caller: true, call_sounds: false });
  const before = contexts[0].tones.length;
  sounds.card.hass = update(sounds.hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  assert.deepEqual(said(), ["180"]);
  assert.equal(contexts[0].tones.length, before);
  tap(sounds.card);
  said();
});

test("the preview neither unlocks nor speaks", () => {
  const { hass, card } = setup(x01(501), { caller: true });
  card.preview = true;
  tap(card);
  assert.equal($(card, ".caller-toggle").getAttribute("aria-pressed"), "false");
  assert.deepEqual(spoken, []);

  // Unlocked by another card on the page, the preview still stays silent.
  const live = setup({}, { caller: true }).card;
  tap(live);
  said();
  card.hass = update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  assert.deepEqual(spoken, []);
  tap(live);
  said();
});

test("without speech synthesis the caller stays silent", (t) => {
  delete globalThis.SpeechSynthesisUtterance;
  delete window.speechSynthesis;
  t.after(() => {
    globalThis.SpeechSynthesisUtterance = Utterance;
    window.speechSynthesis = speech;
  });
  const { hass, card } = setup({}, { caller: true });
  tap(card);
  card.hass = update(hass, visit(dart(20, 1), dart(20, 1), dart(20, 1)));
  assert.equal($(card, ".caller-toggle").getAttribute("aria-pressed"), "true");
  window.speechSynthesis = speech;
  card.hass = update(hass, visit(dart(20, 1), dart(20, 1), dart(19, 1)));
  delete window.speechSynthesis;
  tap(card);
  assert.equal($(card, ".caller-toggle").getAttribute("aria-pressed"), "false");
  assert.deepEqual(spoken, []);
});

test("the status and the banner are written only when they change, and the player up is marked", () => {
  const { hass, card } = setup(game({ remaining: 81 }, "81"));
  const pill = $(card, ".pill");
  const text = pill.firstChild;
  // A status region that is rewritten with the same words is read out again.
  card.hass = update(hass, { "sensor.training_darts": "25" });
  assert.equal(pill.firstChild, text);
  card.hass = update(hass, { "switch.detection": "off" });
  assert.equal(pill.textContent, "Detection stopped");
  assert.equal($(card, ".main .player.active").getAttribute("aria-current"), "true");
  assert.equal($(card, ".main .player:not(.active)").getAttribute("aria-current"), null);
  card.hass = update(hass, game({ remaining: 0, won: true, winner: 1 }, "0"));
  const banner = $(card, ".banner").firstChild;
  card.hass = update(hass, { ...game({ remaining: 0, won: true, winner: 1 }, "0"), "sensor.training_darts": "26" });
  assert.equal($(card, ".banner").firstChild, banner);
});

test("the full-height scoreboard fits the screen, lays out a portrait tablet and keeps its contrast", () => {
  const style = $(setup({}, { full_height: true }).card, "style").textContent;
  const has = (pattern) => assert.match(style, pattern);
  // The screen below the header and above a phone's home indicator, not more; the new
  // game screen scrolls with the page.
  has(
    /--ad-taken: calc\(\s*var\(--header-height, 56px\) \+ var\(--safe-area-inset-top, env\(safe-area-inset-top, 0px\)\) \+\s*var\(--safe-area-inset-bottom, env\(safe-area-inset-bottom, 0px\)\) \+ 16px\s*\);\s*height: calc\(100vh - var\(--ad-taken\)\);\s*height: calc\(100dvh - var\(--ad-taken\)\);/
  );
  has(/\.scoreboard\.full\.choosing \{\s*height: auto;/);
  // Little room for the scores: a line per player; a phone on its side keeps the pad
  // beside them from the top to the bottom.
  has(/@container \(max-height: 200px\) \{\s*\.scoreboard\.full \.players \{ gap: 6px; \}/);
  has(/@media \(orientation: landscape\) and \(max-height: 440px\) \{\s*\.scoreboard\.full\.with-pad \{/);
  has(/grid-template-areas: "header pad" "banner pad" "main pad" "visit pad";/);
  has(/\.scoreboard\.full:not\(\.choosing\) \.main \{\s*flex: 1 1 0; container-type: size; overflow-y: auto; justify-content: safe center;/);
  // The numbers take the width and the height left; the pad sits beside the scores in landscape.
  has(/\.scoreboard\.full \.n2 \.big \{ font-size: clamp\(40px, min\(15cqi, 100cqh - 19cqi\), 240px\); \}/);
  has(/@media \(orientation: landscape\) \{\s*\.scoreboard\.full\.with-pad \{/);
  has(/@media \(orientation: portrait\) \{\s*\.scoreboard\.full \.players\.n2 \{ grid-template-columns: minmax\(0, 1fr\); \}/);
  // Sticky needs a card without a scroll container of its own.
  has(/ha-card \{ overflow: hidden; overflow: clip;/);
  has(/\.lobby-actions \{\s*--ad-card-fill: [^;]+;\s*grid-column: 1 \/ -1;\s*position: sticky;/);
  // The start bar covers what scrolls beneath it, also with a see-through card, and stays
  // above a phone's home indicator.
  has(/background: linear-gradient\(var\(--ad-card-fill\), var\(--ad-card-fill\)\), var\(--primary-background-color, #111\);/);
  has(/padding: 10px var\(--ad-pad\) calc\(10px \+ var\(--safe-area-inset-bottom, env\(safe-area-inset-bottom, 0px\)\)\);/);
  // Accent text and fills are darkened for contrast; pressed buttons show in High Contrast.
  has(/--ad-accent-text: color-mix\(in srgb, var\(--ad-accent\) 60%, var\(--primary-text-color, #212121\)\);/);
  has(/--ad-accent-fill: color-mix\(in srgb, var\(--ad-accent\) 70%, #000\);/);
  // A route's bed is a tag, framed and never filled like a button; the next one is tinted.
  has(/\.bed:first-child \{ font-weight: 800; background: color-mix\(in srgb, var\(--ad-accent\) 16%, transparent\); \}/);
  has(/@media \(forced-colors: active\) \{\s*\[aria-pressed="true"\], \[aria-checked="true"\] \{ outline: 3px solid Highlight;/);
  // The title keeps its words whole; the header's buttons follow below it where they must.
  has(/\.scoreboard > header \{ align-items: flex-start; flex-wrap: wrap; row-gap: 8px; \}/);
  has(/\.scoreboard \.title \{[^}]*overflow-wrap: break-word;\s*\}/);
  // Their row is never wider than the card: the new game button, the caller and the
  // status wrap in it on a phone instead of running over the edge.
  has(/\.scoreboard > header > \.header-actions \{ flex: 1 0 auto; max-width: 100%; \}/);
  has(/\.header-actions \{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: flex-end; \}/);
  // Every touch screen, also a large one beside a mouse, gets controls for a finger.
  has(/@media \(any-pointer: coarse\) \{ \.lobby-toggle, \.caller-toggle \{ min-height: 40px; \} \}/);
  assert.doesNotMatch(style, /\(pointer: coarse\)/);
  // The darts of the visit grow with their own tiles, also when narrow beside a pad.
  has(/\.visit \.dart \{ container-type: inline-size; \}/);
  has(/\.dart \.segment \{ font-size: clamp\(16px, 24cqi, 48px\);/);
  assert.doesNotMatch(style, /opacity: \.85/);
});

test("a bull-off dart that missed the board reads as a miss", () => {
  const { card } = setup(
    game({
      remaining: 501,
      bull_off: { player: 2, throws: [{ player: 1, name: "Alex", hit: "MISS" }, { player: 2, name: "Sam" }] },
    })
  );
  assert.deepEqual(
    $$(card, ".main .player .big").map((big) => big.textContent),
    ["Miss", "–"]
  );
});
