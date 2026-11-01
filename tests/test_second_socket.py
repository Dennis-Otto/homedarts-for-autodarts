"""The second socket of Board Manager 2.1, /api/events/system.

tests/fixtures/board_manager/2.1.0/ws-system-frames.jsonl holds what it sent on a real
board while its detection started and stopped. Nobody stood at that board, so its
frames show no hand: the tests set the flags of a recorded frame, as a takeout of
another real board set them (issue 521): isHand with takeoutStarted, then
isTakeoutPartial and isTakeoutFull, and isHand off with takeoutFinished.
"""

import asyncio
import json
import logging
import time
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.homedarts.errors import AutodartsConnectionError
from custom_components.homedarts.local_api import (
    EVENTS,
    SYSTEM_EVENTS,
    AutodartsLocalAuthError,
    AutodartsLocalClient,
    board_state,
    motion_flags,
    quick_motion_flags,
)
from custom_components.homedarts.local_coordinator import (
    MOTION_SILENCE_SECONDS,
    AutodartsLocalCoordinator,
)

from .local_helpers import (
    BASE,
    RECORDINGS,
    entity_id,
    recorded,
    setup_local,
    setup_v2,
    state,
)
from .test_board_manager_2_1 import (
    LEFT_OVER,
    THROWN,
    answer,
    empty_takeout,
    fired_kinds,
    frames,
    motion_2_1,
    reads_of,
    reread,
    resets,
    running_2_1,
)
from .test_realtime import REAL_EVENTS, Socket, entity_events
from .test_stuck_takeout import pass_time

SECOND_SOCKET = RECORDINGS / "2.1.0" / "ws-system-frames.jsonl"
STOPPED = {"connected": True, "event": "stopped", "running": False, "status": "stopped"}


def recorded_frames() -> list[dict]:
    lines = SECOND_SOCKET.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def frame_of(kind: str) -> dict:
    """The first recorded frame of a kind."""
    return next(frame for frame in recorded_frames() if frame["type"] == kind)


def vantage(**flags) -> dict:
    """A frame of the motion as the real board sent it, with the flags given."""
    frame = deepcopy(frame_of("vantage"))
    frame["data"]["vantage"]["motion"].update(
        {"isWaiting": False, "isDart": False, "isHand": False, "isStable": True}
        | {"isTakeoutPartial": False, "isTakeoutFull": False}
        | flags
    )
    return frame


def motion(**flags) -> dict:
    """The readings of such a frame, as the client hands them to the coordinator."""
    return motion_flags(vantage(**flags)["data"]["vantage"]["motion"])


def compact(item) -> str:
    """A frame as the board writes it."""
    return json.dumps(item, separators=(",", ":"))


async def following(hass, aioclient_mock, **kwargs) -> AutodartsLocalCoordinator:
    """A running detection on 2.1 with its socket open."""
    entry = await setup_v2(
        hass, aioclient_mock, recording="2.1.0", state=running_2_1(), **kwargs
    )
    coordinator = entry.runtime_data.local
    coordinator.stream_connected = True
    return coordinator


def receive(coordinator, *messages) -> None:
    """The socket has sent the motions."""
    for flags in messages:
        coordinator.async_receive("vantage", flags)


def client_of(hass) -> AutodartsLocalClient:
    session = async_get_clientsession(hass)
    return AutodartsLocalClient("192.0.2.10", 3180, session)


def refused(status: int) -> aiohttp.WSServerHandshakeError:
    return aiohttp.WSServerHandshakeError(Mock(), (), status=status)


def text_frames(*items) -> list[str]:
    return [compact(item) for item in items]


def asked_for(connect: AsyncMock) -> list[str]:
    return [call.args[0] for call in connect.call_args_list]


# -- the client: one socket, the right one -----------------------------------------


async def test_board_manager_2_1_is_followed_on_its_second_socket_alone(hass):
    client = client_of(hass)
    client.interface_2_1 = True
    socket = Socket(text_frames(*recorded_frames()), close_code=1000)
    session = async_get_clientsession(hass)
    connect = AsyncMock(return_value=socket)
    with patch.object(session, "ws_connect", new=connect):
        received = [event async for event in REAL_EVENTS(client)]
    # One connection: nothing that /api/events sends can arrive a second time.
    assert asked_for(connect) == [BASE + SYSTEM_EVENTS]
    assert received[0] == ("connected", {})
    assert received[-1] == ("closed", {"code": 1000})
    assert received[1:-1] == [
        (frame["type"], board_state(frame["data"]))
        if frame["type"] == "state"
        else ("vantage", motion_flags(frame["data"]["vantage"]["motion"]))
        for frame in recorded_frames()
        if frame["type"] == "state"
        or (frame["type"] == "vantage" and frame["data"]["vantage"])
    ]
    # What the integration leaves to the read is known, and counts as nothing odd.
    assert client.ignored_frames == 0
    assert client.socket_path is None
    assert socket.closed


