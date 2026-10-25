// Hostile text never turns into markup: player names, attributes, device names, answers and
// card options stay text in every card, view, editor and the dashboard of the strategy (#490).
//
// The cards build their markup from template strings and escape each text that goes into it.
// Text reaches them from places a user does not fully control: names from the online bridge,
// voice commands and the Board Manager, friendly names and the names of other boards. A single
// text that slips through unescaped would run script in Home Assistant with the user's login.
// So these tests take the states of real games, those the integration recorded for the demo of
// the website and a few of the tests of each view, and turn their texts hostile: every string
// of every state the card reads, the names of the board, the answers of Home Assistant and the
// card's options, replaced by markup or with markup after it. Then they look at everything the
// card shows, also behind each of its buttons, for any element, attribute or link that the
// markup made.
//
// The payloads make markers that no card makes itself, an hd-hostile element, a data-hostile
// attribute and an event handler, rather than comparing the card with one that shows harmless
// text: harmless text takes other turns where a card parses it, as the lenient Date.parse of V8
// does, and its markup then differs without any markup of the text.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import fc from "fast-check";

import { Replay } from "../../docs/demo/demo.js";
import { READY, camera, loadCards, makeHass, settle, window } from "./dom.mjs";

const { dashboardStrategy, escapeHtml } = await loadCards();

// Markup that leaves every place where a card writes text at once: the text, an attribute in
// either quotes or none, a list of options, a text field, a style and a title.
const POLYGLOT = `x '"></option></select></textarea></style></title><svg onload=alert(1)>`;
// And markup for one place each: the text, the attributes, a link and a comment.
const LINK = "javascript:alert(1)";
const PAYLOADS = [
  POLYGLOT,
  "<img src=x onerror=alert(1)>",
  "'><hd-hostile></hd-hostile>",
  '" data-hostile="1',
  "' data-hostile='1",
  "x data-hostile=1",
  LINK,
  "<!--hostile-->",
];

// Elements that run or load something, and the marker element of the payloads.
const FORBIDDEN = new Set(["script", "iframe", "frame", "object", "embed", "base", "meta", "link", "hd-hostile"]);
// Attributes whose value a browser opens or runs as an address.
const ADDRESSES = new Set(["href", "src", "xlink:href", "action", "formaction", "poster", "data", "srcdoc"]);

// What markup made in a part of the page and in every shadow root inside it.
function markup(root) {
  const found = [];
  const walk = (parent) => {
    for (const node of parent.childNodes) {
      if (node.nodeType === window.Node.COMMENT_NODE && node.data.includes("hostile")) found.push("<!--hostile-->");
      if (node.nodeType !== window.Node.ELEMENT_NODE) continue;
      if (FORBIDDEN.has(node.localName)) found.push(`<${node.localName}>`);
      for (const name of node.getAttributeNames()) {
        if (/^on/i.test(name) || name === "data-hostile") found.push(`<${node.localName} ${name}>`);
        if (ADDRESSES.has(name) && /^\s*javascript:/i.test(node.getAttribute(name))) {
          found.push(`<${node.localName} ${name}="javascript:">`);
        }
      }
      walk(node);
      if (node.shadowRoot) walk(node.shadowRoot);
    }
  };
  walk(root);
  return found;
}

test("the check finds markup that a text made in every place a card writes text", () => {
  const places = {
    text: (value) => `<p>${value}</p>`,
    "double-quoted attribute": (value) => `<p title="${value}"></p>`,
    "single-quoted attribute": (value) => `<p title='${value}'></p>`,
    "unquoted attribute": (value) => `<p title=${value}></p>`,
    link: (value) => `<a href="${value}">more</a>`,
    style: (value) => `<style>p { color: ${value}; }</style>`,
    title: (value) => `<svg><title>${value}</title></svg>`,
    option: (value) => `<select><option>${value}</option></select>`,
    "text field": (value) => `<textarea>${value}</textarea>`,
  };
  const found = (html) => {
    const part = document.createElement("div");
    part.innerHTML = html;
    return markup(part);
  };
  for (const [place, write] of Object.entries(places)) {
    assert.deepEqual(found(write(POLYGLOT)), ["<svg onload>"], place);
    // Escaped, the payloads stay text, in quotes: a space ends an unquoted attribute, and a
    // link needs more than escaping, as pictureUrl checks the address of a picture.
    for (const payload of PAYLOADS) {
      if (!["link", "unquoted attribute"].includes(place)) {
        assert.deepEqual(found(write(escapeHtml(payload))), [], `${payload} in a ${place}`);
      }
    }
  }
  assert.deepEqual(found(places["unquoted attribute"](escapeHtml("x data-hostile=1"))), ["<p data-hostile>"]);
  assert.deepEqual(found(places.link(escapeHtml("javascript:alert(1)"))), ['<a href="javascript:">']);
});

