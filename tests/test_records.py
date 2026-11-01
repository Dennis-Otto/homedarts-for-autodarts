"""Personal bests, the training streak and the daily goal."""

from datetime import UTC, date, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from custom_components.homedarts.records import (
    DAILY_GOAL_MAX,
    RECORDS,
    SESSION_DARTS,
    PersonalRecords,
)

MONDAY = datetime(2026, 9, 21, 20, 0, tzinfo=UTC)


def darts(records: PersonalRecords, count: int, when: datetime = MONDAY) -> list:
    events = []
    for _ in range(count):
        events += records.observe("dart_detected", {}, when)
    return events


def test_the_first_value_sets_a_record_quietly_and_beating_it_announces_it():
    records = PersonalRecords()
    leg = {
        "game": 501,
        "player": 1,
        "name": "Alex",
        "darts": 24,
        "checkout": 40,
        "double_out": True,
    }
    assert records.observe("leg_won", leg, MONDAY) == []
    assert records.snapshot(MONDAY.date())["bests"] == {
        "highest_checkout": 40,
        "fewest_darts_501": 24,
    }
    # Equal is no personal best; fewer darts and a higher checkout are.
    assert records.observe("leg_won", leg, MONDAY) == []
    events = records.observe("leg_won", {**leg, "darts": 18, "checkout": 121}, MONDAY)
    assert events == [
        (
            "personal_best",
            {
                "record": "highest_checkout",
                "value": 121,
                "previous": 40,
                "name": "Alex",
            },
        ),
        (
            "personal_best",
            {"record": "fewest_darts_501", "value": 18, "previous": 24, "name": "Alex"},
        ),
    ]
    latest = records.snapshot(MONDAY.date())["latest"]
    assert (
        latest["record"] == "fewest_darts_501" and latest["date"] == MONDAY.isoformat()
    )
    # A worse leg changes nothing.
    assert records.observe("leg_won", {**leg, "darts": 30, "checkout": 2}, MONDAY) == []


def test_every_kind_of_record_has_its_source():
    records = PersonalRecords()
    sources = [
        ("visit_completed", {"score": 60, "darts": 3}, {"score": 100, "darts": 3}),
        ("leg_won", {"game": "cricket", "mpr": 2.1}, {"game": "cricket", "mpr": 3.4}),
        (
            "drill_finished",
            {"drill": "around_the_clock", "darts": 60},
            {"drill": "around_the_clock", "darts": 45},
        ),
        (
            "drill_finished",
            {"drill": "doubles", "darts": 90},
            {"drill": "doubles", "darts": 70},
        ),
        (
            "drill_finished",
            {"drill": "bobs_27", "score": 50, "completed": True},
            {"drill": "bobs_27", "score": 120, "completed": True},
        ),
        (
            "checkout_attempt",
            {"drill": "checkout_121", "target": 124, "success": True},
            {"drill": "checkout_121", "target": 130, "success": True},
        ),
        *(
            (
                "drill_finished",
                {"drill": drill, "score": 20},
                {"drill": drill, "score": 40},
            )
            for drill in ("catch_40", "jdc_challenge", "singles")
        ),
        (
            "session_ended",
            {"darts": SESSION_DARTS, "average": 45.5},
            {"darts": 90, "average": 51.2},
        ),
    ]
    announced = []
    for kind, first, better in sources:
        assert records.observe(kind, first, MONDAY) == []
        announced += [
            event["record"] for _, event in records.observe(kind, better, MONDAY)
        ]
    assert announced == [
        "highest_visit",
        "best_cricket_mpr",
        "around_the_clock",
        "doubles",
        "bobs_27",
        "checkout_121",
        "catch_40",
        "jdc_challenge",
        "singles",
        "best_session_average",
    ]
    bests = records.snapshot(MONDAY.date())["bests"]
    assert set(bests) <= set(RECORDS)
    assert bests["bobs_27"] == 120 and bests["best_session_average"] == 51.2


def test_merged_visits_lost_games_and_short_sessions_set_no_record():
    records = PersonalRecords()
    for kind, attributes in (
        ("visit_completed", {"score": 180, "darts": 6}),
        ("drill_finished", {"drill": "bobs_27", "score": 300, "completed": False}),
        ("session_ended", {"darts": SESSION_DARTS - 1, "average": 99.0}),
        ("leg_won", {"game": 401, "darts": 9, "checkout": 170, "double_out": True}),
        ("leg_won", {"game": 501, "darts": "x", "checkout": -5, "double_out": True}),
        # Without double out, a leg finishes more easily: no record.
        ("leg_won", {"game": 501, "darts": 9, "checkout": 180, "double_out": False}),
        ("leg_won", {"game": 301, "darts": 6, "checkout": 141}),
        ("visit_completed", {"score": 0, "darts": 3}),
        ("dart_corrected", {"score": 60}),
        # A missed 121 checkout, or a checkout of the checkout training.
        ("checkout_attempt", {"drill": "checkout_121", "target": 150}),
        ("checkout_attempt", {"drill": "checkout", "target": 150, "success": True}),
    ):
        assert records.observe(kind, attributes, MONDAY) == []
    assert records.snapshot(MONDAY.date())["bests"] == {}


