"""The new games in Home Assistant: options, the start_game action and restarts."""

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homedarts.const import DOMAIN

from .local_helpers import (
    NOW,
    S20,
    T20,
    board,
    entity_id,
    local_entry_data,
    mock_board,
    record,
    setup_local,
    state,
    switch,
)
from .test_practice_setup import select_game, set_number, throw

# A single 1 inside the treble ring, and one outside.
INNER_S1 = {
    "segment": {"name": "S1", "number": 1, "multiplier": 1},
    "coords": {"x": 0.02, "y": 0.3},
}
OUTER_S1 = {
    "segment": {"name": "S1", "number": 1, "multiplier": 1},
    "coords": {"x": 0.03, "y": 0.8},
}


async def test_the_new_options_are_configuration_entities(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    registry = er.async_get(hass)
    for platform, key, value in (
        ("switch", "practice_teams", "off"),
        ("number", "practice_start_1", "0"),
        ("number", "practice_start_4", "0"),
        ("number", "practice_count_up_rounds", "8"),
        ("select", "practice_golf_holes", "9"),
    ):
        assert state(hass, platform, key) == value
        entity = registry.async_get(entity_id(hass, platform, key))
        assert entity.entity_category == er.EntityCategory.CONFIG
    await set_number(hass, "practice_start_2", 301)
    assert practice.starts == [0, 301, 0, 0]
    assert state(hass, "number", "practice_start_2") == "301"
    with pytest.raises(ServiceValidationError) as error:
        await set_number(hass, "practice_start_2", 1)
    assert error.value.translation_key == "invalid_start_score"
    assert practice.starts == [0, 301, 0, 0]
    await select_game(hass, "count_up")
    await set_number(hass, "practice_count_up_rounds", 5)
    assert practice.party.rounds == 5
    assert state(hass, "number", "practice_count_up_rounds") == "5"
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": entity_id(hass, "select", "practice_golf_holes"),
            "option": "18",
        },
        blocking=True,
    )
    assert practice.golf_holes == 18 and practice.party.kind == "count_up"
    await select_game(hass, "golf")
    assert state(hass, "select", "practice_game") == "golf"
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.attributes["rounds"] == 18
    assert state(hass, "sensor", "practice_target") == "1"
    # Teams start a new match of four players.
    await set_number(hass, "practice_players", 4)
    await select_game(hass, "501")
    await switch(hass, "practice_teams", True)
    assert practice.teams is True
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert [team["players"] for team in remaining.attributes["teams"]] == [
        [1, 3],
        [2, 4],
    ]
    assert [score["remaining"] for score in remaining.attributes["scores"]] == [
        501,
        301,
        501,
        301,
    ]


