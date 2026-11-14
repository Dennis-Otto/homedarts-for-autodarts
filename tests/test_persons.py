"""Players linked to persons of Home Assistant, and who throws in the board events."""

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant.common import MockConfigEntry

from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.practice import PracticeGame
from custom_components.homedarts.profiles import Profile, Profiles

from .local_helpers import (
    BULL,
    S20,
    T20,
    board,
    entity_id,
    local_entry_data,
    mock_board,
    record,
    setup_local,
)
from .test_practice_setup import throw


def players(hass) -> dict[str, dict]:
    profiles = hass.states.get(entity_id(hass, "sensor", "player_profiles"))
    return {player["name"]: player for player in profiles.attributes["players"]}


def test_a_link_makes_a_profile_and_a_person_is_one_player():
    profiles = Profiles()
    assert profiles.link(" Dennis ", "person.dennis")
    dennis = profiles.players["dennis"]
    # Linking is no game: nothing counts yet and the player has not played.
    assert (dennis.name, dennis.person, dennis.legs_played, dennis.last_played) == (
        "Dennis",
        "person.dennis",
        0,
        None,
    )
    assert profiles.snapshot()["players"][0]["person"] == "person.dennis"
    # Linking the person to another player moves the link.
    assert profiles.link("Lea", "person.dennis")
    assert profiles.players["dennis"].person is None
    assert profiles.players["lea"].person == "person.dennis"
    # Linking the player again replaces their person.
    assert profiles.link("LEA", "person.lea")
    assert profiles.players["lea"].person == "person.lea"
    for name, person in (
        ("", "person.x"),
        ("  ", "person.x"),
        ("Tom", "sensor.x"),
        ("Tom", "person"),
        ("Tom", "person.Upper Case"),
    ):
        assert not profiles.link(name, person)
    assert "tom" not in profiles.players

    assert profiles.unlink("lea")
    assert profiles.players["lea"].person is None
    assert not profiles.unlink("Nobody")
    # Deleting a player deletes the link with the profile.
    profiles.link("Lea", "person.lea")
    assert profiles.delete("Lea")
    assert all(profile.person != "person.lea" for profile in profiles.players.values())


def test_links_are_stored_and_older_profiles_load_without():
    profiles = Profiles()
    profiles.link("Dennis", "person.dennis")
    profiles.link("Lea", "person.lea")
    restored = Profiles()
    restored.restore(profiles.stored())
    assert {key: profile.person for key, profile in restored.players.items()} == {
        "dennis": "person.dennis",
        "lea": "person.lea",
    }
    for saved in (
        {"name": "Old"},
        {"name": "Old", "person": None},
        {"name": "Old", "person": 7},
        {"name": "Old", "person": "light.kitchen"},
        {"name": "Old", "person": "no entity"},
    ):
        profile = Profile.restored(saved)
        assert profile is not None and profile.person is None, saved


async def test_players_are_linked_and_unlinked_by_actions(
    hass, aioclient_mock, hass_storage
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    hass.states.async_set("person.dennis", "home", {"entity_picture": "/dennis.jpg"})
    await hass.services.async_call(
        DOMAIN,
        "link_player",
        {"player": " Dennis ", "person": "person.dennis"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert players(hass)["Dennis"]["person"] == "person.dennis"
    # The link is saved at once, with the profile.
    saved = hass_storage[f"homedarts.{entry.entry_id}.training"]["data"]["practice"]
    assert saved["profiles"]["players"][0]["person"] == "person.dennis"

    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            "link_player",
            {"player": "Lea", "person": "person.nobody"},
            blocking=True,
        )
    assert error.value.translation_key == "unknown_person"
    assert error.value.translation_placeholders == {"person": "person.nobody"}
    for data in (
        {"player": "Lea", "person": "sensor.dennis"},
        {"player": "   ", "person": "person.dennis"},
        {"player": "x" * 21, "person": "person.dennis"},
    ):
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(DOMAIN, "link_player", data, blocking=True)

    await hass.services.async_call(
        DOMAIN, "unlink_player", {"player": "dennis"}, blocking=True
    )
    await hass.async_block_till_done()
    assert players(hass)["Dennis"]["person"] is None
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN, "unlink_player", {"player": "Nobody"}, blocking=True
        )
    assert error.value.translation_key == "unknown_player"

    # Deleting the player removes the link with the profile.
    await hass.services.async_call(
        DOMAIN,
        "link_player",
        {"player": "Dennis", "person": "person.dennis"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "delete_player", {"name": "Dennis"}, blocking=True
    )
    await hass.async_block_till_done()
    assert "Dennis" not in players(hass)


async def test_a_link_survives_a_restart(hass, aioclient_mock, hass_storage):
    hass_storage["homedarts.person-entry.training"] = {
        "version": 1,
        "key": "homedarts.person-entry.training",
        "data": {
            "practice": {
                "profiles": {
                    "players": [
                        {"name": "Dennis", "legs_played": 4, "person": "person.dennis"},
                        # Saved before players had persons.
                        {"name": "Lea", "legs_played": 2},
                    ]
                }
            }
        },
    }
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        data=local_entry_data(),
        entry_id="person-entry",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert {name: player["person"] for name, player in players(hass).items()} == {
        "Dennis": "person.dennis",
        "Lea": None,
    }


def test_the_player_at_the_board_is_the_thrower():
    practice = PracticeGame()
    practice.set_name(0, "Dennis")
    # Without a game, nobody is at the board.
    assert practice.thrower is None
    practice.set_players(2)
    practice.set_name(1, "Lea")
    practice.bull_off = True
    practice.play(501)
    # The bull-off starts with the first player, then the second.
    assert practice.thrower == "Dennis"
    practice.bulling.index = 1
    assert practice.thrower == "Lea"
    practice.bulling = None
    practice.current = 1
    assert practice.thrower == "Lea"
    practice.set_name(1, "")
    assert practice.thrower is None


async def test_board_events_name_the_player_at_the_board(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    await coordinator.async_start_game(501, names=["Dennis", "Lea"])
    await throw(hass, coordinator, T20, S20, BULL)
    await throw(hass, coordinator, S20)
    await coordinator.async_play(0)
    await throw(hass, coordinator, S20)
    named = [
        (kind, attributes["name"])
        for kind, attributes in events
        if kind in ("dart_detected", "visit_thrown", "visit_completed")
    ]
    assert named == [
        ("dart_detected", "Dennis"),
        ("dart_detected", "Dennis"),
        ("dart_detected", "Dennis"),
        ("visit_thrown", "Dennis"),
        ("visit_completed", "Dennis"),
        ("dart_detected", "Lea"),
        ("visit_completed", "Lea"),
        ("dart_detected", None),
        ("visit_completed", None),
    ]
