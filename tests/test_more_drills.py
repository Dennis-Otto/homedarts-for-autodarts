"""Training games: the 121 ladder, Catch 40, the JDC Challenge and singles."""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.homedarts.checkout import checkout
from custom_components.homedarts.drills import (
    CATCH_TARGETS,
    JDC_STEPS,
    LADDER,
    TARGETS,
    CatchDrill,
    JdcDrill,
    LadderDrill,
    SinglesDrill,
    catch_points,
    make_drill,
)
from custom_components.homedarts.practice import PracticeGame

from .local_helpers import NOW, dart
from .test_drills import throw


def restored(drill):
    """The drill after a restart, from what the store keeps."""
    copy = make_drill(drill.kind)
    copy.restore(json.loads(json.dumps(drill.stored())))
    assert copy.stored() == drill.stored()
    return copy


def test_the_121_ladder_climbs_on_a_finish_and_steps_down_on_a_miss():
    drill = LadderDrill()
    snapshot = drill.snapshot()
    assert snapshot["target"] == "121" and snapshot["remaining"] == 121
    assert snapshot["checkout"] == " ".join(checkout(121, 3))
    assert snapshot["attempt_visits"] == 3 and snapshot["best"] is None
    events = throw(drill, "T20", "T11", "D14")
    assert events == [
        (
            "checkout_attempt",
            {
                "drill": "checkout_121",
                "target": 121,
                "success": True,
                "darts": 3,
                "attempts": 1,
                "successes": 1,
                "rate": 100.0,
                "next": 122,
            },
        )
    ]
    assert drill.snapshot()["target"] == "122" and drill.snapshot()["best"] == 121
    # Three visits without the finish step one down.
    for _ in range(3):
        events = throw(drill, "S1", "S1", "S1")
    assert events[0][1]["success"] is False and events[0][1]["next"] == 121
    # Never below 121.
    for _ in range(3):
        events = throw(drill, "T20", "T20", "T20")
    assert events[0][1]["next"] == 121 and drill.target == 121


def test_a_bust_in_121_voids_only_its_visit():
    drill = LadderDrill()
    # 121: T20 T20 busts; the second visit starts from 121 again.
    assert throw(drill, "T20", "T20") == []
    snapshot = drill.snapshot()
    assert snapshot["remaining"] == 121 and snapshot["attempt_visit"] == 2
    assert snapshot["checkout"] == " ".join(checkout(121, 3))
    drill.track(json_darts("T20"))
    drill.track(json_darts("T20", "T20"))
    snapshot = drill.snapshot()
    # A bust shows until the darts are pulled, with the route of the next visit.
    assert snapshot["bust"] and snapshot["remaining"] == 121
    assert snapshot["checkout"] == " ".join(checkout(121, 3))
    drill.finish_visit(now=NOW)
    drill.track([])
    events = throw(drill, "T20", "T11", "D14")
    assert events[0][1]["success"] is True and events[0][1]["darts"] == 7
    # A bust in the last visit ends the attempt.
    throw(drill, "S1", "S1", "S1")
    throw(drill, "S1", "S1", "S1")
    drill.track(json_darts("T20", "T20"))
    assert drill.snapshot()["checkout"] is None and drill.snapshot()["bust"]
    drill.finish_visit(now=NOW)
    assert drill.target == 121 and drill.visits == 0


def test_the_121_ladder_plays_every_score_up_to_170():
    assert tuple(range(121, 171)) == LADDER
    drill = LadderDrill()
    drill.target = drill.start = 158
    throw(drill, "T20", "T20", "D19")
    assert drill.target == 159
    # 159 has no checkout in one visit: the cards show a setup instead.
    snapshot = drill.snapshot()
    assert snapshot["checkout"] is None
    assert snapshot["setup"] == {"route": "T20 T20 S7", "leave": 32}
    throw(drill, "T20", "T20", "S7")
    snapshot = drill.snapshot()
    assert snapshot["remaining"] == 32 and snapshot["checkout"] == "D16"
    assert snapshot["setup"] is None
    throw(drill, "D16")
    assert drill.target == 160
    drill.target = drill.start = 170
    throw(drill, "T20", "T20", "BULL")
    assert drill.target == 170
    copy = restored(drill)
    assert copy.target == 170 and copy.successes == 3
    # A stored target the ladder does not know starts the ladder again.
    fresh = LadderDrill()
    fresh.restore({"target": 171, "start": 100})
    assert fresh.target == 121


