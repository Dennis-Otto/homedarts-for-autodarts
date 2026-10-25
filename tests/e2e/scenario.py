"""Drive a real Home Assistant instance against the Board Manager double.

Runs inside the Home Assistant container and uses only its public REST and
WebSocket APIs: onboarding, config flow, services, registries and diagnostics.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import socket
import time
from collections.abc import Awaitable
from pathlib import Path

import aiohttp
from board_mock import API_KEY, BOARD_ID, GENERATION, PORT, TLS_KEY, UPDATE, VERSION
from pictures import board_photo
from watchdog import within

HA = "http://127.0.0.1:8123"
BOARD = f"http://board-mock:{PORT}"
CLIENT_ID = f"{HA}/"
PASSWORD = "e2e-only-password"
LOG = Path("/config/home-assistant.log")
# The highlight gallery in the media folder of the Home Assistant container.
GALLERY = Path("/media/homedarts/highlights")
PHOTO = "2026-09-26_21-05-33_E2E Player_180.jpg"

# Darts as Board Manager 2.0 reports them, with the bed and normalized position.
T20 = {
    "segment": {"name": "T20", "number": 20, "multiplier": 3, "bed": "Triple"},
    "coords": {"x": 0.0123, "y": 0.5981},
}
S20 = {
    "segment": {"name": "S20", "number": 20, "multiplier": 1, "bed": "SingleOuter"},
    "coords": {"x": -0.021, "y": 0.781},
}
BULL = {
    "segment": {"name": "Bull", "number": 25, "multiplier": 2, "bed": "Double"},
    "coords": {"x": 0.004, "y": -0.011},
}


def dart(number: int, multiplier: int, bed: str, radius: float) -> dict:
    """A dart in a bed of the number, at a distance from the centre."""
    angle = math.radians(18 * SECTORS.index(number))
    name = f"{'SDT'[multiplier - 1]}{number}"
    return {
        "segment": {
            "name": name,
            "number": number,
            "multiplier": multiplier,
            "bed": bed,
        },
        "coords": {"x": radius * math.sin(angle), "y": radius * math.cos(angle)},
    }


SECTORS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
S1 = {
    "segment": {"name": "S1", "number": 1, "multiplier": 1, "bed": "SingleOuter"},
    "coords": {"x": 0.244, "y": 0.751},
}
D20 = {
    "segment": {"name": "D20", "number": 20, "multiplier": 2, "bed": "Double"},
    "coords": {"x": 0.0, "y": 0.976},
}
# 101 in one visit: 60, 1 and the double 20.
CHECKOUT_101 = [T20, S1, D20]
# Names that appear nowhere else, so diagnostics can be searched for them.
TOURNAMENT_PLAYERS = ["Anneliese", "Bertram", "Cordula"]
# Logged while the fault injection makes the board unavailable.
EXPECTED_LOGS = (
    "Board Manager does not answer",
    "realtime events at",
    # The online bridge explains an unknown trigger once.
    "The online bridge ignored the unknown event 'takeout'",
    # The WebSocket API logs the refused export of the reports step.
    "The export folder ../outside must not be hidden",
)
EXPECTED_TRACEBACKS = (
    "[custom_components.homedarts.local_coordinator] Full error:",
    # Home Assistant's own Assist reads the words of numbers from a file in the event
    # loop the first time a sentence of the voice blueprint has a number, and warns
    # about itself with a stack.
    "site-packages/unicode_rbnf/rbnf/",
    # Home Assistant 2026.10.0b0 imports its schema codec in the event loop the first
    # time a config flow answers, and warns about itself with a stack. Fixed upstream
    # by home-assistant/core#183909 for 2026.10.0; drop this once beta has it.
    "import_module with args ('probatio.codecs',)",
)
MANIFEST = Path("/config/custom_components/homedarts/manifest.json")
# Every file of the cards: both modules and the texts of each language in text/.
FRONTEND = MANIFEST.parent / "frontend"

# Unique ID suffix -> platform of the entities a three-camera board must create.
ENTITIES = {
    "local_connected": "binary_sensor",
    "realtime_connected": "binary_sensor",
    "camera_2_problem": "binary_sensor",
    "start": "button",
    "calibrate_camera_1": "button",
    "detection": "switch",
    "auto_calibrate_on_start": "switch",
    "auto_calibrate": "switch",
    "auto_distortion": "switch",
    "free_stuck_takeout": "switch",
    "standby_minutes": "select",
    "board_events": "event",
    "local_status": "sensor",
    "last_throw": "sensor",
    "num_throws": "sensor",
    "last_throw_score": "sensor",
    "local_visit_score": "sensor",
    "detection_fps": "sensor",
    "training_darts": "sensor",
    "training_triples": "sensor",
    "training_bulls": "sensor",
    "training_points": "sensor",
    "training_visits": "sensor",
    "training_average": "sensor",
    "training_highest_visit": "sensor",
    "training_session": "switch",
    "training_auto_start": "switch",
    "training_idle_timeout": "number",
    "training_last_session": "sensor",
    "practice_game": "select",
    "practice_double_out": "switch",
    "practice_new_leg": "button",
    "practice_remaining": "sensor",
    "practice_checkout": "sensor",
    "practice_target": "sensor",
    "correction_rate": "sensor",
    "personal_best": "sensor",
    "darts_today": "sensor",
    "training_streak": "sensor",
    "training_daily_goal": "number",
    "practice_double_in": "switch",
    "practice_bull_off": "switch",
    "player_profiles": "sensor",
    "last_match": "sensor",
    "favourite_double": "sensor",
    "practice_personal_routes": "switch",
    "practice_legs_played": "sensor",
    "practice_first_9_average": "sensor",
    "practice_players": "number",
    "practice_legs": "number",
    "practice_sets": "number",
    "practice_new_match": "button",
    "practice_player_1": "text",
    "practice_player_4": "text",
    "tournament": "sensor",
    "tournament_format": "select",
    "tournament_game": "select",
    "tournament_players": "text",
    "tournament_groups": "number",
    "tournament_advance": "number",
    "tournament_pause": "number",
    "tournament_third_place": "switch",
    "tournament_random_draw": "switch",
    "tournament_start": "button",
    "tournament_next_match": "button",
    "tournament_stop": "button",
    "weekly_report": "sensor",
    "weekly_report_day": "select",
    "weekly_report_time": "time",
    "training_calendar": "calendar",
    "practice_teams": "switch",
    "practice_start_1": "number",
    "practice_start_4": "number",
    "practice_golf_holes": "select",
    "practice_count_up_rounds": "number",
    "practice_in_mode": "select",
    "practice_out_mode": "select",
    "practice_bull_mode": "select",
    "practice_max_rounds": "number",
    "achievements": "sensor",
    "achievements_enabled": "switch",
}
if GENERATION >= 2:
    # Board Manager 2 reports its cloud link, load and updates, and has no toggle.
    ENTITIES |= {
        "cloud_link": "binary_sensor",
        "cpu_usage": "sensor",
        "memory_usage": "sensor",
        "board_software": "update",
    }
    DISABLED_BY_DEFAULT = {"detection_fps", "cpu_usage", "memory_usage"}
    ABSENT = {"upstream", "connect", "disconnect"}
else:
    ENTITIES |= {"connect": "button", "upstream": "switch"}
    DISABLED_BY_DEFAULT = {"connect", "detection_fps"}
    ABSENT = {"cloud_link", "cpu_usage", "memory_usage", "board_software"}


class E2EFailure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise E2EFailure(message)


async def wait_for(probe, description: str, timeout: float = 30):
    """Poll an async probe until it returns a truthy value."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = await probe()
        if last:
            return last
        await asyncio.sleep(0.5)
    raise E2EFailure(f"Timed out waiting for {description}; last result: {last!r}")


