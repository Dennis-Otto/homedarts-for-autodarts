// The new game screen of the scoreboard: choosing a game, players, the format and rules, and starting it.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { $, $$, DEVICE, READY, loadCards, makeHass, mount, text, update, window } from "./dom.mjs";

const {
  botMatch,
  fairStarts,
  gameGroup,
  gameRules,
  gameState,
  lobbyAverages,
  lobbyChange,
  lobbyChoice,
  lobbyGames,
  lobbySuggestions,
  personLinks,
  pictureUrl,
  startGameData,
} = await loadCards();

const OPTIONS = [
  "off",
  "101",
  "301",
  "501",
  "701",
  "901",
  "1001",
  "cricket",
  "shanghai",
  "halve_it",
  "killer",
  "around_the_clock",
  "doubles",
  "checkout",
  "bobs_27",
];
const PICTURE = "/api/image/serve/alex/512x512";
const PROFILES = {
  "sensor.player_profiles": {
    state: "4",
    attributes: {
      players: [
        { name: "Sam", person: null },
        { name: "Lea", person: "person.lea" },
        { name: "Kim", person: "person.kim" },
        { name: "Alex", person: "person.alex" },
      ],
    },
  },
};
const PEOPLE = {
  "person.alex": { state: "home", attributes: { entity_picture: PICTURE } },
  "person.kim": { state: "home", attributes: { entity_picture: "/api/image/serve/kim/512x512" } },
  "person.lea": { state: "not_home", attributes: {} },
};
// The practice game as the board has it between games: two players, three legs per set.
const BOARD = {
  "sensor.local_visit_score": { state: "0", attributes: { throws: [] } },
  "select.practice_game": { state: "off", attributes: { options: OPTIONS } },
  "number.practice_players": "2",
  "number.practice_legs": "3",
  "number.practice_sets": "1",
  "select.practice_in_mode": "straight",
  "select.practice_out_mode": "double",
  "select.practice_bull_mode": "25_50",
  "number.practice_max_rounds": "0",
  "switch.practice_double_out": "on",
  "switch.practice_double_in": "off",
  "switch.practice_bull_off": "off",
};

// The four name fields share one translation key, like the integration's.
function withNames(hass, names) {
  names.forEach((name, index) => {
    const id = `text.dartboard_practice_player_${index + 1}`;
    hass.entities[id] = { entity_id: id, platform: "homedarts", device_id: DEVICE, translation_key: "practice_player" };
    hass.states[id] = { entity_id: id, state: name, attributes: {} };
  });
  return hass;
}

function withPeople(hass, people = PEOPLE) {
  for (const [id, state] of Object.entries(people)) hass.states[id] = { entity_id: id, ...state };
  return hass;
}

const setup = (states = {}, config = {}, options = {}) => {
  const hass = withPeople(
    withNames(makeHass({ states: { ...READY, ...BOARD, ...PROFILES, ...states }, ...options }), [
      "Alex",
      "Sam",
      "",
      "Player 12",
    ])
  );
  return { hass, card: mount("homedarts-scoreboard-card", hass, config) };
};

const tap = (card, selector) => $(card, selector).click();
// Whether the new game screen shows; an element would make a failing comparison unreadable.
const choosing = (card) => Boolean($(card, ".lobby"));
const lobbyTap = (card, action, value) =>
  $(card, `[data-lobby="${action}"]${value === undefined ? "" : `[data-value="${value}"]`}`).click();
const chosenGame = (card) => $$(card, '.game[aria-pressed="true"]').map((button) => button.textContent);
const players = (card) => $$(card, ".lobby-player .who").map((name) => name.textContent);
const suggestions = (card) => $$(card, ".suggestion").map((button) => [button.className, button.textContent]);
// The switches among the options; the X01 rules are choices of their own.
const options = (card) =>
  $$(card, ".lobby-block.options > .option").map((button) => [button.dataset.value, button.getAttribute("aria-pressed")]);
const choices = (card) =>
  $$(card, ".choice").map((row) => [
    row.getAttribute("aria-label"),
    ...[...row.querySelectorAll(".option")].map(
      (button) => `${button.textContent}${button.getAttribute("aria-pressed") === "true" ? "*" : ""}`
    ),
  ]);
const steppers = (card) => $$(card, ".stepper").map((row) => row.textContent);
const started = (hass) => hass.calls.filter(([domain]) => domain === "homedarts");

test("games are grouped, filtered and ruled like the practice game", () => {
  assert.deepEqual(
    ["501", "cricket", "cricket_cut_throat", "cut_throat", "tactics", "killer", "golf", "bobs_27", "catch_40", "bingo"].map(
      gameGroup
    ),
    ["x01", "cricket", "cricket", "cricket", "cricket", "party", "party", "training", "training", "more"]
  );
  assert.deepEqual(gameRules("killer"), {
    x01: false,
    drill: false,
    teams: false,
    bot: false,
    minPlayers: 2,
    maxPlayers: 8,
  });
  // A party game seats eight, X01 and the Cricket games four.
  assert.deepEqual([gameRules("501").maxPlayers, gameRules("wild_mouse").maxPlayers], [4, 4]);
  assert.deepEqual(gameRules("doubles"), {
    x01: false,
    drill: true,
    teams: false,
    bot: false,
    minPlayers: 1,
    maxPlayers: 1,
  });
  assert.deepEqual([gameRules("701").x01, gameRules("701").teams, gameRules("tactics").teams], [true, true, true]);
  assert.deepEqual(lobbyGames([...OPTIONS, "bingo"], ["501", "bingo", "doubles"]), [
    { group: "x01", games: ["501"] },
    { group: "training", games: ["doubles"] },
    { group: "more", games: ["bingo"] },
  ]);
  assert.deepEqual(lobbyGames(undefined, []), []);
  assert.equal(lobbyGames(OPTIONS, []).length, 4);
  assert.equal(lobbyGames(OPTIONS).length, 4);
});

test("the choice starts from what the board has set, with every name once", () => {
  const board = {
    game: "cricket",
    players: 3,
    names: ["Alex", " alex ", "Sam", "Kim"],
    legs: 20,
    sets: 0,
    double_out: false,
  };
  assert.deepEqual(lobbyChoice(board, ["501", "cricket"]), {
    game: "cricket",
    players: ["Alex", "", "Sam"],
    starts: [0, 0, 0],
    botStart: 0,
    handicap: false,
    fair_start: false,
    teams: false,
    legs: 11,
    sets: 1,
    in_mode: "straight",
    out_mode: "straight",
    bull_mode: "25_50",
    max_rounds: 0,
    bull_off: false,
    bull_off_distance: false,
    three_in_a_bed: true,
    tournament: false,
    format: "round_robin",
    third_place: false,
    random_draw: false,
    groups: 0,
    advance: 2,
    draft: "",
  });
  const plain = lobbyChoice({ game: "off", players: null, names: [], legs: 2.5, sets: null }, ["301", "501"]);
  // Players without names need not be chosen.
  assert.deepEqual([plain.game, plain.players, plain.legs, plain.sets, plain.out_mode], ["501", [], 1, 1, "double"]);
  // The modes win over the switches of double in and double out; the round limit stays within 0 and 50.
  const ruled = (board) => {
    const { in_mode, out_mode, bull_mode, max_rounds } = lobbyChoice({ game: "501", names: [], ...board }, ["501"]);
    return [in_mode, out_mode, bull_mode, max_rounds];
  };
  assert.deepEqual(ruled({ in_mode: "master", out_mode: "master", bull_mode: "50_50", max_rounds: 99, double_in: true }), [
    "master",
    "master",
    "50_50",
    50,
  ]);
  assert.deepEqual(ruled({ in_mode: "sometimes", double_in: true, double_out: false, max_rounds: -3 }), [
    "double",
    "straight",
    "25_50",
    0,
  ]);
  assert.equal(lobbyChoice({ game: undefined, names: [] }, ["cricket", "killer"]).game, "cricket");
});

