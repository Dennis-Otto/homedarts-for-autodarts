/*
 * The live demo of the website (index.html next to this file): the cards of the
 * integration replay games that the integration played at a simulated board.
 *
 * timeline.json holds them, recorded by scripts/record_demo.py: after each move at
 * the board, the states of the entities that changed, and the answers to the
 * positions command of the training card. A stand-in for Home Assistant hands the
 * cards these states as Home Assistant would, with every moment moved to the time
 * of the replay. Nothing is installed, and nothing leaves the page: a button of a
 * card only says that this is a recording.
 */

export const LANGUAGES = ["en", "de", "nl", "fr", "es"];
export const SPEEDS = [1, 2, 4];
// The longest wait between two steps at normal speed, and the wait before the
// games start again from the first one.
export const LONGEST_WAIT = 4000;
export const AGAIN = 8000;
// How long the note about the buttons shows.
export const NOTICE = 4000;

// The languages of the website besides English, as mkdocs.yml builds them; the
// others read the English pages. A language shows a page it has no version of in
// English, in its own menu.
export const WEBSITE_LANGUAGES = ["de", "nl", "fr", "es"];

export const TEXT = {
  en: {
    name: "English",
    page_title: "Live demo of the cards – HomeDarts for Autodarts",
    title: "Try the cards",
    lead: "Games at a simulated board, played by the integration and shown by its cards, right here in your browser. Nothing to install.",
    games: "Games",
    x01: "501 against the bot",
    cricket: "Cricket",
    tournament: "Tournament",
    play: "Play",
    pause: "Pause",
    speed: "Speed",
    language: "Language",
    progress: "Progress of the games",
    notice: "This is a recording, so the buttons change nothing here. In Home Assistant, they do.",
    loading: "Loading the games…",
    failed: "The games could not be loaded. Reload the page to try again.",
    install: "Install the integration",
    docs: "Documentation",
  },
  de: {
    name: "Deutsch",
    page_title: "Live-Demo der Karten – HomeDarts for Autodarts",
    title: "Probier die Karten aus",
    lead: "Spiele an einem simulierten Board, gespielt von der Integration und gezeigt von ihren Karten, direkt hier in deinem Browser. Nichts zu installieren.",
    games: "Spiele",
    x01: "501 gegen den Bot",
    cricket: "Cricket",
    tournament: "Turnier",
    play: "Abspielen",
    pause: "Pause",
    speed: "Tempo",
    language: "Sprache",
    progress: "Fortschritt der Spiele",
    notice: "Das ist eine Aufzeichnung, darum ändern die Schaltflächen hier nichts. In Home Assistant schon.",
    loading: "Die Spiele werden geladen …",
    failed: "Die Spiele konnten nicht geladen werden. Lade die Seite neu, um es noch einmal zu versuchen.",
    install: "Integration installieren",
    docs: "Dokumentation",
  },
  nl: {
    name: "Nederlands",
    page_title: "Live-demo van de kaarten – HomeDarts for Autodarts",
    title: "Probeer de kaarten",
    lead: "Spellen op een gesimuleerd bord, gespeeld door de integratie en getoond door haar kaarten, gewoon hier in je browser. Niets te installeren.",
    games: "Spellen",
    x01: "501 tegen de bot",
    cricket: "Cricket",
    tournament: "Toernooi",
    play: "Afspelen",
    pause: "Pauzeren",
    speed: "Snelheid",
    language: "Taal",
    progress: "Voortgang van de spellen",
    notice: "Dit is een opname, dus de knoppen veranderen hier niets. In Home Assistant wel.",
    loading: "De spellen worden geladen…",
    failed: "De spellen konden niet worden geladen. Laad de pagina opnieuw om het nog eens te proberen.",
    install: "De integratie installeren",
    docs: "Documentatie",
  },
  fr: {
    name: "Français",
    page_title: "Démo en direct des cartes – HomeDarts for Autodarts",
    title: "Essayez les cartes",
    lead: "Des parties sur une cible simulée, jouées par l’intégration et affichées par ses cartes, ici même dans votre navigateur. Rien à installer.",
    games: "Parties",
    x01: "501 contre le bot",
    cricket: "Cricket",
    tournament: "Tournoi",
    play: "Lire",
    pause: "Pause",
    speed: "Vitesse",
    language: "Langue",
    progress: "Progression des parties",
    notice: "Ceci est un enregistrement\u00a0: les boutons ne changent rien ici. Dans Home Assistant, si.",
    loading: "Chargement des parties…",
    failed: "Impossible de charger les parties. Rechargez la page pour réessayer.",
    install: "Installer l’intégration",
    docs: "Documentation",
  },
  es: {
    name: "Español",
    page_title: "Demo en vivo de las tarjetas – HomeDarts for Autodarts",
    title: "Prueba las tarjetas",
    lead: "Partidas en una diana simulada, jugadas por la integración y mostradas por sus tarjetas, aquí mismo en tu navegador. Sin instalar nada.",
    games: "Partidas",
    x01: "501 contra el bot",
    cricket: "Cricket",
    tournament: "Torneo",
    play: "Reproducir",
    pause: "Pausa",
    speed: "Velocidad",
    language: "Idioma",
    progress: "Progreso de las partidas",
    notice: "Esto es una grabación, así que los botones no cambian nada aquí. En Home Assistant, sí.",
    loading: "Cargando las partidas…",
    failed: "No se pudieron cargar las partidas. Recarga la página para intentarlo de nuevo.",
    install: "Instalar la integración",
    docs: "Documentación",
  },
};

