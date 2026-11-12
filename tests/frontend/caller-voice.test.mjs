// The caller with a voice pack: recorded sounds of darts-caller's packs, one call after the
// other, and the browser's voice for what the pack lacks.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, READY, loadCards, makeHass, mount, settle, update, window } from "./dom.mjs";

const { callerSounds, loadSound, voicePack, voicePackName } = await loadCards();

const BASE = "/media/local/homedarts/voices/russ-bray";
const url = (file) => `${BASE}/${encodeURIComponent(file).replace(/%2F/g, "/")}`;
const SOUNDS = {
  180: [url("180.mp3"), url("180+2.mp3")],
  busted: [url("busted.mp3")],
  matchshot: [url("matchshot.mp3")],
  you_require: [url("you_require.mp3")],
  40: [url("40.mp3")],
  sam: [url("names/sam.mp3")],
  // A file that went missing after Home Assistant listed it.
  66: [url("66.mp3")],
};

// What the speakers play, in order: the files of sounds, and "words" in the browser's voice.
const heard = [];
class Utterance {
  constructor(words) {
    this.text = words;
    this.lang = "";
  }
}
const speech = {
  speak(utterance) {
    heard.push(`"${utterance.text}"`);
    setImmediate(() => utterance.onend?.());
  },
  cancel: () => heard.push("cancel"),
};
window.speechSynthesis = speech;
globalThis.SpeechSynthesisUtterance = Utterance;

// An audio context whose sounds end on their own a moment after they start, unless held.
class FakeAudioContext {
  static hold = false;
  static broken = 0;

  constructor() {
    this.destination = { name: "speakers" };
    this.currentTime = 0;
  }

  resume() {}

  async decodeAudioData(data) {
    return { duration: 0.5, file: data.file };
  }

  createBufferSource() {
    if (FakeAudioContext.broken) {
      FakeAudioContext.broken -= 1;
      throw new Error("The audio context is closed");
    }
    const source = {
      connect: (node) => (source.output = node),
      start: () => {
        heard.push(source.buffer.file);
        if (!FakeAudioContext.hold) setImmediate(() => source.onended());
      },
      stop: () => {
        heard.push("stop");
        source.onended();
      },
    };
    return source;
  }

  // The fanfare of a 180.
  createOscillator() {
    return { frequency: {}, connect: (node) => node, start() {}, stop() {} };
  }

  createGain() {
    return { gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect: (node) => node };
  }
}

// Home Assistant with a voice pack: what the card asks for, and the files it loads.
function homeAssistant({ pack = { pack: "russ-bray", sounds: SOUNDS }, answer, withFiles = true } = {}) {
  const asked = [];
  const fetched = [];
  const callWS = (message) => {
    asked.push(message);
    if (answer) return answer(message);
    return message.pack === "russ-bray" ? Promise.resolve(pack) : Promise.reject({ code: "not_found" });
  };
  const fetchWithAuth = async (address) => {
    fetched.push(address);
    const file = decodeURIComponent(address.slice(BASE.length + 1));
    return file === "66.mp3" ? { ok: false, status: 404 } : { ok: true, arrayBuffer: async () => ({ file }) };
  };
  return { asked, fetched, callWS, ...(withFiles ? { fetchWithAuth } : {}) };
}

const PLAYERS = [
  { player: 1, name: "Alex", remaining: 501, legs: 0, sets: 0, average: null },
  { player: 2, name: "Sam", remaining: 501, legs: 0, sets: 0, average: null },
];
const dart = (number, multiplier) => ({ number, multiplier, bed: multiplier === 3 ? "Triple" : "SingleOuter" });
const T20 = dart(20, 3);
const visit = (...throws) => ({
  "sensor.local_visit_score": {
    state: String(throws.reduce((sum, item) => sum + item.number * item.multiplier, 0)),
    attributes: { throws },
  },
});
const x01 = (remaining, keys = [], attributes = {}) => ({
  "sensor.practice_remaining": {
    state: String(remaining),
    attributes: { game: 501, player: 1, name: "Alex", scores: PLAYERS, remaining, visit: keys, ...attributes },
  },
});
const setup = (wiring, config = {}) => {
  const hass = { ...makeHass({ states: { ...READY, ...visit(), ...x01(501) } }), ...wiring };
  delete hass.asked;
  delete hass.fetched;
  const card = mount("homedarts-scoreboard-card", hass, { caller: true, caller_voice: "russ-bray", ...config });
  return { hass, card };
};
const tap = (card) => $(card, ".caller-toggle").click();
// Every call waits for the one before; a few turns of the event loop play them all.
const played = async () => {
  for (let turn = 0; turn < 30; turn += 1) await settle();
  return heard.splice(0);
};

