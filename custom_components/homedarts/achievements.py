"""The catalogue of achievements: milestones a player unlocks, most in tiers.

A value per player measures each achievement, such as the number of 180s or
the fewest darts of a 501 leg; every tier has a threshold the value must
reach. Achievements where fewer is better count the other way round.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Achievement:
    """One milestone and the thresholds of its tiers, the easiest first."""

    key: str
    tiers: tuple[int, ...]
    # Fewer darts are better, as in the shortest leg.
    lower: bool = False

    def tier(self, value: int | None) -> int:
        """The tiers the value reaches."""
        if value is None:
            return 0
        return sum(
            (value <= threshold) if self.lower else (value >= threshold)
            for threshold in self.tiers
        )

    def described(self) -> dict[str, Any]:
        return {"id": self.key, "tiers": list(self.tiers), "lower": self.lower}


CATALOGUE = (
    # Visits of an X01 game, as they scored.
    Achievement("maximum", (1, 10, 100)),
    Achievement("ton_plus", (10, 100, 1000)),
    Achievement("ton_forty", (10, 100, 500)),
    # Won X01 legs with double out, and finishes of the checkout training.
    Achievement("high_finish", (100, 150, 170)),
    Achievement("short_leg", (18, 15, 12), lower=True),
    Achievement("nine_darter", (9,), lower=True),
    Achievement("legs_won", (1, 50, 500)),
    Achievement("matches_won", (1, 25, 250)),
    # Three bulls in one visit, the outer bull or the bullseye.
    Achievement("hat_trick", (1,)),
    Achievement("all_doubles", (21,)),
    Achievement("cricket_nine", (1,)),
    Achievement("shanghai", (1,)),
    Achievement("around_the_clock", (40, 30, 21), lower=True),
    Achievement("bobs_27", (100, 250, 500)),
    Achievement("streak", (3, 7, 10, 30)),
    Achievement("darts_thrown", (1000, 10000, 100000)),
    # Training plans played to their end.
    Achievement("plans_finished", (1, 10, 100)),
)
ACHIEVEMENTS = {achievement.key: achievement for achievement in CATALOGUE}
