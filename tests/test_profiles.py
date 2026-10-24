"""Player profiles, the match history and head-to-head records."""

from datetime import timedelta

import pytest
from homeassistant.core import split_entity_id, valid_entity_id
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.homedarts.practice import PracticeGame
from custom_components.homedarts.profiles import (
    MATCH_HISTORY,
    Profile,
    Profiles,
    _person,
)

from .local_helpers import NOW, throw
from .test_teams_and_handicap import teams


def named(game: int | str, *names: str, legs: int = 1) -> PracticeGame:
    practice = PracticeGame()
    practice.set_players(len(names))
    for index, name in enumerate(names):
        practice.set_name(index, name)
    practice.set_format(legs=legs)
    practice.play(game)
    return practice


def win_leg(practice: PracticeGame) -> None:
    """The player at the board checks out 40 with a double 20."""
    practice.players[practice.current].remaining = 40
    throw(practice, "D20")


def by_name(practice: PracticeGame) -> dict[str, dict]:
    return {
        player["name"]: player for player in practice.profiles.snapshot()["players"]
    }


def test_a_match_fills_the_profiles_the_history_and_head_to_head():
    practice = named(501, "Alex", "Lea", legs=2)
    throw(practice, "T20", "T20", "T20")
    win_leg(practice)  # Lea wins the first leg.
    win_leg(practice)  # Lea starts the second leg... and wins it too.
    players = by_name(practice)
    assert practice.winner == 1
    assert (players["Lea"]["legs_won"], players["Lea"]["matches_won"]) == (2, 1)
    assert (players["Alex"]["legs_played"], players["Alex"]["matches_played"]) == (2, 1)
    assert (
        players["Alex"]["highest_visit"] == 180 and players["Alex"]["average"] == 180.0
    )
    assert players["Lea"]["fewest_darts"] == {"501": 1}
    assert players["Lea"]["highest_checkout"] == 40
    assert players["Lea"]["checkout_rate"] == 100.0
    snapshot = practice.profiles.snapshot()
    assert snapshot["head_to_head"] == [{"players": ["Alex", "Lea"], "wins": [0, 1]}]
    match = snapshot["matches"][0]
    assert (match["game"], match["winner"], match["legs_to_win"]) == (501, 2, 2)
    assert [(entry["name"], entry["sets"]) for entry in match["players"]] == [
        ("Alex", 0),
        ("Lea", 1),
    ]


def test_names_ignore_case_and_unnamed_players_have_no_profile():
    practice = named(301, "Dennis", "")
    win_leg(practice)
    assert list(by_name(practice)) == ["Dennis"]
    again = named(301, "  dennis ", "Lea")
    again.profiles = practice.profiles
    win_leg(again)
    players = by_name(again)
    assert players["Dennis"]["matches_won"] == 2 and "Lea" in players
    # A match against an unnamed player has no head-to-head record.
    assert again.profiles.snapshot()["head_to_head"] == [
        {"players": ["Dennis", "Lea"], "wins": [1, 0]}
    ]
    assert practice.profiles.snapshot()["matches"][1]["players"][1]["name"] is None


def test_cricket_and_party_legs_count_and_keep_their_numbers():
    practice = named("cricket", "Alex", "Sam")
    practice.players[0].marks = [3, 3, 3, 3, 3, 3, 2]
    practice.players[0].marks_hit = 20
    practice.players[0].darts = 21
    throw(practice, "BULL")
    alex = by_name(practice)["Alex"]
    assert alex["mpr"] == round(22 * 3 / 22, 2) and alex["best_mpr"] == 3.0
    # The match counts only the bullseye thrown in it: two marks with one dart.
    assert practice.profiles.snapshot()["matches"][0]["players"][0]["mpr"] == 6.0
    shanghai = named("shanghai", "Kim")
    for number in range(1, 8):
        throw(shanghai, f"S{number}")
    kim = by_name(shanghai)["Kim"]
    assert (kim["legs_played"], kim["legs_won"], kim["average"]) == (1, 1, None)


