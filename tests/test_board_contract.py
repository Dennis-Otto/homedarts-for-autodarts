"""The recorded answers of the Board Manager, and the two doubles that answer like them.

tests/fixtures/board_manager holds what Board Manager 1.0.7, 2.0.0 and 2.0.2 answer,
redacted by scripts/capture_board.py. The double of the unit tests (local_helpers.py)
and that of the Docker end-to-end test (tests/e2e/board_mock.py) answer like them.
These tests fail when a double answers a route in another shape than its recording,
when the integration can't read a recording, when a recording keeps a secret, and
when the capture script would write a recording of another shape or with a secret.
"""

import asyncio
import importlib.util
import json
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.homedarts.local_api import AutodartsLocalClient

from .local_helpers import (
    BASE,
    BULL,
    RECORDINGS,
    S20,
    T20,
    board,
    mock_board,
    mock_board_v2,
    recorded,
)

# The doubles and the recordings answer on 127.0.0.1, the one address the tests of
# Home Assistant may connect to.
pytestmark = pytest.mark.usefixtures("socket_enabled")

ROOT = Path(__file__).parents[1]
REAL_EVENTS = AutodartsLocalClient.events


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


board_mock = load("e2e_board_mock", ROOT / "tests" / "e2e" / "board_mock.py")
capture_board = load("capture_board", ROOT / "scripts" / "capture_board.py")
ROUTES = capture_board.ROUTES
PLACEHOLDERS = capture_board.PLACEHOLDERS
VERSIONS = sorted(path.name for path in RECORDINGS.iterdir() if path.is_dir())
# The generations of the end-to-end double, by the version it answers as.
GENERATIONS = [(1, "1.0.7"), (2, "2.0.0")]


def shape(value):
    """The keys and JSON types of a value without the values: one type for all
    numbers, as JSON has, and for a list the shapes of its items."""
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        shapes = []
        for item in value:
            if (kind := shape(item)) not in shapes:
                shapes.append(kind)
        return shapes
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    return "null" if value is None else type(value).__name__


def within(small, large) -> bool:
    """Whether every key of a shape is in the other shape, with the same type."""
    if isinstance(small, dict):
        return isinstance(large, dict) and all(
            key in large and within(item, large[key]) for key, item in small.items()
        )
    if isinstance(small, list):
        return isinstance(large, list) and all(
            any(within(item, other) for other in large) for item in small
        )
    return small == large


def answers(version: str) -> dict:
    """The recorded answers of a version, by the file that keeps them."""
    return {
        name: recorded(version, name)
        for name in ROUTES
        if (RECORDINGS / version / name).exists()
    }


def frames(version: str) -> list[dict]:
    text = (RECORDINGS / version / capture_board.FRAMES).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def states(version: str) -> list[dict]:
    """The state frames of a recording."""
    return [frame for frame in frames(version) if frame["type"] == "state"]


def summary(version: str) -> dict:
    return recorded(version, capture_board.CAPTURE)


@asynccontextmanager
async def serve(app: web.Application):
    """The app on a free port of 127.0.0.1, and a session to talk to it."""
    server = TestServer(app)
    await server.start_server()
    try:
        async with aiohttp.ClientSession() as session:
            yield server, session
    finally:
        await server.close()


async def until(condition, seconds: float = 5) -> None:
    async with asyncio.timeout(seconds):
        while not condition():
            await asyncio.sleep(0.01)


def replay(version: str) -> web.Application:
    """A board that answers exactly as recorded and sends the recorded frames."""
    app = web.Application()
    for name, path in ROUTES.items():
        if (RECORDINGS / version / name).exists():
            text = (RECORDINGS / version / name).read_text(encoding="utf-8")
            kind = "text/plain" if name.endswith(".txt") else "application/json"

            async def answer(request, text=text, kind=kind):
                return web.Response(text=text, content_type=kind)

            app.router.add_get(path, answer)

    async def events(request):
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        for frame in frames(version):
            await socket.send_json(frame)
        await socket.close()
        return socket

    app.router.add_get(capture_board.EVENTS, events)
    return app


def test_every_tested_version_is_recorded():
    # A new capture adds a folder, which every test here takes up by itself.
    assert {"1.0.7", "2.0.0", "2.0.2"} <= set(VERSIONS)
    assert {version for _, version in GENERATIONS} <= set(VERSIONS)


