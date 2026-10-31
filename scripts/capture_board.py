"""Record what a real Board Manager answers, for tests/fixtures/board_manager.

The unit tests and the Docker end-to-end test answer like the recordings in
tests/fixtures/board_manager, and tests/test_board_contract.py holds both to them.
This script makes such a recording of a board in your network:

    python scripts/capture_board.py 192.168.1.50
    python scripts/capture_board.py dartboard.local --seconds 120
    python scripts/capture_board.py 192.168.1.50 --frames 40 --out /tmp/boards

It reads every route of the Board Manager that the integration reads and records
the frames of its socket for a while: start the detection, throw a few darts and
take them out meanwhile. It writes them to tests/fixtures/board_manager/<version>/,
one file per route, the frames in ws-frames.jsonl and what it recorded in
capture.json. A route the board doesn't have is listed there as absent.

The answers carry the board's ID and API key, its TLS key, the serial numbers of
its cameras and the name and addresses of the board PC. They are replaced by the
placeholders of PLACEHOLDERS before anything is written, in whatever spelling the
board writes their keys (boardId, board_id). So is every value of a key that names a
secret or the ID or name of a board, an account or a person, also a key that a later
Board Manager adds, and under any key every UUID, e-mail address, MAC address, IPv6
address, private IPv4 address and "serial=" of a camera. The script writes nothing if
one of them is left. The port of a camera ("location=") stays: it is the same on
every PC of that model and keeps cameras of one model apart. Look through the files
all the same before you share them.

It needs Python 3.13 or newer and aiohttp (`pip install aiohttp`), which the test
environment of requirements-test.txt has.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple

import aiohttp

ROOT = Path(__file__).parents[1]
RECORDINGS = ROOT / "tests" / "fixtures" / "board_manager"
PORT = 3180
SECONDS = 60
# The routes the integration reads, by the file that keeps the answer.
ROUTES = {
    "state.json": "/api/state",
    "config.json": "/api/config",
    "version.txt": "/api/version",
    "state-stats.json": "/api/state/stats",
    "state-motion.json": "/api/state/motion",
    "cams-stats.json": "/api/cams/stats",
    "cams-state.json": "/api/cams/state",
    "system.json": "/api/system",
    "host.json": "/api/host",
}
EVENTS = "/api/events"
REQUEST = aiohttp.ClientTimeout(total=10)
FRAMES = "ws-frames.jsonl"
CAPTURE = "capture.json"
# What a recording says in place of the identity and the secrets of a board.
PLACEHOLDERS = {
    "board_id": "board-1",
    "api_key": "private-board-api-key",
    "tls_key": "private-tls-key",
    "tls_cert": "private-tls-cert",
    "hostname": "dartboard-pc",
    "ip": "198.51.100.7",
    "ipv6": "2001:db8::7",
    "uuid": "private-uuid",
    "serial": "SN0001",
    "email": "player@example.com",
    "mac": "00:00:5e:00:53:07",
}
# SECRET and IDENTITY read a key as spelling() writes it, so that "apiKey", "api_key"
# and "API-KEY" are one key, and find keys that a later Board Manager adds as well.
# A key whose value is a secret.
SECRET = re.compile(
    r"token|secret|passw|passphrase|credential|apikey|privatekey"
    r"|(?:key|cert|certificate|pwd)$"
)
# A key whose value identifies a person or a device: the ID or the name of something
# that belongs to one, such as "boardId", and what stands for itself, such as "email".
# It takes the words before "id" and "name", because these alone say nothing: every
# camera and every throw has an "id", every camera model a "name".
IDENTITY = re.compile(
    r"(?:board|account|user|owner|customer|tenant|player|member|person|device|machine"
    r"|computer|hardware|installation|instance|session|linkserver|network|wifi)s?"
    r"(?:id|name)s?$"
    r"|(?:display|nick|full|first|last|sur|real)name$"
    r"|(?:uuid|guid|hostname|serial(?:number|no)?|e?mail(?:address)?|mac(?:address)?"
    r"|b?ssid|streamingto)s?$"
    r"|(?:^|local|public|lan|wan|host|remote)ip(?:v[46])?(?:address)?s?$"
)
# The keys that say nothing without the key above them: the "name" of "linkServer".
VAGUE = ("id", "name")
# A smaller number at such a key is an index, such as the camera of a "deviceId".
SMALLEST_ID = 100
# Shorter values are replaced only at their keys, not wherever they appear, so that
# a short ID can't change numbers or names that happen to contain it.
SHORTEST_SECRET = 6
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
# Everything that may be one; private() tells a time and a C++ name from an address.
IPV6 = re.compile(
    r"(?<![0-9A-Za-z:.])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![0-9A-Za-z:.])"
)
# The addresses for documentation (RFC 5737, RFC 3849), such as the placeholders, may
# stay.
DOCUMENTATION = tuple(
    ipaddress.ip_network(network)
    for network in (
        "192.0.2.0/24",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "2001:db8::/32",
    )
)
UUID = re.compile(
    r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}(?![0-9A-Fa-f])"
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
MAC = re.compile(
    r"(?<![0-9A-Fa-f:-])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f:-])"
)
# The serial number in the description of a camera, such as
# "vid=1dfc&pid=8513&serial=SN0001&location=pci-0000:00:14.0-usb-0:3:1.0".
SERIAL = re.compile(
    r"(?i:(?<=serial=)|(?<=serialnumber=)|(?<=serial_number=))[^&,;\s\"'\\]+"
)
# Board Manager versions as they name a folder of recordings.
VERSION = re.compile(r"v?(\d{1,4}(?:\.\d{1,6}){0,3}(?:-[0-9A-Za-z.]{1,32})?)")


def spelling(key: str) -> str:
    """A key without its spelling: "boardId", "board_id" and "BOARD-ID" are one key."""
    return re.sub(r"[\W_]+", "", key).casefold()


SPELLED = {spelling(key): value for key, value in PLACEHOLDERS.items()}


def placeholder(key: str) -> str:
    """The placeholder of a secret, by the key that holds it."""
    return SPELLED.get(spelling(key), f"private-{key}")


def identifies(key: str) -> bool:
    return spelling(key) in SPELLED or bool(IDENTITY.search(spelling(key)))


def is_secret(key: str) -> bool:
    return identifies(key) or bool(SECRET.search(spelling(key)))


def is_placeholder(value: str) -> bool:
    """A value that a recording already says in place of a secret."""
    return value in PLACEHOLDERS.values() or value.startswith("private-")


def below(parent: str, key: str) -> str:
    """The key that judges a value: the one above it where that is a secret or where
    the key says nothing by itself, such as the "name" of "linkServer"."""
    if is_secret(parent):
        return parent
    return f"{parent}-{key}" if parent and spelling(key) in VAGUE else key


def secret_at(key: str, value: object) -> str:
    """The value as a text if its key makes it a secret, and nothing otherwise."""
    if isinstance(value, str):
        return value if is_secret(key) else ""
    if type(value) is int and value >= SMALLEST_ID and identifies(key):
        return str(value)
    return ""


def secrets(answers: object, host: str = "") -> dict[str, str]:
    """The secrets of the answers, each with its placeholder, and the address that
    reached the board."""
    found: dict[str, str] = {}

    def walk(value: object, key: str = "") -> None:
        if isinstance(value, dict):
            for name, item in value.items():
                walk(item, below(key, name))
        elif isinstance(value, list):
            for item in value:
                walk(item, key)
        elif (secret := secret_at(key, value)) and not is_placeholder(secret):
            found.setdefault(secret, placeholder(key))
        elif isinstance(value, str):
            # The serial number of a camera may stand in other texts as well. A short
            # one goes only where SERIAL finds it, as a short "pid" of a camera can
            # be the same text.
            for serial in SERIAL.findall(value):
                if len(serial) >= SHORTEST_SECRET and not is_placeholder(serial):
                    found.setdefault(serial, PLACEHOLDERS["serial"])

    walk(answers)
    if host and not is_placeholder(host):
        found.setdefault(host, PLACEHOLDERS["ip" if is_ip(host) else "hostname"])
    return found


def is_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return False
    return True


def private(address: str) -> bool:
    """An address of a home network, which a recording must not keep: a private IPv4
    address and every IPv6 address a board PC can have, because even a global one
    names its home network."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if any(ip in net for net in DOCUMENTATION):
        return False
    if ip.version == 6:
        return not (ip.is_reserved or ip.is_multicast)
    return ip.is_private and not (ip.is_loopback or ip.is_unspecified)


