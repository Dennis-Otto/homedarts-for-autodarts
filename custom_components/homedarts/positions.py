"""Where darts land: board positions, the bed aimed at, and the grouping around it.

The Board Manager reports a position for most darts, relative to the outer
edge of the double ring (170 mm) with y pointing to the 20. A log keeps the
newest positions together with the bed the dart was aimed at, where the game
knows it; the grouping of the darts at one bed is worked out from them.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

from .aim import MIN_DARTS, ErrorModel, best_aim
from .board import RADIUS_MM, aim_point
from .doubles import aimed_at
from .scoring import BULL_25_50, DOUBLE, STRAIGHT, VISIT_DARTS, fits, score

# The beds a dart can be aimed at, as the log stores them by position; the
# singles are too wide to tell where a player aimed.
AIMS = (
    "BULL",
    *(f"T{number}" for number in range(1, 21)),
    *(f"D{number}" for number in range(1, 21)),
)
# X01 visits that no checkout can finish aim at the treble 20.
SCORING_AIM = "T20"
# Positions further out than this are no darts on the board.
MAX_DISTANCE = 3.0
# A grouping needs this many darts; the trend compares two halves of them.
MIN_GROUP = 10
GROUPS = 6
# The error model of the aim map keeps the darts within this squared distance
# from the others, in the units of their spread: 99 % of the darts of a normal
# distribution. A dart further out was most likely aimed at another bed than the
# game assumes, such as the treble 19 in a scoring visit.
TRIM = -2 * math.log(0.01)
# The darts within it spread less than all of them, by this factor (the share of
# a chi-square distribution with 4 degrees of freedom within TRIM, divided by the
# share of one with 2), which the spread makes up for.
TRIMMED = (1 - 0.01 * (1 + TRIM / 2)) / (1 - 0.01)
TRIM_ROUNDS = 4
# A circular normal spread holds half of its darts within this many standard
# deviations, which makes the median distance a first estimate of the spread.
MEDIAN_RADIUS = math.sqrt(2 * math.log(2))
# The spread of a model is at least this many millimetres, and its correlation
# at most this strong, so that the distribution never collapses onto a line.
MIN_SD = 0.5
MAX_CORRELATION = 0.95


def x01_aims(
    start: int,
    darts: list[dict[str, Any]],
    out_mode: str,
    opening: int | None,
    route: Callable[[int, int], tuple[str, ...]],
    bull_mode: str = BULL_25_50,
) -> list[str | None]:
    """The bed each dart of an X01 visit was aimed at, where it is known.

    With double out, a score one double finishes aims at that double; a score
    no checkout can finish with the darts left is a scoring visit at the treble
    20; otherwise the first bed of the route. `opening` is the place of the
    double or treble that opens the leg with double or master in, while the leg
    still needs one: darts up to it aim at any. Darts at a single, and darts
    after a bust or the finish, have no aim either.
    """
    aims: list[str | None] = []
    remaining: int | None = start
    for index, dart in enumerate(darts[:VISIT_DARTS]):
        aim: str | None = None
        if remaining is not None and (opening is None or index > opening):
            finish = aimed_at(remaining) if out_mode == DOUBLE else None
            path = route(remaining, VISIT_DARTS - index)
            aim = finish or (path[0] if path else SCORING_AIM)
        aims.append(aim if aim in AIMS else None)
        if remaining is None or (opening is not None and index < opening):
            continue
        left = remaining - score(dart, bull_mode)
        busted = (
            left < 0
            or (out_mode != STRAIGHT and left == 1)
            or (left == 0 and not fits(dart, out_mode))
        )
        remaining = None if busted or left == 0 else left
    return aims


def _percentile(distances: list[float], share: float) -> float:
    """The smallest radius that holds this share of the darts."""
    return distances[math.ceil(share * len(distances)) - 1]


def _grouping(offsets: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Mean offset and the radii around it holding 50 and 80 percent."""
    mean_x = sum(x for x, _ in offsets) / len(offsets)
    mean_y = sum(y for _, y in offsets) / len(offsets)
    distances = sorted(math.hypot(x - mean_x, y - mean_y) for x, y in offsets)
    return mean_x, mean_y, _percentile(distances, 0.5), _percentile(distances, 0.8)


