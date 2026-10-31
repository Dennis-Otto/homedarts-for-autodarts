"""Translations, action descriptions, icons and card texts agree with the code,
tool versions kept in two places agree with each other, and pull requests run the
end-to-end tests for every file that they use."""

import ast
import importlib.util
import json
import os
import re
import shlex
import tomllib
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from custom_components.homedarts.achievements import ACHIEVEMENTS
from custom_components.homedarts.binary_sensor import MOTION_SENSORS
from custom_components.homedarts.calls import DECIMAL_MARKS
from custom_components.homedarts.const import LANGUAGES as INTEGRATION_LANGUAGES
from custom_components.homedarts.drills import DRILLS
from custom_components.homedarts.journal import LOCALES
from custom_components.homedarts.local_api import STANDBY_MINUTES
from custom_components.homedarts.local_coordinator import EVENT_TYPES, ISSUES
from custom_components.homedarts.media_source import (
    CHECKOUTS,
    MONTH_TITLES,
    MONTHS,
    SHORT_DATES,
)
from custom_components.homedarts.practice import (
    GAME_OPTIONS,
    MAX_LEGS,
    MAX_PLAYERS,
    MAX_SETS,
)
from custom_components.homedarts.sensor import LOCAL_STATES
from custom_components.homedarts.services import (
    DELETE_PLAYER_SCHEMA,
    START_GAME_SCHEMA,
)
from custom_components.homedarts.tournament import NAMED_STAGES

from .local_helpers import entity_id, setup_local

INTEGRATION = Path(__file__).parents[1] / "custom_components" / "homedarts"
STRINGS = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
# Every translation file counts, so a new language joins every check below.
TRANSLATIONS = {
    path.stem: json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((INTEGRATION / "translations").glob("*.json"))
}
LANGUAGES = sorted(TRANSLATIONS)
# What brings the files in step with strings.json, as far as a command can; the fix
# bot runs it when a check fails.
SYNC = (
    "python scripts/sync_translations.py copies strings.json to en.json, puts the "
    "texts of each language in its order and names each text that a language misses"
)
SERVICES = yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8"))
ICONS = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))
SOURCES = "\n".join(
    path.read_text(encoding="utf-8") for path in sorted(INTEGRATION.glob("*.py"))
)
CARD = (INTEGRATION / "frontend" / "homedarts-card.js").read_text(encoding="utf-8")
# The texts of the cards, a module per language, which the card module imports.
CARD_TEXT_FILES = INTEGRATION / "frontend" / "text"
# Entities whose device class brings the icon.
DEVICE_CLASS_ICONS = {
    ("binary_sensor", "camera_problem"),
    ("binary_sensor", "individual_camera_problem"),
    ("binary_sensor", "granboard_connected"),
    ("binary_sensor", "local_connected"),
    ("button", "restart"),
    ("camera", "board_camera"),
    ("update", "board_software"),
}
# Abort reasons Home Assistant raises itself.
HOME_ASSISTANT_ABORTS = {"already_configured", "already_in_progress"}
# Words of the wrong form of address: German, Dutch and Spanish speak to the
# user informally, French formally, as Home Assistant does in these languages.
WRONG_ADDRESS = {
    "de": r"\b(Sie|Ihr|Ihre|Ihren|Ihrem)\b",
    "nl": r"\b(u|uw|U|Uw)\b",
    "fr": r"\b(tu|toi|ton|ta|tes|Tu|Toi|Ton|Ta|Tes)\b",
    "es": r"\b(usted|ustedes|Usted|Ustedes)\b",
}


def texts(tree: object, path: str = "") -> dict[str, str]:
    """Every translated text by its path, such as entity.sensor.round.name."""
    if isinstance(tree, str):
        return {path: tree}
    assert isinstance(tree, dict), path
    result: dict[str, str] = {}
    for key, value in tree.items():
        result |= texts(value, f"{path}.{key}" if path else key)
    return result


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"{(\w+)}", text))


def states(platform: str, key: str, language: str = "en") -> set[str]:
    return set(TRANSLATIONS[language]["entity"][platform][key]["state"])


def test_english_translation_is_the_source_strings():
    assert TRANSLATIONS["en"] == STRINGS, SYNC


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_has_every_text_with_its_placeholders(language):
    source, translated = texts(STRINGS), texts(TRANSLATIONS[language])
    # The texts of strings.json in its order, so the files compare line by line.
    assert list(translated) == list(source), SYNC
    for path, text in source.items():
        assert placeholders(translated[path]) == placeholders(text), path
        assert translated[path].strip(), path


def assert_tidy(language: str, path: str, text: str) -> None:
    """No stray spaces, the form of address and the punctuation of the language."""
    assert text == text.strip() and "  " not in text, path
    if language in WRONG_ADDRESS and not path.startswith("selector"):
        assert not re.search(WRONG_ADDRESS[language], text), path
    # The words only, without code, placeholders, links and addresses.
    prose = re.sub(
        r"```.*?```|`[^`]*`|{\w+}|\]\([^)]*\)|https?://", "", text, flags=re.S
    )
    if language == "fr":
        # A no-break space goes before : ; ? and !, as in Home Assistant's French.
        assert not re.search(r"\S[;?!]| [:;?!]|\w:", prose), path
    if language == "es":
        assert prose.count("¿") == prose.count("?"), path