def anything(_: str) -> bool:
    return True


class Identifying(NamedTuple):
    """What identifies a device or a person under any key."""

    what: str
    pattern: re.Pattern[str]
    replacement: str
    applies: Callable[[str], bool] = anything

    def replace(self, text: str) -> str:
        return self.pattern.sub(
            lambda match: (
                self.replacement if self.applies(match.group()) else match.group()
            ),
            text,
        )

    def is_left_in(self, text: str) -> bool:
        return any(
            self.applies(match) and match != self.replacement
            for match in self.pattern.findall(text)
        )


IDENTIFYING = (
    Identifying("a private IPv4 address", IPV4, PLACEHOLDERS["ip"], private),
    Identifying("an IPv6 address", IPV6, PLACEHOLDERS["ipv6"], private),
    Identifying("a UUID", UUID, PLACEHOLDERS["uuid"]),
    Identifying("an e-mail address", EMAIL, PLACEHOLDERS["email"]),
    Identifying("a MAC address", MAC, PLACEHOLDERS["mac"]),
    Identifying("a serial number", SERIAL, PLACEHOLDERS["serial"]),
)


def redact(value: Any, found: dict[str, str]) -> Any:
    """The value with every secret, at its key or anywhere in a text, and everything
    of IDENTIFYING replaced by its placeholder."""
    # One pass over the text, longest secret first, so that a placeholder just
    # written is never searched again: "dartboard" stays inside "dartboard-pc".
    anywhere = alternation(secret for secret in found if len(secret) >= SHORTEST_SECRET)

    def text(item: str) -> str:
        if item in found:
            return found[item]
        item = anywhere.sub(lambda match: found[match.group()], item)
        for identifying in IDENTIFYING:
            item = identifying.replace(item)
        return item

    def walk(item: Any, key: str = "") -> Any:
        if isinstance(item, dict):
            return {
                text(name): walk(entry, below(key, name))
                for name, entry in item.items()
            }
        if isinstance(item, list):
            return [walk(entry, key) for entry in item]
        if secret_at(key, item):
            return placeholder(key)
        return text(item) if isinstance(item, str) else item

    return walk(value)


