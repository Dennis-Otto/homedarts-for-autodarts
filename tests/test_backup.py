"""Backups of a board: written when it is deleted and on request, restored into a
board added again, and merged into another board."""

import json
import os
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context
from homeassistant.core_config import Config
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homedarts import backup
from custom_components.homedarts.backup import (
    BACKUP_VERSION,
    KEPT_BACKUPS,
    MERGED,
    MERGED_BOARDS,
    STORES,
    BackupFileError,
    merge_stores,
    read_backup,
)
from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.journal import TrainingJournal
from custom_components.homedarts.profiles import Profile, Profiles
from custom_components.homedarts.progress import (
    WEEK,
    WEEK_FIELDS,
    PlayerProgress,
    Progress,
)
from custom_components.homedarts.records import PersonalRecords
from custom_components.homedarts.repairs import async_create_fix_flow
from custom_components.homedarts.storage import STORAGE_MINOR_VERSION

from .local_helpers import NOW, board, local_entry_data, mock_board, setup_local
from .test_practice_setup import throw
from .test_start_game_and_quality import fix

D20 = ("D20", 20, 2)


@pytest.fixture
def media(hass, tmp_path) -> Path:
    """The media folder, where Home Assistant allows reading and writing."""
    hass.config.config_dir = str(tmp_path)
    folder = tmp_path / "media"
    hass.config.media_dirs = {"local": str(folder)}
    hass.config.allowlist_external_dirs = {str(folder)}
    return folder


def backups(media: Path, board_id: str = "board-1") -> list[Path]:
    return sorted((media / "homedarts" / "backups" / board_id).glob("*.json"))


def stored(hass_storage, entry_id: str) -> dict:
    """The three stores of a board as Home Assistant keeps them."""
    return {
        name: deepcopy(hass_storage.get(f"{DOMAIN}.{entry_id}.{name}"))
        for name in STORES
    }


def contents(stores: dict) -> dict:
    """What a store holds, without its key, which names the entry."""
    return {
        name: {key: value for key, value in store.items() if key != "key"}
        for name, store in stores.items()
        if store is not None
    }


async def call(hass, service: str, context: Context | None = None, **data) -> dict:
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, context=context, return_response=True
    )


async def play(hass, entry, *names: str) -> None:
    """A leg of 501 the first player wins with a checkout of 40."""
    coordinator = entry.runtime_data.local
    await coordinator.async_start_game(501, names=list(names), legs=1)
    coordinator.games.practice.players[0].remaining = 40
    await throw(hass, coordinator, D20)


async def add_board(hass, aioclient_mock, board_id="board-1", host="192.0.2.10"):
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, data=local_entry_data(board_id, host)
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def offer(hass, entry) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(
        DOMAIN, f"backup_available_{entry.entry_id}"
    )


# -- deleting and adding a board again --------------------------------------------


async def test_a_deleted_board_comes_back_as_it_was_from_its_backup(
    hass, aioclient_mock, hass_storage, hass_client, media
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await play(hass, entry, "Alex", "Sam")
    assert await hass.config_entries.async_unload(entry.entry_id)
    before = stored(hass_storage, entry.entry_id)
    assert all(before.values())

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert not any(stored(hass_storage, entry.entry_id).values())
    (file,) = backups(media)
    saved = json.loads(file.read_text(encoding="utf-8"))
    assert (saved["format"], saved["version"]) == ("homedarts.backup", 1)
    assert saved["board_id"] == "board-1" and saved["board"] == entry.title
    assert file.name.startswith("mock-title-")
    assert saved["stores"] == {
        name: {
            "version": store["version"],
            "minor_version": store["minor_version"],
            "data": store["data"],
        }
        for name, store in before.items()
    }

    # The board is added again: with nothing stored, its backup is offered.
    again = await add_board(hass, aioclient_mock)
    issue = offer(hass, again)
    assert issue is not None and issue.is_persistent and issue.is_fixable
    assert issue.translation_placeholders["board"] == again.title
    # In the time zone of Home Assistant, not in that of the machine.
    assert issue.translation_placeholders["date"][:4] == str(dt_util.now().year)

    result = await fix(hass, hass_client, issue.issue_id)
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert offer(hass, again) is None
    assert again.state is ConfigEntryState.LOADED
    profiles = again.runtime_data.local.games.practice.profiles
    assert profiles.players["alex"].legs_won == 1
    # The board writes back what it restored, byte for byte.
    assert await hass.config_entries.async_unload(again.entry_id)
    after = stored(hass_storage, again.entry_id)
    assert contents(after) == contents(before)
    assert json.dumps(contents(after)) == json.dumps(contents(before))


async def test_a_board_with_nothing_stored_leaves_no_backup(
    hass, aioclient_mock, hass_storage, media
):
    # Without an address, the board never sets up and never stores anything.
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={"board_id": "board-1"})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert not (media / "homedarts").exists()
    # A board added for the first time has no backup to offer.
    added = await add_board(hass, aioclient_mock)
    assert offer(hass, added) is None