test("the settings name a pack, or the browser's voice", () => {
  assert.deepEqual(
    [undefined, "", "  ", "browser", " Browser ", 42, " russ-bray "].map(voicePackName),
    [null, null, null, null, null, null, "russ-bray"]
  );
  assert.equal(voicePack(null), null);
  assert.equal(voicePack({ sounds: {} }), null);
  // Only addresses of the media folder count.
  assert.deepEqual(
    voicePack({ sounds: { 180: "180.mp3", busted: [1, "/local/busted.mp3", `${BASE}/busted.mp3`], gameshot: [] } }),
    { sounds: new Map([["busted", [`${BASE}/busted.mp3`]]]) }
  );
});

test("a call is the sounds of darts-caller's file names, or nothing the pack can say", () => {
  const pack =
    (...keys) =>
    (key) =>
      keys.includes(key);
  const t = (key) => ({ bot: "Bot", score_player: "Player" })[key] ?? key;
  const sounds = (call, ...keys) => callerSounds(call, pack(...keys), t);
  assert.deepEqual(sounds({ kind: "score", score: 180 }, "180"), [{ sound: "180" }]);
  assert.equal(sounds({ kind: "score", score: 66 }, "180"), null);
  assert.deepEqual(sounds({ kind: "bust" }, "busted"), [{ sound: "busted" }]);
  assert.deepEqual(sounds({ kind: "leg" }, "gameshot"), [{ sound: "gameshot" }]);
  // The match names its winner: with their sound, or in words.
  assert.deepEqual(sounds({ kind: "match", name: "Alex" }, "matchshot"), [{ sound: "matchshot" }, { text: "Alex" }]);
  assert.deepEqual(sounds({ kind: "match", name: " Alex Bee" }, "matchshot", "alex bee"), [
    { sound: "matchshot" },
    { sound: "alex bee" },
  ]);
  assert.deepEqual(sounds({ kind: "match", name: null }, "matchshot"), [{ sound: "matchshot" }]);
  // The file of a name is its plain lower case, as darts-caller names it, also with ß.
  assert.deepEqual(sounds({ kind: "match", name: "Weiß" }, "matchshot", "weiß"), [
    { sound: "matchshot" },
    { sound: "weiß" },
  ]);
  assert.equal(sounds({ kind: "match", name: "Alex" }, "alex"), null);
  // What a player requires: one sound, or you_require and the score.
  const alone = { kind: "require", remaining: 40, players: 1, player: 1, name: null };
  assert.deepEqual(sounds(alone, "yr_40", "you_require", "40"), [{ sound: "yr_40" }]);
  assert.deepEqual(sounds(alone, "you_require", "c_40", "40"), [{ sound: "you_require" }, { sound: "c_40" }]);
  assert.deepEqual(sounds(alone, "you_require", "40"), [{ sound: "you_require" }, { sound: "40" }]);
  assert.equal(sounds(alone, "you_require"), null);
  assert.equal(sounds(alone, "40", "yr_41"), null);
  // In a match, the player at the board first.
  const match = { ...alone, players: 2, player: 2, name: "Sam" };
  assert.deepEqual(sounds(match, "yr_40", "sam"), [{ sound: "sam" }, { sound: "yr_40" }]);
  assert.deepEqual(sounds({ ...match, bot: true }, "yr_40"), [{ text: "Bot" }, { sound: "yr_40" }]);
  assert.deepEqual(sounds({ ...match, name: null }, "yr_40"), [{ text: "Player 2" }, { sound: "yr_40" }]);
  // Marks, setups and tournaments have no sounds in darts-caller's packs.
  for (const kind of ["marks", "runs", "setup", "limit_match", "tournament_next"]) {
    assert.equal(sounds({ kind, marks: 3, leave: 32 }, "3", "32"), null, kind);
  }
});

