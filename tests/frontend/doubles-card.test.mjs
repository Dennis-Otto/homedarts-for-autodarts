// The doubles card in a browser DOM: every double hit, and the hit rate of the doubles
// darts were aimed at, for everybody or one player.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, loadCards, makeHass, mount, text, update } from "./dom.mjs";

const { bedPath } = await loadCards();

const DOUBLES = [
  { double: "D16", attempts: 40, hits: 20, rate: 50 },
  { double: "D20", attempts: 50, hits: 12, rate: 24 },
  { double: "BULL", attempts: 30, hits: 10 },
  { double: "D99", attempts: 5, hits: 1 },
];
// Every dart in a double, whatever it was aimed at: D3 only while aiming elsewhere.
const LANDED = { D16: 26, D20: 15, BULL: 10, D3: 4, S20: 9, D0: 2, D5: 0, D6: 1.5 };
const favourite = (state, attributes) => ({ "sensor.favourite_double": { state, attributes } });
const EVERYBODY = favourite("D16", { attempts: 120, hits: 42, rate: 35, doubles: DOUBLES, landed: LANDED });
const PROFILES = {
  "sensor.player_profiles": {
    state: "1",
    attributes: {
      players: [
        {
          name: "Lea",
          doubles: { attempts: 12, hits: 3, rate: 25, doubles: [{ double: "D8", attempts: 12, hits: 3 }] },
          hits: { D8: 3, D12: 2, T20: 5 },
        },
      ],
    },
  },
};
const setup = (states, config = {}, options = {}) => {
  const hass = makeHass({ states, ...options });
  return { hass, card: mount("homedarts-doubles-card", hass, config) };
};
const list = (card) =>
  $$(card, ".double").map((item) => [
    item.className,
    item.querySelector(".bed").textContent,
    item.querySelector(".bar i").style.width,
    item.querySelector(".landed").textContent,
    item.querySelector(".count").textContent,
    item.querySelector(".rate").textContent,
  ]);
const fills = (card) => $$(card, ".ring path").map((path) => path.getAttribute("style"));

