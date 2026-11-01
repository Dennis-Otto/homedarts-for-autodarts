"""A computer opponent for X01 and the Cricket games.

The bot aims like a player: in X01 at the treble 20 to score, along the
checkout route when it can finish, and at the setup shot when it cannot; in
the Cricket games it closes numbers and scores where it pays, in Wild Mouse
also doubles, triples and three in a bed, and in Hidden Cricket it searches
for the numbers that do not show yet. Its darts land
with a Gaussian scatter in millimetres around the aim point. In X01, the
scatter of a level is calibrated so that the bot's 3-dart average in legs of
501 with double out matches the level; in the Cricket games, so that its marks
per round match those of a player with that average, a 24th of it.
"""

from __future__ import annotations

import random
from bisect import bisect_left
from collections.abc import Sequence
from typing import Any

from .board import RADIUS_MM, aim_point, bed_name, segment_at, top_bed
from .checkout import (
    BEDS_BY_BULL,
    FINISH_ORDER,
    FINISHING_SCORE,
    TREBLES,
    checkout,
    setup,
)
from .cricket import (
    BULL,
    CRICKET_NUMBERS,
    HIDDEN_CRICKET,
    MARKS_TO_CLOSE,
    WILD_MOUSE,
    by_value,
    play_visit,
    wild_mouse_bed,
    wild_mouse_order,
)
from .scoring import BULL_25_50, DOUBLE, MASTER, STRAIGHT, evaluate_visit

# 0 plays without the bot; otherwise the 3-dart average it plays, 20 to 120.
MIN_LEVEL = 20
MAX_LEVEL = 120
# Seconds between the bot's darts, and before its visit ends.
DEFAULT_DELAY = 2.0
MAX_DELAY = 10.0
BOT_DARTS = 3

# The scatter (standard deviation per axis, in millimetres) that plays a
# level: measured with play_leg() over 600 to 1,500 legs of 501 with double
# out per scatter, in steps of 0.2 to 5 mm; between two levels it is
# interpolated. The tests check the averages it plays.
SCATTER = (
    (20, 48.06),
    (25, 38.69),
    (30, 32.03),
    (35, 26.67),
    (40, 22.92),
    (45, 20.09),
    (50, 18.11),
    (55, 16.29),
    (60, 14.94),
    (65, 13.63),
    (70, 12.6),
    (75, 11.7),
    (80, 10.74),
    (85, 9.89),
    (90, 9.11),
    (95, 8.49),
    (100, 7.86),
    (105, 7.17),
    (110, 6.62),
    (115, 6.03),
    (120, 5.55),
)
# In the Cricket games, a level plays the marks per round (MPR) of a player
# with that 3-dart average: a 24th of it, 2.5 at 60 and 5 at 120, a common
# rule of thumb. The scatter was measured with play_cricket_leg() over 6,000
# legs per scatter, the bot against a player who never scores, and is
# interpolated between two levels. The tests check the MPR it plays.
AVERAGE_PER_MPR = 24
CRICKET_SCATTER = (
    (20, 97.06),
    (25, 71.21),
    (30, 50.78),
    (35, 36.79),
    (40, 29.42),
    (45, 24.99),
    (50, 22.0),
    (55, 19.79),
    (60, 18.15),
    (65, 16.7),
    (70, 15.49),
    (75, 14.5),
    (80, 13.64),
    (85, 12.74),
    (90, 12.08),
    (95, 11.4),
    (100, 10.71),
    (105, 10.12),
    (110, 9.51),
    (115, 8.99),
    (120, 8.51),
)


def valid_level(value: object) -> bool:
    """0 for no bot, or a level of 20 to 120."""
    return type(value) is int and (value == 0 or MIN_LEVEL <= value <= MAX_LEVEL)


def scatter(level: int, cricket: bool = False) -> float:
    """The scatter in millimetres that plays this 3-dart average, or in the
    Cricket games the marks per round that go with it."""
    table = CRICKET_SCATTER if cricket else SCATTER
    levels = [entry[0] for entry in table]
    level = min(max(level, levels[0]), levels[-1])
    index = bisect_left(levels, level)
    high_level, high = table[index]
    if high_level == level:
        return high
    low_level, low = table[index - 1]
    return low + (high - low) * (level - low_level) / (high_level - low_level)


