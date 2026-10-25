"""Checkout routes: the ones players aim for, and never an impossible one."""

from itertools import combinations_with_replacement

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.homedarts.checkout import (
    BEDS,
    BEDS_BY_BULL,
    DOUBLES,
    HIGHEST,
    Setup,
    _hard,
    _leaves,
    checkout,
    setup,
)
from custom_components.homedarts.scoring import (
    BULL,
    BULL_25_50,
    BULL_50_50,
    DOUBLE,
    MASTER,
    MODES,
    STRAIGHT,
)

BY_NAME = {bed.name: bed for bed in BEDS}


def ends(name: str, out_mode: str) -> bool:
    """Whether a dart at this bed may finish with the Out mode: the route's
    BULL is the bullseye, a double."""
    double = name[0] == "D" or name == "BULL"
    return out_mode == STRAIGHT or double or (out_mode == MASTER and name[0] == "T")


def reachable(
    darts: int, out_mode: str = DOUBLE, bull_mode: str = BULL_25_50
) -> set[int]:
    """Every score that can be finished with up to this many darts."""
    beds = BEDS_BY_BULL[bull_mode]
    finishes = {
        bed.score
        for bed in beds
        if out_mode == STRAIGHT
        or bed.multiplier == 2
        or (out_mode == MASTER and bed.multiplier == 3)
    }
    scores = {bed.score for bed in beds}
    result, setups = set(), {0}
    for _ in range(darts):
        result |= {setup + finish for setup in setups for finish in finishes}
        setups = {setup + score for setup in setups for score in scores}
    return result


# Routes of the professional checkout charts, with three darts in hand.
CHART = {
    170: "T20 T20 BULL",
    167: "T20 T19 BULL",
    164: "T20 T18 BULL",
    161: "T20 T17 BULL",
    160: "T20 T20 D20",
    158: "T20 T20 D19",
    157: "T20 T19 D20",
    156: "T20 T20 D18",
    155: "T20 T19 D19",
    154: "T20 T18 D20",
    153: "T20 T19 D18",
    152: "T20 T20 D16",
    151: "T20 T17 D20",
    150: "T20 T18 D18",
    149: "T20 T19 D16",
    148: "T20 T16 D20",
    147: "T20 T17 D18",
    146: "T20 T18 D16",
    145: "T20 T15 D20",
    144: "T20 T20 D12",
    143: "T20 T17 D16",
    142: "T20 T14 D20",
    141: "T20 T19 D12",
    140: "T20 T20 D10",
    138: "T20 T18 D12",
    137: "T20 T19 D10",
    136: "T20 T20 D8",
    135: "T20 T17 D12",
    134: "T20 T14 D16",
    133: "T20 T19 D8",
    132: "T20 T16 D12",
    131: "T20 T13 D16",
    130: "T20 T20 D5",
    129: "T19 T16 D12",
    128: "T18 T14 D16",
    127: "T20 T17 D8",
    126: "T19 T19 D6",
    124: "T20 T16 D8",
    122: "T18 T20 D4",
    120: "T20 S20 D20",
    119: "T19 T10 D16",
    118: "T20 S18 D20",
    115: "T20 S15 D20",
    112: "T20 S12 D20",
    110: "T20 BULL",
    107: "T19 BULL",
    104: "T18 BULL",
    103: "T20 S3 D20",
    101: "T17 BULL",
    100: "T20 D20",
    98: "T20 D19",
    97: "T19 D20",
    96: "T20 D18",
    95: "T19 D19",
    94: "T18 D20",
    93: "T19 D18",
    92: "T20 D16",
    91: "T17 D20",
    89: "T19 D16",
    88: "T16 D20",
    87: "T17 D18",
    86: "T18 D16",
    85: "T15 D20",
    84: "T20 D12",
    83: "T17 D16",
    82: "T14 D20",
    81: "T19 D12",
    80: "T20 D10",
    78: "T18 D12",
    77: "T19 D10",
    76: "T20 D8",
    75: "T17 D12",
    74: "T14 D16",
    73: "T19 D8",
    72: "T16 D12",
    71: "T13 D16",
    69: "T15 D12",
    68: "T20 D4",
    67: "T17 D8",
    65: "25 D20",
    64: "T16 D8",
    63: "T13 D12",
    62: "T10 D16",
    61: "25 D18",
    60: "S20 D20",
    57: "S17 D20",
    50: "BULL",
    41: "S1 D20",
    40: "D20",
    39: "S7 D16",
    36: "D18",
    33: "S1 D16",
    32: "D16",
    31: "S15 D8",
    25: "S9 D8",
    17: "S1 D8",
    16: "D8",
    15: "S7 D4",
    9: "S1 D4",
    5: "S1 D2",
    3: "S1 D1",
    2: "D1",
}


