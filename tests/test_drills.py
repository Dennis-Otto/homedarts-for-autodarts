"""Training games: Around the Clock, doubles training, checkout training, Bob's 27."""

import random

from hypothesis import given
from hypothesis import strategies as st

from custom_components.homedarts.checkout import checkout
from custom_components.homedarts.drills import (
    BOBS_START,
    BOGEY_NUMBERS,
    CHECKOUT_SCORES,
    CHECKOUT_VISITS,
    TARGETS,
    BobsDrill,
    CheckoutDrill,
    TargetDrill,
)
from custom_components.homedarts.practice import PracticeGame

from .local_helpers import NOW, dart


def throw(drill, *names: str) -> list[tuple[str, dict]]:
    """Throw a visit dart by dart and pull the darts; return the events."""
    events = []
    for count in range(1, len(names) + 1):
        events += drill.track([dart(name) for name in names[:count]])
    events += drill.finish_visit(now=NOW)
    drill.track([])
    return events


def hits_in_order(doubles: bool) -> list[str]:
    beds = [f"{'D' if doubles else 'S'}{number}" for number in range(1, 21)]
    return [*beds, "BULL"]


def test_around_the_clock_counts_every_bed_of_the_target():
    drill = TargetDrill("around_the_clock")
    assert drill.snapshot()["target"] == "1"
    assert throw(drill, "T1", "S5", "D2") == []
    snapshot = drill.snapshot()
    assert snapshot["target"] == "3" and snapshot["progress"] == 2
    assert snapshot["darts"] == 3 and snapshot["hits"] == 2
    assert snapshot["hit_rate"] == 66.7


def test_around_the_clock_ends_on_the_bull_and_restarts_with_the_next_dart():
    drill = TargetDrill("around_the_clock")
    beds = hits_in_order(doubles=False)
    for start in range(0, 18, 3):
        assert throw(drill, *beds[start : start + 3]) == []
    events = throw(drill, "S19", "S20", "25")
    assert events == [
        (
            "drill_finished",
            {"drill": "around_the_clock", "darts": 21, "hits": 21, "hit_rate": 100.0},
        )
    ]
    snapshot = drill.snapshot()
    assert snapshot["finished"] and snapshot["target"] is None
    assert snapshot["best"] == 21 and len(snapshot["results"]) == 1
    drill.track([dart("S1")])
    assert drill.snapshot()["target"] == "2"


def test_around_the_clock_ends_on_the_25_where_both_bull_beds_count():
    drill = TargetDrill("around_the_clock")
    drill.index = len(TARGETS) - 1
    assert drill.snapshot()["target"] == "25"
    assert throw(drill, "BULL")[0][0] == "drill_finished"


def test_doubles_training_needs_the_double_ring_and_the_bullseye():
    drill = TargetDrill("doubles")
    throw(drill, "S1", "T1", "D1")
    assert drill.snapshot()["target"] == "D2"
    drill.index = len(TARGETS) - 1
    assert drill.snapshot()["target"] == "BULL"
    assert throw(drill, "25") == []
    assert throw(drill, "BULL")[0][0] == "drill_finished"


def test_the_checkout_training_picks_every_score_three_darts_finish():
    assert tuple(score for score in range(2, 171) if checkout(score)) == CHECKOUT_SCORES
    assert set(range(2, 171)) - set(CHECKOUT_SCORES) == BOGEY_NUMBERS


