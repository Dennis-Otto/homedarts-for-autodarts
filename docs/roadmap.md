---
description: "What each version of HomeDarts for Autodarts brought, what the next release brings, what comes later and what the integration will not do."
---

# Roadmap

[← Documentation](README.md) · [Deutsch](roadmap.de.md)

This roadmap shows what each version brought, what the next release brings and what comes after it. *Next* and *Later* look at least a year ahead, until October 2027, *Not planned* says what the integration won't do, and *Reach* how many people find it. It is a direction, not a promise: priorities follow feedback from players, and dates depend on spare time. Ideas and votes are welcome as [feature requests](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose).

## Version 1.0: the local foundation

Released features, all of them working without the Autodarts cloud:

- Local realtime connection to Board Manager 1 and 2, with automatic discovery.
- Controls, board settings, camera health and Board Manager updates.
- Training analytics with hits per bed, visit history and the `visit_completed` event.
- Three dashboard cards, an automatic dashboard and six blueprints.
- Documentation in English and German.

## Version 1.1: training sessions

- Training sessions that start with the first dart or on purpose, end after a pause and keep a summary of the last 20 sessions.
- The `session_started` and `session_ended` events, and a seventh blueprint that ties light, detection and calibration to a session.
- The last visits in the live card, the session state and past sessions in the training card.
- Board PC details from Board Manager 2: operating system, processor and detection software.

## Version 1.2: practice games and live cameras

- X01 practice games (301, 501, 701) on the local board: remaining score, busts, double out, checkout routes and the last 10 legs, with the `bust` and `leg_won` events.
- A practice panel in the live card with the checkout route and the bed to aim at next, and the practice controls in the automatic dashboard.
- Live camera streams from Board Manager 2 instead of snapshots.
- Camera state right after the detection starts or stops, instead of after the next poll.

## Version 1.3: matches, training games and statistics

- X01 matches for two to four players at one board: the turn passes when the darts are pulled, with legs, sets, player names and a scoreboard in the live card.
- Training games: Around the Clock, doubles training, checkout training and Bob's 27, with the target outlined on the board.
- Practice statistics: first-9 average, checkout rate, doubles rate and legs per day.
- Two blueprints: a practice caller and a highlight photo after a 180 or a checkout.

## Version 1.4: Cricket, scoreboard and personal bests

- Cricket for one to four players with marks, closed numbers, points and marks per round, and a chalkboard in the live card.
- A scoreboard card and a full-screen scoreboard view for a screen at the board, readable from the oche.
- Personal bests with an event when one is beaten, a training streak in days and a daily goal.
- `homedarts.start_game` starts X01, Cricket or a training game with players, names and format in one action.
- Detection quality: the share of corrected darts, with a repair that recalibrates the board when it rises.

## Version 1.5: party games, player profiles, doubles and a caller

- Shanghai, Halve-It and Killer for one to four players; X01 from 101 to 1001 with double in and a bull-off.
- Player profiles with statistics and personal bests per name, a match history and head-to-head records, and a players card.
- A doubles analysis with the hit rate of every double, a doubles card and personal checkout routes.
- A caller in the scoreboard that announces the game through the browser, off by default.
- `homedarts.delete_player` removes a player profile, for example after a typo in a name.

## Version 1.6: more games, a game lobby, reports and online matches

Released as 1.6.0 on 27 September 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#160) has the details.