@pytest.mark.parametrize("version", VERSIONS)
def test_a_recording_answers_every_route_or_names_it_absent(version):
    folder = RECORDINGS / version
    recorded_routes = set(answers(version))
    assert {path.name for path in folder.iterdir()} == recorded_routes | {
        capture_board.FRAMES,
        capture_board.CAPTURE,
    }
    absent = {path for name, path in ROUTES.items() if name not in recorded_routes}
    assert set(summary(version)["absent"]) == absent
    assert summary(version)["board_manager"] == version
    # As the board answers it, maybe with a v, which the folder leaves out.
    assert capture_board.folder_name(recorded(version, "version.txt")) == version
    # Board Manager 2 has /api/system and /api/host, the classic one neither.
    generation = int(version.split(".")[0])
    assert absent == (set() if generation >= 2 else {"/api/system", "/api/host"})
    # A recording says whether it comes from a real board, and when.
    captured = summary(version)["captured"]
    assert captured is None or date.fromisoformat(captured)


@pytest.mark.parametrize("version", VERSIONS)
def test_a_recording_keeps_only_placeholders(version):
    recording = answers(version)
    # Every secret is a placeholder already, and redacted again a recording stays
    # the same: it keeps no private address either.
    assert capture_board.secrets([recording, frames(version)]) == {}
    assert capture_board.redact(recording, {}) == recording
    assert capture_board.redact(frames(version), {}) == frames(version)
    # The placeholders stand where the board keeps the secrets.
    auth = recording["config.json"]["auth"]
    assert auth["board_id"] == PLACEHOLDERS["board_id"]
    assert auth["api_key"] == PLACEHOLDERS["api_key"]
    if "system.json" in recording:
        host = recording["system.json"]["config"]["host"]
        assert host["tls_key"] == PLACEHOLDERS["tls_key"]
        names = {key: recording["host.json"][key] for key in ("hostname", "ip")}
        assert names == {key: PLACEHOLDERS[key] for key in names}


