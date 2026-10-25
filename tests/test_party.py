"""Party games, X01 variants and the bull-off."""

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.homedarts.board import distance_mm
from custom_components.homedarts.party import (
    GOLF_HOLES,
    GOTCHA_TARGETS,
    HALVE_IT_START,
    KILLER_LIVES,
    MAX_ROUNDS,
    PARTY_GAMES,
    WORLD_ORDERS,
    BullOff,
    PartyGame,
    make_party,
)
from custom_components.homedarts.practice import (
    MAX_PLAYERS,
    PARTY_PLAYERS,
    PracticeGame,
)
from custom_components.homedarts.scoring import MODES

from .local_helpers import NOW, dart, throw


def game_of(kind: str | int, players: int = 1, **names: str) -> PracticeGame:
    game = PracticeGame()
    game.set_players(players)
    for index, name in names.items():
        game.set_name(int(index[1:]) - 1, name)
    game.play(kind)
    return game


def kinds(events: list) -> list[str]:
    return [kind for kind, _ in events]


def darts_of(*names: str) -> list[dict]:
    return [dart(name) for name in names]


def missed(number: int) -> dict:
    """A miss next to a number, as the board reports it."""
    return {"number": number, "multiplier": 0, "name": f"M{number}"}


def test_x01_starts_from_101_to_1001():
    for start in (101, 901, 1001):
        assert game_of(start).snapshot()["remaining"] == start
    assert game_of(401).snapshot()["game"] is None


def test_double_in_scores_from_the_first_double():
    game = game_of(301)
    game.double_in = True
    game.new_match()
    game.track([dart("S20"), dart("T20")], now=NOW)
    snapshot = game.snapshot()
    assert snapshot["remaining"] == 301 and snapshot["opened"] is False
    assert snapshot["checkout"] is None
    throw(game, "S20", "T20")
    # The single before the double scores nothing; the double and later darts do.
    throw(game, "S1", "D10", "T20")
    player = game.players[0]
    assert player.remaining == 221 and player.opened is True
    assert (player.first9_darts, player.first9_points) == (5, 80)
    assert game.snapshot()["scores"][0]["opened"] is True


def test_a_bust_takes_the_opening_double_back():
    game = game_of(301)
    game.double_in = True
    game.new_match()
    game.players[0].remaining = 50
    game.track([dart("D20"), dart("T20")], now=NOW)
    # The card shows the double taken back while the bust is on the board.
    assert game.snapshot()["opened"] is False
    assert game.snapshot()["scores"][0]["opened"] is False
    assert kinds(game.finish_visit(now=NOW)) == ["turn_changed"]
    assert game.players[0].remaining == 50 and game.players[0].opened is False


def test_shanghai_wins_at_once_with_single_double_and_treble():
    game = game_of("shanghai", 2, p1="Alex", p2="Sam")
    assert game.snapshot()["target"] == "1" and game.snapshot()["round"] == 1
    throw(game, "S1", "D1", "S5")
    throw(game, "T1")
    snapshot = game.snapshot()
    assert [score["points"] for score in snapshot["scores"]] == [3, 3]
    assert snapshot["target"] == "2" and snapshot["round"] == 2
    events = throw(game, "S2", "T2", "D2")
    assert kinds(events) == ["leg_won", "match_won"]
    won = dict(events)["leg_won"]
    assert (won["game"], won["name"], won["points"], won["darts"]) == (
        "shanghai",
        "Alex",
        15,
        6,
    )
    assert game.snapshot()["winner"] == 1


def test_shanghai_ends_after_seven_rounds_and_a_tie_replays_the_leg():
    game = game_of("shanghai")
    for number in range(1, 7):
        assert throw(game, f"S{number}") == []
    events = throw(game, "D7")
    assert kinds(events) == ["leg_won"]
    assert dict(events)["leg_won"]["points"] == sum(range(1, 7)) + 14
    # The next leg starts again at the 1.
    assert game.snapshot()["target"] == "1"

    tied = game_of("shanghai", 2)
    for _ in range(7):
        throw(tied, "MISS")
        throw(tied, "MISS")
    assert tied.winner is None and tied.starter == 1
    assert tied.snapshot()["player"] == 2 and tied.snapshot()["round"] == 1


