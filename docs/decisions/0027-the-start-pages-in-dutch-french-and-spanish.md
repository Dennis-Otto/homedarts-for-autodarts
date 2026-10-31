---
description: "Why the website has its start page, quick start, installation and FAQ in Dutch, French and Spanish, and shows every other page there in English, with a note."
---

# The start pages of the website in Dutch, French and Spanish, the rest in English

- Status: accepted
- Date: 2026-10-25

## Context

The integration, its cards, the caller and Assist speak English, German, Dutch, French and Spanish, and the documentation is English with a complete German translation ([0005](0005-documentation-in-english-and-german.md), [0009](0009-german-pages-next-to-the-english-ones.md)). The Netherlands and Belgium are among the biggest darts nations, and many Autodarts players speak French or Spanish: a player who follows a link from a forum lands on English pages only, even for the quick start. The website has more than fifty pages, which a maintainer without these languages can't keep in three more languages.

## Options

1. Stay with English and German.
2. Translate every page into Dutch, French and Spanish.
3. Translate the pages that decide whether someone tries the integration, the start page, the quick start from zero to the scoreboard, the installation with the ways to add a board and the frequently asked questions, and show every other page in English on the website of the language, with a note in that language.

## Decision

Option 3. The plugin mkdocs-static-i18n builds a website for each language in its folder, `/nl/`, `/fr/` and `/es/`, from the pages named like the English ones with the code of the language, such as `docs/faq.nl.md`, with menus, search, dates and the switch of the theme in that language. A page that a language lacks is shown in English there, under the menu of the language: the hooks of the blueprint mark its text as English, keep it out of search engines, which list the English page instead, and out of the sitemap, and `scripts/mkdocs_hooks.py` names no versions in other languages for it and gives it a note in the language of the website, which `extra.untranslated` of the language in `mkdocs.yml` words and which links to the translation issue of the language. The search of each website finds its own pages and the English ones it shows.

## Consequences

A change of one of the four pages changes it in five languages where it can, and asks native speakers in the translation issue of the language where it can't. Each translated page states only what changes seldom and links to the English pages for the details; the tests check its links, its counts of blueprints and cards and the oldest release of Home Assistant that it names, as in English and German. A further page of these languages needs no change of the hooks, only a file with the name of the language. A further language needs its entry in `mkdocs.yml`, in `FURTHER` of `scripts/mkdocs_hooks.py` and in `WEBSITE_LANGUAGES` of the live demo, whose tests fail until all three agree. The project hook removes the versions that the blueprint writes into the head of an untranslated copy; [repo-blueprint#428](https://github.com/Dennis-Otto/repo-blueprint/issues/428) fixes that in the blueprint, together with its preview addresses and the style and spelling hints for these languages.

Update of 2026-10-31: the pages were reviewed against the words of the integration and of the menus of Home Assistant ([#480](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/480), [#481](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/481), [#482](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/482)), which `tests/test_website_translations.py` now checks. Those issues are closed with the review, so the note of an untranslated page and the start pages link to the section Translations of `CONTRIBUTING.md`, which stays, and a later request to native speakers is an issue of its own with the label `translations`.
