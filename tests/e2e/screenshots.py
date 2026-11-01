"""Capture documentation screenshots and animations from the demo instance.

Runs in the Playwright container on the demo's Compose network (see screenshots.sh).
Every image shows the synthetic demo board, so no personal data can appear.
"""

from __future__ import annotations

import importlib.util
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic

from pages import FRAMES, POLL, QUIET, WEBSOCKET_QUIET, loaded, open_card_form, probe
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from watchdog import GRACE, budget, deadline, wake_playwright

HA = "http://homeassistant:8123"
BOARD = "http://board-mock:3180"
LANGUAGE = os.environ.get("DEMO_LANGUAGE", "en")
OUTPUT = Path(os.environ.get("OUTPUT", "/repo/docs/images")) / LANGUAGE
LOCALE = {"en": "en-US", "de": "de-DE"}[LANGUAGE]
# Screenshots of a failed run, never next to the scripts (ignored by Git).
ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
# The frozen clock of the demo (compose.frozen.yaml): the moment it stands at, and the
# file in Home Assistant's config volume that moves it on. screenshots.sh sets them,
# so that two runs render the same images; without them, the clock runs as usual.
DEMO_TIME = os.environ.get("DEMO_TIME", "")
DEMO_CLOCK = Path(os.environ.get("DEMO_CLOCK", "/ha-config/.demo_clock"))
_SPEC = importlib.util.spec_from_file_location(
    "demo_clock", Path(__file__).resolve().parent / "frozen" / "sitecustomize.py"
)
demo_clock = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(demo_clock)
CLOCK = demo_clock.Clock(DEMO_TIME, str(DEMO_CLOCK)) if DEMO_TIME else None

# Demo darts as the Board Manager reports them (see demo.py).
T20 = {
    "segment": {"name": "T20", "number": 20, "multiplier": 3, "bed": "Triple"},
    "coords": {"x": 0.035, "y": 0.608},
}
S5 = {
    "segment": {"name": "S5", "number": 5, "multiplier": 1, "bed": "SingleOuter"},
    "coords": {"x": -0.24, "y": 0.76},
}
BULL = {
    "segment": {"name": "Bull", "number": 25, "multiplier": 2, "bed": "Double"},
    "coords": {"x": 0.012, "y": -0.02},
}

# The numbers clockwise from the top, to place darts in the middle of a bed.
ORDER = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]


def at(name: str) -> dict:
    """A detected dart in the middle of the named bed, like S17 or T19."""
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

# Names a practice player; the name fields share one translation key.
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

# Sets a player's own start score; the four numbers share one translation key.
SET_START = """
async ([index, value]) => {
  const hass = document.querySelector('home-assistant').hass;
  const ids = Object.values(hass.entities)
    .filter((item) => item.platform === 'homedarts' && item.translation_key === 'practice_start')
    .map((item) => item.entity_id)
    .sort();
  await hass.callService('number', 'set_value', { entity_id: ids[index], value });
}
"""

FIND_CARDS = """
() => {
  const cards = [];
  (function collect(root) {
    root.querySelectorAll('homedarts-card').forEach((card) => cards.push(card));
    root.querySelectorAll('*').forEach((el) => el.shadowRoot && collect(el.shadowRoot));
  })(document);
  return cards;
}
"""

# Pauses the card animations at a given time, so blinking beds render deterministically.
SEEK = (
    "(time) => { for (const card of ("
    + FIND_CARDS
    + ")()) { for (const animation of card.shadowRoot.getAnimations()) {"
    " animation.pause(); animation.currentTime = time; } } }"
)


def control(changes: dict) -> None:
    """What the board sends: darts, a takeout or a new status."""
    tick()
    request = urllib.request.Request(
        f"{BOARD}/control/state",
        data=json.dumps(changes).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(request, timeout=10).read()


def wait_for_score(page: Page, score: str) -> None:
    page.wait_for_function(
        f"() => ({FIND_CARDS})().some((c) => c.shadowRoot.querySelector('.score')?.textContent === '{score}')",
        timeout=15000,
    )


def ready(page: Page) -> None:
    """Wait until the page has loaded what Home Assistant sends it, and two frames
    since. Its animations go on: every picture holds them itself (settle)."""
    loaded(page)
    page.evaluate(FRAMES)


def open_dashboard(page: Page, view: str) -> None:
    page.goto(f"{HA}/homedarts-demo/{view}")
    page.wait_for_function(
        f"() => ({FIND_CARDS})().some((c) => c.shadowRoot.querySelector('.board svg'))",
        timeout=60000,
    )
    ready(page)


def peak(page: Page) -> None:
    # The end of a blink cycle shows the highlight at full strength.
    page.evaluate(SEEK, 800)


def demo_now() -> datetime | None:
    """The time on the frozen clock of Home Assistant, or None when its clock runs."""
    return None if CLOCK is None else datetime.fromtimestamp(CLOCK(), UTC)


def move_clock(moment: datetime) -> None:
    """Move the frozen clock of Home Assistant to a moment."""
    demo_clock.move(DEMO_CLOCK, moment.timestamp())


def tick() -> None:
    """A move at the board takes two seconds on the frozen clock, as at a real board:
    the history of the board, the length of a session and the training time of the
    weekly report come out the same in every run."""
    if CLOCK is not None:
        demo_clock.move(DEMO_CLOCK, CLOCK() + demo_clock.STEP)


# The toolbar of a dashboard casts no shadow on what scrolls beneath it: Home
# Assistant fades the shadow in at a moment of its own, which no two runs share.
QUIET_TOOLBAR = """
document.addEventListener('DOMContentLoaded', () => {
  const style = document.createElement('style');
  style.textContent = 'html { --bar-box-shadow: none !important; }';
  document.head.append(style);
});
"""


def new_context(
    browser: Browser, flowing: bool = False, **options: object
) -> BrowserContext:
    """A browser context whose clock shows the time of Home Assistant's.

    The clock stands still like Home Assistant's, so relative times, the idle
    screen's clock and countdowns read the same in every run. A context that
    needs time to pass in the page, such as the hold of a tournament result,
    gets a clock that starts at that time and runs.
    """
    context = browser.new_context(**options)
    context.add_init_script(QUIET_TOOLBAR)
    # ready() follows the requests of the frontend on its websocket.
    probe(context)
    if (now := demo_now()) is not None:
        if flowing:
            context.clock.install(time=now)
        else:
            context.clock.set_fixed_time(now)
    return context


# Holds what still moves, so that every image comes out the same in every run:
# pictures still loading are awaited, running transitions and fade-ins jump to
# their end, and endless animations, such as blinking beds, stop at a fixed time.
# Animations a step paused itself, at the moment it wants, stay as they are. While
# Home Assistant still changes the page, it goes on until two looks a tenth of a
# second apart find nothing moving and nothing changed, for three seconds at most.
SETTLE = """
async ([time, wait]) => {
  const roots = () => {
    const found = [document];
    for (let index = 0; index < found.length; index++) {
      found[index].querySelectorAll('*').forEach((el) => el.shadowRoot && found.push(el.shadowRoot));
    }
    return found;
  };
  const loading = roots()
    .flatMap((root) => [...root.querySelectorAll('img')])
    .filter((img) => !img.complete)
    .map((img) => Promise.race([img.decode().catch(() => {}), new Promise((done) => setTimeout(done, 3000))]));
  await Promise.all(loading);
  let changed = 0;
  const observer = new MutationObserver((records) => { changed += records.length; });
  for (const root of roots()) {
    observer.observe(root, { subtree: true, childList: true, attributes: true, characterData: true });
  }
  const hold = () => {
    let moving = 0;
    for (const animation of new Set(roots().flatMap((root) => root.getAnimations()))) {
      if (animation.playState !== 'running') continue;
      moving++;
      try {
        if (animation.effect?.getComputedTiming().endTime === Infinity) {
          animation.pause();
          animation.currentTime = time;
        } else {
          animation.finish();
        }
      } catch (error) {
        animation.cancel();
      }
    }
    return moving;
  };
  let quiet = 0;
  for (let round = 0; round < 30 && quiet < 2; round++) {
    const moving = hold() + changed;
    changed = 0;
    quiet = moving ? 0 : quiet + 1;
    if (!wait) break;
    await new Promise((done) => setTimeout(done, 100));
  }
  observer.disconnect();
}
"""


# Chromium draws every picture whole and sharp, and animates on its main thread, so
# that nothing it draws depends on the timing of its other threads.
STEADY_CHROMIUM = [
    "--disable-checker-imaging",
    "--disable-partial-raster",
    "--disable-threaded-animation",
    "--disable-threaded-scrolling",
    "--run-all-compositor-stages-before-draw",
]


def settle(page: Page, wait: bool = True) -> None:
    """Hold the page still for a picture; without waiting for a frame of a series."""
    page.evaluate(SETTLE, [800, wait])


# pngquant of Ubuntu 24.04, which pngquant.sh installs at its pinned version; on one
# thread, so that nothing in its palettes can depend on the order of threads.
PNGQUANT = ["pngquant", "--force", "--skip-if-larger", "--strip", "--quality=80-95"]


def compress(path: Path) -> None:
    """Shrink a screenshot to about a fifth without visible loss."""
    if not shutil.which("pngquant"):
        return
    result = subprocess.run(
        [*PNGQUANT, "--ext", ".png", str(path)],
        env={**os.environ, "OMP_NUM_THREADS": "1"},
        check=False,
    )
    # 98 and 99: the file would not get smaller or better and stays as it is.
    if result.returncode not in (0, 98, 99):
        raise RuntimeError(f"pngquant failed on {path}: {result.returncode}")


# With KEEP_RAW set, every image and every frame of an animation is also kept as
# taken, before compression, in tests/e2e/artifacts/raw/<language>/, to find out
# what differs between two runs.
RAW = ARTIFACTS / "raw" / LANGUAGE if os.environ.get("KEEP_RAW") else None


def keep_raw(name: str, image: bytes) -> None:
    if RAW is not None:
        RAW.mkdir(parents=True, exist_ok=True)
        (RAW / name).write_bytes(image)


def saved(path: Path) -> None:
    keep_raw(path.name, path.read_bytes())
    compress(path)
    print(f"saved {path}", flush=True)


def card_shot(
    page: Page, name: str, index: int = 0, tag: str = "homedarts-card"
) -> None:
    card = page.locator(tag).nth(index)
    path = OUTPUT / f"{name}.png"
    if card.bounding_box()["height"] > page.viewport_size["height"]:
        # Taller than the screen: the whole page from its top, where the toolbar
        # neither covers the card nor casts a shadow on it.
        page.evaluate("() => window.scrollTo(0, 0)")
        settle(page)
        clip = card.bounding_box()
        page.screenshot(path=str(path), clip=clip, full_page=True, animations="allow")
    else:
        # In sight before the page holds still: a scroll lets the toolbar cast a shadow.
        card.scroll_into_view_if_needed()
        settle(page)
        card.screenshot(path=str(path), animations="allow")
    saved(path)


def tall_card_shot(page: Page, name: str, index: int = 0) -> None:
    """A card taller than the window, which would scroll under the toolbar."""
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"], "height": 2000})
    ready(page)
    peak(page)
    card_shot(page, name, index)
    page.set_viewport_size(size)


def page_shot(page: Page, name: str) -> None:
    settle(page)
    page.screenshot(path=str(OUTPUT / f"{name}.png"))
    saved(OUTPUT / f"{name}.png")


@contextmanager
def failure_screenshots() -> Iterator[list[Browser]]:
    """Save every page still open when a capture fails, in tests/e2e/artifacts."""
    browsers: list[Browser] = []
    try:
        yield browsers
    except Exception:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        pages = [
            page
            for browser in browsers
            for context in browser.contexts
            for page in context.pages
        ]
        # A page of a section that hung may hang as well: ten seconds each, and
        # GRACE for all of them (watchdog.py).
        with deadline(GRACE):
            for number, page in enumerate(pages, start=1):
                path = ARTIFACTS / f"screenshots-{LANGUAGE}-failure-{number}.png"
                try:
                    page.screenshot(path=str(path), full_page=True, timeout=10_000)
                    print(f"saved {path}")
                except Exception as error:  # A screenshot must never hide the failure.
                    print(f"No failure screenshot {number}: {error}")
        raise


class Recorder:
    """Frames of one element and how long each shows, for an animated WebP."""

    def __init__(self, page: Page, tag: str = "homedarts-card") -> None:
        self.page = page
        self.element = page.locator(tag).first
        self.frames: list[Image.Image] = []
        self.durations: list[int] = []

    def shot(self, duration: int, wait: bool = True) -> None:
        self.element.scroll_into_view_if_needed()
        settle(self.page, wait)
        image = self.element.screenshot(animations="allow")
        self.frames.append(Image.open(io.BytesIO(image)))
        self.durations.append(duration)

    def blink(self, count: int = 1, step: int = 100, hold: int | None = None) -> None:
        """The blinking beds of the live card, frame by frame; the last frame holds."""
        settle(self.page)
        for index in range(count):
            self.page.evaluate(SEEK, index * step)
            self.shot(hold if hold and index == count - 1 else step, wait=False)

    def save(self, name: str, width: int = 760) -> None:
        for index, frame in enumerate(self.frames):
            if RAW is not None:
                raw = io.BytesIO()
                frame.save(raw, "PNG")
                keep_raw(f"{name}-{index:02}.png", raw.getvalue())
        # Animated WebP keeps the colours of every frame at a fraction of a GIF's size.
        resized = [
            frame.convert("RGB").resize(
                (width, round(frame.height * width / frame.width)),
                Image.Resampling.LANCZOS,
            )
            for frame in self.frames
        ]
        # A card that grows, like the scoreboard with its new game screen, keeps
        # the size of its tallest frame; the rest is filled with its background.
        height = max(frame.height for frame in resized)
        for index, frame in enumerate(resized):
            if frame.height < height:
                fill = frame.getpixel((0, frame.height - 1))
                padded = Image.new("RGB", (width, height), fill)
                padded.paste(frame, (0, 0))
                resized[index] = padded
        target = OUTPUT / f"{name}.webp"
        resized[0].save(
            target,
            save_all=True,
            append_images=resized[1:],
            duration=self.durations,
            loop=0,
            quality=85,
            method=6,
        )
        size = target.stat().st_size // 1024
        print(f"saved {target} ({size} KiB, {len(self.frames)} frames)", flush=True)


def visit_animation(page: Page) -> None:
    """Darts landing one by one, then the takeout, as an animation."""
    recorder = Recorder(page)
    capture = recorder.blink

    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    wait_for_score(page, "0")
    capture(1, hold=900)
    for darts, score in (([T20], "60"), ([T20, S5], "65"), ([T20, S5, BULL], "115")):
        control({"event": "Throw detected", "throws": darts})
        wait_for_score(page, score)
        capture(16)
    capture(1, hold=900)
    control({"status": "Takeout in progress", "event": "Takeout started"})
    page.wait_for_timeout(700)
    capture(8)
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    wait_for_score(page, "0")
    capture(1, hold=1200)
    recorder.save("card-visit")
    # Restore the demo visit for the remaining screenshots.
    for darts in ([T20], [T20, S5], [T20, S5, BULL]):
        control({"event": "Throw detected", "throws": darts})
    wait_for_score(page, "115")


def correct_live_animation(page: Page) -> None:
    """A dart the board read wrong, corrected on the live card: a tap on the dart with its
    pencil opens the pad below the darts, and T and 20 put it in the treble."""
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    wait_for_score(page, "0")
    recorder = Recorder(page)
    control({"event": "Throw detected", "throws": [at("T20")]})
    control({"event": "Throw detected", "throws": [at("T20"), at("S20")]})
    wait_for_score(page, "80")
    page.wait_for_timeout(600)
    recorder.shot(1400)
    card = page.locator("homedarts-card").first
    tap(page, recorder, card.locator(".slot[data-dart='2']"), 1200)
    tap(page, recorder, card.locator("[data-pad='multiplier'][data-value='3']"), 700)
    tap(page, recorder, card.locator(".pad-number[data-value='T20']"), 300)
    wait_for_score(page, "120")
    page.wait_for_timeout(400)
    recorder.shot(2400)
    recorder.save("correct-live")
    # Restore the demo visit for the remaining screenshots.
    control({"status": "Throw", "event": "Takeout finished", "throws": []})
    for darts in ([T20], [T20, S5], [T20, S5, BULL]):
        control({"event": "Throw detected", "throws": darts})
    wait_for_score(page, "115")


# Animations of the games -----------------------------------------------------------


def game(page: Page, option: str) -> None:
    page.evaluate(
        CALL_SERVICE, ["select", "select_option", "practice_game", {"option": option}]
    )


def players(page: Page, count: int) -> None:
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_players", {"value": count}]
    )


def pull_darts() -> None:
    control({"status": "Takeout in progress", "event": "Takeout started"})
    control({"status": "Throw", "event": "Takeout finished", "throws": []})


def wait_card(
    page: Page, condition: str, tag: str = "homedarts-card", timeout: int = 15000
) -> None:
    """Wait until the card's shadow root `r` meets a JavaScript condition."""
    page.wait_for_function(
        f"() => ({find(tag)})().some((c) => {{ const r = c.shadowRoot; return {condition}; }})",
        timeout=timeout,
    )


def big(value: str) -> str:
    return f"r.querySelector('.practice-remaining')?.textContent === '{value}'"


def visit(page: Page, names: list[str]) -> None:
    """Throw a whole visit without recording it."""
    darts = [at(name) for name in names]
    for count in range(1, len(darts) + 1):
        control({"event": "Throw detected", "throws": darts[:count]})
        page.wait_for_timeout(250)
    pull_darts()
    page.wait_for_timeout(600)


def checkout_animation(page: Page) -> None:
    """A 141 checkout: the route and the outlined bed follow every dart."""
    pull_darts()
    players(page, 1)
    game(page, "501")
    wait_card(page, big("501"))
    for _ in range(2):
        visit(page, ["T20", "T20", "T20"])
    wait_card(page, big("141"))
    recorder = Recorder(page)
    recorder.blink(1, hold=1400)
    thrown: list[dict] = []
    for name, remaining in (("T20", "81"), ("T19", "24"), ("D12", "0")):
        thrown.append(at(name))
        control({"event": "Throw detected", "throws": thrown})
        wait_card(page, big(remaining))
        recorder.blink(10, hold=1100)
    recorder.blink(1, hold=1400)
    pull_darts()
    wait_card(page, big("501"))
    recorder.blink(1, hold=1400)
    recorder.save("practice-checkout")


def cricket_animation(page: Page) -> None:
    """Two players close numbers and score on the chalkboard."""
    pull_darts()
    page.evaluate(SET_NAME, [0, "Alex"])
    page.evaluate(SET_NAME, [1, "Sam"])
    players(page, 2)
    game(page, "cricket")
    cell = (
        "r.querySelectorAll('.practice .cricket tbody tr')[{row}]"
        "?.children[{column}]?.textContent === '{mark}'"
    )
    wait_card(page, "!!r.querySelector('.practice .cricket')")
    recorder = Recorder(page)
    recorder.blink(1, hold=1200)
    # Each dart with what the card shows once it counted.
    visits = [
        [
            ("T20", cell.format(row=0, column=1, mark="Ⓧ")),
            ("T20", big("60")),
            ("S19", cell.format(row=1, column=1, mark="/")),
        ],
        [
            ("T19", cell.format(row=1, column=2, mark="Ⓧ")),
            ("T19", big("57")),
            ("D18", cell.format(row=2, column=2, mark="X")),
        ],
    ]
    for darts in visits:
        thrown: list[dict] = []
        for name, shown in darts:
            thrown.append(at(name))
            control({"event": "Throw detected", "throws": thrown})
            wait_card(page, shown)
            recorder.blink(6, step=120, hold=900)
        pull_darts()
        page.wait_for_timeout(900)
        recorder.blink(1, hold=1300)
    recorder.save("cricket")
    players(page, 1)


