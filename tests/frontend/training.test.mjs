// Training analytics, board status and entity lookup shared by the cards.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  boardStatus,
  cameraEntities,
  entityIndex,
  heatColor,
  heatLevels,
  hitBeds,
  topHits,
  visitBucket,
  visitsFromHistory,
} from "../../custom_components/homedarts/frontend/homedarts-card.js";

test("hit names map to the beds of the board", () => {
  assert.deepEqual(hitBeds("T20"), ["T20"]);
  assert.deepEqual(hitBeds("D16"), ["D16"]);
  assert.deepEqual(hitBeds("S5"), ["SI5", "SO5"]);
  assert.deepEqual(hitBeds("BULL"), ["Bull"]);
  assert.deepEqual(hitBeds("25"), ["25"]);
  assert.deepEqual(hitBeds("MISS"), []);
  assert.deepEqual(hitBeds("T21"), []);
  assert.deepEqual(hitBeds("<b>"), []);
});

test("heat levels count beds or whole numbers", () => {
  const hits = { T20: 5, S20: 3, D16: 1, BULL: 2, 25: 1, MISS: 4, X9: 7, S1: "x", T19: -1 };
  const beds = heatLevels(hits);
  assert.equal(beds.get("T20"), 5);
  assert.equal(beds.get("SI20"), 3);
  assert.equal(beds.get("SO20"), 3);
  assert.equal(beds.get("D16"), 1);
  assert.equal(beds.get("Bull"), 2);
  assert.equal(beds.get("25"), 1);
  assert.equal(beds.size, 6);

  const numbers = heatLevels(hits, "numbers");
  for (const bed of ["SI20", "T20", "SO20", "D20"]) assert.equal(numbers.get(bed), 8);
  assert.equal(numbers.get("D16"), 1);
  assert.equal(numbers.get("Bull"), 3);
  assert.equal(numbers.get("25"), 3);
  assert.equal(heatLevels(null).size, 0);
});

test("thermal heat colours run from blue to red", () => {
  assert.equal(heatColor(0, "thermal"), "hsl(220, 90%, 55%)");
  assert.equal(heatColor(1, "thermal"), "hsl(0, 90%, 55%)");
  assert.equal(heatColor(2, "thermal"), "hsl(0, 90%, 55%)");
  assert.equal(heatColor(Number.NaN, "thermal"), "hsl(220, 90%, 55%)");
});

test("most hit beds are sorted and never include misses", () => {
  const top = topHits({ S20: 3, T20: 5, MISS: 9, D16: 3, S1: 1 }, 3);
  assert.deepEqual(top, [
    ["T20", 5],
    ["D16", 3],
    ["S20", 3],
  ]);
  assert.deepEqual(topHits(undefined), []);
});

test("visit scores are bucketed like darts statistics", () => {
  assert.equal(visitBucket(180), "max");
  assert.equal(visitBucket(140), "high");
  assert.equal(visitBucket(139), "ton");
  assert.equal(visitBucket(100), "ton");
  assert.equal(visitBucket(60), "good");
  assert.equal(visitBucket(26), "low");
});

test("completed visits are read from the event history", () => {
  const rows = [
    { s: "2026-09-25T20:00:00+00:00", a: { event_type: "dart_detected", score: 60 } },
    {
      s: "2026-09-25T20:00:05+00:00",
      a: { event_type: "visit_completed", score: 140, darts: 3, segments: ["T20", "T20", "S20"] },
    },
    { s: "unknown", a: { event_type: "visit_completed", score: 10 } },
    { s: "2026-09-25T19:00:00+00:00", a: { event_type: "visit_completed", score: 26 } },
    { state: "2026-09-25T20:01:00+00:00", attributes: { event_type: "visit_completed", score: "45" } },
  ];
  const since = Date.parse("2026-09-25T19:30:00+00:00");
  assert.deepEqual(visitsFromHistory(rows, since), [
    { time: Date.parse("2026-09-25T20:00:05+00:00"), score: 140, darts: 3, segments: ["T20", "T20", "S20"] },
    { time: Date.parse("2026-09-25T20:01:00+00:00"), score: 45, darts: 0, segments: [] },
  ]);
  assert.deepEqual(visitsFromHistory(null), []);
});

test("undone visits leave the history, the bot's never join it, and new rows add to the known visits", () => {
  const row = (second, event_type, extra = {}) => ({ s: `2026-09-25T20:00:${second}+00:00`, a: { event_type, ...extra } });
  const known = [{ time: 1, score: 81, darts: 3, segments: [] }];
  const rows = [
    row("01", "visit_completed", { score: 26 }),
    row("02", "visit_completed", { score: 100, bot: true }),
    row("03", "visit_undone", { score: 26 }),
    row("04", "visit_completed", { score: 60 }),
    row("05", "visit_completed", { score: "a lot" }),
    row("06", "visit_undone"),
    row("07", "visit_undone"),
    row("08", "visit_undone"),
    row("09", "visit_completed", { score: 45 }),
  ];
  // The undone 26 goes, its corrected darts come back as 60; more undos than visits empty the list.
  assert.deepEqual(
    visitsFromHistory(rows.slice(0, 5), 0, known).map((visit) => visit.score),
    [81, 60]
  );
  assert.deepEqual(visitsFromHistory(rows, 0, known).map((visit) => visit.score), [45]);
  // The known visits stay as they were.
  assert.deepEqual(known.map((visit) => visit.score), [81]);
});

