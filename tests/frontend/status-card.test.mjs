// The status card in a browser DOM: detection, connections, board PC, cameras and maintenance.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, READY, camera, loadCards, makeHass, moreInfo, mount, text, update, withLanguage } from "./dom.mjs";

await loadCards();

const BOARD = {
  ...READY,
  "button.restart": "unknown",
  "binary_sensor.cloud_link": "on",
  "sensor.cpu_usage": "12.4",
  "sensor.memory_usage": { state: "45.2", attributes: { unit_of_measurement: "%" } },
  "sensor.detection_fps": "24.5",
  "update.board_software": { state: "on", attributes: { installed_version: "1.4.2", latest_version: "1.5.0" } },
  "sensor.host_os": "Ubuntu 22.04.4 LTS",
  "sensor.host_processor": "Intel(R) Core(TM) i3-9100T CPU @ 3.10GHz",
  "sensor.vision_version": "0.9.1",
};
const CAMERAS = [camera(2, { fps: "29.97" }), camera(1, { problem: "on" })];
const setup = (states = {}, config = {}, options = {}) => {
  const hass = makeHass({ states: { ...BOARD, ...states }, cameras: CAMERAS, ...options });
  return { hass, card: mount("homedarts-status-card", hass, config) };
};
const without = (...keys) => Object.fromEntries(Object.entries(BOARD).filter(([key]) => !keys.includes(key)));
const cameraRows = (card) =>
  $$(card, ".camera").map((item) => [
    item.className,
    item.querySelector(".camera-name").textContent,
    item.querySelector(".dot").title,
    item.querySelector(".fps").textContent,
    item.querySelector("[data-calibrate]")?.textContent ?? null,
  ]);

test("the status card shows the board state, its detection and its version", () => {
  const { card } = setup();
  assert.equal(text(card, ".title"), "Dartboard");
  assert.equal(text(card, ".pill"), "Ready – throw!");
  assert.equal(text(card, ".detection .state"), "Ready – throw!");
  // Status colours come from the theme.
  assert.equal(card.style.getPropertyValue("--ad-status"), "var(--success-color, #43a047)");
  assert.equal(card.style.getPropertyValue("--ad-accent"), "var(--primary-color)");
  assert.equal($(card, ".toggle").getAttribute("aria-checked"), "true");
  assert.equal($(card, ".toggle").disabled, false);
  assert.equal(text(card, ".version"), "Version 1.4.2");
  assert.equal(card.getCardSize(), 7);
  assert.equal(text(setup({}, { title: "Board PC" }).card, ".title"), "Board PC");
  assert.equal(text(setup({}, {}, { device: { sw_version: null } }).card, ".version"), "–");
});

test("the update badge offers a new version or confirms the current one", () => {
  const { hass, card } = setup();
  const badge = $(card, ".update-badge");
  assert.deepEqual(
    [badge.hidden, badge.textContent, badge.classList.contains("ok"), badge.disabled],
    [false, "Update to 1.5.0", false, false]
  );
  const opened = moreInfo(card);
  badge.click();
  assert.deepEqual(opened, ["update.dartboard_board_software"]);

  card.hass = update(hass, { "update.board_software": { state: "off", attributes: { latest_version: "1.4.2" } } });
  assert.deepEqual(
    [badge.hidden, badge.textContent, badge.classList.contains("ok"), badge.disabled],
    [false, "Up to date", true, true]
  );
  card.hass = update(hass, { "update.board_software": "on" });
  assert.deepEqual([badge.textContent, badge.classList.contains("ok")], ["Update to", false]);
  card.hass = update(hass, { "update.board_software": "unavailable" });
  assert.equal(badge.hidden, true);
});

