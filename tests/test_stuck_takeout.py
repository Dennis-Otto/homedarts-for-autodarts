"""A takeout the board never finishes: Board Manager 2.0.2 sometimes starts a
takeout again on the empty board and keeps it, counting no darts until a reset."""

import asyncio
import logging
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.homedarts.errors import AutodartsConnectionError
from custom_components.homedarts.local_api import AutodartsLocalCommandError
from custom_components.homedarts.storage import storage_key

from .local_helpers import (
    BASE,
    T20,
    board,
    entity_id,
    local_entry_data,
    mock_board,
    record,
    setup_local,
    setup_v2,
    state,
    switch,
    until,
)

STUCK = board(status="Takeout in progress", event="Takeout started")
# How the board reports the reset: no darts, waiting for the next one.
FREED = board(event="Manual reset")
NO_HAND = {
    "isStable": True,
    "isHand": False,
    "isTakeoutPartial": False,
    "isTakeoutFull": False,
}
HAND = {**NO_HAND, "isStable": False, "isHand": True}
LOGGER = "custom_components.homedarts.local_coordinator"


class Board:
    """A board whose reads answer like its socket and whose reset frees a stuck
    takeout, unless told otherwise."""

    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator
        self.state = board()
        self.motion = NO_HAND
        self.frees = True
        self.reset_error: Exception | None = None
        self.read_error: Exception | None = None
        self.commands: list[str] = []

    def show(self, state: dict) -> None:
        self.state = state
        self.coordinator.async_receive("state", deepcopy(state))

    def feel(self, motion: dict) -> None:
        self.motion = motion
        self.coordinator.async_receive("motion_state", dict(motion))

    async def get_state(self) -> dict:
        if self.read_error:
            raise self.read_error
        return deepcopy(self.state)

    async def get_motion_state(self) -> dict:
        return dict(self.motion)

    async def command(self, name: str) -> None:
        self.commands.append(name)
        if self.reset_error:
            raise self.reset_error
        if self.frees:
            self.show(FREED)


