"""Dart positions for the cards, thousands of them too many for attributes, the
sounds of a voice pack for the caller of the scoreboard, and the own training
plans of a board for the editor of the training card."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN
from .games_coordinator import AutodartsGamesCoordinator
from .plans import (
    MAX_DARTS,
    MAX_NAME,
    MAX_PLANS,
    MAX_ROUNDS,
    MAX_STEPS,
    PlanError,
    own_stored,
    read_plans,
)
from .profiles import NAME_LENGTH
from .voices import PACK_LENGTH, async_voice_pack

if TYPE_CHECKING:
    # Home Assistant 2026.10 validates with probatio and makes "voluptuous" an alias
    # of it, so the types are probatio's; older versions still use voluptuous.
    import probatio as vol
else:
    import voluptuous as vol


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_positions)
    websocket_api.async_register_command(hass, ws_voice_pack)
    websocket_api.async_register_command(hass, ws_plans)
    websocket_api.async_register_command(hass, ws_save_plans)


def _no_board(connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    connection.send_error(
        msg["id"], websocket_api.ERR_NOT_FOUND, "No loaded Autodarts board"
    )


def _board(hass: HomeAssistant, device_id: str) -> AutodartsGamesCoordinator | None:
    """The local board of an Autodarts device, if it is loaded."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    for entry in hass.config_entries.async_entries(DOMAIN):
        local: AutodartsGamesCoordinator | None = (
            entry.runtime_data.local if entry.state is ConfigEntryState.LOADED else None
        )
        if local and (DOMAIN, local.board_id) in device.identifiers:
            return local
    return None


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/positions",
        vol.Required("device_id"): str,
        vol.Optional("player"): vol.All(str, vol.Length(max=NAME_LENGTH)),
        # Only the aim map asks for the aim model, the positions alone cost nothing.
        vol.Optional("aim", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_positions(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The positions of the session's darts, or of a player's last darts, and
    their aim model when asked."""
    board = _board(hass, msg["device_id"])
    if board is None:
        _no_board(connection, msg)
        return
    player = msg.get("player")
    aim = await board.async_aim(player) if msg["aim"] else None
    result = board.games.progress.positions(player)
    connection.send_result(msg["id"], result if aim is None else {**result, "aim": aim})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/voice_pack",
        vol.Required("pack"): vol.All(str, vol.Length(min=1, max=PACK_LENGTH)),
    }
)
@websocket_api.async_response
async def ws_voice_pack(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Every sound of a voice pack by its key, with the addresses the scoreboard
    loads them from with its login; not found for a pack without sounds."""
    sounds = await async_voice_pack(hass, msg["pack"])
    if not sounds:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "No such voice pack"
        )
        return
    connection.send_result(msg["id"], {"pack": msg["pack"], "sounds": sounds})


# The limits of own plans, for the fields of the editor.
PLAN_LIMITS = {
    "plans": MAX_PLANS,
    "steps": MAX_STEPS,
    "name": MAX_NAME,
    "darts": MAX_DARTS,
    "rounds": MAX_ROUNDS,
}


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/plans",
        vol.Required("device_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_plans(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The own training plans of a board as its options keep them, with their
    limits; for administrators, who change them."""
    board = _board(hass, msg["device_id"])
    if board is None:
        _no_board(connection, msg)
        return
    connection.send_result(
        msg["id"],
        {"plans": own_stored(board.games.plans.custom), "limits": PLAN_LIMITS},
    )


async def _plan_error(hass: HomeAssistant, error: PlanError, language: str) -> str:
    """The error of the options that tells which plan and step is wrong, in
    the language of the user, with its placeholders filled in."""
    texts = await async_get_translations(hass, language, "options", [DOMAIN])
    text = texts.get(f"component.{DOMAIN}.options.error.{error.reason}", error.reason)
    for key, value in error.placeholders().items():
        text = text.replace(f"{{{key}}}", value)
    return text


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save_plans",
        vol.Required("device_id"): str,
        vol.Required("plans"): list,
        # The language of the user, for the error; else that of Home Assistant.
        vol.Optional("language"): vol.All(str, vol.Length(min=2, max=35)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save_plans(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Keep the own training plans of a board, which the options of the board
    show in YAML as well; an invalid list is refused with an error that tells
    which plan and step is wrong and why."""
    board = _board(hass, msg["device_id"])
    if board is None:
        _no_board(connection, msg)
        return
    try:
        plans = read_plans(msg["plans"])
    except PlanError as error:
        language = msg.get("language") or hass.config.language
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            await _plan_error(hass, error, language),
        )
        return
    await board.async_save_plans(plans)
    connection.send_result(msg["id"], {"plans": own_stored(plans)})
