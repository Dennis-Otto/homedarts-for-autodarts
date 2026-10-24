"""Export training sessions, practice matches and player profiles to a file.

Only administrators, automations and scripts export. Files go where Home
Assistant lets integrations write: by default to homedarts/exports of the media
folder, which needs a login, or on request to www, another media folder or a
folder of allowlist_external_dirs. Every file gets a new, unguessable name,
because www is served at /local/ without a login. Administrators download the
files written since the start through the API.
"""

from __future__ import annotations

import csv
import io
import json
import secrets
import zipfile
from collections import deque
from collections.abc import Callable
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import quote

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.http.decorators import require_admin
from homeassistant.core import HomeAssistant
from homeassistant.core_config import Config
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .games_coordinator import AutodartsGamesCoordinator
from .journal import (
    SESSION_COUNTS,
    TrainingJournal,
    average,
    duration_minutes,
    player_results,
)
from .practice import PARTY_PLAYERS

EXPORT_FORMATS = ("csv", "json")
EXPORT_TABLES = ("sessions", "matches", "profiles")
EXPORT_CONTENTS = (*EXPORT_TABLES, "all")
# Inside the media folder, which Home Assistant serves only with a login.
DEFAULT_FOLDER = Path("homedarts", "exports")
SESSION_COLUMNS = (
    "started",
    "ended",
    "duration_minutes",
    "average",
    *SESSION_COUNTS,
)
MATCH_COLUMNS = (
    "started",
    "ended",
    "game",
    "legs_to_win",
    "sets_to_win",
    "winner",
    "winner_name",
)
# A CSV row has columns for every seat of a match, a party game's eight:
# player_1_name to player_8_points.
PLAYER_COLUMNS = ("name", "legs", "sets", "match_legs", "average", "mpr", "points")
# Spreadsheets run cells that start like a formula; names must stay text.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
DOWNLOAD_URL = "/api/homedarts/export/{name}"
# File name -> path of the exports written since Home Assistant started.
EXPORTS: HassKey[dict[str, Path]] = HassKey(f"{DOMAIN}_exports")
KEPT_DOWNLOADS = 50
# No more exports than this in an hour, so that a looping automation cannot
# fill the disk.
EXPORT_LIMIT = 20
EXPORT_WINDOW = 3600.0
EXPORT_TIMES: HassKey[deque[float]] = HassKey(f"{DOMAIN}_export_times")


class ExportFolderError(ValueError):
    """The folder is hidden, or Home Assistant does not allow writing there."""


def media_folder(config: Config, folder: Path) -> Path:
    """A folder inside the media folder the media browser shows first."""
    media = config.media_dirs
    root = media.get("local") or next(iter(media.values()), config.path("media"))
    return Path(root) / folder


def default_folder(config: Config) -> Path:
    """homedarts/exports of the media folder the media browser shows first."""
    return media_folder(config, DEFAULT_FOLDER)


def allowed_path(config: Config, path: str | Path) -> Path:
    """A path relative to the configuration folder, or absolute, resolved, so
    that neither .. nor a symbolic link leads elsewhere, and in no hidden folder
    of the configuration folder or of allowlist_external_dirs; runs in the
    executor."""
    if isinstance(path, str) and not path.isprintable():
        raise ExportFolderError(path)
    try:
        base = Path(config.config_dir).resolve()
        target = (base / path).resolve()
        roots = [
            base,
            *(Path(folder).resolve() for folder in config.allowlist_external_dirs),
        ]
    except (OSError, RuntimeError, ValueError) as err:
        raise ExportFolderError(str(path)) from err
    for root in roots:
        if target.is_relative_to(root) and any(
            part.startswith(".") for part in target.relative_to(root).parts
        ):
            raise ExportFolderError(str(path))
    return target


