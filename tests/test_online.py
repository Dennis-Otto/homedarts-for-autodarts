"""The bridge for online matches: Tools for Autodarts calls a webhook of Home Assistant."""

import json
import logging
import re
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import State, callback
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache,
)
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from custom_components.homedarts import online
from custom_components.homedarts.config_flow import AutodartsConfigFlow
from custom_components.homedarts.diagnostics import async_get_config_entry_diagnostics
from custom_components.homedarts.local_coordinator import EVENT_TYPES
from custom_components.homedarts.online import (
    EFFECT_TRIGGERS,
    MOMENTS,
    ONLINE_EVENT_TYPES,
    RATE_LIMITS,
    parse,
)

from .local_helpers import (
    BRIDGE,
    NOW,
    WEBHOOK_ID,
    entity_id,
    entity_summary,
    setup_bridge,
)
from .local_helpers import WEBHOOK_PATH as PATH

ROOT = Path(__file__).parents[1]
SENSOR = "sensor.autodarts_board_online_bridge_last_event"
# State attributes of the event entity itself, not of an event.
ENTITY_ATTRIBUTES = {"event_types", "friendly_name", "icon"}


def record_events(hass) -> list[dict]:
    """The details of every board event from now on."""
    events: list[dict] = []

    @callback
    def collect(event) -> None:
        if (new := event.data["new_state"]) and "event_type" in new.attributes:
            events.append(
                {
                    key: value
                    for key, value in new.attributes.items()
                    if key not in ENTITY_ATTRIBUTES
                }
            )

    async_track_state_change_event(
        hass, entity_id(hass, "event", "board_events"), collect
    )
    return events


async def call(client, method: str = "GET", query: str = "", **kwargs):
    response = await client.request(method, f"{PATH}{query}", **kwargs)
    return response.status, await response.text()


# -- triggers ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("trigger", "player", "kind", "details"),
    [
        ("gameon", None, "online_game_on", {}),
        ("gameon", "Dennis", "online_game_on", {"name": "Dennis"}),
        ("bot_throw", None, "online_game_on", {}),
        ("busted", "Lea", "online_busted", {"name": "Lea"}),
        ("bulloff", None, "online_bull_off", {}),
        ("tournament_ready", None, "online_tournament_ready", {}),
        ("idle", None, "online_match_left", {}),
        ("gameshot", None, "online_game_shot", {}),
        ("gameshot+d10", None, "online_game_shot", {"segment": "D10"}),
        # A query string turns the "+" into a space.
        ("gameshot d10", None, "online_game_shot", {"segment": "D10"}),
        ("matchshot+bull", None, "online_match_shot", {"segment": "BULL"}),
        ("matchshot_dennis", "Lea", "online_match_shot", {"name": "dennis"}),
        ("gameshot_john doe", None, "online_game_shot", {"name": "john doe"}),
        ("180", None, "online_visit", {"score": 180}),
        ("0", None, "online_visit", {"score": 0}),
        # A plain number is always the score of a visit, 25 as well.
        ("25", None, "online_visit", {"score": 25}),
        ("range_100_140", None, "online_visit", {"score_min": 100, "score_max": 140}),
        ("100-180", None, "online_visit", {"score_min": 100, "score_max": 180}),
        (
            "t20_t20_t20",
            None,
            "online_visit",
            {"score": 180, "darts": 3, "segments": ["T20", "T20", "T20"]},
        ),
        (
            "s20_25_m5",
            None,
            "online_visit",
            {"score": 45, "darts": 3, "segments": ["S20", "25", "MISS"]},
        ),
        (
            "bull_d20_miss",
            None,
            "online_visit",
            {"score": 90, "darts": 3, "segments": ["BULL", "D20", "MISS"]},
        ),
        ("t20", None, "online_dart", {"segment": "T20", "score": 60}),
        ("d16", None, "online_dart", {"segment": "D16", "score": 32}),
        ("s5", None, "online_dart", {"segment": "S5", "score": 5}),
        ("s25", None, "online_dart", {"segment": "25", "score": 25}),
        ("bull", None, "online_dart", {"segment": "BULL", "score": 50}),
        ("outside", None, "online_dart", {"segment": "MISS", "score": 0}),
        ("m17", None, "online_dart", {"segment": "MISS", "score": 0}),
        ("miss", None, "online_dart", {"segment": "MISS", "score": 0}),
    ],
)
def test_triggers_of_tools_for_homedarts(trigger, player, kind, details):
    assert parse(trigger, player) == (
        kind,
        {"trigger": trigger, **({"name": player} if player else {}), **details},
    )


