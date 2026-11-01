"""Practice games under any mix of darts, corrections, settings and restarts,
with the bot, passes and undone visits; and the visit as Home Assistant knows
it, with corrections and darts entered by hand, for the training session."""

import json
import random

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    rule,
)

from custom_components.homedarts.board import bed_name
from custom_components.homedarts.bot import Bot, aim
from custom_components.homedarts.cricket import CRICKET_GAMES, MARKS_TO_CLOSE
from custom_components.homedarts.drills import DRILLS, RESULTS
from custom_components.homedarts.manual import ManualDarts, parse_bed
from custom_components.homedarts.party import KILLER_LIVES
from custom_components.homedarts.practice import (
    GAMES,
    MAX_LEGS,
    MAX_PLAYERS,
    MAX_SETS,
    OPTIONS,
    X01_RULES,
    PracticeGame,
)
from custom_components.homedarts.scoring import BULL_MODES, MODES, STRAIGHT
from custom_components.homedarts.training import TrainingSession, segments

from .local_helpers import NOW, dart

KINDS = [
    *(101, 301, "cricket", "cut_throat", "tactics"),
    *("random_cricket", "hidden_cricket"),
    *("shanghai", "halve_it", "killer", "golf", "baseball", "count_up"),
    *("bermuda", "round_the_world", "gotcha"),
    *DRILLS,
]
STARTS = [0, 0, 2, 40, 101, 301, 501, 1001]
BEDS = [
    *("T20", "T19", "T15", "T3", "T1", "S20", "S19", "S15", "S3", "S2", "S1"),
    *("D20", "D19", "D16", "D8", "D7", "D3", "D2", "D1", "BULL", "25", "MISS"),
]
POSITIONS = st.one_of(
    st.none(),
    st.tuples(st.floats(-0.1, 0.1), st.floats(-0.1, 0.1)),
)
# Round limits short enough to end legs, and none.
ROUNDS = [0, 0, 1, 2, 3]
RULES = st.fixed_dictionaries(
    {
        "in_mode": st.sampled_from(MODES),
        "out_mode": st.sampled_from(MODES),
        "bull_mode": st.sampled_from(BULL_MODES),
        "max_rounds": st.sampled_from(ROUNDS),
    }
)


def stored_as_json(game: PracticeGame) -> dict:
    """What Home Assistant's store keeps: JSON, with text keys."""
    return json.loads(json.dumps(game.stored()))


