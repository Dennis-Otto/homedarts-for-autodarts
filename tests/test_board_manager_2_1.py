"""Board Manager 2.1 answers in a new shape, which reads as that of 2.0.

tests/fixtures/board_manager_2.1.0_frames.jsonl holds the frames of the socket of a
real board with Board Manager 2.1.0, captured with scripts/capture_board.py while
four visits were thrown and taken out. tests/fixtures/board_manager_2.1.0_misses.jsonl
holds those of the same board for four more visits: with two darts in the surround,
a bouncer and a dart the board placed in the wrong bed. tests/fixtures/board_manager/2.1.0
holds what another real board answers on every route, with its detection running.
"""

import json
import time
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homedarts.diagnostics import async_get_config_entry_diagnostics
from custom_components.homedarts.errors import AutodartsConnectionError
from custom_components.homedarts.games import _throw_positions
from custom_components.homedarts.local_api import (
    AutodartsEndpointMissing,
    AutodartsLocalClient,
    _config_summary,
    board_state,
    board_system,
)
from custom_components.homedarts.sensor import _dart

from .local_helpers import (
    BASE,
    RECORDINGS,
    entity_id,
    local_entry_data,
    mock_board,
    mock_board_v2,
    recorded,
    setup_local,
    setup_v2,
    state,
    switch,
)
from .test_realtime import REAL_EVENTS, Socket, entity_events
from .test_stuck_takeout import pass_time

FRAMES = Path(__file__).parent / "fixtures" / "board_manager_2.1.0_frames.jsonl"
MISSES = Path(__file__).parent / "fixtures" / "board_manager_2.1.0_misses.jsonl"


