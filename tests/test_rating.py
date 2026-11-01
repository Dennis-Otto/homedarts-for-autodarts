"""The rating of the players and the fair start scores from their averages."""

import json
from operator import itemgetter
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.homedarts.games import BoardGames
from custom_components.homedarts.practice import PracticeGame
from custom_components.homedarts.profiles import Profile, Profiles
from custom_components.homedarts.rating import (
    K_SETTLED,
    RECENT_LEGS,
    START_RATING,
    expected,
    fair_starts,
    k_factor,
    rating_changes,
    team_averages,
)

from .local_helpers import NOW, board, dart
from .test_games import D20, Reports, match, play, visit
from .test_teams_and_handicap import teams

FAIR_STARTS = json.loads(
    (Path(__file__).parent / "fixtures" / "fair_starts.json").read_text("utf-8")
)
NEW = (START_RATING, 0)


def game(kind: int | str, *names: str, legs: int = 1, bot: int = 0) -> PracticeGame:
    practice = PracticeGame()
    practice.set_players(len(names))
    for index, name in enumerate(names):
        practice.set_name(index, name)
    practice.set_format(legs=legs)
    if bot:
        practice.set_bot(bot)
    practice.play(kind)
    return practice


def checkout(practice: PracticeGame) -> list[tuple[str, dict]]:
    """The player at the board checks out 40; the visit isn't booked yet."""
    practice.players[practice.current].remaining = 40
    return practice.track([dart("D20")], now=NOW)


def games_of(**averages: int) -> BoardGames:
    """A board whose players have the 3-dart average given, over one leg each."""
    games = BoardGames(Reports(), NOW)
    for name, average in averages.items():
        games.practice.profiles.leg(
            501, [{"name": name, "points": average * 10, "darts": 30}], NOW
        )
    return games


def ratings(practice: PracticeGame) -> dict[str, float | None]:
    return {
        player["name"]: player["rating"]
        for player in practice.profiles.snapshot()["players"]
    }


def match_won(events: list[tuple[str, dict]]) -> dict:
    return next(payload for kind, payload in events if kind == "match_won")


# -- the sums ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("matches", "factor"),
    [(0, 40), (9, 40), (10, 24), (29, 24), (30, K_SETTLED), (500, K_SETTLED)],
)
def test_a_rating_moves_less_the_more_matches_a_player_has(matches, factor):
    assert k_factor(matches) == factor


def test_the_expected_share_follows_the_difference_of_the_ratings():
    assert expected(1000, 1000) == 0.5
    assert expected(1400, 1000) == pytest.approx(10 / 11)
    assert expected(1000, 1400) == pytest.approx(1 / 11)


def test_two_new_players_exchange_half_of_the_factor():
    assert rating_changes({"a": NEW, "b": NEW}, ["a"], ["b"]) == {"a": 20.0, "b": -20.0}


def test_beating_a_stronger_player_earns_more_than_beating_a_weaker_one():
    standing = {"weak": (900.0, 50), "strong": (1300.0, 50)}
    upset = rating_changes(standing, ["weak"], ["strong"])
    expected_win = rating_changes(standing, ["strong"], ["weak"])
    assert upset == {"weak": 14.5, "strong": -14.5}
    assert expected_win == {"strong": 1.5, "weak": -1.5}


def test_each_player_moves_at_their_own_pace():
    changes = rating_changes({"new": NEW, "old": (START_RATING, 40)}, ["new"], ["old"])
    assert changes == {"new": 20.0, "old": -8.0}


def test_partners_split_what_their_team_wins_or_loses():
    standing = dict.fromkeys("abcd", NEW)
    assert rating_changes(standing, ["a", "c"], ["b", "d"]) == {
        "a": 10.0,
        "c": 10.0,
        "b": -10.0,
        "d": -10.0,
    }


def test_the_losers_of_a_match_of_several_share_what_the_winner_gains():
    standing = dict.fromkeys("abc", NEW)
    assert rating_changes(standing, ["a"], ["b", "c"]) == {
        "a": 20.0,
        "b": -10.0,
        "c": -10.0,
    }


@pytest.mark.parametrize(("winners", "losers"), [([], ["a"]), (["a"], []), ([], [])])
def test_without_a_winner_or_a_loser_nothing_changes(winners, losers):
    assert rating_changes({"a": NEW}, winners, losers) == {}