def test_checkout_training_books_attempts_on_three_visits():
    drill = CheckoutDrill(random.Random(3))
    assert drill.target in CHECKOUT_SCORES
    drill.target = drill.start = 81
    route = list(checkout(81))
    assert drill.snapshot()["checkout"] == " ".join(route)
    events = throw(drill, *route)
    assert events[0] == (
        "checkout_attempt",
        {
            "drill": "checkout",
            "target": 81,
            "success": True,
            "darts": len(route),
            "attempts": 1,
            "successes": 1,
            "rate": 100.0,
        },
    )
    assert drill.target in CHECKOUT_SCORES and drill.visits == 0

    drill.target = drill.start = 100
    assert throw(drill, "S20") == []
    assert (
        drill.snapshot()["attempt_visit"] == 2 and drill.snapshot()["remaining"] == 80
    )
    assert throw(drill, "MISS") == []
    events = throw(drill, "S1")
    assert events[0][1]["success"] is False and events[0][1]["darts"] == 3
    assert drill.snapshot()["rate"] == 50.0

    # As in X01, a bust voids only its visit: 40 is left for the next one.
    drill.target = drill.start = 40
    assert throw(drill, "T20") == []
    assert drill.start == 40 and drill.visits == 1 and drill.attempts == 2
    events = throw(drill, "S20", "D10")
    assert events[0][1]["success"] is True and events[0][1]["darts"] == 3
    # A bust in the third visit ends the attempt.
    drill.target = drill.start = 40
    throw(drill, "S10")
    throw(drill, "S10")
    assert throw(drill, "T20")[0][1]["success"] is False
    assert drill.attempts == 4


def test_checkout_training_shows_the_route_for_the_rest_of_the_visit():
    drill = CheckoutDrill(random.Random(3))
    drill.target = drill.start = 40
    drill.track([dart("S20")])
    snapshot = drill.snapshot()
    assert snapshot["remaining"] == 20 and snapshot["checkout"] == "D10"
    # Corrected to the double: the checkout is made, nothing is left to show.
    drill.track([dart("D20")])
    snapshot = drill.snapshot()
    assert snapshot["won"] and snapshot["remaining"] == 0
    assert snapshot["checkout"] is None
    # A bust leaves the score of the visit start for the next visit.
    drill.track([dart("T20")])
    snapshot = drill.snapshot()
    assert snapshot["bust"] and snapshot["remaining"] == 40
    assert snapshot["checkout"] == "D20" and snapshot["attempt_visit"] == 1
    # The bust of the last visit ends the attempt: no route then.
    drill.visits = CHECKOUT_VISITS - 1
    assert drill.snapshot()["checkout"] is None
    drill.visits = 0
    # A full visit shows the route for the next one, unless it was the last.
    drill.track([dart("S10"), dart("S10"), dart("S10")])
    snapshot = drill.snapshot()
    assert snapshot["remaining"] == 10 and snapshot["checkout"] == "D5"
    drill.visits = CHECKOUT_VISITS - 1
    assert drill.snapshot()["checkout"] is None
    # A fourth dart before the takeout does not count.
    drill.visits = 0
    drill.track([dart("S10"), dart("S10"), dart("S10"), dart("D5")])
    assert drill.snapshot()["remaining"] == 10


def test_restored_progress_past_the_bull_finishes_the_game():
    drill = TargetDrill("around_the_clock")
    drill.restore({"index": len(TARGETS), "darts": 30, "hits": 21})
    snapshot = drill.snapshot()
    assert snapshot["target"] is None and snapshot["progress"] == len(TARGETS)
    events = throw(drill, "S1")
    assert [kind for kind, _ in events] == ["drill_finished"]
    assert drill.finished and len(drill.results) == 1
    # The next dart starts a new game.
    drill.track([dart("S1")])
    assert drill.snapshot()["target"] == "2"


def test_bobs_27_adds_hits_and_takes_the_value_of_a_miss():
    drill = BobsDrill()
    assert (
        drill.snapshot()["target"] == "D1" and drill.snapshot()["score"] == BOBS_START
    )
    throw(drill, "D1", "D1", "S1")
    assert drill.snapshot()["score"] == 31 and drill.snapshot()["target"] == "D2"
    throw(drill, "MISS", "S2", "T2")
    assert drill.snapshot()["score"] == 27
    drill.track([dart("D3")])
    # A hit counts at once; a miss costs the value when the darts are pulled.
    assert drill.snapshot()["score"] == 33
    drill.finish_visit(now=NOW)
    drill.score = 1
    events = throw(drill, "MISS")
    assert events == [
        (
            "drill_finished",
            {
                "drill": "bobs_27",
                "score": -7,
                "completed": False,
                "darts": 8,
                "hits": 3,
                "hit_rate": 37.5,
            },
        )
    ]
    assert drill.snapshot()["finished"] and drill.snapshot()["target"] is None


