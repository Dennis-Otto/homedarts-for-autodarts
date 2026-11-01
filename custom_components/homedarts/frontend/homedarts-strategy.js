/*
 * All that every page of Home Assistant loads of HomeDarts: the seven cards and the
 * dashboard strategy "custom:homedarts" as small stand-ins, registered at once.
 *
 * Home Assistant loads the module of an integration on every page and on every start of
 * its app, for every user, whether the page shows a darts card or not. homedarts-card.js
 * is more than half a megabyte for the browser to parse, so a page gets it only when
 * something asks for a card: the settings, the state or the place on the page of a card,
 * its form, its stub in the card picker or the automatic dashboard. Until it is there,
 * the stand-in keeps what it is given and answers Home Assistant's questions about its
 * size with what its card answers. Then it becomes that card, as the same element, and
 * every further element of its type becomes one as soon as it is made.
 *
 * This also keeps the strategy in time: Home Assistant waits five seconds for the element
 * of a dashboard strategy and then shows "Timeout waiting for strategy element" until the
 * page loads again. The element is there as soon as Home Assistant's app is, and building
 * the dashboard may take as long as the card module needs.
 */

const STRATEGY_TYPE = "homedarts";
const STRATEGY_ELEMENT = `ll-strategy-dashboard-${STRATEGY_TYPE}`;
// The documentation website, in English and in German under de/.
const DOCUMENTATION = "https://dennis-otto.github.io/homedarts-for-autodarts";
const STRATEGY_DOCS = ["cards.html#automatic-dashboard", "de/cards.html#automatisches-dashboard"];
// The entries of the card picker, with what each card answers to getCardSize and to
// getGridOptions: tests/frontend/strategy-loader.test.mjs compares them with the cards.
const CARDS = [
  { type: "homedarts-card", key: "live", size: 7, columns: 12, docs: ["cards.html#live-card", "de/cards.html#live-karte"] },
  { type: "homedarts-training-card", key: "training", size: 9, columns: 12, docs: ["cards.html#training-card", "de/cards.html#trainingskarte"] },
  { type: "homedarts-status-card", key: "status", size: 7, columns: 12, docs: ["cards.html#board-status-card", "de/cards.html#board-status"] },
  { type: "homedarts-scoreboard-card", key: "scoreboard", size: 8, columns: "full", docs: ["cards.html#scoreboard-card", "de/cards.html#anzeigetafel"] },
  { type: "homedarts-players-card", key: "players", size: 6, columns: 12, docs: ["cards.html#players-card", "de/cards.html#spielerkarte"] },
  { type: "homedarts-doubles-card", key: "doubles", size: 6, columns: 12, docs: ["cards.html#doubles-card", "de/cards.html#doubles-karte"] },
  { type: "homedarts-leaderboard-card", key: "leaderboard", size: 5, columns: 12, docs: ["cards.html#leaderboard-card", "de/cards.html#bestenliste"] },
];
// The texts of the pickers, for pages that have loaded no text of the cards: the copy of
// those in text/ that `python scripts/sync_translations.py` writes here, so change them
// there. tests/test_sync_translations.py fails when the two differ.
const PICKER_TEXT = {
  "de": {
    "picker_live": "HomeDarts",
    "picker_live_description": "Die aktuelle Aufnahme auf einer Live-Dartscheibe mit getroffenen Feldern, Dart-Positionen, dem Übungsspiel, Trainingsstatistik und Steuerung.",
    "picker_training": "HomeDarts-Training",
    "picker_training_description": "Die Trainingssession mit Trefferbild, 3-Dart-Average, Statistik, Bestleistungen und letzten Aufnahmen.",
    "picker_status": "HomeDarts-Board-Status",
    "picker_status_description": "Erkennung, Verbindungen, Kameras, Board-PC und Wartung eines Autodarts-Boards.",
    "picker_scoreboard": "HomeDarts-Anzeigetafel",
    "picker_scoreboard_description": "Eine große Anzeigetafel für Tablet oder Fernseher am Board: X01, Cricket, Party- und Trainingsspiele, die Aufnahme und ein Caller.",
    "picker_players": "HomeDarts-Spieler",
    "picker_players_description": "Statistik und Bestleistungen jedes Spielers mit Namen, direkte Vergleiche und die letzten Matches.",
    "picker_doubles": "HomeDarts-Doubles",
    "picker_doubles_description": "Die Quote jedes Doubles der Scheibe, für alle oder einen Spieler, mit dem Lieblingsdouble.",
    "picker_leaderboard": "HomeDarts-Bestenliste",
    "picker_leaderboard_description": "Rekorde aller Spieler: bester Average, höchster Checkout, meiste 180er, wenigste Darts und mehr, gesamt, in den letzten vier Wochen oder in dieser Woche.",
    "picker_strategy_description": "Live-, Anzeigetafel-, Trainings-, Spieler- und Board-Ansicht für jedes Board, automatisch erstellt."
  },
  "en": {
    "picker_live": "HomeDarts",
    "picker_live_description": "The current visit on a live dartboard with hit beds, dart positions, the practice game, training statistics and controls.",
    "picker_training": "HomeDarts training",
    "picker_training_description": "The training session with a hit heatmap, 3-dart average, statistics, personal bests and recent visits.",
    "picker_status": "HomeDarts board status",
    "picker_status_description": "Detection, connections, cameras, board PC and maintenance controls of an Autodarts board.",
    "picker_scoreboard": "HomeDarts scoreboard",
    "picker_scoreboard_description": "A large scoreboard for a tablet or TV at the board: X01, Cricket, party and training games, the visit and a caller.",
    "picker_players": "HomeDarts players",
    "picker_players_description": "Statistics and personal bests of every named player, head-to-head records and recent matches.",
    "picker_doubles": "HomeDarts doubles",
    "picker_doubles_description": "The hit rate of every double on the board, for everybody or one player, with the favorite double.",
    "picker_leaderboard": "HomeDarts leaderboard",
    "picker_leaderboard_description": "Records across all players: best average, highest checkout, most 180s, fewest darts and more, for all time, the last four weeks or this week.",
    "picker_strategy_description": "Live, scoreboard, training, players and board views for every board, built automatically."
  },
  "es": {
    "picker_live": "HomeDarts",
    "picker_live_description": "La tirada actual en una diana en directo con los segmentos acertados, las posiciones de los dardos, la partida, las estadísticas de entrenamiento y los controles.",
    "picker_training": "Entrenamiento HomeDarts",
    "picker_training_description": "La sesión de entrenamiento con un mapa de calor de aciertos, la media de 3 dardos, estadísticas, récords personales y las últimas tiradas.",
    "picker_status": "Estado de la diana HomeDarts",
    "picker_status_description": "Detección, conexiones, cámaras, PC de la diana y controles de mantenimiento de una diana Autodarts.",
    "picker_scoreboard": "Marcador HomeDarts",
    "picker_scoreboard_description": "Un marcador grande para una tableta o un televisor junto a la diana: X01, Cricket, juegos de fiesta y de entrenamiento, la tirada y un locutor.",
    "picker_players": "Jugadores HomeDarts",
    "picker_players_description": "Estadísticas y récords personales de cada jugador con nombre, enfrentamientos cara a cara y últimos partidos.",
    "picker_doubles": "Dobles HomeDarts",
    "picker_doubles_description": "El porcentaje de aciertos de cada doble de la diana, para todos o para un jugador, con el doble favorito.",
    "picker_leaderboard": "Clasificación HomeDarts",
    "picker_leaderboard_description": "Los récords de todos los jugadores (mejor media, cierre más alto, más 180, menos dardos y otros) en el histórico, las últimas cuatro semanas o esta semana.",
    "picker_strategy_description": "Vistas en directo, de marcador, de entrenamiento, de jugadores y de la diana, creadas automáticamente para cada diana."
  },
  "fr": {
    "picker_live": "HomeDarts",
    "picker_live_description": "La volée en cours sur une cible en direct, avec les zones touchées, la position des fléchettes, la partie, les statistiques d'entraînement et les commandes.",
    "picker_training": "Entraînement HomeDarts",
    "picker_training_description": "La session d'entraînement avec la carte de chaleur des touches, la moyenne 3 fléchettes, les statistiques, les records personnels et les dernières volées.",
    "picker_status": "État de la cible HomeDarts",
    "picker_status_description": "Détection, connexions, caméras, PC de la cible et commandes de maintenance d'une cible Autodarts.",
    "picker_scoreboard": "Tableau des scores HomeDarts",
    "picker_scoreboard_description": "Un grand tableau des scores pour une tablette ou une télévision près de la cible\u00a0: X01, Cricket, jeux de soirée et d'entraînement, la volée et un annonceur.",
    "picker_players": "Joueurs HomeDarts",
    "picker_players_description": "Statistiques et records personnels de chaque joueur nommé, face-à-face et derniers matchs.",
    "picker_doubles": "Doubles HomeDarts",
    "picker_doubles_description": "Le taux de réussite sur chaque double de la cible, pour tous les joueurs ou un seul, avec le double préféré.",
    "picker_leaderboard": "Classement HomeDarts",
    "picker_leaderboard_description": "Les records de tous les joueurs\u00a0: meilleure moyenne, meilleur finish, le plus de 180, le moins de fléchettes et plus encore, depuis toujours, sur les quatre dernières semaines ou cette semaine.",
    "picker_strategy_description": "Vues En direct, Tableau des scores, Entraînement, Joueurs et Cible pour chaque cible, créées automatiquement."
  },
  "nl": {
    "picker_live": "HomeDarts",
    "picker_live_description": "De huidige beurt op een live dartbord met geraakte vakken, dartposities, het oefenspel, trainingsstatistieken en bediening.",
    "picker_training": "HomeDarts-training",
    "picker_training_description": "De trainingssessie met een heatmap van de treffers, 3-dart-gemiddelde, statistieken, persoonlijke records en recente beurten.",
    "picker_status": "HomeDarts-bordstatus",
    "picker_status_description": "Detectie, verbindingen, camera's, bord-pc en onderhoudsbediening van een Autodarts-bord.",
    "picker_scoreboard": "HomeDarts-scorebord",
    "picker_scoreboard_description": "Een groot scorebord voor een tablet of tv bij het bord: X01, Cricket, party- en trainingsspellen, de beurt en een caller.",
    "picker_players": "HomeDarts-spelers",
    "picker_players_description": "Statistieken en persoonlijke records van elke speler met een naam, onderlinge duels en recente wedstrijden.",
    "picker_doubles": "HomeDarts-dubbels",
    "picker_doubles_description": "Het trefferpercentage van elke dubbel op het bord, voor iedereen of één speler, met de favoriete dubbel.",
    "picker_leaderboard": "HomeDarts-ranglijst",
    "picker_leaderboard_description": "Records van alle spelers: beste gemiddelde, hoogste uitgooi, meeste 180's, minste darts en meer, van aller tijden, van de laatste vier weken of van deze week.",
    "picker_strategy_description": "Live-, scorebord-, trainings-, spelers- en bordweergaven voor elk bord, automatisch opgebouwd."
  }
};

