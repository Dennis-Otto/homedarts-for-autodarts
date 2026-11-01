"""Weekly report, training calendar and export in Home Assistant."""

import csv
import io
import json
import zipfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.core_config import Config
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.homedarts.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.homedarts.export import (
    FORMULA_START,
    ExportFolderError,
    csv_text,
    default_folder,
    export_folder,
)

from .local_helpers import (
    S20,
    T20,
    board,
    entity_id,
    local_entry_data,
    mock_board,
    record,
    setup_local,
    state,
)
from .test_practice_setup import throw

S1 = ("S1", 1, 1)
D10 = ("D10", 10, 2)
D20 = ("D20", 20, 2)


def attributes(hass, platform: str, key: str) -> dict:
    return dict(hass.states.get(entity_id(hass, platform, key)).attributes)


def stored(hass_storage, entry, name: str) -> dict:
    return hass_storage[f"homedarts.{entry.entry_id}.{name}"]["data"]


async def exported(hass, result) -> str:
    """The text of a file that the export wrote, without its byte order mark."""
    return await hass.async_add_executor_job(
        Path(result["path"]).read_text, "utf-8-sig"
    )


async def press(hass, key: str) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id(hass, "button", key)}, blocking=True
    )
    await hass.async_block_till_done()


async def pass_time(hass, freezer, moment: str) -> None:
    freezer.move_to(moment)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.fixture
async def berlin(hass):
    await hass.config.async_set_time_zone("Europe/Berlin")


# -- weekly report ---------------------------------------------------------------


async def test_the_weekly_report_counts_the_week_and_announces_it(
    hass, aioclient_mock, freezer, hass_storage, berlin
):
    # A Thursday evening; the report week starts on Monday at midnight.
    freezer.move_to("2026-10-01 18:00:00+02:00")
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    report = hass.states.get(entity_id(hass, "sensor", "weekly_report"))
    assert report.state == "0"
    assert report.attributes["week_start"] == "2026-09-27T22:00:00+00:00"
    assert report.attributes["week_end"] == "2026-10-04T22:00:00+00:00"
    assert report.attributes["last_week"] is None

    await throw(hass, coordinator, T20)
    freezer.tick(timedelta(seconds=40))
    # The second visit beats the first as the highest visit.
    await throw(hass, coordinator, T20, T20, T20)
    report = attributes(hass, "sensor", "weekly_report")
    assert state(hass, "sensor", "weekly_report") == "4"
    assert {
        key: report[key]
        for key in (
            "visits",
            "average",
            "highest_visit",
            "scores_180",
            "training_minutes",
            "streak",
        )
    } == {
        "visits": 2,
        "average": 180.0,
        "highest_visit": 180,
        "scores_180": 1,
        "training_minutes": 1,
        "streak": 1,
    }
    assert report["personal_bests"] == [
        {"record": "highest_visit", "value": 180, "name": None}
    ]

    await pass_time(hass, freezer, "2026-10-04 23:59:59+02:00")
    assert not [kind for kind, _ in events if kind == "weekly_report"]
    await pass_time(hass, freezer, "2026-10-05 00:00:00+02:00")
    reports = [details for kind, details in events if kind == "weekly_report"]
    assert len(reports) == 1
    assert reports[0]["darts"] == 4 and reports[0]["source"] == "schedule"
    assert reports[0]["week_end"] == "2026-10-04T22:00:00+00:00"
    event = attributes(hass, "event", "board_events")
    assert event["event_type"] == "weekly_report" and event["visits"] == 2
    assert state(hass, "sensor", "weekly_report") == "0"
    report = attributes(hass, "sensor", "weekly_report")
    assert report["week_start"] == "2026-10-04T22:00:00+00:00"
    assert report["last_week"]["darts"] == 4

    # The report and the new week survive a restart.
    await throw(hass, coordinator, S20)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert stored(hass_storage, entry, "report")["counts"]["darts"] == 1
    assert state(hass, "sensor", "weekly_report") == "1"
    report = attributes(hass, "sensor", "weekly_report")
    assert report["last_week"]["average"] == 180.0
    assert report["average_change"] == -120.0


