// The training card in a browser DOM: session totals, heatmap, history and session controls.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, loadCards, makeHass, moreInfo, mount, settle, text, update, withLanguage } from "./dom.mjs";

const { bedPath } = await loadCards();

const STARTED = "2026-09-26T14:30:00+00:00";
const EVENTS = "event.dartboard_board_events";
const HITS = { T20: 3, S20: 6, S5: 2, D16: 1, BULL: 1, 25: 2, S1: 4, MISS: 5 };
const SESSION = {
  "sensor.training_darts": { state: "24", attributes: { hits: HITS } },
  "sensor.training_points": "446",
  "sensor.training_average": "55.75",
  "sensor.training_visits": "8",
  "sensor.training_highest_visit": "140",
  "sensor.training_scores_100": "3",
  "sensor.training_scores_140": "1",
  "sensor.training_scores_180": "0",
  "sensor.training_triples": "3",
  "sensor.training_doubles": "1",
  "sensor.training_bulls": "1",
  "sensor.training_misses": "5",
  "sensor.training_started": STARTED,
  "event.board_events": { state: "2026-09-26T14:29:00.000+00:00", attributes: { event_type: "session_started" } },
  "button.reset_training": "unknown",
  "switch.training_session": { state: "on", last_changed: STARTED },
  "sensor.training_streak": "3",
  "sensor.darts_today": { state: "60", attributes: { goal: 120, goal_reached: false, progress: 50 } },
};
const setup = (states = {}, config = {}, options = {}) => {
  const hass = makeHass({ states: { ...SESSION, ...states }, ...options });
  return { hass, card: mount("homedarts-training-card", hass, config) };
};
const visitRow = (time, score, segments = ["S20", "S20", "S20"]) => ({
  s: time,
  a: { event_type: "visit_completed", score, darts: segments.length, segments },
  lu: Date.parse(time) / 1000,
});
test("the training card shows the session average, darts and visits", () => {
  const { card } = setup();
  assert.equal(text(card, ".title"), "Training · Dartboard");
  assert.match(text(card, ".since"), /^since 09\/26, 2:30\sPM$/);
  assert.equal(text(card, ".average"), "55.8");
  assert.equal(text(card, ".average-label"), "3-dart average");
  assert.equal(text(card, '[data-total="darts"]'), "24");
  assert.equal(text(card, '[data-total="visits"]'), "8");
  assert.equal($(card, ".empty-hint").hidden, true);
  assert.equal(text(setup({}, { title: "Practice room" }).card, ".title"), "Practice room");
  assert.equal(setup().card.getCardSize(), 9);
});

test("older integrations without average and daily darts still show the session", () => {
  const { "sensor.training_average": _, "sensor.darts_today": __, ...states } = SESSION;
  const hass = makeHass({ states });
  const card = mount("homedarts-training-card", hass);
  assert.equal(text(card, ".average"), "55.8");
  assert.deepEqual([$(card, ".daily").hidden, $(card, ".goal").hidden], [false, true]);
  assert.equal(text(card, ".streak"), "🔥 3 days in a row");
  card.hass = update(hass, { "sensor.training_darts": "0" });
  assert.equal(text(card, ".average"), "–");
});

test("an empty session invites the first dart, or a session start", () => {
  const { hass, card } = setup({ "sensor.training_darts": "0", "sensor.training_triples": "0" });
  assert.equal($(card, ".empty-hint").hidden, false);
  assert.equal(text(card, ".empty-hint"), "No darts in this session yet. Start throwing!");
  assert.equal(text(card, '[data-tile="triple_rate"] .value'), "–");
  card.hass = update(hass, { "switch.training_session": "off" });
  assert.equal(text(card, ".empty-hint"), "Start a session to count your darts.");
});

test("tiles show the session records, and nothing opens with a tap on them", () => {
  const { hass, card } = setup();
  assert.deepEqual(
    $$(card, ".tile").map((tile) => [tile.dataset.tile, tile.querySelector(".value").textContent]),
    [
      ["highest", "140"],
      ["scores_100", "3"],
      ["scores_140", "1"],
      ["max", "0"],
      ["triple_rate", "12.5%"],
      ["doubles", "1"],
      ["bulls", "1"],
      ["misses", "5"],
    ]
  );
  assert.equal($(card, '[data-tile="max"]').classList.contains("hot"), false);
  card.hass = update(hass, { "sensor.training_scores_180": "1" });
  assert.equal($(card, '[data-tile="max"]').classList.contains("hot"), true);
  // A tile is static: it has no frame, no cue and no tap.
  const opened = moreInfo(card);
  $(card, '[data-tile="bulls"]').click();
  assert.deepEqual(opened, []);
  assert.equal($(card, ".tile .cue"), null);
});