// Worlds ---------------------------------------------------------------------------

// A world: what a card sees of Home Assistant, the states, the registries of the board and
// what Home Assistant answers. The recording plays now, as on the website.
const NOW = Date.now();
const RECORDING = JSON.parse(readFileSync(new URL("../../docs/demo/timeline.json", import.meta.url), "utf8"));
const replay = new Replay(RECORDING, { now: () => NOW, later: () => null, cancel: () => {} });

// The worlds after each step of the recording, as the demo replays them.
const RECORDED = RECORDING.steps.map((_, step) => {
  replay.seek(step);
  return {
    states: replay.states,
    devices: { [RECORDING.device.id]: RECORDING.device },
    entities: RECORDING.entities,
    answers: { positions: replay.positions, error: "Not in the recording" },
  };
});

function made(options) {
  const { states, devices, entities } = makeHass(options);
  return { states, devices, entities, answers: { positions: {}, error: "Not in the test" } };
}

// Home Assistant as a card sees it, with an administrator, who also gets the menus of the profiles.
function hassOf(world, read) {
  return {
    language: "en",
    locale: { language: "en" },
    states: read ? new Proxy(world.states, { get: (states, id) => (read.add(id), states[id]) }) : world.states,
    devices: world.devices,
    entities: world.entities,
    user: { id: "admin", name: "Admin", is_admin: true },
    callService: () => Promise.resolve(),
    async callWS(message) {
      if (message.type !== "homedarts/positions") throw new Error(world.answers.error);
      return world.answers.positions[message.player ?? ""] ?? { known: false, positions: [], spread: [] };
    },
  };
}

// The recording with every player linked to a person and the picture of the person.
function withPersons(world) {
  const profiles = Object.values(world.states).find((state) => state.entity_id.endsWith("_player_profiles"));
  const players = profiles.attributes.players.map((player, index) => ({ ...player, person: `person.p${index}` }));
  const persons = Object.fromEntries(
    players.map((player, index) => [
      player.person,
      {
        entity_id: player.person,
        state: "home",
        attributes: { friendly_name: player.name, entity_picture: `/api/image/serve/p${index}/512x512` },
      },
    ])
  );
  const linked = { ...profiles, attributes: { ...profiles.attributes, players } };
  return { ...world, states: { ...world.states, ...persons, [profiles.entity_id]: linked } };
}

// The recording with darts entered by hand and a camera that sees nothing.
function withManualEntry(world) {
  const states = { ...world.states };
  for (const [id, state] of Object.entries(states)) {
    if (/practice_manual_entry|camera_1_problem$|camera_problem$/.test(id)) states[id] = { ...state, state: "on" };
  }
  return { ...world, states };
}

