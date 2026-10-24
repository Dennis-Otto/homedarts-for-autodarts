---
description: "Automations while you play: flash the lights on a 180, call the score, celebrate a checkout. Blueprints, board events and examples for your board."
---

# Automations

[← Documentation](README.md) · [Deutsch](automations.de.md)

Your board is fast enough for automations that happen *while* you play. The light flashes the moment the third dart of a 180 lands, and the speaker calls the score before you reach the board.

**On this page:** [Blueprints](#blueprints) · [Blueprint settings](#blueprint-settings) · [Board events](#board-events) · [Examples](#examples) · [Online matches](#online-matches-experimental) · [Adapting automations from older versions](#adapting-automations-from-older-versions)

## Blueprints

Blueprints are ready-made automations, and the integration brings all sixteen along: once your first board is added, they are on the blueprints page, **Settings → Automations & scenes → Blueprints**. Choose one, select your board and the devices to use, and you're done. They require Home Assistant 2026.8 or newer, and every update of the integration brings their new versions, see [updates of the blueprints](#updates-of-the-blueprints).

Not sure which one you need? Start from what your home should do:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/choose-blueprint-dark.png">
  <img src="images/en/choose-blueprint-light.png" alt="Which blueprint fits: For lights, music, a pixel display, photos and celebrations, take the Light show, Walk-on music, Score display, Celebrate a visit score, Highlight photo or Takeout actions. To call the darts, take the Dart caller for every game but the practice game, online matches too, and the Practice caller for the practice game; the caller of the scoreboard card needs no speakers in Home Assistant. For a board that looks after itself, take Start and stop detection automatically, the Board problem alert or the Training session routine. For a summary of your training, take the Training report each day or the Weekly report. To talk to Assist, take Start a game by voice, Enter darts by voice or Ask Assist about your darts." width="560">
</picture>

| Blueprint | What it does | Import |
| --- | --- | --- |
| **Celebrate a visit score** | Runs your actions for visits from a minimum score (default 180), the moment the third dart lands. The actions can use `score`, `darts`, `segments` and `game`. The bot's visits count only if you ask for them. | [![Import the visit score blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fvisit_score.yaml) |
| **Dart caller** | Announces every visit on your speakers with any text-to-speech engine, with a special message for 180, and optionally every dart. It stays silent during a practice game, which the practice caller calls. The messages are templates. | [![Import the dart caller blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fdart_caller.yaml) |
| **Takeout actions** | Runs actions when you start pulling darts and when the board is clear, for example to brighten the board light. | [![Import the takeout actions blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Ftakeout.yaml) |
| **Start and stop detection automatically** | Starts the detection when someone is at the board and stops it after an idle time you choose, so the cameras and board PC can rest. | [![Import the automatic detection blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fauto_detection.yaml) |
| **Board problem alert** | Alerts you after a grace period when the board goes offline or a camera fails. An optional all-clear is sent only after a real alert. The actions can use `problem` and `recovered`. | [![Import the board problem alert blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fboard_alert.yaml) |
| **Training report** | Sends a daily summary of darts, 3-dart average, highest visit and 180s, skipping days without darts. The `summary` variable has the sentence ready. | [![Import the training report blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Ftraining_report.yaml) |
| **Training session routine** | When a [training session](entities.md#training-session) starts, runs your actions, turns on the detection and calibrates the cameras after a short wait; when it ends, turns off the detection and runs your actions with `reason`, `darts`, `average` and `duration_minutes`. The detection switch and the calibration button are optional. | [![Import the training session routine blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Ftraining_session.yaml) |
| **Practice caller** | Calls the [practice game](games.md) on your speakers: "Sam, you require 81" when a checkout is possible, "No score" after a bust, the game shot of a leg or the match, and optionally the score to leave when no checkout is possible and the bull-off. The messages are templates. | [![Import the practice caller blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fpractice_caller.yaml) |
| **Weekly report** | Sends your [training week](entities.md#weekly-report) when the board ends it, by default on Monday at midnight: darts, training time, sessions, the 3-dart average and its change since the week before, best visit, 180s, checkout rate, streak and new personal bests. The message is a template; by default the report appears in Home Assistant's notifications. | [![Import the weekly report blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fweekly_report.yaml) |
| **Highlight photo** | Takes a picture with a board camera after a visit of at least 180 points (adjustable) or a checkout of the practice game, while the darts are still in the board. It saves the picture to the [highlight gallery](#highlight-gallery) and runs your actions, which can use `photo_url`, `photo`, `image`, `message`, `score`, `checkout` and `who`. | [![Import the highlight photo blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fhighlight_photo.yaml) |
| **Light show** | Plays your light effects, such as WLED presets or room lights, for the start of a game, a 180, a high finish, a bust, a won leg or match, a personal best, the daily goal, a won bull-off, an achievement and the winner of a tournament, and optionally during the takeout and in [online matches](online-matches.md). It can restore your lights afterwards and pause the detection while an effect plays. | [![Import the light show blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Flight_show.yaml) |
| **Walk-on music** | Plays the walk-on song of every player on your speakers when a game starts, one after the other until the first dart, and the song of the winner after the match, like the walk-ons of the professionals. The songs are files named after the players, such as `alex.mp3`, with `default.mp3` for everybody else. | [![Import the walk-on music blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fwalk_on.yaml) |
| **Score display** | Shows the [practice game](games.md) on a pixel display at the board, an AWTRIX 3 or a PixelIt: the score after every dart with the route of a checkout, and for a few seconds a 180, a bust, a won leg and the winner. When the game is switched off, or after the idle time, the display goes back to its clock. | [![Import the score display blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fscore_display.yaml) |
| **Start a game by voice** | Starts a practice game when you tell Assist, for example "Start 501 for Alex and Sam", "Start the game Cricket for Alex" or "Play 501 against the bot", in English, German, Spanish, French or Dutch. Assist answers with the game and the players, or with what was wrong. | [![Import the start a game by voice blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fstart_game_by_voice.yaml) |
| **Enter darts by voice** | Enters the darts of a game when you tell Assist, as at a dart machine: the score of a visit, such as "Alex has 140" or "140 points", a checkout, a single dart such as "Triple 20", the next player and undo, in English, German, Spanish, French or Dutch. Assist answers in the words of the scoreboard's caller: what the visit left and who throws next, or why it was refused. | [![Import the enter darts by voice blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fenter_darts_by_voice.yaml) |
| **Ask Assist about your darts** | Answers your questions about the darts, such as "What is my average today?", "How many 180s this week?", "What is my best checkout?", "Who leads the leaderboard?" or "Where should I aim?", in English, German, Spanish, French or Dutch, from the statistics of the board. Assist answers in the language you asked in. | [![Import the ask Assist about your darts blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fask_about_darts.yaml) |

The buttons import a blueprint from GitHub, for example one you deleted. Without My Home Assistant, go to **Settings → Automations & scenes → Blueprints → Import blueprint** and paste the link to the file in [`blueprints/automation/homedarts`](https://github.com/Dennis-Otto/homedarts-for-autodarts/tree/main/blueprints/automation/homedarts). An imported blueprint is kept up to date like the others.

<img src="images/en/blueprints.png" alt="The blueprints page of Home Assistant with the sixteen HomeDarts blueprints, from the board problem alert to the weekly report, and their file names" width="760">

### Updates of the blueprints

The blueprints are part of the integration, so they always match it: after an update in HACS and the restart of Home Assistant, every blueprint you haven't changed is the version of the new release. The integration keeps them in `/config/blueprints/automation/Dennis-Otto/`, the folder where Home Assistant's import saves the blueprints of this repository, so a blueprint you imported before is the same file and is updated as well.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/blueprint-updates-dark.png">
  <img src="images/en/blueprint-updates-light.png" alt="What each start of Home Assistant does with a blueprint of the integration: The integration looks for the file of each of its blueprints in blueprints/automation/Dennis-Otto. A missing file is installed, unless you deleted it, which keeps it deleted. A file with the version of the integration stays as it is. An earlier version that nobody changed, as the integration brought it or as Home Assistant imported it, is updated, and the automations made from it reload with their settings. A file you changed is kept, with a repair that offers the version of the integration." width="560">
</picture>

- **Changed by you:** a blueprint you edited stays as it is. A repair under **Settings → System → Repairs**, *Blueprint not updated*, offers the version of the integration: confirm it to replace your file, or ignore it to keep yours. A later release that changes the blueprint asks again.
- **Deleted by you:** stays deleted. Its button above imports it again.
- **Your automations** keep their settings, and those made from an updated blueprint reload at once.
- **Re-import blueprint** in the menu of a blueprint is no longer needed. It fetches the blueprint from the main branch on GitHub, which can be ahead of your release; the integration then treats it as changed and offers the version that belongs to your release.
- **A blueprint of your own:** to change a blueprint and still get the new versions of the original, save your copy under another name, such as `/config/blueprints/automation/Dennis-Otto/my_light_show.yaml`. The integration looks after only the files named like its blueprints.

The integration compares what a blueprint does, not its comments or its layout: an update replaces an unchanged blueprint together with comments you added. An update also replaces an earlier version in which you changed only the options of a setting, such as a range or a filter; until the next update that changes the blueprint, such a change stays and gets the repair.

### Which caller?

- **Dart caller:** calls every visit, in any game on the board, for example during an online match. While a [practice game](entities.md#practice-game) of the integration is played, it stays silent, so that it never talks over the practice caller. Turn off *Stay silent in practice games* if you don't use the practice caller.
- **Practice caller:** calls what matters in the practice game: requirements, busts, game shots and, if you like, the bull-off.
- **Caller of the scoreboard card:** the [scoreboard](scoreboard.md#the-caller) calls visits and the practice game in one voice, through the browser of the screen at the board. It needs no speakers in Home Assistant.

All three speak the language of Home Assistant without any setting, in English, German, Dutch, French and Spanish, and all three can call with a voice pack of recorded sounds, such as one of darts-caller: see [voice packs of the callers](#voice-packs-of-the-callers) and [of the scoreboard](scoreboard.md#voice-packs).

## Blueprint settings

Every blueprint shows these settings when you create an automation from it: select the blueprint on the blueprints page, fill in the form and save. Settings with a default are optional.

<img src="images/en/blueprint-light-show.png" alt="A new automation from the light show blueprint: its description, the Events entity of the board and a section for every moment, such as a 180, a high finish and a bust" width="760">

### Celebrate a visit score

| Setting | Default | What it does |
| --- | --- | --- |
| Board events | | The *Events* entity of your board. |
| Minimum score | 180 | The lowest visit score that runs the actions. A visit of three darts counts when its third dart lands; a shorter visit when the darts are pulled. |
| Actions | | What happens after such a visit. It can use `score`, `darts`, `segments` and `game` (the practice game, or empty). |
| Also for the bot | off | Also runs the actions for the visits of the practice game's [bot](entities.md#bot). Its darts are not in the board, so its visits are left out by default. |

### Dart caller

| Setting | Default | What it does |
| --- | --- | --- |
| Board events | | The *Events* entity of your board. |
| Text-to-speech engine | | The engine that speaks, for example Home Assistant Cloud or Piper. |
| Speakers | | The media players that play the calls. |
| Language | empty | The language of the voice, for example `en-GB`; empty uses the language of the engine. |
| Voice options | empty | Options of the engine, for example `voice: ...` for another voice. |
| Voice pack | empty | A [voice pack](#voice-packs-of-the-callers) in `homedarts/voices` of the media folder, such as a pack of darts-caller. Its sounds call the visits and the darts it has; the engine speaks the rest. |
| Call every dart | off | Also calls each dart when it lands. The third dart is not called on its own, because the visit follows right away. |
| Stay silent in practice games | on | Leaves the calls to the practice caller while an X01, Cricket or party game of the integration is played. |
| Visit message | `{{ score }}` | Said after a visit. It can use `score`, `darts` and `segments`. |
| Message for 180 | `{{ call }}` | Said instead of the visit message after a 180: "One hundred and eighty!" in the language of Home Assistant. |
| Dart message | `{{ dart_name }}` | Said for each dart. It can use `dart_name` (such as `Treble 20`, `5`, `Bull` or `Miss`, in the language of Home Assistant), `segment` (such as `T20`), `dart_score` and `dart_index`. |

An empty message stays silent. `call` and `dart_name` are the [words of the integration](#calls-in-the-language-of-home-assistant), in English with an older version of the integration.

### Takeout actions

| Setting | Default | What it does |
| --- | --- | --- |
| Board events | | The *Events* entity of your board. |
| When the takeout starts | none | Runs when a hand reaches the board to pull the darts. |
| When the board is clear | none | Runs when all darts are out of the board. |

Fill in at least one of the two.

### Start and stop detection automatically

| Setting | Default | What it does |
| --- | --- | --- |
| Presence | | Any on/off entity that is on while someone is at the board: an occupancy sensor, the room light or an input boolean. |
| Detection switch | | The *Detection* switch of your board. |
| Stop after | 10 minutes | How long the presence has to be off before the detection stops. |

Don't combine this blueprint with a detection switch in the *training session routine*: both would switch the detection.

A detection you start by hand while the presence is off keeps running. A restart of Home Assistant forgets how long the presence has been off: if nobody is there and the detection runs when Home Assistant starts, the detection stops after *Stop after*, also one you started by hand. Saving the automation starts the wait over, too, also the wait after a restart, but leaves a detection you started by hand running; saving other automations changes nothing.

### Board problem alert

| Setting | Default | What it does |
| --- | --- | --- |
| Board connection | | The *Local connection* sensor of your board. |
| Camera problem | | The *Camera problem* sensor of your board. |
| Grace period | 2 minutes | How long a problem has to last before the alert, so that a Board Manager restart or a short calibration stays quiet. |
| Alert actions | | For example a notification to your phone. `problem` is `offline` or `cameras`. |
| Recovery actions | none | Run when a problem you were alerted about is gone, with `recovered` set to `true`. |

A problem also counts when it starts while the sensor is unavailable, for example a camera that fails while the board restarts. A problem that ends while the board is offline gets no all-clear of its own. If the board was offline for longer than the grace period, the all-clear of the connection follows; after a shorter restart, a camera problem that the restart solved stays without an all-clear.

A restart of Home Assistant forgets the grace periods: a problem the board has when Home Assistant starts alerts after the grace period, even if it alerted before the restart, and its all-clear follows as usual. Saving the automation keeps a problem that has not alerted yet, whose grace period was running or whose alert an earlier save was waiting for, and it alerts after a new grace period; a problem that alerted already stays quiet. Saving other automations changes nothing.

What this blueprint and the [automatic detection](#start-and-stop-detection-automatically) do when Home Assistant starts:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/restart-waits-dark.png">
  <img src="images/en/restart-waits-light.png" alt="What the automatic detection and the board problem alert do when Home Assistant starts: if the detection runs while nobody is there, the automatic detection waits for Stop after and stops the detection if still nobody is there; someone who arrives meanwhile keeps it running. If the board is offline or has a camera problem, the board problem alert waits for the Grace period and runs the Alert actions if the problem is still the same; a problem that ended or came back meanwhile is left to the usual triggers" width="640">
</picture>

### Training report

| Setting | Default | What it does |
| --- | --- | --- |
| Time | 21:00 | When the report is sent. Choose a time late in the day: darts count for the day on which they are thrown. |
| Minimum darts | 1 | Skips the report when fewer darts were thrown today. |
| Training darts | | The *Training darts* sensor of your board. |
| Training 3-dart average | | The *Training 3-dart average* sensor of your board. |
| Training highest visit | | The *Training highest visit* sensor of your board. |
| Training 180s | | The *Training 180s* sensor of your board. |
| Actions | | For example a notification with `summary`, such as "30 darts, 3-dart average 57.3, highest visit 140, 1 × 180." in the language of Home Assistant. They can also use `darts`, `average`, `highest`, `scores_180` and `darts_today`. |

A finished session keeps its totals until the next one starts, so the report checks the *Darts today* sensor of the same board and skips days without darts. If that sensor is disabled, the darts of the session decide. To start a new session every day, add *New training session* of your board as the last action.

No board event starts the report, so it takes `summary` from the `summary` attribute of the *Training darts* sensor: the sentence describes that sensor's session, even when the other sensors of the report come from another board, and it is in the language of Home Assistant (see [calls in the language of Home Assistant](#calls-in-the-language-of-home-assistant)). Without the attribute, as with a release of the integration before the one that added it, it writes the sentence in English.

### Training session routine

| Setting | Default | What it does |
| --- | --- | --- |
| Board events | | The *Events* entity of your board. |
| Detection switch | none | Turned on when a session starts and off when it ends. |
| Calibration button | none | The *Start automatic calibration* button, pressed after the detection has started. It is skipped when the first dart started the session, because that dart is still in the board. |
| Wait before calibrating | 5 seconds | Gives the cameras time to open. |
| When a session starts | none | Runs first, for example to switch on the board light. The board is prepared even if one of these actions fails. |
| When a session ends | none | Runs after the detection has stopped, with `reason`, `darts`, `average` and `duration_minutes`. |
| Run for a new training session | off | *New training session* ends a session and starts the next one at once, for example every morning by an automation. By default the board keeps running then; turn this on to run the whole routine. |

Leave the calibration button empty when the board's *Calibrate on start* setting is on: the board calibrates by itself when the detection starts. Don't combine a detection switch here with the blueprint that starts and stops the detection automatically.

### Practice caller

| Setting | Default | What it does |
| --- | --- | --- |
| Board events | | The *Events* entity of your board. |
| Text-to-speech engine, Speakers, Language, Voice options | | As in the dart caller. |
| Voice pack | empty | A [voice pack](#voice-packs-of-the-callers): its sounds call busts, game shots, the match and, when you play alone, what you require; the engine speaks every other call. |
| Checkout possible | `{{ call }}` | Said when the next visit can finish the leg: "Sam, you require 81", or "You require 81" when you play alone. |
| No checkout, a setup | empty | Said when the next visit cannot finish the leg but can leave a finish, with `leave` and `setup`; `{{ call }}` says "Sam, leave yourself 32". Empty uses the *Next player* message. |
| Next player | empty | Said when the next visit cannot finish the leg; `{{ call }}` says "Sam to throw." in a match. Empty stays silent. |
| Bust | `{{ call }}` | Said when a dart busts the visit: "No score". |
| Leg won | `{{ call }}` | Said when a dart wins a leg that does not decide the match: "Game shot, and the leg, Sam!", in a team match with the team's name. |
| Match won | `{{ call }}` | Said when a dart decides the match: "Game shot, and the match, Sam!", in a team match with the team's name. |
| Leg won on the round limit | `{{ call }}` | Said when the last round of an X01 leg with a [round limit](games.md#x01) ends without a checkout and the lowest score wins a leg that does not decide the match, with `rounds` and the `remaining` score of the winner: "Round limit, and the leg, Sam!". |
| Match won on the round limit | `{{ call }}` | Said when the round limit decides the match: "Round limit, and the match, Sam!". |
| Bull-off throw | empty | Said when the next player throws for the bull; `{{ call }}` says "Sam, throw for the bull". The first player of the bull-off is not called. Empty uses the *Next player* message. |
| Bull-off won | empty | Said when the bull-off decides who starts, in one call with the first call of the match; `{{ bull_off_call }}` says "Sam to throw first. Game on!". Empty stays silent. |
| Word for a player without a name | `Player` | Makes "Player 2" in `who` of your own messages, in a match without names. |
| Word for the bot | `Bot` | The name of the practice game's [bot](entities.md#bot) in `who` of your own messages, as the scoreboard shows it, for example "Bot, you require 40". |

`call` and `bull_off_call` are the [words of the integration](#calls-in-the-language-of-home-assistant): the examples above in English, and in the language of Home Assistant in any other.

The first visit of a game is not called, because a game starts without a change of turn. With a [bull-off](games.md#bull-off), the call of the winner starts the game instead.

### Weekly report

| Setting | Default | What it does |
| --- | --- | --- |
| Board events | | The *Events* entity of your board. |
| Minimum darts | 1 | Skips the report of a week with fewer darts, for example a week on holiday. With 0, every week is reported. |
| Title | `{{ week_title }}` | The title of the notification, available as `title`: "Your darts week" in the language of Home Assistant. |
| Message | `{{ summary }}` | The text of the notification, available as `message`: the week in a few sentences, in the language of Home Assistant. |
| Notification actions | a notification in Home Assistant | How the report is sent, for example to your phone, see [below](#weekly-report-on-your-phone). |

The message can use `darts`, `visits`, `sessions`, `training_minutes`, `average`, `average_change`, `highest_visit`, `scores_180`, `checkout_rate`, `legs`, `matches`, `streak`, `daily_goals`, `personal_bests` (how many were set), `week_start`, `week_end` and `summary`, a ready-made summary in the language of Home Assistant. The board ends the week at its *Weekly report day* and *Weekly report time*, by default on Monday at midnight.

### Highlight photo

| Setting | Default | What it does |
| --- | --- | --- |
| Board events | | The *Events* entity of your board. |
| Camera | | The board camera that takes the photo. Enable the camera entity first; camera entities are disabled by default. |
| Visits from | 180 | A visit with at least this score gets a photo when its third dart lands. |
| Checkouts | on | Also a photo when a practice leg is won with a checkout. When the same dart finishes a visit and a leg, you get one photo, with the checkout message. |
| Save to the gallery | on | Saves every photo with [`homedarts.save_highlight`](entities.md#save-a-highlight-photo-homedartssave_highlight), by default to the [highlight gallery](#highlight-gallery) of the media browser. |
| Folder | empty | Empty for the highlight gallery: `homedarts/highlights` in the media folder, `/media/homedarts/highlights` on Home Assistant OS and in a container, `/config/media/homedarts/highlights` in other installations. Another folder must be one Home Assistant may write to, such as `/media/darts` on Home Assistant OS or a folder of `allowlist_external_dirs`; outside the media folder, a photo has no `photo_url`. |
| Actions | none | For example a notification, see [below](#highlight-photo-on-your-phone). Optional while the photos go to the gallery. |
| Message for a visit | `{{ score }}!` | The `message` of a visit photo. |
| Message for a checkout | `Checkout {{ checkout }}{{ ' by ' ~ who if who }}!` | The `message` of a checkout photo. |
| Clip camera | empty | Optional, in the collapsed section *Clip*: a camera with a video stream that films the board, such as a camera of the room or the one of your stream. It records each moment as a [clip](#highlight-clips) beside the photo, so it needs *Save to the gallery*. The board cameras of Autodarts give pictures, not a video stream; the list offers only cameras with one. |
| Seconds before | 5 | How much of the clip comes before the moment of the photo. It needs the stream of the camera to run ahead: turn on *Preload camera stream* in the settings of the camera entity. |
| Seconds after | 8 | How much of the clip follows the moment of the photo. |

Your actions can use:

- `photo_url`: the address of the saved photo, for a notification of the Home Assistant app, for example `/media/local/homedarts/highlights/2026-09-26_21-05-33_Alex_180.jpg`.
- `photo`: the file the picture is saved to.
- `image`: the live picture of the camera, for photos that are not saved.
- `message`, `score`, `checkout` and `who` (the player at the board, when the practice game names them).
- `clip` and `clip_url`: the file and the address of the [clip](#highlight-clips) being recorded, empty without a clip camera or a saved photo. The recording runs in the background, so the actions get both at once and don't wait for it; the file is written when the recording ends, *Seconds after* later. A notification that links the clip waits that long first, for example with a `delay`.

`photo` and `photo_url` are empty when no photo was saved: *Save to the gallery* is off, the camera entity is disabled or unavailable, the camera gives no picture, or Home Assistant may not write to the folder. The log of Home Assistant then says which of them it was. `photo_url` is also empty for a folder outside the media folder, which the app cannot load from. So `photo_url or image` is always a picture: the saved photo, or the live picture of the camera.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/highlight-photo-dark.png">
  <img src="images/en/highlight-photo-light.png" alt="How the highlight photo saves a photo and what your actions get: after a big visit or a checkout, with Save to the gallery on, homedarts.save_highlight saves the photo only when the camera entity is enabled and available, the camera gives a picture and Home Assistant may write to the folder; then photo is the saved file and photo_url its address. Otherwise nothing is saved, the log says why, and photo and photo_url stay empty. Your actions run either way, and photo_url or image is the saved photo or the live picture" width="480">
</picture>

The blueprint needs version 1.12.4 or later of the integration, which brings `homedarts.save_highlight`. Earlier versions of the blueprint saved with `camera.snapshot`, which also announced a photo that was never written; updating the integration brings the new blueprint, and your automation keeps its settings. A *Clip camera* needs a version of the integration later than 1.16.0, whose `homedarts.save_highlight` records the clip.

### Light show

| Setting | Default | What it does |
| --- | --- | --- |
| Board events | | The *Events* entity of your board. |
| Actions when a game starts | none | Run when a [game starts](entities.md#games-that-start-and-end), however it was set up, for example the scene for playing; also when a game goes on after the idle end of the training session. `who` is empty. |
| Actions for a 180 | none | Run the moment the third dart of a 180 lands. |
| High finish from | 100 | A practice leg won with a checkout of at least this score is a high finish. |
| Actions for a high finish | none | Run for a high finish, instead of the actions for a won leg. |
| Actions for a bust | none | Run when a dart of the practice game busts the visit. |
| Actions for a won leg | none | Run when a dart wins a practice leg. The leg that decides a match plays the actions for the match instead. |
| Actions for a won match | none | Run when a dart decides a practice match. |
| Actions for a personal best | none | Run when a value beats your [personal best](entities.md#personal-bests-streak-and-daily-goal). |
| Actions for the daily goal | none | Run when today's darts reach the daily goal. |
| Actions for a won bull-off | none | Run when the bull-off decides who starts. |
| Actions for an achievement | none | Run when a named player unlocks a new tier of an [achievement](entities.md#achievements). |
| Actions for a won tournament | none | Run when the last match of a [tournament](entities.md#tournaments) counts, after the actions for the won match; `who` is the winner of the tournament. |
| React to the takeout | off | Runs the two actions below while you pull the darts. Leave it off without them, so that takeouts never wait behind an effect. |
| When the takeout starts | none | Run when a hand reaches the board. Not restored. |
| When the board is clear | none | Run when all darts are out of the board. Not restored. |
| Also for the bot | off | Also plays the moments of the practice game's [bot](entities.md#bot): its 180, bust, won leg or match and won bull-off. A leg or match the bot wins in a team match plays anyway, because its partner at the board wins it, too. |
| Word for the bot | `Bot` | The bot's name in `who`. |
| Word for a player without a name | `Player` | Makes "Player 2" in `who`. |
| Moments with an effect | none | The moments whose actions start an effect. Only for them are the lights restored and the detection paused. |
| Restore these lights | none | Their state is saved before an effect and restored after it. |
| Effect duration | 10 seconds | How long an effect plays before the lights are restored and the detection starts again. A training session that ends meanwhile ends the effect at once and leaves the detection off. |
| Pause the detection during effects | off | Turns the detection off while an effect plays and on again afterwards, if it was on. The daily goal never pauses it, because it is reached in the middle of a visit, and neither does a new best session average, which comes when a training session ends. |
| Detection switch | none | The *Detection* switch of your board, for pausing it. |
| Also react to online matches | off | Also plays the actions for a bust, a won leg and a won match of an [online match](online-matches.md). A 180 and the takeout of your own darts come from your board anyway. |

The actions can use `moment` (`game_start`, `maximum`, `high_finish`, `bust`, `leg`, `match`, `personal_best`, `daily_goal`, `bull_off`, `achievement`, `tournament`, `takeout` or `board_clear`), `who` (the player's name, the word for the bot, or "Player 2"; empty at the start of a game), `player`, `score` (of a 180), `checkout` (of a won leg) and `trigger.to_state.attributes` for every detail of the [board event](entities.md#board-events). See [light show with WLED and other lights](#light-show-with-wled-and-other-lights).

### Walk-on music

| Setting | Default | What it does |
| --- | --- | --- |
| Board events | | The *Events* entity of your board. |
| Speakers | | The media players that play the songs. |
| Song pack | `walk-ons` | The folder of the songs in `homedarts/voices` of the media folder, for example `/media/homedarts/voices/walk-ons/alex.mp3` for the song of Alex. |
| Seconds per walk-on | 20 | How long the song of each player plays before the song of the next one. The first dart ends the walk-ons at once. |
| Song of the winner | on | Plays the song of the winner once the darts of the winning visit are pulled. |
| Seconds for the winner | 30 | How long the song of the winner plays; 0 plays it to its end. |
| Walk-ons for | a game alone, a match, a party game, a match of a tournament | The games with walk-on music, by their `mode`: `practice`, `match`, `party`, `tournament` and `training`. A training game such as Around the Clock has none unless you choose it. |

Put a song for each player into the song pack, named after the player as the sounds of a [voice pack](#voice-packs-of-the-callers) are named: `alex.mp3` for Alex (the name in small letters), `bot.mp3` for the [bot](entities.md#bot) and `default.mp3` for everybody without a song of their own; `mp3`, `wav`, `ogg` and `flac` play. A player with several songs, such as `alex.mp3` and `alex+2.mp3`, gets one of them at random. Upload them in **Media → My media → homedarts → voices → walk-ons**, or copy them to `/media/homedarts/voices/walk-ons/`.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/walk-on-dark.png">
  <img src="images/en/walk-on-light.png" alt="How the walk-on music plays: When a game starts, the blueprint looks for the song of each player in the song pack, in the order of the seats: the player's own song, such as alex.mp3, bot.mp3 for the bot, or default.mp3. Each song plays for the seconds per walk-on; a player without a song walks on in silence. The first dart ends the walk-ons at once. A game that is stopped or replaced stops the music. When the darts of the winning visit are pulled, the song of the winner plays." width="560">
</picture>

The walk-ons follow the [`game_started` and `game_ended` events](entities.md#games-that-start-and-end): they play for every game however it starts, from the lobby of the [scoreboard](scoreboard.md), by voice, with `homedarts.start_game` or for the next match of a tournament, and not again for a game that goes on after the idle end of the training session. A player without a song walks on in silence when there is no `default.mp3`, and a song pack that does not exist leaves the whole walk-on silent; neither stops the automation. Walk-on music needs version 2.1.0 or later of the integration.

### Score display

| Setting | Default | What it does |
| --- | --- | --- |
| Board events | | The *Events* entity of your board. |
| Practice remaining score | | The *Practice remaining score* entity of your board, which follows every dart of the [practice game](entities.md#practice-game). |
| Display | AWTRIX 3, over MQTT | The display and how Home Assistant reaches it: an AWTRIX 3 over MQTT, a PixelIt over MQTT, or a PixelIt over HTTP with a REST command; see [score display on an AWTRIX or a PixelIt](#score-display-on-an-awtrix-or-a-pixelit). |
| MQTT prefix | empty | For MQTT: the prefix of the display's topics, as its MQTT settings show it, for example `awtrix_1a2b3c`. Empty uses `awtrix` or `pixelit`. |
| PixelIt REST command | `rest_command.pixelit_screen` | For PixelIt over HTTP: the REST command that sends `screen` to the display. |
| AWTRIX icon | empty | An icon of the AWTRIX 3 next to the text, by its file name on the display or its LaMetric number. |
| Flash duration | 5 seconds | How long a 180, a bust, a won leg or the winner stays before the score comes back. |
| Back to the clock after | 5 minutes | How long the display keeps the score, or the result of a finished game, without a dart. |
| Score | `{{ remaining if remaining != '' else points }}{{ ' ' ~ checkout if checkout }}` | What the display shows for the player at the board: in X01 the remaining score and the route of a checkout, for example `81 T15 D18`, in Cricket and the party games the points. Empty leaves the display alone during the game; after a moment, the clock comes back at once. |
| Color of the score, Color when a checkout is possible | white, green | The color of the score, and its color while the visit can finish the leg. |
| Minimum score of a visit | 180 | The lowest visit score that flashes. |
| Visit | `{{ score }}!` | Flashes for such a visit, the moment its third dart lands. |
| Bust | `BUST` | Flashes when a dart busts the visit. |
| Leg won | `GAME SHOT` | Flashes when a dart wins a leg that does not decide the match. |
| Match won | `{{ team or who }} WINS` | Flashes when a dart decides the match; in a team match with the team's name. |
| Color of a visit, Color of a bust, Color of a won leg, Color of the winner | gold, red, green, gold | The colors of the moments. |
| Word for a player without a name | `Player` | Makes "Player 2" in `who`. |
| Word for the bot | `Bot` | The bot's name in `who`. |

An empty message stays silent. The score can use `remaining`, `checkout` (the route), `leave` and `setup` (where to aim without a checkout), `points`, `target`, `who`, `player`, `players` and `game`; the moments `who`, `team`, `score`, `remaining`, `checkout` (the score checked out), `darts` and `average`.

### Start a game by voice

| Setting | Default | What it does |
| --- | --- | --- |
| Sentences | In five languages | What you say to Assist. `{game}` is the game and `{players}` the players; parts in [brackets] are optional, (a\|b) means a or b. |
| Bot level | 60 | The 3-dart average the bot plays when a sentence ends in "bot". |
| Board | | The board to play on. Needed only with more than one board. |

Say for example:

- "Start 501 for Alex and Sam", "Play 301 with Alex, Sam and Kim" or "Start five hundred one"
- "Start the game Cricket for Alex and Sam", "Play a game of Around the Clock"
- "Start 501 for Alex against the bot", "Play 501 for Alex and the bot", "Play the game Cricket against the bot"
- in German "Starte 501 für Alex und Sam", "Starte das Spiel Doppeltraining" or "Spiele 501 gegen den Bot"
- in Spanish "Juega 501 para Alex y Sam", "Juega una partida de Around the Clock" or "Juega 501 contra el bot"
- in French "Lance 501 pour Alex et Sam", "Lance la partie Cricket pour Alex" or "Joue 501 contre le bot"
- in Dutch "Speel 501 voor Alex en Sam", "Start het spel Dubbeltraining" or "Speel 501 tegen de bot"

Assist answers "Game on: 501 with Alex and Sam." in the language of Home Assistant, or says what was wrong, such as a game it does not know, Killer with one player, more players than the game takes or a name longer than 20 characters.

- **The game:** X01 is a number from 101 to 1001, as digits or as words in the language of Home Assistant (see [numbers](#numbers-by-voice)). Every other game follows the word "game", "Spiel", "partida", "partie" or "spel" and is named as the game list shows it, in any language of the integration: "Around the Clock", "Bob's 27", "Doubles training", "Doppeltraining". The beginning of a name is enough where it fits one game alone, such as "Cut Throat".
- **The players:** one word each, joined by "and", "und", "y", "et", "en" or a comma. A player who already has a profile keeps its spelling, even when the voice assistant writes the name in lower case. Without players, the players stay as they are.
- **The bot:** a sentence that ends in "bot" plays against the bot, which takes a seat after the players; any other sentence starts the game without the bot. The bot is never a player, also not in "Play 501 for Alex and the bot", "Spiele 501 für Alex und den Bot", "Juega 501 para Alex y el bot", "Joue 501 pour Alex et le bot" or "Speel 501 voor Alex en de bot".
- **Why a number or the word "game":** Assist hears the sentences of an automation before its own commands. A sentence such as "Start {game} for {players}" would also catch "Start a timer for 5 minutes", and the timer would never run. With a number or the word for a game, your other commands stay as they are, in every language.
- **New sentences:** an automation keeps the sentences you saved in it. After the update of the integration and the restart, the new version of the blueprint is there; for its sentences, leave *Sentences* at its default. Sentences of your own stay as they are.

### Enter darts by voice

| Setting | Default | What it does |
| --- | --- | --- |
| Score of a visit | In five languages | Sentences with the score of a visit, `{score}` from 0 to 180, and optionally the player, `{player}`; parts in [brackets] are optional, (a\|b) means a or b. |
| Checkout | In five languages | Sentences for a visit that checks out what the player has left, optionally with its darts, `{darts}`, and the player. |
| Single dart | In five languages | Sentences for one dart, with the number of its bed, `{number}`, or a bull or a miss. |
| Next player | In five languages | Sentences that end the visit, so the next player throws. |
| Undo | In five languages | Sentences that take the last visit back, to enter it anew. |
| Board | | The board to enter the darts on. Needed only with more than one board. |

Say for example:

- "Alex has 140", "Sam scored 100", "140 points" or just "one hundred forty", for the score of a visit
- "Checkout with two darts", "Game shot in three darts" or "Alex checks out"
- "Triple 20", "Double 16", "Single 5", "Bull", "Single bull" or "Miss"
- "Next player" and "Undo"
- with Home Assistant in German "Alex hat 140", "Aufnahme 100", "Checkout mit zwei Darts", "Doppel 16", "Fehlwurf", "Nächster Spieler" or "Rückgängig"
- with Home Assistant in Spanish "Alex hace 140", "Tirada 100", "Cierre con dos dardos", "Doble 16", "Fallo", "Siguiente jugador" or "Deshacer"
- with Home Assistant in French "Alex a fait 140", "Volée 100", "Checkout en deux fléchettes", "Double 16", "Raté", "Joueur suivant" or "Annule la dernière volée"
- with Home Assistant in Dutch "Alex heeft 140", "Beurt 100", "Uitgooi met twee darts", "Dubbel 16", "Mis", "Volgende speler" or "Ongedaan maken"

<img src="images/en/manual-voice.webp" alt="Animation: the scoreboard of a dartboard without Autodarts with Assist open on top; Alex has 140, Triple 20 and Single bull are typed to Assist, which answers 140 for Alex, 361 left. Sam, you require 501, then Triple 20, 441 left, and 25, 416 left; the dialog closes on Alex at 361 and Sam at 416 with Triple 20 and 25 in his visit" width="760">

Assist answers in the words of the scoreboard's caller, in the language of Home Assistant: "140 for Alex, 361 left. Sam, you require 501." after a visit, "Triple 20, 441 left." after a dart, "No score: Alex stays at 40." after a bust, "Game shot, and the match, Alex!" after the last visit, "Taken back: 140 of Alex." after an undo, or why it was refused.

- **Manual entry:** the darts need *Practice manual entry*, which a [dartboard without Autodarts](without-autodarts.md) has on always. On a board with Autodarts, switch it on for a player without cameras or for darts the board missed.
- **The player:** a sentence with a name enters the visit only while that player is at the board. "Sam scored 100" while Alex throws is refused with "It is Alex's turn, not Sam's.", so a misheard visit never counts for the wrong player. Without a name, the visit is for the player at the board.
- **The checkout** scores what the player has left, with three darts unless the sentence says fewer, one of them at a double. What cannot be checked out, such as 169, is explained.
- **A dart:** the darts of a visit end with "Next player", as on the keypad. A dart that checks out says "Game shot!", and the next player then calls the leg or the match.
- **A number alone** is the score of a visit, not a dart: "twenty" enters a visit of 20; say "Single 20" for a dart.
- **Other commands:** each sentence is a number or has words of darts, so Assist's own commands, such as "What time is it", stay its own.
- **Languages:** the sentences are in English, German, Spanish, French and Dutch, and Assist answers in the language of Home Assistant. In another language, replace them with your own and keep the words of the beds: triple, double, doble or dubbel, single bull, bull, and miss, raté, fallo or mis.
- **New sentences:** an automation keeps the sentences you saved in it. After the update of the integration and the restart, the new version of the blueprint is there; for its sentences, leave them at their default.

#### Numbers by voice

Both voice blueprints understand numbers as digits in every language. Numbers in words follow the language of Home Assistant and are written out in full, as Assist knows them:

| Home Assistant in | Say | Not |
| --- | --- | --- |
| English | "one hundred forty", "five hundred one", "two darts" | "one hundred and forty" |
| German | "einhundertvierzig", "fünfhunderteins", "zwei Darts" | "hundertvierzig" |
| Spanish | "ciento cuarenta", "quinientos uno", "dos dardos" | "ciento y cuarenta" |
| French | "cent quarante", "cinq cent un", "deux fléchettes" | "cinq cent et un" |
| Dutch | "honderdveertig", "vijfhonderdeen", "twee darts" | "honderd veertig" |

So "Checkout mit zwei Darts" needs Home Assistant in German and "Checkout with two darts" Home Assistant in English, while "Checkout mit 2 Darts" and "Checkout with 2 darts" work in both.

How Assist answers a sentence of the voice blueprints:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/voice-dark.png">
  <img src="images/en/voice-light.png" alt="How Assist answers a sentence of the voice blueprints: when a sentence matches one of a blueprint, with numbers as digits or as words in the language of Home Assistant, the blueprint makes the data of the action, such as the game 501 and the player Alex, with the bot at the end of the sentence taken as the bot. The action checks the data: when it fits, the game starts or the darts are entered and Assist says what happened; otherwise Assist says why, for example that the game takes four players at most. A sentence that matches no blueprint stays one of Assist's own commands, such as a timer." width="560">
</picture>

### Ask Assist about your darts

| Setting | Default | What it does |
| --- | --- | --- |
| Average today | In five languages | Questions for the 3-dart average of today's training sessions; parts in [brackets] are optional, (a\|b) means a or b. |
| Average this week | In five languages | Questions for the 3-dart average of the week of the weekly report. |
| 180s this week | In five languages | Questions for the 180s of the week of the weekly report. |
| Darts today | In five languages | Questions for the darts of the day, towards the daily goal. |
| Best checkout | In five languages | Questions for the highest checkout among the personal bests of the board. |
| Training streak | In five languages | Questions for the days in a row with darts, and the longest streak. |
| Leaderboard | In five languages | Questions for the player at the top of the leaderboard. |
| Best aim | In five languages | Questions for the best aim of a player, `{player}`: "I", "ich", "yo", "je" or "ik" is you, as are sentences without a player. |
| Board | | The board whose statistics answer. Without one, the board with the most darts this week answers. |

Ask for example:

- "What is my average today?", "How am I scoring today?" or "What's my average this week?"
- "How many 180s this week?", "How many darts have I thrown today?" or "What is my best checkout?"
- "How long is my streak?", "Who leads the leaderboard?", "Where should Sam aim?" or "Where should I aim?"
- in German "Wie ist mein Schnitt heute?", "Wie viele 180er habe ich diese Woche geworfen?", "Wer führt die Bestenliste an?" or "Wohin soll ich zielen?"
- in Spanish "¿Cuál es mi media de hoy?", "¿Cuántos 180 llevo esta semana?", "¿Quién lidera la clasificación?" or "¿Dónde debo apuntar?"
- in French "Quelle est ma moyenne aujourd'hui ?", "Combien de 180 ai-je faits cette semaine ?", "Qui est en tête du classement ?" or "Où dois-je viser ?"
- in Dutch "Wat is mijn gemiddelde vandaag?", "Hoeveel 180's heb ik deze week gegooid?", "Wie staat bovenaan de ranglijst?" or "Waar moet ik op mikken?"

Assist answers from the statistics of the board, in the language you asked in: "Today: a 3-dart average of 120.2 from 18 darts.", "180s this week: 2.", "18 darts today. 2 more for your daily goal of 20.", "Your best checkout is 141.", "One day in a row. Your record: 1.", "Alex leads the leaderboard with a 3-dart average of 167." or "Sam, aim at Bull: 11.8 points per dart.". Before the first dart, it says what is missing, such as "No darts today yet.".

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/ask-assist-dark.png">
  <img src="images/en/ask-assist-light.png" alt="How Assist answers a question about your darts: When you ask a question of the blueprint, such as What is my average today, the blueprint finds the statistics of the board by what each sensor holds, under any name and in any language - the training sessions of the day, the weekly report, the personal bests, the training streak and the player profiles. With numbers for the question, Assist answers in the language you asked in; without, it says what is missing, such as No darts today yet. A sentence without a question of the blueprint stays one of Assist's own commands." width="560">
</picture>

- **Today** counts every [training session](entities.md#training-session) that started today, also one that has ended. A session that began before midnight and runs on has no day of its own, so Assist answers with "This session: …" instead. For a day of its own, end each session with *Session idle timeout* or start a new one every morning with *New training session*.
- **This week** is the week of the [weekly report](entities.md#weekly-report), which ends on Monday at midnight unless you set another time; the average of a new week is compared with the week before, such as "This week: a 3-dart average of 90, 30.1 less than last week.".
- **The best checkout** is the highest checkout among the [personal bests](statistics.md#personal-bests-streak-and-daily-goal) of the board, and **the streak** counts the days in a row with at least one dart, as the *Training streak* sensor does.
- **The leaderboard** ranks the players by their 3-dart average, then by their won legs, as the leaderboard of the scoreboard does.
- **The best aim** is where a player scores the most points per dart with the spread of their darts ([where to aim](statistics.md#where-to-aim)). It needs darts that the board detected, so a dartboard without Autodarts has none. "I" is the player linked to the person you are signed in as ([players and persons](statistics.md#players-and-persons)); a voice satellite has no person, so it gets the player who played last.
- **Languages:** the questions are in English, German, Spanish, French and Dutch, and Assist answers in the language of the question, that of your voice assistant, also for a regional language such as Spanish for Latin America. In another language, write questions of your own; Assist answers them in English.
- **Other commands:** each question has a word of darts, such as average, 180, checkout or leaderboard, so Assist's own commands, such as "What time is it", stay its own. A question only reads the statistics and changes nothing.
- **New sentences:** an automation keeps the sentences you saved in it. After the update of the integration and the restart, the new version of the blueprint is there; for its sentences, leave them at their default.

### Dart caller messages

The messages of the dart caller are templates. For example:

| Setting | Example |
| --- | --- |
| Visit message | `{{ score }}`, or `{{ score }} points` |
| Message for 180 | `{{ call }}` says "One hundred and eighty!", or your own words, such as `Maximum!` |
| Dart message | `{{ dart_name }}` says "Treble 20", "5", "Bull" or "Miss"; `{{ dart_score }}` says the points |

For German words of your own, see the [German guide](automations.de.md#deutscher-dart-caller).

### Practice caller messages

The practice caller's messages are templates with these variables:

| Variable | Content |
| --- | --- |
| `call` | What the caller says, in the language of Home Assistant, as the defaults say it: "Sam, you require 81", "No score" or "Game shot, and the leg, Sam!" |
| `bull_off_call` | What the caller says when the bull-off is won, in *Bull-off won*: "Sam to throw first. Game on!" |
| `who` | The player's name, "Bot" for the [bot](entities.md#bot) (see *Word for the bot*), "Player 2" in a match without names, empty when you play alone |
| `team` | The team of the player in a [team match](entities.md#teams-and-start-scores), for example `Alex & Kim` when both partners have a name; empty otherwise |
| `remaining` | The score left |
| `checkout` | The route when a checkout is possible, for example `T20 T20 BULL`; in *Leg won*, the score checked out, for example `121` |
| `darts`, `average` | Darts and 3-dart average of the leg, in *Leg won* |
| `rounds` | The rounds of a leg the [round limit](games.md#x01) decided, in *Leg won on the round limit* and *Match won on the round limit*, with the winner's score left in `remaining`; `0` for a checkout |
| `points` | Points in the Cricket and party games; strokes in Golf, runs in Baseball. Killer keeps no points: its events carry the player's `lives` and whether they are a `killer`, for example `trigger.to_state.attributes.lives` |
| `target` | The next target of a party game, for example `20`, `D` or `D16`; the hole in Golf and the inning in Baseball |
| `leave`, `setup` | Where no checkout is possible: the score a [setup](entities.md#setup-hints) leaves, for example `32`, and its darts, for example `T20 T20 S17`; empty otherwise |
| `hit` | The bed of the winning bull-off dart in *Bull-off won*: `BULL`, `25` or for example `S20` |
| `distance` | How far the winning bull-off dart landed from the center, in millimeters, in *Bull-off won*; empty when the board reported no position for it, never `None` |

For example, in words of your own:

| Setting | Example |
| --- | --- |
| Checkout possible | `{{ who ~ ', you' if who else 'You' }} require {{ remaining }}` |
| No checkout, a setup | `{{ who ~ ', leave' if who else 'Leave' }} yourself {{ leave }}` |
| Next player | `{{ who }}`, or `{{ who }}, {{ target }}` in party games |
| Bust | `No score` |
| Leg won | `Game shot, and the leg{{ ', ' ~ (team or who) if team or who }}! {{ checkout }} checkout in {{ darts }} darts.` |
| Match won | `Game shot, and the match, {{ team or who }}!` |
| Leg won on the round limit | `After {{ rounds }} rounds, the leg goes to {{ team or who }} on {{ remaining }}!` |
| Bull-off throw | `{{ who }}, throw for the bull` |
| Bull-off won | `{{ who }} to throw first. Game on!`, or `{{ who }} wins the bull{{ ' by ' ~ distance ~ ' millimeters' if distance is number }}` |
| Word for a player without a name | `Player` |

### Calls in the language of Home Assistant

Home Assistant translates no blueprint, so the integration gives each event that a caller speaks the words for it, in the language of Home Assistant, and the callers say them by default: `call` on the events of the dart caller and the practice caller, `title` and `summary` on the weekly report, and the `summary` attribute of the *Training darts* sensor for the training report, which runs on a timer. They follow a new language of Home Assistant at once, in English, German, Dutch, French and Spanish; a regional variant such as `de-CH` speaks its language, and another language English. The words are those of the [scoreboard's caller](scoreboard.md#the-caller) and of the voice packs that `homedarts.generate_voice_pack` records.

| Event | `call` in English | `call` in German |
| --- | --- | --- |
| `turn_changed` | "Sam, you require 81", "Sam, leave yourself 32", "Sam to throw.", "Sam, throw for the bull" | "Sam, du brauchst 81", "Sam, stell dir die 32", "Sam ist dran.", "Sam, dein Wurf aufs Bull" |
| `bust` | "No score" | "Überworfen" |
| `leg_won`, `match_won` | "Game shot, and the leg, Sam!", "Round limit, and the match, Sam!" | "Game shot, und das Leg, Sam!", "Rundenlimit, und das Match, Sam!" |
| `bull_off_won` | "Sam to throw first. Game on!" | "Sam beginnt. Game on!" |
| `visit_thrown`, `visit_completed` | "One hundred and eighty!", "No score" for 0, otherwise the score | "Einhundertachtzig!", "Keine Punkte" |
| `dart_detected` | "Treble 20", "Double 16", "5", "25", "Bull", "Miss" | "Triple 20", "Doppel 16", "5", "25", "Bull", "Fehlwurf" |

The default calls name the bot and a player without a name in the integration's words too, such as "Bot" and "Spieler 2" in German; *Word for the bot* and *Word for a player without a name* apply to your own messages. Pick a *Voice* that speaks the language of Home Assistant, or leave *Language* empty: an English voice reads German or French words badly. To keep the English calls in a Home Assistant of another language, enter the English examples of the [practice caller messages](#practice-caller-messages) as your messages.

A message of your own keeps its words in every language. An automation set up before calls in your language once the [update of the integration](#updates-of-the-blueprints) brings the new blueprint, unless it saved a message, such as the English default of before: replace that with `{{ call }}`, or the title of the weekly report with `{{ week_title }}`. With an older version of the integration, the events have no words, and the blueprints say them in English.

### Voice packs of the callers

With *Voice pack*, the dart caller and the practice caller play recorded sounds on the speakers instead of the engine's voice: a pack of [darts-caller](https://github.com/lbormann/darts-caller), or one that [`homedarts.generate_voice_pack`](entities.md#record-a-voice-pack-homedartsgenerate_voice_pack) recorded, in a folder of `homedarts/voices` in the media folder, as for the [scoreboard](scoreboard.md#voice-packs). The blueprints ask [`homedarts.voice_sound`](entities.md#find-a-sound-of-a-voice-pack-homedartsvoice_sound) for the sound of each call and play it with `media_player.play_media`; a call the pack has no sound for is spoken by the engine, with your message.

| Blueprint | Calls with a sound of the pack |
| --- | --- |
| Dart caller | The points of a visit, `0` to `180`; every dart: `t20`, `d16`, `s5` or `5`, `bull` for 25, `bullseye`, and `outside` for a miss |
| Practice caller | `busted`, `gameshot` and `matchshot`, also in a match; what you require when you play alone, `yr_40`. A call that names the player at the board, and a leg or match the round limit decides, stay the engine's |

On a media player, a new sound replaces the one that plays, so each call of the blueprints is one sound; the [scoreboard](scoreboard.md#voice-packs) also plays calls of several sounds, such as a name, `you_require` and `40`, one after the other. An empty message stays silent, also with a voice pack. Voice packs need version 1.15.0 or later of the integration.

### Highlight photo on your phone

In *Actions* of the highlight photo, add a notification of the Home Assistant app and give it the picture:

```yaml
action: notify.mobile_app_your_phone
data:
  message: "{{ message }}"
  data:
    image: "{{ photo_url or image }}"
```

The app loads the saved photo, taken while the darts were still in the board, even when the notification reaches a sleeping phone minutes later. Without a saved photo it falls back to `image`, the live picture of the camera, which the app loads only when the notification arrives, possibly after the darts are pulled. Enable the camera entity on the device page first; camera entities are disabled by default.

### Highlight gallery

The highlight photo saves every picture as a file named by the moment, the player and the score, for example `2026-09-26_21-05-33_Alex_180.jpg` or `2026-09-26_21-07-10_Alex_checkout-121.jpg`; a second photo of the same second with the same name, from a second camera for example, gets a space and `(2)` at the end and is kept as well. Open **Media → HomeDarts** in the sidebar: the gallery lists the months, newest first, and every photo with a title such as *180 · Alex · Sep 26*, with the [clips](#highlight-clips) of the highlight photo beside their photos.

<img src="images/en/media-gallery.png" alt="The highlight gallery in the media browser of Home Assistant: September 2026 with a checkout of 121 by Sam, a 180 by Alex and a 140 by Kim" width="760">

- The gallery shows the folder `homedarts/highlights` of the media folder of Home Assistant, which is `/media/homedarts/highlights` on Home Assistant OS and in a container. [How the gallery works](how-it-works.md#highlight-gallery).
- Photos you copy there yourself show, too; without a name of this kind, by their file name and the time they were saved.
- To delete a photo, open **Media → My media → homedarts → highlights**.
- The gallery needs the media browser, which the default configuration of Home Assistant includes.

### Highlight clips

With a *Clip camera*, the highlight photo also records each moment as a clip: from *Seconds before* the photo to *Seconds after* it, saved as an MP4 beside the photo, under its name with `.mp4`, such as `2026-09-26_21-05-33_Alex_180.mp4`. The [highlight gallery](#highlight-gallery) lists it as *Clip · 180 · Alex · Sep 26* with the picture of its photo and plays it in the browser.

- **The camera:** any camera with a video stream in Home Assistant, such as an RTSP camera through the *Generic Camera* or *ONVIF* integration, or the camera of your stream. The board cameras of Autodarts give pictures only, which can't be recorded.
- **The seconds before the dart:** Home Assistant keeps them only while the stream of the camera runs. Open the camera entity, its settings (⚙), and turn on *Preload camera stream*; without it, the clip starts at the photo.
- **One clip at a time:** a camera records one clip at a time. A moment that comes while the clip of the one before is still recording gets its photo without a clip, and the log says why; the clip before it records to the end.
- [`homedarts.save_highlight`](entities.md#save-a-highlight-photo-homedartssave_highlight) records the clip in the background with Home Assistant's [`camera.record`](https://www.home-assistant.io/integrations/camera/), which writes only to folders Home Assistant may write to, such as the media folder of the gallery. An older version of the integration keeps the clips in the folder, but its gallery lists only the photos.
- With the [stream overlay](scoreboard.md#stream-overlay) of the scoreboard, the camera of your stream shows the score as well.

### Light show with WLED and other lights

Give every moment you like its own actions; moments without actions stay dark. A WLED preset that you saved in WLED as "180", for a 180:

```yaml
action: select.select_option
target:
  entity_id: select.wled_preset
data:
  option: "180"
```

A WLED effect at full brightness, for example for a won match:

```yaml
action: light.turn_on
target:
  entity_id: light.wled
data:
  effect: Fireworks
  brightness_pct: 100
```

Plain room lights in the color of the player who won the leg, from player 1 to 4; for a bust, `rgb_color: [255, 0, 0]` turns them red:

```yaml
action: light.turn_on
target:
  entity_id: light.dartroom
data:
  rgb_color: "{{ [[255, 0, 0], [0, 90, 255], [0, 200, 80], [255, 200, 0]][player - 1] }}"
  brightness_pct: 100
```

- **Back to normal:** choose the moments with actions under *Moments with an effect*, and add your lights to *Restore these lights*, for WLED the WLED light rather than the preset select. Before an effect, the blueprint saves their state in a scene, and after *Effect duration* it restores color, brightness and effect. Leave the lights empty if your actions end the effect themselves. Moments you don't choose run their actions and nothing else, so a moment without actions never pauses the board.
- **Pause the detection:** flashing light next to the board can make the cameras see darts that are not there. Turn on *Pause the detection during effects* and choose the *Detection* switch: the detection stops for the effects of the chosen moments and starts again afterwards, but only if it was running. When the detection stops, the visit on the board counts as finished, as after a takeout: the practice game books it and the next player is up.
- **One after the other:** a moment that happens while an effect plays waits for it, and each effect restores the lights it found. Up to nine moments wait, enough for the match that wins a tournament with its personal bests and achievements. The automation runs in queued mode, because a restarted effect would never restore the lights and parallel effects would mix on the same lights.
- **The daily goal** is reached with a dart in the middle of a visit, so its effect never pauses the detection: the rest of the visit still counts.
- **The end of a training session** stops the board: the [training session routine](#training-session-routine) turns the detection off. A session that ends while an effect plays ends the effect at once, so the lights come back before the routine's actions for the end of the session, and the detection stays off. A new session keeps the board running: the effect plays to its end, and the detection starts again. A new best session average comes when a session ends; its effect plays, but never pauses the detection, because the pause would start it again afterwards.
- **Takeout and board clear** set a look of their own, for example a bright board light while you pull the darts and your normal light afterwards. Turn on *React to the takeout* for them. They are not restored and don't pause the detection; while the setting is off, takeouts never wait in the queue.
- **The bot:** its darts are not in the board, so its moments stay dark unless you turn on *Also for the bot*. A leg or match it wins in a team match plays anyway.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/light-show-effect-dark.png">
  <img src="images/en/light-show-effect-light.png" alt="How an effect of the light show plays: a moment with an effect saves the lights and pauses the detection if it runs, unless the moment is the daily goal or a new best session average. Its actions start the effect, which plays for the effect duration. If a training session ends meanwhile, the effect ends at once: the lights are restored and the detection stays off. A new session lets the effect play to its end. After the effect, the lights are restored and a paused detection starts again" width="460">
</picture>

### Score display on an AWTRIX or a PixelIt

A pixel display at the board shows the score from across the room, as on a dart machine: the score of the player at the board after every dart, in green with its route when a checkout is possible, a 180 or a bust for a few seconds, and the winner of the match until the idle time is over or you start the next game.

<img src="images/score-display.svg" alt="A pixel display at the board, five times: 501 in white, the score of the player at the board; 40 D20 in green, a score to check out with its route; 180! in gold; BUST in red; LEA WINS in gold, the winner of the match" width="408">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/score-display-dark.png">
  <img src="images/en/score-display-light.png" alt="How the score display follows the game: every dart, correction or change of the player at the board shows the score of the player at the board, in green with the route when a checkout is possible. A 180, a bust, a won leg or the winner of a match flashes for the flash duration; then the score comes back, or the winner stays when the match is over. When the game is switched off, or nothing happens for the idle time, the display goes back to its clock" width="460">
</picture>

- **AWTRIX 3,** for example on an Ulanzi TC001: connect it to your MQTT broker in its web interface under *MQTT*, add the [MQTT integration](https://www.home-assistant.io/integrations/mqtt/) to Home Assistant with the same broker, and enter the *Prefix* of the display as *MQTT prefix*. The game shows as a notification that stays until the next one replaces it, in front of the apps of the display; its middle button dismisses it. At the end of the game the blueprint dismisses it, and the apps come back.
- **PixelIt over MQTT:** turn on MQTT in the settings of the PixelIt with the broker of Home Assistant's MQTT integration, and enter its *MQTT master topic*, by default `pixelit`, as *MQTT prefix*.
- **PixelIt over HTTP,** without MQTT: add a REST command for the display to `configuration.yaml`, with the address of your PixelIt, and restart Home Assistant. The blueprint hands it the screen in `screen`, and the command sends it to the display:

  ```yaml
  rest_command:
    pixelit_screen:
      url: "http://192.0.2.20/api/screen"
      method: post
      content_type: "application/json"
      payload: "{{ screen | to_json }}"
  ```

  A PixelIt shows each screen until the next one, so at the end of the game the blueprint brings back its clock.

How it follows the game:

- **Every dart** changes the *Practice remaining score*, and the display with it: also a correction, an undone visit and the next player when you pull the darts. The bot's darts count, too, as on the scoreboard.
- **A moment** flashes for the *Flash duration*, and then the score comes back. The next dart, or the next player after the takeout, ends a flash early, so the display always shows the game as it is. Outside the practice game, for example in free play, a 180 flashes as well, and the clock comes back after it.
- **The end:** a finished match keeps its winner on the display. When you switch the practice game off, the clock comes back at once; otherwise after *Back to the clock after* without a dart. A restart of Home Assistant, or saving this automation before the wait is over, shows the game again and starts the wait anew; saving another automation changes nothing. Without a game, the display belongs to its own apps and notifications: the blueprint sends nothing but the moments (and the clock after them).

Your own *Score* is a template. With the name of the player in a match before the score, for example `Sam 81 T15 D18`:

```text
{{ who ~ ' ' if players > 1 }}{{ remaining if remaining != '' else points }}{{ ' ' ~ checkout if checkout }}
```

With the target of a party game next to the points, for example `12 D16`:

```text
{{ remaining if remaining != '' else (points ~ ' ' ~ target) }}{{ ' ' ~ checkout if checkout }}
```

### Weekly report on your phone

Replace the *Notification actions* of the weekly report with a notification of the Home Assistant app:

```yaml
action: notify.mobile_app_your_phone
data:
  title: "{{ title }}"
  message: "{{ message }}"
```

The ready-made `summary` reads, for example: *312 darts in 95 minutes at the board, 3 sessions. 3-dart average 54.2 (+2.1 on the week before). Best visit 140, 1 × 180. Checkout rate 31.2 %. 4 days in a row. 2 new personal bests.* Parts without a value, such as a week without 180s, are left out.

<img src="images/en/weekly-report-notification.png" alt="The notification Your darts week in Home Assistant with the darts, sessions, 3-dart average, best visit and streak of the week" width="468">

The title and the summary are in the language of Home Assistant, for example *Deine Dartwoche* and *312 Darts in 95 Minuten am Board, 3 Sessions. 3-Dart-Average 54,2 (+2,1 zur Vorwoche).* in German. For words of your own, write your own *Title* and *Message*. A shorter German report, in the YAML mode of the automation:

```yaml
use_blueprint:
  path: Dennis-Otto/weekly_report.yaml
  input:
    board_events: event.autodarts_board_events
    report_title: Deine Dartwoche
    report_message: >-
      {{ darts }} Darts{{ ' in ' ~ training_minutes ~ ' Minuten' if training_minutes else '' }}{{ ', 3-Dart-Average ' ~ (average | replace('.', ',')) ~ (' (' ~ ('+' if average_change > 0 else '') ~ (average_change | replace('.', ',')) ~ ')' if average_change is not none else '') if average is not none else '' }}{{ ', ' ~ scores_180 ~ ' × 180' if scores_180 else '' }}{{ ', ' ~ streak ~ (' Tag' if streak == 1 else ' Tage') ~ ' in Folge' if streak else '' }}.
```

## Board events

All realtime moments arrive through the **Events** entity of the board. Each event carries an `event_type` and its details; see the [event reference](entities.md#board-events). The examples use `event.autodarts_board_events`, the entity ID of a board named *Autodarts Board* in a Home Assistant set to English. Home Assistant forms entity IDs from the names in its language, so in German, Dutch, French or Spanish the IDs read differently, for example `event.autodarts_board_ereignisse` in German. A board set up with an earlier version keeps the ID it got then, such as `event.autodarts_board_board_events`.

<img src="images/en/board-events.png" alt="The Events entity of the board in Home Assistant: the last event Visit thrown, its history, and the activity with every dart detected, the visit and the takeout" width="760">

Open the entity on the device page to watch the events arrive while you throw; its activity lists every event with the time it happened.

In the automation editor, choose the trigger **Event received** (*Entity → Event*), select the *Events* entity of your board and the event types you want. In YAML:

```yaml
triggers:
  - trigger: event.received
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - visit_thrown
```

A visit of three darts arrives as `visit_thrown` the moment its third dart lands, and as `visit_completed` when the darts are pulled. For celebrations and calls, use `visit_thrown`, and add `visit_completed` whose `thrown` attribute is `false` for visits with fewer darts.

Darts entered or corrected in Home Assistant carry `manual: true`, and the events of the [bot](entities.md#bot) `bot: true`; see [leave the bot out](#leave-the-bot-out).

Read the details from `trigger.to_state.attributes`, not from the current state of the entity. Two events can follow each other within milliseconds, for example `visit_completed` and `takeout_finished`, and the current state may already show the second one.

## Examples

The entity IDs in the examples are those of a board named *Autodarts Board* in a Home Assistant set to English; yours depend on the name of your board and on the language of Home Assistant during setup. You find them on the device page of the board.

### Flash the lights for a 180

```yaml
alias: Darts - 180 light show
triggers:
  - trigger: event.received
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - visit_thrown
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.attributes.get('score') == 180 }}"
actions:
  - action: light.turn_on
    target:
      entity_id: light.dartroom
    data:
      effect: colorloop
  - delay: 10
  - action: light.turn_on
    target:
      entity_id: light.dartroom
    data:
      effect: none
      brightness_pct: 100
mode: single
```

### Light up the board while you pull the darts

```yaml
alias: Darts - takeout light
triggers:
  - trigger: event.received
    id: started
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - takeout_started
  - trigger: event.received
    id: finished
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - takeout_finished
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: started
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.board_light
            data:
              brightness_pct: 100
    default:
      - action: light.turn_on
        target:
          entity_id: light.board_light
        data:
          brightness_pct: 60
mode: queued
```

### Notify a camera problem

```yaml
alias: Darts - camera problem
triggers:
  - trigger: state
    entity_id: binary_sensor.autodarts_board_camera_problem
    to: "on"
    for:
      minutes: 2
actions:
  - action: notify.mobile_app_phone
    data:
      title: Darts
      message: A board camera delivers no images. Check the camera and its cable.
mode: single
```

### Stop the detection at night

```yaml
alias: Darts - stop detection at night
triggers:
  - trigger: time
    at: "01:00:00"
conditions:
  - condition: state
    entity_id: switch.autodarts_board_detection
    state: "on"
actions:
  - action: switch.turn_off
    target:
      entity_id: switch.autodarts_board_detection
mode: single
```

### Prepare the board when a training session starts

Switch on the board light, start the detection and calibrate the cameras when a session starts, and switch everything off when it ends. Turn off *Start sessions automatically* and start sessions with the *Training session* switch, for example from the training card. Leave out the calibration when the board's *Calibrate on start* setting is on, and don't combine this with automations that switch the detection by presence.

```yaml
alias: Darts - training session routine
triggers:
  - trigger: event.received
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - session_started
    id: started
  - trigger: event.received
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - session_ended
    id: ended
conditions:
  # "New training session" ends a session and starts the next one at once.
  - condition: template
    value_template: "{{ trigger.to_state.attributes.get('reason') != 'new_session' }}"
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: started
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.dart_board
          - action: switch.turn_on
            target:
              entity_id: switch.autodarts_board_detection
          # The dart that started a session is still in the board.
          - if:
              - condition: template
                value_template: "{{ trigger.to_state.attributes.get('reason') != 'first_dart' }}"
            then:
              # Give the cameras time to open.
              - delay: 5
              - action: button.press
                target:
                  entity_id: button.autodarts_board_start_automatic_calibration
      - conditions:
          - condition: trigger
            id: ended
        sequence:
          - action: switch.turn_off
            target:
              entity_id: switch.autodarts_board_detection
          - action: light.turn_off
            target:
              entity_id: light.dart_board
mode: queued
```

### Start a new training session every Monday

```yaml
alias: Darts - weekly training session
triggers:
  - trigger: time
    at: "04:00:00"
conditions:
  - condition: time
    weekday: mon
actions:
  - action: button.press
    target:
      entity_id: button.autodarts_board_new_training_session
mode: single
```

### Call the game shot in a practice game

Announce a won leg and a bust of the [practice game](entities.md#practice-game) on your speakers, with the name of the player.

```yaml
alias: Darts - practice caller
triggers:
  - trigger: event.received
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - leg_won
        - bust
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.darts_room
      message: >-
        {% set event = trigger.to_state.attributes %}
        {# In a team match, the team wins the leg. #}
        {% set player = event.team_name or event.name or 'Player ' ~ event.player %}
        {% if event.event_type == 'leg_won' %}
          Game shot, and the leg, {{ player }}, in {{ event.darts }} darts.
        {% else %}
          Bust. {{ player }}, you still need {{ event.remaining }}.
        {% endif %}
mode: queued
```

To say it as the practice caller does, in the language of Home Assistant, use the words of the event: `message: "{{ trigger.to_state.attributes.call }}"`.

### Send the summary of a match

After a practice match of several players, send every player's numbers to your phone. `match_won` carries the [match summary](entities.md#practice-game) in `summary`; X01 has averages and checkouts, Cricket `mpr` and `marks`.

```yaml
alias: Darts - match summary
triggers:
  - trigger: event.received
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - match_won
actions:
  - action: notify.mobile_app_phone
    data:
      title: "{{ trigger.to_state.attributes.name or 'Player ' ~ trigger.to_state.attributes.player }} wins"
      message: >-
        {%- for player in trigger.to_state.attributes.summary %}
        {{ player.name or 'Player ' ~ player.player }}: legs {{ player.legs }}
        {%- if player.get('average') is not none %}, average {{ player.average }}{% endif %}
        {%- if 'scores_180' in player %}, 180s {{ player.scores_180 }}{% endif %}
        {%- if player.get('checkout_rate') is not none %}, checkout {{ player.checkout_rate }} %{% endif %}
        {%- if player.get('mpr') is not none %}, MPR {{ player.mpr }}{% endif %}.
        {%- endfor %}
mode: queued
```

### Celebrate a personal best and the daily goal

```yaml
alias: Darts - personal best
triggers:
  - trigger: event.received
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - personal_best
        - daily_goal_reached
actions:
  - action: notify.mobile_app_phone
    data:
      message: >-
        {% set event = trigger.to_state.attributes %}
        {% if event.event_type == 'personal_best' %}
          New personal best: {{ event.record | replace('_', ' ') }} {{ event.value }}
          (before {{ event.previous }}){{ ' by ' ~ event.name if event.name }}!
        {% else %}
          Daily goal reached: {{ event.darts }} darts, {{ event.streak }} days in a row.
        {% endif %}
mode: queued
```

### Count the training sessions of the month

The [training calendar](entities.md#training-calendar) answers questions about the past, for example in a script:

```yaml
sequence:
  - action: calendar.get_events
    target:
      entity_id: calendar.autodarts_board_training_calendar
    data:
      start_date_time: "{{ now().replace(day=1, hour=0, minute=0, second=0) }}"
      end_date_time: "{{ now() }}"
    response_variable: calendar
  - variables:
      sessions: >-
        {{ calendar['calendar.autodarts_board_training_calendar'].events
           | selectattr('summary', 'match', 'Training') | list | count }}
```

### Celebrate an achievement

A notification with the player, the achievement and its tier. The `achievement` attribute is the key of the [achievement](entities.md#achievements), such as `maximum` or `short_leg`; the table there names each one.

```yaml
alias: Darts - achievement
triggers:
  - trigger: event.received
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - achievement_unlocked
actions:
  - action: notify.mobile_app_phone
    data:
      message: >-
        {% set event = trigger.to_state.attributes %}
        {% set medal = ['bronze', 'silver', 'gold', 'platinum'][event.tier - 1]
           if event.tiers > 1 else 'unlocked' %}
        {{ event.name }}: {{ event.achievement | replace('_', ' ') }}, {{ medal }}!
mode: queued
```

### Start a game by voice

The blueprint [Start a game by voice](#start-a-game-by-voice) does this with sentences in English, German, Spanish, French and Dutch. For sentences of your own, let the action answer: it knows the games by their names in every language of the integration, and with `response_variable` it tells what started, or what was wrong, in words Assist can say. Keep a fixed word such as "game" before `{game}`, so the sentence never catches another command of Assist.

```yaml
alias: Darts - start by voice
triggers:
  - trigger: conversation
    command:
      - "let's play [a] game [of] {game} with {names}"
actions:
  - action: homedarts.start_game
    data:
      game: "{{ trigger.slots.game }}"
      players: "{{ trigger.slots.names | regex_replace(' and ', ' ') | regex_findall('[^ ]+') }}"
    response_variable: result
  - set_conversation_response: "{{ result.message }}"
mode: single
```

### Enter a visit by voice

The blueprint [Enter darts by voice](#enter-darts-by-voice) does this with sentences in English, German, Spanish, French and Dutch. For sentences of your own, in another language for example, let the action answer: with `response_variable` it says what the visit scored and left and who throws next, or why it was refused. With `player`, a misheard name never gets the visit.

```yaml
alias: Darts - a visit by voice
triggers:
  - trigger: conversation
    command:
      - "{name} threw {0..180:score}"
actions:
  - action: homedarts.enter_visit
    data:
      score: "{{ trigger.slots.score }}"
      player: "{{ trigger.slots.name }}"
    response_variable: result
  - set_conversation_response: "{{ result.message }}"
mode: queued
```

### Announce the results of a tournament

Call every result of a [tournament](entities.md#tournaments), the next match and the winner on your speakers.

```yaml
alias: Darts - tournament announcer
triggers:
  - trigger: event.received
    target:
      entity_id: event.autodarts_board_events
    options:
      event_type:
        - tournament_match_finished
        - tournament_finished
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.darts_room
      message: >-
        {% set event = trigger.to_state.attributes %}
        {% if event.event_type == 'tournament_finished' %}
          {{ event.winner }} wins the tournament, ahead of {{ event.runner_up }}!
        {% else %}
          {{ event.winner }} beats {{ event.loser }},
          {{ event.legs | max }} legs to {{ event.legs | min }}.
          {% if event.next %}Next up: {{ event.next | join(' against ') }}.{% endif %}
        {% endif %}
mode: queued
```

### Enter a visit by hand

For a player without cameras, or a board with the detection switched off: a script enters a whole visit, for example "T20 T20 S20" from a text field on the dashboard or from Assist, and passes the turn. Switch on *Practice manual entry* first; the darts count like detected darts and are marked `manual`.

```yaml
script:
  darts_enter_visit:
    alias: Darts - enter a visit by hand
    fields:
      darts:
        description: The beds of the visit, for example T20 T20 S20
        example: T20 T20 S20
        selector:
          text: {}
    sequence:
      - repeat:
          for_each: "{{ darts.split() }}"
          sequence:
            - action: homedarts.throw_dart
              data:
                segment: "{{ repeat.item }}"
      - action: homedarts.next_player
    mode: single
```

A button on the dashboard takes back the last visit, for a wrong reading noticed after the darts were pulled; the [scoreboard](cards.md#correcting-and-entering-darts) has one built in:

```yaml
type: button
name: Undo last visit
icon: mdi:undo
tap_action:
  action: perform-action
  perform_action: homedarts.undo_visit
  confirmation:
    text: Take the last visit back?
```

### Leave the bot out

The darts of the [bot](entities.md#bot) fire the usual events with `bot: true`, and its seat has no name. The blueprints know it:

- The visit score and the light show leave the bot out; turn on *Also for the bot* to include it.
- The highlight photo takes no photo of the bot's darts, which are not in the board.
- The callers call the bot "Bot" in the language of Home Assistant, like the scoreboard; your own messages call it by the *Word for the bot*.

An automation made from a blueprint takes no conditions of its own unless you take control of it, so use these settings there. To celebrate only your own visits in an automation of your own, add a condition:

```yaml
conditions:
  - condition: template
    value_template: "{{ not trigger.to_state.attributes.get('bot', false) }}"
```

## Online matches (experimental)

In online matches on play.autodarts.io, your own darts arrive as usual. Busts, won legs and matches and the darts of your opponents arrive through the optional online bridge and the browser extension Tools for Autodarts, as board events whose type starts with `online_`. The [online matches guide](online-matches.md) explains how to set it up.

## Adapting automations from older versions

Since version 2.0, the integration is HomeDarts for Autodarts, and its actions start with `homedarts.`: in automations and scripts that call one, replace `autodarts.` with `homedarts.`, for example `homedarts.next_player`. The entity IDs and the board events stay as they are, and the automations made from the blueprints go on working. [From Autodarts to HomeDarts](new-name.md) explains the switch.

Automations that celebrate a 180 or call a visit on `visit_completed` react only when the darts are pulled. Switch them to `visit_thrown` to react the moment the third dart lands, as in the [examples](#flash-the-lights-for-a-180).

Since version 1.0, the **Detection status** sensor reports translatable states: `stopped`, `throw`, `takeout_in_progress` and so on. Older versions reported the raw text of the Board Manager, such as `Stopped` or `Takeout in progress`. Update automations that compare against the old text:

| Before | Now |
| --- | --- |
| `Stopped` | `stopped` |
| `Starting`, `Stopping` | `starting`, `stopping` |
| `Throw` | `throw` |
| `Takeout`, `Takeout in progress` | `takeout`, `takeout_in_progress` |
| `Calibrating` | `calibrating` |
| `Error` | `error` |

The UI shows these states in your language. The *Last event* sensor still reports the raw Board Manager text. It is a diagnostic sensor now and, like *CPU usage*, starts disabled on a board set up with version 1.6.0 or later: enable it on the device page before an automation uses it. Boards set up before keep both entities as they are.
