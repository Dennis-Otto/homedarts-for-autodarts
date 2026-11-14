"""Tournaments in Home Assistant: actions, entities, the pause, events and restarts."""

import json
from datetime import timedelta

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.homedarts.const import DOMAIN

from .local_helpers import (
    S20,
    T20,
    board,
    entity_id,
    record,
    setup_local,
    state,
    switch,
)

D20 = ("D20", 20, 2)
S1 = ("S1", 1, 1)
CHECKOUT = (T20, S1, D20)
PLAYERS = ["Alex", "Sam", "Kim"]


async def throw(hass, coordinator, *darts, pull: bool = True) -> None:
    """Throw a visit dart by dart, then pull the darts."""
    for count in range(1, len(darts) + 1):
        coordinator.async_receive("state", board(*darts[:count]))
    if pull:
        coordinator.async_receive("state", board())
    await hass.async_block_till_done()


async def action(hass, service: str, **data) -> None:
    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await hass.async_block_till_done()


async def press(hass, key: str) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id(hass, "button", key)}, blocking=True
    )
    await hass.async_block_till_done()


def tournament(hass):
    return hass.states.get(entity_id(hass, "sensor", "tournament"))


def fired(events, kind: str) -> list[dict]:
    return [attributes for event, attributes in events if event == kind]


async def pass_pause(hass, seconds: float = 11) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_a_round_robin_plays_through_with_pauses(hass, aioclient_mock, freezer):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    assert state(hass, "sensor", "tournament") == "no_tournament"
    assert tournament(hass).attributes["status"] is None

    await action(hass, "start_tournament", players=PLAYERS, game="101", legs=1, sets=1)
    started = fired(events, "tournament_started")
    assert started == [
        {
            "format": "round_robin",
            "game": 101,
            "matches": 3,
            "players": PLAYERS,
            "start_scores": [0, 0, 0],
            "legs_to_win": 1,
            "sets_to_win": 1,
            "seed": None,
            "source": "training",
        }
    ]
    assert state(hass, "sensor", "tournament") == "round_1"
    assert state(hass, "select", "practice_game") == "101"
    assert state(hass, "text", "practice_player_1") == "Kim"
    assert state(hass, "text", "practice_player_2") == "Sam"
    # The action keeps the players for the next tournament.
    assert state(hass, "text", "tournament_players") == "Alex, Sam, Kim"
    current = tournament(hass).attributes["current"]
    assert current["players"] == ["Kim", "Sam"] and current["match"] == 1

    await throw(hass, coordinator, S1, S1, S1)
    await throw(hass, coordinator, *CHECKOUT)
    finished = fired(events, "tournament_match_finished")
    assert len(finished) == 1
    assert finished[0]["winner"] == "Sam" and finished[0]["next"] == ["Alex", "Kim"]
    assert finished[0]["source"] == "websocket"
    attributes = tournament(hass).attributes
    assert attributes["status"] == "waiting" and attributes["next_at"]
    assert state(hass, "sensor", "tournament") == "round_2"

    # Darts during the pause start no new match.
    await throw(hass, coordinator, T20)
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.attributes["winner"] == 2
    # The pause ends while darts are on the board: the takeout starts the match.
    await throw(hass, coordinator, T20, pull=False)
    freezer.tick(timedelta(seconds=19))
    await pass_pause(hass, 0)
    assert tournament(hass).attributes["status"] == "waiting"
    coordinator.async_receive("state", board())
    await hass.async_block_till_done()
    assert tournament(hass).attributes["status"] == "playing"
    assert state(hass, "text", "practice_player_1") == "Alex"

    await throw(hass, coordinator, *CHECKOUT)
    # The pause ends with an empty board: the next match starts at once.
    freezer.tick(timedelta(seconds=19))
    await pass_pause(hass, 0)
    assert tournament(hass).attributes["current"]["players"] == ["Sam", "Alex"]
    await throw(hass, coordinator, S1, S1, S1)
    await throw(hass, coordinator, *CHECKOUT)
    assert fired(events, "tournament_finished") == [
        {
            "format": "round_robin",
            "game": 101,
            "matches": 3,
            "winner": "Alex",
            "runner_up": "Sam",
            "third": "Kim",
            "players": PLAYERS,
            "source": "websocket",
        }
    ]
    assert state(hass, "sensor", "tournament") == "finished"
    attributes = tournament(hass).attributes
    assert attributes["winner"] == "Alex"
    assert [row["name"] for row in attributes["standings"]] == ["Alex", "Sam", "Kim"]
    # Tournament matches go into the profiles and the head-to-head records.
    last = hass.states.get(entity_id(hass, "sensor", "last_match"))
    assert last.attributes["winner"] == "Alex"
    assert len(last.attributes["matches"]) == 3

    await press(hass, "tournament_stop")
    assert state(hass, "sensor", "tournament") == "no_tournament"


