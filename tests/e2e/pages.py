"""How the browser test waits for the cards, instead of sleeping for a fixed time.

A card draws itself at once and then fills in what Home Assistant sends over its
websocket, such as positions, profiles and trends. A page is settled when every card
has drawn itself, no request of the frontend waits for its answer, the websocket was
quiet for a moment, no animation of a card is running, and the browser has drawn two
frames since. browser.py waits for that, and for the states that a move at the board
sets, so that it checks a page as soon as it is ready and never too early. The
screenshot tool waits the same way until a page has loaded what Home Assistant
sends it, and then holds the animations of each picture itself.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from urllib.parse import urlsplit

from playwright.sync_api import BrowserContext, Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

# Milliseconds without a frame of the websocket before a page counts as settled:
# longer than the gaps between the frames of one update of Home Assistant.
QUIET = 100
# How often a page checks what it waits for, in milliseconds.
POLL = 50
# How far run_until() runs the clock of a page forward at a time, in milliseconds.
CLOCK_STEP = 1000

# Counts the requests of the frontend on Home Assistant's websocket that wait for their
# answer, and notes when the last frame went or came. Added to every page before its
# scripts run, so it wraps the socket the frontend opens. Home Assistant answers a
# request with a result, and a ping with a pong, under the request's id; it may put
# several answers into one frame as a list.
WS_PROBE = """
(() => {
  if (window.__ws) return;
  const Native = window.WebSocket;
  const ws = { sockets: new Set(), last: performance.now() };
  ws.waiting = () => [...ws.sockets].flatMap((socket) => [...socket.__waiting.values()]);
  window.__ws = ws;
  window.WebSocket = class extends Native {
    constructor(...args) {
      super(...args);
      this.__waiting = new Map();
      ws.sockets.add(this);
      // A socket that closes answers nothing more; its frontend asks again on a new one.
      this.addEventListener('close', () => ws.sockets.delete(this));
      this.addEventListener('message', (event) => {
        ws.last = performance.now();
        try {
          for (const message of [].concat(JSON.parse(event.data))) {
            if (message.type === 'result' || message.type === 'pong') this.__waiting.delete(message.id);
          }
        } catch (error) {}
      });
    }
    send(data) {
      ws.last = performance.now();
      try {
        const message = JSON.parse(data);
        if (message.id !== undefined) this.__waiting.set(message.id, message.type);
      } catch (error) {}
      return super.send(data);
    }
  };
})();
"""
# Whether every card on the page has drawn itself.
CARDS_DRAWN = """
() => {
  const cards = [];
  (function collect(root) {
    root.querySelectorAll('*').forEach((el) => {
      if (el.tagName.startsWith('HOMEDARTS-') && !el.tagName.endsWith('-EDITOR')) cards.push(el);
      if (el.shadowRoot) collect(el.shadowRoot);
    });
  })(document);
  return cards.length > 0 && cards.every((card) => card.shadowRoot?.querySelector('ha-card'));
}
"""
# Whether no request waits for its answer and no frame came for the given milliseconds.
WEBSOCKET_QUIET = """
(quiet) => Boolean(window.__ws) && window.__ws.waiting().length === 0
  && performance.now() - window.__ws.last > quiet
"""
# What still waits for its answer, for the message of a page that does not settle.
WEBSOCKET_WAITING = "() => window.__ws ? window.__ws.waiting() : 'no websocket probe'"
# The animations and transitions that run and end, in the cards ("cards") or anywhere on
# the page ("page"), by their names. Endless ones, such as the pulse of the latest dart,
# never end and don't count.
ANIMATIONS = """
(scope) => {
  const roots = scope === 'page' ? [document] : [];
  (function collect(root, inCard) {
    root.querySelectorAll('*').forEach((el) => {
      const card = inCard || el.tagName.startsWith('HOMEDARTS-');
      if (el.shadowRoot) {
        if (card || scope === 'page') roots.push(el.shadowRoot);
        collect(el.shadowRoot, card);
      }
    });
  })(document, false);
  return [...new Set(roots.flatMap((root) => root.getAnimations()))]
    .filter((animation) => animation.playState === 'running'
      && Number.isFinite(animation.effect?.getComputedTiming().endTime))
    .map((animation) => animation.animationName || animation.transitionProperty || 'animation');
}
"""
# Two frames: the browser has laid out and drawn what the last change brought.
FRAMES = "() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"
# The fonts of the page have loaded: text no longer shows in a font that stands in.
FONTS = "() => document.fonts.ready.then(() => true)"
# Opens a path within the app, as its links do, and notes the cards shown before, which
# leave the page once the new view replaces them.
NAVIGATE = """
(path) => {
  if (location.pathname === path) return;
  const cards = [];
  (function collect(root) {
    root.querySelectorAll('*').forEach((el) => {
      if (el.tagName.startsWith('HOMEDARTS-')) cards.push(el);
      if (el.shadowRoot) collect(el.shadowRoot);
    });
  })(document);
  window.__shownBefore = cards;
  history.pushState(null, '', path);
  window.dispatchEvent(new CustomEvent('location-changed', { detail: { replace: false } }));
}
"""
# Whether the view of the path replaced the one before and its cards have drawn.
SHOWN = f"""
(path) => location.pathname === path
  && (window.__shownBefore ?? []).every((card) => !card.isConnected)
  && ({CARDS_DRAWN})()
