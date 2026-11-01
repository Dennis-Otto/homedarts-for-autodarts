"""A real hand on Board Manager 2.1, and a board stuck on a hand that isn't there.

tests/fixtures/board_manager_2.1.0_hand.jsonl holds both sockets of a real board while
visits of one, two and three darts were thrown and taken out. Its _stuck_hand and
_stuck_hand_start hold the same board after its light ring was switched on with the
detection running. Of the 30 frames of the motion a second, the recordings keep those in
which a flag changed, so the tests send the others.
"""

import itertools
import json
from datetime import timedelta
from unittest.mock import PropertyMock, patch

import pytest
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.homedarts.errors import AutodartsConnectionError
from custom_components.homedarts.local_api import (
    SYSTEM_EVENTS,
    AutodartsLocalCommandError,
    board_state,
    motion_flags,
)
from custom_components.homedarts.repairs import StuckHandFlow
from custom_components.homedarts.stuck_hand import (
    MOVING_SECONDS,
    STUCK_HAND_SECONDS,
)
from custom_components.homedarts.tournament import TournamentDirector

from .local_helpers import (
    entity_id,
    hand_recording,
    setup_local,
    setup_v2,
    state,
    switch,
)
from .test_board_contract import capture_board
from .test_board_manager_2_1 import (
    A_HAND,
    answer,
    fired_kinds,
    motion_2_1,
    reread,
    running_2_1,
)
from .test_realtime import entity_events
from .test_start_game_and_quality import fix
from .test_stuck_takeout import pass_time

HAND = "hand"
STUCK = "stuck_hand"
START = "stuck_hand_start"
# What the frames of the stuck board said without a change for most of the recording,
# and what a hand at the board says, both as the real board sent them.
STUCK_FLAGS = next(
    motion_flags(row["data"]["vantage"]["motion"])
    for row in hand_recording(STUCK)
    if row["type"] == "vantage"
)
MOVING_FLAGS = motion_flags(A_HAND)
NO_HAND = {
    **STUCK_FLAGS,
    "isHand": False,
    "isTakeoutFull": False,
    "isTakeoutPartial": False,
}
STOPPING = {"event": "stopping", "running": False, "status": "stopping", "throws": []}
STOPPED = {"event": "stopped", "running": False, "status": "stopped", "throws": []}
STARTING = {"event": "starting", "running": True, "status": "starting", "throws": []}
CALIBRATING = {
    "event": "calibrationStarted",
    "running": True,
    "status": "calibrating",
    "throws": [],
}
A_DART = next(
    row["data"]["throws"]
    for row in hand_recording(HAND)
    if row["type"] == "state" and row["data"]["throws"]
)


def second_socket(rows: list[dict]) -> list[dict]:
    """What the integration follows of a recording."""
    return [row for row in rows if row["socket"] == SYSTEM_EVENTS]


def changes(rows: list[dict]) -> list[tuple[float, dict]]:
    """When the motion of a recording changed, and to what."""
    return [
        (row["t"], motion_flags(row["data"]["vantage"]["motion"]))
        for row in second_socket(rows)
        if row["type"] == "vantage"
    ]


def takeouts(rows: list[dict]) -> list[dict[str, float]]:
    """The moments of each takeout of a recording, by the state and by the flags."""
    found: list[dict[str, float]] = []
    states = [row for row in second_socket(rows) if row["type"] == "state"]
    started = [row["t"] for row in states if row["data"]["event"] == "takeoutStarted"]
    hand = [(t, flags["isHand"]) for t, flags in changes(rows)]
    rises = [t for (_, was), (t, on) in itertools.pairwise(hand) if on and not was]
    for start in started:
        rise = max(t for t in rises if t <= start)
        finished = min(
            row["t"]
            for row in states
            if row["t"] > start and row["data"]["event"] == "takeoutFinished"
        )
        fall = min(t for t, on in hand if not on and t > rise)
        found.append({"rise": rise, "start": start, "finish": finished, "fall": fall})
    return found


