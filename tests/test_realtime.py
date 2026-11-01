"""Push/poll reconciliation, native HA events, persistence and camera controls."""

import asyncio
import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from custom_components.homedarts.errors import AutodartsConnectionError
from custom_components.homedarts.local_api import (
    AutodartsLocalAuthError,
    AutodartsLocalClient,
)
from custom_components.homedarts.local_coordinator import AutodartsLocalCoordinator

from .local_helpers import (
    BASE,
    BULL,
    S20,
    STATE,
    T20,
    board,
    entity_id,
    setup_local,
    state,
    written,
)

REAL_EVENTS = AutodartsLocalClient.events
# The motion flags of a board with a hand at it.
HAND = {"isStable": False, "isHand": True, "isTakeoutPartial": False}


class Socket:
    def __init__(self, frames, close_code=None):
        self.frames = frames
        self.closed = False
        self.close_code = close_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def __aiter__(self):
        for frame in self.frames:
            if isinstance(frame, aiohttp.WSMessage):
                yield frame
            else:
                yield aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, frame, None)


@pytest.fixture
def motion_sensors_enabled():
    """Also create the motion sensors that start disabled."""
    with patch("custom_components.homedarts.binary_sensor.MOTION_DISABLED", ()):
        yield


async def test_socket_frames_are_filtered_and_closed(hass):
    session = async_get_clientsession(hass)
    client = AutodartsLocalClient("192.0.2.10", 3180, session)
    socket = Socket(
        [
            "bad json",
            "[]",
            '{"type":"auth","data":{"token":"secret"}}',
            '{"type":"state","data":null}',
            json.dumps({"type": "state", "data": STATE}),
            '{"type":"cam_stats","data":{"id":0,"fps":30}}',
            # Not JSON by the standard, but accepted by Python's parser.
            '{"type":"stats","data":{"fps":NaN}}',
        ]
    )
    with patch.object(
        session, "ws_connect", new=AsyncMock(return_value=socket)
    ) as connect:
        frames = [frame async for frame in REAL_EVENTS(client)]
    assert frames[:3] == [
        ("connected", {}),
        ("state", STATE),
        ("cam_stats", {"id": 0, "fps": 30}),
    ]
    assert frames[4] == ("closed", {"code": None})
    assert socket.closed
    assert client.ignored_frames == 4
    assert connect.call_args.args == (BASE + "/api/events",)


async def test_socket_skips_binary_frames_and_reports_errors(hass):
    session = async_get_clientsession(hass)
    client = AutodartsLocalClient("192.0.2.10", 3180, session)
    socket = Socket(
        [
            aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, b"\x00\x01", None),
            json.dumps({"type": "state", "data": STATE}),
            aiohttp.WSMessage(aiohttp.WSMsgType.ERROR, RuntimeError("reset"), None),
            json.dumps({"type": "stats", "data": {"fps": 30}}),
        ]
    )
    frames = []

    async def read_frames() -> None:
        async for frame in REAL_EVENTS(client):
            frames.append(frame)

    with (
        patch.object(session, "ws_connect", new=AsyncMock(return_value=socket)),
        pytest.raises(AutodartsConnectionError, match="event connection failed"),
    ):
        await read_frames()
    assert frames == [("connected", {}), ("state", STATE)]
    assert client.ignored_frames == 1
    assert socket.closed


@pytest.mark.parametrize(
    "kind",
    [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED],
)
async def test_socket_closed_by_the_board_ends_with_its_close_code(hass, kind):
    session = async_get_clientsession(hass)
    client = AutodartsLocalClient("192.0.2.10", 3180, session)
    socket = Socket(
        [
            json.dumps({"type": "state", "data": STATE}),
            aiohttp.WSMessage(kind, 1001, "going away"),
            json.dumps({"type": "stats", "data": {"fps": 30}}),
        ],
        close_code=1001,
    )
    with patch.object(session, "ws_connect", new=AsyncMock(return_value=socket)):
        frames = [frame async for frame in REAL_EVENTS(client)]
    assert frames == [("connected", {}), ("state", STATE), ("closed", {"code": 1001})]
    assert socket.closed


