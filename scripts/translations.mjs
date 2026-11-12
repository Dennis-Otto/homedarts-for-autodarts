// The translation bot. It finds the texts of each language that are missing or older
// than their English source, and keeps one GitHub issue per language that native
// speakers can pick up:
//
//   node scripts/translations.mjs          prints what the issues would say
//   node scripts/translations.mjs --sync   opens, updates and closes the issues
//
// A text is stale when its English source changed after the language's text last did.
// The history says so, without a file to keep: on the first-parent history of the
// branch, the newest commit that changed or checked the language's text has an English
// text that differs from today's, by more than its case. A commit checks texts that are
// still right with a line "Translations-checked: fr nl status_ready" in its message,
// which a pull request gets from its description: languages first, then keys; without
// keys, it checks every text of the languages.
// .github/workflows/translations.yml runs it; docs/development.md describes it.
import { execFileSync } from "node:child_process";
import vm from "node:vm";

export const TRANSLATIONS = "custom_components/homedarts/translations";
export const CARD = "custom_components/homedarts/frontend/homedarts-card.js";
// The texts of the cards, a module per language; earlier commits had them in CARD.
export const TEXTS = "custom_components/homedarts/frontend/text";
export const cardFile = (language) => `${TEXTS}/${language}.js`;
export const SOURCE = "en";
// The issues of the bot: the GitHub token of a workflow opens them as this user.
export const BOT = "github-actions[bot]";
export const LABELS = ["translations", "help wanted", "good first issue"];
const MARKER = /^<!-- translation-bot: ([\w-]+) -->/;
const CHECKED = /^Translations?-checked:[ \t]*(.*)$/i;
// GitHub wraps the description of a pull request at 72 characters when it squashes it
// into the commit message. A line of names alone continues a line of checks when its
// first word didn't fit on that line.
const WRAP = 72;
const NAMES = /^[\w.,-]+(?:[ \t]+[\w.,-]+)*$/;
// GitHub takes 65,536 characters in an issue; longer lists end with the keys alone.
const TEXTS_BUDGET = 40_000;
const KEYS_BUDGET = 8_000;

// The two places of the texts, each with the forms of its files: a commit has the
// texts of the first form whose file it has. The integration has a file per language.
// So have the cards, in TEXTS; before, one TEXT dictionary in homedarts-card.js held
// every language, and the history of a text goes on across the move.
const SOURCES = [
  {
    id: "integration",
    forms: [
      {
        path: (language) => `${TRANSLATIONS}/${language}.json`,
        parse: (content) => flatten(JSON.parse(content)),
        select: (parsed) => parsed,
        lines: (content) => jsonLines(content),
      },
    ],
    heading: (language) => `Integration: \`${TRANSLATIONS}/${language}.json\``,
  },
  {
    id: "cards",
    forms: [
      {
        path: cardFile,
        parse: (content) => moduleTexts(content),
        select: (parsed) => parsed,
        lines: (content) => jsonLines(content),
      },
      {
        path: () => CARD,
        parse: (content) => cardTexts(content),
        select: (parsed, language) => parsed[language] ?? {},
        lines: (content, language) => cardLines(content, language),
      },
    ],
    heading: (language) => `Cards: \`${cardFile(language)}\``,
  },
];

