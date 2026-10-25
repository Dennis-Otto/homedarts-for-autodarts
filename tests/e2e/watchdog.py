"""Budgets of time for the steps of the end-to-end tests.

A step that hangs would otherwise run until the time limit of its job, and GitHub
cancels a job at its limit: no step after it runs, so the job keeps no logs and no
screenshots, and nothing explains it. With a budget, a step that takes far longer
than it ever did fails on its own while the job still runs, with its name, the line
that it waits at and the screenshots of its pages
(docs/development.md#when-a-step-hangs).

- ``budget()`` gives a step of browser.py, or a section of screenshots.py, its
  seconds. They drive the browser with Playwright's sync API, and
  ``wake_playwright()`` ends a wait in it without ending Playwright.
- ``within()`` gives a phase of the scenario, in asyncio, its seconds.
- ``deadline()`` is the last resort of both: a process that no exception reaches,
  such as one that hangs in C code, prints the stack of every thread and ends.

The module needs only the standard library, so that the scenario imports it in the
container of Home Assistant too; ``wake_playwright()`` imports greenlet, which only
the browser scripts have. tests/test_e2e_watchdog.py checks it.
"""

from __future__ import annotations

import asyncio
import faulthandler
import os
import signal
import sys
import threading
import time
import traceback
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from types import FrameType, TracebackType
from typing import Any

# Seconds after its budget for a step to end and keep its screenshots, after which
# deadline() ends the process: a hang that no exception breaks still ends long before
# the time limit of the step in the workflow (tests/test_e2e_workflow.py).
GRACE = 120.0


class Overrun(AssertionError):
    """A step took longer than its budget."""


# What a budget calls when its time runs out, with the frame that the signal stopped:
# None when the step runs in that frame, so that the budget raises its failure there,
# or the frame where the step waits, after it has woken the step another way.
Wake = Callable[[FrameType], FrameType | None]


class Budget:
    """The seconds of a step, as a context manager; see ``budget()``."""

    def __init__(
        self, name: str, seconds: float, failure: type[Exception], wake: Wake | None
    ) -> None:
        self.message = f"{name} took longer than {seconds:g} s"
        self.seconds = seconds
        self.failure = failure
        self.wake = wake
        self.ends = 0.0
        self.fired = False
        self.timer: threading.Timer | None = None

    def __enter__(self) -> Budget:
        _install()
        self.ends = time.monotonic() + self.seconds
        _running.append(self)
        _rearm()
        # A thread of its own sends the signal to the main thread: an alarm of the
        # process could reach another thread, and only a signal to the main thread
        # also ends a wait of the main thread in the kernel, such as the select() of
        # asyncio in which Playwright's sync API waits.
        self.timer = threading.Timer(self.seconds, _ring, args=(self,))
        self.timer.daemon = True
        self.timer.start()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> bool:
        assert self.timer is not None
        try:
            self.timer.cancel()
            self.timer.join()
        finally:
            _running.remove(self)
            _rearm()
        if not self.fired or (
            isinstance(error, self.failure) and str(error) == self.message
        ):
            return False
        # Whatever the step did after its time ran out, such as a wait of Playwright
        # that ended cancelled, or even nothing at all: it took too long either way.
        raise self.failure(self.message) from error


def budget(
    name: str,
    seconds: float,
    failure: type[Exception] = Overrun,
    wake: Wake | None = None,
) -> Budget:
    """Fail the step ``name`` with ``failure`` once it runs longer than ``seconds``.

    When its time runs out, the budget prints the stack of the step, so that the log
    shows the line that it waits at, and raises ``failure("<name> took longer than
    <seconds> s")`` where the step is, or lets ``wake`` wake it there. A budget in
    another runs out on its own. deadline() ends the process ``GRACE`` seconds after
    the end of a running budget. Needs the signals of POSIX and the main thread, as
    the scripts in the containers of the tests have them."""
    return Budget(name, seconds, failure, wake)


# The budgets that run, the outer ones first, and the handler of SIGALRM before ours.
_running: list[Budget] = []
_before: list[Any] = [signal.SIG_DFL]
# The budgets whose time ran out, until _expired handles their signal. Reentrant: a
# second signal may come while the handler of the first holds it.
_rung: list[Budget] = []
_rung_lock = threading.RLock()


def _install() -> None:
    """Handle SIGALRM, after the handler that was there, such as pytest-timeout's in a
    test. Ours stays: the signal of a budget that ended just after its time ran out
    still finds it, and a signal that no budget sent goes on to the one before."""
    current = signal.getsignal(signal.SIGALRM)
    if current is not _expired:
        _before[0] = current
        signal.signal(signal.SIGALRM, _expired)


def _ring(due: Budget) -> None:
    with _rung_lock:
        _rung.append(due)
    signal.pthread_kill(threading.main_thread().ident or 0, signal.SIGALRM)


