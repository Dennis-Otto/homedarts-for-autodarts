"""A tournament on several boards, without Home Assistant: the board it was
started on holds it, every board plays a match of its own, and the table and
the bracket take the results of all of them."""

import random
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.homedarts.errors import ActionRefused
from custom_components.homedarts.games import BoardGames
from custom_components.homedarts.practice import PracticeGame
from custom_components.homedarts.profiles import Profile
from custom_components.homedarts.tournament import (
    FINISHED,
    KNOCKOUT,
    MAX_BOARDS,
    PLAYING,
    ROUND_ROBIN,
    VISIT_SECONDS,
    WAITING,
    Tournament,
    TournamentDirector,
)

from .local_helpers import T20, board
from .test_games import NOW, Reports, play, visit

S1 = ("S1", 1, 1)
D20 = ("D20", 20, 2)
# A leg of 101 in one visit: the player to throw first wins the match.
CHECKOUT = (T20, S1, D20)
PLAYERS = ["Alex", "Sam", "Kim", "Lea"]
LATER = NOW + timedelta(seconds=30)


def games(key: str) -> BoardGames:
    """A board with nothing on it, by the key of its entry."""
    board_games = BoardGames(Reports(), NOW, random.Random(1))
    board_games.key = key
    play(board_games, board())
    return board_games


def boards(count: int = 2) -> list[BoardGames]:
    return [games(f"board-{number}") for number in range(1, count + 1)]


def start(host: BoardGames, *guests: BoardGames, **options) -> list:
    options = {
        "players": PLAYERS,
        "game": "101",
        "legs": 1,
        "sets": 1,
        **options,
    }
    return host.start_tournament(
        NOW,
        "Garage",
        [(guest.key, f"Board {guest.key[-1]}", guest) for guest in guests],
        **options,
    )


def names(board_games: BoardGames) -> list[str]:
    return board_games.practice.names[:2]


def fired(events, kind: str) -> list[dict]:
    return [attributes for event, attributes, _ in events if event == kind]


def test_every_board_plays_a_match_of_its_own_at_once():
    host, guest = boards()
    events = start(host, guest)
    assert events[0][1]["boards"] == ["Garage", "Board 2"]
    # The first two matches of the round have four different players.
    assert names(host) == ["Alex", "Lea"]
    assert names(guest) == ["Kim", "Sam"]
    assert guest.host is host and host.guests == {"board-2": guest}
    seen = host.tournament_snapshot()
    assert seen["status"] == PLAYING and seen["board"] == 1
    assert seen["boards"] == [
        {
            "board": 1,
            "name": "Garage",
            "match": 1,
            "players": ["Alex", "Lea"],
            "next_at": None,
        },
        {
            "board": 2,
            "name": "Board 2",
            "match": 2,
            "players": ["Kim", "Sam"],
            "next_at": None,
        },
    ]
    assert [fixture["board"] for fixture in seen["fixtures"]] == [1, 2, *[None] * 4]
    # The other board sees the tournament with its own match first.
    other = guest.tournament_snapshot()
    assert other["board"] == 2 and other["current"]["players"] == ["Kim", "Sam"]
    assert guest.tournament_state() == host.tournament_state() == "round_1"
    # Its own tournament settings stay its own.
    assert guest.tournament.tournament is None


def test_the_table_takes_the_results_of_every_board():
    host, guest = boards()
    start(host, guest)
    # The match of the other board ends first; its board holds the result.
    announced = visit(guest, *CHECKOUT)
    assert not fired(announced, "tournament_match_finished")
    finished = fired(host.take_board_events(), "tournament_match_finished")
    assert finished == [
        {
            "format": ROUND_ROBIN,
            "game": 101,
            "matches": 6,
            "match": 2,
            "round": 1,
            "stage": "round_1",
            "board": "Board 2",
            "players": ["Kim", "Sam"],
            "winner": "Kim",
            "loser": "Sam",
            "legs": [1, 0],
            "sets": [1, 0],
            # Alex and Lea play the next matches of Kim and Sam.
            "next": None,
        }
    ]
    assert host.take_board_events() == []
    assert guest.practice.hold
    seen = guest.tournament_snapshot()
    assert seen["status"] == WAITING and seen["next_at"] is None
    assert seen["last_result"]["winner"] == "Kim"
    # Nothing to play for this board yet: not the match the other board plays,
    # but the first one no board plays yet, which it cannot start now.
    assert seen["round"] == 2 and seen["next"]["players"] != ["Alex", "Lea"]
    assert seen["next_ready"] is False
    assert host.tournament_snapshot()["next_ready"] is False
    announced = visit(host, *CHECKOUT)
    assert fired(announced, "tournament_match_finished")[0]["next"] == [
        "Kim",
        "Alex",
    ]
    table = {
        row["name"]: row["points"] for row in host.tournament_snapshot()["standings"]
    }
    assert table == {"Alex": 2, "Kim": 2, "Lea": 0, "Sam": 0}
    # Now every board has a match it can start.
    assert guest.tournament_snapshot()["next_ready"] is True
    assert host.tournament_snapshot()["next_ready"] is True
    assert (
        guest.tournament_snapshot()["standings"]
        == host.tournament_snapshot()["standings"]
    )