async def test_the_pause_waits_for_the_button_and_changes_at_once(
    hass, aioclient_mock, freezer
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id(hass, "number", "tournament_pause"), "value": 0},
        blocking=True,
    )
    await action(hass, "start_tournament", players=PLAYERS, game="101", legs=1)
    with pytest.raises(ServiceValidationError) as error:
        await press(hass, "tournament_next_match")
    assert error.value.translation_key == "tournament_match_running"
    await throw(hass, coordinator, *CHECKOUT)
    assert tournament(hass).attributes["next_at"] is None
    await pass_pause(hass, 3600)
    assert tournament(hass).attributes["status"] == "waiting"
    # A pause set now counts from the end of the match and its summary.
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id(hass, "number", "tournament_pause"), "value": 30},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert tournament(hass).attributes["pause"] == 30
    assert tournament(hass).attributes["status"] == "waiting"
    freezer.tick(timedelta(seconds=39))
    await pass_pause(hass, 0)
    assert tournament(hass).attributes["status"] == "playing"
    # The button starts the next match at once.
    await throw(hass, coordinator, *CHECKOUT)
    await press(hass, "tournament_next_match")
    assert tournament(hass).attributes["current"]["match"] == 3


async def test_a_timer_that_fires_early_waits_again(hass, aioclient_mock, freezer):
    # A frozen clock: however long the test takes, the pause is not over.
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await action(hass, "start_tournament", players=PLAYERS, game="101", legs=1)
    await throw(hass, coordinator, *CHECKOUT)
    # The timer fires before the pause is over.
    coordinator._fixture_unsub()
    await coordinator._async_fixture_due(dt_util.utcnow())
    assert coordinator._fixture_unsub is not None
    assert tournament(hass).attributes["status"] == "waiting"
    await action(hass, "stop_tournament")
    assert coordinator._fixture_unsub is None


async def test_the_entities_set_the_next_tournament_up(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    registry = er.async_get(hass)
    for platform, key in (
        ("select", "tournament_format"),
        ("select", "tournament_game"),
        ("text", "tournament_players"),
        ("number", "tournament_pause"),
        ("number", "tournament_summary"),
        ("switch", "tournament_third_place"),
        ("switch", "tournament_random_draw"),
    ):
        entry_ = registry.async_get(entity_id(hass, platform, key))
        assert entry_.entity_category == er.EntityCategory.CONFIG, key
    assert state(hass, "select", "tournament_format") == "round_robin"
    assert state(hass, "select", "tournament_game") == "501"
    assert state(hass, "number", "tournament_pause") == "10"
    assert state(hass, "number", "tournament_summary") == "8"
    assert state(hass, "switch", "tournament_third_place") == "off"
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id(hass, "number", "tournament_summary"), "value": 12},
        blocking=True,
    )
    assert state(hass, "number", "tournament_summary") == "12"
    for key, option in (
        ("tournament_format", "knockout"),
        ("tournament_game", "cricket"),
    ):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id(hass, "select", key), "option": option},
            blocking=True,
        )
    await hass.services.async_call(
        "text",
        "set_value",
        {
            "entity_id": entity_id(hass, "text", "tournament_players"),
            "value": "Alex; Sam, Kim,Lea",
        },
        blocking=True,
    )
    await switch(hass, "tournament_third_place", True)
    await switch(hass, "tournament_random_draw", True)
    await switch(hass, "tournament_random_draw", False)
    assert state(hass, "text", "tournament_players") == "Alex, Sam, Kim, Lea"
    assert state(hass, "switch", "tournament_third_place") == "on"

    events = record(hass, coordinator)
    await press(hass, "tournament_start")
    assert fired(events, "tournament_started")[0]["format"] == "knockout"
    assert state(hass, "sensor", "tournament") == "semi_final"
    attributes = tournament(hass).attributes
    assert attributes["game"] == "cricket" and attributes["third_place"] is True
    assert [item["stage"] for item in attributes["bracket"]] == [
        "semi_final",
        "final",
        "third_place",
    ]
    assert state(hass, "select", "practice_game") == "cricket"
    await press(hass, "tournament_stop")
    with pytest.raises(ServiceValidationError) as error:
        await press(hass, "tournament_stop")
    assert error.value.translation_key == "no_tournament"


