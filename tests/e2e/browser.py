"""Verify the dashboard cards in a real browser against the demo instance.

Runs in the Playwright container on the demo's Compose network (see browser.sh).
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
import tomllib
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from pages import (
    CARDS_DRAWN,
    STATES,
    expect_state,
    find,
    open_card_form,
    probe,
    run_until,
    settle,
    show,
    wait_for,
)
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Frame,
    Page,
    Playwright,
    Request,
    Route,
    sync_playwright,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from shards import Step, choose, shard
from watchdog import GRACE, budget, deadline, wake_playwright

HA = "http://homeassistant:8123"
# The client of the frontend at that address, which its login page signs in for.
CLIENT_ID = f"{HA}/"
BOARD = "http://board-mock:3180"
LOADS = 5
# Every request of homedarts-card.js, the module with all cards.
CARD_MODULE = "**/homedarts-card.js*"
# Seconds for which Safari's requests of homedarts-card.js are held back and then let
# go together, as on a slow network: longer than the five seconds Home Assistant
# waits for the element of a dashboard strategy.
CARD_MODULE_DELAY = 6
# Board Manager generation of the demo board, passed on by browser.sh.
GENERATION = int(os.environ.get("BOARD_MANAGER", "1"))
# Writable folder for screenshots, traces and timelines of a failed step, mounted by
# browser.sh.
ARTIFACTS = os.environ.get("BROWSER_ARTIFACTS", "")
# Steps to run instead of all, comma-separated, each the whole name of a step, which
# runs that step alone, or a beginning of names, such as "touch" or "correcting" while
# working on a screen (see shards.py); browser.sh passes BROWSER_STEPS on.
WANTED = os.environ.get("BROWSER_STEPS", "")
# A part of the steps, such as 2/4 for the second of four shards (see shards.py);
# browser.sh gives each of its workers one.
SHARD = os.environ.get("BROWSER_SHARD", "")
# The integration as mounted by browser.sh, for the texts every language expects.
INTEGRATION = Path(__file__).resolve().parents[2] / "custom_components" / "homedarts"


CARDS = find("homedarts-card")
TRAINING_CARDS = find("homedarts-training-card")
STATUS_CARDS = find("homedarts-status-card")
SCOREBOARD_CARDS = find("homedarts-scoreboard-card")
PLAYERS_CARDS = find("homedarts-players-card")
DOUBLES_CARDS = find("homedarts-doubles-card")
LEADERBOARD_CARDS = find("homedarts-leaderboard-card")
FORM_EDITORS = find("hui-form-editor")
SCOREBOARD_STATE = f"""
() => {{
  const root = ({SCOREBOARD_CARDS})()[0].shadowRoot;
  const text = (selector) => root.querySelector(selector)?.textContent ?? null;
  return {{
    title: text('.title'),
    banner: root.querySelector('.banner').hidden ? null : text('.banner'),
    players: [...root.querySelectorAll('.player')].map((el) => [
      el.querySelector('.name').textContent,
      el.querySelector('.big').textContent,
      el.classList.contains('active'),
    ]),
    route: [...root.querySelectorAll('.main .bed')].map((el) => el.textContent),
    big: text('.single .big'),
    cricket: [...root.querySelectorAll('.cricket tr')].map((row) =>
      [...row.children].map((cell) => cell.textContent)
    ),
    darts: [...root.querySelectorAll('.visit .segment')].map((el) => el.textContent),
    scorecard: [...root.querySelectorAll('.scorecard tbody tr')].map((row) =>
      [...row.children].map((cell) => cell.textContent)
    ),
    summary: [...root.querySelectorAll('.summary tr')].map((row) =>
      [...row.children].map((cell) => cell.textContent)
    ),
    sum: text('.sum .value'),
    tile: text('.sum .muted'),
    full: root.querySelector('.scoreboard').classList.contains('full'),
  }};
}}
"""
RENDERED = f"() => ({CARDS})().filter((card) => card.shadowRoot?.querySelector('.board svg')).length"
CARD_STATE = f"""
() => {{
  const card = ({CARDS})()[0];
  const root = card.shadowRoot;
  return {{
    score: root.querySelector('.score').textContent,
    slots: [...root.querySelectorAll('.slot .segment')].map((el) => el.textContent),
    latest: [...root.querySelectorAll('.slot')].findIndex((el) => el.classList.contains('latest')),
    hits: root.querySelectorAll('.hits .hit').length,
    darts: root.querySelectorAll('.darts .dart').length,
    blinking: root.querySelector('.hits').classList.contains('blink'),
    status: root.querySelector('.pill').textContent,
    toggle: root.querySelector('[data-action="toggle"]').textContent,
    numbers: root.querySelectorAll('.numbers text').length,
    beds: root.querySelectorAll('.face path').length,
    recent: [...root.querySelectorAll('.recent-visit')].map((el) => el.textContent),
  }};
}}
"""
# The visit of 115 ended by the reset: the card shows 0 points and no darts, and the
# visit leads the last visits.
VISIT_ENDED_BY_RESET = f"""
() => {{
  const state = ({CARD_STATE})();
  return state.score === '0' && state.darts === 0 && state.recent[0] === '115';
}}
"""
PRACTICE_STATE = f"""
() => {{
  const root = ({CARDS})()[0].shadowRoot;
  return {{
    hidden: root.querySelector('.practice').hidden,
    title: root.querySelector('.practice-title').textContent,
    remaining: root.querySelector('.practice-remaining').textContent,
    route: [...root.querySelectorAll('.practice-route .bed')].map((el) => el.textContent),
    aim: root.querySelectorAll('.aim path').length,
    meta: root.querySelector('.practice-meta').textContent,
    scores: [...root.querySelectorAll('.player-score')].map((el) => [
      el.querySelector('.who').textContent,
      el.querySelector('.rest').textContent,
      el.classList.contains('active'),
    ]),
    grid: [...root.querySelectorAll('.practice .cricket tr')].map((row) =>
      [...row.children].map((cell) => cell.textContent)
    ),
  }};
}}
"""
T20 = {
    "segment": {"name": "T20", "number": 20, "multiplier": 3, "bed": "Triple"},
    "coords": {"x": 0.035, "y": 0.608},
}
T1 = {
    "segment": {"name": "T1", "number": 1, "multiplier": 3, "bed": "Triple"},
    "coords": {"x": 0.187, "y": 0.576},
}
SINGLE_1 = {
    "segment": {"name": "S1", "number": 1, "multiplier": 1, "bed": "SingleOuter"},
    "coords": {"x": 0.25, "y": 0.72},
}
DOUBLE_20 = {
    "segment": {"name": "D20", "number": 20, "multiplier": 2, "bed": "Double"},
    "coords": {"x": 0.002, "y": 0.972},
}
# A single 20 in the outer single bed, where a treble 20 could be read.
SINGLE_20 = {
    "segment": {"name": "S20", "number": 20, "multiplier": 1, "bed": "SingleOuter"},
    "coords": {"x": 0.01, "y": 0.8},
}
# 101 in one visit: 60, 1 and the double 20.
CHECKOUT_101 = [
    T20,
    {
        "segment": {"name": "S1", "number": 1, "multiplier": 1, "bed": "SingleOuter"},
        "coords": {"x": 0.244, "y": 0.751},
    },
    {
        "segment": {"name": "D20", "number": 20, "multiplier": 2, "bed": "Double"},
        "coords": {"x": 0.0, "y": 0.976},
    },
]
# Calls a service for an Autodarts entity through the logged-in frontend.
CALL_SERVICE = """
async ([domain, service, key, data]) => {
  const hass = document.querySelector('home-assistant').hass;
  const entity = Object.values(hass.entities).find(
    (item) => item.platform === 'homedarts' && item.translation_key === key
  );
  await hass.callService(domain, service, { entity_id: entity.entity_id, ...data });
}
"""
# The state of an Autodarts entity by its translation key.
STATE_OF = """
(key) => {
  const hass = document.querySelector('home-assistant').hass;
  const entity = Object.values(hass.entities).find(
    (item) => item.platform === 'homedarts' && item.translation_key === key
  );
  return hass.states[entity.entity_id].state;
}
"""
# Names a practice player; the four name fields share one translation key.
SET_NAME = """
async ([index, name]) => {
  const hass = document.querySelector('home-assistant').hass;
  const ids = Object.values(hass.entities)
    .filter((item) => item.platform === 'homedarts' && item.translation_key === 'practice_player')
    .map((item) => item.entity_id)
    .sort();
  await hass.callService('text', 'set_value', { entity_id: ids[index], value: name });
}
"""
TRAINING_STATE = f"""
() => {{
  const root = ({TRAINING_CARDS})()[0].shadowRoot;
  const text = (selector) => root.querySelector(selector)?.textContent;
  return {{
    average: text('.average'),
    darts: text('[data-total="darts"]'),
    visits: text('[data-total="visits"]'),
    heat: root.querySelectorAll('.heat-layer path').length,
    top: [...root.querySelectorAll('.top-row .key')].map((el) => el.textContent),
    history: root.querySelectorAll('.history-chart .visit-bar:not(.empty)').length,
    highest: root.querySelector('[data-tile="highest"] .value')?.textContent,
    sessions: [...root.querySelectorAll('.session-table tbody tr')].map(
      (row) => [...row.children].slice(2).map((cell) => cell.textContent)
    ),
    session: text('[data-action="session"]'),
    state: text('.session-state'),
  }};
}}
"""
STATUS_STATE = f"""
() => {{
  const root = ({STATUS_CARDS})()[0].shadowRoot;
  return {{
    cameras: root.querySelectorAll('.camera').length,
    version: root.querySelector('.version')?.textContent,
    update: root.querySelector('.update-badge')?.textContent,
    detection: root.querySelector('.toggle')?.getAttribute('aria-checked'),
    chips: root.querySelectorAll('.chip').length,
    system: !root.querySelector('.system-tile')?.hidden,
    info: root.querySelector('.system-info')?.hidden ? '' : root.querySelector('.system-info')?.textContent,
  }};
}}
"""


# Records page errors with their text; Playwright reports some only as "Object".
CAPTURE_ERRORS = r"""
window.__pageErrors = [];
window.addEventListener("error", (event) => {
  window.__pageErrors.push(`${event.message} (${event.filename || "page"})`);
});
window.addEventListener("unhandledrejection", (event) => {
  let reason = event.reason;
  try {
    reason = JSON.stringify(reason, Object.getOwnPropertyNames(reason ?? {}));
  } catch (error) {
    reason = String(reason);
  }
  window.__pageErrors.push(`unhandled rejection: ${reason}`);
});
"""
# A browser notice, not an error: the sections view re-measures itself after the
# card's text wraps differently at the final column width (a few pixels).
BENIGN = ("ResizeObserver loop completed with undelivered notifications",)


class BrowserFailure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise BrowserFailure(message)


def board_requests() -> dict:
    with urllib.request.urlopen(f"{BOARD}/control/requests", timeout=10) as response:
        return json.load(response)


def control(changes: dict) -> None:
    request = urllib.request.Request(
        f"{BOARD}/control/state",
        data=json.dumps(changes).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(request, timeout=10).read()


def open_view(
    browser: Browser,
    view: str,
    cards: str,
    ready: str,
    scheme: str = "dark",
    locale: str = "en-US",
) -> tuple[Page, list[str]]:
    page = browser.new_page(
        locale=locale, viewport={"width": 1280, "height": 820}, color_scheme=scheme
    )
    problems: list[str] = []
    page.add_init_script(CAPTURE_ERRORS)
    page.on(
        "console",
        lambda message: (
            message.type == "error"
            and "homedarts" in message.text.lower()
            and problems.append(f"console: {message.text}")
        ),
    )
    page.goto(f"{HA}/homedarts-demo/{view}")
    page.wait_for_function(
        f"() => ({cards})().some((card) => card.shadowRoot?.querySelector('{ready}'))",
        timeout=30000,
    )
    return page, problems


def open_board(
    browser: Browser, scheme: str = "dark", locale: str = "en-US"
) -> tuple[Page, list[str]]:
    return open_view(browser, "board", CARDS, ".board svg", scheme, locale)


def page_errors(page: Page, problems: list[str]) -> list[str]:
    """Console errors from the card plus every page error except known notices."""
    recorded = page.evaluate("window.__pageErrors || []")
    return problems + [
        error for error in recorded if not any(text in error for text in BENIGN)
    ]


def fresh_loads(browser: Browser) -> None:
    # Home Assistant boots in parallel with the card module; every load must register it.
    for attempt in range(LOADS):
        page, problems = open_board(browser)
        check(page.evaluate(RENDERED) == 1, f"Load {attempt + 1}: card not rendered")
        errors = page_errors(page, problems)
        check(not errors, f"Load {attempt + 1}: {errors}")
        page.close()


def visit(browser: Browser) -> None:
    page, problems = open_board(browser)
    state = page.evaluate(CARD_STATE)
    expected = {
        "score": "115",
        "slots": ["T20", "S5", "Bull"],
        "latest": 2,
        "hits": 3,
        "darts": 3,
        "blinking": True,
        "status": "Remove your darts",
        "toggle": "Stop detection",
        "numbers": 20,
        "beds": 80,
        # The last completed visits, newest first.
        "recent": ["90", "112", "102", "125", "81"],
    }
    check(state == expected, f"Card state {state} != {expected}")

    # Discarding detected darts needs a second tap within a few seconds. The reset
    # comes before the stop, while the visit of 115 is on the board: only the board
    # that took the reset drops the darts and ends the visit on the card. A stop ends
    # the visit too, and after one the card showed 0 points before the reset had even
    # left Home Assistant, so the check of the board's commands came too early.
    commands = len(board_requests()["commands"])
    reset = page.locator("homedarts-card button[data-action='reset']")
    reset.click()
    check(reset.text_content() == "Confirm?", "Reset did not ask for confirmation")
    check(
        len(board_requests()["commands"]) == commands, "Reset ran without confirmation"
    )
    reset.click()
    page.wait_for_function(VISIT_ENDED_BY_RESET, timeout=15000)
    new = board_requests()["commands"][commands:]
    check(
        [(c["method"], c["path"]) for c in new] == [("POST", "/api/reset")],
        f"Reset sent {new}",
    )

    commands = len(board_requests()["commands"])
    page.locator("homedarts-card button[data-action='toggle']").click()
    page.wait_for_function(
        f"() => ({CARD_STATE})().toggle === 'Start detection'", timeout=15000
    )
    new = board_requests()["commands"][commands:]
    check(
        [(c["method"], c["path"]) for c in new] == [("PUT", "/api/stop")],
        f"Stop sent {new}",
    )
    page.locator("homedarts-card button[data-action='toggle']").click()
    page.wait_for_function(
        f"() => ({CARD_STATE})().toggle === 'Stop detection'", timeout=15000
    )
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()


def practice(browser: Browser) -> None:
    """A practice leg counts down and shows the route and the bed to aim at."""
    page, problems = open_board(browser)
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    page.evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "301"}]
    )
    page.wait_for_function(
        f"() => ({PRACTICE_STATE})().remaining === '301'", timeout=15000
    )
    for count in range(1, 4):
        control({"event": "Throw detected", "throws": [T20] * count})
    control({"status": "Takeout in progress", "event": "Takeout started"})
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    page.wait_for_function(
        f"() => ({PRACTICE_STATE})().remaining === '121'", timeout=15000
    )
    state = page.evaluate(PRACTICE_STATE)
    expected = {
        "hidden": False,
        "title": "Practice 301",
        "remaining": "121",
        "route": ["T20", "25", "D18"],
        "aim": 1,
    }
    check(
        {key: state[key] for key in expected} == expected and not state["scores"],
        f"Practice state {state} != {expected}",
    )

    # Two players: the scoreboard follows the turn after the darts are pulled.
    page.evaluate(SET_NAME, [0, "Alex"])
    page.evaluate(SET_NAME, [1, "Sam"])
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_players", {"value": 2}]
    )
    page.wait_for_function(
        f"() => ({PRACTICE_STATE})().scores.length === 2", timeout=15000
    )
    for count in range(1, 4):
        control({"event": "Throw detected", "throws": [T20] * count})
    control({"status": "Takeout in progress", "event": "Takeout started"})
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    page.wait_for_function(
        f"() => ({PRACTICE_STATE})().meta === 'Sam to throw'", timeout=15000
    )
    scores = page.evaluate(PRACTICE_STATE)["scores"]
    check(
        scores == [["Alex", "121", False], ["Sam", "301", True]],
        f"Scoreboard {scores}",
    )

    # Cricket: marks on the chalkboard, points while the other needs the 20.
    page.evaluate(
        CALL_SERVICE,
        ["select", "select_option", "practice_game", {"option": "cricket"}],
    )
    page.wait_for_function(
        f"() => ({PRACTICE_STATE})().title === 'Cricket'", timeout=15000
    )
    for count in range(1, 4):
        control({"event": "Throw detected", "throws": [T20] * count})
    control({"status": "Takeout in progress", "event": "Takeout started"})
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    page.wait_for_function(
        f"() => ({PRACTICE_STATE})().meta === 'Sam to throw'", timeout=15000
    )
    state = page.evaluate(PRACTICE_STATE)
    grid = state["grid"]
    check(
        grid[0][1:] == ["Alex", "Sam"]
        and grid[1] == ["20", "Ⓧ", ""]
        and ["Points", "120", "0"] in grid
        and state["remaining"] == "0"
        and state["route"] == ["T20"]
        and state["aim"] == 1,
        f"Cricket state {state}",
    )

    # Shanghai: the round, the number to hit and every player's points.
    page.evaluate(
        CALL_SERVICE,
        ["select", "select_option", "practice_game", {"option": "shanghai"}],
    )
    page.wait_for_function(
        f"() => ({PRACTICE_STATE})().title === 'Shanghai'", timeout=15000
    )
    single_one = {
        "segment": {"name": "S1", "number": 1, "multiplier": 1, "bed": "SingleOuter"},
        "coords": {"x": 0.25, "y": 0.72},
    }
    control({"event": "Throw detected", "throws": [single_one]})
    page.wait_for_function(
        f"() => ({PRACTICE_STATE})().remaining === '1'", timeout=15000
    )
    state = page.evaluate(PRACTICE_STATE)
    check(
        state["route"] == ["1"]
        and state["meta"].startswith("Round 1/7")
        and state["aim"] == 4,
        f"Shanghai state {state}",
    )
    control({"status": "Takeout in progress", "event": "Takeout started"})
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_players", {"value": 1}]
    )

    # Around the Clock: the next number and all of its beds to aim at.
    page.evaluate(
        CALL_SERVICE,
        ["select", "select_option", "practice_game", {"option": "around_the_clock"}],
    )
    page.wait_for_function(
        f"() => ({PRACTICE_STATE})().title === 'Around the Clock'", timeout=15000
    )
    one = {
        "segment": {"name": "S1", "number": 1, "multiplier": 1, "bed": "SingleOuter"},
        "coords": {"x": 0.25, "y": 0.72},
    }
    control({"event": "Throw detected", "throws": [one]})
    page.wait_for_function(
        f"() => ({PRACTICE_STATE})().remaining === '2'", timeout=15000
    )
    state = page.evaluate(PRACTICE_STATE)
    check(
        state["aim"] == 4 and " · 1 darts · " in state["meta"],
        f"Around the Clock state {state}",
    )
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    page.evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "off"}]
    )
    page.wait_for_function(f"() => ({PRACTICE_STATE})().hidden", timeout=15000)
    check(page.evaluate(PRACTICE_STATE)["aim"] == 0, "Aim still shown without a game")
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()


def progress(browser: Browser) -> None:
    """Badges, trends, the positions heatmap, the aim map and the leaderboard after the
    practice games."""
    page, problems = open_view(browser, "players", PLAYERS_CARDS, ".profile")
    page.wait_for_function(
        f"() => ({PLAYERS_CARDS})()[0].shadowRoot.querySelector('.badges-section:not([hidden])')",
        timeout=15000,
    )
    earned = page.evaluate(
        f"() => [...({PLAYERS_CARDS})()[0].shadowRoot.querySelectorAll('.badge:not(.locked)')]"
        ".map((badge) => badge.dataset.badge)"
    )
    # Alex threw a 180 in 301 and nine marks in Cricket.
    check("maximum" in earned and "cricket_nine" in earned, f"Earned badges {earned}")
    trends = page.evaluate(
        f"() => ({PLAYERS_CARDS})()[0].shadowRoot.querySelectorAll('.trend-player').length"
    )
    check(trends >= 1, f"Trends of {trends} players")
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()

    page, problems = open_view(browser, "training", TRAINING_CARDS, ".heat-layer")
    page.locator("homedarts-training-card button[data-mode='positions']").click()
    page.wait_for_function(
        f"() => ({TRAINING_CARDS})()[0].shadowRoot.querySelectorAll('.heat-layer .position').length > 0",
        timeout=15000,
    )
    page.locator("homedarts-training-card button[data-source='Alex']").click()
    page.wait_for_function(
        f"() => ({TRAINING_CARDS})()[0].shadowRoot"
        ".querySelector('button[data-source=\"Alex\"]').getAttribute('aria-pressed') === 'true'",
        timeout=15000,
    )
    page.wait_for_function(
        f"() => ({TRAINING_CARDS})()[0].shadowRoot.querySelectorAll('.heat-layer .position').length > 0",
        timeout=15000,
    )
    # Alex's aim map, from the worker of the card, or how many darts at a treble it needs.
    page.locator("homedarts-training-card button[data-mode='aim']").click()
    page.wait_for_function(
        f"() => {{ const root = ({TRAINING_CARDS})()[0].shadowRoot;"
        " return root.querySelector('.heat-layer .aim-best')"
        " || root.querySelector('.heat .groups:not([hidden]) .empty-hint'); }",
        timeout=15000,
    )
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()

    page, problems = open_view(browser, "leaderboard", LEADERBOARD_CARDS, ".record")
    leader = page.evaluate(
        f"() => ({LEADERBOARD_CARDS})()[0].shadowRoot"
        ".querySelector('[data-record=\"maximums\"] .record-leader .who')?.textContent"
    )
    check(leader == "Alex", f"Most 180s: {leader}")
    page.locator("homedarts-leaderboard-card button[data-period='week']").click()
    pressed = page.evaluate(
        f"() => ({LEADERBOARD_CARDS})()[0].shadowRoot"
        ".querySelector('[data-period=\"week\"]').getAttribute('aria-pressed')"
    )
    check(pressed == "true", "The period did not switch")
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()


def training(browser: Browser) -> None:
    page, problems = open_view(browser, "training", TRAINING_CARDS, ".heat-layer path")
    # The history of completed visits is loaded from the recorder.
    try:
        page.wait_for_function(
            f"() => ({TRAINING_STATE})().history === 5", timeout=15000
        )
    except PlaywrightTimeout:
        pass  # The comparison below reports what the card shows instead.
    state = page.evaluate(TRAINING_STATE)
    # Demo visits: 81, 125, 102, 112 and 90 points, plus 115 in progress.
    expected = {
        "average": "104.2",
        "darts": "18",
        "visits": "6",
        "heat": 11,
        "top": ["S20", "T20", "Bull", "S5", "25"],
        "history": 5,
        "highest": "125",
        # Darts, average and best visit of the two earlier sessions, newest first.
        "sessions": [["9", "86.0", "97"], ["6", "83.0", "140"]],
        "session": "End session",
        "state": "Session running",
    }
    check(state == expected, f"Training card state {state} != {expected}")

    # Ending a session needs a second tap; starting one does not.
    toggle = page.locator("homedarts-training-card button[data-action='session']")
    toggle.click()
    check(toggle.text_content() == "Confirm?", "Ending did not ask for confirmation")
    toggle.click()
    page.wait_for_function(
        f"() => ({TRAINING_STATE})().session === 'Start session'", timeout=30000
    )
    ended = page.evaluate(TRAINING_STATE)
    check(ended["state"].startswith("Session ended"), f"Session state {ended}")
    check(len(ended["sessions"]) == 3, f"Ended session missing: {ended['sessions']}")
    toggle.click()
    page.wait_for_function(f"() => ({TRAINING_STATE})().darts === '0'", timeout=30000)
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()


def status(browser: Browser) -> None:
    page, problems = open_view(browser, "status", STATUS_CARDS, ".camera")
    state = page.evaluate(STATUS_STATE)
    check(state["cameras"] == 3, f"Status card cameras: {state}")
    check(state["version"].startswith("Version "), f"Status card version: {state}")
    check(state["detection"] == "true", f"Status card detection: {state}")
    check(state["chips"] == 3, f"Status card connections: {state}")
    # Board Manager 2 describes its PC; the classic Board Manager does not.
    expected_info = (
        "Debian 13 · Intel Core i3-9100T · Detection 2.0.0" if GENERATION >= 2 else ""
    )
    check(state["info"] == expected_info, f"Status card board PC: {state}")

    commands = len(board_requests()["commands"])
    toggle = page.locator("homedarts-status-card .toggle")
    toggle.click()
    page.wait_for_function(
        f"() => ({STATUS_STATE})().detection === 'false'", timeout=15000
    )
    new = board_requests()["commands"][commands:]
    check(
        [(c["method"], c["path"]) for c in new] == [("PUT", "/api/stop")],
        f"Stop sent {new}",
    )
    toggle.click()
    page.wait_for_function(
        f"() => ({STATUS_STATE})().detection === 'true'", timeout=15000
    )

    # Restarting the Board Manager needs a second tap.
    restart = page.locator("homedarts-status-card button[data-action='restart']")
    commands = len(board_requests()["commands"])
    restart.click()
    check(restart.text_content() == "Confirm?", "Restart did not ask for confirmation")
    check(
        len(board_requests()["commands"]) == commands,
        "Restart ran without confirmation",
    )
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()


def scoreboard(browser: Browser) -> None:
    """The scoreboard view follows the visit, an X01 match, Cricket and a training game."""
    page = browser.new_page(locale="en-US", viewport={"width": 1280, "height": 800})
    page.add_init_script(CAPTURE_ERRORS)
    page.goto(f"{HA}/homedarts-auto/scoreboard")
    page.wait_for_function(
        f"() => ({SCOREBOARD_CARDS})().some((card) => card.shadowRoot?.querySelector('.main'))",
        timeout=30000,
    )

    def wait(condition: str) -> dict:
        page.wait_for_function(
            f"() => {{ const state = ({SCOREBOARD_STATE})(); return {condition}; }}",
            timeout=15000,
        )
        return page.evaluate(SCOREBOARD_STATE)

    def takeout() -> None:
        control({"status": "Takeout in progress", "event": "Takeout started"})
        control({"status": "Throw", "event": "Takeout finished", "throws": []})

    def game(option: str) -> None:
        page.evaluate(
            CALL_SERVICE,
            ["select", "select_option", "practice_game", {"option": option}],
        )

    # Between games, the visit score is the big number, and the last visit is beside
    # the darts.
    takeout()
    control({"event": "Throw detected", "throws": [T20]})
    state = wait("state.big === '60'")
    check(
        state["full"]
        and state["darts"] == ["T20", "–", "–"]
        and state["tile"] == "Last"
        and state["sum"] is not None,
        f"Scoreboard between games {state}",
    )
    takeout()

    # An X01 match: every player's score, the player at the board and the route.
    page.evaluate(SET_NAME, [0, "Alex"])
    page.evaluate(SET_NAME, [1, "Sam"])
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_players", {"value": 2}]
    )
    game("501")
    state = wait("state.players.length === 2")
    check(state["title"] == "Practice 501", f"Scoreboard title {state}")
    for count in range(1, 4):
        control({"event": "Throw detected", "throws": [T20] * count})
    state = wait("state.sum === '180'")
    check(
        state["players"][0] == ["Alex", "321", True] and state["darts"][2] == "T20",
        f"Scoreboard during the visit {state}",
    )
    takeout()
    state = wait("state.players[1][2]")
    check(
        state["players"] == [["Alex", "321", False], ["Sam", "501", True]],
        f"Scoreboard after the turn {state}",
    )

    # The match ends with its summary; the next dart starts the next match.
    page.evaluate(CALL_SERVICE, ["number", "set_value", "practice_legs", {"value": 1}])
    game("101")
    state = wait("state.players.length === 2 && state.players[0][1] === '101'")
    throws = [T20, SINGLE_1, DOUBLE_20]
    for count in range(1, 4):
        control({"event": "Throw detected", "throws": throws[:count]})
    takeout()
    state = wait("state.summary.length > 0")
    check(
        state["banner"] == "Alex wins the match!"
        # The winner is also named for screen readers.
        and state["summary"][0] == ["Match summary", "Alex Winner", "Sam"]
        and state["summary"][1] == ["Legs", "1", "0"]
        and ["3-dart avg.", "101.0", "–"] in state["summary"]
        and not state["players"],
        f"Scoreboard summary {state}",
    )
    control({"event": "Throw detected", "throws": [T20]})
    state = wait("state.summary.length === 0")
    check(state["banner"] is None, f"Scoreboard after the summary {state}")
    takeout()

    # Cricket: the chalkboard with both players.
    game("cricket")
    state = wait("state.title === 'Cricket'")
    check(
        state["cricket"][0] == ["T20", "Alex", "Sam"] and state["route"] == ["T20"],
        f"Scoreboard in Cricket {state}",
    )

    # A training game: the target is the big number.
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_players", {"value": 1}]
    )
    game("around_the_clock")
    state = wait("state.title === 'Around the Clock'")
    check(state["big"] == "1", f"Scoreboard in Around the Clock {state}")
    game("off")
    wait("state.big !== null && state.title !== 'Around the Clock'")
    errors = page_errors(page, [])
    check(not errors, f"Console problems: {errors}")
    page.close()


# Calls an action of the integration through the logged-in frontend.
CALL_ACTION = """
async ([service, data]) => {
  const hass = document.querySelector('home-assistant').hass;
  await hass.callService('homedarts', service, data);
}
"""


def play_comfort(browser: Browser) -> None:
    """A tap corrects a dart, the keypad enters one and passes, the bot throws, the
    last visit comes back, and the live card corrects a dart the same way."""
    page = browser.new_page(locale="en-US", viewport={"width": 1280, "height": 1000})
    page.add_init_script(CAPTURE_ERRORS)
    page.goto(f"{HA}/homedarts-demo/keypad")
    card = page.locator("homedarts-scoreboard-card")
    card.locator(".main").wait_for(timeout=30000)
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_bot_delay", {"value": 0.5}]
    )
    page.evaluate(CALL_SERVICE, ["switch", "turn_on", "practice_manual_entry"])
    page.evaluate(
        CALL_ACTION,
        ["start_game", {"game": "301", "players": ["Alex"], "bot_level": 120}],
    )
    card.locator(".pad").wait_for(timeout=15000)
    names = card.locator(".player .name").all_text_contents()
    check(names == ["Alex", "Bot Level 120"], f"Players against the bot {names}")
    title = card.locator(".pad .section-label").text_content()
    check(title == "Enter a dart", f"Keypad title {title!r}")

    # The board reads a single 20; a tap on the dart puts it into the treble.
    control({"event": "Throw detected", "throws": [T20, SINGLE_20]})
    card.locator("[data-dart='2']").click()
    title = card.locator(".pad .section-label").text_content()
    check(title == "Correct dart 2", f"Pad title {title!r}")
    card.locator("[data-pad='multiplier'][data-value='3']").click()
    card.locator(".pad-number[data-value='T20']").click()
    page.wait_for_function(
        f"() => ({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector('.sum .value')?.textContent === '120'",
        timeout=15000,
    )
    # The third dart entered by hand, then the next player with a second tap.
    card.locator("[data-pad='multiplier'][data-value='3']").click()
    card.locator(".pad-number[data-value='T20']").click()
    page.wait_for_function(
        f"() => ({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector('.sum .value')?.textContent === '180'",
        timeout=15000,
    )
    card.locator("[data-pad='next']").click()
    label = card.locator("[data-pad='next']").text_content()
    check(label == "Confirm?", f"Next player asks for a second tap: {label!r}")
    card.locator("[data-pad='next']").click()

    # The bot throws, and Alex is up again; the undo takes both visits back.
    page.wait_for_function(
        f"""() => {{
          const root = ({SCOREBOARD_CARDS})()[0].shadowRoot;
          const tiles = [...root.querySelectorAll('.player')];
          return tiles[0].classList.contains('active') && tiles[1].querySelector('.big').textContent !== '301';
        }}""",
        timeout=20000,
    )
    card.locator("[data-pad='undo']").click()
    card.locator("[data-pad='undo']").click()
    page.wait_for_function(
        f"""() => {{
          const root = ({SCOREBOARD_CARDS})()[0].shadowRoot;
          const values = [...root.querySelectorAll('.player .big')].map((el) => el.textContent);
          return values[0] === '121' && values[1] === '301';
        }}""",
        timeout=15000,
    )

    # A keyboard types the score of a visit into the score view, Enter sends it with
    # homedarts.enter_visit, and the pad keeps the keys for the next one.
    page.evaluate(
        CALL_ACTION,
        ["start_game", {"game": "301", "players": ["Alex"], "bot_level": 0}],
    )
    left = (
        f"[...({SCOREBOARD_CARDS})()[0].shadowRoot.querySelectorAll('.player .big')]"
        ".map((el) => el.textContent).join()"
    )
    page.wait_for_function(f"() => {left} === '301'", timeout=15000)
    card.locator("[data-pad='score']").click()
    for score, remaining in (("60", "241"), ("45", "196")):
        page.keyboard.type(score)
        page.keyboard.press("Enter")
        try:
            page.wait_for_function(f"() => {left} === '{remaining}'", timeout=15000)
        except PlaywrightTimeout:
            check(False, f"{score} and Enter left {page.evaluate(f'() => {left}')}")

    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_bot_level", {"value": 0}]
    )
    page.evaluate(CALL_SERVICE, ["switch", "turn_off", "practice_manual_entry"])
    page.evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "off"}]
    )
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    errors = page_errors(page, [])
    check(not errors, f"Console problems: {errors}")
    page.close()

    # The live card corrects a dart of the visit the same way; a pencil shows which.
    live = browser.new_page(locale="en-US", viewport={"width": 1280, "height": 1000})
    live.add_init_script(CAPTURE_ERRORS)
    live.goto(f"{HA}/homedarts-auto/live")
    live_card = live.locator("homedarts-card").first
    live_card.locator(".slots").wait_for(timeout=30000)
    control({"event": "Throw detected", "throws": [T20, SINGLE_20]})
    slots = f"({CARDS})()[0].shadowRoot.querySelectorAll('.slot')"
    live.wait_for_function(
        f"() => [...{slots}].map((el) => el.querySelector('.segment').textContent).join() === 'T20,S20,–'",
        timeout=15000,
    )
    pencils = live_card.locator(".slot.tappable .cue.edit").count()
    check(pencils == 2, f"Pencils on the live card's darts: {pencils}")
    live_card.locator(".slot[data-dart='2']").click()
    title = live_card.locator(".pad .section-label").text_content()
    check(title == "Correct dart 2", f"Live pad title {title!r}")
    live_card.locator("[data-pad='multiplier'][data-value='3']").click()
    live_card.locator(".pad-number[data-value='T20']").click()
    live.wait_for_function(
        f"() => [...{slots}].map((el) => el.querySelector('.segment').textContent).join() === 'T20,T20,–'",
        timeout=15000,
    )
    check(live_card.locator(".pad-area").is_hidden(), "The live pad stays open")
    errors = page_errors(live, [])
    check(not errors, f"Console problems on the live card: {errors}")
    live.close()
    control({"status": "Throw", "event": "Takeout finished", "throws": []})


def lobby(browser: Browser) -> None:
    """A game is chosen and started on the scoreboard, and ended there again."""
    page = browser.new_page(locale="en-US", viewport={"width": 1280, "height": 800})
    page.add_init_script(CAPTURE_ERRORS)
    page.goto(f"{HA}/homedarts-auto/scoreboard")
    card = "homedarts-scoreboard-card"
    page.locator(f"{card} .main").wait_for(timeout=30000)
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    page.evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "off"}]
    )
    page.locator(f"{card} .lobby-cta").click()
    page.locator(f"{card} .lobby").wait_for(timeout=15000)
    title = page.locator(f"{card} .title").text_content()
    check(title == "New game", f"Lobby title {title!r}")
    players = page.locator(f"{card} .lobby-player .who")
    # The screen starts with the players the board has; start from nobody.
    while players.count():
        page.locator(f"{card} .lobby-player [data-lobby='remove']").first.click()
    # Players at home come first: Alex and Sam are home, Kim is out.
    suggested = page.locator(f"{card} .suggestion:not(.guest)").all_text_contents()
    check(
        suggested[:3] == ["Alex⌂", "Sam⌂", "Kim"],
        f"Suggestions {suggested}",
    )
    page.locator(f"{card} .game[data-value='cricket']").click()
    page.locator(f"{card} .suggestion", has_text="Sam").click()
    name = page.locator(f"{card} .lobby-name")
    name.fill("Robin")
    name.press("Enter")
    page.locator(f"{card} .suggestion", has_text="Alex").click()
    check(
        players.all_text_contents() == ["Sam", "Robin", "Alex"],
        f"Players {players.all_text_contents()}",
    )
    page.locator(f"{card} [data-lobby='up'][data-value='2']").click()
    page.locator(f"{card} [data-lobby='up'][data-value='1']").click()
    page.locator(f"{card} [data-lobby='remove'][data-value='2']").click()
    page.locator(f"{card} [data-lobby='legs'][data-value='1']").click()
    check(
        players.all_text_contents() == ["Alex", "Sam"],
        f"Players {players.all_text_contents()}",
    )
    pictures = page.locator(f"{card} .lobby-player .avatar").count()
    check(pictures == 2, f"{pictures} pictures of linked players")
    page.locator(f"{card} .lobby .start").click()

    # The scoreboard shows the game it started, with the pictures of the players.
    page.wait_for_function(
        f"() => ({SCOREBOARD_STATE})().title === 'Cricket'", timeout=15000
    )
    state = page.evaluate(SCOREBOARD_STATE)
    check(state["cricket"][0][1:] == ["Alex", "Sam"], f"Scoreboard {state}")
    heads = page.locator(f"{card} .cricket thead .avatar").count()
    check(heads == 2, f"{heads} pictures on the chalkboard")
    legs = page.evaluate(STATE_OF, "practice_legs")
    check(legs in ("2", "2.0"), f"Legs per set {legs!r}")

    # During a game the header opens the screen; ending the game needs a second tap.
    page.locator(f"{card} .lobby-toggle").click()
    end = page.locator(f"{card} [data-lobby='end']")
    end.click()
    check(end.text_content() == "Confirm?", "Ending did not ask for confirmation")
    end.click()
    page.wait_for_function(
        f"() => !({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector(\"[data-lobby='end']\")",
        timeout=15000,
    )
    page.locator(f"{card} [data-lobby='close']").click()
    page.locator(f"{card} .lobby-cta").wait_for(timeout=15000)
    errors = page_errors(page, [])
    check(not errors, f"Console problems: {errors}")
    page.close()


def more_games(browser: Browser) -> None:
    """A team match, Tactics and Golf on the scoreboard."""
    page = browser.new_page(locale="en-US", viewport={"width": 1280, "height": 800})
    page.add_init_script(CAPTURE_ERRORS)
    page.goto(f"{HA}/homedarts-auto/scoreboard")
    page.wait_for_function(
        f"() => ({SCOREBOARD_CARDS})().some((card) => card.shadowRoot?.querySelector('.main'))",
        timeout=30000,
    )

    def wait(condition: str) -> dict:
        page.wait_for_function(
            f"() => {{ const state = ({SCOREBOARD_STATE})(); return {condition}; }}",
            timeout=15000,
        )
        return page.evaluate(SCOREBOARD_STATE)

    def takeout() -> None:
        control({"status": "Takeout in progress", "event": "Takeout started"})
        control({"status": "Throw", "event": "Takeout finished", "throws": []})

    def call(domain: str, service: str, key: str, **data) -> None:
        page.evaluate(CALL_SERVICE, [domain, service, key, data])

    takeout()
    for index, name in enumerate(("Alex", "Sam", "Kim", "Lea")):
        page.evaluate(SET_NAME, [index, name])
    call("number", "set_value", "practice_players", value=4)
    call("switch", "turn_on", "practice_teams")
    call("select", "select_option", "practice_game", option="301")
    state = wait("state.players.length === 2")
    check(
        state["players"] == [["Alex & Kim", "301", True], ["Sam & Lea", "301", False]],
        f"Scoreboard of a team match {state}",
    )
    control({"event": "Throw detected", "throws": [T20]})
    takeout()
    state = wait("state.players[1][2]")
    check(
        state["players"] == [["Alex & Kim", "241", False], ["Sam & Lea", "301", True]],
        f"Scoreboard after the first team visit {state}",
    )
    call("switch", "turn_off", "practice_teams")
    call("number", "set_value", "practice_players", value=2)

    call("select", "select_option", "practice_game", option="tactics")
    state = wait("state.title === 'Tactics'")
    numbers = [row[0] for row in state["cricket"][1:13]]
    check(
        numbers == [*(str(number) for number in range(20, 9, -1)), "Bull"],
        f"Scoreboard in Tactics {state}",
    )

    call("select", "select_option", "practice_game", option="golf")
    state = wait("state.title === 'Golf' && state.scorecard.length === 2")
    control({"event": "Throw detected", "throws": [T1]})
    takeout()
    # A treble is two strokes.
    state = wait("state.scorecard[0][1] === '2'")
    check(
        state["scorecard"][0][0] == "Alex" and state["scorecard"][0][-1] == "2",
        f"Scorecard of Golf {state}",
    )
    call("number", "set_value", "practice_players", value=1)
    call("select", "select_option", "practice_game", option="off")
    errors = page_errors(page, [])
    check(not errors, f"Console problems: {errors}")
    page.close()


def tournament(browser: Browser) -> None:
    """A round robin started on the new game screen, played, shown and stopped."""
    page = browser.new_page(locale="en-US", viewport={"width": 1280, "height": 800})
    page.add_init_script(CAPTURE_ERRORS)
    # The step runs the clock of the page through the summary of the match.
    page.clock.install()
    page.goto(f"{HA}/homedarts-demo/tournament")
    card = "homedarts-scoreboard-card"
    page.locator(f"{card} .main").wait_for(timeout=30000)
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    page.evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "off"}]
    )
    page.locator(f"{card} .main .lobby-cta").click()
    page.locator(f"{card} [data-lobby='mode'][data-value='tournament']").click()
    groups = page.locator(f"{card} .lobby-group > .section-label").all_text_contents()
    check(groups == ["X01", "Cricket"], f"Tournament games {groups}")
    players = page.locator(f"{card} .lobby-player .who")
    while players.count():
        page.locator(f"{card} .lobby-player [data-lobby='remove']").first.click()
    for name in ("Alex", "Sam", "Kim"):
        page.locator(f"{card} .suggestion", has_text=name).click()
    page.locator(f"{card} .game", has_text="101").click()
    fewer = page.locator(f"{card} [data-lobby='legs'][data-value='-1']")
    while not fewer.is_disabled():
        fewer.click()
    start = page.locator(f"{card} .lobby .start")
    check(start.text_content() == "Start tournament", "No tournament to start")
    start.click()

    # Kim and Sam open the round robin; its round is in the match view.
    page.wait_for_function(
        f"() => ({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector('.meta')"
        ".textContent.startsWith('Tournament · Round 1 · Match 1 of 3')",
        timeout=15000,
    )
    state = page.evaluate(SCOREBOARD_STATE)
    check(
        [player[0] for player in state["players"]] == ["Kim", "Sam"],
        f"First match {state}",
    )
    for count in range(1, 4):
        control({"event": "Throw detected", "throws": CHECKOUT_101[:count]})
    control({"status": "Throw", "event": "Takeout finished", "throws": []})

    # The summary of the match first, and after its eight seconds on the clock of
    # the page the table with the next match.
    table = page.locator(f"{card} .standings")
    page.locator(f"{card} table.summary").wait_for(timeout=15000)
    check(not table.count(), "The table showed before the summary of the match")
    run_until(
        page,
        table,
        15000,
        "The table after the summary of the match",
        page.locator(card),
    )
    rows = page.locator(f"{card} .standings tbody .who").all_text_contents()
    check(rows == ["Kim", "Alex", "Sam"], f"Table {rows}")
    pairing = page.locator(f"{card} .pairing").text_content()
    check(pairing == "AlexvsKim", f"Next match {pairing!r}")
    page.locator(f"{card} .start-next").click()
    page.wait_for_function(
        f"() => ({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector('.meta')"
        ".textContent.startsWith('Tournament · Round 2 · Match 2 of 3')",
        timeout=15000,
    )

    # Ending the game stops the tournament too.
    page.locator(f"{card} .lobby-toggle").click()
    end = page.locator(f"{card} [data-lobby='end']")
    check(end.text_content() == "Stop tournament", f"End button {end.text_content()}")
    end.click()
    end.click()
    page.wait_for_function(
        f"() => !({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector(\"[data-lobby='end']\")",
        timeout=15000,
    )
    stage = page.evaluate(STATE_OF, "tournament")
    check(stage == "no_tournament", f"Tournament after stopping: {stage}")
    page.locator(f"{card} [data-lobby='close']").click()
    errors = page_errors(page, [])
    check(not errors, f"Console problems: {errors}")
    page.close()


# The landscape tablet at the board that the scoreboard screens are built for.
TABLET = {"width": 800, "height": 480}
# Controls the card sizes for a finger; each is at least 44 px high, the keys of the
# pad at least 40 px, so that the pad fits beside the scores of a short screen.
FINGER_TARGETS = (
    ".lobby-cta, .lobby button, .pad button, .visit button.sum, .start-next"
)
PAD_KEYS = ".pad button"
# The width of the scoreboard against its room, and every control that is smaller
# than the card means it to be: finger targets, and whatever has a minimum size of
# 44 px or more in the card's style.
TABLET_LAYOUT = f"""
() => {{
  const card = ({SCOREBOARD_CARDS})()[0];
  const root = card.shadowRoot;
  const frame = root.querySelector('ha-card');
  const small = [];
  let targets = 0;
  for (const el of root.querySelectorAll('button, input, {FINGER_TARGETS}')) {{
    if (!el.getClientRects().length) continue;
    const box = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    const finger = el.matches('{FINGER_TARGETS}');
    if (finger) targets += 1;
    const high = finger || parseFloat(style.minHeight) >= 44;
    const wide = parseFloat(style.minWidth) >= 44;
    const least = el.matches('{PAD_KEYS}') ? 39.5 : 43.5;
    if ((high && box.height < least) || (wide && box.width < 43.5)) {{
      const name = `${{el.className || el.tagName.toLowerCase()}} "${{el.textContent.trim()}}"`;
      small.push(`${{name}} ${{Math.round(box.width)}}x${{Math.round(box.height)}}`);
    }}
  }}
  return {{
    width: frame.scrollWidth,
    room: frame.clientWidth,
    right: Math.round(card.getBoundingClientRect().right),
    viewport: innerWidth,
    targets,
    small,
  }};
}}
"""
# The fitted scoreboard: its height against the screen and its own room, where the
# start of the new game screen sits, and the pad beside the scores.
TABLET_FIT = f"""
() => {{
  const card = ({SCOREBOARD_CARDS})()[0];
  const root = card.shadowRoot;
  const frame = root.querySelector('ha-card');
  const box = (selector) => {{
    const el = root.querySelector(selector);
    if (!el || !el.getClientRects().length) return null;
    const rect = el.getBoundingClientRect();
    return {{ top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right }};
  }};
  const actions = root.querySelector('.lobby-actions');
  return {{
    bottom: Math.round(card.getBoundingClientRect().bottom),
    screen: innerHeight,
    height: frame.scrollHeight,
    room: frame.clientHeight,
    sticky: actions ? getComputedStyle(actions).position : null,
    actions: box('.lobby-actions'),
    main: box('.scoreboard > .main'),
    pad: box('.scoreboard > .pad-area'),
    beside: !!root.querySelector('.scoreboard.full.with-pad'),
  }};
}}
"""


def tablet_screen(browser: Browser) -> None:
    """The new game screen, scoreboard, keypad and tournament on an 800 x 480 tablet:
    nothing wider than the screen, targets for a finger, and idle mode without motion."""
    page = browser.new_page(locale="en-US", viewport=TABLET)
    page.add_init_script(CAPTURE_ERRORS)
    # The step runs the clock of the page through the summary of a match and the
    # time before idle mode.
    page.clock.install()
    card = "homedarts-scoreboard-card"

    def fits(screen: str, targets: bool = True) -> None:
        layout = page.evaluate(TABLET_LAYOUT)
        check(
            layout["width"] <= layout["room"] + 1
            and layout["right"] <= layout["viewport"] + 1,
            f"{screen} is wider than the tablet: {layout}",
        )
        check(not targets or layout["targets"], f"{screen} has no targets: {layout}")
        check(not layout["small"], f"{screen}: targets below 44 px {layout['small']}")

    def fills(screen: str) -> None:
        """A full-height scoreboard is one screen high and needs no scrolling."""
        fit = page.evaluate(TABLET_FIT)
        check(
            fit["bottom"] <= fit["screen"] + 1 and fit["height"] <= fit["room"] + 1,
            f"{screen} is higher than the tablet: {fit}",
        )

    def open_screen(view: str) -> None:
        errors = page_errors(page, [])
        check(not errors, f"Console problems: {errors}")
        page.goto(f"{HA}/homedarts-demo/{view}")
        page.locator(f"{card} .main").wait_for(timeout=30000)

    def game_off() -> None:
        page.evaluate(
            CALL_SERVICE,
            ["select", "select_option", "practice_game", {"option": "off"}],
        )
        control({"status": "Throw", "event": "Takeout finished", "throws": []})

    def end_game() -> None:
        page.locator(f"{card} .lobby-toggle").click()
        end = page.locator(f"{card} [data-lobby='end']")
        end.click()
        end.click()
        page.wait_for_function(
            f"() => !({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector(\"[data-lobby='end']\")",
            timeout=15000,
        )
        page.locator(f"{card} [data-lobby='close']").click()

    def choose(names: tuple[str, ...], game: str) -> None:
        players = page.locator(f"{card} .lobby-player .who")
        while players.count():
            page.locator(f"{card} .lobby-player [data-lobby='remove']").first.click()
        for name in names:
            page.locator(f"{card} .suggestion", has_text=name).click()
        page.locator(f"{card} .game", has_text=game).first.click()

    # Between games, then the new game screen and an X01 match it starts.
    page.goto(f"{HA}/homedarts-demo/tournament")
    page.locator(f"{card} .main").wait_for(timeout=30000)
    game_off()
    page.locator(f"{card} .lobby-cta").wait_for(timeout=15000)
    fits("The scoreboard between games")
    page.locator(f"{card} .lobby-cta").click()
    page.locator(f"{card} .lobby").wait_for(timeout=15000)
    fits("The new game screen")
    # The start stays at the bottom of the screen while the choices scroll.
    fit = page.evaluate(TABLET_FIT)
    actions = fit["actions"]
    check(
        fit["sticky"] == "sticky"
        and actions is not None
        and 0 <= actions["top"]
        and actions["bottom"] <= fit["screen"] + 1,
        f"The start of the new game screen is out of reach: {fit}",
    )
    choose(("Alex", "Sam"), "501")
    page.locator(f"{card} .lobby .start").click()
    page.wait_for_function(
        f"() => ({SCOREBOARD_STATE})().players.length === 2", timeout=15000
    )
    control({"event": "Throw detected", "throws": [T20]})
    page.wait_for_function(
        f"() => ({SCOREBOARD_STATE})().darts[0] === 'T20'", timeout=15000
    )
    fits("The scoreboard of a match", targets=False)
    fills("The scoreboard of a match")
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    end_game()

    # The keypad for darts entered by hand.
    open_screen("keypad")
    page.evaluate(CALL_SERVICE, ["switch", "turn_on", "practice_manual_entry"])
    page.evaluate(
        CALL_ACTION, ["start_game", {"game": "301", "players": ["Alex", "Sam"]}]
    )
    page.locator(f"{card} .pad").wait_for(timeout=15000)
    fits("The keypad")
    fills("The keypad")
    # In landscape, the pad sits beside the scores instead of below them.
    fit = page.evaluate(TABLET_FIT)
    main, pad = fit["main"], fit["pad"]
    check(
        fit["beside"]
        and main is not None
        and pad is not None
        and pad["left"] >= main["right"] - 1
        and pad["top"] < main["bottom"],
        f"The pad is not beside the scores: {fit}",
    )
    # Full screen: the keypad layout still fills exactly one screen, with the hint of a
    # browser that can't keep the screen on over plain HTTP in the header, and the button
    # brings the configured height back.
    toggle = page.locator(f"{card} .fullscreen-toggle")
    toggle.click()
    page.wait_for_function("() => !!document.fullscreenElement", timeout=15000)
    check(
        toggle.get_attribute("aria-pressed") == "true",
        "The full-screen button is not pressed in full screen",
    )
    page.locator(f"{card} header .awake-hint").wait_for(timeout=15000)
    fits("The keypad in full screen")
    fills("The keypad in full screen")
    check(
        page.evaluate(TABLET_FIT)["beside"],
        "The pad is not beside the scores in full screen",
    )
    toggle.click()
    page.wait_for_function("() => !document.fullscreenElement", timeout=15000)
    check(
        toggle.get_attribute("aria-pressed") == "false",
        "The full-screen button stays pressed after full screen",
    )
    fills("The keypad after full screen")
    page.evaluate(CALL_SERVICE, ["switch", "turn_off", "practice_manual_entry"])
    game_off()

    # A round robin: its setup, a match and the table with the next match.
    open_screen("tournament")
    page.locator(f"{card} .main .lobby-cta").click()
    page.locator(f"{card} [data-lobby='mode'][data-value='tournament']").click()
    choose(("Alex", "Sam", "Kim"), "101")
    fewer = page.locator(f"{card} [data-lobby='legs'][data-value='-1']")
    while not fewer.is_disabled():
        fewer.click()
    fits("The tournament setup")
    page.locator(f"{card} .lobby .start").click()
    page.wait_for_function(
        f"() => ({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector('.meta')"
        ".textContent.startsWith('Tournament · Round 1')",
        timeout=15000,
    )
    fits("A tournament match", targets=False)
    for count in range(1, 4):
        control({"event": "Throw detected", "throws": CHECKOUT_101[:count]})
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    # The table follows the eight seconds of the match summary, whose timer starts
    # only once the checkout has reached the card: running the clock before that
    # runs it out without a timer to fire.
    page.locator(f"{card} table.summary").wait_for(timeout=15000)
    run_until(
        page,
        page.locator(f"{card} .standings"),
        15000,
        "The table after the summary of the match",
        page.locator(card),
    )
    page.locator(f"{card} .start-next").wait_for(timeout=15000)
    fits("The tournament table")
    end_game()
    stage = page.evaluate(STATE_OF, "tournament")
    check(stage == "no_tournament", f"Tournament after stopping: {stage}")
    game_off()

    # Idle mode after ten seconds on the clock of the page, without its fade for a
    # device that asks for less motion; a tap brings the scoreboard back.
    page.emulate_media(reduced_motion="reduce")
    open_screen("idle")
    panel = page.locator(f"{card} .idle-panel")
    run_until(page, panel, 20000, "Idle mode", page.locator(card))
    motion = panel.evaluate(
        "(el) => [matchMedia('(prefers-reduced-motion: reduce)').matches,"
        " getComputedStyle(el).animationName]"
    )
    check(motion == [True, "none"], f"Idle mode with reduced motion: {motion}")
    fits("Idle mode", targets=False)
    panel.click()
    panel.wait_for(state="detached", timeout=15000)
    errors = page_errors(page, [])
    check(not errors, f"Console problems: {errors}")
    page.close()


# Touch screens as players use them: the companion app on an iPhone passes the status
# bar and the home indicator on as safe areas (top, bottom), a small Android phone shows
# the dashboard in its browser, an iPhone on its side keeps the home indicator below, and
# a 24 inch touch monitor stands beside the board, as many players have it.
TOUCH_SCREENS = (
    ("iPhone", {"width": 393, "height": 852}, (59, 34)),
    ("small Android phone", {"width": 360, "height": 640}, (0, 0)),
    ("iPhone in landscape", {"width": 852, "height": 393}, (0, 21)),
    ("24-inch touch monitor", {"width": 1920, "height": 1080}, (0, 0)),
)
# Four players whose long names have to fit a phone.
LONG_NAMES = ["Maximilian", "Anneliese-Charlotte", "Bartholomäus", "Konstantin"]


def phone_style(top: int, bottom: int) -> str:
    """Home Assistant's safe areas as the companion app sets them, and a theme whose
    cards are see-through, as glass themes make them."""
    return f"""
