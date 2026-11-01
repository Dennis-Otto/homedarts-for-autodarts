"""Weeks of practice for the demo that nobody can throw in a few minutes.

Three made-up players get twelve weeks of practice games, their lifetime
numbers and where their last darts landed, so that the players card shows
badges, trends and groupings, the leaderboard ranks records and the training
card draws each player's darts. The integration's own classes write the data
in the layout it stores; turning the achievements on then unlocks the badges.
"""

from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, "/config")

from custom_components.homedarts.board import aim_point  # noqa: E402
from custom_components.homedarts.profiles import Profile  # noqa: E402
from custom_components.homedarts.progress import (  # noqa: E402
    TREND_WEEKS,
    WEEK_FIELDS,
    PlayerProgress,
)

# The numbers clockwise from the top, and the rings of the Board Manager in mm.
ORDER = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
BULL, OUTER_BULL, TREBLE, DOUBLE = 7, 17, (97, 107), (160, 170)

# name: scatter in mm, bias at the treble 20 (x right, y up), weekly 3-dart
# averages from twelve weeks ago to this week (None: no practice that week),
# lifetime bests and the current and longest streak.
PLAYERS = {
    "Alex": {
        "sigma": 21,
        "bias": (-6, 2),
        "averages": [48, 49, None, 51, 50, 53, 52, 55, 54, 56, 57, 59],
        "fewest": 17,
        "checkout": 121,
        "mpr": 2.9,
        "maximums": 14,
        "streak": (5, 9),
        "around_the_clock": 36,
        "bobs_27": 185,
        "extra": {"cricket_nines": 1, "hat_tricks": 1},
    },
    "Sam": {
        "sigma": 27,
        "bias": (5, -4),
        "averages": [44, None, 45, 43, 46, None, 45, 47, 46, 45, 48, 47],
        "fewest": 23,
        "checkout": 96,
        "mpr": 2.2,
        "maximums": 5,
        "streak": (2, 4),
        "around_the_clock": 44,
        "bobs_27": 88,
        "extra": {"shanghais": 1},
    },
    "Kim": {
        "sigma": 17,
        "bias": (1, -1),
        "averages": [61, 60, 62, 63, None, 61, 64, 62, 63, None, 64, 65],
        "fewest": 14,
        "checkout": 136,
        "mpr": 3.4,
        "maximums": 9,
        "streak": (0, 12),
        "around_the_clock": 29,
        "bobs_27": 322,
        "extra": {},
    },
}


def bed(x: float, y: float) -> str:
    """The bed a position in millimetres lies in, as the integration names it."""
    radius = math.hypot(x, y)
    if radius <= BULL:
        return "BULL"
    if radius <= OUTER_BULL:
        return "25"
    if radius > DOUBLE[1]:
        return "MISS"
    number = ORDER[round(math.degrees(math.atan2(x, y)) / 18) % 20]
    if TREBLE[0] <= radius <= TREBLE[1]:
        return f"T{number}"
    if DOUBLE[0] <= radius:
        return f"D{number}"
    return f"S{number}"


def darts(
    rng: random.Random, settings: dict, count: int
) -> list[tuple[float, float, str]]:
    """Positions in millimetres with the bed each dart was aimed at."""
    thrown = []
    for index in range(count):
        aim = ("T20", "T20", "T20", "T20", "T20", "T20", "D16", "D20", "D8", "BULL")[
            index % 10
        ]
        centre_x, centre_y = aim_point(aim)
        sigma = settings["sigma"] * (0.85 if aim != "T20" else 1)
        bias_x, bias_y = settings["bias"] if aim == "T20" else (0, 0)
        thrown.append(
            (
                centre_x + bias_x + rng.gauss(0, sigma),
                centre_y + bias_y + rng.gauss(0, sigma),
                aim,
            )
        )
    return thrown


