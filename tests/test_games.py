"""The games of a board on their own: BoardGames without Home Assistant.

These tests need no hass fixture, so each one runs in milliseconds; the tests
of the entities and actions play the same engine through Home Assistant.
"""

import ast
import random
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from custom_components.homedarts.games import (
    ActionRefused,
    BoardGames,
    _throw_positions,
)
from custom_components.homedarts.moments import parse_moment, stamp

from .local_helpers import BULL, S20, T20, board

NOW = datetime(2026, 10, 1, 20, 0, tzinfo=UTC)
GAMES = Path(__file__).parents[1] / "custom_components" / "homedarts" / "games.py"


class Reports:
    """The weekly report and the journal, as far as the games use them."""

    def __init__(self) -> None:
        self.counted: list[str] = []
        self.booked: list[str] = []
        self.rewound: list[dict] = []
        self.forgotten: list[str] = []

    def observe(self, events, now, booked=None):
        assert now == NOW
        self.counted += [kind for kind, _ in events]
        self.booked += [kind for kind, _ in booked or []]

    def checkpoint(self):
        return {"counted": len(self.counted)}

    def rewind(self, checkpoint):
        self.rewound.append(checkpoint)

    def forget(self, name):
        self.forgotten.append(name)


def takeout():
    """The darts are pulled: the board reports the takeout without darts."""
    return board(status="Takeout", event="Takeout started")


def single_20():
    """A dart in the single 20, as entered by hand."""
    return {"name": "S20", "number": 20, "multiplier": 1}


def kinds(announced):
    """The types of the events and their sources."""
    return [(kind, source) for kind, _, source in announced]


def play(games, *states, source="websocket", data=None):
    """Follow the states of the board; the events they bring, and the data
    the entities show."""
    data = {} if data is None else data
    announced = []
    for state in states:
        announced += games.follow_visit(data, state, source, NOW)
    return announced, data


def match(*names, **setup):
    """X01 501 for the players, with the board as it stands between visits."""
    games = BoardGames(Reports(), NOW, random.Random(1))
    games.start_game(501, names=list(names), **setup)
    play(games, board())
    return games


def visit(games, *hits):
    """A visit of three darts that are then pulled."""
    darts = [board(*hits[:count]) for count in range(1, len(hits) + 1)]
    return play(games, *darts, takeout(), board())[0]


def remaining(games):
    return [score["remaining"] for score in games.practice.snapshot()["scores"]]


def refusal(action):
    with pytest.raises(ActionRefused) as refused:
        action()
    return refused.value.key, refused.value.placeholders


def _imports(module: str) -> tuple[set[str], set[str]]:
    """What a module of the integration imports: the modules from outside it,
    and the integration's own modules that it imports relatively."""
    tree = ast.parse((GAMES.parent / f"{module}.py").read_text(encoding="utf-8"))
    outside: set[str] = set()
    own: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            if node.module:
                own.add(node.module.split(".")[0])
            else:
                own.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            outside.add(node.module or "")
        elif isinstance(node, ast.Import):
            outside.update(alias.name for alias in node.names)
    return outside, own


@pytest.mark.mutation_unsafe
def test_the_engine_imports_nothing_of_home_assistant():
    """Neither games.py nor a module it holds, directly or through another
    one, imports Home Assistant."""
    found: dict[str, set[str]] = {}
    waiting = [GAMES.stem]
    while waiting:
        module = waiting.pop()
        if module not in found:
            found[module], own = _imports(module)
            waiting.extend(own)
    # The classes BoardGames holds, and what they build on.
    assert {"training", "practice", "profiles", "drills", "tournament"} <= set(found)
    assert {
        module: sorted(name for name in names if name.split(".")[0] == "homeassistant")
        for module, names in found.items()
        if any(name.split(".")[0] == "homeassistant" for name in names)
    } == {}


def test_positions_come_only_from_states_training_accepts():
    state_ = board(T20, S20, BULL)
    state_["throws"][0]["coords"] = {"x": float("nan"), "y": 0.1}
    state_["throws"][1]["coords"] = {"x": 0.2, "y": -0.3}
    state_["throws"][2]["coords"] = {"x": True, "y": 0.0}
    assert _throw_positions(state_) == [None, (0.2, -0.3), None]
    assert _throw_positions({**state_, "numThrows": 5}) is None
    assert _throw_positions({"numThrows": 0}) == []


def test_darts_name_the_game_and_the_player_at_the_board():
    games = match("Alex", "Kim")
    announced, data = play(games, board(T20))
    assert kinds(announced) == [("dart_detected", "websocket")]
    attributes = announced[0][1]
    assert (attributes["game"], attributes["name"], attributes["score"]) == (
        501,
        "Alex",
        60,
    )
    # The entities show the visit with its darts numbered and the games.
    assert [throw["dart"] for throw in data["throws"]] == [1]
    assert data["practice"]["undo"] is False
    # Raised once by the start of the game, once by the dart.
    assert data["revision"] == games.revision == 2
    assert {"training", "practice", "quality"} <= data.keys()