test("taps change the choice within the limits of the action", () => {
  let choice = lobbyChoice({ game: "501", players: 1, names: ["Alex"], legs: 1, sets: 7 }, ["501"]);
  choice = lobbyChange(choice, "add", "  Sam  ");
  choice = lobbyChange(choice, "add", "sam");
  choice = lobbyChange(choice, "add", "");
  choice = lobbyChange(choice, "add", "A very long name for a dart player");
  choice = lobbyChange(choice, "add");
  choice = lobbyChange(choice, "guest");
  assert.deepEqual(choice.players, ["Alex", "Sam", "A very long name for", ""]);
  // Four players at most.
  assert.deepEqual(lobbyChange(choice, "add", "Kim").players, choice.players);
  assert.deepEqual(lobbyChange(choice, "guest").players, choice.players);
  choice = lobbyChange(choice, "up", "1");
  choice = lobbyChange(choice, "down", "2");
  choice = lobbyChange(choice, "up", "0");
  choice = lobbyChange(choice, "down", "3");
  assert.deepEqual(choice.players, ["Sam", "Alex", "", "A very long name for"]);
  choice = lobbyChange(choice, "remove", "2");
  assert.deepEqual(choice.players, ["Sam", "Alex", "A very long name for"]);
  choice = lobbyChange(choice, "legs", "-1");
  choice = lobbyChange(choice, "sets", "1");
  choice = lobbyChange(choice, "legs", "x");
  assert.deepEqual([choice.legs, choice.sets], [1, 7]);
  choice = lobbyChange(choice, "in_mode", "master");
  choice = lobbyChange(choice, "out_mode", "triple");
  choice = lobbyChange(choice, "bull_mode", "50_50");
  choice = lobbyChange(choice, "bull_mode", "75");
  choice = lobbyChange(choice, "toggle", "double_in");
  choice = lobbyChange(choice, "toggle", "profiles");
  choice = lobbyChange(choice, "game", "killer");
  choice = lobbyChange(choice, "unknown", "1");
  assert.deepEqual(
    [choice.in_mode, choice.out_mode, choice.bull_mode, choice.double_in, choice.profiles, choice.game],
    ["master", "double", "50_50", undefined, undefined, "killer"]
  );
  // The round limit goes in steps up to 50; a limit between steps goes to its neighbours.
  const rounds = (start, ...steps) =>
    steps.reduce((next, step) => lobbyChange(next, "max_rounds", step), { ...choice, max_rounds: start }).max_rounds;
  assert.deepEqual(
    [rounds(0, "1"), rounds(0, "1", "1", "1"), rounds(0, "-1"), rounds(12, "1"), rounds(12, "-1"), rounds(50, "1")],
    [5, 15, 0, 15, 10, 50]
  );
  // A tournament plays straight or double in and out: master comes closest to double.
  const tournament = lobbyChange({ ...choice, out_mode: "master" }, "mode", "tournament");
  assert.deepEqual([tournament.in_mode, tournament.out_mode], ["double", "double"]);
  assert.equal(lobbyChange(tournament, "out_mode", "master").out_mode, "double");
  assert.equal(lobbyChange(tournament, "out_mode", "straight").out_mode, "straight");
  assert.equal(lobbyChange({ ...choice, in_mode: "straight" }, "mode", "match").in_mode, "straight");
});

test("suggestions put players at home first and leave out who plays already", () => {
  const hass = withPeople(makeHass({ states: READY }));
  const profiles = { attributes: { players: [...PROFILES["sensor.player_profiles"].attributes.players, null] } };
  const links = personLinks(hass, profiles);
  assert.deepEqual([...links.keys()], ["lea", "kim", "alex"]);
  assert.deepEqual(links.get("alex"), { person: "person.alex", picture: PICTURE, home: true });
  assert.deepEqual(links.get("lea"), { person: "person.lea", picture: null, home: false });
  assert.deepEqual(lobbySuggestions(profiles, ["Tom", "sam", "", "  "], links, ["Alex", ""]), [
    { name: "Kim", picture: "/api/image/serve/kim/512x512", home: true },
    { name: "Sam", picture: null, home: false },
    { name: "Lea", picture: null, home: false },
    { name: "Tom", picture: null, home: false },
  ]);
  assert.deepEqual(lobbySuggestions(undefined, [], new Map(), []), []);
  assert.equal(personLinks(undefined, undefined).size, 0);
  // Only pictures Home Assistant serves or that come from the web.
  assert.deepEqual(
    [PICTURE, "https://example.com/a.png", "//evil.example/a.png", "javascript:alert(1)", "data:image/png;base64,", 7].map(
      pictureUrl
    ),
    [PICTURE, "https://example.com/a.png", null, null, null, null]
  );
});

test("the action carries only what the game and the board have", () => {
  const choice = lobbyChoice(
    { game: "501", players: 2, names: ["Alex", "Sam"], legs: 3, sets: 2, bull_off: true, bull_off_distance: true },
    ["501"]
  );
  assert.deepEqual(startGameData(choice, { entry: "entry-1", distance: true }), {
    game: "501",
    players: ["Alex", "Sam"],
    config_entry_id: "entry-1",
    legs: 3,
    sets: 2,
    bull_off: true,
    bull_off_distance: true,
    in_mode: "straight", out_mode: "double", bull_mode: "25_50", max_rounds: 0,
  });
  // A board before bull-off by distance does not know the field.
  assert.equal("bull_off_distance" in startGameData(choice, { distance: false }), false);
  assert.deepEqual(startGameData({ ...choice, game: "cricket", bull_off: false }, { distance: true }), {
    game: "cricket",
    players: ["Alex", "Sam"],
    legs: 3,
    sets: 2,
    bull_off: false,
  });
  // Training games are for one player; nobody chosen is one player without a name.
  assert.deepEqual(startGameData({ ...choice, game: "doubles" }), { game: "doubles", players: ["Alex"] });
  assert.deepEqual(startGameData({ ...choice, players: [] }), {
    game: "501",
    players: [""],
    in_mode: "straight", out_mode: "double", bull_mode: "25_50", max_rounds: 0,
  });
});

test("the state of the game decides when the screen and idle mode may come", () => {
  const x01 = (winner) => ({ mode: "x01", practice: { winner } });
  assert.deepEqual(
    [
      { mode: "idle" },
      { mode: "drill", drill: { finished: true } },
      { mode: "drill", drill: { finished: false } },
      { mode: "bulloff", bullOff: {} },
      x01(null),
      x01(1),
      { mode: "cricket", cricket: { winner: 2 } },
      { mode: "party", party: { winner: null } },
    ].map(gameState),
    ["none", "over", "running", "running", "running", "over", "over", "running"]
  );
});

test("between games a big button opens the new game screen with the board's settings", () => {
  const { card } = setup();
  // The big button opens it between games; the header keeps no second one.
  assert.equal($(card, ".lobby-toggle").hidden, true);
  assert.equal(text(card, ".lobby-toggle"), "＋New game");
  assert.equal(text(card, ".main .lobby-cta"), "New game");
  assert.equal(choosing(card), false);
  tap(card, ".main .lobby-cta");

  assert.equal(text(card, ".title"), "New game");
  assert.equal(text(card, ".meta"), "");
  assert.equal($(card, ".lobby-toggle").hidden, true);
  assert.equal($(card, ".visit").hidden, true);
  assert.equal($(card, ".scoreboard").classList.contains("choosing"), true);
  assert.equal($(card, ".lobby").getAttribute("aria-label"), "Choose the game, the players and the format");
  assert.deepEqual(
    $$(card, ".lobby-group > .section-label").map((label) => label.textContent),
    ["X01", "Cricket", "Party games", "Training games"]
  );
  assert.equal($$(card, ".game").length, 14);
  assert.deepEqual(chosenGame(card), ["501"]);
  assert.deepEqual(players(card), ["Alex", "Sam"]);
  // Alex is linked to a person with a picture.
  assert.deepEqual(
    $$(card, ".lobby-player .avatar").map((image) => image.getAttribute("src")),
    [PICTURE]
  );
  // Kim is at home and comes first; the empty field and the numbered one are names too.
  assert.deepEqual(suggestions(card), [
    ["suggestion home", "Kim⌂"],
    ["suggestion", "Lea"],
    ["suggestion", "Player 12"],
    ["suggestion guest", "+ Guest"],
    ["suggestion bot", "+ Bot"],
  ]);
  assert.equal($(card, ".suggestion.home .home").getAttribute("aria-label"), "at home");
  assert.deepEqual(steppers(card), ["Legs per set−3+", "Sets to win−1+", "Max rounds−No limit+"]);
  assert.equal($(card, '[data-lobby="sets"][data-value="-1"]').disabled, true);
  assert.equal($(card, '[data-lobby="legs"][data-value="-1"]').getAttribute("aria-label"), "Fewer: Legs per set");
  assert.deepEqual(choices(card), [
    ["In", "Straight*", "Double", "Master"],
    ["Out", "Straight", "Double*", "Master"],
    ["Bull", "25/50*", "50/50"],
  ]);
  assert.equal($(card, '[data-lobby="max_rounds"][data-value="-1"]').disabled, true);
  assert.equal($(card, '[data-lobby="max_rounds"][data-value="1"]').getAttribute("aria-label"), "More: Max rounds");
  assert.deepEqual(options(card), [
    ["bull_off", "false"],
    ["fair_start", "false"],
  ]);
  assert.equal(text(card, ".lobby .start"), "Start 501");
  // Without a game there is nothing to end.
  assert.equal($(card, '[data-lobby="end"]'), null);
  // Nothing holds the start back.
  assert.equal($(card, ".lobby-hint"), null);
});