# -- aiming ----------------------------------------------------------------------


def x01_aim(
    remaining: int,
    darts: int,
    out_mode: str = DOUBLE,
    opening: str = STRAIGHT,
    bull_mode: str = BULL_25_50,
) -> str:
    """The checkout route if one exists, else the setup shot, else the treble 20.

    Without double out, a score below 60 that the darts left cannot finish
    takes the biggest bed that does not bust. `opening` is the In mode the leg
    still waits for, straight once it is open: before the double or treble
    that opens it, the bot aims at one, see `_opening`.
    """
    if opening != STRAIGHT:
        return _opening(remaining, darts, opening, out_mode, bull_mode)
    if route := checkout(remaining, darts, out_mode, (), bull_mode):
        return route[0]
    if plan := setup(remaining, darts, (), out_mode, bull_mode):
        return plan.route[0]
    if out_mode == STRAIGHT and remaining < 60:
        return max(
            (bed for bed in BEDS_BY_BULL[bull_mode] if bed.score < remaining),
            key=lambda bed: (bed.score, -bed.multiplier),
        ).name
    return "T20"


def _opening(
    remaining: int, darts: int, in_mode: str, out_mode: str, bull_mode: str
) -> str:
    """The bed that opens a leg with double or master in: a double that wins,
    with master in and out a treble that wins as well; with master in the
    treble 20 where it does not bust, as it scores most; then a double ring that
    leaves a finish for the darts left, in the order routes finish on doubles;
    otherwise the double 20, or the biggest double that does not bust where it
    does."""
    lowest = 0 if out_mode == STRAIGHT else 2
    for name in FINISH_ORDER:
        if remaining == FINISHING_SCORE[name]:
            return name
    if in_mode == MASTER:
        for bed in reversed(TREBLES):
            if remaining == bed.score and out_mode != DOUBLE:
                return bed.name
        if remaining - TREBLES[-1].score >= lowest:
            return TREBLES[-1].name
    # The bullseye is too small to open with, unless it wins.
    for name in FINISH_ORDER[:-1]:
        need = remaining - FINISHING_SCORE[name]
        if checkout(need, darts - 1, out_mode, (), bull_mode):
            return name
    safe = [
        name for name in FINISH_ORDER if remaining - FINISHING_SCORE[name] >= lowest
    ]
    if not safe or "D20" in safe:
        return "D20"
    return max(safe, key=FINISHING_SCORE.__getitem__)


def cricket_aim(
    marks: list[int],
    points: int,
    others_marks: list[list[int]],
    others_points: list[int],
    numbers: tuple[int, ...] = CRICKET_NUMBERS,
    cut_throat: bool = False,
) -> str:
    """Close numbers, and score while behind.

    The bot first closes numbers that another player already scores on, then
    scores on a number it closed and another player has open while it is
    behind (in Cut-Throat: while another player has fewer points, on a number
    that player has open), and otherwise closes the next number in order.
    """
    slots = range(len(numbers))
    closed = [marks[slot] >= MARKS_TO_CLOSE for slot in slots]
    threats = [
        slot
        for slot in slots
        if not closed[slot]
        and any(other[slot] >= MARKS_TO_CLOSE for other in others_marks)
    ]
    if cut_throat:
        # Points go to the players with the number open; the fewest win.
        leaders = [
            index
            for index, other in enumerate(others_points)
            if other <= min(others_points)
        ]
        behind = bool(others_points) and min(others_points) < points
        scoring = [
            slot
            for slot in slots
            if closed[slot]
            and any(others_marks[index][slot] < MARKS_TO_CLOSE for index in leaders)
        ]
    else:
        behind = bool(others_points) and max(others_points) > points
        scoring = [
            slot
            for slot in slots
            if closed[slot]
            and any(other[slot] < MARKS_TO_CLOSE for other in others_marks)
        ]
    if threats and not (behind and scoring):
        return top_bed(numbers[threats[0]])
    if scoring and (behind or all(closed)):
        return top_bed(numbers[scoring[0]])
    open_slots = [slot for slot in slots if not closed[slot]]
    return top_bed(numbers[open_slots[0] if open_slots else 0])


