"""The watchdog of the end-to-end tests (tests/e2e/watchdog.py), checked without
Docker: a step that hangs fails soon after its budget, with its name and the line
that it waits at, also when it waits in Playwright's sync API; a step that ends in
time passes; and the process ends at its deadline when nothing else ends the hang.

The browser test checks the watchdog once more on Playwright itself, in its step
"the watchdog"."""

import asyncio
import importlib.util
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

E2E = Path(__file__).parent / "e2e"
SPEC = importlib.util.spec_from_file_location("e2e_watchdog", E2E / "watchdog.py")
assert SPEC is not None and SPEC.loader is not None
watchdog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watchdog)
Overrun = watchdog.Overrun

# The budgets send a signal to the main thread, which POSIX has and the containers of
# the tests run; Windows has no such signal.
needs_signals = pytest.mark.skipif(
    not hasattr(signal, "pthread_kill"), reason="the budgets use the signals of POSIX"
)


class Hung(AssertionError):
    """A failure of a kind of its own, as BrowserFailure of browser.py."""


def wait_forever() -> None:
    threading.Event().wait()  # the line that the step waits at


@needs_signals
@pytest.mark.parametrize("failure", [Overrun, Hung])
def test_a_step_that_hangs_fails_soon_after_its_budget(capfd, failure):
    started = time.monotonic()
    with (
        pytest.raises(failure, match=r"^a hung step took longer than 0\.2 s$"),
        watchdog.budget("a hung step", 0.2, failure),
    ):
        wait_forever()

    assert time.monotonic() - started < 2
    printed = capfd.readouterr().err
    assert "Watchdog: a hung step took longer than 0.2 s. It waits here:\n" in printed
    # The stack ends in the line that the step waits at.
    assert "in wait_forever\n    threading.Event().wait()" in printed


@needs_signals
def test_a_step_that_ends_in_time_passes_and_leaves_no_alarm_behind():
    with watchdog.budget("a quick step", 0.3):
        pass

    # Its time runs out after it ended: nothing happens.
    assert not threading.Event().wait(0.5)
    assert watchdog._running == []


@needs_signals
def test_a_budget_in_another_runs_out_on_its_own():
    with watchdog.budget("a step", 5) as outer:
        with (
            pytest.raises(Overrun, match=r"^a wait took longer than 0\.2 s$"),
            watchdog.budget("a wait", 0.2),
        ):
            wait_forever()
        # The step goes on, within its own budget.
        assert not outer.fired
    assert not outer.fired


@needs_signals
def test_a_step_that_goes_on_after_its_time_ran_out_fails_nevertheless():
    # As wake_playwright does: the wake ends the wait another way and says where the
    # step waited, and the step goes on.
    woken = threading.Event()

    def wake(frame):
        woken.set()
        return frame

    with (
        pytest.raises(Overrun, match=r"^a step took longer than 0\.2 s$") as raised,
        watchdog.budget("a step", 0.2, wake=wake),
    ):
        woken.wait()
    assert raised.value.__cause__ is None

    # What the step raises afterwards, such as the cancellation of a call of
    # Playwright, is the cause.
    woken.clear()

    def cancelled_once_woken() -> None:
        woken.wait()
        raise asyncio.CancelledError

    with (
        pytest.raises(Overrun) as raised,
        watchdog.budget("a step", 0.2, wake=wake),
    ):
        cancelled_once_woken()
    assert isinstance(raised.value.__cause__, asyncio.CancelledError)


@needs_signals
def test_an_alarm_that_no_budget_sent_goes_to_the_handler_before():
    # Such as the alarm of pytest-timeout.
    alarms = []
    before = signal.signal(signal.SIGALRM, lambda *_: alarms.append("before"))
    try:
        with watchdog.budget("a step", 5) as step:
            signal.raise_signal(signal.SIGALRM)
            assert alarms == ["before"]
        assert not step.fired
    finally:
        signal.signal(signal.SIGALRM, before)


def run_python(code: str) -> subprocess.CompletedProcess[str]:
    """Run code with the watchdog in a process of its own, which it may end."""
    return subprocess.run(
        [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(E2E)!r})\n{code}"],
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=20,
    )


def test_a_process_that_is_still_in_its_deadline_ends_with_every_stack():
    started = time.monotonic()
    result = run_python(
        "import threading, watchdog\n"
        "with watchdog.deadline(0.5):\n"
        "    threading.Event().wait()\n"
        "print('never')\n"
    )

    assert time.monotonic() - started < 10
    assert result.returncode == 1
    assert "never" not in result.stdout
    # faulthandler names the timeout and prints the stack of every thread.
    assert "Timeout (0:00:00." in result.stderr
    # The line that waits, after the line of run_python that finds the module.
    assert 'File "<string>", line 4 in <module>' in result.stderr