def test_profiles_can_be_deleted_and_survive_a_restart():
    practice = named(501, "Alex", "Lea")
    win_leg(practice)
    assert practice.profiles.delete("LEA") is True
    assert practice.profiles.delete("Nobody") is False
    assert list(by_name(practice)) == ["Alex"]
    assert practice.profiles.snapshot()["head_to_head"] == []
    # The history keeps the match with both names.
    assert len(practice.profiles.matches) == 1
    restored = PracticeGame()
    restored.restore(practice.stored())
    assert restored.profiles.stored() == practice.profiles.stored()


def test_invalid_stored_profiles_are_dropped():
    profiles = Profiles()
    profiles.restore(
        {
            "players": [
                {"name": "Alex", "legs_played": 5, "legs_won": -1, "best_mpr": "x"},
                {"name": " "},
                {"legs_played": 3},
                "x",
                {"name": "Sam", "fewest_darts": {"501": 18, "x": 3, "301": 0}},
            ],
            "matches": [{"ended": "2026-09-26T20:00:00", "players": []}, {"ended": 1}],
            "head_to_head": {"alex\x00sam": [2, 1], "bad": [1, 1], "a\x00b": [1]},
        }
    )
    snapshot = profiles.snapshot()
    players = {player["name"]: player for player in snapshot["players"]}
    assert players["Alex"]["legs_played"] == 5 and players["Alex"]["legs_won"] == 0
    assert players["Alex"]["best_mpr"] is None
    assert players["Sam"]["fewest_darts"] == {"501": 18}
    assert len(snapshot["matches"]) == 1
    assert snapshot["head_to_head"] == [{"players": ["Alex", "Sam"], "wins": [2, 1]}]
    profiles.restore(None)
    assert profiles.snapshot()["head_to_head"]


def test_the_history_keeps_the_last_matches():
    profiles = Profiles()
    for index in range(MATCH_HISTORY + 5):
        profiles.match(501, [{"name": "A"}, {"name": "B"}], index % 2, 1, 1, now=NOW)
    assert len(profiles.matches) == MATCH_HISTORY
    assert profiles.snapshot()["head_to_head"][0]["wins"] == [13, 12]


def test_a_player_in_two_seats_plays_the_match_once_and_not_against_oneself():
    """Names kept from before every seat needed a name of its own."""
    profiles = Profiles()
    seats = [{"name": "Alex"}, {"name": "Sam"}, {"name": " alex "}]
    profiles.match(501, seats, 2, 1, 1, now=NOW)
    profiles.match(501, seats, 1, 1, 1, now=NOW)
    players = {player["name"]: player for player in profiles.snapshot()["players"]}
    assert (players["Alex"]["matches_played"], players["Alex"]["matches_won"]) == (2, 1)
    assert (players["Sam"]["matches_played"], players["Sam"]["matches_won"]) == (2, 1)
    assert profiles.snapshot()["head_to_head"] == [
        {"players": ["Alex", "Sam"], "wins": [1, 1]}
    ]


def test_a_stored_head_to_head_against_oneself_is_dropped():
    """Earlier versions stored one for a player in two seats."""
    profiles = Profiles()
    profiles.restore({"head_to_head": {"alex\x00alex": [1, 0], "alex\x00sam": [1, 0]}})
    assert profiles.head_to_head == {"alex\x00sam": [1, 0]}


def test_in_a_team_the_checkout_counts_for_the_player_who_threw_it():
    game = teams()
    for player in game.players:
        player.remaining = 40
    throw(game, "MISS", "D20")
    players = by_name(game)
    assert players["Alex"]["legs_won"] == players["Kim"]["legs_won"] == 1
    assert (players["Alex"]["checkout_rate"], players["Alex"]["highest_checkout"]) == (
        50.0,
        40,
    )
    # Kim threw no dart at a double and checked nothing out.
    assert game.profiles.players["kim"].checkouts == 0
    assert (players["Kim"]["checkout_rate"], players["Kim"]["highest_checkout"]) == (
        None,
        None,
    )


