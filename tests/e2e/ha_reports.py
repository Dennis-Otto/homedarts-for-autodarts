"""Home Assistant's reports about the integration: what a coming release stops.

Home Assistant warns in the logs of its own modules, not in that of the integration,
when a custom integration uses what a coming release removes or blocks the event loop:

- the frame helper: "Detected that custom integration 'homedarts' accesses ... This
  will stop working in Home Assistant 2027.1, please create a bug report at ...";
- the loop protection: "Detected blocking call to open with args ... inside the
  event loop by custom integration 'homedarts' at ..., please create a bug report
  at ...";
- a deprecated constant, function or class: "The deprecated function foo was called
  from homedarts. It will be removed in HA Core 2027.1. Use bar instead, please
  create a bug report at ...".

Each of them, and every other warning that asks the user to report a problem of a
custom integration, such as an entity with a state class that its device class
doesn't allow, names the integration in the same words: the issue tracker of its
manifest, or "the author of the 'homedarts' custom integration" without one. The
tests (``tests/conftest.py``) and the end-to-end scenario (``scenario.py``) fail on
each, so the nightly run against the beta of Home Assistant finds what its next
release stops before the users find it in their logs.

The scenario runs in the container of Home Assistant, which mounts this folder alone,
so this module needs nothing but the standard library.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


def release(version: str) -> tuple[int, int]:
    """The year and month of a release of Home Assistant, such as (2026, 11) for
    its beta 2026.11.0b2."""
    year, month = version.split(".")[:2]
    return int(year), int(month)


@dataclass(frozen=True)
class Known:
    """A report that the tests accept for a while: a part of its message, why the
    integration can't follow it yet, and the release of Home Assistant from which
    it fails the tests again, such as the one that stops what it reports. The
    nightly run against the beta reaches that release first."""

    text: str
    reason: str
    until: str

    def __post_init__(self) -> None:
        if not self.text or not self.reason:
            raise ValueError(f"A known report needs its text and its reason: {self}")
        release(self.until)

    def covers(self, message: str, version: str) -> bool:
        return self.text in message and release(version) < release(self.until)


# The reports of Home Assistant that the tests accept for now, each with its reason and
# the release it expires with: none.
KNOWN: tuple[Known, ...] = ()


def pattern(manifest: Mapping[str, Any]) -> re.Pattern[str]:
    """How Home Assistant names the integration of the manifest in a report.

    "We found a custom integration homedarts which has not been tested", which the
    loader writes at every start, names it without quotes and is no report.
    """
    domain = re.escape(manifest["domain"])
    tracker = re.escape(manifest["issue_tracker"])
    return re.compile(
        rf"custom integration '{domain}'|'{domain}' custom integration"
        rf"|create a bug report at {tracker}(?=[\s.,;)]|$)"
    )


def reports(
    messages: Iterable[str],
    manifest: Mapping[str, Any],
    version: str,
    known: Iterable[Known] = KNOWN,
) -> list[str]:
    """The messages that report the integration to its author, apart from the known
    reports that Home Assistant of ``version`` doesn't stop yet."""
    found = pattern(manifest)
    accepted = tuple(known)
    return [
        message
        for message in messages
        if found.search(message)
        and not any(entry.covers(message, version) for entry in accepted)
    ]
