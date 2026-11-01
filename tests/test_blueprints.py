"""The automation blueprints, run by Home Assistant's own automation engine."""

import asyncio
import importlib.util
import json
import logging
import random
import re
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, quote, urlsplit

import pytest
import voluptuous as vol
from homeassistant.components.blueprint import models
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.core import CoreState, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
    get_scheduled_timer_handles,
)
from yaml import safe_dump, safe_load

from custom_components.homedarts.bot import Bot
from custom_components.homedarts.highlights import photo_stem
from custom_components.homedarts.local_coordinator import EVENT_TYPES
from custom_components.homedarts.services import _game_key, async_setup_services

from .local_helpers import (
    BASE,
    BLUEPRINTS,
    BULL,
    EVENTS,
    JPEG,
    MISS,
    OUTER_BULL,
    S20,
    T20,
    automate,
    automate_all,
    board,
    camera_picture,
    entity_id,
    fire,
    setup_bridge,
    setup_cameras,
)
from .local_helpers import WEBHOOK_PATH as ONLINE_BRIDGE
from .test_docs_links import slug
from .test_manual_board import setup_manual

pytestmark = pytest.mark.usefixtures("blueprint_folder")

ROOT = Path(__file__).parents[1]
PATHS = sorted(BLUEPRINTS.glob("*.yaml"))
SOURCE = "https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/blueprints/automation/homedarts/"
IMPORT = re.compile(
    r"https://my\.home-assistant\.io/redirect/blueprint_import/\?blueprint_url=[^)\s\"']+"
)
# The guide's section of a blueprint, which the end of its description links to.
GUIDE = "https://dennis-otto.github.io/homedarts-for-autodarts/automations.html#"
GUIDE_LINK = re.compile(r"\n\n\[Settings and examples in the guide\]\((\S+)\)$")
# Attributes a blueprint reads from a board event.
READS = re.compile(r"(?:attributes|event)\.get\('(\w+)'|attributes\.(?!get\b)(\w+)")
S1 = ("S1", 1, 1)
D20 = ("D20", 20, 2)
MOMENTS = (
    "maximum",
    "high_finish",
    "bust",
    "leg",
    "match",
    "personal_best",
    "daily_goal",
    "bull_off",
    "achievement",
    "tournament",
)


async def fire_all(hass, events: list[tuple[str, dict]]) -> None:
    for kind, attributes in events:
        fire(hass, kind, **attributes)
        await hass.async_block_till_done()


async def until_waiting(hass, seconds: float) -> None:
    """Let a running automation reach a delay of the given length.

    async_block_till_done() would wait for the whole run, which never ends
    while the clock is frozen.
    """
    for _ in range(200):
        due = [
            handle.when() - hass.loop.time()
            for handle in get_scheduled_timer_handles(hass.loop)
        ]
        if any(seconds - 0.5 < left <= seconds for left in due):
            return
        await asyncio.sleep(0)
    raise AssertionError(f"no delay of {seconds} s started")


async def pass_time(hass, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def settle(hass) -> None:
    """Let triggered runs start, or join the queue behind a run that waits."""
    for _ in range(20):
        await asyncio.sleep(0)


async def saved(hass, name: str, inputs: dict, note: str = "") -> None:
    """Save an automation of the blueprint as the automation editor does.

    The first save sets it up; a later one sets it up anew if it changed,
    which forgets its waiting triggers, and every automation hears the
    automation_reloaded event.
    """
    config = {
        "automation": [
            {
                "id": name,
                "description": note,
                "use_blueprint": {"path": f"homedarts/{name}.yaml", "input": inputs},
            }
        ]
    }
    await hass.async_add_executor_job(
        Path(hass.config.path("configuration.yaml")).write_text,
        safe_dump(config),
        "utf-8",
    )
    if "automation" in hass.config.components:
        await hass.services.async_call(
            "automation", "reload", {"id": name}, blocking=True
        )
    else:
        assert await async_setup_component(hass, "automation", config)
    await settle(hass)


async def reloaded(hass) -> None:
    """Reload every automation, as saving another one does: unchanged
    automations keep running, with their waiting triggers."""
    await hass.services.async_call("automation", "reload", blocking=True)
    await settle(hass)


async def photo_taken(hass, freezer) -> None:
    """The highlight photo waits half a second for a leg won by the same dart."""
    await until_waiting(hass, 0.5)
    await settle(hass)
    await pass_time(hass, freezer, 0.5)


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def listened(path: Path) -> set[str]:
    """The board events a blueprint triggers on."""
    return {
        kind
        for node in walk(load_yaml(path))
        if node.get("trigger") == "event.received"
        for kind in node["options"]["event_type"]
    }


def read_attributes(path: Path) -> set[str]:
    return {
        name or attribute
        for name, attribute in READS.findall(path.read_text(encoding="utf-8"))
    }


def spoken(calls) -> list[str]:
    return [str(call.data["message"]) for call in calls]


def voice_pack(hass, tmp_path, *files: str) -> list:
    """A voice pack of darts-caller in the media folder, the actions of the
    integration that find its sounds, and the sounds played on the speakers."""
    pack = tmp_path / "media" / "homedarts" / "voices" / "russ-bray"
    pack.mkdir(parents=True)
    for file in files:
        (pack / file).write_bytes(b"ID3")
    hass.config.media_dirs = {"local": str(tmp_path / "media")}
    async_setup_services(hass)
    return async_mock_service(hass, "media_player", "play_media")


def played(calls) -> list[str]:
    """The files of the voice pack the speakers played."""
    prefix = "media-source://media_source/local/homedarts/voices/russ-bray/"
    assert all(call.data["media_content_type"] == "music" for call in calls)
    assert all(call.data["entity_id"] == ["media_player.dartroom"] for call in calls)
    return [call.data["media_content_id"].removeprefix(prefix) for call in calls]


VOICE = {
    "board_events": EVENTS,
    "tts_engine": "tts.home_assistant_cloud",
    "speakers": ["media_player.dartroom"],
}


# -- every blueprint ------------------------------------------------------------


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.stem)
def test_blueprint_metadata(path):
    blueprint = models.Blueprint(
        load_yaml(path), expected_domain="automation", schema=BLUEPRINT_SCHEMA
    )
    metadata = blueprint.metadata
    assert metadata["name"].startswith("HomeDarts: ")
    assert metadata["source_url"] == SOURCE + path.name
    # The blueprints need the same Home Assistant as the integration.
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert metadata["homeassistant"]["min_version"] == hacs["homeassistant"]
    assert metadata["author"] == "Dennis Otto"
    # Every input explains itself in the blueprint editor.
    for key, entry in blueprint.inputs.items():
        assert entry and entry.get("description"), f"{path.stem}: {key}"


def test_every_blueprint_links_its_section_of_the_guide():
    """The description of each blueprint ends with a link to its own section of the
    blueprint settings in the guide, so the blueprint editor leads to the settings
    and examples on the website."""
    guide = (ROOT / "docs" / "automations.md").read_text(encoding="utf-8")
    settings = guide.split("\n## Blueprint settings\n", 1)[1].split("\n## ", 1)[0]
    sections = {slug(heading) for heading in re.findall(r"^### (.+)$", settings, re.M)}
    linked = {}
    for path in PATHS:
        description = load_yaml(path)["blueprint"]["description"]
        link = GUIDE_LINK.search(description)
        assert link and link[1].startswith(GUIDE), path.stem
        linked[path.stem] = link[1].removeprefix(GUIDE)
    # A section of the blueprint settings, and one of its own.
    assert set(linked.values()) <= sections, linked
    assert len(set(linked.values())) == len(PATHS), linked


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.stem)
def test_blueprints_listen_to_events_of_the_integration(path):
    assert listened(path) <= set(EVENT_TYPES)


@pytest.mark.parametrize(
    "document", ["README.md", "docs/automations.md", "docs/automations.de.md"]
)
def test_documents_import_every_blueprint(document):
    """Each import button opens the blueprint file on the main branch."""
    text = (ROOT / document).read_text(encoding="utf-8")
    imported = set()
    for link in IMPORT.findall(text):
        encoded = link.split("blueprint_url=", 1)[1]
        (url,) = parse_qs(urlsplit(link).query)["blueprint_url"]
        # Fully encoded, as My Home Assistant expects it.
        assert encoded == quote(url, safe="")
        assert url.startswith(SOURCE), url
        imported.add(url.removeprefix(SOURCE))
    assert imported == {path.name for path in PATHS}


@pytest.mark.parametrize("document", ["docs/automations.md", "docs/automations.de.md"])
def test_the_documentation_lists_every_setting(document):
    """Each input of each blueprint has a row in the tables of the settings."""
    text = (ROOT / document).read_text(encoding="utf-8")
    rows: set[str] = set()
    for cell in re.findall(r"^\| ([^|]+?) \|", text, re.MULTILINE):
        # Settings shared with another blueprint share a row.
        rows.update({cell, *cell.split(", ")})
    missing = [
        f"{path.stem}: {entry['name']}"
        for path in PATHS
        for entry in models.Blueprint(
            load_yaml(path), expected_domain="automation", schema=BLUEPRINT_SCHEMA
        ).inputs.values()
        if entry["name"] not in rows
    ]
    assert not missing, missing


def saves(hass) -> list:
    """The photos the blueprint has homedarts.save_highlight save, which answers
    as for a photo it saved."""
    return async_mock_service(
        hass,
        "homedarts",
        "save_highlight",
        response={
            "photo": "/media/homedarts/highlights/2026-09-26_21-05-33_180.jpg",
            "photo_url": "/media/local/homedarts/highlights/2026-09-26_21-05-33_180.jpg",
        },
    )


def photo_name(call) -> str:
    """The name of the photo the blueprint has saved to the gallery, without the
    moment it was taken."""
    assert call.data["folder"] == "", call.data["folder"]
    assert call.data["camera"] == "camera.autodarts_board_camera_1"
    stem = photo_stem(
        datetime(2026, 9, 26, tzinfo=UTC), call.data["player"], str(call.data["label"])
    )
    return stem[20:] + ".jpg"


PHOTO = {
    "board_events": EVENTS,
    "camera": "camera.autodarts_board_camera_1",
    "photo_actions": [
        {
            "action": "test.photo",
            "data": {"image": "{{ image }}", "message": "{{ message }}"},
        }
    ],
}
# The photo as the actions get it: the saved file, its address and the camera.
SAVED = {
    **PHOTO,
    "photo_actions": [
        {
            "action": "test.photo",
            "data": {
                "image": "{{ image }}",
                "message": "{{ message }}",
                "photo": "{{ photo }}",
                "photo_url": "{{ photo_url }}",
            },
        }
    ],
}


class Steady(random.Random):
    """A hand without scatter: every dart of the bot lands where it aims."""

    def gauss(self, mu: float = 0.0, sigma: float = 1.0) -> float:
        return mu


# -- the real board events -------------------------------------------------------


async def visit(hass, coordinator, *darts) -> None:
    """Throw dart by dart, then pull the darts."""
    for count in range(1, len(darts) + 1):
        coordinator.async_receive("state", board(*darts[:count]))
        await hass.async_block_till_done()
    coordinator.async_receive("state", board(*darts, event="Takeout started"))
    coordinator.async_receive("state", board(event="Takeout finished"))
    await hass.async_block_till_done()


async def bot_visit(hass) -> None:
    """The bot throws its darts, each after its delay, and ends its visit."""
    for _ in range(4):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done()


async def test_blueprints_follow_the_real_board_events(
    hass, aioclient_mock, hass_client_no_auth
):
    """A practice match, free play and an online match on the board events."""
    entry = await setup_bridge(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = entity_id(hass, "event", "board_events")
    payloads: dict[str, set[str]] = defaultdict(set)

    setups: set[str] = set()

    @callback
    def collect(event) -> None:
        attributes = event.data["new_state"].attributes
        if kind := attributes.get("event_type"):
            payloads[kind].update(attributes)
            setups.update(attributes.get("setup") or {})

    async def unchanged_board() -> dict:
        # A reconciliation read while the scenario waits finds the same board.
        return dict(coordinator.data["local"])

    async_track_state_change_event(hass, events, collect)
    speak = async_mock_service(hass, "tts", "speak")
    celebrate = async_mock_service(hass, "test", "celebrate")
    light = async_mock_service(hass, "test", "light")
    photos = async_mock_service(hass, "test", "photo")
    snapshots = saves(hass)
    switch_on = async_mock_service(hass, "switch", "turn_on")
    reports = async_mock_service(hass, "test", "report")
    voice = {**VOICE, "board_events": events}
    await automate_all(
        hass,
        [
            (
                "practice_caller",
                {
                    **voice,
                    "bull_off_turn_message": "{{ who }}, throw for the bull",
                    "bull_off_message": "{{ who }} to throw first. Game on!",
                },
            ),
            ("dart_caller", voice),
            (
                "visit_score",
                {
                    "board_events": events,
                    "celebration": [
                        {"action": "test.celebrate", "data": {"score": "{{ score }}"}}
                    ],
                },
            ),
            (
                "light_show",
                {
                    "board_events": events,
                    **{
                        f"{moment}_actions": [
                            {
                                "action": "test.light",
                                "data": {"moment": "{{ moment }}", "who": "{{ who }}"},
                            }
                        ]
                        for moment in MOMENTS
                    },
                    "online_matches": True,
                },
            ),
            (
                "training_session",
                {"board_events": events, "detection": "switch.detection"},
            ),
            # A visit crosses 100 points before its third dart, too.
            (
                "highlight_photo",
                {**PHOTO, "board_events": events, "minimum_score": 100},
            ),
            (
                "weekly_report",
                {
                    "board_events": events,
                    "notify_actions": [
                        {"action": "test.report", "data": {"message": "{{ message }}"}}
                    ],
                },
            ),
        ],
    )
    with patch.object(coordinator.client, "get_state", side_effect=unchanged_board):
        await coordinator.async_set_daily_goal(5)
        await coordinator.async_start_game(
            101, names=["Dennis", "Lea"], legs=1, sets=1, bull_off=True
        )
        await visit(hass, coordinator, BULL)
        await visit(hass, coordinator, S20)
        # 101 - 80 leaves 21: the third dart busts, and it is the fifth of the day.
        await visit(hass, coordinator, T20, S20, T20)
        await visit(hass, coordinator, T20, S1, D20)
        # A party game adds points and the next target to the turn.
        await coordinator.async_start_game("shanghai", names=["Dennis"])
        await visit(hass, coordinator, S1)
        await coordinator.async_play(0)
        await visit(hass, coordinator, T20, T20, T20)
        # A new session every morning keeps the board as it is.
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id(hass, "button", "reset_training")},
            blocking=True,
        )
        await hass.async_block_till_done()
        # The week ends now instead of on Monday.
        coordinator.reports.report.ends = dt_util.utcnow()
        await coordinator.reports._async_report(dt_util.utcnow())
        await hass.async_block_till_done()
        # A team match names the team of the player who checks out.
        await coordinator.async_start_game(
            101, names=["Dennis", "Lea", "Kim", "Sam"], bull_off=False, teams=True
        )
        await visit(hass, coordinator, T20, S1, D20)
    # Tools for Autodarts reports the moments of an online match; your own 180
    # comes from the board.
    client = await hass_client_no_auth()
    for query in (
        "event=busted&player=Lea",
        "event=gameshot_dennis",
        "event=matchshot",
        "event=180",
    ):
        assert (await client.get(f"{ONLINE_BRIDGE}?{query}")).status == 200
    await hass.async_block_till_done()

    assert spoken(speak) == [
        "Lea, throw for the bull",
        "Dennis to throw first. Game on! Dennis, you require 101",
        "No score",
        "Lea, you require 101",
        "Game shot, and the match, Lea!",
        # The dart caller waits for the end of the practice game.
        "One hundred and eighty!",
        "Game shot, and the match, Dennis & Kim!",
    ]
    assert [call.data for call in celebrate] == [{"score": 180}]
    assert [(call.data["moment"], call.data["who"]) for call in light] == [
        ("bull_off", "Dennis"),
        ("daily_goal", ""),
        ("bust", "Dennis"),
        ("personal_best", ""),
        ("match", "Lea"),
        # Lea's checkout of 101, first leg and first match unlock achievements.
        ("achievement", "Lea"),
        ("achievement", "Lea"),
        ("achievement", "Lea"),
        ("maximum", ""),
        ("personal_best", ""),
        ("match", "Dennis"),
        # Dennis checks out 101 for the team; the leg and the match count for Kim, too.
        ("achievement", "Dennis"),
        ("achievement", "Dennis"),
        ("achievement", "Dennis"),
        ("achievement", "Kim"),
        ("achievement", "Kim"),
        ("bust", "Lea"),
        ("leg", "Dennis"),
        ("match", ""),
    ]
    assert not switch_on
    assert [call.data["message"] for call in photos] == [
        "140!",
        "Checkout 101 by Lea!",
        "180!",
        "Checkout 101 by Dennis!",
    ]
    assert [call.data["message"] for call in reports] == [
        "12 darts, 1 session. 3-dart average 123.0. Best visit 180, 1 × 180. "
        "Checkout rate 100.0 %. 1 day in a row. 2 new personal bests."
    ]
    # The gallery names each photo by the time, the player at the board and the score.
    assert [photo_name(call) for call in snapshots] == [
        "Dennis_140.jpg",
        "Lea_checkout-101.jpg",
        "180.jpg",
        "Dennis_checkout-101.jpg",
    ]

    # A round robin of three at 101, everybody winning once: the order of the
    # draw makes Dennis the winner, and the light show plays the tournament.
    with patch.object(coordinator.client, "get_state", side_effect=unchanged_board):
        await coordinator.async_start_tournament(
            players=["Dennis", "Lea", "Kim"],
            game="101",
            legs=1,
            sets=1,
            pause=0,
            rules={"bull_off": False},
        )
        for _ in range(3):
            await visit(hass, coordinator, T20, S1, D20)
            if coordinator.games.tournament.waiting:
                await coordinator.async_next_tournament_match()
    await hass.async_block_till_done()
    assert (light[-2].data["moment"], light[-1].data) == (
        "match",
        {"moment": "tournament", "who": "Dennis"},
    )

    # Against a bot whose darts land where it aims: 180, 180 and 141. Its
    # darts are not in the board, so only the callers name it. Dennis starts
    # at 169, which leaves no checkout, and the turn names a setup instead.
    coordinator.games.bot = Bot(Steady())
    heard, shown = len(speak), (len(light), len(celebrate), len(snapshots))
    with patch.object(coordinator.client, "get_state", side_effect=unchanged_board):
        await coordinator.async_start_game(
            501,
            names=["Dennis"],
            legs=1,
            sets=1,
            double_out=True,
            bull_off=False,
            teams=False,
            start_scores=[169],
            bot_level=120,
        )
        for _ in range(3):
            await visit(hass, coordinator, S1, S1, S1)
            await bot_visit(hass)
    assert spoken(speak)[heard:] == [
        "Bot, you require 141",
        "Game shot, and the match, Bot!",
    ]
    assert (len(light), len(celebrate), len(snapshots)) == shown

    # A round limit of one round decides the match without a checkout: the
    # lowest score wins, and the caller names the winner.
    heard = len(speak)
    with patch.object(coordinator.client, "get_state", side_effect=unchanged_board):
        await coordinator.async_start_game(
            301,
            names=["Dennis", "Lea"],
            legs=1,
            sets=1,
            bull_off=False,
            teams=False,
            bot_level=0,
            start_scores=[],
            max_rounds=1,
        )
        await visit(hass, coordinator, S1, S1, S1)
        await visit(hass, coordinator, T20, S1, S1)
    assert spoken(speak)[heard:][-1] == "Round limit, and the match, Lea!"

    # Whatever a blueprint reads is in the events it listens to.
    for path in PATHS:
        kinds = listened(path)
        if not kinds:
            continue
        assert kinds <= payloads.keys(), path.stem
        available = set().union(*(payloads[kind] for kind in kinds))
        assert read_attributes(path) <= available, path.stem
    # The practice caller reads the score to leave and the darts of a setup.
    assert {"leave", "route"} <= setups


