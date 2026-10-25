"""Aimed beds, dart positions, the grouping around a bed and the error model of the
aim map, with synthetic scatter."""

import json
import math
import random
from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.homedarts import positions
from custom_components.homedarts.aim import MIN_DARTS, ErrorModel
from custom_components.homedarts.board import RADIUS_MM, aim_point
from custom_components.homedarts.checkout import checkout
from custom_components.homedarts.positions import (
    AIMS,
    GROUPS,
    MAX_DISTANCE,
    MIN_GROUP,
    DartLog,
    aim_model,
    error_model,
    spread,
    x01_aims,
)
from custom_components.homedarts.scoring import BULL_50_50, DOUBLE, MASTER, STRAIGHT

from .local_helpers import dart


def darts(*names: str) -> list[dict]:
    return [dart(name) for name in names]


def routes(remaining: int, left: int) -> tuple[str, ...]:
    return checkout(remaining, left)


def single_out(remaining: int, left: int) -> tuple[str, ...]:
    return checkout(remaining, left, STRAIGHT)


def around(aim: str, dx: float, dy: float) -> tuple[float, float, str]:
    """A dart that landed dx and dy millimetres from the centre of a bed."""
    x, y = aim_point(aim)
    return (x + dx) / RADIUS_MM, (y + dy) / RADIUS_MM, aim


def ring(aim: str, radius: float, count: int, centre=(0.0, 0.0)):
    """Darts evenly around a circle, so their mean is the circle's centre."""
    return [
        around(
            aim,
            centre[0] + radius * math.cos(2 * math.pi * index / count),
            centre[1] + radius * math.sin(2 * math.pi * index / count),
        )
        for index in range(count)
    ]


def test_aim_points_follow_the_board():
    assert aim_point("BULL") == (0.0, 0.0)
    x, y = aim_point("T20")
    assert (round(x, 6), y) == (0.0, 102.0)
    # The 6 is on the right, the 3 at the bottom and the 19 next to it.
    x, y = aim_point("D6")
    assert (x, round(y, 6)) == (165.0, 0.0)
    x, y = aim_point("T3")
    assert (round(x, 6), y) == (0.0, -102.0)
    x, y = aim_point("T19")
    assert x < 0 and y < -95
    assert len(AIMS) == 41 and "S20" not in AIMS


def test_x01_scoring_visits_aim_at_the_treble_20():
    assert x01_aims(501, darts("T20", "S20", "S1"), DOUBLE, None, routes) == [
        "T20",
        "T20",
        "T20",
    ]


def test_x01_finishes_aim_at_the_double_or_the_route():
    # 100: T20 D20; after a single 20, 80 is T20 D10 with two darts.
    assert x01_aims(100, darts("S20", "T20", "D10"), DOUBLE, None, routes) == [
        "T20",
        "T20",
        "D10",
    ]
    # One dart at 40 is thrown at D20; a miss leaves 40, a single 20 leaves D10.
    assert x01_aims(40, darts("MISS", "S20", "D10"), DOUBLE, None, routes) == [
        "D20",
        "D20",
        "D10",
    ]
    assert x01_aims(50, darts("BULL"), DOUBLE, None, routes) == ["BULL"]
    # 60 is S20 D20: a single has no aim. Two darts cannot finish 140.
    assert x01_aims(60, darts("S20"), DOUBLE, None, routes) == [None]
    assert x01_aims(200, darts("T20", "T20", "T20"), DOUBLE, None, routes) == [
        "T20",
        "T20",
        "T20",
    ]


def test_x01_darts_after_the_finish_or_a_bust_have_no_aim():
    assert x01_aims(40, darts("D20", "S1", "S1"), DOUBLE, None, routes) == [
        "D20",
        None,
        None,
    ]
    # 20 minus a treble 20 busts: the rest of the visit does not count.
    assert x01_aims(20, darts("T20", "S1", "S1"), DOUBLE, None, routes) == [
        "D10",
        None,
        None,
    ]
    # Leaving one busts with double out, as does a finish on a single.
    assert x01_aims(21, darts("S20", "S1"), DOUBLE, None, routes)[1] is None
    assert x01_aims(20, darts("S20", "S1"), DOUBLE, None, routes)[1] is None


