"""The weekly report: its week in local time, what it counts and what it keeps."""

import copy
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.homedarts.report import (
    REPORT_BESTS,
    WeeklyReport,
    report_week,
)

BERLIN = ZoneInfo("Europe/Berlin")
UTC = dt_util.UTC


@pytest.fixture(autouse=True)
def berlin():
    """Weeks follow Home Assistant's time zone, with daylight saving time."""
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(BERLIN)
    yield
    dt_util.set_default_time_zone(previous)


def local(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=BERLIN)


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def test_the_week_starts_at_the_report_time_in_local_time():
    monday = (0, time(0, 0))
    week = (utc("2026-09-27 22:00"), utc("2026-10-04 22:00"))
    assert report_week(local("2026-09-30 12:00"), *monday) == week
    # The report time itself starts the next week.
    assert report_week(local("2026-09-28 00:00"), *monday) == week
    assert report_week(local("2026-09-27 23:59"), *monday) == (
        utc("2026-09-20 22:00"),
        utc("2026-09-27 22:00"),
    )
    sunday_evening = (6, time(20, 0))
    assert report_week(local("2026-10-04 19:59"), *sunday_evening) == (
        utc("2026-09-27 18:00"),
        utc("2026-10-04 18:00"),
    )
    assert report_week(local("2026-10-04 20:00"), *sunday_evening)[0] == utc(
        "2026-10-04 18:00"
    )


def test_a_week_with_a_clock_change_is_an_hour_longer_or_shorter():
    monday = (0, time(0, 0))
    start, end = report_week(local("2026-10-22 12:00"), *monday)
    assert (start, end) == (utc("2026-10-18 22:00"), utc("2026-10-25 23:00"))
    assert end - start == timedelta(days=7, hours=1)
    start, end = report_week(local("2027-03-24 12:00"), *monday)
    assert (start, end) == (utc("2027-03-21 23:00"), utc("2027-03-28 22:00"))
    assert end - start == timedelta(days=7, hours=-1)
    # A report time the clock skips counts in the time before the change.
    assert report_week(local("2027-03-28 12:00"), 6, time(2, 30))[0] == utc(
        "2027-03-28 01:30"
    )


def dart(report: WeeklyReport, now: datetime) -> None:
    report.observe("dart_detected", {"dart_index": 1}, now)


def test_darts_visits_and_results_count_for_the_week():
    report = WeeklyReport()
    report.begin(local("2026-09-30 12:00"))
    start = local("2026-09-30 18:00")
    # Darts less than five minutes apart are training time; a longer pause is not.
    for seconds in (0, 30, 630, 650):
        dart(report, start + timedelta(seconds=seconds))
    for score, darts in ((60, 3), (180, 3), (40, 5), (0, 0)):
        report.observe("visit_completed", {"score": score, "darts": darts}, start)
    report.observe("session_ended", {"darts": 30}, start)
    report.observe("session_ended", {"darts": 0}, start)
    # Legs and matches announced with a winning dart count once booked.
    report.observe("leg_won", {"game": 501}, start)
    report.observe("match_won", {"game": 501}, start)
    report.booked("leg_won")
    report.booked("match_won")
    report.booked("turn_changed")
    report.observe("daily_goal_reached", {"goal": 3}, start)
    for value in range(REPORT_BESTS + 2):
        report.observe(
            "personal_best",
            {"record": "highest_visit", "value": value, "previous": 1, "name": None},
            start,
        )
    report.observe("personal_best", {"value": 3}, start)
    report.observe("turn_changed", {"player": 2}, start)
    snapshot = report.snapshot(streak=4)
    bests = snapshot.pop("personal_bests")
    assert snapshot == {
        "week_start": "2026-09-27T22:00:00+00:00",
        "week_end": "2026-10-04T22:00:00+00:00",
        "darts": 4,
        "visits": 3,
        "sessions": 1,
        "training_minutes": 1,
        # Points per three darts of every visit, merged ones included.
        "average": 76.36,
        "average_change": None,
        "highest_visit": 180,
        "scores_180": 1,
        "checkout_rate": None,
        "darts_at_double": 0,
        "checkouts": 0,
        "legs": 1,
        "matches": 1,
        "streak": 4,
        "daily_goals": 1,
    }
    assert len(bests) == REPORT_BESTS
    assert bests[0] == {"record": "highest_visit", "value": 11, "name": None}


def leg(game, minute: int) -> dict:
    """A leg of the practice game's history, as it stores it."""
    return {"game": game, "player": 1, "ended": f"2026-09-30T18:{minute:02d}:00+00:00"}