async def number(hass, key: str, value: float) -> None:
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id(hass, "number", key), "value": value},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_the_button_starts_the_groups_and_qualifiers_of_the_entities(
    hass, aioclient_mock
):
    await setup_local(hass, aioclient_mock, state=board())
    registry = er.async_get(hass)
    for key in ("tournament_groups", "tournament_advance"):
        entry_ = registry.async_get(entity_id(hass, "number", key))
        assert entry_.entity_category == er.EntityCategory.CONFIG, key
    # Groups of about four players, of which two go on.
    assert state(hass, "number", "tournament_groups") == "0"
    assert state(hass, "number", "tournament_advance") == "2"
    # There is no single group: 1 steps on in the direction of the change.
    await number(hass, "tournament_groups", 1)
    assert state(hass, "number", "tournament_groups") == "2"
    await number(hass, "tournament_groups", 1)
    assert state(hass, "number", "tournament_groups") == "0"
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": entity_id(hass, "select", "tournament_format"),
            "option": "groups_knockout",
        },
        blocking=True,
    )
    await text(hass, "tournament_players", ", ".join(f"P{n}" for n in range(12)))
    await number(hass, "tournament_groups", 5)
    with pytest.raises(ServiceValidationError) as error:
        await press(hass, "tournament_start")
    assert error.value.translation_key == "tournament_groups"
    assert error.value.translation_placeholders == {
        "count": "12",
        "groups": "5",
        "advance": "2",
    }
    await number(hass, "tournament_groups", 3)
    await number(hass, "tournament_advance", 1)
    await press(hass, "tournament_start")
    attributes = tournament(hass).attributes
    assert [group["group"] for group in attributes["groups"]] == ["A", "B", "C"]
    assert attributes["advance"] == 1
    # The action takes them unless it chooses its own, which it keeps.
    await press(hass, "tournament_stop")
    await action(hass, "start_tournament", groups=0, advance=3)
    attributes = tournament(hass).attributes
    assert [group["group"] for group in attributes["groups"]] == ["A", "B", "C"]
    assert attributes["advance"] == 3
    assert state(hass, "number", "tournament_groups") == "0"
    assert state(hass, "number", "tournament_advance") == "3"
    await press(hass, "tournament_stop")
    await number(hass, "tournament_groups", 2)
    await action(hass, "start_tournament", advance=1)
    assert len(tournament(hass).attributes["groups"]) == 2
    await press(hass, "tournament_stop")
    with pytest.raises(vol.Invalid):
        await action(hass, "start_tournament", groups=1)


async def test_the_action_checks_its_players(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock, state=board())
    with pytest.raises(ServiceValidationError) as error:
        await action(hass, "start_tournament")
    assert error.value.translation_key == "tournament_players"
    with pytest.raises(ServiceValidationError) as error:
        await action(hass, "start_tournament", players=["Alex", "Sam", "ALEX"])
    assert error.value.translation_key == "duplicate_player"
    with pytest.raises(ServiceValidationError) as error:
        await action(hass, "next_tournament_match")
    assert error.value.translation_key == "no_tournament"
    assert state(hass, "sensor", "tournament") == "no_tournament"


