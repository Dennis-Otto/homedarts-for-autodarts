"""Two boards in one home: their entities, events and actions stay apart, and
a tournament on both boards plays a match on each of them."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.services import _device_entries

from .local_helpers import (
    SECOND_BASE,
    T20,
    board,
    entity_id,
    record,
    setup_local,
    state,
    unique_ids,
)


def own(ids: set[str], board_id: str) -> set[str]:
    """The keys of the unique IDs, without the board ID."""
    prefix = f"{board_id}_"
    assert all(unique_id.startswith(prefix) for unique_id in ids)
    return {unique_id.removeprefix(prefix) for unique_id in ids}


async def test_each_board_has_its_own_entities_and_device(hass, two_boards):
    first, second = two_boards
    keys = own(unique_ids(hass, first), "board-1")
    # The second board has two cameras instead of three.
    assert own(unique_ids(hass, second), "board-2") == keys - {
        "camera_2",
        "camera_2_fps",
        "camera_2_problem",
        "calibrate_camera_2",
    }
    for entry in two_boards:
        assert entry.runtime_data.local.board_id == entry.data["board_id"]
    assert second.runtime_data.local.client.base_url == SECOND_BASE
    # Both devices have the default name; their entity IDs still differ.
    first_id = entity_id(hass, "event", "board_events")
    second_id = entity_id(hass, "event", "board_events", "board-2")
    assert first_id != second_id


async def test_darts_of_one_board_announce_on_that_board_only(hass, two_boards):
    first, second = two_boards
    first_events = record(hass, first.runtime_data.local)
    second_events = record(hass, second.runtime_data.local)
    second.runtime_data.local.async_receive("state", board(T20))
    await hass.async_block_till_done()
    assert [kind for kind, _ in second_events] == ["dart_detected"]
    assert first_events == []
    assert state(hass, "sensor", "last_throw", "board-2") == "T20"
    assert state(hass, "sensor", "last_throw", "board-1") == "unknown"
    event = hass.states.get(entity_id(hass, "event", "board_events", "board-2"))
    assert event.attributes["event_type"] == "dart_detected"
    assert state(hass, "event", "board_events", "board-1") == "unknown"


async def test_actions_need_the_board_and_act_on_it_only(hass, two_boards):
    first, second = two_boards
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN, "start_game", {"game": "501"}, blocking=True
        )
    assert error.value.translation_key == "several_boards"
    await hass.services.async_call(
        DOMAIN,
        "start_game",
        {"game": "301", "players": ["Alex"], "config_entry_id": second.entry_id},
        blocking=True,
    )
    assert second.runtime_data.local.games.practice.game == 301
    assert first.runtime_data.local.games.practice.game == 0
    assert state(hass, "select", "practice_game", "board-2") == "301"
    assert state(hass, "select", "practice_game", "board-1") == "off"

    # Alex plays on the second board only, so only there is a profile to delete.
    coordinator = second.runtime_data.local
    for count in range(1, 4):
        coordinator.async_receive("state", board(*[T20] * count))
    coordinator.async_receive("state", board())
    await hass.async_block_till_done()
    assert "alex" in coordinator.games.practice.profiles.players
    for player, new_name in (("Alex", "Al"), ("Al", "Alex")):
        await hass.services.async_call(
            DOMAIN,
            "rename_player",
            {
                "player": player,
                "new_name": new_name,
                "config_entry_id": second.entry_id,
            },
            blocking=True,
        )
        assert list(coordinator.games.practice.profiles.players) == [
            new_name.casefold()
        ]
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            "delete_player",
            {"name": "Alex", "config_entry_id": first.entry_id},
            blocking=True,
        )
    assert error.value.translation_key == "unknown_player"
    await hass.services.async_call(
        DOMAIN,
        "delete_player",
        {"name": "ALEX", "config_entry_id": second.entry_id},
        blocking=True,
    )
    assert not coordinator.games.practice.profiles.players


async def test_one_board_away_leaves_the_other_one_alone(hass, two_boards):
    first, second = two_boards
    assert await hass.config_entries.async_unload(first.entry_id)
    await hass.async_block_till_done()
    # With one board loaded, the actions find it without an entry.
    await hass.services.async_call(
        DOMAIN, "start_game", {"game": "cricket"}, blocking=True
    )
    assert second.runtime_data.local.games.practice.cricket
    assert state(hass, "switch", "detection", "board-2") == "on"


# -- a tournament on several boards ----------------------------------------------

# A dartboard without Autodarts, every dart entered in Home Assistant.
DARTBOARD = "manual_0123456789abcdef0123456789abcdef"
S1 = ("S1", 1, 1)
D20 = ("D20", 20, 2)
# A leg of 101 in one visit: the player to throw first wins the match.
CHECKOUT = (T20, S1, D20)
PLAYERS = ["Alex", "Sam", "Kim", "Lea"]


@pytest.fixture
async def board_and_dartboard(hass, aioclient_mock):
    """An Autodarts board and, in the cellar, a dartboard without Autodarts."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    dartboard = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=DARTBOARD,
        title="Autodarts (Cellar)",
        data={
            "board_id": DARTBOARD,
            "manual_board": True,
            "name": "Cellar",
        },
    )
    dartboard.add_to_hass(hass)
    assert await hass.config_entries.async_setup(dartboard.entry_id)
    await hass.async_block_till_done()
    return entry, dartboard


