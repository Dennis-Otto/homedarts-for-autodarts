"""Personal bests, the training streak in days and the daily goal in darts."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

from .practice import GAMES

# Record -> whether a higher value is better.
RECORDS: dict[str, bool] = {
    "highest_visit": True,
    "highest_checkout": True,
    **{f"fewest_darts_{game}": False for game in GAMES},
    "best_cricket_mpr": True,
    "around_the_clock": False,
    "doubles": False,
    "bobs_27": True,
    "checkout_121": True,
    "catch_40": True,
    "jdc_challenge": True,
    "singles": True,
    "best_session_average": True,
}
# Training games whose score is the record.
SCORED_DRILLS = ("catch_40", "jdc_challenge", "singles")
# A session average needs this many darts to count as a record.
SESSION_DARTS = 30
DAILY_GOAL_MAX = 2000


def _day(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


def _count(value: object, high: int = 10**6) -> int:
    return value if type(value) is int and 0 <= value <= high else 0


def _value(value: object) -> float | int | None:
    """A record value: a finite number that is not negative."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _name(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


class PersonalRecords:
    """The best values ever, darts per day, the streak and the daily goal.

    The first value of a record sets it quietly; beating it announces a
    personal best. Every detected dart counts for the day, in a session or not.
    """

    def __init__(self) -> None:
        self.bests: dict[str, dict[str, Any]] = {}
        # The last personal best that beat an earlier value.
        self.latest: dict[str, Any] | None = None
        self.streak = 0
        self.best_streak = 0
        self.last_day: date | None = None
        # Darts of `day`; another day starts from zero.
        self.day: date | None = None
        self.darts_today = 0
        self.goal = 0
        self.goal_day: date | None = None

    # -- storage ---------------------------------------------------------------

    def restore(self, saved: object) -> None:
        if not isinstance(saved, dict):
            return
        bests = saved.get("bests")
        self.bests = {}
        for record, best in (bests if isinstance(bests, dict) else {}).items():
            if record not in RECORDS or not isinstance(best, dict):
                continue
            value = _value(best.get("value"))
            if value is not None and isinstance(best.get("date"), str):
                self.bests[record] = {
                    "value": value,
                    "date": best["date"],
                    "name": _name(best.get("name")),
                }
        latest = saved.get("latest")
        self.latest = (
            {
                "record": latest["record"],
                "value": latest.get("value"),
                "previous": latest.get("previous"),
                "name": _name(latest.get("name")),
                "date": latest.get("date"),
            }
            if isinstance(latest, dict)
            and isinstance(latest.get("record"), str)
            and latest["record"] in RECORDS
            and isinstance(latest.get("date"), str)
            else None
        )
        self.streak = _count(saved.get("streak"))
        self.best_streak = max(_count(saved.get("best_streak")), self.streak)
        self.last_day = _day(saved.get("last_day"))
        self.day = _day(saved.get("day"))
        self.darts_today = _count(saved.get("darts_today"))
        self.goal = _count(saved.get("goal"), DAILY_GOAL_MAX)
        self.goal_day = _day(saved.get("goal_day"))

    def merge(self, other: PersonalRecords) -> None:
        """Take over the bests of another board that beat those of this one,
        and its longest streak; the streak, the darts of the day and the daily
        goal stay those of this board."""
        for record, best in other.bests.items():
            ours = self.bests.get(record)
            if ours is None or (
                best["value"] > ours["value"]
                if RECORDS[record]
                else best["value"] < ours["value"]
            ):
                self.bests[record] = dict(best)
        self.best_streak = max(self.best_streak, other.best_streak)

    def stored(self) -> dict[str, Any]:
        return {
            "bests": {record: dict(best) for record, best in self.bests.items()},
            "latest": dict(self.latest) if self.latest else None,
            "streak": self.streak,
            "best_streak": self.best_streak,
            "last_day": _iso(self.last_day),
            "day": _iso(self.day),
            "darts_today": self.darts_today,
            "goal": self.goal,
            "goal_day": _iso(self.goal_day),
        }

    # -- counting --------------------------------------------------------------

    def set_goal(self, goal: int, today: date) -> None:
        """A goal that today's darts already reach counts as reached, quietly;
        a higher goal that they do not reach is still to be reached today."""
        self.goal = _count(goal, DAILY_GOAL_MAX)
        if self.goal and self._darts(today) >= self.goal:
            self.goal_day = today
        elif self.goal_day == today:
            self.goal_day = None

    def observe(
        self, kind: str, attributes: dict[str, Any], now: datetime
    ) -> list[tuple[str, dict[str, Any]]]:
        """The personal bests and the daily goal that an event brings."""
        events = self._dart(now.date()) if kind == "dart_detected" else []
        for record, value, name in self._candidates(kind, attributes):
            if (event := self._offer(record, value, name, now)) is not None:
                events.append(event)
        return events

    def _darts(self, today: date) -> int:
        return self.darts_today if self.day == today else 0

    def _dart(self, today: date) -> list[tuple[str, dict[str, Any]]]:
        self.darts_today = self._darts(today) + 1
        self.day = today
        if self.last_day != today:
            yesterday = today - timedelta(days=1)
            self.streak = self.streak + 1 if self.last_day == yesterday else 1
            self.best_streak = max(self.best_streak, self.streak)
            self.last_day = today
        if self.goal and self.darts_today >= self.goal and self.goal_day != today:
            self.goal_day = today
            return [
                (
                    "daily_goal_reached",
                    {
                        "goal": self.goal,
                        "darts": self.darts_today,
                        "streak": self.streak,
                    },
                )
            ]
        return []

    @staticmethod
    def _candidates(
        kind: str, attributes: dict[str, Any]
    ) -> list[tuple[str, float | int | None, str | None]]:
        value = attributes.get
        name = _name(value("name"))
        if kind == "visit_completed" and _count(value("darts")) <= 3:
            # Merged visits after a missed takeout are not one visit.
            return [("highest_visit", _value(value("score")), None)]
        # A team leg is no one player's: it sets no record of darts or marks.
        alone = value("team") is None
        if kind == "leg_won" and value("game") == "cricket":
            return [("best_cricket_mpr", _value(value("mpr")), name)] if alone else []
        if kind == "leg_won" and value("game") in GAMES:
            # Legs without double out finish more easily; they set no record,
            # nor do legs the round limit decided.
            if value("double_out") is not True or value("rounds") is not None:
                return []
            # A leg counts for the score it really started from.
            start = value("start") or value("game")
            records = [("highest_checkout", _value(value("checkout")), name)]
            if alone and start in GAMES:
                records.append((f"fewest_darts_{start}", _value(value("darts")), name))
            return records
        drill = value("drill")
        if kind == "drill_finished" and drill in ("around_the_clock", "doubles"):
            return [(str(drill), _value(value("darts")), None)]
        if kind == "drill_finished" and drill == "bobs_27":
            completed = value("completed") is True
            return [("bobs_27", _value(value("score")) if completed else None, None)]
        if kind == "drill_finished" and drill in SCORED_DRILLS:
            return [(str(drill), _value(value("score")), None)]
        if kind == "checkout_attempt" and drill == "checkout_121":
            success = value("success") is True
            return [
                ("checkout_121", _value(value("target")) if success else None, None)
            ]
        if kind == "session_ended" and _count(value("darts")) >= SESSION_DARTS:
            return [("best_session_average", _value(value("average")), None)]
        return []

    def _offer(
        self,
        record: str,
        value: float | int | None,
        name: str | None,
        now: datetime,
    ) -> tuple[str, dict[str, Any]] | None:
        if not value:
            return None
        best = self.bests.get(record)
        previous = best["value"] if best else None
        if previous is not None and (
            value <= previous if RECORDS[record] else value >= previous
        ):
            return None
        self.bests[record] = {"value": value, "date": now.isoformat(), "name": name}
        if previous is None:
            return None
        details = {"record": record, "value": value, "previous": previous, "name": name}
        self.latest = {**details, "date": now.isoformat()}
        return "personal_best", details

    # -- undo and deleted players ----------------------------------------------

    def checkpoint(self) -> dict[str, Any]:
        """The personal bests before a visit counts, to undo it."""
        return {
            "bests": {record: dict(best) for record, best in self.bests.items()},
            "latest": dict(self.latest) if self.latest else None,
        }

    def rewind(self, checkpoint: dict[str, Any]) -> None:
        """Back to the personal bests of the checkpoint, as when the undone visit
        never counted. Its darts were thrown: they stay darts of the day, of the
        streak and of the daily goal."""
        self.bests = checkpoint["bests"]
        self.latest = checkpoint["latest"]

    def forget(self, name: str) -> None:
        """Remove a player's name from the records; the values stay."""
        key = name.strip().casefold()
        for best in [*self.bests.values(), *([self.latest] if self.latest else [])]:
            if (best.get("name") or "").strip().casefold() == key:
                best["name"] = None

    # -- state -----------------------------------------------------------------

    def snapshot(self, today: date) -> dict[str, Any]:
        darts = self._darts(today)
        alive = self.last_day in (today, today - timedelta(days=1))
        return {
            "streak": self.streak if alive else 0,
            "best_streak": self.best_streak,
            "trained_today": self.last_day == today,
            "last_day": _iso(self.last_day),
            "darts_today": darts,
            "goal": self.goal,
            "goal_reached": bool(self.goal) and self.goal_day == today,
            "progress": min(round(darts * 100 / self.goal, 1), 100.0)
            if self.goal
            else None,
            "bests": {record: best["value"] for record, best in self.bests.items()},
            "latest": dict(self.latest) if self.latest else None,
        }
