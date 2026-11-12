"""Count observed local darts, including corrections, without replaying snapshots."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from .board import bed_name
from .const import LIFECYCLE_STATUSES
from .moments import parse_moment, stamp

# Finished sessions and completed visits kept for the cards.
HISTORY_SIZE = 20
RECENT_VISITS = 10
IDLE_MINUTES_MAX = 240

# Totals that only grow during a session.
COUNTERS = (
    "darts",
    "points",
    "doubles",
    "triples",
    "bulls",
    "misses",
    "visits",
    "scores_100",
    "scores_140",
    "scores_180",
)
# Visit scores are bucketed like darts statistics: 100-139, 140-179 and 180.
SCORE_BUCKETS = (("scores_100", 100, 140), ("scores_140", 140, 180))
# Where a dart came from, besides the board: entered or corrected by hand in
# Home Assistant, or thrown by the practice game's bot. The darts of a visit
# entered as its score are made up, `total`: only their score counts, and
# `at_double` says which of them the player threw at a double.
DART_FLAGS = ("manual", "corrected", "bot", "total", "at_double")


def segments(state: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Use semantic segment values, ignoring jittering camera coordinates."""
    count = state.get("numThrows")
    throws = state.get("throws", [])
    if (
        type(count) is not int
        or count < 0
        or not isinstance(throws, list)
        or len(throws) != count
    ):
        return None
    result = []
    for dart in throws:
        if not isinstance(dart, dict):
            return None
        segment = dart.get("segment") or {}
        if not isinstance(segment, dict):
            return None
        number, multiplier = segment.get("number", 0), segment.get("multiplier", 0)
        if type(number) is not int or type(multiplier) is not int:
            return None
        if number not in (*range(21), 25) or multiplier not in range(4):
            return None
        # Only a miss has no number; the bull has no treble.
        if (number == 0 and multiplier) or (number == 25 and multiplier == 3):
            return None
        name = segment.get("name")
        result.append(
            {
                "number": number,
                "multiplier": multiplier,
                "name": name if isinstance(name, str) else None,
                **{flag: True for flag in DART_FLAGS if dart.get(flag) is True},
            }
        )
    return result


def dart_flags(darts: list[dict[str, Any]]) -> dict[str, bool]:
    """manual when a dart was entered or corrected by hand, bot for the bot's."""
    flags = {}
    if any(dart.get("manual") or dart.get("corrected") for dart in darts):
        flags["manual"] = True
    if any(dart.get("bot") for dart in darts):
        flags["bot"] = True
    if any(dart.get("total") for dart in darts):
        flags["total"] = True
    return flags


