"""The training calendar when the clocks change.

The clocks of US/Pacific, the time zone of the test harness, go back at 09:00 UTC on
2026-11-01, and those of Europe/Berlin at 01:00 UTC on 2026-10-25: the hour before
that moment repeats, with another offset. They go forward at 10:00 UTC on 2026-03-08
and at 01:00 UTC on 2026-03-29: the hour after that moment doesn't exist.
"""

from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util

from .local_helpers import T20, board, entity_id, setup_local
from .test_practice_setup import throw


async def calendar_events(hass) -> list[dict]:
    """Every event of the calendar around the frozen moment."""
    calendar = entity_id(hass, "calendar", "training_calendar")
    now = dt_util.now()
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": calendar,
            "start_date_time": (now - timedelta(hours=6)).isoformat(),
            "end_date_time": (now + timedelta(hours=6)).isoformat(),
        },
        blocking=True,
        return_response=True,
    )
    return response[calendar]["events"]


async def train(hass, aioclient_mock, freezer, zone, begin, seconds):
    """A session of one dart, from the moment it begins for so many seconds; the
    coordinator of its board."""
    await hass.config.async_set_time_zone(zone)
    freezer.move_to(begin)
    entry = await setup_local(hass, aioclient_mock, state=board())
    await throw(hass, entry.runtime_data.local, T20)
    freezer.tick(timedelta(seconds=seconds))
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", "reset_training")},
        blocking=True,
    )
    await hass.async_block_till_done()
    return entry.runtime_data.local


def calendar_state(hass):
    return hass.states.get(entity_id(hass, "calendar", "training_calendar"))


def length(event: dict) -> timedelta:
    return dt_util.parse_datetime(event["end"]) - dt_util.parse_datetime(event["start"])


@pytest.mark.parametrize(
    ("zone", "begin", "seconds", "start", "end", "start_time", "end_time"),
    [
        pytest.param(
            "US/Pacific",
            "2026-11-01T08:59:39+00:00",
            60,
            "2026-11-01T01:59:39-07:00",
            "2026-11-01T01:00:39-08:00",
            "2026-11-01 01:59:39",
            "2026-11-01 01:00:39",
            id="US-earlier-on-the-clock",
        ),
        pytest.param(
            "Europe/Berlin",
            "2026-10-25T00:59:39+00:00",
            60,
            "2026-10-25T02:59:39+02:00",
            "2026-10-25T02:00:39+01:00",
            "2026-10-25 02:59:39",
            "2026-10-25 02:00:39",
            id="Berlin-earlier-on-the-clock",
        ),
        # The shortest event, which starts a minute before its end.
        pytest.param(
            "US/Pacific",
            "2026-11-01T09:00:09+00:00",
            30,
            "2026-11-01T01:59:39-07:00",
            "2026-11-01T01:00:39-08:00",
            "2026-11-01 01:59:39",
            "2026-11-01 01:00:39",
            id="US-shortest-event",
        ),
        pytest.param(
            "US/Pacific",
            "2026-11-01T08:30:00+00:00",
            70 * 60,
            "2026-11-01T01:30:00-07:00",
            "2026-11-01T01:40:00-08:00",
            "2026-11-01 01:30:00",
            "2026-11-01 01:40:00",
            id="US-later-on-the-clock",
        ),
        pytest.param(
            "US/Pacific",
            "2026-03-08T09:59:39+00:00",
            60,
            "2026-03-08T01:59:39-08:00",
            "2026-03-08T03:00:39-07:00",
            "2026-03-08 01:59:39",
            "2026-03-08 03:00:39",
            id="US-over-the-missing-hour",
        ),
        pytest.param(
            "Europe/Berlin",
            "2026-03-29T00:59:39+00:00",
            60,
            "2026-03-29T01:59:39+01:00",
            "2026-03-29T03:00:39+02:00",
            "2026-03-29 01:59:39",
            "2026-03-29 03:00:39",
            id="Berlin-over-the-missing-hour",
        ),
    ],
)
async def test_an_event_across_a_change_of_the_clocks_keeps_its_length(
    hass,
    aioclient_mock,
    freezer,
    zone,
    begin,
    seconds,
    start,
    end,
    start_time,
    end_time,
):
    await train(hass, aioclient_mock, freezer, zone, begin, seconds)

    events = await calendar_events(hass)
    assert [(event["start"], event["end"]) for event in events] == [(start, end)]
    assert length(events[0]) == timedelta(seconds=max(seconds, 60))
    state = calendar_state(hass)
    assert state.state == "off"
    assert state.attributes["message"] == events[0]["summary"]
    assert state.attributes["start_time"] == start_time
    assert state.attributes["end_time"] == end_time


async def test_the_calendar_stays_off_when_the_clocks_go_back_before_an_end(
    hass, aioclient_mock, freezer
):
    """Home Assistant would take the event for a running one and write the state
    again and again, as fast as it can, until the clock reaches its end."""
    coordinator = await train(
        hass, aioclient_mock, freezer, "US/Pacific", "2026-11-01T08:29:00+00:00", 60
    )
    assert calendar_state(hass).attributes["end_time"] == "2026-11-01 01:30:00"

    # An hour later, the clock is half a minute before the end of the event again.
    freezer.move_to("2026-11-01T09:29:30+00:00")
    coordinator.async_update_listeners()
    state = calendar_state(hass)
    assert (state.state, "message" in state.attributes) == ("off", False)
    await hass.async_block_till_done()
    events = await calendar_events(hass)
    assert [event["end"] for event in events] == ["2026-11-01T01:30:00-07:00"]

    # Once the clock reaches the end again, the attributes show the event again.
    freezer.move_to("2026-11-01T09:30:00+00:00")
    coordinator.async_update_listeners()
    state = calendar_state(hass)
    assert (state.state, state.attributes["end_time"]) == ("off", "2026-11-01 01:30:00")


async def test_an_entry_of_a_clock_that_ran_ahead_stays_an_event_of_the_future(
    hass, aioclient_mock, freezer
):
    """A clock that ran ahead left an entry in the future, or a backup of one did:
    Home Assistant runs it as any other event, and the clocks changed nothing."""
    coordinator = await train(
        hass, aioclient_mock, freezer, "US/Pacific", "2026-10-14T20:00:00+00:00", 60
    )

    freezer.move_to("2026-10-14T20:00:30+00:00")
    coordinator.async_update_listeners()
    state = calendar_state(hass)
    assert (state.state, state.attributes["end_time"]) == ("on", "2026-10-14 13:01:00")

    freezer.move_to("2026-10-14T20:01:00+00:00")
    coordinator.async_update_listeners()
    assert calendar_state(hass).state == "off"