def export_folder(config: Config, folder: str | None) -> Path:
    """The export folder, resolved, so that neither .. nor a symbolic link leads
    elsewhere; runs in the executor.

    A folder is relative to the configuration folder, or absolute. It must not
    be hidden and must be one where Home Assistant allows writing: www, the
    media folders and the folders of allowlist_external_dirs.
    """
    target = allowed_path(config, folder or default_folder(config))
    # Home Assistant checks the folder of a file that does not exist yet.
    if not config.is_allowed_path(str(target / "export")):
        raise ExportFolderError(folder)
    return target


class ExportDownloadView(HomeAssistantView):
    """Downloads of this run's exports and backups, for administrators and their
    signed paths."""

    url = DOWNLOAD_URL
    name = "api:homedarts:export"

    @require_admin
    async def get(self, request: web.Request, name: str) -> web.StreamResponse:
        hass = request.app[KEY_HASS]
        path = hass.data.get(EXPORTS, {}).get(name)
        if path is None or not await hass.async_add_executor_job(path.is_file):
            return self.json_message("Export not found", 404)
        return web.FileResponse(
            path, headers={"Content-Disposition": f'attachment; filename="{name}"'}
        )


def offer_download(hass: HomeAssistant, path: Path) -> str:
    """Offer the file for download and return its address."""
    if EXPORTS not in hass.data:
        hass.data[EXPORTS] = {}
        if hass.http is not None:
            hass.http.register_view(ExportDownloadView())
    exports = hass.data[EXPORTS]
    exports[path.name] = path
    for name in list(exports)[:-KEPT_DOWNLOADS]:
        del exports[name]
    return DOWNLOAD_URL.format(name=path.name)


def public_url(config_dir: str, path: Path) -> str | None:
    """The /local/ address of a file in the www folder, which needs no login."""
    www = Path(config_dir).resolve() / "www"
    if not path.is_relative_to(www):
        return None
    return "/local/" + quote(path.relative_to(www).as_posix())


def session_rows(journal: TrainingJournal) -> list[dict[str, Any]]:
    return [
        {
            "started": entry["started"],
            "ended": entry["ended"],
            "duration_minutes": duration_minutes(entry),
            "average": average(entry),
            **{key: entry[key] for key in SESSION_COUNTS},
        }
        for entry in journal.sessions
    ]


def match_rows(journal: TrainingJournal) -> list[dict[str, Any]]:
    rows = []
    for entry in journal.matches:
        players = player_results(entry)
        winner = entry["winner"]
        rows.append(
            {
                **{key: entry[key] for key in MATCH_COLUMNS if key in entry},
                "winner_name": players[winner - 1]["name"] if winner else None,
                "players": players,
            }
        )
    return rows


def profile_rows(coordinator: AutodartsGamesCoordinator) -> list[dict[str, Any]]:
    profiles = coordinator.games.practice.profiles.snapshot()
    players: list[dict[str, Any]] = profiles["players"]
    return players


TABLES: dict[str, Callable[[AutodartsGamesCoordinator], list[dict[str, Any]]]] = {
    "sessions": lambda coordinator: session_rows(coordinator.reports.journal),
    "matches": lambda coordinator: match_rows(coordinator.reports.journal),
    "profiles": profile_rows,
}


