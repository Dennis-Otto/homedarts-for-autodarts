"""Backups of the stores of a board, and how a board gets them back.

Deleting a board deletes its stores, so a backup of them is written first, and
homedarts.backup writes one on request. A backup is one JSON file with the three
stores of the board as Home Assistant keeps them, each with its version: the
training with the games, the personal bests, the player profiles, their progress
and badges and the tournament; the weekly report; and the training calendar.
Backups go to homedarts/backups/<board ID> in the media folder, which needs a
login, like the exports; the newest five of every board stay.

homedarts.restore brings a backup back. Replace writes its stores as they are,
and the board migrates a store of an older version as it loads it. Merge adds
the players of a backup of another board to those of this board, a name in any
upper and lower case being the same player: their numbers, matches, weekly
sums, badges and the sessions and matches of the calendar, with the personal
bests that beat those of this board. What belongs to this board alone stays,
such as the game in progress and its settings, and a backup merged once is not
merged again. The players of a board merge once per source board: a backup of
this board, a second backup of a board merged before, and a backup that holds
what this board holds already are refused, because their darts would count
twice. A backup of a newer version than this release knows is refused. Before
a restore writes, what the board holds is backed up, so a restore can be undone.

A board added again, with nothing stored yet and the board ID of a backup,
offers the newest backup that holds player data with a repair.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.core_config import Config
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    UnsupportedStorageVersionError,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import CONF_BOARD_ID, DOMAIN
from .export import ExportFolderError, allowed_path, media_folder, offer_download
from .journal import TrainingJournal
from .profiles import Profiles
from .progress import Progress
from .records import PersonalRecords
from .report import REPORT_STORES, report_store
from .runtime import AutodartsConfigEntry
from .storage import TrainingStore
from .training import HISTORY_SIZE

_LOGGER = logging.getLogger(__name__)

BACKUP_FORMAT: Final = "homedarts.backup"
# Raised with each change of the layout of a backup, not of the stores in it.
BACKUP_VERSION: Final = 1
# Inside the media folder, which Home Assistant serves only with a login.
BACKUP_FOLDER: Final = Path("homedarts", "backups")
KEPT_BACKUPS: Final = 5
# A backup is read at once; a larger file is none of this integration.
MAX_BACKUP_BYTES: Final = 64 * 2**20
RESTORE_MODES: Final = ("replace", "merge")
STORES: Final = ("training", *REPORT_STORES)
# In the training store: the backups merged into the board.
MERGED: Final = "merged_backups"
# In the training store: the board IDs of the boards merged into the board.
MERGED_BOARDS: Final = "merged_boards"
ISSUE: Final = "backup_available"


class BackupFileError(Exception):
    """The file is no backup this release restores; the translation key says why."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _stores(hass: HomeAssistant, entry: ConfigEntry) -> list[Store[dict[str, Any]]]:
    """The stores of a board as Home Assistant keeps them on disk."""
    return [
        TrainingStore(hass, entry.entry_id),
        *(report_store(hass, entry.entry_id, name) for name in REPORT_STORES),
    ]


def _board_folder(config: Config, entry: ConfigEntry) -> Path:
    """The folder of the backups of a board, by its board ID, which stays the same
    when the board is deleted and added again."""
    board = str(entry.data.get(CONF_BOARD_ID) or entry.entry_id)
    return media_folder(config, BACKUP_FOLDER / slugify(board, separator="-"))


def _board_name(entry: ConfigEntry) -> str:
    return str(entry.data.get(CONF_NAME) or entry.title)


async def async_collect(
    hass: HomeAssistant, entry: AutodartsConfigEntry
) -> dict[str, Any]:
    """Everything the board stores, as a backup holds it.

    A loaded board hands over its own stores, which return what they have not
    written yet, too.
    """
    stores = _stores(hass, entry)
    if entry.state is ConfigEntryState.LOADED:
        local = entry.runtime_data.local
        stores = [local.store.training, *local.reports.stores]
    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "id": uuid.uuid4().hex,
        "created": dt_util.now().isoformat(),
        "board_id": entry.data.get(CONF_BOARD_ID),
        "board": _board_name(entry),
        "stores": {
            name: {
                "version": store.version,
                "minor_version": store.minor_version,
                "data": await store.async_load(),
            }
            for name, store in zip(STORES, stores, strict=True)
        },
    }