@pytest.mark.parametrize(("remaining", "route"), CHART.items())
def test_routes_of_the_checkout_chart(remaining, route):
    assert " ".join(checkout(remaining)) == route


def test_a_missed_first_treble_still_leaves_a_finish():
    # A single 20 would leave 109, 108 or 99, which two darts cannot finish.
    assert checkout(129)[0] == "T19"  # a single 19 leaves 110: T20 BULL
    assert checkout(128)[0] == "T18"
    assert checkout(119)[0] == "T19"
    # With two darts in hand, the first dart is the setup: its miss is lost anyway.
    assert checkout(69, 2) == ("T19", "D6")


def test_two_darts_left_stay_on_the_treble_with_the_bull_behind():
    # A single 20 leaves the bull; with three darts, the single leaves two darts.
    assert checkout(70, 2) == ("T20", "D5")
    assert checkout(70) == ("T18", "D8")
    assert checkout(130) == ("T20", "T20", "D5")


def test_bogey_numbers_limits_and_darts_left():
    impossible = [score for score in range(1, 200) if not checkout(score)]
    assert impossible == [1, 159, 162, 163, 165, 166, 168, 169, *range(171, 200)]
    assert checkout(0) == checkout(-5) == checkout(50, 0) == ()
    assert checkout(40, 1) == ("D20",)
    assert checkout(41, 1) == checkout(100, 1) == ()
    assert checkout(100, 2) == ("T20", "D20")


def test_preferred_doubles_win_among_routes_of_the_same_darts():
    assert checkout(70, 3, DOUBLE, ("D20",)) == ("T10", "D20")
    assert checkout(70, 2, DOUBLE, ("D8",)) == ("T18", "D8")
    assert checkout(90, 3, DOUBLE, ("D15",)) == ("T20", "D15")
    # Fewer darts still come first, and a double never sets up.
    assert checkout(40, 3, DOUBLE, ("D8",)) == ("D20",)
    assert checkout(60, 3, DOUBLE, ("D16",)) == ("S20", "D20")
    # The bull comes last, even for a player who hits it best.
    assert checkout(100, 3, DOUBLE, ("BULL", "D5")) == ("T20", "D20")


def test_single_out_finishes_on_any_bed():
    assert checkout(20, 1, STRAIGHT) == ("S20",)
    assert checkout(60, 3, STRAIGHT) == ("T20",)
    assert checkout(180, 3, STRAIGHT) == ("T20", "T20", "T20")
    assert checkout(181, 3, STRAIGHT) == ()


def test_master_out_finishes_on_a_treble_only_where_it_saves_a_dart():
    # A treble finishes with one dart where a double takes two.
    assert checkout(60, 1, MASTER) == ("T20",)
    assert checkout(57, 3, MASTER) == ("T19",)
    assert checkout(117, 3, MASTER) == ("T20", "T19")
    # Up to 180, the trebles 20 first and the treble that finishes last.
    assert checkout(180, 3, MASTER) == ("T20", "T20", "T20")
    assert checkout(171, 3, MASTER) == ("T20", "T20", "T17")
    assert checkout(159, 3, MASTER) == ("T20", "T20", "T13")
    # With as many darts, the route of the checkout chart on a double.
    assert checkout(100, 3, MASTER) == checkout(100) == ("T20", "D20")
    assert checkout(40, 3, MASTER) == ("D20",)
    assert checkout(36, 1, MASTER) == ("D18",)
    assert checkout(1, 3, MASTER) == checkout(181, 3, MASTER) == ()


def test_the_bull_mode_50_50_routes_50_through_the_whole_bull():
    rules = (DOUBLE, (), BULL_50_50)
    # The bull scores 50 wherever it lands: a dart at it sets up the double.
    assert checkout(90, 3, *rules) == ("BULL", "D20")
    assert checkout(90) == ("T18", "D18")
    assert checkout(70, 3, *rules) == ("BULL", "D10")
    # Only the bullseye is a double: 50 finishes on it.
    assert checkout(50, 1, *rules) == ("BULL",)
    # No dart scores 25, and the outer bull sets up no 61.
    assert checkout(25, 1, STRAIGHT, (), BULL_50_50) == ()
    assert checkout(61, 3, *rules) == ("T15", "D8")
    # Without double out, the bull finishes 50 with one dart, as a single.
    assert checkout(50, 1, STRAIGHT, (), BULL_50_50) == ("BULL",)
    assert checkout(100, 2, STRAIGHT, (), BULL_50_50) == ("T20", "D20")