def frames(path: Path = FRAMES) -> list[dict]:
    """The states the board sent, in order."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["data"] for line in lines]


def flat(name, number, multiplier, bed, x, y):
    """A dart as Board Manager 2.1 sends it."""
    return {
        "bed": bed,
        "bouncer": False,
        "coordsX": x,
        "coordsY": y,
        "failed": False,
        "method": "UnanimousCam",
        "multiplier": multiplier,
        "segmentName": name,
        "segmentNumber": number,
    }


def nested(name, number, multiplier, bed, x, y):
    """The same dart as Board Manager 2.0 sends it."""
    return {
        "segment": {
            "name": name,
            "number": number,
            "bed": bed,
            "multiplier": multiplier,
        },
        "coords": {"x": x, "y": y},
    }


T20 = ("T20", 20, 3, "Triple", 0.0021, 0.6138)
BULL = ("Bull", 25, 2, "Double", 0.0081, -0.0215)
# The darts the board still showed when the capture began.
LEFT_OVER = {**frames()[0], "status": "takeout", "event": "throwDetected"}


def test_a_state_of_board_manager_2_1_reads_as_one_of_2_0():
    raw = {
        "connected": True,
        "event": "takeoutStarted",
        "running": True,
        "status": "takeoutInProgress",
        "throws": [flat(*T20), flat(*BULL)],
    }
    sent = deepcopy(raw)
    assert board_state(raw) == {
        "connected": True,
        "event": "Takeout started",
        "running": True,
        "status": "Takeout in progress",
        "numThrows": 2,
        "throws": [nested(*T20), nested(*BULL)],
    }
    assert raw == sent


@pytest.mark.parametrize(
    ("sent", "read"),
    [
        ("throw", "Throw"),
        ("takeout", "Takeout"),
        ("throwDetected", "Throw detected"),
        ("takeoutFinished", "Takeout finished"),
        ("Takeout in progress", "Takeout in progress"),
        ("Stopped", "Stopped"),
        ("", ""),
        (None, None),
        (3, 3),
    ],
)
def test_status_and_event_read_in_the_words_of_board_manager_2_0(sent, read):
    assert board_state({"status": sent, "event": sent}) == {
        "status": read,
        "event": read,
    }


def test_what_board_manager_2_1_does_not_explain_stays_as_it_is():
    # No status, event or darts: nothing is added.
    assert board_state({"running": False}) == {"running": False}
    # Darts that are no list, darts of no known shape and a count the board sent.
    assert board_state({"throws": None}) == {"throws": None}
    odd = ["T20", {"segmentName": "T20"}, {"segment": {}, "segmentNumber": 20}]
    assert board_state({"throws": odd}) == {"throws": odd, "numThrows": 3}
    assert board_state({"throws": [], "numThrows": 1}) == {"throws": [], "numThrows": 1}


def config_summary(raw: dict) -> dict:
    """What the integration keeps of the answer to /api/config."""
    return _config_summary(raw, "/api/config")


def recorded_states() -> list[tuple[str, dict]]:
    """Every state that the recordings of earlier Board Managers hold."""
    result = []
    for folder in sorted(path for path in RECORDINGS.iterdir() if path.is_dir()):
        if folder.name == "2.1.0":
            continue
        state_file = folder / "state.json"
        result.append((folder.name, json.loads(state_file.read_text(encoding="utf-8"))))
        lines = (folder / "ws-frames.jsonl").read_text(encoding="utf-8").splitlines()
        result.extend(
            (folder.name, frame["data"])
            for frame in map(json.loads, lines)
            if frame["type"] == "state"
        )
    return result


@pytest.mark.parametrize(("version", "recorded"), recorded_states())
def test_a_state_of_an_earlier_board_manager_stays_as_it_is(version, recorded):
    assert board_state(recorded) == recorded, version


async def test_the_client_reads_board_manager_2_1_in_the_shape_of_2_0(
    hass, aioclient_mock
):
    aioclient_mock.get(f"{BASE}/api/state", json=LEFT_OVER)
    session = async_get_clientsession(hass)
    client = AutodartsLocalClient("192.0.2.10", 3180, session)
    assert await client.get_state() == board_state(LEFT_OVER)
    first = frames()[0]
    socket = Socket(
        [
            json.dumps({"type": "state", "data": first}),
            json.dumps({"type": "cam_state", "data": {"isRunning": True}}),
        ]
    )
    with patch.object(session, "ws_connect", new=AsyncMock(return_value=socket)):
        received = [event async for event in REAL_EVENTS(client)]
    assert received[1:3] == [
        ("state", board_state(first)),
        ("cam_state", {"isRunning": True}),
    ]


async def test_the_darts_and_takeouts_of_a_real_board_manager_2_1(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=LEFT_OVER)
    coordinator = entry.runtime_data.local
    event_id = entity_id(hass, "event", "board_events")
    fired = entity_events(
        hass, event_id, entity_id(hass, "sensor", "local_visit_score")
    )
    # The frames as the board sent them, through the socket of the client.
    socket = Socket(
        [json.dumps({"type": "state", "data": frame}) for frame in frames()]
    )
    session = async_get_clientsession(hass)
    with patch.object(session, "ws_connect", new=AsyncMock(return_value=socket)):
        async for kind, data in REAL_EVENTS(coordinator.client):
            if kind == "state":
                coordinator.async_receive(kind, data)
                await hass.async_block_till_done()
    # Each visit: its three darts, the takeout and the empty board that completes it.
    visits = [["S17", "S16", "S12"], ["S9", "S14", "T5"], ["S12", "S9", "S20"]]
    expected = [
        ("status_changed", "Takeout in progress"),
        ("takeout_started", None),
        ("status_changed", "Throw"),
        ("takeout_finished", None),
    ]
    for visit in visits:
        expected += [("dart_detected", segment) for segment in visit]
        expected += [
            ("visit_thrown", visit),
            ("status_changed", "Takeout"),
            ("status_changed", "Takeout in progress"),
            ("takeout_started", None),
            ("visit_completed", visit),
            ("status_changed", "Throw"),
            ("takeout_finished", None),
        ]
    assert [
        (
            attributes["event_type"],
            attributes.get("segment")
            or attributes.get("segments")
            or attributes.get("status"),
        )
        for attributes, _ in fired
    ] == expected
    # The darts left in the board when Home Assistant started count for nobody.
    assert state(hass, "sensor", "training_darts") == "9"
    assert state(hass, "sensor", "local_status") == "throw"
    assert state(hass, "sensor", "local_visit_score") == "0"


def bouncer_visit() -> dict:
    """The full board of the third visit: S7, the bull and a bouncer."""
    return next(
        frame
        for frame in frames(MISSES)
        if frame["status"] == "takeout" and frame["throws"][-1]["bouncer"]
    )


def test_a_dart_board_manager_2_1_could_not_place_has_no_position():
    darts = board_state(bouncer_visit())["throws"]
    assert darts[2] == {
        "segment": {"name": "Miss", "number": 0, "bed": "Outside", "multiplier": 0}
    }
    seven, bull = (dart["coords"] for dart in darts[:2])
    assert _throw_positions(board_state(bouncer_visit())) == [
        (seven["x"], seven["y"]),
        (bull["x"], bull["y"]),
        None,
    ]
    # Last dart shows it without a position, not at the centre of the bull.
    assert "x" not in _dart(darts[2])
    assert "x" in _dart(darts[1])


def test_a_dart_in_the_surround_keeps_its_position():
    surround = frames(MISSES)[6]["throws"][0]
    assert (surround["segmentName"], surround["bed"]) == ("M14", "Outside")
    dart = board_state({"throws": [surround]})["throws"][0]
    assert dart["coords"] == {"x": surround["coordsX"], "y": surround["coordsY"]}


async def test_misses_and_a_bouncer_of_a_real_board_manager_2_1(hass, aioclient_mock):
    empty = {**frames(MISSES)[-1], "event": "takeoutFinished"}
    entry = await setup_local(hass, aioclient_mock, state=empty)
    coordinator = entry.runtime_data.local
    fired = entity_events(
        hass,
        entity_id(hass, "event", "board_events"),
        entity_id(hass, "sensor", "local_visit_score"),
    )
    socket = Socket(
        [json.dumps({"type": "state", "data": frame}) for frame in frames(MISSES)]
    )
    session = async_get_clientsession(hass)
    with patch.object(session, "ws_connect", new=AsyncMock(return_value=socket)):
        async for kind, data in REAL_EVENTS(coordinator.client):
            if kind == "state":
                coordinator.async_receive(kind, data)
                await hass.async_block_till_done()
    visits = [
        ["S19", "S1", "S1"],
        ["M14", "M5", "S9"],
        ["S7", "Bull", "Miss"],
        ["S11", "D11", "M11"],
    ]
    expected = []
    for visit in visits:
        expected += [("dart_detected", segment) for segment in visit]
        expected += [
            ("visit_thrown", visit),
            ("status_changed", "Takeout"),
            ("status_changed", "Takeout in progress"),
            ("takeout_started", None),
            ("visit_completed", visit),
            # The 57 of the third visit beats the 21 of the first.
            *([("personal_best", None)] if "Bull" in visit else []),
            ("status_changed", "Throw"),
            ("takeout_finished", None),
        ]
    assert [
        (
            attributes["event_type"],
            attributes.get("segment")
            or attributes.get("segments")
            or attributes.get("status"),
        )
        for attributes, _ in fired
    ] == expected
    assert [
        attributes["score"]
        for attributes, _ in fired
        if attributes["event_type"] == "visit_completed"
    ] == [21, 9, 57, 33]
    assert state(hass, "sensor", "training_darts") == "12"


# -- the whole local interface, from the recording of a real board ---------------


def system_2_1(**status) -> dict:
    """What the real board answers to /api/system, with the changes of its status."""
    system = recorded("2.1.0", "system.json")
    system["status"].update(status)
    return system


def motion_2_1(**flags) -> dict:
    """What the real board answers to /api/system, with the motion flags given."""
    system = recorded("2.1.0", "system.json")
    system["vantage"]["motion"].update(flags)
    return system


def running_2_1() -> dict:
    """The state of the real board with its detection running."""
    return recorded("2.1.0", "state.json")


def answer(aioclient_mock, path: str, method: str = "GET", **response) -> None:
    """The board answers the route anew from now on."""
    url = f"{BASE}{path}"
    aioclient_mock.mock_calls.clear()
    aioclient_mock._mocks[:] = [
        mock
        for mock in aioclient_mock._mocks
        if not (mock.method.lower() == method.lower() and str(mock.url) == url)
    ]
    aioclient_mock.request(method, url, **response)


async def reread(hass, coordinator) -> None:
    """The next read of the board, as the timer starts it."""
    await coordinator.async_refresh()
    await hass.async_block_till_done()


def sw_version(hass, entry) -> str:
    """The version on the page of the device."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("homedarts", "board-1"), entry.entry_id
    )
    return device.sw_version


