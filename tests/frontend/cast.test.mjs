// Home Assistant Cast: its receiver shows dashboards on a TV through Chromecast. It defines
// hc-main instead of Home Assistant's app element and loads both modules as dashboard
// resources, from the address of Home Assistant, while its own page has another address.
import assert from "node:assert/strict";
import { test } from "node:test";

// The browser comes first; the modules then wait for an app element.
import { makeHass, mount, READY, settle } from "./dom.mjs";
import {
  APP_ELEMENTS,
  frontendReady,
  personLinks,
  pictureUrl,
} from "../../custom_components/homedarts/frontend/homedarts-card.js";
import { appReady } from "../../custom_components/homedarts/frontend/homedarts-strategy.js";

const STRATEGY = "ll-strategy-dashboard-homedarts";
const HOME_ASSISTANT = "https://homeassistant.example.org:8123";
// Home Assistant's own addresses for its pictures, as the frontend and the receiver have it.
const hassUrl = (path = "") => new URL(path, HOME_ASSISTANT).toString();

test("the strategy and the cards register in the receiver of Home Assistant Cast", async () => {
  await settle();
  assert.equal(customElements.get(STRATEGY), undefined);
  assert.equal(customElements.get("homedarts-scoreboard-card"), undefined);

  customElements.define("hc-main", class extends HTMLElement {});
  await customElements.whenDefined(STRATEGY);
  await customElements.whenDefined("homedarts-scoreboard-card");
  assert.equal(customElements.get("home-assistant"), undefined);
  const dashboard = await customElements.get(STRATEGY).generate({}, makeHass({ states: READY }));
  assert.ok(dashboard.views.some((view) => view.path === "scoreboard"));
});

test("modules that the receiver loads while it runs register at once", async (t) => {
  // Defined by the test before, unless this one runs alone.
  if (!customElements.get("hc-main")) customElements.define("hc-main", class extends HTMLElement {});
  await customElements.whenDefined(STRATEGY);
  await customElements.whenDefined("homedarts-scoreboard-card");
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const timers = t.mock.method(globalThis, "setTimeout");
  // The receiver loads its dashboard resources after hc-main is defined.
  await frontendReady();
  assert.equal(timers.mock.callCount(), 0);
  assert.deepEqual(APP_ELEMENTS, ["home-assistant", "hc-main"]);
});

test("the strategy waits for either app element", async () => {
  for (const app of APP_ELEMENTS) {
    const waits = [];
    const registry = {
      whenDefined: (name) => {
        waits.push(name);
        return name === app ? Promise.resolve() : new Promise(() => {});
      },
    };
    await appReady(registry);
    assert.deepEqual(waits, APP_ELEMENTS);
  }
});

test("pictures of Home Assistant carry its address, which the receiver needs", () => {
  const hass = { hassUrl };
  assert.equal(
    pictureUrl("/api/image/serve/alex/512x512", hass),
    "https://homeassistant.example.org:8123/api/image/serve/alex/512x512"
  );
  // Pictures from the web stay as they are, and a host without the address keeps the path.
  assert.equal(pictureUrl("https://example.com/a.png", hass), "https://example.com/a.png");
  assert.equal(pictureUrl("/api/image/serve/alex/512x512", {}), "/api/image/serve/alex/512x512");
  assert.equal(pictureUrl("//evil.example/a.png", hass), null);

  const people = makeHass();
  people.hassUrl = hassUrl;
  people.states["person.alex"] = {
    entity_id: "person.alex",
    state: "home",
    attributes: { entity_picture: "/api/image/serve/alex/512x512" },
  };
  const profiles = { attributes: { players: [{ name: "Alex", person: "person.alex" }] } };
  assert.equal(
    personLinks(people, profiles).get("alex").picture,
    "https://homeassistant.example.org:8123/api/image/serve/alex/512x512"
  );
});

test("the scoreboard on the TV has no full-screen button: the receiver fills the screen anyway", async (t) => {
  // Defined by the first test, unless this one runs alone.
  if (!customElements.get("hc-main")) customElements.define("hc-main", class extends HTMLElement {});
  await customElements.whenDefined("homedarts-scoreboard-card");
  // A browser engine that offers full screen, as the receiver's may.
  Object.defineProperty(document, "fullscreenEnabled", { configurable: true, value: true });
  t.after(() => delete document.fullscreenEnabled);
  const card = mount("homedarts-scoreboard-card", makeHass({ states: READY }));
  assert.equal(card.shadowRoot.querySelector(".fullscreen-toggle").hidden, true);
});