def test_triggers_are_normalized_and_other_boards_ignored():
    assert parse("  GameOn ") == ("online_game_on", {"trigger": "gameon"})
    assert parse("Gameshot   D10") == (
        "online_game_shot",
        {"trigger": "gameshot d10", "segment": "D10"},
    )
    assert parse("other") == ("", {"trigger": "other"})


@pytest.mark.parametrize(
    ("trigger", "player", "name"),
    [
        # Lower case finds the trigger; the name keeps the case it was sent in.
        ("gameshot_Dennis", None, "Dennis"),
        ("MatchShot_John   Doe", None, "John Doe"),
        ("gameshot_Lea_2", "Sam", "Lea_2"),
        # Notifications and file names render a name again, so it never holds
        # the characters of a template, as no player name does.
        ("busted", "{{ 6*7 }}", "6*7"),
        ("gameshot_{% if 1 %}Kim", None, "if 1 Kim"),
        ("matchshot_#Lea", None, "Lea"),
        # Nothing left of the trigger's name: the player who was sent counts.
        ("gameshot_{}", "Sam", "Sam"),
        ("gameshot_%", None, None),
        ("gameon", "{#}", None),
        # As long as a name in the games, at most.
        ("gameshot_" + "x" * 30, None, "x" * 20),
    ],
)
def test_names_keep_their_case_and_lose_template_characters(trigger, player, name):
    moment = parse(trigger, player)
    assert moment is not None
    assert moment[1].get("name") == name
    assert moment[1]["trigger"] == " ".join(trigger.split()).lower()


@pytest.mark.parametrize(
    "trigger",
    [
        "181",
        "1800",
        "t21",
        "t25",
        "d25",
        "s0",
        "range_140_100",
        "range_100",
        "t20_t20",
        "t20_t20_t20_t20",
        "t20_outside_t20",
        "gameshot_",
        "gameshot+x",
        "gameshot+outside",
        "takeout",
        "board_started",
        "lobby_in",
        "dennis",
        "",
    ],
)
def test_unknown_triggers(trigger):
    assert parse(trigger) is None


def test_every_event_type_is_a_board_event_and_documented():
    assert set(MOMENTS.values()) <= set(ONLINE_EVENT_TYPES)
    assert EVENT_TYPES[-len(ONLINE_EVENT_TYPES) :] == ONLINE_EVENT_TYPES
    for document in ("docs/entities.md", "docs/entities.de.md"):
        text = (ROOT / document).read_text(encoding="utf-8")
        for kind in ONLINE_EVENT_TYPES:
            assert f"`{kind}`" in text, (document, kind)
    # Every ready-made effect is a trigger the bridge understands.
    assert all(parse(trigger) is not None for trigger in EFFECT_TRIGGERS)


# -- options -------------------------------------------------------------------