@pytest.fixture
async def at_board(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    simulated = Board(coordinator)
    client = coordinator.client
    with (
        patch.object(client, "get_state", simulated.get_state),
        patch.object(client, "get_motion_state", simulated.get_motion_state),
        patch.object(client, "command", simulated.command),
    ):
        yield entry, coordinator, simulated


async def pass_time(hass, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def messages(caplog, level: int, text: str) -> int:
    return sum(
        record.name == LOGGER and record.levelno == level and text in record.message
        for record in caplog.records
    )


def takeouts(fired) -> list[str]:
    return [
        kind for kind, _ in fired if kind in ("takeout_started", "takeout_finished")
    ]


async def test_a_stuck_takeout_is_freed_after_ten_seconds(
    hass, at_board, freezer, caplog
):
    caplog.set_level(logging.INFO, LOGGER)
    _, coordinator, simulated = at_board
    fired = record(hass, coordinator)
    simulated.show(STUCK)
    await pass_time(hass, freezer, 9)
    assert simulated.commands == []
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is True
    await pass_time(hass, freezer, 2)
    assert simulated.commands == ["reset"]
    # The board reports the empty board after the reset, which ends the takeout.
    assert takeouts(fired) == ["takeout_started", "takeout_finished"]
    assert state(hass, "sensor", "local_status") == "throw"
    assert messages(caplog, logging.INFO, "reset the board (1 of 3 in a row)") == 1
    assert coordinator.diagnostics()["stuck_takeout"] == {
        "free": True,
        "waiting": False,
        "resets": 1,
        "failed_resets": 0,
        "resets_in_a_row": 1,
        "last_reset": coordinator.connection.last_takeout_reset.isoformat(),
    }
    # A board that is free again is left alone.
    await pass_time(hass, freezer, 60)
    assert simulated.commands == ["reset"]
    assert takeouts(fired) == ["takeout_started", "takeout_finished"]


async def test_the_reset_goes_to_the_board(hass, aioclient_mock, freezer):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    aioclient_mock.post(f"{BASE}/api/reset")
    with patch.object(coordinator.client, "get_state", return_value=STUCK):
        coordinator.async_receive("state", STUCK)
        await pass_time(hass, freezer, 11)
    resets = [
        (method, str(url))
        for method, url, *_ in aioclient_mock.mock_calls
        if str(url).endswith("/api/reset")
    ]
    assert resets == [("POST", f"{BASE}/api/reset")]


@pytest.mark.parametrize(
    "stuck",
    [STUCK, board(event="Takeout in progress"), board(status="Takeout in progress")],
    ids=["status and event", "event", "status"],
)
async def test_the_status_or_the_event_tells_the_takeout(
    hass, at_board, freezer, stuck
):
    _, _, simulated = at_board
    simulated.show(stuck)
    await pass_time(hass, freezer, 11)
    assert simulated.commands == ["reset"]


@pytest.mark.parametrize(
    "other",
    [
        board(T20, status="Takeout in progress", event="Takeout started"),
        {**STUCK, "running": False},
        board(status="Calibrating", event="Takeout in progress"),
        board(status="Takeout", event="Takeout started"),
        {key: value for key, value in STUCK.items() if key != "numThrows"},
    ],
    ids=["darts on the board", "stopped", "calibrating", "takeout", "no count"],
)
async def test_other_states_are_no_stuck_takeout(hass, at_board, freezer, other):
    _, coordinator, simulated = at_board
    simulated.show(other)
    await pass_time(hass, freezer, 60)
    assert simulated.commands == []
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is False


@pytest.mark.parametrize(
    "change",
    [board(), board(T20), board(status="Stopped", running=False)],
    ids=["takeout finished", "a dart", "detection stopped"],
)
async def test_a_change_within_ten_seconds_ends_the_wait(
    hass, at_board, freezer, change
):
    _, _, simulated = at_board
    simulated.show(STUCK)
    await pass_time(hass, freezer, 5)
    simulated.show(change)
    await pass_time(hass, freezer, 60)
    assert simulated.commands == []


async def test_the_wait_starts_with_the_first_state_that_shows_it(
    hass, at_board, freezer
):
    _, _, simulated = at_board
    simulated.show(STUCK)
    await pass_time(hass, freezer, 6)
    # The board repeats the state; reads in between found it, too.
    simulated.show(STUCK)
    await pass_time(hass, freezer, 5)
    assert simulated.commands == ["reset"]


async def test_a_hand_at_the_board_waits(hass, at_board, freezer):
    _, _, simulated = at_board
    simulated.show(STUCK)
    await pass_time(hass, freezer, 5)
    simulated.feel(HAND)
    await pass_time(hass, freezer, 60)
    assert simulated.commands == []
    # Ten seconds after the hand has gone.
    simulated.feel(NO_HAND)
    await pass_time(hass, freezer, 9)
    assert simulated.commands == []
    await pass_time(hass, freezer, 2)
    assert simulated.commands == ["reset"]


async def test_a_board_that_stays_stuck_is_reset_three_times_a_period_apart(
    hass, at_board, freezer, caplog
):
    caplog.set_level(logging.INFO, LOGGER)
    _, coordinator, simulated = at_board
    simulated.frees = False
    simulated.show(STUCK)
    await pass_time(hass, freezer, 11)
    assert simulated.commands == ["reset"]
    # Never more than one reset in ten seconds.
    await pass_time(hass, freezer, 5)
    assert simulated.commands == ["reset"]
    await pass_time(hass, freezer, 6)
    await pass_time(hass, freezer, 11)
    assert simulated.commands == ["reset"] * 3
    assert messages(caplog, logging.INFO, "reset the board (3 of 3 in a row)") == 1
    # Then the board is left to its player.
    await pass_time(hass, freezer, 300)
    assert simulated.commands == ["reset"] * 3
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is False
    # A dart shows the board counts again: a later stuck takeout is freed anew.
    simulated.show(board(T20))
    simulated.show(STUCK)
    await pass_time(hass, freezer, 11)
    assert simulated.commands == ["reset"] * 4
    assert coordinator.diagnostics()["stuck_takeout"]["resets_in_a_row"] == 1


async def test_a_failed_reset_is_tried_again_a_period_later(
    hass, at_board, freezer, caplog
):
    caplog.set_level(logging.DEBUG, LOGGER)
    _, coordinator, simulated = at_board
    simulated.reset_error = AutodartsLocalCommandError("Board rejected command")
    simulated.show(STUCK)
    await pass_time(hass, freezer, 11)
    assert simulated.commands == ["reset"]
    assert messages(caplog, logging.DEBUG, "AutodartsLocalCommandError") == 1
    assert messages(caplog, logging.INFO, "reset the board") == 0
    simulated.reset_error = None
    await pass_time(hass, freezer, 11)
    assert simulated.commands == ["reset", "reset"]
    diagnostics = coordinator.diagnostics()["stuck_takeout"]
    assert (diagnostics["resets"], diagnostics["failed_resets"]) == (1, 1)


async def test_a_board_without_the_route_counts_a_failed_reset(
    hass, aioclient_mock, freezer
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    aioclient_mock.post(f"{BASE}/api/reset", status=404)
    with patch.object(coordinator.client, "get_state", return_value=STUCK):
        coordinator.async_receive("state", STUCK)
        await pass_time(hass, freezer, 11)
    diagnostics = coordinator.diagnostics()["stuck_takeout"]
    assert (diagnostics["resets"], diagnostics["failed_resets"]) == (0, 1)


async def test_a_board_out_of_sight_is_not_reset(hass, at_board, freezer):
    _, coordinator, simulated = at_board
    simulated.show(STUCK)
    await pass_time(hass, freezer, 5)
    # A failed read ends the wait: the board may have changed meanwhile.
    simulated.read_error = AutodartsConnectionError("Board away")
    await coordinator.async_refresh()
    await pass_time(hass, freezer, 30)
    assert simulated.commands == []
    # Back and still stuck: ten seconds from the first read that shows it.
    simulated.read_error = None
    await coordinator.async_refresh()
    await pass_time(hass, freezer, 9)
    assert simulated.commands == []
    await pass_time(hass, freezer, 2)
    assert simulated.commands == ["reset"]


async def test_the_switch_turns_it_off_and_on(hass, at_board, freezer):
    _, coordinator, simulated = at_board
    switch_id = entity_id(hass, "switch", "free_stuck_takeout")
    entry = er.async_get(hass).async_get(switch_id)
    assert entry.entity_category == er.EntityCategory.CONFIG
    assert state(hass, "switch", "free_stuck_takeout") == "on"
    simulated.show(STUCK)
    await pass_time(hass, freezer, 5)
    await switch(hass, "free_stuck_takeout", False)
    assert state(hass, "switch", "free_stuck_takeout") == "off"
    await pass_time(hass, freezer, 60)
    assert simulated.commands == []
    assert coordinator.diagnostics()["stuck_takeout"]["free"] is False
    # On again while the board is stuck: ten seconds from now.
    await switch(hass, "free_stuck_takeout", True)
    await pass_time(hass, freezer, 9)
    assert simulated.commands == []
    await pass_time(hass, freezer, 2)
    assert simulated.commands == ["reset"]


async def test_the_switch_stays_off_after_a_restart(hass, aioclient_mock, hass_storage):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await switch(hass, "free_stuck_takeout", False)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    saved = hass_storage[storage_key(entry.entry_id)]["data"]
    assert saved["takeout"] == {"free_stuck": False}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.local.free_stuck_takeout is False
    assert state(hass, "switch", "free_stuck_takeout") == "off"


@pytest.mark.parametrize("stored", [None, "off", {"free_stuck": "no"}])
async def test_a_missing_or_unknown_setting_frees_stuck_takeouts(
    hass, aioclient_mock, hass_storage, stored
):
    key = storage_key("stored-entry")
    hass_storage[key] = {"version": 1, "key": key, "data": {"takeout": stored}}
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(
        domain="homedarts", version=2, data=local_entry_data(), entry_id="stored-entry"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.local.free_stuck_takeout is True


async def test_unloading_ends_the_wait(hass, at_board, freezer):
    entry, coordinator, simulated = at_board
    simulated.show(STUCK)
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is True
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 60)
    assert simulated.commands == []
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is False


async def test_a_reset_that_ends_after_unloading_waits_for_nothing(
    hass, at_board, freezer
):
    entry, coordinator, simulated = at_board
    release = asyncio.Event()

    async def slow_reset(name: str) -> None:
        simulated.commands.append(name)
        await release.wait()

    simulated.frees = False
    simulated.show(STUCK)
    with patch.object(coordinator.client, "command", slow_reset):
        freezer.tick(timedelta(seconds=11))
        async_fire_time_changed(hass)
        await until(lambda: simulated.commands)
        assert await hass.config_entries.async_unload(entry.entry_id)
        release.set()
        await hass.async_block_till_done()
    assert simulated.commands == ["reset"]
    assert coordinator.diagnostics()["stuck_takeout"]["waiting"] is False


async def test_board_manager_2_frees_stuck_takeouts_too(hass, aioclient_mock):
    await setup_v2(hass, aioclient_mock)
    assert state(hass, "switch", "free_stuck_takeout") == "on"