def test_shanghai_counts_no_miss_next_to_the_number():
    game = game_of("shanghai", 2)
    game.track([missed(1), missed(1), dart("S1")], now=NOW)
    assert game.snapshot()["points"] == 1
    game.finish_visit(now=NOW)
    game.track([], now=NOW)
    assert game.party.hits == [1, 0] and game.party.points == [1, 0]
    # A miss next to the number completes no Shanghai either.
    game.party.restore({"turns": 2})
    game.track([dart("S2"), dart("D2"), missed(2)], now=NOW)
    assert game.snapshot()["won"] is False and game.snapshot()["darts"] == 3


def test_halve_it_halves_a_round_without_a_hit():
    game = game_of("halve_it")
    assert game.snapshot()["points"] == HALVE_IT_START
    throw(game, "S15", "T15", "MISS")
    assert game.snapshot()["points"] == 100 and game.snapshot()["target"] == "16"
    throw(game, "S5", "S5", "S5")
    assert game.snapshot()["points"] == 50 and game.snapshot()["target"] == "D"
    throw(game, "D10")
    assert game.snapshot()["points"] == 70 and game.snapshot()["target"] == "17"
    # Pulling the darts early after a miss halves as well.
    throw(game, "S5")
    assert game.snapshot()["points"] == 35 and game.snapshot()["target"] == "18"
    throw(game, "T18")
    throw(game, "T5")
    throw(game, "S19")
    throw(game, "S20")
    # The bull round is named by its number: the outer bull and the bullseye count.
    assert game.snapshot()["target"] == "25"
    events = throw(game, "25", "BULL")
    assert kinds(events) == ["leg_won"]
    # 35 + 54 + 15 (any treble) + 19 + 20 + 75 (the bull)
    assert dict(events)["leg_won"]["points"] == 218


def test_killer_needs_two_players():
    game = game_of("killer")
    snapshot = game.snapshot()
    assert snapshot["needs_players"] == 2 and snapshot["target"] is None
    assert throw(game, "D20") == [] and game.party.numbers == [None]


def test_killer_picks_numbers_then_the_killers_take_lives():
    game = game_of("killer", 3, p1="Alex", p2="Sam", p3="Kim")
    assert game.snapshot()["phase"] == "choose"
    throw(game, "S7")
    # Sam hits the 7 as well: taken, so Sam throws again.
    throw(game, "S7")
    assert game.snapshot()["player"] == 2
    throw(game, "S12")
    throw(game, "BULL")
    throw(game, "S3")
    snapshot = game.snapshot()
    assert snapshot["phase"] == "play" and snapshot["player"] == 1
    assert [score["number"] for score in snapshot["scores"]] == [7, 12, 3]
    assert snapshot["target"] == "D7"
    # Alex becomes a killer and hunts the others from the next dart on.
    game.track([dart("D7")], now=NOW)
    assert game.snapshot()["target"] is None
    # ... and takes two of Sam's lives.
    throw(game, "D7", "D12", "D12")
    scores = game.snapshot()["scores"]
    assert scores[0]["killer"] is True and scores[1]["lives"] == KILLER_LIVES - 2
    throw(game, "S1")
    throw(game, "D3")
    # A killer hitting their own double loses a life.
    throw(game, "D12", "D7")
    scores = game.snapshot()["scores"]
    assert scores[1]["lives"] == 0 and scores[0]["lives"] == KILLER_LIVES - 1
    # Sam is out: Kim throws next.
    assert game.snapshot()["player"] == 3
    throw(game, "S1")
    events = throw(game, "D3", "D3", "D3")
    assert kinds(events) == ["leg_won", "match_won"]
    assert dict(events)["leg_won"]["name"] == "Alex"


def test_killer_numbers_need_a_bed_of_the_number():
    game = game_of("killer", 2)
    # A miss next to the 7 picks nothing: throw again.
    game.track([missed(7)], now=NOW)
    game.finish_visit(now=NOW)
    game.track([], now=NOW)
    assert game.party.numbers == [None, None] and game.snapshot()["player"] == 1
    throw(game, "T7")
    assert game.party.numbers == [7, None]


