"""The stored training: private, versioned and restored after a restart."""

import asyncio
import logging
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.storage import (
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
    TrainingStore,
    storage_key,
)

from .local_helpers import T20, board, local_entry_data, mock_board, state


async def setup(hass, aioclient_mock, entry_id="stored-entry"):
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, data=local_entry_data(), entry_id=entry_id
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def test_the_store_is_private_and_named_after_the_entry(hass):
    store = TrainingStore(hass, "some-entry")
    assert store.key == storage_key("some-entry") == "homedarts.some-entry.training"
    assert (store.version, store.minor_version) == (1, 3)
    # Player names are stored, so the file is readable by Home Assistant only.
    assert store._io._private is True


async def test_the_current_layout_survives_a_restart(
    hass, aioclient_mock, hass_storage
):
    entry = await setup(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    await coordinator.async_start_game(501, names=["Alex", "Sam"], legs=2)
    for count in range(1, 4):
        coordinator.async_receive("state", board(*[T20] * count))
    coordinator.async_receive("state", board())
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    saved = hass_storage[storage_key(entry.entry_id)]
    assert (saved["version"], saved["minor_version"]) == (
        STORAGE_VERSION,
        STORAGE_MINOR_VERSION,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    practice = entry.runtime_data.local.games.practice
    assert practice.names[:2] == ["Alex", "Sam"] and practice.legs_to_win == 2
    assert [player.remaining for player in practice.players] == [321, 501]
    assert practice.current == 1
    assert state(hass, "sensor", "training_darts") == "3"
    assert "alex" in practice.profiles.players


async def restart(hass, entry):
    """Unload the entry, which saves what changed, and set it up again."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data.local


async def test_an_action_builds_the_store_once(hass, aioclient_mock):
    # Building it takes milliseconds with a long history, on a Raspberry Pi more.
    coordinator = (await setup(hass, aioclient_mock)).runtime_data.local
    with patch.object(
        coordinator.games, "stored", wraps=coordinator.games.stored
    ) as stored:
        await coordinator.async_set_idle_minutes(17)
    assert stored.call_count == 1


async def test_a_dart_during_the_save_is_saved_at_the_shutdown(
    hass, aioclient_mock, hass_storage
):
    entry = await setup(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    await coordinator.async_start_game(501, names=["Alex"])
    write = coordinator.store.training.async_save

    async def write_and_throw(data):
        # The action's store is built; a dart lands while it is written.
        await write(data)
        coordinator.async_receive("state", board(T20))

    with patch.object(coordinator.store.training, "async_save", write_and_throw):
        await coordinator.async_set_idle_minutes(17)
    # Long before the delayed save of the dart.
    coordinator = await restart(hass, entry)
    assert coordinator.games.training.idle_minutes == 17
    assert state(hass, "sensor", "training_darts") == "1"


async def test_a_save_that_does_not_finish_is_saved_at_the_shutdown(
    hass, aioclient_mock, hass_storage
):
    entry = await setup(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    await coordinator.async_set_idle_minutes(5)
    with (
        patch.object(
            coordinator.store.training, "async_save", side_effect=asyncio.CancelledError
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator.async_set_idle_minutes(17)
    coordinator = await restart(hass, entry)
    assert coordinator.games.training.idle_minutes == 17


async def test_data_of_a_newer_minor_version_loads_after_a_downgrade(
    hass, aioclient_mock, hass_storage
):
    key = storage_key("stored-entry")
    hass_storage[key] = {
        "version": STORAGE_VERSION,
        "minor_version": STORAGE_MINOR_VERSION + 1,
        "key": key,
        "data": {
            "darts": 12,
            "points": 300,
            "practice": {"game": 301, "names": ["Kim"], "future_rule": True},
            "records": {"goal": 150},
            "a_future_part": {"kept": "or ignored"},
        },
    }
    entry = await setup(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    assert coordinator.games.training.snapshot()["darts"] == 12
    assert (
        coordinator.games.practice.game == 301
        and coordinator.games.practice.names[0] == "Kim"
    )
    assert coordinator.games.records.goal == 150
    # The migration writes the data back in this version's layout.
    assert hass_storage[key]["minor_version"] == STORAGE_MINOR_VERSION
    # Parts of the newer release stay when this one saves.
    await coordinator.async_set_daily_goal(200)
    saved = hass_storage[key]["data"]
    assert saved["a_future_part"] == {"kept": "or ignored"}
    assert saved["records"]["goal"] == 200


async def test_a_store_of_version_1_5_restores(hass, aioclient_mock, hass_storage):
    key = storage_key("stored-entry")
    # Version 1.5 stored the training, the practice game and the records only.
    hass_storage[key] = {
        "version": 1,
        "key": key,
        "data": {
            "darts": 30,
            "points": 900,
            "active": True,
            "practice": {
                "game": 501,
                "names": ["Alex", "Sam", "", ""],
                "players": [{"remaining": 321}, {"remaining": 501}],
                "profiles": {"players": [{"name": "Alex", "legs_played": 4}]},
            },
            "records": {"goal": 100, "streak": 2},
        },
    }
    entry = await setup(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    assert coordinator.games.training.snapshot()["points"] == 900
    players = coordinator.games.practice.players
    assert [player.remaining for player in players] == [321, 501]
    assert coordinator.games.practice.profiles.players["alex"].legs_played == 4
    assert coordinator.games.records.goal == 100
    # Without stored progress, the profiles give every player a start.
    assert "alex" in coordinator.games.progress.players
    assert hass_storage[key]["minor_version"] == STORAGE_MINOR_VERSION


async def failed_setup(hass, aioclient_mock, hass_storage, state: ConfigEntryState):
    """Set the entry up, which fails; afterwards no store may have changed."""
    before = deepcopy(hass_storage)
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, data=local_entry_data(), entry_id="stored-entry"
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is state
    # Delayed saves would have happened by now.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert {
        key: value for key, value in hass_storage.items() if key.startswith("homedarts")
    } == {key: value for key, value in before.items() if key.startswith("homedarts")}
    return entry


def stored_training(hass_storage, **store) -> str:
    key = storage_key("stored-entry")
    hass_storage[key] = {
        "version": STORAGE_VERSION,
        "minor_version": STORAGE_MINOR_VERSION,
        "key": key,
        "data": {"darts": 999, "points": 20000, "records": {"goal": 150}},
        **store,
    }
    return key


async def test_a_store_of_a_newer_major_version_stops_the_setup(
    hass, aioclient_mock, hass_storage
):
    key = stored_training(hass_storage, version=STORAGE_VERSION + 1)
    entry = await failed_setup(
        hass, aioclient_mock, hass_storage, ConfigEntryState.SETUP_ERROR
    )
    assert entry.reason == (
        "The stored training of this board comes from a newer version of the "
        "integration. Install that version again, or restore a backup; the stored "
        "data stays unchanged"
    )
    assert hass_storage[key]["data"]["darts"] == 999


async def test_a_store_that_cannot_be_read_is_tried_again(
    hass, aioclient_mock, hass_storage
):
    key = stored_training(hass_storage)
    with patch.object(
        TrainingStore, "async_load", side_effect=HomeAssistantError("I/O error")
    ):
        entry = await failed_setup(
            hass, aioclient_mock, hass_storage, ConfigEntryState.SETUP_RETRY
        )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.local.games.training.snapshot()["darts"] == 999
    assert hass_storage[key]["data"]["records"]["goal"] == 150


async def test_a_report_that_cannot_be_read_keeps_the_training(
    hass, aioclient_mock, hass_storage
):
    stored_training(hass_storage)
    load = Store.async_load

    async def fail_for_the_report(store):
        if store.key.endswith(".report"):
            raise OSError("Input/output error")
        return await load(store)

    with patch.object(Store, "async_load", fail_for_the_report):
        await failed_setup(
            hass, aioclient_mock, hass_storage, ConfigEntryState.SETUP_RETRY
        )


@pytest.mark.expected_errors
async def test_a_store_that_cannot_be_restored_stops_the_setup(
    hass, aioclient_mock, hass_storage, caplog
):
    stored_training(hass_storage)
    with patch(
        "custom_components.homedarts.games.PersonalRecords.restore",
        side_effect=TypeError("unhashable type: 'list'"),
    ):
        entry = await failed_setup(
            hass, aioclient_mock, hass_storage, ConfigEntryState.SETUP_ERROR
        )
    assert "report this as a bug" in entry.reason
    assert [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.ERROR and record.name.startswith("custom_")
    ] == ["The stored training cannot be restored"]