@pytest.mark.parametrize("case", FAIR_STARTS, ids=lambda case: case["why"])
def test_fair_starts_as_the_card_works_them_out(case):
    assert fair_starts(case["game"], case["averages"]) == case["starts"]


def test_the_average_of_a_team_goes_by_the_partners_it_knows():
    assert team_averages([80, 40, 60, None]) == [70, 40]
    assert team_averages([None, 40, None, 50]) == [None, 45]


# -- a match ----------------------------------------------------------------------


def test_a_won_match_moves_the_ratings_of_both_players():
    practice = game(501, "Alex", "Lea")
    events = checkout(practice)
    assert match_won(events)["rating_changes"] == [
        {"name": "Alex", "rating": 1020.0, "change": 20.0},
        {"name": "Lea", "rating": 980.0, "change": -20.0},
    ]
    # Announced with the winning dart, booked once the visit ends.
    assert ratings(practice) == {}
    practice.finish_visit(now=NOW)
    assert ratings(practice) == {"Alex": 1020.0, "Lea": 980.0}
    assert practice.profiles.players["alex"].rated_matches == 1
    summary = {
        player["name"]: player for player in practice.profiles.snapshot()["players"]
    }
    assert summary["Lea"]["rated_matches"] == 1


def test_a_leg_that_does_not_end_the_match_moves_no_rating():
    practice = game(501, "Alex", "Lea", legs=2)
    assert "match_won" not in [kind for kind, _ in checkout(practice)]
    practice.finish_visit(now=NOW)
    assert ratings(practice) == {"Alex": None, "Lea": None}


def test_a_cricket_match_counts_too():
    practice = game("cricket", "Alex", "Lea")
    practice.players[0].marks = [3, 3, 3, 3, 3, 3, 2]
    practice.players[0].points = 10
    events = practice.track([dart("BULL")], now=NOW)
    assert match_won(events)["rating_changes"][0]["change"] == 20.0
    practice.finish_visit(now=NOW)
    assert ratings(practice) == {"Alex": 1020.0, "Lea": 980.0}


def test_a_team_match_splits_the_change_between_the_partners():
    practice = teams(301)
    events = checkout(practice)
    assert [entry["change"] for entry in match_won(events)["rating_changes"]] == [
        10.0,
        -10.0,
        10.0,
        -10.0,
    ]
    practice.finish_visit(now=NOW)
    assert ratings(practice) == {
        "Alex": 1010.0,
        "Kim": 1010.0,
        "Sam": 990.0,
        "Lea": 990.0,
    }


def test_a_party_game_moves_no_rating():
    practice = game("shanghai", "Alex", "Lea")
    practice.profiles.match(
        "shanghai",
        [{"name": "Alex"}, {"name": "Lea"}],
        0,
        1,
        1,
        now=NOW,
        rated=practice._rated(),
    )
    assert ratings(practice) == {"Alex": None, "Lea": None}


def test_a_match_with_the_bot_moves_no_rating():
    practice = game(501, "Alex", bot=60)
    events = checkout(practice)
    assert match_won(events)["rating_changes"] == []
    practice.finish_visit(now=NOW)
    assert ratings(practice) == {"Alex": None}


def test_a_match_with_a_guest_moves_no_rating():
    practice = game(501, "Alex", "")
    events = checkout(practice)
    assert match_won(events)["rating_changes"] == []
    practice.finish_visit(now=NOW)
    assert ratings(practice) == {"Alex": None}


def test_a_handicap_match_moves_no_rating():
    practice = PracticeGame()
    practice.set_players(2)
    practice.set_name(0, "Alex")
    practice.set_name(1, "Lea")
    practice.set_start(1, 301)
    practice.play(501)
    events = checkout(practice)
    assert match_won(events)["rating_changes"] == []
    practice.finish_visit(now=NOW)
    assert ratings(practice) == {"Alex": None, "Lea": None}


def test_one_name_in_two_seats_plays_nobody():
    profiles = Profiles()
    assert profiles.changes(["Alex", "alex"], [0]) == []


def test_a_player_in_two_seats_changes_once():
    profiles = Profiles()
    assert profiles.changes(["Alex", "alex", "Lea"], [1]) == [
        {"name": "Alex", "rating": 1020.0, "change": 20.0},
        {"name": "Lea", "rating": 980.0, "change": -20.0},
    ]