def test_a_killer_out_of_lives_does_nothing_with_the_rest_of_the_visit():
    game = game_of("killer", 3)
    game.party.restore(
        {"numbers": [1, 2, 3], "lives": [1, 3, 3], "killers": [True, False, False]}
    )
    # The own double takes the last life; the next double would make a killer
    # again and the last one would take a life of player 2.
    throw(game, "D1", "D1", "D2")
    assert game.party.lives == [0, 3, 3]
    assert game.party.killers == [False, False, False]
    assert game.snapshot()["player"] == 2


def test_darts_after_the_winning_dart_do_not_count():
    game = game_of("killer", 2)
    game.party.restore({"numbers": [1, 2], "lives": [3, 1], "killers": [True, False]})
    game.track([dart("D2")], now=NOW)
    assert game.snapshot()["darts"] == 1
    game.track([dart("D2"), dart("S5"), dart("S5")], now=NOW)
    snapshot = game.snapshot()
    assert snapshot["won"] and snapshot["darts"] == 1
    events = game.finish_visit(now=NOW)
    assert kinds(events) == []
    assert game.players[0].darts == 1 and game.legs[0]["darts"] == 1


def test_only_killers_take_lives_and_a_killer_can_lose_the_last_one():
    game = game_of("killer", 2, p1="Alex", p2="Sam")
    throw(game, "S7")
    throw(game, "S12")
    # Alex is no killer yet: Sam's double takes no life.
    throw(game, "D12")
    assert game.party.lives == [KILLER_LIVES] * 2
    throw(game, "MISS")
    game.party.killers[0], game.party.lives[0] = True, 1
    # With the last life, Alex hits the own double: Sam is the last one left.
    events = game.track([dart("D7")], now=NOW)
    assert kinds(events) == ["leg_won", "match_won"]
    assert dict(events)["leg_won"]["name"] == "Sam"
    alex = game.snapshot()["scores"][0]
    assert alex["lives"] == 0 and alex["killer"] is False


def test_a_correction_can_take_a_shanghai_back():
    game = game_of("shanghai", 2)
    shanghai = [dart("S1"), dart("D1"), dart("T1")]
    assert kinds(game.track(shanghai, now=NOW)) == ["leg_won", "match_won"]
    # The board corrects the treble to a single: no Shanghai after all.
    assert game.track([dart("S1"), dart("D1"), dart("S1")], now=NOW) == []
    assert game.snapshot()["winner"] is None
    assert kinds(game.finish_visit(now=NOW)) == ["turn_changed"]
    assert game.snapshot()["player"] == 2 and game.winner is None


def test_killer_turns_skip_players_who_picked_or_are_out():
    killer = make_party("killer", 3)
    killer.restore({"numbers": [7, None, 3]})
    # Whoever still needs a number picks next; a failed pick is thrown again.
    assert killer.next(2) == 1
    assert killer.next(1) == 1
    killer.restore({"numbers": [7, 12, 3], "lives": [0, 2, 0]})
    assert killer.next(1) == 1
    # A stored leg without anybody alive keeps the turn instead of failing.
    killer.restore({"lives": [0, 0, 0]})
    assert killer.next(2) == 2


def test_a_party_game_without_usable_scores_starts_the_leg_fresh():
    game = game_of("killer", 2)
    throw(game, "S5")
    saved = game.stored()
    saved["party"] = "broken"
    restored = PracticeGame()
    restored.restore(saved)
    assert restored.party.kind == "killer"
    assert restored.party.numbers == [None, None]
    assert restored.party.lives == [KILLER_LIVES] * 2