@pytest.mark.parametrize("language", LANGUAGES)
def test_texts_are_tidy(language):
    for path, text in texts(TRANSLATIONS[language]).items():
        assert_tidy(language, path, text)


async def test_the_game_options_agree_everywhere(hass, aioclient_mock):
    game = SERVICES["start_game"]["fields"]["game"]["selector"]["select"]
    assert [str(option) for option in game["options"]] == list(GAME_OPTIONS)
    assert set(STRINGS["selector"][game["translation_key"]]["options"]) == set(
        GAME_OPTIONS
    )
    await setup_local(hass, aioclient_mock)
    select = hass.states.get(entity_id(hass, "select", "practice_game"))
    assert select.attributes["options"] == ["off", *GAME_OPTIONS]
    assert states("select", "practice_game") == {"off", *GAME_OPTIONS}
    standby = hass.states.get(entity_id(hass, "select", "standby_minutes"))
    assert set(standby.attributes["options"]) == states("select", "standby_minutes")


def test_action_limits_agree_with_the_schema():
    fields = SERVICES["start_game"]["fields"]
    assert set(fields) == {str(key) for key in START_GAME_SCHEMA.schema}
    assert set(SERVICES["delete_player"]["fields"]) == {
        str(key) for key in DELETE_PLAYER_SCHEMA.schema
    }
    for field, limit in (("legs", MAX_LEGS), ("sets", MAX_SETS)):
        number = fields[field]["selector"]["number"]
        assert (number["min"], number["max"]) == (1, limit), field
    assert fields["players"]["selector"]["text"]["multiple"] is True
    # The description names the number of players the schema accepts.
    description = STRINGS["services"]["start_game"]["fields"]["players"]["description"]
    assert f"one to {['one', 'two', 'three', 'four'][MAX_PLAYERS - 1]}" in description


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_action_and_field_is_described(language):
    services = TRANSLATIONS[language]["services"]
    assert set(services) == set(SERVICES)
    for service, spec in SERVICES.items():
        assert services[service]["name"] and services[service]["description"]
        assert set(services[service]["fields"]) == set(spec["fields"]), service


def test_select_sensor_and_event_states_are_translated():
    assert states("select", "standby_minutes") == {str(m) for m in STANDBY_MINUTES}
    assert states("sensor", "local_status") == set(LOCAL_STATES)
    event = TRANSLATIONS["en"]["entity"]["event"]["board_events"]
    assert set(event["state_attributes"]["event_type"]["state"]) == set(EVENT_TYPES)


def test_icons_cover_every_entity_and_action():
    for platform, keys in STRINGS["entity"].items():
        icons = set(ICONS["entity"].get(platform, {}))
        assert icons <= set(keys), platform
        missing = {(platform, key) for key in keys} - {(platform, key) for key in icons}
        assert missing <= DEVICE_CLASS_ICONS, missing
    assert set(ICONS["services"]) == set(SERVICES)
    assert set(MOTION_SENSORS) <= set(ICONS["entity"]["binary_sensor"])


# Reads the code as text, which holds every mutant in mutmut's copy.
@pytest.mark.mutation_unsafe
def test_every_message_is_raised_and_every_raised_message_exists():
    for key in STRINGS["exceptions"]:
        assert f'"{key}"' in SOURCES, f"exception {key} is never raised"
    for key in re.findall(r'translation_key="(\w+)"', SOURCES):
        assert (
            key in STRINGS["exceptions"]
            or key in STRINGS["issues"]
            or any(key in keys for keys in STRINGS["entity"].values())
        ), key
    flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    for kind in ("error", "abort"):
        for key in STRINGS["config"][kind]:
            assert f'"{key}"' in flow or key in HOME_ASSISTANT_ABORTS, key


# Reads the code as text, which holds every mutant in mutmut's copy.
@pytest.mark.mutation_unsafe
def test_every_repair_issue_is_translated():
    # Issue names are those of the translation, except the calibration.
    translated = set(STRINGS["issues"])
    assert set(ISSUES) - {"calibration"} <= translated
    assert "calibration_recommended" in translated
    repairs = (INTEGRATION / "repairs.py").read_text(encoding="utf-8")
    for issue, spec in STRINGS["issues"].items():
        if "fix_flow" in spec:
            # A fixable issue explains itself in its flow, not in a description.
            assert "description" not in spec, issue
            for reason in spec["fix_flow"].get("abort", {}):
                assert f'"{reason}"' in repairs, reason
        else:
            assert spec["description"], issue


# The imports of the card texts in the card module: the name and the language of each.
CARD_IMPORTS = re.findall(r'^import (\w+) from "\./text/([\w-]+)\.js";$', CARD, re.M)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """The texts of a file, none of them twice: JSON would keep the last silently."""
    twice = sorted(
        key for key, count in Counter(key for key, _ in pairs).items() if count > 1
    )
    if twice:
        raise ValueError(f"texts given twice: {', '.join(twice)}")
    return dict(pairs)