class PracticeMachine(RuleBasedStateMachine):
    """A board where darts land, get corrected and pulled while players change
    the game, its rules and its format, and Home Assistant restarts."""

    def __init__(self) -> None:
        super().__init__()
        self.game = PracticeGame()
        self.darts: list[str] = []
        self.positions: list[tuple[float, float] | None] = []
        # The game before the last visit was booked, with that visit.
        self.checkpoint: tuple[dict, list[str], list] | None = None

    def _track(self) -> None:
        self.game.track(
            [dart(name) for name in self.darts], list(self.positions), now=NOW
        )

    @initialize(
        kind=st.sampled_from(KINDS),
        players=st.integers(1, MAX_PLAYERS),
        legs=st.integers(1, 3),
        sets=st.integers(1, 2),
        bull_off=st.booleans(),
        teams=st.booleans(),
        starts=st.lists(st.sampled_from(STARTS), min_size=4, max_size=4),
        rules=RULES,
    )
    def start(self, kind, players, legs, sets, bull_off, teams, starts, rules) -> None:
        self.game.bull_off = bull_off
        self.game.teams = teams
        for key, value in rules.items():
            self.game.set_rule(key, value)
        for index, start in enumerate(starts):
            self.game.set_start(index, start)
        self.game.set_players(players)
        self.game.set_format(legs, sets)
        self.game.play(kind)

    @rule(bed=st.sampled_from(BEDS), position=POSITIONS)
    def throw(self, bed, position) -> None:
        if len(self.darts) == 3:
            self.pull_darts()
        self.darts.append(bed)
        self.positions.append(position)
        self._track()

    def _aimed(self, choice: int) -> str:
        """The bed the game suggests: the checkout, the target or a double."""
        snapshot = self.game.snapshot()
        if self.game.bulling:
            return ("BULL", "25", "S20")[choice]
        drill = snapshot["drill"]
        if drill and "remaining" in drill:
            # The checkout drills name the score to finish, not a bed.
            route = drill["checkout"] or f"T{20 - choice}"
            return str(route.split()[0])
        if snapshot.get("checkout"):
            return str(snapshot["checkout"].split()[0])
        target = (drill or snapshot).get("target")
        if target:
            bed = {"D": "D20", "T": "T20", "25": "BULL", "50": "BULL"}.get(
                target, target
            )
            return f"{'SDT'[choice]}{bed}" if bed.isdigit() else str(bed)
        others = [
            score["number"]
            for score in snapshot.get("scores", [])
            if score["player"] != snapshot["player"] and score.get("lives")
        ]
        if snapshot["game"] == "killer" and snapshot["phase"] == "play" and others:
            return f"D{others[choice % len(others)]}"
        return f"T{20 - choice}"

    @rule(choices=st.lists(st.integers(0, 2), min_size=1, max_size=3))
    def aim(self, choices) -> None:
        """A visit at what the game suggests, so that legs and matches end."""
        for choice in choices:
            if len(self.darts) == 3:
                break
            self.darts.append(self._aimed(choice))
            self.positions.append(None if choice else (0.01 * len(self.darts), 0.0))
            self._track()
        self.pull_darts()

    @rule(index=st.integers(0, 2), bed=st.sampled_from(BEDS))
    def correct(self, index, bed) -> None:
        if self.darts:
            self.darts[index % len(self.darts)] = bed
            self._track()

    @rule()
    def pull_darts(self) -> None:
        if self.darts:
            self.checkpoint = (
                self.game.checkpoint(),
                list(self.darts),
                list(self.positions),
            )
        self.game.finish_visit(now=NOW)
        self.darts, self.positions = [], []
        self._track()

    @rule(level=st.sampled_from([0, 0, 19, 20, 60, 120]))
    def bot(self, level) -> None:
        self.game.set_bot(level)
        self.checkpoint = None

    @rule(seed=st.integers(0, 2**16))
    def bot_visit(self, seed) -> None:
        """The bot throws its visit where it aims, like the coordinator lets it."""
        if self.darts:
            self.pull_darts()
        if not self.game.bot_up:
            return
        bot = Bot(random.Random(seed))
        while True:
            snapshot = self.game.snapshot()
            thrown = len(self.darts)
            if snapshot["bull_off"] and thrown:
                break
            if thrown == 3 or snapshot.get("bust") or snapshot.get("won"):
                break
            dart, position = bot.throw(
                aim(snapshot),
                self.game.bot_level,
                cricket=snapshot["game"] in CRICKET_GAMES,
            )
            self.darts.append(bed_name(dart["number"], dart["multiplier"]))
            self.positions.append(position)
            self._track()
        self.pull_darts()

    @rule()
    def pass_turn(self) -> None:
        """Next player without darts: X01, the Cricket and the party games pass."""
        if not self.darts:
            passes = self.game.passes()
            assert bool(self.game.finish_visit(empty=True, now=NOW)) == passes

    @rule()
    def undo(self) -> None:
        """The last visit comes back, with the game as it was before it."""
        if self.checkpoint is None or self.darts:
            return
        saved, darts, positions = self.checkpoint
        self.checkpoint = None
        self.game.rewind(saved, [dart(name) for name in darts], positions, now=NOW)
        self.darts, self.positions = darts, positions
        self._track()

    @rule(
        change=st.sampled_from(
            ["option", "rule", "format", "game", "leg", "start", "rounds"]
        ),
        option=st.sampled_from(OPTIONS),
        enabled=st.booleans(),
        kind=st.sampled_from(KINDS),
        legs=st.integers(0, MAX_LEGS + 1),
        sets=st.integers(0, MAX_SETS + 1),
        players=st.integers(0, MAX_PLAYERS + 1),
        start=st.sampled_from([*STARTS, 1, 1002]),
        name=st.sampled_from(X01_RULES),
        rules=RULES,
    )
    def change(
        self, change, option, enabled, kind, legs, sets, players, start, name, rules
    ) -> None:
        """A rule, the format, the game or a new leg, as the entities set them."""
        game = self.game
        if change == "rule":
            # As the coordinator does: but for the Out mode, a rule starts anew.
            if game.set_rule(name, rules[name]) and name != "out_mode":
                game.new_match()
        elif change == "option":
            # As the coordinator does: double in, the bull-off and teams start anew.
            game.set_option(option, enabled)
            if option in ("double_in", "bull_off", "teams"):
                game.new_match()
        elif change == "format":
            game.set_format(legs, sets)
            game.set_players(players)
        elif change == "start":
            game.set_start(players, start)
        elif change == "rounds":
            game.set_rounds(9 + 9 * enabled, legs)
        elif change == "game":
            game.play(kind)
        else:
            game.new_leg()
        # A change of the game cannot be undone visit by visit.
        self.checkpoint = None

    @rule()
    def restart(self) -> None:
        """Home Assistant stops and starts; darts on the board do not count."""
        saved = stored_as_json(self.game)
        restored = PracticeGame()
        restored.restore(saved)
        # The store loads unchanged, byte for byte.
        assert json.dumps(restored.stored()) == json.dumps(saved)
        self.game = restored
        self.darts, self.positions = [], []
        self.checkpoint = None
        self._track()

    @invariant()
    def the_snapshot_is_consistent(self) -> None:
        game = self.game
        snapshot = game.snapshot()
        json.dumps(snapshot)
        if snapshot["game"] is None:
            return
        players = snapshot["players"]
        assert players == len(game.players)
        assert 1 <= snapshot["player"] <= players
        winner = snapshot["winner"]
        teams = snapshot["teams"]
        assert teams is None or (
            players == 4 and snapshot["game"] in (*GAMES, *CRICKET_GAMES)
        )

        def partners(first: int | None, second: int) -> bool:
            """The same player, or partners in a team."""
            if first is None:
                return False
            return first == second or bool(teams and (first - second) % 2 == 0)

        for score in snapshot["scores"]:
            assert 0 <= score["legs"] <= score["match_legs"]
            if players > 1:
                assert score["legs"] <= game.legs_to_win
                assert score["sets"] <= game.sets_to_win
            won = partners(winner, score["player"])
            # Only the winners have a won match, with every set it needed.
            assert won == (players > 1 and score["sets"] == game.sets_to_win)
            if snapshot["game"] in GAMES:
                assert 0 <= score["remaining"] <= score["start"]
                # Every leg can still be won: nobody stands on 1 with double or
                # master out.
                open_leg = winner is None and snapshot["out_mode"] != STRAIGHT
                assert not (open_leg and score["remaining"] == 1)
                # Nothing is left for the winners, but those of a round limit,
                # or for a checkout on the board.
                checkout = snapshot["won"] and partners(
                    snapshot["player"], score["player"]
                )
                limited = bool(game.legs and game.legs[0].get("rounds"))
                assert (score["remaining"] == 0) == ((won and not limited) or checkout)
            elif snapshot["game"] in CRICKET_GAMES:
                assert len(score["marks"]) == len(snapshot["numbers"])
                assert all(0 <= mark <= 3 for mark in score["marks"])
            else:
                assert score["points"] >= 0
                if snapshot["game"] == "killer":
                    assert 0 <= score["lives"] <= KILLER_LIVES
        assert snapshot["darts"] >= 0

    @invariant()
    def the_bot_sits_last_and_counts_for_nobody(self) -> None:
        game = self.game
        seat = game.bot_seat
        snapshot = game.snapshot()
        assert game.bot_level == 0 or 20 <= game.bot_level <= 120
        if seat is None:
            assert snapshot["bot"] is None
            assert game.humans == len(game.players)
            return
        assert seat == len(game.players) - 1 and 1 <= game.humans <= MAX_PLAYERS - 1
        assert snapshot["bot"] == {"player": seat + 1, "level": game.bot_level}
        assert snapshot["scores"][seat]["bot"] is True
        assert snapshot["scores"][seat]["name"] is None
        # The bot plays X01 and the Cricket games only.
        assert snapshot["game"] in (*GAMES, *CRICKET_GAMES)
        assert all(
            not match["players"][seat].get("name")
            for match in game.profiles.matches
            if len(match["players"]) > seat and match["players"][seat].get("bot")
        )

    @invariant()
    def the_bull_off_waits_for_everybody(self) -> None:
        bulling = self.game.bulling
        if bulling is not None:
            assert 0 <= bulling.index < len(bulling.order)
            assert set(bulling.hits) == set(bulling.distances)
            assert len(bulling.hits) == bulling.index
            # The dart at the bull scores for nobody.
            snapshot = self.game.snapshot()
            assert snapshot.get("visit", []) == []
            assert not snapshot.get("won") and not snapshot.get("bust")
            if snapshot["game"] in GAMES:
                assert snapshot["remaining"] == snapshot["start"]
            if snapshot["game"] in CRICKET_GAMES:
                assert snapshot["target"] is None

    @invariant()
    def a_leg_counts_for_the_match_once(self) -> None:
        """What the leg being played added to the match, a new leg takes back."""
        game = self.game
        for player, tally in zip(game.players, game.tallies, strict=True):
            assert player.match_darts >= player.darts
            assert player.match_marks >= player.marks_hit
            if game.game:
                assert player.match_points >= player.points
            for key in ("scores_100", "scores_140", "scores_180"):
                assert getattr(tally, key) >= getattr(player, key)

    @invariant()
    def the_round_limit_ends_a_leg_unless_the_lowest_score_is_a_tie(self) -> None:
        """Past the last round, a complete round leaves sides that share the
        lowest score; the leg goes on until one side alone has it."""
        game = self.game
        players = len(game.players)
        if not game.game or not game.max_rounds or game.winner is not None:
            return
        if game.leg_visits < game.max_rounds * players or game.leg_visits % players:
            return
        lowest = min(player.remaining for player in game.players)
        sides = {
            tuple(game._side(index))
            for index, player in enumerate(game.players)
            if player.remaining == lowest
        }
        assert len(sides) > 1

    @invariant()
    def a_drill_keeps_its_results(self) -> None:
        """A training game stays within its targets, and one that ended has its
        result among the last ten."""
        drill = self.game.snapshot()["drill"]
        if drill is None:
            return
        assert drill["drill"] == self.game.drill
        assert len(drill["results"]) <= RESULTS
        assert drill["results"] or not drill["finished"]
        if "progress" in drill:
            assert 0 <= drill["progress"] <= drill["targets"]

    @invariant()
    def a_team_with_the_bot_has_no_name(self) -> None:
        snapshot = self.game.snapshot()
        seat = self.game.bot_seat
        for team in snapshot.get("teams") or []:
            if seat is not None and seat + 1 in team["players"]:
                assert team["name"] is None

    @invariant()
    def nobody_wins_a_cricket_leg_unnoticed(self) -> None:
        """Between visits, nobody but the winner has everything closed with
        enough points: Cricket the most, Cut-Throat the fewest."""
        game = self.game
        if not game.cricket or self.darts or game.bulling or len(game.players) < 2:
            return
        teams = game.snapshot()["teams"] is not None

        def side(index: int) -> int:
            return index % 2 if teams else index

        for index, player in enumerate(game.players):
            others = [
                other.points
                for number, other in enumerate(game.players)
                if side(number) != side(index)
            ]
            closed = all(mark >= MARKS_TO_CLOSE for mark in player.marks)
            if game.cricket == "cut_throat":
                wins = closed and all(player.points <= other for other in others)
            else:
                wins = closed and all(player.points >= other for other in others)
            if wins:
                assert game.winner is not None
                assert side(game.winner) == side(index)