def unsettled(rows: list[dict]) -> list[tuple[float, float]]:
    """From when to when the picture of a recording did not stand still."""
    periods, since = [], None
    for t, flags in changes(rows):
        if not flags["isStable"] and since is None:
            since = t
        elif flags["isStable"] and since is not None:
            periods.append((since, t))
            since = None
    return periods


class Board:
    """A real board on Board Manager 2.1: its frames, and a stop and a start that clear
    the hand as they did on the real board, unless told otherwise."""

    def __init__(self, hass, coordinator, freezer) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.freezer = freezer
        self.state = board_state(running_2_1())
        self.flags: dict | None = None
        self.clears = True
        self.commands: list[str] = []
        self.errors: dict[str, Exception] = {}
        self.read_system = coordinator.client.get_system

    def show(self, state: dict) -> None:
        self.state = board_state(state)
        self.coordinator.async_receive("state", dict(self.state))

    def see(self, flags: dict) -> None:
        self.flags = flags
        self.coordinator.async_receive("vantage", dict(flags))

    async def hold(self, seconds: float) -> None:
        """The board sends what it sends now, 30 frames a second, for so many seconds."""
        for frame in range(round(seconds * 30)):
            self.freezer.tick(timedelta(seconds=1 / 30))
            if self.flags:
                self.coordinator.async_receive("vantage", dict(self.flags))
            if frame % 30 == 29:
                async_fire_time_changed(self.hass)
                await self.hass.async_block_till_done()
        async_fire_time_changed(self.hass)
        await self.hass.async_block_till_done()

    async def play(self, rows: list[dict]) -> None:
        """The second socket of a recording at the moments it was recorded."""
        clock = rows[0]["t"]
        for row in second_socket(rows):
            await self.hold(row["t"] - clock)
            clock = row["t"]
            if row["type"] == "state":
                self.show(row["data"])
            elif flags := motion_flags(row["data"]["vantage"]["motion"]):
                # A frame without the readings says nothing.
                self.see(flags)
            await self.hass.async_block_till_done()

    async def get_state(self) -> dict:
        return dict(self.state)

    async def get_system(self) -> dict:
        """A stopped detection has no readings, as on the real board."""
        system = await self.read_system()
        running = self.state.get("running") is True
        return {**system, "motion": dict(self.flags or {}) if running else {}}

    async def command(self, name: str) -> None:
        self.commands.append(name)
        if name in self.errors:
            raise self.errors[name]
        if name == "stop":
            self.show(STOPPING)
            self.show(STOPPED)
        if name == "start":
            self.show(STARTING)
            self.show(running_2_1())
            if self.clears:
                self.see(NO_HAND)


@pytest.fixture
async def at_board(hass, aioclient_mock, freezer):
    """A running detection on 2.1 with its socket open and nothing on the board."""
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    coordinator = entry.runtime_data.local
    coordinator.stream_connected = True
    board = Board(hass, coordinator, freezer)
    with (
        patch.object(coordinator.client, "get_state", board.get_state),
        patch.object(coordinator.client, "get_system", board.get_system),
        patch.object(coordinator.client, "command", board.command),
    ):
        yield entry, coordinator, board


def notice(hass, entry):
    return ir.async_get(hass).async_get_issue(
        "homedarts", f"stuck_hand_{entry.entry_id}"
    )


def stuck_events(fired: list[tuple[dict, object]]) -> list[str]:
    return [
        attributes["event_type"]
        for attributes, _ in fired
        if attributes["event_type"].startswith("stuck_hand")
    ]


def events_of(hass) -> list[tuple[dict, object]]:
    event_id = entity_id(hass, "event", "board_events")
    return entity_events(
        hass, event_id, entity_id(hass, "binary_sensor", "hand_detected")
    )


async def stuck_at(board: Board, seconds: float = STUCK_HAND_SECONDS + 1) -> None:
    board.see(STUCK_FLAGS)
    await board.hold(seconds)


# -- the real hand -----------------------------------------------------------------------