async def test_a_board_whose_backup_fails_keeps_its_stores(
    hass, aioclient_mock, hass_storage, media, caplog
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await play(hass, entry, "Alex")
    assert await hass.config_entries.async_unload(entry.entry_id)
    before = stored(hass_storage, entry.entry_id)
    with patch.object(backup, "_write", side_effect=OSError("disk full")):
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
    assert stored(hass_storage, entry.entry_id) == before
    assert "stays in the .storage folder" in caplog.text
    assert "disk full" in caplog.text


async def test_deleting_the_board_removes_the_offer(
    hass, aioclient_mock, hass_storage, media
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await play(hass, entry, "Alex")
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert backups(media)
    again = await add_board(hass, aioclient_mock)
    assert offer(hass, again) is not None
    await hass.config_entries.async_remove(again.entry_id)
    await hass.async_block_till_done()
    assert offer(hass, again) is None


# -- homedarts.backup ---------------------------------------------------------------


async def test_the_backup_action_writes_what_the_board_has_not_saved_yet(
    hass, aioclient_mock, hass_storage, media
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await play(hass, entry, "Alex")
    response = await call(hass, "backup")
    path = Path(response["path"])
    assert path.parent == media / "homedarts" / "backups" / "board-1"
    assert response["download"] == f"/api/homedarts/export/{path.name}"
    saved = json.loads(await hass.async_add_executor_job(path.read_text, "utf-8"))
    assert (saved["id"], saved["created"]) == (response["id"], response["created"])
    # The leg is not saved yet, but it is in the backup.
    training = saved["stores"]["training"]
    assert (training["version"], training["minor_version"]) == (
        1,
        STORAGE_MINOR_VERSION,
    )
    players = training["data"]["practice"]["profiles"]["players"]
    assert [(player["name"], player["legs_won"]) for player in players] == [("Alex", 1)]


async def test_the_newest_five_backups_of_a_board_stay(
    hass, aioclient_mock, freezer, media
):
    freezer.move_to(NOW)
    await setup_local(hass, aioclient_mock, state=board())
    written = []
    for second in range(KEPT_BACKUPS + 2):
        path = Path((await call(hass, "backup"))["path"])
        # Written in the same second: the second name has a part of the ID.
        os.utime(path, (1_000_000 + second, 1_000_000 + second))
        written.append(path)
    assert written[1].name == f"{written[0].stem}-{written[1].stem[-6:]}.json"
    assert backups(media) == sorted(written[-KEPT_BACKUPS:])


async def test_a_backup_that_cannot_be_written_is_explained(
    hass, aioclient_mock, media
):
    await setup_local(hass, aioclient_mock, state=board())
    (media / "homedarts").mkdir(parents=True)
    (media / "homedarts" / "backups").write_text("a file, not a folder")
    with pytest.raises(HomeAssistantError) as error:
        await call(hass, "backup")
    assert error.value.translation_key == "backup_failed"


async def test_a_board_that_does_not_start_can_be_backed_up(
    hass, aioclient_mock, hass_storage, media
):
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={"board_id": "board-1"})
    entry.add_to_hass(hass)
    hass_storage[f"{DOMAIN}.{entry.entry_id}.journal"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.{entry.entry_id}.journal",
        "data": {"sessions": [], "matches": []},
    }
    assert not await hass.config_entries.async_setup(entry.entry_id)
    response = await call(hass, "backup", config_entry_id=entry.entry_id)
    saved = json.loads(
        await hass.async_add_executor_job(Path(response["path"]).read_text, "utf-8")
    )
    assert saved["stores"]["journal"]["data"] == {"sessions": [], "matches": []}
    assert saved["stores"]["training"]["data"] is None


@pytest.mark.parametrize("service", ["backup", "restore"])
async def test_backups_are_for_administrators(
    hass, aioclient_mock, media, hass_read_only_user, service
):
    await setup_local(hass, aioclient_mock, state=board())
    with pytest.raises(Unauthorized):
        await call(
            hass,
            service,
            Context(user_id=hass_read_only_user.id),
            **({"file": "media/backup.json"} if service == "restore" else {}),
        )
    assert not (media / "homedarts").exists()


async def test_the_board_of_a_backup_or_a_restore(
    hass, aioclient_mock, two_boards, media
):
    with pytest.raises(ServiceValidationError) as error:
        await call(hass, "backup")
    assert error.value.translation_key == "several_boards"
    for unknown in ("no-such-entry", MockConfigEntry(domain="sun").entry_id):
        with pytest.raises(ServiceValidationError) as error:
            await call(hass, "backup", config_entry_id=unknown)
        assert error.value.translation_key == "unknown_board"
    other = MockConfigEntry(domain="sun")
    other.add_to_hass(hass)
    with pytest.raises(ServiceValidationError) as error:
        await call(hass, "restore", config_entry_id=other.entry_id, file="x.json")
    assert error.value.translation_key == "unknown_board"
    _first, second = two_boards
    response = await call(hass, "backup", config_entry_id=second.entry_id)
    assert Path(response["path"]).parent.name == "board-2"
    for entry in two_boards:
        await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as error:
        await call(hass, "backup")
    assert error.value.translation_key == "no_board"


# -- homedarts.restore --------------------------------------------------------------


def write(media: Path, content: object, name: str = "backup.json") -> str:
    path = media / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        content if isinstance(content, str) else json.dumps(content), encoding="utf-8"
    )
    return str(path)


VERSIONS = {"training": 1, "report": 1, "journal": 1}


def config_of(tmp_path: Path) -> Config:
    """The configuration of a Home Assistant whose media folder allows reading."""
    config = Config(None, str(tmp_path))  # type: ignore[arg-type]
    config.media_dirs = {"local": str(tmp_path / "media")}
    config.allowlist_external_dirs = {str(tmp_path / "media")}
    return config


def a_backup(**stores) -> dict:
    return {
        "format": "homedarts.backup",
        "version": BACKUP_VERSION,
        "id": "0123456789abcdef",
        "created": "2026-10-01T22:00:00+02:00",
        "board_id": "board-1",
        "board": "Kitchen",
        "stores": {
            name: {"version": 1, "minor_version": 1, "data": None} for name in STORES
        }
        | stores,
    }


async def test_a_backup_of_an_older_version_is_migrated(
    hass, aioclient_mock, hass_storage, media
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    training = {"version": 1, "minor_version": 1, "data": {"total_darts": 7}}
    response = await call(
        hass, "restore", file=write(media, a_backup(training=training))
    )
    assert response == {
        "mode": "replace",
        "changed": True,
        "previous": None,
        "id": "0123456789abcdef",
        "created": "2026-10-01T22:00:00+02:00",
        "board": "Kitchen",
    }
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.local.games.training.snapshot()["total_darts"] == 7
    saved = hass_storage[f"{DOMAIN}.{entry.entry_id}.training"]
    assert saved["minor_version"] == STORAGE_MINOR_VERSION
    # A store the backup does not have is gone.
    assert f"{DOMAIN}.{entry.entry_id}.journal" not in hass_storage


@pytest.mark.expected_errors
async def test_a_board_that_does_not_start_gets_its_backup(
    hass, aioclient_mock, hass_storage, media
):
    mock_board(aioclient_mock, state=board())
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=local_entry_data())
    entry.add_to_hass(hass)
    # Written by a newer version of the integration.
    hass_storage[f"{DOMAIN}.{entry.entry_id}.training"] = {
        "version": 2,
        "minor_version": 1,
        "key": f"{DOMAIN}.{entry.entry_id}.training",
        "data": {},
    }
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    training = {"version": 1, "minor_version": 3, "data": {"total_darts": 3}}
    await call(hass, "restore", file=write(media, a_backup(training=training)))
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "content",
    [
        "not JSON",
        [],
        {**a_backup(), "format": "other"},
        {**a_backup(), "version": 0},
        {**a_backup(), "version": "1"},
        {**a_backup(), "id": 1},
        {**a_backup(), "stores": []},
        a_backup(report=None),
        a_backup(report={"version": "1", "minor_version": 1, "data": None}),
        a_backup(report={"version": 1, "minor_version": None, "data": None}),
        a_backup(report={"version": 1, "minor_version": 1, "data": []}),
    ],
)
def test_what_is_no_backup_is_refused(tmp_path, content):
    config = config_of(tmp_path)
    with pytest.raises(BackupFileError) as error:
        read_backup(config, write(tmp_path / "media", content), VERSIONS)
    assert error.value.key == "backup_invalid"


