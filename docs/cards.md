---
description: "The seven dashboard cards: live board, training, board status, scoreboard, doubles, players and leaderboard, the automatic dashboard and the card editor."
---

# Dashboard cards

[← Documentation](README.md) · [Deutsch](cards.de.md)

The integration includes seven cards. Home Assistant loads them automatically, so no dashboard resource and no separate HACS download are needed, and a page without a darts card loads less than 20 KB of them: the cards themselves come with the first card on a page; for [Home Assistant Cast](#home-assistant-cast), the integration keeps them in the dashboard resources itself. Each card:

- has a visual editor and follows your theme (light or dark) and [language](README.md#languages) (English, German, Dutch, French or Spanish);
- adapts to its width, from a phone to a wall tablet;
- finds your board by itself. With several boards, choose one in the editor.

**[Try them live](https://dennis-otto.github.io/homedarts-for-autodarts/demo/index.html)**: the scoreboard, the live, training and players cards play a 501 against the bot, a Cricket game and a tournament in your browser, without Home Assistant.

To add one, edit a dashboard, select **Add card** and search for **HomeDarts**. The card picker names the cards **HomeDarts**, **HomeDarts training**, **HomeDarts board status**, **HomeDarts scoreboard**, **HomeDarts players**, **HomeDarts doubles** and **HomeDarts leaderboard**, in your language, and links each one to its section below.

**On this page:** [Live card](#live-card) · [Training card](#training-card) · [Board status card](#board-status-card) · [Scoreboard card](#scoreboard-card) · [Doubles card](#doubles-card) · [Players card](#players-card) · [Leaderboard card](#leaderboard-card) · [Automatic dashboard](#automatic-dashboard) · [Home Assistant Cast](#home-assistant-cast) · [Card editor](#card-editor) · [Accessibility](#accessibility) · [Tips](#tips)

The guides show the cards at work: [games and rules](games.md), [scoreboard at the board](scoreboard.md) and [statistics and players](statistics.md).

## Live card

`custom:homedarts-card` shows the current visit, dart by dart, on a board drawn with the geometry of the Autodarts Board Manager.

<picture>
  <source media="(prefers-color-scheme: light)" srcset="images/en/card-light.png">
  <img src="images/en/card.png" alt="Live card with visit score, dart slots, the board with blinking beds, statistics, connection chips and controls" width="760">
</picture>

- **Visit:** score, the three dart slots and a progress indicator. The latest dart is outlined. A dart with a pencil at its top right corrects with a tap: the [pad of the scoreboard](#correcting-and-entering-darts) opens below the slots, with its keys, its board, the loupe and the zoom. The bot's darts, and darts that older integrations report without their number, have no pencil.
- **Last visits:** the scores of your last five visits, colored like the training card's chart. Hover one for its darts.
- **Practice game:** while a [practice game](games.md) runs, the remaining score, the checkout route and busts appear above the dart slots, and the board outlines the bed to aim at next. Where no checkout exists, the [setup](entities.md#setup-hints) takes its place, for example *T20 T20 S17 leaves 32*, and the board outlines its first dart; "No checkout possible" appears only when no setup exists for a score that could be finished in one visit: up to 170 with double out, up to 180 without. The [bot](entities.md#bot) is listed as *Bot*. In a match, a list shows every player with the remaining score, legs, sets and average, and highlights the player at the board; [start scores](games.md#start-scores-handicap) of their own appear beside the names, and a team match lists the two teams. A won match shows its result in large type, for example 2 : 1, and the [match summary](#match-summary) instead of the list. In the [party games](games.md#party-games), the panel shows the round or hole, the target and every player's points or, in Killer, their number and lives, and who is out. The bull of Around the Clock and Halve-It, where the outer bull counts too, reads *Bull (25/50)*, and both bull beds are outlined. During a bull-off it lists the bed and the distance of every dart and who leads, and it says when a tie throws again. In the [Cricket games](games.md#cricket-games), a chalkboard shows the marks of every player or team on the numbers of the game, the points and the marks per round, dims the numbers everybody has closed and outlines the next open number on the board. Screen readers read the marks as words. In a [training game](games.md#training-games), the panel shows the target, the progress, darts and hit rate (Bob's 27: points and round; checkout training and 121 checkout: the route, or where the darts left cannot finish the score the [setup](entities.md#setup-hints) with the score it leaves, and the checkout rate; Catch 40, the JDC Challenge and the singles training: the round or part and the points), and the board outlines the beds of the target. The live card and the [scoreboard](#scoreboard-card) share how they show a game, so both always tell the same.
- **Board:**
  - Hit beds blink in the highlight color.
  - Numbered markers show where each dart landed.
  - The board glows in the detection status color of your theme: green (success) when ready, amber during a takeout, orange (warning) when stopped, purple while calibrating, red (error) when offline or when a camera has a problem.
- **Training statistics:** darts, 3-dart average, triples, bulls and 180s of the session.
- **Connections:** Board Manager, realtime and cameras. Tap a chip for details.
- **Controls:** start or stop detection, reset detection and calibrate. Resetting and calibrating need a second tap to confirm. Boards without a detection switch get the start or stop button that fits the board status.
- **Keypad:** on a [dartboard without Autodarts](without-autodarts.md), the keypad of the [scoreboard](#correcting-and-entering-darts) sits below the darts, and the connections and controls are left out. Its *Undo last visit* keeps its place and waits while no visit can be undone. With `keypad: true`, a board with Autodarts gets it too while *Practice manual entry* is on.

The board shows the visit; nothing on it reacts to a tap. Numbers, dates and times follow your [profile settings](https://www.home-assistant.io/docs/configuration/user-configuration/): number format, 12- or 24-hour clock and the time zone of the server or the browser.

<img src="images/en/card-visit.webp" alt="Animation: three darts land, their beds blink and the score adds up; the takeout empties the board" width="620">

<img src="images/en/correct-live.webp" alt="Animation: the live card shows T20 and S20 for 80; a tap on the second dart with its pencil opens the pad below the darts, a tap on T and on 20 corrects it, and the visit reads 120" width="620">

<img src="images/en/practice-checkout.webp" alt="Animation: a 141 checkout in a 501 leg. After each dart the remaining score, the route and the outlined bed change: T20 T19 D12, then game shot and a new leg" width="620">

<img src="images/en/card-match.png" alt="Live card during a 501 match of Alex and Sam: Alex at the board with 81 left and the route T19 D12, Sam with 361 left" width="760">

On a phone, the live card stacks the visit, the board, the statistics and the controls:

<img src="images/en/card-mobile.png" alt="The live card on a phone: the visit of T20, S5 and Bull for 115 points, the last visits, the board with the three darts, the training statistics and the controls" width="320">

<img src="images/en/cricket.webp" alt="Animation: Cricket between Alex and Sam. Alex closes the 20, scores 60 and hits a 19; after the takeout Sam closes the 19, scores 57 and hits a double 18" width="620">

<img src="images/en/training-game.webp" alt="Animation: Around the Clock. Each hit moves the target from 1 to 6 and outlines every bed of the next number on the board" width="620">

### Options

| Option | Values | Default | Description |
| --- | --- | --- | --- |
| `device_id` | device | first board | The board to show |
| `title` | text | board name | Card title |
| `layout` | `auto`, `horizontal`, `vertical`, `board` | `auto` | Board on the right, board below, or board only. `auto` switches to vertical on narrow cards |
| `board_style` | `classic`, `flat` | `classic` | Classic board with wires, or the flat look (*Flat* in the editor) |
| `highlight` | `visit`, `last`, `none` | `visit` | Highlight all darts of the visit, only the last one, or none |
| `blink` | boolean | `true` | Blink the hit beds |
| `show_markers` | boolean | `true` | Show dart positions |
| `show_numbers` | boolean | `true` | Show the numbers around the board |
| `show_stats` | boolean | `true` | Show the training statistics |
| `show_recent` | boolean | `true` | Show the last visits |
| `show_practice` | boolean | `true` | Show the practice game and the bed to aim at |
| `show_summary` | boolean | `true` | Show the [match summary](#match-summary) when an X01 or Cricket match ends |
| `summary_seconds` | 0–600 | `0` | How long the summary stays, in seconds; `0` keeps it until the next game starts |
| `corrections` | boolean | `true` | Correct a dart of the visit with a tap on it |
| `keypad` | boolean | `false` | Show the [keypad](#correcting-and-entering-darts) for darts entered by hand while *Practice manual entry* is on; on a [dartboard without Autodarts](without-autodarts.md) it shows unless `false` is set |
| `show_connection` | boolean | `true` | Show the connection chips |
| `show_controls` | boolean | `true` | Show the controls |
| `accent_color` | [color](#colors) | theme primary color | Labels and main button |
| `highlight_color` | [color](#colors) | `#ffd60a` (gold) | Hit beds and the latest dart |

With `layout: vertical` and `board_style: flat`, the board sits below the visit, in the flat look:

<img src="images/en/card-flat-style.png" alt="The live card in the vertical layout with the flat board style: the visit of T20, S5 and Bull for 115 points above the board, the training session and the controls below it" width="400">

With `layout: board`, the card shows the board alone:

<img src="images/en/card-board-only.png" alt="The live card in the board layout: only the board, with the three darts of the visit and the beds they hit lit up" width="400">

```yaml
type: custom:homedarts-card
layout: vertical
board_style: flat
highlight: last
highlight_color: "#00e5ff"
```

## Training card

`custom:homedarts-training-card` turns the local [training session](entities.md#training-session) into a dashboard you'll want to look at after every session.

<picture>
  <source media="(prefers-color-scheme: light)" srcset="images/en/training-card-light.png">
  <img src="images/en/training-card.png" alt="Training card with 3-dart average, heatmap, statistics tiles, most hit beds, personal bests and recent visits" width="760">
</picture>

- **3-dart average**, the number of darts and visits, and when the session started.
- **Streak and daily goal:** the [training streak](entities.md#personal-bests-streak-and-daily-goal) in days and today's darts, with a bar towards the daily goal that turns green when you reach it.
- **Heatmap:**
  - Every bed is colored by how often you hit it, from a dark blue violet (rarely) through teal and green to a light yellow (most often). The colors get lighter with the hits, so they also read for color-blind players and in gray, and the legend below the board shows the counts at both ends. `heatmap_palette: thermal` brings back the former rainbow.
  - Hover or tap a bed for its count and share. Screen readers get the counts of all hit beds as a list, the most hit first.
  - In `numbers` mode, the heatmap sums each number's singles, doubles and triples instead.
  - In `positions` mode, it shows where the darts landed, from the positions the board reports: a smoothed density from blue violet (few darts) to yellow (many), with the newest 300 darts as dots. For the session, the darts of the current visit show the moment they land, as blue pins, and join the logged darts when you pull them. Below the board, the [grouping](how-it-works.md#grouping) at up to three beds aimed at, for example *T20: grouping 38 mm · 80 % within 61 mm · 6 mm left of center*, with *4 mm tighter* when the newer darts group closer.
  - In `aim` mode, it shows where the player scores the most points per dart with their own spread, from 30 darts aimed at a treble: every aim point colored by its points per dart, a ring at the best aim, and below the board the best aim against the treble 20, the treble 19 and the bull, for example *T19: best aim · 18.3 points per dart* and *T20: 17.3 points per dart -1.0*. With fewer darts, the card says how many are missing. [Where to aim](statistics.md#where-to-aim).
  - The switches above the board choose the mode and whose darts it shows: the session, or a named player with all their hits and the positions of their last 1000 darts. The most hit beds follow the choice. [How positions are kept](how-it-works.md#dart-positions).
- **Statistics:** highest visit, 100+, 140+ and 180 visits, triple rate, doubles, bulls and misses. 180s light up in gold. The 100+, 140+ and 180 counts grow when you pull the darts, once the visit is complete. *Details ›* below the tiles opens the details of the session's darts. Screen readers read every tile.
- **Most hit beds:** the top five, with count and share: of the session's darts, or of the hits a player's profile counted.
- **Personal bests:** every [personal best](entities.md#personal-bests-streak-and-daily-goal) that has a value: highest visit and checkout, the fewest darts for every start score, the best Cricket marks per round, the best session average, Around the Clock, the doubles training, Bob's 27, the 121 checkout, Catch 40, the JDC Challenge, the singles training and the longest training streak. The section appears with the first record.
- **Recent visits:** a bar chart of your last visits with the session average as a dashed line.
  - Bars are colored gray below 60, accent color from 60, green for 100+, orange for 140+ and gold for 180.
  - The visits come from the recorder, so the chart survives page reloads, and every visit shows, also when the turn passes at the same moment, as it does in a practice game.
  - An [undone visit](entities.md#undo-a-visit-homedartsundo_visit) leaves the chart; corrected, it comes back as a new visit. The bot's visits are left out, as they count for nobody.
- **Past sessions:** end time, duration, darts, 3-dart average and highest visit of your last five finished sessions.
- **Session controls:**
  - *Start session* and *End session* switch the [training session](entities.md#training-session) on and off. Ending needs a second tap to confirm.
  - *New session* ends the running session and starts the next one, also after a second tap.
  - The line next to the buttons tells whether a session is running or when the last one ended.

### Options

| Option | Values | Default | Description |
| --- | --- | --- | --- |
| `device_id` | device | first board | The board to show |
| `title` | text | *Training · board name* | Card title |
| `mode` | `beds`, `numbers`, `positions`, `aim` | `beds` | Heatmap per bed, per number, of the dart positions or of where to aim |
| `player` | text | the session | A player name: the heatmap starts with that player's darts. The editor lists the named players and takes any other name |
| `board_style` | `muted`, `classic`, `flat` | `muted` | The muted board lets the heatmap stand out |
| `heatmap_palette` | `accessible`, `thermal` | `accessible` | The colors of the heatmap and the most hit beds: `accessible` gets lighter with the hits, for every eye and in gray; `thermal` is the former rainbow from blue to red, at equal lightness |
| `history_size` | 5–60 | `20` | Visits in the chart; labels are shown up to 30 |
| `show_heatmap` | boolean | `true` | Show the heatmap |
| `show_heatmap_controls` | boolean | `true` | Show the switches of the mode and of whose darts the heatmap shows |
| `show_stats` | boolean | `true` | Show the statistics tiles |
| `show_bests` | boolean | `true` | Show the personal bests |
| `show_top` | boolean | `true` | Show the most hit beds |
| `show_history` | boolean | `true` | Show the recent visits |
| `show_sessions` | boolean | `true` | Show the past sessions |
| `show_reset` | boolean | `true` | Show the session controls |
| `accent_color` | [color](#colors) | theme primary color | Labels and 60+ visits |

```yaml
type: custom:homedarts-training-card
mode: numbers
history_size: 40
show_reset: false
```

On a phone, the training card stacks its sections, from the average down to the session controls:

<img src="images/en/training-card-mobile.png" alt="The training card on a phone: the 3-dart average with the streak and today's darts, the heatmap, the statistics tiles, the most hit beds, the personal bests, the recent visits, the past sessions and the session controls" width="320">

With `mode: positions` and `player: Alex`, the heatmap shows where Alex's darts landed, and below the board the grouping at each bed aimed at:

<img src="images/en/training-positions.png" alt="The heatmap in positions mode with Alex's darts: a density around the treble 20, the doubles 16 and 8 and the bull, and below the board the grouping at each bed aimed at" width="440">

The switches above the board choose the mode and whose darts the heatmap shows:

<img src="images/en/heatmap-modes.webp" alt="Animation: the heatmap switches from beds to numbers and positions of the session, then to Alex's positions and beds" width="400">

## Board status card

`custom:homedarts-status-card` shows the health of the board and gathers the maintenance actions in one place.

<picture>
  <source media="(prefers-color-scheme: light)" srcset="images/en/status-card-light.png">
  <img src="images/en/status-card.png" alt="Board status card with detection switch, Board Manager version and update, connections, CPU load, cameras and maintenance buttons" width="760">
</picture>

- **Detection:** a switch with the current status, tinted in the status color. Boards without a detection switch start and stop detection with its buttons; the switch then follows the board status.
- **Board Manager:** the installed version and, with Board Manager 2, a badge for an available update, *Update to 2.0.2 ›*. Tap it for its details.
- **Connections:** Board Manager, realtime and the cloud connection of the board.
- **Board PC** (Board Manager 2): CPU and memory load, the detection frame rate and the share of darts the board corrected, each if you enabled its sensor. A value with an arrow opens its history, and so does the system line. The tile stays hidden while it has nothing to show.
- **Cameras:** a tile for every camera with its status and frame rate (if the frame-rate sensor is enabled) and its own calibration. Its name with an arrow opens the camera. A camera with a problem turns red. The keyboard focus stays on a calibration button while it asks for confirmation.
- **Maintenance:** calibrate all cameras, reset detection and restart Board Manager. Each needs a second tap to confirm.

A [dartboard without Autodarts](without-autodarts.md) has none of these; the card says so in a sentence below its status.

### Options

| Option | Values | Default | Description |
| --- | --- | --- | --- |
| `device_id` | device | first board | The board to show |
| `title` | text | board name | Card title |
| `show_connection` | boolean | `true` | Show the connections |
| `show_system` | boolean | `true` | Show the board PC load |
| `show_cameras` | boolean | `true` | Show the cameras |
| `show_controls` | boolean | `true` | Show the maintenance buttons |
| `accent_color` | [color](#colors) | theme primary color | Labels and the detection switch |

```yaml
type: custom:homedarts-status-card
show_system: false
```

## Scoreboard card

`custom:homedarts-scoreboard-card` is made for a tablet or TV next to the board: large enough to read from the oche, and it always shows what is being played.

<img src="images/en/scoreboard.webp" alt="Animation: the scoreboard during a 501 match. The turn passes between Alex and Sam after every visit, and Alex checks out 141 with T20 T19 D12 to win the match" width="760">

- **Training plans:** with no game on the board, the [plan of the day](games.md#training-plans) waits behind one tap. During a plan, the header says the step, such as *Step 2 of 4: Bob's 27*, with *Skip* and *Stop*. The live card shows the same step and buttons.
- **X01:** a tile for every player with the remaining score, legs, sets and average. The player at the board is outlined and gets the checkout route, a bust or the game shot; where no checkout exists, the [setup](entities.md#setup-hints) with the score it leaves, such as *T20 T20 S17 leaves 32*. Players with a [start score](games.md#start-scores-handicap) of their own show it beside the name, and the [bot](entities.md#bot) its level.
- **Teams:** in a team match, two team tiles such as *Alex & Kim* against *Sam & Lea*, with the shared score, the average of each partner and the partner at the board in bold. The banner names the winning team.
- **Cricket:** a large chalkboard with the marks of every player, the points and the marks per round; the next open number is shown in its top-left corner, above the numbers, and in a match the column of the player at the board frames where a dart scores in green and what to close in amber. Tactics fills it from 20 down to 10 in smaller type, Wild Mouse adds rows for doubles, triples and 3 in a bed, Cut-Throat Cricket reminds that the fewest points win, Random Cricket shows the numbers the leg drew, Hidden Cricket a question mark for every number no dart has found yet, and a team match has a column per team.
- **Party games:** the round and the target, every player's points, or in Killer their number and lives in red hearts. Golf and Baseball add a scorecard of every hole or inning with the total; after a tie, the extra rounds show as a play-off and the players out of it are dimmed.
- **Bull-off:** the bed of every player's dart and its distance from the center, if the board measured it. Once two darts are in, the one that leads is marked. A tie shows the banner *Tie – throw again*.
- **Training games:** the target in large type, with the progress, darts and hit rate (Bob's 27: points and round; checkout training and 121 checkout: the score, the route, or where the darts left cannot finish it the setup with the score it leaves, the checkout rate and the best score reached; Catch 40: the number, the visit and the points; the JDC Challenge: the part and the points; singles training: the round and the points).
- **Between games:** the title (the board name unless you set `title`) and the score of the current visit together with darts, 3-dart average, highest visit and 180s of the training session, the training streak and today's darts towards the daily goal.
- **Winner:** a banner names the winner of the match with the result, for example *Alex wins the match 3 : 2!*, until the next dart. The result counts legs, or sets in a match of sets; a match of one leg has none.
- **Match summary:** when an X01 or Cricket match ends, the [match summary](#match-summary) takes the place of the players.
- **Tournaments:** the round of the match, and between the matches the table or the bracket; see [tournaments](#tournaments).
- **Pictures:** players [linked to a person](entities.md#link-a-player-to-a-person-homedartslink_player) show the person's picture next to their name.
- **Visit:** the three darts of the current visit along the bottom, and beside them its score. While the board is empty, and between games where the big number is the visit, that tile shows the last visit instead, which a tap takes back. A tap on a dart corrects it; see [correcting and entering darts](#correcting-and-entering-darts). Nothing on the card changes its height during a game: the lines for a route, a note and the details keep their room while empty, and a narrow tile keeps two lines for a long route from the start.
- **Caller:** with `caller: true`, the screen at the board calls the game itself in the language of Home Assistant: English, German, Dutch, French or Spanish (other languages hear English). It calls only what counts:
  - X01: the points a visit scored, "No score" for a bust or a visit before the opening double, "you require 81" whenever the remaining score can be finished (up to 170 with double out, 180 without), "leave yourself 32" when only a [setup](entities.md#setup-hints) is possible, the game shot of a leg and the match, and a fanfare for a 180 that counted. The bot is called *Bot*.
  - Cricket games: the marks of a visit, such as "5 marks". Shanghai, Halve-It and Bermuda: the points on the target; Count-Up and Round the World: the points of the visit; Gotcha: the points of the visit, or "No score" for a visit that went too far; Baseball: the runs, such as "3 runs". Killer, Golf, where the last dart counts, and the training games get no score calls.
  - Checkout training, 121 checkout and Catch 40: what the next attempt or visit requires, such as "You require 121".
  - Darts thrown after a bust or a game shot are not called.

  It uses the speech output of the browser, so nothing needs to be set up in Home Assistant. Browsers play sound only after a tap: tap *Caller* on the scoreboard once to switch it on, and again to mute it. The button keeps its name; its pressed state and the speaker symbol show whether the caller is on.

  An X01 visit counts from the score the integration says it started from, so a moment the screen missed, such as a takeout while a tablet woke up, never adds two visits up. A scoreboard that was away, on another view or without its connection to Home Assistant, calls and celebrates nothing that happened meanwhile: it follows the game again from the states it finds when it is back.

<img src="images/en/bot-match.webp" alt="Animation: a 301 match against the bot on the scoreboard. Alex throws and pulls the darts, the bot's three darts land one by one, and Alex is at the board again" width="760">

<img src="images/en/scoreboard-bot.png" alt="Scoreboard of a 301 match against the bot: Alex, who plays from a start score of 169, has 169 left, and instead of a checkout the card shows T20 T20 S17 leaves 32; the bot's tile reads Bot Level 80" width="760">

<img src="images/en/killer.webp" alt="Animation: Killer for Alex, Sam and Kim on the scoreboard. Everybody throws for a number, Alex becomes a killer and takes Sam's lives, Kim becomes a killer too, and Alex takes the last life to win" width="760">

<img src="images/en/scoreboard-cricket.png" alt="Scoreboard in Cricket between Alex and Sam: the chalkboard with marks, points and marks per round, and T19 as the next target" width="760">

<img src="images/en/golf.webp" alt="Animation: Golf for Alex and Sam on the scoreboard. After every visit the scorecard fills: Alex plays 1, 3 and 2, Sam 4, 5 and 5, and the fourth hole is under way" width="760">

<img src="images/en/scoreboard-teams.png" alt="Scoreboard of a 501 team match: Alex and Kim with 45 left against Sam and Lea with 216, Sam at the board in bold with his average" width="760">

The [automatic dashboard](#automatic-dashboard) has a *Scoreboard* view that shows the card across the whole screen. With `full_height`, the scoreboard is exactly one screen high: the numbers and tables grow and shrink with the room the banner, the visit and the keypad leave, so nothing has to be scrolled, from an 800 × 480 display to a TV. A portrait tablet shows two players one above the other, three or four two by two. On a phone, the full-height scoreboard leaves room for the browser's address bar. The full-screen button at the top right puts the scoreboard alone on the screen, without the bars of the browser and Home Assistant's header and sidebar, and keeps the screen on meanwhile; see [full screen](scoreboard.md#full-screen). The guide [scoreboard at the board](scoreboard.md) shows how to set up a tablet or TV, the caller and idle mode step by step.

### New game screen

Choose the next game at the board, without a phone: tap **New game** below the score between games, or at the top right during a game. A few seconds after a match or a training game ends, or after its [match summary](#match-summary), the screen also opens by itself, with the last choice ready for a rematch; a dart thrown instead closes it again.

<img src="images/en/lobby.webp" alt="Animation: on the tablet, New game opens the screen, Cricket is chosen, Sam joins Alex, the legs per set go up to three and the game starts on the scoreboard" width="760">

- **Game:** every game of *Practice game*, grouped into X01, Cricket, party games and training games. `lobby_games` limits the choice.
- **Players:** up to four, in a party game up to eight, in throwing order. Tap a name to add the player, ▲ and ▼ to move them, ✕ to remove them. The names come from the player profiles and the player name fields; players [linked to a person](entities.md#link-a-player-to-a-person-homedartslink_player) who is at home come first, with their picture and ⌂. Type a new name, or add a guest without one. With nobody chosen, one player without a name throws. In X01 and the Cricket games, *+ Bot* seats the [bot](entities.md#bot) after the players, at level 60; − and + change its level in steps of 10, from 20 to 120, and ✕ sends it home. With the bot, up to three players play. Killer needs two players; training games take the first player only. In X01, − and + beside a player set a [start score](games.md#start-scores-handicap) of their own in steps of 100, from 101 to 1001.
- **Format:** legs per set and sets to win, for a match of several players.
- **Options:** for X01 the in and out mode, *Straight*, *Double* or *Master*, the bull mode *25/50* or *50/50* and *Max rounds* in steps up to 50, a tournament straight or double in and out alone; and the bull-off for a match, with bull-off by distance where the board offers it. With four players of X01 or a Cricket game, *Teams* plays 1 and 3 against 2 and 4. In X01, *Fair start* works the [start scores](games.md#fair-start) out from the averages.
- **Start:** starts the game with [`homedarts.start_game`](entities.md#start-a-practice-game-homedartsstart_game), and the scoreboard shows it at once. If detection is stopped, the start switches it on, because no dart counts without it; the screen says so above the button. The start stays at the bottom of the screen while the page scrolls. During a game, *End game* stops it after a second tap.

The screen never opens in the preview of the card editor.

<img src="images/en/lobby-bot.png" alt="The new game screen with 501 chosen: Alex and the bot at level 70 with − and + to change it" width="760">

<img src="images/en/scoreboard-lobby.png" alt="The new game screen on a landscape tablet: the games by group with 501 chosen, Alex and Sam with their pictures, Sam starting from 301, three legs per set, double out and the start button" width="760">

### Correcting and entering darts

The darts of the visit along the bottom are buttons while `corrections` is on, which it is by default.

<img src="images/en/correct-dart.webp" alt="Animation: the scoreboard shows T20, S20 and T20 for 140; a tap on the second dart opens the pad, a tap on T and on 20 corrects it, and the visit reads 180" width="760">

- **Correct a dart:** tap a dart the board read wrong. A pad opens with S, D and T, the numbers 1 to 20, 25, Bull and Miss; S, D or T is set to the dart's bed. Tap the multiplier, then the number, or 25, Bull or Miss, and [`homedarts.correct_dart`](entities.md#correct-a-dart-homedartscorrect_dart) puts the dart there. The remaining score and the visit follow at once. A second tap on the dart, or *Cancel*, closes the pad. The bot's darts cannot be corrected.
- **Where the dart is:** *Keys | Board* at the top of the pad switches from the keys to the board. Tap the spot where the dart is: the bed follows from it, and the dart is logged there in the [dart positions](how-it-works.md#dart-positions). The dashed ring shows where the board saw the dart. A dart corrected with the keys has no position, because the board misread the spot as well. The board stays the pad's view until *Keys* is chosen, and the keypad uses it too.

  <img src="images/en/correct-dart-board.webp" alt="Animation: the board read the second dart as T20 for 180; a tap on it opens the pad, Board shows the board with a dashed ring where the board saw the dart, and a tap on the single 20 above it corrects the visit to 140" width="760">

- **Small screens:** on a card narrower than 600 pixels or a screen lower than that, such as on a phone upright or on its side, the board of a correction opens two and a half times larger around where the board saw the dart; a dart without a position and the keypad open the whole board. A round magnifier switches between the two on every screen, on a phone from the board's corner as on a map: with its plus it zooms in around the dart being corrected or else the last dart with a position, with its minus it shows the whole board. A finger held on the board shows a loupe above it, or beside it near the top edge, with the spot under the finger enlarged and a cross on it; the dart goes where the finger lets go. Two fingers zoom up to five times and move the board, and set no dart. The loupe and the fingers work on every touch screen, also a large monitor; a mouse clicks as before.

  <img src="images/en/correct-dart-loupe.webp" alt="Animation on a phone: the board read the second dart as T20 for 180; a tap on it and on Board opens the board zoomed in around the dashed ring where the board saw it; a finger slides up from the ring, the loupe above it shows the single 20 under a cross, and where the finger lets go the visit becomes 140" width="360">

- **Keypad:** with `keypad: true`, a keypad shows while *Practice manual entry* is on, for darts the board missed or a player without cameras; on a [dartboard without Autodarts](without-autodarts.md) it always shows, unless the card sets `keypad: false`, for example on a TV without touch. Every tap on a bed enters a dart with [`homedarts.throw_dart`](entities.md#enter-a-dart-homedartsthrow_dart), and the next dart starts from S again. *Next player* ends the visit without a takeout; it needs a second tap. While the bot is at the board, the keypad waits.
- **Score:** in X01, *Keys | Board | Score* has a third view, the score of a visit: its digits in as many rows as the numbers of the keys, the score typed and what it leaves in the head, and **OK**, which sends [`homedarts.enter_visit`](entities.md#enter-a-visits-score-homedartsenter_visit). A score that no visit makes from where the player stands, such as 179, or 180 before the opening double with double in, says so, and **OK** waits for another. A checkout asks for its darts where it could take fewer than three, and for the darts at a double where they can differ; a visit that leaves a double in reach asks for the darts at it. The answers keep the rows of the digits, so the pad keeps its height, and *Cancel* goes back to the score. A keyboard types the score too: when the score view opens, the pad takes the focus; digits type the score, Backspace takes back a digit, and Enter sends it, also while a digit of the pad has the focus. During a question, the digits of its answers answer it, and Escape or Backspace go back to the score. The pad keeps the focus after a score went in, so the next one can be typed at once, and while the bot throws, the keys wait as the pad does. On a narrow pad, such as on a 360 pixel phone, the three views show icons, the dots of a keypad, the rings of the board and a sum, so they keep the line of S, D and T; their names stay their labels for screen readers.
- **Undo:** the tile *Last* beside the darts shows the last visit with a curved arrow while [`homedarts.undo_visit`](entities.md#undo-a-visit-homedartsundo_visit) can take it back, for a wrong reading noticed after the darts were pulled or a typo on the keypad. A tap turns it red and asks *Undo?*, a second tap takes the visit back; it comes back to correct its darts, and the keypad's *Next player* or [`homedarts.next_player`](entities.md#pass-the-turn-homedartsnext_player) ends it again. With the keypad too, the tile is the undo, so the keypad keeps the same keys after every visit.
- **Marks:** a dart that a tap corrects has a frame and a pencil at its top right; one entered or corrected by hand has a dashed frame, and the bot's darts are tinted in the accent color. On a dartboard without Autodarts, where every dart is entered by hand, only corrected darts get the dashed frame.

On a full-height scoreboard in landscape, the pad and the keypad sit beside the scores, so the players, the visit and the pad fit the screen together. The pad and the keypad make room for the new game screen, idle mode, the match summary and a tournament's table, and never react in the preview of the card editor.

<img src="images/en/scoreboard-keypad.png" alt="The scoreboard with the keypad: Alex has entered T20 and S19 by hand, marked with dashed frames; below, S, D and T, the numbers 1 to 20, 25, Bull, Miss and Next player" width="760">

### Tournaments

During a [tournament](entities.md#tournaments), the scoreboard follows it:

- **During a match:** the title line names the round and the match, for example *Tournament · Semi-final · Match 5 of 7*.
- **Between the matches:** the [summary](#match-summary) of a match stays for *Tournament summary duration* (8 seconds), then, during *Tournament pause*, the table of a round robin, the tables of the groups, side by side with the places that go on marked, or the bracket shows, a double elimination's losers' bracket below its winners' bracket, with the next match, its round and a countdown to its start. Brackets of 16 and 32 places have smaller boxes. *Start now* starts it at once. During a tournament, the new game screen does not open by itself.
- **Table:** the position, matches played, won and lost, legs won and lost, the leg difference, the 3-dart average (Cricket: MPR) and the points. The players of the next match are marked, the winner of the tournament gets 🏆.
- **Bracket:** a column for every round, with the match for third place below the final; byes, open places and results; the next match is outlined. A player who goes on slides into the next round; on devices set to reduce motion, the places fill without moving.
- **Winner:** after the last match, a banner names the winner of the tournament, and the table or the bracket stays until a new match begins.
- **Caller:** with the caller on and `call_results`, it announces every match as it starts, "Next match: Alex against Sam", and the winner of the tournament.
- **New game screen:** *Tournament* switches the screen to a tournament of named players, up to eight in a round robin and 32 in the other formats: X01, with start scores for a handicap, or a Cricket game, round robin, knockout, double elimination or groups and knockout, with groups the number of groups (*Auto* lets the board choose) and how many of each go on, which start from *Tournament groups* and *Tournament qualifiers per group*, legs and sets, the rules, the match for third place and a random draw. *Start tournament* starts it with [`homedarts.start_tournament`](entities.md#start-a-tournament-homedartsstart_tournament). During a tournament, *Stop tournament* ends it and its game after a second tap. Starting a new tournament while one is played stops that one first: the screen says so, and the start needs a second tap.
- **Several boards:** in a [tournament on several boards](games.md#a-tournament-on-several-boards), the scoreboard of every board plays its own match. Above the table or the bracket, a box for every board shows the players of its match, or when its next match starts, with the box of the card's own board outlined, and below the boxes the expected end of the tournament.
- **Idle mode:** the panel `tournament` shows the table or the bracket of the tournament being played or just finished, on several boards with the boxes of the boards.

<img src="images/en/tournament-table.png" alt="The round robin of four players on the scoreboard between two matches: next up Lea against Sam with a countdown, and the table with Alex first on 4 points" width="760">

<img src="images/en/tournament-groups.png" alt="32 players in eight groups of four on the scoreboard after two rounds: next up Tim against Alex in group A with a countdown, and the tables of groups A to H side by side, the first two places of every group marked as going on" width="760">

<img src="images/en/tournament-double.png" alt="A double elimination of 32 players on the scoreboard after the first round of each bracket: next up Alex against Tim in winners round 2 with a countdown, the winners' bracket up to the grand final, and below it the losers' bracket up to the losers' final, its first round played" width="760">

<img src="images/en/tournament-lobby.png" alt="The new game screen in tournament mode: X01 and the Cricket games, six players with their start scores, knockout with the match for third place, and the start button" width="760">

### Idle mode

When no game runs, or a match or training game is decided, and nobody throws or taps for `idle_after` seconds (3 minutes), the scoreboard shows these panels in turn, one every `idle_interval` seconds:

| Panel | Shows |
| --- | --- |
| `tournament` | The table or the bracket of the tournament being played or just finished |
| `leaderboard` | The five best players by 3-dart average, then by legs won, with their pictures |
| `records` | The personal bests of the board and the longest training streak |
| `today` | Today's darts towards the daily goal, the 3-dart average, highest visit and 180s of the session, and the streak |
| `last_match` | The last match of several players: the game, when it ended, and everybody's legs, or sets in a match of sets, and average, with a trophy for the winner, for both partners of the team that won a team match |
| `clock` | The time and the date |

Panels with nothing to show are skipped. A dart, a new game or a tap anywhere ends idle mode; a new game screen you opened by hand comes back as you left it, with the game and the players chosen. The screen changes only when the next panel is due or the clock's minute ends. On devices set to reduce motion, the panels change without fading.

<img src="images/en/scoreboard-idle.png" alt="Idle mode of the scoreboard: the leaderboard with Alex, Sam and Kim, their pictures, 3-dart averages and legs won" width="760">

### Options

| Option | Values | Default | Description |
| --- | --- | --- | --- |
| `device_id` | device | first board | The board to show |
| `title` | text | board name | Title between games; during a game the title names the game |
| `full_height` | boolean | `false` | Fill the height of the screen, for a view in panel mode |
| `show_visit` | boolean | `true` | Show the darts of the current visit |
| `show_status` | boolean | `true` | Show the board status |
| `fullscreen_button` | boolean | `true` | Show the [full-screen button](scoreboard.md#full-screen) at the top right, where the browser offers full screen: the scoreboard alone on the screen, without the bars of the browser and Home Assistant's header and sidebar |
| `keep_awake` | boolean | `true` | Keep the screen on while the scoreboard is in full screen, where the browser allows it: at an `https://` address, in the browser and in the Companion app alike |
| `caller` | boolean | `false` | Switch the caller on: the screen announces visits, what a player requires, busts and game shots |
| `call_scores` | boolean | `true` | Call the score of every visit (Cricket: its marks) |
| `call_checkouts` | boolean | `true` | Call what the next player requires when a checkout is possible |
| `call_results` | boolean | `true` | Call busts and game shots |
| `call_sounds` | boolean | `true` | Play a fanfare for a 180 |
| `call_darts` | `off`, `score`, `bed` | `off` | Call [every dart](scoreboard.md#for-blind-and-low-vision-players) as it lands: by its points, such as 60, or by its bed, such as Treble 20 |
| `call_route` | boolean | `false` | Call the route of a checkout, also after each dart that leaves another one |
| `call_target` | boolean | `false` | Call the next target of a training or party game, such as Double 16 |
| `caller_voice` | text | empty | A [voice pack](scoreboard.md#voice-packs): the name of a folder of `/media/homedarts/voices` with recorded calls, such as a pack of darts-caller; empty is the browser's voice |
| `lobby` | boolean | `true` | Offer the [new game screen](#new-game-screen) and the [plan of the day](games.md#training-plans) |
| `lobby_games` | list of games | every game | The games the new game screen offers, for example `["501", cricket, killer]`; the plan of the day is offered only if all its games are among them |
| `idle` | boolean | `true` | Switch [idle mode](#idle-mode) on |
| `idle_after` | seconds, 10–3600 | `180` | Time without darts and taps before idle mode starts |
| `idle_interval` | seconds, 3–120 | `10` | Time each panel shows |
| `idle_panels` | list of panels | every panel | The panels of idle mode, in this order: `tournament`, `leaderboard`, `records`, `today`, `last_match`, `clock` |
| `show_summary` | boolean | `true` | Show the [match summary](#match-summary) when an X01 or Cricket match ends |
| `summary_seconds` | 0–600 | `0` | How long the summary stays, in seconds; `0` keeps it until the next game starts |
| `celebrations` | boolean | `true` | Celebrate a 180, a visit of 100 or more, nine marks, a game shot and the match with confetti and a glow ([scoreboard](scoreboard.md#during-the-game)) |
| `corrections` | boolean | `true` | A tap on a dart of the visit [corrects it](#correcting-and-entering-darts); a tap on the last visit beside the darts takes it back while possible |
| `keypad` | boolean | `false` | Show the [keypad](#correcting-and-entering-darts) for darts entered by hand while *Practice manual entry* is on; on a [dartboard without Autodarts](without-autodarts.md) it shows unless `false` is set |
| `overlay` | `off`, `transparent`, `chroma` | `off` | The [stream overlay](scoreboard.md#stream-overlay) for a browser source of OBS: the scoreboard alone over the picture of a stream, see-through or on a key colour; on a dashboard it takes the whole window |
| `overlay_layout` | `lower_third`, `corner`, `full` | `lower_third` | Where the overlay lies in the picture: the players side by side along the bottom, a box in the top-left corner, or the whole picture |
| `overlay_color` | color | `#00FF00` | The key colour under a `chroma` overlay, which the chroma key filter of OBS takes out |
| `accent_color` | [color](#colors) | theme primary color | The player at the board, routes and the visit score |

In the editor, the four `call_…` options wait in the collapsed section *Caller options*; the new game screen, idle mode, correcting and entering darts, and the stream overlay have collapsed sections of their own. An overlay leaves out the status, the caller, the new game screen, idle mode, the keypad and the corrections, which nobody taps on a stream, and the match summary unless it takes the whole picture.

```yaml
type: custom:homedarts-scoreboard-card
full_height: true
caller: true
lobby_games: ["301", "501", cricket, killer]
idle_after: 300
idle_panels: [leaderboard, today, clock]
summary_seconds: 60
```

### Match summary

When an X01 or Cricket match of several players ends, the scoreboard and the live card sum it up: a column for every player, the winner's highlighted, with the result in the first row.

<img src="images/en/match-summary.png" alt="Scoreboard after Alex beat Sam 2 : 1 in 301: the match summary with legs, 3-dart average, first 9, checkout rate, highest checkout, 180s, 140+, 100+, best leg, darts at a double and darts of both players" width="760">

- **X01:** legs (and sets), 3-dart average, first-9 average, checkout rate with the legs checked out and the darts at a double, highest checkout, 180s, 140+ and 100+ visits, best leg in darts, darts at a double and all darts. Without double out, the checkout rate and the darts at a double are left out.
- **Cricket:** legs (and sets), marks per round, marks, best leg in darts and all darts.
- **How long:** until the first dart of the next game, or `summary_seconds` after the card first showed it. Then the players and the result come back, and on the scoreboard the [new game screen](#new-game-screen) opens a few seconds later. While the summary shows, the new game screen opens only with a tap, and [idle mode](#idle-mode) can take over after its idle time. `show_summary: false` switches the summary off. Between the matches of a [tournament](#tournaments), the table or the bracket follows after *Tournament summary*.

Party games keep their scores on screen. The numbers come from the `summary` attribute of the [practice remaining score](entities.md#practice-game); [how they are counted](how-it-works.md#match-summary).

## Doubles card

`custom:homedarts-doubles-card` shows the [doubles analysis](entities.md#doubles-analysis): every double hit on the double ring of the board, colored by its hit rate in the colors of the heatmap, from a dark blue violet (rarely hit) to a light yellow (about every second dart), where darts were aimed at it, and in the accent color by how often it was hit where not. The list below shows every double, the best rate first, with how often it was hit by any dart, the hits and darts aimed at it, and its hit rate; a legend below it shows the colors of the rates. The favorite double is filled. With `player`, it shows the doubles of one named player instead of everybody's; a name without a profile gets a hint to check its spelling.

<img src="images/en/doubles-card.png" alt="Doubles card: the double ring colored by hit rate from blue violet to yellow, and a list of the doubles with hits, darts and hit rate, the best first" width="760">

### Options

| Option | Values | Default | Description |
| --- | --- | --- | --- |
| `device_id` | device | first board | The board to show |
| `title` | text | *Doubles* | Card title |
| `player` | text | everybody | A player name, for that player's doubles. The editor lists the named players and takes any other name |
| `heatmap_palette` | `accessible`, `thermal` | `accessible` | The colors of the hit rates: `accessible` gets lighter with the rate, for every eye and in gray, like the heatmap; `thermal` is the former scale from red to green, at equal lightness |
| `accent_color` | [color](#colors) | theme primary color | Labels |

## Players card

`custom:homedarts-players-card` shows the [player profiles](entities.md#player-profiles): a tile for every named player with legs and matches won, the [rating](statistics.md#rating), 3-dart average, first 9, checkout rate, marks per round and the best marks per round of a Cricket leg, highest visit and checkout and the fewest darts per start score. Players [linked to a person](entities.md#link-a-player-to-a-person-homedartslink_player) show the person's picture. Below, the head-to-head records with a balance bar and the recent matches with their result and the winner in bold: the legs every player won, or the sets in a match of sets, such as *Cricket · Sets*. On request, an *Export* button downloads everything as a file; only administrators see it, as the export is an action for administrators.

**Manage profiles:** for administrators, the ⋮ button of a profile opens its menu: *Rename*, *Merge into …* and *Delete*. Each one asks first in a dialog and says what it does: *Rename* takes the new name, and says when another profile has it, as the two then become one; *Merge into …* offers the other players; *Delete* says what goes for good. A refusal, such as for a player of the tournament being played, shows its reason in the dialog. The arrows move through the menu, Escape and Tab close it, and the keyboard comes back to the ⋮ button after the dialog. What the actions keep and add up: [`homedarts.rename_player`](entities.md#rename-or-merge-players-homedartsrename_player) and [`homedarts.delete_player`](entities.md#delete-a-player-profile-homedartsdelete_player).

<img src="images/en/players-card.png" alt="Players card with the profiles of Alex, Sam and Kim with their pictures, their averages and personal bests, the head-to-head records of the players, and the recent matches" width="760">

- **Badges:** every player's [achievements](entities.md#achievements). An earned badge shows its tier in bronze, silver, gold or platinum, the next goal and how far the player has come; a locked badge is grayed out, with its progress where it can be counted. A player's gallery shows the badges earned and the three goals closest to being earned; *All 18 badges ▾* opens the rest, and *Show fewer* closes them again.
- **Trends:** for every player who practiced in the weeks shown, a tile per figure: 3-dart average, first 9, checkout rate, doubles rate and darts over the weeks, a line of the weekly values, and an arrow that compares the newer half of the weeks with the older half (↗ better, ↘ worse, → about the same). For the darts it compares the darts per week of the complete weeks, a week without practice with none, so the current week, which has only begun, and an odd number of weeks never tip it. Weeks without practice are a dashed stretch of the line; without both halves to compare, the tile shows no arrow.
- **Grouping:** where each player's darts land around the beds they aimed at most, in millimeters, with the change of the newer darts. [How the grouping is measured](how-it-works.md#grouping).

<img src="images/en/players-badges.png" alt="Badges of Alex: earned tiers in bronze, silver and gold, each with the next goal, the progress towards it and a progress bar" width="620">

<img src="images/en/players-trends.png" alt="Trends of Alex, Sam and Kim with the 3-dart average, first 9, checkout rate, doubles rate and darts per week, and the grouping of each player at the treble 20, the bull and the double 8" width="620">

### Options

| Option | Values | Default | Description |
| --- | --- | --- | --- |
| `device_id` | device | first board | The board to show |
| `title` | text | *Players* | Card title |
| `show_head_to_head` | boolean | `true` | Show the head-to-head records |
| `show_matches` | boolean | `true` | Show the recent matches |
| `show_badges` | boolean | `true` | Show the badges |
| `show_locked` | boolean | `true` | Show the next goals and, on demand, every locked badge; without them, players without a badge are left out |
| `show_trends` | boolean | `true` | Show the trends |
| `trend_weeks` | 4–12 | `12` | Weeks in the trends |
| `show_spread` | boolean | `true` | Show the groupings |
| `export` | boolean | `false` | Show an *Export* button. It exports the sessions, matches and profiles with [`homedarts.export`](entities.md#export-training-data-homedartsexport) to `homedarts/exports` in the media folder and downloads the file through Home Assistant with your login. Exports contain player names, so only administrators can export and download; for other users, such as the one of a wall tablet, the export fails. |
| `export_format` | `csv`, `json` | `csv` | Format of the export; CSV comes as a ZIP file with one table each |
| `accent_color` | [color](#colors) | theme primary color | Labels, the balance bars, progress and trend lines |

## Leaderboard card

`custom:homedarts-leaderboard-card` ranks the records of all named players, the [rating](statistics.md#rating) first. The leader of each record gets the crown, the next places follow.

<img src="images/en/leaderboard-card.png" alt="Leaderboard card with the period switch and the records highest rating, best average, highest checkout, most 180s, fewest darts in 501, best Cricket MPR, longest streak, most badges and most darts, each with the leader and two more places" width="760">

| Record | All time | Last 4 weeks, this week |
| --- | --- | --- |
| Best average | The player's 3-dart average in X01 | The average of the X01 legs that ended in the period |
| Highest checkout | The highest checkout with double out | The same, in the period |
| Most 180s | X01 visits that scored 180 | The same, in the period |
| Fewest darts, 501 | The fewest darts of a won 501 leg with double out | The same, in the period |
| Best Cricket MPR | The best marks per round of a won Cricket leg | The same, in the period |
| Longest streak | The longest run of days with darts | – |
| Most badges | Achievement tiers unlocked | Tiers unlocked in the period |
| Most darts | Darts thrown in practice and training games | The same, in the period |

A period covers whole weeks from Monday: *This week* the current week, *Last 4 weeks* the current week and the three before. Players share a place when their values are equal. The switch at the top changes the period until the card's configuration changes.

### Options

| Option | Values | Default | Description |
| --- | --- | --- | --- |
| `device_id` | device | first board | The board to show |
| `title` | text | *Leaderboard* | Card title |
| `period` | `all`, `month`, `week` | `all` | All time, the last four weeks or this week |
| `show_period` | boolean | `true` | Show the period switch |
| `limit` | 1–5 | `3` | Places shown per record |
| `accent_color` | [color](#colors) | theme primary color | Labels and the period switch |

```yaml
type: custom:homedarts-leaderboard-card
period: month
limit: 5
```

## Automatic dashboard

Instead of arranging the cards yourself, let the integration build a whole dashboard:

1. Go to **Settings → Dashboards → Add dashboard**.
2. Choose **HomeDarts**.

For every board, the dashboard gets up to six views in its tabs and the stream overlay, which update themselves when you add a board or enable entities:

| View | Contents |
| --- | --- |
| **Live** | The live card across the full width, so the board and the game stay in sight on a phone too |
| **Scoreboard** | The [scoreboard card](#scoreboard-card) across the whole screen, for a tablet or TV at the board |
| **Training** | The training card with the personal bests, the [doubles card](#doubles-card), the daily goal with darts today, the streak and the last personal best, darts per day for the last 30 days (from long-term statistics, which Home Assistant compiles hourly), the 3-dart average of the last 7 days, practice legs per day, the first 9 average, checkout rate and doubles rate of the practice game, and the training settings: starting sessions automatically and ending them after a pause |
| **Players** | The [players card](#players-card) and the [leaderboard](#leaderboard-card), once the first named player has a profile |
| **Game settings** | The practice game controls with teams and the Golf, Count-Up, Bermuda, Round the World and Gotcha options, the player names, their start scores and the [tournament](entities.md#tournaments) with its settings and buttons, for what the scoreboard's new game screen leaves out |
| **Board** | The board status card, the board settings, the Board Manager update and the share of darts the board corrected; a [dartboard without Autodarts](without-autodarts.md) has no such view |
| **Stream overlay** | The scoreboard as the [stream overlay](scoreboard.md#stream-overlay) of a browser source in OBS, see-through along the bottom of the picture; the tabs leave it out, and its address is the one of the dashboard with `/overlay` at its end |

| For playing | Players, settings and the board |
| --- | --- |
| <img src="images/en/dashboard-live.png" alt="The Live view of the automatic dashboard: the live card with the current visit, its three darts, the last visits, the training session and the board" width="380"><br>**Live** | <img src="images/en/dashboard-players.png" alt="The Players view: the profiles of five players with their averages and personal bests, and their head-to-head records" width="380"><br>**Players** |
| <img src="images/en/dashboard-scoreboard.png" alt="The Scoreboard view: the scoreboard across the screen with the current visit in large digits, the session figures and the button for a new game" width="380"><br>**Scoreboard** | <img src="images/en/dashboard-games.png" alt="The Game settings view: the controls of the practice game, from the game and the players to the bull-off, beside the player names" width="380"><br>**Game settings** |
| <img src="images/en/dashboard-training.png" alt="The Training view: the training card with the daily goal, the 3-dart average, the hit map and the statistics" width="380"><br>**Training** | <img src="images/en/dashboard-board.png" alt="The Board view: the board status card with the detection, the Board Manager, the connections and the cameras, beside the board settings, the software update and the correction rate" width="380"><br>**Board** |

The game settings also have *Bull-off by distance* among the practice rules and *Tournament summary duration* among the tournament settings. Most games need none of them: the scoreboard's [new game screen](#new-game-screen) sets the game, the players and the rules.

In YAML, the whole dashboard is one line; `device_id`, `title`, `scoreboard` and `overlay_view` are optional. `scoreboard` sets options of the scoreboard view's card: `caller`, `keypad`, `corrections`, `idle`, `lobby_games`, `idle_panels`, `fullscreen_button` and `keep_awake`, as described for the [scoreboard card](#scoreboard-card). `overlay_view` sets `overlay`, `overlay_layout` and `overlay_color` of the stream overlay. Options you leave out keep the card's defaults; the stream overlay is see-through.

```yaml
strategy:
  type: custom:homedarts
  device_id: 0123456789abcdef   # only this board
  title: Darts
  scoreboard:
    caller: true
    keypad: true
    lobby_games: ["501", cricket, killer]
    idle_panels: [leaderboard, clock]
  overlay_view:
    overlay_layout: corner
```

To choose the board, the title or the scoreboard's options later, open the dashboard's menu (⋮) → **Edit dashboard**. Home Assistant shows the dashboard's own editor, with the scoreboard's options in the section *Scoreboard view* and those of the stream overlay in *Stream overlay view*:

<img src="images/en/strategy-editor.png" alt="The editor of the automatic dashboard with the board and the title" width="760">

If the chosen board is removed from Home Assistant, the dashboard says so instead of showing empty views; choose another board or clear the choice to show every board. To customize the views themselves, choose **Take control** in the menu (⋮) of that editor. Home Assistant then turns the generated views into a normal dashboard that you can edit; it no longer gets the views of later releases, so prefer the dashboard's own settings where they are enough.

## Home Assistant Cast

[Home Assistant Cast](https://www.home-assistant.io/integrations/cast/#home-assistant-cast) shows a dashboard on a TV through a Chromecast, or on a Google Nest Hub, without a browser on the device. The cards and the automatic dashboard work there too: Cast loads the dashboard resources of Home Assistant, and the integration keeps its small module there, `homedarts-strategy.js`, in the folder of its version under `/homedarts/`, such as `/homedarts/1.16.0-0123abcd/homedarts-strategy.js`. That module brings the cards along as soon as the dashboard shows one. The integration brings it up to date with every start of Home Assistant and removes it with its last board; a resource for `homedarts-card.js` from an earlier release goes by itself. *Settings → Dashboards → ⋮ → Resources* lists the module when advanced mode is on in your user profile. Browsers stay as they are: they load it once, as a resource and as part of Home Assistant.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/cast-dark.png">
  <img src="images/en/cast-light.png" alt="How the cards reach a TV through Home Assistant Cast: a phone at cast.home-assistant.io or the action cast.show_lovelace_view casts a dashboard. The Chromecast opens the receiver of Home Assistant Cast, which signs in to Home Assistant over HTTPS and reads the dashboard and its resources. The integration keeps its small module there, at the address of its version, from every start of Home Assistant until its last board is deleted. The receiver loads the module from Home Assistant, which brings the cards along for the first card of the dashboard, and the TV shows the dashboard with the scoreboard." width="560">
</picture>

- **Resources in YAML:** if your configuration keeps the resources in YAML (`resource_mode: yaml`, or the older `mode: yaml`, under `lovelace:`), the integration can't add any. Add the lines yourself and restart Home Assistant:

  ```yaml
  lovelace:
    resource_mode: yaml
    resources:
      - url: /homedarts/homedarts-strategy.js
        type: module
  ```

  Without a version in the address, browsers ask on every load whether the module changed, so they never keep an old one. They load the module a second time at this address, so add the lines only if you cast. Lines for `homedarts-card.js` from an earlier release can go: they load all the cards on every dashboard.
- **After an update,** restart Home Assistant and cast the dashboard again.

The guide [scoreboard at the board](scoreboard.md#on-a-tv-with-home-assistant-cast) shows how to cast the scoreboard to the TV next to the board.

## Card editor

All options can be set in the visual editor. It is a form of Home Assistant, so it looks and works like the editors of the built-in cards:

- The device picker offers only the boards of HomeDarts.
- Switches show their default until you change them; lists name their default below the field.
- The caller options, the new game screen and idle mode of the scoreboard wait in collapsed sections; the doubles card offers the named players.
- An option the form cannot show, such as a mistyped `layout`, sends the editor to the code view with a message that names it.

<img src="images/en/card-editor.png" alt="The visual editor of the live card" width="760">

### Colors

`accent_color` and `highlight_color` use Home Assistant's color picker. Choose a theme color such as *Primary*, *Accent* or *Red*, which follows your theme, or type any CSS color, for example `#00e5ff`, `rgb(0 229 255)` or `var(--accent-color)`. A theme variable counts without a fallback only, as `var(--name)`. An empty field, or a value that is not a color, uses the default.

Text in the accent color is mixed with your theme's text color, and buttons filled with it are darkened, so both stay readable with the light primary colors of Home Assistant's default themes.

## Accessibility

The cards work with a keyboard, with a screen reader and without animations:

- **Keyboard:** every control is a button with a visible focus ring in the accent color. The board of the live card opens its details with Enter or Space, the statistics of the training card with their own button. The calibration buttons of the status card keep the focus while they ask for confirmation. On the new game screen and the pad of the scoreboard, a button keeps the focus after it is pressed, and the score view of the pad takes the focus itself where its keys come and go, so the digits and Enter of a keyboard always reach it; and a name being typed keeps its text and caret while the screen updates; Enter adds the name you typed. When the scores of a full-height scoreboard scroll, on a phone with the pad open, the keyboard reaches and scrolls them too.
- **Screen readers:** buttons without a text have a label, for example "Move Alex up" on the new game screen. The live board reads the darts of the visit, such as "Dartboard with the current visit: T20, S5, Bull", the chart of recent visits reads their scores, a dart of the scoreboard's visit its bed, points and what a tap does, Cricket marks read as words and Killer's hearts as lives. The player at the board is marked as the current one and the winner is named, not only colored. The status of the board and the winner of a match are announced when they change, and only then; the new game screen reads out a new stepper value and what holds the start back. The detection toggle of the status card is a switch, and the caller button and the options of the new game screen say whether they are on.
- **Reduced motion:** when the device asks for reduced motion, hit beds stop blinking and the latest dart stops pulsing; both stay highlighted. The panels of idle mode change without fading, and the places of a tournament bracket fill without sliding.
- **Color and contrast:** the cards take their colors from your theme, light or dark, and never rely on color alone: the board status comes with a text, the colors of the heatmap and of the doubles card get lighter with the hits, so they also read for color-blind players and in gray, with the numbers at both ends of the legend and the count of a bed on hover or tap, and the Cricket marks are symbols. Text in the accent color, gray text on tinted tiles and the colors of the doubles card are mixed for a contrast of at least 4.5:1; players who are out are faded by color, not transparency. In Windows' high contrast mode, pressed buttons get an outline. Choose an `accent_color` and a `highlight_color` with enough contrast to your theme, or use a high-contrast theme, which the cards follow.
- **Touch:** on a touch screen, the small buttons, such as *New game*, the caller, the period switch and *Export*, are at least 40 pixels high.
- **Hints on a tap:** what a mouse shows as a tooltip, a tap with a finger or a pen shows in a small bubble over the card, without moving anything: the darts of a last visit on the live card, a visit in the training chart and its average line, a trend arrow on the players card, the column names of a tournament's table, a double on the doubles card, a camera's dot on the status card and the hint of a setup. Another tap, Escape or five seconds close it. Controls such as the caller do what they do; their tooltip stays for the mouse.
- **Blind and low-vision players:** the caller of the scoreboard calls every dart, the route of a checkout and the next target of a training or party game, so the board can be played without seeing it ([for blind and low-vision players](scoreboard.md#for-blind-and-low-vision-players)).
- **Language:** the cards follow the language of your Home Assistant profile, and numbers, dates and times its formats.
- **Checked with every change:** [axe-core](https://github.com/dequelabs/axe-core) checks every card in a real browser against WCAG 2.1 at levels A and AA, on a laptop and a phone, in the light and the dark theme ([accessibility check](development.md#accessibility-check)).

## Tips

- **Wall tablet:** the live card with `layout: vertical` fills a portrait screen. The board scales with the card. For a landscape screen at the board, use the [scoreboard](#scoreboard-card).
- **Combine:** put the live card and the training card next to each other in a sections view with two columns.
- **Several boards:** add one card per board and choose the board in each card's editor.
- **Cached old version:** after an update, the card URL changes automatically. If a browser still shows an old card, reload the page. In the companion app, use *Settings → Companion app → Debugging → Reset frontend cache*.
- **Dashboards from version 1.x:** up to version 1.18, the cards were called `custom:autodarts-card` and so on, and the flat look was `board_style: autodarts`. The takeover renames them in the dashboards that Home Assistant keeps; in a dashboard in YAML, replace `custom:autodarts` with `custom:homedarts` and `board_style: autodarts` with `board_style: flat` ([what you change yourself](new-name.md#what-you-change-yourself)).
- **Download size:** all cards come in one module and their texts in a small file per language, compressed to about 175 KB together. A browser downloads it on its first visit and after an update and keeps it until the next one, so only the first load of a dashboard waits for it on a slow connection.
