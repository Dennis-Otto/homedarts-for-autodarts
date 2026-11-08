"""The calibration that Board Manager 2 reports: whether the board holds one, and on
Board Manager 2.1 how exact the fit of each camera is.

tests/fixtures/board_manager holds what real boards answered: 2.0.0 and 2.0.2 report
calibrated and blocker, 2.1.0 also the fit of each of its three cameras, with an
error of 2.31, 1.33 and 0.40 pixels.
"""

import json

import pytest
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.diagnostics import async_get_config_entry_diagnostics
from custom_components.homedarts.local_api import (
    MAX_CAMERAS,
    AutodartsLocalClient,
    calibration_summary,
)
from custom_components.homedarts.local_coordinator import calibration_problem
from custom_components.homedarts.quality import QUALITY_MINIMUM

from .local_helpers import (
    BASE,
    board,
    entity_id,
    recorded,
    setup_local,
    setup_v2,
    state,
)
from .test_board_manager_2_1 import answer, reread, running_2_1
from .test_manual_board import setup_manual
from .test_start_game_and_quality import darts, fix

# The fit of each camera of the real board with Board Manager 2.1.0.
RECORDED_FITS = [
    {"camera": 1, "calibrated": True, "error_px": 2.31, "fit_failed": False},
    {"camera": 2, "calibrated": True, "error_px": 1.33, "fit_failed": False},
    {"camera": 3, "calibrated": True, "error_px": 0.4, "fit_failed": False},
]


def system_2_1(**status) -> dict:
    """The answer of the real board on Board Manager 2.1.0, with its status changed."""
    system = recorded("2.1.0", "system.json")
    system["status"].update(status)
    return system


def failed_fit(camera: int) -> dict:
    """The real board on 2.1.0, whose fit of one camera failed at its last calibration."""
    system = system_2_1()
    system["calibration"]["cams"][camera - 1]["fitFailed"] = True
    return system


def issue(hass, entry):
    return ir.async_get(hass).async_get_issue(DOMAIN, f"calibration_{entry.entry_id}")


def attributes(hass, platform, key):
    return hass.states.get(entity_id(hass, platform, key)).attributes


async def test_the_client_keeps_the_fit_of_each_camera_and_nothing_else(
    hass, aioclient_mock
):
    aioclient_mock.get(f"{BASE}/api/system", json=recorded("2.1.0", "system.json"))
    client = AutodartsLocalClient("192.0.2.10", 3180, async_get_clientsession(hass))
    system = (await client.get_system())["system"]
    assert system["calibrated"] is True
    assert system["blocker"] == "none"
    assert system["calibration"] == RECORDED_FITS
    # Never the matrices of a fit.
    for camera in system["calibration"]:
        assert set(camera) == {"camera", "calibrated", "error_px", "fit_failed"}


@pytest.mark.parametrize("version", ["2.0.0", "2.0.2"])
async def test_board_manager_2_0_reports_its_calibration_without_a_fit(
    hass, aioclient_mock, version
):
    aioclient_mock.get(f"{BASE}/api/system", json=recorded(version, "system.json"))
    client = AutodartsLocalClient("192.0.2.10", 3180, async_get_clientsession(hass))
    system = (await client.get_system())["system"]
    assert (system["calibrated"], system["blocker"]) == (True, "none")
    assert system["calibration"] == []


async def test_a_blocker_reads_in_the_words_of_the_board(hass, aioclient_mock):
    """One that a future Board Manager names reads as it is; no text, as unknown."""
    client = AutodartsLocalClient("192.0.2.10", 3180, async_get_clientsession(hass))
    for blocker, read in (("cameraMissing", "cameraMissing"), (3, None), ("", None)):
        aioclient_mock.clear_requests()
        aioclient_mock.get(f"{BASE}/api/system", json=system_2_1(blocker=blocker))
        assert (await client.get_system())["system"]["blocker"] == read


