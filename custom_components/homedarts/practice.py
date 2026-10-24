"""Practice games on the local board for up to four players, party games for up
to eight, and training games.

X01 with a start score of its own for every player, Cricket, Cut-Throat,
Tactics, Wild Mouse, Random and Hidden Cricket, the party games, and the
training games; X01 and the Cricket games also as two teams of two, and
against the bot. With several players, a bull-off can decide who starts. X01
has the rules of play.autodarts.io: the In and Out mode straight, double or
master, the bull mode 25/50 or 50/50, and a round limit after which the
lowest score wins.

PracticeGame is the match frame of every game: the players, their seats and
teams, the bot, the bull-off, legs and sets, the tallies of the match, undo
and storage. The game itself is a mode of modes.py that the frame plays in.
"""

from __future__ import annotations

import copy
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .board import distance_mm
from .bot import DEFAULT_DELAY, MAX_DELAY, valid_level
from .cricket import CRICKET_GAMES, CRICKET_NUMBERS
from .doubles import DoubleHits, DoubleStats
from .drills import DRILLS, Drill, make_drill
from .modes import (
    PARTY_RULES,
    STATS_KEYS,
    STATS_LEGS,
    CricketMode,
    DrillMode,
    Events,
    GameMode,
    PartyMode,
    VisitRefused,
    X01Mode,
)
from .moments import stamp
from .party import (
    ASCENDING,
    COUNT_UP_ROUNDS,
    GOLF_HOLES,
    GOTCHA_TARGET,
    MAX_ROUNDS,
    PARTY_GAMES,
    WORLD_ORDERS,
    BullOff,
    PartyGame,
    make_party,
    valid_gotcha_target,
)
from .profiles import Profiles, clean_name
from .scoring import (
    BULL_25_50,
    BULL_MODES,
    DOUBLE,
    MASTER,
    MODES,
    STRAIGHT,
    VISIT_DARTS,
    bounded_count,
    rate,
)
from .scoring import average as _average
from .summary import HIGH_VISITS, Tally
from .training import hit_key

GAMES = (101, 301, 501, 701, 901, 1001)
LEG_HISTORY = 10
MAX_PLAYERS = 4
# A party game takes a party: as many players as a tournament, each with a name.
PARTY_PLAYERS = 8
MAX_LEGS = 11
MAX_SETS = 7
# A start score of its own: 0 plays the game's, otherwise 2 to 1001.
MAX_START = 1001
# Two teams of two: players 1 and 3 against players 2 and 4.
TEAM_PLAYERS = 4
# The rules of the practice game that players switch on and off.
OPTIONS = (
    "double_out",
    "double_in",
    "bull_off",
    "bull_off_distance",
    "personal_routes",
    "teams",
    "manual_entry",
    "three_in_a_bed",
    "bermuda_halve_on_miss",
)
# The games to choose from, as the practice game select and start_game offer them.
GAME_OPTIONS = (*(str(game) for game in GAMES), *CRICKET_GAMES, *PARTY_GAMES, *DRILLS)
# The rules a match is played with, which a tournament sets for its matches.
MATCH_RULES = ("double_out", "double_in", "bull_off", "bull_off_distance")
# The X01 rules of play.autodarts.io: the In and Out mode, the bull mode and the
# round limit, 0 for none. Double in and double out stand for the In and Out
# mode double, and their switches and the actions' fields for double or straight.
X01_RULES = ("in_mode", "out_mode", "bull_mode", "max_rounds")
MODE_ALIASES = {"double_in": "in_mode", "double_out": "out_mode"}
DEFAULT_RULES: dict[str, str | int] = {
    "in_mode": STRAIGHT,
    "out_mode": DOUBLE,
    "bull_mode": BULL_25_50,
    "max_rounds": 0,
}
# A leg with a round limit ends after this many rounds at most.
ROUND_LIMIT = 50
# A start score that no dart can win with double or master in and out, but for
# master in and master out: the only openers, D1 and T1, leave 1 or end the leg
# on a treble.
UNWINNABLE_START = 3


def valid_start(value: object) -> bool:
    """0 for the game's start score, or a start score of 2 to 1001."""
    return type(value) is int and (value == 0 or 2 <= value <= MAX_START)


def valid_rule(rule: str, value: object) -> bool:
    """An In or Out mode, a bull mode, or a round limit of 0 to 50."""
    if rule == "max_rounds":
        return type(value) is int and 0 <= value <= ROUND_LIMIT
    choices = BULL_MODES if rule == "bull_mode" else MODES
    return rule in X01_RULES and value in choices


def valid_party_rule(rule: str, value: object) -> bool:
    """An order of Round the World, or a target score of Gotcha."""
    if rule == "gotcha_target":
        return valid_gotcha_target(value)
    return rule in PARTY_RULES and value in WORLD_ORDERS


def unwinnable_rules(in_mode: str, out_mode: str) -> bool:
    """Whether these In and Out modes cannot win a start score of 3."""
    return STRAIGHT not in (in_mode, out_mode) and (in_mode, out_mode) != (
        MASTER,
        MASTER,
    )