def hidden_cricket_aim(
    marks: list[int],
    points: int,
    others_marks: list[list[int]],
    others_points: list[int],
    numbers: Sequence[int | None],
    darts: int,
) -> str:
    """Hidden Cricket, where None stands for a number that does not show yet:
    the bot plays the numbers that show as in Cricket, highest first. Once it
    has closed all of them but the bull while numbers are still hidden, it
    searches: the treble of a number that does not show, another one with every
    dart of the leg, so that it comes round to every number in turn."""
    slots = by_value(numbers)
    hidden = None in numbers
    if hidden and all(
        marks[slot] >= MARKS_TO_CLOSE for slot in slots if numbers[slot] != BULL
    ):
        candidates = sorted(set(range(1, 21)).difference(numbers), reverse=True)
        return top_bed(candidates[darts % len(candidates)])
    return cricket_aim(
        [marks[slot] for slot in slots],
        points,
        [[other[slot] for slot in slots] for other in others_marks],
        others_points,
        tuple(int(numbers[slot] or 0) for slot in slots),
    )


def _wild_mouse_bed(
    slot: int,
    marks: list[int],
    numbers: tuple[int, ...],
    targets: tuple[str, ...],
    visit: list[dict[str, Any]],
) -> str | None:
    """A bed of the board for a Wild Mouse target: any double or triple becomes
    the highest one whose number the bot has closed or that is no Cricket
    number, so that the dart counts for doubles or triples."""
    bed = wild_mouse_bed(slot, numbers, targets, visit)
    if bed not in ("D", "T"):
        return bed
    free = next(
        number
        for number in range(20, 0, -1)
        if number not in numbers or marks[numbers.index(number)] >= MARKS_TO_CLOSE
    )
    return f"{bed}{free}"


def wild_mouse_aim(
    marks: list[int],
    points: int,
    others_marks: list[list[int]],
    others_points: list[int],
    numbers: tuple[int, ...],
    targets: tuple[str, ...],
    visit: list[dict[str, Any]],
) -> str:
    """Close what others score on, score while behind, else close in order.

    As in Cricket, but over every target of Wild Mouse in the order players
    close them; three in a bed follows the first dart of the visit, and once the
    visit's darts can no longer make a bed, the next target takes over.
    """
    order = wild_mouse_order(numbers, targets)
    closed = {slot: marks[slot] >= MARKS_TO_CLOSE for slot in order}
    open_slots = [slot for slot in order if not closed[slot]]
    threats = [
        slot
        for slot in open_slots
        if any(other[slot] >= MARKS_TO_CLOSE for other in others_marks)
    ]
    scoring = [
        slot
        for slot in order
        if closed[slot] and any(other[slot] < MARKS_TO_CLOSE for other in others_marks)
    ]
    behind = bool(others_points) and max(others_points) > points
    if threats and not (behind and scoring):
        wanted = [*threats, *open_slots, *scoring]
    elif scoring and (behind or not open_slots):
        wanted = [*scoring, *open_slots]
    else:
        wanted = [*open_slots, *scoring]
    beds = (_wild_mouse_bed(slot, marks, numbers, targets, visit) for slot in wanted)
    return next((bed for bed in beds if bed), "T20")


def _dart(key: str) -> dict[str, Any]:
    """A dart of the snapshot's visit, such as T20, 25, BULL or MISS."""
    if key in ("25", "BULL"):
        return {"number": 25, "multiplier": 1 if key == "25" else 2}
    if key == "MISS":
        return {"number": 0, "multiplier": 0}
    return {"number": int(key[1:]), "multiplier": "SDT".index(key[0]) + 1}


