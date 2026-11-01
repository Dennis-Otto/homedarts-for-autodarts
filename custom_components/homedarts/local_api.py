"""Local Board Manager API. Configuration secrets never leave this client."""

from __future__ import annotations

import asyncio
import math
import re
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any, cast

import aiohttp
from yarl import URL

from .errors import AutodartsApiError, AutodartsConnectionError, open_session

CONFIG_SWITCHES = ("auto_calibrate_on_start", "auto_calibrate", "auto_distortion")
STANDBY_MINUTES = (5, 10, 15, 30, 60)
# Version numbers such as 1.0.7, v2.0.0 or 2.1.0-beta.1; anything else is dropped.
VERSION_PATTERN = re.compile(r"v?\d{1,4}(?:\.\d{1,6}){0,3}(?:[-+][0-9A-Za-z.-]{1,32})?")
# More cameras than any board has; longer lists are cut.
MAX_CAMERAS = 8
# The socket ended without an error.
CLOSING = (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED)
# Home Assistant stores states of at most 255 characters.
MAX_TEXT = 255
# The sockets of a board. Board Manager 2.1 sends everything of the first on the
# second as well, and its motion there alone.
EVENTS = "/api/events"
SYSTEM_EVENTS = "/api/events/system"
# Notifications the integration follows; the board may send others.
EVENT_KINDS = ("state", "motion_state", "cam_state", "stats", "cam_stats")
# What the second socket sends besides, which the integration reads in /api/system.
# Its "stats" has another shape than that of the first socket.
SYSTEM_READ_KINDS = ("board", "stats", "vantageConfig", "calibration", "cams")
# The readings of the motion the integration keeps.
MOTION_FLAGS = (
    "isWaiting",
    "isStable",
    "isDart",
    "isHand",
    "isTakeoutPartial",
    "isTakeoutFull",
)
# A frame of the motion comes 30 times a second, and these flags stand in it in a row,
# unlike those of a camera, which has no isTakeoutFull. Reading them costs a sixth of
# parsing the frame, whose rest nothing needs. A frame in another form is parsed.
MOTION_FRAME = '{"type":"vantage"'
MOTION_TEXT = re.compile(
    r'"isDart":(?P<isDart>true|false),"isHand":(?P<isHand>true|false),'
    r'"isStable":(?P<isStable>true|false),'
    r'"isTakeoutFull":(?P<isTakeoutFull>true|false),'
    r'"isTakeoutPartial":(?P<isTakeoutPartial>true|false),'
    r'"isWaiting":(?P<isWaiting>true|false)'
)
# Board Manager 2.1 writes status and event in camelCase, "takeoutInProgress"
# where 2.0 wrote "Takeout in progress", and the keys of its settings, "boardId"
# where 2.0 wrote "board_id".
CAMEL_CASE_WORD = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
COMMANDS = {
    "start": ("PUT", "/api/start"),
    "stop": ("PUT", "/api/stop"),
    "reset": ("POST", "/api/reset"),
    "restart": ("POST", "/api/restart"),
    "calibrate": ("POST", "/api/config/calibration/auto"),
    "connect": ("PUT", "/api/upstream/connect"),
    "disconnect": ("PUT", "/api/upstream/disconnect"),
    "start_streams": ("PUT", "/api/streams/start"),
    "stop_streams": ("PUT", "/api/streams/stop"),
}


class AutodartsLocalCommandError(AutodartsApiError):
    """The board rejected an action; do not retry a possibly executed command."""


class AutodartsEndpointMissing(AutodartsLocalCommandError):
    """This firmware does not implement the requested route."""


class AutodartsLocalAuthError(AutodartsLocalCommandError):
    """The board refused access (HTTP 401 or 403); it normally needs no login."""


class AutodartsProtocolError(AutodartsConnectionError):
    """The board answered, but not in a format this integration understands."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Unexpected answer to {path}")


def _dropped_after_sending(error: BaseException | None) -> bool:
    """The connection closed after the request, not while connecting."""
    return isinstance(error, aiohttp.ServerDisconnectedError) or (
        isinstance(error, aiohttp.ClientOSError)
        and not isinstance(error, aiohttp.ClientConnectorError)
    )


def board_generation(version: object) -> int | None:
    """Major Board Manager version: 1 for the classic app, 2 for the headless board."""
    if not isinstance(version, str):
        return None
    major = version.strip().lstrip("v").split(".", 1)[0]
    return int(major) if major.isdigit() and int(major) > 0 else None


def version_text(value: object) -> str | None:
    """A version number the board reports; free text never reaches an entity."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if VERSION_PATTERN.fullmatch(text) else None