def module_texts(source: str) -> dict[str, Any]:
    """The texts of a module of the card texts: JSON after `export default`, with
    comments on lines of their own, as the translation bot reads them too.

    The comments and the words around the JSON become blanks, so that an error of
    JSON names the line and column of the file.
    """
    code = "\n".join(
        "" if line.lstrip().startswith("//") else line for line in source.split("\n")
    )
    start, end = code.find("{"), code.rfind("}") + 1
    if start < 0 or (code[:start].split(), code[end:].split()) != (
        ["export", "default"],
        [";"],
    ):
        raise ValueError(
            'not "export default {…};" with comments on lines of their own'
        )
    head, tail = (re.sub(r"\S", " ", part) for part in (code[:start], code[end:]))
    return json.loads(head + code[start:end] + tail, object_pairs_hook=_unique)


@cache
def card_texts() -> dict[str, dict[str, str]]:
    """Every text of the cards by its key, per language, in the order of TEXT."""
    return {
        language: module_texts((CARD_TEXT_FILES / f"{language}.js").read_text("utf-8"))
        for _, language in CARD_IMPORTS
    }


def test_every_list_of_languages_names_the_languages_of_the_translations():
    # A new translation needs its words in each of these too; without them the
    # calendar, the highlight gallery, the voice actions and the numbers of the
    # weekly report would stay English.
    languages = set(LANGUAGES)
    assert set(INTEGRATION_LANGUAGES) == languages
    assert set(LOCALES) == languages
    assert set(MONTHS) == languages
    assert set(DECIMAL_MARKS) == languages
    # English writes "Sep 26", every other language the day and month in numbers.
    assert set(SHORT_DATES) == languages - {"en"}
    # Where a language has none of its own, it says "Checkout" and "September 2026".
    assert set(CHECKOUTS) | set(MONTH_TITLES) <= languages


def test_the_cards_speak_every_language_of_the_integration():
    # The card module imports each file of text/ by the name of its language, in
    # the order of the integration, and TEXT has them all.
    imported = [language for _, language in CARD_IMPORTS]
    assert [name for name, _ in CARD_IMPORTS] == imported
    assert imported == list(INTEGRATION_LANGUAGES)
    assert sorted(path.stem for path in CARD_TEXT_FILES.iterdir()) == LANGUAGES
    assert f"const TEXT = {{ {', '.join(imported)} }};" in CARD.split("\n")
    assert list(card_texts()) == imported


@pytest.mark.parametrize("language", LANGUAGES)
def test_each_file_of_card_texts_is_json_after_export_default(language):
    """A translator edits the file in the browser; a slip there says how to fix it."""
    path = CARD_TEXT_FILES / f"{language}.js"
    try:
        texts = module_texts(path.read_text(encoding="utf-8"))
    except ValueError as error:
        pytest.fail(
            f"{path.name}: {error}. Each text is a line such as "
            '"visit": "Current visit", with a comma after every text but the last.'
        )
    assert all(isinstance(text, str) for text in texts.values()), path.name


def test_a_slip_in_a_file_of_card_texts_names_its_line():
    good = '// The texts.\nexport default {\n  // Status\n  "a": "A",\n  "b": "B"\n};\n'
    assert module_texts(good) == {"a": "A", "b": "B"}
    with pytest.raises(
        json.JSONDecodeError, match="trailing comma.*: line 5 column 11 "
    ):
        module_texts(good.replace('"B"', '"B",'))
    with pytest.raises(ValueError, match="texts given twice: a"):
        module_texts(good.replace('"b"', '"a"'))
    for wrapped in (
        '{"a": "A"}',
        'export const TEXT = {"a": "A"};',
        "export default 1;",
    ):
        with pytest.raises(ValueError, match="export default"):
            module_texts(wrapped)


@pytest.mark.parametrize("language", LANGUAGES)
def test_card_texts_exist_in_every_language(language):
    english, translated = card_texts()["en"], card_texts()[language]
    assert len(english) > 100
    # The keys of TEXT.en in their order, each text with the same placeholders.
    assert list(translated) == list(english)
    for key, text in english.items():
        assert placeholders(translated[key]) == placeholders(text), key
        assert translated[key], key
        assert_tidy(language, key, translated[key])


# Texts whose key the card puts together from a value, such as `party_${game}`
# or `${key}_long`: the start and the end of the key around the value. The
# choices of the editor's dropdowns are `${prefix}_${value}` of dropdown(…).
CARD_TEXT_FAMILIES = (
    ("achievement_", ""),
    ("achievement_", "_goal"),
    ("call_darts_", ""),
    ("cricket_", ""),
    ("cricket_aim_", ""),
    ("drill_", ""),
    ("export_format_", ""),
    ("highlight_", ""),
    ("idle_panel_", ""),
    ("layout_", ""),
    ("lobby_", ""),
    ("lobby_group_", ""),
    ("mark_", ""),
    ("mode_", ""),
    ("overlay_", ""),
    ("overlay_layout_", ""),
    ("party_", ""),
    ("period_", ""),
    ("picker_", ""),
    ("picker_", "_description"),
    ("record_", ""),
    ("rules_", ""),
    ("style_", ""),
    ("tier_", ""),
    ("tournament_", ""),
    ("tournament_mode_", ""),
    ("tournament_stage_", ""),
    ("trend_", ""),
    ("wild_", ""),
    ("", "_alone"),
    ("", "_entity"),
    ("", "_long"),
)