def test_a_fit_in_an_odd_shape_reads_as_unknown():
    assert calibration_summary("odd") == []
    assert calibration_summary({"cams": "odd"}) == []
    unknown = {"calibrated": None, "error_px": None, "fit_failed": None}
    odd = {"calibrated": "yes", "errorPx": float("nan"), "fitFailed": 1}
    assert calibration_summary({"cams": ["odd", odd, {"errorPx": True}]}) == [
        {"camera": 1, **unknown},
        {"camera": 2, **unknown},
        {"camera": 3, **unknown},
    ]
    many = calibration_summary({"cams": [{}] * (MAX_CAMERAS + 2)})
    assert len(many) == MAX_CAMERAS


def test_a_board_that_reports_nothing_of_its_calibration_has_no_problem_known():
    assert calibration_problem({}) is None
    assert (
        calibration_problem({"system": {"calibrated": None, "calibration": []}}) is None
    )
    # A fit without the word calibrated still tells.
    fit = {"camera": 1, "calibrated": None, "error_px": 1.0, "fit_failed": True}
    assert calibration_problem({"system": {"calibration": [fit]}}) is True


async def test_the_calibration_of_a_real_board_on_2_1(hass, aioclient_mock):
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    # The least exact camera.
    assert state(hass, "sensor", "calibration_error") == "2.31"
    assert (
        attributes(hass, "sensor", "calibration_error").items()
        >= {
            "unit_of_measurement": "px",
            "state_class": "measurement",
            "worst_camera": 1,
            "cameras": RECORDED_FITS,
        }.items()
    )
    assert state(hass, "binary_sensor", "calibration_problem") == "off"
    assert (
        attributes(hass, "binary_sensor", "calibration_problem").items()
        >= {
            "device_class": "problem",
            "blocker": "none",
            "failed_cameras": [],
        }.items()
    )
    registry = er.async_get(hass)
    for platform, key in (
        ("binary_sensor", "calibration_problem"),
        ("sensor", "calibration_error"),
    ):
        registered = registry.async_get(entity_id(hass, platform, key))
        assert registered.entity_category == EntityCategory.DIAGNOSTIC, key
        assert registered.disabled_by is None, key
    assert issue(hass, entry) is None


@pytest.mark.parametrize("version", ["2.0.0", "2.0.2"])
async def test_board_manager_2_0_tells_whether_it_is_calibrated_but_not_how_exact(
    hass, aioclient_mock, version
):
    entry = await setup_v2(hass, aioclient_mock, recording=version, state=board())
    assert state(hass, "binary_sensor", "calibration_problem") == "off"
    assert state(hass, "sensor", "calibration_error") == "unknown"
    assert (
        attributes(hass, "sensor", "calibration_error").items()
        >= {
            "worst_camera": None,
            "cameras": [],
        }.items()
    )
    assert issue(hass, entry) is None


async def test_a_failed_fit_is_a_problem_that_suggests_a_calibration(
    hass, aioclient_mock
):
    entry = await setup_v2(
        hass,
        aioclient_mock,
        recording="2.1.0",
        state=running_2_1(),
        system=failed_fit(1),
    )
    assert state(hass, "binary_sensor", "calibration_problem") == "on"
    assert attributes(hass, "binary_sensor", "calibration_problem")[
        "failed_cameras"
    ] == [1]
    # The error is that of the cameras whose fit holds.
    assert state(hass, "sensor", "calibration_error") == "1.33"
    assert attributes(hass, "sensor", "calibration_error")["worst_camera"] == 2
    suggested = issue(hass, entry)
    assert suggested is not None and suggested.is_fixable
    assert suggested.translation_key == "calibration_missing"
    assert suggested.translation_placeholders is None

    # The next calibration holds.
    coordinator = entry.runtime_data.local
    answer(aioclient_mock, "/api/system", json=system_2_1())
    await reread(hass, coordinator)
    assert state(hass, "binary_sensor", "calibration_problem") == "off"
    assert state(hass, "sensor", "calibration_error") == "2.31"
    assert issue(hass, entry) is None