// What the recording does not reach, as the tests of these views set it up: a team match, a
// party game with lives, a round robin on two boards, and the board PC with its cameras.
const at = (seconds) => new Date(NOW + seconds * 1000).toISOString();
const TEAM_MATCH = {
  ...READY,
  "sensor.practice_remaining": {
    state: "100",
    attributes: {
      game: 501,
      player: 3,
      name: "Kim",
      checkout: "T20 D20",
      legs_to_win: 2,
      teams: [
        { team: 1, name: "Alex & Kim", players: [1, 3] },
        { team: 2, name: "Sam & Lea", players: [2, 4] },
      ],
      scores: ["Alex", "Sam", "Kim", "Lea"].map((name, index) => ({
        player: index + 1,
        name,
        remaining: [100, 301][index % 2],
        start: 501,
        team: (index % 2) + 1,
        legs: 1 - (index % 2),
        sets: 0,
        average: 50 + index,
      })),
    },
  },
  "sensor.local_visit_score": { state: "60", attributes: { throws: [{ segment: { name: "T20" } }] } },
};
const KILLER = {
  ...READY,
  "sensor.practice_remaining": {
    state: "3",
    attributes: {
      game: "killer",
      player: 1,
      name: "Alex",
      legs_to_win: 2,
      sets_to_win: 2,
      scores: [
        { player: 1, name: "Alex", number: 7, lives: 3, killer: true, legs: 1, sets: 0 },
        { player: 2, name: "Sam", number: 12, lives: 0, killer: false, legs: 0, sets: 1 },
      ],
    },
  },
};
const fixture = (number, stage, players, extra = {}) => ({
  match: number,
  round: 1,
  stage,
  players,
  winner: null,
  bye: false,
  legs: [0, 0],
  sets: [0, 0],
  ended: null,
  ...extra,
});
const standing = (position, name, won, lost) => ({
  position,
  name,
  played: won + lost,
  won,
  lost,
  legs_for: won * 2,
  legs_against: lost * 2,
  leg_difference: (won - lost) * 2,
  points: won * 2,
  average: 50.5,
});
const FIRST = fixture(1, "round_1", ["Kim", "Sam"], { winner: "Sam", legs: [1, 2], sets: [0, 1], ended: at(-600) });
const SECOND = fixture(2, "round_2", ["Alex", "Kim"], { round: 2 });
const ROUND_ROBIN = {
  ...READY,
  "sensor.tournament": {
    state: "round_2",
    attributes: {
      status: "waiting",
      format: "round_robin",
      game: 501,
      legs_to_win: 2,
      sets_to_win: 1,
      players: ["Alex", "Sam", "Kim"],
      round: 2,
      rounds: 3,
      matches_played: 1,
      matches_total: 3,
      current: null,
      next: SECOND,
      last_result: { ...FIRST, average: [45.5, 60.25] },
      pause: 10,
      summary: 5,
      next_at: at(600),
      winner: null,
      started: at(-900),
      fixtures: [FIRST, SECOND, fixture(3, "round_3", ["Sam", "Alex"], { round: 3 })],
      standings: [standing(1, "Sam", 1, 0), standing(2, "Alex", 0, 0), standing(3, "Kim", 0, 1)],
      board: 2,
      boards: [
        { board: 1, name: "Garage", match: 2, players: ["Alex", "Kim"], next_at: null },
        { board: 2, name: "Cellar", match: null, players: [], next_at: at(900) },
      ],
      ends_at: at(3600),
    },
  },
};
const BOARD_PC = {
  ...READY,
  "button.restart": "unknown",
  "binary_sensor.cloud_link": "on",
  "sensor.cpu_usage": "12.4",
  "sensor.memory_usage": { state: "45.2", attributes: { unit_of_measurement: "%" } },
  "sensor.detection_fps": "24.5",
  "update.board_software": {
    state: "on",
    attributes: {
      installed_version: "1.4.2",
      latest_version: "1.5.0",
      title: "Board Manager",
      release_summary: "Faster detection",
    },
  },
  "sensor.host_os": "Ubuntu 22.04.4 LTS",
  "sensor.host_processor": "Intel(R) Core(TM) i3-9100T CPU @ 3.10GHz",
  "sensor.vision_version": "0.9.1",
};
const CAMERAS = [camera(1, { problem: "on" }), camera(2, { fps: "29.97" })];

// The cards with the options that show the most of them, and their title.
const CARDS = {
  "homedarts-scoreboard-card": [{ keypad: true, caller: true }, { overlay: "chroma", overlay_layout: "lower_third" }],
  "homedarts-card": [{ keypad: true }, { layout: "vertical" }],
  "homedarts-training-card": [{}, { mode: "aim", player: "Kim" }, { mode: "positions", player: "Alex" }],
  "homedarts-players-card": [{ export: true }],
  "homedarts-status-card": [{}],
  "homedarts-doubles-card": [{}, { player: "Sam" }],
  "homedarts-leaderboard-card": [{ period: "week" }, { period: "all" }],
};
const configs = (type) => CARDS[type].map((options) => ({ title: "Darts", ...options }));

