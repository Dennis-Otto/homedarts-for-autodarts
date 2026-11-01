// The players card in a browser DOM: profiles, head-to-head records, recent matches and escaping.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { $, $$, loadCards, makeHass, mount, settle, text, update, window } from "./dom.mjs";

await loadCards();

const ALEX = {
  name: "Alex",
  legs_played: 20,
  legs_won: 12,
  matches_played: 5,
  matches_won: 3,
  average: 61.25,
  first_9_average: 70.1,
  checkout_rate: 31.3,
  mpr: 2.4,
  highest_visit: 140,
  highest_checkout: 121,
  best_mpr: 3.1,
  fewest_darts: { 501: 18, 301: 12 },
};
const LEA = { name: "Lea", legs_played: 8, legs_won: 3, matches_played: 2, matches_won: 1 };
const profiles = (...players) => ({
  "sensor.player_profiles": { state: String(players.length), attributes: { players } },
});
const lastMatch = (attributes) => ({
  "sensor.last_match": {
    state: "2026-09-26T20:00:00+00:00",
    attributes: { game: "killer", winner: null, matches: [], head_to_head: [], ...attributes },
  },
});
// Matches as the integration keeps them: the format, the winner, and every
// player's legs of the final set, sets and legs of the whole match.
const MATCHES = [
  {
    ended: "2026-09-26T20:00:00+00:00",
    game: "killer",
    legs_to_win: 1,
    sets_to_win: 1,
    winner: 2,
    players: [
      { name: "Alex", legs: 0, sets: 0, match_legs: 0, points: 0 },
      { name: null, legs: 1, sets: 1, match_legs: 1, points: 0 },
    ],
  },
  {
    ended: "later",
    game: 501,
    legs_to_win: 3,
    sets_to_win: 1,
    winner: 1,
    players: [
      { name: "Lea", legs: 3, sets: 1, match_legs: 3, average: 61.2 },
      { name: "Alex", legs: 2, sets: 0, match_legs: 2, average: 58.3 },
    ],
  },
  {
    ended: "2026-09-25T19:00:00+00:00",
    game: "cricket",
    legs_to_win: 2,
    sets_to_win: 2,
    winner: 2,
    players: [
      { name: "Alex", legs: 1, sets: 1, match_legs: 3, mpr: 2.1 },
      { name: "Sam", legs: 2, sets: 2, match_legs: 4, mpr: 2.4 },
    ],
  },
  // Up to version 1.5, the winner lost the legs of the deciding set again.
  {
    ended: "2026-09-24T19:00:00+00:00",
    game: 301,
    legs_to_win: 3,
    sets_to_win: 1,
    winner: 1,
    players: [
      { name: "Lea", legs: 0, sets: 1 },
      { name: "Alex", legs: 2, sets: 0 },
      { name: "Kim" },
    ],
  },
  { ended: "2026-09-23T19:00:00+00:00", game: null, winner: null, players: [] },
];
const setup = (states, config = {}, options = {}) => {
  const hass = makeHass({ states, ...options });
  return { hass, card: mount("homedarts-players-card", hass, config) };
};
const rows = (profile) =>
  [...profile.querySelectorAll("dt")].map((term) => [term.textContent, term.nextElementSibling.textContent]);

test("the players card shows every profile with its statistics and bests", () => {
  const { card } = setup({ ...profiles(ALEX, LEA), ...lastMatch({}) });
  assert.equal(text(card, ".title"), "Players");
  assert.equal(text(card, ".count"), "2");
  assert.equal($(card, ".empty").hidden, true);
  const [alex, lea] = $$(card, ".profile");
  assert.equal(alex.querySelector(".profile-name").textContent, "Alex");
  assert.equal(alex.querySelector(".muted").textContent, "Legs 12/20 · Matches 3/5");
  assert.deepEqual(rows(alex), [
    ["3-dart avg.", "61.3"],
    ["First 9", "70.1"],
    ["Checkout", "31.3%"],
    ["MPR", "2.40"],
    ["Best MPR", "3.10"],
    ["Highest visit", "140"],
    ["Highest checkout", "121"],
    ["Best 301", "12 darts"],
    ["Best 501", "18 darts"],
  ]);
  assert.deepEqual(rows(lea), [
    ["3-dart avg.", "–"],
    ["First 9", "–"],
    ["Checkout", "–"],
    ["Highest visit", "–"],
    ["Highest checkout", "–"],
  ]);
  assert.equal(card.getCardSize(), 6);
});

