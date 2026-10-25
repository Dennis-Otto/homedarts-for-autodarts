"""Home Assistant fixtures for Autodarts."""

import asyncio
import functools
import json
import logging
import os
import re
import shutil
import sys
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component
from hypothesis import settings
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.amber import AmberSnapshotExtension

import custom_components

from .e2e import ha_reports

# The HA test plugin preloads its own custom_components package.
custom_components.__path__.insert(
    0, str(Path(__file__).parents[1] / "custom_components")
)

# Property tests never fail on a slow machine; in CI they replay the same
# examples on every run, so a failure shows up again on a retry.
settings.register_profile("local", deadline=None)
settings.register_profile("ci", deadline=None, derandomize=True, print_blob=True)


def hypothesis_profile(environ: Mapping[str, str]) -> str:
    """The profile of the property tests: the same examples in every run in CI
    and under mutmut, which sets MUTANT_UNDER_TEST before it imports the tests,
    so that a mutant is killed or survives the same way on every machine."""
    return "ci" if environ.get("CI") or "MUTANT_UNDER_TEST" in environ else "local"


settings.load_profile(hypothesis_profile(os.environ))

# The modules of the integration, by the names they are imported with.
INTEGRATION = Path(__file__).parents[1] / "custom_components" / "homedarts"
MODULES = tuple(
    "custom_components.homedarts" + ("" if path.stem == "__init__" else f".{path.stem}")
    for path in sorted(INTEGRATION.glob("*.py"))
)


# How much longer a test may take under mutmut than its time limit allows.
MUTMUT_SLOWDOWN = 10


def pytest_collection_modifyitems(config, items):
    """The frozen clock is set up before every other fixture of a test; under mutmut
    the tests marked mutation_unsafe are skipped, and every test gets ten times its
    time limit.

    A fixture set up before `freezer`, such as `hass` or the integration of a board,
    would run at the real time, and the clock would then jump back to QUIET_MOMENT:
    timers it armed against the wall clock would fire at the wrong moment or never.
    pytest-freezer does the same for a test with the marker freeze_time.

    mutmut runs the tests in its copy of the repository, `mutants/`, which has no Git
    and holds every mutant in the code: a test that reads the code as text or asks
    Git fails there whatever the mutant. Every call of a function that mutmut
    changes passes its trampoline, which records the caller in the first run, so
    the slowest tests take several times as long; mutmut stops a mutant that hangs
    by a time limit of its own. mutmut sets MUTANT_UNDER_TEST in each of its runs,
    to an empty value in the run without a mutant.
    """
    for item in items:
        if "freezer" in getattr(item, "fixturenames", ()):
            item.fixturenames.remove("freezer")
            item.fixturenames.insert(0, "freezer")
    if "MUTANT_UNDER_TEST" not in os.environ:
        return
    skip = pytest.mark.skip(reason="fails in mutmut's copy of the repository")
    for item in items:
        if item.get_closest_marker("mutation_unsafe"):
            item.add_marker(skip)
        # pytest-timeout takes the limit as the first argument or as `timeout=`, and
        # the method after it or as `method=`; the new marker keeps all but the limit.
        limit = item.get_closest_marker("timeout")
        args, kwargs = (limit.args, dict(limit.kwargs)) if limit else ((), {})
        seconds = kwargs.pop("timeout", args[0] if args else None)
        if seconds is None:
            seconds = config.getini("timeout") or 0
        item.add_marker(
            pytest.mark.timeout(float(seconds) * MUTMUT_SLOWDOWN, *args[1:], **kwargs),
            append=False,
        )


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """A test that changes its parameters fails.

    Run again in the same process, it would get the changed ones: mutmut runs every
    test several times in its first process and forks the process of each mutant
    from it, and an IDE runs a failed test again.
    """
    callspec = getattr(item, "callspec", None)
    before = repr(callspec.params) if callspec else ""
    result = yield
    if callspec and repr(callspec.params) != before:
        pytest.fail(
            f"The test changed its parameters from {before} to {callspec.params!r}; "
            "change a copy of them instead.",
            pytrace=False,
        )
    return result