const style = document.createElement('style');
style.textContent = `html {{
  --app-safe-area-inset-top: {top}px !important;
  --app-safe-area-inset-bottom: {bottom}px !important;
  --ha-card-background: rgba(60, 64, 80, 0.35) !important;
}}`;
// The script runs before the page has an element to hold the style.
const add = () => document.documentElement.append(style);
if (document.documentElement) add();
else document.addEventListener('DOMContentLoaded', add, {{ once: true }});
"""


# The room a phone leaves: above the home indicator, the scoreboard's own height.
PHONE_FIT = f"""
() => {{
  const card = ({SCOREBOARD_CARDS})()[0];
  const frame = card.shadowRoot.querySelector('ha-card');
  const inset = getComputedStyle(document.documentElement).getPropertyValue('--safe-area-inset-bottom');
  return {{
    bottom: Math.round(card.getBoundingClientRect().bottom),
    free: innerHeight - (parseFloat(inset) || 0),
    height: frame.scrollHeight,
    room: frame.clientHeight,
  }};
}}
"""
# The start bar of the new game screen: whether it stays at the bottom, covers what
# scrolls beneath it with a background of its own, spans the card and keeps the start
# above the home indicator.
START_BAR = f"""
() => {{
  const root = ({SCOREBOARD_CARDS})()[0].shadowRoot;
  const bar = root.querySelector('.lobby-actions');
  const style = getComputedStyle(bar);
  const frame = root.querySelector('ha-card').getBoundingClientRect();
  const box = bar.getBoundingClientRect();
  const start = root.querySelector('.lobby .start').getBoundingClientRect();
  const inset = getComputedStyle(document.documentElement).getPropertyValue('--safe-area-inset-bottom');
  return {{
    sticky: style.position,
    layers: style.backgroundImage,
    base: style.backgroundColor,
    edges: [Math.round(box.left - frame.left), Math.round(frame.right - box.right)],
    start: [Math.round(start.top), Math.round(start.bottom)],
    free: innerHeight - (parseFloat(inset) || 0),
    buttons: [...bar.querySelectorAll('button')].map((el) => el.dataset.lobby),
    hints: root.querySelectorAll('.lobby-hint').length,
  }};
}}
"""
# Where on the screen the scoreboard's control of every tap was as it was tapped.
TAP_PLACE = f"""
() => {{
  const root = ({SCOREBOARD_CARDS})()[0].shadowRoot;
  root.addEventListener('click', (event) => {{
    const control = event.target.closest('[data-focus]');
    window.__tapped = control && [control.dataset.focus, control.getBoundingClientRect().top];
  }}, true);
}}
"""
# How far the control of the last tap moved on the screen since, and the page's scroll.
TAP_MOVED = f"""
() => {{
  const [key, top] = window.__tapped;
  const root = ({SCOREBOARD_CARDS})()[0].shadowRoot;
  const control = [...root.querySelectorAll('[data-focus]')].find((item) => item.dataset.focus === key);
  return {{
    moved: Math.round(control.getBoundingClientRect().top - top),
    scrolled: Math.round(scrollY),
  }};
}}
"""
# Every card on the page against the width of the phone, and names cut short.
PHONE_WIDTH = """
() => {
  const cards = [];
  (function collect(root) {
    root.querySelectorAll('*').forEach((el) => {
      if (el.tagName.startsWith('HOMEDARTS-') && el.shadowRoot) cards.push(el);
      if (el.shadowRoot) collect(el.shadowRoot);
    });
  })(document);
  const wide = [];
  const cut = [];
  for (const card of cards) {
    const frame = card.shadowRoot.querySelector('ha-card');
    if (!frame) continue;
    if (frame.scrollWidth > frame.clientWidth + 1 || card.getBoundingClientRect().right > innerWidth + 1) {
      wide.push(`${card.tagName.toLowerCase()} ${frame.scrollWidth}/${frame.clientWidth}`);
    }
    for (const el of card.shadowRoot.querySelectorAll('.tile .name')) {
      if (el.scrollWidth > el.clientWidth + 1) cut.push(el.textContent);
    }
  }
  return { cards: cards.length, wide, cut };
}
"""
# The middle of the treble 20 and a spot in the single 20 beside it, in millimetres
# from the bull with y up, as positions count.
TREBLE_20_SPOT = (0, 102)
SINGLE_20_SPOT = (15, 60)
# The part of the board to tap in sight, and where the board is on the screen.
BOARD_VIEW = """
(el) => {
  const [x, y, size] = el.getAttribute('viewBox').split(' ').map(Number);
  const rect = el.getBoundingClientRect();
  return { x, y, size, left: rect.left, top: rect.top, width: rect.width, height: rect.height };
}
"""
LOUPE_SHOWN = (
    f"() => !({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector('.loupe').hidden"
)


# What spoils the pad with its board: a key that something else covers where a
# finger taps it, and a board that draws beyond its box when zoomed in, over the keys
# and past the edge of the card.
PAD_PROBLEMS = f"""
() => {{
  const root = ({SCOREBOARD_CARDS})()[0].shadowRoot;
  const covered = [...root.querySelectorAll('.pad button')]
    .filter((key) => {{
      const rect = key.getBoundingClientRect();
      const hit = root.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
      return rect.width > 0 && !key.contains(hit);
    }})
    .map((key) => `covered: ${{key.textContent.trim()}}`);
  const board = root.querySelector('.pad-board');
  const overflow = board && getComputedStyle(board).overflow;
  return [...covered, ...(board && !['hidden', 'clip'].includes(overflow) ? [`board drawn beyond its box: ${{overflow}}`] : [])];
}}
"""


def board_point(view: dict, spot: tuple[float, float]) -> tuple[float, float]:
    """Where a spot of the board in millimetres is on the screen, zoomed in or not."""
    scale = min(view["width"], view["height"]) / view["size"]
    middle_x = view["x"] + view["size"] / 2
    middle_y = view["y"] + view["size"] / 2
    return (
        view["left"] + view["width"] / 2 + (spot[0] - middle_x) * scale,
        view["top"] + view["height"] / 2 + (-spot[1] - middle_y) * scale,
    )


def fingers(page: Page, *moves: list[tuple[float, float]]) -> bool:
    """Fingers on the touch screen, each from its first point to its last, as the
    browser gets them from a real screen; whether the loupe showed on the way. They
    rest on their last points before they let go, as a finger does that reads the
    loupe: one that leaves still moving flings, and the next tap only stops the fling."""
    session = page.context.new_cdp_session(page)

    def send(kind: str, points: list[tuple[float, float]]) -> None:
        session.send(
            "Input.dispatchTouchEvent",
            {
                "type": kind,
                "touchPoints": [
                    {"x": x, "y": y, "id": index} for index, (x, y) in enumerate(points)
                ],
            },
        )

    send("touchStart", [move[0] for move in moves])
    send("touchMove", [move[-1] for move in moves])
    shown = bool(page.evaluate(LOUPE_SHOWN))
    page.wait_for_timeout(120)
    send("touchEnd", [])
    session.detach()
    return shown


def steady_games(page: Page, device: str, card: str) -> None:
    """Every game of the new game screen is chosen by a tap and stays under the finger:
    where the rules of the game before leave above it, the page follows, unless it is at
    its top already."""
    page.evaluate(TAP_PLACE)
    games = page.locator(f"{card} .lobby .game")
    for index in range(games.count()):
        games.nth(index).tap()
        pressed = games.nth(index).get_attribute("aria-pressed")
        check(pressed == "true", f"{device}: game {index} not chosen by a tap")
        place = page.evaluate(TAP_MOVED)
        check(
            abs(place["moved"]) <= 1 or place["scrolled"] == 0,
            f"{device}: game {index} moved after its tap: {place}",
        )


def ha_post(path: str, data: dict, form: bool = False) -> dict:
    """POST to Home Assistant's API without a token, as its login page does: JSON, or
    the fields of a form."""
    if form:
        body, kind = urllib.parse.urlencode(data).encode(), "x-www-form-urlencoded"
    else:
        body, kind = json.dumps(data).encode(), "json"
    request = urllib.request.Request(
        f"{HA}{path}",
        data=body,
        headers={"Content-Type": f"application/{kind}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def signed_in_before() -> dict:
    """The storage of a browser that signed in to the demo before, for the storage_state
    of a new context: the tokens of the frontend, which keeps them in the local storage
    of Home Assistant's address. The demo trusts the network of the test and has one
    user, so its login flow gives that user's tokens without a form, as the login page
    of a new browser gets them."""
    flow = ha_post(
        "/auth/login_flow",
        {
            "client_id": CLIENT_ID,
            "handler": ["trusted_networks", None],
            "redirect_uri": f"{CLIENT_ID}?auth_callback=1",
        },
    )
    check(
        flow.get("type") == "create_entry",
        f"The demo's login flow wants more than its trusted network: {flow}",
    )
    tokens = ha_post(
        "/auth/token",
        {
            "grant_type": "authorization_code",
            "code": flow["result"],
            "client_id": CLIENT_ID,
        },
        form=True,
    )
    stored = {
        **tokens,
        "hassUrl": HA,
        "clientId": CLIENT_ID,
        # In milliseconds, as the frontend writes it.
        "expires": round((time.time() + tokens["expires_in"]) * 1000),
    }
    return {
        "cookies": [],
        "origins": [
            {
                "origin": HA,
                "localStorage": [{"name": "hassTokens", "value": json.dumps(stored)}],
            }
        ],
    }


def safari(playwright: Playwright) -> None:
    """The automatic dashboard in an iPhone's Safari whose cards load slowly, which
    showed "Timeout waiting for strategy element" instead; and its new game screen, which
    scrolled the page to its top when a tap drew the screen anew: a game far down stays
    where it was tapped."""
    step = "Safari on an iPhone, WebKit"
    timeline = Timeline()
    browser = playwright.webkit.launch()
    try:
        # A phone that opened Home Assistant before: its Safari keeps the tokens of
        # the frontend and shows the dashboard on the first load. A Safari that signed
        # in during the step loaded the page a second time, from the login page, and
        # its WebKit now and then never finished the way back from the login page
        # (page.goto ran out of time) or was still loading when the step reloaded
        # the page for the slow cards (WebKit encountered an internal error).
        context = browser.new_context(
            **playwright.devices["iPhone 13"],
            locale="de-DE",
            storage_state=signed_in_before(),
        )
        # Kept only when the step fails, for Playwright's trace viewer. Its snapshot
        # of the page at every action costs next to nothing; a film of the screen
        # would cost about two seconds.
        context.tracing.start(snapshots=True)
        page = context.new_page()
        page.add_init_script(CAPTURE_ERRORS)
        timeline.follow(page)
        card = "homedarts-scoreboard-card"

        # With an empty cache on slow Wi-Fi: the cards come after Home Assistant
        # stopped waiting for the strategy, which registered on its own. The request
        # is held and let go, not answered after a sleep in the route: a sleep stops
        # Playwright, and every further request would wait for it.
        held: list[Route] = []

        # A function of its own: the sync API takes no built-in such as held.append.
        def hold(route: Route) -> None:
            held.append(route)

        page.route(CARD_MODULE, hold)
        # Only until the page is there: its load waits for the held module.
        page.goto(f"{HA}/homedarts-auto/scoreboard", wait_until="commit")
        page.wait_for_timeout(CARD_MODULE_DELAY * 1000)
        check(
            "/auth/" not in page.url,
            f"The stored tokens didn't sign Safari in, it shows {page.url}",
        )
        timeline.note(f"lets {len(held)} held request(s) go")
        # Once: the strategy's import finds the module that Home Assistant loads.
        check(
            len(held) == 1,
            f"homedarts-card.js loaded {len(held)} times instead of once",
        )
        for route in held:
            route.continue_()
        # Removed only now: Playwright counts the held requests of a removed route as
        # handled, and letting them go then fails.
        page.unroute(CARD_MODULE)
        page.locator(f"{card} .main").wait_for(timeout=60000)
        timeline.note("scoreboard shown")
        page.evaluate(
            CALL_SERVICE,
            ["select", "select_option", "practice_game", {"option": "off"}],
        )
        control({"status": "Throw", "event": "Takeout finished", "throws": []})
        page.locator(f"{card} .lobby-cta").tap()
        page.locator(f"{card} .lobby").wait_for(timeout=15000)
        steady_games(page, "iPhone with Safari", card)
        page.locator(f"{card} [data-lobby='close']").tap()
        errors = page_errors(page, [])
        check(not errors, f"Console problems: {errors}")
    except Exception:
        # The pages of this browser, which the screenshots of main() don't see.
        keep_screenshots(browser, step)
        keep_trace(browser, step, timeline)
        raise
    finally:
        browser.close()


def touch_screens(browser: Browser) -> None:
    """The scoreboard, the new game screen, the keypad and the training card on phones
    and a touch monitor, driven by taps, in German with its long words."""
    for device, size, insets in TOUCH_SCREENS:
        touch_screen(browser, device, size, insets)


def touch_screen(
    browser: Browser, device: str, size: dict[str, int], insets: tuple[int, int]
) -> None:
    phone = size["width"] < 1000
    context = browser.new_context(
        locale="de-DE",
        viewport=size,
        device_scale_factor=3 if phone else 1,
        is_mobile=phone,
        has_touch=True,
    )
    probe(context)
    page = context.new_page()
    page.add_init_script(CAPTURE_ERRORS)
    page.add_init_script(phone_style(*insets))
    card = "homedarts-scoreboard-card"

    def fits(screen: str, targets: bool = True, high: bool = True) -> None:
        """Nothing wider than the screen, every control big enough for a finger, and a
        scoreboard one screen high above the home indicator; the new game screen
        scrolls instead."""
        layout = page.evaluate(TABLET_LAYOUT)
        check(
            layout["width"] <= layout["room"] + 1
            and layout["right"] <= layout["viewport"] + 1,
            f"{device}: {screen} is wider than the screen: {layout}",
        )
        check(not targets or layout["targets"], f"{device}: {screen} has no targets")
        check(
            not layout["small"],
            f"{device}: {screen}: targets below 44 px {layout['small']}",
        )
        fit = page.evaluate(PHONE_FIT)
        check(
            not high
            or (fit["bottom"] <= fit["free"] + 1 and fit["height"] <= fit["room"] + 1),
            f"{device}: {screen} runs below the screen: {fit}",
        )

    def start_bar(screen: str, buttons: list[str]) -> None:
        bar = page.evaluate(START_BAR)
        check(bar["sticky"] == "sticky", f"{device}: {screen}: the bar scrolls away")
        # The card's colour over the page's: nothing shines through a see-through card.
        check(
            "gradient" in bar["layers"] and not bar["base"].startswith("rgba("),
            f"{device}: {screen}: the bar shows what scrolls beneath it: {bar}",
        )
        check(
            max(bar["edges"]) <= 1,
            f"{device}: {screen}: the bar does not span the card: {bar}",
        )
        check(
            bar["start"][0] >= 0 and bar["start"][1] <= bar["free"] + 1,
            f"{device}: {screen}: the start is out of reach: {bar}",
        )
        check(
            bar["buttons"] == buttons, f"{device}: {screen}: buttons {bar['buttons']}"
        )

    def wide(view: str) -> None:
        state = page.evaluate(PHONE_WIDTH)
        check(state["cards"], f"{device}: no cards in the {view} view")
        check(
            not state["wide"], f"{device}: {view} view wider than the screen: {state}"
        )
        check(not state["cut"], f"{device}: {view} view cuts names short: {state}")

    def wait_players(count: int) -> None:
        page.wait_for_function(
            f"() => ({SCOREBOARD_STATE})().players.length === {count}", timeout=15000
        )

    def game_off() -> None:
        page.evaluate(
            CALL_SERVICE,
            ["select", "select_option", "practice_game", {"option": "off"}],
        )
        control({"status": "Throw", "event": "Takeout finished", "throws": []})

    page.goto(f"{HA}/homedarts-auto/scoreboard")
    page.locator(f"{card} .main").wait_for(timeout=30000)
    game_off()
    page.locator(f"{card} .lobby-cta").wait_for(timeout=15000)
    fits("the scoreboard between games")

    # The new game screen with the detection stopped, as at the board after a break:
    # its hint and the start stay above the home indicator on a bar of their own, and
    # every game can be tapped, none hides beneath the bar.
    control({"running": False, "status": "Stopped", "event": "Stopped"})
    page.locator(f"{card} .lobby-cta").tap()
    page.locator(f"{card} .lobby").wait_for(timeout=15000)
    page.locator(f"{card} .lobby-hint").first.wait_for(timeout=15000)
    fits("the new game screen", high=False)
    start_bar("the new game screen", ["close", "start"])
    steady_games(page, device, card)
    players = page.locator(f"{card} .lobby-player [data-lobby='remove']")
    while players.count():
        players.first.tap()
    for name in ("Alex", "Sam"):
        page.locator(f"{card} .suggestion", has_text=name).tap()
    page.locator(f"{card} .lobby .game", has_text="301").first.tap()
    page.locator(f"{card} .lobby .start").tap()
    wait_players(2)
    control({"event": "Throw detected", "throws": [T20]})
    fits("a match of two", targets=False)

    # A running game adds its end to the bar; two taps end it.
    page.locator(f"{card} .lobby-toggle").tap()
    page.locator(f"{card} .lobby").wait_for(timeout=15000)
    start_bar("the new game screen during a game", ["end", "close", "start"])
    end = page.locator(f"{card} [data-lobby='end']")
    end.tap()
    end.tap()
    page.wait_for_function(
        f"() => !({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector(\"[data-lobby='end']\")",
        timeout=15000,
    )
    page.locator(f"{card} [data-lobby='close']").tap()
    control({"status": "Throw", "event": "Takeout finished", "throws": []})

    # Four players with long names, in X01 and in Cricket.
    for game in ("501", "cricket"):
        page.evaluate(
            CALL_ACTION, ["start_game", {"game": game, "players": LONG_NAMES}]
        )
        if game == "501":
            wait_players(4)
        else:
            page.locator(f"{card} .cricket").wait_for(timeout=15000)
        control({"event": "Throw detected", "throws": [T20, SINGLE_20]})
        fits(f"four players with long names in {game}", targets=False)
        control({"status": "Throw", "event": "Takeout finished", "throws": []})
    game_off()

    # The keypad and its board, which opens whole for darts entered by hand: two
    # fingers zoom in, and a finger slides with the loupe from the single 20 to the
    # treble 20 and enters it where it lets go. The keypad is a choice of the card; the
    # demo's keypad view has it.
    page.goto(f"{HA}/homedarts-demo/keypad")
    page.locator(f"{card} .main").wait_for(timeout=30000)
    page.evaluate(CALL_SERVICE, ["switch", "turn_on", "practice_manual_entry"])
    page.evaluate(CALL_ACTION, ["start_game", {"game": "301", "players": ["Alex"]}])
    page.locator(f"{card} .pad").wait_for(timeout=15000)
    fits("the keypad")
    page.locator(f"{card} [data-pad='board']").tap()
    board = page.locator(f"{card} .pad-board")
    board.wait_for(timeout=15000)
    fits("the board to tap")
    view = board.evaluate(BOARD_VIEW)
    check(view["size"] == 460, f"{device}: the keypad's board opens zoomed in: {view}")
    middle = board_point(view, (0, 0))
    fingers(
        page,
        [(middle[0] - 20, middle[1]), (middle[0] - 40, middle[1])],
        [(middle[0] + 20, middle[1]), (middle[0] + 40, middle[1])],
    )
    zoomed = board.evaluate(BOARD_VIEW)
    check(zoomed["size"] < 300, f"{device}: two fingers did not zoom in: {zoomed}")
    problems = page.evaluate(PAD_PROBLEMS)
    check(not problems, f"{device}: the board zoomed in spoils the pad: {problems}")
    shown = fingers(
        page, [board_point(zoomed, SINGLE_20_SPOT), board_point(zoomed, TREBLE_20_SPOT)]
    )
    check(shown, f"{device}: no loupe while aiming")
    page.wait_for_function(
        f"() => ({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector('.sum .value')?.textContent === '60'",
        timeout=15000,
    )
    page.evaluate(CALL_SERVICE, ["switch", "turn_off", "practice_manual_entry"])
    game_off()

    # A dart the board read wrong: on a small screen its board opens zoomed in on where the
    # board saw it, and a tap on the treble 20 corrects it.
    page.evaluate(CALL_ACTION, ["start_game", {"game": "301", "players": ["Alex"]}])
    control({"event": "Throw detected", "throws": [T20, SINGLE_20]})
    # The game has booked both darts before a finger picks the second one.
    page.wait_for_function(
        f"""() => {{
          const state = ({SCOREBOARD_STATE})();
          return state.darts.join() === 'T20,S20,–' && state.players[0]?.[1] === '221';
        }}""",
        timeout=15000,
    )
    page.locator(f"{card} [data-dart='2']").tap()
    board.wait_for(timeout=15000)
    view = board.evaluate(BOARD_VIEW)
    # A small screen: a narrow card, or a low screen as a phone on its side.
    small = min(size["width"], size["height"]) < 600
    check(
        (view["size"] < 460) == small,
        f"{device}: the board of a correction opens {view['size']} mm wide",
    )
    problems = page.evaluate(PAD_PROBLEMS)
    check(
        not problems, f"{device}: the board of a correction spoils the pad: {problems}"
    )
    x, y = board_point(view, TREBLE_20_SPOT)
    page.touchscreen.tap(x, y)
    page.wait_for_function(
        f"() => ({SCOREBOARD_STATE})().darts[1] === 'T20'", timeout=15000
    )
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    game_off()

    # The other views: every card as wide as the screen, the tiles' names whole, once
    # the view before has faded out and what the cards show has arrived.
    for view in ("live", "training", "players"):
        show(page, f"{HA}/homedarts-auto/{view}")
        settle(page, scope="page")
        wide(view)
    # What a mouse sees as a tooltip, a finger sees in a bubble over the card.
    show(page, f"{HA}/homedarts-auto/live")
    page.wait_for_function(
        f"() => ({CARDS})()[0]?.shadowRoot?.querySelector('.recent-visit')",
        timeout=30000,
    )
    # The view before fades out above the card for a moment and would take the tap.
    settle(page, scope="page")
    spot = page.evaluate(RECENT_VISIT_SPOT)
    page.touchscreen.tap(*spot)
    try:
        page.wait_for_function(f"() => ({HINT_SHOWN})().shown", timeout=15000)
    except PlaywrightTimeout:
        pass  # The check below names the screen and what the hint shows instead.
    hint = page.evaluate(HINT_SHOWN)
    check(
        hint["shown"] and hint["inside"] and hint["text"] == hint["title"],
        f"{device}: the hint of a last visit {hint}",
    )
    errors = page_errors(page, [])
    check(not errors, f"{device}: console problems: {errors}")
    context.close()


# The middle of the live card's first last visit, in sight.
RECENT_VISIT_SPOT = f"""
() => {{
  const visit = ({CARDS})()[0].shadowRoot.querySelector('.recent-visit');
  visit.scrollIntoView({{ block: 'center' }});
  const box = visit.getBoundingClientRect();
  return [box.x + box.width / 2, box.y + box.height / 2];
}}
"""
# The hint after a tap on that visit: shown with its title, inside the card and the screen.
HINT_SHOWN = f"""
() => {{
  const root = ({CARDS})()[0].shadowRoot;
  const bubble = root.querySelector('.hint-bubble');
  const card = root.querySelector('ha-card').getBoundingClientRect();
  const box = bubble?.getBoundingClientRect();
  return {{
    shown: Boolean(bubble && !bubble.hidden),
    text: bubble?.textContent ?? null,
    title: root.querySelector('.recent-visit').getAttribute('title'),
    inside: Boolean(box) && box.left >= Math.max(card.left, 0) - 1 && box.right <= Math.min(card.right, innerWidth) + 1
      && box.top >= card.top - 1 && box.bottom <= card.bottom + 1,
  }};
}}
"""


# Every size a dashboard is opened on, in both orientations: its viewport, the safe
# areas at the top and the bottom, and whether it is a touch screen.
SCREENS = (
    ("small phone", {"width": 360, "height": 640}, (0, 0), True),
    ("small phone on its side", {"width": 640, "height": 360}, (0, 0), True),
    ("iPhone", {"width": 393, "height": 852}, (59, 34), True),
    ("iPhone on its side", {"width": 852, "height": 393}, (0, 21), True),
    ("tablet", {"width": 768, "height": 1024}, (24, 20), True),
    ("tablet on its side", {"width": 1024, "height": 768}, (24, 20), True),
    ("laptop", {"width": 1280, "height": 800}, (0, 0), False),
    # Many players have a 24 or 27 inch touch screen beside the board.
    ("24-inch touch monitor", {"width": 1920, "height": 1080}, (0, 0), True),
    ("27-inch touch monitor", {"width": 2560, "height": 1440}, (0, 0), True),
)
# Screens narrower than this are phones held upright.
UPRIGHT_PHONE_WIDTH = 500
# The languages of the cards besides German, whose words take other room.
OTHER_LOCALES = ("en-US", "es-ES", "fr-FR", "nl-NL")
# The views of the generated dashboard; those of the demo dashboard are read from it.
AUTO_VIEWS = ("live", "scoreboard", "training", "players", "board")
DEMO_VIEWS = """
async () => {
  const hass = document.querySelector('home-assistant').hass;
  const config = await hass.callWS({ type: 'lovelace/config', url_path: 'homedarts-demo' });
  return config.views.map((view) => view.path);
}
"""
# What a player would see as broken on this screen, card by card: a card wider than the
# screen, text cut short or cut off, text on top of other text or running over the edge
# of its tile or button, a row of buttons running over its edge, text too small to read,
# a control too small for a finger on a touch screen, and a full-height scoreboard
# running below the screen.
# Text beneath a bar that stays in place is hidden by it and does not count as covered.
LAYOUT_PROBLEMS = """
(touch) => {
  const cards = [];
  (function collect(root) {
    root.querySelectorAll('*').forEach((el) => {
      if (el.tagName.startsWith('HOMEDARTS-') && !el.tagName.endsWith('-EDITOR') && el.shadowRoot) cards.push(el);
      if (el.shadowRoot) collect(el.shadowRoot);
    });
  })(document);
  const problems = [];
  const inset = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue('--safe-area-inset-bottom')
  ) || 0;
  // Shown on the screen: not hidden, and not only for screen readers.
  const shown = (el, frame) => {
    for (let e = el; e && e !== frame.parentNode; e = e.parentElement) {
      if (e.hidden) return false;
      const style = getComputedStyle(e);
      if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return false;
      if (style.clipPath === 'inset(50%)') return false;
    }
    return true;
  };
  const within = (a, b) => ({
    left: Math.max(a.left, b.left), top: Math.max(a.top, b.top),
    right: Math.min(a.right, b.right), bottom: Math.min(a.bottom, b.bottom),
  });
  const area = (r) => Math.max(0, r.right - r.left) * Math.max(0, r.bottom - r.top);
  const words = (el) => el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 40);
  // The tile or button a text sits in: the nearest element with a frame or a fill that
  // shows; a button plain as text has no edge to run over.
  const boxOf = (el, frame) => {
    for (let e = el; e && e !== frame; e = e.parentElement) {
      const style = getComputedStyle(e);
      const fill = style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent';
      const border = parseFloat(style.borderLeftWidth) > 0 && style.borderLeftStyle !== 'none'
        && !style.borderLeftColor.endsWith(', 0)') && style.borderLeftColor !== 'transparent';
      if (border || fill) return e;
    }
    return null;
  };
  for (const card of cards) {
    const root = card.shadowRoot;
    const frame = root.querySelector('ha-card');
    if (!frame) continue;
    const box = card.getBoundingClientRect();
    if (box.width === 0 || box.height === 0) continue;
    const label = card.tagName.toLowerCase();
    if (frame.scrollWidth > frame.clientWidth + 1 || box.right > innerWidth + 1 || box.left < -1) {
      problems.push(`${label} is wider than the screen (${frame.scrollWidth}/${frame.clientWidth}, right ${Math.round(box.right)} of ${innerWidth})`);
    }
    // The part of a text the overflow of its element and their ancestors leaves visible,
    // and whether one cuts it off without letting it scroll.
    // Glyph boxes stand a little above and below a tight line; only a text cut at its
    // side or a line lost as a whole counts.
    const clip = (el, rect) => {
      let visible = rect;
      let cut = false;
      for (let e = el; e && e !== frame.parentNode; e = e.parentElement) {
        const style = getComputedStyle(e);
        if (style.overflowX === 'visible' && style.overflowY === 'visible') continue;
        const next = within(visible, e.getBoundingClientRect());
        const scrolls = /auto|scroll/.test(style.overflowX + style.overflowY);
        const narrower = next.right - next.left < visible.right - visible.left - 2;
        const lower = next.bottom - next.top < (visible.bottom - visible.top) * 0.6;
        if (!scrolls && (narrower || lower)) cut = true;
        visible = next;
      }
      return { visible, cut };
    };
    const texts = [];
    const range = document.createRange();
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const el = node.parentElement;
      if (!el || !node.textContent.trim() || el.closest('svg, style, script')) continue;
      if (!shown(el, frame)) continue;
      const style = getComputedStyle(el);
      // Text only for screen readers.
      if (style.clipPath === 'inset(50%)' || style.clip === 'rect(0px, 0px, 0px, 0px)') continue;
      if (parseFloat(style.fontSize) < 11) {
        problems.push(`${label}: "${words(el)}" is ${style.fontSize}, too small to read`);
      }
      const tile = boxOf(el, frame)?.getBoundingClientRect();
      range.selectNodeContents(node);
      for (const rect of range.getClientRects()) {
        if (rect.width < 2 || rect.height < 2) continue;
        const { visible, cut } = clip(el, rect);
        if (cut && style.textOverflow !== 'ellipsis') problems.push(`${label}: "${words(el)}" is cut off`);
        if (tile && (rect.left < tile.left + 1 || rect.right > tile.right - 1)) {
          problems.push(`${label}: "${words(el)}" runs over the edge of its box`);
        }
        if (area(visible) < 4) continue;
        // The glyphs fill the middle of a text's box; large numbers have a box much
        // higher than what they show.
        const inner = (visible.bottom - visible.top) * 0.2;
        const core = { ...visible, top: visible.top + inner, bottom: visible.bottom - inner };
        texts.push({ el, rect: core, fixed: Boolean(el.closest('.lobby-actions')) });
      }
    }
    for (const el of root.querySelectorAll('*')) {
      if (!shown(el, frame)) continue;
      const style = getComputedStyle(el);
      if (style.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1 && el.textContent.trim()) {
        problems.push(`${label}: "${words(el)}" is cut short`);
      }
    }
    // A row that wraps has room for each of its items; one running over its edge cannot
    // wrap, as buttons and a status that keep to a row wider than the card.
    for (const row of root.querySelectorAll('*')) {
      const style = getComputedStyle(row);
      if (!style.display.endsWith('flex') || style.flexWrap === 'nowrap' || style.flexDirection.startsWith('column')) continue;
      if (/auto|scroll/.test(style.overflowX) || !shown(row, frame)) continue;
      const rect = row.getBoundingClientRect();
      const left = rect.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft);
      const right = rect.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight);
      for (const item of row.children) {
        if (!shown(item, frame) || /absolute|fixed/.test(getComputedStyle(item).position)) continue;
        const edges = item.getBoundingClientRect();
        if (edges.width > 0 && (edges.left < left - 1 || edges.right > right + 1)) {
          problems.push(`${label}: "${words(item) || item.className}" runs out of its row`);
        }
      }
    }
    for (let i = 0; i < texts.length; i += 1) {
      for (let j = i + 1; j < texts.length; j += 1) {
        const a = texts[i];
        const b = texts[j];
        if (a.el === b.el || a.el.contains(b.el) || b.el.contains(a.el) || a.fixed !== b.fixed) continue;
        const both = within(a.rect, b.rect);
        if (both.right - both.left > 3 && both.bottom - both.top > 3) {
          problems.push(`${label}: "${words(a.el)}" lies on "${words(b.el)}"`);
        }
      }
    }
    if (touch) {
      for (const el of root.querySelectorAll('button, input, select, textarea, a[href], [role="button"], [role="tab"], [tabindex="0"]')) {
        if (!shown(el, frame) || el.closest('svg') || el.type === 'hidden') continue;
        const rect = el.getBoundingClientRect();
        // Controls only a keyboard reaches until they have the focus.
        if (rect.width <= 2 || rect.height <= 2 || getComputedStyle(el).clipPath === 'inset(50%)') continue;
        if (rect.height < 40 || rect.width < 40) {
          problems.push(`${label}: "${words(el) || el.getAttribute('aria-label') || el.tagName.toLowerCase()}" is ${Math.round(rect.width)}x${Math.round(rect.height)} for a finger`);
        }
      }
    }
    const board = root.querySelector('.scoreboard.full:not(.choosing)');
    if (board && box.bottom > innerHeight - inset + 1) {
      problems.push(`${label} runs ${Math.round(box.bottom - innerHeight + inset)} px below the screen`);
    }
  }
  return { cards: cards.length, problems: [...new Set(problems)] };
}
"""
# Screenshots of every screen for a look by eye, when BROWSER_SCREENSHOTS is set.
SCREENSHOTS = os.environ.get("BROWSER_SCREENSHOTS", "")


def screens(browser: Browser) -> None:
    """Every view of both dashboards and the scoreboard's screens on every size, in
    German with its long words, and on a phone the scoreboard during a game in the
    other languages: nothing broken, whatever the screen and its side. The screens are
    open side by side and go through every view and every game together."""
    # A choice of screens for a local run, comma-separated, such as "iPhone".
    chosen = {
        name.strip() for name in os.environ.get("BROWSER_SCREENS", "").split(",")
    } - {""}
    sizes = [size for size in SCREENS if not chosen or size[0] in chosen]
    unknown = chosen - {size[0] for size in SCREENS}
    check(not unknown, f"BROWSER_SCREENS names no screen: {sorted(unknown)}")
    opened = [Screen(browser, *size) for size in sizes]
    screen_views(opened)
    for screen in opened:
        screen.close()
    phones = [
        Screen(browser, name, size, insets, touch, locale)
        for name, size, insets, touch in sizes
        if touch and size["width"] < UPRIGHT_PHONE_WIDTH
        for locale in OTHER_LOCALES
    ]
    if phones:
        phone_languages(phones)
    found: list[str] = []
    for screen in opened:
        problems = screen.problems + [
            problem
            for phone in phones
            if phone.name == screen.name
            for problem in phone.problems
        ]
        print(f"  {screen.name}: {len(problems)} problems", flush=True)
        found += problems
    check(not found, "Layout problems:\n" + "\n".join(found))


def screen_page(
    browser: Browser,
    size: dict[str, int],
    insets: tuple[int, int],
    touch: bool,
    locale: str = "de-DE",
) -> tuple[BrowserContext, Page]:
    context = browser.new_context(
        locale=locale,
        viewport=size,
        device_scale_factor=2,
        is_mobile=touch and size["width"] < 1000,
        has_touch=touch,
    )
    probe(context)
    page = context.new_page()
    page.add_init_script(CAPTURE_ERRORS)
    page.add_init_script(phone_style(*insets))
    return context, page


def screen_problems(page: Page, screen: str, name: str, touch: bool) -> list[str]:
    """What is broken in the view on this page, which has settled, and its screenshot
    when wanted."""
    state = page.evaluate(LAYOUT_PROBLEMS, touch)
    if SCREENSHOTS and ARTIFACTS:
        folder = Path(ARTIFACTS) / "screens" / screen.replace(" ", "-")
        folder.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(folder / f"{name}.png"), full_page=True)
    return [f"{screen} · {name}: {problem}" for problem in state["problems"]]


class Screen:
    """A screen size in a browser context of its own, with its page and what is broken
    on it."""

    def __init__(
        self,
        browser: Browser,
        name: str,
        size: dict[str, int],
        insets: tuple[int, int],
        touch: bool,
        locale: str = "de-DE",
    ) -> None:
        self.name = name
        self.touch = touch
        self.locale = locale
        self.context, self.page = screen_page(browser, size, insets, touch, locale)
        self.problems: list[str] = []

    def look(self, view: str) -> None:
        """Note what is broken in the view this screen shows."""
        self.problems += screen_problems(self.page, self.name, view, self.touch)

    def close(self) -> None:
        """Note the console problems of the page and close it."""
        where = self.name if self.locale == "de-DE" else f"{self.name} · {self.locale}"
        self.problems.extend(
            f"{where}: console problem {error}" for error in page_errors(self.page, [])
        )
        self.context.close()


def look(screens: list[Screen], view: str) -> None:
    """Note what is broken in the view on every screen, once each has settled."""
    settle(*[screen.page for screen in screens])
    for screen in screens:
        screen.look(view)


def pulled(pages: list[Page]) -> None:
    """The darts are pulled and the board throws again, which every page shows."""
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    expect_state(pages, {"local_status": "throw", "num_throws": "0"})


def thrown(pages: list[Page], darts: list[dict]) -> None:
    """Darts on the board after a takeout, which every page shows."""
    control({"event": "Throw detected", "throws": darts})
    expect_state(pages, {"num_throws": str(len(darts))})


def scoreboard_in_game(pages: list[Page]) -> None:
    """The scoreboard of the demo, not full height, during a practice game: the new
    game button and the caller beside the status, which reads "ready"."""
    show(pages, f"{HA}/homedarts-demo/scoreboard")
    pages[0].evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "301"}]
    )
    pulled(pages)
    root = f"({SCOREBOARD_CARDS})()[0].shadowRoot"
    wait_for(
        pages,
        f"() => !{root}.querySelector('.lobby-toggle').hidden"
        f" && {root}.querySelector('.caller-toggle')",
    )


def phone_languages(phones: list[Screen]) -> None:
    """The scoreboard during a game on the phones in the other languages: its buttons
    and status take a width of their own in each."""
    pages = [phone.page for phone in phones]
    scoreboard_in_game(pages)
    settle(*pages)
    for phone in phones:
        phone.look(f"scoreboard-during-a-game-{phone.locale}")
    # The next step finds the board between games, as it was.
    pages[0].evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "off"}]
    )
    pulled(pages)
    for phone in phones:
        phone.close()


def screen_views(screens: list[Screen]) -> None:
    """Every view and the scoreboard's own screens on every screen at once: the board
    plays each game once, and every screen shows it."""
    pages = [screen.page for screen in screens]
    first = pages[0]
    root = f"({SCOREBOARD_CARDS})()[0].shadowRoot"

    def click(selector: str) -> None:
        """A tap of the scoreboard's own, on every screen."""
        for page in pages:
            page.evaluate(f"() => {root}.querySelector({selector!r}).click()")

    def pad_problems(view: str) -> None:
        for screen in screens:
            screen.problems.extend(
                f"{screen.name} · {view}: {problem}"
                for problem in screen.page.evaluate(PAD_PROBLEMS)
            )

    show(pages, f"{HA}/homedarts-auto/live")
    views = [f"homedarts-auto/{view}" for view in AUTO_VIEWS]
    views += [f"homedarts-demo/{view}" for view in first.evaluate(DEMO_VIEWS)]
    for view in views:
        show(pages, f"{HA}/{view}")
        look(screens, view.replace("/", "-"))

    # The views show the scoreboard between games; during one, the new game button
    # and the caller stand beside the status.
    scoreboard_in_game(pages)
    look(screens, "scoreboard-during-a-game")

    # The scoreboard's own screens: the new game screen, four players with long names
    # and the keypad, its board to tap, and Cricket for four.
    show(pages, f"{HA}/homedarts-auto/scoreboard")
    first.evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "off"}]
    )
    pulled(pages)
    wait_for(pages, f"() => {root}.querySelector('.lobby-cta')")
    click(".lobby-cta")
    wait_for(pages, f"() => {root}.querySelector('.lobby')")
    look(screens, "scoreboard-new-game")
    click("[data-lobby='close']")
    # The keypad is a choice of the card; the demo's keypad view has it.
    show(pages, f"{HA}/homedarts-demo/keypad")
    first.evaluate(CALL_SERVICE, ["switch", "turn_on", "practice_manual_entry"])
    first.evaluate(CALL_ACTION, ["start_game", {"game": "501", "players": LONG_NAMES}])
    wait_for(pages, f"() => {root}.querySelector('.pad')")
    thrown(pages, [T20, SINGLE_20])
    look(screens, "scoreboard-keypad-four-players")
    click("[data-pad='board']")
    wait_for(pages, f"() => {root}.querySelector('.pad-board')")
    look(screens, "scoreboard-board-to-tap")
    pad_problems("scoreboard-board-to-tap")
    first.evaluate(CALL_SERVICE, ["switch", "turn_off", "practice_manual_entry"])
    pulled(pages)
    # A dart the board read wrong and the board to correct it: zoomed in on where the
    # board saw it on a small screen, whole on a large one.
    first.evaluate(CALL_ACTION, ["start_game", {"game": "301", "players": ["Alex"]}])
    control({"event": "Throw detected", "throws": [T20, SINGLE_20]})
    wait_for(pages, f"() => ({SCOREBOARD_STATE})().darts.join() === 'T20,S20,–'")
    click("[data-dart='2']")
    wait_for(pages, f"() => {root}.querySelector('.pad-board')")
    look(screens, "scoreboard-correction-board")
    pad_problems("scoreboard-correction-board")
    pulled(pages)
    first.evaluate(
        CALL_ACTION, ["start_game", {"game": "cricket", "players": LONG_NAMES}]
    )
    wait_for(pages, f"() => {root}.querySelector('.cricket')")
    thrown(pages, [T20, SINGLE_20])
    look(screens, "scoreboard-cricket-four-players")
    first.evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "off"}]
    )
    pulled(pages)


