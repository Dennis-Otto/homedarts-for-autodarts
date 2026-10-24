"""The Autodarts integration: local boards and dartboards without Autodarts."""

from __future__ import annotations

import logging
from contextlib import suppress

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from . import takeover
from .backup import ISSUE as BACKUP_AVAILABLE
from .backup import async_backup, async_offer_backup
from .button import V1_BUTTONS
from .card import (
    async_add_card_resources,
    async_register_card,
    async_remove_card_resources,
)
from .const import (
    CLOUD_KEYS,
    CLOUD_SENSORS,
    CONF_BOARD_ID,
    CONF_HOST,
    CONF_MANUAL_BOARD,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
    PLATFORMS,
)
from .errors import AutodartsApiError
from .games_coordinator import AutodartsGamesCoordinator, board_deleted
from .local_api import AutodartsLocalClient
from .local_coordinator import ISSUES, AutodartsLocalCoordinator
from .manual_coordinator import AutodartsManualCoordinator
from .online import async_setup_bridge
from .report import BoardReports
from .runtime import AutodartsConfigEntry, AutodartsRuntimeData
from .sensor import SYSTEM_SENSORS
from .services import async_setup_services
from .shipped_blueprints import async_install_blueprints
from .storage import TrainingStore
from .websocket import async_setup_websocket

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Entities that only one Board Manager generation provides.
V1_ONLY = (("switch", "upstream"), *(("button", key) for key in V1_BUTTONS))
V2_ONLY = (
    ("binary_sensor", "cloud_link"),
    *(("sensor", description.key) for description in SYSTEM_SENSORS),
    ("update", "board_software"),
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Provide the dashboard card, the actions, the positions for the cards and
    the blueprints once, independent of entries."""
    await async_register_card(hass)
    async_setup_services(hass)
    async_setup_websocket(hass)
    await async_install_blueprints(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AutodartsConfigEntry) -> bool:
    """Set up a board, which stays usable while it is switched off."""
    if takeover.CONF_TAKEOVER in entry.data:
        # A board of the integration under its former name: its entities, stores
        # and dashboards come over before anything of the board sets up.
        await takeover.async_take_over(hass, entry)
    # Again with every board, so that a board added after the last one was deleted
    # brings the cards back to Home Assistant Cast.
    await async_add_card_resources(hass)
    local: AutodartsGamesCoordinator
    if entry.data.get(CONF_MANUAL_BOARD):
        # A dartboard without Autodarts: nothing to reach, only the store to read.
        local = AutodartsManualCoordinator(hass, entry.data[CONF_BOARD_ID], entry)
        await local.async_load()
        await local.async_config_entry_first_refresh()
    elif host := entry.data.get(CONF_HOST):
        local = AutodartsLocalCoordinator(
            hass,
            AutodartsLocalClient(
                host,
                entry.data.get(CONF_PORT, DEFAULT_PORT),
                async_get_clientsession(hass),
            ),
            entry.data[CONF_BOARD_ID],
            entry,
        )
        # A store that cannot be read stops the setup, unlike a board that is
        # switched off: nothing may overwrite the training with empty data.
        await local.async_load()
        # Entities stay and recover when the board answers again.
        with suppress(ConfigEntryNotReady):
            await local.async_config_entry_first_refresh()
    else:
        # Retrying cannot help: the user has to enter the address first.
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="no_local_address"
        )
    if local.store.empty:
        # Added again after it was deleted, perhaps: its backup is offered.
        await async_offer_backup(hass, entry)
    # A board that is switched off does not stop the setup: the entities of
    # training and games work without it, and the others recover with the board.
    runtime = entry.runtime_data = AutodartsRuntimeData(local)
    device = next(
        (
            device
            for device in dr.async_entries_for_config_entry(
                dr.async_get(hass), entry.entry_id
            )
            if (DOMAIN, entry.data[CONF_BOARD_ID]) in device.identifiers
        ),
        None,
    )
    # The name found by the board search or given to a dartboard without
    # Autodarts, else the device's.
    local.device_name = entry.data.get(CONF_NAME) or (
        device.name if device and device.name else "Autodarts Board"
    )
    if isinstance(local, AutodartsLocalCoordinator):
        local.board_manager.setup_generation = local.generation or 1
        # An unknown generation keeps the entities and their customizations.
        if local.generation is not None:
            _remove_other_generation(hass, entry, local.board_manager_2)
    # Moments of online matches arrive as board events, if switched on.
    runtime.bridge = await async_setup_bridge(hass, entry, local)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    local.async_start()
    return True


def _remove_other_generation(
    hass: HomeAssistant, entry: ConfigEntry, board_manager_2: bool
) -> None:
    """Remove entities of the other Board Manager generation after a change."""
    registry = er.async_get(hass)
    for platform, key in V1_ONLY if board_manager_2 else V2_ONLY:
        entity_id = registry.async_get_entity_id(
            platform, DOMAIN, f"{entry.data[CONF_BOARD_ID]}_{key}"
        )
        if entity_id:
            registry.async_remove(entity_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Upgrade version 1 entries, which stored a board address or a password, and
    those before version 2.2, which could hold the data of the cloud link."""
    # Home Assistant itself refuses entries of a newer major version.
    if entry.version == 1 and not await _async_migrate_v1(hass, entry):
        return False
    # An entry of a newer minor version, from a later release, stays as it is.
    if entry.minor_version < 2:
        _remove_cloud_link(hass, entry)
    return True


async def _async_migrate_v1(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Keep the board of a version 1 entry, found by its address if need be."""
    data = dict(entry.data)
    board_id = data.get(CONF_BOARD_ID)
    host = data.get(CONF_HOST)
    port = data.get(CONF_PORT, DEFAULT_PORT)
    if not board_id and host:
        client = AutodartsLocalClient(host, port, async_get_clientsession(hass))
        try:
            board_id = (await client.get_config()).get(CONF_BOARD_ID)
        except AutodartsApiError:
            board_id = None
    if not board_id:
        # Retried at the next start, so a board that is switched off is no problem.
        _LOGGER.warning(
            "Cannot migrate the Autodarts entry %s yet: the board at %s does not answer",
            entry.title,
            host,
        )
        return False
    # Version 1 cloud entries stored the account password; never keep it.
    new = {CONF_BOARD_ID: board_id}
    if host:
        new |= {CONF_HOST: host, CONF_PORT: port}
    hass.config_entries.async_update_entry(
        entry, data=new, unique_id=board_id, version=2
    )
    _LOGGER.info("Migrated the Autodarts entry %s to version 2", entry.title)
    return True


def _remove_cloud_link(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the login of the cloud link and its sensors from an entry.

    An entry that only the cloud reached has no address; its setup keeps
    failing with no_local_address until one is entered in Reconfigure.
    """
    registry = er.async_get(hass)
    for key in CLOUD_SENSORS:
        if entity_id := registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.data[CONF_BOARD_ID]}_{key}"
        ):
            registry.async_remove(entity_id)
    hass.config_entries.async_update_entry(
        entry,
        data={key: value for key, value in entry.data.items() if key not in CLOUD_KEYS},
        minor_version=2,
    )


