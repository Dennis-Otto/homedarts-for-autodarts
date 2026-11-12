"""The summary of a finished practice match, and snapshots that stay as written."""

import copy
import json

from custom_components.homedarts.practice import PracticeGame
from custom_components.homedarts.summary import Tally

from .local_helpers import match, throw, win_leg


def x01_match() -> tuple[PracticeGame, dict]:
    """Alex beats Sam 2 : 1 in 301, first to two legs; the match_won event."""
    game = match(2, legs=2, p1="Alex", p2="Sam")
    # Leg 1: Alex scores 180, then checks out 121 on D14.
    throw(game, "T20", "T20", "T20")
    throw(game, "S20", "S20", "S20")
    throw(game, "T20", "T11", "D14")
    # Leg 2, Sam first: 177, and 124 out on D2 after Alex's 140.
    throw(game, "T20", "T20", "T19")
    throw(game, "T20", "T20", "S20")
    throw(game, "T20", "T20", "D2")
    # Leg 3: Alex needs twelve darts and misses the bull before D20.
    for visit in (("S20", "S20", "S20"), ("T20", "T20", "T20"), ("S1", "S1", "S1")):
        throw(game, *visit)
        throw(game, "MISS", "MISS", "MISS")
    events = dict(throw(game, "S8", "S10", "D20"))
    return game, events["match_won"]


ALEX = {
    "player": 1,
    "name": "Alex",
    "legs": 2,
    "sets": 1,
    "darts": 21,
    "average": 106.0,
    # 60 + 180 + 3 in leg 3's first nine darts, all darts of the others.
    "first_9_average": 114.0,
    "checkouts": 2,
    "darts_at_double": 3,
    "checkout_rate": 66.7,
    "highest_checkout": 121,
    "scores_100": 1,
    "scores_140": 1,
    "scores_180": 2,
    "best_leg": 6,
}
SAM = {
    "player": 2,
    "name": "Sam",
    "legs": 1,
    "sets": 0,
    "darts": 18,
    "average": 60.17,
    "first_9_average": 60.17,
    "checkouts": 1,
    "darts_at_double": 1,
    "checkout_rate": 100.0,
    "highest_checkout": 124,
    "scores_100": 1,
    "scores_140": 1,
    "scores_180": 0,
    "best_leg": 6,
}


def test_a_finished_x01_match_sums_up_every_player():
    game, won = x01_match()
    summary = game.snapshot()["summary"]
    assert {key: summary[key] for key in summary if key != "ended"} == {
        "game": 301,
        "winner": 1,
        "legs_to_win": 2,
        "sets_to_win": 1,
        "double_out": True,
        "players": [ALEX, SAM],
    }
    # The dart that wins the match announces the same numbers.
    assert won["summary"] == summary["players"]
    assert (won["legs"], won["average"]) == (2, 106.0)
    # The history keeps the numbers of the summary with the match.
    assert game.profiles.matches[0]["summary"]["players"] == summary["players"]
    # Nothing of the scratch booking reached the profiles.
    assert game.profiles.players["alex"].legs_won == 2
    assert game.profiles.players["alex"].matches_won == 1


def test_the_summary_survives_a_restart_and_the_next_match():
    game, _ = x01_match()
    summary = game.snapshot()["summary"]
    restored = PracticeGame()
    restored.restore(json.loads(json.dumps(game.stored())))
    assert restored.snapshot()["summary"] == summary
    assert restored.tallies == game.tallies
    # The next match counts from zero and keeps the summary of the last one.
    throw(restored, "T20")
    assert restored.snapshot()["winner"] is None
    assert restored.snapshot()["summary"] == summary
    assert restored.tallies[0].scores_180 == 0 and restored.tallies[1] == Tally()


def test_stores_without_a_summary_or_with_broken_tallies_still_load():
    game, _ = x01_match()
    saved = game.stored()
    for key in ("summary", "tallies", "out_mode_next"):
        del saved[key]
    game.restore(saved)
    assert game.summary is None and game.out_mode_next is None
    assert game.tallies == [Tally(), Tally()]
    saved |= {
        "summary": {"players": "none"},
        "tallies": [{"scores_180": -1, "best_leg": 9, "checkouts": "2"}, None],
        "out_mode_next": "yes",
    }
    game.restore(saved)
    assert game.summary is None and game.out_mode_next is None
    assert game.tallies == [Tally(best_leg=9), Tally()]
    saved["tallies"] = [{}]
    game.restore(saved)
    assert game.tallies == [Tally(), Tally()]


