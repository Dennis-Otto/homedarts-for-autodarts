"""Statistics count what was booked, once: undone visits, corrected wins, the
bot, passes, abandoned matches, shared names and deleted players."""

import pytest
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.homedarts.progress import WEEK

from .local_helpers import MISS, S20, T20, board, entity_id, record, setup_local
from .test_bot_match import against_the_bot, pass_time
from .test_play_comfort import act, kinds, receive, start
from .test_practice_setup import set_number

S1 = ("S1", 1, 1)
D10 = ("D10", 10, 2)
D20 = ("D20", 20, 2)


def week(coordinator, name: str) -> list[int]:
    return coordinator.games.progress.players[name].week(dt_util.now().date())


async def test_an_undone_visit_counts_once_booked_again(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "501", players=["Alex", "Lea"])
    # Alex's 180 reads as 140, and the darts are pulled before anybody notices.
    receive(coordinator, board(T20), board(T20, S20), board(T20, S20, T20), board())
    await hass.async_block_till_done()
    await act(hass, "undo_visit")
    await act(hass, "correct_dart", dart=2, segment="T20")
    await act(hass, "next_player")
    alex = coordinator.games.progress.players["alex"]
    assert alex.counters["darts"] == 3 and sum(alex.hits.values()) == 3
    assert [alex.counters[key] for key in ("tons", "ton_forties", "maximums")] == [
        1,
        1,
        1,
    ]
    assert week(coordinator, "alex")[WEEK["darts"]] == 3
    counts = coordinator.reports.report.counts
    assert [counts[key] for key in ("darts", "visits", "visit_darts", "points")] == [
        3,
        1,
        3,
        180,
    ]
    assert counts["scores_180"] == 1


async def test_a_misread_180_leaves_no_maximum_once_undone(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "501", players=["Alex", "Lea"])
    receive(coordinator, board(T20), board(T20, T20), board(T20, T20, T20), board())
    await hass.async_block_till_done()
    alex = coordinator.games.progress.players["alex"]
    assert alex.counters["maximums"] == 1 and "maximum" in alex.badges
    await act(hass, "undo_visit")
    await act(hass, "correct_dart", dart=2, segment="S20")
    await act(hass, "next_player")
    alex = coordinator.games.progress.players["alex"]
    assert alex.counters["maximums"] == 0 and "maximum" not in alex.badges
    assert coordinator.reports.report.counts["scores_180"] == 0
    assert coordinator.reports.report.highest_visit == 140