def test_the_recordings_keep_nothing_of_the_board():
    for name in (HAND, STUCK, START):
        rows = hand_recording(name)
        frames = [{"type": row["type"], "data": row["data"]} for row in rows]
        assert capture_board.secrets([frames]) == {}
        assert capture_board.redact(frames, {}) == frames


@pytest.mark.parametrize("visit", [0, 1, 2], ids=["one dart", "two", "three"])
def test_the_state_starts_a_takeout_right_after_the_hand_rises(visit):
    # Why a takeout needs no help from a rising hand: after one or two darts as well,
    # where the board had no need of a takeout, it sends takeoutStarted by itself.
    takeout = takeouts(hand_recording(HAND))[visit]
    assert 0 <= takeout["start"] - takeout["rise"] <= 0.3
    # The hand goes with takeoutFinished, a moment before or after it.
    assert abs(takeout["fall"] - takeout["finish"]) < 0.05
    # A takeout lasts seconds, some shorter than the read of 2 seconds.
    assert 1 <= takeout["finish"] - takeout["start"] <= 3


def test_the_three_takeouts_of_the_recording_are_found():
    assert len(takeouts(hand_recording(HAND))) == 3


def test_one_takeout_of_the_recording_is_shorter_than_the_read_of_2_seconds():
    lengths = [t["fall"] - t["rise"] for t in takeouts(hand_recording(HAND))]
    assert min(lengths) < 2 < max(lengths)


async def test_each_visit_of_the_recording_shows_its_takeout_and_its_hand(
    hass, at_board
):
    _, _, board = at_board
    fired = events_of(hass)
    hand = {}
    rows = hand_recording(HAND)
    await board.play(rows)
    for attributes, sensor in fired:
        hand.setdefault(attributes["event_type"], []).append(sensor)
    assert [
        kind
        for kind in fired_kinds(fired)
        if kind[0] in ("dart_detected", "takeout_started", "takeout_finished")
    ] == [
        ("dart_detected", "S6"),
        ("takeout_started", None),
        ("takeout_finished", None),
        ("dart_detected", "S5"),
        ("dart_detected", "S10"),
        ("takeout_started", None),
        ("takeout_finished", None),
        ("dart_detected", "S18"),
        ("dart_detected", "S5"),
        ("dart_detected", "S12"),
        ("takeout_started", None),
        ("takeout_finished", None),
    ]
    # Hand detected is on when Takeout started reaches an automation, in all three.
    assert hand["takeout_started"] == ["on", "on", "on"]
    assert state(hass, "binary_sensor", "hand_detected") == "off"
    assert stuck_events(fired) == []


async def test_hand_detected_turns_on_and_off_with_each_takeout_of_the_recording(
    hass, at_board
):
    _, _, board = at_board
    rows = hand_recording(HAND)
    seen = []
    for row in second_socket(rows):
        if row["type"] == "vantage":
            board.see(motion_flags(row["data"]["vantage"]["motion"]))
            await hass.async_block_till_done()
            sensor = state(hass, "binary_sensor", "hand_detected")
            if not seen or seen[-1][1] != sensor:
                seen.append((row["t"], sensor))
    # The moments of the recording, also of the takeout of 1.2 seconds in the middle.
    assert [t for t, sensor in seen if sensor == "on"] == [29.791, 39.056, 49.92]
    assert [t for t, sensor in seen if sensor == "off"] == [
        0.226,
        31.822,
        40.284,
        52.413,
    ]


def test_what_only_the_first_socket_sends_is_overtaken_at_once():
    # One socket is enough: the first holds two frames the second does not, each followed
    # within 5 ms by the frame in which both agree, so nothing of them can last.
    rows = hand_recording(HAND)
    states = [row for row in rows if row["type"] == "state"]
    first = [row for row in states if row["socket"] != SYSTEM_EVENTS]
    second = [row["data"] for row in states if row["socket"] == SYSTEM_EVENTS]
    alone = [
        (row, after)
        for row, after in itertools.pairwise(first)
        if row["data"] not in second
    ]
    assert [row["data"]["event"] for row, _ in alone] == ["started", "takeoutStarted"]
    for row, after in alone:
        assert after["t"] - row["t"] < 0.005
        assert after["data"] in second
    # And all the second sends reached the first.
    assert all(data in [row["data"] for row in first] for data in second)


