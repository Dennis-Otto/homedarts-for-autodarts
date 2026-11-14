"""Diagnostics as Home Assistant serves them: complete, and without names or secrets."""

import json

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from custom_components.homedarts.const import DOMAIN

from .local_helpers import (
    BULL,
    OUTER_BULL,
    T20,
    board,
    setup_local,
    setup_v2,
)

# Durations and times of the connection history differ from run to run.
VOLATILE = props("last_success", "last_poll_seconds", "offline_seconds", "started")
PLAYERS = ("Alexandra", "Samuel")
S1 = ("S1", 1, 1)
D20 = ("D20", 20, 2)


@pytest.fixture(autouse=True)
async def diagnostics_component(hass: HomeAssistant) -> None:
    """The endpoint that downloads diagnostics, as in the user interface."""
    assert await async_setup_component(hass, "diagnostics", {})


async def throw(hass, coordinator, *darts) -> None:
    """Throw a visit dart by dart, then pull the darts."""
    for count in range(1, len(darts) + 1):
        coordinator.async_receive("state", board(*darts[:count]))
    coordinator.async_receive("state", board())
    await hass.async_block_till_done()


async def test_diagnostics_of_a_named_match_with_a_bull_off(
    hass, aioclient_mock, hass_client, snapshot: SnapshotAssertion
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await hass.services.async_call(
        DOMAIN,
        "start_game",
        {"game": "501", "players": list(PLAYERS), "bull_off": True},
        blocking=True,
    )
    # The first player has thrown at the bull; the second one is still to throw.
    await throw(hass, coordinator, OUTER_BULL)
    during = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert during["practice_game"]["bull_off_running"] is True
    bull_off = during["local"]["practice"]["bull_off"]
    assert [item["name"] for item in bull_off["throws"]] == ["**REDACTED**"] * 2

    await throw(hass, coordinator, BULL)
    await throw(hass, coordinator, T20, T20, T20)
    after = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    for name in PLAYERS:
        assert name not in json.dumps([during, after])
    assert after == snapshot(exclude=VOLATILE)


async def test_diagnostics_of_a_team_match_leave_out_the_team_names(
    hass, aioclient_mock, hass_client
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    names = [*PLAYERS, "Katharina", "Leonhard"]
    await hass.services.async_call(
        DOMAIN,
        "start_game",
        {"game": "101", "players": names, "teams": True, "legs": 2},
        blocking=True,
    )
    # 101: both teams score 60, then the partner of the first player checks out.
    await throw(hass, coordinator, T20)
    await throw(hass, coordinator, T20)
    await throw(hass, coordinator, S1, D20)
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    (leg,) = diagnostics["local"]["practice"]["legs"]
    assert leg["team"] == 1 and leg["team_name"] == "**REDACTED**"
    assert diagnostics["practice_game"]["teams"] is True
    for name in names:
        assert name not in json.dumps(diagnostics)


async def test_diagnostics_of_board_manager_2(
    hass, aioclient_mock, hass_client, snapshot: SnapshotAssertion
):
    entry = await setup_v2(hass, aioclient_mock)
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diagnostics == snapshot(exclude=VOLATILE)
    text = json.dumps(diagnostics)
    for secret in ("private-board-api-key", "private-tls-key", "dartboard-pc"):
        assert secret not in text
