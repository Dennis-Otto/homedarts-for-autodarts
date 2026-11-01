"""Prepare the demo instance: a configured board, a dashboard and a visit in progress.

Runs inside the Home Assistant container like scenario.py and reuses its API helpers.
The resulting instance is used for previews and documentation screenshots.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
from board_mock import GENERATION, PORT
from demo_progress import seed
from pictures import avatar, board_photo
from scenario import HA, Scenario, wait_for

DASHBOARD = "homedarts-demo"
STRATEGY_DASHBOARD = "homedarts-auto"

# The frozen clock of the screenshots (compose.frozen.yaml), which stands still at
# DEMO_TIME in this container; without DEMO_TIME the demo runs on the real clock.
_SPEC = importlib.util.spec_from_file_location(
    "demo_clock", Path(__file__).resolve().parent / "frozen" / "sitecustomize.py"
)
demo_clock = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(demo_clock)
FROZEN = bool(os.environ.get("DEMO_TIME") and os.environ.get("DEMO_CLOCK"))


def tick() -> None:
    """A move at the board takes two seconds on the frozen clock, as at a real board."""
    if FROZEN:
        demo_clock.move(os.environ["DEMO_CLOCK"], time.time() + demo_clock.STEP)


def dart(name: str, number: int, multiplier: int, bed: str, x: float, y: float):
    return {
        "segment": {
            "name": name,
            "number": number,
            "multiplier": multiplier,
            "bed": bed,
        },
        "coords": {"x": x, "y": y},
    }


T20 = dart("T20", 20, 3, "Triple", 0.035, 0.608)
T20_LEFT = dart("T20", 20, 3, "Triple", -0.041, 0.604)
S20 = dart("S20", 20, 1, "SingleOuter", 0.02, 0.8)
S1 = dart("S1", 1, 1, "SingleOuter", 0.2, 0.74)
S5 = dart("S5", 5, 1, "SingleOuter", -0.24, 0.76)
T19 = dart("T19", 19, 3, "Triple", -0.19, -0.575)
D16 = dart("D16", 16, 2, "Double", -0.58, -0.8)
BULL = dart("Bull", 25, 2, "Double", 0.012, -0.02)
OUTER_BULL = dart("25", 25, 1, "Single", -0.06, 0.07)

# Completed visits give the session statistics realistic values.
HISTORY = [
    [T20, S20, S1],
    [T20, T20_LEFT, S5],
    [S20, OUTER_BULL, T19],
    [T20, S20, D16],
    [BULL, S20, S20],
]
CURRENT = [T20, S5, BULL]
# Earlier, finished sessions for the training card's list of past sessions.
EARLIER = [
    [[T20, T20_LEFT, S20], [S20, S1, S5]],
    [[T19, S20, S20], [BULL, OUTER_BULL, S20], [T20, S5, S1]],
]

CARDS = {
    "board": [{"type": "custom:homedarts-card", "grid_options": {"columns": "full"}}],
    "training": [
        {"type": "custom:homedarts-training-card", "grid_options": {"columns": "full"}}
    ],
    "status": [
        {"type": "custom:homedarts-status-card", "grid_options": {"columns": "full"}}
    ],
    "scoreboard": [{"type": "custom:homedarts-scoreboard-card", "caller": True}],
    "players": [{"type": "custom:homedarts-players-card", "export": True}],
    "doubles": [{"type": "custom:homedarts-doubles-card"}],
    "leaderboard": [{"type": "custom:homedarts-leaderboard-card"}],
    # The players card with badges, trends and groupings, and one player's darts.
    "progress": [
        {
            "type": "custom:homedarts-players-card",
            "show_head_to_head": False,
            "show_matches": False,
            "show_locked": False,
        }
    ],
    "positions": [
        {
            "type": "custom:homedarts-training-card",
            "mode": "positions",
            "player": "Alex",
            "show_bests": False,
            "show_history": False,
            "show_sessions": False,
            "show_reset": False,
        }
    ],
    "styles": [
        {
            "type": "custom:homedarts-card",
            "board_style": "flat",
            "layout": "vertical",
        },
        {"type": "custom:homedarts-card", "layout": "board", "title": "Board"},
    ],
}


# Synthetic people: Alex and Sam are at home, Kim is out.
PEOPLE = [
    ("Alex", (0, 150, 199), "home"),
    ("Sam", (156, 39, 176), "home"),
    ("Kim", (239, 108, 0), "not_home"),
]
# Highlight photos named as the highlight photo blueprint saves them.
GALLERY = Path("/media/homedarts/highlights")
HIGHLIGHTS = {
    "2026-09-26_21-05-33_Alex_180.jpg": ["T20", "T20", "T20"],
    "2026-09-26_21-19-02_Sam_checkout-121.jpg": ["T20", "T11", "D14"],
    "2026-09-12_20-44-10_Kim_140.jpg": ["T20", "T20", "S20"],
    "2026-08-29_19-30-00_Alex_checkout-170.jpg": ["T20", "T20", "BULL"],
    "2026-08-15_18-02-45_Sam_180.jpg": ["T20", "T20", "T20"],
}


def dashboard() -> dict:
    wide = {
        "board": 2,
        "training": 2,
        "status": 2,
        "scoreboard": 2,
        "players": 2,
        "doubles": 2,
        "leaderboard": 2,
        "progress": 2,
        "positions": 2,
        "styles": 1,
    }
    return {
        "title": "HomeDarts",
        "views": [
            *(
                {
                    "title": name.title(),
                    "path": name,
                    "type": "sections",
                    "max_columns": 2,
                    "sections": [
                        {"type": "grid", "column_span": wide[name], "cards": [card]}
                        for card in cards
                    ],
                }
                for name, cards in CARDS.items()
            ),
            # The live card and the scoreboard side by side, for the animation at
            # the top of the README.
            {
                "title": "Hero",
                "path": "hero",
                "type": "sections",
                "max_columns": 3,
                "sections": [
                    {
                        "type": "grid",
                        "column_span": 1,
                        "cards": [{"type": "custom:homedarts-card", "layout": "board"}],
                    },
                    {
                        "type": "grid",
                        "column_span": 2,
                        "cards": [{"type": "custom:homedarts-scoreboard-card"}],
                    },
                ],
            },
            # The scoreboard on a screen at the board, idle after a short time.
            {
                "title": "Idle",
                "path": "idle",
                "panel": True,
                "cards": [
                    {
                        "type": "custom:homedarts-scoreboard-card",
                        "full_height": True,
                        "idle_after": 10,
                        "idle_interval": 60,
                    }
                ],
            },
            # The screen with the keypad for darts entered by hand.
            {
                "title": "Keypad",
                "path": "keypad",
                "panel": True,
                "cards": [
                    {
                        "type": "custom:homedarts-scoreboard-card",
                        "full_height": True,
                        "idle": False,
                        "keypad": True,
                    }
                ],
            },
            # A tournament on that screen.
            {
                "title": "Tournament",
                "path": "tournament",
                "panel": True,
                "cards": [
                    {
                        "type": "custom:homedarts-scoreboard-card",
                        "full_height": True,
                        "idle": False,
                    }
                ],
            },
        ],
    }


# A week of the training calendar before the demo day: (days ago, start, minutes,
# darts, points) of sessions, and (days ago, start, minutes, game, players,
# winner) of matches with every player's legs won and result.
WEEK_SESSIONS = [
    (6, "18:40", 45, 312, 5642),
    (5, "19:05", 35, 240, 4010),
    (3, "18:15", 50, 366, 6468),
    (2, "20:10", 25, 180, 3150),
    (1, "19:30", 60, 420, 8134),
]
WEEK_MATCHES = [
    (
        6,
        "19:40",
        32,
        501,
        [("Alex", 3, {"average": 62.4}), ("Sam", 2, {"average": 55.1})],
        1,
    ),
    (
        4,
        "20:00",
        21,
        "cricket",
        [("Alex", 1, {"mpr": 2.4}), ("Kim", 2, {"mpr": 2.7})],
        2,
    ),
    (
        3,
        "19:20",
        28,
        501,
        [("Sam", 3, {"average": 58.9}), ("Kim", 1, {"average": 49.3})],
        1,
    ),
    (
        2,
        "20:40",
        14,
        "killer",
        [
            ("Alex", 0, {"points": 1}),
            ("Sam", 0, {"points": 0}),
            ("Kim", 1, {"points": 3}),
        ],
        3,
    ),
]


def week_journal(now: datetime) -> dict:
    """The stored training journal of the week before the demo day."""

    def moment(days: int, start: str, minutes: int = 0) -> datetime:
        hour, minute = map(int, start.split(":"))
        day = (now - timedelta(days=days)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return day + timedelta(minutes=minutes)

    sessions = [
        {
            "started": moment(days, start).isoformat(),
            "ended": moment(days, start, minutes).isoformat(),
            "darts": darts,
            "points": points,
            "visits": darts // 3,
            "highest_visit": 140 if darts > 300 else 121,
            "scores_100": darts // 30,
            "scores_140": darts // 120,
            "scores_180": int(darts > 400),
        }
        for days, start, minutes, darts, points in WEEK_SESSIONS
    ]
    matches = [
        {
            "started": moment(days, start).isoformat(),
            "ended": moment(days, start, minutes).isoformat(),
            "game": game,
            "legs_to_win": {501: 3, "cricket": 2}.get(game, 1),
            "sets_to_win": 1,
            "winner": winner,
            # One set each: the legs of the set are the legs of the match.
            "players": [
                {"name": name, "legs": legs, "match_legs": legs, **result}
                for name, legs, result in players
            ],
        }
        for days, start, minutes, game, players, winner in WEEK_MATCHES
    ]
    return {
        "sessions": sorted(sessions, key=lambda entry: entry["ended"]),
        "matches": sorted(matches, key=lambda entry: entry["ended"]),
        "match_start": None,
    }


async def seed_journal(demo: Scenario, entry_id: str) -> None:
    """Give the training calendar a week, written while the entry is unloaded."""

    async def state(expected: str):
        entries = await demo.api(
            "GET", "/api/config/config_entries/entry?domain=homedarts"
        )
        return entries[0]["state"] == expected or None

    await demo.ws("config_entries/disable", entry_id=entry_id, disabled_by="user")
    await wait_for(lambda: state("not_loaded"), "the unloaded entry")
    key = f"homedarts.{entry_id}.journal"
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    journal = {"version": 1, "minor_version": 1, "key": key, "data": week_journal(now)}
    await asyncio.to_thread(
        Path(f"/config/.storage/{key}").write_text, json.dumps(journal)
    )
    await demo.ws("config_entries/disable", entry_id=entry_id, disabled_by=None)
    await wait_for(lambda: state("loaded"), "the entry with a week in its calendar")


# Four weeks of long-term statistics before the demo day, as the recorder compiles
# them, for the graphs of the generated dashboard: (days ago, darts, 3-dart
# average, first 9 average, checkout rate, doubles rate, practice legs) of every
# training day. The last week matches the sessions of the training calendar.
STATISTICS = [
    (27, 210, 46.8, 51.2, 18.5, 24.0, 2),
    (26, 285, 47.9, 52.0, 20.1, 25.2, 3),
    (24, 168, 45.6, 50.4, 19.0, 24.8, 1),
    (23, 330, 48.7, 53.1, 21.4, 26.3, 4),
    (21, 246, 48.1, 52.6, 22.0, 26.9, 2),
    (20, 372, 49.6, 54.0, 23.5, 27.8, 5),
    (19, 198, 48.9, 53.4, 22.8, 27.1, 1),
    (17, 306, 50.2, 54.9, 24.6, 28.5, 3),
    (16, 264, 49.8, 54.2, 25.1, 29.0, 2),
    (14, 420, 51.4, 55.8, 26.3, 29.8, 6),
    (13, 180, 50.6, 55.1, 25.7, 29.4, 1),
    (12, 348, 51.9, 56.3, 27.0, 30.6, 4),
    (10, 294, 52.3, 56.9, 27.8, 31.2, 3),
    (9, 222, 51.7, 56.0, 27.2, 30.8, 2),
    (8, 390, 53.0, 57.6, 28.9, 32.1, 5),
    (6, 312, 54.2, 58.4, 29.6, 32.8, 3),
    (5, 240, 50.1, 55.3, 28.4, 31.9, 2),
    (3, 366, 53.0, 57.9, 30.2, 33.4, 4),
    (2, 180, 52.5, 57.1, 29.8, 33.0, 1),
    (1, 420, 58.1, 61.7, 31.2, 34.6, 5),
]
SUMS = ("training_darts", "practice_legs_played")
MEANS = (
    "training_average",
    "practice_first_9_average",
    "practice_checkout_rate",
    "practice_doubles_rate",
)


async def seed_statistics(demo: Scenario) -> None:
    """Long-term statistics of four weeks, so the graphs never say "No statistics found".

    The recorder continues a total from its own five-minute statistics, which start
    at zero. So the imported totals end at zero yesterday, and a row long before
    the first day holds where they start: every day keeps its change, and today
    continues without a jump when the recorder compiles the next hour.
    """
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    rows: dict[str, list[dict]] = {key: [] for key in (*SUMS, *MEANS)}
    totals = {
        "training_darts": -sum(day[1] for day in STATISTICS),
        "practice_legs_played": -sum(day[-1] for day in STATISTICS),
    }
    start = (now - timedelta(days=40)).replace(minute=0, second=0, microsecond=0)
    for key, total in totals.items():
        rows[key].append({"start": start.isoformat(), "state": 0, "sum": total})
    for days, darts, *values, legs in STATISTICS:
        # One hour of the evening holds the day, as if the session ended then.
        start = (now - timedelta(days=days)).replace(
            hour=19, minute=0, second=0, microsecond=0
        )
        for key, value in zip(SUMS, (darts, legs), strict=True):
            totals[key] += value
            rows[key].append(
                {"start": start.isoformat(), "state": value, "sum": totals[key]}
            )
        for key, value in zip(MEANS, values, strict=True):
            rows[key].append(
                {"start": start.isoformat(), "mean": value, "min": value, "max": value}
            )
    for key, stats in rows.items():
        entity = demo.entity(key)
        state = await demo.api("GET", f"/api/states/{entity}")
        await demo.ws(
            "recorder/import_statistics",
            metadata={
                "has_sum": key in SUMS,
                # 0: no mean, 1: an arithmetic mean.
                "mean_type": 0 if key in SUMS else 1,
                "name": None,
                "source": "recorder",
                "statistic_id": entity,
                "unit_class": None,
                "unit_of_measurement": state["attributes"].get("unit_of_measurement"),
            },
            stats=stats,
        )


# The weekly report blueprint of the repository; in German with the message of
# the documentation.
GERMAN_REPORT = {
    "report_title": "Deine Dartwoche",
    "report_message": (
        "{{ darts }} Darts"
        "{{ ' in ' ~ training_minutes ~ ' Minuten' if training_minutes else '' }}"
        "{{ ', 3-Dart-Average ' ~ (average | replace('.', ','))"
        " ~ (' (' ~ ('+' if average_change > 0 else '')"
        " ~ (average_change | replace('.', ',')) ~ ')'"
        " if average_change is not none else '')"
        " if average is not none else '' }}"
        "{{ ', ' ~ scores_180 ~ ' × 180' if scores_180 else '' }}"
        "{{ ', ' ~ streak ~ (' Tag' if streak == 1 else ' Tage') ~ ' in Folge'"
        " if streak else '' }}."
    ),
}


async def weekly_report(demo: Scenario) -> None:
    """An automation from the weekly report blueprint, as a user would create it."""
    inputs = {"board_events": demo.entity("board_events")}
    if os.environ.get("DEMO_LANGUAGE") == "de":
        inputs |= GERMAN_REPORT
    automation = {
        "id": "homedarts_weekly_report",
        "alias": "Weekly darts report",
        "use_blueprint": {"path": "Dennis-Otto/weekly_report.yaml", "input": inputs},
    }
    folder = Path("/config/automations")
    await asyncio.to_thread(folder.mkdir, exist_ok=True)
    # JSON is YAML, too.
    await asyncio.to_thread(
        (folder / "weekly_report.yaml").write_text, json.dumps([automation])
    )
    await demo.api("POST", "/api/services/automation/reload", json={})

    async def loaded():
        states = await demo.api("GET", "/api/states")
        return (
            any(
                state["entity_id"].startswith("automation.") and state["state"] == "on"
                for state in states
            )
            or None
        )

    await wait_for(loaded, "the weekly report automation")


async def people(demo: Scenario) -> None:
    """Persons with pictures, linked to the players of the demo."""
    for name, color, where in PEOPLE:
        form = aiohttp.FormData()
        form.add_field(
            "file",
            avatar(name[0], color),
            filename=f"{name.lower()}.png",
            content_type="image/png",
        )
        async with demo.session.post(
            f"{HA}/api/image/upload", data=form, headers=demo.headers
        ) as response:
            image = await response.json()
        picture = f"/api/image/serve/{image['id']}/512x512"
        person = await demo.ws("person/create", name=name, picture=picture)
        entity = f"person.{name.lower()}"
        # Without device trackers, the demo tells who is home itself.
        await demo.api(
            "POST",
            f"/api/states/{entity}",
            json={
                "state": where,
                "attributes": {
                    "friendly_name": name,
                    "entity_picture": picture,
                    "id": person["id"],
                },
            },
        )
        await demo.api(
            "POST",
            "/api/services/homedarts/link_player",
            json={"player": name, "person": entity},
        )


def gallery() -> None:
    """Highlight photos for the media browser."""
    GALLERY.mkdir(parents=True, exist_ok=True)
    for name, darts in HIGHLIGHTS.items():
        (GALLERY / name).write_bytes(board_photo(darts))


async def throw(demo: Scenario, darts: list[dict]) -> None:
    for count in range(1, len(darts) + 1):
        tick()
        await demo.board("POST", "/control/state", json={"throws": darts[:count]})
        await asyncio.sleep(0.4)


async def play(demo: Scenario, visits: list[list[dict]]) -> None:
    """Throw each visit and pull the darts, as a player does."""
    for visit in visits:
        await throw(demo, visit)
        tick()
        await demo.board(
            "POST",
            "/control/state",
            json={"status": "Takeout in progress", "event": "Takeout started"},
        )
        tick()
        await demo.board(
            "POST",
            "/control/state",
            json={"status": "Throw", "event": "Takeout finished", "throws": []},
        )
        await asyncio.sleep(0.4)


async def history(demo: Scenario, entry_id: str) -> None:
    """Weeks of practice of three players, written while the entry is disabled."""
    await demo.ws("config_entries/disable", entry_id=entry_id, disabled_by="user")
    await wait_for(lambda: demo.entry_is("not_loaded"), "the disabled entry")
    seed(
        Path(f"/config/.storage/homedarts.{entry_id}.training"),
        datetime.now().astimezone().date(),
    )
    await demo.ws("config_entries/disable", entry_id=entry_id, disabled_by=None)
    await wait_for(lambda: demo.entry_is("loaded"), "the enabled entry")
    # The badges the weeks earned unlock quietly.
    await demo.service("switch", "turn_on", "achievements_enabled")
    await demo.expect_states({"achievements_enabled": "on"})


async def main() -> None:
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        demo = Scenario(session)
        await demo.onboard()
        await demo.connect()
        if GENERATION >= 2:
            result = await demo.discovered_setup()
        else:
            result = await demo.local_flow("board-mock", PORT)
        entry_id = result["result"]["entry_id"]
        await demo.registries(entry_id)
        if FROZEN:
            # Every change comes over the board socket, in the order the board sends
            # it, never first from a poll whose moment depends on the run.
            await demo.ws(
                "config_entries/update", entry_id=entry_id, pref_disable_polling=True
            )
            await wait_for(lambda: demo.entry_is("loaded"), "the entry without polling")
        await seed_journal(demo, entry_id)
        await seed_statistics(demo)
        await weekly_report(demo)
        await history(demo, entry_id)
        # A daily goal the demo darts reach halfway, for the training card.
        await demo.service("number", "set_value", "training_daily_goal", value=120)
        await demo.service("button", "press", "start")
        await demo.expect_states({"detection": "on", "realtime_connected": "on"})
        for session in EARLIER:
            await play(demo, session)
            await demo.service("switch", "turn_off", "training_session")
            await demo.expect_states({"training_session": "off"})
        await demo.service("switch", "turn_on", "training_session")
        await demo.expect_states({"training_session": "on", "training_darts": "0"})
        await play(demo, HISTORY)
        await throw(demo, CURRENT)
        await demo.expect_states({"local_visit_score": "115"})

        await demo.ws(
            "lovelace/dashboards/create",
            url_path=DASHBOARD,
            title="HomeDarts",
            icon="mdi:bullseye-arrow",
            show_in_sidebar=True,
            require_admin=False,
            mode="storage",
        )
        await demo.ws("lovelace/config/save", url_path=DASHBOARD, config=dashboard())
        await people(demo)
        gallery()
        # A second dashboard generated entirely by the HomeDarts strategy.
        await demo.ws(
            "lovelace/dashboards/create",
            url_path=STRATEGY_DASHBOARD,
            title="HomeDarts (automatic)",
            icon="mdi:bullseye",
            show_in_sidebar=True,
            require_admin=False,
            mode="storage",
        )
        await demo.ws(
            "lovelace/config/save",
            url_path=STRATEGY_DASHBOARD,
            config={"strategy": {"type": "custom:homedarts"}},
        )
        await demo.socket.close()


if __name__ == "__main__":
    asyncio.run(main())