test("a dart, a route and a target are the sounds of their beds, or nothing the pack can say", () => {
  const pack =
    (...keys) =>
    (key) =>
      keys.includes(key);
  const sounds = (call, ...keys) => callerSounds(call, pack(...keys), (key) => key);
  const thrown = (key, by = "bed") => ({ kind: "dart", key, by });
  const beds = ["t20", "d16", "s5", "5", "bull", "bullseye", "outside", "60"];
  assert.deepEqual(
    ["T20", "D16", "S5", "25", "BULL", "MISS"].map((key) => sounds(thrown(key), ...beds)),
    ["t20", "d16", "s5", "bull", "bullseye", "outside"].map((sound) => [{ sound }])
  );
  // A single without a sound of its own is its number; by its points, a dart is their sound.
  assert.deepEqual(sounds(thrown("S5"), "5"), [{ sound: "5" }]);
  assert.deepEqual(sounds(thrown("T20", "score"), ...beds), [{ sound: "60" }]);
  assert.deepEqual(sounds(thrown("MISS", "score"), ...beds), [{ sound: "outside" }]);
  assert.equal(sounds(thrown("T19"), ...beds), null);
  // A route is its beds, after the score it finishes where the call names it.
  const route = { kind: "route", route: ["T20", "D16"] };
  assert.deepEqual(sounds(route, "t20", "d16"), [{ sound: "t20" }, { sound: "d16" }]);
  assert.deepEqual(sounds({ ...route, remaining: 92 }, "c_92", "92", "t20", "d16"), [
    { sound: "c_92" },
    { sound: "t20" },
    { sound: "d16" },
  ]);
  assert.deepEqual(sounds({ ...route, remaining: 92 }, "92", "t20", "d16")[0], { sound: "92" });
  assert.equal(sounds({ ...route, remaining: 92 }, "t20", "d16"), null);
  assert.equal(sounds(route, "t20"), null);
  // A target is bs_target_is and the target, as in the blind support of darts-caller.
  const target = (aim, ...keys) => sounds({ kind: "target", target: aim }, "bs_target_is", ...keys);
  assert.deepEqual(target("20", "20", "s20"), [{ sound: "bs_target_is" }, { sound: "20" }]);
  assert.deepEqual(
    [
      ["20", "s20"],
      ["D", "bs_any_double"],
      ["D16", "d16"],
      ["25", "bull"],
      ["50", "bullseye"],
      ["BULL", "bullseye"],
    ].map(([aim, key]) => target(aim, key)[1].sound),
    ["s20", "bs_any_double", "d16", "bull", "bullseye", "bullseye"]
  );
  assert.equal(target("T", "t20"), null);
  assert.equal(target("25", "25"), null);
  assert.equal(sounds({ kind: "target", target: "20" }, "20"), null);
});

test("a sound is loaded once, again after it failed, and the oldest are let go", async () => {
  const context = { decodeAudioData: async (data) => ({ decoded: data }) };
  const fetched = [];
  const fetch = async (address) => {
    fetched.push(address);
    return address.endsWith("404") ? { ok: false, status: 404 } : { ok: true, arrayBuffer: async () => address };
  };
  assert.deepEqual(await loadSound("/media/a.mp3", fetch, context), { decoded: "/media/a.mp3" });
  await loadSound("/media/a.mp3", fetch, context);
  assert.deepEqual(fetched.splice(0), ["/media/a.mp3"]);
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await assert.rejects(loadSound("/media/404", fetch, context), { message: "/media/404: 404" });
    await settle();
  }
  assert.deepEqual(fetched.splice(0), ["/media/404", "/media/404"]);
  for (let index = 0; index < 64; index += 1) await loadSound(`/media/${index}.mp3`, fetch, context);
  fetched.length = 0;
  await loadSound("/media/a.mp3", fetch, context);
  await loadSound("/media/63.mp3", fetch, context);
  assert.deepEqual(fetched, ["/media/a.mp3"]);
});

