// The translation bot of scripts/translations.mjs: which texts of a language it finds
// missing or stale in the history of a temporary git repository, the issue it writes
// for each language, and how it opens, updates and closes the issues on GitHub.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  BOT,
  CARD,
  LABELS,
  TEXTS,
  TRANSLATIONS,
  cardFile,
  cardLines,
  cardTexts,
  checks,
  client,
  closing,
  findings,
  flatten,
  jsonLines,
  languageName,
  main,
  moduleTexts,
  openIssues,
  render,
  sync,
} from "../../scripts/translations.mjs";

const SCRIPT = fileURLToPath(new URL("../../scripts/translations.mjs", import.meta.url));
const TEMPORARY = mkdtempSync(join(tmpdir(), "translation-bot-"));
after(() => rmSync(TEMPORARY, { recursive: true, force: true }));

// Git as on a new machine, without the settings of whoever runs the tests, such as
// signed commits or hooks; the bot and its child processes inherit it.
writeFileSync(join(TEMPORARY, "gitconfig"), "");
// Nor the repository of a Git hook or a container that runs the tests, such as GIT_DIR:
// the repositories of the tests would write into it.
for (const name of execFileSync("git", ["rev-parse", "--local-env-vars"], { encoding: "utf8" }).split(/\s+/)) {
  if (name) delete process.env[name];
}
Object.assign(process.env, {
  GIT_CONFIG_GLOBAL: join(TEMPORARY, "gitconfig"),
  GIT_CONFIG_NOSYSTEM: "1",
  GIT_AUTHOR_NAME: "Translator",
  GIT_AUTHOR_EMAIL: "translator@example.com",
  GIT_COMMITTER_NAME: "Translator",
  GIT_COMMITTER_EMAIL: "translator@example.com",
});

const LINKS = {
  blob: "https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main",
  edit: "https://github.com/Dennis-Otto/homedarts-for-autodarts/edit/main",
};
const file = (language) => `${TRANSLATIONS}/${language}.json`;
const json = (tree) => `${JSON.stringify(tree, null, 2)}\n`;

// The texts of a language as frontend/text/<language>.js has them: JSON after
// export default, with comments on lines of their own.
function textModule(texts) {
  const entries = Object.entries(texts).map(([key, value]) => `  ${JSON.stringify(key)}: ${JSON.stringify(value)}`);
  return ["// The texts of the cards.", "export default {", "  // Status", entries.join(",\n"), "};", ""].join("\n");
}

// A card module as homedarts-card.js wrote it before its texts moved: TEXT between
// other code.
function card(texts) {
  return [
    "// The cards.",
    'const STYLES = { ready: "green" };',
    "",
    "const TEXT = {",
    ...Object.entries(texts).flatMap(([language, entries]) => [
      `  ${language}: {`,
      "    // Status",
      ...Object.entries(entries).map(([key, value]) => `    ${key}: ${JSON.stringify(value)},`),
      "  },",
    ]),
    "};",
    "",
    "const LANGUAGES = Object.keys(TEXT);",
    "",
  ].join("\n");
}

let repositories = 0;
class Repository {
  constructor() {
    repositories += 1;
    this.dir = join(TEMPORARY, `repository-${repositories}`);
    mkdirSync(this.dir);
    this.git("init", "-q", "-b", "main");
  }

  git(...args) {
    return execFileSync("git", args, { cwd: this.dir, encoding: "utf8" });
  }

  commit(message, files = {}) {
    for (const [path, content] of Object.entries(files)) {
      mkdirSync(dirname(join(this.dir, path)), { recursive: true });
      writeFileSync(join(this.dir, path), content);
    }
    this.git("add", "-A");
    this.git("commit", "-q", "--allow-empty", "-m", message);
    return this.git("rev-parse", "HEAD").trim();
  }
}

const ENGLISH = { config: { title: "Board", text: "Hello {name}" } };
const GERMAN = { config: { title: "Brett", text: "Hallo {name}" } };
const FRENCH = { config: { title: "Cible", text: "Bonjour {name}" } };
const CARD_TEXT = {
  en: { ready: "Ready", stop: "Stop" },
  de: { ready: "Bereit", stop: "Stopp" },
  fr: { ready: "Prêt", stop: "Arrêter" },
};

