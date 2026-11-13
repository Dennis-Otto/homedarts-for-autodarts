---
description: "How the integration is released: the release pull request, the notes in the Home Assistant update dialog, betas for testers and signed packages for HACS."
---

# Releases and update notes

[← Documentation](README.md)

HACS installs the GitHub releases of the integration and shows their notes in the Home Assistant update dialog. Releases follow the [repository blueprint](https://github.com/Dennis-Otto/repo-blueprint): nobody chooses a version or writes the notes of a release by hand.

## The release pull request

Every pull request that changes something for users describes it in a fragment of its own in `changelog.d/`, in the words of a user, with the GitHub name of a tester who helped ([which type a pull request takes](#which-type-a-pull-request-takes)). The release bot (**Release** workflow) keeps a pull request titled `chore: release x.y.z` up to date with `main`:

- **The version** follows from the titles of the pull requests merged since the last release: `fix` makes a patch, `feat` a minor and `!` or `BREAKING CHANGE` a major version. Every merge decides it anew. Pull requests of the types `docs`, `test`, `ci`, `chore`, `refactor`, `build` and `style` make no release on their own.
- **The notes:** the fragments of `changelog.d/` and the text of *Unreleased* become the section of the release in `CHANGELOG.md`. The release notes show that text, followed by every pull request of the release.
- **The files of the version:** `custom_components/homedarts/manifest.json`, `version.txt` and `.release-please-manifest.json`.

The release pull request needs the same required checks as every other one, the Docker end-to-end tests with Board Manager 1 and 2 and the oldest supported Home Assistant included, and it is always up to date with `main`, so its checks are those of the commit that becomes the release. Merging it publishes the release; until then, nothing reaches users. A release of dependency updates alone merges itself; every other release waits for the maintainer.

## Which type a pull request takes

A release reaches every installation as an update in HACS, which needs a restart of Home Assistant, and its notes show in the update dialog. So a release has to change what HACS installs, and its notes speak only of what a user of the integration sees:

| The pull request changes | Its type | A fragment in `changelog.d/` |
| --- | --- | --- |
| the integration in `custom_components/homedarts/`, its cards and texts included, the blueprints in `blueprints/`, or `hacs.json` | `feat`, `fix` or `perf`, with `!` for a breaking change | yes, in the words of a user |
| only workflows, the scripts of the checks and the screenshot tool | `ci` | no |
| only tests | `test` | no |
| only the documentation, the website or its pictures | `docs` | no |
| only tools, such as those of the tests of the cards | `chore` | no |

A pull request that repairs a workflow, a test or the screenshot tool is a `ci:` or `test:` even when it fixes a bug of that tool: 2.3.1 and 2.2.3 were releases of `fix(ci):` and `fix:` titles that changed nothing in the package but its version ([#676](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/676)). The check **release type** (`release-type.yml`), which `main` requires, asks GitHub for the files of each pull request and fails a title of the types `feat`, `fix` or `perf`, or one with `!`, when none of them is under `custom_components/` or `blueprints/` or is `hacs.json`; its annotation names the types that fit the files. It reads the title as the pull request has it now, so a new title runs it again by itself, and so does a run of the job again. On your machine, `git diff --name-only origin/main... | TITLE='fix: …' python3 scripts/release_type.py` gives the same answer ([decision 0030](decisions/0030-a-release-changes-the-package.md)).

## Betas

Every pull request of the types `feat`, `fix` and `perf` that reaches `main` also becomes a beta of the next release (the repository variable `BETA_CHANNEL` in `.github/repository.project.toml`): the version of the release pull request with `-beta.N`, such as `2.4.0-beta.2`, with the fragments of `changelog.d/` and the text of *Unreleased* as its notes. It is built, signed and verified like a release, and published as a prerelease that HACS offers only to those who turn on the beta switch ([Betas for testers](installation.md#betas-for-testers)); it announces nothing in the discussions. Updates of dependencies make no beta.

A line `Release-As: 2.0.0-beta.1` in the description of a pull request sets the version of the next release. A version with a suffix such as `-beta.1` becomes a prerelease, which HACS offers only to those who turn on its beta switch for the integration. A beta keeps the fragments of `changelog.d/` and the text of *Unreleased* for the release that follows it, so the final release names everything again.

## Publication

Merging the release pull request creates the release as a draft, with its tag `vx.y.z`, and then:

1. The archive `homedarts.zip` is built from the folder `custom_components/homedarts` of the tagged commit with `git archive`, which HACS installs (`zip_release` and `filename` in `hacs.json`).
2. Every asset gets its signed SLSA build provenance, and the release an SBOM in SPDX and in CycloneDX and the licenses of its third-party components.
3. The complete release is published; GitHub keeps it immutable from then on.
4. The **Release verification** checks the release as its users can: the provenance of every asset, the SBOM, the immutability and the signed commit. It checks the latest release every week as well.

## Signed release packages

| Asset | Contents |
| --- | --- |
| `homedarts.zip` | The folder `custom_components/homedarts` of the released commit, built reproducibly with `git archive` |
| `homedarts-for-autodarts.spdx.json` | The software bill of materials of the release, in SPDX |
| `homedarts-for-autodarts.cdx.json` | The same bill of materials in CycloneDX |
| `THIRD_PARTY_NOTICES.md` | The licenses of the third-party components |
| `provenance.sigstore.json` | A Sigstore bundle with the signed SLSA build provenance of every asset |
| `provenance.intoto.jsonl` | The same signed provenance as in-toto JSON lines, for SLSA tools |

The provenance proves that GitHub Actions built the archive from this repository and commit, so a HACS installation gets exactly the signed file; the download count of `homedarts.zip` shows how often each release was installed. To verify a download:

```sh
gh attestation verify homedarts.zip --repo Dennis-Otto/homedarts-for-autodarts
```

Offline, with the downloaded bundle:

```sh
gh attestation verify homedarts.zip --repo Dennis-Otto/homedarts-for-autodarts \
  --bundle provenance.sigstore.json
```

Version 2.0.0 is the first release as HomeDarts for Autodarts. Up to 1.18.0 the integration was called Autodarts and its repository `ha-autodarts`: those releases carry the archive `autodarts.zip` and the SBOM `ha-autodarts.spdx.json`, and you verify them with `--repo Dennis-Otto/ha-autodarts`, such as `gh attestation verify autodarts.zip --repo Dennis-Otto/ha-autodarts`. Releases up to 1.9.0 carry their bundle as `autodarts.zip.sigstore.json`. Releases 1.0.0 and 1.0.1 were signed before the repository was renamed from `HACSAutodarts` to `ha-autodarts`; verify them with `--repo Dennis-Otto/HACSAutodarts`. Releases before 1.0.0 have no archive.

## Secrets and recovery

The release app opens and updates the release pull request, so that its checks run. Its private key is the secret `RELEASE_AUTOMATION_PRIVATE_KEY` of the environment `release`, which only `main` may use; its client ID is the repository variable `RELEASE_AUTOMATION_CLIENT_ID`, and the variable `PUBLISH_TO` is `hacs`. Every token is short-lived and limited to what its job needs.

If a job of the Release workflow fails, re-run its failed jobs: the draft is completed and published, and nothing is released twice. A published release is never replaced. To leave out a change that is merged already, revert it in a pull request before the release pull request is merged.