test("with nobody chosen, one player throws without a name", () => {
  const { hass, card } = setup({ "number.practice_players": "1" });
  card.hass = withNames({ ...hass, entities: { ...hass.entities }, states: { ...hass.states } }, ["", "", "", ""]);
  tap(card, ".lobby-toggle");
  assert.equal($(card, ".lobby-players"), null);
  assert.equal(text(card, ".lobby-nobody"), "Nobody chosen: one player throws without a name.");
  lobbyTap(card, "start");
  assert.deepEqual(started(hass)[0][2], { game: "501", players: [""], in_mode: "straight", out_mode: "double", bull_mode: "25_50", max_rounds: 0 });
});

test("the format stops at the limits of a match, and a name field without a state is empty", () => {
  const { card } = setup({ "number.practice_legs": "11", "number.practice_sets": "7", "number.practice_max_rounds": "50" });
  card.hass = {
    ...card._hass,
    states: {
      ...card._hass.states,
      "text.dartboard_practice_player_2": { entity_id: "text.dartboard_practice_player_2", state: "unavailable", attributes: {} },
    },
  };
  tap(card, ".lobby-toggle");
  assert.deepEqual(players(card), ["Alex", "Player 2"]);
  assert.equal($(card, '[data-lobby="legs"][data-value="1"]').disabled, true);
  assert.equal($(card, '[data-lobby="sets"][data-value="1"]').disabled, true);
  assert.equal($(card, '[data-lobby="legs"][data-value="1"]').getAttribute("aria-label"), "More: Legs per set");
  assert.deepEqual(steppers(card), ["Legs per set−11+", "Sets to win−7+", "Max rounds−50+"]);
  assert.equal($(card, '[data-lobby="max_rounds"][data-value="1"]').disabled, true);
  assert.equal($(card, '[data-lobby="max_rounds"][data-value="-1"]').disabled, false);
});

test("a card that reaches the page before Home Assistant waits for it", () => {
  const card = document.createElement("homedarts-scoreboard-card");
  card.setConfig({ type: "custom:homedarts-scoreboard-card" });
  document.body.append(card);
  card.remove();
  assert.equal(card.shadowRoot.innerHTML, "");
});

test("the new game screen starts the chosen game with players, format and rules", () => {
  const { hass, card } = setup();
  tap(card, ".main .lobby-cta");
  lobbyTap(card, "game", "cricket");
  assert.deepEqual(chosenGame(card), ["Cricket"]);
  // Cricket has no double in or out.
  assert.deepEqual(options(card), [["bull_off", "false"]]);
  lobbyTap(card, "add", "Kim");
  assert.deepEqual(players(card), ["Alex", "Sam", "Kim"]);
  assert.deepEqual(suggestions(card)[0], ["suggestion", "Lea"]);
  lobbyTap(card, "up", "2");
  lobbyTap(card, "remove", "2");
  assert.deepEqual(players(card), ["Alex", "Kim"]);
  assert.equal($(card, '[data-lobby="up"][data-value="0"]').disabled, true);
  assert.equal($(card, '[data-lobby="down"][data-value="1"]').disabled, true);
  assert.equal($(card, '[data-lobby="remove"][data-value="1"]').getAttribute("aria-label"), "Remove Kim");
  lobbyTap(card, "down", "0");
  lobbyTap(card, "legs", "1");
  lobbyTap(card, "sets", "1");
  lobbyTap(card, "toggle", "bull_off");
  assert.deepEqual(steppers(card), ["Legs per set−4+", "Sets to win−2+"]);
  assert.deepEqual(options(card), [["bull_off", "true"]]);
  // Without the switch for it, the board has no bull-off by distance.
  assert.equal($(card, '[data-value="bull_off_distance"]'), null);
  lobbyTap(card, "start");
  assert.deepEqual(started(hass), [
    [
      "homedarts",
      "start_game",
      { game: "cricket", players: ["Kim", "Alex"], legs: 4, sets: 2, bull_off: true },
    ],
  ]);
  assert.equal(choosing(card), false);
  assert.equal(text(card, ".main .lobby-cta"), "New game");
  assert.equal($(card, ".lobby-toggle").hidden, true);
});

test("names are typed in, and a player can play only once and four at most", () => {
  const { hass, card } = setup();
  tap(card, ".lobby-toggle");
  const input = () => $(card, ".lobby-name");
  assert.equal(input().getAttribute("maxlength"), "20");
  assert.equal(input().getAttribute("placeholder"), "Name");
  assert.equal(input().getAttribute("aria-label"), "Name of another player");
  input().value = "Tom";
  input().dispatchEvent(new window.Event("input", { bubbles: true }));
  // Other keys do nothing; Enter adds the name.
  input().dispatchEvent(new window.KeyboardEvent("keydown", { key: "a", bubbles: true }));
  assert.deepEqual(players(card), ["Alex", "Sam"]);
  input().dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  assert.deepEqual(players(card), ["Alex", "Sam", "Tom"]);
  assert.equal(input().value, "");
  // A name that plays already stays in the field.
  input().value = "alex";
  input().dispatchEvent(new window.Event("input", { bubbles: true }));
  lobbyTap(card, "add-name");
  assert.deepEqual(players(card), ["Alex", "Sam", "Tom"]);
  assert.equal(input().value, "alex");
  lobbyTap(card, "guest");
  assert.deepEqual(players(card), ["Alex", "Sam", "Tom", "Player 4"]);
  // Full: nothing more can be added.
  assert.equal(input().disabled, true);
  assert.ok($$(card, ".suggestion").every((button) => button.disabled));
  assert.equal($(card, '[data-lobby="add-name"]').disabled, true);
  $(card, ".suggestion").click();
  assert.deepEqual(players(card), ["Alex", "Sam", "Tom", "Player 4"]);
  // Other elements do not count as the name field.
  $(card, ".lobby-player .who").dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  $(card, ".lobby-player .who").dispatchEvent(new window.Event("input", { bubbles: true }));
  lobbyTap(card, "start");
  assert.deepEqual(started(hass)[0][2].players, ["Alex", "Sam", "Tom", ""]);
});

test("a party game takes eight players, and in X01 the others sit out", () => {
  const { hass, card } = setup();
  tap(card, ".lobby-toggle");
  lobbyTap(card, "game", "killer");
  for (let index = 0; index < 6; index += 1) lobbyTap(card, "guest");
  assert.deepEqual(players(card), ["Alex", "Sam", ...[3, 4, 5, 6, 7, 8].map((index) => `Player ${index}`)]);
  assert.equal($(card, ".lobby-name").disabled, true);
  assert.equal(text(card, ".lobby-hint"), "8 players at most.");
  // X01 is for four: the others sit out, and the start takes the first four.
  lobbyTap(card, "game", "501");
  assert.equal(text(card, ".lobby-hint"), "501 is for 4: the others sit out.");
  lobbyTap(card, "start");
  assert.deepEqual(started(hass)[0][2].players, ["Alex", "Sam", "", ""]);
  // The board's party comes back on the screen, all eight of them.
  const party = setup({ "number.practice_players": "8" });
  tap(party.card, ".lobby-toggle");
  assert.equal(players(party.card).length, 8);
});

test("Killer asks for two players, and training games take the first player only", () => {
  const { hass, card } = setup();
  tap(card, ".lobby-toggle");
  lobbyTap(card, "game", "killer");
  lobbyTap(card, "remove", "1");
  assert.equal(text(card, ".lobby-hint"), "Killer needs at least two players");
  assert.equal($(card, ".lobby .start").disabled, true);
  // Alone there is no match: no format and no bull-off.
  assert.equal($(card, ".stepper"), null);
  assert.equal($(card, ".options"), null);
  lobbyTap(card, "start");
  assert.deepEqual(started(hass), []);

  lobbyTap(card, "add", "Lea");
  lobbyTap(card, "game", "around_the_clock");
  assert.equal(text(card, ".lobby-hint"), "Training games are for one player: Alex plays.");
  assert.deepEqual(
    $$(card, ".lobby-player").map((row) => row.className),
    ["lobby-player", "lobby-player resting"]
  );
  assert.equal(text(card, ".lobby .start"), "Start Around the Clock");
  lobbyTap(card, "start");
  assert.deepEqual(started(hass), [["homedarts", "start_game", { game: "around_the_clock", players: ["Alex"] }]]);
});