@given(st.integers(-5, 190), st.integers(1, 3), st.sampled_from(MODES))
def test_a_route_adds_up_ends_right_and_exists_whenever_possible(
    remaining, darts, out_mode
):
    route = checkout(remaining, darts, out_mode)
    assert bool(route) == (remaining in reachable(darts, out_mode))
    if route:
        beds = [BY_NAME[name] for name in route]
        assert sum(bed.score for bed in beds) == remaining
        assert len(beds) <= darts
        assert ends(route[-1], out_mode)
        # No route with fewer darts exists.
        assert remaining not in reachable(len(beds) - 1, out_mode)


@pytest.mark.parametrize(
    ("out_mode", "bull_mode"),
    [
        (MASTER, BULL_25_50),
        (MASTER, BULL_50_50),
        (DOUBLE, BULL_50_50),
        (STRAIGHT, BULL_50_50),
    ],
)
def test_every_route_of_the_master_out_and_the_50_50_bull_is_right(out_mode, bull_mode):
    """Every score from 1 to 190 with one to three darts in hand: a route
    exactly where the darts can finish, adding up, ending on a bed the Out mode
    takes, with the fewest darts; with master out on a treble only where no
    double finishes with as few."""
    scores = {bed.name: bed.score for bed in BEDS_BY_BULL[bull_mode]}
    reach = {darts: reachable(darts, out_mode, bull_mode) for darts in range(4)}
    doubles = {darts: reachable(darts, DOUBLE, bull_mode) for darts in range(4)}
    checked = 0
    for remaining in range(1, 191):
        for darts in (1, 2, 3):
            route = checkout(remaining, darts, out_mode, (), bull_mode)
            assert bool(route) == (remaining in reach[darts]), (remaining, darts)
            if not route:
                continue
            checked += 1
            assert sum(scores[name] for name in route) == remaining
            assert ends(route[-1], out_mode)
            assert remaining not in reach[len(route) - 1]
            if out_mode == MASTER and route[-1][0] == "T":
                assert remaining not in doubles[len(route)]
    assert checked == sum(len(reach[darts] & set(range(1, 191))) for darts in (1, 2, 3))


@given(
    st.integers(2, 170),
    st.integers(1, 3),
    st.lists(st.sampled_from([bed.name for bed in DOUBLES]), unique=True),
)
def test_preferred_doubles_never_change_what_is_possible(remaining, darts, preferred):
    route = checkout(remaining, darts, DOUBLE, tuple(preferred))
    usual = checkout(remaining, darts)
    assert len(route) == len(usual)
    if route:
        beds = [BY_NAME[name] for name in route]
        assert sum(bed.score for bed in beds) == remaining
        assert beds[-1].multiplier == 2
        # A double sets up only when the usual route needs one as well.
        doubles = sum(BY_NAME[name].multiplier == 2 for name in usual[:-1])
        assert sum(bed.multiplier == 2 for bed in beds[:-1]) == doubles


def test_the_outer_bull_sets_up_a_double_in_a_route_but_not_the_next_visit():
    # Routes take the outer bull like an easy single before the double, as
    # the charts do for 61, and so after a treble 20 for 121.
    assert checkout(61) == ("25", "D18") and checkout(121) == ("T20", "25", "D18")
    # A setup avoids it: a dart next to it leaves no finish for the next visit.
    assert setup(57, 1) == Setup(("S17",), 40)


def test_setups_follow_the_out_mode_and_the_bull_mode():
    # Without double or master out, any bed finishes: nothing to set up.
    assert setup(250, 3, (), STRAIGHT) is None
    # Master out sets up a double as well, where no three darts finish.
    assert setup(200, 3, (), MASTER) == setup(200) == Setup(("T20", "T20", "T16"), 32)
    assert setup(169, 3, (), MASTER) == Setup(("T20", "T20", "S17"), 32)
    # One dart at 59 leaves 40 with the single 19; master out also takes a
    # treble to finish the next visit, though a double comes first.
    assert setup(59, 1, (), MASTER) == Setup(("S19",), 40)
    assert setup(181, 1, (), MASTER) is None
    # With the bull mode 50/50, the bull sets up 50, a small bed though.
    assert setup(82, 1, (), DOUBLE, BULL_50_50) == Setup(("BULL",), 32)
    assert setup(82, 1) == Setup(("T14",), 40)
    assert setup(169, 3, (), DOUBLE, BULL_50_50) == Setup(("T20", "T20", "S17"), 32)