// The language of ?lang= in the address, else the first of the reader's languages
// that the cards speak, else English.
export function pickLanguage(search, preferred = []) {
  const asked = new URLSearchParams(search).get("lang");
  for (const code of [asked, ...preferred]) {
    const short = String(code ?? "")
      .toLowerCase()
      .split("-")[0];
    if (LANGUAGES.includes(short)) return short;
  }
  return "en";
}

// A date and time as Home Assistant writes it, such as 2026-03-14T19:31:35.650000+00:00.
const MOMENT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

// The value with every date and time in it moved by shift milliseconds.
export function shifted(value, shift) {
  if (typeof value === "string") {
    return MOMENT.test(value) ? new Date(Date.parse(value) + shift).toISOString() : value;
  }
  if (Array.isArray(value)) return value.map((item) => shifted(item, shift));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, shifted(item, shift)]));
  }
  return value;
}

// The steps of the timeline one after another, as the moves at the board came.
export class Replay {
  constructor(
    timeline,
    { now = () => Date.now(), later = (run, wait) => setTimeout(run, wait), cancel = (timer) => clearTimeout(timer) } = {}
  ) {
    this.steps = timeline.steps;
    this.start = Date.parse(timeline.start);
    this.chapters = timeline.chapters.filter((chapter) => chapter.key !== "start");
    this.now = now;
    this.later = later;
    this.cancel = cancel;
    this.speed = 1;
    this.playing = false;
    this.timer = null;
    this.listeners = [];
    this.seek(0);
  }

  onChange(listener) {
    this.listeners.push(listener);
  }

  // The states and answers after the steps up to index, from the first one.
  seek(index) {
    this.states = {};
    this.positions = {};
    for (let step = 0; step <= index; step++) this._apply(step);
    this._schedule();
    this._emit();
  }

  play() {
    this.playing = true;
    this._schedule();
    this._emit();
  }

  pause() {
    this.playing = false;
    this._schedule();
    this._emit();
  }

  toggle() {
    if (this.playing) this.pause();
    else this.play();
  }

  setSpeed(speed) {
    this.speed = speed;
    this._schedule();
    this._emit();
  }

  // The game being played: the last chapter that began at or before this step.
  chapter() {
    const begun = this.chapters.filter((chapter) => chapter.step <= this.index);
    return (begun.at(-1) ?? this.chapters[0]).key;
  }

