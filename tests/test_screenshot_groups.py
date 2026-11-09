"""The screenshot tool renders the images of the documentation in fixed groups, each
from a fresh demo, so that the visual check and the screenshot bot render the groups
side by side on runners of their own and put them together afterwards.

The scripts run here as the workflows run them: tests/e2e/screenshots.sh with a
stand-in for docker, collect.sh with compare.py, scripts/screenshots.sh, whose shards
the screenshot bot of the blueprint renders, with stand-ins for the screenshot tool,
the recorder and uv, and the comment of the visual check in bash with a stand-in for
gh."""

import ast
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from PIL import Image, ImageDraw

ROOT = Path(__file__).parents[1]
E2E = ROOT / "tests" / "e2e"
WORKFLOWS = ROOT / ".github" / "workflows"
TOOL = ast.parse((E2E / "screenshots.py").read_text(encoding="utf-8"))
SPEC = importlib.util.spec_from_file_location("group_times", E2E / "group_times.py")
group_times = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(group_times)

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="the scripts run in bash"
)
# The runners of GitHub have jq, which the comment reads its artifacts with.
needs_jq = pytest.mark.skipif(
    shutil.which("jq") is None, reason="the comment reads with jq"
)


def assigned(name: str) -> ast.expr:
    """What screenshots.py assigns to a name at the level of the module."""
    for node in TOOL.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return node.value
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return node.value
    raise AssertionError(f"screenshots.py assigns nothing to {name}")


