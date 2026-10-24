// The scoreboard in full screen: alone on the screen of a tablet at the board, without
// the bars of the browser and Home Assistant's header and sidebar, and a screen that
// stays on meanwhile.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { $, READY, loadCards, makeHass, mount, settle, window, withLanguage } from "./dom.mjs";

await loadCards();

const { document } = window;
const setup = (config = {}, hass = makeHass({ states: READY })) => mount("homedarts-scoreboard-card", hass, config);
const button = (card) => $(card, ".fullscreen-toggle");
const shown = (card) => [
  button(card).getAttribute("aria-pressed"),
  button(card).firstElementChild.getAttribute("icon"),
  [...$(card, ".scoreboard").classList].sort().join(" "),
  $(card, ".main").getAttribute("role"),
];
const NORMAL = ["false", "mdi:fullscreen", "scoreboard", null];
const FULL = ["true", "mdi:fullscreen-exit", "full fullscreen scoreboard", "region"];

// A browser that offers full screen, as on a tablet: it puts one element on the whole
// screen and tells it, and Escape leaves full screen.
function fullscreen(t, { refuse = false } = {}) {
  const calls = [];
  let element = null;
  const change = (target) => target.dispatchEvent(new window.Event("fullscreenchange", { bubbles: true, composed: true }));
  const { prototype } = window.HTMLElement;
  Object.defineProperty(document, "fullscreenEnabled", { configurable: true, value: true });
  Object.defineProperty(document, "fullscreenElement", { configurable: true, get: () => element });
  prototype.requestFullscreen = function requestFullscreen() {
    calls.push("enter");
    if (refuse) return Promise.reject(new window.TypeError("Permissions check failed"));
    element = this;
    change(this);
    return Promise.resolve();
  };
  document.exitFullscreen = () => {
    calls.push("exit");
    escape();
    return Promise.resolve();
  };
  const escape = () => {
    const left = element;
    element = null;
    change(left);
  };
  t.after(() => {
    delete document.fullscreenEnabled;
    delete document.fullscreenElement;
    delete document.exitFullscreen;
    delete prototype.requestFullscreen;
  });
  return { calls, escape };
}

// The screen wake lock of a browser in a secure context. Each request waits for an
// answer: grant() gives the lock, refuse() says no, as with the battery saver on.
function wakeLock(t) {
  const asked = [];
  const locks = [];
  Object.defineProperty(window.navigator, "wakeLock", {
    configurable: true,
    value: {
      request(type) {
        return new Promise((resolve, reject) => asked.push({ type, resolve, reject }));
      },
    },
  });
  t.after(() => delete window.navigator.wakeLock);
  const lock = () => {
    const sentinel = {
      type: "screen",
      released: false,
      release() {
        sentinel.released = true;
        return Promise.resolve();
      },
    };
    locks.push(sentinel);
    return sentinel;
  };
  return {
    asked,
    locks,
    held: () => locks.filter((sentinel) => !sentinel.released).length,
    grant: async () => {
      asked.at(-1).resolve(lock());
      await settle();
    },
    refuse: async () => {
      asked.at(-1).reject(new window.DOMException("Battery saver", "NotAllowedError"));
      await settle();
    },
  };
}

// The page goes to the background and comes back, as when the tablet switches apps.
function visibility(t) {
  let state = "visible";
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => state });
  t.after(() => delete document.visibilityState);
  return (next) => {
    state = next;
    document.dispatchEvent(new window.Event("visibilitychange"));
  };
}

test("the button is there only where the browser offers full screen and the settings want it", (t) => {
  // happy-dom, like an iPhone, offers no full screen to a page.
  assert.equal(button(setup()).hidden, true);
  Object.defineProperty(document, "fullscreenEnabled", { configurable: true, value: false });
  t.after(() => delete document.fullscreenEnabled);
  assert.equal(button(setup()).hidden, true);
  Object.defineProperty(document, "fullscreenEnabled", { configurable: true, value: true });
  const card = setup();
  assert.equal(button(card).hidden, false);
  assert.equal(button(card).getAttribute("aria-label"), "Full screen");
  assert.match(button(card).title, /Escape or a double tap leaves full screen/);
  assert.deepEqual(shown(card), NORMAL);
  assert.equal(button(setup({ fullscreen_button: false })).hidden, true);
  // The button is the last control of the top bar, after the caller and the status.
  const actions = [...$(setup({ caller: true }), ".header-actions").children].map((child) => child.className);
  assert.deepEqual(actions, ["lobby-toggle", "caller-toggle", "pill", "fullscreen-toggle"]);
});

test("the button has a name in every language of the cards", (t) => {
  Object.defineProperty(document, "fullscreenEnabled", { configurable: true, value: true });
  t.after(() => delete document.fullscreenEnabled);
  const names = Object.fromEntries(
    ["en", "de", "nl", "fr", "es"].map((language) => [
      language,
      button(setup({}, withLanguage(makeHass({ states: READY }), language))).getAttribute("aria-label"),
    ])
  );
  assert.deepEqual(names, {
    en: "Full screen",
    de: "Vollbild",
    nl: "Volledig scherm",
    fr: "Plein écran",
    es: "Pantalla completa",
  });
});