// homedarts-card.js beside a module: in the folder of the same version, as Home Assistant
// loads this one, or with the same query, so that the import finds a module that a
// resource in YAML is loading already.
const cardModule = (url) => new URL(`homedarts-card.js${new URL(url).search}`, url).href;
const CARD_MODULE = cardModule(import.meta.url);

// The element that the class of its card is being made for.
let becoming = null;

// The base class of a card: where a card would make a new element, it gets the one that is
// there. A class may hand its subclasses any object as `this` by returning it from its
// constructor, as polyfills of custom elements do for an element they upgrade. So the
// constructors of the card run on the stand-in as if the browser had upgraded it. It extends
// the stand-in, so the element stays an instance of the class defined for its name.
function becomingBase(StandIn) {
  return class extends StandIn {
    constructor() {
      return becoming;
    }
  };
}

function become(element, Card) {
  Object.setPrototypeOf(element, Card.prototype);
  becoming = element;
  new Card();
}

// homedarts-card.js, once it has loaded.
let cards = null;
let loading = null;

// homedarts-card.js; a failed load is tried again by the next call.
function loadCards(load = () => import(CARD_MODULE)) {
  loading ??= load().then(
    (module) => {
      // Defines what has no stand-in, the editor of the strategy, before anyone asks for it.
      module.register();
      cards = module;
      return module;
    },
    (error) => {
      loading = null;
      throw error;
    }
  );
  return loading;
}

