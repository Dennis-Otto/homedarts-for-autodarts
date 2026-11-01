"""Two teams of two, and a start score of their own for every player."""

import json
from datetime import UTC, datetime

from custom_components.homedarts.practice import PracticeGame, valid_start
from custom_components.homedarts.profiles import Profiles
from custom_components.homedarts.records import PersonalRecords

from .local_helpers import NOW, dart, throw

NAMES = ["Alex", "Sam", "Kim", "Lea"]


def teams(kind: int | str = 301, names=NAMES, legs: int = 1) -> PracticeGame:
    game = PracticeGame()
    for index, name in enumerate(names):
        game.set_name(index, name)
    game.teams = True
    game.set_players(4)
    game.set_format(legs, 1)
    game.play(kind)
    return game


def test_partners_share_one_score_and_take_turns_with_the_opponents():
    game = teams()
    snapshot = game.snapshot()
    assert snapshot["teams"] == [
        {"team": 1, "name": "Alex & Kim", "players": [1, 3]},
        {"team": 2, "name": "Sam & Lea", "players": [2, 4]},
    ]
    assert [score["team"] for score in snapshot["scores"]] == [1, 2, 1, 2]
    game.track([dart("T20")], now=NOW)
    # Both partners show the score of the visit on the board.
    remaining = [score["remaining"] for score in game.snapshot()["scores"]]
    assert remaining == [241, 301, 241, 301]
    events = game.finish_visit(now=NOW)
    game.track([], now=NOW)
    assert events[0][1]["player"] == 2 and events[0][1]["team"] == 2
    assert events[0][1]["team_name"] == "Sam & Lea"
    throw(game, "T19")
    events = throw(game, "S20")
    # Kim throws for Alex's team, from their shared 241.
    assert game.players[2].remaining == 221 and game.players[0].remaining == 221
    assert events[0][1]["player"] == 4 and events[0][1]["remaining"] == 244


def test_a_team_leg_and_match_count_for_both_partners():
    game = teams()
    for player in game.players:
        player.remaining = 40
    game.players[0].darts, game.players[2].darts = 9, 9
    game.players[0].points = game.players[0].match_points = 150
    game.players[2].points = game.players[2].match_points = 111
    game.players[0].match_darts = game.players[2].match_darts = 9
    events = throw(game, "D20")
    kinds = [kind for kind, _ in events]
    assert kinds == ["leg_won", "match_won"]
    won = dict(events)
    assert won["leg_won"]["team"] == 1 and won["leg_won"]["darts"] == 19
    assert won["leg_won"]["average"] == round(301 * 3 / 19, 2)
    assert won["match_won"]["scores"] == [
        {"player": 1, "name": "Alex", "legs": 1, "sets": 1, "team": 1},
        {"player": 2, "name": "Sam", "legs": 0, "sets": 0, "team": 2},
        {"player": 3, "name": "Kim", "legs": 1, "sets": 1, "team": 1},
        {"player": 4, "name": "Lea", "legs": 0, "sets": 0, "team": 2},
    ]
    assert won["match_won"]["average"] == round(301 * 3 / 19, 2)
    snapshot = game.snapshot()
    assert snapshot["winner"] == 1
    assert [score["remaining"] for score in snapshot["scores"]] == [0, 40, 0, 40]
    assert game.legs[0]["team"] == 1 and game.legs[0]["darts"] == 19
    profiles = game.profiles.snapshot()
    wins = {player["name"]: player["matches_won"] for player in profiles["players"]}
    assert wins == {"Alex": 1, "Sam": 0, "Kim": 1, "Lea": 0}
    legs = {player["name"]: player["legs_won"] for player in profiles["players"]}
    assert legs == {"Alex": 1, "Sam": 0, "Kim": 1, "Lea": 0}
    # A team leg sets no fewest darts for one player, but the checkout counts.
    alex = next(player for player in profiles["players"] if player["name"] == "Alex")
    assert alex["fewest_darts"] == {} and alex["highest_checkout"] == 40
    # Head-to-head only between opponents: every winner beat both of them.
    pairs = {tuple(item["players"]): item["wins"] for item in profiles["head_to_head"]}
    assert pairs == {
        ("Alex", "Sam"): [1, 0],
        ("Alex", "Lea"): [1, 0],
        ("Kim", "Sam"): [1, 0],
        ("Kim", "Lea"): [1, 0],
    }
    match = game.profiles.matches[0]
    assert match["winner"] == 1 and match["winners"] == [1, 3]
    assert [player["team"] for player in match["players"]] == [1, 2, 1, 2]


def test_team_cricket_shares_marks_and_points():
    game = teams("cricket")
    game.track([dart("T20"), dart("S20")], now=NOW)
    scores = game.snapshot()["scores"]
    assert [score["points"] for score in scores] == [20, 0, 20, 0]
    assert [score["marks"][0] for score in scores] == [3, 0, 3, 0]
    game.finish_visit(now=NOW)
    game.track([], now=NOW)
    assert game.players[2].marks[0] == 3 and game.players[2].points == 20
    # Sam's team closes the 20: Kim scores no more on it.
    throw(game, "T20")
    throw(game, "T20")
    assert game.players[0].points == 20 and game.players[2].points == 20
    throw(game, "MISS")
    for player in game.players[0::2]:
        player.marks = [3, 3, 3, 3, 3, 3, 2]
        player.points = 20
    game.players[1].darts, game.players[3].darts = 3, 3
    game.players[0].darts, game.players[2].darts = 3, 3
    events = throw(game, "S20", "BULL")
    assert events[0][0] == "leg_won" and events[0][1]["team"] == 1