def test_a_change_names_a_known_player_as_the_profile_spells_them():
    profiles = Profiles()
    profiles.players["alex"] = Profile(name="Alex", rating=1100.0, rated_matches=40)
    assert profiles.changes(["ALEX", None, "Lea"], [2]) == [
        {"name": "Alex", "rating": 1089.8, "change": -10.2},
        {"name": "Lea", "rating": 1025.6, "change": 25.6},
    ]


def test_undoing_the_deciding_visit_takes_the_change_back():
    games = match("Alex", "Lea")
    games.practice.players[0].remaining = 40
    visit(games, D20)
    assert ratings(games.practice) == {"Alex": 1020.0, "Lea": 980.0}
    games.start_game(501)
    play(games, board())
    games.practice.players[0].remaining = 40
    visit(games, D20)
    assert ratings(games.practice) == {"Alex": 1037.7, "Lea": 962.3}
    games.undo_visit(NOW)
    assert ratings(games.practice) == {"Alex": 1020.0, "Lea": 980.0}
    players = games.practice.profiles.players
    assert (players["alex"].rated_matches, players["lea"].rated_matches) == (1, 1)
    # The same win counts once when its visit ends again.
    games.next_player(NOW)
    play(games, board())
    assert ratings(games.practice) == {"Alex": 1037.7, "Lea": 962.3}
    players = games.practice.profiles.players
    assert (players["alex"].rated_matches, players["lea"].rated_matches) == (2, 2)


@given(
    st.lists(
        st.tuples(
            st.sampled_from("abcdef"),
            st.floats(min_value=100, max_value=3000),
            st.integers(min_value=0, max_value=60),
        ),
        min_size=2,
        max_size=4,
        unique_by=lambda player: player[0],
    ),
    st.randoms(use_true_random=False),
)
def test_a_change_does_not_depend_on_the_seats(players, random):
    profiles = Profiles()
    for name, rating, matches in players:
        profiles.players[name] = Profile(name, rating=rating, rated_matches=matches)
    names = [name for name, _, _ in players]
    winner = names[0]
    before = profiles.changes(names, [0])
    random.shuffle(names)
    after = profiles.changes(names, [names.index(winner)])
    by_name = itemgetter("name")
    assert sorted(before, key=by_name) == sorted(after, key=by_name)
    # What the winner gains is never negative, what a loser gets never positive.
    for entry in after:
        assert (entry["change"] >= 0) == (entry["name"] == winner) or not entry[
            "change"
        ]


# -- the profile ------------------------------------------------------------------


def test_a_profile_from_before_the_ratings_starts_like_a_new_player():
    profile = Profile.restored({"name": "Alex", "x01_points": 600, "x01_darts": 30})
    assert profile is not None
    assert (profile.rating, profile.rated_matches, profile.recent_legs) == (
        START_RATING,
        0,
        [],
    )
    assert profile.summary()["rating"] is None
    # No leg since the update: a fair start goes by the lifetime average.
    assert profile.recent_average() == 60.0


def test_ratings_and_recent_legs_are_kept_and_checked():
    profiles = Profiles()
    profiles.leg(
        501,
        [{"name": "Alex", "points": 501, "darts": 18}, {"name": "Lea", "darts": 0}],
        NOW,
    )
    profiles.players["alex"].rating = 1033.3
    profiles.players["alex"].rated_matches = 7
    copy = Profiles()
    copy.restore(json.loads(json.dumps(profiles.stored())))
    alex = copy.players["alex"]
    assert (alex.rating, alex.rated_matches, alex.recent_legs) == (
        1033.3,
        7,
        [[501, 18]],
    )
    assert alex.summary()["rating"] == 1033.3
    assert alex.summary()["recent_average"] == 83.5
    # Lea threw no darts: no recent leg, and no average yet.
    assert copy.players["lea"].recent_legs == []
    assert copy.recent_average("lea") is None
    assert copy.recent_average("nobody") is None
    assert copy.recent_average("ALEX") == 83.5


@pytest.mark.parametrize(
    "rating", ["1100", True, None, float("nan"), float("inf"), [1100]]
)
def test_a_broken_rating_starts_over(rating):
    profile = Profile.restored({"name": "Alex", "rating": rating})
    assert profile is not None
    assert profile.rating == START_RATING