// What each stand-in keeps until it becomes its card.
const waiting = new WeakMap();

// A stand-in becomes its card. What Home Assistant set on the element while it waited, such
// as preview, comes off first, as it would hide the accessors of the card. The card then
// gets everything in the order in which Home Assistant gives it to a new card.
function upgrade(element, Card, kept) {
  const properties = Object.entries(element);
  for (const [name] of properties) delete element[name];
  become(element, Card);
  try {
    if ("config" in kept) element.setConfig(kept.config);
  } catch {
    // Home Assistant builds the card anew, and shows what setConfig throws then.
    element.dispatchEvent(new CustomEvent("ll-rebuild", { bubbles: true, composed: true }));
    return;
  }
  if ("hass" in kept) element.hass = kept.hass;
  for (const [name, value] of properties) element[name] = value;
  if (element.isConnected) element.connectedCallback();
}

function cardStandIn(Base, { type, size, columns }) {
  // The class of the card, made once from the module.
  let Card = null;
  const cardOf = (module) => (Card ??= module.createElements(becomingBase(StandIn))[type]);

  // Keeps what the stand-in is given and loads the card module, once; after a failed load,
  // the next update of Home Assistant tries again.
  function wake(element, given = {}) {
    const kept = waiting.get(element) ?? {};
    waiting.set(element, Object.assign(kept, given));
    if (kept.woken) return;
    kept.woken = true;
    loadCards().then(
      (module) => upgrade(element, cardOf(module), kept),
      () => {
        kept.woken = false;
      }
    );
  }

  class StandIn extends Base {
    static async getStubConfig(...args) {
      return cardOf(await loadCards()).getStubConfig(...args);
    }

    static async getConfigForm() {
      return cardOf(await loadCards()).getConfigForm();
    }

    constructor() {
      super();
      if (cards) become(this, cardOf(cards));
    }

    setConfig(config) {
      wake(this, { config });
    }

    set hass(hass) {
      wake(this, { hass });
    }

    getCardSize() {
      return size;
    }

    getGridOptions() {
      return { columns, min_columns: 6 };
    }

    // A browser reads these two callbacks once, from the class that is defined, so it goes
    // on calling them on an element that has become its card.
    connectedCallback() {
      const own = Object.getPrototypeOf(this);
      if (own === StandIn.prototype) wake(this);
      else own.connectedCallback.call(this);
    }

    disconnectedCallback() {
      const own = Object.getPrototypeOf(this);
      if (own !== StandIn.prototype) own.disconnectedCallback.call(this);
    }
  }
  return StandIn;
}