async def test_the_frame_rate_of_the_second_socket_is_no_frame_rate_of_2_0(hass):
    # "stats" there has another shape: as a frame of 2.0 it would read as no rate.
    client = client_of(hass)
    client.interface_2_1 = True
    socket = Socket(text_frames(frame_of("stats"), {"type": "new", "data": {}}))
    session = async_get_clientsession(hass)
    with patch.object(session, "ws_connect", new=AsyncMock(return_value=socket)):
        received = [event async for event in REAL_EVENTS(client)]
    assert [kind for kind, _ in received] == ["connected", "closed"]
    # A kind nobody knows yet still shows in the diagnostics.
    assert client.ignored_frames == 1


@pytest.mark.parametrize(
    "data",
    [
        {"vantage": None},
        {"vantage": {}},
        {"vantage": {"motion": None}},
        {"vantage": 1},
        {"vantage": {"motion": {"camStates": [], "numDarts": 0}}},
    ],
)
async def test_a_frame_without_the_readings_says_nothing(hass, data):
    # The real board ends with {"vantage": null} when its detection stops. A later one
    # that renames its flags can't freeze the entities at "off" either.
    client = client_of(hass)
    client.interface_2_1 = True
    socket = Socket(text_frames({"type": "vantage", "data": data}))
    session = async_get_clientsession(hass)
    with patch.object(session, "ws_connect", new=AsyncMock(return_value=socket)):
        received = [event async for event in REAL_EVENTS(client)]
    assert [kind for kind, _ in received] == ["connected", "closed"]
    assert client.ignored_frames == 0


@pytest.mark.parametrize("status", [404, 405, 500])
async def test_the_first_socket_serves_a_board_without_the_second(hass, status):
    client = client_of(hass)
    client.interface_2_1 = True
    state_frame = {"type": "state", "data": running_2_1()}
    socket = Socket(text_frames(state_frame), close_code=1000)
    session = async_get_clientsession(hass)
    connect = AsyncMock(side_effect=[refused(status), socket])
    with patch.object(session, "ws_connect", new=connect):
        received = [event async for event in REAL_EVENTS(client)]
    assert asked_for(connect) == [BASE + SYSTEM_EVENTS, BASE + EVENTS]
    assert received == [
        ("connected", {}),
        ("state", board_state(running_2_1())),
        ("closed", {"code": 1000}),
    ]


async def test_a_board_that_refuses_both_sockets_says_so(hass):
    client = client_of(hass)
    client.interface_2_1 = True
    session = async_get_clientsession(hass)
    connect = AsyncMock(side_effect=[refused(403), refused(403)])
    with patch.object(session, "ws_connect", new=connect):
        with pytest.raises(AutodartsLocalAuthError):
            async for _ in REAL_EVENTS(client):
                pass  # pragma: no cover
    assert asked_for(connect) == [BASE + SYSTEM_EVENTS, BASE + EVENTS]
    assert client.socket_path is None


async def test_a_socket_that_breaks_on_the_way_is_no_missing_socket(hass):
    client = client_of(hass)
    client.interface_2_1 = True
    session = async_get_clientsession(hass)
    connect = AsyncMock(side_effect=aiohttp.ClientConnectionError)
    with patch.object(session, "ws_connect", new=connect):
        with pytest.raises(AutodartsConnectionError):
            async for _ in REAL_EVENTS(client):
                pass  # pragma: no cover
    # The board is away: it says nothing about its first socket, nothing to try.
    assert asked_for(connect) == [BASE + SYSTEM_EVENTS]


async def test_an_earlier_board_manager_stays_on_its_socket(hass):
    client = client_of(hass)
    stats = {"type": "stats", "data": {"fps": 30}}
    socket = Socket(text_frames(stats, frame_of("vantage")), close_code=1000)
    session = async_get_clientsession(hass)
    connect = AsyncMock(return_value=socket)
    with patch.object(session, "ws_connect", new=connect):
        received = [event async for event in REAL_EVENTS(client)]
    assert asked_for(connect) == [BASE + EVENTS]
    # As before: its frame rate stays one, and it sends nothing else of these.
    assert received[1] == ("stats", {"fps": 30})
    assert client.ignored_frames == 1