async function show(type, config, world, read) {
  const card = document.createElement(type);
  card.setConfig({ type: `custom:${type}`, device_id: Object.keys(world.devices)[0], ...config });
  card.hass = hassOf(world, read);
  document.body.append(card);
  await settle();
  await settle();
  return card;
}

// The steps of the recording that show a card something that the steps before did not: one
// of each view, without a hundred alike moves of the same game. A step that changes none of
// the states the card read the step before shows the same.
async function viewsOf(type, config, steps = RECORDED.keys()) {
  const views = [];
  const seen = new Set();
  let read = null;
  for (const step of steps) {
    if (read && !Object.keys(RECORDING.steps[step].states).some((id) => read.has(id))) continue;
    read = new Set();
    const card = await show(type, config, RECORDED[step], read);
    const classes = [...card.shadowRoot.querySelectorAll("[class]")].flatMap((element) => [...element.classList]);
    card.remove();
    if (classes.some((name) => !seen.has(name))) views.push(step);
    for (const name of classes) seen.add(name);
  }
  return views;
}

// Each card in each view of the recording with each of its options, and with the variations
// and fixtures of what the recording does not show.
const SCENARIOS = [];
const last = RECORDED.at(-1);
for (const type of Object.keys(CARDS)) {
  // The other options show their own parts in fewer of these views.
  const [standard, ...others] = configs(type);
  const steps = await viewsOf(type, standard);
  for (const config of [standard, ...others]) {
    const views = config === standard ? steps : await viewsOf(type, config, steps);
    SCENARIOS.push(...views.map((step) => ({ name: `step ${step}`, step, type, config, world: RECORDED[step] })));
  }
  SCENARIOS.push({ name: "linked persons", type, config: configs(type)[0], world: withPersons(last) });
  SCENARIOS.push({ name: "manual entry", type, config: configs(type)[0], world: withManualEntry(last) });
}
for (const [name, options] of Object.entries({
  "team match": { states: TEAM_MATCH },
  killer: { states: KILLER },
  "round robin": { states: ROUND_ROBIN },
  "board PC": { states: BOARD_PC, cameras: CAMERAS },
})) {
  for (const type of ["homedarts-scoreboard-card", "homedarts-card", "homedarts-status-card"]) {
    SCENARIOS.push({ name, type, config: configs(type)[0], world: made(options) });
  }
}

// Hostile text ------------------------------------------------------------------------

// Every text in a value by its path, and the names of what an attribute keeps by name, such
// as the beds of hits or the games of fewest darts, which are paths of five and more.
function texts(value, path) {
  if (typeof value === "string") return [{ path }];
  if (Array.isArray(value)) return value.flatMap((item, index) => texts(item, [...path, index]));
  if (!value || typeof value !== "object") return [];
  return Object.entries(value).flatMap(([key, item]) => [
    ...(path.length >= 4 ? [{ path: [...path, key], key: true }] : []),
    ...texts(item, [...path, key]),
  ]);
}

// The texts that reach the card: of the states it reads, but not their entity ids, the names
// of the board, the answers of Home Assistant and the card's options.
async function textsOf({ type, config, world }) {
  const read = new Set();
  (await show(type, config, world, read)).remove();
  return [
    ...[...read]
      .filter((id) => world.states[id])
      .flatMap((id) => texts(world.states[id], ["states", id]).filter(({ path }) => path[2] !== "entity_id")),
    ...texts(world.devices, ["devices"]),
    ...texts(world.answers, ["answers"]),
    ...texts(config, ["config"]),
  ];
}

// A copy of the world and the options with the payload instead of each text, or after it.
// The names of what an attribute keeps by name get the payload only after them, so that
// they stay apart.
function hostile({ world, config }, positions, payload, after) {
  const copy = structuredClone({ ...world, config });
  const parent = (path) => path.slice(0, -1).reduce((node, key) => node[key], copy);
  for (const { path } of positions.filter((position) => !position.key)) {
    const node = parent(path);
    node[path.at(-1)] = after ? `${node[path.at(-1)]}${payload}` : payload;
  }
  // The deepest names first, so that the paths of the others stay as they are.
  const names = positions.filter((position) => position.key).sort((a, b) => b.path.length - a.path.length);
  for (const { path } of after ? names : []) {
    const node = parent(path);
    const entries = Object.entries(node);
    for (const [key] of entries) delete node[key];
    for (const [key, item] of entries) node[key === path.at(-1) ? `${key}${payload}` : key] = item;
  }
  const { config: options, ...rest } = copy;
  return { world: rest, config: options };
}

