"""Corrections, darts entered by hand, passing the turn and undoing a visit in
Home Assistant, with the entities and events they change."""

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError

from .local_helpers import (
    MISS,
    S20,
    T20,
    board,
    entity_id,
    record,
    setup_local,
    state,
    switch,
)

S5 = ("S5", 5, 1)


async def act(hass, service: str, **data) -> None:
    await hass.services.async_call("homedarts", service, data, blocking=True)
    await hass.async_block_till_done()


async def start(hass, game: str = "301", **data) -> None:
    await act(hass, "start_game", game=game, **data)


def receive(coordinator, *states) -> None:
    for item in states:
        coordinator.async_receive("state", item)


def kinds(events) -> list[str]:
    return [kind for kind, _ in events]


def undoable(hass) -> bool:
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    return remaining.attributes["undo"]


def throws(hass) -> list[dict]:
    visit = hass.states.get(entity_id(hass, "sensor", "local_visit_score"))
    return visit.attributes["throws"]


async def test_a_correction_changes_the_game_and_the_training(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass)
    events = record(hass, coordinator)
    # The board reads a single 20 where a treble 20 is.
    receive(coordinator, board(T20), board(T20, S20))
    await hass.async_block_till_done()
    assert state(hass, "sensor", "practice_remaining") == "221"
    await act(hass, "correct_dart", dart=2, segment="t20")
    assert events[-1] == (
        "dart_corrected",
        {
            "dart_index": 2,
            "segment": "T20",
            "score": 60,
            "previous": "S20",
            "manual": True,
            "game": 301,
            "name": None,
            "source": "manual",
        },
    )
    assert state(hass, "sensor", "practice_remaining") == "181"
    assert state(hass, "sensor", "training_points") == "120"
    assert state(hass, "sensor", "local_visit_score") == "120"
    assert state(hass, "sensor", "last_throw") == "T20"
    assert [
        (dart["segment"], dart.get("corrected"), dart["dart"]) for dart in throws(hass)
    ] == [
        ("T20", None, 1),
        ("T20", True, 2),
    ]
    # The board keeps its reading; the correction holds until the takeout.
    receive(coordinator, board(T20, S20), board(T20, S20, S5))
    await hass.async_block_till_done()
    assert state(hass, "sensor", "practice_remaining") == "176"
    events.clear()
    receive(coordinator, board())
    await hass.async_block_till_done()
    completed = dict(events)["visit_completed"]
    assert completed["score"] == 125 and completed["manual"] is True
    assert state(hass, "sensor", "practice_remaining") == "176"
    assert state(hass, "sensor", "training_points") == "125"


async def test_the_bulls_have_the_names_players_use(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass)
    events = record(hass, coordinator)
    receive(coordinator, board(T20), board(T20, S20))
    await hass.async_block_till_done()
    await act(hass, "correct_dart", dart=1, segment="d25")
    assert (events[-1][1]["segment"], events[-1][1]["score"]) == ("BULL", 50)
    await act(hass, "correct_dart", dart=2, segment="SB")
    assert (events[-1][1]["segment"], events[-1][1]["score"]) == ("25", 25)
    assert state(hass, "sensor", "practice_remaining") == "226"


async def test_corrections_that_cannot_be_made(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    receive(coordinator, board(T20))
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "correct_dart", dart=2, segment="S20")
    assert error.value.translation_key == "no_dart"
    assert error.value.translation_placeholders == {"dart": "2"}
    for wrong in ("T21", "20", "S0"):
        with pytest.raises(ServiceValidationError) as error:
            await act(hass, "correct_dart", dart=1, segment=wrong)
        assert error.value.translation_key == "invalid_segment"
    for wrong in ({"dart": 1, "segment": ""}, {"dart": 4, "segment": "S20"}):
        with pytest.raises(vol.Invalid):
            await act(hass, "correct_dart", **wrong)
    # Correcting to what the board reads changes nothing.
    events = record(hass, coordinator)
    await act(hass, "correct_dart", dart=1, segment="T20")
    assert events == []


