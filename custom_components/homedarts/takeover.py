"""Take over the boards that the integration set up under its former name.

Up to version 1.18 the integration was called Autodarts, with the domain
autodarts, until Autodarts asked for a name of its own (decision 0026). A board
set up then is an entry of that domain. Taking it over moves what it has to an
entry of this domain: its entities with their IDs, and so their history and
statistics, its device, the training, games and reports in its stores, the
highlights, exports and voice packs in the media folders and the cards in the
dashboards. The old entry goes, and with the last one the folder of the old
integration, which HACS leaves beside the new one when the domain changes.

What refers to the actions of the old domain, such as autodarts.start_game, in
automations, scripts and dashboards in YAML stays as it is: a repair lists it,
looks again at each start and goes when nothing is left.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Any, Final

from homeassistant.components.automation import DATA_COMPONENT as AUTOMATIONS
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.dashboard import LovelaceStorage
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.util.hass_dict import HassKey

from .card import async_remove_modules
from .const import CLOUD_KEYS, CLOUD_SENSORS, CONF_BOARD_ID, DOMAIN
from .report import REPORT_STORES, report_store
from .storage import TrainingStore
from .voices import MARK, VOICES

_LOGGER = logging.getLogger(__name__)

# The domain of the integration up to version 1.18.
OLD_DOMAIN: Final = "autodarts"
# In the data of an entry until its setup: the ID of the old entry it takes over.
CONF_TAKEOVER: Final = "takeover"
# The repairs once the last board is taken over.
ISSUE_REFERENCES: Final = "takeover_references"
ISSUE_RESTART: Final = "takeover_restart"
# The marker of a voice pack that the old integration generated.
OLD_MARK: Final = ".autodarts-voice-pack"
# An action of the old domain: autodarts.start_game, not play.autodarts.io.
OLD_ACTION = re.compile(rf"\b{OLD_DOMAIN}\.(?!io\b|com\b)[a-z_]+\b")
# A card or the dashboard strategy of the old integration.
OLD_CARD = re.compile(rf"custom:{OLD_DOMAIN}(-[a-z-]+)?")
# The modules of the old cards in the dashboard resources, at any version.
OLD_MODULES = (f"{OLD_DOMAIN}-card.js", f"{OLD_DOMAIN}-strategy.js")
# Boards taken over at once can each find no old board left: they finish one by one.
FINISHING: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_takeover_finishing")


@callback
def old_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """The boards of the former domain that no entry of this one has taken over.

    An ignored board stays ignored. Only an entry that the integration made under
    its former name has a board ID in the data of version 2: an entry of the first
    version, which it never migrated, and one of another integration with the
    domain autodarts, such as the original HACSAutodarts, stay as they are.
    """
    taken = {entry.unique_id for entry in hass.config_entries.async_entries(DOMAIN)}
    return [
        entry
        for entry in hass.config_entries.async_entries(OLD_DOMAIN, include_ignore=False)
        if entry.version >= 2
        and entry.data.get(CONF_BOARD_ID)
        and entry.unique_id not in taken
    ]


def takeover_data(old: ConfigEntry) -> dict[str, Any]:
    """The data of the entry that takes the old one over."""
    data = {key: value for key, value in old.data.items() if key not in CLOUD_KEYS}
    return {**data, CONF_TAKEOVER: old.entry_id}


async def async_take_over(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Move the board of the old entry to this one, before it sets up.

    The old entry is unloaded first, which saves its stores, so that their copy
    misses nothing; its removal then deletes what is left of it.

    The takeover leaves the data of the entry only when nothing of it is left for
    this board: at once while other old boards remain, since the last of them
    finishes, and otherwise once the finish has returned. A finish that fails, or
    that a stop of Home Assistant interrupts, so runs again at the next setup of
    the board, and finds done what is done.
    """
    old_id = entry.data[CONF_TAKEOVER]
    if (old := hass.config_entries.async_get_entry(old_id)) is not None:
        if old.state.recoverable:
            await hass.config_entries.async_unload(old_id)
        _move_registries(hass, old, entry.entry_id)
        await _async_copy_stores(hass, old_id, entry.entry_id)
        await hass.config_entries.async_remove(old_id)
    if not hass.config_entries.async_entries(OLD_DOMAIN, include_ignore=False):
        try:
            await async_finish(hass)
        # Whatever stops the finish must not stop the board, which has everything
        # it needs by now: the finish runs again at its next setup.
        except Exception:
            _LOGGER.exception(
                "The takeover of the boards of the integration Autodarts is not "
                "finished; it continues when %s sets up again",
                entry.title,
            )
            return
    hass.config_entries.async_update_entry(
        entry,
        data={key: value for key, value in entry.data.items() if key != CONF_TAKEOVER},
    )