// The text at a path of the world or the options.
const textAt = ({ world, config }, path) => path.reduce((node, key) => node[key], { ...world, config });

// The names of the players of a world: of the profiles, the games and the tournament.
function playersOf(world) {
  const names = new Set();
  const collect = (value, key) => {
    if (typeof value === "string" && (key === "name" || key === "players")) names.add(value);
    else if (Array.isArray(value)) value.forEach((item) => collect(item, key));
    else if (value && typeof value === "object") for (const [name, item] of Object.entries(value)) collect(item, name);
  };
  for (const state of Object.values(world.states)) collect(state.attributes);
  return [...names].filter((name) => name.trim());
}

// A copy of the world and the options with one player renamed wherever the name stands, in
// any case, as the integration and the cards tell players apart: the profile, the scores,
// the matches, the tournament and the persons stay linked to the new name.
function renamed({ world, config }, name, to) {
  const same = (text) => typeof text === "string" && text.trim().toLowerCase() === name.trim().toLowerCase();
  const rename = (value) => {
    if (same(value)) return to;
    if (Array.isArray(value)) return value.map(rename);
    if (!value || typeof value !== "object") return value;
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [same(key) ? to : key, rename(item)]));
  };
  const { config: options, ...rest } = rename({ ...world, config });
  return { world: rest, config: options };
}

// Controls a user can reach: not those of a closed dialog or of a hidden part, and no link,
// which leads away from the card.
const CONTROLS = [
  "button, summary, input, select, [data-action], [tabindex]",
  "[role=button], [role=menuitem], [role=tab], [role=option]",
].join(", ");
const reachable = (element) =>
  element.isConnected && !element.disabled && !element.closest("dialog:not([open]), [hidden]");
const signature = (element) =>
  `${element.localName}.${element.className}[${[...element.attributes]
    .filter(({ name }) => name.startsWith("data-"))
    .map(({ name, value }) => `${name}=${value}`)}]${element.textContent.trim().slice(0, 24)}`;

// The controls a user can tap now, by their signature.
function controls(card) {
  const found = new Map();
  for (const control of card.shadowRoot.querySelectorAll(CONTROLS)) {
    if (reachable(control) && !found.has(signature(control))) found.set(signature(control), control);
  }
  return found;
}

// What markup the card shows with the world, and with taps: as a user explores the card,
// every control once, and what a tap opened, such as the new game screen, the menu of a
// profile and its dialogs, from a new card along the taps that led there. A tap that shows
// nothing new goes on in the same card. Each control is tapped once for the same card and
// options, in the first view that offers it: explored keeps them, by what they show besides
// the payload and numbers.
async function shown({ type, config, world }, { explored = null, payload = "" } = {}) {
  const found = [];
  const paths = [[]];
  const first = (name) => {
    // Alike controls of another view differ in their numbers at most, such as scores.
    const key = [type, JSON.stringify(config), name.replaceAll(payload, "…").replace(/\d+/g, "#")].join(" ");
    const unexplored = !explored.has(key);
    explored.add(key);
    return unexplored;
  };
  while (paths.length) {
    const path = paths.shift();
    const card = await show(type, config, world);
    for (const name of path) {
      controls(card).get(name)?.click();
      await settle();
    }
    found.push(...markup(card.shadowRoot).map((made) => (path.length ? `${made} after ${path.join(" > ")}` : made)));
    const offered = explored ? [...controls(card).keys()].filter(first) : [];
    for (const name of offered) {
      const before = controls(card);
      // A tap before this one took the control away: from a new card, then.
      if (!before.has(name)) {
        paths.push([...path, name]);
        continue;
      }
      before.get(name).click();
      await settle();
      found.push(...markup(card.shadowRoot).map((made) => `${made} after ${[...path, name].join(" > ")}`));
      if ([...controls(card).keys()].some((other) => !before.has(other))) paths.push([...path, name]);
    }
    card.remove();
  }
  return found;
}