def test_catch_40_scores_by_the_darts_a_checkout_takes():
    assert [catch_points(darts, 61) for darts in (2, 3, 4, 6)] == [3, 2, 1, 1]
    # No two darts finish 99: three darts score 3 there.
    assert [catch_points(darts, 99) for darts in (3, 4)] == [3, 1]
    drill = CatchDrill()
    snapshot = drill.snapshot()
    assert snapshot["target"] == "61" and snapshot["targets"] == 40
    assert snapshot["attempt_visits"] == 2
    assert snapshot["checkout"] == " ".join(checkout(61, 3))
    # 61 in two darts: 3 points, and the next target follows.
    drill.track(json_darts("T15", "D8"))
    assert drill.snapshot()["won"] and drill.snapshot()["score"] == 3
    drill.finish_visit(now=NOW)
    drill.track([])
    snapshot = drill.snapshot()
    assert snapshot["target"] == "62" and snapshot["score"] == 3
    assert snapshot["checkouts"] == 1 and snapshot["progress"] == 1
    # 62 in two visits: four darts score 1.
    throw(drill, "T10", "MISS", "MISS")
    assert drill.snapshot()["attempt_visit"] == 2
    throw(drill, "D16")
    assert drill.score == 4 and drill.index == 2
    # A bust voids only its visit: 63 again, and a finish then scores 1.
    throw(drill, "T20", "T20")
    assert drill.index == 2 and drill.start == 63 and drill.visits == 1
    snapshot = drill.snapshot()
    assert snapshot["attempt_visit"] == 2 and snapshot["remaining"] == 63
    drill.track(json_darts("T13", "D12"))
    assert drill.snapshot()["score"] == 5
    drill.finish_visit(now=NOW)
    drill.track([])
    assert drill.score == 5 and drill.index == 3
    # Two busts, or two visits without the finish, score nothing.
    throw(drill, "T20", "T20")
    throw(drill, "T20", "T20")
    assert drill.score == 5 and drill.index == 4
    throw(drill, "S1", "S1", "S1")
    throw(drill, "S1", "S1", "S1")
    assert drill.score == 5 and drill.index == 5 and drill.darts == 20


def test_catch_40_gives_three_points_for_99_in_three_darts():
    drill = CatchDrill()
    drill.index, drill.start = CATCH_TARGETS.index(99), 99
    drill.track(json_darts("T19", "S10", "D16"))
    assert drill.snapshot()["score"] == 3
    drill.finish_visit(now=NOW)
    assert drill.score == 3 and drill.checkouts == 1


def test_the_checkout_drills_count_their_darts_at_a_double():
    drill = CatchDrill()
    # 61: T11 leaves 28, D14 is a dart at a double, and so is BULL at 50.
    drill.track(json_darts("T11", "S14", "D7"))
    assert drill.double_attempts() == [("D14", False), ("D7", True)]
    drill.finish_visit(now=NOW)
    assert drill.double_attempts() == []
    drill.track(json_darts("S12", "S20", "S20"))
    # 62: S12 leaves 50, so S20 is a dart at the bull, and the next at D15.
    assert drill.double_attempts() == [("BULL", False), ("D15", False)]
    drill.finished = True
    assert drill.double_attempts() == []
    ladder = LadderDrill()
    ladder.track(json_darts("T20", "T20", "S1"))
    assert ladder.double_attempts() == []
    ladder.start = 40
    ladder.track(json_darts("S20", "D10"))
    assert ladder.double_attempts() == [("D20", False), ("D10", True)]


def json_darts(*names):
    return [dart(name) for name in names]


def test_catch_40_finishes_after_100_and_restarts_with_the_next_dart():
    drill = CatchDrill()
    drill.index = len(CATCH_TARGETS) - 1
    drill.start = 100
    drill.score, drill.checkouts, drill.darts = 50, 20, 150
    events = throw(drill, "T20", "D20")
    assert events == [
        (
            "drill_finished",
            {"drill": "catch_40", "score": 53, "checkouts": 21, "darts": 152},
        )
    ]
    snapshot = drill.snapshot()
    assert snapshot["finished"] and snapshot["target"] is None
    assert snapshot["progress"] == 40 and snapshot["best"] == 53
    copy = restored(drill)
    assert copy.finished and copy.score == 53
    copy.track(json_darts("S1"))
    assert copy.snapshot()["target"] == "61" and copy.snapshot()["score"] == 0
    copy.restore({"index": 5, "start": 200, "checkouts": 90, "score": 900})
    assert (copy.start, copy.checkouts, copy.score) == (66, 6, 18)


def test_catch_40_and_the_checkout_training_count_for_the_doubles_analysis():
    practice = PracticeGame()
    practice.set_name(0, "Alex")
    practice.play("catch_40")
    for count in (1, 2, 3):
        practice.track(json_darts("T11", "S14", "D7")[:count], [None] * count, now=NOW)
    booking = practice.booking()
    # 61 is aimed at along its route, 25 D18: the outer bull logs no aim.
    assert booking.booked_aims == [None, "D14", "D7"]
    practice.finish_visit(now=NOW)
    assert practice.doubles.counts == {"D14": [1, 0], "D7": [1, 1]}
    assert practice.profiles.players["alex"].doubles == practice.doubles.counts


