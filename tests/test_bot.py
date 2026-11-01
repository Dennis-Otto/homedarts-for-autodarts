"""The bot: where it aims, where its darts land, and the level it plays."""

import math
import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.homedarts.board import SECTORS, aim_point, bed_name, segment_at
from custom_components.homedarts.bot import (
    AVERAGE_PER_MPR,
    CRICKET_SCATTER,
    MAX_LEVEL,
    MIN_LEVEL,
    SCATTER,
    Bot,
    aim,
    cricket_aim,
    play_cricket_leg,
    play_leg,
    scatter,
    valid_level,
    x01_aim,
)
from custom_components.homedarts.cricket import TACTICS_NUMBERS
from custom_components.homedarts.manual import BEDS
from custom_components.homedarts.scoring import DOUBLE, STRAIGHT

# The averages the bot plays over this many legs of 501 with double out may
# stray this far from its level: the calibration holds within 1.5 % over
# 1,000 legs, and the seeds are fixed, so the test never flakes. A leg of
# level 20 takes 75 darts, give or take 40 %: 400 legs pin its average to
# 2 %; the 70 legs that fit into a second would leave the tolerance to chance.
TOLERANCE = 0.05
LEGS = {20: 400, 60: 300, 100: 300, 120: 300}
# The marks per round the bot plays in Cricket, a 24th of its level, hold
# within 1.5 % over these legs.
CRICKET_LEGS = {20: 150, 60: 300, 120: 300}


def polar(radius: float, number: int) -> tuple[float, float]:
    angle = math.radians(SECTORS.index(number) * 18)
    return radius * math.sin(angle), radius * math.cos(angle)


@pytest.mark.parametrize(
    ("point", "bed"),
    [
        ((0, 0), (25, 2)),
        ((0, 7), (25, 2)),
        ((0, 7.1), (25, 1)),
        ((0, 17), (25, 1)),
        ((0, 17.1), (20, 1)),
        ((0, 97), (20, 1)),
        ((0, 97.1), (20, 3)),
        ((0, 107), (20, 3)),
        ((0, 107.1), (20, 1)),
        ((0, 160.1), (20, 2)),
        ((0, 170), (20, 2)),
        ((0, 170.1), (0, 0)),
        # Clockwise from the 20: the 6 on the right, the 3 at the bottom,
        # the 11 on the left.
        ((102, 0), (6, 3)),
        ((0, -102), (3, 3)),
        ((-102, 0), (11, 3)),
        (polar(165, 16), (16, 2)),
        # Wires between numbers are 9 degrees either side of a number.
        (polar(130, 20), (20, 1)),
        (
            (130 * math.sin(math.radians(8.9)), 130 * math.cos(math.radians(8.9))),
            (20, 1),
        ),
        (
            (130 * math.sin(math.radians(9.1)), 130 * math.cos(math.radians(9.1))),
            (1, 1),
        ),
    ],
)
def test_the_bed_at_a_point(point, bed):
    assert segment_at(*point) == bed


@pytest.mark.parametrize("name", [name for name in BEDS if name != "MISS"])
def test_the_bot_aims_at_the_middle_of_every_bed(name):
    number, multiplier = BEDS[name]
    assert segment_at(*aim_point(name)) == (number, multiplier)


def test_bed_names():
    assert [bed_name(*BEDS[name]) for name in BEDS] == list(BEDS)


@pytest.mark.parametrize(
    ("remaining", "darts", "double_out", "opened", "bed"),
    [
        (501, 3, True, True, "T20"),
        (400, 3, True, True, "T20"),
        # The checkout route, also for the bull with one dart.
        (170, 3, True, True, "T20"),
        (40, 3, True, True, "D20"),
        (50, 1, True, True, "BULL"),
        (61, 2, True, True, "25"),
        # The setup when no route exists.
        (169, 3, True, True, "T20"),
        (89, 1, True, True, "T19"),
        (41, 1, True, True, "S9"),
        # Single out finishes on the biggest bed; beyond it, the treble 20.
        (20, 1, False, True, "S20"),
        (61, 1, False, True, "T20"),
        # Without a finish, single out takes the biggest bed that does not bust.
        (59, 1, False, True, "T19"),
        (44, 1, False, True, "T14"),
        (23, 1, False, True, "D11"),
        # Double in: the double 20 opens the leg ...
        (501, 3, True, False, "D20"),
        (100, 2, True, False, "D20"),
        # ... unless a double wins at once, or leaves a finish for the darts
        # left, as at a handicap start of 40 or less.
        (32, 3, True, False, "D16"),
        (50, 3, True, False, "BULL"),
        (40, 3, False, False, "D20"),
        (33, 3, True, False, "D8"),
        (36, 2, True, False, "D18"),
        # Where the double 20 busts, the biggest double that does not.
        (41, 1, True, False, "D19"),
        (3, 1, True, False, "D20"),
    ],
)
def test_where_the_bot_aims_in_x01(remaining, darts, double_out, opened, bed):
    out_mode = DOUBLE if double_out else STRAIGHT
    opening = STRAIGHT if opened else DOUBLE
    assert x01_aim(remaining, darts, out_mode, opening) == bed


