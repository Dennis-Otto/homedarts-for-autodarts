"""A hand that Board Manager 2.1 sees all the time, and so no dart.

A real board did this when its light ring was switched on with its detection running.
For over seven minutes every frame of its motion said isHand, isTakeoutFull and
isTakeoutPartial, its cameras reported pixels that are 0 on a healthy board, and six
darts thrown at it changed nothing. An auto calibration moved the state to throw but left
the flags. A stop and a start of the detection cleared it at once, with the ring still
on. That the light changed against the reference image of the board is the best
explanation so far, not proven.

A hand that doesn't change for a long time isn't a hand. The frames tell it from someone
at the board as far as they can: the picture of a hand that moves stays unsettled, while
that of the stuck board stood still. Someone who holds a hand still in front of the board
for a whole minute counts as stuck: the notice goes with the hand, and a restart happens
only on an empty board without a game, where it costs nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# A real takeout lasted 1.1 to 2.5 seconds, so a minute leaves plenty of margin, also
# for someone at the board.
STUCK_HAND_SECONDS = 60
# The picture of a hand that pulled darts stayed unsettled for 1.3 to 1.8 seconds at a
# time. That of the stuck board did for 0.6 seconds at most, and a dart that lands shakes
# it for 0.2 seconds at most, so neither of them starts the wait anew.
MOVING_SECONDS = 1


@dataclass
class HandWatch:
    """How long a board has shown a hand whose picture stands still, and what became
    of it. All times are seconds of time.monotonic."""

    # Since when the picture of the hand stands still, and since when it no longer does.
    still_since: float | None = None
    unsettled_since: float | None = None
    gone_since: float | None = None
    # The hand counts as stuck, and everyone was told.
    reported: bool = False
    # The one automatic restart of the detection of this occurrence happened.
    restarted: bool = False

    def nothing_known(self) -> None:
        """A stopped detection or a lost connection says nothing of the hand: what was
        told stays, and the wait starts anew once the board reports again."""
        self.still_since = self.unsettled_since = None

    def hand(self, motion: dict[str, Any], now: float) -> float:
        """A reading with a hand; the seconds left until it counts as stuck."""
        self.gone_since = None
        if self.still_since is None:
            self.still_since = now
        unsettled = self.unsettled_since
        if unsettled is not None and now - unsettled >= MOVING_SECONDS:
            self.still_since = now
        if motion.get("isStable") is not False:
            self.unsettled_since = None
        elif unsettled is None:
            self.unsettled_since = now
        left = self.still_since + STUCK_HAND_SECONDS - now
        if self.unsettled_since is not None:
            # It may be someone at the board, which takes a moment to tell.
            left = max(left, self.unsettled_since + MOVING_SECONDS - now)
        return max(0.0, left)

    def no_hand(self, now: float) -> bool:
        """A reading without a hand; whether it ends a hand that counted as stuck. One
        that comes back within a minute is the same occurrence, so that a board that
        loses it for a moment isn't restarted again and again."""
        self.nothing_known()
        if self.gone_since is None:
            self.gone_since = now
        if now - self.gone_since >= STUCK_HAND_SECONDS:
            self.restarted = False
        ended, self.reported = self.reported, False
        return ended
