"""Reject malformed Board Manager answers instead of passing them to entities."""

from copy import deepcopy
from unittest.mock import Mock

import aiohttp
import pytest

from custom_components.homedarts.errors import AutodartsConnectionError
from custom_components.homedarts.local_api import (
    AutodartsEndpointMissing,
    AutodartsProtocolError,
)

from .local_helpers import BASE, CONFIG, STATE, SYSTEM


@pytest.mark.parametrize(
    ("path", "read"),
    [
        ("/api/config", "get_config"),
        ("/api/system", "get_system"),
        ("/api/state/stats", "get_stats"),
        ("/api/cams/stats", "get_camera_stats"),
        ("/api/state/motion", "get_motion_state"),
        ("/api/cams/state", "get_camera_state"),
        ("/api/host", "get_host"),
    ],
)
async def test_non_object_answers_are_rejected(client, aioclient_mock, path, read):
    aioclient_mock.get(f"{BASE}{path}", json=["not", "an", "object"])
    with pytest.raises(AutodartsConnectionError):
        await getattr(client, read)()


async def test_system_answer_with_malformed_parts_keeps_the_rest(
    client, aioclient_mock
):
    system = {
        **deepcopy(SYSTEM),
        "camStats": {"fps": 30},
        "stats": "busy",
        "motion": None,
        "version": 2,
    }
    aioclient_mock.get(f"{BASE}/api/system", json=system)
    result = await client.get_system()
    assert result["camera_stats"] == {"fps": []}
    assert result["stats"] == {"fps": None}
    assert result["motion"] == {}
    assert result["version"] is None
    assert result["config"]["board_id"] == "board-1"
    assert result["system"]["cloud_link"] == "connected"


@pytest.mark.parametrize("section", ["auth", "cam", "motion"])
async def test_malformed_config_sections_are_rejected(client, aioclient_mock, section):
    aioclient_mock.get(f"{BASE}/api/config", json={**CONFIG, section: "broken"})
    with pytest.raises(AutodartsConnectionError):
        await client.get_config()


async def test_identify_works_without_a_version_route(client, aioclient_mock):
    aioclient_mock.get(f"{BASE}/api/state", json=STATE)
    aioclient_mock.get(f"{BASE}/api/config", json=CONFIG)
    aioclient_mock.get(f"{BASE}/api/version", status=404)
    assert await client.identify() == {
        "board_id": "board-1",
        "version": None,
        "camera_count": 3,
    }


async def test_missing_route_is_only_retried_for_start_and_stop(client, aioclient_mock):
    aioclient_mock.post(f"{BASE}/api/reset", status=404)
    with pytest.raises(AutodartsEndpointMissing):
        await client.command("reset")
    assert len(aioclient_mock.mock_calls) == 1


async def test_invalid_camera_index_sends_nothing(client, aioclient_mock):
    for index in (-1, 1.5, "1", True):
        with pytest.raises(ValueError, match="Invalid camera index"):
            await client.calibrate_camera(index)
    assert not aioclient_mock.mock_calls


@pytest.mark.parametrize(
    "answer",
    [
        {"text": "<html>maintenance</html>"},
        {"exc": aiohttp.ContentTypeError(Mock(), ())},
    ],
)
async def test_answers_that_are_no_json_are_protocol_errors(
    client, aioclient_mock, answer
):
    aioclient_mock.get(f"{BASE}/api/state", **answer)
    with pytest.raises(AutodartsProtocolError) as error:
        await client.get_state()
    assert error.value.path == "/api/state"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2.0.0\n", "2.0.0"),
        ("v1.0.7", "v1.0.7"),
        ("2.1.0-beta.1", "2.1.0-beta.1"),
        ("<html>Board Manager</html>", None),
        ("1." * 200, None),
    ],
)
async def test_versions_must_look_like_versions(client, aioclient_mock, text, expected):
    aioclient_mock.get(f"{BASE}/api/version", text=text)
    assert await client.get_version() == expected


async def test_texts_of_the_board_are_checked(client, aioclient_mock):
    system = {
        **deepcopy(SYSTEM),
        "version": "<script>",
        "updateAvailable": "latest and greatest",
        "link": "c" * 256,
        "stats": {"fps": True, "cpuPercent": "12", "memoryBytes": 5},
        "camState": {"isRunning": True, "device": "/dev/video0"},
    }
    aioclient_mock.get(f"{BASE}/api/system", json=system)
    aioclient_mock.get(
        f"{BASE}/api/host", json={"os": "x" * 256, "visionVersion": "vision 2"}
    )
    result = await client.get_system()
    assert result["version"] is None
    assert result["stats"] == {"fps": None}
    assert result["camera_state"] == {"isRunning": True}
    assert result["system"] == {
        "cpu_percent": None,
        "memory_bytes": 5,
        "update_available": None,
        "cloud_link": None,
        "calibrating_cameras": None,
    }
    host = await client.get_host()
    assert host["os"] is None
    assert host["vision_version"] is None
