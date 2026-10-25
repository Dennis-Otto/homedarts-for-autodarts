"""Party games for one to eight players and the bull-off.

Shanghai, Halve-It and Killer, and Golf, Baseball and Count-Up, which play a
fixed number of rounds and settle a tie at the top in extra rounds; Bermuda,
Round the World and Gotcha as play.autodarts.io plays them.

A party game follows the darts of the visit for the player at the board and
books the visit when the darts are pulled, like X01. It knows its own rules:
who throws next, when a player wins at once, and who wins at the end.
"""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .board import RADIUS_MM, TREBLE_MM, distance_mm
from .scoring import BULL, MODES, STRAIGHT, fits, score
from .training import hit_key

PARTY_GAMES = (
    "shanghai",
    "halve_it",
    "killer",
    "golf",
    "baseball",
    "count_up",
    "bermuda",
    "round_the_world",
    "gotcha",
)
SHANGHAI_ROUNDS = 7
# Halve-It: a number, any double (D), any treble (T) or the bull (25) per round.
HALVE_IT_TARGETS = ("15", "16", "D", "17", "18", "T", "19", "20", "25")
HALVE_IT_START = 40
# Bermuda as play.autodarts.io plays it: any double or the bullseye in round 4,
# any treble in round 8, the bull (25 or 50) in round 12 and the bullseye (50)
# alone in round 13.
BERMUDA_TARGETS = (
    "12", "13", "14", "D", "15", "16", "17", "T", "18", "19", "20", "25", "50",
)  # fmt: skip
# Round the World: the numbers 1 to 20 in an order, then the bull.
ASCENDING, DESCENDING, RANDOM_ORDER = "ascending", "descending", "random"
WORLD_ORDERS = (ASCENDING, DESCENDING, RANDOM_ORDER)
WORLD_NUMBERS = 20
# Gotcha counts up to a target score of 101 to 1001, 301 unless players choose.
GOTCHA_TARGETS = (101, 1001)
GOTCHA_TARGET = 301
KILLER_LIVES = 3
# The bullseye beats the outer bull, which beats every other bed of the board;
# a dart off the board comes last.
BULL_BEDS = {"BULL": 3, "25": 2}
BOARD_BED, OFF_BOARD = 1, 0
GOLF_HOLES = (9, 18)
BASEBALL_INNINGS = 9
COUNT_UP_ROUNDS = 8
MAX_ROUNDS = 20
# Golf strokes of a dart at the hole: the double is the hole in one, the
# treble two strokes, then the inner and the outer single.
GOLF_STROKES = {2: 1, 3: 2}
GOLF_INNER, GOLF_OUTER, GOLF_MISS = 3, 4, 5
# Singles closer to the centre than the middle of the treble ring are inner
# singles; positions are relative to the outer edge of the double ring.
INNER_SINGLE = sum(TREBLE_MM) / 2 / RADIUS_MM
# A visit that ends without a dart, when the player passes: three misses.
MISSES = [{"number": 0, "multiplier": 0}] * 3


def inner_single(position: tuple[float, float] | None) -> bool | None:
    """Whether a single landed inside the treble ring; None without a position."""
    return None if position is None else math.hypot(*position) < INNER_SINGLE


def _thrown(saved: object, thrown: list[int]) -> dict[int, object]:
    """What a stored mapping keeps for the players who threw, by player; the
    keys of a mapping are text in JSON."""
    return {
        int(key): value
        for key, value in (saved if isinstance(saved, dict) else {}).items()
        if str(key).isdigit() and int(key) in thrown
    }