def test_a_deleted_player_leaves_the_records_without_a_name():
    records = PersonalRecords()
    leg = {"game": 501, "name": "Alex", "darts": 24, "checkout": 40, "double_out": True}
    records.observe("leg_won", leg, MONDAY)
    records.observe("leg_won", {**leg, "darts": 18}, MONDAY)
    records.observe("leg_won", {**leg, "name": "Sam", "checkout": 60}, MONDAY)
    records.forget(" alex ")
    bests = records.stored()["bests"]
    assert bests["fewest_darts_501"]["name"] is None
    assert bests["fewest_darts_501"]["value"] == 18
    assert bests["highest_checkout"]["name"] == "Sam"
    assert records.stored()["latest"]["name"] == "Sam"
    records.forget("Sam")
    assert records.stored()["latest"]["name"] is None
    records.latest = None
    records.forget("Nobody")
    assert records.stored()["latest"] is None


def test_a_renamed_player_takes_the_records_along():
    records = PersonalRecords()
    leg = {
        "game": 501,
        "name": "Sammy",
        "darts": 18,
        "checkout": 40,
        "double_out": True,
    }
    records.observe("leg_won", leg, MONDAY)
    records.observe("leg_won", {**leg, "name": "sam", "checkout": 60}, MONDAY)
    records.observe("leg_won", {**leg, "name": "Kim", "darts": 15}, MONDAY)
    records.rename(" SAMMY ", "Sam")
    bests = records.stored()["bests"]
    # Records of the name merged into keep the new spelling, too.
    assert bests["highest_checkout"]["name"] == "Sam"
    assert bests["fewest_darts_501"]["name"] == "Kim"
    assert records.stored()["latest"]["name"] == "Kim"
    records.rename("Kim", "Kimberly")
    assert records.stored()["latest"]["name"] == "Kimberly"
    records.latest = None
    records.rename("Nobody", "Somebody")
    assert records.stored()["latest"] is None


def test_an_undone_visit_takes_back_its_bests_but_not_its_darts():
    records, day = PersonalRecords(), MONDAY.date()
    records.set_goal(3, day)
    leg = {"game": 501, "name": "Alex", "darts": 24, "checkout": 40, "double_out": True}
    records.observe("visit_completed", {"darts": 3, "score": 100}, MONDAY)
    records.observe("leg_won", leg, MONDAY)
    checkpoint = records.checkpoint()
    # The checkpoint is a copy, which a change of the records leaves alone.
    records.forget("Alex")
    # A misread visit and a winning visit that the players undo.
    darts(records, 3)
    records.observe("visit_completed", {"darts": 3, "score": 180}, MONDAY)
    records.observe("leg_won", {**leg, "darts": 9, "checkout": 121}, MONDAY)
    assert records.latest["record"] == "fewest_darts_501"
    records.rewind(checkpoint)
    assert records.snapshot(day)["bests"] == {
        "highest_visit": 100,
        "highest_checkout": 40,
        "fewest_darts_501": 24,
    }
    assert records.bests["highest_checkout"]["name"] == "Alex"
    assert records.latest is None
    # The darts were thrown: the day, the streak and the goal keep them.
    assert (records.darts_today, records.streak, records.goal_day) == (3, 1, day)


def test_darts_count_per_day_and_the_goal_is_announced_once():
    records = PersonalRecords()
    records.set_goal(3, MONDAY.date())
    assert darts(records, 2) == []
    assert darts(records, 1) == [
        ("daily_goal_reached", {"goal": 3, "darts": 3, "streak": 1})
    ]
    assert darts(records, 5) == []
    snapshot = records.snapshot(MONDAY.date())
    assert (
        snapshot["darts_today"],
        snapshot["goal_reached"],
        snapshot["progress"],
    ) == (
        8,
        True,
        100.0,
    )
    # A new day starts from zero, and the goal can be reached again.
    tuesday = MONDAY + timedelta(days=1)
    assert records.snapshot(tuesday.date())["darts_today"] == 0
    assert records.snapshot(tuesday.date())["goal_reached"] is False
    assert darts(records, 3, tuesday)[-1][1]["streak"] == 2
    # A lower goal that today's darts already reach is not announced.
    records.set_goal(2, tuesday.date())
    assert records.snapshot(tuesday.date())["goal_reached"] is True
    records.set_goal(50, tuesday.date())
    assert records.snapshot(tuesday.date())["progress"] == 6.0
    records.set_goal(0, tuesday.date())
    assert records.snapshot(tuesday.date())["progress"] is None
    assert records.snapshot(tuesday.date())["goal_reached"] is False
    records.set_goal(DAILY_GOAL_MAX + 1, tuesday.date())
    assert records.goal == 0


