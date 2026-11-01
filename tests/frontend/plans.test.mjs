// Training plans on the cards: the step header, Skip and Stop, and the offer of the plan of the day.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { $, $$, DEVICE, READY, loadCards, makeHass, mount, text, update, window } from "./dom.mjs";

const { gameView, planButtons, planMeta, planOffer, planOfferHtml, planView, scoreboardHtml } = await loadCards();

const PLAN = {
  plan: "doubles_day",
  name: "Doubles day",
  step: 2,
  steps: 4,
  drill: "bobs_27",
  drills: ["doubles", "bobs_27", "checkout", "catch_40"],
  darts: 12,
  visits: 4,
  darts_limit: 60,
  rounds_limit: null,
};
const OFFER = { plan: "checkout_day", name: "Checkout day", drills: ["checkout", "catch_40"], done: false };
const IDLE = {
  ...READY,
  "sensor.local_visit_score": { state: "0", attributes: { throws: [] } },
  "sensor.practice_target": { state: "unknown", attributes: { drill: null } },
  "sensor.practice_remaining": { state: "unknown", attributes: { plan: null, plan_of_the_day: OFFER } },
};
const PLAYING = {
  ...IDLE,
  "sensor.practice_target": {
    state: "D2",
    attributes: { drill: "bobs_27", score: 25, progress: 1, targets: 21, darts: 3 },
  },
  "sensor.practice_remaining": { state: "unknown", attributes: { plan: PLAN, plan_of_the_day: OFFER } },
};
const ui = { t: (key) => (key === "plan_step" ? "Step {step} of {steps}: {game}" : key) };

const mounted = (type, states, config = {}) => {
  const hass = makeHass({ states });
  return { hass, card: mount(type, hass, { device_id: DEVICE, ...config }) };
};
const scoreboard = (states, config) => mounted("homedarts-scoreboard-card", states, config);
const live = (states, config) => mounted("homedarts-card", states, config);

test("the plan view reads the practice sensor", () => {
  assert.equal(planView(undefined), null);
  assert.equal(planView({ attributes: {} }), null);
  assert.equal(planView({ attributes: { plan: null } }), null);
  assert.equal(planView({ attributes: { plan: { drill: "501" } } }), null);
  assert.deepEqual(planView({ attributes: { plan: PLAN } }), {
    key: "doubles_day",
    name: "Doubles day",
    step: 2,
    steps: 4,
    drill: "bobs_27",
    darts: 12,
    visits: 4,
    dartsLimit: 60,
    roundsLimit: null,
  });
  // What a broken state lacks has a value that shows.
  assert.deepEqual(planView({ attributes: { plan: { plan: "x", name: "y", drill: "doubles" } } }), {
    key: "x",
    name: "y",
    step: 1,
    steps: 1,
    drill: "doubles",
    darts: 0,
    visits: 0,
    dartsLimit: null,
    roundsLimit: null,
  });
});

test("the offer reads the practice sensor", () => {
  assert.equal(planOffer(undefined), null);
  assert.equal(planOffer({ attributes: {} }), null);
  assert.equal(planOffer({ attributes: { plan_of_the_day: { plan: "" } } }), null);
  assert.deepEqual(planOffer({ attributes: { plan_of_the_day: OFFER } }), {
    key: "checkout_day",
    name: "Checkout day",
    drills: ["checkout", "catch_40"],
    done: false,
  });
  assert.deepEqual(
    planOffer({ attributes: { plan_of_the_day: { plan: "x", name: "y", drills: ["doubles", "501"], done: true } } }),
    { key: "x", name: "y", drills: ["doubles"], done: true }
  );
  assert.deepEqual(planOffer({ attributes: { plan_of_the_day: { plan: "x", name: "y", drills: "doubles" } } }).drills, []);
});

test("the game view carries the plan of a training game, and only then", () => {
  const stateOf = (states) => (name) => ({ drill: states.drill, practice: states.practice })[name];
  const drill = { state: "D2", attributes: { drill: "bobs_27" } };
  const practice = { state: "unknown", attributes: { plan: PLAN } };
  assert.equal(gameView(stateOf({ drill, practice })).plan.step, 2);
  assert.equal("plan" in gameView(stateOf({ drill, practice: { attributes: {} } })), false);
  assert.equal(gameView(stateOf({ practice })).mode, "idle");
});

test("the meta line names the plan and how far a step with a limit is", () => {
  const plan = { key: "own", name: "Evening", dartsLimit: null, roundsLimit: null, darts: 3, visits: 1 };
  const words = { t: (key) => ({ plan_limit_darts: "{value}/{limit} darts", plan_limit_visits: "{value}/{limit} visits" })[key] ?? key };
  assert.equal(planMeta(plan, words), "Evening");
  assert.equal(planMeta({ ...plan, dartsLimit: 60 }, words), "Evening · 3/60 darts");
  assert.equal(planMeta({ ...plan, roundsLimit: 10 }, words), "Evening · 1/10 visits");
  assert.equal(planMeta({ ...plan, key: "warm_up" }, words), "plan_warm_up");
  // A name that is a word of the code is an own plan all the same.
  assert.equal(planMeta({ ...plan, key: "constructor", name: "constructor" }, words), "constructor");
});

