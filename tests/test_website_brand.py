"""The brand of the documentation website, and texts that every reader can take in.

The website wears the icon, the navy and the teal of the project instead of the
defaults of Material for MkDocs: the icon in the header, the favicon, the colours and
the preview cards of shared links. Every colour of a text keeps a contrast of at
least 4.5:1 to its background (WCAG 2.2, 1.4.3), the home page shows a phone a picture
it can read, and every table names its columns, which screen readers announce.
"""

import colorsys
import itertools
import re
from pathlib import Path

import pytest
import yaml
from PIL import Image

ROOT = Path(__file__).parents[1]
DOCS = ROOT / "docs"
BRAND = DOCS / "stylesheets" / "brand.css"
DOCUMENTS = sorted(
    path for pattern in ("*.md", "docs/**/*.md") for path in ROOT.glob(pattern)
)
# What WCAG asks of normal text, which the links and the buttons are.
CONTRAST = 4.5
WHITE = "#ffffff"


class MkDocsLoader(yaml.SafeLoader):
    """The YAML of MkDocs, without what its tags such as !ENV build."""


MkDocsLoader.add_multi_constructor("!", lambda loader, suffix, node: None)
MkDocsLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/", lambda loader, suffix, node: None
)


def load(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=MkDocsLoader)


MKDOCS = load(ROOT / "mkdocs.yml")
BLUEPRINT = load(ROOT / ".github" / "mkdocs-blueprint.yml")


def rgb(color: str, background: tuple[float, ...] = (1, 1, 1)) -> tuple[float, ...]:
    """A colour such as #0f766e, or #0f766e1a over its background, as 0 to 1."""
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    alpha = int(color[7:9], 16) / 255 if len(color) == 9 else 1
    return tuple(
        alpha * value + (1 - alpha) * under
        for value, under in zip(channels, background, strict=True)
    )


def luminance(color: tuple[float, ...]) -> float:
    def linear(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(value) for value in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground: tuple[float, ...], background: tuple[float, ...]) -> float:
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def brand_variables() -> dict[str, dict[str, str]]:
    """The custom properties of brand.css in the light scheme, the dark one and the
    header of the dark one, each with those it takes over from the one before."""
    css = re.sub(r"/\*.*?\*/", "", BRAND.read_text(encoding="utf-8"), flags=re.DOTALL)
    blocks: dict[str, dict[str, str]] = {"light": {}, "dark": {}, "header": {}}
    for selector, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        scheme = "light"
        if 'data-md-color-scheme="slate"' in selector:
            scheme = "header" if ".md-header" in selector else "dark"
        blocks[scheme] |= dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+?)\s*;", body))
    dark = blocks["light"] | blocks["dark"]
    return {"light": blocks["light"], "dark": dark, "header": dark | blocks["header"]}


VARIABLES = brand_variables()


def page_background(scheme: str) -> str:
    """The background of the pages: white, or Material's slate grey in its hue."""
    if scheme == "light":
        return WHITE
    hue = float(VARIABLES[scheme]["--md-hue"])
    red, green, blue = colorsys.hls_to_rgb(hue / 360, 0.14, 0.15)
    return "#" + "".join(f"{round(value * 255):02x}" for value in (red, green, blue))


# What a reader sees in which colour, on which background: a custom property of
# brand.css, or the background of the page.
PAIRS = [
    (scheme, what, foreground, background)
    for scheme in ("light", "dark")
    for what, foreground, background in (
        ("links", "--md-typeset-a-color", "page"),
        ("a link under the pointer", "--md-accent-fg-color", "page"),
        ("a button", "--md-primary-fg-color", "page"),
        ("the primary button", "--md-primary-bg-color", "--md-primary-fg-color"),
        ("a button under the pointer", "--md-accent-bg-color", "--md-accent-fg-color"),
    )
] + [("header", "the header", "--md-primary-bg-color", "--md-primary-fg-color")]


@pytest.mark.parametrize(
    ("scheme", "what", "foreground", "background"),
    PAIRS,
    ids=[f"{scheme}: {what}" for scheme, what, _, _ in PAIRS],
)
def test_every_colour_of_a_text_can_be_read(scheme, what, foreground, background):
    variables = VARIABLES[scheme]
    under = rgb(
        page_background(scheme) if background == "page" else variables[background]
    )
    ratio = contrast(rgb(variables[foreground], under), under)
    assert ratio >= CONTRAST, f"{scheme}, {what}: {ratio:.2f}:1"


def test_the_header_of_the_dark_scheme_stays_navy():
    assert VARIABLES["header"]["--md-primary-fg-color"] == "#0a1624"
    assert VARIABLES["light"]["--md-primary-fg-color"] == "#0a1624"


def test_a_colour_with_too_little_contrast_is_found():
    assert contrast(rgb("#4fd1c5"), rgb(WHITE)) < CONTRAST
    assert round(contrast(rgb("#0f766e"), rgb(WHITE)), 2) == 5.47
    # A colour that lets the background shine through is mixed with it first.
    assert rgb("#00000000") == (1, 1, 1)