async def test_golf_counts_inner_and_outer_singles_by_the_dart_position(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await set_number(hass, "practice_players", 2)
    await select_game(hass, "golf")
    for dart in (INNER_S1, OUTER_S1):
        coordinator.async_receive(
            "state", {**board(), "numThrows": 1, "throws": [dart]}
        )
        coordinator.async_receive("state", board())
        await hass.async_block_till_done()
    scores = coordinator.games.practice.snapshot()["scores"]
    assert [score["scorecard"] for score in scores] == [[3], [4]]


async def test_start_game_sets_up_teams_handicaps_and_rounds(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    practice = coordinator.games.practice
    events = record(hass, coordinator)
    await hass.services.async_call(
        DOMAIN,
        "start_game",
        {
            "game": "301",
            "players": ["Alex", "Sam", "Kim", "Lea"],
            "teams": True,
            "start_scores": [0, "201"],
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert practice.teams and practice.starts == [0, 201, 0, 0]
    assert [player.remaining for player in practice.players] == [301, 201, 301, 201]
    await throw(hass, coordinator, T20)
    turn = [attributes for kind, attributes in events if kind == "turn_changed"][-1]
    assert turn["team"] == 2 and turn["team_name"] == "Sam & Lea"
    # Start scores left out play the game's again; holes and rounds are options.
    await hass.services.async_call(
        DOMAIN,
        "start_game",
        {"game": "golf", "players": ["Alex"], "teams": False, "start_scores": []},
        blocking=True,
    )
    assert practice.starts == [0, 0, 0, 0] and not practice.teams
    await hass.services.async_call(
        DOMAIN, "start_game", {"game": "golf", "holes": "18"}, blocking=True
    )
    assert practice.party.rounds == 18
    await hass.services.async_call(
        DOMAIN, "start_game", {"game": "count_up", "rounds": 3}, blocking=True
    )
    assert practice.party.rounds == 3 and practice.golf_holes == 18
    await hass.services.async_call(
        DOMAIN, "start_game", {"game": "tactics"}, blocking=True
    )
    assert state(hass, "select", "practice_game") == "tactics"
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert len(remaining.attributes["numbers"]) == 12
    await hass.services.async_call(
        DOMAIN, "start_game", {"game": "jdc_challenge"}, blocking=True
    )
    assert state(hass, "sensor", "practice_target") == "10"
    await throw(hass, coordinator, S20)


async def test_start_game_with_a_fair_start_scales_from_the_averages(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    practice = coordinator.games.practice
    for name, points in (("Alex", 600), ("Sam", 300)):
        practice.profiles.leg(501, [{"name": name, "points": points, "darts": 30}], NOW)
    await hass.services.async_call(
        DOMAIN,
        "start_game",
        {"game": "501", "players": ["Alex", "Sam"], "fair_start": True},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert practice.starts == [0, 250, 0, 0]
    assert [player.remaining for player in practice.players] == [501, 250]
    # Off, the scores set stay until the action sets others.
    await hass.services.async_call(
        DOMAIN,
        "start_game",
        {"game": "501", "players": ["Alex", "Sam"], "fair_start": False},
        blocking=True,
    )
    assert practice.starts == [0, 250, 0, 0]


async def test_start_game_checks_teams_and_start_scores(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock, state=board())
    for data, key in (
        ({"game": "501", "teams": True}, "team_players"),
        ({"game": "501", "teams": True, "players": ["A", "B", "C"]}, "team_players"),
        ({"game": "golf", "teams": True, "players": ["A", "B", "C", "D"]}, "team_game"),
        ({"game": "501", "start_scores": [1]}, "invalid_start_score"),
        (
            {"game": "501", "start_scores": [501, 501, 501, 501, 501]},
            "too_many_start_scores",
        ),
    ):
        with pytest.raises(ServiceValidationError) as error:
            await hass.services.async_call(DOMAIN, "start_game", data, blocking=True)
        assert error.value.translation_key == key
    for data in (
        {"game": "501", "start_scores": ["many"]},
        {"game": "501", "start_scores": [301], "fair_start": True},
        {"game": "501", "holes": 12},
        {"game": "501", "rounds": 21},
    ):
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(DOMAIN, "start_game", data, blocking=True)


async def test_new_games_and_options_survive_a_restart(
    hass, aioclient_mock, hass_storage
):
    hass_storage["homedarts.games-entry.training"] = {
        "version": 1,
        "key": "homedarts.games-entry.training",
        "data": {
            "practice": {
                "game": "cut_throat",
                "teams": True,
                "starts": [0, 301, 0, 0],
                "golf_holes": 18,
                "count_up_rounds": 12,
                "players": [{"points": 40}, {"points": 20}],
            }
        },
    }
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(
        domain="homedarts", version=2, data=local_entry_data(), entry_id="games-entry"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, "select", "practice_game") == "cut_throat"
    assert state(hass, "switch", "practice_teams") == "on"
    assert state(hass, "number", "practice_start_2") == "301"
    assert state(hass, "select", "practice_golf_holes") == "18"
    assert state(hass, "number", "practice_count_up_rounds") == "12"
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert [score["points"] for score in remaining.attributes["scores"]] == [40, 20]
    assert remaining.attributes["teams"] is None


async def test_a_start_of_3_and_both_double_rules_exclude_each_other(
    hass, aioclient_mock
):
    """The start score numbers and the double switches never make a leg that no
    dart can win: from 3, the only opening double, D1, leaves 1."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    await switch(hass, "practice_double_in", True)
    await switch(hass, "practice_double_out", True)
    with pytest.raises(ServiceValidationError) as error:
        await set_number(hass, "practice_start_1", 3)
    assert error.value.translation_key == "unwinnable_start"
    assert practice.starts[0] == 0
    # A seat nobody plays may keep any start score.
    await set_number(hass, "practice_start_4", 3)

    await switch(hass, "practice_double_in", False)
    await set_number(hass, "practice_start_1", 3)
    with pytest.raises(ServiceValidationError) as error:
        await switch(hass, "practice_double_in", True)
    assert error.value.translation_key == "unwinnable_start"
    assert practice.double_in is False
    await switch(hass, "practice_double_out", False)
    await switch(hass, "practice_double_in", True)
    with pytest.raises(ServiceValidationError):
        await switch(hass, "practice_double_out", True)
    assert (practice.double_in, practice.setting("double_out")) == (True, False)