async def test_options_switch_the_bridge_on_and_show_the_address(hass, aioclient_mock):
    await async_process_ha_core_config(
        hass,
        {
            "internal_url": "http://homeassistant.lan:8123",
            "external_url": "https://darts.example.com",
        },
    )
    entry = await setup_bridge(hass, aioclient_mock, options={})
    assert entry.runtime_data.bridge is None
    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", "homedarts", "board-1_online_bridge_last_event"
        )
        is None
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    # A new address is offered once there is one.
    assert [str(key) for key in result["data_schema"].schema] == [
        "online_bridge",
        "online_bridge_remote",
        "plans",
    ]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"online_bridge": True, "online_bridge_remote": False}
    )
    assert result["step_id"] == "online_bridge"
    url = result["description_placeholders"]["url"]
    webhook_id = url.rsplit("/", 1)[1]
    assert re.fullmatch("[0-9a-f]{64}", webhook_id)
    # Only calls from the home network count, so the address is the internal one.
    assert url == f"http://homeassistant.lan:8123/api/webhook/{webhook_id}"
    effects = result["description_placeholders"]["effects"].split("\n")
    assert len(effects) == len(EFFECT_TRIGGERS)
    assert effects[0] == f"Home Assistant: gameon;URL;{url}?event=gameon;gameon"
    assert f"Home Assistant: 180;URL;{url}?event=180;180" in effects
    assert entry.options == {}

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {
        "online_bridge": True,
        "online_bridge_remote": False,
        "online_bridge_webhook_id": webhook_id,
    }
    # The options reload the entry, which opens the webhook and adds the sensor.
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.bridge is not None
    assert hass.states.get(SENSOR).state == "unknown"

    # Opening the options again shows the same address, with remote calls the
    # external https address.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert [str(key) for key in result["data_schema"].schema] == [
        "online_bridge",
        "online_bridge_remote",
        "online_bridge_new_address",
        "plans",
    ]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "online_bridge": True,
            "online_bridge_remote": True,
            "online_bridge_new_address": False,
        },
    )
    assert result["description_placeholders"]["url"] == (
        f"https://darts.example.com/api/webhook/{webhook_id}"
    )
    await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert entry.options["online_bridge_remote"] is True
    assert entry.runtime_data.bridge.remote is True

    # A new address replaces the old one.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "online_bridge": True,
            "online_bridge_remote": True,
            "online_bridge_new_address": True,
        },
    )
    await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    new_id = entry.options["online_bridge_webhook_id"]
    assert re.fullmatch("[0-9a-f]{64}", new_id) and new_id != webhook_id

    # Switched off, the bridge keeps its address for later and loses its sensor.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "online_bridge": False,
            "online_bridge_remote": False,
            "online_bridge_new_address": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {
        "online_bridge": False,
        "online_bridge_remote": False,
        "online_bridge_webhook_id": new_id,
    }
    assert entry.runtime_data.bridge is None
    assert hass.states.get(SENSOR) is None
    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", "homedarts", "board-1_online_bridge_last_event"
        )
        is None
    )


async def test_a_new_address_replaces_the_old_one_when_switching_off(
    hass, aioclient_mock
):
    """Whoever knows a leaked address can never use it again."""
    entry = await setup_bridge(hass, aioclient_mock)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "online_bridge": False,
            "online_bridge_remote": False,
            "online_bridge_new_address": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    new_id = entry.options["online_bridge_webhook_id"]
    assert re.fullmatch("[0-9a-f]{64}", new_id) and new_id != WEBHOOK_ID
    assert entry.options["online_bridge"] is False


async def test_only_an_entry_with_a_local_board_has_options(hass, aioclient_mock):
    """The bridge delivers moments as events of the local board."""
    local = await setup_bridge(hass, aioclient_mock, options={})
    manual = MockConfigEntry(
        domain="homedarts",
        version=2,
        minor_version=2,
        data={"board_id": "manual_1", "manual_board": True, "name": "Dartboard"},
    )
    manual.add_to_hass(hass)
    assert AutodartsConfigFlow.async_supports_options_flow(local)
    assert not AutodartsConfigFlow.async_supports_options_flow(manual)
    assert local.supports_options and not manual.supports_options