@pytest.mark.parametrize("version", VERSIONS)
def test_the_capture_script_writes_a_recording_byte_for_byte_again(version):
    # A change of the redaction shows here before it changes a recording of a board.
    _, content = capture_board.files(
        answers(version), frames(version), [], PLACEHOLDERS["hostname"], None
    )

    assert set(content) == {
        path.name for path in (RECORDINGS / version).iterdir() if path.is_file()
    }
    for name, text in content.items():
        if name != capture_board.CAPTURE:
            assert text == (RECORDINGS / version / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("version", VERSIONS)
async def test_the_integration_reads_every_recording(version):
    recording = answers(version)
    async with serve(replay(version)) as (server, session):
        client = AutodartsLocalClient("127.0.0.1", server.port, session)
        assert await client.identify() == {
            "board_id": "board-1",
            "version": version,
            "camera_count": len(recording["config.json"]["cam"]["cams"]),
        }
        assert await client.get_state() == recording["state.json"]
        assert await client.get_stats() == recording["state-stats.json"]
        assert await client.get_camera_stats() == recording["cams-stats.json"]
        assert await client.get_camera_state() == recording["cams-state.json"]
        assert await client.get_motion_state() == recording["state-motion.json"]
        if "system.json" in recording:
            raw = recording["system.json"]
            system = await client.get_system()
            assert system["version"] == version
            assert system["config"]["board_id"] == "board-1"
            assert system["camera_stats"] == {
                "fps": [camera["fps"] for camera in raw["camStats"]]
            }
            assert system["camera_state"] == raw["camState"]
            assert system["motion"] == raw["motion"]
            assert system["system"] == {
                "cpu_percent": raw["stats"]["cpuPercent"],
                "memory_bytes": raw["stats"]["memoryBytes"],
                "update_available": raw["updateAvailable"] or None,
                "cloud_link": raw["link"],
            }
            # Every detail of the board PC that the integration keeps is understood.
            host = await client.get_host()
            assert None not in host.values(), host
        received = [event async for event in REAL_EVENTS(client)]
    assert received[0] == ("connected", {})
    assert received[1:-1] == [
        (frame["type"], frame["data"]) for frame in frames(version)
    ]
    assert received[-1][0] == "closed"
    assert client.ignored_frames == 0


@pytest.mark.parametrize(("generation", "version"), GENERATIONS)
async def test_the_end_to_end_double_answers_like_its_recording(generation, version):
    recording = answers(version)
    async with serve(board_mock.create_app(generation)) as (server, session):
        for name, path in ROUTES.items():
            async with session.get(server.make_url(path)) as response:
                if name not in recording:
                    assert response.status == 404, path
                    continue
                assert response.status == 200, path
                text = await response.text()
            if name.endswith(".txt"):
                assert text == recording[name]
            else:
                assert shape(json.loads(text)) == shape(recording[name]), path


@pytest.mark.parametrize(("generation", "version"), GENERATIONS)
async def test_the_end_to_end_double_keeps_the_identity_of_the_test(
    generation, version
):
    async with serve(board_mock.create_app(generation)) as (server, session):
        async with session.get(server.make_url("/api/config")) as response:
            auth = (await response.json())["auth"]
        assert auth == {"board_id": board_mock.BOARD_ID, "api_key": board_mock.API_KEY}
        if generation >= 2:
            async with session.get(server.make_url("/api/system")) as response:
                system = await response.json()
            assert system["config"]["host"]["tls_key"] == board_mock.TLS_KEY
            assert system["version"] == board_mock.version_of(generation) == version
            assert system["updateAvailable"] == board_mock.UPDATE


@pytest.mark.parametrize(("generation", "version"), GENERATIONS)
async def test_the_end_to_end_double_sends_frames_like_its_recording(
    generation, version
):
    app = board_mock.create_app(generation)
    double = app[board_mock.BOARD]
    async with serve(app) as (server, session):
        async with session.ws_connect(server.make_url("/api/events")) as socket:
            await until(lambda: double.sockets)
            for frame in states(version):
                # What the scenario sets; the double adds the rest of its state.
                changes = {
                    key: frame["data"][key]
                    for key in ("running", "status", "event", "throws")
                }
                await session.post(server.make_url("/control/state"), json=changes)
                sent = await socket.receive_json(timeout=5)
                assert shape(sent) == shape(frame), frame


@pytest.mark.parametrize(
    ("setup", "version"), [(mock_board, "1.0.7"), (mock_board_v2, "2.0.0")]
)
async def test_the_unit_double_answers_as_recorded(
    hass, aioclient_mock, setup, version
):
    setup(aioclient_mock)
    session = async_get_clientsession(hass)
    for name, answer in answers(version).items():
        async with session.get(f"{BASE}{ROUTES[name]}") as response:
            text = await response.text()
        assert (text if name.endswith(".txt") else json.loads(text)) == answer, name
    for path in summary(version)["absent"]:
        with pytest.raises(AssertionError, match="No mock registered"):
            await session.get(f"{BASE}{path}")


@pytest.mark.parametrize("version", VERSIONS)
def test_the_darts_of_the_unit_tests_have_only_keys_the_board_sends(version):
    # However many darts the visit of a recording has, each fits what it sends.
    thrown = [frame for frame in states(version) if frame["data"]["throws"]]
    assert thrown
    for frame in thrown:
        assert within(shape(board(T20, S20, BULL)), shape(frame["data"])), frame


@pytest.mark.parametrize(("generation", "version"), GENERATIONS)
async def test_a_capture_of_the_end_to_end_double_matches_its_recording(
    tmp_path, generation, version
):
    app = board_mock.create_app(generation)
    double = app[board_mock.BOARD]
    connected = asyncio.Event()
    published = states(version)

    async def play():
        await connected.wait()
        await until(lambda: double.sockets)
        for frame in published:
            await double.publish(frame["data"])

    async with serve(app) as (server, _):
        player = asyncio.create_task(play())
        folder = await capture_board.capture(
            "127.0.0.1",
            server.port,
            seconds=10,
            out=tmp_path,
            limit=len(published),
            connected=connected.set,
        )
        await player

    assert folder == tmp_path / version
    written = {
        name: json.loads(text) if name.endswith(".json") else text
        for name, text in (
            (path.name, path.read_text(encoding="utf-8"))
            for path in folder.iterdir()
            if path.name in ROUTES
        )
    }
    assert {name: shape(answer) for name, answer in written.items()} == {
        name: shape(answer) for name, answer in answers(version).items()
    }
    lines = (folder / capture_board.FRAMES).read_text(encoding="utf-8").splitlines()
    assert [shape(json.loads(line)) for line in lines] == [
        shape(frame) for frame in published
    ]
    assert json.loads((folder / capture_board.CAPTURE).read_text()) == {
        "board_manager": version,
        "captured": date.today().isoformat(),
        "source": "scripts/capture_board.py",
        "absent": summary(version)["absent"],
    }
    # The identity of the test became the placeholders of a recording.
    everything = "".join(path.read_text(encoding="utf-8") for path in folder.iterdir())
    for secret in (board_mock.BOARD_ID, board_mock.API_KEY, board_mock.TLS_KEY):
        assert secret not in everything
    assert written["config.json"]["auth"] == recorded(version, "config.json")["auth"]