def _expired(signum: int, frame: FrameType | None) -> None:
    with _rung_lock:
        rung = list(_rung)
        _rung.clear()
    if not rung:
        if callable(_before[0]):
            _before[0](signum, frame)
        return
    due = next((one for one in _running if one in rung and not one.fired), None)
    if due is None or frame is None:
        # The signal of a budget that ended just after its time ran out.
        return
    due.fired = True
    waiting = due.wake(frame) if due.wake is not None else None
    stack = "".join(traceback.format_stack(waiting or frame))
    # Straight to the file of stderr, as faulthandler writes: the step may have been
    # in the middle of a print, which a second print would break.
    os.write(2, f"Watchdog: {due.message}. It waits here:\n{stack}".encode())
    if waiting is None:
        raise due.failure(due.message)


# The end of each running deadline(), on the clock of time.monotonic().
_deadlines: list[float] = []


def _rearm() -> None:
    """Set the one timer of faulthandler to the earliest end of a running budget
    plus GRACE, or of a running deadline(), or cancel it."""
    ends = [one.ends + GRACE for one in _running] + _deadlines
    if not ends:
        faulthandler.cancel_dump_traceback_later()
        return
    # To the file of stderr itself, which faulthandler writes to in C.
    faulthandler.dump_traceback_later(
        max(min(ends) - time.monotonic(), 0.001), exit=True, file=sys.__stderr__
    )


@contextmanager
def deadline(seconds: float) -> Iterator[None]:
    """End the process with exit code 1 and the stack of every thread on stderr if it
    is still in this block after ``seconds``: for the screenshots of a step that
    failed, which no budget guards any longer, and for every budget ``GRACE``
    seconds after it ran out. faulthandler does it in C, from a thread of its own, so
    it works even when no Python code runs any more."""
    end = time.monotonic() + seconds
    _deadlines.append(end)
    _rearm()
    try:
        yield
    finally:
        _deadlines.remove(end)
        _rearm()


def wake_playwright(frame: FrameType) -> FrameType | None:
    """Wake a step that waits in a call of Playwright's sync API.

    The sync API runs the events of the browser with asyncio in a greenlet of its
    own, the dispatcher, and switches to it while a step waits for the task of a
    call. The signal of a budget comes in the greenlet that runs. In the step's own,
    the main greenlet of the thread, the budget raises its failure there. In the
    dispatcher an exception would end it, and with it every later call, such as the
    screenshots of the failure; so this cancels the tasks of the calls, which
    Playwright marks with ``__pw_stack__`` (playwright/_impl/_sync_base.py), and the
    step gets the cancellation where it waits. Returns the frame where the step
    waits, or None when the step itself runs."""
    import greenlet

    current = greenlet.getcurrent()
    if current.parent is None:
        return None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # Some other greenlet: the budget raises where it is.
        return None
    loop.call_soon_threadsafe(_cancel_calls, loop)
    step = current
    while step.parent is not None:
        step = step.parent
    waiting: FrameType | None = step.gr_frame
    return waiting


def _cancel_calls(loop: asyncio.AbstractEventLoop) -> None:
    for task in asyncio.all_tasks(loop):
        if hasattr(task, "__pw_stack__"):
            task.cancel()


def awaited_frames(awaitable: object) -> list[FrameType]:
    """The frames of the coroutines that wait for each other, from ``awaitable`` to
    the innermost one: a task waits in its coroutine, that one in the coroutine that
    it awaits, and so on as far as the first future."""
    frames: list[FrameType] = []
    current: object = awaitable
    while current is not None:
        if isinstance(current, asyncio.Task):
            current = current.get_coro()
            continue
        frame = getattr(current, "cr_frame", None) or getattr(current, "gi_frame", None)
        if frame is None:
            break
        frames.append(frame)
        current = getattr(current, "cr_await", None) or getattr(
            current, "gi_yieldfrom", None
        )
    return frames


def format_awaited(awaitable: object) -> str:
    """The stack of a waiting coroutine, as traceback prints a stack."""
    summary = traceback.StackSummary.extract(
        (frame, frame.f_lineno) for frame in awaited_frames(awaitable)
    )
    return "".join(summary.format())


async def within[T](
    name: str,
    seconds: float,
    run: Awaitable[T],
    failure: type[Exception] = Overrun,
) -> T:
    """Await ``run``, and fail with ``failure("<name> took longer than <seconds> s")``
    once it runs longer than ``seconds``, after printing the line that it waits at.
    deadline() ends the process ``GRACE`` seconds later, if the event loop itself
    hangs, such as in a call that blocks it."""
    task = asyncio.ensure_future(run)
    with deadline(seconds + GRACE):
        try:
            done, _ = await asyncio.wait({task}, timeout=seconds)
        except asyncio.CancelledError:
            task.cancel()
            raise
        if not done:
            message = f"{name} took longer than {seconds:g} s"
            print(
                f"Watchdog: {message}. It waits here:\n{format_awaited(task)}",
                flush=True,
            )
            task.cancel()
            await asyncio.wait({task}, timeout=GRACE)
            raise failure(message)
    return task.result()