def test_bobs_27_is_lost_when_the_score_reaches_zero():
    drill = BobsDrill()
    drill.score = 2
    events = throw(drill, "MISS")
    assert events[0][1]["score"] == 0 and events[0][1]["completed"] is False
    assert drill.finished


def test_bobs_27_is_completed_on_the_bull():
    drill = BobsDrill()
    drill.index = len(TARGETS) - 1
    events = throw(drill, "BULL", "25")
    assert events[0][1]["completed"] is True and events[0][1]["score"] == 77
    assert drill.snapshot()["best"] == 77


def test_the_practice_game_switches_between_x01_and_training_games():
    game = PracticeGame()
    game.track([dart("S1")], now=NOW)
    game.play("around_the_clock")
    # The dart already on the board does not count.
    assert game.snapshot()["drill"]["target"] == "1"
    game.track([dart("S1"), dart("S1")], now=NOW)
    assert game.snapshot()["drill"]["target"] == "2"
    assert game.snapshot()["game"] is None
    game.finish_visit(now=NOW)
    restored = PracticeGame()
    restored.restore(game.stored())
    assert restored.drill == "around_the_clock"
    assert restored.snapshot()["drill"]["target"] == "2"
    game.new_leg()
    assert game.snapshot()["drill"]["target"] == "1"
    game.play(501)
    assert game.drill is None and game.snapshot()["remaining"] == 501
    assert game.snapshot()["drill"] is None
    game.play("bobs_27")
    assert game.snapshot()["drill"]["target"] == "D1"


def test_restore_ignores_broken_training_data():
    game = PracticeGame()
    game.restore(
        {
            "drill": "checkout",
            "drills": {
                "checkout": {"target": 169, "start": 5, "attempts": 4, "successes": 9},
                "bobs_27": {"index": 99, "score": "x", "results": [{"score": 1}]},
                "doubles": "broken",
            },
        }
    )
    assert game.drill == "checkout"
    checkout_drill = game.drills["checkout"]
    assert checkout_drill.target in CHECKOUT_SCORES and checkout_drill.target != 169
    assert (checkout_drill.attempts, checkout_drill.successes) == (4, 4)
    bobs = game.drills["bobs_27"]
    assert bobs.index == len(TARGETS) - 1 and bobs.score == BOBS_START
    assert bobs.results == []


@given(
    st.sampled_from(["around_the_clock", "doubles"]),
    st.lists(
        st.lists(
            st.sampled_from(["S1", "D1", "S2", "D2", "T3", "S3", "25", "BULL", "MISS"]),
            min_size=1,
            max_size=3,
        ),
        max_size=40,
    ),
)
def test_target_games_only_move_forward(kind, visits):
    drill = TargetDrill(kind)
    progress = 0
    for visit in visits:
        before = drill.snapshot()
        throw(drill, *visit)
        snapshot = drill.snapshot()
        if not before["finished"]:
            assert snapshot["progress"] >= progress or snapshot["finished"]
        progress = snapshot["progress"]
        assert snapshot["hits"] <= snapshot["darts"]
        assert 0 <= snapshot["progress"] <= len(TARGETS)


@given(st.lists(st.integers(0, 3), max_size=30))
def test_bobs_27_moves_by_the_value_of_the_double(hits_per_visit):
    drill = BobsDrill()
    for hits in hits_per_visit:
        if drill.finished:
            break
        target = TARGETS[drill.index]
        value = 50 if target == 25 else 2 * target
        before = drill.score
        bed = "BULL" if target == 25 else f"D{target}"
        throw(drill, *([bed] * hits + ["MISS"] * (3 - hits)))
        assert drill.score - before == (hits * value if hits else -value)
