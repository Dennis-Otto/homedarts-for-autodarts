// The scoreboard as the overlay of a stream: alone over the picture, for a browser source of OBS.
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
  { player: 1, name: "Alex", remaining: 81, legs: 1, sets: 0, average: 60.2 },
  { player: 2, name: "Sam", remaining: 301, legs: 0, sets: 0, average: 48.5 },
];
const game = (attributes = {}) => ({
  "sensor.practice_remaining": {
    state: String(attributes.remaining ?? 81),
    attributes: { game: 501, player: 1, name: "Alex", remaining: 81, legs_to_win: 2, scores: PLAYERS, ...attributes },
  },
});
// The summary the practice game keeps of a finished match.
const SUMMARY = {
  game: 501,
  winner: 1,
  ended: "2026-09-27T12:00:00+00:00",
  legs_to_win: 2,
  sets_to_win: 1,
  players: PLAYERS.map(({ player, name }) => ({ player, name, legs: 2 - player, sets: 0, average: 50 })),
};
// The board offers games, a keypad and the new game screen, which the overlay leaves out.
const BOARD = {
  "select.practice_game": { state: "501", attributes: { options: ["off", "501", "cricket"] } },
  "switch.practice_manual_entry": "on",
};
const setup = (states = {}, config = {}) => {
  const hass = makeHass({ states: { ...READY, ...BOARD, ...visit(), ...states } });
  return { hass, card: mount("homedarts-scoreboard-card", hass, config) };
};
const stageOf = (card) => {
  const stage = $(card, ".stage");
  return stage && [stage.dataset.mode, stage.dataset.layout, card.style.getPropertyValue("--ad-key")];
};
const page = () => window.document.getElementById("homedarts-overlay");

// Browsers with popovers put the stage above everything on the page; happy-dom has none.
function popovers(t) {
  const shown = new Set();
  const { prototype } = window.HTMLElement;
  prototype.showPopover = function showPopover() {
    shown.add(this);
  };
  prototype.hidePopover = function hidePopover() {
    shown.delete(this);
  };
  t.after(() => {
    delete prototype.showPopover;
    delete prototype.hidePopover;
  });
  return shown;
}

test("the overlay shows the game on plates of its own, without the card and its controls", (t) => {
  // A browser that offers full screen: the overlay has no button for it all the same.
  Object.defineProperty(window.document, "fullscreenEnabled", { configurable: true, value: true });
  t.after(() => delete window.document.fullscreenEnabled);
  const { card } = setup(
    { ...visit(T20), ...game({ checkout: "T15 D18" }) },
    { overlay: "chroma", caller: true, keypad: true, show_status: true, full_height: true, fullscreen_button: true }
  );
  assert.equal($(card, "ha-card").className, "overlay-card");
  assert.deepEqual(stageOf(card), ["chroma", "lower_third", "#00FF00"]);
  assert.equal($(card, ".scoreboard").className, "scoreboard overlay");
  // The game, its format, the scores, the route of the player at the board and the visit.
  assert.equal(text(card, ".title"), "Practice 501");
  assert.equal(text(card, ".meta"), "2 legs per set");
  assert.deepEqual(
    $$(card, ".player .big").map((big) => big.textContent),
    ["81", "301"]
  );
  assert.equal($(card, ".player.active .name").textContent, "Alex");
  assert.ok($(card, ".player.active .route .bed"));
  assert.equal($(card, ".visit").hidden, false);
  assert.equal($(card, ".visit .dart .segment").textContent, "T20");
  // Nobody taps a stream: no status, caller, new game screen, keypad, corrections or full screen.
  assert.equal($(card, ".pill"), null);
  assert.equal($(card, ".fullscreen-toggle").hidden, true);
  assert.equal($(card, ".caller-toggle"), null);
  assert.equal($(card, ".lobby-toggle").hidden, true);
  assert.equal($(card, ".pad-area").hidden, true);
  assert.deepEqual($$(card, ".visit button"), []);
  assert.equal($(card, ".main").getAttribute("tabindex"), null);
});