def test_a_file_that_is_not_utf8_or_too_large_is_refused(tmp_path):
    config = config_of(tmp_path)
    path = tmp_path / "media" / "latin.json"
    path.parent.mkdir()
    path.write_bytes(b'{"board": "K\xfcche"}')
    with pytest.raises(BackupFileError) as error:
        read_backup(config, str(path), VERSIONS)
    assert error.value.key == "backup_invalid"
    file = write(tmp_path / "media", a_backup())
    with (
        patch.object(backup, "MAX_BACKUP_BYTES", 10),
        pytest.raises(BackupFileError) as error,
    ):
        read_backup(config, file, VERSIONS)
    assert error.value.key == "backup_invalid"


@pytest.mark.parametrize(
    "content",
    [
        {**a_backup(), "version": BACKUP_VERSION + 1},
        a_backup(training={"version": 2, "minor_version": 1, "data": {}}),
    ],
)
async def test_a_backup_of_a_newer_version_is_refused(
    hass, aioclient_mock, hass_storage, media, content
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    with pytest.raises(ServiceValidationError) as error:
        await call(hass, "restore", file=write(media, content))
    assert error.value.translation_key == "backup_newer"
    assert error.value.translation_placeholders["file"].endswith("backup.json")
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "file",
    [
        # Out of the folders where Home Assistant allows reading, also by ..
        ".storage/homedarts.board.training",
        "media/../.storage/homedarts.board.training",
        "configuration.json",
        "/etc/passwd",
        # Hidden, no JSON, missing, a folder, control characters.
        "media/.hidden/backup.json",
        "media/backup.txt",
        "media/missing.json",
        "media/folder.json",
        "media/back\nup.json",
    ],
)
async def test_only_backups_in_allowed_folders_are_read(
    hass, aioclient_mock, hass_storage, media, tmp_path, file
):
    await setup_local(hass, aioclient_mock, state=board())
    for name in (
        ".storage/homedarts.board.training",
        "configuration.json",
        "media/.hidden/backup.json",
        "media/backup.txt",
    ):
        write(tmp_path, a_backup(), name)
    (media / "folder.json").mkdir()
    with pytest.raises(ServiceValidationError) as error:
        await call(hass, "restore", file=file)
    assert error.value.translation_key == "backup_file"
    assert "\n" not in error.value.translation_placeholders["file"]