// The strategy of homedarts-card.js.
const cardStrategy = async () => (await loadCards()).createElements(window.HTMLElement)[STRATEGY_ELEMENT];

function strategyElement(Base) {
  return class AutodartsDashboardStrategy extends Base {
    static async generate(config, hass) {
      return (await cardStrategy()).generate(config, hass);
    }

    static async getConfigElement() {
      return (await cardStrategy()).getConfigElement();
    }
  };
}

// The language that Home Assistant sets on the page, also in a regional variant such as
// es-419; a language without card texts reads English.
function pageLanguage() {
  const own = document.documentElement.lang.toLowerCase();
  return Object.keys(PICKER_TEXT).find((lang) => own === lang || own.startsWith(`${lang}-`)) ?? "en";
}

const pageText = (key) => PICKER_TEXT[pageLanguage()][key];
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

// Home Assistant swaps in a scoped custom element registry once its app element is
// defined; an element defined before stays invisible to dashboards (see frontendReady
// in homedarts-card.js, which also defines the elements when this module is missing).
function register() {
  const registry = window.customElements;
  if (!registry.get(STRATEGY_ELEMENT)) registry.define(STRATEGY_ELEMENT, strategyElement(window.HTMLElement));
  for (const card of CARDS) {
    if (!registry.get(card.type)) registry.define(card.type, cardStandIn(window.HTMLElement, card));
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

// Home Assistant's app element, or hc-main of the receiver of Home Assistant Cast, which
// shows dashboards on a TV and loads this module as a dashboard resource once it runs.
const appReady = (registry) => Promise.race(["home-assistant", "hc-main"].map((name) => registry.whenDefined(name)));

if (globalThis.window?.customElements) appReady(window.customElements).then(register);

export { CARD_MODULE, CARDS, appReady, cardModule, loadCards, register, strategyElement };
