"""Tournaments: the draw, the schedule, the table, the bracket and the flow of matches."""

import json
from datetime import UTC, datetime, timedelta
from itertools import combinations
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.homedarts.errors import ActionRefused
from custom_components.homedarts.practice import PracticeGame, valid_settings
from custom_components.homedarts.tournament import (
    FINISHED,
    KNOCKOUT,
    MAX_ENTRANTS,
    MAX_ROUND_ROBIN,
    MIN_ENTRANTS,
    PLAYING,
    ROUND_ROBIN,
    STATES,
    WAITING,
    Match,
    Tournament,
    TournamentDirector,
    TournamentSetup,
    double_knockout,
    knockout,
    parse_players,
    round_robin,
    split_players,
)

from .local_helpers import dart

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
NAMES = ["Alex", "Sam", "Kim", "Lea", "Max", "Tom", "Ida", "Ben"]
# Names for the biggest tournaments.
PLAYERS = [*NAMES, *(f"Player {number}" for number in range(9, MAX_ENTRANTS + 1))]
# A 101 leg in one visit, and one that stops short.
CHECKOUT = ("T20", "S1", "D20")
SHORT = ("S1", "S1", "S1")


def visit(practice: PracticeGame, *names: str) -> None:
    """Throw a visit dart by dart and pull the darts."""
    for count in range(1, len(names) + 1):
        practice.track([dart(name) for name in names[:count]], now=NOW)
    practice.finish_visit(now=NOW)
    practice.track([], now=NOW)


def win(practice: PracticeGame, loser_visits: int = 0) -> None:
    """The player to throw wins a leg of 101; the other one throws first if asked."""
    for _ in range(loser_visits):
        visit(practice, *SHORT)
        visit(practice, *SHORT)
    visit(practice, *CHECKOUT)


def director(
    count: int = 3,
    fmt: str = ROUND_ROBIN,
    game: str = "101",
    legs: int = 1,
    **options,
) -> tuple[TournamentDirector, PracticeGame]:
    practice = PracticeGame()
    tournament = TournamentDirector()
    events = tournament.start(
        practice,
        NOW,
        players=PLAYERS[:count],
        format=fmt,
        game=game,
        legs=legs,
        sets=1,
        **options,
    )
    assert [kind for kind, _ in events] == ["tournament_started"]
    return tournament, practice


def play_out(
    tournament: TournamentDirector,
    practice: PracticeGame,
    winner=lambda names: 0,
    now: datetime = NOW,
) -> list[tuple[str, dict]]:
    """Play every match: the player the function picks wins 1:0, or with legs 2:1."""
    events = []
    while tournament.tournament.status != FINISHED:
        names = practice.names[:2]
        side = winner(names)
        for _ in range(practice.legs_to_win):
            practice.current = side
            win(practice)
        events += tournament.booked(practice, now)
        if tournament.waiting:
            tournament.next_match(practice, NOW)
    return events


# -- the draw -----------------------------------------------------------------


def test_names_are_separated_by_commas_semicolons_or_lines():
    assert parse_players(" Alex, Sam;Kim\n\n , Lea ") == ["Alex", "Sam", "Kim", "Lea"]
    assert parse_players("") == []
    assert parse_players("A" * 30) == ["A" * 20]


@pytest.mark.parametrize("count", range(MIN_ENTRANTS, MAX_ROUND_ROBIN + 1))
def test_a_round_robin_plays_every_pair_once_in_rounds(count):
    matches = round_robin(count)
    pairs = [frozenset(match.players) for match in matches]
    assert sorted(map(sorted, pairs)) == sorted(
        map(sorted, combinations(range(count), 2))
    )
    rounds = count if count % 2 else count - 1
    assert max(match.round for match in matches) == rounds <= 7
    assert all(match.stage == f"round_{match.round}" for match in matches)
    for number in range(1, rounds + 1):
        players = [
            player
            for match in matches
            if match.round == number
            for player in match.players
        ]
        # Nobody plays twice in a round; with an odd number, one player rests.
        assert len(players) == len(set(players)) == count - count % 2
    # Everybody throws first about as often as the opponents.
    first = [
        sum(match.players[0] == player for match in matches) for player in range(count)
    ]
    assert max(first) - min(first) <= 1


def test_a_round_robin_avoids_back_to_back_matches_where_it_can():
    matches = round_robin(5)
    for before, after in zip(matches, matches[1:], strict=False):
        if before.round != after.round:
            assert not set(before.players) & set(after.players)
    # Three players cannot avoid them: every match shares a player with the next.
    assert [match.players for match in round_robin(3)] == [[2, 1], [0, 2], [1, 0]]