| Topic | What it brings | Status |
| --- | --- | --- |
| **More games** | Cut-Throat Cricket, Tactics, Golf, Baseball and Count-Up; the training games 121 checkout, Catch 40, JDC Challenge and singles training | Done |
| **Handicap starts and teams** | Different X01 start scores per player in the same match, for example 501 against 301, and two teams of two in X01 and the Cricket games | Done |
| **Official rules** | PDC set order, match results as 3–2, checkout routes like the professional charts, the bull-off of the WDF and PDC rules | Done |
| **A scoreboard to start games** | A new game screen at the board, idle mode with a leaderboard, and the pictures of players linked to persons of Home Assistant | Done |
| **Reports** | A weekly report with a blueprint, a training calendar of a year and exports to CSV or JSON | Done |
| **Highlights and light** | A highlight gallery in the media browser and a light show blueprint | Done |
| **Online matches** *(experimental)* | Busts, won legs and matches of online matches through the browser extension Tools for Autodarts | Done |
| **Tournament mode** | Round robin or knockout for three to eight named players at one board: the table or bracket on the scoreboard, the next match starts by itself, and the results go into the player profiles | Done |
| **Match summary** | Every player's averages, checkout rate, highest checkout, 180s and best leg after a match, on the scoreboard, the live card and in `match_won` | Done |
| **Achievements** | Milestones per player in tiers, such as the first 180, a ton-plus checkout, a nine-darter or a ten-day streak, each with an event and shown as badges | Done |
| **Trends and heatmaps per player** | Average, checkout rate and doubles rate per week as a trend, every player's own heatmap and a leaderboard of the records of all players | Done |
| **Heatmap of the dart positions** | A heatmap that draws where every dart landed, from the positions the board reports, with the grouping in millimeters; the card switches between beds, numbers and positions | Done |
| **A bot and corrections** | A bot from level 20 to 120 in X01 and the Cricket games, corrections with a tap, darts entered by hand on a keypad, undo of the last visit, and setup hints where no checkout is possible | Done |
| **Dutch, French and Spanish** | The integration, the cards and the caller in three more languages, with tests that keep every language complete | Done |
| **Documentation** | Illustrated guides for games, the scoreboard and statistics, a glossary and an accessibility section | Done |

## Version 1.7: dart positions you can trust

Released as 1.7.0 on 28 September 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#170) has the details.

- The positions heatmap of the training card follows every dart live.
- Corrected darts leave the board's misread position behind, or take the spot you tap on the scoreboard's board, which gives the bed at the same time.

## Version 1.8: every card on every screen

Released as 1.8.0 on 28 September 2026 and 1.8.1 on 29 September 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#180) has the details.

- Every card fits from a 360 pixel phone to a 27 inch touch monitor, upright and on its side, with controls of at least 40 pixels for a finger.
- Corrections on the live card too, with a loupe and a zoom on every touch screen.
- A pencil shows what a tap edits, an arrow what a tap opens; states change with calm animations.
- The doubles card counts every double hit, in every game.
- Nothing on the cards changes its height while a game goes on.

## Version 1.9: games by voice

Released as 1.9.0 on 29 September 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#190) has the details.

- A blueprint that starts a game when you tell Assist, for example "Start 501 for Alex and Sam" or "Starte das Spiel Cricket für Alex", in English and German, with an answer in words.
- What a mouse shows as a tooltip, a tap shows too.
- The game settings of the automatic dashboard in a view of their own.

## Version 1.10: like a dart machine

Released as 1.10.0 on 8 October 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1100-2026-10-08) has the details.

- Wild Mouse, also known as Minnesota Cricket: Cricket plus doubles, triples and three in a bed.
- Aim hints on the chalkboard of every Cricket game, and darts that counted nothing struck through.
- Confetti and a golden glow for a 180, a game shot and the match on the scoreboard.
- How to play every game on the new game screen.
- Party games for up to eight players.
- A takeout that Board Manager 2.0.2 never finishes is freed by itself.
- Animations and diagrams of the new games, and what changes on the way from Autodarts 1.x to 2.x.

## Version 1.11: play without Autodarts

Released as 1.11.0 on 9 October 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1110-2026-10-09) has the details.