class BullOff:
    """Every player throws one dart at the bull; the closest starts the match.

    As the WDF and PDC rules want, the bullseye beats the outer bull, which
    beats every other bed of the board, and a dart off the board comes last;
    two darts in the same bull bed throw again, in reverse order. Outside the
    bull, the measured distance decides, and a dart the board did not measure
    loses to a measured one; so the distance decides inside, if players want,
    but only between measured darts. Darts off the board, and darts none of
    which the board measured, throw again.
    """

    def __init__(self, order: list[int]) -> None:
        self.order = list(order)
        self.index = 0
        # The bed each player hit, as BULL, 25 or S20, and how far from the
        # centre, where the board measured it.
        self.hits: dict[int, str] = {}
        self.distances: dict[int, float | None] = {}
        self.rethrow = False

    @property
    def thrower(self) -> int:
        return self.order[self.index]

    def book(
        self,
        dart: dict[str, Any],
        position: tuple[float, float] | None,
        by_distance: bool = False,
    ) -> int | None:
        """The first dart of the visit counts; the winner once everybody threw."""
        self.hits[self.thrower] = hit_key(dart)
        self.distances[self.thrower] = distance_mm(position)
        self.index += 1
        if self.index < len(self.order):
            return None
        closest = self._closest(by_distance)
        if len(closest) == 1:
            return closest[0]
        # A tie throws again among the tied players, the last one first.
        self.order, self.index = closest[::-1], 0
        self.hits, self.distances, self.rethrow = {}, {}, True
        return None

    def _bed(self, player: int) -> int:
        """How the bed of the player's dart ranks: the bull beds first."""
        hit = self.hits[player]
        return BULL_BEDS.get(hit, OFF_BOARD if hit == "MISS" else BOARD_BED)

    def _closest(self, by_distance: bool) -> list[int]:
        """The players whose darts nothing beats."""
        beds = {player: self._bed(player) for player in self.order}
        best = max(beds.values())
        closest = [player for player in self.order if beds[player] == best]
        if (
            len(closest) == 1
            or best == OFF_BOARD
            or (best > BOARD_BED and not by_distance)
        ):
            return closest
        measured = {
            player: distance
            for player in closest
            if (distance := self.distances[player]) is not None
        }
        if not measured or (best > BOARD_BED and len(measured) < len(closest)):
            return closest
        nearest = min(measured.values())
        return [player for player, distance in measured.items() if distance == nearest]

    def stored(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "index": self.index,
            "hits": self.hits,
            "distances": self.distances,
            "rethrow": self.rethrow,
        }

    @classmethod
    def restored(cls, saved: object, players: int) -> BullOff | None:
        if not isinstance(saved, dict):
            return None
        order = saved.get("order")
        if (
            not isinstance(order, list)
            or not order
            or not all(
                type(player) is int and 0 <= player < players for player in order
            )
            or len(set(order)) != len(order)
        ):
            return None
        bull_off = cls(order)
        bull_off.rethrow = saved.get("rethrow") is True
        index = saved.get("index")
        bull_off.index = (
            index if type(index) is int and index in range(len(order)) else 0
        )
        thrown = order[: bull_off.index]
        for player, value in _thrown(saved.get("hits"), thrown).items():
            if isinstance(value, str):
                bull_off.hits[player] = value
        for player, value in _thrown(saved.get("distances"), thrown).items():
            if value is None:
                bull_off.distances[player] = None
            elif isinstance(value, int | float) and not isinstance(value, bool):
                bull_off.distances[player] = float(value)
        # Up to version 1.5, only distances were kept: that round starts again.
        if not len(bull_off.hits) == len(bull_off.distances) == bull_off.index:
            bull_off.index, bull_off.hits, bull_off.distances = 0, {}, {}
        return bull_off


@dataclass
class Visit:
    """What a visit changes, worked out without booking it."""

    points: list[int]
    won: int | None = None
    lives: list[int] = field(default_factory=list)
    killers: list[bool] = field(default_factory=list)
    numbers: list[int | None] = field(default_factory=list)
    hits: int = 0
    # Darts that count: all of the visit, or up to the dart that won the leg.
    darts: int = 0
    # Round the World: how many targets every player has completed.
    progress: list[int] = field(default_factory=list)
    # Gotcha: a visit that overshot the target score and counts nothing.
    bust: bool = False