async def act(hass, service: str, **data) -> None:
    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await hass.async_block_till_done()


async def throw(hass, coordinator, *darts) -> None:
    """A visit on the Autodarts board, dart by dart, then the takeout."""
    for count in range(1, len(darts) + 1):
        coordinator.async_receive("state", board(*darts[:count]))
    coordinator.async_receive("state", board())
    await hass.async_block_till_done()


async def enter(hass, entry, *beds: str) -> None:
    """A visit entered by hand on the dartboard."""
    for bed in beds:
        await act(hass, "throw_dart", segment=bed, config_entry_id=entry.entry_id)
    await act(hass, "next_player", config_entry_id=entry.entry_id)


async def pause(hass, freezer, seconds: int = 19) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


def tournament(hass, board_id: str = "board-1") -> dict:
    return hass.states.get(entity_id(hass, "sensor", "tournament", board_id)).attributes


def players(hass, board_id: str = "board-1") -> list[str]:
    return [state(hass, "text", f"practice_player_{seat}", board_id) for seat in (1, 2)]


def fired(events, kind: str) -> list[dict]:
    return [attributes for event, attributes in events if event == kind]


async def start_on_both(hass, entry, dartboard, **options) -> None:
    """A round robin of 101 on both boards, held by the Autodarts board."""
    await act(
        hass,
        "start_tournament",
        **{
            "config_entry_id": entry.entry_id,
            "boards": [dartboard.entry_id],
            "players": PLAYERS,
            "game": "101",
            "legs": 1,
            "sets": 1,
            **options,
        },
    )


async def test_two_boards_play_one_tournament_side_by_side(
    hass, board_and_dartboard, freezer
):
    entry, dartboard = board_and_dartboard
    host, cellar = entry.runtime_data.local, dartboard.runtime_data.local
    events, cellar_events = record(hass, host), record(hass, cellar)
    await start_on_both(hass, entry, dartboard)
    assert fired(events, "tournament_started")[0]["boards"] == [
        "Autodarts Board",
        "Cellar",
    ]
    # Each board plays a match of the first round.
    assert players(hass) == ["Alex", "Lea"]
    assert players(hass, DARTBOARD) == ["Kim", "Sam"]
    assert state(hass, "sensor", "tournament", DARTBOARD) == "round_1"
    seen = tournament(hass, DARTBOARD)
    assert seen["board"] == 2 and seen["current"]["players"] == ["Kim", "Sam"]
    assert [board["name"] for board in tournament(hass)["boards"]] == [
        "Autodarts Board",
        "Cellar",
    ]

    # The dartboard ends its match first; the board of the tournament says so.
    await enter(hass, dartboard, "T20", "S1", "D20")
    finished = fired(events, "tournament_match_finished")
    assert [(item["board"], item["winner"]) for item in finished] == [("Cellar", "Kim")]
    assert finished[0]["source"] == "manual"
    assert not fired(cellar_events, "tournament_match_finished")
    points = {row["name"]: row["points"] for row in tournament(hass)["standings"]}
    assert points["Kim"] == 2
    assert tournament(hass, DARTBOARD)["status"] == "waiting"

    await throw(hass, host, *CHECKOUT)
    points = {row["name"]: row["points"] for row in tournament(hass)["standings"]}
    assert points == {"Alex": 2, "Kim": 2, "Lea": 0, "Sam": 0}
    assert tournament(hass, DARTBOARD)["standings"] == tournament(hass)["standings"]

    # After the pause, the first free board takes the next match, then the other.
    await pause(hass, freezer)
    assert players(hass) == ["Kim", "Alex"]
    assert players(hass, DARTBOARD) == ["Lea", "Sam"]
    await throw(hass, host, *CHECKOUT)
    await enter(hass, dartboard, "T20", "S1", "D20")
    await pause(hass, freezer)
    assert players(hass) == ["Sam", "Alex"]
    assert players(hass, DARTBOARD) == ["Lea", "Kim"]
    await enter(hass, dartboard, "T20", "S1", "D20")
    await throw(hass, host, *CHECKOUT)
    # Kim and Lea won two matches each; Lea beat Kim.
    assert [item["winner"] for item in fired(events, "tournament_finished")] == ["Lea"]
    assert state(hass, "sensor", "tournament") == "finished"
    assert len(fired(events, "tournament_match_finished")) == 6
    # Every board goes back to its own games after the tournament.
    assert cellar.games.host is None and not host.games.guests
    assert state(hass, "sensor", "tournament", DARTBOARD) == "no_tournament"