def test_team_cut_throat_gives_both_opponents_the_points():
    game = teams("cut_throat")
    throw(game, "T20", "T20")
    assert [player.points for player in game.players] == [0, 60, 0, 60]


def test_teams_need_four_players_of_x01_or_cricket():
    game = teams()
    game.set_players(2)
    assert game.snapshot()["teams"] is None
    assert game._who(0).get("team") is None
    game = teams("golf")
    assert game.snapshot()["teams"] is None


def test_a_team_without_both_names_has_no_name():
    game = teams(names=["Alex", "", "Kim", "Lea"])
    assert [team["name"] for team in game.snapshot()["teams"]] == [
        "Alex & Kim",
        None,
    ]


def test_the_winners_of_a_team_match_keep_their_score_after_a_restart():
    game = teams()
    for player in game.players:
        player.remaining = 40
    throw(game, "D20")
    saved = json.loads(json.dumps(game.stored()))
    restored = PracticeGame()
    restored.restore(saved)
    assert restored.stored() == saved and restored.teams is True
    assert [player.remaining for player in restored.players] == [0, 40, 0, 40]


def test_start_scores_are_zero_or_two_to_1001():
    assert valid_start(0) and valid_start(2) and valid_start(1001)
    assert not valid_start(1) and not valid_start(1002) and not valid_start(True)


def handicap(*starts: int, game: int = 501) -> PracticeGame:
    practice = PracticeGame()
    practice.set_players(len(starts))
    for index, start in enumerate(starts):
        practice.set_start(index, start)
    practice.play(game)
    return practice


def test_every_player_starts_from_their_own_score():
    game = handicap(0, 301)
    game.set_format(legs=3)
    snapshot = game.snapshot()
    assert [score["start"] for score in snapshot["scores"]] == [501, 301]
    assert [score["remaining"] for score in snapshot["scores"]] == [501, 301]
    assert snapshot["start"] == 501
    game.set_start(1, 1)
    assert game.starts == [0, 301, 0, 0]
    game.set_start(7, 301)
    assert game.starts == [0, 301, 0, 0]
    throw(game, "T20")
    game.players[1].remaining = 40
    events = throw(game, "D20")
    won = dict(events)["leg_won"]
    assert won["start"] == 301 and won["checkout"] == 40
    assert won["average"] == round(301 * 3 / 1, 2)
    assert game.legs[0]["start"] == 301
    # The next leg starts from the own scores again.
    assert [player.remaining for player in game.players] == [501, 301]


def test_handicap_legs_count_for_the_score_they_started_from():
    records = PersonalRecords()
    profiles = Profiles()
    now = datetime(2026, 9, 27, 12, tzinfo=UTC)
    leg = {
        "game": 501,
        "name": "Kim",
        "darts": 12,
        "checkout": 40,
        "double_out": True,
    }
    records.observe("leg_won", {**leg, "start": 501}, now)
    records.observe("leg_won", {**leg, "start": 301, "darts": 9}, now)
    records.observe("leg_won", {**leg, "start": 401, "darts": 6}, now)
    assert records.bests["fewest_darts_501"]["value"] == 12
    assert records.bests["fewest_darts_301"]["value"] == 9
    assert "fewest_darts_401" not in records.bests
    # A team leg sets no fewest darts and no MPR, only the checkout.
    records.observe("leg_won", {**leg, "start": 501, "darts": 3, "team": 1}, now)
    records.observe("leg_won", {"game": "cricket", "mpr": 9.0, "team": 1}, now)
    assert records.bests["fewest_darts_501"]["value"] == 12
    assert "best_cricket_mpr" not in records.bests
    entry = {"name": "Kim", "won": True, "darts": 9, "double_out": True}
    profiles.leg(501, [{**entry, "start": 301}], now=NOW)
    profiles.leg(501, [{**entry, "start": 401}], now=NOW)
    profiles.leg(501, [{**entry, "darts": 12}], now=NOW)
    assert profiles.players["kim"].fewest_darts == {"301": 9, "501": 12}


def test_start_scores_survive_a_restart_and_ignore_nonsense():
    game = handicap(0, 301, 701)
    game.teams = True
    saved = json.loads(json.dumps(game.stored()))
    assert saved["starts"] == [0, 301, 701, 0]
    restored = PracticeGame()
    restored.restore(saved)
    assert restored.stored() == saved
    restored.restore({**saved, "starts": [0, 1, "x", 5000]})
    assert restored.starts == [0, 0, 0, 0]
    restored.restore({**saved, "starts": [301]})
    assert restored.starts == [0, 0, 0, 0]
    # A stored remaining score above the own start begins the leg again.
    saved["players"][1]["remaining"] = 450
    restored.restore(saved)
    assert restored.players[1].remaining == 301


def test_partners_play_from_the_start_of_the_first_player_of_their_team():
    game = handicap(0, 301, 701, 0)
    game.teams = True
    game.new_match()
    assert [player.remaining for player in game.players] == [501, 301, 501, 301]


def test_a_new_leg_after_a_finished_match_starts_the_next_match():
    game = teams()
    for player in game.players:
        player.remaining = 40
    throw(game, "D20")
    assert game.winner == 0
    game.new_leg()
    assert game.winner is None
    assert [player.remaining for player in game.players] == [301] * 4
