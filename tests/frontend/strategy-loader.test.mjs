// The small module of every page: stand-ins of the cards and of the strategy, registered at
// once, with the card module behind them. The tests of this file run in their order: the
// first ones see a page that has not loaded homedarts-card.js, the later ones one that has.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

import { Window } from "happy-dom";

// The browser comes first; the module then waits for Home Assistant's app element.
import { DEVICE, READY, makeHass, settle, window as page } from "./dom.mjs";
import {
  CARD_MODULE,
  CARDS,
  cardModule,
  loadCards,
  register,
  strategyElement,
} from "../../custom_components/homedarts/frontend/homedarts-strategy.js";

const STRATEGY = "ll-strategy-dashboard-homedarts";
const FRONTEND = new URL("../../custom_components/homedarts/frontend/", import.meta.url);
const CARD = new URL("homedarts-card.js", FRONTEND);
// The first element that only homedarts-card.js defines.
const LOADED = "homedarts-strategy-editor";
const LANGUAGES = readdirSync(new URL("text/", FRONTEND)).map((name) => name.replace(".js", ""));
// Entries as Home Assistant reads them when it opens a picker.
const read = (entries) => entries.map((entry) => ({ ...entry }));
const standIn = (type = "homedarts-card") => document.createElement(type);
const config = (type = "homedarts-card") => ({ type: `custom:${type}` });
const isCard = (card) => card.shadowRoot?.querySelector("ha-card") != null;

test("the stand-ins wait for Home Assistant's app element, then register without the card module", async () => {
  await settle();
  assert.equal(customElements.get(STRATEGY), undefined);

  customElements.define("home-assistant", class extends HTMLElement {});
  await customElements.whenDefined(STRATEGY);
  for (const { type } of CARDS) assert.equal(typeof customElements.get(type), "function", type);
  assert.deepEqual(
    page.customCards.map((card) => card.type),
    CARDS.map((card) => card.type)
  );
  assert.deepEqual(
    page.customStrategies.map(({ type, strategyType, name }) => [type, strategyType, name]),
    [["homedarts", "dashboard", "HomeDarts"]]
  );
  await settle();
  assert.equal(customElements.get(LOADED), undefined);
});

