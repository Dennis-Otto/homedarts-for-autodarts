"""The setup with a board that is away, the device's version, polls that only
bring telemetry, and the repair notices of an unloaded board."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant.common import MockConfigEntry

from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.local_api import AutodartsLocalClient
from custom_components.homedarts.topics import Topic

from .local_helpers import (
    BASE,
    STATE,
    SYSTEM,
    board,
    entity_id,
    local_entry_data,
    mock_board,
    mock_board_v2,
    setup_local,
    setup_v2,
    state,
    written,
)


async def test_the_setup_waits_only_briefly_for_a_board_that_is_off(
    hass, aioclient_mock
):
    mock_board(aioclient_mock)
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=local_entry_data())
    entry.add_to_hass(hass)

    reads = 0

    async def first_read_never_answers():
        # Later reads answer, also a poll that a slow test machine makes due.
        nonlocal reads
        reads += 1
        if reads == 1:
            await asyncio.Event().wait()
        return dict(STATE)

    with (
        patch("custom_components.homedarts.local_coordinator.FIRST_POLL_SECONDS", 0),
        patch.object(
            AutodartsLocalClient, "get_state", side_effect=first_read_never_answers
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        coordinator = entry.runtime_data.local
        assert coordinator.connection.last_error == "TimeoutError"
        # Later polls wait as long as ever.
        await coordinator.async_refresh()
    assert coordinator.last_update_success


async def test_the_device_gets_its_version_once_the_board_answers(hass, aioclient_mock):
    aioclient_mock.get(BASE + "/api/state", status=503)
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    # The device of the last run, with the version the board had then.
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "board-1")},
        sw_version="1.0.7",
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    # The entities of a board that is away know no version.
    assert registry.async_get(device.id).sw_version is None
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock)
    await entry.runtime_data.local.async_refresh()
    assert registry.async_get(device.id).sw_version == "1.0.7"


@pytest.fixture
def cpu_usage(hass):
    """The load of the board PC, switched on as a user would."""
    er.async_get(hass).async_get_or_create("sensor", DOMAIN, "board-1_cpu_usage")


def reported(hass, key: str):
    return hass.states.get(entity_id(hass, "sensor", key)).last_reported


@pytest.mark.usefixtures("cpu_usage")
async def test_a_poll_of_only_telemetry_updates_only_its_entities(
    hass, aioclient_mock, freezer
):
    entry = await setup_v2(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    before = {key: reported(hass, key) for key in ("player_profiles", "achievements")}
    system = deepcopy(SYSTEM)
    system["stats"]["cpuPercent"] = 55.5
    system["camStats"][0]["fps"] = 25
    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock, system=system)
    freezer.tick(timedelta(seconds=10))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert state(hass, "sensor", "cpu_usage") == "55.5"
    assert {key: reported(hass, key) for key in before} == before
    # Anything else updates every entity.
    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock, system=system, state={**STATE, "numThrows": 1})
    freezer.tick(timedelta(seconds=10))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert all(reported(hass, key) > before[key] for key in before)


@pytest.mark.expected_errors
@pytest.mark.usefixtures("cpu_usage")
async def test_a_failing_telemetry_entity_leaves_the_others(
    hass, aioclient_mock, freezer, caplog
):
    entry = await setup_v2(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    coordinator.topics.async_add_listener(
        Topic.TELEMETRY, Mock(side_effect=RuntimeError("broken"))
    )
    system = deepcopy(SYSTEM)
    system["stats"]["cpuPercent"] = 60
    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock, system=system)
    freezer.tick(timedelta(seconds=10))
    await coordinator.async_refresh()
    assert state(hass, "sensor", "cpu_usage") == "60"
    assert "Unexpected error updating an entity of telemetry" in caplog.text


async def test_a_poll_that_only_brings_motion_updates_only_its_entities(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    hand = {"isStable": False, "isHand": True}
    with (
        patch.object(coordinator.client, "get_motion_state", return_value=hand),
        written(hass) as entities,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert entities == {
        entity_id(hass, "binary_sensor", key)
        for key in ("hand_detected", "takeout_partial")
    }
    assert state(hass, "binary_sensor", "hand_detected") == "on"
    assert coordinator.readings["motion"] == hand


async def test_an_unloaded_board_withdraws_its_repair_notices(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    registry = ir.async_get(hass)
    issue = f"board_manager_1_{entry.entry_id}"
    assert registry.async_get_issue(DOMAIN, issue)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert registry.async_get_issue(DOMAIN, issue) is None
    # They come back with the next setup, where they still apply.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, issue)