def test_the_recordings_keep_a_moving_hand_and_a_stuck_one_apart():
    # The picture of a hand that pulled darts stayed unsettled for over a second at a
    # time, that of the stuck board and of a landing dart for less.
    rows = hand_recording(HAND)
    periods = unsettled(rows)
    for takeout in takeouts(rows):
        at_takeout = [
            until - since
            for since, until in periods
            if since <= takeout["fall"] and until >= takeout["rise"]
        ]
        assert max(at_takeout) > MOVING_SECONDS
    darts = [
        until - since
        for since, until in periods
        if not any(
            since <= takeout["fall"] + 0.5 and until >= takeout["rise"] - 0.5
            for takeout in takeouts(rows)
        )
        and until < 53
    ]
    assert darts
    assert max(darts) < MOVING_SECONDS
    stuck = unsettled(hand_recording(STUCK))
    assert stuck
    assert max(until - since for since, until in stuck) < MOVING_SECONDS
    # A minute leaves plenty of margin over a real takeout.
    assert all(t["fall"] - t["rise"] < STUCK_HAND_SECONDS / 10 for t in takeouts(rows))


# -- the board stuck on a hand --------------------------------------------------------


async def test_the_recorded_stuck_board_gets_its_notice_after_a_minute(hass, at_board):
    entry, coordinator, board = at_board
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id(hass, "switch", "free_stuck_takeout")},
        blocking=True,
    )
    fired = events_of(hass)
    # The first seconds: a frame without readings, then the takeout on the empty board.
    await board.play(hand_recording(START))
    assert ("takeout_started", None) in fired_kinds(fired)
    rows = hand_recording(STUCK)
    start = second_socket(rows)
    before = [row for row in start if row["t"] < 9]
    later = [row for row in start if row["t"] >= 9]
    # Each of the short movements of the recording leaves the wait running.
    await board.play(before)
    await board.hold(59 - before[-1]["t"])
    assert notice(hass, entry) is None
    assert coordinator.diagnostics()["stuck_hand"]["waiting"] is True
    await board.hold(2)
    found = notice(hass, entry)
    assert found.translation_key == "stuck_hand"
    assert found.is_fixable is True
    assert stuck_events(fired) == ["stuck_hand"]
    assert fired[-1][0]["source"] == "websocket"
    assert coordinator.diagnostics()["stuck_hand"]["seen"] is True
    # A calibration of all three cameras moves the state, while the flags stay.
    await board.hold(later[0]["t"] - 61)
    await board.play(later)
    assert board.state["status"] == "Throw"
    assert notice(hass, entry) is not None
    await board.hold(300)
    assert notice(hass, entry) is not None
    assert stuck_events(fired) == ["stuck_hand"]
    # With the switch off, the integration leaves the board alone.
    assert board.commands == []
    # It goes away when the state clears.
    board.see(NO_HAND)
    await hass.async_block_till_done()
    assert notice(hass, entry) is None
    assert stuck_events(fired) == ["stuck_hand", "stuck_hand_cleared"]
    assert coordinator.diagnostics()["stuck_hand"]["seen"] is False


async def test_a_stuck_hand_on_an_empty_board_restarts_the_detection_once(
    hass, at_board
):
    entry, coordinator, board = at_board
    fired = events_of(hass)
    await stuck_at(board)
    assert board.commands == ["stop", "start"]
    diagnostics = coordinator.diagnostics()["stuck_hand"]
    assert diagnostics["restarts"] == 1
    assert diagnostics["failed_restarts"] == 0
    assert diagnostics["last_restart"] is not None
    # The stop and the start cleared it, as on the real board.
    assert notice(hass, entry) is None
    assert stuck_events(fired) == ["stuck_hand", "stuck_hand_cleared"]
    assert state(hass, "binary_sensor", "hand_detected") == "off"