  progress() {
    return this.steps[this.index].at / this.steps.at(-1).at;
  }

  // A step's states as Home Assistant sends them, with their moments moved to now.
  _apply(index) {
    const step = this.steps[index];
    const shift = this.now() - (this.start + step.at);
    const moment = new Date(this.start + step.at + shift).toISOString();
    const states = { ...this.states };
    for (const [id, value] of Object.entries(step.states)) {
      if (value === null) {
        delete states[id];
        continue;
      }
      states[id] = {
        entity_id: id,
        state: shifted(value[0], shift),
        attributes: shifted(value[1], shift),
        last_changed: moment,
        last_updated: moment,
        context: { id: `demo-${index}`, parent_id: null, user_id: null },
      };
    }
    this.states = states;
    if (step.positions) this.positions = { ...this.positions, ...step.positions };
    this.index = index;
  }

  _schedule() {
    this.cancel(this.timer);
    this.timer = null;
    if (!this.playing) return;
    const next = this.index + 1;
    if (next === this.steps.length) {
      this.timer = this.later(() => this.seek(this.chapters[0].step), AGAIN / this.speed);
      return;
    }
    const wait = Math.min(this.steps[next].at - this.steps[this.index].at, LONGEST_WAIT) / this.speed;
    this.timer = this.later(() => {
      this._apply(next);
      this._schedule();
      this._emit();
    }, wait);
  }

  _emit() {
    for (const listener of this.listeners) listener(this);
  }
}

// What the cards of a board without positions get.
const NO_POSITIONS = { known: false, positions: [], spread: [] };

// Home Assistant as the cards see it: the states of the replay, the registries of the
// recording, the language and theme of the page, and actions that change nothing.
export function hassOf(replay, { entities, devices, language, dark, timeZone, notice }) {
  return {
    states: replay.states,
    entities,
    devices,
    language,
    locale: {
      language,
      number_format: "language",
      time_format: "language",
      date_format: "language",
      first_weekday: "language",
      time_zone: "local",
    },
    config: { time_zone: timeZone, location_name: "Demo", version: "demo" },
    themes: { darkMode: dark, theme: "default", themes: {} },
    selectedTheme: null,
    user: { id: "demo", name: "Demo", is_admin: false, is_owner: false },
    async callService() {
      notice();
    },
    async callWS(message) {
      if (message.type !== "homedarts/positions") {
        throw Object.assign(new Error("Not in the demo"), { code: "not_supported" });
      }
      const player = message.player ?? "";
      return replay.positions[player] ?? { ...NO_POSITIONS, player: player || null };
    },
  };
}

// ha-card and ha-icon come from Home Assistant's frontend; the demo draws its own.
const CARD_STYLE = `
  :host {
    display: block;
    color: var(--primary-text-color);
    background: var(--ha-card-background, var(--card-background-color));
    border: 1px solid var(--divider-color);
    border-radius: var(--ha-card-border-radius, 12px);
    box-shadow: var(--ha-card-box-shadow, none);
  }`;
const ICON_STYLE = `
  :host { display: inline-flex; width: var(--mdc-icon-size, 24px); height: var(--mdc-icon-size, 24px); }
  svg { width: 100%; height: 100%; fill: currentColor; }`;
// A medal, the only icon the cards ask Home Assistant for, by their badges.
const MEDAL =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8a6 6 0 1 1 0 12 6 6 0 0 1 0-12m0 2a4 4 0 1 0 0 8 4 4 0 0 0 0-8M8 2h8l-2 5h-4z"/></svg>';

export function defineHomeElements(window) {
  const elements = { "ha-card": `<style>${CARD_STYLE}</style><slot></slot>`, "ha-icon": `<style>${ICON_STYLE}</style>${MEDAL}` };
  for (const [name, html] of Object.entries(elements)) {
    if (window.customElements.get(name)) continue;
    window.customElements.define(
      name,
      class extends window.HTMLElement {
        connectedCallback() {
          if (this.shadowRoot) return;
          this.attachShadow({ mode: "open" }).innerHTML = html;
        }
      }
    );
  }
}

