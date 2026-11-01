"""Set up and reconfigure Autodarts boards in Home Assistant."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from ipaddress import IPv4Address, ip_address
from typing import TYPE_CHECKING, Any

from homeassistant.components import webhook
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_IMPORT,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import ObjectSelector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import granboard, takeover
from .const import (
    CONF_API_GENERATION,
    CONF_BOARD_ID,
    CONF_GRANBOARD,
    CONF_HOST,
    CONF_MANUAL_BOARD,
    CONF_PLANS,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
)
from .discovery import async_discover_boards
from .errors import AutodartsApiError, AutodartsConnectionError
from .local_api import AutodartsLocalAuthError, AutodartsLocalClient, board_generation
from .online import (
    CONF_NEW_ADDRESS,
    CONF_ONLINE_BRIDGE,
    CONF_ONLINE_REMOTE,
    CONF_WEBHOOK_ID,
    bridge_url,
    effects_csv,
)
from .plans import own_plans
from .repairs import address_title, async_offer_address

if TYPE_CHECKING:
    # Home Assistant 2026.10 validates with probatio and makes "voluptuous" an alias
    # of it, so the types are probatio's; older versions still use voluptuous.
    import probatio as vol
else:
    import voluptuous as vol


def _valid_host(host: str) -> bool:
    if not host or any(char.isspace() or char in "/?#@\\[]" for char in host):
        return False
    if ":" in host:
        try:
            return ip_address(host).version == 6
        except ValueError:
            return False
    return True


def _announced_host(discovery_info: ZeroconfServiceInfo) -> str | None:
    """The board's address; its own "ip" property only if it is the sender's.

    Any device can announce the service, so an address outside the
    announcement never makes Home Assistant contact another host.
    """
    usable = [
        address
        for address in discovery_info.ip_addresses
        if not (
            address.is_loopback
            or address.is_unspecified
            or address.is_multicast
            or address.is_link_local
        )
    ]
    advertised = discovery_info.properties.get("ip")
    for address in usable:
        if str(address) == advertised:
            return str(address)
    # Prefer IPv4, which works without a zone or router advertisements.
    usable.sort(key=lambda address: not isinstance(address, IPv4Address))
    return str(usable[0]) if usable else None


def _announced_port(discovery_info: ZeroconfServiceInfo) -> int:
    """Board Manager 2 may announce its HTTPS port; the plain HTTP one is used."""
    for value in (discovery_info.properties.get("insecurePort"), discovery_info.port):
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if type(value) is int and 0 < value < 65536:
            return value
    return DEFAULT_PORT


# The name a dartboard without Autodarts gets unless the user chooses another,
# and the one it gets with a Granboard.
MANUAL_BOARD_NAME = "Dartboard"
GRANBOARD_NAME = "Granboard"


def _menu_options(manual: bool = False) -> list[str]:
    """Search the network or enter an address, and a dartboard without
    Autodarts, with or without a Granboard, when one is set up."""
    options = ["discover", "local"]
    if manual:
        options.extend(("granboard", "manual"))
    return options


def _name_schema(default: str) -> vol.Schema:
    """The name of a dartboard without Autodarts."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=default): vol.All(
                str, vol.Strip, vol.Length(min=1, max=50)
            )
        }
    )


class AutodartsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a board in the local network or a dartboard without Autodarts."""

    VERSION = 2
    # 2.2 holds no data of the cloud link any more, see async_migrate_entry.
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AutodartsOptionsFlow:
        return AutodartsOptionsFlow()

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: ConfigEntry) -> bool:
        """The options switch the bridge for online matches, which delivers its
        moments as events of the local board; without one, nothing receives them."""
        return bool(config_entry.data.get(CONF_HOST))

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}
        self._found: dict[str, dict[str, Any]] = {}
        self._discovered: dict[str, Any] = {}
        # Names the board search reported, by board ID.
        self._names: dict[str, str] = {}
        # The Bluetooth address of the Granboard being set up.
        self._granboard = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search the network, enter a board address or set up a dartboard
        without Autodarts; first of all, take over the boards of the integration
        under its former name, if it has any."""
        options = _menu_options(manual=True)
        if takeover.old_entries(self.hass):
            options.insert(0, "takeover")
        return self.async_show_menu(step_id="user", menu_options=options)

    async def async_step_takeover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Take over every board of the integration under its former name, with
        its entities, statistics and dashboards (takeover.py)."""
        old = takeover.old_entries(self.hass)
        if not old:
            return self.async_abort(reason="nothing_to_take_over")
        # A discovered board comes first: the flow is about it.
        old.sort(key=lambda entry: entry.unique_id != self.unique_id)
        if user_input is not None:
            for entry in old[1:]:
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_IMPORT},
                        data={takeover.CONF_TAKEOVER: entry.entry_id},
                    )
                )
            return await self._async_take_over(old[0])
        return self.async_show_form(
            step_id="takeover",
            description_placeholders={
                "boards": "\n".join(f"- {entry.title}" for entry in old)
            },
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Take over another board, which the takeover of the first one started."""
        old = self.hass.config_entries.async_get_entry(
            import_data[takeover.CONF_TAKEOVER]
        )
        if old is None or old not in takeover.old_entries(self.hass):
            return self.async_abort(reason="nothing_to_take_over")
        return await self._async_take_over(old)

    async def _async_take_over(self, old: ConfigEntry) -> ConfigFlowResult:
        """An entry with the board, data and options of the old one, which its
        setup takes over."""
        await self.async_set_unique_id(old.unique_id, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=old.title, data=takeover.takeover_data(old), options=dict(old.options)
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """A dartboard without Autodarts, whose darts are all entered by hand.

        It has no board ID of its own, so every one gets a new one: a home
        may have several.
        """
        if user_input is not None:
            name = user_input[CONF_NAME]
            board_id = f"manual_{uuid.uuid4().hex}"
            await self.async_set_unique_id(board_id)
            return self.async_create_entry(
                title=name,
                data={
                    CONF_BOARD_ID: board_id,
                    CONF_MANUAL_BOARD: True,
                    CONF_NAME: name,
                },
            )
        return self.async_show_form(
            step_id="manual", data_schema=_name_schema(MANUAL_BOARD_NAME)
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """A Granboard that Home Assistant's Bluetooth found."""
        await self.async_set_unique_id(granboard.board_id(discovery_info.address))
        self._abort_if_unique_id_configured()
        self._granboard = discovery_info.address
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_granboard_confirm()

    async def async_step_granboard(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """One of the Granboards that Home Assistant's Bluetooth sees, for a
        board whose discovery was dismissed, or to set it up before it shows."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(
                granboard.board_id(address), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            self._granboard = address
            return await self.async_step_granboard_confirm()
        configured = self._async_current_ids(include_ignore=False)
        found = {
            info.address: f"{info.name} ({info.address})"
            for info in granboard.async_discovered(self.hass)
            if granboard.board_id(info.address) not in configured
        }
        if not found:
            return self.async_abort(reason="no_granboards")
        return self.async_show_form(
            step_id="granboard",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(found)}),
        )

    async def async_step_granboard_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """A dartboard without Autodarts that receives the darts of the Granboard."""
        if user_input is not None:
            name = user_input[CONF_NAME]
            return self.async_create_entry(
                title=name,
                data={
                    CONF_BOARD_ID: self.unique_id,
                    CONF_MANUAL_BOARD: True,
                    CONF_NAME: name,
                    CONF_GRANBOARD: self._granboard,
                },
            )
        return self.async_show_form(
            step_id="granboard_confirm",
            data_schema=_name_schema(GRANBOARD_NAME),
            description_placeholders={"address": self._granboard},
        )

    async def _async_identify(self, host: str, port: int) -> dict[str, Any]:
        client = AutodartsLocalClient(host, port, async_get_clientsession(self.hass))
        return await client.identify()

    def _entry_elsewhere(
        self, board_id: str, host: str, port: int
    ) -> ConfigEntry | None:
        """The entry of this board, when it has another address than this one."""
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, board_id
        )
        if entry is None or entry.source == SOURCE_IGNORE:
            return None
        configured = (
            entry.data.get(CONF_HOST),
            entry.data.get(CONF_PORT, DEFAULT_PORT),
        )
        return None if configured == (host, port) else entry

    async def _async_still_answers(self, entry: ConfigEntry) -> bool:
        """Whether the board of the entry still answers at the entry's address."""
        if not entry.data.get(CONF_HOST):
            return False
        try:
            identity = await self._async_identify(
                entry.data[CONF_HOST], entry.data.get(CONF_PORT, DEFAULT_PORT)
            )
        except (AutodartsApiError, ValueError):
            return False
        return bool(identity["board_id"] == entry.unique_id)

    def _local_entry(
        self, host: str, port: int, identity: dict[str, Any]
    ) -> ConfigFlowResult:
        data = {
            CONF_BOARD_ID: identity["board_id"],
            CONF_HOST: host,
            CONF_PORT: port,
        }
        if generation := board_generation(identity.get("version")):
            data[CONF_API_GENERATION] = generation
        # The name given in Autodarts names the entry and the device.
        if name := self._names.get(identity["board_id"]):
            data[CONF_NAME] = name
        return self.async_create_entry(title=f"Autodarts ({name or host})", data=data)

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer the boards Autodarts lists for this network."""
        if user_input is not None:
            board = self._found[user_input[CONF_BOARD_ID]]
            # The address form keeps the found address if the board does not answer.
            self._user_input.update(
                {CONF_HOST: board["host"], CONF_PORT: board["port"]}
            )
            return await self.async_step_local(
                {CONF_HOST: board["host"], CONF_PORT: board["port"]}
            )
        try:
            boards = await async_discover_boards(async_get_clientsession(self.hass))
        except AutodartsConnectionError:
            return await self.async_step_local(error="discovery_failed")
        configured = {entry.unique_id for entry in self._async_current_entries()}
        if self.source == SOURCE_RECONFIGURE:
            # The board being reconfigured may have moved; keep offering it.
            configured.discard(self._get_reconfigure_entry().unique_id)
        self._found = {
            board["board_id"]: board
            for board in boards
            if board["board_id"] not in configured
        }
        if not self._found:
            return await self.async_step_local(error="no_boards_found")
        self._names = {
            board_id: board["name"]
            for board_id, board in self._found.items()
            if board["name"]
        }
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BOARD_ID): vol.In(
                        {
                            board_id: (
                                f"{board['name'] or 'Autodarts'} · {board['host']}"
                                + (f" · {board['version']}" if board["version"] else "")
                            )
                            for board_id, board in self._found.items()
                        }
                    )
                }
            ),
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Board Manager 2 announces itself as _autodarts-board._tcp."""
        host = _announced_host(discovery_info)
        if host is None:
            return self.async_abort(reason="cannot_connect_local")
        port = _announced_port(discovery_info)
        try:
            identity = await self._async_identify(host, port)
        except (AutodartsApiError, ValueError):
            return self.async_abort(reason="cannot_connect_local")
        board_id = identity["board_id"]
        if not board_id:
            return self.async_abort(reason="board_not_configured")
        await self.async_set_unique_id(board_id)
        entry = self._entry_elsewhere(board_id, host, port)
        if entry is not None and not await self._async_still_answers(entry):
            # Any device can announce the board ID, so a board that left its
            # address moves only once the user confirms the repair.
            async_offer_address(self.hass, entry, host, port)
        self._abort_if_unique_id_configured()
        self._async_abort_entries_match({CONF_BOARD_ID: identity["board_id"]})
        self.context["title_placeholders"] = {"name": host}
        if any(
            entry.unique_id == board_id for entry in takeover.old_entries(self.hass)
        ):
            # A board of the integration under its former name: take it over.
            return await self.async_step_takeover()
        self._discovered = {"host": host, "port": port, **identity}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        found = self._discovered
        if user_input is not None:
            return self._local_entry(found["host"], found["port"], found)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "host": found["host"],
                "version": found.get("version") or "?",
                "cameras": str(found.get("camera_count") or "?"),
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        self._user_input = {
            key: entry.data[key] for key in (CONF_HOST, CONF_PORT) if key in entry.data
        }
        if entry.data.get(CONF_MANUAL_BOARD):
            return await self.async_step_reconfigure_manual()
        return self.async_show_menu(step_id="reconfigure", menu_options=_menu_options())

    async def async_step_reconfigure_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The Autodarts board that a dartboard without Autodarts gets."""
        return self.async_show_menu(
            step_id="reconfigure_manual", menu_options=["discover", "local"]
        )

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None, error: str | None = None
    ) -> ConfigFlowResult:
        """Create a local entry, or update an existing entry's local address."""
        errors = {"base": error} if error else {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip().lower()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            if not _valid_host(host):
                errors[CONF_HOST] = "invalid_host"
            else:
                try:
                    identity = await self._async_identify(host, port)
                except AutodartsLocalAuthError:
                    errors["base"] = "board_access_denied"
                except (AutodartsApiError, ValueError):
                    errors["base"] = "cannot_connect_local"
                else:
                    board_id = identity[CONF_BOARD_ID]
                    if not board_id:
                        errors["base"] = "board_not_configured"
                    elif self.source == SOURCE_RECONFIGURE:
                        entry = self._get_reconfigure_entry()
                        if entry.data.get(CONF_MANUAL_BOARD):
                            return self._connect_board(entry, host, port, identity)
                        if board_id != entry.data[CONF_BOARD_ID]:
                            return self.async_abort(reason="wrong_board")
                        return self.async_update_reload_and_abort(
                            entry,
                            title=address_title(entry, host),
                            data_updates={CONF_HOST: host, CONF_PORT: port},
                            reason="reconfigure_successful",
                        )
                    else:
                        await self.async_set_unique_id(board_id)
                        known = self._entry_elsewhere(board_id, host, port)
                        if known is not None:
                            # The board answers where the user says it is now.
                            return self.async_update_reload_and_abort(
                                known,
                                title=address_title(known, host),
                                data_updates={CONF_HOST: host, CONF_PORT: port},
                                reason="address_updated",
                            )
                        self._abort_if_unique_id_configured()
                        self._async_abort_entries_match({CONF_BOARD_ID: board_id})
                        return self._local_entry(host, port, identity)
        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self._user_input.get(CONF_HOST, "")
                    ): str,
                    vol.Required(
                        CONF_PORT, default=self._user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): vol.All(int, vol.Range(min=1, max=65535)),
                }
            ),
            errors=errors,
        )

    def _connect_board(
        self, entry: ConfigEntry, host: str, port: int, identity: dict[str, Any]
    ) -> ConfigFlowResult:
        """A dartboard without Autodarts gets its Autodarts board.

        The board's ID takes the place of the entry's own in the entry, its device
        and its entities, so the games, the statistics, the entity IDs and the
        dashboards stay; the entities of the board come with the reload.
        """
        board_id = identity[CONF_BOARD_ID]
        known = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, board_id
        )
        if known is not None:
            return self.async_abort(reason="already_configured")
        old = entry.data[CONF_BOARD_ID]
        entities = er.async_get(self.hass)
        for item in er.async_entries_for_config_entry(entities, entry.entry_id):
            if item.unique_id == f"{old}_granboard_connected":
                # The Autodarts board has no Granboard, so its sensor goes.
                entities.async_remove(item.entity_id)
                continue
            unique_id = board_id + item.unique_id.removeprefix(old)
            # An entity left behind by an earlier entry of the board gives way.
            if taken := entities.async_get_entity_id(item.domain, DOMAIN, unique_id):
                entities.async_remove(taken)
            entities.async_update_entity(item.entity_id, new_unique_id=unique_id)
        devices = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
            devices.async_update_device(device.id, new_identifiers={(DOMAIN, board_id)})
        data = {
            **{
                key: value
                for key, value in entry.data.items()
                # A Granboard gives way to the board's own detection.
                if key not in (CONF_MANUAL_BOARD, CONF_GRANBOARD)
            },
            CONF_BOARD_ID: board_id,
            CONF_HOST: host,
            CONF_PORT: port,
        }
        if generation := board_generation(identity.get("version")):
            data[CONF_API_GENERATION] = generation
        return self.async_update_reload_and_abort(
            entry, unique_id=board_id, data=data, reason="board_connected"
        )