async def test_address_without_the_configured_urls(hass):
    # Remote calls without an external https address use the home network.
    with patch.object(
        online, "get_url", side_effect=[NoURLAvailableError, "http://192.0.2.5:8123"]
    ):
        assert online.bridge_url(hass, WEBHOOK_ID, True) == (
            f"http://192.0.2.5:8123{PATH}"
        )
    with patch.object(online, "get_url", side_effect=NoURLAvailableError):
        assert online.bridge_url(hass, WEBHOOK_ID, False) == (
            f"http://homeassistant.local:8123{PATH}"
        )


# -- calls ---------------------------------------------------------------------


async def test_calls_become_board_events(
    hass, aioclient_mock, hass_client_no_auth, caplog
):
    caplog.set_level(logging.DEBUG, logger="custom_components.homedarts")
    entry = await setup_bridge(hass, aioclient_mock)
    events = record_events(hass)
    client = await hass_client_no_auth()
    plain = {"Content-Type": "text/plain;charset=UTF-8"}

    # An effect of type URL, and one whose "+" was not encoded.
    assert await call(client, query="?event=180") == (HTTPStatus.OK, "ok")
    assert await call(client, query="?event=gameshot+d10&player=Dennis") == (
        HTTPStatus.OK,
        "ok",
    )
    # An effect of type JSON API sends its JSON as text/plain.
    assert await call(
        client, "POST", data='{"event": "busted", "player": "Lea"}', headers=plain
    ) == (HTTPStatus.OK, "ok")
    assert await call(client, "POST", data='{"event": 140, "other": [1]}') == (
        HTTPStatus.OK,
        "ok",
    )
    assert await call(client, "POST", data="event=t20_t20_t20&player=Sam") == (
        HTTPStatus.OK,
        "ok",
    )
    # A bare trigger or a JSON string, with the player in the address.
    assert await call(client, "POST", "?player=Sam", data="matchshot") == (
        HTTPStatus.OK,
        "ok",
    )
    assert await call(client, "POST", data='"bull"') == (HTTPStatus.OK, "ok")
    # A POST without a body reads the address.
    assert await call(client, "POST", "?event=idle") == (HTTPStatus.OK, "ok")
    # A moment on another board is no event.
    assert await call(client, query="?event=other") == (HTTPStatus.OK, "ignored")
    # Home Assistant answers HEAD requests itself, so websites can check the URL.
    assert (await call(client, "HEAD"))[0] == HTTPStatus.OK
    await hass.async_block_till_done()

    assert events == [
        {
            "event_type": "online_visit",
            "trigger": "180",
            "score": 180,
            "source": "online",
        },
        {
            "event_type": "online_game_shot",
            "trigger": "gameshot d10",
            "segment": "D10",
            "name": "Dennis",
            "source": "online",
        },
        {
            "event_type": "online_busted",
            "trigger": "busted",
            "name": "Lea",
            "source": "online",
        },
        {
            "event_type": "online_visit",
            "trigger": "140",
            "score": 140,
            "source": "online",
        },
        {
            "event_type": "online_visit",
            "trigger": "t20_t20_t20",
            "name": "Sam",
            "score": 180,
            "darts": 3,
            "segments": ["T20", "T20", "T20"],
            "source": "online",
        },
        {
            "event_type": "online_match_shot",
            "trigger": "matchshot",
            "name": "Sam",
            "source": "online",
        },
        {
            "event_type": "online_dart",
            "trigger": "bull",
            "segment": "BULL",
            "score": 50,
            "source": "online",
        },
        {"event_type": "online_match_left", "trigger": "idle", "source": "online"},
    ]
    sensor = hass.states.get(SENSOR)
    assert dt_util.parse_datetime(sensor.state) is not None
    assert sensor.attributes["trigger"] == "idle"
    assert sensor.attributes["event_type"] == "online_match_left"
    assert sensor.attributes["device_class"] == "timestamp"
    assert er.async_get(hass).async_get(SENSOR).entity_category == "diagnostic"

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert WEBHOOK_ID not in json.dumps(diagnostics, default=str)
    assert diagnostics["online_bridge"] == {
        "enabled": True,
        "remote": False,
        "events": 8,
        "ignored": 1,
        "invalid": 0,
        "limited": 0,
        "last_event": sensor.state,
        "last_event_type": "online_match_left",
    }
    assert not [
        record
        for record in caplog.records
        if record.name.startswith("custom_components.homedarts")
        and WEBHOOK_ID in record.getMessage()
    ]