test("the doubles card shows every double hit, the aimed ones coloured by their hit rate", () => {
  const { card } = setup({ ...EVERYBODY, ...PROFILES });
  assert.equal(text(card, ".title"), "Doubles");
  assert.equal(text(card, ".meta"), "55 doubles hit · 120 darts at a double · 35.0%");
  assert.equal($(card, ".empty").hidden, true);
  assert.equal($(card, ".doubles-body").hidden, false);
  assert.equal($(card, "svg").getAttribute("aria-label"), "Doubles");
  // From D1 to D20, the bull last.
  assert.deepEqual(
    $$(card, ".ring path").map((path) => [path.getAttribute("d"), path.textContent]),
    [
      [bedPath("D3"), "D3: hit 4×"],
      [bedPath("D16"), "D16: hit 26× · 20/40 aimed"],
      [bedPath("D20"), "D20: hit 15× · 12/50 aimed"],
      [bedPath("Bull"), "Bull: hit 10× · 10/30 aimed"],
    ]
  );
  // A double hit only while aiming elsewhere takes the accent, the stronger the more hits.
  assert.deepEqual(fills(card), [
    "fill:color-mix(in srgb, var(--ad-accent) 43%, transparent)",
    "fill:#f1e323",
    "fill:#32aca3",
    "fill:#55ca86",
  ]);
  // The legend tells the colours of the rates, from none to about every second dart.
  assert.deepEqual($$(card, ".legend span").map((end) => end.textContent), ["0%", "50%+"]);
  assert.match($(card, ".legend-bar").getAttribute("style"), /linear-gradient\(90deg, #5844bc, .*, #f1e323\)/);
  assert.equal(card.getCardSize(), 6);
});

test("the thermal palette keeps the former red to green of the doubles card", () => {
  const { card } = setup(EVERYBODY, { heatmap_palette: "thermal" });
  assert.deepEqual(fills(card).slice(1), ["fill:hsl(130 70% 46%)", "fill:hsl(62 70% 46%)", "fill:hsl(87 70% 46%)"]);
  assert.match($(card, ".legend-bar").getAttribute("style"), /linear-gradient\(90deg, hsl\(0 70% 46%\), .*, hsl\(130 70% 46%\)\)/);
});

test("the list ranks the aimed doubles by hit rate, then the others by their hits", () => {
  const { hass, card } = setup(EVERYBODY);
  assert.deepEqual(list(card), [
    ["double favourite", "D16", "100%", "26×", "20/40", "50%"],
    ["double", "Bull", "38%", "10×", "10/30", "33%"],
    ["double", "D20", "58%", "15×", "12/50", "24%"],
    ["double", "D3", "15%", "4×", "", "–"],
  ]);
  assert.equal($(card, ".double").getAttribute("title"), "hit 26× · 20/40 aimed");
  // The same rate ranks the double with more darts first; without counted hits, the
  // aimed hits are hits of the double.
  const tied = [
    { double: "D1", attempts: 4, hits: 1, rate: 25 },
    { double: "D2", attempts: 8, hits: 2, rate: 25 },
  ];
  card.hass = update(hass, favourite("D2", { attempts: 12, hits: 3, rate: 25, doubles: tied }));
  assert.deepEqual(
    list(card).map((item) => [item[1], item[3]]),
    [
      ["D2", "2×"],
      ["D1", "1×"],
    ]
  );
});

test("one player's doubles come from the profiles, with every double they hit", () => {
  const { card } = setup({ ...EVERYBODY, ...PROFILES }, { player: " lea " });
  assert.equal(text(card, ".title"), "Doubles · Lea");
  assert.equal(text(card, ".meta"), "5 doubles hit · 12 darts at a double · 25.0%");
  assert.deepEqual(list(card), [
    ["double", "D8", "100%", "3×", "3/12", "25%"],
    ["double", "D12", "67%", "2×", "", "–"],
  ]);
  const unknown = setup({ ...EVERYBODY, ...PROFILES }, { player: "Kim" }).card;
  assert.equal(text(unknown, ".title"), "Doubles · Kim");
  assert.equal($(unknown, ".empty").hidden, false);
  // A name without a profile is most likely mistyped.
  assert.equal(
    text(unknown, ".empty"),
    "No doubles of Kim yet. Check the name in the card settings, or throw at doubles in a practice game as Kim."
  );
  const german = setup(PROFILES, { player: "Kim" }, { language: "de" }).card;
  assert.match(text(german, ".empty"), /^Noch keine Doubles von Kim\./);
});

test("the card fills with the first double hit and explains what a hit rate needs", () => {
  const { hass, card } = setup(favourite("unknown", { attempts: 0, hits: 0, rate: null, doubles: [] }));
  assert.equal($(card, ".empty").hidden, false);
  assert.equal($(card, ".doubles-body").hidden, true);
  assert.equal(
    text(card, ".empty"),
    "Every double you hit shows up here. Its hit rate needs darts aimed at it: X01 with double out, the doubles training, Bob's 27 and the checkout games."
  );
  assert.equal(text(card, ".meta"), "");
  // Doubles hit in a game without double out: no rate, but on the board, the most hit
  // first.
  card.hass = update(
    hass,
    favourite("unknown", { attempts: 0, hits: 0, rate: null, doubles: [], landed: { D5: 2, D9: 3 } })
  );
  assert.equal($(card, ".empty").hidden, true);
  assert.equal(text(card, ".meta"), "5 doubles hit");
  assert.deepEqual(list(card), [
    ["double", "D9", "100%", "3×", "", "–"],
    ["double", "D5", "67%", "2×", "", "–"],
  ]);
  card.hass = update(hass, favourite("D20", { attempts: 50, hits: 12, rate: null, doubles: DOUBLES.slice(1, 2) }));
  assert.equal(text(card, ".meta"), "12 doubles hit · 50 darts at a double");
});

test("the doubles card has a configurable title and speaks German", () => {
  assert.equal(text(setup(EVERYBODY, { title: "Finishing" }).card, ".title"), "Finishing");
  const { card } = setup(EVERYBODY, {}, { language: "de" });
  assert.equal(text(card, ".title"), "Doubles");
  assert.equal(text(card, ".meta"), "55 Doubles getroffen · 120 Darts aufs Double · 35,0 %");
  // The long counts never cut the title short: they go below it on a narrow card.
  const style = $(card, "style").textContent;
  assert.match(style, /\.doubles-card > header \.title \{ flex-shrink: 0; \}/);
  assert.match(style, /\.doubles-card > header \.meta \{ flex: 1 1 16em;/);
  assert.deepEqual(
    $$(card, "p.muted").map((note) => note.textContent),
    [
      "× zählt jeden Dart im Double; 3/5 und die Quote zählen die Darts, die aufs Double zielten: X01 mit Double-Out, Doppeltraining, Bob's 27 und die Checkout-Spiele.",
      "Persönliche Checkout-Wege nutzen Doubles mit mindestens 10 Darts.",
    ]
  );
  assert.equal($(card, ".double").getAttribute("title"), "26× getroffen · 20/40 gezielt");
});
