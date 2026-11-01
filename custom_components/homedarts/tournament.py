"""Tournaments of three to 32 named players, at one board or at several.

A tournament is a series of practice matches between two players at a time:
X01, with a start score of their own for a handicap if wanted, or a Cricket
game. In a round robin everyone plays everyone once and a table ranks the
players; in a knockout the winners go on through a bracket until the final; in
a double elimination a player is out after the second lost match only; with
groups, a round robin in every group sends its best players into a knockout.
When a match ends, its result goes into the table or the bracket, and the next
match starts after the summary of the match and a pause, never while darts of a
visit are on the board. The matches count for the player profiles like any
other match. When the tournament ends, the practice game goes back to its
settings from before, with the next match or the next change of a setting.

A tournament on several boards belongs to the board it was started on, the
first of its boards. Every board plays a match of its own: a board whose pause
is over takes the next match whose players are known and play at no other
board, so the matches of a round run side by side. The players of a match get
the pause after their last match too, wherever they played it. The tournament
forecasts its end from the players' averages and the pace of its matches.
"""

from __future__ import annotations

import random
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .brackets import (
    GRAND_FINAL,
    GRAND_FINAL_RESET,
    GROUP_NAMES,
    KNOCKOUT_STAGES,
    LOSERS_FINAL,
    LOSERS_ROUNDS,
    ROUTES,
    THIRD_PLACE,
    WINNERS_FINAL,
    WINNERS_ROUNDS,
    Match,
    double_knockout,
    enter,
    group_seeds,
    group_stage,
    knockout,
    knockout_plan,
    round_robin,
    shifted,
    snake,
)
from .cricket import CRICKET_GAMES, marks_per_round
from .errors import ActionRefused
from .moments import parse_moment
from .practice import (
    GAMES,
    MATCH_RULES,
    MAX_LEGS,
    MAX_SETS,
    PracticeGame,
    renamed_slots,
    valid_settings,
    valid_start,
)
from .profiles import clean_name, valid_name
from .scoring import BULL_25_50, average, bounded_count

ROUND_ROBIN = "round_robin"
KNOCKOUT = "knockout"
DOUBLE_KNOCKOUT = "double_knockout"
GROUPS_KNOCKOUT = "groups_knockout"
FORMATS = (ROUND_ROBIN, KNOCKOUT, DOUBLE_KNOCKOUT, GROUPS_KNOCKOUT)
# The head-to-head games a tournament plays: X01 and the Cricket games.
TOURNAMENT_GAMES = (*(str(game) for game in GAMES), *CRICKET_GAMES)
MIN_ENTRANTS = 3
MAX_ENTRANTS = 32
# A round robin of more players takes too long at one board: groups play it.
MAX_ROUND_ROBIN = 8
# Groups of three to eight players, two to eight groups, of which one to four
# players each go on into the knockout.
MIN_GROUPS = 2
MAX_GROUPS = len(GROUP_NAMES)
MAX_ADVANCE = 4
DEFAULT_ADVANCE = 2
# Without a number of groups, groups of about this many players.
GROUP_SIZE = 4
# The players every format takes, at least and at most.
ENTRANTS = {
    ROUND_ROBIN: (MIN_ENTRANTS, MAX_ROUND_ROBIN),
    KNOCKOUT: (MIN_ENTRANTS, MAX_ENTRANTS),
    DOUBLE_KNOCKOUT: (MIN_ENTRANTS, MAX_ENTRANTS),
    GROUPS_KNOCKOUT: (MIN_GROUPS * MIN_ENTRANTS, MAX_ENTRANTS),
}
# Seconds between two matches; 0 waits until the next match is started.
DEFAULT_PAUSE = 10
MAX_PAUSE = 600
# Seconds the summary of a match shows before the pause begins, so that the
# table or the bracket with the next match gets the whole pause.
DEFAULT_SUMMARY = 8
MAX_SUMMARY = 60
MAX_SEED = 999_999
# A won match of the round robin is worth two points, as in the Premier League.
WIN_POINTS = 2
# The rules every match of a tournament is played with.
RULES = MATCH_RULES
# A match for third place needs two losing semi-finalists.
THIRD_PLACE_ENTRANTS = 4
# A tournament on several boards plays on two to eight boards at once.
MIN_BOARDS = 2
MAX_BOARDS = 8
# The forecast of the end: a visit takes this many seconds at the board, the
# takeout included, until the tournament has timed enough visits of its own; a
# player without darts yet throws the default average or marks per round; an
# X01 leg takes a visit for the checkout, and Cricket closes 21 marks.
VISIT_SECONDS = 30
TIMED_VISITS = 10
DEFAULT_RATES = {"average": 40.0, "mpr": 1.5}
CHECKOUT_VISITS = 1
CRICKET_MARKS = 21

TOURNAMENT_EVENTS = (
    "tournament_started",
    "tournament_match_finished",
    "tournament_finished",
)
PLAYING = "playing"
WAITING = "waiting"
FINISHED = "finished"
# Eight players play seven rounds of the round robin, in a group too.
MAX_ROUNDS = MAX_ROUND_ROBIN - 1
# The stages the cards name by their key; the numbered rounds they count.
NAMED_STAGES = (
    *KNOCKOUT_STAGES,
    THIRD_PLACE,
    WINNERS_FINAL,
    LOSERS_FINAL,
    GRAND_FINAL,
    GRAND_FINAL_RESET,
)
# The states of the tournament sensor: the stage being played.
STATES = [
    "no_tournament",
    *(f"round_{number}" for number in range(1, MAX_ROUNDS + 1)),
    *KNOCKOUT_STAGES[:0:-1],
    THIRD_PLACE,
    KNOCKOUT_STAGES[0],
    *(f"winners_round_{number}" for number in range(1, WINNERS_ROUNDS)),
    WINNERS_FINAL,
    *(f"losers_round_{number}" for number in range(1, LOSERS_ROUNDS)),
    LOSERS_FINAL,
    GRAND_FINAL,
    GRAND_FINAL_RESET,
    FINISHED,
]

# The draw needs no cryptographic randomness.
_RANDOM = random.Random()
# Earlier than every stored time, for a match without one.
_EPOCH = datetime.min.replace(tzinfo=UTC)


def _shown(due: datetime | None) -> str | None:
    """When a match is due, as the snapshot shows it: no time for a
    tournament stored without its start, whose next match is due at once."""
    return None if due is None or due == _EPOCH else due.isoformat()


def _name(name: str) -> str:
    """A player name as the practice game keeps it."""
    return clean_name(name)


def split_players(text: str) -> list[str]:
    """Names separated by commas, semicolons or new lines, as they were
    written; empty ones are dropped."""
    return [name for name in re.split(r"[,;\r\n]", text) if name.strip()]


def parse_players(text: str) -> list[str]:
    """The names of a list separated by commas, semicolons or new lines, as
    the practice game keeps them."""
    return [name for name in map(_name, split_players(text)) if name]


