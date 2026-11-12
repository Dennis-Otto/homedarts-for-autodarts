"""Reject malformed Board Manager answers instead of passing them to entities."""

import gzip
import json
from copy import deepcopy
from unittest.mock import Mock

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.homedarts.errors import AutodartsConnectionError
from custom_components.homedarts.local_api import (
    MAX_ANSWER,
    MAX_PICTURE,
    AutodartsEndpointMissing,
    AutodartsLocalClient,
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
        "calibrated": "yes",
        "blocker": "b" * 256,
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
        "calibrated": None,
        "blocker": None,
        "calibration": [],
    }
    host = await client.get_host()
    assert host["os"] is None
    assert host["vision_version"] is None


# A board state, with spaces to one byte beyond the limit: once announced by its
# Content-Length and once without one, as a chunked or a compressed answer comes.
PADDED = json.dumps(STATE).encode().ljust(MAX_ANSWER + 1)
OVERSIZED = [
    pytest.param(
        {"json": STATE, "headers": {"Content-Length": str(MAX_ANSWER + 1)}},
        id="announced",
    ),
    pytest.param({"content": PADDED}, id="unannounced"),
]


@pytest.mark.parametrize("answer", OVERSIZED)
@pytest.mark.parametrize(
    ("method", "path", "read"),
    [
        ("get", "/api/state", lambda client: client.get_state()),
        ("get", "/api/version", lambda client: client.get_version()),
        ("put", "/api/start", lambda client: client.command("start")),
    ],
)
async def test_answers_beyond_the_limit_are_not_read(
    client, aioclient_mock, answer, method, path, read
):
    getattr(aioclient_mock, method)(f"{BASE}{path}", **answer)
    with pytest.raises(AutodartsProtocolError) as error:
        await read(client)
    assert error.value.path == path


async def test_an_answer_of_the_largest_size_is_read(client, aioclient_mock):
    aioclient_mock.get(f"{BASE}/api/version", text="1" * MAX_ANSWER)
    # Read, but far too long for a version.
    assert await client.get_version() is None


async def test_an_unreadable_content_length_is_a_protocol_error(client, aioclient_mock):
    aioclient_mock.get(
        f"{BASE}/api/state", json=STATE, headers={"Content-Length": "many"}
    )
    with pytest.raises(AutodartsProtocolError):
        await client.get_state()


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("application/json; charset=utf-8", STATE),
        ("application/vnd.autodarts+json", STATE),
        ("text/html", None),
        ("application/octet-stream", None),
    ],
)
async def test_only_answers_that_say_they_are_json_are_parsed(
    client, aioclient_mock, kind, expected
):
    aioclient_mock.get(f"{BASE}/api/state", json=STATE, headers={"Content-Type": kind})
    if expected is None:
        with pytest.raises(AutodartsProtocolError):
            await client.get_state()
    else:
        assert await client.get_state() == expected


async def test_an_empty_json_answer_is_no_object(client, aioclient_mock):
    aioclient_mock.get(f"{BASE}/api/state", content=b" \n")
    with pytest.raises(AutodartsProtocolError):
        await client.get_state()


async def test_json_nested_too_deep_for_python_is_a_protocol_error(
    client, aioclient_mock
):
    depth = 200_000
    aioclient_mock.get(f"{BASE}/api/state", text="[" * depth + "]" * depth)
    with pytest.raises(AutodartsProtocolError):
        await client.get_state()


@pytest.mark.parametrize(
    ("content", "length"),
    [
        pytest.param(b"jpeg", {"Content-Length": str(MAX_PICTURE + 1)}, id="announced"),
        pytest.param(b"j" * (MAX_PICTURE + 1), {}, id="unannounced"),
    ],
)
async def test_camera_pictures_beyond_the_limit_are_not_read(
    client, aioclient_mock, content, length
):
    aioclient_mock.get(
        f"{BASE}/api/img/cams/0",
        content=content,
        headers={"Content-Type": "image/jpeg", **length},
    )
    with pytest.raises(AutodartsProtocolError):
        await client.get_camera_image(0)


async def test_a_camera_picture_of_the_largest_size_is_read(client, aioclient_mock):
    picture = b"j" * MAX_PICTURE
    aioclient_mock.get(
        f"{BASE}/api/img/cams/0",
        content=picture,
        headers={"Content-Type": "image/jpeg"},
    )
    assert await client.get_camera_image(0) == picture


@pytest.mark.usefixtures("socket_enabled")
async def test_a_compressed_answer_counts_by_its_inflated_size():
    """A few kilobytes on the wire, more than the limit once inflated."""
    compressed = gzip.compress(PADDED)
    assert len(compressed) < MAX_ANSWER // 100

    async def state(_request: web.Request) -> web.Response:
        return web.Response(
            body=compressed,
            content_type="application/json",
            headers={"Content-Encoding": "gzip"},
        )

    async def version(_request: web.Request) -> web.Response:
        return web.Response(
            body=gzip.compress(b"2.1.0"), headers={"Content-Encoding": "gzip"}
        )

    app = web.Application()
    app.router.add_get("/api/state", state)
    app.router.add_get("/api/version", version)
    server = TestServer(app)
    await server.start_server()
    try:
        async with aiohttp.ClientSession() as session:
            board = AutodartsLocalClient("127.0.0.1", server.port, session)
            with pytest.raises(AutodartsProtocolError):
                await board.get_state()
            # A small compressed answer is read as before.
            assert await board.get_version() == "2.1.0"
    finally:
        await server.close()
