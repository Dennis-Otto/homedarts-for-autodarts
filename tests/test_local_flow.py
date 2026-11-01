"""Local onboarding and reconfiguring the address of a board."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .local_helpers import BASE, CONFIG, local_entry_data, mock_board


async def open_local(hass, entry=None):
    context = {"source": SOURCE_USER}
    if entry:
        context = {"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    result = await hass.config_entries.flow.async_init("homedarts", context=context)
    assert result["type"] == FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "local"}
    )


async def test_create_local_entry_without_credentials(hass, aioclient_mock):
    mock_board(aioclient_mock)
    result = await open_local(hass)
    assert set(result["data_schema"].schema) == {"host", "port"}
    with patch("custom_components.homedarts.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.10", "port": 3180}
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {**local_entry_data(), "api_generation": 1}
    assert result["result"].unique_id == "board-1"
    assert all(str(call[1]).startswith(BASE) for call in aioclient_mock.mock_calls)


@pytest.mark.parametrize(
    "host", ["", "http://192.0.2.10:3180", "some host", "user@host", "192.0.2.10:3180"]
)
async def test_bad_host_has_useful_validation(hass, aioclient_mock, host):
    result = await open_local(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": host, "port": 3180}
    )
    assert result["errors"] == {"host": "invalid_host"}
    await create_after_error(hass, aioclient_mock, result)


async def create_after_error(hass, aioclient_mock, result):
    """The form keeps its flow: the correct address sets the board up."""
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock)
    with patch("custom_components.homedarts.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.10", "port": 3180}
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Autodarts (192.0.2.10)"


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        ("offline", "cannot_connect_local"),
        ("refused", "board_access_denied"),
        ("no_board", "board_not_configured"),
    ],
)
async def test_local_setup_errors(hass, aioclient_mock, failure, error):
    if failure == "offline":
        aioclient_mock.get(BASE + "/api/state", status=503)
    elif failure == "refused":
        # Something in front of the board asks for a login it never needs.
        aioclient_mock.get(BASE + "/api/state", status=401)
    else:
        config = deepcopy(CONFIG)
        config["auth"].pop("board_id")
        mock_board(aioclient_mock, config=config)
    result = await open_local(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.10", "port": 3180}
    )
    assert result["errors"] == {"base": error}
    await create_after_error(hass, aioclient_mock, result)


async def test_local_setup_detects_legacy_duplicate(hass, aioclient_mock):
    """An entry from before unique IDs has the board only in its data."""
    mock_board(aioclient_mock)
    entry = MockConfigEntry(domain="homedarts", version=2, data={"board_id": "board-1"})
    entry.add_to_hass(hass)
    result = await open_local(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.10", "port": 3180}
    )
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("board_id", "reason"),
    [("board-1", "reconfigure_successful"), ("board-2", "wrong_board")],
)
async def test_reconfigure_gives_an_entry_without_address_its_board(
    hass, aioclient_mock, board_id, reason
):
    """An entry that only the cloud link reached gets the address of its board."""
    data = {"board_id": "board-1"}
    entry = MockConfigEntry(domain="homedarts", version=2, minor_version=2, data=data)
    entry.add_to_hass(hass)
    config = deepcopy(CONFIG)
    config["auth"]["board_id"] = board_id
    mock_board(aioclient_mock, config=config)
    result = await open_local(hass, entry)
    with patch("custom_components.homedarts.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.10", "port": 3180}
        )
        await hass.async_block_till_done()
    assert result["reason"] == reason
    if board_id == "board-1":
        assert entry.data == {**data, "host": "192.0.2.10", "port": 3180}
    else:
        assert entry.data == data


async def test_menus_offer_the_ways_to_add_a_board(hass):
    """Search, address, a Granboard or a dartboard without Autodarts; no menu
    leads to a login."""
    entry = MockConfigEntry(
        domain="homedarts", version=2, unique_id="board-1", data=local_entry_data()
    )
    entry.add_to_hass(hass)
    for context, options in (
        ({"source": SOURCE_USER}, ["discover", "local", "granboard", "manual"]),
        # A board being set up again stays a board with Autodarts.
        (
            {"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
            ["discover", "local"],
        ),
    ):
        result = await hass.config_entries.flow.async_init("homedarts", context=context)
        assert result["menu_options"] == options