test("the button puts the scoreboard alone on the screen, and takes it back", (t) => {
  const browser = fullscreen(t);
  const card = setup();
  button(card).click();
  assert.deepEqual(browser.calls, ["enter"]);
  assert.equal(document.fullscreenElement, card);
  // Alone on the screen, the scoreboard fills it like at full height, and its scores
  // are a region that the keyboard reaches.
  assert.deepEqual(shown(card), FULL);
  assert.deepEqual(
    ["tabindex", "aria-label"].map((name) => $(card, ".main").getAttribute(name)),
    ["0", "Scoreboard"]
  );
  button(card).click();
  assert.deepEqual(browser.calls, ["enter", "exit"]);
  assert.deepEqual(shown(card), NORMAL);
  assert.equal($(card, ".main").hasAttribute("tabindex"), false);
  // Escape, which the browser handles itself, leaves full screen too.
  button(card).click();
  browser.escape();
  assert.deepEqual(shown(card), NORMAL);
});

test("a scoreboard at full height stays at full height after full screen", (t) => {
  fullscreen(t);
  const card = setup({ full_height: true });
  assert.deepEqual(shown(card), ["false", "mdi:fullscreen", "full scoreboard", "region"]);
  button(card).click();
  assert.deepEqual(shown(card), FULL);
  // New settings while in full screen draw the card anew, still in full screen.
  card.setConfig({ type: "custom:homedarts-scoreboard-card", full_height: true, caller: true });
  assert.deepEqual(shown(card), FULL);
  button(card).click();
  assert.deepEqual(shown(card), ["false", "mdi:fullscreen", "full scoreboard", "region"]);
});

test("the card editor shows the button, which does nothing there", (t) => {
  const browser = fullscreen(t);
  const card = setup();
  card.preview = true;
  button(card).click();
  assert.deepEqual(browser.calls, []);
  assert.deepEqual(shown(card), NORMAL);
});

test("a browser that refuses full screen leaves the scoreboard as it is", async (t) => {
  const browser = fullscreen(t, { refuse: true });
  const card = setup();
  button(card).click();
  await settle();
  assert.deepEqual(browser.calls, ["enter"]);
  assert.deepEqual(shown(card), NORMAL);
});

test("a double tap on the scoreboard leaves full screen, a tap on a control does not count", (t) => {
  t.mock.timers.enable({ apis: ["Date"], now: 0 });
  const browser = fullscreen(t);
  const card = setup();
  // A control among the scores, as the buttons of the new game screen are.
  $(card, ".main").append(Object.assign(document.createElement("button"), { className: "control" }));
  const tap = (selector, after = 100) => {
    t.mock.timers.tick(after);
    $(card, selector).click();
  };
  // Outside full screen, a double tap is a double tap.
  tap(".main");
  tap(".main");
  assert.deepEqual(browser.calls, []);
  button(card).click();
  // Two taps too far apart, and taps of which one is on a control.
  tap(".main");
  tap(".main", 401);
  tap(".heading", 500);
  tap(".control");
  tap(".main");
  assert.deepEqual(browser.calls, ["enter"]);
  tap(".title", 50);
  assert.deepEqual(browser.calls, ["enter", "exit"]);
  assert.deepEqual(shown(card), NORMAL);
});

test("in full screen the screen stays on, and the browser's lock goes when full screen ends", async (t) => {
  const browser = fullscreen(t);
  const lock = wakeLock(t);
  const card = setup();
  button(card).click();
  assert.deepEqual(
    lock.asked.map((ask) => ask.type),
    ["screen"]
  );
  await lock.grant();
  assert.equal(lock.held(), 1);
  // A second notice of full screen asks for no second lock.
  card.dispatchEvent(new window.Event("fullscreenchange"));
  assert.equal(lock.asked.length, 1);
  button(card).click();
  assert.deepEqual(browser.calls, ["enter", "exit"]);
  assert.equal(lock.held(), 0);
  assert.equal($(card, ".awake-hint").hidden, true);
});

test("the lock comes back when the page shows again, and after the browser let it go", async (t) => {
  fullscreen(t);
  const lock = wakeLock(t);
  const page = visibility(t);
  const card = setup();
  button(card).click();
  await lock.grant();
  // In the background the browser lets go of the lock, and so does the card.
  page("hidden");
  assert.equal(lock.held(), 0);
  assert.equal(lock.asked.length, 1);
  page("visible");
  assert.equal(lock.asked.length, 2);
  await lock.grant();
  assert.equal(lock.held(), 1);
  // A lock that the browser let go of by itself, such as for the battery saver.
  lock.locks.at(-1).released = true;
  page("visible");
  assert.equal(lock.asked.length, 3);
  await lock.grant();
  assert.equal(lock.held(), 1);
  // Out of full screen, the page coming back asks for nothing.
  button(card).click();
  page("visible");
  assert.equal(lock.asked.length, 3);
  assert.equal(lock.held(), 0);
});

