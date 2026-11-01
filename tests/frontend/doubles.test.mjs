// The doubles card: every double hit, and hit rates per double, for everybody or one player.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  dashboardStrategy,
  doubleColor, heatColor,
  doublesHtml,
  doublesView,
} from "../../custom_components/homedarts/frontend/homedarts-card.js";

const doubles = {
  state: "D16",
  attributes: {
    attempts: 42,
    hits: 13,
    rate: 31,
    doubles: [
      { double: "D16", attempts: 20, hits: 9, rate: 45 },
      { double: "D20", attempts: 20, hits: 3, rate: 15 },
      { double: "BULL", attempts: 2, hits: 1 },
      { double: "S20", attempts: 5, hits: 5 },
      { double: "D8", attempts: 0, hits: 0 },
    ],
    landed: { D16: 12, D20: 3, BULL: 1, D7: 2 },
  },
};
const profiles = {
  state: "1",
  attributes: {
    players: [{ name: "Alex", doubles: { attempts: 10, hits: 4, rate: 40, favourite: null, doubles: [{ double: "D8", attempts: 10, hits: 4, rate: 40 }] } }],
  },
};

test("without sensors nobody has doubles yet", () => {
  const empty = { attempts: 0, hits: 0, rate: null, favourite: null, landed: 0, doubles: [] };
  assert.deepEqual(doublesView(undefined, undefined), { player: null, known: true, ...empty });
  assert.deepEqual(doublesView(undefined, { state: "0", attributes: {} }, "Lea"), { player: "Lea", known: false, ...empty });
});

test("everybody's doubles or one player's", () => {
  const all = doublesView(doubles, profiles);
  assert.deepEqual([all.player, all.favourite, all.attempts, all.rate, all.landed], [null, "D16", 42, 31, 18]);
  // From D1 to D20, the bull last; D7 was only hit while aiming elsewhere.
  assert.deepEqual(
    all.doubles.map((item) => [item.double, item.rate, item.landed]),
    [
      ["D7", null, 2],
      ["D16", 45, 12],
      ["D20", 15, 3],
      ["BULL", 50, 1],
    ]
  );
  const alex = doublesView(doubles, profiles, " alex ");
  assert.deepEqual([alex.player, alex.known, alex.attempts, alex.doubles[0].double], ["Alex", true, 10, "D8"]);
  const nobody = doublesView(doubles, profiles, "Kim");
  assert.deepEqual([nobody.player, nobody.known, nobody.doubles], ["Kim", false, []]);
  assert.equal(doublesView({ state: "unknown", attributes: {} }).favourite, null);
});

test("colours follow the heatmap up to one hit in two and the list starts with the best double", () => {
  assert.equal(doubleColor(-5), heatColor(0));
  assert.equal(doubleColor(25), heatColor(0.5));
  assert.equal(doubleColor(50), heatColor(1));
  assert.equal(doubleColor(90), heatColor(1));
  // The former scale, for those who prefer it.
  assert.equal(doubleColor(0, "thermal"), "hsl(0 70% 46%)");
  assert.equal(doubleColor(50, "thermal"), "hsl(130 70% 46%)");
  assert.equal(doubleColor(90, "thermal"), "hsl(130 70% 46%)");
  const texts = { doubles_landed: "hit {count}×", doubles_landed_short: "{count}×", doubles_aimed: "aimed" };
  const html = doublesHtml(doublesView(doubles, profiles), {
    t: (key) => texts[key],
    format: (value, digits) => value.toFixed(digits),
    percent: (value, digits) => `${value.toFixed(digits)} %`,
    label: (key) => (key === "BULL" ? "Bull" : key),
  });
  assert.match(html.list, /^<div class="double" title="hit 1× · 1\/2 aimed"><span class="bed"[^>]*>Bull<\/span>/);
  assert.match(
    html.list,
    /<div class="double favourite"[^>]*><span class="bed"[^>]*>D16<\/span>.*<span class="landed">12×<\/span><span class="count">9\/20<\/span><span class="rate">45 %<\/span>/
  );
  assert.match(html.list, /<span class="bed"[^>]*>D7<\/span>.*<span class="landed">2×<\/span><span class="count"><\/span><span class="rate">–<\/span><\/div>$/);
  assert.equal((html.ring.match(/<path /g) || []).length, 4);
  assert.match(html.ring, /<title>D20: hit 3× · 3\/20 aimed<\/title>/);
});

test("the training view shows the doubles card once the sensor exists", () => {
  const entity = (entity_id, translation_key) => ({ entity_id, translation_key, device_id: "dev1", platform: "homedarts" });
  const config = dashboardStrategy({
    locale: { language: "en" },
    entities: Object.fromEntries(
      [entity("sensor.b_darts", "training_darts"), entity("sensor.b_double", "favourite_double")].map((item) => [
        item.entity_id,
        item,
      ])
    ),
    devices: { dev1: { id: "dev1" } },
    states: {},
  });
  const training = config.views.find((view) => view.path === "training");
  assert.equal(training.sections[1].cards[0].type, "custom:homedarts-doubles-card");
});
