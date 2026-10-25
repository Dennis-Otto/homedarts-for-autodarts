"""How long each group of the screenshot tool took, as a table for the summary of the
job that puts the groups of a language together.

Every run of screenshots.py writes the seconds of its sections to
screenshots-<language>-<group>.json among the artifacts, and the render jobs of
visual.yml and screenshots.yml keep it as the artifact times-<language>-<group>.
The table lists every group with its sections and seconds, and flags a group that took more
than SLOWER times as long as the shortest one: the runs of a language wait for their
slowest group, so a section of it moves to a shorter one (GROUPS in screenshots.py).

    python3 tests/e2e/group_times.py en tests/e2e/artifacts >> "$GITHUB_STEP_SUMMARY"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# A group that takes more than this times the seconds of the shortest is flagged.
SLOWER = 1.5


def slow(totals: dict[int, float]) -> dict[int, float]:
    """The groups that took more than SLOWER times as long as the shortest, each with
    how many times as long."""
    if not totals:
        return {}
    shortest = min(totals.values())
    return {
        group: seconds / shortest
        for group, seconds in totals.items()
        if seconds > SLOWER * shortest
    }


def times(language: str, folder: Path) -> tuple[int, dict[int, dict]]:
    """The number of groups and the times of each group that rendered, from the
    files of screenshots.py: in the folder itself, as screenshots.sh leaves them,
    or in a folder for each group's artifact, as the jobs download them."""
    found: dict[int, dict] = {}
    count = 0
    for path in sorted(
        [
            *folder.glob(f"screenshots-{language}-*.json"),
            *folder.glob(f"*/screenshots-{language}-*.json"),
        ]
    ):
        data = json.loads(path.read_text(encoding="utf-8"))
        found[data["group"]] = data
        count = max(count, data["groups"])
    return count, found


def table(language: str, folder: Path) -> str:
    """The table of the groups of a language, in Markdown."""
    count, found = times(language, folder)
    title = f"### Screenshots: the groups ({language})\n\n"
    if not found:
        return title + "No group of this language left its times.\n"
    totals = {
        group: sum(seconds for _, seconds in data["sections"])
        for group, data in found.items()
    }
    flagged = slow(totals)
    shortest = min(totals.values())
    lines = [
        "| Group | Sections | Seconds | Against the shortest |",
        "| --- | --- | ---: | --- |",
    ]
    for group in range(1, count + 1):
        if group not in found:
            lines.append(
                f"| {group}/{count} | – | – | no times: the group failed or took its images from an earlier run |"
            )
            continue
        names = ", ".join(name for name, _ in found[group]["sections"])
        ratio = totals[group] / shortest
        flag = f"⚠️ {ratio:.2f} ×" if group in flagged else f"{ratio:.2f} ×"
        lines.append(f"| {group}/{count} | {names} | {totals[group]:.1f} | {flag} |")
    text = title + "\n".join(lines) + "\n"
    if flagged:
        text += (
            f"\nA group marked ⚠️ took more than {SLOWER} times as long as the"
            " shortest one, and every run of this language waits for it. Move one of"
            " its sections to a shorter group in `GROUPS` of"
            " `tests/e2e/screenshots.py`, keeping the sections that depend on each"
            " other together and in their order"
            " ([Groups side by side](https://dennis-otto.github.io/homedarts-for-autodarts/development.html#groups-side-by-side)).\n"
        )
    return text


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        print(
            "Usage: group_times.py <language> <folder>, such as"
            " group_times.py en tests/e2e/artifacts",
            file=sys.stderr,
        )
        return 2
    language, folder = arguments
    # The summary of a job is UTF-8, also where the console of the machine isn't.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(table(language, Path(folder)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