@pytest.mark.parametrize(
    ("count", "stages", "byes"),
    [
        (3, ["semi_final"] * 2 + ["final"], 1),
        (4, ["semi_final"] * 2 + ["final"], 0),
        (5, ["quarter_final"] * 4 + ["semi_final"] * 2 + ["final"], 3),
        (8, ["quarter_final"] * 4 + ["semi_final"] * 2 + ["final"], 0),
    ],
)
def test_a_knockout_bracket_gives_the_top_seeds_the_byes(count, stages, byes):
    matches = knockout(count, third_place=False)
    assert [match.stage for match in matches] == stages
    assert sum(match.bye for match in matches) == byes
    first = [match for match in matches if match.round == 1]
    # Seed 1 meets the last seed, and seeds 1 and 2 meet in the final at the earliest.
    assert first[0].players[0] == 0 and first[len(first) // 2].players[0] == 1
    for match in first:
        assert match.bye == (match.players[1] is None)
        if match.bye:
            assert match.players[0] < 3


def test_the_seeding_of_eight_players():
    first = [match.players for match in knockout(8, third_place=True)[:4]]
    assert first == [[0, 7], [3, 4], [1, 6], [2, 5]]
    stages = [match.stage for match in knockout(8, third_place=True)]
    assert stages[-2:] == ["third_place", "final"]


def test_byes_go_on_at_once_and_the_third_place_needs_four_players():
    three = Tournament(
        format=KNOCKOUT,
        game="501",
        players=NAMES[:3],
        legs=1,
        sets=1,
        rules={},
        third_place=True,
    )
    assert three.third_place is False
    final = three.matches[-1]
    assert final.players == [0, None]
    assert three.upcoming() == 1
    five = Tournament(
        format=KNOCKOUT, game="501", players=NAMES[:5], legs=1, sets=1, rules={}
    )
    # Seeds 1 to 3 go on; seeds 2 and 3 meet in the semi-final already.
    semis = [match for match in five.matches if match.stage == "semi_final"]
    assert [match.players for match in semis] == [[0, None], [1, 2]]
    round_robin_third = Tournament(
        format=ROUND_ROBIN,
        game="501",
        players=NAMES[:4],
        legs=1,
        sets=1,
        rules={},
        third_place=True,
    )
    assert round_robin_third.third_place is False


# -- the flow of a tournament ----------------------------------------------------


def test_a_round_robin_of_three_through_the_practice_game():
    tournament, practice = director(3)
    assert tournament.state() == "round_1"
    assert practice.kind == 101 and practice.names[:2] == ["Kim", "Sam"]
    assert practice.legs_to_win == practice.sets_to_win == 1
    assert tournament.plays(practice)

    visit(practice, *SHORT)
    visit(practice, *CHECKOUT)
    events = tournament.booked(practice, NOW)
    assert events == [
        (
            "tournament_match_finished",
            {
                "format": ROUND_ROBIN,
                "game": 101,
                "matches": 3,
                "match": 1,
                "round": 1,
                "stage": "round_1",
                "players": ["Kim", "Sam"],
                "winner": "Sam",
                "loser": "Kim",
                "legs": [0, 1],
                "sets": [0, 1],
                "next": ["Alex", "Kim"],
            },
        )
    ]
    assert tournament.waiting and practice.hold
    # Booked once only.
    assert tournament.booked(practice, NOW) == []
    # Darts during the pause start no new match; the result stays.
    practice.track([dart("T20")], now=NOW)
    assert practice.winner == 1 and practice.snapshot()["visit"] == []
    practice.finish_visit(now=NOW)
    assert practice.winner == 1
    assert tournament.state() == "round_2"
    snapshot = tournament.snapshot()
    assert snapshot["status"] == WAITING and snapshot["current"] is None
    assert snapshot["next"]["players"] == ["Alex", "Kim"]
    assert snapshot["last_result"]["winner"] == "Sam"
    assert snapshot["last_result"]["average"] == [3.0, 101.0]
    # The summary of the match, then the pause.
    assert snapshot["next_at"] == (NOW + timedelta(seconds=18)).isoformat()
    assert (snapshot["pause"], snapshot["summary"]) == (10, 8)

    tournament.next_match(practice, NOW)
    assert not practice.hold and practice.winner is None
    assert practice.names[:2] == ["Alex", "Kim"]
    snapshot = tournament.snapshot()
    assert snapshot["current"]["players"] == ["Alex", "Kim"]
    assert snapshot["next"]["players"] == ["Sam", "Alex"]
    assert snapshot["matches_played"] == 1 and snapshot["matches_total"] == 3

    events = play_out(tournament, practice, winner=lambda names: names.index("Alex"))
    assert [kind for kind, _ in events] == [
        "tournament_match_finished",
        "tournament_match_finished",
        "tournament_finished",
    ]
    assert events[-1][1] == {
        "format": ROUND_ROBIN,
        "game": 101,
        "matches": 3,
        "winner": "Alex",
        "runner_up": "Sam",
        "third": "Kim",
        "players": ["Alex", "Sam", "Kim"],
    }
    assert tournament.state() == FINISHED and not practice.hold
    snapshot = tournament.snapshot()
    assert snapshot["winner"] == "Alex" and snapshot["next"] is None
    assert [row["name"] for row in snapshot["standings"]] == ["Alex", "Sam", "Kim"]
    # A finished match counts like every match for the profiles.
    assert practice.profiles.players["alex"].matches_won == 2
    # The next dart plays on as a practice match.
    practice.track([dart("S1")], now=NOW)
    assert practice.winner is None


def test_the_table_ranks_by_points_then_among_the_level_players():
    """Four players: Alex beats everybody; Sam, Kim and Lea beat each other once."""
    tournament, practice = director(4, legs=2)
    beats = {
        ("Alex", "Sam"),
        ("Alex", "Kim"),
        ("Alex", "Lea"),
        ("Sam", "Kim"),
        ("Kim", "Lea"),
        ("Lea", "Sam"),
    }
    # The loser takes one leg: every winner wins 2:1.
    while tournament.tournament.status != FINISHED:
        side = 0 if tuple(practice.names[:2]) in beats else 1
        for thrower in (1 - side, side, side):
            practice.current = thrower
            win(practice)
        tournament.booked(practice, NOW)
        if tournament.waiting:
            tournament.next_match(practice, NOW)
    table = tournament.snapshot()["standings"]
    assert table[0] == {
        "position": 1,
        "name": "Alex",
        "played": 3,
        "won": 3,
        "lost": 0,
        "legs_for": 6,
        "legs_against": 3,
        "leg_difference": 3,
        "points": 6,
        "average": table[0]["average"],
    }
    # Level on points and among themselves: leg difference and average are
    # level too, so the order of the draw decides.
    assert [row["name"] for row in table[1:]] == ["Sam", "Kim", "Lea"]
    assert [row["points"] for row in table] == [6, 2, 2, 2]


def ranked(results: dict[tuple[int, int], tuple[int, int]], count: int = 4) -> list:
    """The table of a round robin with these results: legs of both players."""
    tournament = Tournament(
        format=ROUND_ROBIN,
        game="501",
        players=NAMES[:count],
        legs=3,
        sets=1,
        rules={},
    )
    for match in tournament.matches:
        one, two = match.players
        legs = results.get((one, two)) or results[(two, one)][::-1]
        match.legs = list(legs)
        match.winner = one if legs[0] > legs[1] else two
        match.points = [legs[0] * 100, legs[1] * 100]
        match.darts = [30, 30]
        match.ended = NOW.isoformat()
    return [row["name"] for row in tournament.standings()]


def test_tie_breakers_head_to_head_before_the_leg_difference():
    # Alex and Kim, Sam and Lea are level on points; the winners of their
    # matches go first, although the others have the better leg difference.
    results = {
        (0, 1): (3, 2),
        (0, 2): (3, 2),
        (0, 3): (0, 3),
        (1, 2): (0, 3),
        (1, 3): (3, 2),
        (2, 3): (3, 0),
    }
    assert ranked(results) == ["Alex", "Kim", "Sam", "Lea"]
    # Three players who beat each other in turn: the leg difference decides.
    results = {
        (0, 1): (3, 0),
        (0, 2): (3, 0),
        (0, 3): (3, 0),
        (1, 2): (3, 0),
        (2, 3): (3, 2),
        (3, 1): (3, 2),
    }
    assert ranked(results) == ["Alex", "Sam", "Lea", "Kim"]


def test_the_average_breaks_a_tie_and_players_without_darts_come_last():
    tournament = Tournament(
        format=ROUND_ROBIN, game="501", players=NAMES[:3], legs=1, sets=1, rules={}
    )
    # Everybody wins once, 1:0: level on points, among themselves and in legs.
    for match, darts in zip(tournament.matches, (15, 12, 18), strict=True):
        match.winner = match.players[0]
        match.legs, match.points, match.darts = [1, 0], [501, 400], [darts, darts]
        match.ended = NOW.isoformat()
    table = tournament.standings()
    assert [row["name"] for row in table] == ["Kim", "Alex", "Sam"]
    assert [row["average"] for row in table] == [100.11, 90.1, 81.91]
    fresh = Tournament(
        format=ROUND_ROBIN, game="cricket", players=NAMES[:3], legs=1, sets=1, rules={}
    )
    rows = fresh.standings()
    assert [row["mpr"] for row in rows] == [None] * 3
    assert [row["name"] for row in rows] == NAMES[:3]


def test_a_knockout_of_five_with_third_place():
    tournament, practice = director(5, fmt=KNOCKOUT, third_place=True)
    assert tournament.state() == "quarter_final"
    assert practice.names[:2] == ["Lea", "Max"]
    bracket = tournament.snapshot()["bracket"]
    assert [item["stage"] for item in bracket] == [
        "quarter_final",
        "semi_final",
        "final",
        "third_place",
    ]
    quarter = bracket[0]["matches"]
    assert [match["bye"] for match in quarter] == [True, False, True, True]
    assert quarter[0] == {
        "match": None,
        "round": 1,
        "stage": "quarter_final",
        "players": ["Alex", None],
        "winner": "Alex",
        "bye": True,
        "legs": [0, 0],
        "sets": [0, 0],
        "ended": None,
    }
    # The first named player of every match wins.
    events = play_out(tournament, practice)
    finished = [
        attributes for kind, attributes in events if kind == "tournament_match_finished"
    ]
    assert [(item["stage"], item["players"], item["winner"]) for item in finished] == [
        ("quarter_final", ["Lea", "Max"], "Lea"),
        ("semi_final", ["Alex", "Lea"], "Alex"),
        ("semi_final", ["Sam", "Kim"], "Sam"),
        ("third_place", ["Lea", "Kim"], "Lea"),
        ("final", ["Alex", "Sam"], "Alex"),
    ]
    assert events[-1] == (
        "tournament_finished",
        {
            "format": KNOCKOUT,
            "game": 101,
            "matches": 5,
            "winner": "Alex",
            "runner_up": "Sam",
            "third": "Lea",
            "players": NAMES[:5],
        },
    )
    snapshot = tournament.snapshot()
    assert "standings" not in snapshot
    assert snapshot["bracket"][2]["matches"][0]["winner"] == "Alex"
    assert snapshot["round"] is None and snapshot["rounds"] == 3


def test_a_knockout_without_third_place_names_no_third():
    tournament, practice = director(4, fmt=KNOCKOUT)
    events = play_out(tournament, practice)
    assert events[-1][1]["third"] is None
    assert len(tournament.snapshot()["fixtures"]) == 3


def test_cricket_tournaments_keep_marks_per_round():
    tournament, practice = director(3, game="cricket")
    assert practice.kind == "cricket"
    practice.players[0].marks = [3] * 6 + [2]
    visit(practice, "BULL")
    tournament.booked(practice, NOW)
    result = tournament.snapshot()["last_result"]
    # The bullseye closed the bull and scored: two marks with one dart.
    assert result["mpr"] == [6.0, None] and "average" not in result
    assert tournament.snapshot()["standings"][0]["mpr"] == 6.0


# -- settings, rules and draws ---------------------------------------------------


def test_the_draw_takes_the_order_or_a_seed():
    ordered, _ = director(4)
    assert ordered.tournament.players == NAMES[:4] and ordered.tournament.seed is None
    seeded, _ = director(4, seed=42)
    again, _ = director(4, seed=42)
    assert seeded.tournament.players == again.tournament.players
    assert sorted(seeded.tournament.players) == sorted(NAMES[:4])
    assert seeded.tournament.seed == 42
    with patch(
        "custom_components.homedarts.tournament._RANDOM.randint", return_value=7
    ):
        drawn, _ = director(4, random_draw=True)
    assert drawn.tournament.seed == 7 and drawn.setup.random_draw is True


def test_starting_takes_the_setup_and_the_practice_rules():
    practice = PracticeGame()
    practice.legs_to_win, practice.sets_to_win = 3, 2
    practice.double_in = True
    tournament = TournamentDirector()
    tournament.configure(players=NAMES[:3], game="cricket", format=None, pause=0)
    events = tournament.start(practice, NOW, rules={"double_out": False})
    started = events[0][1]
    assert started == {
        "format": ROUND_ROBIN,
        "game": "cricket",
        "matches": 3,
        "players": NAMES[:3],
        "start_scores": [0, 0, 0],
        "legs_to_win": 3,
        "sets_to_win": 2,
        "seed": None,
    }
    assert tournament.tournament.rules == {
        "double_out": False,
        "double_in": True,
        "bull_off": False,
        "bull_off_distance": False,
    }
    assert practice.double_out is False and practice.double_in is True
    assert tournament.due_at() is None


@pytest.mark.parametrize(
    ("players", "key", "placeholders"),
    [
        (["Alex", "Sam"], "tournament_players", {"count": "2", "min": "3", "max": "8"}),
        (NAMES + ["Zoe"], "tournament_players", {"count": "9", "min": "3", "max": "8"}),
        (["Alex", "Sam", " alex "], "duplicate_player", {"name": "alex"}),
    ],
)
def test_a_round_robin_needs_three_to_eight_different_players(
    players, key, placeholders
):
    tournament = TournamentDirector()
    practice = PracticeGame()
    with pytest.raises(ActionRefused) as error:
        tournament.start(practice, NOW, players=players)
    assert error.value.key == key
    assert error.value.placeholders == placeholders
    # Nothing changed.
    assert tournament.tournament is None and tournament.setup.players == []
    assert tournament.state() == "no_tournament"


def test_empty_names_are_dropped():
    tournament = TournamentDirector()
    tournament.start(PracticeGame(), NOW, players=["Alex", " ", "Sam", "Kim"])
    assert tournament.tournament.players == ["Alex", "Sam", "Kim"]


def test_next_match_and_stop_need_a_tournament():
    tournament = TournamentDirector()
    practice = PracticeGame()
    for action in (
        lambda: tournament.next_match(practice, NOW),
        lambda: tournament.stop(practice),
    ):
        with pytest.raises(ActionRefused) as error:
            action()
        assert error.value.key == "no_tournament"
    assert tournament.snapshot() == {
        "status": None,
        "format": None,
        "game": None,
        "players": [],
        "winner": None,
        "fixtures": [],
    }
    assert not tournament.plays(practice)


def test_the_match_being_played_cannot_be_skipped_but_set_up_again():
    tournament, practice = director(3)
    with pytest.raises(ActionRefused) as error:
        tournament.next_match(practice, NOW)
    assert error.value.key == "tournament_match_running"
    assert error.value.placeholders == {"first": "Kim", "second": "Sam"}
    # Someone chose another game: the button sets the match up again.
    practice.play(301)
    assert not tournament.plays(practice)
    visit(practice, *CHECKOUT)
    assert tournament.booked(practice, NOW) == []
    tournament.next_match(practice, NOW)
    assert tournament.plays(practice) and practice.kind == 101
    practice.set_name(0, "Somebody")
    assert not tournament.plays(practice)
    practice.set_name(0, "Kim")
    practice.set_players(3)
    assert not tournament.plays(practice)


def test_a_finished_tournament_has_no_next_match_and_stops():
    tournament, practice = director(3)
    play_out(tournament, practice)
    with pytest.raises(ActionRefused):
        tournament.next_match(practice, NOW)
    assert tournament.booked(practice, NOW) == []
    tournament.stop(practice)
    assert tournament.tournament is None and tournament.state() == "no_tournament"


def test_stopping_during_the_pause_lets_the_darts_count_again():
    tournament, practice = director(3)
    win(practice)
    tournament.booked(practice, NOW)
    assert practice.hold
    tournament.stop(practice)
    assert not practice.hold
    practice.track([dart("T20")], now=NOW)
    assert practice.winner is None


def test_the_pause_ends_after_the_last_match():
    tournament, practice = director(3, pause=30)
    assert not tournament.due(NOW + timedelta(hours=1))
    win(practice)
    tournament.booked(practice, NOW)
    assert tournament.due_at() == NOW + timedelta(seconds=38)
    assert not tournament.due(NOW + timedelta(seconds=37))
    assert tournament.due(NOW + timedelta(seconds=38))
    # Without a summary, the pause begins with the end of the match.
    tournament.configure(summary=0)
    assert tournament.due_at() == NOW + timedelta(seconds=30)
    tournament.configure(pause=0)
    assert tournament.due_at() is None and not tournament.due(NOW + timedelta(hours=1))
    assert tournament.snapshot()["next_at"] is None


# -- storage -------------------------------------------------------------------------


def stored(tournament: TournamentDirector) -> dict:
    return json.loads(json.dumps(tournament.stored()))


def test_a_tournament_survives_a_restart_at_every_stage():
    tournament, practice = director(5, fmt=KNOCKOUT, third_place=True, seed=3)
    while True:
        restored = TournamentDirector()
        restored.restore(stored(tournament))
        assert restored.stored() == tournament.stored()
        assert restored.snapshot() == tournament.snapshot()
        assert restored.state() == tournament.state()
        if tournament.tournament.status == FINISHED:
            break
        practice.current = 0
        win(practice)
        tournament.booked(practice, NOW)
        restored = TournamentDirector()
        restored.restore(stored(tournament))
        assert restored.waiting == tournament.waiting
        assert restored.snapshot() == tournament.snapshot()
        if tournament.waiting:
            tournament.next_match(practice, NOW)


def test_restore_keeps_the_setup_and_ignores_what_it_does_not_know():
    tournament = TournamentDirector()
    tournament.restore(
        {
            "setup": {
                "format": "swiss",
                "game": "killer",
                "players": ["Alex", 7, " ", "B" * 30, *NAMES],
                "third_place": "yes",
                "random_draw": True,
                "pause": 9999,
                "summary": 61,
                # There is no single group, and at most four of a group go on.
                "groups": 1,
                "advance": 5,
            }
        }
    )
    assert tournament.setup == TournamentSetup(
        players=["Alex", "B" * 20, *NAMES], random_draw=True
    )
    for saved, kept in (
        ({"groups": 9, "advance": "2"}, (0, 2)),
        ({"groups": True, "advance": 0}, (0, 2)),
        ({"groups": 8, "advance": 4}, (8, 4)),
        ({"groups": 2, "advance": 1}, (2, 1)),
    ):
        tournament.restore({"setup": saved})
        assert (tournament.setup.groups, tournament.setup.advance) == kept
    # 32 players at most.
    tournament.restore({"setup": {"players": [f"P{index}" for index in range(40)]}})
    assert len(tournament.setup.players) == MAX_ENTRANTS
    assert tournament.tournament is None
    for saved in (None, [], {"setup": None, "tournament": "x"}):
        tournament.restore(saved)
        assert tournament.setup == TournamentSetup() and tournament.tournament is None


@pytest.mark.parametrize(
    "change",
    [
        {"format": "swiss"},
        {"game": "killer"},
        {"players": "Alex"},
        {"players": ["Alex", "Sam"]},
        {"players": ["Alex", "Sam", " "]},
    ],
)
def test_a_broken_tournament_is_dropped(change):
    tournament, _ = director(3)
    tournament.restore(
        {
            **stored(tournament),
            "tournament": {**stored(tournament)["tournament"], **change},
        }
    )
    assert tournament.tournament is None


def test_restore_replays_the_results_as_far_as_they_fit():
    tournament, practice = director(4, fmt=KNOCKOUT)
    win(practice)
    tournament.booked(practice, NOW)
    tournament.next_match(practice, NOW)
    win(practice)
    tournament.booked(practice, NOW)
    saved = stored(tournament)["tournament"]
    matches = saved["matches"]

    def restored(**changes) -> Tournament:
        return Tournament.restored({**saved, **changes})

    assert restored().status == WAITING
    assert (
        restored(matches=None).matches
        == Tournament.restored({**saved, "matches": []}).matches
    )
    assert restored(status=PLAYING).status == PLAYING
    # A result that does not fit ends the replay; later results are dropped.
    for broken in (
        {**matches[0], "players": [1, 2]},
        {**matches[0], "winner": 5},
        {**matches[0], "ended": None},
        {**matches[0], "ended": "yesterday"},
        "match",
    ):
        again = restored(matches=[broken, *matches[1:]])
        assert again.last_played() is None
        assert again.status == PLAYING
    # Results of a match not yet known are dropped too.
    final = restored(
        matches=[
            matches[0],
            {**matches[1], "winner": None},
            {**matches[2], "winner": 0, "players": [0, None]},
        ]
    )
    assert final.matches[2].winner is None
    # Broken numbers keep their defaults; unknown rules, seeds and times are dropped.
    odd = restored(
        matches=[{**matches[0], "legs": [1, -1], "darts": "many"}, *matches[1:]],
        rules="none",
        seed="7",
        started=5,
        legs_to_win=99,
    )
    assert (
        odd.matches[0].legs == [0, 0] and odd.matches[0].points == matches[0]["points"]
    )
    assert odd.rules["double_out"] is True and odd.seed is None and odd.started is None
    assert odd.legs_to_win == 1
    # More results than matches.
    assert restored(matches=[*matches, *matches]).last_played() == 1


def test_a_finished_tournament_restores_its_end():
    tournament, practice = director(3)
    play_out(tournament, practice)
    saved = stored(tournament)["tournament"]
    assert Tournament.restored(saved).ended == NOW.isoformat()
    assert Tournament.restored({**saved, "ended": 3}).ended is None
    assert Tournament.restored({**saved, "status": PLAYING}).status == FINISHED


def test_byes_in_the_stored_matches_are_kept():
    tournament, _ = director(3, fmt=KNOCKOUT)
    saved = stored(tournament)["tournament"]
    restored = Tournament.restored(saved)
    assert restored.matches[0].bye and restored.matches[0].winner == 0
    assert restored.matches[-1].players == [0, None]


def test_the_sensor_states_cover_every_stage():
    stages = {"no_tournament", FINISHED}
    for count in range(MIN_ENTRANTS, MAX_ENTRANTS + 1):
        stages |= {match.stage for match in knockout(count, third_place=True)}
        stages |= {match.stage for match in double_knockout(count)}
    for count in range(MIN_ENTRANTS, MAX_ROUND_ROBIN + 1):
        stages |= {match.stage for match in round_robin(count)}
    assert stages == set(STATES)
    assert len(STATES) == len(set(STATES))


@given(
    data=st.data(),
    fmt=st.sampled_from([ROUND_ROBIN, KNOCKOUT]),
    third_place=st.booleans(),
    outcomes=st.lists(st.booleans(), min_size=32, max_size=32),
)
def test_every_tournament_ends_with_every_match_played(
    data, fmt, third_place, outcomes
):
    count = data.draw(
        st.integers(
            MIN_ENTRANTS, MAX_ROUND_ROBIN if fmt == ROUND_ROBIN else MAX_ENTRANTS
        )
    )
    tournament, practice = director(count, fmt=fmt, third_place=third_place)
    choices = iter(outcomes)
    events = play_out(tournament, practice, winner=lambda names: int(next(choices)))
    finished = [kind for kind, _ in events].count("tournament_match_finished")
    expected = count * (count - 1) // 2 if fmt == ROUND_ROBIN else count - 1
    expected += int(fmt == KNOCKOUT and third_place and count >= 4)
    assert finished == expected == tournament.snapshot()["matches_total"]
    assert all(match.winner is not None for match in tournament.tournament.matches)
    podium = tournament.tournament.podium()
    assert podium[0] == tournament.snapshot()["winner"]
    assert len(set(filter(None, podium))) == len(list(filter(None, podium)))


def test_a_match_knows_its_loser():
    match = Match(round=1, stage="round_1", players=[3, 5])
    assert match.loser is None and match.ready and not match.played
    match.winner = 5
    assert match.loser == 3 and match.played and not match.ready


def test_the_practice_game_is_free_with_a_result_or_without_a_game():
    practice = PracticeGame()
    tournament = TournamentDirector()
    assert tournament.free(practice)
    practice.play(501)
    assert not tournament.free(practice)
    practice.winner = 0
    assert tournament.free(practice)
    practice.play("doubles")
    assert not tournament.free(practice)


def test_start_scores_give_a_handicap_and_stay_with_their_players():
    tournament, practice = director(3, game="501", start_scores=[0, 301])
    assert tournament.tournament.starts == [0, 301, 0]
    # Kim against Sam: Sam starts from 301.
    assert [player.remaining for player in practice.players] == [501, 301]
    assert practice.starts == [0, 301, 0, 0]
    snapshot = tournament.snapshot()
    assert snapshot["start_scores"] == [0, 301, 0]
    # A random draw keeps every player's start score.
    drawn, practice = director(4, game="501", start_scores=[0, 301, 0, 701], seed=5)
    starts = dict(zip(drawn.tournament.players, drawn.tournament.starts, strict=True))
    assert starts == {"Alex": 0, "Sam": 301, "Kim": 0, "Lea": 701}
    # Storage keeps them; broken ones play the game's start score.
    saved = stored(drawn)["tournament"]
    assert Tournament.restored(saved).starts == drawn.tournament.starts
    assert Tournament.restored({**saved, "starts": [1, "x", 301]}).starts == [
        0,
        0,
        301,
        0,
    ]
    assert Tournament.restored({**saved, "starts": None}).starts == [0, 0, 0, 0]


def test_cricket_variants_play_tournaments_too():
    tournament, practice = director(3, game="tactics", start_scores=[301])
    assert practice.kind == "tactics" and tournament.snapshot()["game"] == "tactics"
    # Start scores are for X01 only.
    assert tournament.tournament.starts == [0, 0, 0] and practice.starts == [0] * 4
    assert "mpr" in tournament.snapshot()["standings"][0]


def test_the_tournament_rules_win_over_a_double_out_for_the_next_leg():
    practice = PracticeGame()
    practice.play(501)
    practice.track([dart("T20")], now=NOW)
    # Switched off during the leg: it would apply from the next one.
    practice.set_option("double_out", False)
    assert practice.out_mode_next == "straight"
    tournament = TournamentDirector()
    tournament.start(practice, NOW, players=NAMES[:3], rules={"double_out": True})
    assert practice.double_out is True and practice.out_mode_next is None


# -- the settings of a match, the end of a tournament, names ----------------------


def test_a_match_with_other_settings_is_no_tournament_match():
    tournament, practice = director(3, legs=2)
    assert tournament.plays(practice)
    # Fewer legs and a start score of 2: Kim wins that match with D1.
    practice.set_format(legs=1)
    practice.set_start(0, 2)
    assert not tournament.plays(practice)
    visit(practice, "D1")
    assert practice.winner == 0
    assert tournament.booked(practice, NOW) == []
    assert tournament.tournament.last_played() is None
    # The button sets the tournament match up again.
    tournament.next_match(practice, NOW)
    assert tournament.plays(practice) and practice.legs_to_win == 2
    for rule in ("double_out", "double_in", "bull_off", "bull_off_distance"):
        practice.set_option(rule, not practice.setting(rule))
        assert not tournament.plays(practice), rule
        practice.set_option(rule, not practice.setting(rule))
        assert tournament.plays(practice), rule
    practice.set_format(sets=2)
    assert not tournament.plays(practice)


def test_a_tournament_being_played_is_stopped_before_a_new_one():
    tournament, practice = director(3)
    for _ in range(2):
        with pytest.raises(ActionRefused) as error:
            tournament.start(practice, NOW, players=NAMES[3:6])
        assert error.value.key == "tournament_running"
        assert tournament.tournament.players == NAMES[:3]
        # Also during the pause.
        win(practice)
        tournament.booked(practice, NOW)
    play_out(tournament, practice)
    # A finished tournament makes way for the next one.
    tournament.start(practice, NOW, players=NAMES[3:6])
    assert tournament.tournament.status == PLAYING
    assert tournament.tournament.players == NAMES[3:6]


def test_a_finished_tournament_says_so_for_the_next_match():
    tournament, practice = director(3)
    play_out(tournament, practice)
    with pytest.raises(ActionRefused) as error:
        tournament.next_match(practice, NOW)
    assert error.value.key == "tournament_finished"


def test_the_tournament_takes_a_double_out_waiting_for_the_next_leg():
    practice = PracticeGame()
    practice.play(501)
    practice.track([dart("T20")], now=NOW)
    practice.set_option("double_out", False)
    tournament = TournamentDirector()
    tournament.start(practice, NOW, players=NAMES[:3])
    assert tournament.tournament.rules["double_out"] is False
    assert practice.double_out is False and practice.out_mode_next is None


def casual_practice() -> PracticeGame:
    """Three named players and the bot, with a handicap, legs and double in."""
    practice = PracticeGame()
    for index, name in enumerate(["Zoe", "Mia", "Leo", "Eva"]):
        practice.set_name(index, name)
    practice.set_start(1, 301)
    practice.set_bot(60)
    practice.play(501, 3)
    practice.set_format(legs=3, sets=2)
    practice.set_option("double_in", True)
    return practice


def test_the_practice_settings_come_back_after_the_tournament():
    practice = casual_practice()
    before = practice.settings()
    assert before["players"] == 3 and len(practice.players) == 4
    tournament = TournamentDirector()
    tournament.start(
        practice,
        NOW,
        players=NAMES[:3],
        game="101",
        legs=1,
        sets=1,
        rules={"double_in": False},
    )
    assert practice.bot_level == 0 and practice.names[2:] == [""] * 6
    # Storage keeps what comes back.
    copy = TournamentDirector()
    copy.restore(stored(tournament))
    assert copy.saved == before
    play_out(tournament, practice)
    # The final's result stays on the cards until the next dart ...
    assert practice.winner is not None and practice.names[:2] != before["names"][:2]
    assert practice.resume == before and tournament.saved is None
    restored = PracticeGame()
    restored.restore(json.loads(json.dumps(practice.stored())))
    assert restored.resume == before
    # ... which starts a match with the settings from before the tournament.
    practice.track([dart("T20")], now=NOW)
    assert practice.settings() == before and practice.resume is None
    assert practice.bot_seat == 3 and practice.kind == 101
    assert practice.players[0].remaining == 101 and practice.winner is None


def test_stopping_brings_the_settings_back_after_the_match_being_played():
    practice = casual_practice()
    before = practice.settings()
    tournament = TournamentDirector()
    tournament.start(practice, NOW, players=NAMES[:3], game="101", legs=2)
    playing = practice.names[:2]
    tournament.stop(practice)
    # The match being played goes on with its players.
    visit(practice, "S1")
    assert practice.names[:2] == playing and practice.resume == before
    # A deleted player does not come back with the settings.
    practice.forget("EVA")
    assert practice.resume["names"] == ["Zoe", "Mia", "Leo"] + [""] * 5
    before["names"] = ["Zoe", "Mia", "Leo"] + [""] * 5
    # A change of a setting brings the others back first.
    practice.set_format(legs=5)
    assert practice.settings() == {**before, "legs_to_win": 5}
    # A new tournament after a finished one keeps the settings from before.
    plain = {"legs": 1, "sets": 1, "rules": {"double_in": False}}
    tournament.start(practice, NOW, players=NAMES[:3], game="101", **plain)
    play_out(tournament, practice)
    tournament.start(practice, NOW, players=NAMES[3:6], game="101", **plain)
    tournament.stop(practice)
    practice.new_match()
    assert practice.settings() == {**before, "legs_to_win": 5}


def test_a_renamed_player_keeps_the_seats_of_the_practice_game():
    practice = casual_practice()
    practice.resume = practice.settings()
    # The bot plays the fourth seat, which keeps the name of who sat there.
    assert practice.rename_player("eva", "Zoe") is True
    assert practice.names[:4] == ["Zoe", "Mia", "Leo", ""]
    assert practice.resume["names"][:4] == ["Zoe", "Mia", "Leo", ""]
    # Two players of the match being played cannot become one.
    assert practice.rename_player("Mia", "zoe") is False
    assert practice.names[:3] == ["Zoe", "Mia", "Leo"]
    assert practice.rename_player("LEO", "Leon") is True
    assert practice.names[:3] == ["Zoe", "Mia", "Leon"]
    practice.resume = None
    assert practice.rename_player("Nobody", "Somebody") is True
    assert practice.names[:3] == ["Zoe", "Mia", "Leon"]


def test_stored_settings_to_come_back_to_are_checked():
    good = PracticeGame().settings()
    assert valid_settings(good) == good
    assert valid_settings({**good, "names": ["{Zoe}", "", "", ""]})["names"][0] == "Zoe"
    for broken in (
        None,
        {**good, "players": 0},
        {**good, "names": ["Zoe"]},
        {**good, "names": [1, "", "", ""]},
        {**good, "starts": [1, 0, 0, 0]},
        {**good, "starts": [0]},
        {**good, "bot_level": 10},
        {**good, "legs_to_win": 12},
        {**good, "sets_to_win": 0},
        {**good, "double_out": "yes"},
    ):
        assert valid_settings(broken) is None, broken
    practice = PracticeGame()
    practice.restore({"game": 501, "resume": {**good, "players": 9}})
    assert practice.resume is None
    tournament = TournamentDirector()
    tournament.restore({"practice": good})
    assert tournament.saved is None


def test_a_new_match_of_the_last_two_players_makes_way_in_the_pause():
    tournament, practice = director(3, pause=30)
    win(practice)
    tournament.booked(practice, NOW)
    assert tournament.waiting and tournament.free(practice)
    # A setting changed in the pause starts that match anew: no darts yet.
    practice.set_format(legs=2)
    assert practice.winner is None and tournament.free(practice)
    # With its first dart, it is played to its end first.
    practice.track([dart("S1")], now=NOW)
    assert not tournament.free(practice)
    practice.track([], now=NOW)
    practice.new_match()
    assert tournament.free(practice)
    # Other players or another game are not the tournament's.
    practice.set_name(0, "Somebody")
    assert not tournament.free(practice)
    practice.play("cricket")
    assert not tournament.free(practice)
    # While a match is being played, nothing makes way.
    tournament.next_match(practice, NOW)
    practice.new_match()
    assert not tournament.free(practice)


def test_a_match_with_a_bull_off_dart_is_under_way():
    practice = PracticeGame()
    practice.bull_off = True
    practice.set_players(2)
    practice.play(501)
    assert practice.fresh
    practice.track([dart("S20")], [(0.0, 0.5)], now=NOW)
    assert not practice.fresh
    practice.finish_visit(now=NOW)
    practice.track([], now=NOW)
    assert practice.bulling.index == 1 and not practice.fresh


def test_a_deleted_player_leaves_the_next_tournament_but_not_one_being_played():
    practice = PracticeGame()
    practice.set_name(0, "Zoe")
    tournament = TournamentDirector()
    tournament.start(practice, NOW, players=NAMES[:3])
    with pytest.raises(ActionRefused) as error:
        tournament.forget(" sam ")
    assert error.value.key == "player_in_tournament"
    assert error.value.placeholders == {"name": "sam"}
    # A player from before the tournament does not come back after it.
    tournament.forget("ZOE")
    assert tournament.saved["names"] == [""] * 8
    tournament.stop(practice)
    tournament.forget("Sam")
    assert tournament.setup.players == ["Alex", "Kim"]
    tournament.forget("nobody")
    assert tournament.setup.players == ["Alex", "Kim"]


def test_a_renamed_player_keeps_the_name_of_a_tournament_being_played():
    practice = PracticeGame()
    for index, name in enumerate(["Zoe", "Mia", "Leo", "Eva"]):
        practice.set_name(index, name)
    tournament = TournamentDirector()
    tournament.start(practice, NOW, players=NAMES[:3], game="101")
    with pytest.raises(ActionRefused) as error:
        tournament.rename(" sam ", "Samuel")
    assert error.value.key == "player_in_tournament"
    # The players of the settings from before come back with their new names.
    tournament.rename("ZOE", "Zoey")
    tournament.rename("Mia", "zoey")
    assert tournament.saved["names"] == ["zoey", "", "Leo", "Eva"] + [""] * 4
    assert tournament.tournament.players == NAMES[:3]
    play_out(tournament, practice)
    # A finished tournament and the setup of the next one take the new name.
    tournament.setup.players = ["Alex", "Sam", "Kim", "SAMMY"]
    tournament.rename("Sam", "Samuel")
    assert tournament.tournament.players == ["Alex", "Samuel", "Kim"]
    tournament.rename("Sammy", "Samuel")
    assert tournament.setup.players == ["Alex", "Samuel", "Kim"]


def test_player_names_never_carry_template_characters():
    with pytest.raises(ActionRefused) as error:
        TournamentDirector().start(
            PracticeGame(), NOW, players=["Alex", "{{ 6*7 }}", "Kim"]
        )
    assert error.value.key == "invalid_player_name"
    assert split_players("Al{ex},\r\n;Kim") == ["Al{ex}", "Kim"]
    assert parse_players("Al{ex}, 50%, #1, {%}") == ["Alex", "50", "1"]
    assert TournamentSetup.restored({"players": ["{%}", "Sam#"]}).players == ["Sam"]
    saved = stored(director(3)[0])["tournament"]
    assert Tournament.restored({**saved, "players": ["{}", "Sam", "Kim"]}) is None
