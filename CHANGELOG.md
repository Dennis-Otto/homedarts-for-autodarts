# Changelog

All notable changes of HomeDarts for Autodarts, called Autodarts up to version 1.18. The complete notes of every version, with each pull request, are on the [releases page](https://github.com/Dennis-Otto/homedarts-for-autodarts/releases); what comes next is in the [roadmap](docs/roadmap.md). Versions follow [Semantic Versioning](https://semver.org/).

## Unreleased

## [2.1.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v2.0.1...v2.1.0) (2026-10-25)

### Fixed

- **No warning of Home Assistant 2026.10 when a tournament names its boards by their devices:** the tournament on several boards reads the config entry of a board's device the way Home Assistant 2026.10 keeps it, so Home Assistant no longer warns in its log that this stops working in Home Assistant 2027.10. The tests now fail on every such warning of Home Assistant about HomeDarts, also every night against its beta, so the next one is fixed before it reaches your log.
- **The cards keep finding their board's config entry after Home Assistant 2027.10:** the cards read the config entry of a board's device from the field Home Assistant 2026.10 keeps it in, so their actions still reach the right board once Home Assistant drops the two older fields.
- **Every dart position comes back after a restart:** a dart that the board measured at the far edge of the area it reports kept its place in the grouping and the aim map only until Home Assistant restarted, because the stored position, rounded to a tenth of a millimetre, lay just past that edge. Now every stored dart comes back, and new tests play each party game, the bull-off, the dart positions and the double rates on after a restart and check that nothing changes.

### New

- **Deleting a board no longer loses its statistics:** before Home Assistant deletes a board, HomeDarts writes a backup of everything the board stored, with the training, the games, the player profiles with their progress and badges, the personal bests, the weekly report and the calendar, to `homedarts/backups` in the media folder, the newest five per board. Add the board again, and a repair offers to bring it all back. The new actions `homedarts.backup` and `homedarts.restore`, for administrators and automations, write a backup on request and restore one ([Backups](https://dennis-otto.github.io/homedarts-for-autodarts/statistics.html#backups)).
- **One player on two boards:** `homedarts.restore` with `mode: merge` adds the players of a backup of another board to a board, so a player who throws on both gets one profile with the darts, legs, matches, checkouts, doubles, trends and badges of both boards, and the better personal bests. Each other board merges once, so no dart counts twice, and every restore first backs up what the board holds.
- **Your automations know when a game starts and ends:** the board's *Events* entity has two new events, `game_started` and `game_ended`, once per game, however it was set up: from the lobby of the scoreboard, by voice, with `homedarts.start_game`, the *Game* select, *New match*, the next match of a tournament or the first dart after a finished match. `game_started` tells the game, its mode (alone, a match, a party or training game, or a tournament), the players with their names and start scores, the format and the bot; `game_ended` tells whether the game was won, stopped, replaced by another one or ended with the idle time of the training session, with the winner. A restart of Home Assistant announces no game twice, so the light of a game, a board in use or a muted TV follow the games reliably ([Games that start and end](https://dennis-otto.github.io/homedarts-for-autodarts/entities.html#games-that-start-and-end)).
- **Walk-on music, like on stage:** the new blueprint *HomeDarts: walk-on music* plays the walk-on song of every player when a game starts, one after the other until the first dart, and the song of the winner after the match. The songs are files in the media folder named after the players, such as `alex.mp3`, with `bot.mp3` for the bot and `default.mp3` for everybody else; a player without a song walks on in silence ([Walk-on music](https://dennis-otto.github.io/homedarts-for-autodarts/automations.html#walk-on-music)).
- **The light show sets the scene when a game starts:** the light show blueprint has a new moment, *Game starts*, for the light you play in.
- **Rename a player, or make two names of one player one profile, without losing anything:** a typo in a name, a guest typed in twice as *Sam* and *Sammy*, or a kid who wants a new name no longer costs the statistics. The new action `homedarts.rename_player` gives a profile a new name, also a new spelling such as *Sam* for *sam*, and the statistics, personal bests, badges, the match history, head-to-head records, the training calendar, the board's records, the weekly report, the link to a person and the player names of the practice game and the tournaments keep it. A name that another profile has already merges the two, as if one player had thrown every dart: the counts add up, the better bests stay, each badge keeps the date it was first reached, and tiers that both names reach together unlock quietly. The event `player_renamed` tells automations the old and the new name. For administrators, the players card has a ⋮ menu on every profile with *Rename*, *Merge into …* and *Delete*, each behind a dialog that says what it does, and it works with the keyboard and a screen reader ([rename or merge players](docs/entities.md#rename-or-merge-players-homedartsrename_player), #467).
- **Full screen at the board, and a screen that stays on:** the scoreboard has a full-screen button at the top right of its top bar. A tap puts the scoreboard alone on the screen of a tablet, without the bars of the browser and without Home Assistant's header and sidebar, and the scores fill the whole screen; the button, Escape or a double tap on the scoreboard leaves full screen. Meanwhile the screen stays on, also after the tablet showed another app, wherever the browser lets a page keep it on: over HTTPS, such as with Home Assistant Cloud, and in the Companion app. Where it can't, the scoreboard says so once and links to what helps instead. The options `fullscreen_button` and `keep_awake`, in the card editor and in the section *Scoreboard view* of the automatic dashboard, switch either off; the TV of Home Assistant Cast and the stream overlay have no button ([full screen](https://dennis-otto.github.io/homedarts-for-autodarts/scoreboard.html#full-screen), #475).

### Improved

- **The pictures of the documentation are rendered once per change:** a pull request that only catches up with `main`, and the screenshot bot after its merge, take the pictures that the visual check already rendered from the same files, in under a minute instead of about ten, and keep the runners free for the tests. Only pictures of this repository's own runs count, never those of a pull request from a fork, and the weekly run of the screenshot bot still renders every picture anew ([images rendered once](https://dennis-otto.github.io/homedarts-for-autodarts/development.html#images-rendered-once)).
- **The pictures of the documentation follow a change of the cards sooner:** the screenshot bot and the visual check of a pull request render them in about 11 minutes instead of 15. The two big tournaments of 32 players stop once their pictures are taken, and the tests play them to their champion with many random results instead.

## [2.0.1](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v2.0.0...v2.0.1) (2026-10-23)

### Fixed

- **Ask Assist about your darts sounds more natural in German, Spanish, French and Dutch:** the answers use the same words as the rest of the integration, such as "¡Objetivo diario alcanzado!" and "Dagdoel bereikt!", and read as people say them, such as "Alex führt die Bestenliste mit einem 3-Dart-Average von 167 an." or "Vandaag: 3-dart-gemiddelde van 120,2 over 18 darts.". Assist also understands more ways to ask, such as "Was ist mein höchstes Finish?", "Wer steht an der Spitze der Bestenliste?", "¿Cuál es mi mejor checkout?", "¿Cuántos días seguidos llevo entrenando?", "Combien de jours de suite ?" and "Hoeveel dagen achter elkaar?". The update brings the new sentences and answers to every automation made from the blueprint; an automation in which you changed the sentences keeps yours, so add the new ones there yourself.
- **The security scans pass again for the test tools of Home Assistant:** Home Assistant 2026.10 pins Pillow 12.3.0 and uv 0.12.23 for the tests of every integration, and no update of the tests can fix their advisories until Home Assistant moves on, so the OSV-Scanner and Findings checks failed on every change. `osv-scanner.toml` now accepts every advisory of exactly these two versions, with the reason and until 2026-11-22. Nothing that you install changes: the integration ships neither of them.
- **The training report and Assist speak a regional language of Home Assistant:** the ready-made `summary` of the training report now comes in the language of Home Assistant, such as "30 Darts, 3-Dart-Average 57,3, höchste Aufnahme 140, 1 × 180." in German, from the new `summary` attribute of the *Training darts* sensor; an automation made from the blueprint gets it with the update. Assist answers in German, Spanish, French or Dutch also when Home Assistant speaks a regional variant such as `de-CH` or `es-419`, with the name of the game in that language too, instead of in English.

## [2.0.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.18.0...v2.0.0) (2026-10-21)

### Breaking changes

- **Autodarts is now HomeDarts for Autodarts:** Autodarts asked the project to stop using its name and logo, so the integration has a name and an icon of its own and the domain `homedarts`. Its actions are now called `homedarts.…`, such as `homedarts.start_game`, its cards `custom:homedarts-…`, its dashboard strategy `custom:homedarts`, and the flat board style of the live and heatmap cards is `flat`; highlights, exports and voice packs live in the media folder `homedarts`. After the update, add **HomeDarts for Autodarts** and choose to take over your boards: they keep their entities, history, statistics and dashboards. Automations and scripts that call the old actions need the new names ([From Autodarts to HomeDarts](https://dennis-otto.github.io/homedarts-for-autodarts/new-name.html)).
- **No cloud link:** Autodarts issues no client IDs to third parties, so the prepared link to the Autodarts cloud is gone, and HomeDarts works locally with the Board Manager. Online matches still reach Home Assistant through Tools for Autodarts.

### Improved

- **An icon of its own:** Home Assistant, HACS and the website show the integration's own icon, a house with a dartboard and a dart in its bull, in place of the Autodarts logo, which Autodarts asked the project to remove.

## [1.18.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.17.0...v1.18.0) (2026-10-19)

### Fixed

- **Voice control finds the darts of the visit by what they show:** a dart you can tap to correct now starts its spoken name with the words on its tile, such as "Dart 2 S20 20 points – Correct dart 2" on the Autodarts card and "S20 20 – Correct dart 2" on the scoreboard, so "click S20 20" in Voice Control or Voice Access taps it, and a screen reader no longer runs the bed and the points together.

### New

- **The *Start tournament* button chooses the groups and who goes on:** two settings join the other tournament settings, *Tournament groups* (2 to 8, or 0, the default, for groups of about four players) and *Tournament qualifiers per group* (1 to 4, two by default). *Start tournament* plays groups and knockout with them, and so does `start_tournament` when you leave out `groups` and `advance`; `groups: 0` asks for groups of about four players. The new game screen of the scoreboard starts from them, and the groups you choose there or in the action stay in them for the next tournament ([tournaments](docs/entities.md#tournaments), #389).

## [1.17.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.16.0...v1.17.0) (2026-10-19)

### New

- **Tournaments of up to 32 players, in a double elimination or groups with a knockout:** a knockout now takes up to 32 players, with a round of 16 and a round of 32, and two formats join the round robin and the knockout. In a **double elimination**, nobody is out before losing two matches: a loser of the winners' bracket gets a second chance in the losers' bracket, the winners of both meet in the grand final, and a deciding final follows if the winner of the losers' bracket wins it. With **groups and knockout**, six to 32 players play a round robin in two to eight groups, of about four players unless you choose the number, and the best of every group, two unless you choose one to four, go on into a knockout, where the group winners are the top seeds and nobody meets a player of their own group in its first round. Choose them on the new game screen, with steppers for the groups and how many of each go on, or with `start_tournament` (`format: double_knockout` or `groups_knockout`, `groups`, `advance`). Between the matches, the scoreboard shows the tables of the groups side by side with the places that go on marked, and the losers' bracket below the winners' bracket; brackets of 16 and 32 places get smaller boxes. *Tournament players* shows as many names as its 255 characters hold, then `…`, and lists them all in its attribute `players`. A round robin still takes up to eight players ([tournaments](docs/games.md#tournaments), #381, #385).
- **One tournament on several boards at once:** a club evening with two boards or more plays one tournament on all of them, Autodarts boards and dartboards without Autodarts alike. Start it with `start_tournament` and the other boards in `boards`, which the action's device picker fills: every board plays a match of its own at once, and after its pause a board takes the next match whose players play at no other board, as soon as it is clear. The players get their pause too, wherever they played last. The board that started the tournament holds it: the table or the bracket takes the results of every board, and its `tournament_match_finished` events name the board that played the match. Between the matches, the scoreboard of every board shows a box for each board, with the match it plays or when its next one starts, and the expected end of the tournament, worked out from the players' averages and the pace of the matches played; *Tournament* has it as `ends_at` at one board too. *Stop tournament* on any board stops it on all of them, and the boards find each other again after a restart ([a tournament on several boards](docs/games.md#a-tournament-on-several-boards), #394, #396).
- **Random Cricket and Hidden Cricket, as on Scolia, Granboard and Dartsmind:** two more Cricket games for one to four players or two teams, also against the bot and in tournaments. Random Cricket plays six numbers of 1 to 20 and the bull, drawn anew for every leg; Hidden Cricket keeps them hidden, as question marks on the chalkboard, until a dart finds one, and then shows it to everybody. Marks, points and the win follow the rules of Cricket. The numbers stay the same through an undone visit and a restart of Home Assistant, the scoreboard's caller names them, and the bot searches for the hidden ones. Start them from the new game screen, by voice or with `start_game` ([Random Cricket](docs/games.md#random-cricket), [Hidden Cricket](docs/games.md#hidden-cricket), #361, #364).
- **The scoreboard in your stream, and clips of your highlights:** the automatic dashboard has a *Stream overlay* view for a browser source in OBS Studio or Streamlabs, at its address with `/overlay` at its end, which its tabs leave out. It shows the scoreboard alone over the picture of your stream: the game, every player's score, the checkout route, the darts of the visit, the winner and the confetti, on dark plates that stay readable over any video, and nothing between games. It is see-through along the bottom of the picture; the dashboard's settings and the card's options `overlay`, `overlay_layout` and `overlay_color` put it in the top-left corner or across the whole picture, or on a key colour for the chroma key filter of OBS, `#00FF00` unless you choose another. On a dashboard the overlay fills the window and hides Home Assistant around it, and Escape or a double click leaves it. With a *Clip camera*, a camera of the room or of your stream, the highlight photo also records every big moment as an MP4 beside its photo, from a few seconds before the dart, and the highlight gallery plays it; the recording runs in the background, so your notification goes out at once ([stream overlay](docs/scoreboard.md#stream-overlay), [highlight clips](docs/automations.md#highlight-clips), #370, #372).
- **Ask Assist about your darts:** the new blueprint *Autodarts: ask Assist about your darts* answers "What is my average today?", "How many 180s this week?", "How many darts today?", "What is my best checkout?", "How long is my streak?", "Who leads the leaderboard?" and "Where should Sam aim?" in English, German, Spanish, French and Dutch, for example "Wie ist mein Schnitt heute?", "¿Cuántos 180 llevo esta semana?" or "Où dois-je viser ?". Assist answers from the statistics of the board in the language you asked in, such as "Today: a 3-dart average of 120.2 from 18 darts.", or says what is missing before the first dart. Today counts every training session that started today, the week is that of the weekly report, the leaderboard ranks as the scoreboard does, and "Where should I aim?" is for the player linked to the person you are signed in as. With more than one board, the board with the most darts this week answers unless you choose one. Like every blueprint, it now comes with the integration ([ask Assist about your darts](docs/automations.md#ask-assist-about-your-darts), #376, #378).
- **The blueprints come with the integration and stay current:** after installing the integration, all fifteen blueprints are on the blueprints page of Home Assistant without importing them. Every update brings the new versions of the blueprints you haven't changed, also of those you imported before, and the automations made from them reload with their settings, so a blueprint always matches the integration it runs with. A blueprint you changed stays yours, with a repair that offers the version of the integration; one you deleted stays deleted, and *Re-import blueprint* is no longer needed ([updates of the blueprints](docs/automations.md#updates-of-the-blueprints), #383, #384).
- **Granboard over Bluetooth (experimental):** a Granboard sends its darts to Home Assistant over Bluetooth, through an adapter of Home Assistant or an ESPHome Bluetooth proxy anywhere in the house, and you play every game, the training and the statistics with them, as on a dartboard without Autodarts, without entering a dart. Home Assistant finds the board and offers to set it up; every hit goes into the visit, the button beside the board passes to the next player, a dart in the wrong bed is corrected on the scoreboard, and a board that sleeps or goes out of reach connects again on its own. The diagnostic entity *Granboard connection* shows the connection. The integration reads the board's frames as open-source Granboard apps do, but it has not met a real board yet: [check every bed](docs/granboard.md#check-every-bed) with yours to help take the label off ([Granboard over Bluetooth](docs/granboard.md), #386, #388).

## [1.16.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.15.0...v1.16.0) (2026-10-18)

### New

- **The score on a pixel display at the board:** the new blueprint *Autodarts: score display* shows the practice game on an AWTRIX 3, such as the Ulanzi TC001, or on a PixelIt: the score of the player at the board after every dart, in green with its route when a checkout is possible, the points in Cricket and the party games, and for a few seconds a 180, a bust, a won leg and the winner of the match. When the game is switched off, or after the idle time, the display goes back to its clock. AWTRIX 3 and PixelIt take the screen over MQTT, and PixelIt also over HTTP through a REST command ([score display](docs/automations.md#score-display-on-an-awtrix-or-a-pixelit), #343, #346).
- **The scoreboard on a TV through Chromecast:** Home Assistant Cast shows the cards and the automatic dashboard on a TV with a Chromecast or on a Google Nest Hub, where it said *Custom element doesn't exist* before. The integration keeps its two modules in the dashboard resources, which Cast loads, brings them up to date with every start of Home Assistant and removes them with its last board; browsers still load them once. With resources in YAML, add the two lines that the documentation names. The pictures of the players come from the address of Home Assistant, so they show on the TV too ([Home Assistant Cast](docs/scoreboard.md#on-a-tv-with-home-assistant-cast), #347, #349).
- **The callers and the weekly report speak your language:** freshly imported, the dart caller, the practice caller and the weekly report speak the language of Home Assistant, in English, German, Dutch, French and Spanish, without a message of your own. In German, for example, the practice caller says "Lea, du brauchst 101", "Überworfen" and "Game shot, und das Match, Lea!", the dart caller "Einhundertachtzig!" and "Triple 20", and the weekly report arrives as *Deine Dartwoche* with a decimal comma. They follow a new language of Home Assistant at once. The board events bring these words in `call`, and the weekly report in `title` and `summary`, for your own automations too. In English, every call stays as it was, and messages you wrote yourself stay as they are; *Word for the bot* and *Word for a player without a name* now only apply to those. Pick a voice that speaks the language of Home Assistant, and to keep English calls in a Home Assistant of another language, enter the English examples as your messages. An automation you set up before speaks your language once you re-import its blueprint; if it saved the English default of before, replace that with `{{ call }}` ([calls in the language of Home Assistant](docs/automations.md#calls-in-the-language-of-home-assistant), #352, #353).
- **A caller for blind and low-vision players:** the caller of the scoreboard can call every dart as it lands, by its bed, such as "Treble 20", or by its points, such as "60"; the route of a checkout, such as "Treble 19, Double 12", and again after each dart that leaves another finish for the darts left; and the next target of a training or party game, such as "Target: Double 16", as soon as it moves on. Switch on *Call every dart*, *Call the checkout route* and *Call the next target* in the caller options of the scoreboard or in the settings of the automatic dashboard; they are off until you do. With a voice pack, the darts, routes and targets play its files of the beds as darts-caller names them, `bs_target_is` and `bs_any_double` included, which *Generate voice pack* now records too, and the browser's voice says what the pack lacks ([for blind and low-vision players](docs/scoreboard.md#for-blind-and-low-vision-players), #358, #360).
- **Online matches from the Autodarts cloud, once it is linked:** the integration is ready for the cloud link, which waits for the client ID that Autodarts issues to the integration. Once linked, the busts, won legs and matches and every dart of your online matches arrive as the same board events as from the online bridge ([the cloud link](docs/online-matches.md#the-cloud-link)), with the source `cloud`, without a browser with Tools for Autodarts, and a board without a Board Manager in your network, such as Lens, gets the Events entity for them. While the bridge is switched on, it alone reports them. A linked board renews its login a minute before it expires, as Autodarts advises (#365).

### Improved

- **Quicker on a Raspberry Pi:** every action, such as a button, a setting or a new game, built the whole store of the training twice: once to save it and once more to compare it with what it had saved, which with a long history and many players took about 20 milliseconds on a desktop PC and several times as long on a Raspberry Pi. It now builds it once, and a dart that lands while it is saved is still saved when Home Assistant stops, as before. The setup hint of the scoreboard and the aim of the bot no longer try 12,341 ways to throw three darts where nothing can be set up, such as 501 at the start of a leg: every setup from 171 to 1001 is found in a tenth of the time, with the same result. Home Assistant also loads the integration about a quarter to half a second faster, because the checkout training no longer works out its 162 scores at every start ([setup hints](docs/how-it-works.md#setup-hints), #329, #333).

## [1.15.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.14.0...v1.15.0) (2026-10-18)

### New

- **Bermuda, Round the World and Gotcha, as on play.autodarts.io:** three more party games for one to eight players. Bermuda plays 13 rounds from the 12 to the bullseye, and a visit without a hit halves your points unless you switch *Practice Bermuda halving on a miss* off. Round the World goes from 1 to 20, from 20 to 1 or in a random order, then to the bull; any bed counts, and the first at the bull wins. Gotcha counts up to a target score of 101 to 1001 with your out mode: go past it and the visit busts, reach another player's score exactly and they go back to 0. Start them from the new game screen, by voice or with `start_game` (`halve_on_miss`, `order`, `target_score`); the scoreboard shows the targets, how far everybody has come round the board and the points to go, and the caller calls the visits and the busts ([party games](docs/games.md#party-games), #305, #308).
- **The caller with a real voice:** the caller of the scoreboard, the dart caller and the practice caller play voice packs, recorded calls in `autodarts/voices` of the media folder whose files are named as in the voice packs of darts-caller, so a pack of darts-caller works as it is. The scoreboard plays the sounds of a call one after the other, with a name the pack lacks in the browser's voice, and every call the pack has no sound for is spoken as before. The new action *Autodarts: Generate voice pack* records a complete pack with any text-to-speech engine of Home Assistant, such as Piper for a voice that never leaves your home; enter the pack as *Voice pack* in the caller options of the scoreboard or of the blueprints ([voice packs](docs/scoreboard.md#voice-packs), #316, #320).
- **Try the cards live:** the [live demo](https://dennis-otto.github.io/homedarts-for-autodarts/demo/index.html) on the website plays a 501 against the bot, a Cricket game and a tournament with the scoreboard, the live, training and players cards, right in the browser: nothing to install, on a phone too and in English, German, Dutch, French and Spanish. The integration plays the games itself, and the screenshot bot records them anew whenever the cards change, so the demo always shows the cards as they are (#307).

### Fixed

- **The darts arrow of the trends no longer falls during every week:** the players card compared the darts of the older half of the weeks shown with those of the newer half, which ends with the current week. If you threw the same number of darts every week, the arrow fell for most of each week, and with 5, 7, 9 or 11 weeks shown it rose, because the newer half had one week more. It now compares the darts per week of the complete weeks, so steady practice shows → and only more or fewer darts a week turn it; a week without practice counts as one without darts, so the arrow also shows when you start practicing or take a break. The darts over the weeks and the line still count the current week; the other arrows were not affected (#327, #328).
- **The dart positions come back after a dropped connection:** when the training card could not get the positions of the heatmap, for example while Home Assistant restarted, it said *No dart positions yet.* until your next visit. It now keeps the positions it showed and asks again with the next update (#327, #328).

## [1.14.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.13.0...v1.14.0) (2026-10-14)

### New

- **Where to aim, from your own spread:** the heatmap of the training card has a fourth mode, *Aim*, that shows where on the board you score the most points per dart with the spread of your own darts. The treble 20 pays only when your darts land close together: from a spread of about 17 mm the treble 19 scores more, and with a wide spread a spot left of the bull, as Tibshirani, Price and Taylor showed in *A statistician plays darts*. From 30 darts aimed at a treble, the map colors every spot of the board by the points per dart you would score aiming there, rings the best aim and compares it with the treble 20, the treble 19 and the bull; with fewer darts it says how many are missing. The player profile has the best aim and its points per dart as `best_aim` and `expected_ppd`, for automations and Assist. The browser draws the map beside the page, in a worker of its own. Home Assistant works out your spread and the best aim after each visit, in some tens of milliseconds and beside its event loop, so nothing waits for it, and the spread of the session only when the map shows it ([where to aim](docs/statistics.md#where-to-aim), #276, #292).
- **Voice in Spanish, French and Dutch:** the blueprints *Autodarts: start a game by voice* and *Autodarts: enter darts by voice* now understand Spanish, French and Dutch as well as English and German, for example "Juega 501 para Alex y Sam", "Lance la partie Cricket pour Alex", "Speel 501 tegen de bot", "Alex hace 140", "Alex a fait 140", "Dubbel 16", "Joueur suivant" or "Ongedaan maken", and Assist answers in the language of Home Assistant. Numbers work as digits or, in the language of Home Assistant, as words such as "ciento cuarenta", "cent quarante" or "honderdveertig". The description of every blueprint now ends with a link to its settings and examples in the guide. For the new sentences, choose **Re-import blueprint** for both voice blueprints on the blueprints page; sentences you saved in an automation stay as they are (#301).

## [1.13.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.12.4...v1.13.0) (2026-10-14)

### New

- **X01 with the rules of play.autodarts.io:** the in and out mode is now *Straight*, *Double* or *Master*. Master in opens a leg with a double, a triple or the bullseye, and master out finishes on one: a master-out 501 takes `T20` for 60, while the route keeps the double of the checkout chart wherever that needs no more darts. With the bull mode *50/50*, the outer bull scores 50 like the bullseye, and the routes aim at the bull for 50, such as `BULL D20` for 90; with double out only the bullseye finishes. *Max rounds*, from 1 to 50, ends a leg after its last round: the lowest score wins, a tie plays on round by round, the scoreboard shows the round, such as *Round 3/10*, and the caller of the cards and the blueprint *Autodarts: practice caller* name the winner. Choose the rules on the new game screen of the scoreboard, with the new entities *Practice in mode*, *Practice out mode*, *Practice bull mode* and *Practice max rounds*, or with `in_mode`, `out_mode`, `bull_mode` and `max_rounds` of `autodarts.start_game`. The bot opens on the triple 20 with master in and plays the out mode and the bull mode of the leg. `double_in` and `double_out` of the action and the switches *Practice double in* and *Practice double out* keep working as the modes double or straight, and a saved game keeps its rules. Checkouts, the checkout rate and the personal bests count legs with double out that a dart checked out; a leg the round limit decided counts for the legs and sets of the match. Tournaments play straight or double in and out, with master as double. For the new messages of the caller, choose **Re-import blueprint** for *Autodarts: practice caller* on the blueprints page (#272).

### Fixed

- **`npm test` no longer fails at random in `tournament.test.mjs`:** on a slow or busy machine, such as a Linux container with little CPU, `npm test` failed with *tournament.test.mjs left 1 timer running after its cards left the page* and the idle timer of a scoreboard, while it passed on a fast one. The cards of a test stayed on the page for the rest of its file, and the countdown of a waiting tournament redrew a scoreboard of an earlier test every second. When that happened while a later test mocked the timers, the scoreboard cleared its idle timer with the mock, which clears nothing, and the real timer ran on. The cards of a test now leave the page when it ends, so no test runs into the timers of another, and a test that leaves a timer running fails with its own name. The cards on your dashboards were not affected. Thanks to @JoeyAwwad for the report (#106, #294).

## [1.12.4](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.12.3...v1.12.4) (2026-10-14)

### Improved

- **The pictures of the documentation keep up with the cards:** a change of a card shows how its pictures change in about eight minutes instead of twenty, because the pictures now render in three groups side by side. A language whose pictures fail to render no longer keeps the other language's new pictures out of the documentation or out of the comment on the pull request, and new pictures no longer put a diagram that changed in the meantime back to its earlier version. The pictures of the players, their badges, doubles and progress, the leaderboard and the weekly report now show the games of their own group, so their numbers change once (#259, #269).

### Fixed

- **The highlight photo hands on only photos that were saved:** with a camera entity that was still disabled, as every board camera starts, with a camera that was unavailable, or when the board sent no picture, the highlight photo still gave your actions a `photo` and a `photo_url` of a file that was never written. The notification on your phone then showed a broken picture instead of the live one, and the gallery silently missed the moment. The blueprint now saves the photo with the new action `autodarts.save_highlight`, for administrators and automations, which answers only for a file that is on disk and otherwise says in the log why there is none; `photo` and `photo_url` then stay empty, so `photo_url or image` shows the live picture. `photo_url` now comes from the media folders Home Assistant really has, so it opens the photo wherever the media folder is, and a folder outside them gets none. The *Folder* setting is empty by default now, for the gallery wherever the media folder is: on a Home Assistant Core installation, the earlier default `/media/autodarts/highlights` saved nothing. Two photos of the same second with the same name, from two cameras, no longer overwrite each other. Choose **Re-import blueprint** in the menu of *Autodarts: highlight photo* on the blueprints page; your automations keep their settings ([highlight photo](docs/automations.md#highlight-photo), [`autodarts.save_highlight`](docs/entities.md#save-a-highlight-photo-homedartssave_highlight), #278, #286).
- **A dart you move is drawn where you put it:** to keep camera jitter off the cards, the visit kept a dart where it was as long as it stayed in its bed. A dart you moved within its bed, by tapping its spot on the board of the pad or with `autodarts.correct_dart` and a position, stayed at its old spot on the card, and when the board took back the first of two darts in one bed, the other one was drawn where the first had been. Only a detected dart that the camera sees move by less than about 1.7 mm now stays where it was; a dart that moved farther, or that you placed in Home Assistant, is drawn at its new spot ([live visit](docs/entities.md#live-visit), #260, #271).
- **A bed in an unknown form no longer stops three sensors:** a bed that the board, or a proxy in front of it, sends as a list or another value that is no text stopped *Detected visit score*, *Last dart* and *Last dart score* with an error in the log. Such a dart now counts without its bed, and the three sensors keep updating ([live visit](docs/entities.md#live-visit), #260, #271).
- **Online matches keep the spelling of names:** the online bridge wrote every player name from Tools for Autodarts in lower case, so the light show and the dart caller cheered for *dennis* after `gameshot_Dennis`. A name now keeps its case, and the name of a player in your profiles comes as the profile spells it, *Dennis* also for `gameshot_dennis`. Like every player name, it no longer contains `{`, `}`, `%` or `#`, which a notification or the file name of a snapshot would render as a template, and is at most 20 characters long ([online matches](docs/online-matches.md#triggers-and-events), #260, #271).
- **The local checks pass after a preview of the website:** once you had set up the preview of the website as the contributing guide describes, or built the website, `bash scripts/check.sh` failed with thousands of ESLint errors, because ESLint checked the JavaScript of MkDocs in `.venv-docs/` and the scripts that the build of the website keeps in `.cache/`. ESLint now skips every folder that Git ignores, and still checks every JavaScript file that Git keeps (#282, #284).
- **Enter sends a score typed on a keyboard:** on the keypad of the scoreboard, Enter pressed the key that had the focus again instead of sending the score typed with a keyboard, and after a score went in, the keys of the keyboard reached nothing at all. Digits typed while the pad asked *Darts for the checkout* went into the score: from 4 left, 4, Enter and 2 sent a visit of 42. The pad now takes the focus when its score view opens and keeps it after every score, Enter sends the score also while a digit of the pad has the focus, and during a question a digit only answers it ([correcting and entering darts](docs/cards.md#correcting-and-entering-darts), #287, #293).
- **The caller calls each visit's own score:** when the screen missed a moment between two visits, such as the takeout of a player who plays alone while a tablet woke up or the connection dropped for a moment, the caller added the visit before to the next one and called a visit of 3 as 143. It now counts every X01 visit from the score it started from, as the integration says, and also calls a visit that it first saw with two darts in it ([caller](docs/scoreboard.md#the-caller), #287, #293).
- **A scoreboard you come back to calls no old results:** back on the view of the scoreboard, or when the connection to Home Assistant returned, the caller announced what had happened meanwhile, such as *Game shot, and the match, Alex!* with confetti for a match that ended minutes before. The scoreboard now follows the game from the states it finds on its return, and calls and celebrates only what happens after it (#287, #293).
- **Both winners of a team match carry the trophy:** the panel *Last match* of idle mode crowned one partner of the team that won, such as Alex but not Kim after Alex and Kim beat Sam and Tom, while the players card crowned both. Now both carry the trophy there too ([idle mode](docs/cards.md#idle-mode), #287, #293).

### Documentation

- **Every guide reads well on a phone:** the guides to the cards, the games and the scoreboard set their pictures side by side in tables, which the GitHub app and a phone squeezed into narrow columns, with pictures of 90 to 164 pixels. Each picture now has a sentence that says what it shows and sits at full width below it, in English and German, as in the README (#277, #279).

## [1.12.3](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.12.2...v1.12.3) (2026-10-13)

### Improved

- **A hand at the board updates only the motion sensors:** the motion the detection sees, a hand at the board or a takeout, changes several times per visit, and every change updated all of a board's more than a hundred entities and worked out the training and the statistics of the players again: about 4 ms on a desktop, several times as long on a Raspberry Pi, each time between two darts. It now updates the motion sensors alone, in under a tenth of a millisecond, and cameras that start or stop update *Cameras active* alone. An update of every entity does less work too: the training sensors and *Last match* reuse what the board already worked out instead of working it out again each. The integration also no longer depends on internals of Home Assistant that any update of Home Assistant could change and so make every board unavailable. The diagnostics list the motion, the cameras, the frame rates and the load of the board PC under `local_readings` ([data updates](docs/how-it-works.md#data-updates), #266).
- **The cards load four times faster on a slow connection:** every phone, tablet and browser downloaded the file with all the cards, 590 KB, as it was, on its first visit and after every update of the integration. It now comes compressed, about 150 KB, so the cards and the automatic dashboard appear sooner, above all on a phone with an empty cache or slow Wi-Fi (#243).

### Fixed

- **A card you left lets go of its timers:** Home Assistant can still update a card after you left its dashboard or view. A scoreboard then started the countdown to the next match of a tournament again, and nothing stopped it, so the card went on redrawing itself every second in the background. The scoreboard and the live card also started the time their match summary shows, and the training card opened its history stream again and kept it open. A card now starts its timers and its stream only while it is on the page, and starts them again when you come back (#241).
- **Assist understands "and the bot" and says why it refused a sentence:** "Play 501 for Alex and the bot" started a game for Alex, "the", "bot" and the bot, and Assist answered *Game on: 501 with Alex, the, bot and the bot.* The bot at the end of the players, as in "Spiele 501 für Alex und den Bot", is now the bot. Nine players, a name longer than 20 characters or a game of 70 characters made Assist answer *Done* while Home Assistant logged an error; Assist now says what was wrong, such as *This game takes 4 players at most*. When Home Assistant itself refuses, for a board it does not know, Assist says its message in the language of Home Assistant instead of a key such as *service_config_entry_not_found*. The guides also showed numbers in words that Assist does not know: it understands digits in every language, and words written out in full in the language of Home Assistant, such as "one hundred forty" or "einhundertvierzig", but not "one hundred and forty" or "hundertvierzig". `autodarts.start_game` now keeps the players for an empty list of names, as a cleared field sends it, where it failed. Home Assistant keeps a copy of a blueprint you imported, so for the bot and the corrected descriptions choose **Re-import blueprint** in the menu of *Autodarts: start a game by voice* and *Autodarts: enter darts by voice* on the blueprints page; your automations keep their settings (#253).
- **`npm test` names a test that hangs:** a test that never ends fails after 60 seconds with its name, and a test file that renders the cards and leaves a timer running fails with its name and what the timer calls, instead of keeping `npm test` running for ever. Thanks to @JoeyAwwad, whose report of a hanging `tests/frontend/tournament.test.mjs` led there (#106, #241).
- **An undone visit takes back its personal bests:** a 180 that the board misread, that you undid and corrected to 140 stayed your highest visit for good, and an undone checkout kept its highest checkout and fewest darts. The personal bests now go back with the visit, like the statistics and the weekly report; its darts still count for the day, the streak and the daily goal.
- **A pass counts like a turn with darts:** passing the last turn of a party game, such as the last round of Count-Up, ended the match, but the weekly report, the players' progress and the training calendar missed its leg and match. They count now, as after a turn with darts.
- **Party matches of five to eight players are kept:** the training calendar and the export left them out, so they were lost once 20 newer matches pushed them out of the player profiles. They are kept now, the CSV of matches has columns up to `player_8_points`, and the ones still in the player profiles come back into the calendar.
- **One name, one player:** *Practice player N* took a name that another player already had, in another case, such as Alex and alex, and that player then played against themselves in the profiles. It now refuses a name that another player in the game has, as `autodarts.start_game` does, while a player slot outside the game gives the name up. The profiles count a player in two seats once and drop the head-to-head records against themselves that earlier versions stored.
- **Deleting a player updates the weekly report:** after `autodarts.delete_player`, the *Weekly report* sensor kept showing the deleted name in last week's personal bests until it changed for another reason.
- **Every bust goes in as its score:** a visit entered as its score, on the keypad or with `autodarts.enter_visit`, was refused as impossible when no visit could throw all of it before the bust, such as 100 with 32 left, or when it was what the player had left but no double could finish it, such as 159 with double out, although the keypad had just said *Bust*. Such a score now busts: the player keeps the score from before the visit, and the next player throws. The darts after the dart that busts don't count, and neither do their darts at a double. A checkout where none exists, such as `checkout: true` on 159, is still refused, now with a message that says no visit checks it out (#232).
- **The keypad offers only scores a visit can make:** no three darts score 163, 166, 169, 172, 173, 175, 176, 178 or 179. Typed on the keypad, such a score said what it would leave, and OK sent it only to fail with an error. It now says *No visit scores 179*, and OK and the Enter key wait for another score. The same goes for a score the rules don't allow from where the player stands, such as 180 before the opening double with double in, or 180 from 60 without double out, whose first treble 20 checks out (#232).
- **Unloading a board leaves no repair notices behind:** a read of the board that was still under way when you disabled or reloaded the board finished afterwards and could bring back a notice such as *Autodarts board address points to a different board*, *Calibrate the Autodarts board* or *Autodarts board found at a new address* for a board that was no longer loaded. The notice stayed until the board was loaded again, its fix ended with *The board is not loaded*, and the log showed *Error fetching autodarts_local data*. The unload now waits for that read and discards its answer before it removes the notices, and a board that fails to unload keeps them.
- **The light show keeps a stopped board stopped:** with *Pause the detection during effects*, a training session that ended with a new best session average turned the detection on again after the effect, because the light show paused the detection that the training session routine was stopping and then started it again; the cameras then kept running after the session. The same happened when a session ended while the effect of a won match played. A new best session average no longer pauses the detection, and a session that ends during an effect ends the effect at once: the lights come back, and the detection stays off. A new session lets the effect play to its end and starts the detection again ([light show](docs/automations.md#light-show-with-wled-and-other-lights), #247, #252).
- **Automatic detection stops after a restart, too:** the blueprint *Start and stop detection automatically* lost its waiting when Home Assistant restarted or when you saved the automation, so a detection that was waiting for its stop ran on, overnight included. If nobody is there and the detection runs when Home Assistant starts, it now stops after *Stop after*; saving the automation starts the wait over, also the wait after a restart, while a detection you started by hand keeps running then (#247, #252, #265).
- **The board alert warns about a problem at startup:** the blueprint *Board problem alert* never warned about a board that was offline, or had a camera problem, when Home Assistant started, and saving the automation during a grace period swallowed that alert. Both now alert after the grace period, also when you save the automation more than once before the alert; saving other automations changes nothing (#247, #252, #265).

### Documentation

- **The README reads well on a phone:** on GitHub, in its app and in HACS, every feature had a narrow column of text next to a tiny picture. Each feature now has a few short points with its picture at full width below them, the quick start in three steps follows the first animation, and the longer lists, the blueprints and the guides open with a tap. The overviews of the documentation on GitHub, in English and German, follow the same layout (#268, #270).

## [1.12.2](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.12.1...v1.12.2) (2026-10-12)

### Fixed

- **The automatic dashboard opens on a slow phone too:** Home Assistant waits five seconds for the dashboard strategy of the integration, and on a phone with an empty cache or slow Wi-Fi the file with all the cards took longer, so the automatic dashboard showed *Error loading the dashboard strategy: Timeout waiting for strategy element* until the page was loaded again. A small file of its own now registers the strategy at once and builds the dashboard as soon as the cards are there.

## [1.12.1](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.12.0...v1.12.1) (2026-10-10)

### Fixed

- **Nothing jumps after a tap:** on a phone, choosing a game far down the new game screen scrolled the page back up, so the next one had to be scrolled to again. In Safari, as in the Home Assistant app on an iPhone, the page jumped to its top; in every browser the rules of the game chosen before left above the tapped game and moved it away from the finger. A tapped button now stays where it is, on every card: the same jump hit *All badges* of the players card and the calibration of a camera on the status card in Safari. The heatmap's choice of whose darts and *All badges* keep the focus of a keyboard too.

## [1.12.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.11.0...v1.12.0) (2026-10-09)

### New

- **Darts by voice:** the new blueprint *Enter darts by voice* enters the darts of a game when you tell Assist, as at a dart machine: the score of a visit, such as "Alex hat 140" or "140 points", a checkout, such as "Checkout mit zwei Darts", a single dart, such as "Triple 20" or "Fehlwurf", "Next player" and "Undo", in English and German. Assist answers in the words of the scoreboard's caller: "140 for Alex, 361 left. Sam, you require 501." A sentence that names a player who is not at the board is refused, so a misheard visit never counts for the wrong player ([blueprint](docs/automations.md#enter-darts-by-voice)).
- **Answers of the actions at the board:** `autodarts.enter_visit`, `autodarts.throw_dart`, `autodarts.next_player` and `autodarts.undo_visit` answer with `response_variable` in words instead of failing, as `autodarts.start_game` does: what a visit scored and left and who throws next, the bed of a dart, the leg or the match, a visit taken back, or why they refused. `autodarts.enter_visit` takes `checkout: true` for a visit that checks out what the player has left, and both it and `autodarts.throw_dart` take `player`, which refuses the entry while another player is at the board ([actions](docs/entities.md#enter-a-visits-score-homedartsenter_visit)).

### Documentation

- The page about security lists `autodarts.enter_visit` among the actions a login can call.

## [1.11.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.10.0...v1.11.0) (2026-10-09)

### New

- **Play without Autodarts:** any dartboard can be set up as a board of its own, under *Dartboard without Autodarts: enter every dart yourself*. Its darts are entered on the keypad, which the live card and the scoreboard show without an option to switch on, and every game, the training sessions and all statistics work as with Autodarts. It has the entities of the games, without detection, cameras or a board PC, and the automatic dashboard leaves out its *Board* view ([guide](docs/without-autodarts.md)).
- **Autodarts later:** *Reconfigure* of a dartboard without Autodarts connects the Autodarts board it got, found on the network or by its address. The dartboard keeps its games, statistics, entity IDs and dashboards, and gets the detection, the cameras and the controls ([how](docs/without-autodarts.md#autodarts-later)).
- **The score of a visit:** in X01, *Score* at the top of the keypad takes a visit as its score, such as 140, instead of its darts, as on a dart machine. A checkout asks for its darts and the darts at a double, a visit that left a double in reach for the darts at it, so the checkout rate stays right; the visit counts for the averages, the 180s and the records, but for no bed. On a narrow pad, such as on a 360 pixel phone, the views of the keypad show icons, so they keep the line of S, D and T. The new action `autodarts.enter_visit` does the same ([how](docs/without-autodarts.md#enter-your-darts), [action](docs/entities.md#enter-a-visits-score-homedartsenter_visit)).
- **The keypad on the live card:** the option `keypad` of the live card shows the scoreboard's keypad below the darts while *Practice manual entry* is on, with *Next player* and *Undo last visit* ([cards](docs/cards.md#live-card)).

### Changed

- **Undo with the keypad:** on the scoreboard, the tile *Last* beside the darts takes the last visit back with the keypad too, as without it, so the keypad keeps the same keys after every visit; on a phone, its keys used to run over their edges in German. The curved arrow of *Last* keeps to its corner, clear of the words and the score, and on a short screen, such as a phone on its side, the score of the visit is as high as the beds of the darts beside it.

## [1.10.0](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.9.2...v1.10.0) (2026-10-08)

### New

- **Party games for up to eight:** Shanghai, Halve-It, Killer, Golf, Baseball and Count-Up take a whole party of up to eight players, on the new game screen, in `autodarts.start_game` and in *Practice players*, with four more name fields; the scoreboard shows them in two rows of four. X01, the Cricket and the training games stay at four ([games](docs/games.md#party-games)).
- **Big moments on the scoreboard:** confetti and a golden glow for a 180, confetti for a game shot and the match, and a glow for a ton and for nine marks in Cricket, on top of the scoreboard without moving anything. `celebrations: false` switches them off ([how](docs/scoreboard.md#during-the-game)).
- **How to play:** the new game screen explains the chosen game in a sentence or two, in every language of the cards, for guests who have never played Halve-It or Killer, with a link to all its rules on the documentation website ([how](docs/scoreboard.md#choose-the-next-game)).
- **Aim hints in Cricket:** as on a dart machine, the chalkboard frames the cells of the player at the board: green where a dart scores, because they have closed the number and somebody still needs it, amber where somebody else has closed it and scores on them. A dart that counted nothing is struck through on the live card and the scoreboard, and a tap or a mouse tells why ([how](docs/games.md#cricket-games)).
- **Wild Mouse:** a fourth Cricket game, also known as Minnesota Cricket. Besides 20 to 15 and the bull, every player closes three doubles, three triples and three in a bed. A dart counts for its number while it is open, otherwise for doubles or triples; the chalkboard has a row for each, the board outlines the next target, and teams, the bot and tournaments play it too. *Three in a bed* on the new game screen, or *Practice Wild Mouse three in a bed*, leaves the bed out ([rules](docs/games.md#wild-mouse)).
- **Free a stuck takeout:** Board Manager 2.0.2 sometimes starts a takeout again on the empty board right after one and keeps it, so darts thrown then are not counted and `takeout_finished` never comes. After ten seconds without darts and without a hand at the board, the integration now resets the board, at most three times in a row, and the takeout ends. The new switch *Free a stuck takeout*, on by default, turns it off; the automatic dashboard shows it with the board settings ([how it works](docs/entities.md#a-takeout-the-board-never-finishes)). Found by @JoeyAwwad (#172).

### Fixed

- **The scoreboard's header on a phone:** during a game, the *New game* button, the caller and the status kept to one row wider than the card, which cut off the end of the status, such as *Ready – throw!*, on a small phone in every language and on an iPhone in German and French. Where they do not fit beside each other, they now wrap below the title, and the status still keeps its width, so nothing moves while it changes.

### Documentation

- Animations of Wild Mouse, of the aim hints in Cricket and of a 180 on the scoreboard, pictures of the Wild Mouse chalkboard and of Killer for a party of eight, and diagrams of where a dart counts in Wild Mouse and of how a stuck takeout is freed ([games](docs/games.md#wild-mouse)).
- What changes on the way from Autodarts 1.x to 2.x, as a player reported it: the cameras to choose again in their old order, the first contact with the Autodarts server, the port and the stuck takeout ([troubleshooting](docs/troubleshooting.md#from-autodarts-1x-to-2x)).

## [1.9.2](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.9.1...v1.9.2) (2026-10-08)

### New

- **Betas for testers:** every change for users becomes a beta of the next release within minutes, which HACS offers to those who turn on the switch *Pre-release* of the integration ([how](docs/installation.md#betas-for-testers)).

### Changed

- **Help on the documentation website:** the help links of the cards in the card picker and of the automatic dashboard, and the documentation link of the integration, open the [documentation website](https://dennis-otto.github.io/homedarts-for-autodarts/) instead of GitHub, in German when Home Assistant speaks German.

### Documentation

- The website switches between English and German on every page, with German menus, search and dates, and starts with a page of its own for each language. The German pages moved next to the English ones, such as `docs/games.de.md` next to `docs/games.md`; the old addresses of the German overview and card guide lead there.

## [1.9.1](https://github.com/Dennis-Otto/homedarts-for-autodarts/compare/v1.9.0...v1.9.1) (2026-10-07)

### Fixed

- **Readable badges:** the words under a badge of the players card, such as when it was earned, had too little contrast on the gold of the badge in the dark theme. They now take the muted text of every other card and reach the contrast that WCAG 2.1 AA asks for.
- **The keyboard reaches the scores:** when the pad leaves a full-height scoreboard on a phone too little room, its scores scroll. A keyboard can now reach and scroll them as well, and a screen reader names them *Scoreboard*.

### Documentation

- The accessibility check of the cards, which axe-core runs in the browser test on a laptop and a phone in both themes.

## 1.9.0

### New

- **Start a game by voice:** a new blueprint lets Assist start a practice game, for example "Starte 501 für Alex und Sam", "Start the game Cricket for Alex" or "Spiele 501 gegen den Bot", in German or English. Assist answers with the game and the players, or with what was wrong. Every sentence has a number from 101 to 1001 or the word "Spiel" or "game", so Assist's own commands, such as a timer, stay its own (#123).
- **`autodarts.start_game` understands a voice:** a game by its name in any language of the integration, such as "Around the Clock" or "Doppeltraining", or by the beginning of a name that fits one game alone; a player's name in the spelling of the player's profile; and with `response_variable`, an answer in words to say instead of a failure (#123).
- **Hints on a tap:** what a mouse shows as a tooltip, a tap with a finger or a pen now shows in a small bubble over the card, without moving anything: the darts of a last visit, a visit in the training chart, a trend arrow, a double, the columns of a tournament's table, a camera's dot and the hint of a setup (#122).

### Changed

- **Game settings in a view of their own:** the live view of the automatic dashboard shows the live card alone. The rows of the practice game, its players, start scores and the tournament moved to the new view *Game settings* (#121).

### Documentation

- The voice blueprint with its sentences, the names and the answer of the start action, the new view and the hint building block, in English and German, with the screenshots and animations recorded anew. The example of an automation of your own no longer catches "start a timer for 5 minutes".

## 1.8.1

### Fixed

- **Nothing moves while a game goes on:** the scoreboard's tiles grew and shrank with what they showed: the average after the first dart, a route or a setup that took another line on a narrow tile, the points under a thrown dart, and *Undo last visit* as a row of its own after every takeout, which also shrank the numbers of a full-height scoreboard. Every tile, the visit and the Cricket chalkboard now keep their height from the start of a game to its last dart, on every screen from a 360 pixel phone to a 27 inch monitor, and the new browser step *steady heights* keeps it so (#119).
- **The status** keeps the width of its longest words during a game, so *Remove your darts* no longer pushes the scoreboard's buttons onto another line on a phone.
- **Training games:** the checkout rate and the best show a dash until they are known, and a narrow screen lays the facts out in columns; the live card's training head has a line for the game and one for what it says.

### Changed

- **Undo the last visit:** the tile beside the darts shows the last visit while the board is empty, between games too, with a curved arrow where a tap can take it back; a second tap on the red *Undo?* does it. The button below the visit is gone.
- **Killer notes** are shorter in German, Spanish, French and Dutch, so they fit one line.

### Documentation

- The README's animation is recorded anew with tiles that hold still, and the development guide has the rule that nothing moves during a game.

## 1.8.0

### New

- **Correct darts on the live card:** a tap on a dart of the visit opens the scoreboard's pad below the darts, with its keys, its board, the loupe and the zoom. A pencil at the top right marks every dart a tap corrects. The new option `corrections` switches it off.
- **Loupe and zoom on touch screens:** on a small screen, the board of a correction opens zoomed in on where the board saw the dart. A finger held on the board shows a loupe above it and sets the dart where it lets go; two fingers zoom and move the board. A round magnifier switches between the zoomed part and the whole board. The loupe and the fingers work on every touch screen, a 24 or 27 inch touch monitor too.
- **Every double hit counts:** the doubles card counts every double any dart hits, in every game and in plain training, next to the rate where darts were aimed at a double. The doubles sensor carries them as `landed`.

### Improved

- **Phones, tablets and touch monitors:** every card fits and reads well from a 360 pixel phone to a 27 inch touch monitor, upright and on its side. The full-height scoreboard stays one screen high, the board to tap fills the room the scores leave, keys grow on large screens, and every control is at least 40 pixels for a finger on any touch screen, also with a mouse plugged in.
- **Clear at a glance:** a pencil shows what a tap edits, an arrow what a tap opens; static parts such as the player tiles, the visit's total, the status and the beds of a route no longer look like buttons. The second tap that confirms is red on every card, the pad says why it waits while the bot throws, and the new game screen says why a player sits out. States change with calm animations, and not at all where the device asks for less motion.
- **The badge gallery** shows each player's badges earned and the three nearest goals; *All 18 badges* opens the rest.
- **Trends** run on through weeks without darts, and a figure without two halves to compare shows no arrow.
- **Grids** keep a tile from standing alone in a last row: four players stand two by two rather than three and one.

### Fixed

- **The scoreboard on a phone** was cut off at the bottom, and the new game screen's start bar showed what scrolled beneath it.
- **The positions heatmap** drew darts that landed beside the board; only darts on the board show (#112).
- **The doubles card** stayed empty after a game with doubles in it.
- **On a phone on its side,** the board to tap was only 160 pixels high, and a zoomed board drew over the keys.
- **A finger on the board to tap** could outlast a pad that closed under it, and later boards no longer redrew.

### Changed

- **Shorter entity names** where Home Assistant's rows cut them: *Distortion correction* instead of *Automatic distortion correction* in every language, and in German *Übungsspiel neues Match*, *Übungsspiel neues Leg* and *Turnier Dauer der Zusammenfassung*. Existing entity ids stay; a new installation names the distortion switch `switch.<board>_distortion_correction`.
- **Taps that opened details unannounced:** the training card's tiles open nothing any more, *Details* below them does; the live card's board is a picture. The status card's own calibration reads *Calibrate all*.

### Documentation

- The loupe, the zoom and touch monitors, correcting on the live card with a new animation, and the UI building blocks in the development guide.

## 1.7.1

### Fixed

- **No error in the log when Home Assistant restarts:** a board poll that started after Home Assistant had closed its connections logged *Unexpected error fetching autodarts_local data* with a traceback. It now counts as an ordinary lost connection, like the event stream, the camera stream and the cloud requests. Reported by @JoeyAwwad in #107.
- **Board settings show at once:** with Board Manager 1, a setting switched on or off, such as *Auto distortion*, could show its old value for up to 30 seconds when a poll was reading the settings at that moment.

### Documentation

- **Autodarts Desktop on Linux** is listed under the supported devices: a player reported version 2.0.2 on Ubuntu 24.04 working with every feature (#105). Autodarts Desktop on Windows is still untested; a compatibility report helps.

## 1.7.0

### New

- **Where a corrected dart really is:** the scoreboard's pad has a new *🎯 Board* view. Tap the spot where the dart is, and the bed and the position come in one step; a dashed ring shows where the board saw the dart. The keypad for darts entered by hand uses it too. `autodarts.correct_dart` and `autodarts.throw_dart` take the position as `x` and `y`, and the bed follows from it.

### Improved

- **Live dart positions:** the positions heatmap of the training card shows the darts of the current visit the moment they land, as blue pins, and loads the logged darts again as soon as you pull them, instead of a visit later.
- **Clean positions after corrections:** where the board misread a bed, it misread the spot as well. A dart corrected into another bed therefore leaves the board's position behind and stays out of the dart positions, the grouping and a bull-off by distance, unless the correction says where the dart is.

## 1.6.0

### New

- **More games:** Cut-Throat Cricket and Tactics; the party games Golf (9 or 18 holes), Baseball and Count-Up; the training games 121 checkout, Catch 40, JDC Challenge and singles training.
- **Handicap and teams:** every player can start X01 from a score of their own, and four players play X01 or a Cricket game as two teams of two.
- **Tournaments** for three to eight players at one board: a round robin with a table or a knockout with a bracket, in X01 with start scores or a Cricket game; the next match starts by itself, the results go into the player profiles, and `autodarts.start_tournament`, `autodarts.next_tournament_match` and `autodarts.stop_tournament` run them from automations.
- **Match summary:** after an X01 or Cricket match, the scoreboard and the live card show every player's averages, checkout rate, highest checkout, 180s and best leg; `match_won` carries the numbers, and the winner's banner names the result, such as 3 : 2.
- **A bot** to play X01 and the Cricket games against, from level 20 to 120: it aims like a player, its darts land with a scatter calibrated to its 3-dart average and show on the cards, and it never counts in your statistics. Seat it on the new game screen, with *Practice bot level* or with `bot_level` of `autodarts.start_game`.
- **Corrections and darts entered by hand:** a tap on a dart of the scoreboard, or `autodarts.correct_dart`, corrects a dart the board read wrong; with *Practice manual entry*, a keypad or `autodarts.throw_dart` enters darts the board missed; `autodarts.next_player` passes the turn, and `autodarts.undo_visit` takes the last visit back, with the new `visit_undone` event.
- **Setup hints:** where the darts left cannot check out, the cards, `turn_changed` and the callers suggest a setup that leaves a good double, such as T20 T20 S17 to leave 32.
- **Achievements** in bronze, silver, gold and platinum, from the first 180 to a nine-darter, with the `achievement_unlocked` event and badges on the players card.
- **Player progress:** twelve weeks of trends per player, a heatmap of the real dart positions for the session or any player, the grouping of the darts in millimeters, and a new leaderboard card with the records of all players.
- **A game lobby on the scoreboard:** a new game screen to choose the game, the players and the format at the board, idle mode with a leaderboard, personal bests, today's darts, the last match and a clock, and the pictures of players linked to persons of Home Assistant with `autodarts.link_player` and `autodarts.unlink_player`.
- **Reports:** a weekly report with its sensor, the `weekly_report` event and a blueprint; a training calendar of the last 365 days; `autodarts.export` and an export button on the players card for CSV or JSON.
- **Highlights and light:** a highlight gallery in the media browser, fed by the highlight photo blueprint, and a new light show blueprint for WLED and room lights.
- **Online matches** *(experimental)*: an optional bridge brings busts, won legs and matches and the darts of opponents on play.autodarts.io into Home Assistant through the browser extension Tools for Autodarts.
- **Dutch, French and Spanish:** the integration, the cards and the caller speak three more languages.
- **Events in time:** `visit_thrown` announces a visit the moment its third dart lands; dart and visit events name the game and the player.
- **Bull-off by distance:** optionally, the measured distance also decides between two darts in the same bull bed. The scoreboard shows the bed and the distance of every dart and who leads.
- **Double out from the next leg:** switching double out during a leg applies from the next leg, so no leg becomes unwinnable.

### Improved

- **Official rules:** the throw alternates within a set and every set starts with the next player, as in PDC set play; a match ends 3–2 instead of losing the legs of the deciding set; checkout routes follow the professional charts; highest checkout and fewest darts count only legs with double out; Killer and Shanghai follow their rules in every detail.
- **Cards:** Home Assistant's own editor forms with color pickers, an editor for the automatic dashboard, personal bests on the training card, numbers, dates and times in the formats of your profile, a caller that calls only what counts, and better keyboard and screen reader support.
- **Connection:** visits and entities survive short connection faults; realtime reconnects with a back-off; a board that is off at the start no longer blocks the setup; repairs for a board that refuses access, answers in an unknown format or moved to a new address.
- **Entities:** clearer names without a repeated "Board", diagnostic and configuration categories where they belong, and complete diagnostics without player names.
- **Safe statistics:** a board whose stored training cannot be read right now, or was saved by a newer version, waits instead of starting empty, so its data is never overwritten. Every leg and visit counts once in the statistics, undo also rewinds the progress, the weekly report and the calendar, and in a team match only the player who checks out gets the checkout.
- **Rules:** Golf counts a double as a hole in one and a triple as two strokes; in the checkout training, the 121 checkout and Catch 40 a bust voids only its visit, the 121 checkout plays every score up to 170, and Catch 40 scores 3 points for 99 in three darts; Cut-Throat Cricket checks the win after every dart; a tournament hands the practice game its players and settings back when it ends; the bot plays Cricket at the marks per round of its level.
- **Scoreboard:** fits every screen, with the pad and the keypad beside the scores on a full-height screen in landscape; starting a game in the lobby also starts the detection; the automatic dashboard sets the scoreboard's caller, keypad, corrections, lobby games and idle panels without taking control; the training card's chart follows the history live, and an undone visit leaves it.
- **Actions and security:** deleting, linking and exporting the players' data are administrator actions, which automations still run; exports go to the media folder by default, only to folders where Home Assistant allows writing and at most 20 an hour; a board found at a new address moves only after you confirm a repair; the highlight gallery shows small thumbnails; invalid values of an action get a message in your language.
- **Quieter entities:** *Last event* and *CPU usage*, which change all the time, start disabled on boards set up from now on.
- **Blueprints:** the visit score and the light show leave the bot out unless you turn on *Also for the bot*, and the callers and the light show name it "Bot" like the scoreboard; the highlight photo hands the saved photo to your notification as `photo_url`; the light show keeps up to nine moments waiting behind an effect, reacts to the takeout only when you ask, and never pauses the detection in the middle of a visit; player names never become templates.
- Brand icons and logos in the sizes of the Home Assistant brand specification.

### Documentation

- A new structure with illustrated guides for [games and rules](docs/games.md), the [scoreboard at the board](docs/scoreboard.md), [statistics and players](docs/statistics.md) and [online matches](docs/online-matches.md), a [glossary](docs/glossary.md) in English and German and an accessibility section in the card guide.
- A new README for HACS, with an animation of the live card and the scoreboard and a feature overview; many new screenshots and animations, and a demo with four weeks of long-term statistics.

### Quality

- 100 % line and branch coverage of the integration and DOM tests of every card element; an end-to-end test against Home Assistant 2026.8.0, the oldest supported release.
- CodeQL also checks the card JavaScript; releases are published only with their signed package attached.
- Community files: security policy with response times, support routes, Discussions, governance and contributor tooling.

## 1.5.0

- Shanghai, Halve-It and Killer for one to four players; X01 from 101 to 1001 with double in and a bull-off.
- Player profiles with statistics and personal bests per name, a match history, head-to-head records and a players card.
- A doubles analysis with the hit rate of every double, a doubles card and personal checkout routes.
- A caller in the scoreboard that announces the game through the browser, off by default.

## 1.4.0

- Cricket for one to four players with marks, closed numbers, points and marks per round, and a chalkboard in the live card.
- A scoreboard card and a full-screen scoreboard view for a screen at the board.
- Personal bests with an event when one is beaten, a training streak in days and a daily goal.
- `autodarts.start_game` starts X01, Cricket or a training game with players, names and format in one action.
- Detection quality: the share of corrected darts, with a repair that recalibrates the board when it rises.

## 1.3.0

- X01 matches for two to four players at one board, with legs, sets, player names and a scoreboard in the live card.
- Training games: Around the Clock, doubles training, checkout training and Bob's 27.
- Practice statistics: first-9 average, checkout rate, doubles rate and legs per day.
- Two blueprints: a practice caller and a highlight photo after a 180 or a checkout.

## 1.2.0

- X01 practice games (301, 501, 701): remaining score, busts, double out, checkout routes and the last 10 legs, with the `bust` and `leg_won` events.
- A practice panel in the live card with the checkout route and the next bed to aim at.
- Live camera streams from Board Manager 2 instead of snapshots.

## 1.1.0

- Training sessions that start with the first dart or on purpose, end after a pause and keep the last 20 sessions.
- The `session_started` and `session_ended` events, and a blueprint that ties light, detection and calibration to a session.
- The last visits in the live card, and the session state and past sessions in the training card.
- Board PC details from Board Manager 2: operating system, processor and detection software.

## 1.0.2

- The repository is now called `Dennis-Otto/ha-autodarts`; GitHub redirects the old address.

## 1.0.1

- Setup no longer offers the cloud link while Autodarts has not issued its client ID; old cloud entries keep working locally.
- Card colors accept valid CSS colors only.

## 1.0.0

- Local realtime connection to Board Manager 1 and 2, with automatic discovery; no Autodarts cloud account needed.
- Controls, board settings, camera health and Board Manager updates.
- Training analytics with hits per bed, a visit history and the `visit_completed` event.
- Three dashboard cards, an automatic dashboard and six blueprints.
- Documentation in English and German.

## 0.4.2 to 0.4.5

Pre-releases that led to 1.0.0.