| Topic | What it brings | Status |
| --- | --- | --- |
| **Dartboard without Autodarts** | Any dartboard as a board of its own, every dart entered on the keypad of the live card and the scoreboard, with every game, the training and the statistics ([guide](without-autodarts.md)) | Done |
| **Autodarts later** | A dartboard without Autodarts becomes an Autodarts board when one arrives, and keeps its statistics ([how](without-autodarts.md#autodarts-later)) | Done |
| **The score of a visit** | X01 visits entered as a score, such as 140, with the darts at a double on a checkout ([how](without-autodarts.md#enter-your-darts)) | Done |
| **The keypad on the live card** | The scoreboard's keypad below the darts of the live card, with *Next player* and *Undo last visit*, while *Practice manual entry* is on ([live card](cards.md#live-card)) | Done |

## Version 1.12: darts by voice

Released as 1.12.0 on 9 October 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1120-2026-10-09) has the details.

| Topic | What it brings | Status |
| --- | --- | --- |
| **Darts by voice** | "Alex has 140", "Checkout with two darts", "Triple 20", "Next player" and "Undo" to Assist, in English and German, with an answer in the caller's words ([blueprint](automations.md#enter-darts-by-voice)) | Done |
| **Answers of the actions at the board** | `homedarts.enter_visit`, `homedarts.throw_dart`, `homedarts.next_player` and `homedarts.undo_visit` answer in words: what a visit scored and left, who throws next, or why they refused ([actions](entities.md#enter-a-visits-score-homedartsenter_visit)) | Done |

## Version 1.13: the rules of play.autodarts.io

Released as 1.13.0 on 14 October 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1130-2026-10-14) has the details.

| Topic | What it brings | Status |
| --- | --- | --- |
| **X01 as on play.autodarts.io** | In and out modes *Straight*, *Double* and *Master*, the bull mode *50/50*, in which the outer bull scores 50, and *Max rounds* from 1 to 50, after which the lowest score wins the leg; on the new game screen, with four new entities and in `homedarts.start_game`, also against the bot ([X01](games.md#x01)) | Done |

## Version 1.14: the best aim from your own spread

Released as 1.14.0 on 14 October 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1140-2026-10-14) has the details.

| Topic | What it brings | Status |
| --- | --- | --- |
| **Where to aim** | A fourth mode of the heatmap, *Aim*, colors the board by the points per dart that the spread of your own darts scores at every spot and rings the best aim, compared with the treble 20, the treble 19 and the bull, from 30 darts aimed at a treble; the player profile has it for automations and Assist ([where to aim](statistics.md#where-to-aim)) | Done |
| **Voice in Spanish, French and Dutch** | Games started and darts entered by voice in Spanish, French and Dutch as well as English and German, such as "Juega 501 para Alex y Sam", "Alex a fait 140" or "Dubbel 16", with numbers as digits or as words ([blueprint](automations.md#start-a-game-by-voice)) | Done |

## Version 1.15: three party games, voice packs and a live demo

Released as 1.15.0 on 18 October 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1150-2026-10-18) has the details.

| Topic | What it brings | Status |
| --- | --- | --- |
| **Bermuda, Round the World and Gotcha** | Three more party games for one to eight players, as on play.autodarts.io, from the new game screen, by voice or with `homedarts.start_game` ([party games](games.md#party-games)) | Done |
| **Voice packs** | The callers play recorded calls, and a voice pack of darts-caller works as it is; *Generate voice pack* records a complete pack with any text-to-speech engine of Home Assistant, such as Piper ([voice packs](scoreboard.md#voice-packs)) | Done |
| **Live demo** | The [live demo](https://dennis-otto.github.io/homedarts-for-autodarts/demo/index.html) plays a 501 against the bot, a Cricket game and a tournament with the cards in the browser, on a phone too and in five languages, with nothing to install | Done |

## Version 1.16: pixel displays, Chromecast and callers in your language

Released as 1.16.0 on 18 October 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1160-2026-10-18) has the details.

| Topic | What it brings | Status |
| --- | --- | --- |
| **The score on a pixel display** | The blueprint *Autodarts: score display* shows the practice game on an AWTRIX 3, such as the Ulanzi TC001, or on a PixelIt at the board: the score after every dart, the checkout route, a 180, a bust and the winner ([score display](automations.md#score-display-on-an-awtrix-or-a-pixelit)) | Done |
| **The scoreboard through Chromecast** | Home Assistant Cast shows the cards and the automatic dashboard on a TV with a Chromecast or on a Google Nest Hub ([Home Assistant Cast](scoreboard.md#on-a-tv-with-home-assistant-cast)) | Done |
| **Calls in the language of Home Assistant** | The dart caller, the practice caller, the training report and the weekly report speak the language of Home Assistant, in English, German, Dutch, French and Spanish, without a message of your own ([calls](automations.md#calls-in-the-language-of-home-assistant)) | Done |
| **A caller for blind and low-vision players** | The scoreboard's caller calls every dart as it lands, the checkout route after every dart and the next target of a training or party game, also from a voice pack ([for blind and low-vision players](scoreboard.md#for-blind-and-low-vision-players)) | Done |
| **The cloud link** | Prepared and kept hidden: the moments of online matches from the Autodarts cloud, without a browser extension, as the same board events as from the online bridge, also for boards without a Board Manager in your network such as Lens | Removed, since Autodarts issues no client IDs to third parties ([decision 0025](decisions/0025-no-cloud-link.md), see [Not planned](#not-planned)) |
| **Quicker on a Raspberry Pi** | Every action saves the training once instead of twice, setup hints are found in a tenth of the time, and Home Assistant loads the integration up to half a second faster ([setup hints](how-it-works.md#setup-hints)) | Done |

## Version 1.17: big tournaments, streaming and Granboard

Released as 1.17.0 on 19 October 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1170-2026-10-19) has the details.

| Topic | What it brings | Status |
| --- | --- | --- |
| **Tournaments of up to 32 players** | A knockout of up to 32 players, a double elimination and groups with a knockout, with the tables of the groups and the losers' bracket on the scoreboard ([tournaments](games.md#tournaments)) | Done |
| **A tournament on several boards** | One tournament on two boards or more at once, Autodarts boards and dartboards without Autodarts alike, with the expected end of the tournament on every scoreboard ([a tournament on several boards](games.md#a-tournament-on-several-boards)) | Done |
| **Random Cricket and Hidden Cricket** | Cricket on six numbers of 1 to 20, drawn anew for every leg, and the bull, as on Scolia, Granboard and Dartsmind; Hidden Cricket keeps the numbers hidden until a dart finds one, and both play against the bot and in tournaments too ([Random Cricket](games.md#random-cricket), [Hidden Cricket](games.md#hidden-cricket)) | Done |
| **Stream overlay and highlight clips** | The scoreboard alone over the picture of a stream in OBS Studio or Streamlabs, and every big moment as an MP4 clip beside its highlight photo ([stream overlay](scoreboard.md#stream-overlay), [highlight clips](automations.md#highlight-clips)) | Done |
| **Questions to Assist** | "What is my average today?", "How many 180s this week?", "What is my best checkout?", "Who leads the leaderboard?" and "Where should I aim?" to Assist, in English, German, Spanish, French and Dutch, answered from the statistics of the board ([blueprint](automations.md#ask-assist-about-your-darts)) | Done |
| **Blueprints that come with the integration** | All fifteen blueprints on the blueprints page without importing them, and every update brings their new versions; a blueprint you changed stays yours ([updates of the blueprints](automations.md#updates-of-the-blueprints)) | Done |
| **Granboard over Bluetooth** *(experimental)* | A Granboard sends its darts over Bluetooth, also through an ESPHome Bluetooth proxy, for every game, the training and the statistics, without entering a dart ([Granboard over Bluetooth](granboard.md)) | Done; not yet tested at a real board (see [Next](#next)) |

## Version 1.18: groups and qualifiers at the start of a tournament

Released as 1.18.0 on 19 October 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1180-2026-10-19) has the details.

| Topic | What it brings | Status |
| --- | --- | --- |
| **Groups and qualifiers** | *Tournament groups* and *Tournament qualifiers per group* join the tournament settings: *Start tournament* and `homedarts.start_tournament` play groups and a knockout with them, and the new game screen takes them as its defaults ([tournaments](entities.md#tournaments)) | Done |
| **In the HACS default repository** | Search for *Autodarts* in HACS and download it, without adding a custom repository first ([install](installation.md#with-hacs-recommended)) | Done on 20 October 2026 ([hacs/default#11306](https://github.com/hacs/default/pull/11306)) |

## Version 2.0: HomeDarts for Autodarts

Released as 2.0.0 on 21 October 2026; the [changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#200-2026-10-21) has the details.

| Topic | What it brings | Status |
| --- | --- | --- |
| **A name of its own** | The integration is now HomeDarts for Autodarts, as Autodarts asked, with the domain `homedarts` and an icon of its own; its actions, cards and folders follow the domain, such as `homedarts.start_game` ([From Autodarts to HomeDarts](new-name.md), [decision 0026](decisions/0026-a-name-of-its-own.md)) | Done |
| **The boards come along** | HomeDarts takes over the boards set up under the old name: their entities with their IDs, history and statistics, the stores of the training, the games and the reports, the highlights, exports and voice packs, and the cards in the dashboards; a repair lists the automations that still call the old actions ([switch over](new-name.md#switch-over)) | Done |
| **No cloud link** | The prepared link to the Autodarts cloud is gone, since Autodarts issues no client IDs to third parties; HomeDarts works locally, and online matches come through Tools for Autodarts ([decision 0025](decisions/0025-no-cloud-link.md)) | Done |

## Next

Ideas for the versions after 2.0. Votes and reactions on the [feature requests](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose) decide the order.

| Topic | What it brings | Dependency |
| --- | --- | --- |
| **Granboard at a real board** | Check every bed of a real Granboard and take the label *experimental* off the Granboard support of 1.17 | A player with a Granboard who [checks every bed](granboard.md#check-every-bed) and reports what counts wrong |
| **Autodarts Desktop** | Verify boards run by Autodarts Desktop and document what works; a player reported 2.0.2 on Linux working ([#105](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/105)) | Test reports from players who use it on Windows |
| **Further languages** | The integration and the cards in more languages, and the questions and answers of Assist in Spanish, French and Dutch as native speakers say them ([#380](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/380)) | Contributions from native speakers ([how to add a language](development.md#translations)) |

## Later

| Topic | Dependency |
| --- | --- |
| **Protocol library on PyPI** (`aioautodarts`) | A separate library for the Board Manager protocol, a prerequisite for a possible Home Assistant core integration; postponed until the protocol settles |

## Not planned

- **A cloud account for local play.** Everything that works with the Board Manager in your network keeps working without an Autodarts account.
- **A link to the Autodarts cloud.** Autodarts issues no client IDs to third-party integrations, so cloud match data and boards without a Board Manager in your network, such as Lens, stay out of reach; the moments of online matches come through the [online bridge](online-matches.md) ([decision 0025](decisions/0025-no-cloud-link.md)).
- **Telemetry.** The integration sends nothing about your games or your home anywhere, and in local mode nothing leaves your network.
- **Breaking changes without a way forward.** Existing config entries, entity IDs and automations keep working, or a release migrates them and its notes say what changes.

## Reach

How many people find the integration and install it, counted once a month: from the numbers GitHub keeps for the repository, and from the [analytics of Home Assistant](https://analytics.home-assistant.io/), which list a custom integration once an installation that shares its usage has it. The integration itself counts nothing (see [Not planned](#not-planned)). `bash scripts/reach.sh` prints the row of the month. The analytics list the integration by its domain, `homedarts` since 2.0; other integrations for Autodarts keep the domain `autodarts`, which this one had up to 1.18 (see [Coming from another tool](coming-from.md)), and the script counts the analytics only for a version that is a release of this one.

| Month | Downloads of the releases | Visitors in 14 days | From Google | In the analytics | Stars |
| --- | --- | --- | --- | --- | --- |
| October 2026 | 120 | 29 | 0 | No | 3 |

The downloads count every installation and update through HACS, of the betas too, since the first release. Where the integration can be found, and the posts that point to it:

| Where | Status |
| --- | --- |
| HACS default repository | Listed since 20 October 2026 ([hacs/default#11306](https://github.com/hacs/default/pull/11306)): a search for *Autodarts* in HACS finds it |
| [awesome-home-assistant](https://github.com/frenck/awesome-home-assistant) | Lists projects from six months of age, so this one from March 2027 |
| Home Assistant forum, Reddit and the Autodarts Discord | The [launch posts](creator-kit.md#launch-posts) are ready |
| Photos of boards it runs at | [Show and tell](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions/categories/show-and-tell) |

## How priorities are set

1. Anything that breaks for users, including changes in Board Manager versions, comes first.
2. Features that work locally come before cloud features.
3. Requests with the most reactions on GitHub come next.