def test_a_restored_bull_off_drops_throws_it_cannot_trust():
    kept = BullOff.restored(
        {
            "order": [2, 0],
            "index": 1,
            "hits": {"2": "25"},
            "distances": {"2": 5},
            "rethrow": True,
        },
        3,
    )
    assert kept.index == 1 and kept.distances == {2: 5.0} and kept.hits == {2: "25"}
    assert kept.thrower == 0 and kept.rethrow
    unmeasured = BullOff.restored(
        {"order": [0, 1], "index": 1, "hits": {"0": "BULL"}, "distances": {"0": None}},
        2,
    )
    assert unmeasured.index == 1 and unmeasured.distances == {0: None}
    for saved in (
        # Up to version 1.5, only the distances were kept: the round starts again.
        {"order": [0, 1, 2], "index": 2, "distances": {"0": 11.0, "1": 0.0}},
        {"order": [0, 1, 2], "index": 2, "hits": "broken", "distances": "broken"},
        # Player 3 has not thrown yet; player 2 threw no bed and no distance.
        {
            "order": [0, 1, 2],
            "index": 2,
            "hits": {"0": "25", "1": 5, "2": "BULL"},
            "distances": {"0": 11.0, "1": True, "x": 1.0},
        },
    ):
        restored = BullOff.restored(saved, 3)
        assert restored.index == 0 and restored.distances == {} and restored.hits == {}
        assert restored.thrower == 0 and not restored.rethrow


@pytest.mark.parametrize(
    "order",
    [
        [],
        (0, 1),
        3,
        # Every player once, each one at the board: 2 is the third of three.
        [0, 2],
        [0, 0],
        [-1, 0],
        [True, 0],
        [0.0, 1],
    ],
)
def test_a_bull_off_with_an_order_of_other_players_starts_anew(order):
    assert BullOff.restored({"order": order, "index": 0}, 2) is None


def test_a_restored_bull_off_counts_only_the_darts_of_players_who_threw():
    # The first of three threw; every other entry belongs to nobody who threw.
    restored = BullOff.restored(
        {
            "order": [2, 0, 1],
            "index": 1,
            "hits": {"2": "S20", "0": "BULL", "x": "25", "-1": "25"},
            "distances": {"2": 40, "1": 2.0, "x": 1.0, "-1": 3.0},
        },
        3,
    )
    assert (restored.index, restored.thrower) == (1, 0)
    assert restored.hits == {2: "S20"} and restored.distances == {2: 40.0}
    assert type(restored.distances[2]) is float and restored.rethrow is False


@pytest.mark.parametrize(
    ("index", "distance"),
    [
        # The index of the next thrower: the first is 0, one past the last is none.
        (0, 2.0),
        (2, 2.0),
        (-1, 2.0),
        (True, 2.0),
        ("1", 2.0),
        (None, 2.0),
        # A distance that is no number, or True, is no distance the board measured.
        (1, "far"),
        (1, True),
    ],
)
def test_a_bull_off_with_an_index_or_distance_it_cannot_trust_starts_anew(
    index, distance
):
    restored = BullOff.restored(
        {
            "order": [1, 0],
            "index": index,
            "hits": {"1": "25", "0": "BULL"},
            "distances": {"1": distance, "0": 1.0},
        },
        2,
    )
    assert type(restored.index) is int and restored.index == 0
    assert restored.hits == {} and restored.distances == {}
    assert restored.thrower == 1


def test_a_bull_off_decides_who_starts():
    game = PracticeGame()
    game.bull_off = True
    game.set_players(2)
    game.play(501)
    assert game.snapshot()["bull_off"]["player"] == 1
    assert throw(game, "25") == [
        (
            "turn_changed",
            {
                "game": 501,
                "player": 2,
                "name": None,
                "players": 2,
                "remaining": None,
                "checkout": None,
                "bull_off": True,
            },
        )
    ]
    game.track([dart("BULL")], now=NOW)
    throws = game.snapshot()["bull_off"]["throws"]
    assert throws == [
        {"player": 1, "name": None, "distance": None, "hit": "25"},
        {"player": 2, "name": None, "distance": None, "hit": "BULL"},
    ]
    events = throw(game, "BULL")
    assert events[0] == (
        "bull_off_won",
        {
            "game": 501,
            "player": 2,
            "name": None,
            "players": 2,
            "distance": None,
            "hit": "BULL",
        },
    )
    assert events[1][1]["player"] == 2 and events[1][1]["remaining"] == 501
    snapshot = game.snapshot()
    assert snapshot["bull_off"] is None and snapshot["player"] == 2
    assert [score["remaining"] for score in snapshot["scores"]] == [501, 501]