def test_a_team_cricket_leg_sets_no_best_marks_per_round():
    game = teams("cricket")
    for player in game.players[0::2]:
        player.marks = [3, 3, 3, 3, 3, 3, 2]
    throw(game, "BULL")
    assert game.legs[0]["team"] == 1
    assert all(profile.best_mpr == 0 for profile in game.profiles.players.values())
    assert by_name(game)["Alex"]["legs_won"] == 1


def test_names_never_keep_template_characters():
    """Linking and restoring clean a name as the games do."""
    profiles = Profiles()
    assert profiles.link("{{ Alex }}", "person.alex")
    assert [profile.name for profile in profiles.players.values()] == ["Alex"]
    assert not profiles.link("{%#}", "person.sam")
    restored = Profiles()
    restored.restore({"players": [{"name": "Sam{#}"}, {"name": "{}"}]})
    assert [profile.name for profile in restored.players.values()] == ["Sam"]


@pytest.mark.parametrize(
    "value",
    [
        "person.alex",
        "person.alex_2",
        "person.4lex",
        "person._alex",
        "person.alex_",
        "person.al__ex",
        "person.Alex",
        "person.alex\n",
        "person.alex.b",
        "person.",
        "person",
        "persons.alex",
        "sensor.alex",
        "",
        3,
        None,
    ],
)
def test_a_profile_links_a_person_as_home_assistant_checks_entity_ids(value):
    """The profiles check a person's entity ID without Home Assistant, as
    Home Assistant does."""
    valid = (
        isinstance(value, str)
        and valid_entity_id(value)
        and split_entity_id(value)[0] == "person"
    )
    assert _person(value) == (value if valid else None)


def test_a_renamed_profile_keeps_its_numbers_matches_and_head_to_head():
    practice = named(501, "Sammy", "Lea")
    throw(practice, "T20", "T20", "T20")
    win_leg(practice)
    profiles = practice.profiles
    profiles.link("Sammy", "person.sam")
    before = by_name(practice)["Sammy"]
    assert profiles.rename(" SAMMY ", "Sam") is False
    after = by_name(practice)["Sam"]
    assert after == {**before, "name": "Sam"}
    assert "sammy" not in profiles.players and profiles.spelled("sam") == "Sam"
    snapshot = profiles.snapshot()
    assert snapshot["head_to_head"] == [{"players": ["Lea", "Sam"], "wins": [1, 0]}]
    assert [entry["name"] for entry in snapshot["matches"][0]["players"]] == [
        "Sam",
        "Lea",
    ]


def test_a_new_spelling_of_the_same_name_renames_the_profile():
    practice = named(301, "sam", "Lea")
    win_leg(practice)
    profiles = practice.profiles
    assert profiles.rename("sam", "  Sam ") is False
    assert set(by_name(practice)) == {"Sam", "Lea"}
    assert profiles.snapshot()["head_to_head"] == [
        {"players": ["Lea", "Sam"], "wins": [0, 1]}
    ]
    assert profiles.matches[0]["players"][0]["name"] == "Sam"


def test_renaming_needs_a_profile_and_a_name():
    profiles = Profiles()
    profiles.link("Sam", "person.sam")
    assert profiles.rename("Nobody", "Sam") is None
    assert profiles.rename("Sam", " {#} ") is None
    assert list(profiles.players) == ["sam"]


