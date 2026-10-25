// The live demo of the website (docs/demo/): its replay of the recording, the Home
// Assistant it gives the cards, and the page with its controls, in every language.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  AGAIN,
  LANGUAGES,
  LONGEST_WAIT,
  Replay,
  TEXT,
  boot,
  defineHomeElements,
  hassOf,
  pickLanguage,
  shifted,
} from "../../docs/demo/demo.js";
import { loadCards, settle, window } from "./dom.mjs";

const RECORDING = JSON.parse(readFileSync(new URL("../../docs/demo/timeline.json", import.meta.url), "utf8"));
// The page without its script, which the tests run themselves.
const BODY = readFileSync(new URL("../../docs/demo/index.html", import.meta.url), "utf8")
  .split("<body>")[1]
  .split('<script type="module">')[0];

const START = "2026-03-14T19:30:00+00:00";
const TIMELINE = {
  format: 1,
  start: START,
  device: { id: "demo-board", name: "Dartboard" },
  entities: {},
  chapters: [
    { key: "start", step: 0 },
    { key: "x01", step: 1 },
    { key: "cricket", step: 3 },
  ],
  steps: [
    { at: 0, states: { "sensor.a": ["1", { since: START, list: [START, 3] }], "sensor.b": ["x", {}] } },
    { at: 1000, states: { "sensor.a": ["2", {}] }, positions: { "": { player: null, positions: [[0, 0.6]] } } },
    { at: 10000, states: { "sensor.b": null } },
    { at: 11000, states: { "sensor.a": ["3", {}] } },
  ],
};

// A clock and timers that move only when the test says so.
function clock(at = Date.parse("2026-10-14T12:00:00Z")) {
  const pending = new Map();
  let next = 0;
  return {
    now: () => at,
    later(run, wait) {
      pending.set(++next, { run, wait });
      return next;
    },
    cancel(timer) {
      pending.delete(timer);
    },
    waits: () => [...pending.values()].map((timer) => timer.wait),
    // The pending timer runs, after its wait.
    run() {
      const [[timer, { run, wait }]] = pending;
      pending.delete(timer);
      at += wait;
      run();
    },
  };
}

test("the page speaks the language of its address, else the reader's, else English", () => {
  assert.equal(pickLanguage("?lang=fr", ["de-DE"]), "fr");
  assert.equal(pickLanguage("?lang=xx", ["pt-BR", "NL-be"]), "nl");
  assert.equal(pickLanguage("", ["es-419"]), "es");
  assert.equal(pickLanguage("", [null, "ja"]), "en");
  assert.equal(pickLanguage(""), "en");
  assert.deepEqual(LANGUAGES, Object.keys(TEXT));
});

test("every text of the page is there in every language", () => {
  for (const language of LANGUAGES) assert.deepEqual(Object.keys(TEXT[language]), Object.keys(TEXT.en), language);
  // French puts a no-break space before a colon.
  assert.match(TEXT.fr.notice, /\u00a0:/);
});

test("the moments of the recording move, and nothing else", () => {
  const value = {
    at: "2026-03-14T19:30:00.500000+00:00",
    day: "2026-03-14",
    list: ["2026-03-14T19:30:00Z", 3, null, true],
  };
  assert.deepEqual(shifted(value, 60000), {
    at: "2026-03-14T19:31:00.500Z",
    day: "2026-03-14",
    list: ["2026-03-14T19:31:00.000Z", 3, null, true],
  });
  assert.equal(shifted("Throw", 1), "Throw");
});