def test_the_same_bull_bed_throws_again_in_reverse_order():
    bull_off = BullOff([0, 1, 2])
    assert bull_off.book(dart("BULL"), (0.01, 0.0)) is None
    assert bull_off.book(dart("BULL"), (0.03, 0.0)) is None
    assert bull_off.book(dart("S20"), None) is None
    # Only the two in the bullseye throw again, the last one first; the
    # official rules do not measure inside the bed.
    assert bull_off.order == [1, 0] and bull_off.index == 0 and bull_off.rethrow
    assert bull_off.book(dart("25"), (0.05, 0.0)) is None
    assert bull_off.book(dart("BULL"), None) == 0
    assert distance_mm((0.03, 0.04)) == 8.5 and distance_mm(None) is None


def test_beds_decide_before_distances_and_a_measured_dart_beats_one_without():
    bull_off = BullOff([0, 1])
    bull_off.book(dart("S20"), (0.1, 0.0))
    # Outside the bull, the measured distance decides: 17 against 34 mm.
    assert bull_off.book(dart("S1"), (0.2, 0.0)) == 0
    # A dart the board did not measure, entered by hand, loses there.
    bull_off = BullOff([0, 1])
    bull_off.book(dart("S1"), None)
    assert bull_off.book(dart("S20"), (0.9, 0.0)) == 1
    # Two darts without a position cannot be told apart: both throw again.
    bull_off = BullOff([0, 1])
    bull_off.book(dart("S20"), None)
    assert bull_off.book(dart("S1"), None) is None and bull_off.order == [1, 0]
    # The outer bull beats every other bed, however close.
    bull_off = BullOff([0, 1])
    bull_off.book(dart("25"), None)
    assert bull_off.book(dart("S20"), (0.1, 0.0)) == 0


def test_a_dart_off_the_board_loses_to_any_bed():
    bull_off = BullOff([0, 1, 2])
    bull_off.book(dart("MISS"), None)
    bull_off.book(dart("S20"), (0.95, 0.0))
    # A miss the board measured close to the bull still comes last.
    assert bull_off.book(dart("MISS"), (0.0, 1.05)) == 1
    # Everybody off the board: all of them throw again, the last one first.
    bull_off = BullOff([0, 1])
    bull_off.book(dart("MISS"), (0.0, 1.02))
    assert bull_off.book(dart("MISS"), (0.0, 1.2)) is None
    assert bull_off.order == [1, 0] and bull_off.rethrow


def test_by_distance_the_closer_dart_in_the_same_bull_bed_wins():
    bull_off = BullOff([0, 1])
    bull_off.book(dart("BULL"), (0.03, 0.0), True)
    assert bull_off.book(dart("BULL"), (0.0, -0.02), True) == 1
    # Inside the bull, only measured darts are compared: both throw again.
    bull_off = BullOff([0, 1])
    bull_off.book(dart("BULL"), (0.03, 0.0), True)
    assert bull_off.book(dart("BULL"), None, True) is None
    assert bull_off.order == [1, 0]
    # Equally close throws again, too.
    bull_off = BullOff([0, 1])
    bull_off.book(dart("25"), (0.05, 0.0), True)
    assert bull_off.book(dart("25"), (0.0, 0.05), True) is None


