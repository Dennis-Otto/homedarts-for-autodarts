"""Training plans: several training games in a row, with a plan of the day."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.homedarts.achievements import ACHIEVEMENTS
from custom_components.homedarts.calls import Caller
from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.drills import CHECKOUT_SCORES, DRILLS
from custom_components.homedarts.errors import ActionRefused
from custom_components.homedarts.games import BoardGames
from custom_components.homedarts.journal import TrainingJournal
from custom_components.homedarts.plans import (
    MAX_NAME,
    MAX_PLANS,
    MAX_STEPS,
    PRESET_NAMES,
    PRESETS,
    ROTATION,
    WEEKDAYS,
    PlanRunner,
    Step,
    own_plans,
    parse_plan,
    parse_step,
    plan_name,
)
from custom_components.homedarts.practice import PracticeGame
from custom_components.homedarts.report import WeeklyReport

from .local_helpers import MISS, board, entity_id, record, setup_local, state

# A Thursday.
NOW = datetime(2026, 10, 1, 20, 0, tzinfo=UTC)
D1 = ("D1", 1, 2)
THREE_STEPS = [
    {"drill": "around_the_clock", "darts": 3},
    {"drill": "bobs_27", "rounds": 2},
    {"drill": "singles", "rounds": 1},
]


class Reports:
    """The weekly report and the journal, as far as the games use them."""

    def __init__(self) -> None:
        self.counted: list[str] = []

    def observe(self, events, now, booked=None):
        self.counted += [kind for kind, _ in events]

    def checkpoint(self):
        return {}

    def rewind(self, checkpoint):
        pass

    def forget(self, name):
        pass

    def rename(self, name, new_name):
        pass


def takeout():
    return board(status="Takeout", event="Takeout started")


def follow(games, *states, now=NOW):
    data: dict = {}
    announced = []
    for one in states:
        announced += games.follow_visit(data, one, "websocket", now)
    return announced, data


def throw(games, *hits, now=NOW):
    """A visit: its darts land and are pulled; the events it brings."""
    hits = hits or (MISS, MISS, MISS)
    darts = [board(*hits[:count]) for count in range(1, len(hits) + 1)]
    return follow(games, *darts, takeout(), board(), now=now)[0]


def planned(steps=None, name="Evening", player=None):
    games = BoardGames(Reports(), NOW, random.Random(1))
    games.start_plan(
        NOW, name=name, steps=THREE_STEPS if steps is None else steps, player=player
    )
    follow(games, board())
    return games


def named(announced, kind):
    return [attributes for found, attributes, _ in announced if found == kind]


def refusal(action):
    with pytest.raises(ActionRefused) as refused:
        action()
    return refused.value.key, refused.value.placeholders


# -- what a plan is ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "step"),
    [
        ({"drill": "doubles"}, Step("doubles")),
        ({"drill": "doubles", "until": "finished"}, Step("doubles")),
        ({"drill": "doubles", "darts": 60}, Step("doubles", darts=60)),
        ({"drill": "checkout", "rounds": 5}, Step("checkout", rounds=5)),
        (
            {"drill": "checkout", "rounds": 5, "options": {"low": 40, "high": 100}},
            Step("checkout", rounds=5, low=40, high=100),
        ),
        (
            {"drill": "checkout", "darts": 9, "options": {"high": 40}},
            Step("checkout", darts=9, high=40),
        ),
    ],
)
def test_a_step_says_its_game_and_what_ends_it(raw, step):
    assert parse_step(raw) == step
    # As stored, it reads the same, for a restart.
    assert parse_step(step.stored()) == step


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "doubles",
        {},
        {"drill": "501"},
        {"drill": "doubles", "colour": "red"},
        # At most one end.
        {"drill": "doubles", "darts": 3, "rounds": 3},
        {"drill": "doubles", "darts": 3, "until": "finished"},
        {"drill": "doubles", "until": "tomorrow"},
        # Sensible limits.
        {"drill": "doubles", "darts": 0},
        {"drill": "doubles", "darts": True},
        {"drill": "doubles", "darts": 1001},
        {"drill": "doubles", "rounds": 0},
        {"drill": "doubles", "rounds": 301},
        {"drill": "doubles", "rounds": "3"},
        # These two never end by themselves.
        {"drill": "checkout"},
        {"drill": "checkout_121"},
        {"drill": "checkout", "until": "finished"},
        # Only the checkout training has options.
        {"drill": "doubles", "options": {"low": 2}},
        {"drill": "checkout", "rounds": 3, "options": "easy"},
        {"drill": "checkout", "rounds": 3, "options": {"lowest": 2}},
        {"drill": "checkout", "rounds": 3, "options": {"low": 0}},
        {"drill": "checkout", "rounds": 3, "options": {"high": 171}},
        # Three darts cannot finish these, and nothing lies between 100 and 40.
        {"drill": "checkout", "rounds": 3, "options": {"low": 168, "high": 169}},
        {"drill": "checkout", "rounds": 3, "options": {"low": 100, "high": 40}},
    ],
)
def test_a_step_that_makes_no_sense_is_refused(raw):
    assert parse_step(raw) is None


@pytest.mark.parametrize(
    "raw",
    [
        None,
        {"steps": [{"drill": "doubles"}]},
        {"name": 3, "steps": [{"drill": "doubles"}]},
        {"name": " ", "steps": [{"drill": "doubles"}]},
        {"name": "x" * (MAX_NAME + 1), "steps": [{"drill": "doubles"}]},
        {"name": "Evening"},
        {"name": "Evening", "steps": []},
        {"name": "Evening", "steps": [{"drill": "doubles"}] * (MAX_STEPS + 1)},
        {"name": "Evening", "steps": [{"drill": "501"}]},
        {"name": "Evening", "steps": [{"drill": "doubles"}], "weekdays": "monday"},
        {"name": "Evening", "steps": [{"drill": "doubles"}], "weekdays": ["payday"]},
        {"name": "Evening", "steps": [{"drill": "doubles"}], "colour": "red"},
        {"name": "Evening", "steps": [{"drill": "doubles"}], "key": 3},
    ],
)
def test_a_plan_that_makes_no_sense_is_refused(raw):
    assert parse_plan(raw) is None


def test_own_plans_are_read_from_the_options():
    plans = own_plans(
        [
            {
                # The name is the key of an own plan, whatever the YAML says.
                "key": "warm_up",
                "name": " Tuesday ",
                "steps": [{"drill": "doubles", "darts": 30}],
                "weekdays": ["tuesday", "monday", "tuesday"],
            }
        ]
    )
    assert plans is not None
    assert (plans[0].key, plans[0].name, plans[0].weekdays) == (
        "Tuesday",
        "Tuesday",
        (0, 1),
    )
    assert parse_plan(plans[0].stored()) == plans[0]
    assert own_plans([]) == ()


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "plans",
        ["plan"],
        [{"name": "Evening"}],
        # The name of a plan of the integration, or of another plan in any case.
        [{"name": "WARM_UP", "steps": [{"drill": "doubles"}]}],
        [
            {"name": "Evening", "steps": [{"drill": "doubles"}]},
            {"name": "evening", "steps": [{"drill": "doubles"}]},
        ],
        [
            {"name": f"Plan {i}", "steps": [{"drill": "doubles"}]}
            for i in range(MAX_PLANS + 1)
        ],
    ],
)
def test_own_plans_that_cannot_be_told_apart_are_refused(raw):
    assert own_plans(raw) is None


def test_every_plan_of_the_integration_is_valid_and_named_in_every_language():
    for plan in PRESETS.values():
        assert parse_plan(plan.stored()) == plan
        assert all(step.drill in DRILLS for step in plan.steps)
        for language, names in PRESET_NAMES.items():
            assert plan_name(plan.key, plan.name, language) == names[plan.key]
        assert plan_name(plan.key, plan.name) == plan.name
    assert plan_name("doubles_day", "Doubles day", "de-AT") == "Doppel-Tag"
    assert plan_name("My plan", "My plan", "de") == "My plan"
    assert len(ROTATION) == len(WEEKDAYS)
    assert set(ROTATION) == set(PRESETS)


# -- playing -----------------------------------------------------------------------


@pytest.mark.parametrize("key", list(PRESETS))
def test_every_plan_of_the_integration_runs_to_its_end(key):
    games = BoardGames(Reports(), NOW, random.Random(1))
    games.start_plan(NOW, key, player="Alex")
    follow(games, board())
    plan = PRESETS[key]
    played, steps, ended = [], [], []
    for _ in range(400):
        if games.plans.plan is None:
            break
        played.append(games.practice.drill)
        announced = throw(games)
        steps += named(announced, "plan_step_finished")
        ended += named(announced, "plan_finished")
    assert [step.drill for step in plan.steps] == list(dict.fromkeys(played))
    assert [step["drill"] for step in steps] == [step.drill for step in plan.steps]
    assert [step["step"] for step in steps] == list(range(1, len(plan.steps) + 1))
    assert not any(step["skipped"] for step in steps)
    assert len(ended) == 1
    assert ended[0]["plan"] == key
    assert ended[0]["plan_name"] == plan.name
    assert ended[0]["name"] == "Alex"
    assert ended[0]["player"] == 1
    assert ended[0]["reason"] == "finished"
    assert ended[0]["completed"] is True
    assert ended[0]["played"] == len(plan.steps)
    assert ended[0]["darts"] == sum(step["darts"] for step in steps)
    assert ended[0]["results"] == [
        {key: step[key] for key in ended[0]["results"][index]}
        for index, step in enumerate(steps)
    ]
    # The board is free again, and today's plan of the integration is done.
    assert games.practice.drill is None
    assert games.practice_snapshot()["plan"] is None
    assert games.plans.done == [key]


def test_the_snapshot_says_which_step_is_played():
    games = planned()
    assert games.practice_snapshot()["plan"] == {
        "plan": "Evening",
        "name": "Evening",
        "step": 1,
        "steps": 3,
        "drill": "around_the_clock",
        "drills": ["around_the_clock", "bobs_27", "singles"],
        "darts": 0,
        "visits": 0,
        "darts_limit": 3,
        "rounds_limit": None,
    }
    assert games.practice.drill == "around_the_clock"


def test_a_step_with_a_limit_moves_on_with_the_visit_that_reaches_it():
    games = planned()
    announced = throw(games, MISS, MISS)
    assert not named(announced, "plan_step_finished")
    assert games.practice_snapshot()["plan"]["darts"] == 2
    announced = throw(games, ("S1", 1, 1), MISS)
    (step,) = named(announced, "plan_step_finished")
    assert step == {
        "plan": "Evening",
        "plan_name": "Evening",
        "name": None,
        "player": 1,
        "step": 1,
        "steps": 3,
        "drill": "around_the_clock",
        "darts": 4,
        "visits": 2,
        "finished": False,
        "skipped": False,
        "hits": 1,
        "hit_rate": 25.0,
    }
    # The next game is on the board, announced as a game of its own.
    assert games.practice.drill == "bobs_27"
    assert games.practice_snapshot()["plan"]["step"] == 2
    assert games.practice_snapshot()["plan"]["darts"] == 0
    (over,) = named(announced, "game_ended")
    (started,) = named(announced, "game_started")
    assert over["game"] == "around_the_clock"
    assert started["game"] == "bobs_27"


def test_a_step_without_a_limit_ends_with_its_game():
    games = planned([{"drill": "bobs_27"}, {"drill": "singles", "rounds": 1}])
    # Five visits without a hit take Bob's 27 below zero.
    events = [throw(games) for _ in range(5)]
    assert not any(named(announced, "plan_step_finished") for announced in events[:-1])
    (step,) = named(events[-1], "plan_step_finished")
    assert step["finished"] is True
    assert step["completed"] is False
    assert step["score"] == 27 - (2 + 4 + 6 + 8 + 10)
    assert games.practice.drill == "singles"


def test_a_limit_also_ends_with_the_game_that_ends_before_it():
    games = planned([{"drill": "bobs_27", "rounds": 300}, {"drill": "singles"}])
    for _ in range(5):
        throw(games)
    assert games.practice.drill == "singles"


def test_a_step_can_play_the_same_game_again_from_the_start():
    games = planned(
        [{"drill": "bobs_27", "rounds": 1}, {"drill": "bobs_27", "rounds": 1}]
    )
    throw(games)
    assert games.practice_snapshot()["plan"]["step"] == 2
    assert games.practice.drills["bobs_27"].score == 27


def test_darts_on_the_board_when_a_step_starts_do_not_count():
    games = planned()
    follow(games, board(MISS, MISS))
    games.next_plan_step(NOW)
    assert games.practice.drill == "bobs_27"
    # The third dart counts, and the two before it stay out of the next game.
    announced = throw_on(games)
    assert not named(announced, "plan_step_finished")
    assert games.practice_snapshot()["plan"]["darts"] == 1
    assert games.practice_snapshot()["plan"]["visits"] == 1


def throw_on(games):
    return follow(games, board(MISS, MISS, MISS), takeout(), board())[0]


def test_a_visit_without_a_dart_of_the_step_counts_for_nothing():
    games = planned()
    follow(games, board(MISS))
    games.next_plan_step(NOW)
    announced = follow(games, takeout(), board())[0]
    assert not named(announced, "plan_step_finished")
    assert games.practice_snapshot()["plan"]["visits"] == 0


def test_skip_moves_on_and_says_it_was_skipped():
    games = planned()
    events = games.next_plan_step(NOW)
    assert [kind for kind, _ in events] == ["plan_step_finished"]
    assert events[0][1]["skipped"] is True
    assert events[0][1]["darts"] == 0
    assert games.practice.drill == "bobs_27"


def test_skipping_the_last_step_finishes_the_plan():
    games = planned()
    throw(games)
    games.next_plan_step(NOW)
    events = games.next_plan_step(NOW)
    assert [kind for kind, _ in events] == ["plan_step_finished", "plan_finished"]
    ended = events[-1][1]
    assert ended["reason"] == "finished"
    assert ended["completed"] is True
    assert ended["played"] == 1
    assert [result["skipped"] for result in ended["results"]] == [False, True, True]
    assert games.practice.drill is None


def test_a_plan_with_every_step_skipped_is_no_finished_plan():
    games = planned([{"drill": "doubles"}], player="Alex")
    events = games.next_plan_step(NOW)
    assert events[-1][0] == "plan_finished"
    assert events[-1][1]["reason"] == "stopped"
    assert events[-1][1]["completed"] is False
    assert games.plans.done == []
    assert games.practice.drill is None


def test_stop_ends_the_plan_and_the_game_with_what_the_step_brought():
    games = planned()
    throw(games, MISS)
    events = games.stop_plan(NOW)
    assert [kind for kind, _ in events] == ["plan_finished"]
    ended = events[0][1]
    assert ended["reason"] == "stopped"
    assert ended["completed"] is False
    assert ended["darts"] == 1
    assert [result["drill"] for result in ended["results"]] == ["around_the_clock"]
    assert ended["results"][0]["skipped"] is False
    assert ended["started"] and ended["ended"]
    assert games.plans.plan is None
    assert games.practice.drill is None


def test_stop_without_a_dart_tells_no_result():
    games = planned()
    assert games.stop_plan(NOW)[0][1]["results"] == []


def test_there_is_nothing_to_skip_or_stop_without_a_plan():
    games = BoardGames(Reports(), NOW)
    assert refusal(lambda: games.next_plan_step(NOW)) == ("no_plan", {})
    assert refusal(lambda: games.stop_plan(NOW)) == ("no_plan", {})


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda games: games.practice.play("doubles"), "replaced"),
        (lambda games: games.practice.play(501), "replaced"),
        (lambda games: games.practice.play(0), "stopped"),
    ],
)
def test_another_game_on_the_board_ends_the_plan(change, reason):
    games = planned()
    change(games)
    announced = games.changed([], NOW)
    (ended,) = [details for kind, details in announced if kind == "plan_finished"]
    assert ended["reason"] == reason
    assert ended["completed"] is False
    assert games.plans.plan is None
    assert "plan_finished" in games._reports.counted
    # The game stays.
    assert games.practice.drill != "around_the_clock"


def test_the_same_game_set_up_again_stays_in_the_plan():
    games = planned()
    throw(games, MISS)
    games.practice.play("around_the_clock")
    assert not [kind for kind, _ in games.changed([], NOW) if kind == "plan_finished"]
    assert games.plans.plan is not None


def test_a_new_plan_takes_the_place_of_the_one_played():
    games = planned()
    events = games.start_plan(NOW, "doubles_day")
    assert [kind for kind, _ in events] == ["plan_finished"]
    assert events[0][1]["reason"] == "replaced"
    assert games.plans.plan is PRESETS["doubles_day"]
    assert games.practice.drill == "doubles"


def test_a_tournament_does_not_give_way_to_a_plan():
    games = BoardGames(Reports(), NOW, random.Random(1))
    games.start_tournament(NOW, players=["Alex", "Sam", "Kim"])
    assert refusal(lambda: games.start_plan(NOW, "warm_up")) == (
        "plan_in_tournament",
        {},
    )


def test_a_plan_is_named_or_given_by_its_steps():
    games = BoardGames(Reports(), NOW)
    assert refusal(lambda: games.start_plan(NOW, "nothing")) == (
        "unknown_plan",
        {"plan": "nothing"},
    )
    assert refusal(lambda: games.start_plan(NOW, steps=[{"drill": "501"}])) == (
        "invalid_plan",
        {},
    )
    assert refusal(lambda: games.start_plan(NOW, "warm_up", player="Al{ex")) == (
        "invalid_player_name",
        {},
    )
    games.start_plan(NOW, steps=[{"drill": "doubles"}])
    assert games.plans.plan.name == "Training plan"


def test_an_own_plan_is_found_by_its_name_in_any_case():
    games = BoardGames(Reports(), NOW)
    games.plans.custom = own_plans(
        [{"name": "Evening", "steps": [{"drill": "singles"}]}]
    )
    games.start_plan(NOW, " EVENING ")
    assert games.plans.plan.key == "Evening"
    assert games.practice.drill == "singles"


def test_a_name_without_steps_names_the_plan_to_start():
    games = BoardGames(Reports(), NOW)
    games.plans.custom = own_plans(
        [{"name": "Evening", "steps": [{"drill": "singles"}]}]
    )
    games.start_plan(NOW, name="evening")
    assert games.plans.plan.key == "Evening"
    assert refusal(lambda: games.start_plan(NOW, name="Morning")) == (
        "unknown_plan",
        {"plan": "Morning"},
    )
    # The field for a key goes first.
    games.start_plan(NOW, "warm_up", name="Evening")
    assert games.plans.plan.key == "warm_up"


def test_a_player_keeps_the_spelling_of_the_profile():
    games = planned([{"drill": "doubles", "darts": 1}], player="Alex")
    throw(games, MISS)
    # Finished games make the profile that spells the name.
    games.practice.profiles.players["alex"] = SimpleNamespace(name="Alex")
    games.start_plan(NOW, "warm_up", player="alex")
    assert games.practice.names[0] == "Alex"


def test_a_name_is_one_player_when_a_plan_starts():
    games = BoardGames(Reports(), NOW)
    games.practice.names[:2] = ["Sam", "Alex"]
    games.start_plan(NOW, "warm_up", player="ALEX")
    assert games.practice.names[:2] == ["ALEX", ""]


def test_the_checkout_training_of_a_step_stays_among_its_finishes():
    games = planned(
        [
            {"drill": "checkout", "rounds": 1, "options": {"low": 40, "high": 41}},
            {"drill": "checkout", "rounds": 1},
        ]
    )
    drill = games.practice.drills["checkout"]
    assert drill.target in (40, 41)
    assert drill.scores == (40, 41)
    throw(games)
    assert drill.scores == CHECKOUT_SCORES
    games.stop_plan(NOW)
    assert drill.scores == CHECKOUT_SCORES


def test_the_undo_of_a_visit_takes_it_out_of_the_step():
    games = planned()
    throw(games, MISS, MISS)
    assert games.practice_snapshot()["plan"]["darts"] == 2
    games.undo_visit(NOW)
    assert games.practice_snapshot()["plan"]["darts"] == 0
    assert games.practice_snapshot()["plan"]["visits"] == 0


def test_a_visit_that_ended_its_step_cannot_be_undone():
    games = planned()
    throw(games)
    assert games.practice_snapshot()["undo"] is False
    assert refusal(lambda: games.undo_visit(NOW))[0] == "undo_unavailable"


# -- the plan of the day -----------------------------------------------------------


@pytest.mark.parametrize("weekday", range(7))
def test_the_plan_of_the_day_turns_with_the_week(weekday):
    # 5 October 2026 is a Monday.
    runner = PlanRunner(date(2026, 10, 5) + timedelta(days=weekday))
    assert runner.today().key == ROTATION[weekday]


def test_an_own_plan_can_take_a_weekday_of_the_rotation():
    # A Thursday.
    games = BoardGames(Reports(), NOW)
    games.plans.custom = own_plans(
        [
            {"name": "Never", "steps": [{"drill": "doubles"}]},
            {
                "name": "Thursdays",
                "steps": [{"drill": "singles"}],
                "weekdays": ["thursday"],
            },
        ]
    )
    assert games.practice_snapshot()["plan_of_the_day"] == {
        "plan": "Thursdays",
        "name": "Thursdays",
        "drills": ["singles"],
        "done": False,
    }
    # Asked for no plan, the action starts the plan of the day.
    games.start_plan(NOW)
    assert games.plans.plan.key == "Thursdays"


def test_the_offer_knows_that_the_plan_of_the_day_is_done_today():
    games = BoardGames(Reports(), NOW)
    key = games.plans.today().key
    games.start_plan(NOW)
    assert games.practice_snapshot()["plan_of_the_day"]["done"] is False
    while games.plans.plan:
        throw(games)
    assert games.practice_snapshot()["plan_of_the_day"]["done"] is True
    # Doing it again changes nothing, and the next day offers it afresh.
    games.start_plan(NOW, key)
    while games.plans.plan:
        throw(games)
    assert games.plans.done == [key]
    games.plans.day = NOW.date() + timedelta(days=7)
    assert games.practice_snapshot()["plan_of_the_day"]["done"] is False
    # Another day's plan starts the list anew.
    later = NOW + timedelta(days=1)
    games.start_plan(later, "warm_up")
    while games.plans.plan:
        throw(games, now=later)
    assert games.plans.done == ["warm_up"]


# -- stored ------------------------------------------------------------------------


def test_a_plan_survives_a_restart_in_the_middle_of_a_step():
    games = planned(player="Alex")
    throw(games, MISS, MISS)
    games.next_plan_step(NOW)
    throw(games, MISS)
    assert games.practice.drills["bobs_27"].index == 1

    restarted = BoardGames(Reports(), NOW)
    restarted.restore(games.stored(), NOW)
    plan = restarted.practice_snapshot()["plan"]
    assert plan["step"] == 2
    assert plan["drill"] == "bobs_27"
    assert plan["darts"] == 1
    assert plan["visits"] == 1
    assert restarted.practice.drill == "bobs_27"
    # The game goes on where it was: one visit at the second double.
    assert restarted.practice.drills["bobs_27"].index == 1
    follow(restarted, board())
    announced = throw(restarted)
    (step,) = named(announced, "plan_step_finished")
    assert step["step"] == 2
    assert step["darts"] == 4
    assert restarted.practice.drill == "singles"
    restarted.next_plan_step(NOW)
    assert restarted.plans.plan is None
    assert restarted.plans.done == ["Evening"]


def test_a_restart_restores_the_finishes_of_the_step():
    games = planned([{"drill": "checkout", "rounds": 9, "options": {"high": 40}}])
    restarted = BoardGames(Reports(), NOW)
    restarted.restore(games.stored(), NOW)
    assert max(restarted.practice.drills["checkout"].scores) == 40
    assert (
        restarted.practice.drills["checkout"].target
        == games.practice.drills["checkout"].target
    )


@pytest.mark.parametrize(
    "broken",
    [
        None,
        "plan",
        {"plan": None},
        {"plan": {"name": "Evening"}, "index": 0},
        {"index": "first"},
        {"index": 9},
        {"index": -1},
        # The game of another step is on the board.
        {"index": 1},
    ],
)
def test_a_broken_plan_in_the_store_starts_without_one(broken):
    games = planned()
    saved = games.stored()
    if isinstance(broken, dict):
        saved["plan"] = {**saved["plan"], **broken}
    else:
        saved["plan"] = broken
    restarted = BoardGames(Reports(), NOW)
    restarted.restore(saved, NOW)
    assert restarted.plans.plan is None
    assert restarted.practice_snapshot()["plan"] is None


def test_broken_counts_in_the_store_start_from_zero():
    games = planned()
    saved = games.stored()
    saved["plan"].update(
        darts="many",
        visits=None,
        started=3,
        results=[
            "x",
            {"darts": "3", "skipped": False},
            {"darts": 3, "skipped": None},
            {"darts": 3, "skipped": True},
        ],
        done_day=3,
        done=["warm_up"],
    )
    restarted = BoardGames(Reports(), NOW)
    restarted.restore(saved, NOW)
    runner = restarted.plans
    assert (runner.darts, runner.visits, runner.started) == (0, 0, "")
    assert runner.results == [{"darts": 3, "skipped": True}]
    assert runner.done == []
    saved["plan"].update(results="none", done_day="2026-10-01", done=["warm_up", 3])
    restarted = BoardGames(Reports(), NOW)
    restarted.restore(saved, NOW)
    assert restarted.plans.results == []
    assert restarted.plans.done == ["warm_up"]


def test_a_store_from_before_the_plans_has_no_plan():
    games = BoardGames(Reports(), NOW)
    games.restore({"practice": {}}, NOW)
    assert games.plans.plan is None
    assert (
        games.practice_snapshot()["plan_of_the_day"]["plan"] == ROTATION[NOW.weekday()]
    )


def test_the_day_of_the_offer_follows_the_time_of_every_step():
    games = BoardGames(Reports(), NOW)
    later = NOW + timedelta(days=1)
    follow(games, board(), now=later)
    assert games.plans.day == later.date()
    games.changed([], NOW)
    assert games.plans.day == NOW.date()


# -- what counts them --------------------------------------------------------------


def test_finished_plans_unlock_the_achievement_of_the_player():
    games = planned([{"drill": "doubles", "darts": 1}], player="Alex")
    announced = throw(games, MISS)
    # The event of the plan comes first, its achievement after it.
    kinds = [kind for kind, _, _ in announced]
    assert kinds.index("plan_finished") < kinds.index("achievement_unlocked")
    unlocked = [
        details
        for details in named(announced, "achievement_unlocked")
        if details["achievement"] == "plans_finished"
    ]
    assert unlocked == [
        {
            "player": 1,
            "name": "Alex",
            "achievement": "plans_finished",
            "tier": 1,
            "tiers": 3,
            "threshold": 1,
        }
    ]
    assert games.progress.players["alex"].counters["plans"] == 1
    assert ACHIEVEMENTS["plans_finished"].tiers == (1, 10, 100)
    assert ACHIEVEMENTS["plans_finished"].tier(10) == 2


def test_a_skip_that_finishes_a_plan_counts_for_the_player_too():
    games = planned(
        [{"drill": "doubles", "darts": 1}, {"drill": "singles"}], player="Alex"
    )
    throw(games, MISS)
    games.next_plan_step(NOW)
    assert games.progress.players["alex"].counters["plans"] == 1


def test_a_stopped_plan_counts_for_nobody():
    games = planned(player="Alex")
    throw(games, MISS)
    games.stop_plan(NOW)
    assert games.progress.players["alex"].counters["plans"] == 0


def test_a_plan_without_a_named_player_unlocks_nothing():
    games = planned([{"drill": "doubles", "darts": 1}])
    announced = throw(games, MISS)
    assert named(announced, "plan_finished")
    assert not named(announced, "achievement_unlocked")


def test_achievements_that_are_off_unlock_quietly_later():
    games = BoardGames(Reports(), NOW)
    games.start_game(501, names=["Alex"])
    games.progress.enable(False, games.practice.profiles, NOW)
    games.start_plan(NOW, steps=[{"drill": "doubles", "darts": 1}])
    follow(games, board())
    assert not named(throw(games, MISS), "achievement_unlocked")
    assert games.progress.players["alex"].counters["plans"] == 1


def test_the_weekly_report_counts_the_finished_plans():
    report = WeeklyReport()
    report.begin(NOW)
    for kind, attributes in (
        ("plan_finished", {"completed": True}),
        ("plan_finished", {"completed": False}),
        ("plan_step_finished", {"completed": True}),
    ):
        report.observe(kind, attributes, NOW)
    assert report.snapshot(0)["plans"] == 1
    restored = WeeklyReport()
    restored.restore(report.stored())
    assert restored.snapshot(0)["plans"] == 1


async def test_the_summary_of_the_week_says_how_many_plans_were_finished(hass):
    caller = Caller()
    await caller.async_load(hass)
    week = {"darts": 10, "training_minutes": 3, "sessions": 1}
    assert caller.summary({**week, "plans": 1}).endswith(" 1 training plan finished.")
    assert caller.summary({**week, "plans": 2}).endswith(" 2 training plans finished.")
    assert "plan" not in caller.summary({**week, "plans": 0})
    assert "plan" not in caller.summary(week)


def finished_plan(**changes):
    return {
        "plan": "doubles_day",
        "plan_name": "Doubles day",
        "completed": True,
        "steps": 3,
        "darts": 120,
        "started": "2026-10-01T19:30:00+00:00",
        "ended": "2026-10-01T20:00:00+00:00",
        **changes,
    }


def test_the_calendar_shows_a_finished_plan():
    journal = TrainingJournal()
    assert journal.add_plan(finished_plan()) is True
    # Announced twice, kept once; only a plan played to its end counts.
    assert journal.add_plan(finished_plan()) is False
    assert journal.add_plan(finished_plan(completed=False)) is False
    assert journal.add_plan(finished_plan(plan_name=3)) is False
    event = journal.latest()
    assert event.summary == "Training plan · Doubles day"
    assert event.description == "3 steps · 120 Darts"
    assert event.uid == "plan-2026-10-01T20:00:00+00:00"
    assert event.start == datetime(2026, 10, 1, 19, 30, tzinfo=UTC)
    found = journal.events(NOW - timedelta(hours=1), NOW)
    assert [one.summary for one in found] == ["Training plan · Doubles day"]


def test_the_calendar_names_a_plan_in_its_language():
    journal = TrainingJournal(lambda: "de")
    journal.add_plan(finished_plan())
    event = journal.latest()
    assert event.summary == "Trainingsplan · Doppel-Tag"
    assert event.description == "3 Schritte · 120 Darts"


@pytest.mark.parametrize(
    ("language", "word"),
    [
        ("en", "step"),
        ("de", "Schritt"),
        ("nl", "stap"),
        ("fr", "étape"),
        ("es", "paso"),
    ],
)
def test_the_calendar_counts_one_step_in_the_singular(language, word):
    journal = TrainingJournal(lambda: language)
    journal.add_plan(finished_plan(steps=1))
    assert journal.latest().description.startswith(f"1 {word} · ")


def test_the_journal_keeps_its_plans_through_a_restart_and_a_merge():
    journal = TrainingJournal()
    journal.add_plan(finished_plan())
    restored = TrainingJournal()
    saved = journal.stored()
    saved["plans"] = [*saved["plans"], "broken", {"plan": "x", "plan_name": "y"}]
    restored.restore(saved)
    assert restored.plans == journal.plans
    assert restored.plans[0]["started"] == "2026-10-01T19:30:00+00:00"
    other = TrainingJournal()
    other.add_plan(finished_plan(ended="2026-10-01T21:00:00+00:00", started=None))
    restored.merge(other)
    assert len(restored.plans) == 2
    assert restored.plans[-1]["started"] is None
    # Without a store of plans, an older journal has none.
    older = TrainingJournal()
    older.restore({"sessions": [], "matches": []})
    assert older.plans == []
    # A year later, the entry goes.
    assert journal._prune(NOW + timedelta(days=400)) is True
    assert journal.plans == []
    assert journal.add_plan(finished_plan(plan=None)) is False
    assert journal.add_plan(finished_plan(ended="never")) is False


# -- the plan as a game of the practice game ----------------------------------------


def test_a_plan_is_for_one_player():
    games = BoardGames(Reports(), NOW)
    games.start_game(501, names=["Alex", "Sam"])
    games.start_plan(NOW, "warm_up")
    assert len(games.practice.players) == 1
    assert isinstance(games.practice, PracticeGame)


# -- in Home Assistant --------------------------------------------------------------


async def test_the_actions_play_a_plan_and_announce_it(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    await hass.services.async_call(
        DOMAIN,
        "start_plan",
        {
            "name": "Evening",
            "steps": [{"drill": "doubles", "darts": 30}, {"drill": "bobs_27"}],
            "player": "Alex",
            "config_entry_id": entry.entry_id,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert state(hass, "sensor", "practice_target") == "D1"
    attributes = hass.states.get(
        entity_id(hass, "sensor", "practice_remaining")
    ).attributes
    assert attributes["plan"]["name"] == "Evening"
    assert attributes["plan"]["step"] == 1
    assert attributes["plan_of_the_day"]["plan"] in PRESETS

    await hass.services.async_call(DOMAIN, "next_plan_step", {}, blocking=True)
    await hass.async_block_till_done()
    assert coordinator.games.practice.drill == "bobs_27"
    assert (
        next(one for one in events if one[0] == "plan_step_finished")[1]["skipped"]
        is True
    )

    await hass.services.async_call(DOMAIN, "stop_plan", {}, blocking=True)
    await hass.async_block_till_done()
    (ended,) = [details for kind, details in events if kind == "plan_finished"]
    assert ended["reason"] == "stopped"
    assert ended["source"] == "training"
    assert coordinator.games.plans.plan is None


async def test_the_actions_say_what_is_wrong(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock)
    for action, data, key in (
        ("start_plan", {"plan": "nothing"}, "unknown_plan"),
        ("start_plan", {"steps": [{"drill": "doubles", "darts": 0}]}, "invalid_plan"),
        ("next_plan_step", {}, "no_plan"),
        ("stop_plan", {}, "no_plan"),
    ):
        with pytest.raises(ServiceValidationError) as refused:
            await hass.services.async_call(DOMAIN, action, data, blocking=True)
        assert refused.value.translation_key == key


async def test_a_plan_goes_on_after_a_restart_of_the_integration(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    await hass.services.async_call(
        DOMAIN, "start_plan", {"plan": "doubles_day"}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "next_plan_step", {}, blocking=True)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.local
    coordinator.games.plans.darts, coordinator.games.plans.visits = 6, 2
    await coordinator.store.async_save()

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    games = entry.runtime_data.local.games
    assert games.practice.drill == "bobs_27"
    assert games.practice_snapshot()["plan"]["step"] == 2
    assert games.practice_snapshot()["plan"]["darts"] == 6
    assert games.practice_snapshot()["plan"]["visits"] == 2


async def test_the_offer_changes_at_midnight(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    today = dt_util.now().date()
    coordinator.games.plans.day = today - timedelta(days=1)
    coordinator._async_new_day(dt_util.now())
    assert coordinator.games.plans.day == today
    assert (
        coordinator.data["practice"]["plan_of_the_day"]["plan"]
        == coordinator.games.plans.today().key
    )


async def test_the_options_keep_own_plans(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    good = [{"name": "Evening", "steps": [{"drill": "doubles", "darts": 30}]}]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    # A plan that is not valid stays in the form, with what the user chose.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "online_bridge": False,
            "online_bridge_remote": True,
            "plans": [{"name": "Evening", "steps": [{"drill": "501"}]}],
        },
    )
    assert result["step_id"] == "init"
    assert result["errors"] == {"plans": "invalid_plans"}
    defaults = {str(key): key.default() for key in result["data_schema"].schema}
    assert defaults["online_bridge_remote"] is True
    assert defaults["plans"][0]["name"] == "Evening"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"online_bridge": False, "online_bridge_remote": False, "plans": good},
    )
    await hass.async_block_till_done()
    assert entry.options["plans"] == good
    games = entry.runtime_data.local.games
    assert [plan.name for plan in games.plans.custom] == ["Evening"]
    await hass.services.async_call(
        DOMAIN, "start_plan", {"plan": "evening"}, blocking=True
    )
    assert games.practice.drill == "doubles"

    # Without plans, the option goes again.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        # What the editor gives once it was emptied.
        {"online_bridge": False, "online_bridge_remote": False, "plans": {}},
    )
    await hass.async_block_till_done()
    assert "plans" not in entry.options
    assert entry.runtime_data.local.games.plans.custom == ()