# -- celebrate a visit score -------------------------------------------------------


async def test_visit_score_runs_actions_for_high_visits_once(hass):
    calls = async_mock_service(hass, "test", "celebrate")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "visit_score",
        {
            "board_events": EVENTS,
            "minimum_score": 100,
            "celebration": [
                {
                    "action": "test.celebrate",
                    "data": {"score": "{{ score }}", "segments": "{{ segments }}"},
                }
            ],
        },
    )
    three = {"darts": 3, "segments": ["T20", "T20", "S20"], "game": None}
    await fire_all(
        hass,
        [
            ("dart_detected", {"score": 60, "segment": "T20", "dart_index": 3}),
            # With the third dart, not again when the darts are pulled.
            ("visit_thrown", {"score": 140, **three}),
            ("visit_completed", {"score": 140, **three, "thrown": True}),
            ("visit_thrown", {"score": 60, **three}),
            # A shorter visit counts when it completes.
            (
                "visit_completed",
                {"score": 120, "darts": 2, "segments": ["T20", "T20"], "thrown": False},
            ),
            # An older integration without visit_thrown.
            ("visit_completed", {"score": 100, **three}),
        ],
    )
    assert [call.data["score"] for call in calls] == [140, 120, 100]
    assert calls[0].data["segments"] == ["T20", "T20", "S20"]


async def test_visit_score_leaves_the_bot_out_unless_asked(hass):
    mine = async_mock_service(hass, "test", "celebrate")
    every = async_mock_service(hass, "test", "every")
    hass.states.async_set(EVENTS, "unknown")
    await automate_all(
        hass,
        [
            (
                "visit_score",
                {
                    "board_events": EVENTS,
                    "minimum_score": 100,
                    "celebration": [
                        {"action": f"test.{action}", "data": {"score": "{{ score }}"}}
                    ],
                    "include_bot": action == "every",
                },
            )
            for action in ("celebrate", "every")
        ],
    )
    bot = {"game": 501, "name": None, "bot": True}
    await fire_all(
        hass,
        [
            ("visit_thrown", {"score": 180, "darts": 3, **bot}),
            ("visit_thrown", {"score": 140, "darts": 3, "game": 501, "name": "Lea"}),
            ("visit_completed", {"score": 100, "darts": 2, "thrown": False, **bot}),
        ],
    )
    # The bot's darts are not in the board.
    assert [call.data["score"] for call in mine] == [140]
    assert [call.data["score"] for call in every] == [180, 140, 100]


# -- dart caller ---------------------------------------------------------------------


async def test_dart_caller_announces_visits_and_darts(hass):
    calls = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "dart_caller", {**VOICE, "call_each_dart": True})
    await fire_all(
        hass,
        [
            ("dart_detected", {"segment": "T20", "score": 60, "dart_index": 1}),
            ("dart_detected", {"segment": "S5", "score": 5, "dart_index": 2}),
            # The third dart is called with its visit.
            ("dart_detected", {"segment": "T20", "score": 60, "dart_index": 3}),
            ("visit_thrown", {"score": 125, "darts": 3, "game": None}),
            ("visit_completed", {"score": 125, "darts": 3, "thrown": True}),
            ("dart_detected", {"segment": "D16", "score": 32, "dart_index": 1}),
            ("dart_detected", {"segment": "M", "score": 0, "dart_index": 2}),
            ("visit_completed", {"score": 32, "darts": 2, "thrown": False}),
            ("dart_detected", {"segment": "Bull", "score": 50, "dart_index": 1}),
            ("dart_detected", {"segment": "25", "score": 25, "dart_index": 2}),
            ("visit_thrown", {"score": 180, "darts": 3, "segments": ["T20"] * 3}),
        ],
    )
    assert spoken(calls) == [
        "Treble 20",
        "5",
        "125",
        "Double 16",
        "Miss",
        "32",
        "Bull",
        "25",
        "One hundred and eighty!",
    ]
    assert calls[0].data["media_player_entity_id"] == ["media_player.dartroom"]
    assert calls[0].data["cache"] is True
    assert "language" not in calls[0].data and "options" not in calls[0].data


async def test_dart_caller_skips_darts_and_practice_games_by_default(hass):
    calls = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass, "dart_caller", {**VOICE, "visit_message": "{{ score }} points"}
    )
    await fire_all(
        hass,
        [
            ("dart_detected", {"segment": "T20", "score": 60, "dart_index": 1}),
            # The practice caller has the floor during a practice game.
            ("visit_thrown", {"score": 140, "darts": 3, "game": 501}),
            ("visit_thrown", {"score": 100, "darts": 3, "game": None}),
        ],
    )
    assert spoken(calls) == ["100 points"]


async def test_dart_caller_in_practice_games_with_its_own_voice(hass):
    calls = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "dart_caller",
        {
            **VOICE,
            "silent_in_practice_games": False,
            "language": "de-DE",
            "tts_options": {"voice": "KatjaNeural"},
            "visit_message": "{{ score }} Punkte",
            "maximum_message": "",
        },
    )
    await fire_all(
        hass,
        [
            ("visit_thrown", {"score": 140, "darts": 3, "game": "cricket"}),
            # An empty message stays silent.
            ("visit_thrown", {"score": 180, "darts": 3, "game": 501}),
        ],
    )
    assert spoken(calls) == ["140 Punkte"]
    assert calls[0].data["language"] == "de-DE"
    assert calls[0].data["options"] == {"voice": "KatjaNeural"}


async def test_dart_caller_plays_the_sounds_of_a_voice_pack(hass, tmp_path):
    """The scores and darts the pack has are its recorded sounds; the engine
    speaks the rest, and every call of a pack that does not exist."""
    calls = async_mock_service(hass, "tts", "speak")
    sounds = voice_pack(
        hass,
        tmp_path,
        "t20.mp3",
        "5.mp3",
        "125.mp3",
        "Outside.wav",
        "bullseye.mp3",
        "bull.mp3",
        "180+1.mp3",
    )
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "dart_caller",
        {**VOICE, "call_each_dart": True, "voice_pack": "russ-bray"},
    )
    await fire_all(
        hass,
        [
            ("dart_detected", {"segment": "T20", "score": 60, "dart_index": 1}),
            ("dart_detected", {"segment": "S5", "score": 5, "dart_index": 2}),
            ("visit_thrown", {"score": 125, "darts": 3, "game": None}),
            ("dart_detected", {"segment": "D16", "score": 32, "dart_index": 1}),
            ("dart_detected", {"segment": "M", "score": 0, "dart_index": 2}),
            ("visit_completed", {"score": 32, "darts": 2, "thrown": False}),
            ("dart_detected", {"segment": "Bull", "score": 50, "dart_index": 1}),
            ("dart_detected", {"segment": "25", "score": 25, "dart_index": 2}),
            ("visit_thrown", {"score": 180, "darts": 3, "segments": ["T20"] * 3}),
        ],
    )
    assert played(sounds) == [
        "t20.mp3",
        "5.mp3",
        "125.mp3",
        "Outside.wav",
        "bullseye.mp3",
        "bull.mp3",
        "180+1.mp3",
    ]
    assert spoken(calls) == ["Double 16", "32"]


async def test_dart_caller_speaks_what_no_voice_pack_has(hass, tmp_path):
    calls = async_mock_service(hass, "tts", "speak")
    sounds = voice_pack(hass, tmp_path, "100.mp3")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "dart_caller", {**VOICE, "voice_pack": "piper-en"})
    await fire_all(hass, [("visit_thrown", {"score": 100, "darts": 3, "game": None})])
    assert sounds == []
    assert spoken(calls) == ["100"]


@pytest.mark.parametrize("pack", ["   ", "p" * 65])
async def test_dart_caller_speaks_with_a_pack_no_folder_can_have(hass, tmp_path, pack):
    calls = async_mock_service(hass, "tts", "speak")
    sounds = voice_pack(hass, tmp_path, "100.mp3")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "dart_caller", {**VOICE, "voice_pack": pack})
    await fire_all(hass, [("visit_thrown", {"score": 100, "darts": 3, "game": None})])
    assert sounds == []
    assert spoken(calls) == ["100"]


async def test_dart_caller_finds_a_pack_named_with_spaces_around(hass, tmp_path):
    sounds = voice_pack(hass, tmp_path, "100.mp3")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "dart_caller", {**VOICE, "voice_pack": " russ-bray "})
    await fire_all(hass, [("visit_thrown", {"score": 100, "darts": 3, "game": None})])
    assert played(sounds) == ["100.mp3"]


# -- practice caller -------------------------------------------------------------------


async def test_practice_caller_calls_requirements_busts_and_game_shots(hass):
    calls = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "practice_caller", VOICE)
    match = {"game": 501, "players": 2}
    await fire_all(
        hass,
        [
            (
                "turn_changed",
                {
                    **match,
                    "player": 2,
                    "name": "Sam",
                    "remaining": 81,
                    "checkout": "T15 D18",
                },
            ),
            # No checkout possible and no turn message: silent.
            (
                "turn_changed",
                {
                    **match,
                    "player": 1,
                    "name": None,
                    "remaining": 321,
                    "checkout": None,
                },
            ),
            ("bust", {**match, "player": 1, "name": None, "remaining": 32}),
            (
                "leg_won",
                {**match, "player": 2, "name": "Sam", "darts": 15, "match": False},
            ),
            # The deciding leg leaves the call to the match.
            (
                "leg_won",
                {**match, "player": 2, "name": "Sam", "darts": 12, "match": True},
            ),
            ("match_won", {**match, "player": 2, "name": "Sam", "sets": 1}),
            (
                "turn_changed",
                {
                    "game": 501,
                    "players": 1,
                    "player": 1,
                    "name": None,
                    "remaining": 40,
                    "checkout": "D20",
                },
            ),
            (
                "leg_won",
                {"game": 501, "players": 1, "player": 1, "name": None, "match": False},
            ),
            # Cricket has no checkout: the next player stays silent.
            (
                "turn_changed",
                {
                    "game": "cricket",
                    "players": 2,
                    "player": 2,
                    "name": "Sam",
                    "remaining": None,
                    "checkout": None,
                    "points": 40,
                },
            ),
            ("leg_won", {"game": "cricket", "players": 2, "player": 2, "name": "Sam"}),
        ],
    )
    assert spoken(calls) == [
        "Sam, you require 81",
        "No score",
        "Game shot, and the leg, Sam!",
        "Game shot, and the match, Sam!",
        "You require 40",
        "Game shot, and the leg!",
        "Game shot, and the leg, Sam!",
    ]


async def test_practice_caller_plays_the_sounds_of_a_voice_pack(hass, tmp_path):
    """A bust, the game shot and the match, and what you require alone are the
    pack's sounds; a call that names the player is the engine's, as is what the
    pack lacks."""
    calls = async_mock_service(hass, "tts", "speak")
    sounds = voice_pack(
        hass, tmp_path, "yr_40.mp3", "busted.mp3", "gameshot.mp3", "matchshot.mp3"
    )
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "practice_caller", {**VOICE, "voice_pack": "russ-bray"})
    alone = {"game": 501, "players": 1, "player": 1, "name": None}
    match = {"game": 501, "players": 2, "player": 2, "name": "Sam"}
    await fire_all(
        hass,
        [
            ("turn_changed", {**alone, "remaining": 40, "checkout": "D20"}),
            # Alone, the pack calls a player with a profile name, too.
            (
                "turn_changed",
                {**alone, "name": "Alex", "remaining": 40, "checkout": "D20"},
            ),
            ("turn_changed", {**alone, "remaining": 41, "checkout": "S1 D20"}),
            ("turn_changed", {**match, "remaining": 40, "checkout": "D20"}),
            ("bust", {**match, "remaining": 32}),
            ("leg_won", {**match, "darts": 15, "match": False}),
            ("leg_won", {**match, "rounds": 10, "remaining": 132, "match": False}),
            ("match_won", {**match, "sets": 1}),
        ],
    )
    assert played(sounds) == [
        "yr_40.mp3",
        "yr_40.mp3",
        "busted.mp3",
        "gameshot.mp3",
        "matchshot.mp3",
    ]
    assert spoken(calls) == [
        "You require 41",
        "Sam, you require 40",
        "Round limit, and the leg, Sam!",
    ]