def _cell(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(FORMULA_START):
        return "'" + value
    return value


def _flat_match(row: dict[str, Any]) -> dict[str, Any]:
    flat = {key: row[key] for key in MATCH_COLUMNS}
    for index in range(PARTY_PLAYERS):
        player = row["players"][index] if index < len(row["players"]) else {}
        for key in PLAYER_COLUMNS:
            flat[f"player_{index + 1}_{key}"] = player.get(key)
    return flat


def _flat_profile(row: dict[str, Any]) -> dict[str, Any]:
    """Plain values of a profile; the fewest darts get a column per start score."""
    flat = {
        key: value
        for key, value in row.items()
        if value is None or isinstance(value, str | int | float)
    }
    fewest = row.get("fewest_darts")
    for game, darts in sorted(
        (fewest if isinstance(fewest, dict) else {}).items(),
        key=lambda item: int(item[0]),
    ):
        flat[f"fewest_darts_{game}"] = darts
    return flat


def csv_text(table: str, rows: list[dict[str, Any]]) -> str:
    """One table as CSV, with a header row even without rows."""
    if table == "sessions":
        flat, columns = rows, list(SESSION_COLUMNS)
    elif table == "matches":
        flat = [_flat_match(row) for row in rows]
        columns = [
            *MATCH_COLUMNS,
            *(
                f"player_{index + 1}_{key}"
                for index in range(PARTY_PLAYERS)
                for key in PLAYER_COLUMNS
            ),
        ]
    else:
        flat = [_flat_profile(row) for row in rows]
        columns = list(dict.fromkeys(key for row in flat for key in row)) or ["name"]
    output = io.StringIO()
    writer = csv.DictWriter(output, columns, lineterminator="\n")
    writer.writeheader()
    for row in flat:
        writer.writerow({key: _cell(row.get(key)) for key in columns})
    return output.getvalue()


def _write(
    config: Config,
    folder: str | None,
    name: str,
    file_format: str,
    data: dict[str, list[dict[str, Any]]],
    exported: str,
) -> tuple[Path, str | None]:
    """Write the file and find its /local/ address; runs in the executor."""
    target = export_folder(config, folder)
    target.mkdir(parents=True, exist_ok=True)
    if file_format == "json":
        path = target / f"{name}.json"
        content = json.dumps(
            {"exported": exported, **data}, indent=2, ensure_ascii=False
        )
        with path.open("x", encoding="utf-8") as file:
            file.write(content + "\n")
    elif len(data) == 1:
        ((table, rows),) = data.items()
        path = target / f"{name}.csv"
        # With a byte order mark, spreadsheet programs read names with umlauts.
        with path.open("x", encoding="utf-8-sig", newline="") as file:
            file.write(csv_text(table, rows))
    else:
        path = target / f"{name}.zip"
        with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as archive:
            for table, rows in data.items():
                archive.writestr(
                    f"{table}.csv", csv_text(table, rows).encode("utf-8-sig")
                )
    return path, public_url(config.config_dir, path)


def _shown(folder: str | None) -> str:
    """The folder for a message: control characters as ?, the default by name."""
    if not folder:
        return DEFAULT_FOLDER.as_posix()
    return "".join(char if char.isprintable() else "?" for char in folder)


def _recent_exports(hass: HomeAssistant) -> deque[float]:
    """When the exports of the last hour were written; refuses one too many."""
    times = hass.data.setdefault(EXPORT_TIMES, deque())
    now = monotonic()
    while times and now - times[0] >= EXPORT_WINDOW:
        times.popleft()
    if len(times) >= EXPORT_LIMIT:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="export_limit",
            translation_placeholders={"count": str(EXPORT_LIMIT)},
        )
    return times


async def async_export(
    hass: HomeAssistant,
    coordinator: AutodartsGamesCoordinator,
    file_format: str,
    what: str,
    folder: str | None = None,
) -> dict[str, Any]:
    """Write the export and describe it for the service response."""
    written = _recent_exports(hass)
    tables = EXPORT_TABLES if what == "all" else (what,)
    data = {table: TABLES[table](coordinator) for table in tables}
    now = dt_util.now()
    name = f"homedarts-{what}-{now:%Y%m%d-%H%M%S}-{secrets.token_hex(8)}"
    try:
        path, url = await hass.async_add_executor_job(
            _write, hass.config, folder, name, file_format, data, now.isoformat()
        )
    except ExportFolderError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="export_folder",
            translation_placeholders={"folder": _shown(folder)},
        ) from err
    except OSError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="export_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    written.append(monotonic())
    return {
        "path": str(path),
        "url": url,
        "download": offer_download(hass, path),
        "format": file_format,
        "what": what,
        "rows": {table: len(rows) for table, rows in data.items()},
    }