def test_a_merge_adds_two_profiles_up_and_keeps_one_person():
    profiles = Profiles()
    sam = profiles.players["sam"] = Profile(
        name="Sam",
        legs_played=4,
        legs_won=2,
        x01_darts=60,
        x01_points=1000,
        highest_visit=140,
        highest_checkout=40,
        best_mpr=2.5,
        fewest_darts={"501": 18},
        doubles={"D20": [4, 1]},
        last_played="2026-10-01T20:00:00+00:00",
    )
    profiles.players["sammy"] = Profile(
        name="Sammy",
        legs_played=1,
        legs_won=1,
        x01_darts=15,
        x01_points=501,
        highest_visit=180,
        highest_checkout=121,
        best_mpr=1.5,
        fewest_darts={"501": 15, "301": 9},
        doubles={"D20": [2, 2], "D16": [1, 0]},
        last_played="2026-10-02T20:00:00+00:00",
        person="person.sam",
    )
    profiles.head_to_head = {
        "kim\x00sam": [1, 2],
        "kim\x00sammy": [3, 4],
        "lea\x00sammy": [5, 6],
        "sam\x00sammy": [7, 8],
    }
    assert profiles.rename("Sammy", "Sam") is True
    assert list(profiles.players) == ["sam"] and profiles.players["sam"] is sam
    assert (sam.legs_played, sam.legs_won, sam.x01_darts, sam.x01_points) == (
        5,
        3,
        75,
        1501,
    )
    assert (sam.highest_visit, sam.highest_checkout, sam.best_mpr) == (180, 121, 2.5)
    assert sam.fewest_darts == {"501": 15, "301": 9}
    assert sam.doubles == {"D20": [6, 3], "D16": [1, 0]}
    assert sam.last_played == "2026-10-02T20:00:00+00:00"
    # The target has no person, so it takes the other one's.
    assert sam.person == "person.sam"
    # The wins against the same player add up, those against each other go.
    assert profiles.head_to_head == {"kim\x00sam": [4, 6], "lea\x00sam": [5, 6]}
    profiles.players["alex"] = Profile(name="Alex", person="person.alex")
    assert profiles.rename("Sam", "alex") is True
    alex = profiles.players["alex"]
    assert (alex.name, alex.person) == ("alex", "person.alex")
    assert profiles.head_to_head == {"alex\x00kim": [6, 4], "alex\x00lea": [6, 5]}


# Doubles, legs and matches of one player, under one of two names.
DOUBLE_ATTEMPTS = st.lists(
    st.tuples(st.sampled_from(["D20", "D16", "BULL"]), st.booleans()), max_size=3
)
LEGS = st.fixed_dictionaries(
    {
        "darts": st.integers(0, 60),
        "points": st.integers(0, 501),
        "first9_points": st.integers(0, 180),
        "first9_darts": st.integers(0, 9),
        "at_double": st.integers(0, 6),
        "checkout": st.integers(0, 170),
        "marks": st.integers(0, 40),
        "won": st.booleans(),
        "double_out": st.booleans(),
        "team": st.booleans(),
    }
)
STEPS = st.lists(
    st.tuples(
        st.booleans(),
        st.one_of(
            st.tuples(st.just("visit"), st.integers(0, 180)),
            st.tuples(st.just("doubles"), DOUBLE_ATTEMPTS),
            st.tuples(st.just("leg"), st.sampled_from([501, 301, "cricket"]), LEGS),
            st.tuples(st.just("match"), st.booleans()),
        ),
    ),
    max_size=25,
)


def played(steps, names: tuple[str, str]) -> Profiles:
    """The profiles after every step, each for one of two names; one player,
    Kim, plays every match against them."""
    profiles = Profiles()
    for minute, (second, (kind, *values)) in enumerate(steps):
        name, now = names[second], NOW + timedelta(minutes=minute)
        if kind == "visit":
            profiles.visit(name, values[0], now)
        elif kind == "doubles":
            profiles.doubles(name, values[0], now)
        elif kind == "leg":
            profiles.leg(values[0], [{**values[1], "name": name}], now)
        else:
            players = [{"name": name, "legs": 1}, {"name": "Kim", "legs": 0}]
            profiles.match(501, players, 0 if values[0] else 1, 1, 1, now=now)
    return profiles


@settings(max_examples=200, deadline=None)
@given(STEPS)
def test_a_merge_gives_the_totals_of_one_name_that_threw_every_dart(steps):
    merged = played(steps, ("Sam", "Sammy"))
    merged.rename("Sammy", "Sam")
    alone = played(steps, ("Sam", "Sam"))
    assert merged.snapshot() == alone.snapshot()