def training_game_animation(page: Page) -> None:
    """Around the Clock: every hit moves the target and its outlined beds."""
    pull_darts()
    game(page, "around_the_clock")
    wait_card(page, big("1"))
    recorder = Recorder(page)
    recorder.blink(1, hold=1200)
    for darts in (
        (("S1", "2"), ("S17", "2"), ("D2", "3")),
        (("T3", "4"), ("S4", "5"), ("S5", "6")),
    ):
        thrown: list[dict] = []
        for name, target in darts:
            thrown.append(at(name))
            control({"event": "Throw detected", "throws": thrown})
            wait_card(
                page,
                big(target)
                + " && r.querySelectorAll('.slot:not(.empty)').length === "
                + str(len(thrown)),
            )
            recorder.blink(6, step=120, hold=800)
        pull_darts()
        page.wait_for_timeout(600)
        recorder.blink(1, hold=900)
    recorder.save("training-game")
    game(page, "off")


def training_plan_animation(page: Page) -> None:
    """A training plan on the scoreboard: the idle screen offers the plan of the
    day, one tap starts it, and two taps on Skip move on to its next step. Not a
    dart lands, so the pictures after it show the same darts of the day."""
    pull_darts()
    game(page, "off")
    board = tablet(page)
    wait_card(board, "!!r.querySelector('.plan-offer')", SCOREBOARD, 60000)
    ready(board)
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1800)
    card = board.locator(SCOREBOARD)
    tap(board, recorder, card.locator(".plan-offer"), 300)
    wait_card(board, "!!r.querySelector('.plan-buttons')", SCOREBOARD)
    ready(board)
    recorder.shot(1800)
    skip = card.locator("[data-plan='skip']")
    tap(board, recorder, skip)
    tap(board, recorder, skip, 300)
    wait_card(board, "r.querySelector('.title')?.textContent.includes('2')", SCOREBOARD)
    ready(board)
    recorder.shot(2400)
    recorder.save("training-plan")
    board.close()
    # Another game ends the plan, and without a dart it counts for nothing.
    game(page, "off")


def scoreboard_animation(page: Page) -> None:
    """A 501 match on the scoreboard: turns pass, and Alex checks out 141."""
    pull_darts()
    page.evaluate(SET_NAME, [0, "Alex"])
    page.evaluate(SET_NAME, [1, "Sam"])
    players(page, 2)
    # One leg decides the match, so the checkout brings the winner banner.
    for key in ("practice_legs", "practice_sets"):
        page.evaluate(CALL_SERVICE, ["number", "set_value", key, {"value": 1}])
    game(page, "501")
    board = page.context.new_page()
    board.set_viewport_size({"width": 1280, "height": 800})
    board.goto(f"{HA}/homedarts-auto/scoreboard")
    tag = "homedarts-scoreboard-card"
    # The first load of the dashboard takes a while.
    wait_card(board, "r.querySelectorAll('.player').length === 2", tag, 60000)
    ready(board)
    recorder = Recorder(board, tag)
    recorder.shot(1400)
    active = "r.querySelector('.player.active .name')?.textContent === '{name}'"
    visits = [
        ("Alex", ["T20", "T20", "T20"], "Sam"),
        ("Sam", ["T20", "S5", "T20"], "Alex"),
        ("Alex", ["T20", "T20", "T20"], "Sam"),
        ("Sam", ["S20", "T20", "S20"], "Alex"),
    ]
    for _, names, following in visits:
        darts = [at(name) for name in names]
        for count in range(1, 4):
            control({"event": "Throw detected", "throws": darts[:count]})
            board.wait_for_timeout(350)
        wait_card(
            board, "r.querySelectorAll('.visit .dart:not(.empty)').length === 3", tag
        )
        recorder.shot(900)
        pull_darts()
        wait_card(board, active.format(name=following), tag)
        board.wait_for_timeout(300)
        recorder.shot(1000)
    thrown: list[dict] = []
    for name in ("T20", "T19", "D12"):
        thrown.append(at(name))
        control({"event": "Throw detected", "throws": thrown})
        wait_card(
            board,
            f"r.querySelectorAll('.visit .dart:not(.empty)').length === {len(thrown)}",
            tag,
        )
        board.wait_for_timeout(300)
        recorder.shot(1100)
    # The game shot shows at once; pulling the darts books the leg and the match.
    recorder.shot(900)
    pull_darts()
    wait_card(board, "!r.querySelector('.banner').hidden", tag)
    board.wait_for_timeout(300)
    recorder.shot(2600)
    recorder.save("scoreboard")
    board.close()
    players(page, 1)
    game(page, "off")


def scoreboard_match(page: Page, option: str) -> tuple[Page, Recorder]:
    """Alex against Sam in one leg of a game on the scoreboard, with its recorder."""
    pull_darts()
    page.evaluate(SET_NAME, [0, "Alex"])
    page.evaluate(SET_NAME, [1, "Sam"])
    players(page, 2)
    for key in ("practice_legs", "practice_sets"):
        page.evaluate(CALL_SERVICE, ["number", "set_value", key, {"value": 1}])
    game(page, option)
    board = page.context.new_page()
    board.set_viewport_size({"width": 1280, "height": 800})
    board.goto(f"{HA}/homedarts-auto/scoreboard")
    wait_card(
        board, "!!r.querySelector('.main .player, .main table')", SCOREBOARD, 60000
    )
    ready(board)
    return board, Recorder(board, SCOREBOARD)


def visit_shots(board: Page, recorder: Recorder, visits: list[list[str]]) -> None:
    """Every dart of the visits shown on its own, then the next player after the takeout."""
    for names in visits:
        darts: list[dict] = []
        for name in names:
            darts.append(at(name))
            control({"event": "Throw detected", "throws": darts})
            wait_card(
                board,
                f"r.querySelectorAll('.visit .dart:not(.empty)').length === {len(darts)}",
                SCOREBOARD,
            )
            board.wait_for_timeout(300)
            recorder.shot(1100)
        recorder.shot(700)
        # While the board is empty, the scoreboard shows the last visit.
        pull_darts()
        board.wait_for_timeout(900)
        recorder.shot(1400)


def wild_mouse_animation(page: Page) -> None:
    """Wild Mouse on the scoreboard: a T20 closes the 20, the next ones count for
    triples, three of them in one bed close 3 in a bed, and a dart that counts
    nothing is struck through."""
    board, recorder = scoreboard_match(page, "wild_mouse")
    recorder.shot(1400)
    visit_shots(
        board,
        recorder,
        [["T20", "T20", "T20"], ["T19", "D16", "S14"], ["T20", "D19", "S20"]],
    )
    recorder.save("wild-mouse")
    board.close()
    end_match(page)


def cricket_hints_animation(page: Page) -> None:
    """Cricket on the scoreboard: the column of the player at the board frames where
    a dart scores in green and what to close in amber; a dart that counted nothing
    is struck through."""
    board, recorder = scoreboard_match(page, "cricket")
    recorder.shot(1200)
    visit_shots(board, recorder, [["T20", "T19", "S5"], ["T20", "S19", "S1"]])
    recorder.save("cricket-hints")
    board.close()
    end_match(page)


def celebration_animation(page: Page) -> None:
    """A 180 on the scoreboard: a golden glow and confetti, gone again by itself."""
    board, recorder = scoreboard_match(page, "501")
    recorder.shot(1000)
    darts: list[dict] = []
    for name in ("T20", "T20"):
        darts.append(at(name))
        control({"event": "Throw detected", "throws": darts})
        wait_card(
            board,
            f"r.querySelectorAll('.visit .dart:not(.empty)').length === {len(darts)}",
            SCOREBOARD,
        )
        board.wait_for_timeout(300)
        recorder.shot(700)
    darts.append(at("T20"))
    control({"event": "Throw detected", "throws": darts})
    wait_card(board, "!!r.querySelector('.celebrate .moment.max')", SCOREBOARD)
    # The confetti frame by frame: the scoreboard's animations stand at each moment in
    # turn, before anything lets them run to their end.
    seek = SEEK.replace("'homedarts-card'", f"'{SCOREBOARD}'")
    for index in range(18):
        board.evaluate(seek, index * 140)
        recorder.shot(140 if index < 17 else 1600, wait=False)
    recorder.save("celebration")
    board.close()
    end_match(page)


def killer_animation(page: Page) -> None:
    """Killer for three on the scoreboard: numbers, killers, lives, the last one left."""
    pull_darts()
    for index, name in enumerate(("Alex", "Sam", "Kim")):
        page.evaluate(SET_NAME, [index, name])
    players(page, 3)
    for key in ("practice_legs", "practice_sets"):
        page.evaluate(CALL_SERVICE, ["number", "set_value", key, {"value": 1}])
    game(page, "killer")
    board = page.context.new_page()
    board.set_viewport_size({"width": 1280, "height": 800})
    board.goto(f"{HA}/homedarts-auto/scoreboard")
    tag = "homedarts-scoreboard-card"
    wait_card(board, "r.querySelectorAll('.player').length === 3", tag, 60000)
    ready(board)
    recorder = Recorder(board, tag)
    recorder.shot(1400)
    detail = "r.querySelectorAll('.player .details')[{0}]?.textContent.includes('{1}')"
    lives = "r.querySelectorAll('.player .big')[{0}]?.textContent === '{1}'"
    # Each visit with what the scoreboard shows after the darts are pulled.
    visits = [
        (["S7"], detail.format(0, "7")),
        (["S12"], detail.format(1, "12")),
        (["S3"], detail.format(2, "3")),
        (["D7", "D12", "D12"], lives.format(1, "♥")),
        (["S1"], detail.format(2, "3")),
        (["D3"], detail.format(2, "Killer")),
        (["D12", "D3", "D3"], lives.format(2, "♥")),
        (["S5"], lives.format(2, "♥")),
    ]
    for names, shown in visits:
        thrown: list[dict] = []
        for name in names:
            thrown.append(at(name))
            control({"event": "Throw detected", "throws": thrown})
            board.wait_for_timeout(500)
            if len(names) > 1:
                recorder.shot(700)
        pull_darts()
        wait_card(board, shown, tag)
        board.wait_for_timeout(400)
        recorder.shot(1000)
    control({"event": "Throw detected", "throws": [at("D3")]})
    wait_card(board, lives.format(2, "✕"), tag)
    board.wait_for_timeout(300)
    recorder.shot(1000)
    pull_darts()
    wait_card(board, "!r.querySelector('.banner').hidden", tag)
    board.wait_for_timeout(300)
    recorder.shot(2600)
    recorder.save("killer")
    board.close()
    players(page, 1)
    game(page, "off")


# A finger on the screen: a ring where the next tap lands, for the animations.
# A popover, because only that shows above the dialogs of Home Assistant.
TAP = """
([x, y]) => {
  const ring = document.createElement('div');
  ring.id = 'demo-tap';
  ring.popover = 'manual';
  ring.style.cssText = `position:fixed;inset:auto;margin:0;padding:0;left:${x - 24}px;top:${y - 24}px;width:48px;height:48px;` +
    'border-radius:50%;background:rgba(255,255,255,.3);border:3px solid rgba(255,255,255,.9);' +
    'box-shadow:0 0 14px rgba(0,0,0,.6);z-index:10000;pointer-events:none';
  document.body.append(ring);
  ring.showPopover();
}
"""
UNTAP = "() => document.getElementById('demo-tap')?.remove()"
SCOREBOARD = "homedarts-scoreboard-card"


def tap(page: Page, recorder: Recorder, target, hold: int = 800) -> None:
    """Show the finger on the target, tap it, and show what the tap changed."""
    box = target.bounding_box()
    page.evaluate(TAP, [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2])
    recorder.shot(450)
    page.evaluate(UNTAP)
    target.click()
    page.wait_for_timeout(300)
    recorder.shot(hold)


def tablet(page: Page, path: str = "homedarts-auto/scoreboard") -> Page:
    """A landscape tablet at the board, showing the scoreboard."""
    board = page.context.new_page()
    board.set_viewport_size({"width": 1280, "height": 800})
    board.goto(f"{HA}/{path}")
    return board


def lobby_animation(page: Page) -> None:
    """Choosing a game on the tablet: the game, a second player, the format, and go."""
    pull_darts()
    game(page, "off")
    page.evaluate(SET_NAME, [0, "Alex"])
    players(page, 1)
    board = tablet(page)
    wait_card(board, "!!r.querySelector('.lobby-cta')", SCOREBOARD, 60000)
    ready(board)
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1200)
    card = board.locator(SCOREBOARD)
    tap(board, recorder, card.locator(".lobby-cta"), 1200)
    tap(board, recorder, card.locator(".game[data-value='cricket']"))
    tap(board, recorder, card.locator(".suggestion", has_text="Sam"))
    tap(board, recorder, card.locator("[data-lobby='legs'][data-value='1']"))
    tap(board, recorder, card.locator("[data-lobby='legs'][data-value='1']"))
    tap(board, recorder, card.locator(".lobby .start"), 300)
    wait_card(board, "!!r.querySelector('.cricket')", SCOREBOARD)
    board.wait_for_timeout(800)
    recorder.shot(2800)
    recorder.save("lobby")
    board.close()
    players(page, 1)
    game(page, "off")


# Calls an action of the integration through the logged-in frontend.
CALL_ACTION = """
async ([service, data]) => {
  const hass = document.querySelector('home-assistant').hass;
  await hass.callService('homedarts', service, data);
}
"""


# Whether Home Assistant shows this many darts on the board.
DARTS_ON_BOARD = """
(darts) => {
  const hass = document.querySelector('home-assistant').hass;
  const entity = Object.values(hass.entities).find(
    (item) => item.platform === 'homedarts' && item.translation_key === 'num_throws'
  );
  return hass.states[entity.entity_id]?.state === String(darts);
}
"""


# Whether the tournament sensor's status is one of the given ones.
TOURNAMENT_IN = """
(statuses) => {
  const hass = document.querySelector('home-assistant').hass;
  const entity = Object.values(hass.entities).find(
    (item) => item.platform === 'homedarts' && item.translation_key === 'tournament'
      && item.entity_id.startsWith('sensor.')
  );
  return statuses.includes(hass.states[entity.entity_id]?.attributes.status);
}
"""


# Playing comfort -----------------------------------------------------------------


def bot_match(
    page: Page, level: int, delay: float, starts: list[int] | None = None
) -> None:
    """Alex against the bot, which throws after a pause of its own."""
    pull_darts()
    game(page, "off")
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_bot_delay", {"value": delay}]
    )
    data = {
        "game": "301",
        "players": ["Alex"],
        "legs": 1,
        "sets": 1,
        "bot_level": level,
    }
    page.evaluate(
        CALL_ACTION,
        ["start_game", {**data, **({"start_scores": starts} if starts else {})}],
    )


def end_bot_match(page: Page) -> None:
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_bot_level", {"value": 0}]
    )
    page.evaluate(SET_START, [0, 0])
    page.evaluate(CALL_SERVICE, ["switch", "turn_off", "practice_manual_entry"])
    pull_darts()
    game(page, "off")


def bot_animation(page: Page) -> None:
    """A 301 match against the bot on the scoreboard: Alex throws, then the bot."""
    bot_match(page, 80, 0.9)
    board = tablet(page)
    active = "r.querySelector('.player.active .name')?.textContent.startsWith('{name}')"
    wait_card(board, "r.querySelectorAll('.player').length === 2", SCOREBOARD, 60000)
    ready(board)
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1400)
    bot = "Bot"
    for names in (["T20", "T19", "T20"], ["S20", "T20", "S5"]):
        darts = [at(name) for name in names]
        for count in range(1, 4):
            control({"event": "Throw detected", "throws": darts[:count]})
            board.wait_for_timeout(350)
        wait_card(
            board,
            "r.querySelectorAll('.visit .dart:not(.empty)').length === 3",
            SCOREBOARD,
        )
        recorder.shot(900)
        pull_darts()
        wait_card(board, active.format(name=bot), SCOREBOARD)
        recorder.shot(700)
        # The bot's darts land one by one, like detected ones.
        for count in range(1, 4):
            wait_card(
                board,
                f"r.querySelectorAll('.visit .dart.bot').length >= {count}",
                SCOREBOARD,
            )
            board.wait_for_timeout(150)
            recorder.shot(700)
        wait_card(board, active.format(name="Alex"), SCOREBOARD)
        board.wait_for_timeout(300)
        recorder.shot(1400)
    recorder.save("bot-match")
    board.close()
    end_bot_match(page)


def correct_animation(page: Page) -> None:
    """A single 20 the board read where a treble 20 is, corrected with two taps."""
    pull_darts()
    page.evaluate(SET_NAME, [0, "Alex"])
    players(page, 1)
    game(page, "501")
    board = tablet(page)
    wait_card(board, "r.querySelectorAll('.player').length === 1", SCOREBOARD, 60000)
    ready(board)
    recorder = Recorder(board, SCOREBOARD)
    darts = [at("T20"), at("S20"), at("T20")]
    for count in range(1, 4):
        control({"event": "Throw detected", "throws": darts[:count]})
        board.wait_for_timeout(350)
    wait_card(
        board, "r.querySelector('.sum .value')?.textContent === '140'", SCOREBOARD
    )
    recorder.shot(1400)
    card = board.locator(SCOREBOARD)
    tap(board, recorder, card.locator("[data-dart='2']"), 1000)
    tap(board, recorder, card.locator("[data-pad='multiplier'][data-value='3']"), 700)
    tap(board, recorder, card.locator(".pad-number[data-value='T20']"), 300)
    wait_card(
        board, "r.querySelector('.sum .value')?.textContent === '180'", SCOREBOARD
    )
    board.wait_for_timeout(300)
    recorder.shot(2400)
    recorder.save("correct-dart")
    board.close()
    pull_darts()
    game(page, "off")


def tap_spot(
    page: Page, recorder: Recorder, board, x: float, y: float, hold: int
) -> None:
    """Tap the pad's board where a dart is, at a position as the board reports it."""
    box = board.bounding_box()
    scale = min(box["width"], box["height"]) / 460
    spot = {
        "x": box["width"] / 2 + x * 170 * scale,
        "y": box["height"] / 2 - y * 170 * scale,
    }
    page.evaluate(TAP, [box["x"] + spot["x"], box["y"] + spot["y"]])
    recorder.shot(450)
    page.evaluate(UNTAP)
    board.click(position=spot)
    page.wait_for_timeout(300)
    recorder.shot(hold)