class OpenSocket(Socket):
    """A socket that stays open until the client closes it, as a real one does."""

    def __init__(self, frames):
        super().__init__(frames, close_code=1000)
        self.close = AsyncMock(side_effect=self._closed)
        self._ended = asyncio.Event()

    async def _closed(self):
        self._ended.set()

    async def __aiter__(self):
        async for message in super().__aiter__():
            yield message
        await self._ended.wait()


async def test_the_socket_moves_when_the_board_shows_itself_as_2_1_later(hass):
    # A board that came up after Home Assistant, or got its update meanwhile.
    client = client_of(hass)
    first = OpenSocket(text_frames({"type": "state", "data": running_2_1()}))
    second = Socket(text_frames(vantage(isHand=True)), close_code=1000)
    session = async_get_clientsession(hass)
    connect = AsyncMock(side_effect=[first, second])
    with patch.object(session, "ws_connect", new=connect):
        events = REAL_EVENTS(client)
        assert await anext(events) == ("connected", {})
        assert (await anext(events))[0] == "state"
        assert client.socket_path == EVENTS
        # Nothing to do for a board that isn't one, and none while a read has not said so.
        await client.leave_first_socket()
        first.close.assert_not_awaited()
        client.interface_2_1 = True
        pending = asyncio.ensure_future(anext(events))
        await asyncio.sleep(0)
        await client.leave_first_socket()
        # The move shows as one more connection, not as a socket the board closed.
        assert await pending == ("connected", {})
        assert client.socket_path == SYSTEM_EVENTS
        rest = [event async for event in events]
    assert asked_for(connect) == [BASE + EVENTS, BASE + SYSTEM_EVENTS]
    assert [kind for kind, _ in rest] == ["vantage", "closed"]
    first.close.assert_awaited_once()


async def test_a_board_without_the_second_socket_is_not_asked_again_and_again(hass):
    client = client_of(hass)
    client.interface_2_1 = True
    first = OpenSocket([])
    session = async_get_clientsession(hass)
    connect = AsyncMock(side_effect=[refused(404), first])
    with patch.object(session, "ws_connect", new=connect):
        events = REAL_EVENTS(client)
        assert await anext(events) == ("connected", {})
        await client.leave_first_socket()
        first.close.assert_not_awaited()
        await events.aclose()
    assert asked_for(connect) == [BASE + SYSTEM_EVENTS, BASE + EVENTS]


async def test_a_read_that_finds_2_1_moves_the_socket(hass, aioclient_mock):
    coordinator = await following(hass, aioclient_mock)
    with patch.object(coordinator.client, "leave_first_socket", AsyncMock()) as moved:
        await reread(hass, coordinator)
    moved.assert_awaited_once()


# -- the readings of a frame, without parsing it -------------------------------------


def test_the_readings_in_the_text_of_a_frame_are_those_it_parses_to():
    lines = SECOND_SOCKET.read_text(encoding="utf-8").splitlines()
    motions = [line for line in lines if json.loads(line)["data"].get("vantage")]
    assert len(motions) > 2
    for line in motions:
        parsed = json.loads(line)["data"]["vantage"]["motion"]
        assert quick_motion_flags(line) == motion_flags(parsed)
    # Every flag on its own, as a hand and a takeout set them.
    for key in ("isWaiting", "isStable", "isDart", "isHand"):
        for value in (True, False):
            assert quick_motion_flags(compact(vantage(**{key: value})))[key] is value
    for key in ("isTakeoutPartial", "isTakeoutFull"):
        assert quick_motion_flags(compact(vantage(**{key: True})))[key] is True


def test_the_flags_of_a_camera_are_not_those_of_the_board():
    frame = vantage()
    for camera in frame["data"]["vantage"]["motion"]["camStates"]:
        camera.update(isHand=True, isDart=True, isStable=False)
    assert quick_motion_flags(compact(frame)) == motion()