def number(value: object) -> int | float | None:
    """A finite number; booleans, NaN and infinity read as unknown."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value if math.isfinite(value) else None


def stats_summary(raw: object) -> dict[str, Any]:
    """The detection frame rate, the only statistic entities show."""
    return {"fps": number(_dict(raw).get("fps"))}


def camera_stats_summary(fps: object) -> dict[str, Any]:
    """Frame rates in camera order; values that are no number read as unknown."""
    values = fps if isinstance(fps, list) else []
    return {"fps": [number(value) for value in values[:MAX_CAMERAS]]}


def motion_flags(raw: dict[str, Any]) -> dict[str, bool]:
    """The readings of the motion that are there; nothing else is kept."""
    return {key: raw[key] for key in MOTION_FLAGS if isinstance(raw.get(key), bool)}


def quick_motion_flags(text: str) -> dict[str, bool] | None:
    """The readings of a frame of the motion without parsing it, if it has their form."""
    if not text.startswith(MOTION_FRAME) or not (match := MOTION_TEXT.search(text)):
        return None
    return {key: value == "true" for key, value in match.groupdict().items()}


def camera_state_summary(raw: object) -> dict[str, bool]:
    """Whether the cameras are opened and running; nothing else is kept."""
    state = _dict(raw)
    return {
        key: state[key]
        for key in ("isOpened", "isRunning")
        if isinstance(state.get(key), bool)
    }


def _config_summary(raw: Any, path: str) -> dict[str, Any]:
    """Only identity and supported controls; never auth, TLS or camera secrets."""
    if not isinstance(raw, dict):
        raise AutodartsProtocolError(path)
    auth, cam, motion = (
        _snake_case(raw.get(key) or {}) for key in ("auth", "cam", "motion")
    )
    if not all(isinstance(section, dict) for section in (auth, cam, motion)):
        raise AutodartsProtocolError(path)
    result = {
        key: cam[key] for key in CONFIG_SWITCHES if isinstance(cam.get(key), bool)
    }
    if isinstance(auth.get("board_id"), str):
        result["board_id"] = auth["board_id"]
    if isinstance(cam.get("cams"), list):
        result["camera_count"] = len(cam["cams"])
    if motion.get("standby_minutes") in STANDBY_MINUTES:
        result["standby_minutes"] = motion["standby_minutes"]
    return result


def _snake_case(section: Any) -> Any:
    """A section of the settings with the keys of Board Manager 2.0."""
    if not isinstance(section, dict):
        return section
    return {
        "_".join(CAMEL_CASE_WORD.split(key)).lower(): value
        for key, value in section.items()
    }


def _spelled(key: str, section: dict[str, Any]) -> str | None:
    """A key of the settings as this board spells it; None if it has no such key."""
    first, *others = key.split("_")
    camel_case = first + "".join(word.capitalize() for word in others)
    return next((name for name in (camel_case, key) if name in section), None)


def has_interface_2_1(raw: dict[str, Any]) -> bool:
    """Whether an answer to /api/system has the shape of Board Manager 2.1."""
    return isinstance(raw.get("status"), dict)


def board_system(raw: dict[str, Any]) -> dict[str, Any]:
    """The answer to /api/system in the shape of Board Manager 2.0.

    Board Manager 2.1 keeps the version, the link and the update under status, the
    state under turn and the motion readings under vantage. An answer of 2.0 stays
    as it is. The settings in it keep their spelling; _config_summary reads both.
    """
    if not has_interface_2_1(raw):
        return raw
    return {
        **raw,
        **raw["status"],
        "state": board_state(_dict(raw.get("turn"))),
        "motion": _dict(_dict(raw.get("vantage")).get("motion")),
    }


def board_state(raw: dict[str, Any]) -> dict[str, Any]:
    """The state of the board in the shape of Board Manager 2.0.

    Board Manager 2.1 sends no numThrows, each dart flat with segmentName,
    segmentNumber, bed, multiplier, coordsX and coordsY, and its status and event
    in camelCase. A state of 2.0 or of the classic app stays as it is.
    """
    state = dict(raw)
    for key in ("status", "event"):
        if key in state:
            state[key] = _phrase(state[key])
    throws = state.get("throws")
    if isinstance(throws, list):
        state["throws"] = [_dart(dart) for dart in throws]
        if "numThrows" not in state:
            state["numThrows"] = len(throws)
    return state


def _phrase(value: object) -> object:
    """A status or event of Board Manager 2.1 in the words of 2.0."""
    if not isinstance(value, str) or " " in value:
        return value
    return " ".join(CAMEL_CASE_WORD.split(value)).capitalize()


def _dart(raw: object) -> object:
    """A flat dart of Board Manager 2.1 with its segment and coordinates nested."""
    if not isinstance(raw, dict) or "segment" in raw or "segmentNumber" not in raw:
        return raw
    dart: dict[str, Any] = {
        "segment": {
            "name": raw.get("segmentName"),
            "number": raw.get("segmentNumber"),
            "bed": raw.get("bed"),
            "multiplier": raw.get("multiplier"),
        }
    }
    # A dart the board could not place, such as a bouncer, comes at (0, 0).
    if raw.get("failed") is not True:
        dart["coords"] = {"x": raw.get("coordsX"), "y": raw.get("coordsY")}
    return dart


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str | None:
    """Text short enough for an entity state; anything else reads as unknown."""
    return value if isinstance(value, str) and 0 < len(value) <= MAX_TEXT else None


class AutodartsLocalClient:
    """Control one local board, using the Board Manager's own HTTP protocol."""

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession) -> None:
        self._session = session
        self.base_url = str(URL.build(scheme="http", host=host, port=port))
        self._command_lock = asyncio.Lock()
        # Socket frames that were no known notification, for diagnostics.
        self.ignored_frames = 0
        # The last answer to /api/system had the shape of Board Manager 2.1, which
        # reports its motion on a socket of its own.
        self.interface_2_1 = False
        # The socket that is open, and the one that was asked for when it opened.
        self.socket_path: str | None = None
        self._open_socket: aiohttp.ClientWebSocketResponse | None = None
        self._asked_second_socket = False
        self._leaving_first_socket = False

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        response_type: str = "json",
        timeout: int = 10,
    ) -> Any:
        try:
            async with asyncio.timeout(timeout):
                async with open_session(self._session).request(
                    method, f"{self.base_url}{path}", json=payload
                ) as response:
                    if response.status in (404, 405):
                        raise AutodartsEndpointMissing(
                            "Endpoint not supported by this board"
                        )
                    if response.status in (401, 403):
                        raise AutodartsLocalAuthError(
                            f"Board refused access (HTTP {response.status})"
                        )
                    if response.status >= 400 and method != "GET":
                        raise AutodartsLocalCommandError(
                            f"Board rejected command (HTTP {response.status})"
                        )
                    response.raise_for_status()
                    if response_type == "none":
                        # PATCH /config may return secrets. Discard the response.
                        await response.read()
                        return None
                    if response_type == "text":
                        return (await response.text()).strip()
                    if response_type == "image":
                        if not response.headers.get("Content-Type", "").startswith(
                            "image/"
                        ):
                            raise AutodartsConnectionError("No camera image available")
                        return await response.read()
                    return await response.json()
        except aiohttp.ContentTypeError as err:
            # Something answers, but not like a Board Manager, e.g. a web page.
            raise AutodartsProtocolError(path) from err
        except (TimeoutError, aiohttp.ClientError) as err:
            # Never log response bodies, which can include the board API key.
            raise AutodartsConnectionError(
                "Unable to communicate with local board"
            ) from err
        except ValueError as err:
            # Invalid JSON or text.
            raise AutodartsProtocolError(path) from err

    async def _object(self, path: str) -> dict[str, Any]:
        """A JSON object; any other answer is a protocol error."""
        result = await self._request("GET", path)
        if not isinstance(result, dict):
            raise AutodartsProtocolError(path)
        return result

    async def get_state(self) -> dict[str, Any]:
        state = await self._object("/api/state")
        if not isinstance(state.get("running"), bool):
            raise AutodartsProtocolError("/api/state")
        return board_state(state)

    async def get_config(self) -> dict[str, Any]:
        """Return only identity and supported controls, never auth/camera secrets."""
        path = "/api/config"
        return _config_summary(await self._request("GET", path), path)

    async def get_system(self) -> dict[str, Any]:
        """Board Manager 2: status, cameras, motion and metadata in one read.

        The raw answer also carries the board API key and TLS key; only the
        fields below ever leave this client.
        """
        answer = await self._object("/api/system")
        self.interface_2_1 = has_interface_2_1(answer)
        raw = board_system(answer)
        stats = _dict(raw.get("stats"))
        cameras = raw.get("camStats")
        if not isinstance(cameras, list):
            cameras = []
        return {
            "config": _config_summary(raw.get("config") or {}, "/api/system"),
            "stats": stats_summary(stats),
            "camera_stats": camera_stats_summary(
                [_dict(camera).get("fps") for camera in cameras]
            ),
            "motion": _dict(raw.get("motion")),
            "camera_state": camera_state_summary(raw.get("camState")),
            "version": version_text(raw.get("version")),
            "system": {
                "cpu_percent": number(stats.get("cpuPercent")),
                "memory_bytes": number(stats.get("memoryBytes")),
                "update_available": version_text(raw.get("updateAvailable")),
                "cloud_link": _text(raw.get("link")),
                "calibrating_cameras": number(raw.get("calibratingCams")),
            },
        }

    async def get_host(self) -> dict[str, Any]:
        """Board Manager 2: the board PC's system, processor and detection software.

        Only these fields leave this client; the host name, addresses and
        camera identifiers of the board PC are dropped.
        """
        raw = await self._object("/api/host")
        cpu = _dict(raw.get("cpu"))
        cores = cpu.get("cores")
        return {
            "os": _text(raw.get("os")),
            "platform": _text(raw.get("platform")),
            "platform_version": _text(raw.get("platformVersion")),
            "kernel": _text(raw.get("kernelVersion")),
            "architecture": _text(raw.get("kernelArch")),
            "cpu_model": _text(cpu.get("model")),
            "cpu_cores": cores if type(cores) is int and cores > 0 else None,
            "vision_version": version_text(raw.get("visionVersion")),
            "opencv_version": version_text(raw.get("openCVVersion")),
        }

    async def identify(self) -> dict[str, Any]:
        """Board ID, version and camera count, as needed to set up a board."""
        await self.get_state()
        config = await self.get_config()
        try:
            version = await self.get_version()
        except AutodartsApiError:
            version = None
        return {
            "board_id": config.get("board_id"),
            "version": version,
            "camera_count": config.get("camera_count"),
        }

    async def get_version(self) -> str | None:
        """The Board Manager version; an answer that is no version reads as None."""
        return version_text(
            await self._request("GET", "/api/version", response_type="text")
        )

    async def get_stats(self) -> dict[str, Any]:
        return stats_summary(await self._object("/api/state/stats"))

    async def get_camera_stats(self) -> dict[str, Any]:
        return camera_stats_summary((await self._object("/api/cams/stats")).get("fps"))

    async def get_motion_state(self) -> dict[str, Any]:
        return await self._object("/api/state/motion")

    async def get_camera_state(self) -> dict[str, Any]:
        return camera_state_summary(await self._object("/api/cams/state"))

    async def events(self) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Receive local notifications; no subscription or control writes needed.

        Yields ("connected", {}) each time a socket opens and ("closed", {"code": ...})
        when the board closes it; a broken connection raises instead.

        One socket is open at a time, so that no frame can arrive twice: on Board
        Manager 2.1 its second, which also sends everything of the first, and the
        first where a board doesn't have that one.
        """
        try:
            while True:
                socket = await self._connect_socket()
                async with socket:
                    self._open_socket = socket
                    yield "connected", {}
                    async for message in socket:
                        if message.type == aiohttp.WSMsgType.ERROR:
                            raise AutodartsConnectionError(
                                "Local event connection failed"
                            )
                        if message.type in CLOSING:
                            break
                        if (event := self._event(message)) is not None:
                            yield event
                    code = socket.close_code
                if not self._leaving_first_socket:
                    break
                self._leaving_first_socket = False
            yield "closed", {"code": code if type(code) is int else None}
        except aiohttp.WSServerHandshakeError as err:
            if err.status in (401, 403):
                raise AutodartsLocalAuthError(
                    f"Board refused access (HTTP {err.status})"
                ) from err
            raise AutodartsConnectionError("Local event connection refused") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AutodartsConnectionError(
                "Local event connection unavailable"
            ) from err
        finally:
            self._open_socket = self.socket_path = None

    async def _connect_socket(self) -> aiohttp.ClientWebSocketResponse:
        """The socket of this board: the second of Board Manager 2.1, and the first
        where the board refuses that one, which then says why if it refuses that too.
        A connection that fails on the way says nothing about the sockets."""
        self._asked_second_socket = self.interface_2_1
        if self.interface_2_1:
            with suppress(aiohttp.WSServerHandshakeError):
                socket = await self._connect(SYSTEM_EVENTS)
                self.socket_path = SYSTEM_EVENTS
                return socket
        socket = await self._connect(EVENTS)
        self.socket_path = EVENTS
        return socket

    async def _connect(self, path: str) -> aiohttp.ClientWebSocketResponse:
        async with asyncio.timeout(10):
            return await open_session(self._session).ws_connect(
                f"{self.base_url}{path}",
                heartbeat=30,
                timeout=aiohttp.ClientWSTimeout(ws_close=5),
                max_msg_size=1024 * 1024,
            )

    async def leave_first_socket(self) -> None:
        """A read found Board Manager 2.1 after the first socket opened, as on a board
        that started after Home Assistant or got its update meanwhile: move to the
        second socket. A board that refused that one keeps the first until it drops."""
        socket = self._open_socket
        if socket is not None and self.interface_2_1 and not self._asked_second_socket:
            self._leaving_first_socket = True
            await socket.close()

    def _event(self, message: aiohttp.WSMessage) -> tuple[str, dict[str, Any]] | None:
        """A known notification; other frames are counted and skipped."""
        second_socket = self.socket_path == SYSTEM_EVENTS
        envelope = None
        if message.type == aiohttp.WSMsgType.TEXT:
            if second_socket and (flags := quick_motion_flags(message.data)):
                return "vantage", flags
            try:
                envelope = message.json()
            except (ValueError, TypeError):
                envelope = None
        kind, data = (
            (envelope.get("type"), envelope.get("data"))
            if isinstance(envelope, dict)
            else (None, None)
        )
        if isinstance(data, dict):
            if second_socket:
                if kind == "vantage":
                    # None when the detection stops, with {"vantage": null}, and when
                    # its flags have other names: then the read stays in charge.
                    motion = _dict(data.get("vantage")).get("motion")
                    flags = motion_flags(_dict(motion))
                    return ("vantage", flags) if flags else None
                if kind in SYSTEM_READ_KINDS:
                    return None
            if kind in EVENT_KINDS:
                return kind, board_state(data) if kind == "state" else data
        self.ignored_frames += 1
        return None

    async def calibrate_camera(self, index: int) -> None:
        if type(index) is not int or index < 0:
            raise ValueError("Invalid camera index")
        async with self._command_lock:
            await self._request(
                "POST",
                f"/api/config/calibration/auto/{index}?distortion=true",
                response_type="none",
                timeout=60,
            )

    async def get_camera_image(self, index: int) -> bytes:
        image = await self._request(
            "GET", f"/api/img/cams/{index}", response_type="image"
        )
        return cast(bytes, image)

    async def open_camera_stream(self, index: int) -> aiohttp.ClientResponse:
        """The live MJPEG stream of one camera, which Board Manager 2 serves.

        The caller closes the response. Any answer other than multipart
        content counts as no stream.
        """
        try:
            response = await open_session(self._session).get(
                f"{self.base_url}/api/streams/cams/{index}",
                timeout=aiohttp.ClientTimeout(
                    total=None, sock_connect=10, sock_read=30
                ),
            )
        except (TimeoutError, aiohttp.ClientError) as err:
            raise AutodartsConnectionError("Unable to open the camera stream") from err
        content_type = response.headers.get("Content-Type", "")
        if response.status != 200 or not content_type.startswith("multipart/"):
            response.close()
            raise AutodartsConnectionError("No camera stream available")
        return response

    async def command(self, command: str) -> None:
        """Send an explicit user action once. Only missing routes permit fallback."""
        method, path = COMMANDS[command]
        async with self._command_lock:
            try:
                await self._request(
                    method,
                    path,
                    response_type="none",
                    timeout=60 if command == "calibrate" else 10,
                )
            except AutodartsEndpointMissing:
                if command not in ("start", "stop"):
                    raise
                await self._request(
                    method, f"/api/detection/{command}", response_type="none"
                )
            except AutodartsConnectionError as err:
                if command == "restart" and _dropped_after_sending(err.__cause__):
                    # Board Manager restarts before it finishes its answer.
                    return
                raise

    async def _write_setting(self, section: str, key: str, value: object) -> None:
        """Change one setting, in the spelling of the board.

        The board tells its spelling right before the write, because an update may
        have changed it since the last read. A setting it doesn't report is not
        written at all: nothing says what it would make of the key.
        """
        async with self._command_lock:
            settings = _dict((await self._object("/api/config")).get(section))
            spelled = _spelled(key, settings)
            if spelled is None:
                raise AutodartsEndpointMissing("Setting not supported by this board")
            await self._request(
                "PATCH",
                "/api/config",
                payload={section: {spelled: value}},
                response_type="none",
            )

    async def set_config_switch(self, key: str, enabled: bool) -> None:
        if key not in CONFIG_SWITCHES or not isinstance(enabled, bool):
            raise ValueError("Unsupported board setting")
        await self._write_setting("cam", key, enabled)

    async def set_standby_minutes(self, minutes: int) -> None:
        if minutes not in STANDBY_MINUTES:
            raise ValueError("Unsupported standby duration")
        await self._write_setting("motion", "standby_minutes", minutes)