# Accessibility -----------------------------------------------------------------------

# axe-core of package.json (npm ci), the engine of browser accessibility checks.
AXE = Path(__file__).resolve().parents[2] / "node_modules" / "axe-core" / "axe.min.js"
# Violations of the cards that are accepted for now, each with its reason.
AXE_BASELINE = Path(__file__).resolve().parent / "accessibility-baseline.toml"
# The rules of WCAG 2.1 at levels A and AA.
WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
# A violation of these fails the step; lesser ones are listed.
FAILING = ("serious", "critical")
# Desktop and phone, as players use them, in both themes.
ACCESSIBILITY_SCREENS = (
    ("laptop", {"width": 1280, "height": 800}, False, "dark"),
    ("laptop, light theme", {"width": 1280, "height": 800}, False, "light"),
    ("iPhone", {"width": 393, "height": 852}, True, "dark"),
    ("iPhone, light theme", {"width": 393, "height": 852}, True, "light"),
)
# axe-core over every card on the page, each with its shadow root, for WCAG 2.1 AA.
AXE_CARDS = """
async (tags) => {
  const cards = [];
  (function collect(root) {
    root.querySelectorAll('*').forEach((el) => {
      if (el.tagName.startsWith('HOMEDARTS-') && !el.tagName.endsWith('-EDITOR') && el.shadowRoot) cards.push(el);
      if (el.shadowRoot) collect(el.shadowRoot);
    });
  })(document);
  const found = [];
  for (const card of cards) {
    const result = await axe.run(card, {
      runOnly: { type: 'tag', values: tags },
      resultTypes: ['violations'],
    });
    for (const violation of result.violations) {
      for (const node of violation.nodes) {
        const path = node.target.flat();
        found.push({
          card: card.tagName.toLowerCase(),
          rule: violation.id,
          impact: node.impact || violation.impact,
          target: path[path.length - 1],
          html: node.html.slice(0, 120),
          summary: (node.failureSummary || violation.help).replace(/\\s+/g, ' ').slice(0, 240),
        });
      }
    }
  }
  return found;
}
"""