def test_x01_legs_bring_darts_at_a_double_and_checkouts():
    report = WeeklyReport()
    report.begin(local("2026-09-30 12:00"))
    # Before any X01 leg; the first look only learns what is there.
    assert report.book_legs([leg("cricket", 1)], []) is True
    assert report.book_legs([leg("cricket", 1)], []) is False
    legs = [leg(501, 10), leg("cricket", 5)]
    stats = [{"at_double": 3, "checkouts": 1}]
    assert report.book_legs(legs, stats) is True
    # Cricket and party legs have no statistics record of their own.
    legs = [leg("killer", 30), leg(301, 20), leg(501, 10), leg("cricket", 5)]
    stats = [{"at_double": 1, "checkouts": 0}, *stats]
    assert report.book_legs(legs, stats) is True
    assert report.book_legs(legs, stats) is False
    snapshot = report.snapshot(0)
    assert (snapshot["darts_at_double"], snapshot["checkouts"]) == (4, 1)
    assert snapshot["checkout_rate"] == 25.0
    # A first look learns the newest X01 leg without counting it.
    fresh = WeeklyReport()
    assert fresh.book_legs(legs, stats) is True
    assert fresh.last_leg == "2026-09-30T18:20:00+00:00"
    assert fresh.snapshot(0)["darts_at_double"] == 0


def test_the_report_ends_the_week_and_compares_it_with_the_last():
    report = WeeklyReport()
    assert report.rollover(local("2026-10-05 00:00"), 0) is None
    report.begin(local("2026-09-30 12:00"))
    report.observe("visit_completed", {"score": 45, "darts": 3}, local("2026-10-01"))
    assert report.rollover(local("2026-10-04 23:59"), 1) is None
    first = report.rollover(local("2026-10-05 00:00"), 2)
    assert first is not None
    assert (first["average"], first["average_change"], first["streak"]) == (
        45.0,
        None,
        2,
    )
    assert report.last == first
    assert report.started == utc("2026-10-04 22:00")
    assert report.snapshot(0)["visits"] == 0
    report.observe("visit_completed", {"score": 60, "darts": 3}, local("2026-10-06"))
    assert report.snapshot(0)["average_change"] == 15.0
    # After three weeks without Home Assistant, the report covers its own week.
    second = report.rollover(local("2026-10-28 09:00"), 0)
    assert second["week_start"] == "2026-10-04T22:00:00+00:00"
    assert second["week_end"] == "2026-10-11T22:00:00+00:00"
    assert report.started == utc("2026-10-25 23:00")


def test_a_new_report_time_ends_the_running_week_at_its_next_occurrence():
    report = WeeklyReport()
    report.set_schedule(6, time(20, 15, 30), local("2026-09-30 12:00"))
    assert (report.started, report.ends) == (
        utc("2026-09-27 18:15"),
        utc("2026-10-04 18:15"),
    )
    assert report.time == time(20, 15)
    report.set_schedule(2, time(0, 0), local("2026-10-01 12:00"))
    assert report.started == utc("2026-09-27 18:15")
    assert report.ends == utc("2026-10-06 22:00")


def test_the_report_survives_a_restart():
    report = WeeklyReport()
    report.set_schedule(4, time(18, 30), local("2026-09-30 12:00"))
    dart(report, local("2026-09-30 18:00"))
    report.observe("visit_completed", {"score": 100, "darts": 3}, local("2026-09-30"))
    report.observe(
        "personal_best",
        {"record": "highest_visit", "value": 100, "name": "Lea"},
        local("2026-09-30"),
    )
    report.book_legs([leg(501, 12)], [{"at_double": 2, "checkouts": 1}])
    report.last = report.snapshot(2)
    restored = WeeklyReport()
    restored.restore(report.stored())
    assert restored.stored() == report.stored()
    assert restored.stored()["time"] == "18:30"


@pytest.mark.parametrize(
    "saved",
    [
        None,
        [],
        {
            "weekday": 9,
            "time": "25:00",
            "started": "2026-10-04T22:00:00+00:00",
            "ends": "2026-09-27T22:00:00+00:00",
            "counts": {"darts": -1, "visits": "3", "points": 2.5},
            "highest_visit": True,
            "bests": [
                {"record": 1},
                "x",
                {"record": "doubles", "value": "9", "name": ""},
            ],
            "last_dart": "yesterday",
            "last_leg": "yesterday",
            "last": {"week_start": "2026-09-20T22:00:00+00:00"},
        },
        {"weekday": "monday", "time": None, "counts": [], "bests": {}, "last": []},
    ],
)
def test_broken_storage_starts_a_fresh_report(saved):
    report = WeeklyReport()
    report.restore(saved)
    stored = report.stored()
    assert stored["weekday"] == 0 and stored["time"] == "00:00"
    assert stored["started"] is None and stored["ends"] is None
    assert set(stored["counts"].values()) == {0}
    assert stored["highest_visit"] == 0
    assert stored["last_dart"] is None and stored["last_leg"] is None
    assert stored["last"] is None
    assert all(best["record"] == "doubles" for best in stored["bests"])


