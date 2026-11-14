"""Board Manager 2: one system read, its own entities and generation changes."""

from collections import Counter
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.homedarts.diagnostics import async_get_config_entry_diagnostics
from custom_components.homedarts.local_api import (
    AutodartsEndpointMissing,
    board_generation,
)

from .local_helpers import (
    BASE,
    STATE,
    SYSTEM,
    entity_id,
    local_entry_data,
    mock_board,
    mock_board_v2,
    setup_local,
    setup_v2,
    state,
    unique_ids,
)

SECRETS = ("private-board-api-key", "private-tls-key")


@pytest.fixture
def cpu_usage(hass):
    """The load of the board PC, switched on as a user would."""
    er.async_get(hass).async_get_or_create("sensor", "homedarts", "board-1_cpu_usage")


@pytest.mark.usefixtures("cpu_usage")
async def test_board_manager_2_entities_and_one_system_read(hass, aioclient_mock):
    entry = await setup_v2(hass, aioclient_mock)
    assert entry.data["api_generation"] == 2
    ids = unique_ids(hass, entry)
    assert {"board-1_cloud_link", "board-1_cpu_usage", "board-1_board_software"} <= ids
    assert not {"board-1_upstream", "board-1_connect", "board-1_disconnect"} & ids
    assert state(hass, "binary_sensor", "cloud_link") == "on"
    assert state(hass, "sensor", "cpu_usage") == "12.5"
    update = hass.states.get(entity_id(hass, "update", "board_software"))
    assert update.state == "on"
    assert update.attributes["installed_version"] == "2.0.0"
    assert update.attributes["latest_version"] == "2.0.2"
    assert state(hass, "binary_sensor", "cameras_active") == "on"
    assert state(hass, "switch", "auto_calibrate") == "on"
    registry = er.async_get(hass)
    memory = registry.async_get(entity_id(hass, "sensor", "memory_usage"))
    assert memory.disabled_by == er.RegistryEntryDisabler.INTEGRATION

    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock)
    await entry.runtime_data.local.async_refresh()
    paths = Counter(call[1].path for call in aioclient_mock.mock_calls)
    assert paths == {"/api/state": 1, "/api/system": 1}


async def test_board_manager_2_secrets_never_leave_the_client(hass, aioclient_mock):
    entry = await setup_v2(hass, aioclient_mock)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["board_manager_generation"] == 2
    for secret in SECRETS:
        assert secret not in str(entry.runtime_data.local.data)
        assert secret not in str(diagnostics)
        assert secret not in str(hass.states.async_all())


async def test_no_update_means_latest_is_installed(hass, aioclient_mock):
    system = {**deepcopy(SYSTEM), "updateAvailable": ""}
    await setup_v2(hass, aioclient_mock, system=system)
    assert state(hass, "update", "board_software") == "off"


async def test_the_load_of_the_board_pc_is_off_unless_wanted(hass, aioclient_mock):
    await setup_v2(hass, aioclient_mock)
    for key in ("cpu_usage", "memory_usage"):
        sensor = er.async_get(hass).async_get(entity_id(hass, "sensor", key))
        assert sensor.disabled_by == er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("cpu_usage")
async def test_failed_system_read_keeps_values(hass, aioclient_mock):
    entry = await setup_v2(hass, aioclient_mock)
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock, version="2.0.0")
    aioclient_mock.get(BASE + "/api/system", status=503)
    await entry.runtime_data.local.async_refresh()
    assert state(hass, "sensor", "cpu_usage") == "12.5"
    assert state(hass, "switch", "auto_calibrate") == "on"
    assert state(hass, "binary_sensor", "cloud_link") == "on"


async def test_upgrade_to_board_manager_2_rebuilds_entities(
    hass, aioclient_mock, freezer
):
    entry = await setup_local(hass, aioclient_mock)
    assert entry.data["api_generation"] == 1
    assert "board-1_upstream" in unique_ids(hass, entry)
    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock)
    coordinator = entry.runtime_data.local
    # Board Manager 1 reports its version every 30 seconds.
    freezer.tick(timedelta(seconds=30))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert entry.data["api_generation"] == 2
    ids = unique_ids(hass, entry)
    assert "board-1_upstream" not in ids
    assert "board-1_cloud_link" in ids
    assert state(hass, "binary_sensor", "cloud_link") == "on"