@pytest.mark.parametrize(
    "text",
    [
        # Other frames, the end of the motion and another form: these are parsed.
        compact({"type": "state", "data": {"status": "throw"}}),
        '{"type":"vantage","data":{"vantage":null}}',
        json.dumps(vantage()),
        json.dumps(vantage(), sort_keys=True, separators=(",", ":"))[::-1],
        compact({"data": vantage()["data"], "type": "vantage"}),
        # A new flag among them, or one with a value that is none.
        compact(vantage()).replace('"isHand":false,', '"isHand":false,"isNew":false,'),
        compact(vantage()).replace(
            '"isHand":false,"isStable"', '"isHand":0,"isStable"'
        ),
    ],
)
def test_a_frame_in_another_form_is_left_to_the_parser(text):
    assert quick_motion_flags(text) is None


@pytest.mark.parametrize(
    "form",
    [
        lambda frame: json.dumps(frame),
        lambda frame: compact({"data": frame["data"], "type": "vantage"}),
    ],
)
async def test_the_parser_finds_the_same_readings_in_another_form(hass, form):
    client = client_of(hass)
    client.interface_2_1 = True
    socket = Socket([form(vantage(isHand=True))])
    session = async_get_clientsession(hass)
    with patch.object(session, "ws_connect", new=AsyncMock(return_value=socket)):
        received = [event async for event in REAL_EVENTS(client)]
    assert received[1] == ("vantage", motion(isHand=True))


# -- the motion follows the frames -------------------------------------------------


async def test_hand_detected_follows_the_frames_without_a_read(hass, aioclient_mock):
    coordinator = await following(hass, aioclient_mock)
    assert state(hass, "binary_sensor", "hand_detected") == "off"
    aioclient_mock.mock_calls.clear()
    receive(coordinator, motion(isHand=True, isStable=False))
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "hand_detected") == "on"
    receive(coordinator, motion(isTakeoutPartial=True, isHand=True))
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "takeout_partial") == "on"
    receive(coordinator, motion())
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "hand_detected") == "off"
    assert state(hass, "binary_sensor", "takeout_partial") == "off"
    assert reads_of(aioclient_mock, "/api/system") == 0


async def test_thirty_frames_a_second_cost_next_to_nothing(
    hass, aioclient_mock, caplog
):
    coordinator = await following(hass, aioclient_mock)
    client = coordinator.client
    client.socket_path = SYSTEM_EVENTS
    message = aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, compact(vantage()), None)
    coordinator.async_receive(*client._event(message))
    await hass.async_block_till_done()
    before = coordinator.diagnostics()
    caplog.clear()
    caplog.set_level(logging.DEBUG)
    two_minutes = 120 * 30
    with (
        patch.object(coordinator, "async_update_listeners") as listeners,
        patch.object(coordinator, "_process") as processed,
        patch.object(coordinator.topics, "async_publish") as published,
    ):
        started = time.perf_counter()
        for _ in range(two_minutes):
            coordinator.async_receive(*client._event(message))
        spent = time.perf_counter() - started
    # Frames that change nothing reach no entity, no log and no diagnostics.
    listeners.assert_not_called()
    processed.assert_not_called()
    published.assert_not_called()
    assert not caplog.records
    assert coordinator.diagnostics() == before
    # A generous bound that even a slow runner keeps: 1 % of the time they took.
    assert spent < 120 * 0.01


async def test_a_changed_value_updates_only_the_entities_of_the_motion(
    hass, aioclient_mock
):
    coordinator = await following(hass, aioclient_mock)
    receive(coordinator, motion())
    await hass.async_block_till_done()
    with (
        patch.object(coordinator, "async_update_listeners") as listeners,
        patch.object(coordinator.topics, "async_publish") as published,
    ):
        receive(coordinator, motion(isHand=True), motion(isHand=True))
    listeners.assert_not_called()
    assert published.call_count == 1


async def test_the_frames_are_ignored_while_the_board_is_the_wrong_one(
    hass, aioclient_mock
):
    coordinator = await following(hass, aioclient_mock)
    coordinator._identity_valid = False
    receive(coordinator, motion(isHand=True))
    assert "isHand" not in coordinator.readings["motion"] or (
        coordinator.readings["motion"]["isHand"] is not True
    )
    assert coordinator.diagnostics()["realtime"]["motion_frames"] is False


# -- the read as the fallback ------------------------------------------------------


