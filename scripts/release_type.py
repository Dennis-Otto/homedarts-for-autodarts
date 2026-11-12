"""Check that the type of a pull request's title fits what it changes.

The title of a pull request becomes the name of its squash commit, and its type
decides the next release: `feat`, `fix` and `perf`, and every type with a `!`,
make one that HACS offers to every installation. A release that changes nothing of
what HACS installs still costs each of them a restart of Home Assistant, and its
notes tell users about workflows, tests or pictures (#676). So such a title has to
change the package that HACS installs: the integration, the blueprints that it
ships, or `hacs.json`, which HACS reads for each release. A pull request that
changes only workflows, tests, the screenshot tool, the pictures or the
documentation is titled `ci:`, `test:`, `docs:` or `chore:` instead.

The workflow *Release type* (`.github/workflows/release-type.yml`) runs it for
each pull request, with the title in `TITLE`, the number of files that GitHub
counts in `CHANGED` and the files of the pull request on standard input, one per
line, the old name of a renamed file included:

    gh api --paginate "repos/$GH_REPO/pulls/$NUMBER/files" \
        --jq '.[] | .filename, (.previous_filename // empty)' \
        | python3 scripts/release_type.py
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterable

# The types that make a release on their own, and a `!` after any type.
TITLE = re.compile(r"^(?P<type>[a-z]+)(?:\([^()]*\))?(?P<breaking>!)?: ")
RELEASING = frozenset({"feat", "fix", "perf"})
# What HACS installs: the folder of the integration, which the archive of the
# release holds, the blueprints, which it ships, and the metadata of HACS.
SHIPPED = re.compile(r"^(?:custom_components/|blueprints/|hacs\.json$)")
# GitHub's API lists at most 3000 files of a pull request.
LISTED = 3000
# The type that fits a file outside the package, by its folder.
FITTING = (
    (re.compile(r"^tests/"), "test"),
    (re.compile(r"^(?:docs/|[^/]+\.md$|changelog\.d/)"), "docs"),
    (re.compile(r"^(?:\.github/|scripts/)"), "ci"),
)
ELSE = "chore"


def releases(title: str) -> str | None:
    """The type of the title when it makes a release, otherwise None."""
    match = TITLE.match(title)
    if not match:
        # The check of the title fails for it; nothing to say here.
        return None
    kind = match["type"]
    if kind in RELEASING or match["breaking"]:
        return kind + (match["breaking"] or "")
    return None


def fitting(files: Iterable[str]) -> list[str]:
    """The types that fit the files, in the order of FITTING."""
    found = {
        next((kind for pattern, kind in FITTING if pattern.match(name)), ELSE)
        for name in files
    }
    order = [kind for _, kind in FITTING] + [ELSE]
    return [kind for kind in order if kind in found]


def verdict(title: str, files: list[str], changed: int) -> tuple[bool, str]:
    """Whether the pull request passes, and what to tell its author."""
    kind = releases(title)
    if kind is None:
        return True, "The title makes no release on its own, so any file may change."
    if changed >= LISTED:
        return True, (
            f"The pull request changes {changed} files, more than GitHub's API lists, "
            f"so a {kind} passes unchecked."
        )
    shipped = [name for name in files if SHIPPED.match(name)]
    if shipped:
        return True, (
            f"A {kind} changes the package that HACS installs: {', '.join(shipped[:5])}"
            + (f" and {len(shipped) - 5} more." if len(shipped) > 5 else ".")
        )
    types = fitting(files)
    instead = " or ".join(f"`{name}:`" for name in types) or "`ci:`"
    return False, (
        f"The type {kind} makes a release, which HACS offers to every installation, "
        "but the pull request changes nothing of what HACS installs: "
        "custom_components/, blueprints/ or hacs.json. "
        f"Title it {instead} instead, and delete its fragment in changelog.d/, "
        "as its notes would only tell users about what they never see."
    )


def main(stdin: Iterable[str], environ: dict[str, str]) -> int:
    files = [line.strip() for line in stdin if line.strip()]
    passes, message = verdict(
        environ.get("TITLE", ""), files, int(environ.get("CHANGED") or 0)
    )
    if passes:
        print(message)
        return 0
    print(f"::error title=A release without a change of the package::{message}")
    summary = environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"{message}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.stdin, dict(os.environ)))
