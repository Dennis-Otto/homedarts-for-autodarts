"""Hit rates of every double, the doubles a player finishes on best, and how
often every double was hit at all.

A dart counts as an attempt at a double when that double is the target: in
X01, the checkout training, 121 and Catch 40 when one double could finish the
remaining score, in the doubles training and in Bob's 27 at the double of the
round, and in the JDC Challenge at the double of the step. A hit counts for
every dart in a double, whatever it was aimed at.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .scoring import BULL, is_double

DOUBLES = (*(f"D{number}" for number in range(1, 21)), "BULL")
# A double needs this many attempts before it changes a checkout route.
MIN_ATTEMPTS = 10


def double_of(number: int) -> str:
    return "BULL" if number == BULL else f"D{number}"


def aimed_at(remaining: int) -> str | None:
    """The double that finishes this score with one dart, if any."""
    if remaining == 50:
        return "BULL"
    if 2 <= remaining <= 40 and remaining % 2 == 0:
        return f"D{remaining // 2}"
    return None


def hits(dart: dict[str, Any], double: str) -> bool:
    return bool(dart["multiplier"] == 2 and double_of(dart["number"]) == double)


class DoubleHits:
    """How often every double was hit, whatever the dart was aimed at."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def record(self, darts: Iterable[dict[str, Any]]) -> None:
        for dart in darts:
            # The made-up darts of a visit entered as its score hit no bed.
            if is_double(dart) and not dart.get("bot") and not dart.get("total"):
                double = double_of(dart["number"])
                self.counts[double] = self.counts.get(double, 0) + 1

    def snapshot(self) -> dict[str, int]:
        return {
            double: self.counts[double] for double in DOUBLES if double in self.counts
        }

    def stored(self) -> dict[str, int]:
        return dict(self.counts)

    def restore(self, saved: object) -> None:
        self.counts = {
            double: count
            for double, count in (saved if isinstance(saved, dict) else {}).items()
            if double in DOUBLES and type(count) is int and count > 0
        }


class DoubleStats:
    """Attempts and hits per double."""

    def __init__(self) -> None:
        self.counts: dict[str, list[int]] = {}

    def record(self, attempts: list[tuple[str, bool]]) -> None:
        for double, hit in attempts:
            if double in DOUBLES:
                count = self.counts.setdefault(double, [0, 0])
                count[0] += 1
                count[1] += int(hit)

    def rate(self, double: str) -> float | None:
        attempts, hit = self.counts.get(double, (0, 0))
        return round(hit * 100 / attempts, 1) if attempts else None

    def preferred(self) -> tuple[str, ...]:
        """The player's strong doubles, the best hit rate first: those with
        enough attempts that are hit at least as often as all doubles
        together. A double never hit is never one of them."""
        attempts = sum(count[0] for count in self.counts.values())
        hit = sum(count[1] for count in self.counts.values())
        strong = [
            double
            for double in DOUBLES
            if double in self.counts
            and (count := self.counts[double])[0] >= MIN_ATTEMPTS
            and count[1] > 0
            # Hits per attempt at least the overall rate, without rounding.
            and count[1] * attempts >= hit * count[0]
        ]
        return tuple(
            sorted(
                strong,
                key=lambda double: (-(self.rate(double) or 0), -self.counts[double][0]),
            )
        )

    def snapshot(self) -> dict[str, Any]:
        attempts = sum(count[0] for count in self.counts.values())
        hit = sum(count[1] for count in self.counts.values())
        preferred = self.preferred()
        return {
            "attempts": attempts,
            "hits": hit,
            "rate": round(hit * 100 / attempts, 1) if attempts else None,
            "favourite": preferred[0] if preferred else None,
            "doubles": [
                {
                    "double": double,
                    "attempts": self.counts[double][0],
                    "hits": self.counts[double][1],
                    "rate": self.rate(double),
                }
                for double in DOUBLES
                if double in self.counts
            ],
        }

    def stored(self) -> dict[str, list[int]]:
        return {double: list(count) for double, count in self.counts.items()}

    def restore(self, saved: object) -> None:
        self.counts = {
            double: list(count)
            for double, count in (saved if isinstance(saved, dict) else {}).items()
            if double in DOUBLES
            and isinstance(count, list)
            and len(count) == 2
            and all(type(value) is int and value >= 0 for value in count)
            and count[1] <= count[0]
        }