def test_the_header_shows_the_icon_and_the_tab_the_favicon():
    theme = MKDOCS["theme"]
    assert theme["logo"] == "branding/icon.svg"
    assert (DOCS / theme["logo"]).is_file()
    with Image.open(DOCS / theme["favicon"]) as favicon:
        assert favicon.format == "PNG"
        assert favicon.size == (48, 48)
        # pngquant (docs/branding/README.md) turns it into a palette PNG: what
        # matters is the transparent corner, not the encoding.
        assert favicon.convert("RGBA").getchannel("A").getpixel((0, 0)) == 0


def test_home_assistant_shows_the_icon_of_the_integration_and_no_other():
    """Autodarts asked for its logo to be removed: the brand folder holds only the
    icon rendered from docs/branding/icon.svg, which Home Assistant also shows in
    place of a logo."""
    brand = ROOT / "custom_components" / "homedarts" / "brand"
    assert sorted(path.name for path in brand.iterdir()) == ["icon.png", "icon@2x.png"]
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        with Image.open(brand / name) as image:
            assert image.format == "PNG"
            assert image.size == (size, size)
            assert image.convert("RGBA").getchannel("A").getpixel((0, 0)) == 0
    assert sorted(path.name for path in (DOCS / "branding").glob("*.svg")) == [
        "icon.svg"
    ]
    assert "LicenseRef-Autodarts" not in (ROOT / "REUSE.toml").read_text(
        encoding="utf-8"
    )


def test_the_colours_keep_the_switch_between_light_and_dark():
    """mkdocs.yml replaces the palette of the blueprint, which a list can't merge
    with: it has the same schemes and switches, in the colours of the brand."""
    palette = MKDOCS["theme"]["palette"]
    assert [
        {key: value for key, value in entry.items() if key not in ("primary", "accent")}
        for entry in palette
    ] == BLUEPRINT["theme"]["palette"]
    assert all(entry["primary"] == entry["accent"] == "custom" for entry in palette)
    assert MKDOCS["extra_css"][0] == "stylesheets/brand.css"
    assert all((DOCS / sheet).is_file() for sheet in MKDOCS["extra_css"])


def test_the_preview_cards_of_shared_links_wear_the_brand():
    layout = MKDOCS["plugins"]["social"]["cards_layout_options"]
    assert layout["background_color"] == VARIABLES["light"]["--md-primary-fg-color"]
    assert contrast(rgb(layout["color"]), rgb(layout["background_color"])) >= CONTRAST


def test_the_footer_says_the_website_is_unofficial_in_both_languages():
    german = next(
        language
        for language in MKDOCS["plugins"]["i18n"]["languages"]
        if language["locale"] == "de"
    )
    assert "not affiliated with Autodarts" in MKDOCS["copyright"]
    assert "nicht mit Autodarts verbunden" in german["copyright"]


@pytest.mark.parametrize("language", ["en", "de"])
def test_a_phone_gets_a_hero_picture_it_can_read(language):
    """The wide picture of the two cards side by side would be about 340 pixels
    wide on a phone; a phone gets the cards one below the other instead."""
    page = DOCS / ("index.md" if language == "en" else "index.de.md")
    text = page.read_text(encoding="utf-8")
    assert (
        f'<source media="(max-width: 600px)" srcset="images/{language}/hero-mobile.webp">'
        in text
    )
    # The lightbox would wrap the picture in a link, inside <picture>, and the
    # browser would ignore the source for the phone: off-glb keeps it away.
    assert f'<img class="off-glb" src="images/{language}/hero.webp"' in text
    with Image.open(DOCS / "images" / language / "hero-mobile.webp") as picture:
        # Sharp on a screen of twice the density, and taller than wide.
        assert 2 * 280 <= picture.width < picture.height


def table_headers(text: str) -> list[list[str]]:
    """The cells of the header row of every Markdown table outside code blocks."""
    text = re.sub(r"^(```|~~~).*?^\1", "", text, flags=re.MULTILINE | re.DOTALL)
    lines = text.splitlines()
    return [
        [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        for line, below in itertools.pairwise(lines)
        if line.lstrip().startswith("|")
        and re.fullmatch(r"\s*\|?(\s*:?-{3,}:?\s*\|)+\s*(:?-{3,}:?\s*)?", below)
    ]


def test_an_empty_header_cell_is_found():
    table = (
        "| | Value |\n| --- | ---: |\n| a | 1 |\n\n```\n| | x |\n| --- | --- |\n```\n"
    )
    assert table_headers(table) == [["", "Value"]]


@pytest.mark.parametrize(
    "document", DOCUMENTS, ids=lambda path: path.relative_to(ROOT).as_posix()
)
def test_every_table_names_its_columns(document):
    empty = [
        " | ".join(cells)
        for cells in table_headers(document.read_text(encoding="utf-8"))
        if not all(cells)
    ]
    assert not empty, f"{document.relative_to(ROOT)}: a header without a name: {empty}"