async def test_the_reads_rest_while_frames_arrive_and_take_over_when_they_stop(
    hass, aioclient_mock, freezer
):
    coordinator = await following(hass, aioclient_mock)
    # A socket without frames of the motion: as in v2.1.1.
    await reread(hass, coordinator)
    assert coordinator.update_interval == timedelta(seconds=2)
    receive(coordinator, motion(isHand=True))
    await reread(hass, coordinator)
    assert coordinator.update_interval == timedelta(seconds=10)
    assert coordinator.diagnostics()["realtime"]["motion_frames"] is True
    # Frames keep the watch going.
    freezer.tick(MOTION_SILENCE_SECONDS - 0.5)
    receive(coordinator, motion(isHand=True))
    freezer.tick(1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(seconds=10)
    # They stop, with the hand still on: no entity stays at an old value.
    answer(aioclient_mock, "/api/system", json=motion_2_1(isHand=False))
    freezer.tick(MOTION_SILENCE_SECONDS * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(seconds=2)
    assert reads_of(aioclient_mock, "/api/system") == 1
    assert state(hass, "binary_sensor", "hand_detected") == "off"
    assert coordinator.diagnostics()["realtime"]["motion_frames"] is False
    # And they come back: the next frame is right whatever the read said.
    receive(coordinator, motion(isHand=True))
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "hand_detected") == "on"
    await reread(hass, coordinator)
    assert coordinator.update_interval == timedelta(seconds=10)
    assert state(hass, "binary_sensor", "hand_detected") == "on"


async def test_a_read_never_overrules_the_frames(hass, aioclient_mock):
    coordinator = await following(hass, aioclient_mock)
    receive(coordinator, motion(isHand=True))
    await hass.async_block_till_done()
    # An answer of a moment ago, which would only flip the entity back and forth.
    answer(aioclient_mock, "/api/system", json=motion_2_1(isHand=False))
    await reread(hass, coordinator)
    assert state(hass, "binary_sensor", "hand_detected") == "on"


async def test_a_stopped_detection_clears_what_the_last_frame_said(
    hass, aioclient_mock
):
    coordinator = await following(hass, aioclient_mock)
    receive(coordinator, motion(isHand=True))
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "hand_detected") == "on"
    # As the real board answers then: no motion in the read, and a state that ends it.
    stopped = {**STOPPED, "throws": []}
    system = recorded("2.1.0", "system.json")
    system["vantage"] = None
    answer(aioclient_mock, "/api/state", json=stopped)
    answer(aioclient_mock, "/api/system", json=system)
    coordinator.async_receive("state", board_state(stopped))
    await hass.async_block_till_done()
    await reread(hass, coordinator)
    assert coordinator.readings["motion"] == {}
    assert state(hass, "binary_sensor", "hand_detected") == "off"
    assert coordinator.update_interval == timedelta(seconds=10)


async def test_frames_that_end_with_the_detection_cost_no_extra_read(
    hass, aioclient_mock, freezer
):
    coordinator = await following(hass, aioclient_mock)
    receive(coordinator, motion())
    stopped = {**STOPPED, "throws": []}
    answer(aioclient_mock, "/api/state", json=stopped)
    await reread(hass, coordinator)
    aioclient_mock.mock_calls.clear()
    freezer.tick(MOTION_SILENCE_SECONDS + 1)
    with patch.object(coordinator, "async_refresh", AsyncMock()) as refresh:
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    refresh.assert_not_awaited()
    assert coordinator.update_interval == timedelta(seconds=10)


async def test_a_dropped_socket_leaves_the_motion_to_the_read_at_once(
    hass, aioclient_mock
):
    coordinator = await following(hass, aioclient_mock)
    coordinator.stream_connected = False
    answer(aioclient_mock, "/api/system", json=motion_2_1(isHand=False))
    seen = []

    async def stream(self):
        yield "connected", {}
        yield "vantage", motion(isHand=True)
        await hass.async_block_till_done()
        seen.append(state(hass, "binary_sensor", "hand_detected"))
        yield "closed", {"code": 1006}

    with patch.object(AutodartsLocalClient, "events", stream):
        await coordinator._follow_events()
    await hass.async_block_till_done()
    assert seen == ["on"]
    assert state(hass, "binary_sensor", "hand_detected") == "off"
    assert coordinator.update_interval == timedelta(seconds=2)
    assert coordinator.diagnostics()["realtime"]["motion_frames"] is False
    assert coordinator.connection.last_close == "closed by the board (1006)"


async def test_the_unload_ends_the_watch_of_the_frames(hass, aioclient_mock):
    coordinator = await following(hass, aioclient_mock)
    receive(coordinator, motion())
    assert await hass.config_entries.async_unload(coordinator._entry.entry_id)
    await hass.async_block_till_done()
    assert coordinator._motion_watch is None