"""
# The states of Autodarts entities by their translation keys, from the frontend; null
# for one it doesn't know yet. A frontend that is still connecting may know the
# entities before their states: hass.states is null then, and a wait that read it
# without care failed at once with a TypeError instead of waiting.
STATES = """
(keys) => {
  const hass = document.querySelector('home-assistant')?.hass;
  return Object.fromEntries(keys.map((key) => {
    const entity = Object.values(hass?.entities ?? {}).find(
      (item) => item.platform === 'homedarts' && item.translation_key === key
    );
    return [key, entity ? hass.states?.[entity.entity_id]?.state ?? null : null];
  }));
}
"""
# Whether the frontend shows these states of Autodarts entities.
STATES_ARE = f"""
(expected) => {{
  const states = ({STATES})(Object.keys(expected));
  return Object.entries(expected).every(([key, value]) => states[key] === value);
}}
"""


class Unsettled(AssertionError):
    """A page that did not reach what the test waits for."""


def find(tag: str) -> str:
    """A page function returning every card element with this tag, in shadow roots too."""
    return f"""
() => {{
  const cards = [];
  (function collect(root) {{
    root.querySelectorAll('{tag}').forEach((card) => cards.push(card));
    root.querySelectorAll('*').forEach((el) => el.shadowRoot && collect(el.shadowRoot));
  }})(document);
  return cards;
}}
"""


def card_frame(cards: str) -> str:
    """A page function returning the frame around the first card that the page function
    `cards` finds, which a card has only in the edit mode of a dashboard."""
    return f"""
() => {{
  let frame = ({cards})()[0];
  while (frame && frame.localName !== 'hui-card-edit-mode') {{
    frame = frame.parentNode ?? frame.host;
  }}
  return frame ?? null;
}}
"""


def edit_card(cards: str) -> str:
    """A page function that opens the form of the first card that the page function
    `cards` finds, as its pencil does in the edit mode of a dashboard: with the path
    that Home Assistant gave the frame of the card. Home Assistant 2026.11 takes the
    path as it is, so a fixed one opens the first card of the first view."""
    return f"""