def correct_board_animation(page: Page) -> None:
    """A single 20 the board read as a treble 20, put where it is on the pad's board."""
    pull_darts()
    page.evaluate(SET_NAME, [0, "Alex"])
    players(page, 1)
    game(page, "501")
    board = tablet(page)
    wait_card(board, "r.querySelectorAll('.player').length === 1", SCOREBOARD, 60000)
    ready(board)
    recorder = Recorder(board, SCOREBOARD)
    # The board saw the second dart in the treble, below the single 20 where it is.
    misread = {**at("T20"), "coords": {"x": 0.03, "y": 0.625}}
    darts = [at("T20"), misread, at("T20")]
    for count in range(1, 4):
        control({"event": "Throw detected", "throws": darts[:count]})
        board.wait_for_timeout(350)
    wait_card(
        board, "r.querySelector('.sum .value')?.textContent === '180'", SCOREBOARD
    )
    recorder.shot(1400)
    card = board.locator(SCOREBOARD)
    tap(board, recorder, card.locator("[data-dart='2']"), 900)
    tap(board, recorder, card.locator("[data-pad='board']"), 1400)
    tap_spot(board, recorder, card.locator(".pad-board"), 0.03, 0.8, 300)
    wait_card(
        board, "r.querySelector('.sum .value')?.textContent === '140'", SCOREBOARD
    )
    board.wait_for_timeout(300)
    recorder.shot(2400)
    recorder.save("correct-dart-board")
    board.close()
    pull_darts()
    game(page, "off")


# The part of the pad's board in sight, and where the board is on the screen.
BOARD_VIEW = """
(el) => {
  const [x, y, size] = el.getAttribute('viewBox').split(' ').map(Number);
  const rect = el.getBoundingClientRect();
  return { x, y, size, left: rect.left, top: rect.top, width: rect.width, height: rect.height };
}
"""


def board_point(view: dict, x: float, y: float) -> tuple[float, float]:
    """Where a position as the board reports it is on the screen, zoomed in or not."""
    scale = min(view["width"], view["height"]) / view["size"]
    middle = (view["x"] + view["size"] / 2, view["y"] + view["size"] / 2)
    return (
        view["left"] + view["width"] / 2 + (x * 170 - middle[0]) * scale,
        view["top"] + view["height"] / 2 + (-y * 170 - middle[1]) * scale,
    )


def correct_loupe_animation(page: Page) -> None:
    """The misread single 20 on a phone: the board opens zoomed in on where the board
    saw the dart, and a finger slides the loupe up to the single 20 and lets go."""
    pull_darts()
    page.evaluate(SET_NAME, [0, "Alex"])
    players(page, 1)
    game(page, "501")
    context = own_context(
        page,
        viewport={"width": 393, "height": 852},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
    )
    phone = context.new_page()
    phone.goto(f"{HA}/homedarts-auto/scoreboard")
    wait_card(phone, "r.querySelectorAll('.player').length === 1", SCOREBOARD, 60000)
    ready(phone)
    recorder = Recorder(phone, SCOREBOARD)
    misread = {**at("T20"), "coords": {"x": 0.03, "y": 0.625}}
    darts = [at("T20"), misread, at("T20")]
    for count in range(1, 4):
        control({"event": "Throw detected", "throws": darts[:count]})
        phone.wait_for_timeout(350)
    wait_card(
        phone, "r.querySelector('.sum .value')?.textContent === '180'", SCOREBOARD
    )
    recorder.shot(1400)
    card = phone.locator(SCOREBOARD)
    tap(phone, recorder, card.locator("[data-dart='2']"), 900)
    tap(phone, recorder, card.locator("[data-pad='board']"), 1600)
    # The finger lands a little off and slides up to the single 20, where it rests
    # and lets go: the loupe above it shows where the dart goes.
    view = card.locator(".pad-board").evaluate(BOARD_VIEW)
    path = [board_point(view, 0.06, y) for y in (0.66, 0.7, 0.75, 0.8)]
    session = context.new_cdp_session(phone)

    def finger(kind: str, point: tuple[float, float] | None) -> None:
        points = [{"x": point[0], "y": point[1], "id": 0}] if point else []
        session.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": points})
        phone.evaluate(UNTAP)
        if point:
            phone.evaluate(TAP, list(point))

    finger("touchStart", path[0])
    phone.wait_for_timeout(200)
    recorder.shot(900)
    for index, point in enumerate(path[1:], 1):
        finger("touchMove", point)
        phone.wait_for_timeout(150)
        recorder.shot(1600 if index == len(path) - 1 else 350)
    finger("touchEnd", None)
    session.detach()
    wait_card(
        phone, "r.querySelector('.sum .value')?.textContent === '140'", SCOREBOARD
    )
    phone.wait_for_timeout(300)
    recorder.shot(2400)
    recorder.save("correct-dart-loupe", width=480)
    context.close()
    pull_darts()
    game(page, "off")


def keypad_screen(page: Page) -> None:
    """The keypad for darts entered by hand, with two darts of the visit entered."""
    bot_match(page, 60, 2)
    page.evaluate(CALL_SERVICE, ["switch", "turn_on", "practice_manual_entry"])
    board = tablet(page, "homedarts-demo/keypad")
    wait_card(board, "!!r.querySelector('.pad')", SCOREBOARD, 60000)
    for segment in ("T20", "S19"):
        board.evaluate(CALL_ACTION, ["throw_dart", {"segment": segment}])
    wait_card(
        board, "r.querySelectorAll('.visit .dart.manual').length === 2", SCOREBOARD
    )
    board.set_viewport_size({"width": 1280, "height": 1000})
    board.wait_for_timeout(1000)
    card_shot(board, "scoreboard-keypad", tag=SCOREBOARD)
    board.close()
    end_bot_match(page)


def bot_scoreboard(page: Page) -> None:
    """Alex at 169 against the bot: the setup that leaves 32 instead of a checkout."""
    bot_match(page, 80, 10, [169])
    board = tablet(page)
    wait_card(board, "!!r.querySelector('.setup')", SCOREBOARD, 60000)
    board.wait_for_timeout(1200)
    card_shot(board, "scoreboard-bot", tag=SCOREBOARD)
    board.close()
    end_bot_match(page)


def lobby_bot(page: Page) -> None:
    """The new game screen with the bot seated after Alex."""
    pull_darts()
    game(page, "off")
    page.evaluate(SET_NAME, [0, "Alex"])
    players(page, 1)
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_bot_level", {"value": 70}]
    )
    board = tablet(page)
    wait_card(board, "!!r.querySelector('.lobby-cta')", SCOREBOARD, 60000)
    board.locator(SCOREBOARD).locator(".lobby-cta").click()
    wait_card(board, "!!r.querySelector('.lobby-player.bot')", SCOREBOARD)
    board.wait_for_timeout(1000)
    page_shot(board, "lobby-bot")
    board.close()
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_bot_level", {"value": 0}]
    )


def seek_scoreboard(board: Page, time: int) -> None:
    """Pause the animations of the scoreboard at a given time, for a frame."""
    board.evaluate(
        "(time) => { for (const card of ("
        + find(SCOREBOARD)
        + ")()) { for (const animation of card.shadowRoot.getAnimations()) {"
        " animation.pause(); animation.currentTime = time; } } }",
        time,
    )


def checkout_101(page: Page, loser: list[str] | None = None) -> None:
    """The first player checks out 101 in one visit, or misses and the second does."""
    if loser:
        visit(page, loser)
    visit(page, ["T20", "S1", "D20"])


def start_tournament_of_five(page: Page) -> None:
    """A knockout of five with a match for third place, 101 in one leg each."""
    pull_darts()
    game(page, "off")
    page.evaluate(
        CALL_ACTION,
        [
            "start_tournament",
            {
                "players": ["Alex", "Sam", "Kim", "Lea", "Max"],
                "format": "knockout",
                "game": "101",
                "legs": 1,
                "sets": 1,
                "double_out": True,
                "bull_off": False,
                "third_place": True,
                "pause": 0,
                # The table or the bracket right after a result.
                "summary": 1,
            },
        ],
    )


def tournament_bracket_animation(page: Page) -> None:
    """A knockout of five filling its bracket: every winner slides into the next round."""
    start_tournament_of_five(page)
    board = tablet(page, "homedarts-demo/tournament")
    wait_card(board, "r.querySelectorAll('.player').length === 2", SCOREBOARD, 60000)
    ready(board)
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1600)
    # Lea, Alex, Kim after Sam's miss, Lea for third place and Alex win.
    misses = [None, None, ["S20", "S20", "S1"], None, None]
    for number, miss in enumerate(misses, 1):
        checkout_101(page, miss)
        wait_card(board, "!!r.querySelector('.bracket')", SCOREBOARD)
        board.wait_for_timeout(200)
        # The places filled by the result slide in, frame by frame.
        for time in (0, 250, 500, 800, 1600):
            seek_scoreboard(board, time)
            recorder.shot(160 if time < 1600 else 2200)
        if number < len(misses):
            page.evaluate(CALL_ACTION, ["next_tournament_match", {}])
            wait_card(board, "!r.querySelector('.bracket')", SCOREBOARD)
            board.wait_for_timeout(600)
            recorder.shot(1000)
    recorder.shot(1800)
    recorder.save("tournament-bracket")
    board.close()
    page.evaluate(CALL_ACTION, ["stop_tournament", {}])
    players(page, 1)
    game(page, "off")


def tournament_table(page: Page) -> None:
    """A round robin of four between two matches: the next match, the countdown, the table."""
    pull_darts()
    game(page, "off")
    page.evaluate(
        CALL_ACTION,
        [
            "start_tournament",
            {
                "players": ["Alex", "Sam", "Kim", "Lea"],
                "format": "round_robin",
                "game": "101",
                "legs": 1,
                "sets": 1,
                "double_out": True,
                "bull_off": False,
                "pause": 0,
                # The table or the bracket right after a result.
                "summary": 1,
            },
        ],
    )
    # Alex beats Lea, Sam beats Kim, then Alex beats Kim: Alex leads on 4 points.
    checkout_101(page)
    page.evaluate(CALL_ACTION, ["next_tournament_match", {}])
    checkout_101(page, ["S20", "S20", "S20"])
    page.evaluate(CALL_ACTION, ["next_tournament_match", {}])
    checkout_101(page, ["S1", "S1", "S1"])
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "tournament_pause", {"value": 90}]
    )
    board = tablet(page, "homedarts-demo/tournament")
    wait_card(board, "!!r.querySelector('.standings')", SCOREBOARD, 60000)
    ready(board)
    page_shot(board, "tournament-table")
    board.close()
    page.evaluate(CALL_ACTION, ["stop_tournament", {}])
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "tournament_pause", {"value": 10}]
    )
    players(page, 1)
    game(page, "off")


# The 32 players of the big tournaments.
FIELD = [
    "Alex", "Sam", "Kim", "Lea", "Max", "Tom", "Mia", "Ben",
    "Zoe", "Jan", "Ida", "Leo", "Amy", "Ole", "Eva", "Tim",
    "Lia", "Nik", "Ava", "Paul", "Ela", "Finn", "Nora", "Jonas",
    "Emma", "Luca", "Lina", "Theo", "Rosa", "Emil", "Ella", "Noah",
]  # fmt: skip


def quick_visit(page: Page, names: list[str]) -> None:
    """A visit that shows in no picture, such as in a match that only leads up to
    one: every move waits until Home Assistant took it, not a fixed time."""
    darts = [at(name) for name in names]
    for count in range(1, len(darts) + 1):
        control({"event": "Throw detected", "throws": darts[:count]})
        page.wait_for_function(DARTS_ON_BOARD, arg=count)
    pull_darts()
    page.wait_for_function(DARTS_ON_BOARD, arg=0)


def play_tournament(page: Page, matches: int) -> None:
    """Play the first `matches` matches of the tournament, most of them won by the
    first player and every third by the second."""
    for played in range(matches):
        if page.evaluate(TOURNAMENT_IN, ["waiting"]):
            page.evaluate(CALL_ACTION, ["next_tournament_match", {}])
            page.wait_for_function(TOURNAMENT_IN, arg=["playing"])
        if played % 3 == 2:
            quick_visit(page, ["S20", "S20", "S1"])
        quick_visit(page, ["T20", "S1", "D20"])
        page.wait_for_function(TOURNAMENT_IN, arg=["waiting", "finished"])


def players_matches(page: Page) -> None:
    """The matches of the players: a knockout of five, with no picture of it. The
    animation of its bracket plays the same matches in a group of its own."""
    start_tournament_of_five(page)
    page.wait_for_function(TOURNAMENT_IN, arg=["playing"])
    play_tournament(page, 5)
    page.evaluate(CALL_ACTION, ["stop_tournament", {}])
    players(page, 1)
    game(page, "off")


def big_tournament(
    page: Page, name: str, options: dict, before: int, shown: str, height: int
) -> None:
    """A tournament of 32 players through the practice game, with a picture of the
    scoreboard between two matches after `before` of them, once `shown` is on it,
    on a screen `height` high that shows all of it.

    The tournament stops right after its picture: the matches after it showed in
    no image, and tests/test_tournament_formats.py plays 32 players to their
    champion with many random results, in a fraction of a second instead of
    minutes."""
    pull_darts()
    game(page, "off")
    page.evaluate(
        CALL_ACTION,
        [
            "start_tournament",
            {
                "players": FIELD,
                **options,
                "game": "101",
                "legs": 1,
                "sets": 1,
                "double_out": True,
                "bull_off": False,
                "pause": 0,
                "summary": 1,
            },
        ],
    )
    play_tournament(page, before)
    # A pause with its countdown, long enough for the picture.
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "tournament_pause", {"value": 90}]
    )
    board = tablet(page, "homedarts-demo/tournament")
    board.set_viewport_size({"width": 1280, "height": height})
    wait_card(board, shown, SCOREBOARD, 60000)
    ready(board)
    card_shot(board, name, tag=SCOREBOARD)
    board.close()
    page.evaluate(CALL_ACTION, ["stop_tournament", {}])
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "tournament_pause", {"value": 10}]
    )
    players(page, 1)
    game(page, "off")


def tournament_groups(page: Page) -> None:
    """32 players in eight groups of four, two of each into a knockout of 16: the
    tables of the groups after two rounds, the places that go on marked."""
    big_tournament(
        page,
        "tournament-groups",
        {"format": "groups_knockout", "groups": 8, "advance": 2},
        # Two rounds of two matches in each of the eight groups.
        32,
        "!!r.querySelector('.groups')",
        # The eight tables, three side by side.
        960,
    )


def tournament_double(page: Page) -> None:
    """A double elimination of 32 players: the winners' bracket after its first
    round and the losers' bracket below it after its first."""
    big_tournament(
        page,
        "tournament-double",
        {"format": "double_knockout"},
        # The 16 matches of the winners' first round and the 8 of the losers'.
        24,
        "!!r.querySelector('.losers-label')",
        # The 16 matches of the winners' first round and the losers' bracket below.
        2520,
    )


def lobby_fair(page: Page) -> None:
    """The new game screen with a fair start: Alex and Sam by their averages."""
    pull_darts()
    game(page, "off")
    for index, name in enumerate(("Alex", "Sam")):
        page.evaluate(SET_NAME, [index, name])
    players(page, 2)
    board = tablet(page)
    # So high that the players with their start scores and the option fit together.
    board.set_viewport_size({"width": 1280, "height": 1100})
    wait_card(board, "!!r.querySelector('.lobby-cta')", SCOREBOARD, 60000)
    card = board.locator(SCOREBOARD)
    card.locator(".lobby-cta").click()
    wait_card(board, "!!r.querySelector('.lobby')", SCOREBOARD)
    card.locator("[data-lobby='toggle'][data-value='fair_start']").click()
    wait_card(board, "!!r.querySelector('.lobby-start.own')", SCOREBOARD)
    board.wait_for_timeout(1000)
    page_shot(board, "lobby-fair")
    board.close()
    players(page, 1)


def tournament_lobby(page: Page) -> None:
    """The new game screen in tournament mode: six players, a knockout with third place."""
    pull_darts()
    game(page, "off")
    board = tablet(page)
    wait_card(board, "!!r.querySelector('.lobby-cta')", SCOREBOARD, 60000)
    card = board.locator(SCOREBOARD)
    card.locator(".lobby-cta").click()
    wait_card(board, "!!r.querySelector('.lobby-mode')", SCOREBOARD)
    card.locator("[data-lobby='mode'][data-value='tournament']").click()
    for name in ("Alex", "Sam", "Kim", "Lea", "Max", "Tom"):
        suggestion = card.locator(".suggestion", has_text=name)
        if suggestion.count():
            suggestion.first.click()
        else:
            card.locator(".lobby-name").fill(name)
            card.locator("[data-lobby='add-name']").click()
    card.locator("[data-lobby='format'][data-value='knockout']").click()
    card.locator("[data-lobby='toggle'][data-value='third_place']").click()
    board.wait_for_timeout(1000)
    # Six players and the rules are taller than a tablet; the card shows them all.
    card_shot(board, "tournament-lobby", tag=SCOREBOARD)
    board.close()


def lobby_screen(page: Page) -> None:
    """The new game screen: two players at home, Sam from 301, three legs per set."""
    pull_darts()
    game(page, "off")
    for index, name in enumerate(("Alex", "Sam")):
        page.evaluate(SET_NAME, [index, name])
    players(page, 2)
    page.evaluate(CALL_SERVICE, ["number", "set_value", "practice_legs", {"value": 1}])
    board = tablet(page)
    wait_card(board, "!!r.querySelector('.lobby-cta')", SCOREBOARD, 60000)
    card = board.locator(SCOREBOARD)
    card.locator(".lobby-cta").click()
    wait_card(board, "!!r.querySelector('.lobby')", SCOREBOARD)
    for _ in range(2):
        card.locator("[data-lobby='legs'][data-value='1']").click()
        card.locator("[data-lobby='lower'][data-value='1']").click()
    board.wait_for_timeout(1000)
    page_shot(board, "scoreboard-lobby")
    board.close()
    players(page, 1)


def idle_screen(page: Page) -> None:
    """Idle mode: the leaderboard of the demo players, with their pictures."""
    pull_darts()
    game(page, "off")
    board = tablet(page, "homedarts-demo/idle")
    wait_card(
        board,
        "r.querySelector('.idle-panel')?.dataset.panel === 'leaderboard'",
        SCOREBOARD,
        60000,
    )
    board.wait_for_timeout(1500)
    page_shot(board, "scoreboard-idle")
    board.close()


def media_gallery(page: Page) -> None:
    """The highlight photos of September in the media browser."""
    # Low enough for the month without a screen full of nothing below it.
    page.set_viewport_size({"width": 1280, "height": 640})
    page.goto(
        f"{HA}/media-browser/browser/app%2Cmedia-source%3A%2F%2Fhomedarts"
        "/directory%2Cmedia-source%3A%2F%2Fhomedarts%2F2026-09"
    )
    # The title of a photo also sits in its hidden tooltip.
    page.get_by_text("180 · Alex").filter(visible=True).first.wait_for(timeout=30000)
    page.wait_for_timeout(3000)
    page_shot(page, "media-gallery")


# The new games ---------------------------------------------------------------


def inner(number: int) -> dict:
    """A single inside the treble ring, which Golf counts as three strokes."""
    angle = math.radians(90 - ORDER.index(number) * 18)
    return {
        "segment": {"name": f"S{number}", "number": number, "multiplier": 1},
        "coords": {
            "x": round(0.4 * math.cos(angle), 3),
            "y": round(0.4 * math.sin(angle), 3),
        },
    }


