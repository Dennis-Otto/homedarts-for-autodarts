// The new games on the scoreboard and the live card in a browser DOM: a team
// match, start scores of their own, Tactics, Golf and a new training game.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, READY, loadCards, makeHass, mount, text, update, window } from "./dom.mjs";

const { bedPath } = await loadCards();

const practice = (state, attributes) => ({ "sensor.practice_remaining": { state, attributes } });
const drill = (state, attributes) => ({ "sensor.practice_target": { state, attributes } });
const setup = (type, states = {}, config = {}, options = {}) => {
  const hass = makeHass({ states: { ...READY, ...states }, ...options });
  return { hass, card: mount(type, hass, config) };
};
const TEAMS = [
  { team: 1, name: "Alex & Kim", players: [1, 3] },
  { team: 2, name: "Sam & Lea", players: [2, 4] },
];
const teamMatch = (remaining, attributes = {}) =>
  practice(String(remaining[0]), {
    game: 501,
    player: 3,
    name: "Kim",
    checkout: "T20 D20",
    legs_to_win: 2,
    teams: TEAMS,
    scores: ["Alex", "Sam", "Kim", "Lea"].map((name, index) => ({
      player: index + 1,
      name,
      remaining: remaining[index % 2],
      start: 501,
      team: (index % 2) + 1,
      legs: 1 - (index % 2),
      sets: 0,
      average: 50 + index,
    })),
    ...attributes,
  });

test("the scoreboard shows two team tiles with the partner at the board", () => {
  const { hass, card } = setup("homedarts-scoreboard-card", teamMatch([100, 301]));
  const tiles = $$(card, ".main .player");
  assert.deepEqual(
    tiles.map((tile) => [tile.className, tile.querySelector(".name").textContent, tile.querySelector(".big").textContent]),
    [
      ["player active", "Alex & Kim", "100"],
      ["player", "Sam & Lea", "301"],
    ]
  );
  assert.equal(text(card, ".player.active .members b"), "Kim Ø 52.0");
  assert.equal(text(card, ".player.active .route"), "T20D20");
  assert.equal(text(card, ".meta"), "2 legs to win a set");
  // A won match keeps the legs of the deciding set; a team counts once in the result.
  const scores = teamMatch([0, 301])["sensor.practice_remaining"].attributes.scores.map((score) => ({
    ...score,
    legs: score.team === 1 ? 2 : 1,
  }));
  card.hass = update(hass, teamMatch([0, 301], { player: 1, winner: 1, scores }));
  assert.equal(text(card, ".banner"), "Alex & Kim win the match 2 : 1!");
  assert.equal($(card, ".banner").hidden, false);
});

test("the live card lists the teams and whose turn it is", () => {
  const { card } = setup("homedarts-card", teamMatch([100, 301]));
  assert.equal(text(card, ".practice-meta"), "Kim to throw");
  assert.equal(text(card, ".practice-remaining"), "100");
  assert.deepEqual(
    $$(card, ".player-score").map((row) => [row.className, row.querySelector(".who").textContent]),
    [
      ["player-score active", "Alex & Kim"],
      ["player-score", "Sam & Lea"],
    ]
  );
});

test("start scores of their own show on both cards", () => {
  const states = practice("501", {
    game: 501,
    player: 1,
    name: "Alex",
    scores: [
      { player: 1, name: "Alex", remaining: 501, start: 501, legs: 0, sets: 0 },
      { player: 2, name: "Sam", remaining: 301, start: 301, legs: 0, sets: 0 },
    ],
  });
  const scoreboard = setup("homedarts-scoreboard-card", states).card;
  assert.deepEqual(
    $$(scoreboard, ".main .player .badge").map((badge) => badge.textContent),
    ["501", "301"]
  );
  const live = setup("homedarts-card", states).card;
  assert.deepEqual(
    $$(live, ".player-score .badge").map((badge) => badge.textContent),
    ["501", "301"]
  );
});

