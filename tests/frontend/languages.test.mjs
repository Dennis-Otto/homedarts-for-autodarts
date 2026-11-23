// Dutch, French and Spanish in a browser DOM: the language a card picks, its texts and
// numbers, its forms and card picker entries, and the voice and words of the caller.
import assert from "node:assert/strict";
import { test } from "node:test";

import { $, $$, READY, camera, loadCards, makeHass, mount, text, update, window } from "./dom.mjs";

const { language, voiceLanguage } = await loadCards();

// What each language shows and says for the same board and game.
const WORDS = {
  nl: {
    ready: "Klaar – gooi!",
    visit: "Huidige beurt",
    progress: "Dart 1 van 3",
    points: "60 punten",
    controls: ["Detectie stoppen", "Detectie resetten", "Kalibreren"],
    callerOn: "Caller aan",
    require: "Sam, je hebt nog 40 nodig",
    bust: "Geen score",
    match: "Game shot, en de wedstrijd, Sam!",
    matchWithoutName: "Game shot, en de wedstrijd!",
    training: "Training · Dartboard",
    averageLabel: "3-dart-gemiddelde",
    session: "Sessie loopt",
    endSession: "Sessie beëindigen",
    update: "Update naar 1.5.0",
    chips: ["Board Manager: Verbonden", "Realtime: Verbroken", "Bordcloud: Niet beschikbaar"],
    cameras: "Camera's: Niet actief",
    layout: "Indeling",
    layouts: ["Automatisch", "Bord rechts", "Bord onderaan", "Alleen bord"],
    scoreboard: "HomeDarts-scorebord",
  },
  fr: {
    ready: "Prêt – lancez\u00a0!",
    visit: "Volée en cours",
    progress: "Fléchette 1 sur 3",
    points: "60 points",
    controls: ["Arrêter la détection", "Réinitialiser la détection", "Calibrer"],
    callerOn: "Annonceur activé",
    require: "Sam, il vous reste 40",
    bust: "Aucun point",
    match: "Game shot, et le match, Sam\u00a0!",
    matchWithoutName: "Game shot, et le match\u00a0!",
    training: "Entraînement · Dartboard",
    averageLabel: "Moyenne 3 fléchettes",
    session: "Session en cours",
    endSession: "Terminer la session",
    update: "Mise à jour vers 1.5.0",
    chips: ["Board Manager\u00a0: Connecté", "Temps réel\u00a0: Déconnecté", "Cloud de la cible\u00a0: Indisponible"],
    cameras: "Caméras\u00a0: Arrêté",
    layout: "Disposition",
    layouts: ["Automatique", "Cible à droite", "Cible en dessous", "Cible seule"],
    scoreboard: "Tableau des scores HomeDarts",
  },
  es: {
    ready: "Todo listo – ¡lanza!",
    visit: "Tirada actual",
    progress: "Dardo 1 de 3",
    points: "60 puntos",
    controls: ["Detener detección", "Restablecer detección", "Calibrar"],
    callerOn: "Locutor activado",
    require: "Sam, te quedan 40",
    bust: "Sin puntos",
    match: "¡Game shot, y el partido, Sam!",
    matchWithoutName: "¡Game shot, y el partido!",
    training: "Entrenamiento · Dartboard",
    averageLabel: "Media de 3 dardos",
    session: "Sesión en curso",
    endSession: "Terminar sesión",
    update: "Actualizar a 1.5.0",
    chips: ["Board Manager: Conectado", "Tiempo real: Desconectado", "Nube de la diana: No disponible"],
    cameras: "Cámaras: No se está ejecutando",
    layout: "Disposición",
    layouts: ["Automática", "Diana a la derecha", "Diana debajo", "Solo la diana"],
    scoreboard: "Marcador HomeDarts",
  },
};

const LANGUAGES = Object.keys(WORDS);
// The raw text of an element, with its no-break spaces.
const raw = (card, selector) => $(card, selector).textContent.trim();

const dart = (number, multiplier) => ({ number, multiplier, bed: multiplier === 3 ? "Triple" : "SingleOuter" });
const T20 = { ...dart(20, 3), x: 0.035, y: 0.608 };
const score = (...throws) => ({
  state: String(throws.reduce((sum, item) => sum + item.number * item.multiplier, 0)),
  attributes: { throws, recent_visits: [] },
});