test("a player's rating shows first, whole, once a match has moved it", () => {
  const { card } = setup({ ...profiles({ ...ALEX, rating: 1036.6, rated_matches: 5 }, LEA), ...lastMatch({}) });
  const [alex, lea] = $$(card, ".profile");
  assert.deepEqual(rows(alex)[0], ["Rating", "1,037"]);
  assert.equal(rows(lea).some(([name]) => name === "Rating"), false);
});

test("head-to-head records show the wins and the balance between two players", () => {
  const { hass, card } = setup({
    ...profiles(ALEX, LEA),
    ...lastMatch({ head_to_head: [{ players: ["Alex", "Lea"], wins: [3, 1] }] }),
  });
  assert.equal($(card, ".h2h-section").hidden, false);
  const versus = $(card, ".versus");
  assert.deepEqual(
    [...versus.querySelectorAll("span")].map((part) => part.textContent),
    ["Alex", "3 : 1", "Lea"]
  );
  assert.equal(versus.querySelector(".balance i").style.width, "75%");
  card.hass = update(hass, lastMatch({ head_to_head: [{ players: ["Alex", "Lea"], wins: [0, 0] }] }));
  assert.equal($(card, ".balance i").style.width, "50%");
  card.hass = update(hass, lastMatch({}));
  assert.equal($(card, ".h2h-section").hidden, true);
});

test("recent matches show when they ended, the game and the winner in bold", () => {
  const { card } = setup({ ...profiles(ALEX), ...lastMatch({ matches: MATCHES }) });
  assert.equal($(card, ".matches-section").hidden, false);
  const matches = $$(card, ".match");
  assert.deepEqual(
    matches.map((match) => [...match.children].map((part) => part.textContent.replace(/\s/g, " "))),
    [
      ["09/26, 8:00 PM", "Killer", "Alex 0 · Player 2 1"],
      // A first to three legs ends 3 : 2, a match of sets tells the sets.
      ["", "501", "Lea 3 · Alex 2"],
      ["09/25, 7:00 PM", "Cricket · Sets", "Alex 1 · Sam 2"],
      ["09/24, 7:00 PM", "301", "Lea 3 · Alex 2 · Kim 0"],
      ["09/23, 7:00 PM", "", ""],
    ]
  );
  assert.deepEqual(
    matches.map((match) => match.querySelector("b")?.textContent),
    ["Player 2 1", "Lea 3", "Sam 2", "Lea 3", undefined]
  );
});

test("without profiles the card explains how players get one", () => {
  const { hass, card } = setup({ ...profiles(), ...lastMatch({}) });
  assert.equal($(card, ".empty").hidden, false);
  assert.equal(
    text(card, ".empty"),
    "No player profiles yet. Give the players of a practice game a name, and every leg counts for them."
  );
  assert.equal(text(card, ".count"), "");
  assert.equal(text(card, ".profiles"), "");
  assert.equal($(card, ".matches-section").hidden, true);
  card.hass = update(hass, profiles(LEA));
  assert.equal($(card, ".empty").hidden, true);
  assert.equal(text(card, ".count"), "1");
});

test("head-to-head records and matches can be hidden and the title changed", () => {
  const states = {
    ...profiles(ALEX, LEA),
    ...lastMatch({ matches: MATCHES, head_to_head: [{ players: ["Alex", "Lea"], wins: [3, 1] }] }),
  };
  const { card } = setup(states, { show_head_to_head: false, show_matches: false, title: "League" });
  assert.equal($(card, ".h2h-section"), null);
  assert.equal($(card, ".matches-section"), null);
  assert.equal(text(card, ".title"), "League");
  assert.equal($$(card, ".profile").length, 2);
});

test("player names are shown as text, never as markup", () => {
  const evil = '<img src=x onerror="alert(1)">';
  const { card } = setup({
    ...profiles({ ...ALEX, name: evil }),
    ...lastMatch({
      head_to_head: [{ players: [evil, "Lea"], wins: [1, 0] }],
      matches: [{ ended: "2026-09-26T20:00:00+00:00", game: evil, winner: 1, players: [{ name: evil, legs: 1 }] }],
    }),
  });
  assert.equal($$(card, "img").length, 0);
  assert.equal(text(card, ".profile-name"), evil);
  assert.equal(text(card, ".versus .who"), evil);
  assert.equal(text(card, ".match .game"), evil);
  assert.equal(text(card, ".match b"), `${evil} 1`);
  assert.ok(!$(card, ".profiles").innerHTML.includes("<img"));
});