def has_data(backup: dict[str, Any]) -> bool:
    """Whether a backup holds player data: profiles, progress, finished
    sessions, personal bests, or sessions and matches of the calendar."""
    stores = _part(backup, "stores")

    def data(name: str) -> dict[str, Any]:
        store = stores.get(name)
        return _part(store, "data") if isinstance(store, dict) else {}

    training, journal = data("training"), data("journal")
    return any(
        (
            _list(_part(_part(training, "practice"), "profiles"), "players"),
            _list(_part(training, "progress"), "players"),
            _list(training, "history"),
            _part(_part(training, "records"), "bests"),
            _list(journal, "sessions"),
            _list(journal, "matches"),
        )
    )


def _write(folder: Path, name: str, backup: dict[str, Any]) -> Path:
    """Write the backup and remove the oldest beyond the newest five of the
    board; runs in the executor."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    if path.exists():
        # A second backup in the same second.
        path = folder / f"{name}-{backup['id'][:6]}.json"
    with path.open("x", encoding="utf-8") as file:
        json.dump(backup, file, ensure_ascii=False)
    # The new backup stays whatever the clock of the file system says.
    older = sorted(
        (found for found in folder.glob("*.json") if found != path),
        key=lambda found: (found.stat().st_mtime_ns, found.name),
    )
    for old in older[: max(len(older) - KEPT_BACKUPS + 1, 0)]:
        old.unlink()
    return path


async def async_backup(
    hass: HomeAssistant, entry: AutodartsConfigEntry, *, removed: bool = False
) -> dict[str, Any] | None:
    """Write a backup of the board and describe it for the service response.

    For a board being deleted or restored into, nothing is written while it
    holds no player data, so that an empty board added again and deleted again
    neither becomes the newest backup nor pushes an older one out.
    """
    try:
        backup = await async_collect(hass, entry)
        if removed and not has_data(backup):
            return None
        now = dt_util.now()
        name = f"{slugify(_board_name(entry), separator='-')}-{now:%Y%m%d-%H%M%S}"
        path = await hass.async_add_executor_job(
            _write, _board_folder(hass.config, entry), name, backup
        )
    except (HomeAssistantError, OSError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="backup_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    _LOGGER.info("Wrote a backup of %s to %s", entry.title, path)
    return {
        "path": str(path),
        "download": offer_download(hass, path),
        "id": backup["id"],
        "created": backup["created"],
    }


# -- reading a backup ------------------------------------------------------------


def backup_file(config: Config, file: str) -> Path:
    """The backup file, resolved, so that neither .. nor a symbolic link leads
    elsewhere; runs in the executor.

    A file is relative to the configuration folder, or absolute. It must be a
    JSON file outside hidden folders where Home Assistant allows reading: www,
    the media folders and the folders of allowlist_external_dirs.
    """
    try:
        target = allowed_path(config, file)
    except ExportFolderError as err:
        raise BackupFileError("backup_file") from err
    if (
        target.suffix.casefold() != ".json"
        or not config.is_allowed_path(str(target))
        or not target.is_file()
    ):
        raise BackupFileError("backup_file")
    return target


def read_backup(config: Config, file: str, versions: dict[str, int]) -> dict[str, Any]:
    """The backup in the file, checked against the versions of the stores this
    release reads; runs in the executor."""
    path = backup_file(config, file)
    if path.stat().st_size > MAX_BACKUP_BYTES:
        raise BackupFileError("backup_invalid")
    try:
        backup = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as err:
        raise BackupFileError("backup_invalid") from err
    if (
        not isinstance(backup, dict)
        or backup.get("format") != BACKUP_FORMAT
        or type(backup.get("version")) is not int
        or backup["version"] < 1
        or not isinstance(backup.get("id"), str)
        or not isinstance(backup.get("stores"), dict)
    ):
        raise BackupFileError("backup_invalid")
    if backup["version"] > BACKUP_VERSION:
        raise BackupFileError("backup_newer")
    for name, version in versions.items():
        store = backup["stores"].get(name)
        if (
            not isinstance(store, dict)
            or type(store.get("version")) is not int
            or type(store.get("minor_version")) is not int
            or not isinstance(store.get("data"), dict | None)
        ):
            raise BackupFileError("backup_invalid")
        # Home Assistant migrates a store of an older version as it loads it.
        if store["version"] > version:
            raise BackupFileError("backup_newer")
    return backup


# -- merging ---------------------------------------------------------------------


def _part(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    return value if isinstance(value, list) else []


def _ids(data: dict[str, Any]) -> list[str]:
    """The backups merged into a board."""
    return [item for item in _list(data, MERGED) if isinstance(item, str)]


def _history(ours: dict[str, Any], theirs: dict[str, Any]) -> list[Any]:
    """The finished training sessions of both boards, newest first."""
    sessions = [
        summary
        for data in (ours, theirs)
        for summary in _list(data, "history")
        if isinstance(summary, dict)
    ]
    unique = {json.dumps(summary, sort_keys=True): summary for summary in sessions}
    return sorted(
        unique.values(), key=lambda summary: str(summary.get("ended")), reverse=True
    )[:HISTORY_SIZE]


def _merge_training(
    ours: dict[str, Any], theirs: dict[str, Any], now: datetime
) -> dict[str, Any]:
    """This board's training store with the players, the bests and the finished
    sessions of another board's."""
    profiles, their_profiles = Profiles(), Profiles()
    profiles.restore(_part(ours, "practice").get("profiles"))
    their_profiles.restore(_part(theirs, "practice").get("profiles"))
    # Progress without stored progress starts from what its profiles prove.
    progress, their_progress = Progress(), Progress()
    progress.restore(ours.get("progress"), profiles, now)
    their_progress.restore(theirs.get("progress"), their_profiles, now)
    records, their_records = PersonalRecords(), PersonalRecords()
    records.restore(ours.get("records"))
    their_records.restore(theirs.get("records"))
    profiles.merge(their_profiles)
    progress.merge(their_progress, profiles, now)
    records.merge(their_records)
    return {
        **ours,
        "history": _history(ours, theirs),
        "practice": {**_part(ours, "practice"), "profiles": profiles.stored()},
        "records": records.stored(),
        "progress": progress.stored(),
    }


