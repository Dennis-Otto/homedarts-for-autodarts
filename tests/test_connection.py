"""Board connection: gaps mid-visit, faults, polling, repairs and diagnostics."""

import asyncio
import logging
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homedarts.diagnostics import async_get_config_entry_diagnostics
from custom_components.homedarts.errors import AutodartsConnectionError
from custom_components.homedarts.local_api import AutodartsLocalClient
from custom_components.homedarts.local_coordinator import AutodartsLocalCoordinator
from custom_components.homedarts.repairs import async_offer_address

from .local_helpers import (
    BASE,
    BULL,
    S20,
    STATE,
    T20,
    board,
    entity_id,
    local_entry_data,
    mock_board,
    mock_board_v2,
    setup_local,
    state,
)

OTHER = "http://192.0.2.20:3180"
LOGGER = "custom_components.homedarts.local_coordinator"


def capture(hass, coordinator) -> list[tuple[str, dict]]:
    """Events the board entity announces, in order."""
    fired: list[tuple[str, dict]] = []

    @callback
    def record(kind, attributes):
        fired.append((kind, attributes))

    async_dispatcher_connect(hass, coordinator.event_signal, record)
    return fired


def kinds(fired, *wanted) -> list[str]:
    return [kind for kind, _ in fired if kind in wanted]


def issue(hass, name, entry):
    return ir.async_get(hass).async_get_issue("homedarts", f"{name}_{entry.entry_id}")


def messages(caplog, level, text) -> int:
    return sum(
        record.levelno == level and text in record.getMessage()
        for record in caplog.records
    )


async def fail(coordinator, times=3, error=AutodartsConnectionError):
    with patch.object(coordinator.client, "get_state", side_effect=error):
        for _ in range(times):
            await coordinator.async_refresh()


# -- visits across connection gaps ------------------------------------------------


async def test_realtime_gap_mid_visit_continues_the_practice_visit(
    hass, aioclient_mock
):
    go, drop, dropped = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def stream(self):
        yield "connected", {}
        await go.wait()
        yield "state", board(T20)
        await drop.wait()
        raise AutodartsConnectionError("reset by peer")

    async def wait(self, delay):
        dropped.set()
        await asyncio.Event().wait()

    with (
        patch.object(AutodartsLocalClient, "events", stream),
        patch.object(AutodartsLocalCoordinator, "_wait_before_reconnect", wait),
    ):
        entry = await setup_local(hass, aioclient_mock, state=board())
        coordinator = entry.runtime_data.local
        await coordinator.async_play(501)
        fired = capture(hass, coordinator)
        go.set()
        await hass.async_block_till_done()
        # The socket drops; the poll right after it finds one more dart.
        with patch.object(
            coordinator.client, "get_state", return_value=board(T20, T20)
        ):
            drop.set()
            await dropped.wait()
        with patch.object(coordinator.client, "get_state", return_value=board()):
            await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)
    visit = [
        (kind, details.get("dart_index"), details["source"])
        for kind, details in fired
        if kind in ("dart_detected", "visit_completed", "turn_changed")
    ]
    assert visit == [
        ("dart_detected", 1, "websocket"),
        ("dart_detected", 2, "poll"),
        ("visit_completed", None, "poll"),
        ("turn_changed", None, "poll"),
    ]
    completed = next(details for kind, details in fired if kind == "visit_completed")
    assert (completed["score"], completed["darts"]) == (120, 2)
    assert coordinator.games.practice.snapshot()["remaining"] == 381