async def test_the_diagnostics_say_which_socket_without_a_count_of_frames(
    hass, aioclient_mock
):
    coordinator = await following(hass, aioclient_mock)
    realtime = coordinator.diagnostics()["realtime"]
    assert realtime["socket"] is None
    assert realtime["motion_frames"] is False
    coordinator.client.socket_path = SYSTEM_EVENTS
    receive(coordinator, motion())
    realtime = coordinator.diagnostics()["realtime"]
    assert realtime["socket"] == SYSTEM_EVENTS
    assert realtime["motion_frames"] is True


# -- darts and takeouts: every one counts once --------------------------------------


def with_motion(states: list[dict]) -> list[dict]:
    """The states of a real board as its second socket sends them: with a frame of its
    board status, frames of its motion in between, and the hand of each takeout."""
    sent: list[dict] = []
    flags: dict = {}
    for data in states:
        if data["event"] == "takeoutStarted":
            flags = {"isHand": True, "isStable": False}
        sent.append(vantage(**flags))
        sent.append({"type": "state", "data": data})
        sent.append(frame_of("board"))
        sent.append(vantage(**flags))
        if data["event"] == "takeoutStarted":
            # The hand pulled the darts, and is still at the board.
            flags = {**flags, "isTakeoutPartial": True}
            sent.append(vantage(**flags))
            flags = {**flags, "isTakeoutFull": True}
            sent.append(vantage(**flags))
            sent.append(frame_of("stats"))
        if data["event"] == "takeoutFinished":
            flags = {}
            sent.append(vantage())
    return sent


async def test_the_darts_and_takeouts_of_a_real_board_count_once_on_the_second_socket(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=LEFT_OVER)
    coordinator = entry.runtime_data.local
    client = coordinator.client
    client.interface_2_1 = True
    coordinator.stream_connected = True
    event_id = entity_id(hass, "event", "board_events")
    fired = entity_events(
        hass, event_id, entity_id(hass, "sensor", "local_visit_score")
    )
    # Three visits with the first dart that arrives twice, on the socket of the client.
    socket = Socket(text_frames(*with_motion(frames())))
    session = async_get_clientsession(hass)
    connect = AsyncMock(return_value=socket)
    with patch.object(session, "ws_connect", new=connect):
        async for kind, data in REAL_EVENTS(client):
            if kind in ("state", "vantage"):
                coordinator.async_receive(kind, data)
                await hass.async_block_till_done()
    assert asked_for(connect) == [BASE + SYSTEM_EVENTS]
    assert fired_kinds(fired) == THROWN
    assert state(hass, "sensor", "training_darts") == "9"
    assert state(hass, "sensor", "local_visit_score") == "0"


async def test_a_hand_in_the_read_still_starts_a_takeout_without_frames(
    hass, aioclient_mock
):
    # Without frames, the read works as in v2.1.1, and a takeout may show there first.
    darts = {**running_2_1(), "throws": frames()[3]["throws"]}
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=darts)
    coordinator = entry.runtime_data.local
    await reread(hass, coordinator)
    event_id = entity_id(hass, "event", "board_events")
    fired = entity_events(
        hass, event_id, entity_id(hass, "sensor", "local_visit_score")
    )
    answer(aioclient_mock, "/api/system", json=motion_2_1(isHand=True))
    await reread(hass, coordinator)
    assert ("takeout_started", None) in fired_kinds(fired)


# -- the guard of a stuck takeout -----------------------------------------------------


async def test_a_hand_in_a_frame_holds_back_a_stuck_takeout_at_once(
    hass, aioclient_mock
):
    empty = {
        "connected": True,
        "event": "takeoutStarted",
        "running": True,
        "status": "takeoutInProgress",
        "throws": [],
    }
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=empty)
    coordinator = entry.runtime_data.local
    coordinator.stream_connected = True
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is True
    receive(coordinator, motion(isHand=True))
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is False
    receive(coordinator, motion())
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is True


async def test_with_frames_a_stuck_takeout_needs_no_look_at_the_board_before_its_reset(
    hass, aioclient_mock, freezer
):
    coordinator = await empty_takeout(hass, aioclient_mock)
    coordinator.stream_connected = True
    coordinator._async_unsub_refresh()
    # The frames say what the board shows: this read would hold the reset back.
    answer(aioclient_mock, "/api/system", json=motion_2_1(isHand=True))
    for _ in range(11):
        receive(coordinator, motion())
        await pass_time(hass, freezer, 1)
    assert resets(aioclient_mock) == 1