def accepted_violations() -> list[dict[str, str]]:
    """The accepted violations: a rule of a card, where its selector names the target."""
    entries = tomllib.loads(AXE_BASELINE.read_text(encoding="utf-8")).get(
        "accepted", []
    )
    for entry in entries:
        check(
            set(entry) == {"rule", "card", "target", "reason"}
            and entry["reason"].strip(),
            f"{AXE_BASELINE.name}: every entry names rule, card, target and its reason",
        )
    return entries


def accessibility(browser: Browser) -> None:
    """axe-core over every card view of both dashboards and the scoreboard's screens,
    on a laptop and a phone in both themes: no serious or critical violation of
    WCAG 2.1 AA beyond the accepted ones of accessibility-baseline.toml."""
    check(AXE.exists(), f"{AXE} is missing; npm ci installs axe-core")
    accepted = accepted_violations()
    used: set[int] = set()
    failing: list[str] = []
    lesser: set[str] = set()
    report: dict[str, list] = {"scanned": [], "violations": []}
    for screen, view, violations in accessibility_views(browser):
        report["scanned"].append(f"{screen} · {view}")
        for violation in violations:
            report["violations"].append({"screen": screen, "view": view, **violation})
            line = (
                f"{violation['card']} · {violation['rule']} ({violation['impact']}): "
                f"{violation['target']} {violation['summary']}"
            )
            matches = [
                index
                for index, entry in enumerate(accepted)
                if entry["rule"] == violation["rule"]
                and entry["card"] == violation["card"]
                and entry["target"] in violation["target"]
            ]
            used.update(matches)
            if matches:
                continue
            if violation["impact"] in FAILING:
                failing.append(f"{screen} · {view} · {line}")
            else:
                lesser.add(line)
    print(f"  {len(report['scanned'])} views checked", flush=True)
    if ARTIFACTS:
        Path(ARTIFACTS, "accessibility.json").write_text(json.dumps(report, indent=1))
    for line in sorted(lesser):
        print(f"  moderate or minor: {line}", flush=True)
    for index, entry in enumerate(accepted):
        if index not in used:
            print(
                f"  {AXE_BASELINE.name}: {entry['card']} {entry['rule']} {entry['target']}"
                " no longer occurs; remove it",
                flush=True,
            )
    check(not failing, "Accessibility violations:\n" + "\n".join(failing))


