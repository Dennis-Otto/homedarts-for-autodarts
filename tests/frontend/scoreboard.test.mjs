// The scoreboard card: what it shows for every game and between games.
import assert from "node:assert/strict";
import { test } from "node:test";

import { scoreboardHtml, gameView } from "../../custom_components/homedarts/frontend/homedarts-card.js";

const ui = {
  t: (key) => ({ score_winner_by: "score_winner_by {result}" })[key] ?? key,
  format: (value, digits) => (Number.isFinite(value) ? value.toFixed(digits) : "–"),
  percent: (value, digits) => (Number.isFinite(value) ? `${value.toFixed(digits)} %` : "–"),
  label: (key) => (key === "BULL" ? "Bull" : key),
  name: "Dartboard",
  stats: { visit: "60", darts: 123, average: 45.6, highest: 140, max: 1 },
};
const board = (states) => scoreboardHtml(gameView((name) => states[name]), ui);

test("the scoreboard shows the game that runs, a training game first", () => {
  const off = { state: "unknown", attributes: { game: null } };
  assert.equal(gameView(() => undefined).mode, "idle");
  assert.equal(gameView((name) => ({ practice: off })[name]).mode, "idle");
  assert.equal(gameView(() => ({ state: "501", attributes: { game: 501 } })).mode, "x01");
  assert.equal(gameView(() => ({ state: "unknown", attributes: { game: "cricket" } })).mode, "cricket");
  const drill = { state: "7", attributes: { drill: "around_the_clock" } };
  assert.equal(gameView((name) => ({ practice: off, drill })[name]).mode, "drill");
});

test("an X01 match shows every player, the player at the board and the route", () => {
  const match = board({
    practice: {
      state: "81",
      attributes: {
        game: 501,
        player: 1,
        checkout: "T15 D18",
        legs_to_win: 3,
        sets_to_win: 1,
        scores: [
          { player: 1, name: "Alex", remaining: 81, legs: 1, sets: 0, average: 84.2 },
          { player: 2, name: null, remaining: 361, legs: 0, sets: 0, average: 46.7 },
        ],
      },
    },
  });
  assert.deepEqual([match.title, match.meta, match.banner], ["practice 501", "3 legs_to_win_set", ""]);
  assert.match(match.main, /<div class="players n2">/);
  assert.match(
    match.main,
    /<div class="player active" aria-current="true"><div class="name">Alex<\/div><div class="big">81<\/div><div class="route"><div class="route-line"><span class="bed">T15<\/span><span class="bed">D18<\/span><\/div><\/div><div class="details"><span class="details-line">score_legs 1 · Ø 84\.2<\/span><\/div>/
  );
  assert.match(
    match.main,
    /<div class="player"><div class="name">score_player 2<\/div><div class="big">361<\/div><div class="route"><div class="route-line"><\/div><\/div>/
  );
});