async def test_names_are_spelled_as_the_players_profile_spells_them(
    hass, aioclient_mock, hass_client_no_auth
):
    entry = await setup_bridge(hass, aioclient_mock)
    entry.runtime_data.local.games.practice.profiles.visit("Dennis", 60, now=NOW)
    events = record_events(hass)
    client = await hass_client_no_auth()
    for query in (
        "?event=gameshot_dennis",
        "?event=busted&player=DENNIS",
        "?event=matchshot_Kim",
        "?event=gameon&player=%7B%7B%206*7%20%7D%7D",
    ):
        assert await call(client, query=query) == (HTTPStatus.OK, "ok")
    await hass.async_block_till_done()
    assert [event["name"] for event in events] == ["Dennis", "Dennis", "Kim", "6*7"]
    assert events[0]["trigger"] == "gameshot_dennis"


@pytest.mark.parametrize(
    ("method", "query", "body", "status", "answer"),
    [
        ("GET", "", None, HTTPStatus.BAD_REQUEST, "event missing"),
        ("GET", "?event=%20", None, HTTPStatus.BAD_REQUEST, "event missing"),
        ("GET", "?event=" + "1" * 65, None, HTTPStatus.BAD_REQUEST, "invalid event"),
        ("GET", "?event=game%01on", None, HTTPStatus.BAD_REQUEST, "invalid event"),
        (
            "GET",
            "?event=180&player=" + "x" * 51,
            None,
            HTTPStatus.BAD_REQUEST,
            "invalid player",
        ),
        (
            "POST",
            "",
            r'{"event": "180", "player": "a\u0007b"}',
            HTTPStatus.BAD_REQUEST,
            "invalid player",
        ),
        (
            "GET",
            "?event=180&x=" + "1" * 1024,
            None,
            HTTPStatus.REQUEST_URI_TOO_LONG,
            "address too long",
        ),
        ("POST", "", "{nope", HTTPStatus.BAD_REQUEST, "invalid JSON"),
        ("POST", "", "[180]", HTTPStatus.BAD_REQUEST, "invalid JSON"),
        ("POST", "", '{"event": true}', HTTPStatus.BAD_REQUEST, "invalid event"),
        ("POST", "", '{"event": ["x"]}', HTTPStatus.BAD_REQUEST, "invalid event"),
        ("POST", "", '{"player": 1.5}', HTTPStatus.BAD_REQUEST, "invalid player"),
        ("POST", "", b"\xff\xfe", HTTPStatus.BAD_REQUEST, "invalid text"),
        ("POST", "", "a=1&" * 11, HTTPStatus.BAD_REQUEST, "invalid fields"),
        (
            "POST",
            "",
            "event=180&x=" + "1" * 1024,
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "body too large",
        ),
        ("POST", "", "  ", HTTPStatus.BAD_REQUEST, "event missing"),
    ],
)
async def test_invalid_calls_are_refused(
    hass, aioclient_mock, hass_client_no_auth, method, query, body, status, answer
):
    entry = await setup_bridge(hass, aioclient_mock)
    events = record_events(hass)
    client = await hass_client_no_auth()
    assert await call(client, method, query, data=body) == (status, answer)
    await hass.async_block_till_done()
    assert not events
    assert entry.runtime_data.bridge.counts["invalid"] == 1
    assert hass.states.get(SENSOR).state == "unknown"