async def test_practice_caller_names_the_team_of_a_team_match(hass):
    calls = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "practice_caller", VOICE)
    teams = {"game": 501, "players": 4, "player": 3, "name": "Kim", "team": 1}
    await fire_all(
        hass,
        [
            ("leg_won", {**teams, "team_name": "Alex & Kim", "match": False}),
            # Without both names, the player at the board is named.
            ("leg_won", {**teams, "team_name": None, "match": False}),
            ("match_won", {**teams, "team_name": "Alex & Kim"}),
        ],
    )
    assert spoken(calls) == [
        "Game shot, and the leg, Alex & Kim!",
        "Game shot, and the leg, Kim!",
        "Game shot, and the match, Alex & Kim!",
    ]


async def test_practice_caller_names_the_winner_of_the_round_limit(hass):
    calls = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "practice_caller",
        {**VOICE, "round_limit_leg_message": "{{ who }} wins on {{ remaining }}"},
    )
    match = {"game": 501, "players": 2, "player": 1, "name": "Lea", "checkout": None}
    teams = {"game": 501, "players": 4, "player": 3, "name": "Kim", "team": 1}
    await fire_all(
        hass,
        [
            ("leg_won", {**match, "rounds": 10, "remaining": 132, "match": False}),
            ("leg_won", {**match, "rounds": 10, "remaining": 40, "match": True}),
            ("match_won", {**match, "rounds": 10}),
            ("match_won", {**teams, "team_name": "Alex & Kim", "rounds": 3}),
            ("leg_won", {**match, "name": None, "players": 1, "match": False}),
        ],
    )
    assert spoken(calls) == [
        "Lea wins on 132",
        "Round limit, and the match, Lea!",
        "Round limit, and the match, Alex & Kim!",
        "Game shot, and the leg!",
    ]


async def test_practice_caller_names_unnamed_players_in_its_language(hass):
    calls = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "practice_caller",
        {
            **VOICE,
            "turn_message": "{{ who }} ist dran{{ ', ' ~ target if target }}",
            "player_label": "Spieler",
            "language": "de-DE",
        },
    )
    party = {"game": "shanghai", "players": 3, "remaining": None, "checkout": None}
    await fire_all(
        hass,
        [
            ("turn_changed", {**party, "player": 3, "name": None, "target": "7"}),
            (
                "turn_changed",
                {
                    "game": 501,
                    "players": 3,
                    "player": 1,
                    "name": None,
                    "remaining": 501,
                    "checkout": None,
                },
            ),
            # Without its own message, a bull-off throw is the next player's turn.
            (
                "turn_changed",
                {**party, "game": 501, "player": 2, "name": None, "bull_off": True},
            ),
            # A won bull-off stays silent without its message.
            ("bull_off_won", {**party, "game": 501, "player": 2, "distance": 5.0}),
            (
                "turn_changed",
                {**party, "game": 501, "player": 2, "name": None, "remaining": 501},
            ),
        ],
    )
    assert spoken(calls) == [
        "Spieler 3 ist dran, 7",
        "Spieler 1 ist dran",
        "Spieler 2 ist dran",
        "Spieler 2 ist dran",
    ]
    assert calls[0].data["language"] == "de-DE"


async def test_practice_caller_calls_the_bull_off(hass):
    calls = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "practice_caller",
        {
            **VOICE,
            "bull_off_turn_message": "{{ who }}, throw for the bull",
            "bull_off_message": (
                "{{ who }} wins the bull with {{ hit }}"
                "{{ ', ' ~ distance ~ ' mm' if distance is number }}"
            ),
        },
    )
    match = {"game": 101, "players": 2, "remaining": None, "checkout": None}
    won = {**match, "player": 2, "name": "Lea", "hit": "S20"}
    await fire_all(
        hass,
        [
            ("turn_changed", {**match, "player": 2, "name": "Lea", "bull_off": True}),
            (
                "bull_off_won",
                {**match, "player": 1, "name": None, "hit": "BULL", "distance": 3.2},
            ),
            # The winner starts: one call for both.
            (
                "turn_changed",
                {
                    **match,
                    "player": 1,
                    "name": None,
                    "remaining": 101,
                    "checkout": "T17 BULL",
                },
            ),
            ("bull_off_won", {**won, "distance": 12.5}),
            ("turn_changed", {**match, "player": 2, "name": "Lea", "remaining": 501}),
            # A dart without a position has no distance, and nobody says "None".
            ("bull_off_won", {**won, "hit": "25", "distance": None}),
            ("turn_changed", {**match, "player": 2, "name": "Lea", "remaining": 501}),
        ],
    )
    assert spoken(calls) == [
        "Lea, throw for the bull",
        "Player 1 wins the bull with BULL, 3.2 mm Player 1, you require 101",
        "Lea wins the bull with S20, 12.5 mm",
        "Lea wins the bull with 25",
    ]


async def test_practice_caller_names_the_bot_like_the_scoreboard(hass):
    calls = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate_all(
        hass,
        [
            ("practice_caller", VOICE),
            (
                "practice_caller",
                {**VOICE, "speakers": ["media_player.kitchen"], "bot_label": "Robo"},
            ),
        ],
    )
    bot = {"game": 501, "players": 2, "player": 2, "name": None, "bot": True}
    await fire_all(
        hass,
        [
            ("turn_changed", {**bot, "remaining": 40, "checkout": "D20"}),
            ("bust", {**bot, "remaining": 40}),
            ("match_won", bot),
        ],
    )
    by_speaker = defaultdict(list)
    for call in calls:
        by_speaker[call.data["media_player_entity_id"][0]].append(call.data["message"])
    assert by_speaker == {
        "media_player.dartroom": [
            "Bot, you require 40",
            "No score",
            "Game shot, and the match, Bot!",
        ],
        "media_player.kitchen": [
            "Robo, you require 40",
            "No score",
            "Game shot, and the match, Robo!",
        ],
    }


# -- the language of Home Assistant ----------------------------------------------------


def translated(language: str) -> dict[str, str]:
    """The messages of the integration in a language, by their keys."""
    path = (
        ROOT / "custom_components" / "homedarts" / "translations" / f"{language}.json"
    )
    exceptions = json.loads(path.read_text(encoding="utf-8"))["exceptions"]
    return {key: entry["message"] for key, entry in exceptions.items()}


async def speaking_board(hass, aioclient_mock, language: str):
    """A board in a Home Assistant of the language, with the callers and the
    weekly report as they are imported, the dart caller calling every dart."""
    hass.config.language = language
    entry = await setup_bridge(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    voice = {**VOICE, "board_events": entity_id(hass, "event", "board_events")}
    await automate_all(
        hass,
        [
            ("practice_caller", voice),
            ("dart_caller", {**voice, "call_each_dart": True}),
            (
                "weekly_report",
                {
                    "board_events": voice["board_events"],
                    "notify_actions": [
                        {
                            "action": "test.report",
                            "data": {
                                "title": "{{ title }}",
                                "message": "{{ message }}",
                            },
                        }
                    ],
                },
            ),
        ],
    )
    return coordinator


async def play_a_short_match(hass, coordinator) -> None:
    """Dennis busts 101, and Lea checks it out."""

    async def unchanged_board() -> dict:
        return dict(coordinator.data["local"])

    with patch.object(coordinator.client, "get_state", side_effect=unchanged_board):
        await coordinator.async_start_game(
            101, names=["Dennis", "Lea"], legs=1, sets=1, bull_off=False
        )
        await visit(hass, coordinator, T20, S20, T20)
        await visit(hass, coordinator, T20, S1, D20)


async def end_the_week(hass, coordinator) -> None:
    coordinator.reports.report.ends = dt_util.utcnow()
    await coordinator.reports._async_report(dt_util.utcnow())
    await hass.async_block_till_done()


async def test_the_callers_and_the_report_speak_german_out_of_the_box(
    hass, aioclient_mock
):
    speak = async_mock_service(hass, "tts", "speak")
    reports = async_mock_service(hass, "test", "report")
    coordinator = await speaking_board(hass, aioclient_mock, "de")
    # Free play: the dart caller calls the darts and the visits.
    await visit(hass, coordinator, T20, T20, T20)
    await visit(hass, coordinator, S20, MISS)
    await visit(hass, coordinator, BULL, OUTER_BULL, D20)
    await play_a_short_match(hass, coordinator)
    await end_the_week(hass, coordinator)
    assert spoken(speak) == [
        "Triple 20",
        "Triple 20",
        "Einhundertachtzig!",
        "20",
        "Fehlwurf",
        "20",
        "Bull",
        "25",
        "115",
        # The practice caller has the floor during the practice game.
        "Überworfen",
        "Lea, du brauchst 101",
        "Game shot, und das Match, Lea!",
    ]
    assert [call.data for call in reports] == [
        {
            "title": "Deine Dartwoche",
            "message": "14 Darts. 3-Dart-Average 119,1. Beste Aufnahme 180, 1 × 180. "
            "Checkout-Quote 100,0 %. 1 Tag in Folge.",
        }
    ]


async def test_the_callers_follow_a_new_language_at_once(hass, aioclient_mock):
    speak = async_mock_service(hass, "tts", "speak")
    coordinator = await speaking_board(hass, aioclient_mock, "en")
    await visit(hass, coordinator, T20, T20, T20)
    await hass.config.async_update(language="nl")
    await hass.async_block_till_done()
    await visit(hass, coordinator, T20, T20, T20)
    assert spoken(speak) == [
        "Treble 20",
        "Treble 20",
        "One hundred and eighty!",
        "Triple 20",
        "Triple 20",
        "Honderdtachtig!",
    ]


@pytest.mark.parametrize("language", ["en", "de", "es-419", "fr", "nl"])
async def test_a_fresh_caller_and_report_speak_every_language(
    hass, aioclient_mock, language
):
    """In each language of the integration, also in a regional variant of it."""
    speak = async_mock_service(hass, "tts", "speak")
    reports = async_mock_service(hass, "test", "report")
    coordinator = await speaking_board(hass, aioclient_mock, language)
    await play_a_short_match(hass, coordinator)
    await end_the_week(hass, coordinator)
    say = translated(language.split("-")[0])
    assert spoken(speak) == [
        say["voice_pack_bust"],
        say["caller_require"].format(name="Lea", remaining=101),
        say["voice_match"].format(name="Lea"),
    ]
    (report,) = reports
    assert report.data["title"] == say["report_title"]
    message = report.data["message"]
    assert message.startswith(say["report_darts"].format(darts=6))
    assert message.endswith(say["report_streak_day"])


async def test_an_older_integration_leaves_the_blueprints_in_english(hass):
    """Events without the words of the integration, from a version before them,
    are called in English, as the blueprints called them before."""
    speak = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate_all(
        hass,
        [
            ("practice_caller", VOICE),
            ("dart_caller", {**VOICE, "call_each_dart": True}),
        ],
    )
    await fire_all(
        hass,
        [
            ("visit_thrown", {"score": 180, "darts": 3, "game": None}),
            ("dart_detected", {"segment": "T20", "score": 60, "dart_index": 1}),
            ("bust", {"game": 501, "players": 1, "player": 1, "remaining": 32}),
            # The winner of a match played alone is named by nobody.
            ("match_won", {"game": 501, "players": 1, "player": 1, "name": None}),
            (
                "match_won",
                {"game": 501, "players": 2, "player": 2, "name": "Lea", "rounds": 3},
            ),
        ],
    )
    assert spoken(speak) == [
        "One hundred and eighty!",
        "Treble 20",
        "No score",
        "Game shot, and the match!",
        "Round limit, and the match, Lea!",
    ]


async def test_the_words_of_a_won_bull_off_open_the_match(hass):
    speak = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "practice_caller",
        {
            **VOICE,
            "bull_off_message": "{{ bull_off_call }}",
            "turn_message": "{{ call }}",
        },
    )
    match = {"game": 501, "players": 2, "remaining": 501, "checkout": None}
    await fire_all(
        hass,
        [
            (
                "bull_off_won",
                {**match, "player": 2, "name": "Lea", "call": "Lea beginnt. Game on!"},
            ),
            (
                "turn_changed",
                {**match, "player": 2, "name": "Lea", "call": "{{ 6*7 }} ist dran."},
            ),
            (
                "turn_changed",
                {**match, "player": 1, "name": "Kim", "call": "Kim ist dran."},
            ),
        ],
    )
    # The template characters of a name never make a template.
    assert spoken(speak) == [
        "Lea beginnt. Game on! 6*7  ist dran.",
        "Kim ist dran.",
    ]


# -- takeout, detection, alerts ----------------------------------------------------


async def test_takeout_actions(hass):
    started = async_mock_service(hass, "test", "started")
    finished = async_mock_service(hass, "test", "finished")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "takeout",
        {
            "board_events": EVENTS,
            "takeout_started": [{"action": "test.started"}],
            "takeout_finished": [{"action": "test.finished"}],
        },
    )
    fire(hass, "takeout_started")
    await hass.async_block_till_done()
    assert (len(started), len(finished)) == (1, 0)
    fire(hass, "takeout_finished")
    await hass.async_block_till_done()
    assert (len(started), len(finished)) == (1, 1)


async def test_detection_follows_presence(hass):
    turned_on = async_mock_service(hass, "switch", "turn_on")
    turned_off = async_mock_service(hass, "switch", "turn_off")
    hass.states.async_set("binary_sensor.dartroom", "off")
    hass.states.async_set("switch.autodarts_detection", "off")
    await automate(
        hass,
        "auto_detection",
        {
            "presence": "binary_sensor.dartroom",
            "detection": "switch.autodarts_detection",
            "stop_after": {"minutes": 10},
        },
    )
    hass.states.async_set("binary_sensor.dartroom", "on")
    await hass.async_block_till_done()
    assert [call.data["entity_id"] for call in turned_on] == [
        ["switch.autodarts_detection"]
    ]
    hass.states.async_set("switch.autodarts_detection", "on")
    hass.states.async_set("binary_sensor.dartroom", "off")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert not turned_off
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=11))
    await hass.async_block_till_done()
    assert [call.data["entity_id"] for call in turned_off] == [
        ["switch.autodarts_detection"]
    ]


DETECTION = {
    "presence": "binary_sensor.dartroom",
    "detection": "switch.autodarts_detection",
    "stop_after": {"minutes": 10},
}


async def test_detection_stops_after_a_restart_while_nobody_is_there(hass, freezer):
    """A restart forgets the waiting for the presence: it starts over."""
    turned_off = async_mock_service(hass, "switch", "turn_off")
    hass.set_state(CoreState.not_running)
    hass.states.async_set("binary_sensor.dartroom", "off")
    hass.states.async_set("switch.autodarts_detection", "on")
    await saved(hass, "auto_detection", DETECTION)
    await hass.async_start()
    await until_waiting(hass, 600)
    # Saving another automation meanwhile changes nothing.
    freezer.tick(timedelta(minutes=1))
    await reloaded(hass)
    freezer.tick(timedelta(minutes=8))
    async_fire_time_changed(hass)
    await settle(hass)
    assert not turned_off
    await pass_time(hass, freezer, 60)
    assert [call.data["entity_id"] for call in turned_off] == [
        ["switch.autodarts_detection"]
    ]


async def test_detection_after_a_restart_stays_for_someone_who_arrives(hass, freezer):
    turned_off = async_mock_service(hass, "switch", "turn_off")
    hass.set_state(CoreState.not_running)
    hass.states.async_set("binary_sensor.dartroom", "off")
    hass.states.async_set("switch.autodarts_detection", "on")
    await saved(hass, "auto_detection", DETECTION)
    await hass.async_start()
    await until_waiting(hass, 600)
    hass.states.async_set("binary_sensor.dartroom", "on")
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 8 * 3600)
    assert not turned_off