// Five languages' worth of history: English changes, translations that follow or not.
function history() {
  const repository = new Repository();
  const texts = structuredClone(CARD_TEXT);
  repository.commit("feat: the first texts", {
    [file("en")]: json(ENGLISH),
    [file("de")]: json(GERMAN),
    [file("fr")]: json(FRENCH),
    [`${TRANSLATIONS}/README.txt`]: "Not a translation.\n",
    [CARD]: card(texts),
  });
  // English changes alone: German follows a commit later, French never.
  const english = structuredClone(ENGLISH);
  english.config.title = "Dartboard";
  repository.commit("fix: say dartboard", { [file("en")]: json(english) });
  repository.commit("fix(i18n): German follows", {
    [file("de")]: json({ config: { ...GERMAN.config, title: "Dartscheibe" } }),
  });
  // English and German change in the same commit; French stays.
  texts.en.stop = "Stop detection";
  texts.de.stop = "Erkennung stoppen";
  repository.commit("fix(cards): name what stops", { [CARD]: card(texts) });
  // Only the case of English changes, and a text changes and changes back.
  texts.en.ready = "READY";
  repository.commit("style: shout", { [CARD]: card(texts) });
  english.config.text = "Hi {name}";
  repository.commit("fix: greet shorter", { [file("en")]: json(english) });
  english.config.text = "Hello {name}";
  repository.commit("revert: greet as before", { [file("en")]: json(english) });
  // A new English text that the other languages lack.
  english.config.added = "New";
  repository.commit("feat: a new text", { [file("en")]: json(english) });
  return repository;
}

const summary = (results) =>
  Object.fromEntries(results.map(({ language, items }) => [language, items.map((item) => `${item.state} ${item.key}`)]));

test("a text is stale when its English text changed after the language's, and missing when it lacks", () => {
  const repository = history();
  const results = findings(repository.dir);
  assert.deepEqual(summary(results), {
    de: ["missing config.added"],
    fr: ["outdated config.title", "missing config.added", "outdated stop"],
  });
  const [title, added, stop] = results[1].items;
  assert.deepEqual(title, {
    source: "integration",
    path: file("fr"),
    key: "config.title",
    english: "Dartboard",
    translation: "Cible",
    line: 3,
    state: "outdated",
    previous: "Board",
  });
  assert.deepEqual(added, {
    source: "integration",
    path: file("fr"),
    key: "config.added",
    english: "New",
    translation: undefined,
    line: undefined,
    state: "missing",
    previous: undefined,
  });
  assert.equal(stop.source, "cards");
  assert.equal(stop.path, CARD);
  assert.equal(stop.previous, "Stop");
  assert.equal(stop.line, 18);
  // An older commit has fewer findings: the history ends where the ref is.
  const first = repository.git("rev-list", "--max-parents=0", "HEAD").trim();
  assert.deepEqual(summary(findings(repository.dir, first)), { de: [], fr: [] });
});

test("a merged branch counts as one commit, at its merge", () => {
  const repository = history();
  repository.git("checkout", "-q", "-b", "feature");
  // On the branch French changes first and English after it; merged, they are one change.
  repository.commit("fix(i18n): French", {
    [file("fr")]: json({ config: { title: "Cible de fléchettes", text: "Bonjour {name}", added: "Nouveau" } }),
  });
  const english = { config: { title: "Dartboard", text: "Hello {name}", added: "New text" } };
  repository.commit("fix: a longer text", { [file("en")]: json(english) });
  repository.git("checkout", "-q", "main");
  repository.commit("docs: meanwhile on main");
  repository.git("merge", "-q", "--no-ff", "-m", "Merge the branch", "feature");
  const [german, french] = findings(repository.dir);
  assert.deepEqual(
    german.items.map((item) => [item.state, item.key]),
    [["missing", "config.added"]]
  );
  assert.deepEqual(
    french.items.map((item) => [item.state, item.key]),
    [["outdated", "stop"]]
  );
});