test("Tactics fills the chalkboard with the numbers down to 10, in German too", () => {
  const numbers = [20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 25];
  const states = practice("unknown", {
    game: "tactics",
    player: 1,
    target: "T12",
    numbers,
    scores: [
      { player: 1, name: "Alex", marks: [3, 3, 3, 3, 3, 3, 3, 3, 0, 0, 0, 0], points: 40, mpr: 2.4 },
      { player: 2, name: "Sam", marks: [3, 3, 3, 3, 3, 3, 3, 3, 0, 0, 0, 0], points: 0, mpr: 1.8 },
    ],
  });
  const { card } = setup("homedarts-scoreboard-card", states, {}, { language: "de" });
  assert.equal(text(card, ".title"), "Tactics");
  assert.equal($$(card, ".main table.cricket.many tbody tr").length, 14);
  assert.deepEqual(
    $$(card, ".main table.cricket tbody tr").slice(7, 9).map((row) => [row.className, row.children[0].textContent]),
    [
      ["closed", "13"],
      ["target", "12"],
    ]
  );
  const live = setup("homedarts-card", states).card;
  assert.equal(text(live, ".practice-title"), "Tactics");
  assert.deepEqual(
    $$(live, ".aim path").map((path) => path.getAttribute("d")),
    [bedPath("T12")]
  );
  const cut = setup("homedarts-scoreboard-card", practice("unknown", { game: "cut_throat", scores: [] })).card;
  assert.equal(text(cut, ".title"), "Cut-Throat Cricket");
  assert.equal(text(cut, ".meta"), "Fewest points win");
});

test("a dart that counted nothing in Cricket is struck through on both cards", () => {
  const throws = [
    { number: 20, multiplier: 3, segment: "x", dart: 1 },
    { number: 14, multiplier: 1, segment: "x", dart: 2 },
  ];
  const states = {
    ...practice("unknown", {
      game: "cricket",
      player: 1,
      target: "T19",
      visit: ["T20", "S14"],
      counted: ["20", null],
      scores: [
        { player: 1, name: "Alex", marks: [3, 0, 0, 0, 0, 0, 0], points: 0 },
        { player: 2, name: "Sam", marks: [0, 0, 0, 0, 0, 0, 0], points: 0 },
      ],
    }),
    "sensor.local_visit_score": { state: "74", attributes: { throws, recent_visits: [] } },
  };
  const board = setup("homedarts-scoreboard-card", states).card;
  assert.deepEqual(
    $$(board, ".visit .dart:not(.empty)").map((dart) => [dart.className, dart.getAttribute("title")]),
    [
      ["dart tappable", null],
      ["dart dead tappable", "Counted nothing"],
    ]
  );
  assert.match($$(board, ".visit .dart")[1].getAttribute("aria-label"), /^S14 14 – Counted nothing – Correct dart 2$/);
  assert.equal($(board, ".main td.aim-score").getAttribute("title"), "Scores here: another player still has it open");
  const live = setup("homedarts-card", states).card;
  assert.deepEqual(
    $$(live, ".slot").map((slot) => [slot.className, slot.getAttribute("title")]),
    [
      ["slot triple tappable", null],
      ["slot single latest dead tappable", "Counted nothing"],
      ["slot empty", null],
    ]
  );
  // Without corrections, the darts are no buttons and keep the hint.
  const still = setup("homedarts-card", states, { corrections: false }).card;
  assert.equal($$(still, ".slot")[1].tagName, "DIV");
  assert.equal($$(still, ".slot")[1].getAttribute("title"), "Counted nothing");
  const plain = setup("homedarts-scoreboard-card", states, { corrections: false }).card;
  assert.equal($$(plain, ".visit .dart")[1].tagName, "DIV");
  assert.equal($$(plain, ".visit .dart")[1].getAttribute("title"), "Counted nothing");
});