def spread(darts: Iterable[tuple[float, float, str | None]]) -> list[dict[str, Any]]:
    """The grouping at every bed aimed at with enough darts, most darts first.

    Offsets are millimetres from the centre of the bed, x to the right and y
    up. The radii hold 50 and 80 percent of the darts around their mean
    point; `change` compares the radius of the newer half of the darts with
    the older half, negative when the grouping got tighter.
    """
    groups: dict[str, list[tuple[float, float]]] = {}
    for x, y, aim in darts:
        if aim in AIMS:
            target_x, target_y = aim_point(aim)
            groups.setdefault(aim, []).append(
                (x * RADIUS_MM - target_x, y * RADIUS_MM - target_y)
            )
    result: list[dict[str, Any]] = []
    for aim, offsets in groups.items():
        if len(offsets) < MIN_GROUP:
            continue
        mean_x, mean_y, r50, r80 = _grouping(offsets)
        change = None
        if len(offsets) >= 2 * MIN_GROUP:
            half = len(offsets) // 2
            change = round(
                _grouping(offsets[half:])[2] - _grouping(offsets[:half])[2], 1
            )
        result.append(
            {
                "target": aim,
                "darts": len(offsets),
                "offset_x": round(mean_x, 1),
                "offset_y": round(mean_y, 1),
                "r50": round(r50, 1),
                "r80": round(r80, 1),
                "change": change,
            }
        )
    result.sort(key=lambda group: (-group["darts"], AIMS.index(group["target"])))
    return result[:GROUPS]


def _model(
    mean: tuple[float, float], covariance: tuple[float, float, float]
) -> tuple[float, float, float, float, float]:
    """Mean, standard deviations and correlation within the limits of a model."""
    sd_x, sd_y = (max(math.sqrt(covariance[i]), MIN_SD) for i in (0, 2))
    correlation = max(
        -MAX_CORRELATION, min(MAX_CORRELATION, covariance[1] / (sd_x * sd_y))
    )
    return mean[0], mean[1], sd_x, sd_y, correlation


def _moments(
    offsets: list[tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float, float]]:
    """Mean point and covariance (xx, xy, yy) of offsets."""
    count = len(offsets)
    mean_x = sum(x for x, _ in offsets) / count
    mean_y = sum(y for _, y in offsets) / count
    xx = sum((x - mean_x) ** 2 for x, _ in offsets) / count
    xy = sum((x - mean_x) * (y - mean_y) for x, y in offsets) / count
    yy = sum((y - mean_y) ** 2 for _, y in offsets) / count
    return (mean_x, mean_y), (xx, xy, yy)


def aim_model(darts: Iterable[tuple[float, float, str | None]]) -> dict[str, Any]:
    """The error model of the aim map, from the darts aimed at any treble.

    Every dart becomes its offset in millimetres from the centre of the treble it
    was aimed at, in the board's directions, x to the right and y up: a player's
    miss to the left stays one to the left wherever they aim. The model is the
    mean offset and the bivariate normal spread around it. It starts from the
    median point and the median distance from it, and four times keeps the darts
    within TRIM of the model so far and measures them again, so that a few darts
    aimed elsewhere do not widen it. With fewer than MIN_DARTS darts at the
    trebles there is no model, only their count.
    """
    offsets = []
    for x, y, aim in darts:
        if aim is not None and aim[0] == "T":
            target_x, target_y = aim_point(aim)
            offsets.append((x * RADIUS_MM - target_x, y * RADIUS_MM - target_y))
    result: dict[str, Any] = {"darts": len(offsets), "needed": MIN_DARTS}
    if len(offsets) < MIN_DARTS:
        return result
    centre = (median(x for x, _ in offsets), median(y for _, y in offsets))
    radius = median(math.hypot(x - centre[0], y - centre[1]) for x, y in offsets)
    variance = (radius / MEDIAN_RADIUS) ** 2
    model = _model(centre, (variance, 0.0, variance))
    for _ in range(TRIM_ROUNDS):
        mean_x, mean_y, sd_x, sd_y, correlation = model
        determinant = 1 - correlation**2
        kept = [
            (x, y)
            for x, y in offsets
            if (
                ((x - mean_x) / sd_x) ** 2
                - 2 * correlation * (x - mean_x) * (y - mean_y) / (sd_x * sd_y)
                + ((y - mean_y) / sd_y) ** 2
            )
            / determinant
            <= TRIM
        ]
        mean, (xx, xy, yy) = _moments(kept)
        model = _model(mean, (xx / TRIMMED, xy / TRIMMED, yy / TRIMMED))
    # Half millimetres are finer than a few hundred darts can tell; a model that
    # stays the same needs no new search for the best aim.
    offset_x, offset_y, sd_x, sd_y, correlation = model
    return {
        **result,
        "offset_x": round(offset_x * 2) / 2,
        "offset_y": round(offset_y * 2) / 2,
        "sd_x": round(sd_x * 2) / 2,
        "sd_y": round(sd_y * 2) / 2,
        "correlation": round(correlation * 20) / 20,
    }


def error_model(model: dict[str, Any]) -> ErrorModel | None:
    """The error model of an aim model, or None without enough darts."""
    if "sd_x" not in model:
        return None
    return ErrorModel(
        model["offset_x"],
        model["offset_y"],
        model["sd_x"],
        model["sd_y"],
        model["correlation"],
    )


