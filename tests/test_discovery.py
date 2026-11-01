"""Finding boards: mDNS announcements, the Autodarts lookup and manual fallback."""

from ipaddress import ip_address
from unittest.mock import patch

import pytest
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homedarts.const import DISCOVERY_URL

from .local_helpers import (
    BASE,
    local_entry_data,
    mock_board,
    mock_board_v2,
    second_board_config,
)

OTHER = "http://192.0.2.20:3180"
LISTED = [
    {
        "boardId": "board-1",
        "name": "Living room",
        "ip": "192.0.2.10",
        "port": "3180",
        "insecurePort": "3180",
        "version": "2.0.0",
    },
    {"boardId": "", "ip": "192.0.2.30"},
    {"boardId": "no-ip"},
    {"boardId": "bad-ip", "ip": "not an address"},
    "garbage",
]


def zeroconf(
    host: str = "192.0.2.10",
    properties: dict | None = None,
    addresses: list[str] | None = None,
    port: int | None = 3180,
):
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(address) for address in addresses or [host]],
        hostname="autodarts.local.",
        name="autodarts-board._autodarts-board._tcp.local.",
        port=port,
        type="_autodarts-board._tcp.local.",
        properties={"id": "25648ad55ac6060d", "cams": "3"}
        if properties is None
        else properties,
    )


async def start(hass, source=SOURCE_USER, entry=None):
    context = {"source": source}
    if entry:
        context["entry_id"] = entry.entry_id
    return await hass.config_entries.flow.async_init("homedarts", context=context)


def moved(hass, entry) -> ir.IssueEntry | None:
    """The repair that offers the entry a new address."""
    return ir.async_get(hass).async_get_issue(
        "homedarts", f"board_moved_{entry.entry_id}"
    )


async def confirm_repair(hass, hass_client, issue_id: str) -> dict:
    """Open the repair and confirm it, as the user does in the UI."""
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    response = await client.post(
        "/api/repairs/issues/fix", json={"handler": "homedarts", "issue_id": issue_id}
    )
    flow = await response.json()
    response = await client.post(f"/api/repairs/issues/fix/{flow['flow_id']}", json={})
    return await response.json()


async def test_announced_board_is_added_with_one_click(hass, aioclient_mock):
    mock_board_v2(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=zeroconf()
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "host": "192.0.2.10",
        "version": "2.0.0",
        "cameras": "3",
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {**local_entry_data(), "api_generation": 2}
    assert result["result"].unique_id == "board-1"


async def test_announced_address_property_is_preferred(hass, aioclient_mock):
    mock_board_v2(aioclient_mock)
    info = zeroconf(
        "fe80::1",
        {"ip": "192.0.2.10", "cams": "3"},
        ["fe80::1", "192.0.2.99", "192.0.2.10"],
    )
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=info
    )
    assert result["description_placeholders"]["host"] == "192.0.2.10"


@pytest.mark.parametrize(
    ("addresses", "advertised"),
    [
        # Any device can put any address into its announcement.
        (["2001:db8::5", "192.0.2.10"], "198.51.100.66"),
        (["fe80::1", "192.0.2.10"], "127.0.0.1"),
        (["192.0.2.10"], None),
    ],
)
async def test_announced_address_must_be_the_senders(
    hass, aioclient_mock, addresses, advertised
):
    mock_board_v2(aioclient_mock)
    properties = {"cams": "3"} if advertised is None else {"ip": advertised}
    info = zeroconf("fe80::1", properties, addresses)
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=info
    )
    # IPv4 of the sender first; no other host is ever contacted.
    assert result["description_placeholders"]["host"] == "192.0.2.10"
    assert {call[1].host for call in aioclient_mock.mock_calls} == {"192.0.2.10"}


async def test_announced_ipv6_board_is_reached_over_ipv6(hass, aioclient_mock):
    mock_board_v2(aioclient_mock, base="http://[2001:db8::10]:3180")
    info = zeroconf("2001:db8::10", {"ip": "2001:db8::10"})
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=info
    )
    assert result["description_placeholders"]["host"] == "2001:db8::10"


async def test_announcement_without_usable_address_is_ignored(hass, aioclient_mock):
    info = zeroconf("127.0.0.1", {"ip": "127.0.0.1"}, ["127.0.0.1", "fe80::1"])
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=info
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect_local"
    assert not aioclient_mock.mock_calls


