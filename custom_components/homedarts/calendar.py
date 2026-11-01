"""The training calendar: finished training sessions and practice matches."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import AutodartsStoredEntity
from .games_coordinator import AutodartsGamesCoordinator
from .journal import JournalEvent
from .runtime import AutodartsConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutodartsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([AutodartsTrainingCalendar(entry.runtime_data.local)])


def _calendar_event(event: JournalEvent) -> CalendarEvent:
    """In local time, like the events of Home Assistant's own calendars.

    When the clocks go back, an event can end earlier on the clock than it starts,
    such as from 01:59:39-07:00 to 01:00:39-08:00, one minute later. Python subtracts
    two times of one time zone by their clocks, so Home Assistant's check of an event
    refuses that one; the event gets its real end after the check.
    """
    start, end = dt_util.as_local(event.start), dt_util.as_local(event.end)
    calendar_event = CalendarEvent(
        start=start,
        end=max(start, end),
        summary=event.summary,
        description=event.description,
        uid=event.uid,
    )
    calendar_event.end = end
    return calendar_event


def _clock_before_its_end(event: JournalEvent) -> bool:
    """Whether an event is over, but the clocks went back to before its end.

    Home Assistant compares the clocks: it takes such an event for one that still
    runs and writes the state again and again, until the clock reaches the end.
    """
    now = dt_util.now()
    # In UTC, the end compares with now as a moment, in local time by the clock.
    return event.end <= now < dt_util.as_local(event.end)


class AutodartsTrainingCalendar(AutodartsStoredEntity, CalendarEntity):
    """Read-only: every entry is something that happened on the board.

    The state attributes show the entry that ended last, so the state is off
    unless a calendar trigger asks for the events of a period. In the hour that
    repeats when the clocks go back, they show nothing while the clock is before
    the end of that entry.
    """

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "training_calendar")

    @property
    def event(self) -> CalendarEvent | None:
        latest = self.coordinator.reports.journal.latest()
        if latest is None or _clock_before_its_end(latest):
            return None
        return _calendar_event(latest)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        journal = self.coordinator.reports.journal
        return [
            _calendar_event(event) for event in journal.events(start_date, end_date)
        ]