// The words of the issues in each language: German, Dutch and Spanish speak to the
// reader informally, French formally, as the translations do.
const WORDS = {
  de: {
    name: "German",
    label: "Deutsch:",
    title: (count) => `Deutsch: ${count} ${count === 1 ? "Text" : "Texte"} zu aktualisieren`,
    intro:
      "Hallo! Die deutsche Übersetzung von HomeDarts for Autodarts hinkt dem englischen Original hinterher. Wenn du Deutsch sprichst, kannst du helfen, ganz ohne Programmierkenntnisse: Die Schritte stehen unten auf Englisch, und du kannst hier auch gern auf Deutsch kommentieren.",
    done: "Alle deutschen Texte sind jetzt aktuell. Danke an alle, die geholfen haben!",
  },
  es: {
    name: "Spanish",
    label: "Español:",
    title: (count) => `Español: ${count} ${count === 1 ? "texto" : "textos"} por actualizar`,
    intro:
      "¡Hola! La traducción al español de HomeDarts for Autodarts se ha quedado atrás respecto al original en inglés. Si hablas español, puedes ayudar sin saber programar: los pasos están en inglés más abajo, y también puedes comentar aquí en español.",
    done: "Todos los textos en español están al día. ¡Gracias a todas las personas que han ayudado!",
  },
  fr: {
    name: "French",
    label: "Français\u00a0:",
    title: (count) => `Français\u00a0: ${count} ${count === 1 ? "texte" : "textes"} à mettre à jour`,
    intro:
      "Bonjour\u00a0! La traduction française de HomeDarts for Autodarts n'est plus à jour par rapport à l'original anglais. Si vous parlez français, vous pouvez aider sans savoir programmer\u00a0: les étapes sont décrites en anglais ci-dessous, et vous pouvez aussi commenter ici en français.",
    done: "Tous les textes français sont maintenant à jour. Merci à toutes les personnes qui ont aidé\u00a0!",
  },
  nl: {
    name: "Dutch",
    label: "Nederlands:",
    title: (count) => `Nederlands: ${count} ${count === 1 ? "tekst" : "teksten"} bij te werken`,
    intro:
      "Hallo! De Nederlandse vertaling van HomeDarts for Autodarts loopt achter op het Engelse origineel. Spreek je Nederlands? Dan kun je helpen, zonder te programmeren: de stappen staan hieronder in het Engels, en je mag hier ook gewoon in het Nederlands reageren.",
    done: "Alle Nederlandse teksten zijn nu bijgewerkt. Bedankt aan iedereen die heeft geholpen!",
  },
};

// The English name of a language, also of one without words of its own above.
export function languageName(language) {
  if (WORDS[language]) return WORDS[language].name;
  try {
    return new Intl.DisplayNames(["en"], { type: "language", fallback: "code" }).of(language);
  } catch {
    return language;
  }
}

export function git(cwd, args, input) {
  return execFileSync("git", args, { cwd, input, maxBuffer: 1 << 30, stdio: ["pipe", "pipe", "pipe"] });
}

// The commits of the first-parent history, the oldest first, with their messages. A
// merged pull request is one commit there, whatever its branch looked like.
export function commits(cwd, ref = "HEAD") {
  const format = "--format=%H%x1f%B%x1e";
  const log = git(cwd, ["rev-list", "--first-parent", "--reverse", "--no-commit-header", format, ref]);
  return log
    .toString("utf8")
    .split("\x1e")
    .slice(0, -1)
    .map((record) => {
      const [sha, message] = record.replace(/^\n/, "").split("\x1f");
      return { sha, message };
    });
}

// The blob of a file in each commit, or null where the file does not exist.
export function blobs(cwd, shas, path) {
  const input = shas.map((sha) => `${sha}:${path}\n`).join("");
  const lines = git(cwd, ["cat-file", "--batch-check=%(objectname)"], input).toString("utf8").split("\n");
  return shas.map((_, index) => (lines[index].endsWith(" missing") ? null : lines[index]));
}

// The contents of blobs, read by one git process.
export function contents(cwd, ids) {
  const unique = [...new Set(ids)];
  const output = git(cwd, ["cat-file", "--batch"], unique.map((id) => `${id}\n`).join(""));
  const result = new Map();
  let offset = 0;
  for (const id of unique) {
    const header = output.indexOf(10, offset);
    const size = Number(output.toString("utf8", offset, header).split(" ")[2]);
    result.set(id, output.toString("utf8", header + 1, header + 1 + size));
    offset = header + size + 2;
  }
  return result;
}

// Every text of a translation tree by its path, such as entity.sensor.round.name.
export function flatten(tree, prefix = "") {
  const texts = {};
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") texts[path] = value;
    else if (value !== null && typeof value === "object") Object.assign(texts, flatten(value, path));
  }
  return texts;
}