async def test_the_action_sets_rules_draw_and_pause(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await action(
        hass,
        "start_tournament",
        players=["Alex", "Sam", "Kim", "Lea", "Max"],
        format="knockout",
        game="301",
        legs=2,
        sets=2,
        double_out=False,
        double_in=True,
        bull_off=True,
        bull_off_distance=True,
        third_place=True,
        seed=11,
        pause=0,
        summary=3,
    )
    attributes = tournament(hass).attributes
    assert attributes["seed"] == 11 and attributes["pause"] == 0
    assert attributes["summary"] == 3
    assert sorted(attributes["players"]) == ["Alex", "Kim", "Lea", "Max", "Sam"]
    assert (attributes["legs_to_win"], attributes["sets_to_win"]) == (2, 2)
    practice = coordinator.games.practice
    assert practice.game == 301 and practice.double_in and not practice.double_out
    assert practice.bull_off and practice.bulling is not None
    assert state(hass, "switch", "tournament_third_place") == "on"
    assert state(hass, "number", "tournament_pause") == "0"


async def test_a_tournament_survives_a_restart(
    hass, aioclient_mock, hass_storage, freezer
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await action(hass, "start_tournament", players=PLAYERS, game="101", legs=1)
    await throw(hass, coordinator, *CHECKOUT)
    assert coordinator.games.practice.hold
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass_storage[f"homedarts.{entry.entry_id}.training"]["data"]["tournament"]
    coordinator = entry.runtime_data.local
    assert coordinator.games.practice.hold
    assert state(hass, "sensor", "tournament") == "round_2"
    assert tournament(hass).attributes["status"] == "waiting"
    # The pause ended while Home Assistant was stopped: the match starts now.
    freezer.tick(timedelta(seconds=60))
    await pass_pause(hass, 0)
    assert tournament(hass).attributes["status"] == "playing"
    await throw(hass, coordinator, S20)
    assert coordinator.games.practice.players[0].remaining == 81


async def test_diagnostics_count_the_tournament_without_names(
    hass, aioclient_mock, hass_client
):
    assert await async_setup_component(hass, "diagnostics", {})
    entry = await setup_local(hass, aioclient_mock, state=board())
    await action(hass, "start_tournament", players=PLAYERS, game="101", legs=1)
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diagnostics["tournament"] == {
        "format": "round_robin",
        "game": "101",
        "players": 3,
        "third_place": False,
        "random_draw": False,
        "groups": 0,
        "advance": 2,
        "pause": 10,
        "summary": 8,
        "running": {
            "format": "round_robin",
            "game": "101",
            "status": "playing",
            "players": 3,
            "matches_played": 0,
            "matches_total": 3,
        },
    }
    text = json.dumps(diagnostics)
    for name in PLAYERS:
        assert name not in text


async def test_another_game_in_the_pause_is_played_to_its_end(
    hass, aioclient_mock, freezer
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await action(hass, "start_tournament", players=PLAYERS, game="101", legs=1)
    await throw(hass, coordinator, *CHECKOUT)
    # Somebody plays a game of their own during the pause.
    await action(hass, "start_game", game="301", players=["Tom"])
    freezer.tick(timedelta(seconds=19))
    await pass_pause(hass, 0)
    assert tournament(hass).attributes["status"] == "waiting"
    assert coordinator.games.practice.kind == 301
    await throw(hass, coordinator, T20)
    assert tournament(hass).attributes["status"] == "waiting"
    # A training game makes no way by itself either; ending the game does.
    await action(hass, "start_game", game="doubles")
    freezer.tick(timedelta(seconds=1))
    await pass_pause(hass, 0)
    assert tournament(hass).attributes["status"] == "waiting"
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id(hass, "select", "practice_game"), "option": "off"},
        blocking=True,
    )
    freezer.tick(timedelta(seconds=5))
    await pass_pause(hass, 0)
    assert tournament(hass).attributes["status"] == "playing"
    assert coordinator._fixture_unsub is None
    assert state(hass, "text", "practice_player_1") == "Alex"


async def test_the_action_takes_start_scores_for_a_handicap(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await action(
        hass,
        "start_tournament",
        players=PLAYERS,
        game="501",
        start_scores=[501, 301, 0],
        legs=1,
    )
    assert tournament(hass).attributes["start_scores"] == [501, 301, 0]
    # Kim against Sam: Sam starts from 301.
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert [score["remaining"] for score in remaining.attributes["scores"]] == [
        501,
        301,
    ]
    assert entry.runtime_data.local.games.practice.starts == [0, 301, 0, 0]
    with pytest.raises(ServiceValidationError) as error:
        await action(hass, "start_tournament", players=PLAYERS, start_scores=[1])
    assert error.value.translation_key == "invalid_start_score"


async def text(hass, key: str, value: str) -> None:
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": entity_id(hass, "text", key), "value": value},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_names_and_the_list_of_players_are_checked(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    many = ", ".join(f"P{number}" for number in range(33))
    for key, value, error_key in (
        ("tournament_players", many, "tournament_players"),
        ("tournament_players", "Alex, {{ 6*7 }}, Kim", "invalid_player_name"),
        ("practice_player_1", "50%", "invalid_player_name"),
    ):
        with pytest.raises(ServiceValidationError) as error:
            await text(hass, key, value)
        assert error.value.translation_key == error_key
    assert error.value.translation_placeholders is None
    assert coordinator.games.tournament.setup.players == []
    assert coordinator.games.practice.names[0] == ""
    # Eight names of 20 characters fit into the state.
    await text(hass, "tournament_players", ",".join(f"{'X' * 19}{n}" for n in range(8)))
    assert len(state(hass, "text", "tournament_players")) <= 255
    with pytest.raises(ServiceValidationError) as error:
        await action(hass, "start_game", game="501", players=["Alex", "{% if %}"])
    assert error.value.translation_key == "invalid_player_name"
    with pytest.raises(ServiceValidationError) as error:
        await action(hass, "start_tournament", players=["Alex", "Sam", "#Kim"])
    assert error.value.translation_key == "invalid_player_name"
    assert state(hass, "sensor", "tournament") == "no_tournament"


async def test_a_long_list_of_players_shows_what_fits_and_keeps_the_rest(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    setup = coordinator.games.tournament.setup
    # A start of 32 players sets them up for the next tournament too.
    names = [f"Player Number {number:02d}xxxx" for number in range(32)]
    await coordinator.async_set_tournament(players=names)
    await hass.async_block_till_done()
    shown = hass.states.get(entity_id(hass, "text", "tournament_players"))
    # Eleven names of 20 characters and the ellipsis fit into 255 characters.
    assert shown.state == ", ".join([*names[:11], "…"])
    assert shown.attributes["players"] == names == setup.players
    # Written back with a name changed, the ellipsis keeps the names it hid.
    await text(hass, "tournament_players", shown.state.replace(names[0], "Alex"))
    assert setup.players == ["Alex", *names[1:]]
    # Alex is shorter: twelve names fit now. The ellipsis keeps the others where
    # it stands, and only once.
    await text(hass, "tournament_players", "Zoe, …, Kim, …")
    assert setup.players == ["Zoe", *names[12:], "Kim"]
    # 33 players are one too many, with the hidden ones too: twelve and 21.
    await coordinator.async_set_tournament(players=names)
    visible = ", ".join(f"P{number}" for number in range(12))
    with pytest.raises(ServiceValidationError) as error:
        await text(hass, "tournament_players", f"{visible}, …")
    assert error.value.translation_placeholders == {
        "count": "33",
        "min": "3",
        "max": "32",
    }
    await text(hass, "tournament_players", "Alex, Sam")
    assert state(hass, "text", "tournament_players") == "Alex, Sam"


async def test_the_action_starts_groups_with_a_knockout(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock, state=board())
    players = [f"Player {number}" for number in range(12)]
    with pytest.raises(ServiceValidationError) as error:
        await action(
            hass,
            "start_tournament",
            players=players,
            format="groups_knockout",
            groups=5,
        )
    assert error.value.translation_key == "tournament_groups"
    await action(
        hass,
        "start_tournament",
        players=players,
        format="groups_knockout",
        groups=3,
        advance=1,
        game="101",
    )
    sensor = tournament(hass)
    assert sensor.state == "round_1"
    assert [group["group"] for group in sensor.attributes["groups"]] == ["A", "B", "C"]
    assert sensor.attributes["advance"] == 1
    assert sensor.attributes["current"]["group"] == "A"
    assert [round_["stage"] for round_ in sensor.attributes["bracket"]] == [
        "semi_final",
        "final",
    ]
    assert state(hass, "select", "tournament_format") == "groups_knockout"
    await action(hass, "stop_tournament")
    await action(hass, "start_tournament", format="double_knockout")
    sensor = tournament(hass)
    assert sensor.state == "winners_round_1"
    assert sensor.attributes["losers_bracket"][0]["stage"] == "losers_round_1"


async def test_a_tournament_is_stopped_before_the_next_one_starts(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock, state=board())
    await action(hass, "start_tournament", players=PLAYERS, game="101", legs=1)
    await text(hass, "tournament_players", "Tom, Ida, Ben")
    with pytest.raises(ServiceValidationError) as error:
        await press(hass, "tournament_start")
    assert error.value.translation_key == "tournament_running"
    with pytest.raises(ServiceValidationError) as error:
        await action(hass, "start_tournament", players=["Tom", "Ida", "Ben"])
    assert error.value.translation_key == "tournament_running"
    assert tournament(hass).attributes["players"] == PLAYERS
    await press(hass, "tournament_stop")
    await press(hass, "tournament_start")
    assert sorted(tournament(hass).attributes["players"]) == ["Ben", "Ida", "Tom"]


async def test_after_the_last_match_the_practice_settings_come_back(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await action(hass, "start_game", game="501", players=["Zoe"], bot_level=60)
    await action(hass, "start_tournament", players=PLAYERS, game="101", legs=1, pause=0)
    assert state(hass, "number", "practice_bot_level") == "0"
    for _ in range(3):
        await throw(hass, coordinator, *CHECKOUT)
        if tournament(hass).attributes["status"] == "waiting":
            await press(hass, "tournament_next_match")
    assert state(hass, "sensor", "tournament") == "finished"
    with pytest.raises(ServiceValidationError) as error:
        await press(hass, "tournament_next_match")
    assert error.value.translation_key == "tournament_finished"
    # The final's result stays until the next dart, which plays Zoe and the bot.
    assert state(hass, "text", "practice_player_1") != "Zoe"
    await throw(hass, coordinator, S20, pull=False)
    assert state(hass, "text", "practice_player_1") == "Zoe"
    assert state(hass, "number", "practice_bot_level") == "60"
    assert state(hass, "number", "practice_players") == "1"
    assert state(hass, "sensor", "practice_remaining") == "81"


async def test_a_player_of_the_tournament_is_deleted_after_it(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await action(hass, "start_tournament", players=PLAYERS, game="101", legs=1)
    # Kim throws first, and so has a profile.
    await throw(hass, coordinator, S20)
    assert "kim" in coordinator.games.practice.profiles.players
    with pytest.raises(ServiceValidationError) as error:
        await action(hass, "delete_player", name="kim")
    assert error.value.translation_key == "player_in_tournament"
    assert error.value.translation_placeholders == {"name": "kim"}
    assert "kim" in coordinator.games.practice.profiles.players
    await press(hass, "tournament_stop")
    await action(hass, "delete_player", name="kim")
    assert "kim" not in coordinator.games.practice.profiles.players
    assert state(hass, "text", "tournament_players") == "Alex, Sam"


async def test_a_game_after_a_stopped_tournament_has_the_players_from_before(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    await action(hass, "start_game", game="501", players=["Zoe"], bot_level=60)
    await action(hass, "start_tournament", players=PLAYERS, game="101", legs=1)
    await press(hass, "tournament_stop")
    await action(hass, "start_game", game="301")
    assert practice.humans == 1 and practice.bot_seat == 1
    assert practice.names[0] == "Zoe" and practice.kind == 301


async def test_the_actions_without_a_tournament_say_why(hass, aioclient_mock):
    """The tournament refuses in the words of the games; the actions show it
    as the message of Home Assistant."""
    await setup_local(hass, aioclient_mock, state=board())
    for service in ("stop_tournament", "next_tournament_match"):
        with pytest.raises(ServiceValidationError) as error:
            await action(hass, service)
        assert error.value.translation_key == "no_tournament"