def reads_of(aioclient_mock, path: str) -> int:
    return sum(
        call[0].upper() == "GET" and str(call[1]).endswith(path)
        for call in aioclient_mock.mock_calls
    )


def writes(aioclient_mock) -> list[dict]:
    return [call[2] for call in aioclient_mock.mock_calls if call[0].upper() == "PATCH"]


@pytest.fixture
def telemetry(hass):
    """The entities a user turns on: the load of the board PC, the frame rates and
    the motion readings for diagnosis."""
    registry = er.async_get(hass)
    for key in ("cpu_usage", "memory_usage", "detection_fps", "camera_0_fps"):
        registry.async_get_or_create("sensor", "homedarts", f"board-1_{key}")
    for key in ("image_stable", "takeout_full"):
        registry.async_get_or_create("binary_sensor", "homedarts", f"board-1_{key}")


def test_the_settings_of_board_manager_2_1_read_as_those_of_2_0():
    assert config_summary(recorded("2.1.0", "config.json")) == {
        "auto_calibrate_on_start": False,
        "auto_distortion": True,
        "board_id": "board-1",
        "camera_count": 3,
        "standby_minutes": 15,
    }


@pytest.mark.parametrize("version", ["1.0.7", "2.0.0", "2.0.2"])
def test_the_settings_of_an_earlier_board_manager_read_as_before(version):
    assert config_summary(recorded(version, "config.json")) == {
        "auto_calibrate_on_start": True,
        "auto_calibrate": True,
        "auto_distortion": False,
        "board_id": "board-1",
        "camera_count": 3,
        "standby_minutes": 15,
    }


