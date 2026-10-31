"""The double of the Board Manager for the unit tests, which answers like the
recordings in tests/fixtures/board_manager, the helpers that set a board up in
Home Assistant, and those the tests of the practice games and of the blueprints
share."""

import itertools
import json
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_STATE_CHANGED, EVENT_STATE_REPORTED
from homeassistant.core import Event, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.homedarts.practice import PracticeGame

# When the unit tests of the games take their steps, which take the time.
NOW = datetime(2026, 10, 1, 20, 0, tzinfo=UTC)
# What Board Manager 1.0.7, 2.0.0, 2.0.2 and 2.1.0 answer, redacted by
# scripts/capture_board.py; the double of the Docker end-to-end test answers like
# them too, and tests/test_board_contract.py holds both doubles to them.
RECORDINGS = Path(__file__).parent / "fixtures" / "board_manager"
# The routes the integration reads, other than /api/system and /api/host of
# Board Manager 2, by the file of their answer.
READINGS = {
    "/api/state/stats": "state-stats.json",
    "/api/cams/stats": "cams-stats.json",
    "/api/cams/state": "cams-state.json",
    "/api/state/motion": "state-motion.json",
}


def recorded(version: str, name: str) -> Any:
    """A fresh copy of a recorded answer: JSON, or the text of version.txt."""
    text = (RECORDINGS / version / name).read_text(encoding="utf-8")
    return text if name.endswith(".txt") else json.loads(text)


BASE = "http://192.0.2.10:3180"
STATE = recorded("1.0.7", "state.json")
CONFIG = recorded("1.0.7", "config.json")
# Board Manager 2.0.0's /api/system, including its secrets, and /api/host, with
# the placeholders of the recording for the names and addresses of the board PC.
SYSTEM = recorded("2.0.0", "system.json")
HOST = recorded("2.0.0", "host.json")


def mock_board(
    mock,
    *,
    state=None,
    config=None,
    config_status=200,
    version=None,
    recording="1.0.7",
    base=BASE,
):
    """A board that answers like the recording, with the answers given instead."""
    mock.get(
        f"{base}/api/state",
        json=recorded(recording, "state.json") if state is None else deepcopy(state),
    )
    mock.get(
        f"{base}/api/config",
        json=recorded(recording, "config.json") if config is None else deepcopy(config),
        status=config_status,
    )
    mock.get(
        f"{base}/api/version",
        text=recorded(recording, "version.txt") if version is None else version,
    )
    for path, name in READINGS.items():
        # A route the board of the recording doesn't have stays without an answer:
        # a read of it fails the test.
        if (RECORDINGS / recording / name).exists():
            mock.get(f"{base}{path}", json=recorded(recording, name))


def local_entry_data(board_id="board-1", host="192.0.2.10"):
    return {"board_id": board_id, "host": host, "port": 3180}


def mock_board_v2(
    mock, *, system=None, state=None, host=None, recording="2.0.0", base=BASE
):
    """A Board Manager 2 board: /api/system instead of upstream routes."""
    mock.get(
        f"{base}/api/system",
        json=recorded(recording, "system.json") if system is None else deepcopy(system),
    )
    mock.get(
        f"{base}/api/host",
        json=recorded(recording, "host.json") if host is None else deepcopy(host),
    )
    mock.put(f"{base}/api/upstream/connect", status=404)
    mock.put(f"{base}/api/upstream/disconnect", status=404)
    mock_board(mock, state=state, recording=recording, base=base)


# A second board in the same home: its own ID, address and two cameras.
SECOND_BASE = "http://192.0.2.20:3180"


def second_board_config():
    config = deepcopy(CONFIG)
    config["auth"]["board_id"] = "board-2"
    config["cam"]["cams"] = ["/dev/video0", "/dev/video2"]
    return config