def _boards(data: dict[str, Any]) -> list[str]:
    """The board IDs of the boards merged into a board."""
    return [item for item in _list(data, MERGED_BOARDS) if isinstance(item, str)]


def merge_stores(
    current: dict[str, Any],
    backup: dict[str, Any],
    now: datetime,
    board_id: str | None = None,
) -> dict[str, Any] | None:
    """The stores of the board with the backup merged in; None when the board
    has it merged already.

    A backup whose darts the board holds already, in part, is refused with
    BackupFileError: one of this board, of a board merged before, or one that
    brings along a board or a backup merged into this board.
    """
    ours = current["training"] or {}
    merged = _ids(ours)
    if backup["id"] in merged:
        return None
    source = {name: store["data"] for name, store in backup["stores"].items()}
    theirs = source["training"] or {}
    source_board = backup.get("board_id")
    ours_boards = _boards(ours)
    theirs_boards = [
        *_boards(theirs),
        *([source_board] if isinstance(source_board, str) else []),
    ]
    if (
        (board_id is not None and board_id in theirs_boards)
        or set(theirs_boards) & set(ours_boards)
        or set(_ids(theirs)) & set(merged)
    ):
        raise BackupFileError("backup_merged_board")
    training = _merge_training(ours, theirs, now)
    # A backup of a board that has others merged in brings them along.
    training[MERGED] = [*merged, *_ids(theirs), backup["id"]]
    training[MERGED_BOARDS] = [*ours_boards, *dict.fromkeys(theirs_boards)]
    journal, their_journal = TrainingJournal(), TrainingJournal()
    journal.restore(current["journal"])
    their_journal.restore(source["journal"])
    journal.merge(their_journal)
    return {
        "training": training,
        # The weekly report counts the running week of this board.
        "report": current["report"]
        if current["report"] is not None
        else source["report"],
        "journal": journal.stored(),
    }


# -- restoring -------------------------------------------------------------------