async def test_a_board_that_says_it_is_not_calibrated_has_a_problem(
    hass, aioclient_mock
):
    entry = await setup_v2(
        hass,
        aioclient_mock,
        recording="2.1.0",
        state=running_2_1(),
        system=system_2_1(calibrated=False),
    )
    assert state(hass, "binary_sensor", "calibration_problem") == "on"
    assert issue(hass, entry).translation_key == "calibration_missing"


async def test_a_camera_without_a_calibration_is_a_problem(hass, aioclient_mock):
    system = system_2_1()
    system["calibration"]["cams"][2]["calibrated"] = False
    await setup_v2(
        hass, aioclient_mock, recording="2.1.0", state=running_2_1(), system=system
    )
    assert state(hass, "binary_sensor", "calibration_problem") == "on"
    assert attributes(hass, "binary_sensor", "calibration_problem")[
        "failed_cameras"
    ] == [3]
    assert state(hass, "sensor", "calibration_error") == "2.31"


async def test_board_manager_2_0_that_is_not_calibrated_has_a_problem(
    hass, aioclient_mock
):
    system = {**recorded("2.0.2", "system.json"), "calibrated": False}
    entry = await setup_v2(
        hass, aioclient_mock, recording="2.0.2", state=board(), system=system
    )
    assert state(hass, "binary_sensor", "calibration_problem") == "on"
    assert issue(hass, entry).translation_key == "calibration_missing"


@pytest.mark.parametrize(
    ("system", "status"),
    [
        # Board Manager 2.1 counts the cameras it calibrates.
        (system_2_1(calibrated=False, calibratingCams=2), "throw"),
        # Its status says so on either version.
        (system_2_1(calibrated=False), "calibrating"),
    ],
)
async def test_a_running_calibration_is_no_problem_yet(
    hass, aioclient_mock, system, status
):
    entry = await setup_v2(
        hass,
        aioclient_mock,
        recording="2.1.0",
        state={**running_2_1(), "status": status},
        system=system,
    )
    assert state(hass, "binary_sensor", "calibration_problem") == "off"
    assert issue(hass, entry) is None


async def test_a_running_calibration_keeps_the_last_result_until_it_is_done(
    hass, aioclient_mock
):
    entry = await setup_v2(
        hass,
        aioclient_mock,
        recording="2.1.0",
        state=running_2_1(),
        system=failed_fit(2),
    )
    coordinator = entry.runtime_data.local
    assert state(hass, "binary_sensor", "calibration_problem") == "on"
    # The board calibrates its cameras: no all-clear in between.
    calibrating_now = failed_fit(2)
    calibrating_now["status"]["calibratingCams"] = 3
    answer(aioclient_mock, "/api/system", json=calibrating_now)
    await reread(hass, coordinator)
    assert state(hass, "binary_sensor", "calibration_problem") == "on"
    assert issue(hass, entry).translation_key == "calibration_missing"
    # The fit fails again: the problem simply stays.
    answer(aioclient_mock, "/api/system", json=failed_fit(2))
    await reread(hass, coordinator)
    assert state(hass, "binary_sensor", "calibration_problem") == "on"
    # Another calibration, and this one holds.
    answer(aioclient_mock, "/api/system", json=calibrating_now)
    await reread(hass, coordinator)
    assert state(hass, "binary_sensor", "calibration_problem") == "on"
    answer(aioclient_mock, "/api/system", json=system_2_1())
    await reread(hass, coordinator)
    assert state(hass, "binary_sensor", "calibration_problem") == "off"
    assert issue(hass, entry) is None


async def test_a_board_that_says_nothing_of_its_calibration_shows_no_problem(
    hass, aioclient_mock
):
    system = system_2_1()
    del system["status"]["calibrated"], system["calibration"]
    entry = await setup_v2(
        hass, aioclient_mock, recording="2.1.0", state=running_2_1(), system=system
    )
    assert state(hass, "binary_sensor", "calibration_problem") == "unavailable"
    assert issue(hass, entry) is None