async def test_a_restart_that_clears_nothing_comes_once(hass, at_board):
    entry, coordinator, board = at_board
    board.clears = False
    fired = events_of(hass)
    await stuck_at(board)
    await board.hold(600)
    assert board.commands == ["stop", "start"]
    assert notice(hass, entry) is not None
    assert stuck_events(fired) == ["stuck_hand"]
    assert coordinator.diagnostics()["stuck_hand"]["restarts"] == 1


async def test_a_hand_that_comes_back_within_a_minute_gets_no_second_restart(
    hass, at_board
):
    _, _, board = at_board
    await stuck_at(board)
    assert board.commands == ["stop", "start"]
    # The detection came back, and the hand with it, seconds later.
    await board.hold(STUCK_HAND_SECONDS - 10)
    await stuck_at(board)
    assert board.commands == ["stop", "start"]
    # Gone for a minute is a new occurrence, which may get a restart of its own.
    board.see(NO_HAND)
    await board.hold(STUCK_HAND_SECONDS + 1)
    await stuck_at(board)
    assert board.commands == ["stop", "start", "stop", "start"]


async def test_a_hand_that_moves_is_no_stuck_hand(hass, at_board):
    entry, _, board = at_board
    fired = events_of(hass)
    # For five minutes, the rhythm of a takeout of the recording.
    for _ in range(150):
        board.see(MOVING_FLAGS)
        await board.hold(MOVING_SECONDS + 0.5)
        board.see(STUCK_FLAGS)
        await board.hold(0.5)
    assert notice(hass, entry) is None
    assert stuck_events(fired) == []
    assert board.commands == []


async def test_a_dart_that_lands_does_not_start_the_wait_anew(hass, at_board):
    entry, _, board = at_board
    board.clears = False
    await stuck_at(board, 30)
    # Six darts were thrown at the stuck board. Each shakes the picture for a moment.
    board.see({**STUCK_FLAGS, "isStable": False})
    await board.hold(MOVING_SECONDS / 2)
    board.see(STUCK_FLAGS)
    await board.hold(STUCK_HAND_SECONDS - 30)
    assert notice(hass, entry) is not None


async def test_someone_who_moves_as_the_wait_ends_gets_another_minute(hass, at_board):
    entry, coordinator, board = at_board
    board.clears = False
    await stuck_at(board, STUCK_HAND_SECONDS - MOVING_SECONDS / 2)
    board.see({**STUCK_FLAGS, "isStable": False})
    # The wait is over meanwhile, with the picture still moving.
    await board.hold(2 * MOVING_SECONDS)
    assert notice(hass, entry) is None
    assert coordinator.diagnostics()["stuck_hand"]["waiting"] is True
    board.see(STUCK_FLAGS)
    await board.hold(STUCK_HAND_SECONDS - 1)
    assert notice(hass, entry) is None
    await board.hold(2)
    assert notice(hass, entry) is not None


@pytest.mark.parametrize(
    "keep",
    ["switch off", "a dart on the board", "a game", "a tournament"],
)
async def test_the_detection_stays_as_it_is_until_it_is_safe(hass, at_board, keep):
    entry, _, board = at_board
    board.clears = False
    tournament = patch.object(
        TournamentDirector, "running", new_callable=PropertyMock, return_value=True
    )
    if keep == "switch off":
        await switch(hass, "free_stuck_takeout", False)
    if keep == "a dart on the board":
        board.show({**running_2_1(), "throws": A_DART})
    if keep == "a game":
        await hass.services.async_call(
            "homedarts", "start_game", {"game": "301"}, blocking=True
        )
    if keep == "a tournament":
        tournament.start()
    await stuck_at(board)
    assert notice(hass, entry) is not None
    assert board.commands == []
    # Then it's safe: the next that the integration hears of the board restarts it, once.
    if keep == "switch off":
        await switch(hass, "free_stuck_takeout", True)
    if keep == "a dart on the board":
        board.show(running_2_1())
    if keep == "a game":
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id(hass, "select", "practice_game"), "option": "off"},
            blocking=True,
        )
    if keep == "a tournament":
        tournament.stop()
    await board.hold(11)
    assert board.commands == ["stop", "start"]
    await board.hold(11)
    assert board.commands == ["stop", "start"]


