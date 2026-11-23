// The practice game in the live card and the dashboard strategy.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  bullOffView,
  cricketView,
  dashboardStrategy,
  partyView,
  practiceView,
} from "../../custom_components/homedarts/frontend/homedarts-card.js";

test("the practice view reads the remaining score sensor", () => {
  assert.equal(practiceView(undefined), null);
  assert.equal(practiceView({ state: "unknown", attributes: {} }), null);
  assert.equal(practiceView({ state: "12.5", attributes: {} }), null);
  assert.deepEqual(
    practiceView({
      state: "121",
      attributes: { game: 501, checkout: "T20 25 D18", bust: false, won: false, darts: 9, average: 126.67 },
    }),
    {
      game: 501,
      remaining: 121,
      from: 121,
      visitFrom: null,
      teams: [],
      route: ["T20", "25", "D18"],
      bust: false,
      won: false,
      darts: 9,
      average: 126.67,
      player: 1,
      name: null,
      winner: null,
      legsToWin: 1,
      setsToWin: 1,
      opened: true,
      inMode: "straight",
      outMode: "double",
      bullMode: "25_50",
      maxRounds: 0,
      round: null,
      limit: null,
      visit: [],
      scores: [],
    }
  );
  const bust = practiceView({
    state: "32",
    attributes: { checkout: "<b> D16", bust: true, darts: "x", double_out: false, visit: ["T20", 5, null, "S1"] },
  });
  assert.deepEqual(
    [bust.route, bust.bust, bust.darts, bust.average, bust.game, bust.outMode, bust.visit],
    [["D16"], true, 0, null, null, "straight", ["T20", "S1"]]
  );
  // The X01 rules, and the leg the round limit decided last; double in from before the modes.
  const ruled = practiceView({
    state: "132",
    attributes: {
      in_mode: "master",
      out_mode: "master",
      bull_mode: "50_50",
      max_rounds: 10,
      round: 3,
      legs: [{ rounds: 10, ended: "2026-10-14T20:00:00", name: "Alex" }, { rounds: 9 }],
    },
  });
  assert.deepEqual(
    [ruled.inMode, ruled.outMode, ruled.bullMode, ruled.maxRounds, ruled.round, ruled.limit],
    ["master", "master", "50_50", 10, 3, { ended: "2026-10-14T20:00:00", name: "Alex" }]
  );
  const older = practiceView({ state: "40", attributes: { double_in: true, out_mode: "triple", legs: [{ checkout: 40 }] } });
  assert.deepEqual([older.inMode, older.outMode, older.limit], ["double", "double", null]);
  assert.deepEqual(practiceView({ state: "0", attributes: { won: true, checkout: null } }).route, []);
});

test("game views fill in what a sensor leaves out", () => {
  assert.deepEqual(
    [practiceView({ state: "40" })].map((view) => [view.game, view.player, view.legsToWin, view.scores]),
    [[null, 1, 1, []]]
  );
  const cricket = cricketView({
    state: "unknown",
    attributes: { game: "cricket", scores: [{ player: 1, marks: [0, 0, 0, 0, 0, 0, 0] }] },
  });
  assert.deepEqual([cricket.scores[0].points, cricket.scores[0].legs, cricket.player], [0, 0, 1]);
  const party = partyView({ state: "unknown", attributes: { game: "shanghai", scores: "none" } });
  assert.deepEqual([party.scores, party.player, party.round, party.phase], [[], 1, null, "play"]);
  assert.deepEqual(bullOffView({ state: "501", attributes: { bull_off: { player: "first", throws: null } } }), {
    player: 1,
    name: null,
    rethrow: false,
    byDistance: false,
    throws: [],
  });
});

test("a match brings every player's score", () => {
  const view = practiceView({
    state: "281",
    attributes: {
      game: 301,
      player: 2,
      name: "",
      winner: null,
      legs_to_win: 3,
      sets_to_win: 1,
      scores: [
        { player: 1, name: "Dennis", remaining: 121, legs: 1, sets: 0, average: 90 },
        { player: 2, name: null, remaining: 281, legs: "x", sets: 0, average: null },
        { player: "3", remaining: 1 },
        null,
      ],
    },
  });
  assert.equal(view.player, 2);
  assert.equal(view.name, null);
  assert.equal(view.legsToWin, 3);
  assert.deepEqual(view.scores, [
    { player: 1, name: "Dennis", remaining: 121, start: null, team: null, legs: 1, sets: 0, average: 90 },
    { player: 2, name: null, remaining: 281, start: null, team: null, legs: 0, sets: 0, average: null },
  ]);
});