def test_after_the_pause_the_first_free_board_takes_the_next_match():
    host, guest = boards()
    start(host, guest)
    visit(guest, *CHECKOUT)
    visit(host, *CHECKOUT)
    director = host.tournament
    # The summary and the pause of each board: 8 and 10 seconds.
    due = NOW + timedelta(seconds=18)
    assert director.due_boards() == [(None, due), ("board-2", due)]
    assert host.next_fixture() == due
    assert host.settle_boards(NOW + timedelta(seconds=17)) == []
    assert host.settle_boards(due) == [host, guest]
    # The board of the tournament first: Kim against Alex, then Lea against Sam.
    assert names(host) == ["Kim", "Alex"]
    assert names(guest) == ["Lea", "Sam"]
    assert not guest.practice.hold
    assert host.next_fixture() is None


def test_players_rest_after_their_match_wherever_they_played_it():
    host, guest = boards()
    # Three players: every match shares a player with the first one.
    start(host, guest, players=PLAYERS[:3])
    assert names(host) == ["Kim", "Sam"]
    assert guest.tournament_snapshot()["status"] == WAITING
    assert host.tournament.due_at("board-2") is None
    visit(host, *CHECKOUT)
    # The other board could take the next match at once, but Kim rests first.
    assert host.tournament.due_boards() == [
        (None, NOW + timedelta(seconds=18)),
        ("board-2", NOW + timedelta(seconds=18)),
    ]
    # Asked to, the other board starts it at once, as the button skips a pause.
    guest.next_tournament_match(NOW)
    assert names(guest) == ["Alex", "Kim"]
    # Sam against Alex has to wait for Alex.
    assert host.tournament.due_boards() == []
    with pytest.raises(ActionRefused) as error:
        host.next_tournament_match(NOW)
    assert error.value.key == "tournament_no_match"


def test_a_board_without_a_match_at_the_start_plays_on_until_it_gets_one():
    host, guest = boards()
    guest.start_game(301, names=["Max"])
    start(host, guest, players=PLAYERS[:3])
    # The board plays its own game meanwhile, and keeps its result.
    assert guest.practice.game == 301 and not guest.practice.hold
    visit(guest, T20)
    assert not guest.board_free()
    visit(host, *CHECKOUT)
    # Its game is played to its end first.
    assert host.settle_boards(LATER) == [host]
    assert names(host) == ["Alex", "Kim"]
    assert guest.practice.game == 301


def test_the_last_result_on_another_board_ends_the_tournament_on_every_board():
    host, guest = boards()
    host.start_game(501, names=["Hugo", "Ina"])
    guest.start_game(301, names=["Max"])
    start(host, guest, format=KNOCKOUT, third_place=True)
    # Semi-finals on both boards; the final and the match for third place next.
    visit(host, *CHECKOUT)
    visit(guest, *CHECKOUT)
    assert host.take_board_events()
    assert host.settle_boards(LATER) == [host, guest]
    # The match for third place comes first in the order of play.
    assert host.tournament_snapshot()["current"]["stage"] == "third_place"
    assert names(host) == ["Lea", "Kim"]
    assert guest.tournament_snapshot()["current"]["stage"] == "final"
    assert names(guest) == ["Alex", "Sam"]
    visit(host, *CHECKOUT)
    visit(guest, *CHECKOUT)
    assert host.tournament.tournament.status == FINISHED
    assert fired(host.take_board_events(), "tournament_finished") == [
        {
            "format": KNOCKOUT,
            "game": 101,
            "matches": 4,
            "winner": "Alex",
            "runner_up": "Sam",
            "third": "Lea",
            "players": PLAYERS,
        }
    ]
    # The board of the final went back to its settings with the result; the
    # board of the tournament does with the next settle.
    assert guest.practice.resume["names"][0] == "Max"
    assert host.practice.hold
    assert host.settle_boards(LATER) == [host, guest]
    assert host.guests == {} and guest.host is None
    # Every board goes back to its settings with its next match.
    assert host.practice.resume["names"][:2] == ["Hugo", "Ina"]
    assert not host.practice.hold and not guest.practice.hold
    assert host.settle_boards(LATER) == []