@needs_signals
def test_a_hang_that_no_exception_ends_ends_the_process_after_the_grace():
    # A wake that wakes nothing: the step keeps waiting after its budget.
    result = run_python(
        "import threading, watchdog\n"
        "watchdog.GRACE = 0.5\n"
        "with watchdog.budget('a stuck step', 0.2, wake=lambda frame: frame):\n"
        "    threading.Event().wait()\n"
    )

    assert result.returncode == 1
    assert "Watchdog: a stuck step took longer than 0.2 s" in result.stderr
    assert "Timeout (0:00:00." in result.stderr


async def inner_wait() -> None:
    await asyncio.Event().wait()


async def hung_phase() -> None:
    await inner_wait()


async def test_a_phase_that_hangs_fails_soon_after_its_budget(capsys):
    started = time.monotonic()
    with pytest.raises(Hung, match=r"^The phase realtime took longer than 0\.2 s$"):
        await watchdog.within("The phase realtime", 0.2, hung_phase(), Hung)

    assert time.monotonic() - started < 2
    printed = capsys.readouterr().out
    assert "Watchdog: The phase realtime took longer than 0.2 s. It waits here:" in (
        printed
    )
    # Every coroutine that waits for the next, to the line of the innermost.
    assert printed.index("in hung_phase") < printed.index("in inner_wait")
    assert "    await asyncio.Event().wait()" in printed


async def test_a_phase_that_ends_in_time_gives_its_result():
    assert await watchdog.within("A phase", 5, asyncio.sleep(0, "done")) == "done"


async def test_a_phase_that_fails_fails_as_it_did():
    async def failing() -> None:
        raise Hung("a check of the phase")

    with pytest.raises(Hung, match=r"^a check of the phase$"):
        await watchdog.within("A phase", 5, failing())


# Playwright's sync API -----------------------------------------------------------


class Bridge:
    """Playwright's sync API in small, as playwright/_impl/_sync_base.py runs it: the
    event loop in a greenlet of its own, the dispatcher, and every call a task, marked
    with __pw_stack__, that the main greenlet waits for while the dispatcher runs."""

    def __init__(self, greenlet) -> None:
        self.greenlet = greenlet
        self.loop = asyncio.new_event_loop()
        self.stopped = self.loop.create_future()
        self.dispatcher = greenlet.greenlet(
            lambda: self.loop.run_until_complete(self.stopped)
        )

    def call(self, coroutine):
        caller = self.greenlet.getcurrent()
        task = self.loop.create_task(coroutine)
        task.__pw_stack__ = []
        task.add_done_callback(lambda _: caller.switch())
        while not task.done():
            self.dispatcher.switch()
        return task.result()

    def close(self) -> None:
        self.stopped.set_result(None)
        while not self.dispatcher.dead:
            self.dispatcher.switch()
        self.loop.close()


@pytest.fixture
def bridge():
    playwright = Bridge(pytest.importorskip("greenlet"))
    yield playwright
    playwright.close()


async def never() -> None:
    await asyncio.get_running_loop().create_future()


@needs_signals
def test_a_wait_in_playwright_ends_cancelled_and_playwright_goes_on(bridge, capfd):
    started = time.monotonic()
    with (
        pytest.raises(
            Overrun, match=r"^a hung call took longer than 0\.2 s$"
        ) as raised,
        watchdog.budget("a hung call", 0.2, wake=watchdog.wake_playwright),
    ):
        bridge.call(never())  # the line that the step waits at

    assert time.monotonic() - started < 2
    assert isinstance(raised.value.__cause__, asyncio.CancelledError)
    # The next call, such as a screenshot of the page, works.
    assert bridge.call(asyncio.sleep(0, "still there")) == "still there"
    # The stack is that of the step, not that of the event loop it waited in.
    printed = capfd.readouterr().err
    assert "bridge.call(never())  # the line that the step waits at" in printed
    assert "run_until_complete" not in printed


@needs_signals
def test_a_wait_of_the_step_itself_beside_playwright_fails_where_it_waits(bridge):
    assert bridge.call(asyncio.sleep(0, "started")) == "started"

    with (
        pytest.raises(
            Overrun, match=r"^a hung step took longer than 0\.2 s$"
        ) as raised,
        watchdog.budget("a hung step", 0.2, wake=watchdog.wake_playwright),
    ):
        wait_forever()

    assert raised.value.__cause__ is None
    assert bridge.call(asyncio.sleep(0, "still there")) == "still there"


def test_the_watchdog_needs_only_the_standard_library():
    # The scenario imports it in the container of Home Assistant, which has no
    # greenlet: only wake_playwright imports it, when it runs.
    source = (E2E / "watchdog.py").read_text(encoding="utf-8")
    imports = {
        line.split()[1].split(".")[0]
        for line in source.splitlines()
        if line.startswith(("import ", "from "))
    }
    assert imports <= set(sys.stdlib_module_names) | {"__future__"}