async def test_detection_stops_after_its_automation_was_saved(hass, freezer):
    """Saving the automation sets it up anew; the waiting starts over."""
    turned_off = async_mock_service(hass, "switch", "turn_off")
    hass.states.async_set("switch.autodarts_detection", "on")
    hass.states.async_set("binary_sensor.dartroom", "on")
    await saved(hass, "auto_detection", DETECTION)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("binary_sensor.dartroom", "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=3))
    await saved(hass, "auto_detection", DETECTION, note="Saved again")
    await until_waiting(hass, 600)
    freezer.tick(timedelta(minutes=9))
    async_fire_time_changed(hass)
    await settle(hass)
    assert not turned_off
    await pass_time(hass, freezer, 60)
    assert len(turned_off) == 1


async def test_detection_stops_after_a_save_during_the_wait_of_a_restart(hass, freezer):
    """After a restart the sensors change in the order their integrations
    start, which says nothing about who started the detection: saving the
    automation while it waits starts the wait over."""
    turned_off = async_mock_service(hass, "switch", "turn_off")
    hass.set_state(CoreState.not_running)
    hass.states.async_set("binary_sensor.dartroom", "off")
    freezer.tick(timedelta(seconds=5))
    hass.states.async_set("switch.autodarts_detection", "on")
    freezer.tick(timedelta(seconds=5))
    await saved(hass, "auto_detection", DETECTION)
    await hass.async_start()
    await until_waiting(hass, 600)
    freezer.tick(timedelta(minutes=4))
    await saved(hass, "auto_detection", DETECTION, note="Saved again")
    await until_waiting(hass, 600)
    freezer.tick(timedelta(minutes=9))
    async_fire_time_changed(hass)
    await settle(hass)
    assert not turned_off
    await pass_time(hass, freezer, 60)
    assert len(turned_off) == 1


async def test_detection_started_by_hand_survives_a_reload(hass, freezer):
    """A detection started while nobody is there keeps running when an
    automation is saved; a reload that keeps this automation leaves its
    waiting alone."""
    turned_off = async_mock_service(hass, "switch", "turn_off")
    hass.states.async_set("binary_sensor.dartroom", "off")
    hass.states.async_set("switch.autodarts_detection", "off")
    await saved(hass, "auto_detection", DETECTION)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("switch.autodarts_detection", "on")
    await hass.async_block_till_done()
    await saved(hass, "auto_detection", DETECTION, note="Saved again")
    await reloaded(hass)
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 8 * 3600)
    assert not turned_off

    # Someone came and went: the presence decides again.
    hass.states.async_set("binary_sensor.dartroom", "on")
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("binary_sensor.dartroom", "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=4))
    await reloaded(hass)
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 5 * 60)
    assert not turned_off
    await pass_time(hass, freezer, 60)
    assert len(turned_off) == 1
    await pass_time(hass, freezer, 8 * 3600)
    assert len(turned_off) == 1


async def test_board_alert_waits_for_the_grace_period(hass, freezer):
    alerts = async_mock_service(hass, "test", "alert")
    recoveries = async_mock_service(hass, "test", "recovered")
    hass.states.async_set("binary_sensor.board_connection", "on")
    hass.states.async_set("binary_sensor.camera_problem", "off")
    await automate(
        hass,
        "board_alert",
        {
            "connection": "binary_sensor.board_connection",
            "camera_problem": "binary_sensor.camera_problem",
            "alert_actions": [
                {"action": "test.alert", "data": {"problem": "{{ problem }}"}}
            ],
            "recovery_actions": [
                {
                    "action": "test.recovered",
                    "data": {
                        "problem": "{{ problem }}",
                        "recovered": "{{ recovered }}",
                    },
                }
            ],
        },
    )
    # A short restart neither alerts nor reports a recovery.
    hass.states.async_set("binary_sensor.board_connection", "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    hass.states.async_set("binary_sensor.board_connection", "on")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=3))
    await hass.async_block_till_done()
    assert not alerts and not recoveries

    hass.states.async_set("binary_sensor.camera_problem", "on")
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 180)
    assert [call.data for call in alerts] == [{"problem": "cameras"}]
    hass.states.async_set("binary_sensor.camera_problem", "off")
    await hass.async_block_till_done()
    assert [call.data for call in recoveries] == [
        {"problem": "cameras", "recovered": True}
    ]

    # A camera that fails while the board restarts is a problem, too.
    hass.states.async_set("binary_sensor.camera_problem", "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.camera_problem", "on")
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 180)
    assert [call.data for call in alerts][-1] == {"problem": "cameras"}
    assert len(alerts) == 2

    # A board that stays offline, and its all-clear.
    hass.states.async_set("binary_sensor.board_connection", "off")
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 180)
    assert alerts[-1].data == {"problem": "offline"}
    hass.states.async_set("binary_sensor.board_connection", "on")
    await hass.async_block_till_done()
    assert recoveries[-1].data == {"problem": "offline", "recovered": True}
    assert (len(alerts), len(recoveries)) == (3, 2)


ALERT = {
    "connection": "binary_sensor.board_connection",
    "camera_problem": "binary_sensor.camera_problem",
    "alert_actions": [{"action": "test.alert", "data": {"problem": "{{ problem }}"}}],
    "recovery_actions": [
        {"action": "test.recovered", "data": {"problem": "{{ problem }}"}}
    ],
}


async def test_board_alert_for_a_problem_at_startup(hass, freezer):
    """A restart forgets the grace periods: a problem the board has when Home
    Assistant starts alerts after one, and its all-clear follows."""
    alerts = async_mock_service(hass, "test", "alert")
    recoveries = async_mock_service(hass, "test", "recovered")
    hass.set_state(CoreState.not_running)
    hass.states.async_set("binary_sensor.board_connection", "off")
    hass.states.async_set("binary_sensor.camera_problem", "on")
    await saved(hass, "board_alert", ALERT)
    await hass.async_start()
    await until_waiting(hass, 120)
    assert not alerts
    await pass_time(hass, freezer, 120)
    assert [call.data for call in alerts] == [
        {"problem": "offline"},
        {"problem": "cameras"},
    ]
    await pass_time(hass, freezer, 8 * 3600)
    assert len(alerts) == 2
    hass.states.async_set("binary_sensor.board_connection", "on")
    await hass.async_block_till_done()
    assert [call.data for call in recoveries] == [{"problem": "offline"}]


async def test_board_alert_at_startup_stays_quiet_for_a_short_problem(hass, freezer):
    alerts = async_mock_service(hass, "test", "alert")
    recoveries = async_mock_service(hass, "test", "recovered")
    hass.set_state(CoreState.not_running)
    hass.states.async_set("binary_sensor.board_connection", "off")
    hass.states.async_set("binary_sensor.camera_problem", "off")
    await saved(hass, "board_alert", ALERT)
    await hass.async_start()
    await until_waiting(hass, 120)
    freezer.tick(timedelta(seconds=30))
    hass.states.async_set("binary_sensor.board_connection", "on")
    await settle(hass)
    # It goes offline again: its own grace period starts then.
    freezer.tick(timedelta(seconds=30))
    hass.states.async_set("binary_sensor.board_connection", "off")
    await settle(hass)
    await pass_time(hass, freezer, 60)
    assert not alerts and not recoveries
    await pass_time(hass, freezer, 60)
    assert [call.data for call in alerts] == [{"problem": "offline"}]
    await pass_time(hass, freezer, 8 * 3600)
    assert len(alerts) == 1 and not recoveries


async def test_board_alert_after_its_automation_was_saved(hass, freezer):
    """Saving the automation sets it up anew: a problem whose grace period was
    running alerts after a new one; one that already alerted stays quiet."""
    alerts = async_mock_service(hass, "test", "alert")
    hass.states.async_set("binary_sensor.board_connection", "on")
    hass.states.async_set("binary_sensor.camera_problem", "off")
    await saved(hass, "board_alert", ALERT)
    hass.states.async_set("binary_sensor.board_connection", "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=90))
    await saved(hass, "board_alert", ALERT, note="Saved again")
    await until_waiting(hass, 120)
    # Saving another automation meanwhile changes nothing.
    freezer.tick(timedelta(seconds=10))
    await reloaded(hass)
    assert not alerts
    await pass_time(hass, freezer, 110)
    assert [call.data for call in alerts] == [{"problem": "offline"}]
    await saved(hass, "board_alert", ALERT, note="Saved once more")
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 8 * 3600)
    assert len(alerts) == 1


async def test_board_alert_after_its_automation_was_saved_twice(hass, freezer):
    """A second save, after the grace period of the problem, keeps the alert
    that the first save was waiting for; once it alerted, a save stays quiet."""
    alerts = async_mock_service(hass, "test", "alert")
    hass.states.async_set("binary_sensor.board_connection", "on")
    hass.states.async_set("binary_sensor.camera_problem", "off")
    await saved(hass, "board_alert", ALERT)
    freezer.tick(timedelta(seconds=1))
    hass.states.async_set("binary_sensor.board_connection", "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=90))
    await saved(hass, "board_alert", ALERT, note="Saved again")
    await until_waiting(hass, 120)
    freezer.tick(timedelta(seconds=40))
    await saved(hass, "board_alert", ALERT, note="Saved once more")
    await until_waiting(hass, 120)
    freezer.tick(timedelta(seconds=119))
    async_fire_time_changed(hass)
    await settle(hass)
    assert not alerts
    await pass_time(hass, freezer, 1)
    assert [call.data for call in alerts] == [{"problem": "offline"}]
    freezer.tick(timedelta(seconds=10))
    await saved(hass, "board_alert", ALERT, note="Saved after the alert")
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 8 * 3600)
    assert len(alerts) == 1


async def test_board_alert_ignores_the_reload_of_other_automations(hass, freezer):
    """A reload that keeps this automation keeps its grace periods, too: no
    second alert for the same problem."""
    alerts = async_mock_service(hass, "test", "alert")
    hass.states.async_set("binary_sensor.board_connection", "on")
    hass.states.async_set("binary_sensor.camera_problem", "off")
    await saved(hass, "board_alert", ALERT)
    freezer.tick(timedelta(seconds=1))
    hass.states.async_set("binary_sensor.board_connection", "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=60))
    await reloaded(hass)
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 60)
    assert [call.data for call in alerts] == [{"problem": "offline"}]
    await reloaded(hass)
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 8 * 3600)
    assert len(alerts) == 1


# -- training ------------------------------------------------------------------------


REPORT = {
    "darts_sensor": "sensor.autodarts_training_darts",
    "average_sensor": "sensor.autodarts_training_average",
    "highest_sensor": "sensor.autodarts_training_highest",
    "maximum_sensor": "sensor.autodarts_training_scores_180",
    "report_actions": [{"action": "test.report", "data": {"message": "{{ summary }}"}}],
}


def training_totals(hass, darts: str) -> None:
    for key, value in (
        ("darts", darts),
        ("average", "57.349"),
        ("highest", "140"),
        ("scores_180", "1"),
    ):
        hass.states.async_set(f"sensor.autodarts_training_{key}", value)


async def report_at(hass, freezer, day: str) -> None:
    freezer.move_to(f"2026-09-{day} 21:00:00+02:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_training_report(hass, freezer):
    reports = async_mock_service(hass, "test", "report")
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-09-26 20:59:00+02:00")
    training_totals(hass, "30")
    await automate(hass, "training_report", REPORT)
    await report_at(hass, freezer, "26")
    assert [call.data["message"] for call in reports] == [
        "30 darts, 3-dart average 57.3, highest visit 140, 1 × 180."
    ]

    # No report without training.
    hass.states.async_set("sensor.autodarts_training_darts", "0")
    await report_at(hass, freezer, "27")
    assert len(reports) == 1
    # Turning the automation off cancels the timer for the next day.
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "all"}, blocking=True
    )


async def test_training_report_skips_days_without_darts(hass, freezer):
    """A finished session keeps its totals; the board's darts today decide."""
    reports = async_mock_service(hass, "test", "report")
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-09-26 20:59:00+02:00")
    config_entry = MockConfigEntry(domain="homedarts")
    config_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("homedarts", "board-1")}
    )
    for key in ("training_darts", "darts_today"):
        er.async_get(hass).async_get_or_create(
            "sensor",
            "homedarts",
            f"board-1_{key}",
            config_entry=config_entry,
            device_id=device.id,
            suggested_object_id=f"autodarts_{key}",
        )
    training_totals(hass, "30")
    today = "sensor.autodarts_darts_today"
    hass.states.async_set(today, "12", {"goal": 0, "goal_reached": False})
    await automate(hass, "training_report", {**REPORT, "minimum_darts": 10})
    await report_at(hass, freezer, "26")
    assert [call.data["message"] for call in reports] == [
        "30 darts, 3-dart average 57.3, highest visit 140, 1 × 180."
    ]
    # The next day the session still shows 30 darts, but none were thrown.
    hass.states.async_set(today, "0", {"goal": 0, "goal_reached": False})
    await report_at(hass, freezer, "27")
    # Too few darts for the minimum.
    hass.states.async_set(today, "5", {"goal": 0, "goal_reached": False})
    await report_at(hass, freezer, "28")
    assert len(reports) == 1
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "all"}, blocking=True
    )


@pytest.mark.parametrize(
    ("language", "summary"),
    [
        ("en", "6 darts, 3-dart average 120.0, highest visit 180, 1 × 180."),
        ("de-CH", "6 Darts, 3-Dart-Average 120,0, höchste Aufnahme 180, 1 × 180."),
        ("es-419", "6 dardos, media de 3 dardos 120,0, tirada más alta 180, 1 × 180."),
    ],
    ids=["en", "de-CH", "es-419"],
)
async def test_the_training_report_speaks_the_language_of_home_assistant(
    hass, aioclient_mock, freezer, language, summary
):
    """Home Assistant translates no blueprint, and no board event starts the
    report: the "Training darts" sensor of the board has the words."""
    reports = async_mock_service(hass, "test", "report")
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-09-26 20:30:00+02:00")
    hass.config.language = language
    entry = await setup_bridge(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await visit(hass, coordinator, T20, T20, T20)
    await visit(hass, coordinator, S20, S20, S20)
    darts = entity_id(hass, "sensor", "training_darts")
    assert hass.states.get(darts).attributes["summary"] == summary
    await automate(
        hass,
        "training_report",
        {
            **REPORT,
            "darts_sensor": darts,
            "average_sensor": entity_id(hass, "sensor", "training_average"),
            "highest_sensor": entity_id(hass, "sensor", "training_highest_visit"),
            "maximum_sensor": entity_id(hass, "sensor", "training_scores_180"),
        },
    )
    await report_at(hass, freezer, "26")
    assert [call.data["message"] for call in reports] == [summary]
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "all"}, blocking=True
    )


async def test_the_training_summary_follows_a_new_language_at_once(
    hass, aioclient_mock
):
    entry = await setup_bridge(hass, aioclient_mock, state=board())
    await visit(hass, entry.runtime_data.local, T20, S20, MISS)
    darts = entity_id(hass, "sensor", "training_darts")
    assert hass.states.get(darts).attributes["summary"] == (
        "3 darts, 3-dart average 80.0, highest visit 80."
    )
    await hass.config.async_update(language="nl")
    await hass.async_block_till_done()
    assert hass.states.get(darts).attributes["summary"] == (
        "3 darts, 3-dart-gemiddelde 80,0, hoogste beurt 80."
    )
    # Without the words, such as a broken translation, the sensor has no
    # summary, and the training report writes its own.
    coordinator = entry.runtime_data.local
    del coordinator.caller.say["training_summary"]
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert "summary" not in hass.states.get(darts).attributes
    assert hass.states.get(darts).attributes["hits"] == {"T20": 1, "S20": 1, "MISS": 1}


async def test_the_training_report_has_its_own_words_without_the_sensors(hass, freezer):
    """A board of a release without the summary, or without its words, gets the
    report in English."""
    reports = async_mock_service(hass, "test", "report")
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-09-26 20:59:00+02:00")
    training_totals(hass, "30")
    hass.states.async_set(
        "sensor.autodarts_training_darts", "30", {"hits": {}, "summary": None}
    )
    await automate(hass, "training_report", REPORT)
    await report_at(hass, freezer, "26")
    assert [call.data["message"] for call in reports] == [
        "30 darts, 3-dart average 57.3, highest visit 140, 1 × 180."
    ]
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "all"}, blocking=True
    )


SESSION = {
    "board_events": EVENTS,
    "detection": "switch.autodarts_board_detection",
    "calibration": "button.autodarts_board_calibrate",
}