def test_stopping_the_tournament_hands_every_board_back():
    host, guest = boards()
    guest.start_game(301, names=["Max"])
    start(host, guest)
    assert host.stop_tournament() == [guest]
    assert guest.host is None and host.guests == {}
    assert guest.practice.resume["names"][0] == "Max"
    assert guest.tournament_snapshot()["status"] is None


def test_the_next_match_of_a_board_starts_at_once_when_asked():
    host, guest = boards()
    host.tournament.configure(pause=0)
    start(host, guest)
    visit(guest, *CHECKOUT)
    visit(host, *CHECKOUT)
    # Without a pause, the boards wait for the button.
    assert host.next_fixture() is None
    guest.next_tournament_match(LATER)
    assert names(guest) == ["Kim", "Alex"]
    host.next_tournament_match(LATER)
    assert names(host) == ["Lea", "Sam"]


def test_a_board_in_a_tournament_starts_no_other():
    host, guest, third = boards(3)
    start(host, guest)
    with pytest.raises(ActionRefused) as error:
        start(guest)
    assert (error.value.key, error.value.placeholders) == (
        "board_in_tournament",
        {"board": "Garage"},
    )
    with pytest.raises(ActionRefused) as error:
        start(third, guest)
    assert error.value.placeholders == {"board": "Board 2"}
    with pytest.raises(ActionRefused) as error:
        start(third, host)
    assert error.value.placeholders == {"board": "Board 1"}
    with pytest.raises(ActionRefused) as error:
        start(*boards(MAX_BOARDS + 1))
    assert (error.value.key, error.value.placeholders) == (
        "tournament_boards",
        {"max": str(MAX_BOARDS)},
    )
    assert third.tournament.tournament is None


def test_the_board_itself_and_a_board_named_twice_count_once():
    host, guest = boards()
    start(host, guest, guest, host)
    assert list(host.guests) == ["board-2"]
    assert host.tournament_snapshot()["boards"][1]["name"] == "Board 2"
    assert len(host.tournament_snapshot()["boards"]) == 2


def test_a_board_whose_own_tournament_is_over_joins_the_next_one():
    host, guest = boards()
    guest.tournament.start(
        guest.practice, NOW, players=PLAYERS[:3], game="101", legs=1, sets=1
    )
    guest.tournament.tournament.status = FINISHED
    start(host, guest)
    assert guest.tournament.tournament is None and guest.host is host


def test_the_boards_of_a_finished_tournament_go_back_before_the_next_one():
    host, guest = boards()
    guest.start_game(301, names=["Max"])
    start(host, guest)
    host.tournament.tournament.status = FINISHED
    start(host, players=PLAYERS[:3])
    assert guest.host is None and host.guests == {}
    assert guest.practice.resume["names"][0] == "Max"
    assert not host.several_boards


def test_a_player_of_a_tournament_on_another_board_stays():
    host, guest = boards()
    start(host, guest)
    with pytest.raises(ActionRefused) as error:
        guest.delete_player("Kim")
    assert error.value.key == "player_in_tournament"
    guest.practice.profiles.link("Kim", "person.kim")
    with pytest.raises(ActionRefused) as error:
        guest.rename_player("Kim", "Kimberly", NOW)
    assert error.value.key == "player_in_tournament"


def test_boards_find_each_other_again_after_a_restart():
    host, guest = boards()
    start(host, guest)
    visit(guest, *CHECKOUT)
    saved_host, saved_guest = host.stored(), guest.stored()
    # The board of the tournament unloads: the other board loses sight of it.
    assert host.leave() == [guest]
    assert guest.host is None and host.guests == {}
    again, back = games("board-1"), games("board-2")
    again.restore(saved_host, NOW)
    back.restore(saved_guest, NOW)
    assert not back.practice.hold
    assert again.attach(back)
    # The result the board showed waits for its next match again.
    assert back.practice.hold
    assert again.tournament_snapshot() == host.tournament_snapshot()
    assert back.tournament_snapshot()["last_result"]["winner"] == "Kim"
    # Not twice, not itself, and no board that is no part of it.
    assert not again.attach(back)
    assert not again.attach(again)
    assert not again.attach(games("board-7"))
    # The other board unloads: the board of the tournament loses sight of it.
    assert back.leave() == [again]
    assert again.guests == {} and back.host is None


