"""Repair issues, translated states and entity metadata."""

import asyncio
import logging
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homedarts import async_unload_entry
from custom_components.homedarts.local_api import AutodartsLocalAuthError
from custom_components.homedarts.local_coordinator import ISSUES

from .local_helpers import (
    BASE,
    CONFIG,
    HOST,
    STATE,
    T20,
    board,
    entity_id,
    local_entry_data,
    mock_board,
    mock_board_v2,
    record,
    setup_local,
    setup_v2,
    state,
    until,
)


def issue(hass, name, entry):
    return ir.async_get(hass).async_get_issue("homedarts", f"{name}_{entry.entry_id}")


def create_every_issue(hass, entry):
    for name in ISSUES:
        ir.async_create_issue(
            hass,
            "homedarts",
            f"{name}_{entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=name,
        )


def another_board():
    """The settings of a board with another board ID."""
    config = deepcopy(CONFIG)
    config["auth"]["board_id"] = "another-board"
    return config


def problems(caplog) -> list[str]:
    """The warnings and errors of the integration."""
    return [
        logged.getMessage()
        for logged in caplog.records
        if logged.levelno >= logging.WARNING
        and logged.name.startswith("custom_components.homedarts")
    ]


async def unload_while_reading(hass, aioclient_mock, entry, method, answer):
    """Unload the entry while a poll waits for the board. The board answers
    the read well after the coordinator began to shut down, as a slow board
    may: by then, an unload that did not wait for it would be over."""
    coordinator = entry.runtime_data.local
    reading = asyncio.Event()
    reads_at_the_answer = []

    async def slow_board(*_args):
        reading.set()
        await until(lambda: coordinator._shutting_down)
        for _ in range(100):
            await asyncio.sleep(0)
        reads_at_the_answer.append(aioclient_mock.call_count)
        if isinstance(answer, Exception):
            raise answer
        return deepcopy(answer)

    with patch.object(coordinator.client, method, side_effect=slow_board):
        polling = hass.async_create_task(coordinator.async_refresh())
        await reading.wait()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await polling
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    # Nothing more is read from a board that unloads.
    assert [aioclient_mock.call_count] == reads_at_the_answer


async def test_classic_board_manager_asks_to_update(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    found = issue(hass, "board_manager_1", entry)
    assert found.severity == ir.IssueSeverity.WARNING
    assert found.translation_key == "board_manager_1"
    assert "headless-installation" in found.learn_more_url
    assert await hass.config_entries.async_remove(entry.entry_id)
    assert issue(hass, "board_manager_1", entry) is None


async def test_update_notice_appears_for_a_known_classic_board(hass, aioclient_mock):
    """Entries created by the setup store the generation, which never changes."""
    mock_board(aioclient_mock)
    data = {**local_entry_data(), "api_generation": 1}
    entry = MockConfigEntry(domain="homedarts", version=2, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert issue(hass, "board_manager_1", entry) is not None
    # Issues are not kept across restarts, so every start reports it again.
    ir.async_delete_issue(hass, "homedarts", f"board_manager_1_{entry.entry_id}")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert issue(hass, "board_manager_1", entry) is not None


async def test_board_manager_2_has_no_update_notice(hass, aioclient_mock):
    entry = await setup_v2(hass, aioclient_mock)
    assert issue(hass, "board_manager_1", entry) is None


async def test_wrong_board_raises_and_clears_a_repair_issue(
    hass, aioclient_mock, freezer
):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock, config=another_board())
    # Board Manager 1 reports its board ID with the settings, every 30 seconds.
    freezer.tick(timedelta(seconds=30))
    await coordinator.async_refresh()
    found = issue(hass, "wrong_board", entry)
    assert found.severity == ir.IssueSeverity.ERROR
    assert found.translation_placeholders == {"address": "http://192.0.2.10:3180"}
    assert state(hass, "switch", "detection") == "unavailable"

    aioclient_mock.clear_requests()
    mock_board(aioclient_mock)
    freezer.tick(timedelta(seconds=30))
    await coordinator.async_refresh()
    assert issue(hass, "wrong_board", entry) is None
    assert state(hass, "switch", "detection") == "off"


async def test_removing_the_entry_removes_every_repair_issue(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    create_every_issue(hass, entry)
    assert await hass.config_entries.async_remove(entry.entry_id)
    assert all(issue(hass, name, entry) is None for name in ISSUES)


async def test_a_failed_unload_keeps_the_board_and_its_repair_issues(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock)
    create_every_issue(hass, entry)
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await async_unload_entry(hass, entry)
    assert all(issue(hass, name, entry) is not None for name in ISSUES)
    # The board is still read, so its issues still apply.
    reads = aioclient_mock.call_count
    await entry.runtime_data.local.async_refresh()
    assert aioclient_mock.call_count > reads

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert all(issue(hass, name, entry) is None for name in ISSUES)


@pytest.mark.parametrize(
    ("method", "answer"),
    [
        # The state arrives; the settings read next name another board.
        ("get_state", STATE),
        # Something between Home Assistant and the board refuses the read.
        ("get_state", AutodartsLocalAuthError("HTTP 403")),
        # The settings name another board.
        ("get_config", {"board_id": "another-board"}),
    ],
    ids=["state", "refused", "settings"],
)
async def test_a_poll_that_ends_during_the_unload_reports_nothing(
    hass, aioclient_mock, freezer, caplog, method, answer
):
    entry = await setup_local(hass, aioclient_mock)
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock, config=another_board())
    # Board Manager 1 reports its board ID with the settings, every 30 seconds.
    freezer.tick(timedelta(seconds=30))
    caplog.clear()
    await unload_while_reading(hass, aioclient_mock, entry, method, answer)
    assert all(issue(hass, name, entry) is None for name in ISSUES)
    assert problems(caplog) == []


async def test_darts_read_during_the_unload_are_not_announced(
    hass, aioclient_mock, freezer
):
    entry = await setup_v2(hass, aioclient_mock)
    events = record(hass, entry.runtime_data.local)
    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock, state=board(T20))
    # The details of the board PC are read again every hour.
    freezer.tick(timedelta(hours=1))
    await unload_while_reading(hass, aioclient_mock, entry, "get_host", HOST)
    assert events == []