test("the history of a card text goes on when TEXT moves into a file per language", () => {
  const repository = history();
  const before = cardTexts(readFileSync(join(repository.dir, CARD), "utf8"));
  repository.commit("refactor(cards): one file per language", {
    [CARD]: "// The cards.\nconst TEXT = { en, de, fr };\n",
    ...Object.fromEntries(Object.entries(before).map(([language, texts]) => [cardFile(language), textModule(texts)])),
  });
  // The move changes nothing: the French text that was outdated before still is.
  const moved = findings(repository.dir);
  assert.deepEqual(summary(moved), {
    de: ["missing config.added"],
    fr: ["outdated config.title", "missing config.added", "outdated stop"],
  });
  const stop = moved[1].items[2];
  assert.equal(stop.path, cardFile("fr"));
  assert.equal(stop.line, 5);
  assert.equal(stop.previous, "Stop");
  // After the move, English changes in its file and German follows in its own.
  repository.commit("fix(cards): say what to do", { [cardFile("en")]: textModule({ ...before.en, ready: "Ready to throw" }) });
  repository.commit("fix(i18n): German follows", { [cardFile("de")]: textModule({ ...before.de, ready: "Bereit zum Werfen" }) });
  const [german, french] = findings(repository.dir);
  assert.deepEqual(summary([german, french]), {
    de: ["missing config.added"],
    fr: ["outdated config.title", "missing config.added", "outdated ready", "outdated stop"],
  });
  assert.deepEqual(french.items[2], {
    source: "cards",
    path: cardFile("fr"),
    key: "ready",
    english: "Ready to throw",
    translation: "Prêt",
    line: 4,
    state: "outdated",
    previous: "Ready",
  });
});

test("languages come from the files of the card texts too, and a missing file is where its texts go", () => {
  const repository = new Repository();
  repository.commit("feat: texts", {
    [file("en")]: json({ title: "Board" }),
    [file("de")]: json({ title: "Brett" }),
    [CARD]: "const TEXT = { en, nl };\n",
    [cardFile("en")]: textModule({ ready: "Ready" }),
    [cardFile("nl")]: textModule({ ready: "Klaar" }),
    [`${TEXTS}/README.md`]: "Not a language.\n",
  });
  const [german, dutch] = findings(repository.dir);
  assert.deepEqual(german.items, [
    {
      source: "cards",
      path: cardFile("de"),
      key: "ready",
      english: "Ready",
      translation: undefined,
      line: undefined,
      state: "missing",
      previous: undefined,
    },
  ]);
  assert.deepEqual(
    dutch.items.map((item) => [item.source, item.state, item.key]),
    [["integration", "missing", "title"]]
  );
});

test("a line Translations-checked counts the texts it names as up to date", () => {
  const repository = history();
  repository.commit(
    [
      "fix: nothing to translate",
      "",
      "The French title is still right.",
      "",
      "Translations-checked: fr config.title",
      "translations-checked: de, xx",
      "Translation-checked: it stop",
      "Translations-checked:",
    ].join("\r\n")
  );
  assert.deepEqual(summary(findings(repository.dir)), {
    de: ["missing config.added"],
    fr: ["missing config.added", "outdated stop"],
  });
  // Without a key, every text of the languages counts; a missing one stays missing.
  repository.commit("fix(i18n): check French\n\nTranslations-checked: fr\n");
  assert.deepEqual(summary(findings(repository.dir)), {
    de: ["missing config.added"],
    fr: ["missing config.added"],
  });
});

test("checks name languages first, then keys, separated by spaces or commas", () => {
  const chain = [
    { message: "feat: a\n\nTranslations-checked: de, fr status_ready, stop\n" },
    { message: "Translations-checked: nl\nTranslations-checked: en de\nnot Translations-checked: de" },
  ];
  assert.deepEqual(checks(chain, ["de", "fr", "nl"]), [
    { index: 0, languages: new Set(["de", "fr"]), keys: new Set(["status_ready", "stop"]) },
    { index: 1, languages: new Set(["nl"]), keys: null },
  ]);
});