async def async_unload_entry(hass: HomeAssistant, entry: AutodartsConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # The board stays loaded, and its repair issues still apply.
        return False
    # Home Assistant shuts the coordinator down only after the unload. A read
    # still in flight ends here first, so that it cannot bring back an issue
    # deleted below.
    await entry.runtime_data.local.async_shutdown()
    # The board's repair issues come back with its next setup, where they
    # still apply; their fixes need a loaded board.
    _delete_issues(hass, entry)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: AutodartsConfigEntry) -> None:
    """Deleting a board deletes its stores once a backup of them is written,
    and deleting its last board the dashboard resources of the cards. The other
    boards of a tournament on several boards play on without it."""
    store = TrainingStore(hass, entry.entry_id)
    board_deleted(hass, entry.entry_id, await store.async_load())
    try:
        await async_backup(hass, entry, removed=True)
    except HomeAssistantError:
        # Nothing is lost: the stores stay where they are.
        _LOGGER.warning(
            "No backup of %s could be written, so its stored data stays in "
            "the .storage folder of Home Assistant",
            entry.title,
            exc_info=True,
        )
    else:
        await store.async_remove()
        await BoardReports.async_remove(hass, entry.entry_id)
    _delete_issues(hass, entry)
    ir.async_delete_issue(hass, DOMAIN, f"{BACKUP_AVAILABLE}_{entry.entry_id}")
    # An ignored board loads nothing; a disabled one can come back.
    if all(
        other.entry_id == entry.entry_id
        for other in hass.config_entries.async_entries(DOMAIN, include_ignore=False)
    ):
        await async_remove_card_resources(hass)


def _delete_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    for issue in ISSUES:
        ir.async_delete_issue(hass, DOMAIN, f"{issue}_{entry.entry_id}")
