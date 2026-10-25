/*
 * Autodarts cards for Home Assistant, served by the Autodarts integration.
 *
 * - homedarts-card: the current visit on a dartboard drawn with the geometry of
 *   the Autodarts Board Manager. Hit beds blink, darts appear at their detected
 *   position and the board glows in the detection status colour.
 * - homedarts-training-card: the local training session with a hit heatmap,
 *   statistics, personal bests, the most hit beds and the recent visits.
 * - homedarts-status-card: detection, connections, cameras, the board PC and
 *   maintenance controls at a glance.
 * - homedarts-scoreboard-card, homedarts-players-card and homedarts-doubles-card:
 *   the game at the board, the player profiles and the hit rate per double.
 * - homedarts-leaderboard-card: records across all players, for all time, the
 *   last four weeks or this week.
 * - The dashboard strategy "custom:homedarts" builds a complete dashboard with
 *   live, scoreboard, training, players and board views for every board.
 *
 * Card editors are forms of Home Assistant (getConfigForm); only the strategy,
 * which Home Assistant offers no form for, brings its own editor element.
 *
 * The texts of the cards are one module per language in text/, a small file for its
 * translators. The integration serves this folder at the address of its version, so
 * the imports below get the texts of this very version (card.py).
 */

import en from "./text/en.js";
import de from "./text/de.js";
import es from "./text/es.js";
import fr from "./text/fr.js";
import nl from "./text/nl.js";

const CARD_TYPE = "homedarts-card";
const TRAINING_TYPE = "homedarts-training-card";
const STATUS_TYPE = "homedarts-status-card";
const SCOREBOARD_TYPE = "homedarts-scoreboard-card";
const PLAYERS_TYPE = "homedarts-players-card";
const DOUBLES_TYPE = "homedarts-doubles-card";
const LEADERBOARD_TYPE = "homedarts-leaderboard-card";
const STRATEGY_TYPE = "homedarts";
const STRATEGY_ELEMENT = `ll-strategy-dashboard-${STRATEGY_TYPE}`;
const STRATEGY_EDITOR_TYPE = "homedarts-strategy-editor";
// The documentation website, in English and in German under de/.
const DOCUMENTATION = "https://dennis-otto.github.io/homedarts-for-autodarts";
// Files of the action homedarts.export, downloaded with the user's login.
const EXPORT_DOWNLOADS = "/api/homedarts/export/";

// Board Manager geometry in millimetres; dart coordinates are normalised to
// the outer edge of the double ring (170 mm) with y pointing to the 20.
const NORM = 170;
const R = {
  bull: 7,
  outerBull: 17,
  trebleIn: 97,
  trebleOut: 107,
  doubleIn: 160,
  doubleOut: 170,
  numbers: 197,
  board: 225,
};
const NUMBERS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5];
const BEDS = {
  SI: [R.outerBull, R.trebleIn],
  T: [R.trebleIn, R.trebleOut],
  SO: [R.trebleOut, R.doubleIn],
  D: [R.doubleIn, R.doubleOut],
  M: [R.doubleOut, R.board],
};

const STYLES = {
  flat: {
    black: "#212121",
    white: "#fffde7",
    red: "#ef5350",
    green: "#66bb6a",
    surround: "#212121",
    wire: "none",
    numbers: "#ffffff",
  },
  classic: {
    black: "#1b1b1b",
    white: "#f1e4c3",
    red: "#d42f2f",
    green: "#1d9150",
    surround: "#101010",
    wire: "#b8bcc2",
    numbers: "#f5f5f5",
  },
  // A quiet board that lets a heatmap stand out.
  muted: {
    black: "#2a2d33",
    white: "#3b3f47",
    red: "#34373e",
    green: "#303339",
    surround: "#1c1e22",
    wire: "#4f545d",
    numbers: "#d6d9de",
  },
};

// The theme's colours for success, warnings and errors, with the former colours as fallback.
const STATUS_COLORS = {
  ready: "var(--success-color, #43a047)",
  takeout: "var(--amber-color, #fbc02d)",
  stopped: "var(--warning-color, #fb8c00)",
  calibrating: "var(--purple-color, #8e24aa)",
  problem: "var(--error-color, #e53935)",
  offline: "var(--error-color, #e53935)",
};

const GOLD = "#ffd60a";

const VISIT_COLORS = {
  max: GOLD,
  high: "#ff8c42",
  ton: "#43b581",
  good: "var(--ad-accent)",
  low: "#8a8f98",
};

// Colour names of Home Assistant's colour picker; they follow the theme.
const THEME_COLORS = new Set([
  "primary",
  "accent",
  "red",
  "pink",
  "purple",
  "deep-purple",
  "indigo",
  "blue",
  "light-blue",
  "cyan",
  "teal",
  "green",
  "light-green",
  "lime",
  "yellow",
  "amber",
  "orange",
  "deep-orange",
  "brown",
  "light-grey",
  "grey",
  "dark-grey",
  "blue-grey",
  "black",
  "white",
]);

// Every language of the cards, English first: its file in text/ has the keys of
// text/en.js in their order (CONTRIBUTING.md#translations).
const TEXT = { en, de, es, fr, nl };

const DEFAULTS = {
  layout: "auto",
  board_style: "classic",
  highlight: "visit",
  blink: true,
  show_markers: true,
  show_numbers: true,
  show_stats: true,
  show_connection: true,
  show_controls: true,
  show_recent: true,
  show_practice: true,
  // A tap on a dart of the visit corrects it; the keypad enters darts by hand while
  // Practice manual entry is on, and on a dartboard without Autodarts.
  corrections: true,
  keypad: false,
  // The summary of a finished match stays until the next game, or this many seconds.
  show_summary: true,
  summary_seconds: 0,
};

const TRAINING_DEFAULTS = {
  mode: "beds",
  board_style: "muted",
  show_heatmap: true,
  show_stats: true,
  show_bests: true,
  show_top: true,
  show_history: true,
  show_reset: true,
  show_sessions: true,
  history_size: 20,
  show_heatmap_controls: true,
};

// Hits per bed, per number, where the darts landed, or where to aim.
const HEAT_MODES = ["beds", "numbers", "positions", "aim"];

const STATUS_DEFAULTS = {
  show_connection: true,
  show_cameras: true,
  show_system: true,
  show_controls: true,
};

const DOUBLES_DEFAULTS = {};

const PLAYERS_DEFAULTS = {
  show_head_to_head: true,
  show_matches: true,
  // The export writes a file with player names; the button appears on request.
  export: false,
  export_format: "csv",
  show_badges: true,
  show_locked: true,
  show_trends: true,
  show_spread: true,
  trend_weeks: 12,
};

const LEADERBOARD_DEFAULTS = {
  period: "all",
  show_period: true,
  limit: 3,
};

const SCOREBOARD_DEFAULTS = {
  full_height: false,
  show_visit: true,
  show_status: true,
  // A button that shows the scoreboard alone on the whole screen, which then stays on.
  fullscreen_button: true,
  keep_awake: true,
  // The caller speaks only when switched on, and a tap unlocks the sound.
  caller: false,
  call_scores: true,
  call_checkouts: true,
  call_results: true,
  call_sounds: true,
  // For blind and low-vision players: every dart, the route of a checkout and the next target.
  call_darts: "off",
  call_route: false,
  call_target: false,
  // The new game screen; without a list of games it offers every game of the board.
  lobby: true,
  // Panels in turn when no game runs and nobody threw or tapped for a while.
  idle: true,
  idle_after: 180,
  idle_interval: 10,
  show_summary: true,
  summary_seconds: 0,
  // Confetti and a glow for a 180, a ton, nine marks, a game shot and the match.
  celebrations: true,
  // A tap on a dart of the visit corrects it; the keypad enters darts by hand
  // while Practice manual entry is on, and on a dartboard without Autodarts.
  corrections: true,
  keypad: false,
  // The overlay of a stream: the scoreboard alone over the video, for a browser source of OBS.
  overlay: "off",
  overlay_layout: "lower_third",
  overlay_color: "#00FF00",
};

// Entities a card reads, by domain and translation key of the integration.
const BOARD_KEYS = {
  status: "sensor.local_status",
  numThrows: "sensor.num_throws",
  connected: "binary_sensor.local_connected",
  realtime: "binary_sensor.realtime_connected",
  cameras: "binary_sensor.cameras_active",
  calibrating: "binary_sensor.calibrating",
  cameraProblem: "binary_sensor.camera_problem",
  hand: "binary_sensor.hand_detected",
  takeoutPartial: "binary_sensor.takeout_partial",
  detection: "switch.detection",
  start: "button.start",
  stop: "button.stop",
  reset: "button.reset",
  calibrate: "button.calibrate",
};

const KEYS = {
  ...BOARD_KEYS,
  visit: "sensor.local_visit_score",
  lastThrow: "sensor.last_throw",
  darts: "sensor.training_darts",
  points: "sensor.training_points",
  average: "sensor.training_average",
  triples: "sensor.training_triples",
  bulls: "sensor.training_bulls",
  max: "sensor.training_scores_180",
  started: "sensor.training_started",
  practice: "sensor.practice_remaining",
  drill: "sensor.practice_target",
  manualEntry: "switch.practice_manual_entry",
};

const TRAINING_KEYS = {
  darts: "sensor.training_darts",
  points: "sensor.training_points",
  average: "sensor.training_average",
  visits: "sensor.training_visits",
  highest: "sensor.training_highest_visit",
  scores_100: "sensor.training_scores_100",
  scores_140: "sensor.training_scores_140",
  max: "sensor.training_scores_180",
  triples: "sensor.training_triples",
  doubles: "sensor.training_doubles",
  bulls: "sensor.training_bulls",
  misses: "sensor.training_misses",
  started: "sensor.training_started",
  events: "event.board_events",
  visit: "sensor.local_visit_score",
  newSession: "button.reset_training",
  session: "switch.training_session",
  lastSession: "sensor.training_last_session",
  streak: "sensor.training_streak",
  today: "sensor.darts_today",
  bests: "sensor.personal_best",
  profiles: "sensor.player_profiles",
};

const STATUS_KEYS = {
  ...BOARD_KEYS,
  restart: "button.restart",
  cloudLink: "binary_sensor.cloud_link",
  upstream: "switch.upstream",
  cpu: "sensor.cpu_usage",
  memory: "sensor.memory_usage",
  fps: "sensor.detection_fps",
  corrected: "sensor.correction_rate",
  update: "update.board_software",
  hostOs: "sensor.host_os",
  processor: "sensor.host_processor",
  vision: "sensor.vision_version",
};

const DOUBLES_KEYS = {
  doubles: "sensor.favourite_double",
  profiles: "sensor.player_profiles",
};

const PLAYERS_KEYS = {
  profiles: "sensor.player_profiles",
  lastMatch: "sensor.last_match",
  achievements: "sensor.achievements",
};

const LEADERBOARD_KEYS = {
  profiles: "sensor.player_profiles",
  achievements: "sensor.achievements",
};

const SCOREBOARD_KEYS = {
  ...BOARD_KEYS,
  visit: "sensor.local_visit_score",
  practice: "sensor.practice_remaining",
  drill: "sensor.practice_target",
  darts: "sensor.training_darts",
  average: "sensor.training_average",
  highest: "sensor.training_highest_visit",
  max: "sensor.training_scores_180",
  streak: "sensor.training_streak",
  today: "sensor.darts_today",
  // The new game screen reads the game, the format and the rules as they are set.
  game: "select.practice_game",
  players: "number.practice_players",
  legs: "number.practice_legs",
  sets: "number.practice_sets",
  inMode: "select.practice_in_mode",
  outMode: "select.practice_out_mode",
  bullMode: "select.practice_bull_mode",
  maxRounds: "number.practice_max_rounds",
  doubleOut: "switch.practice_double_out",
  doubleIn: "switch.practice_double_in",
  bullOff: "switch.practice_bull_off",
  bullOffDistance: "switch.practice_bull_off_distance",
  teams: "switch.practice_teams",
  threeInABed: "switch.practice_three_in_a_bed",
  // The bot for the new game screen, and whether darts can be entered by hand.
  botLevel: "number.practice_bot_level",
  manualEntry: "switch.practice_manual_entry",
  // Profiles with their pictures, records and the last match for the idle panels.
  profiles: "sensor.player_profiles",
  lastMatch: "sensor.last_match",
  bests: "sensor.personal_best",
  // The tournament, its settings for the new game screen and its buttons.
  tournament: "sensor.tournament",
  tournamentGame: "select.tournament_game",
  tournamentFormat: "select.tournament_format",
  tournamentThird: "switch.tournament_third_place",
  tournamentDraw: "switch.tournament_random_draw",
  tournamentGroups: "number.tournament_groups",
  tournamentAdvance: "number.tournament_advance",
  tournamentNext: "button.tournament_next_match",
  tournamentStop: "button.tournament_stop",
};

// Per-camera entities carry their camera number as an attribute.
const CAMERA_KEYS = {
  problem: "binary_sensor.individual_camera_problem",
  fps: "sensor.camera_fps",
  calibrate: "button.calibrate_camera",
  image: "camera.board_camera",
};

// The card speaks Home Assistant's language, also in a regional variant such as "es-419"
// or "de-CH"; a language without card texts reads English.
const LANGUAGES = Object.keys(TEXT);
function language(hass) {
  const own = String(hass?.locale?.language || hass?.language || "en").toLowerCase();
  return LANGUAGES.find((lang) => own === lang || own.startsWith(`${lang}-`)) ?? "en";
}

// Every language has every key; an unknown key reads as itself.
const translate = (hass, key) => TEXT[language(hass)][key] ?? key;

// "{name} requires {remaining}" with its values.
const fill = (text, values) => text.replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? ""));

// The caller speaks the card's language, in Home Assistant's regional variant where it has one.
function voiceLanguage(hass) {
  const lang = language(hass);
  const own = String(hass?.locale?.language || hass?.language || "");
  return own.toLowerCase().startsWith(lang) ? own : lang;
}

// Home Assistant asks for card forms without hass. The last hass a card saw, or
// the page language that Home Assistant sets, stands in for it.
let pageHass = null;
const pageLanguage = () =>
  language(pageHass ?? { language: globalThis.document?.documentElement?.lang || "en" });
const pageText = (key) => TEXT[pageLanguage()][key] ?? key;

const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => `&#${char.charCodeAt(0)};`);

// Card options reach the style only as real colours, never as url() or broken values.
// Colour names of Home Assistant's picker, such as "primary" or "red", follow the theme.
// A theme variable counts only without a fallback: the browser accepts anything there,
// images too. Escapes could hide a url().
function cssColor(value, fallback) {
  if (typeof value !== "string") return fallback;
  if (THEME_COLORS.has(value)) return `var(--${value}-color)`;
  if (/^var\(--[\w-]+\)$/.test(value)) return value;
  if (/\\|url|image|src\(|var\(/i.test(value)) return fallback;
  return globalThis.CSS?.supports?.("color", value) ? value : fallback;
}

// Stream overlay --------------------------------------------------------------

// What the overlay of a stream lies on: a key colour that a chroma key filter takes out,
// or nothing at all, for a browser source that shows what is see-through.
const OVERLAY_MODES = ["chroma", "transparent"];
// A band along the bottom of the picture, a box in its top-left corner, or all of it.
const OVERLAY_LAYOUTS = ["lower_third", "corner", "full"];

// The overlay the settings of a scoreboard ask for, or null for the card as it is.
// Unknown values fall back to the defaults, as the code editor may write anything.
function overlayOf(config) {
  if (!OVERLAY_MODES.includes(config?.overlay)) return null;
  const layout = OVERLAY_LAYOUTS.includes(config.overlay_layout)
    ? config.overlay_layout
    : SCOREBOARD_DEFAULTS.overlay_layout;
  const key =
    config.overlay === "chroma" ? cssColor(config.overlay_color, SCOREBOARD_DEFAULTS.overlay_color) : "transparent";
  return { mode: config.overlay, layout, key };
}

// Nobody taps a stream: the overlay has no new game screen, idle mode, caller, keypad,
// corrections, status or full-screen button, and only the whole picture has room for
// the summary of a match.
function overlayConfig(config) {
  const overlay = overlayOf(config);
  if (!overlay) return config;
  return {
    ...config,
    full_height: false,
    show_status: false,
    fullscreen_button: false,
    keep_awake: false,
    caller: false,
    lobby: false,
    idle: false,
    corrections: false,
    keypad: false,
    ...(overlay.layout === "full" ? {} : { show_summary: false }),
  };
}

// The overlays that hold the page: while one is there, the page shows nothing else, and
// what is around the overlay is see-through.
const overlayHolders = new Set();
const OVERLAY_PAGE_ID = "homedarts-overlay";
const OVERLAY_PAGE_CSS = `
  html, body { background: transparent !important; overflow: hidden !important; }
  body > * { visibility: hidden !important; }
`;

function holdPage(card, hold) {
  if (hold) overlayHolders.add(card);
  else overlayHolders.delete(card);
  const style = document.getElementById(OVERLAY_PAGE_ID);
  if (overlayHolders.size && !style) {
    const sheet = document.createElement("style");
    sheet.id = OVERLAY_PAGE_ID;
    sheet.textContent = OVERLAY_PAGE_CSS;
    document.head.append(sheet);
  } else if (!overlayHolders.size) {
    style?.remove();
  }
}

// Leaving the overlay, which covers the dashboard's own controls: back to the page before
// it, or, opened on its own as in OBS, to the dashboard's first view.
function leaveOverlay() {
  if (window.history.length > 1) {
    window.history.back();
    return;
  }
  const dashboard = window.location.pathname.split("/").slice(0, 2).join("/");
  window.history.pushState(null, "", dashboard);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
}

// Full screen where the browser offers it to the page: not on an iPhone, which shows only
// videos on the whole screen, and not on the TV of Home Assistant Cast, which shows the
// dashboard on the whole screen anyway, and where nobody taps.
const fullscreenOffered = () => document.fullscreenEnabled === true && !window.customElements.get("hc-main");

// The controls of the scoreboard, whose taps never count as a double tap that leaves
// full screen: the keypad, the darts of the visit, the new game screen and its fields.
const FULLSCREEN_CONTROLS = "button, a, input, select, textarea, label, [role=button], .tappable, .pad-area, .loupe";
// Two taps at most this far apart, in milliseconds, are a double tap.
const DOUBLE_TAP = 400;
// How long the hint stays that the browser can't keep the screen on, in milliseconds.
const AWAKE_HINT = 15000;

const usable = (state) => state && !["unknown", "unavailable"].includes(state.state);
const finite = (value) => (Number.isFinite(value) ? value : null);
const named = (value) => (typeof value === "string" && value ? value : null);

// Darts of a visit sensor that name a bed.
const visitThrows = (state) =>
  (Array.isArray(state?.attributes?.throws) ? state.attributes.throws : []).filter(
    (dart) => dart && Number.isInteger(dart.number) && Number.isInteger(dart.multiplier)
  );

// The integration's name of the bed a dart hit: S20, D16, T19, 25, BULL or MISS.
function dartKey(dart) {
  if (dart.number === 0 || dart.multiplier === 0) return "MISS";
  if (dart.number === 25) return dart.multiplier >= 2 ? "BULL" : "25";
  return `${"SDT"[dart.multiplier - 1] ?? "S"}${dart.number}`;
}

// Points of a bed by its name.
function keyScore(key) {
  if (key === "BULL") return 50;
  if (key === "25") return 25;
  const match = /^([SDT])(\d{1,2})$/.exec(key);
  return match ? { S: 1, D: 2, T: 3 }[match[1]] * Number(match[2]) : 0;
}

// Formatting ----------------------------------------------------------------

// Intl formatters are expensive to build, so every locale and option set keeps one.
const formatters = new Map();
function formatter(kind, locale, options) {
  const key = JSON.stringify([kind, locale, options]);
  let cached = formatters.get(key);
  if (!cached) {
    cached = kind === "date" ? new Intl.DateTimeFormat(locale, options) : new Intl.NumberFormat(locale, options);
    formatters.set(key, cached);
  }
  return cached;
}

// Number formats of the user profile, as Home Assistant maps them to locales.
const NUMBER_LOCALES = {
  comma_decimal: ["en-US", "en"],
  decimal_comma: ["de", "es", "it"],
  space_comma: ["fr", "sv", "cs"],
  quote_decimal: ["de-CH"],
  system: undefined,
};

function formatNumber(hass, value, digits = 0) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "–";
  const locale = hass?.locale || {};
  const options = { minimumFractionDigits: digits, maximumFractionDigits: digits };
  if (locale.number_format === "none") {
    return formatter("number", "en-US", { ...options, useGrouping: false }).format(value);
  }
  const target = Object.hasOwn(NUMBER_LOCALES, locale.number_format)
    ? NUMBER_LOCALES[locale.number_format]
    : locale.language || hass?.language;
  return formatter("number", target, options).format(value);
}

// "45 %" in German, "45%" in English, as Home Assistant writes percentages.
const PERCENT_SPACE = ["cs", "de", "fi", "fr", "sk", "sv"];
function formatPercent(hass, value, digits = 0) {
  const number = formatNumber(hass, value, digits);
  if (number === "–") return number;
  return `${number}${PERCENT_SPACE.includes(hass?.locale?.language ?? hass?.language) ? " " : ""}%`;
}

// The 12- or 24-hour clock of the user profile; by default, that of the language.
const clocks = new Map();
function amPm(locale, language) {
  const format = locale.time_format ?? "language";
  const key = `${format}|${language}`;
  if (!clocks.has(key)) {
    let twelve = format === "12";
    if (format === "language" || format === "system") {
      // Only "system" follows the browser; never fall back to it for the language.
      const lang = format === "language" ? language || "en" : undefined;
      twelve = new Date("January 1, 2023 22:00:00").toLocaleString(lang).includes("10");
    }
    clocks.set(key, twelve);
  }
  return clocks.get(key);
}

// The order of day and month of the user profile's date format; YMD has no year here.
const DATE_ORDERS = { DMY: ["day", "month"], MDY: ["month", "day"], YMD: ["month", "day"] };

// Day, month and time like "26.09., 14:05", in the server's or the browser's time zone,
// with the date in the order of the user profile, as Home Assistant writes numeric dates.
function formatDateTime(hass, time) {
  const moment = new Date(time);
  if (Number.isNaN(moment.getTime())) return "";
  const locale = hass?.locale || {};
  const language = locale.language || hass?.language;
  const twelve = amPm(locale, language);
  const server = hass?.config?.time_zone;
  const format = formatter("date", locale.date_format === "system" ? undefined : language, {
    day: "2-digit",
    month: "2-digit",
    hour: twelve ? "numeric" : "2-digit",
    minute: "2-digit",
    hourCycle: twelve ? "h12" : "h23",
    ...(server && locale.time_zone !== "local" ? { timeZone: server } : {}),
  });
  if (!Object.hasOwn(DATE_ORDERS, locale.date_format)) return format.format(moment);
  const order = DATE_ORDERS[locale.date_format];
  // The language's separators stay; day and month take the places of the profile's order.
  const parts = format.formatToParts(moment);
  const value = (type) => parts.find((part) => part.type === type).value;
  let next = 0;
  return parts.map((part) => (["day", "month"].includes(part.type) ? value(order[next++]) : part.value)).join("");
}

// Entity lookup ------------------------------------------------------------

// hass.entities is replaced whenever the registry changes, so it keys a cache
// that spares every card from scanning all entities on each state update.
const deviceCache = new WeakMap();
const indexCache = new WeakMap();

function homedartsDevices(hass) {
  const entities = hass?.entities || {};
  let devices = deviceCache.get(entities);
  if (!devices) {
    const found = new Set();
    for (const entity of Object.values(entities)) {
      if (entity.platform === "homedarts" && entity.device_id) found.add(entity.device_id);
    }
    devices = [...found];
    deviceCache.set(entities, devices);
  }
  return devices;
}

// A device the card or dashboard names must still exist; without a device registry, it may.
const knownDevice = (hass, deviceId) => !hass?.devices || Boolean(hass.devices[deviceId]);

function entityIndex(hass, deviceId) {
  const entities = hass?.entities || {};
  let byDevice = indexCache.get(entities);
  if (!byDevice) {
    byDevice = new Map();
    indexCache.set(entities, byDevice);
  }
  let index = byDevice.get(deviceId);
  if (!index) {
    index = {};
    for (const entity of Object.values(entities)) {
      if (entity.platform !== "homedarts" || entity.device_id !== deviceId) continue;
      if (!entity.translation_key) continue;
      const key = `${entity.entity_id.split(".")[0]}.${entity.translation_key}`;
      (index[key] ||= []).push(entity.entity_id);
    }
    byDevice.set(deviceId, index);
  }
  return index;
}

function resolveKeys(index, keys) {
  return Object.fromEntries(Object.entries(keys).map(([name, key]) => [name, index[key]?.[0]]));
}

function cameraEntities(hass, index) {
  const cameras = new Map();
  for (const [role, key] of Object.entries(CAMERA_KEYS)) {
    for (const id of index[key] || []) {
      const number = Number(hass.states[id]?.attributes?.camera);
      if (!Number.isInteger(number) || number < 1) continue;
      if (!cameras.has(number)) cameras.set(number, { number });
      cameras.get(number)[role] ??= id;
    }
  }
  return [...cameras.values()].sort((a, b) => a.number - b.number);
}

// Geometry ----------------------------------------------------------------

function point(radius, degrees) {
  const angle = (degrees * Math.PI) / 180;
  return [radius * Math.sin(angle), -radius * Math.cos(angle)];
}

const fmt = (value) => Number(value.toFixed(2));

function sectorPath(inner, outer, start, end) {
  const [x1, y1] = point(outer, start);
  const [x2, y2] = point(outer, end);
  const [x3, y3] = point(inner, end);
  const [x4, y4] = point(inner, start);
  return (
    `M${fmt(x1)} ${fmt(y1)}A${outer} ${outer} 0 0 1 ${fmt(x2)} ${fmt(y2)}` +
    `L${fmt(x3)} ${fmt(y3)}A${inner} ${inner} 0 0 0 ${fmt(x4)} ${fmt(y4)}Z`
  );
}

function ringPath(inner, outer) {
  const circle = (r) => `M${r} 0A${r} ${r} 0 1 0 ${-r} 0A${r} ${r} 0 1 0 ${r} 0Z`;
  return inner > 0 ? circle(outer) + circle(inner) : circle(outer);
}

function bedPath(id) {
  if (id === "Bull") return ringPath(0, R.bull);
  if (id === "25") return ringPath(R.bull, R.outerBull);
  if (id === "Miss") return ringPath(R.doubleOut, R.board);
  const match = /^(SI|SO|T|D|M)(\d+)$/.exec(id);
  const index = match ? NUMBERS.indexOf(Number(match[2])) : -1;
  if (index < 0) return null;
  const [inner, outer] = BEDS[match[1]];
  return sectorPath(inner, outer, index * 18 - 9, index * 18 + 9);
}

function sectorAt(dart) {
  if (!Number.isFinite(dart.x) || !Number.isFinite(dart.y)) return null;
  const degrees = (Math.atan2(dart.x, dart.y) * 180) / Math.PI;
  return NUMBERS[((Math.round(degrees / 18) % 20) + 20) % 20];
}

function beds(dart) {
  const { number, multiplier, bed } = dart;
  if (number === 25) return [multiplier >= 2 ? "Bull" : "25"];
  if (multiplier === 0 || bed === "Outside") {
    const sector = NUMBERS.includes(number) ? number : sectorAt(dart);
    return [sector ? `M${sector}` : "Miss"];
  }
  if (!NUMBERS.includes(number)) return [];
  if (bed === "Triple" || multiplier === 3) return [`T${number}`];
  if (bed === "Double" || multiplier === 2) return [`D${number}`];
  if (bed === "SingleInner") return [`SI${number}`];
  if (bed === "SingleOuter") return [`SO${number}`];
  if (Number.isFinite(dart.x) && Number.isFinite(dart.y)) {
    return [Math.hypot(dart.x, dart.y) * NORM < R.trebleIn ? `SI${number}` : `SO${number}`];
  }
  return [`SI${number}`, `SO${number}`];
}

function kind(dart) {
  if (dart.number === 25) return dart.multiplier >= 2 ? "bull" : "outer-bull";
  if (dart.multiplier === 0 || dart.bed === "Outside") return "miss";
  return { 3: "triple", 2: "double" }[dart.multiplier] || "single";
}

function label(hass, dart) {
  // A dart of a visit entered as its score has no bed of its own, only its points.
  if (dart.total) return String(dart.number * dart.multiplier);
  if (dart.number === 25) return dart.multiplier >= 2 ? "Bull" : "25";
  if (kind(dart) === "miss") return translate(hass, "miss");
  return `${{ 3: "T", 2: "D" }[dart.multiplier] || "S"}${dart.number}`;
}

function parseSegment(name) {
  // Fallback for integrations without dart details: the last segment name only.
  const text = String(name || "").trim();
  if (/^(bull|db|d25)$/i.test(text)) return { number: 25, multiplier: 2 };
  if (text === "25" || /^s25$/i.test(text)) return { number: 25, multiplier: 1 };
  const match = /^([SDTM])(\d{1,2})$/i.exec(text);
  if (!match) return null;
  const multiplier = { S: 1, D: 2, T: 3, M: 0 }[match[1].toUpperCase()];
  return { number: Number(match[2]), multiplier };
}

function boardSvg(style) {
  const colors = STYLES[style] || STYLES.classic;
  const wire = colors.wire === "none" ? "" : ` stroke="${colors.wire}" stroke-width="0.7"`;
  const parts = [`<circle r="${R.board}" fill="${colors.surround}"/>`];
  NUMBERS.forEach((number, index) => {
    const even = index % 2 === 0;
    const single = even ? colors.black : colors.white;
    const ring = even ? colors.red : colors.green;
    const start = index * 18 - 9;
    for (const [bed, fill] of [["SI", single], ["T", ring], ["SO", single], ["D", ring]]) {
      const [inner, outer] = BEDS[bed];
      parts.push(`<path d="${sectorPath(inner, outer, start, start + 18)}" fill="${fill}"${wire}/>`);
    }
  });
  parts.push(`<circle r="${R.outerBull}" fill="${colors.green}"${wire}/>`);
  parts.push(`<circle r="${R.bull}" fill="${colors.red}"${wire}/>`);
  if (colors.wire !== "none") {
    parts.push(
      `<circle r="${R.doubleOut}" fill="none" stroke="${colors.wire}" stroke-width="1.2"/>`
    );
  }
  return parts.join("");
}

function numbersSvg(style) {
  // Drawn above highlights, so a hit outside the double ring keeps its number readable.
  const color = (STYLES[style] || STYLES.classic).numbers;
  return NUMBERS.map((number, index) => {
    const [x, y] = point(R.numbers, index * 18);
    return `<text x="${fmt(x)}" y="${fmt(y)}" fill="${color}" class="number">${number}</text>`;
  }).join("");
}

// Training analytics ------------------------------------------------------

// Hits are counted per bed as S20, D16, T19, 25, BULL or MISS by the integration.
function hitBeds(key) {
  const text = String(key);
  if (text === "BULL") return ["Bull"];
  if (text === "25") return ["25"];
  const match = /^([SDT])(\d{1,2})$/.exec(text);
  if (!match || !NUMBERS.includes(Number(match[2]))) return [];
  const number = match[2];
  return { S: [`SI${number}`, `SO${number}`], D: [`D${number}`], T: [`T${number}`] }[match[1]];
}

function validHits(hits) {
  return Object.entries(hits && typeof hits === "object" ? hits : {})
    .map(([key, count]) => [key, Number(count)])
    .filter(([key, count]) => Number.isInteger(count) && count > 0 && (key === "MISS" || hitBeds(key).length));
}

function heatLevels(hits, mode = "beds") {
  const levels = new Map();
  const add = (bed, count) => levels.set(bed, (levels.get(bed) || 0) + count);
  for (const [key, count] of validHits(hits)) {
    const beds = hitBeds(key);
    if (mode !== "numbers") {
      beds.forEach((bed) => add(bed, count));
      continue;
    }
    // Numbers mode sums singles, doubles and triples of a sector.
    const number = /^[SDT](\d{1,2})$/.exec(key)?.[1];
    const group = number ? ["SI", "T", "SO", "D"].map((bed) => `${bed}${number}`) : beds.length ? ["Bull", "25"] : [];
    group.forEach((bed) => add(bed, count));
  }
  return levels;
}

function heatRatio(count, max) {
  return max > 1 ? Math.min(1, Math.max(0, (count - 1) / (max - 1))) : 1;
}

function heatColor(ratio) {
  // Thermal scale from blue (rarely hit) through green and yellow to red (most hit).
  const value = Math.min(1, Math.max(0, Number(ratio) || 0));
  return `hsl(${Math.round(220 * (1 - value))}, 90%, 55%)`;
}

function topHits(hits, limit = 5) {
  return validHits(hits)
    .filter(([key]) => key !== "MISS")
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit);
}

function hitLabel(hass, key) {
  if (key === "BULL") return "Bull";
  if (key === "MISS") return translate(hass, "miss");
  return key;
}

function visitBucket(score) {
  if (score >= 180) return "max";
  if (score >= 140) return "high";
  if (score >= 100) return "ton";
  if (score >= 60) return "good";
  return "low";
}

// "Intel(R) Core(TM) i3-9100T CPU @ 3.10GHz" reads as "Intel Core i3-9100T".
function shortProcessor(name) {
  if (typeof name !== "string") return "";
  return name
    .replace(/\((R|TM)\)/gi, "")
    .replace(/\s+CPU\b.*$|\s*@.*$/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

// Completed visits of the visit sensor, newest first; malformed entries are skipped.
function recentVisits(visits, limit = 5) {
  if (!Array.isArray(visits)) return [];
  return visits
    .filter((visit) => visit && Number.isFinite(visit.score) && visit.score >= 0 && Array.isArray(visit.segments))
    .slice(0, limit)
    .map((visit) => ({
      score: Math.round(visit.score),
      segments: visit.segments.filter((segment) => typeof segment === "string"),
    }));
}

// Finished sessions of the last-session sensor, newest first.
function pastSessions(sessions, limit = 5) {
  if (!Array.isArray(sessions)) return [];
  return sessions
    .filter((session) => session && Number.isFinite(Date.parse(session.ended)) && session.darts > 0)
    .slice(0, limit)
    .map((session) => ({
      ended: Date.parse(session.ended),
      minutes: finite(session.duration_minutes),
      darts: finite(session.darts),
      average: finite(session.average),
      best: finite(session.highest_visit),
    }));
}

// Board events that change the visits of the training card, and the most visits it shows.
const VISIT_EVENTS = ["visit_completed", "visit_undone", "session_started"];
const HISTORY_LIMIT = 60;
// The slots a narrow chart of the last visits shows.
const HISTORY_NARROW = 10;

// The visits of the session after rows of the board events entity, as the recorder
// or the history stream deliver them, on top of the visits known so far: a session
// start empties the list, a completed visit joins it, and an undone visit leaves it
// again (its darts come back as a new visit). The bot's visits count for nobody.
function visitsFromHistory(rows, since = 0, known = []) {
  let visits = [...known];
  for (const row of Array.isArray(rows) ? rows : []) {
    const attributes = row?.a || row?.attributes;
    const type = attributes?.event_type;
    const time = Date.parse(row?.s ?? row?.state);
    // The start sensor has whole seconds, so a visit of the previous session
    // can fall into the same second; the start event itself is precise.
    if (!Number.isFinite(time) || time < since) continue;
    if (type === "session_started") {
      visits = [];
      continue;
    }
    if (type === "visit_undone") {
      visits = visits.slice(0, -1);
      continue;
    }
    if (type !== "visit_completed" || attributes.bot === true) continue;
    const score = Number(attributes.score);
    if (!Number.isFinite(score)) continue;
    visits.push({
      time,
      score,
      darts: Number(attributes.darts) || 0,
      segments: Array.isArray(attributes.segments) ? attributes.segments.map(String) : [],
    });
  }
  return visits;
}

// Personal bests -------------------------------------------------------------

// Records of the personal-best sensor in reading order, and how each value reads.
const RECORD_ORDER = [
  ["highest_visit", "highest", "count"],
  ["highest_checkout", "highest_checkout", "count"],
  ["fewest_darts", "best_leg", "darts"],
  ["best_cricket_mpr", "best_cricket_mpr", "mpr"],
  ["best_session_average", "best_session_average", "average"],
  ["around_the_clock", "drill_around_the_clock", "darts"],
  ["doubles", "drill_doubles", "darts"],
  ["bobs_27", "drill_bobs_27", "points"],
  ["checkout_121", "drill_checkout_121", "count"],
  ["catch_40", "drill_catch_40", "points"],
  ["jdc_challenge", "drill_jdc_challenge", "points"],
  ["singles", "drill_singles", "points"],
];

// Every personal best that has a value, and the longest training streak.
function bestsView(bests, streak) {
  const attributes = bests?.attributes || {};
  const value = (key) => (finite(attributes[key]) !== null && attributes[key] > 0 ? attributes[key] : null);
  const records = [];
  for (const [key, name, kind] of RECORD_ORDER) {
    if (key !== "fewest_darts") {
      if (value(key) !== null) records.push({ record: key, name, kind, value: value(key) });
      continue;
    }
    // One fewest-darts record per start score, the shortest game first.
    Object.keys(attributes)
      .map((item) => /^fewest_darts_(\d+)$/.exec(item))
      .filter((match) => match && value(match[0]) !== null)
      .map((match) => ({ record: match[0], name, kind, value: value(match[0]), game: Number(match[1]) }))
      .sort((a, b) => a.game - b.game)
      .forEach((record) => records.push(record));
  }
  const longest = finite(streak?.attributes?.best_streak);
  if (longest > 0) records.push({ record: "best_streak", name: "best_streak", kind: "days", value: longest });
  return records;
}

function bestsHtml(records, ui) {
  const { t, format } = ui;
  const shown = (record) => {
    if (record.kind === "mpr") return format(record.value, 2);
    if (record.kind === "average") return format(record.value, 1);
    if (record.kind === "count") return format(record.value, 0);
    const key = { darts: "unit_darts", points: "unit_points" }[record.kind] ?? (record.value === 1 ? "unit_day" : "unit_days");
    return fill(t(key), { value: format(record.value, 0) });
  };
  return records
    .map(
      (record) =>
        `<div><dt>${escapeHtml(fill(t(record.name), { game: record.game }))}</dt>` +
        `<dd data-record="${escapeHtml(record.record)}">${escapeHtml(shown(record))}</dd></div>`
    )
    .join("");
}

// Games ----------------------------------------------------------------------

// The darts a game counted in the current visit, by bed name.
const gameVisit = (attributes) =>
  (Array.isArray(attributes.visit) ? attributes.visit : []).filter((key) => typeof key === "string");

// The two teams of a team match: the team number and its players.
function teamsView(teams) {
  return (Array.isArray(teams) ? teams : [])
    .filter((team) => team && Number.isInteger(team.team) && Array.isArray(team.players))
    .map((team) => ({ team: team.team, players: team.players.filter(Number.isInteger) }));
}

const teamOf = (score) => (Number.isInteger(score.team) ? score.team : null);

// The bot's seat among the scores: marked, the others as they were.
const botOf = (score) => (score.bot === true ? { bot: true } : {});

// Where to aim when no checkout exists: the setup darts and the score they leave.
function setupView(setup) {
  if (!setup || typeof setup.route !== "string" || !Number.isInteger(setup.leave)) return null;
  const route = setup.route.split(/\s+/).filter((bed) => hitBeds(bed).length);
  return route.length ? { route, leave: setup.leave } : null;
}

// The In and Out modes of X01: any dart, a double, or a double or a treble.
const X01_MODES = ["straight", "double", "master"];
const BULL_MODES = ["25_50", "50_50"];

// The leg the round limit decided last, from the newest leg of the history.
function roundLimitLeg(legs) {
  const leg = Array.isArray(legs) ? legs[0] : null;
  return Number.isInteger(leg?.rounds) ? { ended: String(leg.ended), name: named(leg.name) } : null;
}

// The X01 rules of a board, as the selects or the sensor give them, or the switches of
// double in and double out where no mode is known.
const inModeOf = (board) =>
  X01_MODES.includes(board.in_mode) ? board.in_mode : board.double_in === true ? "double" : "straight";
const outModeOf = (board) =>
  X01_MODES.includes(board.out_mode) ? board.out_mode : board.double_out === false ? "straight" : "double";

// The practice leg of the remaining-score sensor, or null without a game.
function practiceView(state) {
  if (!usable(state)) return null;
  const remaining = Number(state.state);
  if (!Number.isInteger(remaining) || remaining < 0) return null;
  const attributes = state.attributes || {};
  const route = typeof attributes.checkout === "string" ? attributes.checkout.split(/\s+/) : [];
  const scores = (Array.isArray(attributes.scores) ? attributes.scores : [])
    .filter((score) => score && Number.isInteger(score.player) && Number.isInteger(score.remaining))
    .map((score) => ({
      player: score.player,
      name: named(score.name),
      remaining: score.remaining,
      start: finite(score.start),
      team: teamOf(score),
      ...botOf(score),
      legs: finite(score.legs) ?? 0,
      sets: finite(score.sets) ?? 0,
      average: finite(score.average),
    }));
  return {
    game: finite(attributes.game),
    remaining,
    // What the player had before the visit: for its score entered on the keypad, where
    // the remaining score stands in for it, and for the caller, which counts the visit
    // from it where the integration says it.
    from: finite(attributes.visit_from) ?? remaining,
    visitFrom: finite(attributes.visit_from),
    teams: teamsView(attributes.teams),
    route: route.filter((bed) => hitBeds(bed).length),
    ...(setupView(attributes.setup) ? { setup: setupView(attributes.setup) } : {}),
    ...(finite(attributes.bot?.level) ? { botLevel: attributes.bot.level } : {}),
    bust: attributes.bust === true,
    won: attributes.won === true,
    darts: finite(attributes.darts) ?? 0,
    average: finite(attributes.average),
    player: finite(attributes.player) ?? 1,
    name: named(attributes.name),
    winner: finite(attributes.winner),
    legsToWin: finite(attributes.legs_to_win) ?? 1,
    setsToWin: finite(attributes.sets_to_win) ?? 1,
    // Without double or master in, every player is in from the first dart.
    opened: attributes.opened !== false,
    inMode: inModeOf(attributes),
    outMode: outModeOf(attributes),
    bullMode: attributes.bull_mode === "50_50" ? "50_50" : "25_50",
    maxRounds: finite(attributes.max_rounds) ?? 0,
    round: finite(attributes.round),
    limit: roundLimitLeg(attributes.legs),
    visit: gameVisit(attributes),
    scores,
  };
}

// The highest score that ends a leg: two trebles 20 and the bull with double out, or
// three trebles 20.
const highestCheckout = (practice) => (practice.outMode === "double" ? 170 : 180);

const DRILLS = [
  "around_the_clock",
  "doubles",
  "checkout",
  "bobs_27",
  "checkout_121",
  "catch_40",
  "jdc_challenge",
  "singles",
];
// Training games that check out a score, with a route to show.
const CHECKOUT_DRILLS = ["checkout", "checkout_121", "catch_40"];

// The training game of the target sensor; a finished game has no target.
function drillView(state) {
  const attributes = state?.attributes || {};
  if (!state || state.state === "unavailable" || !DRILLS.includes(attributes.drill)) return null;
  const route = typeof attributes.checkout === "string" ? attributes.checkout.split(/\s+/) : [];
  return {
    kind: attributes.drill,
    target: usable(state) ? String(state.state) : null,
    finished: attributes.finished === true,
    progress: finite(attributes.progress) ?? 0,
    targets: finite(attributes.targets) ?? 21,
    darts: finite(attributes.darts) ?? 0,
    hitRate: finite(attributes.hit_rate),
    score: finite(attributes.score),
    remaining: finite(attributes.remaining),
    route: route.filter((bed) => hitBeds(bed).length),
    bust: attributes.bust === true,
    won: attributes.won === true,
    // Where the darts left cannot finish, the darts that leave a finish for the next visit.
    setup: setupView(attributes.setup),
    visit: finite(attributes.attempt_visit),
    visits: finite(attributes.attempt_visits),
    attempts: finite(attributes.attempts) ?? 0,
    successes: finite(attributes.successes) ?? 0,
    rate: finite(attributes.rate),
    part: finite(attributes.part),
    best: finite(attributes.best),
    thrown: gameVisit(attributes),
    completed: Array.isArray(attributes.results) ? attributes.results[0]?.completed === true : false,
  };
}

// Beds to aim at in a training game: the route of a checkout, every bed of a
// number and the whole bull for 25, or the double of the doubles.
function drillBeds(drill) {
  if (!drill || drill.finished) return [];
  if (CHECKOUT_DRILLS.includes(drill.kind)) return hitBeds(drill.route[0] ?? drill.setup?.route[0] ?? "");
  const target = drill.target ?? "";
  return /^\d+$/.test(target) ? targetBeds(target) : hitBeds(target);
}

const CRICKET_NUMBERS = [20, 19, 18, 17, 16, 15, 25];
const CRICKET_GAMES = ["cricket", "cut_throat", "tactics", "wild_mouse", "random_cricket", "hidden_cricket"];
// What Wild Mouse closes besides the numbers, in the order of its rows.
const WILD_TARGETS = ["doubles", "triples", "bed"];
// No mark, one, two, and a closed number, as on a Cricket chalkboard.
const CRICKET_MARKS = ["", "/", "X", "Ⓧ"];

// The Cricket leg of the remaining-score sensor, which has no state then.
function cricketView(state) {
  const attributes = state?.attributes || {};
  if (!state || state.state === "unavailable" || !CRICKET_GAMES.includes(attributes.game)) return null;
  // Tactics adds the numbers 14 to 10, Wild Mouse doubles, triples and three in a bed;
  // Random and Hidden Cricket draw theirs, and Hidden Cricket has null for a number
  // that does not show yet.
  const hidden = attributes.game === "hidden_cricket";
  const number = (value) => Number.isInteger(value) || (hidden && value === null);
  const numbers =
    Array.isArray(attributes.numbers) && attributes.numbers.length && attributes.numbers.every(number)
      ? attributes.numbers
      : CRICKET_NUMBERS;
  const wild = attributes.game === "wild_mouse";
  const targets =
    wild && Array.isArray(attributes.targets) ? attributes.targets.filter((key) => WILD_TARGETS.includes(key)) : [];
  const slots = numbers.length + targets.length;
  const scores = (Array.isArray(attributes.scores) ? attributes.scores : [])
    .filter(
      (score) => score && Number.isInteger(score.player) && Array.isArray(score.marks) && score.marks.length === slots
    )
    .map((score) => ({
      player: score.player,
      name: named(score.name),
      marks: score.marks.map((mark) => (Number.isInteger(mark) ? Math.min(Math.max(mark, 0), 3) : 0)),
      points: finite(score.points) ?? 0,
      team: teamOf(score),
      ...botOf(score),
      legs: finite(score.legs) ?? 0,
      sets: finite(score.sets) ?? 0,
      mpr: finite(score.mpr),
    }));
  // Wild Mouse aims at any double or triple, too.
  const aim = (target) => hitBeds(target).length || (wild && ["D", "T"].includes(target));
  return {
    kind: attributes.game,
    numbers,
    targets,
    // The row to aim at, as a triple can also count for triples in Wild Mouse.
    targetRow: wild && typeof attributes.target_row === "string" ? attributes.target_row : null,
    // What every dart of the visit counted for, null for nothing.
    counted: Array.isArray(attributes.counted) ? attributes.counted : [],
    bed: wild && attributes.bed === true,
    teams: teamsView(attributes.teams),
    target: typeof attributes.target === "string" && aim(attributes.target) ? attributes.target : null,
    won: attributes.won === true,
    darts: finite(attributes.darts) ?? 0,
    points: finite(attributes.points) ?? 0,
    mpr: finite(attributes.mpr),
    player: finite(attributes.player) ?? 1,
    name: named(attributes.name),
    winner: finite(attributes.winner),
    legsToWin: finite(attributes.legs_to_win) ?? 1,
    setsToWin: finite(attributes.sets_to_win) ?? 1,
    visit: gameVisit(attributes),
    scores,
  };
}

// The darts on the board that counted nothing in a Cricket game: on a number nobody
// needs any more, or none of the game. The game's darts are the last ones of the visit.
function deadDarts(view, darts) {
  if (view?.mode !== "cricket") return darts.map(() => false);
  const { counted, visit } = view.cricket;
  const offset = darts.length - counted.length;
  const known = counted.length === visit.length;
  return darts.map((_, index) => known && index >= offset && counted[index - offset] === null);
}

// Beds to aim at in Cricket: the treble of the next open number, or the whole
// bull, whose beds both mark; in Wild Mouse also every double or triple.
function cricketBeds(cricket) {
  if (!cricket || cricket.won || cricket.winner !== null || !cricket.target) return [];
  return ["BULL", "D", "T"].includes(cricket.target)
    ? targetBeds(cricket.target === "BULL" ? "25" : cricket.target)
    : hitBeds(cricket.target);
}

const PARTY_GAMES = [
  "shanghai",
  "halve_it",
  "killer",
  "golf",
  "baseball",
  "count_up",
  "bermuda",
  "round_the_world",
  "gotcha",
];
// Round the World: the numbers 1 to 20, then the bull.
const WORLD_TARGETS = 21;
// Party games with a scorecard of every round.
const SCORECARD_GAMES = ["golf", "baseball"];
const BOARD_NUMBERS = Array.from({ length: 20 }, (_, index) => index + 1);

// A party game of the remaining-score sensor, which has no state then.
function partyView(state) {
  const attributes = state?.attributes || {};
  if (!state || state.state === "unavailable" || !PARTY_GAMES.includes(attributes.game)) return null;
  const scores = (Array.isArray(attributes.scores) ? attributes.scores : [])
    .filter((score) => score && Number.isInteger(score.player))
    .map((score) => ({
      player: score.player,
      name: named(score.name),
      points: finite(score.points) ?? 0,
      legs: finite(score.legs) ?? 0,
      sets: finite(score.sets) ?? 0,
      number: Number.isInteger(score.number) ? score.number : null,
      lives: Number.isInteger(score.lives) ? score.lives : null,
      killer: score.killer === true,
      scorecard: Array.isArray(score.scorecard) ? score.scorecard.filter(Number.isInteger) : [],
      // Round the World: the targets done; Gotcha: the points left to the target score.
      progress: Number.isInteger(score.progress) ? score.progress : null,
      left: Number.isInteger(score.left) ? score.left : null,
    }));
  return {
    kind: attributes.game,
    round: finite(attributes.round),
    rounds: finite(attributes.rounds),
    // The players of extra rounds after a tie.
    playoff: Array.isArray(attributes.playoff) ? attributes.playoff.filter(Number.isInteger) : null,
    target: typeof attributes.target === "string" && attributes.target ? attributes.target : null,
    phase: attributes.phase === "choose" ? "choose" : "play",
    needsPlayers: finite(attributes.needs_players),
    points: finite(attributes.points) ?? 0,
    // What the visit so far scored, and a Gotcha visit that went too far.
    scored: finite(attributes.scored),
    bust: attributes.bust === true,
    won: attributes.won === true,
    darts: finite(attributes.darts) ?? 0,
    player: finite(attributes.player) ?? 1,
    name: named(attributes.name),
    winner: finite(attributes.winner),
    legsToWin: finite(attributes.legs_to_win) ?? 1,
    setsToWin: finite(attributes.sets_to_win) ?? 1,
    visit: gameVisit(attributes),
    scores,
  };
}

// The bull-off before a match, while it runs: the bed and distance of every
// dart so far, and whether a tie throws again.
function bullOffView(state) {
  const bullOff = state?.attributes?.bull_off;
  if (!state || state.state === "unavailable" || !bullOff || typeof bullOff !== "object") return null;
  return {
    player: Number.isInteger(bullOff.player) ? bullOff.player : 1,
    name: named(bullOff.name),
    rethrow: bullOff.rethrow === true,
    byDistance: bullOff.by_distance === true,
    throws: (Array.isArray(bullOff.throws) ? bullOff.throws : [])
      .filter((item) => item && Number.isInteger(item.player))
      .map((item) => ({
        player: item.player,
        name: named(item.name),
        ...botOf(item),
        hit: named(item.hit),
        distance: finite(item.distance),
      })),
  };
}

// The bullseye beats the outer bull, which beats every other bed.
const BULL_RANKS = { BULL: 2, 25: 1 };

// The players whose dart no other beats so far, as the integration decides:
// the better bull bed first; outside the bull, or by distance if the players
// want, the closer dart. Darts the board did not measure stay tied.
function bullOffLeaders(bullOff) {
  const thrown = bullOff.throws.filter((item) => item.hit);
  const rank = (item) => BULL_RANKS[item.hit] ?? 0;
  const best = Math.max(0, ...thrown.map(rank));
  const leaders = thrown.filter((item) => rank(item) === best);
  const measured = leaders.every((item) => item.distance !== null);
  if (leaders.length < 2 || (best && !bullOff.byDistance) || !measured) return leaders.map((item) => item.player);
  const nearest = Math.min(...leaders.map((item) => item.distance));
  return leaders.filter((item) => item.distance === nearest).map((item) => item.player);
}

// Beds of a target: a number, any double (with the bull) or treble, the
// whole bull, which games name 25, or the bullseye alone, 50 in Bermuda.
function targetBeds(target) {
  if (!target) return [];
  if (target === "BULL" || target === "25") return [...hitBeds("BULL"), ...hitBeds("25")];
  if (target === "50") return hitBeds("BULL");
  if (target === "D") return [...BOARD_NUMBERS.flatMap((n) => hitBeds(`D${n}`)), ...hitBeds("BULL")];
  if (target === "T") return BOARD_NUMBERS.flatMap((n) => hitBeds(`T${n}`));
  return ["S", "T", "D"].flatMap((bed) => hitBeds(`${bed}${target}`));
}

// Beds to aim at in a party game: a number, any double or treble, the bull, or
// the doubles a killer hunts.
function partyBeds(party) {
  if (!party || party.won || party.winner !== null || party.needsPlayers) return [];
  if (party.kind === "killer") {
    if (party.phase === "choose") return [];
    if (party.target) return hitBeds(party.target);
    return party.scores
      .filter((score) => score.player !== party.player && score.lives > 0 && score.number)
      .flatMap((score) => hitBeds(`D${score.number}`));
  }
  return targetBeds(party.target);
}

// How a target reads: "Any double" for D, "Bull (25/50)" for the bull where
// both beds count, "Bullseye (50)" where only the bullseye does, "Bull" for the
// bullseye, D7 for D7.
function targetText(ui, target) {
  if (target === "D") return ui.t("any_double");
  if (target === "T") return ui.t("any_treble");
  if (target === "25") return ui.t("bull_target");
  if (target === "50") return ui.t("bullseye_target");
  return ui.label(target);
}

const hearts = (lives) => (lives > 0 ? "♥".repeat(lives) : "✕");

// What the board shows: a training game, a bull-off, Cricket, a party game, X01, or none.
function gameView(stateOf) {
  const drill = drillView(stateOf("drill"));
  if (drill) return { mode: "drill", drill };
  const bullOff = bullOffView(stateOf("practice"));
  if (bullOff) return { mode: "bulloff", bullOff };
  const cricket = cricketView(stateOf("practice"));
  if (cricket) return { mode: "cricket", cricket };
  const party = partyView(stateOf("practice"));
  if (party) return { mode: "party", party };
  const practice = practiceView(stateOf("practice"));
  if (practice) return { mode: "x01", practice };
  return { mode: "idle" };
}

// Beds to aim at next, outlined on the live board.
function aimBeds(view) {
  const { mode, practice } = view;
  if (mode === "drill") return drillBeds(view.drill);
  if (mode === "bulloff") return targetBeds("25");
  if (mode === "cricket") return cricketBeds(view.cricket);
  if (mode === "party") return partyBeds(view.party);
  if (mode !== "x01" || practice.winner !== null) return [];
  // Before double in, every double opens the leg.
  if (!practice.opened) return targetBeds("D");
  // Without a checkout, the setup's first dart.
  return practice.won ? [] : hitBeds(practice.route[0] ?? practice.setup?.route[0] ?? "");
}

// Scoreboard -----------------------------------------------------------------

// Players without a name are numbered in a match; alone, nobody needs a name.
// The bot is the bot.
const playerName = (ui, score, match) =>
  score.bot ? ui.t("bot") : score.name || (match ? `${ui.t("score_player")} ${score.player}` : "");

// The score of the player at the board, with the name and whether it is the bot.
const upScore = (game) =>
  game.scores?.find((score) => score.player === game.player) ?? { player: game.player, name: game.name };

const note = (text, kind = "") => `<span class="note${kind ? ` ${kind}` : ""}">${escapeHtml(text)}</span>`;

// The players of a team as they are called: Alex & Kim.
const teamName = (ui, team, scores) =>
  team.players
    .map((player) => playerName(ui, scores.find((score) => score.player === player) ?? { player, name: null }, true))
    .join(" & ");

// A won match as darts players tell it, the winner first: 3 : 2 in legs, or
// in sets when the match has them; a team counts once. A match of one leg
// has no result to tell.
function matchResult(game) {
  const winner = game.scores.find((score) => score.player === game.winner);
  if (!winner || game.scores.length < 2 || (game.legsToWin < 2 && game.setsToWin < 2)) return "";
  const count = (score) => (game.setsToWin > 1 ? score.sets : score.legs);
  const teams = game.teams ?? [];
  const others = teams.length
    ? teams
        .filter((team) => !team.players.includes(winner.player))
        .map((team) => game.scores.find((score) => score.player === team.players[0]))
        .filter(Boolean)
    : game.scores.filter((score) => score !== winner);
  return [winner, ...others].map(count).join(" : ");
}

// Who won the match, and how: "Alex wins the match 3 : 2!", or both players
// of a team; without a result "Alex wins the match!".
function winnerText(game, ui) {
  const result = matchResult(game);
  const team = game.teams?.find((item) => item.players.includes(game.winner));
  if (team) {
    const said = result ? fill(ui.t("score_winners_by"), { result }) : ui.t("score_winners");
    return `${teamName(ui, team, game.scores)} ${said}`;
  }
  const score = game.scores.find((item) => item.player === game.winner) ?? { player: game.winner, name: null };
  const said = result ? fill(ui.t("score_winner_by"), { result }) : ui.t("score_winner");
  return `${playerName(ui, score, true)} ${said}`;
}

// The Cricket game as players call it: Cricket, Cut-Throat Cricket, Tactics.
const cricketTitle = (t, kind) => t(kind === "cricket" ? "cricket" : `cricket_${kind}`);

const bedChips = (ui, route) =>
  route.map((bed) => `<span class="bed">${escapeHtml(ui.label(bed))}</span>`).join("");

// Legs and sets of a player, where the match has them.
const matchScore = (game, score, t) => [
  game.legsToWin > 1 ? `${t("score_legs")} ${score.legs}` : "",
  game.setsToWin > 1 ? `${t("score_sets")} ${score.sets}` : "",
];

// What the player at the board needs in X01: the route, a bust or the game shot.
function x01Note(practice, ui) {
  const { t } = ui;
  if (practice.won) return note(t("game_shot"), "won");
  if (practice.bust) return note(t("bust"), "bust");
  if (practice.route.length) return bedChips(ui, practice.route);
  if (!practice.opened) return note(t(practice.inMode === "master" ? "master_in_needed" : "double_in_needed"));
  if (practice.setup) return setupHtml(practice.setup, ui);
  // Single out finishes up to 180; double out only up to 170.
  return practice.remaining <= highestCheckout(practice) ? note(t("no_checkout")) : "";
}

// The setup darts, and the score they leave for the next visit.
const setupHtml = (setup, ui) =>
  `<span class="setup" title="${escapeHtml(ui.t("setup_hint"))}">${bedChips(ui, setup.route)}` +
  `<span class="leave">${escapeHtml(fill(ui.t("setup_leave"), { leave: setup.leave }))}</span></span>`;

// Start scores are worth showing when players start from different scores.
const handicap = (practice) => practice.scores.some((score) => score.start !== null && score.start !== practice.game);

// A player of the scoreboard and of the live card's match list.
function x01Players(practice, ui) {
  const { t, format } = ui;
  const scores = practice.scores.length
    ? practice.scores
    : [{ player: 1, name: practice.name, remaining: practice.remaining, legs: 0, sets: 0, average: null }];
  const match = scores.length > 1;
  const starts = handicap(practice);
  return scores.map((score) => {
    const active = practice.winner === null && score.player === practice.player;
    return {
      name: playerName(ui, score, match),
      // The bot shows its level; players their own start score.
      badge:
        score.bot && practice.botLevel
          ? fill(t("bot_level"), { level: practice.botLevel })
          : starts && score.start
            ? String(score.start)
            : "",
      value: String(score.remaining),
      state: practice.winner === score.player ? "winner" : active && match ? "active" : "",
      note: active ? x01Note(practice, ui) : "",
      details: match
        ? [...matchScore(practice, score, t), score.average === null ? "" : `Ø ${format(score.average, 1)}`]
        : [
            practice.darts ? `${practice.darts} ${t("leg_darts")}` : "",
            practice.average === null ? "" : `Ø ${format(practice.average, 1)}`,
          ],
    };
  });
}

// The two teams of a team match: the score, the partners with the one at the
// board, and legs and sets.
function x01Teams(practice, ui) {
  const { t, format } = ui;
  const starts = handicap(practice);
  return practice.teams
    .map((team) => ({ team, members: practice.scores.filter((score) => team.players.includes(score.player)) }))
    .filter(({ members }) => members.length)
    .map(({ team, members }) => {
      const up = practice.winner === null && team.players.includes(practice.player);
      const [first] = members;
      return {
        name: teamName(ui, team, practice.scores),
        badge: starts && first.start ? String(first.start) : "",
        value: String(first.remaining),
        state: team.players.includes(practice.winner) ? "winner" : up ? "active" : "",
        note: up ? x01Note(practice, ui) : "",
        members: members.map((score) => ({
          name: playerName(ui, score, true),
          up: up && score.player === practice.player,
          detail: score.average === null ? "" : `Ø ${format(score.average, 1)}`,
        })),
        details: matchScore(practice, first, t),
      };
    });
}

// Every player, or in a team match the two teams.
function x01Tiles(practice, ui) {
  const teams = x01Teams(practice, ui);
  return teams.length ? teams : x01Players(practice, ui);
}

// What the player at the board aims at in a party game.
function partyNote(party, ui) {
  const { t } = ui;
  const killer = party.kind === "killer";
  const current = party.scores.find((score) => score.player === party.player);
  if (party.won) return note(t("game_shot"), "won");
  if (party.needsPlayers) return note(t("needs_players"));
  if (killer && party.phase === "choose") return note(t("killer_choose"));
  if (party.target) return `<span class="bed">${escapeHtml(targetText(ui, party.target))}</span>`;
  if (current?.left !== null && current?.left !== undefined) return note(fill(t("gotcha_left"), { points: current.left }));
  if (killer && current?.killer) return note(t("killer_hunt"));
  return "";
}

function partyPlayers(party, ui) {
  const { t } = ui;
  const match = party.scores.length > 1;
  const killer = party.kind === "killer";
  return party.scores.map((score) => {
    const active = party.winner === null && score.player === party.player;
    // Out in Killer, or out of the extra rounds after a tie.
    const out = (killer && score.lives === 0) || Boolean(party.playoff && !party.playoff.includes(score.player));
    const lives = score.lives ?? 0;
    return {
      name: playerName(ui, score, match),
      value: killer ? hearts(lives) : String(score.points),
      lives: killer,
      // Hearts read as "3 lives", not as three heart symbols.
      spoken: killer ? fill(t(lives === 1 ? "killer_life" : "killer_lives"), { count: lives }) : "",
      state: party.winner === score.player ? "winner" : active && match ? "active" : out ? "out" : "",
      note: active ? partyNote(party, ui) : "",
      details: [
        ...(match ? matchScore(party, score, t) : []),
        killer && score.number ? String(score.number) : "",
        killer && score.killer ? t("party_killer") : "",
        killer && out ? t("out") : "",
        score.progress === null ? "" : `${score.progress}/${WORLD_TARGETS}`,
        // The points to go of the others; the winner has none.
        !score.left || active ? "" : fill(t("gotcha_left"), { points: score.left }),
      ],
    };
  });
}

// Every dart of the bull-off with its bed and, where measured, its distance;
// once two darts are in, the one that leads.
function bullOffPlayers(bullOff, ui) {
  const match = bullOff.throws.length > 1;
  const leaders = bullOffLeaders(bullOff);
  const thrown = bullOff.throws.filter((item) => item.hit).length;
  const leader = thrown > 1 && leaders.length === 1 ? leaders[0] : null;
  return bullOff.throws.map((item) => ({
    name: playerName(ui, item, match),
    value: item.hit ? ui.label(item.hit) : "–",
    state: item.player === bullOff.player ? "active" : item.player === leader ? "winner" : "",
    note: "",
    details: [
      item.distance === null ? "" : `${ui.format(item.distance, 1)}\u00a0mm`,
      item.player === leader ? ui.t("bull_off_leads") : "",
    ],
  }));
}

// A start score of the player's own, beside the name.
const badge = (player) => (player.badge ? ` <span class="badge">${escapeHtml(player.badge)}</span>` : "");

// The partners of a team, the one at the board in bold.
const membersHtml = (members) =>
  members
    .map((member) => {
      const text = escapeHtml([member.name, member.detail].filter(Boolean).join(" "));
      return member.up ? `<b>${text}</b>` : `<span>${text}</span>`;
    })
    .join(" · ");

// Who is up and who won, for assistive technology: the page shows both by colour.
const turnMark = (player) => (player.state === "active" ? ' aria-current="true"' : "");
const winnerMark = (player, ui) =>
  player.state === "winner" && ui.t ? ` <span class="visually-hidden">${escapeHtml(ui.t("winner"))}</span>` : "";

// A value such as Killer's hearts, with the words a screen reader says instead.
const valueHtml = (tag, style, player) =>
  `<${tag} class="${style}${player.lives ? " lives" : ""}"` +
  `${player.spoken ? ` role="img" aria-label="${escapeHtml(player.spoken)}"` : ""}>${escapeHtml(player.value)}</${tag}>`;

// Players as large tiles on the scoreboard, with the picture of a linked person.
function playerTiles(players, ui = {}) {
  const tiles = players.map(
    (player) =>
      `<div class="player${player.state ? ` ${player.state}` : ""}"${turnMark(player)}><div class="name">` +
      `${avatarHtml(ui.avatar?.(player.name))}${escapeHtml(player.name)}${badge(player)}${winnerMark(player, ui)}</div>` +
      valueHtml("div", "big", player) +
      `<div class="route"><div class="route-line">${player.note}</div></div>` +
      (player.members ? `<div class="members">${membersHtml(player.members)}</div>` : "") +
      `<div class="details"><span class="details-line">${escapeHtml(player.details.filter(Boolean).join(" · "))}</span></div></div>`
  );
  const teams = players.some((player) => player.members) ? " teams" : "";
  return `<div class="players n${Math.max(players.length, 1)}${teams}">${tiles.join("")}</div>`;
}

// Players as rows in the live card.
const playerRows = (players, ui = {}) =>
  players
    .map(
      (player) =>
        `<div class="player-score${player.state ? ` ${player.state}` : ""}"${turnMark(player)}>` +
        `<span class="who">${escapeHtml(player.name)}${badge(player)}${winnerMark(player, ui)}</span>` +
        `<span class="muted">${escapeHtml(player.details.filter(Boolean).join(" · "))}</span>` +
        valueHtml("span", "rest", player) +
        `</div>`
    )
    .join("");

// The columns of the chalkboard: every player, or every team with its
// partners, the one at the board in bold.
function cricketColumns(cricket, ui) {
  const mpr = (score) => (score.mpr === null ? "–" : ui.format(score.mpr, 2));
  const playing = cricket.winner === null;
  const teams = cricket.teams
    .map((team) => ({ team, members: cricket.scores.filter((score) => team.players.includes(score.player)) }))
    .filter(({ members }) => members.length)
    .map(({ team, members }) => ({
      ...members[0],
      head: members
        .map((score) => {
          const name = escapeHtml(playerName(ui, score, true));
          return playing && score.player === cricket.player ? `<b>${name}</b>` : name;
        })
        .join(" &#38; "),
      mpr: members.map(mpr).join(" · "),
      active: playing && team.players.includes(cricket.player),
      winner: team.players.includes(cricket.winner),
    }));
  if (teams.length) return teams;
  const match = cricket.scores.length > 1;
  return cricket.scores.map((score) => ({
    ...score,
    head: `${avatarHtml(ui.avatar?.(playerName(ui, score, match)))}${escapeHtml(playerName(ui, score, match))}`,
    mpr: mpr(score),
    active: playing && cricket.player === score.player,
    winner: cricket.winner === score.player,
  }));
}

// The Cricket chalkboard: marks, points, marks per round, legs and sets. The
// scoreboard shows the next number in its corner; the live card has it beside.
function cricketTable(cricket, ui, { aim = true } = {}) {
  const { t } = ui;
  const columns = cricketColumns(cricket, ui);
  const match = columns.length > 1;
  const kind = (column) => (column.winner ? "winner" : match && column.active ? "active" : "");
  // As on a dart machine, the player at the board sees where a dart scores, because they
  // have closed and somebody still needs it, and what to close, because somebody scores on it.
  const up = match ? columns.find((column) => column.active) : undefined;
  const others = columns.filter((column) => column !== up);
  const hintOf = (column, slot) => {
    if (column !== up || slot === undefined) return "";
    if (up.marks[slot] >= 3) return others.some((other) => other.marks[slot] < 3) ? "score" : "";
    return others.some((other) => other.marks[slot] >= 3) ? "close" : "";
  };
  const cell = (column, slot) => {
    const hint = hintOf(column, slot);
    const style = [kind(column), hint && `aim-${hint}`].filter(Boolean).join(" ");
    return `<td class="${style}"${hint ? ` title="${escapeHtml(t(`cricket_aim_${hint}`))}"` : ""}>`;
  };
  const row = (style, heading, content, slot) =>
    `<tr class="${style}"><th>${heading}</th>${columns
      .map((column) => `${cell(column, slot)}${content(column)}</td>`)
      .join("")}</tr>`;
  const marks = (count) =>
    `<span role="img" aria-label="${escapeHtml(t(`mark_${count}`))}">${CRICKET_MARKS[count]}</span>`;
  // The numbers, then what Wild Mouse closes besides them; a question mark for a number
  // of Hidden Cricket that does not show yet.
  const keys = [...cricket.numbers.map((number) => (number === null ? null : String(number))), ...cricket.targets];
  const hiddenHeading = `<span role="img" aria-label="${escapeHtml(t("cricket_hidden"))}">?</span>`;
  const rows = keys.map((key, slot) => {
    const bed = key === "25" ? "BULL" : `T${key}`;
    const aimed = key !== null && (cricket.targetRow === null ? bed === cricket.target : key === cricket.targetRow);
    const style = columns.every((column) => column.marks[slot] >= 3) ? "closed" : aimed ? "target" : "";
    const heading =
      key === null
        ? hiddenHeading
        : escapeHtml(key === "25" ? "Bull" : WILD_TARGETS.includes(key) ? t(`wild_${key}`) : key);
    return row(style, heading, (column) => marks(column.marks[slot]), slot);
  });
  const text = (value) => (column) => escapeHtml(value(column));
  const label = (key) => escapeHtml(t(key));
  if (match) rows.push(row("total", label("cricket_points"), text((column) => String(column.points))));
  rows.push(row("detail", label("cricket_mpr"), text((column) => column.mpr)));
  if (match && cricket.legsToWin > 1) rows.push(row("detail", label("score_legs"), text((column) => String(column.legs))));
  if (match && cricket.setsToWin > 1) rows.push(row("detail", label("score_sets"), text((column) => String(column.sets))));
  const head = columns
    .map((column) => ({ ...column, state: kind(column) }))
    .map((column) => `<th class="${column.state}"${turnMark(column)}>${column.head}${winnerMark(column, ui)}</th>`)
    .join("");
  const next = aim && cricket.target && !cricket.won && cricket.winner === null ? bedChips(ui, [cricket.target]) : "";
  const shot = aim && cricket.won && cricket.winner === null ? note(t("game_shot"), "won") : "";
  const corner = shot || next;
  // Tactics has twelve numbers and Wild Mouse ten rows; they fit the screen in smaller type.
  const size = keys.length > CRICKET_NUMBERS.length ? " many" : "";
  // The next number sits above the numbers, so the chalkboard fits a landscape screen.
  return (
    `<table class="cricket${size}">${
      corner || columns.some((column) => column.head) ? `<thead><tr><th class="aim">${corner}</th>${head}</tr></thead>` : ""
    }<tbody>${rows.join("")}</tbody></table>`
  );
}

// Golf and Baseball: the score of every hole or inning per player, and the total.
function scorecardTable(party, ui) {
  const current = party.winner === null ? party.round : null;
  const played = Math.max(party.rounds ?? 0, current ?? 0, ...party.scores.map((score) => score.scorecard.length));
  const rounds = Array.from({ length: played }, (_, index) => index + 1);
  // Extra rounds go on from 1 after 20.
  const number = (round) => ((round - 1) % 20) + 1;
  const now = (round) => (round === current ? ` class="now"` : "");
  const match = party.scores.length > 1;
  const rows = party.scores.map((score) => {
    const up = current !== null && score.player === party.player;
    // The visit at the board counts for the round being played.
    const booked = score.scorecard.reduce((sum, value) => sum + value, 0);
    const live = up && party.visit.length ? score.points - booked : null;
    const cells = rounds
      .map((round) => `<td${now(round)}>${score.scorecard[round - 1] ?? (round === current && live !== null ? live : "")}</td>`)
      .join("");
    const style = party.winner === score.player ? "winner" : up && match ? "active" : "";
    return (
      `<tr${style ? ` class="${style}"` : ""}><th>${escapeHtml(playerName(ui, score, match))}</th>${cells}` +
      `<td class="total">${score.points}</td></tr>`
    );
  });
  const head = rounds.map((round) => `<th${now(round)}>${number(round)}</th>`).join("");
  return (
    `<table class="scorecard"><thead><tr><th></th>${head}<th class="total">${escapeHtml(ui.t("total"))}</th></tr></thead>` +
    `<tbody>${rows.join("")}</tbody></table>`
  );
}

// The round of a party game: Hole 3/9, Inning 5/9, Round 2/7, or an extra round.
function partyRound(party, t) {
  if (!party.rounds || party.round === null) return "";
  const name = t({ golf: "golf_hole", baseball: "baseball_inning" }[party.kind] ?? "drill_round");
  if (party.playoff) return `${t("playoff")} · ${name} ${party.target ?? party.round}`;
  return `${name} ${party.round}/${party.rounds}`;
}

// A training game: the target, what happened and the facts about the game.
// A fact reads "12 darts", or with its name first "Round 3 / 21".
function drillParts(drill, ui) {
  const { t, percent } = ui;
  const fact = (value, name = "", lead = false) => ({ value, name, lead });
  const big = drill.finished ? "✓" : targetText(ui, drill.target ?? "–");
  if (drill.kind === "bobs_27") {
    const outcome = drill.completed
      ? note(fill(t("drill_bobs_done"), { points: drill.score }), "won")
      : note(t("drill_bobs_lost"), "bust");
    return {
      big,
      note: drill.finished ? outcome : "",
      facts: [
        fact(String(drill.score ?? "–"), t("drill_points")),
        fact(`${Math.min(drill.progress + 1, drill.targets)} / ${drill.targets}`, t("drill_round"), true),
      ],
    };
  }
  const scored = drill.finished ? note(fill(t("drill_bobs_done"), { points: drill.score }), "won") : "";
  if (drill.kind === "catch_40" && drill.finished) {
    return { big, note: scored, facts: [fact(String(drill.score ?? 0), t("drill_points"))] };
  }
  if (CHECKOUT_DRILLS.includes(drill.kind)) {
    const visit = fact(`${drill.visit ?? 1} / ${drill.visits ?? 3}`, t("drill_visit"), true);
    const facts =
      drill.kind === "catch_40"
        ? [
            fact(`${drill.progress + 1} / ${drill.targets}`, t("drill_round"), true),
            visit,
            fact(String(drill.score ?? 0), t("drill_points")),
          ]
        : [
            visit,
            fact(`${drill.successes} / ${drill.attempts}`, t("drill_checked")),
            // The rate and the best show a dash until they are known, so the facts
            // keep their lines from the first visit.
            fact(drill.rate === null ? "– %" : percent(drill.rate)),
            fact(drill.best === null ? "–" : String(drill.best), t("drill_best"), true),
          ];
    return {
      big: String(drill.remaining ?? drill.target ?? "–"),
      note: drill.won
        ? note(t("game_shot"), "won")
        : drill.bust
          ? note(t("bust"), "bust")
          : drill.setup && !drill.route.length
            ? setupHtml(drill.setup, ui)
            : bedChips(ui, drill.route),
      facts,
    };
  }
  if (drill.kind === "jdc_challenge" || drill.kind === "singles") {
    const step =
      drill.kind === "jdc_challenge"
        ? fact(`${drill.part ?? 1} / 3`, t("drill_part"), true)
        : fact(`${Math.min(drill.progress + 1, drill.targets)} / ${drill.targets}`, t("drill_round"), true);
    return {
      big,
      note: scored,
      facts: [
        step,
        fact(String(drill.score ?? 0), t("drill_points")),
        fact(drill.best === null ? "–" : String(drill.best), t("drill_best"), true),
      ],
    };
  }
  return {
    big,
    note: drill.finished ? note(fill(t("drill_done"), { darts: drill.darts }), "won") : "",
    facts: [
      fact(`${drill.progress} / ${drill.targets}`),
      fact(String(drill.darts), t("leg_darts")),
      fact(percent(drill.hitRate), t("drill_hits")),
    ],
  };
}

// Facts in large type, their values bold.
const factsHtml = (facts) =>
  facts
    .map(({ value, name, lead }) => {
      const bold = `<b>${escapeHtml(value)}</b>`;
      return `<span>${lead ? `${escapeHtml(name)} ${bold}` : `${bold} ${escapeHtml(name)}`}</span>`;
    })
    .join("");

// Facts in their box, which lays them out by its width.
const factsBlock = (html) => `<div class="facts-box"><div class="facts">${html}</div></div>`;

// Facts in a line of text.
const factsText = (facts) =>
  facts.map(({ value, name, lead }) => (lead ? `${name} ${value}` : `${value} ${name}`).trim()).join(" · ");

function drillBoard(drill, ui) {
  const parts = drillParts(drill, ui);
  // "Bull (25/50)" fits the screen in smaller type than a number.
  const long = parts.big.length > 4 ? " long" : "";
  return (
    `<div class="single"><div class="big${long}">${escapeHtml(parts.big)}</div><div class="route"><div class="route-line">${parts.note}</div></div>` +
    `${factsBlock(factsHtml(parts.facts))}</div>`
  );
}

function idleBoard(stats, ui) {
  const { t, format } = ui;
  const fact = (value, name) => ({ value, name });
  const facts = [
    fact(format(stats.darts, 0), t("darts")),
    fact(format(stats.average, 1), t("average")),
    fact(format(stats.highest, 0), t("highest")),
    fact(format(stats.max, 0), t("max")),
  ];
  if (stats.streak > 0) facts.push(fact(format(stats.streak, 0), t(stats.streak === 1 ? "streak_day" : "streak_days")));
  if (stats.today !== null && stats.today !== undefined) {
    facts.push(
      fact(stats.goal ? `${format(stats.today, 0)} / ${format(stats.goal, 0)}` : format(stats.today, 0), t("darts_today"))
    );
  }
  return (
    `<div class="single"><div class="label">${escapeHtml(t("visit"))}</div>` +
    `<div class="big">${escapeHtml(stats.visit ?? "–")}</div>${factsBlock(factsHtml(facts))}</div>`
  );
}

// Match summary ----------------------------------------------------------------

// The summary of the finished match on the board, as the practice sensor keeps
// it; the next game, which clears the winner, ends it.
function summaryView(state) {
  const attributes = state?.attributes || {};
  const summary = attributes.summary;
  if (!state || state.state === "unavailable" || !summary || typeof summary !== "object") return null;
  if (!Number.isInteger(attributes.winner) || summary.winner !== attributes.winner || summary.game !== attributes.game) {
    return null;
  }
  const raw = (Array.isArray(summary.players) ? summary.players : []).filter(
    (item) => item && Number.isInteger(item.player)
  );
  if (raw.length < 2) return null;
  // X01 has averages, the Cricket games marks per round; party games neither.
  const kind = "average" in raw[0] ? "x01" : "mpr" in raw[0] ? "cricket" : "party";
  return {
    ended: String(summary.ended ?? ""),
    kind,
    winner: summary.winner,
    legsToWin: finite(summary.legs_to_win) ?? 1,
    setsToWin: finite(summary.sets_to_win) ?? 1,
    doubleOut: summary.double_out !== false,
    players: raw.map((item) => ({
      player: item.player,
      name: named(item.name),
      ...botOf(item),
      legs: finite(item.legs) ?? 0,
      sets: finite(item.sets) ?? 0,
      darts: finite(item.darts),
      average: finite(item.average),
      first9: finite(item.first_9_average),
      checkouts: finite(item.checkouts) ?? 0,
      atDouble: finite(item.darts_at_double) ?? 0,
      checkoutRate: finite(item.checkout_rate),
      highestCheckout: finite(item.highest_checkout),
      scores100: finite(item.scores_100),
      scores140: finite(item.scores_140),
      scores180: finite(item.scores_180),
      bestLeg: finite(item.best_leg),
      mpr: finite(item.mpr),
      marks: finite(item.marks),
    })),
  };
}

// The rows of the summary: the result, then the numbers of the game.
function summaryRows(summary, ui) {
  const { t, format, percent } = ui;
  const value = (number, digits = 0) => (number === null ? "–" : format(number, digits));
  const darts = (number) => (number === null ? "–" : fill(t("unit_darts"), { value: format(number, 0) }));
  const checkout = (player) =>
    player.checkoutRate === null
      ? "–"
      : `${percent(player.checkoutRate, 1)} (${player.checkouts}/${player.atDouble})`;
  const doubles = summary.doubleOut;
  const rows = {
    x01: [
      [t("average"), (player) => value(player.average, 1)],
      [t("first_9"), (player) => value(player.first9, 1)],
      ...(doubles ? [[t("summary_checkout"), checkout]] : []),
      [t("highest_checkout"), (player) => value(player.highestCheckout)],
      [t("max"), (player) => value(player.scores180)],
      [t("scores_140"), (player) => value(player.scores140)],
      [t("scores_100"), (player) => value(player.scores100)],
      [t("summary_best_leg"), (player) => darts(player.bestLeg)],
      ...(doubles ? [[t("summary_at_double"), (player) => value(player.atDouble)]] : []),
    ],
    cricket: [
      [t("cricket_mpr"), (player) => value(player.mpr, 2)],
      [t("summary_marks"), (player) => value(player.marks)],
      [t("summary_best_leg"), (player) => darts(player.bestLeg)],
    ],
    party: [],
  }[summary.kind];
  const sets = summary.setsToWin > 1;
  const legs = [t("score_legs"), (player) => String(player.legs)];
  return [
    ...(sets ? [[t("score_sets"), (player) => String(player.sets)], legs] : [legs]),
    ...rows,
    [t("darts"), (player) => value(player.darts)],
  ];
}

// The summary as a table: a column per player with the picture of a linked
// person, the winner's highlighted, and the result in the first row. In a
// team match, both partners of the winning team are the winners.
function summaryTable(summary, ui, teams = []) {
  const team = (Array.isArray(teams) ? teams : []).find((item) => item.players.includes(summary.winner));
  const winners = team ? team.players : [summary.winner];
  const column = (player) => (winners.includes(player.player) ? "winner" : "");
  const head = summary.players
    .map((player) => {
      const name = playerName(ui, player, true);
      const state = column(player);
      return `<th class="${state}">${avatarHtml(ui.avatar?.(name))}${escapeHtml(name)}${winnerMark({ state }, ui)}</th>`;
    })
    .join("");
  const rows = summaryRows(summary, ui)
    .map(
      ([name, cell], index) =>
        `<tr${index ? "" : ` class="result"`}><th>${escapeHtml(name)}</th>${summary.players
          .map((player) => `<td class="${column(player)}">${escapeHtml(cell(player))}</td>`)
          .join("")}</tr>`
    )
    .join("");
  return (
    `<table class="summary"><thead><tr><th class="caption">${escapeHtml(ui.t("summary"))}</th>${head}</tr></thead>` +
    `<tbody>${rows}</tbody></table>`
  );
}

// The X01 rules besides the usual double out, and the round of a leg with a round
// limit; past it, the extra rounds of a tie.
function x01Rules(practice, t) {
  const rules = [
    { double: t("double_in"), master: t("master_in") }[practice.inMode] ?? "",
    { straight: t("straight_out"), master: t("master_out") }[practice.outMode] ?? "",
    practice.bullMode === "50_50" ? t("bull_50_50") : "",
  ];
  if (practice.maxRounds && practice.round !== null) {
    const name = t("drill_round");
    rules.push(
      practice.round > practice.maxRounds
        ? `${t("playoff")} · ${name} ${practice.round}`
        : `${name} ${practice.round}/${practice.maxRounds}`
    );
  }
  return rules;
}

// Legs per set and sets to win of a match.
const matchFormat = (game, t) =>
  game.scores.length > 1
    ? [
        game.legsToWin > 1 ? `${game.legsToWin} ${t("legs_per_set")}` : "",
        game.setsToWin > 1 ? `${game.setsToWin} ${t("sets_to_win")}` : "",
      ]
    : [];

// Title, format, winner banner and main markup of the scoreboard.
function scoreboardHtml(view, ui) {
  const { t } = ui;
  if (view.mode === "drill") {
    return { title: t(`drill_${view.drill.kind}`), meta: "", banner: "", bannerKind: "", main: drillBoard(view.drill, ui) };
  }
  if (view.mode === "idle") {
    return { title: ui.name, meta: t("training"), banner: "", bannerKind: "", main: idleBoard(ui.stats, ui) };
  }
  if (view.mode === "bulloff") {
    // A tie throws again, which the banner tells in the colour of a warning.
    const { rethrow } = view.bullOff;
    return {
      title: t("bull_off"),
      meta: t("bull_off_hint"),
      banner: rethrow ? t("bull_off_rethrow") : "",
      bannerKind: rethrow ? "rethrow" : "",
      main: playerTiles(bullOffPlayers(view.bullOff, ui), ui),
    };
  }
  const game = { cricket: view.cricket, party: view.party }[view.mode] ?? view.practice;
  const round = view.mode === "party" ? partyRound(game, t) : "";
  // Cut-Throat turns the points round, Random and Hidden Cricket draw their numbers, and
  // Golf's players stop by pulling their darts.
  const hint = {
    cut_throat: "cut_throat_hint",
    wild_mouse: "wild_mouse_hint",
    random_cricket: "random_cricket_hint",
    hidden_cricket: "hidden_cricket_hint",
    golf: "golf_hint",
  }[game.kind];
  const scorecard = view.mode === "party" && SCORECARD_GAMES.includes(game.kind);
  // The summary of a won match takes the place of the players.
  const main = view.summary
    ? () => summaryTable(view.summary, ui, game.teams)
    : {
        cricket: () => cricketTable(game, ui),
        party: () => playerTiles(partyPlayers(game, ui), ui) + (scorecard ? scorecardTable(game, ui) : ""),
        x01: () => playerTiles(x01Tiles(game, ui), ui),
      }[view.mode];
  return {
    title: { cricket: cricketTitle(t, game.kind), party: t(`party_${game.kind}`) }[view.mode] ??
      `${t("practice")} ${game.game ?? ""}`.trim(),
    meta: [round, hint ? t(hint) : "", ...(view.mode === "x01" ? x01Rules(game, t) : []), ...matchFormat(game, t)]
      .filter(Boolean)
      .join(" · "),
    banner: game.winner !== null ? winnerText(game, ui) : "",
    bannerKind: "",
    main: main(),
  };
}

// Players -------------------------------------------------------------------

// Profiles, head-to-head records and recent matches from their two sensors.
function playersView(profiles, lastMatch) {
  const players = (Array.isArray(profiles?.attributes?.players) ? profiles.attributes.players : [])
    .filter((player) => player && named(player.name))
    .map((player) => ({
      name: player.name,
      legsPlayed: finite(player.legs_played) ?? 0,
      legsWon: finite(player.legs_won) ?? 0,
      matchesPlayed: finite(player.matches_played) ?? 0,
      matchesWon: finite(player.matches_won) ?? 0,
      average: finite(player.average),
      first9: finite(player.first_9_average),
      checkoutRate: finite(player.checkout_rate),
      mpr: finite(player.mpr),
      bestMpr: finite(player.best_mpr),
      highestVisit: finite(player.highest_visit),
      highestCheckout: finite(player.highest_checkout),
      fewestDarts: Object.entries(
        player.fewest_darts && typeof player.fewest_darts === "object" ? player.fewest_darts : {}
      )
        .filter(([game, darts]) => /^\d+$/.test(game) && Number.isInteger(darts))
        .map(([game, darts]) => ({ game: Number(game), darts }))
        .sort((a, b) => a.game - b.game),
    }));
  const attributes = lastMatch?.attributes || {};
  const headToHead = (Array.isArray(attributes.head_to_head) ? attributes.head_to_head : []).filter(
    (item) =>
      item &&
      Array.isArray(item.players) &&
      item.players.length === 2 &&
      Array.isArray(item.wins) &&
      item.wins.length === 2 &&
      item.wins.every(Number.isInteger)
  );
  const matches = (Array.isArray(attributes.matches) ? attributes.matches : [])
    .filter((match) => match && typeof match.ended === "string" && Array.isArray(match.players))
    .map((match) => ({
      ended: match.ended,
      game: match.game,
      winner: finite(match.winner),
      // Both players of the winning team, in a team match.
      winners: Array.isArray(match.winners) ? match.winners.filter(Number.isInteger) : [finite(match.winner)],
      legsToWin: finite(match.legs_to_win) ?? 1,
      setsToWin: finite(match.sets_to_win) ?? 1,
      players: match.players.filter((player) => player && typeof player === "object"),
    }));
  return { players, headToHead, matches };
}

// What a player won in a match of the history: sets when the match had sets,
// otherwise legs. Up to version 1.5, winning the match took the winner's legs
// of the deciding set away again; a match won in legs had all it needed.
function historyScore(match, player, index) {
  if (match.setsToWin > 1) return finite(player.sets) ?? 0;
  const legs = finite(player.legs) ?? 0;
  return match.winners.includes(index + 1) ? Math.max(legs, match.legsToWin) : legs;
}

// A game as players call it: 501, Cricket, Killer, Bob's 27. Games the card does
// not know yet read as Home Assistant names the option, if it is asked.
function gameName(t, game, fallback) {
  if (Number.isInteger(game)) return String(game);
  if (CRICKET_GAMES.includes(game)) return cricketTitle(t, game);
  if (PARTY_GAMES.includes(game)) return t(`party_${game}`);
  if (DRILLS.includes(game)) return t(`drill_${game}`);
  return (fallback && fallback(game)) || String(game ?? "");
}

// The actions of the profile menu of the players card, in their order, with the title of
// the dialog that asks before each one and the words of the button that does it.
const MANAGE_ACTIONS = {
  rename: { title: "rename_title", button: "manage_rename" },
  merge: { title: "merge_title", button: "merge_button" },
  delete: { title: "delete_title", button: "manage_delete" },
};
const MANAGE_LABELS = { rename: "manage_rename", merge: "manage_merge", delete: "manage_delete" };

// The button that opens the menu of a profile, and the menu while it is open: Merge into
// only where there is another profile to merge into.
function manageHtml(name, ui, others) {
  const open = ui.menu === name;
  const label = escapeHtml(fill(ui.t("manage_player"), { name }));
  const button =
    `<button type="button" class="manage" data-manage="${escapeHtml(name)}" data-focus="${escapeHtml(`manage:${name}`)}"` +
    ` aria-haspopup="menu" aria-expanded="${open}" aria-label="${label}"><span aria-hidden="true">⋮</span></button>`;
  if (!open) return button;
  const items = Object.keys(MANAGE_ACTIONS)
    .filter((action) => action !== "merge" || others)
    .map(
      (action) =>
        `<button type="button" role="menuitem" tabindex="-1" data-action="${action}" data-focus="menu:${action}">` +
        `${escapeHtml(ui.t(MANAGE_LABELS[action]))}</button>`
    )
    .join("");
  return `${button}<div class="manage-menu" role="menu" aria-label="${label}">${items}</div>`;
}

function playersHtml(view, ui) {
  const { t, format, percent, date } = ui;
  const value = (number, digits = 0) => (number === null ? "–" : format(number, digits));
  const players = view.players
    .map((player) => {
      const rows = [
        [t("average"), value(player.average, 1)],
        [t("first_9"), value(player.first9, 1)],
        [t("checkout_short"), percent(player.checkoutRate, 1)],
        ...(player.mpr === null ? [] : [[t("cricket_mpr"), value(player.mpr, 2)]]),
        ...(player.bestMpr === null ? [] : [[t("best_mpr"), value(player.bestMpr, 2)]]),
        [t("highest"), value(player.highestVisit)],
        [t("highest_checkout"), value(player.highestCheckout)],
        ...player.fewestDarts.map((best) => [
          fill(t("best_leg"), { game: best.game }),
          fill(t("unit_darts"), { value: best.darts }),
        ]),
      ];
      return (
        `<div class="profile"><div class="profile-name">${avatarHtml(ui.avatar?.(player.name))}` +
        `<span>${escapeHtml(player.name)}</span>${ui.manage ? manageHtml(player.name, ui, view.players.length > 1) : ""}</div>` +
        `<div class="muted">${escapeHtml(
          `${t("profile_legs")} ${player.legsWon}/${player.legsPlayed} · ` +
            `${t("profile_matches")} ${player.matchesWon}/${player.matchesPlayed}`
        )}</div><dl>${rows
          .map(([name, shown]) => `<dt>${escapeHtml(name)}</dt><dd>${escapeHtml(shown)}</dd>`)
          .join("")}</dl></div>`
      );
    })
    .join("");
  const headToHead = view.headToHead
    .map((item) => {
      const total = item.wins[0] + item.wins[1];
      const share = total ? Math.round((item.wins[0] * 100) / total) : 50;
      return (
        `<div class="versus"><span class="who">${escapeHtml(item.players[0])}</span>` +
        `<span class="tally">${item.wins[0]} : ${item.wins[1]}</span>` +
        `<span class="who right">${escapeHtml(item.players[1])}</span>` +
        `<div class="balance"><i style="width:${share}%"></i></div></div>`
      );
    })
    .join("");
  const matches = view.matches
    .map((match) => {
      const players = match.players
        .map((player, index) => {
          const shown = `${player.name || `${t("score_player")} ${index + 1}`} ${historyScore(match, player, index)}`;
          const tag = match.winners.includes(index + 1) ? "b" : "span";
          return `<${tag}>${escapeHtml(shown)}</${tag}>`;
        })
        .join(" · ");
      // Results count legs; a match of sets says so.
      const game = [gameName(t, match.game), match.setsToWin > 1 ? t("score_sets") : ""].filter(Boolean).join(" · ");
      return (
        `<div class="match"><span class="muted">${escapeHtml(date(match.ended))}</span>` +
        `<span class="game">${escapeHtml(game)}</span><span>${players}</span></div>`
      );
    })
    .join("");
  return { players, headToHead, matches };
}

// People ---------------------------------------------------------------------

// Pictures that Home Assistant serves itself or that come from the web; no other schemes.
// Home Assistant's own get its address, as in its own cards: the receiver of Home Assistant
// Cast has an address of its own.
function pictureUrl(value, hass) {
  if (typeof value !== "string" || !/^(\/(?!\/)|https?:\/\/)/i.test(value)) return null;
  return value.startsWith("/") && typeof hass?.hassUrl === "function" ? hass.hassUrl(value) : value;
}

const avatarHtml = (picture) =>
  picture ? `<img class="avatar" src="${escapeHtml(picture)}" alt="" draggable="false">` : "";

// Names are the same player regardless of upper and lower case, as in the integration.
const nameKey = (name) => String(name ?? "").trim().toLowerCase();

// The person each player is linked to, with the picture and whether they are home.
function personLinks(hass, profiles) {
  const links = new Map();
  const players = Array.isArray(profiles?.attributes?.players) ? profiles.attributes.players : [];
  for (const player of players) {
    if (!named(player?.name) || !named(player.person)) continue;
    const state = hass?.states?.[player.person];
    links.set(nameKey(player.name), {
      person: player.person,
      picture: pictureUrl(state?.attributes?.entity_picture, hass),
      home: state?.state === "home",
    });
  }
  return links;
}

// The new game screen ------------------------------------------------------------

const LOBBY_GROUPS = ["x01", "cricket", "party", "training", "more"];
// Limits of the start_game action: four players in X01, the Cricket and the training
// games, and a party of eight in a party game.
const LOBBY_LIMITS = { players: 4, name: 20, legs: 11, sets: 7 };
const PARTY_PLAYERS = 8;
// Every game of the practice select this card knows, for the editor before a board is seen.
const KNOWN_GAMES = ["101", "301", "501", "701", "901", "1001", ...CRICKET_GAMES, ...PARTY_GAMES, ...DRILLS];
// A game that ended opens the new game screen after this pause, so the result shows first.
const LOBBY_DELAY = 8000;
const LOBBY_OPTIONS = ["bull_off", "bull_off_distance", "teams", "three_in_a_bed"];
// The round limit of X01 in the steps the screen offers, 0 for none, up to 50.
const ROUND_STEPS = [0, 5, 10, 15, 20, 30, 50];
// Teams are two pairs of players; start scores of their own go in steps of 100.
const TEAM_SIZE = 4;
// The bot's level: its 3-dart average, set in steps of 10.
const BOT_LEVELS = [20, 120];
const BOT_STEP = 10;
const BOT_DEFAULT = 60;
const START_STEP = 100;
const START_LIMITS = [101, 1001];

function gameGroup(game) {
  if (/^\d+$/.test(game)) return "x01";
  if (game.startsWith("cricket") || CRICKET_GAMES.includes(game)) return "cricket";
  if (PARTY_GAMES.includes(game)) return "party";
  return DRILLS.includes(game) ? "training" : "more";
}

// What a game asks of the players, and whether the X01 rules apply.
function gameRules(game) {
  const group = gameGroup(game);
  const drill = group === "training";
  return {
    x01: group === "x01",
    drill,
    // Four players of X01 or a Cricket game may play as two teams, and the
    // bot plays these games, too.
    teams: group === "x01" || group === "cricket",
    bot: group === "x01" || group === "cricket",
    minPlayers: game === "killer" ? 2 : 1,
    maxPlayers: drill ? 1 : group === "party" ? PARTY_PLAYERS : LOBBY_LIMITS.players,
  };
}

// The games of the practice select by group, as far as the card offers them.
function lobbyGames(options, offered) {
  const wanted = Array.isArray(offered) && offered.length ? new Set(offered.map(String)) : null;
  const games = (Array.isArray(options) ? options : [])
    .map(String)
    .filter((game) => game !== "off" && (!wanted || wanted.has(game)));
  return LOBBY_GROUPS.map((group) => ({ group, games: games.filter((game) => gameGroup(game) === group) })).filter(
    (item) => item.games.length
  );
}

const within = (value, max, fallback) =>
  Number.isInteger(value) ? Math.min(Math.max(value, 1), max) : fallback;

// The choice the new game screen starts from: the game, the players and the
// rules as the board has them now. A name twice becomes a guest.
function lobbyChoice(board, games) {
  const game = games.includes(board.game) ? board.game : games.includes("501") ? "501" : games[0];
  const count = within(board.players, PARTY_PLAYERS, 1);
  const players = [];
  for (let index = 0; index < count; index += 1) {
    const name = String(board.names[index] ?? "").trim();
    players.push(players.some((other) => name && nameKey(other) === nameKey(name)) ? "" : name);
  }
  // Players without any name need not be chosen: the game starts with one of them.
  const chosen = players.some(Boolean) ? players : [];
  const starts = Array.isArray(board.starts) ? board.starts : [];
  const start = (index) => (Number.isInteger(starts[index]) ? starts[index] : 0);
  return {
    game,
    players: chosen,
    // The start score of every player, 0 for the game's; set ones go back with the start.
    starts: chosen.map((_, index) => start(index)),
    handicap: starts.some((value) => Number.isInteger(value) && value > 0),
    teams: board.teams === true,
    legs: within(board.legs, LOBBY_LIMITS.legs, 1),
    sets: within(board.sets, LOBBY_LIMITS.sets, 1),
    in_mode: inModeOf(board),
    out_mode: outModeOf(board),
    bull_mode: board.bull_mode === "50_50" ? "50_50" : "25_50",
    max_rounds: Number.isInteger(board.max_rounds) ? Math.min(Math.max(board.max_rounds, 0), ROUND_STEPS.at(-1)) : 0,
    bull_off: board.bull_off === true,
    bull_off_distance: board.bull_off_distance === true,
    three_in_a_bed: board.three_in_a_bed !== false,
    // The bot's level, where the board has a bot.
    ...(Number.isInteger(board.bot) && board.bot >= BOT_LEVELS[0] ? { bot: Math.min(board.bot, BOT_LEVELS[1]) } : {}),
    // A tournament instead of a match, with the settings of the next tournament.
    tournament: false,
    format: TOURNAMENT_FORMATS.includes(board.format) ? board.format : "round_robin",
    third_place: board.third_place === true,
    random_draw: board.random_draw === true,
    // Groups with knockout: the groups (0 lets the board make them) and how
    // many of each go on, as the board has them; without them, two go on.
    groups: Number.isInteger(board.groups) ? board.groups : 0,
    advance: Number.isInteger(board.advance) ? board.advance : GROUP_LIMITS.through,
    draft: "",
  };
}

// Whether the bot plays the chosen game: in a match of X01 or a Cricket game.
const botSeat = (choice) => Boolean(choice.bot) && !choice.tournament && gameRules(choice.game).bot;

// How many players a choice takes: up to four in a match, eight in a round robin and
// 32 in the other tournaments; the bot takes a seat of its own.
const playerLimit = (choice) =>
  choice.tournament
    ? tournamentPlayers(choice.format)[1]
    : (gameGroup(choice.game) === "party" ? PARTY_PLAYERS : LOBBY_LIMITS.players) - Number(botSeat(choice));

// The choice after a tap: a game, a player added, moved or removed, the format or a rule.
function lobbyChange(choice, action, value) {
  const next = { ...choice, players: [...choice.players], starts: [...(choice.starts ?? [])] };
  const index = Number(value);
  const room = next.players.length < playerLimit(next);
  if (action === "game") {
    next.game = String(value);
  } else if (action === "mode") {
    // Tournament players need a name; a tournament of guests has no table.
    next.tournament = value === "tournament";
    // A tournament plays straight or double in and out: master comes closest to double.
    for (const rule of ["in_mode", "out_mode"]) if (next.tournament && next[rule] === "master") next[rule] = "double";
    // The start scores stay with their players.
    const kept = next.players
      .map((name, index) => [name, next.starts[index] ?? 0])
      .filter(([name]) => name || !next.tournament)
      .slice(0, playerLimit(next));
    next.players = kept.map(([name]) => name);
    next.starts = kept.map(([, start]) => start);
  } else if (action === "format" && TOURNAMENT_FORMATS.includes(value)) {
    next.format = value;
  } else if (action === "groups") {
    // The next number of groups that fits, or the board's choice below the fewest.
    const { groups, options } = groupSetup(next);
    next.groups = options[Math.min(Math.max(options.indexOf(groups) + index, 0), options.length - 1)];
  } else if (action === "advance") {
    const { advance, most } = groupSetup(next);
    next.advance = Math.min(Math.max(advance + index, 1), most);
  } else if (action === "add") {
    const name = String(value ?? "").trim().slice(0, LOBBY_LIMITS.name);
    if (room && name && !next.players.some((player) => nameKey(player) === nameKey(name))) {
      next.players.push(name);
      next.starts.push(0);
      next.draft = "";
    }
  } else if (action === "guest" && room && !next.tournament) {
    next.players.push("");
    next.starts.push(0);
  } else if (action === "remove") {
    next.players.splice(index, 1);
    next.starts.splice(index, 1);
  } else if (action === "up" || action === "down") {
    const other = action === "up" ? index - 1 : index + 1;
    if (other >= 0 && other < next.players.length) {
      [next.players[index], next.players[other]] = [next.players[other], next.players[index]];
      [next.starts[index], next.starts[other]] = [next.starts[other] ?? 0, next.starts[index] ?? 0];
    }
  } else if ((action === "lower" || action === "raise") && gameGroup(next.game) === "x01" && index in next.players) {
    // A start score of the player's own in steps of 100; the game's start is 0.
    const game = Number(next.game);
    const shown = (next.starts[index] || game) + (action === "raise" ? START_STEP : -START_STEP);
    const start = Math.min(Math.max(shown, START_LIMITS[0]), START_LIMITS[1]);
    next.starts[index] = start === game ? 0 : start;
  } else if (action === "legs" || action === "sets") {
    next[action] = within(next[action] + index, LOBBY_LIMITS[action], next[action]);
  } else if ((action === "in_mode" || action === "out_mode") && X01_MODES.includes(value)) {
    next[action] = next.tournament && value === "master" ? next[action] : value;
  } else if (action === "bull_mode" && BULL_MODES.includes(value)) {
    next.bull_mode = value;
  } else if (action === "max_rounds") {
    // The next step up or down; a limit of the board between steps goes to its neighbours.
    const steps = index > 0 ? ROUND_STEPS.filter((step) => step > next.max_rounds) : ROUND_STEPS.filter((step) => step < next.max_rounds);
    next.max_rounds = (index > 0 ? steps[0] : steps.at(-1)) ?? next.max_rounds;
  } else if (action === "toggle" && [...LOBBY_OPTIONS, "third_place", "random_draw"].includes(value)) {
    next[value] = !next[value];
  } else if (action === "bot") {
    // In, out, weaker or stronger; a new bot plays at a medium level.
    const level = { add: BOT_DEFAULT, remove: 0, lower: next.bot - BOT_STEP, raise: next.bot + BOT_STEP }[value];
    const seated = value === "add" ? room && !next.bot : Boolean(next.bot);
    if (seated && level !== undefined) next.bot = level && Math.min(Math.max(level, BOT_LEVELS[0]), BOT_LEVELS[1]);
  }
  return next;
}

// Names to add: players at home first, then everybody else with a profile or a name field.
function lobbySuggestions(profiles, names, links, chosen) {
  const taken = new Set(chosen.map(nameKey));
  const people = new Map();
  const listed = (Array.isArray(profiles?.attributes?.players) ? profiles.attributes.players : []).map(
    (player) => player?.name
  );
  for (const name of [...listed, ...names]) {
    const key = nameKey(name);
    if (!named(name) || !key || taken.has(key) || people.has(key)) continue;
    const link = links.get(key);
    people.set(key, { name: name.trim(), picture: link?.picture ?? null, home: link?.home === true });
  }
  const all = [...people.values()];
  return [...all.filter((person) => person.home), ...all.filter((person) => !person.home)];
}

// The start_game action for a choice; rules the game or the board does not have stay out.
function startGameData(choice, { entry = null, distance = false, bed = false } = {}) {
  const rules = gameRules(choice.game);
  const players = choice.players.slice(0, rules.maxPlayers - Number(botSeat(choice)));
  const data = { game: choice.game, players: players.length ? players : [""] };
  if (entry) data.config_entry_id = entry;
  // Nobody chosen is one player without a name, who may play the bot.
  if (!rules.drill && Math.max(players.length, 1) + Number(botSeat(choice)) > 1) {
    Object.assign(data, { legs: choice.legs, sets: choice.sets, bull_off: choice.bull_off });
    if (distance && choice.bull_off) data.bull_off_distance = choice.bull_off_distance;
  }
  if (rules.x01) {
    Object.assign(data, {
      in_mode: choice.in_mode,
      out_mode: choice.out_mode,
      bull_mode: choice.bull_mode,
      max_rounds: choice.max_rounds,
    });
  }
  // Start scores go with the start once any is set, so the game's start comes back, too.
  const starts = players.map((_, index) => choice.starts?.[index] ?? 0);
  if (rules.x01 && (choice.handicap || starts.some(Boolean))) data.start_scores = starts;
  // The bot plays its games once chosen, and leaves them with level 0.
  const bot = botSeat(choice);
  if (rules.bot && "bot" in choice) data.bot_level = bot ? choice.bot : 0;
  if (rules.teams && players.length + Number(bot) === TEAM_SIZE) data.teams = choice.teams === true;
  if (bed && choice.game === "wild_mouse") data.three_in_a_bed = choice.three_in_a_bed !== false;
  return data;
}

// The rules of every game in a sentence or two; the headings of the games page in
// English and in German link to all of them, where the anchor is not the game's own.
const RULES_DOCS = {
  cut_throat: "cut-throat-cricket",
  doubles: ["doubles-training", "doppeltraining"],
  checkout: "checkout-training",
  bobs_27: "bobs-27",
  checkout_121: "121-checkout",
  singles: "singles-training",
};

// How the chosen game is played, and a link to all its rules; nothing for a game the
// card does not know.
function lobbyRulesHtml(game, ui) {
  const key = gameGroup(game) === "x01" ? "x01" : game;
  if (!Object.hasOwn(TEXT.en, `rules_${key}`)) return "";
  const anchor = RULES_DOCS[key] ?? key.replaceAll("_", "-");
  const [en, de] = Array.isArray(anchor) ? anchor : [anchor, anchor];
  const link = documentation([`games.html#${en}`, `de/games.html#${de}`]);
  return (
    `<div class="lobby-rules"><div class="section-label">${escapeHtml(ui.t("lobby_rules"))}</div>` +
    `<p>${escapeHtml(ui.t(`rules_${key}`))}</p>` +
    `<a class="link" href="${escapeHtml(link)}" target="_blank" rel="noreferrer">` +
    `${escapeHtml(ui.t("lobby_rules_more"))}${cueHtml("details", true)}</a></div>`
  );
}

// The new game screen: the games by group, the players, the format, the rules and the start.
function lobbyHtml(choice, ui) {
  const { t } = ui;
  const rules = gameRules(choice.game);
  const text = (key, values) => escapeHtml(values ? fill(t(key), values) : t(key));
  // Every button keeps the focus through the next render, for keyboards and screen readers.
  const button = (action, value, content, extra = "") =>
    `<button type="button" data-lobby="${action}"${value === undefined ? "" : ` data-value="${escapeHtml(value)}"`}` +
    ` data-focus="${escapeHtml(`${action}:${value ?? ""}`)}"${extra}>${content}</button>`;
  const block = (label, content, kind) =>
    `<div class="lobby-block ${kind}"><div class="section-label">${text(label)}</div>${content}</div>`;
  // A tournament plays X01 and Cricket, as far as the board offers them.
  const offered = choice.tournament ? ui.tournamentGames : ui.games;
  const modes = ui.tournamentGames.length
    ? `<div class="lobby-mode" role="group" aria-label="${text("tournament_mode")}">${["match", "tournament"]
        .map((mode) =>
          button(
            "mode",
            mode,
            text(`tournament_mode_${mode}`),
            ` class="mode" aria-pressed="${choice.tournament === (mode === "tournament")}"`
          )
        )
        .join("")}</div>`
    : "";
  // How the chosen game is played shows right below its group, where the eyes are.
  const games = offered
    .map(
      ({ group, games: list }) =>
        `<div class="lobby-group ${group}"><div class="section-label">${text(`lobby_group_${group}`)}</div>` +
        `<div class="game-grid">${list
          .map((game) =>
            button("game", game, escapeHtml(ui.name(game)), ` class="game" aria-pressed="${game === choice.game}"`)
          )
          .join("")}</div>${list.includes(choice.game) ? lobbyRulesHtml(choice.game, ui) : ""}</div>`
    )
    .join("");
  const shown = (name, index) => name || `${t("score_player")} ${index + 1}`;
  const last = choice.players.length - 1;
  // In X01, every player can start from a score of their own.
  const startHtml = (index, who) => {
    if (!rules.x01) return "";
    const start = choice.starts?.[index] || Number(choice.game);
    return (
      `<span class="lobby-start${choice.starts?.[index] ? " own" : ""}">` +
      button("lower", index, "−", ` aria-label="${text("lobby_start_lower", who)}"${start <= START_LIMITS[0] ? " disabled" : ""}`) +
      `<b>${start}</b>` +
      button("raise", index, "+", ` aria-label="${text("lobby_start_raise", who)}"${start >= START_LIMITS[1] ? " disabled" : ""}`) +
      `</span>`
    );
  };
  const bot = botSeat(choice);
  const seats = choice.tournament ? tournamentPlayers(choice.format)[1] : rules.maxPlayers - Number(bot);
  // The bot sits after the players, at its level.
  const botRow = bot
    ? `<li class="lobby-player bot"><span class="bot-icon" aria-hidden="true">🤖</span>` +
      `<span class="who">${text("bot")}</span><span class="lobby-start own">` +
      button("bot", "lower", "−", ` aria-label="${text("lobby_bot_lower")}"${choice.bot <= BOT_LEVELS[0] ? " disabled" : ""}`) +
      `<b>${choice.bot}</b>` +
      button("bot", "raise", "+", ` aria-label="${text("lobby_bot_raise")}"${choice.bot >= BOT_LEVELS[1] ? " disabled" : ""}`) +
      `</span>${button("bot", "remove", "✕", ` aria-label="${text("lobby_bot_remove")}"`)}</li>`
    : "";
  const players = choice.players
    .map((name, index) => {
      const who = { name: shown(name, index) };
      return (
        `<li class="lobby-player${index >= seats ? " resting" : ""}">${avatarHtml(ui.avatar(name))}` +
        `<span class="who">${escapeHtml(who.name)}</span>${startHtml(index, who)}<span class="lobby-moves">` +
        button("up", index, "▲", ` aria-label="${text("lobby_move_up", who)}"${index === 0 ? " disabled" : ""}`) +
        button("down", index, "▼", ` aria-label="${text("lobby_move_down", who)}"${index === last ? " disabled" : ""}`) +
        button("remove", index, "✕", ` aria-label="${text("lobby_remove", who)}"`) +
        `</span></li>`
      );
    })
    .join("");
  const full = choice.players.length >= playerLimit(choice) ? " disabled" : "";
  const suggestions =
    ui.suggestions
      .map((person) =>
        button(
          "add",
          person.name,
          `${avatarHtml(person.picture)}<span>${escapeHtml(person.name)}</span>` +
            (person.home
              ? `<span class="home" role="img" title="${text("lobby_home")}" aria-label="${text("lobby_home")}">⌂</span>`
              : ""),
          ` class="suggestion${person.home ? " home" : ""}"${full}`
        )
      )
      .join("") +
    (choice.tournament ? "" : button("guest", undefined, `+ ${text("lobby_guest")}`, ` class="suggestion guest"${full}`)) +
    (!choice.tournament && rules.bot && !choice.bot
      ? button("bot", "add", `+ ${text("bot")}`, ` class="suggestion bot"${full}`)
      : "");
  const entry =
    `<div class="name-entry"><input class="lobby-name" type="text" maxlength="${LOBBY_LIMITS.name}" autocomplete="off"` +
    ` enterkeyhint="done" data-focus="lobby-name" placeholder="${text("lobby_name")}"` +
    ` aria-label="${text("lobby_new_player")}"${full}>` +
    `${button("add-name", undefined, text("lobby_add"), full)}</div>`;
  const match = choice.tournament || (!rules.drill && choice.players.length + Number(bot) > 1);
  const stepper = (key, label, { shown = choice[key], lowest = choice[key] <= 1, highest = choice[key] >= LOBBY_LIMITS[key] } = {}) => {
    const name = { name: t(label) };
    return (
      `<div class="stepper"><span class="stepper-label">${text(label)}</span><span class="stepper-controls">` +
      button(key, -1, "−", ` aria-label="${text("lobby_decrease", name)}"${lowest ? " disabled" : ""}`) +
      `<b class="stepper-value">${escapeHtml(shown)}</b>` +
      button(key, 1, "+", ` aria-label="${text("lobby_increase", name)}"${highest ? " disabled" : ""}`) +
      `</span></div>`
    );
  };
  // The groups and how many of each go on, for groups with knockout.
  const grouping = groupSetup(choice);
  const groupSteppers =
    choice.tournament && choice.format === "groups_knockout"
      ? stepper("groups", "tournament_groups", {
          shown: grouping.groups || fill(t("tournament_auto"), { count: grouping.shown }),
          lowest: grouping.groups === 0,
          highest: grouping.groups === grouping.options.at(-1),
        }) +
        stepper("advance", "tournament_advance", {
          shown: grouping.advance,
          lowest: grouping.advance <= 1,
          highest: grouping.advance >= grouping.most,
        })
      : "";
  // The In and Out mode, the bull mode and the round limit of X01; a tournament plays
  // straight or double in and out, the bull 25/50 and no round limit.
  const choices = (key, values, label) =>
    `<div class="choice" role="group" aria-label="${text(label)}"><span class="stepper-label">${text(label)}</span>` +
    `<span class="choice-options">${values
      .map(([value, name]) => button(key, value, name, ` class="option" aria-pressed="${choice[key] === value}"`))
      .join("")}</span></div>`;
  const x01Modes = X01_MODES.filter((mode) => !choice.tournament || mode !== "master").map((mode) => [
    mode,
    text(`lobby_${mode}`),
  ]);
  const limit = { name: t("lobby_max_rounds") };
  const x01 = rules.x01
    ? choices("in_mode", x01Modes, "lobby_in_mode") +
      choices("out_mode", x01Modes, "lobby_out_mode") +
      (choice.tournament
        ? ""
        : choices("bull_mode", BULL_MODES.map((mode) => [mode, mode.replace("_", "/")]), "lobby_bull_mode") +
          `<div class="stepper rounds"><span class="stepper-label">${text("lobby_max_rounds")}</span>` +
          `<span class="stepper-controls">` +
          button("max_rounds", -1, "−", ` aria-label="${text("lobby_decrease", limit)}"${choice.max_rounds ? "" : " disabled"}`) +
          `<b class="stepper-value">${choice.max_rounds || text("lobby_no_limit")}</b>` +
          button(
            "max_rounds",
            1,
            "+",
            ` aria-label="${text("lobby_increase", limit)}"${choice.max_rounds >= ROUND_STEPS.at(-1) ? " disabled" : ""}`
          ) +
          `</span></div>`)
    : "";
  const options = [
    ...(match ? ["bull_off"] : []),
    ...(match && ui.distance && choice.bull_off ? ["bull_off_distance"] : []),
    ...(!choice.tournament && rules.teams && ui.teams && choice.players.length + Number(bot) === TEAM_SIZE
      ? ["teams"]
      : []),
    ...(!choice.tournament && ui.bed && choice.game === "wild_mouse" ? ["three_in_a_bed"] : []),
    ...(choice.tournament && THIRD_PLACE_FORMATS.includes(choice.format) && knockoutPlayers(choice) >= THIRD_PLACE_PLAYERS
      ? ["third_place"]
      : []),
    ...(choice.tournament ? ["random_draw"] : []),
  ];
  const formats = choice.tournament
    ? `<div class="formats">${TOURNAMENT_FORMATS.map((format) =>
        button("format", format, text(`tournament_${format}`), ` class="option" aria-pressed="${choice.format === format}"`)
      ).join("")}</div>`
    : "";
  const blocked = lobbyBlocked(choice);
  // The screen's live region reads the hints out; here they are shown.
  const hints = lobbyHints(choice, ui)
    .map((hint) => `<span class="lobby-hint">${escapeHtml(hint)}</span>`)
    .join("");
  const actions =
    `<div class="lobby-actions">${hints}` +
    (ui.running || ui.tournamentRunning
      ? button(
          "end",
          undefined,
          text(ui.confirmEnd ? "confirm" : ui.tournamentRunning ? "tournament_stop" : "lobby_end"),
          ` class="secondary${ui.confirmEnd ? " confirm" : ""}"`
        )
      : "") +
    button("close", undefined, text("lobby_close"), ' class="secondary"') +
    button(
      "start",
      undefined,
      ui.confirmStart
        ? text("confirm")
        : choice.tournament
          ? text("tournament_start")
          : text("lobby_start", { game: ui.name(choice.game) }),
      ` class="start${ui.confirmStart ? " confirm" : ""}"${blocked ? " disabled" : ""}`
    ) +
    `</div>`;
  return (
    `<section class="lobby" aria-label="${text("lobby_label")}">` +
    `<div class="lobby-games">${modes}${games}</div>` +
    `<div class="lobby-setup">${block(
      "lobby_players",
      (players || botRow
        ? `<ol class="lobby-players">${players}${botRow}</ol>`
        : `<p class="lobby-nobody muted">${text("lobby_nobody")}</p>`) +
        `<div class="suggestions">${suggestions}</div>${entry}`,
      "players-block"
    )}` +
    (match
      ? block(
          "lobby_format",
          `${formats}<div class="steppers">${stepper("legs", "lobby_legs")}${stepper("sets", "lobby_sets")}${groupSteppers}</div>`,
          "format"
        )
      : "") +
    (options.length || x01
      ? block(
          "lobby_options",
          x01 +
            options
              .map((option) =>
                button("toggle", option, text(option), ` class="option" aria-pressed="${choice[option]}"`)
              )
              .join(""),
          "options"
        )
      : "") +
    `</div>${actions}</section>`
  );
}

// Whether the start waits for players: a tournament needs the players of its format,
// Killer two; nobody chosen is one player without a name.
const lobbyBlocked = (choice) => {
  if (!choice.tournament) return Math.max(choice.players.length, 1) < gameRules(choice.game).minPlayers;
  const [fewest, most] = tournamentPlayers(choice.format);
  return choice.players.length < fewest || choice.players.length > most;
};

// What holds the start back or what it does besides: too few players, a training
// game that one player plays, or detection that the start switches on.
function lobbyHints(choice, ui) {
  const { t } = ui;
  const hints = [];
  const rules = gameRules(choice.game);
  // The seats of a match: the bot takes one; players beyond them sit out.
  const seats = rules.maxPlayers - Number(botSeat(choice));
  const limit = playerLimit(choice);
  if (lobbyBlocked(choice)) {
    const [min, max] = tournamentPlayers(choice.format);
    hints.push(choice.tournament ? fill(t("tournament_needs_players"), { min, max }) : t("needs_players"));
  }
  else if (!choice.tournament && rules.drill && choice.players.length > 1) {
    hints.push(fill(t("lobby_one_player"), { name: choice.players[0] || `${t("score_player")} 1` }));
  } else if (!choice.tournament && choice.players.length > seats) {
    hints.push(fill(t("lobby_resting"), { game: ui.name(choice.game), count: seats }));
  } else if (choice.players.length >= limit && ui.suggestions.length) {
    // A full game takes no more of the suggestions, which fade.
    hints.push(fill(t("lobby_full"), { count: limit }));
  }
  if (choice.tournament && ui.tournamentRunning) hints.push(t("lobby_tournament_running"));
  if (ui.detectionOff) hints.push(t("lobby_detection"));
  return hints;
}

// Correcting and entering darts ---------------------------------------------------

// The bed a pad button enters: S20, D16, T19, 25, BULL or MISS.
const padBed = (multiplier, number) => `${"SDT"[multiplier - 1]}${number}`;
// The pad's board: the dartboard with its surround, in millimetres.
const PAD_VIEW = 2 * (R.board + 5);

// On a small screen the board to tap opens this much larger around where the board
// saw the dart being corrected; two fingers zoom up to the most. The loupe under a
// finger shows the board that much larger again.
const PAD_ZOOM = 2.5;
const PAD_ZOOM_MOST = 5;
const LOUPE_ZOOM = 2.5;
// A card narrower than this, or a screen lower, as a phone on its side, is a small screen.
const PAD_SMALL = 600;
// Building blocks: the icons of the cards, lines in the colour of their text.
const ICON_PATHS = {
  edit: "M4 20l1.2-4.8L15.6 4.8a2 2 0 0 1 2.8 0l.8.8a2 2 0 0 1 0 2.8L8.8 18.8z M13.8 6.6l3.6 3.6",
  details: "M9 5l7 7-7 7",
  expand: "M6 9l6 6 6-6",
  undo: "M9 14L4 9l5-5 M4 9h10.5a5.5 5.5 0 0 1 0 11H11",
};
// A cue says what a tap does: a pencil edits, an arrow opens the details, a curved arrow
// undoes. At the top right of a tile, or inline after the words of a control that looks
// like text.
const cueHtml = (kind, inline = false) =>
  `<svg class="cue ${kind}${inline ? " inline" : ""}" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICON_PATHS[kind]}"/></svg>`;
const EDIT_ICON = cueHtml("edit");
const UNDO_CUE = cueHtml("undo");
// The arrow of the undo, apart from its words, which screen readers say alone.
const UNDO_ICON = `<span class="undo-icon" aria-hidden="true">↶</span>`;
// The views of the keypad as icons, which a narrow pad shows instead of their names: the
// keys as the dots of a keypad, the board as its rings and the score of a visit as a sum.
const VIEW_ICONS = {
  keys:
    `<svg viewBox="0 0 24 24" aria-hidden="true"><g class="dots">` +
    [6, 12, 18].flatMap((y) => [6, 12, 18].map((x) => `<circle cx="${x}" cy="${y}" r="2"/>`)).join("") +
    `</g></svg>`,
  board: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><circle class="dots" cx="12" cy="12" r="1.3"/></svg>`,
  score: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.5 7V4.5h-11l6.5 7.5-6.5 7.5h11V17"/></svg>`,
};

// The part of the pad's board in sight: all of it, or, zoomed in with `zoom` as
// { scale, x, y }, the square of that scale around x and y in millimetres of the
// drawing (y points down), kept on the board.
function padViewBox(zoom) {
  const half = PAD_VIEW / 2;
  if (!(zoom?.scale > 1)) return { x: -half, y: -half, size: PAD_VIEW };
  const size = PAD_VIEW / Math.min(zoom.scale, PAD_ZOOM_MOST);
  const middle = (value) => Math.min(Math.max(Number.isFinite(value) ? value : 0, size / 2 - half), half - size / 2);
  return { x: middle(zoom.x) - size / 2, y: middle(zoom.y) - size / 2, size };
}
const viewBoxText = (view) => [view.x, view.y, view.size, view.size].map(fmt).join(" ");

// Where a point of the screen lies on the drawing of the pad's board, in millimetres.
// The board is drawn square in the middle of its element; a board that is not laid
// out has no point.
function boardPoint(svg, event, view) {
  const rect = svg.getBoundingClientRect();
  const scale = Math.min(rect.width, rect.height) / view.size;
  if (!(scale > 0)) return null;
  return [
    view.x + view.size / 2 + (event.clientX - rect.left - rect.width / 2) / scale,
    view.y + view.size / 2 + (event.clientY - rect.top - rect.height / 2) / scale,
  ];
}

// Where a tap on the pad's board lands, as the board reports positions: 1 is the
// outer edge of the double ring and y points to the 20.
function boardSpot(svg, event, view = padViewBox(null)) {
  const point = boardPoint(svg, event, view);
  if (!point) return null;
  const round = (value) => Math.round(value * 1000) / 1000 || 0;
  return [round(point[0] / NORM), round(-point[1] / NORM)];
}

// The pad's board: a tap says where the dart is, and the bed follows from it. The
// darts of the visit show where they are; the dart being corrected, where the board
// saw it.
function padBoardHtml(pad, ui) {
  const { t } = ui;
  const view = padViewBox(pad.zoom);
  // Pins keep their size on the screen when the board is zoomed in.
  const size = view.size / PAD_VIEW;
  const pins = pad.pins
    .map(({ x, y, seen }) => {
      const at = `cx="${fmt(x * NORM)}" cy="${fmt(-y * NORM)}"`;
      return seen
        ? `<circle class="spot seen" ${at} r="${fmt(13 * size)}"><title>${escapeHtml(t("pad_seen"))}</title></circle>`
        : `<circle class="spot" ${at} r="${fmt(8 * size)}"/>`;
    })
    .join("");
  return (
    `<svg class="pad-board${pad.disabled ? " disabled" : ""}"${pad.disabled ? "" : ` data-pad="spot"`}` +
    ` viewBox="${viewBoxText(view)}" role="img" aria-label="${escapeHtml(t("pad_spot"))}">` +
    `<g class="face">${boardSvg("classic")}</g><g class="numbers">${numbersSvg("classic")}</g>${pins}</svg>` +
    `<div class="pad-hint" aria-hidden="true">${escapeHtml(t("pad_spot_hint"))}</div>`
  );
}

// Score of a visit -------------------------------------------------------------------

// The beds a dart of a visit entered as its score can hit, as the integration makes its
// darts up: their points and whether they are a double or a treble. A miss, the bulls,
// and the single, double and treble of every number; with the bull mode 50/50, the
// outer bull scores what the bullseye does, which stands for both.
const SCORE_BEDS = [
  { points: 0, double: false, treble: false },
  { points: 25, double: false, treble: false, outer: true },
  { points: 50, double: true, treble: false },
  ...[...Array(20)].flatMap((_, index) =>
    [1, 2, 3].map((times) => ({ points: (index + 1) * times, double: times === 2, treble: times === 3 }))
  ),
];
const bedsByPoints = (beds) =>
  beds.reduce((found, bed) => found.set(bed.points, [...(found.get(bed.points) ?? []), bed]), new Map());
const SCORE_BULLS = {
  "25_50": { beds: SCORE_BEDS, byPoints: bedsByPoints(SCORE_BEDS) },
  "50_50": {
    beds: SCORE_BEDS.filter((bed) => !bed.outer),
    byPoints: bedsByPoints(SCORE_BEDS.filter((bed) => !bed.outer)),
  },
};

// Whether a dart opens or ends a leg with this In or Out mode: any dart straight, a
// double or the bullseye with double, and a treble as well with master.
const fitsMode = (dart, mode) => mode === "straight" || dart.double || (mode === "master" && dart.treble);

// How the darts of a visit end from what the player had, as the integration counts them:
// "bust" at a dart that goes below zero, leaves 1 with double or master out or reaches
// zero without the dart the Out mode needs, "won" at zero, and null where they leave the
// rest.
function visitOutcome(from, darts, out) {
  let left = from;
  for (const dart of darts) {
    left -= dart.points;
    if (left < 0 || (out !== "straight" && left === 1) || (left === 0 && !fitsMode(dart, out))) return "bust";
    if (left === 0) return "won";
  }
  return null;
}

// Whether some visit of `count` darts scores `points` and passes `test`, which tells by
// its darts, with the beds of the bull mode.
function someVisit(entry, count, points, test, chosen = []) {
  const { beds, byPoints } = SCORE_BULLS[entry.bull === "50_50" ? "50_50" : "25_50"];
  if (chosen.length === count - 1) return (byPoints.get(points) ?? []).some((dart) => test([...chosen, dart]));
  return beds.some((dart) => dart.points <= points && someVisit(entry, count, points - dart.points, test, [...chosen, dart]));
}

// Whether these darts can open the leg: while it waits for a double, or a double or a
// treble with master in, the first that scores is one.
function opens(entry, darts) {
  const first = darts.find((dart) => dart.points);
  return !entry.opening || !first || fitsMode(first, entry.opening);
}

// The fewest darts that check out what the player has left, or null where no visit can.
function checkoutDarts(entry) {
  const wins = (darts) => opens(entry, darts) && visitOutcome(entry.from, darts, entry.out) === "won";
  return [1, 2, 3].find((count) => someVisit(entry, count, entry.from, wins)) ?? null;
}

// Whether a visit scores this from where the player stands, as the integration takes it:
// no three darts make 163, 166, 169, 172, 173, 175, 176, 178 or 179; while the leg waits
// for a double, the first dart that scores is one, so 1 or 180 don't open it; and more than
// is left busts only where no dart checks out on the way, as the first treble 20 of 180
// from 60 does without double out.
function scorable(entry, points) {
  return someVisit(
    entry,
    3,
    points,
    (darts) => opens(entry, darts) && (points === entry.from || visitOutcome(entry.from, darts, entry.out) !== "won")
  );
}

// Whether the score typed can go in: OK and Enter wait for one that a visit scores.
const scoreReady = (entry, typed) => typed !== "" && scorable(entry, Number(typed));

// The keypad takes the score of a visit in an X01 leg being played: what the player had
// before the visit, the Out mode, the In mode the leg waits for to open, if any, and the
// bull mode.
function scoreEntry(view) {
  const practice = view.mode === "x01" ? view.practice : null;
  if (!practice || practice.winner !== null) return null;
  return {
    from: practice.from,
    out: practice.outMode,
    opening: practice.opened ? null : practice.inMode,
    bull: practice.bullMode,
  };
}

// What a score says before it goes in: what it leaves, a checkout or a bust, or that no
// visit scores it. What the player has left busts where no checkout exists, such as 159
// with double out.
function scoreHint(entry, points, t) {
  if (!scorable(entry, points)) return fill(t("score_impossible"), { score: points });
  if (points === entry.from && checkoutDarts(entry) !== null) return t("checkout");
  const left = entry.from - points;
  if (left < 0 || (entry.out !== "straight" && left <= 1)) return t("bust");
  return fill(t("setup_leave"), { leave: left });
}

const counting = (from, to) => [...Array(to - from + 1)].map((_, index) => from + index);

// What a score takes besides itself: the darts of a checkout and the darts at a double,
// asked where they can differ. With the answers so far, the next question, or the data
// of homedarts.enter_visit once nothing is left to ask. A checkout goes in as one, so
// that the integration refuses it rather than book a bust where it can't check out.
function scoreAnswer(entry, points, answers = {}) {
  const data = { score: points };
  const least = points === entry.from ? checkoutDarts(entry) : null;
  if (least !== null) {
    data.checkout = true;
    if (answers.darts === undefined && least < 3) return { ask: "darts", choices: counting(least, 3) };
    data.darts = answers.darts ?? 3;
    // Darts at a double count with double out alone.
    if (entry.out !== "double") return { data };
    if (answers.doubles === undefined && data.darts > 1) return { ask: "doubles", choices: counting(1, data.darts) };
    data.darts_at_double = answers.doubles ?? 1;
    return { data };
  }
  // A visit that left a double in reach may have thrown at it; what is left where no double
  // finishes it, such as 159, goes in as it is and busts.
  if (entry.out === "double" && entry.from - points <= 50 && points !== entry.from) {
    if (answers.doubles === undefined) return { ask: "doubles", choices: counting(0, 3) };
    data.darts_at_double = answers.doubles;
  }
  return { data };
}

// What the score view does, and Cancel, after which the pad keeps the keys of a keyboard.
const SCORE_ACTIONS = ["score", "digit", "erase", "enter", "answer", "cancel"];

// The score view of the keypad, in the pad's head the score typed so far with what it
// leaves, or the question after it; below, the digits in four rows of three, as tall as
// the numbers of the keys, or the answers and Cancel in the same four rows, so the pad
// keeps its height whatever it shows.
function padScoreHtml(pad, ui, button) {
  const { t } = ui;
  const score = pad.score;
  if (score.ask) {
    const span = 12 / score.ask.choices.length;
    const answers = score.ask.choices
      .map((count) => button("answer", count, String(count), ` class="digit answer" style="--span:${span}"`))
      .join("");
    return (
      `<div class="pad-score">${answers}` +
      `${button("cancel", undefined, escapeHtml(t("pad_cancel")), ` class="secondary ask-cancel" style="--span:12"`)}</div>`
    );
  }
  const digit = (value) => button("digit", value, value, ` class="digit"`);
  const keys = [
    ..."123456789".split("").map(digit),
    button("erase", undefined, "⌫", ` class="digit" aria-label="${escapeHtml(t("score_erase"))}"`, !score.typed),
    digit("0"),
    button("enter", undefined, escapeHtml(t("score_enter")), ` class="digit enter"`, !score.ready),
  ].join("");
  return `<div class="pad-score">${keys}</div>`;
}

// What the head of the score view says: the score typed and what it leaves, or the
// question after it.
function padScoreLine(pad, ui) {
  const { t } = ui;
  const score = pad.score;
  if (score.ask) {
    return `<span class="score-line ask">${escapeHtml(t(score.ask.ask === "darts" ? "score_darts" : "score_doubles"))}</span>`;
  }
  return (
    `<span class="score-line"><span class="typed">${escapeHtml(score.typed || "–")}</span>` +
    `<span class="muted">${escapeHtml(score.hint)}</span></span>`
  );
}

// The pad of the scoreboard: single, double or treble, the numbers, the bulls
// and a miss. It corrects a dart of the visit, or enters darts by hand with
// the next player and, on the live card, the undo of the last visit, which need a
// second tap. The undo key keeps its place while there is nothing to undo.
function padHtml(pad, ui) {
  const { t } = ui;
  const button = (action, value, content, extra = "", off = false) =>
    `<button type="button" data-pad="${action}"${value === undefined ? "" : ` data-value="${escapeHtml(value)}"`}` +
    ` data-focus="${escapeHtml(`${action}:${value ?? ""}`)}"` +
    `${(pad.disabled && action !== "cancel") || off ? " disabled" : ""}${extra}>${content}</button>`;
  const title = pad.dart ? fill(t("correct_title"), { dart: pad.dart }) : pad.score ? t("score_title") : t("enter_title");
  const multipliers = [
    [1, "pad_single"],
    [2, "pad_double"],
    [3, "pad_treble"],
  ]
    .map(([multiplier, name]) =>
      button(
        "multiplier",
        multiplier,
        "SDT"[multiplier - 1],
        ` class="multiplier" aria-pressed="${pad.multiplier === multiplier}" aria-label="${escapeHtml(t(name))}"`
      )
    )
    .join("");
  const numbers = BOARD_NUMBERS.map((number) =>
    button("bed", padBed(pad.multiplier, number), String(number), ` class="pad-number"`)
  ).join("");
  const bulls = [
    button("bed", "25", "25", ` class="bull"`),
    button("bed", "BULL", "Bull", ` class="bull"`),
    button("bed", "MISS", escapeHtml(t("miss")), ` class="miss"`),
  ].join("");
  const confirm = (action, key) => escapeHtml(t(pad.confirm === action ? "confirm" : key));
  const confirming = (action) => (pad.confirm === action ? " confirm" : "");
  const actions = pad.dart
    ? button("cancel", undefined, escapeHtml(t("pad_cancel")), ` class="secondary"`)
    : button("next", undefined, confirm("next", "next_player"), ` class="secondary${confirming("next")}"`) +
      (pad.undo === undefined
        ? ""
        : button(
            "undo",
            undefined,
            `${UNDO_ICON} ${confirm("undo", "undo_visit")}`,
            ` class="secondary${confirming("undo")}" title="${escapeHtml(t("undo_hint"))}"`,
            !pad.undo
          ));
  // The board instead of the keys, for the spot where the dart is.
  // The keys or the board, one of the two, as the segmented control of every card.
  // In an X01 leg, the keypad also takes the score of a visit.
  // A narrow pad shows the views as icons, so they keep a line with S, D and T.
  const viewButton = (action, label, pressed) => {
    const name = escapeHtml(t(label));
    return button(
      action,
      undefined,
      `${VIEW_ICONS[action]}<span class="view-name">${name}</span>`,
      ` aria-pressed="${pressed}" aria-label="${name}"`
    );
  };
  const view =
    `<div class="segmented view" role="group" aria-label="${escapeHtml(t("pad_view"))}">` +
    viewButton("keys", "pad_keys", pad.board !== true && !pad.score) +
    viewButton("board", "pad_board", pad.board === true) +
    (pad.scoreable ? viewButton("score", "pad_score", Boolean(pad.score)) : "") +
    `</div>`;
  // On the board, a switch between the whole board and its part around the dart: a
  // magnifier with a plus zooms in, one with a minus shows all of it.
  const zoomed = padViewBox(pad.zoom).size < PAD_VIEW;
  const magnifier =
    `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6"/>` +
    `<path d="M14.5 14.5 20 20M7 10h6${zoomed ? "" : "M10 7v6"}"/></svg>`;
  const zoom = pad.board
    ? button(
        "zoom",
        undefined,
        magnifier,
        ` class="zoom" aria-pressed="${zoomed}" aria-label="${escapeHtml(t("pad_zoom"))}"` +
          ` title="${escapeHtml(t(zoomed ? "pad_whole" : "pad_zoom"))}"`
      )
    : "";
  const body = pad.board
    ? padBoardHtml(pad, ui)
    : pad.score
      ? padScoreHtml(pad, ui, button)
      : `<div class="pad-numbers">${numbers}</div>`;
  const keys = !pad.board && !pad.score;
  // The pad itself takes the focus where a key that had it goes away, so that the keys
  // of a keyboard keep reaching it; the Tab key passes it by.
  return (
    `<section class="pad${pad.dart ? " correcting" : ""}${pad.board ? " on-board" : ""}${pad.score ? " on-score" : ""}"` +
    ` tabindex="-1" data-focus="pad" aria-label="${escapeHtml(title)}">` +
    `<div class="pad-head"><span class="section-label">${escapeHtml(title)}</span>` +
    `${keys ? multipliers : ""}${pad.score ? padScoreLine(pad, ui) : ""}${zoom}${view}</div>` +
    (pad.disabled ? `<p class="pad-hint pad-wait">${escapeHtml(t("pad_bot_wait"))}</p>` : "") +
    `${body}<div class="pad-extra">${keys ? bulls : ""}${actions}</div></section>`
  );
}

// While the bot is at the board, its darts count; nobody enters or corrects any.
function botAtBoard(view) {
  const game = view.practice ?? view.cricket ?? view.party ?? null;
  const thrower = view.bullOff?.throws.find((item) => item.player === view.bullOff.player);
  return Boolean((game ? upScore(game) : thrower)?.bot);
}

// Idle mode ----------------------------------------------------------------------

// The tournament first: while one is on, it matters most.
const IDLE_PANELS = ["tournament", "leaderboard", "records", "today", "last_match", "clock"];

// Whether a game is on: none without a game, over once a match or a training game is decided.
function gameState(view) {
  if (view.mode === "idle") return "none";
  if (view.mode === "drill") return view.drill.finished ? "over" : "running";
  if (view.mode === "bulloff") return "running";
  const game = view.practice ?? view.cricket ?? view.party;
  return game.winner === null ? "running" : "over";
}

// The best players by 3-dart average, then by legs won.
function leaderboardHtml(data, ui) {
  const ranked = data.players
    .filter((player) => player.legsPlayed > 0)
    .sort(
      (a, b) => (b.average ?? -1) - (a.average ?? -1) || b.legsWon - a.legsWon || a.name.localeCompare(b.name)
    )
    .slice(0, 5);
  if (!ranked.length) return "";
  return `<ol class="ranking">${ranked
    .map(
      (player, index) =>
        `<li><span class="rank">${index + 1}</span>${avatarHtml(ui.avatar(player.name))}` +
        `<span class="who">${escapeHtml(player.name)}</span>` +
        `<span class="score">${player.average === null ? "–" : `Ø ${escapeHtml(ui.format(player.average, 1))}`}</span>` +
        `<span class="muted">${escapeHtml(
          fill(ui.t("idle_legs"), { won: player.legsWon, played: player.legsPlayed })
        )}</span></li>`
    )
    .join("")}</ol>`;
}

function recordsHtml(data, ui) {
  return data.records.length ? `<dl class="records">${bestsHtml(data.records, ui)}</dl>` : "";
}

// Today's darts towards the daily goal, and the session.
function todayHtml(data, ui) {
  const { t, format } = ui;
  const { stats } = data;
  if (stats.today === null) return "";
  const goal = stats.goal > 0;
  const share = goal ? Math.min(100, Math.round((stats.today * 100) / stats.goal)) : 0;
  const facts = [
    { value: format(stats.average, 1), name: t("average") },
    { value: format(stats.highest, 0), name: t("highest") },
    { value: format(stats.max, 0), name: t("max") },
    ...(stats.streak > 0
      ? [{ value: format(stats.streak, 0), name: t(stats.streak === 1 ? "streak_day" : "streak_days") }]
      : []),
  ];
  return (
    `<div class="single"><div class="big">${escapeHtml(format(stats.today, 0))}</div>` +
    `<div class="label">${escapeHtml(goal ? fill(t("idle_goal"), { goal: format(stats.goal, 0) }) : t("darts_today"))}</div>` +
    (goal ? `<div class="goal${share >= 100 ? " reached" : ""}"><i style="width:${share}%"></i></div>` : "") +
    `${factsBlock(factsHtml(facts))}</div>`
  );
}

// The last match of several players: the game, when, and everybody's result.
function lastMatchHtml(data, ui) {
  const { t, format } = ui;
  const match = data.match;
  if (!match) return "";
  const rows = match.players
    .map((player, index) => {
      const name = named(player.name) ?? `${t("score_player")} ${index + 1}`;
      // Both partners of the team that won, as in the players card.
      const winner = match.winners.includes(index + 1);
      const numbers = [
        // Legs, or sets in a match of sets, as in the players card.
        String(historyScore(match, player, index)),
        finite(player.average) === null ? "" : `Ø ${format(player.average, 1)}`,
        finite(player.mpr) === null ? "" : `${t("cricket_mpr")} ${format(player.mpr, 2)}`,
      ];
      return (
        `<li class="${winner ? "winner" : ""}">${avatarHtml(ui.avatar(name))}<span class="who">${escapeHtml(name)}</span>` +
        `<span class="score">${escapeHtml(numbers[0])}</span>` +
        `<span class="muted">${escapeHtml(numbers.slice(1).filter(Boolean).join(" · "))}</span>` +
        `${winner ? '<span class="trophy" aria-hidden="true">🏆</span>' : ""}</li>`
      );
    })
    .join("");
  return (
    `<div class="match-head">${escapeHtml(`${gameName(t, match.game)} · ${ui.date(match.ended)}`)}</div>` +
    `<ol class="ranking result">${rows}</ol>`
  );
}

function clockHtml(data, ui) {
  const shown = ui.clock(data.now);
  return (
    `<div class="single clock"><div class="big">${escapeHtml(shown.time)}</div>` +
    `${factsBlock(`<span>${escapeHtml(shown.day)}</span>`)}</div>`
  );
}

const IDLE_RENDER = {
  tournament: tournamentPanelHtml,
  leaderboard: leaderboardHtml,
  records: recordsHtml,
  today: todayHtml,
  last_match: lastMatchHtml,
  clock: clockHtml,
};

// The panels with something to show, in the order of the card's list.
function idlePanels(wanted, data, ui) {
  const list = Array.isArray(wanted) && wanted.length ? [...new Set(wanted)] : IDLE_PANELS;
  return list
    .filter((panel) => IDLE_PANELS.includes(panel))
    .map((panel) => ({ panel, html: IDLE_RENDER[panel](data, ui) }))
    .filter((panel) => panel.html);
}

// The time and the day as a clock shows them, in the server's or the browser's time zone.
function formatClock(hass, moment) {
  const locale = hass?.locale || {};
  const language = locale.language || hass?.language;
  const twelve = amPm(locale, language);
  const server = hass?.config?.time_zone;
  const zone = server && locale.time_zone !== "local" ? { timeZone: server } : {};
  return {
    time: formatter("date", language, {
      hour: twelve ? "numeric" : "2-digit",
      minute: "2-digit",
      hourCycle: twelve ? "h12" : "h23",
      ...zone,
    }).format(moment),
    day: formatter("date", language, { weekday: "long", day: "numeric", month: "long", ...zone }).format(moment),
  };
}

// Tournaments ----------------------------------------------------------------------

const TOURNAMENT_STATUS = ["playing", "waiting", "finished"];
const TOURNAMENT_FORMATS = ["round_robin", "knockout", "double_knockout", "groups_knockout"];
// The players of every format of the start_tournament action, at least and at most.
const TOURNAMENT_PLAYERS = {
  round_robin: [3, 8],
  knockout: [3, 32],
  double_knockout: [3, 32],
  groups_knockout: [6, 32],
};
const tournamentPlayers = (format) => TOURNAMENT_PLAYERS[format];
// Two to eight groups of three to eight players, of which one to four go on into
// the knockout; without a number, groups of about four players and two go on.
const GROUP_LIMITS = { groups: [2, 8], size: [3, 8], advance: 4, about: 4, through: 2 };
// A knockout has a match for third place from four players, also after the groups.
const THIRD_PLACE_PLAYERS = 4;
const THIRD_PLACE_FORMATS = ["knockout", "groups_knockout"];

// Whether this many players make that many groups of three to eight players, each
// with more players than go on.
function groupsFit(count, groups, advance = 1) {
  const smallest = Math.floor(count / groups);
  return (
    groups >= GROUP_LIMITS.groups[0] &&
    groups <= GROUP_LIMITS.groups[1] &&
    smallest >= GROUP_LIMITS.size[0] &&
    Math.ceil(count / groups) <= GROUP_LIMITS.size[1] &&
    advance < smallest
  );
}

// The groups of the new game screen for its players: a number that no longer fits
// leaves it to the board (0, about four players a group), and fewer players go on
// where the groups are small.
function groupSetup(choice) {
  const count = choice.players.length;
  const options = Array.from({ length: GROUP_LIMITS.groups[1] - 1 }, (_, index) => index + 2).filter((groups) =>
    groupsFit(count, groups)
  );
  const groups = options.includes(choice.groups) ? choice.groups : 0;
  const shown = groups || Math.min(Math.max(Math.floor(count / GROUP_LIMITS.about), 2), GROUP_LIMITS.groups[1]);
  const most = Math.max(Math.min(Math.floor(count / shown) - 1, GROUP_LIMITS.advance), 1);
  const advance = Math.min(Math.max(choice.advance ?? GROUP_LIMITS.through, 1), most);
  return { groups, shown, options: [0, ...options], advance, most };
}

// The players of the knockout: all of them, or those who go on after the groups.
const knockoutPlayers = (choice) => {
  if (choice.format !== "groups_knockout") return choice.players.length;
  const { shown, advance } = groupSetup(choice);
  return shown * advance;
};

// A match of the tournament sensor: its players, the winner and the result.
function tournamentMatch(item) {
  if (!item || typeof item !== "object") return null;
  const pair = (list, read) => [0, 1].map((index) => read(Array.isArray(list) ? list[index] : undefined));
  return {
    match: finite(item.match),
    round: finite(item.round) ?? 1,
    stage: named(item.stage) ?? "",
    group: named(item.group),
    players: pair(item.players, named),
    winner: named(item.winner),
    bye: item.bye === true,
    legs: pair(item.legs, (value) => finite(value) ?? 0),
    sets: pair(item.sets, (value) => finite(value) ?? 0),
    ended: named(item.ended),
  };
}

// The tournament being played or just finished, from its sensor; null without one.
function tournamentView(state) {
  const attributes = state?.attributes ?? {};
  if (!usable(state) || !TOURNAMENT_STATUS.includes(attributes.status)) return null;
  const list = (value) => (Array.isArray(value) ? value : []);
  const game = Number.isInteger(attributes.game) ? attributes.game : named(attributes.game);
  const nextAt = Date.parse(attributes.next_at);
  const endsAt = Date.parse(attributes.ends_at);
  const rows = (value) =>
    list(value)
      .filter((row) => named(row?.name))
      .map((row) => ({
        position: finite(row.position) ?? 0,
        name: row.name,
        played: finite(row.played) ?? 0,
        won: finite(row.won) ?? 0,
        lost: finite(row.lost) ?? 0,
        legsFor: finite(row.legs_for) ?? 0,
        legsAgainst: finite(row.legs_against) ?? 0,
        difference: finite(row.leg_difference) ?? 0,
        points: finite(row.points) ?? 0,
        average: finite(row.average ?? row.mpr),
      }));
  const rounds = (value) =>
    list(value)
      .filter((round) => named(round?.stage))
      .map((round) => ({ stage: round.stage, matches: list(round.matches).map(tournamentMatch).filter(Boolean) }));
  return {
    stage: state.state,
    status: attributes.status,
    format: TOURNAMENT_FORMATS.includes(attributes.format) ? attributes.format : "round_robin",
    game,
    // Cricket ranks by marks per round, X01 by the 3-dart average.
    mpr: typeof game === "string",
    setsToWin: finite(attributes.sets_to_win) ?? 1,
    played: finite(attributes.matches_played) ?? 0,
    total: finite(attributes.matches_total) ?? 0,
    current: tournamentMatch(attributes.current),
    next: tournamentMatch(attributes.next),
    // False while the board waits for a match another board still plays.
    nextReady: attributes.next_ready !== false,
    last: tournamentMatch(attributes.last_result),
    nextAt: Number.isFinite(nextAt) ? nextAt : null,
    pause: finite(attributes.pause) ?? 0,
    summary: finite(attributes.summary) ?? 8,
    winner: named(attributes.winner),
    started: named(attributes.started),
    standings: rows(attributes.standings),
    // The tables of the groups, and how many of each go on into the knockout.
    groups: list(attributes.groups)
      .filter((group) => named(group?.group))
      .map((group) => ({ name: group.group, standings: rows(group.standings) })),
    advance: finite(attributes.advance) ?? 0,
    bracket: rounds(attributes.bracket),
    // The losers' bracket of a double elimination.
    losers: rounds(attributes.losers_bracket),
    // A tournament on several boards: the board of the sensor, from 1, and every
    // board with its match, or when its next match starts.
    board: finite(attributes.board),
    boards: list(attributes.boards)
      .filter((item) => named(item?.name))
      .map((item) => {
        const at = Date.parse(item.next_at);
        return {
          board: finite(item.board),
          name: item.name,
          match: finite(item.match),
          players: list(item.players).map(named).filter(Boolean),
          nextAt: Number.isFinite(at) ? at : null,
        };
      }),
    // When the tournament is expected to end.
    endsAt: Number.isFinite(endsAt) ? endsAt : null,
  };
}

// The numbered rounds: of a round robin or a group, and of the two brackets of a
// double elimination.
const NUMBERED_ROUNDS = ["round", "winners_round", "losers_round"];

// "Round 2", "Losers round 3", or a knockout stage such as "Semi-final".
function stageName(t, stage) {
  const [, kind, round] = /^(\w+?)_(\d+)$/.exec(stage) ?? [];
  return NUMBERED_ROUNDS.includes(kind) ? fill(t(`tournament_${kind}`), { round }) : t(`tournament_stage_${stage}`);
}

// The stage of a match, with its group: "Group B · Round 2".
const matchStage = (t, match) =>
  [match.group ? fill(t("tournament_group"), { group: match.group }) : "", stageName(t, match.stage)]
    .filter(Boolean)
    .join(" · ");

// The tournament round of a match, for the scoreboard's match view.
function tournamentLabel(view, match, t) {
  return [
    t("tournament"),
    matchStage(t, match),
    fill(t("tournament_match"), { match: match.match, matches: view.total }),
  ].join(" · ");
}

// Whether the practice game plays this match: the same two players, in order.
const playsMatch = (names, match) =>
  Boolean(match) && names.length === 2 && match.players.every((name, index) => name === names[index]);

const signed = (value) => (value > 0 ? `+${value}` : value < 0 ? `−${-value}` : "0");

// The round robin table, with the players of the next match marked. The table of a
// group leaves out the matches, the legs and the average, and marks the places that
// go on into the knockout.
function tournamentTable(view, ui, { standings = view.standings, through = 0 } = {}) {
  const { t, format } = ui;
  const compact = through > 0;
  const column = (key) =>
    `<th scope="col"><abbr title="${escapeHtml(t(`${key}_long`))}">${escapeHtml(t(key))}</abbr></th>`;
  const statistic = view.mpr
    ? `<th scope="col">${escapeHtml(t("cricket_mpr"))}</th>`
    : `<th scope="col"><abbr title="${escapeHtml(t("average_long"))}">Ø</abbr></th>`;
  const next = new Set((view.status === "waiting" ? view.next : view.current)?.players ?? []);
  const rows = standings.map((row) => {
    const kind = [
      row.name === view.winner ? "champion" : next.has(row.name) ? "next" : "",
      row.position <= through ? "through" : "",
    ].filter(Boolean);
    const goes = row.position <= through ? ` <span class="visually-hidden">${escapeHtml(t("tournament_through"))}</span>` : "";
    return (
      `<tr${kind.length ? ` class="${kind.join(" ")}"` : ""}><td class="rank">${row.position}</td>` +
      `<th scope="row" class="who"><span class="player-name">${avatarHtml(ui.avatar(row.name))}` +
      `<span>${escapeHtml(row.name)}</span>${goes}</span></th>` +
      (compact ? "" : `<td>${row.played}</td>`) +
      `<td>${row.won}</td><td>${row.lost}</td>` +
      (compact ? "" : `<td>${row.legsFor}:${row.legsAgainst}</td>`) +
      `<td>${signed(row.difference)}</td>` +
      (compact ? "" : `<td>${row.average === null ? "–" : escapeHtml(format(row.average, view.mpr ? 2 : 1))}</td>`) +
      `<td class="points">${row.points}</td></tr>`
    );
  });
  const columns = compact
    ? ["tournament_won", "tournament_lost", "tournament_difference"]
    : ["tournament_played", "tournament_won", "tournament_lost", "tournament_legs", "tournament_difference"];
  return (
    `<table class="standings"><thead><tr><th scope="col" class="rank">#</th>` +
    `<th scope="col" class="who">${escapeHtml(t("tournament_player"))}</th>` +
    columns.map(column).join("") +
    `${compact ? "" : statistic}${column("tournament_points")}</tr></thead><tbody>${rows.join("")}</tbody></table>`
  );
}

// The tables of the groups side by side, the places that go on marked.
function tournamentGroups(view, ui) {
  const { t } = ui;
  const tables = view.groups.map(
    (group) =>
      `<section class="group"><div class="section-label">${escapeHtml(fill(t("tournament_group"), { group: group.name }))}</div>` +
      `${tournamentTable(view, ui, { standings: group.standings, through: view.advance })}</section>`
  );
  return `<div class="groups">${tables.join("")}</div>`;
}

// Whether the knockout after the groups has begun: a place of it has a player.
const knockoutBegun = (view) =>
  view.bracket.some((round) => round.matches.some((match) => match.players.some((name) => name !== null)));

// A tournament on several boards: what every board plays, or when its next match
// starts, the board of the card marked, and when the tournament is expected to end.
// Nothing for a tournament at one board.
function tournamentBoards(view, ui, now = Date.now()) {
  if (view.boards.length < 2) return "";
  const { t } = ui;
  const time = ui.time ?? ((moment) => formatClock(null, moment).time);
  const rows = view.boards.map((board) => {
    const playing = board.players.length === 2;
    const waits =
      board.nextAt !== null && board.nextAt > now
        ? fill(t("tournament_board_next"), { time: time(board.nextAt) })
        : t("tournament_board_free");
    const match = playing
      ? `${escapeHtml(board.players[0])} <span class="vs">${escapeHtml(t("tournament_vs"))}</span> ${escapeHtml(board.players[1])}`
      : escapeHtml(waits);
    const kind = [playing ? "playing" : "waiting", board.board !== null && board.board === view.board ? "own" : ""];
    return (
      `<li class="${kind.filter(Boolean).join(" ")}"><span class="board-name">${escapeHtml(board.name)}</span>` +
      `<span class="board-match">${match}</span></li>`
    );
  });
  const ends =
    view.endsAt !== null && view.endsAt > now
      ? `<p class="forecast">${escapeHtml(fill(t("tournament_ends"), { time: time(view.endsAt) }))}</p>`
      : "";
  return `<section class="boards" aria-label="${escapeHtml(t("tournament_boards"))}"><ul>${rows.join("")}</ul>${ends}</section>`;
}

// What shows of a tournament between its matches and in idle mode: the boards of a
// tournament on several boards, then the table of a round robin, the groups until
// their knockout begins, and the brackets.
function tournamentBody(view, ui, fresh = new Set()) {
  return tournamentBoards(view, ui) + tournamentStage(view, ui, fresh);
}

function tournamentStage(view, ui, fresh) {
  if (view.format === "round_robin") return tournamentTable(view, ui);
  if (view.format === "groups_knockout" && !knockoutBegun(view)) return tournamentGroups(view, ui);
  if (!view.losers.length) return tournamentBracket(view, ui, fresh);
  return (
    tournamentBracket(view, ui, fresh) +
    `<div class="section-label losers-label">${escapeHtml(ui.t("tournament_losers_bracket"))}</div>` +
    tournamentBracket({ ...view, bracket: view.losers, winner: null }, ui, fresh)
  );
}

// Every place of the bracket with its player and whether the match decided it,
// so that a place filled since the last look can be animated.
function bracketSlots(view) {
  const slots = new Map();
  for (const round of [...(view?.bracket ?? []), ...(view?.losers ?? [])]) {
    round.matches.forEach((match, index) => {
      const decided = match.winner !== null && !match.bye;
      match.players.forEach((name, side) => {
        slots.set(`${round.stage}-${index}-${side}`, `${name}|${decided && name === match.winner}`);
      });
    });
  }
  return slots;
}

// The places that got a player or a result since the last bracket; none at first sight.
function freshSlots(before, after) {
  const fresh = new Set();
  if (!before) return fresh;
  for (const [key, value] of after) {
    if (before.get(key) !== value && !value.startsWith("null|")) fresh.add(key);
  }
  return fresh;
}

// The knockout bracket: a column per round; the match for third place below the final.
// The last round crowns the champion: the final, or the grand final of a double
// elimination. A bracket of 16 or 32 places has smaller boxes.
function tournamentBracket(view, ui, fresh = new Set()) {
  const { t } = ui;
  const live = (view.status === "waiting" ? view.next : view.current)?.match ?? null;
  const crown = view.winner ? view.bracket.filter((round) => round.stage !== "third_place").at(-1)?.stage : null;
  const widest = Math.max(0, ...view.bracket.map((round) => round.matches.length));
  const size = widest > 8 ? " huge" : widest > 4 ? " big" : "";
  const box = (match, stage, index) => {
    const decided = match.winner !== null && !match.bye;
    const slots = match.players.map((name, side) => {
      const key = `${stage}-${index}-${side}`;
      const classes = [
        "slot",
        name === null ? "open" : "",
        decided && name === match.winner ? "won" : "",
        decided && name !== match.winner ? "lost" : "",
        fresh.has(key) ? "fresh" : "",
      ].filter(Boolean);
      const shown = name ?? t(match.bye ? "tournament_bye" : "tournament_open");
      const score = decided ? String(view.setsToWin > 1 ? match.sets[side] : match.legs[side]) : "";
      return (
        `<div class="${classes.join(" ")}">${avatarHtml(name && ui.avatar(name))}` +
        `<span class="who">${escapeHtml(shown)}</span><span class="score">${score}</span></div>`
      );
    });
    const kind = [
      "duel",
      match.bye ? "bye" : "",
      match.match !== null && match.match === live ? "live" : "",
      stage === crown ? "crowned" : "",
    ].filter(Boolean);
    return `<div class="${kind.join(" ")}">${slots.join("")}</div>`;
  };
  const third = view.bracket.find((round) => round.stage === "third_place");
  const columns = view.bracket
    .filter((round) => round !== third)
    .map(
      (round) =>
        `<div class="round ${escapeHtml(round.stage)}"><div class="section-label">${escapeHtml(stageName(t, round.stage))}</div>` +
        `<div class="duels">${round.matches.map((match, index) => box(match, round.stage, index)).join("")}` +
        (third && round.stage === "final"
          ? `<div class="section-label third">${escapeHtml(stageName(t, third.stage))}</div>` +
            third.matches.map((match, index) => box(match, third.stage, index)).join("")
          : "") +
        `</div></div>`
    );
  return `<div class="bracket${size}">${columns.join("")}</div>`;
}

// Who plays next, while the tournament waits; the countdown is filled in every second.
function tournamentNextUp(view, ui) {
  const { t } = ui;
  const match = view.status === "waiting" ? view.next : null;
  if (!match) return "";
  const [first, second] = match.players.map((name) => name ?? t("tournament_open"));
  return (
    `<div class="next-up"><span class="section-label">${escapeHtml(
      `${t("tournament_next")} · ${matchStage(t, match)}`
    )}</span>` +
    `<span class="pairing">${avatarHtml(ui.avatar(first))}<b>${escapeHtml(first)}</b>` +
    `<span class="vs">${escapeHtml(t("tournament_vs"))}</span><b>${escapeHtml(second)}</b>${avatarHtml(
      ui.avatar(second)
    )}</span>` +
    `<span class="countdown" role="timer"></span>` +
    (ui.startNow && view.nextReady
      ? `<button type="button" class="start-next" data-tournament="next">${escapeHtml(t("tournament_start_now"))}</button>`
      : "") +
    `</div>`
  );
}

// When the next match starts: in a few seconds, after the takeout, or when asked.
function tournamentCountdown(view, now, t) {
  if (view.status !== "waiting") return "";
  if (!view.nextReady) return t("tournament_board_free");
  if (!view.pause || view.nextAt === null) return t("tournament_on_request");
  const seconds = Math.min(Math.max(Math.ceil((view.nextAt - now) / 1000), 0), view.pause);
  if (!seconds) return t("tournament_after_takeout");
  // A long pause counts down in minutes and seconds.
  const time =
    seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")} min`;
  return fill(t("tournament_countdown"), { time });
}

// The tournament between its matches: who plays next, and the table or the bracket.
function tournamentHtml(view, ui) {
  const { t } = ui;
  const body = tournamentBody(view, ui, ui.fresh);
  return {
    title: t("tournament"),
    meta: [
      t(`tournament_${view.format}`),
      gameName(t, view.game),
      view.status === "finished" ? "" : fill(t("tournament_progress"), { played: view.played, total: view.total }),
    ]
      .filter(Boolean)
      .join(" · "),
    banner: view.winner ? fill(t("tournament_winner"), { name: view.winner }) : "",
    main: `<div class="tournament ${view.format}">${tournamentNextUp(view, ui)}${body}</div>`,
  };
}

// The idle panel of a tournament: its table or bracket.
function tournamentPanelHtml(data, ui) {
  const view = data.tournament;
  if (!view) return "";
  return tournamentBody(view, ui);
}

// What the caller follows of a tournament.
function tournamentCallState(view) {
  return view
    ? {
        started: view.started,
        status: view.status,
        match: view.current?.match ?? null,
        players: view.current?.players ?? [],
        winner: view.winner,
      }
    : null;
}

// The calls of a tournament: every match as it starts, and the champion. Nothing
// at first sight: undefined is a card that has not seen the tournament sensor yet.
function tournamentCalls(previous, current, options) {
  if (previous === undefined || !current || options.call_results === false) return [];
  const same = previous?.started === current.started;
  if (current.status === "finished") {
    return same && previous.status !== "finished" ? [{ kind: "tournament_won", name: current.winner }] : [];
  }
  if (current.status !== "playing" || (same && current.match === previous.match)) return [];
  const [first, second] = current.players;
  return [{ kind: "tournament_next", first, second }];
}

// The start_tournament action for the choice of the new game screen.
function tournamentStartData(choice, { entry = null, distance = false } = {}) {
  const named = choice.players.map((name, index) => [name, choice.starts?.[index] ?? 0]).filter(([name]) => name);
  const players = named.map(([name]) => name);
  const starts = named.map(([, start]) => start);
  const data = {
    players,
    format: choice.format,
    game: choice.game,
    legs: choice.legs,
    sets: choice.sets,
    bull_off: choice.bull_off,
    random_draw: choice.random_draw,
  };
  if (entry) data.config_entry_id = entry;
  if (distance && choice.bull_off) data.bull_off_distance = choice.bull_off_distance;
  if (gameGroup(choice.game) === "x01") {
    Object.assign(data, { double_out: choice.out_mode !== "straight", double_in: choice.in_mode !== "straight" });
  }
  // A handicap goes with the start, and so does the game's start score when it is back.
  if (gameGroup(choice.game) === "x01" && (choice.handicap || starts.some(Boolean))) data.start_scores = starts;
  if (THIRD_PLACE_FORMATS.includes(choice.format)) {
    data.third_place = choice.third_place && knockoutPlayers(choice) >= THIRD_PLACE_PLAYERS;
  }
  // The groups go along, 0 for those the board makes, and so do the qualifiers.
  if (choice.format === "groups_knockout") {
    const { groups, advance } = groupSetup(choice);
    Object.assign(data, { groups, advance });
  }
  return data;
}

// Doubles --------------------------------------------------------------------

const DOUBLE_ORDER = [...BOARD_NUMBERS.map((number) => `D${number}`), "BULL"];

// Every double hit by any dart, with its attempts and hit rate where darts were aimed
// at it; `landed` counts the darts in each double by name, such as { D16: 3 }.
function doubleCounts(source, landed) {
  const aimed = new Map(
    (Array.isArray(source?.doubles) ? source.doubles : [])
      .filter(
        (item) =>
          item &&
          DOUBLE_ORDER.includes(item.double) &&
          Number.isInteger(item.attempts) &&
          Number.isInteger(item.hits) &&
          item.attempts > 0
      )
      .map((item) => [item.double, item])
  );
  const counted = landed && typeof landed === "object" ? landed : {};
  const doubles = DOUBLE_ORDER.map((double) => {
    const item = aimed.get(double);
    // A hit of a dart aimed at the double is a hit of the double, also where older
    // data counted no hits.
    const count = Math.max(Number.isInteger(counted[double]) && counted[double] > 0 ? counted[double] : 0, item?.hits ?? 0);
    if (!item && !count) return null;
    return {
      double,
      landed: count,
      attempts: item?.attempts ?? 0,
      hits: item?.hits ?? 0,
      rate: item ? (finite(item.rate) ?? Math.round((item.hits * 1000) / item.attempts) / 10) : null,
    };
  }).filter(Boolean);
  return {
    attempts: finite(source?.attempts) ?? 0,
    hits: finite(source?.hits) ?? 0,
    rate: finite(source?.rate),
    favourite: typeof source?.favourite === "string" ? source.favourite : null,
    landed: doubles.reduce((sum, item) => sum + item.landed, 0),
    doubles,
  };
}

// Names of every player profile, for the player picker of the doubles card.
function profileNames(hass) {
  const names = new Set();
  for (const id of Object.values(hass?.entities || {})) {
    if (id.platform !== "homedarts" || id.translation_key !== "player_profiles") continue;
    const players = hass.states?.[id.entity_id]?.attributes?.players;
    for (const player of Array.isArray(players) ? players : []) if (named(player?.name)) names.add(player.name);
  }
  return [...names].sort((a, b) => a.localeCompare(b));
}

// Everybody's doubles, or one player's from the profiles.
function doublesView(doubles, profiles, player = "") {
  const wanted = String(player || "").trim().toLowerCase();
  if (wanted) {
    const profile = (Array.isArray(profiles?.attributes?.players) ? profiles.attributes.players : []).find(
      (item) => typeof item?.name === "string" && item.name.trim().toLowerCase() === wanted
    );
    // A profile counts every dart by the bed it hit.
    return { player: profile?.name ?? player, known: Boolean(profile), ...doubleCounts(profile?.doubles, profile?.hits) };
  }
  const attributes = doubles?.attributes || {};
  const favourite = usable(doubles) ? doubles.state : null;
  return { player: null, known: true, ...doubleCounts({ ...attributes, favourite }, attributes.landed) };
}

// Red for rarely hit doubles, green from about one hit in two.
function doubleColor(rate) {
  const hue = Math.round(Math.min(Math.max(rate, 0), 50) * 2.6);
  return `hsl(${hue} 70% 46%)`;
}

// The colour of a double: its hit rate where darts were aimed at it, else the accent,
// the stronger the more often it was hit.
const doubleTint = (item, most) =>
  item.rate === null
    ? `color-mix(in srgb, var(--ad-accent) ${Math.round(35 + (55 * item.landed) / most)}%, transparent)`
    : doubleColor(item.rate);

function doublesHtml(view, ui) {
  const { t, format, percent, label } = ui;
  const most = Math.max(1, ...view.doubles.map((item) => item.landed));
  const told = (item) =>
    [
      fill(t("doubles_landed"), { count: format(item.landed, 0) }),
      item.attempts ? `${format(item.hits, 0)}/${format(item.attempts, 0)} ${t("doubles_aimed")}` : null,
    ]
      .filter(Boolean)
      .join(" · ");
  // Every double of the list is a bed of the board.
  const ring = view.doubles
    .map(
      (item) =>
        `<path d="${bedPath(hitBeds(item.double)[0])}" style="fill:${doubleTint(item, most)}"><title>${escapeHtml(
          `${label(item.double)}: ${told(item)}`
        )}</title></path>`
    )
    .join("");
  // The bar tells how often a double was hit, its colour the rate; the doubles aimed at
  // come first, the best rate first.
  const list = [...view.doubles]
    .sort((a, b) => (b.rate ?? -1) - (a.rate ?? -1) || b.attempts - a.attempts || b.landed - a.landed)
    .map(
      (item) =>
        `<div class="double${item.double === view.favourite ? " favourite" : ""}" title="${escapeHtml(told(item))}">` +
        `<span class="bed" style="--c:${doubleTint(item, most)}">${escapeHtml(label(item.double))}</span>` +
        `<span class="bar"><i style="width:${Math.round((100 * item.landed) / most)}%;background:${doubleTint(item, most)}"></i></span>` +
        `<span class="landed">${escapeHtml(fill(t("doubles_landed_short"), { count: format(item.landed, 0) }))}</span>` +
        `<span class="count">${item.attempts ? escapeHtml(`${format(item.hits, 0)}/${format(item.attempts, 0)}`) : ""}</span>` +
        `<span class="rate">${escapeHtml(item.rate === null ? "–" : percent(item.rate, 0))}</span></div>`
    )
    .join("");
  return { ring, list };
}

// Progress -------------------------------------------------------------------

// The icon of every achievement; the colour of a badge tells its tier.
const ACHIEVEMENT_ICONS = {
  maximum: "mdi:crown",
  ton_plus: "mdi:arrow-up-bold-circle-outline",
  ton_forty: "mdi:rocket-launch",
  high_finish: "mdi:flag-checkered",
  short_leg: "mdi:run-fast",
  nine_darter: "mdi:star-shooting",
  legs_won: "mdi:trophy-variant-outline",
  matches_won: "mdi:trophy",
  hat_trick: "mdi:bullseye",
  all_doubles: "mdi:circle-double",
  cricket_nine: "mdi:pound",
  shanghai: "mdi:dice-multiple",
  around_the_clock: "mdi:clock-time-twelve-outline",
  bobs_27: "mdi:target",
  streak: "mdi:fire",
  darts_thrown: "mdi:arrow-projectile-multiple",
};
// Bronze, silver, gold and platinum; an achievement of a single tier is gold.
const TIER_COLORS = ["#c07a3c", "#a9b6c4", GOLD, "#5fd0e8"];

function tierColor(tier, tiers) {
  if (!tier) return null;
  return TIER_COLORS[tiers === 1 ? 2 : Math.min(tier, TIER_COLORS.length) - 1];
}

// Every player's badges from the achievements sensor: the tier reached, when,
// and how far the value has come towards the next tier.
function badgesView(achievements) {
  const attributes = achievements?.attributes || {};
  const catalogue = (Array.isArray(attributes.catalogue) ? attributes.catalogue : []).filter(
    (item) =>
      item && typeof item.id === "string" && Array.isArray(item.tiers) && item.tiers.length && item.tiers.every(Number.isFinite)
  );
  const players = (Array.isArray(attributes.players) ? attributes.players : [])
    .filter((player) => player && named(player.name))
    .map((player) => {
      const earned = player.badges && typeof player.badges === "object" ? player.badges : {};
      const progress = player.progress && typeof player.progress === "object" ? player.progress : {};
      const badges = catalogue.map((item) => {
        const tiers = item.tiers.length;
        const reached = Number(earned[item.id]?.tier);
        const tier = Number.isInteger(reached) ? Math.min(Math.max(reached, 0), tiers) : 0;
        const dates = (Array.isArray(earned[item.id]?.dates) ? earned[item.id].dates : []).filter(
          (date) => typeof date === "string"
        );
        const value = finite(progress[item.id]);
        const goal = item.tiers[Math.min(tier, tiers - 1)];
        // A count shows how far it has come; fewest darts and yes-or-no badges do not.
        const measurable = item.lower !== true && goal > 1 && tier < tiers && value !== null;
        return {
          id: item.id,
          tier,
          tiers,
          goal,
          lower: item.lower === true,
          value,
          share: measurable ? Math.min(1, Math.max(0, value / goal)) : null,
          date: dates.at(-1) ?? null,
          dates,
        };
      });
      return { name: player.name, unlocked: badges.reduce((sum, badge) => sum + badge.tier, 0), badges };
    });
  return { players };
}

// The badges a closed gallery shows: those earned, and the next goals, the locked badges
// closest to being earned.
const BADGE_GOALS = 3;
function shownBadges(player, locked, open) {
  if (!locked) return player.badges.filter((badge) => badge.tier);
  if (open) return player.badges;
  const goals = player.badges
    .filter((badge) => !badge.tier)
    .sort((a, b) => (b.share ?? -1) - (a.share ?? -1))
    .slice(0, BADGE_GOALS);
  return player.badges.filter((badge) => badge.tier || goals.includes(badge));
}

function badgesHtml(player, ui, locked = true, open = true) {
  const { t, format, date } = ui;
  const before = open && locked ? shownBadges(player, true, false) : null;
  return shownBadges(player, locked, open)
    .map((badge) => {
      const tier = badge.tier && badge.tiers > 1 ? t(`tier_${Math.min(badge.tier, 4)}`) : "";
      const title = `${t(`achievement_${badge.id}`)}${tier ? ` · ${tier}` : ""}`;
      const goal = fill(t(`achievement_${badge.id}_goal`), { value: format(badge.goal) });
      let status = t("badge_locked");
      if (badge.share !== null) status = fill(t("badge_progress"), { value: format(badge.value), goal: format(badge.goal) });
      else if (badge.lower && badge.value !== null && badge.tier < badge.tiers) status = fill(t("badge_best"), { value: format(badge.value) });
      else if (badge.tier) status = fill(t("badge_earned"), { date: date(badge.date) });
      const bar = badge.share === null ? "" : `<span class="badge-bar"><i style="width:${fmt(badge.share * 100)}%"></i></span>`;
      const color = tierColor(badge.tier, badge.tiers);
      return (
        `<div class="badge${badge.tier ? "" : " locked"}${before && !before.includes(badge) ? " appear" : ""}"` +
        ` data-badge="${escapeHtml(badge.id)}"` +
        `${color ? ` style="--tier:${color}"` : ""}>` +
        `<span class="badge-icon"><ha-icon icon="${ACHIEVEMENT_ICONS[badge.id] ?? "mdi:medal-outline"}"></ha-icon></span>` +
        `<span class="badge-text"><b>${escapeHtml(title)}</b><span>${escapeHtml(goal)}</span>` +
        `<span class="muted">${escapeHtml(status)}</span>${bar}</span></div>`
      );
    })
    .join("");
}

// The weekly sums of a player's trend that its figures come from.
const TREND_SUMS = [
  "darts",
  "x01_darts",
  "x01_points",
  "first9_points",
  "first9_darts",
  "at_double",
  "checkouts",
  "double_attempts",
  "double_hits",
  "maximums",
];
const ratioOf = (part, whole, factor) => (whole > 0 ? (part * factor) / whole : null);
const TREND_METRICS = [
  { key: "average", label: "average", digits: 1, of: (sums) => ratioOf(sums.x01_points, sums.x01_darts, 3) },
  { key: "first_9", label: "first_9", digits: 1, of: (sums) => ratioOf(sums.first9_points, sums.first9_darts, 3) },
  {
    key: "checkout_rate",
    label: "checkout_short",
    digits: 1,
    percent: true,
    of: (sums) => ratioOf(sums.checkouts, sums.at_double, 100),
  },
  {
    key: "doubles_rate",
    label: "doubles_rate_short",
    digits: 1,
    percent: true,
    of: (sums) => ratioOf(sums.double_hits, sums.double_attempts, 100),
  },
  // A sum, not a ratio: its arrow compares the darts of a complete week.
  { key: "darts", label: "darts", digits: 0, perWeek: true, of: (sums) => (sums.darts > 0 ? sums.darts : null) },
];

// The last weeks of a trend, oldest first, each with its sums.
function trendWeeks(trend, size) {
  const weeks = Array.isArray(trend?.weeks) ? trend.weeks.filter((week) => typeof week === "string") : [];
  const count = Math.min(Math.max(1, Math.round(size) || 1), weeks.length);
  const first = weeks.length - count;
  return weeks.slice(first).map((week, index) => {
    const sums = { week };
    for (const name of TREND_SUMS) sums[name] = finite(trend[name]?.[first + index]) ?? 0;
    for (const name of ["highest_checkout", "best_501", "best_mpr"]) sums[name] = finite(trend[name]?.[first + index]);
    return sums;
  });
}

// Sums of several weeks; bests keep the best week.
function addWeeks(weeks) {
  const total = Object.fromEntries(TREND_SUMS.map((name) => [name, 0]));
  const best = (values, pick) => (values.length ? pick(...values) : null);
  for (const week of weeks) for (const name of TREND_SUMS) total[name] += week[name];
  const known = (name) => weeks.map((week) => week[name]).filter((value) => value !== null && value > 0);
  total.highest_checkout = best(known("highest_checkout"), Math.max);
  total.best_501 = best(known("best_501"), Math.min);
  total.best_mpr = best(known("best_mpr"), Math.max);
  return total;
}

// Every figure of a player's trend: its value over the weeks, the value of each
// week for the sparkline, and whether the newer half of the weeks is better. A ratio
// such as the average compares the two halves. A sum such as the darts compares what
// a week of either half adds up to, a week without darts with none, and only the
// complete weeks: the newer half can hold a week more than the older one, and the
// last week is the current one, which has only begun.
function trendView(trend, size = 12) {
  const weeks = trendWeeks(trend, size);
  return TREND_METRICS.map((metric) => {
    const compared = metric.perWeek ? weeks.slice(0, -1) : weeks;
    const half = Math.floor(compared.length / 2);
    const figure = (part) => {
      const value = metric.of(addWeeks(part));
      return metric.perWeek && part.length ? (value ?? 0) / part.length : value;
    };
    const before = figure(compared.slice(0, half));
    const after = figure(compared.slice(half));
    // Without both halves there is nothing to compare, and no arrow; neither without a
    // figure in any of the weeks compared, such as complete weeks without darts.
    let direction = null;
    if (before !== null && after !== null && metric.of(addWeeks(compared)) !== null) {
      direction = "steady";
      const change = after - before;
      if (Math.abs(change) >= Math.max(0.5, Math.abs(before) * 0.02)) direction = change > 0 ? "up" : "down";
    }
    return {
      key: metric.key,
      label: metric.label,
      digits: metric.digits,
      percent: metric.percent === true,
      values: weeks.map((week) => metric.of(week)),
      value: metric.of(addWeeks(weeks)),
      direction,
    };
  });
}

// A small line of the weekly values. It runs on through the weeks without a value, whose
// stretch is dashed, so that it never breaks into pieces; a single value is a dot.
function sparkline(values) {
  const known = values.map((value, index) => [index, value]).filter(([, value]) => value !== null);
  if (!known.length) return "";
  const low = Math.min(...known.map(([, value]) => value));
  const high = Math.max(...known.map(([, value]) => value));
  const x = (index) => fmt(values.length > 1 ? (index * 100) / (values.length - 1) : 50);
  const y = (value) => fmt(high === low ? 12 : 21 - ((value - low) / (high - low)) * 18);
  const point = ([index, value]) => `${x(index)},${y(value)}`;
  const runs = [[known[0]]];
  const gaps = [];
  known.slice(1).forEach((item, at) => {
    const before = known[at];
    if (item[0] === before[0] + 1) runs.at(-1).push(item);
    else {
      gaps.push([before, item]);
      runs.push([item]);
    }
  });
  const line = (points, style = "") => `<polyline${style ? ` class="${style}"` : ""} points="${points.map(point).join(" ")}"/>`;
  const lines =
    known.length === 1
      ? line([known[0], known[0]], "dot")
      : [...gaps.map((pair) => line(pair, "gap")), ...runs.filter((run) => run.length > 1).map((run) => line(run))].join("");
  const last = values.findLastIndex((value) => value !== null);
  const end = `${x(last)},${y(values[last])}`;
  return (
    `<svg class="spark" viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true">` +
    `${lines}<polyline class="dot last" points="${end} ${end}"/></svg>`
  );
}

const TREND_ARROWS = { up: "↗", down: "↘", steady: "→" };

function trendsHtml(players, ui) {
  const { t, format, percent } = ui;
  return players
    .map((player) => {
      const metrics = player.metrics
        .map((metric) => {
          const shown =
            metric.value === null ? "–" : metric.percent ? percent(metric.value, metric.digits) : format(metric.value, metric.digits);
          const trend = metric.direction ? t(`trend_${metric.direction}`) : "";
          const arrow = metric.direction
            ? ` <span class="arrow ${metric.direction}" role="img" title="${escapeHtml(trend)}" aria-label="${escapeHtml(trend)}">` +
              `${TREND_ARROWS[metric.direction]}</span>`
            : "";
          return (
            `<div class="trend" data-metric="${metric.key}"><span class="trend-label">${escapeHtml(t(metric.label))}</span>` +
            `<span class="trend-value">${escapeHtml(shown)}${arrow}</span>` +
            `${sparkline(metric.values)}</div>`
          );
        })
        .join("");
      return (
        `<div class="trend-player"><div class="trend-name">${escapeHtml(player.name)}</div>` +
        `<div class="trends balanced n${player.metrics.length}">${metrics}</div></div>`
      );
    })
    .join("");
}

// The groupings of a player or the session, at most `limit` beds.
function spreadView(groups, limit = 3) {
  return (Array.isArray(groups) ? groups : [])
    .filter(
      (group) =>
        group &&
        typeof group.target === "string" &&
        ["darts", "offset_x", "offset_y", "r50", "r80"].every((key) => Number.isFinite(group[key]))
    )
    .slice(0, limit)
    .map((group) => ({ ...group, change: finite(group.change) }));
}

// "6 mm left of center, 2 mm high", in board directions as the player sees them.
function offsetText(ui, group) {
  const { t, format } = ui;
  const mm = (value) => fill(t("unit_mm"), { value: format(Math.abs(value)) });
  const parts = [];
  if (Math.abs(group.offset_x) >= 1) {
    parts.push(fill(t(group.offset_x < 0 ? "spread_left" : "spread_right"), { distance: mm(group.offset_x) }));
  }
  if (Math.abs(group.offset_y) >= 1) {
    parts.push(fill(t(group.offset_y < 0 ? "spread_low" : "spread_high"), { distance: mm(group.offset_y) }));
  }
  return parts.join(", ") || t("spread_centered");
}

function spreadHtml(groups, ui) {
  const { t, format, label } = ui;
  const mm = (value) => fill(t("unit_mm"), { value: format(Math.abs(value)) });
  return groups
    .map((group) => {
      const text = [
        fill(t("spread_group"), { r50: mm(group.r50) }),
        fill(t("spread_group80"), { r80: mm(group.r80) }),
        offsetText(ui, group),
      ].join(" · ");
      const changed = group.change !== null && Math.abs(group.change) >= 1;
      const change = changed
        ? `<span class="group-change ${group.change < 0 ? "better" : "worse"}">${escapeHtml(
            fill(t(group.change < 0 ? "spread_tighter" : "spread_wider"), { value: mm(group.change) })
          )}</span>`
        : "";
      return (
        `<div class="group" data-target="${escapeHtml(group.target)}"><span class="group-target">${escapeHtml(
          label(group.target)
        )}</span><span class="group-text">${escapeHtml(text)}</span>${change}</div>`
      );
    })
    .join("");
}

// Trends and groupings of every named player from the profiles sensor.
function progressView(profiles, weeks = 12) {
  return (Array.isArray(profiles?.attributes?.players) ? profiles.attributes.players : [])
    .filter((player) => player && named(player.name))
    .map((player) => ({
      name: player.name,
      metrics: trendView(player.trend, weeks),
      groups: spreadView(player.spread),
      active: trendWeeks(player.trend, weeks).some((week) => week.darts > 0 || week.x01_darts > 0),
    }));
}

// A smoothed density of dart positions on a grid over the board, in millimetres.
const DENSITY_CELL = 8;
const DENSITY_SIGMA = 8;
// The newest darts are also drawn as dots, up to this many.
const POSITION_DOTS = 300;
// The edge of the board with its number ring, as positions count: a dart beyond it
// missed the board, and the board is all the drawing shows.
const BOARD_EDGE = R.board / NORM;

const onBoard = (x, y) => Number.isFinite(x) && Number.isFinite(y) && Math.hypot(x, y) <= BOARD_EDGE;
const validPositions = (positions) =>
  (Array.isArray(positions) ? positions : []).filter(
    (position) => Array.isArray(position) && onBoard(position[0], position[1])
  );

// The darts of the current visit that the session logs once the visit is booked: every
// dart of the visit the board saw on it, not the bot's.
const visitPositions = (throws) =>
  (Array.isArray(throws) ? throws : [])
    .filter((dart) => Number.isInteger(dart?.dart) && dart.bot !== true)
    .map((dart) => [dart.x, dart.y])
    .filter(([x, y]) => onBoard(x, y));
// When the newest visit was booked; the visit sensor lists the recent visits newest first.
const newestVisit = (state) => state?.attributes?.recent_visits?.[0]?.time;

function positionsDensity(positions) {
  const cells = new Map();
  const reach = Math.ceil((3 * DENSITY_SIGMA) / DENSITY_CELL);
  for (const [nx, ny] of validPositions(positions)) {
    const x = nx * NORM;
    const y = -ny * NORM;
    const column = Math.round(x / DENSITY_CELL);
    const row = Math.round(y / DENSITY_CELL);
    for (let i = column - reach; i <= column + reach; i += 1) {
      for (let j = row - reach; j <= row + reach; j += 1) {
        const dx = i * DENSITY_CELL - x;
        const dy = j * DENSITY_CELL - y;
        const weight = Math.exp(-(dx * dx + dy * dy) / (2 * DENSITY_SIGMA * DENSITY_SIGMA));
        if (weight < 0.01) continue;
        const key = `${i},${j}`;
        cells.set(key, (cells.get(key) || 0) + weight);
      }
    }
  }
  return cells;
}

// The density in the heatmap colours, softened by a blur, and the newest darts as dots;
// the darts of the current visit count for the density and stand out as pins.
function positionsHtml(positions, live) {
  const valid = validPositions(positions);
  const current = validPositions(live);
  const cells = positionsDensity([...valid, ...current]);
  let max = 0;
  for (const value of cells.values()) max = Math.max(max, value);
  const half = DENSITY_CELL / 2;
  const density = [...cells.entries()]
    .filter(([, value]) => value >= max * 0.04)
    .map(([key, value]) => {
      const [column, row] = key.split(",").map(Number);
      const ratio = value / max;
      return (
        `<rect x="${fmt(column * DENSITY_CELL - half)}" y="${fmt(row * DENSITY_CELL - half)}" ` +
        `width="${DENSITY_CELL}" height="${DENSITY_CELL}" fill="${heatColor(ratio)}" fill-opacity="${fmt(0.3 + 0.6 * ratio)}"/>`
      );
    })
    .join("");
  const dots = valid
    .slice(-POSITION_DOTS)
    .map(([x, y]) => `<circle class="position" cx="${fmt(x * NORM)}" cy="${fmt(-y * NORM)}" r="2.2"/>`)
    .join("");
  const pins = current
    .map(([x, y]) => `<circle class="position live" cx="${fmt(x * NORM)}" cy="${fmt(-y * NORM)}" r="6"/>`)
    .join("");
  return `<g class="density" filter="url(#ad-density)">${density}</g><g class="positions">${dots}${pins}</g>`;
}

// The aim map -------------------------------------------------------------------

// Where a player scores the most per dart, from their own spread, as aim.py of the
// integration has it (Tibshirani, Price and Taylor, "A statistician plays darts", 2011):
// the points per dart at an aim point are the mean score of 1,000 fixed draws of the
// player's error, each landing point rounded to the millimetre, on a 2 mm grid over the
// board. Home Assistant finds the best aim and its points; the card draws the points of
// every aim point, to the last digit those of Home Assistant. aimSegment, aimDraws and
// aimField also run in a Web Worker, so they take the geometry with the request and use
// nothing else of this module.
const AIM_DRAWS = 1000;
const AIM_GRID = 2;
const AIM_MODEL_KEYS = ["offset_x", "offset_y", "sd_x", "sd_y", "correlation"];
// The beds the best aim is compared with, as Home Assistant sends them.
const AIM_COMPARED = ["T20", "T19", "BULL"];
// Every third point of the grid is drawn, a cell of 6 mm, softened by the blur of the
// density; the colors run from this share of the most points per dart to the most.
const AIM_CELL = 3;
const AIM_FLOOR = 0.6;

// The number and multiplier of the bed at a point in whole millimetres, as aim.py has
// it: the rings compared by the square of the distance, which is exact, and a point
// exactly between two sectors in the one that rounding half to even picks, as Python does.
function aimSegment(x, y, geometry) {
  const [bull, outerBull, trebleIn, trebleOut, doubleIn, doubleOut] = geometry.rings;
  const square = x * x + y * y;
  if (square <= bull * bull) return [25, 2];
  if (square <= outerBull * outerBull) return [25, 1];
  if (square > doubleOut * doubleOut) return [0, 0];
  const sector = (Math.atan2(x, y) * (180 / Math.PI)) / 18;
  let index = Math.round(sector);
  if (index - sector === 0.5 && index % 2 !== 0) index -= 1;
  const number = geometry.numbers[((index % 20) + 20) % 20];
  if (square > trebleIn * trebleIn && square <= trebleOut * trebleOut) return [number, 3];
  return [number, square > doubleIn * doubleIn ? 2 : 1];
}

// Pairs of standard normal numbers, spread evenly: a Fibonacci lattice of the unit square,
// mapped by the Box-Muller transform.
function aimDraws(count) {
  const golden = (Math.sqrt(5) - 1) / 2;
  const draws = new Float64Array(2 * count);
  for (let index = 0; index < count; index += 1) {
    const radius = Math.sqrt(-2 * Math.log((index + 0.5) / count));
    const angle = 2 * Math.PI * ((index * golden) % 1);
    draws[2 * index] = radius * Math.cos(angle);
    draws[2 * index + 1] = radius * Math.sin(angle);
  }
  return draws;
}

// The points per dart at every aim point of the grid, row by row from the bottom, -1 off
// the board, and the most of them.
function aimField(request) {
  const { model, geometry, draws: count, grid } = request;
  const board = geometry.rings[5];
  const reach = 2 * board;
  const edge = board + reach;
  const width = 2 * edge + 1;
  // The points of every millimetre around the board.
  const cells = new Uint8Array(width * width);
  for (let y = -board; y <= board; y += 1) {
    for (let x = -board; x <= board; x += 1) {
      const [number, multiplier] = aimSegment(x, y, geometry);
      cells[(y + edge) * width + x + edge] = number * multiplier;
    }
  }
  // Where the draws land, as offsets in those cells; a draw beyond the reach misses the
  // board from every aim point on it and scores nothing.
  const draws = aimDraws(count);
  const spread = Math.sqrt(1 - model.correlation * model.correlation);
  const landing = [];
  for (let index = 0; index < count; index += 1) {
    const first = draws[2 * index];
    const second = draws[2 * index + 1];
    const x = Math.floor(model.offset_x + model.sd_x * first + 0.5);
    const y = Math.floor(model.offset_y + model.sd_y * (model.correlation * first + spread * second) + 0.5);
    if (Math.abs(x) <= reach && Math.abs(y) <= reach) landing.push(y * width + x);
  }
  const offsets = Int32Array.from(landing);
  const side = Math.floor(board / grid);
  const size = 2 * side + 1;
  const field = new Float32Array(size * size).fill(-1);
  let high = 0;
  for (let row = 0; row < size; row += 1) {
    const y = (row - side) * grid;
    for (let column = 0; column < size; column += 1) {
      const x = (column - side) * grid;
      if (x * x + y * y > board * board) continue;
      const base = (y + edge) * width + x + edge;
      let sum = 0;
      for (let index = 0; index < offsets.length; index += 1) sum += cells[base + offsets[index]];
      field[row * size + column] = sum / count;
      high = Math.max(high, sum / count);
    }
  }
  return { size, grid, field, high };
}

// The error model of a player or the session with the best aim of Home Assistant, or how
// many darts at a treble it has and needs.
function aimView(aim) {
  const count = (value, otherwise) => (Number.isInteger(value) && value >= 0 ? value : otherwise);
  const darts = count(aim?.darts, 0);
  const needed = count(aim?.needed, 30);
  const best = aim?.best;
  const valid =
    AIM_MODEL_KEYS.every((key) => Number.isFinite(aim?.[key])) &&
    aim.sd_x > 0 &&
    aim.sd_y > 0 &&
    Math.abs(aim.correlation) < 1 &&
    typeof best?.bed === "string" &&
    [best.x, best.y].every(Number.isInteger) &&
    Number.isFinite(best.expected);
  if (!valid) return { darts, needed, model: null, key: null, best: null, compared: [] };
  const model = Object.fromEntries(AIM_MODEL_KEYS.map((key) => [key, aim[key]]));
  const compared = AIM_COMPARED.filter((bed) => bed !== best.bed && Number.isFinite(best.compared?.[bed])).map(
    (bed) => ({ bed, expected: best.compared[bed] })
  );
  return {
    darts,
    needed,
    model,
    key: AIM_MODEL_KEYS.map((key) => model[key]).join("|"),
    best: { bed: best.bed, x: best.x, y: best.y, expected: best.expected },
    compared,
  };
}

// What the worker needs for a model: the draws, the grid and the board.
const aimRequest = (model) => ({
  model,
  geometry: { rings: [R.bull, R.outerBull, R.trebleIn, R.trebleOut, R.doubleIn, R.doubleOut], numbers: NUMBERS },
  draws: AIM_DRAWS,
  grid: AIM_GRID,
});

// The script of the worker: the functions above and an answer to every request.
const aimWorkerSource = () =>
  `${[aimSegment, aimDraws, aimField].map(String).join("\n")}\n` +
  "self.onmessage = (event) => {\n" +
  "  const field = aimField(event.data.request);\n" +
  "  self.postMessage({ id: event.data.id, field }, [field.field.buffer]);\n" +
  "};\n";

// The aim maps of a training card, from a Web Worker of its own, which starts with the first
// map and ends with the card. Where the page has no workers or allows none of its own, as
// with a strict content security policy, the card computes the maps itself.
class AimFields {
  constructor() {
    // undefined until the first map, null without a worker.
    this.worker = undefined;
    this.jobs = new Map();
    this.next = 0;
  }

  _worker() {
    if (this.worker !== undefined) return this.worker;
    this.worker = null;
    if (typeof window.Worker !== "function" || typeof window.URL?.createObjectURL !== "function") return null;
    try {
      const url = window.URL.createObjectURL(new window.Blob([aimWorkerSource()], { type: "text/javascript" }));
      const worker = new window.Worker(url);
      // The worker holds on to its script; the address is needed no longer.
      window.URL.revokeObjectURL(url);
      worker.onmessage = ({ data }) => {
        const job = this.jobs.get(data.id);
        this.jobs.delete(data.id);
        job.resolve(data.field);
      };
      // A worker that can't start leaves its maps, and every later one, to the card.
      worker.onerror = () => {
        worker.terminate();
        this.worker = null;
        const jobs = [...this.jobs.values()];
        this.jobs.clear();
        for (const job of jobs) job.resolve(aimField(job.request));
      };
      this.worker = worker;
    } catch {
      // The card computes the maps.
    }
    return this.worker;
  }

  // The points per dart of a request.
  compute(request) {
    return new Promise((resolve) => {
      const worker = this._worker();
      if (!worker) {
        resolve(aimField(request));
        return;
      }
      this.next += 1;
      this.jobs.set(this.next, { request, resolve });
      worker.postMessage({ id: this.next, request });
    });
  }

  // The card left the page: the worker ends, and maps on their way come to nothing.
  stop() {
    this.worker?.terminate();
    this.worker = undefined;
    const jobs = [...this.jobs.values()];
    this.jobs.clear();
    for (const job of jobs) job.resolve(null);
  }
}

// The points per dart in the heatmap colors, from AIM_FLOOR of the most to the most, with
// the best aim as a ring.
function aimHtml(field, best) {
  const low = field.high * AIM_FLOOR;
  const side = (field.size - 1) / 2;
  const half = (AIM_CELL * field.grid) / 2;
  const cells = [];
  for (let row = side % AIM_CELL; row < field.size; row += AIM_CELL) {
    for (let column = side % AIM_CELL; column < field.size; column += AIM_CELL) {
      const value = field.field[row * field.size + column];
      if (!(value > low)) continue;
      const ratio = (value - low) / (field.high - low);
      const x = (column - side) * field.grid;
      const y = -(row - side) * field.grid;
      cells.push(
        `<rect x="${fmt(x - half)}" y="${fmt(y - half)}" width="${2 * half}" height="${2 * half}" ` +
          `fill="${heatColor(ratio)}" fill-opacity="${fmt(0.35 + 0.55 * ratio)}"/>`
      );
    }
  }
  const at = `cx="${best.x}" cy="${-best.y}"`;
  return (
    `<g class="density" filter="url(#ad-density)">${cells.join("")}</g>` +
    `<g class="aim"><circle class="aim-shadow" ${at} r="7"/><circle class="aim-best" ${at} r="7"/>` +
    `<circle class="aim-dot" ${at} r="2"/></g>`
  );
}

// The best aim and the beds compared with it: the bed, its points per dart and how many
// fewer than the best, for the list below the board and for screen readers.
function aimRows(view, ui) {
  const { t, format } = ui;
  return [
    { bed: view.best.bed, text: fill(t("aim_best"), { points: format(view.best.expected, 1) }), change: "" },
    ...view.compared.map(({ bed, expected }) => {
      // To the tenth that the card shows; a bed as good as the best shows no difference.
      const change = Math.round((expected - view.best.expected) * 10) / 10;
      return { bed, text: fill(t("aim_points"), { points: format(expected, 1) }), change: change ? format(change, 1) : "" };
    }),
  ];
}

function aimSummaryHtml(view, ui) {
  const { t, format, label } = ui;
  const rows = aimRows(view, ui).map(
    ({ bed, text, change }) =>
      `<div class="group" data-target="${escapeHtml(bed)}"><span class="group-target">${escapeHtml(label(bed))}</span>` +
      `<span class="group-text">${escapeHtml(text)}</span>` +
      `${change ? `<span class="group-change worse">${escapeHtml(change)}</span>` : ""}</div>`
  );
  // Whole millimetres, as the groupings show them.
  const mm = (value) => fill(t("unit_mm"), { value: format(value) });
  const model = fill(t("aim_model"), {
    darts: format(view.darts),
    across: mm(view.model.sd_x),
    up: mm(view.model.sd_y),
  });
  return `${rows.join("")}<p class="muted aim-model">${escapeHtml(`${model} · ${offsetText(ui, view.model)}`)}</p>`;
}

// Leaderboard ------------------------------------------------------------------

// Records across all players: all time from the profiles, a period from the weeks.
const LEADERBOARD_RECORDS = [
  { key: "average", digits: 1 },
  { key: "checkout", digits: 0 },
  { key: "maximums", digits: 0 },
  { key: "best_501", digits: 0, lower: true, unit: "unit_darts" },
  { key: "mpr", digits: 2 },
  { key: "streak", digits: 0, unit: "unit_days", always: true },
  { key: "achievements", digits: 0 },
  { key: "darts", digits: 0 },
];
const PERIOD_WEEKS = { week: 1, month: 4 };
const PERIODS = ["all", "month", "week"];

function leaderboardRecords(profiles, achievements, period = "all") {
  const weeks = PERIOD_WEEKS[period] ?? null;
  const badges = new Map(badgesView(achievements).players.map((player) => [player.name.toLowerCase(), player]));
  const players = (Array.isArray(profiles?.attributes?.players) ? profiles.attributes.players : []).filter(
    (player) => player && named(player.name)
  );
  const rows = players.map((player) => {
    const earned = badges.get(player.name.toLowerCase());
    if (!weeks) {
      return {
        name: player.name,
        average: finite(player.average),
        checkout: finite(player.highest_checkout),
        maximums: finite(player.maximums),
        best_501: finite(player.fewest_darts?.["501"]),
        mpr: finite(player.best_mpr),
        streak: finite(player.best_streak),
        achievements: earned?.unlocked ?? null,
        darts: finite(player.darts_thrown),
      };
    }
    const range = trendWeeks(player.trend, weeks);
    const sums = addWeeks(range);
    const since = range[0]?.week ?? "9999";
    return {
      name: player.name,
      average: ratioOf(sums.x01_points, sums.x01_darts, 3),
      checkout: sums.highest_checkout,
      maximums: sums.maximums,
      best_501: sums.best_501,
      mpr: sums.best_mpr,
      streak: null,
      // Every tier unlocked since the first day of the period.
      achievements: (earned?.badges ?? []).reduce(
        (count, badge) => count + badge.dates.filter((date) => date.slice(0, 10) >= since).length,
        0
      ),
      darts: sums.darts,
    };
  });
  const records = LEADERBOARD_RECORDS.filter((record) => !weeks || !record.always)
    .map((record) => {
      const better = (a, b) => (record.lower ? a[record.key] - b[record.key] : b[record.key] - a[record.key]);
      const ranked = rows
        .filter((row) => row[record.key] !== null && row[record.key] > 0)
        .sort((a, b) => better(a, b) || a.name.localeCompare(b.name));
      // Equal values share their place.
      const places = ranked.map((row) => ({
        name: row.name,
        value: row[record.key],
        place: 1 + ranked.filter((other) => better(other, row) < 0).length,
      }));
      return { ...record, places };
    })
    .filter((record) => record.places.length);
  return { period: weeks ? period : "all", records };
}

function leaderboardRecordsHtml(view, ui, limit = 3) {
  const { t, format } = ui;
  const shown = (record, value) => {
    const number = format(value, record.digits);
    if (!record.unit) return number;
    return fill(t(record.unit === "unit_days" && value === 1 ? "unit_day" : record.unit), { value: number });
  };
  return view.records
    .map((record) => {
      const [leader, ...rest] = record.places.slice(0, Math.max(1, limit));
      const others = rest
        .map(
          (place) =>
            `<li><span class="place">${place.place}.</span><span class="who">${escapeHtml(place.name)}</span>` +
            `<span class="value">${escapeHtml(shown(record, place.value))}</span></li>`
        )
        .join("");
      return (
        `<div class="record" data-record="${record.key}"><div class="record-name">${escapeHtml(t(`record_${record.key}`))}</div>` +
        `<div class="record-leader"><span class="who">${escapeHtml(leader.name)}</span>` +
        `<span class="value">${escapeHtml(shown(record, leader.value))}</span></div>` +
        `${others ? `<ol class="record-places">${others}</ol>` : ""}</div>`
      );
    })
    .join("");
}

// Caller ---------------------------------------------------------------------

// Marks of a Cricket dart: a treble is three, the outer bull one, the bull two.
function cricketMarks(key, numbers) {
  if (key === "BULL" || key === "25") return numbers.includes(25) ? (key === "BULL" ? 2 : 1) : 0;
  const match = /^([SDT])(\d{1,2})$/.exec(key);
  return match && numbers.includes(Number(match[2])) ? "SDT".indexOf(match[1]) + 1 : 0;
}

// What a finished visit counted: the X01 score, Cricket marks or party points.
// Null where nothing fits: busts and game shots have calls of their own, Killer
// and the training games count no points, and a visit joined halfway is unknown.
function visitCount(view, keys, start) {
  const points = (list) => list.reduce((sum, key) => sum + keyScore(key), 0);
  if (view.mode === "idle") return { kind: "score", score: points(keys) };
  if (view.mode === "x01") {
    const { practice } = view;
    if (practice.bust || practice.won || start === null) return null;
    // Darts before the opening double score nothing, so the remaining score tells.
    return { kind: "score", score: start - practice.remaining };
  }
  if (view.mode === "cricket" && !view.cricket.won) {
    const { cricket } = view;
    // In Wild Mouse a dart marks its number, or doubles or triples once, and a bed once more.
    const marks =
      cricket.kind === "wild_mouse"
        ? keys.reduce((sum, key, index) => {
            const counted = cricket.counted[index];
            return sum + (WILD_TARGETS.includes(counted) ? 1 : cricketMarks(key, counted ? [Number(counted)] : []));
          }, Number(cricket.bed))
        : keys.reduce((sum, key) => sum + cricketMarks(key, cricket.numbers), 0);
    return { kind: "marks", marks };
  }
  // Killer counts lives, and in Golf the last dart counts, whenever the darts are pulled.
  const { party } = view;
  if (view.mode !== "party" || party.won || ["killer", "golf"].includes(party.kind)) return null;
  if (party.kind === "count_up") return { kind: "score", score: points(keys) };
  // Round the World moves on with every hit and Gotcha may bust: the integration counts.
  if (["round_the_world", "gotcha"].includes(party.kind)) {
    return party.bust || party.scored === null ? null : { kind: "score", score: party.scored };
  }
  if (party.kind === "baseball") {
    const inning = [Number(party.target)];
    return { kind: "runs", runs: keys.reduce((sum, key) => sum + cricketMarks(key, inning), 0) };
  }
  const aim = new Set(targetBeds(party.target));
  return { kind: "score", score: points(keys.filter((key) => hitBeds(key).some((bed) => aim.has(bed)))) };
}

// What the caller listens to: the darts a game counted, or the visit on the board between games.
function callerState(visit, view, previous = null) {
  const current = view ?? { mode: "idle" };
  const game = current.practice ?? current.cricket ?? current.party ?? null;
  const winner = game?.scores?.find((score) => score.player === game.winner);
  // Darts after a bust or a game shot are not among the darts of the game. Between games
  // and in the bull-off, the darts are those on the board.
  const idle = ["idle", "bulloff"].includes(current.mode) ? visitThrows(visit).map(dartKey) : [];
  const keys = game ? game.visit : (current.drill?.thrown ?? idle);
  // A checkout training has a remaining score, too.
  const remaining = current.practice?.remaining ?? current.drill?.remaining ?? null;
  const player = game?.player ?? null;
  const up = game ? upScore(game) : null;
  // The remaining score before the visit, which the visit's score is counted from: in
  // X01 as the integration says, so a state the card missed, such as the takeout between
  // two visits of a player alone, never adds the visit before to this one.
  const start =
    current.practice?.visitFrom ??
    (!keys.length
      ? remaining
      : previous?.mode === current.mode && previous?.player === player
        ? previous.start
        : null);
  // What a training or a party game aims at next; the checkout training has its route instead.
  const { drill, party } = current;
  const aim = drill
    ? !drill.finished && !CHECKOUT_DRILLS.includes(drill.kind) && drill.target
    : party && !party.won && party.winner === null && !party.needsPlayers && party.target;
  return {
    darts: keys.length,
    visit: keys.join(" "),
    count: visitCount(current, keys, start),
    mode: current.mode,
    // The numbers of Random and Hidden Cricket, which they draw for every leg.
    kind: game?.kind ?? null,
    numbers: current.cricket?.numbers ?? [],
    // A leg nobody has marked yet: one that has just begun.
    fresh: (current.cricket?.scores ?? []).every((score) => score.marks.every((mark) => mark === 0)),
    player,
    name: game?.name ?? null,
    bot: up?.bot === true,
    players: game?.scores?.length ?? 0,
    remaining,
    start,
    route: current.practice?.route ?? current.drill?.route ?? [],
    setup: current.practice?.setup?.leave ?? current.drill?.setup?.leave ?? null,
    target: aim || null,
    bust: game?.bust === true,
    // A visit that counts nothing more: a bust, in a game or a checkout training, which calls
    // no bust of its own.
    voided: game?.bust === true || current.drill?.bust === true,
    // When the board booked its last visit: a visit that came after it is another one, also
    // where the card missed the takeout in between.
    booked: newestVisit(visit) ?? null,
    won: game?.won === true,
    winner: game?.winner ?? null,
    winnerName: winner?.name ?? null,
    // The leg the round limit decided last, by when it ended, and its winner.
    limit: current.practice?.limit?.ended ?? null,
    limitName: current.practice?.limit?.name ?? null,
  };
}

// How the caller may call every dart: by its points or by its bed. Off calls none.
const DART_CALLS = ["off", "score", "bed"];
const dartCalls = (options) => (DART_CALLS.slice(1).includes(options.call_darts) ? options.call_darts : null);

// The darts of the visit the caller has not called yet: those after the darts it knew of
// this visit, a corrected dart included, or every dart of another player's visit. The darts
// on the board when a game starts or ends were thrown before, so they are not called again.
// Fewer darts after the board booked a visit are those of the next one, where the card
// missed the takeout of a player alone in a game without a score to count from.
function newDarts(previous, current) {
  if (previous.mode !== current.mode) return [];
  const darts = (state) => (state.visit ? state.visit.split(" ") : []);
  const next = current.booked !== previous.booked && current.darts < previous.darts;
  const same = previous.player === current.player && previous.start === current.start && !next;
  const known = same ? darts(previous) : [];
  const thrown = darts(current);
  const first = thrown.findIndex((key, index) => key !== known[index]);
  return first < 0 ? [] : thrown.slice(first);
}

// The calls between two states: the darts, a visit, a requirement and its route, a bust,
// a game shot or the next target.
function callerCalls(previous, current, options) {
  if (!previous) return [];
  const calls = [];
  const on = (key) => options[key] !== false;
  // Every dart as it lands, for players who cannot see the board, before what it decided.
  const by = dartCalls(options);
  if (by) calls.push(...newDarts(previous, current).map((key) => ({ kind: "dart", key, by })));
  const finished = current.darts === 3 && (previous.darts !== 3 || previous.visit !== current.visit);
  if (on("call_scores") && finished && current.count) {
    calls.push({ ...current.count });
    if (current.count.score === 180 && on("call_sounds")) calls.push({ kind: "fanfare" });
  }
  if (on("call_results") && current.bust && !previous.bust) calls.push({ kind: "bust" });
  if (on("call_results") && current.winner !== null && previous.winner === null) {
    calls.push({ kind: current.limit ? "limit_match" : "match", name: current.winnerName });
  } else if (on("call_results") && current.won && !previous.won && current.winner === null) {
    calls.push({ kind: "leg" });
  } else if (on("call_results") && current.limit !== previous.limit && current.limit && current.winner === null) {
    calls.push({ kind: "limit_leg", name: current.limitName });
  }
  // The numbers a leg drew follow the game shot of the leg before.
  if (on("call_scores")) calls.push(...drawnCalls(previous, current));
  const turn =
    current.player !== previous.player || current.remaining !== previous.remaining || previous.darts > 0;
  // The route exists only for a score the darts of a visit can finish; without
  // one, the caller names the score to leave.
  const next =
    ["x01", "drill"].includes(current.mode) &&
    current.darts === 0 &&
    turn &&
    current.winner === null &&
    current.remaining !== null;
  const up = on("call_checkouts") && next;
  const who = {
    name: current.name,
    ...(current.bot ? { bot: true } : {}),
    player: current.player,
    players: current.players,
  };
  if (up && current.route.length) {
    calls.push({ kind: "require", ...who, remaining: current.remaining });
  } else if (up && current.setup !== null) {
    calls.push({ kind: "setup", ...who, leave: current.setup });
  }
  // The route of the checkout: at the start of a visit, after what the player requires, and
  // whenever a dart leaves another one for the darts left, then with the score it finishes.
  // The bot needs none.
  const route = current.route.join(" ");
  const changed = current.remaining !== previous.remaining || route !== previous.route.join(" ");
  const aiming = next || (current.darts > 0 && current.darts < 3 && changed && current.winner === null);
  if (options.call_route === true && route && aiming && !current.voided && !current.bot) {
    calls.push({ kind: "route", route: current.route, ...(up ? {} : { remaining: current.remaining }) });
  }
  // The target of a training or a party game when it moves on, and for each player whose
  // turn comes, except the bot.
  const aim = current.target !== previous.target || current.player !== previous.player;
  if (options.call_target === true && current.target !== null && aim && !current.bot) {
    calls.push({ kind: "target", target: current.target });
  }
  return calls;
}

// A bed as a caller says it, as the integration's callers do: "Treble 20", "Double 16",
// "5" for a single, "25", "Bull" or "Miss".
function bedWords(key, t) {
  if (key === "MISS") return t("say_dart_miss");
  if (key === "BULL") return t("say_dart_bull");
  const [, ring, number] = /^([SDT])(\d+)$/.exec(key) ?? [];
  if (!ring || ring === "S") return number ?? key;
  return fill(t(ring === "D" ? "say_dart_double" : "say_dart_treble"), { number });
}

// A target as a caller says it: any double or treble, the bull where both of its beds count,
// the bullseye where only it does, a number or a bed.
function targetWords(target, t) {
  if (target === "D") return t("any_double");
  if (target === "T") return t("any_treble");
  if (target === "25") return t("say_dart_bull");
  return ["50", "BULL"].includes(target) ? t("say_bullseye") : bedWords(target, t);
}

// Random Cricket names the numbers it drew when a leg begins; Hidden Cricket a number as
// soon as a dart shows it. A game that comes back with marks on the board, as after a reload
// of the integration, is one the caller has named already.
function drawnCalls(previous, current) {
  const same = previous.kind === current.kind;
  const drawn = previous.numbers.join() !== current.numbers.join();
  if (current.kind === "random_cricket" && drawn && (same || current.fresh)) {
    return [{ kind: "numbers", numbers: current.numbers.filter((number) => number !== 25) }];
  }
  if (current.kind !== "hidden_cricket" || !same) return [];
  return current.numbers
    .filter((number, slot) => number !== null && previous.numbers[slot] === null)
    .map((number) => ({ kind: "shown", number }));
}

// A call as the caller says it.
function callerText(call, t) {
  if (call.kind === "numbers") return fill(t("say_numbers"), { numbers: call.numbers.join(", ") });
  if (call.kind === "shown") return fill(t("say_shown"), { number: call.number });
  if (call.kind === "dart") {
    return call.by === "score" && call.key !== "MISS" ? String(keyScore(call.key)) : bedWords(call.key, t);
  }
  if (call.kind === "route") {
    const route = call.route.map((key) => bedWords(key, t)).join(", ");
    return call.remaining === undefined ? route : fill(t("say_route"), { remaining: call.remaining, route });
  }
  if (call.kind === "target") return fill(t("say_target"), { target: targetWords(call.target, t) });
  if (call.kind === "score") return call.score === 0 ? t("say_no_score") : String(call.score);
  if (call.kind === "marks") {
    if (call.marks === 0) return t("say_no_score");
    return call.marks === 1 ? t("say_mark") : fill(t("say_marks"), { marks: call.marks });
  }
  if (call.kind === "runs") {
    if (call.runs === 0) return t("say_no_score");
    return call.runs === 1 ? t("say_run") : fill(t("say_runs"), { runs: call.runs });
  }
  if (call.kind === "bust") return t("say_bust");
  if (call.kind === "leg") return t("say_leg");
  if (["match", "limit_match", "limit_leg"].includes(call.kind)) {
    // Without a name the call ends with the match or the leg, before the punctuation of
    // the language.
    const key = { match: "say_match", limit_match: "say_limit_match", limit_leg: "say_limit_leg" }[call.kind];
    const words = call.name ? t(key) : t(key).replace(/,\s*\{name\}/, "");
    return fill(words, { name: call.name });
  }
  if (call.kind === "tournament_next") return fill(t("say_tournament_next"), { first: call.first, second: call.second });
  if (call.kind === "tournament_won") return fill(t("say_tournament_won"), { name: call.name });
  if (call.kind === "require" || call.kind === "setup") {
    // Alone, nobody needs a name; in a match, unnamed players have a number.
    const name = call.players > 1 ? playerName({ t }, call, true) : null;
    const [say, value] =
      call.kind === "require" ? ["say_require", { remaining: call.remaining }] : ["say_setup", { leave: call.leave }];
    return name ? fill(t(say), { name, ...value }) : fill(t(`${say}_alone`), value);
  }
  return "";
}

// One audio context for every card; browsers allow sound only after a tap.
const callerAudio = { unlocked: false, context: null };

// Voice packs -----------------------------------------------------------------
//
// A voice pack is a folder of /media/homedarts/voices with recorded calls, named as darts-caller
// names the files of its packs: 180.mp3, busted.mp3, gameshot.mp3, yr_40.mp3 or a player's name.
// The caller plays the sounds of a call one after the other through the audio context its tap
// unlocked, and says in the browser's voice what the pack lacks.

// The pack the card's settings name; none, empty or "browser" is the browser's voice.
function voicePackName(value) {
  const name = typeof value === "string" ? value.trim() : "";
  return name && name.toLowerCase() !== "browser" ? name : null;
}

// The sounds of a pack as Home Assistant lists them: key -> the addresses of its files in the
// media folder, the only ones the card loads. Null for a pack without sounds.
function voicePack(result) {
  const sounds = new Map();
  for (const [key, files] of Object.entries(result?.sounds ?? {})) {
    const urls = Array.isArray(files) ? files.filter((url) => typeof url === "string" && url.startsWith("/media/")) : [];
    if (urls.length) sounds.set(key, urls);
  }
  return sounds.size ? { sounds } : null;
}

// The sounds of a bed in darts-caller's packs, the first one a pack has counting: t20, d16,
// s5 or 5, bull for the 25, bullseye, and outside for a miss.
function bedSounds(key) {
  if (key === "MISS") return ["outside"];
  if (key === "BULL") return ["bullseye"];
  if (key === "25") return ["bull"];
  const bed = key.toLowerCase();
  return key.startsWith("S") ? [bed, key.slice(1)] : [bed];
}

// The sounds of a target after bs_target_is: any double, the bull, the bullseye, a number or a
// bed. Any treble has none in darts-caller's packs.
function targetSounds(target) {
  if (target === "D") return ["bs_any_double"];
  if (target === "T") return [];
  if (target === "50") return ["bullseye"];
  return /^\d+$/.test(target) && target !== "25" ? [target, `s${target}`] : bedSounds(target);
}

// The parts of a call as a pack says them: its recorded sounds, and the words of a name it has
// no sound for, whose file darts-caller names in lower case. Null when the pack cannot say the
// call, which the browser's voice then says whole. What a player requires is one sound, yr_40,
// or you_require and the score, c_40 or 40. A dart is the sound of its bed or of its points,
// a route the sounds of its beds, and a target bs_target_is and the target.
function callerSounds(call, has, t) {
  const sound = (key) => (has(key) ? { sound: key } : null);
  const one = (key) => (has(key) ? [{ sound: key }] : null);
  const name = (words) => sound(nameKey(words)) ?? { text: words };
  // Every part the first of its sounds that the pack has; without one for each part, none.
  const parts = (choices) => {
    const found = choices.map((keys) => keys.find(has));
    return found.every(Boolean) ? found.map((key) => ({ sound: key })) : null;
  };
  if (call.kind === "dart") {
    return parts([call.by === "score" && call.key !== "MISS" ? [String(keyScore(call.key))] : bedSounds(call.key)]);
  }
  if (call.kind === "route") {
    const score = call.remaining === undefined ? [] : [[`c_${call.remaining}`, String(call.remaining)]];
    return parts([...score, ...call.route.map(bedSounds)]);
  }
  if (call.kind === "target") return parts([["bs_target_is"], targetSounds(call.target)]);
  if (call.kind === "score") return one(String(call.score));
  if (call.kind === "bust") return one("busted");
  if (call.kind === "leg") return one("gameshot");
  if (call.kind === "match") {
    const shot = one("matchshot");
    return shot && call.name ? [...shot, name(call.name)] : shot;
  }
  if (call.kind !== "require") return null;
  const left = call.remaining;
  const score = sound(`c_${left}`) ?? sound(String(left));
  const require = one(`yr_${left}`) ?? (has("you_require") && score ? [{ sound: "you_require" }, score] : null);
  // Alone, nobody needs a name; in a match, unnamed players have a number.
  return require && call.players > 1 ? [name(playerName({ t }, call, true)), ...require] : require;
}

// The sounds of the packs, loaded once, and the calls waiting their turn: a call never talks
// over the one before. Switching the caller off starts a new round, which ends the calls of
// the one before.
const callerVoice = { queue: Promise.resolve(), round: 0, sounds: new Map(), playing: null };
// The decoded sounds kept for the next calls, the most recent last.
const KEPT_SOUNDS = 64;
// How much longer than its sound or its words a part of a call may take before the next one
// comes anyway, as when a suspended audio context never ends a sound.
const SOUND_GRACE = 1000;
const SPEECH_GRACE = 3000;
const SPEECH_PER_CHARACTER = 120;

// One of the files of a key, at random, as darts-caller plays them.
const soundUrl = (urls) => urls[Math.floor(Math.random() * urls.length)];

// A sound decoded for the audio context; one that failed is asked for again next time.
function loadSound(url, fetch, context) {
  const kept = callerVoice.sounds;
  const sound =
    kept.get(url) ??
    fetch(url)
      .then((response) => {
        if (!response.ok) throw new Error(`${url}: ${response.status}`);
        return response.arrayBuffer();
      })
      .then((data) => context.decodeAudioData(data));
  kept.delete(url);
  kept.set(url, sound);
  sound.catch(() => kept.delete(url));
  for (const old of [...kept.keys()].slice(0, -KEPT_SOUNDS)) kept.delete(old);
  return sound;
}

// Words in the browser's voice, in the language of the card; nothing without a voice.
function utter(text, lang) {
  const speech = window.speechSynthesis;
  if (!text || !speech || typeof SpeechSynthesisUtterance === "undefined") return null;
  const utterance = new SpeechSynthesisUtterance(text);
  // The words are those of the card's language, so the voice must be too.
  utterance.lang = lang;
  speech.speak(utterance);
  return utterance;
}

// A part of a call that ends by itself, or after a while at the latest.
function ended(target, events, wait) {
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      resolve();
    };
    const timer = setTimeout(done, wait);
    for (const event of events) target[event] = done;
  });
}

function playSound(buffer, context) {
  const source = context.createBufferSource();
  source.buffer = buffer;
  source.connect(context.destination);
  const end = ended(source, ["onended"], buffer.duration * 1000 + SOUND_GRACE);
  source.start();
  callerVoice.playing = source;
  return end;
}

function sayWords(text, lang) {
  const utterance = utter(text, lang);
  return utterance ? ended(utterance, ["onend", "onerror"], SPEECH_GRACE + text.length * SPEECH_PER_CHARACTER) : null;
}

// One call of a pack: its sounds one after the other, a name without a sound in the browser's
// voice. A sound that does not load leaves the whole call to the browser's voice; one the
// browser cannot play ends the call, and the next one still comes.
async function playCall(parts, words, { round, lang, fetch, context }) {
  let plan = parts;
  let sounds = [];
  try {
    sounds = await Promise.all(parts.map((part) => (part.url ? loadSound(part.url, fetch, context) : null)));
  } catch {
    plan = [{ text: words }];
  }
  try {
    for (const [index, part] of plan.entries()) {
      if (round !== callerVoice.round) return;
      await (part.url ? playSound(sounds[index], context) : sayWords(part.text, lang));
      callerVoice.playing = null;
    }
  } catch {
    // Nothing more of this call.
  }
}

// The caller falls silent: what it plays stops, and the calls waiting are dropped.
function silenceCaller() {
  callerVoice.round += 1;
  callerVoice.playing?.stop();
  callerVoice.playing = null;
  window.speechSynthesis?.cancel();
}

// Big moments at the board, celebrated without a word, as the banner and the caller say
// what happened: a glow in the colour of the moment, and confetti for a 180, a game shot and
// the match. Nothing of it moves the scoreboard, and it fades out by itself.
const CELEBRATION_GLOW = {
  max: GOLD,
  match: GOLD,
  leg: VISIT_COLORS.ton,
  ton40: VISIT_COLORS.high,
  ton: VISIT_COLORS.ton,
  nine: GOLD,
};
const CONFETTI = { max: 36, match: 48, leg: 28 };
const CONFETTI_COLORS = [GOLD, VISIT_COLORS.high, VISIT_COLORS.ton, "var(--ad-accent)", "#e5484d"];

// What the change from one caller state to the next celebrates, if anything: the match, a
// leg, or a finished visit of a 180, 140 or more, 100 or more, or nine marks in Cricket.
function celebrationOf(previous, current) {
  if (!previous) return null;
  if (current.winner !== null && previous.winner === null) return "match";
  if (current.won && !previous.won) return "leg";
  const finished = current.darts === 3 && (previous.darts !== 3 || previous.visit !== current.visit);
  const count = finished ? current.count : null;
  if (count?.kind === "marks") return count.marks >= 9 ? "nine" : null;
  if (count?.kind !== "score" || count.score < 100) return null;
  return count.score === 180 ? "max" : count.score >= 140 ? "ton40" : "ton";
}

// The glow and the confetti of a moment; every piece flies its own way, the same in every run.
function celebrationHtml(kind, round) {
  const count = CONFETTI[kind] ?? 0;
  const pieces = Array.from({ length: count }, (_, index) => {
    const angle = Math.round((index * 360) / count + (index % 3) * 11);
    const reach = 26 + ((index * 37) % 24);
    const color = CONFETTI_COLORS[index % CONFETTI_COLORS.length];
    return `<i style="--a:${angle}deg;--r:${reach}cqi;--d:${(index % 6) * 50}ms;--c:${color}"></i>`;
  });
  return (
    `<div class="moment ${kind}" data-round="${round}" style="--c:${CELEBRATION_GLOW[kind]}">` +
    `<div class="glow"></div>${pieces.join("")}</div>`
  );
}

function playFanfare() {
  const context = callerAudio.context;
  if (!context) return;
  const start = context.currentTime;
  [523.25, 659.25, 783.99, 1046.5].forEach((frequency, index) => {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "triangle";
    oscillator.frequency.value = frequency;
    const at = start + index * 0.14;
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(0.25, at + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + (index === 3 ? 0.9 : 0.3));
    oscillator.connect(gain).connect(context.destination);
    oscillator.start(at);
    oscillator.stop(at + 1);
  });
}

// Board status shared by the live and status cards.
// How long a hint shows after a tap.
const HINT_SECONDS = 5;

// What the status says while a game goes on; it keeps the width of the longest.
const PLAY_STATUSES = ["status_ready", "status_full", "status_takeout", "status_hand"];
// The same on a dartboard without Autodarts.
const MANUAL_STATUSES = ["status_manual", "status_manual_full"];

function boardStatus(stateOf) {
  const on = (name) => stateOf(name)?.state === "on";
  const connected = stateOf("connected");
  const detection = stateOf("detection")?.state;
  const status = String(stateOf("status")?.state || "").toLowerCase();
  // A dartboard without Autodarts waits for darts entered by hand; three make a visit.
  if (status === "manual") {
    return visitThrows(stateOf("visit")).length >= 3 ? ["takeout", "status_manual_full"] : ["ready", "status_manual"];
  }
  if (!connected || connected.state !== "on") return ["offline", "status_offline"];
  if (on("calibrating") || status === "calibrating") return ["calibrating", "status_calibrating"];
  if (on("cameraProblem")) return ["problem", "status_problem"];
  if (status === "starting") return ["stopped", "status_starting"];
  if (status === "stopping") return ["stopped", "status_stopping"];
  if (detection === "off" || status === "stopped") return ["stopped", "status_stopped"];
  if (status.includes("takeout") || on("takeoutPartial")) return ["takeout", "status_takeout"];
  if (on("hand")) return ["takeout", "status_hand"];
  if (Number(stateOf("numThrows")?.state) >= 3) return ["takeout", "status_full"];
  return ["ready", "status_ready"];
}

// Whether detection runs: the detection switch tells, or without it the board status.
function detectionRunning(stateOf, status) {
  const detection = stateOf("detection");
  return detection ? detection.state === "on" : !["stopped", "offline"].includes(status);
}

// Dashboard strategy -------------------------------------------------------

const SETTING_KEYS = [
  "switch.auto_calibrate_on_start",
  "switch.auto_calibrate",
  "switch.auto_distortion",
  "select.standby_minutes",
  "switch.free_stuck_takeout",
];

const PRACTICE_KEYS = [
  "select.practice_game",
  "number.practice_players",
  "number.practice_legs",
  "number.practice_sets",
  "select.practice_in_mode",
  "select.practice_out_mode",
  "select.practice_bull_mode",
  "number.practice_max_rounds",
  "switch.practice_bull_off",
  "switch.practice_bull_off_distance",
  "switch.practice_teams",
  "switch.practice_three_in_a_bed",
  "switch.practice_personal_routes",
  "select.practice_golf_holes",
  "number.practice_count_up_rounds",
  "switch.practice_bermuda_halve_on_miss",
  "select.practice_round_the_world_order",
  "number.practice_gotcha_target",
  "number.practice_bot_level",
  "number.practice_bot_delay",
  "switch.practice_manual_entry",
  "button.practice_new_leg",
  "button.practice_new_match",
];

// The settings of the next tournament and its buttons; the sensor gets a tile.
const TOURNAMENT_KEYS = [
  "select.tournament_format",
  "select.tournament_game",
  "text.tournament_players",
  "number.tournament_groups",
  "number.tournament_advance",
  "number.tournament_pause",
  "number.tournament_summary",
  "switch.tournament_third_place",
  "switch.tournament_random_draw",
  "button.tournament_start",
  "button.tournament_next_match",
  "button.tournament_stop",
];

// A name pattern such as "Practice {name}" or "{name} de la partie" that finds the {name}.
function namePattern(text) {
  const escape = (part) => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const [before, after = ""] = text.split("{name}");
  return new RegExp(`^${escape(before)}(.+)${escape(after)}$`, "i");
}

// An entity's name without its board and without the section it sits in, so
// "Autodarts Board Practice players" reads "Players" under "Practice", and
// "Joueurs de la partie" reads "Joueurs" under "Partie".
function rowName(hass, entityId, board, section) {
  let name = hass?.states?.[entityId]?.attributes?.friendly_name;
  if (typeof name !== "string") return null;
  if (board && name.toLowerCase().startsWith(`${board.toLowerCase()} `)) name = name.slice(board.length + 1);
  // The section's name pattern, such as namePattern("Practice {name}").
  name = (section?.exec(name)?.[1] ?? name).trim();
  return name ? name[0].toUpperCase() + name.slice(1) : null;
}

// What the views of one board share: its entities, their rows and the view names.
function boardContext(hass, t, deviceId, number, count) {
  const index = entityIndex(hass, deviceId);
  const id = (key) => index[key]?.[0];
  const device = hass.devices?.[deviceId];
  const name = device?.name_by_user || device?.name || "HomeDarts";
  // Rows and graphs name their entities briefly, the board is the view's. A section such as
  // "practice" leaves out what the names of its entities share, after "practice_entity".
  const patterns = {};
  const row = (entity, section) => {
    const pattern = section && (patterns[section] ??= namePattern(t(`${section}_entity`)));
    const text = rowName(hass, entity, name, pattern);
    if (!text) return entity;
    // The game select is the practice section itself.
    return { entity, name: section && text.toLowerCase() === t(section).toLowerCase() ? t("practice_game_row") : text };
  };
  return {
    t,
    index,
    id,
    // The state of an entity of the board by its key.
    state: (key) => hass.states?.[id(key)],
    row,
    rows: (keys, section) => keys.map(id).filter(Boolean).map((entity) => row(entity, section)),
    // Several boards get their own set of views.
    suffix: count > 1 ? ` · ${name}` : "",
    slug: count > 1 ? `-${number + 1}` : "",
    card: (type, options = {}) => ({ type: `custom:${type}`, device_id: deviceId, ...options }),
  };
}

const FULL = { grid_options: { columns: "full" } };
// A tile as wide as its section, so that long names such as the detection's correction
// rate stay whole on every screen.
const tile = (row) => ({ type: "tile", ...FULL, ...(typeof row === "string" ? { entity: row } : row) });

// The live card alone, so the board and the game stay in sight on every screen.
function liveDashboardView(board) {
  return {
    title: `${board.t("view_live")}${board.suffix}`,
    path: `live${board.slug}`,
    icon: "mdi:bullseye-arrow",
    type: "sections",
    max_columns: 2,
    sections: [{ type: "grid", column_span: 2, cards: [board.card(CARD_TYPE, FULL)] }],
  };
}

// The rules, players and start scores of the practice game and the settings of a
// tournament, in a view of their own beside the live view.
function gamesDashboardView(board) {
  const { t } = board;
  const practice = board.rows(PRACTICE_KEYS, "practice");
  const names = (board.index["text.practice_player"] ?? []).map((entity) => board.row(entity, "practice"));
  const starts = (board.index["number.practice_start"] ?? []).map((entity) => board.row(entity, "practice"));
  const controls = [
    { type: "heading", heading: t("practice") },
    { type: "entities", entities: practice },
    ...(names.length ? [{ type: "entities", title: t("practice_names"), entities: names }] : []),
    ...(starts.length ? [{ type: "entities", title: t("practice_starts"), entities: starts }] : []),
  ];
  const tournament = board.rows(TOURNAMENT_KEYS, "tournament");
  const stage = board.id("sensor.tournament");
  const tournamentCards = [
    { type: "heading", heading: t("tournament") },
    ...(stage ? [tile(stage)] : []),
    { type: "entities", entities: tournament },
  ];
  const sections = [
    ...(practice.length ? [{ type: "grid", column_span: 2, cards: controls }] : []),
    ...(tournament.length ? [{ type: "grid", column_span: 2, cards: tournamentCards }] : []),
  ];
  if (!sections.length) return null;
  return {
    title: `${t("view_games")}${board.suffix}`,
    path: `games${board.slug}`,
    icon: "mdi:tune-variant",
    type: "sections",
    max_columns: 2,
    sections,
  };
}

// Options of the scoreboard view that the dashboard's own settings may set.
const STRATEGY_SCOREBOARD = [
  "caller",
  "caller_voice",
  "call_darts",
  "call_route",
  "call_target",
  "keypad",
  "corrections",
  "idle",
  "lobby_games",
  "idle_panels",
  "fullscreen_button",
  "keep_awake",
];

// The options set in the dashboard's settings, without the empty ones.
function scoreboardOptions(config) {
  const chosen = config?.scoreboard && typeof config.scoreboard === "object" ? config.scoreboard : {};
  const set = (value) => value !== undefined && value !== null && value !== "" && !(Array.isArray(value) && !value.length);
  return Object.fromEntries(STRATEGY_SCOREBOARD.filter((key) => set(chosen[key])).map((key) => [key, chosen[key]]));
}

// The scoreboard fills the screen of a tablet or TV at the board, with the options of
// the dashboard's settings: the dashboard stays automatic, so later releases reach it.
function scoreboardDashboardView(board, options = {}) {
  return {
    title: `${board.t("view_scoreboard")}${board.suffix}`,
    path: `scoreboard${board.slug}`,
    icon: "mdi:scoreboard-outline",
    panel: true,
    cards: [board.card(SCOREBOARD_TYPE, { full_height: true, ...options })],
  };
}

// Options of the overlay view that the dashboard's own settings may set.
const STRATEGY_OVERLAY = ["overlay", "overlay_layout", "overlay_color"];

// The overlay options set in the dashboard's settings, without the empty ones.
function overlayOptions(config) {
  const chosen = config?.overlay_view && typeof config.overlay_view === "object" ? config.overlay_view : {};
  return Object.fromEntries(
    STRATEGY_OVERLAY.filter((key) => typeof chosen[key] === "string" && chosen[key]).map((key) => [key, chosen[key]])
  );
}

// The scoreboard as the overlay of a stream, for a browser source of OBS: a view that
// the tabs leave out, at the address of the dashboard with /overlay at its end. It is
// see-through and lies along the bottom of the picture unless the settings say otherwise.
function overlayDashboardView(board, options = {}) {
  return {
    title: `${board.t("view_overlay")}${board.suffix}`,
    path: `overlay${board.slug}`,
    icon: "mdi:video-outline",
    subview: true,
    panel: true,
    cards: [board.card(SCOREBOARD_TYPE, { overlay: "transparent", ...options })],
  };
}

// Goals, graphs of darts, averages and practice legs, and the training settings.
function trainingTrends(board) {
  const { t, id, rows } = board;
  const bars = (title, key) => ({
    type: "statistics-graph",
    title,
    entities: rows([key]),
    stat_types: ["change"],
    period: "day",
    chart_type: "bar",
    days_to_show: 30,
  });
  const week = (title, entities) => ({ type: "history-graph", title, entities, hours_to_show: 168 });
  const trends = [];
  const goals = rows(["number.training_daily_goal", "sensor.darts_today", "sensor.training_streak", "sensor.personal_best"]);
  if (goals.length) trends.push({ type: "entities", title: t("goals_and_bests"), entities: goals });
  if (id("sensor.training_darts")) trends.push(bars(t("darts_per_day"), "sensor.training_darts"));
  if (id("sensor.training_average")) trends.push(week(t("average_trend"), rows(["sensor.training_average"])));
  if (id("sensor.practice_legs_played")) trends.push(bars(t("practice_legs_per_day"), "sensor.practice_legs_played"));
  const practice = rows([
    "sensor.practice_first_9_average",
    "sensor.practice_checkout_rate",
    "sensor.practice_doubles_rate",
  ]);
  if (practice.length) trends.push(week(t("practice_trend"), practice));
  const settings = rows(["switch.training_auto_start", "number.training_idle_timeout"]);
  if (settings.length) trends.push({ type: "entities", title: t("training_settings"), entities: settings });
  return trends;
}

function trainingDashboardView(board) {
  const trends = trainingTrends(board);
  return {
    title: `${board.t("view_training")}${board.suffix}`,
    path: `training${board.slug}`,
    icon: "mdi:chart-box-outline",
    type: "sections",
    max_columns: 2,
    sections: [
      { type: "grid", column_span: 2, cards: [board.card(TRAINING_TYPE, FULL)] },
      ...(board.id("sensor.favourite_double")
        ? [{ type: "grid", column_span: 2, cards: [board.card(DOUBLES_TYPE, FULL)] }]
        : []),
      ...(trends.length ? [{ type: "grid", column_span: 2, cards: trends }] : []),
    ],
  };
}

// The players and their records, once a player has a profile.
function playersDashboardView(board) {
  const players = board.state("sensor.player_profiles")?.attributes?.players;
  if (!Array.isArray(players) || !players.length) return null;
  return {
    title: `${board.t("view_players")}${board.suffix}`,
    path: `players${board.slug}`,
    icon: "mdi:account-group",
    type: "sections",
    max_columns: 2,
    sections: [
      { type: "grid", column_span: 2, cards: [board.card(PLAYERS_TYPE, FULL)] },
      { type: "grid", column_span: 2, cards: [board.card(LEADERBOARD_TYPE, FULL)] },
    ],
  };
}

// The status card, the board settings, the software update and the detection quality;
// a dartboard without Autodarts has none of them.
function boardDashboardView(board) {
  if (board.state("sensor.local_status")?.state === "manual") return null;
  const settings = board.rows(SETTING_KEYS);
  const maintenance = [{ type: "heading", heading: board.t("board_settings") }];
  if (settings.length) maintenance.push({ type: "entities", entities: settings });
  maintenance.push(...board.rows(["update.board_software", "sensor.correction_rate"]).map(tile));
  return {
    title: `${board.t("view_board")}${board.suffix}`,
    path: `board${board.slug}`,
    icon: "mdi:cog-outline",
    type: "sections",
    max_columns: 2,
    sections: [
      { type: "grid", cards: [board.card(STATUS_TYPE, FULL)] },
      ...(maintenance.length > 1 ? [{ type: "grid", cards: maintenance }] : []),
    ],
  };
}

// A complete dashboard for every board: live play, the scoreboard, training, players and maintenance.
function dashboardStrategy(hass, config = {}) {
  const t = (key) => translate(hass, key);
  const title = config.title || "HomeDarts";
  // A board removed since the dashboard was set up must not leave views without entities.
  const devices = (config.device_id ? [config.device_id] : homedartsDevices(hass)).filter((id) =>
    knownDevice(hass, id)
  );
  if (!devices.length) {
    const content = t(config.device_id ? "strategy_board_missing" : "strategy_no_board");
    return { title, views: [{ title: "HomeDarts", cards: [{ type: "markdown", content }] }] };
  }
  const options = scoreboardOptions(config);
  const overlay = overlayOptions(config);
  const views = devices.flatMap((deviceId, number) => {
    const board = boardContext(hass, t, deviceId, number, devices.length);
    return [
      liveDashboardView(board),
      scoreboardDashboardView(board, options),
      trainingDashboardView(board),
      playersDashboardView(board),
      gamesDashboardView(board),
      boardDashboardView(board),
      overlayDashboardView(board, overlay),
    ].filter(Boolean);
  });
  return { title, views };
}

// Editor forms ---------------------------------------------------------------

const deviceField = { name: "device_id", selector: { device: { filter: { integration: "homedarts" } } } };
const titleField = { name: "title", selector: { text: {} } };
const toggles = (names, defaults) => ({
  type: "grid",
  name: "",
  schema: names.map((name) => ({ name, selector: { boolean: {} }, default: defaults[name] })),
});
const dropdown = (name, prefix, values) => ({
  name,
  selector: {
    select: { mode: "dropdown", options: values.map((value) => ({ value, label: pageText(`${prefix}_${value}`) })) },
  },
});
// The colour picker of Home Assistant: theme colours, or any colour typed in.
const colorField = (name, defaultColor) => ({
  name,
  selector: { ui_color: defaultColor ? { default_color: defaultColor } : {} },
});
const accentField = colorField("accent_color", "primary");
// The voice pack of the caller, a folder of the media folder.
const voiceField = { name: "caller_voice", selector: { text: {} } };
// Every dart called by its points or its bed, for players who cannot see the board well.
const dartCallsField = () => dropdown("call_darts", "call_darts", DART_CALLS);
// Where the overlay of a stream lies in the picture, and the colour that a chroma key takes out.
const overlayLayoutField = () => dropdown("overlay_layout", "overlay_layout", OVERLAY_LAYOUTS);
const overlayColorField = { name: "overlay_color", selector: { text: {} } };
// Named players to pick from; any other name can be typed in.
const playerField = (helper) => ({
  name: "player",
  ...(helper ? { helper } : {}),
  selector: {
    select: {
      mode: "dropdown",
      custom_value: true,
      options: profileNames(pageHass).map((name) => ({ value: name, label: name })),
    },
  },
});

const FORM_HELPERS = {
  device_id: "device_helper",
  player: "player_helper",
  accent_color: "color_helper",
  highlight_color: "highlight_color_helper",
  caller_options: "caller_options_helper",
  caller_voice: "caller_voice_helper",
  call_darts: "call_darts_helper",
  lobby_section: "lobby_section_helper",
  lobby_games: "lobby_games_helper",
  idle_section: "idle_section_helper",
  idle_panels: "idle_panels_helper",
  keypad: "keypad_helper",
  keep_awake: "keep_awake_helper",
  input_section: "input_section_helper",
  summary_seconds: "summary_seconds_helper",
  overlay_section: "overlay_section_helper",
  overlay_color: "overlay_color_helper",
};

// The games to offer in the editor: those of a board's practice select, or every game the card knows.
function gameOptions(hass) {
  const select = Object.values(hass?.entities || {}).find(
    (entity) => entity.platform === "homedarts" && entity.translation_key === "practice_game"
  );
  const options = hass?.states?.[select?.entity_id]?.attributes?.options;
  return (Array.isArray(options) ? options.map(String) : KNOWN_GAMES)
    .filter((game) => game !== "off")
    .map((game) => ({ value: game, label: gameName(pageText, /^\d+$/.test(game) ? Number(game) : game) }));
}

// Seconds in a box with their unit.
const secondsField = (name, min, max, defaults = SCOREBOARD_DEFAULTS) => ({
  name,
  selector: { number: { min, max, step: 1, mode: "box", unit_of_measurement: "s" } },
  default: defaults[name],
});

// Every field of a form, also those inside grids and expandable sections.
const formFields = (schema) => schema.flatMap((field) => (field.schema ? formFields(field.schema) : [field]));

// The editor form of a card: its fields in the page language, labels and help,
// and a check that sends options the form cannot show to the code editor.
function cardForm(schema, defaults) {
  const fields = formFields(schema);
  const options = new Map(
    fields
      .filter((field) => field.selector.select && !field.selector.select.custom_value)
      .map((field) => [field.name, field.selector.select.options])
  );
  return {
    schema,
    computeLabel: (field) => (field.name ? pageText(field.name) : undefined),
    computeHelper: (field) => {
      if (field.helper) return pageText(field.helper);
      if (FORM_HELPERS[field.name]) return pageText(FORM_HELPERS[field.name]);
      const standard = options.get(field.name)?.find((option) => option.value === defaults[field.name]);
      return standard ? fill(pageText("default_hint"), { value: standard.label }) : undefined;
    },
    assertConfig: (config) => {
      for (const field of fields) {
        const value = config?.[field.name];
        if (value === undefined || value === null || value === "") continue;
        // YAML reads 501 as a number; the option is the text "501".
        const allowed = (item) =>
          options.get(field.name).some((option) => option.value === (typeof item === "number" ? String(item) : item));
        const valid = options.has(field.name)
          ? field.selector.select.multiple
            ? Array.isArray(value) && value.every(allowed)
            : allowed(value)
          : field.selector.boolean
            ? typeof value === "boolean"
            : !field.selector.number || Number.isFinite(value);
        if (!valid) {
          throw new Error(fill(pageText("invalid_option"), { name: field.name, value: JSON.stringify(value) }));
        }
      }
    },
  };
}

const FORMS = {
  live: () => [
    deviceField,
    titleField,
    {
      type: "grid",
      name: "",
      schema: [
        dropdown("layout", "layout", ["auto", "horizontal", "vertical", "board"]),
        dropdown("board_style", "style", ["classic", "flat"]),
      ],
    },
    dropdown("highlight", "highlight", ["visit", "last", "none"]),
    toggles(
      [
        "blink",
        "show_markers",
        "show_numbers",
        "show_stats",
        "show_recent",
        "show_practice",
        "show_connection",
        "show_controls",
        "show_summary",
        "corrections",
        "keypad",
      ],
      DEFAULTS
    ),
    // Seconds the summary of a finished match stays; 0 until the next game starts.
    secondsField("summary_seconds", 0, 600, DEFAULTS),
    { type: "grid", name: "", schema: [accentField, colorField("highlight_color")] },
  ],
  training: () => [
    deviceField,
    titleField,
    {
      type: "grid",
      name: "",
      schema: [dropdown("mode", "mode", HEAT_MODES), dropdown("board_style", "style", ["muted", "classic", "flat"])],
    },
    playerField("heatmap_player_helper"),
    {
      name: "history_size",
      selector: { number: { min: 5, max: 60, step: 1, mode: "slider" } },
      default: TRAINING_DEFAULTS.history_size,
    },
    toggles(
      [
        "show_heatmap",
        "show_heatmap_controls",
        "show_stats",
        "show_bests",
        "show_top",
        "show_history",
        "show_sessions",
        "show_reset",
      ],
      TRAINING_DEFAULTS
    ),
    accentField,
  ],
  status: () => [
    deviceField,
    titleField,
    toggles(["show_connection", "show_system", "show_cameras", "show_controls"], STATUS_DEFAULTS),
    accentField,
  ],
  scoreboard: () => [
    deviceField,
    titleField,
    toggles(
      [
        "full_height",
        "show_visit",
        "show_status",
        "caller",
        "show_summary",
        "celebrations",
        "fullscreen_button",
        "keep_awake",
      ],
      SCOREBOARD_DEFAULTS
    ),
    secondsField("summary_seconds", 0, 600),
    // The calls matter only with the caller on, so they wait in a closed section.
    {
      type: "expandable",
      name: "caller_options",
      flatten: true,
      schema: [
        toggles(
          ["call_scores", "call_checkouts", "call_results", "call_sounds", "call_route", "call_target"],
          SCOREBOARD_DEFAULTS
        ),
        dartCallsField(),
        voiceField,
      ],
    },
    {
      type: "expandable",
      name: "lobby_section",
      flatten: true,
      schema: [
        toggles(["lobby"], SCOREBOARD_DEFAULTS),
        { name: "lobby_games", selector: { select: { multiple: true, mode: "dropdown", options: gameOptions(pageHass) } } },
      ],
    },
    {
      type: "expandable",
      name: "idle_section",
      flatten: true,
      schema: [
        toggles(["idle"], SCOREBOARD_DEFAULTS),
        { type: "grid", name: "", schema: [secondsField("idle_after", 10, 3600), secondsField("idle_interval", 3, 120)] },
        {
          name: "idle_panels",
          selector: {
            select: {
              multiple: true,
              mode: "list",
              options: IDLE_PANELS.map((panel) => ({ value: panel, label: pageText(`idle_panel_${panel}`) })),
            },
          },
        },
      ],
    },
    // Corrections are on, the keypad off: it needs Practice manual entry anyway.
    {
      type: "expandable",
      name: "input_section",
      flatten: true,
      schema: [toggles(["corrections", "keypad"], SCOREBOARD_DEFAULTS)],
    },
    // The overlay of a stream is for a browser source of OBS, not for the screen at the board.
    {
      type: "expandable",
      name: "overlay_section",
      flatten: true,
      schema: [
        {
          type: "grid",
          name: "",
          schema: [dropdown("overlay", "overlay", ["off", ...OVERLAY_MODES]), overlayLayoutField()],
        },
        overlayColorField,
      ],
    },
    accentField,
  ],
  players: () => [
    deviceField,
    titleField,
    toggles(
      ["show_head_to_head", "show_matches", "show_badges", "show_locked", "show_trends", "show_spread", "export"],
      PLAYERS_DEFAULTS
    ),
    {
      name: "trend_weeks",
      selector: { number: { min: 4, max: 12, step: 1, mode: "slider" } },
      default: PLAYERS_DEFAULTS.trend_weeks,
    },
    dropdown("export_format", "export_format", ["csv", "json"]),
    accentField,
  ],
  leaderboard: () => [
    deviceField,
    titleField,
    {
      type: "grid",
      name: "",
      schema: [
        dropdown("period", "period", PERIODS),
        { name: "limit", selector: { number: { min: 1, max: 5, step: 1, mode: "box" } }, default: LEADERBOARD_DEFAULTS.limit },
      ],
    },
    toggles(["show_period"], LEADERBOARD_DEFAULTS),
    accentField,
  ],
  doubles: () => [deviceField, titleField, playerField(), accentField],
};

// The dashboard's settings: the board, the title and, in a section of its own, what
// the scoreboard view offers, in the page language.
const strategyForm = (hass) => [
  deviceField,
  titleField,
  {
    type: "expandable",
    name: "scoreboard",
    schema: [
      toggles(["caller", "keypad", "corrections", "idle", "fullscreen_button", "keep_awake"], SCOREBOARD_DEFAULTS),
      voiceField,
      dartCallsField(),
      toggles(["call_route", "call_target"], SCOREBOARD_DEFAULTS),
      { name: "lobby_games", selector: { select: { multiple: true, mode: "dropdown", options: gameOptions(hass) } } },
      {
        name: "idle_panels",
        selector: {
          select: {
            multiple: true,
            mode: "list",
            options: IDLE_PANELS.map((panel) => ({ value: panel, label: translate(hass, `idle_panel_${panel}`) })),
          },
        },
      },
    ],
  },
  {
    type: "expandable",
    name: "overlay_view",
    schema: [
      {
        type: "grid",
        name: "",
        schema: [
          {
            name: "overlay",
            selector: {
              select: {
                mode: "dropdown",
                options: OVERLAY_MODES.map((value) => ({ value, label: translate(hass, `overlay_${value}`) })),
              },
            },
          },
          {
            name: "overlay_layout",
            selector: {
              select: {
                mode: "dropdown",
                options: OVERLAY_LAYOUTS.map((value) => ({ value, label: translate(hass, `overlay_layout_${value}`) })),
              },
            },
          },
        ],
      },
      overlayColorField,
    ],
  },
];

// Labels and help of the dashboard's settings that differ from those of the cards.
const STRATEGY_LABELS = { scoreboard: "strategy_scoreboard", overlay_view: "strategy_overlay" };
const STRATEGY_HELPERS = {
  ...FORM_HELPERS,
  device_id: "strategy_device_helper",
  scoreboard: "strategy_scoreboard_helper",
  overlay_view: "strategy_overlay_helper",
};

// Styles ----------------------------------------------------------------------

// Coloured text is mixed with the theme's text colour: darker on light themes,
// lighter on dark ones, so it stays readable on both.
// Building block, segmented control: buttons that switch the view of a card, one at a
// time, such as the heatmap's mode, whose darts, the period or the pad's keys and board.
const SEGMENTED_CSS = `
  .segmented {
    display: inline-flex; flex-wrap: wrap; gap: 2px; padding: 3px; border-radius: 999px;
    background: color-mix(in srgb, var(--primary-text-color) 6%, transparent);
  }
  .segmented button {
    font: inherit; font-size: 12px; font-weight: 600; padding: 4px 10px; border: 0; border-radius: 999px;
    cursor: pointer; color: var(--ad-muted-text); background: none; white-space: nowrap;
  }
  .segmented button[aria-pressed="true"] { color: #fff; background: var(--ad-accent-fill); }
  /* Finger-sized at a touch screen. */
  @media (any-pointer: coarse) { .segmented button { min-height: 40px; } }
`;

const BASE_CSS = `
  :host {
    display: block;
    --ad-ok-text: color-mix(in srgb, ${STATUS_COLORS.ready} 65%, var(--primary-text-color, #212121));
    --ad-error-text: color-mix(in srgb, ${STATUS_COLORS.problem} 75%, var(--primary-text-color, #212121));
    --ad-warn-text: color-mix(in srgb, ${STATUS_COLORS.takeout} 45%, var(--primary-text-color, #212121));
    --ad-gold-text: color-mix(in srgb, ${GOLD} 45%, var(--primary-text-color, #212121));
    /* The accent as text on the card, and as a fill under white text: the theme's
       primary colour alone is too light for both on a light card. */
    --ad-accent-text: color-mix(in srgb, var(--ad-accent) 60%, var(--primary-text-color, #212121));
    --ad-accent-fill: color-mix(in srgb, var(--ad-accent) 70%, #000);
    /* Secondary text that stays readable on tinted tiles. */
    --ad-muted-text: color-mix(in srgb, var(--secondary-text-color) 80%, var(--primary-text-color, #212121));
    /* The tint a control takes under a pointer, and when it is pressed. */
    --ad-hover: color-mix(in srgb, var(--primary-text-color, #212121) 7%, transparent);
    --ad-press: color-mix(in srgb, var(--primary-text-color, #212121) 14%, transparent);
    /* How long a change of state takes, and how it moves: quick, and calm at its end. */
    --ad-fast: 150ms;
    --ad-slow: 240ms;
    --ad-ease: cubic-bezier(.2, .7, .2, 1);
  }
  [hidden] { display: none !important; }
  /* Read by assistive technology, not shown. */
  .visually-hidden {
    position: absolute !important; width: 1px; height: 1px; margin: -1px; padding: 0; border: 0;
    overflow: hidden; clip: rect(0 0 0 0); clip-path: inset(50%); white-space: nowrap;
  }
  /* Windows High Contrast shows no background colours: pressed buttons get an outline. */
  @media (forced-colors: active) {
    [aria-pressed="true"], [aria-checked="true"] { outline: 3px solid Highlight; outline-offset: -3px; }
  }
  /* A setup: its darts, then the score they leave. */
  .setup { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: center; }
  .setup .leave { font-weight: 700; color: var(--secondary-text-color); white-space: nowrap; }
  /* Clipped corners without a scroll container of its own, so sticky parts stick to the page. */
  ha-card { overflow: hidden; overflow: clip; height: 100%; }
  .root { container-type: inline-size; height: 100%; }
  header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .title {
    font-size: 16px; font-weight: 600; color: var(--primary-text-color);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  /* Building block, status: a glowing dot and its words, never the shape of a button. It
     is as wide as the longest words it takes during a game, its dot and words at its end,
     so nothing beside it moves while they change. On a card narrower than that, its words
     wrap instead of running over the edge. */
  .pill {
    display: inline-grid; justify-items: end; align-items: center; flex-shrink: 0; max-width: 100%; min-height: 28px;
    font-size: 12px; font-weight: 600;
    color: color-mix(in srgb, var(--ad-status) 45%, var(--primary-text-color, #212121));
    transition: color .4s;
  }
  .pill > span { grid-area: 1 / 1; display: inline-flex; align-items: center; gap: 8px; }
  .pill > span::before {
    content: ""; width: 8px; height: 8px; border-radius: 50%;
    background: var(--ad-status); box-shadow: 0 0 8px var(--ad-status);
  }
  .pill::after { content: attr(data-widest); grid-area: 1 / 1; padding-inline-start: 16px; visibility: hidden; }
  /* Building block, hint: the words of a tooltip in a bubble over the card, after a tap. */
  .hint-bubble {
    position: absolute; z-index: 5; max-width: min(260px, calc(100% - 16px)); padding: 6px 10px; border-radius: 8px;
    font-size: 12px; font-weight: 600; line-height: 1.35; text-align: center; pointer-events: none;
    color: var(--card-background-color, #fff); background: color-mix(in srgb, var(--primary-text-color, #212121) 90%, transparent);
    box-shadow: 0 4px 14px rgba(0, 0, 0, .3); transition: opacity var(--ad-fast) var(--ad-ease);
  }
  @starting-style { .hint-bubble { opacity: 0; } }
  .section-label {
    font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
    color: var(--ad-accent-text);
  }
  .muted { font-size: 11px; color: var(--ad-muted-text); }
  /* No word alone on a line: titles and labels balance their lines, text avoids orphans. */
  .title, .section-label, th { text-wrap: balance; }
  .muted, .pad-hint, .lobby-hint, .hint, .empty-hint { text-wrap: pretty; }
  /* Building block, cue: what a tap on a tile does, at its top right: a pencil edits, an
     arrow opens the details; inline after the words of a control that looks like text.
     The pencil turns to the accent while its tile is being edited. */
  .cue {
    position: absolute; top: 6px; right: 6px; width: 14px; height: 14px; overflow: visible; pointer-events: none;
    fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;
    color: var(--ad-muted-text);
  }
  .cue.inline { position: static; display: inline-block; width: .9em; height: .9em; margin-left: .3em; vertical-align: -.1em; }
  .picked .cue { color: var(--ad-accent-text); }
  /* A link that opens more below it turns its arrow up once open. */
  .cue.expand { transition: transform .2s; }
  [aria-expanded="true"] > .cue.expand { transform: rotate(180deg); }
  /* Building block, tile: a static one is a tinted area without a frame; one a tap edits
     or opens has a frame, which the pointer lights up, and a cue. */
  .tappable { position: relative; border: 1px solid var(--divider-color, rgba(127,127,127,.3)); }
  @media (hover: hover) { .tappable:not(:disabled):hover { border-color: var(--ad-accent); } }
  /* Building block, tag: a label such as a bed of a route, framed but never filled like a
     button; the one that comes next is tinted and bold. */
  .bed { border-radius: 8px; font-weight: 700; color: var(--ad-accent-text); border: 1px solid var(--ad-accent); }
  .bed:first-child { font-weight: 800; background: color-mix(in srgb, var(--ad-accent) 16%, transparent); }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip {
    display: inline-flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 999px;
    font: inherit; font-size: 12px; color: var(--secondary-text-color); cursor: pointer;
    border: 1px solid var(--divider-color, rgba(127,127,127,.25)); background: none;
  }
  .chip::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--chip, #9e9e9e); }
  .chip.on { --chip: ${STATUS_COLORS.ready}; }
  .chip.off { --chip: #9e9e9e; }
  .chip.alert { --chip: ${STATUS_COLORS.problem}; color: var(--ad-error-text); }
  /* A finger needs about 36 px, more than a mouse pointer. */
  @media (any-pointer: coarse) { .chip { min-height: 40px; } }
  .controls { display: flex; flex-wrap: wrap; gap: 8px; }
  .controls button, button.action {
    flex: 1 1 auto; min-height: 40px; padding: 0 14px; border-radius: 12px; cursor: pointer;
    font: inherit; font-size: 13px; font-weight: 600; color: var(--primary-text-color);
    border: 1px solid var(--divider-color, rgba(127,127,127,.3)); background: none;
    transition: background .2s, border-color .2s, color .2s;
  }
  :is(.controls button, button.action).primary {
    color: #fff; background: var(--ad-accent-fill); border-color: var(--ad-accent-fill);
  }
  :is(.controls button, button.action).primary.stop { background: none; color: var(--ad-accent-text); }
  /* Building block, control: every button answers. A mouse sees what it can click, a
     finger feels its press, a keyboard sees where it is; a disabled one fades, and the
     second tap a button asks for, to confirm, is red wherever it is. */
  button:not(:disabled) { cursor: pointer; }
  @media (hover: hover) {
    button:not(:disabled):hover { background-image: linear-gradient(var(--ad-hover), var(--ad-hover)); }
  }
  button:not(:disabled):active {
    background-image: linear-gradient(var(--ad-press), var(--ad-press)); transform: scale(.97);
  }
  button:disabled { opacity: .45; cursor: default; }
  :host button.confirm { color: #fff; background: ${STATUS_COLORS.problem}; border-color: ${STATUS_COLORS.problem}; }
  :is(button, [tabindex]):focus-visible { outline: 2px solid var(--ad-accent); outline-offset: 2px; }
  /* Building block, motion: a change of state glides, what appears as a whole fades in from
     a little below, and a device that asks for less motion gets none. Parts drawn anew
     with every tap do not fade in, or they would flicker. */
  button, .tappable {
    transition: background-color var(--ad-fast) var(--ad-ease), border-color var(--ad-fast) var(--ad-ease),
      color var(--ad-fast) var(--ad-ease), box-shadow var(--ad-fast) var(--ad-ease),
      opacity var(--ad-fast) var(--ad-ease), transform var(--ad-fast) var(--ad-ease);
  }
  .appear { transition: opacity var(--ad-slow) var(--ad-ease), transform var(--ad-slow) var(--ad-ease); }
  @starting-style { .appear { opacity: 0; transform: translateY(6px); } }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      transition-duration: 0s !important; animation-duration: 0s !important; animation-iteration-count: 1 !important;
    }
    button:not(:disabled):active { transform: none; }
  }
  svg { display: block; width: 100%; height: 100%; overflow: visible; }
  .number {
    font-size: 22px; font-weight: 700; line-height: 1; text-anchor: middle; dominant-baseline: central;
    pointer-events: none;
  }
  .note { font-weight: 800; color: var(--secondary-text-color); }
  .note.won { color: var(--ad-ok-text); }
  .note.bust { color: var(--ad-error-text); }
  .note.rethrow { color: var(--ad-warn-text); }
  .message { padding: 18px; color: var(--secondary-text-color); }
  /* The picture of the person a player is linked to. */
  .avatar {
    display: inline-block; flex-shrink: 0; width: 1.25em; height: 1.25em; margin-right: .35em;
    border-radius: 50%; object-fit: cover; vertical-align: -.2em;
    background: color-mix(in srgb, var(--primary-text-color) 10%, transparent);
  }
  ${SEGMENTED_CSS}
  /* Building block, link: a control that looks like text, with an arrow after it, which
     opens the details of what it names. */
  .link {
    display: inline-flex; align-items: center; padding: 0; border: 0; background: none;
    font: inherit; font-size: 13px; font-weight: 600; color: var(--ad-accent-text); text-align: start;
  }
  @media (hover: hover) { .link:not(:disabled):hover { text-decoration: underline; background-image: none; } }
  .link:not(:disabled):active { background-image: none; opacity: .7; }
  @media (any-pointer: coarse) { .link { min-height: 40px; } }
  /* What opens its details with a tap underlines its words under a mouse. */
  @media (hover: hover) { :is(.metric, .system-info, .camera-name):hover .opens { text-decoration: underline; } }
`;

// Building block, balanced grid: tiles in as many columns as fit, in rows as even as they
// can be, four tiles as two by two rather than three and one; a shorter last row stands
// in the middle, or its last tile fills it. A grid says how many tiles it has with a
// class such as "balanced n4"; beyond eight tiles it fills its rows as they come. The
// widths are those of the card, whose padding the tiles do not get.
function balancedCss(selector, min, gap, padding, most = 8) {
  const rules = [];
  for (let count = 2; count <= most; count += 1) {
    for (let fit = 1; fit <= count; fit += 1) {
      const rows = Math.ceil(count / fit);
      const columns = Math.ceil(count / rows);
      const from = fit === 1 ? 0 : fit * min + (fit - 1) * gap + padding;
      const to = fit === count ? 0 : (fit + 1) * min + fit * gap + padding - 0.02;
      const query = [from && `(min-width: ${from}px)`, to && `(max-width: ${to}px)`].filter(Boolean).join(" and ");
      const grid = `${selector}.balanced.n${count}`;
      const last = count - (rows - 1) * columns;
      const free = columns - last;
      let place = "";
      if (free > 0 && free % 2 === 0) place = ` ${grid} > :nth-child(${count - last + 1}) { grid-column-start: ${free / 2 + 1}; }`;
      else if (free > 0) place = ` ${grid} > :last-child { grid-column-end: -1; }`;
      rules.push(`  @container ${query} { ${grid} { grid-template-columns: repeat(${columns}, minmax(0, 1fr)); }${place} }`);
    }
  }
  return rules.join("\n");
}

// Each player on one line, the name beside the score, where the scores have little room.
const compactPlayers = (players, height) => `  @container (max-height: ${height}px) {
    ${players} { gap: 6px; }
    ${players} .player {
      flex-direction: row; justify-content: space-between; gap: 8px; padding: 4px 10px; border-radius: 14px;
    }
    ${players} .player .name { font-size: clamp(13px, 8cqh, 18px); text-align: left; min-height: 0; }
    ${players} .big { font-size: clamp(20px, 16cqh, 36px); }
    ${players} .player :is(.route, .members, .details) { display: none; }
  }`;

// The pad that corrects a dart of the visit, on the live card and the scoreboard: the
// keys, or the board to tap with its loupe.
const PAD_CSS = `
  .pad { font-size: clamp(14px, 1.8cqi, 22px); }
  .pad { display: grid; gap: clamp(6px, 1cqi, 12px); }
  .pad-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .pad-head .section-label { flex: 1; min-width: 8em; }
  .pad button {
    min-height: 48px; padding: 0 10px; border-radius: 12px; font: inherit; font-weight: 700; cursor: pointer;
    touch-action: manipulation; color: var(--primary-text-color);
    border: 2px solid var(--divider-color, rgba(127,127,127,.3));
    background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  }
  .pad button:disabled { opacity: .4; cursor: default; }
  .pad button[aria-pressed="true"] {
    color: #fff; background: var(--ad-accent-fill); border-color: var(--ad-accent-fill);
  }
  .pad .multiplier { min-width: 56px; }
  .pad .zoom {
    display: grid; place-items: center; width: 44px; height: 44px; min-height: 0; padding: 0; border-radius: 50%;
    background: var(--ha-card-background, var(--card-background-color, #fff));
  }
  .pad .zoom[aria-pressed="true"] {
    color: var(--ad-accent-text); border-color: var(--ad-accent); background: var(--ha-card-background, var(--card-background-color, #fff));
  }
  .pad .zoom svg { width: 24px; height: 24px; fill: none; stroke: currentColor; stroke-width: 2.2; stroke-linecap: round; }
  .pad-numbers { display: grid; grid-template-columns: repeat(10, minmax(0, 1fr)); gap: 6px; }
  /* A narrow pad keeps S, D, T and its keys or board in one row. */
  @container (max-width: 560px) {
    .pad-numbers { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .pad-score { --digit-span: 4; --answer-rows: 3; }
    .pad .multiplier { min-width: 44px; }
    .pad .segmented.view { padding: 2px; }
    .pad .segmented.view button { padding: 0 10px; }
  }
  /* The score view: the digits in as many rows as the numbers of the keys, two rows of
     six on a wide pad and four of three on a narrow one, which the answers to a question
     after the score and Cancel keep, so the pad keeps its height: the rows share it
     equally, so answers spanning three rows are as tall as three rows of digits. */
  .pad-score { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); grid-auto-rows: 1fr; gap: 6px; }
  .pad-score > button { grid-column: span var(--digit-span, 2); }
  .pad-score > :is(.answer, .ask-cancel) { grid-column: span var(--span); }
  .pad-score > .answer { grid-row: span var(--answer-rows, 1); }
  .pad-score .enter { color: #fff; background: var(--ad-accent-fill); border-color: var(--ad-accent-fill); }
  /* A question takes the line of the score typed, as tall as its large digits. */
  .score-line { display: flex; align-items: baseline; gap: .5em; flex: 1; min-width: 6em; min-height: 1.68em; }
  .score-line .typed { min-width: 1.8em; font-size: 1.4em; line-height: 1.2; font-weight: 800; font-variant-numeric: tabular-nums; }
  .score-line.ask { align-items: center; font-weight: 700; }
  .pad-extra { display: flex; flex-wrap: wrap; gap: 6px; }
  .pad-extra button { flex: 1 1 5.5em; }
  .pad .secondary { color: var(--ad-accent-text); border-color: var(--ad-accent); background: none; }
  /* The board instead of the keys: a tap says where the dart is. Zoomed in, it draws
     only within its own box, never over the keys and the edge of the card. */
  .pad .view { margin-left: auto; }
  .pad .segmented button { min-height: 40px; padding: 0 14px; border: 0; border-radius: 999px; font-size: inherit; color: var(--ad-muted-text); background: none; }
  .pad .segmented button[aria-pressed="true"] { color: #fff; background: var(--ad-accent-fill); }
  .pad .segmented.view svg {
    display: none; width: 22px; height: 22px; margin: auto; fill: none;
    stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;
  }
  .pad .segmented.view svg .dots { fill: currentColor; stroke: none; }
  /* A pad narrower than S, D, T and the three names of the views, as on a 360 pixel
     phone, shows the views as icons. */
  @container (max-width: 369px) {
    .pad .segmented.view svg { display: block; }
    .pad .segmented.view .view-name { display: none; }
    .pad .segmented.view button { min-width: 40px; }
  }
  .pad-wait { margin: 0; font-weight: 700; color: var(--ad-warn-text); }
  .pad-board {
    width: min(100%, 420px, 52vh); height: auto; aspect-ratio: 1; margin-inline: auto; overflow: hidden;
    cursor: crosshair; touch-action: manipulation; -webkit-tap-highlight-color: transparent;
  }
  .pad-board.disabled { opacity: .4; cursor: default; }
  /* Fingers on the board aim and zoom; the page does not scroll or zoom under them. */
  .pad-board[data-pad="spot"] { touch-action: none; }
  :is(.pad-board, .loupe) .spot { vector-effect: non-scaling-stroke; }
  /* The loupe above the finger that aims: the board magnified, a cross on the spot. */
  .loupe {
    position: absolute; z-index: 3; width: 132px; height: 132px; border-radius: 50%; overflow: hidden; pointer-events: none;
    border: 3px solid var(--ad-accent); box-shadow: 0 6px 18px rgba(0, 0, 0, .45);
    background: var(--primary-background-color, #111);
  }
  .loupe svg { display: block; width: 100%; height: 100%; }
  .loupe { transition: opacity var(--ad-fast) var(--ad-ease), transform var(--ad-fast) var(--ad-ease); }
  @starting-style { .loupe { opacity: 0; transform: scale(.8); } }
  .loupe::after {
    content: ""; position: absolute; inset: 0;
    background:
      linear-gradient(var(--ad-accent), var(--ad-accent)) center / 2px 34px no-repeat,
      linear-gradient(var(--ad-accent), var(--ad-accent)) center / 34px 2px no-repeat;
  }
  :is(.pad-board, .loupe) .spot { fill: #3182ce; stroke: #fff; stroke-width: 3; pointer-events: none; }
  :is(.pad-board, .loupe) .spot.seen { fill: none; stroke: var(--ad-accent); stroke-width: 4; stroke-dasharray: 7 5; pointer-events: auto; }
  .pad-hint { text-align: center; font-size: .8em; color: var(--ad-muted-text); }
  .undo-icon { margin-inline-end: .2em; }
  .pad button:focus-visible { outline: 3px solid var(--ad-accent); outline-offset: 2px; }
`;

const CSS = `${BASE_CSS}${PAD_CSS}
  .layout {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas: "header board" "visit board" "session board" "footer board";
    align-content: center;
    column-gap: 24px;
    row-gap: 16px;
    padding: 18px;
    box-sizing: border-box;
    height: 100%;
  }
  .layout.vertical {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas: "header" "visit" "board" "session" "footer";
  }
  .layout.board-only { grid-template-columns: minmax(0, 1fr); grid-template-areas: "header" "board"; }
  .layout.board-only :is(.visit, .session, .footer) { display: none; }
  @container (max-width: 560px) {
    .pad-extra { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); }
    .pad-extra > :is(.bull, .miss) { grid-column: span 2; }
    .pad-extra > .secondary { grid-column: span 3; line-height: 1.15; }
    .pad-extra > :is(.secondary:only-child, :not(.secondary) + .secondary:last-child) { grid-column: 1 / -1; }
  }
  @container (max-width: 520px) {
    .layout.auto {
      grid-template-columns: minmax(0, 1fr);
      grid-template-areas: "header" "visit" "board" "session" "footer";
    }
  }
  header { grid-area: header; }
  .visit { grid-area: visit; display: flex; flex-direction: column; gap: 12px; min-width: 0; }
  .session { grid-area: session; min-width: 0; }
  .footer { grid-area: footer; display: flex; flex-direction: column; gap: 12px; min-width: 0; }
  .board { grid-area: board; align-self: center; }
  .visit-label {
    font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
    color: var(--ad-accent-text);
  }
  .score-row { display: flex; align-items: baseline; gap: 10px; margin-top: 2px; }
  .score {
    font-size: clamp(48px, 16cqw, 84px); font-weight: 800; line-height: 1;
    letter-spacing: -0.04em; color: var(--primary-text-color); font-variant-numeric: tabular-nums;
  }
  .score-unit { font-size: 14px; color: var(--secondary-text-color); }
  .progress { margin-left: auto; font-size: 12px; color: var(--secondary-text-color); white-space: nowrap; }
  .slots { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .practice {
    display: grid; gap: 8px; padding: 10px 12px; border-radius: 14px;
    border: 1px solid color-mix(in srgb, var(--ad-accent) 45%, transparent);
    background: color-mix(in srgb, var(--ad-accent) 8%, transparent);
  }
  /* The game and what it says of the game take a line each from the start, so a longer
     line after the first visit moves nothing. */
  .practice-head { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; }
  .practice-meta { line-height: 1.4; min-height: 1.4em; }
  .practice-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
  .practice-remaining {
    font-size: 34px; font-weight: 800; line-height: 1; letter-spacing: -0.03em;
    color: var(--primary-text-color); font-variant-numeric: tabular-nums;
  }
  .practice-route { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 13px; }
  .practice-route .bed { padding: 3px 9px; }
  .practice-route .note { font-weight: 700; }
  .practice-route .note:not(.won, .bust) { font-size: 11px; font-weight: 400; }
  .scoreboard { display: grid; gap: 4px; }
  .player-score {
    display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: baseline;
    gap: 12px; padding: 4px 8px; border-radius: 8px;
  }
  .player-score.active { background: color-mix(in srgb, var(--ad-accent) 18%, transparent); }
  .player-score.out { opacity: .45; }
  .player-score .rest.lives { color: var(--ad-error-text); letter-spacing: .05em; }
  .player-score.winner { background: color-mix(in srgb, ${STATUS_COLORS.ready} 20%, transparent); }
  .player-score .who { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .player-score .rest { font-weight: 800; font-variant-numeric: tabular-nums; }
  .player-score .badge {
    margin-left: .3em; padding: 0 .35em; border-radius: 6px; font-size: 11px; font-weight: 600;
    color: var(--secondary-text-color); border: 1px solid var(--divider-color, rgba(127,127,127,.4));
  }
  .cricket { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; table-layout: fixed; }
  .cricket th, .cricket td { padding: 3px 6px; text-align: center; }
  .cricket thead th {
    font-size: 12px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .cricket th.aim .bed { font-size: 11px; padding: 1px 6px; }
  .cricket tr > :first-child { width: 4.2em; text-align: left; }
  .cricket tbody th { font-weight: 700; color: var(--secondary-text-color); }
  .cricket td { font-size: 17px; font-weight: 800; line-height: 1.1; color: var(--ad-accent-text); }
  .cricket tr.closed > * { opacity: 0.35; }
  .cricket tr.target th { color: var(--ad-accent-text); }
  .cricket tr.total td {
    font-size: 15px; color: var(--primary-text-color);
    border-top: 1px solid var(--divider-color, rgba(127,127,127,.25));
  }
  .cricket tr.detail td { font-size: 12px; font-weight: 600; color: var(--secondary-text-color); }
  .cricket .active { background: color-mix(in srgb, var(--ad-accent) 18%, transparent); }
  /* Where the player at the board scores, and what they had better close. */
  .cricket td.aim-score { box-shadow: inset 0 0 0 2px ${STATUS_COLORS.ready}; }
  .cricket td.aim-close { box-shadow: inset 0 0 0 2px ${STATUS_COLORS.takeout}; }
  .cricket .winner { background: color-mix(in srgb, ${STATUS_COLORS.ready} 20%, transparent); }
  .summary { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 12px; font-variant-numeric: tabular-nums; }
  .summary th, .summary td { padding: 2px 6px; text-align: center; }
  .summary tr > :first-child { width: 36%; text-align: left; }
  .summary thead th { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .summary thead th.caption { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--ad-accent-text); }
  .summary tbody th { font-weight: 400; color: var(--secondary-text-color); }
  .summary td { font-weight: 700; color: var(--primary-text-color); }
  .summary tr.result td { font-size: 17px; font-weight: 800; color: var(--ad-accent-text); }
  .summary .winner { background: color-mix(in srgb, ${STATUS_COLORS.ready} 20%, transparent); }
  .aim path {
    fill: color-mix(in srgb, var(--ad-accent) 35%, transparent);
    stroke: var(--ad-accent); stroke-width: 3; stroke-dasharray: 6 3;
  }
  .recent { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
  .recent-list { display: flex; flex-wrap: wrap; gap: 6px; }
  /* A visit gone by: its score after a dot in its colour, plain text and nothing to tap. */
  .recent-visit {
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--primary-text-color);
  }
  .recent-visit::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--bucket); }
  .slot {
    position: relative; padding: 10px 8px 9px; border-radius: 14px; text-align: center;
    border: 1px solid transparent;
    background: color-mix(in srgb, var(--primary-text-color) 4%, transparent);
    transition: border-color .3s, box-shadow .3s, background .3s;
  }
  .slot.empty { background: color-mix(in srgb, var(--primary-text-color) 2%, transparent); }
  .slot.latest {
    border-color: var(--ad-highlight);
    box-shadow: 0 0 0 1px var(--ad-highlight), 0 0 18px color-mix(in srgb, var(--ad-highlight) 35%, transparent);
  }
  .slot .index { font-size: 11px; color: var(--ad-muted-text); }
  .slot .segment { font-size: 22px; font-weight: 800; margin: 2px 0; color: var(--primary-text-color); }
  .slot .value { font-size: 12px; color: var(--ad-muted-text); font-variant-numeric: tabular-nums; }
  .slot.triple .segment { color: color-mix(in srgb, #ef6c57 80%, var(--primary-text-color)); }
  .slot.double .segment { color: color-mix(in srgb, #43b581 70%, var(--primary-text-color)); }
  .slot.bull .segment, .slot.outer-bull .segment { color: color-mix(in srgb, #e5484d 80%, var(--primary-text-color)); }
  .slot.miss .segment { color: var(--secondary-text-color); }
  /* A dart that counted nothing in a Cricket game. */
  .slot.dead .segment { color: var(--ad-muted-text); text-decoration: line-through 2px; }
  .slot > span { display: block; }
  button.slot { width: 100%; font: inherit; color: inherit; cursor: pointer; touch-action: manipulation; }
  button.slot:focus-visible { outline: 3px solid var(--ad-accent); outline-offset: 2px; }
  .slot.picked { border-color: var(--ad-accent); box-shadow: inset 0 0 0 2px var(--ad-accent); }
  /* The pad below the darts fits their column, however wide the card is. */
  .visit > .pad-area { margin-top: 2px; container-type: inline-size; }
  .stats { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 6px; margin-top: 8px; }
  .stat { min-width: 0; }
  .stat .value {
    font-size: 18px; font-weight: 700; color: var(--primary-text-color);
    font-variant-numeric: tabular-nums; white-space: nowrap;
  }
  /* A long name takes a second line in a narrow column instead of losing its end. */
  .stat .name { font-size: 11px; line-height: 1.25; color: var(--secondary-text-color); overflow-wrap: break-word; hyphens: auto; }
  .section-head { display: flex; justify-content: space-between; gap: 8px; }
  .since { font-size: 11px; color: var(--secondary-text-color); }
  .board { display: flex; justify-content: center; }
  .board-frame {
    width: clamp(180px, 42cqw, 380px); aspect-ratio: 1; border-radius: 50%;
    box-shadow: 0 0 42px 4px color-mix(in srgb, var(--ad-status) 55%, transparent);
    transition: box-shadow .5s;
  }
  .board-frame svg { border-radius: 50%; }
  .layout.vertical .board-frame, .layout.board-only .board-frame { width: min(100%, 420px); }
  @container (max-width: 520px) {
    .layout.auto .board-frame { width: min(100%, 360px); }
    .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); row-gap: 12px; }
  }
  .hit { fill: var(--ad-highlight); opacity: .88; pointer-events: none; }
  .blink .hit { animation: ad-blink .8s ease-in-out infinite alternate; }
  .dart .pin { fill: #3182ce; stroke: #fff; stroke-width: 2; }
  .dart text { font-size: 11px; font-weight: 700; line-height: 1; fill: #fff; text-anchor: middle; dominant-baseline: central; }
  .dart.latest .halo { fill: none; stroke: var(--ad-highlight); stroke-width: 2; animation: ad-pulse 1.6s ease-out infinite; transform-box: fill-box; transform-origin: center; }
  @keyframes ad-blink { from { opacity: .18; } to { opacity: .95; } }
  @keyframes ad-pulse { from { opacity: .9; transform: scale(.7); } to { opacity: 0; transform: scale(1.8); } }
  @media (prefers-reduced-motion: reduce) {
    .blink .hit, .dart.latest .halo { animation: none; }
  }
`;

const TRAINING_CSS = `${BASE_CSS}
  .training { display: flex; flex-direction: column; gap: 18px; padding: 18px; box-sizing: border-box; }
  .hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
  .average {
    font-size: clamp(44px, 14cqw, 72px); font-weight: 800; line-height: 1; letter-spacing: -0.04em;
    color: var(--primary-text-color); font-variant-numeric: tabular-nums;
  }
  .average-label { font-size: 12px; color: var(--secondary-text-color); margin-top: 4px; }
  .totals { display: flex; gap: 18px; }
  .daily { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 14px; }
  .streak {
    padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; white-space: nowrap;
    color: color-mix(in srgb, #ff8a00 55%, var(--primary-text-color, #212121));
    background: color-mix(in srgb, #ff8a00 14%, transparent);
  }
  .goal { flex: 1 1 180px; display: flex; align-items: center; gap: 8px; min-width: 0; }
  .goal-bar {
    flex: 1; height: 6px; border-radius: 999px; overflow: hidden;
    background: color-mix(in srgb, var(--primary-text-color) 10%, transparent);
  }
  .goal-bar span { display: block; height: 100%; border-radius: inherit; background: var(--ad-accent); transition: width .4s; }
  .goal.reached .goal-bar span { background: ${STATUS_COLORS.ready}; }
  .goal-text { font-size: 12px; color: var(--secondary-text-color); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .total .value { font-size: 22px; font-weight: 700; color: var(--primary-text-color); font-variant-numeric: tabular-nums; text-align: right; }
  .total .name { font-size: 11px; color: var(--secondary-text-color); text-align: right; }
  .body { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px; align-items: start; }
  .body.single { grid-template-columns: minmax(0, 1fr); }
  @container (max-width: 560px) { .body { grid-template-columns: minmax(0, 1fr); } }
  .heat { display: flex; flex-direction: column; align-items: center; gap: 10px; }
  .heat-frame { position: relative; width: min(100%, 380px); aspect-ratio: 1; }
  /* The hits of a tapped bed, over the bottom of the board. */
  .heat-caption {
    position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); padding: 3px 10px; border-radius: 999px;
    font-size: 12px; font-weight: 700; white-space: nowrap; pointer-events: none; color: var(--primary-text-color);
    background: var(--ha-card-background, var(--card-background-color, #fff)); box-shadow: 0 1px 4px rgba(0,0,0,.25);
  }
  .heat-caption:empty { opacity: 0; }
  .heat-bed { stroke: rgba(0,0,0,.25); stroke-width: .6; }
  .legend { width: min(100%, 320px); display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 8px; }
  .legend-bar { height: 8px; border-radius: 999px; }
  .side { display: flex; flex-direction: column; gap: 18px; min-width: 0; }
  .tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; border-radius: 14px; }
  .tile {
    min-width: 0; padding: 10px 8px; border-radius: 14px; text-align: center;
    background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  }
  .tile .value { font-size: 20px; font-weight: 800; color: var(--primary-text-color); font-variant-numeric: tabular-nums; white-space: nowrap; }
  /* A long name takes a second line on a phone instead of losing its end. */
  .tile .name { font-size: 11px; line-height: 1.25; color: var(--ad-muted-text); overflow-wrap: break-word; hyphens: auto; }
  .tile.hot .value { color: var(--ad-gold-text); }
  @container (max-width: 380px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .side > .details { align-self: flex-end; margin-top: -10px; }
  .bests dl { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 6px 18px; margin: 8px 0 0; }
  .bests dl > div { display: flex; justify-content: space-between; gap: 10px; min-width: 0; }
  .bests dt { font-size: 12px; color: var(--secondary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bests dd { margin: 0; font-size: 13px; font-weight: 700; color: var(--primary-text-color); font-variant-numeric: tabular-nums; white-space: nowrap; }
  /* The rows share their columns, so that every bar ends where the others do. */
  .top { display: grid; grid-template-columns: 3.2em minmax(0, 1fr) auto; gap: 6px 10px; }
  .top > .empty-hint { grid-column: 1 / -1; }
  .top-row { display: grid; grid-column: 1 / -1; grid-template-columns: subgrid; align-items: center; font-size: 13px; }
  .top-row .count { text-align: right; }
  .top-row .key { font-weight: 800; color: var(--primary-text-color); }
  .top-row .bar { height: 8px; border-radius: 999px; background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); overflow: hidden; }
  .top-row .fill { height: 100%; border-radius: inherit; }
  .top-row .count { color: var(--secondary-text-color); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .history-chart {
    position: relative; height: 104px; display: flex; align-items: stretch; gap: 4px; margin-top: 8px;
    container-type: inline-size;
  }
  @container (max-width: 560px) { .visit-bar.far { display: none; } }
  .visit-bar {
    flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; justify-content: flex-end; align-items: center;
  }
  .visit-bar .fill {
    width: 100%; max-width: 30px; min-height: 3px; border-radius: 5px 5px 2px 2px;
    height: calc((100% - 16px) * var(--height));
  }
  .visit-bar .label {
    font-size: 11px; font-weight: 700; line-height: 14px; margin-bottom: 2px;
    color: var(--secondary-text-color); font-variant-numeric: tabular-nums; white-space: nowrap;
  }
  .visit-bar.empty .fill { background: color-mix(in srgb, var(--primary-text-color) 7%, transparent); height: 3px; }
  .average-line {
    position: absolute; left: 0; right: 0; bottom: calc((100% - 16px) * var(--height));
    border-top: 1px dashed var(--secondary-text-color); opacity: .55; pointer-events: none;
  }
  .footer-row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
  .footer-row button.action { flex: 0 0 auto; }
  .footer-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
  .session-table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; font-variant-numeric: tabular-nums; }
  .session-table th {
    padding: 4px 6px; text-align: right; font-size: 11px; font-weight: 600; color: var(--secondary-text-color);
  }
  .session-table td {
    padding: 6px; text-align: right; color: var(--primary-text-color);
    border-top: 1px solid var(--divider-color, rgba(127,127,127,.2));
  }
  .session-table :is(th, td):first-child { text-align: left; }
  .empty-hint { font-size: 13px; color: var(--secondary-text-color); text-align: center; padding: 8px 0; }
  .heat-head { width: 100%; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
  .heat-controls { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
  .position { fill: #fff; fill-opacity: .85; stroke: rgba(0,0,0,.55); stroke-width: .6; }
  /* The darts of the current visit, like the pins of the live card. */
  .position.live { fill: #3182ce; fill-opacity: 1; stroke: #fff; stroke-width: 2; }
  /* The best aim of the aim map: a white ring on a dark one stands out on every color. */
  .aim-shadow { fill: none; stroke: rgba(0,0,0,.55); stroke-width: 5; }
  .aim-best { fill: none; stroke: #fff; stroke-width: 2.5; }
  .aim-dot { fill: #fff; stroke: rgba(0,0,0,.55); stroke-width: .8; }
  .aim-model { margin: 6px 0 0; font-size: 12px; }
  .heat .groups { width: 100%; display: grid; gap: 2px; }
  .group { display: grid; grid-template-columns: 3.4em minmax(0, 1fr) auto; gap: 10px; align-items: baseline; font-size: 13px; }
  .group-target {
    padding: 1px 0; border-radius: 8px; text-align: center; font-size: 12px; font-weight: 800;
    color: var(--ad-accent-text); border: 1px solid var(--ad-accent);
  }
  .group-change { font-size: 12px; font-weight: 700; white-space: nowrap; }
  .group-change.better { color: var(--ad-ok-text); }
  .group-change.worse { color: var(--ad-error-text); }
`;

const STATUS_CSS = `${BASE_CSS}
  .status-card { display: flex; flex-direction: column; gap: 16px; padding: 18px; box-sizing: border-box; }
  .manual-note { margin: 0; font-size: 13px; line-height: 1.45; }
  .detection {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 12px 14px; border-radius: 16px;
    background: color-mix(in srgb, var(--ad-status) 10%, transparent);
  }
  .detection .name { font-weight: 700; color: var(--primary-text-color); }
  .detection .state { font-size: 12px; color: var(--secondary-text-color); }
  .toggle {
    position: relative; width: 52px; height: 30px; flex-shrink: 0; border-radius: 999px; cursor: pointer;
    border: none; background: color-mix(in srgb, var(--primary-text-color) 20%, transparent); transition: background .2s;
  }
  .toggle::after {
    content: ""; position: absolute; top: 3px; left: 3px; width: 24px; height: 24px; border-radius: 50%;
    background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.3); transition: transform .2s;
  }
  .toggle[aria-checked="true"] { background: var(--ad-accent); }
  .toggle[aria-checked="true"]::after { transform: translateX(22px); }
  .toggle:disabled { opacity: .45; cursor: default; }
  .info { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }
${balancedCss(".info", 150, 8, 36)}
  .info-tile {
    display: flex; flex-direction: column; gap: 6px; min-width: 0; padding: 12px; border-radius: 14px;
    background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  }
  .info-tile .value { font-size: 15px; font-weight: 700; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .info-tile .badge {
    align-self: flex-start; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; cursor: pointer;
    border: none; font-family: inherit;
    color: var(--ad-warn-text); background: color-mix(in srgb, ${STATUS_COLORS.takeout} 16%, transparent);
  }
  .info-tile .badge.ok { color: var(--ad-ok-text); background: color-mix(in srgb, ${STATUS_COLORS.ready} 14%, transparent); cursor: default; }
  .metrics { display: flex; gap: 14px; flex-wrap: wrap; }
  .system-info {
    all: unset; display: block; cursor: pointer; overflow-wrap: anywhere;
  }
  .metric {
    all: unset; display: block; cursor: pointer; border-radius: 6px;
  }
  .metric .value { display: block; font-size: 15px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--primary-text-color); }
  .metric .name { display: block; font-size: 11px; color: var(--secondary-text-color); }
  .camera-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; }
${balancedCss(".camera-grid", 130, 8, 36)}
  .camera {
    display: flex; flex-direction: column; gap: 8px; padding: 12px; border-radius: 14px;
    border: 1px solid var(--divider-color, rgba(127,127,127,.25));
  }
  .camera.problem { border-color: ${STATUS_COLORS.problem}; background: color-mix(in srgb, ${STATUS_COLORS.problem} 8%, transparent); }
  .camera-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .camera-name { font-weight: 700; color: var(--primary-text-color); background: none; border: none; padding: 0; font: inherit; font-weight: 700; cursor: pointer; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: ${STATUS_COLORS.ready}; box-shadow: 0 0 6px ${STATUS_COLORS.ready}; }
  .camera.problem .dot { background: ${STATUS_COLORS.problem}; box-shadow: 0 0 6px ${STATUS_COLORS.problem}; }
  .camera .fps { font-size: 12px; color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
  .camera button.action { min-height: 32px; font-size: 12px; }
  /* On a touch screen the small controls grow to a finger's size; the switch by a
     transparent border, which keeps its look. */
  @media (any-pointer: coarse) {
    .toggle { box-sizing: content-box; border: 4px solid transparent; background-clip: padding-box; }
    .info-tile .badge, .camera-name, .camera button.action { min-height: 40px; }
    .system-info { display: flex; align-items: center; min-height: 40px; }
  }
`;

const SCOREBOARD_CSS = `${BASE_CSS}${PAD_CSS}
  /* Big moments: a glow around the scoreboard and confetti from its middle, over everything
     and in nobody's way, gone after two seconds and a half. */
  .celebrate {
    position: absolute; inset: 0; z-index: 4; overflow: hidden; pointer-events: none; border-radius: inherit;
  }
  .moment, .moment .glow { position: absolute; inset: 0; }
  .moment .glow {
    border-radius: inherit; opacity: 0;
    box-shadow: inset 0 0 clamp(40px, 9cqi, 140px) clamp(6px, 1.4cqi, 20px) var(--c);
    animation: moment-glow 1.8s ease-out forwards;
  }
  .moment i {
    position: absolute; left: 50%; top: 45%; width: clamp(6px, 1.1cqi, 14px); height: clamp(10px, 1.9cqi, 24px);
    border-radius: 2px; background: var(--c); opacity: 0;
    animation: moment-confetti 2.5s var(--d) cubic-bezier(.15, .75, .35, 1) forwards;
  }
  @keyframes moment-glow { 15% { opacity: 1; } 100% { opacity: 0; } }
  @keyframes moment-confetti {
    0% { opacity: 1; transform: translate(-50%, -50%) rotate(var(--a)) translateY(0) rotate(0deg); }
    75% { opacity: 1; }
    100% {
      opacity: 0; transform: translate(-50%, -50%) rotate(var(--a)) translateY(calc(-1 * var(--r))) rotate(600deg);
    }
  }
  @media (prefers-reduced-motion: reduce) { .moment { display: none; } }
  /* Secondary text sits on tinted tiles here: its darker mix stays readable on them. */
  .scoreboard {
    --ad-pad: clamp(14px, 2.4cqi, 32px);
    position: relative; display: flex; flex-direction: column; gap: clamp(12px, 2cqi, 24px);
    padding: var(--ad-pad); box-sizing: border-box;
  }
  /* Full height is the screen below Home Assistant's header: a banner, the visit or the
     keypad make the numbers smaller instead of pushing the page past the screen. The
     dynamic viewport leaves room for a phone's browser bar; older browsers use vh. On a
     phone the header also covers the status bar and the home indicator takes the bottom:
     their safe areas count as Home Assistant counts them for its own views. */
  .scoreboard.full {
    --ad-taken: calc(
      var(--header-height, 56px) + var(--safe-area-inset-top, env(safe-area-inset-top, 0px)) +
        var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px)) + 16px
    );
    height: calc(100vh - var(--ad-taken));
    height: calc(100dvh - var(--ad-taken));
  }
  /* The new game screen scrolls with the page, its start button stays at the bottom. */
  .scoreboard.full.choosing {
    height: auto;
    min-height: calc(100vh - var(--ad-taken));
    min-height: calc(100dvh - var(--ad-taken));
  }
  /* Full screen: the card alone on the screen, from edge to edge, without Home
     Assistant's header, so only the safe areas of a phone or tablet take room from the
     scoreboard. Where the new game screen is taller than the screen, the card scrolls in
     it. Two quick taps leave full screen instead of zooming. */
  :host(:fullscreen) { overflow-y: auto; background: var(--primary-background-color, #111); }
  :host(:fullscreen) ha-card { height: auto; min-height: 100%; border: none; border-radius: 0; }
  .scoreboard.fullscreen {
    --ad-taken: calc(
      var(--safe-area-inset-top, env(safe-area-inset-top, 0px)) +
        var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px))
    );
    touch-action: manipulation;
  }
  .heading { display: grid; gap: 2px; min-width: 0; }
  /* The title keeps its words whole: where the buttons beside it leave too little room,
     as on a phone, they follow in a row below it. That row is never wider than the card;
     where the buttons and the status do not fit in it, they wrap. */
  .scoreboard .title {
    font-size: clamp(18px, 3cqi, 36px); font-weight: 700; line-height: 1.15;
    white-space: normal; overflow: visible; text-overflow: clip; overflow-wrap: break-word;
  }
  .scoreboard > header { align-items: flex-start; flex-wrap: wrap; row-gap: 8px; }
  .scoreboard > header > .heading { flex: 0 1 auto; max-width: 100%; }
  .scoreboard > header > .header-actions { flex: 1 0 auto; max-width: 100%; }
  .scoreboard .meta { font-size: clamp(12px, 1.7cqi, 20px); }
  .scoreboard .pill { font-size: clamp(12px, 1.5cqi, 18px); }
  .banner {
    padding: .5em 1em; border-radius: 16px; text-align: center; font-weight: 800;
    font-size: clamp(18px, 3.4cqi, 44px); color: var(--ad-ok-text);
    background: color-mix(in srgb, ${STATUS_COLORS.ready} 16%, transparent);
  }
  .banner.rethrow { color: var(--ad-warn-text); background: color-mix(in srgb, ${STATUS_COLORS.takeout} 18%, transparent); }
  .main { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 12px; min-height: 0; }
  /* At full height the scores are a container of the room left: what is in it sizes by
     that room, and a long table scrolls inside instead of the page. "safe" keeps the
     top of a table that does not fit where it can be scrolled to. */
  .scoreboard.full:not(.choosing) .main {
    flex: 1 1 0; container-type: size; overflow-y: auto; justify-content: safe center;
  }
  /* The keyboard scrolls the scores too; its ring stays inside what scrolls. */
  .scoreboard.full .main:focus-visible { outline-offset: -2px; border-radius: 20px; }
  .players { display: grid; gap: clamp(8px, 1.6cqi, 24px); }
  .players.n1 { grid-template-columns: minmax(0, 1fr); }
  .players.n2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .players.n3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .players.n4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  /* A party of five to eight in two rows of four, on tiles with less room around the
     score, so that all of them fit a screen. */
  .players:is(.n5, .n6, .n7, .n8) { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: clamp(6px, 1.2cqi, 16px); }
  :is(.n5, .n6, .n7, .n8) > .player { padding: clamp(6px, 1.2cqi, 18px) 8px; gap: clamp(2px, .5cqi, 8px); }
  :is(.n5, .n6, .n7, .n8) > .player .name { font-size: clamp(14px, 2cqi, 30px); }
  :is(.n5, .n6, .n7, .n8) > .player .route { font-size: clamp(12px, 1.6cqi, 22px); }
  :is(.n5, .n6, .n7, .n8) > .player .details { font-size: clamp(11px, 1.4cqi, 18px); }
  .player {
    display: flex; flex-direction: column; align-items: center; gap: clamp(4px, .8cqi, 12px); min-width: 0;
    padding: clamp(12px, 2.2cqi, 32px) 12px; border-radius: 20px; border: 2px solid transparent;
    background: color-mix(in srgb, var(--primary-text-color) 4%, transparent); transition: border-color .3s, background .3s;
  }
  .player.active { border-color: var(--ad-accent); background: color-mix(in srgb, var(--ad-accent) 12%, transparent); }
  .player.winner {
    border-color: ${STATUS_COLORS.ready}; background: color-mix(in srgb, ${STATUS_COLORS.ready} 14%, transparent);
  }
  /* A player who is out fades by colour, which keeps the text readable. */
  .player.out { border-style: dashed; }
  .player.out :is(.name, .big, .details) { color: var(--ad-muted-text); }
  .big.lives { color: var(--ad-error-text); letter-spacing: 0; }
  .badge {
    display: inline-block; margin-left: .3em; padding: 0 .4em; border-radius: 8px; vertical-align: middle;
    font-size: .55em; font-weight: 700; color: var(--ad-muted-text);
    border: 1px solid var(--divider-color, rgba(127,127,127,.4));
  }
  .members { font-size: clamp(13px, 2.1cqi, 28px); color: var(--ad-muted-text); text-align: center; }
  .members b { color: var(--ad-accent-text); }
  .cricket.many tbody th, .cricket.many tbody td { padding-top: .05em; padding-bottom: .05em; line-height: 1.05; }
  .cricket.many td { font-size: clamp(14px, min(3.2cqi, 2.7vh), 42px); }
  .cricket.many tbody th { font-size: clamp(13px, min(2.4cqi, 2.4vh), 32px); }
  .cricket.many tr.total td { font-size: clamp(20px, min(4.2cqi, 3.8vh), 56px); }
  .scorecard { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  .scorecard th, .scorecard td { padding: .15em .2em; text-align: center; font-size: clamp(11px, 1.8cqi, 26px); }
  .scorecard thead th { color: var(--ad-muted-text); font-weight: 600; }
  .scorecard tbody th {
    text-align: left; max-width: 8em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    color: var(--primary-text-color);
  }
  .scorecard .now { background: color-mix(in srgb, var(--ad-accent) 14%, transparent); }
  .scorecard .total { font-weight: 800; color: var(--primary-text-color); }
  .scorecard tr.active th { color: var(--ad-accent-text); }
  .scorecard tr.winner > * { background: color-mix(in srgb, ${STATUS_COLORS.ready} 16%, transparent); }
  /* A long name takes a second line in a narrow tile instead of losing its end. */
  .player .name {
    max-width: 100%; min-height: 1.2em; font-size: clamp(16px, 2.8cqi, 40px); font-weight: 700; line-height: 1.2;
    text-align: center; color: var(--primary-text-color); overflow-wrap: anywhere; hyphens: auto;
    display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2; overflow: hidden;
  }
  .player.active .name::before { content: "▶ "; content: "▶ " / ""; color: var(--ad-accent-text); }
  .big {
    font-weight: 800; line-height: 1; letter-spacing: -0.04em; font-variant-numeric: tabular-nums;
    color: var(--primary-text-color);
  }
  /* Sized by width and height, so a landscape screen shows everything at once. */
  .n1 .big, .single .big { font-size: clamp(80px, min(24cqi, 32vh), 320px); }
  .single .big.long { font-size: clamp(48px, min(11cqi, 20vh), 150px); letter-spacing: -0.02em; }
  .n2 .big { font-size: clamp(64px, min(15cqi, 26vh), 240px); }
  .n3 .big { font-size: clamp(48px, min(10cqi, 22vh), 170px); }
  .n4 .big { font-size: clamp(44px, min(8cqi, 20vh), 140px); }
  :is(.n5, .n6, .n7, .n8) .big { font-size: clamp(36px, min(7cqi, 13vh), 120px); }
  @container (max-width: 640px) {
    .players.n3, .players.n4, .players:is(.n5, .n6, .n7, .n8) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .n3 .big, .n4 .big { font-size: clamp(44px, min(15cqi, 14vh), 120px); }
    :is(.n5, .n6, .n7, .n8) .big { font-size: clamp(32px, min(12cqi, 9vh), 96px); }
  }
  /* The route, a note and the details keep their lines while empty, so a tile stays as
     high from the first dart to the game shot. A tile too narrow for a route with what it
     leaves, or for a long note, keeps two lines for them from the start. */
  .route { align-self: stretch; container-type: inline-size; font-size: clamp(14px, 2.6cqi, 34px); line-height: 1.2; }
  /* Three beds always fit one line: a narrow tile takes smaller type for them. */
  .route-line {
    display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: .4em; min-height: 1.8em;
    font-size: min(1em, 10cqi);
  }
  @container (max-width: 15em) { .player .route-line { min-height: calc(3.28em + 10px); } }
  .route .bed, .setup .bed { padding: .12em .55em; border-radius: 10px; border-width: 2px; }
  .details { font-size: clamp(12px, 1.9cqi, 24px); color: var(--ad-muted-text); font-variant-numeric: tabular-nums; }
  .player .details { align-self: stretch; container-type: inline-size; text-align: center; line-height: 1.4; }
  .details-line { display: block; min-height: 1.4em; }
  @container (max-width: 13em) { .player .details-line { min-height: 2.8em; } }
  .cricket { width: 100%; border-collapse: collapse; table-layout: fixed; font-variant-numeric: tabular-nums; }
  /* On a full screen the chalkboard's rows share its whole height, without bands above
     and below it. */
  .scoreboard.full .main > .cricket { height: 100%; }
  .cricket th, .cricket td { padding: .1em .3em; text-align: center; }
  /* Names break onto a second line in a narrow column instead of losing their end. */
  .cricket thead th {
    font-size: clamp(12px, min(2.6cqi, 3.4vh), 34px); font-weight: 700; line-height: 1.1; color: var(--primary-text-color);
    overflow-wrap: anywhere; hyphens: auto;
  }
  .cricket tr > :first-child { width: 20%; }
  .cricket tbody th {
    font-size: clamp(16px, min(3cqi, 3vh), 42px); font-weight: 800; color: var(--ad-muted-text);
  }
  .cricket td { font-size: clamp(20px, min(4.4cqi, 3.6vh), 60px); font-weight: 800; line-height: 1.05; color: var(--ad-accent-text); }
  /* A number without marks keeps the line of one with them, so the first mark moves nothing. */
  .cricket td::after { content: "\\200b"; }
  .cricket th.aim { font-size: clamp(14px, min(2.4cqi, 3vh), 30px); }
  .cricket th.aim .bed { display: inline-block; }
  .cricket tr.closed > * { opacity: .3; }
  .cricket tr.target th { color: var(--ad-accent-text); }
  .cricket tr.total > * { border-top: 2px solid var(--divider-color, rgba(127,127,127,.25)); }
  .cricket tr.total td { font-size: clamp(24px, min(5cqi, 4.4vh), 68px); color: var(--primary-text-color); }
  .cricket tr.detail > * {
    font-size: clamp(12px, min(1.9cqi, 2.4vh), 24px); font-weight: 600; color: var(--ad-muted-text);
  }
  .cricket .active { background: color-mix(in srgb, var(--ad-accent) 14%, transparent); }
  /* Where the player at the board scores, and what they had better close. */
  .cricket td.aim-score { box-shadow: inset 0 0 0 clamp(2px, .35cqi, 4px) ${STATUS_COLORS.ready}; }
  .cricket td.aim-close { box-shadow: inset 0 0 0 clamp(2px, .35cqi, 4px) ${STATUS_COLORS.takeout}; }
  .cricket .winner { background: color-mix(in srgb, ${STATUS_COLORS.ready} 16%, transparent); }
  .summary { width: 100%; border-collapse: collapse; table-layout: fixed; font-variant-numeric: tabular-nums; }
  .summary th, .summary td { padding: .12em .4em; line-height: 1.2; text-align: center; }
  .summary tr > :first-child { width: 26%; text-align: left; }
  .summary thead th {
    font-size: clamp(12px, min(2.6cqi, 3.4vh), 34px); font-weight: 700; line-height: 1.1; color: var(--primary-text-color);
    overflow-wrap: anywhere; hyphens: auto;
  }
  .summary thead th.caption {
    font-size: clamp(11px, min(1.5cqi, 2vh), 18px); letter-spacing: .12em; text-transform: uppercase; color: var(--ad-accent-text);
  }
  .summary tbody th { font-size: clamp(12px, min(1.8cqi, 2.5vh), 24px); font-weight: 600; color: var(--ad-muted-text); }
  /* Sized by width and height, so every row fits a landscape screen. */
  .summary td { font-size: clamp(16px, min(2.8cqi, 2.9vh), 38px); font-weight: 800; color: var(--primary-text-color); }
  .summary tr.result td { font-size: clamp(24px, min(5cqi, 5vh), 72px); line-height: 1.1; color: var(--ad-accent-text); }
  .summary tbody tr + tr > * { border-top: 1px solid var(--divider-color, rgba(127,127,127,.2)); }
  .summary .winner { background: color-mix(in srgb, ${STATUS_COLORS.ready} 16%, transparent); }
  .single { display: flex; flex-direction: column; align-items: center; gap: clamp(6px, 1.2cqi, 16px); text-align: center; }
  .single .label {
    font-size: clamp(12px, 1.9cqi, 24px); font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
    color: var(--ad-accent-text);
  }
  /* The facts keep their lines while their numbers grow: a narrow box lays them out in
     columns, whose rows stay as many as the facts are. */
  .facts-box { align-self: stretch; container-type: inline-size; font-size: clamp(14px, 2.4cqi, 32px); }
  .facts {
    display: flex; flex-wrap: wrap; justify-content: center; gap: .3em 1.2em;
    color: var(--ad-muted-text); font-variant-numeric: tabular-nums;
  }
  @container (max-width: 48em) { .facts { display: grid; grid-template-columns: repeat(3, auto); justify-content: center; } }
  @container (max-width: 30em) { .facts { grid-template-columns: repeat(2, auto); } }
  .facts b { color: var(--primary-text-color); }
  .caller-toggle {
    display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px; cursor: pointer;
    font: inherit; font-size: clamp(12px, 1.5cqi, 18px); font-weight: 600; color: var(--ad-muted-text);
    border: 1px solid var(--divider-color, rgba(127,127,127,.4)); background: none;
  }
  .caller-toggle[aria-pressed="true"] {
    color: #fff; background: var(--ad-accent-fill); border: 1px solid var(--ad-accent-fill);
  }
  .header-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
  /* The tile beside the darts has a width of its own, whatever it shows, so the darts
     keep theirs: their beds are sized by it. */
  .visit { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(5em, .6fr); gap: clamp(6px, 1.2cqi, 16px); }
  .dart, .sum {
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
    padding: clamp(6px, 1.2cqi, 16px); border-radius: 14px;
  }
  .dart {
    position: relative; border: 1px solid transparent;
    background: color-mix(in srgb, var(--primary-text-color) 4%, transparent);
  }
  /* A dart's bed and points grow with its own tile, which is narrow beside a pad. */
  .visit .dart { container-type: inline-size; }
  .dart .segment { font-size: clamp(16px, 24cqi, 48px); font-weight: 800; color: var(--primary-text-color); }
  .dart.empty .segment { color: var(--ad-muted-text); }
  .dart .points { font-size: clamp(11px, 7cqi, 20px); line-height: 1.2; min-height: 1.2em; }
  .sum .muted { font-size: clamp(11px, 1.6cqi, 20px); min-height: 1.2em; }
  .dart .points { color: var(--ad-muted-text); }
  .sum { min-width: 0; border: 1px solid transparent; color: var(--ad-accent-text); background: color-mix(in srgb, var(--ad-accent) 14%, transparent); }
  /* The last visit, which a tap undoes; the second tap that confirms is red. */
  button.sum { position: relative; font: inherit; cursor: pointer; touch-action: manipulation; }
  button.sum:focus-visible { outline: 3px solid var(--ad-accent); outline-offset: 2px; }
  /* The undo arrow keeps to the very corner, clear of the words and the score of the last visit. */
  .visit .sum .cue { top: clamp(2px, .4cqi, 8px); right: clamp(2px, .4cqi, 8px); width: clamp(10px, .9cqi, 18px); height: clamp(10px, .9cqi, 18px); }
  .sum.confirm .cue { color: inherit; }
  /* A dart of the visit corrects with a tap; entered, corrected and bot darts are marked. */
  button.dart { font: inherit; color: inherit; cursor: pointer; touch-action: manipulation; }
  /* Every tile of the visit is as high as one a finger taps, so the row keeps its height
     whether its darts and the last visit can be tapped or not. */
  @media (any-pointer: coarse) { .visit > :is(.dart, .sum) { min-height: 44px; } }
  button.dart:focus-visible { outline: 3px solid var(--ad-accent); outline-offset: 2px; }
  .visit .dart .cue {
    top: clamp(3px, 4cqi, 10px); right: clamp(3px, 4cqi, 10px); width: clamp(11px, 9cqi, 20px); height: clamp(11px, 9cqi, 20px);
  }
  .dart.picked { border-color: var(--ad-accent); box-shadow: inset 0 0 0 2px var(--ad-accent); }
  .dart.manual, .dart.corrected { border-style: dashed; }
  .dart.manual, .dart.corrected { border-color: var(--divider-color, rgba(127,127,127,.4)); }
  .dart.bot { background: color-mix(in srgb, var(--ad-accent) 10%, transparent); }
  /* A dart that counted nothing in a Cricket game. */
  .dart.dead .segment { color: var(--ad-muted-text); text-decoration: line-through clamp(2px, 2cqi, 4px); }
  .lobby-player.bot .bot-icon { font-size: 1.3em; }
  .sum .muted { color: inherit; }
  .sum .value { font-size: clamp(22px, 4.2cqi, 56px); font-weight: 800; line-height: 1; font-variant-numeric: tabular-nums; }
  /* The new game screen: large targets for a finger, readable from the oche. */
  .lobby-toggle, .lobby-cta, .lobby button { font: inherit; cursor: pointer; touch-action: manipulation; }
  .lobby-toggle {
    display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 14px; border-radius: 999px;
    font-size: clamp(12px, 1.5cqi, 18px); font-weight: 700; color: var(--ad-accent-text);
    border: 1px solid var(--ad-accent); background: none;
  }
  .lobby-cta {
    align-self: center; min-height: 56px; padding: 0 clamp(24px, 4cqi, 56px); border: none; border-radius: 999px;
    font-size: clamp(16px, 2.4cqi, 28px); font-weight: 800; color: #fff; background: var(--ad-accent-fill);
  }
  .choosing .main { justify-content: flex-start; }
  .lobby {
    display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: clamp(14px, 2.4cqi, 32px); align-items: start;
    font-size: clamp(14px, 1.2cqi, 19px);
  }
  /* A portrait tablet or a phone stacks the games above the players; a small landscape
     screen keeps them side by side. */
  @container (max-width: 880px) { .lobby { grid-template-columns: minmax(0, 1fr); } }
  @media (orientation: landscape) {
    @container (min-width: 640px) { .lobby { grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); } }
  }
  .lobby-games, .lobby-setup {
    display: grid; grid-template-columns: minmax(0, 1fr); gap: clamp(12px, 1.8cqi, 22px); align-content: start;
  }
  .lobby .section-label { margin-bottom: 8px; font-size: clamp(11px, 1.4cqi, 15px); }
  /* How the chosen game is played, below its group. */
  .lobby-rules { margin-top: 10px; }
  .lobby-rules p { margin: 0 0 4px; line-height: 1.4; max-width: 60ch; }
  .game-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(clamp(112px, 15cqi, 180px), 1fr)); gap: 8px; }
  .lobby button {
    min-height: 48px; padding: 0 14px; border-radius: 14px; font-weight: 700; color: var(--primary-text-color);
    border: 2px solid var(--divider-color, rgba(127,127,127,.3));
    background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  }
  .lobby button:disabled { opacity: .4; cursor: default; }
  /* Training games have longer names. */
  .lobby-group.training .game-grid, .lobby-group.more .game-grid {
    grid-template-columns: repeat(auto-fill, minmax(clamp(150px, 20cqi, 240px), 1fr));
  }
  .lobby .game {
    min-height: clamp(52px, 7cqi, 76px); padding: 4px 8px; font-size: clamp(15px, 2.1cqi, 26px); line-height: 1.1;
    hyphens: auto; overflow-wrap: break-word;
  }
  .lobby [aria-pressed="true"] { color: #fff; background: var(--ad-accent-fill); border-color: var(--ad-accent-fill); }
  .lobby-players { list-style: none; margin: 0 0 10px; padding: 0; display: grid; gap: 6px; }
  .lobby-player {
    display: flex; align-items: center; gap: 6px; padding: 4px 4px 4px 12px; border-radius: 16px;
    font-size: clamp(16px, 2cqi, 24px); font-weight: 700; background: color-mix(in srgb, var(--ad-accent) 12%, transparent);
  }
  .lobby-player.resting { color: var(--ad-muted-text); background: none; outline: 1px dashed var(--divider-color, rgba(127,127,127,.4)); }
  /* In a narrow column the moves go below the name and the start score. */
  .lobby-player { flex-wrap: wrap; row-gap: 4px; }
  .lobby-player .who { flex: 1 1 6em; min-width: 0; overflow-wrap: anywhere; hyphens: auto; }
  .lobby-moves { display: inline-flex; gap: 6px; margin-left: auto; }
  .lobby-player button { min-width: 48px; padding: 0; }
  .lobby-start { display: inline-flex; align-items: center; gap: 4px; font-variant-numeric: tabular-nums; }
  .lobby-start b { min-width: 3.2ch; text-align: center; font-size: .85em; color: var(--ad-muted-text); }
  .lobby-start.own b { color: var(--ad-accent-text); }
  .lobby-player .lobby-start button { min-width: 40px; }
  .suggestions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
  .lobby .suggestion { display: inline-flex; align-items: center; border-radius: 999px; }
  .suggestion .home { margin-left: 6px; color: var(--ad-ok-text); }
  .lobby .suggestion.guest { border-style: dashed; }
  .name-entry { display: flex; gap: 8px; }
  .lobby-name {
    flex: 1; min-width: 0; min-height: 48px; box-sizing: border-box; padding: 0 14px; border-radius: 14px;
    font: inherit; font-size: max(16px, 1em); color: var(--primary-text-color); background: none;
    border: 2px solid var(--divider-color, rgba(127,127,127,.3));
  }
  .steppers { display: flex; flex-wrap: wrap; gap: 8px 24px; }
  .stepper { display: grid; gap: 4px; }
  .stepper-label { font-size: clamp(13px, 1.6cqi, 18px); font-weight: 600; color: var(--ad-muted-text); }
  .stepper-controls { display: flex; align-items: center; gap: 10px; }
  .lobby .stepper button { min-width: 52px; font-size: 22px; }
  .stepper-value { min-width: 2ch; text-align: center; font-size: clamp(20px, 2.6cqi, 32px); font-variant-numeric: tabular-nums; }
  .lobby-nobody { margin: 0 0 10px; font-size: clamp(12px, 1.5cqi, 16px); }
  .options { display: flex; flex-wrap: wrap; gap: 8px; }
  .options .section-label { flex-basis: 100%; margin-bottom: 0; }
  .options .choice { flex-basis: 100%; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
  .choice .stepper-label { min-width: 4.5em; }
  .choice-options { display: flex; flex-wrap: wrap; gap: 8px; }
  .options .stepper.rounds { flex-basis: 100%; margin-bottom: 4px; }
  .stepper.rounds .stepper-value { min-width: 4ch; font-size: clamp(16px, 2cqi, 24px); }
  /* The start stays in reach at the bottom of the screen while the page scrolls, below
     both columns and above a phone's home indicator, across the whole card. The card's
     background lies on the page's, so the games scrolling beneath stay hidden with a
     theme whose cards are see-through. */
  .lobby-actions {
    --ad-card-fill: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    grid-column: 1 / -1;
    position: sticky; bottom: 0; z-index: 1; display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end;
    gap: 10px; margin: 0 calc(-1 * var(--ad-pad));
    padding: 10px var(--ad-pad) calc(10px + var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px)));
    background: linear-gradient(var(--ad-card-fill), var(--ad-card-fill)), var(--primary-background-color, #111);
    box-shadow: 0 -10px 12px -10px rgba(0, 0, 0, .45);
  }
  /* On a phone the start fills the rest of the row, or a row of its own. */
  @container (max-width: 560px) { .lobby-actions .start { flex: 1 1 10em; } }
  /* On a screen higher than the choice, as a large monitor, the start bar stays at the
     bottom of the card instead of right below the choice. */
  .scoreboard.full.choosing .lobby { flex: 1 0 auto; grid-template-rows: auto minmax(0, 1fr); }
  .scoreboard.full.choosing .lobby-actions { align-self: end; }
  @container (max-width: 880px) { .scoreboard.full.choosing .lobby { grid-template-rows: auto auto minmax(0, 1fr); } }
  .lobby-hint { flex: 1 1 100%; font-weight: 700; color: var(--ad-warn-text); }
  .lobby-hint:empty { display: none; }
  .lobby .secondary { background: none; }
  .lobby .start {
    min-height: 60px; padding: 0 clamp(20px, 3cqi, 40px); font-size: clamp(17px, 2.3cqi, 26px); font-weight: 800;
    color: #fff; background: var(--ad-accent-fill); border-color: var(--ad-accent-fill);
  }
  /* Idle mode: panels in turn, faded in unless the device asks for less motion. */
  .idle-panel { display: flex; flex-direction: column; gap: clamp(8px, 1.6cqi, 20px); animation: ad-fade .6s ease both; }
  @keyframes ad-fade { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  @media (prefers-reduced-motion: reduce) { .idle-panel { animation: none; } }
  .idle-back { text-align: center; font-size: clamp(11px, 1.4cqi, 15px); }
  .ranking {
    list-style: none; margin: 0 auto; padding: 0; width: min(100%, 960px); display: grid; gap: clamp(6px, 1.2cqi, 14px);
  }
  .ranking li {
    display: flex; align-items: center; gap: clamp(8px, 1.6cqi, 20px); padding: clamp(8px, 1.4cqi, 16px) clamp(12px, 2cqi, 24px);
    border-radius: 16px; font-size: clamp(16px, 2.8cqi, 36px); background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  }
  .ranking li.winner { background: color-mix(in srgb, ${STATUS_COLORS.ready} 16%, transparent); }
  .ranking .rank { min-width: 1.2em; font-weight: 800; color: var(--ad-accent-text); }
  .ranking .who { flex: 1; min-width: 0; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ranking .score { font-weight: 800; font-variant-numeric: tabular-nums; }
  .ranking .muted { font-size: .55em; color: var(--ad-muted-text); }
  .match-head { text-align: center; font-size: clamp(14px, 2.2cqi, 28px); font-weight: 700; color: var(--ad-muted-text); }
  .records {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(clamp(160px, 24cqi, 300px), 1fr));
    gap: clamp(8px, 1.4cqi, 16px); width: min(100%, 1100px); margin: 0 auto;
  }
  .records div { padding: clamp(10px, 1.6cqi, 18px); border-radius: 16px; background: color-mix(in srgb, var(--primary-text-color) 5%, transparent); }
  .records dt { font-size: clamp(12px, 1.6cqi, 18px); color: var(--ad-muted-text); }
  .records dd { margin: 4px 0 0; font-size: clamp(20px, 3.4cqi, 44px); font-weight: 800; font-variant-numeric: tabular-nums; }
  .goal {
    width: min(80%, 640px); height: 12px; border-radius: 999px; overflow: hidden;
    background: color-mix(in srgb, var(--primary-text-color) 12%, transparent);
  }
  .goal i { display: block; height: 100%; border-radius: inherit; background: var(--ad-accent); }
  .goal.reached i { background: ${STATUS_COLORS.ready}; }
  /* Tournaments: who plays next, the round robin table and the knockout bracket. */
  .tournament { display: flex; flex-direction: column; gap: clamp(10px, 1.8cqi, 24px); width: 100%; }
  .next-up {
    display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 6px clamp(10px, 2cqi, 24px);
    padding: clamp(10px, 1.6cqi, 20px); border-radius: 18px; text-align: center;
    background: color-mix(in srgb, var(--ad-accent) 12%, transparent);
  }
  .next-up .section-label { flex-basis: 100%; font-size: clamp(11px, 1.4cqi, 15px); }
  .pairing {
    display: inline-flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: .35em;
    font-size: clamp(20px, 3.6cqi, 48px); font-weight: 800; color: var(--primary-text-color);
  }
  .pairing .vs { font-size: .5em; font-weight: 600; color: var(--ad-muted-text); }
  .countdown { font-size: clamp(13px, 1.8cqi, 22px); font-weight: 600; color: var(--ad-muted-text); }
  .start-next {
    min-height: 44px; padding: 0 18px; border-radius: 999px; cursor: pointer; touch-action: manipulation;
    font: inherit; font-size: clamp(13px, 1.7cqi, 20px); font-weight: 700;
    color: #fff; background: var(--ad-accent-fill); border: none;
  }
  /* A tournament on several boards: a box per board, the card's own marked, and the expected end. */
  .boards { width: min(100%, 1100px); margin: 0 auto; }
  .boards ul {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
    gap: clamp(6px, 1cqi, 12px); margin: 0; padding: 0; list-style: none;
  }
  .boards li {
    display: flex; flex-direction: column; gap: 2px; padding: clamp(8px, 1.2cqi, 14px); border-radius: 14px;
    background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  }
  .boards li.own { box-shadow: inset 0 0 0 2px var(--ad-accent); }
  .boards .board-name {
    font-size: clamp(11px, 1.4cqi, 15px); font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
    color: var(--ad-muted-text);
  }
  .boards .board-match { font-size: clamp(14px, 2cqi, 24px); font-weight: 700; color: var(--primary-text-color); }
  .boards li.waiting .board-match { font-weight: 600; color: var(--ad-muted-text); }
  .boards .vs { font-size: .7em; font-weight: 600; color: var(--ad-muted-text); }
  .boards .forecast {
    margin: clamp(6px, 1cqi, 10px) 0 0; text-align: center; font-size: clamp(12px, 1.6cqi, 18px);
    color: var(--ad-muted-text);
  }
  .standings {
    width: min(100%, 1100px); margin: 0 auto; border-collapse: collapse; font-variant-numeric: tabular-nums;
    font-size: clamp(14px, 2.2cqi, 30px); color: var(--primary-text-color);
  }
  .standings th, .standings td { padding: .3em .45em; text-align: center; }
  .standings thead th {
    font-size: .55em; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--ad-muted-text);
  }
  .standings abbr { text-decoration: none; }
  /* The name takes the room the numbers leave, and a long one ends in an ellipsis. */
  .standings .who { width: 40%; max-width: 0; text-align: left; font-weight: 700; }
  .standings .player-name { display: flex; align-items: center; min-width: 0; }
  .standings .player-name span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .standings tbody tr { border-top: 1px solid var(--divider-color, rgba(127,127,127,.2)); }
  .standings .rank { width: 2em; font-weight: 800; color: var(--ad-accent-text); }
  .standings .points { font-weight: 800; }
  .standings tr.next { background: color-mix(in srgb, var(--ad-accent) 10%, transparent); }
  .standings tr.champion { background: color-mix(in srgb, ${STATUS_COLORS.ready} 16%, transparent); }
  .standings tr.champion .player-name span::after { content: " 🏆"; }
  /* The places of a group that go on into the knockout. */
  .standings tr.through .rank { box-shadow: inset 4px 0 0 var(--ad-accent); }
  .groups {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
    gap: clamp(10px, 2cqi, 28px); align-items: start;
  }
  .groups .group { min-width: 0; }
  .groups .standings { font-size: clamp(12px, 1.6cqi, 22px); }
  .scoreboard.full .groups .standings { font-size: clamp(11px, min(1.5cqi, 2.6cqh), 22px); }
  .losers-label { margin: clamp(10px, 2cqi, 24px) 0 6px; font-size: clamp(11px, 1.4cqi, 15px); }
  .bracket { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: clamp(10px, 2.4cqi, 36px); }
  .bracket .round { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .bracket .duels { flex: 1; display: flex; flex-direction: column; justify-content: space-around; gap: 10px; }
  .bracket .section-label { font-size: clamp(11px, 1.4cqi, 15px); }
  .bracket .section-label.third { margin-top: 6px; }
  /* Brackets of 16 and 32 places keep their boxes small enough for a screen. */
  .bracket.big .slot { font-size: clamp(11px, 1.4cqi, 18px); min-height: 1.5em; }
  .bracket.huge .slot { font-size: clamp(10px, 1cqi, 14px); min-height: 1.4em; padding: .15em .45em; }
  .bracket.big .duels, .bracket.huge .duels { gap: 4px; }
  .duel {
    position: relative; border-radius: 14px; overflow: hidden; background: color-mix(in srgb, var(--primary-text-color) 4%, transparent);
    border: 2px solid var(--divider-color, rgba(127,127,127,.3));
  }
  .duel.live { border-color: var(--ad-accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ad-accent) 25%, transparent); }
  .duel.bye { border-style: dashed; }
  .duel.bye .slot { color: var(--ad-muted-text); }
  .slot {
    display: flex; align-items: center; gap: .3em; min-height: 1.7em; padding: .25em .6em;
    font-size: clamp(13px, 2cqi, 26px); color: var(--primary-text-color);
  }
  .slot + .slot { border-top: 1px solid var(--divider-color, rgba(127,127,127,.2)); }
  .slot .who { flex: 1; min-width: 0; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .slot.open .who { font-weight: 500; font-style: italic; color: var(--ad-muted-text); }
  .slot .score { font-weight: 800; font-variant-numeric: tabular-nums; }
  .slot.won { background: color-mix(in srgb, ${STATUS_COLORS.ready} 16%, transparent); }
  .slot.lost { color: var(--ad-muted-text); }
  .duel.crowned .slot.won .who::after { content: " 🏆"; }
  /* A player who goes on slides into the next round, outlined for a moment. */
  .slot.fresh { animation: ad-advance 1.6s ease-out backwards; }
  @keyframes ad-advance {
    from { opacity: 0; transform: translateX(-1.5em); box-shadow: inset 0 0 0 3px var(--ad-accent); }
    35% { opacity: 1; transform: none; box-shadow: inset 0 0 0 3px var(--ad-accent); }
    to { box-shadow: inset 0 0 0 3px transparent; }
  }
  @media (prefers-reduced-motion: reduce) { .slot.fresh { animation: none; } }
  /* A phone shows the rounds one below the other. */
  @container (max-width: 560px) { .bracket { grid-auto-flow: row; } }
  .lobby-mode { display: flex; gap: 8px; }
  .lobby .mode { flex: 1; font-size: clamp(15px, 2cqi, 22px); }
  .formats { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
  /* Finger-sized at a touch screen. */
  @media (any-pointer: coarse) { .lobby-toggle, .caller-toggle { min-height: 40px; } }
  /* The full-screen button: an icon in a ring, finger-sized at a touch screen. */
  .fullscreen-toggle {
    display: inline-grid; place-items: center; width: 36px; height: 36px; padding: 0; border-radius: 999px;
    cursor: pointer; touch-action: manipulation; color: var(--ad-muted-text); --mdc-icon-size: 22px;
    border: 1px solid var(--divider-color, rgba(127,127,127,.4)); background: none;
  }
  .fullscreen-toggle[aria-pressed="true"] {
    color: #fff; background: var(--ad-accent-fill); border-color: var(--ad-accent-fill);
  }
  @media (any-pointer: coarse) { .fullscreen-toggle { width: 44px; height: 44px; } }
  /* Once, where the browser can't keep the screen on: what to do instead. It is a row of
     its own in the header, so every layout of the scoreboard keeps its grid areas. */
  .awake-hint {
    flex: 1 0 100%; box-sizing: border-box; min-width: 0; margin: 0; padding: .6em 1em; border-radius: 12px; font-size: clamp(13px, 1.6cqi, 18px);
    color: var(--ad-warn-text); background: color-mix(in srgb, ${STATUS_COLORS.takeout} 14%, transparent);
  }
  .awake-hint a { color: inherit; font-weight: 700; }

  /* Full height: numbers and tables take the width (cqi) and the height (cqh) of the
     scores, less what the names, routes and details below them need. */
  .scoreboard.full .main > .players { flex: 1 1 auto; }
  .scoreboard.full .player { justify-content: center; }
  .scoreboard.full .n1 .big { font-size: clamp(40px, min(24cqi, 100cqh - 19cqi), 320px); }
  .scoreboard.full .single .big { font-size: clamp(40px, min(24cqi, 100cqh - 13cqi), 320px); }
  .scoreboard.full .single .big.long { font-size: clamp(36px, min(11cqi, 100cqh - 13cqi), 150px); }
  .scoreboard.full .main:has(.lobby-cta) .single .big { font-size: clamp(40px, min(24cqi, 100cqh - 13cqi - 80px), 320px); }
  .scoreboard.full .n2 .big { font-size: clamp(40px, min(15cqi, 100cqh - 19cqi), 240px); }
  .scoreboard.full .n3 .big { font-size: clamp(36px, min(10cqi, 100cqh - 19cqi), 170px); }
  .scoreboard.full .n4 .big { font-size: clamp(36px, min(8cqi, 100cqh - 19cqi), 140px); }
  .scoreboard.full :is(.n5, .n6, .n7, .n8) .big { font-size: clamp(24px, min(6cqi, 50cqh - 14cqi), 110px); }
  .scoreboard.full .players.teams .big { font-size: clamp(36px, min(15cqi, 100cqh - 23cqi), 240px); }
  @container (max-width: 640px) {
    .scoreboard.full :is(.n3, .n4) .big { font-size: clamp(32px, min(15cqi, 50cqh - 21cqi), 120px); }
    .scoreboard.full :is(.n5, .n6, .n7, .n8) .big { font-size: clamp(24px, min(12cqi, 25cqh - 20cqi), 96px); }
  }
  .scoreboard.full .cricket td { font-size: clamp(13px, min(4.4cqi, 6.2cqh), 60px); }
  .scoreboard.full .cricket tbody th { font-size: clamp(12px, min(3cqi, 5.4cqh), 42px); }
  .scoreboard.full .cricket thead th { font-size: clamp(12px, min(2.6cqi, 5.4cqh), 34px); }
  .scoreboard.full .cricket tr.total td { font-size: clamp(16px, min(5cqi, 7.2cqh), 68px); }
  .scoreboard.full .cricket tr.detail > * { font-size: clamp(11px, min(1.9cqi, 4cqh), 24px); }
  .scoreboard.full .cricket.many td { font-size: clamp(12px, min(3.2cqi, 4.4cqh), 42px); }
  .scoreboard.full .cricket.many tbody th { font-size: clamp(11px, min(2.4cqi, 4cqh), 32px); }
  .scoreboard.full .cricket.many tr.total td { font-size: clamp(14px, min(4.2cqi, 5.6cqh), 56px); }
  .scoreboard.full .summary td { font-size: clamp(12px, min(2.8cqi, 4.7cqh), 38px); }
  .scoreboard.full .summary tbody th { font-size: clamp(11px, min(1.8cqi, 4.1cqh), 24px); }
  .scoreboard.full .summary thead th { font-size: clamp(12px, min(2.6cqi, 5cqh), 34px); }
  .scoreboard.full .summary tr.result td { font-size: clamp(16px, min(5cqi, 7.5cqh), 72px); }
  .scoreboard.full .slot { font-size: clamp(12px, min(2cqi, 3.3cqh), 26px); }
  .scoreboard.full .pairing { font-size: clamp(18px, min(3.6cqi, 6cqh), 48px); }
  .scoreboard.full .standings { font-size: clamp(12px, min(2.2cqi, 3.7cqh), 30px); }
  .scoreboard.full .banner { font-size: clamp(16px, min(3.4cqi, 5.5vh), 44px); padding: .3em 1em; }
  /* A small landscape screen, such as 800 × 480 or 1024 × 600: less room around the parts. */
  @media (max-height: 640px) {
    .scoreboard.full { --ad-pad: 16px; padding: 10px var(--ad-pad); gap: 8px; }
    .scoreboard.full .visit :is(.dart, .sum) { padding: 4px 6px; flex-direction: row; gap: 8px; }
    /* The score of the visit as high as the darts' beds, and the undo arrow a corner of its own. */
    .scoreboard.full .visit .sum .value { font-size: clamp(16px, min(4.2cqi, 5.5vh), 56px); }
    .scoreboard.full .visit button.sum { padding-inline-end: calc(6px + clamp(10px, .9cqi, 18px)); }
    /* The words and the score of the tile beside the darts side by side need its room. */
    .scoreboard.full .visit { grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(8.5em, .8fr); }
    .scoreboard.full .visit .dart .segment { font-size: clamp(14px, min(19cqi, 5vh), 40px); }
    .scoreboard.full .player { padding-block: 8px; }
  }
  /* Darts entered or corrected on a landscape screen: the pad beside the scores, where
     it is in reach without scrolling. */
  @media (orientation: landscape) {
    .scoreboard.full.with-pad {
      display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); grid-template-rows: auto auto minmax(0, 1fr) auto;
      grid-template-areas: "header header" "banner banner" "main pad" "visit pad"; align-items: stretch;
    }
    .scoreboard.full.with-pad > header { grid-area: header; }
    .scoreboard.full.with-pad > .banner { grid-area: banner; }
    .scoreboard.full.with-pad > .main { grid-area: main; }
    .scoreboard.full.with-pad > .visit { grid-area: visit; }
    .scoreboard.full.with-pad > .pad-area { grid-area: pad; align-self: end; min-height: 0; }
    .scoreboard.full.with-pad .pad-numbers { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .scoreboard.full.with-pad .pad-score { --digit-span: 4; --answer-rows: 3; }
    @media (max-height: 640px) {
      .scoreboard.full.with-pad .pad button { min-height: 40px; }
      .scoreboard.full.with-pad :is(.pad, .pad-numbers, .pad-score, .pad-extra) { gap: 4px; }
    }
  }
  /* A portrait tablet: the tiles fill the height, two players one above the other. */
  @media (orientation: portrait) {
    .scoreboard.full .players.n2 { grid-template-columns: minmax(0, 1fr); }
    .scoreboard.full .players:is(.n3, .n4, .n5, .n6, .n7, .n8) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .scoreboard.full .n1 .big { font-size: clamp(80px, min(36cqi, 100cqh - 19cqi), 420px); }
    .scoreboard.full .n2 .big { font-size: clamp(64px, min(30cqi, 50cqh - 21cqi), 360px); }
    .scoreboard.full :is(.n3, .n4) .big { font-size: clamp(48px, min(17cqi, 50cqh - 21cqi), 220px); }
    .scoreboard.full :is(.n5, .n6, .n7, .n8) .big { font-size: clamp(28px, min(12cqi, 25cqh - 20cqi), 140px); }
    .scoreboard.full :is(.n5, .n6, .n7, .n8) > .player .name { font-size: clamp(14px, 3.4cqi, 34px); }
    .scoreboard.full :is(.n5, .n6, .n7, .n8) > .player .route { font-size: clamp(12px, 2.6cqi, 26px); }
    .scoreboard.full :is(.n5, .n6, .n7, .n8) > .player .details { font-size: clamp(11px, 2.4cqi, 22px); }
    .scoreboard.full .players.teams .big { font-size: clamp(48px, min(26cqi, 50cqh - 25cqi), 320px); }
    .scoreboard.full .single .big { font-size: clamp(80px, min(36cqi, 100cqh - 13cqi), 420px); }
    .scoreboard.full .cricket td { font-size: clamp(14px, min(6cqi, 6.2cqh), 80px); }
    .scoreboard.full .cricket tr.total td { font-size: clamp(18px, min(7cqi, 7.2cqh), 90px); }
    .scoreboard.full .cricket tbody th { font-size: clamp(13px, min(4.4cqi, 5.4cqh), 56px); }
  }
  /* A phone: the pad's keys take less room so the scores stay in sight. Its label gets a
     line of its own, S, D, T and the three views share the next one, and the bulls, the
     miss and the actions share one row. */
  @container (max-width: 560px) {
    .scoreboard.full .pad-head .section-label { flex-basis: 100%; }
    .scoreboard.full :is(.pad, .pad-numbers, .pad-score) { gap: 4px; }
    .scoreboard.full .pad button { min-height: 42px; padding: 0 6px; }
    .scoreboard.full .pad-extra { display: grid; grid-template-columns: repeat(auto-fit, minmax(4.2em, 1fr)); gap: 4px; }
    .scoreboard.full .pad-extra button { line-height: 1.1; }
  }
  /* The board to tap fills the room the scores leave, on every screen: below them the
     scores keep a short line each, beside them the board takes the pad's column from
     the top to the bottom. Its zoom switch sits on the board's corner, as on a map, so
     the head keeps one line. */
  .scoreboard.full:has(.pad.on-board) > .main { flex: 1 1 0; min-height: 96px; }
  .scoreboard.full:has(.pad.on-board) > .pad-area { flex: 4 1 0; min-height: 0; display: flex; flex-direction: column; }
  .scoreboard.full.with-pad:has(.pad.on-board) > .pad-area { align-self: stretch; }
  .scoreboard.full .pad.on-board {
    flex: 1 1 0; min-height: 0;
    grid-template-columns: minmax(0, 1fr) auto; grid-template-rows: auto minmax(160px, 1fr) auto auto;
    grid-template-areas: "label view" "board board" "hint hint" "extra extra";
  }
  .scoreboard.full .pad.on-board > .pad-head { display: contents; }
  .scoreboard.full .pad.on-board > .pad-head > .section-label { grid-area: label; align-self: center; }
  .scoreboard.full .pad.on-board > .pad-head > .view { grid-area: view; }
  .scoreboard.full .pad.on-board > .pad-head > .zoom {
    grid-area: board; justify-self: end; align-self: start; z-index: 1; margin: 6px; min-height: 0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, .35);
  }
  .scoreboard.full .pad.on-board > .pad-board { grid-area: board; width: 100%; height: 100%; min-height: 0; aspect-ratio: auto; }
  .scoreboard.full .pad.on-board > .pad-hint { grid-area: hint; }
  .scoreboard.full .pad.on-board > .pad-extra { grid-area: extra; }
  .scoreboard.full .section-label { font-size: clamp(11px, 1cqi, 15px); }
  /* A large landscape screen, as a touch monitor beside the board: the keys grow with
     its height. */
  @media (orientation: landscape) and (min-height: 641px) {
    .scoreboard.full.with-pad .pad { font-size: clamp(14px, min(1.8cqi, 2.6vh), 28px); }
    .scoreboard.full.with-pad .pad button:not(.zoom) { min-height: clamp(48px, 7vh, 88px); }
  }
  /* A phone on its side: the pad takes the right half from the top to the bottom, its
     numbers in rows of ten as on a large screen, or of seven or five where ten keys
     would be narrower than a finger, 40 px. */
  @media (orientation: landscape) and (max-height: 440px) {
    .scoreboard.full.with-pad {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      grid-template-areas: "header pad" "banner pad" "main pad" "visit pad";
    }
    .scoreboard.full.with-pad > .pad-area { align-self: stretch; overflow-y: auto; container-type: inline-size; }
    .scoreboard.full.with-pad .pad-head .section-label { flex-basis: 100%; }
    .scoreboard.full.with-pad .pad-numbers { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    @container (min-width: 298px) {
      .scoreboard.full.with-pad .pad-numbers { grid-template-columns: repeat(7, minmax(0, 1fr)); }
      .scoreboard.full.with-pad .pad-score { --digit-span: 3; --answer-rows: 2; }
    }
    @container (min-width: 427px) {
      .scoreboard.full.with-pad .pad-numbers { grid-template-columns: repeat(10, minmax(0, 1fr)); }
      .scoreboard.full.with-pad .pad-score { --digit-span: 2; --answer-rows: 1; }
    }
    .scoreboard.full.with-pad .pad { gap: 4px; }
    .scoreboard.full.with-pad :is(.pad-numbers, .pad-score) { gap: 3px; }
    .scoreboard.full.with-pad .pad button { min-height: 40px; padding: 0 4px; }
    .scoreboard.full.with-pad .pad-extra { display: grid; grid-template-columns: repeat(auto-fit, minmax(4.2em, 1fr)); gap: 4px; }
    .scoreboard.full.with-pad .pad-extra button { line-height: 1.1; }
    /* The board's hint gives way, too long for the width of half a phone. */
    .scoreboard.full.with-pad .pad.on-board {
      grid-template-rows: auto minmax(120px, 1fr) auto; grid-template-areas: "label view" "board board" "extra extra";
    }
    .scoreboard.full.with-pad .pad.on-board > .pad-hint { display: none; }
  }
  /* Little room for the scores, as beside a pad on a phone: each player on one line, the
     name beside the score, so that every score stays in sight. Three or four players in
     two rows of tiles need their line sooner. */
${compactPlayers(".scoreboard.full .players", 200)}
${compactPlayers(".scoreboard.full .players:is(.n3, .n4)", 280)}
  /* Little room above the visit, as on a phone on its side: the visit without its
     label, the facts smaller, and a smaller start of the next game; with even less
     room, the number and the start alone. */
  @container (max-height: 240px) {
    .scoreboard.full .single { gap: 4px; }
    .scoreboard.full .single .label { display: none; }
    .scoreboard.full .single .facts { font-size: 13px; }
    .scoreboard.full .single .big { font-size: clamp(28px, 100cqh - 64px, 320px); }
    .scoreboard.full .main:has(.lobby-cta) .single .big { font-size: clamp(28px, 100cqh - 112px, 320px); }
    .scoreboard.full .lobby-cta { min-height: 44px; font-size: 16px; }
  }
  @container (max-height: 150px) {
    .scoreboard.full .single .facts { display: none; }
    .scoreboard.full .main:has(.lobby-cta) .single .big { font-size: clamp(28px, 100cqh - 56px, 320px); }
  }
  /* A Cricket chalkboard with little room: rows as high as the room allows. */
  @container (max-height: 260px) {
    .scoreboard.full .cricket :is(th, td), .scoreboard.full .cricket.many :is(th, td) { padding-block: 0; line-height: 1.05; }
    .scoreboard.full .cricket td, .scoreboard.full .cricket.many td { font-size: clamp(11px, min(4.4cqi, 8cqh), 60px); }
    .scoreboard.full .cricket tbody th, .scoreboard.full .cricket.many tbody th { font-size: clamp(11px, min(3cqi, 7cqh), 42px); }
    .scoreboard.full .cricket thead th, .scoreboard.full .cricket.many thead th { font-size: clamp(11px, min(2.6cqi, 6.5cqh), 34px); }
    .scoreboard.full .cricket tr.total td, .scoreboard.full .cricket.many tr.total td { font-size: clamp(11px, min(4.2cqi, 9cqh), 56px); }
  }
  /* The overlay of a stream: no card around it, the scores on plates of their own over the
     picture, in colours that stay readable over any video, whatever the theme, and far from
     a green or a blue key. Sizes follow the height of the picture. */
  ha-card.overlay-card { background: none; border: none; border-radius: 0; box-shadow: none; overflow: visible; }
  .stage {
    --ad-plate: #14171d;
    --ad-plate-edge: #323844;
    --primary-text-color: #ffffff;
    --secondary-text-color: #c5cad3;
    --divider-color: #3a414d;
    --ad-muted-text: #c5cad3;
    --ad-accent-text: color-mix(in srgb, var(--ad-accent) 55%, #ffffff);
    --ad-accent-fill: color-mix(in srgb, var(--ad-accent) 70%, #000000);
    --ad-ok-text: ${GOLD};
    --ad-gold-text: ${GOLD};
    --ad-warn-text: #ffd166;
    --ad-error-text: #ff8a80;
    position: relative; container-type: size; aspect-ratio: 16 / 9; overflow: hidden;
    color: var(--primary-text-color); background: var(--ad-key, transparent);
  }
  /* In the card editor, what is see-through shows as a checkerboard, as in an image editor. */
  .stage[data-mode="transparent"]:not(.taken) {
    background: repeating-conic-gradient(#9aa0aa 0 25%, #c9ced6 0 50%) 0 0 / 20px 20px;
  }
  /* On the dashboard, the stage is the whole window, above Home Assistant. */
  .stage.taken {
    position: fixed; inset: 0; width: 100%; height: 100%; max-width: none; max-height: none; aspect-ratio: auto;
    margin: 0; padding: 0; border: 0; visibility: visible;
  }
  .stage .overlay {
    position: absolute; display: grid; gap: 1.2cqh; padding: 0; box-sizing: border-box;
    grid-template-columns: minmax(0, 1fr); align-content: end;
    grid-template-areas: "header" "banner" "main" "visit";
  }
  /* Between games the picture belongs to the stream. */
  .stage .overlay.quiet { display: none; }
  .stage .overlay > header { grid-area: header; justify-content: flex-start; }
  .stage .overlay > .banner { grid-area: banner; }
  .stage .overlay > .main { grid-area: main; gap: 1.2cqh; min-height: 0; justify-content: flex-start; }
  .stage .overlay > .visit { grid-area: visit; }
  .stage .overlay :is(.header-actions, .pad-area, .loupe) { display: none !important; }
  /* The game and its format in one line. */
  .stage .overlay .heading {
    display: block; padding: .7cqh 1.6cqh; border-radius: 1.2cqh; border: .25cqh solid var(--ad-plate-edge);
    background: var(--ad-plate);
  }
  .stage .overlay .heading:has(.title:empty):has(.meta:empty) { display: none; }
  .stage .overlay .title { display: inline; font-size: 2.8cqh; font-weight: 800; }
  .stage .overlay .meta { display: inline; font-size: 2.2cqh; color: var(--ad-muted-text); }
  .stage .overlay .title:not(:empty) + .meta:not(:empty)::before { content: " · "; content: " · " / ""; }
  .stage .overlay .banner {
    justify-self: start; padding: .8cqh 2.4cqh; border-radius: 1.2cqh; font-size: 3.6cqh;
    color: #14171d; background: ${GOLD};
  }
  .stage .overlay .banner.rethrow { color: #14171d; background: #ffb74d; }
  .stage .overlay .players { gap: 1.2cqh; }
  .stage .overlay .player {
    gap: .5cqh; padding: 1.2cqh 1.6cqh; border-radius: 1.6cqh; border: .3cqh solid var(--ad-plate-edge);
    background: var(--ad-plate);
  }
  .stage .overlay .player.active {
    border-color: var(--ad-accent); background: color-mix(in srgb, var(--ad-accent) 16%, var(--ad-plate));
  }
  .stage .overlay .player.winner { border-color: ${GOLD}; background: color-mix(in srgb, ${GOLD} 16%, var(--ad-plate)); }
  .stage .overlay .player .name { font-size: 3.2cqh; }
  .stage .overlay .big { font-size: 12cqh; }
  .stage .overlay .route { font-size: 2.8cqh; }
  .stage .overlay .details, .stage .overlay .members { font-size: 2.2cqh; }
  .stage .overlay :is(.n5, .n6, .n7, .n8) > .player .name { font-size: 2.4cqh; }
  .stage .overlay :is(.n5, .n6, .n7, .n8) .big { font-size: 7cqh; }
  .stage .overlay .single .big { font-size: 12cqh; }
  .stage .overlay .single .big.long { font-size: 7cqh; }
  .stage .overlay .single .label { font-size: 2.2cqh; }
  .stage .overlay .facts-box { font-size: 2.4cqh; }
  /* Tables, a training game and the screens of a tournament lie on a plate as a whole. */
  .stage .overlay .main > :not(.players) {
    box-sizing: border-box; padding: 1cqh 1.6cqh; border-radius: 1.6cqh; border: .3cqh solid var(--ad-plate-edge);
    background: var(--ad-plate);
  }
  .stage .overlay .main > table { border-collapse: separate; border-spacing: 0; }
  .stage .overlay :is(.dart, .sum) {
    padding: .8cqh 1.2cqh; border-radius: 1.2cqh; border: .25cqh solid var(--ad-plate-edge); background: var(--ad-plate);
  }
  .stage .overlay > .visit { gap: 1cqh; grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(0, .8fr); }
  .stage .overlay .sum {
    color: #ffffff; border-color: var(--ad-accent); background: color-mix(in srgb, var(--ad-accent) 35%, var(--ad-plate));
  }
  .stage .overlay .dart.bot { background: color-mix(in srgb, var(--ad-accent) 14%, var(--ad-plate)); }
  .stage .overlay .dart .segment { font-size: 3.6cqh; }
  .stage .overlay .dart .points { font-size: 2cqh; }
  .stage .overlay .sum .muted { font-size: 1.8cqh; }
  .stage .overlay .sum .value { font-size: 4cqh; }
  /* A chalkboard or a scorecard beside the stream, in smaller type than on the screen at the board. */
  .stage:not([data-layout="full"]) .overlay :is(.cricket, .scorecard) :is(th, td) {
    padding: .2cqh .8cqh; font-size: 2.4cqh; line-height: 1.1;
  }
  .stage:not([data-layout="full"]) .overlay .cricket tr.total td { font-size: 3cqh; }
  .stage:not([data-layout="full"]) .overlay .cricket tr.detail > * { font-size: 1.8cqh; }
  /* A glow mixes with the key colour, which a chroma key leaves as a fringe; the confetti stays. */
  .stage[data-mode="chroma"] .moment .glow { display: none; }
  /* Lower third: the players side by side along the bottom, the visit beside them. */
  .stage[data-layout="lower_third"] .overlay {
    left: 4cqw; right: 4cqw; bottom: 5cqh; max-height: 50cqh; align-items: end;
    grid-template-columns: minmax(0, max-content) auto; justify-content: start;
    grid-template-areas: "header header" "banner banner" "main visit";
  }
  .stage[data-layout="lower_third"] .overlay .players {
    grid-template-columns: none; grid-auto-flow: column; grid-auto-columns: minmax(0, 30cqw); justify-content: start;
  }
  .stage[data-layout="lower_third"] .overlay .main > .cricket { width: 56cqw; }
  .stage[data-layout="lower_third"] .overlay > .visit { width: 14cqw; grid-template-columns: minmax(0, 1fr); gap: .8cqh; }
  .stage[data-layout="lower_third"] .overlay > .visit > :is(.dart, .sum) {
    flex-direction: row; justify-content: space-between; gap: 1cqh;
  }
  /* Corner: a box in the top-left corner, a line for each player with the score at its end. */
  .stage[data-layout="corner"] .overlay { top: 4cqh; left: 3cqw; width: 32cqw; align-content: start; }
  .stage[data-layout="corner"] .overlay .players { grid-template-columns: minmax(0, 1fr); gap: .8cqh; }
  .stage[data-layout="corner"] .overlay .player {
    display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; column-gap: 1.6cqh; row-gap: .2cqh;
    grid-template-areas: "name big" "details big" "route route" "members members"; padding: .9cqh 1.6cqh;
  }
  .stage[data-layout="corner"] .overlay .player > .name {
    grid-area: name; justify-self: start; text-align: left; font-size: 2.6cqh;
  }
  .stage[data-layout="corner"] .overlay .player > .big { grid-area: big; font-size: 7cqh; }
  .stage[data-layout="corner"] .overlay .player > .route { grid-area: route; font-size: 2.2cqh; }
  .stage[data-layout="corner"] .overlay .player > .route .route-line { justify-content: flex-start; }
  .stage[data-layout="corner"] .overlay .player > .details { grid-area: details; text-align: left; font-size: 1.8cqh; }
  .stage[data-layout="corner"] .overlay .player > .members { grid-area: members; text-align: left; font-size: 1.8cqh; }
  .stage[data-layout="corner"] .overlay .dart .segment { font-size: 2.8cqh; }
  .stage[data-layout="corner"] .overlay .dart .points { font-size: 1.6cqh; }
  .stage[data-layout="corner"] .overlay .sum .value { font-size: 3.2cqh; }
  /* Full: the scoreboard over the whole picture, for a scene of its own. */
  .stage[data-layout="full"] .overlay {
    inset: 5cqh 4cqw; align-content: stretch; grid-template-rows: auto auto minmax(0, 1fr) auto;
  }
  .stage[data-layout="full"] .overlay > .main { justify-content: center; }
  .stage[data-layout="full"] .overlay .title { font-size: 3.6cqh; }
  .stage[data-layout="full"] .overlay .meta { font-size: 2.8cqh; }
  .stage[data-layout="full"] .overlay .banner { justify-self: center; font-size: 4.6cqh; }
  .stage[data-layout="full"] .overlay .player .name { font-size: 4.4cqh; }
  .stage[data-layout="full"] .overlay :is(.n1, .single) .big { font-size: 30cqh; }
  .stage[data-layout="full"] .overlay .n2 .big { font-size: 22cqh; }
  .stage[data-layout="full"] .overlay .n3 .big { font-size: 17cqh; }
  .stage[data-layout="full"] .overlay .n4 .big { font-size: 13cqh; }
  .stage[data-layout="full"] .overlay :is(.n5, .n6, .n7, .n8) .big { font-size: 9cqh; }
  .stage[data-layout="full"] .overlay .route { font-size: 3.8cqh; }
  .stage[data-layout="full"] .overlay :is(.details, .members) { font-size: 2.8cqh; }
  .stage[data-layout="full"] .overlay .dart .segment { font-size: 5cqh; }
  .stage[data-layout="full"] .overlay .dart .points { font-size: 2.6cqh; }
  .stage[data-layout="full"] .overlay .sum .muted { font-size: 2.2cqh; }
  .stage[data-layout="full"] .overlay .sum .value { font-size: 5.4cqh; }
`;

const PLAYERS_CSS = `${BASE_CSS}
  .players-card { display: flex; flex-direction: column; gap: 16px; padding: 18px; box-sizing: border-box; }
  .profiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }
${balancedCss(".profiles", 210, 10, 36)}
  .profile {
    display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; border-radius: 14px; min-width: 0;
    background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  }
  .profile-name {
    display: flex; align-items: center; min-width: 0; font-size: 17px; font-weight: 800; color: var(--primary-text-color);
  }
  .profile-name span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  /* Building block, menu: a button with three dots opens the actions of what it sits on,
     in a list below it, for a mouse, a finger and the keyboard alike. */
  .profile { position: relative; }
  .profile-name .manage {
    flex: 0 0 auto; margin: -10px -10px -10px auto; min-width: 44px; min-height: 44px; padding: 0;
    border: 0; border-radius: 10px; background: none; font: inherit; font-size: 20px; line-height: 1;
    color: var(--ad-muted-text);
  }
  .manage-menu {
    position: absolute; top: 48px; right: 8px; z-index: 2; display: flex; flex-direction: column;
    min-width: 160px; padding: 6px 0; border-radius: 12px; box-shadow: 0 6px 20px rgba(0,0,0,.25);
    background: var(--card-background-color, var(--ha-card-background, #fff));
    border: 1px solid var(--divider-color, rgba(127,127,127,.3));
  }
  .manage-menu button {
    min-height: 40px; padding: 0 16px; border: 0; background: none; text-align: start;
    font: inherit; font-size: 14px; font-weight: 600; color: var(--primary-text-color);
  }
  .manage-menu [data-action="delete"] { color: var(--ad-error-text); }
  /* The dialog that asks before a profile changes or goes. */
  .manage-dialog {
    width: min(420px, calc(100vw - 32px)); box-sizing: border-box; padding: 20px; border-radius: 16px;
    border: 1px solid var(--divider-color, rgba(127,127,127,.3)); color: var(--primary-text-color);
    background: var(--card-background-color, var(--ha-card-background, #fff));
  }
  .manage-dialog::backdrop { background: rgba(0,0,0,.45); }
  .manage-dialog h2 { margin: 0 0 12px; font-size: 18px; }
  .manage-dialog p { margin: 0 0 12px; font-size: 14px; }
  .manage-field { display: grid; gap: 6px; margin-bottom: 12px; font-size: 13px; font-weight: 600; }
  .manage-field :is(input, select) {
    min-height: 44px; box-sizing: border-box; padding: 0 12px; border-radius: 12px; font: inherit;
    font-size: max(16px, 1em); font-weight: 400; color: var(--primary-text-color); background: none;
    border: 2px solid var(--divider-color, rgba(127,127,127,.3));
  }
  .manage-field :is(input, select):focus-visible { outline: 2px solid var(--ad-accent); outline-offset: 2px; }
  .manage-error { color: var(--ad-error-text); }
  .profile-name .avatar { width: 1.6em; height: 1.6em; margin-right: .45em; }
  .profile dl { display: grid; grid-template-columns: 1fr auto; gap: 3px 10px; margin: 4px 0 0; }
  .profile dt { font-size: 12px; color: var(--ad-muted-text); }
  .profile dd { margin: 0; font-size: 13px; font-weight: 700; text-align: right; font-variant-numeric: tabular-nums; }
  .versus { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 4px 10px; padding: 6px 0; }
  .versus .who { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .versus .right { text-align: right; }
  .versus .tally { font-weight: 800; font-variant-numeric: tabular-nums; }
  .balance {
    grid-column: 1 / -1; height: 5px; border-radius: 999px; overflow: hidden;
    background: color-mix(in srgb, var(--primary-text-color) 12%, transparent);
  }
  .balance i { display: block; height: 100%; background: var(--ad-accent); }
  .match {
    display: grid; grid-template-columns: auto auto minmax(0, 1fr); gap: 10px; align-items: baseline;
    padding: 6px 0; border-top: 1px solid var(--divider-color, rgba(127,127,127,.2)); font-size: 13px;
  }
  .match .game { font-weight: 700; }
  .match b { color: var(--ad-ok-text); }
  .players-card header .export { flex: 0 0 auto; margin-left: auto; min-height: 32px; font-size: 13px; }
  /* Finger-sized at a touch screen. */
  @media (any-pointer: coarse) { .players-card header .export { min-height: 40px; } }
`;

const DOUBLES_CSS = `${BASE_CSS}
  .doubles-card { display: flex; flex-direction: column; gap: 14px; padding: 18px; box-sizing: border-box; }
  /* The title keeps its word; the counts beside it go below it on a narrow card. */
  .doubles-card > header { flex-wrap: wrap; align-items: baseline; row-gap: 4px; }
  .doubles-card > header .title { flex-shrink: 0; }
  .doubles-card > header .meta { flex: 1 1 16em; text-align: right; text-wrap: balance; }
  .doubles-body { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; align-items: start; }
  @container (max-width: 560px) { .doubles-body { grid-template-columns: minmax(0, 1fr); } }
  .doubles-board { max-width: 380px; width: 100%; margin: 0 auto; aspect-ratio: 1; }
  .ring path { stroke: var(--ha-card-background, var(--card-background-color, #1c1c1c)); stroke-width: 1.5; }
  .double-list { display: grid; gap: 6px; }
  .double {
    display: grid; grid-template-columns: 3.4em minmax(0, 1fr) 3.2em 4.4em 3.4em; gap: 10px; align-items: center;
    font-variant-numeric: tabular-nums;
  }
  .double .bed {
    padding: 2px 0; border-radius: 8px; text-align: center; font-size: 12px; font-weight: 800;
    color: color-mix(in srgb, var(--c) 50%, var(--primary-text-color, #212121)); border: 1px solid var(--c);
  }
  /* The favourite double: tinted in its rate's colour, like the next bed of a route. */
  .double.favourite .bed { background: color-mix(in srgb, var(--c) 20%, transparent); }
  .double .bar {
    height: 6px; border-radius: 999px; overflow: hidden;
    background: color-mix(in srgb, var(--primary-text-color) 10%, transparent);
  }
  .double .bar i { display: block; height: 100%; border-radius: inherit; }
  /* Fixed columns keep the bars of every row equally long. */
  .double .landed { font-size: 13px; font-weight: 700; text-align: right; }
  .double .count { font-size: 12px; color: var(--secondary-text-color); text-align: right; }
  .double .rate { font-size: 13px; font-weight: 700; text-align: right; }
`;

// Badges, trends and groupings of the players card.
const PROGRESS_CSS = `
  .section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
  .badge-player + .badge-player { margin-top: 12px; }
  .badge-owner { display: flex; align-items: baseline; gap: 8px; margin: 8px 0 6px; }
  .badge-owner b { font-size: 15px; color: var(--primary-text-color); }
  .badge-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
  .badge {
    display: grid; grid-template-columns: 38px minmax(0, 1fr); gap: 10px; align-items: center; min-width: 0;
    padding: 8px 10px; border-radius: 12px; background: color-mix(in srgb, var(--tier) 13%, transparent);
  }
  /* A medal: the tier's colour with a metallic sheen. */
  .badge-icon {
    width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; --mdc-icon-size: 22px;
    color: #fff; text-shadow: 0 1px 1px rgba(0,0,0,.3);
    background: radial-gradient(circle at 32% 28%, color-mix(in srgb, var(--tier) 35%, #fff), var(--tier) 55%,
      color-mix(in srgb, var(--tier) 70%, #000));
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--tier) 45%, transparent), 0 1px 3px rgba(0,0,0,.25);
  }
  .badge-text { display: flex; flex-direction: column; gap: 1px; min-width: 0; font-size: 12px; line-height: 1.3; }
  .badge-text b { font-size: 13px; color: var(--primary-text-color); }
  .badge-text > span { color: var(--ad-muted-text); }
  .badge.locked {
    background: none; border: 1px dashed color-mix(in srgb, var(--primary-text-color) 22%, transparent);
    padding: 7px 9px;
  }
  .badge.locked .badge-icon {
    color: var(--disabled-text-color, #9e9e9e); box-shadow: none; text-shadow: none;
    background: color-mix(in srgb, var(--primary-text-color) 8%, transparent);
  }
  .badge.locked .badge-text b { color: var(--secondary-text-color); }
  .badge-bar {
    display: block; height: 4px; margin-top: 3px; border-radius: 999px; overflow: hidden;
    background: color-mix(in srgb, var(--primary-text-color) 10%, transparent);
  }
  .badge-bar i { display: block; height: 100%; border-radius: inherit; background: var(--ad-accent); }
  .trend-player, .group-player { padding: 8px 0; border-top: 1px solid var(--divider-color, rgba(127,127,127,.2)); }
  :is(.trend-player, .group-player):first-child { border-top: 0; }
  .trend-name { font-weight: 700; margin-bottom: 6px; color: var(--primary-text-color); }
  .trends { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }
${balancedCss(".trends", 140, 8, 36)}
  .trend {
    display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 6px; align-items: center;
    padding: 8px 10px; border-radius: 12px; background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  }
  .trend-label { font-size: 11px; line-height: 1.25; color: var(--ad-muted-text); overflow-wrap: break-word; hyphens: auto; }
  .trend-value { font-size: 14px; font-weight: 700; text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .trend .spark { grid-column: 1 / -1; height: 24px; }
  .spark polyline {
    fill: none; stroke: var(--ad-accent); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round;
    vector-effect: non-scaling-stroke;
  }
  .spark .dot { stroke-width: 5; }
  .spark .gap { stroke-dasharray: 3 4; opacity: .55; }
  .arrow.up { color: var(--ad-ok-text); }
  .arrow.down { color: var(--ad-error-text); }
  .arrow.steady { color: var(--secondary-text-color); }
  .groups { display: grid; gap: 2px; }
  .group { display: grid; grid-template-columns: 3.4em minmax(0, 1fr) auto; gap: 10px; align-items: baseline; font-size: 13px; }
  .group-target {
    padding: 1px 0; border-radius: 8px; text-align: center; font-size: 12px; font-weight: 800;
    color: var(--ad-accent-text); border: 1px solid var(--ad-accent);
  }
  .group-text { color: var(--primary-text-color); }
  .group-change { font-size: 12px; font-weight: 700; white-space: nowrap; }
  .group-change.better { color: var(--ad-ok-text); }
  .group-change.worse { color: var(--ad-error-text); }
`;

const LEADERBOARD_CSS = `${BASE_CSS}
  .leaderboard { display: flex; flex-direction: column; gap: 14px; padding: 18px; box-sizing: border-box; }
  .leaderboard header { flex-wrap: wrap; }
  .records { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }
  .record {
    display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; border-radius: 14px; min-width: 0;
    background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  }
  .record-name { font-size: 12px; font-weight: 700; letter-spacing: .02em; color: var(--ad-accent-text); }
  .record-leader { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; min-width: 0; }
  .record-leader .who {
    font-size: 17px; font-weight: 800; color: var(--primary-text-color);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .record-leader .who::before { content: "👑 "; font-size: 14px; }
  .record-leader .value { font-size: 20px; font-weight: 800; color: var(--ad-gold-text); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .record-places { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; font-size: 13px; }
  .record-places li { display: grid; grid-template-columns: 1.8em minmax(0, 1fr) auto; gap: 6px; color: var(--ad-muted-text); }
  .record-places .who { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .record-places .value { font-variant-numeric: tabular-nums; }
`;

// Live card panel --------------------------------------------------------------

// The practice panel of the live card: the game, the line under it, the big
// number, what to aim at next and, in a match, a row for every player.
function livePanel(view, ui) {
  if (view.summary) return summaryPanel(view, ui);
  const { t, format } = ui;
  const turn = (game) => (game.winner === null ? `${playerName(ui, upScore(game), true)} ${t("score_turn")}` : "");
  const winner = (game) => note(winnerText(game, ui), "won");
  if (view.mode === "drill") {
    const parts = drillParts(view.drill, ui);
    return {
      title: t(`drill_${view.drill.kind}`),
      meta: factsText(parts.facts),
      big: parts.big,
      route: parts.note,
      rows: "",
    };
  }
  if (view.mode === "bulloff") {
    const { bullOff } = view;
    const bot = bullOff.throws.some((item) => item.player === bullOff.player && item.bot);
    return {
      title: t("bull_off"),
      meta: `${playerName(ui, { ...bullOff, bot }, true)} ${t("score_turn")}`,
      big: "Bull",
      route: bullOff.rethrow ? note(t("bull_off_rethrow"), "rethrow") : note(t("bull_off_hint")),
      rows: playerRows(bullOffPlayers(bullOff, ui), ui),
    };
  }
  if (view.mode === "cricket") {
    const { cricket } = view;
    const match = cricket.scores.length > 1;
    // In a match the points decide; alone, the numbers closed so far.
    const current = cricket.scores.find((score) => score.player === cricket.player);
    const closed = current ? current.marks.filter((mark) => mark >= 3).length : 0;
    const alone = cricket.darts
      ? [`${cricket.darts} ${t("leg_darts")}`, cricket.mpr === null ? "" : `${t("cricket_mpr")} ${format(cricket.mpr, 2)}`]
      : [];
    return {
      title: cricketTitle(t, cricket.kind),
      meta: match ? turn(cricket) : alone.filter(Boolean).join(" · "),
      big: match ? String(cricket.points) : `${closed}/${cricket.numbers.length}`,
      route:
        cricket.winner !== null
          ? winner(cricket)
          : cricket.won
            ? note(t("game_shot"), "won")
            : bedChips(ui, cricket.target ? [cricket.target] : []),
      rows: cricket.scores.length ? cricketTable(cricket, ui, { aim: false }) : "",
    };
  }
  if (view.mode === "party") {
    const { party } = view;
    const match = party.scores.length > 1;
    const current = party.scores.find((score) => score.player === party.player);
    const killer = party.kind === "killer";
    return {
      title: t(`party_${party.kind}`),
      meta: [partyRound(party, t), match ? turn(party) : ""].filter(Boolean).join(" · "),
      big: killer ? (party.phase === "choose" ? "?" : String(current?.number ?? "–")) : String(party.points),
      route: party.winner !== null ? winner(party) : partyNote(party, ui),
      rows: match ? playerRows(partyPlayers(party, ui), ui) : "",
    };
  }
  const { practice } = view;
  const players = x01Tiles(practice, ui);
  const match = players.length > 1;
  return {
    title: `${t("practice")} ${practice.game ?? ""}`.trim(),
    meta: [...x01Rules(practice, t), match ? turn(practice) : players[0].details.filter(Boolean).join(" · ")]
      .filter(Boolean)
      .join(" · "),
    big: String(practice.remaining),
    route: practice.winner !== null ? winner(practice) : x01Note(practice, ui),
    routeTitle: practice.route.length ? `${t("checkout")}: ${practice.route.join(" ")}` : "",
    rows: match ? playerRows(players, ui) : "",
  };
}

// A won match with its summary: the result in large type, the summary below.
function summaryPanel(view, ui) {
  const panel = livePanel({ ...view, summary: null }, ui);
  const game = view.cricket ?? view.party ?? view.practice;
  return { ...panel, big: matchResult(game) || panel.big, routeTitle: "", rows: summaryTable(view.summary, ui, game.teams) };
}

// Home Assistant brings its form element with its own editors; the strategy
// editor, which Home Assistant offers no form for, loads it with a card editor.
async function loadForm() {
  if (customElements.get("ha-form") || !window.loadCardHelpers) return;
  try {
    const helpers = await window.loadCardHelpers();
    const card = await helpers.createCardElement({ type: "entities", entities: [] });
    await card.constructor.getConfigElement?.();
  } catch {
    // The editor shows its form as soon as Home Assistant defines it.
  }
}

// The control in a part that takes the focus and its place by this key.
function withFocus(element, key) {
  return [...element.querySelectorAll("[data-focus]")].find((item) => item.dataset.focus === key);
}

// What scrolls a node: the nearest part around it, across shadow roots, whose content
// runs over and may scroll, else the page.
function scrollerOf(node) {
  for (let item = node.parentElement; item; item = item.parentElement ?? item.getRootNode().host) {
    if (/auto|scroll/.test(window.getComputedStyle(item).overflowY) && item.scrollHeight > item.clientHeight) return item;
  }
  return document.scrollingElement;
}

// Elements ------------------------------------------------------------------

// Elements are created on demand: Home Assistant replaces HTMLElement while it boots.
function createElements(Base) {
  class CardBase extends Base {
    static keys = {};

    static defaults = {};

    // The name of the card's form in FORMS.
    static form = null;

    static getStubConfig(hass) {
      const [deviceId] = homedartsDevices(hass);
      return deviceId ? { device_id: deviceId } : {};
    }

    // The visual editor: a form of Home Assistant, in the language of the page.
    static getConfigForm() {
      return this.form ? cardForm(FORMS[this.form](), this.defaults) : undefined;
    }

    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._watchedStates = [];
      this._confirm = null;
      this._initHints();
      // The control of the last tap, which keeps its place when it is drawn anew.
      this.shadowRoot.addEventListener("click", (event) => (this._tapped = event.target.closest("[data-focus]")), true);
    }

    // Building block, hint: what a pointer's tooltip tells shows on a tap too. A finger or a
    // pen on anything with a title that does nothing else shows the title in a bubble over
    // the card, so nothing moves; a mouse keeps the browser's own tooltip. Another tap,
    // Escape or a few seconds close it.
    _initHints() {
      const root = this.shadowRoot;
      root.addEventListener("pointerdown", (event) => (this._pointer = event.pointerType), true);
      root.addEventListener("click", (event) => {
        const target = event.target.closest("[title]");
        const acts = target?.closest("button, a, input, select, label, [role=button], .tappable");
        if (target && !acts && this._pointer && this._pointer !== "mouse") this._showHint(target);
        else this._hideHint();
      });
      root.addEventListener("keydown", (event) => event.key === "Escape" && this._hideHint());
    }

    _showHint(target) {
      // Every card with something to hint at is built in a root; a message is not.
      const box = this.shadowRoot.querySelector(".root");
      let bubble = box.querySelector(":scope > .hint-bubble");
      if (!bubble) {
        bubble = document.createElement("div");
        bubble.className = "hint-bubble";
        bubble.setAttribute("role", "status");
        box.append(bubble);
      }
      bubble.textContent = target.getAttribute("title");
      bubble.hidden = false;
      // Above what was tapped, or below it where the card has no room above, and never
      // beyond the card's sides.
      const area = box.getBoundingClientRect();
      const spot = target.getBoundingClientRect();
      const { offsetWidth: width, offsetHeight: height } = bubble;
      const middle = spot.left - area.left + spot.width / 2 - width / 2;
      const above = spot.top - area.top - height - 8;
      bubble.style.left = `${Math.max(8, Math.min(middle, area.width - width - 8))}px`;
      bubble.style.top = `${above >= 4 ? above : spot.bottom - area.top + 8}px`;
      clearTimeout(this._hintTimer);
      this._hintTimer = setTimeout(() => this._hideHint(), HINT_SECONDS * 1000);
    }

    _hideHint() {
      clearTimeout(this._hintTimer);
      const bubble = this.shadowRoot.querySelector(".hint-bubble");
      if (bubble) bubble.hidden = true;
    }

    setConfig(config) {
      if (!config || typeof config !== "object") throw new Error("Invalid configuration");
      this._config = { ...this.constructor.defaults, ...config };
      // What the card's settings say themselves, without the defaults.
      this._ownConfig = config;
      this._built = false;
      this._message = null;
      this._watchedStates = [];
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      pageHass = hass;
      this._render();
    }

    // Home Assistant sets this in the card editor and picker, where taps must not act.
    set preview(value) {
      this._preview = Boolean(value);
    }

    get preview() {
      return Boolean(this._preview);
    }

    // A pending confirmation ends with the card, so it shows no "Confirm?" when it returns.
    disconnectedCallback() {
      this._hideHint();
      clearTimeout(this._confirmTimer);
      this._confirm = null;
      this._confirmChanged();
      clearTimeout(this._summaryTimer);
    }

    // A summary whose time ran out while the card was away is gone when it returns.
    connectedCallback() {
      if (this._built && this._summarySeen) this._update();
    }

    // The summary of the finished match, while it shows: until the next game
    // starts or, with summary_seconds, that long after the card first showed it.
    _matchSummary(view) {
      const c = this._config;
      clearTimeout(this._summaryTimer);
      // Party games keep their final scores on screen; they have no numbers to sum up.
      const shown = ["x01", "cricket"].includes(view.mode) && c.show_summary !== false;
      const summary = shown ? summaryView(this._state("practice")) : null;
      // As the form allows: a timer of weeks would fire at once, and again with every update.
      const seconds = Math.min(600, Number(c.summary_seconds) || 0);
      if (!summary || seconds <= 0) return summary;
      if (this._summarySeen?.ended !== summary.ended) this._summarySeen = { ended: summary.ended, at: Date.now() };
      const left = this._summarySeen.at + seconds * 1000 - Date.now();
      if (left <= 0) return null;
      // Only leaving the page stops the timer, so a card away from the page sets it when it comes back.
      if (this.isConnected) this._summaryTimer = setTimeout(() => this._update(), left);
      return summary;
    }

    getGridOptions() {
      return { columns: 12, min_columns: 6 };
    }

    _css() {
      return BASE_CSS;
    }

    // Cards that show the pictures of the persons linked to the players.
    static avatars = false;

    // Entity ids whose state changes redraw the card.
    _watched() {
      return [...Object.values(this._ids), ...(this.constructor.avatars ? this._personIds() : [])];
    }

    // The persons linked to the player profiles.
    _personIds() {
      const players = this._state("profiles")?.attributes?.players;
      return (Array.isArray(players) ? players : []).map((player) => named(player?.person)).filter(Boolean);
    }

    // The state of a watched entity as far as the card cares about it: of a
    // person only the picture and whether they are home, not every move.
    _relevant(id, state) {
      if (!state || !id.startsWith("person.")) return state;
      return `${state.state}|${state.attributes?.entity_picture ?? ""}`;
    }

    _render() {
      if (!this._config || !this._hass) return;
      const hass = this._hass;
      const deviceId = this._config.device_id || homedartsDevices(hass)[0];
      // A deleted device must not be mistaken for an unreachable board.
      if (!deviceId || (this._config.device_id && !knownDevice(hass, deviceId))) {
        const message = translate(hass, "no_board");
        if (this._message !== message) {
          this.shadowRoot.innerHTML = `<style>${this._css()}</style><ha-card><div class="message">${escapeHtml(
            message
          )}</div></ha-card>`;
          this._message = message;
        }
        this._built = false;
        return;
      }
      this._message = null;
      this._index = entityIndex(hass, deviceId);
      this._ids = resolveKeys(this._index, this.constructor.keys);
      const states = this._watched().map((id) => (id ? this._relevant(id, hass.states[id]) : undefined));
      const lang = language(hass);
      const rebuild = !this._built || this._language !== lang || this._deviceId !== deviceId;
      if (
        !rebuild &&
        states.length === this._watchedStates.length &&
        states.every((state, index) => state === this._watchedStates[index])
      ) {
        return;
      }
      if (rebuild) {
        this._language = lang;
        this._deviceId = deviceId;
        this._build();
        this._built = true;
      }
      this._watchedStates = states;
      this._update();
    }

    _t(key) {
      return translate(this._hass, key);
    }

    _state(name) {
      const id = this._ids?.[name];
      return id ? this._hass.states[id] : undefined;
    }

    _number(name) {
      const state = this._state(name);
      const value = usable(state) ? Number(state.state) : NaN;
      return Number.isFinite(value) ? value : null;
    }

    _format(value, digits = 0) {
      return formatNumber(this._hass, value, digits);
    }

    _percent(value, digits = 0) {
      return formatPercent(this._hass, value, digits);
    }

    // Texts, numbers, beds and the pictures of players as the shared renderers read them.
    _ui() {
      const links = personLinks(this._hass, this._state("profiles"));
      return {
        t: (key) => this._t(key),
        format: (value, digits) => this._format(value, digits),
        percent: (value, digits) => this._percent(value, digits),
        label: (key) => hitLabel(this._hass, key),
        date: (value) => formatDateTime(this._hass, value),
        time: (moment) => formatClock(this._hass, moment).time,
        avatar: (name) => links.get(nameKey(name))?.picture ?? null,
        links,
      };
    }

    _since() {
      const started = this._state("started");
      const shown = usable(started) ? formatDateTime(this._hass, started.state) : "";
      return shown ? `${this._t("since")} ${shown}` : "";
    }

    _deviceName() {
      const device = this._hass.devices?.[this._deviceId];
      return this._config.title || device?.name_by_user || device?.name || "HomeDarts";
    }

    _status() {
      return boardStatus((name) => this._state(name));
    }

    // A dartboard without Autodarts, whose darts are all entered by hand.
    _manualBoard() {
      return this._state("status")?.state === "manual";
    }

    // The keypad for darts entered by hand: on a dartboard without Autodarts, unless the
    // card's own settings switch it off; on a board with Autodarts, with the keypad option
    // while Practice manual entry is on.
    _keypad() {
      if (this._manualBoard()) return this._ownConfig?.keypad !== false;
      return Boolean(this._config.keypad) && this._state("manualEntry")?.state === "on";
    }

    _call(domain, service, data) {
      // Home Assistant already shows failures as a toast.
      Promise.resolve(this._hass.callService(domain, service, data)).catch(() => {});
    }

    _press(id) {
      if (id) this._call("button", "press", { entity_id: id });
    }

    // The switch starts and stops detection; boards without it have a button each.
    _toggleDetection() {
      if (this.preview) return;
      const running = detectionRunning((name) => this._state(name), this._status()[0]);
      if (this._ids.detection) {
        this._call("switch", running ? "turn_off" : "turn_on", { entity_id: this._ids.detection });
      } else {
        this._press(this._ids[running ? "stop" : "start"]);
      }
    }

    // Destructive actions need a second tap within a few seconds.
    _confirmed(action) {
      if (this._confirm === action) {
        this._confirm = null;
        clearTimeout(this._confirmTimer);
        return true;
      }
      this._confirm = action;
      clearTimeout(this._confirmTimer);
      this._confirmTimer = setTimeout(() => {
        this._confirm = null;
        this._confirmChanged();
      }, 4000);
      return false;
    }

    _confirmChanged() {}

    _moreInfo(entityId) {
      if (!entityId || this.preview) return;
      this.dispatchEvent(
        new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId } })
      );
    }

    // Replace markup only when it changes, so animations and focus survive updates.
    // A focused element with data-focus gets the focus back after a change, and a
    // text field what was typed in it and where the caret was. The markup is parsed
    // apart and swapped in at once: Safari scrolls the page to its top when innerHTML
    // empties a part that holds most of it, as the new game screen does.
    _setHtml(element, html) {
      if (!element || element._adHtml === html) return;
      const active = this.shadowRoot.activeElement;
      const focus = active && element.contains(active) ? active.dataset.focus : undefined;
      const typed = active?.tagName === "INPUT" ? [active.value, active.selectionStart, active.selectionEnd] : null;
      const tapped = this._tapped && element.contains(this._tapped) ? this._tapped : null;
      const top = tapped?.getBoundingClientRect().top;
      const parsed = element.cloneNode(false);
      parsed.innerHTML = html;
      element.replaceChildren(...parsed.childNodes);
      element._adHtml = html;
      if (top >= 0 && top < window.innerHeight) this._keepPlace(element, tapped.dataset.focus, top);
      if (!focus) return;
      const target = withFocus(element, focus);
      if (!target) return;
      // The control stays where it is; the page does not scroll to it.
      target.focus({ preventScroll: true });
      if (!typed) return;
      target.value = typed[0];
      target.setSelectionRange(typed[1], typed[2]);
    }

    // Building block, steady place: a control in sight that the next render after its
    // tap draws anew stays under the finger. Where a part above it grew or shrank, as
    // the rules of the game chosen before, what scrolls the card moves along by as much.
    _keepPlace(element, key, top) {
      const control = withFocus(element, key);
      const moved = control ? control.getBoundingClientRect().top - top : 0;
      if (moved) scrollerOf(control).scrollTop += moved;
    }

    // Text that is the same stays, so a status region does not announce it again.
    _text(element, text) {
      if (element.textContent !== text) element.textContent = text;
    }

    // The status in words, as wide as the longest words it takes during a game.
    _showStatus(pill, key) {
      this._setHtml(pill, `<span>${escapeHtml(this._t(key))}</span>`);
      const words = (MANUAL_STATUSES.includes(key) ? MANUAL_STATUSES : PLAY_STATUSES).map((name) => this._t(name));
      pill.dataset.widest = words.reduce((longest, text) => (text.length > longest.length ? text : longest));
    }
  }

  // Live visit card ------------------------------------------------------------

  // Correcting a dart of the visit, on the live card and the scoreboard: a tap on a
  // dart picks it, the pad puts it where it is with the keys or a spot on the board.
  class PadCard extends CardBase {
    // The config entry of the board, for actions of the integration.
    _entry() {
      const device = this._hass.devices?.[this._deviceId];
      return device?.primary_config_entry ?? device?.config_entries?.[0] ?? null;
    }

    // The state of correcting and the taps that change it: the darts, the pad, and the
    // frame the loupe moves in. The pad shows the board instead of the keys, all of it
    // or zoomed in; the fingers on it and when the last one set a dart.
    _initPad(darts, frame) {
      this._padFrame = frame;
      this._pick = null;
      this._multiplier = 1;
      this._padBoard = false;
      // The score view of the keypad, what is typed there and the question after it.
      this._padScore = false;
      this._typed = "";
      this._asking = null;
      this._padZoom = null;
      this._touches = new Map();
      this._gesture = null;
      this._touched = 0;
      darts?.addEventListener("click", (event) => {
        const dart = event.target.closest("[data-dart]");
        if (dart) this._pickDart(Number(dart.dataset.dart));
        // The last visit beside the darts undoes it.
        const action = event.target.closest("[data-pad]");
        if (action) this._padAction(action.dataset.pad);
      });
      this._el.pad.addEventListener("click", (event) => {
        const target = event.target.closest("[data-pad]");
        if (!target || target.disabled) return;
        const spot = target.dataset.pad === "spot";
        // A finger that let go of the board has set its dart already.
        if (spot && Date.now() - this._touched < 800) return;
        // A tap on the board says where the dart is.
        const value = spot ? boardSpot(target, event, padViewBox(this._padZoom)) : target.dataset.value;
        this._padAction(target.dataset.pad, value);
      });
      for (const type of ["pointerdown", "pointermove", "pointerup", "pointercancel"]) {
        this._el.pad.addEventListener(type, (event) => this._boardTouch(event));
      }
      // A keyboard types the score: digits, Backspace, Enter and Escape press the keys of
      // the score view, and only those it offers, so a bot at the board holds them too.
      this._el.pad.addEventListener("keydown", (event) => {
        const key = this._scoreKey(event);
        if (!key) return;
        event.preventDefault();
        if (key !== true) this._padAction(key.dataset.pad, key.dataset.value);
      });
    }

    // The key of the score view that a key of a keyboard presses, if the view offers it.
    // During the question after a score, a digit answers it, and Backspace goes back to
    // the score as Escape does. Enter takes the score on the pad and on a digit, as on a
    // calculator; on any other key of the pad it presses that key, as everywhere. While OK
    // is off, Enter there does nothing at all (true): the browser must not press the
    // focused digit again.
    _scoreKey(event) {
      const view = this._el.pad.querySelector(".pad-score");
      if (!view || event.ctrlKey || event.altKey || event.metaKey) return null;
      const asking = Boolean(this._asking);
      const other = event.target.closest?.('button:not([data-pad="digit"], [data-pad="erase"])');
      const selector = /^[0-9]$/.test(event.key)
        ? `[data-pad="${asking ? "answer" : "digit"}"][data-value="${event.key}"]`
        : {
            Backspace: asking ? '[data-pad="cancel"]' : '[data-pad="erase"]',
            Enter: other ? null : '[data-pad="enter"]',
            Escape: '[data-pad="cancel"]',
          }[event.key];
      const key = selector ? view.querySelector(selector) : null;
      if (key && !key.disabled) return key;
      return event.key === "Enter" && Boolean(selector);
    }

    // Keys of a keyboard reach the pad where the focus is. When the score view opens, a
    // score goes in or a question is answered or left, the pad itself takes the focus, as
    // the key that had it may be gone or off; after a digit only when the focus left the
    // pad. A mouse gives it the focus too, since Safari gives a clicked button none; a
    // finger only when the focus was in the card already, so a tablet keeps its page.
    _padFocus(action) {
      if (!SCORE_ACTIONS.includes(action)) return null;
      if (!this.shadowRoot.activeElement && this._pointer !== "mouse") return null;
      return () => {
        const pad = this._el.pad.querySelector(".pad");
        const active = this.shadowRoot.activeElement;
        const stays = ["digit", "erase"].includes(action) && active && pad?.contains(active);
        if (pad && !stays) pad.focus({ preventScroll: true });
      };
    }

    // The keypad of darts entered by hand, and in an X01 leg its score view.
    _keypadPad(view, disabled, base, extra) {
      const entry = scoreEntry(view);
      const scoring = Boolean(entry && this._padScore) && !this._pick;
      const score = scoring
        ? {
            typed: this._typed,
            hint: this._typed ? scoreHint(entry, Number(this._typed), (key) => this._t(key)) : "",
            ready: scoreReady(entry, this._typed),
            ask: this._asking,
          }
        : null;
      return { dart: null, multiplier: this._multiplier, disabled, scoreable: Boolean(entry), score, ...extra, ...base };
    }

    // A score typed on the keypad goes in with what it takes besides itself.
    _scoreAction(action, value) {
      const entry = scoreEntry(gameView((name) => this._state(name)));
      if (!entry) return;
      if (action === "digit") {
        const typed = this._typed === "0" ? value : this._typed + value;
        if (Number(typed) <= 180) this._typed = typed;
        return;
      }
      if (action === "erase") {
        this._typed = this._typed.slice(0, -1);
        return;
      }
      // OK, and Enter on a keyboard with it, waits for a score that a visit scores: it is
      // off until then, and the pad takes no key that is off.
      const points = Number(this._typed);
      const answers = this._asking?.answers ?? {};
      if (action === "answer") answers[this._asking.ask] = Number(value);
      const next = scoreAnswer(entry, points, answers);
      if (next.ask) {
        this._asking = { ...next, answers };
        return;
      }
      const config = this._entry() ? { config_entry_id: this._entry() } : {};
      this._call("homedarts", "enter_visit", { ...config, ...next.data });
      this._typed = "";
      this._asking = null;
    }

    // What the pad shows of the darts of the visit, for any pad: the board instead of
    // the keys, zoomed in or not, and the darts where they are, the one being corrected
    // where the board saw it. A picked dart that left the visit is dropped.
    _padBase(darts) {
      if (this._pick && !darts.some((dart) => dart.dart === this._pick.dart)) this._pick = null;
      const board = this._padBoard;
      const pins = darts
        .filter((dart) => Number.isFinite(dart.x) && Number.isFinite(dart.y))
        .map((dart) => ({ x: dart.x, y: dart.y, seen: dart.dart === this._pick?.dart }));
      return { board, zoom: board ? this._padZoom : null, pins };
    }

    // A tap on a dart of the visit opens the pad to correct it; another tap closes it.
    _pickDart(dart) {
      if (this.preview) return;
      const shown = visitThrows(this._state("visit")).find((item) => item.dart === dart);
      this._pick =
        this._pick?.dart === dart || !shown ? null : { dart, multiplier: Math.min(Math.max(shown.multiplier, 1), 3) };
      if (this._padBoard) this._padZoom = this._openZoom();
      this._update();
    }

    // Where the board to tap opens: on a small screen, zoomed in on where the board saw
    // the dart being corrected; for darts entered by hand, the whole board.
    _openZoom() {
      const width = this.getBoundingClientRect().width;
      const small = Math.min(width, window.innerHeight) < PAD_SMALL;
      return this._pick && width > 0 && small ? this._zoomAt(this._pick.dart) : null;
    }

    // Zoomed in on a dart of the visit, the one being corrected or else the last one;
    // on the bull without a dart that has a position.
    _zoomAt(dart) {
      const darts = visitThrows(this._state("visit")).filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));
      const at = darts.find((item) => item.dart === dart) ?? (dart === undefined ? darts.at(-1) : null);
      if (dart !== undefined && !at) return null;
      return { scale: PAD_ZOOM, x: (at?.x ?? 0) * NORM, y: -(at?.y ?? 0) * NORM };
    }

    // Fingers on the board to tap: one aims with the loupe and sets the dart where it
    // lets go; a second finger turns aiming into zooming and moving the board. A mouse
    // clicks instead.
    _boardTouch(event) {
      if (event.pointerType === "mouse") return;
      const touches = this._touches;
      if (event.type === "pointerdown") {
        const svg = event.target.closest?.("svg.pad-board[data-pad='spot']");
        if (!svg) return;
        event.preventDefault();
        svg.setPointerCapture?.(event.pointerId);
        touches.set(event.pointerId, { clientX: event.clientX, clientY: event.clientY });
        if (!this._gesture) {
          this._gesture = { svg, aim: event.pointerId, pinch: null };
          this._el.loupe.innerHTML = `<svg>${svg.innerHTML}</svg>`;
        } else if (touches.size === 2) {
          const [a, b] = [...touches.values()];
          const middle = { clientX: (a.clientX + b.clientX) / 2, clientY: (a.clientY + b.clientY) / 2 };
          this._gesture.aim = null;
          this._gesture.pinch = {
            distance: Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY) || 1,
            scale: this._padZoom?.scale ?? 1,
            anchor: boardPoint(svg, middle, padViewBox(this._padZoom)),
          };
        }
        this._aim(event);
        return;
      }
      const gesture = this._gesture;
      if (!gesture || !touches.has(event.pointerId)) return;
      if (event.type === "pointermove") {
        touches.set(event.pointerId, { clientX: event.clientX, clientY: event.clientY });
        if (gesture.pinch && touches.size === 2) this._pinch();
        else this._aim(event);
        return;
      }
      touches.delete(event.pointerId);
      if (event.type === "pointerup" && gesture.aim === event.pointerId) {
        const spot = boardSpot(gesture.svg, event, padViewBox(this._padZoom));
        this._touched = Date.now();
        this._endGesture();
        this._padAction("spot", spot);
      } else if (!touches.size) {
        this._endGesture();
      }
    }

    // The loupe above the aiming finger, which would hide the spot itself, or beside it
    // where there is no room above; it shows the board around the spot magnified.
    _aim(event) {
      const gesture = this._gesture;
      const loupe = this._el.loupe;
      const view = padViewBox(this._padZoom);
      const point = gesture.aim === event.pointerId ? boardPoint(gesture.svg, event, view) : null;
      loupe.hidden = !point;
      if (!point) return;
      const size = view.size / LOUPE_ZOOM;
      loupe.firstElementChild.setAttribute("viewBox", viewBoxText({ x: point[0] - size / 2, y: point[1] - size / 2, size }));
      const box = this._padFrame.getBoundingClientRect();
      const width = loupe.offsetWidth || 132;
      const x = event.clientX - box.left;
      const y = event.clientY - box.top;
      const above = y - width - 24;
      const beside = x + 24 + width <= box.width ? x + 24 : x - 24 - width;
      const left = above >= 0 ? x - width / 2 : beside;
      loupe.style.left = `${Math.round(Math.min(Math.max(left, 0), Math.max(box.width - width, 0)))}px`;
      loupe.style.top = `${Math.round(above >= 0 ? above : Math.max(y - width / 2, 0))}px`;
    }

    // Two fingers zoom the board, and the spot between them stays between them.
    _pinch() {
      const { svg, pinch } = this._gesture;
      const [a, b] = [...this._touches.values()];
      const scale = Math.min(
        Math.max((pinch.scale * Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY)) / pinch.distance, 1),
        PAD_ZOOM_MOST
      );
      const rect = svg.getBoundingClientRect();
      const pixels = Math.min(rect.width, rect.height) / (PAD_VIEW / scale);
      if (!pinch.anchor || !(pixels > 0)) return;
      const middle = { x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 };
      this._padZoom =
        scale > 1.02
          ? {
              scale,
              x: pinch.anchor[0] - (middle.x - rect.left - rect.width / 2) / pixels,
              y: pinch.anchor[1] - (middle.y - rect.top - rect.height / 2) / pixels,
            }
          : null;
      svg.setAttribute("viewBox", viewBoxText(padViewBox(this._padZoom)));
    }

    _endGesture() {
      this._clearGesture();
      this._update();
    }

    _clearGesture() {
      this._gesture = null;
      this._touches.clear();
      this._el.loupe.hidden = true;
    }

    // Fingers on the board keep the pad as it is until they let go. A pad that closes or
    // shows its keys ends what the fingers did, which no longer reach it.
    _keepPad(pad) {
      if (this._gesture && pad?.board) return true;
      if (this._gesture) this._clearGesture();
      return false;
    }

    _padAction(action, value) {
      if (this.preview) return;
      const focus = this._padFocus(action);
      const pick = this._pick;
      const data = (extra) => ({ ...(this._entry() ? { config_entry_id: this._entry() } : {}), ...extra });
      if (action === "multiplier") {
        if (pick) pick.multiplier = Number(value);
        else this._multiplier = Number(value);
      } else if (action === "bed" && pick) {
        this._call("homedarts", "correct_dart", data({ dart: pick.dart, segment: value }));
        this._pick = null;
      } else if (action === "bed") {
        this._call("homedarts", "throw_dart", data({ segment: value }));
        this._multiplier = 1;
      } else if (action === "spot") {
        // The bed follows from the spot, in Home Assistant as on the board.
        if (!value) return;
        const [x, y] = value;
        this._call("homedarts", pick ? "correct_dart" : "throw_dart", data({ ...(pick ? { dart: pick.dart } : {}), x, y }));
        this._pick = null;
      } else if (["digit", "erase", "enter", "answer"].includes(action)) {
        this._scoreAction(action, value);
      } else if (action === "board" || action === "keys" || action === "score") {
        this._padBoard = action === "board";
        this._padScore = action === "score";
        this._asking = null;
        this._padZoom = this._padBoard ? this._openZoom() : null;
      } else if (action === "zoom") {
        this._padZoom = padViewBox(this._padZoom).size < PAD_VIEW ? null : this._zoomAt(pick?.dart);
      } else if (action === "cancel") {
        // The question after a score goes, and the score stays to be changed.
        if (this._asking) this._asking = null;
        else this._pick = null;
      } else if (this._confirmed(action)) {
        // Passing the turn and undoing the last visit need a second tap.
        this._call("homedarts", action === "next" ? "next_player" : "undo_visit", data({}));
      }
      this._update();
      focus?.();
    }

  }

  class AutodartsCard extends PadCard {
    static keys = KEYS;

    static defaults = DEFAULTS;

    static form = "live";

    getCardSize() {
      return this._config?.layout === "vertical" ? 10 : 7;
    }

    _css() {
      return CSS;
    }

    _visitHtml(t) {
      const c = this._config;
      const practice = `
        <div class="practice" hidden>
          <div class="practice-head">
            <span class="section-label practice-title"></span>
            <span class="muted practice-meta"></span>
          </div>
          <div class="practice-row">
            <span class="practice-remaining">–</span>
            <div class="practice-route"></div>
          </div>
          <div class="scoreboard" hidden></div>
        </div>`;
      const recent = `<div class="recent" hidden><span class="muted">${t("recent")}</span><div class="recent-list"></div></div>`;
      return `
        <div class="visit">
          <div>
            <div class="visit-label">${t("visit")}</div>
            <div class="score-row">
              <span class="score">–</span>
              <span class="score-unit">${t("points")}</span>
              <span class="progress"></span>
            </div>
          </div>
          ${c.show_practice ? practice : ""}
          <div class="slots"></div>
          <div class="pad-area appear" hidden></div>
          ${c.show_recent ? recent : ""}
        </div>`;
    }

    _boardHtml(t) {
      const c = this._config;
      return `
        <div class="board">
          <div class="board-frame">
            <svg viewBox="-230 -230 460 460" role="img" aria-label="${t("board_label")}">
              <g class="face">${boardSvg(c.board_style)}</g>
              <g class="hits${c.blink ? " blink" : ""}"></g>
              <g class="aim"></g>
              ${c.show_numbers ? `<g class="numbers">${numbersSvg(c.board_style)}</g>` : ""}
              <g class="darts"></g>
            </svg>
          </div>
        </div>`;
    }

    _sessionHtml(t) {
      if (!this._config.show_stats) return "";
      const stats = ["darts", "average", "triples", "bulls", "max"]
        .map((key) => `<div class="stat" data-stat="${key}"><div class="value">–</div><div class="name">${t(key)}</div></div>`)
        .join("");
      return `
        <div class="session">
          <div class="section-head">
            <span class="section-label">${t("session")}</span>
            <span class="since"></span>
          </div>
          <div class="stats">${stats}</div>
        </div>`;
    }

    _footerHtml(t) {
      const c = this._config;
      if (!c.show_connection && !c.show_controls) return "";
      const controls = `
        <div class="controls">
          <button class="primary" data-action="toggle"></button>
          <button data-action="reset">${t("reset")}</button>
          <button data-action="calibrate">${t("calibrate")}</button>
        </div>`;
      return `
        <div class="footer">
          ${c.show_connection ? `<div class="chips"></div>` : ""}
          ${c.show_controls ? controls : ""}
        </div>`;
    }

    _build() {
      const c = this._config;
      const t = (key) => escapeHtml(this._t(key));
      const layout = c.layout === "board" ? "board-only" : c.layout;
      this.shadowRoot.innerHTML = `
        <style>${CSS}</style>
        <ha-card>
          <div class="root">
            <div class="layout ${escapeHtml(layout)}">
              <header>
                <div class="title"></div>
                <div class="pill" role="status"></div>
              </header>
              ${this._visitHtml(t)}
              ${this._boardHtml(t)}
              ${this._sessionHtml(t)}
              ${this._footerHtml(t)}
              <div class="loupe" hidden aria-hidden="true"></div>
            </div>
          </div>
        </ha-card>`;
      const root = this.shadowRoot;
      this._el = {
        title: root.querySelector(".title"),
        pill: root.querySelector(".pill"),
        score: root.querySelector(".score"),
        progress: root.querySelector(".progress"),
        recent: root.querySelector(".recent"),
        recentList: root.querySelector(".recent-list"),
        practice: root.querySelector(".practice"),
        practiceTitle: root.querySelector(".practice-title"),
        practiceMeta: root.querySelector(".practice-meta"),
        practiceRemaining: root.querySelector(".practice-remaining"),
        practiceRoute: root.querySelector(".practice-route"),
        scoreboard: root.querySelector(".scoreboard"),
        aim: root.querySelector(".aim"),
        layout: root.querySelector(".layout"),
        slots: root.querySelector(".slots"),
        pad: root.querySelector(".pad-area"),
        loupe: root.querySelector(".loupe"),
        since: root.querySelector(".since"),
        stats: Object.fromEntries(
          [...root.querySelectorAll(".stat")].map((el) => [el.dataset.stat, el.querySelector(".value")])
        ),
        footer: root.querySelector(".footer"),
        chips: root.querySelector(".chips"),
        controls: root.querySelector(".controls"),
        hits: root.querySelector(".hits"),
        darts: root.querySelector(".darts"),
        svg: root.querySelector("svg"),
      };
      this._initPad(this._el.slots, this._el.layout);
      this._el.controls?.addEventListener("click", (event) => this._onControl(event));
      this._el.chips?.addEventListener("click", (event) => {
        const id = event.target.closest(".chip")?.dataset.entity;
        if (id) this._moreInfo(id);
      });
    }

    _darts() {
      const visit = this._state("visit");
      if (Array.isArray(visit?.attributes?.throws)) return visitThrows(visit);
      // Older integration versions only report the last segment.
      const last = this._state("lastThrow");
      const count = Number(this._state("numThrows")?.state);
      const parsed = usable(last) ? parseSegment(last.state) : null;
      if (!parsed || !(count > 0)) return [];
      return [...Array(Math.min(count, 3) - 1).fill(null), parsed];
    }

    _update() {
      const c = this._config;
      const el = this._el;
      const t = (key) => this._t(key);
      el.title.textContent = this._deviceName();

      const [status, statusText] = this._status();
      this.style.setProperty("--ad-status", STATUS_COLORS[status]);
      this.style.setProperty("--ad-accent", cssColor(c.accent_color, "var(--primary-color)"));
      this.style.setProperty("--ad-highlight", cssColor(c.highlight_color, GOLD));
      this._showStatus(el.pill, statusText);

      const darts = this._darts();
      const known = darts.filter(Boolean);
      const visit = this._state("visit");
      const total = usable(visit)
        ? visit.state
        : known.reduce((sum, dart) => sum + dart.number * dart.multiplier, 0);
      el.score.textContent = darts.length || usable(visit) ? total : "–";
      el.progress.textContent = darts.length ? `${t("dart")} ${darts.length} ${t("of")} 3` : "";
      if (el.recent) {
        const visits = recentVisits(visit?.attributes?.recent_visits);
        el.recent.hidden = !visits.length;
        this._setHtml(
          el.recentList,
          visits
            .map(
              (item) =>
                `<span class="recent-visit" style="--bucket:${VISIT_COLORS[visitBucket(item.score)]}" ` +
                `title="${escapeHtml(item.segments.length ? `${item.segments.join(" · ")} = ${item.score}` : String(item.score))}">${item.score}</span>`
            )
            .join("")
        );
      }

      // Darts of the current visit correct with a tap, which Home Assistant carries out
      // also while the board is offline; the bot's darts do not.
      const tappable = c.corrections && !this.preview;
      if (!tappable) this._pick = null;
      // The practice sensor carries one game at a time; a training game comes first.
      const view = c.show_practice ? gameView((name) => this._state(name)) : { mode: "idle" };
      const dead = deadDarts(view, darts);
      this._setHtml(
        el.slots,
        [0, 1, 2].map((index) => this._slotHtml(darts[index], index, darts.length, tappable, dead[index])).join("")
      );
      this._updatePad(darts);
      this._updatePractice(view);
      this._updateBoard(darts, view);
      this._updateStats();
      // A dartboard without Autodarts has no connections and no detection to control.
      if (el.footer) el.footer.hidden = this._manualBoard();
      this._updateChips();
      this._updateControls(status);
    }

    // A dart of the visit: its bed and points, and a pencil where a tap corrects it. A dart
    // that counted nothing in a Cricket game is struck through.
    _slotHtml(dart, index, count, tappable, dead = false) {
      const t = (key) => escapeHtml(this._t(key));
      const head = `<span class="index">${t("dart")} ${index + 1}</span>`;
      if (!dart) {
        const unknown = index < count;
        return (
          `<div class="slot ${unknown ? "unknown" : "empty"}">${head}` +
          `<span class="segment">${unknown ? "?" : "–"}</span><span class="value">&nbsp;</span></div>`
        );
      }
      const correctable = tappable && Number.isInteger(dart.dart) && !dart.bot;
      const picked = correctable && this._pick?.dart === dart.dart;
      const marks = [dart.total ? "total" : kind(dart), index === count - 1 && "latest", picked && "picked", dead && "dead"];
      const style = ["slot", ...marks.filter(Boolean)].join(" ");
      const bed = label(this._hass, dart);
      const points = dart.number * dart.multiplier;
      // The spaces between the parts keep their words apart for screen readers.
      const content = `${head} <span class="segment">${escapeHtml(bed)}</span> <span class="value">${points} ${t("points")}</span>`;
      const nothing = dead ? this._t("cricket_dead") : "";
      const title = nothing ? ` title="${escapeHtml(nothing)}"` : "";
      if (!correctable) return `<div class="${style}"${title}>${content}</div>`;
      // The label starts with what the tile shows and then says what a tap does:
      // "Dart 1 T20 60 points – Correct dart 1".
      const shown = `${this._t("dart")} ${index + 1} ${bed} ${points} ${this._t("points")}`;
      const spoken = [shown, nothing, fill(this._t("correct_title"), { dart: dart.dart })];
      return (
        `<button type="button" class="${style} tappable" data-dart="${dart.dart}" data-focus="dart-${dart.dart}"` +
        `${title} aria-label="${escapeHtml(spoken.filter(Boolean).join(" – "))}">${content}${EDIT_ICON}</button>`
      );
    }

    // The pad of the dart being corrected, or the keypad while darts are entered by hand,
    // below the darts; fingers on its board keep it as it is until they let go. While the
    // bot is at the board, it waits.
    _updatePad(darts) {
      const el = this._el;
      const known = darts.filter(Boolean);
      const base = this._padBase(known);
      const pick = this._pick;
      const view = gameView((name) => this._state(name));
      const disabled = botAtBoard(view);
      let pad = null;
      if (pick) {
        pad = { dart: pick.dart, multiplier: pick.multiplier, disabled, ...base };
      } else if (this._keypad() && !this.preview) {
        // The last visit can be undone while no dart of the next one is in.
        const undo = this._state("practice")?.attributes?.undo === true && !known.length;
        const confirm = ["next", "undo"].includes(this._confirm) ? this._confirm : null;
        pad = this._keypadPad(view, disabled, base, { undo, confirm });
      }
      el.pad.hidden = !pad;
      if (!this._keepPad(pad)) this._setHtml(el.pad, pad ? padHtml(pad, { t: (key) => this._t(key) }) : "");
    }

    _updatePractice(view) {
      const el = this._el;
      if (!el.practice) return;
      el.practice.hidden = view.mode === "idle";
      if (view.mode === "idle") return;
      const panel = livePanel({ ...view, summary: this._matchSummary(view) }, this._ui());
      el.practiceTitle.textContent = panel.title;
      el.practiceMeta.textContent = panel.meta;
      el.practiceRemaining.textContent = panel.big;
      el.practiceRoute.title = panel.routeTitle ?? "";
      this._setHtml(el.practiceRoute, panel.route);
      el.scoreboard.hidden = !panel.rows;
      this._setHtml(el.scoreboard, panel.rows);
    }

    _updateBoard(darts, view) {
      const c = this._config;
      const latest = darts.length - 1;
      const highlighted =
        c.highlight === "none"
          ? []
          : darts
              .map((dart, index) => (dart && (c.highlight !== "last" || index === latest) ? dart : null))
              // The made-up darts of a visit entered as its score light no bed.
              .filter((dart) => dart && !dart.total);
      const paths = new Set(highlighted.flatMap(beds));
      this._setHtml(
        this._el.hits,
        [...paths]
          .map((id) => bedPath(id))
          .filter(Boolean)
          .map((d) => `<path class="hit" d="${d}"/>`)
          .join("")
      );
      // The bed the player aims at next: the route, the target or the doubles that open a leg.
      this._setHtml(
        this._el.aim,
        aimBeds(view)
          .map((id) => bedPath(id))
          .filter(Boolean)
          .map((d) => `<path d="${d}"/>`)
          .join("")
      );

      this._setHtml(
        this._el.darts,
        c.show_markers
          ? darts
              .map((dart, index) => {
                if (!dart || !Number.isFinite(dart.x) || !Number.isFinite(dart.y)) return "";
                const radius = Math.hypot(dart.x, dart.y) * NORM;
                const scale = radius > R.board - 4 ? (R.board - 4) / radius : 1;
                const x = fmt(dart.x * NORM * scale);
                const y = fmt(-dart.y * NORM * scale);
                return (
                  `<g class="dart${index === latest ? " latest" : ""}" transform="translate(${x} ${y})">` +
                  `<circle class="halo" r="11"/><circle class="pin" r="9.5"/><text>${index + 1}</text></g>`
                );
              })
              .join("")
          : ""
      );
      const summary = darts
        .filter(Boolean)
        .map((dart) => label(this._hass, dart))
        .join(", ");
      this._el.svg.setAttribute(
        "aria-label",
        summary ? `${this._t("board_label")}: ${summary}` : this._t("board_label")
      );
    }

    _updateStats() {
      const stats = this._el.stats;
      if (!stats.darts) return;
      const darts = this._number("darts");
      const points = this._number("points");
      // Older integration versions have no average sensor.
      const average = this._ids.average
        ? this._number("average")
        : darts > 0 && points !== null
          ? (points / darts) * 3
          : null;
      stats.darts.textContent = this._format(darts);
      stats.average.textContent = this._format(average, 1);
      stats.triples.textContent = this._format(this._number("triples"));
      stats.bulls.textContent = this._format(this._number("bulls"));
      stats.max.textContent = this._format(this._number("max"));
      this._el.since.textContent = this._since();
    }

    _updateChips() {
      if (!this._el.chips) return;
      const t = (key) => escapeHtml(this._t(key));
      const chip = (name, text, alert = false) => {
        const id = this._ids[name];
        if (!id) return "";
        const state = this._hass.states[id]?.state;
        const cls = alert ? "alert" : state === "on" ? "on" : "off";
        return `<button class="chip ${cls}" data-entity="${escapeHtml(id)}" data-focus="${escapeHtml(id)}">${text}</button>`;
      };
      const problem = this._state("cameraProblem")?.state === "on";
      this._setHtml(
        this._el.chips,
        [
          chip("connected", t("board")),
          chip("realtime", t("realtime")),
          problem ? chip("cameraProblem", t("camera_problem"), true) : chip("cameras", t("cameras")),
        ].join("")
      );
    }

    _updateControls(status) {
      const controls = this._el.controls;
      if (!controls) return;
      // Without a detection switch, the board status tells whether detection runs.
      const running = detectionRunning((name) => this._state(name), status);
      const toggle = controls.querySelector('[data-action="toggle"]');
      toggle.textContent = this._t(running ? "stop" : "start");
      toggle.classList.toggle("stop", running);
      toggle.disabled = status === "offline" || !(this._ids.detection || this._ids[running ? "stop" : "start"]);
      for (const action of ["reset", "calibrate"]) {
        const button = controls.querySelector(`[data-action="${action}"]`);
        const confirming = this._confirm === action;
        button.textContent = this._t(confirming ? "confirm" : action);
        button.classList.toggle("confirm", confirming);
        button.disabled = status === "offline" || !this._ids[action];
      }
    }

    _confirmChanged() {
      if (!this._el) return;
      this._updateControls(this._status()[0]);
      // The keypad's second taps, for the next player and the undo.
      this._updatePad(this._darts());
    }

    _onControl(event) {
      const action = event.target.closest("button")?.dataset.action;
      if (!action || this.preview) return;
      if (action === "toggle") {
        this._toggleDetection();
        return;
      }
      // Reset and calibration discard detected darts, so they need a second tap.
      if (this._confirmed(action)) this._press(this._ids[action]);
      this._confirmChanged();
    }
  }

  // Training card ---------------------------------------------------------------

  const TRAINING_TILES = ["highest", "scores_100", "scores_140", "max", "triple_rate", "doubles", "bulls", "misses"];

  class AutodartsTrainingCard extends CardBase {
    static keys = TRAINING_KEYS;

    static defaults = TRAINING_DEFAULTS;

    static form = "training";

    constructor() {
      super();
      // The visits of the session and the time of the newest board event read for them.
      this._visits = [];
      this._historyTime = -Infinity;
      // The heatmap mode and whose darts it shows, as switched in the card.
      this._mode = null;
      this._source = null;
      this._positions = null;
      this._positionsFor = null;
      // The darts of the current visit last drawn, and the drawing of the positions.
      this._live = [];
      this._drawn = null;
      // The points per dart of the aim map last drawn, the model of the map computed or
      // on its way, and who computes them.
      this._aimField = null;
      this._aimFor = null;
      this._aimFields = new AimFields();
      this._aimDrawn = null;
    }

    // A new configuration shows its own mode and player again.
    setConfig(config) {
      this._mode = null;
      this._source = null;
      super.setConfig(config);
    }

    getCardSize() {
      return 9;
    }

    _css() {
      return TRAINING_CSS;
    }

    // The history stream and the worker of the aim map end with the card; the stream
    // starts again when it returns, and the worker with the next map.
    disconnectedCallback() {
      super.disconnectedCallback();
      this._closeHistory();
      // A map on its way comes to nothing, and comes anew when the card returns.
      this._aimFields.stop();
      this._aimFor = this._aimField?.key ?? null;
    }

    connectedCallback() {
      super.connectedCallback();
      if (this._built) this._updateHistory();
    }

    // Only visits and session starts change the card; other board events leave it alone.
    // Of the current visit, only where its darts landed and the newest booked visit matter.
    _relevant(id, state) {
      if (id === this._ids.visit) {
        return `${newestVisit(state)}|${JSON.stringify(visitPositions(state?.attributes?.throws))}`;
      }
      if (id !== this._ids.events) return state;
      const type = state?.attributes?.event_type;
      if (this._event?.id !== id || VISIT_EVENTS.includes(type)) {
        this._event = { id, state };
      }
      return this._event.state;
    }

    _heatHtml(t) {
      const c = this._config;
      const legend = [0, 0.25, 0.5, 0.75, 1].map(heatColor).join(", ");
      const modes = HEAT_MODES.map(
        (mode) => `<button type="button" data-mode="${mode}" aria-pressed="false">${t(`mode_${mode}`)}</button>`
      ).join("");
      const controls = c.show_heatmap_controls
        ? `<div class="heat-controls">
            <div class="segmented modes" role="group" aria-label="${t("mode")}">${modes}</div>
            <div class="segmented sources" role="group" aria-label="${t("heatmap_source")}" hidden></div>
          </div>`
        : "";
      return `
        <div class="heat">
          <div class="heat-head"><div class="section-label">${t("heatmap")}</div>${controls}</div>
          <div class="heat-frame">
            <svg viewBox="-230 -230 460 460" role="img" aria-label="${t("heatmap_label")}">
              <defs><filter id="ad-density" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="4"/>
              </filter></defs>
              <g class="face">${boardSvg(c.board_style)}</g>
              <g class="heat-layer"></g>
              <g class="numbers">${numbersSvg(c.board_style)}</g>
            </svg>
            <div class="heat-caption" aria-live="polite"></div>
          </div>
          <div class="legend">
            <span class="muted legend-min">1</span>
            <div class="legend-bar" style="background: linear-gradient(90deg, ${legend})"></div>
            <span class="muted legend-max">–</span>
          </div>
          <ul class="visually-hidden heat-list"></ul>
          <div class="groups" hidden></div>
        </div>`;
    }

    _sideHtml(t) {
      const c = this._config;
      const tiles = TRAINING_TILES.map(
        (key) => `<div class="tile" data-tile="${key}"><div class="value">–</div><div class="name">${t(key)}</div></div>`
      ).join("");
      return `
        <div class="side">
          ${
            c.show_stats
              ? `<div class="tiles" role="group" aria-label="${t("statistics")}">${tiles}</div>` +
                `<button type="button" class="link details" aria-label="${t("statistics_label")}">` +
                `${t("details")}${cueHtml("details", true)}</button>`
              : ""
          }
          ${
            c.show_top
              ? `<div class="top-section"><div class="section-label">${t("top")}</div><div class="top"></div></div>`
              : ""
          }
        </div>`;
    }

    _bodyHtml(t) {
      const c = this._config;
      const side = c.show_stats || c.show_top;
      if (!c.show_heatmap && !side) return "";
      return `
        <div class="body${c.show_heatmap && side ? "" : " single"}">
          ${c.show_heatmap ? this._heatHtml(t) : ""}
          ${side ? this._sideHtml(t) : ""}
        </div>`;
    }

    _sessionsHtml(t) {
      return `
        <div class="sessions" hidden>
          <div class="section-label">${t("past_sessions")}</div>
          <table class="session-table">
            <thead><tr>
              <th>${t("session_end")}</th><th>${t("duration")}</th><th>${t("darts")}</th>
              <th>${t("average")}</th><th>${t("highest_short")}</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>`;
    }

    _footerHtml(t) {
      return `
        <div class="footer-row">
          <span class="muted session-state"></span>
          <div class="footer-actions">
            <button class="action" data-action="session" hidden></button>
            <button class="action" data-action="new_session">${t("new_session")}</button>
          </div>
        </div>`;
    }

    _build() {
      const c = this._config;
      const t = (key) => escapeHtml(this._t(key));
      this.shadowRoot.innerHTML = `
        <style>${TRAINING_CSS}</style>
        <ha-card>
          <div class="root">
            <div class="training">
              <header>
                <div class="title"></div>
                <div class="muted since"></div>
              </header>
              <div class="daily" hidden>
                <span class="streak" hidden><span aria-hidden="true">🔥</span> <span class="streak-text"></span></span>
                <div class="goal" hidden>
                  <div class="goal-bar" hidden><span></span></div>
                  <span class="goal-text"></span>
                </div>
              </div>
              <div class="hero">
                <div>
                  <div class="average">–</div>
                  <div class="average-label">${t("average_long")}</div>
                </div>
                <div class="totals">
                  <div class="total"><div class="value" data-total="darts">–</div><div class="name">${t("darts")}</div></div>
                  <div class="total"><div class="value" data-total="visits">–</div><div class="name">${t("visits")}</div></div>
                </div>
              </div>
              <div class="empty-hint" hidden>${t("no_darts")}</div>
              ${this._bodyHtml(t)}
              ${c.show_bests ? `<div class="bests" hidden><div class="section-label">${t("personal_bests")}</div><dl></dl></div>` : ""}
              ${
                c.show_history
                  ? `<div class="history"><div class="section-label">${t("history")}</div><div class="history-chart"></div></div>`
                  : ""
              }
              ${c.show_sessions ? this._sessionsHtml(t) : ""}
              ${c.show_reset ? this._footerHtml(t) : ""}
            </div>
          </div>
        </ha-card>`;
      const root = this.shadowRoot;
      this._el = {
        title: root.querySelector(".title"),
        since: root.querySelector(".since"),
        daily: root.querySelector(".daily"),
        streak: root.querySelector(".streak"),
        streakText: root.querySelector(".streak-text"),
        goal: root.querySelector(".goal"),
        goalBar: root.querySelector(".goal-bar"),
        goalFill: root.querySelector(".goal-bar span"),
        goalText: root.querySelector(".goal-text"),
        average: root.querySelector(".average"),
        totals: Object.fromEntries([...root.querySelectorAll("[data-total]")].map((el) => [el.dataset.total, el])),
        empty: root.querySelector(".empty-hint"),
        heat: root.querySelector(".heat-layer"),
        heatSvg: root.querySelector(".heat-frame svg"),
        heatCaption: root.querySelector(".heat-caption"),
        heatList: root.querySelector(".heat-list"),
        legendMin: root.querySelector(".legend-min"),
        legendMax: root.querySelector(".legend-max"),
        modes: root.querySelector(".modes"),
        sources: root.querySelector(".sources"),
        groups: root.querySelector(".heat .groups"),
        tiles: Object.fromEntries(
          [...root.querySelectorAll("[data-tile]")].map((el) => [el.dataset.tile, el.querySelector(".value")])
        ),
        bests: root.querySelector(".bests"),
        bestList: root.querySelector(".bests dl"),
        top: root.querySelector(".top"),
        history: root.querySelector(".history-chart"),
        newSession: root.querySelector('[data-action="new_session"]'),
        session: root.querySelector('[data-action="session"]'),
        sessionState: root.querySelector(".session-state"),
        sessions: root.querySelector(".sessions"),
        sessionRows: root.querySelector(".session-table tbody"),
      };
      this._el.newSession?.addEventListener("click", () => {
        if (this.preview) return;
        if (this._confirmed("new_session")) this._press(this._ids.newSession);
        this._confirmChanged();
      });
      this._el.session?.addEventListener("click", () => {
        if (this.preview || !this._ids.session) return;
        const running = this._state("session")?.state === "on";
        // Starting is harmless; ending needs a second tap like a new session.
        if (!running || this._confirmed("end_session")) {
          this._call("switch", running ? "turn_off" : "turn_on", { entity_id: this._ids.session });
        }
        this._confirmChanged();
      });
      // A tap on the tiles opens the details; keyboards and screen readers have a button of their own.
      root.querySelector(".details")?.addEventListener("click", () => this._moreInfo(this._ids.darts));
      // A tap on a bed tells its hits, on a touch screen too.
      this._el.heatSvg?.addEventListener("click", (event) => {
        const title = event.target.closest(".heat-bed")?.querySelector("title");
        this._el.heatCaption.textContent = title ? title.textContent : "";
      });
      this._el.modes?.addEventListener("click", (event) => {
        const button = event.target.closest?.("button[data-mode]");
        if (!button) return;
        this._mode = button.dataset.mode;
        this._update();
      });
      this._el.sources?.addEventListener("click", (event) => {
        const button = event.target.closest?.("button[data-source]");
        if (!button) return;
        this._source = button.dataset.source;
        this._update();
      });
    }

    _confirmChanged() {
      const button = this._el?.newSession;
      if (button) {
        const confirming = this._confirm === "new_session";
        button.textContent = this._t(confirming ? "confirm" : "new_session");
        button.classList.toggle("confirm", confirming);
        button.disabled = !this._ids.newSession;
      }
      const toggle = this._el?.session;
      if (toggle) {
        const running = this._state("session")?.state === "on";
        const confirming = running && this._confirm === "end_session";
        toggle.hidden = !this._ids.session;
        toggle.textContent = this._t(confirming ? "confirm" : running ? "end_session" : "start_session");
        toggle.classList.toggle("primary", !running);
        toggle.classList.toggle("confirm", confirming);
      }
    }

    _updateSessions() {
      const el = this._el;
      const session = this._state("session");
      if (el.sessionState) {
        // The end of the last session as it was booked; the switch's last change is
        // also every restart of Home Assistant.
        const ended = pastSessions(this._state("lastSession")?.attributes?.sessions, 1)[0]?.ended;
        el.sessionState.textContent = !usable(session)
          ? ""
          : session.state === "on"
            ? this._t("session_running")
            : ended
              ? `${this._t("session_ended")} ${formatDateTime(this._hass, ended)}`
              : this._t("no_session");
      }
      if (!el.sessions) return;
      const sessions = pastSessions(this._state("lastSession")?.attributes?.sessions);
      const duration = (minutes) =>
        minutes === null
          ? "–"
          : minutes < 1
            ? this._t("under_a_minute")
            : fill(this._t("unit_minutes"), { value: this._format(minutes) });
      el.sessions.hidden = !sessions.length;
      this._setHtml(
        el.sessionRows,
        sessions
          .map((item) =>
            [
              formatDateTime(this._hass, item.ended),
              duration(item.minutes),
              this._format(item.darts),
              this._format(item.average, 1),
              this._format(item.best),
            ]
              .map((cell) => `<td>${escapeHtml(cell)}</td>`)
              .join("")
          )
          .map((row) => `<tr>${row}</tr>`)
          .join("")
      );
    }

    // The streak and today's darts towards the daily goal.
    _updateDaily() {
      const el = this._el;
      const streak = this._number("streak");
      const today = this._number("today");
      el.daily.hidden = !(streak > 0) && today === null;
      el.streak.hidden = !(streak > 0);
      el.streakText.textContent = `${this._format(streak)} ${this._t(streak === 1 ? "streak_day" : "streak_days")}`;
      el.goal.hidden = today === null;
      const attributes = this._state("today")?.attributes || {};
      const goal = Number(attributes.goal) || 0;
      el.goalBar.hidden = !goal;
      el.goalFill.style.width = goal ? `${Math.min(100, (today / goal) * 100)}%` : "0";
      el.goal.classList.toggle("reached", attributes.goal_reached === true);
      el.goalText.textContent = `${
        goal ? `${this._format(today)} / ${this._format(goal)}` : this._format(today)
      } ${this._t("darts_today")}`;
    }

    _updateBests() {
      if (!this._el.bests) return;
      const records = bestsView(this._state("bests"), this._state("streak"));
      this._el.bests.hidden = !records.length;
      this._setHtml(this._el.bestList, bestsHtml(records, this._ui()));
    }

    _update() {
      const c = this._config;
      const el = this._el;
      this.style.setProperty("--ad-accent", cssColor(c.accent_color, "var(--primary-color)"));
      el.title.textContent = c.title || `${this._t("training")} · ${this._deviceName()}`;
      el.since.textContent = this._since();
      this._updateDaily();

      const darts = this._number("darts");
      const points = this._number("points");
      const average = this._ids.average
        ? this._number("average")
        : darts > 0 && points !== null
          ? (points / darts) * 3
          : null;
      el.average.textContent = this._format(average, 1);
      el.totals.darts.textContent = this._format(darts);
      el.totals.visits.textContent = this._format(this._number("visits"));
      el.empty.hidden = darts > 0;
      const idle = this._state("session")?.state === "off";
      el.empty.textContent = this._t(idle ? "no_session_hint" : "no_darts");

      const tiles = el.tiles;
      if (tiles.highest) {
        for (const key of ["highest", "scores_100", "scores_140", "max", "doubles", "bulls", "misses"]) {
          tiles[key].textContent = this._format(this._number(key));
        }
        tiles.max.parentElement.classList.toggle("hot", this._number("max") > 0);
        const triples = this._number("triples");
        tiles.triple_rate.textContent = darts > 0 && triples !== null ? this._percent((triples / darts) * 100, 1) : "–";
      }

      this._updateHeatmap(darts);
      this._updateBests();
      this._updateHistory();
      this._updateSessions();
      this._confirmChanged();
    }

    // The heatmap mode chosen in the card, otherwise the configured one.
    _heatMode() {
      const mode = this._mode ?? this._config.mode;
      return HEAT_MODES.includes(mode) ? mode : "beds";
    }

    // Whose darts the heatmap shows: a player's name, or empty for the session.
    _heatSource() {
      return this._source ?? String(this._config.player ?? "").trim();
    }

    _profile(name) {
      const players = this._state("profiles")?.attributes?.players;
      const wanted = name.toLowerCase();
      return (Array.isArray(players) ? players : []).find(
        (player) => typeof player?.name === "string" && player.name.toLowerCase() === wanted
      );
    }

    // The session or a player: hits for the beds and numbers, positions from the board.
    _updateHeatmap(darts) {
      const source = this._heatSource();
      const profile = source ? this._profile(source) : null;
      const hits = source ? profile?.hits : this._state("darts")?.attributes?.hits;
      this._updateHeatControls(source);
      if (this._el.heat && ["positions", "aim"].includes(this._heatMode())) this._loadPositions(source);
      this._updateHeat(hits);
      // A player's shares are of the hits the profile counted; darts of older versions have no hits.
      const counted = validHits(hits).reduce((sum, [, count]) => sum + count, 0);
      this._updateTop(hits, source ? counted : darts);
    }

    _updateHeatControls(source) {
      const el = this._el;
      if (el.heatSvg) {
        const labels = { positions: "positions_label", aim: "aim_label" };
        el.heatSvg.setAttribute("aria-label", this._t(labels[this._heatMode()] ?? "heatmap_label"));
      }
      if (!el.modes) return;
      for (const button of el.modes.querySelectorAll("button")) {
        button.setAttribute("aria-pressed", String(button.dataset.mode === this._heatMode()));
      }
      const players = this._state("profiles")?.attributes?.players;
      const names = (Array.isArray(players) ? players : [])
        .filter((player) => named(player?.name) && (finite(player.darts_thrown) ?? 0) > 0)
        .map((player) => player.name)
        .sort((a, b) => a.localeCompare(b));
      if (source && !names.some((name) => name.toLowerCase() === source.toLowerCase())) names.push(source);
      el.sources.hidden = !names.length;
      this._setHtml(
        el.sources,
        ["", ...names]
          .map(
            (name) =>
              `<button type="button" data-source="${escapeHtml(name)}" data-focus="${escapeHtml(`source:${name}`)}" aria-pressed="${
                name.toLowerCase() === source.toLowerCase()
              }">${escapeHtml(name || this._t("heatmap_session"))}</button>`
          )
          .join("")
      );
    }

    // New positions come with every booked visit: a player's with the darts of the profile,
    // the session's with the newest recent visit, which an undone visit takes back, and
    // with a new session. Without the visit sensor, the visits of the session count them.
    // The recent visits change together with the darts of the visit, so its darts never
    // leave the board before they come back logged.
    _positionsKey(source) {
      const visit = this._state("visit");
      const count = source
        ? finite(this._profile(source)?.darts_thrown)
        : visit
          ? `${this._state("started")?.state}|${newestVisit(visit)}`
          : this._number("visits");
      return `${this._deviceId}|${source}|${count ?? ""}`;
    }

    // The darts of the current visit, while the session logs them.
    _livePositions(source) {
      if (source || this._state("session")?.state !== "on") return [];
      return visitPositions(this._state("visit")?.attributes?.throws);
    }

    // Only the aim map asks for the aim model, which Home Assistant works out anew for new
    // darts; an answer with it serves the positions, too.
    async _loadPositions(source) {
      const aim = this._heatMode() === "aim";
      const darts = this._positionsKey(source);
      const key = aim ? `${darts}|aim` : darts;
      const asked = this._positionsFor;
      if (asked === key || asked === `${darts}|aim` || typeof this._hass.callWS !== "function") return;
      this._positionsFor = key;
      let result;
      try {
        result = await this._hass.callWS({
          type: "homedarts/positions",
          device_id: this._deviceId,
          ...(source ? { player: source } : {}),
          ...(aim ? { aim: true } : {}),
        });
      } catch {
        // No answer is no board without positions: after a restart of Home Assistant or a
        // dropped connection, the drawing stays as it is and the next update asks again.
        if (this._positionsFor === key) this._positionsFor = null;
        return;
      }
      if (this._positionsFor !== key) return;
      const positions = validPositions(result?.positions);
      this._positions = {
        key,
        source,
        positions,
        spread: spreadView(result?.spread),
        aim: aim ? aimView(result?.aim) : null,
      };
      // An answer that arrives after a switch to beds or numbers waits for positions or the aim map.
      if (this._heatMode() === "positions") this._drawPositions();
      if (this._heatMode() === "aim") this._drawAim();
    }

    // Where the player or the session scores the most per dart: the points of every aim
    // point, which the worker computes once per model, with the best aim of Home Assistant.
    // Without enough darts at a treble, the card says how many are missing.
    _drawAim() {
      const el = this._el;
      const source = this._heatSource();
      const shown = this._positions?.source === source ? this._positions.aim : null;
      const view = shown?.model ? shown : null;
      if (view && this._aimFor !== view.key) this._loadAim(view.key, view.model);
      const ready = view && this._aimField?.key === view.key ? this._aimField : null;
      this._live = [];
      el.heatCaption.textContent = "";
      // The map is drawn once per field and best aim, not with every update of the card.
      if (ready && (this._aimDrawn?.field !== ready || this._aimDrawn.best !== view.best)) {
        this._aimDrawn = { source, field: ready, best: view.best, html: aimHtml(ready, view.best) };
      }
      // While the field of a new model is on its way, the last map of the same darts stays.
      const drawn = view && (ready || this._aimDrawn?.source === source) ? this._aimDrawn : null;
      const field = drawn?.field;
      this._setHtml(el.heat, drawn ? drawn.html : "");
      const ui = this._ui();
      this._setHtml(
        el.heatList,
        view
          ? aimRows(view, ui)
              .map(({ bed, text }) => `<li>${escapeHtml(`${ui.label(bed)}: ${text}`)}</li>`)
              .join("")
          : ""
      );
      el.legendMin.textContent = field ? this._format(field.high * AIM_FLOOR, 1) : "–";
      el.legendMax.textContent = field ? this._format(field.high, 1) : "–";
      el.groups.hidden = !shown;
      // Without a model, how many darts at a treble are missing: at least one.
      const more = () =>
        fill(this._t("aim_more"), {
          needed: this._format(shown.needed),
          missing: this._format(Math.max(shown.needed - shown.darts, 1)),
        });
      this._setHtml(
        el.groups,
        view ? aimSummaryHtml(view, ui) : shown ? `<div class="empty-hint">${escapeHtml(more())}</div>` : ""
      );
    }

    async _loadAim(key, model) {
      this._aimFor = key;
      const field = await this._aimFields.compute(aimRequest(model));
      // A newer model is on its way, or the card left the page.
      if (!field || this._aimFor !== key) return;
      this._aimField = { key, ...field };
      if (this._heatMode() === "aim") this._drawAim();
    }

    _drawPositions() {
      const el = this._el;
      if (!el.heat) return;
      const source = this._heatSource();
      const shown = this._positions?.source === source ? this._positions : null;
      // A visit booked just now keeps its darts on the board until they come back logged.
      const live = shown && this._positionsFor !== shown.key ? this._live : this._livePositions(source);
      this._live = live;
      const positions = shown?.positions ?? [];
      // The density is drawn once per answer and visit, not with every update of the card.
      const drawn = JSON.stringify(live);
      if (this._drawn?.shown !== shown || this._drawn.live !== drawn) {
        this._drawn = { shown, live: drawn, html: positionsHtml(positions, live) };
      }
      this._setHtml(el.heat, this._drawn.html);
      this._setHtml(el.heatList, "");
      const count = positions.length + live.length;
      el.legendMin.textContent = this._t("legend_few");
      el.legendMax.textContent = count ? this._t("legend_many") : "–";
      // Groupings need darts at a bed the game knows; without positions, the card says so.
      el.groups.hidden = !shown || (count > 0 && !shown.spread.length);
      this._setHtml(
        el.groups,
        shown && !count
          ? `<div class="empty-hint">${escapeHtml(this._t("positions_empty"))}</div>`
          : spreadHtml(shown?.spread ?? [], this._ui())
      );
    }

    _updateHeat(hits) {
      const el = this._el;
      if (!el.heat) return;
      if (this._heatMode() === "positions") {
        this._drawPositions();
        return;
      }
      if (this._heatMode() === "aim") {
        this._drawAim();
        return;
      }
      // Back in positions mode, no visit of long ago stays on the board.
      this._live = [];
      el.groups.hidden = true;
      el.legendMin.textContent = "1";
      const levels = heatLevels(hits, this._heatMode());
      const max = Math.max(0, ...levels.values());
      const counts = new Map(validHits(hits));
      const total = [...counts.values()].reduce((sum, count) => sum + count, 0);
      // What a hit bed tells: its name, its hits and their share.
      const describe = (bed) => {
        // Tooltips name the scoring bed; singles cover both single areas.
        const key = bed === "Bull" ? "BULL" : bed.replace(/^S[IO]/, "S");
        const numbers = this._heatMode() === "numbers";
        const count = numbers ? levels.get(bed) : counts.get(key);
        const name = numbers ? (bed === "Bull" || bed === "25" ? "Bull" : bed.replace(/^\D+/, "")) : hitLabel(this._hass, key);
        return [`${name}: ${count} ${this._t("hits")} · ${this._percent((count / total) * 100, 1)}`, count];
      };
      const beds = max ? [...levels.keys()].filter((bed) => bedPath(bed)).map((bed) => [bed, describe(bed)]) : [];
      const markup = beds
        .map(([bed, [text]]) => {
          const ratio = heatRatio(levels.get(bed), max);
          return (
            `<path class="heat-bed" d="${bedPath(bed)}" fill="${heatColor(ratio)}" fill-opacity="${fmt(0.6 + 0.35 * ratio)}">` +
            `<title>${escapeHtml(text)}</title></path>`
          );
        })
        .join("");
      // A tapped bed told its hits of the board as it was.
      if (el.heat._adHtml !== markup) el.heatCaption.textContent = "";
      this._setHtml(el.heat, markup);
      // The same counts as a list for screen readers, most hit first, every bed once.
      const listed = new Map(beds.map(([, described]) => described));
      this._setHtml(
        el.heatList,
        [...listed]
          .sort((a, b) => b[1] - a[1])
          .map(([text]) => `<li>${escapeHtml(text)}</li>`)
          .join("")
      );
      el.legendMax.textContent = max ? this._format(max) : "–";
    }

    _updateTop(hits, darts) {
      if (!this._el.top) return;
      const top = topHits(hits, 5);
      const most = top[0]?.[1] || 0;
      this._setHtml(
        this._el.top,
        top.length
          ? top
              .map(([key, count]) => {
                const width = count / most;
                const share = darts > 0 ? ` · ${this._percent((count / darts) * 100, 0)}` : "";
                return (
                  `<div class="top-row"><span class="key">${escapeHtml(hitLabel(this._hass, key))}</span>` +
                  `<div class="bar"><div class="fill" style="width:${fmt(width * 100)}%;background:${heatColor(heatRatio(count, most))}"></div></div>` +
                  `<span class="count">${escapeHtml(`${this._format(count)}×${share}`)}</span></div>`
                );
              })
              .join("")
          : `<div class="empty-hint">–</div>`
      );
    }

    _sessionStart() {
      const started = Date.parse(this._state("started")?.state);
      return Number.isFinite(started) ? started : 0;
    }

    // The visits of the session: what the recorder has since the session started, then
    // every board event as it happens. Home Assistant sends state changes that come
    // together in one message, and the page shows only the last of them; the history
    // stream has each one, so no visit goes missing behind the turn that follows it.
    _updateHistory() {
      if (!this._el.history) {
        this._closeHistory();
        return;
      }
      // Only leaving the page closes the stream, so a card away from the page opens it when it comes back.
      if (!this.isConnected) return;
      const since = this._sessionStart();
      const key = `${this._ids.events}|${since}`;
      if (this._historyFor !== key) this._openHistory(since, key);
      // Without the recorder, the events entity's state still adds the visits it shows.
      if (!this._stream) this._addRows([this._state("events")]);
      this._drawHistory();
    }

    // A new session or board starts an empty history.
    _openHistory(since, key) {
      this._closeHistory();
      this._historyFor = key;
      this._historyStart = since;
      this._visits = [];
      this._historyTime = -Infinity;
      const id = this._ids.events;
      const connection = this._hass.connection;
      if (!id || typeof connection?.subscribeMessage !== "function") return;
      // The recorder keeps ten days by default; older visits are not needed.
      const start = Math.max(since, Date.now() - 7 * 86400000);
      const stream = Promise.resolve(
        connection.subscribeMessage(
          (message) => {
            if (this._historyFor !== key) return;
            this._addRows(message?.states?.[id]);
            this._drawHistory();
          },
          {
            type: "history/stream",
            entity_ids: [id],
            start_time: new Date(start).toISOString(),
            minimal_response: false,
            no_attributes: false,
            significant_changes_only: false,
          }
        )
      );
      this._stream = stream;
      stream.catch(() => {
        // Without the recorder, visits of the open dashboard still appear.
        if (this._stream === stream) this._stream = null;
      });
    }

    _closeHistory() {
      const stream = this._stream;
      this._stream = null;
      this._historyFor = null;
      stream?.then((unsubscribe) => unsubscribe()).catch(() => {});
    }

    // Board events newer than those read before: a stream that starts again after a lost
    // connection sends the older ones once more.
    _addRows(rows) {
      const time = (row) => Date.parse(row?.s ?? row?.state);
      const fresh = (Array.isArray(rows) ? rows : []).filter((row) => time(row) > this._historyTime);
      if (!fresh.length) return;
      this._historyTime = Math.max(...fresh.map(time));
      // The newest visits, as many as the largest chart shows.
      this._visits = visitsFromHistory(fresh, this._historyStart, this._visits).slice(-HISTORY_LIMIT);
    }

    _historySize() {
      return Math.min(HISTORY_LIMIT, Math.max(5, Number(this._config.history_size) || 20));
    }

    _drawHistory() {
      // The stream draws only while the chart exists: without it, the stream is closed.
      const chart = this._el.history;
      const visits = this._visits.slice(-this._historySize());
      if (!visits.length) {
        chart.removeAttribute("role");
        chart.removeAttribute("aria-label");
        this._setHtml(chart, `<div class="empty-hint">${escapeHtml(this._t("history_empty"))}</div>`);
        return;
      }
      const size = this._historySize();
      const labels = size <= 30;
      const share = (score) => fmt(Math.min(180, Math.max(0, score)) / 180);
      // A narrow chart shows only the last slots, the rest marked far, so that every
      // score above its bar stays readable.
      const far = (index) => (index < visits.length - HISTORY_NARROW || index >= Math.max(HISTORY_NARROW, visits.length) ? " far" : "");
      const bars = visits.map((visit, index) => {
        const tip = `${visit.segments.join(" · ")}${visit.segments.length ? " = " : ""}${visit.score}`;
        return (
          `<div class="visit-bar${far(index)}" title="${escapeHtml(tip)}">` +
          (labels ? `<span class="label">${visit.score}</span>` : "") +
          `<div class="fill" style="--height:${share(visit.score)};background:${VISIT_COLORS[visitBucket(visit.score)]}"></div></div>`
        );
      });
      // Empty slots keep the bar width steady while the session fills the chart.
      for (let index = visits.length; index < size; index += 1) {
        bars.push(`<div class="visit-bar empty${far(index)}"><div class="fill"></div></div>`);
      }
      const average = this._number("average");
      const line =
        average !== null
          ? `<div class="average-line" style="--height:${share(average)}" title="${escapeHtml(
              `${this._t("average_long")}: ${this._format(average, 1)}`
            )}"></div>`
          : "";
      chart.setAttribute("role", "img");
      chart.setAttribute(
        "aria-label",
        `${this._t("history")}: ${visits.map((visit) => visit.score).join(", ")}`
      );
      this._setHtml(chart, line + bars.join(""));
    }
  }

  // Status card -----------------------------------------------------------------

  class AutodartsStatusCard extends CardBase {
    static keys = STATUS_KEYS;

    static defaults = STATUS_DEFAULTS;

    static form = "status";

    getCardSize() {
      return 7;
    }

    _css() {
      return STATUS_CSS;
    }

    _watched() {
      const cameras = Object.values(CAMERA_KEYS).flatMap((key) => this._index[key] || []);
      return [...Object.values(this._ids), ...cameras];
    }

    _build() {
      const c = this._config;
      const t = (key) => escapeHtml(this._t(key));
      const connections = `
        <div class="info-tile">
          <span class="section-label">${t("connections")}</span>
          <div class="chips"></div>
        </div>`;
      const system = `
        <div class="info-tile system-tile" hidden>
          <span class="section-label">${t("system")}</span>
          <div class="metrics"></div>
          <button class="system-info muted" hidden></button>
        </div>`;
      const cameras = `
        <div class="cameras-section" hidden>
          <div class="section-label">${t("cameras")}</div>
          <div class="camera-grid"></div>
        </div>`;
      const controls = `
        <div class="controls">
          <button data-action="calibrate">${t("calibrate_all")}</button>
          <button data-action="reset">${t("reset")}</button>
          <button data-action="restart">${t("restart")}</button>
        </div>`;
      this.shadowRoot.innerHTML = `
        <style>${STATUS_CSS}</style>
        <ha-card>
          <div class="root">
            <div class="status-card">
              <header>
                <div class="title"></div>
                <div class="pill" role="status"></div>
              </header>
              <p class="manual-note muted" hidden>${t("manual_board")}</p>
              <div class="detection">
                <div>
                  <div class="name">${t("detection")}</div>
                  <div class="state"></div>
                </div>
                <button class="toggle" role="switch" aria-checked="false" aria-label="${t("detection")}"></button>
              </div>
              <div class="info">
                <div class="info-tile board-tile">
                  <span class="section-label">${t("board")}</span>
                  <span class="value version">–</span>
                  <button class="badge update-badge"></button>
                </div>
                ${c.show_connection ? connections : ""}
                ${c.show_system ? system : ""}
              </div>
              ${c.show_cameras ? cameras : ""}
              ${c.show_controls ? controls : ""}
            </div>
          </div>
        </ha-card>`;
      const root = this.shadowRoot;
      this._el = {
        title: root.querySelector(".title"),
        pill: root.querySelector(".pill"),
        manual: root.querySelector(".manual-note"),
        detection: root.querySelector(".detection"),
        info: root.querySelector(".info"),
        detectionState: root.querySelector(".detection .state"),
        toggle: root.querySelector(".toggle"),
        version: root.querySelector(".version"),
        update: root.querySelector(".update-badge"),
        chips: root.querySelector(".chips"),
        system: root.querySelector(".system-tile"),
        metrics: root.querySelector(".metrics"),
        systemInfo: root.querySelector(".system-info"),
        camerasSection: root.querySelector(".cameras-section"),
        cameras: root.querySelector(".camera-grid"),
        controls: root.querySelector(".controls"),
      };
      this._el.toggle.addEventListener("click", () => this._toggleDetection());
      this._el.update.addEventListener("click", () => this._moreInfo(this._ids.update));
      for (const list of [this._el.chips, this._el.metrics]) {
        list?.addEventListener("click", (event) => this._moreInfo(event.target.closest("[data-entity]")?.dataset.entity));
      }
      this._el.systemInfo?.addEventListener("click", () => this._moreInfo(this._ids.hostOs));
      this._el.cameras?.addEventListener("click", (event) => {
        const target = event.target.closest("[data-entity], [data-calibrate]");
        if (!target) return;
        if (target.dataset.entity) {
          this._moreInfo(target.dataset.entity);
          return;
        }
        if (this.preview) return;
        const action = `camera:${target.dataset.calibrate}`;
        if (this._confirmed(action)) this._press(target.dataset.calibrate);
        this._confirmChanged();
      });
      this._el.controls?.addEventListener("click", (event) => {
        const action = event.target.closest("button")?.dataset.action;
        if (!action || this.preview) return;
        if (this._confirmed(action)) this._press(this._ids[action]);
        this._confirmChanged();
      });
    }

    _confirmChanged() {
      if (!this._el) return;
      const [status] = this._status();
      this._updateControls(status);
      this._updateCameras(status);
    }

    _update() {
      const c = this._config;
      const el = this._el;
      const t = (key) => this._t(key);
      el.title.textContent = c.title || this._deviceName();
      const [status, statusText] = this._status();
      this.style.setProperty("--ad-status", STATUS_COLORS[status]);
      this.style.setProperty("--ad-accent", cssColor(c.accent_color, "var(--primary-color)"));
      this._showStatus(el.pill, statusText);
      // A dartboard without Autodarts has no detection, connections, board PC or cameras.
      const manual = this._manualBoard();
      el.manual.hidden = !manual;
      for (const part of [el.detection, el.info, el.controls]) if (part) part.hidden = manual;
      if (manual) return;

      const running = detectionRunning((name) => this._state(name), status);
      el.toggle.setAttribute("aria-checked", String(running));
      el.toggle.disabled = status === "offline" || !(this._ids.detection || this._ids[running ? "stop" : "start"]);
      el.detectionState.textContent = t(statusText);

      const device = this._hass.devices?.[this._deviceId];
      el.version.textContent = device?.sw_version ? `${t("version")} ${device.sw_version}` : "–";
      const update = this._state("update");
      el.update.hidden = update?.state !== "on" && update?.state !== "off";
      el.update.classList.toggle("ok", update?.state === "off");
      el.update.disabled = update?.state !== "on";
      // An update opens its details with a tap, and says so with an arrow.
      this._setHtml(
        el.update,
        update?.state === "on"
          ? `${escapeHtml(`${t("update_available")} ${update.attributes?.latest_version ?? ""}`.trim())}${cueHtml("details", true)}`
          : escapeHtml(t("up_to_date"))
      );

      this._updateChips();
      this._updateSystem();
      this._updateCameras(status);
      this._updateControls(status);
    }

    _updateChips() {
      if (!this._el.chips) return;
      const chip = (name, text) => {
        const id = this._ids[name];
        if (!id) return "";
        const cls = this._hass.states[id]?.state === "on" ? "on" : "off";
        return `<button class="chip ${cls}" data-entity="${escapeHtml(id)}" data-focus="${escapeHtml(id)}">${escapeHtml(text)}</button>`;
      };
      this._setHtml(
        this._el.chips,
        [
          chip("connected", this._t("board")),
          chip("realtime", this._t("realtime")),
          this._ids.cloudLink ? chip("cloudLink", this._t("cloud")) : chip("upstream", this._t("cloud")),
        ].join("")
      );
    }

    _updateSystem() {
      if (!this._el.system) return;
      const metric = (name, text, value) =>
        value === null
          ? ""
          : `<button class="metric" data-entity="${escapeHtml(this._ids[name])}" data-focus="${escapeHtml(name)}">` +
            `<span class="value">${escapeHtml(value)}</span>` +
            `<span class="name opens">${escapeHtml(text)}${cueHtml("details", true)}</span></button>`;
      // Percentages read as Home Assistant writes them; other units keep their symbol.
      const measured = (name, digits, unit) => {
        const number = this._number(name);
        if (number === null) return null;
        if (unit === "%") return this._percent(number, digits);
        return `${this._format(number, digits)}${unit ? ` ${unit}` : ""}`;
      };
      const markup = [
        metric("cpu", this._t("cpu"), measured("cpu", 0, "%")),
        metric("memory", this._t("memory"), measured("memory", 0, this._state("memory")?.attributes?.unit_of_measurement)),
        metric("fps", this._t("detection_fps"), measured("fps", 1, "fps")),
        metric("corrected", this._t("corrected"), measured("corrected", 1, "%")),
      ].join("");
      const text = (name) => (usable(this._state(name)) ? String(this._state(name).state) : "");
      const vision = text("vision");
      const info = [
        text("hostOs"),
        shortProcessor(text("processor")),
        vision ? `${this._t("vision_short")} ${vision}` : "",
      ].filter(Boolean);
      if (this._el.systemInfo) {
        this._el.systemInfo.hidden = !info.length;
        this._setHtml(this._el.systemInfo, `<span class="opens">${escapeHtml(info.join(" · "))}</span>${cueHtml("details", true)}`);
      }
      this._el.system.hidden = !markup && !info.length;
      const tiles = this._el.system.parentElement;
      tiles.className = `info balanced n${[...tiles.children].filter((tile) => !tile.hidden).length}`;
      this._setHtml(this._el.metrics, markup);
    }

    _updateCameras(status) {
      if (!this._el.cameras) return;
      const cameras = cameraEntities(this._hass, this._index);
      this._el.camerasSection.hidden = !cameras.length;
      const markup = cameras
        .map((camera) => {
          const problem = this._hass.states[camera.problem]?.state === "on";
          const fpsState = camera.fps ? this._hass.states[camera.fps] : undefined;
          const fps = usable(fpsState) ? `${this._format(Number(fpsState.state), 1)} fps` : "";
          const target = camera.image || camera.problem || camera.fps;
          const confirming = camera.calibrate && this._confirm === `camera:${camera.calibrate}`;
          const calibrate = camera.calibrate
            ? `<button class="action${confirming ? " confirm" : ""}" data-calibrate="${escapeHtml(camera.calibrate)}"` +
              ` data-focus="${escapeHtml(`calibrate:${camera.calibrate}`)}"${status === "offline" ? " disabled" : ""}>` +
              `${escapeHtml(this._t(confirming ? "confirm" : "calibrate"))}</button>`
            : "";
          return (
            `<div class="camera${problem ? " problem" : ""}">` +
            `<div class="camera-head"><button class="camera-name" data-entity="${escapeHtml(target || "")}"` +
            ` data-focus="${escapeHtml(`camera:${camera.number}`)}">` +
            `<span class="opens">${escapeHtml(`${this._t("camera")} ${camera.number}`)}</span>${cueHtml("details", true)}` +
            `</button><span class="dot" title="${escapeHtml(
              this._t(problem ? "camera_failure" : "camera_ok")
            )}"></span></div>` +
            `<div class="fps">${escapeHtml(problem ? this._t("camera_failure") : fps || this._t("camera_ok"))}</div>` +
            `${calibrate}</div>`
          );
        })
        .join("");
      this._el.cameras.className = `camera-grid balanced n${cameras.length}`;
      this._setHtml(this._el.cameras, markup);
    }

    _updateControls(status) {
      const controls = this._el.controls;
      if (!controls) return;
      // Beside every camera's own calibration, this one calibrates them all.
      const words = { calibrate: "calibrate_all", reset: "reset", restart: "restart" };
      for (const action of ["calibrate", "reset", "restart"]) {
        const button = controls.querySelector(`[data-action="${action}"]`);
        const confirming = this._confirm === action;
        button.textContent = this._t(confirming ? "confirm" : words[action]);
        button.classList.toggle("confirm", confirming);
        button.hidden = !this._ids[action];
        button.disabled = status === "offline";
      }
    }
  }

  // Scoreboard card -------------------------------------------------------------

  class AutodartsScoreboardCard extends PadCard {
    static keys = SCOREBOARD_KEYS;

    static defaults = SCOREBOARD_DEFAULTS;

    static form = "scoreboard";

    static avatars = true;

    getCardSize() {
      return 8;
    }

    getGridOptions() {
      return { columns: "full", min_columns: 6 };
    }

    _css() {
      return SCOREBOARD_CSS;
    }

    setConfig(config) {
      super.setConfig(overlayConfig(config));
    }

    // The overlay takes the window only outside the card editor and the edit mode.
    set preview(value) {
      super.preview = value;
      this._stage();
    }

    get preview() {
      return super.preview;
    }

    // Back on the screen counts as a look at it: the idle time starts again.
    connectedCallback() {
      if (!this._el) return;
      this._activity = Date.now();
      this._rejoin();
      this._update();
      // Home Assistant hands a view it shows again its new states within its own update.
      // When none have come a moment later (a new leave or return cancels the wait),
      // nothing changed while the card was away: the caller still knows the game and
      // calls the very next dart again.
      clearTimeout(this._rejoinTimer);
      if (this._away) this._rejoinTimer = setTimeout(() => (this._away = null));
    }

    disconnectedCallback() {
      super.disconnectedCallback();
      this._leave();
      clearTimeout(this._lobbyTimer);
      clearTimeout(this._idleTimer);
      clearTimeout(this._tournamentTimer);
      clearInterval(this._tournamentTick);
      this._tournamentTick = null;
      this._idleOff();
      this._stage();
      // The browser leaves full screen with a card that leaves the page, and tells the page.
      if (this._fullscreen) this._fullscreenChanged();
    }

    // Full screen shows the scoreboard alone on the screen, without the bars of the
    // browser and the header and sidebar of Home Assistant. The button, Escape, which the
    // browser handles, or a double tap on the scoreboard leaves it.
    _toggleFullscreen() {
      if (this.preview) return;
      // The browser may say no, for example to a page in a frame: the card stays as it is.
      const asked = this._fullscreen ? document.exitFullscreen() : this.requestFullscreen();
      asked.catch(() => {});
    }

    // The browser tells the card when it enters and leaves full screen, also when Escape or
    // a gesture of the system left it.
    _fullscreenChanged = () => {
      this._fullscreen = this.isConnected && this.getRootNode().fullscreenElement === this;
      this._showFullscreen();
      this._keepAwake();
    };

    // In full screen the scoreboard fills the screen, as at full height, without the room
    // that Home Assistant's header takes.
    _showFullscreen() {
      const el = this._el;
      const on = Boolean(this._fullscreen);
      const full = on || Boolean(this._config.full_height);
      el.board.classList.toggle("fullscreen", on);
      el.board.classList.toggle("full", full);
      // At full height the scores have a region of their own, which the keyboard reaches.
      if (full) {
        el.main.tabIndex = 0;
        el.main.setAttribute("role", "region");
        el.main.setAttribute("aria-label", this._t("view_scoreboard"));
      } else {
        for (const name of ["tabindex", "role", "aria-label"]) el.main.removeAttribute(name);
      }
      el.fullscreen.setAttribute("aria-pressed", String(on));
      el.fullscreen.firstElementChild.setAttribute("icon", on ? "mdi:fullscreen-exit" : "mdi:fullscreen");
      if (!on) {
        clearTimeout(this._awakeTimer);
        el.awake.hidden = true;
      }
    }

    // Two taps in quick succession leave full screen, unless one of them was on a control.
    _doubleTap(event) {
      const now = Date.now();
      const double = now - (this._lastTap ?? -Infinity) <= DOUBLE_TAP;
      const counts = Boolean(this._fullscreen) && !event.target.closest(FULLSCREEN_CONTROLS);
      this._lastTap = counts && !double ? now : null;
      if (counts && double) this._toggleFullscreen();
    }

    // While the scoreboard fills the screen, the screen stays on where the browser lets a
    // page hold it on: over HTTPS, as with Home Assistant Cloud, and in the Companion app.
    // The browser lets go of it while the page is hidden, so it is held again when the
    // page shows.
    _keepAwake = () => {
      const wanted = Boolean(this._fullscreen && this._config.keep_awake);
      if (wanted) document.addEventListener("visibilitychange", this._keepAwake);
      else document.removeEventListener("visibilitychange", this._keepAwake);
      if (!wanted || document.visibilityState === "hidden") {
        this._letSleep();
        return;
      }
      // Held, or asked for: a lock that the browser let go of is asked for again.
      if (this._awake && !this._awake.lock?.released) return;
      const wakeLock = window.navigator.wakeLock;
      if (typeof wakeLock?.request !== "function") {
        this._awakeHint();
        return;
      }
      const hold = { lock: null };
      this._awake = hold;
      wakeLock.request("screen").then(
        (lock) => {
          // Left full screen while the browser answered.
          if (this._awake !== hold) {
            lock.release();
            return;
          }
          hold.lock = lock;
        },
        () => {
          if (this._awake === hold) this._awake = null;
          this._awakeHint();
        }
      );
    };

    // A lock still asked for is let go of as soon as the browser gives it.
    _letSleep() {
      this._awake?.lock?.release();
      this._awake = null;
    }

    // Once, the first time the browser can't keep the screen on: how to keep it on anyway.
    _awakeHint() {
      if (this._hintedAwake || !this._fullscreen) return;
      this._hintedAwake = true;
      this._el.awake.hidden = false;
      this._awakeTimer = setTimeout(() => (this._el.awake.hidden = true), AWAKE_HINT);
    }

    // On the dashboard, the overlay of a stream takes the whole window, above Home
    // Assistant, which it hides, so that a browser source of OBS shows the overlay alone.
    // The card editor and the dashboard's edit mode show it inside the card, as does a
    // browser without popovers, which put an element above everything else.
    _stage() {
      const stage = this._el?.stage;
      const take = Boolean(stage) && this.isConnected && !this.preview && typeof stage.showPopover === "function";
      holdPage(this, take);
      if (take) window.addEventListener("keydown", this._leaveKey);
      else window.removeEventListener("keydown", this._leaveKey);
      if (!stage || take === this._taken) return;
      this._taken = take;
      stage.classList.toggle("taken", take);
      if (take) {
        stage.popover = "manual";
        stage.showPopover();
      } else {
        // A card that left the page has its popover closed already.
        if (stage.isConnected) stage.hidePopover();
        stage.removeAttribute("popover");
      }
    }

    // Escape leaves the overlay, as a double click on it does.
    _leaveKey = (event) => {
      if (event.key === "Escape") leaveOverlay();
    };

    // A connection to Home Assistant that drops is time away from the board, too.
    set hass(hass) {
      if (hass.connected === false) this._leave();
      super.hass = hass;
      this._rejoin();
    }

    // Away from the page, or from Home Assistant while the connection is down, the caller
    // hears nothing: what changed meanwhile is history, not news. It keeps the states it
    // saw last, to know the first new ones after its return.
    _leave() {
      clearTimeout(this._rejoinTimer);
      this._away ??= { states: this._hass?.states };
    }

    // Back on the page with new states, the caller follows the game from them: it calls
    // and celebrates only what changes after its return, never a visit or a match that
    // ended while it was away.
    _rejoin() {
      const hass = this._hass;
      if (!this._away || !this.isConnected || hass.connected === false || hass.states === this._away.states) return;
      this._away = null;
      clearTimeout(this._rejoinTimer);
      this._callerState = callerState(this._state("visit"), gameView((name) => this._state(name)));
      this._tournamentCall = tournamentCallState(tournamentView(this._state("tournament")));
    }

    // The four player name fields, in their order.
    _nameIds() {
      return [...(this._index?.["text.practice_player"] ?? [])].sort((a, b) =>
        a.localeCompare(b, "en", { numeric: true })
      );
    }

    // The start scores of the players, in the same order as the names.
    _startIds() {
      return [...(this._index?.["number.practice_start"] ?? [])].sort((a, b) =>
        a.localeCompare(b, "en", { numeric: true })
      );
    }

    _watched() {
      return [...super._watched(), ...this._nameIds(), ...this._startIds()];
    }

    _build() {
      const c = this._config;
      const t = (key) => escapeHtml(this._t(key));
      // The label stays; the pressed state and the speaker tell whether the caller is on.
      const caller =
        `<button class="caller-toggle" aria-pressed="false" title="${t("caller_hint")}">` +
        `<span class="caller-icon" aria-hidden="true">🔇</span><span>${t("caller")}</span></button>`;
      // An icon alone: the pressed state tells whether the scoreboard fills the screen.
      const fullscreen =
        `<button type="button" class="fullscreen-toggle" aria-pressed="false" aria-label="${t("fullscreen")}"` +
        ` title="${t("fullscreen_hint")}"${c.fullscreen_button && fullscreenOffered() ? "" : " hidden"}>` +
        `<ha-icon icon="mdi:fullscreen" aria-hidden="true"></ha-icon></button>`;
      const awake = documentation(["scoreboard.html#full-screen", "de/scoreboard.html#vollbild"]);
      // The overlay of a stream lies on a picture of its own, the stage.
      const overlay = overlayOf(c);
      this._overlay = overlay;
      const stage = overlay ? `<div class="stage" data-mode="${overlay.mode}" data-layout="${overlay.layout}">` : "";
      this.shadowRoot.innerHTML = `
        <style>${SCOREBOARD_CSS}</style>
        <ha-card${overlay ? ` class="overlay-card"` : ""}>
          <div class="root">
            ${stage}<div class="scoreboard${overlay ? " overlay" : ""}">
              <header>
                <div class="heading">
                  <div class="title"></div>
                  <div class="muted meta"></div>
                </div>
                <div class="header-actions">
                  <button type="button" class="lobby-toggle" hidden><span aria-hidden="true">＋</span><span>${t(
                    "lobby_open"
                  )}</span></button>
                  ${c.caller ? caller : ""}
                  ${c.show_status ? `<div class="pill" role="status"></div>` : ""}
                  ${fullscreen}
                </div>
                <p class="awake-hint" role="status" hidden>${t("awake_hint")}
                  <a href="${awake}" target="_blank" rel="noreferrer">${t("awake_hint_link")}</a></p>
              </header>
              <div class="banner appear" role="status" hidden></div>
              <div class="main"></div>
              ${c.show_visit ? `<div class="visit"></div>` : ""}
              <div class="pad-area appear" hidden></div>
              <div class="loupe" hidden aria-hidden="true"></div>
              <div class="celebrate" aria-hidden="true"></div>
              <div class="visually-hidden said" role="status"></div>
            </div>${overlay ? "</div>" : ""}
          </div>
        </ha-card>
      `;
      const root = this.shadowRoot;
      this._el = {
        stage: root.querySelector(".stage"),
        board: root.querySelector(".scoreboard"),
        title: root.querySelector(".title"),
        meta: root.querySelector(".meta"),
        pill: root.querySelector(".pill"),
        banner: root.querySelector(".banner"),
        main: root.querySelector(".main"),
        visit: root.querySelector(".visit"),
        caller: root.querySelector(".caller-toggle"),
        callerIcon: root.querySelector(".caller-icon"),
        lobby: root.querySelector(".lobby-toggle"),
        fullscreen: root.querySelector(".fullscreen-toggle"),
        awake: root.querySelector(".awake-hint"),
        pad: root.querySelector(".pad-area"),
        loupe: root.querySelector(".loupe"),
        celebrate: root.querySelector(".celebrate"),
        // A live region outside the markup that is replaced, so what it says is heard.
        said: root.querySelector(".said"),
      };
      this._hints = "";
      this._taken = false;
      this._el.stage?.addEventListener("dblclick", () => this._taken && leaveOverlay());
      this._initPad(this._el.visit, this._el.board);
      this._callerState = null;
      this._followed = null;
      this._el.caller?.addEventListener("click", () => this._toggleCaller());
      this._el.lobby.addEventListener("click", () => this._lobbyAction("open"));
      this._el.fullscreen.addEventListener("click", () => this._toggleFullscreen());
      this._el.board.addEventListener("click", (event) => this._doubleTap(event));
      this.addEventListener("fullscreenchange", this._fullscreenChanged);
      this._showFullscreen();
      this._el.main.addEventListener("click", (event) => {
        const target = event.target.closest("[data-lobby]");
        if (target && !target.disabled) this._lobbyAction(target.dataset.lobby, target.dataset.value);
        if (event.target.closest("[data-tournament]") && !this.preview) this._press(this._ids.tournamentNext);
      });
      this._el.main.addEventListener("input", (event) => {
        if (this._lobby && event.target.classList.contains("lobby-name")) this._lobby.draft = event.target.value;
      });
      this._el.main.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" || !event.target.classList.contains("lobby-name")) return;
        event.preventDefault();
        this._lobbyAction("add-name");
      });
      // Every tap and key at the screen ends idle mode and starts the idle time again.
      for (const kind of ["click", "keydown"]) this._el.board.addEventListener(kind, () => this._touch());
    }

    // The tap that unlocks the sound; a second tap mutes the caller again.
    _toggleCaller() {
      if (this.preview) return;
      callerAudio.unlocked = !callerAudio.unlocked;
      if (callerAudio.unlocked) {
        const Context = window.AudioContext || window.webkitAudioContext;
        if (!callerAudio.context && Context) callerAudio.context = new Context();
        callerAudio.context?.resume?.();
        // Speaking inside the tap keeps browsers from blocking later calls.
        this._speak(this._t("caller_on"));
        // Each time the caller is switched on, the pack is asked for anew, with the files
        // copied there since.
        this._voiceFor = undefined;
        this._followVoice();
      } else {
        silenceCaller();
      }
      this._showCaller();
    }

    // The voice pack the card's settings name, asked for once; until Home Assistant answers,
    // and for a pack it does not know, the browser's voice calls.
    _followVoice() {
      const pack = voicePackName(this._config.caller_voice);
      if (this._voiceFor === pack) return;
      this._voiceFor = pack;
      this._voice = null;
      const hass = this._hass;
      if (pack && typeof hass.callWS === "function" && typeof hass.fetchWithAuth === "function") {
        this._loadVoice(pack);
      }
    }

    async _loadVoice(pack) {
      let result = null;
      try {
        result = await this._hass.callWS({ type: "homedarts/voice_pack", pack });
      } catch {
        // An unknown pack leaves the calls to the browser's voice.
      }
      if (this._voiceFor === pack) this._voice = voicePack(result);
    }

    // A call in the pack's sounds where it has them, in the browser's voice where not; with a
    // pack, every call waits for the one before.
    _callOut(call) {
      const t = (key) => this._t(key);
      const words = callerText(call, t);
      const voice = this._voice;
      const context = callerAudio.context;
      if (!voice || !context) {
        this._speak(words);
        return;
      }
      const parts = callerSounds(call, (key) => voice.sounds.has(key), t) ?? [{ text: words }];
      const plan = parts.map((part) => (part.sound ? { url: soundUrl(voice.sounds.get(part.sound)) } : part));
      const hass = this._hass;
      const options = { round: callerVoice.round, lang: voiceLanguage(hass), fetch: (url) => hass.fetchWithAuth(url), context };
      callerVoice.queue = callerVoice.queue.then(() => playCall(plan, words, options));
    }

    _showCaller() {
      const button = this._el.caller;
      if (!button) return;
      button.setAttribute("aria-pressed", String(callerAudio.unlocked));
      this._el.callerIcon.textContent = callerAudio.unlocked ? "🔊" : "🔇";
    }

    // A big moment shows at once, with or without the caller; a new one starts afresh.
    _celebrate(previous, current) {
      const kind = celebrationOf(previous, current);
      if (!kind || this._config.celebrations === false || this.preview) return;
      this._moments = (this._moments ?? 0) + 1;
      this._setHtml(this._el.celebrate, celebrationHtml(kind, this._moments));
    }

    _speak(text) {
      utter(text, voiceLanguage(this._hass));
    }

    _announce(visit, view, tournament) {
      if (this._away) return;
      const current = callerState(visit, view, this._callerState);
      const previous = this._callerState;
      this._callerState = current;
      this._celebrate(previous, current);
      const followed = tournamentCallState(tournament);
      const before = this._tournamentCall;
      this._tournamentCall = followed;
      if (!this._config.caller || !callerAudio.unlocked || this.preview) return;
      this._followVoice();
      for (const call of [
        ...callerCalls(previous, current, this._config),
        ...tournamentCalls(before, followed, this._config),
      ]) {
        if (call.kind === "fanfare") playFanfare();
        else this._callOut(call);
      }
    }

    // New game screen -----------------------------------------------------------

    // The games the screen offers: none without the practice game or with the screen off.
    _lobbyGames() {
      if (this._config.lobby === false) return [];
      return lobbyGames(this._state("game")?.attributes?.options, this._config.lobby_games);
    }

    // The game, the players and the rules as the board has them now.
    _board() {
      const on = (name) => this._state(name)?.state === "on";
      return {
        game: this._state("game")?.state,
        players: this._number("players"),
        names: this._nameIds().map((id) => {
          const state = this._hass.states[id];
          return usable(state) ? String(state.state) : "";
        }),
        legs: this._number("legs"),
        sets: this._number("sets"),
        in_mode: this._state("inMode")?.state,
        out_mode: this._state("outMode")?.state,
        bull_mode: this._state("bullMode")?.state,
        max_rounds: this._number("maxRounds"),
        double_out: !this._state("doubleOut") || on("doubleOut"),
        double_in: on("doubleIn"),
        bull_off: on("bullOff"),
        bull_off_distance: on("bullOffDistance"),
        teams: on("teams"),
        three_in_a_bed: !this._state("threeInABed") || on("threeInABed"),
        starts: this._startIds().map((id) => {
          const start = Number(this._hass.states[id]?.state);
          return Number.isInteger(start) ? start : 0;
        }),
        format: this._state("tournamentFormat")?.state,
        third_place: on("tournamentThird"),
        random_draw: on("tournamentDraw"),
        groups: this._number("tournamentGroups"),
        advance: this._number("tournamentAdvance"),
        bot: this._number("botLevel"),
      };
    }

    // The tournament games the screen offers, of the games it offers at all.
    _tournamentGames() {
      const offered = new Set(this._lobbyGames().flatMap((group) => group.games));
      const games = this._state("tournamentGame")?.attributes?.options;
      return lobbyGames((Array.isArray(games) ? games : []).filter((game) => offered.has(String(game))));
    }

    // A game by the name players know; newer games by the name Home Assistant gives them.
    _gameName(game) {
      const select = this._state("game");
      return gameName(
        (key) => this._t(key),
        /^\d+$/.test(game) ? Number(game) : game,
        (option) => (this._hass.formatEntityState ? this._hass.formatEntityState(select, option) : null)
      );
    }

    _lobbyAction(action, value) {
      if (this.preview) return;
      if (action === "open") {
        this._openLobby(false);
        return;
      }
      const choice = this._lobby;
      if (!choice) return;
      if (action === "close") {
        this._lobby = null;
      } else if (action === "start") {
        // A new tournament stops the one being played, which needs a second tap.
        if (!choice.tournament || !this._tournamentRunning() || this._confirmed("start")) this._startGame(choice);
      } else if (action === "end") {
        // Ending the game needs a second tap; the screen stays for the next game.
        // A tournament ends with its game.
        if (this._confirmed("end")) {
          if (this._tournamentRunning()) this._press(this._ids.tournamentStop);
          this._call("select", "select_option", { entity_id: this._ids.game, option: "off" });
        }
      } else if (action === "mode") {
        const next = lobbyChange(choice, action, value);
        const games = (next.tournament ? this._tournamentGames() : this._lobbyGames()).flatMap((group) => group.games);
        if (!games.includes(next.game)) next.game = games.includes("501") ? "501" : games[0];
        this._lobby = next;
      } else if (action === "add-name") {
        const field = this._el.main.querySelector(".lobby-name");
        this._lobby = lobbyChange(choice, "add", field.value);
        // An added name leaves the field; one that cannot be added stays in it.
        field.value = this._lobby.draft;
      } else {
        this._lobby = lobbyChange(choice, action, value);
        this._say(this._lobbyValue(action, value));
      }
      this._update();
    }

    // What a stepper shows after its button, for a screen reader.
    _lobbyValue(action, value) {
      const choice = this._lobby;
      const index = Number(value);
      if (action === "legs" || action === "sets") return `${this._t(`lobby_${action}`)} ${choice[action]}`;
      if (action === "groups" || action === "advance") {
        const { shown, advance } = groupSetup(choice);
        return `${this._t(`tournament_${action}`)} ${action === "groups" ? shown : advance}`;
      }
      if (action === "max_rounds") return `${this._t("lobby_max_rounds")} ${choice.max_rounds || this._t("lobby_no_limit")}`;
      if (action === "lower" || action === "raise") {
        const name = choice.players[index] || `${this._t("score_player")} ${index + 1}`;
        return `${name} ${choice.starts[index] || choice.game}`;
      }
      return action === "bot" && choice.bot ? `${this._t("bot")} ${choice.bot}` : "";
    }

    _say(text) {
      if (text) this._el.said.textContent = text;
    }

    // Opened by a tap, or by itself a few seconds after a game ended.
    _openLobby(auto) {
      clearTimeout(this._lobbyTimer);
      const games = this._lobbyGames().flatMap((group) => group.games);
      // Between the matches of a tournament, its table or bracket shows instead.
      if (this.preview || !games.length || this._lobby || (auto && this._tournamentOwned)) return;
      this._lobby = { ...lobbyChoice(this._board(), games), auto };
      // The screen that opens by itself also waits the idle time before idle mode takes over.
      this._activity = Date.now();
      this._idleOff();
      this._update();
    }

    // Darts count only while the board detects them: the start switches detection on,
    // which the new game screen says beforehand.
    _startGame(choice) {
      const options = {
        entry: this._entry(),
        distance: Boolean(this._ids.bullOffDistance),
        bed: Boolean(this._ids.threeInABed),
      };
      if (this._detectionOff()) this._toggleDetection();
      if (choice.tournament) this._startTournament(tournamentStartData(choice, options));
      else this._call("homedarts", "start_game", startGameData(choice, options));
      this._lobby = null;
    }

    // The integration starts no tournament while one is played: the one being played
    // stops first, and the new one starts once the stop succeeded. A failure shows
    // Home Assistant's message, in the language of the user.
    async _startTournament(data) {
      if (this._tournamentRunning()) {
        const entry = this._entry();
        try {
          await this._hass.callService("homedarts", "stop_tournament", entry ? { config_entry_id: entry } : {});
        } catch {
          return;
        }
      }
      this._call("homedarts", "start_tournament", data);
    }

    // Detection is stopped on a board that is online.
    _detectionOff() {
      const [status] = this._status();
      return status !== "offline" && !detectionRunning((name) => this._state(name), status);
    }

    // The pad while a dart is corrected, or the keypad while darts are entered by hand.
    // The undo of the last visit is the tile beside the darts, so the keypad keeps its keys.
    _pad(view, darts) {
      const disabled = botAtBoard(view);
      const base = this._padBase(darts);
      if (this._pick) return { dart: this._pick.dart, multiplier: this._pick.multiplier, disabled, ...base };
      if (this._keypad()) {
        const confirm = this._confirm === "next" ? "next" : null;
        return this._keypadPad(view, disabled, base, { confirm });
      }
      return null;
    }

    // The last visit can be undone while the board is empty.
    _undoable(darts) {
      return this._state("practice")?.attributes?.undo === true && !darts.length;
    }

    // The tile beside the darts: the score of the visit being thrown, or, while the board
    // is empty and between games, the last visit, which a tap undoes where it can. It
    // takes the place of a button of its own, so nothing moves when the darts are pulled.
    _visitTile(view, visit, darts, undo) {
      const t = (key) => this._t(key);
      const last = recentVisits(visit?.attributes?.recent_visits, 1)[0];
      if (view.mode !== "idle" && darts.length) {
        return (
          `<div class="sum"><span class="muted">${escapeHtml(t("visit_short"))}</span>` +
          `<span class="value">${escapeHtml(usable(visit) ? visit.state : "–")}</span></div>`
        );
      }
      const score = last ? String(last.score) : "–";
      const content = (name) => `<span class="muted">${escapeHtml(t(name))}</span><span class="value">${escapeHtml(score)}</span>`;
      if (!undo) return `<div class="sum last">${content("last_short")}</div>`;
      const confirm = this._confirm === "undo";
      const spoken = confirm ? t("confirm") : `${t("undo_visit")}: ${score}`;
      return (
        `<button type="button" class="sum last tappable${confirm ? " confirm" : ""}" data-pad="undo" data-focus="undo:"` +
        ` aria-label="${escapeHtml(spoken)}">${content(confirm ? "undo_short" : "last_short")}${UNDO_CUE}</button>`
      );
    }

    // Tournament ------------------------------------------------------------------

    _tournamentRunning() {
      return ["playing", "waiting"].includes(tournamentView(this._state("tournament"))?.status);
    }

    // The tournament and what the screen shows of it: the round in the match view,
    // or, between its matches, the table or the bracket once the result has shown.
    _tournamentState(view) {
      const tournament = tournamentView(this._state("tournament"));
      this._tournamentOwned = false;
      clearTimeout(this._tournamentTimer);
      if (!tournament) return { tournament, shown: false, label: "" };
      const game = view.practice ?? view.cricket ?? view.party ?? null;
      const names = game ? game.scores.map((score) => score.name) : [];
      const over = gameState(view) !== "running";
      // A new match after the final: the tournament is over for this screen.
      if (tournament.status === "finished" && !over) this._tournamentDismissed = tournament.started;
      // When the screen saw the result of the last match; long ago at first sight.
      const result = tournament.last ? `${tournament.started}|${tournament.last.match}` : null;
      if (this._tournamentResult?.key !== result) {
        this._tournamentResult = { key: result, at: this._tournamentResult ? Date.now() : 0 };
      }
      const playing = tournament.status === "playing" && playsMatch(names, tournament.current);
      const between =
        over &&
        (tournament.status === "waiting" ||
          (tournament.status === "finished" && this._tournamentDismissed !== tournament.started));
      this._tournamentOwned = playing || between;
      // The summary time of the tournament, after which its pause begins; timed on the page only,
      // as nothing but leaving it stops the timer.
      const summary = tournament.summary * 1000;
      const wait = this._tournamentResult.at + summary - Date.now();
      if (between && wait > 0 && this.isConnected) this._tournamentTimer = setTimeout(() => this._update(), wait);
      // The match view names the round, also with the result of the match.
      const labelled = playing ? tournament.current : between && wait > 0 ? tournament.last : null;
      // The bracket animates the places filled since it last changed.
      const slots = bracketSlots(tournament);
      const signature = JSON.stringify([...slots]);
      if (this._bracket?.signature !== signature) {
        this._bracket = { signature, slots, fresh: freshSlots(this._bracket?.slots, slots) };
      }
      return {
        tournament,
        shown: between && wait <= 0,
        label: labelled ? tournamentLabel(tournament, labelled, (key) => this._t(key)) : "",
      };
    }

    _confirmChanged() {
      if (this._el && this.isConnected) this._update();
    }

    // Idle mode -----------------------------------------------------------------

    // What happened since the last update: darts, and a game that started or ended.
    _follow(visit, view, summary = null) {
      const state = gameState(view);
      const darts = visitThrows(visit);
      const signature = `${darts.map(dartKey).join(" ")}|${view.mode}|${state}`;
      const previous = this._followed;
      this._followed = { signature, state, darts: darts.length };
      if (!previous || signature !== previous.signature) {
        this._activity = Date.now();
        this._idleOff();
      }
      // Players who throw after a game do not need the screen that opened by itself.
      if (previous && darts.length > previous.darts && this._lobby?.auto) this._lobby = null;
      // The summary of a match comes first: the screen opens by itself only after it.
      const summaryEnded = Boolean(this._summaryShown && !summary);
      this._summaryShown = Boolean(summary);
      if (state === "running" || summary) {
        clearTimeout(this._lobbyTimer);
      } else if ((previous?.state === "running" || summaryEnded) && !this.preview && this.isConnected) {
        clearTimeout(this._lobbyTimer);
        this._lobbyTimer = setTimeout(() => this._openLobby(true), LOBBY_DELAY);
      }
      this._scheduleIdle(state);
    }

    _scheduleIdle(state) {
      clearTimeout(this._idleTimer);
      const c = this._config;
      if (this.preview || !c.idle || state === "running" || !this.isConnected) {
        this._idleOff();
        return;
      }
      if (this._idle) return;
      const due = this._activity + Math.max(Number(c.idle_after) || 0, 5) * 1000;
      this._idleTimer = setTimeout(() => this._idleOn(), Math.max(due - Date.now(), 0));
    }

    _idleOn() {
      if (!this._idlePanels().length) return;
      this._idle = { index: 0, since: Date.now() };
      // A new game screen opened by hand comes back with the tap that ends idle mode.
      this._resting = this._lobby && !this._lobby.auto ? this._lobby : null;
      this._lobby = null;
      clearTimeout(this._lobbyTimer);
      this._idleNext();
      this._update();
    }

    // Milliseconds each panel shows.
    _idleEvery() {
      return Math.max(Number(this._config.idle_interval) || 0, 3) * 1000;
    }

    // The screen changes only when the next panel is due or the clock's minute ends.
    _idleNext() {
      const now = Date.now();
      const panel = this._idle.since + this._idleEvery() - now;
      clearTimeout(this._idleTick);
      this._idleTick = setTimeout(() => this._idleStep(), Math.min(panel, 60000 - (now % 60000)));
    }

    _idleStep() {
      if (Date.now() - this._idle.since >= this._idleEvery()) {
        this._idle.index += 1;
        this._idle.since = Date.now();
      }
      this._idleNext();
      this._update();
    }

    _idleOff() {
      clearTimeout(this._idleTick);
      this._idleTick = null;
      this._idle = null;
    }

    // A tap or a key at the screen.
    _touch() {
      this._activity = Date.now();
      if (this._idle) {
        this._idleOff();
        this._lobby = this._resting ?? null;
        this._resting = null;
        this._update();
      } else if (this._followed) {
        this._scheduleIdle(this._followed.state);
      }
    }

    // The idle panels with something to show.
    _idlePanels() {
      const profiles = playersView(this._state("profiles"), this._state("lastMatch"));
      const data = {
        tournament: tournamentView(this._state("tournament")),
        players: profiles.players,
        match: profiles.matches[0] ?? null,
        records: bestsView(this._state("bests"), this._state("streak")),
        stats: this._stats(),
        now: new Date(),
      };
      const ui = { ...this._ui(), clock: (moment) => formatClock(this._hass, moment) };
      return idlePanels(this._config.idle_panels, data, ui);
    }

    // The visit and the training session between games.
    _stats() {
      const visit = this._state("visit");
      return {
        visit: usable(visit) ? visit.state : null,
        darts: this._number("darts"),
        average: this._number("average"),
        highest: this._number("highest"),
        max: this._number("max"),
        streak: this._number("streak"),
        today: this._number("today"),
        goal: Number(this._state("today")?.attributes?.goal) || 0,
      };
    }

    // Rendering -----------------------------------------------------------------

    _update() {
      const c = this._config;
      const el = this._el;
      const t = (key) => this._t(key);
      const overlay = this._overlay;
      this._stage();
      this._showCaller();
      const [status, statusText] = this._status();
      this.style.setProperty("--ad-status", STATUS_COLORS[status]);
      this.style.setProperty("--ad-accent", cssColor(c.accent_color, "var(--primary-color)"));
      if (overlay) this.style.setProperty("--ad-key", overlay.key);
      if (el.pill) this._showStatus(el.pill, statusText);

      const visit = this._state("visit");
      const view = gameView((name) => this._state(name));
      const ui = { ...this._ui(), name: this._deviceName(), stats: this._stats() };
      const summary = this._matchSummary(view);
      const board = scoreboardHtml({ ...view, summary }, ui);
      const tournament = this._tournamentState(view);
      this._announce(visit, view, tournament.tournament);
      this._follow(visit, view, summary);
      const games = this._lobbyGames();
      if (!games.length) this._lobby = null;
      const panels = this._idle ? this._idlePanels() : [];
      const panel = panels.length ? panels[this._idle.index % panels.length] : null;
      let { title, meta, banner, main } = board;
      // Between games the overlay leaves the picture to the stream; only the whole picture
      // has room for the table or the bracket of a tournament.
      const between = tournament.shown && (!overlay || overlay.layout === "full");
      const quiet = Boolean(overlay) && view.mode === "idle" && !between;
      if (quiet) ({ title, meta, banner, main } = { title: "", meta: "", banner: "", main: "" });
      let hints = "";
      if (this._lobby) {
        const choice = this._lobby;
        const lobbyUi = {
          ...ui,
          games,
          tournamentGames: this._tournamentGames(),
          tournamentRunning: this._tournamentRunning(),
          name: (game) => this._gameName(game),
          suggestions: lobbySuggestions(this._state("profiles"), this._board().names, ui.links, choice.players),
          distance: Boolean(this._ids.bullOffDistance),
          teams: Boolean(this._ids.teams),
          bed: Boolean(this._ids.threeInABed),
          running: ![undefined, "off", "unknown", "unavailable"].includes(this._state("game")?.state),
          confirmEnd: this._confirm === "end",
          confirmStart: this._confirm === "start",
          detectionOff: this._detectionOff(),
        };
        title = t("lobby_title");
        meta = "";
        main = lobbyHtml(choice, lobbyUi);
        hints = lobbyHints(choice, lobbyUi).join(" ");
      } else if (panel) {
        title = ui.name;
        meta = t(`idle_panel_${panel.panel}`);
        banner = "";
        main =
          `<div class="idle-panel" data-panel="${panel.panel}">${panel.html}</div>` +
          `<div class="idle-back muted">${escapeHtml(t("idle_back"))}</div>`;
      } else if (between) {
        ({ title, meta, banner, main } = tournamentHtml(tournament.tournament, {
          ...ui,
          fresh: this._bracket.fresh,
          startNow: Boolean(this._ids.tournamentNext) && !this.preview,
        }));
      } else if (tournament.label) {
        meta = [tournament.label, meta].filter(Boolean).join(" · ");
      } else if (view.mode === "idle" && games.length) {
        main += `<button type="button" class="lobby-cta" data-lobby="open">${escapeHtml(t("lobby_open"))}</button>`;
      }
      // Between games the big button opens the new game screen; the header needs none.
      el.lobby.hidden = !games.length || Boolean(this._lobby) || main.includes('class="lobby-cta"');
      el.board.classList.toggle("choosing", Boolean(this._lobby));
      el.board.classList.toggle("idling", Boolean(panel));
      el.board.classList.toggle("quiet", quiet);
      this._text(el.title, title);
      this._text(el.meta, meta);
      el.banner.hidden = !banner;
      this._text(el.banner, banner);
      el.banner.classList.toggle("rethrow", board.bannerKind === "rethrow");
      // The same idle panel with a new minute or number keeps its element, so it does not fade in again.
      const shown = el.main.firstElementChild;
      if (panel && shown?.dataset.panel === panel.panel) {
        this._setHtml(shown, panel.html);
        el.main._adHtml = main;
      } else {
        this._setHtml(el.main, main);
      }
      // The hints of the new game screen are read out when they change; what is typed stays.
      if (hints !== this._hints) this._say(hints);
      this._hints = hints;
      const field = this._lobby ? el.main.querySelector(".lobby-name") : null;
      if (field && field !== this.shadowRoot.activeElement) field.value = this._lobby.draft;
      // The countdown to the next match changes every second, the rest stays; on the page only,
      // because nothing but leaving it stops the countdown.
      const counting = this.isConnected && between && !this._lobby && !panel && tournament.tournament.status === "waiting";
      const countdown = el.main.querySelector(".countdown");
      if (countdown) countdown.textContent = tournamentCountdown(tournament.tournament, Date.now(), t);
      if (counting !== Boolean(this._tournamentTick)) {
        clearInterval(this._tournamentTick);
        this._tournamentTick = counting ? setInterval(() => this._update(), 1000) : null;
      }
      // The new game screen, the idle panels, the match summary and the tournament need the room of the
      // visit; an overlay between games shows none.
      const away = Boolean(this._lobby || panel || summary || between || quiet);
      const darts = visitThrows(visit).slice(-3);
      // Darts of the current visit correct with a tap; the bot's darts do not.
      const tappable = c.corrections && !this.preview && !away;
      const pad = this.preview || away ? null : this._pad(view, darts);
      el.pad.hidden = !pad;
      el.board.classList.toggle("with-pad", Boolean(pad));
      if (!this._keepPad(pad)) this._setHtml(el.pad, pad ? padHtml(pad, { t }) : "");
      if (!el.visit) return;
      el.visit.hidden = away;
      const undo = Boolean(c.corrections && !this.preview && !away && this._undoable(darts));
      // A dart that counted nothing in a Cricket game is struck through.
      const dead = deadDarts(view, darts);
      // On a dartboard without Autodarts every dart is entered by hand; only corrections stand out.
      const marked = this._manualBoard() ? ["corrected", "bot"] : ["manual", "corrected", "bot"];
      const slots = [0, 1, 2].map((index) => {
        const dart = darts[index];
        if (!dart) return `<div class="dart empty"><span class="segment">–</span><span class="points"></span></div>`;
        const flags = marked.filter((flag) => dart[flag] === true);
        const picked = Boolean(this._pick) && this._pick.dart === dart.dart;
        const style = ["dart", ...flags, ...(picked ? ["picked"] : []), ...(dead[index] ? ["dead"] : [])].join(" ");
        const bed = label(this._hass, dart);
        const points = dart.number * dart.multiplier;
        // The space keeps the bed and the points apart for screen readers.
        const content = `<span class="segment">${escapeHtml(bed)}</span> <span class="points">${points}</span>`;
        const nothing = dead[index] ? t("cricket_dead") : "";
        const title = nothing ? ` title="${escapeHtml(nothing)}"` : "";
        // The label names the dart and what a tap does: "T20 60 – Correct dart 1".
        const spoken = [`${bed} ${points}`, nothing, fill(t("correct_title"), { dart: dart.dart })];
        return tappable && Number.isInteger(dart.dart) && !dart.bot
          ? `<button type="button" class="${style} tappable" data-dart="${dart.dart}" data-focus="dart-${dart.dart}"` +
              `${title} aria-label="${escapeHtml(spoken.filter(Boolean).join(" – "))}">` +
              `${content}${EDIT_ICON}</button>`
          : `<div class="${style}"${title}>${content}</div>`;
      });
      this._setHtml(el.visit, slots.join("") + this._visitTile(view, visit, darts, undo));
    }
  }

  // Players card ----------------------------------------------------------------

  class AutodartsPlayersCard extends CardBase {
    static keys = PLAYERS_KEYS;

    static defaults = PLAYERS_DEFAULTS;

    static form = "players";

    static avatars = true;

    getCardSize() {
      return 6;
    }

    _css() {
      return PLAYERS_CSS;
    }

    _build() {
      const c = this._config;
      const t = (key) => escapeHtml(this._t(key));
      const section = (name, title) =>
        `<div class="${name}-section" hidden><div class="section-label">${t(title)}</div><div class="${name}"></div></div>`;
      this.shadowRoot.innerHTML = `
        <style>${PLAYERS_CSS}${PROGRESS_CSS}</style>
        <ha-card>
          <div class="root">
            <div class="players-card">
              <header>
                <div class="title"></div>
                <div class="muted count"></div>
                ${
                  // The export is an action for administrators; others would only get an error.
                  c.export && this._admin()
                    ? `<button class="action export">${t("export_button")}</button>`
                    : ""
                }
              </header>
              <div class="message empty" hidden>${t("no_profiles")}</div>
              <div class="profiles"></div>
              ${
                // Renaming, merging and deleting a profile are actions for administrators, too.
                this._admin()
                  ? `<dialog class="manage-dialog" aria-labelledby="manage-title"><form class="manage-form">` +
                    `<h2 id="manage-title"></h2><div class="manage-body"></div>` +
                    `<p class="manage-error" role="alert" hidden></p><div class="controls">` +
                    `<button type="button" class="action manage-cancel">${t("manage_cancel")}</button>` +
                    `<button type="submit" class="action primary manage-confirm"></button></div></form></dialog>`
                  : ""
              }
              ${c.show_head_to_head ? section("h2h", "head_to_head") : ""}
              ${c.show_matches ? section("matches", "recent_matches") : ""}
              ${this._progressHtml(t)}
            </div>
          </div>
        </ha-card>
      `;
      const root = this.shadowRoot;
      this._el = {
        title: root.querySelector(".title"),
        count: root.querySelector(".count"),
        empty: root.querySelector(".empty"),
        profiles: root.querySelector(".profiles"),
        h2hSection: root.querySelector(".h2h-section"),
        h2h: root.querySelector(".h2h"),
        matchesSection: root.querySelector(".matches-section"),
        matches: root.querySelector(".matches"),
        export: root.querySelector(".export"),
        dialog: root.querySelector(".manage-dialog"),
      };
      this._el.export?.addEventListener("click", () => this._export());
      this._menu = null;
      if (this._el.dialog) this._buildManage();
      // The players whose badge gallery shows all its badges.
      this._openBadges = new Set();
      root.querySelector(".badges-list")?.addEventListener("click", (event) => {
        const name = event.target.closest("[data-badges]")?.dataset.badges;
        if (name === undefined) return;
        if (!this._openBadges.delete(name)) this._openBadges.add(name);
        this._updateProgress();
      });
    }

    _admin() {
      return this._hass.user?.is_admin === true;
    }

    // The board's config entry, for the actions, which need it with several boards.
    _entry() {
      const device = this._hass.devices?.[this._deviceId];
      const entry = device?.primary_config_entry || device?.config_entries?.[0];
      return entry ? { config_entry_id: entry } : {};
    }

    // The menu of a profile and the dialog that asks before its action.
    _buildManage() {
      const { profiles, dialog } = this._el;
      profiles.addEventListener("click", (event) => {
        const button = event.target.closest("[data-manage], [data-action]");
        if (button?.dataset.manage !== undefined) this._toggleMenu(button.dataset.manage);
        else if (button) this._openManage(button.dataset.action);
      });
      profiles.addEventListener("keydown", (event) => this._menuKey(event));
      // A tap or a click anywhere else closes the menu.
      this.shadowRoot.addEventListener("pointerdown", (event) => {
        if (this._menu !== null && !event.target.closest(".manage-menu, [data-manage]")) this._toggleMenu(null);
      });
      dialog.querySelector(".manage-cancel").addEventListener("click", () => dialog.close());
      dialog.querySelector(".manage-form").addEventListener("submit", (event) => {
        event.preventDefault();
        this._confirmManage();
      });
      dialog.addEventListener("input", () => this._renameHint());
      // The keyboard comes back to the menu button of the player, also of a new name once
      // the profiles show it.
      dialog.addEventListener("close", () => {
        const active = this.shadowRoot.activeElement;
        if (dialog.contains(active)) active.blur();
        this._focusLater = this._returnTo;
        this._returnTo = null;
        this._focusMenuButton();
      });
    }

    // Opens the menu of a profile, or closes the one that is open with null or the same name.
    _toggleMenu(name, focus = "first") {
      if (this.preview) return;
      const before = this._menu;
      this._menu = name === before ? null : name;
      this._update();
      if (this._menu === null) {
        withFocus(this._el.profiles, `manage:${before}`).focus();
        return;
      }
      const items = this._menuItems();
      items[focus === "last" ? items.length - 1 : 0].focus();
    }

    _focusMenuButton() {
      const button = this._focusLater && withFocus(this._el.profiles, `manage:${this._focusLater}`);
      if (!button) return;
      this._focusLater = null;
      button.focus();
    }

    _menuItems() {
      return [...this._el.profiles.querySelectorAll(".manage-menu [role=menuitem]")];
    }

    // The keys of a menu button: the arrows open the menu, and in the menu they move from
    // action to action; Escape closes it, and so does Tab, which goes on.
    _menuKey(event) {
      const name = event.target.dataset.manage;
      if (name !== undefined) {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault();
          if (this._menu !== name) this._toggleMenu(name, event.key === "ArrowUp" ? "last" : "first");
        }
        return;
      }
      if (!event.target.closest(".manage-menu")) return;
      const items = this._menuItems();
      const index = items.indexOf(event.target);
      const moves = { ArrowDown: index + 1, ArrowUp: index - 1, Home: 0, End: items.length - 1 };
      if (event.key in moves) {
        event.preventDefault();
        items[(moves[event.key] + items.length) % items.length].focus();
      } else if (event.key === "Escape") {
        event.preventDefault();
        this._toggleMenu(null);
      } else if (event.key === "Tab") {
        // The menu button keeps the place, and Tab goes on from there.
        this._toggleMenu(null);
      }
    }

    // The dialog of an action of the open menu: what it does, and the new name or the
    // player to merge into.
    _openManage(action) {
      const name = this._menu;
      const { dialog } = this._el;
      const text = (key, values = {}) => escapeHtml(fill(this._t(key), { name, ...values }));
      this._menu = null;
      this._update();
      this._managing = { action, name };
      this._returnTo = name;
      const others = playersView(this._state("profiles"), null)
        .players.map((player) => player.name)
        .filter((other) => nameKey(other) !== nameKey(name));
      const body = {
        rename:
          `<label class="manage-field">${text("rename_label")}<input class="manage-input" type="text"` +
          ` maxlength="${LOBBY_LIMITS.name}" autocomplete="off" required value="${escapeHtml(name)}"></label>` +
          `<p class="muted manage-hint" aria-live="polite">${text("rename_hint")}</p>`,
        merge:
          `<label class="manage-field">${text("merge_label")}<select class="manage-input">` +
          others.map((other) => `<option>${escapeHtml(other)}</option>`).join("") +
          `</select></label><p>${text("merge_hint")}</p>`,
        delete: `<p>${text("delete_hint")}</p>`,
      }[action];
      dialog.querySelector("h2").textContent = fill(this._t(MANAGE_ACTIONS[action].title), { name });
      dialog.querySelector(".manage-body").innerHTML = body;
      const confirm = dialog.querySelector(".manage-confirm");
      confirm.textContent = this._t(MANAGE_ACTIONS[action].button);
      // What cannot be undone is red, as the second tap of a button that asks first.
      confirm.classList.toggle("confirm", action !== "rename");
      confirm.disabled = false;
      dialog.querySelector(".manage-error").hidden = true;
      dialog.showModal();
      (dialog.querySelector(".manage-input") || dialog.querySelector(".manage-cancel")).focus();
    }

    // Under the new name, whether it is another player's, whose profile it then joins.
    _renameHint() {
      const { action, name } = this._managing;
      if (action !== "rename") return;
      const hint = this._el.dialog.querySelector(".manage-hint");
      const typed = nameKey(this._el.dialog.querySelector(".manage-input").value);
      const other = playersView(this._state("profiles"), null).players.find(
        (player) => nameKey(player.name) === typed && typed !== nameKey(name)
      );
      hint.textContent = other ? fill(this._t("rename_merges"), { other: other.name }) : this._t("rename_hint");
    }

    // The action the dialog asked for; its error stays in the dialog, in the words of the integration.
    async _confirmManage() {
      const { action, name } = this._managing;
      const { dialog } = this._el;
      const value = dialog.querySelector(".manage-input")?.value.trim();
      const confirm = dialog.querySelector(".manage-confirm");
      const error = dialog.querySelector(".manage-error");
      if (confirm.disabled || (action !== "delete" && !value)) return;
      const [service, data] =
        action === "delete" ? ["delete_player", { name }] : ["rename_player", { player: name, new_name: value }];
      confirm.disabled = true;
      try {
        await this._hass.callWS({
          type: "call_service",
          domain: "homedarts",
          service,
          service_data: { ...data, ...this._entry() },
        });
        this._returnTo = action === "delete" ? null : value;
        dialog.close();
      } catch (failure) {
        error.textContent = failure?.message || this._t("manage_failed");
        error.hidden = false;
        confirm.disabled = false;
      }
    }

    // The action writes the file; it downloads through Home Assistant with the
    // user's login, also while Home Assistant does not serve the www folder.
    async _export() {
      const button = this._el.export;
      if (this.preview || button.disabled) return;
      button.disabled = true;
      button.textContent = this._t("exporting");
      try {
        const result = await this._hass.callWS({
          type: "call_service",
          domain: "homedarts",
          service: "export",
          service_data: {
            format: this._config.export_format === "json" ? "json" : "csv",
            what: "all",
            ...this._entry(),
          },
          return_response: true,
        });
        const download = result?.response?.download;
        if (typeof download !== "string" || !download.startsWith(EXPORT_DOWNLOADS)) {
          throw new Error(result?.response?.path || "");
        }
        const signed = await this._hass.callWS({ type: "auth/sign_path", path: download, expires: 60 });
        const link = document.createElement("a");
        link.href = signed.path;
        link.download = download.slice(EXPORT_DOWNLOADS.length);
        this.shadowRoot.append(link);
        link.click();
        link.remove();
      } catch (error) {
        const detail = error?.message ? `: ${error.message}` : "";
        this.dispatchEvent(
          new CustomEvent("hass-notification", {
            bubbles: true,
            composed: true,
            detail: { message: `${this._t("export_failed")}${detail}` },
          })
        );
      } finally {
        button.disabled = false;
        button.textContent = this._t("export_button");
      }
    }

    _update() {
      const c = this._config;
      const el = this._el;
      this.style.setProperty("--ad-accent", cssColor(c.accent_color, "var(--primary-color)"));
      el.title.textContent = c.title || this._t("players_title");
      const view = playersView(this._state("profiles"), this._state("lastMatch"));
      el.count.textContent = view.players.length ? String(view.players.length) : "";
      el.empty.hidden = view.players.length > 0;
      // A menu stays open only while its profile is there.
      if (!view.players.some((player) => player.name === this._menu)) this._menu = null;
      const html = playersHtml(view, { ...this._ui(), manage: Boolean(this._el.dialog), menu: this._menu });
      el.profiles.className = `profiles balanced n${view.players.length}`;
      this._setHtml(el.profiles, html.players);
      // Unless the keyboard went on meanwhile.
      if (!this.shadowRoot.activeElement) this._focusMenuButton();
      if (el.h2hSection) {
        el.h2hSection.hidden = !view.headToHead.length;
        this._setHtml(el.h2h, html.headToHead);
      }
      if (el.matchesSection) {
        el.matchesSection.hidden = !view.matches.length;
        this._setHtml(el.matches, html.matches);
      }
      this._updateProgress();
    }

    // Badges, trends and groupings, each in a section of its own.
    _progressHtml(t) {
      const c = this._config;
      const section = (name, title, extra = "") =>
        `<div class="${name}-section" hidden><div class="section-head"><div class="section-label">${t(title)}</div>` +
        `<span class="muted ${name}-meta"></span></div><div class="${name}-list"></div>${extra}</div>`;
      return [
        c.show_badges ? section("badges", "badges") : "",
        c.show_trends ? section("trends", "trends") : "",
        c.show_spread ? section("groups", "spread", `<p class="muted">${t("spread_hint")}</p>`) : "",
      ].join("");
    }

    // Below a player's badges, a link to all of them, or back to the earned ones and the
    // next goals; none where all of them show anyway.
    _moreBadgesHtml(player) {
      if (!this._config.show_locked || shownBadges(player, true, false).length === player.badges.length) return "";
      const open = this._openBadges.has(player.name);
      const words = open ? this._t("badges_fewer") : fill(this._t("badges_all"), { count: this._format(player.badges.length) });
      return (
        `<button type="button" class="link more-badges" data-badges="${escapeHtml(player.name)}"` +
        ` data-focus="${escapeHtml(`badges:${player.name}`)}" aria-expanded="${open}">` +
        `${escapeHtml(words)}${cueHtml("expand", true)}</button>`
      );
    }

    _updateProgress() {
      const c = this._config;
      const root = this.shadowRoot;
      const ui = this._ui();
      const badges = root.querySelector(".badges-section");
      if (badges) {
        const players = badgesView(this._state("achievements")).players.filter(
          (player) => c.show_locked || player.unlocked
        );
        badges.hidden = !players.length;
        const count = (player) =>
          player.unlocked === 1 ? this._t("badge_count_one") : fill(this._t("badge_count"), { count: this._format(player.unlocked) });
        this._setHtml(
          badges.querySelector(".badges-list"),
          players
            .map(
              (player) =>
                `<div class="badge-player"><div class="badge-owner"><b>${escapeHtml(player.name)}</b>` +
                `<span class="muted">${escapeHtml(count(player))}</span></div>` +
                `<div class="badge-list">${badgesHtml(player, ui, c.show_locked, this._openBadges.has(player.name))}</div>` +
                this._moreBadgesHtml(player) +
                `</div>`
            )
            .join("")
        );
      }
      const weeks = Math.min(12, Math.max(4, Math.round(Number(c.trend_weeks)) || PLAYERS_DEFAULTS.trend_weeks));
      const progress = progressView(this._state("profiles"), weeks);
      const trends = root.querySelector(".trends-section");
      if (trends) {
        const active = progress.filter((player) => player.active);
        trends.hidden = !active.length;
        trends.querySelector(".trends-meta").textContent = fill(this._t("trends_range"), { weeks });
        this._setHtml(trends.querySelector(".trends-list"), trendsHtml(active, ui));
      }
      const groups = root.querySelector(".groups-section");
      if (groups) {
        const grouped = progress.filter((player) => player.groups.length);
        groups.hidden = !grouped.length;
        this._setHtml(
          groups.querySelector(".groups-list"),
          grouped
            .map(
              (player) =>
                `<div class="group-player"><div class="trend-name">${escapeHtml(player.name)}</div>` +
                `<div class="groups">${spreadHtml(player.groups, ui)}</div></div>`
            )
            .join("")
        );
      }
    }
  }

  // Leaderboard card --------------------------------------------------------------

  class AutodartsLeaderboardCard extends CardBase {
    static keys = LEADERBOARD_KEYS;

    static defaults = LEADERBOARD_DEFAULTS;

    static form = "leaderboard";

    constructor() {
      super();
      // The period switched in the card, until the configuration changes.
      this._chosen = null;
    }

    setConfig(config) {
      this._chosen = null;
      super.setConfig(config);
    }

    getCardSize() {
      return 5;
    }

    _css() {
      return LEADERBOARD_CSS;
    }

    _period() {
      const period = this._chosen ?? this._config.period;
      return PERIODS.includes(period) ? period : "all";
    }

    _build() {
      const t = (key) => escapeHtml(this._t(key));
      const periods = this._config.show_period
        ? `<div class="segmented periods" role="group" aria-label="${t("period")}">${PERIODS.map(
            (period) => `<button type="button" data-period="${period}" aria-pressed="false">${t(`period_${period}`)}</button>`
          ).join("")}</div>`
        : "";
      this.shadowRoot.innerHTML = `
        <style>${LEADERBOARD_CSS}</style>
        <ha-card>
          <div class="root">
            <div class="leaderboard">
              <header><div class="title"></div>${periods}</header>
              <div class="message empty" hidden>${t("leaderboard_empty")}</div>
              <div class="records"></div>
            </div>
          </div>
        </ha-card>
      `;
      const root = this.shadowRoot;
      this._el = {
        title: root.querySelector(".title"),
        empty: root.querySelector(".empty"),
        records: root.querySelector(".records"),
        periods: root.querySelector(".periods"),
      };
      this._el.periods?.addEventListener("click", (event) => {
        const button = event.target.closest?.("button[data-period]");
        if (!button) return;
        this._chosen = button.dataset.period;
        this._update();
      });
    }

    _update() {
      const c = this._config;
      const el = this._el;
      this.style.setProperty("--ad-accent", cssColor(c.accent_color, "var(--primary-color)"));
      el.title.textContent = c.title || this._t("leaderboard");
      const period = this._period();
      for (const button of el.periods?.querySelectorAll("button") ?? []) {
        button.setAttribute("aria-pressed", String(button.dataset.period === period));
      }
      const view = leaderboardRecords(this._state("profiles"), this._state("achievements"), period);
      el.empty.hidden = view.records.length > 0;
      const limit = Math.min(5, Math.max(1, Math.round(Number(c.limit)) || LEADERBOARD_DEFAULTS.limit));
      this._setHtml(el.records, leaderboardRecordsHtml(view, this._ui(), limit));
    }
  }

  // Doubles card ----------------------------------------------------------------

  class AutodartsDoublesCard extends CardBase {
    static keys = DOUBLES_KEYS;

    static defaults = DOUBLES_DEFAULTS;

    static form = "doubles";

    getCardSize() {
      return 6;
    }

    _css() {
      return DOUBLES_CSS;
    }

    _build() {
      const t = (key) => escapeHtml(this._t(key));
      this.shadowRoot.innerHTML = `
        <style>${DOUBLES_CSS}</style>
        <ha-card>
          <div class="root">
            <div class="doubles-card">
              <header>
                <div class="title"></div>
                <div class="muted meta"></div>
              </header>
              <div class="message empty" hidden></div>
              <div class="doubles-body">
                <div class="doubles-board">
                  <svg viewBox="-230 -230 460 460" role="img">
                    <g class="face">${boardSvg("muted")}</g>
                    <g class="ring"></g>
                    <g class="numbers">${numbersSvg("muted")}</g>
                  </svg>
                </div>
                <div>
                  <div class="double-list"></div>
                  <p class="muted">${t("doubles_legend")}</p>
                  <p class="muted">${t("doubles_routes")}</p>
                </div>
              </div>
            </div>
          </div>
        </ha-card>
      `;
      const root = this.shadowRoot;
      this._el = {
        title: root.querySelector(".title"),
        meta: root.querySelector(".meta"),
        empty: root.querySelector(".empty"),
        body: root.querySelector(".doubles-body"),
        ring: root.querySelector(".ring"),
        list: root.querySelector(".double-list"),
        svg: root.querySelector("svg"),
      };
    }

    _update() {
      const c = this._config;
      const el = this._el;
      const t = (key) => this._t(key);
      this.style.setProperty("--ad-accent", cssColor(c.accent_color, "var(--primary-color)"));
      const view = doublesView(this._state("doubles"), this._state("profiles"), c.player);
      el.title.textContent = c.title || [t("doubles_title"), view.player].filter(Boolean).join(" · ");
      el.meta.textContent = [
        view.landed ? `${this._format(view.landed)} ${t("doubles_hit")}` : null,
        view.attempts
          ? `${this._format(view.attempts)} ${t("doubles_darts")}` +
            (view.rate === null ? "" : ` · ${this._percent(view.rate, 1)}`)
          : null,
      ]
        .filter(Boolean)
        .join(" · ");
      el.empty.hidden = view.doubles.length > 0;
      // A name without a profile is most likely mistyped, which the card says.
      el.empty.textContent = view.known ? t("doubles_empty") : fill(t("doubles_unknown_player"), { player: view.player });
      el.body.hidden = view.doubles.length === 0;
      el.svg.setAttribute("aria-label", t("doubles_title"));
      const html = doublesHtml(view, this._ui());
      this._setHtml(el.ring, html.ring);
      this._setHtml(el.list, html.list);
    }
  }

  // Dashboard strategy -----------------------------------------------------------

  // The editor of the dashboard strategy: the board, the title and the scoreboard view.
  class AutodartsStrategyEditor extends Base {
    setConfig(config) {
      this._config = { ...config };
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    connectedCallback() {
      if (customElements.get("ha-form")) this._render();
      else customElements.whenDefined("ha-form").then(() => this._render());
    }

    _render() {
      if (!this._hass || !this._config || !customElements.get("ha-form")) return;
      if (!this._form) {
        const form = document.createElement("ha-form");
        form.schema = strategyForm(this._hass);
        form.computeLabel = (field) => (field.name ? translate(this._hass, STRATEGY_LABELS[field.name] ?? field.name) : undefined);
        form.computeHelper = (field) =>
          STRATEGY_HELPERS[field.name] ? translate(this._hass, STRATEGY_HELPERS[field.name]) : undefined;
        form.addEventListener("value-changed", (event) => {
          event.stopPropagation();
          const config = { ...event.detail.value };
          for (const key of ["device_id", "title"]) if (!config[key]) delete config[key];
          // Scoreboard options left empty follow the card's defaults.
          const scoreboard = scoreboardOptions(config);
          if (Object.keys(scoreboard).length) config.scoreboard = scoreboard;
          else delete config.scoreboard;
          const overlay = overlayOptions(config);
          if (Object.keys(overlay).length) config.overlay_view = overlay;
          else delete config.overlay_view;
          this._config = config;
          this.dispatchEvent(new CustomEvent("config-changed", { bubbles: true, composed: true, detail: { config } }));
        });
        this.appendChild(form);
        this._form = form;
      }
      this._form.hass = this._hass;
      this._form.data = this._config;
    }
  }

  class AutodartsDashboardStrategy extends Base {
    static async generate(config, hass) {
      return dashboardStrategy(hass, config);
    }

    static async getConfigElement() {
      await loadForm();
      return document.createElement(STRATEGY_EDITOR_TYPE);
    }
  }

  return {
    [STRATEGY_ELEMENT]: AutodartsDashboardStrategy,
    [STRATEGY_EDITOR_TYPE]: AutodartsStrategyEditor,
    [CARD_TYPE]: AutodartsCard,
    [TRAINING_TYPE]: AutodartsTrainingCard,
    [STATUS_TYPE]: AutodartsStatusCard,
    [SCOREBOARD_TYPE]: AutodartsScoreboardCard,
    [PLAYERS_TYPE]: AutodartsPlayersCard,
    [DOUBLES_TYPE]: AutodartsDoublesCard,
    [LEADERBOARD_TYPE]: AutodartsLeaderboardCard,
  };
}

// Registration ------------------------------------------------------------------

// Card picker entries with their documentation in both languages.
const CARDS = [
  { type: CARD_TYPE, key: "live", docs: ["cards.html#live-card", "de/cards.html#live-karte"] },
  { type: TRAINING_TYPE, key: "training", docs: ["cards.html#training-card", "de/cards.html#trainingskarte"] },
  { type: STATUS_TYPE, key: "status", docs: ["cards.html#board-status-card", "de/cards.html#board-status"] },
  { type: SCOREBOARD_TYPE, key: "scoreboard", docs: ["cards.html#scoreboard-card", "de/cards.html#anzeigetafel"] },
  { type: PLAYERS_TYPE, key: "players", docs: ["cards.html#players-card", "de/cards.html#spielerkarte"] },
  { type: DOUBLES_TYPE, key: "doubles", docs: ["cards.html#doubles-card", "de/cards.html#doubles-karte"] },
  { type: LEADERBOARD_TYPE, key: "leaderboard", docs: ["cards.html#leaderboard-card", "de/cards.html#bestenliste"] },
];
const STRATEGY_DOCS = ["cards.html#automatic-dashboard", "de/cards.html#automatisches-dashboard"];

const documentation = ([en, de]) => `${DOCUMENTATION}/${pageLanguage() === "de" ? de : en}`;

// Home Assistant reads the entries when it opens its card picker, so the
// getters answer in the language of that moment.
const pickerEntry = ({ type, key, docs }) => ({
  type,
  preview: true,
  get name() {
    return pageText(`picker_${key}`);
  },
  get description() {
    return pageText(`picker_${key}_description`);
  },
  get documentationURL() {
    return documentation(docs);
  },
});

function register() {
  const registry = window.customElements;
  for (const [type, element] of Object.entries(createElements(window.HTMLElement))) {
    if (!registry.get(type)) registry.define(type, element);
  }
  window.customCards = window.customCards || [];
  for (const card of CARDS) {
    if (!window.customCards.some((known) => known.type === card.type)) window.customCards.push(pickerEntry(card));
  }
  // Offered in the "Add dashboard" dialog of Home Assistant.
  window.customStrategies = window.customStrategies || [];
  if (!window.customStrategies.some((known) => known.type === STRATEGY_TYPE)) {
    window.customStrategies.push({
      type: STRATEGY_TYPE,
      strategyType: "dashboard",
      name: "HomeDarts",
      get description() {
        return pageText("picker_strategy_description");
      },
      get documentationURL() {
        return documentation(STRATEGY_DOCS);
      },
    });
  }
}

// The app element of Home Assistant, and hc-main of the receiver of Home Assistant Cast,
// which shows dashboards on a TV and loads this module as a dashboard resource.
const APP_ELEMENTS = ["home-assistant", "hc-main"];

// Home Assistant loads this module in parallel with its own app, which then swaps in
// a scoped custom element registry. Elements defined before that swap stay invisible
// to dashboards, so the cards wait for the app element; other hosts get them after a timeout.
async function frontendReady(timeout = 30000) {
  const registry = window.customElements;
  if (APP_ELEMENTS.some((name) => registry.get(name))) return;
  let timer;
  const expired = new Promise((resolve) => {
    timer = setTimeout(resolve, timeout);
  });
  const apps = registry.whenDefined ? APP_ELEMENTS.map((name) => registry.whenDefined(name)) : [];
  await Promise.race([...apps, expired]);
  clearTimeout(timer);
}

if (globalThis.window?.customElements) frontendReady().then(register);

export {
  APP_ELEMENTS,
  addWeeks,
  checkoutDarts,
  scoreAnswer,
  scoreEntry,
  scoreHint,
  scoreReady,
  scorable,
  aimBeds,
  aimDraws,
  aimField,
  aimHtml,
  aimRequest,
  aimRows,
  aimSegment,
  aimSummaryHtml,
  aimView,
  badgesHtml,
  badgesView,
  bracketSlots,
  freshSlots,
  stageName,
  tournamentBoards,
  tournamentCalls,
  tournamentCallState,
  tournamentCountdown,
  tournamentHtml,
  tournamentLabel,
  tournamentStartData,
  tournamentView,
  bedPath,
  beds,
  bestsHtml,
  bestsView,
  boardSpot,
  padViewBox,
  boardStatus,
  boardSvg,
  bullOffLeaders,
  bullOffView,
  callerCalls,
  callerSounds,
  callerState,
  callerText,
  celebrationHtml,
  celebrationOf,
  cameraEntities,
  cardForm,
  createElements,
  cricketBeds,
  cricketTable,
  cricketView,
  cssColor,
  dartKey,
  dashboardStrategy,
  deadDarts,
  detectionRunning,
  doubleColor,
  doublesHtml,
  doublesView,
  drillBeds,
  drillView,
  entityIndex,
  escapeHtml,
  formatClock,
  formatDateTime,
  formatNumber,
  formatPercent,
  frontendReady,
  gameGroup,
  gameRules,
  gameState,
  gameView,
  heatColor,
  heatLevels,
  heatRatio,
  hitBeds,
  idlePanels,
  kind,
  label,
  language,
  leaderboardRecords,
  leaderboardRecordsHtml,
  livePanel,
  loadSound,
  lobbyChange,
  lobbyChoice,
  lobbyHints,
  lobbyGames,
  lobbyHtml,
  lobbySuggestions,
  matchResult,
  padBed,
  padHtml,
  NORM,
  NUMBERS,
  numbersSvg,
  offsetText,
  parseSegment,
  partyBeds,
  partyView,
  pastSessions,
  personLinks,
  pictureUrl,
  playersHtml,
  playersView,
  positionsDensity,
  positionsHtml,
  practiceView,
  profileNames,
  progressView,
  R,
  recentVisits,
  register,
  scoreboardHtml,
  sectorAt,
  setupView,
  shortProcessor,
  sparkline,
  spreadHtml,
  spreadView,
  startGameData,
  summaryTable,
  summaryView,
  targetBeds,
  targetText,
  tierColor,
  topHits,
  trendsHtml,
  trendView,
  trendWeeks,
  visitBucket,
  visitCount,
  visitsFromHistory,
  voiceLanguage,
  voicePack,
  voicePackName,
};