test("X01 rules, bull-off by distance and the board's config entry go with the start", () => {
  const { hass, card } = setup(
    { "switch.practice_bull_off": "on", "switch.practice_bull_off_distance": "off" },
    {},
    { device: { config_entry_id: "entry-7", primary_config_entry: "other", config_entries: ["other"] } }
  );
  tap(card, ".lobby-toggle");
  assert.deepEqual(options(card), [
    ["bull_off", "true"],
    ["bull_off_distance", "false"],
    ["fair_start", "false"],
  ]);
  assert.equal(text(card, '[data-value="bull_off_distance"]'), "Bull-off by distance");
  lobbyTap(card, "toggle", "bull_off_distance");
  lobbyTap(card, "in_mode", "double");
  lobbyTap(card, "out_mode", "master");
  lobbyTap(card, "bull_mode", "50_50");
  lobbyTap(card, "max_rounds", "1");
  lobbyTap(card, "max_rounds", "1");
  assert.deepEqual(choices(card), [
    ["In", "Straight", "Double*", "Master"],
    ["Out", "Straight", "Double", "Master*"],
    ["Bull", "25/50", "50/50*"],
  ]);
  assert.equal(steppers(card).at(-1), "Max rounds−10+");
  assert.equal(text(card, ".said"), "Max rounds 10");
  lobbyTap(card, "game", "301");
  lobbyTap(card, "start");
  assert.deepEqual(started(hass)[0][2], {
    game: "301",
    players: ["Alex", "Sam"],
    config_entry_id: "entry-7",
    legs: 3,
    sets: 1,
    bull_off: true,
    bull_off_distance: true,
    in_mode: "double",
    out_mode: "master",
    bull_mode: "50_50",
    max_rounds: 10,
  });
  // Without a primary entry, the first entry of the device.
  const other = setup({}, {}, { device: { config_entries: ["entry-9"] } });
  tap(other.card, ".lobby-toggle");
  lobbyTap(other.card, "start");
  assert.equal(started(other.hass)[0][2].config_entry_id, "entry-9");
});

test("Wild Mouse offers three in a bed, which goes with its start", () => {
  const games = { state: "off", attributes: { options: [...OPTIONS, "wild_mouse"] } };
  const { hass, card } = setup({ "select.practice_game": games, "switch.practice_three_in_a_bed": "off" });
  tap(card, ".lobby-toggle");
  lobbyTap(card, "game", "wild_mouse");
  assert.deepEqual(options(card), [
    ["bull_off", "false"],
    ["three_in_a_bed", "false"],
  ]);
  assert.equal(text(card, '[data-value="three_in_a_bed"]'), "Three in a bed");
  lobbyTap(card, "toggle", "three_in_a_bed");
  lobbyTap(card, "start");
  assert.deepEqual(started(hass)[0][2], {
    game: "wild_mouse",
    players: ["Alex", "Sam"],
    legs: 3,
    sets: 1,
    bull_off: false,
    three_in_a_bed: true,
  });
  // Other games leave the rule out, and so does a board without it.
  tap(card, ".lobby-toggle");
  lobbyTap(card, "game", "cricket");
  assert.deepEqual(options(card), [["bull_off", "false"]]);
  const older = setup({ "select.practice_game": games });
  tap(older.card, ".lobby-toggle");
  lobbyTap(older.card, "game", "wild_mouse");
  assert.deepEqual(options(older.card), [["bull_off", "false"]]);
  lobbyTap(older.card, "start");
  assert.equal("three_in_a_bed" in started(older.hass)[0][2], false);
  assert.equal(startGameData({ game: "wild_mouse", players: ["A"] }, { bed: true }).three_in_a_bed, true);
});

test("the screen says how the chosen game is played and links to all its rules", () => {
  const site = "https://dennis-otto.github.io/homedarts-for-autodarts/";
  const rules = (card) => [$(card, ".lobby-rules p").textContent, $(card, ".lobby-rules a").getAttribute("href")];
  const { card } = setup();
  tap(card, ".lobby-toggle");
  lobbyTap(card, "game", "501");
  assert.equal(text(card, ".lobby-rules .section-label"), "How to play");
  assert.deepEqual(rules(card), [
    "Count down to exactly zero; with double out, the last dart hits a double or the bullseye. A dart that goes too far busts the visit.",
    `${site}games.html#x01`,
  ]);
  assert.equal($(card, ".lobby-rules a").getAttribute("target"), "_blank");
  assert.equal(text(card, ".lobby-rules a"), "All rules");
  lobbyTap(card, "game", "doubles");
  assert.equal(rules(card)[1], `${site}games.html#doubles-training`);
  lobbyTap(card, "game", "halve_it");
  assert.equal(rules(card)[1], `${site}games.html#halve-it`);
  // In German, the German page and its heading.
  const german = setup({}, {}, { language: "de" }).card;
  tap(german, ".lobby-toggle");
  lobbyTap(german, "game", "doubles");
  assert.equal(text(german, ".lobby-rules .section-label"), "So wird gespielt");
  assert.deepEqual(rules(german), [
    "Triff D1 bis D20 und dann das Bullseye der Reihe nach, mit so wenigen Darts wie möglich.",
    `${site}de/games.html#doppeltraining`,
  ]);
  // A game the card does not know has no rules to show.
  const odd = setup({ "select.practice_game": { state: "off", attributes: { options: ["off", "bingo"] } } }).card;
  tap(odd, ".lobby-toggle");
  assert.equal($(odd, ".lobby-rules"), null);
});

test("during a game the screen opens with it chosen and can end it with a second tap", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "setInterval", "Date"], now: 0 });
  const running = {
    "select.practice_game": { state: "shanghai", attributes: { options: OPTIONS } },
    "switch.practice_double_out": "off",
    "sensor.practice_remaining": {
      state: "unknown",
      attributes: { game: "shanghai", round: 1, rounds: 7, target: "1", player: 1, scores: [{ player: 1 }] },
    },
  };
  const { hass, card } = setup(running);
  assert.equal($(card, ".main .lobby-cta"), null);
  tap(card, ".lobby-toggle");
  assert.deepEqual(chosenGame(card), ["Shanghai"]);
  const end = () => $(card, '[data-lobby="end"]');
  assert.equal(end().textContent, "End game");
  end().click();
  assert.equal(end().textContent, "Confirm?");
  assert.deepEqual(hass.calls, []);
  // Without the second tap, the question goes away again.
  t.mock.timers.tick(4000);
  assert.equal(end().textContent, "End game");
  end().click();
  end().click();
  assert.deepEqual(hass.calls, [["select", "select_option", { entity_id: "select.dartboard_practice_game", option: "off" }]]);
  // The screen stays for the next game.
  card.hass = update(hass, {
    "select.practice_game": { state: "off", attributes: { options: OPTIONS } },
    "sensor.practice_remaining": "unknown",
  });
  assert.equal(end(), null);
  assert.equal(text(card, ".title"), "New game");
  lobbyTap(card, "close");
  assert.equal(choosing(card), false);
  assert.equal(text(card, ".main .lobby-cta"), "New game");
  // Taps on the screen without a lobby do nothing.
  card._lobbyAction("start");
  assert.equal(hass.calls.length, 1);
});

test("the screen can be switched off, limited to some games, and never opens in the preview", () => {
  const off = setup({}, { lobby: false }).card;
  assert.equal($(off, ".lobby-toggle").hidden, true);
  assert.equal($(off, ".lobby-cta"), null);
  off._lobbyAction("open");
  assert.equal(choosing(off), false);

  const some = setup({}, { lobby_games: ["cricket", "killer", "tactics", 301] }).card;
  tap(some, ".lobby-toggle");
  // YAML reads 301 as a number; it is offered all the same.
  assert.deepEqual(
    $$(some, ".game").map((button) => button.textContent),
    ["301", "Cricket", "Killer"]
  );
  // Without 501 among the games, the first game is chosen.
  assert.deepEqual(chosenGame(some), ["301"]);

  const preview = setup().card;
  preview.preview = true;
  tap(preview, ".lobby-toggle");
  tap(preview, ".main .lobby-cta");
  assert.equal(choosing(preview), false);

  // A board without the practice game has no screen.
  const bare = mount("homedarts-scoreboard-card", makeHass({ states: READY }));
  assert.equal($(bare, ".lobby-toggle").hidden, true);
});