def test_the_streak_counts_days_in_a_row_and_survives_until_tomorrow_ends():
    records = PersonalRecords()
    day = MONDAY
    for _ in range(3):
        darts(records, 1, day)
        day += timedelta(days=1)
    # Three days in a row; the fourth day has no darts yet.
    snapshot = records.snapshot(day.date())
    assert (snapshot["streak"], snapshot["trained_today"]) == (3, False)
    assert snapshot["last_day"] == "2026-09-23"
    # A day without darts breaks it; the best streak stays.
    later = day + timedelta(days=1)
    assert records.snapshot(later.date())["streak"] == 0
    darts(records, 1, later)
    snapshot = records.snapshot(later.date())
    assert (snapshot["streak"], snapshot["best_streak"]) == (1, 3)


def test_records_survive_a_restart_and_invalid_data_is_dropped():
    records = PersonalRecords()
    records.set_goal(100, MONDAY.date())
    darts(records, 12)
    records.observe("visit_completed", {"score": 60, "darts": 3}, MONDAY)
    records.observe("visit_completed", {"score": 140, "darts": 3}, MONDAY)
    restored = PersonalRecords()
    restored.restore(records.stored())
    assert restored.stored() == records.stored()
    assert restored.snapshot(MONDAY.date()) == records.snapshot(MONDAY.date())

    broken = PersonalRecords()
    broken.restore(
        {
            "bests": {
                "highest_visit": {"value": 100, "date": "2026-09-21T20:00:00"},
                "unknown": {"value": 1, "date": "2026-09-21"},
                "doubles": {"value": -1, "date": "2026-09-21"},
                "bobs_27": {"value": 50},
                "fewest_darts_501": "x",
            },
            "latest": {"record": "nope", "date": "2026-09-21"},
            "streak": -2,
            "best_streak": "3",
            "last_day": "yesterday",
            "day": 5,
            "darts_today": 1.5,
            "goal": DAILY_GOAL_MAX + 10,
        }
    )
    snapshot = broken.snapshot(date(2026, 9, 21))
    assert snapshot["bests"] == {"highest_visit": 100}
    assert snapshot["latest"] is None
    assert (snapshot["streak"], snapshot["best_streak"], snapshot["last_day"]) == (
        0,
        0,
        None,
    )
    assert (snapshot["darts_today"], snapshot["goal"]) == (0, 0)
    broken.restore(None)
    assert broken.snapshot(date(2026, 9, 21))["bests"] == {"highest_visit": 100}
    # Stored data may hold anything, even a list for a record.
    broken.restore({"latest": {"record": ["doubles"], "date": "2026-09-21"}})
    assert broken.latest is None


@given(
    st.lists(
        st.tuples(st.integers(0, 3), st.integers(0, 200), st.integers(1, 40)),
        max_size=60,
    )
)
def test_any_days_keep_the_streak_and_the_bests_consistent(days):
    records = PersonalRecords()
    day = MONDAY
    for skip, score, count in days:
        day += timedelta(days=skip)
        darts(records, count, day)
        records.observe("visit_completed", {"score": score, "darts": 3}, day)
        snapshot = records.snapshot(day.date())
        assert 1 <= snapshot["streak"] <= snapshot["best_streak"]
        assert snapshot["trained_today"] is True
        assert snapshot["darts_today"] >= count
    scores = [score for _, score, _ in days if score]
    if scores:
        assert records.snapshot(day.date())["bests"]["highest_visit"] == max(scores)


def test_a_higher_daily_goal_is_reached_anew():
    records, day = PersonalRecords(), MONDAY.date()
    records.set_goal(2, day)
    assert [kind for kind, _ in darts(records, 2)] == ["daily_goal_reached"]
    assert records.snapshot(day)["goal_reached"] is True
    records.set_goal(5, day)
    assert records.snapshot(day)["goal_reached"] is False
    assert darts(records, 2) == []
    assert darts(records, 1) == [
        ("daily_goal_reached", {"goal": 5, "darts": 5, "streak": 1})
    ]
    # A lower goal is reached at once, quietly; a goal set on another day
    # leaves the day it was reached.
    records.set_goal(3, day)
    assert records.snapshot(day)["goal_reached"] is True
    records.set_goal(9, day + timedelta(days=1))
    assert records.goal_day == day