@pytest.mark.parametrize("status", [401, 403])
async def test_socket_refused_by_the_board_is_an_access_error(hass, status):
    session = async_get_clientsession(hass)
    client = AutodartsLocalClient("192.0.2.10", 3180, session)
    refused = aiohttp.WSServerHandshakeError(Mock(), (), status=status)
    with (
        patch.object(session, "ws_connect", side_effect=refused),
        pytest.raises(AutodartsLocalAuthError, match=f"HTTP {status}"),
    ):
        await anext(REAL_EVENTS(client))


async def test_socket_handshake_rejected_otherwise_is_a_connection_error(hass):
    session = async_get_clientsession(hass)
    client = AutodartsLocalClient("192.0.2.10", 3180, session)
    refused = aiohttp.WSServerHandshakeError(Mock(), (), status=400)
    with (
        patch.object(session, "ws_connect", side_effect=refused),
        pytest.raises(AutodartsConnectionError, match="refused"),
    ):
        await anext(REAL_EVENTS(client))


async def test_socket_after_home_assistant_closed_its_session_is_a_lost_connection():
    """Home Assistant closes its shared session last when it stops (#107)."""
    session = aiohttp.ClientSession()
    await session.close()
    client = AutodartsLocalClient("192.0.2.10", 3180, session)
    with pytest.raises(AutodartsConnectionError, match="closed its HTTP session"):
        await anext(REAL_EVENTS(client))


