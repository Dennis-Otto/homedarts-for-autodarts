# Notes of this project for coding agents

HomeDarts for Autodarts: Home Assistant integration for Autodarts boards and any dartboard: local realtime board control, X01, Cricket, party and training games, tournaments and a bot, player statistics with heatmaps, seven dashboard cards and sixteen blueprints, games started by voice. No cloud account needed.

This file belongs to the project: the blueprint wrote it once, and its updates leave it alone. It adds to `AGENTS.md` what a coding agent needs to know about this project alone, such as its architecture, the commands of its own checks and what to watch for in its tests.

## Where things are

- The integration is in `custom_components/homedarts/`, its manifest and version in `custom_components/homedarts/manifest.json`, the HACS metadata in `hacs.json`.
- `README.md` documents installation, configuration and use, `docs/` holds the pages of the website, <https://dennis-otto.github.io/homedarts-for-autodarts/>, and `CHANGELOG.md` lists the changes of every release.
- The tests are in `tests/`; `scripts/check.sh` runs every check.
- The rules of this project for contributors are in `docs/development.md`: the [requirements of a change](../docs/development.md#requirements-for-changes), the [checks with the end-to-end and the browser test](../docs/development.md#tests), the [translations](../docs/development.md#translations) and the [pages of the website](../docs/development.md#pages-of-the-website). `CONTRIBUTING.md` belongs to the blueprint and equals what its template renders: a section of this project there makes every update of the blueprint conflict (#673). New text of the project goes into `docs/development.md`, and into `CONTRIBUTING.md` only between the two marked lines of `## Releases`.

## Names

- The integration is **HomeDarts for Autodarts**, **HomeDarts** for short, with the domain `homedarts` and the repository `Dennis-Otto/homedarts-for-autodarts` ([decision 0026](../docs/decisions/0026-a-name-of-its-own.md)). Up to 1.18 it was called Autodarts, with the domain `autodarts` and the repository `Dennis-Otto/ha-autodarts`; `custom_components/homedarts/takeover.py` takes over the boards set up under that name, and `docs/new-name.md` explains the switch to users.
- *Autodarts* names only the product and the company: Autodarts boards, the Board Manager, Autodarts Desktop, the Autodarts cloud and play.autodarts.io, the device name "Autodarts Board" and the entity IDs that come from it (`sensor.autodarts_board_…`), "a dartboard without Autodarts". Never show the logo of Autodarts, and keep the note that the project is an unofficial community project, not affiliated with Autodarts.

## On Windows

- **The setup of `AGENTS.md` fails on Windows.** `pip install --require-hashes -r requirements-test.txt` stops because the lock file, compiled on Linux, pins no `winrt-runtime`, which bleak needs on Windows alone. pytest couldn't start anyway: Home Assistant runs on Linux and macOS only, and `homeassistant/runner.py`, which pytest-homeassistant-custom-component imports, imports `fcntl`. Neither `--no-deps` nor an install without the hashes gets past that, so leave the lock file and the setup as they are.
- **Run the checks in Docker instead,** with the command of [the checks in Docker](../docs/development.md#the-checks-in-docker), from Git Bash in your worktree: it runs `scripts/check.sh` on a copy of the working tree, with the changes that you haven't committed yet, reads the history of git from the main checkout and changes nothing in either. It takes about three minutes, so give the call a timeout of ten. `npm ci && npm test` runs the tests of the cards on Windows itself.
- **WSL 2 and the dev container** work too, for a clone of their own: [On Windows](../docs/development.md#on-windows) says how. A worktree on a drive of Windows doesn't work in WSL, since its `.git` names the main checkout by a path of Windows.
