"""The project goes by its own name, HomeDarts for Autodarts (decision 0026).

Up to 1.18 it was called "Autodarts for Home Assistant", the Autodarts integration.
Since 2.0, *Autodarts* names only the product and the company, so the old names of
the project stay out of every file that a user or a search engine reads.
"""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
OLD_NAMES = re.compile(r"Autodarts for Home Assistant|\b[Tt]he Autodarts integration\b")
# The places that may still say the old name, each with its reason.
ALLOWED = (
    # The released sections tell what each version was called then.
    re.compile(r"CHANGELOG\.md"),
    # The pages about the new name tell the story of the switch.
    re.compile(r"docs/new-name(\.[a-z]{2})?\.md"),
    # A record of a decision keeps the words of its day.
    re.compile(r"docs/decisions/\d{4}-.*\.md"),
    # Another project is called "Autodarts for Home Assistant": the page that
    # compares the integrations names it, and so do the notes of the issue assistant,
    # which tell it apart from this one.
    re.compile(r"docs/coming-from(\.[a-z]{2})?\.md"),
    re.compile(r"\.github/issue-assistant/project\.md"),
    # This test names what it looks for.
    re.compile(r"tests/test_names\.py"),
)


def tracked_files() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True, text=True
    ).stdout
    return [path for path in listed.split("\0") if path]


def old_names(path: str, text: str) -> list[str]:
    """The lines of a file that call the project by its old name."""
    if any(allowed.fullmatch(path) for allowed in ALLOWED):
        return []
    return [
        f"{path}:{number}: {line.strip()}"
        for number, line in enumerate(text.splitlines(), start=1)
        if OLD_NAMES.search(line)
    ]


@pytest.mark.mutation_unsafe  # asks Git
def test_no_file_calls_the_project_by_its_old_name():
    found = []
    for path in tracked_files():
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue  # a picture, or a file deleted in the working tree
        found += old_names(path, text)
    assert not found, (
        "The project is HomeDarts for Autodarts, the HomeDarts integration "
        "(docs/decisions/0026-a-name-of-its-own.md); write that instead of:\n"
        + "\n".join(found)
    )


@pytest.mark.parametrize(
    "line",
    [
        "Security fixes are provided for the latest release of the Autodarts integration.",
        '"""The Autodarts integration: local boards."""',
        "Every version of Autodarts for Home Assistant: the new games",
    ],
)
def test_an_old_name_is_found(line):
    assert old_names("SECURITY.md", line) == [f"SECURITY.md:1: {line}"]


@pytest.mark.parametrize(
    "line",
    [
        "Take over the boards of the integration Autodarts",
        "Is this an official Autodarts integration?",
        "HomeDarts for Autodarts, the HomeDarts integration",
    ],
)
def test_the_new_name_and_the_takeover_are_no_old_names(line):
    assert old_names("docs/faq.md", line) == []


def test_the_pages_about_the_old_name_may_name_it():
    line = "The integration was called Autodarts for Home Assistant."
    for path in ("CHANGELOG.md", "docs/new-name.de.md", "docs/coming-from.md"):
        assert old_names(path, line) == []