OPEN = [0] * 7
CLOSED = [3] * 7


def marks(*closed: int, bull: int = 0) -> list[int]:
    """Marks on 20 to 15 and the bull, with the given numbers closed."""
    return [3 if number in closed else 0 for number in (20, 19, 18, 17, 16, 15)] + [
        bull
    ]


@pytest.mark.parametrize(
    ("own", "points", "others", "others_points", "cut_throat", "bed"),
    [
        # From the start, the numbers close in order.
        (OPEN, 0, [OPEN], [0], False, "T20"),
        (marks(20), 0, [OPEN], [0], False, "T19"),
        # Behind on points: score on a closed number the others have open.
        (marks(20), 0, [OPEN], [40], False, "T20"),
        # Another player scores on a number the bot has open: close it first.
        (marks(20), 20, [marks(19)], [0], False, "T19"),
        # ... unless the bot is behind and can score itself.
        (marks(20), 0, [marks(19)], [40], False, "T20"),
        # Everything closed but behind: score where the others are open.
        (CLOSED, 0, [marks(20, 19)], [40], False, "T18"),
        # Nothing left to close or score on.
        (CLOSED, 0, [CLOSED], [0], False, "T20"),
        # The bull last, aimed at its centre.
        (marks(20, 19, 18, 17, 16, 15), 0, [OPEN], [0], False, "BULL"),
        # Cut-Throat: points hurt, so the bot scores while another player has
        # fewer points, on a number that player has open.
        (marks(20), 0, [OPEN, OPEN], [0, 0], True, "T19"),
        (marks(20), 60, [OPEN, marks(20)], [0, 20], True, "T20"),
        (marks(20, 19), 60, [marks(20), marks(19)], [0, 20], True, "T19"),
    ],
)
def test_where_the_bot_aims_in_cricket(
    own, points, others, others_points, cut_throat, bed
):
    assert cricket_aim(own, points, others, others_points, cut_throat=cut_throat) == bed


def test_the_bot_plays_the_numbers_of_tactics():
    own = [3] * 11 + [0]
    assert cricket_aim([0] * 12, 0, [[0] * 12], [0], TACTICS_NUMBERS) == "T20"
    assert cricket_aim(own, 0, [[0] * 12], [0], TACTICS_NUMBERS) == "BULL"


def test_the_bot_aims_from_the_snapshot_of_the_game():
    assert aim({"bull_off": {"player": 2}}) == "BULL"
    x01 = {"bull_off": None, "remaining": 100, "visit": ["S1"], "double_out": True}
    assert aim(x01) == "T20"
    assert aim({**x01, "remaining": 32, "visit": ["S1", "S1"]}) == "D16"
    assert aim({**x01, "opened": False}) == "D20"
    cricket = {
        "bull_off": None,
        "game": "cricket",
        "numbers": [20, 19, 18, 17, 16, 15, 25],
        "player": 2,
        "visit": [],
        "scores": [
            {"player": 1, "marks": marks(19), "points": 0},
            {"player": 2, "marks": marks(20), "points": 20},
        ],
    }
    # Player 1 has the 19 closed: the bot closes it, too.
    assert aim(cricket) == "T19"
    # Partners in a team: only the other team counts.
    teams = {
        **cricket,
        "scores": [
            {"player": 1, "team": 1, "marks": OPEN, "points": 0},
            {"player": 2, "team": 2, "marks": marks(20), "points": 20},
            {"player": 3, "team": 1, "marks": OPEN, "points": 0},
            {"player": 4, "team": 2, "marks": marks(19), "points": 100},
        ],
    }
    assert aim(teams) == "T19"


def test_the_scatter_of_a_level():
    assert [scatter(level) for level, _ in SCATTER] == [sigma for _, sigma in SCATTER]
    # Between two levels of the table the scatter is interpolated.
    assert scatter(22) == pytest.approx(48.06 + (38.69 - 48.06) * 2 / 5)
    assert scatter(MIN_LEVEL - 5) == scatter(MIN_LEVEL)
    assert scatter(MAX_LEVEL + 5) == scatter(MAX_LEVEL)
    # Better players scatter less.
    sigmas = [sigma for _, sigma in SCATTER]
    assert sigmas == sorted(sigmas, reverse=True)


