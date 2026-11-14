"""Personal bests, darts today, the streak and the daily goal in Home Assistant."""

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.homedarts.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .local_helpers import (
    T20,
    board,
    entity_id,
    local_entry_data,
    mock_board,
    record,
    setup_local,
    state,
)
from .test_practice_setup import set_number, throw


async def test_darts_today_the_daily_goal_and_a_personal_best(
    hass, aioclient_mock, freezer
):
    # Days start at midnight in Home Assistant's time zone: 07:00 UTC in summer.
    await hass.config.async_set_time_zone("US/Pacific")
    freezer.move_to("2026-09-21 18:00:00+00:00")
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    assert state(hass, "sensor", "darts_today") == "0"
    assert state(hass, "sensor", "training_streak") == "0"
    assert state(hass, "sensor", "personal_best") == "unknown"
    goal = er.async_get(hass).async_get(
        entity_id(hass, "number", "training_daily_goal")
    )
    assert goal.entity_category == er.EntityCategory.CONFIG
    await set_number(hass, "training_daily_goal", 10)

    # The first visit sets the highest visit quietly, the second beats it.
    await throw(hass, coordinator, T20)
    await throw(hass, coordinator, T20, T20, T20)
    bests = [attributes for kind, attributes in events if kind == "personal_best"]
    assert [(best["record"], best["value"], best["previous"]) for best in bests] == [
        ("highest_visit", 180, 60)
    ]
    best = hass.states.get(entity_id(hass, "sensor", "personal_best"))
    assert best.state == "2026-09-21T18:00:00+00:00"
    assert best.attributes["record"] == "highest_visit"
    assert best.attributes["highest_visit"] == 180

    await throw(hass, coordinator, T20, T20, T20)
    assert not [kind for kind, _ in events if kind == "daily_goal_reached"]
    await throw(hass, coordinator, T20, T20, T20)
    reached = [
        attributes for kind, attributes in events if kind == "daily_goal_reached"
    ]
    assert reached == [{"goal": 10, "darts": 10, "streak": 1, "source": "websocket"}]
    today = hass.states.get(entity_id(hass, "sensor", "darts_today"))
    assert today.state == "10"
    assert today.attributes == {
        **today.attributes,
        "goal": 10,
        "goal_reached": True,
        "progress": 100.0,
    }
    assert state(hass, "sensor", "training_streak") == "1"
    assert state(hass, "number", "training_daily_goal") == "10"

    # Midnight starts a new day; the streak lives on until the day ends without darts.
    freezer.move_to("2026-09-22 07:00:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state(hass, "sensor", "darts_today") == "0"
    streak = hass.states.get(entity_id(hass, "sensor", "training_streak"))
    assert streak.state == "1" and streak.attributes["trained_today"] is False
    freezer.move_to("2026-09-24 07:00:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    streak = hass.states.get(entity_id(hass, "sensor", "training_streak"))
    assert streak.state == "0" and streak.attributes["best_streak"] == 1


async def test_personal_bests_survive_a_restart(hass, aioclient_mock, hass_storage):
    hass_storage["homedarts.records-entry.training"] = {
        "version": 1,
        "key": "homedarts.records-entry.training",
        "data": {
            "records": {
                "bests": {
                    "highest_checkout": {
                        "value": 121,
                        "date": "2026-09-20T19:00:00+00:00",
                        "name": "Alex",
                    }
                },
                "latest": {
                    "record": "highest_checkout",
                    "value": 121,
                    "previous": 100,
                    "name": "Alex",
                    "date": "2026-09-20T19:00:00+00:00",
                },
                "streak": 4,
                "best_streak": 6,
                "goal": 300,
            }
        },
    }
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(
        domain="homedarts", version=2, data=local_entry_data(), entry_id="records-entry"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    best = hass.states.get(entity_id(hass, "sensor", "personal_best"))
    assert best.state == "2026-09-20T19:00:00+00:00"
    assert (best.attributes["name"], best.attributes["previous"]) == ("Alex", 100)
    assert best.attributes["highest_checkout"] == 121
    assert state(hass, "number", "training_daily_goal") == "300"
    # Without a last training day, there is no streak to continue.
    streak = hass.states.get(entity_id(hass, "sensor", "training_streak"))
    assert streak.state == "0" and streak.attributes["best_streak"] == 6


async def test_diagnostics_name_the_game_and_only_count_the_records(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    coordinator.games.practice.play("cricket")
    coordinator.games.records.set_goal(200, dt_util.now().date())
    coordinator.games.records.bests["highest_checkout"] = {
        "value": 121,
        "date": "2026-09-20T19:00:00+00:00",
        "name": "Secret Name",
    }
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["practice_game"]["game"] == "cricket"
    assert diagnostics["records"]["daily_goal"] == 200
    assert diagnostics["records"]["stored_bests"] == 1
    assert "Secret Name" not in str(diagnostics)
    coordinator.games.practice.play("bobs_27")
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["practice_game"]["game"] == "bobs_27"