def best_throws(darts: int, bull_mode: str) -> dict[int, tuple[tuple, tuple]]:
    """For every total of this many setup darts, the best of all the ways to
    throw it: the fewest small beds, then the fewest and the biggest trebles.

    Setup darts aim at singles, trebles and the outer bull; the outer bull and
    the trebles below 19 are small. A setup names the trebles first, the
    bigger beds first.
    """
    beds = sorted(
        (bed for bed in BEDS_BY_BULL[bull_mode] if bed.multiplier != 2),
        key=lambda bed: (bed.multiplier != 3, -bed.score),
    )
    best: dict[int, tuple[tuple, tuple]] = {}
    for throw in combinations_with_replacement(beds, darts):
        total = sum(bed.score for bed in throw)
        key = (
            sum(
                (bed.number == BULL and bed.multiplier == 1)
                or (bed.multiplier == 3 and bed.number < 19)
                for bed in throw
            ),
            sum(bed.multiplier == 3 for bed in throw),
            tuple(-bed.score for bed in throw),
        )
        if total not in best or key < best[total][0]:
            best[total] = (key, tuple(bed.name for bed in throw))
    return best


def every_throw(remaining, darts, preferred, out_mode, bull_mode, throws):
    """The setup found by trying every way to throw the darts in hand, with
    no shortcut: the best leave of the tiers worth setting up (a finish of
    one dart above the highest checkout with three darts), with the fewest
    small beds, the better leave, then the fewest and the biggest trebles."""
    if (
        remaining < 2
        or not 0 < darts <= 3
        or out_mode == STRAIGHT
        or checkout(remaining, darts, out_mode, (), bull_mode)
    ):
        return None
    tiers = 1 if darts == 3 and remaining > HIGHEST[out_mode] else 2
    found = [
        ((tier, key[0], place, *key[1:]), names, leave)
        for leave, (tier, place) in _leaves(
            preferred, out_mode, bull_mode
        ).ranks.items()
        if tier <= tiers and remaining - leave in throws[darts]
        for key, names in [throws[darts][remaining - leave]]
    ]
    if not found:
        return None
    _, names, leave = min(found)
    return Setup(names, leave)


@pytest.mark.parametrize(
    ("preferred", "out_mode", "bull_mode"),
    [
        ((), DOUBLE, BULL_25_50),
        (("D20", "D10"), DOUBLE, BULL_25_50),
        (("D3", "D7", "D1"), DOUBLE, BULL_25_50),
        (("D8",), MASTER, BULL_25_50),
        ((), DOUBLE, BULL_50_50),
    ],
)
def test_a_setup_is_the_best_of_every_way_to_throw_the_darts(
    preferred, out_mode, bull_mode
):
    """Every score up to 1001 with no to four darts in hand: the search of a
    setup gives up early only where no way to throw the darts sets anything up."""
    throws = {darts: best_throws(darts, bull_mode) for darts in (1, 2, 3)}
    for remaining in range(1002):
        for darts in range(5):
            found = setup(remaining, darts, preferred, out_mode, bull_mode)
            assert found == every_throw(
                remaining, darts, preferred, out_mode, bull_mode, throws
            ), (remaining, darts)
            # Even three treble 20s leave too much above 230: nothing to set up.
            assert found is None or remaining - 60 * darts <= 230


def test_a_setup_avoids_the_outer_bull_and_the_small_trebles():
    small_trebles = {f"T{number}" for number in range(1, 19)}
    hard = {
        bull_mode: {bed.name for bed in beds if _hard(bed)}
        for bull_mode, beds in BEDS_BY_BULL.items()
    }
    # With the bull mode 50/50, the outer bull is the single "BULL" of 50 points;
    # the bullseye, a double, is no small bed.
    assert hard == {
        BULL_25_50: {"25", *small_trebles},
        BULL_50_50: {"BULL", *small_trebles},
    }
