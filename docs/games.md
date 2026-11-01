---
description: "X01, Cricket, party and training games in Home Assistant: matches, sets, teams and tournaments, against the bot or each other, with every rule explained."
---

# Games and rules

[← Documentation](README.md) · [Deutsch](games.de.md)

Your Autodarts board plays games in Home Assistant itself: X01 from 101 to 1001, six Cricket games, nine party games and eight training games, alone, as a match of up to four players, a party game of up to eight or a tournament of up to 32. Home Assistant counts every dart the board detects, recognizes busts, shows the checkout route and keeps the game through restarts. No Autodarts account, no cloud and no browser tab are needed.

<img src="images/en/lobby.webp" alt="Animation: on the tablet at the board, New game opens the game screen, Cricket is chosen, Sam joins Alex, the legs per set go up to three and the game starts on the scoreboard" width="760">

**On this page:** [All games at a glance](#all-games-at-a-glance) · [Start a game](#start-a-game) · [At the board](#at-the-board) · [Corrections and darts entered by hand](#corrections-and-darts-entered-by-hand) · [Matches, legs and sets](#matches-legs-and-sets) · [Match summary](#match-summary) · [Teams](#teams) · [Start scores (handicap)](#start-scores-handicap) · [Bull-off](#bull-off) · [Playing against the bot](#playing-against-the-bot) · [Tournaments](#tournaments) · [X01](#x01) · [Cricket games](#cricket-games) · [Party games](#party-games) · [Training games](#training-games) · [Statistics](#statistics)

## All games at a glance

| Game | Players | Goal |
| --- | :---: | --- |
| [**X01**](#x01): 101, 301, 501, 701, 901, 1001 | 1–4, or two teams of two | Count down to exactly zero, by default on a double |
| [**Cricket**](#cricket) | 1–4, or two teams of two | Close 20 to 15 and the bull, and score on the numbers the others still have open |
| [**Cut-Throat Cricket**](#cut-throat-cricket) | 1–4, or two teams of two | Close everything with the fewest points: your points go to the others |
| [**Tactics**](#tactics) | 1–4, or two teams of two | Cricket on 20 to 10 and the bull |
| [**Wild Mouse**](#wild-mouse) | 1–4, or two teams of two | Cricket plus three doubles, three triples and three darts in one bed |
| [**Random Cricket**](#random-cricket) | 1–4, or two teams of two | Cricket on six numbers of 1 to 20 and the bull, drawn anew for every leg |
| [**Hidden Cricket**](#hidden-cricket) | 1–4, or two teams of two | Random Cricket whose numbers show only once a dart finds them |
| [**Shanghai**](#shanghai) | 1–8 | Score on the numbers 1 to 7; single, double and triple in one visit win at once |
| [**Halve-It**](#halve-it) | 1–8 | Hit the target of the round, or your points are halved |
| [**Killer**](#killer) | 2–8 | Win your number, become a killer and take the others' lives |
| [**Golf**](#golf) | 1–8 | Nine or 18 holes in the fewest strokes |
| [**Baseball**](#baseball) | 1–8 | Score the most runs in nine innings |
| [**Count-Up**](#count-up) | 1–8 | Score the most points in 1 to 20 rounds |
| [**Bermuda**](#bermuda) | 1–8 | Thirteen targets as on play.autodarts.io; a visit without a hit halves your points |
| [**Round the World**](#round-the-world) | 1–8 | 1 to 20 in an order of your choice, then the bull; the first to hit the bull wins |
| [**Gotcha**](#gotcha) | 1–8 | Count up to the target score, and send others back to 0 by reaching their score |
| [**Around the Clock**](#around-the-clock) | 1 | 1 to 20 and the bull in the fewest darts |
| [**Doubles training**](#doubles-training) | 1 | D1 to D20 and the bullseye in the fewest darts |
| [**Checkout training**](#checkout-training) | 1 | Random finishes from 2 to 170 within three visits |
| [**Bob's 27**](#bobs-27) | 1 | One visit at every double, without dropping to zero |
| [**121 checkout**](#121-checkout) | 1 | Check out 121 in nine darts, and climb |
| [**Catch 40**](#catch-40) | 1 | Check out 61 to 100, the faster the more points |
| [**JDC Challenge**](#jdc-challenge) | 1 | The 57-dart routine of the Junior Darts Corporation |
| [**Singles training**](#singles-training) | 1 | One visit at each number, points per mark |
| [**Tournament**](#tournaments) | 3–32 | A round robin, a knockout, a double elimination or groups with a knockout, of X01 or Cricket matches, at one board or on several at once |

## Start a game

There are four ways to start a game. All of them end in the same place: the *Practice game* of your board, which the [live card](cards.md#live-card), the [scoreboard](scoreboard.md) and the [board events](entities.md#board-events) follow.

1. **On the screen at the board.** Tap **New game** on the [scoreboard](scoreboard.md#choose-the-next-game), choose the game, the players and the format, and tap **Start**. The screen also opens by itself a few seconds after a game ends, ready for a rematch. **Tournament** on the same screen starts a [tournament](#tournaments).
2. **On the dashboard.** The *Live* view of the [automatic dashboard](cards.md#automatic-dashboard) has the practice controls: *Practice game*, the number of players, their names and start scores, legs, sets and the rules. Choosing a game starts it.
3. **In an automation or script** with the action [`homedarts.start_game`](entities.md#start-a-practice-game-homedartsstart_game), which sets everything in one call:

   ```yaml
   action: homedarts.start_game
   data:
     game: "501"
     players: [Alex, Sam]
     legs: 3
   ```

4. **By voice** with Assist: "Start Cricket for Alex and Sam". The [automation guide](automations.md#start-a-game-by-voice) has the automation.

To end a game, choose *Off* in *Practice game*, or tap **End game** on the new game screen. *New practice leg* starts the leg again, and what that leg added to the match averages and the match summary counts no more; *New practice match* starts the match from zero legs and sets.

Player names cannot contain curly brackets, the percent sign, the number sign (#) or control characters, because Home Assistant would read them as a template where a name goes into a message or a file name. The name entities and the actions refuse such a name.

## At the board

- **A visit ends when you pull the darts.** The practice game books it with the takeout. Darts that are already in the board when a game starts do not count.
- **Three darts per visit.** A fourth dart before the takeout does not count. Darts the board does not detect, such as bounce-outs, count as not thrown.
- **Corrections count.** When you correct a dart in Autodarts or on the scoreboard before the takeout, the game follows the correction; see [corrections and darts entered by hand](#corrections-and-darts-entered-by-hand).
- **The turn passes with the takeout,** also after a bust. The live card and the scoreboard outline the player at the board.
- **What the cards show:** the remaining score and the checkout route, the Cricket chalkboard, the round and the target of a party game or the target of a training game. The board outlines the bed to aim at. [Live card](cards.md#live-card), [scoreboard](scoreboard.md).
- **Events for your automations:** `bust`, `leg_won`, `match_won`, `turn_changed`, `bull_off_won`, `drill_finished`, `checkout_attempt`, `achievement_unlocked` and the tournament events arrive the moment they happen, for callers and [light shows](automations.md#light-show).
- **Training sessions keep counting.** The practice game and the [training session](statistics.md#training-sessions) are independent; a dart counts in both.

## Corrections and darts entered by hand

<img src="images/en/correct-dart.webp" alt="Animation: the scoreboard shows T20, S20 and T20 for 140; a tap on the second dart opens the pad, a tap on T and on 20 corrects it, and the visit reads 180" width="760">

A dart the board read wrong, a dart it missed, or the visits of a player without cameras: Home Assistant puts the visit right before it counts.

- **Correct a dart:** tap the dart on the [scoreboard](scoreboard.md#correct-and-enter-darts) and choose the right bed, or use [`homedarts.correct_dart`](entities.md#correct-a-dart-homedartscorrect_dart). The remaining score, a bust or a win, the Cricket marks and the statistics follow at once. The board keeps its own reading; when it corrects the dart itself later, its reading counts again. Tap the spot on the pad's board, and the dart also counts where it really is for the dart positions.
- **Enter a dart:** with *Practice manual entry* on, the scoreboard's keypad or [`homedarts.throw_dart`](entities.md#enter-a-dart-homedartsthrow_dart) adds a dart as if the board had detected it. This works with the detection stopped too, so a player without cameras can play along.
- **Next player:** ends the visit without pulling the darts; the darts in the board count for nobody until they are pulled. Without darts, the player at the board passes in X01, the Cricket and the party games; in a party game the pass counts as a visit of three misses, so Halve-It halves the points and Golf scores 5 strokes, and a pass that ends the last round counts the leg and the match like a visit with darts. A training game, a bull-off and Killer while the numbers are chosen do not pass.
- **Undo the last visit:** when a wrong reading is noticed after the takeout, a tap on the last visit beside the darts of the scoreboard or [`homedarts.undo_visit`](entities.md#undo-a-visit-homedartsundo_visit) takes the visit back, also after a won leg: its darts become the current visit again, to correct them, and *Next player* ends it. This works while no dart is in the board and the game has not changed since, but not after a visit that decided a tournament match. The statistics, the personal bests, the players' progress with their achievements, the weekly report and the training calendar go back with the visit, so it counts once when it is booked again.
- **Marked:** darts entered or corrected in Home Assistant carry `manual`, so automations can tell them apart. [The exact rules](how-it-works.md#corrections-and-darts-entered-by-hand).

## Matches, legs and sets

<img src="images/en/scoreboard.webp" alt="Animation: the scoreboard during a 501 match. The turn passes between Alex and Sam after every visit, and Alex checks out 141 with T20 T19 D12 to win the match" width="760">

- **Players:** set *Practice players* to 2, 3 or 4, or choose them on the new game screen. After every visit the next player throws; a bust passes the turn too.
- **Legs and sets:** the first player to win *Practice legs per set* legs wins the set; there is no tie-break and no need for two clear legs. The first player to win *Practice sets to win* sets wins the match. With one set to win, a match is simply the first to that many legs. With one player, legs just count up.
- **Throwing first:** as in PDC set play, the first throw passes to the next player every leg within a set, and every new set starts with the player after the one who started the previous set. With two players, player 1 starts sets 1, 3 and 5 and player 2 sets 2 and 4. The first leg of a match starts with player 1, or with the winner of the [bull-off](#bull-off).
- **Result:** the result stays on the cards until the next dart, which starts a new match. The winner keeps the legs of the deciding set, so a first-to-3 match ends 3–2 on the scoreboard. `match_won`, the match history and the [player profiles](statistics.md#player-profiles) keep every player's legs and sets; `match_legs` counts the legs of the whole match.
- **Averages:** each player's average and marks per round cover the whole match.

## Match summary

<img src="images/en/match-summary.png" alt="Scoreboard after Alex beat Sam 2 : 1 in 301: the match summary with legs, 3-dart average, first 9, checkout rate, highest checkout, 180s, 140+, 100+, best leg, darts at a double and darts of both players" width="760">

When an X01 or Cricket match of several players ends, the scoreboard and the live card sum it up: a column for every player, the winner's highlighted, with the result in the first row. The winner's banner names the result too, for example *Alex wins the match 3 : 2!*

- **X01:** legs and sets, 3-dart and first-9 average, the checkout rate with the legs checked out and the darts at a double, the highest checkout, 180s, 140+ and 100+ visits, the best leg in darts and all darts. Without double out, the checkout rate and the darts at a double are left out.
- **Cricket:** legs and sets, marks per round, marks, the best leg in darts and all darts.
- **Party games** keep their scores on the screen.
- **How long:** until the first dart of the next game, or for `summary_seconds` of the [card](cards.md#match-summary). `match_won` carries the numbers for your automations, for example to [send them to your phone](automations.md#send-the-summary-of-a-match). [How they are counted](how-it-works.md#match-summary).

## Teams

<img src="images/en/scoreboard-teams.png" alt="Scoreboard of a 501 team match: Alex and Kim with 45 left against Sam and Lea with 216, Sam at the board in bold with his average" width="760">

- **Two teams of two:** turn on *Practice teams* (on the new game screen: *Teams*) and play X01 or a Cricket game with four players. Players 1 and 3 play against players 2 and 4. The throwing order is the seat order, so the teams alternate: A1, B1, A2, B2. With fewer or more than four players, and in party and training games, everybody plays alone.
- **One score per team:** partners share the remaining score, the opening double with double in, and in the Cricket games the marks and points. A team plays from the start score of its first player.
- **Throwing first** passes to the next seat every leg, as in any match of four, so the teams take turns.
- **Winning:** both partners win the leg and the match. The scoreboard names the winning team, and `leg_won` and `match_won` add `team` and `team_name`, for example *Alex & Kim*. A team without a name for both players, and a team with the bot, has no `team_name`.
- **Statistics per person:** the first nine, the checkout rate, the averages and the marks per round stay with the player who threw the darts. The player profiles count the leg and the match for both partners, and each of them beats both opponents in the head-to-head records; partners play no head-to-head. A team leg sets no fewest-darts and no marks-per-round personal best; a checkout still counts for the player who threw it.

## Start scores (handicap)

<img src="images/en/scoreboard-handicap.png" alt="Scoreboard of a 501 match with start scores: Alex from 501 with 361 left, Sam from 301 with 241 left and at the board" width="760">

- For a fair match between players of different strength, every player can start X01 from a score of their own, from 2 to 1001: set *Practice start score player N*, use − and + beside the player on the new game screen, or pass `start_scores` to [`homedarts.start_game`](entities.md#start-a-practice-game-homedartsstart_game).
- `0` plays the game's start score. All other rules stay the same; the average counts from the player's own start, and `leg_won` names it in `start`.
- The scoreboard and the live card show every start score of its own beside the name.
- A leg counts for the fewest-darts personal best of the score it really started from: a leg from 301 for `fewest_darts_301`, a leg from 401 for none, because 401 is no X01 game.
- A match with different start scores moves no [rating](statistics.md#rating), because the handicap evens out what a win says about strength.

### Fair start

<img src="images/en/lobby-fair.png" alt="The new game screen with 501 chosen and Fair start on: Alex keeps 501, and Sam starts from the share of it that his average is worth, with − and + to change it" width="760">

Nobody has to guess what is fair: **Fair start** on the [new game screen](scoreboard.md#choose-the-next-game), or `fair_start: true` in [`homedarts.start_game`](entities.md#start-a-practice-game-homedartsstart_game), works the start scores out from the 3-dart averages.

- **The strongest player keeps the game's score.** Everybody else starts from their share of it, by their average of the last 30 X01 legs: half the average, half the score. The score is rounded to 10 and is never below 101.
- **For example,** in 501 Alex averages 60 and Sam 30: Alex starts from 501 and Sam from 250.
- **A player without X01 legs** keeps the game's score, as there is nothing to go by, and the screen says so. A player from before this version, who has played no leg since, counts by their lifetime average.
- **The bot** counts by its level, which is its average, and can be the strongest player, too. On the new game screen, its row shows its start score, which changes with its level.
- **A team** plays from one score, by the average of both partners. The bot counts as a partner.
- **Change them as you like:** the screen shows the scores, and − and + still change them. A new player, another game or another order works them out again. Turned off, everybody plays the game's score again.

## Bull-off

<img src="images/en/bull-off.webp" alt="Animation: the bull-off on the scoreboard. Alex hits the outer bull 15.7 millimeters from the center, Sam the bullseye 4 millimeters from it and leads, and the 501 match starts with Sam at the board" width="760">

- With *Practice bull-off* (on the new game screen: *Bull-off*) and two or more players, a match starts with one dart per player at the bull, in seat order. Only the first dart of each visit counts. The scoreboard shows the bed of every dart and its distance from the center, marks the dart that leads, and says *Tie – throw again* when a tie throws again.
- As the WDF and PDC rules want, the bullseye beats the outer bull, which beats every other bed. Two or more darts in the same bull bed tie: those players throw again, the last of them first.
- Outside the bull, the dart closer to the center wins. The distance comes from the position the board reports, measured against the outer edge of the double ring (170 mm). Any bed of the board beats a dart off the board; when all darts miss the board, everybody throws again.
- With *Practice bull-off by distance*, the measured distance also decides between two darts in the same bull bed; darts equally close to 0.1 mm throw again.
- A dart without a position, such as one entered by hand, cannot be measured. Outside the bull, a measured dart beats it, and two darts without a position throw again. In the same bull bed, a dart without a position ties, also by distance, and those players throw again.
- The dart at the bull scores nothing in the game: the remaining score, the marks and the averages start with the first visit of the match.
- The bull-off only decides who starts. With three or four players, the others follow in seat order. `bull_off_won` announces the winner, for example for the [practice caller](automations.md#practice-caller).

## Playing against the bot

<img src="images/en/bot-match.webp" alt="Animation: a 301 match against the bot on the scoreboard. Alex throws and pulls the darts, the bot's three darts land one by one, and Alex is at the board again" width="760">

Nobody to play with? X01 and the Cricket games can be played against the bot, a computer player of the strength you choose.

- **A bot at your level:** once a player has X01 legs, the bot's row on the new game screen offers *At my level*, which sets the bot to the player's average of the last 30 legs, in its steps of 10. With several players, it goes by what they average.
- **Seat the bot:** tap **+ Bot** on the [new game screen](scoreboard.md#choose-the-next-game), set *Practice bot level*, or start a game with `bot_level`. The level is the 3-dart average the bot plays, from 20 for a beginner to 120, above any professional's season average. `0` plays without the bot. There is no level from 1 to 19: in *Practice bot level*, a step up from 0 seats the bot at 20, and a step down from 20 sends it home.
- **In the Cricket games,** the level plays the marks per round of a player with that average, about a 24th of it: 2.5 at level 60, 3.3 at 80, 4.2 at 100 and 5 at 120.
- **Its seat:** after the players. With the bot, up to three players play, also as the fourth player of two teams; such a team has no team name. Choosing X01 or a Cricket game for four players while a bot level is set asks you to make room first.
- **Changing the level** during a match lets the bot play the new level from its next dart. Seating the bot, or sending it home with `0`, starts a new match; in party and training games, where it does not play, a new level changes nothing until the next X01 or Cricket game.
- **Its turn:** when your darts are pulled, the bot throws its three darts one by one, with the pause of *Practice bot delay* (2 seconds) before each, and they appear on the cards where they landed. Throw while it is at the board, and it throws the rest of its visit at once.
- **How it plays:** like a player: at the triple 20 to score, along the checkout route to finish and at a [setup](#x01) where no route exists; in Cricket it closes the numbers and scores while it is behind, and in Hidden Cricket it searches for the numbers that do not show yet. With double in, it opens with a double that wins or leaves a finish for its darts, otherwise with the double 20, or with a smaller double where the double 20 would bust; with master in, it opens with the triple 20 where it does not bust. It plays the out mode and the bull mode of the leg. Without double out and without a finish, it takes the biggest bed that does not bust. It always aims at the usual checkout routes, also with *Practice personal checkout routes*, and the cards show those routes for its turn. Its darts scatter as much as those of a player of its level. [How the bot plays](how-it-works.md#bot).
- **What counts:** the bot's darts count for nobody's statistics, personal bests or achievements; the result of the match counts in your player profile. Party games, training games and tournaments are played without the bot; after a tournament, the bot comes back with the other practice settings.

<img src="images/en/scoreboard-bot.png" alt="Scoreboard of a 301 match against the bot: Alex, who plays from a start score of 169, has 169 left, and instead of a checkout the card shows T20 T20 S17 leaves 32; the bot's tile reads Bot Level 80" width="760">

## Tournaments

<img src="images/en/tournament-bracket.webp" alt="Animation: the knockout bracket of five players on the scoreboard. Lea beats Max in the quarter-final and slides into the semi-final; Alex beats Lea and goes into the final, Lea into the match for third place; Kim beats Sam, Lea takes third place and Alex wins the final" width="760">

A tournament for three to 32 named players, at one board one match at a time, or on [several boards at once](#a-tournament-on-several-boards), in one of four formats:

- **Round robin**, three to eight players: everyone plays everyone once, and a table ranks the players.
- **Knockout**, three to 32 players: the winners go on through a bracket until the final.
- **Double elimination**, three to 32 players: nobody is out before losing two matches. A loser of the winners' bracket gets a second chance in the losers' bracket, and the winners of both brackets meet in the grand final.
- **Groups and knockout**, six to 32 players: everyone plays everyone in their group, and the best of every group go on into a knockout, as at a club championship.

Every match is an X01 match, with start scores for a handicap if you like, or a Cricket game, with the legs, sets and rules of the tournament. The results go into the [player profiles](statistics.md#player-profiles) and the head-to-head records like every match.

1. **Start:** tap **New game** on the scoreboard, then **Tournament**. Choose the players, the format, with groups also the number of groups and how many of each go on, the game, the legs and sets and the rules, and tap **Start tournament**. Or start it from an automation:

   ```yaml
   action: homedarts.start_tournament
   data:
     players: [Alex, Sam, Kim, Lea]
     format: round_robin
     game: "501"
     legs: 2
   ```

   Groups of four for 16 players, of which the first two go on into a knockout of eight:

   ```yaml
   action: homedarts.start_tournament
   data:
     players: [Alex, Sam, Kim, Lea, Max, Tom, Ida, Ben, Zoe, Eli, Noa, Mia, Leo, Ava, Jon, Uma]
     format: groups_knockout
     groups: 4
     advance: 2
     game: "501"
   ```

2. **Play:** the first match starts at once, and the title line of the scoreboard names the round, the group and the match. When a match is decided and the darts are pulled, the scoreboard shows its summary, then the table, the groups or the brackets with the next match and a countdown. The next match starts by itself; **Start now** skips the wait.
3. **Winner:** after the last match, a banner names the winner, and the table or the bracket stays until a new match begins. `tournament_finished` can start the [light show](automations.md#light-show) or [announce the results](automations.md#announce-the-results-of-a-tournament).
4. **Afterwards:** the practice game goes back to the players, names, start scores, legs, sets, rules and bot level it had before the tournament, with the first dart of the next match or the first change of a practice setting. After *Stop tournament*, a match being played is played to its end first. A new tournament starts only when none is being played: stop the one being played first.

**Tournament** on the new game screen of the scoreboard sets up the players, the game, the format and the rules:

<img src="images/en/tournament-lobby.png" alt="The new game screen in tournament mode: X01 and the Cricket games, six players with their start scores, knockout with the match for third place, and the start button" width="560">

Between two matches, the scoreboard shows the next match with its countdown, and the table of a round robin:

<img src="images/en/tournament-table.png" alt="The round robin of four players on the scoreboard between two matches: next up Lea against Sam with a countdown, and the table with Alex first on 4 points" width="760">

With groups, it shows the tables of the groups side by side, with the places that go on marked, and in a double elimination the losers' bracket below the winners' bracket. Both from the demo, with 32 players:

<img src="images/en/tournament-groups.png" alt="32 players in eight groups of four on the scoreboard after two rounds: next up Tim against Alex in group A with a countdown, and the tables of groups A to H side by side, the first two places of every group marked as going on" width="760">

<img src="images/en/tournament-double.png" alt="A double elimination of 32 players on the scoreboard after the first round of each bracket: next up Alex against Tim in winners round 2 with a countdown, the winners' bracket up to the grand final, and below it the losers' bracket up to the losers' final, its first round played" width="760">

The [entity reference](entities.md#tournaments) lists the tournament's settings, buttons and actions, and the [scoreboard guide](scoreboard.md#tournaments) what the screen shows.

### A tournament on several boards

A club evening with two boards or more plays one tournament on all of them: every board plays a match of its own, and the table or the bracket takes the results of every board. Each board may be an Autodarts board or a [dartboard without Autodarts](without-autodarts.md), whose darts are entered on the keypad. Start the tournament on one board, which then holds it, and name the other boards in `boards`: in **Developer tools → Actions** with the device picker, or in an automation by their device or entry:

```yaml
action: homedarts.start_tournament
data:
  config_entry_id: 01JA0GARAGEBOARD0000000000 # the board that holds the tournament
  boards: [01JA0CELLARBOARD0000000000] # the other boards
  players: [Alex, Sam, Kim, Lea, Max, Tom]
  format: round_robin
  game: "501"
```

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/tournament-boards-dark.png">
  <img src="images/en/tournament-boards-light.png" alt="How a tournament runs on several boards: The tournament starts on one board, with the other boards in boards. Every board takes a match at once if one is ready whose players play at no other board. When a match is decided and its darts are pulled, its result goes into the table or the bracket, which the board holding the tournament keeps for all boards. After the last match, every board goes back to its own games. Otherwise the board shows the summary and the pause, which the players of its next match get too. Then the board takes the next match whose players are known and free, as soon as it is clear; a board without such a match waits for a result of another board." width="560">
</picture>

- **Side by side:** every board starts a match at once. After its pause, a board takes the next match whose players are known and play at no other board, as soon as no darts are left on it: the board that is free first plays next. A board without such a match waits until a result of another board brings one, for example the final after both semi-finals.
- **A pause for the players too:** the players of a match get the summary and the pause after their last match, wherever they played it, so nobody walks from one board straight into the next match. *Next tournament match* on a board starts its match at once.
- **Every scoreboard:** the scoreboard of each board shows its own match with its round and number, and between the matches the table or the bracket of the whole tournament. Above it, a box for every board says what it plays or when its next match starts, the board's own box marked, and below them the expected end of the tournament.
- **Expected end:** the matches still to play, one after the other on the board that is free first, each as long as the averages of its players make it: their average in the tournament, else that of their player profile at its start, else 40 points a visit. A visit takes 30 seconds until the matches played show the real pace. *Tournament* has the time in its attribute `ends_at`, at one board too.
- **The board that holds it:** its *Tournament* sensor, its settings and its events stand for the whole tournament: `tournament_match_finished` of every board arrives there, with the `board` that played the match. The *Tournament* sensor of another board shows the same tournament, with its own match first. *Stop tournament* on any of the boards stops it on all of them; afterwards, every board goes back to its own practice settings. A match counts for the player profiles of the board it was played on.
- **Restarts:** the boards find each other again after a restart of Home Assistant or the reload of a board, and every board keeps its match. A board that is switched off keeps its match until it is back; a board deleted from Home Assistant gives its match back for another board at once, and when the deleted board held the tournament, the other boards go back to their practice settings. A board that waits for a match another board still plays says so on the scoreboard, without *Start now*. A board that plays in a tournament starts no other one, and a tournament plays on up to eight boards.

### Tournament rules

- **Players:** three to eight players in a round robin, three to 32 in a knockout and a double elimination, six to 32 with groups, each with a name. *Tournament players* shows as many of them as its 255 characters hold, then `…`; its attribute `players` lists them all, and a list written back with the `…` keeps the names it stands for. A name is the same player regardless of upper and lower case, as in the [player profiles](entities.md#player-profiles). A player of the tournament being played cannot be deleted; a deleted player leaves the list for the next tournament.
- **Draw:** the order of the names, or a random order with *Tournament random draw* or a `seed`. The same seed always draws the same order; a random draw without a seed picks one and shows it in the `seed` attribute of *Tournament*.
- **Round robin:** everyone plays everyone once, in rounds by the circle method: three or four players play 3 rounds, five or six play 5, seven or eight play 7. With an odd number of players, one player sits out every round. Within a round, a player of the round's last match opens the next round only when no other match can, and the first throw goes to the player of a match who had it less often.
- **Points:** a won match is worth 2 points, as in the Premier League, a lost one none. A match cannot end in a draw.
- **Tie-breakers:** players level on points are ranked by
  1. the points they won in the matches among themselves,
  2. the leg difference: legs won minus legs lost over all their matches, every leg of a match with sets included,
  3. the 3-dart average over all their matches (Cricket: the marks per round),
  4. the order of the draw.

  So of two players level on points, the one who won their match goes first; of three players who beat each other in turn, the leg difference decides.
- **Knockout:** a bracket of 4, 8, 16 or 32 places, the fewest that hold the players: 4 places for three or four players, 8 for five to eight, 16 for nine to 16 and 32 for 17 to 32. The first player of the draw is seed 1, the second seed 2, and so on, placed as in professional draws: seed 1 meets the last seed first, seeds 1 and 2 can meet in the final at the earliest, and seeds 1 to 4 not before the semi-finals. Places the players do not fill are byes for the top seeds, who go straight into the next round, so byes fall in the first round only. The rounds are the round of 32, the round of 16, the quarter-finals, the semi-finals and the final.
- **Double elimination:** the winners' bracket is a knockout as above. A player who loses there drops into the losers' bracket; a player who loses there is out. The rounds of the losers' bracket take turns: its players among themselves, then against the players who just dropped from the winners' bracket, crossed every other round, so that two players meet again as late as they can. The winner of the winners' final and the winner of the losers' final meet in the grand final. If the winner of the losers' bracket wins it, both have lost once, and a deciding final follows. So every player but the champion loses exactly two matches: three players play 4 or 5 matches, 32 play 62 or 63. Byes for the top seeds fall in the first round of the winners' bracket and in the first two rounds of the losers' bracket, where nobody drops in. Third is the loser of the losers' final.
- **Groups and knockout:** two to eight groups, A to H, of three to eight players each, as *Tournament groups* or `groups` sets them; with 0, the default, groups of about four players, for example eight groups of four for 32 players. The draw goes into the groups like a snake: seed 1 into group A, seed 2 into group B, and so on, and from the last group back, so that every group gets one of the top seeds and no group has more than one player more than another. Every group plays a round robin and ranks its players by its rules above, and all groups play round by round: the first round of every group, then the second. The best of every group go on, as many as *Tournament qualifiers per group* or `advance` sets, one to four, two by default, always fewer than the smallest group has. In the knockout, the group winners are the top seeds in the order of the groups, then the second places, and so on, and every player goes where they meet the players of their own group as late as the bracket allows, never in its first round. The knockout begins when the last match of the groups is decided.
- **Third place:** with *Tournament third-place match* and four players or more in the knockout, also in the knockout after the groups, the losers of the semi-finals play for third place, before the final. Without it, a knockout has no third place. A double elimination has its third place without it.
- **Order of play:** one match at a time, round by round. A knockout plays the matches of a round from the top of the bracket down, and the match for third place before the final. A double elimination plays a round of the winners' bracket, then the rounds of the losers' bracket it fills: in a crossed round, who dropped first plays first. The grand finals come last.
- **Matches:** every match is a [match](#matches-legs-and-sets) of two players, with the legs per set, sets to win, double out, double in and bull-off of the tournament. Rules the tournament does not set come from the practice game as you set them, also an out mode that waits for the next leg. A tournament plays straight or double in and out, with master coming as double, the bull 25/50 and no round limit; after it, the practice game has its own rules again. In X01, a player with a start score of their own starts every leg of the tournament from it, a handicap; the other one from the game's. The first named player throws first, unless the bull-off decides.
- **Changed matches:** a match whose legs, sets, start scores or rules are changed while it is played is no tournament match any more, and its result does not count; *Next tournament match* sets the tournament match up again. A setting changed during the pause starts the match of the last two players anew: until its first dart, it makes way for the next match when the pause is over.
- **Averages:** a player's average counts the points and darts of all their tournament matches; the darts of a bust visit count, its points do not.
- **Winner:** the winner of the final or of the last grand final, or the player at the top of the table after the last match. After it, *Next tournament match* says that the tournament is over: stop it, or start a new one.

How a player goes through a double elimination:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/double-elimination-dark.png">
  <img src="images/en/double-elimination-light.png" alt="How a double elimination runs: every player starts in the winners' bracket. A player who wins there goes on to the next round, up to the winners' final, whose winner plays the grand final. A player who loses a match of the winners' bracket drops into the losers' bracket, and one who loses there is out after the second defeat. The winner of the losers' final plays the grand final. If the winner of the winners' bracket wins it, they are the champion; if the winner of the losers' bracket wins it, both have lost once, and the deciding final makes the champion." width="560">
</picture>

## X01

<img src="images/en/practice-checkout.webp" alt="Animation: a 141 checkout in a 501 leg. After each dart the remaining score, the route and the outlined bed change: T20 T19 D12, then game shot and a new leg" width="620">

- **Counting down:** the score starts at 101, 301, 501, 701, 901 or 1001, and every dart subtracts its score.
- **In and out:** as on play.autodarts.io, *Practice in mode* and *Practice out mode* set how a leg opens and ends: **Straight** with any dart, **Double** with a double or the bullseye, **Master** with a double, a triple or the bullseye. A leg starts straight and ends on a double unless you choose otherwise, on the new game screen of the scoreboard too.
- **Double out** (the default): the last dart of a leg must hit a double or the bullseye. **Master out** takes a triple as well: the route finishes on one only where it saves a dart, such as `T20` for 60, and keeps the checkout chart's double otherwise. **Straight out** finishes on any bed.
- **Double in and master in** (off by default): a player's score starts with the first double or bullseye of the leg, with master in also a triple; darts before it score nothing. The cards ask for it and outline the double ring. A bust takes the opening dart back. With double or master in and out, a start score of 3 cannot be won, since D1 leaves 1 and T1 ends on a triple; only master in and master out win it, with T1. Such a start score is refused.
- **Changing the out mode:** a leg keeps the rules it started with. Changing the out mode during a leg, once a dart counted, applies from the next leg; before the first dart of a leg, between matches and in the other games it applies at once. So no leg becomes unwinnable: a player who stands on 1 in a leg without double out can still finish it with a single 1 when double out comes on. Another in mode, bull mode or round limit starts a new match.
- **Bull mode:** with *Practice bull mode* 25/50, the outer bull scores 25 and the bullseye 50; with 50/50, the whole bull scores 50. Only the bullseye is a double, so with double out 50 still finishes on the bullseye, but on the way the route aims at the bull for 50: `BULL D20` for 90, where 25/50 plays `T18 D18`.
- **Round limit:** with *Practice max rounds*, from 1 to 50, a leg ends after its last round: when every player has thrown that many visits without a checkout, the lowest score wins the leg, and the callers name the winner. Partners of a team share their score. On a tie for the lowest score the leg goes on, round by round, until one player or team alone has it or somebody checks out. The scoreboard shows the round, such as *Round 3/10*, and *Play-off* for the extra rounds. `0`, the default, plays without a limit.
- **Bust:** a dart that goes below zero, leaves 1 with double or master out, or reaches 0 with a dart the out mode does not take busts the visit. The score returns to the start of the visit. The dart that busts counts as thrown; later darts of the visit do not.
- **Game shot:** a dart that reaches exactly 0 wins the leg. `leg_won` is announced at once; the leg is booked when you pull the darts, so a correction before that still counts. Darts after the winning dart do not count.
- **Checkout route:** whenever a score can be finished, the cards show the route for the darts left in the visit, for example `T20 T20 BULL` for 170, and outline the next bed on the board. "No checkout possible" appears only for a score that one visit could finish: up to 170 with double out, up to 180 without. The route follows the professional checkout charts; with *Practice personal checkout routes*, it prefers your strongest doubles: those with at least 10 darts that you hit at least as often as all your doubles together, never one you have not hit yet. On the way to a double, the outer bull counts as an easy single, as in the charts' `25 D18` for 61; a setup for the next visit avoids it, because a miss next to it leaves no finish. [How the route is chosen](how-it-works.md#practice-game).
- **Setup:** where the darts left cannot check out, at 169, above 170 or at 100 with one dart, the cards show a setup instead, for example *T20 T20 S17 leaves 32*: darts that leave a good double for the next visit, preferably 32, 40, 36 or 16. The caller says *Leave yourself 32*. [How the setup is chosen](how-it-works.md#setup-hints).
- **Average:** points scored per three darts of the leg. Darts of a bust visit count, their points do not.
- **Records:** checkouts, the checkout rate, the doubles and the personal bests count legs with double out that a dart checked out. A leg that the round limit decided counts for the legs and sets of the match, and sets no checkout, best leg or record.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/round-limit-dark.png">
  <img src="images/en/round-limit-light.png" alt="How a leg with a round limit ends: a dart that checks out wins the leg at any time. Otherwise, once every player has thrown the last round, the one player or team with the lowest score wins the leg; on a tie, the players throw another round" width="460">
</picture>

<img src="images/en/card-match.png" alt="Live card during a 501 match of Alex and Sam: Alex at the board with 81 left and the route T19 D12, Sam with 361 left" width="760">

## Cricket games

<img src="images/en/cricket.webp" alt="Animation: Cricket between Alex and Sam. Alex closes the 20, scores 60 and hits a 19; after the takeout Sam closes the 19, scores 57 and hits a double 18" width="620">

The live card and the scoreboard show a chalkboard with the marks of every player or team (`/`, `X`, `Ⓧ`), the points and the marks per round (MPR). Numbers everybody has closed are dimmed, and the board outlines the next open number, from 20 down to the bull. Once you have closed everything but the points are not yet enough to win, it outlines the highest number an opponent still has open, to score on; in Cut-Throat, one that a player with the fewest points has open. Screen readers read the marks as words.

In a match, the column of the player at the board helps like a dart machine: a green frame where a dart scores, because you have closed the number and somebody still needs it, and an amber frame where somebody else has closed it and scores on you, so you had better close it. A dart of the visit that counted nothing, on a number nobody needs any more or on none of the game, is struck through. A mouse over a frame or a struck-through dart, or a tap on it, says what it means.

<img src="images/en/cricket-hints.webp" alt="Animation: Cricket between Alex and Sam on the scoreboard. Alex closes the 20 and the 19, and an S5 is struck through as it counted nothing; at Sam's turn the 20 and the 19 are framed in amber, to close; Sam closes the 20, marks the 19 once, and an S1 counts nothing; at Alex's turn the 19 is framed in green, to score" width="760">

### Cricket

- **Marks:** only 20 to 15 and the bull count. A single is one mark, a double two, a triple three; the outer bull is one mark, the bullseye two. Three marks close a number.
- **Points:** further marks on a closed number score its value (25 for the bull) as long as another player still has it open.
- **Win:** close every number with at least as many points as everybody else. The win is checked after every dart, so a closing dart wins at once when the points are enough, and later darts of the visit do not count. Alone, closing every number wins the leg.
- **Marks per round:** the marks that closed a number or scored, per three darts actually thrown. Marks on a number nobody needs any more do not count.

<img src="images/en/scoreboard-cricket.png" alt="Scoreboard in Cricket between Alex and Sam: the chalkboard with marks, points and marks per round, and T19 as the next target" width="760">

### Cut-Throat Cricket

- **Marks:** as in Cricket, on 20 to 15 and the bull.
- **Points go to the others:** further marks on a closed number give its value to every other player who still has it open; the player who threw them scores nothing.
- **Win:** close every number with no more points than anybody else: the fewest points win. The win is checked after every dart, also for the others: when the points of a dart leave another player who has closed everything with the fewest points, that player wins at once, and the later darts of the visit do not count. Alone, closing every number wins. The scoreboard reminds everybody that the fewest points win.

### Tactics

- Cricket on the numbers 20 to 10 and the bull, twelve numbers in all. Marks, points and the win follow the rules of Cricket.

<img src="images/en/scoreboard-tactics.png" alt="Scoreboard in Tactics between Alex and Sam: the chalkboard from 20 down to 10 and the bull, Alex with 94 points, Sam at the board with T15 as the next target" width="760">

### Wild Mouse

Also known as Minnesota Cricket. Besides 20 to 15 and the bull, every player closes three more targets: **Doubles**, **Triples** and **3 in a bed**. The chalkboard has a row for each.

<img src="images/en/wild-mouse.webp" alt="Animation: Wild Mouse between Alex and Sam on the scoreboard. Alex's first T20 closes the 20, the next two count for Triples and, three in one bed, close 3 in a bed; Sam closes the 19, marks the 16 twice, and an S14 counts nothing and is struck through; Alex's next T20 closes Triples, a D19 marks the 19 twice and an S20 scores 20" width="760">

- **Every dart counts once:** a dart marks its number while you still have it open, as in Cricket: a T20 is three marks on the 20. Otherwise a double is one mark on Doubles and a triple one mark on Triples, on any number and with the bullseye as a double. Three marks close Doubles and Triples.
- **3 in a bed:** three darts of a visit in the same bed, such as three single 18s or three T20s, close it at once; the darts count for their targets as well. To play without it, as casual players often do, switch off *Three in a bed* on the new game screen or *Practice Wild Mouse three in a bed*; a change starts the game anew.
- **Points:** a target you have closed scores while another player still has it open: a number its value per mark, as in Cricket, Doubles and Triples the dart's whole score (32 points for a D16), and 3 in a bed the three darts together (180 for three T20s).
- **Win:** close every target with at least as many points as everybody else, as in Cricket.
- **Target:** the board outlines the next open target: 20 down to 15, then any double, any triple, for 3 in a bed the single 20 and after the first dart its bed, and the bull last.
- **Marks per round:** every mark that closed or scored counts, on the numbers as on Doubles and Triples; 3 in a bed counts one.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/wild-mouse-dark.png">
  <img src="images/en/wild-mouse-light.png" alt="Where a dart counts in Wild Mouse: its number while it is open for you, a triple three times; otherwise one mark on Doubles or Triples while they are open; otherwise it scores on a target you closed that others still need; otherwise it counts nothing and is struck through. The third dart: all three in one bed close 3 in a bed, or score once it is closed" width="560">
</picture>

### Random Cricket

Cricket on numbers that change with every leg, as Scolia, Granboard and Dartsmind offer it: the doubles and triples change from leg to leg, which keeps a group of regulars on their toes.

<img src="images/en/scoreboard-random-cricket.png" alt="Scoreboard in Random Cricket between Alex and Sam: the chalkboard with the numbers the leg drew, 16, 10, 9, 7, 3 and 2, and the bull. Alex has closed the 16, framed in green where a dart scores, and the 10, with 16 points; Sam has closed the 10 and marked the 9 twice; Alex's T10 is on the board, and T9 is the next target" width="760">

- **Numbers:** every leg draws six different numbers from 1 to 20 at random; the bull is always in. The chalkboard shows them highest first. The next leg draws new ones, and so do a new leg and a new match that you start.
- **Marks, points and the win** follow the rules of [Cricket](#cricket). A dart on a number the leg did not draw counts nothing and is struck through.
- **Kept with the game:** an undone visit and a restart of Home Assistant play on with the same numbers.
- **The caller** names the numbers when a leg begins, such as *Numbers 18, 14, 11, 7, 5, 2 and the bull*.

### Hidden Cricket

Random Cricket with a secret: the six numbers of the leg stay hidden until a dart finds them.

<img src="images/en/hidden-cricket.webp" alt="Animation: Hidden Cricket between Alex and Sam on the scoreboard. The chalkboard starts with six question marks and the bull. Alex's T20, T19 and T18 hit no number of the leg and count nothing; Sam's T15 shows the 15 and closes it, while the T17 and T16 count nothing; Alex's T14, T13 and T12 find nothing either; Sam's T11 and T9 show and close the 11 and the 9, and Alex, at the board again, has T15 as the target and amber frames on the three numbers Sam has closed" width="760">

- **Numbers:** six of 1 to 20, drawn anew for every leg as in Random Cricket, and the bull. The chalkboard shows a question mark for each number until a dart marks it; from then on its row shows the number to everybody. The bull always shows. The rows keep the order of the draw, so the row a number shows up in says nothing about the numbers still hidden.
- **Marks, points and the win** follow the rules of [Cricket](#cricket): the dart that finds a number marks it, and a dart on a number the leg did not draw counts nothing.
- **Target:** the board outlines the highest number that shows and is still open, then the bull once every number shows, and once those are closed, a number that shows to score on. While numbers are still hidden and every number that shows but the bull is closed, there is no target: that is the time to search. It never points at a hidden number: finding those is up to you.
- **The bot** plays the numbers that show; once it has closed them, it searches for the others with the triple of a different number with every dart ([how](how-it-works.md#bot)).
- **No peeking:** *Practice remaining score* has `null` for a number that does not show yet, so neither the cards nor the history of Home Assistant give it away.
- **The caller** names a number as soon as it shows, such as *17 is in*.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/hidden-cricket-rules-dark.png">
  <img src="images/en/hidden-cricket-rules-light.png" alt="What a dart does in Hidden Cricket: every leg draws six of the numbers 1 to 20, which stay hidden, and the bull, which always shows. A dart on a number the leg did not draw counts nothing. A dart on a drawn number that does not show yet shows it to everybody in its row and marks it. A dart on a number that shows marks it or scores, as in Cricket" width="460">
</picture>

## Party games

Six pub classics and three games of play.autodarts.io for one to eight players, a whole party; Killer needs two. With five to eight, the scoreboard shows two rows of four tiles.

<img src="images/en/scoreboard-party.png" alt="Scoreboard in Killer for a party of eight, Alex to Ben, in two rows of four tiles: Alex at the board as a killer, Sam with two lives left" width="760"> They book a visit when you pull the darts and win legs and sets like any match. The cards show the round, the target and every player's points or lives, and outline the beds to aim at. Party games do not count for the X01 statistics.

### Shanghai

<img src="images/en/shanghai.webp" alt="Animation: Shanghai for Alex and Sam on the scoreboard. Both score on the 1 and the 2, then Sam hits single, double and triple 2 in one visit and wins at once" width="760">

- Seven rounds at the numbers 1 to 7; the traditional pub game plays 1 to 20 or nine rounds.
- Every dart in any bed of the round's number scores its value. A miss next to the number counts nothing.
- A single, a double and a triple of the number in one visit, a *Shanghai*, win the leg at once; later darts of the visit do not count.
- After seven rounds, the most points win. A tie in points goes to the player with more hits; with equal hits, the leg is played again and the next player starts it.

### Halve-It

<img src="images/en/halve-it.webp" alt="Animation: Halve-It for Alex and Sam on the scoreboard. Sam misses the 15 and falls from 40 to 20 points, catches up on the 16, and misses any double in the third round: 116 points become 58" width="760">

- Everybody starts with 40 points. The nine rounds aim at 15, 16, any double, 17, 18, any triple, 19, 20 and the bull, shown as *Bull (25/50)*.
- Hits add their score. *Any double* includes the bullseye. In the bull round, the outer bull scores 25 and the bullseye 50.
- A visit without a hit on the target halves the points, rounded down, also when fewer than three darts were thrown.
- The most points after nine rounds win; ties are decided as in Shanghai.

### Killer

<img src="images/en/killer.webp" alt="Animation: Killer for Alex, Sam and Kim on the scoreboard. Everybody throws for a number, Alex becomes a killer and takes Sam's lives, Kim becomes a killer too, and Alex takes the last life to win" width="760">

- Two to four players with 3 lives each.
- First, everybody throws one dart for a number of their own: any bed of 1 to 20 that nobody has yet. A miss, the bull or a number already taken means throwing again.
- Only doubles count after that. Hitting the double of your own number makes you a killer for the rest of the leg. Before that, the doubles of the others do nothing.
- A killer takes a life with every hit on another player's double and loses one with every hit on their own, also with a second own double in the visit that made them a killer.
- A player without lives is out: the rest of the visit does nothing, and the turn skips them from then on.
- The last player with a life left wins at once; later darts of the visit do not count.
- Killer keeps no points: `turn_changed` and `leg_won` carry the player's `lives` and whether they are a `killer` instead.

### Golf

<img src="images/en/golf.webp" alt="Animation: Golf for Alex and Sam on the scoreboard. After every visit the scorecard fills: Alex plays 2, 3 and 1, Sam 4, 5 and 5, and the fourth hole is under way" width="760">

- Nine or 18 holes, set in *Practice Golf holes*; hole *n* is played on the number *n*.
- A player throws up to three darts per hole and may stop after any dart by pulling the darts: **the last dart thrown counts**.
- Strokes: a double is a hole in one, 1 stroke; a triple 2, an inner single 3, an outer single 4, anything else 5, also a visit passed without a dart. Whether a single is inner or outer comes from the position the board reports, split in the middle of the treble ring; a single without a position counts as an outer single.
- The fewest strokes after the last hole win. A tie at the top plays extra holes among the tied players, in their throwing order, on the next numbers (after 20 from 1 again), until one of them has fewer strokes after a hole. The scoreboard keeps a scorecard of every hole and shows the extra holes as a play-off.

### Baseball

<img src="images/en/scoreboard-baseball.png" alt="Scoreboard in Baseball between Alex and Sam: the runs of both players and the scorecard of the first four innings" width="760">

- Nine innings; inning *n* is played on the number *n*, with one visit of three darts.
- Every dart in a bed of the inning's number scores runs: a single 1, a double 2, a triple 3. The bull scores nothing.
- The most runs after nine innings win. A tie at the top plays extra innings among the tied players on 10, 11 and so on, until one of them leads after an inning.

### Count-Up

- 1 to 20 rounds, set in *Practice Count-Up rounds*, 8 by default. Every dart scores its value.
- The most points win. A tie at the top plays extra rounds among the tied players until one of them leads after a round.

### Bermuda

<img src="images/en/bermuda.webp" alt="Animation: Bermuda for Alex and Sam on the scoreboard. Both score on the 12, Sam misses the 13 and falls from 48 to 24 points, and Alex climbs to 167 on the 14" width="760">

- Thirteen rounds from 0 points, as [play.autodarts.io](https://play.autodarts.io) plays them: 12, 13, 14, any double, 15, 16, 17, any triple, 18, 19, 20, the bull and the bullseye.
- Hits score their points. *Any double* includes the bullseye. In the twelfth round, *Bull (25/50)*, both bulls count; in the last, *Bullseye (50)*, only the bullseye.
- A visit without a hit on the target halves the points, rounded down, also when fewer than three darts were thrown. *Practice Bermuda halving on a miss* turns this off, so that a miss just scores nothing; a change starts a game of Bermuda anew.
- The most points after 13 rounds win; ties are decided as in Shanghai.

### Round the World

<img src="images/en/round-the-world.webp" alt="Animation: Round the World for Alex and Sam on the scoreboard. Alex hits 1, 2 and 3 in one visit, Sam 1 and 2, and every tile shows how many of the 21 targets the player has done" width="760">

- Every player goes round the board on their own: the numbers 1 to 20, then the bull. *Practice Round the World order* plays 1 to 20 (`ascending`, the default), 20 to 1 (`descending`) or the numbers in a new random order for every leg (`random`); the bull always comes last. A change starts a game of Round the World anew.
- Any bed of the target completes it, and the next dart aims at the next target, also within a visit. The outer bull and the bullseye both complete the bull.
- Every hit adds its points, a triple 3 nine of them. The tiles show the points and how many of the 21 targets each player has done.
- The first to complete the bull wins at once; later darts of the visit do not count.

### Gotcha

<img src="images/en/gotcha.webp" alt="Animation: Gotcha up to 101 for Alex and Sam on the scoreboard. Sam reaches Alex's 75 and sends Alex back to 0, Alex climbs to 86, and Sam checks out on double 10" width="760">

- Everybody counts up from 0 to the target score: 301 by default, 101 to 1001 in *Practice Gotcha target score*. A change starts a game of Gotcha anew.
- The leg ends as the *Practice out mode* asks, as X01 does the other way round: on any dart (straight), on a double or the bullseye (double), or also on a triple (master). A new out mode changes a leg only before its first dart.
- A dart that goes past the target score, leaves 1 with double or master out, or reaches the target with a dart the out mode does not take busts the visit: it counts nothing.
- **Gotcha:** a dart that brings you to exactly another player's score sends that player back to 0. A visit that busts takes its gotchas back.
- The tiles show every player's points and the points to go. The first to finish wins at once.
- Unlike play.autodarts.io, Gotcha here has no round limit: *Practice max rounds* applies to X01 only, and a leg goes on until somebody finishes.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/gotcha-rules-dark.png">
  <img src="images/en/gotcha-rules-light.png" alt="What a dart does in Gotcha: a dart adds its points. Past the target score, on 1 left with double or master out, or on the target with a dart that does not fit the out mode, the visit busts and counts nothing, its gotchas included. On the target with a fitting dart, the player wins the leg. Below the target, every other player on exactly the new score goes back to 0, and the next dart follows" width="460">
</picture>

## Training games

Eight classic drills for one player. Each follows the darts of the current visit, books the visit when you pull the darts and outlines its target on the board. A finished game stays on the cards until the next dart starts it again; *New practice leg* starts it again at once. Every game keeps its last 10 results, and its best result is a [personal best](statistics.md#personal-bests-streak-and-daily-goal). `drill_finished` and `checkout_attempt` announce the results. In the checkout training, 121 and Catch 40, as in X01, every dart at a score that one double finishes counts for your [doubles analysis](statistics.md#doubles-analysis).

### Around the Clock

<img src="images/en/training-game.webp" alt="Animation: Around the Clock. Each hit moves the target from 1 to 6 and outlines every bed of the next number on the board" width="620">

- 1 to 20, then the bull, in order, with any bed of the number. The bull target reads *Bull (25/50)* on the cards, `25` in the attributes: the outer bull and the bullseye both count, and both are outlined. Fewer darts are better.

### Doubles training

- D1 to D20, then the bullseye (`BULL`); only the double ring and the bullseye count. Fewer darts are better, and every dart counts for your [doubles analysis](statistics.md#doubles-analysis).

### Checkout training

- A random score from 2 to 170 that three darts can finish, checked out on a double within three visits. As in X01, a bust voids only its visit: the next visit starts from the score before it. A third visit without the finish, a bust in it included, ends the attempt; the route shows only while the attempt goes on. The checkout rate counts successful attempts.

### Bob's 27

<img src="images/en/bobs-27.webp" alt="Animation: Bob's 27 on the scoreboard. Two hits on D1 raise 27 points to 31, a visit without D2 lowers them to 27, and two hits on D3 raise them to 39" width="760">

- Start with 27 points and throw one visit at each double from D1 to D20 and then at the bullseye. Every hit adds the value of the double; a visit without a hit subtracts it.
- The game is lost as soon as the score reaches zero or less, and completed after the bullseye.

### 121 checkout

<img src="images/en/checkout-121.webp" alt="Animation: the 121 checkout on the live card. T20, S1 and S20 leave 40, D20 in the second visit is the game shot, and the target climbs to 122" width="620">

- Check out 121 on a double within three visits, nine darts. As in X01, a bust voids only its visit. A finish raises the target to the next score; three visits without the finish lower it by one, never below 121.
- Every score up to 170 is played, also those one visit cannot finish, such as 159: nine darts can, and the cards show a setup for the next visit instead of a route. 170 is the top. The highest score checked out is the personal best.

### Catch 40

<img src="images/en/scoreboard-catch-40.png" alt="Catch 40 on the scoreboard: 62 to check out in the second round, the visit and the points so far" width="760">

- Check out 61, 62 and so on up to 100, each on a double within two visits, six darts.
- A checkout in two darts scores 3 points, in three darts 2 and in four to six darts 1. No two darts can finish 99, so there three darts score 3 points.
- As in X01, a bust voids only its visit: the second visit starts from the score before it, and a finish then scores 1. Two visits without the finish score nothing, and the next number follows. At most 120 points.

### JDC Challenge

- The practice routine of the [Junior Darts Corporation](https://www.juniordarts.com/), 57 darts, as its academies play it ([rules](https://www.godartspro.com/jdc/)).
- First one visit at each number from 10 to 15: every dart in a bed of the number scores its value, and a single, double and triple of it in the visit add 100 (a Shanghai).
- Then one dart at each double from D1 to D20, 50 points a hit, and one at the bullseye for 100. A dart the board does not detect moves on to the next double with the next detected dart.
- Then one visit at each number from 15 to 20 like the first part. At most 3,380 points.

### Singles training

- One visit at each number from 1 to 20 and then at the bull (`25`).
- Every dart in a bed of the number scores a point per mark: a single 1, a double 2, a triple 3; the outer bull 1 and the bullseye 2. At most 186 points.

## Statistics

Every game feeds the statistics: X01 legs the first-9 average, checkout rate and doubles rate; Cricket the marks per round; named players their [profiles](statistics.md#player-profiles), head-to-head records, match history, [achievements](statistics.md#achievements) and weekly trends; every dart at a double the [doubles analysis](statistics.md#doubles-analysis). The [statistics guide](statistics.md) shows all of it, and [records and statistics](how-it-works.md#records-and-statistics) explains exactly which legs count for which record.
