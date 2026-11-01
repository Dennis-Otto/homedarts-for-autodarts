// Badges, weekly trends, groupings, dart positions and the leaderboard, as pure views.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  addWeeks,
  badgesHtml,
  badgesView,
  dashboardStrategy,
  formatNumber,
  formatPercent,
  leaderboardRecords,
  leaderboardRecordsHtml,
  NORM,
  offsetText,
  positionsDensity,
  positionsHtml,
  progressView,
  sparkline,
  spreadHtml,
  spreadView,
  tierColor,
  trendsHtml,
  trendView,
  trendWeeks,
} from "../../custom_components/homedarts/frontend/homedarts-card.js";

import { makeHass } from "./dom.mjs";

const TEXT = {
  achievement_maximum: "180",
  achievement_maximum_goal: "180s in X01: {value}",
  achievement_short_leg: "Short leg",
  achievement_short_leg_goal: "A 501 leg in {value} darts or fewer",
  achievement_hat_trick: "Hat trick",
  achievement_hat_trick_goal: "Three bulls in one visit",
  achievement_streak: "Streak",
  achievement_streak_goal: "Days in a row: {value}",
  badge_locked: "Locked",
  badge_earned: "Earned {date}",
  badge_progress: "{value} of {goal}",
  badge_best: "Best so far: {value}",
  tier_1: "Bronze",
  tier_2: "Silver",
  tier_3: "Gold",
  tier_4: "Platinum",
  unit_mm: "{value} mm",
  unit_darts: "{value} darts",
  unit_day: "{value} day",
  unit_days: "{value} days",
  spread_group: "grouping {r50}",
  spread_group80: "80 % within {r80}",
  spread_left: "{distance} left of center",
  spread_right: "{distance} right of center",
  spread_high: "{distance} high",
  spread_low: "{distance} low",
  spread_centered: "centered",
  spread_tighter: "{value} tighter",
  spread_wider: "{value} wider",
  trend_up: "rising",
  trend_down: "falling",
  trend_steady: "steady",
  average: "3-dart avg.",
  first_9: "First 9",
  checkout_short: "Checkout",
  doubles_rate_short: "Doubles",
  darts: "Darts",
};
const hass = makeHass();
const ui = {
  t: (key) => TEXT[key] ?? key,
  format: (value, digits = 0) => formatNumber(hass, value, digits),
  percent: (value, digits = 0) => formatPercent(hass, value, digits),
  label: (key) => (key === "BULL" ? "Bull" : key),
  date: (value) => `on ${value}`,
};

const CATALOGUE = [
  { id: "maximum", tiers: [1, 10, 100], lower: false },
  { id: "short_leg", tiers: [18, 15, 12], lower: true },
  { id: "hat_trick", tiers: [1], lower: false },
  { id: "streak", tiers: [3, 7, 10, 30], lower: false },
  { id: "broken", tiers: [] },
  { id: 7, tiers: [1] },
];
const achievements = {
  state: "5",
  attributes: {
    latest: { name: "Alex", achievement: "maximum", tier: 2, date: "2026-09-23T20:00:00+02:00" },
    catalogue: CATALOGUE,
    players: [
      {
        name: "Alex",
        unlocked: 99,
        badges: {
          maximum: { tier: 2, dates: ["2026-09-01T20:00:00+02:00", "2026-09-23T20:00:00+02:00"] },
          short_leg: { tier: 1, dates: ["2026-09-10T20:00:00+02:00", 3] },
          hat_trick: { tier: 1, dates: ["2026-07-01T20:00:00+02:00"] },
          streak: { tier: 9, dates: "never" },
        },
        progress: { maximum: 37, short_leg: 17, hat_trick: 1, streak: 31 },
      },
      { name: "Sam", badges: null, progress: null },
      { name: "", badges: {} },
      null,
    ],
  },
};