def test_without_double_out_the_route_can_end_on_a_single():
    assert x01_aims(20, darts("S20"), STRAIGHT, None, single_out) == [None]
    assert x01_aims(501, darts("T20"), STRAIGHT, None, single_out) == ["T20"]
    assert x01_aims(20, darts("S19", "S1"), STRAIGHT, None, single_out) == [None, None]


def test_double_in_aims_after_the_opening_double():
    # Before the opening double, any double will do.
    assert x01_aims(501, darts("S20", "D5", "T20"), DOUBLE, 1, routes) == [
        None,
        None,
        "T20",
    ]
    assert x01_aims(501, darts("S20", "S5", "T20"), DOUBLE, 3, routes) == [
        None,
        None,
        None,
    ]
    assert x01_aims(501, darts("D20", "T20"), DOUBLE, 0, routes) == [None, "T20"]


def test_the_double_that_finishes_comes_before_the_route():
    # A route that sets up another double: one dart at 32 is still thrown at D16.
    def setup(remaining: int, left: int) -> tuple[str, ...]:
        return ("S16", "D8")

    assert x01_aims(32, darts("S16", "D8"), DOUBLE, None, setup) == ["D16", "D8"]
    # Without double out, the route names the bed.
    assert x01_aims(32, darts("S16", "D8"), STRAIGHT, None, setup) == [None, None]


def test_the_opening_double_scores_for_the_darts_after_it():
    # D10 opens and leaves 40: the next dart aims at D20.
    assert x01_aims(60, darts("D10", "D20"), DOUBLE, 0, routes) == [None, "D20"]
    assert x01_aims(60, darts("S1", "D10", "S20"), DOUBLE, 1, routes) == [
        None,
        None,
        "D20",
    ]


def test_the_aims_count_the_outer_bull_as_the_bull_mode_scores_it():
    def route(remaining: int, left: int) -> tuple[str, ...]:
        return checkout(remaining, left, DOUBLE, (), BULL_50_50)

    # With the bull mode 50/50, the outer bull leaves 40 of 90 for D20; with
    # 25/50 it leaves 65, which the route sets up with a single, the outer bull.
    aims = x01_aims(90, darts("25", "D20"), DOUBLE, None, route, BULL_50_50)
    assert aims[1] == "D20"
    assert checkout(65, 2) == ("25", "D20")
    assert x01_aims(90, darts("25", "D20"), DOUBLE, None, routes)[1] is None


@pytest.mark.parametrize(
    ("start", "names", "out_mode", "aims"),
    [
        # A single 1 leaves 2 for D1, and with master out 3 for T1.
        (3, ("S1", "D1"), DOUBLE, [None, "D1"]),
        (4, ("S1", "T1"), MASTER, ["D2", "T1"]),
        # 1 left busts with double out: no checkout, no treble 20 either.
        (3, ("S2", "S1"), DOUBLE, [None, None]),
        # A finish without double out ends the visit.
        (20, ("S20", "T20"), STRAIGHT, [None, None]),
        (501, ("T20", "T20", "T20"), STRAIGHT, ["T20", "T20", "T20"]),
    ],
)
def test_the_aims_follow_the_score_left_after_every_dart(start, names, out_mode, aims):
    def route(remaining: int, left: int) -> tuple[str, ...]:
        return checkout(remaining, left, out_mode)

    assert x01_aims(start, darts(*names), out_mode, None, route) == aims


def test_the_grouping_of_rings_is_exact():
    """20 darts 30 mm and 20 darts 10 mm around a point 6 mm left of T20."""
    older = ring("T20", 30, 20, centre=(-6, 2))
    newer = ring("T20", 10, 20, centre=(-6, 2))
    [group] = spread([*older, *newer])
    assert group == {
        "target": "T20",
        "darts": 40,
        "offset_x": -6.0,
        "offset_y": 2.0,
        "r50": 10.0,
        "r80": 30.0,
        # The newer half is 20 mm tighter than the older one.
        "change": -20.0,
    }


