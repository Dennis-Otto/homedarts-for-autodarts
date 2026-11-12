// The players card: profiles, head-to-head records and recent matches.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  dashboardStrategy,
  playersHtml,
  playersView,
} from "../../custom_components/homedarts/frontend/homedarts-card.js";

const profiles = {
  state: "2",
  attributes: {
    players: [
      {
        name: "Alex",
        legs_played: 20,
        legs_won: 12,
        matches_played: 5,
        matches_won: 3,
        average: 61.25,
        first_9_average: 70.1,
        checkout_rate: 31.3,
        mpr: 2.4,
        best_mpr: 3.1,
        highest_visit: 140,
        highest_checkout: 121,
        fewest_darts: { 501: 18, 301: 12, x: 3 },
      },
      { name: "Lea", legs_played: 8, legs_won: 3, average: null, fewest_darts: null },
      { name: "", legs_played: 1 },
      null,
    ],
  },
};
const lastMatch = {
  state: "2026-09-26T20:00:00+00:00",
  attributes: {
    head_to_head: [{ players: ["Alex", "Lea"], wins: [3, 1] }, { players: ["A"], wins: [1] }],
    // As the integration keeps a match: Killer, first to two legs.
    matches: [
      {
        ended: "2026-09-26T20:00:00+00:00",
        game: "killer",
        legs_to_win: 2,
        sets_to_win: 1,
        winner: 2,
        players: [
          { name: "Alex", legs: 1, sets: 0, match_legs: 1, points: 0 },
          { name: null, legs: 2, sets: 1, match_legs: 2, points: 0 },
        ],
      },
      { ended: 5, players: [] },
    ],
  },
};
const ui = {
  t: (key) => ({ best_leg: "Best {game}", unit_darts: "{value} darts" })[key] ?? key,
  format: (value, digits) => value.toFixed(digits),
  percent: (value, digits) => (value === null ? "–" : `${value.toFixed(digits)}%`),
  date: () => "26.09., 22:00",
};

test("the players view keeps valid profiles, records and matches", () => {
  const view = playersView(profiles, lastMatch);
  assert.deepEqual(
    view.players.map((player) => player.name),
    ["Alex", "Lea"]
  );
  assert.deepEqual(view.players[0].fewestDarts, [
    { game: 301, darts: 12 },
    { game: 501, darts: 18 },
  ]);
  assert.equal(view.players[1].average, null);
  assert.equal(view.headToHead.length, 1);
  assert.equal(view.matches.length, 1);
  assert.deepEqual([view.matches[0].legsToWin, view.matches[0].setsToWin], [2, 1]);
  assert.deepEqual(playersView(undefined, undefined), { players: [], headToHead: [], matches: [] });
});

test("a profile without statistics counts no legs and no matches yet", () => {
  const [player] = playersView({ attributes: { players: [{ name: "Kim" }] } }, undefined).players;
  assert.deepEqual(
    [player.legsPlayed, player.legsWon, player.matchesPlayed, player.matchesWon, player.average, player.fewestDarts],
    [0, 0, 0, 0, null, []]
  );
});

test("the players card shows statistics, the balance and who won", () => {
  const html = playersHtml(playersView(profiles, lastMatch), ui);
  assert.match(html.players, /<div class="profile-name"><span>Alex<\/span><\/div><div class="muted">profile_legs 12\/20 · profile_matches 3\/5<\/div>/);
  assert.match(html.players, /<dt>average<\/dt><dd>61\.3<\/dd>/);
  assert.match(html.players, /<dt>checkout_short<\/dt><dd>31\.3%<\/dd>/);
  assert.match(html.players, /<dt>cricket_mpr<\/dt><dd>2\.40<\/dd><dt>best_mpr<\/dt><dd>3\.10<\/dd>/);
  assert.match(html.players, /<dt>Best 301<\/dt><dd>12 darts<\/dd><dt>Best 501<\/dt>/);
  // Lea never played Cricket: no MPR rows, and missing numbers read as dashes.
  assert.doesNotMatch(html.players.split("Lea")[1], /mpr/);
  assert.match(html.players.split("Lea")[1], /<dt>checkout_short<\/dt><dd>–<\/dd>/);
  assert.match(html.players.split("Lea")[1], /<dt>average<\/dt><dd>–<\/dd>/);
  assert.match(html.headToHead, /<span class="tally">3 : 1<\/span>.*<i style="width:75%">/);
  assert.match(html.matches, /<span class="game">party_killer<\/span><span><span>Alex 1<\/span> · <b>score_player 2 2<\/b><\/span>/);
});

test("the dashboard gets a players view once a player has a profile", () => {
  const entity = (entity_id, translation_key) => ({ entity_id, translation_key, device_id: "dev1", platform: "homedarts" });
  const hass = (items, states = {}) => ({
    locale: { language: "en" },
    entities: Object.fromEntries(items.map((item) => [item.entity_id, item])),
    devices: { dev1: { id: "dev1" } },
    states,
  });
  const without = dashboardStrategy(hass([entity("sensor.b_darts", "training_darts")]));
  assert.equal(without.views.some((view) => view.path === "players"), false);
  const entities = [entity("sensor.b_darts", "training_darts"), entity("sensor.b_profiles", "player_profiles")];
  // The sensor exists on every board; the view waits for the first profile.
  for (const profiles of [undefined, { state: "0", attributes: { players: [] } }, { state: "1", attributes: {} }]) {
    const empty = dashboardStrategy(hass(entities, profiles ? { "sensor.b_profiles": profiles } : {}));
    assert.equal(empty.views.some((view) => view.path === "players"), false);
  }
  const withProfiles = dashboardStrategy(
    hass(entities, { "sensor.b_profiles": { state: "1", attributes: { players: [{ name: "Alex" }] } } })
  );
  const players = withProfiles.views.find((view) => view.path === "players");
  assert.equal(players.title, "Players");
  assert.equal(players.sections[0].cards[0].type, "custom:homedarts-players-card");
});