# Starts axe-core over the cards of the page; its violations, or why it failed, come
# into window.__axeFound, so that the scans of several pages run at the same time.
START_AXE = f"""
(tags) => {{
  window.__axeFound = null;
  ({AXE_CARDS})(tags).then(
    (violations) => {{ window.__axeFound = {{ violations }}; }},
    (error) => {{ window.__axeFound = {{ error: String(error) }}; }},
  );
}}
"""


def accessibility_views(browser: Browser) -> list[tuple[str, str, list[dict]]]:
    """The violations of every card view, and of the scoreboard's own screens, on every
    screen and theme: all of them open at once, the board playing each game once."""
    opened: list[tuple[str, Page]] = []
    for screen, size, touch, scheme in ACCESSIBILITY_SCREENS:
        context = browser.new_context(
            locale="en-US",
            viewport=size,
            device_scale_factor=2 if touch else 1,
            is_mobile=touch,
            has_touch=touch,
            color_scheme=scheme,
        )
        probe(context)
        opened.append((screen, context.new_page()))
    pages = [page for _, page in opened]
    first = pages[0]
    axe = AXE.read_text(encoding="utf-8")
    found: list[tuple[str, str, list[dict]]] = []
    root = f"({SCOREBOARD_CARDS})()[0].shadowRoot"

    def scan(name: str) -> None:
        settle(*pages)
        for page in pages:
            if not page.evaluate("() => Boolean(window.axe)"):
                page.evaluate(axe)
            page.evaluate(START_AXE, WCAG_TAGS)
        for screen, page in opened:
            page.wait_for_function("() => window.__axeFound", timeout=60000)
            result = page.evaluate("() => window.__axeFound")
            check(
                "error" not in result, f"axe-core failed on {screen} · {name}: {result}"
            )
            found.append((screen, name, result["violations"]))

    def click(selector: str) -> None:
        """A tap of the scoreboard's own, on every screen."""
        for page in pages:
            page.evaluate(f"() => {root}.querySelector({selector!r}).click()")

    show(pages, f"{HA}/homedarts-auto/live")
    views = [f"homedarts-auto/{view}" for view in AUTO_VIEWS]
    views += [f"homedarts-demo/{view}" for view in first.evaluate(DEMO_VIEWS)]
    for view in views:
        show(pages, f"{HA}/{view}")
        scan(view)

    # The idle screen of the scoreboard, once nobody threw for a while; a practice
    # match on the live card; and the scoreboard's own screens: the new game screen,
    # the keypad with its board, the board of a correction and Cricket.
    show(pages, f"{HA}/homedarts-demo/idle")
    wait_for(
        pages,
        f"() => ({SCOREBOARD_CARDS})()[0]?.shadowRoot?.querySelector('.idle-panel')",
        timeout=30000,
    )
    scan("homedarts-demo/idle · idle screen")
    show(pages, f"{HA}/homedarts-demo/board")
    pulled(pages)
    first.evaluate(
        CALL_ACTION, ["start_game", {"game": "501", "players": ["Alex", "Sam"]}]
    )
    thrown(pages, [T20, SINGLE_20])
    wait_for(pages, f"() => ({CARDS})()[0]?.shadowRoot.querySelector('.practice')")
    scan("homedarts-demo/board · practice match")
    show(pages, f"{HA}/homedarts-auto/scoreboard")
    scan("homedarts-auto/scoreboard · practice match")
    click("[data-dart='2']")
    wait_for(pages, f"() => {root}.querySelector('.pad')")
    scan("homedarts-auto/scoreboard · correcting a dart")
    click("[data-pad='board']")
    wait_for(pages, f"() => {root}.querySelector('.pad-board')")
    scan("homedarts-auto/scoreboard · the board of a correction")
    pulled(pages)
    first.evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "off"}]
    )
    wait_for(pages, f"() => {root}.querySelector('.lobby-cta')")
    click(".lobby-cta")
    wait_for(pages, f"() => {root}.querySelector('.lobby')")
    scan("homedarts-auto/scoreboard · new game screen")
    click("[data-lobby='close']")
    show(pages, f"{HA}/homedarts-demo/keypad")
    first.evaluate(CALL_SERVICE, ["switch", "turn_on", "practice_manual_entry"])
    first.evaluate(
        CALL_ACTION, ["start_game", {"game": "cricket", "players": LONG_NAMES}]
    )
    wait_for(pages, f"() => {root}.querySelector('.pad')")
    thrown(pages, [T20, SINGLE_20])
    scan("homedarts-demo/keypad · Cricket with the keypad")
    click("[data-pad='board']")
    wait_for(pages, f"() => {root}.querySelector('.pad-board')")
    scan("homedarts-demo/keypad · the board to tap")
    first.evaluate(CALL_SERVICE, ["switch", "turn_off", "practice_manual_entry"])
    first.evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": "off"}]
    )
    pulled(pages)
    for page in pages:
        page.context.close()
    return found