def test_the_bull_off_rule_and_a_rethrow_show_in_the_snapshot():
    game = PracticeGame()
    game.bull_off = True
    game.set_players(2)
    game.play(501)
    throw(game, "BULL")
    game.track([dart("BULL")], [(0.02, 0.0)], now=NOW)
    snapshot = game.snapshot()["bull_off"]
    assert snapshot["rethrow"] is False and snapshot["by_distance"] is False
    assert snapshot["throws"][1] == {
        "player": 2,
        "name": None,
        "distance": 3.4,
        "hit": "BULL",
    }
    assert kinds(game.finish_visit(now=NOW)) == ["turn_changed"]
    game.track([], now=NOW)
    snapshot = game.snapshot()["bull_off"]
    assert snapshot["rethrow"] and snapshot["player"] == 2
    assert [item["player"] for item in snapshot["throws"]] == [2, 1]
    assert snapshot["throws"][0]["hit"] is None
    game.bull_off_distance = True
    throw(game, "BULL")
    game.track([dart("BULL")], [(0.0, 0.01)], now=NOW)
    events = game.finish_visit(now=NOW)
    # Player 2 threw without a position: the darts cannot be compared, so again.
    assert kinds(events) == ["turn_changed"] and game.bulling.order == [0, 1]
    game.track([], now=NOW)
    game.track([dart("BULL")], [(0.02, 0.0)], now=NOW)
    game.finish_visit(now=NOW)
    game.track([], now=NOW)
    game.track([dart("BULL")], [(0.0, 0.01)], now=NOW)
    events = game.finish_visit(now=NOW)
    assert events[0] == (
        "bull_off_won",
        {
            "game": 501,
            "player": 2,
            "name": None,
            "players": 2,
            "distance": 1.7,
            "hit": "BULL",
        },
    )
    assert game.starter == game.set_starter == 1


def test_party_games_and_the_bull_off_survive_a_restart():
    game = game_of("killer", 2)
    game.bull_off = True
    game.new_match()
    throw(game, "25")
    restored = PracticeGame()
    restored.restore(game.stored())
    assert restored.stored() == game.stored()
    assert restored.bulling is not None and restored.bulling.distances == {0: None}
    assert restored.bulling.hits == {0: "25"}
    throw(restored, "BULL")
    throw(restored, "S5")
    throw(restored, "S9")
    saved = restored.stored()
    again = PracticeGame()
    again.restore(saved)
    # Player 2 won the bull-off, so player 2 picked first.
    assert again.party.numbers == [9, 5] and again.snapshot()["phase"] == "play"
    saved["party"] = {"numbers": [5, 5], "lives": [9, 1], "killers": "x"}
    saved["bulling"] = {"order": [0, 0]}
    again.restore(saved)
    assert again.party.numbers == [None, None] and again.bulling is None
    assert again.party.lives == [KILLER_LIVES] * 2


BEDS = [
    "S1",
    "D1",
    "T1",
    "S2",
    "D2",
    "T2",
    "S3",
    "D7",
    "D12",
    "S15",
    "T15",
    "BULL",
    "25",
    "MISS",
]


@given(
    st.sampled_from(["shanghai", "halve_it", "killer"]),
    st.integers(1, MAX_PLAYERS),
    st.booleans(),
    st.lists(st.lists(st.sampled_from(BEDS), min_size=1, max_size=3), max_size=60),
)
def test_any_party_game_keeps_its_scores_consistent(kind, players, bull_off, visits):
    game = game_of(kind, players)
    game.bull_off = bull_off
    game.new_match()
    for visit in visits:
        throw(game, *visit)
        snapshot = game.snapshot()
        assert 1 <= snapshot["player"] <= players
        for score in snapshot["scores"]:
            assert score["points"] >= 0
            if kind == "killer":
                assert 0 <= score["lives"] <= KILLER_LIVES
        if (
            kind == "killer"
            and snapshot["phase"] == "play"
            and snapshot["winner"] is None
        ):
            # Nobody who is out ever throws.
            assert snapshot["scores"][snapshot["player"] - 1]["lives"] > 0


@pytest.mark.parametrize("starter", [3, -1, True, "1", None])
def test_a_party_game_starts_with_the_first_player_unless_the_store_names_one(
    starter,
):
    shanghai = make_party("shanghai", 3)
    shanghai.restore({"starter": 2})
    assert shanghai.starter == 2
    shanghai.restore({"starter": starter})
    assert shanghai.starter == 0