def card_text_families(code: str) -> set[tuple[str, str]]:
    """The families of keys that code puts together, as `party_${game}` and
    `${say}_alone`, and the choices of its dropdowns."""
    families = set(re.findall(r"`(\w*)\$\{[^{}`]*\}(\w*)`", code))
    dropdowns = re.findall(r'dropdown\("\w+", "(\w+)"', code)
    return families | {(f"{prefix}_", "") for prefix in dropdowns}


def unused_card_texts(
    code: str,
    keys: list[str],
    values: frozenset[str] = frozenset(),
    sources: dict[tuple[str, str], frozenset[str]] | None = None,
) -> list[str]:
    """The keys that code reads neither in quotes nor by a family of
    CARD_TEXT_FAMILIES whose value is a word of the code, one of the values or a
    number, such as "gotcha" of party_gotcha or 3 of mark_3. A family of
    sources takes only the values of its own list, such as DRILLS for drill_."""
    quoted = set(re.findall(r"[\"'`](\w+)[\"'`]", code)) | values
    sources = sources or {}

    def built(key: str, start: str, end: str) -> bool:
        value = key[len(start) : len(key) - len(end)]
        if not (key.startswith(start) and key.endswith(end) and value):
            return False
        if (start, end) in sources:
            return value in sources[start, end]
        return value in quoted or value.isdigit()

    def used(key: str) -> bool:
        return key in quoted or any(
            built(key, start, end) for start, end in CARD_TEXT_FAMILIES
        )

    return [key for key in keys if not used(key)]


def test_every_family_of_card_texts_is_still_built():
    families = card_text_families(CARD)
    assert [family for family in CARD_TEXT_FAMILIES if family not in families] == []


# Families whose values come from one list of the integration: a key of such a
# family counts only for a value of that list, not for any word of the code.
CARD_TEXT_SOURCES = {
    ("achievement_", ""): frozenset(ACHIEVEMENTS),
    ("achievement_", "_goal"): frozenset(ACHIEVEMENTS),
    ("drill_", ""): frozenset(DRILLS),
    ("tournament_stage_", ""): frozenset(NAMED_STAGES),
}


def test_every_card_text_is_used():
    # A text that the cards never show would still go to the translators. The
    # integration hands the cards the achievements and the stages of the brackets.
    values = frozenset((*ACHIEVEMENTS, *NAMED_STAGES))
    keys = list(card_texts()["en"])
    assert unused_card_texts(CARD, keys, values, CARD_TEXT_SOURCES) == []


def test_a_card_text_that_nothing_reads_is_found():
    code = (
        'const PARTY_GAMES = ["gotcha"];\n'
        'ui.t("score");\nui.t(`party_${game}`);\nui.t(`mark_${count}`);\n'
        'dropdown("layout", "layout", ["auto"]);\n'
    )
    assert card_text_families(code) == {("party_", ""), ("mark_", ""), ("layout_", "")}
    keys = ["score", "party_gotcha", "mark_3", "layout_auto", "party_bingo", "team"]
    assert unused_card_texts(code, keys) == ["party_bingo", "team"]
    assert unused_card_texts(code, keys, frozenset({"bingo"})) == ["team"]
    # "target" is a word of the code, but not a drill of the integration.
    code += 'ui.t(`drill_${kind}`);\nel.className = "target";\n'
    keys = ["drill_doubles", "drill_target"]
    assert unused_card_texts(code, keys) == ["drill_doubles"]
    sources = {("drill_", ""): frozenset({"doubles"})}
    assert unused_card_texts(code, keys, sources=sources) == ["drill_target"]


# Dependabot bumps the requirements files; the copies elsewhere follow by hand.
ROOT = INTEGRATION.parents[1]
E2E = ROOT / "tests" / "e2e"


def pinned(path: Path, package: str) -> str:
    """The version of a package pinned as ``package==version`` in a requirements file."""
    text = path.read_text(encoding="utf-8")
    versions = re.findall(rf"^{re.escape(package)}==(\S+)", text, re.M | re.I)
    assert len(versions) == 1, (path.name, versions)
    return versions[0]


def test_pre_commit_runs_the_ruff_of_the_test_requirements():
    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    # A rev is a tag, or a commit with the tag as "# frozen: v1.2.3".
    rev = re.search(
        r"repo: https://github\.com/astral-sh/ruff-pre-commit\n"
        r"\s+rev: (\S+)(?: # frozen: (\S+))?\n",
        config,
    )
    assert rev, "the Ruff hook is missing"
    version = (rev[2] or rev[1]).removeprefix("v")
    assert version == pinned(ROOT / "requirements-test.in", "ruff")
    assert version == pinned(ROOT / "requirements-test.txt", "ruff")


