### Features

- **A rating for every player:** an Elo rating, starting at 1000, says who beats whom. Every match of X01 or a Cricket game between named players from the same start score moves it, partners split the change of their team, and undoing the deciding visit takes it back. The players card shows it, the leaderboard card ranks it, and `match_won` carries `rating_changes`.
- **Fair start scores:** *Fair start* on the new game screen and `fair_start: true` in `homedarts.start_game` work the start scores of an X01 game out from the players' averages of the last 30 legs, so nobody has to guess a handicap. The strongest player keeps the game's score, teams and the bot count too, and − and + still change the scores.
- **A bot at your level:** the bot's row on the new game screen offers *At my level*, which sets the bot to the players' average.

### Fixed

- **Start scores of a team match:** the new game screen sent a start score for every partner, which the action refused. It now sends one per team, and partners show and change one score.
