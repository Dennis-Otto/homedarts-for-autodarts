"""The Board Manager of a board: realtime events, HTTP reads and recovery.

AutodartsLocalCoordinator follows the board with its push notifications and
reconciles them with periodic reads; it frees stuck takeouts, raises the
repair issues of the board and runs its actions. The reads besides the state
are in BoardReads (reads.py), the generation of the Board Manager in
BoardGeneration (generation.py). The training and the games run in
AutodartsGamesCoordinator, which it extends; a dartboard without Autodarts
plays them without a Board Manager, see AutodartsManualCoordinator.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable, Coroutine
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .camera_health import CameraHealth
from .const import DOMAIN, LIFECYCLE_STATUSES
from .errors import AutodartsApiError, AutodartsConnectionError
from .games_coordinator import AutodartsGamesCoordinator
from .generation import BoardGeneration
from .local_api import (
    AutodartsEndpointMissing,
    AutodartsLocalAuthError,
    AutodartsLocalClient,
    AutodartsProtocolError,
    camera_state_summary,
    motion_flags,
    number,
    stats_summary,
)
from .online import ONLINE_EVENT_TYPES
from .reads import BoardReads
from .topics import BoardTopics, Topic
from .tournament import TOURNAMENT_EVENTS

_LOGGER = logging.getLogger(__name__)
# Poll quickly without realtime events; with them, polling only reconciles.
POLL_INTERVAL = timedelta(seconds=2)
STREAM_POLL_INTERVAL = timedelta(seconds=30)
# Board Manager 2 announces no camera changes, so it is read more often.
STREAM_POLL_INTERVAL_V2 = timedelta(seconds=10)
# Board Manager 2.1 sends its motion 30 times a second, a real board with gaps of up to
# a quarter of a second. Frames that stay away this long leave the motion to the read.
MOTION_SILENCE_SECONDS = 2
# The quick reads of Board Manager 2.1 report the frame rates and the load as often
# as those reads, which a timer may start a second early.
TELEMETRY_SECONDS = 8
# A board that stays away, for example while its PC is off, is asked less often.
OFFLINE_POLL_INTERVAL = timedelta(seconds=15)
OFFLINE_AFTER_FAILURES = 10
# Failed polls in a row that keep the last values, like a short Wi-Fi hiccup.
TOLERATED_FAILURES = 2
# The first poll during setup waits this long for the board.
FIRST_POLL_SECONDS = 3
# Realtime reconnects wait 1, 2, 4 ... 60 seconds, each shortened by up to a fifth.
RECONNECT_MIN = 1
RECONNECT_MAX = 60
RECONNECT_JITTER = 0.2
# A realtime connection that lasted this long starts the back-off over.
RECONNECT_RESET_SECONDS = 30
# Failed realtime attempts in a row before a warning, about half a minute.
STREAM_WARN_ATTEMPTS = 5
# Board Manager 2.0.2 may start a takeout again right after one ends and keep it
# on the empty board, counting no darts until a reset. Real takeouts last 0.3 to
# 2.5 seconds, so one that holds ten seconds without a hand at the board is
# stuck, while a player who waits for the board hardly notices the delay.
STUCK_TAKEOUT_SECONDS = 10
# Resets in a row, a period apart, before a board that stays stuck is left to
# its player; a dart on the board allows them again.
STUCK_TAKEOUT_RESETS = 3
# High-rate push values: their sensors show them with the next poll, and only a
# camera alarm they raise or clear shows at once.
TELEMETRY = ("stats", "camera_stats")
# Values of the board PC's load in /api/system that change with every read.
SYSTEM_TELEMETRY = ("cpu_percent", "memory_bytes")
# The readings of each topic, kept in readings beside the data: a change of
# them alone updates only the entities that show them, see BoardTopics.
# "system" holds the load of the board PC, data["system"] the rest.
READINGS: dict[Topic, tuple[str, ...]] = {
    Topic.TELEMETRY: (*TELEMETRY, "system"),
    Topic.MOTION: ("motion",),
    Topic.CAMERA_STATE: ("camera_state",),
}
EVENT_TYPES = [
    "dart_detected",
    "dart_corrected",
    "takeout_started",
    "takeout_finished",
    "status_changed",
    "visit_thrown",
    "visit_completed",
    "session_started",
    "session_ended",
    "bust",
    "leg_won",
    "match_won",
    "turn_changed",
    "game_started",
    "game_ended",
    "drill_finished",
    "checkout_attempt",
    "personal_best",
    "daily_goal_reached",
    "bull_off_won",
    "weekly_report",
    "achievement_unlocked",
    *TOURNAMENT_EVENTS,
    "visit_undone",
    "player_renamed",
    # Moments of online matches, from the browser extension Tools for Autodarts.
    *ONLINE_EVENT_TYPES,
]
# Repair issues of an entry, named <issue>_<entry_id>.
ISSUES = (
    "wrong_board",
    "board_manager_1",
    "calibration",
    "board_moved",
    "board_access_denied",
    "unsupported_response",
)
# Jitter only spreads reconnects; it needs no cryptographic randomness.
_RANDOM = random.Random()  # noqa: S311


def _lifecycle(state: dict[str, Any]) -> tuple[object, str]:
    """Whether the detection runs and where it is in starting or stopping."""
    status = str(state.get("status", "")).lower()
    return state.get("running"), status if status in LIFECYCLE_STATUSES else "running"


def _error_name(error: BaseException) -> str:
    """The kind of a failure, for diagnostics; messages may contain addresses."""
    return type(error.__cause__ or error).__name__


@dataclass
class ConnectionStats:
    """Connection history for diagnostics; no addresses, messages or payloads."""

    failures: int = 0
    last_error: str | None = None
    last_success: datetime | None = None
    offline_since: float | None = None
    poll_seconds: float | None = None
    connects: int = 0
    stream_failures: int = 0
    reconnect_delay: float = RECONNECT_MIN
    last_close: str | None = None
    # Stuck takeouts freed with a reset, and resets the board did not accept.
    takeout_resets: int = 0
    failed_takeout_resets: int = 0
    last_takeout_reset: datetime | None = None


class AutodartsLocalCoordinator(AutodartsGamesCoordinator):
    """Keep controls local and reconcile push notifications with periodic reads."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AutodartsLocalClient,
        board_id: str,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(hass, board_id, entry, POLL_INTERVAL, _LOGGER)
        self.client = client
        self._health = CameraHealth()
        self._settings: dict[str, Any] = {}
        # The version the device page shows, as far as this run set it.
        self._device_version: str | None = None
        # The generation and the version of the Board Manager, and the reads
        # besides the state.
        self.board_manager = BoardGeneration(
            hass, entry, self._issue_id("board_manager_1")
        )
        self.reads = BoardReads(client, self.board_manager)
        self._first_poll = True
        self._identity_valid = True
        self._access_denied = False
        self._action_lock = asyncio.Lock()
        # One read at a time: an older answer must never replace a newer one.
        self._poll_lock = asyncio.Lock()
        self.connection = ConnectionStats()
        self._stream_task: asyncio.Task[None] | None = None
        self.stream_connected = False
        # A valid notification arrived since the socket opened.
        self._stream_live = False
        self._stream_warned = False
        self._stream_error_logged = False
        self._reconnect_now = asyncio.Event()
        self._revisions: dict[str, int] = {}
        # The motion flags, the cameras' state, the frame rates and the board
        # PC's load, see READINGS; each topic tells the entities that show it.
        self.readings: dict[str, Any] = {}
        self.topics = BoardTopics()
        # async_shutdown began: a read that ends later changes nothing.
        self._shutting_down = False
        self._observed_state: dict[str, Any] | None = None
        self._observed_motion: dict[str, Any] | None = None
        self._taking_out = False
        # Reset the board when it keeps a takeout without darts; a stored setting.
        self.free_stuck_takeout = True
        self._takeout_unsub: CALLBACK_TYPE | None = None
        # Resets of a stuck takeout since the last dart on the board.
        self._takeout_resets = 0
        # When a read last reported the frame rates and the load.
        self._telemetry_reported = 0.0
        # When Board Manager 2.1 last sent its motion, and the watch for its end.
        self._motion_frame_at: float | None = None
        self._motion_watch: CALLBACK_TYPE | None = None

    def _restore(self, saved: object) -> None:
        super()._restore(saved)
        takeout = saved.get("takeout") if isinstance(saved, dict) else None
        self.free_stuck_takeout = not (
            isinstance(takeout, dict) and takeout.get("free_stuck") is False
        )

    def _stored(self) -> dict[str, Any]:
        """The games, with the switch that frees a stuck takeout."""
        return {
            **super()._stored(),
            "takeout": {"free_stuck": self.free_stuck_takeout},
        }

    @callback
    def async_start(self) -> None:
        # Issues of earlier runs are not kept across restarts.
        self.board_manager.report()
        super().async_start()
        if self._stream_task is None:
            self._stream_task = self._entry.async_create_background_task(
                self.hass, self._listen(), f"{DOMAIN} local events"
            )

    async def async_shutdown(self) -> None:
        self._shutting_down = True
        await super().async_shutdown()

    async def _async_settle(self) -> None:
        """Nothing throws, resets or listens any more. A poll still in flight
        ends now, without effect (see _unchanged), before the stores are saved
        and the unload deletes the repair issues. Each read of the board gives
        up after 10 seconds."""
        if self._stream_task:
            self._stream_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._stream_task
            self._stream_task = None
        self._cancel_takeout()
        self._end_motion_frames()
        async with self._poll_lock:
            pass

    # -- realtime events ---------------------------------------------------------

    async def _listen(self) -> None:
        """Follow the push notifications until async_shutdown cancels this task."""
        delay: float = RECONNECT_MIN
        while True:
            lasted = await self._follow_events()
            if lasted is not None and lasted >= RECONNECT_RESET_SECONDS:
                delay = RECONNECT_MIN
            self.connection.reconnect_delay = delay
            woken = await self._wait_before_reconnect(
                delay * (1 - RECONNECT_JITTER * _RANDOM.random())
            )
            # A board that answers polls again is reconnected at once.
            delay = RECONNECT_MIN if woken else min(delay * 2, RECONNECT_MAX)

    @callback
    def _update_listeners_unless_shutting_down(self) -> None:
        """The entities hear of the lost stream, unless the unload removes them."""
        if self._shutting_down:
            return
        self.async_update_listeners()

    async def _follow_events(self) -> float | None:
        """One realtime connection; how long it lasted, None if it never opened."""
        self._reconnect_now.clear()
        connected_at: float | None = None
        try:
            async for kind, payload in self.client.events():
                if kind == "connected":
                    connected_at = time.monotonic()
                    self.connection.connects += 1
                    self.stream_connected = True
                    self.async_update_listeners()
                elif kind == "closed":
                    self.connection.last_close = (
                        f"closed by the board ({payload['code']})"
                    )
                else:
                    self.async_receive(kind, payload)
        except AutodartsApiError as err:
            self.connection.last_close = _error_name(err)
            _LOGGER.debug("Local event stream unavailable; HTTP polling remains active")
        except Exception:
            # Never let one bad message end realtime updates until a reload.
            self.connection.last_close = "unexpected error"
            if self._stream_error_logged:
                _LOGGER.debug(
                    "Unexpected error in the local event stream", exc_info=True
                )
            else:
                self._stream_error_logged = True
                _LOGGER.exception("Unexpected error in the local event stream")
        finally:
            live, self._stream_live = self._stream_live, False
            self.stream_connected = False
            self._end_motion_frames()
            self.update_interval = self._poll_interval()
            if connected_at is not None:
                self._suspend_tracking()
            self._update_listeners_unless_shutting_down()
        lasted = None if connected_at is None else time.monotonic() - connected_at
        if connected_at is not None:
            # Resume fast polling right away instead of after the long interval.
            await self.async_request_refresh()
        if not live and (lasted is None or lasted < RECONNECT_RESET_SECONDS):
            self._stream_attempt_failed()
        return lasted

    async def _wait_before_reconnect(self, delay: float) -> bool:
        """Wait for the next attempt; True when a poll found the board back first."""
        try:
            async with asyncio.timeout(delay):
                await self._reconnect_now.wait()
        except TimeoutError:
            return False
        self._reconnect_now.clear()
        return True

    @callback
    def _stream_attempt_failed(self) -> None:
        """Warn once when realtime events stay away although the board answers."""
        self.connection.stream_failures += 1
        if (
            self.connection.stream_failures >= STREAM_WARN_ATTEMPTS
            and self.last_update_success
            and self.data
            and not self._stream_warned
        ):
            self._stream_warned = True
            _LOGGER.warning(
                "Board Manager answers, but its realtime events at %s/api/events are "
                "unavailable; values update by polling every 2 seconds instead",
                self.client.base_url,
            )

    @callback
    def _stream_active(self) -> None:
        """The first valid notification: polling can slow down to reconciling."""
        if self._stream_live or not self.stream_connected:
            return
        self._stream_live = True
        self.connection.stream_failures = 0
        self.update_interval = self._poll_interval()
        if self._stream_warned:
            self._stream_warned = False
            _LOGGER.info("Realtime events from the Board Manager are available again")

    def _poll_interval(self) -> timedelta:
        if self.client.interface_2_1 and self.stream_connected:
            # While Board Manager 2.1 sends its motion on the socket, the read only
            # reconciles. Without those frames only /api/system reports the motion, so
            # a running detection is read as often as a board without a socket. A
            # stopped detection rests, although no frame may ever show that a socket
            # works.
            running = (self.data or {}).get("local", {}).get("running") is True
            return (
                POLL_INTERVAL
                if running and not self._motion_frames_arrive()
                else STREAM_POLL_INTERVAL_V2
            )
        if self._stream_live:
            return (
                STREAM_POLL_INTERVAL_V2
                if self.board_manager_2
                else STREAM_POLL_INTERVAL
            )
        if self.connection.failures >= OFFLINE_AFTER_FAILURES:
            return OFFLINE_POLL_INTERVAL
        return POLL_INTERVAL

    def _suspend_tracking(self) -> None:
        """Changes may be missed; the next state tells how the visit went on,
        and times a stuck takeout anew."""
        self.games.training.suspend()
        self._observed_motion = None
        self._cancel_takeout()

    def _message(
        self, kind: str, payload: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """The data field a notification updates, reduced to known values."""
        if kind == "state":
            return (
                ("local", payload) if isinstance(payload.get("running"), bool) else None
            )
        if kind == "motion_state":
            return "motion", motion_flags(payload)
        if kind == "cam_state":
            return "camera_state", camera_state_summary(payload)
        if kind == "stats":
            return "stats", stats_summary(payload)
        if kind != "cam_stats":
            return None
        index, fps = payload.get("id"), number(payload.get("fps"))
        count = self._settings.get("camera_count", 0)
        if type(index) is not int or not 0 <= index < count or fps is None:
            return None
        current = self.readings.get("camera_stats", {}).get("fps")
        frames = list(current) if isinstance(current, list) else []
        frames.extend([None] * max(0, count - len(frames)))
        frames[index] = fps
        return "camera_stats", {"fps": frames}

    @callback
    def async_receive(self, kind: str, payload: dict[str, Any]) -> None:
        """Merge a push message: a state updates every entity, a reading only
        those of its topic, see _receive_reading."""
        if (
            not isinstance(payload, dict)
            or not self._identity_valid
            or self._shutting_down
        ):
            return
        if kind == "vantage":
            self._receive_motion_frame(payload)
            return
        message = self._message(kind, payload)
        if message is None:
            return
        field, value = message
        self._stream_active()
        self._revisions[field] = self._revisions.get(field, 0) + 1
        if field != "local":
            self._receive_reading(field, value)
            return
        data = dict(self.data or {})
        previous = data.get(field)
        data[field] = value
        self._process(data, {field}, "websocket")
        self.data = data
        recovered = not self.last_update_success
        if recovered:
            _LOGGER.info("Local Board Manager is available again")
        self.last_update_success = True
        if previous != value or recovered:
            self.async_update_listeners()
        if isinstance(previous, dict) and _lifecycle(previous) != _lifecycle(value):
            # Board Manager 2 announces no camera changes; read them right after a
            # start or stop instead of waiting for the next slow poll.
            self._entry.async_create_task(
                self.hass, self.async_request_refresh(), f"{DOMAIN} camera state"
            )

    @callback
    def _receive_reading(self, field: str, value: dict[str, Any]) -> None:
        """A reading of a push message. It updates the entities of its topic
        alone; a camera alarm it raises or clears updates every entity."""
        changed = self._read({**self.readings, field: value})
        data = dict(self.data or {})
        if field in TELEMETRY:
            data["camera_problems"] = self._health.update(
                data, self.readings, time.monotonic()
            )
        else:
            self._process(data, {field}, "websocket")
        if data.get("camera_problems") != (self.data or {}).get("camera_problems"):
            self.data = data
            self.async_update_listeners()
        elif field not in TELEMETRY:
            # Frame rates arrive several times a second: the next poll shows them.
            self._publish(changed)

    @callback
    def _receive_motion_frame(self, motion: dict[str, bool]) -> None:
        """The motion of Board Manager 2.1, 30 times a second: only a value that
        changed goes further, and a frame compares with what entities show, so that
        the next one puts right whatever a read said before it."""
        self._stream_active()
        self._motion_frame_at = time.monotonic()
        if self._motion_watch is None:
            self._watch_motion_frames(None)
        if motion != self.readings.get("motion"):
            self._revisions["motion"] = self._revisions.get("motion", 0) + 1
            self._receive_reading("motion", motion)

    def _motion_frames_arrive(self) -> bool:
        at = self._motion_frame_at
        return at is not None and time.monotonic() - at < MOTION_SILENCE_SECONDS

    @callback
    def _watch_motion_frames(self, _now: datetime | None) -> None:
        """Look again every so often whether frames arrive. Once they stopped, with
        the socket open and silent or sending only the rest, the read takes over at
        once instead of with its next slow turn, so no entity stays at an old value."""
        self._motion_watch = None
        if self._motion_frames_arrive():
            self._motion_watch = async_call_later(
                self.hass, MOTION_SILENCE_SECONDS, self._watch_motion_frames
            )
            return
        self._motion_frame_at = None
        self.update_interval = self._poll_interval()
        if self.update_interval == POLL_INTERVAL:
            self._entry.async_create_task(
                self.hass, self.async_refresh(), f"{DOMAIN} motion read"
            )

    @callback
    def _end_motion_frames(self) -> None:
        self._motion_frame_at = None
        if self._motion_watch:
            self._motion_watch()
            self._motion_watch = None

    def _read(self, readings: dict[str, Any]) -> set[Topic]:
        """Keep new readings; the topics whose readings they change."""
        previous, self.readings = self.readings, readings
        return {
            topic
            for topic, keys in READINGS.items()
            if any(previous.get(key) != readings.get(key) for key in keys)
        }

    @callback
    def _publish(self, topics: set[Topic]) -> None:
        """Update the entities of the topics, in the same order every time."""
        for topic in READINGS:
            if topic in topics:
                self.topics.async_publish(topic)

    # -- the board's state and takeouts ------------------------------------------

    def _start_takeout(self, source: str) -> None:
        if not self._taking_out:
            self._taking_out = True
            self._emit("takeout_started", {}, source)

    def _finish_takeout(self, source: str) -> None:
        if self._taking_out:
            self._taking_out = False
            self._emit("takeout_finished", {}, source)

    def _process(self, data: dict[str, Any], fields: set[str], source: str) -> None:
        state = data.get("local", {})
        if "local" in fields:
            self._guarded(lambda: self._follow_visit(data, state, source))
            if self._observed_state is not None:
                self._observe_status(self._observed_state, state, source)
            self._observed_state = state
        if "motion" in fields:
            self._observe_motion(self.readings.get("motion", {}), state, source)
        self._watch_takeout(data)
        data["camera_problems"] = self._health.update(
            data, self.readings, time.monotonic()
        )

    def _observe_status(
        self, previous: dict[str, Any], state: dict[str, Any], source: str
    ) -> None:
        """Status changes and takeouts the board reports in its state."""
        status = state.get("status")
        if isinstance(status, str) and status != previous.get("status"):
            self._emit("status_changed", {"status": status}, source)
        marker = str(state.get("event") or status or "").lower()
        if (
            state.get("running") is not True
            or str(status).lower() in LIFECYCLE_STATUSES
        ):
            self._taking_out = False
        elif marker in ("takeout started", "takeout in progress"):
            self._start_takeout(source)
        elif marker == "takeout finished" or state.get("numThrows") == 0:
            self._finish_takeout(source)

    def _observe_motion(
        self, motion: dict[str, Any], state: dict[str, Any], source: str
    ) -> None:
        """A hand at the board starts a takeout; an empty board finishes it. With
        the frames of Board Manager 2.1, its state says so at the same moment, and an
        empty board comes before the hand is gone: the state alone tells."""
        previous = self._observed_motion
        if (
            previous is not None
            and not self._motion_frames_arrive()
            and state.get("running") is True
            and str(state.get("status", "")).lower() not in LIFECYCLE_STATUSES
        ):
            started = any(
                motion.get(key) is True and previous.get(key) is not True
                for key in ("isHand", "isTakeoutPartial")
            )
            count = state.get("numThrows")
            if started and type(count) is int and count > 0:
                self._start_takeout(source)
            if (
                motion.get("isTakeoutFull") is True
                and previous.get("isTakeoutFull") is not True
            ):
                self._finish_takeout(source)
        self._observed_motion = motion

    # -- stuck takeouts ----------------------------------------------------------

    def _takeout_stuck(self, data: dict[str, Any]) -> bool:
        """The board shows a takeout without darts and no hand at it, and the
        switch to free such a takeout is on."""
        state = data.get("local") or {}
        status = str(state.get("status", "")).lower()
        count = state.get("numThrows")
        return (
            self.free_stuck_takeout
            and state.get("running") is True
            and status not in LIFECYCLE_STATUSES
            and "takeout in progress" in (status, str(state.get("event", "")).lower())
            and type(count) is int
            and count == 0
            and (self.readings.get("motion") or {}).get("isHand") is not True
        )

    @callback
    def _watch_takeout(self, data: dict[str, Any]) -> None:
        """Time a stuck takeout from the state that first shows it; any other
        state, a hand at the board or the switch turned off ends the wait."""
        count = (data.get("local") or {}).get("numThrows")
        if type(count) is int and count > 0:
            # The board counts darts again, so a later takeout may be freed anew.
            self._takeout_resets = 0
        if not self._takeout_stuck(data):
            self._cancel_takeout()
        elif (
            self._takeout_unsub is None
            and self._takeout_resets < STUCK_TAKEOUT_RESETS
            and not self._shutting_down
        ):
            self._takeout_unsub = async_call_later(
                self.hass, STUCK_TAKEOUT_SECONDS, self._async_free_takeout
            )

    @callback
    def _cancel_takeout(self) -> None:
        if self._takeout_unsub:
            self._takeout_unsub()
            self._takeout_unsub = None

    async def _async_free_takeout(self, _now: datetime) -> None:
        """The takeout held a whole period: reset the board once. The state it
        reports next ends the takeout; a board still stuck gets another period."""
        self._takeout_unsub = None
        self._takeout_resets += 1
        connection = self.connection
        try:
            await self.client.command("reset")
        except AutodartsApiError as err:
            connection.failed_takeout_resets += 1
            _LOGGER.debug(
                "The board did not take the reset of a stuck takeout: %s",
                _error_name(err),
            )
        else:
            connection.takeout_resets += 1
            connection.last_takeout_reset = dt_util.utcnow()
            _LOGGER.info(
                "Board Manager kept a takeout on the empty board for %s seconds, "
                "counting no darts; reset the board (%s of %s in a row)",
                STUCK_TAKEOUT_SECONDS,
                self._takeout_resets,
                STUCK_TAKEOUT_RESETS,
            )
            # Read the board at once, as after every action.
            await self.async_request_refresh()
        self._watch_takeout(self.data or {})

    @callback
    def async_set_free_stuck_takeout(self, enabled: bool) -> None:
        """Free stuck takeouts, or leave them to the player; kept across restarts."""
        self.free_stuck_takeout = enabled
        self._takeout_resets = 0
        self._watch_takeout(self.data or {})
        self.store.save_later()
        self.async_update_listeners()

    # -- repair issues -----------------------------------------------------------

    @callback
    def _report_identity(self) -> None:
        """A repair issue explains why a board at the wrong address stays offline."""
        issue = self._issue_id("wrong_board")
        if self._identity_valid:
            ir.async_delete_issue(self.hass, DOMAIN, issue)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="wrong_board",
            translation_placeholders={"address": self.client.base_url},
        )

    @callback
    def _report_access(self) -> None:
        """The board normally needs no login; something refuses Home Assistant."""
        issue = self._issue_id("board_access_denied")
        if not self._access_denied:
            ir.async_delete_issue(self.hass, DOMAIN, issue)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="board_access_denied",
            translation_placeholders={"address": self.client.base_url},
        )

    @callback
    def _report_protocol(self) -> None:
        """Required reads that keep failing ask for an update of the integration."""
        issue = self._issue_id("unsupported_response")
        failing = self.reads.failing()
        if not failing:
            ir.async_delete_issue(self.hass, DOMAIN, issue)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="unsupported_response",
            translation_placeholders={"reads": ", ".join(failing)},
        )

    @property
    def generation(self) -> int | None:
        """Board Manager 1 (classic app) or 2 (headless board); None until known."""
        return self.board_manager.generation

    @property
    def board_manager_2(self) -> bool:
        """Entities and endpoints of the headless Board Manager 2 apply."""
        return self.board_manager.board_manager_2

    # -- polling -----------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        async with self._poll_lock:
            started = time.monotonic()
            try:
                data = await self._poll()
            finally:
                self.connection.poll_seconds = round(time.monotonic() - started, 3)
                self._report_protocol()
                self.update_interval = self._poll_interval()
        await self.client.leave_first_socket()
        return data

    async def _poll(self) -> dict[str, Any]:
        revisions = dict(self._revisions)
        # The setup waits only briefly for a board that is switched off: it
        # goes on without the board anyway.
        first, self._first_poll = self._first_poll, False
        try:
            try:
                async with asyncio.timeout(FIRST_POLL_SECONDS if first else None):
                    state = await self.client.get_state()
            except TimeoutError as err:
                raise AutodartsConnectionError("Board Manager is slow") from err
        except AutodartsApiError as err:
            if self._shutting_down:
                return self._unchanged()
            self.reads.result("/api/state", err)
            return self._poll_failed(err)
        if self._shutting_down:
            return self._unchanged()
        self.reads.result("/api/state", None)
        reads = await self.reads.read()
        if self._shutting_down:
            return self._unchanged()
        config, version = reads["config"], reads["version"]
        if config:
            self._identity_valid = (
                config.get("board_id", self.board_id) == self.board_id
            )
        self._report_identity()
        if not self._identity_valid:
            # Notifications are ignored meanwhile, so darts may be missed.
            self._suspend_tracking()
            self._offline("wrong board")
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="wrong_board")
        self._poll_succeeded()
        if config is not None:
            # A failed read keeps the last settings instead of hiding controls.
            self._settings = config
        board_manager = self.board_manager
        previous_version = board_manager.version
        board_manager.version = (version if isinstance(version, str) else None) or (
            previous_version
        )
        if board_manager.version != self._device_version:
            self._update_device_version()
        board_manager.check()
        await self.reads.read_host(board_manager.version != previous_version)
        if self._shutting_down:
            return self._unchanged()
        data, readings = dict(self.data or {}), dict(self.readings)
        if (system := reads.get("system")) is not None:
            data["system"] = {
                key: value
                for key, value in system.items()
                if key not in SYSTEM_TELEMETRY
            }
            readings["system"] = {
                key: value for key, value in system.items() if key in SYSTEM_TELEMETRY
            }
        if self.reads.host is not None:
            data["board_pc"] = self.reads.host
        fields = set()
        motion = reads["motion"]
        if self._motion_frames_arrive() and state.get("running") is True:
            # The frames are newer than any read, whose answer would only flip the
            # entities until the next frame. A stopped detection sends no more of them.
            motion = None
        for field, value in {
            "local": state,
            "stats": reads["stats"],
            "camera_stats": reads["camera_stats"],
            "motion": None if motion is None else motion_flags(motion),
            "camera_state": reads["camera_state"],
        }.items():
            values = data if field == "local" else readings
            if value is None and field in values:
                continue  # A failed optional read keeps the last known value.
            # A completed HTTP read must not roll back a newer socket message.
            if self._revisions.get(field, 0) == revisions.get(field, 0):
                values[field] = value or {}
                fields.add(field)
        data.update(settings=self._settings, version=board_manager.version)
        changed = self._read(readings)
        self._process(data, fields, "poll")
        if self.last_update_success and data == self.data:
            # Every entity updates when anything else changed; without such a
            # change only those of the readings do.
            self._publish(self._with_telemetry(changed))
        return data

    def _with_telemetry(self, topics: set[Topic]) -> set[Topic]:
        """Each poll reports the frame rates and the load anew; the quick reads of
        Board Manager 2.1 as often as the polls of 2.0, for the recorder's sake."""
        now = time.monotonic()
        if (
            self.client.interface_2_1
            and now - self._telemetry_reported < TELEMETRY_SECONDS
        ):
            return topics - {Topic.TELEMETRY}
        self._telemetry_reported = now
        return {Topic.TELEMETRY, *topics}

    @callback
    def _offline(self, error: str) -> None:
        """Count a failed poll and note when the outage began."""
        connection = self.connection
        connection.failures += 1
        connection.last_error = error
        if connection.offline_since is None:
            connection.offline_since = time.monotonic()

    def _poll_failed(self, error: AutodartsApiError) -> dict[str, Any]:
        """Keep the last values through a short hiccup; then the board is offline."""
        self._offline(_error_name(error))
        if isinstance(error, AutodartsLocalAuthError):
            if not self._access_denied:
                _LOGGER.warning(
                    "Board Manager at %s refused access (HTTP 401 or 403); it "
                    "normally needs no login, so check proxies and firewalls between "
                    "Home Assistant and the board",
                    self.client.base_url,
                )
                self._access_denied = True
                self._report_access()
        if self.stream_connected and self.data:
            # Realtime events still arrive, so a missed poll is no outage.
            _LOGGER.debug("Board Manager missed a poll; realtime events continue")
            return dict(self.data)
        self._suspend_tracking()
        if self.data and self.connection.failures <= TOLERATED_FAILURES:
            _LOGGER.debug("Board Manager missed a poll; keeping the last values")
            return dict(self.data)
        self._health = CameraHealth()
        if isinstance(error, AutodartsLocalAuthError):
            key = "board_access_denied"
        elif isinstance(error, AutodartsProtocolError):
            key = "unsupported_response"
        else:
            key = "board_unavailable"
        raise UpdateFailed(translation_domain=DOMAIN, translation_key=key) from error

    def _unchanged(self) -> dict[str, Any]:
        """The end of a poll whose read finished after async_shutdown began:
        nothing changes, so no repair issue, event or error outlives the unload."""
        if not self.last_update_success:
            # A board that was away stays away, without another error.
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="board_unavailable"
            )
        return dict(self.data or {})

    @callback
    def _poll_succeeded(self) -> None:
        connection = self.connection
        if connection.failures and not self.stream_connected:
            # The board is back: reconnect realtime events now, not after a back-off.
            self._reconnect_now.set()
        connection.failures = 0
        connection.offline_since = None
        connection.last_success = dt_util.utcnow()
        if self._access_denied:
            self._access_denied = False
            self._report_access()
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id("board_moved"))

    def diagnostics(self) -> dict[str, Any]:
        """How the connection went, without addresses, messages or secrets."""
        connection = self.connection
        since = connection.offline_since
        return {
            "consecutive_failures": connection.failures,
            "last_error": connection.last_error,
            "last_success": connection.last_success.isoformat()
            if connection.last_success
            else None,
            "offline_seconds": None
            if since is None
            else round(time.monotonic() - since),
            "last_poll_seconds": connection.poll_seconds,
            "board_manager_version": self.board_manager.version,
            "system_api_missing": self.board_manager.no_system_api is not None,
            "system_api_misses": self.board_manager.system_misses,
            "identity_valid": self._identity_valid,
            "access_denied": self._access_denied,
            "unknown_answers": sorted(self.reads.protocol_failures),
            "realtime": {
                "connected": self.stream_connected,
                "receiving": self._stream_live,
                "connects": connection.connects,
                "failed_attempts": connection.stream_failures,
                "reconnect_delay_seconds": connection.reconnect_delay,
                "last_close": connection.last_close,
                "ignored_frames": self.client.ignored_frames,
                "socket": self.client.socket_path,
                "motion_frames": self._motion_frames_arrive(),
            },
            "stuck_takeout": {
                "free": self.free_stuck_takeout,
                "waiting": self._takeout_unsub is not None,
                "resets": connection.takeout_resets,
                "failed_resets": connection.failed_takeout_resets,
                "resets_in_a_row": self._takeout_resets,
                "last_reset": connection.last_takeout_reset.isoformat()
                if connection.last_takeout_reset
                else None,
            },
        }

    @callback
    def _update_device_version(self) -> None:
        """Show a Board Manager update on the device page without a reload.

        Also the first version known: the entities of a board that was away
        at the start cleared it. Before the device exists, its entities
        create it with the version.
        """
        registry = dr.async_get(self.hass)
        device = registry.async_get_device_by_identifier(
            (DOMAIN, self.board_id), self._entry.entry_id
        )
        if device is None:
            return
        version = self._device_version = self.board_manager.version
        if device.sw_version != version:
            registry.async_update_device(device.id, sw_version=version)

    async def async_recalibrate(self) -> None:
        """Calibrate all cameras and count the corrections from zero."""
        await self.async_action(lambda: self.client.command("calibrate"))
        self.games.quality.reset()
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id("calibration"))
        # The correction rate starts over now, not with the next read.
        self.async_update_listeners()

    async def async_action(
        self, action: Callable[[], Coroutine[Any, Any, None]]
    ) -> None:
        async with self._action_lock:
            try:
                await action()
            except AutodartsEndpointMissing as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="not_supported"
                ) from err
            except AutodartsLocalAuthError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="board_access_denied"
                ) from err
            except AutodartsApiError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="action_failed"
                ) from err
            self.reads.metadata_updated = 0
            await self.async_request_refresh()