test("the winner gets the banner; alone, busts and missing routes show a note", () => {
  const won = board({
    practice: {
      state: "0",
      attributes: {
        game: 301,
        player: 2,
        winner: 2,
        sets_to_win: 2,
        scores: [
          { player: 1, name: "<b>", remaining: 40, legs: 0, sets: 1 },
          { player: 2, name: null, remaining: 0, legs: 0, sets: 2 },
        ],
      },
    },
  });
  // The winner's sets come first.
  assert.equal(won.banner, "score_player 2 score_winner_by 2 : 1");
  assert.equal(won.meta, "2 sets_to_win");
  assert.match(won.main, /<div class="player winner"><div class="name">score_player 2/);
  assert.match(won.main, /&#60;b&#62;/);
  assert.doesNotMatch(won.main, /active/);

  const alone = (attributes, state = "32") => board({ practice: { state, attributes } }).main;
  const player = { player: 1, name: null, remaining: 32, legs: 0, sets: 0, average: 50 };
  const bust = alone({ game: 301, bust: true, darts: 9, average: 56.33, scores: [player] });
  assert.match(bust, /<div class="player"><div class="name"><\/div><div class="big">32<\/div>/);
  assert.match(bust, /<span class="note bust">bust<\/span>/);
  assert.match(bust, /<div class="details"><span class="details-line">9 leg_darts · Ø 56\.3<\/span><\/div>/);
  const stuck = alone({ game: 501, scores: [{ ...player, remaining: 169 }] }, "169");
  assert.match(stuck, /<span class="note">no_checkout<\/span>/);
  const shot = alone({ game: 501, won: true, scores: [{ ...player, remaining: 0 }] }, "0");
  assert.match(shot, /<span class="note won">game_shot<\/span>/);
});

test("cricket shows the chalkboard, the points and the next number", () => {
  const cricket = board({
    practice: {
      state: "unknown",
      attributes: {
        game: "cricket",
        player: 1,
        target: "T19",
        scores: [
          { player: 1, name: "Alex", marks: [3, 1, 0, 0, 0, 0, 0], points: 60, legs: 0, sets: 0, mpr: 3.5 },
          { player: 2, name: "Sam", marks: [3, 0, 0, 0, 0, 0, 0], points: 0, legs: 0, sets: 0, mpr: 3 },
        ],
      },
    },
  });
  assert.equal(cricket.title, "cricket");
  assert.match(
    cricket.main,
    /<thead><tr><th class="aim"><span class="bed">T19<\/span><\/th><th class="active" aria-current="true">Alex<\/th><th class="">Sam<\/th><\/tr><\/thead>/
  );
  // Every mark has a name for screen readers.
  const closed = '<span role="img" aria-label="mark_3">Ⓧ</span>';
  assert.ok(cricket.main.includes(`<tr class="closed"><th>20</th><td class="active">${closed}</td><td class="">${closed}</td></tr>`));
  assert.ok(
    cricket.main.includes(
      '<tr class="target"><th>19</th><td class="active"><span role="img" aria-label="mark_1">/</span></td>' +
        '<td class=""><span role="img" aria-label="mark_0"></span></td></tr>'
    )
  );
  assert.match(cricket.main, /<tr class="total"><th>cricket_points<\/th><td class="active">60<\/td><td class="">0<\/td><\/tr>/);
  assert.match(cricket.main, /<tr class="detail"><th>cricket_mpr<\/th><td class="active">3\.50<\/td>/);

  const alone = board({
    practice: {
      state: "unknown",
      attributes: {
        game: "cricket",
        won: true,
        scores: [{ player: 1, marks: [3, 3, 3, 3, 3, 3, 3], points: 0, mpr: null }],
      },
    },
  });
  assert.match(alone.main, /<th class=""><\/th>/);
  assert.doesNotMatch(alone.main, /class="total"/);
  assert.match(alone.main, /<td class="">–<\/td>/);
  assert.match(alone.main, /<span class="note won">game_shot<\/span>/);
});

test("training games show their target, between games the visit and the session", () => {
  const clock = board({
    drill: {
      state: "7",
      attributes: { drill: "around_the_clock", progress: 6, targets: 21, darts: 9, hit_rate: 66.7 },
    },
  });
  assert.equal(clock.title, "drill_around_the_clock");
  assert.match(clock.main, /<div class="big">7<\/div>/);
  assert.match(clock.main, /<b>6 \/ 21<\/b>.*<b>9<\/b> leg_darts.*<b>67 %<\/b> drill_hits/);

  const bobs = board({
    drill: {
      state: "unknown",
      attributes: { drill: "bobs_27", finished: true, score: 77, progress: 21, targets: 21, results: [{ completed: true }] },
    },
  });
  assert.match(bobs.main, /<div class="big">✓<\/div><div class="route"><div class="route-line"><span class="note won">drill_bobs_done<\/span>/);
  assert.match(bobs.main, /<b>77<\/b> drill_points<\/span><span>drill_round <b>21 \/ 21<\/b>/);
  const lost = board({ drill: { state: "unknown", attributes: { drill: "bobs_27", finished: true, score: -3 } } });
  assert.match(lost.main, /<span class="note bust">drill_bobs_lost<\/span>/);

  const checkout = board({
    drill: {
      state: "81",
      attributes: {
        drill: "checkout",
        remaining: 81,
        checkout: "T15 D18",
        attempt_visit: 2,
        attempt_visits: 3,
        attempts: 4,
        successes: 1,
        rate: 25,
      },
    },
  });
  assert.match(checkout.main, /<div class="big">81<\/div><div class="route"><div class="route-line"><span class="bed">T15<\/span><span class="bed">D18<\/span>/);
  assert.match(checkout.main, /drill_visit <b>2 \/ 3<\/b>.*<b>1 \/ 4<\/b> drill_checked.*<b>25 %<\/b>/);
  const bust = board({ drill: { state: "81", attributes: { drill: "checkout", remaining: 81, bust: true } } });
  assert.match(bust.main, /<span class="note bust">bust<\/span>/);

  const idle = board({});
  assert.deepEqual([idle.title, idle.meta, idle.banner], ["Dartboard", "training", ""]);
  assert.match(idle.main, /<div class="label">visit<\/div><div class="big">60<\/div>/);
  assert.match(idle.main, /<b>123<\/b> darts.*<b>45\.6<\/b> average.*<b>140<\/b> highest.*<b>1<\/b> max/);
});

test("between games the scoreboard adds the streak and the darts towards the daily goal", () => {
  const stats = { ...ui.stats, streak: 4, today: 120, goal: 300 };
  const idle = scoreboardHtml({ mode: "idle" }, { ...ui, stats });
  assert.match(idle.main, /<b>4<\/b> streak_days.*<b>120 \/ 300<\/b> darts_today/);
  const first = scoreboardHtml({ mode: "idle" }, { ...ui, stats: { ...stats, streak: 1, goal: 0 } });
  assert.match(first.main, /<b>1<\/b> streak_day<\/span><span><b>120<\/b> darts_today/);
  const none = scoreboardHtml({ mode: "idle" }, { ...ui, stats: { ...stats, streak: 0, today: null } });
  assert.doesNotMatch(none.main, /streak|darts_today/);
});

test("party games and the bull-off have their own boards", () => {
  const killer = board({
    practice: {
      state: "unknown",
      attributes: {
        game: "killer",
        phase: "play",
        player: 1,
        target: null,
        scores: [
          { player: 1, name: "Alex", number: 7, lives: 3, killer: true },
          { player: 2, name: "Sam", number: 12, lives: 0 },
        ],
      },
    },
  });
  assert.equal(killer.title, "party_killer");
  // Hearts read as the number of lives.
  assert.match(
    killer.main,
    /<div class="big lives" role="img" aria-label="killer_lives">♥♥♥<\/div><div class="route"><div class="route-line"><span class="note">killer_hunt<\/span>/
  );
  assert.match(killer.main, /<div class="player out"><div class="name">Sam<\/div><div class="big lives" role="img" aria-label="killer_lives">✕<\/div>/);
  const halve = board({
    practice: {
      state: "unknown",
      attributes: { game: "halve_it", round: 3, rounds: 9, target: "D", player: 1, scores: [{ player: 1, points: 80 }] },
    },
  });
  assert.equal(halve.meta, "drill_round 3/9");
  assert.match(halve.main, /<div class="big">80<\/div><div class="route"><div class="route-line"><span class="bed">any_double<\/span>/);
  const bullOff = board({
    practice: {
      state: "501",
      attributes: {
        game: 501,
        bull_off: { player: 2, throws: [{ player: 1, name: "Alex", hit: "S20", distance: 11.4 }, { player: 2, name: "Sam" }] },
      },
    },
  });
  assert.deepEqual([bullOff.title, bullOff.meta, bullOff.banner], ["bull_off", "bull_off_hint", ""]);
  // Every dart shows its bed and how far from the centre it landed.
  assert.match(
    bullOff.main,
    /<div class="player"><div class="name">Alex<\/div><div class="big">S20<\/div><div class="route"><div class="route-line"><\/div><\/div><div class="details"><span class="details-line">11\.4\u00a0mm<\/span><\/div>/
  );
  assert.match(bullOff.main, /<div class="player active" aria-current="true"><div class="name">Sam<\/div><div class="big">–<\/div>/);
});

test("an X01 game names the rules besides double out, and the round of a round limit", () => {
  const leg = (attributes) =>
    board({
      practice: {
        state: "301",
        attributes: { game: 501, player: 1, scores: [{ player: 1, name: "Alex", remaining: 301 }], ...attributes },
      },
    });
  const ruled = leg({ in_mode: "master", out_mode: "straight", bull_mode: "50_50", max_rounds: 10, round: 3, opened: false });
  assert.equal(ruled.meta, "master_in · straight_out · bull_50_50 · drill_round 3/10");
  assert.match(ruled.main, /master_in_needed/);
  // Past the limit, a tie plays extra rounds; double in and master out read as such.
  assert.equal(leg({ in_mode: "double", out_mode: "master", max_rounds: 10, round: 11 }).meta, "double_in · master_out · playoff · drill_round 11");
  assert.match(leg({ in_mode: "double", opened: false }).main, /double_in_needed/);
  // The usual rules and a limit without a round say nothing.
  assert.equal(leg({ max_rounds: 10 }).meta, "");
});
