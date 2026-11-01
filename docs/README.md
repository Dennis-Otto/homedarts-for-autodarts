# HomeDarts for Autodarts: documentation

[← Project page](https://github.com/Dennis-Otto/homedarts-for-autodarts) · [Deutsche Dokumentation](README.de.md) · [Nederlands](index.nl.md) · [Français](index.fr.md) · [Español](index.es.md)

Everything about HomeDarts for Autodarts, the Home Assistant integration for Autodarts boards and any other dartboard: how to set it up, play and train with it, put a scoreboard next to the board, follow your statistics and let your home join in. The [website of the documentation](https://dennis-otto.github.io/homedarts-for-autodarts/) has the same pages, with a search and a switch to German; its start page, quick start, installation and FAQ are also in [Dutch](https://dennis-otto.github.io/homedarts-for-autodarts/nl/), [French](https://dennis-otto.github.io/homedarts-for-autodarts/fr/) and [Spanish](https://dennis-otto.github.io/homedarts-for-autodarts/es/). HomeDarts for Autodarts is an unofficial community project, not affiliated with Autodarts.

<img src="images/en/hero.webp" alt="Animation: a 301 match on the live card and the scoreboard side by side. Alex throws three triple 20s, Sam scores 85, and Alex checks out 121 for the game shot" width="100%">

**Jump to:** [Get started](#get-started) · [Guides](#guides) · [Reference](#reference) · [Project](#project) · [Use cases](#use-cases) · [Supported devices](#supported-devices) · [Languages](#languages)

## Get started

- [From zero to the scoreboard](getting-started.md): for Autodarts players without Home Assistant: set up Home Assistant and HACS, install the integration, add the board and play the first game on the scoreboard
- [Installation and setup](installation.md): requirements, HACS and manual installation, the ways to add a board, reconfiguration, updating and removal
- [Play without Autodarts](without-autodarts.md): any dartboard with every game, the training and the statistics: set it up, enter the darts on a keypad, and what is different
- [Granboard over Bluetooth](granboard.md): the darts of a Granboard over Home Assistant's Bluetooth and ESPHome proxies, for every game: set it up, play, the connection and how to check every bed *(experimental)*
- [Frequently asked questions](faq.md): short answers about the account, devices, online play, privacy, several boards, screens, languages, updates and switching
- [Coming from another tool](coming-from.md): how HomeDarts compares with Autodarts Local, the other integrations, MQTT bridges, darts-caller, darts-wled and Tools for Autodarts, and how to switch from them
- [From Autodarts to HomeDarts](new-name.md): why the integration has a new name since version 2.0, and how HomeDarts takes over your boards with their entities, statistics and dashboards

## Guides

- [Games and rules](games.md): every game at a glance, four ways to start one, matches, the match summary, teams, handicaps, the bull-off, tournaments and the rules of X01, the Cricket games, the party games and the training games
- [Scoreboard at the board](scoreboard.md): a tablet or TV next to the board: setup, landscape and portrait, the new game screen, tournaments, the caller and idle mode
- [Statistics and players](statistics.md): training sessions, personal bests, the heatmap and dart positions, where to aim, progress over time, doubles, player profiles, the rating, achievements, trends and grouping, the leaderboard, the weekly report, the training calendar, exports and backups
- [Automations](automations.md): sixteen blueprints, their settings, board events and ready-to-use examples
- [Online matches](online-matches.md): busts, won legs and matches of online matches as board events, with the browser extension Tools for Autodarts *(experimental)*

## Reference

- [Dashboard cards](cards.md): the live card, the training card, the board status card, the scoreboard, the doubles card, the players card, the leaderboard card and the automatic dashboard, with every option and accessibility
- [Entities and events](entities.md): every entity, board event, state, attribute and action, and which Board Manager generation provides it
- [How it works](how-it-works.md): architecture, update intervals, connection behavior, Board Manager generations, address changes, training and records, stored data and privacy
- [Troubleshooting](troubleshooting.md): setup messages, repairs, unavailable entities, failing actions, diagnostics and logs
- [Security design](security.md): what is protected, trust boundaries, threats and countermeasures
- [Glossary](glossary.md): the words of darts and of this integration, with their German terms

## Project

- [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md): what every version brought
- [Roadmap](roadmap.md): released versions and what comes next
- [Development](development.md): tests, Docker end-to-end test, demo instance, accessibility check, screenshots, the screenshot bot, the visual check and CI
- [Releases](releases.md): how versions and release notes are produced
- [Creator kit](creator-kit.md): facts, descriptions, ready-to-post texts for forums, Reddit and Discord, videos, animations and pictures for YouTubers, streamers and bloggers, free to use

## Use cases

### Train with a purpose

Follow your average, your 180s and where your darts land after every session, and let a daily goal and a training streak keep you going.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="images/en/training-card-light.png">
    <img src="images/en/training-card.png" alt="Training card with 3-dart average, heatmap, statistics and recent visits" width="480">
  </picture>
</p>

[Statistics →](statistics.md)

### A darts night with friends

Choose the game on the tablet at the board or start a tournament, let the scoreboard keep the score and call the game, and watch the table or the leaderboard between games.

<p align="center"><img src="images/en/lobby.webp" alt="Animation: a game is chosen on the new game screen of the tablet at the board and starts on the scoreboard" width="600"></p>

[Scoreboard →](scoreboard.md)

### Atmosphere

Light shows for a 180 or a won match, a dart caller on your speakers and the board light for the takeout.

<img src="images/en/blueprint-light-show.png" alt="A new automation from the light show blueprint with a section for every moment of the game" width="100%">

[Automations →](automations.md)

### Keep the highlights

A photo of the board after every 180 or checkout, on your phone and in a gallery by month.

<img src="images/en/media-gallery.png" alt="The highlight gallery in the media browser with photos of a checkout and two high visits" width="100%">

[Highlight gallery →](automations.md#highlight-gallery)

### Progress over months

Long-term graphs, a weekly report on your phone and a training calendar with a year of sessions and matches.

<p align="center"><img src="images/en/dashboard-trends.png" alt="Graphs of darts per day, the 3-dart average and practice legs over four weeks" width="480"></p>

[Progress over time →](statistics.md#progress-over-time)

### A board that looks after itself

Start the detection when you enter the darts room, stop it when you leave, and get a notification when the board goes offline or a camera fails.

<picture>
  <source media="(prefers-color-scheme: light)" srcset="images/en/status-card-light.png">
  <img src="images/en/status-card.png" alt="Board status card with detection, connections, board PC load and cameras" width="100%">
</picture>

[Blueprints →](automations.md#blueprints)

<!-- --8<-- [start:devices-and-languages] -->

## Supported devices

| Setup | Supported | Tested with |
| --- | --- | --- |
| Board Manager 2: Autodarts 2 without a screen (headless) | 2.x | 2.0.0, 2.0.2 and 2.1.0 |
| Board Manager 1 (classic app) | 1.x | 1.0.7 |
| Autodarts Desktop on Linux | Works, as reported by a player | 2.0.2 on Ubuntu 24.04 ([report](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/105)) |
| Autodarts Desktop on Windows and other systems | Not tested yet | – |
| Winmau Autodarts devices such as Autodarts X | Not tested yet | – |
| Cameras | Any number supported by the Board Manager | 3 |
| Home Assistant | 2026.8 or newer ([why](decisions/0022-home-assistant-2026-8-as-the-oldest-release.md)) | 2026.8.0 and 2026.9.4 |

Any board hardware that runs the Autodarts Board Manager works, because the integration talks to the Board Manager, not to the cameras. Rows reported by a player were tested by a player on their own board, not by the project.

Since September 2026, the Autodarts documentation describes the Board Manager as the browser interface of Autodarts 0.x that is not supported from version 2 on. The local interface on port 3180 that the integration uses still answers on Autodarts 2.1.0. If an update changes it, the integration shows a repair notice instead of failing silently (see [troubleshooting](troubleshooting.md#repairs)). If your setup is not in the table, a [compatibility report](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) helps, even when everything works.

On **Board Manager 2.1**, the integration works as before, with these differences:

- The switch *Automatic recalibration* is unavailable, because Board Manager 2.1 no longer has this option, and the generated dashboard leaves it out. *Calibrate on start* and *Distortion correction* remain.
- The buttons *Start camera streams* and *Stop camera streams* are unavailable, because Board Manager 2.1 no longer has these commands. The live view of the cameras works without them.
- *Hand detected*, *Image stable*, *Darts partially removed* and *Darts fully removed* come from the second socket of the board, `/api/events/system`, the moment they change. Only if that socket stays away do they update every 2 seconds while the detection runs, and a hand that is at the board for a moment only may not show then.
- A board that [sees a hand all the time](entities.md#a-hand-the-board-sees-all-the-time) detects no darts, and a calibration doesn't clear it: a real board did this when its light ring was switched on with the detection running. A repair notice says so and restarts the detection, and if a routine switches the light, switch it before the detection starts, or restart the detection after it.

## Languages

The integration speaks English, German, Dutch, French and Spanish: setup, options, entities and their states, actions, messages and repairs, the cards with their editors and the caller of the scoreboard. It follows the language of Home Assistant; a regional variant such as `de-CH` or `es-419` counts as its language. Other languages see English.

- Home Assistant names the entities in the language of the server (**Settings → System → General**); states and cards follow the language of your user profile.
- The caller speaks the card's language with a voice of your browser or tablet for that language, or with a [voice pack](scoreboard.md#voice-packs) of recorded calls; `homedarts.generate_voice_pack` records one in the language you choose.
- The documentation is in English and German; its start page, quick start, installation and frequently asked questions are also in Dutch, French and Spanish, whose websites show the other pages in English. The settings of the blueprints are in English because Home Assistant does not translate blueprints. Their calls still speak all five languages: the integration gives the events the words of the callers and of the weekly report, and the training report its summary, in the language of Home Assistant ([calls in the language of Home Assistant](automations.md#calls-in-the-language-of-home-assistant)). The voice blueprints understand sentences in all five languages. Assist answers in the language of Home Assistant, and in the language of the question for *Ask Assist about your darts*.

Texts that are missing in a language, or older than their English original, are listed in that language's [translation issue](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues?q=is%3Aissue%20is%3Aopen%20label%3Atranslations), which a bot keeps up to date. It explains how to fix them right on GitHub, without programming. Each language has two small files of its own, `translations/<language>.json` for the integration and `frontend/text/<language>.js` for the cards, both in `custom_components/homedarts/`. To improve a translation or add a language, see [translations in CONTRIBUTING.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CONTRIBUTING.md#translations).

<!-- --8<-- [end:devices-and-languages] -->