def match_of(page: Page, names: list[str], option: str) -> Page:
    """A match of these players; returns the scoreboard view at the board."""
    pull_darts()
    for index, name in enumerate(names):
        page.evaluate(SET_NAME, [index, name])
    players(page, len(names))
    for key, value in (("practice_legs", 2), ("practice_sets", 1)):
        page.evaluate(CALL_SERVICE, ["number", "set_value", key, {"value": value}])
    game(page, option)
    board = page.context.new_page()
    board.set_viewport_size({"width": 1280, "height": 800})
    board.goto(f"{HA}/homedarts-auto/scoreboard")
    wait_card(
        board, "!!r.querySelector('.main .player, .main table')", SCOREBOARD, 60000
    )
    ready(board)
    return board


def throw_visits(board: Page, visits: list[list[dict]]) -> None:
    for darts in visits:
        for count in range(1, len(darts) + 1):
            control({"event": "Throw detected", "throws": darts[:count]})
            board.wait_for_timeout(250)
        pull_darts()
        board.wait_for_timeout(500)


def end_match(page: Page) -> None:
    players(page, 1)
    for index in range(4):
        page.evaluate(SET_START, [index, 0])
    page.evaluate(CALL_SERVICE, ["switch", "turn_off", "practice_teams", {}])
    game(page, "off")


def tactics_scoreboard(page: Page) -> None:
    """Tactics on the scoreboard: the chalkboard runs down to 10."""
    board = match_of(page, ["Alex", "Sam"], "tactics")
    throw_visits(
        board,
        [
            [at("T20"), at("T20"), at("S19")],
            [at("T20"), at("T19"), at("S18")],
            [at("T19"), at("T18"), at("D17")],
            [at("T18"), at("D17"), at("S16")],
            [at("T17"), at("T16"), at("T15")],
            [at("S17"), at("T16"), at("D15")],
            [at("T14"), at("T13"), at("S12")],
        ],
    )
    control({"event": "Throw detected", "throws": [at("T12")]})
    wait_card(
        board,
        "r.querySelectorAll('.cricket tbody tr')[8]?.children[2]?.textContent === 'Ⓧ'",
        SCOREBOARD,
    )
    board.wait_for_timeout(800)
    page_shot(board, "scoreboard-tactics")
    board.close()
    end_match(page)


def wild_mouse_scoreboard(page: Page) -> None:
    """Wild Mouse on the scoreboard: doubles, triples and three in a bed below the
    numbers, and the frames of where the player at the board scores or closes."""
    board = match_of(page, ["Alex", "Sam"], "wild_mouse")
    throw_visits(
        board,
        [
            [at("T20"), at("T20"), at("T20")],
            [at("T19"), at("D16"), at("S18")],
            [at("T19"), at("D5"), at("S14")],
            [at("T20"), at("S17"), at("D3")],
        ],
    )
    control({"event": "Throw detected", "throws": [at("T18")]})
    wait_card(
        board,
        "r.querySelectorAll('.cricket tbody tr')[2]?.children[1]?.textContent === 'Ⓧ'",
        SCOREBOARD,
    )
    board.wait_for_timeout(800)
    page_shot(board, "scoreboard-wild-mouse")
    board.close()
    end_match(page)


def party_scoreboard(page: Page) -> None:
    """Killer for a party of eight on the scoreboard, in two rows of four tiles."""
    pull_darts()
    game(page, "killer")
    names = ["Alex", "Sam", "Kim", "Lea", "Mia", "Leo", "Zoe", "Ben"]
    for index, name in enumerate(names):
        page.evaluate(SET_NAME, [index, name])
    players(page, len(names))
    for key in ("practice_legs", "practice_sets"):
        page.evaluate(CALL_SERVICE, ["number", "set_value", key, {"value": 1}])
    board = page.context.new_page()
    board.set_viewport_size({"width": 1280, "height": 800})
    board.goto(f"{HA}/homedarts-auto/scoreboard")
    wait_card(
        board, "r.querySelectorAll('.main .player').length === 8", SCOREBOARD, 60000
    )
    board.wait_for_timeout(1500)
    # Everybody throws for a number, then Alex becomes a killer and takes a life.
    numbers = ["S7", "S12", "S3", "S18", "S9", "S14", "S20", "S5"]
    throw_visits(board, [[at(number)] for number in numbers])
    control({"event": "Throw detected", "throws": [at("D7"), at("D12")]})
    wait_card(
        board,
        "r.querySelectorAll('.main .player')[1]?.querySelector('.big')?.textContent === '♥♥'",
        SCOREBOARD,
    )
    board.wait_for_timeout(800)
    page_shot(board, "scoreboard-party")
    board.close()
    end_match(page)


def teams_scoreboard(page: Page) -> None:
    """A team match of four on the scoreboard, the partner at the board outlined."""
    page.evaluate(CALL_SERVICE, ["switch", "turn_on", "practice_teams", {}])
    board = match_of(page, ["Alex", "Sam", "Kim", "Lea"], "501")
    throw_visits(
        board,
        [
            [at("T20"), at("T20"), at("T20")],
            [at("T20"), at("S20"), at("T20")],
            [at("T20"), at("T19"), at("S19")],
            [at("S20"), at("T20"), at("S5")],
            [at("T20"), at("T20"), at("S20")],
        ],
    )
    control({"event": "Throw detected", "throws": [at("T20")]})
    wait_card(board, "r.querySelector('.player.active .members b')", SCOREBOARD)
    board.wait_for_timeout(800)
    page_shot(board, "scoreboard-teams")
    board.close()
    end_match(page)


def handicap_scoreboard(page: Page) -> None:
    """Sam starts from 301 against Alex's 501."""
    page.evaluate(SET_START, [1, 301])
    board = match_of(page, ["Alex", "Sam"], "501")
    throw_visits(board, [[at("T20"), at("T20"), at("S20")]])
    control({"event": "Throw detected", "throws": [at("T20")]})
    wait_card(board, "r.querySelectorAll('.player .badge').length === 2", SCOREBOARD)
    board.wait_for_timeout(800)
    page_shot(board, "scoreboard-handicap")
    board.close()
    end_match(page)


def golf_animation(page: Page) -> None:
    """Golf for two on the scoreboard: the scorecard fills hole by hole."""
    page.evaluate(
        CALL_SERVICE,
        ["select", "select_option", "practice_golf_holes", {"option": "9"}],
    )
    board = match_of(page, ["Alex", "Sam"], "golf")
    wait_card(board, "!!r.querySelector('.scorecard')", SCOREBOARD)
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1400)
    holes = [
        [at("T1")],
        [at("S2"), at("S1")],
        [inner(2)],
        [at("T3"), at("S3")],
        [at("D3")],
        [at("S5"), at("T4")],
        [at("S4"), at("D4")],
    ]
    for darts in holes:
        for count in range(1, len(darts) + 1):
            control({"event": "Throw detected", "throws": darts[:count]})
            board.wait_for_timeout(500)
            recorder.shot(700)
        pull_darts()
        board.wait_for_timeout(700)
        recorder.shot(900)
    recorder.shot(1600)
    recorder.save("golf")
    board.close()
    end_match(page)


def checkout_121_animation(page: Page) -> None:
    """The 121 checkout: a finish climbs to 122."""
    pull_darts()
    game(page, "checkout_121")
    wait_card(page, big("121"))
    recorder = Recorder(page)
    recorder.blink(1, hold=1400)
    for darts, remaining in (
        ([at("T20"), at("S1"), at("S20")], "40"),
        ([at("D20")], "0"),
    ):
        thrown: list[dict] = []
        for name in darts:
            thrown.append(name)
            control({"event": "Throw detected", "throws": thrown})
            page.wait_for_timeout(500)
            recorder.blink(8, step=120, hold=900)
        wait_card(page, big(remaining))
        recorder.blink(1, hold=1200)
        pull_darts()
        page.wait_for_timeout(700)
    wait_card(page, big("122"))
    recorder.blink(1, hold=1800)
    recorder.save("checkout-121")
    game(page, "off")


def doubles_card(page: Page) -> None:
    """The doubles card after a doubles training with a few misses per double."""
    open_dashboard(page, "board")
    pull_darts()
    game(page, "doubles")
    for number in range(1, 13):
        misses = (number * 3) % 7
        darts = [at(f"S{number}")] * misses + [at(f"D{number}")]
        for start in range(0, len(darts), 3):
            visit = darts[start : start + 3]
            for count in range(1, len(visit) + 1):
                control({"event": "Throw detected", "throws": visit[:count]})
                page.wait_for_timeout(200)
            pull_darts()
            page.wait_for_timeout(300)
    game(page, "off")
    page.goto(f"{HA}/homedarts-auto/training")
    page.wait_for_function(
        f"() => ({find('homedarts-doubles-card')})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.double').length >= 10)",
        timeout=60000,
    )
    ready(page)
    card_shot(page, "doubles-card", tag="homedarts-doubles-card")


def players_card(page: Page) -> None:
    """The players card after the matches of the animations."""
    page.goto(f"{HA}/homedarts-auto/players")
    page.wait_for_function(
        f"() => ({find('homedarts-players-card')})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.profile').length >= 2)",
        timeout=60000,
    )
    # Badges, trends and groupings have pictures of their own.
    page.evaluate(
        f"() => ({find('homedarts-players-card')})().forEach((card) => card.setConfig("
        "{...card._config, show_badges: false, show_trends: false, show_spread: false}))"
    )
    ready(page)
    card_shot(page, "players-card", tag="homedarts-players-card")


# The box of some parts of a card, scrolled below the toolbar: the card's full
# width, from the first part to the last.
PARTS = """
([tag, selectors]) => {
  const cards = [];
  (function collect(root) {
    root.querySelectorAll(tag).forEach((card) => cards.push(card));
    root.querySelectorAll('*').forEach((el) => el.shadowRoot && collect(el.shadowRoot));
  })(document);
  const card = cards[0];
  const parts = selectors.map((selector) => card.shadowRoot.querySelector(selector));
  parts[0].scrollIntoView();
  window.scrollBy(0, -100);
  const frame = card.getBoundingClientRect();
  const boxes = parts.map((part) => part.getBoundingClientRect());
  const top = Math.min(...boxes.map((box) => box.top)) - 16;
  const bottom = Math.max(...boxes.map((box) => box.bottom)) + 16;
  return { x: frame.left, y: top, width: frame.width, height: bottom - top };
}
"""


def part_shot(page: Page, name: str, tag: str, selectors: list[str]) -> None:
    """A part of a card, such as one of its sections, across the card's width."""
    clip = page.evaluate(PARTS, [tag, selectors])
    settle(page)
    page.screenshot(path=str(OUTPUT / f"{name}.png"), clip=clip)
    saved(OUTPUT / f"{name}.png")


def progress_cards(page: Page) -> None:
    """Badges, trends and groupings of the demo players, Alex's darts and aim map,
    and the records."""
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"], "height": 2000})
    players = "homedarts-players-card"
    page.goto(f"{HA}/homedarts-demo/progress")
    page.wait_for_function(
        f"() => ({find(players)})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.trend .spark').length >= 10"
        " && c.shadowRoot.querySelectorAll('.badge').length >= 10"
        " && c.shadowRoot.querySelectorAll('.group').length >= 3)",
        timeout=60000,
    )
    ready(page)
    part_shot(
        page,
        "players-badges",
        players,
        [".badges-section .section-head", ".badge-player"],
    )
    part_shot(page, "players-trends", players, [".trends-section", ".groups-section"])
    training = "homedarts-training-card"
    page.goto(f"{HA}/homedarts-demo/positions")
    page.wait_for_function(
        f"() => ({find(training)})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.heat-layer .position').length > 100"
        " && c.shadowRoot.querySelectorAll('.heat .group').length >= 2)",
        timeout=60000,
    )
    ready(page)
    part_shot(page, "training-positions", training, [".heat"])
    # Alex's aim map, which the worker of the card draws from Alex's spread.
    page.locator(f"{training} button[data-mode='aim']").click()
    page.wait_for_function(
        f"() => ({find(training)})().some((c) =>"
        " c.shadowRoot.querySelector('.heat-layer .aim-best')"
        " && c.shadowRoot.querySelectorAll('.heat .group').length >= 2)",
        timeout=60000,
    )
    ready(page)
    part_shot(page, "training-aim", training, [".heat"])
    page.goto(f"{HA}/homedarts-demo/leaderboard")
    page.wait_for_function(
        f"() => ({find('homedarts-leaderboard-card')})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.record').length >= 7)",
        timeout=60000,
    )
    ready(page)
    card_shot(page, "leaderboard-card", tag="homedarts-leaderboard-card")
    page.set_viewport_size(size)


def heatmap_animation(page: Page) -> None:
    """The heatmap from beds to numbers and positions, then Alex's own darts."""
    tag = "homedarts-training-card"
    page.goto(f"{HA}/homedarts-demo/positions")
    page.wait_for_function(
        f"() => ({find(tag)})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.heat-layer .position').length > 100)",
        timeout=60000,
    )
    # The heatmap of the card, where the switches are.
    recorder = Recorder(page, f"{tag} .heat")

    def show(selector: str, ready: str, hold: int) -> None:
        page.locator(f"{tag} {selector}").click()
        page.wait_for_function(
            f"() => ({find(tag)})()[0].shadowRoot.querySelector('{ready}')",
            timeout=30000,
        )
        page.wait_for_timeout(700)
        recorder.shot(hold)

    show("button[data-source='']", 'button[data-source=""][aria-pressed=true]', 200)
    show("button[data-mode='beds']", ".heat-layer .heat-bed", 1800)
    show(
        "button[data-mode='numbers']",
        "button[data-mode=numbers][aria-pressed=true]",
        1800,
    )
    show("button[data-mode='positions']", ".heat-layer .position", 1800)
    show(
        "button[data-source='Alex']",
        "button[data-source=Alex][aria-pressed=true]",
        2400,
    )
    show("button[data-mode='beds']", "button[data-mode=beds][aria-pressed=true]", 2400)
    # The first frame only prepared the session; the animation starts with its beds.
    recorder.frames.pop(0)
    recorder.durations.pop(0)
    # Groupings make some frames taller; every frame gets the size of the tallest.
    size = (
        max(frame.width for frame in recorder.frames),
        max(frame.height for frame in recorder.frames),
    )
    frames = []
    for frame in recorder.frames:
        frame = frame.convert("RGB")
        canvas = Image.new("RGB", size, frame.getpixel((2, 2)))
        canvas.paste(frame, (0, 0))
        frames.append(canvas)
    recorder.frames = frames
    recorder.save("heatmap-modes", width=520)


def scoreboard_page(page: Page) -> Page:
    """The scoreboard view of the generated dashboard, as on a tablet at the board."""
    board = page.context.new_page()
    board.set_viewport_size({"width": 1280, "height": 800})
    board.goto(f"{HA}/homedarts-auto/scoreboard")
    board.wait_for_function(
        f"() => ({find('homedarts-scoreboard-card')})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.player').length === 2)",
        timeout=60000,
    )
    ready(board)
    return board


def match_summary(page: Page) -> None:
    """The scoreboard after Alex beats Sam 2 : 1 in 301: the summary of the match."""
    pull_darts()
    page.evaluate(SET_NAME, [0, "Alex"])
    page.evaluate(SET_NAME, [1, "Sam"])
    players(page, 2)
    for key, value in (("practice_legs", 2), ("practice_sets", 1)):
        page.evaluate(CALL_SERVICE, ["number", "set_value", key, {"value": value}])
    game(page, "301")
    board = scoreboard_page(page)
    tag = "homedarts-scoreboard-card"
    visits = [
        # Leg 1: Alex scores 180 and checks out 121.
        ["T20", "T20", "T20"],
        ["T20", "S20", "S5"],
        ["T20", "T11", "D14"],
        # Leg 2: Sam scores 140 and checks out 161 on the bull.
        ["T20", "T20", "S20"],
        ["T19", "S19", "S3"],
        ["T20", "T17", "BULL"],
        # Leg 3: Sam's 180 is too late; Alex misses D17 and takes D1.
        ["T20", "T20", "S20"],
        ["S20", "S20", "S20"],
        ["T20", "T19", "S10"],
        ["T20", "T20", "T20"],
        ["D16", "D1"],
    ]
    for names in visits:
        darts = [BULL if name == "BULL" else at(name) for name in names]
        for count in range(1, len(darts) + 1):
            control({"event": "Throw detected", "throws": darts[:count]})
            board.wait_for_timeout(250)
        pull_darts()
        wait_card(board, "!r.querySelector('.visit .dart:not(.empty)')", tag)
        board.wait_for_timeout(400)
    wait_card(board, "r.querySelector('.summary')", tag)
    # A taller screen keeps the whole card below the toolbar of Home Assistant.
    board.set_viewport_size({"width": 1280, "height": 1000})
    board.wait_for_timeout(800)
    card_shot(board, "match-summary", tag=tag)
    board.close()
    players(page, 1)
    game(page, "off")


def practice_card(page: Page) -> None:
    """A 501 match in the live card, and the scoreboard in Cricket."""

    def service(option: str) -> None:
        page.evaluate(
            CALL_SERVICE,
            ["select", "select_option", "practice_game", {"option": option}],
        )

    def takeout() -> None:
        control({"status": "Takeout in progress", "event": "Takeout started"})
        control({"status": "Throw", "event": "Takeout finished", "throws": []})
        wait_for_score(page, "0")

    # A 501 match of two players, three legs to win.
    takeout()
    service("501")
    page.evaluate(SET_NAME, [0, "Alex"])
    page.evaluate(SET_NAME, [1, "Sam"])
    for key, value in (("practice_players", 2), ("practice_legs", 3)):
        page.evaluate(CALL_SERVICE, ["number", "set_value", key, {"value": value}])
    for visit in ([T20] * 3, [T20, S5, S5], [T20] * 3, [T20, S5, S5]):
        for count in range(1, len(visit) + 1):
            control({"event": "Throw detected", "throws": visit[:count]})
            page.wait_for_timeout(300)
        takeout()
    control({"event": "Throw detected", "throws": [T20]})
    page.wait_for_function(
        f"() => ({FIND_CARDS})().some((c) => "
        "c.shadowRoot.querySelector('.practice-remaining')?.textContent === '81')",
        timeout=15000,
    )
    page.wait_for_timeout(800)
    peak(page)
    card_shot(page, "card-match")
    scoreboard = scoreboard_page(page)

    # Cricket between the same two players, Alex aiming at the 19.
    takeout()
    service("cricket")
    for names in (
        ("T20", "T20", "S19"),
        ("T19", "T19", "S18"),
        ("T18", "S17", "D17"),
        ("T20", "D16", "S18"),
    ):
        visit = [at(name) for name in names]
        for count in range(1, 4):
            control({"event": "Throw detected", "throws": visit[:count]})
            page.wait_for_timeout(300)
        takeout()
    control({"event": "Throw detected", "throws": [at("T16")]})
    page.wait_for_function(
        f"() => ({FIND_CARDS})().some((c) => c.shadowRoot"
        ".querySelectorAll('.practice .cricket tbody tr')[4]?.children[1]?.textContent === 'Ⓧ')",
        timeout=15000,
    )
    scoreboard.wait_for_function(
        f"() => ({find('homedarts-scoreboard-card')})().some((c) => c.shadowRoot"
        ".querySelectorAll('.cricket tbody tr')[4]?.children[1]?.textContent === 'Ⓧ')",
        timeout=15000,
    )
    scoreboard.wait_for_timeout(800)
    page_shot(scoreboard, "scoreboard-cricket")
    scoreboard.close()
    page.evaluate(
        CALL_SERVICE, ["number", "set_value", "practice_players", {"value": 1}]
    )
    service("off")


