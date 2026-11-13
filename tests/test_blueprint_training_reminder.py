"""The training reminder blueprint, on a real board and on made-up sensors."""

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from .local_helpers import T20, automate, board, entity_id, setup_local
from .test_practice_setup import set_number, throw

pytestmark = pytest.mark.usefixtures("blueprint_folder")

ACTIONS = [
    {
        "action": "test.remind",
        "data": {
            "message": "{{ reminder }}",
            "numbers": "{{ [left, goal, darts_today, streak] }}",
        },
    }
]
TODAY = "sensor.autodarts_darts_today"
STREAK = "sensor.autodarts_training_streak"


async def at(hass, freezer, moment: str) -> None:
    """Move the clock in the time zone of the tests, where it is summer."""
    freezer.move_to(f"2026-09-{moment}+02:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def reminded(calls) -> list[tuple[str, list[int]]]:
    return [(call.data["message"], call.data["numbers"]) for call in calls]


async def turn_off(hass) -> None:
    """Turning the automation off cancels the timer for the next day."""
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "all"}, blocking=True
    )


@pytest.mark.parametrize(
    ("language", "both", "goal"),
    [
        (
            "en",
            "10 darts left to your daily goal of 10. "
            "Throw a dart today to keep your streak of 2 days.",
            "7 darts left to your daily goal of 10.",
        ),
        (
            "de-CH",
            "Noch 10 Darts bis zu deinem Tagesziel von 10. "
            "Wirf heute einen Dart, um deine Serie von 2 Tagen zu halten.",
            "Noch 7 Darts bis zu deinem Tagesziel von 10.",
        ),
        (
            "fr",
            "Encore 10 fléchettes pour atteindre votre objectif quotidien de 10. "
            "Lancez une fléchette aujourd'hui pour garder votre série de 2 jours.",
            "Encore 7 fléchettes pour atteindre votre objectif quotidien de 10.",
        ),
    ],
    ids=["en", "de-CH", "fr"],
)
async def test_the_reminder_of_a_real_board(
    hass, aioclient_mock, freezer, language, both, goal
):
    """The board's sensors bring the words in the language of Home Assistant,
    which translates no blueprint."""
    calls = async_mock_service(hass, "test", "remind")
    hass.config.language = language
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-09-24 18:00:00+02:00")
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await set_number(hass, "training_daily_goal", 10)
    # Two days in a row with darts, the goal missed on both.
    await throw(hass, coordinator, T20, T20, T20)
    await at(hass, freezer, "25 18:00:00")
    await throw(hass, coordinator, T20, T20, T20)
    device = er.async_get(hass).async_get(entity_id(hass, "sensor", "darts_today"))
    await automate(
        hass,
        "training_reminder",
        {"board": device.device_id, "reminder_actions": ACTIONS},
    )
    # A day with darts keeps the streak: only the goal is open.
    await at(hass, freezer, "25 19:00:00")
    assert reminded(calls) == [(goal, [7, 10, 3, 2])]

    # No dart yet the next day: the goal is open and the streak ends tonight.
    await at(hass, freezer, "26 00:00:01")
    await at(hass, freezer, "26 19:00:00")
    assert reminded(calls)[1:] == [(both, [10, 10, 0, 2])]

    # A visit after the reminder keeps the streak, and so does one in the
    # morning of the next day.
    await at(hass, freezer, "26 20:00:00")
    await throw(hass, coordinator, T20, T20, T20)
    await at(hass, freezer, "27 08:00:00")
    await throw(hass, coordinator, T20, T20, T20)
    await at(hass, freezer, "27 19:00:00")
    assert reminded(calls)[2:] == [(goal, [7, 10, 3, 4])]

    # The goal reached stays quiet.
    await at(hass, freezer, "28 08:00:00")
    for _ in range(4):
        await throw(hass, coordinator, T20, T20, T20)
    assert (
        "reminder"
        not in hass.states.get(entity_id(hass, "sensor", "darts_today")).attributes
    )
    assert (
        "reminder"
        not in hass.states.get(entity_id(hass, "sensor", "training_streak")).attributes
    )
    await at(hass, freezer, "28 19:00:00")
    assert len(calls) == 3
    await turn_off(hass)


