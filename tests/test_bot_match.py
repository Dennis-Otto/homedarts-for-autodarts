"""A match against the bot in Home Assistant: its turns, its darts and its settings."""

import asyncio
import random
from datetime import timedelta
from unittest.mock import patch

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed_exact,
)

from custom_components.homedarts.bot import Bot
from custom_components.homedarts.number import AutodartsBotLevel

from .local_helpers import (
    S20,
    T20,
    board,
    entity_id,
    local_entry_data,
    mock_board,
    record,
    setup_local,
    state,
    until,
)
from .test_play_comfort import act, kinds, receive, start, throws
from .test_practice_setup import select_game, set_number


async def pass_time(hass, freezer, seconds: float) -> None:
    """Exactly this much time, without the half second of other tests."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()


async def against_the_bot(hass, aioclient_mock, game="301", level=120, **data):
    """Alex against the bot, which throws a second after each of its darts."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    coordinator.games.bot = Bot(random.Random(1))
    await set_number(hass, "practice_bot_delay", 1)
    await start(hass, game, players=["Alex"], bot_level=level, **data)
    return entry, coordinator


def bot_darts(events) -> list[dict]:
    return [
        attributes
        for kind, attributes in events
        if kind == "dart_detected" and attributes.get("bot")
    ]


async def test_the_bot_throws_after_the_players_visit(hass, aioclient_mock, freezer):
    entry, coordinator = await against_the_bot(hass, aioclient_mock)
    assert state(hass, "number", "practice_players") == "1"
    assert state(hass, "number", "practice_bot_level") == "120"
    remaining = hass.states.get(entity_id(hass, "sensor", "practice_remaining"))
    assert remaining.attributes["bot"] == {"player": 2, "level": 120}
    assert remaining.attributes["players"] == 2
    events = record(hass, coordinator)
    receive(coordinator, board(T20), board())
    await hass.async_block_till_done()
    turn = events[-1][1]
    assert events[-1][0] == "turn_changed" and turn["bot"] is True
    # The bot waits its delay before each dart.
    await pass_time(hass, freezer, 0.5)
    assert not bot_darts(events)
    await pass_time(hass, freezer, 0.6)
    (first,) = bot_darts(events)
    assert first["name"] is None and first["source"] == "bot"
    assert first["game"] == 301 and first["dart_index"] == 1
    # Its darts show on the board like detected ones, with their positions.
    (shown,) = throws(hass)
    assert shown["bot"] is True and {"x", "y"} <= set(shown)
    await pass_time(hass, freezer, 1)
    await pass_time(hass, freezer, 1)
    assert len(bot_darts(events)) == 3
    # Only Alex's visit is completed so far.
    assert kinds(events).count("visit_completed") == 1
    # A second after its last dart, its visit ends and Alex is up again.
    await pass_time(hass, freezer, 1)
    completed = dict(events)["visit_completed"]
    assert completed["bot"] is True and completed["darts"] == 3
    assert events[-1][0] == "turn_changed" and events[-1][1]["name"] == "Alex"
    assert not coordinator.games.practice.bot_up and throws(hass) == []
    # Only Alex's dart counts for the training, the records and the reports.
    assert coordinator.games.training.snapshot()["darts"] == 1
    assert coordinator.games.records.darts_today == 1
    assert coordinator.reports.report.counts["darts"] == 1
    assert coordinator.games.quality.snapshot()["darts"] == 1
    visits = coordinator.games.training.recent_visits
    assert [visit["score"] for visit in visits] == [60]
    # Nothing more happens until Alex throws.
    await pass_time(hass, freezer, 5)
    assert len(bot_darts(events)) == 3
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_a_player_throwing_early_ends_the_bots_visit(
    hass, aioclient_mock, freezer
):
    entry, coordinator = await against_the_bot(hass, aioclient_mock)
    receive(coordinator, board(T20), board())
    await pass_time(hass, freezer, 1.1)
    events = record(hass, coordinator)
    receive(coordinator, board(S20))
    await hass.async_block_till_done()
    # The bot throws the rest of its visit at once; the new dart is Alex's.
    assert len(bot_darts(events)) == 2
    assert kinds(events)[-3:] == ["visit_completed", "turn_changed", "dart_detected"]
    alex = events[-1][1]
    assert alex["name"] == "Alex" and "bot" not in alex and alex["dart_index"] == 1
    assert coordinator.games.practice.snapshot()["visit"] == ["S20"]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_what_players_cannot_do_while_the_bot_throws(
    hass, aioclient_mock, freezer
):
    entry, coordinator = await against_the_bot(hass, aioclient_mock)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id(hass, "switch", "practice_manual_entry")},
        blocking=True,
    )
    receive(coordinator, board(T20), board())
    await pass_time(hass, freezer, 1.1)
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "throw_dart", segment="T20")
    assert error.value.translation_key == "bot_turn"
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "correct_dart", dart=1, segment="T20")
    assert error.value.translation_key == "bot_dart"
    # Next player ends the bot's visit early.
    events = record(hass, coordinator)
    await act(hass, "next_player")
    assert kinds(events) == ["visit_completed", "turn_changed"]
    assert not coordinator.games.practice.bot_up
    # Its next step does not come, and a step that was due does nothing.
    await pass_time(hass, freezer, 3)
    coordinator._bot_step(dt_util.utcnow())
    assert len(bot_darts(events)) == 0
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_undo_takes_back_the_players_visit_and_the_bots(
    hass, aioclient_mock, freezer
):
    entry, coordinator = await against_the_bot(hass, aioclient_mock)
    receive(coordinator, board(T20), board(T20, S20), board())
    await hass.async_block_till_done()
    for _ in range(4):
        await pass_time(hass, freezer, 1)
    bot_remaining = coordinator.games.practice.players[1].remaining
    assert bot_remaining < 301 and coordinator.games.practice.current == 0
    await act(hass, "undo_visit")
    practice = coordinator.games.practice
    assert practice.current == 0 and practice.players[1].remaining == 301
    assert practice.snapshot()["visit"] == ["T20", "S20"]
    # The bot waits until Alex's visit is booked again.
    await pass_time(hass, freezer, 3)
    assert not practice.bot_up
    await act(hass, "correct_dart", dart=2, segment="T20")
    await act(hass, "next_player")
    assert practice.players[0].remaining == 181 and practice.bot_up
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_a_new_game_ends_the_bots_visit(hass, aioclient_mock, freezer):
    entry, coordinator = await against_the_bot(hass, aioclient_mock)
    receive(coordinator, board(T20), board())
    await pass_time(hass, freezer, 1.1)
    assert coordinator.games.manual.bot_darts() == 1
    events = record(hass, coordinator)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", "practice_new_leg")},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert "visit_completed" in kinds(events)
    assert (
        coordinator.games.manual.bot_darts() == 0
        and not coordinator.games.practice.bot_up
    )
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_the_bot_throws_its_dart_of_the_bull_off(hass, aioclient_mock, freezer):
    entry, coordinator = await against_the_bot(hass, aioclient_mock, bull_off=True)
    events = record(hass, coordinator)
    receive(coordinator, board(S20), board())
    await hass.async_block_till_done()
    assert coordinator.games.practice.bot_up
    await pass_time(hass, freezer, 1)
    await pass_time(hass, freezer, 1)
    # One dart, then the bull-off goes on or is decided.
    assert len(bot_darts(events)) == 1
    assert dict(events)["visit_completed"]["bot"] is True
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_the_bot_goes_on_after_a_restart(
    hass, aioclient_mock, hass_storage, freezer
):
    hass_storage["homedarts.bot-entry.training"] = {
        "version": 1,
        "key": "homedarts.bot-entry.training",
        "data": {
            "practice": {
                "game": 301,
                "names": ["Alex", "", "", ""],
                "players": [{"remaining": 241}, {"remaining": 301}],
                "current": 1,
                "bot_level": 60,
                "bot_delay": 0.5,
            }
        },
    }
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(
        domain="homedarts", version=2, data=local_entry_data(), entry_id="bot-entry"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.local
    assert coordinator.games.practice.bot_up
    assert state(hass, "number", "practice_bot_delay") == "0.5"
    events = record(hass, coordinator)
    await pass_time(hass, freezer, 0.6)
    assert len(bot_darts(events)) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_the_bot_stops_before_the_unload_waits_for_a_read(
    hass, aioclient_mock, freezer
):
    entry, coordinator = await against_the_bot(hass, aioclient_mock)
    receive(coordinator, board(T20), board())
    await hass.async_block_till_done()
    assert coordinator.games.practice.bot_up
    events = record(hass, coordinator)
    reading = asyncio.Event()

    async def slow_board(*_args):
        reading.set()
        await until(lambda: coordinator._shutting_down)
        for _ in range(100):
            await asyncio.sleep(0)
        # The bot's delay passes while the unload still waits for this read.
        freezer.tick(timedelta(seconds=1.1))
        async_fire_time_changed_exact(hass)
        return board()

    with patch.object(coordinator.client, "get_state", side_effect=slow_board):
        polling = hass.async_create_task(coordinator.async_refresh())
        await reading.wait()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await polling
    await hass.async_block_till_done()
    assert events == []


async def test_the_bot_settings(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    await start(hass, "501")
    await set_number(hass, "practice_bot_level", 60)
    assert practice.bot_seat == 1 and state(hass, "number", "practice_players") == "1"
    # There is no level from 1 to 19: a step down from 20 sends the bot home,
    # and a step up from 0 seats the weakest bot.
    await set_number(hass, "practice_bot_level", 20)
    await set_number(hass, "practice_bot_level", 19)
    assert practice.bot_level == 0 and practice.bot_seat is None
    await set_number(hass, "practice_bot_level", 1)
    assert practice.bot_level == 20
    await set_number(hass, "practice_bot_level", 60)
    with pytest.raises(ServiceValidationError) as error:
        await AutodartsBotLevel(entry.runtime_data.local).async_set_native_value(121)
    assert error.value.translation_key == "invalid_bot_level"
    # With the bot, three players at most.
    await set_number(hass, "practice_players", 3)
    assert len(practice.players) == 4
    with pytest.raises(ServiceValidationError) as error:
        await set_number(hass, "practice_players", 4)
    assert error.value.translation_key == "bot_seat"
    await set_number(hass, "practice_bot_level", 0)
    await set_number(hass, "practice_players", 4)
    with pytest.raises(ServiceValidationError) as error:
        await set_number(hass, "practice_bot_level", 60)
    assert error.value.translation_key == "bot_seat"
    # The bot does not play party games, which have room for eight players.
    await start(hass, "shanghai")
    await set_number(hass, "practice_bot_level", 60)
    assert practice.bot_level == 60 and practice.bot_seat is None
    await set_number(hass, "practice_bot_delay", 2.5)
    assert practice.bot_delay == 2.5


async def test_start_game_counts_the_players_before_a_new_bot_level(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    await start(hass, "501", players=["Alex", "Sam"])
    # Without players, the players stay, and the bot joins them.
    await start(hass, "501", bot_level=60)
    assert practice.humans == 2 and len(practice.players) == 3
    assert practice.names[:2] == ["Alex", "Sam"] and practice.bot_seat == 2
    # Sent home, the bot leaves its seat to nobody.
    await start(hass, "301", bot_level=0)
    assert practice.humans == 2 and len(practice.players) == 2


async def test_choosing_a_game_of_the_bot_keeps_four_players(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    await start(hass, "killer", players=["A", "B", "C", "D"], bot_level=60)
    for game in ("501", "cricket"):
        with pytest.raises(ServiceValidationError) as error:
            await select_game(hass, game)
        assert error.value.translation_key == "bot_seat"
    assert practice.kind == "killer" and len(practice.players) == 4
    # Party games have room for four.
    await select_game(hass, "shanghai")
    assert practice.kind == "shanghai" and len(practice.players) == 4


async def test_the_bot_throws_with_its_cricket_scatter(hass, aioclient_mock, freezer):
    entry, coordinator = await against_the_bot(hass, aioclient_mock, game="cricket")
    with patch.object(
        coordinator.games.bot, "throw", wraps=coordinator.games.bot.throw
    ) as throw:
        receive(coordinator, board(T20), board())
        await pass_time(hass, freezer, 1.1)
    assert throw.call_args.kwargs == {"cricket": True}
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_start_game_with_the_bot(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    with pytest.raises(ServiceValidationError) as error:
        await start(hass, players=["A", "B", "C", "D"], bot_level=60)
    assert error.value.translation_key == "bot_seat"
    for wrong in (10, 121):
        with pytest.raises(ServiceValidationError) as error:
            await start(hass, bot_level=wrong)
        assert error.value.translation_key == "invalid_bot_level"
    with pytest.raises(vol.Invalid):
        await start(hass, bot_level="strong")
    # Three players and the bot make two teams.
    await start(hass, "cricket", players=["A", "B", "C"], bot_level=80, teams=True)
    assert practice.bot_seat == 3 and practice.snapshot()["teams"] is not None
    # Party games do not count the bot's seat.
    await start(hass, "killer", players=["A", "B", "C", "D"])
    assert len(practice.players) == 4 and practice.bot_level == 80
    await start(hass, "501", players=["A"], bot_level=0)
    assert len(practice.players) == 1


async def test_tournaments_play_without_the_bot(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    await start(hass, "501", players=["Alex"], bot_level=60)
    assert practice.bot_seat == 1
    await act(hass, "start_tournament", players=["Alex", "Sam", "Kim"], game="301")
    assert practice.bot_level == 0 and practice.bot_seat is None
    assert len(practice.players) == 2