@pytest.mark.parametrize(
    ("level", "valid"),
    [
        (0, True),
        (20, True),
        (60, True),
        (120, True),
        (19, False),
        (121, False),
        (-1, False),
        (True, False),
        ("60", False),
        (60.0, False),
    ],
)
def test_valid_levels(level, valid):
    assert valid_level(level) is valid


@given(
    seed=st.integers(0, 2**32), bed=st.sampled_from(["T20", "D16", "S5", "25", "BULL"])
)
def test_a_dart_lands_in_the_bed_of_its_position(seed, bed):
    dart, (x, y) = Bot(random.Random(seed)).throw(bed, 60)
    assert (dart["number"], dart["multiplier"]) == segment_at(x * 170, y * 170)
    assert dart["name"] == bed_name(dart["number"], dart["multiplier"])


def test_the_same_seed_throws_the_same_darts():
    first = [Bot(random.Random(7)).throw("T20", 80) for _ in range(3)]
    again = [Bot(random.Random(7)).throw("T20", 80) for _ in range(3)]
    assert first == again
    # Without a random generator of its own, the bot still throws.
    assert Bot().throw("T20", 120)[0]["number"] in range(26)


@pytest.mark.parametrize("level", sorted(LEGS))
def test_the_bot_plays_its_level(level):
    """Averages of 501 with double out, over hundreds of legs."""
    bot = Bot(random.Random(level))
    legs = LEGS[level]
    darts = sum(play_leg(bot, level) for _ in range(legs))
    average = 501 * 3 * legs / darts
    assert abs(average - level) <= level * TOLERANCE, average


@pytest.mark.parametrize("level", sorted(CRICKET_LEGS))
def test_the_bot_plays_the_marks_per_round_of_its_level_in_cricket(level):
    """Marks per round against a player who never scores, over hundreds of legs."""
    bot = Bot(random.Random(level))
    marks = darts = 0
    for _ in range(CRICKET_LEGS[level]):
        counted, thrown = play_cricket_leg(bot, level)
        marks += counted
        darts += thrown
    target = level / AVERAGE_PER_MPR
    assert abs(marks * 3 / darts - target) <= target * TOLERANCE


def test_the_cricket_scatter_of_a_level():
    assert [scatter(level, cricket=True) for level, _ in CRICKET_SCATTER] == [
        sigma for _, sigma in CRICKET_SCATTER
    ]
    sigmas = [sigma for _, sigma in CRICKET_SCATTER]
    assert sigmas == sorted(sigmas, reverse=True)
    # The Cricket numbers are harder to score on than the treble 20: a level
    # scatters more in Cricket than in X01.
    assert all(scatter(level, cricket=True) > sigma for level, sigma in SCATTER)
    # A dart of the Cricket games lands with that scatter.
    _aim_x, aim_y = aim_point("T20")
    x01 = Bot(random.Random(1)).throw("T20", 60)[1]
    cricket = Bot(random.Random(1)).throw("T20", 60, cricket=True)[1]
    ratio = (cricket[1] * 170 - aim_y) / (x01[1] * 170 - aim_y)
    assert ratio == pytest.approx(scatter(60, cricket=True) / scatter(60), rel=0.01)


def test_the_bot_plays_tactics_down_to_ten():
    counted, darts = play_cricket_leg(Bot(random.Random(5)), 120, TACTICS_NUMBERS)
    assert counted >= 36 and darts >= 12


class RecordingBot(Bot):
    """A bot that keeps every dart it throws."""

    def __init__(self, seed: int) -> None:
        super().__init__(random.Random(seed))
        self.darts: list[dict] = []

    def throw(self, bed: str, level: int, cricket: bool = False):
        dart, position = super().throw(bed, level, cricket)
        self.darts.append(dart)
        return dart, position


@pytest.mark.parametrize(
    ("level", "start", "double_out", "fewest"),
    [(120, 40, True, 1), (60, 301, True, 6), (60, 301, False, 6)],
)
def test_a_leg_of_the_bot_ends_on_a_double_or_with_single_out(
    level, start, double_out, fewest
):
    """With double out, the dart that wins a leg is a double or the bullseye;
    with single out, a single or a treble wins as well."""
    bot = RecordingBot(3)
    finishes = []
    for _ in range(20):
        bot.darts.clear()
        # Every dart thrown counts, those of a bust as well.
        out_mode = DOUBLE if double_out else STRAIGHT
        assert play_leg(bot, level, start, out_mode) == len(bot.darts) >= fewest
        finishes.append(bot.darts[-1]["multiplier"])
    if double_out:
        assert set(finishes) == {2}
    else:
        assert set(finishes) - {2}