// The texts of a module of TEXTS: JSON after "export default", with comments on
// lines of their own, as tests/test_consistency.py reads them too.
export function moduleTexts(source) {
  const json = source
    .split("\n")
    .filter((line) => !/^\s*\/\//.test(line))
    .join("\n");
  return flatten(JSON.parse(json.slice(json.indexOf("{"), json.lastIndexOf("}") + 1)));
}

// TEXT of an earlier version of the card module, by language: the object literal
// alone, evaluated without access to anything else. It ends with the first line "};".
// Today's module only puts the modules of TEXTS together, on one line.
export function cardTexts(source) {
  const start = source.indexOf("const TEXT = {\n");
  if (start < 0) return {};
  const open = source.indexOf("{", start);
  const literal = source.slice(open, source.indexOf("\n};", open) + 2);
  const text = vm.runInNewContext(`(${literal})`, Object.create(null), { timeout: 10_000 });
  return Object.fromEntries(Object.entries(text).map(([language, texts]) => [language, flatten(texts)]));
}

// The line of every text in a translation file, for links to it.
export function jsonLines(content) {
  const lines = new Map();
  const parents = [];
  content.split("\n").forEach((line, index) => {
    const match = /^(\s*)("(?:[^"\\]|\\.)*")\s*:\s*(.)/.exec(line);
    if (!match) return;
    const indent = match[1].length;
    while (parents.length > 0 && parents.at(-1).indent >= indent) parents.pop();
    const key = JSON.parse(match[2]);
    if (match[3] === "{") parents.push({ indent, key });
    else lines.set([...parents.map((parent) => parent.key), key].join("."), index + 1);
  });
  return lines;
}

// The line of every text of a language in TEXT of an earlier card module.
export function cardLines(source, language) {
  const lines = new Map();
  const all = source.split("\n");
  const start = all.indexOf(`  ${language}: {`, all.indexOf("const TEXT = {"));
  if (start < 0) return lines;
  for (let index = start + 1; index < all.length && !all[index].startsWith("  }"); index += 1) {
    const match = /^ {4}(\w+):/.exec(all[index]);
    if (match) lines.set(match[1], index + 1);
  }
  return lines;
}

// When each text of a language last changed: the index of the commit by key, and the
// texts of every version, to look up the English text of a certain time.
function timeline(versions) {
  const changed = new Map();
  let previous = {};
  for (const { index, texts } of versions) {
    for (const [key, value] of Object.entries(texts)) {
      if (previous[key] !== value) changed.set(key, index);
    }
    previous = texts;
  }
  return { changed, versions };
}

function textAt(timeline, key, index) {
  // The first version has index 0, so there is always one.
  return timeline.versions.findLast((version) => version.index <= index).texts[key];
}

// The lines "Translations-checked: <languages> [<keys>]" of every commit message.
export function checks(chain, languages) {
  const found = [];
  chain.forEach(({ message }, index) => {
    const lines = message.split(/\r?\n/);
    lines.forEach((line, number) => {
      const match = CHECKED.exec(line);
      if (!match) return;
      let value = match[1];
      for (let next = number + 1; next < lines.length && continues(lines[next - 1], lines[next]); next += 1) {
        value += ` ${lines[next]}`;
      }
      const tokens = value.split(/[\s,]+/).filter(Boolean);
      const count = tokens.findIndex((token) => !languages.includes(token));
      const listed = count < 0 ? tokens : tokens.slice(0, count);
      if (listed.length === 0) return;
      const keys = count < 0 ? [] : tokens.slice(count);
      found.push({ index, languages: new Set(listed), keys: keys.length > 0 ? new Set(keys) : null });
    });
  });
  return found;
}

function continues(previous, line) {
  const word = line.split(/[ \t]/, 1)[0];
  return NAMES.test(line) && [...previous].length + 1 + [...word].length > WRAP;
}

function checkedAt(found, language, key) {
  let index = -1;
  for (const check of found) {
    if (check.languages.has(language) && (check.keys === null || check.keys.has(key))) index = check.index;
  }
  return index;
}