@pytest.mark.parametrize(
    "counts",
    [[True, 0], [2.5, 0], [-1, 0], ["3", 0], [3], [3, 0, 0], "3"],
)
def test_party_points_and_hits_take_only_a_whole_count_for_every_player(counts):
    shanghai = make_party("shanghai", 2)
    shanghai.restore({"points": [4, 0], "hits": [2, 0]})
    shanghai.restore({"points": counts, "hits": counts})
    assert (shanghai.points, shanghai.hits) == ([4, 0], [2, 0])


@pytest.mark.parametrize(("turns", "kept"), [(0, 0), (5, 5), (-3, 0), ("5", 0)])
def test_party_turns_are_a_count_from_zero(turns, kept):
    shanghai = make_party("shanghai", 2)
    shanghai.restore({"turns": 7})
    shanghai.restore({"turns": turns})
    assert shanghai.turns == kept
    shanghai.restore({})
    assert shanghai.turns == 0


def test_killer_numbers_are_numbers_of_the_board_and_lives_are_three_at_most():
    killer = make_party("killer", 2)
    killer.restore({"numbers": [1, 20], "lives": [0, KILLER_LIVES]})
    assert killer.numbers == [1, 20] and killer.lives == [0, KILLER_LIVES]
    for numbers in ([True, None], [21, None], [0, None], [2.0, None], [5, 5]):
        killer = make_party("killer", 2)
        killer.restore({"numbers": numbers})
        assert killer.numbers == [None, None]
    for lives in ([KILLER_LIVES + 1, 1], [-1, 1], [True, 1], [1]):
        killer = make_party("killer", 2)
        killer.restore({"lives": lives})
        assert killer.lives == [KILLER_LIVES] * 2


def test_killer_details_and_targets_follow_the_number_and_the_killer():
    killer = make_party("killer", 3)
    killer.restore({"numbers": [7, None, 3], "killers": [True, False, False]})
    assert killer.details(0) == {"number": 7, "lives": KILLER_LIVES, "killer": True}
    assert killer.details(1) == {"number": None, "lives": KILLER_LIVES, "killer": False}
    # A killer aims at the doubles of the others, and nobody before a number.
    assert [killer.target(player) for player in range(3)] == [None, None, "D3"]


@pytest.mark.parametrize(("name", "number"), [("S1", 1), ("T20", 20), ("BULL", None)])
def test_killer_numbers_are_picked_from_1_to_20(name, number):
    killer = make_party("killer", 2)
    assert killer.book(0, darts_of(name)).numbers == [number, None]


def test_a_killer_dart_counts_after_darts_that_do_nothing():
    killer = make_party("killer", 3)
    killer.restore({"numbers": [5, 7, 9]})
    killer.book(0, darts_of("S1", "D9", "D5"))
    # D9 takes no life from a player who is no killer yet; D5 makes them one.
    assert killer.killers == [True, False, False] and killer.lives == [3, 3, 3]
    # A player out of lives has none to lose.
    killer.restore({"lives": [3, 0, 3]})
    assert killer.book(0, darts_of("D7", "D9")).lives == [3, 0, 2]


def test_gotcha_counts_the_darts_that_score():
    gotcha = make_party("gotcha", 2)
    assert gotcha.book(0, darts_of("S20", "MISS", "T1")).hits == 2
    assert gotcha.book(1, darts_of("MISS")).hits == 0
    assert gotcha.hits == [2, 0]


@pytest.mark.parametrize(("points", "kept"), [(301, True), (302, False)])
def test_gotcha_keeps_scores_up_to_its_target(points, kept):
    gotcha = make_party("gotcha", 2, target=301)
    gotcha.restore({"points": [points, 12]})
    assert gotcha.points == ([points, 12] if kept else [0, 0])


VISIT_BEDS = [
    *(f"{bed}{number}" for bed in "SDT" for number in range(1, 21)),
    "25",
    "BULL",
    "MISS",
]
VISITS = st.lists(st.lists(st.sampled_from(VISIT_BEDS), max_size=3), max_size=40)