// Twelve weeks of sums, the newest last; three weeks have darts.
const WEEKS = Array.from({ length: 12 }, (_, index) => `2026-07-${String(6 + index).padStart(2, "0")}`);
const column = (values) => [...Array(12 - values.length).fill(0), ...values];
const bests = (values) => [...Array(12 - values.length).fill(null), ...values];
const TREND = {
  weeks: WEEKS,
  darts: column([60, 0, 90, 120]),
  x01_darts: column([45, 0, 60, 90]),
  x01_points: column([600, 0, 900, 1500]),
  first9_points: column([300, 0, 400, 480]),
  first9_darts: column([9, 0, 9, 9]),
  at_double: column([10, 0, 8, 6]),
  checkouts: column([1, 0, 2, 3]),
  double_attempts: column([20, 0, 16, 12]),
  double_hits: column([2, 0, 4, 6]),
  maximums: column([0, 0, 1, 2]),
  highest_checkout: bests([40, null, 81, 64]),
  best_501: bests([27, null, 21, 24]),
  best_mpr: bests([null, null, 2.4, 1.8]),
};
const profiles = {
  state: "3",
  attributes: {
    players: [
      {
        name: "Alex",
        average: 55.5,
        highest_checkout: 121,
        fewest_darts: { 501: 18 },
        best_mpr: 2.8,
        maximums: 4,
        best_streak: 5,
        darts_thrown: 1200,
        trend: TREND,
        spread: [
          { target: "T20", darts: 120, offset_x: -6.2, offset_y: 1.4, r50: 38.4, r80: 61, change: -4.2 },
          { target: "D16", darts: 20, offset_x: 0.4, offset_y: -0.2, r50: 21, r80: 30.5, change: 0.3 },
          { target: "BULL", darts: 11, offset_x: 3, offset_y: -2, r50: 12, r80: 20, change: 2.5 },
          { target: "D8", darts: 10, offset_x: 1, offset_y: 1, r50: 20, r80: 30, change: null },
          { target: "T19", darts: "many" },
        ],
      },
      {
        name: "Sam",
        average: 61.2,
        highest_checkout: 80,
        fewest_darts: {},
        best_mpr: null,
        maximums: 4,
        best_streak: 1,
        darts_thrown: 300,
        trend: { ...TREND, x01_points: column([0, 0, 0, 1800]), maximums: column([0, 0, 0, 0]) },
      },
      { name: "Kim", trend: { weeks: WEEKS } },
      { name: 3 },
    ],
  },
};

test("tiers have the colours of medals", () => {
  assert.equal(tierColor(0, 3), null);
  assert.equal(tierColor(1, 3), "#c07a3c");
  assert.equal(tierColor(1, 1), "#ffd60a");
  assert.equal(tierColor(4, 4), "#5fd0e8");
  assert.equal(tierColor(9, 4), "#5fd0e8");
});

test("badges come from the catalogue with their tier, dates and progress", () => {
  assert.deepEqual(badgesView(undefined), { players: [] });
  const { players } = badgesView(achievements);
  assert.deepEqual(
    players.map((player) => [player.name, player.unlocked]),
    [
      ["Alex", 8],
      ["Sam", 0],
    ]
  );
  const [maximum, shortLeg, hatTrick, streak] = players[0].badges;
  assert.deepEqual(maximum, {
    id: "maximum",
    tier: 2,
    tiers: 3,
    goal: 100,
    lower: false,
    value: 37,
    share: 0.37,
    date: "2026-09-23T20:00:00+02:00",
    dates: ["2026-09-01T20:00:00+02:00", "2026-09-23T20:00:00+02:00"],
  });
  // Fewer darts are better: no bar, but the best so far.
  assert.deepEqual([shortLeg.tier, shortLeg.goal, shortLeg.share, shortLeg.dates.length], [1, 15, null, 1]);
  assert.deepEqual([hatTrick.tier, hatTrick.goal, hatTrick.share], [1, 1, null]);
  // More tiers than the catalogue has count as the highest.
  assert.deepEqual([streak.tier, streak.goal, streak.share, streak.date], [4, 30, null, null]);
  const sam = players[1].badges;
  assert.deepEqual(
    sam.map((badge) => [badge.tier, badge.value, badge.share]),
    [
      [0, null, null],
      [0, null, null],
      [0, null, null],
      [0, null, null],
    ]
  );
});