async def test_unknown_triggers_are_explained_once(
    hass, aioclient_mock, hass_client_no_auth, caplog
):
    caplog.set_level(logging.DEBUG, logger="custom_components.homedarts")
    await setup_bridge(hass, aioclient_mock)
    events = record_events(hass)
    client = await hass_client_no_auth()
    for trigger in ("takeout", "lobby_in"):
        assert await call(client, query=f"?event={trigger}") == (
            HTTPStatus.BAD_REQUEST,
            "unknown event",
        )
    assert not events
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.name == "custom_components.homedarts.online"
        and record.levelno == logging.WARNING
    ]
    assert warnings == [
        "The online bridge ignored the unknown event 'takeout'; the documentation "
        "lists the triggers of Tools for Autodarts it understands"
    ]
    assert "Online bridge ignored the unknown event 'lobby_in'" in caplog.text


async def test_calls_beyond_the_rate_limit_are_refused(
    hass, aioclient_mock, hass_client_no_auth
):
    entry = await setup_bridge(hass, aioclient_mock)
    events = record_events(hass)
    client = await hass_client_no_auth()
    per_second = RATE_LIMITS[0][1]
    with patch.object(online, "monotonic", return_value=100.0):
        for _ in range(per_second):
            assert await call(client, query="?event=t20") == (HTTPStatus.OK, "ok")
        assert await call(client, query="?event=t20") == (
            HTTPStatus.TOO_MANY_REQUESTS,
            "too many calls",
        )
    # A second later, the bridge accepts calls again.
    with patch.object(online, "monotonic", return_value=101.0):
        assert await call(client, query="?event=t20") == (HTTPStatus.OK, "ok")
    await hass.async_block_till_done()
    assert len(events) == per_second + 1
    assert entry.runtime_data.bridge.counts["limited"] == 1


async def test_a_minute_of_calls_is_limited_too(
    hass, aioclient_mock, hass_client_no_auth
):
    """A leaked address cannot keep the recorder and the lights busy for long."""
    entry = await setup_bridge(hass, aioclient_mock)
    events = record_events(hass)
    client = await hass_client_no_auth()
    (_, per_second), (minute, per_minute) = RATE_LIMITS
    # Always fewer calls than the limit per second, until the minute is full.
    spacing = 1.0 / (per_second - 1)
    moments = [100.0 + index * spacing for index in range(per_minute)]
    for moment in moments:
        with patch.object(online, "monotonic", return_value=moment):
            assert await call(client, query="?event=t20") == (HTTPStatus.OK, "ok")
    later = moments[-1] + 1.0
    assert later - moments[0] < minute
    with patch.object(online, "monotonic", return_value=later):
        assert await call(client, query="?event=t20") == (
            HTTPStatus.TOO_MANY_REQUESTS,
            "too many calls",
        )
    # Once the first call is a minute old, the next one is welcome.
    with patch.object(online, "monotonic", return_value=moments[0] + minute):
        assert await call(client, query="?event=t20") == (HTTPStatus.OK, "ok")
    await hass.async_block_till_done()
    assert len(events) == per_minute + 1
    assert entry.runtime_data.bridge.counts["limited"] == 1


async def test_calls_over_the_websocket_api(hass, aioclient_mock, hass_ws_client):
    """Home Assistant's own test call passes a request with a different reader."""
    await setup_bridge(hass, aioclient_mock)
    events = record_events(hass)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "webhook/handle",
            "webhook_id": WEBHOOK_ID,
            "method": "POST",
            "body": '{"event": "busted"}',
        }
    )
    result = (await client.receive_json())["result"]
    assert (result["status"], result["body"]) == (HTTPStatus.OK, "ok")
    await hass.async_block_till_done()
    assert [event["event_type"] for event in events] == ["online_busted"]


@pytest.mark.parametrize(("remote", "answer"), [(False, ""), (True, "ok")])
async def test_calls_from_outside_the_home_network(
    hass, aioclient_mock, hass_client_no_auth, remote, answer
):
    """Home Assistant refuses them silently unless remote calls are allowed."""
    await setup_bridge(
        hass, aioclient_mock, options={**BRIDGE, "online_bridge_remote": remote}
    )
    events = record_events(hass)
    client = await hass_client_no_auth()
    with patch(
        "homeassistant.components.webhook.network_util.is_local", return_value=False
    ):
        assert await call(client, query="?event=180") == (HTTPStatus.OK, answer)
    await hass.async_block_till_done()
    assert len(events) == (1 if remote else 0)