@functools.cache
def module_caches(module: ModuleType) -> tuple[Callable[..., Any], ...]:
    """The functions with a functools cache that a module defines, such as those
    of the checkouts."""
    return tuple(
        value
        for value in vars(module).values()
        if not isinstance(value, type)
        and callable(getattr(value, "cache_clear", None))
        and getattr(value, "__module__", None) == module.__name__
    )


def clear_integration_caches() -> None:
    """Empties the functools caches of every module of the integration loaded so far."""
    for name in MODULES:
        if (module := sys.modules.get(name)) is not None:
            for cached in module_caches(module):
                cached.cache_clear()


@pytest.fixture(autouse=True)
def fresh_caches():
    """Every test starts with the caches of the integration empty, as if it ran alone.

    mutmut runs the tests of a mutant in a process that it forks from the one that
    ran all the tests first: a result cached there, from the code without the mutant,
    would hide the mutant. And while that first run records which tests call a
    function, a test that finds its result in the cache would not count.
    """
    clear_integration_caches()


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Snapshots live in tests/__snapshots__, whichever pytest plugin loads last.

    syrupy and the HA test plugin both define this fixture with different folders;
    the plugins' load order follows the order of the installed packages on disk.
    """
    return snapshot.use_extension(AmberSnapshotExtension)


@pytest.fixture(autouse=True)
def custom_integration(enable_custom_integrations):
    """Enable discovery of the real integration from this repository."""


@pytest.fixture(autouse=True)
def shipped_blueprints(request):
    """The integration brings its blueprints into the configuration folder, which in
    tests is a folder of the test harness: only the tests marked installs_blueprints
    let it, into a folder of their own."""
    if request.node.get_closest_marker("installs_blueprints"):
        yield
        return
    with patch("custom_components.homedarts.async_install_blueprints"):
        yield


@pytest.fixture(autouse=True)
def local_stream():
    """No external sockets in tests; stream-specific tests override this source."""

    async def idle_stream(self):
        await asyncio.Future()
        yield  # pragma: no cover

    with patch(
        "custom_components.homedarts.local_api.AutodartsLocalClient.events", idle_stream
    ):
        yield


# Where the clock of a test that freezes it starts: noon on a Wednesday in the time
# zone of the test harness, US/Pacific. The frozen clock used to start at the real
# time, and a test that moved it on by an hour heard the weekly report, due at the
# midnight before Monday, whenever it ran in the last hour of a week. From noon in the
# middle of a week, a test reaches the next midnight only with a tick of twelve hours
# and the end of the week only with one of four and a half days.
QUIET_MOMENT = "2026-10-14T12:00:00-07:00"


@pytest.fixture
def freezer(request, freezer):
    """The frozen clock at the same quiet moment in every run, unless the test names
    its own moment with the marker freeze_time."""
    if request.node.get_closest_marker("freeze_time") is None:
        freezer.move_to(QUIET_MOMENT)
    return freezer


# Loggers of the integration, those Home Assistant reports its entities with,
# and those of the WebSocket commands and webhooks it offers, which answer a
# crashing handler with an error of their own.
WATCHED_LOGGERS = (
    "custom_components.homedarts",
    "homeassistant.helpers.entity",
    "homeassistant.helpers.entity_platform",
    "homeassistant.components.websocket_api",
    "homeassistant.components.webhook",
)
# How the coordinator reports a board that is away, once per outage.
UNAVAILABLE = re.compile(r"Error fetching homedarts_local data: ")


# The manifest, whose domain and issue tracker Home Assistant's reports about the
# integration name (tests/e2e/ha_reports.py).
MANIFEST = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

# The log of a test that pytest_runtest_teardown checks, and whether the test logs
# errors of the integration on purpose.
CHECKED_LOG = pytest.StashKey[pytest.LogCaptureFixture]()
ERRORS_EXPECTED = pytest.StashKey[bool]()


@pytest.fixture(autouse=True)
def no_unexpected_errors(request, caplog):
    """An error in the log fails the test, unless it is marked expected_errors, and
    a report of Home Assistant about the integration fails every test."""
    request.node.stash[CHECKED_LOG] = caplog
    request.node.stash[ERRORS_EXPECTED] = (
        request.node.get_closest_marker("expected_errors") is not None
    )


def reported(record: logging.LogRecord) -> bool:
    """Whether Home Assistant reports the integration in a warning, whatever its
    logger, such as a deprecated call that its next release stops."""
    return record.levelno >= logging.WARNING and bool(
        ha_reports.reports([record.getMessage()], MANIFEST, HA_VERSION)
    )


def unexpected_error(record: logging.LogRecord) -> bool:
    """Whether an error of the integration or of the parts of Home Assistant that
    run its entities, WebSocket commands and webhooks fails the test."""
    return (
        record.levelno >= logging.ERROR
        and record.name.startswith(WATCHED_LOGGERS)
        and not UNAVAILABLE.match(record.getMessage())
    )


def log_problems(
    records: Iterable[tuple[str, logging.LogRecord]], errors_expected: bool
) -> list[str]:
    """The records of a test, each with the phase that logged it, that fail it: every
    report of Home Assistant about the integration, and the unexpected errors unless
    the test is marked expected_errors."""
    return [
        f"{when}: {record.name}: {record.getMessage()}"
        for when, record in records
        if reported(record) or (not errors_expected and unexpected_error(record))
    ]


@pytest.hookimpl(wrapper=True, trylast=True)
def pytest_runtest_teardown(item):
    """Checks the log once every fixture is torn down: hass last, which
    unloads the entries and stops Home Assistant.

    As the innermost wrapper, this runs while pytest still holds the records
    of the teardown.
    """
    yield
    caplog = item.stash.get(CHECKED_LOG, None)
    if caplog is None:
        return
    problems = log_problems(
        (
            (when, record)
            for when in ("setup", "call", "teardown")
            for record in caplog.get_records(when)
        ),
        item.stash[ERRORS_EXPECTED],
    )
    assert not problems, "\n".join(["The log of the test shows problems:", *problems])


@pytest.fixture
async def blueprint_folder(hass, tmp_path):
    """Serve the repository blueprints from a temporary configuration folder."""
    from .local_helpers import BLUEPRINTS

    hass.config.config_dir = str(tmp_path)
    shutil.copytree(BLUEPRINTS, tmp_path / "blueprints" / "automation" / "homedarts")
    assert await async_setup_component(hass, "event", {})


@pytest.fixture
async def client(hass, aioclient_mock):
    """A client for the board at the address of local_entry_data."""
    from custom_components.homedarts.local_api import AutodartsLocalClient

    return AutodartsLocalClient("192.0.2.10", 3180, async_get_clientsession(hass))


@pytest.fixture
async def two_boards(hass, aioclient_mock):
    """Two boards in one home, each with its own ID, address and cameras."""
    from .local_helpers import (
        SECOND_BASE,
        board,
        local_entry_data,
        mock_board,
        second_board_config,
    )

    mock_board(aioclient_mock, state=board())
    mock_board(
        aioclient_mock, state=board(), config=second_board_config(), base=SECOND_BASE
    )
    entries = []
    for board_id, host in (("board-1", "192.0.2.10"), ("board-2", "192.0.2.20")):
        entry = MockConfigEntry(
            domain="homedarts",
            version=2,
            unique_id=board_id,
            title=f"Autodarts ({host})",
            data=local_entry_data(board_id, host),
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entries.append(entry)
    return entries