test("a line of checks that GitHub wrapped at 72 characters goes on in the lines of names after it", () => {
  // As GitHub writes the description of a pull request into the commit of its squash.
  const wrapped = [
    "docs: point native speakers to the translation issues (#159)",
    "",
    "Translations-checked: de config.step.cloud.data_description.client_id",
    "config.progress.wait_for_device entity.sensor.favourite_double.name",
    "heatmap_label",
    "",
    // A wrapped line of other words ends the names, though its first word didn't fit.
    "Translations-checked: fr config.step.cloud.data_description.client_id",
    "Generated-by: [Claude Code](https://claude.com/claude-code)",
    // A short line was not wrapped: the names below it are words of their own.
    "Translations-checked: nl status_ready",
    "of dart points",
  ].join("\r\n");
  assert.deepEqual(checks([{ message: wrapped }], ["de", "fr", "nl"]), [
    {
      index: 0,
      languages: new Set(["de"]),
      keys: new Set([
        "config.step.cloud.data_description.client_id",
        "config.progress.wait_for_device",
        "entity.sensor.favourite_double.name",
        "heatmap_label",
      ]),
    },
    { index: 0, languages: new Set(["fr"]), keys: new Set(["config.step.cloud.data_description.client_id"]) },
    { index: 0, languages: new Set(["nl"]), keys: new Set(["status_ready"]) },
  ]);
});

test("languages come from the translation files and from TEXT, and a translation may be older than its English text", () => {
  const repository = new Repository();
  // Spanish has a text before English has it; Dutch has no translation file.
  repository.commit("feat: texts", {
    [file("en")]: json({ title: "Board" }),
    [file("es")]: json({ title: "Diana", later: "Más tarde" }),
    [CARD]: card({ en: { ready: "Ready" }, nl: { ready: "Klaar" } }),
  });
  repository.commit("feat: English catches up", { [file("en")]: json({ title: "Board", later: "Later" }) });
  const [spanish, dutch] = findings(repository.dir);
  assert.equal(spanish.language, "es");
  assert.deepEqual(spanish.items, [
    {
      source: "integration",
      path: file("es"),
      key: "later",
      english: "Later",
      translation: "Más tarde",
      line: 3,
      state: "outdated",
      previous: undefined,
    },
    {
      source: "cards",
      path: CARD,
      key: "ready",
      english: "Ready",
      translation: undefined,
      line: undefined,
      state: "missing",
      previous: undefined,
    },
  ]);
  assert.equal(dutch.language, "nl");
  assert.deepEqual(
    dutch.items.map((item) => [item.source, item.state, item.key]),
    [
      ["integration", "missing", "title"],
      ["integration", "missing", "later"],
    ]
  );
});

test("the bot stops when it no longer finds the English texts", () => {
  const repository = new Repository();
  repository.commit("feat: texts", { [file("en")]: json({ title: "Board" }), [file("de")]: json({ title: "Brett" }) });
  assert.throws(() => findings(repository.dir), new RegExp(`No English texts in ${cardFile("en")}`));
  const empty = new Repository();
  empty.commit("feat: no texts yet", { [CARD]: card({ en: { ready: "Ready" } }) });
  assert.throws(() => findings(empty.dir), new RegExp(`No English texts in ${TRANSLATIONS}/en.json`));
});

test("a file of card texts is read as JSON, with comments on lines of their own", () => {
  const source = [
    "// The texts.",
    "export default {",
    "  // Status",
    '  "hello": "Hello {name} }",',
    "    // A comment may be indented.",
    '  "address": "https://example.com/a // b",',
    '  "ready": "Prêt\\u00a0!"',
    "};",
    "",
  ].join("\n");
  assert.deepEqual(moduleTexts(source), { hello: "Hello {name} }", address: "https://example.com/a // b", ready: "Prêt\u00a0!" });
  assert.deepEqual([...jsonLines(source)], [["hello", 4], ["address", 6], ["ready", 7]]);
  // A comma after the last text is no JSON; the consistency tests name the file.
  assert.throws(() => moduleTexts('export default {\n  "a": "A",\n};\n'), { name: "SyntaxError" });
  // The card module of today puts the files together and has no texts of its own.
  assert.deepEqual(cardTexts("const TEXT = { en, de };\nconst DEFAULTS = {\n  layout: 1,\n};\n"), {});
});