test("the players card speaks German, also without a locale", () => {
  const hass = makeHass({ states: { ...profiles(ALEX), ...lastMatch({ matches: MATCHES.slice(0, 1) }) } });
  const card = mount("homedarts-players-card", { ...hass, locale: undefined, language: "de" });
  assert.equal(text(card, ".title"), "Spieler");
  assert.equal($(card, ".profile .muted").textContent, "Legs 12/20 · Matches 3/5");
  assert.deepEqual(rows($(card, ".profile")).slice(0, 3), [
    ["3-Dart-Average", "61,3"],
    ["First 9", "70,1"],
    ["Checkout", "31,3 %"],
  ]);
  assert.deepEqual(rows($(card, ".profile")).slice(3, 5), [
    ["MPR", "2,40"],
    ["Beste MPR", "3,10"],
  ]);
  assert.deepEqual(rows($(card, ".profile")).slice(-2), [
    ["Bestes 301-Leg", "12 Darts"],
    ["Bestes 501-Leg", "18 Darts"],
  ]);
  assert.equal(text(card, ".match .muted"), "26.09., 20:00");
});

// Export ---------------------------------------------------------------------

const NAME = "homedarts-all-20260927-201500-0123456789abcdef.zip";
const DOWNLOAD = `/api/homedarts/export/${NAME}`;

// Home Assistant's answers: the response of the action, then a signed path.
function connection(response) {
  const requests = [];
  const callWS = (message) => {
    requests.push(message);
    if (message.type === "auth/sign_path") return Promise.resolve({ path: `${message.path}?authSig=signed` });
    return Promise.resolve({ context: {}, response });
  };
  return { requests, callWS };
}

// Clicks on download links, instead of navigating the test browser.
function downloads() {
  const clicked = [];
  const original = window.HTMLAnchorElement.prototype.click;
  window.HTMLAnchorElement.prototype.click = function click() {
    clicked.push({ href: this.getAttribute("href"), download: this.download, connected: this.isConnected });
  };
  return { clicked, restore: () => (window.HTMLAnchorElement.prototype.click = original) };
}

function notices(card) {
  const messages = [];
  card.addEventListener("hass-notification", (event) => messages.push(event.detail.message));
  return messages;
}

// The export is an action for administrators.
const ADMIN = { id: "8f1c", name: "Dennis", is_admin: true };

test("the export button is off by default, and only administrators get it", () => {
  const { card } = setup({ ...profiles(ALEX), ...lastMatch({}) }, {}, { user: ADMIN });
  assert.equal($(card, ".export"), null);
  // A user without admin rights, or a page without a user, would only get an error.
  for (const user of [{ ...ADMIN, is_admin: false }, undefined]) {
    const other = setup({ ...profiles(ALEX), ...lastMatch({}) }, { export: true }, { user }).card;
    assert.equal($(other, ".export"), null);
    assert.equal(text(other, ".title"), "Players");
  }
  assert.ok($(setup({ ...profiles(ALEX), ...lastMatch({}) }, { export: true }, { user: ADMIN }).card, ".export"));
});

test("the export button writes every table and downloads the file with the user's login", async () => {
  const { requests, callWS } = connection({
    path: `/config/www/homedarts/${NAME}`,
    url: `/local/homedarts/${NAME}`,
    download: DOWNLOAD,
  });
  const { card } = setup(
    { ...profiles(ALEX), ...lastMatch({}) },
    { export: true },
    { callWS, user: ADMIN, device: { primary_config_entry: "entry-1", config_entries: ["other", "entry-1"] } }
  );
  const { clicked, restore } = downloads();
  try {
    const button = $(card, ".export");
    assert.equal(button.textContent, "Export");
    button.click();
    assert.equal(button.disabled, true);
    assert.equal(button.textContent, "Exporting …");
    // A second tap while the file is written does nothing.
    button.click();
    await settle();
    assert.deepEqual(requests, [
      {
        type: "call_service",
        domain: "homedarts",
        service: "export",
        service_data: { format: "csv", what: "all", config_entry_id: "entry-1" },
        return_response: true,
      },
      { type: "auth/sign_path", path: DOWNLOAD, expires: 60 },
    ]);
    assert.deepEqual(clicked, [{ href: `${DOWNLOAD}?authSig=signed`, download: NAME, connected: true }]);
    assert.equal($(card, "a"), null);
    assert.equal(button.disabled, false);
    assert.equal(button.textContent, "Export");
  } finally {
    restore();
  }
});