def test_a_normal_scatter_has_the_expected_radii():
    """Darts scattered normally: half lie within 1.18 and 80 % within 1.79 sigma."""
    generator = random.Random(27)
    sigma = 20
    scatter = [
        around("D16", generator.gauss(4, sigma), generator.gauss(-3, sigma))
        for _ in range(2000)
    ]
    [group] = spread(scatter)
    assert group["darts"] == 2000
    assert group["offset_x"] == pytest.approx(4, abs=2)
    assert group["offset_y"] == pytest.approx(-3, abs=2)
    assert group["r50"] == pytest.approx(1.1774 * sigma, rel=0.06)
    assert group["r80"] == pytest.approx(1.7941 * sigma, rel=0.06)
    assert group["change"] == pytest.approx(0, abs=3)


def test_groupings_need_enough_darts_and_an_aim():
    few = ring("BULL", 5, MIN_GROUP - 1)
    unaimed = [(x, y, None) for x, y, _ in ring("T19", 5, 30)]
    singles = [(x, y, "S20") for x, y, _ in ring("T20", 5, 30)]
    assert spread([*few, *unaimed, *singles]) == []
    [group] = spread(ring("BULL", 5, MIN_GROUP))
    # With fewer than two halves of enough darts, there is no trend.
    assert group["target"] == "BULL" and group["change"] is None


def test_groupings_come_most_darts_first():
    beds = [f"D{number}" for number in range(1, GROUPS + 3)]
    scatter = [
        dart for index, bed in enumerate(beds) for dart in ring(bed, 8, 10 + index)
    ]
    scatter += ring("T20", 8, 10 + len(beds))
    groups = spread(scatter)
    assert len(groups) == GROUPS
    assert [group["target"] for group in groups[:3]] == ["T20", beds[-1], beds[-2]]
    # Equal numbers of darts keep the order of the aims.
    tied = spread([*ring("D2", 8, 10), *ring("D1", 8, 10)])
    assert [group["target"] for group in tied] == ["D1", "D2"]


def test_the_grouping_is_rounded_to_a_tenth_of_a_millimetre():
    older = ring("T20", 30.37, 20, centre=(-6.24, 2.26))
    newer = ring("T20", 10.11, 20, centre=(-6.24, 2.26))
    assert spread([*older, *newer]) == [
        {
            "target": "T20",
            "darts": 40,
            "offset_x": -6.2,
            "offset_y": 2.3,
            "r50": 10.1,
            "r80": 30.4,
            "change": -20.3,
        }
    ]


def test_the_radii_hold_half_and_four_fifths_of_the_darts():
    # Two darts at 1 to 5 mm left and right of D16.
    line = [around("D16", side * step, 0.0) for step in range(1, 6) for side in (1, -1)]
    [group] = spread(line)
    assert (group["r50"], group["r80"]) == (3.0, 4.0)


def test_a_bed_with_too_few_darts_leaves_the_others_their_grouping():
    few = ring("BULL", 5, MIN_GROUP - 1)
    [group] = spread([*few, *ring("T19", 5, 2 * MIN_GROUP)])
    # Two halves of enough darts each show the trend.
    assert (group["target"], group["darts"], group["change"]) == (
        "T19",
        2 * MIN_GROUP,
        0.0,
    )


def test_the_log_keeps_the_newest_darts_compactly():
    log = DartLog(3)
    log.add(None, "T20")
    log.add((0.0, 4.0), "T20")
    assert len(log) == 0
    for step in range(4):
        log.add((0.1 * step, 0.6), "T20" if step else "S20")
    assert len(log) == 3
    assert log.positions() == [[0.1, 0.6], [0.2, 0.6], [0.3, 0.6]]
    stored = log.stored()
    assert stored == [170, 1020, 21, 340, 1020, 21, 510, 1020, 21]
    copy = DartLog(3)
    copy.restore(stored)
    assert copy.positions() == log.positions()
    assert list(copy.darts)[0][2] == "T20"
    log.clear()
    assert log.positions() == [] and log.spread() == []