test("between games the overlay leaves the picture to the stream", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout", "Date"], now: Date.UTC(2026, 8, 27, 12) });
  const { hass, card } = setup({ ...visit(T20), ...game() }, { overlay: "transparent" });
  const quiet = () => $(card, ".scoreboard").classList.contains("quiet");
  assert.equal(quiet(), false);
  // The game ends: no new game screen opens by itself, and no idle mode follows.
  card.hass = update(hass, { "sensor.practice_remaining": "unavailable", ...visit() });
  assert.equal(quiet(), true);
  assert.deepEqual([text(card, ".title"), text(card, ".meta"), text(card, ".main")], ["", "", ""]);
  assert.equal($(card, ".banner").hidden, true);
  assert.equal($(card, ".visit").hidden, true);
  t.mock.timers.tick(600000);
  assert.equal($(card, ".lobby"), null);
  assert.equal($(card, ".idle-panel"), null);
  assert.equal(quiet(), true);
});

test("the settings of an overlay fall back to their defaults", (t) => {
  globalThis.CSS = { supports: (property, value) => property === "color" && value === "#FF00FF" };
  t.after(() => delete globalThis.CSS);
  const shown = (config) => stageOf(setup(game(), config).card);
  // Off, unknown or missing: the scoreboard as it is.
  for (const overlay of [undefined, "off", "green"]) assert.equal(shown({ overlay }), null);
  assert.deepEqual(shown({ overlay: "chroma", overlay_layout: "corner", overlay_color: "#FF00FF" }), [
    "chroma",
    "corner",
    "#FF00FF",
  ]);
  assert.deepEqual(shown({ overlay: "chroma", overlay_layout: "middle", overlay_color: "url(x)" }), [
    "chroma",
    "lower_third",
    "#00FF00",
  ]);
  // See-through needs no key colour.
  assert.deepEqual(shown({ overlay: "transparent", overlay_layout: "full", overlay_color: "#FF00FF" }), [
    "transparent",
    "full",
    "transparent",
  ]);
});

test("only the whole picture has room for the summary of a match", () => {
  const won = game({ remaining: 0, winner: 1, summary: SUMMARY });
  for (const [layout, summary] of [
    ["lower_third", false],
    ["corner", false],
    ["full", true],
  ]) {
    const { card } = setup(won, { overlay: "chroma", overlay_layout: layout });
    assert.equal(text(card, ".banner"), "Alex wins the match 1 : 0!", layout);
    assert.equal(Boolean($(card, ".main table.summary")), summary, layout);
  }
});

test("on the dashboard the overlay takes the window and hides Home Assistant, not in the editor", (t) => {
  const shown = popovers(t);
  const { card } = setup(game(), { overlay: "chroma" });
  const stage = $(card, ".stage");
  const taken = () => [shown.has(stage), stage.getAttribute("popover"), stage.classList.contains("taken"), Boolean(page())];
  assert.deepEqual(taken(), [true, "manual", true, true]);
  assert.match(page().textContent, /html, body \{ background: transparent !important; overflow: hidden !important; \}/);
  assert.match(page().textContent, /body > \* \{ visibility: hidden !important; \}/);
  // A second overlay shares the page, which comes back once the last one has left.
  const other = setup(game(), { overlay: "transparent", overlay_layout: "corner" }).card;
  assert.equal(window.document.querySelectorAll("#homedarts-overlay").length, 1);
  other.remove();
  assert.ok(page());
  // The card editor and the edit mode of the dashboard show the overlay inside the card.
  card.preview = true;
  assert.deepEqual(taken(), [false, null, false, false]);
  card.preview = false;
  assert.deepEqual(taken(), [true, "manual", true, true]);
  // A card that leaves the page gives the page back; back on it, it takes the window again.
  card.remove();
  assert.deepEqual(taken().slice(1), [null, false, false]);
  window.document.body.append(card);
  assert.deepEqual(taken(), [true, "manual", true, true]);
  // An overlay switched off becomes the scoreboard again.
  card.setConfig({ type: "custom:homedarts-scoreboard-card" });
  assert.equal($(card, ".stage"), null);
  assert.equal(page(), null);
});