test("a game that ends opens the screen by itself, and throwing darts closes it again", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "setInterval", "Date"], now: 0 });
  const match = (attributes) => ({
    "select.practice_game": { state: "501", attributes: { options: OPTIONS } },
    "sensor.practice_remaining": {
      state: "0",
      attributes: {
        game: 501,
        player: 1,
        name: "Alex",
        scores: [
          { player: 1, name: "Alex", remaining: 0, legs: 1, sets: 1 },
          { player: 2, name: "Sam", remaining: 40, legs: 0, sets: 0 },
        ],
        ...attributes,
      },
    },
  });
  const { hass, card } = setup(match({ winner: null }));
  let next = update(hass, match({ won: true, winner: 1 }));
  card.hass = next;
  assert.equal(text(card, ".banner"), "Alex wins the match!");
  t.mock.timers.tick(7999);
  assert.equal(choosing(card), false);
  t.mock.timers.tick(1);
  assert.equal(text(card, ".title"), "New game");
  // The result stays above the screen.
  assert.equal(text(card, ".banner"), "Alex wins the match!");
  assert.deepEqual(chosenGame(card), ["501"]);
  // The next dart starts the rematch, so the screen that opened by itself goes.
  next = update(next, {
    "sensor.local_visit_score": { state: "60", attributes: { throws: [{ number: 20, multiplier: 3 }] } },
  });
  card.hass = next;
  assert.equal(choosing(card), false);

  // A game that starts again before the pause keeps the screen closed.
  card.hass = next = update(next, match({ winner: null }));
  card.hass = next = update(next, match({ winner: 1 }));
  card.hass = next = update(next, match({ winner: null }));
  t.mock.timers.tick(10000);
  assert.equal(choosing(card), false);

  // A screen opened by a tap stays while darts land.
  tap(card, ".lobby-toggle");
  card.hass = update(next, {
    "sensor.local_visit_score": { state: "120", attributes: { throws: [{ number: 20, multiplier: 3 }, { number: 20, multiplier: 3 }] } },
  });
  assert.equal(text(card, ".title"), "New game");
});

test("the screen that opens by itself waits the idle time before idle mode takes over", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "setInterval", "Date"], now: 0 });
  const decided = (winner) => ({
    "sensor.practice_remaining": {
      state: "0",
      attributes: { game: 501, player: 1, winner, scores: [{ player: 1, remaining: 0 }, { player: 2, remaining: 60 }] },
    },
  });
  const { hass, card } = setup(decided(null), { idle_after: 10 });
  card.hass = update(hass, decided(1));
  t.mock.timers.tick(8000);
  assert.equal(text(card, ".title"), "New game");
  // Ten seconds from the opening, not from the end of the game.
  t.mock.timers.tick(9999);
  assert.equal(choosing(card), true);
  t.mock.timers.tick(1);
  assert.equal(choosing(card), false);
  assert.equal($(card, ".idle-panel").dataset.panel, "clock");

  // Once idle mode has begun, nobody is there to choose: the screen stays closed.
  const early = setup(decided(null), { idle_after: 5 });
  early.card.hass = update(early.hass, decided(1));
  t.mock.timers.tick(5000);
  assert.equal($(early.card, ".idle-panel").dataset.panel, "clock");
  t.mock.timers.tick(5000);
  assert.equal(choosing(early.card), false);
});

test("the new game screen speaks German and names newer games as Home Assistant does", () => {
  const { hass, card } = setup(
    { "select.practice_game": { state: "off", attributes: { options: [...OPTIONS, "bingo"] } } },
    {},
    { language: "de" }
  );
  hass.formatEntityState = (state, option) => (option === "bingo" ? "Bingo" : option);
  card.hass = { ...hass };
  tap(card, ".lobby-toggle");
  assert.equal(text(card, ".title"), "Neues Spiel");
  assert.deepEqual(
    $$(card, ".lobby-group > .section-label").map((label) => label.textContent),
    ["X01", "Cricket", "Partyspiele", "Trainingsspiele", "Weitere Spiele"]
  );
  assert.equal($$(card, ".game").at(-1).textContent, "Bingo");
  assert.equal(text(card, ".lobby .start"), "501 starten");
  assert.deepEqual(options(card).map(([option]) => text(card, `[data-value="${option}"]`)), ["Ausbullen", "Fairer Start"]);
  assert.deepEqual(choices(card)[0], ["In", "Straight*", "Double", "Master"]);
  assert.equal(steppers(card).at(-1), "Maximale Runden−Keine Grenze+");
  assert.deepEqual(
    suggestions(card)
      .slice(-2)
      .map(([, label]) => label),
    ["+ Gast", "+ Bot"]
  );
  assert.deepEqual(
    $$(card, ".lobby-block > .section-label").map((label) => label.textContent),
    ["Spieler", "Format", "Optionen"]
  );
  // Without Home Assistant's names, a newer game reads as its option.
  delete hass.formatEntityState;
  card.hass = update(hass, { "number.practice_legs": "4" });
  assert.equal($$(card, ".game").at(-1).textContent, "bingo");
});

test("in X01 every player can start from a score of their own, in steps of 100", () => {
  let choice = lobbyChoice(
    { game: "501", players: 2, names: ["Alex", "Sam"], starts: [0, 301, "x", 0] },
    ["501", "cricket"]
  );
  assert.deepEqual([choice.starts, choice.handicap], [[0, 301], true]);
  choice = lobbyChange(choice, "raise", "0");
  choice = lobbyChange(choice, "lower", "1");
  assert.deepEqual(choice.starts, [601, 201]);
  // Back at the game's start, a start of its own is 0 again; 101 and 1001 are the limits.
  choice = lobbyChange(choice, "lower", "0");
  assert.deepEqual(choice.starts, [0, 201]);
  for (let step = 0; step < 3; step += 1) choice = lobbyChange(choice, "lower", "1");
  for (let step = 0; step < 6; step += 1) choice = lobbyChange(choice, "raise", "0");
  assert.deepEqual(choice.starts, [1001, 101]);
  // The start scores move and go with their players.
  choice = lobbyChange(choice, "guest");
  choice = lobbyChange(choice, "up", "1");
  assert.deepEqual([choice.players, choice.starts], [["Sam", "Alex", ""], [101, 1001, 0]]);
  choice = lobbyChange(choice, "remove", "0");
  assert.deepEqual(choice.starts, [1001, 0]);
  // Nobody at that place, or a game other than X01, changes nothing.
  assert.deepEqual(lobbyChange(choice, "raise", "5").starts, [1001, 0]);
  assert.deepEqual(lobbyChange({ ...choice, game: "cricket" }, "raise", "1").starts, [1001, 0]);
  assert.deepEqual(startGameData(choice), {
    game: "501",
    players: ["Alex", ""],
    legs: 1,
    sets: 1,
    bull_off: false,
    in_mode: "straight", out_mode: "double", bull_mode: "25_50", max_rounds: 0,
    start_scores: [1001, 0],
  });
  // Once the board had start scores, the game's start goes back with the start.
  const reset = lobbyChoice({ game: "301", players: 1, names: ["Alex"], starts: [0, 201] }, ["301"]);
  assert.deepEqual(startGameData(reset).start_scores, [0]);
  // A choice from older cards without start scores starts from the game's.
  const { starts, ...older } = reset;
  assert.deepEqual(lobbyChange(older, "raise", "0").starts, [401]);
  const pair = { ...older, players: ["Alex", "Sam"] };
  assert.deepEqual(lobbyChange(pair, "down", "0").starts, [0, 0]);
  assert.equal("start_scores" in startGameData({ ...older, handicap: false }), false);
});

test("four players of X01 or Cricket can play as two teams", () => {
  const names = ["Alex", "Sam", "Kim", "Lea"];
  let choice = lobbyChoice({ game: "cricket", players: 4, names, teams: true }, ["cricket", "golf"]);
  assert.equal(startGameData(choice).teams, true);
  choice = lobbyChange(choice, "toggle", "teams");
  assert.equal(startGameData(choice).teams, false);
  // Teams need four players and a game for teams.
  assert.equal("teams" in startGameData({ ...choice, players: names.slice(0, 3) }), false);
  assert.equal("teams" in startGameData({ ...choice, game: "golf" }), false);
});