async def test_malformed_and_unknown_push_messages_change_nothing(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    before = deepcopy(coordinator.data)
    for kind, payload in (
        ("state", {**STATE, "running": "yes"}),
        ("cam_stats", {"id": 3, "fps": 30}),
        ("cam_stats", {"id": -1, "fps": 30}),
        ("cam_stats", {"id": True, "fps": 30}),
        ("cam_stats", {"id": 0, "fps": "30"}),
        ("auth", {"token": "private"}),
    ):
        coordinator.async_receive(kind, payload)
    assert coordinator.data == before
    assert "private" not in str(coordinator.data)


async def test_detection_rate_pushes_do_not_update_entities_each_time(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    updates = []
    unsubscribe = coordinator.async_add_listener(lambda: updates.append(True))
    coordinator.async_receive("stats", {"fps": 25.0})
    assert coordinator.readings["stats"] == {"fps": 25.0}
    # High-rate telemetry is published by the poll, not per message.
    assert updates == []
    coordinator.async_receive("state", board(T20))
    assert updates == [True]
    unsubscribe()


async def test_a_motion_message_updates_only_the_motion_entities(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    with written(hass) as entities:
        coordinator.async_receive("motion_state", {**HAND, "isTakeoutFull": False})
        await hass.async_block_till_done()
    assert entities == {
        entity_id(hass, "binary_sensor", key)
        for key in ("hand_detected", "takeout_partial")
    }
    assert state(hass, "binary_sensor", "hand_detected") == "on"
    # The same flags again change nothing, and nothing is written.
    with written(hass) as entities:
        coordinator.async_receive("motion_state", {**HAND, "isTakeoutFull": False})
        await hass.async_block_till_done()
    assert not entities


async def test_a_camera_message_updates_only_whether_the_cameras_run(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    with written(hass) as entities:
        coordinator.async_receive("cam_state", {"isRunning": True, "isOpened": True})
        await hass.async_block_till_done()
    assert entities == {entity_id(hass, "binary_sensor", "cameras_active")}
    assert state(hass, "binary_sensor", "cameras_active") == "on"


async def test_socket_handshake_failure_is_recoverable(hass):
    session = async_get_clientsession(hass)
    client = AutodartsLocalClient("192.0.2.10", 3180, session)
    with (
        patch.object(session, "ws_connect", side_effect=aiohttp.ClientConnectionError),
        pytest.raises(AutodartsConnectionError),
    ):
        await anext(REAL_EVENTS(client))


def entity_events(hass, event_id: str, sensor_id: str) -> list[tuple[dict, str]]:
    """Every event of the entity, with the sensor state its consumers see."""
    fired: list[tuple[dict, str]] = []

    @callback
    def changed(event) -> None:
        fired.append(
            (dict(event.data["new_state"].attributes), hass.states.get(sensor_id).state)
        )

    async_track_state_change_event(hass, event_id, changed)
    return fired


async def test_push_updates_entities_and_emits_one_event_per_dart(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    event_id = entity_id(hass, "event", "board_events")
    fired = entity_events(
        hass, event_id, entity_id(hass, "sensor", "local_visit_score")
    )
    for count in range(1, 4):
        coordinator.async_receive("state", board(*([T20] * count)))
        await hass.async_block_till_done()
        dart, visit_score = fired[count - 1]
        assert dart["event_type"] == "dart_detected"
        assert dart["dart_index"] == count
        assert dart["source"] == "websocket"
        assert dart["game"] is None
        # The sensor already shows the dart when the event arrives.
        assert visit_score == str(60 * count)
    # The third dart completes the visit while the darts are in the board.
    thrown, visit_score = fired[-1]
    assert len(fired) == 4
    assert thrown["event_type"] == "visit_thrown"
    assert {key: thrown[key] for key in ("score", "darts", "segments", "game")} == {
        "score": 180,
        "darts": 3,
        "segments": ["T20", "T20", "T20"],
        "game": None,
    }
    assert visit_score == "180"
    assert hass.states.get(event_id).attributes["event_type"] == "visit_thrown"
    assert state(hass, "sensor", "training_darts") == "3"
    # The visit counts as a 180 once it is complete.
    assert state(hass, "sensor", "training_scores_180") == "0"
    assert state(hass, "sensor", "training_average") == "180.0"
    assert state(hass, "sensor", "training_highest_visit") == "180"
    darts = hass.states.get(entity_id(hass, "sensor", "training_darts"))
    assert darts.attributes["hits"] == {"T20": 3}
    last_event = hass.states.get(event_id).state
    coordinator.async_receive("state", board(T20, T20, T20))
    await hass.async_block_till_done()
    assert hass.states.get(event_id).state == last_event
    coordinator.async_receive("state", board(T20, S20, T20))
    await hass.async_block_till_done()
    assert state(hass, "sensor", "training_darts") == "3"
    assert state(hass, "sensor", "training_scores_180") == "0"
    assert hass.states.get(event_id).attributes["event_type"] == "dart_corrected"


@pytest.mark.usefixtures("motion_sensors_enabled")
async def test_motion_sensors_and_takeout_events_are_not_replayed(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    coordinator.async_receive("state", board(T20))
    coordinator.async_receive(
        "motion_state",
        {
            "isHand": True,
            "isStable": False,
            "isTakeoutPartial": True,
            "isTakeoutFull": False,
        },
    )
    await hass.async_block_till_done()
    event_id = entity_id(hass, "event", "board_events")
    assert hass.states.get(event_id).attributes["event_type"] == "takeout_started"
    assert state(hass, "binary_sensor", "hand_detected") == "on"
    assert state(hass, "binary_sensor", "takeout_partial") == "on"
    first = hass.states.get(event_id).state
    coordinator.async_receive("state", board(T20, event="Takeout started"))
    await hass.async_block_till_done()
    assert hass.states.get(event_id).state == first
    coordinator.async_receive(
        "motion_state",
        {
            "isHand": False,
            "isStable": True,
            "isTakeoutFull": True,
            "isTakeoutPartial": False,
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(event_id).attributes["event_type"] == "takeout_finished"
    coordinator.async_receive("state", board(event="Takeout finished"))
    await hass.async_block_till_done()
    # The empty board completes the visit; takeout events are not repeated.
    completed = hass.states.get(event_id)
    assert completed.attributes["event_type"] == "visit_completed"
    assert completed.attributes["score"] == 60
    assert completed.attributes["segments"] == ["T20"]
    assert state(hass, "sensor", "training_darts") == "1"
    coordinator.async_receive("state", {**STATE})
    assert state(hass, "binary_sensor", "takeout_full") == "off"


async def test_inflight_poll_never_rolls_back_newer_push(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local

    async def stale_read():
        coordinator.async_receive("state", board(BULL))
        return board()

    with patch.object(coordinator.client, "get_state", side_effect=stale_read):
        await coordinator.async_refresh()
    assert state(hass, "sensor", "last_throw") == "Bull"
    assert state(hass, "sensor", "training_darts") == "1"
    assert state(hass, "sensor", "training_bulls") == "1"


async def test_event_consumers_see_updated_sensor_values(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    received = []

    @callback
    def capture(kind, attributes):
        received.append((kind, state(hass, "sensor", "training_points")))

    unsubscribe = async_dispatcher_connect(hass, coordinator.event_signal, capture)
    coordinator.async_receive("state", board(T20))
    await hass.async_block_till_done()
    unsubscribe()
    assert received == [("dart_detected", "60")]


async def test_training_survives_reload_and_reset_does_not_touch_board(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    entry.runtime_data.local.async_receive("state", board(T20, T20, T20))
    task = entry.runtime_data.local._stream_task
    with patch.object(
        AutodartsLocalClient, "get_state", return_value=board(T20, T20, T20)
    ):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert task.done()
    assert state(hass, "sensor", "training_darts") == "3"
    assert state(hass, "sensor", "training_scores_180") == "1"
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", "reset_training")},
        blocking=True,
    )
    entry.runtime_data.local.async_receive("state", board(T20, T20, T20))
    assert state(hass, "sensor", "training_darts") == "0"
    assert all(call[0] == "GET" for call in aioclient_mock.mock_calls)
    with patch.object(
        entry.runtime_data.local.client,
        "get_state",
        side_effect=AutodartsConnectionError,
    ):
        await entry.runtime_data.local.async_refresh()
    assert state(hass, "sensor", "training_darts") == "0"
    assert state(hass, "button", "reset_training") != "unavailable"


@pytest.mark.parametrize("index", [0, 1, 2])
async def test_individual_calibration_button(hass, aioclient_mock, index):
    await setup_local(hass, aioclient_mock)
    url = f"{BASE}/api/config/calibration/auto/{index}?distortion=true"
    aioclient_mock.post(url, status=204)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", f"calibrate_camera_{index}")},
        blocking=True,
    )
    writes = [call for call in aioclient_mock.mock_calls if call[0] != "GET"]
    assert [(call[0], str(call[1])) for call in writes] == [("POST", url)]


async def test_disconnection_never_rewrites_previously_counted_darts(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    coordinator.async_receive("state", board(T20, T20, T20))
    with patch.object(
        coordinator.client, "get_state", side_effect=AutodartsConnectionError
    ):
        await coordinator.async_refresh()
    coordinator.async_receive("state", board(S20, S20, S20))
    assert state(hass, "sensor", "training_darts") == "3"
    assert state(hass, "sensor", "training_points") == "180"
    coordinator.async_receive("state", board())
    coordinator.async_receive("state", board(BULL))
    assert state(hass, "sensor", "training_darts") == "4"
    assert state(hass, "sensor", "training_points") == "230"


async def test_poll_fallback_produces_events_and_counts_once(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    with patch.object(coordinator.client, "get_state", return_value=board(T20)):
        await coordinator.async_refresh()
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    event = hass.states.get(entity_id(hass, "event", "board_events"))
    assert event.attributes["source"] == "poll"
    assert event.attributes["event_type"] == "dart_detected"
    assert state(hass, "sensor", "training_darts") == "1"


@pytest.mark.usefixtures("motion_sensors_enabled")
async def test_calibration_hides_stale_motion_flags(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    coordinator.async_receive("motion_state", {"isHand": True, "isStable": True})
    assert state(hass, "binary_sensor", "hand_detected") == "on"
    coordinator.async_receive("state", board(status="Calibrating"))
    assert state(hass, "binary_sensor", "calibrating") == "on"
    assert state(hass, "binary_sensor", "hand_detected") == "off"
    assert state(hass, "binary_sensor", "image_stable") == "off"


async def test_removing_integration_deletes_saved_session(
    hass, aioclient_mock, hass_storage
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    entry.runtime_data.local.async_receive("state", board(T20))
    store = Store(hass, 1, f"homedarts.{entry.entry_id}.training")
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert (await store.async_load())["darts"] == 1
    await hass.config_entries.async_remove(entry.entry_id)
    assert f"homedarts.{entry.entry_id}.training" not in hass_storage


async def test_wrong_board_mutes_push_and_keeps_controls_unavailable(
    hass, aioclient_mock, freezer
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    freezer.tick(timedelta(seconds=30))
    with patch.object(
        coordinator.client, "get_config", return_value={"board_id": "other"}
    ):
        await coordinator.async_refresh()
    coordinator.async_receive("state", board(T20))
    assert state(hass, "button", "calibrate") == "unavailable"
    assert state(hass, "sensor", "training_darts") == "0"
    with patch.object(
        coordinator.client, "get_config", side_effect=AutodartsConnectionError
    ):
        await coordinator.async_refresh()
    coordinator.async_receive("state", board(T20))
    assert state(hass, "button", "calibrate") == "unavailable"


async def test_camera_stats_push_merges_individual_camera_and_raises_alarm(
    hass, aioclient_mock, freezer
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    updates = []
    unsubscribe = coordinator.async_add_listener(lambda: updates.append(True))
    coordinator.async_receive("cam_state", {"isRunning": True, "isOpened": True})
    updates.clear()
    coordinator.async_receive("cam_stats", {"id": 1, "fps": 0})
    assert coordinator.readings["camera_stats"]["fps"] == [29.9, 0, 29.8]
    freezer.tick(timedelta(seconds=14))
    coordinator.async_receive("cam_stats", {"id": 1, "fps": 0})
    assert not updates
    assert state(hass, "binary_sensor", "camera_problem") == "off"
    # The alarm itself is published at once, not with the next poll.
    freezer.tick(timedelta(seconds=1))
    coordinator.async_receive("cam_stats", {"id": 1, "fps": 0})
    assert updates == [True]
    unsubscribe()
    assert state(hass, "binary_sensor", "camera_problem") == "on"
    assert state(hass, "binary_sensor", "camera_1_problem") == "on"
    assert state(hass, "binary_sensor", "camera_0_problem") == "off"
    coordinator.async_receive("cam_state", {"isRunning": False})
    assert state(hass, "binary_sensor", "camera_problem") == "off"


async def test_stream_reconnects_polling_continues_and_unload_cancels(
    hass, aioclient_mock
):
    messages = asyncio.Queue()
    closed = asyncio.Event()
    retry = asyncio.Event()
    connected = asyncio.Event()
    calls = 0

    async def stream(self):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise AutodartsConnectionError()
        try:
            yield "connected", {}
            connected.set()
            while True:
                yield await messages.get()
        finally:
            closed.set()

    async def wait(self, delay):
        await retry.wait()
        return False

    with (
        patch.object(AutodartsLocalClient, "events", stream),
        patch.object(AutodartsLocalCoordinator, "_wait_before_reconnect", wait),
    ):
        entry = await setup_local(hass, aioclient_mock, state=board())
        assert state(hass, "binary_sensor", "realtime_connected") == "off"
        await entry.runtime_data.local.async_refresh()
        assert state(hass, "binary_sensor", "local_connected") == "on"
        retry.set()
        await connected.wait()
        assert state(hass, "binary_sensor", "realtime_connected") == "on"
        await messages.put(("state", board(T20)))
        await hass.async_block_till_done()
        assert state(hass, "sensor", "training_darts") == "1"
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert closed.is_set()