def alternation(texts: Iterable[str]) -> re.Pattern[str]:
    """A pattern that finds any of the texts, the longest where several start, and
    nothing without texts. Digits alone count only as a number of their own: the
    serial number "000000" is not in the 1.0000000000000002 of a calibration."""
    unique = sorted(set(texts), key=lambda item: (-len(item), item))
    return re.compile(
        "|".join(
            rf"(?<![\d.]){item}(?![\d.])" if item.isdigit() else re.escape(item)
            for item in unique
        )
        or "(?!)"
    )


def leftovers(content: str, found: dict[str, str]) -> list[str]:
    """What a file to be written still holds of the secrets, by their placeholders."""
    # Each secret as written in a text, and as JSON writes it, such as a key of
    # several lines.
    written = {
        form: replacement
        for secret, replacement in found.items()
        if len(secret) >= SHORTEST_SECRET
        for form in (secret, json.dumps(secret, ensure_ascii=False)[1:-1])
    }
    # The placeholders are searched along with the secrets, longest first, so that
    # a secret inside a placeholder, such as "dartboard" in "dartboard-pc", doesn't
    # count as left.
    allowed = set(PLACEHOLDERS.values()) | set(found.values())
    search = alternation([*written, *allowed])
    left = {
        written[match]
        for match in search.findall(content)
        if match in written and match not in allowed
    }
    left.update(item.what for item in IDENTIFYING if item.is_left_in(content))
    return sorted(left)


def folder_name(version: object) -> str:
    """The folder of a recording: the Board Manager version without its v."""
    match = VERSION.fullmatch(version.strip()) if isinstance(version, str) else None
    if match is None:
        raise SystemExit(f"The board answers no version on /api/version: {version!r}")
    return match.group(1)


def files(
    answers: dict[str, Any],
    frames: Sequence[Any],
    absent: Sequence[str],
    host: str,
    captured: str | None,
) -> tuple[str, dict[str, str]]:
    """The folder and the redacted files of a recording, by their names."""
    version = folder_name(answers.get("version.txt"))
    found = secrets(answers, host) | secrets(list(frames))
    content = {}
    for name, answer in redact(answers, found).items():
        content[name] = (
            f"{answer.strip()}\n"
            if name.endswith(".txt")
            else json.dumps(answer, indent=2, ensure_ascii=False) + "\n"
        )
    content[FRAMES] = "".join(
        json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\n"
        for frame in redact(list(frames), found)
    )
    summary = {
        "board_manager": version,
        "captured": captured,
        "source": "scripts/capture_board.py",
        "absent": list(absent),
    }
    content[CAPTURE] = json.dumps(summary, indent=2) + "\n"
    left = sorted(
        {item for text in content.values() for item in leftovers(text, found)}
    )
    if left:
        raise SystemExit(
            f"Nothing written: the recording still holds {', '.join(left)}."
        )
    return version, content