async def test_a_report_due_while_home_assistant_was_stopped_follows_at_start(
    hass, aioclient_mock, freezer, hass_storage
):
    freezer.move_to("2026-10-07 09:00:00+00:00")
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    hass_storage[f"homedarts.{entry.entry_id}.report"] = {
        "version": 1,
        "key": f"homedarts.{entry.entry_id}.report",
        "data": {
            "weekday": 0,
            "time": "00:00",
            "started": "2026-09-21T07:00:00+00:00",
            "ends": "2026-09-28T07:00:00+00:00",
            "counts": {"darts": 120, "visits": 40, "visit_darts": 120, "points": 2000},
        },
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    # The frozen clock runs the report that is due now only when told to.
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    event = attributes(hass, "event", "board_events")
    assert event["event_type"] == "weekly_report"
    assert (event["darts"], event["average"]) == (120, 50.0)
    assert event["week_end"] == "2026-09-28T07:00:00+00:00"
    # The new week is the current one, in the test time zone (US/Pacific).
    report = attributes(hass, "sensor", "weekly_report")
    assert report["week_start"] == "2026-10-05T07:00:00+00:00"
    assert state(hass, "sensor", "weekly_report") == "0"


async def test_day_and_time_of_the_report_are_settings(
    hass, aioclient_mock, freezer, hass_storage, berlin
):
    freezer.move_to("2026-10-01 18:00:00+02:00")
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    registry = er.async_get(hass)
    for platform, key in (
        ("select", "weekly_report_day"),
        ("time", "weekly_report_time"),
    ):
        registered = registry.async_get(entity_id(hass, platform, key))
        assert registered.entity_category == er.EntityCategory.CONFIG
    assert state(hass, "select", "weekly_report_day") == "monday"
    assert state(hass, "time", "weekly_report_time") == "00:00:00"

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": entity_id(hass, "select", "weekly_report_day"),
            "option": "sunday",
        },
        blocking=True,
    )
    await hass.services.async_call(
        "time",
        "set_value",
        {
            "entity_id": entity_id(hass, "time", "weekly_report_time"),
            "time": "20:00:00",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert state(hass, "select", "weekly_report_day") == "sunday"
    assert state(hass, "time", "weekly_report_time") == "20:00:00"
    report = attributes(hass, "sensor", "weekly_report")
    # The running week keeps its start and ends at the next Sunday evening.
    assert report["week_start"] == "2026-09-27T22:00:00+00:00"
    assert report["week_end"] == "2026-10-04T18:00:00+00:00"
    assert stored(hass_storage, entry, "report")["weekday"] == 6
    assert stored(hass_storage, entry, "report")["time"] == "20:00"

    events = record(hass, coordinator)
    # A timer that fires early changes nothing.
    await coordinator.reports._async_report(dt_util.utcnow())
    assert not events
    await pass_time(hass, freezer, "2026-10-04 20:00:00+02:00")
    assert [kind for kind, _ in events] == ["weekly_report"]
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["reports"] == {
        "weekday": 6,
        "time": "20:00",
        "journal_sessions": 0,
        "journal_matches": 0,
    }


async def test_x01_legs_bring_the_checkout_rate_of_the_week(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await coordinator.async_start_game(101)
    # 101 - 61 leaves 40: the next two darts are thrown at a double.
    await throw(hass, coordinator, T20, S1)
    await throw(hass, coordinator, S20, D10)
    report = attributes(hass, "sensor", "weekly_report")
    assert (report["darts_at_double"], report["checkouts"]) == (2, 1)
    assert (report["checkout_rate"], report["legs"]) == (50.0, 1)


# -- training calendar -------------------------------------------------------------


async def calendar_events(hass, start: str, end: str) -> list[dict]:
    calendar = entity_id(hass, "calendar", "training_calendar")
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": calendar, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    return response[calendar]["events"]


async def play_a_match(hass, freezer, coordinator, names=("Alex", "Sam")) -> None:
    """Alex beats Sam in one leg of 101 within two minutes."""
    await coordinator.async_start_game(101, names=list(names), legs=1, sets=1)
    await throw(hass, coordinator, T20, S1)
    freezer.tick(timedelta(minutes=1))
    await throw(hass, coordinator, S1)
    freezer.tick(timedelta(minutes=1))
    await throw(hass, coordinator, D20)


async def test_the_calendar_lists_sessions_and_matches(
    hass, aioclient_mock, freezer, hass_storage
):
    freezer.move_to("2026-09-27 18:00:00+00:00")
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    calendar = hass.states.get(entity_id(hass, "calendar", "training_calendar"))
    assert calendar.state == "off"
    assert "message" not in calendar.attributes

    await throw(hass, coordinator, T20, T20, S20)
    freezer.tick(timedelta(minutes=10))
    await press(hass, "reset_training")
    freezer.tick(timedelta(minutes=5))
    await play_a_match(hass, freezer, coordinator)
    events = await calendar_events(
        hass, "2026-09-27T17:00:00+00:00", "2026-09-27T19:00:00+00:00"
    )
    assert events == [
        {
            "start": "2026-09-27T11:00:00-07:00",
            "end": "2026-09-27T11:10:00-07:00",
            "summary": "Training · 3 Darts · Ø 140.0",
            "description": "180: 0 · 140+: 1 · 100+: 0 · Max: 140",
        },
        {
            "start": "2026-09-27T11:15:00-07:00",
            "end": "2026-09-27T11:17:00-07:00",
            "summary": "101 · Alex 1:0 Sam",
            "description": "Alex: Ø 101.0\nSam: Ø 3.0",
        },
    ]
    calendar = attributes(hass, "calendar", "training_calendar")
    assert calendar["message"] == "101 · Alex 1:0 Sam"
    assert (
        await calendar_events(
            hass, "2026-09-26T00:00:00+00:00", "2026-09-27T00:00:00+00:00"
        )
        == []
    )

    # The journal keeps both after a restart.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    journal = stored(hass_storage, entry, "journal")
    assert (len(journal["sessions"]), len(journal["matches"])) == (1, 1)
    assert (
        len(
            await calendar_events(
                hass, "2026-09-27T17:00:00+00:00", "2026-09-27T19:00:00+00:00"
            )
        )
        == 2
    )
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["reports"]["journal_matches"] == 1
    assert "Alex" not in str(diagnostics["reports"])


async def test_the_journal_takes_over_the_stored_history_once(
    hass, aioclient_mock, hass_storage
):
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(domain="homedarts", version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    now = dt_util.utcnow()

    def ago(days: int) -> str:
        return (now - timedelta(days=days)).isoformat()

    hass_storage[f"homedarts.{entry.entry_id}.training"] = {
        "version": 1,
        "key": f"homedarts.{entry.entry_id}.training",
        "data": {
            "active": False,
            "history": [
                {"started": ago(2), "ended": ago(1), "darts": 90, "points": 1500},
                {"started": ago(400), "ended": ago(399), "darts": 30, "points": 500},
            ],
            "practice": {
                "profiles": {
                    "matches": [
                        {
                            "ended": ago(3),
                            "game": "cricket",
                            "legs_to_win": 1,
                            "sets_to_win": 1,
                            "winner": 2,
                            "players": [
                                {"name": "Lea", "legs": 0, "sets": 0, "mpr": 1.5},
                                {"name": "Kim", "legs": 0, "sets": 1, "mpr": 2.1},
                            ],
                        }
                    ]
                }
            },
        },
    }
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = await calendar_events(hass, ago(500), now.isoformat())
    assert [event["summary"] for event in events] == [
        "Cricket · Lea 0:1 Kim",
        "Training · 90 Darts · Ø 50.0",
    ]
    assert await hass.config_entries.async_unload(entry.entry_id)
    journal = stored(hass_storage, entry, "journal")
    # The session older than a year is not taken over.
    assert len(journal["sessions"]) == 1
    assert await hass.config_entries.async_remove(entry.entry_id)
    for name in ("training", "report", "journal"):
        assert f"homedarts.{entry.entry_id}.{name}" not in hass_storage


# -- export ------------------------------------------------------------------------------


async def export(hass, **data) -> dict:
    return await hass.services.async_call(
        "homedarts", "export", data, blocking=True, return_response=True
    )


def folders(hass, config: Path, media: Path | None = None) -> Path:
    """The configuration folder, with www and a media folder allowed for writing
    as Home Assistant sets them up; returns the default export folder."""
    media = media or config / "media"
    hass.config.config_dir = str(config)
    hass.config.media_dirs = {"local": str(media)}
    hass.config.allowlist_external_dirs = {str(config / "www"), str(media)}
    return media / "homedarts" / "exports"


@pytest.fixture
async def played(hass, aioclient_mock, freezer, tmp_path):
    """A board with a finished session and a match, and a configuration folder."""
    freezer.move_to("2026-09-27 18:00:00+00:00")
    folders(hass, tmp_path)
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await throw(hass, coordinator, T20, T20, S20)
    await press(hass, "reset_training")
    await play_a_match(hass, freezer, coordinator, names=("=Alex", "Sam"))
    return tmp_path


async def test_export_everything_as_json(hass, played):
    result = await export(hass, format="json")
    path = Path(result["path"])
    # The media folder needs a login.
    assert path.parent == played / "media" / "homedarts" / "exports"
    assert path.name.startswith("homedarts-all-20260927-")
    assert result["url"] is None
    assert result["download"] == f"/api/homedarts/export/{path.name}"
    assert result["rows"] == {"sessions": 1, "matches": 1, "profiles": 2}
    content = json.loads(await hass.async_add_executor_job(path.read_text, "utf-8"))
    assert content["exported"].startswith("2026-09-27T11:")
    session = content["sessions"][0]
    assert (session["darts"], session["average"]) == (3, 140.0)
    assert session["duration_minutes"] == 0.0
    match = content["matches"][0]
    assert (match["game"], match["winner"], match["winner_name"]) == (101, 1, "=Alex")
    assert [player["legs"] for player in match["players"]] == [1, 0]
    assert match["started"] == "2026-09-27T18:00:00+00:00"
    assert {profile["name"] for profile in content["profiles"]} == {"=Alex", "Sam"}
    # In www, which Home Assistant serves without a login, only on request.
    result = await export(hass, format="json", folder="www/homedarts")
    path = Path(result["path"])
    assert path.parent == played / "www" / "homedarts"
    assert result["url"] == f"/local/homedarts/{path.name}"


async def test_export_tables_as_csv(hass, played):
    result = await export(hass, what="sessions")
    path = Path(result["path"])
    assert path.suffix == ".csv"
    raw = await hass.async_add_executor_job(path.read_bytes)
    # The byte order mark lets spreadsheet programs detect UTF-8.
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    assert rows[0]["darts"] == "3" and rows[0]["average"] == "140.0"

    result = await export(hass, what="profiles", format="csv")
    rows = list(csv.DictReader(io.StringIO(await exported(hass, result))))
    # A name that looks like a formula stays text in a spreadsheet.
    assert sorted(row["name"] for row in rows) == ["'=Alex", "Sam"]
    assert "fewest_darts_101" in rows[0]
    assert "doubles" not in rows[0]

    result = await export(hass)
    path = Path(result["path"])
    assert path.suffix == ".zip"
    with zipfile.ZipFile(path) as archive:
        assert sorted(archive.namelist()) == [
            "matches.csv",
            "profiles.csv",
            "sessions.csv",
        ]
        matches = archive.read("matches.csv").decode("utf-8-sig").splitlines()
    assert matches[0].startswith("started,ended,game,legs_to_win,sets_to_win,winner")
    assert ",'=Alex," in matches[1]


@pytest.mark.parametrize("start", FORMULA_START)
def test_a_cell_that_starts_like_a_formula_stays_text(start):
    """Every character a spreadsheet starts a formula with, in every column."""
    rows = [
        {"name": f"{start}Alex", "legs": 1, "average": -1.5},
        {"name": f"Sam{start}", "legs": 0, "average": None},
    ]
    written = list(csv.DictReader(io.StringIO(csv_text("profiles", rows))))
    assert [row["name"] for row in written] == [f"'{start}Alex", f"Sam{start}"]
    # Numbers stay numbers, also below zero.
    assert [row["average"] for row in written] == ["-1.5", ""]


async def test_an_empty_export_still_has_its_columns(hass, aioclient_mock, tmp_path):
    default = folders(hass, tmp_path)
    await setup_local(hass, aioclient_mock, state=board())
    # Without Home Assistant's web server, there is just no download.
    with patch.object(hass, "http", None):
        result = await export(hass, what="profiles")
    assert result["url"] is None
    assert await exported(hass, result) == "name\n"
    result = await export(hass, what="matches")
    header = (await exported(hass, result)).splitlines()
    # Columns are only ever added after the others, for tables that read them.
    assert header[0].split(",") == [
        "started",
        "ended",
        "game",
        "legs_to_win",
        "sets_to_win",
        "winner",
        "winner_name",
        *(
            f"player_{number}_{key}"
            for number in range(1, 9)
            for key in (
                "name",
                "legs",
                "sets",
                "match_legs",
                "average",
                "mpr",
                "points",
            )
        ),
    ]
    # The action also runs without asking for its response.
    await hass.services.async_call(
        "homedarts", "export", {"what": "sessions"}, blocking=True
    )
    assert len(list(default.iterdir())) == 3


async def test_a_party_of_eight_reaches_the_calendar_and_the_export(
    hass, aioclient_mock, freezer, tmp_path
):
    freezer.move_to("2026-09-27 18:00:00+00:00")
    folders(hass, tmp_path)
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    names = ["Alex", "Sam", "Kim", "Lea", "Mia", "Leo", "Zoe", "Ben"]
    await coordinator.async_start_game("count_up", names=names, rounds=1)
    await throw(hass, coordinator, T20)
    for _ in names[1:]:
        await throw(hass, coordinator, S1)
    assert coordinator.games.practice.winner == 0
    (event,) = [
        event
        for event in await calendar_events(
            hass, "2026-09-27T17:00:00+00:00", "2026-09-27T19:00:00+00:00"
        )
        if event["summary"].startswith("Count-Up")
    ]
    assert event["summary"] == (
        "Count-Up · Alex 1 · Sam 0 · Kim 0 · Lea 0 · Mia 0 · Leo 0 · Zoe 0 · Ben 0"
    )
    assert event["description"].splitlines()[-1] == "Ben: 1"
    result = await export(hass, what="matches")
    (row,) = csv.DictReader(io.StringIO(await exported(hass, result)))
    assert [row[f"player_{number}_name"] for number in range(1, 9)] == names
    assert (row["player_8_points"], row["winner_name"]) == ("1", "Alex")
    result = await export(hass, what="matches", format="json")
    (match,) = json.loads(await exported(hass, result))["matches"]
    assert [player["name"] for player in match["players"]] == names


@pytest.mark.parametrize(
    ("folder", "shown"),
    [
        ("../outside", "../outside"),
        (".storage", ".storage"),
        ("www/.hidden", "www/.hidden"),
        ("/etc", "/etc"),
        # Only where Home Assistant allows writing.
        ("exports", "exports"),
        ("custom_components/homedarts", "custom_components/homedarts"),
        # Control characters never reach the file system or the message.
        ("www/a\x00b", "www/a?b"),
        ("www/tab\there", "www/tab?here"),
    ],
)
async def test_export_writes_only_where_home_assistant_allows_it(
    hass, aioclient_mock, tmp_path, folder, shown
):
    folders(hass, tmp_path / "config")
    await setup_local(hass, aioclient_mock, state=board())
    with pytest.raises(ServiceValidationError) as error:
        await export(hass, folder=folder)
    assert error.value.translation_key == "export_folder"
    assert error.value.translation_placeholders == {"folder": shown}
    assert not (tmp_path / "outside").exists()
    assert not (tmp_path / "config" / "exports").exists()
    assert not (tmp_path / "config" / "custom_components").exists()


async def test_export_to_an_allowed_folder_of_your_own(hass, aioclient_mock, tmp_path):
    """A folder of allowlist_external_dirs, given by its path; never a hidden one."""
    folders(hass, tmp_path / ".homeassistant")
    share = tmp_path / "share"
    hass.config.allowlist_external_dirs.add(str(share))
    await setup_local(hass, aioclient_mock, state=board())
    result = await export(hass, what="sessions", folder=str(share / "darts"))
    assert Path(result["path"]).parent == share / "darts"
    # A hidden configuration folder, as in a Home Assistant Core install, is fine.
    result = await export(hass, what="sessions")
    assert Path(result["path"]).parent == (
        tmp_path / ".homeassistant" / "media" / "homedarts" / "exports"
    )
    with pytest.raises(ServiceValidationError) as error:
        await export(hass, folder=str(share / ".secret"))
    assert error.value.translation_key == "export_folder"
    # A link cannot lead from an allowed folder to one that is not.
    try:
        (share / "link").symlink_to(tmp_path / ".homeassistant")
    except OSError:
        return  # Creating links needs rights Windows does not always grant.
    with pytest.raises(ServiceValidationError):
        await export(hass, folder=str(share / "link" / "exports"))
    assert not (tmp_path / ".homeassistant" / "exports").exists()


async def test_the_default_folder_must_be_allowed_too(hass, aioclient_mock, tmp_path):
    folders(hass, tmp_path)
    hass.config.allowlist_external_dirs = set()
    await setup_local(hass, aioclient_mock, state=board())
    with pytest.raises(ServiceValidationError) as error:
        await export(hass, what="sessions")
    assert error.value.translation_placeholders == {"folder": "homedarts/exports"}
    assert not (tmp_path / "media").exists()


def test_a_folder_that_cannot_be_resolved_is_refused(tmp_path):
    config = Config.__new__(Config)
    config.config_dir = str(tmp_path)
    with (
        patch.object(Path, "resolve", side_effect=RuntimeError("Symlink loop")),
        pytest.raises(ExportFolderError),
    ):
        export_folder(config, "www/loop")


def test_the_default_folder_without_a_local_media_folder(tmp_path):
    config = Config.__new__(Config)
    config.config_dir = str(tmp_path)
    config.media_dirs = {"recordings": str(tmp_path / "recordings")}
    assert default_folder(config) == tmp_path / "recordings" / "homedarts" / "exports"
    config.media_dirs = {}
    assert default_folder(config) == tmp_path / "media" / "homedarts" / "exports"


async def test_exports_are_limited_per_hour(hass, aioclient_mock, tmp_path):
    """A looping automation cannot fill the disk."""
    folders(hass, tmp_path)
    await setup_local(hass, aioclient_mock, state=board())
    with (
        patch("custom_components.homedarts.export.EXPORT_LIMIT", 2),
        patch("custom_components.homedarts.export.monotonic", return_value=1000.0),
    ):
        await export(hass, what="sessions")
        # A refused folder writes nothing and does not count.
        with pytest.raises(ServiceValidationError):
            await export(hass, what="sessions", folder="exports")
        await export(hass, what="sessions")
        with pytest.raises(ServiceValidationError) as error:
            await export(hass, what="sessions")
    assert error.value.translation_key == "export_limit"
    assert error.value.translation_placeholders == {"count": "2"}
    # An hour later, the next export is written.
    with (
        patch("custom_components.homedarts.export.EXPORT_LIMIT", 2),
        patch("custom_components.homedarts.export.monotonic", return_value=4600.0),
    ):
        await export(hass, what="sessions")


async def test_export_never_follows_a_link_out_of_the_configuration_folder(
    hass, aioclient_mock, tmp_path
):
    config = tmp_path / "config"
    config.mkdir()
    (tmp_path / "outside").mkdir()
    try:
        (config / "link").symlink_to(tmp_path / "outside", target_is_directory=True)
    except OSError:
        pytest.skip("Creating links needs rights Windows does not always grant.")
    hass.config.config_dir = str(config)
    await setup_local(hass, aioclient_mock, state=board())
    for folder in ("link", "link/exports"):
        with pytest.raises(ServiceValidationError) as error:
            await export(hass, folder=folder)
        assert error.value.translation_key == "export_folder"
    assert list((tmp_path / "outside").iterdir()) == []


async def test_export_reports_a_folder_it_cannot_create(hass, aioclient_mock, tmp_path):
    folders(hass, tmp_path)
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "taken").write_text("a file, not a folder")
    await setup_local(hass, aioclient_mock, state=board())
    with pytest.raises(HomeAssistantError) as error:
        await export(hass, folder="www/taken")
    assert error.value.translation_key == "export_failed"


async def test_administrators_download_the_exports_of_this_run(
    hass,
    aioclient_mock,
    tmp_path,
    hass_client,
    hass_client_no_auth,
    hass_read_only_access_token,
):
    folders(hass, tmp_path)
    assert await async_setup_component(hass, "http", {})
    await setup_local(hass, aioclient_mock, state=board())
    result = await export(hass, what="sessions")
    name = Path(result["path"]).name
    assert (result["url"], result["download"]) == (
        None,
        f"/api/homedarts/export/{name}",
    )
    client = await hass_client()
    response = await client.get(result["download"])
    assert response.status == 200
    assert response.headers["Content-Disposition"] == f'attachment; filename="{name}"'
    assert (await response.read()).startswith(b"\xef\xbb\xbfstarted,")
    anonymous = await hass_client_no_auth()
    assert (await anonymous.get(result["download"])).status == 401
    # A user who is no administrator gets no player data either.
    user = await hass_client(access_token=hass_read_only_access_token)
    assert (await user.get(result["download"])).status == 401
    assert (await client.get("/api/homedarts/export/other.csv")).status == 404
    await hass.async_add_executor_job(Path(result["path"]).unlink)
    assert (await client.get(result["download"])).status == 404
    # Only the latest exports stay available for download.
    with patch("custom_components.homedarts.export.KEPT_DOWNLOADS", 1):
        first = await export(hass, what="profiles")
        second = await export(hass, what="matches")
    assert (await client.get(first["download"])).status == 404
    assert (await client.get(second["download"])).status == 200