class Scenario:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session
        self.headers: dict[str, str] = {}
        self.entities: dict[str, str] = {}
        self.socket: aiohttp.ClientWebSocketResponse | None = None
        self.message_id = 0
        self.pending: dict[int, asyncio.Future] = {}
        self.events: asyncio.Queue = asyncio.Queue()
        self.reader: asyncio.Task | None = None
        # Discovery stores the announced address instead of the service name.
        self.board_ip = socket.gethostbyname("board-mock")
        self.webhook_id: str | None = None
        self.device_id = ""

    async def http(self, method: str, url: str, *, status: int = 200, **kwargs):
        async with self.session.request(
            method, url, headers=self.headers, **kwargs
        ) as response:
            body = await response.text()
            check(
                response.status == status,
                f"{method} {url}: expected HTTP {status}, got {response.status}: {body}",
            )
            return json.loads(body) if body else None

    async def api(self, method: str, path: str, **kwargs):
        return await self.http(method, f"{HA}{path}", **kwargs)

    async def board(self, method: str, path: str, **kwargs):
        return await self.http(method, f"{BOARD}{path}", **kwargs)

    # Authentication and WebSocket API

    async def onboard(self) -> None:
        created = await self.api(
            "POST",
            "/api/onboarding/users",
            json={
                "client_id": CLIENT_ID,
                "name": "E2E Admin",
                "username": "e2e-admin",
                "password": PASSWORD,
                "language": "en",
            },
        )
        token = await self.api(
            "POST",
            "/auth/token",
            data={
                "grant_type": "authorization_code",
                "code": created["auth_code"],
                "client_id": CLIENT_ID,
            },
        )
        self.headers = {"Authorization": f"Bearer {token['access_token']}"}

        async def running():
            # Onboarding answers before every configured integration has loaded.
            async with self.session.get(
                f"{HA}/api/config", headers=self.headers
            ) as response:
                return (
                    response.status == 200
                    and (await response.json())["state"] == "RUNNING"
                )

        await wait_for(running, "Home Assistant to finish starting", timeout=120)
        # Complete onboarding like a user, so the regular dashboards are served.
        await self.api("POST", "/api/onboarding/core_config")
        await self.api("POST", "/api/onboarding/analytics")
        await self.api(
            "POST",
            "/api/onboarding/integration",
            json={
                "client_id": CLIENT_ID,
                "redirect_uri": f"{CLIENT_ID}?auth_callback=1",
            },
        )

    async def connect(self) -> None:
        self.socket = await self.session.ws_connect(f"{HA}/api/websocket")
        check(
            (await self.socket.receive_json())["type"] == "auth_required",
            "WebSocket API did not request authentication",
        )
        await self.socket.send_json(
            {
                "type": "auth",
                "access_token": self.headers["Authorization"].removeprefix("Bearer "),
            }
        )
        check(
            (await self.socket.receive_json())["type"] == "auth_ok",
            "WebSocket authentication failed",
        )
        self.reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        async for message in self.socket:
            payload = message.json()
            if payload["type"] == "event":
                self.events.put_nowait(payload["event"])
            elif future := self.pending.pop(payload["id"], None):
                future.set_result(payload)

    async def ws_result(self, command: str, **payload) -> dict:
        self.message_id += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[self.message_id] = future
        await self.socket.send_json({"id": self.message_id, "type": command, **payload})
        return await asyncio.wait_for(future, 30)

    async def ws(self, command: str, **payload):
        result = await self.ws_result(command, **payload)
        check(result["success"], f"{command} failed: {result.get('error')}")
        return result["result"]

    async def caught_up(self) -> None:
        """Wait until the WebSocket brought the events fired before this call.

        The states come over REST and the events over the WebSocket, and the
        integration fires an event just after it wrote the states that go with it.
        A state can therefore show a change before its event arrived here. Home
        Assistant answers a ping on the WebSocket after the events it sent before.
        """
        if self.socket is not None:
            await self.ws_result("ping")

    # Home Assistant helpers

    def entity(self, key: str) -> str:
        return self.entities[f"{BOARD_ID}_{key}"]

    async def state(self, key: str) -> dict:
        return await self.api("GET", f"/api/states/{self.entity(key)}")

    async def expect_states(self, expected: dict[str, str], timeout: float = 30):
        async def probe():
            actual = {key: (await self.state(key))["state"] for key in expected}
            return actual == expected or None

        try:
            await wait_for(probe, f"states {expected}", timeout)
        except E2EFailure:
            actual = {key: (await self.state(key))["state"] for key in expected}
            raise E2EFailure(f"Expected {expected}, got {actual}") from None
        # The events of these states, for the checks that read them next.
        await self.caught_up()

    async def service(self, domain: str, service: str, key: str, **data) -> None:
        await self.api(
            "POST",
            f"/api/services/{domain}/{service}",
            json={"entity_id": self.entity(key), **data},
        )

    async def entry_is(self, state: str) -> bool:
        entries = await self.api(
            "GET", "/api/config/config_entries/entry?domain=homedarts"
        )
        return len(entries) == 1 and entries[0]["state"] == state

    async def flow(self, flow_id: str | None = None, **data) -> dict:
        if flow_id is None:
            return await self.api(
                "POST", "/api/config/config_entries/flow", json={"handler": "homedarts"}
            )
        return await self.api(
            "POST", f"/api/config/config_entries/flow/{flow_id}", json=data
        )

    async def local_flow(self, host: str, port: int) -> dict:
        menu = await self.flow()
        check(
            menu["type"] == "menu"
            and menu["menu_options"] == ["discover", "local", "granboard", "manual"],
            f"Unexpected setup menu: {menu}",
        )
        form = await self.flow(menu["flow_id"], next_step_id="local")
        check(form["step_id"] == "local", f"Local setup form missing: {form}")
        return await self.flow(form["flow_id"], host=host, port=port)

    # Scenario steps

    async def setup(self) -> str:
        result = await self.local_flow("http://board-mock", PORT)
        check(result["errors"] == {"host": "invalid_host"}, f"URL accepted: {result}")
        result = await self.local_flow("board-mock", PORT + 1)
        check(
            result["errors"] == {"base": "cannot_connect_local"},
            f"Closed port accepted: {result}",
        )
        if GENERATION >= 2:
            result = await self.discovered_setup()
        else:
            result = await self.local_flow("Board-Mock", PORT)
            check(
                result["title"] == "Autodarts (board-mock)",
                f"Title: {result['title']}",
            )
        check(result["type"] == "create_entry", f"Local setup failed: {result}")
        entry_id = result["result"]["entry_id"]

        # The same board at the address of its entry; a new address would be
        # taken over instead (address_updated, see test_discovery.py).
        stored = self.board_ip if GENERATION >= 2 else "board-mock"
        duplicate = await self.local_flow(stored, PORT)
        check(
            duplicate.get("reason") == "already_configured",
            f"Second entry for the same board was not rejected: {duplicate}",
        )

        await wait_for(lambda: self.entry_is("loaded"), "the config entry to load")
        return entry_id

    async def discovered_setup(self) -> dict:
        """Home Assistant finds the announced Board Manager 2 on its own."""

        async def announced():
            flows = await self.ws("config_entries/flow/progress")
            return next(
                (
                    flow
                    for flow in flows
                    if flow["handler"] == "homedarts"
                    and flow["context"].get("source") == "zeroconf"
                ),
                None,
            )

        flow = await wait_for(announced, "the mDNS announcement to be discovered", 60)
        check(flow["step_id"] == "zeroconf_confirm", f"Discovery flow: {flow}")
        result = await self.api(
            "GET", f"/api/config/config_entries/flow/{flow['flow_id']}"
        )
        check(result["step_id"] == "zeroconf_confirm", f"Discovery form: {result}")
        placeholders = result["description_placeholders"]
        check(
            placeholders["version"] == VERSION and placeholders["cameras"] == "3",
            f"Discovery details: {placeholders}",
        )
        return await self.flow(flow["flow_id"])

    async def registries(self, entry_id: str) -> None:
        registered: dict[str, dict] = {}

        async def discovered():
            registered.clear()
            for item in await self.ws("config/entity_registry/list"):
                if item["config_entry_id"] == entry_id:
                    registered[item["unique_id"]] = item
            return all(f"{BOARD_ID}_{key}" in registered for key in ENTITIES)

        await wait_for(discovered, "all local entities, including discovered cameras")
        for key, platform in ENTITIES.items():
            item = registered[f"{BOARD_ID}_{key}"]
            check(item["platform"] == "homedarts", f"{key}: wrong integration")
            check(
                item["entity_id"].startswith(f"{platform}."),
                f"{key}: expected {platform}, got {item['entity_id']}",
            )
            disabled = item["disabled_by"] == "integration"
            check(
                disabled == (key in DISABLED_BY_DEFAULT),
                f"{key}: unexpected disabled_by {item['disabled_by']!r}",
            )
        unexpected = {f"{BOARD_ID}_{key}" for key in ABSENT} & set(registered)
        check(not unexpected, f"Entities of the other generation: {unexpected}")
        self.entities = {
            unique_id: item["entity_id"] for unique_id, item in registered.items()
        }

        devices = [
            device
            for device in await self.ws("config/device_registry/list")
            if ["homedarts", BOARD_ID] in device["identifiers"]
        ]
        check(len(devices) == 1, f"Expected one board device, got {devices}")
        device = devices[0]
        self.device_id = device["id"]
        check(device["sw_version"] == VERSION, f"Firmware: {device['sw_version']}")
        check(
            device["configuration_url"] in (BOARD, f"http://{self.board_ip}:{PORT}"),
            f"Configuration URL: {device['configuration_url']}",
        )

    async def initial_state(self) -> None:
        expected = {
            "local_connected": "on",
            "realtime_connected": "on",
            "detection": "off",
            "auto_calibrate_on_start": "on",
            "auto_calibrate": "on",
            "auto_distortion": "off",
            "free_stuck_takeout": "on",
            "standby_minutes": "15",
            "local_status": "stopped",
            "training_darts": "0",
        }
        if GENERATION >= 2:
            expected |= {"cloud_link": "on", "board_software": "on"}
        else:
            expected |= {"upstream": "on"}
        await self.expect_states(expected)
        if GENERATION >= 2:
            update = await self.state("board_software")
            versions = (
                update["attributes"]["installed_version"],
                update["attributes"]["latest_version"],
            )
            check(versions == (VERSION, UPDATE), f"Update versions: {versions}")

    async def controls(self) -> None:
        await self.service("button", "press", "start")
        await self.expect_states({"detection": "on", "local_status": "throw"})
        await self.service("switch", "turn_on", "auto_distortion")
        await self.expect_states({"auto_distortion": "on"})
        await self.service("select", "select_option", "standby_minutes", option="30")
        await self.expect_states({"standby_minutes": "30"})
        await self.service("button", "press", "calibrate_camera_1")
        if GENERATION < 2:
            await self.service("switch", "turn_off", "upstream")
            await self.expect_states({"upstream": "off"})
            await self.service("switch", "turn_on", "upstream")
            await self.expect_states({"upstream": "on"})

        board = await self.board("GET", "/control/requests")
        expected = [
            {"method": "PUT", "path": "/api/start", "body": None},
            {
                "method": "PATCH",
                "path": "/api/config",
                "body": {"cam": {"auto_distortion": True}},
            },
            {
                "method": "PATCH",
                "path": "/api/config",
                "body": {"motion": {"standby_minutes": 30}},
            },
            {
                "method": "POST",
                "path": "/api/config/calibration/auto/1?distortion=true",
                "body": None,
            },
        ]
        if GENERATION < 2:
            expected += [
                {"method": "PUT", "path": "/api/upstream/disconnect", "body": None},
                {"method": "PUT", "path": "/api/upstream/connect", "body": None},
            ]
        check(
            board["commands"] == expected,
            f"Board commands differ:\n{json.dumps(board['commands'], indent=2)}",
        )

    async def realtime(self, entry_id: str) -> None:
        # Without polling, every following change must arrive over the board socket.
        await self.ws(
            "config_entries/update", entry_id=entry_id, pref_disable_polling=True
        )
        await wait_for(
            lambda: self.entry_is("loaded"), "the reloaded entry without polling"
        )
        await self.expect_states({"realtime_connected": "on", "detection": "on"})
        await self.service("select", "select_option", "practice_game", option="301")
        await self.expect_states({"practice_game": "301", "practice_remaining": "301"})
        await self.ws("subscribe_events", event_type="state_changed")

        await self.board(
            "POST", "/control/state", json={"event": "Throw detected", "throws": [T20]}
        )
        await self.expect_states({"last_throw": "T20", "last_throw_score": "60"})
        await self.board("POST", "/control/state", json={"throws": [T20, BULL]})
        await self.expect_states(
            {"last_throw": "Bull", "local_visit_score": "110", "num_throws": "2"}
        )
        throws = (await self.state("local_visit_score"))["attributes"]["throws"]
        check(
            throws
            == [
                {
                    "segment": "T20",
                    "number": 20,
                    "multiplier": 3,
                    "score": 60,
                    "bed": "Triple",
                    "x": 0.012,
                    "y": 0.598,
                    "dart": 1,
                },
                {
                    "segment": "Bull",
                    "number": 25,
                    "multiplier": 2,
                    "score": 50,
                    "bed": "Double",
                    "x": 0.004,
                    "y": -0.011,
                    "dart": 2,
                },
            ],
            f"Unexpected dart details for the dashboard card: {throws}",
        )
        await self.board(
            "POST",
            "/control/state",
            json={"event": "Dart corrected", "throws": [S20, BULL]},
        )
        await self.expect_states({"local_visit_score": "70"})
        await self.board(
            "POST",
            "/control/state",
            json={"status": "Takeout in progress", "event": "Takeout started"},
        )
        await self.board(
            "POST",
            "/control/state",
            json={"status": "Throw", "event": "Takeout finished", "throws": []},
        )
        await self.expect_states(
            {
                "num_throws": "0",
                "local_visit_score": "0",
                "training_darts": "2",
                "training_triples": "0",
                "training_bulls": "1",
                "training_points": "70",
                "training_visits": "1",
                "training_highest_visit": "70",
                "training_average": "105.0",
                "practice_remaining": "231",
            }
        )
        hits = (await self.state("training_darts"))["attributes"]["hits"]
        check(hits == {"BULL": 1, "S20": 1}, f"Unexpected hits for the heatmap: {hits}")

        fired = self.fired_board_events()
        board_events = [
            (
                item["event_type"],
                item.get("segment"),
                item.get("score"),
                item.get("status"),
            )
            for item in fired
        ]
        check(
            board_events
            == [
                ("dart_detected", "T20", 60, None),
                ("dart_detected", "Bull", 50, None),
                ("dart_corrected", "S20", 20, None),
                ("status_changed", None, None, "Takeout in progress"),
                ("takeout_started", None, None, None),
                ("visit_completed", None, 70, None),
                # The practice game announces the next visit.
                ("turn_changed", None, None, None),
                ("status_changed", None, None, "Throw"),
                ("takeout_finished", None, None, None),
            ],
            f"Unexpected board events: {fired}",
        )
        check(
            all(item["source"] == "websocket" for item in fired),
            f"Events did not arrive in realtime: {fired}",
        )

        store = Path(f"/config/.storage/homedarts.{entry_id}.training")

        async def persisted():
            if not store.exists():
                return None
            return json.loads(store.read_text())["data"]["darts"] == 2

        await wait_for(persisted, "the persisted training session", timeout=20)

    def fired_board_events(self) -> list[dict]:
        """Attributes of the board events since the last call, in order."""
        fired = []
        while not self.events.empty():
            event = self.events.get_nowait()["data"]
            if event["entity_id"] == self.entity("board_events") and event["new_state"]:
                fired.append(event["new_state"]["attributes"])
        return fired

    def state_changes(self, key: str) -> list[str]:
        """States an entity passed through since the events were last read."""
        changes = []
        while not self.events.empty():
            data = self.events.get_nowait()["data"]
            if data["entity_id"] == self.entity(key) and data["new_state"]:
                changes.append(data["new_state"]["state"])
        return changes

    async def fault(self, **fault) -> None:
        await self.board("POST", "/control/fault", json=fault)

    async def faulted_reads(self, path: str) -> None:
        """Wait until the board used up its counted faults and was read twice more.

        Polls never overlap, so the second read after the faults shows that Home
        Assistant has handled every faulted read and the first good one after them.
        """

        async def used_up():
            requests = await self.board("GET", "/control/requests")
            return requests if requests["faults_left"] == 0 else None

        requests = await wait_for(used_up, f"the faulted reads of {path}", timeout=60)
        reads = requests["reads"].get(path, 0)

        async def read_again():
            requests = await self.board("GET", "/control/requests")
            return requests["reads"].get(path, 0) >= reads + 2 or None

        await wait_for(read_again, f"two reads of {path} after the faults", timeout=60)

    async def resilience(self, entry_id: str) -> None:
        """Faults of a real network and board: visits and entities survive them."""
        # Polling is back, as it notices a board that is away.
        await self.ws(
            "config_entries/update", entry_id=entry_id, pref_disable_polling=False
        )
        await wait_for(lambda: self.entry_is("loaded"), "the entry with polling")
        await self.expect_states({"realtime_connected": "on", "local_connected": "on"})
        self.fired_board_events()

        # 1. The socket drops mid-visit; polling finds the second dart meanwhile.
        await self.board("POST", "/control/state", json={"throws": [T20]})
        await self.expect_states({"last_throw": "T20"})
        await self.fault(drop_sockets=True, refuse_sockets=True)
        await self.expect_states({"realtime_connected": "off"})
        await self.board("POST", "/control/state", json={"throws": [T20, T20]})
        await self.expect_states({"num_throws": "2", "local_visit_score": "120"})
        await self.fault(refuse_sockets=False)
        await self.expect_states({"realtime_connected": "on"}, timeout=90)
        await self.board("POST", "/control/state", json={"throws": []})
        await self.expect_states({"practice_remaining": "111", "training_darts": "4"})
        visit = [
            (item["event_type"], item.get("dart_index"), item["source"])
            for item in self.fired_board_events()
            if item["event_type"] in ("dart_detected", "visit_completed")
        ]
        check(
            [item[:2] for item in visit]
            == [("dart_detected", 1), ("dart_detected", 2), ("visit_completed", None)]
            and visit[1][2] == "poll",
            f"The visit did not survive the dropped socket: {visit}",
        )

        # 2. The board is away while its darts are pulled and one is thrown again.
        await self.board("POST", "/control/state", json={"throws": [S20]})
        await self.expect_states({"last_throw": "S20"})
        await self.fault(drop_sockets=True, refuse_sockets=True, http_status=503)
        # Two missed polls are a hiccup; the third makes the board unavailable.
        await self.expect_states(
            {"local_connected": "off", "detection": "unavailable"}, timeout=40
        )
        # The board events stay available for the events of Home Assistant itself.
        events = await self.state("board_events")
        check(events["state"] != "unavailable", f"Board events: {events}")
        await self.board("POST", "/control/state", json={"throws": []})
        await self.board("POST", "/control/state", json={"throws": [BULL]})
        await self.fault(clear=True)
        # The visit ended during the outage; the dart after it is not counted.
        await self.expect_states(
            {
                "local_connected": "on",
                "last_throw": "Bull",
                "practice_remaining": "91",
                "training_darts": "5",
            },
            timeout=40,
        )
        await self.expect_states({"realtime_connected": "on"}, timeout=90)
        completed = [
            item
            for item in self.fired_board_events()
            if item["event_type"] == "visit_completed"
        ]
        check(
            [(item["score"], item["segments"]) for item in completed]
            == [(20, ["S20"])],
            f"The visit of the outage was not completed once: {completed}",
        )
        await self.board("POST", "/control/state", json={"throws": []})
        await self.expect_states({"num_throws": "0", "training_darts": "5"})

        # 3. Failing and slow reads for a few seconds are no outage.
        await self.fault(drop_sockets=True, refuse_sockets=True)
        await self.expect_states({"realtime_connected": "off"})
        self.fired_board_events()
        await self.fault(http_status=503, paths=["/api/state"], count=2)
        await self.faulted_reads("/api/state")
        # Longer than the ten seconds a read may take.
        await self.fault(delay=11, paths=["/api/state"], count=1)
        await self.faulted_reads("/api/state")
        await self.expect_states({"local_connected": "on"})
        check(
            "off" not in self.state_changes("local_connected"),
            "A few failed reads made the board unavailable",
        )
        await self.fault(clear=True)
        await self.expect_states({"realtime_connected": "on"}, timeout=90)

        # 4. Malformed frames are skipped; the next notification works.
        for frame in (
            "not json",
            '{"type":"state","data":{"running":"yes","throws":[]}}',
            '{"type":"cam_stats","data":{"id":9,"fps":NaN}}',
        ):
            await self.fault(frame=frame)
        await self.fault(binary=True)
        await self.board("POST", "/control/state", json={"throws": [T20]})
        await self.expect_states({"last_throw": "T20", "practice_remaining": "31"})
        await self.board("POST", "/control/state", json={"throws": []})
        await self.expect_states({"training_darts": "6"})

        # 5. The Board Manager restarts: away for a few seconds, then back.
        await self.fault(restart=3)
        await self.expect_states({"realtime_connected": "off"})
        await self.expect_states(
            {"realtime_connected": "on", "local_connected": "on"}, timeout=90
        )
        report = await self.api("GET", f"/api/diagnostics/config_entry/{entry_id}")
        realtime = report["data"]["connection"]["realtime"]
        check(
            realtime["ignored_frames"] >= 2 and realtime["connects"] >= 4,
            f"Diagnostics do not show the faults: {realtime}",
        )

        # 6. The board keeps a takeout on the empty board, as Board Manager 2.0.2
        # sometimes does: after ten seconds, a reset frees it and the takeout ends.
        self.fired_board_events()
        await self.fault(stuck_takeout=True)
        await self.expect_states({"local_status": "takeout_in_progress"})

        async def freed():
            requests = await self.board("GET", "/control/requests")
            return [
                command
                for command in requests["commands"]
                if command["path"] == "/api/reset"
            ] or None

        resets = await wait_for(freed, "the reset of the stuck takeout", timeout=40)
        await self.expect_states({"local_status": "throw", "num_throws": "0"})
        takeouts = [
            item["event_type"]
            for item in self.fired_board_events()
            if item["event_type"] in ("takeout_started", "takeout_finished")
        ]
        check(
            len(resets) == 1 and takeouts == ["takeout_started", "takeout_finished"],
            f"The stuck takeout did not end once: {resets}, {takeouts}",
        )
        report = await self.api("GET", f"/api/diagnostics/config_entry/{entry_id}")
        stuck = report["data"]["connection"]["stuck_takeout"]
        check(
            stuck["resets"] == 1 and not stuck["waiting"],
            f"Diagnostics do not show the reset of the stuck takeout: {stuck}",
        )

    async def options(
        self, flow_id: str | None = None, entry_id: str | None = None, **data
    ) -> dict:
        if flow_id is None:
            return await self.api(
                "POST",
                "/api/config/config_entries/options/flow",
                json={"handler": entry_id},
            )
        return await self.api(
            "POST", f"/api/config/config_entries/options/flow/{flow_id}", json=data
        )

    async def bridge_sensor(self) -> str | None:
        for item in await self.ws("config/entity_registry/list"):
            if item["unique_id"] == f"{BOARD_ID}_online_bridge_last_event":
                return item["entity_id"]
        return None

    async def webhook(self, method: str, path: str, **kwargs) -> tuple[int, str]:
        """A call as Tools for Autodarts makes it: no login, no JSON content type."""
        async with self.session.request(method, f"{HA}{path}", **kwargs) as response:
            return response.status, await response.text()

    async def online_bridge(self, entry_id: str) -> None:
        """Moments of an online match arrive through the webhook of the options."""
        form = await self.options(entry_id=entry_id)
        check(form["step_id"] == "init", f"Unexpected options: {form}")
        shown = await self.options(
            form["flow_id"], online_bridge=True, online_bridge_remote=False
        )
        check(shown["step_id"] == "online_bridge", f"No bridge address: {shown}")
        url = shown["description_placeholders"]["url"]
        webhook_id = url.rsplit("/", 1)[1]
        check(re.fullmatch("[0-9a-f]{64}", webhook_id) is not None, f"Address: {url}")
        effects = shown["description_placeholders"]["effects"].splitlines()
        check(
            f"Home Assistant: 180;URL;{url}?event=180;180" in effects,
            f"Unexpected effects to import: {effects}",
        )
        done = await self.options(shown["flow_id"])
        check(done["type"] == "create_entry", f"Options were not saved: {done}")
        self.webhook_id = webhook_id
        sensor = await wait_for(self.bridge_sensor, "the online bridge sensor", 60)
        self.entities[f"{BOARD_ID}_online_bridge_last_event"] = sensor
        await self.expect_states(
            {"online_bridge_last_event": "unknown", "realtime_connected": "on"},
            timeout=90,
        )
        self.fired_board_events()

        path = f"/api/webhook/{webhook_id}"
        answers = [
            await self.webhook("GET", f"{path}?event=180"),
            await self.webhook(
                "POST",
                path,
                data='{"event": "busted", "player": "Lea"}',
                headers={"Content-Type": "text/plain;charset=UTF-8"},
            ),
            await self.webhook("GET", f"{path}?event=takeout"),
        ]
        check(
            answers == [(200, "ok"), (200, "ok"), (400, "unknown event")],
            f"Unexpected webhook answers: {answers}",
        )
        fired: list[dict] = []

        async def arrived():
            fired.extend(
                item
                for item in self.fired_board_events()
                if item.get("event_type", "").startswith("online_")
            )
            return len(fired) >= 2

        await wait_for(arrived, "the online board events")
        check(
            [
                (item["event_type"], item.get("score"), item.get("name"))
                for item in fired
            ]
            == [("online_visit", 180, None), ("online_busted", None, "Lea")]
            and all(item["source"] == "online" for item in fired),
            f"Unexpected online events: {fired}",
        )
        last = await self.state("online_bridge_last_event")
        check(
            last["state"] not in ("unknown", "unavailable")
            and last["attributes"]["trigger"] == "busted",
            f"Unexpected last event: {last}",
        )
        report = await self.api("GET", f"/api/diagnostics/config_entry/{entry_id}")
        check(
            webhook_id not in json.dumps(report),
            "Diagnostics expose the webhook address",
        )
        summary = report["data"]["online_bridge"]
        check(
            summary["events"] == 2 and summary["invalid"] == 1,
            f"Unexpected bridge diagnostics: {summary}",
        )

        # Switched off, the address answers like any unknown one. The reloaded
        # event entity restores its last event, which is not a new one.
        last_event = (await self.state("board_events"))["state"]
        form = await self.options(entry_id=entry_id)
        done = await self.options(
            form["flow_id"],
            online_bridge=False,
            online_bridge_remote=False,
            online_bridge_new_address=False,
        )
        check(done["type"] == "create_entry", f"Options were not saved: {done}")

        async def removed():
            return await self.bridge_sensor() is None

        await wait_for(removed, "the online bridge sensor to be removed", 60)
        del self.entities[f"{BOARD_ID}_online_bridge_last_event"]
        answer = await self.webhook("GET", f"{path}?event=180")
        check(answer == (200, ""), f"The switched-off bridge answered: {answer}")
        await self.expect_states({"realtime_connected": "on"}, timeout=90)
        new_online_events = []
        while not self.events.empty():
            data = self.events.get_nowait()["data"]
            new = data["new_state"]
            if (
                data["entity_id"] == self.entity("board_events")
                and new
                and new["state"] != last_event
                and new["attributes"].get("event_type", "").startswith("online_")
            ):
                new_online_events.append(new["attributes"])
        check(
            not new_online_events,
            f"The switched-off bridge fired events: {new_online_events}",
        )

    async def call(self, domain: str, service: str, **data) -> dict:
        """An action with its response, over the WebSocket API like the cards."""
        result = await self.ws(
            "call_service",
            domain=domain,
            service=service,
            return_response=True,
            **data,
        )
        return result["response"]

    async def refused(self, command: str, **payload) -> dict:
        """A command that must fail, with the error it reports."""
        self.message_id += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[self.message_id] = future
        await self.socket.send_json({"id": self.message_id, "type": command, **payload})
        result = await asyncio.wait_for(future, 30)
        check(not result["success"], f"{command} did not fail: {result}")
        return result["error"]

    async def download(self, path: str, headers: dict[str, str]) -> tuple[int, str]:
        async with self.session.get(f"{HA}{path}", headers=headers) as response:
            return response.status, await response.text(encoding="utf-8-sig")

    async def reports(self, entry_id: str) -> None:
        """Weekly report, training calendar and exports over the real API."""
        await self.expect_states(
            {"weekly_report_day": "monday", "weekly_report_time": "00:00:00"}
        )
        # The week counts every dart so far; the session started with the first.
        training = {
            key: (await self.state(f"training_{key}"))["state"]
            for key in ("darts", "visits", "average")
        }
        report = await self.state("weekly_report")
        attributes = report["attributes"]
        check(
            (report["state"], str(attributes["visits"]), str(attributes["average"]))
            == (training["darts"], training["visits"], training["average"])
            and attributes["last_week"] is None,
            f"The weekly report {report} differs from the session {training}",
        )
        await self.service(
            "select", "select_option", "weekly_report_day", option="sunday"
        )
        await self.service("time", "set_value", "weekly_report_time", time="20:30:00")
        await self.expect_states(
            {"weekly_report_day": "sunday", "weekly_report_time": "20:30:00"}
        )

        # A new session ends the one with the darts of the earlier steps.
        await self.service("button", "press", "reset_training")
        calendar = self.entity("training_calendar")
        period = {
            "start_date_time": time.strftime(
                "%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() - 86400)
            ),
            "end_date_time": time.strftime(
                "%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() + 3600)
            ),
        }

        async def listed():
            events = (
                await self.call(
                    "calendar",
                    "get_events",
                    service_data=period,
                    target={"entity_id": calendar},
                )
            )[calendar]["events"]
            return events or None

        events = await wait_for(listed, "the finished session in the calendar")
        darts, average = int(training["darts"]), float(training["average"])
        check(
            [event["summary"] for event in events]
            == [f"Training · {darts} Darts · Ø {average:.1f}"],
            f"Unexpected training calendar: {events}",
        )

        export = await self.call(
            "homedarts", "export", service_data={"format": "json", "what": "all"}
        )
        name = Path(export["path"]).name
        # By default in the media folder, which needs a login: no /local/ address.
        check(
            export["path"] == f"/media/homedarts/exports/{name}"
            and name.startswith("homedarts-all-")
            and export["url"] is None
            and export["download"] == f"/api/homedarts/export/{name}"
            and export["rows"] == {"sessions": 1, "matches": 0, "profiles": 0},
            f"Unexpected export: {export}",
        )
        status, body = await self.download(export["download"], self.headers)
        check(status == 200, f"Export download failed: HTTP {status}")
        sessions = json.loads(body)["sessions"]
        check(
            [(item["darts"], item["average"]) for item in sessions]
            == [(darts, average)],
            f"Unexpected exported sessions: {sessions}",
        )
        status, _ = await self.download(export["download"], {})
        check(status == 401, f"Export downloadable without login: HTTP {status}")
        # The players card downloads with a signed path, as a browser link does.
        signed = await self.ws("auth/sign_path", path=export["download"], expires=60)
        status, _ = await self.download(signed["path"], {})
        check(status == 200, f"Signed export download failed: HTTP {status}")

        # On request in www, which Home Assistant serves at /local/.
        export = await self.call(
            "homedarts",
            "export",
            service_data={"what": "sessions", "folder": "www/homedarts"},
        )
        name = Path(export["path"]).name
        check(
            export["path"] == f"/config/www/homedarts/{name}"
            and export["url"] == f"/local/homedarts/{name}",
            f"Unexpected export to www: {export}",
        )
        status, body = await self.download(export["download"], self.headers)
        check(
            status == 200 and body.splitlines()[0].startswith("started,ended,"),
            f"Unexpected CSV export: HTTP {status} {body[:200]}",
        )
        error = await self.refused(
            "call_service",
            domain="homedarts",
            service="export",
            service_data={"folder": "../outside"},
            return_response=True,
        )
        check(
            error["code"] == "service_validation_error",
            f"An export outside the configuration folder was not refused: {error}",
        )

        store = Path(f"/config/.storage/homedarts.{entry_id}.journal")

        async def persisted():
            if not store.exists():
                return None
            return len(json.loads(store.read_text())["data"]["sessions"]) == 1 or None

        await wait_for(persisted, "the persisted training journal", timeout=30)

    async def start_game(self, **data) -> None:
        await self.api("POST", "/api/services/homedarts/start_game", json=data)

    async def visit(self, *darts: dict) -> None:
        """Throw a visit and pull the darts."""
        await self.board("POST", "/control/state", json={"throws": list(darts)})
        await self.expect_states({"num_throws": str(len(darts))})
        await self.board("POST", "/control/state", json={"throws": []})
        await self.expect_states({"num_throws": "0"})

    async def events_until(self, kind: str) -> list[dict]:
        """The board events until one of this kind arrived."""
        fired: list[dict] = []

        async def arrived():
            fired.extend(self.fired_board_events())
            return any(item["event_type"] == kind for item in fired)

        await wait_for(arrived, f"a {kind} event")
        return fired

    async def games(self) -> None:
        """New games, a team match and start scores, set up with the action."""
        self.fired_board_events()
        # Golf alone: nine holes, and the last dart of a visit counts.
        await self.start_game(game="golf", players=["Alex"], holes=9)
        await self.expect_states({"practice_game": "golf", "practice_target": "1"})
        # An inner single is three strokes: the board's position tells the bed.
        await self.visit(dart(1, 1, "SingleInner", 0.35))
        await self.visit(dart(2, 3, "Triple", 0.6), dart(2, 1, "SingleOuter", 0.8))
        # A treble is two strokes, a double one.
        for hole in range(3, 10):
            await self.visit(dart(hole, 3, "Triple", 0.6))
        won = [
            item
            for item in await self.events_until("leg_won")
            if item["event_type"] == "leg_won"
        ]
        check(
            [(item["game"], item["points"], item["darts"]) for item in won]
            == [("golf", 3 + 4 + 14, 10)],
            f"Unexpected end of the Golf leg: {won}",
        )

        # Tactics for two: the numbers go down to 10.
        await self.start_game(game="tactics", players=["Alex", "Sam"])
        await self.expect_states({"practice_game": "tactics", "practice_target": "T20"})
        await self.visit(dart(10, 3, "Triple", 0.6), dart(10, 3, "Triple", 0.6))
        game = (await self.state("practice_remaining"))["attributes"]
        check(
            len(game["numbers"]) == 12
            and [score["points"] for score in game["scores"]] == [30, 0]
            and game["scores"][0]["marks"][10] == 3
            and game["player"] == 2,
            f"Unexpected Tactics chalkboard: {game}",
        )

        # Two teams of two, the second team from 201.
        await self.start_game(
            game="301",
            players=["Alex", "Sam", "Kim", "Lea"],
            teams=True,
            start_scores=[0, 201],
        )
        await self.expect_states({"practice_teams": "on", "practice_start_2": "201"})
        self.fired_board_events()
        await self.visit(T20)
        game = (await self.state("practice_remaining"))["attributes"]
        check(
            [score["remaining"] for score in game["scores"]] == [241, 201, 241, 201]
            and [team["name"] for team in game["teams"]] == ["Alex & Kim", "Sam & Lea"],
            f"Unexpected team match: {game}",
        )
        turns = [
            (item["player"], item.get("team"), item.get("team_name"))
            for item in await self.events_until("turn_changed")
            if item["event_type"] == "turn_changed"
        ]
        check(turns == [(2, 2, "Sam & Lea")], f"Unexpected turn: {turns}")
        await self.start_game(
            game="501", players=["Alex"], teams=False, start_scores=[]
        )

    async def achievements(self) -> None:
        """A 180 of a named player unlocks a badge; the cards read the positions.

        The games before gave Alex other badges and darts already.
        """
        await self.api(
            "POST",
            "/api/services/homedarts/start_game",
            json={"game": "501", "players": ["Alex"]},
        )
        await self.expect_states({"practice_game": "501", "practice_remaining": "501"})
        badges = int((await self.state("achievements"))["state"])
        self.fired_board_events()
        for count in range(1, 4):
            await self.board(
                "POST",
                "/control/state",
                json={"event": "Throw detected", "throws": [T20] * count},
            )
        await self.expect_states({"local_visit_score": "180"})
        await self.board(
            "POST",
            "/control/state",
            json={"status": "Takeout in progress", "event": "Takeout started"},
        )
        await self.board(
            "POST",
            "/control/state",
            json={"status": "Throw", "event": "Takeout finished", "throws": []},
        )
        await self.expect_states(
            {"practice_remaining": "321", "achievements": str(badges + 1)}
        )
        unlocked = [
            {key: item.get(key) for key in ("player", "name", "achievement", "tier")}
            for item in self.fired_board_events()
            if item["event_type"] == "achievement_unlocked"
        ]
        check(
            unlocked
            == [{"player": 1, "name": "Alex", "achievement": "maximum", "tier": 1}],
            f"Unexpected achievements: {unlocked}",
        )
        attributes = (await self.state("achievements"))["attributes"]
        alex = next(item for item in attributes["players"] if item["name"] == "Alex")
        check(
            attributes["latest"]["achievement"] == "maximum"
            and alex["badges"]["maximum"]["tier"] == 1,
            f"Unexpected achievements sensor: {attributes}",
        )
        profiles = (await self.state("player_profiles"))["attributes"]["players"]
        alex = next(item for item in profiles if item["name"] == "Alex")
        check(
            alex["maximums"] == 1
            and alex["hits"]["T20"] >= 3
            and alex["trend"]["maximums"][-1] == 1,
            f"Unexpected progress of Alex: {alex}",
        )
        player = await self.ws(
            "homedarts/positions", device_id=self.device_id, player="alex"
        )
        check(
            player["player"] == "Alex"
            and player["positions"][-3:] == [[0.012, 0.598]] * 3,
            f"Unexpected positions of Alex: {player}",
        )
        session = await self.ws("homedarts/positions", device_id=self.device_id)
        check(
            session["positions"][-3:] == [[0.012, 0.598]] * 3,
            f"Unexpected positions of the session: {session}",
        )
        await self.service("select", "select_option", "practice_game", option="off")
        await self.expect_states({"practice_game": "off"})

    async def match_summary(self) -> None:
        """A match ends with its summary; double out waits for the next leg."""
        await self.board("POST", "/control/state", json={"throws": []})
        await self.expect_states({"num_throws": "0"})
        await self.start_game(game="101", players=["Alex", "Sam"], legs=1)
        await self.expect_states({"practice_remaining": "101"})
        self.fired_board_events()
        await self.visit(
            T20, dart(1, 1, "SingleOuter", 0.8), dart(20, 2, "Double", 0.97)
        )

        async def summarized():
            attributes = (await self.state("practice_remaining"))["attributes"]
            return attributes.get("summary")

        summary = await wait_for(summarized, "the summary of the match")
        players = [
            (item["name"], item["legs"], item["darts"], item["average"])
            for item in summary["players"]
        ]
        check(
            summary["winner"] == 1
            and players == [("Alex", 1, 3, 101.0), ("Sam", 0, 0, None)]
            and summary["players"][0]["highest_checkout"] == 101,
            f"Unexpected match summary: {summary}",
        )
        won = [
            item
            for item in self.fired_board_events()
            if item["event_type"] == "match_won"
        ]
        check(
            len(won) == 1 and won[0]["summary"] == summary["players"],
            f"match_won does not carry the summary: {won}",
        )

        # Double out switched on during a leg applies from the next one.
        await self.start_game(game="301", players=["Alex"], double_out=False)
        await self.expect_states({"practice_remaining": "301"})
        await self.visit(T20)
        await self.expect_states({"practice_remaining": "241"})
        await self.service("switch", "turn_on", "practice_double_out")
        await self.expect_states({"practice_double_out": "on"})
        leg = (await self.state("practice_remaining"))["attributes"]
        check(leg["double_out"] is False, f"Double out changed the leg: {leg}")
        await self.service("button", "press", "practice_new_leg")
        await self.expect_states({"practice_remaining": "301"})
        leg = (await self.state("practice_remaining"))["attributes"]
        check(leg["double_out"] is True, f"Double out missing in the next leg: {leg}")

        # The rules of play.autodarts.io: master out ends a leg on a treble, and
        # after the last round of a round limit the lowest score wins the leg.
        self.fired_board_events()
        await self.start_game(
            game="301",
            players=["Alex", "Sam"],
            legs=2,
            out_mode="master",
            max_rounds=1,
            bull_off=False,
            bot_level=0,
        )
        await self.expect_states(
            {
                "practice_remaining": "301",
                "practice_out_mode": "master",
                "practice_max_rounds": "1",
                "practice_double_out": "off",
            }
        )
        await self.visit(T20)
        await self.visit(S20)
        won = [
            item
            for item in await self.events_until("leg_won")
            if item["event_type"] == "leg_won"
        ]
        check(
            (won[-1]["name"], won[-1]["rounds"], won[-1]["remaining"])
            == ("Alex", 1, 241)
            and won[-1]["checkout"] is None,
            f"The round limit did not decide the leg: {won}",
        )
        await self.start_game(game="301", max_rounds=0, out_mode="double")
        await self.expect_states({"practice_max_rounds": "0"})

    async def action(self, service: str, **data) -> None:
        await self.api("POST", f"/api/services/homedarts/{service}", json=data)

    async def play_comfort(self) -> None:
        """A dart corrected, darts entered by hand, an undone visit and the bot."""
        await self.board("POST", "/control/state", json={"throws": []})
        await self.expect_states({"num_throws": "0"})
        await self.start_game(game="301", players=["Alex", "Sam"], legs=1)
        await self.expect_states({"practice_remaining": "301"})
        self.fired_board_events()
        # The board reads a single 20 where a treble 20 is; the correction holds
        # while the board keeps its reading.
        await self.board("POST", "/control/state", json={"throws": [T20, S20]})
        await self.expect_states({"practice_remaining": "221"})
        await self.action("correct_dart", dart=2, segment="T20")
        await self.expect_states(
            {"practice_remaining": "181", "local_visit_score": "120"}
        )
        corrected = [
            item
            for item in await self.events_until("dart_corrected")
            if item["event_type"] == "dart_corrected"
        ]
        check(
            (
                corrected[-1]["segment"],
                corrected[-1]["previous"],
                corrected[-1]["manual"],
            )
            == ("T20", "S20", True),
            f"Unexpected correction: {corrected}",
        )
        throws = (await self.state("local_visit_score"))["attributes"]["throws"]
        check(
            [(dart["segment"], dart.get("corrected"), dart["dart"]) for dart in throws]
            == [("T20", None, 1), ("T20", True, 2)],
            f"The visit does not show the correction: {throws}",
        )
        await self.board("POST", "/control/state", json={"throws": []})
        await self.expect_states({"num_throws": "0", "practice_remaining": "301"})

        # Sam plays without cameras: two darts entered by hand, then the next player.
        await self.service("switch", "turn_on", "practice_manual_entry")
        await self.expect_states({"practice_manual_entry": "on"})
        self.fired_board_events()
        darts = int((await self.state("training_darts"))["state"])
        for segment in ("T20", "d20"):
            await self.action("throw_dart", segment=segment)
        await self.expect_states({"practice_remaining": "201"})
        await self.action("next_player")
        fired = await self.events_until("turn_changed")
        entered = [
            item
            for item in fired
            if item["event_type"] in ("dart_detected", "visit_completed")
        ]
        check(
            [(item["event_type"], item.get("manual")) for item in entered]
            == [
                ("dart_detected", True),
                ("dart_detected", True),
                ("visit_completed", True),
            ],
            f"Darts entered by hand are not marked: {entered}",
        )
        await self.expect_states({"practice_remaining": "181"})
        check(
            int((await self.state("training_darts"))["state"]) == darts + 2,
            "Darts entered by hand do not count for the training",
        )
        # Sam's visit comes back, and is ended again.
        attributes = (await self.state("practice_remaining"))["attributes"]
        check(attributes["undo"] is True, f"No undo offered: {attributes}")
        await self.action("undo_visit")
        undone = [
            item
            for item in await self.events_until("visit_undone")
            if item["event_type"] == "visit_undone"
        ]
        check(
            (undone[-1]["score"], undone[-1]["name"]) == (100, "Sam"),
            f"Unexpected undo: {undone}",
        )
        await self.expect_states({"practice_remaining": "201"})
        await self.action("next_player")
        await self.expect_states({"practice_remaining": "181"})
        await self.service("switch", "turn_off", "practice_manual_entry")

        # A match against the bot: it throws half a second after each dart.
        await self.service("number", "set_value", "practice_bot_delay", value=0.5)
        await self.start_game(game="301", players=["Alex"], bot_level=120)
        await self.expect_states(
            {"practice_remaining": "301", "practice_bot_level": "120"}
        )
        darts = int((await self.state("training_darts"))["state"])
        self.fired_board_events()
        await self.visit(T20, T20, T20)

        async def bot_visit():
            fired.extend(self.fired_board_events())
            return any(
                item["event_type"] == "visit_completed" and item.get("bot")
                for item in fired
            )

        fired = []
        await wait_for(bot_visit, "the bot's visit")
        bot = [
            item
            for item in fired
            if item["event_type"] == "dart_detected" and item.get("bot")
        ]
        check(
            len(bot) == 3 and all(item["name"] is None for item in bot),
            f"Unexpected darts of the bot: {bot}",
        )
        scores = (await self.state("practice_remaining"))["attributes"]["scores"]
        check(
            scores[1].get("bot") is True and scores[1]["remaining"] < 301,
            f"The bot did not score: {scores}",
        )
        check(
            int((await self.state("training_darts"))["state"]) == darts + 3,
            "The bot's darts count for the training",
        )
        await self.service("number", "set_value", "practice_bot_level", value=0)
        await self.expect_states({"practice_bot_level": "0"})

    async def say(self, text: str) -> str:
        """What Assist answers to a sentence."""
        result = await self.ws("conversation/process", text=text, language="en")
        return result["response"]["speech"]["plain"]["speech"]

    async def voice(self) -> None:
        """The blueprint starts games from sentences in English and German, Assist says
        what started or what was wrong, and its own commands stay its own."""
        spoken = [
            ("Start 501 for Alex and Sam", "Game on: 501 with Alex and Sam."),
            (
                "Starte das Spiel Doppeltraining",
                "Game on: Doubles training with Alex and Sam.",
            ),
            (
                "Play 501 for alex against the bot",
                "Game on: 501 with Alex and the bot.",
            ),
            (
                "Starte das Spiel Cricket für Alex und Sam",
                "Game on: Cricket with Alex and Sam.",
            ),
        ]
        for text, answer in spoken:
            said = await self.say(text)
            check(said == answer, f"Assist answered {said!r} to {text!r}")
        await self.expect_states(
            {"practice_game": "cricket", "practice_bot_level": "0"}
        )
        said = await self.say("Start the game Golfball for Alex")
        check(
            said.startswith('No game is called "Golfball"'), f"Unknown game: {said!r}"
        )
        # Sentences of other commands never reach the blueprint.
        said = await self.say("Start the vacuum for 5 minutes")
        check(
            "Game on" not in said and "game" not in said,
            f"Another command went to the blueprint: {said!r}",
        )
        await self.service("select", "select_option", "practice_game", option="off")
        await self.expect_states({"practice_game": "off"})

    async def voice_entry(self) -> None:
        """The blueprint enters darts from sentences in English and German, as at a
        dart machine: a visit's score, a dart, the next player, a visit taken back,
        and a player who is not at the board; Assist answers in the caller's words."""
        await self.service("switch", "turn_on", "practice_manual_entry")
        await self.expect_states({"practice_manual_entry": "on"})
        said = await self.say("Start 501 for Alex and Sam")
        check(said == "Game on: 501 with Alex and Sam.", f"No game by voice: {said!r}")
        spoken = [
            ("Alex hat 140", "140 for Alex, 361 left. Sam, you require 501."),
            ("Triple 20", "Triple 20, 441 left."),
            ("single bull", "25, 416 left."),
            ("next player", "Alex, you require 361."),
            ("Sam scored 100", "It is Alex's turn, not Sam's."),
            ("100 Punkte", "100 for Alex, 261 left. Sam, you require 416."),
            ("Rückgängig", "Taken back: 100 of Alex."),
            # The visit taken back gives way to the score entered for it.
            ("60", "60 for Alex, 301 left. Sam, you require 416."),
            ("Doppel 8", "Double 8, 400 left."),
            (
                "Checkout with two darts",
                "No visit checks out 416 with these rules and darts.",
            ),
            ("miss", "Miss, 400 left."),
        ]
        for text, answer in spoken:
            said = await self.say(text)
            check(said == answer, f"Assist answered {said!r} to {text!r}")
        scores = (await self.state("practice_remaining"))["attributes"]["scores"]
        check(
            [item["remaining"] for item in scores] == [301, 400],
            f"The darts by voice left {scores}",
        )
        # Its sentences need the words of darts: other commands stay Assist's own.
        said = await self.say("What is the time")
        check("left" not in said and "turn" not in said, f"Caught: {said!r}")
        await self.service("select", "select_option", "practice_game", option="off")
        await self.service("switch", "turn_off", "practice_manual_entry")
        await self.expect_states(
            {"practice_game": "off", "practice_manual_entry": "off"}
        )

    async def voice_questions(self) -> None:
        """The blueprint answers questions about the darts from the statistics of the
        board, which it finds in a real Home Assistant as in the tests: Assist answers
        in the language of the voice assistant, English here, also to German."""
        best = (await self.state("personal_best"))["attributes"].get("highest_checkout")
        said = await self.say("What is my best checkout?")
        wanted = f"Your best checkout is {best}." if best else "No checkout yet."
        check(said == wanted, f"Assist answered {said!r}, not {wanted!r}")
        week = (await self.state("weekly_report"))["attributes"]["scores_180"]
        said = await self.say("Wie viele 180er habe ich diese Woche geworfen?")
        wanted = f"180s this week: {week}." if week else "No 180 this week yet."
        check(said == wanted, f"Assist answered {said!r}, not {wanted!r}")

    async def card(self) -> None:
        """The bundled dashboard card and the strategy's own small module are served
        and loaded without a resource, from the folder of one version with the texts
        of every language, and the card module is compressed. Both modules are
        dashboard resources too, which Home Assistant Cast loads from its own origin."""
        version = json.loads(MANIFEST.read_text())["version"]
        files = {
            path.relative_to(FRONTEND).as_posix(): path.read_bytes()
            for path in FRONTEND.rglob("*.js")
        }
        content = b"".join(files[name] for name in sorted(files))
        folder = f"/homedarts/{version}-{hashlib.sha256(content).hexdigest()[:8]}"
        url = f"{folder}/homedarts-card.js"
        strategy_url = f"{folder}/homedarts-strategy.js"
        texts = [
            f"{folder}/{name}" for name in sorted(files) if name.startswith("text/")
        ]
        check(len(texts) >= 5, f"The texts of the cards are {texts}")
        sources = {}
        for address in (url, strategy_url, *texts):
            async with self.session.get(f"{HA}{address}") as response:
                sources[address] = await response.text()
                check(
                    response.status == 200,
                    f"{address} not served: HTTP {response.status}",
                )
                check(
                    "javascript" in response.headers.get("Content-Type", ""),
                    f"{address} served as {response.headers.get('Content-Type')}",
                )
        source = sources[url]
        for address in texts:
            name = address.removeprefix(f"{folder}/")
            check(f'from "./{name}";' in source, f"The card does not import {name}")
            check(
                sources[address].encode() == files[name],
                f"{address} is not the file of the integration",
            )
        # Compressed, as for every browser: aiohttp accepts gzip too.
        async with self.session.get(f"{HA}{url}", auto_decompress=False) as response:
            sent = len(await response.read())
            encoding = response.headers.get("Content-Encoding")
        check(
            encoding == "gzip" and sent < len(source.encode()) * 0.3,
            f"{url} sent with {sent} bytes, encoded as {encoding}",
        )
        check(
            '"ll-strategy-dashboard-homedarts"' in sources[strategy_url],
            "The strategy module defines no strategy",
        )
        for element in (
            "homedarts-card",
            "homedarts-training-card",
            "homedarts-status-card",
            "homedarts-scoreboard-card",
            "homedarts-players-card",
            "homedarts-doubles-card",
            "homedarts-leaderboard-card",
        ):
            check(f'"{element}"' in source, f"Card element {element} missing")
        async with self.session.get(f"{HA}/") as response:
            page = await response.text()
        check(url in page, "Dashboards do not load the HomeDarts card")
        check(strategy_url in page, "Dashboards do not load the strategy module")
        resources = [
            (item["type"], item["url"])
            for item in await self.ws("lovelace/resources")
            if item["url"].startswith("/homedarts/")
        ]
        check(
            resources == [("module", strategy_url), ("module", url)],
            f"The dashboard resources for Cast are {resources}",
        )
        cast = "https://cast.home-assistant.io"
        for address in (url, strategy_url):
            async with self.session.get(
                f"{HA}{address}", headers={"Origin": cast}
            ) as response:
                allowed = response.headers.get("Access-Control-Allow-Origin")
            check(allowed == cast, f"Cast may not load {address}: {allowed}")

    async def people(self) -> None:
        """A player becomes a person of Home Assistant, and stops being one."""
        await self.api(
            "POST",
            "/api/states/person.e2e_player",
            status=201,
            json={"state": "home", "attributes": {"entity_picture": "/e2e.png"}},
        )

        async def person() -> str | None:
            players = (await self.state("player_profiles"))["attributes"]["players"]
            return next(
                (p["person"] for p in players if p["name"] == "E2E Player"), "missing"
            )

        async def linked() -> bool:
            return await person() == "person.e2e_player"

        async def unlinked() -> bool:
            return await person() is None

        await self.api(
            "POST",
            "/api/services/homedarts/link_player",
            json={"player": "E2E Player", "person": "person.e2e_player"},
        )
        await wait_for(linked, "the player linked to the person")
        await self.api(
            "POST",
            "/api/services/homedarts/unlink_player",
            json={"player": "e2e player"},
        )
        await wait_for(unlinked, "the link to be undone")
        await self.api(
            "POST", "/api/services/homedarts/delete_player", json={"name": "E2E Player"}
        )
        await self.api("DELETE", "/api/states/person.e2e_player")

    async def gallery(self) -> None:
        """The media browser lists the highlight photos by month and serves them."""
        GALLERY.mkdir(parents=True, exist_ok=True)
        photo = board_photo(["T20", "T20", "T20"])
        (GALLERY / PHOTO).write_bytes(photo)
        outside = GALLERY.parents[1] / "e2e-outside.jpg"
        outside.write_bytes(photo)
        try:
            sources = await self.ws(
                "media_source/browse_media", media_content_id="media-source://"
            )
            titles = [child["title"] for child in sources["children"]]
            check("HomeDarts" in titles, f"Media sources: {titles}")
            root = await self.ws(
                "media_source/browse_media", media_content_id="media-source://homedarts"
            )
            months = [
                (child["title"], child["can_expand"]) for child in root["children"]
            ]
            check(months == [("September 2026", True)], f"Months: {months}")
            month = await self.ws(
                "media_source/browse_media",
                media_content_id="media-source://homedarts/2026-09",
            )
            photos = [
                (child["title"], child["media_class"], child["media_content_type"])
                for child in month["children"]
            ]
            check(
                photos == [("180 · E2E Player · Sep 26", "image", "image/jpeg")],
                f"Photos: {photos}",
            )
            resolved = await self.ws(
                "media_source/resolve_media",
                media_content_id=f"media-source://homedarts/{PHOTO}",
            )
            check(
                resolved["url"].startswith(
                    "/media/local/homedarts/highlights/2026-09-26_21-05-33_E2E%20Player_180.jpg?authSig="
                ),
                f"Resolved: {resolved}",
            )
            # The signed address works without a login, like in an image element.
            async with self.session.get(f"{HA}{resolved['url']}") as response:
                check(response.status == 200, f"Photo: HTTP {response.status}")
                check(await response.read() == photo, "The photo has other bytes")
            # Nothing outside the gallery resolves.
            for identifier in ("../e2e-outside.jpg", "..%2Fe2e-outside.jpg", "2026-09"):
                failed = await self.ws_result(
                    "media_source/resolve_media",
                    media_content_id=f"media-source://homedarts/{identifier}",
                )
                check(not failed["success"], f"{identifier} resolved: {failed}")
            unknown = await self.ws_result(
                "media_source/browse_media",
                media_content_id="media-source://homedarts/../..",
            )
            check(not unknown["success"], f"Browsing outside: {unknown}")
            # A board camera starts disabled: it saves no photo, and the action
            # says why instead of answering with a file that was never written.
            camera = self.entity("camera_0")
            error = await self.refused(
                "call_service",
                domain="homedarts",
                service="save_highlight",
                service_data={"camera": camera, "player": "E2E Player", "label": 180},
                return_response=True,
            )
            check(
                error["code"] == "service_validation_error"
                and error.get("translation_key") == "highlight_camera_missing"
                and f"The camera {camera} does not exist or is disabled"
                in error["message"],
                f"save_highlight with a disabled camera: {error}",
            )
            photos = sorted(path.name for path in GALLERY.iterdir())
            check(photos == [PHOTO], f"Photos in the gallery: {photos}")
        finally:
            (GALLERY / PHOTO).unlink()
            outside.unlink()

    async def tournament(self) -> None:
        """A round robin of three at 101, started by the action and played on the board."""
        self.fired_board_events()
        await self.api(
            "POST",
            "/api/services/homedarts/start_tournament",
            json={
                "players": TOURNAMENT_PLAYERS,
                "format": "round_robin",
                "game": "101",
                "legs": 1,
                "sets": 1,
                "double_out": True,
                "bull_off": False,
                "pause": 1,
                "summary": 0,
            },
        )
        await self.expect_states(
            {
                "tournament": "round_1",
                "practice_game": "101",
                "practice_remaining": "101",
            }
        )
        pairings = []
        for number in (1, 2, 3):

            async def current(number: int = number) -> dict | None:
                match = (await self.state("tournament"))["attributes"]["current"]
                return match if match and match["match"] == number else None

            match = await wait_for(current, f"tournament match {number}")
            pairings.append(match["players"])
            # The first player of every match checks out 101 in one visit.
            for count in range(1, 4):
                await self.board(
                    "POST", "/control/state", json={"throws": CHECKOUT_101[:count]}
                )
            await self.expect_states({"practice_remaining": "0"})
            await self.board("POST", "/control/state", json={"throws": []})
        await self.expect_states({"tournament": "finished"})
        attributes = (await self.state("tournament"))["attributes"]
        first, second, third = TOURNAMENT_PLAYERS
        check(
            pairings == [[third, second], [first, third], [second, first]],
            f"Unexpected order of play: {pairings}",
        )
        # Everybody won once, 1:0 with the same average: the order of the draw decides.
        check(
            attributes["winner"] == first
            and [row["name"] for row in attributes["standings"]] == TOURNAMENT_PLAYERS
            and all(row["points"] == 2 for row in attributes["standings"]),
            f"Unexpected table: {attributes['standings']}",
        )
        # The websocket can deliver the last events after the state reads finished.
        fired: list[dict] = []

        async def tournament_events() -> list[dict] | None:
            fired.extend(
                item
                for item in self.fired_board_events()
                if item["event_type"].startswith("tournament_")
            )
            done = fired and fired[-1]["event_type"] == "tournament_finished"
            return fired if done else None

        await wait_for(tournament_events, "the tournament events")
        check(
            [item["event_type"] for item in fired]
            == [
                "tournament_started",
                *["tournament_match_finished"] * 3,
                "tournament_finished",
            ]
            and fired[-1]["winner"] == first
            and fired[1]["next"] == [first, third],
            f"Unexpected tournament events: {fired}",
        )
        # The matches count for the profiles like any other match.
        profiles = (await self.state("player_profiles"))["attributes"]["players"]
        won = {player["name"]: player["matches_won"] for player in profiles}
        check(
            all(won.get(name) == 1 for name in TOURNAMENT_PLAYERS),
            f"Tournament matches missing in the profiles: {won}",
        )
        await self.api("POST", "/api/services/homedarts/stop_tournament", json={})
        await self.expect_states({"tournament": "no_tournament"})

    async def manual_board(self) -> None:
        """A dartboard without Autodarts beside the board: set up from the menu,
        played with darts entered by hand, and removed again."""
        # No Granboard is in reach of the container's Bluetooth, which the step of
        # the setup menu says, in a real Home Assistant with its Bluetooth API.
        menu = await self.flow()
        result = await self.flow(menu["flow_id"], next_step_id="granboard")
        check(
            result["type"] == "abort" and result["reason"] == "no_granboards",
            f"The Granboard step did not say that none is in reach: {result}",
        )
        menu = await self.flow()
        form = await self.flow(menu["flow_id"], next_step_id="manual")
        check(
            form["step_id"] == "manual",
            f"No form for a board without Autodarts: {form}",
        )
        result = await self.flow(form["flow_id"], name="Garage")
        check(
            result["type"] == "create_entry" and result["title"] == "Garage",
            f"A board without Autodarts was not set up: {result}",
        )
        entry_id = result["result"]["entry_id"]

        async def loaded():
            entries = await self.api(
                "GET", "/api/config/config_entries/entry?domain=homedarts"
            )
            return any(
                entry["entry_id"] == entry_id and entry["state"] == "loaded"
                for entry in entries
            )

        await wait_for(loaded, "the board without Autodarts to load")
        entities = {
            item["translation_key"]: item["entity_id"]
            for item in await self.ws("config/entity_registry/list")
            if item["config_entry_id"] == entry_id
        }
        for key in ("local_status", "practice_remaining", "training_darts"):
            check(key in entities, f"The board without Autodarts lacks {key}")
        for key in ("local_connected", "detection", "practice_manual_entry"):
            check(key not in entities, f"The board without Autodarts has {key}")

        async def states(expected: dict[str, str]):
            async def probe():
                actual = {
                    key: (await self.api("GET", f"/api/states/{entities[key]}"))[
                        "state"
                    ]
                    for key in expected
                }
                return actual == expected or None

            await wait_for(probe, f"states {expected} of the board without Autodarts")

        await states({"local_status": "manual"})
        board = {"config_entry_id": entry_id}
        await self.action("start_game", game="501", players=["Alex", "Sam"], **board)
        await states({"practice_remaining": "501"})
        for segment in ("T20", "T20", "T19"):
            await self.action("throw_dart", segment=segment, **board)
        await states({"practice_remaining": "324", "local_visit_score": "177"})
        await self.action("next_player", **board)
        await states({"practice_remaining": "501", "training_darts": "3"})
        # Its Autodarts board can be connected later, but not one that another
        # entry has already.
        menu = await self.api(
            "POST",
            "/api/config/config_entries/flow",
            json={"handler": "homedarts", "entry_id": entry_id},
        )
        check(
            menu["step_id"] == "reconfigure_manual"
            and menu["menu_options"] == ["discover", "local"],
            f"No way to connect an Autodarts board: {menu}",
        )
        form = await self.flow(menu["flow_id"], next_step_id="local")
        stored = self.board_ip if GENERATION >= 2 else "board-mock"
        result = await self.flow(form["flow_id"], host=stored, port=PORT)
        check(
            result.get("reason") == "already_configured",
            f"The board of another entry was connected: {result}",
        )
        await self.api("DELETE", f"/api/config/config_entries/entry/{entry_id}")
        check(
            not Path(f"/config/.storage/homedarts.{entry_id}.training").exists(),
            "The training of the board without Autodarts was not deleted",
        )

    async def diagnostics(self, entry_id: str) -> None:
        report = await self.api("GET", f"/api/diagnostics/config_entry/{entry_id}")
        data = report["data"]
        check(API_KEY not in json.dumps(report), "Diagnostics expose the board API key")
        for name in TOURNAMENT_PLAYERS:
            check(
                name not in json.dumps(report), f"Diagnostics expose the player {name}"
            )
        check(TLS_KEY not in json.dumps(report), "Diagnostics expose the TLS key")
        check(BOARD_ID not in json.dumps(data), "Diagnostics expose the board ID")
        check("Alex" not in json.dumps(report), "Diagnostics expose a player name")
        check(
            data["local_available"] is True and data["realtime_connected"] is True,
            f"Unexpected diagnostics summary: {data}",
        )

    async def offline(self) -> None:
        """Home Assistant stays off the internet. Onboarding sets up Radio Browser,
        which looks up radio stations on the internet as soon as it starts; the
        stand-in of offline/radio_browser takes its place and turns that down, also
        through the restarts of the scenario."""
        manifest = await self.ws("manifest/get", integration="radio_browser")
        check(
            manifest["is_built_in"] is False,
            "Home Assistant has its own Radio Browser instead of the stand-in of "
            "offline/radio_browser, which keeps it off the internet",
        )
        entries = await self.api(
            "GET", "/api/config/config_entries/entry?domain=radio_browser"
        )
        check(
            not entries,
            f"Onboarding set up Radio Browser, which reaches the internet: {entries}",
        )

    async def logs(self) -> None:
        problems = [
            item
            for item in await self.ws("system_log/list")
            if (
                item["level"] in ("ERROR", "CRITICAL")
                or item["name"].startswith("custom_components.homedarts")
            )
            and not any(
                expected in " ".join(item["message"]) for expected in EXPECTED_LOGS
            )
        ]
        check(not problems, f"Home Assistant logged problems: {problems}")
        log = LOG.read_text() if LOG.exists() else ""
        check(API_KEY not in log, "Home Assistant log contains the board API key")
        check(TLS_KEY not in log, "Home Assistant log contains the TLS key")
        check(
            self.webhook_id is not None and self.webhook_id not in log,
            "Home Assistant log contains the webhook address",
        )
        # Records start with a timestamp; the outage of the fault injection logs
        # its cause at debug level, every other traceback is a problem.
        records = re.split(r"\n(?=\d{4}-\d{2}-\d{2} )", log)
        tracebacks = [
            record
            for record in records
            if "Traceback" in record
            and not any(expected in record for expected in EXPECTED_TRACEBACKS)
        ]
        check(not tracebacks, f"Home Assistant log contains tracebacks: {tracebacks}")

        board = await self.board("GET", "/control/requests")
        check(
            not board["unexpected"],
            f"Unexpected Board Manager calls: {board['unexpected']}",
        )

    async def remove(self, entry_id: str) -> None:
        await self.api("DELETE", f"/api/config/config_entries/entry/{entry_id}")

        async def disconnected():
            return (await self.board("GET", "/control/requests"))["sockets"] == 0

        await wait_for(disconnected, "the board socket to close after removal")
        remaining = [
            item
            for item in await self.ws("config/entity_registry/list")
            if item["platform"] == "homedarts"
        ]
        check(not remaining, f"Entities remain after removal: {remaining}")
        for store in ("training", "report", "journal"):
            check(
                not Path(f"/config/.storage/homedarts.{entry_id}.{store}").exists(),
                f"The {store} store was not deleted with the integration",
            )