test("the replay plays the steps at their pace, faster on demand, and starts again", () => {
  const time = clock();
  const replay = new Replay(TIMELINE, time);
  const seen = [];
  replay.onChange(() => seen.push(replay.index));
  // The first step: its states as Home Assistant sends them, at the time of the replay.
  const first = replay.states["sensor.a"];
  assert.equal(first.state, "1");
  assert.equal(first.attributes.since, new Date(time.now()).toISOString());
  assert.deepEqual(first.attributes.list, [new Date(time.now()).toISOString(), 3]);
  assert.equal(first.last_changed, new Date(time.now()).toISOString());
  assert.equal(replay.chapter(), "x01");
  assert.equal(replay.progress(), 0);
  assert.deepEqual(time.waits(), []);

  replay.play();
  assert.deepEqual(time.waits(), [1000]);
  time.run();
  assert.equal(replay.states["sensor.a"].state, "2");
  assert.deepEqual(replay.positions[""].positions, [[0, 0.6]]);
  // A long wait between two steps is cut short.
  assert.deepEqual(time.waits(), [LONGEST_WAIT]);
  replay.setSpeed(2);
  assert.deepEqual(time.waits(), [LONGEST_WAIT / 2]);
  time.run();
  assert.equal(replay.states["sensor.b"], undefined);
  assert.equal(replay.chapter(), "x01");
  time.run();
  assert.equal(replay.chapter(), "cricket");
  assert.equal(replay.progress(), 1);
  // After the last step, the games start again from the first one.
  assert.deepEqual(time.waits(), [AGAIN / 2]);
  time.run();
  assert.equal(replay.index, 1);
  assert.deepEqual(Object.keys(replay.states), ["sensor.a", "sensor.b"]);
  assert.deepEqual(time.waits(), [LONGEST_WAIT / 2]);

  replay.toggle();
  assert.equal(replay.playing, false);
  assert.deepEqual(time.waits(), []);
  replay.toggle();
  assert.equal(replay.playing, true);
  replay.pause();
  assert.deepEqual(seen, [0, 1, 1, 2, 3, 1, 1, 1, 1]);
});

test("the cards get positions, states and actions that change nothing", async () => {
  const replay = new Replay(TIMELINE, clock());
  replay.seek(1);
  let told = 0;
  const hass = hassOf(replay, {
    entities: {},
    devices: {},
    language: "de",
    dark: true,
    timeZone: "Europe/Berlin",
    notice: () => told++,
  });
  assert.equal(hass.states, replay.states);
  assert.equal(hass.locale.language, "de");
  assert.equal(hass.themes.darkMode, true);
  assert.equal(hass.config.time_zone, "Europe/Berlin");
  await hass.callService("switch", "turn_off", {});
  assert.equal(told, 1);
  assert.deepEqual(await hass.callWS({ type: "homedarts/positions", device_id: "demo-board" }), {
    player: null,
    positions: [[0, 0.6]],
  });
  assert.deepEqual(await hass.callWS({ type: "homedarts/positions", player: "Kim" }), {
    player: "Kim",
    known: false,
    positions: [],
    spread: [],
  });
  replay.seek(0);
  assert.equal((await hass.callWS({ type: "homedarts/positions" })).player, null);
  await assert.rejects(hass.callWS({ type: "auth/sign_path" }), { code: "not_supported" });
});

test("the demo draws the cards and icons of Home Assistant itself", () => {
  defineHomeElements(window);
  const card = window.customElements.get("ha-card");
  defineHomeElements(window);
  assert.equal(window.customElements.get("ha-card"), card);
  const element = window.document.createElement("ha-card");
  window.document.body.append(element);
  const root = element.shadowRoot;
  assert.ok(root.querySelector("slot"));
  element.remove();
  window.document.body.append(element);
  assert.equal(element.shadowRoot, root);
  const icon = window.document.createElement("ha-icon");
  window.document.body.append(icon);
  assert.ok(icon.shadowRoot.querySelector("svg"));
});

// The window of the page: happy-dom's document and elements, with an address, the
// reader's settings and timers of the test.
function page({ search = "", languages, dark = false, still = true, fetch } = {}) {
  window.document.body.innerHTML = BODY;
  const changes = [];
  const pending = [];
  const view = {
    document: window.document,
    customElements: window.customElements,
    HTMLElement: window.HTMLElement,
    location: { search, href: `http://localhost/demo/index.html${search}` },
    navigator: { languages },
    history: {
      replaceState(_state, _title, address) {
        view.location.href = String(address);
      },
    },
    matchMedia: (query) => ({
      matches: query.includes("reduced-motion") ? still : dark,
      addEventListener: (_type, listener) => changes.push(listener),
    }),
    fetch: fetch ?? (async () => ({ ok: true, json: async () => RECORDING })),
    setTimeout(run) {
      pending.push(run);
      return pending.length;
    },
    clearTimeout() {},
  };
  return { view, changes, pending };
}

const $ = (selector) => window.document.querySelector(selector);
const inCard = (tag, selector) => $(tag).shadowRoot.querySelector(selector);

