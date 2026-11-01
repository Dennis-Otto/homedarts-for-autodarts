"""The recorded answers of the Board Manager, and the two doubles that answer like them.

tests/fixtures/board_manager holds what Board Manager 1.0.7, 2.0.0, 2.0.2 and 2.1.0
answer, redacted by scripts/capture_board.py. The double of the unit tests (local_helpers.py)
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
from functools import partial
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.homedarts.local_api import (
    AutodartsEndpointMissing,
    AutodartsLocalClient,
    _snake_case,
    board_state,
    board_system,
    motion_flags,
)

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
# What BOARD_MANAGER says to the end-to-end double, by the version it answers as.
GENERATIONS = [(1, "1.0.7"), (2, "2.0.0"), ("2.1", "2.1.0")]
# The doubles the capture script can record: on 2.1 it still leaves the board ID in a
# recording. The fix of issue 526 removes this constant and captures all GENERATIONS.
CAPTURED = GENERATIONS[:2]
# The routes of a Board Manager that its version doesn't have.
ABSENT = {
    "1.0.7": {"/api/system", "/api/host"},
    "2.1.0": {"/api/state/motion"},
}
# The frames of a real board of 2.1.0 with real darts: the recording of 2.1.0 comes
# from a board on which none was thrown.
THROWN_2_1 = RECORDINGS.parent / "board_manager_2.1.0_frames.jsonl"


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


def system_frames(version: str) -> list[dict]:
    """The frames of the second socket, of a version that has one."""
    path = RECORDINGS / version / capture_board.SYSTEM_FRAMES
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def states(version: str) -> list[dict]:
    """The state frames of a recording, and of 2.1.0 those with real darts."""
    recorded_frames = frames(version)
    if version == "2.1.0":
        lines = THROWN_2_1.read_text(encoding="utf-8").splitlines()
        recorded_frames += [json.loads(line) for line in lines]
    return [frame for frame in recorded_frames if frame["type"] == "state"]


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

    async def system_events(request):
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        for frame in system_frames(version):
            await socket.send_json(frame)
        await socket.close()
        return socket

    app.router.add_get(capture_board.EVENTS, events)
    if system_frames(version):
        app.router.add_get(capture_board.SYSTEM_EVENTS, system_events)
    return app


def test_every_tested_version_is_recorded():
    # A new capture adds a folder, which every test here takes up by itself.
    assert {"1.0.7", "2.0.0", "2.0.2", "2.1.0"} <= set(VERSIONS)
    assert {version for _, version in GENERATIONS} <= set(VERSIONS)


@pytest.mark.parametrize("version", VERSIONS)
def test_a_recording_answers_every_route_or_names_it_absent(version):
    folder = RECORDINGS / version
    recorded_routes = set(answers(version))
    assert {path.name for path in folder.iterdir()} == recorded_routes | {
        capture_board.FRAMES,
        capture_board.CAPTURE,
    } | ({capture_board.SYSTEM_FRAMES} if system_frames(version) else set())
    absent = {path for name, path in ROUTES.items() if name not in recorded_routes}
    assert set(summary(version)["absent"]) == absent
    assert summary(version)["board_manager"] == version
    # As the board answers it, maybe with a v, which the folder leaves out.
    assert capture_board.folder_name(recorded(version, "version.txt")) == version
    # Board Manager 2 has /api/system and /api/host, the classic one neither, and
    # 2.1 no /api/state/motion.
    assert absent == ABSENT.get(version, set())
    # A recording says whether it comes from a real board, and when.
    captured = summary(version)["captured"]
    assert captured is None or date.fromisoformat(captured)


@pytest.mark.parametrize("version", VERSIONS)
def test_a_recording_keeps_only_placeholders(version):
    recording = answers(version)
    # Every secret is a placeholder already, and redacted again a recording stays
    # the same: it keeps no private address either.
    second = system_frames(version)
    assert capture_board.secrets([recording, frames(version), second]) == {}
    assert capture_board.redact(recording, {}) == recording
    assert capture_board.redact(frames(version), {}) == frames(version)
    assert capture_board.redact(second, {}) == second
    # The placeholders stand where the board keeps the secrets, in its spelling; a
    # board without a key has an empty one, which is no secret.
    auth = _snake_case(recording["config.json"]["auth"])
    assert auth["board_id"] == PLACEHOLDERS["board_id"]
    assert auth["api_key"] in (PLACEHOLDERS["api_key"], "")
    if "system.json" in recording:
        host = _snake_case(recording["system.json"]["config"]["host"])
        assert host["tls_key"] in (PLACEHOLDERS["tls_key"], "")
        names = {key: recording["host.json"][key] for key in ("hostname", "ip")}
        assert names == {key: PLACEHOLDERS[key] for key in names}


@pytest.mark.parametrize("version", VERSIONS)
def test_the_capture_script_writes_a_recording_byte_for_byte_again(version):
    # A change of the redaction shows here before it changes a recording of a board.
    _, content = capture_board.files(
        answers(version),
        frames(version),
        [],
        PLACEHOLDERS["hostname"],
        None,
        system_frames(version),
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
        assert await client.get_state() == board_state(recording["state.json"])
        assert await client.get_stats() == {"fps": recording["state-stats.json"]["fps"]}
        assert await client.get_camera_stats() == {
            "fps": recording["cams-stats.json"]["fps"]
        }
        assert await client.get_camera_state() == recording["cams-state.json"]
        if "state-motion.json" in recording:
            assert await client.get_motion_state() == recording["state-motion.json"]
        else:
            with pytest.raises(AutodartsEndpointMissing):
                await client.get_motion_state()
        if "system.json" in recording:
            raw = board_system(recording["system.json"])
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
                "calibrating_cameras": raw.get("calibratingCams"),
            }
            # Every detail of the board PC that the integration keeps is understood.
            host = await client.get_host()
            assert None not in host.values(), host
        received = [event async for event in REAL_EVENTS(client)]
    assert received[0] == ("connected", {})
    second = system_frames(version)
    assert received[1:-1] == (
        [notification(frame) for frame in second if notification(frame)]
        if second
        else [
            (
                frame["type"],
                board_state(frame["data"])
                if frame["type"] == "state"
                else frame["data"],
            )
            for frame in frames(version)
        ]
    )
    assert received[-1][0] == "closed"
    assert client.ignored_frames == 0


def notification(frame: dict) -> tuple[str, dict] | None:
    """What the client makes of a frame of the second socket: the state and the
    motion; the rest is what the read of /api/system says as well."""
    if frame["type"] == "state":
        return "state", board_state(frame["data"])
    if frame["type"] == "vantage" and frame["data"]["vantage"]:
        return "vantage", motion_flags(frame["data"]["vantage"]["motion"])
    return None


def test_the_second_socket_sends_every_frame_of_the_first():
    # Why Board Manager 2.1 needs one socket: the recording holds both side by side.
    # The second may have more, as the first dart after a takeout once showed.
    second = iter(frame for frame in system_frames("2.1.0") if frame["type"] == "state")
    first = frames("2.1.0")
    assert first
    assert all(frame in second for frame in first)


def test_the_recording_of_the_second_socket_shows_what_the_integration_reads():
    second = system_frames("2.1.0")
    # The kinds of the board, the changes of its motion and its end with the detection.
    assert {frame["type"] for frame in second} == {
        "state",
        "board",
        "vantage",
        "stats",
        "vantageConfig",
        "calibration",
        "cams",
    }
    motions = [
        frame["data"]["vantage"] for frame in second if frame["type"] == "vantage"
    ]
    assert motions[-1] is None
    for key in ("isHand", "isStable", "isTakeoutPartial", "isTakeoutFull"):
        assert all(type(motion["motion"][key]) is bool for motion in motions[:-1])
    # A recording stays small: the board sent 30 of these a second.
    path = RECORDINGS / "2.1.0" / capture_board.SYSTEM_FRAMES
    assert path.stat().st_size < 32 * 1024


async def test_the_end_to_end_double_sends_the_second_socket_like_its_recording():
    app = board_mock.create_app("2.1")
    double = app[board_mock.BOARD]
    recording = {}
    for frame in system_frames("2.1.0"):
        recording.setdefault(frame["type"], []).append(shape(frame))
    async with serve(app) as (server, session):
        path = server.make_url(capture_board.SYSTEM_EVENTS)
        async with session.ws_connect(path) as socket:
            await until(lambda: double.sockets)
            start = {"running": True, "status": "throw", "event": "started"}
            await session.post(server.make_url("/control/state"), json=start)
            await session.post(
                server.make_url("/control/motion"), json={"isHand": True}
            )
            kinds = set()
            hand = False
            while kinds != set(recording) or not hand:
                sent = await socket.receive_json(timeout=5)
                kinds.add(sent["type"])
                assert shape(sent) in recording[sent["type"]], sent["type"]
                if sent["type"] == "vantage":
                    hand = sent["data"]["vantage"]["motion"]["isHand"]
            # The read tells the same.
            async with session.get(server.make_url("/api/system")) as response:
                system = await response.json()
            assert system["vantage"]["motion"]["isHand"] is True


@pytest.mark.parametrize("generation", [1, 2])
async def test_the_end_to_end_double_of_an_earlier_board_has_no_second_socket(
    generation,
):
    app = board_mock.create_app(generation)
    async with serve(app) as (server, session):
        path = server.make_url(capture_board.SYSTEM_EVENTS)
        with pytest.raises(aiohttp.WSServerHandshakeError) as refused:
            await session.ws_connect(path)
    assert refused.value.status == 404
    assert app[board_mock.BOARD].unexpected == [f"GET {capture_board.SYSTEM_EVENTS}"]


async def test_the_second_socket_of_the_end_to_end_double_has_its_faults():
    app = board_mock.create_app("2.1")
    double = app[board_mock.BOARD]
    start = {"running": True, "status": "throw", "event": "started"}
    async with serve(app) as (server, session):
        fault = server.make_url("/control/fault")
        path = server.make_url(capture_board.SYSTEM_EVENTS)
        await session.post(server.make_url("/control/state"), json=start)
        async with session.ws_connect(path) as socket:
            await session.post(fault, json={"motion_frames": False})
            await until(lambda: not double.motion_frames)
            # The socket lives on, with no motion in it.
            while (await socket.receive_json(timeout=5))["type"] == "vantage":
                pass
            for _ in range(3):
                sent = await socket.receive_json(timeout=5)
                assert sent["type"] != "vantage"
                await session.post(fault, json={"motion_frames": False})
            await session.post(
                fault, json={"second_socket": False, "drop_sockets": True}
            )
            await until(lambda: not double.second_sockets)
        with pytest.raises(aiohttp.WSServerHandshakeError) as refused:
            await session.ws_connect(path)
        assert refused.value.status == 404
        # The first socket stays, and the reads don't count the sockets.
        async with session.ws_connect(server.make_url(capture_board.EVENTS)):
            await until(lambda: double.sockets)
        assert capture_board.SYSTEM_EVENTS not in double.reads


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
            auth = _snake_case((await response.json())["auth"])
        assert auth == {"board_id": board_mock.BOARD_ID, "api_key": board_mock.API_KEY}
        if board_mock.generation_of(generation) >= 2:
            async with session.get(server.make_url("/api/system")) as response:
                system = board_system(await response.json())
            host = _snake_case(system["config"]["host"])
            assert host["tls_key"] == board_mock.TLS_KEY
            assert system["version"] == board_mock.version_of(generation) == version
            assert system["updateAvailable"] == board_mock.UPDATES[str(generation)]


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


async def test_the_end_to_end_double_says_the_words_of_the_scenario_as_2_1_does():
    app = board_mock.create_app("2.1")
    double = app[board_mock.BOARD]
    darts = [
        {
            "segment": {
                "name": "T20",
                "number": 20,
                "multiplier": 3,
                "bed": "Triple",
            },
            "coords": {"x": 0.0123, "y": 0.5981},
        }
    ]
    async with serve(app) as (server, session):
        async with session.ws_connect(server.make_url("/api/events")) as socket:
            await until(lambda: double.sockets)
            await session.post(
                server.make_url("/control/state"),
                json={
                    "running": True,
                    "status": "Takeout in progress",
                    "event": "Takeout started",
                    "throws": darts,
                },
            )
            sent = await socket.receive_json(timeout=5)
    data = sent["data"]
    assert (data["status"], data["event"]) == ("takeoutInProgress", "takeoutStarted")
    # As a real board sends a dart.
    real = next(frame for frame in states("2.1.0") if frame["data"]["throws"])
    assert shape(data["throws"]) == shape(real["data"]["throws"][:1])
    # It reads as what the scenario said.
    assert board_state(data)["throws"] == darts
    assert board_state(data)["status"] == "Takeout in progress"


async def test_the_end_to_end_double_of_2_1_refuses_the_spelling_of_2_0():
    app = board_mock.create_app("2.1")
    double = app[board_mock.BOARD]
    async with serve(app) as (server, session):
        old = {"motion": {"standby_minutes": 30}}
        async with session.patch(server.make_url("/api/config"), json=old) as response:
            assert response.status == 400
        assert double.unexpected
        new = {"motion": {"standbyMinutes": 30}}
        async with session.patch(server.make_url("/api/config"), json=new) as response:
            assert response.status == 200
        assert double.config["motion"]["standbyMinutes"] == 30


def test_the_words_of_board_manager_2_1_stay_as_they_are():
    for words in ("throw", "takeoutInProgress", "stopped", "throwDetected"):
        assert board_mock.words_of_2_1(words) == words
    assert board_mock.words_of_2_1("Throw") == "throw"
    assert board_mock.words_of_2_1("Throw detected") == "throwDetected"


@pytest.mark.parametrize(
    ("setup", "version"),
    [
        (mock_board, "1.0.7"),
        (mock_board_v2, "2.0.0"),
        (partial(mock_board_v2, recording="2.0.2"), "2.0.2"),
        (partial(mock_board_v2, recording="2.1.0"), "2.1.0"),
    ],
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
        data = shape(board_state(frame["data"]))
        assert within(shape(board(T20, S20, BULL)), data), frame


@pytest.mark.parametrize(("generation", "version"), CAPTURED)
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