def test_the_jdc_challenge_plays_shanghai_doubles_and_shanghai():
    assert len(JDC_STEPS) == 33
    drill = JdcDrill()
    snapshot = drill.snapshot()
    assert snapshot["target"] == "10" and snapshot["part"] == 1
    # A single, double and treble of the number: its value and 100.
    throw(drill, "S10", "D10", "T10")
    assert drill.parts == [160, 0, 0] and drill.snapshot()["target"] == "11"
    for number in range(11, 16):
        throw(drill, f"T{number}", "S1")
    assert drill.parts == [160 + 3 * sum(range(11, 16)), 0, 0]
    snapshot = drill.snapshot()
    assert snapshot["target"] == "D1" and snapshot["part"] == 2
    # One dart per double: the target moves with every dart.
    drill.track(json_darts("D1"))
    assert drill.snapshot()["target"] == "D2" and drill.snapshot()["parts"][1] == 50
    assert drill.double_attempts() == [("D1", True)]
    drill.finish_visit(now=NOW)
    drill.track([])
    throw(drill, "D2", "S3", "D4")
    for start in range(5, 20, 3):
        throw(drill, *(f"D{number}" for number in range(start, start + 3)))
    # The bullseye is worth 100; darts after it do not count.
    events = throw(drill, "D20", "BULL", "T20")
    assert drill.parts[1] == 50 * 19 + 100 and drill.snapshot()["part"] == 3
    assert events == [] and drill.darts == 13 + 21
    for number in range(15, 20):
        throw(drill, f"S{number}")
    events = throw(drill, "T20", "D20", "S20")
    score = sum(drill.parts)
    assert events == [
        (
            "drill_finished",
            {
                "drill": "jdc_challenge",
                "score": score,
                "parts": drill.parts,
                "darts": 13 + 21 + 8,
            },
        )
    ]
    snapshot = drill.snapshot()
    assert snapshot["finished"] and snapshot["target"] is None
    assert snapshot["progress"] == 33 and snapshot["best"] == score
    assert drill.double_attempts() == []
    copy = restored(drill)
    assert copy.finished and copy.step == 33
    copy.restore({"step": 99, "parts": [1, 2]})
    assert copy.step == 32 and copy.parts == drill.parts


def test_singles_score_a_point_per_mark_on_the_number():
    drill = SinglesDrill()
    assert drill.snapshot()["target"] == "1" and drill.snapshot()["targets"] == 21
    # A double of the number is no dart at a double.
    drill.track([dart("D1")])
    assert drill.double_attempts() == []
    drill.track([])
    throw(drill, "S1", "D1", "T2")
    snapshot = drill.snapshot()
    assert snapshot["target"] == "2" and snapshot["score"] == 3
    assert snapshot["hits"] == 2 and snapshot["hit_rate"] == 66.7
    for number in range(2, 21):
        throw(drill, f"T{number}")
    events = throw(drill, "BULL", "25", "MISS")
    assert events == [
        (
            "drill_finished",
            {
                "drill": "singles",
                "score": 3 + 19 * 3 + 3,
                "darts": 25,
                "hits": 23,
                "hit_rate": 92.0,
            },
        )
    ]
    assert drill.snapshot()["target"] is None and drill.snapshot()["best"] == 63
    copy = restored(drill)
    copy.restore({"index": 30, "darts": 3, "hits": 9, "score": 99})
    assert (copy.index, copy.hits, copy.score) == (len(TARGETS) - 1, 3, 9)


def test_the_new_training_games_run_in_the_practice_game():
    game = PracticeGame()
    for kind in ("checkout_121", "catch_40", "jdc_challenge", "singles"):
        game.play(kind)
        snapshot = game.snapshot()
        assert snapshot["drill"]["drill"] == kind and snapshot["game"] is None
    # The doubles of the JDC Challenge count for the doubles analysis.
    game.play("jdc_challenge")
    game.drills["jdc_challenge"].step = 6
    game.track(json_darts("D1", "MISS"), now=NOW)
    game.finish_visit(now=NOW)
    assert game.doubles.counts == {"D1": [1, 1], "D2": [1, 0]}


@settings(max_examples=50, deadline=None)
@given(
    kind=st.sampled_from(["checkout_121", "catch_40", "jdc_challenge", "singles"]),
    visits=st.lists(
        st.lists(
            st.sampled_from(["T20", "T19", "D20", "D8", "S1", "BULL", "25", "MISS"]),
            min_size=1,
            max_size=3,
        ),
        max_size=80,
    ),
)
def test_training_games_survive_restarts_at_any_point(kind, visits):
    drill = make_drill(kind)
    for visit in visits:
        throw(drill, *visit)
        drill = restored(drill)
        snapshot = drill.snapshot()
        assert 0 <= snapshot.get("progress", 0) <= snapshot.get("targets", 1000)
        assert snapshot.get("score", 0) >= 0