def test_a_stored_whole_number_is_a_rating():
    profile = Profile.restored({"name": "Alex", "rating": 1100})
    assert profile is not None
    assert profile.rating == 1100.0
    assert isinstance(profile.rating, float)


@pytest.mark.parametrize(
    "leg", ["501,18", [501], [501, 18, 1], [501, 0], [-1, 18], ["501", 18], [501, True]]
)
def test_a_broken_recent_leg_goes(leg):
    profile = Profile.restored({"name": "Alex", "recent_legs": [leg, [100, 9]]})
    assert profile is not None
    assert profile.recent_legs == [[100, 9]]


def test_stored_recent_legs_that_are_no_list_go():
    profile = Profile.restored({"name": "Alex", "recent_legs": "many"})
    assert profile is not None
    assert profile.recent_legs == []


def test_stored_recent_legs_stay_within_the_limit():
    legs = [[index, 9] for index in range(RECENT_LEGS + 5)]
    profile = Profile.restored({"name": "Alex", "recent_legs": legs})
    assert profile is not None
    assert profile.recent_legs == legs[:RECENT_LEGS]


def test_the_recent_average_goes_by_the_last_30_legs_the_newest_first():
    profiles = Profiles()
    # An old form of 30 points per visit, then 30 legs of 60.
    profiles.leg(501, [{"name": "Alex", "points": 300, "darts": 30}], NOW)
    for _ in range(RECENT_LEGS):
        profiles.leg(501, [{"name": "Alex", "points": 600, "darts": 30}], NOW)
    profile = profiles.players["alex"]
    assert len(profile.recent_legs) == RECENT_LEGS
    assert profile.recent_average() == 60.0
    assert profile.summary()["average"] == pytest.approx(59.03, abs=0.01)
    profiles.leg(501, [{"name": "Alex", "points": 150, "darts": 30}], NOW)
    assert profile.recent_legs[0] == [150, 30]


def test_a_cricket_leg_is_no_recent_leg():
    profiles = Profiles()
    profiles.leg("cricket", [{"name": "Alex", "darts": 30, "marks": 40}], NOW)
    assert profiles.players["alex"].recent_legs == []


@pytest.mark.parametrize("join", [Profile.merge, Profile.absorb])
def test_two_profiles_of_one_player_weigh_their_ratings_by_their_matches(join):
    mine = Profile(
        "Alex",
        rating=1100.0,
        rated_matches=30,
        recent_legs=[[300, 15]],
        last_played="2026-10-01T20:00:00+00:00",
    )
    other = Profile(
        "alex",
        rating=900.0,
        rated_matches=10,
        recent_legs=[[100, 15]],
        last_played="2026-10-02T20:00:00+00:00",
    )
    join(mine, other)
    assert (mine.rating, mine.rated_matches) == (1050.0, 40)
    # The legs of the profile that played last come first.
    assert mine.recent_legs == [[100, 15], [300, 15]]


@pytest.mark.parametrize("join", [Profile.merge, Profile.absorb])
def test_two_profiles_keep_the_newer_legs_of_the_first_and_stay_within_the_limit(join):
    legs = [[index, 9] for index in range(RECENT_LEGS)]
    mine = Profile("Alex", recent_legs=legs, last_played="2026-10-02T20:00:00+00:00")
    other = Profile("alex", recent_legs=[[1, 1]], last_played=None)
    join(mine, other)
    assert mine.recent_legs == legs
    assert (mine.rating, mine.rated_matches) == (START_RATING, 0)


# -- starting a game --------------------------------------------------------------


def test_a_fair_start_scales_two_players():
    games = games_of(Alex=60, Sam=30)
    games.start_game(501, names=["Alex", "Sam"], fair_start=True)
    assert games.practice.lineup()["start_scores"] == [501, 250]
    assert [player.remaining for player in games.practice.players] == [501, 250]


def test_a_fair_start_scales_four_players():
    games = games_of(Alex=90, Sam=60, Kim=45, Lea=30)
    games.start_game(701, names=["Alex", "Sam", "Kim", "Lea"], fair_start=True)
    assert games.practice.lineup()["start_scores"] == [701, 470, 350, 230]