async def test_board_without_system_endpoint_returns_to_classic(hass, aioclient_mock):
    mock_board(aioclient_mock)
    aioclient_mock.get(BASE + "/api/system", status=404)
    data = {**local_entry_data(), "api_generation": 2}
    entry = MockConfigEntry(domain="homedarts", version=2, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.data["api_generation"] == 1
    ids = unique_ids(hass, entry)
    assert "board-1_upstream" in ids
    assert not {"board-1_cloud_link", "board-1_board_software"} & ids


async def test_version_2_board_without_system_endpoint_settles_as_classic(
    hass, aioclient_mock, freezer
):
    """Such a board is switched over once and stays so, instead of reloading."""
    mock_board(aioclient_mock, version="2.0.0")
    aioclient_mock.get(BASE + "/api/system", status=404)
    aioclient_mock.get(BASE + "/api/host", status=404)
    data = {**local_entry_data(), "api_generation": 2}
    entry = MockConfigEntry(domain="homedarts", version=2, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.local
    # A board that is still starting may miss the route for a while.
    assert entry.data["api_generation"] == 2
    assert "board-1_cpu_usage" in unique_ids(hass, entry)
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        for _ in range(5):
            freezer.tick(timedelta(seconds=59))
            await coordinator.async_refresh()
        reload.assert_not_called()
        freezer.tick(timedelta(seconds=5))
        await coordinator.async_refresh()
    reload.assert_called_once_with(entry.entry_id)
    assert entry.data["api_generation"] == 1
    assert entry.data["no_system_api"] == "2.0.0"

    # The next start, like the reload, keeps the classic protocol for good.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock, version="2.0.0")
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        for _ in range(5):
            await coordinator.async_refresh()
    reload.assert_not_called()
    assert coordinator.generation == 1
    # Only once an hour: the route may come with an update of the same version.
    assert "/api/system" not in {call[1].path for call in aioclient_mock.mock_calls}
    ids = unique_ids(hass, entry)
    assert "board-1_upstream" in ids
    # Every entity of Board Manager 2 is removed, the board PC details, too.
    assert (
        not {
            "board-1_cloud_link",
            "board-1_board_software",
            "board-1_cpu_usage",
            "board-1_host_os",
            "board-1_host_processor",
            "board-1_vision_version",
        }
        & ids
    )


async def test_a_board_that_answers_the_system_endpoint_again_is_board_manager_2(
    hass, aioclient_mock, freezer
):
    mock_board(aioclient_mock, version="2.0.0")
    aioclient_mock.get(BASE + "/api/system", status=404)
    data = {**local_entry_data(), "api_generation": 1, "no_system_api": "2.0.0"}
    entry = MockConfigEntry(domain="homedarts", version=2, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock)
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        freezer.tick(timedelta(minutes=59))
        await coordinator.async_refresh()
        reload.assert_not_called()
        freezer.tick(timedelta(minutes=1))
        await coordinator.async_refresh()
    reload.assert_called_once_with(entry.entry_id)
    assert entry.data["api_generation"] == 2
    assert "no_system_api" not in entry.data


@pytest.mark.usefixtures("cpu_usage")
async def test_system_endpoint_missing_for_a_moment_changes_nothing(
    hass, aioclient_mock
):
    entry = await setup_v2(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    missing = AutodartsEndpointMissing("starting")
    for _ in range(2):
        with patch.object(coordinator.client, "get_system", side_effect=missing):
            for _ in range(4):
                await coordinator.async_refresh()
        await coordinator.async_refresh()
    assert entry.data["api_generation"] == 2
    assert "no_system_api" not in entry.data
    assert state(hass, "sensor", "cpu_usage") == "12.5"


@pytest.mark.usefixtures("cpu_usage")
async def test_a_board_that_brings_the_system_endpoint_at_start_is_board_manager_2(
    hass, aioclient_mock
):
    aioclient_mock.get(BASE + "/api/version", text="2.1.0")
    mock_board_v2(aioclient_mock, system={**deepcopy(SYSTEM), "version": "2.1.0"})
    data = {**local_entry_data(), "api_generation": 1, "no_system_api": "2.0.0"}
    entry = MockConfigEntry(domain="homedarts", version=2, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "no_system_api" not in entry.data
    assert entry.data["api_generation"] == 2
    await entry.runtime_data.local.async_refresh()
    assert state(hass, "sensor", "cpu_usage") == "12.5"


async def test_new_board_manager_version_asks_for_the_system_endpoint_again(
    hass, aioclient_mock, freezer
):
    mock_board(aioclient_mock, version="2.0.0")
    aioclient_mock.get(BASE + "/api/system", status=404)
    data = {**local_entry_data(), "api_generation": 1, "no_system_api": "2.0.0"}
    entry = MockConfigEntry(domain="homedarts", version=2, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.data["api_generation"] == 1
    # Board Manager 2.1.0 is installed while Home Assistant runs.
    aioclient_mock.clear_requests()
    aioclient_mock.get(BASE + "/api/version", text="2.1.0")
    mock_board_v2(aioclient_mock, system={**deepcopy(SYSTEM), "version": "2.1.0"})
    freezer.tick(timedelta(seconds=30))
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await entry.runtime_data.local.async_refresh()
    reload.assert_called_once_with(entry.entry_id)
    assert "no_system_api" not in entry.data
    assert entry.data["api_generation"] == 2


async def test_board_without_system_endpoint_of_unknown_version_stays_classic(
    hass, aioclient_mock
):
    mock_board(aioclient_mock, version="2.0.0")
    aioclient_mock.get(BASE + "/api/system", status=404)
    data = {**local_entry_data(), "api_generation": 1, "no_system_api": ""}
    entry = MockConfigEntry(domain="homedarts", version=2, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.data["api_generation"] == 1
    # Once the version is known, it is the one without the route: a new
    # version asks again.
    assert entry.data["no_system_api"] == "2.0.0"
    assert "board-1_upstream" in unique_ids(hass, entry)


def test_board_generation_from_version():
    assert board_generation("2.0.0") == 2
    assert board_generation("v1.0.7") == 1
    assert board_generation(" 10.1 ") == 10
    for value in (None, "", "beta", "0.9", 2):
        assert board_generation(value) is None


async def test_board_pc_details_without_private_names(hass, aioclient_mock):
    entry = await setup_v2(hass, aioclient_mock)
    system = hass.states.get(entity_id(hass, "sensor", "host_os"))
    assert system.state == "Debian 13"
    assert system.attributes["kernel"] == "6.12.107+deb13-amd64"
    assert system.attributes["architecture"] == "x86_64"
    processor = hass.states.get(entity_id(hass, "sensor", "host_processor"))
    assert processor.state == "Intel(R) Core(TM) i3-9100T CPU @ 3.10GHz"
    assert processor.attributes["cores"] == 4
    vision = hass.states.get(entity_id(hass, "sensor", "vision_version"))
    assert vision.state == "2.0.0"
    assert vision.attributes["opencv_version"] == "5.0.0"
    registry = er.async_get(hass)
    for key in ("host_os", "host_processor", "vision_version"):
        entry_ = registry.async_get(entity_id(hass, "sensor", key))
        assert entry_.entity_category == er.EntityCategory.DIAGNOSTIC
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["local"]["board_pc"]["vision_version"] == "2.0.0"
    for private in ("dartboard-pc", "198.51.100.7", "USB Camera"):
        assert private not in str(entry.runtime_data.local.data)
        assert private not in str(diagnostics)
        assert private not in str(hass.states.async_all())


@pytest.mark.usefixtures("cpu_usage")
async def test_board_without_host_details_keeps_working(hass, aioclient_mock):
    aioclient_mock.get(BASE + "/api/host", status=404)
    entry = await setup_v2(hass, aioclient_mock)
    assert entry.runtime_data.local.data["board_pc"] == {}
    assert state(hass, "sensor", "host_os") == "unknown"
    assert state(hass, "sensor", "vision_version") == "unknown"
    assert state(hass, "sensor", "cpu_usage") == "12.5"


@pytest.mark.usefixtures("cpu_usage")
async def test_failed_host_read_is_asked_again_at_the_next_poll(hass, aioclient_mock):
    aioclient_mock.get(BASE + "/api/host", status=503)
    entry = await setup_v2(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    assert "board_pc" not in coordinator.data
    assert state(hass, "sensor", "cpu_usage") == "12.5"

    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock)
    await coordinator.async_refresh()
    assert state(hass, "sensor", "host_os") == "Debian 13"
    assert [call[1].path for call in aioclient_mock.mock_calls].count("/api/host") == 1


async def test_board_that_tells_no_version_runs_as_classic(
    hass, aioclient_mock, freezer
):
    aioclient_mock.get(BASE + "/api/version", status=404)
    entry = await setup_local(hass, aioclient_mock)
    assert "api_generation" not in entry.data
    coordinator = entry.runtime_data.local
    assert coordinator.generation is None
    ids = unique_ids(hass, entry)
    assert "board-1_upstream" in ids and "board-1_cloud_link" not in ids
    assert state(hass, "switch", "detection") == "off"
    # The version is asked with the other metadata, not with every poll.
    aioclient_mock.clear_requests()
    aioclient_mock.get(BASE + "/api/version", status=404)
    mock_board(aioclient_mock)
    for _ in range(10):
        freezer.tick(timedelta(seconds=2))
        await coordinator.async_refresh()
    paths = [call[1].path for call in aioclient_mock.mock_calls]
    assert paths.count("/api/version") == 0
    freezer.tick(timedelta(seconds=10))
    await coordinator.async_refresh()
    paths = [call[1].path for call in aioclient_mock.mock_calls]
    # Once as the probe of the generation, once with the metadata.
    assert paths.count("/api/version") == 2


async def test_cameras_are_read_right_after_the_detection_starts(hass, aioclient_mock):
    """Board Manager 2 sends no camera messages, so a start triggers one read."""
    stopped = deepcopy(SYSTEM)
    stopped["camState"] = {"isOpened": False, "isRunning": False}
    entry = await setup_v2(hass, aioclient_mock, system=stopped)
    coordinator = entry.runtime_data.local
    assert state(hass, "binary_sensor", "cameras_active") == "off"

    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock, state={**STATE, "running": True, "status": "Throw"})
    board = {**STATE, "running": True, "status": "Starting", "event": "Starting"}
    coordinator.async_receive("state", board)
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "cameras_active") == "on"
    reads = [call[1].path for call in aioclient_mock.mock_calls]
    assert reads.count("/api/system") == 1

    # Takeouts change the status too, but never the cameras.
    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock, state={**STATE, "running": True, "status": "Throw"})
    for status in ("Throw", "Takeout in progress", "Throw"):
        coordinator.async_receive("state", {**board, "status": status})
    await hass.async_block_till_done()
    assert not aioclient_mock.mock_calls


async def test_board_pc_details_are_read_again_every_hour(
    hass, aioclient_mock, freezer
):
    entry = await setup_v2(hass, aioclient_mock)
    coordinator = entry.runtime_data.local

    async def host_reads():
        await coordinator.async_refresh()
        paths = [call[1].path for call in aioclient_mock.mock_calls]
        aioclient_mock.clear_requests()
        mock_board_v2(aioclient_mock)
        return paths.count("/api/host")

    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock)
    freezer.tick(timedelta(minutes=59))
    assert await host_reads() == 0
    freezer.tick(timedelta(minutes=1))
    assert await host_reads() == 1
    assert await host_reads() == 0