test("TEXT of an earlier card module is read in isolation, whatever its texts hold", () => {
  const source = [
    "const TEXT = {",
    "  en: {",
    "    // Placeholders in braces and a brace of its own",
    '    hello: "Hello {name} }",',
    "    long:",
    '      "A text on a line of its own",',
    "    quoted: 'Single \"quotes\"',",
    "    template: `Back${'ticks'}`,",
    "    count: 3,",
    "    nothing: null,",
    "    process: typeof process,",
    "  },",
    "  de: {},",
    "};",
    "const AFTER = { en: 1 };",
  ].join("\n");
  assert.deepEqual(cardTexts(source), {
    en: {
      hello: "Hello {name} }",
      long: "A text on a line of its own",
      quoted: 'Single "quotes"',
      template: "Backticks",
      process: "undefined",
    },
    de: {},
  });
  assert.deepEqual(cardTexts("const OTHER = {};\n"), {});
  assert.throws(() => cardTexts("const TEXT = {\n  en: {\n"), { name: "SyntaxError" });
});

test("texts are flattened to their paths, and their lines are found for links", () => {
  assert.deepEqual(flatten({ a: { b: "B", c: { d: "D" } }, e: "E", f: 1, g: null }), { "a.b": "B", "a.c.d": "D", e: "E" });
  const content = json({ config: { step: { title: "T", 'say "hi"': "Hi" } }, other: { title: "O" } });
  assert.deepEqual(
    [...jsonLines(content)],
    [
      ["config.step.title", 4],
      ['config.step.say "hi"', 5],
      ["other.title", 9],
    ]
  );
  const source = card({ en: { ready: "Ready", stop: "Stop" }, de: { ready: "Bereit" } });
  assert.deepEqual([...cardLines(source, "de")], [["ready", 12]]);
  assert.deepEqual([...cardLines(source, "en")], [["ready", 7], ["stop", 8]]);
  assert.deepEqual([...cardLines(source, "fr")], []);
});

test("languages have English names, also those without words of the bot", () => {
  assert.equal(languageName("fr"), "French");
  assert.equal(languageName("it"), "Italian");
  assert.equal(languageName("pt-BR"), "Brazilian Portuguese");
  assert.equal(languageName("1"), "1");
});

const item = (key, fields = {}) => ({
  source: "integration",
  path: file("fr"),
  key,
  english: `English ${key}`,
  translation: `Français ${key}`,
  line: 7,
  state: "outdated",
  previous: `Old ${key}`,
  ...fields,
});

test("an issue names each text with its English text then and now and its translation", () => {
  const { title, body } = render(
    {
      language: "fr",
      items: [
        item("config.title"),
        item("config.added", { state: "missing", translation: undefined, previous: undefined, line: undefined }),
        item("config.code", { english: "Run ```yaml``` or `x`", previous: undefined }),
        item("stop", { source: "cards", path: cardFile("fr"), line: 20 }),
      ],
    },
    LINKS
  );
  assert.equal(title, "Translation: French needs 4 updates · Français\u00a0: 4 textes à mettre à jour");
  assert.ok(body.startsWith("<!-- translation-bot: fr -->\n\n**Français\u00a0:** Bonjour\u00a0!"));
  assert.match(body, /\*\*English:\*\* Hello! 4 French texts .* are missing or older than the English original: 1 missing, 3 outdated\./);
  assert.ok(body.includes(`### Integration: \`${file("fr")}\``));
  assert.ok(
    body.includes(
      `#### [\`config.title\`](${LINKS.blob}/${file("fr")}#L7) · outdated\n\nEnglish now:\n\`\`\`text\nEnglish config.title\n\`\`\`\n\n` +
        "English when last translated:\n```text\nOld config.title\n```\n\nFrench now:\n```text\nFrançais config.title\n```"
    )
  );
  assert.ok(body.includes("#### `config.added` · missing\n\nEnglish now:\n```text\nEnglish config.added\n```\n\nFrench: missing"));
  // A fence longer than any backticks of the text keeps it whole.
  assert.ok(body.includes("English now:\n````text\nRun ```yaml``` or `x`\n````\n\nFrench now:"));
  assert.ok(body.includes(`### Cards: \`${cardFile("fr")}\`\n\n#### [\`stop\`](${LINKS.blob}/${cardFile("fr")}#L20)`));
  assert.ok(body.includes(`[\`${file("fr")}\`](${LINKS.edit}/${file("fr")})`));
  assert.ok(body.includes(`[\`${cardFile("fr")}\`](${LINKS.edit}/${cardFile("fr")}) for the texts of the dashboard cards\n`));
  assert.ok(body.includes("the comma after them where there is one"));
  assert.ok(body.includes("`fix(i18n): update the French texts`"));
  assert.ok(body.includes(`[changelog](${LINKS.blob}/CHANGELOG.md) thanks you`));
  assert.ok(body.includes("`Translations-checked: fr config.title`"));
  assert.ok(body.includes(`[translation guide](${LINKS.blob}/docs/development.md#translations)`));
  assert.ok(body.endsWith("once every French text is up to date.\n"));
});