const label = ({ type, name, config }) => `${type} at ${name} with ${JSON.stringify(config)}`;

test("every card has its views from the recording, and the scoreboard one of each game", async () => {
  for (const type of Object.keys(CARDS)) {
    assert.ok(SCENARIOS.filter((scenario) => scenario.type === type && "step" in scenario).length >= 2, type);
  }
  const steps = SCENARIOS.filter(({ type }) => type === "homedarts-scoreboard-card").map(({ step }) => step);
  const chapters = RECORDING.chapters.map(({ step }) => step);
  for (const [index, start] of chapters.entries()) {
    const end = chapters[index + 1] ?? RECORDING.steps.length;
    assert.ok(steps.some((step) => step >= start && step < end), RECORDING.chapters[index].key);
  }
  // The fixtures show what they are for.
  const views = {
    "team match": ["homedarts-scoreboard-card", ".player .members"],
    killer: ["homedarts-scoreboard-card", ".big.lives"],
    "round robin": ["homedarts-scoreboard-card", ".standings"],
    "board PC": ["homedarts-status-card", ".camera.problem"],
  };
  for (const [name, [type, selector]] of Object.entries(views)) {
    const { config, world } = SCENARIOS.find((scenario) => scenario.type === type && scenario.name === name);
    const card = await show(type, config, world);
    assert.ok(card.shadowRoot.querySelector(selector), `${name}: ${selector}`);
    card.remove();
  }
  // The persons lend the players their pictures, on the scoreboard and the players card.
  for (const type of ["homedarts-scoreboard-card", "homedarts-players-card"]) {
    const linked = (scenario) => scenario.type === type && scenario.name === "linked persons";
    const { config, world } = SCENARIOS.find(linked);
    const card = await show(type, config, world);
    assert.ok(card.shadowRoot.querySelector("img.avatar[src^='/api/image/serve/']"), type);
    card.remove();
  }
});

test("every text of every card is hostile at once, in every view and behind every control", async () => {
  const explored = new Set();
  let rotation = 0;
  for (const scenario of SCENARIOS) {
    const positions = await textsOf(scenario);
    // The payload for every place instead of the texts, and after them with every control:
    // so the names of the players stay apart, and the menus of their profiles open.
    for (const after of [false, true]) {
      const world = hostile(scenario, positions, POLYGLOT, after);
      const found = await shown({ ...scenario, ...world }, after ? { explored, payload: POLYGLOT } : {});
      assert.deepEqual(found, [], `${label(scenario)}: ${after ? "after" : "instead of"} the texts`);
    }
    // Two of the payloads for one place each in turn.
    const others = PAYLOADS.filter((payload) => payload !== POLYGLOT && payload !== LINK);
    for (const after of [false, true]) {
      const payload = others[rotation++ % others.length];
      const world = hostile(scenario, positions, payload, after);
      assert.deepEqual(await shown({ ...scenario, ...world }), [], `${label(scenario)}: ${payload}`);
    }
    // Every address, such as the picture of a person, a link to script, while the texts that
    // lead to it, such as the link of a profile to its person, stay as they are.
    const addresses = positions.filter(({ path, key }) => !key && /^(\/|https?:)/i.test(textAt(scenario, path)));
    const world = hostile(scenario, addresses, LINK, false);
    assert.deepEqual(await shown({ ...scenario, ...world }), [], `${label(scenario)}: ${LINK}`);
  }
});

test("a hostile player name shows as text wherever the player appears", async () => {
  // The controls with the payload for every place, which the first player of each view gets.
  const explored = new Set();
  let renames = 0;
  for (const scenario of SCENARIOS) {
    // Every player of each view, the first with every control.
    for (const [index, name] of playersOf(scenario.world).entries()) {
      const payload = index ? PAYLOADS[renames % PAYLOADS.length] : POLYGLOT;
      // The new name alone, and the old one with the payload after it, as the online
      // bridge accepts any printable name of up to 50 characters.
      const to = renames++ % 2 ? `${name}${payload}` : payload;
      const world = renamed(scenario, name, to);
      const found = await shown({ ...scenario, ...world }, index ? {} : { explored, payload: to });
      assert.deepEqual(found, [], `${label(scenario)}: ${to}`);
    }
  }
  assert.ok(renames > SCENARIOS.length);
});