def write(out: Path, version: str, content: dict[str, str]) -> Path:
    """Write a recording; files of an earlier recording that this one lacks go."""
    folder = out / version
    folder.mkdir(parents=True, exist_ok=True)
    for name in (*ROUTES, FRAMES, CAPTURE):
        if name not in content:
            (folder / name).unlink(missing_ok=True)
    for name, text in content.items():
        (folder / name).write_text(text, encoding="utf-8", newline="\n")
    return folder


def base_url(host: str, port: int) -> str:
    """The address of the Board Manager, an IPv6 address in brackets."""
    return f"http://[{host}]:{port}" if ":" in host else f"http://{host}:{port}"


async def read_routes(
    session: aiohttp.ClientSession, base: str
) -> tuple[dict[str, Any], list[str]]:
    """The answer of every route, and the routes the board doesn't have."""
    answers: dict[str, Any] = {}
    absent = []
    for name, path in ROUTES.items():
        async with session.get(f"{base}{path}", timeout=REQUEST) as response:
            if response.status in (404, 405):
                absent.append(path)
                continue
            response.raise_for_status()
            text = await response.text()
            answers[name] = text if name.endswith(".txt") else json.loads(text)
    return answers, absent


async def read_frames(
    session: aiohttp.ClientSession,
    base: str,
    seconds: float,
    limit: int | None = None,
    connected: Callable[[], None] = lambda: None,
) -> tuple[list[Any], int]:
    """The frames of the socket for some seconds or up to a number of them, and
    how many were no JSON."""
    frames: list[Any] = []
    skipped = 0
    async with asyncio.timeout(10):
        socket = await session.ws_connect(
            f"{base}{EVENTS}", timeout=aiohttp.ClientWSTimeout(ws_close=5)
        )
    async with socket:
        connected()
        try:
            async with asyncio.timeout(seconds):
                async for message in socket:
                    if message.type != aiohttp.WSMsgType.TEXT:
                        continue
                    try:
                        frames.append(json.loads(message.data))
                    except ValueError:
                        skipped += 1
                    if limit is not None and len(frames) >= limit:
                        break
        except TimeoutError:
            pass
    return frames, skipped


async def capture(
    host: str,
    port: int = PORT,
    seconds: float = SECONDS,
    out: Path = RECORDINGS,
    limit: int | None = None,
    connected: Callable[[], None] = lambda: None,
) -> Path:
    """Record a board and write the recording; the folder it went to."""
    base = base_url(host, port)
    # No limit for the session, whose socket stays open while it records.
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout()) as session:
        answers, absent = await read_routes(session, base)
        frames, skipped = await read_frames(session, base, seconds, limit, connected)
    if skipped:
        print(f"Skipped {skipped} frames that were no JSON.", file=sys.stderr)
    version, content = files(answers, frames, absent, host, date.today().isoformat())
    return write(out, version, content)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record what a Board Manager answers, without its secrets."
    )
    parser.add_argument("host", help="the address or name of the board PC")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument(
        "--seconds",
        type=float,
        default=SECONDS,
        help="how long to record the socket (default: %(default)s)",
    )
    parser.add_argument(
        "--frames",
        type=int,
        help="stop after this many frames of the socket",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=RECORDINGS,
        help="the folder of the recordings (default: tests/fixtures/board_manager)",
    )
    arguments = parser.parse_args(argv)

    def connected() -> None:
        print(
            f"Recording the socket for {arguments.seconds:g} s: start the detection, "
            "throw a few darts and take them out.",
            file=sys.stderr,
        )

    try:
        folder = asyncio.run(
            capture(
                arguments.host,
                arguments.port,
                arguments.seconds,
                arguments.out,
                arguments.frames,
                connected,
            )
        )
    except (aiohttp.ClientError, TimeoutError, ValueError) as error:
        print(f"The board did not answer as expected: {error!r}", file=sys.stderr)
        return 1
    print(f"Wrote {folder}. Look through the files before you share them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