async def test_a_game_on_another_board_keeps_the_detection_as_it_is(hass, at_board):
    _, coordinator, _ = at_board
    empty = board_state(running_2_1())
    assert coordinator._may_restart_detection(empty) is True
    coordinator.games.host = object()
    assert coordinator._may_restart_detection(empty) is False
    coordinator.games.host = None


async def test_a_restart_starts_only_after_the_stop_ended(hass, at_board):
    _, coordinator, board = at_board
    answers = iter(
        [
            board_state(STOPPING),
            AutodartsConnectionError("hiccup"),
            board_state(STOPPED),
        ]
    )
    asked: list[str] = []

    async def stopping():
        asked.append(f"read after {len(board.commands)} commands")
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    with (
        patch.object(coordinator.client, "get_state", stopping),
        patch("custom_components.homedarts.local_coordinator.STOP_READ_SECONDS", 0),
    ):
        await coordinator.async_restart_detection()
    # The third read shows the end of the stop, and the start follows it.
    assert asked == ["read after 1 commands"] * 3
    assert board.commands == ["stop", "start"]


async def test_a_stop_that_never_shows_its_end_still_gets_its_start(hass, at_board):
    _, coordinator, board = at_board
    with (
        patch("custom_components.homedarts.local_coordinator.STOP_READ_SECONDS", 0),
        patch.object(board, "show"),
    ):
        await coordinator.async_restart_detection()
    assert board.commands == ["stop", "start"]


@pytest.mark.parametrize("fails", ["stop", "start"])
async def test_a_restart_the_board_refuses_comes_once_and_says_so(
    hass, at_board, fails, caplog
):
    entry, coordinator, board = at_board
    board.errors[fails] = AutodartsLocalCommandError("refused")
    await stuck_at(board)
    await board.hold(300)
    assert board.commands[-1] == fails
    assert board.commands.count(fails) == 1
    diagnostics = coordinator.diagnostics()["stuck_hand"]
    assert diagnostics["restarts"] == 0
    assert diagnostics["failed_restarts"] == 1
    assert notice(hass, entry) is not None
    assert "start the detection" in caplog.text


async def test_a_stopped_detection_ends_the_wait_and_keeps_the_notice(hass, at_board):
    entry, coordinator, board = at_board
    await switch(hass, "free_stuck_takeout", False)
    await stuck_at(board, 30)
    board.show(STOPPED)
    assert coordinator.diagnostics()["stuck_hand"]["waiting"] is False
    # Nothing is said of the hand while the detection is stopped.
    board.flags = None
    await board.hold(STUCK_HAND_SECONDS + 1)
    assert notice(hass, entry) is None
    board.show(running_2_1())
    await stuck_at(board)
    assert notice(hass, entry) is not None
    # A stop says nothing of the hand, so the notice stays until a start shows it gone.
    board.show(STOPPED)
    board.flags = None
    await board.hold(5)
    assert notice(hass, entry) is not None
    board.show(running_2_1())
    board.see(NO_HAND)
    await hass.async_block_till_done()
    assert notice(hass, entry) is None


async def test_a_calibration_starts_the_wait_anew(hass, at_board):
    entry, _, board = at_board
    board.clears = False
    await stuck_at(board, STUCK_HAND_SECONDS - 5)
    board.show(CALIBRATING)
    await board.hold(1)
    board.show(running_2_1())
    await board.hold(STUCK_HAND_SECONDS - 5)
    assert notice(hass, entry) is None
    await board.hold(6)
    assert notice(hass, entry) is not None
    # Restarted, not cleared: the wait goes on for what the restart left.
    assert board.commands == ["stop", "start"]


