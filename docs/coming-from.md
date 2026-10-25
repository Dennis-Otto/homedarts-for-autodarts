---
description: "Switch to HomeDarts from Autodarts Local, another integration for Autodarts, an MQTT bridge or darts-caller: what takes its place and how to switch."
---

# Coming from another tool

[← Documentation](README.md) · [Deutsch](coming-from.de.md)

Other projects bring an Autodarts board into Home Assistant or next to it. This page compares them with HomeDarts and shows, for each one, the entities, events and blueprints that take its place, and how to switch while it stays installed. The facts are as of October 2026, from each project's own documentation and code, which the links lead to. If a project has changed since then, [tell us](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions) so that this page stays fair.

Used HomeDarts up to version 1.18, when it was called Autodarts? That is no other tool: HomeDarts takes over your boards with everything they have, as [From Autodarts to HomeDarts](new-name.md) shows.

**Jump to:** [At a glance](#at-a-glance) · [Can it stay?](#can-it-stay) · [Autodarts Local](#autodarts-local) · [Quevinsta's integration](#autodarts-for-home-assistant-by-quevinsta) · [belese's integration](#autodarts-by-belese) · [Autodarts Connect Online](#autodarts-connect-online) · [Darts Hub](#darts-hub) · [MQTT bridges](#mqtt-bridges) · [darts-caller and darts-wled](#darts-caller-and-darts-wled) · [Tools for Autodarts](#tools-for-autodarts) · [The original integration](#the-original-integration)

## At a glance

<!-- --8<-- [start:compare] -->

| Feature | HomeDarts | Autodarts app with [Tools for Autodarts](https://github.com/creazy231/tools-for-autodarts) | [darts-caller](https://github.com/Peschi90/darts-caller) and [darts-wled](https://github.com/Peschi90/darts-wled) | Other Home Assistant integrations |
| --- | --- | --- | --- | --- |
| **Runs without the cloud** | Yes, with the [local interface](how-it-works.md#privacy) of the Board Manager | No, with an [Autodarts account](https://autodarts.com/) | No, darts-caller [signs in to Autodarts](https://github.com/Peschi90/darts-caller#autodarts-login) | Some of them ([details](coming-from.md#can-it-stay)) |
| **Entities and events in Home Assistant** | Yes, an [event](entities.md#board-events) for every dart, visit, takeout, bust, leg and match | No | No | Sensors of the current visit or game |
| **Blueprints** | [Sixteen blueprints](automations.md#blueprints) | No | No | No |
| **Light show** | [Light show](automations.md#light-show) blueprint, for WLED or any light | WLED, with Tools | WLED, with darts-wled | Your own automations |
| **Caller** | On the [scoreboard](scoreboard.md#the-caller) or your [speakers](automations.md#which-caller) | In the app, with a premium voice in [Plus](https://autodarts.com/); more with Tools | Voice packs, with darts-caller | No |
| **Statistics kept at home** | [Yes](statistics.md): averages, heatmaps, profiles and a year of history | No, in the Autodarts account | No | No |
| **Without an Autodarts board** | Yes, on a [keypad](without-autodarts.md) or a [Granboard over Bluetooth](granboard.md) *(experimental)* | Yes, on a keypad or with [Lens](https://autodarts.com/) | No | No |
| **Online matches** | Your darts, and the moments of the match through the [online bridge](online-matches.md) *(experimental)* | Yes | Yes | Some of them, through the cloud |
| **License and cost** | [MIT](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE), free | Autodarts: a free plan and the paid [Plus](https://autodarts.com/); Tools: [CC BY-NC 4.0](https://github.com/creazy231/tools-for-autodarts/blob/main/LICENSE) | Free, no license stated | MIT, Apache 2.0 or no license file |

<!-- --8<-- [end:compare] -->

*As of October 2026, from the documentation and the code of each project. The sections below have the details and the sources.*

## Can it stay?

Yes, every one of them. Home Assistant loads one integration per domain, and HomeDarts has a domain of its own, `homedarts`. So each of the others can stay installed beside it while you move your automations, and go when nothing uses it any more. HomeDarts leaves their entries as they are: it takes over only the boards it set up under its former name, Autodarts.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/coming-from-dark.png">
  <img src="images/en/coming-from-light.png" alt="Switching from another integration for Autodarts: The integration under its former name, Autodarts, up to version 1.18, is no other tool: update it, and HomeDarts takes over its boards. Every other integration, such as the original HACSAutodarts, Quevinsta's, belese's, Autodarts Local, Autodarts Connect Online, Darts Hub or an MQTT bridge, can stay while you switch, because HomeDarts has a domain of its own, homedarts. Install HomeDarts beside it and add the board, move the automations to the events and blueprints of HomeDarts, then delete the entries of the old integration, remove it in HACS and restart Home Assistant" width="520">
</picture>

| Project | Domain | Reads the board through | Next to HomeDarts |
| --- | --- | --- | --- |
| [Original integration](#the-original-integration) by Trkal | `autodarts` | The Autodarts cloud, and the Board Manager for the darts | Can stay |
| [Autodarts for Home Assistant](#autodarts-for-home-assistant-by-quevinsta) by Quevinsta | `autodarts` | The Board Manager, locally | Can stay |
| [autodarts](#autodarts-by-belese) by belese | `autodarts` | The Autodarts cloud | Can stay |
| [Autodarts Local](#autodarts-local) | `autodarts_local` | The Board Manager, locally | Can stay |
| [Autodarts Connect Online](#autodarts-connect-online) | `autodarts_connect` | The Autodarts cloud | Can stay |
| [Darts Hub](#darts-hub) | `darts_hub` | darts-hub or darts-caller, and the Board Manager | Can stay |
| [MQTT bridges](#mqtt-bridges) | `mqtt` | Its own program and an MQTT broker | Can stay |
| [darts-caller and darts-wled](#darts-caller-and-darts-wled) | Outside Home Assistant | The Autodarts cloud | Can stay; let one caller speak |
| [Tools for Autodarts](#tools-for-autodarts) | In the browser | The Autodarts web app | Stays; the online bridge uses it |

### Switch step by step

1. **Install HomeDarts beside it** and add your board, as the [installation guide](installation.md#add-your-board) describes. Both follow the same board.
2. **Move your automations,** one at a time, with the tables below. The dialog of an entity lists the automations and scripts that use it under **Related**.
3. **Delete the entries of the old integration** in **Settings → Devices & services** when nothing uses it any more: open the integration and, for every entry, its menu (⋮) → **Delete**.
4. **Remove its code.** In HACS, open the integration, then its menu (⋮) → **Remove**. If you added it as a custom repository, delete it as well under the menu (⋮) → **Custom repositories**. For a manual installation, delete its folder in `config/custom_components`, such as `config/custom_components/autodarts`.
5. **Restart Home Assistant.**

The entity IDs below are those of a board named *Autodarts Board* in a Home Assistant set to English, as in the [examples of the automations](automations.md#examples). You find yours on the device page of the board.

## Autodarts Local

[Autodarts Local](https://github.com/Mastershort/ha-autodarts-local) by Mastershort, domain `autodarts_local`, reads the state of the Board Manager every second: whether the board is online, its status, the darts of the visit and their sum, and three buttons for the detection.

| Autodarts Local | Here |
| --- | --- |
| *Connection*: `Online` or `Offline` | The *Local connection* binary sensor, under [Health and connections](entities.md#health-and-connections) |
| *Status*, such as `Throw` or `Takeout` | *Detection status*: `throw`, `takeout`, `takeout_in_progress` and the others of the [live visit](entities.md#live-visit), with the event `status_changed`; for the takeout the events `takeout_started` and `takeout_finished` |
| *Current Turn Score* | *Detected visit score*, and the event `visit_thrown` the moment the third dart lands |
| *Number of Throws* | *Darts in visit* |
| *Throw 1*, *Throw 2*, *Throw 3* | The `throws` attribute of *Detected visit score*, the *Last dart* sensor and the event `dart_detected` with `dart_index` and `segment` |
| The buttons *Start Detection*, *Stop Detection* and *Reset Detection* | The buttons *Start detection*, *Stop detection* and *Reset detection*, and the *Detection* switch, under [Controls](entities.md#controls) |
| The example automation *Takeout Light* | The [takeout actions](automations.md#takeout-actions) blueprint, or the example [Light up the board while you pull the darts](automations.md#light-up-the-board-while-you-pull-the-darts) |

**Can stay.** Both call the device *Autodarts Board*, as HomeDarts does for a board added by its address. While both are installed, the buttons here get IDs ending in `_2`, such as `button.autodarts_board_start_detection_2`. Remove Autodarts Local before you add the board here, and the buttons get the IDs your automations already use, such as `button.autodarts_board_start_detection`.

## Autodarts for Home Assistant by Quevinsta

[Autodarts for Home Assistant](https://github.com/Quevinsta/autodarts-for-home-assistant) by Quevinsta, domain `autodarts`, is made for X01 and reads the state of the Board Manager every ten seconds: the three darts and their values, the visit, the remaining score, whether a checkout is possible, and the result of the leg.

| Quevinsta's integration | Here |
| --- | --- |
| *Dart 1*, *Dart 2*, *Dart 3* and their values | The `throws` attribute of *Detected visit score* and the event `dart_detected` |
| *Throw Summary*, *Turn Total* | *Detected visit score*, and the `segments` and the `score` of the event `visit_thrown` |
| *Remaining*, *Checkout Possible* | *Practice remaining score* and *Practice checkout*, which is *unknown* when no route exists, in a [practice game](entities.md#practice-game) |
| *Leg Won*, *Leg Lost*, *Leg Result* | The events `leg_won` and `match_won`, with the `name` of the winner |
| *Autodarts Status* | The *Local connection* binary sensor |

Here, Home Assistant counts the practice game itself: X01 from 101 to 1001, the Cricket games, the party games and the training games. A game on play.autodarts.io is counted in the browser, and its score doesn't reach Home Assistant: Autodarts issues no client IDs to third-party integrations, so there is no cloud link ([decision 0025](decisions/0025-no-cloud-link.md)).

**Can stay.** Its domain is `autodarts`, that of HomeDarts `homedarts`, so you [switch step by step](#switch-step-by-step).

## autodarts by belese

[autodarts](https://github.com/belese/ha_integrations) by belese, domain `autodarts`, follows the board through the Autodarts cloud with the email address and the password of your Autodarts account. It shows the board state, the players, the player at the board and the winner. Its last change was in February 2025.

| belese's integration | Here |
| --- | --- |
| Board state | *Detection status*, locally and without an account |
| Players, current player | `players`, `player` and `name` of *Practice remaining score* in a practice game, and the event `turn_changed` |
| Winner | The event `match_won` and the `winner` attribute of *Practice remaining score* |

HomeDarts needs no Autodarts account and stores no password.

**Can stay.** Its domain is `autodarts`, that of HomeDarts `homedarts`, so you [switch step by step](#switch-step-by-step). Delete its entry at the end: it holds the password of your account.

## Autodarts Connect Online

[Autodarts Connect Online](https://github.com/casef007/HA-autodarts-connect-online) by casef007, domain `autodarts_connect`, is a beta that follows the board through the Autodarts cloud with the email address, the password and the board ID of your account. Its README says that it signs in with the public credentials of darts-caller for now. It sees online matches and bot games, with the name, score, average and Cricket marks of up to four players, and fires the event `autodarts_throw` for every dart.

| Autodarts Connect Online | Here |
| --- | --- |
| The event `autodarts_throw` | The event `dart_detected`, locally, for every dart on your board |
| Name, score and average of up to four players | `scores` of *Practice remaining score* for a match of up to four, up to eight players in the [party games](entities.md#party-games) and 32 in the [tournaments](entities.md#tournaments) |
| Cricket marks | The `marks`, `points` and `mpr` of every player in the `scores` of *Practice remaining score*, in the [Cricket games](entities.md#cricket) |
| Online matches | Your darts as usual, and busts, won legs and matches through the [online bridge](online-matches.md) *(experimental)* |

**Can stay.** It sees more of an online match than HomeDarts does today, such as the darts and scores of your opponents. If you play online most of the time, keep it beside HomeDarts.

## Darts Hub

[Darts Hub](https://github.com/etienne72230/ha-darts-hub) by etienne72230, domain `darts_hub`, needs darts-hub or darts-caller running in your network, on port 8079, and the Board Manager on port 3180. It shows the match, up to six players with their scores, the details of every dart with its position, and buttons to reset and calibrate the board.

| Darts Hub | Here |
| --- | --- |
| Board status, current event | *Detection status* and the [board events](entities.md#board-events) |
| Players and scores of the match | *Practice remaining score* with its `scores`, for the practice game that Home Assistant counts |
| Dart 1 to 3 and the last dart, with value, multiplier, field and position | The `throws` attribute of *Detected visit score*, with `segment`, `multiplier`, `score`, `bed` and the position `x`/`y` |
| The buttons *Reset Board* and *Calibrate Board* | *Reset detection* and *Start automatic calibration* |

**Can stay.** HomeDarts needs neither darts-hub nor darts-caller.

## MQTT bridges

MQTT bridges, such as [Autodarts MQTT](https://github.com/Quevinsta/autodarts-mqtt) by Quevinsta, are programs that you run yourself. They publish the board status, the number of darts and averages to an MQTT broker, and Home Assistant creates their entities through MQTT discovery.

| Autodarts MQTT | Here |
| --- | --- |
| Board status | *Detection status* |
| Number of throws | *Darts in visit* |
| 3-dart average | *Training 3-dart average* of the [training session](entities.md#training-session) |
| Leg average | The `average` of the event `leg_won` |

**Can stay.** HomeDarts needs neither a broker nor a program of its own. To remove a bridge, stop it and delete its device in **Settings → Devices & services → MQTT**.

## darts-caller and darts-wled

[darts-caller](https://github.com/Peschi90/darts-caller) plays the sound files of a voice pack for the state of an Autodarts game and passes the game on to other programs, such as [darts-wled](https://github.com/Peschi90/darts-wled), which drives WLED lights with it. [darts-hub](https://github.com/lbormann/darts-hub) downloads, sets up and starts them. They run on a PC, and darts-caller signs in to your Autodarts account and follows its games.

What Home Assistant does now:

| darts-caller and darts-wled | Here |
| --- | --- |
| Calls of scores and checkouts | The [caller of the scoreboard](scoreboard.md#the-caller), through the screen at the board, or the [dart caller](automations.md#dart-caller) and [practice caller](automations.md#practice-caller) blueprints on your speakers; both also play the [voice packs](scoreboard.md#voice-packs) of darts-caller |
| WLED effects for a 180, a bust or a game shot | The [light show](automations.md#light-show) blueprint with your [WLED presets or other lights](automations.md#light-show-with-wled-and-other-lights) |
| Game events for other programs | [Board events](entities.md#board-events) for every dart, visit, takeout, bust, won leg and match, for every automation of Home Assistant |

**Can stay.** darts-caller follows the cloud and HomeDarts the board, so both work at the same time. Two callers talk over each other, though, and two programs that drive the same WLED lights fight over them: let one of each speak and light. In online matches, darts-caller also calls your opponents' scores, which HomeDarts doesn't see.

## Tools for Autodarts

[Tools for Autodarts](https://github.com/creazy231/tools-for-autodarts) is a browser extension for the Autodarts web app, with more caller voices, sound effects, WLED effects, animations and many settings for the lobby and the match.

**Stays.** The [online bridge](online-matches.md) uses its WLED feature: it calls Home Assistant with the moments of an online match, which become `online_*` [board events](entities.md#board-events). As with darts-caller, let one caller speak in the room: the one of the Autodarts app, the one of Tools or the one of Home Assistant.

## The original integration

HomeDarts started as a fork of [Trkal/HACSAutodarts](https://github.com/Trkal/HACSAutodarts), a prototype from April 2026 with the domain `autodarts`. It follows the board through the Autodarts cloud, signed in with your Autodarts account, and with the address of the board it reads the darts from the Board Manager too. It shows the board state, the last detection event, the mode, state and round of the match, the visit score and the darts.

| The original integration | Here |
| --- | --- |
| *Board Status* | The *Local connection* binary sensor |
| *Board Event*, such as *Throw* or *Takeout* | *Detection status*, with the event `status_changed` |
| *Last Throw*, *Throws in Turn* | The *Last dart* sensor, *Darts in visit* and the event `dart_detected` |
| *Visit Score* | *Detected visit score*, and the event `visit_thrown` the moment the third dart lands |
| *Game Mode*, *Match State*, *Round*, *Total Turns* | *Practice game* and the `game`, `round` and `winner` of *Practice remaining score*, in a [practice game](entities.md#practice-game) that Home Assistant counts itself, with the events `leg_won` and `match_won` |

A game on play.autodarts.io doesn't reach Home Assistant here, as the [section on Quevinsta's integration](#autodarts-for-home-assistant-by-quevinsta) explains.

**Can stay.** Up to version 1.18 HomeDarts had the domain `autodarts` too; since 2.0 it has `homedarts`, so both run side by side, and HomeDarts leaves the entry of the original as it is. [Switch from the original integration](installation.md#switch-from-the-original-integration) has the steps.