def weeks(rng: random.Random, settings: dict, today: date) -> dict[str, list[int]]:
    """The sums of every week with practice, in the stored order."""
    monday = today - timedelta(days=today.weekday())
    result = {}
    for ago, average in zip(
        range(TREND_WEEKS - 1, -1, -1), settings["averages"], strict=True
    ):
        if average is None:
            continue
        legs = rng.randint(6, 12)
        x01_darts = legs * rng.randint(20, 27)
        cricket_darts = rng.choice((0, 0, 30, 45))
        sums = {
            "darts": x01_darts + cricket_darts + rng.randint(20, 90),
            "x01_darts": x01_darts,
            "x01_points": round(average * x01_darts / 3),
            "first9_points": round((average + rng.uniform(4, 10)) * legs * 3),
            "first9_darts": legs * 9,
            "at_double": legs * rng.randint(3, 5),
            "checkouts": legs // 2 + rng.randint(0, 2),
            "cricket_darts": cricket_darts,
            "cricket_marks": round(cricket_darts * settings["mpr"] * 0.8 / 3),
            "legs": legs + (2 if cricket_darts else 0),
            "legs_won": legs // 2,
            "maximums": rng.choice((0, 0, 1, 1, 2)),
            "highest_checkout": rng.randint(40, settings["checkout"]),
            "best_501": rng.randint(settings["fewest"], settings["fewest"] + 9),
            "best_mpr": round(settings["mpr"] * 100 * rng.uniform(0.8, 1))
            if cricket_darts
            else 0,
        }
        sums["double_attempts"] = sums["at_double"] + rng.randint(10, 30)
        sums["double_hits"] = round(sums["double_attempts"] * rng.uniform(0.18, 0.32))
        key = (monday - timedelta(weeks=ago)).isoformat()
        result[key] = [sums[name] for name in WEEK_FIELDS]
    return result


def player(
    name: str, settings: dict, today: date, rng: random.Random
) -> tuple[dict, dict]:
    """A profile and the progress of one player, as the integration stores them."""
    progress = PlayerProgress(name)
    progress.weeks = weeks(rng, settings, today)
    for x, y, aim in darts(rng, settings, 700):
        progress.log.add((x / 170, y / 170), aim)
        progress.hits[bed(x, y)] += 1
    total = {
        name: sum(week[index] for week in progress.weeks.values())
        for index, name in enumerate(WEEK_FIELDS)
    }
    # Older weeks count for the lifetime numbers, too.
    older = 1.6
    counters = progress.counters
    counters["darts"] = round(total["darts"] * older)
    counters["maximums"] = settings["maximums"]
    counters["tons"] = round(total["x01_darts"] * older / 9)
    counters["ton_forties"] = round(total["x01_darts"] * older / 30)
    counters["around_the_clock"] = settings["around_the_clock"]
    counters["bobs_27"] = settings["bobs_27"]
    counters.update(settings["extra"])
    current, longest = settings["streak"]
    progress.streak, progress.best_streak = (current or 1), longest
    progress.last_day = today if current else today - timedelta(days=20)
    doubles = {
        double: [attempts, round(attempts * rate)]
        for double, attempts, rate in (
            ("D20", 60, 0.22),
            ("D16", 48, 0.31),
            ("D8", 30, 0.27),
            ("D10", 18, 0.2),
            ("BULL", 12, 0.17),
        )
    }
    profile = Profile(
        name=name,
        legs_played=round(total["legs"] * older),
        legs_won=round(total["legs_won"] * older),
        matches_played=round(total["legs"] * older / 4),
        matches_won=round(total["legs_won"] * older / 4),
        x01_darts=round(total["x01_darts"] * older),
        x01_points=round(total["x01_points"] * older),
        first9_points=round(total["first9_points"] * older),
        first9_darts=round(total["first9_darts"] * older),
        at_double=round(total["at_double"] * older),
        checkouts=round(total["checkouts"] * older),
        cricket_darts=round(total["cricket_darts"] * older),
        cricket_marks=round(total["cricket_marks"] * older),
        highest_visit=180,
        highest_checkout=settings["checkout"],
        best_mpr=settings["mpr"],
        fewest_darts={"501": settings["fewest"], "301": settings["fewest"] - 5},
        doubles=doubles,
        # The better the average, the higher the rating, around the 1000 of a new player.
        rating=round(800 + 4 * total["x01_points"] / total["x01_darts"] * 3, 1),
        rated_matches=round(total["legs"] * older / 4),
        # Always in the past, so that the games of the demo come first.
        last_played=f"{(today - timedelta(days=1 if current else 20)).isoformat()}T20:00:00+00:00",
    )
    return asdict(profile), progress.stored()


def seed(path: Path, today: date) -> None:
    """Add the players to a stored training, with the achievements still off."""
    stored = json.loads(path.read_text())
    data = stored["data"]
    rng = random.Random(27)
    profiles, progress = [], []
    for name, settings in PLAYERS.items():
        profile, entry = player(name, settings, today, rng)
        profiles.append(profile)
        progress.append(entry)
    practice = data.setdefault("practice", {})
    practice.setdefault("profiles", {})["players"] = profiles
    data["progress"] = {
        "enabled": False,
        "players": progress,
        "session": [],
        "latest": None,
    }
    path.write_text(json.dumps(stored))