async def _async_write_stores(
    hass: HomeAssistant, entry: AutodartsConfigEntry, backup: dict[str, Any], mode: str
) -> tuple[bool, dict[str, Any] | None]:
    """Write the stores of the backup, or merge it in, after a backup of what
    the board holds: whether that changed the board, False for a backup merged
    before, and the backup written first, if any."""
    stores = _stores(hass, entry)
    written = backup["stores"]
    if mode == "merge":
        current = {
            name: await store.async_load()
            for name, store in zip(STORES, stores, strict=True)
        }
        merged = merge_stores(
            current, backup, dt_util.now(), entry.data.get(CONF_BOARD_ID)
        )
        if merged is None:
            return False, None
        written = {
            name: {
                "version": store.version,
                "minor_version": store.minor_version,
                "data": merged[name],
            }
            for name, store in zip(STORES, stores, strict=True)
        }
    # What the board holds now, so that the restore can be undone.
    try:
        previous = await async_backup(hass, entry, removed=True)
    except HomeAssistantError as err:
        # A store of a newer version, which this release cannot read: the
        # restore is what brings such a board back.
        if not isinstance(err.__cause__, UnsupportedStorageVersionError):
            raise
        _LOGGER.warning(
            "The stores of %s come from a newer version and are replaced "
            "without a backup: %s",
            entry.title,
            err.__cause__,
        )
        previous = None
    for name, store in zip(STORES, stores, strict=True):
        saved = written[name]
        # Saved with the version it has, so that the board migrates it.
        target: Store[dict[str, Any]] = Store(
            hass,
            saved["version"],
            store.key,
            private=True,
            minor_version=saved["minor_version"],
        )
        if saved["data"] is None:
            await target.async_remove()
        else:
            await target.async_save(saved["data"])
    return True, previous


def _shown(file: str) -> str:
    """The file for a message: control characters as ?."""
    return "".join(char if char.isprintable() else "?" for char in file)


async def async_restore(
    hass: HomeAssistant, entry: AutodartsConfigEntry, file: str, mode: str
) -> dict[str, Any]:
    """Restore a backup into the board, which unloads for it and loads again.

    What the board held before is backed up first; the response names that
    backup as previous, or None when the board held no player data.
    """
    versions = {
        name: store.version
        for name, store in zip(STORES, _stores(hass, entry), strict=True)
    }
    try:
        backup = await hass.async_add_executor_job(
            read_backup, hass.config, file, versions
        )
    except BackupFileError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=err.key,
            translation_placeholders={"file": _shown(file)},
        ) from err
    except OSError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="backup_file",
            translation_placeholders={"file": _shown(file)},
        ) from err
    # The board writes what it has not saved yet as it unloads.
    if not await hass.config_entries.async_unload(entry.entry_id):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="restore_failed",
            translation_placeholders={"error": "the board does not unload"},
        )
    try:
        changed, previous = await _async_write_stores(hass, entry, backup, mode)
    except BackupFileError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=err.key,
            translation_placeholders={"file": _shown(file)},
        ) from err
    except (HomeAssistantError, OSError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="restore_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    finally:
        await hass.config_entries.async_reload(entry.entry_id)
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE}_{entry.entry_id}")
    _LOGGER.info("Restored the backup %s into %s (%s)", backup["id"], entry.title, mode)
    return {
        "mode": mode,
        "changed": changed,
        "previous": previous["path"] if previous else None,
        "id": backup["id"],
        "created": backup.get("created"),
        "board": backup.get("board"),
    }


# -- the offer of a board added again ----------------------------------------------


def _holds_data(path: Path) -> bool:
    """Whether the file is a backup with player data; runs in the executor."""
    try:
        if path.stat().st_size > MAX_BACKUP_BYTES:
            return False
        backup = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    return isinstance(backup, dict) and has_data(backup)


def _newest(folder: Path) -> tuple[Path, float] | None:
    """The newest backup in the folder that holds player data and when it was
    written; runs in the executor."""
    found = [(path.stat().st_mtime, path) for path in folder.glob("*.json")]
    for modified, path in sorted(found, reverse=True):
        if _holds_data(path):
            return path, modified
    return None


async def async_offer_backup(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """A board with nothing stored yet: offer the newest backup of its board ID.

    The repair stays until the backup is restored, the board is deleted or the
    user ignores it.
    """
    newest = await hass.async_add_executor_job(
        _newest, _board_folder(hass.config, entry)
    )
    if newest is None:
        return
    path, modified = newest
    when = dt_util.as_local(dt_util.utc_from_timestamp(modified))
    placeholders = {"board": entry.title, "date": f"{when:%Y-%m-%d %H:%M}"}
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE}_{entry.entry_id}",
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE,
        translation_placeholders=placeholders,
        data={"entry_id": entry.entry_id, "file": str(path), **placeholders},
    )