test("the export can be JSON and picks the board's entry", async () => {
  const { requests, callWS } = connection({ download: DOWNLOAD.replace(".zip", ".json") });
  const { clicked, restore } = downloads();
  try {
    for (const [config, device] of [
      [{ export: true, export_format: "json" }, { config_entries: ["entry-2"] }],
      [{ export: true, export_format: "xml" }, {}],
    ]) {
      const { card } = setup({ ...profiles(ALEX), ...lastMatch({}) }, config, { callWS, device, user: ADMIN });
      $(card, ".export").click();
      await settle();
    }
    assert.deepEqual(
      requests.filter((request) => request.service_data).map((request) => request.service_data),
      [
        { format: "json", what: "all", config_entry_id: "entry-2" },
        { format: "csv", what: "all" },
      ]
    );
    assert.deepEqual(
      clicked.map((link) => link.download),
      [NAME.replace(".zip", ".json"), NAME.replace(".zip", ".json")]
    );
  } finally {
    restore();
  }
});

test("a failed export shows why and leaves the button ready", async () => {
  const answers = [
    () => Promise.reject(new Error("The export could not be written: disk full")),
    () => Promise.resolve({ response: { url: null, path: "/config/exports/x.csv" } }),
    () => Promise.reject({}),
    // Only exports of the integration are downloaded.
    () => Promise.resolve({ response: { download: "https://example.com/x.zip" } }),
  ];
  const callWS = () => answers.shift()();
  const { card } = setup({ ...profiles(ALEX), ...lastMatch({}) }, { export: true }, { callWS, user: ADMIN });
  const messages = notices(card);
  const { clicked, restore } = downloads();
  try {
    for (let attempt = 0; attempt < 4; attempt += 1) {
      $(card, ".export").click();
      await settle();
    }
    assert.deepEqual(messages, [
      "Export failed: The export could not be written: disk full",
      "Export failed: /config/exports/x.csv",
      "Export failed",
      "Export failed",
    ]);
    assert.deepEqual(clicked, []);
    assert.equal($(card, ".export").disabled, false);
  } finally {
    restore();
  }
});


test("the export needs Home Assistant's connection and no preview", async () => {
  const { card } = setup({ ...profiles(ALEX), ...lastMatch({}) }, { export: true }, { user: ADMIN });
  const messages = notices(card);
  card.preview = true;
  $(card, ".export").click();
  await settle();
  assert.deepEqual(messages, []);
  card.preview = false;
  $(card, ".export").click();
  await settle();
  assert.equal(messages.length, 1);
  assert.match(messages[0], /^Export failed: /);
});

test("the export button speaks German", () => {
  const hass = makeHass({ language: "de", states: { ...profiles(ALEX), ...lastMatch({}) }, user: ADMIN });
  const card = mount("homedarts-players-card", hass, { export: true });
  assert.equal(text(card, ".export"), "Exportieren");
});

// Renaming, merging and deleting a profile: a menu on each profile, for administrators, and a
// dialog that asks before each action.
const SAM = { name: "Sam", legs_played: 1, legs_won: 1, matches_played: 1, matches_won: 1 };
const press = (target, key) =>
  target.dispatchEvent(new window.KeyboardEvent("keydown", { key, bubbles: true, composed: true, cancelable: true }));
const tap = (target) => target.dispatchEvent(new window.PointerEvent("pointerdown", { bubbles: true, composed: true }));
const menuButton = (card, name) => $$(card, "[data-manage]").find((button) => button.dataset.manage === name);
const items = (card) => $$(card, ".manage-menu [role=menuitem]");
const focused = (card) => card.shadowRoot.activeElement;
const submit = (card) => $(card, ".manage-form").dispatchEvent(new window.Event("submit", { cancelable: true }));
const typed = (input, value) => {
  input.value = value;
  input.dispatchEvent(new window.Event("input", { bubbles: true }));
};

function manage(card, name, action) {
  menuButton(card, name).click();
  items(card)
    .find((item) => item.dataset.action === action)
    .click();
  return $(card, ".manage-dialog");
}