@pytest.mark.parametrize(
    "script", ["browser.sh", "live_demo.sh", "screenshots.sh", "visual.sh"]
)
def test_the_playwright_image_matches_the_playwright_package(script):
    text = (E2E / script).read_text(encoding="utf-8")
    images = re.findall(
        r"^PLAYWRIGHT_IMAGE=\"mcr\.microsoft\.com/playwright/python:"
        r"v([\d.]+)-\w+@sha256:[0-9a-f]{64}\"$",
        text,
        re.M,
    )
    # The browsers of the image fit only the same version of the package.
    assert images == [pinned(E2E / "requirements-browser.in", "playwright")]
    assert images == [pinned(E2E / "requirements-browser.txt", "playwright")]


# A pull request runs the end-to-end tests only when it changes what they use.
E2E_WORKFLOW = yaml.safe_load(
    (ROOT / ".github" / "workflows" / "e2e.yml").read_text(encoding="utf-8")
)


def e2e_pattern(name: str = "tested") -> re.Pattern[str]:
    """The paths whose change runs the end-to-end tests in a pull request: the Home
    Assistant tests ("tested") or the live demo ("demo")."""
    steps = E2E_WORKFLOW["jobs"]["changes"]["steps"]
    (run,) = [step["run"] for step in steps if step.get("id") == "files"]
    patterns = re.findall(rf"^{name}='(.+)'$", run, re.M)
    assert len(patterns) == 1, patterns
    return re.compile(patterns[0])


def mounted() -> set[str]:
    """The files and folders of the repository that the compose files mount."""
    root = ROOT.resolve()
    paths = set()
    for compose in sorted(E2E.glob("compose*.yaml")):
        services = yaml.safe_load(compose.read_text(encoding="utf-8"))["services"]
        for service in services.values():
            for volume in service.get("volumes", []):
                if isinstance(volume, dict):
                    source = volume["source"]
                else:
                    source = volume.split(":")[0]
                # A named volume holds what Home Assistant writes, not the repository.
                if source.startswith("."):
                    paths.add((E2E / source).resolve().relative_to(root).as_posix())
    return paths


# The live demo has a job of its own, which runs for what it plays.
LIVE_DEMO = "live_demo.py"


def read_from_the_root(live_demo: bool = False) -> set[str]:
    """What the scripts of tests/e2e read from the root of the repository, such as
    browser.py in the repository that browser.sh mounts: those of the Home
    Assistant tests, or with live_demo those of the live demo."""
    paths = set()
    for script in sorted(E2E.glob("*.py")):
        if (script.name == LIVE_DEMO) != live_demo:
            continue
        text = script.read_text(encoding="utf-8")
        for parts in re.findall(r'parents\[2\]((?:\s*/\s*"[^"]+")+)', text):
            paths.add("/".join(re.findall(r'"([^"]+)"', parts)))
    return paths


def test_pull_requests_run_the_end_to_end_tests_for_every_file_they_use():
    # Both finders know the integration, so this test can't pass on nothing.
    assert "custom_components/homedarts" in mounted()
    assert "custom_components/homedarts" in read_from_the_root()
    used = mounted() | read_from_the_root() | {".github/workflows/e2e.yml"}
    # npm ci installs node_modules, with axe-core, from the package files.
    if any(path.startswith("node_modules/") for path in used):
        used = {path for path in used if not path.startswith("node_modules/")}
        used |= {"package.json", "package-lock.json"}
    pattern = e2e_pattern()
    for path in sorted(used):
        # A folder counts with every file in it, also one added later.
        sample = f"{path}/new.file" if (ROOT / path).is_dir() else path
        assert pattern.match(sample), f"e2e.yml must run the tests for {path}"


def test_pull_requests_run_the_live_demo_for_every_file_it_plays():
    used = read_from_the_root(live_demo=True)
    assert {"docs/demo", "custom_components/homedarts/frontend"} <= used
    used |= {
        ".github/workflows/e2e.yml",
        "tests/e2e/live_demo.py",
        "tests/e2e/live_demo.sh",
        "tests/e2e/requirements-browser.txt",
    }
    pattern = e2e_pattern("demo")
    for path in sorted(used):
        sample = f"{path}/new.file" if (ROOT / path).is_dir() else path
        assert pattern.match(sample), f"e2e.yml must run the live demo for {path}"


def test_the_browser_test_mounts_only_the_repository_and_its_artifacts():
    # browser.py reads from the repository what read_from_the_root() finds; a new
    # mount needs its files among those that run the tests in e2e.yml.
    script = (E2E / "browser.sh").read_text(encoding="utf-8")
    assert re.findall(r'--volume "([^"]+)"', script) == [
        "${ROOT_MOUNT}:/repo:ro",
        "${artifacts_mount}:/artifacts",
    ]