def test_a_state_that_changes_nothing_keeps_the_revision():
    games = match("Alex")
    _, data = play(games, board(T20))
    revision = games.revision
    assert play(games, board(T20), data=data)[0] == []
    assert games.revision == revision


def test_a_visit_is_booked_once_its_darts_are_pulled():
    games = match("Alex", "Kim")
    reports = games._reports
    announced = visit(games, T20, T20, T20)
    assert ("visit_thrown", "websocket") in kinds(announced)
    completed = kinds(announced).index(("visit_completed", "websocket"))
    # The booking follows the visit: the next player is at the board.
    assert ("turn_changed", "websocket") in kinds(announced)[completed:]
    assert remaining(games) == [321, 501]
    assert games.practice.thrower == "Kim"
    assert "visit_completed" in reports.counted
    assert games.practice_snapshot()["undo"] is True


def test_an_undone_visit_comes_back_with_the_game_from_before_it():
    games = match("Alex", "Kim")
    reports = games._reports
    visit(games, T20, T20, T20)
    checkpoint = {"counted": reports.counted.index("visit_completed")}
    assert games.undo_visit(NOW) == [
        (
            "visit_undone",
            {
                "darts": 3,
                "score": 180,
                "segments": ["T20", "T20", "T20"],
                "game": 501,
                "name": "Alex",
            },
            "manual",
        )
    ]
    assert reports.rewound == [checkpoint]
    _, data = play(games, board(), source="manual")
    # The darts are the visit again, which is not booked.
    assert [throw["dart"] for throw in data["throws"]] == [1, 2, 3]
    assert remaining(games) == [321, 501]
    assert games.practice.thrower == "Alex"
    # One visit back, and no further.
    assert refusal(lambda: games.undo_visit(NOW)) == ("undo_unavailable", {})


def test_a_change_made_in_home_assistant_cannot_be_undone_visit_by_visit():
    games = match("Alex", "Kim")
    visit(games, T20, T20, T20)
    revision = games.revision
    assert games.changed([], NOW) == []
    assert games.revision == revision + 1
    snapshots = games.snapshots()
    assert snapshots["practice"]["undo"] is False
    assert snapshots["revision"] == games.revision
    assert snapshots["training"] == games.training.snapshot()


def test_a_visit_without_darts_passes_only_in_a_game():
    games = match("Alex", "Kim")
    announced = games.next_player(NOW)
    assert ("turn_changed", "manual") in kinds(announced)
    assert games.practice.thrower == "Kim"
    assert refusal(lambda: BoardGames(Reports(), NOW).next_player(NOW)) == (
        "empty_visit",
        {},
    )


def test_the_next_player_pulls_no_darts_of_the_visit():
    games = match("Alex", "Kim")
    play(games, board(T20))
    assert games.next_player(NOW) == []
    # The visit ends with the next state of the board, here still with its dart.
    announced, _ = play(games, board(T20), source="manual")
    assert ("visit_completed", "manual") in kinds(announced)
    assert games.practice.thrower == "Kim"


def test_darts_entered_by_hand_need_the_keypad_and_a_visit_with_room():
    games = match("Alex", "Kim")
    assert refusal(lambda: games.throw_dart(single_20())) == ("manual_entry_off", {})
    games.practice.manual_entry = True
    for _ in range(3):
        games.throw_dart(single_20())
        play(games, board(), source="manual")
    assert refusal(lambda: games.throw_dart(single_20())) == ("visit_full", {})


def test_a_visit_entered_as_its_score_needs_an_x01_visit_without_darts_on_the_board():
    games = BoardGames(Reports(), NOW)
    games.practice.manual_entry = True
    assert refusal(lambda: games.enter_visit(board(), 60)) == ("visit_not_x01", {})
    games = match("Alex")
    games.practice.manual_entry = True
    assert refusal(lambda: games.enter_visit(board(T20), 60)) == ("visit_on_board", {})
    assert refusal(lambda: games.enter_visit(board(), 0, checkout=True)) == (
        "checkout_impossible",
        {"remaining": "501"},
    )
    games.throw_dart(single_20())
    games.enter_visit(board(), 100)
    # The visit replaces the darts entered by hand before it, and ends.
    play(games, board(), source="manual")
    games.manual.end_visit()
    announced, _ = play(games, board(), source="manual")
    assert ("visit_completed", "manual") in kinds(announced)
    assert remaining(games) == [401]