test("the buttons of a plan ask again before they do what cannot be undone", () => {
  const words = { t: (key) => key };
  assert.match(planButtons(words, null), /data-plan="skip".*>plan_skip<.*data-plan="stop".*>plan_stop</);
  assert.match(planButtons(words, "plan_skip"), />confirm<.*>plan_stop</);
  assert.match(planButtons(words, "plan_stop"), />plan_skip<.*>confirm</);
});

test("the offer names the plan and its games, or that it is done", () => {
  const words = { t: (key) => ({ plan_of_the_day: "Today: {name}", plan_done: "Done: {name}" })[key] ?? key };
  assert.equal(planOfferHtml(null, words), "");
  const offer = { key: "<own>", name: "Eve & <b>", drills: ["doubles"], done: false };
  const html = planOfferHtml(offer, words);
  assert.match(html, /data-plan="start" data-value="&#60;own&#62;"/);
  assert.match(html, />Today: Eve &#38; &#60;b&#62;</);
  assert.match(html, />drill_doubles</);
  assert.match(planOfferHtml({ ...offer, done: true }, words), />Done: Eve/);
});

test("the scoreboard's header says the step of the plan", () => {
  const view = { mode: "drill", drill: { kind: "bobs_27", score: 25, progress: 1, targets: 21, darts: 3, target: "D2" } };
  const words = { ...ui, format: String, label: String };
  assert.equal(scoreboardHtml(view, words).title, "drill_bobs_27");
  assert.equal(scoreboardHtml(view, words).meta, "");
  const plan = planView({ attributes: { plan: PLAN } });
  const planned = scoreboardHtml({ ...view, plan }, words);
  assert.equal(planned.title, "Step 2 of 4: drill_bobs_27");
  assert.match(planned.meta, /^plan_doubles_day · /);
});

test("the scoreboard shows the step with Skip and Stop, which call the actions after a second tap", () => {
  const { card, hass } = scoreboard(PLAYING);
  assert.equal(text(card, ".title"), "Step 2 of 4: Bob's 27");
  assert.equal(text(card, ".meta"), "Doubles day · 12 / 60 darts");
  const [skip, stop] = $$(card, ".plan-buttons button");
  assert.equal(skip.textContent, "Skip");
  assert.equal(stop.textContent, "Stop");

  skip.click();
  assert.equal(hass.calls.length, 0);
  assert.equal($$(card, ".plan-buttons button")[0].textContent, "Confirm?");
  $$(card, ".plan-buttons button")[0].click();
  assert.deepEqual(hass.calls.at(-1), ["homedarts", "next_plan_step", {}]);

  $$(card, ".plan-buttons button")[1].click();
  assert.equal(hass.calls.length, 1);
  $$(card, ".plan-buttons button")[1].click();
  assert.deepEqual(hass.calls.at(-1), ["homedarts", "stop_plan", {}]);
});

test("a board with an entry names it in the action", () => {
  const hass = makeHass({ states: PLAYING, device: { config_entry_id: "entry-1" } });
  const card = mount("homedarts-scoreboard-card", hass, { device_id: DEVICE });
  $$(card, ".plan-buttons button")[0].click();
  $$(card, ".plan-buttons button")[0].click();
  assert.deepEqual(hass.calls.at(-1), ["homedarts", "next_plan_step", { config_entry_id: "entry-1" }]);
});

test("one tap on the idle screen starts the plan of the day", () => {
  const { card, hass } = scoreboard(IDLE);
  const offer = $(card, ".plan-offer");
  assert.equal(text(card, ".plan-offer-name"), "Plan of the day: Checkout day");
  assert.equal(text(card, ".plan-offer-games"), "Checkout training · Catch 40");
  offer.click();
  assert.deepEqual(hass.calls.at(-1), ["homedarts", "start_plan", { plan: "checkout_day" }]);
});

test("the idle screen says when the plan of the day is done, and offers it again", () => {
  const { card } = scoreboard({
    ...IDLE,
    "sensor.practice_remaining": { state: "unknown", attributes: { plan_of_the_day: { ...OFFER, done: true } } },
  });
  assert.equal(text(card, ".plan-offer-name"), "Done today: Checkout day");
});

test("without an offer, the idle screen stays as it was", () => {
  const { card } = scoreboard({ ...IDLE, "sensor.practice_remaining": "unknown" });
  assert.equal($(card, ".plan-offer"), null);
});

test("a game without a plan shows no buttons of a plan", () => {
  const { card, hass } = scoreboard(IDLE);
  const states = {
    "sensor.practice_target": PLAYING["sensor.practice_target"],
    "sensor.practice_remaining": { state: "unknown", attributes: { plan: null, plan_of_the_day: OFFER } },
  };
  card.hass = update(hass, states);
  assert.equal($(card, ".plan-buttons"), null);
  assert.equal($(card, ".plan-offer"), null);
  assert.equal(text(card, ".title"), "Bob's 27");
});

test("the overlay of a stream has nothing to tap", () => {
  const playing = scoreboard(PLAYING, { overlay: "chroma" }).card;
  assert.equal(text(playing, ".title"), "Step 2 of 4: Bob's 27");
  assert.equal($(playing, ".plan-buttons"), null);
  assert.equal($(scoreboard(IDLE, { overlay: "chroma" }).card, ".plan-offer"), null);
});

test("the offer follows the options of the new game screen", () => {
  assert.equal($(scoreboard(IDLE, { lobby: false }).card, ".plan-offer"), null);
  assert.equal($(scoreboard(IDLE, { lobby_games: ["501", "cricket"] }).card, ".plan-offer"), null);
  assert.equal($(scoreboard(IDLE, { lobby_games: ["501", "checkout"] }).card, ".plan-offer"), null);
  assert.notEqual($(scoreboard(IDLE, { lobby_games: ["checkout", "catch_40"] }).card, ".plan-offer"), null);
  assert.notEqual($(scoreboard(IDLE, { lobby_games: [] }).card, ".plan-offer"), null);
});

test("the preview of the card picker starts nothing", () => {
  const { card, hass } = scoreboard(IDLE);
  card.preview = true;
  $(card, ".plan-offer").click();
  assert.equal(hass.calls.length, 0);
});

test("the new game screen hides the buttons of a plan", () => {
  const states = { ...PLAYING, "select.practice_game": { state: "bobs_27", attributes: { options: ["off", "501", "bobs_27"] } } };
  const { card } = scoreboard(states);
  assert.equal($$(card, ".plan-buttons").length, 1);
  $(card, ".lobby-toggle").click();
  assert.notEqual($(card, ".lobby"), null);
  assert.equal($$(card, ".plan-buttons").length, 0);
});

test("the live card shows the step with Skip and Stop", () => {
  const { card, hass } = live(PLAYING);
  assert.equal(text(card, ".practice-title"), "Step 2 of 4: Bob's 27");
  const meta = text(card, ".practice-meta");
  assert.ok(meta.startsWith("Doubles day · 12 / 60 darts · "), meta);
  assert.match(meta, /25/);
  assert.equal($(card, ".practice-plan").hidden, false);
  $$(card, ".practice-plan button")[0].click();
  assert.equal(hass.calls.length, 0);
  assert.equal($$(card, ".practice-plan button")[0].textContent, "Confirm?");
  $$(card, ".practice-plan button")[0].click();
  assert.deepEqual(hass.calls.at(-1), ["homedarts", "next_plan_step", {}]);
  // A tap beside the buttons does nothing.
  $(card, ".practice-plan .plan-buttons").click();
  assert.equal(hass.calls.length, 1);
});

test("the second tap of the live card runs out", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { card } = live(PLAYING);
  $$(card, ".practice-plan button")[1].click();
  assert.equal($$(card, ".practice-plan button")[1].textContent, "Confirm?");
  t.mock.timers.tick(4000);
  assert.equal($$(card, ".practice-plan button")[1].textContent, "Stop");
});