def find(tag: str) -> str:
    return FIND_CARDS.replace("'homedarts-card'", f"'{tag}'")


def training_card(page: Page, suffix: str) -> None:
    """The heatmap, statistics and the visit history read from the recorder."""
    size = page.viewport_size
    # A tall page keeps the whole card below the toolbar.
    tall = 2600 if size["width"] < 600 else 1700
    page.set_viewport_size({"width": size["width"], "height": tall})
    page.goto(f"{HA}/homedarts-demo/training")
    page.wait_for_function(
        f"() => ({find('homedarts-training-card')})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.history-chart .visit-bar:not(.empty)').length >= 5)",
        timeout=60000,
    )
    ready(page)
    card_shot(page, f"training-card{suffix}", tag="homedarts-training-card")
    page.set_viewport_size(size)


def live_positions(page: Page) -> None:
    """The positions of the session, with the darts of the current visit as pins."""
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"], "height": 1700})
    tag = "homedarts-training-card"
    # The card of Alex's positions, switched to the session.
    page.goto(f"{HA}/homedarts-demo/positions")
    page.locator(f"{tag} button[data-source='']").click()
    page.wait_for_function(
        f"() => ({find(tag)})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.heat-layer .position.live').length === 3"
        " && c.shadowRoot.querySelectorAll('.heat-layer .position:not(.live)').length >= 15)",
        timeout=60000,
    )
    ready(page)
    part_shot(page, "training-live-positions", tag, [".heat"])
    page.set_viewport_size(size)


def status_card(page: Page, suffix: str) -> None:
    page.goto(f"{HA}/homedarts-demo/status")
    page.wait_for_function(
        f"() => ({find('homedarts-status-card')})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.camera').length === 3)",
        timeout=60000,
    )
    ready(page)
    card_shot(page, f"status-card{suffix}", tag="homedarts-status-card")


def strategy_dashboard(page: Page) -> None:
    """The training view of the dashboard that the strategy generates."""
    size = page.viewport_size
    page.set_viewport_size({"width": size["width"], "height": 1700})
    page.goto(f"{HA}/homedarts-auto/training")
    page.wait_for_function(
        f"() => ({find('homedarts-training-card')})().some((c) =>"
        " c.shadowRoot.querySelectorAll('.history-chart .visit-bar:not(.empty)').length >= 5)",
        timeout=60000,
    )
    page.wait_for_timeout(2500)
    page_shot(page, "dashboard-strategy")
    page.set_viewport_size(size)


# The views of the automatic dashboard in the order of its tabs, each with the card
# it waits for: its first card, or for the game settings the built-in card of a list.
STRATEGY_VIEWS = (
    ("live", "homedarts-card"),
    ("scoreboard", "homedarts-scoreboard-card"),
    ("training", "homedarts-training-card"),
    ("players", "homedarts-players-card"),
    ("games", "hui-entities-card"),
    ("board", "homedarts-status-card"),
)


def strategy_views(page: Page) -> None:
    """Every view of the automatic dashboard as a laptop shows it, all of one size, as
    dashboard-<view>.png, which the card guide shows side by side. Without the
    sidebar, which would take a fifth of each picture. The steps only look, so the
    images after them stay as they were."""
    context = own_context(page, viewport={"width": 1280, "height": 800})
    # Before Home Assistant reads it, on every page: the first load of a dashboard
    # passes through the login, which would take a script's page from under it.
    context.add_init_script(f"try {{ {HIDE_SIDEBAR} }} catch {{}}")
    view = context.new_page()
    for path, tag in STRATEGY_VIEWS:
        view.goto(f"{HA}/homedarts-auto/{path}")
        wait_card(view, "r?.querySelector('ha-card')", tag, 60000)
        if tag.startswith("homedarts-"):
            ready(view)
        else:
            # Built-in cards alone, which ready() does not wait for.
            view.wait_for_function(
                WEBSOCKET_QUIET, arg=QUIET, timeout=15000, polling=POLL
            )
            view.evaluate(FRAMES)
        page_shot(view, f"dashboard-{path}")
    context.close()


# Takes the focus from where a click left it, deep in the shadow roots.
BLUR = """
() => {
  let element = document.activeElement;
  while (element?.shadowRoot?.activeElement) element = element.shadowRoot.activeElement;
  element?.blur?.();
}
"""


def rest_pointer(page: Page) -> None:
    """No row lit up by the pointer or the focus, whichever way the page came about."""
    page.mouse.move(0, 0)
    page.evaluate(BLUR)


def config_flow(page: Page) -> None:
    page.goto(f"{HA}/config/integrations/dashboard/add?domain=homedarts")
    # An integration that is already set up asks before adding another entry.
    confirm = page.get_by_role("button", name="OK", exact=True)
    try:
        confirm.wait_for(timeout=10000)
        confirm.click()
    except PlaywrightTimeoutError:
        pass
    # Never open the network search here: it would list the real boards of this
    # internet connection in a public screenshot.
    menu = page.get_by_text(
        "Enter board address" if LANGUAGE == "en" else "Board-Adresse eingeben",
        exact=True,
    )
    menu.wait_for(timeout=30000)
    # The question before may or may not have come, and its button left the
    # pointer over the menu.
    rest_pointer(page)
    page.wait_for_timeout(800)
    page_shot(page, "setup-menu")
    menu.click()
    title = "Connect local board" if LANGUAGE == "en" else "Lokales Board verbinden"
    page.get_by_text(title, exact=True).wait_for(timeout=15000)
    rest_pointer(page)
    page.wait_for_timeout(800)
    page_shot(page, "setup-local")
    # Leave the unfinished flow; the demo instance is discarded afterwards.
    page.goto(f"{HA}/homedarts-demo/board")


# Opens a path of Home Assistant within the app, as its links do.
NAVIGATE = """
(path) => {
  history.pushState(null, '', path);
  window.dispatchEvent(new CustomEvent('location-changed', { detail: { replace: false } }));
}
"""


def device_page(page: Page) -> None:
    open_dashboard(page, "board")
    device_id = page.evaluate(
        "() => Object.values(document.querySelector('home-assistant').hass.devices)"
        ".find((d) => d.identifiers.some((i) => i[0] === 'homedarts')).id"
    )
    # The device page names the button to the Board Manager once, when it opens,
    # and gets no words when the texts of the settings have not arrived yet. So the
    # list of devices comes first, with those texts, and the device opens from there
    # within the app, again if it still has to.
    page.goto(f"{HA}/config/devices/dashboard")
    page.get_by_text("Autodarts Board").first.wait_for(timeout=30000)
    page.wait_for_timeout(1500)
    visit = page.locator("ha-device-info-card ha-button[target='_blank']").filter(
        has_text=re.compile(r"\w")
    )
    for attempt in range(4):
        page.evaluate(NAVIGATE, f"/config/devices/device/{device_id}")
        try:
            visit.first.wait_for(timeout=10000)
            break
        except PlaywrightTimeoutError:
            if attempt == 3:
                raise
            page.evaluate(NAVIGATE, "/config/devices/dashboard")
            page.wait_for_timeout(2000)
    page.wait_for_timeout(2500)
    page_shot(page, "device")


def editor(page: Page) -> None:
    page.goto(f"{HA}/homedarts-demo/board")
    # The dashboard has loaded once the card has drawn its board.
    page.wait_for_function(
        f"() => ({FIND_CARDS})().some((c) => c.shadowRoot.querySelector('.board svg'))",
        timeout=60000,
    )
    open_card_form(page, FIND_CARDS)
    page.wait_for_timeout(2000)
    peak(page)
    page_shot(page, "card-editor")
    page.keyboard.press("Escape")


def strategy_editor(page: Page) -> None:
    """The editor of the generated dashboard: the board and the title."""
    page.goto(f"{HA}/homedarts-auto/live")
    page.wait_for_function(
        f"() => ({FIND_CARDS})().some((c) => c.shadowRoot.querySelector('.board svg'))",
        timeout=60000,
    )
    page.evaluate(f"() => ({find('hui-root')})()[0]._enableEditMode()")
    page.locator("homedarts-strategy-editor > ha-form").wait_for(timeout=15000)
    page.wait_for_timeout(2000)
    page_shot(page, "strategy-editor")
    page.keyboard.press("Escape")


# Reports ---------------------------------------------------------------------------

# The report day and time one minute from now, in Home Assistant's time zone.
NEXT_MINUTE = """
async () => {
  const hass = document.querySelector('home-assistant').hass;
  const text = await hass.callApi('POST', 'template', {
    template: "{{ (now() + timedelta(minutes=1)).strftime('%A|%H:%M:00') | lower }}",
  });
  return text.split('|');
}
"""
REPORTED = """
async () => {
  const hass = document.querySelector('home-assistant').hass;
  const notifications = await hass.callWS({ type: 'persistent_notification/get' });
  return notifications.some((item) => item.notification_id === 'homedarts_weekly_report');
}
"""
SHOW_NOTIFICATIONS = """
() => document.querySelector('home-assistant').shadowRoot
  .querySelector('home-assistant-main')
  .dispatchEvent(new CustomEvent('hass-show-notifications', { bubbles: true, composed: true }))
"""


def local_page(page: Page) -> Page:
    """A page in the demo's time zone, so that times read as the board saw them."""
    context = new_context(
        page.context.browser,
        viewport={"width": 1280, "height": 900},
        device_scale_factor=2,
        locale=LOCALE,
        color_scheme="dark",
        timezone_id="Europe/Berlin",
    )
    return context.new_page()


def training_calendar(page: Page) -> None:
    """Home Assistant's calendar with the week of sessions and matches before today."""
    calendar = local_page(page)
    calendar.goto(f"{HA}/calendar")
    calendar.locator(".fc-event").first.wait_for(timeout=60000)
    # The list of seven days, one week back, shows every title in full.
    calendar.locator("ha-button[value=listWeek]").click()
    calendar.locator("ha-full-calendar .prev").click()
    calendar.locator(".fc-list-event").first.wait_for(timeout=15000)
    calendar.wait_for_timeout(1500)
    page_shot(calendar, "training-calendar")
    calendar.context.close()


def weekly_report_notification(page: Page) -> None:
    """The notification of the demo's weekly report automation, from its blueprint.

    Last, because the report starts the demo's week anew.
    """
    report = local_page(page)
    open_dashboard(report, "board")
    due = None
    if (now := demo_now()) is not None:
        # The frozen clock moves on to the last second before the report time first:
        # Home Assistant waits for that time in real seconds, from the moment the
        # report time is set, and without this for up to the rest of the minute.
        due = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        move_clock(max(now, due - timedelta(seconds=1)))
    day, time = report.evaluate(NEXT_MINUTE)
    report.evaluate(
        CALL_SERVICE, ["select", "select_option", "weekly_report_day", {"option": day}]
    )
    report.evaluate(
        CALL_SERVICE, ["time", "set_value", "weekly_report_time", {"time": time}]
    )
    if due is not None:
        # The minute passes; Home Assistant sends the report when it checks the time
        # again.
        move_clock(due)
        report.clock.set_fixed_time(due)
    for _ in range(90):
        if report.evaluate(REPORTED):
            break
        report.wait_for_timeout(2000)
    else:
        raise RuntimeError("The weekly report sent no notification")
    report.evaluate(SHOW_NOTIFICATIONS)
    title = "Deine Dartwoche" if LANGUAGE == "de" else "Your darts week"
    report.get_by_text(title).wait_for(timeout=15000)
    report.wait_for_timeout(1500)
    notification = report.locator("persistent-notification-item").first
    notification.scroll_into_view_if_needed()
    settle(report)
    notification.screenshot(path=str(OUTPUT / "weekly-report-notification.png"))
    saved(OUTPUT / "weekly-report-notification.png")
    report.context.close()


# The illustrated guides -------------------------------------------------------------

# A wall tablet and the pictures of the README need no sidebar.
HIDE_SIDEBAR = "localStorage.setItem('dockedSidebar', JSON.stringify('always_hidden'))"
OUTER_BULL = {
    "segment": {"name": "25", "number": 25, "multiplier": 1, "bed": "Single"},
    "coords": {"x": -0.06, "y": 0.07},
}
# The checkout route of the practice game, as the sensor shows it.
ROUTE = """
() => {
  const hass = document.querySelector('home-assistant').hass;
  const entity = Object.values(hass.entities).find(
    (item) => item.platform === 'homedarts' && item.translation_key === 'practice_checkout'
  );
  return hass.states[entity.entity_id].state;
}
"""
# The numbers of the Cricket game being played, as the practice game shows them.
CRICKET_NUMBERS = """
() => {
  const hass = document.querySelector('home-assistant').hass;
  const entity = Object.values(hass.entities).find(
    (item) => item.platform === 'homedarts' && item.translation_key === 'practice_remaining'
  );
  return hass.states[entity.entity_id].attributes.numbers;
}
"""
# Replaces the secret of the online bridge on the screen before a screenshot.
MASK_SECRET = """
() => {
  (function mask(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      walker.currentNode.textContent = walker.currentNode.textContent.replace(/[0-9a-f]{64}/g, '…');
    }
    root.querySelectorAll('*').forEach((el) => el.shadowRoot && mask(el.shadowRoot));
  })(document);
}
"""


class ClipRecorder(Recorder):
    """Frames of a region of the page, such as two cards side by side."""

    def __init__(self, page: Page, clip: dict) -> None:
        super().__init__(page)
        self.clip = clip

    def shot(self, duration: int, wait: bool = True) -> None:
        settle(self.page, wait)
        image = self.page.screenshot(clip=self.clip, animations="allow")
        self.frames.append(Image.open(io.BytesIO(image)))
        self.durations.append(duration)


def named_dart(name: str) -> dict:
    """A dart in the bed a checkout route names: T20, D12, 25 or BULL."""
    return {"BULL": BULL, "25": OUTER_BULL}.get(name) or at(name)


def own_context(page: Page, **options):
    """A browser context of its own, for a device of another size."""
    return new_context(
        page.context.browser,
        locale=LOCALE,
        color_scheme="dark",
        **{"device_scale_factor": 1, **options},
    )


def start_match(page: Page, names: list[str], option: str, legs: int = 1) -> None:
    """A match of these players, decided by one set of `legs` legs."""
    pull_darts()
    for index, name in enumerate(names):
        page.evaluate(SET_NAME, [index, name])
    players(page, len(names))
    for key, value in (("practice_legs", legs), ("practice_sets", 1)):
        page.evaluate(CALL_SERVICE, ["number", "set_value", key, {"value": value}])
    game(page, option)


def dart_by_dart(board: Page, recorder: Recorder, darts: list[dict]) -> None:
    """Throw a visit dart by dart, a frame after each, and pull the darts."""
    for count in range(1, len(darts) + 1):
        control({"event": "Throw detected", "throws": darts[:count]})
        board.wait_for_timeout(500)
        recorder.shot(700)
    pull_darts()
    board.wait_for_timeout(700)
    recorder.shot(1000)


HERO_CARDS = ("homedarts-card", SCOREBOARD)


def hero_view(view: Page) -> tuple[ClipRecorder, list[int]]:
    """The live card and the scoreboard of the hero dashboard on a page, and a
    recorder of the region around both, with their heights at the start."""
    view.goto(f"{HA}/homedarts-demo/hero")
    wait_card(view, "r.querySelectorAll('.player').length === 2", SCOREBOARD, 60000)
    ready(view)
    boxes = [view.locator(tag).first.bounding_box() for tag in HERO_CARDS]
    left = min(box["x"] for box in boxes) - 12
    top = min(box["y"] for box in boxes) - 12
    right = max(box["x"] + box["width"] for box in boxes) + 12
    bottom = max(box["y"] + box["height"] for box in boxes) + 12
    recorder = ClipRecorder(
        view, {"x": left, "y": top, "width": right - left, "height": bottom - top}
    )
    return recorder, [round(box["height"]) for box in boxes]


def hero_animation(page: Page) -> None:
    """The first picture of the README and of the website: a 301 match on the live
    card and the scoreboard.

    Alex throws a 180, Sam scores 85, and Alex checks out 121 for the game shot. The
    same match plays on a wide screen, the two cards side by side (hero.webp), and on
    a phone, where Home Assistant puts the scoreboard below the live card
    (hero-mobile.webp): the home page of the website shows that one on a phone, on
    which the wide picture would be too small to read.
    """
    start_match(page, ["Alex", "Sam"], "301")
    wide = page.context.new_page()
    wide.add_init_script(HIDE_SIDEBAR)
    wide.set_viewport_size({"width": 1280, "height": 720})
    phone_context = own_context(
        page,
        # Tall enough for both cards, one below the other.
        viewport={"width": 390, "height": 1100},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
    )
    phone = phone_context.new_page()
    views = {
        "hero": (wide, *hero_view(wide)),
        "hero-mobile": (phone, *hero_view(phone)),
    }
    for _, recorder, _ in views.values():
        recorder.blink(1, hold=1400)
    darts_shown = "r.querySelectorAll('.visit .dart:not(.empty)').length === {0}"
    active = "r.querySelector('.player.active .name')?.textContent.includes('{0}')"

    def steady(view: Page, heights: list[int]) -> None:
        # The cards keep their heights through the game; a card that grows would
        # leave the clip and make the picture restless.
        now = [
            round(view.locator(tag).first.bounding_box()["height"])
            for tag in HERO_CARDS
        ]
        if any(abs(a - b) > 1 for a, b in zip(now, heights, strict=True)):
            raise AssertionError(
                f"Hero cards changed their heights: {heights} -> {now}"
            )

    def throw(names: list[str]) -> None:
        thrown: list[dict] = []
        for name in names:
            thrown.append(named_dart(name))
            control({"event": "Throw detected", "throws": thrown})
            for view, recorder, heights in views.values():
                wait_card(view, darts_shown.format(len(thrown)), SCOREBOARD)
                steady(view, heights)
                # The bed lights up, then holds at full strength.
                view.evaluate(SEEK, 250)
                recorder.shot(250)
                view.evaluate(SEEK, 800)
                recorder.shot(650)

    for names, following in (
        (["T20", "T20", "T20"], "Sam"),
        (["T20", "S20", "S5"], "Alex"),
    ):
        throw(names)
        for _, recorder, _ in views.values():
            recorder.blink(1, hold=600)
        pull_darts()
        for view, recorder, heights in views.values():
            wait_card(view, active.format(following), SCOREBOARD)
            view.wait_for_timeout(300)
            steady(view, heights)
            recorder.blink(1, hold=900)
    # Alex follows the route the cards show for 121; the game shot ends the
    # animation, before the match summary takes the place of the players.
    throw(wide.evaluate(ROUTE).split())
    for name, (_, recorder, _) in views.items():
        recorder.blink(1, hold=2800)
        # On a phone, the picture is shown about 340 pixels wide: at 560 pixels it
        # stays sharp on a screen of twice the density.
        recorder.save(name, width=960 if name == "hero" else 560)
    wide.close()
    phone_context.close()
    pull_darts()
    players(page, 1)
    game(page, "off")