test("an issue speaks the language it is for, in the singular too", () => {
  const titles = ["de", "es", "fr", "nl", "it"].map((language) => render({ language, items: [item("a")] }, LINKS).title);
  assert.deepEqual(titles, [
    "Translation: German needs 1 update · Deutsch: 1 Text zu aktualisieren",
    "Translation: Spanish needs 1 update · Español: 1 texto por actualizar",
    "Translation: French needs 1 update · Français\u00a0: 1 texte à mettre à jour",
    "Translation: Dutch needs 1 update · Nederlands: 1 tekst bij te werken",
    "Translation: Italian needs 1 update",
  ]);
  const two = ["de", "es", "nl"].map((language) => render({ language, items: [item("a"), item("b")] }, LINKS).title);
  assert.deepEqual(two, [
    "Translation: German needs 2 updates · Deutsch: 2 Texte zu aktualisieren",
    "Translation: Spanish needs 2 updates · Español: 2 textos por actualizar",
    "Translation: Dutch needs 2 updates · Nederlands: 2 teksten bij te werken",
  ]);
  const { body } = render({ language: "it", items: [item("a", { state: "missing", translation: undefined })] }, LINKS);
  assert.ok(body.startsWith("<!-- translation-bot: it -->\n\n**English:** Hello! 1 Italian text of HomeDarts"));
  assert.ok(body.includes("1 Italian text of HomeDarts for Autodarts is missing. If you speak Italian"));
  assert.ok(body.includes("Italian: missing"));
  assert.ok(!body.includes("dashboard cards"));
  assert.ok(render({ language: "nl", items: [item("a", { source: "cards" })] }, LINKS).body.includes("Spreek je Nederlands?"));
  const german = render({ language: "de", items: [item("a"), item("b")] }, LINKS).body;
  assert.ok(german.includes("kannst du helfen"));
  assert.ok(german.includes("2 German texts of HomeDarts for Autodarts are older than the English original. If"));
  assert.ok(render({ language: "es", items: [item("a")] }, LINKS).body.includes("puedes ayudar"));
});