def skipped_by(workflow: str) -> set[str]:
    """The files of the end-to-end tests whose change alone does not start a workflow
    of the screenshot tool."""
    path = ROOT / ".github" / "workflows" / workflow
    # PyYAML reads the key "on" as True.
    trigger = yaml.safe_load(path.read_text(encoding="utf-8"))[True]
    (event,) = [event for event in ("push", "pull_request") if event in trigger]
    return {path[1:] for path in trigger[event]["paths"] if path.startswith("!")}


def imports(script: Path) -> set[str]:
    """The modules a script imports, by the first part of their names."""
    tree = ast.parse(script.read_text(encoding="utf-8"))
    names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and not node.level
    }
    return {name.partition(".")[0] for name in names}


@pytest.mark.parametrize("workflow", ["screenshots.yml", "visual.yml"])
def test_the_screenshot_tool_runs_again_for_every_script_it_uses(workflow):
    # The screenshot bot and the visual check skip the browser test, but a module
    # of the browser test that the screenshot tool imports counts for it, such as
    # pages.py, whose waits both use.
    skipped = skipped_by(workflow)
    assert "tests/e2e/browser.py" in skipped
    assert "tests/e2e/screenshots.py" not in skipped
    for script in sorted(E2E.glob("*.py")):
        if f"tests/e2e/{script.name}" in skipped:
            continue
        used = {f"tests/e2e/{name}.py" for name in imports(script)} & skipped
        assert not used, f"{script.name} imports {sorted(used)}, which {workflow} skips"


@pytest.mark.parametrize("workflow", ["screenshots.yml", "visual.yml"])
def test_the_pictures_are_taken_again_when_the_recorded_board_changes(workflow):
    # The double of the Board Manager in the demo answers like its recordings, and
    # the pictures show what it answers, such as the board PC of the status card.
    recordings = "tests/fixtures/board_manager"
    assert recordings in mounted()
    path = ROOT / ".github" / "workflows" / workflow
    trigger = yaml.safe_load(path.read_text(encoding="utf-8"))[True]
    (event,) = [event for event in ("push", "pull_request") if event in trigger]
    assert f"{recordings}/**" in trigger[event]["paths"]
    # Its README alone changes no picture.
    assert f"!{recordings}/README.md" in trigger[event]["paths"]


# The key of the rendered images (tests/e2e/render_key.py): a job of the visual check
# or of the screenshot bot takes the images of an earlier run with the same key, so
# the key has to change with every file that changes an image.
RENDER_KEY_SPEC = importlib.util.spec_from_file_location(
    "render_key", E2E / "render_key.py"
)
assert RENDER_KEY_SPEC is not None and RENDER_KEY_SPEC.loader is not None
render_key = importlib.util.module_from_spec(RENDER_KEY_SPEC)
RENDER_KEY_SPEC.loader.exec_module(render_key)


def in_the_key(path: str) -> bool:
    """Whether a file or a folder lies below one of the inputs of the key."""
    return any(
        path == folder or path.startswith(f"{folder}/") for folder in render_key.INPUTS
    )


def test_the_key_of_the_images_knows_every_file_that_the_demo_mounts():
    # Home Assistant of the demo reads the integration, its blueprints and the
    # recordings of the Board Manager through the compose files, the screenshot tool
    # its scripts in tests/e2e.
    assert "blueprints/automation/homedarts" in mounted()
    for path in sorted(mounted()):
        assert in_the_key(path), f"render_key.py must know {path}, which the demo reads"


@pytest.mark.parametrize("workflow", ["screenshots.yml", "visual.yml"])
def test_the_key_of_the_images_skips_what_the_workflow_skips(workflow):
    # A file whose change alone starts no render changes no image either.
    assert skipped_by(workflow) == render_key.SKIPPED


@pytest.mark.parametrize("workflow", ["screenshots.yml", "visual.yml"])
def test_the_key_of_the_images_knows_every_file_that_starts_a_render(workflow):
    path = ROOT / ".github" / "workflows" / workflow
    trigger = yaml.safe_load(path.read_text(encoding="utf-8"))[True]
    (event,) = [event for event in ("push", "pull_request") if event in trigger]
    started = [
        pattern.removesuffix("/**")
        for pattern in trigger[event]["paths"]
        if not pattern.startswith("!")
    ]
    # The workflow itself renders as the other one does (tests/test_render_key.py),
    # and the screenshot bot records the live demo apart from the images.
    apart = {
        f".github/workflows/{workflow}",
        "tests/demo_timeline.py",
        "scripts/record_demo.py",
    }
    assert "custom_components/homedarts/frontend" in started
    for pattern in started:
        if pattern not in apart:
            assert in_the_key(pattern), f"render_key.py must know {pattern}"