def beds(darts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The darts whose bed is known: not those of a visit entered as its score."""
    return [dart for dart in darts if not dart.get("total")]


def hit_key(dart: dict[str, Any]) -> str:
    """A stable name per bed: S20, D16, T19, 25 (outer bull), BULL or MISS."""
    return bed_name(dart["number"], dart["multiplier"])


def _visit_details(darts: list[dict[str, Any]]) -> dict[str, Any]:
    """Score, darts and segments of a visit, as its events announce them."""
    return {
        "score": sum(d["number"] * d["multiplier"] for d in darts),
        "darts": len(darts),
        "segments": [d["name"] or hit_key(d) for d in beds(darts)],
    }


def _visit_summary(darts: list[dict[str, Any]]) -> dict[str, int]:
    points = sum(d["number"] * d["multiplier"] for d in darts)
    # A visit has three darts; a missed takeout can merge more, which never scores.
    regular = 0 < len(darts) <= 3
    summary = {
        name: int(regular and low <= points < high) for name, low, high in SCORE_BUCKETS
    }
    summary["scores_180"] = int(len(darts) == 3 and points == 180)
    return summary


def _visit_high(contribution: dict[str, int]) -> int:
    """The score a visit offers as the highest visit: none for darts merged
    after a missed takeout, as for the score bands of _visit_summary."""
    return contribution["points"] if 0 < contribution["darts"] <= 3 else 0


def is_takeout(state: dict[str, Any]) -> bool:
    """The Board Manager reports removal in its status or last event."""
    return any(
        "takeout" in str(state.get(key, "")).lower() for key in ("status", "event")
    )


def _key(dart: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    """A dart as a whole: its bed, its name and where it came from."""
    return tuple(sorted(dart.items()))


def _contains(darts: list[dict[str, Any]], subset: list[dict[str, Any]]) -> bool:
    remaining = [_key(dart) for dart in darts]
    for dart in subset:
        if _key(dart) not in remaining:
            return False
        remaining.remove(_key(dart))
    return True


def _timestamp(value: object) -> str | None:
    """A stored ISO timestamp with a time zone; anything else is dropped."""
    if isinstance(value, str):
        parsed = parse_moment(value)
        if parsed and parsed.tzinfo:
            return value
    return None


def _count(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _summarize(started: str, ended: str, totals: dict[str, Any]) -> dict[str, Any]:
    """Counts, 3-dart average and duration of a finished session."""
    counts = {
        key: _count(totals.get(key))
        for key in (*COUNTERS, "highest_visit", "manual_darts", "total_darts")
    }
    begin, end = parse_moment(started), parse_moment(ended)
    seconds = (end - begin).total_seconds() if begin and end else 0
    darts = counts["darts"]
    return {
        "started": started,
        "ended": ended,
        "duration_minutes": round(max(seconds, 0) / 60, 1),
        **counts,
        "average": round(counts["points"] / darts * 3, 2) if darts else None,
    }


def _restored_summary(saved: object) -> dict[str, Any] | None:
    if not isinstance(saved, dict):
        return None
    started, ended = _timestamp(saved.get("started")), _timestamp(saved.get("ended"))
    if not started or not ended:
        return None
    return _summarize(started, ended, saved)


def _restored_visit(saved: object) -> dict[str, Any] | None:
    if not isinstance(saved, dict):
        return None
    time, names = _timestamp(saved.get("time")), saved.get("segments")
    if not time or not isinstance(names, list):
        return None
    if not all(isinstance(name, str) for name in names):
        return None
    return {
        "time": time,
        "score": _count(saved.get("score")),
        "darts": _count(saved.get("darts")),
        "segments": list(names),
        **{flag: True for flag in ("manual", "total") if saved.get(flag) is True},
    }


class TrainingSession:
    """Training sessions of observed darts, with one revisable active visit.

    Dart and visit events are announced whether or not a session runs, so
    automations work in every game; only darts thrown during a session count.
    """

    def __init__(self, now: datetime) -> None:
        self.started = stamp(now)
        self.ended: str | None = None
        # Version 1.0 counted every dart; without an explicit start, it still does.
        self.active = True
        self.auto_start = True
        self.idle_minutes = 0
        self.last_activity: str | None = None
        self.history: list[dict[str, Any]] = []
        self.recent_visits: list[dict[str, Any]] = []
        self._committed = dict.fromkeys(COUNTERS, 0)
        self._highest_visit = 0
        # Darts of the session entered by hand, and those of visits entered
        # as their score.
        self._manual = 0
        self._total = 0
        self._hits: Counter[str] = Counter()
        self._completed: list[tuple[str, dict[str, Any]]] = []
        self._active: list[dict[str, Any]] = []
        # Throws since the baseline are announced; throws during a session count.
        self._tracked: list[bool] = []
        self._counting: list[bool] = []
        self._initialized = False
        self._removing = False
        # The current visit has announced its third dart.
        self._full = False
        # The board was out of sight; the next state shows whether the visit went on.
        self._resuming = False
        # The last completed visit, as it was before it was booked, to undo it.
        self._last: dict[str, Any] | None = None

    def restore(self, saved: dict[str, Any] | None) -> None:
        if not isinstance(saved, dict):
            return
        self._committed = {key: _count(saved.get(key)) for key in COUNTERS}
        self._highest_visit = _count(saved.get("highest_visit"))
        self._manual = _count(saved.get("manual_darts"))
        self._total = _count(saved.get("total_darts"))
        hits = saved.get("hits")
        self._hits = Counter(
            {
                key: count
                for key, count in (hits.items() if isinstance(hits, dict) else [])
                if isinstance(key, str) and type(count) is int and count > 0
            }
        )
        if started := _timestamp(saved.get("started")):
            self.started = started
        # Data stored by version 1.0 has no session state: it was always counting.
        for key in ("active", "auto_start"):
            if isinstance(saved.get(key), bool):
                setattr(self, key, saved[key])
        idle = saved.get("idle_minutes")
        if type(idle) is int and 0 <= idle <= IDLE_MINUTES_MAX:
            self.idle_minutes = idle
        self.ended = None if self.active else _timestamp(saved.get("ended"))
        self.last_activity = _timestamp(saved.get("last_activity"))
        history, visits = saved.get("history"), saved.get("recent_visits")
        summaries = map(_restored_summary, history if isinstance(history, list) else [])
        self.history = [summary for summary in summaries if summary][:HISTORY_SIZE]
        restored = map(_restored_visit, visits if isinstance(visits, list) else [])
        self.recent_visits = [visit for visit in restored if visit][:RECENT_VISITS]

    def stored(self) -> dict[str, Any]:
        """Everything that survives a restart, including settings and history.

        The visit on the board counts with its score: after a restart, its
        darts belong to no visit.
        """
        return {
            **self.snapshot(scores=True),
            "auto_start": self.auto_start,
            "idle_minutes": self.idle_minutes,
            "last_activity": self.last_activity,
            "history": [dict(summary) for summary in self.history],
            "recent_visits": [
                {**visit, "segments": list(visit["segments"])}
                for visit in self.recent_visits
            ],
        }

    def _counted(self) -> list[dict[str, Any]]:
        return [
            dart
            for dart, counting in zip(self._active, self._counting, strict=True)
            if counting
        ]

    def _contribution(self, scores: bool = True) -> dict[str, int]:
        """What the counted darts of the active visit add to the totals; the
        score of the visit only once it is complete, if scores is False."""
        darts = self._counted()
        known = beds(darts)
        return {
            "darts": len(darts),
            "points": sum(d["number"] * d["multiplier"] for d in darts),
            "doubles": sum(
                d["multiplier"] == 2 and 1 <= d["number"] <= 20 for d in known
            ),
            "triples": sum(
                d["multiplier"] == 3 and 1 <= d["number"] <= 20 for d in known
            ),
            "bulls": sum(
                d["number"] == 25 and d["multiplier"] in (1, 2) for d in known
            ),
            "misses": sum(hit_key(d) == "MISS" for d in known),
            "visits": int(bool(darts)),
            **_visit_summary(darts if scores else []),
        }

    def _manual_darts(self) -> int:
        return sum(bool(dart.get("manual")) for dart in self._counted())

    def _total_darts(self) -> int:
        return sum(bool(dart.get("total")) for dart in self._counted())

    def _hit_counts(self) -> Counter[str]:
        """The beds the counted darts of the active visit hit, where known."""
        return Counter(map(hit_key, beds(self._counted())))

    def snapshot(self, scores: bool = False) -> dict[str, Any]:
        """The session's totals. A visit counts for the 100+, 140+ and 180
        visits once complete, unless scores: two trebles would be a 100+
        visit until the third makes it a 180."""
        current = self._contribution(scores)
        hits = self._hits + self._hit_counts()
        return {
            "started": self.started,
            "ended": self.ended,
            "active": self.active,
            **{key: self._committed[key] + current[key] for key in COUNTERS},
            "highest_visit": max(self._highest_visit, _visit_high(current)),
            "manual_darts": self._manual + self._manual_darts(),
            "total_darts": self._total + self._total_darts(),
            "hits": dict(sorted(hits.items())),
        }

    def _fold(self) -> None:
        """Add the counted darts of the active visit to the session totals."""
        current = self._contribution()
        for key in COUNTERS:
            self._committed[key] += current[key]
        self._highest_visit = max(self._highest_visit, _visit_high(current))
        self._manual += self._manual_darts()
        self._total += self._total_darts()
        self._hits.update(self._hit_counts())
        self._counting = [False] * len(self._active)

    def visit(self) -> list[dict[str, Any]]:
        """The announced darts of the current visit, in throwing order."""
        return [
            dart
            for dart, tracked in zip(self._active, self._tracked, strict=True)
            if tracked
        ]

    def visit_slots(self) -> list[int]:
        """Where the darts of the current visit are among the darts on the board."""
        return [index for index, tracked in enumerate(self._tracked) if tracked]

    def _commit(self, now: datetime, announce: bool = False) -> None:
        announced = self.visit()
        flags = dart_flags(announced)
        # The bot's visits count nowhere, so the human's visit stays undoable.
        booked = announce and bool(announced) and not flags.get("bot")
        last = self._before_commit() if booked else None
        self._fold()
        if announce and announced:
            visit = _visit_details(announced)
            # Automations that announced the visit with its third dart skip it now.
            self._completed.append(
                ("visit_completed", {**visit, "thrown": self._full, **flags})
            )
            if last is not None:
                self.recent_visits.insert(
                    0,
                    {
                        "time": stamp(now),
                        **visit,
                        **{
                            flag: True
                            for flag in ("manual", "total")
                            if flags.get(flag)
                        },
                    },
                )
                del self.recent_visits[RECENT_VISITS:]
                self._last = last
        self._rest([])

    def _before_commit(self) -> dict[str, Any]:
        """What booking the current visit adds to the session, to take it back."""
        slots = self.visit_slots()
        return {
            "session": self.started,
            "darts": [dict(self._active[slot]) for slot in slots],
            "counting": [self._counting[slot] for slot in slots],
            "contribution": self._contribution(),
            "hits": self._hit_counts(),
            "highest": self._highest_visit,
            "manual": self._manual_darts(),
            "total": self._total_darts(),
            "full": self._full,
        }

    def can_undo(self) -> bool:
        """Whether undo_visit can take the last completed visit back now."""
        last = self._last
        return last is not None and last["session"] == self.started and not self._active

    def undo_visit(self) -> list[dict[str, Any]] | None:
        """Take the last completed visit back as the current visit.

        Its darts leave the session totals, the hits and the recent visits
        again, and come back as the darts of the current visit, so they can
        be corrected and booked anew. Only while no dart is on the board and
        the session that counted them still runs; None otherwise.
        """
        last = self._last
        if last is None or not self.can_undo():
            return None
        for key in COUNTERS:
            self._committed[key] -= last["contribution"][key]
        self._hits -= last["hits"]
        self._highest_visit = last["highest"]
        self._manual -= last["manual"]
        self._total -= last["total"]
        del self.recent_visits[:1]
        darts: list[dict[str, Any]] = last["darts"]
        self._active = [dict(dart) for dart in darts]
        self._tracked = [True] * len(darts)
        self._counting = list(last["counting"])
        self._full = last["full"]
        self._last = None
        return [dict(dart) for dart in darts]

    def _rest(self, observed: list[dict[str, Any]]) -> None:
        """Darts on the board that are neither announced nor counted again."""
        self._active = list(observed)
        self._tracked = [False] * len(observed)
        self._counting = [False] * len(observed)
        self._full = False

    def _withdraw(self, observed: list[dict[str, Any]]) -> None:
        """Drop darts the board no longer reports, keeping the others' flags."""
        remaining = list(zip(self._active, self._tracked, self._counting, strict=True))
        flags = []
        for dart in observed:
            index = next(i for i, (old, _, _) in enumerate(remaining) if old == dart)
            flags.append(remaining.pop(index)[1:])
        self._active = list(observed)
        self._tracked = [tracked for tracked, _ in flags]
        self._counting = [counting for _, counting in flags]

    def baseline(
        self, state: dict[str, Any], now: datetime, announce: bool = False
    ) -> None:
        """Keep accumulated counts; never count darts already present on startup."""
        self._commit(now, announce)
        observed = segments(state)
        self._initialized = observed is not None
        self._rest(observed or [])
        self._removing = False
        self._resuming = False

    def suspend(self) -> None:
        """The board is out of sight for a while; keep the visit in progress.

        The next state continues the visit if the board still shows its darts
        first; otherwise the visit ended meanwhile and is completed.
        """
        self._resuming = self._initialized

    def _start(self, reason: str, now: datetime) -> tuple[str, dict[str, Any]]:
        started = stamp(now)
        self._committed = dict.fromkeys(COUNTERS, 0)
        self._highest_visit = 0
        self._manual = 0
        self._total = 0
        self._hits = Counter()
        self._last = None
        # Darts already on the board belong to no session.
        self._counting = [False] * len(self._active)
        self.started, self.ended, self.active = started, None, True
        self.last_activity = started
        return "session_started", {"started": started, "reason": reason}

    def start(self, now: datetime) -> tuple[str, dict[str, Any]] | None:
        """Start counting from zero, unless a session is already running."""
        return None if self.active else self._start("manual", now)

    def end(
        self, reason: str, now: datetime, at: str | None = None
    ) -> tuple[str, dict[str, Any]] | None:
        """Finish the running session and keep its summary."""
        if not self.active:
            return None
        # Darts still on the board belong to this session, not to the next one.
        self._fold()
        self._last = None
        self.active = False
        self.ended = at or stamp(now)
        summary = _summarize(self.started, self.ended, self.snapshot())
        if summary["darts"]:
            self.history.insert(0, summary)
            del self.history[HISTORY_SIZE:]
        return "session_ended", {**summary, "reason": reason}

    def new_session(self, now: datetime) -> list[tuple[str, dict[str, Any]]]:
        """Finish the running session, if any, and start the next one."""
        ended = self.end("new_session", now)
        return [*([ended] if ended else []), self._start("new_session", now)]

    def observe(
        self, state: dict[str, Any], now: datetime
    ) -> list[tuple[str, dict[str, Any]]]:
        """Return dart events, preceded by a visit that ended with this state.

        The third dart of a visit is followed by visit_thrown, while the darts
        are still in the board; visit_completed follows when they are pulled.
        """
        self._completed = []
        events = self._observe(state, now)
        result = [*self._completed, *events, *self._thrown()]
        if result:
            self.last_activity = stamp(now)
        return result

    def _thrown(self) -> list[tuple[str, dict[str, Any]]]:
        """The visit once its third dart has landed, announced once per visit."""
        announced = self.visit()
        if self._full or len(announced) < 3:
            return []
        self._full = True
        darts = announced[:3]
        return [("visit_thrown", {**_visit_details(darts), **dart_flags(darts)})]

    def _observe(
        self, state: dict[str, Any], now: datetime
    ) -> list[tuple[str, dict[str, Any]]]:
        observed = segments(state)
        if observed is None:
            return []
        status = str(state.get("status", "")).lower()
        if (
            not self._initialized
            or state.get("running") is not True
            or status in LIFECYCLE_STATUSES
        ):
            self.baseline(state, now, announce=self._initialized)
            return []
        if self._resuming:
            self._resuming = False
            if observed[: len(self._active)] != self._active:
                # Darts were pulled or replaced while the board was out of sight.
                self._commit(now, announce=True)
                self._rest(observed)
                self._removing = False
                return []
        if len(observed) < len(self._active):
            if not observed or is_takeout(state):
                # Removing darts preserves their score, unlike a segment correction.
                self._commit(now, announce=True)
                self._rest(observed)
                self._removing = bool(observed)
                return []
            if _contains(self._active, observed):
                # Outside a takeout, fewer known darts mean a withdrawn detection.
                self._withdraw(observed)
                return []
            # New darts without an empty board in between: a missed takeout.
            self._commit(now, announce=True)
            self._removing = False
        if self._removing:
            if len(observed) <= len(self._active):
                self._rest(observed)
                return []
            # Darts beyond the ones still being removed are new throws.
            self._removing = False
        events: list[tuple[str, dict[str, Any]]] = []
        for index, dart in enumerate(observed):
            kind = None
            details: dict[str, Any] = {}
            if index >= len(self._active):
                # The bot's darts are nobody's training, so they start none.
                if not self.active and self.auto_start and not dart.get("bot"):
                    events.append(self._start("first_dart", now))
                self._active.append(dart)
                self._tracked.append(True)
                # The bot's darts never count for the players' training.
                self._counting.append(self.active and not dart.get("bot"))
                kind = "dart_detected"
            elif dart != self._active[index]:
                previous = self._active[index]
                self._active[index] = dart
                kind = "dart_corrected"
                details["previous"] = previous["name"] or hit_key(previous)
            if kind:
                events.append(
                    (
                        kind,
                        {
                            "dart_index": index + 1,
                            # Like the visit's segments, when the board names none.
                            "segment": dart["name"] or hit_key(dart),
                            "score": dart["number"] * dart["multiplier"],
                            **details,
                            **dart_flags([dart]),
                        },
                    )
                )
        return events
