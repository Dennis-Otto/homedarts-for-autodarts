"""Exercise local entities and services in a real HA setup."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homedarts.camera import AutodartsCamera
from custom_components.homedarts.diagnostics import async_get_config_entry_diagnostics
from custom_components.homedarts.errors import AutodartsConnectionError

from .local_helpers import (
    BASE,
    CONFIG,
    STATE,
    entity_id,
    entity_summary,
    local_entry_data,
    mock_board,
    setup_local,
    state,
)


async def test_local_setup_entities_and_private_diagnostics(
    hass, aioclient_mock, snapshot
):
    entry = await setup_local(hass, aioclient_mock)
    assert all(str(call[1]).startswith(BASE) for call in aioclient_mock.mock_calls)
    registry = er.async_get(hass)
    assert entity_summary(hass, entry) == snapshot
    assert state(hass, "switch", "detection") == "off"
    assert state(hass, "switch", "upstream") == "on"
    assert state(hass, "binary_sensor", "local_connected") == "on"
    assert state(hass, "select", "standby_minutes") == "15"
    assert state(hass, "sensor", "local_status") == "stopped"
    assert state(hass, "sensor", "local_visit_score") == "0"
    camera = registry.async_get(entity_id(hass, "camera", "camera_0"))
    assert camera.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert (
        registry.async_get(entity_id(hass, "button", "calibrate")).disabled_by is None
    )
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("homedarts", "board-1"), entry.entry_id
    )
    assert device.name == "Autodarts Board"
    assert device.sw_version == "1.0.7"
    assert device.configuration_url == BASE
    # The complete diagnostics are compared in test_diagnostics.py.
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["local"]["settings"]["board_id"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["host"] == "**REDACTED**"
    for sensitive in ("private-board-api-key", "api_key", "192.0.2.10", "/dev/video0"):
        assert sensitive not in str(diagnostics)
    coordinator = entry.runtime_data.local
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not list(coordinator.async_contexts())


@pytest.mark.parametrize(
    ("key", "method", "path"),
    [
        ("calibrate", "post", "/api/config/calibration/auto"),
        ("reset", "post", "/api/reset"),
        ("restart", "post", "/api/restart"),
        ("start", "put", "/api/start"),
        ("stop", "put", "/api/stop"),
    ],
)
async def test_button_services_send_commands(hass, aioclient_mock, key, method, path):
    await setup_local(hass, aioclient_mock)
    getattr(aioclient_mock, method)(BASE + path, status=204)
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id(hass, "button", key)}, blocking=True
    )
    calls = [call for call in aioclient_mock.mock_calls if call[0] != "GET"]
    assert [(call[0], str(call[1])) for call in calls] == [
        (method.upper(), BASE + path)
    ]


async def test_switch_and_select_refresh_actual_board_state(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    aioclient_mock.put(BASE + "/api/start", status=204)
    # An accepted command need not have changed the physical state yet.
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id(hass, "switch", "detection")},
        blocking=True,
    )
    assert state(hass, "switch", "detection") == "off"
    with patch.object(
        entry.runtime_data.local.client,
        "get_state",
        return_value={**STATE, "running": True},
    ):
        await entry.runtime_data.local.async_refresh()
    assert state(hass, "switch", "detection") == "on"
    aioclient_mock.patch(BASE + "/api/config", status=204)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id(hass, "switch", "auto_calibrate")},
        blocking=True,
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id(hass, "select", "standby_minutes"), "option": "30"},
        blocking=True,
    )
    writes = [call[2] for call in aioclient_mock.mock_calls if call[0] == "PATCH"]
    assert writes == [
        {"cam": {"auto_calibrate": False}},
        {"motion": {"standby_minutes": 30}},
    ]


async def test_cloud_connection_switch_connects_and_disconnects(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock)
    aioclient_mock.put(BASE + "/api/upstream/connect", status=204)
    aioclient_mock.put(BASE + "/api/upstream/disconnect", status=204)
    for service in ("turn_off", "turn_on"):
        await hass.services.async_call(
            "switch",
            service,
            {"entity_id": entity_id(hass, "switch", "upstream")},
            blocking=True,
        )
    writes = [call for call in aioclient_mock.mock_calls if call[0] != "GET"]
    assert [(call[0], call[1].path) for call in writes] == [
        ("PUT", "/api/upstream/disconnect"),
        ("PUT", "/api/upstream/connect"),
    ]


async def test_camera_frame_rates_follow_the_camera_order(
    hass, aioclient_mock, freezer
):
    aioclient_mock.get(BASE + "/api/cams/stats", json={"fps": [29.9, "fast"]})
    entry = await setup_local(hass, aioclient_mock)
    registry = er.async_get(hass)
    for index in range(3):
        sensor = entity_id(hass, "sensor", f"camera_{index}_fps")
        assert registry.async_get(sensor).disabled_by is not None
        registry.async_update_entity(sensor, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, "sensor", "camera_0_fps") == "29.9"
    assert state(hass, "sensor", "camera_1_fps") == "unknown"
    # The board reports fewer cameras than it has configured.
    assert state(hass, "sensor", "camera_2_fps") == "unknown"
    # Cards group the entities of a camera by its number.
    for index in range(3):
        fps = hass.states.get(entity_id(hass, "sensor", f"camera_{index}_fps"))
        assert fps.attributes["camera"] == index + 1
    # A camera the board no longer has is unavailable, like its picture entity.
    config = deepcopy(CONFIG)
    config["cam"]["cams"] = config["cam"]["cams"][:1]
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock, config=config)
    freezer.tick(timedelta(seconds=30))
    await entry.runtime_data.local.async_refresh()
    await hass.async_block_till_done()
    assert state(hass, "sensor", "camera_0_fps") == "29.9"
    assert state(hass, "sensor", "camera_1_fps") == "unavailable"


async def test_command_rejection_is_visible_to_user(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock)
    aioclient_mock.post(BASE + "/api/config/calibration/auto", status=409)
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id(hass, "button", "calibrate")},
            blocking=True,
        )
    # Shown to the user in their language, from the translated exception.
    assert error.value.translation_key == "action_failed"
    assert "did not accept the action" in str(error.value)


async def test_disconnect_and_recovery_updates_entities(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    with patch.object(
        coordinator.client, "get_state", side_effect=AutodartsConnectionError
    ):
        # Two missed polls, a few seconds, are a hiccup rather than an outage.
        for _ in range(2):
            await coordinator.async_refresh()
            assert state(hass, "binary_sensor", "local_connected") == "on"
            assert state(hass, "switch", "detection") == "off"
        await coordinator.async_refresh()
    assert state(hass, "binary_sensor", "local_connected") == "off"
    assert state(hass, "button", "calibrate") == "unavailable"
    assert state(hass, "switch", "detection") == "unavailable"
    await coordinator.async_refresh()
    assert state(hass, "binary_sensor", "local_connected") == "on"
    assert state(hass, "switch", "detection") == "off"


async def test_optional_endpoints_and_delayed_camera_discovery(
    hass, aioclient_mock, freezer
):
    entry = await setup_local(hass, aioclient_mock, config_status=404)
    assert state(hass, "switch", "detection") == "off"
    assert state(hass, "switch", "auto_calibrate") == "unavailable"
    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("camera", "homedarts", "board-1_camera_0") is None
    )
    coordinator = entry.runtime_data.local
    with patch.object(
        coordinator.client, "get_config", return_value={"camera_count": 2}
    ):
        # The settings of Board Manager 1 are read again after 30 seconds.
        freezer.tick(timedelta(seconds=29))
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert (
            registry.async_get_entity_id("camera", "homedarts", "board-1_camera_1")
            is None
        )
        freezer.tick(timedelta(seconds=1))
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert entity_id(hass, "camera", "camera_1")
    assert entity_id(hass, "sensor", "camera_1_fps")


async def test_throw_scores_and_snapshot(hass, aioclient_mock):
    throws = [
        {"segment": {"name": "T20", "number": 20, "multiplier": 3}},
        {"segment": {"name": "D16", "number": 16, "multiplier": 2}},
    ]
    entry = await setup_local(
        hass, aioclient_mock, state={**STATE, "numThrows": 2, "throws": throws}
    )
    assert state(hass, "sensor", "last_throw") == "D16"
    assert state(hass, "sensor", "last_throw_score") == "32"
    assert state(hass, "sensor", "local_visit_score") == "92"
    assert state(hass, "sensor", "num_throws") == "2"
    aioclient_mock.get(
        BASE + "/api/img/cams/0",
        content=b"jpeg",
        headers={"Content-Type": "image/jpeg"},
    )
    camera = AutodartsCamera(entry.runtime_data.local, 0)
    assert await camera.async_camera_image() == b"jpeg"
    assert not any(call[0] != "GET" for call in aioclient_mock.mock_calls)
    # A camera without a picture shows none instead of failing.
    aioclient_mock.get(BASE + "/api/img/cams/1", status=503)
    silent = AutodartsCamera(entry.runtime_data.local, 1)
    assert await silent.async_camera_image() is None


async def test_wrong_board_at_configured_address_cannot_be_controlled(
    hass, aioclient_mock
):
    config = deepcopy(CONFIG)
    config["auth"]["board_id"] = "another-board"
    mock_board(aioclient_mock, config=config)
    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    # The entry loads for training and games; the board stays out of reach.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "local_connected") == "off"
    assert state(hass, "switch", "detection") == "unavailable"
    assert state(hass, "button", "calibrate") == "unavailable"
    assert state(hass, "switch", "training_session") == "on"
    issue = ir.async_get(hass).async_get_issue(
        "homedarts", f"wrong_board_{entry.entry_id}"
    )
    assert issue.translation_placeholders == {"address": BASE}