async def test_a_lost_connection_starts_the_wait_anew(hass, at_board):
    entry, coordinator, board = at_board
    await stuck_at(board, 30)
    coordinator._suspend_tracking()
    assert coordinator.diagnostics()["stuck_hand"]["waiting"] is False
    await board.hold(STUCK_HAND_SECONDS - 25)
    assert notice(hass, entry) is None
    board.show(running_2_1())
    assert coordinator.diagnostics()["stuck_hand"]["waiting"] is True


async def test_the_reads_alone_find_a_stuck_hand_without_frames(
    hass, aioclient_mock, freezer
):
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    coordinator = entry.runtime_data.local
    await switch(hass, "free_stuck_takeout", False)
    fired = events_of(hass)
    answer(aioclient_mock, "/api/system", json=motion_2_1(**STUCK_FLAGS))
    await reread(hass, coordinator)
    for _ in range(STUCK_HAND_SECONDS // 2):
        assert notice(hass, entry) is None
        await pass_time(hass, freezer, 2)
    await pass_time(hass, freezer, 2)
    assert notice(hass, entry) is not None
    assert stuck_events(fired) == ["stuck_hand"]
    assert fired[-1][0]["source"] == "poll"
    answer(aioclient_mock, "/api/system", json=motion_2_1(**NO_HAND))
    await reread(hass, coordinator)
    assert notice(hass, entry) is None
    assert stuck_events(fired) == ["stuck_hand", "stuck_hand_cleared"]
    assert fired[-1][0]["source"] == "poll"


async def test_a_read_that_fails_ends_the_wait(hass, aioclient_mock, freezer):
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    coordinator = entry.runtime_data.local
    coordinator.stream_connected = True
    answer(aioclient_mock, "/api/system", json=motion_2_1(**STUCK_FLAGS))
    await reread(hass, coordinator)
    assert coordinator.diagnostics()["stuck_hand"]["waiting"] is True
    # The socket stays open and silent, while the board answers no read.
    answer(aioclient_mock, "/api/state", status=500)
    await reread(hass, coordinator)
    coordinator.async_receive("state", board_state(running_2_1()))
    assert coordinator.diagnostics()["stuck_hand"]["waiting"] is False
    await pass_time(hass, freezer, STUCK_HAND_SECONDS + 1)
    assert notice(hass, entry) is None


async def test_a_frame_without_the_hand_flag_says_nothing_of_it(hass, at_board):
    entry, coordinator, board = at_board
    board.clears = False
    await stuck_at(board)
    assert notice(hass, entry) is not None
    # A read of a detection that only starts may have no readings.
    coordinator.async_receive("motion_state", {})
    await hass.async_block_till_done()
    assert notice(hass, entry) is not None
    assert coordinator.diagnostics()["stuck_hand"]["seen"] is True


@pytest.mark.parametrize("version", ["1.0.7", "2.0.2"])
async def test_an_earlier_board_manager_stays_as_it_is(
    hass, aioclient_mock, freezer, version
):
    setup = setup_local if version == "1.0.7" else setup_v2
    entry = await setup(hass, aioclient_mock, recording=version)
    coordinator = entry.runtime_data.local
    fired = events_of(hass)
    with patch.object(coordinator.client, "command") as command:
        for _ in range(5):
            coordinator.async_receive("motion_state", STUCK_FLAGS)
            await pass_time(hass, freezer, STUCK_HAND_SECONDS)
        assert notice(hass, entry) is None
        assert stuck_events(fired) == []
        command.assert_not_called()
    assert coordinator.diagnostics()["stuck_hand"]["waiting"] is False


async def test_an_unload_ends_the_wait_and_removes_the_notice(hass, at_board):
    entry, coordinator, board = at_board
    board.clears = False
    await stuck_at(board)
    assert notice(hass, entry) is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert notice(hass, entry) is None
    assert coordinator.diagnostics()["stuck_hand"]["waiting"] is False
    # Nothing starts a restart any more.
    board.commands.clear()
    coordinator._hand.restarted = False
    coordinator._watch_hand(coordinator.data)
    await hass.async_block_till_done()
    assert board.commands == []


# -- the repair -----------------------------------------------------------------------


async def test_the_notice_restarts_the_detection_when_confirmed(
    hass, at_board, hass_client
):
    entry, _, board = at_board
    await switch(hass, "free_stuck_takeout", False)
    await stuck_at(board)
    assert board.commands == []
    result = await fix(hass, hass_client, f"stuck_hand_{entry.entry_id}")
    assert result["type"] == "create_entry"
    assert board.commands == ["stop", "start"]
    assert notice(hass, entry) is None


async def test_the_confirmed_notice_finishes_the_takeout_that_held_the_board(
    hass, at_board, hass_client
):
    entry, _, board = at_board
    await switch(hass, "free_stuck_takeout", False)
    fired = events_of(hass)
    await board.play(hand_recording(START))
    await stuck_at(board)
    assert ("takeout_finished", None) not in fired_kinds(fired)
    await fix(hass, hass_client, f"stuck_hand_{entry.entry_id}")
    assert fired_kinds(fired).count(("takeout_finished", None)) == 1


async def test_a_restart_finishes_the_takeout_that_held_the_board(hass, at_board):
    _, _, board = at_board
    fired = events_of(hass)
    await board.play(hand_recording(START))
    assert ("takeout_started", None) in fired_kinds(fired)
    await stuck_at(board)
    assert board.commands == ["stop", "start"]
    assert fired_kinds(fired).count(("takeout_finished", None)) == 1


async def test_a_refused_stop_finishes_no_takeout(hass, at_board):
    _, coordinator, board = at_board
    fired = events_of(hass)
    await board.play(hand_recording(START))
    board.errors["stop"] = AutodartsLocalCommandError("refused")
    await stuck_at(board)
    assert board.commands == ["stop"]
    assert ("takeout_finished", None) not in fired_kinds(fired)
    # What the restart left behind doesn't change what a later stop does.
    board.show(STOPPED)
    await hass.async_block_till_done()
    assert ("takeout_finished", None) not in fired_kinds(fired)
    assert coordinator.diagnostics()["stuck_hand"]["failed_restarts"] == 1


async def test_a_hand_that_stays_after_the_repair_brings_the_notice_back(
    hass, at_board, hass_client
):
    entry, _, board = at_board
    await switch(hass, "free_stuck_takeout", False)
    board.clears = False
    fired = events_of(hass)
    await stuck_at(board)
    await fix(hass, hass_client, f"stuck_hand_{entry.entry_id}")
    assert notice(hass, entry) is None
    await board.hold(STUCK_HAND_SECONDS + 1)
    assert notice(hass, entry) is not None
    assert stuck_events(fired) == ["stuck_hand"]


async def test_a_restart_the_board_refuses_keeps_the_repair_open(
    hass, at_board, hass_client
):
    entry, _, board = at_board
    await switch(hass, "free_stuck_takeout", False)
    await stuck_at(board)
    board.errors["stop"] = AutodartsLocalCommandError("refused")
    result = await fix(hass, hass_client, f"stuck_hand_{entry.entry_id}")
    assert result["type"] == "abort" and result["reason"] == "restart_failed"
    assert notice(hass, entry) is not None


async def test_the_repair_of_a_board_that_is_gone_says_so(hass):
    flow = StuckHandFlow("gone")
    flow.hass, flow.handler, flow.issue_id = hass, "homedarts", "stuck_hand_gone"
    assert (await flow.async_step_init())["step_id"] == "confirm"
    result = await flow.async_step_confirm({})
    assert result["type"] == "abort" and result["reason"] == "board_unavailable"


def test_the_recordings_stay_in_order_and_small():
    for name in (HAND, STUCK, START):
        rows = hand_recording(name)
        assert rows == sorted(rows, key=lambda row: row["t"])
        assert all(set(row) == {"socket", "t", "type", "data"} for row in rows)
        assert len(json.dumps(rows)) < 64 * 1024