def valid_delay(value: object) -> bool:
    """Seconds between the bot's darts: 0 to 10."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return 0 <= value <= MAX_DELAY


def valid_settings(saved: object) -> dict[str, Any] | None:
    """Stored match settings (see PracticeGame.settings), if they are sound."""
    if not isinstance(saved, dict):
        return None
    names, starts = saved.get("names"), saved.get("starts")
    # Up to version 1.9, four players had a name.
    if not (
        bounded_count(saved.get("players"), 1, PARTY_PLAYERS, 0)
        and isinstance(names, list)
        and MAX_PLAYERS <= len(names) <= PARTY_PLAYERS
        and all(isinstance(name, str) for name in names)
        and isinstance(starts, list)
        and len(starts) == MAX_PLAYERS
        and all(valid_start(start) for start in starts)
        and valid_level(saved.get("bot_level"))
        and bounded_count(saved.get("legs_to_win"), 1, MAX_LEGS, 0)
        and bounded_count(saved.get("sets_to_win"), 1, MAX_SETS, 0)
        and all(isinstance(saved.get(rule), bool) for rule in MATCH_RULES)
    ):
        return None
    kept = ("players", "bot_level", "legs_to_win", "sets_to_win", *MATCH_RULES)
    # Up to version 1.12, double in and double out were the In and Out mode.
    rules = {
        **DEFAULT_RULES,
        **{
            rule: DOUBLE if saved[alias] else STRAIGHT
            for alias, rule in MODE_ALIASES.items()
        },
    }
    return {
        **{key: saved[key] for key in kept},
        **{
            rule: saved[rule] if valid_rule(rule, saved.get(rule)) else rules[rule]
            for rule in X01_RULES
        },
        "names": [clean_name(name) for name in names]
        + [""] * (PARTY_PLAYERS - len(names)),
        "starts": list(starts),
    }


@dataclass
class Player:
    """Scores of one player; remaining, darts and points restart every leg."""

    remaining: int = 0
    darts: int = 0
    points: int = 0
    # Legs won in the current set, or in the final set of a finished match.
    legs: int = 0
    sets: int = 0
    match_legs: int = 0
    match_darts: int = 0
    match_points: int = 0
    # Points of the first nine darts and darts thrown at a double, per leg.
    first9_points: int = 0
    first9_darts: int = 0
    at_double: int = 0
    # Cricket: marks per number, and the marks that counted per leg and match.
    marks: list[int] = field(default_factory=lambda: [0] * len(CRICKET_NUMBERS))
    marks_hit: int = 0
    match_marks: int = 0
    # Double in: scoring starts with the first double of the leg.
    opened: bool = False
    # Visits of 100+, 140+ and 180 points in the leg, as the tally of the
    # match counts them.
    scores_100: int = 0
    scores_140: int = 0
    scores_180: int = 0

    def new_leg(self, start: int, slots: int = len(CRICKET_NUMBERS)) -> None:
        self.remaining, self.darts, self.points = start, 0, 0
        self.first9_points, self.first9_darts, self.at_double = 0, 0, 0
        self.marks, self.marks_hit = [0] * slots, 0
        self.opened = False
        self.scores_100, self.scores_140, self.scores_180 = 0, 0, 0

    def high_visit(self, points: int) -> None:
        """An X01 visit of the leg, with the points it scored."""
        for low, key in HIGH_VISITS:
            if points >= low:
                setattr(self, key, getattr(self, key) + 1)
                return

    @classmethod
    def restored(cls, saved: object, slots: int = len(CRICKET_NUMBERS)) -> Player:
        data = saved if isinstance(saved, dict) else {}
        numbers = {
            key: bounded_count(data.get(key), 0, 10**6, 0)
            for key, value in asdict(cls()).items()
            if type(value) is int
        }
        marks = data.get("marks")
        valid = isinstance(marks, list) and len(marks) == slots
        return cls(
            **numbers,
            marks=[bounded_count(mark, 0, 3, 0) for mark in marks]
            if valid and isinstance(marks, list)
            else [0] * slots,
            opened=data.get("opened") is True,
        )


class PracticeGame:
    """Matches and training games played with the darts the board detects.

    The training session reports the darts of the current visit; a visit
    ends when the darts are pulled, and then the next player throws. With
    several players, legs make sets and sets make the match; the result stays
    until the next dart. The game being played is the mode: X01, a Cricket,
    party or training game, or none.
    """

    def __init__(self) -> None:
        # The game being played; see modes.py.
        self.mode = GameMode(self)
        # The randomness of the games that draw, such as Random Cricket; no
        # cryptographic randomness, which games need not.
        self.rng = random.Random()  # noqa: S311
        # The X01 rules: how a leg opens and ends, what the outer bull scores,
        # and the rounds after which the lowest score wins the leg, 0 for none.
        self.in_mode = STRAIGHT
        self.out_mode = DOUBLE
        self.bull_mode = BULL_25_50
        self.max_rounds = 0
        self.bull_off = False
        # The Out mode changed during a leg: the rule of the next leg.
        self.out_mode_next: str | None = None
        # Two darts in the same bull bed: the measured distance decides instead
        # of a rethrow; an option, as the official rules throw again.
        self.bull_off_distance = False
        # Checkout routes over the strongest doubles of the player at the board.
        self.personal_routes = False
        # Four players of X01 or Cricket play as two teams of two.
        self.teams = False
        # Darts entered by hand in Home Assistant, for missed detections.
        self.manual_entry = False
        # Wild Mouse with three in a bed, as its rules have it; casual players
        # often leave it out.
        self.three_in_a_bed = True
        # The bot's 3-dart average, 0 without it, and the seconds between its
        # darts. In X01 and the Cricket games, it takes the last seat.
        self.bot_level = 0
        self.bot_delay = DEFAULT_DELAY
        # A start score of their own per player; 0 plays the game's.
        self.starts = [0] * MAX_PLAYERS
        self.golf_holes = GOLF_HOLES[0]
        self.count_up_rounds = COUNT_UP_ROUNDS
        # Bermuda halves the score of a visit without a hit, as play.autodarts.io
        # does; Round the World goes round in an order; Gotcha counts up to this.
        self.bermuda_halve_on_miss = True
        self.round_the_world_order = ASCENDING
        self.gotcha_target = GOTCHA_TARGET
        # The bull-off before a match of several players, while it runs.
        self.bulling: BullOff | None = None
        self.legs_to_win = 1
        self.sets_to_win = 1
        self.names = [""] * PARTY_PLAYERS
        self.players = [Player()]
        self.current = 0
        # Visits booked in the X01 leg being played, which count its rounds.
        self.leg_visits = 0
        # Who throws first in the current leg, and in the current set: the
        # throw passes on every leg within a set and every set within the match.
        self.starter = 0
        self.set_starter = 0
        self.winner: int | None = None
        self.legs: list[dict[str, Any]] = []
        self.leg_stats: list[dict[str, int]] = []
        self.legs_total = 0
        # Every player's numbers of the match, and the summary of the last match.
        self.tallies = [Tally()]
        self.summary: dict[str, Any] | None = None
        # When the first dart of the match landed, for the training calendar.
        self.match_started: str | None = None
        # Raised with every new match, so that a game is told from the one
        # before it, after a restart too; see lifecycle.py.
        self.serial = 0
        # Every training game, with its results of every session.
        self.drills: dict[str, Drill] = {kind: make_drill(kind) for kind in DRILLS}
        self.profiles = Profiles()
        self.doubles = DoubleStats()
        self.double_hits = DoubleHits()
        # A tournament keeps a finished match until its next match starts, and
        # leaves the settings from before it to come back with the next match
        # after it, or with the next change of a setting.
        self.hold = False
        self.resume: dict[str, Any] | None = None
        self._visit: list[dict[str, Any]] = []
        # Board positions of the visit's darts, where the board reports them.
        self._positions: list[tuple[float, float] | None] = []
        # Darts of the current visit thrown before the leg began.
        self._skip = 0
        self._announced: str | None = None

    @property
    def double_out(self) -> bool:
        """The Out mode double, which statistics and records count checkouts with."""
        return self.out_mode == DOUBLE

    @double_out.setter
    def double_out(self, enabled: bool) -> None:
        self.out_mode = DOUBLE if enabled else STRAIGHT

    @property
    def double_in(self) -> bool:
        """The In mode double."""
        return self.in_mode == DOUBLE

    @double_in.setter
    def double_in(self, enabled: bool) -> None:
        self.in_mode = DOUBLE if enabled else STRAIGHT

    # -- storage ---------------------------------------------------------------

    def restore(self, saved: object) -> None:
        if not isinstance(saved, dict):
            return
        for option in OPTIONS:
            if isinstance(saved.get(option), bool):
                setattr(self, option, saved[option])
        # Up to version 1.12, double in and double out were the In and Out mode.
        for rule in X01_RULES:
            if valid_rule(rule, saved.get(rule)):
                setattr(self, rule, saved[rule])
        starts = saved.get("starts")
        if isinstance(starts, list) and len(starts) == MAX_PLAYERS:
            self.starts = [start if valid_start(start) else 0 for start in starts]
        if saved.get("golf_holes") in GOLF_HOLES:
            self.golf_holes = saved["golf_holes"]
        self.count_up_rounds = bounded_count(
            saved.get("count_up_rounds"), 1, MAX_ROUNDS, COUNT_UP_ROUNDS
        )
        for rule in PARTY_RULES:
            if valid_party_rule(rule, saved.get(rule)):
                setattr(self, rule, saved[rule])
        self.legs_to_win = bounded_count(saved.get("legs_to_win"), 1, MAX_LEGS, 1)
        self.sets_to_win = bounded_count(saved.get("sets_to_win"), 1, MAX_SETS, 1)
        level, delay = saved.get("bot_level"), saved.get("bot_delay")
        self.bot_level = level if type(level) is int and valid_level(level) else 0
        self.bot_delay = (
            float(delay)
            if isinstance(delay, int | float) and valid_delay(delay)
            else DEFAULT_DELAY
        )
        names = saved.get("names")
        if isinstance(names, list):
            self.names = [
                clean_name(name) if isinstance(name, str) else ""
                for name in [*names, *[""] * PARTY_PLAYERS][:PARTY_PLAYERS]
            ]
        players = saved.get("players")
        if not (isinstance(players, list) and 0 < len(players) <= PARTY_PLAYERS):
            # Version 1.2 stored a single player at the top level.
            players = [
                {"remaining": saved.get("remaining"), "darts": saved.get("darts")}
            ]
        drill = saved.get("drill")
        mode = self._mode(drill if drill in DRILLS else saved.get("game"), len(players))
        if mode.drill is None and not mode.playing:
            # A store without a game it knows keeps the X01 game being played.
            mode = self._mode(self.game, len(players))
        self.mode = mode
        slots = self.mode.slots()
        self.players = [Player.restored(player, slots) for player in players]
        last = len(self.players) - 1
        self.current = bounded_count(saved.get("current"), 0, last, 0)
        self.leg_visits = bounded_count(saved.get("leg_visits"), 0, 10**6, 0)
        self.starter = bounded_count(saved.get("starter"), 0, last, 0)
        # Up to version 1.5, the starter passed on every leg; the legs of the
        # current set tell who started it.
        played = sum(player.legs for player in self.players)
        self.set_starter = bounded_count(
            saved.get("set_starter"),
            0,
            last,
            (self.starter - played) % len(self.players),
        )
        winner = saved.get("winner")
        self.winner = winner if type(winner) is int and 0 <= winner <= last else None
        self.mode.restore(saved)
        # A bull-off decides who starts a match, and a training game has none.
        self.bulling = (
            BullOff.restored(saved.get("bulling"), len(self.players))
            if self.mode.playing
            else None
        )
        stats = saved.get("leg_stats")
        self.leg_stats = [
            {key: record[key] for key in STATS_KEYS}
            for record in (stats if isinstance(stats, list) else [])
            if isinstance(record, dict)
            and all(
                type(record.get(key)) is int and record[key] >= 0 for key in STATS_KEYS
            )
        ][:STATS_LEGS]
        total = saved.get("legs_total")
        self.legs_total = total if type(total) is int and total >= 0 else 0
        self.profiles.restore(saved.get("profiles"))
        self.doubles.restore(saved.get("doubles"))
        self.double_hits.restore(saved.get("double_hits"))
        drills = saved.get("drills")
        for drill_kind, drill in self.drills.items():
            state = drills.get(drill_kind) if isinstance(drills, dict) else None
            if isinstance(state, dict):
                drill.restore(state)
        legs = saved.get("legs")
        self.legs = [
            dict(leg)
            for leg in (legs if isinstance(legs, list) else [])
            if isinstance(leg, dict)
            and leg.get("game") in (*GAMES, *CRICKET_GAMES, *PARTY_GAMES)
            and type(leg.get("darts")) is int
            # A party game passed without darts to its end has none, and so has
            # an X01 leg the round limit decided after passes.
            and (
                leg["darts"] > 0
                or (
                    leg["darts"] == 0
                    and (leg["game"] in PARTY_GAMES or "rounds" in leg)
                )
            )
        ][:LEG_HISTORY]
        self._restore_match(saved)

    def _restore_match(self, saved: dict[str, Any]) -> None:
        """The tallies of the match, its summary and an Out mode waiting for
        the next leg; stores before version 1.6 have none of them, and up to
        version 1.12 a double out waited."""
        pending = saved.get("out_mode_next", saved.get("double_out_next"))
        if isinstance(pending, bool):
            pending = DOUBLE if pending else STRAIGHT
        self.out_mode_next = pending if valid_rule("out_mode", pending) else None
        self.resume = valid_settings(saved.get("resume"))
        tallies = saved.get("tallies")
        self.tallies = (
            [Tally.restored(tally) for tally in tallies]
            if isinstance(tallies, list) and len(tallies) == len(self.players)
            else [Tally() for _ in self.players]
        )
        summary = saved.get("summary")
        self.summary = (
            copy.deepcopy(summary)
            if isinstance(summary, dict) and isinstance(summary.get("players"), list)
            else None
        )
        started = saved.get("match_started")
        self.match_started = started if isinstance(started, str) else None
        serial = saved.get("serial")
        self.serial = serial if type(serial) is int and serial >= 0 else 0

    def stored(self) -> dict[str, Any]:
        own = self.mode.stored()
        return {
            "game": self.mode.kind,
            "double_out": self.double_out,
            "double_in": self.double_in,
            **{rule: getattr(self, rule) for rule in X01_RULES},
            "bull_off": self.bull_off,
            "bull_off_distance": self.bull_off_distance,
            "personal_routes": self.personal_routes,
            "teams": self.teams,
            "starts": list(self.starts),
            "manual_entry": self.manual_entry,
            "three_in_a_bed": self.three_in_a_bed,
            "bot_level": self.bot_level,
            "bot_delay": self.bot_delay,
            "golf_holes": self.golf_holes,
            "count_up_rounds": self.count_up_rounds,
            "bermuda_halve_on_miss": self.bermuda_halve_on_miss,
            **{rule: getattr(self, rule) for rule in PARTY_RULES},
            "drawn": own["drawn"],
            "doubles": self.doubles.stored(),
            "double_hits": self.double_hits.stored(),
            "party": own["party"],
            "bulling": self.bulling.stored() if self.bulling else None,
            "legs_to_win": self.legs_to_win,
            "sets_to_win": self.sets_to_win,
            "names": list(self.names),
            "players": [asdict(player) for player in self.players],
            "current": self.current,
            "leg_visits": self.leg_visits,
            "starter": self.starter,
            "set_starter": self.set_starter,
            "winner": self.winner,
            "legs": [dict(leg) for leg in self.legs],
            "leg_stats": [dict(record) for record in self.leg_stats],
            "legs_total": self.legs_total,
            "drill": self.drill,
            "drills": {kind: drill.stored() for kind, drill in self.drills.items()},
            "profiles": self.profiles.stored(),
            "out_mode_next": self.out_mode_next,
            "resume": copy.deepcopy(self.resume),
            "tallies": [tally.stored() for tally in self.tallies],
            "summary": copy.deepcopy(self.summary),
            "match_started": self.match_started,
            "serial": self.serial,
        }

    # -- settings --------------------------------------------------------------

    def play(self, game: int | str, players: int | None = None) -> None:
        """Start a match of X01, a Cricket or party game, or a training game,
        with this many players besides the bot or as many as before.

        0 stops playing.
        """
        self._resume()
        humans = self.humans if players is None else players
        self.mode = self._mode(game, humans)
        # The bot joins the games it plays, and leaves the others.
        self.set_players(humans)

    def _mode(self, kind: object, players: int) -> GameMode:
        """The mode factory: the mode that plays a game named as the select
        names it, or as an X01 start score; no game for anything else."""
        if isinstance(kind, str):
            if kind in DRILLS:
                return DrillMode(self, kind)
            if kind in CRICKET_GAMES:
                return CricketMode(self, kind)
            if kind in PARTY_GAMES:
                return PartyMode(self, self._party(kind, players))
        if isinstance(kind, int) and kind in GAMES:
            return X01Mode(self, kind)
        return GameMode(self)

    def _party(self, kind: str, players: int) -> PartyGame:
        """A party game with the rules players chose for it."""
        options: dict[str, dict[str, Any]] = {
            "bermuda": {"halve": self.bermuda_halve_on_miss},
            "round_the_world": {"order": self.round_the_world_order},
            "gotcha": {"target": self.gotcha_target, "out_mode": self.out_mode},
        }
        rounds = {"golf": self.golf_holes, "count_up": self.count_up_rounds}
        return make_party(kind, players, rounds.get(kind), **options.get(kind, {}))

    @property
    def game(self) -> int:
        """The X01 start score of the game being played; 0 in another game."""
        return self.mode.game

    @game.setter
    def game(self, start: int) -> None:
        """Play X01 from this start score, or no game with 0, in the match as
        it is."""
        self.mode = self._mode(start, len(self.players))

    @property
    def cricket(self) -> str | None:
        """The Cricket game being played: cricket, cut_throat or tactics."""
        return self.mode.cricket

    @property
    def party(self) -> PartyGame | None:
        """The party game being played."""
        return self.mode.party

    @property
    def drill(self) -> str | None:
        """The training game played instead of a match, if any."""
        return self.mode.drill

    @property
    def drawn(self) -> tuple[int, ...] | None:
        """The numbers Random and Hidden Cricket drew for the leg."""
        return self.mode.drawn

    @drawn.setter
    def drawn(self, numbers: tuple[int, ...]) -> None:
        self.mode.drawn = tuple(numbers)

    @property
    def humans(self) -> int:
        """The players at the board without the bot."""
        return len(self.players) - (self.bot_seat is not None)

    @property
    def seats(self) -> int:
        """The players the game takes: eight in a party game and before a game
        is chosen, four in the other games."""
        return PARTY_PLAYERS if self.mode.party_seats else MAX_PLAYERS

    def set_players(self, count: int) -> None:
        """Players besides the bot; the bot takes a seat of its own after them."""
        self._resume()
        bot = int(self._bot_plays())
        humans = min(bounded_count(count, 1, PARTY_PLAYERS, 1), self.seats - bot)
        self.players = [Player() for _ in range(humans + bot)]
        self.new_match()

    def set_bot(self, level: int) -> None:
        """The bot's level, 0 without the bot. A bot that joins or leaves the
        game being played starts a new match; otherwise the new level plays
        from the bot's next dart."""
        self._resume()
        if not valid_level(level) or level == self.bot_level:
            return
        humans, playing = self.humans, self._bot_plays()
        self.bot_level = level
        if self._bot_plays() != playing:
            self.set_players(humans)

    def set_format(self, legs: int | None = None, sets: int | None = None) -> None:
        self._resume()
        if legs is not None:
            self.legs_to_win = bounded_count(legs, 1, MAX_LEGS, self.legs_to_win)
        if sets is not None:
            self.sets_to_win = bounded_count(sets, 1, MAX_SETS, self.sets_to_win)
        self.new_match()

    def set_start(self, index: int, start: int) -> None:
        """A start score of the player's own, or 0 for the game's; a new match."""
        self._resume()
        if 0 <= index < MAX_PLAYERS and valid_start(start):
            self.starts[index] = start
        self.new_match()

    def set_rounds(
        self, golf_holes: int | None = None, count_up_rounds: int | None = None
    ) -> None:
        """Holes of Golf and rounds of Count-Up; a change starts the game anew
        while it is played."""
        self._resume()
        before = {
            "golf_holes": self.golf_holes,
            "count_up_rounds": self.count_up_rounds,
        }
        if golf_holes in GOLF_HOLES:
            self.golf_holes = golf_holes
        if count_up_rounds is not None:
            self.count_up_rounds = bounded_count(
                count_up_rounds, 1, MAX_ROUNDS, self.count_up_rounds
            )
        self._restart(
            *(
                setting
                for setting, value in before.items()
                if getattr(self, setting) != value
            )
        )

    def set_party_rule(self, rule: str, value: str | int) -> None:
        """The order of Round the World or the target score of Gotcha; a
        change starts the game anew while it is played."""
        self._resume()
        if not valid_party_rule(rule, value) or value == getattr(self, rule):
            return
        setattr(self, rule, value)
        self._restart(rule)

    def set_option(self, option: str, enabled: bool) -> None:
        """Switch a rule of the game on or off.

        Double in and double out set the In and Out mode to double or straight,
        see set_rule. A rule that a game is made with starts the game anew
        while it is played, such as three in a bed of Wild Mouse, which changes
        the targets to close.
        """
        if option in MODE_ALIASES:
            self.set_rule(MODE_ALIASES[option], DOUBLE if enabled else STRAIGHT)
            return
        self._resume()
        changed = enabled != getattr(self, option)
        setattr(self, option, enabled)
        if changed:
            self._restart(option)

    def _restart(self, *changed: str) -> None:
        """Start the game being played anew when a setting it is made with
        changed, such as the holes of Golf."""
        if set(changed) & set(self.mode.settings):
            self.play(self.mode.kind)

    def set_rule(self, rule: str, value: str | int) -> bool:
        """Set an X01 rule; whether it changed what players set.

        The Out mode changes a leg only before its first dart; once darts
        count, it applies from the next leg. A leg keeps its rules, so none
        becomes unwinnable, as for a player on 1 when double out comes on.
        """
        self._resume()
        if not valid_rule(rule, value) or value == self.rule(rule):
            return False
        if rule == "out_mode" and self._leg_begun():
            self.out_mode_next = None if value == self.out_mode else str(value)
            return True
        setattr(self, rule, value)
        if rule == "out_mode":
            self.out_mode_next = None
            self.mode.out_mode_changed()
        return True

    def unwinnable(
        self, starts: list[int] | None = None, rules: dict[str, Any] | None = None
    ) -> bool:
        """Whether a seat would start from 3 with In and Out modes that cannot
        win it (see unwinnable_rules), with these start scores or rules instead
        of the current ones. Double in and double out stand for the modes
        double or straight."""
        given = dict(rules or {})
        for alias, rule in MODE_ALIASES.items():
            if alias in given and rule not in given:
                given[rule] = DOUBLE if given[alias] else STRAIGHT
        modes = [given.get(rule, self.rule(rule)) for rule in ("in_mode", "out_mode")]
        seats = (self.starts if starts is None else starts)[: len(self.players)]
        return unwinnable_rules(*modes) and UNWINNABLE_START in seats

    def setting(self, option: str) -> bool:
        """A rule as players set it; double out may wait for the next leg."""
        if option == "double_out":
            return bool(self.rule("out_mode") == DOUBLE)
        return bool(getattr(self, option))

    def rule(self, rule: str) -> Any:
        """An X01 rule as players set it; the Out mode may wait for the next leg."""
        if rule == "out_mode" and self.out_mode_next is not None:
            return self.out_mode_next
        return getattr(self, rule)

    def tournament_setting(self, option: str) -> bool:
        """A rule of a match for a tournament to play, see setting; a
        tournament plays straight or double in and out, and master comes
        closest to double."""
        if option in MODE_ALIASES:
            return bool(self.rule(MODE_ALIASES[option]) != STRAIGHT)
        return self.setting(option)

    def plain_rules(self) -> bool:
        """Whether X01 is played with the rules a tournament knows: straight or
        double in and out, the outer bull 25 and no round limit."""
        return (
            MASTER not in (self.in_mode, self.rule("out_mode"))
            and self.bull_mode == BULL_25_50
            and not self.max_rounds
        )

    def _leg_begun(self) -> bool:
        """Darts of the X01 or Gotcha leg in progress count already."""
        return bool(
            self.mode.uses_out_mode
            and self.winner is None
            and (any(player.darts for player in self.players) or self._scoring())
        )

    def set_name(self, index: int, name: str) -> None:
        """A player's name, without the characters no name contains."""
        self._resume()
        if 0 <= index < PARTY_PLAYERS:
            self.names[index] = clean_name(name)

    def rename(self, index: int, name: str) -> bool:
        """Name one seat, as *Practice player N* does; whether it took the name.

        A name is one player, in any upper and lower case: a seat in play
        keeps a name it has, so another seat cannot take it, while a resting
        seat or the bot's seat, which keeps the name of whoever sat there
        before, gives it up.
        """
        self._resume()
        key = clean_name(name).casefold()
        twins = [
            seat
            for seat, other in enumerate(self.names)
            if key and seat != index and other.casefold() == key
        ]
        if any(seat < len(self.players) and seat != self.bot_seat for seat in twins):
            return False
        for seat in twins:
            self.names[seat] = ""
        self.set_name(index, name)
        return True

    def forget(self, name: str) -> None:
        """Clear the player slots with this name, in any upper and lower case,
        also in the settings a tournament left to come back to."""
        key = name.strip().casefold()

        def cleared(names: list[str]) -> list[str]:
            return ["" if slot.casefold() == key else slot for slot in names]

        self.names = cleared(self.names)
        if self.resume:
            self.resume["names"] = cleared(self.resume["names"])

    def settings(self) -> dict[str, Any]:
        """What players set up for a match, for a tournament to come back to:
        the players besides the bot, their names and start scores, the bot's
        level, the format and the rules."""
        return {
            "players": self.humans,
            "names": list(self.names),
            "starts": list(self.starts),
            "bot_level": self.bot_level,
            "legs_to_win": self.legs_to_win,
            "sets_to_win": self.sets_to_win,
            **{rule: self.setting(rule) for rule in MATCH_RULES},
            **{rule: self.rule(rule) for rule in X01_RULES},
        }

    def _resume(self) -> None:
        """Back to the settings a tournament left, once, with a new match."""
        saved, self.resume = self.resume, None
        if saved is None:
            return
        self.names, self.starts = list(saved["names"]), list(saved["starts"])
        self.bot_level = saved["bot_level"]
        self.legs_to_win = saved["legs_to_win"]
        self.sets_to_win = saved["sets_to_win"]
        for rule in (*MATCH_RULES, *X01_RULES):
            setattr(self, rule, saved[rule])
        self.out_mode_next = None
        self.set_players(saved["players"])

    def new_match(self) -> None:
        """Everybody starts from zero legs and sets; player 1 throws first,
        unless a bull-off decides it."""
        self._resume()
        self.serial += 1
        self.players = [Player() for _ in self.players]
        self.tallies = [Tally() for _ in self.players]
        self.match_started = None
        self.starter, self.set_starter, self.winner = 0, 0, None
        self.bulling = (
            BullOff(list(range(len(self.players))))
            if self.bull_off and len(self.players) > 1 and self.mode.playing
            else None
        )
        self._next_leg()

    def new_leg(self) -> None:
        """Start the leg again from the full score: what it added to the
        match counts no more, and darts already thrown do not count.

        After a finished match, the next match starts.
        """
        if self.winner is not None:
            self.new_match()
            return
        for player, tally in zip(self.players, self.tallies, strict=True):
            player.match_darts = max(0, player.match_darts - player.darts)
            player.match_marks = max(0, player.match_marks - player.marks_hit)
            # Only X01 counts the points of its legs for the match.
            player.match_points = max(0, player.match_points - player.points)
            for _, key in HIGH_VISITS:
                left = getattr(tally, key) - getattr(player, key)
                setattr(tally, key, max(0, left))
        self._next_leg()

    def _next_leg(self) -> None:
        """The next leg from the full score; darts already thrown do not count."""
        if self.out_mode_next is not None:
            self.out_mode, self.out_mode_next = self.out_mode_next, None
            self.mode.out_mode_changed()
        self.leg_visits = 0
        slots = self.mode.slots()
        for index, player in enumerate(self.players):
            player.new_leg(self.mode.start(index), slots)
        self.mode.new_leg()
        self.current = self.starter
        self._skip = len(self._visit)
        self._announced = None

    # -- play ------------------------------------------------------------------

    def _name(self, index: int) -> str | None:
        """The name of the player in a seat; the bot has none of its own."""
        return None if index == self.bot_seat else self.names[index] or None

    def _bot_plays(self) -> bool:
        """The bot plays X01 and the Cricket games once it has a level."""
        return self.bot_level > 0 and self.mode.bot

    @property
    def bot_seat(self) -> int | None:
        """The bot's seat, the last one, while it plays."""
        if not self._bot_plays() or len(self.players) < 2:
            return None
        return len(self.players) - 1

    @property
    def bot_up(self) -> bool:
        """Whether the bot throws now: in its turn, or its dart of the bull-off."""
        seat = self.bot_seat
        if seat is None or self.winner is not None:
            return False
        return (self.bulling.thrower if self.bulling else self.current) == seat

    def _teamed(self) -> bool:
        """Four players of X01 or a Cricket game play as two teams."""
        return self.teams and len(self.players) == TEAM_PLAYERS and self.mode.team_play

    def _side(self, index: int) -> list[int]:
        """The player and their partner in a team, in seat order."""
        return [index % 2, index % 2 + 2] if self._teamed() else [index]

    def _winners(self) -> list[int]:
        return [] if self.winner is None else self._side(self.winner)

    def _team_name(self, team: int) -> str | None:
        """Alex & Kim, when both players of the team have a name; a team with
        the bot has none, as the bot's seat has no name."""
        first, second = self._name(team), self._name(team + 2)
        return f"{first} & {second}" if first and second else None

    def _teams_snapshot(self) -> list[dict[str, Any]] | None:
        if not self._teamed():
            return None
        return [
            {
                "team": team + 1,
                "name": self._team_name(team),
                "players": [team + 1, team + 3],
            }
            for team in (0, 1)
        ]

    @property
    def kind(self) -> int | str | None:
        """The X01, Cricket or party game being played; None otherwise."""
        return self.mode.kind if self.mode.playing else None

    @property
    def fresh(self) -> bool:
        """Whether the match being played has seen no dart yet: none booked,
        none of a bull-off and none on the board."""
        bulling = self.bulling
        return (
            self.winner is None
            and not any(player.match_darts for player in self.players)
            and not (bulling and (bulling.index or bulling.rethrow))
            and not self._thrown()
        )

    @property
    def thrower(self) -> str | None:
        """The name of the player at the board in a game, if they have one."""
        if not self.mode.playing:
            return None
        return self._name(self.bulling.thrower if self.bulling else self.current)

    def lineup(self) -> dict[str, Any]:
        """The game set up on the board as game_started tells it: the game, the
        players by seat with their names, the start scores in X01, the format,
        and the seat and the level of the bot. A training game is for player 1
        alone."""
        training = self.drill is not None
        seats = 1 if training else len(self.players)
        bot = self.bot_seat
        return {
            "game": self.drill if training else self.kind,
            "players": seats,
            "names": [self._name(index) for index in range(seats)],
            "start_scores": [self.mode.start(index) for index in range(seats)]
            if self.game
            else None,
            "legs": None if training else self.legs_to_win,
            "sets": None if training else self.sets_to_win,
            "bot_player": None if bot is None else bot + 1,
            "bot_level": None if bot is None else self.bot_level,
        }

    def victor(self) -> dict[str, Any]:
        """Who won the match, as game_ended tells it: the name of the player or
        of their team, none for the bot or a player without one, and the seat."""
        if self.winner is None:
            return {"winner": None, "player": None}
        who = self._who(self.winner)
        return {
            "winner": who.get("team_name") or who["name"],
            "player": self.winner + 1,
        }

    def _who(self, index: int) -> dict[str, Any]:
        who = {
            "game": self.mode.kind,
            "player": index + 1,
            "name": self._name(index),
            "players": len(self.players),
        }
        if index == self.bot_seat:
            who["bot"] = True
        if self._teamed():
            who["team"] = index % 2 + 1
            who["team_name"] = self._team_name(index % 2)
        return who

    def _sum(self, index: int, key: str) -> int:
        """A number of the player, or of both partners in a team."""
        return sum(getattr(self.players[other], key) for other in self._side(index))

    def _thrown(self) -> list[dict[str, Any]]:
        return self._visit[self._skip : VISIT_DARTS]

    def _scoring(self) -> list[dict[str, Any]]:
        """The darts of the visit that score: none while the bull-off decides
        who starts, whose dart is thrown at the bull."""
        return [] if self.bulling else self._thrown()

    def _record_doubles(
        self, attempts: list[tuple[str, bool]], player: int, now: datetime
    ) -> None:
        # The bot's darts count for nobody's doubles.
        if player != self.bot_seat:
            self.doubles.record(attempts)
            self.profiles.doubles(self._name(player), attempts, now)

    def _position(self, index: int) -> tuple[float, float] | None:
        """Where the board saw the dart at this index of the thrown darts."""
        index += self._skip
        return self._positions[index] if index < len(self._positions) else None

    def _result(self, index: int) -> tuple[int, int, bool]:
        """Legs in the set, sets and the match decision after the player wins
        this leg; a won set keeps its legs until the next set starts."""
        player = self.players[index]
        legs, sets = player.legs + 1, player.sets
        if len(self.players) == 1:
            return legs, sets, False
        if legs >= self.legs_to_win:
            sets += 1
        return legs, sets, sets >= self.sets_to_win

    def _final(self, winner: int, legs: int, sets: int) -> list[dict[str, Any]]:
        """Legs and sets of everybody once this leg decides the match."""
        side = self._side(winner)
        return [
            {
                "player": index + 1,
                "name": self._name(index),
                "legs": legs if index in side else player.legs,
                "sets": sets if index in side else player.sets,
                **self._seat(index),
            }
            for index, player in enumerate(self.players)
        ]

    def _seat(self, index: int) -> dict[str, Any]:
        """The team of a seat and whether the bot sits there, where that applies."""
        seat: dict[str, Any] = {"team": index % 2 + 1} if self._teamed() else {}
        if index == self.bot_seat:
            seat["bot"] = True
        return seat

    def _won(
        self, winner: int, leg: dict[str, Any], won_match: dict[str, Any]
    ) -> Events:
        """The leg the seat wins, and the match where the leg decides it: who
        won, what the game announces of the leg or of the match, and the legs
        and sets after it."""
        legs, sets, match = self._result(winner)
        events: Events = [
            (
                "leg_won",
                {
                    **self._who(winner),
                    **leg,
                    "legs": legs,
                    "sets": sets,
                    "match": match,
                },
            )
        ]
        if match:
            events.append(
                (
                    "match_won",
                    {
                        **self._who(winner),
                        "legs": legs,
                        "sets": sets,
                        "scores": self._final(winner, legs, sets),
                        **won_match,
                    },
                )
            )
        return events

    def track(
        self,
        visit: list[dict[str, Any]],
        positions: list[tuple[float, float] | None] | None = None,
        *,
        now: datetime,
    ) -> Events:
        """Follow the darts of the current visit, announcing a bust or a win.

        A won match comes with every player's numbers for its summary, as the
        visit that decided it leaves them once it is booked.
        """
        return self._summarized(self._follow(visit, positions, now), False, now)

    def _follow(
        self,
        visit: list[dict[str, Any]],
        positions: list[tuple[float, float] | None] | None,
        now: datetime,
    ) -> Events:
        self._visit = list(visit)
        self._positions = list(positions or [])
        self._skip = min(self._skip, len(self._visit))
        if self.mode.playing:
            if self.winner is not None and self._thrown():
                if self.hold:
                    # Darts thrown while a tournament waits count for no match.
                    self._skip = len(self._visit)
                    return []
                # The first dart after a finished match starts the next one.
                self.new_match()
                self._skip = 0
            if self.match_started is None and self._thrown():
                self.match_started = stamp(now)
            if self.bulling:
                return []
        return self.mode.track()

    def score_visit(
        self,
        points: int,
        darts: int | None = None,
        at_double: int | None = None,
        checkout: bool = False,
    ) -> list[dict[str, Any]]:
        """The darts of an X01 visit entered as its score, `points`; see
        X01Mode.score_visit. Only a leg being played takes one."""
        if self.bulling or self.winner is not None or self.hold:
            raise VisitRefused("visit_not_x01")
        return self.mode.score_visit(points, darts, at_double, checkout)

    def passes(self) -> bool:
        """Whether a visit without darts can end, so the next player throws:
        in X01, the Cricket and the party games, where it counts as a visit of
        three misses, but not in a bull-off or while Killer's numbers are
        chosen."""
        return bool(self.mode.passes() and self.winner is None and self.bulling is None)

    def finish_visit(self, empty: bool = False, *, now: datetime) -> Events:
        """Book the visit whose darts were pulled; then the next player throws.

        With empty, a visit without darts is booked as well where passes()
        allows it: the player at the board passes. A training game books
        every visit, a match none after its end.
        """
        decided = self.winner is not None
        events: Events = []
        # Every double hit counts, in a game or not and whatever the dart was aimed
        # at; the bot's darts count for nobody.
        if not self.bot_up:
            self.double_hits.record(self._thrown())
        if not self.mode.playing:
            events = self.mode.book(now)
        elif self.winner is None and (self._thrown() or (empty and self.passes())):
            events = self._book_bull_off() if self.bulling else self.mode.book(now)
        if self.winner is not None and not decided:
            self.summary = self._summary(self.winner, now)
        self._visit, self._skip, self._announced = [], 0, None
        return self._summarized(events, True, now)

    def _turn(self) -> tuple[str, dict[str, Any]]:
        """The player at the board next, with what callers need to announce."""
        if self.bulling:
            return (
                "turn_changed",
                {
                    **self._who(self.bulling.thrower),
                    "remaining": None,
                    "checkout": None,
                    "bull_off": True,
                },
            )
        return "turn_changed", {**self._who(self.current), **self.mode.turn_details()}

    @property
    def round(self) -> int:
        """The round of the X01 leg being played, from 1."""
        return self.leg_visits // len(self.players) + 1

    # -- bull-off ----------------------------------------------------------------

    def _book_bull_off(self) -> Events:
        """The first dart of the visit counts; the closest dart starts the match."""
        bulling = self.bulling
        assert bulling is not None
        winner = bulling.book(
            self._thrown()[0], self._position(0), self.bull_off_distance
        )
        if winner is None:
            return [self._turn()]
        won = {"distance": bulling.distances[winner], "hit": bulling.hits[winner]}
        self.bulling = None
        self.starter = self.set_starter = winner
        self._next_leg()
        return [("bull_off_won", {**self._who(winner), **won}), self._turn()]

    def _bull_off_snapshot(self) -> dict[str, Any] | None:
        bulling = self.bulling
        if bulling is None:
            return None
        thrown = self._thrown()
        live = {
            "distance": distance_mm(self._position(0)) if thrown else None,
            "hit": hit_key(thrown[0]) if thrown else None,
        }
        return {
            "player": bulling.thrower + 1,
            "name": self._name(bulling.thrower),
            "rethrow": bulling.rethrow,
            "by_distance": self.bull_off_distance,
            "throws": [
                {
                    "player": index + 1,
                    "name": self._name(index),
                    **self._seat(index),
                    **(
                        live
                        if index == bulling.thrower
                        else {
                            "distance": bulling.distances.get(index),
                            "hit": bulling.hits.get(index),
                        }
                    ),
                }
                for index in bulling.order
            ],
        }

    def statistics(self) -> dict[str, Any]:
        """Averages and rates of the last ten legs and the double drills."""
        totals = {
            key: sum(record[key] for record in self.leg_stats) for key in STATS_KEYS
        }
        drill_darts, drill_hits = 0, 0
        for kind in ("doubles", "bobs_27"):
            for result in self.drills[kind].results:
                darts, hits = result.get("darts"), result.get("hits")
                if type(darts) is int and type(hits) is int and 0 <= hits <= darts:
                    drill_darts += darts
                    drill_hits += hits
        return {
            "first_9_average": _average(
                totals["first9_points"], totals["first9_darts"]
            ),
            "checkout_rate": rate(totals["checkouts"], totals["at_double"]),
            "doubles_rate": rate(
                totals["checkouts"] + drill_hits, totals["at_double"] + drill_darts
            ),
            "legs_played": self.legs_total,
            "legs_counted": len(self.leg_stats),
            "darts_at_double": totals["at_double"] + drill_darts,
        }

    # -- legs and matches ---------------------------------------------------------

    def _leg_entries(self, rounds: int | None = None) -> list[dict[str, Any]]:
        """Every player's numbers of the leg that just ended, for the profiles;
        a leg the round limit decided was not checked out."""
        entries = []
        side = self._side(self.current)
        for index, player in enumerate(self.players):
            entry: dict[str, Any] = {
                "name": self._name(index),
                "won": index in side,
                "darts": player.darts,
            }
            if self._teamed():
                # A team leg sets no record of fewest darts for one player.
                entry["team"] = True
            if rounds:
                entry["rounds"] = rounds
            entry.update(self.mode.leg_entry(index, player, rounds))
            entries.append(entry)
        return entries

    def _match_entries(self) -> list[dict[str, Any]]:
        """Every player's result of the match that just ended, for the history."""
        entries = []
        for index, player in enumerate(self.players):
            entry: dict[str, Any] = {
                "name": self._name(index),
                "legs": player.legs,
                "sets": player.sets,
                "match_legs": player.match_legs,
                **self._seat(index),
                **self.mode.match_entry(index, player),
            }
            entries.append(entry)
        return entries

    def _book_leg(self, now: datetime, rounds: int | None = None) -> None:
        """The leg the player at self.current won: checked out, or decided by
        the round limit after this many rounds."""
        self._tally_leg(checked_out=not rounds)
        self.profiles.leg(self.mode.kind, self._leg_entries(rounds), now)
        winner = self.players[self.current]
        side = self._side(self.current)
        record = self.mode.book_leg(rounds)
        self.legs.insert(
            0,
            {
                **self._who(self.current),
                **record,
                "ended": stamp(now),
            },
        )
        del self.legs[LEG_HISTORY:]
        self.legs_total += 1
        legs, sets, match = self._result(self.current)
        set_won = sets > winner.sets
        for index in side:
            player = self.players[index]
            player.legs, player.sets = legs, sets
            player.match_legs += 1
        if match:
            # The result stays: the winners keep the legs of the deciding set,
            # and what they had left when the round limit decided it.
            for index in side:
                self.players[index].remaining = winner.remaining if rounds else 0
            self.winner = self.current
            self.profiles.match(
                self.mode.kind,
                self._match_entries(),
                self.current,
                self.legs_to_win,
                self.sets_to_win,
                side,
                self.match_started,
                now=now,
            )
            return
        players = len(self.players)
        if set_won:
            # A won set starts the next one from zero legs for everybody, and
            # the next player in turn throws first in the new set.
            for player in self.players:
                player.legs = 0
            self.set_starter = (self.set_starter + 1) % players
            self.starter = self.set_starter
        else:
            self.starter = (self.starter + 1) % players
        self._next_leg()

    # -- match summary ------------------------------------------------------------

    def _tally_leg(self, checked_out: bool = True) -> None:
        """The leg that ended counts for everybody's match numbers. A team
        wins the leg together, in the darts of both partners; the checkout
        counts for the player who threw it. A leg the round limit decided is
        nobody's best leg."""
        for player, tally in zip(self.players, self.tallies, strict=True):
            tally.leg(player.first9_points, player.first9_darts, player.at_double)
        if not checked_out:
            return
        darts = self._sum(self.current, "darts")
        for index in self._side(self.current):
            # What the player who threw it had left, which only X01 keeps.
            checkout = self.players[index].remaining if index == self.current else 0
            self.tallies[index].won(darts, checkout, self.double_out)

    def _summary(self, winner: int, now: datetime) -> dict[str, Any]:
        """The match that just ended: its format, winner and every player."""
        return {
            "game": self.mode.kind,
            "ended": stamp(now),
            "winner": winner + 1,
            "legs_to_win": self.legs_to_win,
            "sets_to_win": self.sets_to_win,
            "double_out": self.double_out,
            "players": [
                self._summary_entry(index) for index in range(len(self.players))
            ],
        }

    def _summary_entry(self, index: int) -> dict[str, Any]:
        """One player's numbers of the match: legs, sets and darts, and those of
        the game, such as the averages of X01 and the marks of Cricket."""
        player, tally = self.players[index], self.tallies[index]
        entry: dict[str, Any] = {
            "player": index + 1,
            "name": self._name(index),
            "legs": player.match_legs,
            "sets": player.sets,
            "darts": player.match_darts,
        }
        if index == self.bot_seat:
            entry["bot"] = True
        entry.update(self.mode.summary_entry(index, player, tally))
        return entry

    def _settled(self, now: datetime) -> list[dict[str, Any]]:
        """Every player's numbers of the summary once the visit that decides
        the match is booked: a scratch copy of the game books it."""
        # The copy must not touch the profiles and doubles of the players.
        memo: dict[int, Any] = {
            id(self.profiles): Profiles(),
            id(self.doubles): DoubleStats(),
            id(self.double_hits): DoubleHits(),
        }
        scratch = copy.deepcopy(self, memo)
        scratch.finish_visit(now=now)
        assert scratch.summary is not None
        players: list[dict[str, Any]] = scratch.summary["players"]
        return players

    def _summarized(self, events: Events, booked: bool, now: datetime) -> Events:
        """A won match announces every player's numbers of its summary."""
        if not any(kind == "match_won" for kind, _ in events):
            return events
        if booked:
            assert self.summary is not None
            players = self.summary["players"]
        else:
            players = self._settled(now)
        return [
            (
                kind,
                {**payload, "summary": copy.deepcopy(players)}
                if kind == "match_won"
                else payload,
            )
            for kind, payload in events
        ]

    # -- undo ------------------------------------------------------------------

    def checkpoint(self) -> dict[str, Any]:
        """The game as it is, to come back to before the next visit is booked,
        with the darts that were on the board when the leg or the drill began:
        they count for no visit."""
        saved = copy.deepcopy(self.stored())
        saved["on_board"] = self._skip
        saved.update(self.mode.checkpoint())
        return saved

    def rewind(
        self,
        checkpoint: dict[str, Any],
        visit: list[dict[str, Any]],
        positions: list[tuple[float, float] | None],
        now: datetime,
    ) -> None:
        """Back to a checkpoint, with the darts of its visit thrown again.

        What the darts announced was announced before; only a correction that
        changes it announces anew.
        """
        self.mode = GameMode(self)
        self.restore(checkpoint)
        # Darts that counted for no visit before the undo count for none after it.
        self._visit, self._skip = [], checkpoint.get("on_board", 0)
        self._announced = None
        self.mode.rewind(checkpoint)
        self.track(visit, positions, now=now)

    # -- state -----------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        seat = self.bot_seat
        common = {
            "double_out": self.double_out,
            **{rule: getattr(self, rule) for rule in X01_RULES},
            "players": len(self.players),
            "legs_to_win": self.legs_to_win,
            "sets_to_win": self.sets_to_win,
            # Copies: Home Assistant keeps the attributes of every state it wrote.
            "legs": [dict(leg) for leg in self.legs],
            "summary": copy.deepcopy(self.summary),
            # The training game shows itself here.
            "drill": None,
            "double_in": self.double_in,
            "bull_off": self._bull_off_snapshot(),
            "teams": self._teams_snapshot(),
            "bot": None
            if seat is None
            else {"player": seat + 1, "level": self.bot_level},
        }
        return self.mode.snapshot(common)

    # -- analysis ----------------------------------------------------------------

    def booking(self) -> Booking:
        """The visit that finish_visit books next, for the players' statistics.

        Every dart of the visit comes with its position and, where the game
        knows it, the bed it was aimed at; the darts that count for the player
        at the board follow from the start and end of the booked darts.
        """
        visit = list(self._visit)
        booking = Booking(
            visit=visit,
            positions=[
                self._positions[index] if index < len(self._positions) else None
                for index in range(len(visit))
            ],
            aims=[None] * len(visit),
            start=self._skip,
            end=self._skip + len(self._thrown()),
        )
        thrown = self._thrown()
        # A match counts no darts after its end.
        if not thrown or (self.mode.playing and self.winner is not None):
            return booking
        if self.bulling:
            booking.player = self.bulling.thrower
            booking.game = "bull_off"
            booking.end = booking.start + 1
            booking.aims[booking.start] = "BULL"
        else:
            self.mode.booking(booking, thrown)
        booking.name = None if booking.player is None else self._name(booking.player)
        return booking


@dataclass
class Booking:
    """A visit as the practice game books it, see PracticeGame.booking."""

    visit: list[dict[str, Any]]
    # Positions and aimed beds, one per dart of the visit.
    positions: list[tuple[float, float] | None]
    aims: list[str | None]
    # The darts from start to end count for the player at the board, if any.
    start: int = 0
    end: int = 0
    player: int | None = None
    name: str | None = None
    game: int | str | None = None
    # X01 points the visit scores, nothing for a bust.
    scored: int | None = None
    # The numbers of the Cricket game being played.
    cricket: tuple[int, ...] = ()
    # A Shanghai: a single, double and treble of the round's number.
    shanghai: bool = False
    # The score the visit checked out in the checkout training.
    checkout: int | None = None

    @property
    def darts(self) -> list[dict[str, Any]]:
        return self.visit[self.start : self.end]

    @property
    def booked_positions(self) -> list[tuple[float, float] | None]:
        return self.positions[self.start : self.end]

    @property
    def booked_aims(self) -> list[str | None]:
        return self.aims[self.start : self.end]
