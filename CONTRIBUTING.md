# Contributing

Contributions are welcome through issues and pull requests.
Participation follows [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and project decision-making is described in [GOVERNANCE.md](GOVERNANCE.md).
Use [SUPPORT.md](SUPPORT.md) to choose the correct public support channel and [SECURITY.md](SECURITY.md) for private vulnerability reports.

All changes reach the protected `main` branch through pull requests that pass every required check.
Coding agents find these rules in short in [AGENTS.md](AGENTS.md), with the files that belong to the blueprint and are changed there. A pull request that changes one of those, as `.github/blueprint/owned.txt` lists them, gets a notice that says where the change belongs instead.

## Requirements for changes

- New functionality and bug fixes must include automated tests. Use pytest for integration behavior and extend the Docker end-to-end test in `tests/e2e/` when a user-visible Home Assistant flow changes.
- Code must pass Ruff (lint and format) and strict mypy with the rules configured in `pyproject.toml`, keep the test coverage of every line and branch at 100 %, and remain compatible with the Home Assistant version used by the tests.
- The JavaScript of the cards and of their tests must pass ESLint with the rules of `eslint.config.mjs`. Dashboard card changes need Node tests in `tests/frontend/` and, for visible changes, the browser test in `tests/e2e/browser.py`.
- Blueprint changes need tests in `tests/test_blueprints.py`, which run the blueprints through Home Assistant's automation engine, and `python scripts/ship_blueprints.py`, which copies them into the integration, whose release package carries them, and records the fingerprint of the new version; `tests/test_shipped_blueprints.py` fails until it has run. Each start of Home Assistant brings the blueprints of the installed release into the configuration and updates those nobody changed ([decision 0023](docs/decisions/0023-blueprints-ship-with-the-integration.md)). The import buttons and the `source_url` of every blueprint point to `main`, so whoever imports or re-imports a blueprint between two releases gets the one on `main`, while HACS installs the latest release of the integration. A blueprint on `main` therefore keeps working with the latest release: a change that needs events, attributes or actions of an unreleased version is merged together with its release, or the blueprint's description names the version it needs. New inputs get defaults that keep existing automations working as before.
- Tests keep working under the weekly [mutation tests](docs/development.md#mutation-tests), which run them several times in one process and in processes forked from it, against changed code in a copy of the repository: a test leaves its parameters unchanged, and one that reads the code as text or asks Git is marked `@pytest.mark.mutation_unsafe`.
- User-facing text belongs in `strings.json` and every translation, card texts in every file of `frontend/text/`; see [Translations](#translations).
- Update the README and `docs/` when behavior, setup, or supported versions change. The documentation is English, with a German translation next to each page (`docs/games.de.md` next to `docs/games.md`); update both. Regenerate screenshots with `bash tests/e2e/screenshots.sh` when a visible card or dialog changes.
- Local Board Manager communication must not log, store, or expose the board API key. Cloud tokens remain in the config entry.
- Every commit carries a [Developer Certificate of Origin](https://developercertificate.org/) sign-off, `Signed-off-by: Your Name <you@example.com>`, which `git commit -s` adds.
- Name the issue that a pull request fixes with `Fixes #123` in its description. The issue stays open until a release ships the fix and then closes with a link to the release.

## Tests

New functionality comes with tests in the automated test suite, in the same pull request, and so does every change of behavior. A bug fix comes with a test that fails without the fix, so that the bug can't return unnoticed. `scripts/check.sh` fails when a line or a branch of the code runs in no test, and runs the tests on every logical core with pytest-xdist where it is installed, in at most eight processes unless `PYTEST_XDIST_AUTO_NUM_WORKERS` sets another number, so each test stands on its own, without the state or the order of another one. A test that makes a Git repository of its own first clears the variables that point Git at another, such as `GIT_DIR`, which Git sets for its hooks in a worktree and an agent sets for a worktree in a container, with `unset $(git rev-parse --local-env-vars)` in a shell script; otherwise its `git init` and its commits land in the repository that runs the tests. A pull request without the tests it needs is not merged.

Every Friday the mutation tests change the code in thousands of small ways and show in the summary of the *Mutation* workflow each change that no test noticed, those that change the logic first, each with its change: a test that fails with such a change kills it. A line whose text no test needs to check, such as a log line, a note or the help of an option, gets `# pragma: no mutate` at its end, and mutmut leaves it alone; `# pragma: no mutate block` at the end of the first line of an `if`, `for`, `with` or another statement with a block leaves that statement and its block alone, and `# pragma: no mutate start` … `# pragma: no mutate end` the lines between them. On a line of its own, `# pragma: no mutate block` leaves alone every statement up to the end of the block it stands in. mutmut runs the tests in a copy of the repository, `mutants/`, which has no Git and holds the code with every mutant: a test that can't pass there, because it reads the code as text, asks Git or starts the tool, also a copy of it in a folder of its own, gets `@pytest.mark.mutation_unsafe`, and a test of a function with a cache of `functools` clears it with `cache_clear()`. mutmut copies a whole function for each of its mutants: a long function with many of them, such as a parser with the options of every command, makes a copy of many megabytes that takes minutes to compile, so split it into smaller functions.

## Coding standards

- **Python** follows [PEP 8](https://peps.python.org/pep-0008/) in the format of [Ruff](https://docs.astral.sh/ruff/), which matches Black, with the rules of Ruff that `pyproject.toml` selects. The code has type hints, which mypy checks in its strict mode.
- **The integration** keeps the rules that hassfest checks for Home Assistant and the HACS action for HACS, such as those of its manifest, translations and services.
- **Shell scripts** pass [ShellCheck](https://www.shellcheck.net/), which the CI never skips, **workflows** pass actionlint and zizmor's audit of their security, and **Markdown** follows the rules of markdownlint in `.markdownlint.jsonc`.
- **A new action or reusable workflow** needs its pattern `owner/repo@*` in `[actions.selected]` of `.github/repository.project.toml`, also for what it runs in turn: GitHub starts only the listed ones. The step *Check that the allowed actions let every action start* of the check *lint* fails while the list lacks one, and `python3 .github/blueprint.py settings actions` runs it on your machine, with the GitHub CLI. Its jobs start once a maintainer has run `python3 .github/blueprint.py settings apply`. A step with `uses: docker://…` is an action as well, which GitHub refuses whatever the list names, and `settings check` names it too: run the image in a `run:` step instead, pinned by its digest, as `docker run --rm --volume "$PWD:/github/workspace" --workdir /github/workspace <image>` with the step's `with: args` after it and its `entrypoint` as `--entrypoint`, which is what GitHub does for such a step.
- **Every text file** has LF line endings, no trailing whitespace, a line break at its end and no conflict markers that a merge left; `.editorconfig` sets up most editors for it.

`scripts/check.sh` and the Lint workflow check these standards on every pull request, which merges only when they pass. An exception to a rule is rare and is marked at its place in the code, with its reason in a comment.

## Workflow

1. Open an issue or a discussion first for anything larger than a small fix, so we can agree on the approach.
2. Fork the repository and create a branch from `main`, for example `feat/cricket-variants` or `fix/bull-off-tie`.
3. Describe what changes for users, in the words of a user, in a new file in `changelog.d/` named after your branch without its type, such as `changelog.d/dark-mode.md` for the branch `feat/dark-mode`, below the heading of its kind of change, such as `### Features` or `### Bug fixes`. The check of the title, *conventional title*, asks for it in every `feat`, `fix` or `perf` pull request, and checks it as the release takes it in. A file of its own conflicts with no other pull request; a line under `## Unreleased` in `CHANGELOG.md` works as well, but conflicts with each pull request that adds one at the same place. A tester who helped is thanked in the entry by their GitHub name.
4. Commit with [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`, `refactor:` or `perf:`, with an optional scope such as `feat(scoreboard): …`. Mark breaking changes with `!`.
5. A change that makes or changes a decision that shapes the project, such as a supported platform or the way of releasing, records it in [`docs/decisions/`](docs/decisions/README.md).
6. Open a pull request with a Conventional Commit title. A workflow checks the title and labels the pull request. Pull requests are squashed into one commit on `main`, and the title decides the next version: `fix` a patch, `feat` a minor, `!` a major version, or a minor one while the version is below 1.0.0.
7. The maintainer reviews every pull request for correctness, tests, documentation in both languages, security and user impact.

### The changelog

A fragment holds the entries of one pull request, each below the heading of its kind of change:

```markdown
### Features

- **Dark mode:** the settings follow the theme of the system.
```

The headings are those of the blueprint, `Breaking changes`, `Features`, `Changes`, `Bug fixes` and `Performance`, those of [Keep a Changelog](https://keepachangelog.com/), `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed` and `Security`, and every other one that `CHANGELOG.md` has already. The release bot moves the entries of every fragment and of Unreleased into the section of the next release, each kind of change below one heading, and deletes the fragments in the same commit of the release pull request. `bash scripts/check.sh` checks every fragment as the release takes it in, those that wait on `main` for the next release too, with `python3 .github/blueprint.py fragments`. A heading that surely means a kind of change, such as `### Fixes` for `### Fixed` or `## Features` for `### Features`, `python3 .github/blueprint.py fragments --fix` renames, as the fix bot does on the branch of a pull request and suggests on one from a fork; a heading as close to one kind as to another, such as `### Change`, stays for you. The check of the title, *conventional title*, takes only a new fragment as the entry of a pull request: one that `main` has already is the entry of another pull request that waits for its release, so a pull request that changes it gets a warning, and one that needs an entry adds a fragment of its own under a new name. A page of the website that includes `CHANGELOG.md` with a line `--8<-- "CHANGELOG.md"` shows the entries of the fragments under Unreleased until the release takes them in, grouped as the release groups them.

## Checks

Before opening a pull request, run the checks of the CI, then the end-to-end and the browser test:

```bash
python3.14 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-test.txt
npm ci
. .venv/bin/activate && bash scripts/check.sh
BOARD_MANAGER=2 bash tests/e2e/run.sh
bash tests/e2e/browser.sh
```

`scripts/check.sh` runs the text checks, Ruff, strict mypy, pytest with every line and branch covered, and in `scripts/check-project.sh` the tests of the cards with Node. To run it before every push on its own, turn on the hook of the repository once: `git config core.hooksPath .githooks`. The end-to-end and browser tests require Docker with Compose. The [development guide](docs/development.md) describes every tool, including the demo instance.

Git runs the hook only when its file is executable. Windows has no such mode and adds the file as a plain one, which `scripts/check.sh` reports; `git update-index --chmod=+x .githooks/pre-push` and a commit make it executable.

Do not include real credentials, board IDs, API keys, private network addresses, or logs containing personal data. Use reserved documentation addresses such as `192.0.2.10` and clearly synthetic values in tests and documentation.

The development container in `.devcontainer/` sets up Python 3.14, Node.js 24 and Docker in one step, for VS Code and GitHub Codespaces, and `bash scripts/check.sh` runs in it. Optional pre-commit hooks run Ruff and basic file checks before each commit: `pip install pre-commit && pre-commit install`.

## Translations

The integration speaks English, German, Dutch, French and Spanish. Its texts live in two places:

- `custom_components/homedarts/strings.json` with the English source, copied unchanged to `translations/en.json`, and one file per language in `translations/` with the same keys in the same order;
- the texts of the dashboard cards, one file per language in `custom_components/homedarts/frontend/text/`: `en.js` with the English source and one file per language with the same keys in the same order. Each file is `export default` followed by JSON, one text per line such as `"visit": "Current visit",`, with a comma after every text but the last; comments stand on lines of their own. The card module imports every file, and `TEXT` puts them together.

`tests/test_consistency.py` keeps every language complete. It fails when a translation file or a file of card texts misses a key, has one too many, loses a placeholder such as `{name}`, uses the wrong form of address, or when a translation file has no file of card texts or the other way round. It names the line of a slip in a file of card texts, such as a comma after the last text. It also fails for a card text that no card reads, by its key or by a family of keys such as `party_${game}`, because the translation bot would still ask volunteers to translate it. So a pull request that adds a text adds it to every language, and one that removes a text, or the last code that shows it, removes it everywhere. If you do not speak a language, ask in the pull request; a maintainer or a native speaker adds the missing texts before the merge. The texts `picker_*` have a copy in `homedarts-strategy.js`, the small module of every page, which `python3 scripts/sync_translations.py` writes.

When an English text changes, change its translations in the same pull request. If you can't, the [translation bot](docs/development.md#translation-bot) opens an issue for each language with outdated or missing texts and asks native speakers for them. A translation that stays right after an English change is marked with a line such as `Translations-checked: de fr status_ready` in the description of the pull request: the languages first, then the keys, or no keys for every text of the languages.

A new language needs its translation file, its file of card texts with its import and its entry in `TEXT` of `homedarts-card.js`, its code in `LANGUAGES` of `const.py`, its words for the calendar in `journal.py`, its month names and date format for the highlight gallery in `media_source.py`, its decimal mark for the weekly report in `DECIMAL_MARKS` of `calls.py`, the default sentences of the three voice blueprints with their examples in `tests/test_voice_blueprints.py` and the guide, the answers of *Ask Assist about your darts* in its `answers`, and a line in the documentation's [language section](docs/README.md#languages). `tests/test_consistency.py` and `tests/test_voice_blueprints.py` fail until each of these lists, except the line of the documentation, names the languages of the translation files, so a new language can't stay English in one place unnoticed. The card picks a language by Home Assistant's language code, so `es` also serves `es-419`. The settings of the blueprints stay English because Home Assistant does not translate blueprints. What the callers and the weekly report say comes from the integration instead: the board events carry it in `call`, `title` and `summary`, rendered by `calls.py` from the `caller_*`, `report_*`, `voice_*` and `voice_pack_*` messages, so a translation of these messages is what they say. The sentences of the voice blueprints come in every language, and so do the answers of *Ask Assist about your darts*, which a blueprint has to bring itself: they follow the style below, which `tests/test_voice_blueprints.py` checks for French and Spanish. The translation bot reads only the translation files and the files of card texts, so it doesn't see the sentences and answers of the voice blueprints: a change to their English text changes the other languages in the same pull request, or asks native speakers for them in an issue with the label `translations`.

Style of the languages:

- Speak to the user as Home Assistant does in that language: informally in German ("du"), Dutch ("je") and Spanish ("tú"), formally in French ("vous"). French puts a no-break space (`\u00a0`) before `:`, `;`, `?` and `!`; Spanish opens questions with `¿`. The tests check both.
- Keep the darts terms players use in that language, and the English ones where they do: leg, set, bull, 180, game shot, double out. Game names such as Around the Clock, Bob's 27 or Shanghai stay English.
- Use one term for one thing throughout. The glossaries: German "Aufnahme" for a visit, "Übungsspiel", "Doppelquote"; Dutch "beurt", "uitgooi", "dubbel", "oefenspel", "bullen"; French "volée", "manche" for a leg, "finish", "partie"; Spanish "tirada", "cierre", "doble", "partida".
- The `say_*` texts are spoken by the caller; write them as a caller would say them.
- `practice_entity` and `tournament_entity` of the card texts say how the names of the practice and tournament entities read, for example `Practice {name}` or `{name} de la partie`, so the automatic dashboard can show them without the section they sit in. Keep them in line with the entity names of the translation file.

The documentation is English with a complete German translation. Each German page sits next to its English page, with the English name and `.de`, such as `docs/games.de.md` next to `docs/games.md`, and links to German pages by those names. A pull request that changes a page changes both languages. Keep the terms of the [glossary](docs/glossary.md) ([German](docs/glossary.de.md)), for example "Übungsspiel", "Aufnahme" for a visit and "Doppelquote". Dutch, French and Spanish have the pages that decide whether someone tries the integration, `index`, `getting-started`, `installation` and `faq`, such as `docs/faq.nl.md`, and their websites show every other page in English, with a note that leads to this section, which `extra.untranslated` of the language in `mkdocs.yml` words ([decision 0027](docs/decisions/0027-the-start-pages-in-dutch-french-and-spanish.md)). A pull request that changes one of these four pages changes them in every language where it can, in the terms of the glossaries above; where it can't, it says so, keeps the English words in the translated page, and an issue with the label `translations` asks native speakers. A native speaker can improve them at any time: the pencil of each page of the website opens its file on GitHub. `tests/test_website_translations.py` holds these pages to what a player sees: the buttons and terms of the translation files, the menus of Home Assistant, which it lists from the translations of Home Assistant's frontend, and the style above. It also fails when `getting-started` or `faq` lacks a section or a link of its English page: add it to the translated page as well, in English if you can't translate it, and say so in the pull request. A link from such a page goes to its own page in that language, such as `installation.nl.md`, and to the English page for a section that only English has, such as `installation.md#reconfigure`. `tests/test_docs_links.py` checks that every link, heading anchor and image resolves, and that every count of blueprints, dashboard cards and `homedarts.*` actions matches the blueprint files, the card picker and `services.yaml`.

## When a check fails

A check that fails explains itself. The PR coach writes what the check found, why that matters and how to fix it, with the commands to run, into the summary of the check and as its annotation; the pull request also shows each finding of a tool at the line that it names, as an annotation, and the comment lists them: those of the text files and of ShellCheck, and of Ruff, mypy and pytest. After the checks, the coach keeps one comment on the pull request up to date with a section for each check that failed, also on a pull request from a fork, and a title that is no Conventional Commit gets one that passes. The comment follows every push and says so once every check passes. On a pull request of a person, the same comment also says what the merge makes: the next version, from the title and a `BREAKING CHANGE:` or `Release-As:` line of the description; the entry that it adds to the changelog; the coverage of the tests against that of `main`, file by file; and, when it changes the website, a link to the website that the check *docs* built, with the address of each page that it changes. While the checks pass, it comments only when it has something of this to say. On your machine, `scripts/check.sh` explains the step that stopped it in the same words.

The explanations are in `.github/checks.toml`, which the blueprint keeps current, and in `.github/checks.project.toml` for the checks of this project alone, whose explanations win. A check that you add to the required checks of `.github/repository.project.toml`, or that `scripts/check-project.sh` runs, comes with its explanation in `.github/checks.project.toml`, in the same pull request: what it found, why that matters and how to fix it, with the commands and a link to read more. The step *Explanations of the checks* of `scripts/check.sh` fails for every required check and every step of `scripts/check.sh` without one, which `python3 .github/blueprint.py coach verify` lists. The comment follows the workflows of the checks that the blueprint sets up; for a workflow of this project alone, such as one of visual tests, name it in the answer `test_workflows` of `.copier-answers.yml`, which the next update of the blueprint brings into `.github/workflows/after-checks.yml`.

A workflow of this project that has something to say about a pull request, such as the size of a module or the result of visual tests, adds a part to the same comment instead of a comment of its own. It keeps the artifact `pr-report-<name>` for the head of the pull request, with the file `report.md`, and `[report.<name>]` in `.github/checks.project.toml` gives the part its title, the text of `about` and, in `replaces`, the marker of its old comment, which the coach then deletes. The coach shows the Markdown of `report.md` only as code, a table with code in each cell, and a part whose first line is `<!-- quiet -->` brings no comment while the checks pass.

## Pull requests fix themselves

What a command can fix, a pull request fixes by itself. When a check fails, its job runs the commands of `autofix` from `.github/checks.toml` on the head of the pull request, such as the fix of the text files or of the format of the code, and keeps the files that they changed. After the checks, the fix bot commits them as one commit onto a branch of this repository, also one of Renovate, and the checks run again: pull the branch before you push again. On a pull request from a fork, it suggests the fixes at their lines, and **Commit suggestion** takes each. A pull request with the label `no-bot-fixes` gets no commit of the bot. On your machine, `python3 .github/blueprint.py fix run` runs the same commands, `python3 .github/blueprint.py fix text` fixes the text files alone, and `python3 .github/blueprint.py fix version` writes the version of the release bot back into each file where a hand changed it.

Every explanation says in `autofix` how its check fixes itself: the commands, a list in which `{blueprint}` stands for `python3 .github/blueprint.py`, or a sentence with the reason why no command can; `python3 .github/blueprint.py coach verify` lists each explanation without one. The fix bot takes the fixes of the runs of Lint and of the CI alone: a check in a workflow of this project's own names its commands in `autofix` for a person, and the bot doesn't commit them yet ([Dennis-Otto/repo-blueprint#429](https://github.com/Dennis-Otto/repo-blueprint/issues/429)). The bot runs nothing of a pull request with a token that can write, and commits only text files that the commit has already, outside `.git` and the workflows.

## Website

MkDocs builds the website from `mkdocs.yml` and the pages in `docs/`. The check *docs* builds it strictly in every pull request, so that a broken link fails; after the build, lychee checks every link and anchor of the built pages, also those written in HTML, without asking a server, `python3 .github/blueprint.py site-check site` what the hooks of the website promise, such as a sitemap in every folder of pages and the 404 page in the default language, that no page loads more than 1,200 KB at once on a phone, and that every page shows each picture of its Markdown, the parts of the README included, and `scripts/check-site.sh`, where it exists, the website as this project alone does. Every change of `main` publishes it on GitHub Pages, signs its provenance, which `SECURITY.md` shows how to verify, and asks the published website for its pages. To see it while you write, at <http://127.0.0.1:8000>:

```sh
python3 -m venv .venv-docs
.venv-docs/bin/pip install --require-hashes -r .github/docs-requirements.txt
.venv-docs/bin/mkdocs serve
```

On Windows, use `py -3` in place of `python3` and `.venv-docs/Scripts/` in place of `.venv-docs/bin/`; the dev container sets these tools up on its own. With them, `bash scripts/check.sh` builds the website strictly as well and checks what its hooks promise, as the check *docs* does, and without them it leaves that to the CI. The preview cards for social media come from the CI alone, because they need the Cairo library, which Windows doesn't have; where it is installed, `CI=true` before the command draws them too.

Every page meets WCAG 2.2 AA, in the light and the dark theme: the stylesheet of the blueprint gives the theme the contrast that it asks for and underlines the links in the text. After each build, the check *docs* opens every page in Chrome and runs [axe-core](https://github.com/dequelabs/axe-core) on it, and names each serious or critical violation in its summary and as an annotation at its page, with a link that explains the fix. For one release of the blueprint it only reports; then it fails the check. To run it on your machine after a build, with Google Chrome, or another Chrome or Chromium named in `CHROME`:

```sh
npm ci --prefix .github/a11y --ignore-scripts
node .github/a11y/check.mjs site
```

One page the website writes by itself: *Automation*, which the hooks of the blueprint make from `.github/workflows/` at every build, in English and, on a website in German, in German too. It shows every workflow with the comment at its top and what starts it, each schedule in words, the checks that `main` requires and the environments and secrets that each one uses, so a new workflow says there what it does once its comment does. A page `docs/automation.md` of your own takes its place.

## Pages in one column

The READMEs, this guide and the pages of `docs/` have one column, so that they read well in the GitHub app and on a phone, which keep columns side by side and squeeze them until the text is a few words wide and the pictures tiny:

- A table holds tabular data, never a layout: no `<table>` that sets a picture beside text, and no `<td width="…">`.
- A picture or a GIF comes at full width below the text that it illustrates.
- A long list, such as every option or every entity, goes into `<details>` with a `<summary>` that names it, so that the page stays short.
- A cell of a Markdown table holds a value, a name or a short sentence: one of more than 30 words is a paragraph, which goes into a list, or onto a page of its own that the table links.

`scripts/check.sh` fails on a `<table>` with a picture and on a cell with a width in a README, a CONTRIBUTING file or a page of `docs/`, with its file and line, and warns of a cell of a Markdown table with more than 30 words, which fails nothing yet. `python3 .github/blueprint.py pages --fix` puts the cells of such a table one below the other, the text before its picture, and leaves out the widths; a table inside a table it leaves to you.

Every page of the website starts with front matter that describes it in one sentence of 50 to 160 characters, written for that page in its language. Search engines show it under the title of the page, and so do the previews of a shared link:

```markdown
---
description: "X01, Cricket, party and training games in Home Assistant: matches, sets, teams and tournaments, against the bot or each other, with every rule explained."
---

# Games and rules
```

`tests/test_docs_links.py` fails for a page without a description, with a description that another page has, or with the words of the template of a decision. A page that moves keeps its file for the old links on GitHub, with front matter such as `moved: installation.md` instead: on the website it leads to that page at once, in the language of the website, and stays out of search engines, the sitemap and the search of the website (`scripts/mkdocs_hooks.py`).

After its title, a page starts with the line back to the overview on GitHub and the link to the other language, such as `[← Documentation](README.md) · [Deutsch](games.de.md)`. The website leaves that line out, because its menu and its switch of the language do the same. The changelog of the website, `docs/changelog.md`, is the line `--8<-- "CHANGELOG.md"`: the hooks include the file with its links written from the root, so that `docs/games.md` there leads to the page of the website, and its pencil edits `CHANGELOG.md`. `README.md`, which HACS shows too, and its German translation `docs/README.de.md` link to the pages of the website, such as `https://dennis-otto.github.io/homedarts-for-autodarts/games.html` and `https://dennis-otto.github.io/homedarts-for-autodarts/de/games.html`, and not to the Markdown on GitHub, which has no search, no dark mode and no switch of the language. Only their link to the changelog stays on GitHub until the website has published its page. `tests/test_docs_links.py` names the address on the website for every link of the two that still leads to a page on GitHub.

## Diagrams

The GitHub app, the stores of the projects and other renderers of Markdown show a `mermaid` block as code, so a diagram is a picture of its source. The source is Mermaid in `docs/diagrams/<name>.mmd`, and `bash scripts/diagrams.sh` draws it, with Docker, as `docs/images/diagrams/<name>.svg` on a white card and `<name>.dark.svg` for a dark theme. The Markdown shows them with paths from its own folder, and the website shows them too, the picture of the theme that the reader switches to:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/diagrams/<name>.dark.svg">
  <img src="docs/images/diagrams/<name>.svg" alt="The title of the diagram: its description">
</picture>
```

- A diagram runs from top to bottom (`flowchart TB`), so that it keeps its size in a narrow column and on a phone, and has `accTitle` and `accDescr` for screen readers, which the `alt` of its picture repeats.
- Labels are text in the pictures: `<br>` breaks a line, and a label in `` "`…`" `` takes `**bold**` and `*italic*`.
- Colors are tints that read in the light and the dark theme, the same in every repository made from the blueprint: blue (`#526cfe`) the blueprint and its bots, orange (`#f59e0b`) you and what is yours, green (`#16a34a`) what comes out, as in `classDef bot fill:#526cfe2e,stroke:#526cfe,stroke-width:2px`.
- A diagram of a German page is `<name>.de.mmd`. A diagram in a README that has a German twin, `README.de.md`, comes in both languages.
- `bash scripts/diagrams.sh --extract` turns every `mermaid` block of the Markdown into a source and its picture, also one in a quote such as a note, and writes the `alt` of each picture from the `accTitle` and `accDescr` of its source. A `mermaid` block inside another block of code, such as an example, or in a comment stays as it is. `scripts/check.sh` fails on a `mermaid` block once a page shows a picture of a diagram, on a source or a picture without the other, and on an `alt` that its source doesn't say.
- The script draws only the sources that a page shows, and those that have a picture already. A source in `docs/diagrams/` that no page shows stays as it is, such as one that a script of the project draws in its own way.
- The check *diagrams* draws the pictures anew when a pull request changes a diagram or adds a `mermaid` block. On a branch of this repository, the diagram bot commits the sources and pictures that it made, with a comment that names the pages it changed, so you need no Docker for a diagram: change its source and push. When the bot can't commit, it says so in a comment on the pull request. For a fork, the summary of the check lists the files and the command, and the run keeps them as its artifact.
- On `main`, the Diagrams workflow draws every diagram after each change of a diagram or a new `mermaid` block, and every week, and keeps one pull request from the branch `bot/diagrams` with what is left, which merges itself once every check passes; without the release app, the run warns and names the command instead. A failed run opens an issue, which the weekly run closes once the bot passes again.

## Screenshots

`bash scripts/screenshots.sh` renders the pictures of this project in place, such as the social preview `.github/social-preview.png` and the screenshots of the documentation and the stores, and `.github/screenshots-paths.txt` lists the files whose change can change them, as the paths of a workflow. Both belong to this project: add a picture to the script, with a fixed clock, size and data, so that the same code renders the same pixels, and its sources to the list.

- The screenshot bot (`screenshot-bot.yml`) runs the script after a change of `main` that touches a file of the list, after every release and every week, without secrets. Each picture whose pixels stayed the same keeps its committed file; when pixels changed, one pull request from `bot/screenshots` holds the new pictures and merges itself once every check passes. Without the script, the bot renders nothing.
- To see what a change of yours changes, run the script, then `python3 .github/blueprint.py screenshots restore`, which gives every picture that looks the same its committed file back and lists the others; commit what is left, or leave it to the bot. It compares the pixels with Pillow, which `python3 -m pip install --require-hashes -r .github/screenshots-requirements.txt` installs.

## Releases

The release bot keeps a pull request titled `chore: release x.y.z` with the next version, up to date with `main` and decided anew with every merge. Its section of the changelog is the text of the fragments in `changelog.d/` and of Unreleased, and it deletes the fragments; without such text, it lists the pull requests. Merging it creates the release with the package for HACS, its SBOM and its signed provenance; the [release guide](docs/releases.md) describes every step. A release of dependency updates merges and publishes itself, once a day, or at once when it fixes a vulnerability.

A line `Release-As: 2.0.0-beta.1` in the description of a pull request sets the version of the next release, for a prerelease for example. After the merge, the release bot writes the title and such a line, or one of `BREAKING CHANGE:`, into the end of the description as an override in an HTML comment, which release-please reads instead of the squash commit, whose parser could fail on another line of the description. A prerelease leaves the fragments and the text of Unreleased to the release that follows it.

A file that the release ships beside its package, such as the zip of a browser extension, comes from `scripts/release-assets.sh` of this project, if it has one. The build of the release runs `bash scripts/release-assets.sh FOLDER VERSION` at the commit of the release, in a job of its own without a token that may write, a secret, `sudo` or Docker, with the Node.js of `.nvmrc` (or that of the runner without one) and `npm ci --ignore-scripts` first where a `package.json` is. The script writes each asset as a file at the top of `FOLDER`, by a name of letters, digits, `.`, `_`, `+` and `-` that starts and ends with a letter or a digit and that no asset of the release has. The release keeps `provenance.*`, `*.intoto.jsonl`, `*.spdx.json`, `*.cdx.json`, `*.openvex.json` and `THIRD_PARTY_NOTICES.md` for itself. The script reaches only GitHub, Node.js and npm. The release attests every asset and attaches it to the draft before it is published; its SBOMs describe the zips and tarballs of the script where no registry delivers the project (`PUBLISH_TO` is `none` or unset), and the verification of the release fails for an asset without its signed provenance.

<!-- The text of this project about its releases starts below this line, and every update of the blueprint keeps it. -->
<!-- The text of this project about its releases ends above this line. -->

By contributing, you agree that your contribution is licensed under the MIT license of this project.