test("only administrators get the menu of a profile", () => {
  for (const user of [{ ...ADMIN, is_admin: false }, undefined]) {
    const { card } = setup({ ...profiles(ALEX, LEA), ...lastMatch({}) }, {}, { user });
    assert.deepEqual($$(card, "[data-manage]"), []);
    assert.equal($(card, ".manage-dialog"), null);
  }
  const { card } = setup({ ...profiles(ALEX, LEA), ...lastMatch({}) }, {}, { user: ADMIN });
  const button = menuButton(card, "Alex");
  assert.equal(button.getAttribute("aria-label"), "Manage Alex");
  assert.equal(button.getAttribute("aria-haspopup"), "menu");
  assert.equal(button.getAttribute("aria-expanded"), "false");
  assert.equal($(card, ".profile-name span").textContent, "Alex");
  assert.equal($(card, ".manage-menu"), null);
});

test("the menu of a profile opens with a click or the arrows and goes with Escape, Tab or a tap elsewhere", () => {
  const { card } = setup({ ...profiles(ALEX, LEA), ...lastMatch({}) }, {}, { user: ADMIN });
  menuButton(card, "Alex").click();
  assert.equal(menuButton(card, "Alex").getAttribute("aria-expanded"), "true");
  const menu = $(card, ".manage-menu");
  assert.equal(menu.getAttribute("role"), "menu");
  assert.equal(menu.getAttribute("aria-label"), "Manage Alex");
  assert.deepEqual(
    items(card).map((item) => [item.textContent, item.tabIndex]),
    [
      ["Rename", -1],
      ["Merge into …", -1],
      ["Delete", -1],
    ]
  );
  assert.equal(focused(card), items(card)[0]);
  // The arrows go round, Home and End to either end; other keys do nothing.
  for (const [key, index] of [
    ["ArrowDown", 1],
    ["End", 2],
    ["ArrowDown", 0],
    ["ArrowUp", 2],
    ["Home", 0],
    ["a", 0],
  ]) {
    press(focused(card), key);
    assert.equal(focused(card), items(card)[index], key);
  }
  press(focused(card), "Escape");
  assert.equal($(card, ".manage-menu"), null);
  assert.equal(focused(card), menuButton(card, "Alex"));
  // The up arrow opens it at its last action; the arrows of an open menu's button keep it.
  press(menuButton(card, "Alex"), "ArrowUp");
  assert.equal(focused(card), items(card)[2]);
  press(menuButton(card, "Alex"), "ArrowDown");
  assert.equal(items(card).length, 3);
  press(menuButton(card, "Alex"), "x");
  press(items(card)[0], "Tab");
  assert.equal($(card, ".manage-menu"), null);
  assert.equal(focused(card), menuButton(card, "Alex"));
  press(menuButton(card, "Lea"), "ArrowDown");
  assert.equal(menuButton(card, "Lea").getAttribute("aria-expanded"), "true");
  // A key or a click elsewhere in the profiles is no action.
  press($(card, ".profile dd"), "ArrowDown");
  $(card, ".profile dd").click();
  assert.equal(items(card).length, 3);
  // Another profile's button opens its menu; the same button closes it.
  menuButton(card, "Alex").click();
  assert.equal(menuButton(card, "Lea").getAttribute("aria-expanded"), "false");
  menuButton(card, "Alex").click();
  assert.equal($(card, ".manage-menu"), null);
  // A tap inside the menu keeps it, a tap elsewhere closes it.
  menuButton(card, "Alex").click();
  tap(items(card)[1]);
  tap(menuButton(card, "Alex"));
  assert.equal(items(card).length, 3);
  tap($(card, ".title"));
  assert.equal($(card, ".manage-menu"), null);
  tap($(card, ".title"));
});

test("one profile has nothing to merge into, and a preview opens no menu", () => {
  const { card, hass } = setup({ ...profiles(ALEX, LEA), ...lastMatch({}) }, {}, { user: ADMIN });
  menuButton(card, "Lea").click();
  // A profile that goes away takes its open menu along.
  card.hass = update(hass, profiles(ALEX));
  assert.equal($(card, ".manage-menu"), null);
  menuButton(card, "Alex").click();
  assert.deepEqual(
    items(card).map((item) => item.dataset.action),
    ["rename", "delete"]
  );
  menuButton(card, "Alex").click();
  card.preview = true;
  menuButton(card, "Alex").click();
  assert.equal($(card, ".manage-menu"), null);
});