test("a lock that comes after full screen ended is let go of at once", async (t) => {
  fullscreen(t);
  const lock = wakeLock(t);
  const card = setup();
  button(card).click();
  button(card).click();
  await lock.grant();
  assert.equal(lock.held(), 0);
  // Refused after full screen ended: nothing to tell any more.
  button(card).click();
  button(card).click();
  await lock.refuse();
  assert.equal($(card, ".awake-hint").hidden, true);
});

test("without the setting the scoreboard asks for no lock", (t) => {
  fullscreen(t);
  const lock = wakeLock(t);
  const card = setup({ keep_awake: false });
  button(card).click();
  assert.deepEqual(shown(card), FULL);
  assert.equal(lock.asked.length, 0);
  assert.equal($(card, ".awake-hint").hidden, true);
});

test("once, where the browser can't keep the screen on, a hint says how to keep it on", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  fullscreen(t);
  // Over plain HTTP the browser has no wake lock.
  const card = setup();
  const hint = $(card, ".awake-hint");
  button(card).click();
  assert.equal(hint.hidden, false);
  assert.match(hint.textContent, /This browser can't keep the screen on here/);
  const link = hint.querySelector("a");
  assert.equal(link.href, "https://dennis-otto.github.io/homedarts-for-autodarts/scoreboard.html#full-screen");
  assert.equal(link.textContent, "How to keep it on");
  assert.deepEqual([link.target, link.rel], ["_blank", "noreferrer"]);
  t.mock.timers.tick(15000);
  assert.equal(hint.hidden, true);
  // The next time in full screen, the hint stays away.
  button(card).click();
  button(card).click();
  assert.equal(hint.hidden, true);
  // Leaving full screen takes a hint along that still shows.
  const other = setup();
  button(other).click();
  assert.equal($(other, ".awake-hint").hidden, false);
  button(other).click();
  assert.equal($(other, ".awake-hint").hidden, true);
  await settle();
});

test("a lock the browser refuses shows the hint too", async (t) => {
  fullscreen(t);
  const lock = wakeLock(t);
  const card = setup();
  button(card).click();
  await lock.refuse();
  assert.equal($(card, ".awake-hint").hidden, false);
  // Asked for again when the page shows again, it is held this time.
  document.dispatchEvent(new window.Event("visibilitychange"));
  await lock.grant();
  assert.equal(lock.held(), 1);
  button(card).click();
});

test("a scoreboard that leaves the page leaves full screen and lets the screen sleep", async (t) => {
  fullscreen(t);
  const lock = wakeLock(t);
  const card = setup();
  button(card).click();
  await lock.grant();
  // The browser leaves full screen with the element and tells the document, not the card.
  card.remove();
  assert.equal(lock.held(), 0);
  document.body.append(card);
  assert.deepEqual(shown(card), NORMAL);
  assert.equal(lock.asked.length, 1);
});

// axe-core, the engine of the accessibility check in a real browser, runs its rules that need
// no layout here too: the name of the button and of the link of the hint.
test("the top bar with the button and the hint pass axe-core's WCAG 2.1 A and AA rules", async (t) => {
  fullscreen(t);
  window.eval(readFileSync(new URL("../../node_modules/axe-core/axe.min.js", import.meta.url), "utf8"));
  const card = setup();
  button(card).click();
  const result = await window.axe.run($(card, ".scoreboard"), {
    runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
  });
  assert.deepEqual(
    Array.from(result.violations, (rule) => rule.id),
    []
  );
  const passes = Array.from(result.passes, (rule) => rule.id);
  for (const rule of ["button-name", "link-name", "aria-allowed-attr"]) assert.ok(passes.includes(rule), rule);
  button(card).click();
});

test("full screen fills the screen from edge to edge, with a button the size of a finger", () => {
  const style = $(setup(), "style").textContent;
  const has = (pattern) => assert.match(style, pattern);
  has(/:host\(:fullscreen\) \{ overflow-y: auto; background: var\(--primary-background-color, #111\); \}/);
  has(/:host\(:fullscreen\) ha-card \{ height: auto; min-height: 100%; border: none; border-radius: 0; \}/);
  // Without Home Assistant's header, only the safe areas take room from the height.
  has(/\.scoreboard\.fullscreen \{\s*--ad-taken: calc\(\s*var\(--safe-area-inset-top, env\(safe-area-inset-top, 0px\)\) \+/);
  has(/touch-action: manipulation;\s*\}/);
  has(/@media \(any-pointer: coarse\) \{ \.fullscreen-toggle \{ width: 44px; height: 44px; \} \}/);
});