def test_a_system_read_of_board_manager_2_1_reads_as_one_of_2_0():
    raw = recorded("2.1.0", "system.json")
    sent = deepcopy(raw)
    system = board_system(raw)
    assert raw == sent
    for key in ("version", "link", "updateAvailable", "blocker", "takenOver"):
        assert system[key] == raw["status"][key]
    assert system["motion"] == raw["vantage"]["motion"]
    assert system["state"] == board_state(raw["turn"])
    assert system["config"] == raw["config"]


def test_a_system_read_of_2_1_without_its_readings_has_empty_ones():
    system = board_system({"status": {"version": "2.1.0"}, "vantage": "odd"})
    assert system["version"] == "2.1.0"
    assert system["motion"] == {}
    assert system["state"] == {}


@pytest.mark.parametrize("version", ["2.0.0", "2.0.2"])
def test_a_system_read_of_an_earlier_board_manager_stays_as_it_is(version):
    raw = recorded(version, "system.json")
    assert board_system(raw) == raw


async def test_a_board_rolled_back_from_2_1_is_set_up_anew(hass, aioclient_mock):
    er.async_get(hass).async_get_or_create(
        "button", "homedarts", "board-1_start_streams"
    )
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    coordinator = entry.runtime_data.local
    connect(coordinator, running_2_1())
    await reread(hass, coordinator)
    assert coordinator.update_interval == timedelta(seconds=2)
    assert state(hass, "button", "start_streams") == "unavailable"
    # Board Manager 1 has no /api/system: its version reloads the entry, so nothing
    # of 2.1 outlives the client, neither its pace nor the commands it hides.
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/api/system", status=404)
    mock_board(aioclient_mock)
    await reread(hass, coordinator)
    assert entry.runtime_data.local is not coordinator
    coordinator = entry.runtime_data.local
    connect(coordinator, recorded("1.0.7", "state.json"))
    assert coordinator.client.interface_2_1 is False
    assert coordinator.update_interval == timedelta(seconds=30)
    assert state(hass, "button", "start_streams") != "unavailable"


@pytest.mark.usefixtures("telemetry")
async def test_every_entity_reads_the_right_value_on_board_manager_2_1(
    hass, aioclient_mock
):
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    assert entry.state == ConfigEntryState.LOADED
    assert entry.data["api_generation"] == 2
    host = recorded("2.1.0", "host.json")
    stats = recorded("2.1.0", "system.json")["stats"]
    assert float(state(hass, "sensor", "cpu_usage")) == pytest.approx(
        stats["cpuPercent"]
    )
    for platform, key, value in (
        # The detection.
        ("switch", "detection", "on"),
        ("sensor", "local_status", "throw"),
        ("binary_sensor", "cameras_active", "on"),
        ("binary_sensor", "calibrating", "off"),
        # The settings.
        ("switch", "auto_calibrate_on_start", "off"),
        ("switch", "auto_distortion", "on"),
        ("select", "standby_minutes", "15"),
        # The motion readings.
        ("binary_sensor", "hand_detected", "off"),
        ("binary_sensor", "image_stable", "on"),
        ("binary_sensor", "takeout_partial", "off"),
        ("binary_sensor", "takeout_full", "off"),
        # The cloud link and the update.
        ("binary_sensor", "cloud_link", "on"),
        ("update", "board_software", "off"),
        # The board PC.
        ("sensor", "vision_version", "3.0.0"),
        ("sensor", "host_os", "Debian 13"),
        ("sensor", "host_processor", host["cpu"]["model"]),
        # The load and the frame rates.
        ("sensor", "memory_usage", str(stats["memoryBytes"])),
        ("sensor", "detection_fps", "30"),
        ("sensor", "camera_0_fps", "30"),
    ):
        assert state(hass, platform, key) == value, key
    update = hass.states.get(entity_id(hass, "update", "board_software"))
    assert update.attributes["installed_version"] == "2.1.0"
    assert update.attributes["latest_version"] == "2.1.0"
    assert sw_version(hass, entry) == "2.1.0"
    # A camera for each of the three the board reports.
    assert entry.runtime_data.local.data["settings"]["camera_count"] == 3
    # Nothing keeps asking for a route the board doesn't have.
    assert reads_of(aioclient_mock, "/api/state/motion") == 0
    assert not entry.runtime_data.local.reads.failing()