def test_only_darts_of_the_visit_can_be_corrected_and_never_the_bots():
    games = match("Alex", bot_level=5)
    assert refusal(lambda: games.correct_dart(1, single_20())) == (
        "no_dart",
        {"dart": "1"},
    )
    play(games, board(T20))
    games.correct_dart(1, single_20())
    announced, _ = play(games, board(T20), source="manual")
    assert kinds(announced) == [("dart_corrected", "manual")]
    visit(games, T20, T20, T20)
    assert games.practice.bot_up
    games.bot_step()
    play(games, board(), source="bot")
    assert refusal(lambda: games.correct_dart(1, single_20())) == ("bot_dart", {})
    games.practice.manual_entry = True
    assert refusal(lambda: games.throw_dart(single_20())) == ("bot_turn", {})


def test_the_bot_throws_the_rest_of_its_visit_when_a_player_throws():
    games = match("Alex", bot_level=5)
    visit(games, T20, T20, T20)
    assert games.practice.bot_up
    games.bot_step()
    play(games, board(), source="bot")
    assert games.manual.bot_darts() == 1
    assert not games.interrupts_bot(board())
    assert games.interrupts_bot(board(S20))
    announced, _ = play(games, board(S20))
    sources = [source for _, _, source in announced]
    # The bot's darts and its booked visit come first, then the player's dart.
    assert sources.count("bot") >= 3
    assert sources[-1] == "websocket"
    assert not games.practice.bot_up
    assert remaining(games)[1] < 501


def test_the_bot_ends_its_visit_after_its_darts():
    games = match("Alex", bot_level=5)
    visit(games, T20, T20, T20)
    for _ in range(3):
        games.bot_step()
        play(games, board(), source="bot")
    assert games.practice.bot_up
    games.bot_step()
    announced, _ = play(games, board(), source="bot")
    assert ("visit_completed", "bot") in kinds(announced)
    assert not games.practice.bot_up


def test_the_bot_throws_as_seeded():
    def bot_darts(seed):
        games = BoardGames(Reports(), NOW, random.Random(seed))
        games.start_game(501, names=["Alex"], bot_level=3)
        play(games, board())
        visit(games, T20, T20, T20)
        for _ in range(3):
            games.bot_step()
        return [extra.dart for extra in games.manual.extras]

    assert bot_darts(7) == bot_darts(7)


def test_the_games_restore_what_they_stored():
    games = match("Alex", "Kim")
    visit(games, T20, T20, T20)
    restored = BoardGames(Reports(), NOW)
    restored.restore(games.stored(), NOW)
    assert restored.stored() == games.stored()
    assert restored.practice.snapshot() == games.practice.snapshot()
    for broken in (None, ["not", "stored", "games"]):
        fresh = BoardGames(Reports(), NOW)
        fresh.restore(broken, NOW)
        assert fresh.practice.game == 0
        assert fresh.training.history == []
        assert fresh.tournament.tournament is None


def test_a_deleted_player_is_forgotten_everywhere():
    games = match("Alex", "Kim")
    visit(games, T20, T20, T20)
    assert games.delete_player("Alex") is True
    assert games._reports.forgotten == ["Alex"]
    assert "Alex" not in games.practice.names
    assert games.delete_player("Alex") is False
    assert games._reports.forgotten == ["Alex"]


@pytest.mark.parametrize(
    ("change", "anew"),
    [
        (lambda games: games.set_practice_option("double_in", True), True),
        (lambda games: games.set_practice_option("double_out", False), False),
        (lambda games: games.set_x01_rule("in_mode", "double"), True),
        (lambda games: games.set_x01_rule("out_mode", "master"), False),
    ],
)
def test_a_setting_that_changes_how_a_match_starts_starts_it_anew(change, anew):
    games = match("Alex", "Kim")
    visit(games, T20, T20, T20)
    change(games)
    assert remaining(games) == ([501, 501] if anew else [321, 501])


def test_a_game_takes_only_valid_player_names():
    games = BoardGames(Reports(), NOW)
    assert refusal(lambda: games.start_game(501, names=["Alex", "#Kim"])) == (
        "invalid_player_name",
        {},
    )
    assert games.practice.game == 0


def test_a_tournament_match_waits_until_the_board_is_free():
    games = BoardGames(Reports(), NOW)
    play(games, board())
    assert games.board_free()
    play(games, board(T20))
    assert not games.board_free()


def test_the_games_keep_the_time_of_a_step_in_utc():
    """As Home Assistant's clock in UTC wrote it, so stored games read alike."""
    evening = datetime(2026, 10, 1, 22, 0, tzinfo=timezone(timedelta(hours=2)))
    assert stamp(evening) == "2026-10-01T20:00:00+00:00"
    assert parse_moment(stamp(evening)) == evening
    assert parse_moment("soon") is None
    assert parse_moment(None) is None
