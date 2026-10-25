"""Golf, Baseball and Count-Up: rounds for everybody, extra rounds after a tie."""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.homedarts.board import RADIUS_MM, TREBLE_MM
from custom_components.homedarts.party import (
    Baseball,
    CountUp,
    Golf,
    golf_strokes,
    inner_single,
    make_party,
)
from custom_components.homedarts.practice import PracticeGame

from .local_helpers import NOW, dart, throw


def darts(*names: str) -> list[dict]:
    return [dart(name) for name in names]


def single(number: int, inner: bool | None) -> dict:
    return {**dart(f"S{number}"), "inner": inner}


def test_golf_strokes_by_bed():
    # The double is the hole in one, the treble two strokes.
    assert golf_strokes(dart("D3"), 3) == 1
    assert golf_strokes(dart("T3"), 3) == 2
    assert golf_strokes(single(3, True), 3) == 3
    assert golf_strokes(single(3, False), 3) == 4
    # Without a position the board saw, a single counts as an outer single.
    assert golf_strokes(single(3, None), 3) == 4
    assert golf_strokes(dart("T4"), 3) == 5
    assert golf_strokes(dart("MISS"), 3) == 5


def test_inner_singles_lie_inside_the_treble_ring():
    assert inner_single(None) is None
    assert inner_single((0.0, 0.3)) is True
    assert inner_single((0.4, 0.5)) is False
    # The middle of the board's treble ring, 97 to 107 mm from the centre,
    # splits them.
    assert TREBLE_MM == (97, 107)
    assert inner_single((0.0, 101.9 / RADIUS_MM)) is True
    assert inner_single((0.0, 102.1 / RADIUS_MM)) is False


def test_the_last_dart_of_a_golf_visit_counts():
    golf = Golf(1)
    assert golf.target(0) == "1" and golf.rounds == 9
    assert golf.visit(0, []).points == [0]
    assert golf.visit(0, darts("D1", "MISS")).points == [5]
    # A player stops after a good dart by pulling the darts.
    result = golf.book(0, darts("MISS", "D1"))
    assert result.points == [1] and result.hits == 1 and result.won is None
    assert golf.round == 2 and golf.details(0) == {"scorecard": [1]}


def test_a_golf_hole_passed_without_a_dart_is_a_miss():
    golf = Golf(1)
    result = golf.book(0, [])
    assert result.points == [5] and result.darts == 0 and result.hits == 0
    assert golf.details(0) == {"scorecard": [5]} and golf.round == 2


def test_golf_is_won_with_the_fewest_strokes_after_the_last_hole():
    golf = make_party("golf", 2, 18)
    assert isinstance(golf, Golf) and golf.rounds == 18
    golf = make_party("golf", 2, 9)
    for hole in range(1, 9):
        golf.book(0, darts(f"D{hole}"))
        golf.book(1, darts(f"T{hole}"))
    assert golf.book(0, darts("T9")).won is None
    result = golf.book(1, darts("D9"))
    assert result.won == 0 and golf.points == [10, 17]


def test_a_tie_plays_extra_holes_among_the_tied_players():
    golf = Golf(3, 1)
    golf.new_leg(3, 1)
    # Player 2 starts; players 2 and 3 tie at the top with a treble each.
    assert golf.next(0) == 1
    golf.book(1, darts("T1"))
    golf.book(2, darts("T1"))
    assert golf.book(0, darts("S2")).won is None
    assert golf.playoff() == [1, 2] and golf.round == 2
    assert golf.target(1) == "2" and golf.next(0) == 1
    golf.book(1, darts("D2"))
    assert golf.next(1) == 2
    result = golf.book(2, darts("D2"))
    assert result.won is None and golf.round == 3
    golf.book(1, darts("T3"))
    assert golf.book(2, darts("D3")).won == 2


def test_extra_rounds_go_on_from_one_after_twenty():
    golf = Golf(2, 20)
    for _ in range(19):
        golf.book(0, darts("MISS"))
        golf.book(1, darts("MISS"))
    assert golf.target(0) == "20"
    golf.book(0, darts("MISS"))
    golf.book(1, darts("MISS"))
    assert golf.target(0) == "1" and golf.playoff() == [0, 1]


def test_baseball_scores_runs_on_the_number_of_the_inning():
    baseball = Baseball(2)
    assert baseball.rounds == 9
    result = baseball.book(0, darts("T1", "S1", "D2"))
    assert result.points == [4, 0] and result.hits == 2
    # The bull scores no runs.
    assert baseball.book(1, darts("BULL", "D1")).points == [4, 2]
    assert baseball.round == 2 and baseball.details(1) == {"scorecard": [2]}