@dataclass(frozen=True)
class Aim:
    """The aim model of a log's darts with its best aim, and the version of the
    darts it was worked out for."""

    version: int
    model: dict[str, Any]
    errors: ErrorModel | None = None
    best: dict[str, Any] | None = None

    def view(self) -> dict[str, Any]:
        """The model with its best aim, for the cards."""
        best = self.best_aim()
        return {**self.model, **({"best": best} if best else {})}

    def best_aim(self) -> dict[str, Any] | None:
        best = self.best
        return {**best, "compared": dict(best["compared"])} if best else None


# What a log knows before its first aim model is worked out.
NO_AIM = Aim(-1, {"darts": 0, "needed": MIN_DARTS})


def work_out_aim(
    version: int, darts: Sequence[tuple[float, float, str | None]], previous: Aim
) -> Aim:
    """The aim model of the darts, with the best aim searched anew only when the
    model differs from the previous one. It takes some milliseconds, the search
    some tens, so it runs in an executor, never on the event loop."""
    model = aim_model(darts)
    errors = error_model(model)
    if errors is None:
        return Aim(version, model)
    if errors == previous.errors:
        return Aim(version, model, errors, previous.best)
    return Aim(version, model, errors, best_aim(errors))


class DartLog:
    """The newest dart positions with the bed aimed at, oldest first.

    Positions are stored in tenths of a millimetre and the aim by its place in
    AIMS, three numbers per dart, which keeps a thousand darts small.
    """

    def __init__(self, size: int) -> None:
        self.darts: deque[tuple[float, float, str | None]] = deque(maxlen=size)
        # The grouping changes only with a new dart; the sensors ask often.
        self._spread: list[dict[str, Any]] | None = None
        # Every change of the darts counts, so that an aim model worked out off
        # the event loop is known to belong to the darts as they are.
        self.version = 0
        self._aim = NO_AIM

    def __len__(self) -> int:
        return len(self.darts)

    def __deepcopy__(self, memo: dict[int, Any]) -> DartLog:
        """A copy for undo: the positions are immutable, so copying is quick."""
        log = DartLog(self.darts.maxlen or 0)
        log.darts.extend(self.darts)
        log._spread = self._spread
        log.version = self.version
        log._aim = self._aim
        return log

    def add(self, position: tuple[float, float] | None, aim: str | None) -> None:
        if position is None or math.hypot(*position) > MAX_DISTANCE:
            return
        x, y = position
        self.darts.append((x, y, aim if aim in AIMS else None))
        self._spread = None
        self.version += 1

    def clear(self) -> None:
        self.darts.clear()
        self._spread = None
        self.version += 1

    def join(self, earlier: DartLog) -> None:
        """Put the darts of another log before these, as thrown earlier; the
        newest stay, as many as the log keeps."""
        darts = [*earlier.darts, *self.darts]
        self.darts.clear()
        self.darts.extend(darts)
        self._spread = None
        self.version += 1

    def positions(self) -> list[list[float]]:
        """Normalised positions like the visit sensor's, for the cards."""
        return [[round(x, 3), round(y, 3)] for x, y, _ in self.darts]

    def spread(self) -> list[dict[str, Any]]:
        if self._spread is None:
            self._spread = spread(self.darts)
        return [dict(group) for group in self._spread]

    @property
    def aim_stale(self) -> bool:
        """Whether darts came or went since the newest aim model."""
        return self._aim.version != self.version

    def aim_job(self) -> Callable[[], Aim]:
        """Work out the aim model of the darts as they are now, in an executor;
        they are copied here, on the event loop."""
        version, darts, previous = self.version, tuple(self.darts), self._aim
        return lambda: work_out_aim(version, darts, previous)

    def store_aim(self, aim: Aim) -> bool:
        """Keep an aim model unless a newer one is kept; whether the best aim
        changed with it."""
        if aim.version <= self._aim.version:
            return False
        changed = aim.best != self._aim.best
        self._aim = aim
        return changed

    def aim(self) -> dict[str, Any]:
        """The newest aim model worked out, with its best aim, for the cards."""
        return self._aim.view()

    def best_aim(self) -> dict[str, Any] | None:
        """The best aim of the newest aim model; it stays until the next one."""
        return self._aim.best_aim()

    def stored(self) -> list[int]:
        scale = RADIUS_MM * 10
        flat: list[int] = []
        for x, y, aim in self.darts:
            flat.extend(
                (round(x * scale), round(y * scale), AIMS.index(aim) + 1 if aim else 0)
            )
        return flat

    def restore(self, saved: object) -> None:
        self.clear()
        if not isinstance(saved, list) or len(saved) % 3:
            return
        scale = RADIUS_MM * 10
        limit = MAX_DISTANCE * scale
        for index in range(0, len(saved), 3):
            x, y, aim = saved[index : index + 3]
            if not all(type(value) is int for value in (x, y, aim)):
                continue
            if abs(x) > limit or abs(y) > limit or not 0 <= aim <= len(AIMS):
                continue
            self.add((x / scale, y / scale), AIMS[aim - 1] if aim else None)