PracticeMachine.TestCase.settings = settings(
    max_examples=200, stateful_step_count=80, deadline=None
)
# 200 games take 10-25 s on a busy machine, and shrinking a failure takes longer:
# a generous limit lets a real failure show its example instead of a timeout.
TestPracticeMachine = pytest.mark.timeout(180)(PracticeMachine.TestCase)


def board_state(names: list[str], running: bool = True, status: str = "Throw") -> dict:
    """The board with these darts, as Board Manager reports it."""
    return {
        "running": running,
        "connected": True,
        "status": status if running else "Stopped",
        "event": status if running else "Stopped",
        "numThrows": len(names),
        "throws": [{"segment": dart(name)} for name in names],
    }


class VisitMachine(RuleBasedStateMachine):
    """A player against the bot: the board, corrections and darts entered by
    hand, passes and undone visits, followed by the training session and the
    practice game the way the coordinator follows them."""

    def __init__(self) -> None:
        super().__init__()
        self.board: list[str] = []
        self.running = True
        self.manual = ManualDarts()
        self.training = TrainingSession(NOW)
        self.game = PracticeGame()
        self.game.set_bot(60)
        self.game.play(301)
        self.bot = Bot(random.Random(0))
        self.effective: dict = {}
        self.undo_point: dict | None = None
        self.observe()

    def follow(self, state: dict) -> None:
        self.effective = self.manual.apply(state)
        for kind, attributes in self.training.observe(self.effective, now=NOW):
            if kind == "visit_completed":
                if not attributes.get("bot"):
                    self.undo_point = self.game.checkpoint()
                self.game.finish_visit(now=NOW)
        visit = self.training.visit()
        self.game.track(visit, [None] * len(visit), now=NOW)

    def observe(self, status: str = "Throw") -> None:
        state = board_state(self.board, self.running, status)
        if self.game.bot_up and self.manual.board_darts(state):
            # The player throws while the bot is at the board: it finishes first.
            before = self.manual.held(state)
            while not self.bot_done():
                self.bot_dart()
                self.follow(before)
            self.manual.end_visit()
            self.follow(before)
        self.follow(state)

    def bot_done(self) -> bool:
        snapshot = self.game.snapshot()
        thrown = self.manual.bot_darts()
        if snapshot["bull_off"]:
            return thrown >= 1
        return thrown >= 3 or snapshot["bust"] or snapshot["won"]

    def bot_dart(self) -> None:
        dart, position = self.bot.throw(aim(self.game.snapshot()), 60)
        self.manual.add(dart, position, "bot")

    @rule(bed=st.sampled_from(BEDS))
    def throw(self, bed) -> None:
        if self.running:
            self.board.append(bed)
            self.observe()

    @rule(index=st.integers(0, 3), bed=st.sampled_from(BEDS))
    def board_corrects(self, index, bed) -> None:
        if index < len(self.board):
            self.board[index] = bed
            self.observe()

    @rule(index=st.integers(0, 3))
    def board_withdraws(self, index) -> None:
        if index < len(self.board):
            del self.board[index]
            self.observe()

    @rule(keep=st.integers(0, 3), takeout=st.booleans())
    def pull(self, keep, takeout) -> None:
        """Darts pulled, all or some; the board may report the takeout."""
        self.board = self.board[:keep] if keep < len(self.board) else []
        self.observe("Takeout in progress" if takeout and self.board else "Throw")

    @rule()
    def toggle_detection(self) -> None:
        self.running = not self.running
        self.observe()

    @rule(bed=st.sampled_from(BEDS))
    def enter(self, bed) -> None:
        if len(self.training.visit()) < 3 and not self.game.bot_up:
            self.manual.add(parse_bed(bed), None, "manual")
            self.observe()

    @rule(index=st.integers(0, 2), bed=st.sampled_from(BEDS), position=POSITIONS)
    def correct(self, index, bed, position) -> None:
        slots = self.training.visit_slots()
        if index >= len(slots):
            return
        kind, place = self.manual.sources[slots[index]]
        if kind == "extra" and self.manual.extras[place].dart.get("bot"):
            return
        self.manual.correct(slots[index], parse_bed(bed), position)
        self.observe()

    @rule()
    def next_player(self) -> None:
        if self.training.visit() or self.manual.extras:
            self.manual.end_visit()
        elif self.game.passes():
            self.game.finish_visit(empty=True, now=NOW)
        self.observe()

    @rule()
    def bot_step(self) -> None:
        """The bot throws a dart or ends its visit, as its timer does."""
        if not self.game.bot_up:
            return
        if self.bot_done():
            self.manual.end_visit()
        else:
            self.bot_dart()
        self.observe()

    @rule()
    def undo(self) -> None:
        darts = self.training.undo_visit() if self.undo_point else None
        if self.undo_point is None or darts is None:
            return
        self.game.rewind(self.undo_point, darts, [None] * len(darts), now=NOW)
        self.manual.replay(darts, [None] * len(darts))
        self.undo_point = None
        self.observe()

    @invariant()
    def the_training_follows_the_visit_home_assistant_knows(self) -> None:
        darts = segments(self.effective)
        assert darts is not None and self.training._active == darts
        if self.effective["running"]:
            assert len(self.manual.sources) == len(darts)
        for place, fix in self.manual.fixes.items():
            assert self.manual._readings[place] == fix.reading

    @invariant()
    def a_corrected_dart_is_only_where_the_correction_puts_it(self) -> None:
        throws = self.effective.get("throws", [])
        for index, (kind, place) in enumerate(self.manual.sources):
            if kind == "board" and place in self.manual.fixes:
                position = self.manual.fixes[place].position
                expected = (
                    None if position is None else dict(zip("xy", position, strict=True))
                )
                assert throws[index].get("coords") == expected

    @invariant()
    def the_session_counts_every_dart_once(self) -> None:
        snapshot = self.training.snapshot()
        assert sum(snapshot["hits"].values()) == snapshot["darts"] >= 0
        assert 0 <= snapshot["manual_darts"] <= snapshot["darts"]
        assert all(snapshot[key] >= 0 for key in ("points", "visits", "misses"))
        # The bot's darts count for nobody.
        assert not any(
            dart.get("bot") and counting
            for dart, counting in zip(
                self.training._active, self.training._counting, strict=True
            )
        )

    @invariant()
    def the_game_stays_consistent(self) -> None:
        snapshot = self.game.snapshot()
        json.dumps(snapshot)
        assert snapshot["bot"] == {"player": 2, "level": 60}
        for score in snapshot["scores"]:
            assert 0 <= score["remaining"] <= 301


VisitMachine.TestCase.settings = settings(
    max_examples=150, stateful_step_count=60, deadline=None
)
TestVisitMachine = pytest.mark.timeout(180)(VisitMachine.TestCase)