test("Golf shows the scorecard and outlines the hole", () => {
  const golf = (attributes) =>
    practice("unknown", {
      game: "golf",
      player: 1,
      name: "Alex",
      round: 4,
      rounds: 9,
      target: "4",
      scores: [
        { player: 1, name: "Alex", points: 11, scorecard: [3, 4, 4] },
        { player: 2, name: "Sam", points: 13, scorecard: [5, 4, 4] },
      ],
      ...attributes,
    });
  const { hass, card } = setup("homedarts-scoreboard-card", golf({}));
  assert.equal(text(card, ".title"), "Golf");
  assert.equal(text(card, ".meta"), "Hole 4/9 · The last dart counts – pull your darts to stop");
  assert.deepEqual(
    $$(card, ".scorecard thead th").map((cell) => cell.textContent),
    ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "Total"]
  );
  assert.deepEqual(
    $$(card, ".scorecard tbody tr").map((row) => [row.className, row.textContent]),
    [
      ["active", "Alex34411"],
      ["", "Sam54413"],
    ]
  );
  card.hass = update(hass, golf({ round: 10, target: "10", playoff: [1, 2] }));
  assert.equal(text(card, ".meta"), "Play-off · Hole 10 · The last dart counts – pull your darts to stop");
  const live = setup("homedarts-card", golf({})).card;
  assert.equal(text(live, ".practice-meta"), "Hole 4/9 · Alex to throw");
  assert.deepEqual(
    $$(live, ".aim path").map((path) => path.getAttribute("d")),
    ["SI4", "SO4", "T4", "D4"].map(bedPath)
  );
});

test("the 121 checkout shows the route and calls what the next attempt requires", () => {
  const spoken = [];
  const speech = { speak: (utterance) => spoken.push(utterance.text), cancel: () => {} };
  window.speechSynthesis = speech;
  globalThis.SpeechSynthesisUtterance = class {
    constructor(words) {
      this.text = words;
    }
  };
  const ladder = (state, attributes) =>
    drill(state, {
      drill: "checkout_121",
      attempt_visit: 1,
      attempt_visits: 3,
      attempts: 0,
      successes: 0,
      visit: [],
      ...attributes,
    });
  const { hass, card } = setup(
    "homedarts-scoreboard-card",
    { ...ladder("121", { remaining: 121, checkout: "T20 T11 D14" }), ...practice("unknown", { game: null }) },
    { caller: true }
  );
  $(card, ".caller-toggle").click();
  spoken.splice(0);
  assert.equal(text(card, ".title"), "121 checkout");
  assert.equal(text(card, ".main .big"), "121");
  assert.equal(text(card, ".main .route"), "T20T11D14");
  let next = update(hass, ladder("121", { remaining: 61, checkout: "T11 D14", visit: ["T20"] }));
  card.hass = next;
  next = update(next, ladder("122", { remaining: 122, checkout: "T20 T14 D10", attempts: 1, successes: 1, best: 121 }));
  card.hass = next;
  assert.deepEqual(spoken, ["You require 122"]);
  assert.deepEqual(
    $$(card, ".main .facts span").map((fact) => fact.textContent),
    ["Visit 1 / 3", "1 / 1 checked out", "– % ", "Best 121"]
  );
  $(card, ".caller-toggle").click();
  delete window.speechSynthesis;
  delete globalThis.SpeechSynthesisUtterance;
});

test("the scoreboard and the live card show the setup of a checkout training without a route", () => {
  const states = {
    ...drill("159", {
      drill: "checkout_121",
      remaining: 159,
      checkout: null,
      setup: { route: "T20 T19 S10", leave: 32 },
      attempt_visit: 1,
      attempt_visits: 3,
      attempts: 2,
      successes: 1,
      visit: [],
    }),
    ...practice("unknown", { game: null }),
  };
  const scoreboard = setup("homedarts-scoreboard-card", states).card;
  assert.equal(text(scoreboard, ".main .big"), "159");
  assert.equal(text(scoreboard, ".main .route"), "T20T19S10leaves 32");
  assert.equal(
    $(scoreboard, ".main .route .setup").getAttribute("title"),
    "No checkout with the darts left: set up the next visit"
  );
  const live = setup("homedarts-card", states).card;
  assert.equal(text(live, ".practice-route"), "T20T19S10leaves 32");
});
