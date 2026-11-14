"""The weekly report blueprint, on made-up and on real board events."""

from pathlib import Path

import pytest
from pytest_homeassistant.common import (
    async_fire_time_changed,
    async_mock_service,
)

from .local_helpers import EVENTS, T20, automate, board, entity_id, fire, setup_local
from .test_practice_setup import throw

pytestmark = pytest.mark.usefixtures("blueprint_folder")

WEEK = {
    "week_start": "2026-09-27T22:00:00+00:00",
    "week_end": "2026-10-04T22:00:00+00:00",
    "darts": 312,
    "visits": 104,
    "sessions": 3,
    "training_minutes": 95,
    "average": 54.25,
    "average_change": 2.14,
    "highest_visit": 140,
    "scores_180": 1,
    "checkout_rate": 31.25,
    "darts_at_double": 16,
    "checkouts": 5,
    "legs": 5,
    "matches": 2,
    "streak": 4,
    "daily_goals": 2,
    "personal_bests": [
        {"record": "highest_visit", "value": 140, "name": None},
        {"record": "fewest_darts_501", "value": 18, "name": "Lea"},
    ],
    "source": "schedule",
}


async def test_the_weekly_report_sends_a_summary(hass):
    notify = async_mock_service(hass, "notify", "phone")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "weekly_report",
        {
            "board_events": EVENTS,
            "notify_actions": [
                {
                    "action": "notify.phone",
                    "data": {"title": "{{ title }}", "message": "{{ message }}"},
                }
            ],
        },
    )
    fire(hass, "weekly_report", **WEEK)
    await hass.async_block_till_done()
    fire(hass, "visit_completed", score=180, darts=3, segments=["T20"] * 3)
    await hass.async_block_till_done()
    assert [call.data for call in notify] == [
        {
            "title": "Your darts week",
            "message": "312 darts in 95 minutes at the board, 3 sessions. "
            "3-dart average 54.2 (+2.1 on the week before). Best visit 140, 1 × 180. "
            "Checkout rate 31.2 %. 4 days in a row. 2 new personal bests.",
        }
    ]


async def test_a_quiet_week_reads_short_or_is_skipped(hass):
    notifications = async_mock_service(hass, "persistent_notification", "create")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "weekly_report", {"board_events": EVENTS, "minimum_darts": 10})
    quiet = {
        **WEEK,
        "darts": 9,
        "sessions": 1,
        "training_minutes": 3,
        "average": 20.0,
        "average_change": None,
        "highest_visit": None,
        "scores_180": 0,
        "checkout_rate": None,
        "streak": 1,
        "personal_bests": [],
    }
    fire(hass, "weekly_report", **quiet)
    await hass.async_block_till_done()
    assert not notifications
    fire(hass, "weekly_report", **{**quiet, "darts": 10, "average_change": -3.25})
    await hass.async_block_till_done()
    fire(
        hass, "weekly_report", **{**quiet, "darts": 12, "average": None, "sessions": 0}
    )
    await hass.async_block_till_done()
    fire(
        hass,
        "weekly_report",
        **{
            **quiet,
            "darts": 30,
            "training_minutes": 1,
            "highest_visit": 60,
            "streak": 0,
            "personal_bests": [{"record": "doubles"}],
        },
    )
    await hass.async_block_till_done()
    assert [call.data for call in notifications] == [
        {
            "title": "Your darts week",
            "message": "10 darts in 3 minutes at the board, 1 session. "
            "3-dart average 20.0 (-3.2 on the week before). 1 day in a row.",
            "notification_id": "homedarts_weekly_report",
        },
        {
            "title": "Your darts week",
            "message": "12 darts in 3 minutes at the board. 1 day in a row.",
            "notification_id": "homedarts_weekly_report",
        },
        {
            "title": "Your darts week",
            "message": "30 darts in 1 minute at the board, 1 session. "
            "3-dart average 20.0. Best visit 60. 1 new personal best.",
            "notification_id": "homedarts_weekly_report",
        },
    ]


# The German message of the documentation (docs/automations.de.md).
GERMAN_MESSAGE = (
    "{{ darts }} Darts{{ ' in ' ~ training_minutes ~ ' Minuten' if training_minutes else '' }}"
    "{{ ', 3-Dart-Average ' ~ (average | replace('.', ',')) ~ (' (' ~ ('+' if average_change > 0 else '')"
    " ~ (average_change | replace('.', ',')) ~ ')' if average_change is not none else '')"
    " if average is not none else '' }}"
    "{{ ', ' ~ scores_180 ~ ' × 180' if scores_180 else '' }}"
    "{{ ', ' ~ streak ~ (' Tag' if streak == 1 else ' Tage') ~ ' in Folge' if streak else '' }}."
)


async def test_the_german_message_of_the_documentation(hass):
    notify = async_mock_service(hass, "notify", "phone")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "weekly_report",
        {
            "board_events": EVENTS,
            "report_title": "Deine Dartwoche",
            "report_message": GERMAN_MESSAGE,
            "notify_actions": [
                {
                    "action": "notify.phone",
                    "data": {"title": "{{ title }}", "message": "{{ message }}"},
                }
            ],
        },
    )
    fire(hass, "weekly_report", **WEEK)
    await hass.async_block_till_done()
    quiet = {"average": None, "training_minutes": 0, "scores_180": 0, "streak": 1}
    fire(hass, "weekly_report", **{**WEEK, **quiet, "darts": 12})
    await hass.async_block_till_done()
    assert [call.data["title"] for call in notify] == ["Deine Dartwoche"] * 2
    assert [call.data["message"] for call in notify] == [
        "312 Darts in 95 Minuten, 3-Dart-Average 54,2 (+2,1), 1 × 180, 4 Tage in Folge.",
        "12 Darts, 1 Tag in Folge.",
    ]


async def test_the_report_of_a_real_week(hass, aioclient_mock, freezer):
    notify = async_mock_service(hass, "notify", "phone")
    freezer.move_to("2026-09-30 18:00:00-07:00")
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await automate(
        hass,
        "weekly_report",
        {
            "board_events": entity_id(hass, "event", "board_events"),
            "notify_actions": [
                {"action": "notify.phone", "data": {"message": "{{ message }}"}}
            ],
        },
    )
    await throw(hass, coordinator, T20, T20, T20)
    # The report week ends on Monday at midnight in the test time zone.
    freezer.move_to("2026-10-05 00:00:00-07:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [call.data["message"] for call in notify] == [
        "3 darts. 3-dart average 180.0. Best visit 180, 1 × 180."
    ]


@pytest.mark.parametrize("document", ["docs/automations.md", "docs/automations.de.md"])
def test_the_documentation_shows_the_tested_german_message(document):
    text = (Path(__file__).parents[1] / document).read_text(encoding="utf-8")
    assert GERMAN_MESSAGE in text