async def test_the_boards_find_each_other_after_a_reload(
    hass, board_and_dartboard, freezer
):
    entry, dartboard = board_and_dartboard
    await start_on_both(hass, entry, dartboard)
    assert await hass.config_entries.async_reload(dartboard.entry_id)
    await hass.async_block_till_done()
    cellar = dartboard.runtime_data.local
    host = entry.runtime_data.local
    assert cellar.games.host is host.games
    await enter(hass, dartboard, "T20", "S1", "D20")
    assert tournament(hass)["matches_played"] == 1
    # The board of the tournament reloads, and still holds it.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    host = entry.runtime_data.local
    assert cellar.games.host is host.games
    assert cellar.games.practice.hold
    await throw(hass, host, *CHECKOUT)
    assert tournament(hass)["matches_played"] == 2
    await pause(hass, freezer)
    assert players(hass, DARTBOARD) == ["Lea", "Sam"]


async def test_a_deleted_board_gives_its_match_back(hass, board_and_dartboard):
    entry, dartboard = board_and_dartboard
    await start_on_both(hass, entry, dartboard)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_remove(dartboard.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    seats = entry.runtime_data.local.games.tournament.tournament.seats
    assert seats[1].match is None


async def test_a_board_deleted_while_the_other_plays_on_gives_its_match_back(
    hass, board_and_dartboard, freezer
):
    entry, dartboard = board_and_dartboard
    await start_on_both(hass, entry, dartboard)
    assert await hass.config_entries.async_remove(dartboard.entry_id)
    await hass.async_block_till_done()
    host = entry.runtime_data.local
    assert host.games.tournament.tournament.seats[1].match is None
    # The board of the tournament plays the match of the deleted board next.
    await throw(hass, host, *CHECKOUT)
    await pause(hass, freezer)
    assert players(hass) == ["Kim", "Sam"]


async def test_a_deleted_board_of_the_tournament_hands_its_boards_back(
    hass, board_and_dartboard
):
    entry, dartboard = board_and_dartboard
    cellar = dartboard.runtime_data.local
    await start_on_both(hass, entry, dartboard)
    await enter(hass, dartboard, "T20", "S1", "D20")
    assert cellar.games.practice.hold
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    # The dartboard plays again, with its settings from before the tournament.
    assert cellar.games.host is None and not cellar.games.practice.hold
    assert cellar.games.practice.resume is not None


async def test_the_boards_of_the_action_are_checked(hass, board_and_dartboard):
    entry, dartboard = board_and_dartboard
    with pytest.raises(ServiceValidationError) as error:
        await start_on_both(hass, entry, dartboard, boards=["no-such-board"])
    assert error.value.translation_key == "unknown_board"
    # A device of another integration is no board either.
    other = MockConfigEntry(domain="demo")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("demo", "lamp")}
    )
    with pytest.raises(ServiceValidationError) as error:
        await start_on_both(hass, entry, dartboard, boards=[device.id])
    assert error.value.translation_placeholders == {"board": device.id}
    # The device picker of the action names the boards by their devices.
    [cellar] = dr.async_entries_for_config_entry(dr.async_get(hass), dartboard.entry_id)
    await start_on_both(hass, entry, dartboard, boards=[cellar.id, entry.entry_id])
    assert dartboard.runtime_data.local.games.host is entry.runtime_data.local.games
    # A board of the tournament starts no other, and waits for its next match.
    with pytest.raises(ServiceValidationError) as error:
        await act(
            hass,
            "start_tournament",
            config_entry_id=dartboard.entry_id,
            players=PLAYERS,
        )
    assert error.value.translation_key == "board_in_tournament"
    assert error.value.translation_placeholders == {"board": "Autodarts Board"}
    await enter(hass, dartboard, "T20", "S1", "D20")
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "next_tournament_match", config_entry_id=dartboard.entry_id)
    assert error.value.translation_key == "tournament_no_match"
    # Stopped on any of its boards, the tournament stops on all of them.
    await act(hass, "stop_tournament", config_entry_id=dartboard.entry_id)
    assert state(hass, "sensor", "tournament") == "no_tournament"
    assert dartboard.runtime_data.local.games.host is None