def function(name: str) -> ast.FunctionDef:
    """The function of that name at the level of the module of screenshots.py."""
    (found,) = [
        node
        for node in TOOL.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    return found


def called(node: ast.FunctionDef) -> list[str]:
    """The names of the functions that a function calls, in the order of its lines."""
    calls = [
        call
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    ]
    return [call.func.id for call in sorted(calls, key=lambda call: call.lineno)]


GROUPS = ast.literal_eval(assigned("GROUPS"))
SECONDS = ast.literal_eval(assigned("SECONDS"))
STARTUP = ast.literal_eval(assigned("STARTUP"))
BUDGETS = ast.literal_eval(assigned("BUDGETS"))
SECTION_BUDGET = ast.literal_eval(assigned("SECTION_BUDGET"))
SECTIONS = assigned("SECTIONS")
assert isinstance(SECTIONS, ast.Dict)
SECTION_FUNCTIONS = {
    ast.literal_eval(key): value.id
    for key, value in zip(SECTIONS.keys, SECTIONS.values, strict=True)
    if key is not None and isinstance(value, ast.Name)
}


def workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def group_count(script: str) -> int:
    counts = re.findall(
        r"^GROUP_COUNT=(\d+)$", (ROOT / script).read_text(encoding="utf-8"), re.M
    )
    assert len(counts) == 1, (script, counts)
    return int(counts[0])


# The groups ------------------------------------------------------------------------


def test_every_section_renders_in_exactly_one_group():
    sections = [section for group in GROUPS for section in group]
    assert len(sections) == len(set(sections)), sections
    assert sorted(sections) == sorted(SECTION_FUNCTIONS)
    assert all(GROUPS), "a group without sections"


def test_every_section_is_a_function_of_the_tool():
    functions = {node.name for node in TOOL.body if isinstance(node, ast.FunctionDef)}
    assert len(SECTION_FUNCTIONS) == len(SECTIONS.keys)
    assert set(SECTION_FUNCTIONS.values()) <= functions


def test_the_steps_that_depend_on_each_other_share_a_group():
    group_of = {
        section: number for number, group in enumerate(GROUPS) for section in group
    }
    # The cards and their graphs of the week come before the games end their legs.
    assert group_of["cards"] == group_of["games"]
    assert GROUPS[group_of["games"]].index("cards") < GROUPS[group_of["games"]].index(
        "games"
    )
    # The darts of the bot follow the fixed random numbers of the demo: its first
    # match is that of the corrections, as before the groups, and then the formats.
    bot = GROUPS[group_of["corrections"]]
    assert bot.index("corrections") < bot.index("formats")
    # A second board would be the first of the cards without one: the dartboard
    # without Autodarts comes last in its group. The weekly report starts a new week:
    # the calendar comes last in its group, or right before that board.
    assert GROUPS[group_of["manual"]][-1] == "manual"
    calendar = [
        section for section in GROUPS[group_of["calendar"]] if section != "manual"
    ]
    assert calendar[-1] == "calendar"
    # The quick start removes the board of the demo and sets it up again as new.
    assert GROUPS[group_of["setup"]][-1] == "setup"


def test_the_quick_start_has_every_caption_in_both_languages():
    captions = ast.literal_eval(assigned("SETUP_CAPTIONS"))
    buttons = ast.literal_eval(assigned("SETUP_BUTTONS"))
    assert set(captions) == set(buttons) == {"en", "de"}
    assert len(captions["en"]) == len(captions["de"]) == 5
    assert buttons["en"].keys() == buttons["de"].keys()


def test_no_group_takes_much_longer_than_the_shortest():
    # The runs of a language wait for their slowest group: by the measured seconds
    # of its sections, none takes more than SLOWER times as long as the shortest.
    assert sorted(SECONDS) == sorted(SECTION_FUNCTIONS)
    totals = {
        number: sum(SECONDS[section] for section in group)
        for number, group in enumerate(GROUPS, 1)
    }
    assert group_times.slow(totals) == {}, totals


def test_the_longest_group_takes_nine_minutes_at_most():
    # A job of a group starts its demo and then renders its sections. On a runner of
    # GitHub, the whole job of the longest group stays within nine minutes.
    longest = max(sum(SECONDS[section] for section in group) for group in GROUPS)
    assert longest + STARTUP <= 9 * 60


def test_the_players_play_their_own_matches():
    # The players card shows the five players of a tournament. The section plays it
    # itself, before its first picture, so no other section has to come before it:
    # "more games", which shows the bracket of that tournament, renders on a runner
    # of its own.
    calls = called(function("people"))
    assert calls.index("players_matches") < calls.index("players_card")
    assert "play_tournament" in called(function("players_matches"))
    assert "start_tournament_of_five" in called(function("players_matches"))
    assert "start_tournament_of_five" in called(
        function("tournament_bracket_animation")
    )
    group_of = {
        section: number for number, group in enumerate(GROUPS) for section in group
    }
    assert group_of["more games"] != group_of["people"]


def test_a_match_before_a_picture_waits_for_home_assistant_not_for_a_fixed_time():
    # Most of the seconds of the big tournaments were fixed waits between the darts
    # of matches that no image shows.
    for name in ("quick_visit", "play_tournament"):
        assert "wait_for_timeout" not in {
            node.func.attr
            for node in ast.walk(function(name))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }, name
    assert "quick_visit" in called(function("play_tournament"))
    assert "checkout_101" not in called(function("play_tournament"))


def test_the_weekly_report_waits_seconds_for_its_time_not_the_rest_of_a_minute():
    # Home Assistant waits for the report time in real seconds from the moment it is
    # set, so the frozen clock is just before that time by then.
    report = ast.unparse(function("weekly_report_notification"))
    assert report.index("seconds=1") < report.index("NEXT_MINUTE")
    assert report.index("NEXT_MINUTE") < report.index("'weekly_report_time'")
    assert report.index("'weekly_report_time'") < report.index("move_clock(due)")


def test_every_section_may_take_twice_its_seconds_before_the_watchdog_fails_it():
    assert set(BUDGETS) <= set(SECONDS)
    for section, seconds in SECONDS.items():
        assert BUDGETS.get(section, SECTION_BUDGET) >= 2 * seconds, section


def test_the_big_tournaments_stop_at_their_pictures():
    # No image shows a match after the picture; the tests of the tournament formats
    # play 32 players to their champion instead (tests/test_tournament_formats.py).
    played = [
        node
        for node in ast.walk(function("big_tournament"))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "play_tournament"
    ]
    assert [[ast.unparse(argument) for argument in call.args] for call in played] == [
        ["page", "before"]
    ]


@pytest.mark.parametrize(
    "script",
    ["tests/e2e/screenshots.sh", "tests/e2e/collect.sh", "scripts/screenshots.sh"],
)
def test_the_scripts_know_how_many_groups_there_are(script):
    assert group_count(script) == len(GROUPS)


def test_the_visual_check_renders_every_group_on_a_runner_of_its_own():
    count = len(GROUPS)
    render = workflow("visual.yml")["jobs"]["render"]
    matrix = render["strategy"]["matrix"]
    assert matrix["group"] == list(range(1, count + 1))
    assert matrix["language"] == ["en", "de"]
    assert (
        render["name"]
        == f"render (${{{{ matrix.language }}}}, ${{{{ matrix.group }}}}/{count})"
    )
    (step,) = [
        step for step in render["steps"] if "screenshots.sh" in step.get("run", "")
    ]
    assert step["env"]["SCREENSHOT_GROUP"] == f"${{{{ matrix.group }}}}/{count}"
    assert step["env"]["IMAGES"] == "tests/e2e/artifacts/rendered"
    (upload,) = [
        step
        for step in render["steps"]
        if step.get("with", {}).get("path") == "tests/e2e/artifacts/rendered/"
    ]
    # Under the key of what the images are rendered from (tests/test_render_key.py).
    assert upload["with"]["name"] == "${{ steps.earlier.outputs.name }}"
    # One group that fails cancels neither the other groups nor what comes after.
    assert render["strategy"]["fail-fast"] is False
    assert "!cancelled()" in workflow("visual.yml")["jobs"]["compare"]["if"]


def test_the_job_of_a_language_lists_how_long_its_groups_took():
    render = workflow("visual.yml")["jobs"]["render"]["steps"]
    # An artifact of their own: the folder of the images belongs to root, the user of
    # the container that rendered them, so no step of the runner writes into it.
    assert not any("artifacts/rendered/" in step.get("run", "") for step in render)
    (kept,) = [
        step for step in render if step.get("name") == "Keep the seconds of the group"
    ]
    assert kept["if"] == "${{ !cancelled() }}"
    # Only informational: a failed upload of the seconds never costs the images.
    assert kept["continue-on-error"] is True
    assert kept["with"] == {
        "name": "times-${{ matrix.language }}-${{ matrix.group }}",
        "path": "tests/e2e/artifacts/screenshots-*.json",
        "if-no-files-found": "ignore",
        "retention-days": 1,
    }
    steps = workflow("visual.yml")["jobs"]["compare"]["steps"]
    names = [step.get("name") for step in steps]
    taken = steps[names.index("Take the seconds of every group")]
    assert taken["if"] == "${{ !cancelled() }}"
    assert taken["continue-on-error"] is True
    assert taken["with"] == {
        "pattern": "times-${{ matrix.language }}-*",
        "path": "tests/e2e/artifacts",
    }
    table = steps[names.index("List how long the groups took")]
    assert names.index("Take the seconds of every group") < names.index(
        "List how long the groups took"
    )
    assert table["if"] == "${{ !cancelled() }}"
    assert table["continue-on-error"] is True
    assert table["env"]["LANGUAGE"] == "${{ matrix.language }}"
    assert table["run"] == (
        'python3 tests/e2e/group_times.py "$LANGUAGE" tests/e2e/artifacts'
        ' >> "$GITHUB_STEP_SUMMARY"'
    )


def blueprint_screenshots():
    """The module of the screenshot bot of the blueprint, which reads its settings."""
    spec = importlib.util.spec_from_file_location(
        "blueprint_screenshots", ROOT / ".github" / "blueprint" / "screenshots.py"
    )
    module = importlib.util.module_from_spec(spec)
    # Its dataclasses look their module up by name.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_screenshot_bot_renders_every_group_of_every_language_as_a_shard():
    # Each group of each language on a runner of its own, as in the visual check, and
    # the recording of the live demo beside them.
    languages = workflow("visual.yml")["jobs"]["render"]["strategy"]["matrix"][
        "language"
    ]
    settings = tomllib.loads(
        (ROOT / ".github" / "screenshots.toml").read_text(encoding="utf-8")
    )
    assert settings["shards"] == [
        f"{language}-{group}"
        for language in languages
        for group in range(1, len(GROUPS) + 1)
    ] + ["timeline"]
    assert settings["files"] == ["docs/demo/timeline.json"]
    script = (ROOT / "scripts" / "screenshots.sh").read_text(encoding="utf-8")
    assert f"LANGUAGES=({' '.join(languages)})" in script
    # The bot takes the settings as they are: a value it can't take fails its run.
    taken = blueprint_screenshots().settings(ROOT)
    assert list(taken.shards) == settings["shards"]
    assert list(taken.files) == settings["files"]
    assert list(taken.hosts) == settings["hosts"]
    assert list(taken.skip_wait) == settings["skip_wait"]
    assert taken.timeout_minutes == settings["timeout_minutes"]
    assert taken.failure_folder == settings["failure_folder"]


def test_the_step_that_renders_a_shard_has_the_time_of_the_step_of_the_visual_check():
    # The same group of the same tool, on the same runner.
    (render,) = [
        step
        for step in workflow("visual.yml")["jobs"]["render"]["steps"]
        if step.get("run") == "exec bash tests/e2e/screenshots.sh"
    ]
    settings = tomllib.loads(
        (ROOT / ".github" / "screenshots.toml").read_text(encoding="utf-8")
    )
    assert settings["timeout_minutes"] == render["timeout-minutes"]


def test_a_shard_that_failed_keeps_what_the_screenshot_tool_left():
    # The pages that a failed capture saved, the seconds of the sections and the
    # images of the group so far: the folder that Git ignores, in which the tool and
    # scripts/screenshots.sh leave them.
    settings = tomllib.loads(
        (ROOT / ".github" / "screenshots.toml").read_text(encoding="utf-8")
    )
    folder = settings["failure_folder"]
    assert folder == "tests/e2e/artifacts"
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert f"/{folder}/" in ignored
    script = (ROOT / "scripts" / "screenshots.sh").read_text(encoding="utf-8")
    assert f'local folder="{folder}/rendered-${{language}}-${{group}}"' in script
    tool = (ROOT / "tests" / "e2e" / "screenshots.py").read_text(encoding="utf-8")
    assert 'ARTIFACTS = Path(__file__).resolve().parent / "artifacts"' in tool


def test_the_comment_of_the_visual_check_finds_one_report_per_language():
    compare = workflow("visual.yml")["jobs"]["compare"]
    assert compare["strategy"]["matrix"]["language"] == ["en", "de"]
    (upload,) = [
        step
        for step in compare["steps"]
        if step.get("with", {}).get("name", "").startswith("visual-")
    ]
    assert upload["with"]["name"] == "visual-${{ matrix.language }}"
    comment = (WORKFLOWS / "visual-comment.yml").read_text(encoding="utf-8")
    assert "--pattern 'visual-??'" in comment


# The same images from the same code ---------------------------------------------------


def source(name: str) -> str:
    """A function of the tool as text, without its comments."""
    return ast.unparse(function(name))


def in_order(text: str, *parts: str) -> None:
    """Every part stands in the text, each after the one before it."""
    place = 0
    for part in parts:
        found = text.find(part, place)
        assert found >= 0, f"{part!r} after {text[max(place - 60, 0) : place]!r}"
        place = found + len(part)


def test_the_pointer_leaves_what_it_clicked_before_every_picture():
    # A button that comes to lie under the pointer takes its hover colour at a moment
    # of Chrome's own, as Submit in online-bridge.png did in some of the runs, and
    # pngquant then chooses other colours for the whole picture.
    in_order(source("settle"), "page.mouse.move(0, 0)", "page.evaluate(SETTLE")


def test_no_page_of_a_step_stays_open_behind_the_next_step():
    # A page handed to a step as context.new_page() can't be closed by its section: it
    # goes on drawing behind the steps after it. With sixteen of them open, seven of
    # them blinking boards, the heatmap of the section people drew fewer than two
    # frames in 30 s and its screenshot timed out (#586).
    handed = [
        f"{ast.unparse(call.func)}() on line {call.lineno}"
        for call in ast.walk(TOOL)
        if isinstance(call, ast.Call)
        for argument in call.args
        if isinstance(argument, ast.Call)
        and isinstance(argument.func, ast.Attribute)
        and argument.func.attr == "new_page"
    ]
    assert not handed, f"pages that never close: {handed}"
    # The sections with a page for each step open each one alone.
    for name in ("people", "flapped"):
        assert ".new_page(" not in source(name)
        assert "alone" in called(function(name))


@pytest.mark.parametrize("name", ["blueprint_list", "online_bridge_options"])
def test_a_page_of_the_settings_opens_once_it_has_its_texts(name):
    # A search field that shows before the texts have come says "Search" for good, as
    # de/blueprints.png did in some of the runs.
    assert "settings_page" in called(function(name))
    assert ".goto(" not in source(name)


def test_the_texts_of_a_page_of_the_settings_come_before_the_page():
    in_order(
        source("settings_page"),
        "view.goto(",
        "settings_texts(view)",
        "view.evaluate(NAVIGATE, path)",
    )
    assert "ui.common.search" in source("settings_texts")


def test_the_options_of_the_bridge_show_the_address_and_never_save_themselves():
    # Their editor comes last and moves the box. A click that missed it saved the
    # options, online-bridge.png showed "Success" instead of the address, and the board
    # that started anew took the darts of the current visit from heatmap-modes.webp.
    text = source("online_bridge_options")
    in_order(
        text,
        ".cm-editor",
        "settle(view)",
        "ha-checkbox",
        "form.data.online_bridge === true",
        "ha-button",
        "ha-markdown pre",
        "'online-bridge'",
    )
    # The form before the address has words in code too: waiting for one waits for
    # nothing.
    assert "ha-markdown code" not in text


def test_the_picture_of_the_bridge_shows_its_dialog_without_the_page_behind_it():
    # The page of the integration behind the dialog counts its entities: two new ones
    # changed 2.15 % of online-bridge.png in #621, three digits and the colours that
    # pngquant chose for the rest of the picture.
    assert "page_shot" not in called(function("online_bridge_options"))
    in_order(
        source("online_bridge_options"),
        "view.evaluate(MASK_SECRET)",
        "dialog_shot(view, dialog, 'online-bridge')",
    )
    in_order(
        source("dialog_shot"),
        "dialog.locator(\"[part='dialog']\")",
        "settle(page)",
        "surface.evaluate(SURFACE)",
        "clip = whole_pixels(box)",
        "page.screenshot(path=str(path), clip=clip)",
        "cut_to_box(path, box, clip)",
        "round_corners(path, box['radius'] * box['ratio'])",
        "saved(path)",
    )
    surface = ast.literal_eval(assigned("SURFACE"))
    in_order(surface, "getBoundingClientRect()", "scrollY", "borderTopLeftRadius")
    assert "devicePixelRatio" in surface


# Every picture of a dialog of Home Assistant, by the step that takes it.
DIALOG_PICTURES = {
    "config_flow": ("setup-menu", "setup-local"),
    "board_events_dialog": ("board-events",),
    "online_bridge_options": ("online-bridge",),
    "manual_setup": ("setup-manual",),
}
# A dialog that a step opens or waits for: the tag of a dialog of Home Assistant,
# such as dialog-data-entry-flow or ha-more-info-dialog, or the event that opens
# the dialog of an entity.
DIALOG = re.compile(r"\bdialog-[a-z-]+|\bha-[a-z-]*dialog\b|\bhass-more-info\b")


@pytest.mark.parametrize(("step", "pictures"), DIALOG_PICTURES.items())
def test_every_picture_of_a_dialog_shows_the_dialog_without_the_page_behind_it(
    step, pictures
):
    # The page behind a dialog changes with what has nothing to do with the dialog:
    # the page of the integrations behind the setup counts the devices and entities of
    # each integration, and the dashboard behind the events of the board shows the
    # cards of the board. Each of them would change the picture, and pngquant would
    # then choose other colours for all of it.
    assert "page_shot" not in called(function(step))
    text = source(step)
    for picture in pictures:
        assert re.search(rf"dialog_shot\(\w+, dialog, '{picture}'\)", text), picture
    assert DIALOG.search(text)


def test_a_step_that_takes_a_picture_of_the_page_opens_no_dialog():
    # A new picture of a dialog takes dialog_shot as well.
    opened = {
        node.name: texts
        for node in TOOL.body
        if isinstance(node, ast.FunctionDef) and "page_shot" in called(node)
        if (
            texts := [
                constant.value
                for constant in ast.walk(node)
                if isinstance(constant, ast.Constant)
                and isinstance(constant.value, str)
                and DIALOG.search(constant.value)
            ]
        )
    }
    assert opened == {}


@pytest.mark.parametrize(
    "text",
    [
        "dialog-data-entry-flow",
        "ha-more-info-dialog",
        "ha-dialog-new-dashboard input",
        "new CustomEvent('hass-more-info', {bubbles: true})",
    ],
)
def test_the_tags_of_the_dialogs_are_found(text):
    assert DIALOG.search(text)


@pytest.mark.parametrize("text", ["[part='dialog']", "ha-card", "dialogs"])
def test_what_is_no_dialog_is_not_found(text):
    assert not DIALOG.search(text)


def tool(name: str) -> Callable[..., Any]:
    """A function of the tool that needs neither Playwright nor a page."""
    namespace = {"Image": Image, "ImageDraw": ImageDraw, "Path": Path, "math": math}
    code = ast.Module([function(name)], [])
    # Only the function of the tool, which can't be imported without Playwright.
    exec(compile(code, "screenshots.py", "exec"), namespace)
    return namespace[name]


# The boxes of the surfaces of three dialogs in a render of the demo, in CSS pixels.
MENU = {"x": 350.0, "y": 222.0, "width": 580.0, "height": 376.0}
# The form of the board's address and the options of the bridge stand at a fraction
# of a pixel, in the middle of the window and with a height that has one.
ADDRESS = {"x": 350.0, "y": 189.921875, "width": 580.0, "height": 440.15625}
BRIDGE = {"x": 350.0, "y": 228.453125, "width": 580.0, "height": 643.078125}


def test_a_dialog_at_whole_pixels_is_taken_as_it_stands():
    assert tool("whole_pixels")(MENU) == {
        "x": 350,
        "y": 222,
        "width": 580,
        "height": 376,
    }


def test_a_dialog_at_a_fraction_of_a_pixel_is_taken_with_the_whole_pixels_around_it():
    assert tool("whole_pixels")(ADDRESS) == {
        "x": 350,
        "y": 189,
        "width": 580,
        "height": 442,
    }


def cut(tmp_path: Path, box: dict[str, float], above: int, below: int) -> Image.Image:
    """The picture of the clip around the box, cut: the dialog with the rows of the
    page above and below it that Chromium drew at twice the size."""
    clip = tool("whole_pixels")(box)
    width, height = clip["width"] * 2, clip["height"] * 2
    path = tmp_path / "dialog.png"
    image = Image.new("RGB", (width, height), (28, 28, 28))
    image.paste((17, 17, 17), (0, 0, width, above))
    image.paste((5, 5, 5), (0, height - below, width, height))
    image.save(path)
    tool("cut_to_box")(path, {**box, "ratio": 2}, clip)
    with Image.open(path) as picture:
        picture.load()
        return picture


def colours(image: Image.Image) -> list[tuple[int, int, int]]:
    return [colour for _, colour in image.getcolors()]


def test_a_dialog_at_whole_pixels_keeps_every_pixel(tmp_path):
    image = cut(tmp_path, MENU, 0, 0)
    assert image.size == (1160, 752)


def test_a_dialog_at_a_fraction_of_a_pixel_shows_none_of_the_page_behind_it(tmp_path):
    # In a render, Chromium drew the form of the address from the third row of the
    # clip to the last but two: the page above it and its shadow below.
    image = cut(tmp_path, ADDRESS, 2, 2)
    assert image.size == (1160, 880)
    assert colours(image) == [(28, 28, 28)]


def test_a_dialog_drawn_beyond_its_box_loses_only_its_own_colour(tmp_path):
    # Chromium drew the options of the bridge on every row of the clip, also on the
    # first and the last, which their box covers only a tenth of.
    image = cut(tmp_path, BRIDGE, 0, 0)
    assert image.size == (1160, 1286)
    assert colours(image) == [(28, 28, 28)]


def test_a_pixel_that_a_dialog_covers_only_in_part_is_left_out(tmp_path):
    # An edge in the middle of a pixel of the screen, which Chromium may draw on the
    # pixel inside or outside it.
    box = {"x": 350.25, "y": 100.25, "width": 580.0, "height": 400.0}
    image = cut(tmp_path, box, 1, 1)
    assert image.size == (1159, 799)
    assert colours(image) == [(28, 28, 28)]


def round_corners(path: Path, radius: float) -> None:
    """round_corners() of the tool."""
    tool("round_corners")(path, radius)


def test_a_picture_of_a_dialog_is_clear_outside_its_round_corners(tmp_path):
    path = tmp_path / "dialog.png"
    Image.new("RGB", (200, 100), (28, 28, 28)).save(path)
    round_corners(path, 24)
    with Image.open(path) as image:
        assert image.size == (200, 100)
        alpha = image.getchannel("A")
        colours = image.convert("RGB")
    for corner in [(0, 0), (199, 0), (0, 99), (199, 99), (3, 3), (196, 96)]:
        assert alpha.getpixel(corner) == 0, corner
    # The edges between the corners and everything inside stay as they were.
    for inside in [(24, 24), (100, 0), (0, 50), (199, 50), (100, 99), (100, 50)]:
        assert alpha.getpixel(inside) == 255, inside
        assert colours.getpixel(inside) == (28, 28, 28)
    # The arc of a corner fades instead of stepping.
    arc = [alpha.getpixel((x, y)) for x in range(24) for y in range(24)]
    assert len({value for value in arc if 0 < value < 255}) > 4


def test_the_round_corners_of_a_dialog_come_out_the_same_every_time(tmp_path):
    pictures = []
    for name in ["first.png", "second.png"]:
        path = tmp_path / name
        Image.new("RGB", (120, 80), (28, 28, 28)).save(path)
        round_corners(path, 13.5)
        pictures.append(path.read_bytes())
    assert pictures[0] == pictures[1]


def test_the_field_of_assist_has_its_focus_before_its_first_picture():
    # The dialog gives it the focus seconds after it shows on a busy runner, in some
    # runs not at all, and its label moves up with that: the first frames of
    # manual-voice.webp differed from run to run.
    in_order(
        source("manual_voice_animation"),
        "field.wait_for(",
        "give_focus(board, field)",
        "recorder.shot(700)",
    )
    # It looks again after the focus has come: the dialog may still take it away.
    in_order(
        source("give_focus"),
        "settle(page)",
        "matches(':focus')",
        "kept == 3",
        "field.focus()",
    )


def test_the_pictures_that_flapped_render_twice_from_fresh_demos():
    assert {"blueprints_page", "online_bridge_options", "heatmap_animation"} <= set(
        called(function("flapped"))
    )
    assert "manual_voice_animation" in called(function("manual_board"))

    tool = workflow("twice.yml")
    assert tool[True]["schedule"]
    assert "workflow_dispatch" in tool[True]
    assert "tests/e2e/screenshots.py" in tool[True]["push"]["paths"]
    job = tool["jobs"]["twice"]
    assert job["strategy"]["matrix"]["language"] == ["en", "de"]
    renders = [
        step
        for step in job["steps"]
        if "tests/e2e/screenshots.sh" in step.get("run", "")
    ]
    assert len(renders) == 2
    for step in renders:
        assert step["env"]["SCREENSHOT_SECTIONS"] == "flapped,manual"
        assert step["env"]["SCREENSHOT_GROUP"] == f"1/{len(GROUPS)}"
        assert step["env"]["LANGUAGES"] == "${{ matrix.language }}"
    folders = [step["env"]["IMAGES"] for step in renders]
    assert len(set(folders)) == 2
    (compared,) = [
        step for step in job["steps"] if "tests/e2e/compare.py" in step.get("run", "")
    ]
    in_order(compared["run"], folders[0], folders[1], "--twice")


def test_the_sections_beside_the_groups_are_functions_of_the_tool():
    beside = assigned("BESIDE_THE_GROUPS")
    assert isinstance(beside, ast.Dict)
    functions = {node.name for node in TOOL.body if isinstance(node, ast.FunctionDef)}
    assert {value.id for value in beside.values} <= functions
    assert not {ast.literal_eval(key) for key in beside.keys} & set(SECTION_FUNCTIONS)


def chosen_sections(value: str) -> tuple[str, ...]:
    """What the tool renders for SCREENSHOT_SECTIONS in its second group."""
    namespace = {
        "SECTIONS": SECTION_FUNCTIONS,
        "BESIDE_THE_GROUPS": {"flapped": "flapped"},
        "GROUPS": GROUPS,
    }
    code = ast.Module([function("chosen_sections")], [])
    # Only the function of the tool, which can't be imported without Playwright.
    exec(compile(code, "screenshots.py", "exec"), namespace)
    return namespace["chosen_sections"](value, 2)


def test_the_sections_of_a_render_are_those_of_its_group_or_those_it_names():
    assert chosen_sections("") == GROUPS[1]
    assert chosen_sections("flapped,manual") == ("flapped", "manual")


def test_a_section_that_the_tool_does_not_have_stops_the_render():
    with pytest.raises(SystemExit, match=r"no sections \['nothing'\]"):
        chosen_sections("flapped,nothing")


# screenshots.sh --------------------------------------------------------------------

# Notes every call; the screenshot tool fails when a test sets $FAIL, and the first
# call whose words contain $FAIL_ONCE fails.
DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
if [[ -n "${FAIL_ONCE:-}" && "$*" == *"$FAIL_ONCE"* && $(grep -cF -- "$FAIL_ONCE" "$CALLS") == 1 ]]; then
  echo "unexpected EOF" >&2
  exit 1
fi
if [[ -n "${FAIL:-}" && "$1" == run ]]; then
  exit 1
fi
"""


def render(
    tmp_path: Path, **env: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run screenshots.sh with a stand-in for docker; the result and the docker calls."""
    docker = tmp_path / "docker"
    docker.write_text(DOCKER, encoding="utf-8", newline="\n")
    docker.chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    result = subprocess.run(
        ["bash", str(E2E / "screenshots.sh")],
        env={**os.environ, "DOCKER_BIN": docker.as_posix(), "CALLS": str(calls), **env},
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    return result, calls.read_text(encoding="utf-8").splitlines()


def runs(calls: list[str]) -> list[tuple[str, str, str]]:
    """The language, group and folder of every run of the screenshot tool."""
    found = []
    for call in calls:
        if call.startswith("run "):
            settings = dict(re.findall(r"--env (\w+)=(\S*)", call))
            found.append(
                (
                    settings["DEMO_LANGUAGE"],
                    settings["SCREENSHOT_GROUP"],
                    settings["OUTPUT"],
                )
            )
    return found


def test_every_group_renders_from_a_fresh_demo_in_turn(tmp_path):
    result, calls = render(tmp_path, LANGUAGES="en de")

    assert result.returncode == 0, result.stderr
    count = len(GROUPS)
    assert runs(calls) == [
        (language, f"{group}/{count}", "/repo/docs/images")
        for language in ("en", "de")
        for group in range(1, count + 1)
    ]
    # Each run follows a demo started anew, and the Playwright image comes once.
    starts = [index for index, call in enumerate(calls) if " up --detach " in call]
    tools = [index for index, call in enumerate(calls) if call.startswith("run ")]
    assert len(starts) == len(tools) == 2 * count
    assert all(start < tool for start, tool in zip(starts, tools, strict=True))
    assert all(tool < start for tool, start in zip(tools, starts[1:], strict=False))
    assert (
        sum(
            call.startswith("pull --quiet mcr.microsoft.com/playwright/")
            for call in calls
        )
        == 1
    )


def test_a_pull_that_the_registry_cuts_off_is_tried_again(tmp_path):
    # demo.sh pulls nothing itself: inside its "up", the cut would end the job.
    result, calls = render(
        tmp_path,
        LANGUAGES="en",
        SCREENSHOT_GROUP="1/4",
        E2E_PULL_PAUSE="0",
        FAIL_ONCE=" pull --quiet --policy missing",
    )

    assert result.returncode == 0, result.stderr
    assert sum(" pull --quiet --policy missing" in call for call in calls) == 2
    assert "failed (attempt 1 of 3); trying again in 0 s" in result.stderr
    pulled = max(i for i, call in enumerate(calls) if " pull --quiet --policy" in call)
    assert pulled < next(i for i, call in enumerate(calls) if " up " in call)


def test_a_group_that_fails_shows_its_containers_and_removes_its_browser(tmp_path):
    result, calls = render(tmp_path, LANGUAGES="en", SCREENSHOT_GROUP="1/4", FAIL="1")

    assert result.returncode == 1
    (run,) = [call for call in calls if call.startswith("run ")]
    assert "--name autodarts_demo-playwright " in run
    project = "compose --project-name autodarts_demo --file compose.yaml "
    after = [call.removeprefix(project) for call in calls[calls.index(run) + 1 :]]
    # First the browser goes, which a signal would leave running, so that no container
    # outlives the step; then the state of the containers, what they use and the end
    # of the log of Home Assistant, and the demo.
    assert after == [
        "rm --force autodarts_demo-playwright",
        "ps --all",
        "stats --no-stream",
        "exec -T homeassistant tail -n 100 /config/home-assistant.log",
        "down --volumes --remove-orphans",
    ]


def test_one_group_renders_into_the_folder_it_is_given(tmp_path):
    count = len(GROUPS)
    result, calls = render(
        tmp_path,
        LANGUAGES="de",
        SCREENSHOT_GROUP=f"2/{count}",
        IMAGES="tests/e2e/artifacts/rendered",
    )

    assert result.returncode == 0, result.stderr
    assert runs(calls) == [("de", f"2/{count}", "/repo/tests/e2e/artifacts/rendered")]
    assert f"Group 2 of {count} in de, from a fresh demo" in result.stdout


def test_the_sections_that_a_render_names_reach_the_tool(tmp_path):
    result, calls = render(
        tmp_path,
        LANGUAGES="de",
        SCREENSHOT_GROUP=f"1/{len(GROUPS)}",
        SCREENSHOT_SECTIONS="flapped,manual",
    )

    assert result.returncode == 0, result.stderr
    (tool,) = [call for call in calls if call.startswith("run ")]
    assert "--env SCREENSHOT_SECTIONS=flapped,manual " in tool


@pytest.mark.parametrize(
    ("setting", "message"),
    [
        ({"SCREENSHOT_GROUP": "0/4"}, "choose one of the 4 groups"),
        ({"SCREENSHOT_GROUP": "5/4"}, "choose one of the 4 groups"),
        ({"SCREENSHOT_GROUP": "1/2"}, "choose one of the 4 groups"),
        ({"SCREENSHOT_GROUP": "first"}, "choose one of the 4 groups"),
        ({"IMAGES": "/tmp/images"}, "below the repository root"),
        ({"IMAGES": "../images"}, "below the repository root"),
    ],
)
def test_screenshots_sh_refuses_what_it_cannot_render(tmp_path, setting, message):
    result, calls = render(tmp_path, **setting)

    assert result.returncode == 2
    assert message in result.stderr
    assert calls == []


# collect.sh ------------------------------------------------------------------------


def picture(path: Path, colour=(20, 30, 40), level: int = 6) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (6, 6), colour).save(path, compress_level=level)
    return path


@pytest.fixture
def repository(tmp_path):
    """A repository with collect.sh and compare.py, with the blueprint's screenshot tool
    that draws the differences, committed images in English, and a diagram that no
    group of the screenshot tool renders."""
    for script in ("collect.sh", "compare.py"):
        target = tmp_path / "tests" / "e2e" / script
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(E2E / script, target)
    shutil.copytree(
        ROOT / ".github" / "blueprint",
        tmp_path / ".github" / "blueprint",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (tmp_path / "docs" / "diagrams").mkdir(parents=True)
    (tmp_path / "docs" / "diagrams" / "flow.en.mmd").write_text("flowchart TB\n")
    images = tmp_path / "docs" / "images" / "en"
    picture(images / "card.png")
    picture(images / "same.png", level=1)
    picture(images / "flow-dark.png", colour=(0, 0, 0))
    picture(images / "flow-light.png", colour=(255, 255, 255))
    return tmp_path


def rendered(root: Path, group: int, name: str, **options) -> Path:
    return picture(
        root / "tests" / "e2e" / "artifacts" / f"rendered-en-{group}" / "en" / name,
        **options,
    )


def collect(root: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(root / "tests" / "e2e" / "collect.sh")],
        env={
            **os.environ,
            "LANGUAGES": "en",
            "PYTHON": Path(sys.executable).as_posix(),
            **env,
        },
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )


def test_collect_puts_the_groups_together_and_compares_them(repository):
    rendered(repository, 1, "card.png", colour=(200, 30, 40))
    # The same pixels in another file.
    rendered(repository, 2, "same.png", level=9)
    rendered(repository, 3, "new.png")
    rendered(repository, 4, "last.png")

    result = collect(repository)

    assert result.returncode == 0, result.stderr
    assert f"Put together 4 images of {len(GROUPS)} groups in en." in result.stdout
    images = repository / "docs" / "images" / "en"
    assert sorted(path.name for path in images.iterdir()) == [
        "card.png",
        "flow-dark.png",
        "flow-light.png",
        "last.png",
        "new.png",
        "same.png",
    ]
    report = json.loads(
        (repository / "tests/e2e/artifacts/visual/report.json").read_text()
    )
    assert {entry["path"]: entry["status"] for entry in report["images"]} == {
        "en/card.png": "changed",
        "en/last.png": "added",
        "en/new.png": "added",
    }
    # The diagrams and the image with the same pixels.
    assert report["unchanged"] == 3
    assert Image.open(images / "card.png").getpixel((0, 0)) == (200, 30, 40)


def test_collect_removes_an_image_that_nothing_makes_any_more(repository):
    rendered(repository, 1, "card.png")
    rendered(repository, 2, "same.png", level=1)
    rendered(repository, 3, "new.png")
    rendered(repository, 4, "last.png")
    picture(repository / "docs/images/en/gone.png")

    result = collect(repository)

    assert result.returncode == 0, result.stderr
    assert "en/gone.png comes from no group and no diagram any more; it goes." in (
        result.stdout
    )
    assert not (repository / "docs/images/en/gone.png").exists()
    report = json.loads(
        (repository / "tests/e2e/artifacts/visual/report.json").read_text()
    )
    assert {"path": "en/gone.png", "status": "removed", "share": 1.0} in report[
        "images"
    ]
    assert (repository / "docs/images/en/flow-light.png").exists()


def test_collect_takes_the_groups_under_the_keys_of_their_artifacts(repository):
    # The jobs download the artifact of each group, rendered-<language>-<group>-<key>,
    # into a folder of its name (tests/e2e/render_key.py); visual.sh leaves the
    # folders without the key.
    artifacts = repository / "tests" / "e2e" / "artifacts"
    picture(artifacts / f"rendered-en-1-{'ab' * 32}" / "en" / "card.png", (200, 30, 40))
    rendered(repository, 2, "same.png", level=1)
    picture(artifacts / f"rendered-en-3-{'cd' * 32}" / "en" / "new.png")
    picture(artifacts / f"rendered-en-4-{'ef' * 32}" / "en" / "last.png")

    result = collect(repository)

    assert result.returncode == 0, result.stderr
    assert f"Put together 4 images of {len(GROUPS)} groups in en." in result.stdout
    images = repository / "docs" / "images" / "en"
    assert Image.open(images / "card.png").getpixel((0, 0)) == (200, 30, 40)
    assert (images / "new.png").exists()


def test_collect_fails_without_the_images_of_a_group(repository):
    rendered(repository, 1, "card.png")
    rendered(repository, 3, "new.png")
    rendered(repository, 4, "last.png")
    # A group whose folder came without images counts as missing too.
    (repository / "tests/e2e/artifacts/rendered-en-2/en").mkdir(parents=True)

    result = collect(repository)

    assert result.returncode == 1
    assert (
        "No images of group 2 in en: the job of the group shows why." in result.stderr
    )
    assert not (repository / "tests/e2e/artifacts/visual").exists()


def test_collect_fails_on_an_image_that_two_groups_rendered(repository):
    rendered(repository, 1, "card.png")
    rendered(repository, 2, "card.png")
    rendered(repository, 3, "new.png")
    rendered(repository, 4, "last.png")

    result = collect(repository)

    assert result.returncode == 1
    assert "en/card.png comes from group 1 and group 2" in result.stderr


# scripts/screenshots.sh ------------------------------------------------------------

# The screenshot tool: notes its settings, and leaves an image for each name of
# $NAMES in the folder of its language, unless the test sets $FAIL; with $HANG, it
# waits until a SIGINT ends it, and notes that.
TOOL_STAND_IN = """#!/usr/bin/env bash
printf 'render %s %s %s\\n' "$LANGUAGES" "$SCREENSHOT_GROUP" "$IMAGES" >> "$CALLS"
if [[ -n "${HANG:-}" ]]; then
  trap 'kill "$sleeper"; echo interrupted >> "$CALLS"; exit 130' INT
  sleep 30 >/dev/null 2>&1 &
  sleeper=$!
  wait
fi
if [[ -n "${FAIL:-}" ]]; then
  exit 3
fi
mkdir -p "$REPOSITORY/$IMAGES/$LANGUAGES" "$REPOSITORY/tests/e2e/artifacts"
for name in ${NAMES-card.png}; do
  printf '%s %s' "$SCREENSHOT_GROUP" "$name" > "$REPOSITORY/$IMAGES/$LANGUAGES/$name"
done
group="${SCREENSHOT_GROUP%/*}"
printf '| section | 1.0 |\\n' > "$REPOSITORY/tests/e2e/artifacts/screenshots-$LANGUAGES-$group.md"
"""
# The recorder of the live demo, run by the Python that the script chose.
RECORDER_STAND_IN = """import os
import sys
from pathlib import Path

with open(os.environ["CALLS"], "a", encoding="utf-8") as calls:
    calls.write("record\\n")
target = Path(os.environ["REPOSITORY"], "docs", "demo", "timeline.json")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text("{}\\n", encoding="utf-8")
"""
# uv: notes its calls, and makes a Python in a new environment that notes its runs.
UV_STAND_IN = """#!/usr/bin/env bash
printf 'uv %s\\n' "$*" >> "$CALLS"
if [[ "$1" == venv ]]; then
  venv="${*: -1}"
  mkdir -p "$venv/bin"
  printf '#!/usr/bin/env bash\\nprintf "venv python %%s\\\\n" "$*" >> "$CALLS"\\n' > "$venv/bin/python"
  chmod +x "$venv/bin/python"
fi
"""
# GNU timeout: notes the limit that the script gives a group, and keeps it, or takes
# SHORT_LIMIT instead, so that a group that hangs runs out of time in a second.
TIMEOUT_STAND_IN = """#!/usr/bin/env bash
printf '%s\\n' "$3" >> "$LIMITS"
exec timeout "$1" "$2" "${SHORT_LIMIT:-$3}" "${@:4}"
"""


@pytest.fixture
def project(tmp_path):
    """A copy of scripts/screenshots.sh and of the settings of the bot in a
    repository of its own, with an image of each language that no group renders, and
    stand-ins for the screenshot tool, the recorder, uv and GNU timeout."""
    root = tmp_path / "repository"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(
        ROOT / "scripts" / "screenshots.sh", root / "scripts" / "screenshots.sh"
    )
    (root / ".github").mkdir()
    shutil.copy(
        ROOT / ".github" / "screenshots.toml", root / ".github" / "screenshots.toml"
    )
    (root / ".python-version").write_text("3.14\n", encoding="utf-8")
    (root / "requirements-test.txt").touch()
    for language in ("en", "de"):
        (root / "docs" / "images" / language).mkdir(parents=True)
        (root / "docs" / "images" / language / "diagram-light.png").write_text("kept")
    stand_ins = tmp_path / "stand-ins"
    stand_ins.mkdir()
    for name, text in (
        ("screenshots.sh", TOOL_STAND_IN),
        ("record_demo.py", RECORDER_STAND_IN),
        ("uv", UV_STAND_IN),
        ("timeout", TIMEOUT_STAND_IN),
    ):
        (stand_ins / name).write_text(text, encoding="utf-8", newline="\n")
        (stand_ins / name).chmod(0o755)
    (tmp_path / "calls").touch()
    (tmp_path / "limits").touch()
    (tmp_path / "runner").mkdir()
    env = {
        **os.environ,
        "REPOSITORY": str(root),
        "CALLS": str(tmp_path / "calls"),
        "SCREENSHOTS_RENDER": str(stand_ins / "screenshots.sh"),
        "SCREENSHOTS_RECORD": str(stand_ins / "record_demo.py"),
        "PYTHON": sys.executable,
        "UV": str(stand_ins / "uv"),
        "SCREENSHOTS_TIMEOUT": str(stand_ins / "timeout"),
        "LIMITS": str(tmp_path / "limits"),
        "RUNNER_TEMP": str(tmp_path / "runner"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }
    for name in ("SCREENSHOTS_SHARD", "SHORT_LIMIT", "FAIL", "HANG", "NAMES"):
        env.pop(name, None)
    return root, env


def shard(
    project: tuple[Path, dict[str, str]], **env: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run the copy of scripts/screenshots.sh; the result and the calls of the
    stand-ins."""
    root, base = project
    result = subprocess.run(
        ["bash", str(root / "scripts" / "screenshots.sh")],
        env={**base, **env},
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    calls = Path(base["CALLS"]).read_text(encoding="utf-8").splitlines()
    return result, calls


def test_a_shard_renders_its_group_into_a_folder_and_over_its_language(project):
    root, env = project
    (root / "docs" / "images" / "de" / "card.png").write_text("committed")

    result, calls = shard(project, SCREENSHOTS_SHARD="de-3", NAMES="card.png new.webp")

    assert result.returncode == 0, result.stderr
    assert calls == ["render de 3/4 tests/e2e/artifacts/rendered-de-3"]
    images = root / "docs" / "images"
    assert (images / "de" / "card.png").read_text() == "3/4 card.png"
    assert (images / "de" / "new.webp").read_text() == "3/4 new.webp"
    # Only its own images: the bot deletes none, and the other language stays.
    assert (images / "de" / "diagram-light.png").read_text() == "kept"
    assert sorted(path.name for path in (images / "en").iterdir()) == [
        "diagram-light.png"
    ]
    assert "Group 3 of 4 in de: 2 images in docs/images/de." in result.stdout
    # The seconds of its sections in the summary of the job.
    assert Path(env["GITHUB_STEP_SUMMARY"]).read_text() == "| section | 1.0 |\n"


def test_a_shard_renders_its_group_anew_into_an_empty_folder(project):
    root, _ = project
    old = root / "tests" / "e2e" / "artifacts" / "rendered-en-1" / "en" / "old.png"
    old.parent.mkdir(parents=True)
    old.write_text("an earlier render")

    result, _ = shard(project, SCREENSHOTS_SHARD="en-1")

    assert result.returncode == 0, result.stderr
    assert not old.exists()
    assert not (root / "docs" / "images" / "en" / "old.png").exists()


def test_without_a_shard_every_group_and_the_recording_render_in_turn(project):
    root, env = project
    del env["GITHUB_STEP_SUMMARY"]

    result, calls = shard(project)

    assert result.returncode == 0, result.stderr
    count = len(GROUPS)
    assert calls == [
        f"render {language} {group}/{count} "
        f"tests/e2e/artifacts/rendered-{language}-{group}"
        for language in ("en", "de")
        for group in range(1, count + 1)
    ] + ["record"]
    assert (root / "docs" / "demo" / "timeline.json").read_text() == "{}\n"


def test_the_shard_timeline_records_the_live_demo_alone(project):
    root, _ = project

    result, calls = shard(project, SCREENSHOTS_SHARD="timeline")

    assert result.returncode == 0, result.stderr
    assert calls == ["record"]
    assert (root / "docs" / "demo" / "timeline.json").read_text() == "{}\n"


def test_the_recording_takes_a_python_that_uv_makes_for_the_project(project):
    root, env = project
    del env["PYTHON"]
    venv = Path(env["RUNNER_TEMP"]) / "homedarts-recording"
    (venv / "left").mkdir(parents=True)

    result, calls = shard(project, SCREENSHOTS_SHARD="timeline")

    assert result.returncode == 0, result.stderr
    # A fresh environment outside the repository, with the Python of
    # .python-version and the locked packages of the tests.
    assert calls == [
        f"uv venv --quiet --python 3.14 {venv}",
        f"uv pip install --quiet --python {venv} --require-hashes"
        f" -r {root}/requirements-test.txt",
        f"venv python {env['SCREENSHOTS_RECORD']}",
    ]
    assert not (venv / "left").exists()


def test_the_recording_without_python_or_uv_says_what_it_needs(project):
    _, env = project
    del env["PYTHON"]

    result, calls = shard(project, SCREENSHOTS_SHARD="timeline", UV="no-such-uv")

    assert result.returncode == 1
    assert "set PYTHON to a Python that has them, or install uv" in result.stderr
    assert calls == []


def test_a_group_that_fails_to_render_fails_its_shard(project):
    root, _ = project

    result, calls = shard(project, SCREENSHOTS_SHARD="en-2", FAIL="1")

    assert result.returncode == 3
    assert calls == ["render en 2/4 tests/e2e/artifacts/rendered-en-2"]
    folder = root / "docs" / "images" / "en"
    assert sorted(path.name for path in folder.iterdir()) == ["diagram-light.png"]


def limits(project: tuple[Path, dict[str, str]]) -> list[str]:
    """The time limits that the script gave its groups, in turn."""
    return Path(project[1]["LIMITS"]).read_text(encoding="utf-8").splitlines()


def test_a_group_that_hangs_gets_a_sigint_and_fails_its_shard(project):
    # The screenshot tool gets the signal itself, ends its demo and prints the state
    # of its containers, before the step of the bot runs out of time.
    result, calls = shard(project, SCREENSHOTS_SHARD="de-1", HANG="1", SHORT_LIMIT="1s")

    assert result.returncode == 124
    assert calls == ["render de 1/4 tests/e2e/artifacts/rendered-de-1", "interrupted"]
    assert "Group 1 in de took longer than 18m" in result.stderr
    assert limits(project) == ["18m"]


def test_a_group_ends_three_minutes_before_the_step_that_renders_its_shard(project):
    # GitHub's SIGINT at the end of the step would reach the script alone, and the
    # runner kills what still runs ten seconds later. The group gets its own SIGINT
    # and two minutes more to clean up, and still fails before the step does.
    settings = tomllib.loads(
        (ROOT / ".github" / "screenshots.toml").read_text(encoding="utf-8")
    )
    step = settings["timeout_minutes"]

    result, _ = shard(project, SCREENSHOTS_SHARD="en-2")

    assert result.returncode == 0, result.stderr
    assert limits(project) == [f"{step - 3}m"]
    script = (ROOT / "scripts" / "screenshots.sh").read_text(encoding="utf-8")
    assert 'TIMEOUT="${SCREENSHOTS_TIMEOUT:-timeout}"' in script
    command = '"${TIMEOUT}" --signal=INT --kill-after=2m "${LIMIT}" bash "${RENDER}"'
    assert command in script
    # The bot takes the same limit for the step.
    assert blueprint_screenshots().settings(ROOT).timeout_minutes == step


def test_without_a_time_limit_of_the_step_a_group_ends_before_its_45_minutes(project):
    # The bot gives the step the most that it may set, and so does the script.
    root, _ = project
    toml = root / ".github" / "screenshots.toml"
    toml.write_text(
        "".join(
            line
            for line in toml.read_text(encoding="utf-8").splitlines(keepends=True)
            if not line.startswith("timeout_minutes")
        ),
        encoding="utf-8",
    )
    assert blueprint_screenshots().settings(root).timeout_minutes is None

    result, _ = shard(project, SCREENSHOTS_SHARD="de-4")

    assert result.returncode == 0, result.stderr
    assert limits(project) == [f"{blueprint_screenshots().MOST_MINUTES - 3}m"]


@pytest.mark.parametrize("minutes", [1, 3])
def test_a_time_limit_of_the_step_that_leaves_a_group_no_time_fails_at_once(
    project, minutes
):
    root, _ = project
    toml = root / ".github" / "screenshots.toml"
    toml.write_text(
        re.sub(
            r"^timeout_minutes = \d+$",
            f"timeout_minutes = {minutes}",
            toml.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        ),
        encoding="utf-8",
    )

    result, calls = shard(project, SCREENSHOTS_SHARD="en-1")

    assert result.returncode == 2
    assert calls == []
    assert f"timeout_minutes = {minutes} in .github/screenshots.toml" in result.stderr


def test_a_group_that_rendered_no_image_fails_its_shard(project):
    result, _ = shard(project, SCREENSHOTS_SHARD="en-4", NAMES="")

    assert result.returncode == 1
    assert "Group 4 in en rendered no image" in result.stderr


@pytest.mark.parametrize(
    "name", ["fr-1", "en-0", "en-5", "en", "EN-1", "en-1 ", "timelines", "all"]
)
def test_scripts_screenshots_sh_refuses_a_shard_it_does_not_have(project, name):
    result, calls = shard(project, SCREENSHOTS_SHARD=name)

    assert result.returncode == 2
    assert "choose timeline or a language of en de and a group of 1 to 4" in (
        result.stderr
    )
    assert calls == []


def test_scripts_screenshots_sh_runs_the_screenshot_tool_and_the_recorder():
    script = (ROOT / "scripts" / "screenshots.sh").read_text(encoding="utf-8")
    assert "${REPOSITORY_ROOT}/tests/e2e/screenshots.sh}" in script
    assert "${REPOSITORY_ROOT}/scripts/record_demo.py}" in script
    assert (E2E / "screenshots.sh").is_file()
    assert (ROOT / "scripts" / "record_demo.py").is_file()


# The comment of the visual check ---------------------------------------------------

COMMENT = workflow("visual-comment.yml")["jobs"]["comment"]["steps"]

COMMENT_GH = """#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CALLS"
case "$*" in
  "pr view "*) echo "$HEAD_SHA" ;;
  "api repos/"*"/artifacts "*) cat "$ARTIFACTS" ;;
  "run download "*) cp -R "$DOWNLOADS"/. "${*: -1}" ;;