def scoreboard_game(page: Page, names: list[str], option: str) -> Page:
    """A game of these players on the scoreboard of a landscape tablet."""
    start_match(page, names, option)
    board = page.context.new_page()
    # High enough that the winner's banner never pushes the card under the toolbar.
    board.set_viewport_size({"width": 1280, "height": 1000})
    board.goto(f"{HA}/homedarts-auto/scoreboard")
    wait_card(
        board, "!!r.querySelector('.main .player, .main .single')", SCOREBOARD, 60000
    )
    ready(board)
    return board


def winning_visit(board: Page, recorder: Recorder, darts: list[dict]) -> None:
    """Throw the visit that wins the match dart by dart, pull the darts and hold
    the banner of the winner."""
    for count in range(1, len(darts) + 1):
        control({"event": "Throw detected", "throws": darts[:count]})
        board.wait_for_timeout(500)
        recorder.shot(700 if count < len(darts) else 1200)
    pull_darts()
    wait_card(board, "!r.querySelector('.banner').hidden", SCOREBOARD)
    board.wait_for_timeout(300)
    recorder.shot(2600)


def shanghai_animation(page: Page) -> None:
    """Shanghai for two: Sam hits single, double and triple 2 and wins at once."""
    board = scoreboard_game(page, ["Alex", "Sam"], "shanghai")
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1400)
    for darts in (
        [at("S1"), at("T1"), at("S20")],
        [at("D1"), at("S1"), at("S1")],
        [at("S2"), at("D2"), at("S15")],
    ):
        dart_by_dart(board, recorder, darts)
    winning_visit(board, recorder, [at("S2"), at("D2"), at("T2")])
    recorder.save("shanghai")
    board.close()
    end_match(page)


def halve_it_animation(page: Page) -> None:
    """Halve-It for two: a visit without a hit on the target halves the points."""
    board = scoreboard_game(page, ["Alex", "Sam"], "halve_it")
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1400)
    for darts in (
        [at("T15"), at("S15"), at("S1")],
        [at("S2"), at("S10"), at("S6")],
        [at("S16"), at("S7"), at("S8")],
        [at("D16"), at("S16"), at("T16")],
        [at("S3"), at("S17"), at("D17")],
        [at("S5"), at("S1"), at("S20")],
    ):
        dart_by_dart(board, recorder, darts)
    recorder.shot(1600)
    recorder.save("halve-it")
    board.close()
    end_match(page)


def bermuda_animation(page: Page) -> None:
    """Bermuda for two: the beds hit score their points, and a visit without a
    hit on the target halves them."""
    board = scoreboard_game(page, ["Alex", "Sam"], "bermuda")
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1400)
    for darts in (
        [at("T12"), at("S12"), at("D12")],
        [at("S12"), at("S5"), at("T12")],
        [at("S13"), at("D13"), at("S1")],
        [at("S20"), at("S1"), at("S18")],
        [at("T14"), at("S11"), at("S14")],
        [at("D14"), at("D10"), at("S14")],
    ):
        dart_by_dart(board, recorder, darts)
    recorder.shot(1600)
    recorder.save("bermuda")
    board.close()
    end_match(page)


def random_cricket_scoreboard(page: Page) -> None:
    """Random Cricket on the scoreboard: the six numbers the leg drew, highest
    first, and the bull; a dart on a number the leg did not draw counts nothing."""
    board = match_of(page, ["Alex", "Sam"], "random_cricket")
    numbers = page.evaluate(CRICKET_NUMBERS)
    first, second, third = numbers[:3]
    unused = next(number for number in range(20, 0, -1) if number not in numbers)
    throw_visits(
        board,
        [
            [at(f"T{first}"), at(f"S{first}"), at(f"S{second}")],
            [at(f"T{second}"), at(f"D{third}"), at(f"S{unused}")],
        ],
    )
    # Alex's treble closes the second number, which Sam has closed already.
    control({"event": "Throw detected", "throws": [at(f"T{second}")]})
    wait_card(
        board,
        "r.querySelectorAll('.cricket tbody tr')[1]?.children[1]?.textContent === 'Ⓧ'",
        SCOREBOARD,
    )
    page_shot(board, "scoreboard-random-cricket")
    board.close()
    end_match(page)


def hidden_cricket_animation(page: Page) -> None:
    """Hidden Cricket on the scoreboard: a question mark for every number of the
    leg that no dart has marked yet. The players sweep the board from the 20
    down; a dart on a number of the leg shows it in its row, and one on a number
    the leg did not draw counts nothing."""
    board, recorder = scoreboard_match(page, "hidden_cricket")
    recorder.shot(1400)
    visit_shots(
        board,
        recorder,
        [[f"T{number - dart}" for dart in range(3)] for number in (20, 17, 14, 11)],
    )
    recorder.save("hidden-cricket")
    board.close()
    end_match(page)


def round_the_world_animation(page: Page) -> None:
    """Round the World for two: every hit moves a player on to the next number."""
    board = scoreboard_game(page, ["Alex", "Sam"], "round_the_world")
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1400)
    for darts in (
        [at("S1"), at("T2"), at("S3")],
        [at("S1"), at("S18"), at("D2")],
        [at("S4"), at("S5"), at("S20")],
        [at("T3"), at("S4"), at("S4")],
    ):
        dart_by_dart(board, recorder, darts)
    recorder.shot(1600)
    recorder.save("round-the-world")
    board.close()
    end_match(page)


def gotcha_animation(page: Page) -> None:
    """Gotcha for two up to 101: Sam reaches Alex's 75 and sends Alex back to 0,
    then checks out on a double."""
    target = ["number", "set_value", "practice_gotcha_target"]
    page.evaluate(CALL_SERVICE, [*target, {"value": 101}])
    board = scoreboard_game(page, ["Alex", "Sam"], "gotcha")
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1400)
    for darts in (
        [at("T20"), at("S10"), at("S5")],
        [at("T20"), at("S10"), at("S5")],
        [at("T20"), at("S20"), at("D3")],
    ):
        dart_by_dart(board, recorder, darts)
    winning_visit(board, recorder, [at("S6"), at("D10")])
    recorder.save("gotcha")
    board.close()
    end_match(page)
    page.evaluate(CALL_SERVICE, [*target, {"value": 301}])


def bull_off_animation(page: Page) -> None:
    """The bull-off: Sam's bullseye beats Alex's outer bull, and Sam throws first."""
    page.evaluate(CALL_SERVICE, ["switch", "turn_on", "practice_bull_off", {}])
    board = scoreboard_game(page, ["Alex", "Sam"], "501")
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1600)
    for dart in (OUTER_BULL, BULL):
        control({"event": "Throw detected", "throws": [dart]})
        board.wait_for_timeout(700)
        recorder.shot(1400)
        pull_darts()
        board.wait_for_timeout(700)
        if dart is OUTER_BULL:
            recorder.shot(1000)
    wait_card(
        board,
        "r.querySelector('.player.active .name')?.textContent.includes('Sam')",
        SCOREBOARD,
    )
    board.wait_for_timeout(300)
    recorder.shot(2600)
    recorder.save("bull-off")
    board.close()
    page.evaluate(CALL_SERVICE, ["switch", "turn_off", "practice_bull_off", {}])
    end_match(page)


def bobs_27_animation(page: Page) -> None:
    """Bob's 27 on the scoreboard: every double adds, a visit without one subtracts."""
    board = scoreboard_game(page, ["Alex"], "bobs_27")
    recorder = Recorder(board, SCOREBOARD)
    recorder.shot(1400)
    for darts in (
        [at("D1"), at("S1"), at("D1")],
        [at("S2"), at("S5"), at("S2")],
        [at("D3"), at("D3"), at("T3")],
    ):
        dart_by_dart(board, recorder, darts)
    recorder.shot(1400)
    recorder.save("bobs-27")
    board.close()
    end_match(page)


def baseball_scoreboard(page: Page) -> None:
    """Baseball for two after four innings: the scorecard of the runs."""
    board = scoreboard_game(page, ["Alex", "Sam"], "baseball")
    throw_visits(
        board,
        [
            [at("S1"), at("T1"), at("S1")],
            [at("D1"), at("S1"), at("S20")],
            [at("S2"), at("S2"), at("D2")],
            [at("T2"), at("S2"), at("S15")],
            [at("S3"), at("S17"), at("S3")],
            [at("T3"), at("D3"), at("S3")],
            [at("D4"), at("S4"), at("S4")],
        ],
    )
    control({"event": "Throw detected", "throws": [at("S4")]})
    wait_card(board, "!!r.querySelector('.scorecard')", SCOREBOARD)
    board.wait_for_timeout(800)
    page_shot(board, "scoreboard-baseball")
    board.close()
    end_match(page)


def catch_40_scoreboard(page: Page) -> None:
    """Catch 40 on the scoreboard: the score to check out, the round and the points."""
    pull_darts()
    players(page, 1)
    game(page, "catch_40")
    board = tablet(page)
    wait_card(board, "!!r.querySelector('.single .big')", SCOREBOARD, 60000)
    board.wait_for_timeout(1000)
    # 61 in two darts, then a first dart at 62.
    throw_visits(board, [[at("T11"), at("D14")]])
    control({"event": "Throw detected", "throws": [at("S12")]})
    board.wait_for_timeout(1000)
    page_shot(board, "scoreboard-catch-40")
    board.close()
    pull_darts()
    game(page, "off")


def scoreboard_portrait(page: Page) -> None:
    """The scoreboard of a portrait tablet: the Cricket chalkboard fills its height."""
    start_match(page, ["Alex", "Sam"], "cricket", legs=3)
    context = own_context(page, viewport={"width": 800, "height": 1280})
    context.add_init_script(HIDE_SIDEBAR)
    board = context.new_page()
    board.goto(f"{HA}/homedarts-auto/scoreboard")
    wait_card(board, "!!r.querySelector('.cricket')", SCOREBOARD, 60000)
    throw_visits(
        board,
        [
            [at("T20"), at("S20"), at("S19")],
            [at("T19"), at("T19"), at("S20")],
            [at("S20"), at("T18"), at("D18")],
            [at("T17"), at("S17"), at("S16")],
        ],
    )
    control({"event": "Throw detected", "throws": [at("T16")]})
    wait_card(
        board, "r.querySelectorAll('.visit .dart:not(.empty)').length === 1", SCOREBOARD
    )
    board.wait_for_timeout(1000)
    page_shot(board, "scoreboard-portrait")
    context.close()
    end_match(page)


# The picture of a stream behind the overlay: a highlight photo of the demo, as the
# camera of a stream shows the board. The page is see-through behind the overlay,
# which leaves OBS the picture below it; here the page itself shows the photo.
STREAM_PICTURE = """
async ([name]) => {
  const hass = document.querySelector('home-assistant').hass;
  const path = `/media/local/homedarts/highlights/${name}`;
  const signed = await hass.callWS({ type: 'auth/sign_path', path });
  const picture = new Image();
  picture.src = signed.path;
  await picture.decode();
  document.documentElement.style.setProperty(
    'background', `#000 url("${signed.path}") center / cover no-repeat`, 'important'
  );
}
"""

OVERLAY_CORNER = f"""
() => ({find(SCOREBOARD)})()[0].setConfig({{
  type: 'custom:homedarts-scoreboard-card', overlay: 'chroma', overlay_layout: 'corner'
}})
"""


def stream_overlay(page: Page) -> None:
    """The scoreboard as the overlay of a stream in OBS: see-through along the bottom
    of the picture of the board, and on its key colour in the top-left corner."""
    start_match(page, ["Alex", "Sam"], "501", legs=3)
    context = own_context(page, viewport={"width": 1280, "height": 720})
    board = context.new_page()
    board.goto(f"{HA}/homedarts-auto/overlay")
    wait_card(
        board,
        "r.querySelectorAll('.stage.taken .player').length === 2",
        SCOREBOARD,
        60000,
    )
    throw_visits(
        board,
        [
            [at("T20"), at("T20"), at("T20")],
            [at("S20"), at("S20"), at("S1")],
            [at("T20"), at("T19"), at("T20")],
            [at("T20"), at("S20"), at("S5")],
        ],
    )
    control({"event": "Throw detected", "throws": [at("T20")]})
    wait_card(
        board, "r.querySelectorAll('.visit .dart:not(.empty)').length === 1", SCOREBOARD
    )
    board.evaluate(STREAM_PICTURE, ["2026-09-26_21-05-33_Alex_180.jpg"])
    page_shot(board, "scoreboard-overlay")
    # The same card in the corner, on the key colour that OBS takes out.
    board.evaluate(OVERLAY_CORNER)
    wait_card(
        board,
        "r.querySelector('.stage.taken[data-layout=corner] .visit .dart:not(.empty)')",
        SCOREBOARD,
    )
    page_shot(board, "scoreboard-overlay-corner")
    context.close()
    end_match(page)


def fullscreen_scoreboard(page: Page) -> None:
    """The scoreboard of a landscape tablet after a tap on its full-screen button: alone
    on the screen, without Home Assistant's header and sidebar, the button pressed."""
    start_match(page, ["Alex", "Sam"], "501", legs=3)
    context = own_context(page, viewport={"width": 1280, "height": 800})
    board = context.new_page()
    board.goto(f"{HA}/homedarts-auto/scoreboard")
    wait_card(board, "r.querySelectorAll('.player').length === 2", SCOREBOARD, 60000)
    throw_visits(
        board,
        [
            [at("T20"), at("T20"), at("S20")],
            [at("S20"), at("T19"), at("S7")],
        ],
    )
    control({"event": "Throw detected", "throws": [at("T20")]})
    wait_card(
        board, "r.querySelectorAll('.visit .dart:not(.empty)').length === 1", SCOREBOARD
    )
    board.locator(SCOREBOARD).locator(".fullscreen-toggle").click()
    wait_card(
        board,
        "r.querySelector('.scoreboard.fullscreen .fullscreen-toggle[aria-pressed=true]')",
        SCOREBOARD,
    )
    # The numbers grow with the screen that the scoreboard now fills.
    ready(board)
    page_shot(board, "scoreboard-fullscreen")
    context.close()
    end_match(page)


def dashboard_trends(page: Page) -> None:
    """The graphs of the generated training view, from four weeks of statistics."""
    # Home Assistant draws the lines of its graphs at once, without the animation
    # that the standing clock would stop, for a device that asks for less motion.
    context = own_context(
        page,
        viewport={"width": 1280, "height": 2400},
        device_scale_factor=2,
        reduced_motion="reduce",
    )
    view = context.new_page()
    view.goto(f"{HA}/homedarts-auto/training")
    view.locator("hui-statistics-graph-card").first.wait_for(timeout=60000)
    # The graphs draw a moment after their data arrives.
    view.wait_for_timeout(5000)
    section = view.locator("hui-section").last
    section.scroll_into_view_if_needed()
    settle(view)
    section.screenshot(path=str(OUTPUT / "dashboard-trends.png"))
    saved(OUTPUT / "dashboard-trends.png")
    context.close()


# Home Assistant loads the texts of its settings, such as the names of their tabs,
# apart from its other texts. It merges every load into the texts it holds, but
# shows only what its newest load put together, and it counts on its timers of no
# delay to run in the order they were asked for. They need not: Chrome holds back
# a timer asked for deep inside other timers, and the frozen clock one asked for
# during a tick. A later load that overtakes the settings' shows the texts without
# theirs, for as long as the page lives. So once the settings' texts are merged,
# one more update shows everything Home Assistant holds.
SETTINGS_TEXTS = """
async () => {
  const app = document.querySelector('home-assistant');
  if (typeof app._updateResources !== 'function') {
    throw new Error('Home Assistant no longer updates its texts with _updateResources');
  }
  await app.hass.loadFragmentTranslation('config');
  await app._updateResources(app.hass.language, {});
}
"""


def settings_texts(page: Page) -> None:
    """Show the texts of the settings, even when a later load hid them."""
    app = "document.querySelector('home-assistant')"
    page.wait_for_function(f"() => {app}?.hass?.loadFragmentTranslation")
    page.evaluate(SETTINGS_TEXTS)
    # A load that overtook this update shows the same texts a moment later.
    page.wait_for_function(
        f"() => {app}.hass.localize('ui.panel.config.automation.caption') !== ''"
    )


def blueprint_list(context: BrowserContext) -> Page:
    """A new page with the blueprints of Home Assistant, in the texts of the settings."""
    view = context.new_page()
    view.goto(f"{HA}/config/blueprint/dashboard")
    view.get_by_text("HomeDarts: light show").first.wait_for(timeout=60000)
    # The list shows before the texts of the settings, such as its tabs.
    settings_texts(view)
    view.get_by_text(
        "Automations" if LANGUAGE == "en" else "Automationen", exact=True
    ).first.wait_for(timeout=30000)
    view.wait_for_timeout(1500)
    return view


def blueprint_form(view: Page, blueprint: str, name: str, height: int) -> None:
    """The form of a blueprint of the list, as the picture `name`; closes the page."""
    # A blueprint opens a new automation with its form.
    view.get_by_text(blueprint).first.click()
    view.wait_for_url("**/config/automation/edit/new", timeout=30000)
    view.set_viewport_size({"width": 1280, "height": height})
    view.wait_for_timeout(3000)
    page_shot(view, name)
    view.close()


# The names of the automation blueprints that Home Assistant knows, which its list shows.
BLUEPRINT_NAMES = """
async () => {
  const hass = document.querySelector('home-assistant').hass;
  const blueprints = await hass.callWS({ type: 'blueprint/list', domain: 'automation' });
  return Object.values(blueprints).flatMap((blueprint) => blueprint.metadata?.name ?? []);
}
"""


def require_every_blueprint(view: Page) -> None:
    """Fail if the window cuts off a row of the list: it draws only the rows in view,
    so a new blueprint would otherwise drop out of the picture without a word."""
    bottom = view.viewport_size["height"]
    cut_off = []
    names = view.evaluate(BLUEPRINT_NAMES)
    for name in names:
        row = view.get_by_text(name, exact=True)
        box = row.first.bounding_box() if row.count() else None
        if box is None or box["y"] + box["height"] > bottom:
            cut_off.append(name)
    if cut_off or not names:
        raise AssertionError(
            f"The list of {len(names)} blueprints doesn't fit into the {bottom} px of"
            f" the window, raise the height in blueprints_page(): {cut_off}"
        )


def blueprints_page(page: Page) -> None:
    """The blueprints of the integration in Home Assistant, and two of their forms."""
    # So high that the list shows every blueprint: it only draws the rows in view.
    context = own_context(
        page, viewport={"width": 1280, "height": 1180}, device_scale_factor=2
    )
    view = blueprint_list(context)
    require_every_blueprint(view)
    page_shot(view, "blueprints")
    blueprint_form(view, "HomeDarts: light show", "blueprint-light-show", 900)
    # So high that its short form shows whole, with the sections that open closed.
    blueprint_form(
        blueprint_list(context), "HomeDarts: walk-on music", "blueprint-walk-on", 1150
    )
    context.close()


# Waits until the recorder has written the last event of an entity: the dialog of
# the entity reads its history and activity from there, and the recorder writes
# only every five seconds.
RECORDED = """
async (entityId) => {
  for (let round = 0; round < 120; round++) {
    const hass = document.querySelector('home-assistant').hass;
    const events = await hass.callWS({
      type: 'logbook/get_events',
      start_time: new Date(Date.now() - 86400 * 1000).toISOString(),
      entity_ids: [entityId],
    });
    if (events.length && events[events.length - 1].state === hass.states[entityId].state) {
      return;
    }
    await new Promise((done) => setTimeout(done, 250));
  }
  throw new Error(`The recorder has not written the last event of ${entityId}`);
}
"""