test("a long issue stays below GitHub's limit and lists the rest by key", () => {
  const items = Array.from({ length: 2000 }, (_, index) => item(`config.section_${index}.description`));
  const { body } = render({ language: "fr", items }, LINKS);
  assert.ok(body.length < 65_536, body.length);
  const shown = body.match(/^#### /gm).length;
  assert.ok(shown > 50 && shown < 2000, shown);
  const rest = body.match(/^And (\d+) more texts, too many to show here: (.*)$/m);
  assert.equal(Number(rest[1]), 2000 - shown);
  assert.ok(rest[2].startsWith(`\`config.section_${shown}.description\`, `));
  assert.ok(rest[2].endsWith(", …"));
  // A few more fit in full.
  const few = render({ language: "fr", items: items.slice(0, shown + 3) }, LINKS).body;
  assert.match(few, /^And 3 more texts, too many to show here: `[^…]*`$/m);
});

test("the comment that closes an issue thanks the helpers in both languages", () => {
  assert.equal(
    closing("de"),
    "**Deutsch:** Alle deutschen Texte sind jetzt aktuell. Danke an alle, die geholfen haben!\n\n" +
      "**English:** Every German text is up to date now. Thank you to everyone who helped!\n"
  );
  assert.equal(closing("it"), "**English:** Every Italian text is up to date now. Thank you to everyone who helped!\n");
});

// A GitHub that answers from a list of issues and records every request.
function fakeGitHub(issues = [], { labels = LABELS } = {}) {
  const requests = [];
  let next = 100;
  const fetch = async (url, init) => {
    const body = init.body === undefined ? undefined : JSON.parse(init.body);
    requests.push({ method: init.method, url, body, headers: init.headers });
    const path = new URL(url).pathname + new URL(url).search;
    let answer = {};
    if (init.method === "GET") {
      const page = Number(new URL(url).searchParams.get("page"));
      answer = issues.slice((page - 1) * 100, page * 100);
    } else if (path.endsWith("/issues") && init.method === "POST") {
      next += 1;
      answer = { number: next, labels: labels.map((name) => ({ name })) };
    }
    if (path.includes("/fail")) return { ok: false, status: 422, text: async () => "Validation Failed" };
    return { ok: true, status: 200, json: async () => answer };
  };
  return { fetch, requests };
}

const request = (fetch) =>
  client({ token: "token", repository: "Dennis-Otto/homedarts-for-autodarts", api: "https://api.github.com", fetch });
const botIssue = (number, language, fields = {}) => ({
  number,
  title: `Old title ${language}`,
  body: `<!-- translation-bot: ${language} -->\n\nOld`,
  user: { login: BOT },
  ...fields,
});

test("requests to GitHub carry the token and the API version, and a refusal stops the bot", async () => {
  const github = fakeGitHub();
  const answer = await request(github.fetch)("POST", "/issues", { title: "T" });
  assert.deepEqual(answer, { number: 101, labels: LABELS.map((name) => ({ name })) });
  await request(github.fetch)("GET", "/issues?page=1");
  assert.deepEqual(github.requests[0], {
    method: "POST",
    url: "https://api.github.com/repos/Dennis-Otto/homedarts-for-autodarts/issues",
    body: { title: "T" },
    headers: {
      accept: "application/vnd.github+json",
      authorization: "Bearer token",
      "content-type": "application/json",
      "x-github-api-version": "2022-11-28",
    },
  });
  assert.equal(github.requests[1].body, undefined);
  await assert.rejects(request(github.fetch)("PATCH", "/fail", {}), /GitHub answered PATCH \/fail with 422: Validation Failed/);
});

test("the bot finds its own open issues on every page, by the language in their marker", async () => {
  const others = Array.from({ length: 97 }, (_, index) => ({ number: index + 1, body: "Something else" }));
  const issues = [
    ...others,
    { number: 98, body: null },
    { number: 99, body: "<!-- translation-bot: fr -->", pull_request: {} },
    { number: 100, body: "Mentions <!-- translation-bot: fr --> later" },
    botIssue(101, "fr"),
    botIssue(102, "fr"),
    botIssue(103, "nl"),
  ];
  const github = fakeGitHub(issues);
  const found = await openIssues(request(github.fetch));
  assert.deepEqual(
    [...found].map(([language, issue]) => [language, issue.number]),
    [
      ["fr", 101],
      ["nl", 103],
    ]
  );
  assert.deepEqual(
    github.requests.map((sent) => sent.url.split("/repos/Dennis-Otto/homedarts-for-autodarts")[1]),
    [
      "/issues?state=open&creator=github-actions%5Bbot%5D&per_page=100&page=1",
      "/issues?state=open&creator=github-actions%5Bbot%5D&per_page=100&page=2",
    ]
  );
});

test("the bot opens, updates, keeps and closes one issue per language", async () => {
  const results = [
    { language: "de", items: [item("a")] },
    { language: "es", items: [item("a"), item("b")] },
    { language: "fr", items: [item("a")] },
    { language: "it", items: [] },
    { language: "nl", items: [] },
    { language: "pt", items: [item("a")] },
  ];
  const current = render(results[2], LINKS);
  const github = fakeGitHub([botIssue(7, "es"), botIssue(8, "fr", current), botIssue(9, "nl")]);
  const log = [];
  await sync(request(github.fetch), results, LINKS, (line) => log.push(line));
  assert.deepEqual(log, [
    "German: 1 update, opened #101",
    "Spanish: 2 updates, updated #7",
    "French: 1 update, #8 is current",
    "Italian: up to date",
    "Dutch: up to date, closed #9",
    "Portuguese: 1 update, opened #102",
  ]);
  const writes = github.requests.filter((sent) => sent.method !== "GET");
  const path = (sent) => `${sent.method} ${sent.url.split("/repos/Dennis-Otto/homedarts-for-autodarts")[1]}`;
  assert.deepEqual(writes.map(path), [
    "POST /issues",
    "PATCH /issues/7",
    "POST /issues/9/comments",
    "PATCH /issues/9",
    "POST /issues",
  ]);
  assert.deepEqual(writes[0].body, { ...render(results[0], LINKS), labels: LABELS });
  assert.deepEqual(writes[1].body, render(results[1], LINKS));
  assert.deepEqual(writes[2].body, { body: closing("nl") });
  assert.deepEqual(writes[3].body, { state: "closed", state_reason: "completed" });
});

test("labels that GitHub dropped from a new issue are added afterwards", async () => {
  const github = fakeGitHub([], { labels: ["translations"] });
  const log = [];
  await sync(request(github.fetch), [{ language: "fr", items: [item("a")] }], LINKS, (line) => log.push(line));
  const writes = github.requests.filter((sent) => sent.method !== "GET");
  assert.deepEqual(
    writes.map((sent) => [sent.method, sent.url.split("/homedarts-for-autodarts")[1], sent.body.labels]),
    [
      ["POST", "/issues", LABELS],
      ["POST", "/issues/101/labels", ["help wanted", "good first issue"]],
    ]
  );
  assert.deepEqual(log, ["French: 1 update, opened #101"]);
});

// The addresses of the links of a Markdown text.
const links = (markdown) => [...markdown.matchAll(/\]\(([^)\s]+)\)/g)].map((match) => match[1]);