async def test_a_backup_that_cannot_be_read_is_explained(hass, aioclient_mock, media):
    await setup_local(hass, aioclient_mock, state=board())
    file = write(media, a_backup())
    with (
        patch.object(Path, "read_text", side_effect=PermissionError("denied")),
        pytest.raises(ServiceValidationError) as error,
    ):
        await call(hass, "restore", file=file)
    assert error.value.translation_key == "backup_file"


async def test_a_board_that_does_not_unload_keeps_its_data(hass, aioclient_mock, media):
    await setup_local(hass, aioclient_mock, state=board())
    file = write(media, a_backup())
    with (
        patch.object(hass.config_entries, "async_unload", return_value=False) as unload,
        pytest.raises(HomeAssistantError) as error,
    ):
        await call(hass, "restore", file=file)
    assert unload.called
    assert error.value.translation_key == "restore_failed"


@pytest.mark.expected_errors
async def test_a_merge_into_a_board_of_a_newer_version_fails_and_the_board_stays(
    hass, aioclient_mock, hass_storage, media
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    file = write(media, a_backup())
    key = f"{DOMAIN}.{entry.entry_id}.training"
    newer = {"version": 2, "minor_version": 1, "key": key, "data": {}}

    async def unload(entry_id, **kwargs):
        # The board saves as it unloads, then a newer version writes its store.
        result = await original(entry_id, **kwargs)
        hass_storage[key] = newer
        return result

    original = hass.config_entries.async_unload
    with (
        patch.object(hass.config_entries, "async_unload", side_effect=unload),
        pytest.raises(HomeAssistantError) as error,
    ):
        await call(hass, "restore", file=file, mode="merge")
    assert error.value.translation_key == "restore_failed"
    assert hass_storage[key] == newer


# -- the repair -----------------------------------------------------------------------


async def start_repair(hass, data: dict) -> dict:
    flow = await async_create_fix_flow(hass, "backup_available_entry", data)
    flow.hass = hass
    flow.issue_id = "backup_available_entry"
    result = await flow.async_step_init()
    assert result["step_id"] == "confirm"
    return await flow.async_step_confirm({})


async def test_the_repair_of_a_board_that_is_gone_or_a_backup_that_is_gone(
    hass, aioclient_mock, media
):
    result = await start_repair(hass, {"entry_id": "gone", "file": "x.json"})
    assert result["reason"] == "board_unavailable"
    entry = await setup_local(hass, aioclient_mock, state=board())
    result = await start_repair(
        hass, {"entry_id": entry.entry_id, "file": str(media / "gone.json")}
    )
    assert result["reason"] == "restore_failed"


# -- merging two boards ------------------------------------------------------------------


async def test_a_player_of_two_boards_gets_the_darts_of_both(
    hass, aioclient_mock, hass_storage, two_boards, media
):
    first, second = two_boards
    await play(hass, first, "Alex", "Sam")
    await play(hass, second, "alex", "Kim")
    file = (await call(hass, "backup", config_entry_id=second.entry_id))["path"]

    response = await call(
        hass, "restore", config_entry_id=first.entry_id, file=file, mode="merge"
    )
    assert response["changed"] is True
    await hass.async_block_till_done()
    games = first.runtime_data.local.games
    alex = games.practice.profiles.players["alex"]
    assert (alex.name, alex.legs_played, alex.legs_won) == ("Alex", 2, 2)
    assert (alex.matches_won, alex.checkouts, alex.highest_checkout) == (2, 2, 40)
    assert alex.doubles["D20"] == [2, 2]
    assert set(games.practice.profiles.players) == {"alex", "sam", "kim"}
    assert len(games.practice.profiles.matches) == 2
    assert games.progress.players["alex"].counters["darts"] == 2
    assert games.progress.players["alex"].badges["legs_won"]
    journal = first.runtime_data.local.reports.journal
    assert len(journal.matches) == 2
    assert await hass.config_entries.async_unload(first.entry_id)
    merged = stored(hass_storage, first.entry_id)
    assert merged["training"]["data"][MERGED] == [
        json.loads(await hass.async_add_executor_job(Path(file).read_text, "utf-8"))[
            "id"
        ]
    ]

    # The same backup again changes nothing.
    assert await hass.config_entries.async_setup(first.entry_id)
    response = await call(
        hass, "restore", config_entry_id=first.entry_id, file=file, mode="merge"
    )
    assert response["changed"] is False
    assert await hass.config_entries.async_unload(first.entry_id)
    assert stored(hass_storage, first.entry_id) == merged


def test_a_merge_into_an_empty_board_takes_the_players_over():
    backup_of = a_backup(
        training={
            "version": 1,
            "minor_version": 3,
            "data": {
                MERGED: ["older", 7],
                "history": [{"started": "a", "ended": "b"}],
                "practice": {"profiles": {"players": [{"name": "Alex"}]}},
            },
        },
        report={"version": 1, "minor_version": 1, "data": {"started": "x"}},
    )
    current = dict.fromkeys(STORES)
    merged = merge_stores(current, backup_of, NOW)
    assert merged is not None
    training = merged["training"]
    assert training[MERGED] == ["older", "0123456789abcdef"]
    assert [player["name"] for player in training["practice"]["profiles"]["players"]]
    assert training["history"] == [{"started": "a", "ended": "b"}]
    # Without a weekly report of its own, the board takes the backup's.
    assert merged["report"] == {"started": "x"}
    # A backup with an empty training store adds nothing.
    assert training[MERGED_BOARDS] == ["board-1"]
    again = merge_stores(
        {**merged, "training": {**training, MERGED: "broken", MERGED_BOARDS: 1}},
        {**a_backup(), "board_id": None},
        NOW,
    )
    assert again is not None and again["report"] == {"started": "x"}
    assert again["training"][MERGED] == ["0123456789abcdef"]
    assert again["training"][MERGED_BOARDS] == []


def test_the_sessions_of_both_boards_newest_first_once():
    ours = {"history": [{"ended": "2"}, {"ended": "1"}, "broken"]}
    theirs = {"history": [{"ended": "3"}, {"ended": "1"}]}
    assert backup._history(ours, theirs) == [
        {"ended": "3"},
        {"ended": "2"},
        {"ended": "1"},
    ]
    assert backup._history({"history": "broken"}, {}) == []


# -- merging the parts -------------------------------------------------------------------


def test_a_profile_takes_the_numbers_of_the_same_player():
    ours = Profile(
        name="Alex",
        legs_played=3,
        highest_visit=100,
        best_mpr=2.5,
        fewest_darts={"501": 15, "301": 12},
        doubles={"D20": [4, 1]},
        last_played="2026-10-02T20:00:00+00:00",
    )
    theirs = Profile(
        name="alex",
        legs_played=2,
        highest_visit=140,
        best_mpr=1.0,
        fewest_darts={"501": 18, "101": 3},
        doubles={"D20": [2, 2], "D16": [1, 0]},
        last_played="2026-10-03T20:00:00+00:00",
    )
    ours.merge(theirs)
    assert (ours.name, ours.legs_played, ours.highest_visit) == ("Alex", 5, 140)
    assert ours.best_mpr == 2.5
    assert ours.fewest_darts == {"501": 15, "301": 12, "101": 3}
    assert ours.doubles == {"D20": [6, 3], "D16": [1, 0]}
    assert ours.last_played == "2026-10-03T20:00:00+00:00"
    nobody = Profile(name="Kim")
    nobody.merge(Profile(name="Kim"))
    assert nobody.last_played is None


def test_profiles_keep_a_person_with_one_player():
    ours, theirs = Profiles(), Profiles()
    ours.restore(
        {
            "players": [
                {"name": "Alex", "person": "person.alex"},
                {"name": "Sam"},
            ],
            "matches": [{"ended": "2", "players": []}],
            "head_to_head": {"alex\x00sam": [1, 2]},
        }
    )
    theirs.restore(
        {
            "players": [
                {"name": "Kim", "person": "person.alex"},
                {"name": "sam", "person": "person.sam"},
                {"name": "Lea", "person": "person.lea"},
            ],
            "matches": [
                {"ended": "3", "players": []},
                {"ended": "2", "players": []},
            ],
            "head_to_head": {"alex\x00sam": [3, 0], "kim\x00lea": [1, 0]},
        }
    )
    ours.merge(theirs)
    persons = {key: player.person for key, player in ours.players.items()}
    assert persons == {
        "alex": "person.alex",
        "sam": "person.sam",
        "kim": None,
        "lea": "person.lea",
    }
    assert [match["ended"] for match in ours.matches] == ["3", "2"]
    assert ours.head_to_head == {"alex\x00sam": [4, 2], "kim\x00lea": [1, 0]}


def week(**sums) -> list[int]:
    row = [0] * len(WEEK_FIELDS)
    for name, value in sums.items():
        row[WEEK[name]] = value
    return row


def test_progress_adds_the_weeks_and_keeps_the_bests():
    ours = PlayerProgress("Alex")
    ours.weeks = {
        "2026-09-28": week(darts=30, highest_checkout=40, best_501=18, best_mpr=0)
    }
    ours.counters |= {"darts": 30, "around_the_clock": 30, "bobs_27": 200}
    ours.hits.update({"T20": 2})
    ours.log.add((0.1, 0.1), None)
    ours.streak, ours.best_streak, ours.last_day = 2, 4, date(2026, 10, 1)
    ours.badges = {"maximum": ["2026-09-01"], "ton_plus": ["2026-09-05"]}
    theirs = PlayerProgress("alex")
    theirs.weeks = {
        "2026-09-28": week(darts=12, highest_checkout=100, best_501=21, best_mpr=250),
        "2026-07-06": week(darts=3, best_501=15),
    }
    theirs.counters |= {"darts": 12, "around_the_clock": 0, "bobs_27": 300}
    theirs.hits.update({"T20": 1, "S1": 1})
    theirs.log.add((-0.1, 0.1), "T20")
    theirs.streak, theirs.best_streak, theirs.last_day = 5, 5, date(2026, 10, 3)
    theirs.badges = {
        "maximum": ["2026-08-01", "2026-08-02"],
        "ton_plus": ["2026-09-09"],
    }
    ours.merge(theirs)
    assert ours.weeks["2026-09-28"] == week(
        darts=42, highest_checkout=100, best_501=18, best_mpr=250
    )
    assert ours.weeks["2026-07-06"] == week(darts=3, best_501=15)
    assert (ours.counters["darts"], ours.counters["around_the_clock"]) == (42, 30)
    assert ours.counters["bobs_27"] == 300
    assert ours.hits == {"T20": 3, "S1": 1}
    # The other board's darts come first, this board's stay the newest.
    assert [dart[2] for dart in ours.log.darts] == ["T20", None]
    assert (ours.streak, ours.best_streak, ours.last_day) == (5, 5, date(2026, 10, 3))
    assert ours.badges == {
        "maximum": ["2026-08-01", "2026-08-02"],
        "ton_plus": ["2026-09-05"],
    }
    # A board whose last day is older, or which has none, leaves the streak.
    for last_day in (date(2026, 9, 1), None):
        older = PlayerProgress("alex")
        older.streak, older.last_day = 1, last_day
        ours.merge(older)
        assert (ours.streak, ours.last_day) == (5, date(2026, 10, 3))


def test_the_weeks_beyond_the_trend_are_dropped():
    ours, theirs = PlayerProgress("Alex"), PlayerProgress("Alex")
    ours.weeks = {f"2026-{month:02}-01": week(darts=1) for month in range(1, 8)}
    theirs.weeks = {f"2025-{month:02}-01": week(darts=1) for month in range(1, 13)}
    ours.merge(theirs)
    assert len(ours.weeks) == 12
    assert min(ours.weeks) == "2025-08-01"


def test_progress_unlocks_what_both_boards_reach_together():
    profiles = Profiles()
    profiles.restore({"players": [{"name": "Alex", "legs_won": 5}]})
    ours, theirs = Progress(), Progress()
    ours.restore({"players": [{"name": "Alex"}]}, profiles, NOW)
    theirs.restore({"players": [{"name": "Kim"}]}, Profiles(), NOW)
    ours.merge(theirs, profiles, NOW)
    assert set(ours.players) == {"alex", "kim"}
    assert ours.players["alex"].badges["legs_won"] == [NOW.isoformat()]
    # Without achievements, nothing unlocks.
    quiet = Progress()
    quiet.restore({"enabled": False, "players": [{"name": "Alex"}]}, profiles, NOW)
    quiet.merge(Progress(), profiles, NOW)
    assert quiet.players["alex"].badges == {}


def test_the_better_personal_bests_of_two_boards():
    ours, theirs = PersonalRecords(), PersonalRecords()
    ours.restore(
        {
            "bests": {
                "highest_visit": {"value": 100, "date": "a", "name": "Alex"},
                "fewest_darts_501": {"value": 18, "date": "a", "name": "Alex"},
                "highest_checkout": {"value": 121, "date": "a", "name": "Alex"},
            },
            "best_streak": 3,
            "streak": 1,
        }
    )
    theirs.restore(
        {
            "bests": {
                "highest_visit": {"value": 140, "date": "b", "name": "Kim"},
                "fewest_darts_501": {"value": 15, "date": "b", "name": "Kim"},
                "highest_checkout": {"value": 40, "date": "b", "name": "Kim"},
                "doubles": {"value": 30, "date": "b", "name": "Kim"},
            },
            "best_streak": 7,
            "streak": 7,
        }
    )
    ours.merge(theirs)
    assert {record: best["value"] for record, best in ours.bests.items()} == {
        "highest_visit": 140,
        "fewest_darts_501": 15,
        "highest_checkout": 121,
        "doubles": 30,
    }
    assert (ours.streak, ours.best_streak) == (1, 7)
    ours.merge(theirs)
    assert ours.bests["fewest_darts_501"]["value"] == 15


def session(ended: str) -> dict:
    return {
        "started": f"2026-10-0{ended}T19:00:00+00:00",
        "ended": f"2026-10-0{ended}T20:00:00+00:00",
        "darts": 3,
        "points": 60,
    }


def test_the_calendar_takes_the_sessions_of_both_boards_in_order():
    ours, theirs = TrainingJournal(), TrainingJournal()
    ours.restore({"sessions": [session("1"), session("3")]})
    theirs.restore({"sessions": [session("2"), session("3")]})
    assert len(theirs.sessions) == 2
    ours.merge(theirs)
    assert [entry["ended"][:10] for entry in ours.sessions] == [
        "2026-10-01",
        "2026-10-02",
        "2026-10-03",
    ]
    with patch("custom_components.homedarts.journal.JOURNAL_SIZE", 2):
        ours.merge(TrainingJournal())
    assert [entry["ended"][:10] for entry in ours.sessions] == [
        "2026-10-02",
        "2026-10-03",
    ]


# -- no dart counts twice, and nothing is lost for good ---------------------------------


async def test_a_board_does_not_merge_its_own_backup(
    hass, aioclient_mock, hass_storage, media
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await play(hass, entry, "Alex")
    file = (await call(hass, "backup"))["path"]
    with pytest.raises(ServiceValidationError) as error:
        await call(hass, "restore", file=file, mode="merge")
    assert error.value.translation_key == "backup_merged_board"
    assert error.value.translation_placeholders["file"] == file
    await hass.async_block_till_done()
    alex = entry.runtime_data.local.games.practice.profiles.players["alex"]
    assert (alex.legs_won, alex.legs_played) == (1, 1)


async def test_a_board_merges_another_board_once(
    hass, aioclient_mock, hass_storage, two_boards, media
):
    first, second = two_boards
    await play(hass, second, "Alex")
    file = (await call(hass, "backup", config_entry_id=second.entry_id))["path"]
    await call(hass, "restore", config_entry_id=first.entry_id, file=file, mode="merge")
    await hass.async_block_till_done()
    await play(hass, second, "Alex")
    newer = (await call(hass, "backup", config_entry_id=second.entry_id))["path"]
    with pytest.raises(ServiceValidationError) as error:
        await call(
            hass, "restore", config_entry_id=first.entry_id, file=newer, mode="merge"
        )
    assert error.value.translation_key == "backup_merged_board"
    await hass.async_block_till_done()
    alex = first.runtime_data.local.games.practice.profiles.players["alex"]
    assert alex.legs_won == 1
    assert await hass.config_entries.async_unload(first.entry_id)
    training = stored(hass_storage, first.entry_id)["training"]["data"]
    assert training[MERGED_BOARDS] == ["board-2"]


def a_board(board_id: str | None, backup_id: str, **training) -> dict:
    return {
        **a_backup(training={"version": 1, "minor_version": 1, "data": training}),
        "board_id": board_id,
        "id": backup_id,
    }


@pytest.mark.parametrize(
    ("ours", "theirs"),
    [
        # A backup of a board that has this board merged in.
        ({}, a_board("c", "y", **{MERGED_BOARDS: ["a"]})),
        # Both boards have the same third board merged in.
        ({MERGED_BOARDS: ["c"]}, a_board("b", "y", **{MERGED_BOARDS: ["c"]})),
        # Both boards have the same backup merged in, from a board without ID.
        ({MERGED: ["x"]}, a_board(None, "y", **{MERGED: ["x"]})),
    ],
)
def test_a_backup_that_brings_along_what_the_board_holds_is_refused(ours, theirs):
    current = dict.fromkeys(STORES) | {"training": ours}
    with pytest.raises(BackupFileError) as error:
        merge_stores(current, theirs, NOW, "a")
    assert error.value.key == "backup_merged_board"


def test_merged_boards_and_backups_come_along():
    current = dict.fromkeys(STORES) | {
        "training": {MERGED: ["x"], MERGED_BOARDS: ["c"]}
    }
    theirs = a_board("b", "y", **{MERGED: ["z"], MERGED_BOARDS: ["d", "d"]})
    merged = merge_stores(current, theirs, NOW, None)
    assert merged is not None
    assert merged["training"][MERGED] == ["x", "z", "y"]
    assert merged["training"][MERGED_BOARDS] == ["c", "d", "b"]


async def test_an_empty_board_deleted_again_keeps_the_backup_with_data(
    hass, aioclient_mock, hass_storage, hass_client, media
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await play(hass, entry, "Alex", "Sam")
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    (first,) = backups(media)
    for _ in range(KEPT_BACKUPS + 1):
        again = await add_board(hass, aioclient_mock)
        # The empty board saves its stores, and is deleted again.
        assert await hass.config_entries.async_unload(again.entry_id)
        assert stored(hass_storage, again.entry_id)["training"] is not None
        await hass.config_entries.async_remove(again.entry_id)
        await hass.async_block_till_done()
    assert backups(media) == [first]
    # A newer backup without player data, and a damaged one, are not offered.
    empty = await add_board(hass, aioclient_mock)
    file = Path((await call(hass, "backup"))["path"])
    broken = write(file.parent, "{", "broken.json")
    huge = write(file.parent, a_board("board-1", "huge", history=[{}]), "huge.json")
    listed = write(file.parent, [], "listed.json")
    for later, path in enumerate((file, Path(broken), Path(huge), Path(listed))):
        os.utime(path, (2e9 + later, 2e9 + later))
    with patch.object(backup, "MAX_BACKUP_BYTES", 100):
        await backup.async_offer_backup(hass, empty)
    issue = offer(hass, empty)
    assert issue is not None and issue.data["file"] == str(first)
    result = await fix(hass, hass_client, issue.issue_id)
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    profiles = empty.runtime_data.local.games.practice.profiles
    assert set(profiles.players) == {"alex", "sam"}


async def test_a_board_with_only_unreadable_backups_offers_none(
    hass, aioclient_mock, media
):
    folder = media / "homedarts" / "backups" / "board-1"
    write(folder, "{", "broken.json")
    entry = await add_board(hass, aioclient_mock)
    assert offer(hass, entry) is None


async def test_a_restore_backs_up_what_the_board_held(
    hass, aioclient_mock, hass_storage, media
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    file = write(media, a_backup())
    # A board without player data writes no backup first.
    response = await call(hass, "restore", file=file)
    assert response["previous"] is None
    assert not backups(media)
    await hass.async_block_till_done()
    await play(hass, entry, "Alex")
    response = await call(hass, "restore", file=file)
    previous = Path(response["previous"])
    assert previous.parent == media / "homedarts" / "backups" / "board-1"
    saved = json.loads(await hass.async_add_executor_job(previous.read_text, "utf-8"))
    names = saved["stores"]["training"]["data"]["practice"]["profiles"]["players"]
    assert [player["name"] for player in names] == ["Alex"]
    # The restore is undone with that backup.
    await hass.async_block_till_done()
    assert not entry.runtime_data.local.games.practice.profiles.players
    await call(hass, "restore", file=str(previous))
    await hass.async_block_till_done()
    assert entry.runtime_data.local.games.practice.profiles.players["alex"].legs_won


@pytest.mark.parametrize(
    "stores",
    [
        "broken",
        {"training": "broken", "journal": {"data": "broken"}},
        {"training": {"data": {"practice": {"profiles": {"players": []}}}}},
    ],
)
def test_a_backup_without_player_data(stores):
    assert not backup.has_data({"stores": stores})


@pytest.mark.parametrize(
    "stores",
    [
        {"training": {"data": {"progress": {"players": [{}]}}}},
        {"training": {"data": {"records": {"bests": {"doubles": {}}}}}},
        {"journal": {"data": {"sessions": [{}]}}},
        {"journal": {"data": {"matches": [{}]}}},
    ],
)
def test_a_backup_with_player_data(stores):
    assert backup.has_data({"stores": stores})


async def test_a_restore_whose_backup_fails_leaves_the_board_as_it_was(
    hass, aioclient_mock, hass_storage, media
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await play(hass, entry, "Alex")
    file = write(media, a_backup())
    with (
        patch.object(backup, "_write", side_effect=OSError("disk full")),
        pytest.raises(HomeAssistantError) as error,
    ):
        await call(hass, "restore", file=file)
    assert error.value.translation_key == "restore_failed"
    await hass.async_block_till_done()
    alex = entry.runtime_data.local.games.practice.profiles.players["alex"]
    assert alex.legs_won == 1