async def test_training_session_prepares_and_tidies_up_the_board(hass, freezer):
    turn_on = async_mock_service(hass, "switch", "turn_on")
    turn_off = async_mock_service(hass, "switch", "turn_off")
    press = async_mock_service(hass, "button", "press")
    light = async_mock_service(hass, "test", "light")
    report = async_mock_service(hass, "test", "report")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "training_session",
        {
            **SESSION,
            "calibration_delay": {"seconds": 5},
            "session_started": [{"action": "test.light"}],
            "session_ended": [
                {
                    "action": "test.report",
                    "data": {
                        "reason": "{{ reason }}",
                        "darts": "{{ darts }}",
                        "average": "{{ average }}",
                        "minutes": "{{ duration_minutes }}",
                    },
                }
            ],
        },
    )
    fire(hass, "session_started", started="2026-09-26T18:00:00+00:00", reason="manual")
    # The cameras get time to open before the calibration.
    await until_waiting(hass, 5)
    assert len(light) == 1
    assert turn_on[0].data["entity_id"] == ["switch.autodarts_board_detection"]
    assert not press
    await pass_time(hass, freezer, 5)
    assert press[0].data["entity_id"] == ["button.autodarts_board_calibrate"]

    fire(
        hass,
        "session_ended",
        reason="idle",
        darts=30,
        average=48.5,
        duration_minutes=20.0,
    )
    await hass.async_block_till_done()
    assert turn_off[0].data["entity_id"] == ["switch.autodarts_board_detection"]
    assert report[0].data == {
        "reason": "idle",
        "darts": 30,
        "average": 48.5,
        "minutes": 20.0,
    }


async def test_training_session_without_board_controls_only_runs_actions(hass):
    turn_on = async_mock_service(hass, "switch", "turn_on")
    press = async_mock_service(hass, "button", "press")
    light = async_mock_service(hass, "test", "light")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "training_session",
        {"board_events": EVENTS, "session_started": [{"action": "test.light"}]},
    )
    fire(hass, "session_started", started="2026-09-26T18:00:00+00:00")
    await hass.async_block_till_done()
    fire(hass, "session_ended", reason="manual", darts=0)
    await hass.async_block_till_done()
    assert len(light) == 1
    assert not turn_on and not press


async def test_training_session_started_by_a_dart_skips_the_calibration(hass):
    turn_on = async_mock_service(hass, "switch", "turn_on")
    press = async_mock_service(hass, "button", "press")
    hass.states.async_set(EVENTS, "unknown")
    # Saved before the wait became a duration: plain seconds keep working.
    await automate(hass, "training_session", {**SESSION, "calibration_delay": 0})
    fire(
        hass,
        "session_started",
        started="2026-09-26T18:00:00+00:00",
        reason="first_dart",
    )
    await hass.async_block_till_done()
    assert turn_on[0].data["entity_id"] == ["switch.autodarts_board_detection"]
    # The dart that started the session is still in the board.
    assert not press


async def test_training_session_keeps_the_board_for_a_new_session(hass):
    turn_on = async_mock_service(hass, "switch", "turn_on")
    turn_off = async_mock_service(hass, "switch", "turn_off")
    light = async_mock_service(hass, "test", "light")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "training_session",
        {
            **SESSION,
            "calibration": [],
            "session_started": [{"action": "test.light"}],
            "session_ended": [{"action": "test.light"}],
        },
    )
    fire(hass, "session_ended", reason="new_session", darts=12)
    fire(hass, "session_started", reason="new_session")
    await hass.async_block_till_done()
    assert not turn_on and not turn_off and not light


async def test_training_session_routine_for_a_new_session_on_request(hass):
    turn_on = async_mock_service(hass, "switch", "turn_on")
    turn_off = async_mock_service(hass, "switch", "turn_off")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "training_session",
        {**SESSION, "calibration": [], "run_for_new_session": True},
    )
    fire(hass, "session_ended", reason="new_session", darts=12)
    await hass.async_block_till_done()
    fire(hass, "session_started", reason="new_session")
    await hass.async_block_till_done()
    assert len(turn_off) == 1 and len(turn_on) == 1


async def test_training_session_prepares_the_board_despite_a_failing_action(hass):
    turn_on = async_mock_service(hass, "switch", "turn_on")
    async_mock_service(
        hass, "test", "light", raise_exception=HomeAssistantError("light offline")
    )
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "training_session",
        {
            **SESSION,
            "calibration": [],
            "session_started": [{"action": "test.light"}],
        },
    )
    fire(hass, "session_started", reason="manual")
    await hass.async_block_till_done()
    assert turn_on[0].data["entity_id"] == ["switch.autodarts_board_detection"]


# -- highlight photo ---------------------------------------------------------------------


async def test_highlight_photo_for_a_180_and_a_checkout(hass, freezer):
    photos = async_mock_service(hass, "test", "photo")
    snapshots = saves(hass)
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "highlight_photo", PHOTO)
    fire(hass, "visit_thrown", score=140, darts=3)
    fire(hass, "visit_thrown", score=180, darts=3, name="Alex/Bee_2")
    # The photo waits a moment for a leg won by the same dart.
    await photo_taken(hass, freezer)
    assert [call.data for call in photos] == [
        {
            "image": "/api/camera_proxy/camera.autodarts_board_camera_1",
            "message": "180!",
        }
    ]
    fire(hass, "leg_won", game=501, players=2, player=2, name="Sam", checkout=121)
    await photo_taken(hass, freezer)
    assert photos[-1].data["message"] == "Checkout 121 by Sam!"
    # A Cricket leg has no checkout to show.
    fire(hass, "leg_won", game="cricket", players=2, player=1, name="Lea", mpr=2.4)
    await hass.async_block_till_done()
    assert len(photos) == 2
    # The bot's darts are not in the board.
    fire(hass, "visit_thrown", score=180, darts=3, name=None, bot=True)
    fire(hass, "leg_won", game=501, players=2, player=2, checkout=121, bot=True)
    await hass.async_block_till_done()
    assert len(photos) == 2
    # Characters a file name cannot have, and the separator, leave the player's name.
    assert [photo_name(call) for call in snapshots] == [
        "Alex Bee 2_180.jpg",
        "Sam_checkout-121.jpg",
    ]


async def test_highlight_photo_of_a_checkout_by_the_third_dart(hass, freezer):
    """The visit and the leg arrive together; the leg gets one photo."""
    photos = async_mock_service(hass, "test", "photo")
    snapshots = saves(hass)
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "highlight_photo", {**PHOTO, "minimum_score": 100})
    fire(hass, "visit_thrown", score=170, darts=3)
    fire(hass, "leg_won", game=501, players=1, player=1, name=None, checkout=170)
    await photo_taken(hass, freezer)
    assert [call.data["message"] for call in photos] == ["Checkout 170!"]
    assert [photo_name(call) for call in snapshots] == ["checkout-170.jpg"]


async def test_highlight_photo_can_skip_checkouts_and_lower_the_score(hass, freezer):
    photos = async_mock_service(hass, "test", "photo")
    saves(hass)
    hass.states.async_set(EVENTS, "unknown")
    # Saved before the visit came from the board events: the old input is ignored.
    await automate(
        hass,
        "highlight_photo",
        {
            **PHOTO,
            "visit_score": "sensor.autodarts_board_detected_visit_score",
            "minimum_score": 140,
            "checkouts": False,
        },
    )
    fire(hass, "visit_thrown", score=140, darts=3)
    await photo_taken(hass, freezer)
    fire(hass, "leg_won", game=501, players=1, player=1, name=None, checkout=40)
    await hass.async_block_till_done()
    assert [call.data["message"] for call in photos] == ["140!"]


async def test_highlight_photo_gallery_folder_and_saving_can_change(hass, freezer):
    photos = async_mock_service(hass, "test", "photo")
    snapshots = saves(hass)
    hass.states.async_set(EVENTS, "unknown")
    await automate_all(
        hass,
        [
            (
                "highlight_photo",
                {
                    **PHOTO,
                    "gallery_folder": " /config/media/darts/ ",
                    "checkouts": False,
                },
            ),
            # Only the gallery, without actions of its own.
            (
                "highlight_photo",
                {
                    "board_events": EVENTS,
                    "camera": "camera.autodarts_board_camera_2",
                    "minimum_score": 100,
                },
            ),
            ("highlight_photo", {**PHOTO, "save_photo": False, "minimum_score": 120}),
        ],
    )
    fire(hass, "visit_thrown", score=180, darts=3, name="Lea")
    await photo_taken(hass, freezer)
    # Without a folder of its own, the photo goes to the gallery, wherever the
    # media folder is.
    assert sorted(
        (call.data["folder"], call.data["camera"], call.data["player"])
        for call in snapshots
    ) == [
        ("", "camera.autodarts_board_camera_2", "Lea"),
        ("/config/media/darts/", "camera.autodarts_board_camera_1", "Lea"),
    ]
    assert len(photos) == 2


# The clip as the actions get it.
CLIPPED = {
    **PHOTO,
    "clip_camera": "camera.room",
    "photo_actions": [
        {
            "action": "test.photo",
            "data": {"clip": "{{ clip }}", "clip_url": "{{ clip_url }}"},
        }
    ],
}


async def test_highlight_photo_records_a_clip_beside_the_photo(hass, freezer):
    """A camera with a video stream records the moment as an MP4 beside the
    photo, where the gallery plays it; homedarts.save_highlight records it in
    the background and answers with its file and address at once."""
    photos = async_mock_service(hass, "test", "photo")
    saved = []
    clip = "/media/homedarts/highlights/2026-09-26_21-05-33_180.mp4"
    url = "/media/local/homedarts/highlights/2026-09-26_21-05-33_180.mp4"

    async def save(call):
        saved.append(call)
        answer = {
            "photo": clip.removesuffix(".mp4") + ".jpg",
            "photo_url": url.removesuffix(".mp4") + ".jpg",
        }
        return (
            {**answer, "clip": clip, "clip_url": url}
            if "clip_camera" in call.data
            else answer
        )

    hass.services.async_register(
        "homedarts", "save_highlight", save, supports_response=SupportsResponse.OPTIONAL
    )
    hass.states.async_set(EVENTS, "unknown")
    await automate_all(
        hass,
        [
            ("highlight_photo", CLIPPED),
            (
                "highlight_photo",
                {
                    **CLIPPED,
                    "clip_camera": "camera.stream",
                    "clip_lookback": 2,
                    "clip_duration": 20,
                },
            ),
            # Without a clip camera, or without a saved photo, there is no clip,
            # and the action gets no clip fields, which older versions lack.
            ("highlight_photo", {**CLIPPED, "clip_camera": ""}),
            ("highlight_photo", {**CLIPPED, "save_photo": False}),
        ],
    )
    fire(hass, "visit_thrown", score=180, darts=3, name="Alex")
    await photo_taken(hass, freezer)
    assert sorted(
        (
            call.data.get("clip_camera", ""),
            call.data.get("clip_lookback"),
            call.data.get("clip_duration"),
        )
        for call in saved
    ) == [("", None, None), ("camera.room", 5, 8), ("camera.stream", 2, 20)]
    assert all(call.data["camera"] == PHOTO["camera"] for call in saved)
    assert sorted((call.data["clip"], call.data["clip_url"]) for call in photos) == [
        ("", ""),
        ("", ""),
        (clip, url),
        (clip, url),
    ]


@pytest.mark.parametrize(
    "layout",
    # /media on Home Assistant OS and in a container, /config/media elsewhere.
    ["home_assistant_os", "core"],
)
async def test_highlight_photo_hands_the_saved_file_to_the_actions(
    hass, aioclient_mock, freezer, tmp_path, tmp_path_factory, layout
):
    """The app loads the saved photo instead of the camera seconds later."""
    # tmp_path is the configuration folder (blueprint_folder), so the media
    # folder of Core is inside it, the one of Home Assistant OS outside.
    assert hass.config.config_dir == str(tmp_path)
    media = (
        tmp_path_factory.mktemp("media")
        if layout == "home_assistant_os"
        else tmp_path / "media"
    )
    share = tmp_path_factory.mktemp("share")
    hass.config.media_dirs = {"local": str(media)}
    hass.config.allowlist_external_dirs = {str(media), str(share)}
    photos = async_mock_service(hass, "test", "photo")
    cameras = await setup_cameras(hass, aioclient_mock, 0, 1, 2)
    for index in range(3):
        camera_picture(aioclient_mock, index)
    await automate_all(
        hass,
        [
            ("highlight_photo", {**SAVED, "camera": cameras[0]}),
            (
                "highlight_photo",
                {**SAVED, "camera": cameras[1], "gallery_folder": f"{media}/darts"},
            ),
            (
                "highlight_photo",
                {**SAVED, "camera": cameras[2], "gallery_folder": f"{share}/darts"},
            ),
            (
                "highlight_photo",
                {
                    **SAVED,
                    "camera": "camera.autodarts_board_camera_4",
                    "save_photo": False,
                },
            ),
        ],
    )
    fire(hass, "visit_thrown", score=180, darts=3, name="Alex Bee")
    await photo_taken(hass, freezer)
    sent = {call.data["image"][-1]: call.data for call in photos}
    file = Path(sent["1"]["photo"]).name
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_Alex Bee_180\.jpg", file)
    assert [
        (sent[camera]["photo"], sent[camera]["photo_url"]) for camera in "1234"
    ] == [
        (
            str(media.resolve() / "homedarts" / "highlights" / file),
            f"/media/local/homedarts/highlights/{quote(file)}",
        ),
        (str(media.resolve() / "darts" / file), f"/media/local/darts/{quote(file)}"),
        # Outside the media folder, Home Assistant has no address for the file.
        (str(share.resolve() / "darts" / file), ""),
        # Nothing saved, nothing to load: the actions fall back to `image`.
        ("", ""),
    ]
    # Every photo the actions get is on disk.
    assert [
        await hass.async_add_executor_job(Path(sent[camera]["photo"]).read_bytes)
        for camera in "123"
    ] == [JPEG] * 3


async def test_a_photo_that_was_not_saved_gets_no_file_and_no_address(
    hass, aioclient_mock, freezer, tmp_path, caplog
):
    """A disabled, an unavailable and a failing camera save nothing: the actions
    still run, with the live picture instead of a file that was never written."""
    media = tmp_path / "media"
    hass.config.media_dirs = {"local": str(media)}
    hass.config.allowlist_external_dirs = {str(media)}
    photos = async_mock_service(hass, "test", "photo")
    failing, unplugged, disabled = await setup_cameras(hass, aioclient_mock, 0, 1)
    aioclient_mock.get(f"{BASE}/api/img/cams/0", status=500, text="error")
    # The board has one camera less: its entity stays, unavailable.
    coordinator = hass.config_entries.async_entries("homedarts")[0].runtime_data.local
    with patch.object(
        coordinator.client, "get_config", return_value={"camera_count": 1}
    ):
        # The settings of Board Manager 1 are read again after 30 seconds.
        freezer.tick(timedelta(seconds=30))
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(unplugged).state == "unavailable"
    assert entity_id(hass, "event", "board_events") == EVENTS
    await automate_all(
        hass,
        [
            ("highlight_photo", {**SAVED, "camera": camera})
            for camera in (failing, unplugged, disabled)
        ],
    )
    fire(hass, "visit_thrown", score=180, darts=3, name="Alex")
    await photo_taken(hass, freezer)
    assert sorted(call.data["image"] for call in photos) == [
        f"/api/camera_proxy/{camera}" for camera in (failing, unplugged, disabled)
    ]
    assert {(call.data["photo"], call.data["photo_url"]) for call in photos} == {
        ("", "")
    }
    assert not (media / "homedarts").exists()
    # The log says why each photo is missing.
    for camera, reason in (
        (failing, "gave no picture"),
        (unplugged, "is unavailable"),
        (disabled, "does not exist or is disabled"),
    ):
        assert f"The camera {camera} {reason}" in caplog.text


