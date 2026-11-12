"""A dartboard without Autodarts: set up without a board, every dart entered in
Home Assistant, with the games, the training and the statistics of a board."""

from contextlib import suppress
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.homedarts.config_flow import AutodartsConfigFlow
from custom_components.homedarts.const import DISCOVERY_URL
from custom_components.homedarts.diagnostics import async_get_config_entry_diagnostics
from custom_components.homedarts.games_coordinator import AutodartsGamesCoordinator
from custom_components.homedarts.local_api import AutodartsLocalClient
from custom_components.homedarts.local_coordinator import AutodartsLocalCoordinator
from custom_components.homedarts.manual_coordinator import (
    MANUAL_STATE,
    AutodartsManualCoordinator,
)
from custom_components.homedarts.storage import storage_key

from .local_helpers import entity_summary, mock_board, mock_board_v2, record

BOARD_ID = "manual_0123456789abcdef0123456789abcdef"
DATA = {
    "board_id": BOARD_ID,
    "manual_board": True,
    "name": "Garage",
}


async def setup_manual(hass, **kwargs) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        unique_id=BOARD_ID,
        title="Autodarts (Garage)",
        data=DATA,
        **kwargs,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity(hass, platform: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        platform, "homedarts", f"{BOARD_ID}_{key}"
    )


def value(hass, platform: str, key: str) -> str:
    entity_id = entity(hass, platform, key)
    assert entity_id is not None
    return hass.states.get(entity_id).state


async def act(hass, service: str, **data) -> None:
    await hass.services.async_call("homedarts", service, data, blocking=True)
    await hass.async_block_till_done()


async def test_setup_offers_a_dartboard_without_autodarts(hass):
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_USER}
    )
    assert result["menu_options"][-1] == "manual"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    # The name is trimmed, and none is no name.
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "   "}
        )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": " Garage "}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garage"
    entry = result["result"]
    board_id = entry.data["board_id"]
    assert board_id.startswith("manual_") and len(board_id) == 39
    assert entry.unique_id == board_id
    assert entry.data == {
        "board_id": board_id,
        "manual_board": True,
        "name": "Garage",
    }
    # The options keep the own training plans, on every board.
    assert AutodartsConfigFlow.async_supports_options_flow(entry)
    assert entry.supports_options


async def test_a_dartboard_without_autodarts_keeps_own_plans(hass):
    entry = await setup_manual(hass)
    plans = [{"name": "Garage evening", "steps": [{"drill": "doubles", "darts": 30}]}]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    # Without a board, there is no bridge for online matches: only the plans.
    assert result["step_id"] == "init"
    assert [str(key) for key in result["data_schema"].schema] == ["plans"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"plans": plans}
    )
    await hass.async_block_till_done()
    # The plans are kept at once, without the step of the bridge's address.
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"plans": plans}
    # The options reload the entry, whose coordinator reads them anew.
    coordinator = entry.runtime_data.local
    assert isinstance(coordinator, AutodartsManualCoordinator)
    assert [plan.name for plan in coordinator.games.plans.custom] == ["Garage evening"]
    await hass.services.async_call(
        "homedarts", "start_plan", {"plan": "Garage evening"}, blocking=True
    )
    assert coordinator.games.practice.drill == "doubles"

    # The form shows the stored plans again, and an empty list removes them.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    defaults = {str(key): key.default() for key in result["data_schema"].schema}
    assert defaults == {"plans": plans}
    await hass.config_entries.options.async_configure(result["flow_id"], {"plans": {}})
    await hass.async_block_till_done()
    assert entry.options == {}
    assert entry.runtime_data.local.games.plans.custom == ()