test("a card speaks Home Assistant's language, also in a regional variant, and English otherwise", () => {
  for (const [own, card, voice] of [
    ["nl", "nl", "nl"],
    ["nl-BE", "nl", "nl-BE"],
    ["fr", "fr", "fr"],
    ["fr-CA", "fr", "fr-CA"],
    ["es", "es", "es"],
    ["es-419", "es", "es-419"],
    ["de-CH", "de", "de-CH"],
    ["en-GB", "en", "en-GB"],
    // A language without card texts reads and hears English, even when its code starts like one.
    ["it", "en", "en"],
    ["esperanto", "en", "en"],
    ["", "en", "en"],
  ]) {
    const hass = { locale: { language: own }, language: own };
    assert.equal(language(hass), card, own);
    assert.equal(voiceLanguage(hass), voice, own);
  }
  // Without a locale Home Assistant's language setting decides; without either, English.
  assert.equal(language({ language: "fr" }), "fr");
  assert.equal(language(undefined), "en");
});

test("the live card speaks Dutch, French and Spanish, with their decimal comma", () => {
  for (const lang of LANGUAGES) {
    const words = WORDS[lang];
    const states = { ...READY, "sensor.local_visit_score": score(T20), "sensor.training_average": "45.6" };
    const card = mount("homedarts-card", makeHass({ states, language: lang }));
    assert.equal(raw(card, ".pill"), words.ready, lang);
    assert.equal(raw(card, ".visit-label"), words.visit, lang);
    assert.equal(text(card, ".progress"), words.progress, lang);
    assert.equal(text(card, ".slot .value"), words.points, lang);
    assert.equal(text(card, '[data-stat="average"] .value'), "45,6", lang);
    assert.deepEqual(
      $$(card, ".controls button").map((button) => button.textContent),
      words.controls,
      lang
    );
    card.remove();
  }
});

const SESSION = {
  "sensor.training_darts": { state: "24", attributes: { hits: { T20: 3, S20: 6, MISS: 5 } } },
  "sensor.training_average": "55.75",
  "sensor.training_started": "2026-09-26T14:30:00+00:00",
  "button.reset_training": "unknown",
  "switch.training_session": { state: "on", last_changed: "2026-09-26T14:30:00+00:00" },
};
const BOARD = {
  ...READY,
  "update.board_software": { state: "on", attributes: { installed_version: "1.4.2", latest_version: "1.5.0" } },
};

test("the training and status cards speak Dutch, French and Spanish", () => {
  for (const lang of LANGUAGES) {
    const words = WORDS[lang];
    const training = mount("homedarts-training-card", makeHass({ states: SESSION, language: lang }));
    assert.equal(text(training, ".title"), words.training, lang);
    assert.equal(text(training, ".average"), "55,8", lang);
    assert.equal(raw(training, ".average-label"), words.averageLabel, lang);
    assert.equal(raw(training, ".session-state"), words.session, lang);
    assert.equal(raw(training, '[data-action="session"]'), words.endSession, lang);
    const status = mount("homedarts-status-card", makeHass({ states: BOARD, cameras: [camera(1)], language: lang }));
    assert.equal(raw(status, ".pill"), words.ready, lang);
    assert.equal(raw(status, ".update-badge"), words.update, lang);
    training.remove();
    status.remove();
    // The connection chips say their state in Home Assistant's words of that language.
    const links = {
      "binary_sensor.realtime_connected": "off",
      "binary_sensor.cloud_link": "unavailable",
      "binary_sensor.cameras_active": "off",
    };
    const chips = mount("homedarts-status-card", makeHass({ states: { ...BOARD, ...links }, language: lang }));
    assert.deepEqual(
      $$(chips, ".chip").map((chip) => chip.getAttribute("aria-label")),
      words.chips,
      lang
    );
    const live = mount("homedarts-card", makeHass({ states: { ...BOARD, ...links }, language: lang }));
    assert.equal($$(live, ".chip").at(-1).getAttribute("aria-label"), words.cameras, lang);
    chips.remove();
    live.remove();
  }
});