test("renaming asks for the new name, says when it joins another profile and calls the action", async () => {
  const { requests, callWS } = connection(null);
  const { card, hass } = setup(
    { ...profiles(ALEX, LEA), ...lastMatch({}) },
    {},
    { callWS, user: ADMIN, device: { config_entry_id: "entry-1" } }
  );
  const dialog = manage(card, "Alex", "rename");
  assert.equal(dialog.open, true);
  assert.equal($(card, ".manage-menu"), null);
  assert.equal(dialog.getAttribute("aria-labelledby"), "manage-title");
  assert.equal(dialog.querySelector("#manage-title").textContent, "Rename Alex");
  const input = dialog.querySelector("input");
  assert.equal(focused(card), input);
  assert.equal(input.value, "Alex");
  assert.equal(input.closest("label").textContent, "New name");
  const hint = dialog.querySelector(".manage-hint");
  const kept = "Statistics, badges, records and the link to a person keep the new name.";
  assert.equal(hint.textContent, kept);
  typed(input, " LEA ");
  assert.equal(hint.textContent, "Lea has a profile already: both become one profile, as if one player had thrown every dart.");
  for (const value of ["ALEX", "Al"]) {
    typed(input, value);
    assert.equal(hint.textContent, kept);
  }
  const confirm = dialog.querySelector(".manage-confirm");
  assert.equal(confirm.textContent, "Rename");
  assert.equal(confirm.classList.contains("confirm"), false);
  // Without a name, nothing happens.
  input.value = "  ";
  submit(card);
  assert.deepEqual(requests, []);
  input.value = " Al ";
  submit(card);
  assert.equal(confirm.disabled, true);
  submit(card);
  await settle();
  assert.deepEqual(requests, [
    {
      type: "call_service",
      domain: "homedarts",
      service: "rename_player",
      service_data: { player: "Alex", new_name: "Al", config_entry_id: "entry-1" },
    },
  ]);
  assert.equal(dialog.open, false);
  // The keyboard comes back to the menu button once the profiles show the new name.
  const later = update(hass, lastMatch({ matches: [] }));
  card.hass = later;
  card.hass = update(later, profiles({ ...ALEX, name: "Al" }, LEA));
  assert.equal(focused(card), menuButton(card, "Al"));
});

test("merging offers the other players and calls the action with the one that keeps the profile", async () => {
  const { requests, callWS } = connection(null);
  const { card } = setup({ ...profiles(ALEX, LEA, SAM), ...lastMatch({}) }, {}, { callWS, user: ADMIN });
  const dialog = manage(card, "Alex", "merge");
  assert.equal(dialog.querySelector("h2").textContent, "Merge Alex into …");
  const select = dialog.querySelector("select");
  assert.equal(focused(card), select);
  assert.equal(select.closest("label").textContent.startsWith("Player who keeps the profile"), true);
  assert.deepEqual(
    [...select.options].map((option) => option.textContent),
    ["Lea", "Sam"]
  );
  assert.match(dialog.querySelector(".manage-body p").textContent, /^The statistics, badges and records of Alex go/);
  const confirm = dialog.querySelector(".manage-confirm");
  assert.equal(confirm.textContent, "Merge");
  assert.equal(confirm.classList.contains("confirm"), true);
  select.value = "Sam";
  select.dispatchEvent(new window.Event("input", { bubbles: true }));
  submit(card);
  await settle();
  assert.deepEqual(
    requests.map((request) => [request.service, request.service_data]),
    [["rename_player", { player: "Alex", new_name: "Sam" }]]
  );
  assert.equal(dialog.open, false);
});

test("deleting asks first, starts on Cancel and calls the action", async () => {
  const { requests, callWS } = connection(null);
  const { card } = setup({ ...profiles(ALEX, LEA), ...lastMatch({}) }, {}, { callWS, user: ADMIN });
  const dialog = manage(card, "Lea", "delete");
  assert.equal(dialog.querySelector("h2").textContent, "Delete Lea?");
  assert.match(dialog.querySelector(".manage-body").textContent, /This cannot be undone\.$/);
  assert.equal(focused(card), dialog.querySelector(".manage-cancel"));
  assert.equal(dialog.querySelector(".manage-confirm").textContent, "Delete");
  submit(card);
  await settle();
  assert.deepEqual(
    requests.map((request) => [request.service, request.service_data]),
    [["delete_player", { name: "Lea" }]]
  );
  assert.equal(dialog.open, false);
});