test("a session start drops visits of the previous session in the same second", () => {
  // The start sensor reports 20:00:00; the previous visit ended 300 ms later.
  const since = Date.parse("2026-09-25T20:00:00+00:00");
  const rows = [
    { s: "2026-09-25T20:00:00.100+00:00", a: { event_type: "visit_completed", score: 60 } },
    { s: "2026-09-25T20:00:00.300+00:00", a: { event_type: "session_ended", darts: 3 } },
    { s: "2026-09-25T20:00:00.600+00:00", a: { event_type: "session_started" } },
    { s: "2026-09-25T20:00:04+00:00", a: { event_type: "visit_completed", score: 100 } },
  ];
  assert.deepEqual(
    visitsFromHistory(rows, since).map((visit) => visit.score),
    [100]
  );
  // An older session start before the window changes nothing.
  const older = [{ s: "2026-09-25T19:00:00+00:00", a: { event_type: "session_started" } }, rows[3]];
  assert.deepEqual(visitsFromHistory(older, since).map((visit) => visit.score), [100]);
});

test("board status follows connection, detection and takeout", () => {
  const states = (values) => (name) => (name in values ? { state: values[name] } : undefined);
  assert.deepEqual(boardStatus(states({})), ["offline", "status_offline"]);
  assert.deepEqual(boardStatus(states({ connected: "on", detection: "off" })), ["stopped", "status_stopped"]);
  assert.deepEqual(boardStatus(states({ connected: "on", status: "calibrating" })), [
    "calibrating",
    "status_calibrating",
  ]);
  assert.deepEqual(boardStatus(states({ connected: "on", cameraProblem: "on" })), ["problem", "status_problem"]);
  assert.deepEqual(boardStatus(states({ connected: "on", detection: "on", status: "takeout_in_progress" })), [
    "takeout",
    "status_takeout",
  ]);
  assert.deepEqual(boardStatus(states({ connected: "on", detection: "on", numThrows: "3" })), [
    "takeout",
    "status_full",
  ]);
  assert.deepEqual(boardStatus(states({ connected: "on", detection: "on", status: "throw" })), [
    "ready",
    "status_ready",
  ]);
});

test("entities are found per device and cameras grouped by number", () => {
  const entity = (entity_id, translation_key, device_id = "board") => ({
    entity_id,
    translation_key,
    device_id,
    platform: "homedarts",
  });
  const hass = {
    entities: {
      a: entity("binary_sensor.cam_2_problem", "individual_camera_problem"),
      b: entity("binary_sensor.cam_1_problem", "individual_camera_problem"),
      c: entity("button.cam_1_calibrate", "calibrate_camera"),
      d: entity("sensor.other_board_status", "local_status", "other"),
      e: { entity_id: "light.kitchen", platform: "hue", device_id: "board" },
      f: entity("sensor.board_status", "local_status"),
      g: entity("sensor.board_uptime", undefined),
    },
    states: {
      "binary_sensor.cam_2_problem": { state: "on", attributes: { camera: 2 } },
      "binary_sensor.cam_1_problem": { state: "off", attributes: { camera: 1 } },
      "button.cam_1_calibrate": { state: "unknown", attributes: { camera: 1 } },
    },
  };
  const index = entityIndex(hass, "board");
  assert.deepEqual(index["sensor.local_status"], ["sensor.board_status"]);
  assert.equal(index["light.undefined"], undefined);
  // Entities without a translation key cannot be told apart and are skipped.
  assert.deepEqual(Object.keys(index).sort(), [
    "binary_sensor.individual_camera_problem",
    "button.calibrate_camera",
    "sensor.local_status",
  ]);
  assert.deepEqual(entityIndex({}, "board"), {});
  // The index is cached until the entity registry changes.
  assert.equal(entityIndex(hass, "board"), index);
  assert.deepEqual(cameraEntities(hass, index), [
    { number: 1, problem: "binary_sensor.cam_1_problem", calibrate: "button.cam_1_calibrate" },
    { number: 2, problem: "binary_sensor.cam_2_problem" },
  ]);
});

test("heat ratios run from the least to the most hit bed", async () => {
  const { heatRatio } = await import("../../custom_components/homedarts/frontend/homedarts-card.js");
  assert.equal(heatRatio(1, 5), 0);
  assert.equal(heatRatio(3, 5), 0.5);
  assert.equal(heatRatio(5, 5), 1);
  assert.equal(heatRatio(1, 1), 1);
});