def test_the_log_restores_only_valid_darts():
    log = DartLog(10)
    for saved in (None, {"x": 1}, [1, 2]):
        log.restore(saved)
        assert len(log) == 0
    log.restore(
        [
            *(170, 1020, 0),
            *(170.5, 1020, 21),
            *(9000, 0, 21),
            *(0, -9000, 21),
            *(0, 0, 42),
            *(0, 0, -1),
            *(0, 0, True),
            *(-170, 0, 1),
        ]
    )
    assert log.positions() == [[0.1, 0.6], [-0.1, 0.0]]
    assert [aim for _, _, aim in log.darts] == [None, "BULL"]


def test_darts_at_the_edge_of_the_board_come_back_after_a_restart():
    log = DartLog(10)
    # Up to MAX_DISTANCE from the centre, and the last double, D20.
    log.add((MAX_DISTANCE, 0.0), "D20")
    log.add((0.0, -MAX_DISTANCE), None)
    # Rounded to tenths of a millimetre, this one is a little further out.
    log.add((2.99985, 0.0173), "BULL")
    log.add((MAX_DISTANCE, 0.001), "T20")
    stored = log.stored()
    assert stored == [5100, 0, 41, 0, -5100, 0, 5100, 29, 1]
    restored = DartLog(10)
    restored.restore(json.loads(json.dumps(stored)))
    assert restored.stored() == stored
    assert [aim for _, _, aim in restored.darts] == ["D20", None, "BULL"]


def test_a_restored_log_takes_darts_up_to_a_tenth_of_a_millimetre_further_out():
    log = DartLog(10)
    log.restore(
        [
            *(5101, 0, 1),
            *(0, -5101, 41),
            *(5102, 0, 1),
            *(-4000, 4000, 1),
            *(10**400, 0, 1),
        ]
    )
    assert log.stored() == [5101, 0, 1, 0, -5101, 41]


def test_the_log_keeps_aims_of_the_beds_it_knows_and_rounds_positions():
    log = DartLog(10)
    log.add((0.12345, -0.56789), "S20")
    log.add((-0.0004, 0.9996), "T20")
    assert log.positions() == [[0.123, -0.568], [-0.0, 1.0]]
    assert [aim for _, _, aim in log.darts] == [None, "T20"]


def test_an_aim_model_of_the_same_darts_is_no_newer_one():
    log = DartLog(10)
    log.add((0.0, 0.6), "T20")
    best = {"aim": "T20", "compared": {}}
    assert log.store_aim(positions.Aim(log.version, {"darts": 1}, best=best))
    other = {"aim": "T19", "compared": {}}
    assert not log.store_aim(positions.Aim(log.version, {"darts": 1}, best=other))
    assert log.best_aim() == best


POSITIONS = st.lists(
    st.tuples(
        st.floats(-MAX_DISTANCE - 0.1, MAX_DISTANCE + 0.1),
        st.floats(-MAX_DISTANCE - 0.1, MAX_DISTANCE + 0.1),
        st.sampled_from([*AIMS, "S20", None]),
    ),
    max_size=40,
)


@given(POSITIONS, POSITIONS, st.integers(1, 50))
def test_a_restored_log_goes_on_as_the_stored_one(before, after, size):
    log = DartLog(size)
    for x, y, aim in before:
        log.add((x, y), aim)
    stored = log.stored()
    restored = DartLog(size)
    restored.restore(json.loads(json.dumps(stored)))
    assert restored.stored() == stored and len(restored) == len(log)
    for x, y, aim in after:
        log.add((x, y), aim)
        restored.add((x, y), aim)
    assert restored.stored() == log.stored()
    # Within a tenth of a millimetre, the positions of the cards round alike.
    for position, original in zip(restored.positions(), log.positions(), strict=True):
        assert position == pytest.approx(original, abs=2e-3)


def test_the_log_works_out_its_grouping_once_per_dart():
    log = DartLog(100)
    for x, y, aim in ring("T20", 5, MIN_GROUP):
        log.add((x, y), aim)
    first = log.spread()
    first[0]["darts"] = 0
    assert log.spread()[0]["darts"] == MIN_GROUP
    log.add((0.0, 0.6), "T20")
    assert log.spread()[0]["darts"] == MIN_GROUP + 1