@callback
def _move_registries(hass: HomeAssistant, old: ConfigEntry, new_id: str) -> None:
    """The entities and the device of the old entry become those of the new one,
    with their IDs, names, areas and customizations; the sensors of the cloud link
    that never came go.

    The entities come first: Home Assistant moves the device only together with
    the entities that are already the new entry's.
    """
    entities = er.async_get(hass)
    cloud = {f"{old.data.get(CONF_BOARD_ID)}_{key}" for key in CLOUD_SENSORS}
    for item in er.async_entries_for_config_entry(entities, old.entry_id):
        if item.domain == "sensor" and item.unique_id in cloud:
            entities.async_remove(item.entity_id)
            continue
        # An entity that an earlier entry of this domain left behind gives way.
        if taken := entities.async_get_entity_id(item.domain, DOMAIN, item.unique_id):
            entities.async_remove(taken)
        try:
            entities.async_update_entity_platform(
                item.entity_id, DOMAIN, new_config_entry_id=new_id
            )
        except ValueError:
            # Still loaded, because the old entry failed to unload: the entity of
            # this domain gets an ID of its own.
            _LOGGER.warning("%s stays with the old integration", item.entity_id)
    devices = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(devices, old.entry_id):
        devices.async_update_device(
            device.id,
            new_config_entry_id=new_id,
            new_identifiers={
                (DOMAIN if domain == OLD_DOMAIN else domain, key)
                for domain, key in device.identifiers
            },
        )


async def _async_copy_stores(hass: HomeAssistant, old_id: str, new_id: str) -> None:
    """The training, the games and the reports of the old entry, loaded as the old
    integration saved them and saved for the new entry."""
    pairs = [
        (TrainingStore(hass, old_id, OLD_DOMAIN), TrainingStore(hass, new_id)),
        *(
            (
                report_store(hass, old_id, name, OLD_DOMAIN),
                report_store(hass, new_id, name),
            )
            for name in REPORT_STORES
        ),
    ]
    for old, new in pairs:
        if (data := await old.async_load()) is not None:
            await new.async_save(data)


async def async_finish(hass: HomeAssistant) -> None:
    """With the last board taken over: the media, the dashboards and the folder of
    the old integration; then the repairs for what still names the old actions
    and for the restart that unloads the old integration. What is done stays done,
    so the second of two boards that finish at once finds nothing left to do."""
    async with hass.data.setdefault(FINISHING, asyncio.Lock()):
        await hass.async_add_executor_job(
            _move_media, list(hass.config.media_dirs.values())
        )
        references = await _async_references(hass)
        await async_remove_modules(hass, *OLD_MODULES, folder=OLD_DOMAIN)
        _report_references(hass, references)
        if await hass.async_add_executor_job(
            _remove_old_folder, Path(hass.config.path("custom_components", OLD_DOMAIN))
        ):
            ir.async_create_issue(
                hass,
                DOMAIN,
                ISSUE_RESTART,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_RESTART,
            )


async def async_check_references(hass: HomeAssistant) -> None:
    """Once Home Assistant has started, with the automations and scripts loaded:
    look again for what still names the old domain while the repair that lists it
    is there, so that its list stays current and the repair goes with the last of
    it. The repair may also be one that an earlier version made without keeping
    it over a restart, which comes back this way. Without the repair nothing is looked
    at: after the user has worked it off, a start costs nothing."""
    if ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_REFERENCES) is None:
        return
    async with hass.data.setdefault(FINISHING, asyncio.Lock()):
        _report_references(hass, await _async_references(hass))