async def test_darts_entered_by_hand_need_the_switch(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    assert state(hass, "switch", "practice_manual_entry") == "off"
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "throw_dart", segment="T20")
    assert error.value.translation_key == "manual_entry_off"
    await switch(hass, "practice_manual_entry", True)
    await start(hass, players=["Alex", "Lea"])
    events = record(hass, coordinator)
    for bed in ("T20", "T20", "bull"):
        await act(hass, "throw_dart", segment=bed)
    assert kinds(events) == [*["dart_detected"] * 3, "visit_thrown"]
    assert events[0][1] == {
        "dart_index": 1,
        "segment": "T20",
        "score": 60,
        "manual": True,
        "game": 301,
        "name": "Alex",
        "source": "manual",
        # As a caller says it, in the language of Home Assistant.
        "call": "Treble 20",
    }
    assert events[-1][1]["manual"] is True and events[-1][1]["score"] == 170
    assert state(hass, "sensor", "practice_remaining") == "131"
    assert [dart.get("manual") for dart in throws(hass)] == [True] * 3
    assert "x" not in throws(hass)[0]
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "throw_dart", segment="S1")
    assert error.value.translation_key == "visit_full"
    # Without a takeout, the next player comes to the board.
    events.clear()
    await act(hass, "next_player")
    assert kinds(events) == ["visit_completed", "turn_changed"]
    assert events[1][1]["name"] == "Lea" and events[1][1]["source"] == "manual"
    training = coordinator.games.training.snapshot()
    assert training["darts"] == 3 and training["manual_darts"] == 3
    assert coordinator.games.records.darts_today == 3


async def test_a_dart_entered_by_hand_can_say_where_it_is(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await switch(hass, "practice_manual_entry", True)
    await start(hass)
    # The bed follows from the spot; a bed named with it must be the same.
    await act(hass, "throw_dart", x=0.02, y=0.61)
    await act(hass, "throw_dart", segment="bull", x="0.01", y="-0.02")
    assert [(dart["segment"], dart["x"], dart["y"]) for dart in throws(hass)] == [
        ("T20", 0.02, 0.61),
        ("BULL", 0.01, -0.02),
    ]
    assert state(hass, "sensor", "practice_remaining") == "191"
    assert coordinator.games.manual.extras[1].position == (0.01, -0.02)


async def test_a_dart_moved_in_its_bed_is_drawn_at_its_new_spot(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock, state=board())
    await switch(hass, "practice_manual_entry", True)
    await start(hass)
    await act(hass, "throw_dart", x=0, y=0.6)
    # The spot of the dart, in the same treble 20; the board saw none of it.
    await act(hass, "correct_dart", dart=1, x=0.05, y=0.62)
    assert [(dart["segment"], dart["x"], dart["y"]) for dart in throws(hass)] == [
        ("T20", 0.05, 0.62)
    ]
    # No camera jitter moves a dart placed by hand, so even a small move counts.
    await act(hass, "correct_dart", dart=1, x=0.052, y=0.62)
    assert [(dart["x"], dart["y"]) for dart in throws(hass)] == [(0.052, 0.62)]
    assert state(hass, "sensor", "practice_remaining") == "241"


async def test_manual_entry_without_the_detection(hass, aioclient_mock):
    stopped = {**board(), "running": False, "status": "Stopped", "event": "Stopped"}
    entry = await setup_local(hass, aioclient_mock, state=stopped)
    coordinator = entry.runtime_data.local
    await switch(hass, "practice_manual_entry", True)
    await start(hass)
    events = record(hass, coordinator)
    await act(hass, "throw_dart", segment="T20")
    await act(hass, "throw_dart", segment="miss")
    assert state(hass, "sensor", "practice_remaining") == "241"
    # A poll of the stopped board keeps the visit.
    receive(coordinator, stopped)
    await hass.async_block_till_done()
    assert state(hass, "sensor", "practice_remaining") == "241"
    await act(hass, "next_player")
    assert "visit_completed" in kinds(events)
    assert coordinator.games.practice.players[0].remaining == 241


async def test_the_next_player_while_darts_are_in_the_board(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, players=["Alex", "Lea"])
    events = record(hass, coordinator)
    receive(coordinator, board(T20))
    await hass.async_block_till_done()
    await act(hass, "next_player")
    assert kinds(events)[-2:] == ["visit_completed", "turn_changed"]
    # Alex's dart stays in the board; Lea's darts count for Lea.
    events.clear()
    receive(coordinator, board(T20), board(T20, S20))
    await hass.async_block_till_done()
    assert events[0][1]["dart_index"] == 1 and events[0][1]["name"] == "Lea"
    assert [dart["segment"] for dart in throws(hass)] == ["S20"]
    assert coordinator.games.practice.snapshot()["scores"][1]["remaining"] == 281
    # Passing without darts: the turn goes on.
    receive(coordinator, board())
    await hass.async_block_till_done()
    events.clear()
    await act(hass, "next_player")
    assert kinds(events) == ["turn_changed"]
    assert events[0][1]["name"] == "Lea" and events[0][1]["remaining"] == 281


async def test_a_party_game_passes_without_darts_but_not_while_choosing(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    await start(hass, "golf", players=["Alex", "Sam"])
    # A visit without darts: three misses, five strokes in Golf.
    await act(hass, "next_player")
    assert practice.current == 1 and practice.party.points == [5, 0]
    await start(hass, "killer", players=["Alex", "Sam"])
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "next_player")
    assert error.value.translation_key == "empty_visit"


async def test_undo_the_last_visit_to_correct_it(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "501", players=["Alex", "Lea"])
    events = record(hass, coordinator)
    # Alex's 180 reads as 140, and the darts are pulled before anybody notices.
    receive(coordinator, board(T20), board(T20, S20), board(T20, S20, T20), board())
    await hass.async_block_till_done()
    assert coordinator.games.practice.players[0].remaining == 361
    assert state(hass, "sensor", "training_points") == "140"
    assert coordinator.games.practice.current == 1
    # The cards offer the undo while it is possible.
    assert undoable(hass) is True
    events.clear()
    await act(hass, "undo_visit")
    assert undoable(hass) is False
    assert events[0] == (
        "visit_undone",
        {
            "darts": 3,
            "score": 140,
            "segments": ["T20", "S20", "T20"],
            "game": 501,
            "name": "Alex",
            "source": "manual",
        },
    )
    # Alex is at the board again with the darts of the visit.
    assert coordinator.games.practice.current == 0
    assert state(hass, "sensor", "practice_remaining") == "361"
    assert [dart["segment"] for dart in throws(hass)] == ["T20", "S20", "T20"]
    assert state(hass, "sensor", "training_points") == "140"
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "undo_visit")
    assert error.value.translation_key == "undo_unavailable"
    await act(hass, "correct_dart", dart=2, segment="T20")
    assert state(hass, "sensor", "practice_remaining") == "321"
    events.clear()
    await act(hass, "next_player")
    assert dict(events)["visit_completed"]["score"] == 180
    assert coordinator.games.practice.players[0].remaining == 321
    training = coordinator.games.training.snapshot()
    assert training["points"] == 180 and training["scores_180"] == 1
    assert training["visits"] == 1


