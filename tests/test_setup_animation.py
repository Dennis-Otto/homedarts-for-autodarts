"""The animation of the quick start shows how little setup it takes: it comes from the
screenshot tool alone, stays small, reads on a phone and describes every step."""

import re
from pathlib import Path

import pytest
from PIL import Image, ImageSequence

ROOT = Path(__file__).parents[1]
DOCS = ROOT / "docs"
TOOL = ROOT / "tests" / "e2e" / "screenshots.py"
LIMIT = 1_500_000
# What a phone shows it on: about 390 points wide, at twice that many pixels at least.
PHONE = 2 * 390
PICTURE = re.compile(r'<img src="([^"]*/setup\.webp)" alt="([^"]*)" width="100%">')
# The address that the README needs, for HACS, in place of a relative path.
RAW = "https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/"
# The pages with the picture of their language, and the words of the steps in its text
# where the page quotes Home Assistant in that language.
PAGES = {
    "README.md": (
        "en",
        ("Discovered", "Add", "Submit", "Settings", "HomeDarts", "scoreboard"),
    ),
    "docs/getting-started.md": (
        "en",
        ("Discovered", "Add", "Submit", "Settings", "HomeDarts", "scoreboard"),
    ),
    "docs/README.de.md": (
        "de",
        ("Entdeckt", "Hinzufügen", "OK", "Einstellungen", "HomeDarts", "Anzeigetafel"),
    ),
    "docs/getting-started.de.md": (
        "de",
        ("Entdeckt", "Hinzufügen", "OK", "Einstellungen", "HomeDarts", "Anzeigetafel"),
    ),
    "docs/getting-started.nl.md": ("en", ("Ontdekt", "HomeDarts", "scorebord")),
    "docs/getting-started.fr.md": ("en", ("Découvertes", "HomeDarts", "tableau des")),
    "docs/getting-started.es.md": ("en", ("Descubierto", "HomeDarts", "marcador")),
}
LANGUAGES = ("en", "de")


def durations(path: Path) -> list[int]:
    """How long each frame of an animation shows, in milliseconds."""
    shown = []
    with Image.open(path) as animation:
        for frame in ImageSequence.Iterator(animation):
            # The WebP plugin sets the duration of a frame only once it is loaded.
            frame.load()
            shown.append(int(frame.info["duration"]))
    return shown


def test_the_screenshot_tool_makes_the_animation():
    # Never a picture made by hand: the screenshot bot renders it like the others.
    assert 'recorder.save("setup", width=SETUP_WIDTH)' in TOOL.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_animation_stays_small(language):
    assert (DOCS / "images" / language / "setup.webp").stat().st_size <= LIMIT


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_animation_reads_on_a_phone_and_fits_a_big_screen(language):
    with Image.open(DOCS / "images" / language / "setup.webp") as picture:
        assert picture.is_animated
        assert picture.width >= PHONE
        # Across the column of a README, it still fits on a screen.
        assert picture.height <= 1.2 * picture.width


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_animation_takes_the_real_time_of_the_setup(language):
    # A hand on a phone, not a fast-forward; its last caption says under a minute.
    total = sum(durations(DOCS / "images" / language / "setup.webp"))
    assert 25_000 <= total < 60_000


@pytest.mark.parametrize("page", PAGES)
def test_the_pages_of_the_setup_show_the_animation_with_every_step(page):
    language, words = PAGES[page]
    (found,) = PICTURE.findall((ROOT / page).read_text(encoding="utf-8"))
    source, alt = found
    assert source.removeprefix(RAW).removeprefix("docs/") == (
        f"images/{language}/setup.webp"
    )
    # The French of a page has a no-break space before its colon.
    assert re.findall(r"\b([1-5])\s?:", alt) == list("12345")
    assert [word for word in words if word not in alt] == []