async def test_a_board_away_at_the_unload_does_not_recover_in_the_log(
    hass, aioclient_mock, caplog
):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{BASE}/api/state", status=503)
    for _ in range(3):
        await coordinator.async_refresh()
    assert not coordinator.last_update_success
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock)
    caplog.clear()
    with caplog.at_level(logging.INFO):
        await unload_while_reading(hass, aioclient_mock, entry, "get_state", STATE)
    assert not coordinator.last_update_success
    assert "recovered" not in caplog.text


async def test_a_poll_during_the_unload_brings_back_no_unknown_format_notice(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    # No running flag: this is no Board Manager state this integration knows.
    mock_board(aioclient_mock, state={"status": "Throw"})
    for _ in range(3):
        await coordinator.async_refresh()
    assert issue(hass, "unsupported_response", entry) is not None
    # Every poll reports the reads that keep failing as it ends, after the
    # shutdown too; the unload deletes the notice only after that.
    await unload_while_reading(hass, aioclient_mock, entry, "get_state", STATE)
    assert issue(hass, "unsupported_response", entry) is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("Takeout in progress", "takeout_in_progress"),
        ("Calibrating", "calibrating"),
        ("Throw", "throw"),
        ("Something new", "unknown"),
        (None, "unknown"),
    ],
)
async def test_detection_status_is_translatable(hass, aioclient_mock, status, expected):
    await setup_local(hass, aioclient_mock, state={**STATE, "status": status})
    assert state(hass, "sensor", "local_status") == expected
    options = hass.states.get(entity_id(hass, "sensor", "local_status")).attributes[
        "options"
    ]
    assert "takeout_in_progress" in options


async def test_entity_categories_and_classes(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock)
    registry = er.async_get(hass)

    def entry(platform, key):
        return registry.async_get(entity_id(hass, platform, key))

    for key in ("start", "stop", "reset"):
        assert entry("button", key).entity_category is None
    restart = entry("button", "restart")
    assert restart.entity_category == EntityCategory.CONFIG
    assert restart.original_device_class == ButtonDeviceClass.RESTART
    assert entry("binary_sensor", "cameras_active").original_device_class == "running"
    assert entry("binary_sensor", "calibrating").original_device_class == "running"
    darts = hass.states.get(entity_id(hass, "sensor", "training_darts"))
    # Session totals start from zero with the session, and a correction or an
    # undone visit can lower them.
    assert darts.attributes["state_class"] == "total"
    coordinator = hass.config_entries.async_entries("homedarts")[0].runtime_data.local
    assert darts.attributes["last_reset"] == coordinator.games.training.started
    session = hass.states.get(entity_id(hass, "sensor", "training_started"))
    assert "last_reset" not in session.attributes
    average = hass.states.get(entity_id(hass, "sensor", "training_average"))
    assert "last_reset" not in average.attributes
    assert "icon" not in darts.attributes


def test_board_event_and_darts_in_visit_values():
    from custom_components.homedarts import sensor

    data = {"local": {"event": "Throw detected", "status": "Throw", "numThrows": 2}}
    assert sensor._get_board_event(data) == "Throw detected"
    assert sensor._get_num_throws(data) == 2
    # Without an event the status shows.
    assert sensor._get_board_event({"local": {"status": "Stopped"}}) == "Stopped"
    # Before the first read, and a count that is no number, read as unknown.
    for empty in ({}, {"local": {}}, {"local": None}):
        assert sensor._get_board_event(empty) is None
        assert sensor._get_num_throws(empty) is None
    assert sensor._get_num_throws({"local": {"numThrows": True}}) is None


async def test_training_average_is_unknown_without_darts(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock)
    assert state(hass, "sensor", "training_average") == "unknown"
    average = hass.states.get(entity_id(hass, "sensor", "training_average"))
    assert average.attributes["state_class"] == "measurement"
    darts = hass.states.get(entity_id(hass, "sensor", "training_darts"))
    assert darts.attributes["hits"] == {}


async def test_training_values_have_the_units_of_the_live_sensors(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock)
    units = {
        key: hass.states.get(
            entity_id(hass, "sensor", f"training_{key}")
        ).attributes.get("unit_of_measurement")
        for key in ("darts", "triples", "points", "average", "visits", "scores_180")
    }
    assert units == {
        "darts": "darts",
        "triples": "darts",
        "points": "points",
        "average": "points",
        "visits": "visits",
        "scores_180": "visits",
    }
    started = hass.states.get(entity_id(hass, "sensor", "training_started"))
    assert "unit_of_measurement" not in started.attributes