test("Cancel closes the dialog and the keyboard goes back to the menu button", () => {
  const { card } = setup({ ...profiles(ALEX, LEA), ...lastMatch({}) }, {}, { user: ADMIN });
  const dialog = manage(card, "Alex", "rename");
  dialog.querySelector(".manage-cancel").click();
  assert.equal(dialog.open, false);
  assert.equal(focused(card), menuButton(card, "Alex"));
  // A dialog closed from elsewhere brings the keyboard back, too.
  manage(card, "Alex", "rename");
  menuButton(card, "Lea").focus();
  dialog.close();
  assert.equal(focused(card), menuButton(card, "Alex"));
});

test("a refused action keeps the dialog open with the reason", async () => {
  const answers = [
    () => Promise.reject({ code: "service_validation_error", message: "Lea and Alex both play the match being played." }),
    () => Promise.reject({}),
    () => Promise.reject(),
  ];
  const callWS = () => answers.shift()();
  const { card } = setup({ ...profiles(ALEX, LEA), ...lastMatch({}) }, {}, { callWS, user: ADMIN });
  const dialog = manage(card, "Lea", "merge");
  const error = dialog.querySelector(".manage-error");
  assert.equal(error.getAttribute("role"), "alert");
  assert.equal(error.hidden, true);
  const reasons = [];
  for (let attempt = 0; attempt < 3; attempt += 1) {
    submit(card);
    await settle();
    reasons.push(error.hidden ? null : error.textContent);
  }
  assert.deepEqual(reasons, [
    "Lea and Alex both play the match being played.",
    "That did not work. Try again.",
    "That did not work. Try again.",
  ]);
  assert.equal(dialog.open, true);
  assert.equal(dialog.querySelector(".manage-confirm").disabled, false);
  // The next dialog starts without the reason of the last one.
  dialog.close();
  manage(card, "Lea", "delete");
  assert.equal(error.hidden, true);
});

test("the menu and its dialog speak German", () => {
  const hass = makeHass({ language: "de", states: { ...profiles(ALEX, LEA), ...lastMatch({}) }, user: ADMIN });
  const card = mount("homedarts-players-card", hass, {});
  assert.equal(menuButton(card, "Alex").getAttribute("aria-label"), "Alex verwalten");
  const dialog = manage(card, "Alex", "merge");
  assert.equal(dialog.querySelector("h2").textContent, "Alex zusammenführen mit …");
  assert.equal(dialog.querySelector(".manage-cancel").textContent, "Abbrechen");
  assert.equal(dialog.querySelector(".manage-confirm").textContent, "Zusammenführen");
});

// axe-core, the engine of the accessibility check in a real browser, runs its rules that need
// no layout here too: the roles of the menu and its items, the names of buttons and fields.
test("the open menu and its dialog pass axe-core's WCAG 2.1 A and AA rules", async () => {
  window.eval(readFileSync(new URL("../../node_modules/axe-core/axe.min.js", import.meta.url), "utf8"));
  const audit = async (element) => {
    const result = await window.axe.run(element, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] });
    // Arrays of the page's window, made arrays of the tests.
    return { violations: Array.from(result.violations, (rule) => rule.id), passes: Array.from(result.passes, (rule) => rule.id) };
  };
  const rated = { ...ALEX, rating: 1036.6, rated_matches: 5 };
  const { card } = setup({ ...profiles(rated, LEA), ...lastMatch({}) }, {}, { user: ADMIN });
  menuButton(card, "Alex").click();
  const menu = await audit($(card, "ha-card"));
  assert.deepEqual(menu.violations, []);
  for (const rule of ["aria-required-children", "aria-required-parent", "aria-allowed-attr", "button-name"]) {
    assert.ok(menu.passes.includes(rule), rule);
  }
  menuButton(card, "Alex").click();
  for (const action of ["rename", "merge", "delete"]) {
    const dialog = manage(card, "Alex", action);
    const checked = await audit(dialog);
    assert.deepEqual(checked.violations, [], action);
    assert.ok(checked.passes.includes("button-name"), action);
    // The new name is a field with a label, the player to merge into a list with one.
    const field = { rename: "label", merge: "select-name" }[action];
    if (field) assert.ok(checked.passes.includes(field), action);
    dialog.close();
  }
});