test("without an audio context, the browser's voice calls, also with a pack", async () => {
  assert.equal(window.AudioContext ?? window.webkitAudioContext, undefined);
  const wiring = homeAssistant();
  const { hass, card } = setup(wiring);
  tap(card);
  assert.deepEqual(wiring.asked, [{ type: "homedarts/voice_pack", pack: "russ-bray" }]);
  await settle();
  card.hass = update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  assert.deepEqual(await played(), ['"Caller on"', '"180"']);
  assert.deepEqual(wiring.fetched, []);
  tap(card);
  heard.length = 0;
});

test("the pack calls what it has, one call after the other, and the browser's voice the rest", async (t) => {
  window.AudioContext = FakeAudioContext;
  t.mock.method(Math, "random", () => 0.99);
  const wiring = homeAssistant();
  const { hass, card } = setup(wiring);
  tap(card);
  await played();
  let next = update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  card.hass = next;
  // Sam requires 40: the pack has Sam, "you require" and 40, but no yr_40.
  next = update(next, { ...visit(), ...x01(40, [], { player: 2, name: "Sam", checkout: "D20" }) });
  card.hass = next;
  next = update(next, {
    ...visit(dart(20, 1), dart(20, 1), dart(5, 1)),
    ...x01(40, ["S20", "S20", "S5"], { player: 2, name: "Sam", checkout: "D20", bust: true }),
  });
  card.hass = next;
  // A visit without a sound, and one whose file went missing.
  const miss = dart(0, 0);
  next = update(next, { ...visit(), ...x01(321, []) });
  card.hass = next;
  next = update(next, { ...visit(miss, miss, miss), ...x01(321, ["M", "M", "M"]) });
  card.hass = next;
  next = update(next, { ...visit(dart(20, 3), dart(6, 1), dart(0, 0)), ...x01(255, ["T20", "S6", "M"]) });
  card.hass = next;
  next = update(next, { ...visit(dart(20, 2)), ...x01(0, ["D20"], { player: 2, name: "Sam", won: true, winner: 2 }) });
  card.hass = next;
  // Nothing plays over another call: each waits for the one before.
  assert.deepEqual(heard.splice(0), []);
  assert.deepEqual(await played(), [
    "180+2.mp3",
    "names/sam.mp3",
    "you_require.mp3",
    "40.mp3",
    "busted.mp3",
    '"No score"',
    '"66"',
    "matchshot.mp3",
    "names/sam.mp3",
  ]);
  // Loaded with the login of the scoreboard, each file once.
  assert.equal(wiring.fetched.filter((address) => address.endsWith("sam.mp3")).length, 1);
  assert.equal(wiring.asked.length, 1);
  tap(card);
  assert.deepEqual(heard.splice(0), ["cancel"]);
  // Switched on again, the card asks for the pack anew, with the files copied there since.
  tap(card);
  await played();
  assert.equal(wiring.asked.length, 2);
  tap(card);
  heard.length = 0;
});

test("switching the caller off ends the call that plays and drops those that wait", async (t) => {
  t.mock.method(Math, "random", () => 0);
  FakeAudioContext.hold = true;
  const { hass, card } = setup(homeAssistant());
  tap(card);
  await played();
  let next = update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  card.hass = next;
  next = update(next, { ...visit(), ...x01(40, [], { player: 2, name: "Sam", checkout: "D20" }) });
  card.hass = next;
  assert.deepEqual(await played(), ["180.mp3"]);
  tap(card);
  assert.deepEqual(await played(), ["stop", "cancel"]);
  FakeAudioContext.hold = false;
});