// The page: the cards in their places, the controls, and the replay that drives them.
export async function boot({ window, load, timeline = "timeline.json" }) {
  const document = window.document;
  const text = (key) => TEXT[language][key];
  let language = pickLanguage(window.location.search, window.navigator.languages ?? []);
  const scheme = window.matchMedia("(prefers-color-scheme: dark)");
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const status = document.getElementById("status");
  const notice = document.getElementById("notice");
  const write = () => {
    document.documentElement.lang = language;
    document.title = text("page_title");
    for (const element of document.querySelectorAll("[data-text]")) element.textContent = text(element.dataset.text);
    for (const element of document.querySelectorAll("[data-label]")) {
      element.setAttribute("aria-label", text(element.dataset.label));
    }
    // The links of the header lead to the pages of the website in this language.
    const folder = WEBSITE_LANGUAGES.includes(language) ? `${language}/` : "";
    for (const element of document.querySelectorAll("[data-page]")) {
      element.setAttribute("href", `../${folder}${element.dataset.page}.html`);
    }
  };
  write();
  status.textContent = text("loading");

  let data;
  try {
    defineHomeElements(window);
    const [cards, response] = await Promise.all([load(), window.fetch(timeline)]);
    if (!response.ok) throw new Error(`${timeline}: ${response.status}`);
    data = await response.json();
    cards.register();
  } catch (error) {
    status.textContent = text("failed");
    throw error;
  }
  status.textContent = "";

  const replay = new Replay(data);
  const cards = [...document.querySelectorAll("[data-card]")].map((slot) => {
    const card = document.createElement(slot.dataset.card);
    card.setConfig({});
    slot.append(card);
    return card;
  });

  // The controls: play and pause, the games, the speed and the language.
  const play = document.getElementById("play");
  const chapters = document.getElementById("chapters");
  const speed = document.getElementById("speed");
  const choice = document.getElementById("language");
  const bar = document.getElementById("progress");
  for (const chapter of replay.chapters) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.text = chapter.key;
    button.dataset.chapter = chapter.key;
    button.addEventListener("click", () => {
      replay.seek(chapter.step);
      replay.play();
    });
    chapters.append(button);
  }
  const option = (label, value) => Object.assign(document.createElement("option"), { textContent: label, value });
  for (const value of SPEEDS) speed.append(option(`${value}×`, String(value)));
  for (const code of LANGUAGES) choice.append(option(TEXT[code].name, code));
  choice.value = language;
  play.addEventListener("click", () => replay.toggle());
  speed.addEventListener("change", () => replay.setSpeed(Number(speed.value)));
  choice.addEventListener("change", () => {
    language = choice.value;
    const address = new URL(window.location.href);
    address.searchParams.set("lang", language);
    window.history.replaceState(null, "", address);
    write();
    show();
  });
  scheme.addEventListener("change", () => show());

  let hidden = null;
  const tell = () => {
    notice.textContent = text("notice");
    notice.hidden = false;
    window.clearTimeout(hidden);
    hidden = window.setTimeout(() => {
      notice.hidden = true;
    }, NOTICE);
  };
  // The details of an entity, which Home Assistant opens on a tap, aren't here either.
  document.addEventListener("hass-more-info", tell);
  const devices = { [data.device.id]: data.device };
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const show = () => {
    const hass = hassOf(replay, { entities: data.entities, devices, language, dark: scheme.matches, timeZone, notice: tell });
    for (const card of cards) card.hass = hass;
    play.dataset.text = replay.playing ? "pause" : "play";
    play.textContent = text(play.dataset.text);
    for (const button of chapters.children) {
      button.setAttribute("aria-current", String(button.dataset.chapter === replay.chapter()));
    }
    speed.value = String(replay.speed);
    bar.value = replay.progress();
  };
  replay.onChange(show);
  write();
  show();
  // A reader who asked for less motion starts the games with the button.
  if (!still) replay.play();
  return replay;
}