test("the detection switch stops and starts detection", () => {
  const { hass, card } = setup();
  const toggle = $(card, ".toggle");
  toggle.click();
  card.hass = update(hass, { "switch.detection": "off" });
  assert.equal(toggle.getAttribute("aria-checked"), "false");
  assert.equal(text(card, ".detection .state"), "Detection stopped");
  toggle.click();
  assert.deepEqual(hass.calls, [
    ["switch", "turn_off", { entity_id: "switch.dartboard_detection" }],
    ["switch", "turn_on", { entity_id: "switch.dartboard_detection" }],
  ]);
});

test("without a detection switch the buttons follow the board status; offline or in the preview nothing happens", () => {
  // The board detects darts, so the switch is on and a tap stops detection.
  const hass = makeHass({ states: without("switch.detection") });
  const card = mount("homedarts-status-card", hass);
  assert.equal($(card, ".toggle").getAttribute("aria-checked"), "true");
  $(card, ".toggle").click();
  assert.deepEqual(hass.calls, [["button", "press", { entity_id: "button.dartboard_stop" }]]);
  // Stopped, a tap starts it again.
  card.hass = update(hass, { "sensor.local_status": "Stopped" });
  assert.equal($(card, ".toggle").getAttribute("aria-checked"), "false");
  $(card, ".toggle").click();
  assert.deepEqual(hass.calls.at(-1), ["button", "press", { entity_id: "button.dartboard_start" }]);

  const offline = setup({ "binary_sensor.local_connected": "off" }).card;
  assert.equal(text(offline, ".pill"), "Board unreachable");
  assert.equal($(offline, ".toggle").disabled, true);
  const lean = mount("homedarts-status-card", makeHass({ states: without("switch.detection", "button.stop") }));
  assert.equal($(lean, ".toggle").disabled, true);

  const preview = setup();
  preview.card.preview = true;
  $(preview.card, ".toggle").click();
  assert.deepEqual(preview.hass.calls, []);
});

test("connection chips show the board, realtime and cloud links and open more-info", () => {
  const { card } = setup({ "binary_sensor.realtime_connected": "off" });
  assert.deepEqual(
    $$(card, ".chip").map((chip) => [chip.className, chip.textContent, chip.dataset.entity]),
    [
      ["chip on", "Board Manager", "binary_sensor.dartboard_local_connected"],
      ["chip off", "Realtime", "binary_sensor.dartboard_realtime_connected"],
      ["chip on", "Board cloud", "binary_sensor.dartboard_cloud_link"],
    ]
  );
  // Each chip says what it measures, as its tooltip and as its accessible name, which
  // starts with the label that it shows.
  const told = [
    "Board Manager: Home Assistant reaches the Board Manager.",
    "Realtime: Live events arrive from the board.",
    "Board cloud: The board's own link to Autodarts, as the board reports it; HomeDarts doesn't use it.",
  ];
  assert.deepEqual($$(card, ".chip").map((chip) => chip.title), told);
  assert.deepEqual($$(card, ".chip").map((chip) => chip.getAttribute("aria-label")), told);
  const german = setup({}, {}, { language: "de" }).card;
  assert.deepEqual(
    $$(german, ".chip").map((chip) => [chip.textContent, chip.title]),
    [
      ["Board Manager", "Board Manager: Home Assistant erreicht den Board Manager."],
      ["Echtzeit", "Echtzeit: Live-Ereignisse kommen vom Board an."],
      ["Board-Cloud", "Board-Cloud: Die eigene Verbindung des Boards zu Autodarts, wie das Board sie meldet; HomeDarts nutzt sie nicht."],
    ]
  );
  const opened = moreInfo(card);
  $$(card, ".chip")[2].click();
  $(card, ".chips").click();
  assert.deepEqual(opened, ["binary_sensor.dartboard_cloud_link"]);

  // Older integrations report the cloud upstream as a switch.
  const upstream = mount(
    "homedarts-status-card",
    makeHass({ states: { ...without("binary_sensor.cloud_link"), "switch.upstream": "off" } })
  );
  assert.deepEqual(
    $$(upstream, ".chip").map((chip) => [chip.className, chip.textContent, chip.dataset.entity, chip.title]).at(-1),
    ["chip off", "Board cloud", "switch.dartboard_upstream", told[2]]
  );
  const upstreamOpened = moreInfo(upstream);
  $$(upstream, ".chip").at(-1).click();
  assert.deepEqual(upstreamOpened, ["switch.dartboard_upstream"]);
  const lean = mount("homedarts-status-card", makeHass({ states: without("binary_sensor.realtime_connected") }));
  assert.deepEqual(
    $$(lean, ".chip").map((chip) => chip.textContent),
    ["Board Manager", "Board cloud"]
  );
});

