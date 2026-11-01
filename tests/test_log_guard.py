"""The guard of the log: Home Assistant's reports about the integration fail the tests.

Home Assistant warns in the logs of its own modules when the integration uses what a
coming release removes, or blocks the event loop. Each such report fails the test that
logged it, in ``tests/conftest.py``, and the end-to-end scenario, in its phase
``logs``, also against the beta of Home Assistant every night
(``tests/e2e/ha_reports.py``). The reports here are made by Home Assistant itself, so
a beta that changes their words fails these tests first.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from homeassistant.helpers import deprecation, frame
from homeassistant.loader import CUSTOM_WARNING
from homeassistant.util import loop

from .conftest import (
    CHECKED_LOG,
    ERRORS_EXPECTED,
    HA_VERSION,
    MANIFEST,
    log_problems,
    pytest_runtest_teardown,
)
from .e2e import ha_reports

E2E = Path(__file__).parent / "e2e"
HOMEDARTS = "custom_components/homedarts"


def old_helper() -> None:
    """A function that Home Assistant deprecates, called by the integration."""


def frame_report() -> None:
    frame.report_usage("accesses hass.data directly", breaks_in_ha_version="2099.1")


def blocking_call() -> None:
    loop.raise_for_blocking_call(open, strict=False, args=("/config/darts.json",))


def deprecated_call() -> None:
    deprecation.deprecated_function("its replacement", breaks_in_ha_version="2099.1")(
        old_helper
    )()


# Each report: how the integration makes it, the logger of Home Assistant that writes
# it, and how its message begins.
REPORTS = {
    "frame helper": (
        frame_report,
        "homeassistant.helpers.frame",
        "Detected that custom integration 'homedarts' accesses hass.data directly",
    ),
    "blocking call": (
        blocking_call,
        "homeassistant.util.loop",
        "Detected blocking call to open with args ('/config/darts.json',) inside the "
        "event loop by custom integration 'homedarts'",
    ),
    # Home Assistant writes it in the log of the module of the deprecated function.
    "deprecated function": (
        deprecated_call,
        __name__,
        "The deprecated function old_helper was called from homedarts.",
    ),
}


def reported(caplog, report) -> list[logging.LogRecord]:
    """The records of a report that Home Assistant makes, taken out of the log of
    the test, which would fail it."""
    caplog.clear()
    report()
    records = list(caplog.records)
    caplog.clear()
    return records


@pytest.fixture(autouse=True)
def forget_blocking_calls(monkeypatch):
    """Home Assistant reports a blocking call once per process, then at debug level;
    the mutation tests run the same test several times in one process."""
    monkeypatch.setattr(loop, "_PREVIOUSLY_REPORTED", set())


@pytest.mark.parametrize("integration_frame_path", [HOMEDARTS])
@pytest.mark.parametrize("report", REPORTS)
@pytest.mark.parametrize("errors_expected", [False, True])
async def test_a_report_of_home_assistant_fails_the_test(
    hass, caplog, mock_integration_frame, report, errors_expected
):
    make, logger, message = REPORTS[report]
    records = reported(caplog, make)
    problems = log_problems([("call", record) for record in records], errors_expected)
    assert len(problems) == 1
    assert problems[0].startswith(f"call: {logger}: {message}")


@pytest.mark.parametrize("integration_frame_path", [HOMEDARTS])
async def test_the_teardown_fails_with_the_message_of_home_assistant(
    hass, caplog, mock_integration_frame
):
    records = reported(caplog, frame_report)
    log = SimpleNamespace(
        get_records=lambda when: records if when == "teardown" else []
    )
    item = SimpleNamespace(stash={CHECKED_LOG: log, ERRORS_EXPECTED: True})
    teardown = pytest_runtest_teardown(item)
    next(teardown)
    with pytest.raises(AssertionError) as failure:
        teardown.send(None)
    # The failure quotes Home Assistant's message, with the phase and the logger.
    assert (
        "teardown: homeassistant.helpers.frame: Detected that custom integration "
        "'homedarts' accesses hass.data directly at custom_components/homedarts/"
        "light.py, line 23: self.light.is_on. This will stop working in Home "
        "Assistant 2099.1, please "
    ) in str(failure.value)


def test_a_clean_log_passes_the_teardown():
    log = SimpleNamespace(get_records=lambda when: [])
    teardown = pytest_runtest_teardown(
        SimpleNamespace(stash={CHECKED_LOG: log, ERRORS_EXPECTED: False})
    )
    next(teardown)
    with pytest.raises(StopIteration):
        teardown.send(None)


@pytest.mark.parametrize(
    "integration_frame_path",
    ["custom_components/other", "homeassistant/components/hue"],
)
async def test_a_report_about_another_integration_passes(
    hass, caplog, mock_integration_frame
):
    records = reported(caplog, frame_report)
    assert records
    assert log_problems([("call", record) for record in records], False) == []


@pytest.mark.parametrize("integration_frame_path", [HOMEDARTS])
async def test_a_report_below_a_warning_passes(hass, caplog, mock_integration_frame):
    records = reported(
        caplog,
        lambda: frame.report_usage("accesses hass.data directly", level=logging.INFO),
    )
    assert records
    assert log_problems([("call", record) for record in records], False) == []


def record(name: str, level: int, message: str) -> logging.LogRecord:
    return logging.LogRecord(name, level, __file__, 1, message, None, None)


@pytest.mark.parametrize(
    "unrelated",
    [
        record("homeassistant.loader", logging.WARNING, CUSTOM_WARNING % "homedarts"),
        record("custom_components.homedarts", logging.WARNING, "The board is away"),
        record("homeassistant.helpers.frame", logging.ERROR, "Detected that a sensor"),
    ],
    ids=["custom integration", "warning of the integration", "error of another"],
)
def test_an_unrelated_warning_passes(unrelated):
    assert log_problems([("call", unrelated)], False) == []


def test_an_error_of_the_integration_still_fails_unless_expected():
    error = record("custom_components.homedarts", logging.ERROR, "The board broke")
    assert log_problems([("setup", error)], False) == [
        "setup: custom_components.homedarts: The board broke"
    ]
    assert log_problems([("setup", error)], True) == []


@pytest.mark.parametrize(
    "message",
    [
        "Entity sensor.board_state is using state class 'total' which is impossible, "
        "please create a bug report at "
        "https://github.com/Dennis-Otto/homedarts-for-autodarts/issues",
        "Something went wrong, please report it to the author of the 'homedarts' "
        "custom integration",
    ],
)
def test_every_request_to_report_the_integration_counts(message):
    assert ha_reports.reports([message], MANIFEST, HA_VERSION) == [message]


def test_the_tracker_of_another_repository_is_no_report():
    message = (
        "please create a bug report at "
        "https://github.com/Dennis-Otto/homedarts-for-autodarts/issues-of-another"
    )
    assert ha_reports.reports([message], MANIFEST, HA_VERSION) == []


def test_a_known_report_passes_until_its_release():
    message = "Detected that custom integration 'homedarts' accesses hass.data directly"
    known = [
        ha_reports.Known(
            text="accesses hass.data directly",
            reason="Home Assistant offers no replacement before 2026.11.",
            until="2026.11",
        )
    ]
    assert ha_reports.reports([message], MANIFEST, "2026.10.1", known) == []
    assert ha_reports.reports([message], MANIFEST, "2026.11.0b0", known) == [message]
    assert ha_reports.reports(["Other " + message], MANIFEST, "2026.10.1", known) == []
    assert ha_reports.reports(
        [message.replace("hass.data", "hass.http")], MANIFEST, "2026.10.1", known
    ) == [message.replace("hass.data", "hass.http")]


@pytest.mark.parametrize(
    ("fields", "problem"),
    [
        ({"text": "", "reason": "No replacement yet.", "until": "2026.11"}, "needs"),
        ({"text": "hass.data", "reason": "", "until": "2026.11"}, "needs"),
        (
            {"text": "hass.data", "reason": "No replacement yet.", "until": "soon"},
            "not enough values",
        ),
    ],
    ids=["no text", "no reason", "no release"],
)
def test_a_known_report_names_its_text_reason_and_release(fields, problem):
    with pytest.raises(ValueError, match=problem):
        ha_reports.Known(**fields)


def test_the_releases_of_home_assistant_compare_by_year_and_month():
    assert ha_reports.release("2026.11.0b2") == (2026, 11)
    assert ha_reports.release("2026.9.3") < ha_reports.release("2026.10")
    assert ha_reports.release("2027.1.0.dev20261201") == (2027, 1)


# ------------------------------------------------------------- the end-to-end scenario

FRAME_REPORT = (
    "Detected that custom integration 'homedarts' accesses hass.data directly at "
    "custom_components/homedarts/sensor.py, line 23: self.hass.data. This will stop "
    "working in Home Assistant 2099.1, please create a bug report at "
    "https://github.com/Dennis-Otto/homedarts-for-autodarts/issues"
)


@pytest.fixture
def scenario(monkeypatch, tmp_path):
    """The scenario with the answers of Home Assistant and of the simulated Board
    Manager that its phase logs reads, without Docker."""
    monkeypatch.syspath_prepend(str(E2E))
    spec = importlib.util.spec_from_file_location("e2e_scenario", E2E / "scenario.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "e2e_scenario", module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "LOG", tmp_path / "home-assistant.log")
    monkeypatch.setattr(
        module, "MANIFEST", E2E.parents[1] / "custom_components/homedarts/manifest.json"
    )
    run = module.Scenario.__new__(module.Scenario)
    run.webhook_id = "e2e-webhook"
    run.system_log = []

    async def ws(command, **payload):
        return {
            "system_log/list": run.system_log,
            "get_config": {"version": "2026.11.0b1"},
        }[command]

    async def board(method, path, **kwargs):
        return {"unexpected": []}

    run.ws = ws
    run.board = board
    return SimpleNamespace(module=module, run=run, log=module.LOG)


def entry(level: str, name: str, message: str) -> dict:
    return {"level": level, "name": name, "message": [message], "count": 1}


async def test_the_scenario_fails_on_a_report_in_the_system_log(scenario):
    scenario.run.system_log.append(
        entry("WARNING", "homeassistant.helpers.frame", FRAME_REPORT)
    )
    with pytest.raises(scenario.module.E2EFailure) as failure:
        await scenario.run.logs()
    assert str(failure.value) == (
        f"Home Assistant reports the integration: {[FRAME_REPORT]}"
    )


async def test_the_scenario_fails_on_a_report_in_the_log_file(scenario):
    scenario.log.write_text(
        "2026-10-25 01:02:03.456 WARNING (MainThread) [homeassistant.loader] "
        + CUSTOM_WARNING % "homedarts"
        + "\n2026-10-25 01:02:04.000 WARNING (MainThread) [homeassistant.helpers.frame] "
        + FRAME_REPORT
        + "\n2026-10-25 01:02:05.000 DEBUG (MainThread) [custom_components.homedarts] "
        + "please report it to the author of the 'homedarts' custom integration\n"
    )
    scenario.run.system_log.append(
        entry("WARNING", "homeassistant.helpers.frame", FRAME_REPORT)
    )
    with pytest.raises(scenario.module.E2EFailure) as failure:
        await scenario.run.logs()
    # The same report in the system log and in the file is named once.
    assert str(failure.value) == (
        f"Home Assistant reports the integration: {[FRAME_REPORT]}"
    )


async def test_the_scenario_passes_a_log_without_reports(scenario):
    scenario.log.write_text(
        "2026-10-25 01:02:03.456 WARNING (MainThread) [homeassistant.loader] "
        + CUSTOM_WARNING % "homedarts"
        + "\n"
    )
    scenario.run.system_log.append(
        entry("WARNING", "homeassistant.loader", CUSTOM_WARNING % "homedarts")
    )
    await scenario.run.logs()


async def test_a_known_report_hides_no_other_report_of_its_entry(scenario, monkeypatch):
    # The system log groups the reports of the frame helper in one entry.
    other = FRAME_REPORT.replace("hass.data", "hass.http")
    known = [
        ha_reports.Known(
            text="accesses hass.data directly",
            reason="Home Assistant offers no replacement before 2099.1.",
            until="2099.1",
        )
    ]
    monkeypatch.setattr(
        scenario.module,
        "reports",
        lambda messages, manifest, version: ha_reports.reports(
            messages, manifest, version, known
        ),
    )
    scenario.run.system_log.append(
        {
            "level": "WARNING",
            "name": "homeassistant.helpers.frame",
            "message": [FRAME_REPORT, other],
            "count": 2,
        }
    )
    with pytest.raises(scenario.module.E2EFailure) as failure:
        await scenario.run.logs()
    assert str(failure.value) == f"Home Assistant reports the integration: {[other]}"