def normal(
    generator: random.Random,
    aims: list[str],
    count: int,
    offset=(0.0, 0.0),
    sd=(20.0, 20.0),
    correlation=0.0,
):
    """Darts scattered normally around the centres of beds, in the board's directions."""
    darts = []
    for index in range(count):
        first, second = generator.gauss(0, 1), generator.gauss(0, 1)
        dx = offset[0] + sd[0] * first
        dy = offset[1] + sd[1] * (
            correlation * first + math.sqrt(1 - correlation**2) * second
        )
        darts.append(around(aims[index % len(aims)], dx, dy))
    return darts


def test_the_aim_model_needs_darts_at_a_treble():
    darts = [*ring("T20", 5, MIN_DARTS - 1), *ring("D16", 5, 40), *ring("BULL", 5, 40)]
    darts += [(x, y, None) for x, y, _ in ring("T19", 5, 40)]
    assert aim_model(darts) == {"darts": MIN_DARTS - 1, "needed": MIN_DARTS}
    assert error_model(aim_model(darts)) is None
    model = aim_model([*darts, *ring("T5", 5, 1)])
    assert model["darts"] == MIN_DARTS
    assert error_model(model) == ErrorModel(0.0, 0.0, 3.5, 3.5, 0.0)


def test_the_aim_model_pools_every_treble_in_the_board_directions():
    """A miss to the left stays one to the left at the treble 3, 6 and 11 too."""
    generator = random.Random(5)
    trebles = [f"T{number}" for number in (20, 3, 6, 11, 19)]
    darts = normal(generator, trebles, 3000, (-6, 3), (12, 24), 0.3)
    model = aim_model(darts)
    assert model["darts"] == 3000
    assert model["offset_x"] == pytest.approx(-6, abs=1)
    assert model["offset_y"] == pytest.approx(3, abs=1.5)
    assert model["sd_x"] == pytest.approx(12, rel=0.05)
    assert model["sd_y"] == pytest.approx(24, rel=0.05)
    assert model["correlation"] == pytest.approx(0.3, abs=0.05)
    # Half millimetres and twentieths, which a new dart mostly leaves as they are.
    assert all((model[key] * 2).is_integer() for key in ("offset_x", "sd_x", "sd_y"))
    assert (model["correlation"] * 20) == pytest.approx(
        round(model["correlation"] * 20)
    )


def test_darts_aimed_elsewhere_do_not_widen_the_model():
    """A player who goes for the treble 19 in a scoring visit, which the game takes
    for one at the treble 20, keeps their own spread."""
    generator = random.Random(8)
    darts = normal(generator, ["T20"], 300)
    elsewhere = normal(generator, ["T19"], 30)
    darts += [(x, y, "T20") for x, y, _ in elsewhere]
    model = aim_model(darts)
    assert model["darts"] == 330
    assert model["sd_x"] == pytest.approx(20, rel=0.12)
    assert model["sd_y"] == pytest.approx(20, rel=0.12)
    assert abs(model["offset_x"]) < 4 and abs(model["offset_y"]) < 4
    # All of them would make it twice as wide up and down.
    xs, ys = zip(*((x * 170, y * 170) for x, y, _ in darts), strict=True)
    mean = sum(ys) / len(ys)
    assert math.sqrt(sum((y - mean) ** 2 for y in ys) / len(ys)) > 50


def test_the_aim_model_never_collapses():
    # Every dart on one spot: the spread is half a millimetre.
    spot = [around("T20", 2, -1)] * MIN_DARTS
    assert aim_model(spot) | {"darts": 0} == {
        "darts": 0,
        "needed": MIN_DARTS,
        "offset_x": 2.0,
        "offset_y": -1.0,
        "sd_x": 0.5,
        "sd_y": 0.5,
        "correlation": 0.0,
    }
    # Darts on a line: the correlation stops short of one.
    line = [around("T20", step, step) for step in range(-20, 20)]
    model = aim_model(line)
    assert model["correlation"] == 0.95
    assert model["sd_x"] == model["sd_y"] > 5