async def test_names_never_become_templates(hass, freezer, caplog):
    """A name is text, also in the fields Home Assistant renders once more."""
    hass.states.async_set("sensor.secret", "s3cr3t")
    messages = []

    async def notify(call) -> None:
        messages.append(call.data["message"].async_render(parse_result=False))

    # Like the notify services, which take templates.
    snapshots = saves(hass)
    hass.services.async_register(
        "test",
        "notify",
        notify,
        schema=vol.Schema({vol.Required("message"): cv.template}),
    )
    speak = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    tell = [{"action": "test.notify", "data": {"message": "{{ message }}"}}]
    await automate_all(
        hass,
        [
            ("highlight_photo", {**PHOTO, "photo_actions": tell}),
            (
                "light_show",
                {
                    "board_events": EVENTS,
                    "leg_actions": [
                        {"action": "test.notify", "data": {"message": "{{ who }}"}}
                    ],
                },
            ),
            ("practice_caller", VOICE),
        ],
    )
    names = {
        "{{ 6*7 }}": "6*7",
        "Kim {% if": "Kim  if",
        "{{ states('sensor.secret') }}": "states('sensor.secret')",
        "{# note #}Lea": "note Lea",
    }
    for name in names:
        fire(hass, "leg_won", game=501, players=2, player=1, name=name, checkout=40)
        await photo_taken(hass, freezer)
    shown = list(names.values())
    assert [message for message in messages if not message.startswith("C")] == shown
    assert [message for message in messages if message.startswith("C")] == [
        f"Checkout 40 by {who}!" for who in shown
    ]
    assert spoken(speak) == [f"Game shot, and the leg, {who}!" for who in shown]
    # The photo gets the name as text, part of its file name.
    assert [call.data["player"] for call in snapshots] == shown
    assert [photo_name(call) for call in snapshots] == [
        "6 7_checkout-40.jpg",
        "Kim if_checkout-40.jpg",
        "states('sensor.secre_checkout-40.jpg",
        "note Lea_checkout-40.jpg",
    ]
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


# -- light show ------------------------------------------------------------------------


def moment_actions(action: str = "test.light") -> dict:
    return {
        f"{moment}_actions": [
            {
                "action": action,
                "data": {
                    "moment": "{{ moment }}",
                    "who": "{{ who }}",
                    "score": "{{ score }}",
                    "checkout": "{{ checkout }}",
                },
            }
        ]
        for moment in (*MOMENTS, "takeout", "board_clear")
    }


async def test_light_show_moments(hass):
    light = async_mock_service(hass, "test", "light")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "light_show",
        {
            "board_events": EVENTS,
            **moment_actions(),
            "high_finish_minimum": 100,
            "takeout_moments": True,
        },
    )
    x01 = {"game": 501, "players": 2}
    await fire_all(
        hass,
        [
            ("visit_thrown", {"score": 140, "darts": 3}),
            ("visit_thrown", {"score": 180, "darts": 3}),
            ("visit_completed", {"score": 180, "darts": 3, "thrown": True}),
            # An older integration announces the 180 when the darts are pulled.
            ("visit_completed", {"score": 180, "darts": 3}),
            ("takeout_started", {}),
            ("takeout_finished", {}),
            ("bust", {**x01, "player": 1, "name": "Dennis", "remaining": 32}),
            ("leg_won", {**x01, "player": 2, "name": None, "checkout": 40}),
            ("leg_won", {**x01, "player": 1, "name": "Dennis", "checkout": 121}),
            # A Cricket leg is a won leg without a checkout.
            ("leg_won", {"game": "cricket", "players": 1, "player": 1, "name": None}),
            # The deciding leg leaves the stage to the match.
            ("leg_won", {**x01, "player": 2, "name": "Lea", "match": True}),
            ("match_won", {**x01, "player": 2, "name": "Lea"}),
            ("personal_best", {"record": "highest_visit", "value": 180}),
            ("daily_goal_reached", {"goal": 100, "darts": 100, "streak": 3}),
            ("bull_off_won", {**x01, "player": 2, "name": None, "distance": 4.1}),
            (
                "achievement_unlocked",
                {"player": 1, "name": "Dennis", "achievement": "maximum", "tier": 1},
            ),
            ("turn_changed", {**x01, "player": 2, "name": None}),
            # The tournament's winner after the final.
            ("tournament_match_finished", {"winner": "Lea", "loser": "Dennis"}),
            ("tournament_finished", {"winner": "Lea", "runner_up": "Dennis"}),
        ],
    )
    assert [
        (
            call.data["moment"],
            call.data["who"],
            call.data["score"],
            call.data["checkout"],
        )
        for call in light
    ] == [
        ("maximum", "", 180, 0),
        ("maximum", "", 180, 0),
        ("takeout", "", 0, 0),
        ("board_clear", "", 0, 0),
        ("bust", "Dennis", 0, 0),
        ("leg", "Player 2", 0, 40),
        ("high_finish", "Dennis", 0, 121),
        ("leg", "", 0, 0),
        ("match", "Lea", 0, 0),
        ("personal_best", "", 0, 0),
        ("daily_goal", "", 0, 0),
        ("bull_off", "Player 2", 0, 0),
        ("achievement", "Dennis", 0, 0),
        ("tournament", "Lea", 0, 0),
    ]


async def test_light_show_sets_the_scene_when_a_game_starts(hass):
    light = async_mock_service(hass, "test", "light")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "light_show",
        {
            "board_events": EVENTS,
            "game_start_actions": [
                {
                    "action": "test.light",
                    "data": {"moment": "{{ moment }}", "who": "{{ who }}"},
                }
            ],
        },
    )
    started = {"game": 501, "mode": "match", "players": 2, "names": ["Alex", None]}
    await fire_all(
        hass,
        [
            # A game with the bot is no moment of the bot.
            ("game_started", {**started, "bot_player": 2, "bot_level": 60}),
            ("game_ended", {**started, "reason": "stopped"}),
            ("game_started", {**started, "resumed": True}),
        ],
    )
    assert [call.data for call in light] == [{"moment": "game_start", "who": ""}] * 2


async def test_light_show_restores_the_lights_and_pauses_the_detection(hass, freezer):
    light = async_mock_service(hass, "test", "light")
    snapshot = async_mock_service(hass, "scene", "create")
    restore = async_mock_service(hass, "scene", "turn_on")
    turn_off = async_mock_service(hass, "switch", "turn_off")
    turn_on = async_mock_service(hass, "switch", "turn_on")
    detection = "switch.autodarts_board_detection"
    hass.states.async_set(EVENTS, "unknown")
    hass.states.async_set(detection, "on")
    await automate(
        hass,
        "light_show",
        {
            "board_events": EVENTS,
            **moment_actions(),
            "effect_moments": ["maximum", "bust"],
            "restore_lights": ["light.wled", "light.dartroom"],
            "effect_duration": {"seconds": 8},
            "pause_detection": True,
            "detection": detection,
            "takeout_moments": True,
        },
    )
    fire(hass, "visit_thrown", score=180, darts=3)
    await until_waiting(hass, 8)
    automation = hass.states.async_all("automation")[0].entity_id
    scene = automation.replace("automation.", "homedarts_light_show_")
    assert [call.data for call in snapshot] == [
        {"scene_id": scene, "snapshot_entities": ["light.wled", "light.dartroom"]}
    ]
    assert [call.data["entity_id"] for call in turn_off] == [[detection]]
    assert len(light) == 1 and not restore and not turn_on
    hass.states.async_set(detection, "off")
    await pass_time(hass, freezer, 8)
    assert [call.data["entity_id"] for call in restore] == [[f"scene.{scene}"]]
    assert [call.data["entity_id"] for call in turn_on] == [[detection]]

    # Takeout and board clear set a look of their own, at once, and so does
    # a moment without an effect.
    fire(hass, "takeout_started")
    await hass.async_block_till_done()
    fire(hass, "leg_won", game=501, players=1, player=1, name=None, checkout=40)
    await hass.async_block_till_done()
    assert len(light) == 3 and len(snapshot) == 1 and len(turn_off) == 1

    # A detection that was off stays off.
    fire(hass, "bust", game=501, players=1, player=1, name=None, remaining=40)
    await until_waiting(hass, 8)
    await pass_time(hass, freezer, 8)
    assert len(snapshot) == 2 and len(restore) == 2
    assert len(turn_off) == 1 and len(turn_on) == 1


async def test_light_show_restores_the_lights_after_a_failing_effect(hass, freezer):
    async_mock_service(
        hass, "test", "light", raise_exception=HomeAssistantError("WLED offline")
    )
    async_mock_service(hass, "scene", "create")
    restore = async_mock_service(hass, "scene", "turn_on")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "light_show",
        {
            "board_events": EVENTS,
            **moment_actions(),
            "effect_moments": ["match"],
            "restore_lights": ["light.wled"],
            "effect_duration": {"seconds": 5},
        },
    )
    fire(hass, "match_won", game=501, players=2, player=1, name="Lea")
    await until_waiting(hass, 5)
    await pass_time(hass, freezer, 5)
    assert len(restore) == 1


async def test_light_show_without_restore_plays_moments_at_once(hass):
    light = async_mock_service(hass, "test", "light")
    snapshot = async_mock_service(hass, "scene", "create")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "light_show",
        {"board_events": EVENTS, "maximum_actions": [{"action": "test.light"}]},
    )
    # Moments without actions stay dark.
    await fire_all(
        hass,
        [
            ("bust", {"game": 501, "players": 1, "player": 1, "remaining": 40}),
            ("visit_thrown", {"score": 180, "darts": 3}),
            ("visit_thrown", {"score": 180, "darts": 3}),
        ],
    )
    assert len(light) == 2 and not snapshot


async def test_light_show_reacts_to_online_matches_when_asked(hass):
    light = async_mock_service(hass, "test", "light")
    online = async_mock_service(hass, "test", "online")
    hass.states.async_set(EVENTS, "unknown")
    await automate_all(
        hass,
        [
            ("light_show", {"board_events": EVENTS, **moment_actions()}),
            (
                "light_show",
                {
                    "board_events": EVENTS,
                    **moment_actions("test.online"),
                    "online_matches": True,
                },
            ),
        ],
    )
    await fire_all(
        hass,
        [
            ("online_busted", {"trigger": "busted", "source": "online"}),
            (
                "online_game_shot",
                {"trigger": "gameshot+d10", "segment": "D10", "source": "online"},
            ),
            (
                "online_match_shot",
                {"trigger": "matchshot_dennis", "name": "dennis", "source": "online"},
            ),
            # Your own 180 comes from the board, and only once.
            ("online_visit", {"trigger": "180", "score": 180, "source": "online"}),
        ],
    )
    # Off by default: an online match stays dark.
    assert not light
    assert [(call.data["moment"], call.data["who"]) for call in online] == [
        ("bust", ""),
        ("leg", ""),
        ("match", "dennis"),
    ]


async def test_light_show_keeps_the_moments_that_wait_for_an_effect(hass, freezer):
    """The final of a tournament brings personal bests and achievements while
    its effect plays; the takeouts of the next visits never take their place."""
    light = async_mock_service(hass, "test", "light")
    async_mock_service(hass, "scene", "create")
    restore = async_mock_service(hass, "scene", "turn_on")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "light_show",
        {
            "board_events": EVENTS,
            **moment_actions(),
            "effect_moments": ["match"],
            "restore_lights": ["light.wled"],
            "effect_duration": {"seconds": 10},
        },
    )
    fire(hass, "match_won", game=501, players=2, player=1, name="Lea")
    await until_waiting(hass, 10)
    lea = {"player": 1, "name": "Lea", "tier": 1}
    for kind, attributes in [
        ("takeout_started", {}),
        ("personal_best", {"record": "highest_checkout", "value": 121}),
        ("personal_best", {"record": "fewest_darts_501", "value": 15}),
        ("takeout_finished", {}),
        *[
            ("achievement_unlocked", {**lea, "achievement": achievement})
            for achievement in ("match", "leg", "high_finish", "short_leg")
        ],
        *[
            (kind, {})
            for _ in range(5)
            for kind in ("takeout_started", "takeout_finished")
        ],
        ("tournament_finished", {"winner": "Lea", "runner_up": "Kim"}),
    ]:
        fire(hass, kind, **attributes)
        await settle(hass)
    await pass_time(hass, freezer, 10)
    assert [call.data["moment"] for call in light] == [
        "match",
        "personal_best",
        "personal_best",
        *["achievement"] * 4,
        "tournament",
    ]
    assert len(restore) == 1


async def test_light_show_never_pauses_the_detection_in_the_middle_of_a_visit(
    hass, freezer
):
    light = async_mock_service(hass, "test", "light")
    snapshot = async_mock_service(hass, "scene", "create")
    restore = async_mock_service(hass, "scene", "turn_on")
    turn_off = async_mock_service(hass, "switch", "turn_off")
    detection = "switch.autodarts_board_detection"
    hass.states.async_set(EVENTS, "unknown")
    hass.states.async_set(detection, "on")
    await automate(
        hass,
        "light_show",
        {
            "board_events": EVENTS,
            **moment_actions(),
            "effect_moments": ["daily_goal", "maximum"],
            "restore_lights": ["light.wled"],
            "effect_duration": {"seconds": 5},
            "pause_detection": True,
            "detection": detection,
        },
    )
    # The dart that reaches the daily goal may be the first of a visit: the
    # effect plays, and the detection keeps counting the visit.
    fire(hass, "daily_goal_reached", goal=100, darts=100, streak=1)
    await until_waiting(hass, 5)
    assert len(light) == len(snapshot) == 1 and not turn_off
    await pass_time(hass, freezer, 5)
    assert len(restore) == 1
    # The third dart of a 180 ends its visit: the detection pauses.
    fire(hass, "visit_thrown", score=180, darts=3)
    await until_waiting(hass, 5)
    assert [call.data["entity_id"] for call in turn_off] == [[detection]]
    await pass_time(hass, freezer, 5)
    assert len(light) == len(restore) == 2


def stopping_board(hass, light_show: dict) -> list[tuple[str, dict]]:
    """The light show pausing the detection next to the training session
    routine, which stops it when a session ends."""
    detection = SESSION["detection"]
    hass.states.async_set(EVENTS, "unknown")
    hass.states.async_set(detection, "on")
    return [
        ("training_session", {**SESSION, "calibration": []}),
        (
            "light_show",
            {
                "board_events": EVENTS,
                **moment_actions(),
                "restore_lights": ["light.wled"],
                "effect_duration": {"seconds": 10},
                "pause_detection": True,
                "detection": detection,
                **light_show,
            },
        ),
    ]


async def test_light_show_keeps_the_board_stopped_after_a_session(hass, freezer):
    """A new best session average comes right after the end of its session,
    while the switch still shows the detection running."""
    light = async_mock_service(hass, "test", "light")
    async_mock_service(hass, "scene", "create")
    restore = async_mock_service(hass, "scene", "turn_on")
    turn_off = async_mock_service(hass, "switch", "turn_off")
    turn_on = async_mock_service(hass, "switch", "turn_on")
    await automate_all(
        hass, stopping_board(hass, {"effect_moments": ["personal_best", "match"]})
    )
    session = {"reason": "manual", "darts": 60, "average": 52.4, "duration_minutes": 9}
    fire(hass, "session_ended", **session)
    fire(hass, "personal_best", record="best_session_average", value=52.4)
    await until_waiting(hass, 10)
    # The board stops the detection after the routine asked it to.
    hass.states.async_set(SESSION["detection"], "off")
    await pass_time(hass, freezer, 10)
    assert [call.data["moment"] for call in light] == ["personal_best"]
    assert len(restore) == 1
    assert [call.data["entity_id"] for call in turn_off] == [[SESSION["detection"]]]
    assert not turn_on


async def test_light_show_ends_its_effect_with_the_session(hass, freezer):
    """A session that ends while an effect plays has stopped the board: the
    lights come back at once, and the detection stays off."""
    async_mock_service(hass, "test", "light")
    async_mock_service(hass, "scene", "create")
    restore = async_mock_service(hass, "scene", "turn_on")
    turn_off = async_mock_service(hass, "switch", "turn_off")
    turn_on = async_mock_service(hass, "switch", "turn_on")
    await automate_all(hass, stopping_board(hass, {"effect_moments": ["match"]}))
    fire(hass, "match_won", game=501, players=2, player=1, name="Lea")
    await until_waiting(hass, 10)
    hass.states.async_set(SESSION["detection"], "off")
    freezer.tick(timedelta(seconds=3))
    fire(hass, "session_ended", reason="manual", darts=30, average=40.1)
    await settle(hass)
    assert len(restore) == 1
    await pass_time(hass, freezer, 10)
    assert len(turn_off) == 2 and len(restore) == 1
    assert not turn_on