def test_a_tied_baseball_game_plays_extra_innings():
    baseball = Baseball(2)
    for _ in range(9):
        baseball.book(0, darts("MISS"))
        baseball.book(1, darts("MISS"))
    assert baseball.playoff() == [0, 1] and baseball.target(0) == "10"
    baseball.book(0, darts("S10"))
    assert baseball.book(1, darts("T10")).won == 1


def test_count_up_adds_every_dart_for_its_rounds():
    count_up = make_party("count_up", 1, 2)
    assert isinstance(count_up, CountUp) and count_up.rounds == 2
    assert count_up.target(0) is None
    assert count_up.book(0, darts("T20", "MISS", "25")).hits == 2
    assert count_up.book(0, darts("S1")).won == 0 and count_up.points == [86]
    assert make_party("count_up", 2).rounds == 8


def test_the_scorecard_keeps_the_score_of_every_round():
    count_up = CountUp(1, 3)
    for names in (("S20", "MISS"), ("T20",), ("S1", "S2", "S3")):
        count_up.book(0, darts(*names))
    assert count_up.scorecard == [[20, 60, 6]] and count_up.points == [86]
    assert count_up.turns == 3 and count_up.hits == [5]


def test_rounds_games_restore_their_state_and_ignore_nonsense():
    golf = Golf(3, 9)
    golf.book(0, darts("D1"))
    saved = json.loads(json.dumps(golf.stored()))
    restored = Golf(3, 9)
    restored.restore(saved)
    assert restored.stored() == golf.stored()
    restored.restore(
        {
            **saved,
            "round": 0,
            "lineup": [0, 0],
            "thrown": 5,
            "scorecard": [[1], [-1], []],
        }
    )
    assert restored.stored() == golf.stored()
    restored.restore({**saved, "lineup": [], "scorecard": [[1]]})
    assert restored.lineup == [0, 1, 2] and restored.scorecard == [[1], [], []]
    restored.restore(None)
    assert restored.stored() == golf.stored()


def test_a_rounds_game_takes_every_field_of_the_store_whatever_it_held():
    # The second player starts the leg: the lineup differs from a new game's.
    stored = Golf(2, 9)
    stored.new_leg(2, 1)
    saved = json.loads(json.dumps(stored.stored()))
    used = Golf(2, 9)
    for player in (0, 1, 0):
        used.book(player, darts("S1"))
    assert (used.current_round, used.thrown, used.lineup) == (2, 1, [0, 1])
    used.restore(saved)
    assert used.stored() == stored.stored()
    assert (used.current_round, used.thrown, used.lineup) == (1, 0, [1, 0])


def test_a_rounds_game_stored_after_its_last_round_stays_decided():
    count_up = CountUp(2, 1)
    count_up.book(0, darts("S20"))
    assert count_up.book(1, darts("S1")).won == 0
    saved = json.loads(json.dumps(count_up.stored()))
    # Everybody has thrown in the last round, which decided the leg.
    assert saved["thrown"] == 2 and saved["round"] == 1
    restored = CountUp(2, 1)
    restored.restore(saved)
    assert restored.stored() == count_up.stored()


@pytest.mark.parametrize(
    "lineup", [[True, 0], [0, 2], [-1, 0], [0, 0], [], "10", [0.0, 1], [1.0]]
)
def test_a_rounds_game_takes_only_a_lineup_of_its_own_players(lineup):
    golf = Golf(2, 9)
    golf.restore({"lineup": [1, 0]})
    golf.restore({"lineup": lineup})
    assert golf.lineup == [1, 0]


@pytest.mark.parametrize(
    ("field", "value", "nonsense"),
    [
        ("thrown", 2, [3, -1, True, "1"]),
        ("round", 3, [0, -1, True, "2"]),
    ],
)
def test_a_rounds_game_keeps_its_round_and_turn_without_a_count_of_them(
    field, value, nonsense
):
    for wrong in nonsense:
        golf = Golf(2, 9)
        golf.restore({field: value})
        golf.restore({field: wrong})
        assert golf.stored()[field] == value


def rounds_game(kind: str, players: int = 2) -> PracticeGame:
    practice = PracticeGame()
    practice.set_players(players)
    practice.play(kind)
    return practice