def test_the_aim_model_of_a_scatter_to_the_half_millimetre():
    """Darts 5 mm right of and 4 mm below the trebles, spread 10 mm sideways and
    16 mm up and down with a correlation of 0.6, and 30 aimed at the treble 19 in
    scoring visits: the model of the trimmed darts, to its rounding."""
    generator = random.Random(11)
    darts = normal(generator, ["T20", "T3", "T11"], 300, (5, -4), (10, 16), 0.6)
    darts += [(x, y, "T20") for x, y, _ in normal(generator, ["T19"], 30)]
    assert aim_model(darts) == {
        "darts": 330,
        "needed": MIN_DARTS,
        "offset_x": 5.5,
        "offset_y": -4.0,
        "sd_x": 10.0,
        "sd_y": 16.5,
        "correlation": 0.6,
    }


def test_a_group_of_darts_far_off_does_not_pull_the_model():
    """Darts 40 mm right of and 30 mm below the treble 20, and a quarter of them
    60 mm higher: the median point and the median distance from it, where the
    model starts, keep the far group out from the first round."""
    generator = random.Random(3)
    darts = normal(generator, ["T20"], 200, (40, -30), (8, 8))
    darts += normal(generator, ["T20"], 70, (40, 30), (8, 8))
    assert aim_model(darts) == {
        "darts": 270,
        "needed": MIN_DARTS,
        "offset_x": 39.5,
        "offset_y": -31.0,
        "sd_x": 8.0,
        "sd_y": 8.0,
        "correlation": -0.15,
    }


def test_the_model_of_a_tight_grouping_starts_without_a_correlation():
    generator = random.Random(4)
    darts = normal(generator, ["T20"], 100, sd=(0.8, 0.8))
    assert aim_model(darts) == {
        "darts": 100,
        "needed": MIN_DARTS,
        "offset_x": 0.0,
        "offset_y": 0.0,
        "sd_x": 0.5,
        "sd_y": 1.0,
        "correlation": -0.2,
    }


def work_out(log: DartLog) -> bool:
    """The aim model of a log, as the coordinator works it out in an executor."""
    return log.store_aim(log.aim_job()())


def test_the_log_searches_the_best_aim_only_for_a_new_model(monkeypatch):
    log = DartLog(1000)
    # Before the first aim model, the log knows nothing of one.
    assert log.aim_stale
    assert log.aim() == {"darts": 0, "needed": MIN_DARTS}
    assert work_out(log) is False and not log.aim_stale
    assert log.best_aim() is None
    for x, y, aim in normal(random.Random(2), ["T20"], 200):
        log.add((x, y), aim)
    assert log.aim_stale
    searched = []
    original = positions.best_aim
    monkeypatch.setattr(
        positions, "best_aim", lambda model: searched.append(model) or original(model)
    )
    # The darts are copied for the executor; a dart that comes meanwhile waits
    # for the next model.
    job = log.aim_job()
    log.add(around("D16", 3, 4)[:2], "D16")
    first = job()
    assert log.store_aim(first) is True and log.aim_stale
    best = log.best_aim()
    assert best["bed"] == "T19" and set(best["compared"]) == {"T20", "T19", "BULL"}
    best["compared"]["T20"] = 0
    aim = log.aim()
    assert aim["darts"] == 200 and aim["best"]["compared"]["T20"] > 0
    aim["best"]["compared"]["T20"] = 0
    # Darts at a double leave the model, and the best aim, as they were.
    log.add(around("D16", 3, 4)[:2], "D16")
    assert len(log) == 202
    assert work_out(log) is False and not log.aim_stale
    assert log.best_aim()["compared"]["T20"] > 0
    assert len(searched) == 1
    # A model worked out for older darts never replaces a newer one.
    assert log.store_aim(first) is False and not log.aim_stale
    copy = deepcopy(log)
    assert copy.best_aim() == log.best_aim() and not copy.aim_stale
    assert work_out(copy) is False and len(searched) == 1
    for _ in range(2):
        log.add(around("T20", 30, -30)[:2], "T20")
    work_out(log)
    assert log.aim()["darts"] == 202
    assert len(searched) == 2
    log.clear()
    assert log.aim_stale and log.best_aim() is not None
    assert work_out(log) is True
    assert log.best_aim() is None and "best" not in log.aim()
