"""The X01 practice game in Home Assistant: entities, events and restarts."""

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .local_helpers import (
    BULL,
    OUTER_BULL,
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

D18 = ("D18", 18, 2)
D20 = ("D20", 20, 2)
S1 = ("S1", 1, 1)


async def select_game(hass, option: str) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id(hass, "select", "practice_game"), "option": option},
        blocking=True,
    )
    await hass.async_block_till_done()


async def throw(hass, coordinator, *darts) -> None:
    """Throw a visit dart by dart, then pull the darts."""
    for count in range(1, len(darts) + 1):
        coordinator.async_receive("state", board(*darts[:count]))
    coordinator.async_receive("state", board())
    await hass.async_block_till_done()


async def test_practice_game_counts_down_busts_and_wins(
    hass, aioclient_mock, hass_storage
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    assert state(hass, "select", "practice_game") == "off"
    assert state(hass, "sensor", "practice_remaining") == "unknown"
    assert state(hass, "sensor", "practice_checkout") == "unknown"

    await select_game(hass, "301")
    assert state(hass, "sensor", "practice_remaining") == "301"
    await throw(hass, coordinator, T20, T20, T20)
    assert state(hass, "sensor", "practice_remaining") == "121"
    assert state(hass, "sensor", "practice_checkout") == "T20 25 D18"

    # 121 - 120 leaves one, which cannot be finished on a double.
    await throw(hass, coordinator, T20, T20)
    busts = [attributes for kind, attributes in events if kind == "bust"]
    assert len(busts) == 1
    assert busts[0]["game"] == 301 and busts[0]["remaining"] == 121
    assert state(hass, "sensor", "practice_remaining") == "121"

    await throw(hass, coordinator, T20, OUTER_BULL, D18)
    won = [attributes for kind, attributes in events if kind == "leg_won"]
    assert len(won) == 1
    assert {key: won[0][key] for key in ("game", "darts", "average", "checkout")} == {
        "game": 301,
        "darts": 8,
        "average": 112.88,
        "checkout": 121,
    }
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.state == "301"
    assert remaining.attributes["legs"][0]["darts"] == 8

    registry = er.async_get(hass)
    double_out = registry.async_get(entity_id(hass, "switch", "practice_double_out"))
    assert double_out.entity_category == er.EntityCategory.CONFIG
    await switch(hass, "practice_double_out", False)
    assert state(hass, "switch", "practice_double_out") == "off"
    await throw(hass, coordinator, BULL)
    assert state(hass, "sensor", "practice_remaining") == "251"
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", "practice_new_leg")},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert state(hass, "sensor", "practice_remaining") == "301"
    # Settings and the new leg are saved at once, with the finished legs.
    saved = hass_storage[f"homedarts.{entry.entry_id}.training"]["data"]["practice"]
    assert saved["game"] == 301 and saved["double_out"] is False
    assert saved["legs"][0]["checkout"] == 121
    await select_game(hass, "off")
    assert state(hass, "sensor", "practice_remaining") == "unknown"


async def test_visits_name_the_game_and_come_before_their_result(hass, aioclient_mock):
    """Callers hear the visit with its third dart, then the bust or the win."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    await select_game(hass, "101")
    # 101 - 60 - 20 leaves 21, and the third dart busts.
    await throw(hass, coordinator, T20, S20, T20)
    await throw(hass, coordinator, T20, S1, D20)
    assert [kind for kind, _ in events] == [
        "game_started",
        *["dart_detected"] * 3,
        "visit_thrown",
        "bust",
        "visit_completed",
        "turn_changed",
        *["dart_detected"] * 3,
        "visit_thrown",
        "leg_won",
        "visit_completed",
        "turn_changed",
    ]
    visits = [
        attributes
        for kind, attributes in events
        if kind in ("dart_detected", "visit_thrown", "visit_completed")
    ]
    assert all(attributes["game"] == 101 for attributes in visits)
    assert events[4][1]["score"] == 140
    assert events[6][1]["thrown"] is True
    # Training games and free play leave the game empty.
    await select_game(hass, "around_the_clock")
    await throw(hass, coordinator, S1)
    await select_game(hass, "off")
    await throw(hass, coordinator, S20)
    darts = [attributes for kind, attributes in events if kind == "dart_detected"]
    assert [dart["game"] for dart in darts[-2:]] == [None, None]


async def test_practice_game_survives_a_restart(hass, aioclient_mock, hass_storage):
    data = local_entry_data()
    hass_storage["homedarts.practice-entry.training"] = {
        "version": 1,
        "key": "homedarts.practice-entry.training",
        "data": {
            "practice": {
                "game": 501,
                "double_out": True,
                "remaining": 100,
                "darts": 30,
                "legs": [{"game": 501, "darts": 18, "average": 83.5, "checkout": 40}],
            }
        },
    }
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(
        domain="homedarts", version=2, data=data, entry_id="practice-entry"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, "select", "practice_game") == "501"
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.state == "100"
    assert remaining.attributes["darts"] == 30
    assert len(remaining.attributes["legs"]) == 1
    assert state(hass, "sensor", "practice_checkout") == "T20 D20"


async def set_number(hass, key: str, value: int) -> None:
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id(hass, "number", key), "value": value},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_a_match_of_two_players_with_names_turns_and_a_winner(
    hass, aioclient_mock, hass_storage
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    name = entity_id(hass, "text", "practice_player_1")
    assert (
        er.async_get(hass).async_get(name).entity_category == er.EntityCategory.CONFIG
    )
    await hass.services.async_call(
        "text", "set_value", {"entity_id": name, "value": "Dennis"}, blocking=True
    )
    await select_game(hass, "301")
    await set_number(hass, "practice_players", 2)
    await set_number(hass, "practice_legs", 1)
    assert state(hass, "number", "practice_players") == "2"
    assert state(hass, "text", "practice_player_1") == "Dennis"

    await throw(hass, coordinator, T20, T20, T20)
    turns = [attributes for kind, attributes in events if kind == "turn_changed"]
    assert turns[-1]["player"] == 2 and turns[-1]["remaining"] == 301
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.state == "301" and remaining.attributes["player"] == 2
    scores = remaining.attributes["scores"]
    assert [(score["name"], score["remaining"]) for score in scores] == [
        ("Dennis", 121),
        (None, 301),
    ]

    await throw(hass, coordinator, OUTER_BULL)
    coordinator.games.practice.players[0].remaining = 36
    await throw(hass, coordinator, D18)
    won = [attributes for kind, attributes in events if kind == "match_won"]
    assert won and won[0]["name"] == "Dennis" and won[0]["sets"] == 1
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.attributes["winner"] == 1

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", "practice_new_match")},
        blocking=True,
    )
    await hass.async_block_till_done()
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.attributes["winner"] is None
    assert [score["remaining"] for score in remaining.attributes["scores"]] == [
        301,
        301,
    ]
    saved = hass_storage[f"homedarts.{entry.entry_id}.training"]["data"]["practice"]
    assert saved["names"][0] == "Dennis" and len(saved["players"]) == 2


async def test_legs_and_sets_to_win_are_numbers(hass, aioclient_mock, hass_storage):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await select_game(hass, "501")
    await set_number(hass, "practice_players", 2)
    await set_number(hass, "practice_legs", 3)
    await set_number(hass, "practice_sets", 2)
    assert state(hass, "number", "practice_legs") == "3"
    assert state(hass, "number", "practice_sets") == "2"
    practice = entry.runtime_data.local.games.practice
    assert (practice.legs_to_win, practice.sets_to_win) == (3, 2)
    saved = hass_storage[f"homedarts.{entry.entry_id}.training"]["data"]["practice"]
    assert (saved["legs_to_win"], saved["sets_to_win"]) == (3, 2)


async def test_training_games_show_their_target(hass, aioclient_mock, hass_storage):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    assert state(hass, "sensor", "practice_target") == "unknown"
    await select_game(hass, "around_the_clock")
    assert state(hass, "select", "practice_game") == "around_the_clock"
    assert state(hass, "sensor", "practice_remaining") == "unknown"
    target = hass.states.get(entity_id(hass, "sensor", "practice_target"))
    assert target.state == "1" and target.attributes["drill"] == "around_the_clock"
    assert target.attributes["targets"] == 21

    one = ("S1", 1, 1)
    two = ("D2", 2, 2)
    await throw(hass, coordinator, one, two, T20)
    target = hass.states.get(entity_id(hass, "sensor", "practice_target"))
    assert target.state == "3" and target.attributes["hits"] == 2
    assert target.attributes["darts"] == 3

    await select_game(hass, "bobs_27")
    target = hass.states.get(entity_id(hass, "sensor", "practice_target"))
    assert target.state == "D1" and target.attributes["score"] == 27
    coordinator.games.practice.drills["bobs_27"].score = 1
    await throw(hass, coordinator, T20)
    finished = [attributes for kind, attributes in events if kind == "drill_finished"]
    assert finished and finished[0]["drill"] == "bobs_27"
    assert finished[0]["completed"] is False

    await select_game(hass, "checkout")
    target = hass.states.get(entity_id(hass, "sensor", "practice_target"))
    assert int(target.state) == target.attributes["remaining"]
    await select_game(hass, "off")
    assert state(hass, "sensor", "practice_target") == "unknown"
    saved = hass_storage[f"homedarts.{entry.entry_id}.training"]["data"]["practice"]
    assert saved["drills"]["bobs_27"]["results"][0]["score"] == -1


async def test_cricket_shows_marks_points_and_the_next_target(
    hass, aioclient_mock, hass_storage
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    await select_game(hass, "cricket")
    await set_number(hass, "practice_players", 2)
    assert state(hass, "select", "practice_game") == "cricket"
    assert state(hass, "sensor", "practice_target") == "T20"
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.state == "unknown" and remaining.attributes["game"] == "cricket"
    assert remaining.attributes["numbers"] == [20, 19, 18, 17, 16, 15, 25]

    await throw(hass, coordinator, T20, T20)
    turns = [attributes for kind, attributes in events if kind == "turn_changed"]
    assert turns[-1]["player"] == 2 and turns[-1]["points"] == 0
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    first = remaining.attributes["scores"][0]
    assert first["marks"][0] == 3 and first["points"] == 60
    # Player 2 still needs every number.
    assert state(hass, "sensor", "practice_target") == "T20"
    await select_game(hass, "off")
    saved = hass_storage[f"homedarts.{entry.entry_id}.training"]["data"]["practice"]
    assert saved["game"] == 0 and saved["players"][0]["marks"] == [0] * 7


async def test_cricket_survives_a_restart(hass, aioclient_mock, hass_storage):
    marks = [3, 3, 2, 0, 0, 0, 1]
    hass_storage["homedarts.practice-entry.training"] = {
        "version": 1,
        "key": "homedarts.practice-entry.training",
        "data": {
            "practice": {
                "game": "cricket",
                "players": [{"marks": marks, "points": 38, "darts": 9}],
                "legs": [{"game": "cricket", "darts": 24, "mpr": 2.5, "points": 0}],
            }
        },
    }
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        data=local_entry_data(),
        entry_id="practice-entry",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, "select", "practice_game") == "cricket"
    assert state(hass, "sensor", "practice_target") == "T18"
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.attributes["scores"][0]["marks"] == marks
    assert remaining.attributes["points"] == 38 and remaining.attributes["mpr"] == 0.0
    assert remaining.attributes["legs"][0]["mpr"] == 2.5


async def test_practice_statistics_follow_the_legs(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    assert state(hass, "sensor", "practice_first_9_average") == "unknown"
    assert state(hass, "sensor", "practice_legs_played") == "0"
    await select_game(hass, "301")
    coordinator.games.practice.players[0].remaining = 36
    await throw(hass, coordinator, D18)
    assert state(hass, "sensor", "practice_legs_played") == "1"
    assert state(hass, "sensor", "practice_checkout_rate") == "100.0"
    first_nine = hass.states.get(entity_id(hass, "sensor", "practice_first_9_average"))
    assert float(first_nine.state) == 108.0
    assert first_nine.attributes["legs_counted"] == 1
    registry = er.async_get(hass)
    legs = registry.async_get(entity_id(hass, "sensor", "practice_legs_played"))
    # An undone visit that won a leg takes the leg back.
    assert legs.capabilities == {"state_class": "total"}


async def test_party_games_rules_and_the_bull_off_in_home_assistant(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    await select_game(hass, "shanghai")
    assert state(hass, "select", "practice_game") == "shanghai"
    assert state(hass, "sensor", "practice_target") == "1"
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.state == "unknown" and remaining.attributes["round"] == 1
    assert remaining.attributes["points"] == 0

    registry = er.async_get(hass)
    for key in (
        "practice_double_in",
        "practice_bull_off",
        "practice_bull_off_distance",
    ):
        rule = registry.async_get(entity_id(hass, "switch", key))
        assert rule.entity_category == er.EntityCategory.CONFIG
        assert state(hass, "switch", key) == "off"
    await set_number(hass, "practice_players", 2)
    await switch(hass, "practice_bull_off", True)
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.attributes["bull_off"]["player"] == 1
    await throw(hass, coordinator, OUTER_BULL)
    await throw(hass, coordinator, BULL)
    won = [attributes for kind, attributes in events if kind == "bull_off_won"]
    # The bullseye beats the outer bull; the board reported no positions.
    assert won and won[0]["player"] == 2 and won[0]["hit"] == "BULL"
    assert won[0]["distance"] is None
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.attributes["bull_off"] is None
    assert remaining.attributes["player"] == 2

    await select_game(hass, "1001")
    await switch(hass, "practice_double_in", True)
    assert coordinator.games.practice.double_in is True
    assert coordinator.games.practice.snapshot()["remaining"] == 1001