async def test_an_undone_misread_180_is_no_personal_best(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    records = coordinator.games.records
    await start(hass, "501", players=["Alex", "Lea"])
    # Alex's first visit sets the highest visit quietly; Lea throws a 1.
    receive(coordinator, board(T20), board(T20, S20), board(T20, S20, S20), board())
    receive(coordinator, board(S1), board())
    # Alex's 140 reads as 180, and the darts are pulled before anybody notices.
    receive(coordinator, board(T20), board(T20, T20), board(T20, T20, T20), board())
    await hass.async_block_till_done()
    assert records.bests["highest_visit"]["value"] == 180
    assert records.latest["value"] == 180
    await act(hass, "undo_visit")
    assert records.bests["highest_visit"]["value"] == 100
    assert records.latest is None
    events = record(hass, coordinator)
    await act(hass, "correct_dart", dart=2, segment="S20")
    await act(hass, "next_player")
    assert records.bests["highest_visit"]["value"] == 140
    assert dict(events)["personal_best"] == {
        "record": "highest_visit",
        "value": 140,
        "previous": 100,
        "name": None,
        "source": "manual",
    }
    assert {key: records.latest[key] for key in ("value", "previous")} == {
        "value": 140,
        "previous": 100,
    }
    # The darts were thrown and stay the darts of the day.
    assert records.darts_today == 7


async def test_an_undone_misread_checkout_is_no_personal_best(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    records = coordinator.games.records
    earlier = {"date": "2026-10-01T20:00:00+00:00", "name": "Sam"}
    records.bests = {
        "highest_checkout": {"value": 40, **earlier},
        "fewest_darts_101": {"value": 6, **earlier},
    }
    await start(hass, "101", players=["Alex", "Sam"], legs=1)
    # Alex's single 20 reads as a double 20: 101 checked out with three darts.
    receive(coordinator, board(T20), board(T20, S1), board(T20, S1, D20), board())
    await hass.async_block_till_done()
    assert records.bests["highest_checkout"]["value"] == 101
    assert records.latest["record"] == "fewest_darts_101"
    await act(hass, "undo_visit")
    await act(hass, "correct_dart", dart=3, segment="S20")
    await act(hass, "next_player")
    assert coordinator.games.practice.winner is None
    assert records.bests["highest_checkout"] == {"value": 40, **earlier}
    assert records.bests["fewest_darts_101"] == {"value": 6, **earlier}
    assert records.latest is None


async def test_an_undone_first_visit_forgets_the_new_player(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "501", players=["Kim"])
    receive(coordinator, board(T20), board())
    await hass.async_block_till_done()
    assert "kim" in coordinator.games.progress.players
    await act(hass, "undo_visit")
    assert "kim" not in coordinator.games.progress.players


async def test_an_undone_winning_visit_leaves_one_leg_and_one_match(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    reports = coordinator.reports
    await start(hass, "101", players=["Alex", "Sam"], legs=1)
    receive(coordinator, board(T20), board(T20, S1), board(T20, S1, D20), board())
    await hass.async_block_till_done()
    assert len(reports.journal.matches) == 1
    await act(hass, "undo_visit")
    assert reports.journal.matches == []
    assert [reports.report.counts[key] for key in ("legs", "matches")] == [0, 0]
    await act(hass, "next_player")
    assert len(reports.journal.matches) == 1
    assert len(coordinator.games.practice.profiles.matches) == 1
    counts = reports.report.counts
    assert [
        counts[key] for key in ("legs", "matches", "darts_at_double", "checkouts")
    ] == [1, 1, 1, 1]
    alex = week(coordinator, "alex")
    assert [
        alex[WEEK[key]]
        for key in ("x01_darts", "x01_points", "legs", "legs_won", "checkouts")
    ] == [3, 101, 1, 1, 1]


async def test_a_week_that_ended_before_the_undo_stays_reported(
    hass, aioclient_mock, freezer
):
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-10-04 23:59:00+02:00")
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "501", players=["Alex", "Lea"])
    receive(coordinator, board(T20), board())
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 120)
    assert coordinator.reports.report.last["visits"] == 1
    await act(hass, "undo_visit")
    await act(hass, "next_player")
    # The visit counts for the new week, too, as it was booked again.
    assert coordinator.reports.report.counts["visits"] == 1
    assert coordinator.reports.report.last["visits"] == 1


async def test_records_and_the_report_count_the_booked_leg_only(hass, aioclient_mock):
    """A win announced with a dart can be corrected away before it is booked."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "101")
    coordinator.games.practice.players[0].remaining = 40
    events = record(hass, coordinator)
    receive(coordinator, board(D20))
    # The board reads the dart again, as a single 20: no checkout.
    receive(coordinator, board(S20), board(S20, D10), board())
    await hass.async_block_till_done()
    assert kinds(events).count("leg_won") == 2
    assert "personal_best" not in kinds(events)
    records = coordinator.games.records.bests
    assert records["fewest_darts_101"]["value"] == 2
    assert records["highest_checkout"]["value"] == 40
    assert coordinator.reports.report.counts["legs"] == 1


async def test_the_bot_counts_for_nobody(hass, aioclient_mock, freezer):
    entry, coordinator = await against_the_bot(hass, aioclient_mock, game="101")
    events = record(hass, coordinator)
    for _ in range(10):
        receive(coordinator, board(MISS), board())
        await hass.async_block_till_done()
        for _ in range(5):
            await pass_time(hass, freezer, 1)
        if coordinator.games.practice.legs_total:
            break
    assert coordinator.games.practice.legs[0].get("bot") is True
    # Its leg is played, but sets no record and is nobody's progress.
    assert coordinator.reports.report.counts["legs"] == 1
    assert not {"fewest_darts_101", "highest_checkout"} & set(
        coordinator.games.records.bests
    )
    assert set(coordinator.games.progress.players) == {"alex"}
    # The bot's darts have positions, Alex's none: the session has no darts.
    assert len(coordinator.games.progress.session) == 0
    unlocked = [details for kind, details in events if kind == "achievement_unlocked"]
    assert all(details["name"] == "Alex" for details in unlocked)
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("passed", [False, True], ids=["dart", "pass"])
async def test_a_passed_last_turn_books_the_match_like_a_dart(
    hass, aioclient_mock, passed
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "count_up", players=["Alex", "Sam"], rounds=1)
    receive(coordinator, board(T20), board())
    await hass.async_block_till_done()
    # Sam's turn ends the only round, with a missed dart or without one.
    if passed:
        await act(hass, "next_player")
    else:
        receive(coordinator, board(MISS), board())
        await hass.async_block_till_done()
    assert coordinator.games.practice.winner == 0
    counts = coordinator.reports.report.counts
    assert [counts[key] for key in ("legs", "matches")] == [1, 1]
    assert len(coordinator.reports.journal.matches) == 1
    for name in ("alex", "sam"):
        assert week(coordinator, name)[WEEK["legs"]] == 1


async def test_an_abandoned_match_does_not_start_the_next_one(
    hass, aioclient_mock, freezer
):
    freezer.move_to("2026-09-20 18:00:00+00:00")
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "101", players=["Alex", "Sam"], legs=1)
    receive(coordinator, board(T20), board())
    await hass.async_block_till_done()
    # A week later, the same game starts anew and is played to the end.
    freezer.move_to("2026-09-27 20:00:00+00:00")
    await start(hass, "101", players=["Alex", "Sam"], legs=1)
    receive(coordinator, board(T20), board(T20, S1), board(T20, S1, D20), board())
    await hass.async_block_till_done()
    (match,) = coordinator.reports.journal.matches
    assert match["started"] == "2026-09-27T20:00:00+00:00"


async def test_a_deleted_player_leaves_the_weekly_report(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "101", players=["Alex"])
    # The first checkout sets the record quietly, a higher one beats it.
    for checkout, dart in ((32, ("D16", 16, 2)), (40, D20)):
        coordinator.games.practice.players[0].remaining = checkout
        receive(coordinator, board(dart), board())
    await hass.async_block_till_done()
    names = [best["name"] for best in coordinator.reports.report.bests]
    assert "Alex" in names
    await act(hass, "delete_player", name="alex")
    names = [best["name"] for best in coordinator.reports.report.bests]
    assert "Alex" not in names and len(names) == 2


async def test_a_deleted_player_leaves_last_weeks_report(hass, aioclient_mock, freezer):
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-10-04 23:59:00+02:00")
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "101", players=["Alex"])
    for checkout, dart in ((32, ("D16", 16, 2)), (40, D20)):
        coordinator.games.practice.players[0].remaining = checkout
        receive(coordinator, board(dart), board())
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 120)
    report = entity_id(hass, "sensor", "weekly_report")

    def names(state) -> list[str | None]:
        return [
            best["name"] for best in state.attributes["last_week"]["personal_bests"]
        ]

    assert "Alex" in names(hass.states.get(report))
    changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await act(hass, "delete_player", name="alex")
    (change,) = [event for event in changes if event.data["entity_id"] == report]
    assert "Alex" not in names(change.data["new_state"])
    assert "Alex" in names(change.data["old_state"])


async def name_seat(hass, seat: int, name: str) -> None:
    await hass.services.async_call(
        "text",
        "set_value",
        {
            "entity_id": entity_id(hass, "text", f"practice_player_{seat}"),
            "value": name,
        },
        blocking=True,
    )


async def test_two_seats_never_share_a_name(hass, aioclient_mock):
    """The name of each seat, as the games view enters it, is a player of its own."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    await set_number(hass, "practice_players", 8)
    await name_seat(hass, 1, "Alex")
    await name_seat(hass, 8, "Sam")
    for seat, name in ((2, " alex "), (2, "SAM")):
        with pytest.raises(ServiceValidationError) as error:
            await name_seat(hass, seat, name)
        assert error.value.translation_key == "duplicate_player"
        assert error.value.translation_placeholders == {"name": name.strip()}
    # A seat may change the letters of its own name, and seats may be empty.
    await name_seat(hass, 1, "ALEX")
    await name_seat(hass, 8, "")
    await name_seat(hass, 2, "")
    assert practice.names == ["ALEX", *[""] * 7]


async def test_a_resting_seat_gives_its_name_up(hass, aioclient_mock):
    """Sam trains alone after a match with Alex: the seat Sam sat on before
    rests, and its name goes to the seat Sam takes now."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    await start(hass, "501", players=["Alex", "Sam"])
    await set_number(hass, "practice_players", 1)
    await name_seat(hass, 1, "sam")
    assert practice.names[:2] == ["sam", ""]
    assert hass.states.get(entity_id(hass, "text", "practice_player_2")).state == ""
    # A resting seat cannot take the name of a seat in play.
    with pytest.raises(ServiceValidationError):
        await name_seat(hass, 2, "Sam")
    assert practice.names[:2] == ["sam", ""]


async def test_the_bots_seat_gives_its_name_up(hass, aioclient_mock):
    """The bot plays under no name; its seat keeps the name of whoever sat
    there before."""
    _entry, coordinator = await against_the_bot(hass, aioclient_mock)
    practice = coordinator.games.practice
    await name_seat(hass, 2, "Sam")
    await name_seat(hass, 1, "SAM")
    assert practice.bot_seat == 1 and practice.names[:2] == ["SAM", ""]


async def test_a_refused_name_brings_the_practice_players_back(hass, aioclient_mock):
    """After a tournament, the players from before come back with the first
    change of a setting, also with a name they refuse."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    practice = entry.runtime_data.local.games.practice
    await start(hass, "501", players=["Zoe", "Sam"])
    await act(hass, "start_tournament", players=["Tom", "Ida", "Ben"], game="101")
    await act(hass, "stop_tournament")
    with pytest.raises(ServiceValidationError):
        await name_seat(hass, 1, "Sam")
    assert practice.names[:2] == ["Zoe", "Sam"]
    assert hass.states.get(entity_id(hass, "text", "practice_player_1")).state == "Zoe"


async def test_the_bull_off_darts_are_training_darts(hass, aioclient_mock):
    """Every dart thrown counts for the training session, also in a bull-off:
    only the game decides what a dart scores."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await start(hass, "501", players=["Alex", "Sam"], bull_off=True)
    receive(coordinator, board(("Bull", 25, 2)), board(), board(T20), board())
    await hass.async_block_till_done()
    assert coordinator.games.practice.bulling is None
    training = coordinator.games.training.snapshot()
    assert (training["darts"], training["visits"], training["bulls"]) == (2, 2, 1)
    assert coordinator.games.quality.snapshot()["darts"] == 2