// Every language but English with its missing and stale texts, in the order of the
// English texts, the integration's first.
export function findings(cwd, ref = "HEAD") {
  const chain = commits(cwd, ref);
  const shas = chain.map((commit) => commit.sha);
  const head = shas.length - 1;
  const blobCache = new Map();
  const blobsOf = (path) => {
    if (!blobCache.has(path)) blobCache.set(path, blobs(cwd, shas, path));
    return blobCache.get(path);
  };
  // Each blob is read and parsed once; the card's is the same for every language.
  const read = new Map();
  const readAll = (ids) => {
    const unread = ids.filter((id) => id && !read.has(id));
    if (unread.length === 0) return;
    for (const [id, content] of contents(cwd, unread)) read.set(id, content);
  };
  const named = (folder, extension) =>
    git(cwd, ["ls-tree", "--name-only", ref, `${folder}/`])
      .toString("utf8")
      .split("\n")
      .filter((file) => file.endsWith(extension))
      .map((file) => file.slice(folder.length + 1, -extension.length));
  // The languages of the card module of an earlier ref, before its texts moved.
  const cardBlob = blobsOf(CARD)[head];
  readAll([cardBlob]);
  const earlierCard = cardBlob ? Object.keys(cardTexts(read.get(cardBlob))) : [];
  const languages = [...new Set([...named(TRANSLATIONS, ".json"), ...named(TEXTS, ".js"), ...earlierCard])]
    .filter((code) => code !== SOURCE)
    .sort();
  const found = checks(chain, languages);
  const results = languages.map((language) => ({ language, items: [] }));
  for (const source of SOURCES) {
    // Each blob is parsed once per form; the earlier card module is the same for every language.
    const parsed = new Map(source.forms.map((form) => [form, new Map()]));
    const history = (language, like) => {
      const forms = source.forms.map((form) => ({ form, ids: blobsOf(form.path(language)) }));
      // The file of each commit, of the first form that it has.
      const files = shas.map((_, index) => {
        const first = forms.find(({ ids }) => ids[index]);
        return first ? { form: first.form, id: first.ids[index] } : null;
      });
      const changes = files.flatMap((file, index) => (index > 0 && file?.id === files[index - 1]?.id ? [] : [{ index, file }]));
      readAll(changes.map(({ file }) => file?.id));
      const versions = changes.map(({ index, file }) => {
        if (!file) return { index, texts: {} };
        const cache = parsed.get(file.form);
        if (!cache.has(file.id)) cache.set(file.id, file.form.parse(read.get(file.id)));
        return { index, texts: file.form.select(cache.get(file.id), language) };
      });
      // Where the texts are now, or would go: in the form of English, the newest without it.
      const now = files[head];
      const form = like ?? now?.form ?? source.forms[0];
      const lines = now?.form === form ? form.lines(read.get(now.id), language) : new Map();
      return { timeline: timeline(versions), form, path: form.path(language), lines };
    };
    const english = history(SOURCE);
    const current = english.timeline.versions.at(-1).texts;
    if (Object.keys(current).length === 0) {
      throw new Error(`No English texts in ${english.path}; the translation bot needs to learn its new form.`);
    }
    for (const result of results) {
      const { language } = result;
      const translated = history(language, english.form);
      const texts = translated.timeline.versions.at(-1).texts;
      const { path, lines } = translated;
      for (const [key, text] of Object.entries(current)) {
        const translation = texts[key];
        const item = { source: source.id, path, key, english: text, translation, line: lines.get(key) };
        if (translation === undefined) {
          result.items.push({ ...item, state: "missing", previous: undefined });
          continue;
        }
        const since = Math.max(translated.timeline.changed.get(key), checkedAt(found, language, key));
        // A language writes its own case, so a change of case alone in English is none.
        const previous = textAt(english.timeline, key, since);
        if (previous?.toLowerCase() !== text.toLowerCase()) result.items.push({ ...item, state: "outdated", previous });
      }
    }
  }
  return results;
}