class PartyGame(ABC):
    """The rules of one party game for the players at the board."""

    kind = ""
    start = 0
    # Rounds of a leg, where the game has a fixed number.
    rounds: int | None = None
    # The fewest players the game takes.
    min_players = 1

    def __init__(self, players: int) -> None:
        self.players = players
        self.new_leg(players, 0)

    def new_leg(self, players: int, starter: int) -> None:
        self.players = players
        self.starter = starter
        self.points = [self.start] * players
        self.hits = [0] * players
        self.turns = 0

    @property
    def round(self) -> int:
        return self.turns // self.players + 1

    @property
    def shown_round(self) -> int | None:
        """The round the card shows, which never passes the last one."""
        return min(self.round, self.rounds) if self.rounds else None

    def playoff(self) -> list[int] | None:
        """The players of extra rounds after a tie, while they play them."""
        return None

    @property
    def choosing(self) -> bool:
        """Whether the players still choose what they play for, before the
        darts count."""
        return False

    def announced(self, player: int, result: Visit | None = None) -> dict[str, Any]:
        """What the game announces of a player at a turn and a won leg: their
        points, with the darts of the visit so far as `result` has them."""
        points = result.points if result else self.points
        return {"points": points[player]}

    @abstractmethod
    def target(self, player: int) -> str | None:
        """What the player aims at next, if the game names one."""

    @abstractmethod
    def visit(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        """What the darts of the visit change, without booking them."""

    def book(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        """Keep the visit; the winner when it decides the leg."""
        result = self.visit(player, darts)
        self.points = result.points
        self.hits[player] += result.hits
        self.turns += 1
        if result.won is None:
            result.won = self._decided()
        return result

    def _decided(self) -> int | None:
        return None

    def next(self, player: int) -> int:
        return (player + 1) % self.players

    def _best(self) -> int | None:
        """The most points win; more hits break a tie, otherwise nobody wins."""
        ranking = sorted(
            range(self.players),
            key=lambda index: (self.points[index], self.hits[index]),
            reverse=True,
        )
        first = ranking[0]
        if len(ranking) > 1 and (self.points[first], self.hits[first]) == (
            self.points[ranking[1]],
            self.hits[ranking[1]],
        ):
            return -1
        return first

    def details(self, player: int) -> dict[str, Any]:
        return {}

    def live_target(self, player: int, result: Visit) -> str | None:
        """What the player aims at after the darts of the visit so far."""
        return self.target(player)

    def live_details(self, player: int, result: Visit) -> dict[str, Any]:
        """The details of a player with the darts of the visit so far."""
        return self.details(player)

    def stored(self) -> dict[str, Any]:
        return {
            "starter": self.starter,
            "points": list(self.points),
            "hits": list(self.hits),
            "turns": self.turns,
        }

    def restore(self, saved: object) -> None:
        if not isinstance(saved, dict):
            return
        size = self.players

        def counts(key: str, low: int = 0) -> list[int] | None:
            values = saved.get(key)
            if (
                isinstance(values, list)
                and len(values) == size
                and all(type(value) is int and value >= low for value in values)
            ):
                return list(values)
            return None

        starter = saved.get("starter")
        self.starter = starter if type(starter) is int and starter in range(size) else 0
        self.points = counts("points") or self.points
        self.hits = counts("hits") or self.hits
        turns = saved.get("turns")
        self.turns = max(turns, 0) if type(turns) is int else 0


class Shanghai(PartyGame):
    """Seven rounds at 1 to 7; a single, double and treble in one visit wins."""

    kind = "shanghai"
    rounds = SHANGHAI_ROUNDS

    def target(self, player: int) -> str | None:
        return str(min(self.round, SHANGHAI_ROUNDS))

    def visit(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        number = min(self.round, SHANGHAI_ROUNDS)
        points = list(self.points)
        hits: list[int] = []
        for count, dart in enumerate(darts, 1):
            # A miss next to the number is no hit.
            if dart["number"] != number or dart["multiplier"] == 0:
                continue
            points[player] += score(dart)
            hits.append(dart["multiplier"])
            if set(hits) >= {1, 2, 3}:
                return Visit(points, player, hits=len(hits), darts=count)
        return Visit(points, hits=len(hits), darts=len(darts))

    def _decided(self) -> int | None:
        return self._best() if self.turns >= SHANGHAI_ROUNDS * self.players else None


class HalveIt(PartyGame):
    """Nine targets from 40 points; a visit without a hit halves the score."""

    kind = "halve_it"
    start = HALVE_IT_START
    targets: tuple[str, ...] = HALVE_IT_TARGETS
    rounds = len(HALVE_IT_TARGETS)
    halves = True

    def target(self, player: int) -> str | None:
        return self.targets[min(self.round, len(self.targets)) - 1]

    @staticmethod
    def hit(dart: dict[str, Any], target: str) -> bool:
        """Any bed of the number counts; D and T mean any double or treble,
        the bullseye included, 25 the outer bull or the bullseye, and 50 the
        bullseye alone."""
        number, multiplier = dart["number"], dart["multiplier"]
        if number == 0 or multiplier == 0:
            return False
        if target == "D":
            return bool(multiplier == 2)
        if target == "T":
            return bool(multiplier == 3)
        if target == "50":
            return bool(number == BULL and multiplier == 2)
        return bool(number == int(target))

    def visit(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        target = self.target(player) or ""
        hits = [dart for dart in darts if self.hit(dart, target)]
        points = list(self.points)
        points[player] += sum(score(dart) for dart in hits)
        if self.halves and not hits and len(darts) >= 3:
            # Halving rounds down.
            points[player] //= 2
        return Visit(points, hits=len(hits), darts=len(darts))

    def book(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        # A visit ends with fewer than three darts when darts miss the board.
        thrown = len(darts)
        if not any(self.hit(dart, self.target(player) or "") for dart in darts):
            darts = [*darts, *MISSES][:3]
        result = super().book(player, darts)
        result.darts = thrown
        return result

    def _decided(self) -> int | None:
        done = self.turns >= len(self.targets) * self.players
        return self._best() if done else None


class Bermuda(HalveIt):
    """Thirteen targets from 0 points, as play.autodarts.io plays them: the
    beds hit score their points, and a visit without a hit halves the score,
    unless players play without halving."""

    kind = "bermuda"
    start = 0
    targets = BERMUDA_TARGETS
    rounds = len(BERMUDA_TARGETS)

    def __init__(self, players: int, halve: bool = True) -> None:
        self.halves = halve
        super().__init__(players)


class Killer(PartyGame):
    """Everybody picks a number; hit your double to become a killer, then
    take the lives of the others with their doubles. The last one alive wins.
    """

    kind = "killer"
    min_players = 2

    def new_leg(self, players: int, starter: int) -> None:
        super().new_leg(players, starter)
        self.numbers: list[int | None] = [None] * players
        self.lives = [KILLER_LIVES] * players
        self.killers = [False] * players

    @property
    def choosing(self) -> bool:
        return None in self.numbers

    def announced(self, player: int, result: Visit | None = None) -> dict[str, Any]:
        """Killer keeps no points: the lives, and whether the player is a killer."""
        if result:
            return {"lives": result.lives[player], "killer": result.killers[player]}
        return {"lives": self.lives[player], "killer": self.killers[player]}

    def target(self, player: int) -> str | None:
        number = self.numbers[player]
        if number is None:
            return None
        return None if self.killers[player] else f"D{number}"

    def visit(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        numbers, lives, killers = (
            list(self.numbers),
            list(self.lives),
            list(self.killers),
        )
        if self.choosing:
            # One dart in any bed of a number that nobody has yet picks it.
            dart = darts[0] if darts else None
            if (
                dart
                and dart["multiplier"] > 0
                and 1 <= dart["number"] <= 20
                and dart["number"] not in numbers
            ):
                numbers[player] = dart["number"]
            return Visit(
                list(self.points), None, lives, killers, numbers, darts=len(darts)
            )
        won, counted = None, len(darts)
        for count, dart in enumerate(darts, 1):
            if lives[player] == 0:
                # Out of the game: the rest of the visit does nothing.
                break
            if dart["multiplier"] != 2 or dart["number"] not in numbers:
                continue
            owner = numbers.index(dart["number"])
            if owner == player and not killers[player]:
                killers[player] = True
            elif killers[player] and lives[owner] > 0:
                # A killer hitting their own double loses a life, too.
                lives[owner] -= 1
                if lives[player] == 0:
                    killers[player] = False
            alive = [index for index, left in enumerate(lives) if left > 0]
            if len(alive) == 1:
                won, counted = alive[0], count
                break
        return Visit(list(self.points), won, lives, killers, numbers, darts=counted)

    def book(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        # Only a dart decides a Killer leg, never the end of a round.
        result = super().book(player, darts)
        self.numbers, self.lives, self.killers = (
            result.numbers,
            result.lives,
            result.killers,
        )
        return result

    def next(self, player: int) -> int:
        if self.choosing and self.numbers[player] is None:
            # A dart that picked no number is thrown again.
            return player
        following = player
        for _ in range(self.players):
            following = (following + 1) % self.players
            if self.choosing:
                if self.numbers[following] is None:
                    return following
            elif self.lives[following] > 0:
                return following
        return player

    def details(self, player: int) -> dict[str, Any]:
        return {
            "number": self.numbers[player],
            "lives": self.lives[player],
            "killer": self.killers[player],
        }

    def live_target(self, player: int, result: Visit) -> str | None:
        # A killer made in this visit hunts the others from the next dart.
        number = result.numbers[player]
        return None if number is None or result.killers[player] else f"D{number}"

    def live_details(self, player: int, result: Visit) -> dict[str, Any]:
        return {
            "number": result.numbers[player],
            "lives": result.lives[player],
            "killer": result.killers[player],
        }

    def stored(self) -> dict[str, Any]:
        return {
            **super().stored(),
            "numbers": list(self.numbers),
            "lives": list(self.lives),
            "killers": list(self.killers),
        }

    def restore(self, saved: object) -> None:
        super().restore(saved)
        if not isinstance(saved, dict):
            return
        numbers, lives, killers = (
            saved.get("numbers"),
            saved.get("lives"),
            saved.get("killers"),
        )
        size = self.players
        if (
            isinstance(numbers, list)
            and len(numbers) == size
            and all(
                number is None or (type(number) is int and 1 <= number <= 20)
                for number in numbers
            )
            and len({number for number in numbers if number is not None})
            == len([number for number in numbers if number is not None])
        ):
            self.numbers = list(numbers)
        if (
            isinstance(lives, list)
            and len(lives) == size
            and all(type(left) is int and 0 <= left <= KILLER_LIVES for left in lives)
        ):
            self.lives = list(lives)
        if isinstance(killers, list) and len(killers) == size:
            self.killers = [killer is True for killer in killers]


class RoundTheWorld(PartyGame):
    """The numbers 1 to 20 in an order, then the bull: a dart in any bed of
    its target completes it and scores its points, and the next dart aims at
    the next target. Whoever completes the bull first wins."""

    kind = "round_the_world"

    def __init__(self, players: int, order: str = ASCENDING) -> None:
        self.order = order if order in WORLD_ORDERS else ASCENDING
        super().__init__(players)

    def new_leg(self, players: int, starter: int) -> None:
        super().new_leg(players, starter)
        numbers = list(range(1, WORLD_NUMBERS + 1))
        if self.order == DESCENDING:
            numbers.reverse()
        elif self.order == RANDOM_ORDER:
            # Not for security: a new order for every leg.
            random.shuffle(numbers)
        self.sequence = [*numbers, BULL]
        self.progress = [0] * players

    def _name(self, done: int) -> str | None:
        return str(self.sequence[done]) if done < len(self.sequence) else None

    def target(self, player: int) -> str | None:
        return self._name(self.progress[player])

    def visit(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        points, progress, hits = list(self.points), list(self.progress), 0
        for count, dart in enumerate(darts, 1):
            done = progress[player]
            if done >= len(self.sequence):
                # A restored leg that is already round the board.
                break
            if dart["multiplier"] == 0 or dart["number"] != self.sequence[done]:
                continue
            points[player] += score(dart)
            progress[player] = done + 1
            hits += 1
            if progress[player] == len(self.sequence):
                return Visit(points, player, hits=hits, darts=count, progress=progress)
        return Visit(points, hits=hits, darts=len(darts), progress=progress)

    def book(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        result = super().book(player, darts)
        self.progress = result.progress
        return result

    def details(self, player: int) -> dict[str, Any]:
        return {"progress": self.progress[player]}

    def live_target(self, player: int, result: Visit) -> str | None:
        return self._name(result.progress[player])

    def live_details(self, player: int, result: Visit) -> dict[str, Any]:
        return {"progress": result.progress[player]}

    def stored(self) -> dict[str, Any]:
        return {
            **super().stored(),
            "sequence": list(self.sequence),
            "progress": list(self.progress),
        }

    def restore(self, saved: object) -> None:
        super().restore(saved)
        if not isinstance(saved, dict):
            return
        sequence, progress = saved.get("sequence"), saved.get("progress")
        if (
            isinstance(sequence, list)
            and all(type(number) is int for number in sequence)
            and sequence[-1:] == [BULL]
            and sorted(sequence[:-1]) == list(range(1, WORLD_NUMBERS + 1))
        ):
            self.sequence = list(sequence)
        if (
            isinstance(progress, list)
            and len(progress) == self.players
            and all(
                type(done) is int and 0 <= done <= len(self.sequence)
                for done in progress
            )
        ):
            self.progress = list(progress)


class Gotcha(PartyGame):
    """Count up from 0 to the target score and finish it as the Out mode
    asks, as in X01 the other way round. A dart that overshoots, leaves 1
    with double or master out, or reaches the target with a dart that does
    not fit the Out mode busts the visit, which then counts nothing. A dart
    that brings the player to exactly another player's score sends that
    player back to 0: gotcha."""

    kind = "gotcha"

    def __init__(
        self, players: int, target: int = GOTCHA_TARGET, out_mode: str = STRAIGHT
    ) -> None:
        self.goal = target if valid_gotcha_target(target) else GOTCHA_TARGET
        self.out_mode = out_mode if out_mode in MODES else STRAIGHT
        super().__init__(players)

    def target(self, player: int) -> str | None:
        return None

    def left(self, points: int) -> int:
        """What a player with these points has left to score."""
        return self.goal - points

    def visit(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        points, hits = list(self.points), 0
        for count, dart in enumerate(darts, 1):
            scored = score(dart)
            left = self.left(points[player] + scored)
            if (
                left < 0
                or (self.out_mode != STRAIGHT and left == 1)
                or (left == 0 and not fits(dart, self.out_mode))
            ):
                return Visit(list(self.points), bust=True, darts=count)
            if not scored:
                continue
            points[player] += scored
            hits += 1
            if left == 0:
                return Visit(points, player, hits=hits, darts=count)
            for other in range(self.players):
                if other != player and points[other] == points[player]:
                    points[other] = 0
        return Visit(points, hits=hits, darts=len(darts))

    def details(self, player: int) -> dict[str, Any]:
        return {"left": self.left(self.points[player])}

    def live_details(self, player: int, result: Visit) -> dict[str, Any]:
        return {"left": self.left(result.points[player])}

    def restore(self, saved: object) -> None:
        super().restore(saved)
        # Points beyond the target belong to another target score.
        if any(points > self.goal for points in self.points):
            self.points = [self.start] * self.players


def valid_gotcha_target(target: object) -> bool:
    """A target score of Gotcha: a whole number from 101 to 1001."""
    low, high = GOTCHA_TARGETS
    return type(target) is int and low <= target <= high


class RoundsGame(PartyGame):
    """A fixed number of rounds for everybody; the best total wins.

    A tie at the top after the last round plays extra rounds among the tied
    players, in their throwing order, until one of them is ahead after a
    round. Round n aims at the number n, and extra rounds carry on from
    there, after 20 from 1 again.
    """

    default_rounds = 9
    lowest_wins = False

    def __init__(self, players: int, rounds: int | None = None) -> None:
        self.length = rounds or self.default_rounds
        self.rounds = self.length
        super().__init__(players)

    def new_leg(self, players: int, starter: int) -> None:
        super().new_leg(players, starter)
        self.current_round = 1
        # The players of the round in throwing order, and how many have thrown.
        self.lineup = [(starter + offset) % players for offset in range(players)]
        self.thrown = 0
        # The score of every round, per player.
        self.scorecard: list[list[int]] = [[] for _ in range(players)]

    @property
    def round(self) -> int:
        return self.current_round

    @property
    def shown_round(self) -> int | None:
        return self.current_round

    def playoff(self) -> list[int] | None:
        return list(self.lineup) if self.current_round > self.length else None

    def number(self) -> int:
        return (self.current_round - 1) % MAX_ROUNDS + 1

    def target(self, player: int) -> str | None:
        return str(self.number())

    @abstractmethod
    def score(self, darts: list[dict[str, Any]]) -> tuple[int, int]:
        """The points and the hits of a visit in the current round."""

    def visit(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        points = list(self.points)
        scored, hits = self.score(darts)
        points[player] += scored
        return Visit(points, hits=hits, darts=len(darts))

    def book(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        result = self.visit(player, darts)
        self.scorecard[player].append(result.points[player] - self.points[player])
        self.points = result.points
        self.hits[player] += result.hits
        self.turns += 1
        self.thrown += 1
        if self.thrown == len(self.lineup):
            result.won = self._round_played()
        return result

    def _round_played(self) -> int | None:
        """The winner once the last round decides the leg; otherwise the next round."""
        if self.current_round >= self.length:
            pick = min if self.lowest_wins else max
            best = pick(self.points[player] for player in self.lineup)
            leaders = [player for player in self.lineup if self.points[player] == best]
            if len(leaders) == 1:
                return leaders[0]
            self.lineup = leaders
        self.current_round += 1
        self.thrown = 0
        return None

    def next(self, player: int) -> int:
        return self.lineup[self.thrown]

    def details(self, player: int) -> dict[str, Any]:
        return {"scorecard": list(self.scorecard[player])}

    def stored(self) -> dict[str, Any]:
        return {
            **super().stored(),
            "round": self.current_round,
            "lineup": list(self.lineup),
            "thrown": self.thrown,
            "scorecard": [list(scores) for scores in self.scorecard],
        }

    def restore(self, saved: object) -> None:
        super().restore(saved)
        if not isinstance(saved, dict):
            return
        size = self.players
        current, lineup = saved.get("round"), saved.get("lineup")
        thrown, scorecard = saved.get("thrown"), saved.get("scorecard")
        if type(current) is int and current >= 1:
            self.current_round = current
        if (
            isinstance(lineup, list)
            and lineup
            and all(type(player) is int and 0 <= player < size for player in lineup)
            and len(set(lineup)) == len(lineup)
        ):
            self.lineup = list(lineup)
        # Everybody has thrown once the last round decided the leg.
        if type(thrown) is int and thrown in range(len(self.lineup) + 1):
            self.thrown = thrown
        if (
            isinstance(scorecard, list)
            and len(scorecard) == size
            and all(
                isinstance(scores, list)
                and all(type(value) is int and value >= 0 for value in scores)
                for scores in scorecard
            )
        ):
            self.scorecard = [list(scores) for scores in scorecard]


def golf_strokes(dart: dict[str, Any], hole: int) -> int:
    """Strokes of a dart at the hole: double 1, treble 2, inner single 3,
    outer single 4, anything else 5. A single without a position counts as
    an outer single."""
    if dart["number"] != hole or dart["multiplier"] == 0:
        return GOLF_MISS
    if dart["multiplier"] in GOLF_STROKES:
        return GOLF_STROKES[dart["multiplier"]]
    return GOLF_INNER if dart.get("inner") else GOLF_OUTER


class Golf(RoundsGame):
    """Nine or 18 holes, hole n at the number n; the last dart of the visit
    counts, so players stop by pulling their darts. The double is a hole in
    one, the treble two strokes; the fewest strokes win."""

    kind = "golf"
    lowest_wins = True

    def score(self, darts: list[dict[str, Any]]) -> tuple[int, int]:
        if not darts:
            return 0, 0
        strokes = golf_strokes(darts[-1], self.number())
        return strokes, int(strokes < GOLF_MISS)

    def book(self, player: int, darts: list[dict[str, Any]]) -> Visit:
        # A player who passes without a dart plays the hole as a miss.
        result = super().book(player, darts or MISSES[:1])
        result.darts = len(darts)
        return result


class Baseball(RoundsGame):
    """Nine innings, inning n at the number n: a single scores one run, a
    double two, a treble three. The most runs win."""

    kind = "baseball"

    def score(self, darts: list[dict[str, Any]]) -> tuple[int, int]:
        number = self.number()
        hits = [
            dart["multiplier"]
            for dart in darts
            if dart["number"] == number and dart["multiplier"] > 0
        ]
        return sum(hits), len(hits)


class CountUp(RoundsGame):
    """Every dart scores its value for a number of rounds; the most points win."""

    kind = "count_up"
    default_rounds = COUNT_UP_ROUNDS

    def target(self, player: int) -> str | None:
        return None

    def score(self, darts: list[dict[str, Any]]) -> tuple[int, int]:
        return sum(score(dart) for dart in darts), sum(
            score(dart) > 0 for dart in darts
        )


GAME_RULES: dict[str, type[PartyGame]] = {
    "shanghai": Shanghai,
    "halve_it": HalveIt,
    "killer": Killer,
    "golf": Golf,
    "baseball": Baseball,
    "count_up": CountUp,
    "bermuda": Bermuda,
    "round_the_world": RoundTheWorld,
    "gotcha": Gotcha,
}


def make_party(
    kind: str, players: int, rounds: int | None = None, **options: Any
) -> PartyGame:
    """The rules of a party game; Golf and Count-Up take their number of
    rounds, Bermuda whether a miss halves, Round the World its order and
    Gotcha its target score and Out mode."""
    rules = GAME_RULES[kind]
    if issubclass(rules, RoundsGame):
        return rules(players, rounds)
    return rules(players, **options)
