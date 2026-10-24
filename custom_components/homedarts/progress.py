"""Progress of every named player: weekly trends, hits, positions, streaks, badges.

The practice game books each visit for the player at the board. What the
visit and a leg it finished add is read right before and after that booking:
the darts with their positions and aims, and how the lifetime numbers of the
profiles grew. Like the profiles, progress exists for named players only, and
a name is the same player in any upper and lower case.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .achievements import ACHIEVEMENTS, CATALOGUE
from .doubles import DOUBLES
from .positions import DartLog
from .practice import GAMES, Booking, PracticeGame
from .profiles import Profile, Profiles
from .training import beds, hit_key

TREND_WEEKS = 12
PLAYER_DARTS = 1000
SESSION_DARTS = 5000
# Sums of a week, stored as one list in this order. The Cricket MPR of the
# best leg is stored in hundredths; 0 means none for the bests.
WEEK_FIELDS = (
    "darts",
    "x01_darts",
    "x01_points",
    "first9_points",
    "first9_darts",
    "at_double",
    "checkouts",
    "double_attempts",
    "double_hits",
    "cricket_darts",
    "cricket_marks",
    "legs",
    "legs_won",
    "maximums",
    "highest_checkout",
    "best_501",
    "best_mpr",
)
WEEK = {name: index for index, name in enumerate(WEEK_FIELDS)}
BESTS = ("highest_checkout", "best_501", "best_mpr")
# Lifetime numbers of a profile whose growth a week collects, by week field.
PROFILE_FIELDS = {
    "x01_darts": "x01_darts",
    "x01_points": "x01_points",
    "first9_points": "first9_points",
    "first9_darts": "first9_darts",
    "at_double": "at_double",
    "checkouts": "checkouts",
    "cricket_darts": "cricket_darts",
    "cricket_marks": "cricket_marks",
    "legs": "legs_played",
    "legs_won": "legs_won",
}
# The bests among the sums of a week and the counters, where 0 is none: the
# fewest darts, and the highest values besides those of a week.
FEWEST = ("best_501", "around_the_clock")
HIGHEST = ("high_finish", "bobs_27")
COUNTERS = (
    "darts",
    "maximums",
    "tons",
    "ton_forties",
    "hat_tricks",
    "cricket_nines",
    "shanghais",
    "high_finish",
    "around_the_clock",
    "bobs_27",
)


# The sums of a week and the counters that are bests, of which two names of
# one player keep the higher, or the lower where fewer is better; 0 is none.
HIGHER = frozenset(("highest_checkout", "best_mpr", "high_finish", "bobs_27"))
FEWER = frozenset(("best_501", "around_the_clock"))


def _key(name: str) -> str:
    return name.strip().casefold()


def _joined(name: str, mine: int, other: int) -> int:
    """A sum or a counter of two names of one player as one."""
    if name in HIGHER:
        return max(mine, other)
    if name in FEWER:
        return min(mine or other, other or mine)
    return mine + other


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _count(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _day(value: object) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _merged(field: str, mine: int, theirs: int) -> int:
    """A sum of a week or a counter from two boards. A best, where 0 is none,
    is the better one: the fewer darts, else the higher value."""
    if field in FEWEST and mine and theirs:
        return min(mine, theirs)
    if field in (*BESTS, *FEWEST, *HIGHEST):
        return max(mine, theirs)
    return mine + theirs


def _profile_counts(profiles: Profiles) -> dict[str, list[int]]:
    """The lifetime numbers of every profile that weeks collect."""
    counts = {}
    for key, profile in profiles.players.items():
        doubles = profile.doubles.values()
        counts[key] = [
            *(getattr(profile, name) for name in PROFILE_FIELDS.values()),
            sum(count[0] for count in doubles),
            sum(count[1] for count in doubles),
        ]
    return counts


@dataclass
class PlayerProgress:
    """What one player threw, week by week, and the badges it earned."""

    name: str
    hits: Counter[str] = field(default_factory=Counter)
    log: DartLog = field(default_factory=lambda: DartLog(PLAYER_DARTS))
    # Monday of a week -> the sums of WEEK_FIELDS.
    weeks: dict[str, list[int]] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=lambda: dict.fromkeys(COUNTERS, 0))
    streak: int = 0
    best_streak: int = 0
    last_day: date | None = None
    # Achievement -> when each tier was unlocked.
    badges: dict[str, list[str]] = field(default_factory=dict)

    def week(self, day: date) -> list[int]:
        """The sums of the week of this day; weeks beyond the trend are dropped."""
        monday = _monday(day)
        key = monday.isoformat()
        if key not in self.weeks:
            self.weeks[key] = [0] * len(WEEK_FIELDS)
            oldest = (monday - timedelta(weeks=TREND_WEEKS - 1)).isoformat()
            for old in [week for week in self.weeks if week < oldest]:
                del self.weeks[old]
        return self.weeks[key]

    def trained(self, day: date) -> None:
        """A day with darts continues the streak of the day before."""
        if self.last_day == day:
            return
        yesterday = day - timedelta(days=1)
        self.streak = self.streak + 1 if self.last_day == yesterday else 1
        self.best_streak = max(self.best_streak, self.streak)
        self.last_day = day

    def current_streak(self, today: date) -> int:
        alive = self.last_day in (today, today - timedelta(days=1))
        return self.streak if alive else 0

    def trend(self, today: date) -> dict[str, list[Any]]:
        """The last weeks up to this one, oldest first, one list per sum."""
        monday = _monday(today)
        keys = [
            (monday - timedelta(weeks=ago)).isoformat()
            for ago in range(TREND_WEEKS - 1, -1, -1)
        ]
        empty = [0] * len(WEEK_FIELDS)
        rows = [self.weeks.get(key, empty) for key in keys]
        trend: dict[str, list[Any]] = {"weeks": keys}
        for name, index in WEEK.items():
            column: list[Any] = [row[index] for row in rows]
            if name in BESTS:
                column = [value or None for value in column]
            if name == "best_mpr":
                column = [value / 100 if value else None for value in column]
            trend[name] = column
        return trend

    def absorb(self, other: PlayerProgress) -> None:
        """Take over the progress of another name of the same player, as if
        one name had thrown every dart: counts, hits and the sums of every
        week add up, the bests stay, the darts of the one who threw last come
        last, the training days make one streak where they meet, and each tier
        of a badge keeps the date it was first unlocked."""
        self.hits.update(other.hits)
        newer, older = (other, self) if self._threw_before(other) else (self, other)
        newer.log.join(older.log)
        self.log = newer.log
        for week, sums in other.weeks.items():
            kept = self.weeks.setdefault(week, [0] * len(WEEK_FIELDS))
            for name, index in WEEK.items():
                kept[index] = _joined(name, kept[index], sums[index])
        self.weeks = dict(sorted(self.weeks.items())[-TREND_WEEKS:])
        for name, count in other.counters.items():
            self.counters[name] = _joined(name, self.counters[name], count)
        self._join_streaks(newer, older)
        for key, dates in other.badges.items():
            mine = self.badges.get(key, [])
            longer, shorter = sorted((mine, dates), key=len, reverse=True)
            self.badges[key] = [
                min(when, shorter[tier]) if tier < len(shorter) else when
                for tier, when in enumerate(longer)
            ]

    def _threw_before(self, other: PlayerProgress) -> bool:
        """Whether the other player threw on a later day than this one."""
        return other.last_day is not None and (
            self.last_day is None or other.last_day > self.last_day
        )

    def _join_streaks(self, newer: PlayerProgress, older: PlayerProgress) -> None:
        """The streak of the training days of two names of one player, of
        which the newer threw last: the older one's days continue it where
        they reach it."""
        best = max(newer.best_streak, older.best_streak)
        streak = newer.streak
        if newer.last_day is not None and older.last_day is not None:
            start = newer.last_day - timedelta(days=max(newer.streak, 1) - 1)
            if older.last_day >= start - timedelta(days=1):
                begun = older.last_day - timedelta(days=max(older.streak, 1) - 1)
                start = min(start, begun)
            streak = (newer.last_day - start).days + 1
        self.streak, self.last_day = streak, newer.last_day
        self.best_streak = max(best, streak)

    def merge(self, other: PlayerProgress) -> None:
        """Add what the same player threw on another board: the sums of every
        week, the hits and the counters add up, the bests among them and the
        longest streak are the better of both, and each tier of a badge counts
        from the day it was first unlocked. The positions of the other board
        come before those of this one, which stay the newest."""
        self.hits.update(other.hits)
        log = DartLog(PLAYER_DARTS)
        for x, y, aim in (*other.log.darts, *self.log.darts):
            log.add((x, y), aim)
        self.log = log
        for week, theirs in other.weeks.items():
            ours = self.weeks.setdefault(week, [0] * len(WEEK_FIELDS))
            for index, (mine, value) in enumerate(zip(ours, theirs, strict=True)):
                ours[index] = _merged(WEEK_FIELDS[index], mine, value)
        self.weeks = dict(sorted(self.weeks.items())[-TREND_WEEKS:])
        for key, count in other.counters.items():
            self.counters[key] = _merged(key, self.counters[key], count)
        self.best_streak = max(self.best_streak, other.best_streak)
        if other.last_day and (not self.last_day or other.last_day > self.last_day):
            self.streak, self.last_day = other.streak, other.last_day
        for key, theirs_dates in other.badges.items():
            ours_dates = self.badges.get(key, [])
            longer = max(ours_dates, theirs_dates, key=len)
            self.badges[key] = [
                *map(min, ours_dates, theirs_dates),
                *longer[min(len(ours_dates), len(theirs_dates)) :],
            ]

    def stored(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "hits": dict(self.hits),
            "log": self.log.stored(),
            "weeks": {key: list(sums) for key, sums in self.weeks.items()},
            "counters": dict(self.counters),
            "streak": self.streak,
            "best_streak": self.best_streak,
            "last_day": self.last_day.isoformat() if self.last_day else None,
            "badges": {key: list(dates) for key, dates in self.badges.items()},
        }

    @classmethod
    def restored(cls, saved: dict[str, Any]) -> PlayerProgress | None:
        name = saved.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        player = cls(name=name.strip())
        hits = saved.get("hits")
        player.hits = Counter(
            {
                key: count
                for key, count in (hits.items() if isinstance(hits, dict) else [])
                if isinstance(key, str) and type(count) is int and count > 0
            }
        )
        player.log.restore(saved.get("log"))
        weeks = saved.get("weeks")
        valid = {
            key: list(sums)
            for key, sums in (weeks.items() if isinstance(weeks, dict) else [])
            if _day(key) is not None
            and isinstance(sums, list)
            and all(type(value) is int and value >= 0 for value in sums)
        }
        # Weeks of an older layout have fewer sums; the new ones start at zero.
        player.weeks = {
            key: [*sums, *[0] * len(WEEK_FIELDS)][: len(WEEK_FIELDS)]
            for key, sums in sorted(valid.items())[-TREND_WEEKS:]
        }
        counters = saved.get("counters")
        counters = counters if isinstance(counters, dict) else {}
        player.counters = {key: _count(counters.get(key)) for key in COUNTERS}
        player.streak = _count(saved.get("streak"))
        player.best_streak = max(_count(saved.get("best_streak")), player.streak)
        player.last_day = _day(saved.get("last_day"))
        badges = saved.get("badges")
        for key, dates in badges.items() if isinstance(badges, dict) else []:
            if (
                key in ACHIEVEMENTS
                and isinstance(dates, list)
                and all(isinstance(when, str) for when in dates)
            ):
                player.badges[key] = list(dates[: len(ACHIEVEMENTS[key].tiers)])
        return player


@dataclass
class Pending:
    """The moment before the practice game books a visit."""

    booking: Booking
    counts: dict[str, list[int]]
    legs_total: int
    drill: str | None
    result: dict[str, Any] | None


class Progress:
    """Every named player's progress, and the darts of the training session."""

    def __init__(self) -> None:
        # Achievements are unlocked and announced; progress counts regardless.
        self.enabled = True
        self.players: dict[str, PlayerProgress] = {}
        # Positions of the darts of the training session.
        self.session = DartLog(SESSION_DARTS)
        self.latest: dict[str, Any] | None = None

    def _player(self, name: object) -> PlayerProgress | None:
        if not isinstance(name, str) or not name.strip():
            return None
        return self.players.setdefault(_key(name), PlayerProgress(name.strip()))

    # -- booking ---------------------------------------------------------------

    def before(self, practice: PracticeGame) -> Pending:
        """What a visit changes shows against this moment, see after."""
        drill = practice.drill
        results = practice.drills[drill].results if drill else []
        return Pending(
            booking=practice.booking(),
            counts=_profile_counts(practice.profiles),
            legs_total=practice.legs_total,
            drill=drill,
            result=results[0] if results else None,
        )

    def session_visit(self, booking: Booking) -> None:
        """The darts of a completed visit of the training session."""
        for position, aim in zip(booking.positions, booking.aims, strict=True):
            self.session.add(position, aim)

    def session_started(self) -> None:
        self.session.clear()

    def after(
        self, pending: Pending, practice: PracticeGame, now: datetime
    ) -> list[tuple[str, dict[str, Any]]]:
        """Collect what the booked visit added; the achievements it unlocked."""
        today = now.date()
        booking = pending.booking
        if booking.player is not None and (player := self._player(booking.name)):
            self._visit(player, booking, today)
        empty = [0] * (len(PROFILE_FIELDS) + 2)
        for key, counts in _profile_counts(practice.profiles).items():
            grown = [
                now_ - then
                for now_, then in zip(
                    counts, pending.counts.get(key, empty), strict=True
                )
            ]
            if any(grown) and (
                player := self._player(practice.profiles.players[key].name)
            ):
                week = player.week(today)
                for field_, value in zip(
                    (*PROFILE_FIELDS, "double_attempts", "double_hits"),
                    grown,
                    strict=True,
                ):
                    week[WEEK[field_]] += value
        if practice.legs_total > pending.legs_total and practice.legs:
            self._leg(practice.legs[0], today)
        if pending.drill:
            results = practice.drills[pending.drill].results
            if results and results[0] is not pending.result:
                self._result(results[0], practice.names[0])
        if not self.enabled:
            return []
        # The bot's seat keeps the name of whoever sat there before.
        seats = {
            _key(name): index + 1
            for index, name in enumerate(practice.names[: len(practice.players)])
            if name and index != practice.bot_seat
        }
        return self._unlock(practice.profiles, now, seats)

    def _visit(self, player: PlayerProgress, booking: Booking, today: date) -> None:
        darts = booking.darts
        counters = player.counters
        counters["darts"] += len(darts)
        week = player.week(today)
        week[WEEK["darts"]] += len(darts)
        player.hits.update(hit_key(dart) for dart in beds(darts))
        for position, aim in zip(
            booking.booked_positions, booking.booked_aims, strict=True
        ):
            player.log.add(position, aim)
        player.trained(today)
        scored = booking.scored or 0
        counters["tons"] += scored >= 100
        counters["ton_forties"] += scored >= 140
        if scored == 180:
            counters["maximums"] += 1
            week[WEEK["maximums"]] += 1
        if len(beds(darts)) == 3:
            counters["hat_tricks"] += all(
                dart["number"] == 25 and dart["multiplier"] in (1, 2) for dart in darts
            )
            # Nine marks: three trebles on numbers of the Cricket game.
            counters["cricket_nines"] += bool(booking.cricket) and all(
                dart["number"] in booking.cricket and dart["multiplier"] == 3
                for dart in darts
            )
        counters["shanghais"] += booking.shanghai
        counters["high_finish"] = max(counters["high_finish"], booking.checkout or 0)

    def _leg(self, leg: dict[str, Any], today: date) -> None:
        """The bests of the week from the leg that the visit finished."""
        player = self._player(leg.get("name"))
        if player is None:
            return
        week = player.week(today)
        game, darts = leg.get("game"), _count(leg.get("darts"))
        # Like the profile, a team leg sets no fewest darts and no best MPR.
        alone = leg.get("team") is None
        # A leg the round limit decided was not checked out.
        checked_out = leg.get("rounds") is None
        if game in GAMES and leg.get("double_out") is True and checked_out:
            index = WEEK["highest_checkout"]
            week[index] = max(week[index], _count(leg.get("checkout")))
            best = WEEK["best_501"]
            # A handicap leg counts for the score it really started from.
            if leg.get("start", game) == 501 and darts and alone:
                week[best] = min(week[best] or darts, darts)
        mpr = leg.get("mpr")
        if game == "cricket" and isinstance(mpr, int | float) and alone:
            index = WEEK["best_mpr"]
            week[index] = max(week[index], round(mpr * 100))

    def _result(self, result: dict[str, Any], name: str) -> None:
        """The best finished training games of player 1."""
        player = self._player(name)
        if player is None:
            return
        counters = player.counters
        drill, darts = result.get("drill"), _count(result.get("darts"))
        if drill == "around_the_clock" and darts:
            best = counters["around_the_clock"]
            counters["around_the_clock"] = min(best or darts, darts)
        if drill == "bobs_27" and result.get("completed") is True:
            counters["bobs_27"] = max(counters["bobs_27"], _count(result.get("score")))

    # -- achievements ------------------------------------------------------------

    @staticmethod
    def _values(
        player: PlayerProgress, profile: Profile | None
    ) -> dict[str, int | None]:
        """The value that measures every achievement of the player."""
        counters = player.counters
        fewest = profile.fewest_darts.get("501") if profile else None
        doubles = {key for key in player.hits if key in DOUBLES}
        if profile:
            doubles |= {double for double, count in profile.doubles.items() if count[1]}
        best = {key: counters[key] or None for key in ("around_the_clock", "bobs_27")}
        finish = max(
            counters["high_finish"], profile.highest_checkout if profile else 0
        )
        return {
            "maximum": counters["maximums"],
            "ton_plus": counters["tons"],
            "ton_forty": counters["ton_forties"],
            "high_finish": finish or None,
            "short_leg": fewest,
            "nine_darter": fewest,
            "legs_won": profile.legs_won if profile else 0,
            "matches_won": profile.matches_won if profile else 0,
            "hat_trick": counters["hat_tricks"],
            "all_doubles": len(doubles),
            "cricket_nine": counters["cricket_nines"],
            "shanghai": counters["shanghais"],
            **best,
            "streak": player.best_streak,
            "darts_thrown": counters["darts"],
        }

    def _unlock(
        self,
        profiles: Profiles,
        now: datetime,
        seats: dict[str, int] | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Unlock every tier reached; announced unless seats is None."""
        events: list[tuple[str, dict[str, Any]]] = []
        when = now.isoformat()
        for key, player in self.players.items():
            values = self._values(player, profiles.players.get(key))
            for achievement in CATALOGUE:
                reached = achievement.tier(values[achievement.key])
                dates = player.badges.get(achievement.key, [])
                if reached <= len(dates):
                    continue
                player.badges[achievement.key] = [
                    *dates,
                    *[when] * (reached - len(dates)),
                ]
                details = {
                    "name": player.name,
                    "achievement": achievement.key,
                    "tier": reached,
                }
                self.latest = {**details, "date": when}
                if seats is not None:
                    events.append(
                        (
                            "achievement_unlocked",
                            {
                                "player": seats.get(key),
                                **details,
                                "tiers": len(achievement.tiers),
                                "threshold": achievement.tiers[reached - 1],
                            },
                        )
                    )
        return events

    def enable(self, enabled: bool, profiles: Profiles, now: datetime) -> None:
        """Achievements reached while they were off unlock quietly."""
        self.enabled = enabled
        if enabled:
            self._unlock(profiles, now)

    def forget(self, name: str) -> None:
        self.players.pop(_key(name), None)
        if self.latest and _key(self.latest["name"]) == _key(name):
            self.latest = None

    def rename(
        self, name: str, new_name: str, profiles: Profiles, now: datetime
    ) -> None:
        """A player's progress under a new name, after the profiles renamed
        the player; the progress of a name that has some already takes it
        over, see PlayerProgress.absorb, and the tiers that the two reach
        together unlock quietly."""
        old, new = _key(name), _key(new_name)
        keys = (old, new)
        if self.latest and _key(self.latest["name"]) in keys:
            self.latest = {**self.latest, "name": new_name}
        player = self.players.pop(old, None)
        target = self.players.get(new)
        if target is None:
            if player is None:
                return
            target = self.players[new] = player
        elif player is not None:
            target.absorb(player)
            if self.enabled:
                self._unlock(profiles, now)
        target.name = new_name

    # -- undo ------------------------------------------------------------------

    def checkpoint(self, names: Iterable[str]) -> dict[str, Any]:
        """The progress of these players and of the session, before a visit
        is booked; a visit books for the players at the board only."""
        keys = {_key(name) for name in names if name and name.strip()}
        return {
            "players": {key: copy.deepcopy(self.players.get(key)) for key in keys},
            "session": copy.deepcopy(self.session),
            "latest": copy.deepcopy(self.latest),
        }

    def rewind(self, checkpoint: dict[str, Any]) -> None:
        """Back to a checkpoint, as when the visits since were never booked."""
        for key, player in checkpoint["players"].items():
            if player is None:
                self.players.pop(key, None)
            else:
                self.players[key] = player
        self.session = checkpoint["session"]
        self.latest = checkpoint["latest"]

    # -- storage ---------------------------------------------------------------

    def merge(self, other: Progress, profiles: Profiles, now: datetime) -> None:
        """Take over the progress of the players of another board, after the
        profiles took over theirs; the badges that the numbers of both boards
        reach together unlock quietly."""
        for key, theirs in other.players.items():
            if key in self.players:
                self.players[key].merge(theirs)
            else:
                self.players[key] = theirs
        if self.enabled:
            self._unlock(profiles, now)

    def stored(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "players": [player.stored() for player in self.players.values()],
            "session": self.session.stored(),
            "latest": dict(self.latest) if self.latest else None,
        }

    def restore(self, saved: object, profiles: Profiles, now: datetime) -> None:
        """Restore, or start from what the profiles already prove.

        Without stored progress, as after an update, every profile gets its
        darts so far, and the achievements they reach unlock quietly.
        """
        if not isinstance(saved, dict) or not isinstance(saved.get("players"), list):
            for key, profile in profiles.players.items():
                player = self.players.setdefault(key, PlayerProgress(profile.name))
                player.counters["darts"] = profile.x01_darts + profile.cricket_darts
            if self.enabled:
                self._unlock(profiles, now)
            return
        self.enabled = saved.get("enabled") is not False
        for entry in saved["players"]:
            if isinstance(entry, dict) and (restored := PlayerProgress.restored(entry)):
                self.players[_key(restored.name)] = restored
        self.session.restore(saved.get("session"))
        latest = saved.get("latest")
        if (
            isinstance(latest, dict)
            and isinstance(latest.get("name"), str)
            and isinstance(latest.get("achievement"), str)
            and latest["achievement"] in ACHIEVEMENTS
            and type(latest.get("tier")) is int
            and isinstance(latest.get("date"), str)
        ):
            self.latest = {
                key: latest[key] for key in ("name", "achievement", "tier", "date")
            }

    # -- state -----------------------------------------------------------------

    def summary(self, name: str, today: date) -> dict[str, Any]:
        """Trend, hits, grouping and streak of a player for the profile list."""
        player = self.players.get(_key(name))
        if player is None:
            return {}
        # The best aim of the newest aim model, which the coordinator works out
        # off the event loop after a visit.
        best = player.log.best_aim()
        return {
            "darts_thrown": player.counters["darts"],
            "maximums": player.counters["maximums"],
            "streak": player.current_streak(today),
            "best_streak": player.best_streak,
            "hits": dict(sorted(player.hits.items())),
            "spread": player.log.spread(),
            "best_aim": best["bed"] if best else None,
            "expected_ppd": round(best["expected"], 1) if best else None,
            "trend": player.trend(today),
        }

    def achievements(self, profiles: Profiles) -> dict[str, Any]:
        """Every player's badges and how far each achievement has come."""
        players: list[dict[str, Any]] = []
        for key, player in sorted(
            self.players.items(), key=lambda item: item[1].name.casefold()
        ):
            values = self._values(player, profiles.players.get(key))
            badges: dict[str, dict[str, Any]] = {
                achievement: {"tier": len(dates), "dates": list(dates)}
                for achievement, dates in player.badges.items()
                if dates
            }
            players.append(
                {
                    "name": player.name,
                    "unlocked": sum(badge["tier"] for badge in badges.values()),
                    "badges": badges,
                    "progress": values,
                }
            )
        return {
            "latest": dict(self.latest) if self.latest else None,
            "catalogue": [achievement.described() for achievement in CATALOGUE],
            "players": players,
        }

    def log(self, name: str | None = None) -> DartLog:
        """The logged darts of a player, or of the session without a name."""
        if not name or not name.strip():
            return self.session
        player = self.players.get(_key(name))
        return player.log if player else DartLog(0)

    def stale_aims(self) -> list[DartLog]:
        """The players' logs with darts that their aim model does not know yet."""
        return [player.log for player in self.players.values() if player.log.aim_stale]

    def positions(self, name: str | None = None) -> dict[str, Any]:
        """The logged positions and their grouping, of a player or the session."""
        if not name or not name.strip():
            return {
                "player": None,
                "known": True,
                "positions": self.session.positions(),
                "spread": self.session.spread(),
            }
        player = self.players.get(_key(name))
        log = player.log if player else DartLog(0)
        return {
            "player": player.name if player else name.strip(),
            "known": player is not None,
            "positions": log.positions(),
            "spread": log.spread(),
        }
