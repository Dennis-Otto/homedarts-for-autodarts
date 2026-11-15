"""Training sessions in Home Assistant: switches, pauses, restarts and history."""

from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from .local_helpers import (
    BULL,
    S20,
    T20,
    board,
    entity_id,
    local_entry_data,
    mock_board,
    reads_say,
    record,
    setup_local,
    state,
    switch,
)


async def test_switch_ends_and_starts_sessions_with_events_and_history(
    hass, aioclient_mock, hass_storage
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    await switch(hass, "training_auto_start", False)
    registry = er.async_get(hass)
    auto_start = registry.async_get(entity_id(hass, "switch", "training_auto_start"))
    assert auto_start.entity_category == er.EntityCategory.CONFIG
    coordinator.async_receive("state", board(T20))
    coordinator.async_receive("state", board(T20, T20))
    await hass.async_block_till_done()
    assert state(hass, "switch", "training_session") == "on"

    await switch(hass, "training_session", False)
    assert state(hass, "switch", "training_session") == "off"
    kind, summary = events[-1]
    assert kind == "session_ended"
    assert summary["reason"] == "manual" and summary["source"] == "training"
    assert summary["darts"] == 2 and summary["average"] == 180.0
    last = hass.states.get(entity_id(hass, "sensor", "training_last_session"))
    assert float(last.state) == 180.0
    assert last.attributes["darts"] == 2
    assert len(last.attributes["sessions"]) == 1
    saved = hass_storage[f"homedarts.{entry.entry_id}.training"]["data"]
    assert saved["active"] is False and saved["auto_start"] is False
    assert saved["history"][0]["points"] == 120

    # Without a session, darts are announced but no longer counted.
    coordinator.async_receive("state", board(T20, T20, S20))
    coordinator.async_receive("state", board())
    await hass.async_block_till_done()
    assert [kind for kind, _ in events[-3:]] == [
        "dart_detected",
        "visit_thrown",
        "visit_completed",
    ]
    assert state(hass, "sensor", "training_darts") == "2"
    visit = hass.states.get(entity_id(hass, "sensor", "local_visit_score"))
    assert visit.attributes["recent_visits"][0]["score"] == 140

    await switch(hass, "training_session", True)
    assert events[-1][0] == "session_started"
    assert events[-1][1]["reason"] == "manual"
    assert state(hass, "switch", "training_session") == "on"
    assert state(hass, "sensor", "training_darts") == "0"
    await switch(hass, "training_auto_start", True)
    assert state(hass, "switch", "training_auto_start") == "on"
    assert hass_storage[f"homedarts.{entry.entry_id}.training"]["data"]["auto_start"]


async def test_the_first_dart_starts_a_session_and_the_button_starts_anew(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    await switch(hass, "training_session", False)
    coordinator.async_receive("state", board(BULL))
    await hass.async_block_till_done()
    assert [kind for kind, _ in events[-2:]] == ["session_started", "dart_detected"]
    assert events[-2][1]["reason"] == "first_dart"
    assert state(hass, "sensor", "training_bulls") == "1"

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", "reset_training")},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert [kind for kind, _ in events[-2:]] == ["session_ended", "session_started"]
    assert events[-2][1]["reason"] == "new_session"
    assert events[-1][1]["reason"] == "new_session"
    assert state(hass, "sensor", "training_darts") == "0"


async def test_a_pause_ends_the_session_at_its_last_dart(hass, aioclient_mock, freezer):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id(hass, "number", "training_idle_timeout"), "value": 10},
        blocking=True,
    )
    assert state(hass, "number", "training_idle_timeout") == "10"
    # The board answers its reads with the darts as well: a takeout that a poll
    # found would count as the last activity.
    reads_say(aioclient_mock, board(T20))
    coordinator.async_receive("state", board(T20))
    freezer.tick(timedelta(minutes=9))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    reads_say(aioclient_mock, board(T20, S20))
    coordinator.async_receive("state", board(T20, S20))
    last_dart = dt_util.utcnow()
    # A timer that fires after a new dart only reschedules the end.
    await coordinator._async_end_idle(dt_util.utcnow())
    assert coordinator._idle_unsub is not None
    freezer.tick(timedelta(minutes=9))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state(hass, "switch", "training_session") == "on"

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state(hass, "switch", "training_session") == "off"
    kind, summary = events[-1]
    assert kind == "session_ended" and summary["reason"] == "idle"
    assert dt_util.parse_datetime(summary["ended"]) == last_dart
    assert summary["darts"] == 2


async def test_unloading_cancels_a_pending_pause(
    hass, aioclient_mock, hass_storage, freezer
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id(hass, "number", "training_idle_timeout"), "value": 10},
        blocking=True,
    )
    coordinator.async_receive("state", board(T20))
    assert coordinator._idle_unsub is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert coordinator._idle_unsub is None
    freezer.tick(timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # The session is still running: it ends with the pause after the next start.
    saved = hass_storage[f"homedarts.{entry.entry_id}.training"]["data"]
    assert saved["active"] is True and saved["darts"] == 1


async def test_an_overdue_pause_ends_the_session_after_a_restart(
    hass, aioclient_mock, hass_storage
):
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    now = dt_util.utcnow()
    last_dart = (now - timedelta(hours=1)).isoformat()
    hass_storage[f"homedarts.{entry.entry_id}.training"] = {
        "version": 1,
        "key": f"homedarts.{entry.entry_id}.training",
        "data": {
            "started": (now - timedelta(hours=2)).isoformat(),
            "active": True,
            "auto_start": False,
            "idle_minutes": 15,
            "last_activity": last_dart,
            "darts": 6,
            "points": 300,
            "visits": 2,
        },
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    assert state(hass, "switch", "training_session") == "off"
    assert state(hass, "switch", "training_auto_start") == "off"
    assert state(hass, "number", "training_idle_timeout") == "15"
    last = hass.states.get(entity_id(hass, "sensor", "training_last_session"))
    assert float(last.state) == 150.0
    assert last.attributes["ended"] == last_dart
    assert last.attributes["duration_minutes"] == 60.0
    event = hass.states.get(entity_id(hass, "event", "board_events"))
    assert event.attributes["event_type"] == "session_ended"
    assert event.attributes["reason"] == "idle"