test("the board PC tile shows load, memory, detection rate and the system", () => {
  const { hass, card } = setup();
  assert.equal($(card, ".system-tile").hidden, false);
  assert.deepEqual(
    $$(card, ".metric").map((metric) => [
      metric.querySelector(".value").textContent,
      metric.querySelector(".name").textContent,
      metric.dataset.entity,
    ]),
    [
      ["12%", "CPU", "sensor.dartboard_cpu_usage"],
      ["45%", "Memory", "sensor.dartboard_memory_usage"],
      ["24.5 fps", "Detection", "sensor.dartboard_detection_fps"],
    ]
  );
  // The metrics are buttons, so the keyboard reaches their details too.
  assert.deepEqual(
    $$(card, ".metric").map((metric) => metric.localName),
    ["button", "button", "button"]
  );
  assert.equal($(card, ".system-info").hidden, false);
  assert.equal(text(card, ".system-info"), "Ubuntu 22.04.4 LTS · Intel Core i3-9100T · Detection 0.9.1");
  const opened = moreInfo(card);
  $$(card, ".metric .value")[1].click();
  $(card, ".metrics").click();
  $(card, ".system-info").click();
  assert.deepEqual(opened, ["sensor.dartboard_memory_usage", "sensor.dartboard_host_os"]);

  card.hass = update(hass, {
    "sensor.cpu_usage": "unavailable",
    "sensor.memory_usage": "512",
    "sensor.vision_version": "unknown",
  });
  assert.deepEqual(
    $$(card, ".metric .value").map((value) => value.textContent),
    ["512", "24.5 fps"]
  );
  assert.equal(text(card, ".system-info"), "Ubuntu 22.04.4 LTS · Intel Core i3-9100T");
});

test("the board PC tile hides without data and shows the system alone", () => {
  const system = ["sensor.cpu_usage", "sensor.memory_usage", "sensor.detection_fps"];
  const infoOnly = mount("homedarts-status-card", makeHass({ states: without(...system) }));
  assert.equal($(infoOnly, ".system-tile").hidden, false);
  assert.equal($$(infoOnly, ".metric").length, 0);
  const nothing = mount(
    "homedarts-status-card",
    makeHass({ states: without(...system, "sensor.host_os", "sensor.host_processor", "sensor.vision_version") })
  );
  assert.equal($(nothing, ".system-tile").hidden, true);
  assert.equal($(nothing, ".system-info").hidden, true);
});

test("cameras are listed by number with their frame rate or their problem", () => {
  const { card } = setup();
  assert.equal($(card, ".cameras-section").hidden, false);
  assert.deepEqual(cameraRows(card), [
    ["camera problem", "Camera 1", "Problem", "Problem", "Calibrate"],
    ["camera", "Camera 2", "OK", "30.0 fps", "Calibrate"],
  ]);
  const opened = moreInfo(card);
  $$(card, ".camera-name")[1].click();
  $(card, ".camera-grid").click();
  assert.deepEqual(opened, ["camera.dartboard_camera_2_board_camera"]);
});

