---
description: "Why a pull request makes a release only when it changes what HACS installs, and how the required check release type keeps the types of the titles to that."
---

# A release changes the package that HACS installs

- Status: accepted
- Date: 2026-11-12

## Context

The type of a pull request's title decides the next release: `fix` makes a patch, `feat` a minor and `!` a major version, and each of them a beta before it, a release discussion and a run of the release verification. Nothing said which type a pull request takes that repairs a workflow, a test or the screenshot tool, so such pull requests were titled `fix(ci):` or `fix:` and wrote a fragment of the changelog. Two of the five stable releases before 2.3.2 changed nothing in the package but its version: 2.3.1 (#651, the jobs of the project stop when Harden-Runner doesn't block) and 2.2.3 (#598, the same screenshots from the same code). Every installation was offered each of them, with a restart of Home Assistant, and the update dialog showed notes about CI jobs and documentation pictures ([#676](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/676)). Of the 78 pull requests among the last 300 merged ones whose titles made a release, 13 changed nothing under `custom_components/` or `blueprints/` and not `hacs.json`.

## Options

1. Write the rule into the guides alone: the next pull request whose author or agent doesn't read them makes the same release.
2. A step of `scripts/check-project.sh`: the CI runs on the event of a push, not on a new title, and a run again reads the title of its event, so a title fixed after a failure would stay red until the next push.
3. A required check of its own, `release type`, that runs on every push and every new title, asks GitHub's API for the current title and the files of the pull request, and fails a title that makes a release without a change of the package.
4. A guard in the release workflow of the blueprint that makes no release when the built package equals that of the last one but for its version: it would stop the release, not the title, and the fragment would wait in the notes of the next real release. It belongs to repo-blueprint and can follow when this check proves too narrow.

## Decision

Option 3, with the rule written into `docs/releases.md` and the notes for coding agents. `feat`, `fix` and `perf`, and every type with `!`, are for a change of `custom_components/`, `blueprints/` or `hacs.json`, which HACS reads for each release; `ci`, `test`, `docs` and `chore` are for the rest, without a fragment. The check is `scripts/release_type.py`, tested with every line and branch, in the workflow `release-type.yml`, which blocks every host but GitHub's and runs without sudo and Docker as every job of the project. It reads the title through the API, not from its event, so that a run again, also one of the flaky-test bot, checks the title that the pull request has. A pull request of more than 3000 files, more than the API lists, passes unchecked. The answer `test_workflows` names the workflow, so that the report of the PR coach on the pull request explains it.

## Consequences

A pull request that changes only workflows, tests, the screenshot tool or the pictures can't make a release; its check names the types that fit its files. A real fix of the integration that forgot its files fails as well, which is right. Dependency updates of the integration change `manifest.json` and pass; those of the tools are `chore`. Each push and each new title runs one short job more. The check looks at paths, not at what changes in them: a `fix` that changes only a comment in the integration still passes, and its author and reviewer decide whether it is one.