test("a page whose games don't load says so", async () => {
  const { view } = page({ fetch: async () => ({ ok: false, status: 404 }) });
  await assert.rejects(boot({ window: view, load: loadCards }), /timeline.json: 404/);
  assert.equal($("#status").textContent, TEXT.en.failed);
  assert.equal(window.document.documentElement.lang, "en");
});

test("the page plays the recorded games with the cards, in the reader's language", async () => {
  const { view, changes, pending } = page({ languages: ["de-DE"] });
  const replay = await boot({ window: view, load: loadCards });
  try {
    assert.equal(window.document.documentElement.lang, "de");
    assert.equal(window.document.title, TEXT.de.page_title);
    assert.equal($("h1").textContent, TEXT.de.title);
    assert.equal($("#status").textContent, "");
    assert.equal($("#progress").getAttribute("aria-label"), TEXT.de.progress);
    // The header leads to the German pages of the website.
    assert.equal($("[data-page='installation']").getAttribute("href"), "../de/installation.html");
    assert.equal($("[data-page='cards']").getAttribute("href"), "../de/cards.html");
    assert.equal($("[data-page='index']").getAttribute("href"), "../de/index.html");
    // A reader who asked for less motion starts the games with the button.
    assert.equal(replay.playing, false);
    assert.equal($("#play").textContent, TEXT.de.play);
    const cards = [...window.document.querySelectorAll("[data-card] > *")].map((card) => card.localName);
    assert.deepEqual(cards, [
      "homedarts-scoreboard-card",
      "homedarts-card",
      "homedarts-training-card",
      "homedarts-players-card",
    ]);
    const chapters = [...$("#chapters").children];
    assert.deepEqual(
      chapters.map((button) => button.textContent),
      ["501 gegen den Bot", "Cricket", "Turnier"]
    );

    $("#play").click();
    assert.equal(replay.playing, true);
    assert.equal($("#play").textContent, TEXT.de.pause);
    // The label carries the state; a toggle state would announce it twice.
    assert.equal($("#play").hasAttribute("aria-pressed"), false);
    chapters[2].click();
    assert.equal(replay.chapter(), "tournament");
    assert.equal(chapters[2].getAttribute("aria-current"), "true");
    assert.equal(chapters[0].getAttribute("aria-current"), "false");
    $("#speed").value = "4";
    $("#speed").dispatchEvent(new window.Event("change"));
    assert.equal(replay.speed, 4);
    replay.pause();

    // A button of a card, or the details of an entity, only say that this is a recording.
    inCard("homedarts-card", "button[data-action='toggle']").click();
    await settle();
    assert.equal($("#notice").hidden, false);
    assert.equal($("#notice").textContent, TEXT.de.notice);
    pending.at(-1)();
    assert.equal($("#notice").hidden, true);
    window.document.dispatchEvent(new window.CustomEvent("hass-more-info", { detail: { entityId: "x" } }));
    assert.equal($("#notice").hidden, false);

    // Another language changes the page, the cards and the address.
    $("#language").value = "fr";
    $("#language").dispatchEvent(new window.Event("change"));
    assert.equal(window.document.documentElement.lang, "fr");
    assert.equal($("h1").textContent, TEXT.fr.title);
    assert.equal(chapters[1].textContent, TEXT.fr.cricket);
    assert.match(view.location.href, /\?lang=fr$/);
    // The header leads to the French website, which shows the card guide in English.
    assert.equal($("[data-page='installation']").getAttribute("href"), "../fr/installation.html");
    assert.equal($("[data-page='cards']").getAttribute("href"), "../fr/cards.html");
    assert.equal($("homedarts-scoreboard-card")._hass.language, "fr");
    // A dark theme of the system reaches the cards.
    changes[0]();
    assert.equal($("homedarts-card")._hass.themes.darkMode, false);

    // The last step: Kim wins the tournament.
    replay.seek(replay.steps.length - 1);
    await settle();
    assert.match($("homedarts-scoreboard-card").shadowRoot.textContent, /Kim/);
  } finally {
    replay.pause();
  }
});

test("the games start on their own, in the language of the address", async () => {
  const { view } = page({ search: "?lang=es", still: false, dark: true });
  const replay = await boot({ window: view, load: loadCards });
  try {
    assert.equal(replay.playing, true);
    assert.equal(window.document.documentElement.lang, "es");
    assert.equal($("#language").value, "es");
    assert.equal($("homedarts-card")._hass.themes.darkMode, true);
  } finally {
    replay.pause();
  }
});