esac
"""


@pytest.fixture
def comment(tmp_path):
    """The reports that a run of the visual check left, and stand-ins for gh and
    python3 to write the comment of the run from them."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(COMMENT_GH, encoding="utf-8", newline="\n")
    gh.chmod(0o755)
    python3 = bin_dir / "python3"
    python3.write_text(
        f'#!/usr/bin/env bash\nexec "{Path(sys.executable).as_posix()}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    python3.chmod(0o755)
    (tmp_path / "downloads").mkdir()
    (tmp_path / "runner").mkdir()
    (tmp_path / "artifacts").touch()
    (tmp_path / "calls").touch()
    head = "0123456789abcdef"
    return tmp_path, {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "RUNNER_TEMP": str(tmp_path / "runner"),
        "GITHUB_SERVER_URL": "https://github.com",
        "GH_REPO": "owner/repo",
        "RUN_ID": "99",
        "RUN_URL": "https://github.com/owner/repo/actions/runs/99",
        "HEAD_SHA": head,
        "PULL_REQUESTS": json.dumps([{"number": 7, "head": {"sha": head}}]),
        "CALLS": str(tmp_path / "calls"),
        "ARTIFACTS": str(tmp_path / "artifacts"),
        "DOWNLOADS": str(tmp_path / "downloads"),
    }


def report_of(root: Path, language: str, images: list[dict], unchanged: int) -> None:
    """The report of a language that rendered, as the job compare uploads it."""
    folder = root / "downloads" / f"visual-{language}"
    folder.mkdir()
    (folder / "report.json").write_text(
        json.dumps({"images": images, "unchanged": unchanged})
    )
    with (root / "artifacts").open("a") as file:
        file.write(f"visual-{language} {100 + len(language)}\n")


def write_comment(
    root: Path, env: dict[str, str], conclusion: str
) -> tuple[subprocess.CompletedProcess[str], str, str]:
    (script,) = [
        step["run"]
        for step in COMMENT
        if step.get("name") == "Write the comment from the reports of the check"
    ]
    result = subprocess.run(
        ["bash", "-c", script],
        env={**env, "CONCLUSION": conclusion},
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    written = root / "runner" / "visual" / "comment.md"
    text = written.read_text(encoding="utf-8") if written.exists() else ""
    return result, text, (root / "calls").read_text(encoding="utf-8")


@needs_jq
def test_the_comment_lists_the_language_that_rendered_when_the_other_failed(comment):
    root, env = comment
    changed = {"path": "de/card.png", "status": "changed", "share": 0.25}
    report_of(root, "de", [changed], unchanged=77)
    # The render jobs of a failed group leave artifacts of their own.
    with (root / "artifacts").open("a") as file:
        file.write("rendered-de-1 1\nvisual-failure-en-2-1 2\n")

    result, text, calls = write_comment(root, env, "failure")

    assert result.returncode == 0, result.stderr
    assert "run download 99 --pattern visual-?? " in calls
    assert "1 of 78 German images look different" in text
    assert "| `docs/images/de/card.png` | changed | 25.00 % |" in text
    assert "[German](https://github.com/owner/repo/actions/runs/99/artifacts/102)" in (
        text
    )
    assert "The English images could not be rendered for 0123456" in text
    assert "api --method POST repos/owner/repo/issues/7/comments " in calls


@needs_jq
def test_the_comment_asks_to_delete_an_image_that_no_group_renders_any_more(comment):
    # Each shard of the screenshot bot renders one group and deletes nothing, so the
    # pull request that drops an image deletes it.
    root, env = comment
    removed = {"path": "en/old-card.png", "status": "removed", "share": 1.0}
    changed = {"path": "en/card.png", "status": "changed", "share": 0.5}
    report_of(root, "en", [removed, changed], unchanged=10)
    report_of(root, "de", [], unchanged=12)

    result, text, _ = write_comment(root, env, "success")

    assert result.returncode == 0, result.stderr
    assert "| `docs/images/en/old-card.png` | removed | 100 % |" in text
    assert (
        "No group renders `docs/images/en/old-card.png` any more, and the screenshot"
        " bot deletes no image: delete it in this pull request"
    ) in text
    assert "`docs/images/en/card.png` any more" not in text


@needs_jq
def test_a_comment_without_a_removed_image_asks_for_no_deletion(comment):
    root, env = comment
    report_of(root, "en", [{"path": "en/card.png", "status": "added", "share": 1.0}], 3)
    report_of(root, "de", [], unchanged=4)

    result, text, _ = write_comment(root, env, "success")

    assert result.returncode == 0, result.stderr
    assert "| `docs/images/en/card.png` | added | 100 % |" in text
    assert "deletes no image" not in text


@needs_jq
def test_the_comment_names_the_failed_language_also_when_the_other_looks_the_same(
    comment,
):
    root, env = comment
    report_of(root, "en", [], unchanged=78)

    result, text, calls = write_comment(root, env, "failure")

    assert result.returncode == 0, result.stderr
    assert "every English image looks as committed" in text
    assert "The German images could not be rendered" in text
    # A failure is worth a comment even without an earlier one.
    assert "api --method POST " in calls


@needs_jq
def test_the_comment_says_why_when_no_language_rendered(comment):
    root, env = comment
    (root / "artifacts").write_text("visual-failure-en-1-1 1\n")

    result, text, calls = write_comment(root, env, "failure")

    assert result.returncode == 0, result.stderr
    assert "run download" not in calls
    assert "The images could not be rendered for 0123456; the [run](" in text
    assert "api --method POST " in calls


@needs_jq
def test_the_comment_of_two_languages_that_look_the_same_stays_away(comment):
    root, env = comment
    report_of(root, "en", [], unchanged=78)
    report_of(root, "de", [], unchanged=78)

    result, text, calls = write_comment(root, env, "success")

    assert result.returncode == 0, result.stderr
    assert "every image looks as committed" in text
    assert "could not be rendered" not in text
    assert "needs no comment" in result.stdout
    assert "--method POST" not in calls