@pytest.mark.usefixtures("telemetry")
async def test_a_recording_of_2_0_2_gives_what_it_gave(hass, aioclient_mock):
    await setup_v2(
        hass,
        aioclient_mock,
        recording="2.0.2",
        state={**recorded("2.0.2", "state.json"), "running": True, "status": "Throw"},
    )
    for platform, key, value in (
        ("switch", "auto_calibrate_on_start", "on"),
        ("switch", "auto_calibrate", "on"),
        ("switch", "auto_distortion", "off"),
        ("select", "standby_minutes", "15"),
        ("binary_sensor", "image_stable", "on"),
        ("binary_sensor", "hand_detected", "off"),
        ("binary_sensor", "cloud_link", "on"),
        ("sensor", "vision_version", "2.0.2"),
    ):
        assert state(hass, platform, key) == value, key


async def test_a_board_on_2_1_with_another_id_counts_as_the_wrong_board(
    hass, aioclient_mock
):
    system = recorded("2.1.0", "system.json")
    system["config"]["auth"]["boardId"] = "another-board"
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", system=system)
    assert ir.async_get(hass).async_get_issue(
        "homedarts", f"wrong_board_{entry.entry_id}"
    )


async def test_a_board_on_2_1_can_be_set_up(hass, aioclient_mock):
    mock_board_v2(aioclient_mock, recording="2.1.0")
    client = AutodartsLocalClient("192.0.2.10", 3180, async_get_clientsession(hass))
    assert await client.identify() == {
        "board_id": "board-1",
        "version": "2.1.0",
        "camera_count": 3,
    }


async def test_an_option_board_manager_2_1_no_longer_has_is_not_offered(
    hass, aioclient_mock
):
    await setup_v2(hass, aioclient_mock, recording="2.1.0")
    assert state(hass, "switch", "auto_calibrate") == "unavailable"
    client = AutodartsLocalClient("192.0.2.10", 3180, async_get_clientsession(hass))
    aioclient_mock.patch(f"{BASE}/api/config", status=204)
    with pytest.raises(AutodartsEndpointMissing):
        await client.set_config_switch("auto_calibrate", True)
    assert not writes(aioclient_mock)


async def test_the_writes_of_board_manager_2_1_use_its_spelling(hass, aioclient_mock):
    await setup_v2(hass, aioclient_mock, recording="2.1.0")
    aioclient_mock.patch(f"{BASE}/api/config", status=204)
    await switch(hass, "auto_calibrate_on_start", True)
    await switch(hass, "auto_distortion", False)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id(hass, "select", "standby_minutes"), "option": "30"},
        blocking=True,
    )
    assert writes(aioclient_mock) == [
        {"cam": {"autoCalibrateOnStart": True}},
        {"cam": {"autoDistortion": False}},
        {"motion": {"standbyMinutes": 30}},
    ]


@pytest.mark.parametrize("version", ["1.0.7", "2.0.0", "2.0.2"])
async def test_the_writes_of_an_earlier_board_manager_keep_their_spelling(
    hass, aioclient_mock, version
):
    mock_board(aioclient_mock, recording=version)
    aioclient_mock.patch(f"{BASE}/api/config", status=204)
    client = AutodartsLocalClient("192.0.2.10", 3180, async_get_clientsession(hass))
    await client.set_config_switch("auto_calibrate", False)
    await client.set_standby_minutes(30)
    assert writes(aioclient_mock) == [
        {"cam": {"auto_calibrate": False}},
        {"motion": {"standby_minutes": 30}},
    ]


async def test_a_write_right_after_an_update_uses_the_new_spelling(
    hass, aioclient_mock
):
    # The integration last read the board on 2.0.2; the board has 2.1.0 by now.
    await setup_v2(hass, aioclient_mock, recording="2.0.2")
    answer(aioclient_mock, "/api/config", json=recorded("2.1.0", "config.json"))
    aioclient_mock.patch(f"{BASE}/api/config", status=204)
    await switch(hass, "auto_distortion", True)
    assert writes(aioclient_mock) == [{"cam": {"autoDistortion": True}}]


