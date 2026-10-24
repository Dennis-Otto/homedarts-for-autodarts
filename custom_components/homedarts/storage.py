"""The stored training sessions, practice game and records of a board."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
    UnsupportedStorageVersionError,
)
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .report import BoardReports

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
# Raised with each change of the stored layout; every part restores older
# layouts itself, see _async_migrate_func. 2: version 1.6 added the progress,
# the tournament, the match summary and the bot. 3: the switch that frees a
# stuck takeout.
STORAGE_MINOR_VERSION = 3
# A change of the training is saved this many seconds after it, together
# with those that follow.
TRAINING_SAVE_DELAY = 5


def storage_key(entry_id: str, domain: str = DOMAIN) -> str:
    """The file in .storage that holds the training of an entry; another domain
    for an entry of the integration under its former name (takeover.py)."""
    return f"{domain}.{entry_id}.training"


class TrainingStore(Store[dict[str, Any]]):
    """Kept private: player names and personal bests are stored with the darts."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, domain: str = DOMAIN
    ) -> None:
        super().__init__(
            hass,
            STORAGE_VERSION,
            storage_key(entry_id, domain),
            private=True,
            minor_version=STORAGE_MINOR_VERSION,
        )

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Data of another minor version loads as it is.

        Every part restores older layouts and ignores fields it does not know,
        so data written by a newer release also loads after a downgrade; the
        BoardStore keeps its unknown parts when it saves. Home Assistant
        refuses a newer major version before it calls this.
        """
        return old_data


class BoardStore:
    """Where Home Assistant keeps the training, the games and the reports of a
    board: the training store, with the stores of the weekly report and the
    training journal.

    Everything is restored before the first poll, and nothing is saved before.
    A store that cannot be read stops the setup instead, so that no empty data
    overwrites it: for a retry after a read error, for good when it is of a
    newer layout or cannot be restored. Parts of the training store that a
    newer release wrote stay after a downgrade.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        reports: BoardReports,
        data: Callable[[], dict[str, Any]],
    ) -> None:
        self.training = TrainingStore(hass, entry_id)
        self._reports = reports
        # What the training store holds now, built when it is written.
        self._data = data
        # Whether the stores were restored; nothing is saved before.
        self.loaded = False
        # Whether the training store was empty, as for a board added anew.
        self.empty = False
        # Top-level parts of the training store the games do not own: those of
        # a newer release, and the backups merged into it (backup.py).
        self._unknown: dict[str, Any] = {}
        self._dirty = False

    async def async_load(self, restore: Callable[[object], None]) -> None:
        """Hand the stored training to restore, then restore the reports."""
        try:
            saved = await self.training.async_load()
            restore(saved)
            await self._reports.async_load()
        except UnsupportedStorageVersionError as err:
            self._keep()
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="storage_newer"
            ) from err
        except (HomeAssistantError, OSError) as err:
            self._keep()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="storage_unreadable"
            ) from err
        except Exception as err:
            self._keep()
            _LOGGER.exception("The stored training cannot be restored")
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="storage_invalid"
            ) from err
        known = self._data()
        self._unknown = {
            key: value
            for key, value in (saved if isinstance(saved, dict) else {}).items()
            if key not in known
        }
        self.loaded = True
        self.empty = saved is None
        if saved is None:
            self.save_later()

    def _keep(self) -> None:
        """Never write a store that could not be read."""
        for store in (self.training, *self._reports.stores):
            store.make_read_only()

    def _stored(self) -> dict[str, Any]:
        return {**self._unknown, **self._data()}

    def save_later(self) -> None:
        """Save a change in a few seconds, together with those that follow."""
        self._dirty = True
        self.training.async_delay_save(self._stored, TRAINING_SAVE_DELAY)

    async def async_save(self) -> None:
        """Save now, with everything before.

        A dart that arrives during the write marks the store again (see
        save_later), so the shutdown still saves it; the store is built once,
        without comparing it again.
        """
        self._dirty = False
        try:
            await self.training.async_save(self._stored())
        except BaseException:
            # Not written, for example cancelled: the shutdown saves it.
            self._dirty = True
            raise

    async def async_shutdown(self) -> None:
        """Write what is not saved yet; a store never restored is never written."""
        if self.loaded and self._dirty:
            await self.training.async_save(self._stored())
            self._dirty = False
        await self._reports.async_shutdown()
