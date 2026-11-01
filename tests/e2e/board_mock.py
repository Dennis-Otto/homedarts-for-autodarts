"""Deterministic Board Manager double for the Docker end-to-end test.

Serves the local HTTP and WebSocket protocol used by the integration, records every
write command and rejects routes the integration is not expected to call. It
answers like the recordings of Board Manager 1.0.7, 2.0.0 and 2.1.0 in
tests/fixtures/board_manager, which compose.yaml mounts at /fixtures/board_manager,
with the identity of the test and the state of the board it simulates;
tests/test_board_contract.py holds it to them, as it does the double of the unit
tests. BOARD_MANAGER=2 switches to the headless Board Manager 2: /api/system, no
upstream routes, and an mDNS announcement like the real board. BOARD_MANAGER=2.1
answers like Board Manager 2.1: the new shape of its state and of /api/system, the
camelCase of its settings, no /api/state/motion, and its second socket with the motion
30 times a second, which POST /control/motion changes. The scenario speaks in the words
of Board Manager 2.0 with either, and this double says them as 2.1 says them.

POST /control/fault injects the faults of a real network and board: dropped or
refused sockets, failing or slow reads, malformed frames, restarts and the takeout
that Board Manager 2.0.2 sometimes never finishes; on 2.1 a board without its second
socket, and a second socket without frames of the motion.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import socket
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from aiohttp import WSCloseCode, WSMsgType, web

BOARD_ID = "e2e-board"
# Synthetic secret: it must never reach Home Assistant state, diagnostics or logs.
API_KEY = "e2e-only-board-api-key"
TLS_KEY = "e2e-only-tls-key"
PORT = 3180
BOARD_MANAGER = os.environ.get("BOARD_MANAGER", "1")
# The Board Manager versions the double answers as, those of its recordings, and
# the update each announces.
VERSIONS = {"1": "1.0.7", "2": "2.0.0", "2.1": "2.1.0"}
UPDATES = {"1": "2.0.2", "2": "2.0.2", "2.1": "2.1.1"}


def generation_of(board_manager: int | str) -> int:
    return int(str(board_manager).split(".")[0])


def version_of(board_manager: int | str) -> str:
    """The Board Manager version the double answers as, that of its recording."""
    return VERSIONS[str(board_manager)]


GENERATION = generation_of(BOARD_MANAGER)
VERSION = version_of(BOARD_MANAGER)
UPDATE = UPDATES[BOARD_MANAGER]
INTERFACE_2_1 = BOARD_MANAGER == "2.1"
# Next to tests/e2e in the repository, and at /fixtures next to /e2e in the
# container of the double. Read when the double starts: the scenario imports this
# module in the container of Home Assistant, which doesn't mount them.
RECORDINGS = Path(__file__).resolve().parents[1] / "fixtures" / "board_manager"
V1_ONLY = {("PUT", "/api/upstream/connect"), ("PUT", "/api/upstream/disconnect")}
EVENTS = "/api/events"
SYSTEM_EVENTS = "/api/events/system"
# As often as the second socket of the real board sends its motion, per second.
MOTION_FRAMES = 30

COMMANDS = {
    ("PUT", "/api/start"): {"running": True, "status": "Throw", "event": "Started"},
    ("PUT", "/api/stop"): {"running": False, "status": "Stopped", "event": "Stopped"},
    ("POST", "/api/restart"): {},
    ("POST", "/api/config/calibration/auto"): {},
    ("PUT", "/api/upstream/connect"): {"connected": True},
    ("PUT", "/api/upstream/disconnect"): {"connected": False},
    ("PUT", "/api/streams/start"): {},
    ("PUT", "/api/streams/stop"): {},
}


def words_of_2_1(words: str) -> str:
    """A status or event as Board Manager 2.1 says it, "takeoutInProgress" for
    "Takeout in progress"."""
    first, *others = words.split(" ")
    if not others and first != first.capitalize():
        return first  # In its words already, such as "takeoutStarted".
    return first.lower() + "".join(word.capitalize() for word in others)


def dart_of_2_1(dart: dict) -> dict:
    """A dart as Board Manager 2.1 sends it; one of its own stays as it is."""
    if "segment" not in dart:
        return dart
    segment, coords = dart["segment"], dart.get("coords", {})
    return {
        "bed": segment.get("bed", "Single"),
        "bouncer": False,
        "coordsX": coords.get("x", 0.0),
        "coordsY": coords.get("y", 0.0),
        "failed": False,
        "method": "UnanimousCam",
        "multiplier": segment["multiplier"],
        "segmentName": segment["name"],
        "segmentNumber": segment["number"],
    }


class Board:
    def __init__(self, board_manager: int | str = BOARD_MANAGER) -> None:
        self.generation = generation_of(board_manager)
        self.version = version_of(board_manager)
        self.update = UPDATES[str(board_manager)]
        self.interface_2_1 = str(board_manager) == "2.1"
        self.state = self.recorded("state.json")
        self.config = self.recorded("config.json")
        # The identity of the test, never that of the recording.
        if self.interface_2_1:
            self.config["auth"].update(boardId=BOARD_ID, apiKey=API_KEY)
            # The settings the scenario starts from; those of the board it has none
            # of its own for, like the other recordings.
            self.config["cam"].update(autoCalibrateOnStart=True, autoDistortion=False)
            # Stopped, as the other recordings begin: the recording of 2.1.0 was made
            # with the detection running.
            self.state.update(running=False, status="stopped", event="stopped")
        else:
            self.config["auth"].update(board_id=BOARD_ID, api_key=API_KEY)
        self.commands: list[dict] = []
        self.unexpected: list[str] = []
        # Reads by path, so a test can tell when an injected fault was read.
        self.reads: dict[str, int] = {}
        self.sockets: set[web.WebSocketResponse] = set()
        # Those of them on the second socket of Board Manager 2.1, the frames it
        # repeats and the motion flags the scenario set.
        self.second_sockets: set[web.WebSocketResponse] = set()
        self.frames = self.recorded_frames() if self.interface_2_1 else {}
        self.motion: dict[str, bool] = {}
        self.clear_faults()

    def recorded(self, name: str) -> Any:
        """A fresh copy of an answer of the recording: JSON, or the version text."""
        text = (RECORDINGS / self.version / name).read_text(encoding="utf-8")
        return text if name.endswith(".txt") else json.loads(text)

    def recorded_frames(self) -> dict[str, dict]:
        """The last frame of each kind on the second socket of the recording; of the
        motion the last with one, as the recording ends with the detection."""
        path = RECORDINGS / self.version / "ws-system-frames.jsonl"
        frames = map(json.loads, path.read_text(encoding="utf-8").splitlines())
        return {
            frame["type"]: frame
            for frame in frames
            if frame["type"] != "vantage" or frame["data"]["vantage"]
        }

    def motion_frame(self) -> dict:
        frame = copy.deepcopy(self.frames["vantage"])
        frame["data"]["vantage"]["motion"].update(self.motion)
        return frame

    def status_frame(self) -> dict:
        """The board frame of the second socket, which comes with every state."""
        frame = copy.deepcopy(self.frames["board"])
        frame["data"]["status"].update(
            link="connected" if self.state["connected"] else "disconnected",
            updateAvailable=self.update,
        )
        return frame

    async def repeat(self, client: web.WebSocketResponse) -> None:
        """What the second socket repeats for as long as it is open: its motion while
        the detection runs, the load and the settings of the detection every second."""
        beat = 0
        with suppress(ConnectionResetError):
            while not client.closed:
                if self.state["running"] and self.motion_frames:
                    # Without spaces, as the board writes it.
                    text = json.dumps(self.motion_frame(), separators=(",", ":"))
                    await client.send_str(text)
                if beat % MOTION_FRAMES == 0:
                    await client.send_json(self.frames["stats"])
                    await client.send_json(self.frames["vantageConfig"])
                beat += 1
                await asyncio.sleep(1 / MOTION_FRAMES)

    def clear_faults(self) -> None:
        # Refused sockets, failing or slow reads and a restart in progress.
        self.refuse_sockets = False
        self.second_socket = True
        self.motion_frames = True
        self.http_status: int | None = None
        self.delay = 0.0
        self.fault_paths: list[str] | None = None
        self.fault_count: int | None = None
        self.down_until = 0.0

    def read_fault(self, path: str) -> tuple[int | None, float]:
        """The status and delay a read gets; a counted fault is used up."""
        if time.monotonic() < self.down_until:
            return 503, 0.0
        if self.fault_paths is not None and path not in self.fault_paths:
            return None, 0.0
        if self.fault_count is not None:
            if self.fault_count <= 0:
                return None, 0.0
            self.fault_count -= 1
        return self.http_status, self.delay

    async def drop_sockets(self) -> None:
        for client in list(self.sockets):
            await client.close(code=WSCloseCode.GOING_AWAY)

    async def send_raw(self, frame: str | bytes) -> None:
        for client in list(self.sockets):
            if isinstance(frame, bytes):
                await client.send_bytes(frame)
            else:
                await client.send_str(frame)

    async def record(self, request: web.Request) -> None:
        body = await request.json() if request.can_read_body else None
        self.commands.append(
            {"method": request.method, "path": request.path_qs, "body": body}
        )

    def answered_state(self) -> dict:
        """The state of the board, as its Board Manager says it."""
        if not self.interface_2_1:
            return self.state
        return {
            "connected": self.state["connected"],
            "event": words_of_2_1(self.state["event"]),
            "running": self.state["running"],
            "status": words_of_2_1(self.state["status"]),
            "throws": [dart_of_2_1(dart) for dart in self.state["throws"]],
        }

    async def publish(self, changes: dict) -> None:
        running = self.state["running"]
        self.state.update(changes)
        if not self.interface_2_1:
            self.state["numThrows"] = len(self.state["throws"])
        for client in list(self.sockets):
            await client.send_json({"type": "state", "data": self.answered_state()})
        for client in list(self.second_sockets):
            await client.send_json(self.status_frame())
            if self.state["running"] != running:
                await client.send_json(self.frames["calibration"])
                await client.send_json(self.frames["cams"])


def routes(board: Board) -> web.RouteTableDef:
    api = web.RouteTableDef()

    @api.get("/health")
    async def health(request):
        return web.Response(text="ok")

    @api.get("/api/state")
    async def state(request):
        return web.json_response(board.answered_state())

    @api.get("/api/config")
    async def config(request):
        return web.json_response(board.config)

    @api.patch("/api/config")
    async def patch_config(request):
        await board.record(request)
        for section, values in (await request.json()).items():
            if (
                board.interface_2_1
                and not values.keys() <= board.config[section].keys()
            ):
                # A key in another spelling: nothing says what the real board makes
                # of it, so the integration must never send one.
                board.unexpected.append(f"PATCH /api/config {values}")
                raise web.HTTPBadRequest
            board.config[section].update(values)
        # The real Board Manager echoes its full configuration, including the key.
        return web.json_response(board.config)

    @api.get("/api/version")
    async def version(request):
        return web.Response(text=board.recorded("version.txt"))

    @api.get("/api/state/stats")
    async def stats(request):
        fps = 12.5 if board.state["running"] else 0.0
        return web.json_response({**board.recorded("state-stats.json"), "fps": fps})

    @api.get("/api/cams/stats")
    async def camera_stats(request):
        fps = 30.0 if board.state["running"] else 0.0
        frames = [fps] * len(board.config["cam"]["cams"])
        return web.json_response({**board.recorded("cams-stats.json"), "fps": frames})

    @api.get("/api/cams/state")
    async def camera_state(request):
        running = board.state["running"]
        recorded = board.recorded("cams-state.json")
        return web.json_response(
            {**recorded, "isRunning": running, "isOpened": running}
        )

    async def motion(request):
        return web.json_response(board.recorded("state-motion.json"))

    if not board.interface_2_1:
        api.get("/api/state/motion")(motion)

    @api.post("/api/reset")
    async def reset(request):
        await board.record(request)
        # The darts go, and a running detection waits for darts again, also after
        # a takeout it never finished.
        changes = {"throws": [], "event": "Manual reset"}
        if board.state["running"]:
            changes["status"] = "Throw"
        await board.publish(changes)
        return web.json_response({})

    @api.post("/api/config/calibration/auto/{index:\\d+}")
    async def calibrate_camera(request):
        await board.record(request)
        return web.json_response({})

    async def system(request):
        running = board.state["running"]
        fps = 30.0 if running else 0.0
        system = board.recorded("system.json")
        # The configuration and state of the board, and the TLS key of the test.
        tls_key = "tlsKey" if board.interface_2_1 else "tls_key"
        host = {**system["config"]["host"], tls_key: TLS_KEY}
        system["config"] = {**copy.deepcopy(board.config), "host": host}
        if board.interface_2_1:
            system["turn"] = board.answered_state()
            system["vantage"]["motion"].update(board.motion)
        else:
            system["state"] = {key: board.state[key] for key in system["state"]}
        system["stats"]["fps"] = 12.5 if running else 0.0
        cameras = system["camStats"]
        system["camStats"] = [
            {**cameras[index % len(cameras)], "id": index, "fps": fps}
            for index in range(len(board.config["cam"]["cams"]))
        ]
        system["camState"].update(isRunning=running, isOpened=running)
        status = system["status"] if board.interface_2_1 else system
        status["link"] = "connected" if board.state["connected"] else "disconnected"
        status["updateAvailable"] = board.update
        return web.json_response(system)

    async def host(request):
        # Like the board PC of the recording, including the details the
        # integration drops: its name, its address and those of its cameras.
        return web.json_response(board.recorded("host.json"))

    if board.generation >= 2:
        api.get("/api/system")(system)
        api.get("/api/host")(host)

    async def follow(websocket: web.WebSocketResponse) -> None:
        board.sockets.add(websocket)
        try:
            async for message in websocket:
                if message.type == WSMsgType.ERROR:
                    break
        finally:
            board.sockets.discard(websocket)

    async def opened(request: web.Request) -> web.WebSocketResponse:
        if board.refuse_sockets or time.monotonic() < board.down_until:
            raise web.HTTPServiceUnavailable
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)
        return websocket

    @api.get(EVENTS)
    async def events(request):
        websocket = await opened(request)
        await follow(websocket)
        return websocket

    async def system_events(request):
        if not board.second_socket:
            raise web.HTTPNotFound
        websocket = await opened(request)
        board.second_sockets.add(websocket)
        repeating = asyncio.create_task(board.repeat(websocket))
        try:
            await follow(websocket)
        finally:
            board.second_sockets.discard(websocket)
            repeating.cancel()
        return websocket

    if board.interface_2_1:
        api.get(SYSTEM_EVENTS)(system_events)

    @api.post("/control/motion")
    async def control_motion(request):
        board.motion.update(await request.json())
        return web.json_response(board.motion)

    @api.post("/control/state")
    async def control_state(request):
        await board.publish(await request.json())
        return web.json_response(board.state)

    @api.post("/control/fault")
    async def control_fault(request):
        fault = await request.json()
        if fault.get("clear"):
            board.clear_faults()
        if "refuse_sockets" in fault:
            board.refuse_sockets = fault["refuse_sockets"]
        if "second_socket" in fault:
            board.second_socket = fault["second_socket"]
        if "motion_frames" in fault:
            board.motion_frames = fault["motion_frames"]
        if "http_status" in fault or "delay" in fault:
            board.http_status = fault.get("http_status")
            board.delay = fault.get("delay", 0.0)
            board.fault_paths = fault.get("paths")
            board.fault_count = fault.get("count")
        if restart := fault.get("restart"):
            # Down for a few seconds, like the Board Manager after a restart.
            board.down_until = time.monotonic() + restart
        if fault.get("drop_sockets") or fault.get("restart"):
            await board.drop_sockets()
        if fault.get("stuck_takeout"):
            # Like Board Manager 2.0.2 right after a takeout: a takeout again, on
            # the empty board, which only a reset ends.
            await board.publish(
                {
                    "status": "Takeout in progress",
                    "event": "Takeout started",
                    "throws": [],
                }
            )
        if "frame" in fault:
            await board.send_raw(fault["frame"])
        if fault.get("binary"):
            await board.send_raw(b"\x00\x01")
        return web.json_response({"sockets": len(board.sockets)})

    @api.get("/control/requests")
    async def control_requests(request):
        return web.json_response(
            {
                "commands": board.commands,
                "unexpected": board.unexpected,
                "sockets": len(board.sockets),
                "second_sockets": len(board.second_sockets),
                "reads": board.reads,
                # Counted faults not yet used up; None without a counted fault.
                "faults_left": board.fault_count,
            }
        )

    return api


def fault_injection(board: Board):
    """Reads of the Board Manager API fail or answer slowly while a fault is set."""

    @web.middleware
    async def middleware(request, handler):
        # The socket has faults of its own: dropped or refused connections.
        if (
            request.method == "GET"
            and request.path.startswith("/api/")
            and request.path not in (EVENTS, SYSTEM_EVENTS)
        ):
            board.reads[request.path] = board.reads.get(request.path, 0) + 1
            status, delay = board.read_fault(request.path)
            if delay:
                await asyncio.sleep(delay)
            if status:
                return web.Response(status=status, text="injected fault")
        return await handler(request)

    return middleware


BOARD = web.AppKey("board", Board)


def create_app(board_manager: int | str = BOARD_MANAGER) -> web.Application:
    board = Board(board_manager)
    generation = board.generation
    app = web.Application(middlewares=[fault_injection(board)])
    app[BOARD] = board
    app.add_routes(routes(board))

    for (method, path), changes in COMMANDS.items():
        if generation >= 2 and (method, path) in V1_ONLY:
            continue  # Board Manager 2 has no upstream routes.

        async def command(request, changes=changes):
            await board.record(request)
            if changes:
                await board.publish(copy.deepcopy(changes))
            return web.json_response({})

        app.router.add_route(method, path, command)

    async def unexpected(request):
        board.unexpected.append(f"{request.method} {request.path_qs}")
        raise web.HTTPNotFound

    # Registered last, so only routes without a Board Manager double end here.
    app.router.add_route("*", "/{tail:.*}", unexpected)
    return app


async def announce(app: web.Application) -> None:
    """Board Manager 2 announces itself on the LAN like the real board."""
    from zeroconf import ServiceInfo
    from zeroconf.asyncio import AsyncZeroconf

    address = socket.gethostbyname(socket.gethostname())
    zeroconf = AsyncZeroconf(interfaces=[address])
    info = ServiceInfo(
        "_autodarts-board._tcp.local.",
        "autodarts-board._autodarts-board._tcp.local.",
        addresses=[socket.inet_aton(address)],
        port=PORT,
        properties={"id": "e2e0000000000001", "ip": address, "cams": "3"},
        server="homedarts-e2e.local.",
    )
    await zeroconf.async_register_service(info)

    async def withdraw(app: web.Application) -> None:
        await zeroconf.async_unregister_service(info)
        await zeroconf.async_close()

    app.on_cleanup.append(withdraw)


if __name__ == "__main__":
    app = create_app()
    if GENERATION >= 2:
        app.on_startup.append(announce)
    web.run_app(app, port=PORT, print=None)