@st.composite
def party_setups(draw) -> tuple[str, int, int | None, dict]:
    """A party game, its players, and the options it takes."""
    kind = draw(st.sampled_from(PARTY_GAMES))
    players = draw(st.integers(2 if kind == "killer" else 1, PARTY_PLAYERS))
    rounds, options = None, {}
    if kind == "golf":
        rounds = draw(st.sampled_from(GOLF_HOLES))
    elif kind == "count_up":
        rounds = draw(st.integers(1, MAX_ROUNDS))
    elif kind == "bermuda":
        options = {"halve": draw(st.booleans())}
    elif kind == "round_the_world":
        options = {"order": draw(st.sampled_from(WORLD_ORDERS))}
    elif kind == "gotcha":
        options = {
            "target": draw(st.integers(*GOTCHA_TARGETS)),
            "out_mode": draw(st.sampled_from(MODES)),
        }
    return kind, players, rounds, options


def play(
    game: PartyGame,
    player: int,
    visits: list[list[str]],
    decided: bool = False,
    new_legs: bool = True,
) -> tuple[int, bool, list]:
    """Book the visits in turn: the next player after each, and after a decided
    leg a new one, which the next player starts, or the end of the play. The
    player at the board, whether the leg is decided, and what every visit made."""
    results = []
    for visit in visits:
        if decided:
            if not new_legs:
                break
            player = (game.starter + 1) % game.players
            game.new_leg(game.players, player)
            decided = False
        result = game.book(player, [dart(name) for name in visit])
        results.append(result)
        if result.won is None:
            player = game.next(player)
        else:
            decided = True
    return player, decided, results


def state(game: PartyGame) -> tuple:
    """Everything the cards and the announcements show of a party game."""
    players = range(game.players)
    return (
        game.stored(),
        [game.details(player) for player in players],
        [game.target(player) for player in players],
        [game.announced(player) for player in players],
        (game.round, game.shown_round, game.playoff(), game.choosing),
    )


@given(party_setups(), VISITS, VISITS, VISITS)
def test_a_restored_party_game_plays_on_as_the_stored_one(
    setup, before, elsewhere, after
):
    kind, players, rounds, options = setup
    game = make_party(kind, players, rounds, **options)
    player, decided, _ = play(game, 0, before)
    # The store keeps the game as JSON. A restart restores it into a game just
    # made, and every field it keeps replaces what a game held before.
    saved = json.loads(json.dumps(game.stored()))
    fresh = make_party(kind, players, rounds, **options)
    fresh.restore(saved)
    used = make_party(kind, players, rounds, **options)
    play(used, 0, elsewhere)
    used.restore(saved)
    for copy in (fresh, used):
        assert state(copy) == state(game)
    played = play(game, player, after, decided, new_legs=False)
    for copy in (fresh, used):
        assert play(copy, player, after, decided, new_legs=False) == played
        assert state(copy) == state(game)


BULL_OFF_BEDS = ["BULL", "25", "S20", "T5", "D1", "MISS"]


@st.composite
def bull_off_throws(draw) -> tuple[list[int], list]:
    """An order of the players and the darts they throw at the bull."""
    players = draw(st.integers(1, PARTY_PLAYERS))
    order = draw(st.permutations(range(players)))
    position = st.none() | st.tuples(st.floats(-1.2, 1.2), st.floats(-1.2, 1.2))
    darts = draw(
        st.lists(st.tuples(st.sampled_from(BULL_OFF_BEDS), position), max_size=30)
    )
    return list(order), darts


@given(bull_off_throws(), st.integers(0, 30), st.booleans())
def test_a_restored_bull_off_goes_on_as_the_stored_one(throws, split, by_distance):
    order, darts = throws
    bull_off = BullOff(order)
    for name, position in darts[:split]:
        if bull_off.book(dart(name), position, by_distance) is not None:
            # Decided: the match starts, and nothing is left to restore.
            return
    saved = json.loads(json.dumps(bull_off.stored()))
    restored = BullOff.restored(saved, len(order))
    assert restored.stored() == bull_off.stored()
    for name, position in darts[split:]:
        winner = bull_off.book(dart(name), position, by_distance)
        assert restored.book(dart(name), position, by_distance) == winner
        assert restored.stored() == bull_off.stored()
        if winner is not None:
            break
