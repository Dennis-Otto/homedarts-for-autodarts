"""Which steps of the browser test a run takes, decided without a browser.

Every step of browser.py belongs to one of four groups that take about the same
time. ``BROWSER_SHARD=k/n`` runs the groups ``g`` with ``(g - 1) % n == k - 1``, so
one, two and four shards each run every group once: shard 1/2 runs the groups 1 and
3, shard 2/4 the group 2. ``BROWSER_STEPS`` picks steps by the beginning of their
names, in a shard or in the whole run. The steps keep their order, and each one but
those that read the demo as demo.py left it starts from the board between games
(``Board.between_games`` in browser.py), so every choice of steps passes as the whole
run does. A drill, a step that fails on purpose, runs only when ``BROWSER_STEPS``
names it by its whole name.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

GROUPS = 4
# The seconds that a step may take before the watchdog fails it (watchdog.py): about
# three times its longest run in CI, and at least two minutes.
BUDGET = 120.0


@dataclass(frozen=True)
class Step:
    """A step of the browser test: its name, its group and what it runs."""

    name: str
    group: int
    run: Callable[[], None]
    # Reads the demo as demo.py left it, such as the visit on the board: it comes
    # before every step that changes the board, and nothing is reset before it.
    as_started: bool = False
    # The seconds after which the watchdog fails the step.
    budget: float = BUDGET
    # Fails on purpose, to show what a failure of its kind leaves behind: runs only
    # when BROWSER_STEPS names it by its whole name, never in a shard of its own.
    drill: bool = False


class Choice(ValueError):
    """BROWSER_STEPS or BROWSER_SHARD asks for something the steps can't give."""


def shard(value: str) -> tuple[int, int]:
    """BROWSER_SHARD as (k, n): the k-th of n shards, or (1, 1) for the whole run."""
    if not value.strip():
        return 1, 1
    found = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", value)
    if not found or not 1 <= int(found[1]) <= int(found[2]):
        raise Choice(
            f"BROWSER_SHARD is k/n with 1 <= k <= n, such as 2/4, not {value!r}"
        )
    part, parts = int(found[1]), int(found[2])
    if parts > GROUPS:
        raise Choice(
            f"BROWSER_SHARD={value.strip()}: the steps have {GROUPS} groups, "
            f"so there are at most {GROUPS} shards"
        )
    return part, parts


def names(value: str) -> list[str]:
    """BROWSER_STEPS as the names, or beginnings of names, of the steps it asks for."""
    return [name.strip() for name in value.split(",") if name.strip()]


def asked(step: Step, wanted: str, steps: Sequence[Step]) -> bool:
    """Whether BROWSER_STEPS asks for the step with one of its words: the whole name of
    a step asks for that step alone, such as "training card" without the "training card
    editor", and a beginning for every step it begins, such as "touch". A drill only
    by its whole name."""
    if step.drill or any(other.name == wanted for other in steps):
        return step.name == wanted
    return step.name.startswith(wanted)


def choose(steps: Sequence[Step], wanted: str = "", part: str = "") -> list[Step]:
    """The steps to run, in their order: those of the shard ``part`` that ``wanted``
    asks for, or all of them but the drills for empty values."""
    for step in steps:
        if not 1 <= step.group <= GROUPS:
            raise Choice(f"{step.name}: group {step.group} is not 1 to {GROUPS}")
    words = names(wanted)
    unknown = sorted(
        word for word in words if not any(asked(step, word, steps) for step in steps)
    )
    if unknown:
        raise Choice(f"BROWSER_STEPS names no step: {unknown}")
    k, n = shard(part)
    return [
        step
        for step in steps
        if (step.group - 1) % n == k - 1
        and (
            any(asked(step, word, steps) for word in words) if words else not step.drill
        )
    ]