() => {{
  const frame = ({card_frame(cards)})();
  frame.dispatchEvent(new CustomEvent('ll-edit-card', {{
    bubbles: true, composed: true, detail: {{path: frame.path}},
  }}));
}}
"""


def open_card_form(page: Page, cards: str) -> None:
    """Open the form of the first card of a dashboard that has drawn it. Edit mode comes
    from the dashboard itself, as the address alone is not enough: Home Assistant drops
    ?edit=1 when the dashboard draws before it knows the user (#249)."""
    page.evaluate(f"() => ({find('hui-root')})()[0].lovelace.setEditMode(true)")
    page.wait_for_function(card_frame(cards), timeout=15000)
    page.evaluate(edit_card(cards))
    # Home Assistant builds the form of the card from getConfigForm.
    page.locator("hui-form-editor ha-form").first.wait_for(timeout=15000)


def probe(target: Page | BrowserContext) -> None:
    """Follow the websocket of every page of a context, or of one page, from its load."""
    target.add_init_script(WS_PROBE)


def where(page: Page) -> str:
    """The address of a page, the size of its screen and its language: the screens of a
    step show the same address, so a wait that runs out names its screen too."""
    size = page.viewport_size
    screen = f" at {size['width']}x{size['height']}" if size else ""
    try:
        language = f" in {page.evaluate('() => navigator.language')}"
    except Exception:  # A page that broke still names its address and screen.
        language = ""
    return f"{page.url}{screen}{language}"


def wait_for(
    pages: Iterable[Page],
    expression: str,
    arg: object = None,
    timeout: int = 15000,
    what: str = "",
) -> None:
    """Wait until a page function returns something true on every page. A page that
    does not get there names itself and what it waited for: the given words, or the
    end of the function, where its selector or comparison is."""
    for page in pages:
        try:
            page.wait_for_function(expression, arg=arg, timeout=timeout, polling=POLL)
        except PlaywrightTimeout as error:
            waited = what or " ".join(expression.split())
            if len(waited) > 120:
                waited = f"...{waited[-117:]}"
            raise Unsettled(
                f"{where(page)}: {waited} did not become true in {timeout} ms"
            ) from error


def within_app(current: str, url: str) -> bool:
    """Whether show() opens the address within the app on a page at the current one: a
    page of the same Home Assistant, where neither address has a query or a fragment.
    The app reads those when it starts, such as ?edit=1 for edit mode, and keeps what
    they set when it opens another view within, so an address with one loads, and so
    does any view after one."""
    here, there = urlsplit(current), urlsplit(url)
    return here.netloc == there.netloc and not (
        here.query or here.fragment or there.query or there.fragment
    )


def show(pages: Page | Iterable[Page], url: str) -> None:
    """Open a view on every page at once, until its cards have drawn: loaded on a page
    that shows nothing of Home Assistant yet, and within the app on one that does, as
    its links do. That keeps the frontend and its websocket, and takes a tenth of a
    second instead of a load of the whole app. An address with a query or a fragment,
    and any view after one, always loads (see within_app)."""
    pages = [pages] if isinstance(pages, Page) else list(pages)
    target = urlsplit(url)
    for page in pages:
        if within_app(page.url, url):
            page.evaluate(NAVIGATE, target.path)
        else:
            # Only until the page is there: its cards are what the next lines wait for.
            page.goto(url, wait_until="commit")
    for page in pages:
        try:
            page.wait_for_function(SHOWN, arg=target.path, timeout=30000, polling=POLL)
        except PlaywrightTimeout as error:
            raise Unsettled(
                f"{where(page)}: the view of {target.path} did not replace the one"
                " before or its cards did not draw"
            ) from error


def loaded(*pages: Page) -> None:
    """Wait until every page has what Home Assistant sends it: its cards drawn, its
    fonts loaded and its websocket quiet. The screenshot tool waits for no more,
    because it holds the animations of a picture itself."""
    wait_for(pages, CARDS_DRAWN, timeout=30000, what="every card drawn")
    for page in pages:
        page.evaluate(FONTS)
    for page in pages:
        try:
            page.wait_for_function(
                WEBSOCKET_QUIET, arg=QUIET, timeout=15000, polling=POLL
            )
        except PlaywrightTimeout as error:
            waiting = page.evaluate(WEBSOCKET_WAITING)
            raise Unsettled(
                f"{where(page)}: the websocket does not get quiet;"
                f" waiting for {waiting}"
            ) from error


def settle(*pages: Page, scope: str = "cards") -> None:
    """Wait until every page is settled: loaded, the animations of its cards (or with
    scope "page", of the whole page) ended, and two frames drawn since."""
    loaded(*pages)
    for page in pages:
        try:
            page.wait_for_function(
                f"() => ({ANIMATIONS})({scope!r}).length === 0",
                timeout=15000,
                polling=POLL,
            )
        except PlaywrightTimeout as error:
            running = page.evaluate(ANIMATIONS, scope)
            raise Unsettled(
                f"{where(page)}: animations do not end: {running}"
            ) from error
    for page in pages:
        page.evaluate(FRAMES)


def expect_state(pages: Iterable[Page], expected: Mapping[str, str]) -> None:
    """Wait until every page shows these states of Autodarts entities, by their
    translation keys, such as {"num_throws": "2"} after the second dart of a visit."""
    for page in pages:
        try:
            page.wait_for_function(
                STATES_ARE, arg=dict(expected), timeout=15000, polling=POLL
            )
        except PlaywrightTimeout as error:
            shown = page.evaluate(STATES, list(expected))
            raise Unsettled(
                f"{where(page)}: expected {dict(expected)}, the page shows {shown}"
            ) from error


def showing(card: Locator) -> str:
    """The text a card shows, in one line and cut to 120 characters, so a wait that
    runs out says which screen of the card it stayed on."""
    try:
        text = " ".join(card.first.inner_text(timeout=1000).split())
    except Exception:  # A card that is gone or broke still lets the step name it.
        return "nothing"
    if not text:
        return "no text"
    return repr(text if len(text) <= 120 else f"{text[:117]}...")


def run_until(
    page: Page, target: Locator, within: int, what: str, card: Locator
) -> None:
    """Run the clock of a page forward until the target shows. A step checks what a
    timer of a card leads to, such as the table after the summary of a match or idle
    mode, in a moment instead of waiting the timer out: the page runs Playwright's
    clock, installed with page.clock.install() before it loads, and run_for() fires
    every timer that falls due on the way, as the time would. The clock runs a second
    at a time, not by the whole time of the timer at once, because a card may start
    its timer a moment after the step sees what it waits for. A target that has not
    shown after `within` milliseconds on the clock fails the step with what it is and
    what the card showed instead, such as the summary of the match or the scoreboard."""
    ran = 0
    while not target.is_visible():
        if ran >= within:
            raise Unsettled(
                f"{where(page)}: {what} did not show within {within} ms"
                f" on the clock of the page; the card showed {showing(card)}"
            )
        page.clock.run_for(CLOCK_STEP)
        ran += CLOCK_STEP