# The numbers clockwise from the top, to place a dart in the middle of its bed.
ORDER = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]


def aimed(name: str) -> dict:
    """A detected dart in the middle of the named bed: S17, D5, T20, 25 or BULL."""
    if name in ("25", "BULL"):
        return {
            "segment": {
                "name": "25" if name == "25" else "Bull",
                "number": 25,
                "multiplier": 1 if name == "25" else 2,
                "bed": "Single" if name == "25" else "Double",
            },
            "coords": {"x": -0.06, "y": 0.07}
            if name == "25"
            else {"x": 0.01, "y": -0.02},
        }
    number, multiplier = int(name[1:]), "SDT".index(name[0]) + 1
    radius = {1: 0.79, 2: 0.976, 3: 0.606}[multiplier]
    angle = math.radians(90 - ORDER.index(number) * 18)
    return {
        "segment": {"name": name, "number": number, "multiplier": multiplier},
        "coords": {
            "x": round(radius * math.cos(angle), 3),
            "y": round(radius * math.sin(angle), 3),
        },
    }


# Heights of every card on the page and of the scoreboard's parts, which fill a
# full-height screen whatever they show.
HEIGHTS = """
() => {
  const cards = [];
  (function collect(root) {
    root.querySelectorAll('*').forEach((el) => {
      if (el.tagName.startsWith('HOMEDARTS-') && el.shadowRoot?.querySelector('ha-card')) cards.push(el);
      if (el.shadowRoot) collect(el.shadowRoot);
    });
  })(document);
  const height = (el) => Math.round(el.getBoundingClientRect().height);
  const found = {};
  cards.forEach((card, index) => {
    const name = `${card.localName} ${index + 1}`;
    found[name] = height(card);
    // Parts by their first class and place, which stay while their state changes.
    const root = card.shadowRoot;
    for (const selector of ['.main > *', '.scoreboard > .visit', '.practice', '.player']) {
      root.querySelectorAll(selector).forEach((part, place) => {
        found[`${name} ${part.classList[0]} ${place + 1}`] = height(part);
      });
    }
  });
  return found;
}
"""
STEADY_SCREENS = (
    ("small phone", {"width": 360, "height": 640}),
    ("tablet", {"width": 768, "height": 1024}),
    ("laptop", {"width": 1280, "height": 800}),
    ("27-inch touch monitor", {"width": 2560, "height": 1440}),
)
# The live card beside the scoreboard, the full-height scoreboard and the live card
# with its game.
STEADY_VIEWS = (
    "homedarts-demo/hero",
    "homedarts-auto/scoreboard",
    "homedarts-auto/live",
)
# Games from their start to the last dart: the visits, dart by dart. X01 shows routes,
# a setup with what it leaves, a bust and the game shot; a match of legs and sets
# its details; Killer long notes on narrow tiles.
STEADY_GAMES = (
    ("off", [], {}, ["T20 S5 S1", "T19 T19"]),
    (
        "301",
        ["Alex", "Sam"],
        {},
        ["T20 T20 T20", "T20 S20 S5", "T20 T20", "S20 S20 S7", "T20 S11", "S1", "BULL"],
    ),
    (
        "501",
        ["Alex", "Sam"],
        {"legs": 3, "sets": 2},
        ["T20 T20 T20", "T20 S20 S5", "S1 S1 S1"],
    ),
    ("cricket", ["Alex", "Sam"], {}, ["T20 T20 S20", "T19 T19 T19", "S18 S18 S18"]),
    ("tactics", ["Alex", "Sam"], {}, ["T20 T19 T18", "S10 S11 S12"]),
    (
        "killer",
        ["Alex", "Sam", "Kim"],
        {},
        ["D5 S5 S1", "D12 S12 S3", "D17 S1 S1", "D12 D12 S5"],
    ),
    ("checkout_121", ["Alex"], {}, ["T20 S11 BULL", "T20 T20 D20"]),
)