test("the pickers speak the language of the page, from a table of the small module", async () => {
  for (const lang of LANGUAGES) {
    const { default: text } = await import(new URL(`text/${lang}.js`, FRONTEND));
    for (const variant of [lang, `${lang}-XX`]) {
      page.document.documentElement.lang = variant;
      assert.deepEqual(
        read(page.customCards).map(({ name, description }) => [name, description]),
        CARDS.map(({ key }) => [text[`picker_${key}`], text[`picker_${key}_description`]]),
        variant
      );
      assert.equal(page.customStrategies[0].description, text.picker_strategy_description, variant);
    }
  }
  const doubles = page.customCards[5];
  page.document.documentElement.lang = "de";
  assert.match(doubles.documentationURL, /\/de\/cards\.html#doubles-karte$/);
  assert.match(page.customStrategies[0].documentationURL, /\/de\/cards\.html#automatisches-dashboard$/);
  page.document.documentElement.lang = "sv";
  assert.match(doubles.documentationURL, /\/cards\.html#doubles-card$/);
  assert.match(page.customStrategies[0].documentationURL, /\/cards\.html#automatic-dashboard$/);
  // A language without card texts reads English.
  assert.equal(doubles.name, "HomeDarts doubles");
  page.document.documentElement.lang = "en";
});

test("before the card module loads, Home Assistant still gets its answers, and made alone a stand-in loads nothing", async () => {
  for (const { type, size, columns } of CARDS) {
    const card = standIn(type);
    assert.equal(card.getCardSize(), size, type);
    assert.deepEqual(card.getGridOptions(), { columns, min_columns: 6 }, type);
    assert.equal(card.shadowRoot, null);
    // Leaving a page it never showed anything on is nothing to do.
    card.disconnectedCallback();
  }
  await settle();
  assert.equal(customElements.get(LOADED), undefined);
});

test("a failed load leaves the stand-ins waiting, and the next update of Home Assistant loads the cards", async (t) => {
  const warn = t.mock.method(console, "warn", () => {});
  let fail;
  const failing = loadCards(() => new Promise((_, reject) => (fail = reject)));
  const first = makeHass({ states: READY });
  const second = makeHass({ states: READY, language: "de" });

  // The usual card: its settings, its state, what Home Assistant sets on it and its place.
  const shown = standIn();
  shown.setConfig(config());
  shown.hass = first;
  shown.preview = true;
  shown.layout = "grid";
  document.body.append(shown);
  // Settings that a later edit of the dashboard replaced before the module came.
  const edited = standIn("homedarts-status-card");
  edited.setConfig({ ...config("homedarts-status-card"), title: "Old" });
  edited.setConfig({ ...config("homedarts-status-card"), title: "New" });
  // Not on the page yet, as Home Assistant makes a card before it adds it.
  const away = standIn("homedarts-scoreboard-card");
  away.setConfig(config("homedarts-scoreboard-card"));
  // Only on the page, and only with a state.
  const bare = standIn("homedarts-players-card");
  document.body.append(bare);
  const stateOnly = standIn("homedarts-training-card");
  stateOnly.hass = first;
  // Gone again before the module came.
  const gone = standIn("homedarts-doubles-card");
  document.body.append(gone);
  gone.remove();
  // Settings that setConfig of the card refuses: Home Assistant shows them only on a rebuild.
  const invalid = standIn("homedarts-leaderboard-card");
  const rebuilt = [];
  invalid.addEventListener("ll-rebuild", (event) => rebuilt.push(event));
  invalid.setConfig(null);
  invalid.hass = first;

  fail(new Error("offline"));
  await assert.rejects(failing, /offline/);
  await settle();
  assert.equal(customElements.get(LOADED), undefined);
  assert.equal(shown.shadowRoot, null);
  assert.equal(shown.getCardSize(), 7);
  assert.equal(rebuilt.length, 0);
  // A blank card has its reason in the console, once for all the stand-ins of the page.
  assert.deepEqual(
    warn.mock.calls.map(({ arguments: [text, error] }) => [text, error.message]),
    [["HomeDarts: the card module did not load", "offline"]]
  );

  for (const card of [shown, edited, away, bare, stateOnly, gone, invalid]) card.hass = second;
  await loadCards();
  await settle();

  assert.equal(typeof customElements.get(LOADED), "function");
  // The same element is the card now, with the newest of all that it was given.
  assert.ok(isCard(shown));
  assert.equal(shown._hass, second);
  assert.equal(shown.preview, true);
  assert.equal(Object.hasOwn(shown, "preview"), false);
  assert.equal(shown.layout, "grid");
  assert.equal(shown.isConnected, true);
  assert.equal(edited._config.title, "New");
  assert.ok(isCard(away));
  assert.equal(away.isConnected, false);
  for (const card of [bare, stateOnly, gone]) assert.ok(card.shadowRoot, card.localName);
  // The card takes no further state: Home Assistant replaces the element.
  assert.equal(rebuilt.length, 1);
  assert.equal(rebuilt[0].bubbles && rebuilt[0].composed, true);
  assert.equal(invalid._hass, undefined);
});

test("once the module is there, every new element is its card at once", () => {
  for (const { type, size, columns } of CARDS) {
    const card = standIn(type);
    assert.ok(card.shadowRoot, type);
    assert.ok(card instanceof customElements.get(type), type);
    // What the stand-ins answered is what the cards answer.
    assert.equal(card.getCardSize(), size, type);
    assert.deepEqual(card.getGridOptions(), { columns, min_columns: 6 }, type);
    // An error of setConfig reaches Home Assistant at once, as from any card.
    assert.throws(() => card.setConfig(null), /Invalid configuration/);
    card.setConfig(config(type));
    card.hass = makeHass({ states: READY });
    assert.ok(isCard(card), type);
  }
});

test("a browser goes on calling the callbacks of the stand-in, which hand on to the card", (t) => {
  const { prototype } = customElements.get("homedarts-scoreboard-card");
  const card = standIn("homedarts-scoreboard-card");
  const own = Object.getPrototypeOf(card);
  assert.notEqual(own, prototype);
  const connected = t.mock.method(own, "connectedCallback", () => {});
  const disconnected = t.mock.method(own, "disconnectedCallback", () => {});
  prototype.connectedCallback.call(card);
  assert.equal(connected.mock.callCount(), 1);
  prototype.disconnectedCallback.call(card);
  assert.equal(disconnected.mock.callCount(), 1);
});

test("the stub of the card picker and the form of the editor are those of the card", async () => {
  const module = await import(CARD.href);
  const hass = makeHass({ states: READY });
  const cards = module.createElements(HTMLElement);
  for (const { type } of CARDS) {
    const element = customElements.get(type);
    assert.deepEqual(await element.getStubConfig(hass), { device_id: DEVICE }, type);
    assert.deepEqual((await element.getConfigForm()).schema, cards[type].getConfigForm().schema, type);
  }
});

test("the entries of the pickers are those that the card module would make itself", async (t) => {
  const module = await import(CARD.href);
  const other = new Window({ url: "http://localhost:8123/" });
  globalThis.window = other;
  t.after(async () => {
    globalThis.window = page;
    await other.happyDOM.close();
  });
  module.register();
  for (const lang of [...LANGUAGES, "sv"]) {
    document.documentElement.lang = lang;
    // The card module also goes by the language that its cards last saw, the same one.
    standIn().hass = makeHass({ language: lang });
    assert.deepEqual(read(page.customCards), read(other.customCards), lang);
    assert.deepEqual(read(page.customStrategies), read(other.customStrategies), lang);
  }
  document.documentElement.lang = "en";
});

test("the card module is the one beside this module, with the same version", () => {
  assert.equal(CARD_MODULE, CARD.href);
  // Home Assistant loads this module from the folder of the version, which the import keeps.
  assert.equal(
    cardModule("http://homeassistant.local:8123/homedarts/1.16.0-0123abcd/homedarts-strategy.js"),
    "http://homeassistant.local:8123/homedarts/1.16.0-0123abcd/homedarts-card.js"
  );
  // A resource of an earlier release had the version in its query.
  assert.equal(
    cardModule("http://homeassistant.local:8123/homedarts/homedarts-strategy.js?v=1.12.1-0123abcd"),
    "http://homeassistant.local:8123/homedarts/homedarts-card.js?v=1.12.1-0123abcd"
  );
});

test("the strategy builds the dashboard of homedarts-card.js and keeps its element", async () => {
  const card = await import(CARD.href);
  const hass = makeHass();
  const element = customElements.get(STRATEGY);
  assert.deepEqual(await element.generate({}, hass), card.dashboardStrategy(hass, {}));
  // The card module registers the rest and leaves what came first.
  card.register();
  assert.equal(customElements.get(STRATEGY), element);
  assert.equal(page.customStrategies.length, 1);
  assert.equal(page.customCards.length, CARDS.length);
});

test("the strategy's editor is the one of homedarts-card.js", async () => {
  const editor = await customElements.get(STRATEGY).getConfigElement();
  assert.equal(editor.localName, "homedarts-strategy-editor");
});

test("registering again adds nothing, and leaves what the page already knows", (t) => {
  const known = customElements.get(STRATEGY);
  const cards = [...page.customCards];
  register();
  assert.equal(customElements.get(STRATEGY), known);
  assert.deepEqual(page.customCards, cards);
  assert.equal(page.customStrategies.length, 1);
  assert.notEqual(strategyElement(HTMLElement), known);

  const other = new Window({ url: "http://localhost:8123/" });
  const own = class extends other.HTMLElement {};
  other.customElements.define("homedarts-card", own);
  other.customCards = [{ type: "homedarts-card", name: "Mine" }];
  other.customStrategies = [{ type: "homedarts", name: "Mine" }];
  globalThis.window = other;
  t.after(async () => {
    globalThis.window = page;
    await other.happyDOM.close();
  });
  register();
  assert.equal(other.customElements.get("homedarts-card"), own);
  assert.equal(typeof other.customElements.get("homedarts-training-card"), "function");
  assert.equal(other.customCards.length, CARDS.length);
  assert.equal(other.customCards[0].name, "Mine");
  assert.deepEqual(other.customStrategies, [{ type: "homedarts", name: "Mine" }]);
});

test("the small module brings no other module along on every page", () => {
  const source = readFileSync(new URL("homedarts-strategy.js", FRONTEND), "utf-8");
  assert.doesNotMatch(source, /^\s*import\s/m);
});