test("the new game screen offers teams and start scores of their own", () => {
  const teams = {
    "switch.practice_teams": "off",
    "number.practice_players": "4",
    "select.practice_game": { state: "501", attributes: { options: OPTIONS } },
  };
  const { hass, card } = setup(teams);
  ["Alex", "Sam", "Kim", "Lea"].forEach((name, index) => {
    const id = `text.dartboard_practice_player_${index + 1}`;
    hass.states[id] = { ...hass.states[id], state: name };
  });
  // The four start scores share one translation key, like the names.
  hass.entities = { ...hass.entities };
  [0, 301, 0, "unavailable"].forEach((start, index) => {
    const id = `number.dartboard_practice_start_score_player_${index + 1}`;
    hass.entities[id] = { entity_id: id, platform: "homedarts", device_id: DEVICE, translation_key: "practice_start" };
    hass.states[id] = { entity_id: id, state: String(start), attributes: {} };
  });
  card.hass = { ...hass };
  tap(card, ".lobby-toggle");
  assert.deepEqual(
    $$(card, ".lobby-start").map((start) => [start.className, start.querySelector("b").textContent]),
    [
      ["lobby-start", "501"],
      ["lobby-start own", "301"],
      ["lobby-start", "501"],
      ["lobby-start", "501"],
    ]
  );
  assert.equal($(card, '[data-lobby="raise"][data-value="0"]').getAttribute("aria-label"), "Higher start score: Alex");
  lobbyTap(card, "raise", "0");
  // 101 and 1001 are the limits of the steps.
  for (let step = 0; step < 5; step += 1) lobbyTap(card, "raise", "2");
  for (let step = 0; step < 4; step += 1) lobbyTap(card, "lower", "3");
  assert.deepEqual(
    ["raise", "lower"].map((action) => $(card, `[data-lobby="${action}"][data-value="${action === "raise" ? 2 : 3}"]`).disabled),
    [true, true]
  );
  assert.deepEqual(options(card), [
    ["bull_off", "false"],
    ["teams", "false"],
    ["fair_start", "false"],
  ]);
  assert.equal(text(card, '[data-value="teams"]'), "Teams (1 + 3 against 2 + 4)");
  lobbyTap(card, "toggle", "teams");
  tap(card, ".lobby .start");
  const [[, , data]] = started(hass);
  // A team plays from the start score of its first player, and the action takes one per team.
  assert.deepEqual([data.start_scores, data.teams], [[601, 301], true]);
  // Cricket has no start scores; without the team switch, no teams are offered.
  const cricket = setup({ "number.practice_players": "4" });
  tap(cricket.card, ".lobby-toggle");
  lobbyTap(cricket.card, "game", "cricket");
  assert.deepEqual([$$(cricket.card, ".lobby-start").length, options(cricket.card).length], [0, 1]);
});

test("buttons keep the focus through every render, for keyboards and screen readers", () => {
  const { card } = setup();
  tap(card, ".lobby-toggle");
  const focused = () => card.shadowRoot.activeElement;
  for (const [action, value] of [
    ["game", "cricket"],
    ["legs", "1"],
    ["toggle", "bull_off"],
    ["game", "501"],
    ["raise", "0"],
  ]) {
    const button = $(card, `[data-lobby="${action}"][data-value="${value}"]`);
    button.focus();
    button.click();
    // The markup is new, and the same button has the focus again.
    assert.notEqual(focused(), button, action);
    assert.equal(focused().dataset.focus, `${action}:${value}`, action);
  }
  // A button that is gone after the tap leaves the focus nowhere.
  const suggestion = $(card, '[data-lobby="add"][data-value="Kim"]');
  suggestion.focus();
  suggestion.click();
  assert.equal($(card, '[data-lobby="add"][data-value="Kim"]'), null);
  assert.deepEqual(players(card), ["Alex", "Sam", "Kim"]);
});

test("a name being typed keeps its text and its caret when the screen renders again", () => {
  const { hass, card } = setup();
  tap(card, ".lobby-toggle");
  const field = $(card, ".lobby-name");
  // The draft is never part of the markup, so typing does not replace the field.
  assert.equal(field.hasAttribute("value"), false);
  field.focus();
  field.value = "Jona";
  field.setSelectionRange(2, 2);
  field.dispatchEvent(new window.Event("input", { bubbles: true }));
  // The board's status changes: the same field stays, with its caret.
  card.hass = update(hass, { "sensor.local_status": "Takeout" });
  assert.equal($(card, ".lobby-name"), field);
  assert.deepEqual([field.value, field.selectionStart], ["Jona", 2]);
  // Kim leaves home: the suggestions change and the field is new, with the text and caret of the old one.
  card.hass = withPeople(update(hass, { "sensor.local_status": "Throw" }), { "person.kim": { state: "not_home", attributes: {} } });
  const renewed = $(card, ".lobby-name");
  assert.notEqual(renewed, field);
  assert.equal(card.shadowRoot.activeElement, renewed);
  assert.deepEqual([renewed.value, renewed.selectionStart, renewed.selectionEnd], ["Jona", 2, 2]);
  // A tap elsewhere renders the field anew with the name typed so far.
  $(card, '[data-lobby="legs"][data-value="1"]').click();
  assert.equal($(card, ".lobby-name").value, "Jona");
  $(card, ".lobby-name").dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  assert.deepEqual(players(card), ["Alex", "Sam", "Jona"]);
  assert.equal($(card, ".lobby-name").value, "");
});

test("the start stays at the bottom below both columns, and a live region reads out what changed", () => {
  const { card } = setup();
  tap(card, ".lobby-toggle");
  // Sticky only works as a child of the grid, not inside a column.
  assert.equal($(card, ".lobby-actions").parentElement, $(card, ".lobby"));
  const said = $(card, ".said");
  assert.deepEqual([said.getAttribute("role"), said.parentElement, said.className], ["status", $(card, ".scoreboard"), "visually-hidden said"]);
  lobbyTap(card, "legs", "1");
  assert.equal(said.textContent, "Legs per set 4");
  lobbyTap(card, "sets", "1");
  assert.equal(said.textContent, "Sets to win 2");
  lobbyTap(card, "raise", "0");
  assert.equal(said.textContent, "Alex 601");
  lobbyTap(card, "guest");
  lobbyTap(card, "lower", "2");
  assert.equal(said.textContent, "Player 3 401");
  lobbyTap(card, "remove", "2");
  lobbyTap(card, "bot", "add");
  assert.equal(said.textContent, "Bot 60");
  lobbyTap(card, "bot", "raise");
  assert.equal(said.textContent, "Bot 70");
  // Taps without a value to read out leave the last one.
  lobbyTap(card, "bot", "remove");
  lobbyTap(card, "toggle", "bull_off");
  assert.equal(said.textContent, "Bot 70");
  // What holds the start back is read out once, when it appears.
  lobbyTap(card, "game", "killer");
  lobbyTap(card, "remove", "1");
  lobbyTap(card, "remove", "0");
  assert.equal(said.textContent, "Killer needs at least two players");
  // Once the hint goes, nothing new is said.
  said.textContent = "";
  lobbyTap(card, "game", "cricket");
  assert.equal($(card, ".lobby-hint"), null);
  assert.equal(said.textContent, "");
});

test("a start with detection stopped switches detection on, which the screen says first", () => {
  const { hass, card } = setup({ "switch.detection": "off" });
  tap(card, ".lobby-toggle");
  assert.deepEqual($$(card, ".lobby-hint").map((hint) => hint.textContent), ["Detection is stopped: the start switches it on."]);
  lobbyTap(card, "start");
  assert.deepEqual(hass.calls.slice(0, 2), [
    ["switch", "turn_on", { entity_id: "switch.dartboard_detection" }],
    ["homedarts", "start_game", started(hass)[0][2]],
  ]);
  // Boards without the switch press their start button; an offline board and a running one are left alone.
  const { "switch.detection": _, ...ready } = READY;
  const buttons = makeHass({ states: { ...ready, ...BOARD, "sensor.local_status": "Stopped" } });
  const legacy = mount("homedarts-scoreboard-card", buttons);
  tap(legacy, ".lobby-toggle");
  lobbyTap(legacy, "start");
  assert.deepEqual(buttons.calls[0], ["button", "press", { entity_id: "button.dartboard_start" }]);
  for (const states of [{ "switch.detection": "off", "binary_sensor.local_connected": "off" }, {}]) {
    const other = setup(states);
    tap(other.card, ".lobby-toggle");
    assert.equal($(other.card, ".lobby-hint"), null);
    lobbyTap(other.card, "start");
    assert.deepEqual(other.hass.calls.map(([domain]) => domain), ["homedarts"]);
  }
});

