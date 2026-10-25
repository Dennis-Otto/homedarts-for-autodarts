---
description: "Why the documentation is written in English, for the Home Assistant community, with a complete German translation for the many German-speaking players."
---

# Write the documentation in English, with a complete German translation

- Status: accepted
- Date: 2026-09-26

## Context

Many Autodarts players are in German-speaking countries, and the maintainer is German; the Home Assistant community writes in English.

## Options

1. English only.
2. English first, with a complete German translation that changes in the same pull request.

## Decision

Option 2. The documentation is in `docs/`, its German translation in `docs/de/`, and every pull request that changes one changes the other. Since [0009](0009-german-pages-next-to-the-english-ones.md), each German page sits next to its English page. Since [0027](0027-the-start-pages-in-dutch-french-and-spanish.md), the start page, the quick start, the installation and the frequently asked questions are also in Dutch, French and Spanish. The integration and its cards speak English, German, Spanish, French and Dutch.

## Consequences

Every change of the documentation is written twice. A bot opens an issue per language when texts of the integration go stale.