def test_a_cricket_match_sums_up_marks_and_the_best_leg():
    game = match(2, p1="Alex")
    game.play("cricket")
    throw(game, "T20", "T19", "T18")
    throw(game, "MISS", "MISS", "MISS")
    throw(game, "T17", "T16", "T15")
    throw(game, "S20")
    events = dict(throw(game, "BULL", "25"))
    players = game.snapshot()["summary"]["players"]
    assert players == [
        {
            "player": 1,
            "name": "Alex",
            "legs": 1,
            "sets": 1,
            "darts": 8,
            "mpr": 7.88,
            "marks": 21,
            "best_leg": 8,
        },
        {
            "player": 2,
            "name": None,
            "legs": 0,
            "sets": 0,
            "darts": 4,
            "mpr": 0.75,
            "marks": 1,
            "best_leg": None,
        },
    ]
    assert events["match_won"]["summary"] == players


def test_party_matches_sum_up_legs_and_darts():
    game = match(2, p2="Sam")
    game.play("shanghai")
    throw(game, "MISS", "MISS")
    # A Shanghai wins at once, before the darts are pulled.
    events = dict(throw(game, "S1", "D1", "T1"))
    summary = game.snapshot()["summary"]
    assert summary["game"] == "shanghai" and summary["winner"] == 2
    assert summary["players"] == [
        {"player": 1, "name": None, "legs": 0, "sets": 0, "darts": 2},
        {"player": 2, "name": "Sam", "legs": 1, "sets": 1, "darts": 3},
    ]
    assert events["match_won"]["summary"] == summary["players"]
    # The history keeps no summary of a party game: it stays a plain row.
    assert "summary" not in game.profiles.matches[0]
    assert "details" not in game.profiles.snapshot()["matches"][0]


def test_a_party_match_decided_by_the_last_round_announces_its_summary():
    game = match(2)
    game.play("shanghai")
    events: dict = {}
    for round_number in range(1, 8):
        throw(game, f"S{round_number}")
        events = dict(throw(game, "MISS", "MISS", "MISS"))
    assert game.snapshot()["winner"] == 1
    players = game.snapshot()["summary"]["players"]
    assert [(player["legs"], player["darts"]) for player in players] == [
        (1, 7),
        (0, 21),
    ]
    assert events["match_won"]["summary"] == players


def test_playing_alone_ends_no_match_and_has_no_summary():
    game = match(1)
    game.players[0].remaining = 40
    throw(game, "D20")
    assert game.snapshot()["summary"] is None
    assert game.tallies[0].best_leg == 1 and game.tallies[0].checkouts == 1


def test_a_single_out_match_counts_finishes_but_no_checkout_rate():
    game = match(2)
    game.double_out = False
    game.players[0].remaining = 7
    throw(game, "S7")
    player = game.snapshot()["summary"]["players"][0]
    assert (player["checkouts"], player["darts_at_double"]) == (0, 0)
    assert player["checkout_rate"] is None and player["highest_checkout"] == 7


def test_snapshots_do_not_change_once_written():
    """Home Assistant keeps the attributes of every state it wrote."""
    game, _ = x01_match()
    snapshot = game.snapshot()
    written = copy.deepcopy(snapshot)
    # The first dart starts the next match, whose first leg joins the legs.
    throw(game, "MISS")
    win_leg(game, 1)
    assert game.snapshot()["legs"] != written["legs"]
    assert snapshot == written
    game.play("doubles")
    drill = game.snapshot()["drill"]
    written = copy.deepcopy(drill)
    for target in (*(f"D{number}" for number in range(1, 21)), "BULL"):
        throw(game, target)
    assert game.snapshot()["drill"]["results"] != written["results"]
    assert drill == written


def test_a_team_wins_its_legs_together_and_the_checkout_counts_for_its_thrower():
    game = PracticeGame()
    for index, name in enumerate(("Alex", "Sam", "Kim", "Lea")):
        game.set_name(index, name)
    game.teams = True
    game.set_players(4)
    game.play(301)
    throw(game, "T20", "T20", "T20")
    throw(game, "MISS")
    # Kim finishes the 121 of Alex and Kim, in the sixth dart of the team.
    events = dict(throw(game, "T20", "T11", "D14"))
    players = {entry["name"]: entry for entry in game.snapshot()["summary"]["players"]}
    assert events["match_won"]["summary"] == list(players.values())
    numbers = ("legs", "darts", "best_leg", "checkouts", "highest_checkout")
    assert {name: tuple(players[name][key] for key in numbers) for name in players} == {
        "Alex": (1, 3, 6, 0, None),
        "Sam": (0, 1, None, 0, None),
        "Kim": (1, 3, 6, 1, 121),
        "Lea": (0, 0, None, 0, None),
    }