test("cameras without an image, a frame rate or a calibration still appear", () => {
  const cameras = [
    camera(1, { image: null, fps: "unavailable", calibrate: null }),
    camera(2, { image: null, problem: null }),
    camera(3, { image: null, problem: null, fps: null }),
    // A camera attribute that is not a camera number is ignored.
    camera(0),
  ];
  const card = mount("homedarts-status-card", makeHass({ states: BOARD, cameras }));
  assert.deepEqual(cameraRows(card), [
    ["camera", "Camera 1", "OK", "OK", null],
    ["camera", "Camera 2", "OK", "30.0 fps", "Calibrate"],
    ["camera", "Camera 3", "OK", "OK", "Calibrate"],
  ]);
  assert.deepEqual(
    $$(card, ".camera-name").map((name) => name.dataset.entity),
    ["binary_sensor.dartboard_camera_1_individual_camera_problem", "sensor.dartboard_camera_2_camera_fps", ""]
  );
  const none = mount("homedarts-status-card", makeHass({ states: BOARD }));
  assert.equal($(none, ".cameras-section").hidden, true);
});

test("calibrating a camera needs a second tap within four seconds", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { hass, card } = setup();
  const calibrate = (number) => $$(card, "[data-calibrate]")[number - 1];
  calibrate(1).click();
  assert.deepEqual(
    [calibrate(1).textContent, calibrate(1).classList.contains("confirm"), calibrate(2).textContent],
    ["Confirm?", true, "Calibrate"]
  );
  t.mock.timers.tick(4000);
  assert.equal(calibrate(1).textContent, "Calibrate");
  calibrate(2).click();
  calibrate(2).click();
  assert.deepEqual(hass.calls, [["button", "press", { entity_id: "button.dartboard_camera_2_calibrate_camera" }]]);
  assert.equal(calibrate(2).textContent, "Calibrate");

  card.preview = true;
  calibrate(1).click();
  calibrate(1).click();
  assert.equal(hass.calls.length, 1);
  const offline = setup({ "binary_sensor.local_connected": "off" }).card;
  assert.deepEqual(
    $$(offline, "[data-calibrate]").map((button) => button.disabled),
    [true, true]
  );
});

test("calibration, reset and restart need a second tap within four seconds", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { hass, card } = setup();
  const button = (action) => $(card, `[data-action="${action}"]`);
  assert.deepEqual(
    $$(card, ".controls button").map((item) => [item.textContent, item.hidden, item.disabled]),
    [
      // Beside each camera's own calibration, this one calibrates them all.
      ["Calibrate all", false, false],
      ["Reset detection", false, false],
      ["Restart", false, false],
    ]
  );
  button("restart").click();
  assert.deepEqual(
    [button("restart").textContent, button("restart").classList.contains("confirm")],
    ["Confirm?", true]
  );
  t.mock.timers.tick(4000);
  assert.equal(button("restart").textContent, "Restart");
  button("restart").click();
  button("calibrate").click();
  assert.equal(button("restart").textContent, "Restart");
  button("calibrate").click();
  assert.deepEqual(hass.calls, [["button", "press", { entity_id: "button.dartboard_calibrate" }]]);
  $(card, ".controls").click();
  card.preview = true;
  button("reset").click();
  button("reset").click();
  assert.equal(hass.calls.length, 1);
});

test("maintenance buttons hide without their entity and wait while the board is offline", () => {
  const lean = mount("homedarts-status-card", makeHass({ states: without("button.restart") }));
  assert.deepEqual(
    $$(lean, ".controls button").map((item) => item.hidden),
    [false, false, true]
  );
  const offline = setup({ "binary_sensor.local_connected": "off" }).card;
  assert.deepEqual(
    $$(offline, ".controls button").map((item) => item.disabled),
    [true, true, true]
  );
});

test("a camera that changes redraws the card", () => {
  const { hass, card } = setup();
  $(card, ".title").textContent = "stale";
  card.hass = update(hass, { "sensor.dartboard_camera_2_camera_fps": { state: "12", attributes: { camera: 2 } } });
  assert.equal(text(card, ".title"), "Dartboard");
  assert.equal(cameraRows(card)[1][3], "12.0 fps");
});