def test_a_golf_leg_in_the_practice_game_uses_the_dart_positions():
    practice = rounds_game("golf")
    snapshot = practice.snapshot()
    assert snapshot["game"] == "golf" and snapshot["rounds"] == 9
    practice.set_rounds(golf_holes=18)
    snapshot = practice.snapshot()
    assert snapshot["rounds"] == 18 and snapshot["round"] == 1
    assert snapshot["target"] == "1" and snapshot["playoff"] is None
    # An inner single: three strokes, as the board's position tells.
    practice.track([dart("S1")], [(0.0, 0.3)], now=NOW)
    assert practice.snapshot()["points"] == 3
    events = practice.finish_visit(now=NOW)
    assert events == [
        (
            "turn_changed",
            {
                "game": "golf",
                "player": 2,
                "name": None,
                "players": 2,
                "remaining": None,
                "checkout": None,
                "setup": None,
                "points": 0,
                "target": "1",
            },
        )
    ]
    practice.track([dart("S1")], [(0.0, 0.8)], now=NOW)
    practice.finish_visit(now=NOW)
    practice.track([], now=NOW)
    scores = practice.snapshot()["scores"]
    assert [score["scorecard"] for score in scores] == [[3], [4]]
    assert practice.snapshot()["round"] == 2


def test_a_golf_leg_ends_with_leg_won_after_the_last_hole():
    practice = rounds_game("golf", 1)
    practice.set_rounds(golf_holes=9)
    for hole in range(1, 9):
        throw(practice, f"D{hole}")
    events = throw(practice, "T9")
    assert events == [
        (
            "leg_won",
            {
                "game": "golf",
                "player": 1,
                "name": None,
                "players": 1,
                "darts": 9,
                "points": 10,
                "legs": 1,
                "sets": 0,
                "match": False,
            },
        )
    ]
    assert practice.legs[0]["points"] == 10 and practice.legs_total == 1


@pytest.mark.parametrize(
    ("kind", "points"),
    [("golf", 5), ("baseball", 0), ("count_up", 0), ("shanghai", 0)],
)
def test_a_party_game_passes_a_visit_without_darts_as_three_misses(kind, points):
    practice = rounds_game(kind)
    assert practice.passes()
    ((event, turn),) = practice.finish_visit(empty=True, now=NOW)
    assert event == "turn_changed" and turn["player"] == 2
    assert practice.snapshot()["scores"][0]["points"] == points
    assert practice.players[0].darts == 0


def test_halve_it_halves_a_visit_passed_without_darts():
    practice = rounds_game("halve_it")
    practice.finish_visit(empty=True, now=NOW)
    assert practice.party.points == [20, 40]


def test_count_up_rounds_are_an_option_and_restart_the_game():
    practice = rounds_game("count_up", 1)
    practice.set_rounds(count_up_rounds=3)
    assert practice.snapshot()["rounds"] == 3 and practice.party.rounds == 3
    practice.set_rounds(count_up_rounds=99)
    assert practice.count_up_rounds == 3
    # Only a change of its own rounds starts the game anew.
    throw(practice, "T20")
    practice.set_rounds(golf_holes=18, count_up_rounds=3)
    assert practice.party.points == [60]
    practice.set_rounds(count_up_rounds=4)
    assert practice.party.points == [0] and practice.party.rounds == 4
    practice.set_rounds(count_up_rounds=3)
    throw(practice, "T20")
    throw(practice, "T20")
    events = throw(practice, "T20")
    assert events[0][0] == "leg_won" and events[0][1]["points"] == 180
    # Another game keeps the options; the stored game brings them back.
    practice.play("baseball")
    restored = PracticeGame()
    restored.restore(json.loads(json.dumps(practice.stored())))
    assert restored.count_up_rounds == 3 and restored.golf_holes == 18
    assert restored.party.kind == "baseball" and restored.party.rounds == 9
    restored.restore({"game": "count_up", "count_up_rounds": 0, "golf_holes": 10})
    assert restored.count_up_rounds == 8 and restored.golf_holes == 18


@settings(max_examples=60, deadline=None)
@given(
    kind=st.sampled_from(["golf", "baseball", "count_up"]),
    players=st.integers(1, 4),
    visits=st.lists(
        st.lists(st.sampled_from(["T1", "D2", "S3", "S20", "T20", "MISS"]), max_size=3),
        max_size=120,
    ),
)
def test_rounds_games_always_end_with_one_winner(kind, players, visits):
    practice = rounds_game(kind, players)
    for visit in visits:
        before = practice.legs_total
        events = throw(practice, *visit) if visit else []
        won = [event for event in events if event[0] == "leg_won"]
        assert len(won) == practice.legs_total - before <= 1
        snapshot = practice.snapshot()
        assert all(score["points"] >= 0 for score in snapshot["scores"])
        assert snapshot["round"] >= 1
