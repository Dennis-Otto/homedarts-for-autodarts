"""Find boards on this network through the lookup the Board Manager app uses."""

from __future__ import annotations

import asyncio
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Any

import aiohttp

from .const import DEFAULT_PORT, DISCOVERY_URL
from .errors import AutodartsConnectionError


def is_board_address(address: IPv4Address | IPv6Address) -> bool:
    """Whether a board may be at an address that an announcement or the lookup names.

    Never Home Assistant's own host, an address of no host or of a group of hosts,
    or a link-local one, which needs a zone; an IPv4 address written as IPv6 counts
    as the IPv4 address.
    """
    if isinstance(address, IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return not (
        address.is_loopback
        or address.is_unspecified
        or address.is_multicast
        or address.is_link_local
    )


def _port(value: Any) -> int:
    port = int(value) if isinstance(value, (int, str)) and str(value).isdigit() else 0
    return port if 0 < port < 65536 else DEFAULT_PORT


async def async_discover_boards(session: aiohttp.ClientSession) -> list[dict[str, Any]]:
    """Boards Autodarts reports behind this network's public address.

    The service needs no login; it sees this network's public IP address, as it
    does when the Board Manager app searches for boards.
    """
    try:
        async with asyncio.timeout(10):
            async with session.get(DISCOVERY_URL) as response:
                response.raise_for_status()
                listed = await response.json(content_type=None)
    except (TimeoutError, aiohttp.ClientError, ValueError) as err:
        raise AutodartsConnectionError("Board lookup unavailable") from err
    boards = []
    for board in listed if isinstance(listed, list) else []:
        if not isinstance(board, dict):
            continue
        board_id, host = board.get("boardId"), board.get("ip")
        if not isinstance(board_id, str) or not board_id or not isinstance(host, str):
            continue
        try:
            address = ip_address(host)
        except ValueError:
            continue
        if not is_board_address(address):
            continue
        name, version = board.get("name"), board.get("version")
        boards.append(
            {
                "board_id": board_id,
                "host": host,
                "port": _port(board.get("insecurePort") or board.get("port")),
                "name": name.strip()
                if isinstance(name, str) and name.strip()
                else None,
                "version": version if isinstance(version, str) else None,
            }
        )
    return boards