test("the game settings offer the practice controls and player names, the live view the card alone", () => {
  const entity = (entity_id, translation_key) => ({ entity_id, translation_key, device_id: "dev", platform: "homedarts" });
  const entities = [
    entity("select.board_practice_game", "practice_game"),
    entity("number.board_players", "practice_players"),
    entity("number.board_legs", "practice_legs"),
    entity("number.board_sets", "practice_sets"),
    entity("button.board_new_leg", "practice_new_leg"),
    entity("button.board_new_match", "practice_new_match"),
    entity("select.board_out_mode", "practice_out_mode"),
    entity("switch.board_double_out", "practice_double_out"),
    entity("text.board_player_1", "practice_player"),
    entity("text.board_player_2", "practice_player"),
  ];
  const hass = {
    locale: { language: "de" },
    entities: Object.fromEntries(entities.map((item) => [item.entity_id, item])),
    devices: { dev: { id: "dev" } },
    states: {},
  };
  const views = dashboardStrategy(hass).views;
  assert.deepEqual(views.map((view) => [view.path, view.title, view.icon]), [
    ["live", "Live", "mdi:bullseye-arrow"],
    ["scoreboard", "Anzeigetafel", "mdi:scoreboard-outline"],
    ["training", "Training", "mdi:chart-box-outline"],
    ["games", "Spieleinstellungen", "mdi:tune-variant"],
    ["board", "Board", "mdi:heart-pulse"],
    ["overlay", "Stream-Overlay", "mdi:video-outline"],
  ]);
  assert.deepEqual(views[0].sections, [
    { type: "grid", column_span: 2, cards: [{ type: "custom:homedarts-card", device_id: "dev", grid_options: { columns: "full" } }] },
  ]);
  assert.deepEqual(views[3].sections[0].cards, [
    { type: "heading", heading: "Übungsspiel" },
    {
      type: "entities",
      entities: [
        "select.board_practice_game",
        "number.board_players",
        "number.board_legs",
        "number.board_sets",
        "select.board_out_mode",
        "button.board_new_leg",
        "button.board_new_match",
      ],
    },
    { type: "entities", title: "Spielernamen", entities: ["text.board_player_1", "text.board_player_2"] },
  ]);
});

test("training games show their target, progress and beds to aim at", async () => {
  const { drillView, drillBeds } = await import("../../custom_components/homedarts/frontend/homedarts-card.js");
  assert.equal(drillView(undefined), null);
  assert.equal(drillView({ state: "7", attributes: { drill: "golf" } }), null);
  const clock = drillView({
    state: "7",
    attributes: { drill: "around_the_clock", progress: 6, targets: 21, darts: 9, hit_rate: 66.7, finished: false },
  });
  assert.deepEqual([clock.target, clock.progress, clock.darts, clock.hitRate], ["7", 6, 9, 66.7]);
  assert.deepEqual(drillBeds(clock), ["SI7", "SO7", "T7", "D7"]);
  // The bull of Around the Clock is 25: both bull beds count.
  assert.deepEqual(drillBeds({ ...clock, target: "25" }), ["Bull", "25"]);
  assert.deepEqual(drillBeds({ ...clock, target: "BULL" }), ["Bull"]);
  const doubles = drillView({ state: "D16", attributes: { drill: "doubles" } });
  assert.deepEqual(drillBeds(doubles), ["D16"]);
  const done = drillView({
    state: "unknown",
    attributes: { drill: "bobs_27", finished: true, score: 77, results: [{ completed: true }] },
  });
  assert.deepEqual([done.target, done.finished, done.completed, done.score], [null, true, true, 77]);
  assert.deepEqual(drillBeds(done), []);
  const checkout = drillView({
    state: "81",
    attributes: { drill: "checkout", remaining: 81, checkout: "T15 D18", attempt_visit: 2, attempts: 4, successes: 1, rate: 25 },
  });
  assert.deepEqual([checkout.remaining, checkout.visit, checkout.rate], [81, 2, 25]);
  assert.deepEqual(drillBeds(checkout), ["T15"]);
});

test("the training view charts practice legs per day and the practice trend", () => {
  const entity = (entity_id, translation_key) => ({ entity_id, translation_key, device_id: "dev", platform: "homedarts" });
  const entities = [
    entity("sensor.board_darts", "training_darts"),
    entity("sensor.board_practice_legs", "practice_legs_played"),
    entity("sensor.board_first_nine", "practice_first_9_average"),
    entity("sensor.board_checkout_rate", "practice_checkout_rate"),
  ];
  const hass = {
    locale: { language: "en" },
    entities: Object.fromEntries(entities.map((item) => [item.entity_id, item])),
    devices: { dev: { id: "dev" } },
    states: {},
  };
  const training = dashboardStrategy(hass).views.find((view) => view.path === "training");
  const [darts, legs, trend] = training.sections[1].cards;
  assert.deepEqual(darts.entities, ["sensor.board_darts"]);
  assert.deepEqual([legs.title, legs.entities, legs.stat_types], [
    "Practice legs per day",
    ["sensor.board_practice_legs"],
    ["change"],
  ]);
  assert.deepEqual(trend.entities, ["sensor.board_first_nine", "sensor.board_checkout_rate"]);
  // The doubles rate joins the trend once the integration has it.
  entities.push(entity("sensor.board_doubles_rate", "practice_doubles_rate"));
  hass.entities = Object.fromEntries(entities.map((item) => [item.entity_id, item]));
  const next = dashboardStrategy(hass).views.find((view) => view.path === "training").sections[1].cards[2];
  assert.equal(next.title, "First 9, checkout and doubles rate");
  assert.deepEqual(next.entities, ["sensor.board_first_nine", "sensor.board_checkout_rate", "sensor.board_doubles_rate"]);
});

