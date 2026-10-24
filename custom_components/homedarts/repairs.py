"""Repairs the integration can fix itself: calibrate, follow a moved board,
replace a changed blueprint with the one of the release, or restore the backup
of a board added again."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

from .backup import ISSUE as BACKUP_AVAILABLE
from .backup import async_restore
from .const import CONF_BOARD_ID, CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN
from .errors import AutodartsApiError
from .local_api import AutodartsLocalClient
from .local_coordinator import AutodartsLocalCoordinator
from .shipped_blueprints import ISSUE as BLUEPRINT_EDITED
from .shipped_blueprints import async_restore_blueprint
from .takeover import ISSUE_RESTART


def address_title(entry: ConfigEntry, host: str) -> str:
    """The entry's title at a new address: a title that named the old address
    names the new one; a board's name stays."""
    old = entry.data.get(CONF_HOST)
    if old and entry.title == f"Autodarts ({old})":
        return f"Autodarts ({host})"
    return entry.title


def _address(host: str, port: int) -> str:
    return str(URL.build(scheme="http", host=host, port=port))


@callback
def async_offer_address(
    hass: HomeAssistant, entry: ConfigEntry, host: str, port: int
) -> None:
    """A board with the entry's board ID answers at another address. Any device
    can claim a board ID, so the entry moves only once the user confirms."""
    old = entry.data.get(CONF_HOST)
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"board_moved_{entry.entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="board_moved",
        translation_placeholders={
            "old": _address(old, entry.data.get(CONF_PORT, DEFAULT_PORT))
            if old
            else "",
            "new": _address(host, port),
        },
        data={"entry_id": entry.entry_id, "host": host, "port": port},
    )


class CalibrationFlow(RepairsFlow):
    """Many corrected darts: calibrate once the board is empty."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        if user_input is None:
            issue = ir.async_get(self.hass).async_get_issue(DOMAIN, self.issue_id)
            return self.async_show_form(
                step_id="confirm",
                description_placeholders=issue.translation_placeholders
                if issue
                else None,
            )
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        loaded = entry is not None and entry.state is ConfigEntryState.LOADED
        coordinator = entry.runtime_data.local if entry and loaded else None
        # Only a Board Manager calibrates; a dartboard without Autodarts has none.
        if not isinstance(coordinator, AutodartsLocalCoordinator):
            return self.async_abort(reason="board_unavailable")
        try:
            await coordinator.async_recalibrate()
        except HomeAssistantError:
            return self.async_abort(reason="calibration_failed")
        return self.async_create_entry(data={})


class BoardMovedFlow(RepairsFlow):
    """The board answers at another address: switch to it once confirmed."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        entry = self.hass.config_entries.async_get_entry(
            str(self._data.get("entry_id", ""))
        )
        host, port = self._data.get("host"), self._data.get("port")
        if entry is None or not isinstance(host, str) or type(port) is not int:
            return self.async_abort(reason="board_unavailable")
        client = AutodartsLocalClient(host, port, async_get_clientsession(self.hass))
        if user_input is None:
            return self.async_show_form(
                step_id="confirm", description_placeholders={"new": client.base_url}
            )
        # The board may have moved again since the notice appeared.
        try:
            identity = await client.identify()
        except AutodartsApiError:
            return self.async_abort(reason="board_unavailable")
        if identity["board_id"] != entry.data[CONF_BOARD_ID]:
            return self.async_abort(reason="board_unavailable")
        self.hass.config_entries.async_update_entry(
            entry,
            title=address_title(entry, host),
            data={**entry.data, CONF_HOST: host, CONF_PORT: port},
        )
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_create_entry(data={})


class BlueprintEditedFlow(RepairsFlow):
    """A blueprint the user changed: replace it with the one of the release once
    confirmed, or keep it by ignoring the repair."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._file = str(data.get("file", ""))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        if user_input is None:
            issue = ir.async_get(self.hass).async_get_issue(DOMAIN, self.issue_id)
            return self.async_show_form(
                step_id="confirm",
                description_placeholders=issue.translation_placeholders
                if issue
                else None,
            )
        try:
            restored = await async_restore_blueprint(self.hass, self._file)
        except OSError:
            return self.async_abort(reason="write_failed")
        if not restored:
            return self.async_abort(reason="not_shipped")
        return self.async_create_entry(data={})


class BackupFlow(RepairsFlow):
    """A backup of a board added again: restore it once confirmed, or keep the
    board as it is by ignoring the repair."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    key: str(self._data.get(key, "")) for key in ("board", "date")
                },
            )
        entry = self.hass.config_entries.async_get_entry(
            str(self._data.get("entry_id", ""))
        )
        if entry is None:
            return self.async_abort(reason="board_unavailable")
        try:
            await async_restore(
                self.hass, entry, str(self._data.get("file", "")), "replace"
            )
        except HomeAssistantError:
            return self.async_abort(reason="restore_failed")
        return self.async_create_entry(data={})


class RestartFlow(RepairsFlow):
    """Restart Home Assistant, which unloads the integration under its former
    name once its boards are taken over and its folder is gone."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        if user_input is not None:
            await self.hass.services.async_call("homeassistant", "restart")
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="confirm")


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """The flow of a fixable issue, named <issue>_<entry_id>, or for a blueprint
    <issue>_<file>_<version>."""
    data = data or {}
    if issue_id.startswith("board_moved_"):
        return BoardMovedFlow(data)
    if issue_id.startswith("calibration_"):
        return CalibrationFlow(str(data.get("entry_id", "")))
    if issue_id.startswith(BLUEPRINT_EDITED):
        return BlueprintEditedFlow(data)
    if issue_id.startswith(BACKUP_AVAILABLE):
        return BackupFlow(data)
    if issue_id == ISSUE_RESTART:
        return RestartFlow()
    # Only the issues above are fixable; any other one has nothing to confirm.
    return ConfirmRepairFlow()