// A match of the history that keeps its summary, and the numbers the integration answers.
const kept = (ended, extra = {}) => ({
  ended,
  game: 501,
  legs_to_win: 2,
  sets_to_win: 1,
  winner: 1,
  details: true,
  players: [
    { name: "Alex", legs: 2, sets: 1 },
    { name: "Lea", legs: 1, sets: 0 },
  ],
  ...extra,
});
const NUMBERS = {
  double_out: true,
  players: [
    { player: 1, name: "Alex", legs: 2, sets: 1, darts: 45, average: 66.8, checkouts: 2, darts_at_double: 5, checkout_rate: 40 },
    { player: 2, name: "Lea", legs: 1, sets: 0, darts: 42, average: 59.1, checkouts: 1, darts_at_double: 6, checkout_rate: 16.7 },
  ],
};
const summaryUi = { ...ui, format: (value, digits = 0) => value.toFixed(digits) };
const historyView = (...matches) => playersView(undefined, { attributes: { matches } });

test("a match whose summary the history keeps is a button that opens it", () => {
  const view = historyView(kept("a"), { ...kept("b"), details: "yes" });
  assert.deepEqual(
    view.matches.map((match) => match.details),
    [true, false]
  );
  const closed = playersHtml(view, summaryUi).matches;
  assert.match(closed, /^<button type="button" class="match" data-match="a" data-focus="match:a" aria-expanded="false">/);
  assert.match(closed, /<\/button><div class="match">/);
  assert.doesNotMatch(closed, /match-summary/);
  // Opened, it says that it loads until the integration answers, then shows the table.
  const open = (answer) =>
    playersHtml(view, { ...summaryUi, matches: { open: new Set(["a"]), summaries: new Map(answer ? [[`a\nAlex\nLea`, answer]] : []) } })
      .matches;
  assert.match(open(), /aria-expanded="true">.*<\/button><div class="match-summary"><p class="muted">match_summary_loading<\/p><\/div>/);
  assert.match(open({ state: "loading" }), /match_summary_loading/);
  const table = open({ state: "loaded", numbers: NUMBERS });
  assert.match(table, /<div class="match-summary"><table class="summary">/);
  assert.match(table, /<tr class="result"><th>score_legs<\/th><td class="winner">2<\/td><td class="">1<\/td><\/tr>/);
  assert.match(table, /<th>average<\/th><td class="winner">66\.8<\/td><td class="">59\.1<\/td>/);
  assert.match(table, /<th>summary_checkout<\/th><td class="winner">40\.0% \(2\/5\)<\/td>/);
  // A failed answer, or one without the numbers of two players, says so.
  for (const answer of [{ state: "failed" }, { state: "loaded", numbers: { players: [NUMBERS.players[0]] } }]) {
    assert.match(open(answer), /<p class="muted" role="alert">match_summary_failed<\/p>/);
  }
});

test("in the summary of a team match both partners of the winning team won", () => {
  const four = [...NUMBERS.players, ...NUMBERS.players.map((player) => ({ ...player, player: player.player + 2, name: `${player.name} 2` }))];
  const match = kept("t", {
    winners: [1, 3],
    players: [{ name: "Alex" }, { name: "Lea" }, { name: "Alex 2" }, { name: "Lea 2" }],
  });
  const html = playersHtml(historyView(match), {
    ...summaryUi,
    matches: {
      open: new Set(["t"]),
      summaries: new Map([["t\nAlex\nLea\nAlex 2\nLea 2", { state: "loaded", numbers: { players: four } }]]),
    },
  }).matches;
  const result = html.match(/<tr class="result">(.*?)<\/tr>/)[1];
  assert.deepEqual(
    [...result.matchAll(/<td class="(\w*)">/g)].map((cell) => cell[1]),
    ["winner", "", "winner", ""]
  );
  // An unnamed seat keys its summary without a name.
  const unnamed = historyView(kept("u", { players: [{ name: "Alex" }, { name: null }] }));
  const shown = playersHtml(unnamed, {
    ...summaryUi,
    matches: { open: new Set(["u"]), summaries: new Map([["u\nAlex\n", { state: "loaded", numbers: NUMBERS }]]) },
  }).matches;
  assert.match(shown, /<table class="summary">/);
});

test("the card lists the latest ten matches and all of them on request", () => {
  const view = historyView(...Array.from({ length: 12 }, (_, index) => ({ ...kept(`m${index}`), details: index % 2 === 0 })));
  const ten = playersHtml(view, summaryUi).matches;
  assert.equal([...ten.matchAll(/class="match"/g)].length, 10);
  assert.match(
    ten,
    /<button type="button" class="link more-matches" data-more-matches data-focus="matches:more" aria-expanded="false">matches_all<svg/
  );
  const all = playersHtml(view, { ...summaryUi, t: (key) => (key === "matches_all" ? "All {count}" : key), matches: { all: true } }).matches;
  assert.equal([...all.matchAll(/class="match"/g)].length, 12);
  assert.match(all, /aria-expanded="true">matches_fewer<svg/);
  const counted = playersHtml(view, { ...summaryUi, t: (key) => (key === "matches_all" ? "All {count}" : key) }).matches;
  assert.match(counted, />All 12<svg/);
  // Ten matches need no link.
  assert.doesNotMatch(playersHtml(historyView(kept("x")), summaryUi).matches, /more-matches/);
});
