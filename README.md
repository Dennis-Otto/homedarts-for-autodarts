<div align="center">

<img src="https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/custom_components/homedarts/brand/icon.png" alt="The icon of the integration: a house with a dartboard" width="96" height="96">

# HomeDarts for Autodarts

**Your Autodarts board, live in Home Assistant: local, realtime and ready for automations.**

[![HACS default repository](https://img.shields.io/badge/HACS-Default-41BDF5.svg?logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz)
[![Latest release](https://img.shields.io/github/v/release/Dennis-Otto/homedarts-for-autodarts?label=release)](https://github.com/Dennis-Otto/homedarts-for-autodarts/releases)
[![Home Assistant 2026.8 or newer](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5.svg?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![Documentation](https://img.shields.io/badge/docs-website-526CFE.svg?logo=materialformkdocs&logoColor=white)](https://dennis-otto.github.io/homedarts-for-autodarts/)
[![CI](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/ci.yml/badge.svg)](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/ci.yml)
[![Coverage 100 %](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://dennis-otto.github.io/homedarts-for-autodarts/development.html#tests)

[**Documentation**](https://dennis-otto.github.io/homedarts-for-autodarts/) · [**Try it live**](https://dennis-otto.github.io/homedarts-for-autodarts/demo/index.html) · [**Deutsche Anleitung**](https://dennis-otto.github.io/homedarts-for-autodarts/de/) · [Quick start](#quick-start) · [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md) · [💛 Sponsor](https://github.com/sponsors/Dennis-Otto)

</div>

**HomeDarts for Autodarts** brings your Autodarts board into Home Assistant: every dart, live from the Board Manager in your network. Any other dartboard plays along too, with its darts entered by hand or sent by a Granboard. HomeDarts for Autodarts is an unofficial community project, not affiliated with Autodarts. Up to version 1.18 it was called Autodarts; [From Autodarts to HomeDarts](https://dennis-otto.github.io/homedarts-for-autodarts/new-name.html) explains the new name and how HomeDarts takes over your boards.

<img src="https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/docs/images/en/hero.webp" alt="Animation: a 301 match on the live card and the scoreboard side by side. Alex throws three triple 20s, the beds light up and the scoreboard counts down to 121; Sam scores 85; Alex checks out 121 with T20, outer bull and D18 for the game shot" width="100%">

**[Try the cards live in your browser](https://dennis-otto.github.io/homedarts-for-autodarts/demo/index.html)**: a 501 against the bot, a Cricket game and a tournament, played by the integration at a simulated board and shown by its cards, on a phone too and in all five languages. Nothing to install.

## Quick start

You need Home Assistant 2026.8 or newer with [HACS](https://hacs.xyz), and an Autodarts board in your network or any dartboard whose darts you enter on a keypad ([requirements](#requirements)).

1. **Install with HACS, then restart Home Assistant.**

   [![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration)

   Or open **HACS** in Home Assistant, search for **HomeDarts** and select **Download**.

2. **Add your board.** With Board Manager 2, Home Assistant usually shows it under **Settings → Devices & services → Discovered** already. Otherwise:

   [![Open your Home Assistant instance and start setting up HomeDarts for Autodarts.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homedarts)

   Choose **Search for boards on this network** or **Enter board address** and confirm. Without Autodarts, choose **Dartboard without Autodarts: enter every dart yourself**.

3. **Add the cards.** Create a complete dashboard in one step: **Settings → Dashboards → Add dashboard → HomeDarts**. Or edit a dashboard, choose **Add card** and search for *HomeDarts*.

New to Home Assistant? [From zero to the scoreboard](https://dennis-otto.github.io/homedarts-for-autodarts/getting-started.html) takes you from nothing to the scoreboard next to your board. The [installation guide](https://dennis-otto.github.io/homedarts-for-autodarts/installation.html) covers manual installation, reconfiguration, updates and removal.

Coming from Autodarts Local, another integration for Autodarts or darts-caller? [Coming from another tool](https://dennis-otto.github.io/homedarts-for-autodarts/coming-from.html) shows what takes their place and how to switch. Short answers to the common questions are in the [FAQ](https://dennis-otto.github.io/homedarts-for-autodarts/faq.html).

## Why

- **Instant and local.** Darts appear in Home Assistant a fraction of a second after they land, straight from the Board Manager in your network. No account, no cloud, no client ID.
- **A whole darts evening.** X01 from 101 to 1001, six Cricket games, nine party games and eight training games, alone, as a match of up to four, a party game of up to eight or a tournament of up to 32, with a scoreboard for the tablet at the board.
- **Your progress in numbers.** Averages, heatmaps of the real dart positions, where to aim with your own spread, personal bests, badges, weekly trends, player profiles, a weekly report and a year of history, all kept in your home.
- **Your home plays along.** Lights for a 180, a caller on your speakers, the board light for the takeout, a photo of your best checkout.

## Features

[Play](#play) · [Like a dart machine](#like-a-dart-machine) · [Train](#train) · [Analyze](#analyze) · [Screen at the board](#screen-at-the-board) · [Automate](#automate) · [Local and private](#local-and-private)

### Play

- X01 from 101 to 1001 with straight, double and master in and out, the 50/50 bull, a round limit and the checkout route after every dart
- Cricket, Cut-Throat Cricket, Tactics, Wild Mouse, Random Cricket and Hidden Cricket on a chalkboard
- Party games for up to eight: Shanghai, Halve-It, Killer, Golf, Baseball, Count-Up, Bermuda, Round the World and Gotcha
- Tournaments of three to 32 players: a round robin with a table, a knockout, a double elimination or groups with a knockout, with their brackets, at one board or on several boards at once

<details>
<summary>Matches, the bot, corrections and more</summary>

- Matches of up to four players with legs and sets, two teams of two, handicap start scores and a bull-off, and a summary of every match
- A bot from level 20 to 120 to play X01 and Cricket against
- A tap corrects a dart the board read wrong; a keypad enters darts by hand, and the last visit can be undone
- No Autodarts? Any dartboard plays along, with every dart entered on the keypad
- Setup hints where no checkout is possible, such as T20 T20 S17 to leave 32

</details>

<img src="https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/docs/images/en/tournament-bracket.webp" alt="Animation: the knockout bracket of five players on the scoreboard; the winners slide into the next round until Alex wins the final" width="100%">

[Games and rules →](https://dennis-otto.github.io/homedarts-for-autodarts/games.html)

### Like a dart machine

- Wild Mouse, also known as Minnesota Cricket, with doubles, triples and three in a bed
- Random Cricket with new numbers every leg, and Hidden Cricket, whose numbers show only once a dart finds them
- Aim hints on the chalkboard: green where a dart scores, amber what to close, and a dart that counted nothing struck through
- Confetti and a golden glow for a 180, a game shot and the match, a glow for a ton
- How to play every game on the new game screen, for guests who never played it, and party games for up to eight players

<img src="https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/docs/images/en/celebration.webp" alt="Animation: a 180 on the scoreboard. Alex throws three triple 20s, a golden glow lights up the scoreboard and confetti flies from its middle, then the scoreboard shows 321 as before" width="100%">

[Wild Mouse →](https://dennis-otto.github.io/homedarts-for-autodarts/games.html#wild-mouse)

### Train

- Training sessions that start with the first dart and keep your last 20 sessions
- Eight training games: Around the Clock, doubles training, checkout training, Bob's 27, the 121 checkout, Catch 40, the JDC Challenge and the singles training
- A daily goal, a training streak and personal bests with an event when you beat one

<img src="https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/docs/images/en/training-game.webp" alt="Animation: Around the Clock on the live card; every hit moves the target and outlines the beds of the next number" width="100%">

[Training games →](https://dennis-otto.github.io/homedarts-for-autodarts/games.html#training-games)

### Analyze

- 3-dart average, first 9 average, checkout and doubles rate
- A heatmap of every bed or of the real dart positions, with the grouping in millimeters
- An aim map: where each player scores the most points per dart with their own spread, the treble 20, the treble 19 or a spot near the bull
- Player profiles with badges in bronze, silver, gold and platinum, and a leaderboard; a profile is renamed with all its numbers, and two names of one player merge into one

<details>
<summary>Trends, reports, the calendar and exports</summary>

- Weekly trends, head-to-head records and the match history of every player
- The hit rate of every double, a weekly report, a training calendar and exports to CSV or JSON
- A backup of every board before it is deleted, which a board added again restores, and the players of two boards merged into one
- Long-term statistics for graphs over weeks and months

</details>

<p align="center"><img src="https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/docs/images/en/heatmap-modes.webp" alt="Animation: the heatmap of the training card switches from beds to numbers and the real dart positions, then to one player's darts" width="520"></p>

[Statistics and players →](https://dennis-otto.github.io/homedarts-for-autodarts/statistics.html)

### Screen at the board

- A scoreboard for a tablet or TV, also through Chromecast, readable from the oche, with a [full-screen button](https://dennis-otto.github.io/homedarts-for-autodarts/scoreboard.html#full-screen) that keeps the screen on
- A new game screen to choose the game, the players and the format at the board, or to start a tournament
- A caller that calls the game through the screen's browser, also with the recorded voice packs of darts-caller or a voice you record with Piper, and for blind and low-vision players every dart, the checkout route and the next target
- Idle mode with a leaderboard, personal bests, today's darts and a clock
- A [stream overlay](https://dennis-otto.github.io/homedarts-for-autodarts/scoreboard.html#stream-overlay) for OBS: the score, the route and the visit over the picture of your stream, see-through or on a key colour

<p align="center"><img src="https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/docs/images/en/lobby.webp" alt="Animation: on the tablet, New game opens the game screen, Cricket and a second player are chosen and the game starts" width="600"></p>

[Scoreboard at the board →](https://dennis-otto.github.io/homedarts-for-autodarts/scoreboard.html)

### Automate

- Board events for every dart, visit, takeout, bust, won leg and match, personal best and more
- Fifteen blueprints: light show, score display, dart and practice callers, highlight photos, reports, alerts, routines, games started and darts entered by voice, and answers from Assist about your darts, which come with the integration and update with it ([see them](#blueprints))
- Start any game with one action, also by voice, tell Assist your darts, as at a dart machine, and ask it "What is my average today?"
- Online matches on play.autodarts.io through an optional bridge *(experimental)*

<img src="https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/docs/images/en/media-gallery.png" alt="The highlight gallery in the media browser of Home Assistant: photos of a checkout of 121, a 180 and a 140" width="100%">

[Automations →](https://dennis-otto.github.io/homedarts-for-autodarts/automations.html)

### Local and private

- Found automatically with Board Manager 2; Board Manager 1 works too
- Nothing leaves your network unless you use the board search or the online bridge; board secrets are never stored
- Seven dashboard cards and an automatic dashboard, in English, German, Dutch, French and Spanish ([languages](https://dennis-otto.github.io/homedarts-for-autodarts/#languages))
- Light on a Raspberry Pi: a message of the board updates only the entities that show what changed ([data updates](https://dennis-otto.github.io/homedarts-for-autodarts/how-it-works.html#data-updates))
- Every rule of the Home Assistant quality scale up to Platinum, 100 % test coverage

<p align="center"><img src="https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/docs/images/en/architecture-dark.png" alt="Architecture: the Board Manager on the board PC sends realtime events to HomeDarts in Home Assistant, which provides entities, board events, cards and automations" width="480"></p>

[How it works →](https://dennis-otto.github.io/homedarts-for-autodarts/how-it-works.html)

## How it compares

How HomeDarts compares with the Autodarts app and its browser extension, with darts-caller and darts-wled, and with the other Home Assistant integrations for Autodarts:

| Feature | HomeDarts | Autodarts app with [Tools for Autodarts](https://github.com/creazy231/tools-for-autodarts) | [darts-caller](https://github.com/Peschi90/darts-caller) and [darts-wled](https://github.com/Peschi90/darts-wled) | Other Home Assistant integrations |
| --- | --- | --- | --- | --- |
| **Runs without the cloud** | Yes, with the [local interface](https://dennis-otto.github.io/homedarts-for-autodarts/how-it-works.html#privacy) of the Board Manager | No, with an [Autodarts account](https://autodarts.com/) | No, darts-caller [signs in to Autodarts](https://github.com/Peschi90/darts-caller#autodarts-login) | Some of them ([details](https://dennis-otto.github.io/homedarts-for-autodarts/coming-from.html#can-it-stay)) |
| **Entities and events in Home Assistant** | Yes, an [event](https://dennis-otto.github.io/homedarts-for-autodarts/entities.html#board-events) for every dart, visit, takeout, bust, leg and match | No | No | Sensors of the current visit or game |
| **Blueprints** | [Fifteen blueprints](https://dennis-otto.github.io/homedarts-for-autodarts/automations.html#blueprints) | No | No | No |
| **Light show** | [Light show](https://dennis-otto.github.io/homedarts-for-autodarts/automations.html#light-show) blueprint, for WLED or any light | WLED, with Tools | WLED, with darts-wled | Your own automations |
| **Caller** | On the [scoreboard](https://dennis-otto.github.io/homedarts-for-autodarts/scoreboard.html#the-caller) or your [speakers](https://dennis-otto.github.io/homedarts-for-autodarts/automations.html#which-caller) | In the app, with a premium voice in [Plus](https://autodarts.com/); more with Tools | Voice packs, with darts-caller | No |
| **Statistics kept at home** | [Yes](https://dennis-otto.github.io/homedarts-for-autodarts/statistics.html): averages, heatmaps, profiles and a year of history | No, in the Autodarts account | No | No |
| **Without an Autodarts board** | Yes, on a [keypad](https://dennis-otto.github.io/homedarts-for-autodarts/without-autodarts.html) or a [Granboard over Bluetooth](https://dennis-otto.github.io/homedarts-for-autodarts/granboard.html) *(experimental)* | Yes, on a keypad or with [Lens](https://autodarts.com/) | No | No |
| **Online matches** | Your darts, and the moments of the match through the [online bridge](https://dennis-otto.github.io/homedarts-for-autodarts/online-matches.html) *(experimental)* | Yes | Yes | Some of them, through the cloud |
| **License and cost** | [MIT](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE), free | Autodarts: a free plan and the paid [Plus](https://autodarts.com/); Tools: [CC BY-NC 4.0](https://github.com/creazy231/tools-for-autodarts/blob/main/LICENSE) | Free, no license stated | MIT, Apache 2.0 or no license file |

*As of October 2026, from the documentation and the code of each project. [Coming from another tool](https://dennis-otto.github.io/homedarts-for-autodarts/coming-from.html) has the details, the sources and how to switch.*

## Requirements

**Home Assistant 2026.8 or newer** with [HACS](https://hacs.xyz), and an Autodarts board in your network, or any dartboard whose darts you enter on a keypad ([play without Autodarts](https://dennis-otto.github.io/homedarts-for-autodarts/without-autodarts.html)), or a Granboard within reach of Home Assistant's Bluetooth ([Granboard](https://dennis-otto.github.io/homedarts-for-autodarts/granboard.html), experimental). No Autodarts account is needed.

- **Board Manager 2**, Autodarts 2 without a screen, is recommended and tested up to 2.0.2; the classic **Board Manager 1** works too.
- A player reports that **Autodarts Desktop** 2.0.2 on Linux works too.
- Autodarts Desktop on Windows and Winmau Autodarts devices such as Autodarts X have not been tested yet; a [compatibility report](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) helps, whether it works or not.

## Blueprints

The integration brings every blueprint along and keeps those you haven't changed up to date with each of its updates. Choose one on the blueprints page of Home Assistant, select your board and you're done; the buttons import one from GitHub, for example one you deleted.

- **Light show.** Your WLED presets or room lights for a 180, a high finish, a bust, a won leg or match, a personal best, an achievement, the winner of a tournament and more, and back to your normal light afterwards.

  [![Import the light show blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Flight_show.yaml)

- **Dart caller.** Every visit announced on your speakers, with a special call for 180, in the language of Home Assistant or with the recorded sounds of a voice pack.

  [![Import the dart caller blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fdart_caller.yaml)

- **Highlight photo.** A picture of the board after a 180 or a checkout, on your phone and in a gallery of the media browser, and with a camera of the room a clip from a few seconds before the dart.

  [![Import the highlight photo blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fhighlight_photo.yaml)

<details>
<summary>Twelve more: visit score, practice caller, score display, takeout, detection, routines, reports, alerts and voice</summary>

- **Celebrate a visit score.** Your actions for every 180, every ton, or any score you choose, the moment the third dart lands.

  [![Import the visit score blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fvisit_score.yaml)

- **Practice caller.** Who needs what, busts and game shots of the practice game on your speakers, in the language of Home Assistant.

  [![Import the practice caller blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fpractice_caller.yaml)

- **Score display.** The score of the practice game after every dart, its checkout route, a 180 and the winner on an AWTRIX 3 or a PixelIt at the board.

  [![Import the score display blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fscore_display.yaml)

- **Takeout actions.** Light up the board while you pull your darts.

  [![Import the takeout actions blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Ftakeout.yaml)

- **Start and stop detection automatically**, based on presence in the darts room.

  [![Import the automatic detection blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fauto_detection.yaml)

- **Training session routine.** Light, detection and calibration follow your training sessions.

  [![Import the training session routine blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Ftraining_session.yaml)

- **Weekly report.** Your training week with the trend of your 3-dart average, as a notification in the language of Home Assistant.

  [![Import the weekly report blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fweekly_report.yaml)

- **Training report.** Your daily summary with the 3-dart average, in the language of Home Assistant.

  [![Import the training report blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Ftraining_report.yaml)

- **Board problem alert** when the board goes offline or a camera fails, with an optional all-clear.

  [![Import the board problem alert blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fboard_alert.yaml)

- **Start a game by voice.** Say "Start 501 for Alex and Sam" to Assist, in English, German, Spanish, French or Dutch.

  [![Import the start a game by voice blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fstart_game_by_voice.yaml)

- **Enter darts by voice.** Say "Alex has 140", "Triple 20" or "next player" to Assist, as at a dart machine, in English, German, Spanish, French or Dutch.

  [![Import the enter darts by voice blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fenter_darts_by_voice.yaml)

- **Ask Assist about your darts.** Ask "What is my average today?", "How many 180s this week?" or "Where should I aim?", in English, German, Spanish, French or Dutch, and the statistics of the board answer.

  [![Import the ask Assist about your darts blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fask_about_darts.yaml)

</details>

## Documentation

Every guide is on the [documentation website](https://dennis-otto.github.io/homedarts-for-autodarts/), in English and [German](https://dennis-otto.github.io/homedarts-for-autodarts/de/), with a search.

<details>
<summary>Every guide, one line each</summary>

### Get started

- [From zero to the scoreboard](https://dennis-otto.github.io/homedarts-for-autodarts/getting-started.html): for Autodarts players without Home Assistant, from nothing to the first game on the scoreboard
- [Installation](https://dennis-otto.github.io/homedarts-for-autodarts/installation.html): requirements, HACS and manual installation, the ways to add a board, updates and removal
- [Play without Autodarts](https://dennis-otto.github.io/homedarts-for-autodarts/without-autodarts.html): any dartboard with every game, the training and the statistics, its darts entered on a keypad
- [Granboard over Bluetooth](https://dennis-otto.github.io/homedarts-for-autodarts/granboard.html): the darts of a Granboard over Home Assistant's Bluetooth and ESPHome proxies, for every game *(experimental)*
- [Frequently asked questions](https://dennis-otto.github.io/homedarts-for-autodarts/faq.html): account, devices, online play, privacy, several boards, screens, languages, updates and switching, in short answers
- [Coming from another tool](https://dennis-otto.github.io/homedarts-for-autodarts/coming-from.html): Autodarts Local, the other integrations, MQTT bridges, darts-caller, darts-wled and Tools for Autodarts compared, and how to switch
- [From Autodarts to HomeDarts](https://dennis-otto.github.io/homedarts-for-autodarts/new-name.html): why the integration has a new name since version 2.0, and how HomeDarts takes over the boards you set up under the old one

### Guides

- [Games and rules](https://dennis-otto.github.io/homedarts-for-autodarts/games.html): how to start a game, matches, teams, handicaps, the bull-off, the match summary, tournaments and the rules of every game
- [Scoreboard at the board](https://dennis-otto.github.io/homedarts-for-autodarts/scoreboard.html): a tablet or TV at the board, the new game screen, tournaments, the caller and idle mode
- [Statistics and players](https://dennis-otto.github.io/homedarts-for-autodarts/statistics.html): sessions, personal bests, heatmaps and dart positions, where to aim, doubles, player profiles, achievements, trends, the leaderboard, reports, calendar, export and backups
- [Automations](https://dennis-otto.github.io/homedarts-for-autodarts/automations.html): fifteen blueprints, board events and ready-to-use examples
- [Online matches](https://dennis-otto.github.io/homedarts-for-autodarts/online-matches.html): moments of online matches on play.autodarts.io in Home Assistant *(experimental)*

### Reference

- [Dashboard cards](https://dennis-otto.github.io/homedarts-for-autodarts/cards.html): all seven cards, the automatic dashboard, every option and accessibility
- [Entities and events](https://dennis-otto.github.io/homedarts-for-autodarts/entities.html): every entity, event, attribute and action
- [How it works](https://dennis-otto.github.io/homedarts-for-autodarts/how-it-works.html): data flow, update intervals, connection behavior, stored data and privacy
- [Troubleshooting](https://dennis-otto.github.io/homedarts-for-autodarts/troubleshooting.html): messages, repairs, diagnostics and logs
- [Security design](https://dennis-otto.github.io/homedarts-for-autodarts/security.html): what is protected, trust boundaries, threats and countermeasures
- [Glossary](https://dennis-otto.github.io/homedarts-for-autodarts/glossary.html): the words of darts and of this integration, in English and German

### Project

- [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md) and [releases](https://github.com/Dennis-Otto/homedarts-for-autodarts/releases): what every version brought; the [roadmap](https://dennis-otto.github.io/homedarts-for-autodarts/roadmap.html) shows what comes next
- [Deutsche Dokumentation](https://dennis-otto.github.io/homedarts-for-autodarts/de/): die komplette Anleitung auf Deutsch

</details>

## Known limitations

- **No cloud match data.** Autodarts issues no client IDs to third-party integrations, so there is no cloud link; everything works with the Board Manager in your network.
- **Online matches through a browser extension.** Busts and game shots of online matches arrive only while the Autodarts page is open with Tools for Autodarts, a third-party extension. [Limitations](https://dennis-otto.github.io/homedarts-for-autodarts/online-matches.html#limitations).
- **Training sessions count darts, not games.** A session counts every dart the board detects; players, legs and checkouts belong to the practice game, which keeps its own statistics.
- **Board Manager updates are installed on the board PC.** The update entity reports new Board Manager 2 versions.
- **Live camera view with Board Manager 2 only.** With Board Manager 1, the camera entities show snapshots.

## Support and contributing

- **Questions and ideas:** the [FAQ](https://dennis-otto.github.io/homedarts-for-autodarts/faq.html) answers the common ones; ask the rest in [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions). **Bugs:** [issues](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose), with the diagnostics of your board. [SUPPORT.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SUPPORT.md) explains where to ask what.
- **Tried it?** A [tester report](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=tester_report.yml) tells us what worked, what didn't and what you miss; short answers are fine.
- **Speak German, Dutch, French or Spanish?** The [translation issues](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues?q=is%3Aissue%20is%3Aopen%20label%3Atranslations) name the texts that are missing or outdated in your language, and how to fix them in the browser, no programming needed.
- **Security:** report vulnerabilities privately as described in [SECURITY.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SECURITY.md).
- **Show your board:** post a photo of your board, the screen next to it and what Home Assistant does with it in [Show and tell](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions/new?category=show-and-tell). It gives others ideas and shows them that the integration runs at boards like theirs.
- **Show it:** for videos, articles and posts, the [creator kit](https://dennis-otto.github.io/homedarts-for-autodarts/creator-kit.html) has facts, ready-to-post texts, videos and pictures, free to use.
- **Contributing:** contributions are welcome; [CONTRIBUTING.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CONTRIBUTING.md) explains the checks. Participation follows the [code of conduct](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CODE_OF_CONDUCT.md) and the project's [governance](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/GOVERNANCE.md).

## Quality and security

[![Docker end-to-end test](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/e2e.yml/badge.svg)](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/e2e.yml)
[![CodeQL](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/codeql.yml/badge.svg)](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/codeql.yml)
[![Secret scan](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/secret-scan.yml)
[![SBOM](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/sbom.yml/badge.svg)](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/sbom.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Dennis-Otto/homedarts-for-autodarts/badge)](https://scorecard.dev/viewer/?uri=github.com/Dennis-Otto/homedarts-for-autodarts)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14935/badge)](https://www.bestpractices.dev/projects/14935)

- Meets every rule of the [Home Assistant integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) up to Platinum ([self-assessment](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/custom_components/homedarts/quality_scale.yaml)), including strict typing.
- 100 % line and branch coverage of the integration, fuzzed cards, a Docker end-to-end test against both Board Manager generations and the oldest supported Home Assistant, a real browser test of every card, and weekly [mutation tests](https://dennis-otto.github.io/homedarts-for-autodarts/development.html#mutation-tests) of the game rules. [Development](https://dennis-otto.github.io/homedarts-for-autodarts/development.html).
- Signed release packages with SLSA provenance. [Releases](https://dennis-otto.github.io/homedarts-for-autodarts/releases.html#signed-release-packages).
- CI jobs that reach only the hosts they need: Harden-Runner blocks every other one, the bots that may write reach GitHub alone, and the Home Assistant under test stays off the internet. [Development](https://dennis-otto.github.io/homedarts-for-autodarts/development.html#network-of-the-jobs).

## Credits and license

HomeDarts started as a fork of [Trkal/HACSAutodarts](https://github.com/Trkal/HACSAutodarts), a cloud-based prototype from April 2026. Since September 2026 it has been rewritten and is maintained independently by [@Dennis-Otto](https://github.com/Dennis-Otto): local realtime control for both Board Manager generations, games, training analytics, dashboard cards, blueprints, tests and documentation. Up to version 1.18 it was called Autodarts and shared the domain `autodarts` with the original; since 2.0 it has the domain `homedarts`, so both can be installed side by side, and the [installation guide](https://dennis-otto.github.io/homedarts-for-autodarts/installation.html#switch-from-the-original-integration) explains how to switch. Thanks to Trkal for the original work and to the Autodarts team for their open local API.

Licensed under the [MIT license](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE). The license covers the icon too. The names Autodarts and Winmau belong to their respective owners. HomeDarts for Autodarts is an unofficial community project, not affiliated with Autodarts.