def steady_heights(browser: Browser) -> None:
    """No card moves while a game goes on: from its start to its last dart, the cards
    and the scoreboard's parts keep their heights on every screen, in German with its
    long words. Only a new game and the match summary after it may change them. Every
    screen and view is open at once, and the board plays each game once for all."""
    found: list[str] = []
    opened: list[tuple[str, str, Page]] = []
    contexts: list[BrowserContext] = []
    for screen, size in STEADY_SCREENS:
        context = browser.new_context(locale="de-DE", viewport=size)
        probe(context)
        contexts.append(context)
        for view in STEADY_VIEWS:
            page = context.new_page()
            page.add_init_script(CAPTURE_ERRORS)
            opened.append((screen, view, page))
    pages = [page for _, _, page in opened]
    for view in STEADY_VIEWS:
        show([page for _, shown, page in opened if shown == view], f"{HA}/{view}")
    control_page = pages[0]

    def heights() -> dict[tuple[str, str, str], int]:
        return {
            (screen, view, part): value
            for screen, view, page in opened
            for part, value in page.evaluate(HEIGHTS).items()
        }

    def pull() -> None:
        """The takeout: every page shows it start and end, as the board reports it."""
        control({"status": "Takeout in progress", "event": "Takeout started"})
        expect_state(pages, {"local_status": "takeout_in_progress"})
        pulled(pages)

    for game, players, options, visits in STEADY_GAMES:
        pull()
        if players:
            control_page.evaluate(
                CALL_ACTION,
                ["start_game", {"game": game, "players": players, **options}],
            )
        else:
            control_page.evaluate(
                CALL_SERVICE,
                ["select", "select_option", "practice_game", {"option": "off"}],
            )
        expect_state(pages, {"practice_game": game})
        settle(*pages)
        start = heights()

        def compare(moment: str) -> None:
            settle(*pages)
            for key, value in heights().items():
                before = start.get(key)
                if before is None or abs(before - value) > 1:
                    screen, view, part = key
                    found.append(
                        f"{screen} · {game} · {moment} · {view} {part}: {before} → {value}"
                    )

        for number, visit in enumerate(visits, 1):
            darts = visit.split()
            for count in range(1, len(darts) + 1):
                thrown(pages, [aimed(name) for name in darts[:count]])
                compare(f"visit {number}: {' '.join(darts[:count])}")
            # The takeout after the game shot shows the match summary.
            if number < len(visits):
                pull()
                compare(f"visit {number} pulled")
        print(f"  {game}: {len(found)} changes so far", flush=True)
    pull()
    control_page.evaluate(
        CALL_SERVICE,
        ["select", "select_option", "practice_game", {"option": "off"}],
    )
    for screen, view, page in opened:
        errors = page_errors(page, [])
        found.extend(f"{screen} · {view}: console problem {error}" for error in errors)
    for context in contexts:
        context.close()
    check(not found, "Heights that changed during a game:\n" + "\n".join(found[:40]))


def caller(browser: Browser) -> None:
    """The caller stays silent until a tap switches it on."""
    page, problems = open_view(
        browser, "scoreboard", SCOREBOARD_CARDS, ".caller-toggle"
    )
    toggle = f"({SCOREBOARD_CARDS})()[0].shadowRoot.querySelector('.caller-toggle')"
    state = page.evaluate(f"() => {toggle}.getAttribute('aria-pressed')")
    check(state == "false", f"Caller before the tap: {state}")
    page.evaluate(f"() => {toggle}.click()")
    page.wait_for_function(
        f"() => {toggle}.getAttribute('aria-pressed') === 'true'", timeout=5000
    )
    # The label stays "Caller"; the pressed state tells that it is on.
    text = page.evaluate(f"() => {toggle}.textContent")
    check(text == "🔊Caller", f"Caller after the tap: {text}")
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()


def strategy(browser: Browser) -> None:
    """The generated dashboard shows each card in its view."""
    page = browser.new_page(locale="en-US", viewport={"width": 1280, "height": 900})
    page.add_init_script(CAPTURE_ERRORS)
    for view, cards, ready in (
        ("live", CARDS, ".board svg"),
        ("scoreboard", SCOREBOARD_CARDS, ".main"),
        ("training", TRAINING_CARDS, ".heat-layer"),
        ("players", PLAYERS_CARDS, ".players-card"),
        ("players", LEADERBOARD_CARDS, ".leaderboard"),
        ("board", STATUS_CARDS, ".camera"),
    ):
        page.goto(f"{HA}/homedarts-auto/{view}")
        page.wait_for_function(
            f"() => ({cards})().some((card) => card.shadowRoot?.querySelector('{ready}'))",
            timeout=30000,
        )
    # The live view is the live card alone; the game's rows have a view of their own.
    page.goto(f"{HA}/homedarts-auto/live")
    page.wait_for_function(f"() => ({CARDS})().length === 1", timeout=30000)
    rows = find("hui-entities-card")
    check(
        page.evaluate(f"() => ({rows})().length") == 0, "Entity rows in the live view"
    )
    page.goto(f"{HA}/homedarts-auto/games")
    page.wait_for_function(f"() => ({rows})().length >= 2", timeout=30000)
    headings = page.evaluate(
        f"() => ({find('hui-heading-card')})().map((card) => card.shadowRoot?.textContent.trim())"
    )
    check(
        any("Practice" in text for text in headings)
        and any("Tournament" in text for text in headings),
        f"Game settings headings {headings}",
    )
    errors = page_errors(page, [])
    check(not errors, f"Console problems: {errors}")
    page.close()


def players_export(browser: Browser) -> None:
    """The export button of the players card downloads every table as a ZIP file."""
    page, problems = open_view(browser, "players", PLAYERS_CARDS, ".export")
    with page.expect_download(timeout=30000) as download:
        page.evaluate(
            f"() => ({PLAYERS_CARDS})()[0].shadowRoot.querySelector('.export').click()"
        )
    name = download.value.suggested_filename
    check(
        name.startswith("homedarts-all-") and name.endswith(".zip"),
        f"Unexpected export download: {name}",
    )
    with zipfile.ZipFile(download.value.path()) as archive:
        tables = sorted(archive.namelist())
    check(
        tables == ["matches.csv", "profiles.csv", "sessions.csv"],
        f"Unexpected export tables: {tables}",
    )
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()


def editor(
    browser: Browser,
    view: str = "board",
    cards: str = CARDS,
    ready: str = ".board svg",
    rows: int = 6,
) -> None:
    """Home Assistant builds the card's form from getConfigForm."""
    page, problems = open_view(browser, view, cards, ready)
    open_card_form(page, cards)
    fields = page.evaluate(f"() => ({FORM_EDITORS})()[0].schema.length")
    check(fields == rows, f"{view} form has {fields} rows")
    # The labels are the card's own, not generic names.
    label = page.evaluate(
        f"() => ({FORM_EDITORS})()[0].computeLabel({{name: 'device_id'}})"
    )
    check(label == "Board", f"{view} form labels the board {label!r}")
    page.keyboard.press("Escape")
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()


def strategy_editor(browser: Browser) -> None:
    """Editing the generated dashboard opens the strategy's own editor."""
    page = browser.new_page(locale="en-US", viewport={"width": 1280, "height": 900})
    page.add_init_script(CAPTURE_ERRORS)
    page.goto(f"{HA}/homedarts-auto/live")
    page.wait_for_function(
        f"() => ({CARDS})().some((card) => card.shadowRoot?.querySelector('.board svg'))",
        timeout=30000,
    )
    page.evaluate(f"() => ({find('hui-root')})()[0]._enableEditMode()")
    form = page.locator("homedarts-strategy-editor > ha-form")
    form.wait_for(timeout=15000)
    fields = form.evaluate("(element) => element.schema.map((field) => field.name)")
    check(
        fields == ["device_id", "title", "scoreboard", "overlay_view"],
        f"Strategy editor fields {fields}",
    )
    page.keyboard.press("Escape")
    errors = page_errors(page, [])
    check(not errors, f"Console problems: {errors}")
    page.close()


def light_theme(browser: Browser) -> None:
    page, problems = open_board(browser, "light")
    check(page.evaluate(RENDERED) == 1, "Card not rendered in the light theme")
    errors = page_errors(page, problems)
    check(not errors, f"Console problems: {errors}")
    page.close()


def read(path: str) -> str:
    return (INTEGRATION / path).read_text(encoding="utf-8")


def card_texts(language: str) -> dict[str, str]:
    """The texts of the cards in a language: the JSON of its module in frontend/text/,
    without the comments on lines of their own (tests/test_consistency.py checks it)."""
    source = read(f"frontend/text/{language}.js")
    code = "\n".join(
        line for line in source.split("\n") if not line.lstrip().startswith("//")
    )
    texts: dict[str, str] = json.loads(code[code.index("{") : code.rindex("}") + 1])
    return texts


# What the page shows and what Home Assistant serves in the language of the browser.
LANGUAGE_STATE = f"""
async (language) => {{
  const hass = document.querySelector('home-assistant').hass;
  const root = ({CARDS})()[0].shadowRoot;
  const served = await hass.callWS({{
    type: 'frontend/get_translations',
    language,
    category: 'entity',
    integration: ['homedarts'],
  }});
  return {{
    language: hass.locale.language,
    label: root.querySelector('.visit-label').textContent,
    reset: root.querySelector('[data-action="reset"]').textContent,
    status: served.resources['component.homedarts.entity.sensor.local_status.name'],
  }};
}}
"""


def languages(browser: Browser) -> None:
    """A browser in Dutch, French or Spanish gets the cards and the entity texts in it."""
    for language in ("nl", "fr", "es"):
        page, problems = open_board(browser, locale=f"{language}-{language.upper()}")
        texts = card_texts(language)
        translation = json.loads(read(f"translations/{language}.json"))
        expected = {
            "language": language,
            "label": texts["visit"],
            "reset": texts["reset"],
            "status": translation["entity"]["sensor"]["local_status"]["name"],
        }
        state = page.evaluate(LANGUAGE_STATE, language)
        check(state == expected, f"{language}: {state} != {expected}")
        errors = page_errors(page, problems)
        check(not errors, f"{language}: console problems: {errors}")
        page.close()


def artifact(step: str, name: str) -> Path | None:
    """Where a file of a failed step goes for the CI artifact, or None without the
    folder of the artifacts."""
    if not ARTIFACTS or not os.path.isdir(ARTIFACTS):
        return None
    slug = "".join(char if char.isalnum() else "-" for char in step)
    return Path(ARTIFACTS, f"{slug}-{name}")


def keep_screenshots(browser: Browser, step: str, besides: Page | None = None) -> None:
    """Save every page still open after a failed step for the CI artifact, besides the
    page that only sets up the board."""
    pages = [
        page
        for context in browser.contexts
        for page in context.pages
        if page is not besides
    ]
    for number, page in enumerate(pages, start=1):
        path = artifact(step, f"{number}.png")
        if path is None:
            return
        try:
            # Ten seconds, not Playwright's thirty: a page of a step that hung may
            # hang as well, and the screenshots of all pages have GRACE together.
            page.screenshot(path=path, full_page=True, timeout=10_000)
        except Exception as error:  # A screenshot must never hide the real failure.
            print(f"No screenshot of {step}: {error}", flush=True)


class StepTimes:
    """The seconds of every step, kept as a table in browser-steps-table.md with the
    other artifacts after each step, failed or not: browser.sh adds it to the summary
    of the job in CI, which shows what to make faster and how to split the steps.
    While a step runs, the table names it as running, so that a run that GitHub
    stops, such as when its step of the workflow runs out of time, still names the
    step that it stopped in."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.steps: list[tuple[str, float]] = []
        self.path = artifact("browser steps", "table.md")

    def running(self, name: str) -> None:
        self.write(f"| {name} (running) | – |")

    def add(self, name: str, seconds: float) -> float:
        self.steps.append((name, seconds))
        self.write()
        return seconds

    def write(self, *running: str) -> None:
        if self.path is None:
            return
        rows = [f"| {step} | {taken:.1f} |" for step, taken in self.steps]
        total = sum(taken for _, taken in self.steps)
        self.path.write_text(
            "\n".join(
                [
                    f"### {self.title}",
                    "",
                    "| Step | Seconds |",
                    "| --- | ---: |",
                    *rows,
                    *running,
                    f"| All steps | {total:.1f} |",
                    "",
                ]
            ),
            encoding="utf-8",
        )


class Timeline:
    """What happened when in a step, in seconds from its start: the pages it opened,
    the requests of the integration's files, sent, done or failed, and what the step
    noted."""

    def __init__(self) -> None:
        self.start = time.monotonic()
        self.events: list[str] = []

    def note(self, event: str) -> None:
        self.events.append(f"{time.monotonic() - self.start:6.2f} s  {event}")

    def follow(self, page: Page) -> None:
        def requested(what: str, request: Request) -> None:
            # The files of the integration, such as homedarts-card.js.
            if "/homedarts/" in request.url:
                self.note(f"{what} {request.resource_type} {request.url}")

        def opened(frame: Frame) -> None:
            # Without the query, which holds the code of a login.
            if frame == page.main_frame:
                self.note(f"page {frame.url.partition('?')[0]}")

        page.on("framenavigated", opened)
        page.on("request", lambda sent: requested("sent", sent))
        page.on("requestfinished", lambda done: requested("done", done))
        page.on(
            "requestfailed",
            lambda failed: requested(f"failed ({failed.failure})", failed),
        )


# The text of the page's panel, in shadow roots too: what Home Assistant shows, such
# as "Error loading the dashboard strategy: Timeout waiting for strategy element".
PANEL_TEXT = f"""
() => {{
  const text = (node) => node.nodeType === Node.TEXT_NODE
    ? node.textContent
    : ['STYLE', 'SCRIPT'].includes(node.nodeName)
      ? ''
      : [...(node.shadowRoot?.childNodes ?? []), ...node.childNodes].map(text).join(' ');
  const panel = ({find("partial-panel-resolver")})()[0] ?? document.body;
  return text(panel).replace(/\\s+/g, ' ').trim().slice(0, 1000);
}}
"""


def keep_trace(browser: Browser, step: str, timeline: Timeline) -> None:
    """Print the timeline of a failed step with what its pages show and their errors,
    and save it and the step's Playwright trace for the CI artifact: together they
    tell a bug of the cards, such as "Timeout waiting for strategy element", from one
    of the test."""
    for context in browser.contexts:
        for page in context.pages:
            try:
                timeline.note(f"shown: {page.evaluate(PANEL_TEXT)}")
                timeline.note(f"page errors: {page_errors(page, [])}")
            except Exception as error:  # The page may be gone with the failure.
                reason = str(error).partition("\n")[0]
                timeline.note(f"page not readable: {reason}")
    events = "\n".join(timeline.events)
    print(f"Timeline of {step}:\n{events}", flush=True)
    path = artifact(step, "timeline.txt")
    if path is None:
        return
    try:
        path.write_text(events + "\n", encoding="utf-8")
        for number, context in enumerate(browser.contexts, start=1):
            name = "trace.zip" if number == 1 else f"trace-{number}.zip"
            context.tracing.stop(path=artifact(step, name))
    except Exception as error:  # A trace must never hide the real failure.
        print(f"No trace of {step}: {error}", flush=True)


# A dartboard without Autodarts beside the demo board, on a dashboard of its own.
MANUAL_DASHBOARD = "homedarts-manual"
ADD_MANUAL_BOARD = """
async (name) => {
  const hass = document.querySelector('home-assistant').hass;
  const flow = (path, data) => hass.callApi('POST', `config/config_entries/flow${path}`, data);
  const menu = await flow('', { handler: 'homedarts' });
  const form = await flow(`/${menu.flow_id}`, { next_step_id: 'manual' });
  const done = await flow(`/${form.flow_id}`, { name });
  return done.result.entry_id;
}
"""
MANUAL_DEVICE = """
(entry) => Object.values(document.querySelector('home-assistant').hass.devices ?? {})
  .find((device) => device.config_entries.includes(entry))?.id ?? null
