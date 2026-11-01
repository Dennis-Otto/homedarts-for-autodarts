"""A strength rating per player, and fair start scores from the averages.

The rating is Elo's: a player who beats a stronger player gains more than one
who beats a weaker one, and what the winners gain, the losers lose, as far as
both move at the same pace. It starts at 1000 and moves fast while it says
little yet, so a new player soon stands where they belong.

A fair start gives every player the score they need to finish with the
strongest player, by the 3-dart averages: half the average, half the score.

Both are plain sums, so the tests can check them without a game. The new game
screen works out the same fair start in `fairStarts` of homedarts-card.js, and
the two read the same cases from tests/fixtures/fair_starts.json in their tests.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Final

START_RATING: Final = 1000.0
# A player rated this much higher is expected to win ten games for each they lose.
SCALE: Final = 400.0
# How far a match moves a rating, by the rated matches the player has played.
K_STEPS: Final = ((10, 40), (30, 24))
K_SETTLED: Final = 16
# The digits a rating keeps.
DIGITS: Final = 1

# The legs of a player's recent average.
RECENT_LEGS: Final = 30
# The lowest fair start score, and the steps of the others.
FAIR_LOWEST: Final = 101
FAIR_STEP: Final = 10


def k_factor(matches: int) -> int:
    """How far one match moves the rating of a player with this many rated
    matches: far at first, and less and less."""
    for below, factor in K_STEPS:
        if matches < below:
            return factor
    return K_SETTLED


def expected(rating: float, other: float) -> float:
    """The share of the games a player is expected to win against another."""
    return float(1 / (1 + 10 ** ((other - rating) / SCALE)))


def rating_changes(
    standing: Mapping[str, tuple[float, int]],
    winners: Collection[str],
    losers: Collection[str],
) -> dict[str, float]:
    """What a match adds to the rating of every player in `standing`, which
    holds each player's rating and rated matches before the match.

    Every winner beats every loser, and these results together weigh as much as
    the one result of two players: partners split what their team wins or loses,
    and players who lost to the same winner have no result against each other.
    Nothing depends on the seats: all of it comes from the ratings before the
    match, in the order of the names. Without a winner or a loser, nothing
    changes.
    """
    results = len(winners) * len(losers)
    if not results:
        return {}
    earned = dict.fromkeys((*winners, *losers), 0.0)
    for winner in sorted(winners):
        for loser in sorted(losers):
            surprise = 1 - expected(standing[winner][0], standing[loser][0])
            earned[winner] += surprise
            earned[loser] -= surprise
    return {
        player: round(k_factor(standing[player][1]) * share / results, DIGITS)
        for player, share in earned.items()
    }


def team_averages(averages: Sequence[float | None]) -> list[float | None]:
    """The average of each of two teams, by seat: seats 1 and 3 play against
    seats 2 and 4. A partner without an average doesn't count."""
    teams: list[float | None] = []
    for team in (0, 1):
        known = [average for average in averages[team::2] if average]
        teams.append(sum(known) / len(known) if known else None)
    return teams


def fair_starts(game: int, averages: Sequence[float | None]) -> list[int]:
    """Each player's start score in an X01 game, from their averages.

    The strongest player keeps the game's score, shown as 0 as in `start_scores`,
    and so does a player without an average. Everybody else starts from their
    share of it, rounded to 10 and at least 101.
    """
    top = max((average for average in averages if average), default=0.0)
    return [_fair_start(game, average, top) for average in averages]


def _fair_start(game: int, average: float | None, top: float) -> int:
    if not average or average == top:
        return 0
    # Half up, as the card rounds it; round() would round half to even.
    start = int(game * average / top / FAIR_STEP + 0.5) * FAIR_STEP
    start = max(start, FAIR_LOWEST)
    return 0 if start >= game else start
