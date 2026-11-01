"""Recovery from board outages, flaky reads and old entries."""

import asyncio
import logging
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.homedarts import CLOUD_SENSORS
from custom_components.homedarts.errors import AutodartsConnectionError
from custom_components.homedarts.local_api import AutodartsLocalClient
from custom_components.homedarts.local_coordinator import AutodartsLocalCoordinator

from .local_helpers import (
    BASE,
    CONFIG,
    STATE,
    entity_id,
    local_entry_data,
    mock_board,
    setup_local,
    state,
    until,
)

# The login that entries of the cloud link held, before version 2.2.
TOKEN = {"access_token": "old", "refresh_token": "old-refresh", "expires_at": 0}


async def test_board_switched_off_at_setup_recovers(hass, aioclient_mock):
    aioclient_mock.get(BASE + "/api/state", status=503)
    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    # Training and games work without the board; its entities wait for it.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    assert state(hass, "binary_sensor", "local_connected") == "off"
    assert state(hass, "switch", "detection") == "unavailable"
    assert state(hass, "switch", "training_session") == "on"

    aioclient_mock.clear_requests()
    mock_board(aioclient_mock)
    await entry.runtime_data.local.async_refresh()
    assert state(hass, "binary_sensor", "local_connected") == "on"
    assert state(hass, "switch", "detection") == "off"


@pytest.mark.parametrize(
    ("old", "expected"),
    [
        ({"host": "192.0.2.10", "port": 3180}, local_entry_data()),
        (
            {
                "email": "player@example.com",
                "password": "e2e-only-password",
                "board_id": "board-1",
                "host": "192.0.2.10",
                "port": 3180,
            },
            local_entry_data(),
        ),
    ],
)
async def test_version_1_entries_are_migrated_without_passwords(
    hass, aioclient_mock, old, expected
):
    mock_board(aioclient_mock)
    entry = MockConfigEntry(domain="homedarts", version=1, data=old)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (entry.version, entry.minor_version) == (2, 2)
    # The first refresh also records the board generation.
    assert dict(entry.data) == {**expected, "api_generation": 1}
    assert entry.unique_id == "board-1"
    assert entry.state == ConfigEntryState.LOADED


async def test_unreachable_version_1_board_is_migrated_later(hass, aioclient_mock):
    aioclient_mock.get(BASE + "/api/config", status=503)
    entry = MockConfigEntry(
        domain="homedarts", version=1, data={"host": "192.0.2.10", "port": 3180}
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 1
    assert dict(entry.data) == {"host": "192.0.2.10", "port": 3180}


async def test_entry_of_a_newer_integration_version_is_left_alone(hass):
    data = {**local_entry_data(), "future_setting": True}
    entry = MockConfigEntry(domain="homedarts", version=3, data=data)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 3 and dict(entry.data) == data


async def test_entry_of_a_newer_minor_version_still_loads(hass, aioclient_mock):
    mock_board(aioclient_mock)
    data = {**local_entry_data(), "future_setting": True}
    entry = MockConfigEntry(domain="homedarts", version=2, minor_version=3, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    assert (entry.version, entry.minor_version) == (2, 3)
    # The first refresh records the board generation; the rest stays as it was.
    assert dict(entry.data) == {**data, "api_generation": 1}


@pytest.mark.parametrize("name", [None, "Match Board"])
async def test_entries_lose_the_data_of_the_cloud_link(hass, aioclient_mock, name):
    """Entries before version 2.2 could hold the login of the cloud link, which is
    gone; the board, its address and its name stay."""
    mock_board(aioclient_mock)
    kept = {**local_entry_data(), **({"name": name} if name else {})}
    cloud = {"token": TOKEN, "client_id": "registered-test-client"}
    entry = MockConfigEntry(
        domain="homedarts", version=2, data={**kept, **cloud, "local_only": False}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    assert (entry.version, entry.minor_version) == (2, 2)
    assert dict(entry.data) == {**kept, "api_generation": 1}
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("homedarts", "board-1"), entry.entry_id
    )
    assert device.name == (name or "Autodarts Board")
    assert not hass.config_entries.flow.async_progress()


async def test_entry_that_only_the_cloud_reached_asks_for_the_address(hass):
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        data={"board_id": "board-1", "token": TOKEN, "client_id": "test-client"},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (entry.version, entry.minor_version) == (2, 2)
    assert dict(entry.data) == {"board_id": "board-1"}
    # Retrying cannot help: the address has to be entered in Reconfigure.
    assert entry.state == ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "no_local_address"
    assert not hass.config_entries.flow.async_progress()


async def test_the_sensors_of_the_cloud_link_are_removed(hass, aioclient_mock):
    mock_board(aioclient_mock)
    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    cloud = [
        registry.async_get_or_create(
            "sensor", "homedarts", f"board-1_{key}", config_entry=entry
        ).entity_id
        for key in CLOUD_SENSORS
    ]
    # The local entities of the same board and those of another board stay.
    kept = [
        registry.async_get_or_create(platform, "homedarts", unique_id).entity_id
        for platform, unique_id in (
            ("sensor", "board-1_board_event"),
            ("event", "board-1_board_events"),
            ("sensor", "board-1_last_throw"),
            ("sensor", "board-2_round"),
        )
    ]
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    assert not [entity for entity in cloud if registry.async_get(entity)]
    assert all(registry.async_get(entity) for entity in kept)


async def test_failed_reads_keep_settings_and_motion(hass, aioclient_mock, freezer):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    freezer.tick(timedelta(seconds=30))
    with (
        patch.object(
            coordinator.client, "get_config", side_effect=AutodartsConnectionError
        ),
        patch.object(
            coordinator.client, "get_motion_state", side_effect=AutodartsConnectionError
        ),
    ):
        await coordinator.async_refresh()
    assert state(hass, "switch", "auto_calibrate") == "on"
    assert state(hass, "select", "standby_minutes") == "15"
    assert coordinator.readings["motion"]["isStable"] is True
    assert coordinator.data["settings"]["camera_count"] == 3


async def test_setting_switched_during_a_poll_shows_without_waiting(
    hass, aioclient_mock, freezer
):
    """A poll that asked for the settings just before a switch changed one gets
    the old value; the switch must not show it until the next regular read."""
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    freezer.tick(timedelta(seconds=30))
    read_settings = coordinator.client.get_config
    asked, answered = asyncio.Event(), asyncio.Event()

    async def settings_on_the_way():
        settings = await read_settings()
        asked.set()
        await answered.wait()
        return settings

    with patch.object(coordinator.client, "get_config", settings_on_the_way):
        poll = hass.async_create_task(coordinator.async_refresh())
        await asked.wait()
    switched = deepcopy(CONFIG)
    switched["cam"]["auto_distortion"] = True
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock, config=switched)
    aioclient_mock.patch(f"{BASE}/api/config", status=204)
    switching = hass.async_create_task(
        hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id(hass, "switch", "auto_distortion")},
            blocking=True,
        )
    )
    await until(lambda: any(call[0] == "PATCH" for call in aioclient_mock.mock_calls))
    # The old answer arrives after the board has taken the new setting.
    answered.set()
    await poll
    await switching
    # The switch's own refresh follows the poll after the one-second cooldown.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    assert state(hass, "switch", "auto_distortion") == "on"