async def test_no_write_goes_out_when_the_spelling_is_unknown(hass, aioclient_mock):
    # Without an answer about the settings nothing tells how to write them.
    aioclient_mock.get(f"{BASE}/api/config", status=500)
    aioclient_mock.patch(f"{BASE}/api/config", status=204)
    client = AutodartsLocalClient("192.0.2.10", 3180, async_get_clientsession(hass))
    with pytest.raises(AutodartsConnectionError):
        await client.set_standby_minutes(30)
    assert not writes(aioclient_mock)


@pytest.mark.usefixtures("telemetry")
async def test_the_motion_of_2_1_comes_from_the_system_read(hass, aioclient_mock):
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    coordinator = entry.runtime_data.local
    assert state(hass, "binary_sensor", "hand_detected") == "off"
    answer(
        aioclient_mock,
        "/api/system",
        json=motion_2_1(isHand=True, isStable=False, isTakeoutPartial=True),
    )
    await reread(hass, coordinator)
    assert state(hass, "binary_sensor", "hand_detected") == "on"
    assert state(hass, "binary_sensor", "image_stable") == "off"
    assert state(hass, "binary_sensor", "takeout_partial") == "on"
    answer(aioclient_mock, "/api/system", json=motion_2_1(isTakeoutFull=True))
    await reread(hass, coordinator)
    assert state(hass, "binary_sensor", "hand_detected") == "off"
    assert state(hass, "binary_sensor", "takeout_full") == "on"
    assert reads_of(aioclient_mock, "/api/state/motion") == 0


@pytest.mark.usefixtures("telemetry")
async def test_what_the_socket_of_2_1_no_longer_sends_comes_from_the_read(
    hass, aioclient_mock
):
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    coordinator = entry.runtime_data.local
    system = recorded("2.1.0", "system.json")
    system["camState"] = {"isOpened": False, "isRunning": False}
    system["stats"].update(fps=12, cpuPercent=7.5, memoryBytes=1024)
    system["camStats"][0]["fps"] = 12
    answer(aioclient_mock, "/api/system", json=system)
    await reread(hass, coordinator)
    assert state(hass, "binary_sensor", "cameras_active") == "off"
    assert state(hass, "sensor", "detection_fps") == "12"
    assert state(hass, "sensor", "camera_0_fps") == "12"
    assert state(hass, "sensor", "cpu_usage") == "7.5"


async def test_the_system_read_of_2_1_keeps_the_board_current(hass, aioclient_mock):
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0")
    coordinator = entry.runtime_data.local
    answer(
        aioclient_mock,
        "/api/system",
        json=system_2_1(
            updateAvailable="2.2.0", link="disconnected", calibratingCams=2
        ),
    )
    await reread(hass, coordinator)
    update = hass.states.get(entity_id(hass, "update", "board_software"))
    assert update.state == "on"
    assert update.attributes["latest_version"] == "2.2.0"
    assert state(hass, "binary_sensor", "cloud_link") == "off"
    assert state(hass, "binary_sensor", "calibrating") == "on"


async def test_an_update_of_the_board_shows_at_once(hass, aioclient_mock):
    # The stale values on a real Home Assistant right after its board went to 2.1.0.
    entry = await setup_v2(hass, aioclient_mock, recording="2.0.2")
    coordinator = entry.runtime_data.local
    assert state(hass, "sensor", "vision_version") == "2.0.2"
    answer(aioclient_mock, "/api/host", json=recorded("2.1.0", "host.json"))
    answer(aioclient_mock, "/api/system", json=recorded("2.1.0", "system.json"))
    answer(aioclient_mock, "/api/state", json=running_2_1())
    await reread(hass, coordinator)
    assert state(hass, "sensor", "vision_version") == "3.0.0"
    update = hass.states.get(entity_id(hass, "update", "board_software"))
    assert update.attributes["installed_version"] == "2.1.0"
    assert sw_version(hass, entry) == "2.1.0"
    # The option that update took away is no longer offered.
    assert state(hass, "switch", "auto_calibrate") == "unavailable"
    assert state(hass, "switch", "auto_distortion") == "on"


def connect(coordinator, *frames) -> None:
    """The socket of the board is open, and has sent the frames."""
    coordinator.stream_connected = True
    for frame in frames:
        coordinator.async_receive("state", board_state(frame))