test("a browser without popovers shows the overlay inside the card", () => {
  const { card } = setup(game(), { overlay: "chroma" });
  assert.equal($(card, ".stage").classList.contains("taken"), false);
  assert.equal($(card, ".stage").hasAttribute("popover"), false);
  assert.equal(page(), null);
});

test("Escape or a double click leaves the overlay for the page before it or the dashboard", (t) => {
  popovers(t);
  const { history } = window;
  const back = t.mock.method(history, "back", () => {});
  let length = 1;
  Object.defineProperty(history, "length", { configurable: true, get: () => length });
  const changed = [];
  const changes = (event) => changed.push([window.location.pathname, event.detail]);
  window.addEventListener("location-changed", changes);
  t.after(() => {
    delete history.length;
    window.removeEventListener("location-changed", changes);
    history.replaceState(null, "", "/lovelace/0");
  });
  const key = (name) => window.dispatchEvent(new window.KeyboardEvent("keydown", { key: name }));
  const { card } = setup(game(), { overlay: "chroma" });
  key("Enter");
  assert.deepEqual(changed, []);
  // Opened on its own, as in OBS, the overlay leaves for the first view of its dashboard.
  key("Escape");
  assert.deepEqual(changed, [["/lovelace", { replace: false }]]);
  assert.equal(back.mock.callCount(), 0);
  // With a page before it, the overlay goes back there.
  length = 2;
  $(card, ".stage").dispatchEvent(new window.MouseEvent("dblclick", { bubbles: true }));
  assert.equal(back.mock.callCount(), 1);
  // Inside the card, in the editor, neither leaves.
  card.preview = true;
  key("Escape");
  $(card, ".stage").dispatchEvent(new window.MouseEvent("dblclick", { bubbles: true }));
  assert.equal(back.mock.callCount(), 1);
  // At the root of the site, the overlay leaves for the root.
  card.preview = false;
  length = 1;
  history.replaceState(null, "", "/");
  key("Escape");
  assert.deepEqual(changed.at(-1), ["/", { replace: false }]);
});

test("the overlay lies on a key colour or on nothing, sized by the picture, its glow left out on a key", () => {
  const style = $(setup(game(), { overlay: "chroma" }).card, "style").textContent;
  const has = (pattern) => assert.match(style, pattern);
  has(/ha-card\.overlay-card \{ background: none; border: none; border-radius: 0; box-shadow: none; overflow: visible; \}/);
  has(/position: relative; container-type: size; aspect-ratio: 16 \/ 9; overflow: hidden;\s*color: var\(--primary-text-color\); background: var\(--ad-key, transparent\);/);
  has(/\.stage\[data-mode="transparent"\]:not\(\.taken\) \{\s*background: repeating-conic-gradient/);
  has(/\.stage\.taken \{\s*position: fixed; inset: 0; width: 100%; height: 100%;[^}]*visibility: visible;/);
  has(/\.stage \.overlay\.quiet \{ display: none; \}/);
  has(/\.stage\[data-mode="chroma"\] \.moment \.glow \{ display: none; \}/);
  // Plates are opaque: a see-through tint would mix with the key colour.
  has(/\.stage \.overlay \.player\.active \{\s*border-color: var\(--ad-accent\); background: color-mix\(in srgb, var\(--ad-accent\) 16%, var\(--ad-plate\)\);/);
  has(/\.stage\[data-layout="lower_third"\] \.overlay \{\s*left: 4cqw; right: 4cqw; bottom: 5cqh;/);
  has(/\.stage\[data-layout="corner"\] \.overlay \{ top: 4cqh; left: 3cqw; width: 32cqw; align-content: start; \}/);
  has(/\.stage\[data-layout="full"\] \.overlay \{\s*inset: 5cqh 4cqw;/);
});