test("a sound the browser cannot play ends its call, and the next one still comes", async () => {
  const { hass, card } = setup(homeAssistant());
  tap(card);
  await played();
  FakeAudioContext.broken = 1;
  let next = update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  card.hass = next;
  next = update(next, {
    ...visit(dart(20, 1), dart(20, 1), dart(5, 1)),
    ...x01(321, ["S20", "S20", "S5"], { bust: true }),
  });
  card.hass = next;
  assert.deepEqual(await played(), ["busted.mp3"]);
  tap(card);
  heard.length = 0;
});

test("without the browser's voice, the pack still calls and a name without a sound is left out", async () => {
  delete window.speechSynthesis;
  const { hass, card } = setup(homeAssistant());
  tap(card);
  await settle();
  card.hass = update(hass, {
    ...visit(dart(20, 2)),
    ...x01(0, ["D20"], { player: 1, name: "Alex", won: true, winner: 1 }),
  });
  assert.deepEqual(await played(), ["matchshot.mp3"]);
  tap(card);
  window.speechSynthesis = speech;
});

test("an unknown pack, or a Home Assistant that cannot hand out its files, leaves the calls to the browser", async () => {
  const score = (hass) => update(hass, { ...visit(T20, T20, T20), ...x01(321, ["T20", "T20", "T20"]) });
  for (const [wiring, config, asked] of [
    [homeAssistant(), { caller_voice: "piper-en" }, 1],
    [homeAssistant(), { caller_voice: "browser" }, 0],
    [homeAssistant({ withFiles: false }), {}, 0],
    [{}, {}, 0],
  ]) {
    const { hass, card } = setup(wiring, config);
    tap(card);
    await played();
    card.hass = score(hass);
    assert.deepEqual(heard.splice(0), ['"180"']);
    assert.equal(wiring.asked?.length ?? 0, asked);
    tap(card);
    heard.length = 0;
  }
  // The answer for a pack the settings no longer name comes too late to count.
  let answered;
  const wiring = homeAssistant({
    answer: (message) =>
      message.pack === "russ-bray" ? new Promise((resolve) => (answered = resolve)) : Promise.reject(new Error("no")),
  });
  const { hass, card } = setup(wiring);
  tap(card);
  card.setConfig({ type: "custom:homedarts-scoreboard-card", caller: true, caller_voice: "piper-en" });
  card.hass = update(hass, { ...visit(dart(20, 1)), ...x01(481, ["S20"]) });
  assert.deepEqual(
    wiring.asked.map((message) => message.pack),
    ["russ-bray", "piper-en"]
  );
  answered({ pack: "russ-bray", sounds: SOUNDS });
  await played();
  card.hass = score(card._hass);
  assert.deepEqual(heard.splice(0), ['"180"']);
  tap(card);
  heard.length = 0;
});

test("for a blind player, the pack calls every dart and the route that is left, the browser what it lacks", async () => {
  window.AudioContext = FakeAudioContext;
  const beds = { ...SOUNDS, t20: [url("t20.mp3")], d20: [url("d20.mp3")] };
  const wiring = homeAssistant({ pack: { pack: "russ-bray", sounds: beds } });
  const { hass, card } = setup(wiring, { call_darts: "bed", call_route: true });
  tap(card);
  await played();
  let next = update(hass, { ...visit(), ...x01(100, [], { checkout: "T20 D20" }) });
  card.hass = next;
  next = update(next, { ...visit(T20), ...x01(40, ["T20"], { checkout: "D20" }) });
  card.hass = next;
  next = update(next, { ...visit(T20, dart(20, 2)), ...x01(0, ["T20", "D20"], { won: true }) });
  card.hass = next;
  assert.deepEqual(await played(), [
    '"Alex, you require 100"',
    "t20.mp3",
    "d20.mp3",
    "t20.mp3",
    "40.mp3",
    "d20.mp3",
    "d20.mp3",
    '"Game shot, and the leg!"',
  ]);
  tap(card);
  heard.length = 0;
});