test("any few texts of any view are hostile", async () => {
  const cases = [];
  for (const scenario of SCENARIOS) cases.push({ scenario, positions: await textsOf(scenario) });
  // A failure names the view by its number, the texts by their paths.
  await fc.assert(
    fc.asyncProperty(
      fc
        .nat({ max: cases.length - 1 })
        .chain((view) =>
          fc.tuple(
            fc.constant(view),
            fc.subarray(cases[view].positions, { minLength: 1, maxLength: 6 }),
            fc.constantFrom(...PAYLOADS),
            fc.boolean()
          )
        ),
      async ([view, positions, payload, after]) => {
        const { scenario } = cases[view];
        const world = hostile(scenario, positions, payload, after);
        assert.deepEqual(await shown({ ...scenario, ...world }), [], label(scenario));
      }
    ),
    { numRuns: 200 }
  );
});

// The dashboard and the editors ----------------------------------------------------------

// Every field of a form, also those inside grids and expandable sections.
const formFields = (schema) => schema.flatMap((field) => (field.schema ? formFields(field.schema) : [field]));

test("the dashboard of the strategy hands hostile names only to cards that keep them text", async () => {
  const positions = texts(last.devices, ["devices"]);
  for (const [index, payload] of PAYLOADS.entries()) {
    const { world, config } = hostile({ world: last, config: { title: payload } }, positions, payload, index % 2 === 1);
    const cards = [];
    const collect = (value) => {
      if (Array.isArray(value)) value.forEach(collect);
      if (!value || typeof value !== "object" || Array.isArray(value)) return;
      if (String(value.type).startsWith("custom:homedarts-")) cards.push(value);
      // A markdown card would show its content as markup.
      if (value.type === "markdown") assert.ok(!value.content.includes(payload), value.content);
      Object.values(value).forEach(collect);
    };
    collect(dashboardStrategy(hassOf(world), config));
    assert.deepEqual(new Set(cards.map(({ type }) => type.slice("custom:".length))), new Set(Object.keys(CARDS)));
    for (const { type, ...options } of cards) {
      const card = { type: type.slice("custom:".length), config: options, world };
      assert.deepEqual(await shown(card), [], `${card.type} of the dashboard: ${payload}`);
    }
  }
});

test("the editors hand hostile text to the form of Home Assistant as data and make no markup", async () => {
  // Home Assistant's form, which draws its fields from the schema and the data.
  if (!customElements.get("ha-form")) customElements.define("ha-form", class extends window.HTMLElement {});
  const games = Object.values(last.states).find((state) => state.entity_id.endsWith("_practice_game"));
  for (const payload of PAYLOADS) {
    const { world, config } = hostile(
      { world: last, config: { title: payload, device_id: RECORDING.device.id } },
      [...texts(games, ["states", games.entity_id]), ...texts(last.devices, ["devices"])],
      payload,
      false
    );
    const editor = await customElements.get("ll-strategy-dashboard-homedarts").getConfigElement();
    editor.setConfig(config);
    editor.hass = hassOf(world);
    document.body.append(editor);
    await settle();
    assert.deepEqual(
      [...editor.children].map((child) => child.localName),
      ["ha-form"]
    );
    assert.deepEqual(markup(editor), []);
    assert.equal(editor.querySelector("ha-form").data.title, payload);
    editor.remove();
    // A card's form refuses an option it cannot offer with a message, which Home Assistant
    // shows as text, with the option written as JSON in it.
    const choices = Object.keys(CARDS).flatMap((type) => {
      const form = customElements.get(type).getConfigForm();
      const fields = formFields(form.schema).filter(({ selector }) => selector.select && !selector.select.custom_value);
      return fields.map((field) => [type, form, field]);
    });
    assert.ok(new Set(choices.map(([type]) => type)).size >= 4);
    for (const [type, form, field] of choices) {
      assert.throws(
        () => form.assertConfig({ [field.name]: payload }),
        (error) => error instanceof Error && error.message.includes(JSON.stringify(payload)),
        `${type} ${field.name}`
      );
    }
  }
});
