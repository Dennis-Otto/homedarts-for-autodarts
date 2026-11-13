// The oldest browsers the cards are made for, as docs/scoreboard.md#browsers names them: an
// old tablet on the wall is the screen many people put at their board. A web feature that is
// newer than this floor either has a fallback, so that the cards still work without it, or
// stays out of the cards. The table knows the features the cards use and those they must not
// use without a fallback; a feature that is in neither isn't checked, so add a new one here.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

import { $, READY, loadCards, makeHass, mount } from "./dom.mjs";

await loadCards();

const FLOOR = { safari: 16.4, chrome: 111, firefox: 121 };
const FRONTEND = new URL("../../custom_components/homedarts/frontend/", import.meta.url);
const SOURCES = [
  ...["homedarts-card.js", "homedarts-strategy.js"].map((name) => new URL(name, FRONTEND)),
  ...readdirSync(new URL("text/", FRONTEND)).map((name) => new URL(`text/${name}`, FRONTEND)),
].map((url) => readFileSync(url, "utf8"));
const CARDS = SOURCES[0];

// The first version of each browser that has the feature (MDN's browser compatibility
// data; Infinity: not in that browser when the row was written); `fallback` says why the
// cards still work in an older one.
const FEATURES = [
  { name: "color-mix()", pattern: /color-mix\(/, safari: 16.2, chrome: 111, firefox: 113 },
  { name: "container queries", pattern: /@container\b/, safari: 16, chrome: 105, firefox: 110 },
  { name: "container query units", pattern: /\d(?:cqi|cqb|cqw|cqh|cqmin|cqmax)\b/, safari: 16, chrome: 105, firefox: 110 },
  { name: ":has()", pattern: /:has\(/, safari: 15.4, chrome: 105, firefox: 121 },
  { name: "dynamic viewport units", pattern: /\d(?:dvh|dvw|svh|svw|lvh|lvw)\b/, safari: 15.4, chrome: 108, firefox: 101 },
  { name: "overflow: clip", pattern: /overflow(?:-[xy])?: clip/, safari: 16, chrome: 90, firefox: 81 },
  { name: "<dialog>", pattern: /showModal\(/, safari: 15.4, chrome: 37, firefox: 98 },
  { name: "Array.prototype.at()", pattern: /\.at\(/, safari: 15.4, chrome: 92, firefox: 90 },
  { name: "Object.hasOwn()", pattern: /Object\.hasOwn\(/, safari: 15.4, chrome: 93, firefox: 92 },
  { name: "Array.prototype.findLast()", pattern: /\.findLast(?:Index)?\(/, safari: 15.4, chrome: 97, firefox: 104 },
  { name: "change array by copy", pattern: /\.(?:toSorted|toReversed|toSpliced)\(/, safari: 16, chrome: 110, firefox: 115 },
  {
    name: "subgrid", pattern: /subgrid/, safari: 16, chrome: 117, firefox: 71,
    fallback: "a plain column template comes before it (checked below)",
  },
  {
    name: "@starting-style", pattern: /@starting-style/, safari: 17.5, chrome: 117, firefox: 129,
    fallback: "an entry animation: without it the element appears at once",
  },
  {
    name: "text-wrap: balance and pretty", pattern: /text-wrap: (?:balance|pretty)/, safari: 17.5, chrome: 114, firefox: 121,
    fallback: "nicer line breaks: without it the lines break as usual",
  },
  {
    name: "popover", pattern: /\.showPopover\(/, safari: 17, chrome: 114, firefox: 125,
    fallback: "the stream overlay asks for showPopover first and stays inside its card without it",
  },
  // Not used, and void in a browser at the floor: a new use needs a fallback first.
  { name: "light-dark()", pattern: /light-dark\(/, safari: 17.5, chrome: 123, firefox: 120 },
  { name: "CSS nesting", pattern: /^\s*&[\s.:[]/m, safari: 16.5, chrome: 112, firefox: 117 },
  { name: "relative colours", pattern: /(?:rgb|hsl|hwb|lab|lch|oklab|oklch|color)a?\(from\s/, safari: 18, chrome: 119, firefox: 128 },
  { name: "@scope", pattern: /@scope\b/, safari: 17.4, chrome: 118, firefox: 146 },
  { name: "@property", pattern: /@property\b/, safari: 16.4, chrome: 85, firefox: 128 },
  { name: "style queries", pattern: /@container\s+style\(/, safari: 18, chrome: 111, firefox: Infinity },
  { name: "anchor positioning", pattern: /anchor-name|position-anchor/, safari: 26, chrome: 125, firefox: Infinity },
  { name: "field-sizing", pattern: /field-sizing/, safari: Infinity, chrome: 123, firefox: Infinity },
  { name: "content-visibility", pattern: /content-visibility/, safari: 18, chrome: 85, firefox: 125 },
  { name: "Object.groupBy()", pattern: /(?:Object|Map)\.groupBy\(/, safari: 17.4, chrome: 117, firefox: 119 },
  { name: "Promise.withResolvers()", pattern: /Promise\.withResolvers\(/, safari: 17.4, chrome: 119, firefox: 121 },
  { name: "Set methods", pattern: /\.(?:union|intersection|symmetricDifference|isSubsetOf)\(/, safari: 17, chrome: 122, firefox: 127 },
  { name: "Intl.Segmenter", pattern: /Intl\.Segmenter/, safari: 14.1, chrome: 87, firefox: 125 },
  { name: "Array.fromAsync()", pattern: /Array\.fromAsync\(/, safari: 16.4, chrome: 121, firefox: 115 },
];

const BROWSERS = Object.keys(FLOOR);
const newerThanTheFloor = (feature) => BROWSERS.filter((browser) => feature[browser] > FLOOR[browser]);
const used = (feature) => SOURCES.some((source) => feature.pattern.test(source));

test("every feature of the cards works at the floor or has a fallback", () => {
  const missing = FEATURES.filter((feature) => used(feature) && !feature.fallback && newerThanTheFloor(feature).length)
    .map((feature) => `${feature.name}: ${newerThanTheFloor(feature).map((browser) => `${browser} ${feature[browser]}`).join(", ")}`);
  assert.deepEqual(missing, [], "newer than the floor of docs/scoreboard.md#browsers, without a fallback");
});

test("a fallback is only named where the floor needs one", () => {
  // A feature that every browser at the floor has needs no excuse, and the table stays true.
  assert.deepEqual(FEATURES.filter((feature) => feature.fallback && !newerThanTheFloor(feature).length), []);
});

test("the check finds a feature that is newer than the floor", () => {
  const nesting = FEATURES.find((feature) => feature.name === "CSS nesting");
  assert.ok(nesting.pattern.test("  .card {\n    & .title { color: red; }\n  }"));
  assert.ok(!nesting.pattern.test("  return a\n    && b;"));
  assert.deepEqual(newerThanTheFloor(nesting), ["safari", "chrome"]);
  assert.equal(used(nesting), false);
});

test("the fallbacks the table promises are in the cards", () => {
  // A plain column template before each subgrid, which an older browser keeps.
  for (const match of CARDS.matchAll(/grid-template-columns: subgrid/g)) {
    const rule = CARDS.slice(CARDS.lastIndexOf("{", match.index), match.index);
    assert.match(rule, /grid-template-columns: (?!subgrid)[^;]+;/);
  }
  // The stream overlay asks before it takes a popover.
  assert.match(CARDS, /typeof stage\.showPopover === "function"/);
});

test("a colour made with color-mix() keeps a plain colour in a browser without it", () => {
  // A custom property made of color-mix() is void in an older browser, and the text that
  // takes its colour from it loses it. Each one gets a plain colour of the theme there.
  const mixed = new Set([...CARDS.matchAll(/(--[a-z0-9-]+): color-mix\(/g)].map((match) => match[1]));
  const plain = new Set();
  for (const block of CARDS.matchAll(/@supports not \(color: color-mix\(in srgb, red, blue\)\) \{([\s\S]*?)\n {2}\}/g)) {
    for (const [, name, value] of block[1].matchAll(/(--[a-z0-9-]+): ([^;]+);/g)) {
      assert.doesNotMatch(value, /color-mix/);
      plain.add(name);
    }
  }
  assert.ok(mixed.size >= 9);
  assert.deepEqual([...mixed].filter((name) => !plain.has(name)), []);
});

test("every card carries the plain colours for an older browser", () => {
  const card = mount("homedarts-status-card", makeHass({ states: READY, device: { primary_config_entry: "01JENTRY" } }), {});
  const style = $(card, "style").textContent;
  assert.match(style, /@supports not \(color: color-mix\(in srgb, red, blue\)\) \{\s*:host \{\s*--ad-ok-text: var\(--success-color/);
});

test("the documentation names the floor", () => {
  const pages = ["scoreboard.md", "scoreboard.de.md", "troubleshooting.md", "troubleshooting.de.md",
    "faq.md", "faq.de.md", "faq.es.md", "faq.fr.md", "faq.nl.md"];
  for (const page of pages) {
    const text = readFileSync(new URL(`../../docs/${page}`, import.meta.url), "utf8");
    for (const version of [`Safari ${FLOOR.safari}`, `${FLOOR.chrome}`, `Firefox ${FLOOR.firefox}`]) {
      assert.ok(text.includes(version), `${page} names ${version}`);
    }
  }
});