@pytest.mark.parametrize(
    ("properties", "port", "expected"),
    [
        ({"insecurePort": "3181"}, 443, 3181),
        ({"insecurePort": "none"}, 3182, 3182),
        ({"insecurePort": "70000"}, None, 3180),
        ({}, 3183, 3183),
    ],
)
async def test_announced_plain_http_port_is_used(
    hass, aioclient_mock, properties, port, expected
):
    mock_board_v2(aioclient_mock, base=f"http://192.0.2.10:{expected}")
    info = zeroconf(properties=properties, port=port)
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=info
    )
    with patch("custom_components.homedarts.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
    assert result["data"]["port"] == expected
    assert {call[1].port for call in aioclient_mock.mock_calls} == {expected}


async def test_announced_known_board_moves_once_the_user_confirms(
    hass, aioclient_mock, hass_client
):
    aioclient_mock.get(BASE + "/api/state", status=503)
    mock_board_v2(aioclient_mock, base=OTHER)
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        unique_id="board-1",
        title="Autodarts (192.0.2.10)",
        data=local_entry_data(),
    )
    entry.add_to_hass(hass)
    # The board moved while it was off: the entry loads without it.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert not entry.runtime_data.local.last_update_success
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=zeroconf("192.0.2.20")
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Any device can announce the board ID: the entry stays where it is and
    # a repair asks the user.
    await hass.async_block_till_done()
    assert entry.data["host"] == "192.0.2.10"
    issue = moved(hass, entry)
    assert issue.is_fixable
    assert issue.translation_key == "board_moved"
    assert issue.translation_placeholders == {"old": BASE, "new": OTHER}
    assert issue.data == {
        "entry_id": entry.entry_id,
        "host": "192.0.2.20",
        "port": 3180,
    }

    result = await confirm_repair(hass, hass_client, issue.issue_id)
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.data["host"] == "192.0.2.20"
    # A title that named the old address names the new one.
    assert entry.title == "Autodarts (192.0.2.20)"
    # The entry reloads at the new address.
    assert entry.runtime_data.local.client.base_url == OTHER
    assert entry.runtime_data.local.last_update_success
    assert moved(hass, entry) is None


async def test_board_that_still_answers_is_never_moved(hass, aioclient_mock):
    """Another device that echoes the board ID cannot take over the entry."""
    mock_board(aioclient_mock)
    mock_board_v2(aioclient_mock, base=OTHER)
    entry = MockConfigEntry(
        domain="homedarts", version=2, unique_id="board-1", data=local_entry_data()
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=zeroconf("192.0.2.20")
    )
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == "192.0.2.10"
    assert moved(hass, entry) is None


async def test_ignored_board_is_offered_no_address(hass, aioclient_mock):
    mock_board_v2(aioclient_mock)
    entry = MockConfigEntry(
        domain="homedarts", unique_id="board-1", source=SOURCE_IGNORE, data={}
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=zeroconf()
    )
    assert result["reason"] == "already_configured"
    assert moved(hass, entry) is None


async def test_known_board_at_its_address_is_identified_once(hass, aioclient_mock):
    mock_board_v2(aioclient_mock)
    entry = MockConfigEntry(
        domain="homedarts", version=2, unique_id="board-1", data=local_entry_data()
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=zeroconf()
    )
    assert result["reason"] == "already_configured"
    paths = [call[1].path for call in aioclient_mock.mock_calls]
    assert paths.count("/api/state") == 1


async def test_known_board_without_address_is_offered_the_announced_one(
    hass, aioclient_mock, hass_client
):
    mock_board_v2(aioclient_mock)
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        unique_id="board-1",
        title="Autodarts (Living room)",
        data={"board_id": "board-1"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=zeroconf()
    )
    assert result["reason"] == "already_configured"
    assert "host" not in entry.data
    issue = moved(hass, entry)
    assert issue.translation_placeholders == {"old": "", "new": BASE}
    # The integration runs, as it does for the entries it has.
    assert await async_setup_component(hass, "homedarts", {})
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await confirm_repair(hass, hass_client, issue.issue_id)
    assert result["type"] == "create_entry"
    assert (entry.data["host"], entry.data["port"]) == ("192.0.2.10", 3180)
    # The name of the board stays the title.
    assert entry.title == "Autodarts (Living room)"
    reload.assert_called_once_with(entry.entry_id)


async def test_announced_board_that_does_not_answer_is_ignored(hass, aioclient_mock):
    aioclient_mock.get(BASE + "/api/state", status=503)
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=zeroconf()
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect_local"


async def test_announced_board_without_board_id_asks_for_setup(hass, aioclient_mock):
    mock_board(aioclient_mock, config={"auth": {}, "cam": {}, "motion": {}})
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_ZEROCONF}, data=zeroconf()
    )
    assert result["reason"] == "board_not_configured"


