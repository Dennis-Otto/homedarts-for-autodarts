"""Player profiles and the last match in Home Assistant."""

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.homedarts.const import DOMAIN

from .local_helpers import board, entity_id, record, setup_local, state, switch
from .test_practice_setup import select_game, set_number, throw

D20 = ("D20", 20, 2)


async def test_profiles_the_last_match_and_deleting_a_player(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    assert state(hass, "sensor", "player_profiles") == "0"
    assert state(hass, "sensor", "last_match") == "unknown"
    for index, name in enumerate(("Alex", "Lea")):
        coordinator.games.practice.set_name(index, name)
    await select_game(hass, "501")
    await set_number(hass, "practice_players", 2)
    coordinator.games.practice.players[0].remaining = 40
    await throw(hass, coordinator, D20)

    profiles = hass.states.get(entity_id(hass, "sensor", "player_profiles"))
    assert profiles.state == "2"
    alex = next(
        item for item in profiles.attributes["players"] if item["name"] == "Alex"
    )
    assert (alex["legs_won"], alex["matches_won"], alex["highest_checkout"]) == (
        1,
        1,
        40,
    )
    last = hass.states.get(entity_id(hass, "sensor", "last_match"))
    assert last.state != "unknown" and last.attributes["winner"] == "Alex"
    assert last.attributes["game"] == 501
    assert last.attributes["head_to_head"] == [
        {"players": ["Alex", "Lea"], "wins": [1, 0]}
    ]

    # The checkout was a dart at D20, for the doubles analysis.
    doubles = hass.states.get(entity_id(hass, "sensor", "favourite_double"))
    assert doubles.state == "unknown"
    assert (doubles.attributes["attempts"], doubles.attributes["hits"]) == (1, 1)
    assert doubles.attributes["doubles"] == [
        {"double": "D20", "attempts": 1, "hits": 1, "rate": 100.0}
    ]
    # Every double hit, whatever the dart was aimed at.
    assert doubles.attributes["landed"] == {"D20": 1}
    await switch(hass, "practice_personal_routes", True)
    assert coordinator.games.practice.personal_routes is True
    assert coordinator.games.practice.winner == 0

    await hass.services.async_call(
        DOMAIN, "delete_player", {"name": "lea"}, blocking=True
    )
    await hass.async_block_till_done()
    assert state(hass, "sensor", "player_profiles") == "1"
    # The name leaves the player slots, so the next leg creates no profile again.
    assert coordinator.games.practice.names[:2] == ["Alex", ""]
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN, "delete_player", {"name": "Nobody"}, blocking=True
        )
    assert error.value.translation_key == "unknown_player"

    # The board's personal bests keep their values, without the name.
    assert coordinator.games.records.bests["highest_checkout"]["name"] == "Alex"
    await hass.services.async_call(
        DOMAIN, "delete_player", {"name": "ALEX"}, blocking=True
    )
    await hass.async_block_till_done()
    assert state(hass, "sensor", "player_profiles") == "0"
    assert coordinator.games.practice.names[:2] == ["", ""]
    best = coordinator.games.records.bests["highest_checkout"]
    assert best["name"] is None and best["value"] == 40
    # The match history keeps the names.
    last = hass.states.get(entity_id(hass, "sensor", "last_match"))
    assert last.attributes["winner"] == "Alex"


async def test_renaming_and_merging_players(hass, aioclient_mock):
    """The action renames a player everywhere, merges two names of one player,
    announces it and explains what it cannot do."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    for index, name in enumerate(("Sammy", "Lea")):
        coordinator.games.practice.set_name(index, name)
    await select_game(hass, "501")
    await set_number(hass, "practice_players", 2)
    coordinator.games.practice.players[0].remaining = 40
    await throw(hass, coordinator, D20)
    events = record(hass, coordinator)

    async def rename(player: str, new_name: str) -> None:
        await hass.services.async_call(
            DOMAIN,
            "rename_player",
            {"player": player, "new_name": new_name},
            blocking=True,
        )
        await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as error:
        await rename("Sammy", "LEA")
    assert error.value.translation_key == "merge_in_play"
    assert error.value.translation_placeholders == {"name": "Sammy", "other": "Lea"}
    with pytest.raises(ServiceValidationError) as error:
        await rename("Nobody", "Sam")
    assert error.value.translation_key == "unknown_player"
    with pytest.raises(ServiceValidationError) as error:
        await rename("Sammy", "Sam #1")
    assert error.value.translation_key == "invalid_player_name"
    # The same name again is no change and no event.
    await rename("sammy", "Sammy")
    assert events == []

    await rename(" sammy", "Sam")
    assert events == [
        (
            "player_renamed",
            {"old": "Sammy", "new": "Sam", "merged": False, "source": "training"},
        )
    ]
    profiles = hass.states.get(entity_id(hass, "sensor", "player_profiles"))
    assert {player["name"] for player in profiles.attributes["players"]} == {
        "Sam",
        "Lea",
    }
    last = hass.states.get(entity_id(hass, "sensor", "last_match"))
    assert last.attributes["head_to_head"] == [
        {"players": ["Lea", "Sam"], "wins": [0, 1]}
    ]
    assert coordinator.games.records.bests["highest_checkout"]["name"] == "Sam"
    assert coordinator.games.practice.names[:2] == ["Sam", "Lea"]
    assert [
        player["name"] for player in coordinator.reports.journal.matches[-1]["players"]
    ] == ["Sam", "Lea"]

    # Once Lea rests, Sam and Lea become one player; the event says so.
    await set_number(hass, "practice_players", 1)
    events.clear()
    await rename("Lea", "Sam")
    assert events[0][1]["merged"] is True
    profiles = hass.states.get(entity_id(hass, "sensor", "player_profiles"))
    (sam,) = profiles.attributes["players"]
    assert (sam["name"], sam["legs_played"], sam["matches_played"]) == ("Sam", 2, 2)
    last = hass.states.get(entity_id(hass, "sensor", "last_match"))
    assert last.attributes["head_to_head"] == []
    event = hass.states.get(entity_id(hass, "event", "board_events"))
    assert "player_renamed" in event.attributes["event_types"]