async def board_sensors(hass) -> str:
    """The "Darts today" and "Training streak" sensors of a board, as the
    states of a test set them; the id of the board's device."""
    config_entry = MockConfigEntry(domain="homedarts")
    config_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("homedarts", "board-1")}
    )
    for key in ("darts_today", "training_streak", "training_darts"):
        er.async_get(hass).async_get_or_create(
            "sensor",
            "homedarts",
            f"board-1_{key}",
            config_entry=config_entry,
            device_id=device.id,
            suggested_object_id=f"autodarts_{key}",
        )
    # A sensor of the same unit and without the attributes of the two.
    hass.states.async_set("sensor.autodarts_training_darts", "30", {"hits": {}})
    return device.id


def sensors(
    hass,
    darts: int,
    goal: int,
    streak: int,
    *,
    reached: bool = False,
    words: tuple[str, str] | None = None,
) -> None:
    """The states of the two sensors, with the words of their reminders if given."""
    goal_words, streak_words = (
        ({"reminder": said} for said in words) if words else ({}, {})
    )
    hass.states.async_set(
        TODAY,
        str(darts),
        {"goal": goal, "goal_reached": reached, "progress": None, **goal_words},
    )
    hass.states.async_set(
        STREAK,
        str(streak),
        {
            "best_streak": 9,
            "trained_today": darts > 0,
            "last_day": None,
            **streak_words,
        },
    )


async def test_the_minimum_streak_the_weekdays_and_the_words_of_its_own(hass, freezer):
    """Without the words of the sensors, as with an older release of the
    integration, the reminder says its own in English."""
    calls = async_mock_service(hass, "test", "remind")
    await hass.config.async_set_time_zone("Europe/Berlin")
    # A Thursday.
    freezer.move_to("2026-09-24 20:00:00+02:00")
    device = await board_sensors(hass)
    sensors(hass, 0, 0, 1)
    await automate(
        hass,
        "training_reminder",
        {
            "board": device,
            "reminder_time": "21:00:00",
            "weekdays": ["mon", "tue", "thu", "fri", "sat"],
            "reminder_actions": ACTIONS,
        },
    )
    # No goal, and a streak below the minimum of 2 days.
    await at(hass, freezer, "24 21:00:00")
    assert calls == []
    sensors(hass, 0, 0, 2)
    await at(hass, freezer, "25 21:00:00")
    assert reminded(calls) == [
        ("Throw a dart today to keep your streak of 2 days.", [0, 0, 0, 2])
    ]
    # One dart short of the goal, which was raised after the darts of the day.
    sensors(hass, 9, 10, 3)
    await at(hass, freezer, "26 21:00:00")
    assert reminded(calls)[1:] == [
        ("1 dart left to your daily goal of 10.", [1, 10, 9, 3])
    ]
    # Not on a Sunday.
    sensors(hass, 0, 10, 4)
    await at(hass, freezer, "27 21:00:00")
    assert len(calls) == 2
    # A goal lowered below the darts of the day, and one reached, stay quiet.
    sensors(hass, 12, 10, 5)
    await at(hass, freezer, "28 21:00:00")
    sensors(hass, 12, 10, 5, reached=True)
    await at(hass, freezer, "29 21:00:00")
    assert len(calls) == 2
    await turn_off(hass)


async def test_a_streak_of_one_day_and_the_words_of_the_sensors(hass, freezer):
    calls = async_mock_service(hass, "test", "remind")
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-09-24 18:00:00+02:00")
    device = await board_sensors(hass)
    sensors(hass, 0, 0, 1)
    await automate(
        hass,
        "training_reminder",
        {"board": device, "minimum_streak": 1, "reminder_actions": ACTIONS},
    )
    await at(hass, freezer, "24 19:00:00")
    assert reminded(calls) == [
        ("Throw a dart today to keep your streak of 1 day.", [0, 0, 0, 1])
    ]
    sensors(hass, 0, 20, 1, words=("Twenty to go.", "Keep it."))
    await at(hass, freezer, "25 19:00:00")
    assert reminded(calls)[1:] == [("Twenty to go. Keep it.", [20, 20, 0, 1])]
    await turn_off(hass)


async def test_a_board_without_the_sensors_stays_quiet(hass, freezer):
    """A board whose sensors are disabled, or a device that is no longer there."""
    calls = async_mock_service(hass, "test", "remind")
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-09-24 18:00:00+02:00")
    await automate(
        hass,
        "training_reminder",
        {"board": "0123456789abcdef", "minimum_streak": 1, "reminder_actions": ACTIONS},
    )
    await at(hass, freezer, "24 19:00:00")
    assert calls == []
    await turn_off(hass)
