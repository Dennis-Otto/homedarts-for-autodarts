"""The recording that the live demo of the website plays (docs/demo/).

The demo shows the cards without Home Assistant: it replays what the integration
did in a few games at a simulated board, as Home Assistant would have sent it to
the cards. The integration plays them here for real, in the Home Assistant of the
tests, on a clock that moves only when the games do, so that every recording is
the same until the integration or the games change.

After each move at the board, the timeline keeps the states of the Autodarts
entities that changed, with the moment of the move, and the answers of the
homedarts/positions command that the training card asks for. `python
scripts/record_demo.py` writes it to docs/demo/timeline.json; the screenshot bot
does so with the images, so that the demo follows the integration.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.json import JSONEncoder
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import (
    async_fire_time_changed_exact,
)

from custom_components.homedarts.bot import Bot
from custom_components.homedarts.const import DOMAIN

from .local_helpers import BASE, board, entity_id, reads_say, setup_local, switch

# Raised when the shape of the file changes in a way docs/demo/demo.js must know.
FORMAT = 1
# The moment the recording starts; the demo moves it to the moment it plays.
START = datetime(2026, 3, 14, 19, 30, tzinfo=UTC)
# The name of the board in the demo, and the ID of its device there.
BOARD_NAME = "Dartboard"
DEVICE = "demo-board"

# The numbers clockwise from the top, to place darts in their beds.
ORDER = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
# The radius of each bed, normalised to the outer edge of the double ring.
RADIUS = {"S": 0.79, "D": 0.976, "T": 0.606}

# How long a player takes, in seconds: a dart, the takeout, and a look at the result.
DART = 1.1
TAKEOUT = 1.8
LOOK = 3.5
# How long the tournament shows the summary of a match, then the pause before the
# next one, in seconds.
SUMMARY = 4
PAUSE = 5

# 501 against the bot: a 140, a 180, an 85 and the 96 checkout.
X01_VISITS = [
    ["T20", "T20", "S20"],
    ["T20", "T20", "T20"],
    ["T20", "S5", "S20"],
    ["T20", "D18"],
]
# Cricket, Alex against Sam: Alex scores on the 20, Sam on the 18, and the outer bull
# closes the last number of Alex, who leads.
CRICKET_VISITS = [
    ["T20", "T20", "T19"],
    ["T18", "S18", "S1"],
    ["T17", "T16", "T15"],
    ["S17", "T18", "S5"],
    ["T18", "Bull", "T20"],
    ["T17", "S16", "S3"],
    ["25"],
]
TOURNAMENT_PLAYERS = ["Alex", "Sam", "Kim", "Robin"]


def dart(name: str, jitter: random.Random) -> dict[str, Any]:
    """A detected dart in the named bed, like T20, S5, D18, 25 or Bull.

    Darts land a little off the middle of their bed, as real ones do, but always in it.
    """
    if name in ("Bull", "25"):
        number, multiplier, radius = 25, 2 if name == "Bull" else 1, 0.02
        if name == "25":
            radius = 0.06
        angle = jitter.uniform(0, 2 * math.pi)
    else:
        number = int(name[1:])
        multiplier = "SDT".index(name[0]) + 1
        radius = RADIUS[name[0]] + jitter.uniform(-0.012, 0.012)
        angle = math.radians(90 - ORDER.index(number) * 18 + jitter.uniform(-6, 6))
    return {
        "segment": {"name": name, "number": number, "multiplier": multiplier},
        "coords": {
            "x": round(radius * math.cos(angle), 3),
            "y": round(radius * math.sin(angle), 3),
        },
    }


def detected(darts: list[dict[str, Any]], **changes: Any) -> dict[str, Any]:
    """The state of a running board with these darts of the current visit."""
    return {**board(), "numThrows": len(darts), "throws": darts, **changes}


def dump(timeline: dict[str, Any]) -> str:
    """The timeline as JSON, with a line for each entity and step, for short diffs."""

    def line(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    head = "".join(
        f"{line(key)}:{line(value)},\n"
        for key, value in timeline.items()
        if key not in ("entities", "steps")
    )
    entities = ",\n".join(
        f"{line(key)}:{line(value)}" for key, value in timeline["entities"].items()
    )
    steps = ",\n".join(line(step) for step in timeline["steps"])
    return f'{{{head}"entities":{{\n{entities}\n}},\n"steps":[\n{steps}\n]}}\n'


def plain(value: Any) -> Any:
    """A value as the frontend receives it over the websocket: JSON."""
    return json.loads(json.dumps(value, cls=JSONEncoder))


class Recorder:
    """The board, the clock and the timeline of one recording."""

    def __init__(
        self, hass: HomeAssistant, freezer: Any, mock: Any, entry: Any
    ) -> None:
        self.hass = hass
        self.freezer = freezer
        self.mock = mock
        self.entry = entry
        self.coordinator = entry.runtime_data.local
        self.jitter = random.Random(7)
        self.steps: list[dict[str, Any]] = []
        self.chapters: list[dict[str, Any]] = []
        self.shown: dict[str, list[Any]] = {}
        self.answers: dict[str, Any] = {}
        self.players: set[str] = set()
        registry = er.async_get(hass)
        self.entities = {
            item.entity_id: {
                "entity_id": item.entity_id,
                "device_id": DEVICE,
                "platform": DOMAIN,
                "translation_key": item.translation_key,
            }
            for item in er.async_entries_for_config_entry(registry, entry.entry_id)
            if item.disabled_by is None and item.translation_key
        }
        devices = dr.async_get(hass)
        (device,) = dr.async_entries_for_config_entry(devices, entry.entry_id)
        self.device = {
            "id": DEVICE,
            "name": BOARD_NAME,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "sw_version": device.sw_version,
        }

    async def wait(self, seconds: float) -> None:
        """Time passes at the board, and with it every timer of the integration."""
        self.freezer.tick(timedelta(seconds=seconds))
        async_fire_time_changed_exact(self.hass)
        await self.hass.async_block_till_done()

    def moment(self) -> int:
        """Milliseconds since the start of the recording."""
        return round((dt_util.utcnow() - START).total_seconds() * 1000)

    async def snap(self) -> None:
        """A step of the timeline with every state and answer that changed."""
        states: dict[str, list[Any] | None] = {}
        for entity in sorted(self.entities):
            state = self.hass.states.get(entity)
            current = (
                None if state is None else [state.state, plain(dict(state.attributes))]
            )
            if self.shown.get(entity) != current:
                states[entity] = current
                if current is None:
                    self.shown.pop(entity, None)
                else:
                    self.shown[entity] = current
        positions = {}
        progress = self.coordinator.games.progress
        for player in ["", *sorted(self.players)]:
            # The answer of homedarts/positions with its aim model, as the aim map
            # of the training card asks for it.
            answer = plain(
                {
                    **progress.positions(player or None),
                    "aim": await self.coordinator.async_aim(player or None),
                }
            )
            if self.answers.get(player) != answer:
                positions[player] = self.answers[player] = answer
        if not states and not positions:
            return
        step: dict[str, Any] = {"at": self.moment(), "states": states}
        if positions:
            step["positions"] = positions
        self.steps.append(step)

    def chapter(self, key: str) -> None:
        """The next step starts the chapter, which the demo offers to jump to."""
        self.chapters.append({"key": key, "step": len(self.steps)})

    async def board(self, state: dict[str, Any], seconds: float) -> None:
        """The board reports a state after the given time, and answers its reads
        with it from then on."""
        await self.wait(seconds)
        reads_say(self.mock, state)
        self.coordinator.async_receive("state", state)
        await self.hass.async_block_till_done()
        await self.snap()

    async def visit(self, names: list[str], pull: bool = True) -> None:
        """A player throws the darts one by one, then pulls them."""
        darts = [dart(name, self.jitter) for name in names]
        for count in range(1, len(darts) + 1):
            await self.board(detected(darts[:count]), DART)
        if pull:
            await self.board(
                detected(darts, status="Takeout in progress", event="Takeout started"),
                LOOK if len(names) < 3 else DART,
            )
            await self.board(detected([], event="Takeout finished"), TAKEOUT)

    async def bot_visit(self) -> None:
        """The bot throws its three darts, each after its delay."""
        for _ in range(3):
            await self.wait(1.05)
            await self.snap()
        await self.wait(0.5)
        await self.snap()

    async def action(self, service: str, seconds: float = LOOK, **data: Any) -> None:
        await self.wait(seconds)
        await self.hass.services.async_call(DOMAIN, service, data, blocking=True)
        await self.hass.async_block_till_done()
        await self.snap()

    async def number(self, key: str, value: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id(self.hass, "number", key), "value": value},
            blocking=True,
        )
        await self.hass.async_block_till_done()

    def timeline(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "start": START.isoformat(),
            "device": self.device,
            "entities": dict(sorted(self.entities.items())),
            "chapters": self.chapters,
            "steps": self.steps,
        }


async def x01_against_the_bot(demo: Recorder) -> None:
    demo.chapter("x01")
    demo.players.add("Alex")
    await demo.number("practice_bot_delay", 1)
    await demo.action("start_game", 1, game="501", players=["Alex"], bot_level=60)
    for index, visit in enumerate(X01_VISITS):
        await demo.visit(visit)
        if index < len(X01_VISITS) - 1:
            await demo.bot_visit()
    await demo.wait(LOOK)
    await demo.snap()


async def cricket(demo: Recorder) -> None:
    demo.chapter("cricket")
    demo.players.add("Sam")
    # The bot sits this one out.
    await demo.number("practice_bot_level", 0)
    await demo.action("start_game", game="cricket", players=["Alex", "Sam"])
    for visit in CRICKET_VISITS:
        await demo.visit(visit)
    await demo.wait(LOOK)
    await demo.snap()


async def tournament(demo: Recorder) -> None:
    demo.chapter("tournament")
    demo.players.update(TOURNAMENT_PLAYERS)
    await demo.action(
        "start_tournament",
        players=TOURNAMENT_PLAYERS,
        format="knockout",
        game="101",
        legs=1,
        sets=1,
        summary=SUMMARY,
        pause=PAUSE,
        third_place=False,
    )
    for _ in range(3):
        await demo.visit(["S1", "S1", "S1"])
        await demo.visit(["T20", "S1", "D20"])
        # The summary, then the pause, which counts down on the scoreboard.
        for _ in range(SUMMARY + PAUSE):
            await demo.wait(1)
            await demo.snap()
    await demo.wait(LOOK)
    await demo.snap()


async def connected(_client: Any) -> AsyncIterator[tuple[str, Any]]:
    """The realtime events of the board: open, with every state from the recording."""
    yield "connected", None
    await asyncio.Future()


async def record(hass: HomeAssistant, aioclient_mock: Any, freezer: Any) -> dict:
    """The whole timeline: a board that gets ready, then the games one by one."""
    freezer.move_to(START)
    # The cameras run, as at a board that detects darts.
    aioclient_mock.get(
        f"{BASE}/api/cams/state", json={"isRunning": True, "isOpened": True}
    )
    with patch(
        "custom_components.homedarts.local_api.AutodartsLocalClient.events", connected
    ):
        entry = await setup_local(hass, aioclient_mock, state=board())
        entry.runtime_data.local.games.bot = Bot(random.Random(1))
        demo = Recorder(hass, freezer, aioclient_mock, entry)
        await switch(hass, "training_session", True)
        demo.chapter("start")
        await demo.snap()
        await x01_against_the_bot(demo)
        await cricket(demo)
        await tournament(demo)
    return demo.timeline()