async def test_nothing_to_undo(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    with pytest.raises(ServiceValidationError):
        await act(hass, "undo_visit")
    await start(hass)
    receive(coordinator, board(T20), board())
    await hass.async_block_till_done()
    assert undoable(hass) is True
    # A dart of the next visit is in the board.
    receive(coordinator, board(MISS))
    await hass.async_block_till_done()
    assert undoable(hass) is False
    with pytest.raises(ServiceValidationError):
        await act(hass, "undo_visit")
    receive(coordinator, board())
    await hass.async_block_till_done()
    # A new game cannot go back to the last one.
    await start(hass)
    assert undoable(hass) is False
    with pytest.raises(ServiceValidationError):
        await act(hass, "undo_visit")


async def test_a_new_game_ends_a_visit_entered_by_hand(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await switch(hass, "practice_manual_entry", True)
    await start(hass)
    await act(hass, "throw_dart", segment="T20")
    events = record(hass, coordinator)
    await start(hass, "501")
    # The dart counts for the training, not for the new game.
    assert kinds(events) == ["game_ended", "game_started", "visit_completed"]
    assert coordinator.games.practice.snapshot()["visit"] == []
    assert state(hass, "sensor", "practice_remaining") == "501"
    assert coordinator.games.training.snapshot()["darts"] == 1


async def test_no_undo_of_a_visit_a_tournament_took(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await act(
        hass, "start_tournament", players=["Alex", "Sam", "Kim"], game="101", legs=1
    )
    checkout = (T20, ("S1", 1, 1), ("D20", 20, 2))
    receive(coordinator, *(board(*checkout[:count]) for count in (1, 2, 3)), board())
    await hass.async_block_till_done()
    matches = coordinator.games.tournament.tournament.matches
    assert any(match.winner is not None for match in matches)
    assert undoable(hass) is False
    with pytest.raises(ServiceValidationError):
        await act(hass, "undo_visit")