async def test_a_home_may_have_several_dartboards_without_autodarts(hass):
    for name in ("Garage", "Cellar"):
        result = await hass.config_entries.flow.async_init(
            "homedarts", context={"source": SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        flow = hass.config_entries.flow.async_progress()[0]["flow_id"]
        await hass.config_entries.flow.async_configure(flow, {"name": name})
        await hass.async_block_till_done()
    entries = hass.config_entries.async_entries("homedarts")
    assert [entry.title for entry in entries] == [
        "Garage",
        "Cellar",
    ]
    assert len({entry.unique_id for entry in entries}) == 2
    names = {
        device.name
        for entry in entries
        for device in dr.async_entries_for_config_entry(
            dr.async_get(hass), entry.entry_id
        )
    }
    assert names == {"Garage", "Cellar"}


async def test_a_dartboard_without_autodarts_has_the_entities_of_the_games(
    hass, aioclient_mock, snapshot
):
    entry = await setup_manual(hass)
    # Nothing is ever asked of a board.
    assert not aioclient_mock.mock_calls
    coordinator = entry.runtime_data.local
    assert isinstance(coordinator, AutodartsManualCoordinator)
    assert coordinator.manual_board and coordinator.update_interval is None
    assert entry.runtime_data.bridge is None
    assert entity_summary(hass, entry) == snapshot
    assert value(hass, "sensor", "local_status") == "manual"
    assert value(hass, "sensor", "local_visit_score") == "0"
    assert value(hass, "switch", "training_session") == "on"
    # Every dart is entered by hand, so manual entry is on and cannot be turned off.
    assert coordinator.games.practice.manual_entry
    for platform, key in (
        ("switch", "practice_manual_entry"),
        ("switch", "detection"),
        ("switch", "free_stuck_takeout"),
        ("binary_sensor", "local_connected"),
        ("button", "calibrate"),
        ("select", "standby_minutes"),
        ("sensor", "correction_rate"),
        ("sensor", "num_throws"),
        ("sensor", "detection_fps"),
        ("camera", "camera_0"),
        ("update", "board_software"),
    ):
        assert entity(hass, platform, key) is None, key
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("homedarts", BOARD_ID), entry.entry_id
    )
    assert device.name == "Garage"
    assert device.manufacturer is None
    assert device.configuration_url is None and device.sw_version is None
    # Time passes without a read of any board.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert not aioclient_mock.mock_calls
    assert value(hass, "sensor", "local_status") == "manual"


async def test_every_dart_is_entered_by_hand(hass):
    entry = await setup_manual(hass)
    coordinator = entry.runtime_data.local
    await act(hass, "start_game", game="501", players=["Alex", "Sam"])
    events = record(hass, coordinator)
    for bed in ("T20", "T20", "T20"):
        await act(hass, "throw_dart", segment=bed)
    assert value(hass, "sensor", "local_visit_score") == "180"
    assert value(hass, "sensor", "last_throw") == "T20"
    await act(hass, "next_player")
    assert value(hass, "sensor", "practice_remaining") == "501"
    remaining = hass.states.get(entity(hass, "sensor", "practice_remaining"))
    assert remaining.attributes["name"] == "Sam"
    assert value(hass, "sensor", "training_darts") == "3"
    assert value(hass, "sensor", "training_scores_180") == "1"
    kinds = [kind for kind, _ in events]
    assert kinds.count("dart_detected") == 3
    assert "visit_thrown" in kinds and "visit_completed" in kinds
    completed = next(item for kind, item in events if kind == "visit_completed")
    assert completed["score"] == 180 and completed["manual"] is True
    # Sam passes.
    await act(hass, "next_player")
    remaining = hass.states.get(entity(hass, "sensor", "practice_remaining"))
    assert remaining.attributes["name"] == "Alex"
    # The board waits for darts; the status never changes by itself.
    assert value(hass, "sensor", "local_status") == "manual"
    assert coordinator.data["local"] == MANUAL_STATE


async def test_manual_entry_stays_on_after_a_restart(hass, hass_storage):
    # The store of a board that had manual entry off, before it lost its Autodarts.
    hass_storage[storage_key("manual-entry")] = {
        "version": 1,
        "minor_version": 3,
        "key": storage_key("manual-entry"),
        "data": {"practice": {"game": 301, "manual_entry": False}},
    }
    entry = await setup_manual(hass, entry_id="manual-entry")
    coordinator = entry.runtime_data.local
    assert coordinator.games.practice.manual_entry
    await act(hass, "throw_dart", segment="S20")
    await act(hass, "next_player")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.local
    assert coordinator.games.practice.manual_entry
    assert value(hass, "sensor", "practice_remaining") == "281"
    assert value(hass, "sensor", "training_darts") == "1"
    # A refresh keeps the game as it is.
    await coordinator.async_refresh()
    assert value(hass, "sensor", "practice_remaining") == "281"


async def test_a_dartboard_without_autodarts_has_no_transport(hass):
    entry = await setup_manual(hass)
    coordinator = entry.runtime_data.local
    # It plays the games beside the board's coordinator, not as a board whose
    # transport is switched off: there is nothing on it to control.
    assert isinstance(coordinator, AutodartsGamesCoordinator)
    assert not isinstance(coordinator, AutodartsLocalCoordinator)
    for name in ("client", "async_action", "async_recalibrate", "readings", "topics"):
        assert not hasattr(coordinator, name), name


async def test_no_code_of_a_dartboard_without_autodarts_reaches_a_client(
    hass, aioclient_mock
):
    # A client of a Board Manager, made anywhere from here on, fails the test.
    with patch.object(
        AutodartsLocalClient, "__init__", side_effect=AssertionError("a client")
    ):
        entry = await setup_manual(hass)
        await act(hass, "start_game", game="501", players=["Alex", "Sam"])
        await act(hass, "throw_dart", segment="T20")
        await act(hass, "correct_dart", dart=1, segment="T19")
        await act(hass, "next_player")
        await act(hass, "enter_visit", score=60)
        await act(hass, "undo_visit")
        # Every button and switch of the board, once on and once off; the
        # games may refuse one, such as a tournament without players.
        entity_ids = [
            item.entity_id
            for item in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
        ]
        for entity_id in entity_ids:
            domain = entity_id.split(".")[0]
            services = {"button": ("press",), "switch": ("turn_off", "turn_on")}
            for service in services.get(domain, ()):
                with suppress(ServiceValidationError):
                    await hass.services.async_call(
                        domain, service, {"entity_id": entity_id}, blocking=True
                    )
        await hass.async_block_till_done()
        await async_get_config_entry_diagnostics(hass, entry)
        await entry.runtime_data.local.async_refresh()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)
    assert not aioclient_mock.mock_calls