test("the heatmap colours every hit bed from dark to light with its share", () => {
  const { card } = setup();
  const beds = $$(card, ".heat-bed");
  assert.equal(beds.length, 10);
  const byTitle = Object.fromEntries(beds.map((bed) => [bed.querySelector("title").textContent, bed]));
  assert.deepEqual(Object.keys(byTitle).sort(), [
    "25: 2 hits · 8.3%",
    "Bull: 1 hits · 4.2%",
    "D16: 1 hits · 4.2%",
    "S1: 4 hits · 16.7%",
    "S20: 6 hits · 25.0%",
    "S5: 2 hits · 8.3%",
    "T20: 3 hits · 12.5%",
  ]);
  const hottest = beds.find((bed) => bed.getAttribute("d") === bedPath("SI20"));
  assert.deepEqual(
    [hottest.getAttribute("fill"), hottest.getAttribute("fill-opacity")],
    ["#f1e323", "0.95"]
  );
  const coldest = beds.find((bed) => bed.getAttribute("d") === bedPath("D16"));
  assert.deepEqual(
    [coldest.getAttribute("fill"), coldest.getAttribute("fill-opacity")],
    ["#5844bc", "0.9"]
  );
  assert.equal(text(card, ".legend-max"), "6");
  assert.equal(text(card, ".legend-min"), "1");
  assert.match($(card, ".legend-bar").getAttribute("style"), /linear-gradient\(90deg, #5844bc, .*, #f1e323\)/);
  // The bars of the most hit beds follow the scale.
  assert.match($(card, ".top-row .fill").getAttribute("style"), /background:#f1e323/);
});

test("the thermal palette keeps the former colours of the training card", () => {
  const { card } = setup({}, { heatmap_palette: "thermal" });
  const fills = (selector) => [$(card, selector).getAttribute("fill"), $(card, selector).getAttribute("fill-opacity")];
  assert.deepEqual(fills(`.heat-layer path[d="${bedPath("SI20")}"]`), ["hsl(0, 90%, 55%)", "0.95"]);
  assert.deepEqual(fills(`.heat-layer path[d="${bedPath("D16")}"]`), ["hsl(220, 90%, 55%)", "0.6"]);
  assert.equal(
    $(card, ".legend-bar").getAttribute("style"),
    "background: linear-gradient(90deg, hsl(220, 90%, 55%), hsl(165, 90%, 55%), hsl(110, 90%, 55%), hsl(55, 90%, 55%), hsl(0, 90%, 55%))"
  );
  assert.match($(card, ".top-row .fill").getAttribute("style"), /background:hsl\(0, 90%, 55%\)/);
});

test("an unknown palette falls back to the accessible one", () => {
  const { card } = setup({}, { heatmap_palette: "rainbow" });
  assert.equal($(card, `.heat-layer path[d="${bedPath("SI20")}"]`).getAttribute("fill"), "#f1e323");
});

test("in numbers mode the heatmap sums every bed of a number", () => {
  const { card } = setup({}, { mode: "numbers" });
  const titles = $$(card, ".heat-bed title").map((title) => title.textContent);
  assert.equal(titles.length, 18);
  assert.equal(titles.filter((title) => title === "20: 9 hits · 37.5%").length, 4);
  assert.equal(titles.filter((title) => title === "Bull: 3 hits · 12.5%").length, 2);
  assert.equal(text(card, ".legend-max"), "9");
});

test("without hits the heatmap stays empty", () => {
  const { card } = setup({ "sensor.training_darts": { state: "0", attributes: { hits: {} } } });
  assert.equal($$(card, ".heat-bed").length, 0);
  assert.equal(text(card, ".legend-max"), "–");
  assert.equal(text(card, ".top"), "–");
});

test("the most hit beds are ranked with their share of all darts", () => {
  const { hass, card } = setup();
  assert.deepEqual(
    $$(card, ".top-row").map((row) => [
      row.querySelector(".key").textContent,
      row.querySelector(".fill").style.width,
      row.querySelector(".count").textContent,
    ]),
    [
      ["S20", "100%", "6× · 25%"],
      ["S1", "66.67%", "4× · 17%"],
      ["T20", "50%", "3× · 13%"],
      ["25", "33.33%", "2× · 8%"],
      ["S5", "33.33%", "2× · 8%"],
    ]
  );
  card.hass = update(hass, { "sensor.training_darts": { state: "0", attributes: { hits: { BULL: 2 } } } });
  assert.deepEqual(
    $$(card, ".top-row").map((row) => [row.querySelector(".key").textContent, row.querySelector(".count").textContent]),
    [["Bull", "2×"]]
  );
});

test("the streak and today's darts count towards the daily goal", () => {
  const { hass, card } = setup();
  assert.equal($(card, ".daily").hidden, false);
  assert.equal($(card, ".streak").hidden, false);
  assert.equal(text(card, ".streak"), "🔥 3 days in a row");
  assert.equal($(card, ".goal-bar").hidden, false);
  assert.equal($(card, ".goal-bar span").style.width, "50%");
  assert.equal($(card, ".goal").classList.contains("reached"), false);
  assert.equal(text(card, ".goal-text"), "60 / 120 darts today");

  card.hass = update(hass, {
    "sensor.training_streak": "1",
    "sensor.darts_today": { state: "150", attributes: { goal: 120, goal_reached: true } },
  });
  assert.equal(text(card, ".streak"), "🔥 1 day in a row");
  assert.equal($(card, ".goal-bar span").style.width, "100%");
  assert.equal($(card, ".goal").classList.contains("reached"), true);

  card.hass = update(hass, { "sensor.training_streak": "0", "sensor.darts_today": { state: "60", attributes: {} } });
  assert.equal($(card, ".streak").hidden, true);
  assert.equal($(card, ".goal-bar").hidden, true);
  assert.equal(text(card, ".goal-text"), "60 darts today");

  card.hass = update(hass, { "sensor.training_streak": "0", "sensor.darts_today": "unavailable" });
  assert.equal($(card, ".daily").hidden, true);
  assert.equal($(card, ".goal").hidden, true);
});

// Home Assistant's websocket connection with the history stream: every subscription is kept
// with its message, its callback and whether it was closed again.
const historyStream = ({ fail = false, unsubscribe = () => Promise.resolve() } = {}) => {
  const streams = [];
  const connection = {
    subscribeMessage(callback, message) {
      const stream = { callback, message, closed: false };
      streams.push(stream);
      if (fail) return Promise.reject(new Error("unknown command"));
      return Promise.resolve(() => {
        stream.closed = true;
        return unsubscribe();
      });
    },
  };
  return { streams, connection };
};
// The recorder's rows, or new board events, as a message of the stream.
const send = (stream, rows) => stream.callback({ states: { [EVENTS]: rows } });
const eventRow = (time, event_type, extra = {}) => ({ s: time, a: { event_type, ...extra }, lu: Date.parse(time) / 1000 });
const chartLabel = (card) => $(card, ".history-chart").getAttribute("aria-label");

test("the history loads the visits of the session from the recorder, then follows every board event", async (t) => {
  t.mock.timers.enable({ apis: ["Date"], now: Date.parse("2026-09-26T15:00:00Z") });
  const { streams, connection } = historyStream();
  const { card } = setup({}, {}, { connection });
  assert.deepEqual(
    streams.map((stream) => stream.message),
    [
      {
        type: "history/stream",
        entity_ids: [EVENTS],
        start_time: "2026-09-26T14:30:00.000Z",
        minimal_response: false,
        no_attributes: false,
        significant_changes_only: false,
      },
    ]
  );
  assert.equal(text(card, ".history-chart"), "Completed visits appear here.");
  assert.equal($(card, ".history-chart").getAttribute("role"), null);
  send(streams[0], [
    visitRow("2026-09-26T14:29:59.000+00:00", 99),
    visitRow("2026-09-26T14:31:00.000+00:00", 60),
    eventRow("2026-09-26T14:32:00.000+00:00", "takeout_finished"),
    visitRow("2026-09-26T14:33:00.000+00:00", 140, ["T20", "T20", "D10"]),
  ]);
  const chart = $(card, ".history-chart");
  assert.equal(chart.getAttribute("role"), "img");
  assert.equal(chartLabel(card), "Recent visits: 60, 140");
  const bars = $$(card, ".visit-bar");
  assert.equal(bars.length, 20);
  assert.equal($$(card, ".visit-bar.empty").length, 18);
  assert.deepEqual(
    bars.slice(0, 2).map((bar) => [bar.title, bar.textContent, bar.querySelector(".fill").getAttribute("style")]),
    [
      ["S20 · S20 · S20 = 60", "60", "--height:0.33;background:var(--ad-accent)"],
      ["T20 · T20 · D10 = 140", "140", "--height:0.78;background:#ff8c42"],
    ]
  );
  const line = $(card, ".average-line");
  assert.deepEqual([line.getAttribute("style"), line.title], ["--height:0.31", "3-dart average: 55.8"]);

  // A practice game books the visit and passes the turn at once: the page sees only the
  // turn, the stream both. Visits without segments show their score alone.
  send(streams[0], [
    eventRow("2026-09-26T14:35:00.000+00:00", "visit_completed", { score: 26 }),
    eventRow("2026-09-26T14:35:00.001+00:00", "turn_changed"),
  ]);
  assert.equal(chartLabel(card), "Recent visits: 60, 140, 26");
  assert.equal($$(card, ".visit-bar:not(.empty)").at(-1).title, "26");
  // The bot's visits count for nobody.
  const bot = visitRow("2026-09-26T14:36:00.000+00:00", 100);
  send(streams[0], [{ ...bot, a: { ...bot.a, bot: true } }]);
  assert.equal(chartLabel(card), "Recent visits: 60, 140, 26");
  // An undone visit leaves the chart; corrected, it comes back as a new visit.
  send(streams[0], [
    eventRow("2026-09-26T14:37:00.000+00:00", "visit_undone", { score: 26 }),
    visitRow("2026-09-26T14:37:30.000+00:00", 45, ["S20", "S20", "S5"]),
  ]);
  assert.equal(chartLabel(card), "Recent visits: 60, 140, 45");
  // After a lost connection the stream sends the recorder's rows again: nothing doubles.
  send(streams[0], [visitRow("2026-09-26T14:31:00.000+00:00", 60), visitRow("2026-09-26T14:33:00.000+00:00", 140)]);
  send(streams[0], []);
  streams[0].callback({});
  assert.equal(chartLabel(card), "Recent visits: 60, 140, 45");
  // A new session in the stream empties the chart.
  send(streams[0], [eventRow("2026-09-26T14:40:00.000+00:00", "session_started")]);
  assert.equal(text(card, ".history-chart"), "Completed visits appear here.");
});

test("an older session loads at most a week of history", (t) => {
  t.mock.timers.enable({ apis: ["Date"], now: Date.parse("2026-09-26T15:00:00Z") });
  const { streams, connection } = historyStream();
  setup({ "sensor.training_started": "2026-08-01T10:00:00+00:00" }, {}, { connection });
  setup({ "sensor.training_started": "unknown" }, {}, { connection });
  assert.deepEqual(
    streams.map((stream) => stream.message.start_time),
    ["2026-09-19T15:00:00.000Z", "2026-09-19T15:00:00.000Z"]
  );
});

test("without the recorder, visits of the open dashboard are added once each", async () => {
  const board = (hass, event) => update(hass, { "event.board_events": event });
  for (const options of [{}, historyStream({ fail: true })]) {
    const { hass, card } = setup({}, {}, options.connection ? { connection: options.connection } : {});
    await settle();
    const visit = { state: "2026-09-26T14:35:00.000+00:00", attributes: { event_type: "visit_completed", score: 26 } };
    let next = board(hass, visit);
    card.hass = next;
    card.hass = update(next, { "sensor.training_visits": "9" });
    assert.equal(chartLabel(card), "Recent visits: 26");
    // Undone, the visit leaves the chart once.
    next = board(next, { state: "2026-09-26T14:36:00.000+00:00", attributes: { event_type: "visit_undone" } });
    card.hass = next;
    card.hass = update(next, { "sensor.training_visits": "8" });
    assert.equal(text(card, ".history-chart"), "Completed visits appear here.");
    // The bot's visits count for nobody.
    card.hass = board(next, {
      state: "2026-09-26T14:37:00.000+00:00",
      attributes: { event_type: "visit_completed", score: 60, bot: true },
    });
    assert.equal(text(card, ".history-chart"), "Completed visits appear here.");
  }
  // Without the events entity there is nothing to follow.
  const { "event.board_events": _, ...states } = SESSION;
  const { streams, connection } = historyStream();
  const noEvents = mount("homedarts-training-card", makeHass({ states, connection }));
  assert.deepEqual(streams, []);
  assert.equal(text(noEvents, ".history-chart"), "Completed visits appear here.");
});

test("a new session starts an empty history and closes the stream of the old one", async (t) => {
  // Both sessions lie within the week of history the card loads.
  t.mock.timers.enable({ apis: ["Date"], now: Date.parse("2026-09-26T16:05:00Z") });
  const { streams, connection } = historyStream();
  const { hass, card } = setup({}, {}, { connection });
  send(streams[0], [visitRow("2026-09-26T14:31:00.000+00:00", 180)]);
  card.hass = update(hass, {
    "sensor.training_started": "2026-09-26T16:00:00+00:00",
    "sensor.training_visits": "0",
  });
  await settle();
  assert.deepEqual(
    streams.map((stream) => [stream.message.start_time, stream.closed]),
    [
      ["2026-09-26T14:30:00.000Z", true],
      ["2026-09-26T16:00:00.000Z", false],
    ]
  );
  assert.equal(text(card, ".history-chart"), "Completed visits appear here.");
  // A late message of the old stream is left out.
  send(streams[0], [visitRow("2026-09-26T16:01:00.000+00:00", 100)]);
  assert.equal(text(card, ".history-chart"), "Completed visits appear here.");
  send(streams[1], [visitRow("2026-09-26T16:02:00.000+00:00", 45)]);
  assert.equal(chartLabel(card), "Recent visits: 45");
});

test("a stream that fails after the next one started leaves that one alone", async () => {
  const pending = [];
  const connection = {
    subscribeMessage: (callback, message) =>
      new Promise((resolve, reject) => pending.push({ callback, message, resolve, reject })),
  };
  const { hass, card } = setup({}, {}, { connection });
  card.hass = update(hass, { "sensor.training_started": "2026-09-26T16:00:00+00:00" });
  // The first stream fails after the card closed it for the new session.
  pending[0].reject(new Error("connection lost"));
  await settle();
  pending[1].resolve(() => Promise.resolve());
  await settle();
  pending[1].callback({ states: { [EVENTS]: [visitRow("2026-09-26T16:02:00.000+00:00", 60)] } });
  assert.equal(chartLabel(card), "Recent visits: 60");
  // A stream that fails while it is the card's own leaves the events entity to add visits.
  card.hass = update(hass, { "sensor.training_started": "2026-09-26T17:00:00+00:00" });
  pending[2].reject(new Error("recorder stopped"));
  await settle();
  card.hass = update(hass, {
    "sensor.training_started": "2026-09-26T17:00:00+00:00",
    "event.board_events": { state: "2026-09-26T17:01:00.000+00:00", attributes: { event_type: "visit_completed", score: 81 } },
  });
  assert.equal(chartLabel(card), "Recent visits: 81");
});

test("the stream ends with the card and starts again when it returns", async () => {
  const { streams, connection } = historyStream({ unsubscribe: () => Promise.reject(new Error("offline")) });
  const { card } = setup({}, {}, { connection });
  send(streams[0], [visitRow("2026-09-26T14:31:00.000+00:00", 60)]);
  card.remove();
  await settle();
  assert.equal(streams[0].closed, true);
  document.body.append(card);
  assert.equal(streams.length, 2);
  send(streams[1], [visitRow("2026-09-26T14:31:00.000+00:00", 60)]);
  assert.equal(chartLabel(card), "Recent visits: 60");
  // Without the history chart there is no stream at all; a card placed before it has hass waits.
  const hidden = setup({}, { show_history: false }, { connection });
  assert.equal(streams.length, 2);
  hidden.card.setConfig({ type: "custom:homedarts-training-card", show_history: true });
  assert.equal(streams.length, 3);
  hidden.card.setConfig({ type: "custom:homedarts-training-card", show_history: false });
  await settle();
  assert.equal(streams[2].closed, true);
  const early = document.createElement("homedarts-training-card");
  document.body.append(early);
  early.setConfig({ type: "custom:homedarts-training-card" });
  early.hass = makeHass({ states: SESSION, connection });
  assert.equal(streams.length, 4);
});

test("a card that left the page opens no history stream when it gets a new state", async () => {
  const { streams, connection } = historyStream();
  const { hass, card } = setup({}, {}, { connection });
  card.remove();
  await settle();
  assert.equal(streams[0].closed, true);
  // Home Assistant can still hand a card new states after it left the page.
  card.hass = update(hass, {
    "event.board_events": { state: "2026-09-26T14:31:00.000+00:00", attributes: { event_type: "visit_completed", score: 60 } },
  });
  assert.equal(streams.length, 1);
  // Back on the page, the history follows the board again.
  document.body.append(card);
  assert.equal(streams.length, 2);
});

test("a new configuration keeps the history, also for a larger chart", () => {
  const { streams, connection } = historyStream();
  const { card } = setup({}, { history_size: 5 }, { connection });
  const rows = [60, 45, 100, 26, 140, 81, 180].map((score, index) =>
    visitRow(`2026-09-26T14:4${index}:00.000+00:00`, score)
  );
  send(streams[0], rows);
  assert.equal(chartLabel(card), "Recent visits: 100, 26, 140, 81, 180");
  card.setConfig({ type: "custom:homedarts-training-card", history_size: 10, title: "Practice room" });
  assert.equal(streams.length, 1);
  assert.equal(chartLabel(card), "Recent visits: 60, 45, 100, 26, 140, 81, 180");
});

test("the history size keeps between five and sixty visits, with labels up to thirty", () => {
  const rows = Array.from({ length: 70 }, (_, index) =>
    visitRow(new Date(Date.parse("2026-09-26T14:40:00Z") + index * 1000).toISOString(), (index * 7) % 181)
  );
  const chart = (config, states = {}, sent = rows.slice(-7)) => {
    const { streams, connection } = historyStream();
    const { card } = setup(states, config, { connection });
    send(streams[0], sent);
    return card;
  };
  const small = chart({ history_size: 2 });
  assert.equal($$(small, ".visit-bar").length, 5);
  assert.equal($$(small, ".visit-bar:not(.empty)").length, 5);
  // The card keeps the newest sixty visits, as many as the largest chart shows.
  const large = chart({ history_size: 100 }, {}, rows);
  assert.equal($$(large, ".visit-bar").length, 60);
  assert.equal($$(large, ".visit-bar:not(.empty)").length, 60);
  assert.equal($$(large, ".visit-bar .label").length, 0);
  assert.equal($$(large, ".visit-bar")[0].title, "S20 · S20 · S20 = 70");
  const invalid = chart({ history_size: "many" }, { "sensor.training_average": "unknown" });
  assert.equal($$(invalid, ".visit-bar").length, 20);
  assert.equal($$(invalid, ".visit-bar .label").length, 7);
  assert.equal($(invalid, ".average-line"), null);
  // A narrow chart shows the last ten slots, whose scores stay readable: the seven
  // visits and three empty slots; with more visits than that, the newest ten.
  const near = (card) => $$(card, ".visit-bar:not(.far)").map((bar) => (bar.classList.contains("empty") ? "·" : bar.title));
  assert.deepEqual(near(invalid).filter((slot) => slot === "·").length, 3);
  assert.equal(near(invalid).length, 10);
  const full = chart({}, {}, rows.slice(-15));
  assert.deepEqual(near(full), rows.slice(-10).map((row) => `S20 · S20 · S20 = ${row.a.score}`));
  assert.equal($$(full, ".visit-bar.empty:not(.far)").length, 0);
  assert.match($(full, "style").textContent, /@container \(max-width: 560px\) \{ \.visit-bar\.far \{ display: none; \} \}/);
});

test("past sessions list when they ended, how long they took and how they went", () => {
  const sessions = [
    { ended: "2026-09-25T20:00:00+00:00", duration_minutes: 42, darts: 150, average: 48.2, highest_visit: 100 },
    { ended: "2026-09-24T19:00:00+00:00", duration_minutes: 0.5, darts: 9, average: 30, highest_visit: 45 },
    { ended: "2026-09-23T18:00:00+00:00", duration_minutes: null, darts: 3, average: null, highest_visit: null },
    { ended: "not a date", darts: 3 },
  ];
  const { hass, card } = setup({ "sensor.training_last_session": { state: "48.2", attributes: { sessions } } });
  assert.equal($(card, ".sessions").hidden, false);
  const rows = $$(card, ".session-table tbody tr").map((row) =>
    [...row.children].map((cell) => cell.textContent.replace(/\s/g, " "))
  );
  assert.deepEqual(rows, [
    ["09/25, 8:00 PM", "42 min", "150", "48.2", "100"],
    ["09/24, 7:00 PM", "<1 min", "9", "30.0", "45"],
    ["09/23, 6:00 PM", "–", "3", "–", "–"],
  ]);
  card.hass = update(hass, { "sensor.training_last_session": { state: "unknown", attributes: { sessions: [] } } });
  assert.equal($(card, ".sessions").hidden, true);
});

// The last session as the integration booked it.
const LAST = {
  "sensor.training_last_session": {
    state: "48.2",
    attributes: { sessions: [{ ended: "2026-09-26T15:10:00+00:00", duration_minutes: 40, darts: 150, average: 48.2 }] },
  },
};

test("the session state tells whether a session runs or when it ended", () => {
  const { hass, card } = setup(LAST);
  assert.equal(text(card, ".session-state"), "Session running");
  // The end comes from the booked session: the switch also changes with every restart.
  card.hass = update(hass, { "switch.training_session": { state: "off", last_changed: "2026-09-27T08:00:00+00:00" } });
  assert.match(text(card, ".session-state"), /^Session ended 09\/26, 3:10\sPM$/);
  card.hass = update(hass, { "switch.training_session": "off", "sensor.training_last_session": "unknown" });
  assert.equal(text(card, ".session-state"), "No session running");
  // A switch that is not available tells nothing.
  card.hass = update(hass, { "switch.training_session": "unavailable" });
  assert.equal(text(card, ".session-state"), "");
  const { "switch.training_session": _, ...states } = SESSION;
  const lean = mount("homedarts-training-card", makeHass({ states }));
  assert.equal(text(lean, ".session-state"), "");
  assert.equal($(lean, '[data-action="session"]').hidden, true);
});

test("a new session and the end of a session need a second tap; a start does not", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { hass, card } = setup();
  const reset = $(card, '[data-action="new_session"]');
  const toggle = $(card, '[data-action="session"]');
  assert.deepEqual(
    [toggle.hidden, toggle.textContent, toggle.classList.contains("primary")],
    [false, "End session", false]
  );

  reset.click();
  assert.deepEqual([reset.textContent, reset.classList.contains("confirm")], ["Confirm?", true]);
  t.mock.timers.tick(4000);
  assert.deepEqual([reset.textContent, reset.classList.contains("confirm")], ["New session", false]);
  reset.click();
  reset.click();
  assert.deepEqual(hass.calls, [["button", "press", { entity_id: "button.dartboard_reset_training" }]]);

  toggle.click();
  assert.deepEqual([toggle.textContent, toggle.classList.contains("confirm")], ["Confirm?", true]);
  toggle.click();
  assert.deepEqual(hass.calls.at(-1), ["switch", "turn_off", { entity_id: "switch.dartboard_training_session" }]);

  card.hass = update(hass, { "switch.training_session": "off" });
  assert.deepEqual([toggle.textContent, toggle.classList.contains("primary")], ["Start session", true]);
  toggle.click();
  assert.deepEqual(hass.calls.at(-1), ["switch", "turn_on", { entity_id: "switch.dartboard_training_session" }]);
  assert.equal(hass.calls.length, 3);
});

test("session controls ignore taps in the preview and without their entities", () => {
  const { hass, card } = setup();
  card.preview = true;
  for (const action of ["new_session", "new_session", "session", "session"]) {
    $(card, `[data-action="${action}"]`).click();
  }
  assert.deepEqual(hass.calls, []);
  assert.equal(text(card, '[data-action="new_session"]'), "New session");

  const { "switch.training_session": _, "button.reset_training": __, ...states } = SESSION;
  const bare = makeHass({ states });
  const lean = mount("homedarts-training-card", bare);
  assert.equal($(lean, '[data-action="new_session"]').disabled, true);
  $(lean, '[data-action="session"]').click();
  assert.deepEqual(bare.calls, []);
});

test("heatmap, statistics, top list, history, sessions and controls can be hidden", () => {
  const heatOnly = setup({}, { show_stats: false, show_top: false }).card;
  assert.equal($(heatOnly, ".body").getAttribute("class"), "body single");
  assert.equal($(heatOnly, ".side"), null);
  const sideOnly = setup({}, { show_heatmap: false }).card;
  assert.equal($(sideOnly, ".body").getAttribute("class"), "body single");
  assert.equal($(sideOnly, ".heat"), null);
  assert.equal($$(sideOnly, ".tile").length, 8);
  const topOnly = setup({}, { show_heatmap: false, show_stats: false }).card;
  assert.equal($(topOnly, ".tiles"), null);
  assert.equal($$(topOnly, ".top-row").length, 5);
  const statsOnly = setup({}, { show_heatmap: false, show_top: false }).card;
  assert.equal($(statsOnly, ".top"), null);
  const minimal = setup(
    { "sensor.training_last_session": { state: "40", attributes: { sessions: [] } } },
    {
      show_heatmap: false,
      show_stats: false,
      show_top: false,
      show_history: false,
      show_sessions: false,
      show_reset: false,
    }
  ).card;
  for (const selector of [".body", ".history", ".sessions", ".footer-row"]) assert.equal($(minimal, selector), null);
  assert.equal(text(minimal, ".average"), "55.8");
  assert.equal($(setup().card, ".body").getAttribute("class"), "body");
});

test("the training card speaks German", () => {
  const { card } = setup({}, {}, { language: "de" });
  assert.equal(text(card, ".title"), "Training · Dartboard");
  assert.equal(text(card, ".since"), "seit 26.09., 14:30");
  assert.equal(text(card, ".average"), "55,8");
  assert.equal(text(card, ".average-label"), "3-Dart-Average");
  assert.equal(text(card, '[data-tile="triple_rate"] .value'), "12,5 %");
  assert.equal(text(card, ".streak"), "🔥 3 Tage in Folge");
  assert.equal(text(card, ".goal-text"), "60 / 120 Darts heute");
  assert.equal(text(card, ".session-state"), "Session läuft");
  assert.equal(text(card, '[data-action="session"]'), "Session beenden");
  assert.equal($(card, ".heat-bed title").textContent.includes("Treffer"), true);
  card.hass = withLanguage(makeHass({ states: SESSION }), "en");
  assert.equal(text(card, ".average"), "55.8");
  // Without a locale, Home Assistant's language decides.
  const ended = { ...SESSION, ...LAST, "switch.training_session": "off" };
  const legacy = mount("homedarts-training-card", {
    ...makeHass({ states: ended }),
    locale: undefined,
    language: "de",
  });
  assert.equal(text(legacy, ".session-state"), "Session beendet 26.09., 15:10");
});

const BESTS = {
  "sensor.personal_best": {
    state: "2026-09-20T18:00:00+00:00",
    attributes: {
      record: "highest_checkout",
      value: 121,
      previous: 100,
      name: "Alex",
      highest_visit: 140,
      highest_checkout: 121,
      fewest_darts_501: 18,
      fewest_darts_301: 12,
      fewest_darts_x: 3,
      best_cricket_mpr: 3.125,
      best_session_average: 58.44,
      around_the_clock: 38,
      doubles: 0,
      bobs_27: 412,
    },
  },
  "sensor.training_streak": { state: "3", attributes: { best_streak: 12 } },
};
const bests = (card) => $$(card, ".bests dl > div").map((row) => [row.firstChild.textContent, row.lastChild.textContent]);

test("personal bests list every record with a value and the longest streak", () => {
  const { hass, card } = setup(BESTS);
  assert.equal($(card, ".bests").hidden, false);
  assert.equal(text(card, ".bests .section-label"), "Personal bests");
  assert.deepEqual(bests(card), [
    ["Highest visit", "140"],
    ["Highest checkout", "121"],
    ["Best 301", "12 darts"],
    ["Best 501", "18 darts"],
    ["Best Cricket MPR", "3.13"],
    ["Best session average", "58.4"],
    ["Around the Clock", "38 darts"],
    ["Bob's 27", "412 points"],
    ["Longest streak", "12 days"],
  ]);
  card.hass = update(hass, { "sensor.training_streak": { state: "1", attributes: { best_streak: 1 } } });
  assert.deepEqual(bests(card).at(-1), ["Longest streak", "1 day"]);
  // Without records the section waits for the first one.
  card.hass = update(hass, { "sensor.personal_best": "unknown", "sensor.training_streak": "0" });
  assert.equal($(card, ".bests").hidden, true);
  assert.equal($(setup(BESTS, { show_bests: false }).card, ".bests"), null);
  const german = setup(BESTS, {}, { language: "de" }).card;
  assert.equal(text(german, ".bests .section-label"), "Bestleistungen");
  assert.deepEqual(bests(german).slice(2, 5), [
    ["Bestes 301-Leg", "12 Darts"],
    ["Bestes 501-Leg", "18 Darts"],
    ["Beste MPR im Cricket", "3,13"],
  ]);
  assert.deepEqual(bests(german).at(-1), ["Längste Serie", "12 Tage"]);
});

test("the statistics tiles are read out, and a visible link with an arrow opens the details", () => {
  const { card } = setup();
  const tiles = $(card, ".tiles");
  // A group, not a button: a button would hide the eight figures from screen readers.
  assert.deepEqual(
    [tiles.getAttribute("role"), tiles.getAttribute("tabindex"), tiles.getAttribute("aria-label")],
    ["group", null, "Training statistics"]
  );
  assert.equal(text(card, '[data-tile="highest"]'), "140Highest visit");
  // The link says "Details" with an arrow; a screen reader hears what it opens.
  const details = $(card, ".details");
  assert.deepEqual(
    [details.localName, details.type, details.className, details.textContent, details.getAttribute("aria-label")],
    ["button", "button", "link details", "Details", "Training statistics, open the details"]
  );
  assert.equal(details.querySelectorAll(".cue.details.inline").length, 1);
  const opened = moreInfo(card);
  tiles.click();
  details.click();
  assert.deepEqual(opened, ["sensor.dartboard_training_darts"]);
  assert.equal($(setup({}, { show_stats: false }).card, ".details"), null);
  // The fire emoji is decoration only.
  assert.equal($(card, ".streak [aria-hidden]").textContent, "🔥");
});

test("board events other than visits and session starts leave the card alone", () => {
  const { hass, card } = setup();
  $(card, ".title").textContent = "stale";
  const event = (type) => ({ state: new Date().toISOString(), attributes: { event_type: type } });
  let next = update(hass, { "event.board_events": event("takeout_finished") });
  card.hass = next;
  assert.equal(text(card, ".title"), "stale");
  next = update(next, { "event.board_events": { ...event("visit_completed"), attributes: { event_type: "visit_completed", score: 60, darts: 3, segments: ["S20", "S20", "S20"] } } });
  card.hass = next;
  assert.equal(text(card, ".title"), "Training · Dartboard");
});

test("numbers, times and time zones follow the user profile", () => {
  const ended = { ...SESSION, ...LAST, "switch.training_session": "off" };
  const profile = (locale, config) => {
    const hass = makeHass({ states: ended });
    return mount("homedarts-training-card", { ...hass, locale: { ...hass.locale, ...locale }, config });
  };
  // English words with German numbers and a 24-hour clock in the server's time zone.
  const card = profile(
    { number_format: "decimal_comma", time_format: "24", time_zone: "server" },
    { time_zone: "Europe/Berlin" }
  );
  assert.equal(text(card, ".average"), "55,8");
  assert.equal(text(card, ".session-state"), "Session ended 09/26, 17:10");
  // The browser's time zone, a 12-hour clock and no grouping.
  const local = profile({ number_format: "none", time_format: "12", time_zone: "local" }, { time_zone: "Europe/Berlin" });
  assert.match(text(local, ".session-state"), /^Session ended 09\/26, 3:10\sPM$/);
  assert.equal(text(profile({ number_format: "space_comma" }), ".average"), "55,8");
  const system = new Intl.NumberFormat(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(55.75);
  assert.equal(text(profile({ number_format: "system", time_format: "system" }), ".average"), system);
  assert.equal(text(profile({ number_format: "quote_decimal" }), ".average"), "55.8");
  // The date follows the profile's date format, the language keeps its separators.
  const date = (date_format) => text(profile({ date_format, time_format: "24" }), ".session-state");
  assert.equal(date("DMY"), "Session ended 26/09, 15:10");
  assert.equal(date("MDY"), "Session ended 09/26, 15:10");
  assert.equal(date("YMD"), "Session ended 09/26, 15:10");
  assert.equal(date("language"), "Session ended 09/26, 15:10");
  const german = (date_format) =>
    text(profile({ language: "de", date_format, time_format: "24" }), ".session-state").replace(/^\S+ \S+ /, "");
  assert.deepEqual([german("DMY"), german("MDY"), german("constructor")], ["26.09., 15:10", "09.26., 15:10", "26.09., 15:10"]);
  const browser = new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date("2026-09-26T15:10:00+00:00"));
  assert.equal(date("system"), `Session ended ${browser}`);
});