def test_a_board_that_plays_for_another_board_gives_its_match_back():
    host, guest = boards()
    start(host, guest)
    saved = host.stored()
    host.leave()
    # Meanwhile, the other board joined a tournament held by a third board.
    third = games("board-3")
    start(third, guest)
    assert guest.host is third
    again = games("board-1")
    again.restore(saved, NOW)
    assert not again.attach(guest)
    assert again.tournament.tournament.seats[1].match is None
    assert guest.host is third


def test_a_board_that_plays_a_tournament_of_its_own_gives_its_match_back():
    host, guest = boards()
    start(host, guest)
    saved = host.stored()
    host.leave()
    # Meanwhile, the other board started a tournament of its own.
    guest.tournament.start(
        guest.practice, NOW, players=PLAYERS[:3], game="101", legs=1, sets=1
    )
    again = games("board-1")
    again.restore(saved, NOW)
    assert again.tournament.tournament.seats[1].match == 1
    assert not again.attach(guest)
    tournament = again.tournament.tournament
    assert tournament.seats[1].match is None
    assert tournament.matches[1].board is None and tournament.matches[1].started is None
    assert guest.host is None
    # Again, without a match: nothing changes; and a board that is no part of it.
    again.tournament.vacate("board-2")
    again.tournament.vacate("board-9")
    assert tournament.status == PLAYING
    # The board of the tournament takes the match after its own.
    visit(again, *CHECKOUT)
    assert again.settle_boards(LATER) == [again]
    assert names(again) == ["Kim", "Sam"]


def test_a_restored_tournament_keeps_its_boards_where_they_fit():
    host, guest = boards()
    start(host, guest)
    saved = host.tournament.tournament.stored()
    seats = saved["seats"]
    assert [seat["key"] for seat in seats] == ["board-1", "board-2"]
    assert Tournament.restored(saved).seats == host.tournament.tournament.seats
    # Matches that no board can take, and boards that make no sense.
    odd = Tournament.restored(
        {
            **saved,
            "seats": [
                {**seats[0], "match": "first"},
                {**seats[1], "match": 0, "saved": "none"},
            ],
        }
    )
    assert [seat.match for seat in odd.seats] == [None, 0]
    assert odd.matches[1].started is None and odd.matches[1].board is None
    clash = Tournament.restored(
        {**saved, "seats": [{**seats[0], "match": 0}, {**seats[1], "match": 0}]}
    )
    assert [seat.match for seat in clash.seats] == [0, None]
    # A board that has not played takes a match of players who have not either at once.
    director = TournamentDirector()
    director.tournament = clash
    assert director.due_at("board-2") == NOW
    # One stored without its start: at once, at no time that a snapshot shows.
    clash.started = None
    assert director.due_at("board-2") == datetime.min.replace(tzinfo=UTC)
    assert director.due(NOW, "board-2")
    assert [board["next_at"] for board in director.snapshot("board-2")["boards"]] == [
        None,
        None,
    ]
    beyond = Tournament.restored(
        {**saved, "seats": [seats[0], {**seats[1], "match": 99}]}
    )
    assert beyond.seats[1].match is None
    for broken in (
        "boards",
        [seats[0]],
        [seats[0], seats[0]],
        [seats[0], {"key": 2, "name": "x"}],
        [seats[0], "seat"],
    ):
        assert not Tournament.restored({**saved, "seats": broken}).several
    # Broken times and boards of a match are dropped.
    matches = saved["matches"]
    timed = Tournament.restored(
        {
            **saved,
            "matches": [{**matches[0], "started": "soon", "board": 5}, *matches[1:]],
        }
    )
    assert timed.matches[0].started == saved["started"]
    assert timed.matches[0].board == 0


def test_the_end_is_forecast_from_the_averages_and_the_pace():
    host, guest = boards()
    start(host, guest)
    tournament = host.tournament.tournament
    # Six matches of 101 at 40 points a visit, three on each board: a match takes
    # (101 / 40 + 1) visits of each player at 30 seconds a visit.
    match = 2 * (101 / 40 + 1) * VISIT_SECONDS
    expected = NOW + timedelta(seconds=3 * match + 2 * 18)
    assert tournament.ends_at(8, 10) == expected.isoformat()
    assert host.tournament_snapshot()["ends_at"] == expected.isoformat()
    # A finished tournament or one without a start has no forecast.
    tournament.started = None
    assert tournament.ends_at(8, 10) is None
    tournament.started = NOW.isoformat()
    tournament.status = FINISHED
    assert tournament.ends_at(8, 10) is None