def aim(snapshot: dict[str, Any]) -> str:
    """Where the bot aims next, from the practice game's snapshot."""
    if snapshot.get("bull_off"):
        return "BULL"
    thrown = len(snapshot.get("visit") or [])
    if "numbers" in snapshot:
        numbers = tuple(snapshot["numbers"])
        player = snapshot["player"]
        scores = snapshot["scores"]
        own = next(score for score in scores if score["player"] == player)
        team = own.get("team")
        others = [
            score
            for score in scores
            if score["player"] != player and (team is None or score.get("team") != team)
        ]
        if snapshot["game"] == HIDDEN_CRICKET:
            return hidden_cricket_aim(
                own["marks"],
                own["points"],
                [score["marks"] for score in others],
                [score["points"] for score in others],
                numbers,
                snapshot["darts"],
            )
        if snapshot["game"] == WILD_MOUSE:
            return wild_mouse_aim(
                own["marks"],
                own["points"],
                [score["marks"] for score in others],
                [score["points"] for score in others],
                numbers,
                tuple(snapshot["targets"]),
                [_dart(key) for key in snapshot["visit"]],
            )
        return cricket_aim(
            own["marks"],
            own["points"],
            [score["marks"] for score in others],
            [score["points"] for score in others],
            numbers,
            snapshot["game"] == "cut_throat",
        )
    return x01_aim(
        snapshot["remaining"],
        BOT_DARTS - thrown,
        snapshot.get("out_mode", DOUBLE),
        STRAIGHT
        if snapshot.get("opened") is not False
        else snapshot.get("in_mode", DOUBLE),
        snapshot.get("bull_mode", BULL_25_50),
    )


# -- throwing --------------------------------------------------------------------


class Bot:
    """Throws darts with the scatter of its level; the random numbers can be seeded."""

    def __init__(self, rng: random.Random | None = None) -> None:
        # Darts need no cryptographic randomness.
        self.rng = rng or random.Random()

    def throw(
        self, bed: str, level: int, cricket: bool = False
    ) -> tuple[dict[str, Any], tuple[float, float]]:
        """A dart aimed at the bed: its segment and its position on the board."""
        sigma = scatter(level, cricket)
        aim_x, aim_y = aim_point(bed)
        # Positions like the board's, relative to the outer edge of the double
        # ring; the bed is the one at the position the cards show.
        x = round((aim_x + self.rng.gauss(0, sigma)) / RADIUS_MM, 4)
        y = round((aim_y + self.rng.gauss(0, sigma)) / RADIUS_MM, 4)
        number, multiplier = segment_at(x * RADIUS_MM, y * RADIUS_MM)
        dart = {
            "number": number,
            "multiplier": multiplier,
            "name": bed_name(number, multiplier),
        }
        return dart, (x, y)


def play_leg(
    bot: Bot,
    level: int,
    start: int = 501,
    out_mode: str = DOUBLE,
    bull_mode: str = BULL_25_50,
) -> int:
    """The darts the bot needs for a leg alone, by the rules of the practice game.

    This is how the scatter of every level was calibrated, and how the tests
    check it.
    """
    remaining, total = start, 0
    while True:
        visit: list[dict[str, Any]] = []
        left, counted = remaining, 0
        outcome: str | None = None
        for dart in range(BOT_DARTS):
            bed = x01_aim(left, BOT_DARTS - dart, out_mode, STRAIGHT, bull_mode)
            visit.append(bot.throw(bed, level)[0])
            left, outcome, counted = evaluate_visit(
                remaining, visit, out_mode, bull_mode
            )
            if outcome:
                break
        total += counted
        if outcome == "won":
            return total
        remaining = left


def play_cricket_leg(
    bot: Bot, level: int, numbers: tuple[int, ...] = CRICKET_NUMBERS
) -> tuple[int, int]:
    """The marks that counted and the darts of the bot for a Cricket leg
    against a player who never scores, by the rules of the practice game.

    This is how the Cricket scatter of every level was calibrated, and how the
    tests check it.
    """
    marks, points, counted, total = [0] * len(numbers), 0, 0, 0
    others, scores = [[0] * len(numbers)], [0]
    while True:
        visit: list[dict[str, Any]] = []
        result = play_visit(marks, points, visit, others, scores, numbers)
        for _ in range(BOT_DARTS):
            bed = cricket_aim(result.marks, result.points, others, scores, numbers)
            visit.append(bot.throw(bed, level, cricket=True)[0])
            result = play_visit(marks, points, visit, others, scores, numbers)
            if result.won:
                break
        counted += result.counted
        total += result.darts
        if result.won:
            return counted, total
        marks, points = result.marks, result.points