class AutodartsOptionsFlow(OptionsFlowWithReload):
    """Switch the bridge for online matches on or off and show its address, and
    keep the own training plans of the board."""

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        options = self.config_entry.options
        if user_input is not None:
            enabled = user_input[CONF_ONLINE_BRIDGE]
            # An editor that was emptied gives an empty object.
            plans = user_input.get(CONF_PLANS) or []
            if own_plans(plans) is None:
                return self._options_form({**options, **user_input}, invalid=True)
            self._options = {
                **options,
                CONF_ONLINE_BRIDGE: enabled,
                CONF_ONLINE_REMOTE: user_input[CONF_ONLINE_REMOTE],
            }
            if plans:
                self._options[CONF_PLANS] = plans
            else:
                self._options.pop(CONF_PLANS, None)
            # The address stays when the bridge is switched off, so that the
            # effects in the browser work again after switching it on; a new
            # one replaces it at once, so a leaked address never works again.
            if user_input.get(CONF_NEW_ADDRESS) or (
                enabled and not options.get(CONF_WEBHOOK_ID)
            ):
                self._options[CONF_WEBHOOK_ID] = webhook.async_generate_id()
            if enabled:
                return await self.async_step_online_bridge()
            return self.async_create_entry(data=self._options)
        return self._options_form(options)

    def _options_form(
        self, values: Mapping[str, Any], invalid: bool = False
    ) -> ConfigFlowResult:
        """The form of the options; `invalid` when the own plans are not valid,
        which stay in the form to be corrected."""
        schema: dict[vol.Marker, Any] = {
            vol.Required(
                CONF_ONLINE_BRIDGE, default=values.get(CONF_ONLINE_BRIDGE, False)
            ): bool,
            vol.Required(
                CONF_ONLINE_REMOTE, default=values.get(CONF_ONLINE_REMOTE, False)
            ): bool,
        }
        if self.config_entry.options.get(CONF_WEBHOOK_ID):
            schema[vol.Required(CONF_NEW_ADDRESS, default=False)] = bool
        schema[vol.Optional(CONF_PLANS, default=values.get(CONF_PLANS, []))] = (
            ObjectSelector()
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors={CONF_PLANS: "invalid_plans"} if invalid else None,
        )

    async def async_step_online_bridge(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The address and the effects to import into Tools for Autodarts."""
        if user_input is not None:
            return self.async_create_entry(data=self._options)
        url = bridge_url(
            self.hass, self._options[CONF_WEBHOOK_ID], self._options[CONF_ONLINE_REMOTE]
        )
        return self.async_show_form(
            step_id="online_bridge",
            data_schema=vol.Schema({}),
            description_placeholders={"url": url, "effects": effects_csv(url)},
        )