test("the live card shows a training game without a plan as before", () => {
  const { card } = live({
    ...PLAYING,
    "sensor.practice_remaining": { state: "unknown", attributes: { plan: null } },
  });
  assert.equal(text(card, ".practice-title"), "Bob's 27");
  assert.equal($(card, ".practice-plan").hidden, true);
  assert.equal($(card, ".practice-plan").innerHTML, "");
});

test("every language has the words of the plans", async () => {
  for (const language of ["de", "es", "fr", "nl"]) {
    const hass = makeHass({ language, states: PLAYING });
    const card = mount("homedarts-scoreboard-card", hass, { device_id: DEVICE });
    const title = text(card, ".title");
    assert.match(title, /2.*4/, language);
    assert.doesNotMatch(title, /plan_step/, language);
    assert.notEqual(title, "Step 2 of 4: Bob's 27", language);
    assert.doesNotMatch(text(card, ".meta"), /plan_|Doubles day/, language);
  }
});

// axe-core, the engine of the accessibility check in a real browser, runs its rules that need
// no layout here too: the names of the buttons.
test("the step header, Skip, Stop and the offer pass axe-core's WCAG 2.1 A and AA rules", async () => {
  window.eval(readFileSync(new URL("../../node_modules/axe-core/axe.min.js", import.meta.url), "utf8"));
  const check = async (root) => {
    const result = await window.axe.run(root, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] });
    assert.deepEqual(
      Array.from(result.violations, (rule) => rule.id),
      []
    );
    assert.ok(Array.from(result.passes, (rule) => rule.id).includes("button-name"));
  };
  await check($(scoreboard(PLAYING).card, ".scoreboard"));
  await check($(scoreboard(IDLE).card, ".scoreboard"));
  await check($(live(PLAYING).card, ".practice"));
});