async def test_missed_poll_during_realtime_stream_is_no_outage(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    coordinator.stream_connected = True
    with patch.object(
        coordinator.client, "get_state", side_effect=AutodartsConnectionError
    ):
        await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert state(hass, "binary_sensor", "local_connected") == "on"
    assert state(hass, "switch", "detection") == "off"


async def test_poll_after_home_assistant_closed_its_session_is_no_error(
    hass, aioclient_mock
):
    """A poll can still start after Home Assistant closed its session (#107)."""
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    requests = aioclient_mock.call_count
    # The last stage of a stop closes the shared session.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()
    await coordinator.async_refresh()
    # The board is left alone and the last values stay, without an error in the log.
    assert aioclient_mock.call_count == requests
    assert coordinator.last_update_success
    assert state(hass, "binary_sensor", "local_connected") == "on"


@pytest.mark.expected_errors
async def test_stream_survives_unexpected_errors_and_polls_slowly_meanwhile(
    hass, aioclient_mock, caplog
):
    release, handshake, live, fail, reconnected = (asyncio.Event() for _ in range(5))
    calls = 0
    waits = []

    async def stream(self):
        nonlocal calls
        calls += 1
        yield "connected", {}
        if calls == 1:
            handshake.set()
            await release.wait()
            yield "state", {**STATE}
            live.set()
            await fail.wait()
            raise RuntimeError("unexpected board message")
        reconnected.set()
        await asyncio.Event().wait()

    async def wait(self, delay):
        waits.append(delay)
        return False

    with (
        patch.object(AutodartsLocalClient, "events", stream),
        patch.object(AutodartsLocalCoordinator, "_wait_before_reconnect", wait),
    ):
        entry = await setup_local(hass, aioclient_mock)
        coordinator = entry.runtime_data.local
        await handshake.wait()
        # An open socket alone does not prove that notifications arrive.
        assert coordinator.update_interval == timedelta(seconds=2)
        release.set()
        await live.wait()
        assert coordinator.update_interval == timedelta(seconds=30)
        fail.set()
        await reconnected.wait()
        assert state(hass, "binary_sensor", "realtime_connected") == "on"
        assert await hass.config_entries.async_unload(entry.entry_id)
    assert coordinator.update_interval == timedelta(seconds=2)
    # The connection delivered notifications, so the back-off starts at 1 second.
    assert 0.8 <= waits[0] <= 1
    # The failure is logged once, with the error that ended the stream.
    errors = [
        record
        for record in caplog.records
        if record.levelno >= logging.ERROR and record.name.startswith("custom_")
    ]
    assert [record.getMessage() for record in errors] == [
        "Unexpected error in the local event stream"
    ]
    assert str(errors[0].exc_info[1]) == "unexpected board message"


async def test_connected_stream_without_any_board_answer_is_still_an_outage(
    hass, aioclient_mock
):
    aioclient_mock.get(BASE + "/api/state", status=503)

    async def stream(self):
        yield "connected", {}
        await asyncio.Event().wait()

    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    with patch.object(AutodartsLocalClient, "events", stream):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data.local
        assert coordinator.stream_connected
        # Only a board that answered before can miss a poll without an outage.
        await coordinator.async_refresh()
        assert not coordinator.last_update_success
        assert state(hass, "binary_sensor", "local_connected") == "off"
        assert state(hass, "switch", "detection") == "unavailable"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_reconnect_back_off_doubles_to_a_minute_and_starts_over(
    hass, aioclient_mock, freezer
):
    """Failures wait 1, 2, 4 ... 60 seconds, less up to a fifth of jitter."""
    waits = []
    calls = 0
    done = asyncio.Event()

    async def wait(self, delay):
        waits.append(delay)
        return False

    async def stream(self):
        nonlocal calls
        calls += 1
        if calls == 10:
            # Half a minute of connection starts the back-off over.
            yield "connected", {}
            freezer.tick(timedelta(seconds=30))
        if calls < 12:
            raise AutodartsConnectionError()
        done.set()
        await asyncio.Event().wait()

    with (
        patch.object(AutodartsLocalClient, "events", stream),
        patch.object(AutodartsLocalCoordinator, "_wait_before_reconnect", wait),
    ):
        entry = await setup_local(hass, aioclient_mock)
        await done.wait()
        assert await hass.config_entries.async_unload(entry.entry_id)
    bases = [1, 2, 4, 8, 16, 32, 60, 60, 60, 1, 2]
    assert len(waits) == len(bases)
    assert all(
        0.8 * base <= delay <= base for delay, base in zip(waits, bases, strict=True)
    )
    # The jitter spreads the waits instead of repeating exact values.
    assert (
        len({round(delay / base, 6) for delay, base in zip(waits, bases, strict=True)})
        > 1
    )


async def test_starting_twice_keeps_one_event_stream_and_one_day_timer(
    hass, aioclient_mock
):
    streams = 0

    async def stream(self):
        nonlocal streams
        streams += 1
        yield "connected", {}
        await asyncio.Event().wait()

    with patch.object(AutodartsLocalClient, "events", stream):
        entry = await setup_local(hass, aioclient_mock)
        coordinator = entry.runtime_data.local
        task, day_timer = coordinator._stream_task, coordinator._midnight_unsub
        coordinator.async_start()
        await hass.async_block_till_done()
        assert coordinator._stream_task is task and streams == 1
        assert coordinator._midnight_unsub is day_timer
        assert await hass.config_entries.async_unload(entry.entry_id)
    assert task.done() and coordinator._midnight_unsub is None


async def test_board_update_after_the_device_was_deleted_adds_no_device(
    hass, aioclient_mock, freezer
):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    registry = dr.async_get(hass)
    board = ("homedarts", "board-1")
    registry.async_remove_device(
        registry.async_get_device_by_identifier(board, entry.entry_id).id
    )
    freezer.tick(timedelta(seconds=30))
    with patch.object(coordinator.client, "get_version", return_value="1.0.8"):
        await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data["version"] == "1.0.8"
    assert registry.async_get_device_by_identifier(board, entry.entry_id) is None


async def test_non_numeric_board_values_read_as_unknown(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock, state={**STATE, "numThrows": "three"})
    assert state(hass, "sensor", "num_throws") == "unknown"
    assert state(hass, "binary_sensor", "local_connected") == "on"


async def test_board_manager_update_shows_on_the_device(hass, aioclient_mock, freezer):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    registry = dr.async_get(hass)
    device = registry.async_get_device_by_identifier(
        ("homedarts", "board-1"), entry.entry_id
    )
    assert device.sw_version == "1.0.7"
    freezer.tick(timedelta(seconds=30))
    with patch.object(coordinator.client, "get_version", return_value="1.0.8"):
        await coordinator.async_refresh()
    assert registry.async_get(device.id).sw_version == "1.0.8"


async def test_version_1_cloud_entry_without_board_address_asks_for_the_address(hass):
    """Only the local address helps, so no login is started."""
    old = {"email": "player@example.com", "password": "secret", "board_id": "board-1"}
    entry = MockConfigEntry(domain="homedarts", version=1, data=old)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert dict(entry.data) == {"board_id": "board-1"}
    assert (entry.version, entry.minor_version) == (2, 2)
    assert entry.state == ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "no_local_address"
    assert not hass.config_entries.flow.async_progress()