def test_a_stored_report_keeps_only_valid_values():
    report = WeeklyReport()
    report.restore(
        {
            "weekday": 6,
            "time": "07:45:12+02:00",
            "last": {
                "week_start": "2026-09-20T22:00:00+00:00",
                "week_end": "2026-09-27T22:00:00+00:00",
                "darts": 99,
                "average": float("nan"),
                "average_change": -1.5,
                "streak": "3",
                "personal_bests": [{"record": "highest_visit", "value": 140}, None],
            },
        }
    )
    assert (report.weekday, report.time) == (6, time(7, 45))
    last = report.last
    assert (last["darts"], last["average"], last["average_change"]) == (99, None, -1.5)
    assert last["streak"] == 0
    assert last["personal_bests"] == [
        {"record": "highest_visit", "value": 140, "name": None}
    ]


def test_an_undone_visit_leaves_the_week_as_it_was_before():
    report = WeeklyReport()
    report.begin(local("2026-09-30 12:00"))
    dart(report, local("2026-09-30 18:00"))
    report.book_legs([leg(501, 1)], [{"at_double": 1, "checkouts": 0}])
    before = report.stored()
    report.observe("visit_completed", {"score": 180, "darts": 3}, local("2026-09-30"))
    report.booked("leg_won")
    report.book_legs(
        [leg(501, 9), leg(501, 1)],
        [{"at_double": 2, "checkouts": 1}, {"at_double": 1, "checkouts": 0}],
    )
    assert report.rewind(before) is True
    assert report.stored() == before
    # A week that ended since stays as it was reported.
    report.observe("visit_completed", {"score": 60, "darts": 3}, local("2026-09-30"))
    report.rollover(local("2026-10-05 00:00"), 0)
    assert report.rewind(before) is False
    assert report.last["visits"] == 1


def test_a_deleted_player_leaves_the_bests_of_the_report():
    report = WeeklyReport()
    report.begin(local("2026-09-30 12:00"))
    for name in ("Alex", "Sam"):
        report.observe(
            "personal_best",
            {"record": "highest_visit", "value": 100, "name": name},
            local("2026-09-30"),
        )
    report.last = report.snapshot(0)
    report.forget(" alex ")
    assert [best["name"] for best in report.bests] == ["Sam", None]
    assert [best["name"] for best in report.last["personal_bests"]] == ["Sam", None]
    WeeklyReport().forget("Alex")


def test_a_deleted_player_leaves_the_published_report_as_it_was():
    """The weekly_report event and the sensor keep the report they published:
    the name goes from a new report, so the sensor sees the change."""
    report = WeeklyReport()
    report.begin(local("2026-09-30 12:00"))
    report.observe(
        "personal_best",
        {"record": "highest_visit", "value": 100, "name": "Alex"},
        local("2026-09-30"),
    )
    published = report.rollover(local("2026-10-05 00:00"), 0)
    kept = copy.deepcopy(published)
    report.forget("Alex")
    assert published == kept and report.last is not published
    assert report.last["personal_bests"] == [
        {"record": "highest_visit", "value": 100, "name": None}
    ]


def test_a_renamed_player_takes_the_bests_of_the_report_along():
    report = WeeklyReport()
    report.begin(local("2026-09-30 12:00"))
    for name in ("Sammy", "sam", "Kim"):
        report.observe(
            "personal_best",
            {"record": "highest_visit", "value": 100, "name": name},
            local("2026-09-30"),
        )
    published = report.rollover(local("2026-10-05 00:00"), 0)
    kept = copy.deepcopy(published)
    report.observe(
        "personal_best",
        {"record": "highest_visit", "value": 140, "name": "Sammy"},
        local("2026-10-05 12:00"),
    )
    report.rename("sammy", "Sam")
    assert [best["name"] for best in report.bests] == ["Sam"]
    assert [best["name"] for best in report.last["personal_bests"]] == [
        "Kim",
        "Sam",
        "Sam",
    ]
    assert published == kept and report.last is not published
    WeeklyReport().rename("Sam", "Sammy")