# The seconds after which the watchdog fails a phase (watchdog.py): about three times
# its longest run in CI, at least two minutes. Only the resilience, with its outages
# and its restart of the board, took longer than 15 s: 50 s at most in October 2026.
PHASE_BUDGET = 120.0


async def phase[T](name: str, run: Awaitable[T], budget: float = PHASE_BUDGET) -> T:
    """Run a phase of the scenario and print its seconds, which tell where its time
    goes: "Scenario phase: resilience (46.3 s)". A phase that hangs fails after its
    budget with the line that it waits at, long before the time limit of the job."""
    print(f"Scenario phase: {name}", flush=True)
    started = time.monotonic()
    result = await within(f"The phase {name}", budget, run, E2EFailure)
    print(f"Scenario phase: {name} ({time.monotonic() - started:.1f} s)", flush=True)
    return result


async def main() -> None:
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        scenario = Scenario(session)
        await phase("onboarding", scenario.onboard())
        await phase("connection", scenario.connect())
        entry_id = await phase("setup", scenario.setup())
        await phase("registries", scenario.registries(entry_id))
        await phase("initial state", scenario.initial_state())
        await phase("controls", scenario.controls())
        await phase("realtime", scenario.realtime(entry_id))
        await phase("resilience", scenario.resilience(entry_id), budget=150)
        await phase("online bridge", scenario.online_bridge(entry_id))
        await phase("reports", scenario.reports(entry_id))
        await phase("games", scenario.games())
        await phase("achievements", scenario.achievements())
        await phase("match summary", scenario.match_summary())
        await phase("play comfort", scenario.play_comfort())
        await phase("voice", scenario.voice())
        await phase("voice entry", scenario.voice_entry())
        await phase("voice questions", scenario.voice_questions())
        await phase("card", scenario.card())
        await phase("people", scenario.people())
        await phase("gallery", scenario.gallery())
        await phase("tournament", scenario.tournament())
        await phase("manual board", scenario.manual_board())
        await phase("diagnostics", scenario.diagnostics(entry_id))
        await phase("offline", scenario.offline())
        await phase("logs", scenario.logs())
        await phase("removal", scenario.remove(entry_id))
        await scenario.socket.close()
    print(
        f"Docker E2E passed for Board Manager {GENERATION}: onboarding, "
        + ("mDNS discovery, " if GENERATION >= 2 else "")
        + "local config flow and validation, registries, "
        "controls, realtime darts/corrections/takeouts with positions, persistence, "
        "dropped sockets mid-visit, outages, failing and slow reads, malformed "
        "frames, a restart, a stuck takeout freed, the online bridge, weekly report, "
        "training calendar, "
        "exports, Golf, Tactics and a team match with start scores, an achievement "
        "with dart positions, a match "
        "summary, double out from the next leg, a corrected dart, darts entered by "
        "hand with an undone visit, a match against the bot, games started by voice, "
        "darts entered by voice, "
        "dashboard card, players linked to "
        "persons, the highlight gallery in the media browser, a round robin "
        "tournament, a dartboard without Autodarts beside the board, private "
        "diagnostics, no Radio Browser to reach the internet, clean logs and removal."
    )


if __name__ == "__main__":
    asyncio.run(main())