async def test_search_lists_new_boards_and_connects_locally(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY_URL, json=LISTED)
    mock_board_v2(aioclient_mock)
    result = await start(hass)
    assert result["menu_options"] == ["discover", "local", "granboard", "manual"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    assert result["step_id"] == "discover"
    options = result["data_schema"].schema["board_id"].container
    assert options == {"board-1": "Living room · 192.0.2.10 · 2.0.0"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"board_id": "board-1"}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    # The name the board has in Autodarts names the entry and the device.
    assert result["title"] == "Autodarts (Living room)"
    assert result["data"] == {
        **local_entry_data(),
        "api_generation": 2,
        "name": "Living room",
    }
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("homedarts", "board-1"), result["result"].entry_id
    )
    assert device.name == "Living room"


async def test_search_lists_a_board_without_a_name_by_its_address(hass, aioclient_mock):
    nameless = {"boardId": "board-2", "name": " ", "ip": "192.0.2.40"}
    aioclient_mock.get(DISCOVERY_URL, json=[LISTED[0], nameless])
    mock_board(
        aioclient_mock, config=second_board_config(), base="http://192.0.2.40:3180"
    )
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    options = result["data_schema"].schema["board_id"].container
    assert options["board-2"] == "Autodarts · 192.0.2.40"
    with patch("custom_components.homedarts.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"board_id": "board-2"}
        )
    assert result["title"] == "Autodarts (192.0.2.40)"
    assert "name" not in result["data"]


async def test_search_without_new_boards_falls_back_to_address(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY_URL, json=LISTED)
    MockConfigEntry(
        domain="homedarts", unique_id="board-1", data=local_entry_data()
    ).add_to_hass(hass)
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    assert result["step_id"] == "local"
    assert result["errors"] == {"base": "no_boards_found"}
    # The board of the entry above answers at the entered address.
    mock_board(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.10", "port": 3180}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_unavailable_search_falls_back_to_address(hass, aioclient_mock):
    aioclient_mock.get(DISCOVERY_URL, status=503)
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    assert result["step_id"] == "local"
    assert result["errors"] == {"base": "discovery_failed"}
    mock_board(aioclient_mock)
    with patch("custom_components.homedarts.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.10", "port": 3180}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    # Without the search, no name is known.
    assert result["title"] == "Autodarts (192.0.2.10)"
    assert "name" not in result["data"]


async def test_reconfigure_by_search_updates_the_address(hass, aioclient_mock):
    listed = [{**LISTED[0], "ip": "192.0.2.20"}]
    aioclient_mock.get(DISCOVERY_URL, json=listed)
    mock_board_v2(aioclient_mock, base=OTHER)
    entry = MockConfigEntry(
        domain="homedarts", version=2, unique_id="board-1", data=local_entry_data()
    )
    entry.add_to_hass(hass)
    result = await start(hass, SOURCE_RECONFIGURE, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    # The configured board is still offered when reconfiguring it.
    assert result["step_id"] == "discover"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"board_id": "board-1"}
    )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["host"] == "192.0.2.20"
    await hass.async_block_till_done()
    assert entry.runtime_data.local.client.base_url == OTHER


async def test_search_keeps_the_found_address_when_the_board_does_not_answer(
    hass, aioclient_mock
):
    aioclient_mock.get(DISCOVERY_URL, json=LISTED)
    aioclient_mock.get(BASE + "/api/state", status=503)
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"board_id": "board-1"}
    )
    assert result["step_id"] == "local"
    assert result["errors"] == {"base": "cannot_connect_local"}
    defaults = {str(key): key.default() for key in result["data_schema"].schema}
    assert defaults == {"host": "192.0.2.10", "port": 3180}


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Autodarts (192.0.2.10)", "Autodarts (192.0.2.20)"),
        ("Autodarts (Living room)", "Autodarts (Living room)"),
    ],
)
async def test_known_board_entered_at_a_new_address_moves_there(
    hass, aioclient_mock, title, expected
):
    """The user says where the board is now; the entry follows."""
    mock_board_v2(aioclient_mock, base=OTHER)
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        unique_id="board-1",
        title=title,
        data=local_entry_data(),
    )
    entry.add_to_hass(hass)
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "local"}
    )
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.20", "port": 3180}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "address_updated"
    assert entry.data["host"] == "192.0.2.20"
    assert entry.title == expected
    reload.assert_called_once_with(entry.entry_id)


async def test_reconfigure_to_a_new_address_renames_an_address_title(
    hass, aioclient_mock
):
    mock_board_v2(aioclient_mock, base=OTHER)
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        unique_id="board-1",
        title="Autodarts (192.0.2.10)",
        data=local_entry_data(),
    )
    entry.add_to_hass(hass)
    result = await start(hass, SOURCE_RECONFIGURE, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "local"}
    )
    with patch.object(hass.config_entries, "async_schedule_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "192.0.2.20", "port": 3180}
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Autodarts (192.0.2.20)"