async def test_light_show_plays_on_into_a_new_session(hass, freezer):
    """A new session keeps the board running: the effect plays to its end, and
    the detection starts again."""
    async_mock_service(hass, "test", "light")
    async_mock_service(hass, "scene", "create")
    restore = async_mock_service(hass, "scene", "turn_on")
    turn_on = async_mock_service(hass, "switch", "turn_on")
    async_mock_service(hass, "switch", "turn_off")
    await automate_all(hass, stopping_board(hass, {"effect_moments": ["match"]}))
    fire(hass, "match_won", game=501, players=2, player=1, name="Lea")
    await until_waiting(hass, 10)
    hass.states.async_set(SESSION["detection"], "off")
    freezer.tick(timedelta(seconds=4))
    async_fire_time_changed(hass)
    fire(hass, "session_ended", reason="new_session", darts=30, average=40.1)
    fire(hass, "session_started", reason="new_session")
    await until_waiting(hass, 6)
    assert not restore and not turn_on
    await pass_time(hass, freezer, 6)
    assert len(restore) == 1
    assert [call.data["entity_id"] for call in turn_on] == [[SESSION["detection"]]]


async def test_light_show_leaves_the_bot_out_unless_asked(hass):
    light = async_mock_service(hass, "test", "light")
    everyone = async_mock_service(hass, "test", "everyone")
    hass.states.async_set(EVENTS, "unknown")
    await automate_all(
        hass,
        [
            ("light_show", {"board_events": EVENTS, **moment_actions()}),
            (
                "light_show",
                {
                    "board_events": EVENTS,
                    **moment_actions("test.everyone"),
                    "include_bot": True,
                    "bot_label": "Robo",
                },
            ),
        ],
    )
    bot = {"game": 501, "players": 2, "player": 2, "name": None, "bot": True}
    # In a team match, the bot's partner at the board wins with it.
    team = {**bot, "players": 4, "player": 4, "team": 2, "team_name": None}
    await fire_all(
        hass,
        [
            ("bull_off_won", {**bot, "hit": "BULL", "distance": 3.0}),
            ("visit_thrown", {"score": 180, "darts": 3, **bot}),
            ("bust", {**bot, "remaining": 32}),
            ("leg_won", {**bot, "checkout": 40, "match": False}),
            ("match_won", bot),
            ("bust", {**team, "remaining": 32}),
            ("leg_won", {**team, "checkout": 121, "match": False}),
            ("match_won", team),
        ],
    )
    assert [(call.data["moment"], call.data["who"]) for call in light] == [
        ("high_finish", "Bot"),
        ("match", "Bot"),
    ]
    assert [(call.data["moment"], call.data["who"]) for call in everyone] == [
        ("bull_off", "Robo"),
        ("maximum", "Robo"),
        ("bust", "Robo"),
        ("leg", "Robo"),
        ("match", "Robo"),
        ("bust", "Robo"),
        ("high_finish", "Robo"),
        ("match", "Robo"),
    ]


async def test_light_show_names_unnamed_players_in_its_language(hass):
    light = async_mock_service(hass, "test", "light")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "light_show",
        {"board_events": EVENTS, **moment_actions(), "player_label": "Spieler"},
    )
    await fire_all(
        hass,
        [
            ("bust", {"game": 501, "players": 3, "player": 3, "name": None}),
            ("bust", {"game": 501, "players": 1, "player": 1, "name": None}),
        ],
    )
    assert [call.data["who"] for call in light] == ["Spieler 3", ""]


async def test_practice_caller_names_the_score_to_leave_without_a_checkout(hass):
    calls = async_mock_service(hass, "tts", "speak")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "practice_caller",
        {
            **VOICE,
            "setup_message": "{{ who ~ ', leave' if who else 'Leave' }} yourself {{ leave }}",
            "turn_message": "{{ who }}",
        },
    )
    match = {"game": 501, "players": 2, "player": 2, "name": "Sam", "checkout": None}
    await fire_all(
        hass,
        [
            (
                "turn_changed",
                {
                    **match,
                    "remaining": 169,
                    "setup": {"route": "T20 T20 S17", "leave": 32},
                },
            ),
            # Nothing to set up: the next player is called.
            ("turn_changed", {**match, "remaining": 301, "setup": None}),
            # A checkout wins over a setup.
            (
                "turn_changed",
                {**match, "remaining": 40, "checkout": "D20", "setup": None},
            ),
        ],
    )
    assert spoken(calls) == ["Sam, leave yourself 32", "Sam", "Sam, you require 40"]


# -- score display -----------------------------------------------------------------------

PRACTICE = "sensor.autodarts_board_practice_remaining_score"
AWTRIX = {
    "board_events": EVENTS,
    "practice_score": PRACTICE,
    "display_type": "awtrix",
    "topic_prefix": "awtrix_1a2b3c",
}
WHITE, GREEN, GOLD, RED = [255, 255, 255], [0, 200, 80], [255, 190, 0], [255, 0, 0]
# The default flash duration and idle time, in seconds.
FLASH, IDLE = 5, 300
PIXELIT_CLOCK = {"clock": {"show": True, "switchAktiv": False, "withSeconds": False}}


def practice_state(hass, remaining: int | None, **attributes) -> None:
    """The practice remaining score as the integration writes it: the score of
    the player at the board, and the game in the attributes."""
    hass.states.async_set(
        PRACTICE,
        "unknown" if remaining is None else str(remaining),
        {
            "game": 501,
            "player": 1,
            "players": 1,
            "name": None,
            "checkout": None,
            "setup": None,
            "won": False,
            "winner": None,
            "bot": None,
            **attributes,
        },
    )


def timers(hass) -> set:
    return {
        handle
        for handle in get_scheduled_timer_handles(hass.loop)
        if not handle.cancelled()
    }


@asynccontextmanager
async def waits(hass, seconds: float) -> AsyncIterator[None]:
    """Run what starts the display's next run, and let it show its screen and
    reach its wait of the given length. A run that a new one replaces leaves
    its wait behind, so only a new wait counts."""
    before = timers(hass)
    yield
    for _ in range(200):
        due = [handle.when() - hass.loop.time() for handle in timers(hass) - before]
        if any(seconds - 0.5 < left <= seconds for left in due):
            return
        await asyncio.sleep(0)
    raise AssertionError(f"no new delay of {seconds} s started")