def board(*hits, **changes):
    """A running board with the given darts of the current visit."""
    return {
        "running": True,
        "connected": True,
        "status": "Throw",
        "event": "Throw",
        "numThrows": len(hits),
        "throws": [
            {"segment": {"name": name, "number": number, "multiplier": multiplier}}
            for name, number, multiplier in hits
        ],
        **changes,
    }


T20 = ("T20", 20, 3)
S20 = ("S20", 20, 1)
BULL = ("Bull", 25, 2)
OUTER_BULL = ("25", 25, 1)
MISS = ("M", 0, 0)


async def setup_local(hass, aioclient_mock, **kwargs):
    """A Board Manager 1 board, set up locally."""
    mock_board(aioclient_mock, **kwargs)
    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    return entry


# Options of an entry with the online bridge switched on.
WEBHOOK_ID = "0123456789abcdef" * 4
WEBHOOK_PATH = f"/api/webhook/{WEBHOOK_ID}"
BRIDGE = {"online_bridge": True, "online_bridge_webhook_id": WEBHOOK_ID}


async def setup_bridge(hass, aioclient_mock, options=None, **kwargs):
    """A Board Manager 1 board whose entry has the options, by default the bridge on."""
    mock_board(aioclient_mock, **kwargs)
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        data=local_entry_data(),
        options=BRIDGE if options is None else options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    return entry


async def setup_v2(hass, aioclient_mock, **kwargs):
    """A Board Manager 2 board, set up locally."""
    mock_board_v2(aioclient_mock, **kwargs)
    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id(hass, platform, key, board_id="board-1"):
    result = er.async_get(hass).async_get_entity_id(
        platform, "homedarts", f"{board_id}_{key}"
    )
    assert result is not None
    return result


# A picture of a board camera, as the board sends it.
JPEG = b"\xff\xd8\xff\xe0 the board with three darts in the treble 20 \xff\xd9"


async def setup_cameras(hass, aioclient_mock, *enabled: int) -> list[str]:
    """A Board Manager 1 board and its three cameras, those with these indexes
    enabled, as on the page of the board."""
    await setup_local(hass, aioclient_mock, state=board())
    cameras = [entity_id(hass, "camera", f"camera_{index}") for index in range(3)]
    registry = er.async_get(hass)
    for index in enabled:
        registry.async_update_entity(cameras[index], disabled_by=None)
    # Home Assistant loads the board again 30 seconds after an entity was enabled.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    assert all(hass.states.get(cameras[index]) for index in enabled)
    return cameras


def camera_picture(aioclient_mock, index: int, content: bytes = JPEG) -> None:
    """The picture the camera with this index sends."""
    aioclient_mock.get(
        f"{BASE}/api/img/cams/{index}",
        content=content,
        headers={"Content-Type": "image/jpeg"},
    )


def state(hass, platform, key, board_id="board-1"):
    return hass.states.get(entity_id(hass, platform, key, board_id)).state