async def test_a_running_detection_on_2_1_is_read_as_often_as_without_a_socket(
    hass, aioclient_mock
):
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    coordinator = entry.runtime_data.local
    stopped = {
        **running_2_1(),
        "running": False,
        "status": "stopped",
        "event": "stopped",
    }
    connect(coordinator, running_2_1())
    await reread(hass, coordinator)
    assert coordinator.update_interval == timedelta(seconds=2)
    # A stopped detection has no readings to follow: the board has its rest, also
    # while its socket stays silent and proves nothing by a frame.
    answer(aioclient_mock, "/api/state", json=stopped)
    connect(coordinator, stopped)
    await reread(hass, coordinator)
    await reread(hass, coordinator)
    assert coordinator.update_interval == timedelta(seconds=10)
    coordinator._stream_live = False
    await reread(hass, coordinator)
    assert coordinator.update_interval == timedelta(seconds=10)
    # Without a socket, the reads are all there is.
    coordinator.stream_connected = False
    await reread(hass, coordinator)
    assert coordinator.update_interval == timedelta(seconds=2)


async def test_an_earlier_board_manager_keeps_its_pace(hass, aioclient_mock):
    running = {**recorded("2.0.2", "state.json"), "running": True, "status": "Throw"}
    entry = await setup_v2(hass, aioclient_mock, recording="2.0.2", state=running)
    coordinator = entry.runtime_data.local
    connect(coordinator, running)
    await reread(hass, coordinator)
    assert coordinator.update_interval == timedelta(seconds=10)


@pytest.mark.usefixtures("telemetry")
async def test_the_quick_reads_of_2_1_report_the_load_no_more_often_than_before(
    hass, aioclient_mock
):
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    coordinator = entry.runtime_data.local
    connect(coordinator, running_2_1())

    def load(percent: float, **flags) -> dict:
        system = motion_2_1(**flags)
        system["stats"]["cpuPercent"] = percent
        return system

    answer(aioclient_mock, "/api/system", json=load(1.0))
    coordinator._telemetry_reported = 0.0
    await reread(hass, coordinator)
    assert state(hass, "sensor", "cpu_usage") == "1.0"
    # The next quick read: not yet, while a change of the motion shows at once.
    answer(aioclient_mock, "/api/system", json=load(2.0, isHand=True))
    await reread(hass, coordinator)
    assert state(hass, "binary_sensor", "hand_detected") == "on"
    assert state(hass, "sensor", "cpu_usage") == "1.0"
    # Ten seconds after the last report.
    answer(aioclient_mock, "/api/system", json=load(3.0, isHand=True))
    coordinator._telemetry_reported = time.monotonic() - 10
    await reread(hass, coordinator)
    assert state(hass, "sensor", "cpu_usage") == "3.0"


async def test_the_diagnostics_keep_the_secrets_of_2_1_out(hass, aioclient_mock):
    secrets = {
        "boardId": "secret-board-id",
        "apiKey": "secret-api-key",
        "tlsKey": "secret-tls-key",
        "tlsCert": "secret-tls-cert",
    }
    system = recorded("2.1.0", "system.json")
    system["config"]["auth"].update(
        boardId=secrets["boardId"], apiKey=secrets["apiKey"]
    )
    system["config"]["host"].update(
        tlsKey=secrets["tlsKey"], tlsCert=secrets["tlsCert"]
    )
    entry = MockConfigEntry(
        domain="homedarts", version=2, data=local_entry_data(secrets["boardId"])
    )
    mock_board_v2(aioclient_mock, recording="2.1.0", system=system)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    report = json.dumps(await async_get_config_entry_diagnostics(hass, entry))
    for secret in secrets.values():
        assert secret not in report
    # Whatever may once reach the data of the board, in either spelling.
    local = entry.runtime_data.local
    local.data = {
        **local.data,
        "leaked": {**secrets, "api_key": "secret-api-key", "tls_key": "secret-tls-key"},
    }
    report = json.dumps(await async_get_config_entry_diagnostics(hass, entry))
    for secret in secrets.values():
        assert secret not in report


@pytest.mark.parametrize("command", ["start_streams", "stop_streams"])
async def test_commands_board_manager_2_1_no_longer_has_are_not_offered(
    hass, aioclient_mock, command
):
    er.async_get(hass).async_get_or_create("button", "homedarts", f"board-1_{command}")
    await setup_v2(hass, aioclient_mock, recording="2.1.0")
    assert state(hass, "button", command) == "unavailable"