def test_the_end_to_end_tests_run_the_oldest_supported_home_assistant():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    oldest = hacs["homeassistant"]
    assert re.fullmatch(
        rf"ghcr\.io/home-assistant/home-assistant:{re.escape(oldest)}"
        r"@sha256:[0-9a-f]{64}",
        E2E_WORKFLOW["env"]["OLDEST_HOME_ASSISTANT"],
    )
    jobs = E2E_WORKFLOW["jobs"]
    matrices = {
        "scenario": jobs["scenario"]["strategy"]["matrix"]["include"],
        "browser": jobs["browser"]["strategy"]["matrix"]["home_assistant"],
    }
    for job, matrix in matrices.items():
        # The other jobs run the current release, the default of compose.yaml.
        (entry,) = [entry for entry in matrix if entry.get("oldest")]
        assert entry["name"] == f"Home Assistant {oldest}", job
        (image,) = [
            step["env"]["HOME_ASSISTANT_IMAGE"]
            for step in jobs[job]["steps"]
            if "HOME_ASSISTANT_IMAGE" in step.get("env", {})
        ]
        assert "env.OLDEST_HOME_ASSISTANT" in image, job


# How the pages name the oldest supported Home Assistant: "2026.8 or newer",
# "**2026.8** oder neuer", "ab 2026.8" and the badge of the README.
MINIMUM_RELEASE = re.compile(
    r"\*{0,2}(20\d\d\.\d{1,2})(?:\.\d+)?\*{0,2} "
    r"(?:or newer|oder neuer|of nieuwer|ou plus récent|o posterior)"
    r"|\bab \*{0,2}(20\d\d\.\d{1,2})"
    r"|Home%20Assistant-(20\d\d\.\d{1,2})%2B"
)


def test_the_documentation_names_the_oldest_supported_home_assistant():
    """A new minimum starts in hacs.json, and every page follows it
    (docs/decisions/0022-home-assistant-2026-8-as-the-oldest-release.md)."""
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    oldest = ".".join(hacs["homeassistant"].split(".")[:2])
    # The changelog and the decisions keep the releases of their time.
    pages = [
        path
        for path in sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").glob("*.md"))
        if path.name != "CHANGELOG.md"
    ]
    named: Counter[str] = Counter()
    wrong = []
    for path in pages:
        page = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, 1):
            for match in MINIMUM_RELEASE.finditer(line):
                release = next(group for group in match.groups() if group)
                named[page] += 1
                if release != oldest:
                    wrong.append(f"{page}:{number}: {match[0]}")
    assert not wrong, (
        f"hacs.json requires Home Assistant {oldest}, but these lines name another "
        "release as the oldest one; name the release of hacs.json there, or, for a "
        "feature that needs a newer release, write 'since 2026.x' instead of "
        "'2026.x or newer' or 'ab 2026.x':\n" + "\n".join(wrong)
    )
    # The pattern still finds what each language says on its main pages.
    for page in (
        "README.md",
        "docs/README.md",
        "docs/README.de.md",
        "docs/installation.md",
        "docs/installation.de.md",
        "docs/installation.nl.md",
        "docs/installation.fr.md",
        "docs/installation.es.md",
    ):
        assert named[page], page


def test_each_lock_file_is_compiled_for_its_own_python():
    # Renovate installs pip-tools once per run, for the Python of the first lock file
    # it compiles: the tests compile with pip-compile for the Python of the project,
    # the browser tests with uv for the Python 3.12 of the Playwright image.
    python = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    test = (ROOT / "requirements-test.txt").read_text(encoding="utf-8")
    assert f"autogenerated by pip-compile with Python {python}\n" in test
    browser = (E2E / "requirements-browser.txt").read_text(encoding="utf-8")
    assert re.search(
        r"^#    uv pip compile --generate-hashes --python-version=3\.12\.\d+ ",
        browser,
        re.M,
    )


# Folders that hold no lock file of the project: those Renovate ignores
# (ignorePaths in .github/renovate-blueprint.json5), Git's own and what tools write.
# Renovate reads only committed files, so lock_files() also skips every folder that
# is a checkout of its own, such as a worktree in .claude/worktrees.
NO_LOCK_FILES = {".git", "node_modules", "vendor", "site", "mutants"}

# The options that Renovate reads only as --option=value: optionsWithArguments in
# lib/modules/manager/pip-compile/common.ts of Renovate. Written with a space, the
# option makes Renovate throw for the whole file.
OPTIONS_WITH_VALUES = {
    "--output-file",
    "--extra",
    "--extra-index-url",
    "--resolver",
    "--constraint",
    "--constraints",
    "--python-version",
    "--no-emit-package",
    "--prerelease",
    "--format",
    "--resolution",
    "--fork-strategy",
    "--exclude-newer",
    "--exclude-newer-package",
    "--group",
    "--override",
    "--overrides",
}


def lock_files() -> list[Path]:
    """The lock files that Renovate's pip-compile manager updates: every
    requirements*.txt (its managerFilePatterns in .github/renovate-blueprint.json5)."""
    found = []
    for folder, folders, files in os.walk(ROOT):
        folders[:] = [
            name
            for name in folders
            if name not in NO_LOCK_FILES
            and not name.startswith(".venv")
            # another checkout, such as .claude/worktrees/*
            and not (Path(folder) / name / ".git").exists()
        ]
        found += [
            Path(folder) / name
            for name in files
            if re.fullmatch(r"requirements[^/]*\.txt", name)
        ]
    return sorted(found)


