"""Board Manager 2.1 sends its state in a new shape, which reads as that of 2.0.

tests/fixtures/board_manager_2.1.0_frames.jsonl holds the frames of the socket of a
real board with Board Manager 2.1.0, captured with scripts/capture_board.py while
four visits were thrown and taken out.
"""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.homedarts.local_api import AutodartsLocalClient, board_state

from .local_helpers import BASE, RECORDINGS, entity_id, setup_local, state
from .test_realtime import REAL_EVENTS, Socket, entity_events

FRAMES = Path(__file__).parent / "fixtures" / "board_manager_2.1.0_frames.jsonl"


def frames() -> list[dict]:
    """The states the board sent, in order."""
    lines = FRAMES.read_text(encoding="utf-8").splitlines()
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


def recorded_states() -> list[tuple[str, dict]]:
    """Every state that the recordings of earlier Board Managers hold."""
    result = []
    for folder in sorted(path for path in RECORDINGS.iterdir() if path.is_dir()):
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