async def test_a_switched_off_or_unloaded_bridge_does_not_answer(
    hass, aioclient_mock, hass_client_no_auth
):
    # Home Assistant's default configuration loads webhooks.
    assert await async_setup_component(hass, "webhook", {})
    entry = await setup_bridge(
        hass, aioclient_mock, options={**BRIDGE, "online_bridge": False}
    )
    assert entry.runtime_data.bridge is None
    assert hass.states.get(SENSOR) is None
    events = record_events(hass)
    client = await hass_client_no_auth()
    # Home Assistant answers every unknown address alike, so it gives nothing away.
    assert await call(client, query="?event=180") == (HTTPStatus.OK, "")
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["online_bridge"] == {"enabled": False}

    hass.config_entries.async_update_entry(entry, options=BRIDGE)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    events = record_events(hass)
    assert await call(client, query="?event=180") == (HTTPStatus.OK, "ok")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await call(client, query="?event=180") == (HTTPStatus.OK, "")
    assert len(events) == 1


async def test_sensor_remembers_the_last_event_across_restarts(hass, aioclient_mock):
    mock_restore_cache(
        hass,
        [
            State(
                SENSOR,
                "2026-09-26T20:15:00+00:00",
                {"trigger": "180", "event_type": "online_visit"},
            )
        ],
    )
    entry = await setup_bridge(hass, aioclient_mock)
    sensor = hass.states.get(SENSOR)
    assert sensor.state == "2026-09-26T20:15:00+00:00"
    assert sensor.attributes["trigger"] == "180"
    assert sensor.attributes["event_type"] == "online_visit"
    bridge = entry.runtime_data.bridge
    assert bridge.diagnostics()["last_event"] == "2026-09-26T20:15:00+00:00"

    # A newer moment is never replaced by an older one.
    bridge.restore(dt_util.utcnow(), "busted", "online_busted")
    assert bridge.last_trigger == "180"


def test_restore_keeps_only_valid_values():
    bridge = object.__new__(online.OnlineBridge)
    bridge.last_event = None
    bridge.restore(None, "180", "online_visit")
    assert bridge.last_event is None
    moment = dt_util.utcnow()
    bridge.restore(moment, 180, None)
    assert (bridge.last_event, bridge.last_trigger, bridge.last_event_type) == (
        moment,
        None,
        None,
    )


async def test_sensor_after_a_restart_without_an_event(hass, aioclient_mock):
    mock_restore_cache(hass, [State(SENSOR, "unknown", {})])
    await setup_bridge(hass, aioclient_mock)
    assert hass.states.get(SENSOR).state == "unknown"


async def test_no_bridge_without_webhooks(hass, aioclient_mock):
    with patch.object(online, "async_setup_component", return_value=False):
        loaded = await setup_bridge(hass, aioclient_mock)
    assert loaded.runtime_data.bridge is None


async def test_entities_and_diagnostics_of_the_bridge(
    hass, aioclient_mock, hass_client, snapshot: SnapshotAssertion
):
    """The bridge adds one diagnostic sensor; diagnostics keep the address secret."""
    assert await async_setup_component(hass, "diagnostics", {})
    entry = await setup_bridge(hass, aioclient_mock)
    added = {
        unique_id: summary
        for unique_id, summary in entity_summary(hass, entry).items()
        if "online" in unique_id
    }
    assert added == snapshot
    client = await hass_client()
    assert (await client.get(f"{PATH}?event=busted")).status == HTTPStatus.OK
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert WEBHOOK_ID not in json.dumps(diagnostics)
    assert diagnostics["online_bridge"] == snapshot(exclude=props("last_event"))