test("cricket shows every player's marks, the points and the bed to aim at", async () => {
  const { cricketView, cricketBeds } = await import("../../custom_components/homedarts/frontend/homedarts-card.js");
  assert.equal(cricketView(undefined), null);
  assert.equal(cricketView({ state: "301", attributes: { game: 301 } }), null);
  assert.equal(cricketView({ state: "unavailable", attributes: { game: "cricket" } }), null);
  const view = cricketView({
    state: "unknown",
    attributes: {
      game: "cricket",
      player: 2,
      name: "Lea",
      target: "T19",
      darts: 6,
      points: 0,
      mpr: 1.5,
      legs_to_win: 2,
      numbers: [20, 19, 18, 17, 16, 15, 25],
      scores: [
        { player: 1, name: "Dennis", marks: [3, 1, 0, 0, 0, 0, 2], points: 60, legs: 1, sets: 0, mpr: 3.5 },
        { player: 2, name: null, marks: [3, 9, -1, "x", 0, 0, 0], points: 0, legs: 0, sets: 0, mpr: 1.5 },
        { player: 3, marks: [1, 2] },
        null,
      ],
    },
  });
  assert.deepEqual([view.player, view.name, view.target, view.legsToWin, view.winner], [2, "Lea", "T19", 2, null]);
  assert.deepEqual(
    view.scores.map((score) => [score.name, score.marks, score.points]),
    [
      ["Dennis", [3, 1, 0, 0, 0, 0, 2], 60],
      [null, [3, 3, 0, 0, 0, 0, 0], 0],
    ]
  );
  assert.deepEqual(cricketBeds(view), ["T19"]);
  assert.deepEqual(cricketBeds({ ...view, target: "BULL" }), ["Bull", "25"]);
  assert.deepEqual(cricketBeds({ ...view, won: true }), []);
  assert.deepEqual(cricketBeds({ ...view, winner: 1 }), []);
  const odd = cricketView({ state: "unknown", attributes: { game: "cricket", target: "<b>", numbers: [1, "x"] } });
  assert.deepEqual([odd.target, odd.numbers, odd.scores, odd.mpr], [null, [20, 19, 18, 17, 16, 15, 25], [], null]);
});

test("party games show points, lives and the beds of their target", async () => {
  const { partyView, partyBeds, bullOffView } = await import(
    "../../custom_components/homedarts/frontend/homedarts-card.js"
  );
  assert.equal(partyView({ state: "unknown", attributes: { game: "cricket" } }), null);
  const shanghai = partyView({
    state: "unknown",
    attributes: { game: "shanghai", round: 3, rounds: 7, target: "3", points: 9, player: 1, scores: [{ player: 1, points: 9 }] },
  });
  assert.deepEqual([shanghai.kind, shanghai.round, shanghai.rounds, shanghai.points], ["shanghai", 3, 7, 9]);
  assert.deepEqual(partyBeds(shanghai), ["SI3", "SO3", "T3", "D3"]);
  const halve = (target) => partyBeds({ ...shanghai, kind: "halve_it", target });
  assert.equal(halve("D").length, 21);
  assert.equal(halve("T").length, 20);
  assert.deepEqual(halve("25"), ["Bull", "25"]);
  assert.deepEqual(halve("BULL"), ["Bull", "25"]);
  assert.deepEqual(partyBeds({ ...shanghai, won: true }), []);
  const killer = partyView({
    state: "unknown",
    attributes: {
      game: "killer",
      phase: "play",
      player: 1,
      target: null,
      scores: [
        { player: 1, number: 7, lives: 3, killer: true },
        { player: 2, number: 12, lives: 0, killer: false },
        { player: 3, number: 3, lives: 2, killer: false },
        { player: "x" },
      ],
    },
  });
  // A killer aims at the doubles of the players still in the game.
  assert.deepEqual(partyBeds(killer), ["D3"]);
  assert.deepEqual(partyBeds({ ...killer, target: "D7" }), ["D7"]);
  assert.deepEqual(partyBeds({ ...killer, phase: "choose" }), []);
  assert.deepEqual(partyBeds({ ...killer, needsPlayers: 2 }), []);
  assert.equal(killer.scores.length, 3);
  assert.equal(bullOffView({ state: "301", attributes: { bull_off: null } }), null);
  const bullOff = bullOffView({
    state: "301",
    attributes: {
      bull_off: {
        player: 2,
        name: "Sam",
        rethrow: true,
        by_distance: true,
        throws: [{ player: 1, hit: "S20", distance: 11 }, { player: 2, hit: null, distance: null }, "x"],
      },
    },
  });
  assert.deepEqual(bullOff, {
    player: 2,
    name: "Sam",
    rethrow: true,
    byDistance: true,
    throws: [
      { player: 1, name: null, hit: "S20", distance: 11 },
      { player: 2, name: null, hit: null, distance: null },
    ],
  });
});