def check_names(names: list[str]) -> None:
    """Player names must not contain the characters no name contains."""
    if not all(valid_name(name) for name in names):
        raise ActionRefused("invalid_player_name")


def _flag(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _moment(value: object) -> datetime | None:
    """A stored time, in UTC when it names no time zone."""
    moment = parse_moment(value)
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


def _rate(value: object) -> float | None:
    """A 3-dart average or marks per round as stored, or None."""
    if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
        return float(value)
    return None


def _expected(count: int) -> float:
    """How many legs or sets a match to win this many of them takes on average:
    between the count and twice the count less one."""
    return (3 * count - 1) / 2


@dataclass
class Seat:
    """A board of a tournament: the ID of its entry and its name, both empty at
    one board, the match it plays, and for a board other than the first the
    practice settings from before the tournament, to go back to after it."""

    key: str = ""
    name: str = ""
    match: int | None = None
    saved: dict[str, Any] | None = None


@dataclass
class TournamentSetup:
    """The settings of the next tournament, as its entities show them."""

    format: str = ROUND_ROBIN
    game: str = "501"
    players: list[str] = field(default_factory=list)
    third_place: bool = False
    random_draw: bool = False
    # Groups with knockout: the number of groups, 0 for groups of about four
    # players, and how many of each group go on into the knockout.
    groups: int = 0
    advance: int = DEFAULT_ADVANCE
    pause: int = DEFAULT_PAUSE
    summary: int = DEFAULT_SUMMARY

    @classmethod
    def restored(cls, saved: object) -> TournamentSetup:
        data = saved if isinstance(saved, dict) else {}
        players = data.get("players")
        names = [
            _name(name)
            for name in (players if isinstance(players, list) else [])
            if isinstance(name, str)
        ]
        return cls(
            format=data["format"] if data.get("format") in FORMATS else ROUND_ROBIN,
            game=data["game"] if data.get("game") in TOURNAMENT_GAMES else "501",
            players=[name for name in names if name][:MAX_ENTRANTS],
            third_place=_flag(data.get("third_place"), False),
            random_draw=_flag(data.get("random_draw"), False),
            groups=bounded_count(data.get("groups"), MIN_GROUPS, MAX_GROUPS, 0),
            advance=bounded_count(data.get("advance"), 1, MAX_ADVANCE, DEFAULT_ADVANCE),
            pause=bounded_count(data.get("pause"), 0, MAX_PAUSE, DEFAULT_PAUSE),
            summary=bounded_count(data.get("summary"), 0, MAX_SUMMARY, DEFAULT_SUMMARY),
        )


def auto_groups(count: int) -> int:
    """The number of groups for this many players without one given: groups of
    about four players, two at least and eight at most."""
    return min(max(count // GROUP_SIZE, MIN_GROUPS), MAX_GROUPS)


def fits_groups(count: int, groups: int, advance: int) -> bool:
    """Whether this many players make groups of three to eight players, each
    with more players than go on into the knockout."""
    if not (MIN_GROUPS <= groups <= MAX_GROUPS and 1 <= advance <= MAX_ADVANCE):
        return False
    smallest, largest = count // groups, -(-count // groups)
    return (
        smallest >= MIN_ENTRANTS and largest <= MAX_ROUND_ROBIN and advance < smallest
    )


class Tournament:
    """A tournament being played, or finished."""

    def __init__(
        self,
        *,
        format: str,
        game: str,
        players: list[str],
        legs: int,
        sets: int,
        rules: dict[str, bool],
        starts: list[int] | None = None,
        third_place: bool = False,
        groups: int = 0,
        advance: int = DEFAULT_ADVANCE,
        seed: int | None = None,
        started: str | None = None,
        boards: list[tuple[str, str]] | None = None,
        rates: list[float | None] | None = None,
    ) -> None:
        self.format = format
        self.game = game
        # The names in the order of the draw, and the X01 start score of every
        # player: 0 for the game's, another one for a handicap.
        self.players = list(players)
        count = len(players)
        self.starts = [
            start if valid_start(start) and game.isdigit() else 0
            for start in [*(starts or []), *[0] * count][:count]
        ]
        self.legs_to_win = legs
        self.sets_to_win = sets
        self.rules = dict(rules)
        # The players of every group, and the group and the place in it of
        # every seed of the knockout after the groups.
        self.groups = snake(count, groups) if format == GROUPS_KNOCKOUT else []
        self.advance = advance if self.groups else 0
        self.seeding = group_seeds(groups, advance) if self.groups else ()
        knockout_players = len(self.seeding) if self.groups else count
        self.third_place = (
            third_place
            and format in (KNOCKOUT, GROUPS_KNOCKOUT)
            and knockout_players >= THIRD_PLACE_ENTRANTS
        )
        self.seed = seed
        self.started = started
        self.ended: str | None = None
        self.status = PLAYING
        # The boards that play the matches, the first one the tournament's own,
        # and the averages or marks per round of the players' profiles at the
        # start, for the forecast.
        self.seats = [Seat(key, name) for key, name in boards or [("", "")]]
        given = list(rates or [])
        self.rates = [_rate(rate) for rate in [*given, *[None] * count][:count]]
        if format == ROUND_ROBIN:
            self.matches = round_robin(count)
        elif format == KNOCKOUT:
            self.matches = knockout(count, self.third_place)
        elif format == DOUBLE_KNOCKOUT:
            self.matches = double_knockout(count)
        else:
            stage = group_stage(self.groups)
            later = knockout_plan(knockout_players, self.third_place)
            self.matches = [*stage, *shifted(later, len(stage))]
        for index in range(len(self.matches)):
            self._settle(index)
        first = self.upcoming()
        assert first is not None
        self.begin(first, 0, started)

    @property
    def several(self) -> bool:
        """Whether the tournament plays on several boards."""
        return len(self.seats) > 1

    @property
    def kind(self) -> int | str:
        """The game as the practice game names it: 501 or cricket."""
        return int(self.game) if self.game.isdigit() else self.game

    @property
    def rounds(self) -> int:
        return max(match.round for match in self.matches)

    def upcoming(self) -> int | None:
        """The match to play next: the first one whose players are known."""
        return next(
            (index for index, match in enumerate(self.matches) if match.ready), None
        )

    def last_played(self, board: int | None = None) -> int | None:
        """The match that ended last, of all or at a board; of two that ended
        at the same time, the later one in the order of play."""
        played = [
            index
            for index, match in enumerate(self.matches)
            if match.played and (board is None or match.board == board)
        ]
        return max(
            played,
            key=lambda index: (_moment(self.matches[index].ended) or _EPOCH, index),
            default=None,
        )

    def free_for(self, board: int, index: int) -> bool:
        """Whether a board can take this match: its players are known, and no
        other board plays it or another match of them."""
        match = self.matches[index]
        if not match.ready:
            return False
        for number, seat in enumerate(self.seats):
            if number == board or seat.match is None:
                continue
            if seat.match == index or not set(match.players).isdisjoint(
                self.matches[seat.match].players
            ):
                return False
        return True

    def next_for(self, board: int) -> int | None:
        """The match a board plays next: the first one it can take."""
        return next(
            (
                index
                for index in range(len(self.matches))
                if self.free_for(board, index)
            ),
            None,
        )

    def begin(self, index: int, board: int, at: str | None) -> None:
        """A board takes a match."""
        match = self.matches[index]
        self.seats[board].match = index
        match.started = match.started or at
        if self.several:
            match.board = board
        self.refresh()

    def refresh(self) -> None:
        """The status of a tournament still being played, after a board took
        a match or ended one."""
        busy = any(seat.match is not None for seat in self.seats)
        self.status = PLAYING if busy else WAITING

    def rested(self, index: int, board: int) -> datetime | None:
        """When the board and the players of a match last ended a match."""
        players = set(self.matches[index].players)
        ends = [
            moment
            for match in self.matches
            if match.played
            and (
                not self.several
                or match.board == board
                or not players.isdisjoint(match.players)
            )
            and (moment := _moment(match.ended)) is not None
        ]
        return max(ends, default=None)

    def names(self, match: Match) -> list[str | None]:
        return [
            None if player is None else self.players[player] for player in match.players
        ]

    def _stage(self, stage: str) -> Match:
        return next(match for match in self.matches if match.stage == stage)

    def _settle(self, index: int) -> None:
        """A bye goes on as soon as its player is known."""
        match = self.matches[index]
        if match.bye and match.winner is None and match.players[0] is not None:
            match.winner = match.players[0]
            self._advance(index)

    def _advance(self, index: int) -> None:
        """The winner of a match goes on, and so does the loser where losers
        play on: in the match for third place and the losers' bracket. The
        last match of the groups draws the knockout after them."""
        match = self.matches[index]
        if match.stage == GRAND_FINAL:
            assert match.winner_to is not None
            self._decide(match, self.matches[match.winner_to[0]])
            return
        for target, player in (
            (match.winner_to, match.winner),
            (match.loser_to, match.loser),
        ):
            if target is not None and player is not None:
                self.matches[target[0]].players[target[1]] = player
                self._settle(target[0])
        if match.group is not None and all(
            other.played for other in self.matches if other.group is not None
        ):
            tables = [self._ranked(group) for group in range(len(self.groups))]
            qualifiers = [tables[group][place] for group, place in self.seeding]
            for entered in enter(self.matches, qualifiers):
                self._settle(entered)

    @staticmethod
    def _decide(final: Match, reset: Match) -> None:
        """The winner of the winners' bracket wins the grand final, and with it
        the tournament; else both players have lost once, and the second grand
        final decides."""
        if final.winner == final.players[0]:
            reset.players, reset.winner = [final.winner, None], final.winner
        else:
            reset.players, reset.bye = list(final.players), False

    def record(self, index: int, practice: PracticeGame, ended: str) -> None:
        """The result of the practice match that just ended."""
        match = self.matches[index]
        assert practice.winner is not None
        players = practice.players
        match.winner = match.players[practice.winner]
        match.legs = [player.match_legs for player in players]
        match.sets = [player.sets for player in players]
        match.points = [player.match_points for player in players]
        match.marks = [player.match_marks for player in players]
        match.darts = [player.match_darts for player in players]
        match.ended = ended
        self._advance(index)

    # -- results ---------------------------------------------------------------

    def _averages(self, scored: list[int], darts: list[int]) -> list[float | None]:
        """3-dart averages in X01, marks per round in Cricket."""
        rate = marks_per_round if self.game in CRICKET_GAMES else average
        return [rate(part, count) for part, count in zip(scored, darts, strict=True)]

    @property
    def _statistic(self) -> str:
        return "mpr" if self.game in CRICKET_GAMES else "average"

    def _scored(self, match: Match) -> list[int]:
        return match.marks if self.game in CRICKET_GAMES else match.points

    def _table(self, group: int | None = None) -> list[tuple[int, dict[str, Any]]]:
        """The table of the round robin or of a group, with the place of every
        player in the draw: points, then the points of the matches among the
        players level on points, the leg difference, the average and the order
        of the draw."""
        members = (
            list(range(len(self.players))) if group is None else self.groups[group]
        )
        won, lost, legs_for, legs_against, scored, darts = (
            dict.fromkeys(members, 0) for _ in range(6)
        )
        played = [
            match for match in self.matches if match.played and match.group == group
        ]
        for match in played:
            for side, player in enumerate(match.players):
                assert player is not None
                won[player] += int(player == match.winner)
                lost[player] += int(player != match.winner)
                legs_for[player] += match.legs[side]
                legs_against[player] += match.legs[1 - side]
                scored[player] += self._scored(match)[side]
                darts[player] += match.darts[side]
        points = {player: wins * WIN_POINTS for player, wins in won.items()}
        averages = dict(
            zip(
                members,
                self._averages(
                    [scored[player] for player in members],
                    [darts[player] for player in members],
                ),
                strict=True,
            )
        )

        def among(player: int) -> int:
            level = {other for other in members if points[other] == points[player]}
            return sum(
                WIN_POINTS
                for match in played
                if match.winner == player and match.loser in level
            )

        def rank(player: int) -> tuple[int, int, int, float, int]:
            value = averages[player]
            return (
                -points[player],
                -among(player),
                legs_against[player] - legs_for[player],
                -(value if value is not None else -1.0),
                player,
            )

        return [
            (
                player,
                {
                    "position": position,
                    "name": self.players[player],
                    "played": won[player] + lost[player],
                    "won": won[player],
                    "lost": lost[player],
                    "legs_for": legs_for[player],
                    "legs_against": legs_against[player],
                    "leg_difference": legs_for[player] - legs_against[player],
                    "points": points[player],
                    self._statistic: averages[player],
                },
            )
            for position, player in enumerate(sorted(members, key=rank), 1)
        ]

    def _ranked(self, group: int) -> list[int]:
        """The players of a group by their place in its table."""
        return [player for player, _ in self._table(group)]

    def standings(self) -> list[dict[str, Any]]:
        """The round robin table."""
        return [row for _, row in self._table()]

    def tables(self) -> list[dict[str, Any]]:
        """The table of every group."""
        return [
            {
                "group": GROUP_NAMES[group],
                "standings": [row for _, row in self._table(group)],
            }
            for group in range(len(self.groups))
        ]

    def podium(self) -> list[str | None]:
        """Winner, runner-up and third of a finished tournament."""
        if self.format == ROUND_ROBIN:
            return [row["name"] for row in self.standings()[:3]]
        if self.format == DOUBLE_KNOCKOUT:
            reset = self._stage(GRAND_FINAL_RESET)
            final = reset if reset.played else self._stage(GRAND_FINAL)
            third = self._stage(LOSERS_FINAL).loser
        else:
            final = self._stage(KNOCKOUT_STAGES[0])
            third = self._stage(THIRD_PLACE).winner if self.third_place else None
        return [
            self.players[player] if player is not None else None
            for player in (final.winner, final.loser, third)
        ]

    # -- state -----------------------------------------------------------------

    def numbers(self) -> dict[int, int]:
        """Matches to play by their place in the order of play, from 1; byes have none."""
        played = [index for index, match in enumerate(self.matches) if not match.bye]
        return {index: number for number, index in enumerate(played, 1)}

    def match(
        self, index: int | None, numbers: dict[int, int]
    ) -> dict[str, Any] | None:
        """A match as the sensor shows it, with its number from numbers()."""
        if index is None:
            return None
        match = self.matches[index]
        result: dict[str, Any] = {
            "match": numbers.get(index),
            "round": match.round,
            "stage": match.stage,
            **({} if match.group is None else {"group": GROUP_NAMES[match.group]}),
            "players": self.names(match),
            "winner": None if match.winner is None else self.players[match.winner],
            "bye": match.bye,
            "legs": list(match.legs),
            "sets": list(match.sets),
            "ended": match.ended,
        }
        if self.several:
            # The board, from 1, that plays or played the match.
            result["board"] = None if match.board is None else match.board + 1
        if match.played:
            result[self._statistic] = self._averages(self._scored(match), match.darts)
        return result

    def after(self, index: int, skip: set[int] | None = None) -> int | None:
        """The match after this one in the order of play, known or not; with
        skip, not one of those, such as the matches of the other boards."""
        return next(
            (
                later
                for later in range(index + 1, len(self.matches))
                if not self.matches[later].bye
                and self.matches[later].winner is None
                and later not in (skip or set())
            ),
            None,
        )

    # -- forecast --------------------------------------------------------------

    def _rates_now(self) -> list[float]:
        """The average or the marks per round of every player: in the
        tournament, else from the profile at its start, else the default."""
        count = len(self.players)
        scored, darts = [0] * count, [0] * count
        for match in self.matches:
            if not match.played:
                continue
            for side, player in enumerate(match.players):
                assert player is not None
                scored[player] += self._scored(match)[side]
                darts[player] += match.darts[side]
        default = DEFAULT_RATES[self._statistic]
        return [
            measured or profile or default
            for measured, profile in zip(
                self._averages(scored, darts), self.rates, strict=True
            )
        ]

    def _visit_seconds(self) -> float:
        """How long a visit takes: as the matches played so far took them, once
        they had enough of them, else the default."""
        seconds, darts = 0.0, 0
        for match in self.matches:
            begun, ended = _moment(match.started), _moment(match.ended)
            if match.played and begun and ended and ended > begun:
                seconds += (ended - begun).total_seconds()
                darts += sum(match.darts)
        visits = darts / 3
        return seconds / visits if visits >= TIMED_VISITS else VISIT_SECONDS

    def _length(self, index: int, rates: list[float], visit: float) -> timedelta:
        """How long a match takes: a leg ends once the faster of its players
        has thrown their score down or closed the board, with as many visits of
        the other one, times the legs and sets a match takes on average. A
        player not known yet throws the mean of all players."""
        match = self.matches[index]
        mean = sum(rates) / len(rates)
        visits = []
        for player in match.players:
            rate = mean if player is None else rates[player]
            if self.game in CRICKET_GAMES:
                visits.append(CRICKET_MARKS / rate)
            else:
                start = (player is not None and self.starts[player]) or int(self.game)
                visits.append(start / rate + CHECKOUT_VISITS)
        legs = _expected(self.legs_to_win) * _expected(self.sets_to_win)
        return timedelta(seconds=legs * 2 * min(visits) * visit)

    def ends_at(self, summary: int, pause: int) -> str | None:
        """When the tournament is expected to end: every match still to play
        on the board that is free first, with the summary and the pause between
        two matches, each as long as the players' averages and the pace of the
        tournament make it. Only stored times go in, so the forecast changes
        with the tournament, not with the clock."""
        start = _moment(self.started)
        if start is None or self.status == FINISHED:
            return None
        gap = timedelta(seconds=summary + pause)
        rates, visit = self._rates_now(), self._visit_seconds()
        ends: list[datetime] = []
        free: list[datetime] = []
        for number, seat in enumerate(self.seats):
            if seat.match is not None:
                begun = _moment(self.matches[seat.match].started) or start
                ends.append(begun + self._length(seat.match, rates, visit))
                free.append(ends[-1] + gap)
                continue
            last = self.last_played(number if self.several else None)
            ended = None if last is None else _moment(self.matches[last].ended)
            ends.append(ended or start)
            free.append(start if ended is None else ended + gap)
        taken = {seat.match for seat in self.seats}
        for index, match in enumerate(self.matches):
            if match.bye or match.winner is not None or index in taken:
                continue
            board = free.index(min(free))
            ends[board] = free[board] + self._length(index, rates, visit)
            free[board] = ends[board] + gap
        return max(ends).isoformat()

    def bracket(self, losers: bool = False) -> list[dict[str, Any]]:
        """The rounds of the bracket with their matches, byes included; the
        match for third place comes after the final. A double elimination has
        the winners' bracket with the grand final, and the losers' bracket on
        its own; the second grand final shows once it is played."""
        stages: list[str] = []
        for match in self.matches:
            if match.group is None and match.stage not in stages:
                stages.append(match.stage)
        if THIRD_PLACE in stages:
            stages = [*(stage for stage in stages if stage != THIRD_PLACE), THIRD_PLACE]
        rounds: list[dict[str, Any]] = []
        numbers = self.numbers()
        for stage in stages:
            if stage.startswith("losers_") != losers:
                continue
            indexes = sorted(
                (
                    index
                    for index, match in enumerate(self.matches)
                    if match.stage == stage
                    and not (stage == GRAND_FINAL_RESET and match.bye)
                ),
                key=lambda index: self.matches[index].slot,
            )
            if indexes:
                rounds.append(
                    {
                        "stage": stage,
                        "round": self.matches[indexes[0]].round,
                        "matches": [self.match(index, numbers) for index in indexes],
                    }
                )
        return rounds

    def views(self) -> dict[str, Any]:
        """The table of a round robin, the bracket of the other formats, the
        losers' bracket of a double elimination and the tables of the groups."""
        if self.format == ROUND_ROBIN:
            return {"standings": self.standings()}
        views: dict[str, Any] = {"bracket": self.bracket()}
        if self.format == DOUBLE_KNOCKOUT:
            views["losers_bracket"] = self.bracket(losers=True)
        if self.groups:
            views |= {"groups": self.tables(), "advance": self.advance}
        return views

    def stored(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "game": self.game,
            "players": list(self.players),
            "starts": list(self.starts),
            "legs_to_win": self.legs_to_win,
            "sets_to_win": self.sets_to_win,
            "rules": dict(self.rules),
            "third_place": self.third_place,
            "groups": len(self.groups),
            "advance": self.advance,
            "seed": self.seed,
            "started": self.started,
            "ended": self.ended,
            "status": self.status,
            "rates": list(self.rates),
            "matches": [
                {
                    key: value
                    for key, value in asdict(match).items()
                    if key not in ROUTES
                }
                for match in self.matches
            ],
            # The boards of a tournament on several boards.
            **(
                {"seats": [asdict(seat) for seat in self.seats]} if self.several else {}
            ),
        }

    @staticmethod
    def _boards(saved: object) -> list[tuple[str, str]] | None:
        """The keys and names of the stored boards of a tournament on several
        boards; None for one board, or for boards that make no sense."""
        if not isinstance(saved, list) or not MIN_BOARDS <= len(saved) <= MAX_BOARDS:
            return None
        if not all(
            isinstance(seat, dict)
            and isinstance(seat.get("key"), str)
            and isinstance(seat.get("name"), str)
            for seat in saved
        ):
            return None
        keys = {seat["key"] for seat in saved}
        if len(keys) < len(saved):
            return None
        return [(seat["key"], seat["name"]) for seat in saved]

    @classmethod
    def restored(cls, saved: object) -> Tournament | None:
        """The stored tournament; the draw is made again and the stored results
        are replayed onto it as far as they fit."""
        if not isinstance(saved, dict):
            return None
        players = saved.get("players")
        if not (
            saved.get("format") in FORMATS
            and saved.get("game") in TOURNAMENT_GAMES
            and isinstance(players, list)
            and ENTRANTS[saved["format"]][0]
            <= len(players)
            <= ENTRANTS[saved["format"]][1]
            and all(isinstance(name, str) and _name(name) for name in players)
        ):
            return None
        groups, advance = saved.get("groups"), saved.get("advance")
        if saved["format"] != GROUPS_KNOCKOUT:
            groups, advance = 0, DEFAULT_ADVANCE
        elif not (
            type(groups) is int
            and type(advance) is int
            and fits_groups(len(players), groups, advance)
        ):
            return None
        rules = saved.get("rules")
        rules = rules if isinstance(rules, dict) else {}
        starts = saved.get("starts")
        seed = saved.get("seed")
        rates = saved.get("rates")
        boards = cls._boards(saved.get("seats"))
        tournament = cls(
            format=saved["format"],
            game=saved["game"],
            players=[_name(name) for name in players],
            legs=bounded_count(saved.get("legs_to_win"), 1, MAX_LEGS, 1),
            sets=bounded_count(saved.get("sets_to_win"), 1, MAX_SETS, 1),
            rules={
                rule: _flag(rules.get(rule), rule == "double_out") for rule in RULES
            },
            starts=starts if isinstance(starts, list) else None,
            third_place=saved.get("third_place") is True,
            groups=groups,
            advance=advance,
            seed=seed if type(seed) is int else None,
            started=saved["started"] if isinstance(saved.get("started"), str) else None,
            boards=boards,
            rates=rates if isinstance(rates, list) else None,
        )
        matches = saved.get("matches")
        for index, stored in enumerate(matches if isinstance(matches, list) else []):
            if not tournament._replay(index, stored):
                break
        for seat in tournament.seats:
            seat.match = None
        if tournament.upcoming() is None:
            tournament.status = FINISHED
            ended = saved.get("ended")
            tournament.ended = ended if isinstance(ended, str) else None
        elif boards is not None:
            tournament._reseat(saved["seats"])
        elif saved.get("status") == WAITING and tournament.last_played() is not None:
            tournament.status = WAITING
        else:
            tournament.seats[0].match = tournament.upcoming()
        # A match no board plays has not begun.
        playing = {seat.match: number for number, seat in enumerate(tournament.seats)}
        for index, match in enumerate(tournament.matches):
            if match.winner is None:
                match.started = match.started if index in playing else None
                match.board = playing.get(index) if tournament.several else None
        return tournament

    def _reseat(self, saved: list[dict[str, Any]]) -> None:
        """The stored matches of the boards, where they fit, and the practice
        settings of the boards to go back to."""
        for number, (seat, stored) in enumerate(zip(self.seats, saved, strict=True)):
            index = stored.get("match")
            if (
                type(index) is int
                and 0 <= index < len(self.matches)
                and self.free_for(number, index)
            ):
                seat.match = index
            if number:
                seat.saved = valid_settings(stored.get("saved"))
        self.refresh()

    def _replay(self, index: int, saved: object) -> bool:
        """A stored result for the match at this place; False where it does not fit."""
        if index >= len(self.matches) or not isinstance(saved, dict):
            return False
        match = self.matches[index]
        if match.bye:
            return True
        winner, ended = saved.get("winner"), saved.get("ended")
        if winner is None:
            self._timed(match, saved)
            return True
        if (
            not match.ready
            or saved.get("players") != match.players
            or winner not in match.players
            or not isinstance(ended, str)
            or parse_moment(ended) is None
        ):
            return False
        for key in ("legs", "sets", "points", "marks", "darts"):
            values = saved.get(key)
            if (
                isinstance(values, list)
                and len(values) == 2
                and all(type(value) is int and value >= 0 for value in values)
            ):
                setattr(match, key, list(values))
        match.winner, match.ended = winner, ended
        self._timed(match, saved)
        self._advance(index)
        return True

    def _timed(self, match: Match, saved: dict[str, Any]) -> None:
        """When a board began the stored match, and which board."""
        if _moment(saved.get("started")) is not None:
            match.started = saved["started"]
        board = saved.get("board")
        if self.several and type(board) is int and 0 <= board < len(self.seats):
            match.board = board


class TournamentDirector:
    """The setup of the next tournament and the tournament being played.

    It sets the practice game up for every match and takes the result when the
    match is booked. Between two matches, the practice game holds the result:
    darts thrown meanwhile start no new match. The settings of the practice
    game from before the tournament go back to it when the tournament ends.

    A tournament on several boards knows its boards by their key: the director
    takes the practice game of the board a key names, and None for its own,
    the first board of the tournament.
    """

    def __init__(self) -> None:
        self.setup = TournamentSetup()
        self.tournament: Tournament | None = None
        # The practice settings from before the tournament being played.
        self.saved: dict[str, Any] | None = None

    @property
    def waiting(self) -> bool:
        """The board of the director waits for its next match."""
        return self.waiting_at()

    def waiting_at(self, board: str | None = None) -> bool:
        tournament = self.tournament
        return (
            tournament is not None
            and tournament.status != FINISHED
            and tournament.seats[self._seat(board)].match is None
        )

    @property
    def running(self) -> bool:
        """A tournament is being played, or waits for its next match."""
        return self.tournament is not None and self.tournament.status != FINISHED

    def _seat(self, board: str | None) -> int:
        """The place of a board among the boards of the tournament: 0 for the
        board of the director, else the board of this key."""
        tournament = self.tournament
        if board is None or tournament is None:
            return 0
        return next(
            number for number, seat in enumerate(tournament.seats) if seat.key == board
        )

    def guests(self) -> list[str]:
        """The keys of the other boards of the tournament being played."""
        tournament = self.tournament
        if not self.running or tournament is None:
            return []
        return [seat.key for seat in tournament.seats[1:]]

    def name(self) -> str:
        """The name of the first board of the tournament."""
        return self.tournament.seats[0].name if self.tournament else ""

    def configure(self, **values: Any) -> None:
        """Settings of the next tournament; None leaves one as it is."""
        for key, value in values.items():
            if value is not None:
                setattr(self.setup, key, value)

    # -- the tournament ------------------------------------------------------------

    def start(
        self,
        practice: PracticeGame,
        now: datetime,
        *,
        players: list[str] | None = None,
        start_scores: list[int] | None = None,
        legs: int | None = None,
        sets: int | None = None,
        seed: int | None = None,
        rules: dict[str, bool | None] | None = None,
        groups: int | None = None,
        advance: int | None = None,
        boards: list[tuple[str, str]] | None = None,
        **setup: Any,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Draw a tournament and set the practice game up for its first match.

        Unset values come from the setup; legs, sets and rules from the practice
        game. Start scores go with the players in their order; 0 or none plays
        the game's. A seed draws the order at random, the same order for the
        same seed. Groups with knockout make groups of about four players
        with 0 groups. Boards, the key and the name of each with this board first,
        make a tournament on several boards, which the other boards then join.
        A tournament being played has to be stopped first.
        """
        if self.running:
            raise ActionRefused("tournament_running")
        check_names(list(players or []))
        given_starts = list(start_scores or [])
        entrants = [
            (_name(name), given_starts[index] if index < len(given_starts) else 0)
            for index, name in enumerate(
                self.setup.players if players is None else players
            )
            if name.strip()
        ]
        names = [name for name, _ in entrants]
        seen: set[str] = set()
        for name in names:
            if name.casefold() in seen:
                raise ActionRefused("duplicate_player", name=name)
            seen.add(name.casefold())
        chosen = setup.get("format") or self.setup.format
        fewest, most = ENTRANTS[chosen]
        if not fewest <= len(names) <= most:
            raise ActionRefused(
                "tournament_players",
                count=str(len(names)),
                min=str(fewest),
                max=str(most),
            )
        groups = self.setup.groups if groups is None else groups
        advance = self.setup.advance if advance is None else advance
        drawn = groups or auto_groups(len(names))
        if chosen == GROUPS_KNOCKOUT and not fits_groups(len(names), drawn, advance):
            raise ActionRefused(
                "tournament_groups",
                count=str(len(names)),
                groups=str(drawn),
                advance=str(advance),
            )
        self.configure(players=names, groups=groups, advance=advance, **setup)
        if seed is None and self.setup.random_draw:
            seed = _RANDOM.randint(1, MAX_SEED)
        order = list(entrants)
        if seed is not None:
            random.Random(seed).shuffle(order)
        given = rules or {}
        cricket = self.setup.game in CRICKET_GAMES
        self.tournament = Tournament(
            format=self.setup.format,
            game=self.setup.game,
            players=[name for name, _ in order],
            starts=[start for _, start in order],
            legs=practice.legs_to_win if legs is None else legs,
            sets=practice.sets_to_win if sets is None else sets,
            rules={
                # A double out waiting for the next leg is the one players set.
                rule: practice.tournament_setting(rule)
                if given.get(rule) is None
                else bool(given[rule])
                for rule in RULES
            },
            third_place=self.setup.third_place,
            groups=drawn,
            advance=advance,
            seed=seed,
            started=now.isoformat(),
            boards=boards,
            rates=[practice.profiles.rate(name, cricket) for name, _ in order],
        )
        # The settings to go back to: those before an earlier tournament, if
        # the practice game has not gone back to them yet.
        self.saved = practice.resume or practice.settings()
        practice.resume = None
        self._play(practice, 0)
        tournament = self.tournament
        return [
            (
                "tournament_started",
                {
                    **self._about(tournament),
                    "players": list(tournament.players),
                    "start_scores": list(tournament.starts),
                    "legs_to_win": tournament.legs_to_win,
                    "sets_to_win": tournament.sets_to_win,
                    "seed": tournament.seed,
                    **(
                        {
                            "groups": len(tournament.groups),
                            "advance": tournament.advance,
                        }
                        if tournament.groups
                        else {}
                    ),
                    **(
                        {"boards": [seat.name for seat in tournament.seats]}
                        if tournament.several
                        else {}
                    ),
                },
            )
        ]

    def join(self, practice: PracticeGame, board: str, now: datetime) -> None:
        """Another board takes its place as the tournament starts: its practice
        settings wait for the end of the tournament, and it plays a match at
        once if one is ready for it."""
        tournament = self.tournament
        assert tournament is not None
        number = self._seat(board)
        tournament.seats[number].saved = practice.resume or practice.settings()
        practice.resume = None
        practice.hold = False
        index = tournament.next_for(number)
        if index is not None:
            tournament.begin(index, number, now.isoformat())
            self._play(practice, number)

    def attach(self, practice: PracticeGame, board: str) -> None:
        """A board of the tournament is back after a restart: a result it
        showed waits for its next match again."""
        tournament = self.tournament
        assert tournament is not None
        number = self._seat(board)
        practice.hold = (
            tournament.seats[number].match is None
            and tournament.last_played(number) is not None
        )

    def vacate(self, board: str) -> None:
        """A board that left the tournament for good gives its match back, for
        another board to play."""
        tournament = self.tournament
        if board not in self.guests() or tournament is None:
            return
        seat = tournament.seats[self._seat(board)]
        if seat.match is not None:
            match = tournament.matches[seat.match]
            match.started = match.board = None
            seat.match = None
            tournament.refresh()

    def stop(self, practice: PracticeGame) -> None:
        """End the tournament; the practice match being played goes on, and
        the practice settings from before come back after it."""
        if self.tournament is None:
            raise ActionRefused("no_tournament")
        self.tournament = None
        practice.hold = False
        self._hand_back(practice)

    def release(self, practice: PracticeGame, board: str | None = None) -> None:
        """A board after the tournament, or before it stops: the practice
        settings from before come back with its next match or change of a
        setting."""
        practice.hold = False
        if board is None:
            self._hand_back(practice)
            return
        tournament = self.tournament
        assert tournament is not None
        seat = tournament.seats[self._seat(board)]
        if seat.saved is not None:
            practice.resume, seat.saved = seat.saved, None

    def _hand_back(self, practice: PracticeGame) -> None:
        """The practice settings from before the tournament go back to the
        practice game with its next match or change of a setting."""
        if self.saved is not None:
            practice.resume, self.saved = self.saved, None

    def check(self, name: str) -> None:
        """A player of the tournament being played cannot be deleted or
        renamed."""
        key = name.strip().casefold()
        tournament = self.tournament
        if (
            self.running
            and tournament is not None
            and any(player.casefold() == key for player in tournament.players)
        ):
            raise ActionRefused("player_in_tournament", name=name.strip())

    def forget(self, name: str) -> None:
        """Take a deleted player off the setup of the next tournament; a player
        of the tournament being played cannot be deleted."""
        self.check(name)
        key = name.strip().casefold()
        self.setup.players = [
            player for player in self.setup.players if player.casefold() != key
        ]
        if self.saved:
            self.saved["names"] = [
                "" if slot.casefold() == key else slot for slot in self.saved["names"]
            ]

    def rename(self, name: str, new_name: str) -> None:
        """A renamed player's new name in the setup of the next tournament, in
        a finished tournament and in the player slots the practice game gets
        back after the tournament; a player renamed into one who is in the
        setup already is there once. A player of the tournament being played
        keeps the name, and so does the tournament."""
        self.check(name)
        names = (name, new_name)
        keys = {player.strip().casefold() for player in names}
        players: list[str] = []
        for player in self.setup.players:
            if player.casefold() not in keys:
                players.append(player)
            elif new_name not in players:
                players.append(new_name)
        self.setup.players = players
        if self.tournament is not None and not self.running:
            self.tournament.players = [
                new_name if player.casefold() in keys else player
                for player in self.tournament.players
            ]
        if self.saved:
            self.saved["names"] = renamed_slots(self.saved["names"], names, new_name)

    def next_match(
        self, practice: PracticeGame, now: datetime, board: str | None = None
    ) -> None:
        """Start the next match at a board now, or set its current one up again
        when the practice game plays something else."""
        tournament = self.tournament
        if tournament is None:
            raise ActionRefused("no_tournament")
        if tournament.status == FINISHED:
            raise ActionRefused("tournament_finished")
        number = self._seat(board)
        index = tournament.seats[number].match
        if index is not None and self.plays(practice, board):
            first, second = tournament.names(tournament.matches[index])
            raise ActionRefused(
                "tournament_match_running", first=str(first), second=str(second)
            )
        if index is None:
            index = tournament.next_for(number)
            if index is None:
                raise ActionRefused("tournament_no_match")
            tournament.begin(index, number, now.isoformat())
        self._play(practice, number)

    def _play(self, practice: PracticeGame, number: int) -> None:
        """The practice game as the match of a board wants it."""
        tournament = self.tournament
        assert tournament is not None
        index = tournament.seats[number].match
        assert index is not None
        entrants = tournament.matches[index].players
        names = self._current_names(number)
        for rule, value in tournament.rules.items():
            setattr(practice, rule, value)
        # The rules of the tournament, not an Out mode left for the next leg;
        # its matches count the outer bull 25 and have no round limit.
        practice.out_mode_next = None
        practice.bull_mode, practice.max_rounds = BULL_25_50, 0
        for slot in range(len(practice.names)):
            practice.set_name(slot, names[slot] if slot < len(names) else "")
            entrant = entrants[slot] if slot < len(entrants) else None
            practice.set_start(
                slot, 0 if entrant is None else tournament.starts[entrant]
            )
        practice.hold = False
        # Tournaments are for the players: the bot sits them out.
        practice.bot_level = 0
        practice.set_players(len(names))
        practice.set_format(tournament.legs_to_win, tournament.sets_to_win)
        practice.play(tournament.kind)

    def _current_names(self, number: int) -> list[str]:
        tournament = self.tournament
        assert tournament is not None
        index = tournament.seats[number].match
        assert index is not None
        return [str(name) for name in tournament.names(tournament.matches[index])]

    def plays(self, practice: PracticeGame, board: str | None = None) -> bool:
        """Whether the practice game plays the match of a board: its game and
        players, with the format, the rules and the start scores of the
        tournament. A match whose settings were changed is another one."""
        tournament = self.tournament
        if tournament is None or tournament.status == FINISHED:
            return False
        number = self._seat(board)
        index = tournament.seats[number].match
        if index is None:
            return False
        names = self._current_names(number)
        starts = [
            0 if entrant is None else tournament.starts[entrant]
            for entrant in tournament.matches[index].players
        ]
        return (
            practice.kind == tournament.kind
            and len(practice.players) == len(names)
            and practice.names[: len(names)] == names
            and practice.starts[: len(starts)] == starts
            and practice.legs_to_win == tournament.legs_to_win
            and practice.sets_to_win == tournament.sets_to_win
            and all(
                practice.setting(rule) == on for rule, on in tournament.rules.items()
            )
            and practice.plain_rules()
        )

    def booked(
        self, practice: PracticeGame, now: datetime, board: str | None = None
    ) -> list[tuple[str, dict[str, Any]]]:
        """The result of the tournament match of a board, which its practice
        game just booked."""
        tournament = self.tournament
        if (
            tournament is None
            or practice.winner is None
            or not self.plays(practice, board)
        ):
            return []
        number = self._seat(board)
        seat = tournament.seats[number]
        index = seat.match
        assert index is not None
        tournament.record(index, practice, now.isoformat())
        seat.match = None
        match = tournament.matches[index]
        winner, loser = match.winner, match.loser
        assert winner is not None and loser is not None
        following = tournament.next_for(number)
        result = {
            **self._about(tournament),
            "match": tournament.numbers()[index],
            "round": match.round,
            "stage": match.stage,
            **({} if match.group is None else {"group": GROUP_NAMES[match.group]}),
            **({"board": seat.name} if tournament.several else {}),
            "players": tournament.names(match),
            "winner": tournament.players[winner],
            "loser": tournament.players[loser],
            "legs": list(match.legs),
            "sets": list(match.sets),
            "next": None
            if following is None
            else tournament.names(tournament.matches[following]),
        }
        events: list[tuple[str, dict[str, Any]]] = [
            ("tournament_match_finished", result)
        ]
        if tournament.upcoming() is not None:
            tournament.refresh()
            practice.hold = True
            return events
        tournament.status, tournament.ended = FINISHED, now.isoformat()
        self.release(practice, board)
        champion, runner_up, third = tournament.podium()
        events.append(
            (
                "tournament_finished",
                {
                    **self._about(tournament),
                    "winner": champion,
                    "runner_up": runner_up,
                    "third": third,
                    "players": list(tournament.players),
                },
            )
        )
        return events

    @staticmethod
    def _about(tournament: Tournament) -> dict[str, Any]:
        return {
            "format": tournament.format,
            "game": tournament.kind,
            "matches": len(tournament.numbers()),
        }

    def _due_at(self, number: int) -> datetime | None:
        """When the next match of a board is due: once the summary of the last
        match of the board and of each of its players, then the pause, are
        over; at once for a board and players who have not played yet. None
        without a pause, while the board plays, and without a match it could
        take."""
        tournament = self.tournament
        if (
            tournament is None
            or tournament.status == FINISHED
            or tournament.seats[number].match is not None
        ):
            return None
        index = tournament.next_for(number)
        if index is None:
            return None
        rested = tournament.rested(index, number)
        if rested is None:
            # A tournament stored without its start: at once.
            return _moment(tournament.started) or _EPOCH
        if not self.setup.pause:
            return None
        return rested + timedelta(seconds=self.setup.summary + self.setup.pause)

    def due_at(self, board: str | None = None) -> datetime | None:
        """When the next match of a board is due; None without a pause."""
        return self._due_at(self._seat(board))

    def due(self, now: datetime, board: str | None = None) -> bool:
        return (at := self.due_at(board)) is not None and at <= now

    def due_boards(self) -> list[tuple[str | None, datetime]]:
        """The boards whose next match is due at a known time, with that time:
        None for the board of the director, else the key of the board."""
        tournament = self.tournament
        if tournament is None:
            return []
        return [
            (seat.key if number else None, at)
            for number, seat in enumerate(tournament.seats)
            if (at := self._due_at(number)) is not None
        ]

    def free(self, practice: PracticeGame, board: str | None = None) -> bool:
        """Whether the practice game of a board can make way for its next match
        by itself: it shows a result, or nothing is played. A match of the last
        two players of the board started anew during the pause, by a change of
        its settings, makes way until its first dart. Another game chosen
        during the pause is played to its end first."""
        if practice.winner is not None or (
            practice.kind is None and practice.drill is None
        ):
            return True
        tournament = self.tournament
        if tournament is None or not self.waiting_at(board):
            return False
        number = self._seat(board)
        last = tournament.last_played(number if tournament.several else None)
        if last is None:
            return False
        names = [str(name) for name in tournament.names(tournament.matches[last])]
        return (
            practice.fresh
            and practice.kind == tournament.kind
            and len(practice.players) == len(names)
            and practice.names[: len(names)] == names
        )

    # -- storage and state ---------------------------------------------------------

    def stored(self) -> dict[str, Any]:
        return {
            "setup": asdict(self.setup),
            "tournament": self.tournament.stored() if self.tournament else None,
            "practice": dict(self.saved) if self.saved else None,
        }

    def restore(self, saved: object) -> None:
        data = saved if isinstance(saved, dict) else {}
        self.setup = TournamentSetup.restored(data.get("setup"))
        self.tournament = Tournament.restored(data.get("tournament"))
        self.saved = valid_settings(data.get("practice")) if self.running else None

    def _shown(self, number: int) -> int:
        """The match a board plays, or the one it plays next during a pause, or
        the first match still to play while it waits for another board."""
        tournament = self.tournament
        assert tournament is not None
        index = tournament.seats[number].match
        if index is None:
            index = self._waits_for(number)
        if index is None:
            index = tournament.upcoming()
        assert index is not None
        return index

    def _waits_for(self, number: int) -> int | None:
        """The match a board without one takes next: the first it can take, or
        else the first one still to play that no other board plays, its
        players possibly still open; None when the other boards play the
        rest."""
        tournament = self.tournament
        assert tournament is not None
        index = tournament.next_for(number)
        if index is None:
            taken = {seat.match for seat in tournament.seats if seat.match is not None}
            index = tournament.after(-1, taken)
        return index

    def state(self, board: str | None = None) -> str:
        """The stage a board plays, or the next one during a pause."""
        tournament = self.tournament
        if tournament is None:
            return "no_tournament"
        if tournament.status == FINISHED:
            return FINISHED
        return tournament.matches[self._shown(self._seat(board))].stage

    def snapshot(self, board: str | None = None) -> dict[str, Any]:
        """Everything a card or an automation needs to know about the
        tournament, as a board sees it: its own match first."""
        tournament = self.tournament
        if tournament is None:
            return {
                "status": None,
                "format": None,
                "game": None,
                "players": [],
                "winner": None,
                "fixtures": [],
            }
        number = self._seat(board)
        finished = tournament.status == FINISHED
        current = None if finished else tournament.seats[number].match
        upcoming = None if finished else self._shown(number)
        taken = {seat.match for seat in tournament.seats if seat.match is not None}
        if current is not None:
            following = tournament.after(current, taken)
        else:
            following = None if finished else self._waits_for(number)
        last = tournament.last_played(number if tournament.several else None)
        due = self._due_at(number)
        numbers = tournament.numbers()
        status = FINISHED if finished else WAITING if current is None else PLAYING
        return {
            "status": status,
            "format": tournament.format,
            "game": tournament.kind,
            "legs_to_win": tournament.legs_to_win,
            "sets_to_win": tournament.sets_to_win,
            **tournament.rules,
            "third_place": tournament.third_place,
            "seed": tournament.seed,
            "players": list(tournament.players),
            "start_scores": list(tournament.starts),
            "round": None if upcoming is None else tournament.matches[upcoming].round,
            "rounds": tournament.rounds,
            "matches_played": sum(match.played for match in tournament.matches),
            "matches_total": len(numbers),
            "current": tournament.match(current, numbers),
            "next": tournament.match(following, numbers),
            # Whether the board can start its next match now; False while it
            # waits for a match another board still plays.
            "next_ready": (
                not finished
                and current is None
                and tournament.next_for(number) is not None
            ),
            "last_result": tournament.match(last, numbers),
            "pause": self.setup.pause,
            "summary": self.setup.summary,
            "next_at": _shown(due),
            "ends_at": tournament.ends_at(self.setup.summary, self.setup.pause),
            "winner": tournament.podium()[0] if finished else None,
            "started": tournament.started,
            "ended": tournament.ended,
            **self._boards(number, numbers),
            "fixtures": [tournament.match(index, numbers) for index in numbers],
            **tournament.views(),
        }

    def _boards(self, number: int, numbers: dict[int, int]) -> dict[str, Any]:
        """The boards of a tournament on several boards, each with its match or
        when its next one is due, and the board, from 1, the snapshot is of."""
        tournament = self.tournament
        assert tournament is not None
        if not tournament.several:
            return {}
        boards = []
        for place, seat in enumerate(tournament.seats):
            due = self._due_at(place)
            match = None if seat.match is None else tournament.matches[seat.match]
            boards.append(
                {
                    "board": place + 1,
                    "name": seat.name,
                    "match": None if seat.match is None else numbers[seat.match],
                    "players": [] if match is None else tournament.names(match),
                    "next_at": _shown(due),
                }
            )
        return {"board": number + 1, "boards": boards}