"""
SAVE_MANUAL_DASHBOARD = """
async ([path, device]) => {
  const hass = document.querySelector('home-assistant').hass;
  const card = (type, options = {}) => ({ type: `custom:${type}`, device_id: device, ...options });
  const section = (cards) => ({ type: 'sections', max_columns: 2, sections: [{ type: 'grid', column_span: 2, cards }] });
  await hass.callWS({
    type: 'lovelace/dashboards/create', url_path: path, title: 'Garage', mode: 'storage',
    show_in_sidebar: false, require_admin: false,
  });
  await hass.callWS({
    type: 'lovelace/config/save', url_path: path,
    config: { views: [
      { title: 'Live', path: 'live', ...section([card('homedarts-card', { grid_options: { columns: 'full' } })]) },
      { title: 'Scoreboard', path: 'scoreboard', panel: true, cards: [card('homedarts-scoreboard-card', { full_height: true })] },
      { title: 'Status', path: 'status', ...section([card('homedarts-status-card')]) },
    ] },
  });
}
"""
REMOVE_MANUAL_BOARD = """
async ([path, entry]) => {
  const hass = document.querySelector('home-assistant').hass;
  const dashboards = await hass.callWS({ type: 'lovelace/dashboards/list' });
  const dashboard = dashboards.find((item) => item.url_path === path);
  if (dashboard) await hass.callWS({ type: 'lovelace/dashboards/delete', dashboard_id: dashboard.id });
  await hass.callApi('DELETE', `config/config_entries/entry/${entry}`);
}
"""


def manual_board(browser: Browser) -> None:
    """A dartboard without Autodarts: set up from the menu, its darts entered with
    taps on the keypad of the live card and the scoreboard, its status card with
    nothing to show, and every view on every screen size; removed again after."""
    page = browser.new_page(locale="en-US", viewport={"width": 1280, "height": 1000})
    page.add_init_script(CAPTURE_ERRORS)
    page.goto(f"{HA}/homedarts-demo/board")
    page.wait_for_function(CARDS_DRAWN, timeout=30000)
    entry = page.evaluate(ADD_MANUAL_BOARD, "Garage")
    page.wait_for_function(f"() => ({MANUAL_DEVICE})('{entry}')", timeout=30000)
    device = page.evaluate(MANUAL_DEVICE, entry)
    try:
        page.evaluate(SAVE_MANUAL_DASHBOARD, [MANUAL_DASHBOARD, device])
        page.evaluate(
            CALL_ACTION,
            [
                "start_game",
                {"config_entry_id": entry, "game": "501", "players": ["Alex", "Sam"]},
            ],
        )
        live = f"({CARDS})()[0]?.shadowRoot"
        page.goto(f"{HA}/{MANUAL_DASHBOARD}/live")
        page.wait_for_function(f"() => {live}?.querySelector('.pad')", timeout=30000)
        shown = page.evaluate(
            f"""() => ({{
              pill: {live}.querySelector('.pill').textContent,
              footer: {live}.querySelector('.footer').hidden,
            }})"""
        )
        check(
            shown == {"pill": "Enter your darts", "footer": True},
            f"The live card of a board without Autodarts: {shown}",
        )
        # Three darts with taps on the keypad; the live card counts the visit.
        for bed, multiplier in (("T20", "3"), ("T20", "3"), ("T19", "3")):
            page.evaluate(
                f'() => {live}.querySelector(\'[data-pad="multiplier"]'
                f'[data-value="{multiplier}"]\').click()'
            )
            page.evaluate(
                f"() => {live}.querySelector('.pad-number[data-value=\"{bed}\"]').click()"
            )
        page.wait_for_function(
            f"() => {live}.querySelector('.score')?.textContent === '177'"
            f" && {live}.querySelector('.pill').textContent === 'Visit complete'",
            timeout=15000,
        )
        # The next player takes a second tap.
        for _ in range(2):
            page.evaluate(f"() => {live}.querySelector('[data-pad=\"next\"]').click()")
        page.wait_for_function(
            f"() => {live}.querySelector('.practice-remaining')?.textContent === '501'"
            f" && {live}.querySelector('.pill').textContent === 'Enter your darts'",
            timeout=15000,
        )
        # The scoreboard has the keypad without its option, and shows Alex's 324.
        board = f"({SCOREBOARD_CARDS})()[0]?.shadowRoot"
        page.goto(f"{HA}/{MANUAL_DASHBOARD}/scoreboard")
        page.wait_for_function(f"() => {board}?.querySelector('.pad')", timeout=30000)
        scores = page.evaluate(SCOREBOARD_STATE)["players"]
        check(
            scores == [["Alex", "324", False], ["Sam", "501", True]],
            f"The scoreboard of a board without Autodarts: {scores}",
        )
        # Sam's visit goes in as its score; one that no visit scores keeps OK off.
        page.evaluate(f"() => {board}.querySelector('[data-pad=\"score\"]').click()")
        line = f"() => {board}.querySelector('.score-line').textContent"
        ok_off = f"() => {board}.querySelector('[data-pad=\"enter\"]').disabled"
        for digit in "179":
            page.evaluate(
                f"() => {board}.querySelector('.pad-score [data-value=\"{digit}\"]').click()"
            )
        shown = [page.evaluate(line), page.evaluate(ok_off)]
        check(
            shown == ["179No visit scores 179", True],
            f"A score no visit makes: {shown}",
        )
        for _ in "179":
            page.evaluate(
                f"() => {board}.querySelector('[data-pad=\"erase\"]').click()"
            )
        for digit in "100":
            page.evaluate(
                f"() => {board}.querySelector('.pad-score [data-value=\"{digit}\"]').click()"
            )
        hint = page.evaluate(f"() => {board}.querySelector('.score-line').textContent")
        check(hint == "100leaves 401", f"The score of a visit says {hint!r}")
        page.evaluate(f"() => {board}.querySelector('[data-pad=\"enter\"]').click()")
        page.wait_for_function(
            f"() => {board}.querySelectorAll('.player .big')[1]?.textContent === '401'",
            timeout=15000,
        )
        # Alex and Sam score on, which leaves Alex 144, from where 100 leaves a double.
        for score, player, left in (("180", 0, "144"), ("100", 1, "301")):
            for digit in score:
                page.evaluate(
                    f"() => {board}.querySelector('.pad-score [data-value=\"{digit}\"]').click()"
                )
            page.evaluate(
                f"() => {board}.querySelector('[data-pad=\"enter\"]').click()"
            )
            page.wait_for_function(
                f"() => {board}.querySelectorAll('.player .big')[{player}]?.textContent"
                f" === '{left}'",
                timeout=15000,
            )
        # 180 is more than Alex's 144 and busts: Alex keeps 144 while Sam throws, and
        # Sam's 0 brings Alex back.
        for digit in "180":
            page.evaluate(
                f"() => {board}.querySelector('.pad-score [data-value=\"{digit}\"]').click()"
            )
        shown = [page.evaluate(line), page.evaluate(ok_off)]
        check(shown == ["180Bust – the score stays", False], f"A bust says {shown}")
        page.evaluate(f"() => {board}.querySelector('[data-pad=\"enter\"]').click()")
        page.wait_for_function(
            f'() => {board}.querySelector(\'[data-pad="answer"][data-value="0"]\')',
            timeout=15000,
        )
        page.evaluate(
            f'() => {board}.querySelector(\'[data-pad="answer"][data-value="0"]\')'
            ".click()"
        )
        page.wait_for_function(
            f"() => {board}.querySelectorAll('.player')[1]?.classList.contains('active')",
            timeout=15000,
        )
        scores = page.evaluate(SCOREBOARD_STATE)["players"]
        check(
            scores == [["Alex", "144", False], ["Sam", "301", True]],
            f"After Alex's bust: {scores}",
        )
        page.evaluate(
            f"() => {board}.querySelector('.pad-score [data-value=\"0\"]').click()"
        )
        page.evaluate(f"() => {board}.querySelector('[data-pad=\"enter\"]').click()")
        page.wait_for_function(
            f"() => {board}.querySelectorAll('.player')[0]?.classList.contains('active')",
            timeout=15000,
        )
        page.goto(f"{HA}/{MANUAL_DASHBOARD}/status")
        note = f"({STATUS_CARDS})()[0]?.shadowRoot.querySelector('.manual-note')"
        page.wait_for_function(f"() => {note} && !{note}.hidden", timeout=30000)
        errors = page_errors(page, [])
        check(not errors, f"Console problems: {errors}")
        # Every view on every screen at once.
        screens = [Screen(browser, *size) for size in SCREENS]
        views = [screen.page for screen in screens]
        for name in ("live", "scoreboard", "status"):
            show(views, f"{HA}/{MANUAL_DASHBOARD}/{name}")
            look(screens, f"manual-{name}")
        # The score view of the scoreboard's keypad.
        show(views, f"{HA}/{MANUAL_DASHBOARD}/scoreboard")
        root = f"({SCOREBOARD_CARDS})()[0].shadowRoot"

        def click(selector: str) -> None:
            """A tap of the scoreboard's own, on every screen."""
            for view in views:
                view.evaluate(f"() => {root}.querySelector({selector!r}).click()")

        click('[data-pad="score"]')
        look(screens, "manual-scoreboard-score")
        # The question after a score keeps the pad's height, and so does Cancel.
        pad = f"() => {root}.querySelector('.pad').getBoundingClientRect().height"
        for digit in "100":
            click(f'.pad-score [data-value="{digit}"]')
        typed = [view.evaluate(pad) for view in views]
        click('[data-pad="enter"]')
        wait_for(views, f"() => {root}.querySelector('[data-pad=\"answer\"]')")
        look(screens, "manual-scoreboard-ask")
        asked = [view.evaluate(pad) for view in views]
        click('[data-pad="cancel"]')
        wait_for(views, f"() => {root}.querySelector('[data-pad=\"enter\"]')")
        back = [view.evaluate(pad) for view in views]
        found: list[str] = []
        for screen, score, *after in zip(screens, typed, asked, back, strict=True):
            screen.problems.extend(
                f"{screen.name}: the pad is {height:.0f} px tall {moment}, "
                f"{score:.0f} px with the score"
                for moment, height in zip(
                    ("asking", "after Cancel"), after, strict=True
                )
                if abs(height - score) > 1
            )
            screen.close()
            found += screen.problems
        check(not found, "Layout problems:\n" + "\n".join(found))
    finally:
        page.evaluate(REMOVE_MANUAL_BOARD, [MANUAL_DASHBOARD, entry])
        page.close()


# Where every step finds the board and its games, whatever the step before it left: no
# tournament, no keypad and no game, the detection running and no darts on the board.
# A card that showed a game opens its new game screen by itself eight seconds after the
# game ends, so a game left running would open it in the middle of the next step.
BETWEEN_GAMES = {
    "tournament": "no_tournament",
    "practice_manual_entry": "off",
    "practice_game": "off",
    "practice_teams": "off",
    "detection": "on",
    "local_status": "throw",
    "num_throws": "0",
}
# The states that the board itself sets, by its detection, its status and its darts.
BOARD_STATES = ("detection", "local_status", "num_throws")
# The match settings that steps change, as they are between games: one player, one
# leg and one set, without the bot.
MATCH_SETTINGS = {
    "practice_bot_level": 0,
    "practice_players": 1,
    "practice_legs": 1,
    "practice_sets": 1,
}
# Whether the page knows the states of these Autodarts entities.
STATES_KNOWN = (
    f"(keys) => Object.values(({STATES})(keys)).every((state) => state !== null)"
)


class Board:
    """Brings the board and its games back between games before a step, through a page
    of its own that shows no card and stays open for the whole run."""

    def __init__(self, browser: Browser) -> None:
        self.browser = browser
        self.page: Page | None = None

    def between_games(self) -> None:
        keys = [*BETWEEN_GAMES, *MATCH_SETTINGS]
        page = self.page
        if page is None:
            page = self.page = self.browser.new_page()
            page.goto(f"{HA}/profile/general")
            wait_for([page], STATES_KNOWN, arg=keys, timeout=30000)
        states = page.evaluate(STATES, keys)
        if states["tournament"] != BETWEEN_GAMES["tournament"]:
            page.evaluate(CALL_ACTION, ["stop_tournament", {}])
        if states["practice_manual_entry"] != "off":
            page.evaluate(CALL_SERVICE, ["switch", "turn_off", "practice_manual_entry"])
        if states["practice_game"] != "off":
            page.evaluate(
                CALL_SERVICE,
                ["select", "select_option", "practice_game", {"option": "off"}],
            )
        if states["practice_teams"] != "off":
            page.evaluate(CALL_SERVICE, ["switch", "turn_off", "practice_teams"])
        for key, value in MATCH_SETTINGS.items():
            if float(states[key]) != value:
                page.evaluate(
                    CALL_SERVICE, ["number", "set_value", key, {"value": value}]
                )
        if any(states[key] != BETWEEN_GAMES[key] for key in BOARD_STATES):
            control(
                {
                    "running": True,
                    "status": "Throw",
                    "event": "Takeout finished",
                    "throws": [],
                }
            )
        expect_state([page], BETWEEN_GAMES)


def watchdog(browser: Browser) -> None:
    """The watchdog itself, on Playwright's real sync API, whose greenlets and tasks
    it relies on (wake_playwright of watchdog.py): a wait in a page that never ends,
    and one of the step itself, each fail soon after a budget of two seconds with the
    name of the wait, and the page still answers afterwards, as the screenshots of a
    step that hung need it. So a new release of Playwright that changes them fails
    here, and not first in a step that hangs."""
    page = browser.new_page()
    never = "() => new Promise(() => {})"
    waits: tuple[tuple[str, Callable[[], object]], ...] = (
        ("A wait in a page that never ends", lambda: page.evaluate(never)),
        ("A wait of the step that never ends", lambda: threading.Event().wait()),
    )
    for what, wait in waits:
        started = time.monotonic()
        try:
            with budget(what, 2, BrowserFailure, wake_playwright):
                wait()
        except BrowserFailure as error:
            check(
                str(error) == f"{what} took longer than 2 s",
                f"{what} failed with {error!r}",
            )
        else:
            raise BrowserFailure(f"{what} ended")
        taken = time.monotonic() - started
        check(taken < 10, f"{what} failed {taken:.1f} s after a budget of 2 s")
        check(
            page.evaluate("() => 6 * 7") == 42,
            f"The page no longer answers after {what.lower()} ran out of time",
        )
    page.close()


def hung_step(browser: Browser) -> None:
    """A drill, which runs only when BROWSER_STEPS names it: a step that hangs in its
    page, as steps did in CI until GitHub cancelled their job. Its budget runs out,
    and the run fails as after any hang, with the name of the step, the line that it
    waited at, a screenshot of its page and the logs of Home Assistant."""
    page = browser.new_page()
    page.set_content("<h1>A step that hangs</h1>")
    page.evaluate("() => new Promise(() => {})")


def steps(browser: Browser, playwright: Playwright) -> list[Step]:
    """Every step in its order, each in one of four groups of about the same seconds,
    which browser-steps-table.md lists after a run. In CI the groups 1 and 2 share a
    runner (BROWSER_WORKERS=2): the steady heights, the longest step, run beside the
    short steps of group 1. The groups 3 and 4 have a runner each, so that Safari's
    WebKit in group 4 shares the CPU with no other browser: it failed to load the
    scripts of Home Assistant while every screen size opened nine screens beside it.
    A step that runs longer than its budget fails (shards.BUDGET): one of about three
    times its longest run in CI, at least two minutes."""
    return [
        # Both read the demo as demo.py left it: the training card its session before
        # any control changes it, the live card the visit on the board.
        Step("training card", 1, lambda: training(browser), as_started=True),
        Step("live card", 1, lambda: visit(browser), as_started=True),
        Step("fresh loads", 1, lambda: fresh_loads(browser)),
        Step("practice game", 1, lambda: practice(browser)),
        Step("progress and leaderboard", 1, lambda: progress(browser)),
        Step("status card", 1, lambda: status(browser)),
        Step("scoreboard", 1, lambda: scoreboard(browser)),
        Step("more games", 1, lambda: more_games(browser)),
        Step("scoreboard caller", 1, lambda: caller(browser)),
        Step("new game screen", 1, lambda: lobby(browser)),
        Step(
            "correcting with the keypad and the bot", 1, lambda: play_comfort(browser)
        ),
        Step("tournament", 1, lambda: tournament(browser)),
        Step("the watchdog", 3, lambda: watchdog(browser)),
        Step("tablet screen", 3, lambda: tablet_screen(browser)),
        Step("touch screens", 4, lambda: touch_screens(browser)),
        Step("Safari on an iPhone", 4, lambda: safari(playwright)),
        # 41 s at most in CI.
        Step("every screen size", 3, lambda: screens(browser), budget=150),
        Step("accessibility", 4, lambda: accessibility(browser)),
        # 126 s at most in CI.
        Step("steady heights", 2, lambda: steady_heights(browser), budget=390),
        Step("automatic dashboard", 1, lambda: strategy(browser)),
        Step("players export", 1, lambda: players_export(browser)),
        Step("live card editor", 1, lambda: editor(browser, rows=7)),
        Step(
            "training card editor",
            1,
            lambda: editor(browser, "training", TRAINING_CARDS, ".heat-layer", 7),
        ),
        Step(
            "status card editor",
            1,
            lambda: editor(browser, "status", STATUS_CARDS, ".toggle", 4),
        ),
        Step(
            "doubles editor",
            1,
            lambda: editor(browser, "doubles", DOUBLES_CARDS, ".doubles-card", 4),
        ),
        Step(
            "players editor",
            1,
            lambda: editor(browser, "players", PLAYERS_CARDS, ".players-card", 6),
        ),
        Step(
            "leaderboard editor",
            1,
            lambda: editor(
                browser, "leaderboard", LEADERBOARD_CARDS, ".leaderboard", 5
            ),
        ),
        Step(
            "scoreboard editor",
            1,
            lambda: editor(browser, "scoreboard", SCOREBOARD_CARDS, ".main", 10),
        ),
        Step("dashboard strategy editor", 1, lambda: strategy_editor(browser)),
        Step("light theme", 1, lambda: light_theme(browser)),
        Step("languages", 1, lambda: languages(browser)),
        Step("a hung step", 3, lambda: hung_step(browser), budget=20, drill=True),
        # Last: a second board would be the first of the cards without one.
        Step("a dartboard without Autodarts", 3, lambda: manual_board(browser)),
    ]


def main() -> None:
    part, parts = shard(SHARD)
    which = f" of shard {part}/{parts}" if parts > 1 else ""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        board = Board(browser)
        chosen = choose(steps(browser, playwright), WANTED, SHARD)
        times = StepTimes(f"Browser steps{which}")
        for step in chosen:
            # A failure then names the step, not only a timeout deep in Playwright.
            print(f"Browser step: {step.name}", flush=True)
            times.running(step.name)
            started = time.monotonic()
            # A step that hangs fails after its budget with the line it waits at,
            # long before the time limit of the job (watchdog.py).
            watch = budget(step.name, step.budget, BrowserFailure, wake_playwright)
            try:
                with watch:
                    if not step.as_started:
                        try:
                            board.between_games()
                        except Exception as error:
                            raise BrowserFailure(
                                f"Before {step.name}, the board did not get back"
                                f" between games: {error}"
                            ) from error
                    step.run()
            except Exception:
                # browser.sh explains a step that took too long otherwise.
                how = "took too long" if watch.fired else "failed"
                times.add(f"{step.name} ({how})", time.monotonic() - started)
                with deadline(GRACE):
                    keep_screenshots(browser, step.name, besides=board.page)
                raise
            seconds = times.add(step.name, time.monotonic() - started)
            print(f"Browser step: {step.name} ({seconds:.1f} s)", flush=True)
        browser.close()
    total = sum(seconds for _, seconds in times.steps)
    count = f"{len(chosen)} step{'' if len(chosen) == 1 else 's'}"
    ran = ", ".join(step.name for step in chosen) or "no step of BROWSER_STEPS is in it"
    print(f"Browser check{which} passed, {count} in {total:.0f} s: {ran}.")


if __name__ == "__main__":
    main()