async def tick(hass, freezer, seconds: float) -> None:
    """Let time pass, without waiting for a run that waits on."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await settle(hass)


def awtrix_screens(calls, prefix: str = "awtrix_1a2b3c") -> list:
    """What the AWTRIX shows, notification by notification: text and color,
    None for the dismissal that brings its clock back."""
    screens: list[tuple[str, list[int]] | None] = []
    for call in calls:
        if call.data["topic"] == f"{prefix}/notify/dismiss":
            assert call.data["payload"] == ""
            screens.append(None)
            continue
        assert call.data["topic"] == f"{prefix}/notify"
        notice = json.loads(call.data["payload"])
        # Held until the next notification replaces it.
        assert (notice.pop("hold"), notice.pop("stack")) == (True, False)
        notice.pop("icon", None)
        screens.append((notice.pop("text"), notice.pop("color")))
        assert not notice, notice
    return screens


def pixelit_screen(text: str, color: list[int]) -> dict:
    return {
        "text": {
            "textString": text,
            "bigFont": False,
            "scrollText": "auto",
            "scrollTextDelay": 50,
            "centerText": True,
            "position": {"x": 0, "y": 1},
            "color": dict(zip("rgb", color, strict=True)),
        }
    }


def picture_script():
    spec = importlib.util.spec_from_file_location(
        "render_score_display", ROOT / "scripts" / "render_score_display.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_picture_of_the_display_shows_the_colors_of_the_blueprint():
    """scripts/render_score_display.py draws the picture of the guide, in the
    default colors of the blueprint, and nothing that would scroll."""
    picture = picture_script()
    inputs = models.Blueprint(
        load_yaml(BLUEPRINTS / "score_display.yaml"),
        expected_domain="automation",
        schema=BLUEPRINT_SCHEMA,
    ).inputs
    for _, setting, color in picture.SCREENS:
        assert inputs[setting]["default"] == list(color), setting
    assert picture.PICTURE.read_text(encoding="utf-8") == picture.render()
    with pytest.raises(ValueError, match="would scroll"):
        picture.lit("1000000000")


async def test_score_display_shows_the_score_after_every_dart(hass, freezer):
    publish = async_mock_service(hass, "mqtt", "publish")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "score_display", {**AWTRIX, "icon": " 1234 "})
    for remaining, route in ((501, None), (441, None), (81, "T15 D18")):
        async with waits(hass, IDLE):
            practice_state(hass, remaining, checkout=route)
    # A checkout is possible: the score with its route, in another color.
    assert awtrix_screens(publish) == [
        ("501", WHITE),
        ("441", WHITE),
        ("81 T15 D18", GREEN),
    ]
    assert {json.loads(call.data["payload"])["icon"] for call in publish} == {"1234"}
    # Without a dart for the idle time, the clock comes back.
    await tick(hass, freezer, IDLE - 1)
    assert len(publish) == 3
    await pass_time(hass, freezer, 1)
    assert awtrix_screens(publish)[3:] == [None]


async def test_score_display_in_every_game(hass, freezer):
    publish = async_mock_service(hass, "mqtt", "publish")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "score_display", {**AWTRIX, "topic_prefix": " "})
    # Without a game, the display belongs to its own apps, also when the
    # sensor appears after a restart or changes.
    practice_state(hass, None, game=None)
    await hass.async_block_till_done()
    practice_state(hass, None, game=None, legs_to_win=2)
    await hass.async_block_till_done()
    assert not publish
    # Cricket and the party games show the points of the player at the board.
    async with waits(hass, IDLE):
        practice_state(hass, None, game="cricket", points=45, target="T19")
    async with waits(hass, IDLE):
        practice_state(hass, None, game="shanghai", points=12, target="7")
    # A training game, or no game at all, brings the clock back at once.
    practice_state(hass, None, game=None)
    await hass.async_block_till_done()
    practice_state(hass, None, game=None, legs_to_win=3)
    await hass.async_block_till_done()
    assert awtrix_screens(publish, prefix="awtrix") == [
        ("45", WHITE),
        ("12", WHITE),
        None,
    ]
    assert all("icon" not in call.data["payload"] for call in publish)


async def test_score_display_flashes_the_moments(hass, freezer):
    publish = async_mock_service(hass, "mqtt", "publish")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "score_display", AWTRIX)
    match = {"game": 501, "players": 2, "player": 1, "name": "Dennis"}
    async with waits(hass, IDLE):
        practice_state(hass, 321, players=2, name="Dennis")
    # A 180 flashes with its third dart, and the score comes back after it.
    async with waits(hass, FLASH):
        fire(hass, "visit_thrown", score=180, darts=3, game=501, name="Dennis")
    async with waits(hass, IDLE):
        await tick(hass, freezer, FLASH)
    # Its darts pulled, a shorter visit and a visit below the minimum flash nothing.
    fire(hass, "visit_completed", score=180, darts=3, thrown=True, game=501)
    fire(hass, "visit_completed", score=100, darts=2, thrown=False, game=501)
    fire(hass, "visit_thrown", score=140, darts=3, game=501)
    await settle(hass)
    assert awtrix_screens(publish) == [
        ("321", WHITE),
        ("180!", GOLD),
        ("321", WHITE),
    ]

    async with waits(hass, FLASH):
        fire(hass, "bust", **match, remaining=40)
    async with waits(hass, IDLE):
        await tick(hass, freezer, FLASH)
    # The dart that wins the leg: the sensor first, then the board event.
    async with waits(hass, IDLE):
        practice_state(hass, 0, players=2, name="Dennis", won=True)
    async with waits(hass, FLASH):
        fire(hass, "leg_won", **match, checkout=40, match=False)
    async with waits(hass, IDLE):
        await tick(hass, freezer, FLASH)
    assert awtrix_screens(publish)[3:] == [
        ("BUST", RED),
        ("321", WHITE),
        ("GAME SHOT", GREEN),
    ]

    # The next leg; its deciding dart flashes the winner, not the leg.
    lea = {**match, "player": 2, "name": "Lea"}
    async with waits(hass, IDLE):
        practice_state(hass, 501, players=2, player=2, name="Lea")
    async with waits(hass, IDLE):
        practice_state(hass, 0, players=2, player=2, name="Lea", won=True, winner=2)
    fire(hass, "leg_won", **lea, checkout=501, match=True)
    await settle(hass)
    async with waits(hass, FLASH):
        fire(hass, "match_won", **lea)
    async with waits(hass, IDLE):
        await tick(hass, freezer, FLASH)
    assert awtrix_screens(publish)[6:] == [("501", WHITE), ("Lea WINS", GOLD)]
    # The winner stays until the idle time is over.
    await pass_time(hass, freezer, IDLE)
    assert awtrix_screens(publish)[8:] == [None]


@pytest.mark.parametrize(
    ("winner", "who"),
    [
        ({"player": 2, "name": None}, "Spieler 2"),
        ({"player": 2, "name": None, "bot": True}, "Computer"),
        (
            {"player": 1, "name": "Kim", "team": 1, "team_name": "Dennis & Kim"},
            "Dennis & Kim",
        ),
        ({"player": 1, "name": "{{ 6*7 }}"}, "6*7"),
    ],
)
async def test_score_display_names_the_winner(hass, freezer, winner, who):
    publish = async_mock_service(hass, "mqtt", "publish")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "score_display",
        {**AWTRIX, "player_label": "Spieler", "bot_label": "Computer"},
    )
    async with waits(hass, FLASH):
        fire(hass, "match_won", game=501, players=2, **winner)
    assert awtrix_screens(publish) == [(f"{who} WINS", GOLD)]


@pytest.mark.parametrize(
    ("transport", "settings"),
    [
        # The name of the REST command needs no domain.
        ("pixelit", {"pixelit_command": " pixelit_screen "}),
        ("pixelit_mqtt", {"topic_prefix": "dartroom/pixelit/"}),
    ],
)
async def test_score_display_on_a_pixelit(hass, freezer, transport, settings):
    publish = async_mock_service(hass, "mqtt", "publish")
    post = async_mock_service(hass, "rest_command", "pixelit_screen")
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "score_display",
        {
            "board_events": EVENTS,
            "practice_score": PRACTICE,
            "display_type": transport,
            "score_color": [255, 255, 0],
            **settings,
        },
    )
    async with waits(hass, IDLE):
        practice_state(hass, 40, checkout="D20")
    async with waits(hass, IDLE):
        practice_state(hass, 60)
    async with waits(hass, FLASH):
        fire(hass, "bust", game=501, players=1, player=1, name=None, remaining=60)
    async with waits(hass, IDLE):
        await tick(hass, freezer, FLASH)
    await pass_time(hass, freezer, IDLE)
    if transport == "pixelit":
        assert not publish
        screens = [call.data["screen"] for call in post]
    else:
        assert not post
        assert {call.data["topic"] for call in publish} == {
            "dartroom/pixelit/setScreen"
        }
        screens = [json.loads(call.data["payload"]) for call in publish]
    assert screens == [
        pixelit_screen("40 D20", GREEN),
        pixelit_screen("60", [255, 255, 0]),
        pixelit_screen("BUST", RED),
        pixelit_screen("60", [255, 255, 0]),
        PIXELIT_CLOCK,
    ]


async def test_score_display_keeps_going_when_the_display_is_away(hass, freezer):
    """A display that cannot be reached misses a screen, and gets the next."""
    post = async_mock_service(
        hass,
        "rest_command",
        "pixelit_screen",
        raise_exception=HomeAssistantError("PixelIt offline"),
    )
    hass.states.async_set(EVENTS, "unknown")
    await automate(
        hass,
        "score_display",
        {"board_events": EVENTS, "practice_score": PRACTICE, "display_type": "pixelit"},
    )
    async with waits(hass, IDLE):
        practice_state(hass, 501)
    await pass_time(hass, freezer, IDLE)
    assert [call.data["screen"] for call in post] == [
        pixelit_screen("501", WHITE),
        PIXELIT_CLOCK,
    ]


async def test_score_display_shows_the_game_again_after_a_restart(hass, freezer):
    """A restart, or saving the automation, forgets the wait for the clock:
    the display shows the game again and waits anew."""
    publish = async_mock_service(hass, "mqtt", "publish")
    hass.set_state(CoreState.not_running)
    hass.states.async_set(EVENTS, "unknown")
    practice_state(hass, 301)
    await saved(hass, "score_display", AWTRIX)
    async with waits(hass, IDLE):
        await hass.async_start()
    freezer.tick(timedelta(minutes=4))
    async with waits(hass, IDLE):
        await saved(hass, "score_display", AWTRIX, note="Saved again")
    await tick(hass, freezer, IDLE - 1)
    assert awtrix_screens(publish) == [("301", WHITE), ("301", WHITE)]
    await pass_time(hass, freezer, 1)
    assert awtrix_screens(publish)[2:] == [None]
    # Without a game, a restart or the save of another automation leaves the
    # display to its own apps and notifications.
    practice_state(hass, None, game=None)
    await hass.async_block_till_done()
    await reloaded(hass)
    await hass.async_block_till_done()
    assert awtrix_screens(publish)[2:] == [None, None]


async def test_score_display_ignores_the_save_of_another_automation(hass, freezer):
    """Home Assistant reloads every automation when any one is saved: that
    neither cuts the wait short nor puts an old game back on the display."""
    publish = async_mock_service(hass, "mqtt", "publish")
    hass.states.async_set(EVENTS, "unknown")
    await saved(hass, "score_display", AWTRIX)
    async with waits(hass, IDLE):
        practice_state(hass, 321)
    # A game that runs: nothing new, and the clock comes back on time.
    await tick(hass, freezer, 60)
    await reloaded(hass)
    assert awtrix_screens(publish) == [("321", WHITE)]
    await tick(hass, freezer, IDLE - 61)
    assert len(publish) == 1
    await pass_time(hass, freezer, 1)
    assert awtrix_screens(publish)[1:] == [None]
    # An old game whose clock came back long ago stays off the display.
    await tick(hass, freezer, 86400)
    await reloaded(hass)
    assert awtrix_screens(publish)[1:] == [None]


async def test_score_display_without_a_score_brings_the_clock_back_after_a_moment(
    hass, freezer
):
    """With an empty score, a moment flashes and the clock comes back after
    it, not after the idle time."""
    publish = async_mock_service(hass, "mqtt", "publish")
    hass.states.async_set(EVENTS, "unknown")
    await automate(hass, "score_display", {**AWTRIX, "score_message": ""})
    practice_state(hass, 321)
    await settle(hass)
    assert not publish
    async with waits(hass, FLASH):
        fire(hass, "visit_thrown", score=180, darts=3, game=501)
    await pass_time(hass, freezer, FLASH)
    assert awtrix_screens(publish) == [("180!", GOLD), None]


async def throw(hass, coordinator, *darts) -> None:
    """Throw dart by dart, without waiting for the runs that wait for the clock."""
    for count in range(1, len(darts) + 1):
        coordinator.async_receive("state", board(*darts[:count]))
        await settle(hass)


async def test_score_display_follows_the_real_board(hass, aioclient_mock, freezer):
    """A practice match on the board events and the sensor of the integration."""
    entry = await setup_bridge(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    practice = entity_id(hass, "sensor", "practice_remaining")
    publish = async_mock_service(hass, "mqtt", "publish")
    # An idle time that no timer of the integration has.
    idle = 7 * 60

    async def unchanged_board() -> dict:
        return dict(coordinator.data["local"])

    await automate(
        hass,
        "score_display",
        {
            **AWTRIX,
            "board_events": entity_id(hass, "event", "board_events"),
            "practice_score": practice,
            "idle_time": 7,
        },
    )
    with patch.object(coordinator.client, "get_state", side_effect=unchanged_board):
        async with waits(hass, idle):
            await coordinator.async_start_game(
                501, names=["Dennis", "Lea"], legs=1, sets=1, bull_off=False
            )
        async with waits(hass, FLASH):
            await throw(hass, coordinator, T20, T20, T20)
        async with waits(hass, idle):
            await tick(hass, freezer, FLASH)
        async with waits(hass, idle):
            coordinator.async_receive(
                "state", board(T20, T20, T20, event="Takeout started")
            )
            coordinator.async_receive("state", board(event="Takeout finished"))
        screens = awtrix_screens(publish)
        assert screens[:3] == [("501", WHITE), ("441", WHITE), ("381", WHITE)]
        assert screens[-3:] == [
            ("180!", GOLD),
            ("321", WHITE),
            # The darts pulled, Lea is up.
            ("501", WHITE),
        ]
        # The third dart's score gives way to the 180 that its board event
        # brings right after, at once or a moment later.
        assert screens[3:-3] in ([], [("321", WHITE)])

        # A leg of 101 decides the match: the winner stays until the idle time is over.
        async with waits(hass, idle):
            await coordinator.async_start_game(
                101, names=["Dennis", "Lea"], legs=1, sets=1, bull_off=False
            )
        routes = [hass.states.get(practice).attributes["checkout"]]
        async with waits(hass, idle):
            await throw(hass, coordinator, T20)
        routes.append(hass.states.get(practice).attributes["checkout"])
        async with waits(hass, FLASH):
            await throw(hass, coordinator, T20, S1, D20)
        async with waits(hass, idle):
            await tick(hass, freezer, FLASH)
        assert awtrix_screens(publish)[len(screens) :] == [
            (f"101 {routes[0]}", GREEN),
            (f"41 {routes[1]}", GREEN),
            ("40 D20", GREEN),
            ("Dennis WINS", GOLD),
        ]
        await pass_time(hass, freezer, idle)
    assert awtrix_screens(publish)[len(screens) + 4 :] == [None]


# -- walk-on music ----------------------------------------------------------------------


WALK_ON = {"board_events": EVENTS, "speakers": ["media_player.dartroom"]}
# Alex, Kim and the bot set up a match.
LINEUP = {
    "game": 501,
    "mode": "match",
    "players": 3,
    "names": ["Alex", "Kim", None],
    "bot_player": 3,
    "bot_level": 60,
    "resumed": False,
    "underway": False,
}


def walk_on_pack(hass, tmp_path, *files: str) -> tuple[list, list]:
    """Walk-on songs in the pack walk-ons of the media folder, the actions of the
    integration that find them, and the songs the speakers play and stop."""
    pack = tmp_path / "media" / "homedarts" / "voices" / "walk-ons"
    pack.mkdir(parents=True)
    for file in files:
        (pack / file).write_bytes(b"ID3")
    hass.config.media_dirs = {"local": str(tmp_path / "media")}
    async_setup_services(hass)
    hass.states.async_set(EVENTS, "unknown")
    return (
        async_mock_service(hass, "media_player", "play_media"),
        async_mock_service(hass, "media_player", "media_stop"),
    )


async def song_waits(hass, seconds: float) -> None:
    """Let a run find the song in the media folder, which the executor reads,
    and reach the wait of its walk-on."""
    for _ in range(100):
        try:
            await until_waiting(hass, seconds)
        except AssertionError:
            await hass.async_add_executor_job(lambda: None)
        else:
            return
    raise AssertionError(f"no walk-on of {seconds} s started")


async def walk_on(hass, freezer, seconds: float = 20) -> None:
    """The walk-on of a player plays to its end."""
    await song_waits(hass, seconds)
    await pass_time(hass, freezer, seconds)


def songs(calls) -> list[str]:
    """The files of the walk-on pack the speakers played."""
    prefix = "media-source://media_source/local/homedarts/voices/walk-ons/"
    assert all(call.data["media_content_type"] == "music" for call in calls)
    assert all(call.data["entity_id"] == ["media_player.dartroom"] for call in calls)
    return [call.data["media_content_id"].removeprefix(prefix) for call in calls]


async def test_walk_on_plays_the_song_of_every_player_in_turn(hass, tmp_path, freezer):
    play, stop = walk_on_pack(hass, tmp_path, "alex.mp3", "Bot.mp3", "default.mp3")
    await automate(hass, "walk_on", WALK_ON)
    fire(hass, "game_started", **LINEUP)
    await song_waits(hass, 20)
    # The next song follows within the same run, which a wait for the end of
    # the run would not let through.
    for _ in range(2):
        freezer.tick(timedelta(seconds=20))
        async_fire_time_changed(hass)
        await song_waits(hass, 20)
    await pass_time(hass, freezer, 20)
    # Kim has no song of her own.
    assert songs(play) == ["alex.mp3", "default.mp3", "Bot.mp3"]
    assert len(stop) == 3
    await pass_time(hass, freezer, 60)
    assert (len(play), len(stop)) == (3, 3)


async def test_walk_on_ends_at_the_first_dart(hass, tmp_path, freezer):
    play, stop = walk_on_pack(hass, tmp_path, "alex.mp3", "kim.mp3")
    await automate(hass, "walk_on", {**WALK_ON, "walk_on_seconds": 30})
    fire(hass, "game_started", **LINEUP)
    await song_waits(hass, 30)
    fire(hass, "dart_detected", segment="T20", score=60, dart_index=1)
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 60)
    assert (songs(play), len(stop)) == (["alex.mp3"], 1)


async def test_walk_on_ends_at_the_first_visit_entered_as_its_score(
    hass, tmp_path, freezer
):
    """A visit from the keypad or by voice comes without darts."""
    play, stop = walk_on_pack(hass, tmp_path, "alex.mp3", "kim.mp3")
    await automate(hass, "walk_on", {**WALK_ON, "walk_on_seconds": 30})
    fire(hass, "game_started", **LINEUP)
    await song_waits(hass, 30)
    fire(hass, "visit_completed", total=140, player=1)
    await hass.async_block_till_done()
    await pass_time(hass, freezer, 60)
    assert (songs(play), len(stop)) == (["alex.mp3"], 1)


async def test_walk_on_stays_silent_without_a_song_and_does_not_fail(
    hass, tmp_path, freezer, caplog
):
    """A player without a song, a pack without the songs, or no pack at all."""
    play, stop = walk_on_pack(hass, tmp_path, "kim.mp3")
    await saved(hass, "walk_on", WALK_ON)
    fire(hass, "game_started", **LINEUP)
    await walk_on(hass, freezer)
    await pass_time(hass, freezer, 60)
    assert (songs(play), len(stop)) == (["kim.mp3"], 1)
    await saved(hass, "walk_on", {**WALK_ON, "song_pack": "nobody"})
    fire(hass, "game_started", **LINEUP)
    for _ in range(5):
        await hass.async_add_executor_job(lambda: None)
        await hass.async_block_till_done()
    assert (len(play), len(stop)) == (1, 1)
    assert "Error" not in caplog.text


async def test_walk_on_plays_the_song_of_the_winner(hass, tmp_path, freezer):
    play, stop = walk_on_pack(hass, tmp_path, "alex.mp3", "bot.mp3", "default.mp3")
    await saved(hass, "walk_on", WALK_ON)
    won = {**LINEUP, "reason": "won", "winner": "Alex", "player": 1}
    # The bot wins with its own song, Kim with the default one.
    for player in (1, 3, 2):
        fire(hass, "game_ended", **{**won, "player": player})
        await walk_on(hass, freezer, 30)
    assert songs(play) == ["alex.mp3", "bot.mp3", "default.mp3"]
    assert len(stop) == 3
    # A song to its end, and no song of the winner.
    await saved(hass, "walk_on", {**WALK_ON, "winner_seconds": 0})
    fire(hass, "game_ended", **won)
    for _ in range(5):
        await hass.async_add_executor_job(lambda: None)
        await hass.async_block_till_done()
    await pass_time(hass, freezer, 60)
    assert (len(play), len(stop)) == (4, 3)
    await saved(hass, "walk_on", {**WALK_ON, "winner_song": False})
    fire(hass, "game_ended", **won)
    await hass.async_block_till_done()
    assert len(play) == 4


async def test_walk_on_stops_with_a_game_that_ends_otherwise(hass, tmp_path):
    play, stop = walk_on_pack(hass, tmp_path, "default.mp3")
    await automate(hass, "walk_on", WALK_ON)
    fire(hass, "game_started", **LINEUP)
    await song_waits(hass, 20)
    fire(hass, "game_ended", **{**LINEUP, "reason": "stopped"})
    await hass.async_block_till_done()
    assert (len(play), len(stop)) == (1, 1)
    # Nothing plays, so nothing stops.
    fire(hass, "game_ended", **{**LINEUP, "reason": "replaced"})
    await hass.async_block_till_done()
    assert len(stop) == 1


async def test_walk_on_leaves_out_games_without_walk_ons(hass, tmp_path):
    play, _ = walk_on_pack(hass, tmp_path, "default.mp3")
    await automate(hass, "walk_on", WALK_ON)
    await fire_all(
        hass,
        [
            ("game_started", {**LINEUP, "mode": "training", "game": "bobs_27"}),
            # A game that goes on, after the idle time or an undone visit.
            ("game_started", {**LINEUP, "resumed": True}),
            # A game started by its first dart, after a finished match.
            ("game_started", {**LINEUP, "underway": True}),
        ],
    )
    assert play == []


# -- examples of the documentation -------------------------------------------------------


def _voice_examples(document: str, action: str) -> list[dict]:
    """The examples of a guide that answer a sentence to Assist with an action."""
    text = (ROOT / document).read_text(encoding="utf-8")
    return [
        example
        for example in (
            safe_load(block)
            for block in re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)
            if "trigger: conversation" in block
        )
        if example["actions"][0]["action"] == action
    ]


@pytest.mark.parametrize(
    ("document", "language"),
    [("docs/automations.md", "en"), ("docs/automations.de.md", "de")],
)
async def test_the_voice_example_starts_every_game(hass, document, language):
    """Every game, spoken as the practice game select names it, starts that game;
    the names become the players, and Assist says what the action answers."""
    (example,) = _voice_examples(document, "homedarts.start_game")
    start, answer = example["actions"]
    assert start["response_variable"] == "result"
    assert answer == {"set_conversation_response": "{{ result.message }}"}
    translation = json.loads(
        (
            ROOT / "custom_components/homedarts/translations" / f"{language}.json"
        ).read_text(encoding="utf-8")
    )
    games = translation["entity"]["select"]["practice_game"]["state"]
    names = {"en": "Dennis and Lea", "de": "Dennis und Lea"}[language]
    for option, name in games.items():
        if option == "off":
            continue
        run = {"trigger": {"slots": {"game": name, "names": names}}}
        game = Template(start["data"]["game"], hass).async_render(
            run, parse_result=False
        )
        assert await _game_key(hass, game) == option, name
    players = Template(start["data"]["players"], hass).async_render(run)
    assert players == ["Dennis", "Lea"]


@pytest.mark.parametrize(
    ("document", "language", "message"),
    [
        (
            "docs/automations.md",
            "en",
            "140 for Alex, 361 left. Sam, you require 501.",
        ),
        (
            "docs/automations.de.md",
            "de",
            "140 für Alex, noch 361. Sam, du brauchst 501.",
        ),
    ],
)
async def test_the_voice_example_enters_a_visit(hass, document, language, message):
    """The example's sentence enters the visit for the player it names, and Assist
    says what the action answers."""
    (example,) = _voice_examples(document, "homedarts.enter_visit")
    enter, answer = example["actions"]
    assert enter["response_variable"] == "result"
    assert answer == {"set_conversation_response": "{{ result.message }}"}
    (sentence,) = example["triggers"][0]["command"]
    assert "{0..180:score}" in sentence and "{name}" in sentence
    await setup_manual(hass)
    hass.config.language = language
    await hass.services.async_call(
        "homedarts",
        "start_game",
        {"game": "501", "players": ["Alex", "Sam"]},
        blocking=True,
    )
    run = {"trigger": {"slots": {"score": 140, "name": "alex"}}}
    data = {
        key: Template(value, hass).async_render(run)
        for key, value in enter["data"].items()
    }
    result = await hass.services.async_call(
        "homedarts", "enter_visit", data, blocking=True, return_response=True
    )
    assert result == {"entered": True, "message": message}