async def test_commands_of_an_earlier_board_manager_stay_offered(hass, aioclient_mock):
    er.async_get(hass).async_get_or_create(
        "button", "homedarts", "board-1_start_streams"
    )
    await setup_v2(hass, aioclient_mock, recording="2.0.2")
    assert state(hass, "button", "start_streams") != "unavailable"


# A takeout on an empty board. The hand flag of the real board never turned on in the
# live test, as no dart was thrown, so the tests of it rest on the shape of the recording.
EMPTY_TAKEOUT = {
    "connected": True,
    "event": "takeoutStarted",
    "running": True,
    "status": "takeoutInProgress",
    "throws": [],
}


async def empty_takeout(hass, aioclient_mock):
    """A board on 2.1 that shows a takeout without darts and takes a reset."""
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=EMPTY_TAKEOUT)
    aioclient_mock.post(f"{BASE}/api/reset")
    return entry.runtime_data.local


def resets(aioclient_mock) -> int:
    """The resets since the last answer() to the board."""
    return sum(
        call[0].upper() == "POST" and call[1].path == "/api/reset"
        for call in aioclient_mock.mock_calls
    )


async def test_a_hand_in_the_system_read_holds_back_a_stuck_takeout(
    hass, aioclient_mock
):
    coordinator = await empty_takeout(hass, aioclient_mock)
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is True
    answer(aioclient_mock, "/api/system", json=motion_2_1(isHand=True))
    await reread(hass, coordinator)
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is False
    answer(aioclient_mock, "/api/system", json=motion_2_1(isHand=False))
    await reread(hass, coordinator)
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is True


async def test_a_stuck_takeout_is_not_reset_with_a_hand_at_the_board(
    hass, aioclient_mock, freezer
):
    coordinator = await empty_takeout(hass, aioclient_mock)
    answer(aioclient_mock, "/api/system", json=motion_2_1(isHand=True))
    await reread(hass, coordinator)
    await pass_time(hass, freezer, 30)
    assert resets(aioclient_mock) == 0
    # The hand is gone: the takeout gets its whole period from the read that shows it.
    answer(aioclient_mock, "/api/system", json=motion_2_1(isHand=False))
    await reread(hass, coordinator)
    await pass_time(hass, freezer, 9)
    assert resets(aioclient_mock) == 0
    await pass_time(hass, freezer, 2)
    assert resets(aioclient_mock) == 1


@pytest.mark.parametrize(
    "look",
    [{"json": motion_2_1(isHand=True)}, {"status": 500}],
    ids=["a hand", "no answer"],
)
async def test_the_board_is_looked_at_right_before_its_reset(
    hass, aioclient_mock, freezer, look
):
    coordinator = await empty_takeout(hass, aioclient_mock)
    # No poll comes before the reset, and the socket of 2.1 announces no hand.
    coordinator._async_unsub_refresh()
    answer(aioclient_mock, "/api/system", **look)
    await pass_time(hass, freezer, 11)
    assert resets(aioclient_mock) == 0
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is True
    # A period later the board has no hand at it, and takes its reset.
    answer(aioclient_mock, "/api/system", json=motion_2_1(isHand=False))
    await pass_time(hass, freezer, 11)
    assert resets(aioclient_mock) == 1


async def test_a_state_during_the_look_at_the_board_ends_the_wait(
    hass, aioclient_mock, freezer
):
    coordinator = await empty_takeout(hass, aioclient_mock)
    coordinator._async_unsub_refresh()
    client = coordinator.client
    read = client.get_system

    async def freed_meanwhile():
        coordinator.async_receive("state", board_state(running_2_1()))
        return await read()

    with patch.object(client, "get_system", freed_meanwhile):
        await pass_time(hass, freezer, 11)
    assert resets(aioclient_mock) == 0
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is False


async def test_a_new_wait_during_the_look_at_the_board_gets_its_whole_period(
    hass, aioclient_mock, freezer
):
    coordinator = await empty_takeout(hass, aioclient_mock)
    coordinator._async_unsub_refresh()
    client = coordinator.client
    read = client.get_system

    async def freed_and_stuck_again():
        coordinator.async_receive("state", board_state(running_2_1()))
        coordinator.async_receive("state", board_state(EMPTY_TAKEOUT))
        return await read()

    with patch.object(client, "get_system", freed_and_stuck_again):
        await pass_time(hass, freezer, 11)
    assert resets(aioclient_mock) == 0
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is True
    await pass_time(hass, freezer, 11)
    assert resets(aioclient_mock) == 1