test("badges show the next goal, the progress and when they were earned", () => {
  const { players } = badgesView(achievements);
  const html = badgesHtml(players[0], ui);
  assert.match(html, /data-badge="maximum" style="--tier:#a9b6c4"/);
  assert.match(html, /<b>180 · Silver<\/b><span>180s in X01: 100<\/span><span class="muted">37 of 100<\/span>/);
  assert.match(html, /<span class="badge-bar"><i style="width:37%"><\/i><\/span>/);
  assert.match(html, /<b>Short leg · Bronze<\/b><span>A 501 leg in 15 darts or fewer<\/span><span class="muted">Best so far: 17<\/span>/);
  // A badge of a single tier is gold and has no tier name.
  assert.match(html, /data-badge="hat_trick" style="--tier:#ffd60a">.*<b>Hat trick<\/b>/);
  assert.match(html, /Earned on 2026-07-01T20:00:00\+02:00/);
  assert.match(html, /<b>Streak · Platinum<\/b><span>Days in a row: 30<\/span><span class="muted">Earned on null<\/span>/);
  assert.match(html, /<ha-icon icon="mdi:crown">/);
  const locked = badgesHtml(players[1], ui);
  assert.equal((locked.match(/class="badge locked/g) ?? []).length, 4);
  // Opened, the badges beyond the next three goals fade in; the goals stay as they were.
  assert.equal((locked.match(/class="badge locked appear"/g) ?? []).length, 1);
  assert.equal((badgesHtml(players[1], ui, true, false).match(/appear/g) ?? []).length, 0);
  assert.match(locked, /<span class="muted">Locked<\/span>/);
  assert.doesNotMatch(locked, /style=/);
  assert.equal(badgesHtml(players[1], ui, false), "");
  const unknown = badgesHtml({ badges: [{ ...players[1].badges[0], id: "future" }] }, ui);
  assert.match(unknown, /mdi:medal-outline/);
  const plans = badgesHtml({ badges: [{ ...players[1].badges[0], id: "plans_finished" }] }, ui);
  assert.match(plans, /mdi:clipboard-check-outline/);
});

test("weeks of a trend come with their sums, the newest last", () => {
  assert.deepEqual(trendWeeks(undefined, 12), []);
  const weeks = trendWeeks(TREND, 4);
  assert.deepEqual(
    weeks.map((week) => [week.week, week.darts, week.highest_checkout]),
    [
      ["2026-07-14", 60, 40],
      ["2026-07-15", 0, null],
      ["2026-07-16", 90, 81],
      ["2026-07-17", 120, 64],
    ]
  );
  assert.equal(trendWeeks(TREND, 0).length, 1);
  assert.equal(trendWeeks(TREND, 40).length, 12);
  const total = addWeeks(weeks);
  assert.deepEqual(
    [total.darts, total.x01_points, total.maximums, total.highest_checkout, total.best_501, total.best_mpr],
    [270, 3000, 3, 81, 21, 2.4]
  );
  assert.deepEqual([addWeeks([]).darts, addWeeks([]).highest_checkout], [0, null]);
});

test("trends give every figure over the weeks and where it is heading", () => {
  const metrics = trendView(TREND, 4);
  const byKey = Object.fromEntries(metrics.map((metric) => [metric.key, metric]));
  assert.deepEqual(Object.keys(byKey), ["average", "first_9", "checkout_rate", "doubles_rate", "darts"]);
  assert.equal(byKey.average.value, (3000 * 3) / 195);
  assert.deepEqual(byKey.average.values, [40, null, 45, 50]);
  // 40 in the older half, 48 in the newer one.
  assert.equal(byKey.average.direction, "up");
  assert.deepEqual(byKey.first_9.values, [100, null, (400 * 3) / 9, 160]);
  assert.equal(byKey.checkout_rate.percent, true);
  assert.equal(byKey.checkout_rate.direction, "up");
  assert.equal(byKey.doubles_rate.value, (12 * 100) / 48);
  assert.deepEqual(byKey.darts.values, [60, null, 90, 120]);
  assert.equal(byKey.darts.value, 270);
  const falling = trendView({ ...TREND, x01_points: column([900, 0, 300, 300]) }, 4);
  assert.equal(falling[0].direction, "down");
  const steady = trendView({ ...TREND, x01_points: column([450, 0, 600, 900]) }, 4);
  assert.equal(steady[0].direction, "steady");
  // A single week has nothing to compare with: no direction, and no arrow.
  assert.ok(trendView(TREND, 1).every((metric) => metric.direction === null));
  assert.ok(trendView(undefined).every((metric) => metric.value === null && !metric.values.length));
});

test("the darts arrow compares the complete weeks per week, so steady throwing stays steady", () => {
  const dartsOf = (darts, size) => trendView({ weeks: WEEKS, darts: column(darts) }, size).at(-1);
  // 300 darts every week, while the current week has only begun, is half done or is done:
  // no window the editor offers shows an arrow up or down, odd ones included.
  for (let size = 4; size <= 12; size += 1) {
    for (const current of [0, 40, 150, 300]) {
      const darts = dartsOf([...Array(11).fill(300), current], size);
      assert.equal(darts.key, "darts");
      assert.equal(darts.direction, "steady", `${size} weeks, ${current} darts this week`);
    }
  }
  // The value and the line still count the current week.
  const steady = dartsOf([300, 300, 300, 300, 40], 5);
  assert.equal(steady.value, 4 * 300 + 40);
  assert.deepEqual(steady.values, [300, 300, 300, 300, 40]);
  // More or fewer darts a week still show: 200 a week, then 400 a week.
  assert.equal(dartsOf([200, 200, 400, 400, 10], 5).direction, "up");
  assert.equal(dartsOf([400, 400, 400, 200, 200, 10], 6).direction, "down");
  // A week without darts is a week with none, not one left out: a pause, a start.
  assert.equal(dartsOf([300, 300, 300, 0, 10], 5).direction, "down");
  assert.equal(dartsOf([0, 0, 300, 300, 10], 5).direction, "up");
  // Darts of the current week alone, or no complete week before it, leave nothing to compare.
  assert.equal(dartsOf([0, 0, 0, 0, 120], 5).direction, null);
  assert.equal(dartsOf([300, 300], 2).direction, null);
});

test("sparklines draw the weeks and bridge a week without a value with a dashed stretch", () => {
  assert.equal(sparkline([]), "");
  assert.equal(sparkline([null, null]), "");
  const line = sparkline([40, null, 45, 50]);
  // The line never breaks into pieces: the week without darts is a dashed stretch.
  assert.match(line, /<polyline class="gap" points="0,21 66.67,12"\/>/);
  assert.match(line, /<polyline points="66.67,12 100,3"\/>/);
  assert.doesNotMatch(line, /class="dot" /);
  assert.match(line, /<polyline class="dot last" points="100,3 100,3"\/>/);
  // Equal values sit in the middle; a single week in the middle of the width.
  assert.match(sparkline([5, 5]), /points="0,12 100,12"/);
  assert.match(sparkline([7]), /class="dot last" points="50,12 50,12"/);
});

test("trends show a tile for every figure with its arrow", () => {
  const html = trendsHtml([{ name: "Alex <3", metrics: trendView(TREND, 4) }], ui);
  assert.match(html, /<div class="trend-name">Alex &#60;3<\/div>/);
  assert.match(html, /data-metric="average"><span class="trend-label">3-dart avg.<\/span><span class="trend-value">46.2 /);
  assert.match(html, /<span class="arrow up" role="img" title="rising" aria-label="rising">↗<\/span>/);
  assert.match(html, /data-metric="checkout_rate">.*?<span class="trend-value">25.0% /);
  assert.match(html, /data-metric="darts">.*?<span class="trend-value">270 /);
  const empty = trendsHtml([{ name: "Kim", metrics: trendView({ weeks: WEEKS }, 4) }], ui);
  // Without darts there is nothing to compare: a dash and no arrow.
  assert.match(empty, /<span class="trend-value">–<\/span>/);
  assert.doesNotMatch(empty, /class="arrow/);
  // The five figures sit in a balanced grid.
  assert.match(html, /<div class="trends balanced n5">/);
});

test("groupings read as millimetres and directions on the board", () => {
  assert.deepEqual(spreadView(undefined), []);
  const groups = spreadView(profiles.attributes.players[0].spread);
  assert.deepEqual(
    groups.map((group) => group.target),
    ["T20", "D16", "BULL"]
  );
  assert.equal(spreadView(profiles.attributes.players[0].spread, 5).length, 4);
  assert.equal(offsetText(ui, groups[0]), "6 mm left of center, 1 mm high");
  assert.equal(offsetText(ui, groups[1]), "centered");
  assert.equal(offsetText(ui, groups[2]), "3 mm right of center, 2 mm low");
  const html = spreadHtml(groups, ui);
  assert.match(
    html,
    /data-target="T20"><span class="group-target">T20<\/span><span class="group-text">grouping 38 mm · 80 % within 61 mm · 6 mm left of center, 1 mm high<\/span><span class="group-change better">4 mm tighter<\/span>/
  );
  // A change under a millimetre is no change.
  assert.match(html, /data-target="D16">.*?centered<\/span><\/div>/);
  assert.match(html, /<span class="group-target">Bull<\/span>.*<span class="group-change worse">3 mm wider<\/span>/);
});

test("progress lists every named player's trend and groupings", () => {
  const players = progressView(profiles, 4);
  assert.deepEqual(
    players.map((player) => [player.name, player.active, player.groups.length]),
    [
      ["Alex", true, 3],
      ["Sam", true, 0],
      ["Kim", false, 0],
    ]
  );
  assert.deepEqual(progressView(undefined), []);
});

test("dart positions become a smooth density and dots", () => {
  assert.equal(positionsDensity([]).size, 0);
  const density = positionsDensity([[0, 0], [0, 0], "broken", [Number.NaN, 0]]);
  // Two darts in the middle, weighed by their distance to every cell nearby.
  assert.equal(density.get("0,0"), 2);
  assert.ok(density.get("1,0") < 2 && density.get("1,0") > 1.2);
  assert.equal(density.has("4,0"), false);
  const html = positionsHtml([[0, 0.6], [0.01, 0.6]]);
  assert.match(html, /^<g class="density" filter="url\(#ad-density\)"><rect /);
  assert.match(html, /<circle class="position" cx="0" cy="-102" r="2.2"\/><circle class="position" cx="1.7" cy="-102" r="2.2"\/>/);
  const many = Array.from({ length: 400 }, (_, index) => [index / 1000, 0]);
  assert.equal((positionsHtml(many).match(/class="position"/g) ?? []).length, 300);
  assert.equal(positionsHtml([]), `<g class="density" filter="url(#ad-density)"></g><g class="positions"></g>`);
  assert.equal(NORM, 170);
});

test("the leaderboard ranks the ratings of all time, and only of all time", () => {
  const rated = {
    attributes: {
      players: [
        { name: "Alex", rating: 985.5, trend: [] },
        { name: "Sam", rating: 1042.3, trend: [] },
        { name: "Kim", rating: null, trend: [] },
      ],
    },
  };
  const { records } = leaderboardRecords(rated, undefined);
  assert.equal(records[0].key, "rating");
  assert.deepEqual(records[0].places, [
    { name: "Sam", value: 1042.3, place: 1 },
    { name: "Alex", value: 985.5, place: 2 },
  ]);
  assert.equal(leaderboardRecords(rated, undefined, "month").records.some((record) => record.key === "rating"), false);
});

test("the leaderboard ranks every record of all time", () => {
  const view = leaderboardRecords(profiles, achievements);
  assert.equal(view.period, "all");
  const records = Object.fromEntries(view.records.map((record) => [record.key, record.places]));
  assert.deepEqual(Object.keys(records), ["average", "checkout", "maximums", "best_501", "mpr", "streak", "achievements", "darts"]);
  assert.deepEqual(records.average, [
    { name: "Sam", value: 61.2, place: 1 },
    { name: "Alex", value: 55.5, place: 2 },
  ]);
  // Equal values share their place, in the order of the names.
  assert.deepEqual(records.maximums, [
    { name: "Alex", value: 4, place: 1 },
    { name: "Sam", value: 4, place: 1 },
  ]);
  assert.deepEqual(records.best_501, [{ name: "Alex", value: 18, place: 1 }]);
  assert.deepEqual(records.achievements, [{ name: "Alex", value: 8, place: 1 }]);
  assert.deepEqual(leaderboardRecords(undefined, undefined, "year"), { period: "all", records: [] });
});

test("a period ranks the weeks it covers", () => {
  const month = leaderboardRecords(profiles, achievements, "month");
  assert.equal(month.period, "month");
  const records = Object.fromEntries(month.records.map((record) => [record.key, record.places]));
  assert.equal(records.streak, undefined);
  assert.deepEqual(records.average, [
    { name: "Alex", value: (3000 * 3) / 195, place: 1 },
    { name: "Sam", value: (1800 * 3) / 195, place: 2 },
  ]);
  assert.deepEqual(records.checkout, [
    { name: "Alex", value: 81, place: 1 },
    { name: "Sam", value: 81, place: 1 },
  ]);
  assert.deepEqual(records.maximums, [{ name: "Alex", value: 3, place: 1 }]);
  assert.deepEqual(records.best_501[0], { name: "Alex", value: 21, place: 1 });
  assert.deepEqual(records.mpr[0].value, 2.4);
  // Badges since the first week of the period, 14 July: the hat trick is older.
  assert.deepEqual(records.achievements, [{ name: "Alex", value: 3, place: 1 }]);
  const week = leaderboardRecords(profiles, achievements, "week");
  const thisWeek = Object.fromEntries(week.records.map((record) => [record.key, record.places]));
  assert.deepEqual(thisWeek.darts, [
    { name: "Alex", value: 120, place: 1 },
    { name: "Sam", value: 120, place: 1 },
  ]);
  assert.equal(thisWeek.mpr[0].value, 1.8);
  // A player without weeks has no records in a period.
  const newcomer = { attributes: { players: [{ name: "Lea", maximums: 2 }] } };
  assert.deepEqual(leaderboardRecords(newcomer, achievements, "week").records, []);
  assert.equal(leaderboardRecords(newcomer, achievements).records[0].key, "maximums");
});

test("the leaderboard shows the leader and the next places", () => {
  const view = leaderboardRecords(profiles, achievements);
  const html = leaderboardRecordsHtml(view, ui, 3);
  assert.match(
    html,
    /data-record="average"><div class="record-name">record_average<\/div><div class="record-leader"><span class="who">Sam<\/span><span class="value">61.2<\/span><\/div><ol class="record-places"><li><span class="place">2.<\/span><span class="who">Alex<\/span><span class="value">55.5<\/span><\/li><\/ol>/
  );
  assert.match(html, /data-record="best_501">.*?<span class="value">18 darts<\/span><\/div><\/div>/);
  assert.match(html, /data-record="streak">.*?<span class="value">5 days<\/span>.*?<span class="value">1 day<\/span>/);
  assert.doesNotMatch(leaderboardRecordsHtml(view, ui, 1), /record-places/);
  assert.doesNotMatch(leaderboardRecordsHtml(view, ui, 0), /record-places/);
});

test("the players view of the dashboard has the leaderboard too", () => {
  const board = makeHass({ states: { "sensor.player_profiles": { state: "2", attributes: { players: [{ name: "Alex" }] } } } });
  const view = dashboardStrategy(board).views.find((item) => item.path === "players");
  assert.deepEqual(
    view.sections.map((section) => section.cards[0].type),
    ["custom:homedarts-players-card", "custom:homedarts-leaderboard-card"]
  );
});
