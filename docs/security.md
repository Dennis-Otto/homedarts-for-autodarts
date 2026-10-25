---
description: "How HomeDarts protects your data and your board: what it protects, whom it trusts, the threats it counters and the risks that remain."
---

# Security design

[← Documentation](README.md) · [Deutsch](security.de.md)

This page explains how the integration protects your data and your board, what it trusts, and which risks remain. Report vulnerabilities privately as described in [SECURITY.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SECURITY.md).

## What is protected

| Asset | Where it lives | Protection |
| --- | --- | --- |
| Board API key, TLS key, camera device paths | Board Manager configuration | Dropped as soon as a configuration is read; never stored, logged, shown or included in diagnostics |
| Board ID, board address | Home Assistant config entry | Redacted from diagnostics; the connection history in diagnostics holds counts, kinds of errors and durations, never addresses or error messages |
| Training sessions, practice games and tournaments, personal bests, player names and profiles with head-to-head records, match history, doubles statistics, progress with dart positions, achievements and linked persons, weekly report and training calendar | Home Assistant `.storage` ([stored data](how-it-works.md#stored-data)) | Local only; deleted with the board after a backup of it to the media folder; player names are redacted from diagnostics |
| Backups of a board, with player names | `homedarts/backups/<board ID>` in the media folder | Written before a board is deleted and by administrators and automations; the newest five per board; the media folder needs a login; downloads for administrators only |
| Exports with player names | By default `homedarts/exports` in the media folder; on request `www`, another media folder or a folder of `allowlist_external_dirs` | Written only by administrators and automations, at most 20 in an hour; only into folders where Home Assistant allows writing, never into hidden ones; unguessable file names; downloads for administrators only |
| Control of the board | Board Manager API | Actions only on request of a user or an automation, sent once |
| Address of the online bridge (optional) | Options of the Home Assistant config entry | A random secret of 64 hexadecimal characters, shown only in the options; never logged by the integration or included in diagnostics; replaceable with a new one in the options, which stops the old one at once, also while the bridge is switched off |

## Trust boundaries

```text
 Board PC                      Home Assistant                    Internet
┌────────────────────┐        ┌──────────────────────────┐       ┌──────────────────────┐
│ Board Manager      │  LAN   │ HomeDarts                │ HTTPS │ Autodarts discovery  │
│ port 3180, no login├───────►│ validates every answer   ├──────►│ service, only when   │
└────────────────────┘        │ dashboard cards (browser)│       │ you search for boards│
                              └──────────────────────────┘       └──────────────────────┘
```

1. **Board Manager → integration.** The local API has no login. The integration treats every answer as untrusted input: types, ranges and structures are checked before any value reaches an entity, and unexpected data reads as *unknown* instead of raising errors. Version numbers must look like version numbers, texts longer than 255 characters read as unknown, and realtime notifications are reduced to the same known values as reads. An answer in an unknown format is logged once; if a required read keeps answering like that, a repair notice appears. HTTP 401 or 403 is reported as refused access; the integration never sends credentials to the board.
2. **Integration → dashboard.** The cards render board data in the browser. Every text from the board or the entity registry is escaped, and numbers are validated before they become SVG geometry.
3. **Integration → internet.** Nothing leaves the local network in local mode. *Search for boards* contacts the public Autodarts discovery service once, on request; the integration never contacts it on its own. There is no link to the Autodarts cloud and no Autodarts login ([decision 0025](decisions/0025-no-cloud-link.md)). Taking over the boards set up under the former name of the integration, Autodarts, happens inside Home Assistant as well ([how](how-it-works.md#taken-over-from-the-former-name)).
4. **Network → integration (mDNS).** Any device in the network can announce an Autodarts board. The integration contacts only the addresses the announcement was sent from, never loopback, link-local or multicast addresses, and never an address named only in the announcement's properties. An existing board never moves on its own: when its configured address no longer answers with its board ID, a repair notice offers the new address, and the entry moves only once you confirm it, after the board has been identified there again.
5. **Browser → integration (online bridge, optional).** Off by default. When switched on, Home Assistant accepts the calls of the browser extension Tools for Autodarts at a secret webhook address, by default only from the home network. The integration accepts only the known triggers, fields of limited length and at most 20 calls per second and 120 per minute. A call can only fire an `online_*` board event: it never controls the board or changes stored data. [Online matches](online-matches.md).

## Threats and countermeasures

| Threat | Countermeasure | Evidence |
| --- | --- | --- |
| Secrets from the board leak into Home Assistant | Configuration is reduced to an allow-list of fields right after reading; responses to writes are discarded | Tests check that the API key never appears in entities, diagnostics or logs, also in the Docker end-to-end test |
| Malformed or hostile board data crashes the integration or the cards | Validation of every payload; property-based tests with Hypothesis (training engine) and fast-check (cards) run thousands of random inputs | `tests/test_training_properties.py`, `tests/frontend/properties.test.js` |
| Script injection through board or device names in the cards | All inserted text is escaped; no `innerHTML` with unescaped data | fast-check property "escaped text never contains markup"; `tests/frontend/hostile-text.test.mjs` makes every text, address and player name hostile in all 7 cards, the strategy and the editors, in every view of the demo recording and of its fixtures, also behind every control, and finds no markup ([Development](development.md#hostile-text-in-the-cards)) |
| A wrong board at a configured address shows or controls foreign data | The board ID is checked with every read of Board Manager 2, and with Board Manager 1 at the start and at least every 30 seconds; a mismatch makes the entities unavailable, ignores its realtime notifications and raises a repair notice | `tests/test_local_setup.py`, `tests/test_issues_and_metadata.py`, `tests/test_realtime.py` |
| A device in the network announces itself as a board | Only the announcing addresses are contacted; a board that still answers at its configured address is never moved; otherwise a repair notice asks you first, and the board ID is checked again when you confirm | `tests/test_discovery.py` |
| Someone who learns the address of the online bridge sends fake moments | Off by default; only calls from the home network unless allowed; a secret of 64 random hexadecimal characters; known triggers only, limited lengths, at most 20 calls per second and 120 per minute; events only; a new address in the options, which replaces the old one at once, also when the bridge is switched off | `tests/test_online.py` |
| Many viewers overload the board PC with camera streams | At most two live streams per camera are relayed; further viewers get snapshots | `tests/test_camera_stream.py` |
| Faulty board data or a bug in a game rule cuts the connection | Errors in the training and the games are contained and logged once; high-rate values never run the game logic; reads never overlap | `tests/test_connection.py` |
| An export writes where it should not, overwrites a file or fills the disk | Only administrators and automations export; the folder is resolved before writing, so neither `..` nor a symbolic link leads elsewhere, and it must be one where Home Assistant allows writing (`www`, the media folders, `allowlist_external_dirs`); hidden folders and control characters are refused; at most 20 exports in an hour; every export is a new file | `tests/test_reports_setup.py` |
| A highlight photo writes where it should not or overwrites a file | Only administrators and automations save highlight photos; the folder follows the rules of the exports; a file name keeps only safe characters of the player and the label; every photo is a new file, and one that is cut off is deleted | `tests/test_highlights.py` |
| A voice pack writes or deletes where it should not, or replaces a recorded pack | Only administrators and automations generate voice packs; the folder follows the rules of the exports; a pack name is a plain folder name, without `/` or `..`; the sounds are recorded into a hidden folder beside the pack, which replaces only a pack the integration generated itself (marked with `.homedarts-voice-pack`), checked again right before; one pack at a time | `tests/test_voices.py` |
| Taking over the boards of the former name changes or deletes what is not its own | Only entries that the integration made under its former name are taken over, never those of another integration with the domain `autodarts`; the takeover deletes only the folder `autodarts` in `custom_components` whose manifest names this project; stores, registry entries and media move inside Home Assistant, without a login or a connection to the internet; a media file that is there already stays | `tests/test_takeover.py` |
| The user of a shared wall tablet deletes, renames, relinks or exports the players' data, or saves what a camera sees | `homedarts.delete_player`, `homedarts.rename_player`, `homedarts.link_player`, `homedarts.unlink_player`, `homedarts.export`, `homedarts.backup`, `homedarts.restore`, `homedarts.save_highlight` and `homedarts.generate_voice_pack` are administrator actions, which automations still run; only administrators download exports and backups | `tests/test_services.py`, `tests/test_reports_setup.py`, `tests/test_highlights.py`, `tests/test_backup.py` |
| A restore reads a file it should not, or a backup from a newer version breaks a board | Only administrators and automations restore; the file is resolved before reading, so neither `..` nor a symbolic link leads elsewhere, and it must be a JSON file in a folder where Home Assistant allows reading (`www`, the media folders, `allowlist_external_dirs`), never a hidden one such as `.storage`; a backup is checked before the board unloads, and one from a newer version is refused | `tests/test_backup.py` |
| A player name runs as a formula in a spreadsheet | CSV cells that start like a formula get a leading apostrophe | `tests/test_reports_setup.py` |
| An action runs twice, for example a restart or a reset | Actions are sent once and never retried automatically | `tests/test_local_api.py` |
| A compromised dependency or build | Hash-pinned dependencies, pinned Actions and images, Dependabot, dependency review, CodeQL, Gitleaks, OpenSSF Scorecard | [Development](development.md#continuous-integration) |
| A compromised action, package or test of a pull request sends a token or data from a job of the CI elsewhere | Harden-Runner blocks every host that a job of the project's workflows doesn't need; the bots, which may write, reach GitHub alone and run without sudo and Docker; the Home Assistant of the tests calls nothing on the internet | `tests/test_workflow_network.py`, `tests/test_e2e_offline.py`, [Development](development.md#network-of-the-jobs) |
| A tampered release | Release packages carry Sigstore-signed SLSA provenance | [Releases](releases.md#signed-release-packages) |

## Common weaknesses

How the integration counters the weaknesses of the [CWE Top 25](https://cwe.mitre.org/top25/) that matter for it. CodeQL looks for them in the Python and the JavaScript on every pull request.

| Weakness | Countermeasure |
| --- | --- |
| Cross-site scripting (CWE-79) | Every text from the board, the entity registry or a player is escaped before it becomes HTML, and numbers are checked before they become SVG geometry |
| Path traversal (CWE-22) | Exports, highlight photos and generated voice packs resolve their folder before writing, so neither `..` nor a symbolic link leads elsewhere; the highlight copies serve only plain file names of photos in the highlight folder; voice packs are plain folder names of the voice folder |
| Improper input validation (CWE-20) | Every answer of the Board Manager, every realtime notification and every call of the online bridge is checked against known types, ranges and lengths |
| Exposure of sensitive information (CWE-200, CWE-532) | The board API key is dropped right after reading and never stored, logged or shown; the diagnostics redact board IDs, addresses and player names |
| Missing authorization (CWE-862) | Actions, downloads, highlight copies and the WebSocket commands need a login to Home Assistant; deleting, relinking and exporting the data of players, saving highlight photos and generating voice packs need an administrator |
| Server-side request forgery (CWE-918) | Discovery contacts only the addresses an announcement came from, never loopback, link-local or multicast addresses |
| Uncontrolled resource consumption (CWE-400) | At most two live streams per camera, 20 exports in an hour, and 20 calls a second and 120 a minute for the online bridge |
| Formula injection in exports (CWE-1236) | CSV cells that start like a formula get a leading apostrophe |
| Command and code injection (CWE-78, CWE-94) | The integration runs no commands and evaluates no code, and it has no Python dependencies at runtime |

## Design principles

- **Least privilege:** GitHub workflows run with read-only tokens unless a job needs more; the integration only reads the Board Manager and writes to it only when you or an automation ask for it; the actions that delete, relink or export the players' data are for administrators.
- **Fail safe:** unknown data becomes *unknown*, an unreachable board makes entities unavailable, and a wrong board never shows its data.
- **Local first:** the integration talks to the Board Manager in your network and needs no Autodarts account; the board search and the online bridge are optional.
- **Small attack surface:** no Python dependencies at runtime and no open ports of its own. What the integration adds to Home Assistant's own web server:
  - the files of the cards under `/homedarts/`, such as `/homedarts/<version>/homedarts-card.js`, `homedarts-strategy.js` and the texts of each language in `text/`, served without a login like every other frontend file; they contain code and texts, no data;
  - the nineteen `homedarts.*` actions, which need a login like every action: `start_game`, `correct_dart`, `throw_dart`, `enter_visit`, `next_player`, `undo_visit`, `start_tournament`, `next_tournament_match`, `stop_tournament` and `voice_sound`, which only reads which sounds a voice pack has, for every user, and `delete_player`, `rename_player`, `link_player`, `unlink_player`, `export`, `backup`, `restore`, `save_highlight` and `generate_voice_pack` for administrators, automations and scripts started by them;
  - the downloads of this run's exports at `/api/homedarts/export/`, for administrators or with their signed link that expires after a minute;
  - small copies of the highlight photos at `/api/homedarts/highlights/`, for logged-in users like the photos themselves; only plain file names of photos in the highlight folder are served;
  - the WebSocket command `homedarts/positions`, with which the cards read the dart positions, for logged-in users;
  - the WebSocket command `homedarts/voice_pack`, with which the scoreboard lists the sounds of a voice pack (at most 10,000 files are looked at), for logged-in users;
  - only while the online bridge is on, one secret webhook address.

## Residual risks

- The Board Manager's local API has no login. Anyone who can reach port 3180 in your network can control the board, with or without this integration. Keep the board PC in a trusted network.
- Files in the `www` folder are served at `/local/` without a login to anyone who can reach Home Assistant and knows the file name. Exports go to the media folder, which needs a login, unless you choose `www`; delete exports in `www` you no longer need.
- The local API is not officially supported by Autodarts from Board Manager 2 on. A future Board Manager version may change it; the integration detects the generation and is tested against both.
- The integration talks plain HTTP to the board. If Board Manager 2 announces an HTTPS port, the plain HTTP port it announces is used; TLS to the board is not supported.
- The online bridge relies on the secrecy of its address. Whoever knows it and can reach Home Assistant can fire online board events and the automations that react to them, until you create a new address.
- Anyone in the network can announce a board over mDNS. Home Assistant then shows a discovered board, which is only added after you confirm it.