async def test_diagnostics_of_a_dartboard_without_autodarts(hass):
    entry = await setup_manual(hass)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["connection"] == {"manual_board": True}
    assert diagnostics["local_available"] is True
    assert diagnostics["realtime_connected"] is False
    assert diagnostics["board_manager_generation"] is None


async def reconfigure(hass, entry, step: str) -> dict:
    result = await hass.config_entries.flow.async_init(
        "homedarts",
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure_manual"
    assert result["menu_options"] == ["discover", "local"]
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


async def play_a_visit(hass) -> None:
    await act(hass, "start_game", game="301", players=["Alex"])
    for bed in ("T20", "T20", "S20"):
        await act(hass, "throw_dart", segment=bed)
    await act(hass, "next_player")


def board_state(hass, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, "homedarts", f"board-1_{key}"
    )
    assert entity_id is not None, key
    return hass.states.get(entity_id).state


async def test_an_autodarts_board_joins_a_dartboard_without_autodarts(
    hass, aioclient_mock
):
    entry = await setup_manual(hass)
    await play_a_visit(hass)
    registry = er.async_get(hass)
    darts = entity(hass, "sensor", "training_darts")
    result = await reconfigure(hass, entry, "local")
    assert result["step_id"] == "local"
    mock_board(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.10", "port": 3180}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "board_connected"
    assert entry.unique_id == "board-1"
    assert entry.title == "Autodarts (Garage)"
    assert entry.data == {
        "board_id": "board-1",
        "name": "Garage",
        "host": "192.0.2.10",
        "port": 3180,
        "api_generation": 1,
    }
    assert not entry.runtime_data.local.manual_board
    # Every entity keeps its entity ID, with the board's ID in its unique ID.
    assert (
        registry.async_get_entity_id("sensor", "homedarts", "board-1_training_darts")
        == darts
    )
    assert not [
        item.unique_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.unique_id.startswith("manual_")
    ]
    # The games and the statistics stay; the board brings what was missing.
    assert hass.states.get(darts).state == "3"
    assert board_state(hass, "sensor", "practice_remaining") == "161"
    assert board_state(hass, "binary_sensor", "local_connected") == "on"
    assert board_state(hass, "sensor", "local_status") == "stopped"
    assert board_state(hass, "switch", "practice_manual_entry") == "on"
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert [(device.name, device.identifiers) for device in devices] == [
        ("Garage", {("homedarts", "board-1")})
    ]
    assert devices[0].manufacturer == "Autodarts"


async def test_the_board_search_finds_the_board_of_a_dartboard_without_autodarts(
    hass, aioclient_mock
):
    entry = await setup_manual(hass)
    aioclient_mock.get(
        DISCOVERY_URL,
        json=[
            {
                "boardId": "board-1",
                "name": "Garage",
                "ip": "192.0.2.10",
                "port": "3180",
                "insecurePort": "3180",
                "version": "2.0.0",
            }
        ],
    )
    mock_board_v2(aioclient_mock)
    result = await reconfigure(hass, entry, "discover")
    assert result["step_id"] == "discover"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"board_id": "board-1"}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "board_connected"
    assert entry.data["api_generation"] == 2
    assert entry.runtime_data.local.board_manager_2


async def test_an_entity_left_behind_by_the_board_gives_way(hass, aioclient_mock):
    entry = await setup_manual(hass)
    registry = er.async_get(hass)
    # An entity of the board's earlier entry, which the registry kept.
    left = registry.async_get_or_create(
        "sensor", "homedarts", "board-1_training_darts", suggested_object_id="old"
    )
    darts = entity(hass, "sensor", "training_darts")
    result = await reconfigure(hass, entry, "local")
    # A board whose version does not tell its generation yet.
    mock_board(aioclient_mock, version="")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.10", "port": 3180}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "board_connected"
    assert "api_generation" not in entry.data
    assert registry.async_get(left.entity_id) is None
    assert (
        registry.async_get_entity_id("sensor", "homedarts", "board-1_training_darts")
        == darts
    )


async def test_a_board_of_another_entry_stays_where_it_is(hass, aioclient_mock):
    mock_board(aioclient_mock)
    other = MockConfigEntry(
        domain="homedarts",
        version=2,
        unique_id="board-1",
        data={"board_id": "board-1", "host": "192.0.2.10", "port": 3180},
    )
    other.add_to_hass(hass)
    entry = await setup_manual(hass)
    result = await reconfigure(hass, entry, "local")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.10", "port": 3180}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == BOARD_ID and entry.data == DATA
    # A board that does not answer leaves the dartboard as it is, too.
    aioclient_mock.get("http://192.0.2.99:3180/api/state", status=503)
    result = await reconfigure(hass, entry, "local")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.99", "port": 3180}
    )
    assert result["errors"] == {"base": "cannot_connect_local"}
    assert entry.data == DATA


async def test_removing_a_dartboard_without_autodarts_removes_its_training(
    hass, hass_storage
):
    entry = await setup_manual(hass)
    await act(hass, "start_game", game="301")
    await act(hass, "throw_dart", segment="S20")
    await act(hass, "next_player")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert storage_key(entry.entry_id) in hass_storage
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert storage_key(entry.entry_id) not in hass_storage
