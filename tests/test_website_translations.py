"""The Dutch, French and Spanish pages of the website say what a player sees.

The start page, the quick start, the installation and the frequently asked questions
decide whether someone tries the integration, and they were written without native
speakers (docs/decisions/0027-the-start-pages-in-dutch-french-and-spanish.md). A page
that names a button differently from the screen beside it loses that player, so these
tests hold the pages to the words of the integration and of Home Assistant, to the
style of each language and to the English pages that they translate.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
DOCS = ROOT / "docs"
INTEGRATION = ROOT / "custom_components" / "homedarts"
LANGUAGES = ("nl", "fr", "es")
PAGES = ("index", "getting-started", "installation", "faq")
NBSP = "\xa0"
CONTRIBUTING = (
    "https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/"
    "CONTRIBUTING.md#translations"
)

# The words of the menus of Home Assistant, as its frontend has them in its
# translations (hass_frontend/static/translations of Home Assistant 2026.11): the
# steps of a path such as **Settings → Dashboards**, which this test collects from the
# pages and from the last dialog of the setup.
MENU_STEPS = {
    "nl": {
        "Instellingen",
        "Systeem",
        "Apparaten en diensten",
        "Ontdekt",
        "Dashboards",
        "Voeg dashboard toe",
        "Updates",
        "HomeDarts",
    },
    "fr": {
        "Paramètres",
        "Système",
        "Appareils et services",
        "Découvertes",
        "Tableaux de bord",
        "Ajouter un tableau de bord",
        "Mises à jour",
        "HomeDarts",
    },
    "es": {
        "Configuración",
        "Sistema",
        "Dispositivos y servicios",
        "Descubierto",
        "Paneles de control",
        "Añadir panel de control",
        "Actualizaciones",
        "HomeDarts",
    },
}
# Its buttons, from the same files. HACS has no translations: its frontend comes in
# English alone, so its button is Download in every language.
BUTTONS = {
    "nl": ("Toevoegen", "Voeg kaart toe", "Herstart Home Assistant", "Download"),
    "fr": ("Ajouter", "Ajouter une carte", "Redémarrer Home Assistant", "Download"),
    "es": ("Añadir", "Añadir tarjeta", "Reiniciar Home Assistant", "Download"),
}
PATH = re.compile(r"\*\*([^*\n]*→[^*\n]*)\*\*")

# What each page quotes from the integration, with the marks it quotes it in, by the
# key of the translation file or, with card., of the file of card texts.
QUOTES = {
    "getting-started": (
        ("**{}**", "config.step.zeroconf_confirm.title"),
        ("**{}**", "config.step.user.menu_options.discover"),
        ("**{}**", "config.step.user.menu_options.local"),
        ("**{}**", "config.step.user.menu_options.manual"),
        ("*{}*", "card.view_scoreboard"),
        ("**{}**", "card.lobby_title"),
        ("**{}**", "card.lobby_start"),
    ),
    "installation": (
        ("**{}**", "config.step.zeroconf_confirm.title"),
        ("**{}**", "config.step.user.menu_options.discover"),
        ("**{}**", "config.step.user.menu_options.local"),
        ("**{}**", "config.step.user.menu_options.manual"),
    ),
    "faq": (
        ("**{}**", "config.step.user.menu_options.takeover"),
        ("*{}*", "entity.update.board_software.name"),
        ("*{}*", "issues.backup_available.title"),
        ("*{}*", "card.view_scoreboard"),
    ),
}
# The placeholders of these quotes, as the pages fill them in.
FILLED_IN = {"{game}": "501", "{board}": "…"}

# One term for one thing (CONTRIBUTING.md#translations): the pages use the words of
# these texts of the integration.
TERMS = (
    "card.heatmap",
    "card.session",
    "card.caller",
    "card.caller_voice",
    "card.idle",
    "card.idle_panel_leaderboard",
    "card.average_long",
    "card.lobby_group_party",
    "card.fullscreen",
    "card.system",
    "card.tournament_round_robin",
    "card.tournament_knockout",
    "card.tournament_double_knockout",
    "entity.calendar.training_calendar.name",
    "entity.number.training_daily_goal.name",
    "entity.sensor.weekly_report.name",
    "entity.sensor.achievements.name",
)
# Words that these pages had in place of those terms, or that no screen shows.
SLIPS = {
    "nl": (
        "trefferkaart",
        "trainingskalender",
        "takeout",
        "pc van het bord",
        "Apparaten & diensten",
    ),
    "fr": (
        "cartes des touches",
        "carte des touches",
        "séance",
        "pont en ligne",
        "ponts MQTT",
        "jeux de fête",
        "Découverts",
        "Télécharger**",
    ),
    "es": (
        "mapas de aciertos",
        "mapa de aciertos",
        "liguilla",
        "eliminatoria",
        "Ajustes →",
        "Descargar**",
    ),
}

# Words of the wrong form of address, as in tests/test_consistency.py: Dutch and
# Spanish speak to the reader informally, French formally, as Home Assistant does.
WRONG_ADDRESS = {
    "nl": r"\b(u|uw|U|Uw)\b",
    "fr": r"\b(tu|toi|ton|ta|tes|Tu|Toi|Ton|Ta|Tes)\b",
    "es": r"\b(usted|ustedes|Usted|Ustedes)\b",
}
FRONT_MATTER = re.compile(r"\A---\n(.*?)^---$", re.MULTILINE | re.DOTALL)
DESCRIPTION = re.compile(r'^description: "(.*)"$', re.MULTILINE)
# What is no sentence of the language: code, addresses, the marks of a picture and of
# a link, the attributes and icons of the website.
NO_PROSE = re.compile(
    r"`[^`\n]*`"
    r"|\]\([^)\s]*\)"
    r"|!(?=\[)"
    r"|\{[^{}\n]*\}"
    r"|:[a-z0-9-]+:"
    r"|https?://\S+"
    # The heading of an English page that a link names.
    r"|Which caller\?"
)
ENGLISH_PICTURE = re.compile(r'<img\b[^>]*\blang="en"[^>]*>')
PICTURE_TEXT = re.compile(r'<img\b[^>]*\balt="([^"]*)"[^>]*>')
TAG = re.compile(r"<[^>\n]+>")
HEADING = re.compile(r"^(#{1,6}) ", re.MULTILINE)
# A link of a page or the source of a picture.
LINK = re.compile(r"\]\(([^)\s]+)\)|\bsrc=\"([^\"]+)\"")
LANGUAGE_SUFFIX = re.compile(r"\.(de|nl|fr|es)\.md$")
OWN_ISSUE = re.compile(r"homedarts-for-autodarts/issues/\d+")
# A sentence for Assist on the start page, in the quotes of its language.
QUOTED = re.compile(rf'"([^"]+)"|«{NBSP}([^»]+?){NBSP}»')


def read(page: str) -> str:
    return (DOCS / f"{page}.md").read_text("utf-8")


def pages(language: str) -> dict[str, str]:
    return {page: read(f"{page}.{language}") for page in PAGES}


def flat(tree: dict, prefix: str = "") -> dict[str, str]:
    found: dict[str, str] = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            found.update(flat(value, f"{prefix}{key}."))
        else:
            found[f"{prefix}{key}"] = value
    return found


def integration(language: str) -> dict[str, str]:
    """The texts of the integration in a language, those of the cards with card."""
    translation = json.loads(
        (INTEGRATION / "translations" / f"{language}.json").read_text("utf-8")
    )
    cards = (INTEGRATION / "frontend" / "text" / f"{language}.js").read_text("utf-8")
    return flat(translation) | {
        f"card.{key}": json.loads(text)
        for key, text in re.findall(
            r'^\s*"(\w+)": ("(?:[^"\\]|\\.)*"),?$', cards, re.MULTILINE
        )
    }


def prose(text: str) -> str:
    """The sentences of a page, its description and the texts of its pictures among
    them, without what the website or a language of its own, such as code, brings."""
    description = FRONT_MATTER.match(text)
    assert description, "a page starts with its front matter"
    found = DESCRIPTION.search(description[1])
    assert found, "the front matter has a description"
    body = text[description.end() :]
    body = ENGLISH_PICTURE.sub("", body)
    body = PICTURE_TEXT.sub(r"\1", body)
    body = TAG.sub("", body)
    return found[1] + "\n" + NO_PROSE.sub("", body)


def targets(text: str, page: str) -> set[str]:
    """Where a page links to, in a form that is the same for each language: a page
    without the code of a language, and the anchor only where that page is English."""
    found = set()
    for markdown, html in LINK.findall(text):
        path, _, anchor = (markdown or html).partition("#")
        path = LANGUAGE_SUFFIX.sub(".md", path)
        # The English pages link to the devices and languages in the README, which
        # the start page includes; the translated start pages have them themselves.
        path = "index.md" if path == "README.md" else path
        if path in ("", f"{page}.md"):
            continue
        translated = path.removesuffix(".md") in PAGES
        found.add(path if translated or not anchor else f"{path}#{anchor}")
    return found


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_path_through_the_menus_says_what_home_assistant_says(language):
    texts = [
        *pages(language).values(),
        integration(language)["config.create_entry.default"],
    ]
    steps = {
        step
        for text in texts
        for path in PATH.findall(text)
        for step in path.split(" → ")
    }
    assert steps == MENU_STEPS[language]


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_button_says_what_home_assistant_and_hacs_say(language):
    text = "\n".join(pages(language).values())
    for button in BUTTONS[language]:
        assert f"**{button}**" in text, button


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("page", QUOTES)
def test_a_page_quotes_the_integration_word_for_word(language, page):
    texts = integration(language)
    for marks, key in QUOTES[page]:
        quote = texts[key]
        for placeholder, value in FILLED_IN.items():
            quote = quote.replace(placeholder, value)
        assert marks.format(quote) in read(f"{page}.{language}"), key


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_pages_use_the_terms_of_the_integration(language):
    text = "\n".join(pages(language).values()).lower()
    texts = integration(language)
    for key in TERMS:
        assert texts[key].lower() in text, key


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_pages_have_no_word_for_what_no_screen_shows(language):
    for page, text in pages(language).items():
        for slip in SLIPS[language]:
            assert slip.lower() not in text.lower(), f"{page}: {slip}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_integration_has_one_word_for_the_heatmap(language):
    # The heading of the card names what its switches name, and the pages follow.
    texts = integration(language)
    assert texts["card.heatmap"] == texts["card.mode"]


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("page", PAGES)
def test_a_page_keeps_the_style_of_its_language(language, page):
    text = prose(read(f"{page}.{language}"))
    assert not re.search(WRONG_ADDRESS[language], text), page
    if language == "fr":
        # A no-break space goes before : ; ? and ! and inside the quotes, as in the
        # French of Home Assistant, so that none of them starts a line.
        slips = re.findall(
            rf".{{0,20}}(?:\S[;?!]| [:;?!]|\w:|«[^{NBSP}]|[^{NBSP}]»)", text
        )
        assert not slips, slips
    if language == "es":
        assert text.count("¿") == text.count("?"), page
        assert text.count("¡") == text.count("!"), page


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_start_page_quotes_sentences_that_assist_understands(language):
    guide = read("automations").replace(NBSP, " ")
    line = next(
        line
        for line in read(f"index.{language}").splitlines()
        if "Assist" in line and "Alex" in line and "Sam" in line
    )
    sentences = [first or second for first, second in QUOTED.findall(line)]
    assert len(sentences) == 4, line
    for sentence in sentences:
        assert f'"{sentence.replace(NBSP, " ")}"' in guide, sentence


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("page", ("getting-started", "faq"))
def test_a_page_with_all_of_the_english_page_keeps_up_with_it(language, page):
    # Both have every step and every question of the English page, so a change there
    # that adds a section or a link shows here until the translation follows.
    english = read(page)
    translation = read(f"{page}.{language}")
    assert HEADING.findall(translation) == HEADING.findall(english)
    assert targets(translation, page) == targets(english, page)


@pytest.mark.parametrize("language", LANGUAGES)
def test_help_with_a_translation_leads_to_how_to_help(language):
    for page, text in pages(language).items():
        assert not OWN_ISSUE.search(text), page
    assert CONTRIBUTING in read(f"index.{language}")
