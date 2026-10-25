# Notes of this project for coding agents

HomeDarts for Autodarts: Home Assistant integration for Autodarts boards and any dartboard: local realtime board control, X01, Cricket, party and training games, tournaments and a bot, player statistics with heatmaps, seven dashboard cards and sixteen blueprints, games started by voice. No cloud account needed.

This file belongs to the project: the blueprint wrote it once, and its updates leave it alone. It adds to `AGENTS.md` what a coding agent needs to know about this project alone, such as its architecture, the commands of its own checks and what to watch for in its tests.

## Where things are

- The integration is in `custom_components/homedarts/`, its manifest and version in `custom_components/homedarts/manifest.json`, the HACS metadata in `hacs.json`.
- `README.md` documents installation, configuration and use, `docs/` holds the pages of the website, <https://dennis-otto.github.io/homedarts-for-autodarts/>, and `CHANGELOG.md` lists the changes of every release.
- The tests are in `tests/`; `scripts/check.sh` runs every check.

## Names

- The integration is **HomeDarts for Autodarts**, **HomeDarts** for short, with the domain `homedarts` and the repository `Dennis-Otto/homedarts-for-autodarts` ([decision 0026](../docs/decisions/0026-a-name-of-its-own.md)). Up to 1.18 it was called Autodarts, with the domain `autodarts` and the repository `Dennis-Otto/ha-autodarts`; `custom_components/homedarts/takeover.py` takes over the boards set up under that name, and `docs/new-name.md` explains the switch to users.
- *Autodarts* names only the product and the company: Autodarts boards, the Board Manager, Autodarts Desktop, the Autodarts cloud and play.autodarts.io, the device name "Autodarts Board" and the entity IDs that come from it (`sensor.autodarts_board_…`), "a dartboard without Autodarts". Never show the logo of Autodarts, and keep the note that the project is an unofficial community project, not affiliated with Autodarts.