def test_a_player_without_history_keeps_the_games_score():
    games = games_of(Alex=60, Sam=30)
    games.start_game(501, names=["New", "Sam", "Alex"], fair_start=True)
    assert games.practice.lineup()["start_scores"] == [501, 250, 501]


def test_a_fair_start_of_players_without_history_leaves_everybody_at_the_games_score():
    games = games_of()
    games.start_game(501, names=["Alex", "Sam"], fair_start=True)
    assert games.practice.lineup()["start_scores"] == [501, 501]


def test_a_fair_start_replaces_the_start_scores_set_before():
    games = games_of(Alex=60)
    games.start_game(501, names=["Alex", "Sam"], start_scores=[301, 701])
    games.start_game(501, names=["Alex", "Sam"], fair_start=True)
    assert games.practice.lineup()["start_scores"] == [501, 501]


def test_a_team_plays_from_the_average_of_its_partners():
    games = games_of(Alex=80, Sam=30, Kim=40, Lea=50)
    games.start_game(
        501, names=["Alex", "Sam", "Kim", "Lea"], teams=True, fair_start=True
    )
    # Alex and Kim average 60, Sam and Lea 40.
    assert games.practice.lineup()["start_scores"] == [501, 330, 501, 330]


def test_the_bot_counts_by_its_level_and_keeps_the_score_when_stronger():
    games = games_of(Alex=30)
    games.start_game(501, names=["Alex"], bot_level=60, fair_start=True)
    assert games.practice.lineup()["start_scores"] == [250, 501]


def test_the_bot_starts_lower_when_it_is_weaker():
    games = games_of(Alex=60)
    games.start_game(501, names=["Alex"], bot_level=30, fair_start=True)
    assert games.practice.lineup()["start_scores"] == [501, 250]


def test_the_level_the_bot_has_counts_when_the_action_names_none():
    games = games_of(Alex=30)
    games.practice.bot_level = 60
    games.start_game(501, names=["Alex"], fair_start=True)
    assert games.practice.lineup()["start_scores"] == [250, 501]


def test_a_team_with_the_bot_counts_it_as_a_partner():
    games = games_of(Alex=60, Sam=20, Kim=60)
    games.start_game(
        501, names=["Alex", "Sam", "Kim"], teams=True, bot_level=40, fair_start=True
    )
    # Sam and the bot average 30 against the 60 of Alex and Kim.
    assert games.practice.lineup()["start_scores"] == [501, 250, 501, 250]


def test_the_players_of_the_board_count_when_the_action_names_none():
    games = games_of(Alex=60, Sam=30)
    games.practice.set_name(0, "Alex")
    games.practice.set_name(1, "Sam")
    games.practice.set_players(2)
    games.start_game(501, fair_start=True)
    assert games.practice.lineup()["start_scores"] == [501, 250]


def six_players_of_a_party_game(games: BoardGames) -> None:
    """The board still has the players of a party game, who are more than X01 seats."""
    for index, name in enumerate(("Alex", "Sam", "Kim", "Robin", "Max", "Lea")):
        games.practice.set_name(index, name)
    games.practice.set_players(6)


def test_players_who_get_no_seat_count_for_nobody():
    games = games_of(Alex=40, Sam=30, Kim=30, Robin=20, Max=80, Lea=25)
    six_players_of_a_party_game(games)
    games.start_game(501, fair_start=True)
    assert games.practice.lineup()["start_scores"] == [501, 380, 380, 250]


def test_players_who_get_no_seat_leave_the_teams_as_they_are():
    games = games_of(Alex=40, Sam=30, Kim=40, Robin=30, Max=80, Lea=25)
    six_players_of_a_party_game(games)
    games.start_game(501, teams=True, fair_start=True)
    assert games.practice.lineup()["start_scores"] == [501, 380, 501, 380]


def test_the_bot_takes_a_seat_from_players_who_rest():
    games = games_of(Alex=40, Sam=30, Kim=30, Robin=80)
    six_players_of_a_party_game(games)
    games.start_game(501, bot_level=20, fair_start=True)
    assert games.practice.lineup()["start_scores"] == [501, 380, 380, 250]


def test_a_game_without_start_scores_ignores_a_fair_start():
    games = games_of(Alex=60, Sam=30)
    games.start_game("cricket", names=["Alex", "Sam"], fair_start=True)
    assert games.practice.starts == [0, 0, 0, 0]