async def test_the_repair_calibrates_and_comes_back_if_it_did_not_help(
    hass, aioclient_mock, hass_client
):
    entry = await setup_v2(
        hass,
        aioclient_mock,
        recording="2.1.0",
        state=running_2_1(),
        system=failed_fit(2),
    )
    issue_id = f"calibration_{entry.entry_id}"
    aioclient_mock.post(f"{BASE}/api/config/calibration/auto", json={})
    flow = await fix(hass, hass_client, issue_id, confirm=False)
    assert flow["step_id"] == "confirm" and flow["description_placeholders"] is None
    result = await fix(hass, hass_client, issue_id)
    assert result["type"] == "create_entry"
    assert any(
        call[0] == "POST" and call[1].path == "/api/config/calibration/auto"
        for call in aioclient_mock.mock_calls
    )
    assert issue(hass, entry) is None
    # The fit of the camera fails again.
    await reread(hass, entry.runtime_data.local)
    assert issue(hass, entry).translation_key == "calibration_missing"


async def test_the_board_and_the_correction_rate_share_one_repair(hass, aioclient_mock):
    entry = await setup_v2(hass, aioclient_mock, recording="2.0.0", state=board())
    coordinator = entry.runtime_data.local
    calibrated = recorded("2.0.0", "system.json")
    uncalibrated = {**calibrated, "calibrated": False}

    async def board_says(system: dict) -> None:
        answer(aioclient_mock, "/api/system", json=system)
        await reread(hass, coordinator)

    # Every second dart corrected suggests a calibration for the rate.
    darts(coordinator.games.quality, QUALITY_MINIMUM, corrected_every=2)
    coordinator.async_receive("state", board())
    assert issue(hass, entry).translation_key == "calibration_recommended"
    # What the board says comes first, and while it lasts, darts keep it.
    await board_says(uncalibrated)
    assert issue(hass, entry).translation_key == "calibration_missing"
    assert issue(hass, entry).translation_placeholders is None
    coordinator.async_receive("state", board())
    assert issue(hass, entry).translation_key == "calibration_missing"
    # Calibrated again, the rate is still high.
    await board_says(calibrated)
    assert issue(hass, entry).translation_key == "calibration_recommended"
    assert issue(hass, entry).translation_placeholders == {"rate": "50"}

    # A rate between the two limits keeps a suggestion for the rate.
    coordinator.games.quality.reset()
    darts(coordinator.games.quality, QUALITY_MINIMUM, corrected_every=7)
    coordinator.async_receive("state", board())
    assert issue(hass, entry).translation_key == "calibration_recommended"
    # But not one of the board, once the board is calibrated again.
    await board_says(uncalibrated)
    assert issue(hass, entry).translation_key == "calibration_missing"
    await board_says(calibrated)
    assert issue(hass, entry) is None
    coordinator.async_receive("state", board())
    assert issue(hass, entry) is None


async def test_board_manager_1_and_a_dartboard_without_autodarts_report_none(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    registry = er.async_get(hass)
    for platform, key in (
        ("binary_sensor", "calibration_problem"),
        ("sensor", "calibration_error"),
    ):
        assert registry.async_get_entity_id(platform, DOMAIN, f"board-1_{key}") is None
    manual = await setup_manual(hass)
    for registered in er.async_entries_for_config_entry(registry, manual.entry_id):
        assert "calibration_problem" not in registered.unique_id
        assert "calibration_error" not in registered.unique_id
    assert issue(hass, entry) is None


async def test_the_diagnostics_show_the_calibration_without_its_matrices(
    hass, aioclient_mock
):
    entry = await setup_v2(hass, aioclient_mock, recording="2.1.0", state=running_2_1())
    report = await async_get_config_entry_diagnostics(hass, entry)
    system = report["local"]["system"]
    assert (system["calibrated"], system["blocker"]) == (True, "none")
    assert system["calibration"] == RECORDED_FITS
    for matrix in ("homography", '"k"', '"d"'):
        assert matrix not in json.dumps(report)