@pytest.mark.parametrize(
    "device",
    [
        SimpleNamespace(config_entries={"cellar", "lamp"}),
        SimpleNamespace(
            is_composite_device=True,
            config_entry_id="cellar",
            config_entries={"cellar", "lamp"},
        ),
    ],
    ids=["before Home Assistant 2026.10", "a device of several entries"],
)
def test_a_device_of_several_entries_names_each(device):
    """Home Assistant before 2026.10 keeps every config entry of a device in
    config_entries, and so does a device of several entries from before it; every
    other device has one, config_entry_id, and reading config_entries of it reports
    the integration."""
    assert _device_entries(device) == {"cellar", "lamp"}


async def test_a_board_with_darts_on_it_takes_its_match_with_the_takeout(
    hass, board_and_dartboard, freezer
):
    entry, dartboard = board_and_dartboard
    host = entry.runtime_data.local
    await start_on_both(hass, entry, dartboard)
    await enter(hass, dartboard, "T20", "S1", "D20")
    await throw(hass, host, *CHECKOUT)
    # Darts on the Autodarts board as the pause ends: the dartboard is the
    # first free board and takes the next match.
    host.async_receive("state", board(T20))
    await pause(hass, freezer)
    assert players(hass, DARTBOARD) == ["Kim", "Alex"]
    assert tournament(hass)["status"] == "waiting"
    # Looked at again a few seconds later, and started with the takeout.
    await pause(hass, freezer, 5)
    assert tournament(hass)["status"] == "waiting"
    host.async_receive("state", board())
    await hass.async_block_till_done()
    assert players(hass) == ["Lea", "Sam"]
    assert tournament(hass)["status"] == "playing"


async def test_three_players_on_two_boards_wait_for_each_other(
    hass, board_and_dartboard, freezer
):
    entry, dartboard = board_and_dartboard
    host = entry.runtime_data.local
    await start_on_both(hass, entry, dartboard, players=PLAYERS[:3])
    # Every match shares a player with the first one: the dartboard waits.
    assert tournament(hass, DARTBOARD)["status"] == "waiting"
    assert tournament(hass, DARTBOARD)["next_at"] is None
    await throw(hass, host, *CHECKOUT)
    # Both boards could take the next match once Kim rested: the first one does.
    await pause(hass, freezer)
    assert players(hass) == ["Alex", "Kim"]
    assert tournament(hass, DARTBOARD)["status"] == "waiting"


async def test_the_boards_go_by_the_names_their_users_gave_them(
    hass, board_and_dartboard
):
    entry, dartboard = board_and_dartboard
    registry = dr.async_get(hass)
    [device] = dr.async_entries_for_config_entry(registry, dartboard.entry_id)
    registry.async_update_device(device.id, name_by_user="Garage")
    await start_on_both(hass, entry, dartboard)
    names = [board["name"] for board in tournament(hass)["boards"]]
    assert names == ["Autodarts Board", "Garage"]


async def test_a_board_that_shuts_down_changes_no_other_board(
    hass, board_and_dartboard
):
    entry, dartboard = board_and_dartboard
    await start_on_both(hass, entry, dartboard)
    host = entry.runtime_data.local
    # A look at the boards still to come is called off.
    host._schedule_fixture()
    assert host._settle_task is not None
    await host.async_shutdown()
    assert host._settle_task is None
    assert dartboard.runtime_data.local.games.host is None