// A block of code that holds any text as it is, whatever backticks it has.
function fenced(text) {
  const longest = Math.max(2, ...[...text.matchAll(/`+/g)].map((match) => match[0].length));
  const fence = "`".repeat(longest + 1);
  return `${fence}text\n${text}\n${fence}`;
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

// The title and text of the issue of a language.
export function render(result, links) {
  const { language, items } = result;
  const name = languageName(language);
  const words = WORDS[language];
  const count = items.length;
  const title = `Translation: ${name} needs ${plural(count, "update")}${words ? ` · ${words.title(count)}` : ""}`;
  const missing = items.filter((item) => item.state === "missing").length;
  const outdated = count - missing;
  let state = `missing or older than the English original: ${missing} missing, ${outdated} outdated`;
  if (missing === 0) state = "older than the English original";
  if (outdated === 0) state = "missing";
  const parts = [`<!-- translation-bot: ${language} -->`];
  if (words) parts.push(`**${words.label}** ${words.intro}`);
  parts.push(
    `**English:** Hello! ${plural(count, `${name} text`)} of HomeDarts for Autodarts ${count === 1 ? "is" : "are"} ${state}. If you speak ${name}, you can help, no programming needed: the steps are below.`,
    "## Texts"
  );
  let length = parts.join("\n\n").length;
  let shown = 0;
  for (const item of items) {
    const block = [];
    if (shown === 0 || items[shown - 1].source !== item.source) {
      block.push(`### ${SOURCES.find((source) => source.id === item.source).heading(language)}`);
    }
    const key = item.line ? `[\`${item.key}\`](${links.blob}/${item.path}#L${item.line})` : `\`${item.key}\``;
    block.push(`#### ${key} · ${item.state}`, `English now:\n${fenced(item.english)}`);
    if (item.state === "missing") {
      block.push(`${name}: missing`);
    } else {
      if (item.previous !== undefined) block.push(`English when last translated:\n${fenced(item.previous)}`);
      block.push(`${name} now:\n${fenced(item.translation)}`);
    }
    const text = block.join("\n\n");
    if (length + text.length > TEXTS_BUDGET) break;
    parts.push(text);
    length += text.length + 2;
    shown += 1;
  }
  if (shown < count) {
    let rest = items
      .slice(shown)
      .map((item) => `\`${item.key}\``)
      .join(", ");
    if (rest.length > KEYS_BUDGET) rest = `${rest.slice(0, rest.lastIndexOf(", ", KEYS_BUDGET))}, …`;
    parts.push(`And ${plural(count - shown, "more text")}, too many to show here: ${rest}`);
  }
  const files = [...new Set(items.map((item) => item.source))].map((id) =>
    id === "integration"
      ? `   - [\`${TRANSLATIONS}/${language}.json\`](${links.edit}/${TRANSLATIONS}/${language}.json) for the texts of the integration: setup, entities, actions and messages`
      : `   - [\`${cardFile(language)}\`](${links.edit}/${cardFile(language)}) for the texts of the dashboard cards`
  );
  parts.push(
    "## How to help",
    "You need a GitHub account, but no programming and no setup: it all happens in the browser.",
    [
      "1. Open the file and click the pencil, *Edit this file*. GitHub makes a copy of the repository for you, a fork.",
      ...files,
      "2. Find each key listed above, whose link shows its line, and change only the text in quotes. Keep the key, the quotes, the comma after them where there is one, placeholders such as `{name}`, and the order of the lines.",
      `3. Click *Commit changes…*, then *Propose changes* and *Create pull request*. A title such as \`fix(i18n): update the ${name} texts\` fits. The checks of the pull request test every language, and a maintainer helps when one fails.`,
      `4. Once it is merged, the next release brings your texts to every user, and the [changelog](${links.blob}/CHANGELOG.md) thanks you by your GitHub name. A maintainer writes that line, you don't need to.`,
    ].join("\n"),
    `Is a text still right as it is? Say so in a comment here, or put a line such as \`Translations-checked: ${language} ${items[0].key}\` with its keys into the description of your pull request; once merged, the bot counts them as up to date.`,
    `The [translation guide](${links.blob}/docs/development.md#translations) has the style of each language: how to address the reader and which darts terms stay English. This issue updates itself when the texts change and closes itself once every ${name} text is up to date.`
  );
  return { title, body: `${parts.join("\n\n")}\n` };
}

// What the bot writes when a language is up to date again.
export function closing(language) {
  const name = languageName(language);
  const words = WORDS[language];
  const english = `**English:** Every ${name} text is up to date now. Thank you to everyone who helped!`;
  return words ? `**${words.label}** ${words.done}\n\n${english}\n` : `${english}\n`;
}

// A request to the REST API of GitHub for the repository.
export function client({ token, repository, api, fetch }) {
  return async (method, path, body) => {
    const response = await fetch(`${api}/repos/${repository}${path}`, {
      method,
      headers: {
        accept: "application/vnd.github+json",
        authorization: `Bearer ${token}`,
        "content-type": "application/json",
        "x-github-api-version": "2022-11-28",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`GitHub answered ${method} ${path} with ${response.status}: ${await response.text()}`);
    return response.json();
  };
}

// The open issues of the bot, by language.
export async function openIssues(request, page = 1, issues = new Map()) {
  const batch = await request("GET", `/issues?state=open&creator=${encodeURIComponent(BOT)}&per_page=100&page=${page}`);
  for (const issue of batch) {
    const language = issue.pull_request ? undefined : MARKER.exec(issue.body ?? "")?.[1];
    if (language && !issues.has(language)) issues.set(language, issue);
  }
  return batch.length < 100 ? issues : openIssues(request, page + 1, issues);
}

// One issue per language with work to do; the issue of a language without closes.
export async function sync(request, results, links, log) {
  const issues = await openIssues(request);
  for (const result of results) {
    const issue = issues.get(result.language);
    const name = languageName(result.language);
    if (result.items.length === 0) {
      if (issue) {
        await request("POST", `/issues/${issue.number}/comments`, { body: closing(result.language) });
        await request("PATCH", `/issues/${issue.number}`, { state: "closed", state_reason: "completed" });
        log(`${name}: up to date, closed #${issue.number}`);
      } else {
        log(`${name}: up to date`);
      }
      continue;
    }
    const { title, body } = render(result, links);
    const updates = plural(result.items.length, "update");
    if (!issue) {
      const created = await request("POST", "/issues", { title, body, labels: LABELS });
      // GitHub drops the labels of a new issue silently when the token may not set them.
      const labelled = new Set(created.labels.map((label) => label.name));
      const unlabelled = LABELS.filter((label) => !labelled.has(label));
      if (unlabelled.length > 0) await request("POST", `/issues/${created.number}/labels`, { labels: unlabelled });
      log(`${name}: ${updates}, opened #${created.number}`);
    } else if (issue.title !== title || issue.body !== body) {
      await request("PATCH", `/issues/${issue.number}`, { title, body });
      log(`${name}: ${updates}, updated #${issue.number}`);
    } else {
      log(`${name}: ${updates}, #${issue.number} is current`);
    }
  }
}

export async function main(args, env, { cwd = process.cwd(), fetch = globalThis.fetch, log = console.log } = {}) {
  const repository = env.GITHUB_REPOSITORY || "Dennis-Otto/homedarts-for-autodarts";
  const server = env.GITHUB_SERVER_URL || "https://github.com";
  const links = { blob: `${server}/${repository}/blob/main`, edit: `${server}/${repository}/edit/main` };
  const results = findings(cwd);
  if (!args.includes("--sync")) {
    for (const result of results) {
      if (result.items.length === 0) {
        log(`${languageName(result.language)}: up to date\n`);
        continue;
      }
      const { title, body } = render(result, links);
      log(`# ${title}\n\n${body}`);
    }
    return;
  }
  if (!env.GITHUB_TOKEN) throw new Error("--sync needs GITHUB_TOKEN with the permission to write issues.");
  const api = env.GITHUB_API_URL || "https://api.github.com";
  await sync(client({ token: env.GITHUB_TOKEN, repository, api, fetch }), results, links, log);
}

if (import.meta.main) await main(process.argv.slice(2), process.env);