async def _async_references(hass: HomeAssistant) -> list[str]:
    """The automations, the scripts and the dashboards in YAML that still use the
    old domain; the dashboards that Home Assistant keeps get the new cards."""
    return [*_automations_and_scripts(hass), *await _async_update_dashboards(hass)]


@callback
def _report_references(hass: HomeAssistant, references: list[str]) -> None:
    """The repair that lists what still uses the old domain, kept over a restart,
    because the takeover asks for one; it goes when nothing is left. A repair
    that the user ignored stays ignored."""
    if not references:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_REFERENCES)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_REFERENCES,
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_REFERENCES,
        translation_placeholders={
            "items": "\n".join(f"- {item}" for item in references)
        },
    )


def _move_media(roots: list[str]) -> None:
    """The highlights, exports and voice packs of the old integration move to the
    folders of this one; what is there already stays, and so does the old folder
    with what could not move. A folder that is read-only or full, or a file that
    cannot move, stays with a warning: it stops neither the rest of the media nor
    the dashboards, the repairs and the removal of the old integration."""
    for root in roots:
        old = Path(root, OLD_DOMAIN)
        if not old.is_dir():
            continue
        new = Path(root, DOMAIN)
        try:
            new.mkdir(exist_ok=True)
            items = list(old.iterdir())
        except OSError as err:
            _LOGGER.warning("The media in %s stay where they are: %s", old, err)
            continue
        for item in items:
            if not (new / item.name).exists():
                _move(item, new / item.name)
        for marker in Path(root, VOICES).glob(f"*/{OLD_MARK}"):
            _move(marker, marker.with_name(MARK))
        with suppress(OSError):
            old.rmdir()


def _move(source: Path, target: Path) -> None:
    """Move a file or a folder, or warn that it stays where it is."""
    try:
        source.rename(target)
    except OSError as err:
        _LOGGER.warning("%s stays where it is: %s", source, err)


async def _async_update_dashboards(hass: HomeAssistant) -> list[str]:
    """Rename the cards and the strategy in the dashboards that Home Assistant
    keeps; returns the dashboards in YAML that still use the old ones."""
    if (lovelace := hass.data.get(LOVELACE_DATA)) is None:
        return []
    left = []
    for url_path, dashboard in lovelace.dashboards.items():
        try:
            config = await dashboard.async_load(False)
        except HomeAssistantError:
            # A dashboard that Home Assistant generates has nothing to rename.
            continue
        renamed = _renamed(config)
        if renamed == config:
            continue
        if isinstance(dashboard, LovelaceStorage):
            await dashboard.async_save(renamed)
        else:
            left.append(f"/{url_path or 'lovelace'}")
    return left


def _renamed(value: Any) -> Any:
    """A dashboard with the cards of this integration: the types of the cards and
    the strategy, and the flat board style, which the cards called autodarts."""
    if isinstance(value, dict):
        return {
            key: "flat"
            if key == "board_style" and item == OLD_DOMAIN
            else _renamed(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_renamed(item) for item in value]
    if isinstance(value, str) and (match := OLD_CARD.fullmatch(value)):
        return f"custom:{DOMAIN}{match.group(1) or ''}"
    return value


@callback
def _automations_and_scripts(hass: HomeAssistant) -> list[str]:
    """The automations and scripts that call an action of the old domain."""
    found = []
    for component in (hass.data.get(AUTOMATIONS), hass.data.get("script")):
        for entity in component.entities if component else ():
            raw = getattr(entity, "raw_config", None)
            if raw and OLD_ACTION.search(json.dumps(raw, default=str)):
                found.append(entity.entity_id)
    return sorted(found)


def _remove_old_folder(folder: Path) -> bool:
    """Delete the folder of the integration under its former name, which HACS left
    behind: only that one, recognized by its manifest, never another integration
    with the domain autodarts."""
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not (
        isinstance(manifest, dict)
        and manifest.get("domain") == OLD_DOMAIN
        and "@Dennis-Otto" in manifest.get("codeowners", [])
    ):
        return False
    shutil.rmtree(folder)
    return True