def test_renovate_can_run_the_command_of_every_lock_file_again():
    # Renovate updates a lock file by running the command in its header again. It
    # reads an option with a value only as --option=value; for "--option value" it
    # logs a warning in its own run and never updates the file. uv writes the command
    # into the header as it was typed (pip-compile writes --option=value itself).
    paths = {path.relative_to(ROOT).as_posix(): path for path in lock_files()}
    assert {"requirements-test.txt", "tests/e2e/requirements-browser.txt"} <= set(paths)
    for name, path in paths.items():
        commands = re.findall(
            r"^#    (?:uv pip compile|pip-compile) (.+)$",
            path.read_text(encoding="utf-8"),
            re.M,
        )
        assert len(commands) == 1, f"{name} needs the command that compiled it"
        arguments = shlex.split(commands[0])
        assert not set(arguments) & OPTIONS_WITH_VALUES, (
            f"{name}: join each value to its option with '=' in the header"
        )
        assert f"--output-file={path.name}" in arguments, name
        # Every argument without a dash is a source file next to the lock file, such
        # as its .in file; the value of an option after a space would read as one.
        for source in [argument for argument in arguments if argument[0] != "-"]:
            assert (path.parent / source).is_file(), (
                f"{name}: join {source!r} to its option with '=' in the header"
            )


def test_osv_exceptions_cover_only_the_pinned_versions():
    ignored = tomllib.loads((ROOT / "osv-scanner.toml").read_text(encoding="utf-8"))
    # The rules of the dependency review, which the workflow reads.
    review = yaml.safe_load(
        (ROOT / ".github" / "dependency-review.yml").read_text(encoding="utf-8")
    )
    accepted = ignored.get("IgnoredVulns", [])
    for vulnerability in accepted:
        package, version = re.match(r"(\S+) (\S+): ", vulnerability["reason"]).groups()
        # Once the test base moves on, the exception has to go.
        assert pinned(ROOT / "requirements-test.txt", package) == version, (
            f"remove {vulnerability['id']} from osv-scanner.toml and .github/dependency-review.yml"
        )
    assert review["allow-ghsas"] == [vulnerability["id"] for vulnerability in accepted]


def test_osv_overrides_accept_only_the_pinned_versions():
    # A [[PackageOverrides]] entry accepts every advisory of one version that Home
    # Assistant pins in the test base; once the test base moves on, it has to go, or it
    # would accept the advisories of a version that nothing here installs any more.
    config = tomllib.loads((ROOT / "osv-scanner.toml").read_text(encoding="utf-8"))
    test_base = (ROOT / "requirements-test.txt").read_text(encoding="utf-8")
    for override in config.get("PackageOverrides", []):
        name, version = override["name"], override["version"]
        versions = re.findall(rf"^{re.escape(name)}==(\S+)", test_base, re.M | re.I)
        assert versions == [version], (
            f"requirements-test.txt pins {name} {versions or 'no more'}: remove the "
            f"override of {name} {version} from osv-scanner.toml and run "
            "python3 .github/blueprint.py advisories --fix (from blueprint 1.0.8 on)"
        )


def node_packages() -> dict[str, dict[str, Any]]:
    """The packages of package-lock.json by their folder, such as node_modules/eslint."""
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    return lock["packages"]


def test_node_tools_install_minimatch_with_the_fix_of_its_advisory():
    # GHSA-g3hv-75wg-m249, a denial of service by a pattern, is fixed from minimatch
    # 11.0.1 on and the OpenSSF Scorecard reports the version below it. ESLint and its
    # config array still ask for ^10, so without the override of package.json npm goes
    # back to the 10.2.6 with the advisory.
    versions = [
        package["version"]
        for path, package in node_packages().items()
        if path.endswith("node_modules/minimatch")
    ]
    assert versions, "no package needs minimatch any more: remove this test"
    for version in versions:
        assert tuple(map(int, version.split("."))) >= (11, 0, 1), (
            f"minimatch {version} has GHSA-g3hv-75wg-m249: raise it in the overrides "
            "of package.json and run npm install --package-lock-only --ignore-scripts"
        )


def test_node_overrides_leave_with_the_update_that_fixes_them():
    # An override raises a package that a tool asks for in a range too old for its fix.
    # It stays only while such a range exists, like an entry of osv-scanner.toml, or it
    # would hold the package back from the updates of the tools that ask for it.
    manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    packages = node_packages()
    for name, version in manifest.get("overrides", {}).items():
        assert packages[f"node_modules/{name}"]["version"] == version, (
            f"run npm install --package-lock-only --ignore-scripts for {name} {version}"
        )
        ranges = [
            package["dependencies"][name]
            for package in packages.values()
            if name in package.get("dependencies", {})
        ]
        major = version.split(".")[0]
        assert any(not spec.startswith(f"^{major}.") for spec in ranges), (
            f"everything that needs {name} now takes {name} {version}: remove its "
            "override from package.json and run "
            "npm install --package-lock-only --ignore-scripts"
        )