test("connections, board PC, cameras and controls can be hidden", () => {
  const { card } = setup(
    {},
    { show_connection: false, show_system: false, show_cameras: false, show_controls: false, accent_color: 7 }
  );
  for (const selector of [".chips", ".system-tile", ".cameras-section", ".controls"]) {
    assert.equal($(card, selector), null);
  }
  assert.equal(text(card, ".version"), "Version 1.4.2");
  assert.equal(card.style.getPropertyValue("--ad-accent"), "var(--primary-color)");
});

test("the status card speaks German", () => {
  const { hass, card } = setup({}, {}, { language: "de" });
  assert.equal(text(card, ".pill"), "Bereit – wirf!");
  assert.equal(text(card, ".detection .name"), "Erkennung");
  assert.equal(text(card, ".update-badge"), "Update auf 1.5.0");
  assert.deepEqual(cameraRows(card)[0], ["camera problem", "Kamera 1", "Störung", "Störung", "Kalibrieren"]);
  assert.equal(cameraRows(card)[1][3], "30,0 fps");
  assert.deepEqual(
    $$(card, ".controls button").map((item) => item.textContent),
    ["Alle kalibrieren", "Erkennung zurücksetzen", "Neu starten"]
  );
  card.hass = withLanguage(hass, "en");
  assert.equal(text(card, ".update-badge"), "Update to 1.5.0");
});

test("a card removed before it was drawn has nothing to redraw", () => {
  const card = document.createElement("homedarts-status-card");
  document.body.append(card);
  card.remove();
  assert.equal(card.shadowRoot.innerHTML, "");
});

test("the share of corrected darts shows how well detection works", () => {
  const { card } = setup({ "sensor.correction_rate": { state: "3.25", attributes: { unit_of_measurement: "%" } } });
  assert.deepEqual(
    [$$(card, ".metric .value").at(-1).textContent, $$(card, ".metric .name").at(-1).textContent],
    ["3.3%", "Corrected"]
  );
  const german = setup({ "sensor.correction_rate": "3.25" }, {}, { language: "de" }).card;
  assert.equal($$(german, ".metric .value").at(-1).textContent, "3,3 %");
  assert.equal($$(german, ".metric .name").at(-1).textContent, "Korrigiert");
});

test("an empty board PC tile stays hidden, since hidden beats every display rule", () => {
  const card = mount("homedarts-status-card", makeHass({ states: without("sensor.cpu_usage", "sensor.memory_usage", "sensor.detection_fps", "sensor.host_os", "sensor.host_processor", "sensor.vision_version") }));
  assert.equal($(card, ".system-tile").hidden, true);
  assert.match($(card, "style").textContent, /\[hidden\] \{ display: none !important; \}/);
});

test("the keyboard focus stays on a calibration button while it asks for confirmation", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { hass, card } = setup();
  const button = () => $$(card, "[data-calibrate]")[1];
  button().focus();
  assert.equal(card.shadowRoot.activeElement, button());
  button().click();
  // The confirmation redraws the cameras; the new button has the focus again.
  assert.equal(button().textContent, "Confirm?");
  assert.equal(card.shadowRoot.activeElement, button());
  t.mock.timers.tick(4000);
  assert.equal(button().textContent, "Calibrate");
  assert.equal(card.shadowRoot.activeElement, button());
  // Other redraws keep the focus too, also on a camera's name and a chip.
  $$(card, ".camera-name")[0].focus();
  card.hass = update(hass, { "sensor.dartboard_camera_2_camera_fps": { state: "12", attributes: { camera: 2 } } });
  assert.equal(card.shadowRoot.activeElement, $$(card, ".camera-name")[0]);
  $$(card, ".chip")[1].focus();
  card.hass = update(hass, { "binary_sensor.realtime_connected": "off" });
  assert.equal(card.shadowRoot.activeElement, $$(card, ".chip")[1]);
  assert.equal($$(card, ".chip")[1].className, "chip off");
});