test("every language has the words of the connection chips' states", async () => {
  const texts = {};
  for (const lang of ["en", "de", ...LANGUAGES]) {
    texts[lang] = (await import(`../../custom_components/homedarts/frontend/text/${lang}.js`)).default;
  }
  const keys = Object.keys(texts.en).filter((key) => key.startsWith("chip_"));
  assert.deepEqual(keys, [
    "chip_state",
    "chip_connected",
    "chip_disconnected",
    "chip_running",
    "chip_not_running",
    "chip_on",
    "chip_off",
    "chip_unavailable",
    "chip_unknown",
  ]);
  for (const [lang, text] of Object.entries(texts)) {
    for (const key of keys) assert.equal(typeof text[key], "string", `${lang} ${key}`);
    // The pattern names the label first, so the name starts with what the chip shows.
    assert.match(text.chip_state, /^\{label\}(\u00a0)?: \{state\}$/, lang);
  }
});

// The scoreboard of a two-player 501 at the board.
const PLAYERS = [
  { player: 1, name: "Alex", remaining: 501, legs: 0, sets: 0, average: null },
  { player: 2, name: "Sam", remaining: 301, legs: 0, sets: 0, average: null },
];
const x01 = (remaining, keys = [], attributes = {}) => ({
  "sensor.practice_remaining": {
    state: String(remaining),
    attributes: { game: 501, player: 1, name: "Alex", scores: PLAYERS, remaining, visit: keys, ...attributes },
  },
});
const visit = (...throws) => ({ "sensor.local_visit_score": score(...throws) });
const spoken = [];
window.speechSynthesis = { speak: (utterance) => spoken.push([utterance.text, utterance.lang]), cancel() {} };
globalThis.SpeechSynthesisUtterance = class {
  constructor(words) {
    this.text = words;
    this.lang = "";
  }
};

test("the caller calls Dutch, French and Spanish games with a voice of that language", () => {
  for (const lang of LANGUAGES) {
    const words = WORDS[lang];
    const hass = makeHass({ states: { ...READY, ...visit(), ...x01(501) }, language: lang });
    const card = mount("homedarts-scoreboard-card", hass, { caller: true });
    $(card, ".caller-toggle").click();
    assert.deepEqual(spoken.splice(0), [[words.callerOn, lang]], lang);
    const sam = { player: 2, name: "Sam", checkout: "D20" };
    let next = update(hass, { ...visit(), ...x01(40, [], sam) });
    card.hass = next;
    next = update(next, { ...visit(dart(20, 1), dart(20, 1), dart(5, 1)), ...x01(40, ["S20", "S20", "S5"], { ...sam, bust: true }) });
    card.hass = next;
    next = update(next, { ...visit(dart(20, 2)), ...x01(0, ["D20"], { ...sam, won: true, winner: 2 }) });
    card.hass = next;
    assert.deepEqual(
      spoken.splice(0),
      [words.require, words.bust, words.match].map((call) => [call, lang]),
      lang
    );
    // A winner without a name hears the call without one, in the punctuation of the language.
    const nameless = [PLAYERS[0], { ...PLAYERS[1], name: null }];
    card.hass = update(next, { ...visit(), ...x01(40, [], { ...sam, name: null, scores: nameless }) });
    card.hass = update(next, x01(0, ["D20"], { ...sam, name: null, scores: nameless, won: true, winner: 2 }));
    assert.equal(spoken.splice(0).at(-1)[0], words.matchWithoutName, lang);
    // The caller is one for every card; the next language switches it on again.
    $(card, ".caller-toggle").click();
    spoken.splice(0);
    card.remove();
  }
});

test("card forms and the card picker speak the language of the last Home Assistant a card saw", () => {
  for (const lang of LANGUAGES) {
    const words = WORDS[lang];
    mount("homedarts-card", makeHass({ states: READY, language: lang })).remove();
    const form = customElements.get("homedarts-card").getConfigForm();
    assert.equal(form.computeLabel({ name: "layout" }), words.layout, lang);
    assert.deepEqual(
      form.schema[2].schema[0].selector.select.options.map((option) => option.label),
      words.layouts,
      lang
    );
    const scoreboard = window.customCards.find((card) => card.type === "homedarts-scoreboard-card");
    assert.equal(scoreboard.name, words.scoreboard, lang);
    // The documentation is English and German; other languages link the English one.
    assert.equal(scoreboard.documentationURL, "https://dennis-otto.github.io/homedarts-for-autodarts/cards.html#scoreboard-card", lang);
  }
});