// Fair start ---------------------------------------------------------------------

const FAIR = new Map([
  ["alex", 60],
  ["sam", 30],
  ["kim", 45],
  ["lea", 15],
]);
const fairChoice = (board, averages = FAIR) => ({
  ...lobbyChoice({ game: "501", names: [], ...board, players: board.names.length }, ["101", "301", "501", "cricket"]),
  averages,
});
// The profiles with their averages, as the sensor shows them, and the board's players.
const PLAYERS_AVERAGES = {
  "sensor.player_profiles": {
    state: "2",
    attributes: {
      players: [
        { name: "Alex", person: null, recent_average: 60 },
        { name: "Sam", person: null, recent_average: 30 },
      ],
    },
  },
};
const shownStarts = (card) => $$(card, ".lobby-start b").map((start) => start.textContent);

test("a fair start works out the scores that the integration does", () => {
  const cases = JSON.parse(readFileSync(new URL("../fixtures/fair_starts.json", import.meta.url), "utf8"));
  for (const { why, game, averages, starts } of cases) assert.deepEqual(fairStarts(game, averages), starts, why);
});

test("the averages of the profiles are by name, without those of players who have none", () => {
  const averages = lobbyAverages({
    attributes: {
      players: [
        { name: "Alex", recent_average: 60.5 },
        { name: "Sam", recent_average: null },
        { name: "", recent_average: 40 },
        null,
      ],
    },
  });
  assert.deepEqual([...averages], [["alex", 60.5]]);
  assert.deepEqual([...lobbyAverages(undefined)], []);
});

test("a fair start sets the scores, follows the players and the game, and goes back when off", () => {
  let choice = lobbyChange(fairChoice({ names: ["Alex", "Sam"] }), "toggle", "fair_start");
  assert.deepEqual([choice.fair_start, choice.starts], [true, [0, 250]]);
  assert.deepEqual(startGameData(choice).start_scores, [0, 250]);
  // − and + still change a score, and another option leaves it.
  choice = lobbyChange(choice, "lower", "1");
  choice = lobbyChange(choice, "toggle", "bull_off");
  choice = lobbyChange(choice, "legs", "1");
  assert.deepEqual(choice.starts, [0, 150]);
  // Another line-up works them out again, also with a player without an average.
  choice = lobbyChange(choice, "add", "Kim");
  assert.deepEqual(choice.starts, [0, 250, 380]);
  choice = lobbyChange(choice, "add", "Nobody");
  assert.deepEqual(choice.starts, [0, 250, 380, 0]);
  choice = lobbyChange(choice, "remove", "3");
  choice = lobbyChange(choice, "up", "1");
  assert.deepEqual([choice.players, choice.starts], [["Sam", "Alex", "Kim"], [250, 0, 380]]);
  choice = lobbyChange(choice, "game", "301");
  assert.deepEqual(choice.starts, [150, 0, 230]);
  // A game without start scores plays from nothing, and X01 from its share again.
  choice = lobbyChange(choice, "game", "cricket");
  assert.deepEqual(choice.starts, [0, 0, 0]);
  choice = lobbyChange(choice, "game", "501");
  assert.deepEqual(choice.starts, [250, 0, 380]);
  // Off, everybody plays the game's score, and no start scores go with the start.
  choice = lobbyChange(choice, "toggle", "fair_start");
  assert.deepEqual([choice.fair_start, choice.starts], [false, [0, 0, 0]]);
  assert.equal("start_scores" in startGameData(choice), false);
});

test("without a fair start a change of the line-up leaves the scores alone", () => {
  let choice = fairChoice({ names: ["Alex", "Sam"], starts: [301, 0] });
  choice = lobbyChange(choice, "add", "Kim");
  choice = lobbyChange(choice, "toggle", "teams");
  assert.deepEqual(choice.starts, [301, 0, 0]);
});

test("a fair start without averages leaves everybody at the game's score", () => {
  let choice = lobbyChoice({ game: "501", names: ["Alex", "Sam"], players: 2 }, ["501"]);
  choice = lobbyChange(choice, "toggle", "fair_start");
  assert.deepEqual(choice.starts, [0, 0]);
  assert.equal(botMatch(choice), null);
});

test("players who rest get no fair start and count for nobody", () => {
  let choice = fairChoice({ names: ["Lea", "Sam", "Kim", "Alex"], bot: 40 });
  // The bot takes the fourth seat, so Alex rests, and Kim is the strongest player.
  choice = lobbyChange(choice, "toggle", "fair_start");
  assert.deepEqual([choice.starts, choice.botStart], [[170, 330, 0, 0], 450]);
});

test("the bot plays a fair start by its level, and its score goes with the start", () => {
  let choice = lobbyChange(fairChoice({ names: ["Alex"] }), "bot", "add");
  choice = lobbyChange(choice, "toggle", "fair_start");
  // As strong as Alex, at the medium level.
  assert.deepEqual([choice.starts, choice.botStart], [[0], 0]);
  choice = lobbyChange(choice, "bot", "lower");
  choice = lobbyChange(choice, "bot", "lower");
  assert.deepEqual([choice.bot, choice.starts, choice.botStart], [40, [0], 330]);
  assert.deepEqual(startGameData(choice).start_scores, [0, 330]);
  choice = lobbyChange(choice, "bot", "raise");
  choice = lobbyChange(choice, "bot", "raise");
  choice = lobbyChange(choice, "bot", "raise");
  assert.deepEqual([choice.bot, choice.starts, choice.botStart], [70, [430], 0]);
  assert.deepEqual(startGameData(choice).start_scores, [430]);
  // Gone, it leaves the start score of its seat behind.
  choice = lobbyChange(choice, "bot", "remove");
  assert.deepEqual([choice.starts, choice.botStart], [[0], 0]);
  assert.deepEqual("start_scores" in startGameData(choice), false);
});

test("partners play a fair start from one score, by the average of both", () => {
  let choice = lobbyChange(fairChoice({ names: ["Alex", "Sam", "Kim", "Lea"], teams: true }), "toggle", "fair_start");
  // Alex and Kim average 52.5, Sam and Lea 22.5.
  assert.deepEqual(choice.starts, [0, 210, 0, 210]);
  assert.deepEqual(startGameData(choice).start_scores, [0, 210]);
  // − and + of either partner change the score of both.
  choice = lobbyChange(choice, "lower", "3");
  assert.deepEqual(choice.starts, [0, 110, 0, 110]);
  assert.deepEqual(startGameData(choice).start_scores, [0, 110]);
  // Alone, everybody plays from their own again.
  choice = lobbyChange(choice, "toggle", "teams");
  assert.deepEqual(choice.starts, [0, 250, 380, 130]);
  assert.deepEqual(startGameData(choice).start_scores, [0, 250, 380, 130]);
});

test("the bot as a partner counts by its level, and only the teams have a score", () => {
  const seats = fairChoice({ names: ["Alex", "Sam", "Kim"], teams: true, bot: 50 });
  const choice = lobbyChange(seats, "toggle", "fair_start");
  // Alex and Kim average 52.5, Sam and the bot 40.
  assert.deepEqual([choice.starts, choice.botStart], [[0, 380, 0], 380]);
  assert.deepEqual(startGameData(choice).start_scores, [0, 380]);
  // − and + of the player beside the bot change the score of the team; nobody else plays from it.
  const lower = lobbyChange(choice, "lower", "1");
  assert.deepEqual([lower.starts, lower.botStart], [[0, 280, 0], 280]);
  assert.deepEqual(startGameData(lower).start_scores, [0, 280]);
});

test("a team of four seated players stays a team while others rest", () => {
  const seats = fairChoice({ names: ["Alex", "Sam", "Kim", "Lea", "Max"], teams: true });
  const choice = lobbyChange(seats, "toggle", "fair_start");
  // Alex and Kim average 52.5, Sam and Lea 22.5, and Max does not count.
  assert.deepEqual(choice.starts.slice(0, 4), [0, 210, 0, 210]);
  const data = startGameData(choice);
  assert.deepEqual([data.players.length, data.start_scores, data.teams], [4, [0, 210], true]);
});