test("without --sync the bot prints its issues; with it, it needs a token and writes to GitHub", async () => {
  const repository = history();
  const log = [];
  await main([], {}, { cwd: repository.dir, log: (line) => log.push(line) });
  assert.equal(log.length, 2);
  assert.ok(log[0].startsWith("# Translation: German needs 1 update · Deutsch: 1 Text zu aktualisieren\n\n<!-- translation-bot: de -->"));
  assert.ok(links(log[0]).some((link) => link.startsWith("https://github.com/Dennis-Otto/homedarts-for-autodarts/edit/main/")));
  assert.ok(log[1].startsWith("# Translation: French needs 3 updates"));
  await assert.rejects(main(["--sync"], {}, { cwd: repository.dir }), /--sync needs GITHUB_TOKEN/);
  const github = fakeGitHub();
  const env = {
    GITHUB_TOKEN: "token",
    GITHUB_REPOSITORY: "someone/fork",
    GITHUB_SERVER_URL: "https://github.example",
    GITHUB_API_URL: "https://api.github.example",
  };
  log.length = 0;
  await main(["--sync"], env, { cwd: repository.dir, fetch: github.fetch, log: (line) => log.push(line) });
  assert.deepEqual(log, ["German: 1 update, opened #101", "French: 3 updates, opened #102"]);
  assert.ok(github.requests.every((sent) => sent.url.startsWith("https://api.github.example/repos/someone/fork/")));
  const fork = links(github.requests.at(-1).body.body);
  assert.ok(fork.length > 3 && fork.every((link) => link.startsWith("https://github.example/someone/fork/")), fork);
  // Without the variables of a workflow, the API of github.com.
  const plain = fakeGitHub();
  await main(["--sync"], { GITHUB_TOKEN: "token" }, { cwd: repository.dir, fetch: plain.fetch, log() {} });
  assert.ok(plain.requests[0].url.startsWith("https://api.github.com/repos/Dennis-Otto/homedarts-for-autodarts/issues?"));
});

test("the script runs on its own in the repository it is called in", () => {
  const repository = history();
  // Up to date: German has its new text too.
  repository.commit("fix(i18n): the new texts", {
    [file("de")]: json({ config: { title: "Dartscheibe", text: "Hallo {name}", added: "Neu" } }),
  });
  const output = execFileSync(process.execPath, [SCRIPT], { cwd: repository.dir, encoding: "utf8" });
  assert.ok(output.startsWith("German: up to date\n\n# Translation: French needs 3 updates"), output.slice(0, 200));
});