# Home Assistant gives every state it draws in a history or an activity list a
# colour of its own, the next of its palette, in the order it draws them first,
# for as long as the page lives. The events entity has a new state with every
# event. The timeline of a history draws one state per pixel, the one that lasts
# longest there, so which states it colours depends on its width the moment its
# data arrives; and the history and the activity of the dialog arrive in either
# order. So an activity list of the entity, as the dialog has it but out of sight,
# draws every event of the last 24 hours first, newest first: the dialog finds them
# all coloured, and the newest events always get the first colours of the palette.
COLOUR_EVENTS = """
async (entityId) => {
  if (!customElements.get('ha-logbook')) {
    throw new Error('Home Assistant has not loaded its activity list');
  }
  const logbook = document.createElement('ha-logbook');
  Object.assign(logbook, {
    hass: document.querySelector('home-assistant').hass,
    time: { recent: 86400 },
    entityIds: [entityId],
    narrow: true,
    noIcon: true,
    graphColor: true,
    nameDetail: 'none',
  });
  const box = document.createElement('div');
  box.style.cssText = 'position: fixed; top: 0; left: -10000px; width: 600px;';
  box.append(logbook);
  document.body.append(box);
  const rows = () => {
    const found = [];
    const roots = [logbook.shadowRoot];
    for (let index = 0; index < roots.length; index++) {
      roots[index]?.querySelectorAll('*').forEach((el) => {
        if (el.localName === 'ha-logbook-entry') found.push(el);
        if (el.shadowRoot) roots.push(el.shadowRoot);
      });
    }
    return found;
  };
  try {
    // Done when two looks a tenth of a second apart find the same rows, all drawn.
    let count = 0;
    for (let round = 0; round < 300; round++) {
      await new Promise((done) => setTimeout(done, 100));
      const drawn = logbook.getEntries().length ? rows() : [];
      await Promise.all(drawn.map((row) => row.updateComplete));
      if (drawn.length && drawn.length === count) return count;
      count = drawn.length;
    }
    throw new Error(`No activity of ${entityId} to colour`);
  } finally {
    box.remove();
  }
}
"""


def board_events_dialog(page: Page) -> None:
    """The events entity after a visit: the last event, its history and the activity."""
    pull_darts()
    context = own_context(
        page, viewport={"width": 1280, "height": 900}, device_scale_factor=2
    )
    view = context.new_page()
    open_dashboard(view, "board")
    for darts in ([T20], [T20, S5], [T20, S5, BULL]):
        control({"event": "Throw detected", "throws": darts})
        view.wait_for_timeout(500)
    if (now := demo_now()) is not None:
        # The dialog opens a few seconds after the visit.
        move_clock(now + timedelta(seconds=6))
        view.clock.set_fixed_time(now + timedelta(seconds=6))
    entity = view.evaluate(
        "() => Object.values(document.querySelector('home-assistant').hass.entities)"
        ".find((item) => item.platform === 'homedarts' && item.translation_key === 'board_events')"
        ".entity_id"
    )
    view.evaluate(RECORDED, entity)
    view.evaluate(COLOUR_EVENTS, entity)
    view.evaluate(
        "(entityId) => document.querySelector('home-assistant').dispatchEvent("
        "new CustomEvent('hass-more-info', {bubbles: true, composed: true, detail: {entityId}}))",
        entity,
    )
    dialog = view.locator("ha-more-info-dialog")
    dialog.locator("ha-logbook-entry").first.wait_for(timeout=30000)
    dialog.locator("state-history-chart-timeline canvas").first.wait_for(timeout=30000)
    # The chart draws its timeline a moment after it has its data.
    view.wait_for_timeout(1500)
    page_shot(view, "board-events")
    context.close()


def online_bridge_options(page: Page) -> None:
    """The options of the board: the address and the lines for Tools for Autodarts.

    The secret of the address is masked. Closing the dialog keeps the options as
    they were.
    """
    context = own_context(
        page, viewport={"width": 1280, "height": 1100}, device_scale_factor=2
    )
    view = context.new_page()
    view.goto(f"{HA}/config/integrations/integration/homedarts")
    # The label of the button is one of the texts of the settings.
    settings_texts(view)
    label = "Configure" if LANGUAGE == "en" else "Konfigurieren"
    view.locator(f"button[aria-label='{label}']").first.click()
    dialog = view.locator("dialog-data-entry-flow")
    dialog.locator("ha-checkbox").first.click()
    # The button with a text submits; the icon buttons have none.
    dialog.locator("ha-button").filter(has_text=re.compile(r"\w")).last.click()
    dialog.locator("ha-markdown code, ha-markdown pre").first.wait_for(timeout=30000)
    view.wait_for_timeout(1500)
    view.evaluate(MASK_SECRET)
    page_shot(view, "online-bridge")
    context.close()


# A dartboard without Autodarts -------------------------------------------------------

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
# The live card and the scoreboard of the board without Autodarts, in a dashboard of
# their own: the cards of the demo dashboard show its first board.
SAVE_MANUAL_DASHBOARD = """
async ([path, device]) => {
  const hass = document.querySelector('home-assistant').hass;
  const card = (type, options = {}) => ({ type: `custom:${type}`, device_id: device, ...options });
  await hass.callWS({
    type: 'lovelace/dashboards/create', url_path: path, title: 'Garage', mode: 'storage',
    show_in_sidebar: false, require_admin: false,
  });
  await hass.callWS({
    type: 'lovelace/config/save', url_path: path,
    config: { views: [
      {
        title: 'Live', path: 'live', type: 'sections', max_columns: 2,
        sections: [{ type: 'grid', column_span: 2, cards: [card('homedarts-card')] }],
      },
      { title: 'Scoreboard', path: 'scoreboard', panel: true, cards: [card('homedarts-scoreboard-card', { full_height: true })] },
    ] },
  });
}
"""
MANUAL_MENU = {
    "en": "Dartboard without Autodarts: enter every dart yourself",
    "de": "Dartscheibe ohne Autodarts: jeden Dart selbst eingeben",
}
MANUAL_TITLE = {"en": "Dartboard without Autodarts", "de": "Dartscheibe ohne Autodarts"}


def manual_setup(page: Page) -> None:
    """The form of the setup that adds a dartboard without Autodarts."""
    page.goto(f"{HA}/config/integrations/dashboard/add?domain=homedarts")
    confirm = page.get_by_role("button", name="OK", exact=True)
    try:
        confirm.wait_for(timeout=10000)
        confirm.click()
    except PlaywrightTimeoutError:
        pass
    menu = page.get_by_text(MANUAL_MENU[LANGUAGE], exact=True)
    menu.wait_for(timeout=30000)
    menu.click()
    page.get_by_text(MANUAL_TITLE[LANGUAGE], exact=True).wait_for(timeout=15000)
    rest_pointer(page)
    page.wait_for_timeout(800)
    page_shot(page, "setup-manual")
    # The board itself is added below, the same way in every run, once the frontend
    # is connected again.
    open_dashboard(page, "board")


def keypad_dart(page: Page, recorder: Recorder, multiplier: str, bed: str) -> None:
    """A dart on the keypad: its multiplier, then its number."""
    card = page.locator(SCOREBOARD)
    if multiplier != "1":
        tap(
            page,
            recorder,
            card.locator(f"[data-pad='multiplier'][data-value='{multiplier}']"),
            350,
        )
    tap(page, recorder, card.locator(f".pad-number[data-value='{bed}']"), 600)


def manual_score_animation(page: Page, board: dict) -> None:
    """The score of a visit on the keypad: Alex switches to it, checks out 40 of 101
    with two darts, one of them at a double, and wins the match against Sam, whose
    summary counts the checkout."""
    page.evaluate(
        CALL_ACTION,
        ["start_game", {**board, "game": "101", "players": ["Alex", "Sam"], "legs": 1}],
    )
    for score in (61, 45):
        page.evaluate(CALL_ACTION, ["enter_visit", {**board, "score": score}])
    tablet_page = tablet(page, f"{MANUAL_DASHBOARD}/scoreboard")
    wait_card(tablet_page, "!!r.querySelector('.pad')", SCOREBOARD, 60000)
    ready(tablet_page)
    recorder = Recorder(tablet_page, SCOREBOARD)
    recorder.shot(1400)
    card = tablet_page.locator(SCOREBOARD)
    tap(tablet_page, recorder, card.locator(".pad [data-pad='score']"), 900)
    for digit in "40":
        tap(
            tablet_page,
            recorder,
            card.locator(f".pad-score [data-value='{digit}']"),
            500,
        )
    recorder.shot(800)
    tap(tablet_page, recorder, card.locator("[data-pad='enter']"), 1200)
    tap(
        tablet_page, recorder, card.locator("[data-pad='answer'][data-value='2']"), 1200
    )
    tap(tablet_page, recorder, card.locator("[data-pad='answer'][data-value='1']"), 300)
    wait_card(
        tablet_page,
        "!r.querySelector('.banner').hidden && !!r.querySelector('table.summary')",
        SCOREBOARD,
    )
    # No key under the finger stays lit at the end.
    tablet_page.mouse.move(0, 0)
    tablet_page.wait_for_timeout(1200)
    recorder.shot(3000)
    recorder.save("manual-score")
    tablet_page.close()


# What the voice animation says to Assist, and what Assist answers.
VOICE_SENTENCES = {
    "en": [
        ("Alex has 140", "140 for Alex, 361 left. Sam, you require 501."),
        ("Triple 20", "Triple 20, 441 left."),
        ("Single bull", "25, 416 left."),
    ],
    "de": [
        ("Alex hat 140", "140 für Alex, noch 361. Sam, du brauchst 501."),
        ("Triple 20", "Triple 20, noch 441."),
        ("Single Bull", "25, noch 416."),
    ],
}
ASSIST = "ha-voice-command-dialog"
# Home Assistant's sidebar stays out of the picture of a dialog over the scoreboard.
NO_SIDEBAR = "localStorage.setItem('dockedSidebar', JSON.stringify('always_hidden'))"


def manual_voice_animation(page: Page, entry: str) -> None:
    """Darts by voice: on the tablet at a dartboard without Autodarts, Alex's visit
    and two darts of Sam's go in through Assist, which answers in the words of the
    caller, and the scoreboard shows them once the dialog closes."""
    automation = {
        "id": "homedarts_voice_darts",
        "alias": "Darts by voice",
        "use_blueprint": {
            "path": "Dennis-Otto/enter_darts_by_voice.yaml",
            "input": {"board": entry},
        },
    }
    folder = DEMO_CLOCK.parent / "automations"
    folder.mkdir(exist_ok=True)
    (folder / "voice_darts.yaml").write_text(json.dumps([automation]))
    reload = (
        "async () => document.querySelector('home-assistant').hass"
        ".callService('automation', 'reload', {})"
    )
    page.evaluate(reload)
    page.wait_for_function(
        "() => document.querySelector('home-assistant').hass"
        ".states['automation.darts_by_voice']?.state === 'on'",
        timeout=30000,
    )
    page.evaluate(
        CALL_ACTION,
        [
            "start_game",
            {"config_entry_id": entry, "game": "501", "players": ["Alex", "Sam"]},
        ],
    )
    board = page.context.new_page()
    board.add_init_script(NO_SIDEBAR)
    board.set_viewport_size({"width": 1280, "height": 800})
    board.goto(f"{HA}/{MANUAL_DASHBOARD}/scoreboard")
    wait_card(board, "!!r.querySelector('.pad')", SCOREBOARD, 60000)
    ready(board)
    recorder = Recorder(board, "home-assistant")
    recorder.shot(1600)
    board.locator("body").press("a")
    dialog = board.locator(ASSIST)
    field = dialog.get_by_role("textbox")
    field.wait_for(timeout=15000)
    board.wait_for_timeout(800)
    recorder.shot(700)
    for sentence, answer in VOICE_SENTENCES[LANGUAGE]:
        field.fill(sentence)
        recorder.shot(900)
        field.press("Enter")
        said = dialog.get_by_text(answer, exact=True)
        said.wait_for(timeout=20000)
        # The chat does not always follow its answer down; the picture does.
        said.scroll_into_view_if_needed()
        board.wait_for_timeout(900)
        recorder.shot(2200)
    board.keyboard.press("Escape")
    dialog.get_by_role("textbox").wait_for(state="hidden", timeout=15000)
    board.wait_for_timeout(1200)
    recorder.shot(2600)
    recorder.save("manual-voice")
    board.evaluate("localStorage.removeItem('dockedSidebar')")
    board.close()
    (folder / "voice_darts.yaml").unlink()
    page.evaluate(reload)


def manual_board(page: Page) -> None:
    """A dartboard without Autodarts beside the demo board: the setup form, a visit
    entered with taps on the scoreboard's keypad, and the live card with the keypad
    while the next player enters darts. It leaves the demo again afterwards."""
    open_dashboard(page, "board")
    manual_setup(page)
    entry = page.evaluate(ADD_MANUAL_BOARD, "Garage")
    page.wait_for_function(f"() => ({MANUAL_DEVICE})('{entry}')", timeout=30000)
    device = page.evaluate(MANUAL_DEVICE, entry)
    page.evaluate(SAVE_MANUAL_DASHBOARD, [MANUAL_DASHBOARD, device])
    board = {"config_entry_id": entry}
    page.evaluate(
        CALL_ACTION,
        ["start_game", {**board, "game": "501", "players": ["Alex", "Sam"], "legs": 1}],
    )
    tablet_page = tablet(page, f"{MANUAL_DASHBOARD}/scoreboard")
    wait_card(tablet_page, "!!r.querySelector('.pad')", SCOREBOARD, 60000)
    ready(tablet_page)
    recorder = Recorder(tablet_page, SCOREBOARD)
    recorder.shot(1400)
    keypad_dart(tablet_page, recorder, "3", "T20")
    keypad_dart(tablet_page, recorder, "3", "T20")
    keypad_dart(tablet_page, recorder, "3", "T19")
    wait_card(
        tablet_page, "r.querySelector('.sum .value')?.textContent === '177'", SCOREBOARD
    )
    recorder.shot(1600)
    card = tablet_page.locator(SCOREBOARD)
    tap(tablet_page, recorder, card.locator("[data-pad='next']"), 700)
    tap(tablet_page, recorder, card.locator("[data-pad='next']"), 300)
    wait_card(tablet_page, "!!r.querySelector('.player.active')", SCOREBOARD)
    tablet_page.wait_for_timeout(600)
    recorder.shot(2600)
    recorder.save("manual-entry")
    tablet_page.close()
    # Sam enters two darts; the live card shows them on its board.
    for segment in ("T20", "S19"):
        page.evaluate(CALL_ACTION, ["throw_dart", {**board, "segment": segment}])
    page.goto(f"{HA}/{MANUAL_DASHBOARD}/live")
    wait_card(page, "r.querySelector('.score')?.textContent === '79'", timeout=60000)
    page.wait_for_timeout(800)
    # Taller than the window: without a scroll, which would start the blink of the
    # darts' beds anew, so they show at full strength in every run.
    tall_card_shot(page, "manual-live")
    manual_score_animation(page, board)
    manual_voice_animation(page, entry)
    page.evaluate(
        """async ([path, entry]) => {
          const hass = document.querySelector('home-assistant').hass;
          const dashboards = await hass.callWS({ type: 'lovelace/dashboards/list' });
          const dashboard = dashboards.find((item) => item.url_path === path);
          await hass.callWS({ type: 'lovelace/dashboards/delete', dashboard_id: dashboard.id });
          await hass.callApi('DELETE', `config/config_entries/entry/${entry}`);
        }""",
        [MANUAL_DASHBOARD, entry],
    )


# The groups of images --------------------------------------------------------------


# The quick start, from the discovered board to the scoreboard --------------------------

# Square and narrow: Home Assistant lays itself out as on a phone, and the picture reads
# at the width of a phone as well as across the column of a README on a big screen.
SETUP_WINDOW = {"width": 600, "height": 600}
SETUP_WIDTH = 900
SETUP_CAPTIONS = {
    "en": (
        "Home Assistant finds your board by itself",
        "Select Add and confirm: no account",
        "Settings → Dashboards → Add dashboard",
        "Choose HomeDarts and give it a title",
        "Your scoreboard, in under a minute",
    ),
    "de": (
        "Home Assistant findet dein Board selbst",
        "Hinzufügen wählen und bestätigen: kein Konto nötig",
        "Einstellungen → Dashboards → Dashboard hinzufügen",
        "HomeDarts wählen und einen Titel geben",
        "Deine Anzeigetafel, in unter einer Minute",
    ),
}
# The words of Home Assistant on the buttons of the way there.
SETUP_BUTTONS = {
    "en": {
        "add": "Add",
        "add integration": "Add integration",
        "submit": "Submit",
        "finish": "Skip and finish",
        "add dashboard": "Add dashboard",
        "create": "Create",
    },
    "de": {
        "add": "Hinzufügen",
        "add integration": "Integration hinzufügen",
        "submit": "OK",
        "finish": "Überspringen und fertigstellen",
        "add dashboard": "Dashboard hinzufügen",
        "create": "Erstellen",
    },
}
# The band with the caption, in pixels of the window: room for two lines on every
# frame, so that the picture keeps its height. Liberation Sans comes with the Playwright
# image.
CAPTION_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
CAPTION_HEIGHT = 84
CAPTION_TEXT = 25
CAPTION_MARGIN = 16
CAPTION_BADGE = 44
CAPTION_BAND = (1, 87, 155)
CAPTION_INK = (255, 255, 255)
# What a new user has: a board that Home Assistant found, no entry for it, no dashboard
# of HomeDarts. The entry goes, and Home Assistant finds the announced board again by
# itself.
FRESH_START = """
async () => {
  const hass = document.querySelector('home-assistant').hass;
  const entries = await hass.callApi('GET', 'config/config_entries/entry?domain=homedarts');
  for (const entry of entries) {
    await hass.callApi('DELETE', `config/config_entries/entry/${entry.entry_id}`);
  }
  for (const dashboard of await hass.callWS({ type: 'lovelace/dashboards/list' })) {
    if (dashboard.url_path.startsWith('homedarts')) {
      await hass.callWS({ type: 'lovelace/dashboards/delete', dashboard_id: dashboard.id });
    }
  }
}
"""
# The integration kept a backup of the removed board and offers it to the board that
# came back, on the settings page; a new user has no such backup.
NO_BACKUP_NOTE = """
async () => {
  const hass = document.querySelector('home-assistant').hass;
  const { issues } = await hass.callWS({ type: 'repairs/list_issues' });
  for (const issue of issues.filter((issue) => issue.domain === 'homedarts')) {
    await hass.callWS({
      type: 'repairs/ignore_issue', domain: issue.domain, issue_id: issue.issue_id, ignore: true,
    });
  }
}
"""
# The address of the simulated board in the Docker network depends on the machine: every
# picture shows the same one, as it might look in a home network.
SHOWN_ADDRESS = r"""
() => {
  (function show(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const text = walker.currentNode;
      const shown = text.data.replace(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g, '192.168.1.50');
      if (shown !== text.data) text.data = shown;
    }
    root.querySelectorAll('*').forEach((el) => el.shadowRoot && show(el.shadowRoot));
  })(document);
}
"""