test("partners show the one score they play from", () => {
  const names = ["Alex", "Sam", "Kim", "Lea"];
  // Teams on: the first player of each team decides.
  let choice = lobbyChange(fairChoice({ names, starts: [401, 0, 301, 0] }), "toggle", "teams");
  assert.deepEqual(choice.starts, [401, 0, 401, 0]);
  assert.deepEqual(startGameData(choice).start_scores, [401, 0]);
  // A move changes who plays from which score, and the row says so.
  choice = lobbyChange(fairChoice({ names, teams: true, starts: [301, 0, 301, 0] }), "up", "1");
  assert.deepEqual(choice.starts, [0, 301, 0, 301]);
  assert.deepEqual(startGameData(choice).start_scores, [0, 301]);
  // − and + of the second partner move the team, too.
  choice = lobbyChange(choice, "raise", "2");
  assert.deepEqual(choice.starts, [601, 301, 601, 301]);
  assert.deepEqual(startGameData(choice).start_scores, [601, 301]);
});

test("the bot's stored start score shows again and goes back with the start", () => {
  const games = ["501"];
  let choice = lobbyChoice({ game: "501", names: ["Alex"], players: 1, bot: 60, starts: [0, 330] }, games);
  assert.equal(choice.botStart, 330);
  assert.deepEqual(startGameData(choice).start_scores, [0, 330]);
  // In a team, it plays from the score of the second team.
  const team = { game: "501", names: ["Alex", "Sam", "Kim"], players: 3, bot: 50, teams: true, starts: [0, 380, 0, 0] };
  choice = lobbyChoice(team, games);
  assert.equal(choice.botStart, 380);
  assert.deepEqual(startGameData(choice).start_scores, [0, 380]);
  // With every seat taken, the bot has the last one and a resting player none.
  choice = lobbyChoice({ game: "501", names: ["Alex", "Sam", "Kim", "Lea"], players: 4, bot: 50, starts: [0, 0, 0, 280] }, games);
  assert.equal(choice.botStart, 280);
  // Without a bot, nobody has its score.
  assert.equal(lobbyChoice({ game: "501", names: ["Alex"], players: 1, starts: [0, 330] }, games).botStart, 0);
});

test("the board's start scores of a team show for both partners", () => {
  const board = { game: "501", names: ["Alex", "Sam", "Kim", "Lea"], players: 4, teams: true, starts: [0, 210, 0, 0] };
  assert.deepEqual(lobbyChoice(board, ["501"]).starts, [0, 210, 0, 210]);
  const bot = { ...board, names: ["Alex", "Sam", "Kim"], players: 3, bot: 50 };
  assert.deepEqual(lobbyChoice(bot, ["501"]).starts, [0, 210, 0]);
  assert.deepEqual(lobbyChoice({ ...board, teams: false }, ["501"]).starts, [0, 210, 0, 0]);
});

test("a tournament goes by its whole field", () => {
  let choice = lobbyChange(fairChoice({ names: ["Alex", "Sam", "Kim"], bot: 80 }), "mode", "tournament");
  choice = lobbyChange(choice, "toggle", "fair_start");
  // A tournament has no bot.
  assert.deepEqual([choice.starts, choice.botStart], [[0, 250, 380], 0]);
});

test("the bot's level for the players goes in the bot's steps and within its levels", () => {
  const level = (averages, names = ["Alex"]) => botMatch(fairChoice({ names }, new Map(averages)));
  assert.equal(level([["alex", 64]]), 60);
  assert.equal(level([["alex", 65]]), 70);
  assert.equal(level([["alex", 12]]), 20);
  assert.equal(level([["alex", 140]]), 120);
  assert.equal(level([]), null);
  // With several players, what they average; a player without an average doesn't count.
  assert.equal(
    level(
      [
        ["alex", 60],
        ["sam", 40],
      ],
      ["Alex", "Sam", "Kim"]
    ),
    50
  );
  let choice = lobbyChange(fairChoice({ names: ["Alex"] }), "bot", "add");
  assert.equal(lobbyChange({ ...choice, bot: 40 }, "bot", "match").bot, 60);
  // Without a suggestion, the bot stays.
  choice = lobbyChange({ ...choice, bot: 40, averages: new Map() }, "bot", "match");
  assert.equal(choice.bot, 40);
});

test("the new game screen offers a fair start, shows its scores and says who has none", () => {
  const { hass, card } = setup({
    ...PLAYERS_AVERAGES,
    "select.practice_game": { state: "501", attributes: { options: OPTIONS } },
  });
  withNames(hass, ["Alex", "Sam"]);
  card.hass = { ...hass };
  tap(card, ".lobby-toggle");
  assert.deepEqual(shownStarts(card), ["501", "501"]);
  assert.equal(text(card, '[data-value="fair_start"]'), "Fair start");
  lobbyTap(card, "toggle", "fair_start");
  assert.deepEqual(options(card).at(-1), ["fair_start", "true"]);
  assert.deepEqual(shownStarts(card), ["501", "250"]);
  assert.equal($$(card, ".lobby-start.own").length, 1);
  assert.equal($(card, ".lobby-hint"), null);
  // A guest has no history.
  lobbyTap(card, "guest");
  assert.deepEqual(shownStarts(card), ["501", "250", "501"]);
  assert.equal(text(card, ".lobby-hint"), "Players without X01 legs yet start from the game's score.");
  lobbyTap(card, "remove", "2");
  tap(card, ".lobby .start");
  const [[, , data]] = started(hass);
  assert.deepEqual(data.start_scores, [0, 250]);
});

test("a game without start scores offers no fair start, and says nothing about it", () => {
  const { card } = setup();
  tap(card, ".lobby-toggle");
  lobbyTap(card, "toggle", "fair_start");
  lobbyTap(card, "game", "cricket");
  assert.deepEqual(options(card).map(([option]) => option), ["bull_off"]);
  assert.equal($(card, ".lobby-hint"), null);
});

test("a tournament whose game the board doesn't have works out the scores of the game it plays", () => {
  const tournament = {
    "select.tournament_game": { state: "501", attributes: { options: ["501"] } },
    "select.tournament_format": { state: "round_robin", attributes: { options: ["round_robin"] } },
    ...PLAYERS_AVERAGES,
    "select.practice_game": { state: "301", attributes: { options: OPTIONS } },
  };
  const { card } = setup(tournament);
  tap(card, ".lobby-toggle");
  lobbyTap(card, "toggle", "fair_start");
  assert.deepEqual(shownStarts(card), ["301", "150"]);
  lobbyTap(card, "mode", "tournament");
  assert.deepEqual(shownStarts(card), ["501", "250"]);
});

test("the bot's row suggests the level of the players and shows a fair start of its own", () => {
  const { hass, card } = setup({
    ...PLAYERS_AVERAGES,
    "number.practice_players": "1",
    "number.practice_bot_level": "40",
  });
  withNames(hass, ["Alex"]);
  card.hass = { ...hass };
  tap(card, ".lobby-toggle");
  assert.equal(text(card, ".bot-match"), "At my level: 60");
  assert.equal($(card, ".lobby-from"), null);
  lobbyTap(card, "toggle", "fair_start");
  assert.equal(text(card, ".lobby-from"), "from 330");
  // Tapped, the bot plays at that level, and so as strong as Alex from the same score.
  lobbyTap(card, "bot", "match");
  assert.equal(text(card, ".lobby-player.bot .lobby-start b"), "60");
  assert.equal($(card, ".bot-match"), null);
  assert.equal($(card, ".lobby-from"), null);
  assert.equal(text(card, ".said"), "Bot 60");
});

// axe-core, the engine of the accessibility check in a real browser, runs its rules that need
// no layout here too: the names of the buttons and their pressed states.
test("the new game screen with a fair start and the bot's level passes axe-core's WCAG 2.1 A and AA rules", async () => {
  window.eval(readFileSync(new URL("../../node_modules/axe-core/axe.min.js", import.meta.url), "utf8"));
  const { hass, card } = setup({
    ...PLAYERS_AVERAGES,
    "number.practice_players": "1",
    "number.practice_bot_level": "40",
  });
  withNames(hass, ["Alex"]);
  card.hass = { ...hass };
  tap(card, ".lobby-toggle");
  lobbyTap(card, "toggle", "fair_start");
  const result = await window.axe.run($(card, ".lobby"), { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] });
  assert.deepEqual(Array.from(result.violations, (rule) => rule.id), []);
  assert.ok(Array.from(result.passes, (rule) => rule.id).includes("button-name"));
});