def test_the_averages_of_the_profiles_at_the_start_count():
    practice = PracticeGame()
    practice.profiles.players["alex"] = Profile(
        name="Alex", x01_points=1010, x01_darts=30
    )
    director = TournamentDirector()
    director.start(practice, NOW, players=PLAYERS[:3], game="101", legs=1, sets=1)
    tournament = director.tournament
    assert tournament.rates == [101.0, None, None]
    # Alex checks out in two visits; a match against Alex takes as many of the other.
    assert tournament._length(1, tournament._rates_now(), 30) == timedelta(
        seconds=2 * 2 * 30
    )
    # The averages of the tournament take over from the profiles; one of no
    # points at all is none.
    tournament.matches[0].winner = 2
    tournament.matches[0].points = [101, 0]
    tournament.matches[0].darts = [3, 3]
    assert tournament.matches[0].players == [2, 1]
    assert tournament._rates_now() == [101.0, 40.0, 101.0]
    # Cricket counts the marks per round.
    practice.profiles.players["alex"].cricket_marks = 9
    practice.profiles.players["alex"].cricket_darts = 9
    cricket = TournamentDirector()
    cricket.start(practice, NOW, players=PLAYERS[:3], game="cricket", legs=1, sets=1)
    assert cricket.tournament.rates == [3.0, None, None]
    assert cricket.tournament._length(1, [3.0, 1.5, 1.5], 30) == timedelta(
        seconds=2 * 7 * 30
    )


def test_the_pace_of_the_matches_played_takes_over_from_the_default():
    host, guest = boards()
    start(host, guest)
    tournament = host.tournament.tournament
    for match in tournament.matches[:2]:
        match.winner = match.players[0]
        match.darts = [30, 30]
        match.ended = (NOW + timedelta(minutes=10)).isoformat()
    for seat in tournament.seats:
        seat.match = None
    # 20 visits in 10 minutes: 30 seconds a visit, timed.
    assert tournament._visit_seconds() == 30.0
    tournament.matches[0].ended = (NOW + timedelta(minutes=20)).isoformat()
    assert tournament._visit_seconds() == 45.0
    # Too few visits keep the default.
    tournament.matches[0].darts = tournament.matches[1].darts = [3, 3]
    assert tournament._visit_seconds() == VISIT_SECONDS


def test_cricket_and_open_places_have_a_forecast_too():
    host, guest = boards()
    start(host, guest, game="cricket", format=KNOCKOUT, players=[*PLAYERS, "Max"])
    tournament = host.tournament.tournament
    assert tournament.ends_at(8, 10) is not None
    # A board that waits after its match frees up after the gap.
    visit(host, *CHECKOUT)
    assert tournament.ends_at(0, 0) is not None


def test_a_naive_time_is_taken_as_utc():
    host, guest = boards()
    start(host, guest)
    tournament = host.tournament.tournament
    tournament.started = "2026-10-01T20:00:00"
    assert tournament.ends_at(8, 10).endswith("+00:00")


def test_a_board_that_left_for_good_gives_its_match_back():
    host, guest = boards()
    start(host, guest)
    director = host.tournament
    director.vacate("board-9")
    director.vacate("board-2")
    tournament = director.tournament
    assert tournament.seats[1].match is None
    assert tournament.matches[1].board is None
    # Again, without a match: nothing changes.
    director.vacate("board-2")
    # The board of the tournament takes it after its own match.
    host.leave()
    assert director.guests() == ["board-2"]
    visit(host, *CHECKOUT)
    host.settle_boards(LATER)
    assert names(host) == ["Kim", "Sam"]


def test_a_board_of_one_board_tournament_has_no_boards():
    director = TournamentDirector()
    assert director.due_boards() == []
    assert director.guests() == [] and director.name() == ""
    practice = PracticeGame()
    director.start(practice, NOW, players=PLAYERS[:3], game="101", legs=1, sets=1)
    snapshot = director.snapshot()
    assert "boards" not in snapshot and "board" not in snapshot["fixtures"][0]
    host = games("board-1")
    host.start_tournament(
        NOW, "Garage", None, players=PLAYERS[:3], game="101", legs=1, sets=1
    )
    assert host.settle_boards(LATER) == [] and not host.several_boards