def caption_lines(text: str, font: ImageFont.FreeTypeFont, width: float) -> list[str]:
    """A caption broken into the two lines of its band at most, or a clear failure."""
    lines = [""]
    for word in text.split():
        joined = f"{lines[-1]} {word}".strip()
        if font.getlength(joined) <= width:
            lines[-1] = joined
        else:
            lines.append(word)
    if len(lines) > 2 or any(font.getlength(line) > width for line in lines):
        raise ValueError(f"The caption does not fit in two lines: {text}")
    return lines


def with_caption(frame: Image.Image, step: int, text: str) -> Image.Image:
    """A frame under the band with the number of its step and its caption."""
    scale = frame.width / SETUP_WINDOW["width"]
    height = round(CAPTION_HEIGHT * scale)
    framed = Image.new("RGB", (frame.width, height + frame.height), CAPTION_BAND)
    framed.paste(frame.convert("RGB"), (0, height))
    draw = ImageDraw.Draw(framed)
    margin, badge = CAPTION_MARGIN * scale, CAPTION_BADGE * scale
    top = (height - badge) / 2
    draw.ellipse((margin, top, margin + badge, top + badge), fill=CAPTION_INK)
    font = ImageFont.truetype(CAPTION_FONT, round(CAPTION_TEXT * scale))
    draw.text(
        (margin + badge / 2, height / 2),
        str(step),
        font=font,
        fill=CAPTION_BAND,
        anchor="mm",
    )
    left = margin * 2 + badge
    lines = caption_lines(text, font, frame.width - left - margin)
    draw.multiline_text(
        (left, height / 2),
        "\n".join(lines),
        font=font,
        fill=CAPTION_INK,
        anchor="lm",
        spacing=round(4 * scale),
    )
    return framed


class CaptionRecorder(Recorder):
    """Frames of the whole window, each under the caption of its step."""

    def __init__(self, page: Page, captions: tuple[str, ...]) -> None:
        super().__init__(page)
        self.captions = captions
        self.step = 1

    def shot(self, duration: int, wait: bool = True) -> None:
        self.page.evaluate(SHOWN_ADDRESS)
        settle(self.page, wait)
        image = Image.open(io.BytesIO(self.page.screenshot(animations="allow")))
        caption = self.captions[self.step - 1]
        self.frames.append(with_caption(image, self.step, caption))
        self.durations.append(duration)


def quiet(page: Page) -> None:
    """Wait until a page of the settings, without cards, has what Home Assistant sends."""
    page.wait_for_function(WEBSOCKET_QUIET, arg=QUIET, timeout=15000, polling=POLL)
    page.evaluate(FRAMES)


def tap_to(
    page: Page,
    recorder: CaptionRecorder,
    target,
    arrives,
    hold: int,
    step: int | None = None,
) -> None:
    """Show the finger on the target, tap it, and show what it opens once it has, under
    the caption of the next step if it begins there."""
    box = target.bounding_box()
    page.evaluate(TAP, [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2])
    recorder.shot(600)
    page.evaluate(UNTAP)
    target.click()
    arrives.wait_for(timeout=30000)
    rest_pointer(page)
    quiet(page)
    recorder.step = step or recorder.step
    recorder.shot(hold)


def setup_animation(page: Page) -> None:
    """The way from the discovered board to the scoreboard, as a new user goes it,
    through the app and at the pace of a hand on a phone, with one cut to the settings."""
    words = SETUP_BUTTONS[LANGUAGE]

    def button(name: str):
        return page.get_by_role("button", name=words[name], exact=True).first

    pull_darts()
    page.goto(f"{HA}/config/integrations/dashboard")
    button("add integration").wait_for(timeout=30000)
    quiet(page)
    page.evaluate(FRESH_START)
    # Home Assistant finds the board again, and the card comes by itself.
    button("add").wait_for(timeout=60000)
    rest_pointer(page)
    quiet(page)
    recorder = CaptionRecorder(page, SETUP_CAPTIONS[LANGUAGE])
    recorder.shot(3000)

    # Add the board, and the board is there.
    tap_to(page, recorder, button("add"), button("submit"), 3000, step=2)
    tap_to(page, recorder, button("submit"), button("finish"), 3200)
    page.evaluate(NO_BACKUP_NOTE)
    # Home Assistant goes on to the page of the new device.
    tap_to(page, recorder, button("finish"), page.locator("ha-device-info-card"), 1500)

    # Settings, Dashboards, Add dashboard.
    recorder.step = 3
    settings = page.locator("a[href='/config/lovelace/dashboards']").first
    # No single tap leads there: the arrow of the page goes back through the integrations
    # and the steps that the dialogs of the setup left in the history of the browser. So
    # the picture cuts to the settings without showing a tap, and the caption names the way.
    page.evaluate(NAVIGATE, "/config/dashboard")
    settings.wait_for(timeout=30000)
    rest_pointer(page)
    quiet(page)
    recorder.shot(1800)
    settings.scroll_into_view_if_needed()
    add_dashboard = button("add dashboard")
    tap_to(page, recorder, settings, add_dashboard, 1600)

    # HomeDarts, with a title.
    search = page.locator("ha-dialog-new-dashboard input").first
    tap_to(page, recorder, add_dashboard, search, 1000, step=4)
    search.fill("HomeDarts")
    choice = page.locator("ha-dialog-new-dashboard").get_by_text(
        "HomeDarts", exact=True
    )
    choice.wait_for(timeout=15000)
    recorder.shot(2000)
    title = page.locator("dialog-lovelace-dashboard-detail input").first
    tap_to(page, recorder, choice, title, 700)
    title.fill("HomeDarts")
    rest_pointer(page)
    recorder.shot(1600)
    row = page.locator("ha-data-table").get_by_text("HomeDarts", exact=True).first
    tap_to(page, recorder, button("create"), row, 1600)

    # The dashboard, and its scoreboard.
    scoreboard_tab = page.get_by_role("tab").nth(1)
    tap_to(page, recorder, row, scoreboard_tab, 2000, step=5)
    tap_to(
        page,
        recorder,
        scoreboard_tab,
        page.locator(f"{SCOREBOARD} .single .big").first,
        2400,
    )
    # The first darts of the evening.
    for count, score in ((1, "60"), (2, "120"), (3, "180")):
        control({"event": "Throw detected", "throws": [T20] * count})
        wait_card(
            page, f"r.querySelector('.big')?.textContent === '{score}'", SCOREBOARD
        )
        recorder.shot(4000 if count == 3 else 1000)
    recorder.save("setup", width=SETUP_WIDTH)


def cards(browser: Browser) -> None:
    """The cards in both colour schemes and on a phone, their editors, the setup and
    the device page."""
    for scheme, suffix in (("dark", ""), ("light", "-light")):
        context = new_context(
            browser,
            viewport={"width": 1280, "height": 820},
            device_scale_factor=2,
            locale=LOCALE,
            color_scheme=scheme,
        )
        page = context.new_page()
        open_dashboard(page, "board")
        wait_for_score(page, "115")
        peak(page)
        card_shot(page, f"card{suffix}")
        training_card(page, suffix)
        status_card(page, suffix)
        if scheme == "dark":
            # While the current visit is on the board.
            live_positions(page)
            open_dashboard(page, "styles")
            peak(page)
            # The short card first, while the page is at the top: the tall one
            # scrolls it under the toolbar.
            card_shot(page, "card-board-only", 1)
            tall_card_shot(page, "card-flat-style", 0)
            editor(page)
            strategy_editor(page)
            config_flow(page)
            device_page(page)
            # Before the games, whose legs would end the graphs of the week.
            dashboard_trends(page)
        context.close()

    mobile = new_context(
        browser,
        viewport={"width": 412, "height": 915},
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
        locale=LOCALE,
        color_scheme="dark",
    )
    page = mobile.new_page()
    open_dashboard(page, "board")
    peak(page)
    card_shot(page, "card-mobile")
    training_card(page, "-mobile")
    mobile.close()


def live(browser: Browser) -> None:
    """The live card as the darts of a visit land and as a dart is corrected."""
    context = new_context(
        browser,
        # High enough for the whole card: a tap never scrolls it under the toolbar.
        viewport={"width": 1100, "height": 1000},
        device_scale_factor=1,
        locale=LOCALE,
        color_scheme="dark",
    )
    page = context.new_page()
    open_dashboard(page, "board")
    visit_animation(page)
    correct_live_animation(page)
    context.close()


def practice(browser: Browser) -> None:
    """A practice leg on the live card. After the cards and the live card, because
    the leg adds visits to the demo session."""
    context = new_context(
        browser,
        viewport={"width": 1280, "height": 820},
        device_scale_factor=2,
        locale=LOCALE,
        color_scheme="dark",
    )
    page = context.new_page()
    open_dashboard(page, "board")
    practice_card(page)
    context.close()


def games_context(browser: Browser) -> tuple[BrowserContext, Page]:
    """For the games as animations, at the size the documentation shows them: a
    context and its page on the board's dashboard."""
    context = new_context(
        browser,
        # The hold of a tournament result needs the time in the page to pass.
        flowing=True,
        viewport={"width": 1100, "height": 1100},
        device_scale_factor=1,
        locale=LOCALE,
        color_scheme="dark",
    )
    page = context.new_page()
    open_dashboard(page, "board")
    return context, page


def games(browser: Browser) -> None:
    """The first picture of the README, and games on the live card and the
    scoreboard."""
    context, page = games_context(browser)
    hero_animation(page)
    checkout_animation(page)
    cricket_animation(page)
    training_game_animation(page)
    training_plan_animation(page)
    scoreboard_animation(page)
    celebration_animation(page)
    cricket_hints_animation(page)
    wild_mouse_animation(page)
    killer_animation(page)
    lobby_animation(page)
    golf_animation(page)
    context.close()


def later_games(browser: Browser) -> tuple[BrowserContext, Page]:
    """A context for games as after the first picture of the README: the pages that
    open from now on show no sidebar, as that picture leaves it; the dashboard,
    already open, keeps it."""
    context, page = games_context(browser)
    page.evaluate(HIDE_SIDEBAR)
    return context, page


def more_games(browser: Browser) -> None:
    """More games and the bracket of a tournament of five."""
    context, page = later_games(browser)
    checkout_121_animation(page)
    tournament_bracket_animation(page)
    shanghai_animation(page)
    halve_it_animation(page)
    bermuda_animation(page)
    round_the_world_animation(page)
    gotcha_animation(page)
    random_cricket_scoreboard(page)
    hidden_cricket_animation(page)
    bull_off_animation(page)
    bobs_27_animation(page)
    context.close()


def corrections(browser: Browser) -> None:
    """A match against the bot, and a dart corrected on the scoreboard, on its board
    and with the loupe."""
    context, page = later_games(browser)
    bot_animation(page)
    correct_animation(page)
    correct_board_animation(page)
    correct_loupe_animation(page)
    context.close()


def formats(browser: Browser) -> None:
    """The new games and formats on the scoreboard."""
    context = new_context(
        browser,
        viewport={"width": 1280, "height": 1000},
        device_scale_factor=2,
        locale=LOCALE,
        color_scheme="dark",
    )
    page = context.new_page()
    open_dashboard(page, "board")
    tactics_scoreboard(page)
    wild_mouse_scoreboard(page)
    party_scoreboard(page)
    teams_scoreboard(page)
    handicap_scoreboard(page)
    baseball_scoreboard(page)
    catch_40_scoreboard(page)
    scoreboard_portrait(page)
    bot_scoreboard(page)
    keypad_screen(page)
    context.close()


def people(browser: Browser) -> None:
    """The players and their progress, the lobby, the tournaments, the media, the
    blueprints and the match summary, after the matches that fill the players card."""
    context = new_context(
        browser,
        viewport={"width": 1280, "height": 1000},
        device_scale_factor=2,
        locale=LOCALE,
        color_scheme="dark",
    )

    def on_board() -> Page:
        """A new page on the board's dashboard, for steps that call actions."""
        page = context.new_page()
        open_dashboard(page, "board")
        return page

    players_matches(on_board())
    players_card(context.new_page())
    doubles_card(context.new_page())
    lobby_screen(on_board())
    lobby_bot(on_board())
    lobby_fair(on_board())
    tournament_lobby(on_board())
    tournament_table(on_board())
    idle_screen(on_board())
    media_gallery(context.new_page())
    # After the doubles training, so the training view shows its doubles.
    strategy_dashboard(context.new_page())
    strategy_views(context.new_page())
    blueprints_page(context.new_page())
    board_events_dialog(context.new_page())
    online_bridge_options(context.new_page())
    progress_cards(context.new_page())
    # Recorded sharp at twice the size, shown at the size of the card.
    heatmap_animation(context.new_page())
    # Last: the match adds to the players and doubles of the cards above.
    page = context.new_page()
    open_dashboard(page, "board")
    match_summary(page)
    # After every other picture of its group: its darts count for the players.
    stream_overlay(page)
    fullscreen_scoreboard(page)
    context.close()


def tournaments(browser: Browser) -> None:
    """The big tournaments: groups with a knockout and a double elimination, 32
    players each, each up to its picture."""
    context = new_context(
        browser,
        viewport={"width": 1280, "height": 1000},
        device_scale_factor=2,
        locale=LOCALE,
        color_scheme="dark",
    )
    page = context.new_page()
    open_dashboard(page, "board")
    tournament_groups(page)
    tournament_double(page)
    context.close()


def calendar(browser: Browser) -> None:
    """The training calendar and the weekly report. Each opens a page in the demo's
    time zone; the report comes last, because it starts a new week."""
    page = browser.new_page()
    training_calendar(page)
    weekly_report_notification(page)
    page.close()


def manual(browser: Browser) -> None:
    """A dartboard without Autodarts. Last of its group: a second board would be the
    first of the cards without one."""
    context = new_context(
        browser,
        viewport={"width": 1280, "height": 1000},
        device_scale_factor=2,
        locale=LOCALE,
        color_scheme="dark",
    )
    manual_board(context.new_page())
    context.close()


def setup(browser: Browser) -> None:
    """The quick start, from the discovered board to the scoreboard. Last of its group:
    it removes the board of the demo and sets it up again as new."""
    context = new_context(
        browser,
        viewport=SETUP_WINDOW,
        device_scale_factor=2,
        locale=LOCALE,
        color_scheme="dark",
    )
    setup_animation(context.new_page())
    context.close()


SECTIONS: dict[str, Callable[[Browser], None]] = {
    "cards": cards,
    "live": live,
    "practice": practice,
    "games": games,
    "more games": more_games,
    "setup": setup,
    "corrections": corrections,
    "formats": formats,
    "people": people,
    "tournaments": tournaments,
    "calendar": calendar,
    "manual": manual,
}
# The images come in fixed groups of sections. Each group starts from a fresh demo,
# so that the visual check and the screenshot bot render the groups side by side,
# one runner each, and a group renders the same images on its own as after the
# others. The sections of a group run in their order: a later one sees what the
# earlier ones played. The groups take about the same time (SECONDS); screenshots.sh,
# visual.yml and screenshots.yml know how many there are.
GROUPS = (
    # The cards before the games, whose legs would end the graphs of the week.
    ("cards", "live", "practice", "games"),
    # The quick start removes the board of the demo: last in its group.
    ("more games", "setup"),
    # The players play their own matches. The dartboard without Autodarts last: its
    # second board would be the first of the cards without one.
    ("people", "manual"),
    # The bot plays its first match in the corrections, as it did before the groups.
    # The big tournaments before the calendar's weekly report, which starts a new week.
    ("corrections", "formats", "tournaments", "calendar"),
)
# The seconds of each section on a runner of GitHub, the mean of both languages in
# the visual check of 1 November 2026 (run 41288192544). No group may take more than
# SLOWER of group_times.py times the seconds of the shortest
# (tests/test_screenshot_groups.py), and the job that puts the groups of a language
# together marks one that did. Each job also starts its demo (STARTUP): with four
# groups, the longest job stays within nine minutes, and the runners take about as
# many minutes as with three.
SECONDS = {
    "cards": 43.0,
    "live": 27.0,
    "practice": 25.0,
    "games": 240.0,
    "more games": 284.0,
    # Came later: the mean of both languages in run 41328996823.
    "setup": 29.0,
    "people": 214.0,
    "corrections": 53.0,
    "formats": 122.0,
    "tournaments": 109.0,
    "calendar": 9.0,
    "manual": 46.0,
}
# The seconds of a job of a group before its first section and after its last: it
# pulls Home Assistant and starts its demo, about two and a half minutes, and keeps
# its images.
STARTUP = 160.0
# The seconds after which the watchdog fails a section (watchdog.py): about twice
# its longest run in CI (SECONDS) and at least two minutes, and with GRACE less than
# the time limit of its step in visual.yml and screenshots.yml.
SECTION_BUDGET = 120.0
BUDGETS = {
    "games": 510.0,
    "more games": 570.0,
    "formats": 270.0,
    "people": 450.0,
    "tournaments": 240.0,
}


def chosen_group(value: str) -> int:
    """The group that SCREENSHOT_GROUP, such as 2/4, chooses, counted from 1."""
    match = re.fullmatch(r"([1-9][0-9]*)/([1-9][0-9]*)", value.strip())
    if not match:
        raise SystemExit(
            f"SCREENSHOT_GROUP={value!r}: give the group and the number of groups,"
            f" such as 1/{len(GROUPS)}"
        )
    group, count = int(match[1]), int(match[2])
    if count != len(GROUPS) or group > count:
        raise SystemExit(
            f"SCREENSHOT_GROUP={value}: the screenshot tool has {len(GROUPS)} groups"
            f" of images, 1/{len(GROUPS)} to {len(GROUPS)}/{len(GROUPS)}"
        )
    return group


def main() -> None:
    group = chosen_group(os.environ.get("SCREENSHOT_GROUP", f"1/{len(GROUPS)}"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    timings: list[tuple[str, float]] = []
    # The inner context saves the open pages while the browser still runs.
    with sync_playwright() as playwright, failure_screenshots() as browsers:
        browser = playwright.chromium.launch(args=STEADY_CHROMIUM)
        browsers.append(browser)
        for name in GROUPS[group - 1]:
            began = monotonic()
            print(f"Screenshot section: {name}", flush=True)
            # A section that hangs fails after its budget with the line it waits at,
            # long before the time limit of the job.
            with budget(
                f"The section {name}",
                BUDGETS.get(name, SECTION_BUDGET),
                wake=wake_playwright,
            ):
                SECTIONS[name](browser)
            timings.append((name, monotonic() - began))
            print(f"Screenshot section: {name} ({timings[-1][1]:.1f} s)", flush=True)
        browser.close()
    # For the summary of the workflow run, to keep the groups about equally long:
    # the table of this group, and its seconds for the table of all groups of the
    # language (group_times.py).
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / f"screenshots-{LANGUAGE}-{group}.md").write_text(
        f"### Screenshots: group {group} of {len(GROUPS)} ({LANGUAGE})\n\n"
        "| Section | Seconds |\n| --- | ---: |\n"
        + "".join(f"| {name} | {seconds:.1f} |\n" for name, seconds in timings)
        + f"| all | {sum(seconds for _, seconds in timings):.1f} |\n",
        encoding="utf-8",
    )
    (ARTIFACTS / f"screenshots-{LANGUAGE}-{group}.json").write_text(
        json.dumps(
            {
                "language": LANGUAGE,
                "group": group,
                "groups": len(GROUPS),
                "sections": [[name, round(seconds, 1)] for name, seconds in timings],
            }
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    sys.exit(main())