async def test_visit_pulled_during_an_outage_is_completed(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await coordinator.async_play(501)
    fired = capture(hass, coordinator)
    coordinator.async_receive("state", board(T20, T20))
    await fail(coordinator)
    assert state(hass, "binary_sensor", "local_connected") == "off"
    # Meanwhile the darts were pulled and one new dart was thrown.
    with patch.object(coordinator.client, "get_state", return_value=board(S20)):
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert kinds(fired, "dart_detected", "visit_completed", "turn_changed") == [
        "dart_detected",
        "dart_detected",
        "visit_completed",
        "turn_changed",
    ]
    completed = next(details for kind, details in fired if kind == "visit_completed")
    assert completed["segments"] == ["T20", "T20"]
    assert state(hass, "sensor", "training_darts") == "2"
    assert state(hass, "sensor", "practice_remaining") == "381"


async def test_realtime_state_ends_an_outage(hass, aioclient_mock, caplog):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await fail(coordinator)
    assert state(hass, "binary_sensor", "local_connected") == "off"
    coordinator.async_receive("state", board(T20))
    assert state(hass, "binary_sensor", "local_connected") == "on"
    assert state(hass, "sensor", "last_throw") == "T20"
    assert messages(caplog, logging.INFO, "Local Board Manager is available again") == 1


async def test_status_changes_are_announced_also_after_a_gap(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    fired = capture(hass, coordinator)
    coordinator.async_receive("state", board(status="Takeout in progress"))
    await fail(coordinator)
    stopped = board(status="Stopped", running=False)
    with patch.object(coordinator.client, "get_state", return_value=stopped):
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    changes = [details["status"] for kind, details in fired if kind == "status_changed"]
    assert changes == ["Takeout in progress", "Stopped"]


# -- faults in the games and in the data --------------------------------------------


@pytest.mark.expected_errors
async def test_game_faults_never_cost_the_board_connection(
    hass, aioclient_mock, caplog
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    broken = patch.object(
        coordinator.games.practice, "snapshot", side_effect=IndexError("closest")
    )
    emit = patch.object(coordinator, "_emit", wraps=coordinator._emit)
    with broken, emit as emitted:
        coordinator.async_receive("state", board(T20))
        coordinator.async_receive("state", board(T20, T20))
        with patch.object(
            coordinator.client, "get_state", return_value=board(T20, T20)
        ):
            await coordinator.async_refresh()
    # The darts the training took in are announced although the game failed.
    assert [call.args[0] for call in emitted.call_args_list] == [
        "dart_detected",
        "dart_detected",
    ]
    assert coordinator.last_update_success
    assert state(hass, "binary_sensor", "local_connected") == "on"
    assert state(hass, "sensor", "last_throw") == "T20"
    failed = "Training or practice game failed; the board stays connected"
    assert messages(caplog, logging.ERROR, failed) == 1
    # Once the game works again, the entities catch up.
    coordinator.async_receive("state", board(T20, T20, T20))
    assert state(hass, "sensor", "training_darts") == "3"


async def test_the_board_logs_its_updates_under_the_transport(hass, aioclient_mock):
    # Debug logging for the connection keeps showing why a read failed.
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    assert coordinator.logger.name == LOGGER


async def test_rejected_states_never_shift_positions_onto_the_visit(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    practice = coordinator.games.practice
    with patch.object(practice, "track", wraps=practice.track) as track:
        first = board(T20)
        first["throws"][0]["coords"] = {"x": 0.1, "y": 0.2}
        coordinator.async_receive("state", first)
        # More darts than the board counts: training ignores the state.
        broken = board(BULL, T20, numThrows=1)
        broken["throws"][0]["coords"] = {"x": 0.9, "y": 0.9}
        coordinator.async_receive("state", broken)
    assert [call.args[1] for call in track.call_args_list] == [
        [(0.1, 0.2)],
        [(0.1, 0.2)],
    ]


async def test_board_text_longer_than_a_state_reads_as_unknown(hass, aioclient_mock):
    # Locally, Last event is a diagnostic that starts switched off.
    er.async_get(hass).async_get_or_create("sensor", "homedarts", "board-1_board_event")
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    coordinator.async_receive("state", board(event="x" * 256, status="Throw"))
    assert state(hass, "sensor", "board_event") == "Throw"
    # The same for the name of a segment, which Last dart shows.
    coordinator.async_receive("state", board(("y" * 256, 20, 1), status="Throw"))
    assert state(hass, "sensor", "last_throw") == "unknown"
    assert state(hass, "sensor", "last_throw_score") == "20"
    last_event = er.async_get(hass).async_get(entity_id(hass, "sensor", "board_event"))
    assert last_event.entity_category == er.EntityCategory.DIAGNOSTIC


# -- polling ----------------------------------------------------------------------------


async def test_overlapping_polls_are_read_one_after_the_other(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    fired = capture(hass, coordinator)
    release = asyncio.Event()
    answers = [board(T20), board(T20, S20)]
    reading = 0
    most = 0

    async def get_state():
        nonlocal reading, most
        reading += 1
        most = max(most, reading)
        answer = answers.pop(0)
        if answers:
            # The older read answers last.
            await release.wait()
        reading -= 1
        return answer

    with patch.object(coordinator.client, "get_state", side_effect=get_state):
        first = hass.async_create_task(coordinator.async_refresh())
        second = hass.async_create_task(coordinator.async_refresh())
        for _ in range(5):
            await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)
    await hass.async_block_till_done()
    assert most == 1
    detected = [
        details["dart_index"] for kind, details in fired if kind == "dart_detected"
    ]
    assert detected == [1, 2]
    assert state(hass, "sensor", "last_throw") == "S20"


async def test_unchanged_polls_leave_the_entities_alone(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    updates = []
    unsubscribe = coordinator.async_add_listener(lambda: updates.append(True))
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    assert updates == []
    with patch.object(
        coordinator.client, "get_state", return_value={**STATE, "running": True}
    ):
        await coordinator.async_refresh()
    assert updates == [True]
    unsubscribe()


async def test_telemetry_leaves_training_and_games_alone(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    revision = coordinator.data["revision"]
    with (
        patch.object(
            coordinator.games.practice,
            "snapshot",
            wraps=coordinator.games.practice.snapshot,
        ) as practice,
        patch.object(
            coordinator.games.training,
            "observe",
            wraps=coordinator.games.training.observe,
        ) as observe,
    ):
        for _ in range(10):
            coordinator.async_receive("stats", {"fps": 25.0, "extra": "dropped"})
            coordinator.async_receive("cam_stats", {"id": 0, "fps": 30})
            coordinator.async_receive("motion_state", {"isStable": True})
            coordinator.async_receive("cam_state", {"isRunning": True, "x": 1})
        assert practice.call_count == 0
        assert observe.call_count == 0
        assert coordinator.data["revision"] == revision
        coordinator.async_receive("state", board(T20))
        # Practice sensors show the published snapshot instead of computing it.
        assert practice.call_count == 1
    assert coordinator.data["revision"] == revision + 1
    assert coordinator.readings["stats"] == {"fps": 25.0}
    assert coordinator.readings["camera_state"] == {"isRunning": True}


async def test_an_update_of_every_entity_reuses_the_published_snapshots(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    with (
        patch.object(
            coordinator.games.training,
            "snapshot",
            wraps=coordinator.games.training.snapshot,
        ) as training,
        patch.object(
            coordinator.games.practice.profiles,
            "snapshot",
            wraps=coordinator.games.practice.profiles.snapshot,
        ) as profiles,
    ):
        coordinator.async_update_listeners()
        coordinator.async_update_listeners()
        # The training sensors show the published session, the players and
        # the matches are worked out once per change.
        assert training.call_count == 0
        assert profiles.call_count == 0
        coordinator.async_receive("state", board(T20))
        assert training.call_count == 1


async def test_poll_keeps_only_known_values(hass, aioclient_mock):
    aioclient_mock.get(BASE + "/api/state/stats", json={"fps": 9, "secret": "x"})
    aioclient_mock.get(
        BASE + "/api/cams/state", json={"isRunning": True, "device": "/dev/video0"}
    )
    aioclient_mock.get(BASE + "/api/cams/stats", json={"fps": [30, "fast", None]})
    entry = await setup_local(hass, aioclient_mock)
    readings = entry.runtime_data.local.readings
    assert readings["stats"] == {"fps": 9}
    assert readings["camera_state"] == {"isRunning": True}
    assert readings["camera_stats"] == {"fps": [30, None, None]}


async def test_board_that_stays_away_is_polled_less_often(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    await fail(coordinator, times=9)
    assert coordinator.update_interval == timedelta(seconds=2)
    await fail(coordinator, times=1)
    assert coordinator.update_interval == timedelta(seconds=15)
    await coordinator.async_refresh()
    assert coordinator.update_interval == timedelta(seconds=2)


async def test_board_off_at_the_start_still_loads(hass, aioclient_mock):
    """Training, games and their events work without the board."""
    aioclient_mock.get(BASE + "/api/state", status=503)
    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "local_connected") == "off"
    assert state(hass, "switch", "detection") == "unavailable"
    assert state(hass, "switch", "training_session") == "on"
    assert state(hass, "sensor", "practice_remaining") == "unknown"
    events = entity_id(hass, "event", "board_events")
    assert hass.states.get(events).state != "unavailable"
    # A session ended in Home Assistant is announced although the board is off.
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id(hass, "switch", "training_session")},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(events).attributes["event_type"] == "session_ended"
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock)
    await entry.runtime_data.local.async_refresh()
    await hass.async_block_till_done()
    assert state(hass, "binary_sensor", "local_connected") == "on"
    assert state(hass, "switch", "detection") == "off"
    assert entity_id(hass, "camera", "camera_2")


async def test_unknown_generation_keeps_the_entities_of_board_manager_2(
    hass, aioclient_mock
):
    """A board that is off at the first start may still run Board Manager 2."""
    registry = er.async_get(hass)
    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    cpu = registry.async_get_or_create(
        "sensor", "homedarts", "board-1_cpu_usage", config_entry=entry
    )
    aioclient_mock.get(BASE + "/api/state", status=503)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(cpu.entity_id) is not None
    aioclient_mock.clear_requests()
    mock_board_v2(aioclient_mock)
    await entry.runtime_data.local.async_refresh()
    await hass.async_block_till_done()
    await entry.runtime_data.local.async_refresh()
    assert entry.data["api_generation"] == 2
    assert hass.states.get(cpu.entity_id).state == "12.5"


# -- realtime reconnects ----------------------------------------------------------------


async def test_reconnect_wait_ends_when_a_poll_finds_the_board(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    await fail(coordinator, times=1)
    waiting = hass.async_create_task(coordinator._wait_before_reconnect(60))
    await asyncio.sleep(0)
    assert not waiting.done()
    await coordinator.async_refresh()
    assert await waiting is True
    # Without a poll that finds the board back, the wait simply ends.
    assert await coordinator._wait_before_reconnect(0) is False


async def test_woken_reconnect_starts_the_back_off_over(hass, aioclient_mock):
    waits = []
    done = asyncio.Event()

    async def stream(self):
        if len(waits) == 4:
            done.set()
            await asyncio.Event().wait()
        raise AutodartsConnectionError("refused")
        yield  # Never reached; makes this an async generator.

    async def wait(self, delay):
        waits.append(delay)
        return len(waits) == 2

    with (
        patch.object(AutodartsLocalClient, "events", stream),
        patch.object(AutodartsLocalCoordinator, "_wait_before_reconnect", wait),
    ):
        entry = await setup_local(hass, aioclient_mock)
        await done.wait()
        assert await hass.config_entries.async_unload(entry.entry_id)
    bases = [1, 2, 1, 2]
    assert all(0.8 * base <= delay <= base for delay, base in zip(waits, bases))


@pytest.mark.expected_errors
async def test_realtime_problems_are_logged_once(hass, aioclient_mock, caplog):
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    calls = 0
    done = asyncio.Event()

    async def stream(self):
        nonlocal calls
        calls += 1
        if calls <= 2:
            yield "connected", {}
            raise RuntimeError("unexpected board message")
        if calls < 8:
            raise AutodartsConnectionError("refused")
        yield "connected", {}
        yield "state", {**STATE}
        done.set()
        await asyncio.Event().wait()

    with (
        patch.object(AutodartsLocalClient, "events", stream),
        patch.object(
            AutodartsLocalCoordinator,
            "_wait_before_reconnect",
            AsyncMock(return_value=False),
        ),
    ):
        entry = await setup_local(hass, aioclient_mock)
        await done.wait()
        await hass.async_block_till_done()
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        assert await hass.config_entries.async_unload(entry.entry_id)
    unexpected = "Unexpected error in the local event stream"
    assert messages(caplog, logging.ERROR, unexpected) == 1
    assert messages(caplog, logging.DEBUG, unexpected) == 1
    assert messages(caplog, logging.WARNING, "realtime events at") == 1
    assert messages(caplog, logging.INFO, "available again") == 1
    realtime = diagnostics["connection"]["realtime"]
    assert realtime["connected"] and realtime["receiving"]
    assert realtime["connects"] == 3
    assert realtime["failed_attempts"] == 0
    assert realtime["last_close"] == "AutodartsConnectionError"


async def test_socket_closed_by_the_board_is_recorded(hass, aioclient_mock):
    done = asyncio.Event()
    calls = 0

    async def stream(self):
        nonlocal calls
        calls += 1
        if calls == 1:
            yield "connected", {}
            yield "closed", {"code": 1001}
            return
        done.set()
        await asyncio.Event().wait()

    with (
        patch.object(AutodartsLocalClient, "events", stream),
        patch.object(
            AutodartsLocalCoordinator,
            "_wait_before_reconnect",
            AsyncMock(return_value=False),
        ),
    ):
        entry = await setup_local(hass, aioclient_mock)
        await done.wait()
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        assert await hass.config_entries.async_unload(entry.entry_id)
    assert diagnostics["connection"]["realtime"]["last_close"] == (
        "closed by the board (1001)"
    )


# -- refused access and unknown answers -------------------------------------------------


@pytest.mark.parametrize("status", [401, 403])
async def test_board_that_refuses_access_raises_a_repair(
    hass, aioclient_mock, caplog, status
):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    aioclient_mock.get(BASE + "/api/state", status=status)
    for _ in range(4):
        await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.last_exception.translation_key == "board_access_denied"
    found = issue(hass, "board_access_denied", entry)
    assert found.severity == ir.IssueSeverity.ERROR
    assert found.translation_placeholders == {"address": BASE}
    assert messages(caplog, logging.WARNING, "refused access") == 1
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock)
    await coordinator.async_refresh()
    assert issue(hass, "board_access_denied", entry) is None
    assert state(hass, "binary_sensor", "local_connected") == "on"


@pytest.mark.parametrize(
    "status,key", [(403, "board_access_denied"), (404, "not_supported")]
)
async def test_actions_the_board_refuses_explain_why(hass, aioclient_mock, status, key):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    aioclient_mock.put(BASE + "/api/streams/start", status=status)
    with pytest.raises(HomeAssistantError) as error:
        await coordinator.async_action(
            lambda: coordinator.client.command("start_streams")
        )
    assert error.value.translation_key == key


async def test_unknown_state_answers_raise_a_repair(hass, aioclient_mock, caplog):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    # No running flag: this is no Board Manager state this integration knows.
    mock_board(aioclient_mock, state={"status": "Throw"})
    for _ in range(2):
        await coordinator.async_refresh()
    assert issue(hass, "unsupported_response", entry) is None
    await coordinator.async_refresh()
    assert coordinator.last_exception.translation_key == "unsupported_response"
    found = issue(hass, "unsupported_response", entry)
    assert found.translation_placeholders == {"reads": "/api/state"}
    assert found.severity == ir.IssueSeverity.WARNING
    unknown = "answered /api/state in an unknown format"
    assert messages(caplog, logging.WARNING, unknown) == 1
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock)
    await coordinator.async_refresh()
    assert issue(hass, "unsupported_response", entry) is None


async def test_unknown_optional_answers_are_only_logged(hass, aioclient_mock, caplog):
    aioclient_mock.get(BASE + "/api/state/stats", text="<html>not found</html>")
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    for _ in range(3):
        await coordinator.async_refresh()
    assert issue(hass, "unsupported_response", entry) is None
    unknown = "answered /api/state/stats in an unknown format"
    assert messages(caplog, logging.WARNING, unknown) == 1
    assert state(hass, "binary_sensor", "local_connected") == "on"


async def test_unknown_settings_answers_raise_a_repair(hass, aioclient_mock, freezer):
    aioclient_mock.get(BASE + "/api/config", json={"auth": "broken"})
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    # Board Manager 1 reports its settings every 30 seconds; polls in between
    # neither count nor clear the problem.
    for _ in range(2):
        freezer.tick(timedelta(seconds=30))
        await coordinator.async_refresh()
        await coordinator.async_refresh()
    found = issue(hass, "unsupported_response", entry)
    assert found.translation_placeholders == {"reads": "/api/config"}
    assert state(hass, "binary_sensor", "local_connected") == "on"


async def test_unknown_system_answers_raise_a_repair(hass, aioclient_mock):
    aioclient_mock.get(BASE + "/api/system", json=["no", "object"])
    mock_board_v2(aioclient_mock)
    data = {**local_entry_data(), "api_generation": 2}
    entry = MockConfigEntry(domain="homedarts", version=2, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.local
    for _ in range(2):
        await coordinator.async_refresh()
    found = issue(hass, "unsupported_response", entry)
    assert found.translation_placeholders == {"reads": "/api/system"}


# -- a board at a new address -----------------------------------------------------------


async def go_away(hass, aioclient_mock, freezer, coordinator, minutes=5):
    """The configured address stops answering for some minutes."""
    aioclient_mock.get(BASE + "/api/state", status=503)
    await fail_through_mock(coordinator)
    freezer.tick(timedelta(minutes=minutes))
    await coordinator.async_refresh()
    await hass.async_block_till_done()


async def fail_through_mock(coordinator):
    for _ in range(3):
        await coordinator.async_refresh()


async def test_local_board_is_never_looked_up_elsewhere(hass, aioclient_mock, freezer):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    await go_away(hass, aioclient_mock, freezer, coordinator, minutes=60)
    assert {call[1].host for call in aioclient_mock.mock_calls} == {"192.0.2.10"}
    assert issue(hass, "board_moved", entry) is None


async def test_board_back_at_its_address_withdraws_the_offer(
    hass, aioclient_mock, freezer
):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    await go_away(hass, aioclient_mock, freezer, coordinator)
    # Board Manager 2 announced the board at another address meanwhile.
    async_offer_address(hass, entry, "192.0.2.20", 3180)
    assert issue(hass, "board_moved", entry) is not None
    aioclient_mock.clear_requests()
    mock_board(aioclient_mock)
    await coordinator.async_refresh()
    assert issue(hass, "board_moved", entry) is None


@pytest.mark.parametrize("answer", ["offline", "another board", "bad issue"])
async def test_moved_board_repair_checks_the_address_again(
    hass, aioclient_mock, freezer, hass_client, answer
):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    await go_away(hass, aioclient_mock, freezer, coordinator)
    # Board Manager 2 announced the board at another address meanwhile.
    async_offer_address(hass, entry, "192.0.2.20", 3180)
    issue_id = f"board_moved_{entry.entry_id}"
    aioclient_mock.clear_requests()
    if answer == "offline":
        aioclient_mock.get(OTHER + "/api/state", status=503)
    elif answer == "another board":
        config = {"auth": {"board_id": "another-board"}, "cam": {}}
        mock_board(aioclient_mock, base=OTHER, config=config)
    else:
        ir.async_create_issue(
            hass,
            "homedarts",
            issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="board_moved",
            data={"entry_id": entry.entry_id, "host": "192.0.2.20", "port": "3180"},
        )
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    response = await client.post(
        "/api/repairs/issues/fix", json={"handler": "homedarts", "issue_id": issue_id}
    )
    flow = await response.json()
    if answer != "bad issue":
        assert flow["description_placeholders"] == {"new": OTHER}
        response = await client.post(
            f"/api/repairs/issues/fix/{flow['flow_id']}", json={}
        )
        flow = await response.json()
    assert flow["type"] == "abort"
    assert flow["reason"] == "board_unavailable"
    assert entry.data["host"] == "192.0.2.10"


# -- diagnostics ------------------------------------------------------------------------


async def test_diagnostics_never_name_players(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await coordinator.async_set_player_name(0, "Secret Player")
    await coordinator.async_play(501)
    coordinator.async_receive("state", board(T20))
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert "Secret Player" not in str(diagnostics)
    assert diagnostics["local"]["practice"]["name"] == "**REDACTED**"
    assert diagnostics["local"]["practice"]["remaining"] == 441


async def test_diagnostics_tell_how_the_connection_went(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock)
    coordinator = entry.runtime_data.local
    aioclient_mock.clear_requests()
    aioclient_mock.get(BASE + "/api/state", status=503)
    await coordinator.async_refresh()
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    connection = diagnostics["connection"]
    assert connection["consecutive_failures"] == 1
    assert connection["last_error"] == "ClientResponseError"
    assert connection["last_success"].endswith("+00:00")
    assert connection["offline_seconds"] == 0
    assert connection["last_poll_seconds"] >= 0
    assert connection["board_manager_version"] == "1.0.7"
    assert connection["system_api_missing"] is False
    assert connection["identity_valid"] is True
    assert connection["access_denied"] is False
    assert connection["unknown_answers"] == []
    assert connection["realtime"] == {
        "connected": False,
        "receiving": False,
        "connects": 0,
        "failed_attempts": 0,
        "reconnect_delay_seconds": 1,
        "last_close": None,
        "ignored_frames": 0,
        "socket": None,
        "motion_frames": False,
    }
    assert "192.0.2.10" not in str(diagnostics)