def unique_ids(hass, entry) -> set[str]:
    registry = er.async_get(hass)
    return {
        item.unique_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


def record(hass, coordinator) -> list[tuple[str, dict]]:
    """The events the board announces from now on."""
    events: list[tuple[str, dict]] = []

    @callback
    def receive(kind: str, attributes: dict) -> None:
        events.append((kind, attributes))

    async_dispatcher_connect(hass, coordinator.event_signal, receive)
    return events


async def switch(hass, key: str, on: bool) -> None:
    await hass.services.async_call(
        "switch",
        "turn_on" if on else "turn_off",
        {"entity_id": entity_id(hass, "switch", key)},
        blocking=True,
    )
    await hass.async_block_till_done()


def entity_summary(hass, entry) -> dict[str, str]:
    """By unique ID: entity ID, category, whether it starts disabled, device
    class, unit, state class and translation key, and whether it is named
    after its device."""
    registry = er.async_get(hass)
    return {
        item.unique_id: " | ".join(
            (
                item.entity_id,
                item.entity_category or "-",
                "disabled" if item.disabled_by else "enabled",
                item.original_device_class or "-",
                item.unit_of_measurement or "-",
                (item.capabilities or {}).get("state_class") or "-",
                item.translation_key or "-",
                "named" if item.has_entity_name else "unnamed",
            )
        )
        for item in sorted(
            er.async_entries_for_config_entry(registry, entry.entry_id),
            key=lambda item: item.unique_id,
        )
    }


@contextmanager
def written(hass) -> Iterator[set[str]]:
    """The entities whose state is written meanwhile, changed or reported anew."""
    entities: set[str] = set()

    @callback
    def write(event: Event) -> None:
        entities.add(event.data["entity_id"])

    @callback
    def every(_data) -> bool:
        return True

    unsubscribe = [
        hass.bus.async_listen(kind, write, every)
        for kind in (EVENT_STATE_CHANGED, EVENT_STATE_REPORTED)
    ]
    try:
        yield entities
    finally:
        for remove in unsubscribe:
            remove()


# -- practice games, played without Home Assistant -------------------------------


def dart(name: str) -> dict:
    if name == "BULL":
        return {"number": 25, "multiplier": 2, "name": "Bull"}
    if name == "25":
        return {"number": 25, "multiplier": 1, "name": "25"}
    if name == "MISS":
        return {"number": 0, "multiplier": 0, "name": "M"}
    return {
        "number": int(name[1:]),
        "multiplier": "SDT".index(name[0]) + 1,
        "name": name,
    }


def throw(game: PracticeGame, *names: str) -> list[tuple[str, dict]]:
    """Throw a visit dart by dart and pull the darts; return the events.

    Playing alone, the turn stays with the same player; those events are
    left out here and checked on their own.
    """
    events = []
    for count in range(1, len(names) + 1):
        events += game.track([dart(name) for name in names[:count]], now=NOW)
    events += game.finish_visit(now=NOW)
    game.track([], now=NOW)
    if len(game.players) == 1:
        events = [event for event in events if event[0] != "turn_changed"]
    return events


PLAYER_1 = {"game": 301, "player": 1, "name": None, "players": 1}


def playing(start: int, remaining: int | None = None, **settings) -> PracticeGame:
    game = PracticeGame()
    game.restore({"game": start, "remaining": remaining or start, **settings})
    return game


def match(players: int, legs: int = 1, sets: int = 1, **names) -> PracticeGame:
    game = PracticeGame()
    game.play(301)
    game.set_players(players)
    game.set_format(legs, sets)
    for index, name in names.items():
        game.set_name(int(index[1:]) - 1, name)
    return game


def win_leg(game: PracticeGame, winner: int) -> list[tuple[str, dict]]:
    """The given player (1 to 4) wins the leg; the others miss until then."""
    while game.snapshot()["player"] != winner:
        throw(game, "MISS")
    game.players[winner - 1].remaining = 40
    return throw(game, "D20")


# -- blueprints, run by Home Assistant's automation engine ------------------------

BLUEPRINTS = Path(__file__).parents[1] / "blueprints" / "automation" / "homedarts"
EVENTS = "event.autodarts_board_events"
# Consecutive events always get distinct timestamps, even with a frozen clock.
TICKS = itertools.count(1)


async def automate_all(hass, instances: list[tuple[str, dict]]) -> None:
    configs = [
        {"use_blueprint": {"path": f"homedarts/{name}.yaml", "input": inputs}}
        for name, inputs in instances
    ]
    assert await async_setup_component(hass, "automation", {"automation": configs})
    await hass.async_block_till_done()
    automations = hass.states.async_all("automation")
    assert [state.state for state in automations] == ["on"] * len(configs), automations


async def automate(hass, name: str, inputs: dict) -> None:
    await automate_all(hass, [(name, inputs)])


def fire(hass, event_type: str, **attributes) -> None:
    hass.states.async_set(
        EVENTS,
        (dt_util.utcnow() + timedelta(microseconds=next(TICKS))).isoformat(
            timespec="microseconds"
        ),
        {"event_type": event_type, **attributes},
    )
