"""The screenshot tool renders the images of the documentation in fixed groups, each
from a fresh demo, so that the visual check and the screenshot bot render the groups
side by side on runners of their own and put them together afterwards.

The scripts run here as the workflows run them: screenshots.sh with a stand-in for
docker, collect.sh with compare.py, and the steps of the screenshot bot in bash with
stand-ins for gh and a repository of their own."""

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from PIL import Image

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
# The runners of GitHub have jq, which the bot reads its reports with.
needs_jq = pytest.mark.skipif(
    shutil.which("jq") is None, reason="the bot reads with jq"
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


GROUPS = ast.literal_eval(assigned("GROUPS"))
SECONDS = ast.literal_eval(assigned("SECONDS"))
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
        r"^GROUP_COUNT=(\d+)$", (E2E / script).read_text(encoding="utf-8"), re.M
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
    # The players card shows the five players of the tournament of "more games".
    people = GROUPS[group_of["people"]]
    assert people.index("more games") < people.index("people")
    # The darts of the bot follow the fixed random numbers of the demo: its first
    # match is that of the corrections, as before the groups, and then the formats.
    bot = GROUPS[group_of["corrections"]]
    assert bot.index("corrections") < bot.index("formats")
    # A second board would be the first of the cards without one, and the weekly
    # report starts a new week: both come last in their group.
    manual = GROUPS[group_of["manual"]]
    assert manual[-2:] == ("calendar", "manual")


def test_no_group_takes_much_longer_than_the_shortest():
    # The runs of a language wait for their slowest group: by the measured seconds
    # of its sections, none takes more than SLOWER times as long as the shortest.
    assert sorted(SECONDS) == sorted(SECTION_FUNCTIONS)
    totals = {
        number: sum(SECONDS[section] for section in group)
        for number, group in enumerate(GROUPS, 1)
    }
    assert group_times.slow(totals) == {}, totals


def test_every_section_may_take_twice_its_seconds_before_the_watchdog_fails_it():
    assert set(BUDGETS) <= set(SECONDS)
    for section, seconds in SECONDS.items():
        assert BUDGETS.get(section, SECTION_BUDGET) >= 2 * seconds, section


def test_the_big_tournaments_stop_at_their_pictures():
    # No image shows a match after the picture; the tests of the tournament formats
    # play 32 players to their champion instead (tests/test_tournament_formats.py).
    (big,) = [
        node
        for node in TOOL.body
        if isinstance(node, ast.FunctionDef) and node.name == "big_tournament"
    ]
    played = [
        node
        for node in ast.walk(big)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "play_tournament"
    ]
    assert [[ast.unparse(argument) for argument in call.args] for call in played] == [
        ["page", "before"]
    ]


@pytest.mark.parametrize("script", ["screenshots.sh", "collect.sh"])
def test_the_scripts_know_how_many_groups_there_are(script):
    assert group_count(script) == len(GROUPS)


@pytest.mark.parametrize(
    ("name", "jobs"),
    [("visual.yml", ("compare",)), ("screenshots.yml", ("collect", "pull-request"))],
)
def test_the_workflows_render_every_group_on_a_runner_of_its_own(name, jobs):
    count = len(GROUPS)
    render = workflow(name)["jobs"]["render"]
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
    assert (
        upload["with"]["name"] == "rendered-${{ matrix.language }}-${{ matrix.group }}"
    )
    # One group that fails cancels neither the other groups nor what comes after.
    assert render["strategy"]["fail-fast"] is False
    for job in jobs:
        assert "!cancelled()" in workflow(name)["jobs"][job]["if"]


@pytest.mark.parametrize(
    ("name", "job"), [("visual.yml", "compare"), ("screenshots.yml", "collect")]
)
def test_the_job_of_a_language_lists_how_long_its_groups_took(name, job):
    steps = workflow(name)["jobs"]["render"]["steps"]
    names = [step.get("name") for step in steps]
    listed = steps[names.index("List how long the sections took")]
    # The seconds of the group go with its images, before they are kept.
    assert (
        'cp "$times" tests/e2e/artifacts/rendered/' in listed["run"]
        and "tests/e2e/artifacts/screenshots-*.json" in listed["run"]
    )
    assert names.index("List how long the sections took") < names.index(
        "Keep the images of the group"
    )
    (table,) = [
        step
        for step in workflow(name)["jobs"][job]["steps"]
        if "group_times.py" in step.get("run", "")
    ]
    assert table["if"] == "${{ !cancelled() }}"
    assert table["env"]["LANGUAGE"] == "${{ matrix.language }}"
    assert table["run"] == (
        'python3 tests/e2e/group_times.py "$LANGUAGE" tests/e2e/artifacts'
        ' >> "$GITHUB_STEP_SUMMARY"'
    )


def test_the_bot_runs_nothing_in_a_fork():
    for job in workflow("screenshots.yml")["jobs"].values():
        assert "!github.event.repository.fork" in job["if"]


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


# screenshots.sh --------------------------------------------------------------------

# Notes every call; the screenshot tool fails when a test sets $FAIL.
DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
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


def test_a_group_that_fails_shows_its_containers_and_removes_its_browser(tmp_path):
    result, calls = render(tmp_path, LANGUAGES="en", SCREENSHOT_GROUP="1/3", FAIL="1")

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


@pytest.mark.parametrize(
    ("setting", "message"),
    [
        ({"SCREENSHOT_GROUP": "0/3"}, "choose one of the 3 groups"),
        ({"SCREENSHOT_GROUP": "4/3"}, "choose one of the 3 groups"),
        ({"SCREENSHOT_GROUP": "1/2"}, "choose one of the 3 groups"),
        ({"SCREENSHOT_GROUP": "first"}, "choose one of the 3 groups"),
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
    """A repository with collect.sh and compare.py, committed images in English, and
    a diagram that no group of the screenshot tool renders."""
    for script in ("collect.sh", "compare.py"):
        target = tmp_path / "tests" / "e2e" / script
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(E2E / script, target)
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

    result = collect(repository)

    assert result.returncode == 0, result.stderr
    assert f"Put together 3 images of {len(GROUPS)} groups in en." in result.stdout
    images = repository / "docs" / "images" / "en"
    assert sorted(path.name for path in images.iterdir()) == [
        "card.png",
        "flow-dark.png",
        "flow-light.png",
        "new.png",
        "same.png",
    ]
    report = json.loads(
        (repository / "tests/e2e/artifacts/visual/report.json").read_text()
    )
    assert {entry["path"]: entry["status"] for entry in report["images"]} == {
        "en/card.png": "changed",
        "en/new.png": "added",
    }
    # The diagrams and the image with the same pixels.
    assert report["unchanged"] == 3
    assert Image.open(images / "card.png").getpixel((0, 0)) == (200, 30, 40)
    # The bot takes the rendered images alone: main may have newer diagrams.
    collected = repository / "tests/e2e/artifacts/collected/en"
    assert sorted(path.name for path in collected.iterdir()) == [
        "card.png",
        "new.png",
        "same.png",
    ]
    assert (collected / "card.png").read_bytes() == (images / "card.png").read_bytes()


def test_collect_removes_an_image_that_nothing_makes_any_more(repository):
    rendered(repository, 1, "card.png")
    rendered(repository, 2, "same.png", level=1)
    rendered(repository, 3, "new.png")
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


def test_collect_restores_the_committed_file_of_an_unchanged_image(repository):
    committed = (repository / "docs/images/en/same.png").read_bytes()
    for group, name in ((1, "card.png"), (2, "same.png"), (3, "other.png")):
        rendered(repository, group, name, level=9)

    result = collect(repository, RESTORE="1")

    assert result.returncode == 0, result.stderr
    assert (repository / "docs/images/en/same.png").read_bytes() == committed
    collected = repository / "tests/e2e/artifacts/collected/en/same.png"
    assert collected.read_bytes() == committed


def test_collect_fails_without_the_images_of_a_group(repository):
    rendered(repository, 1, "card.png")
    rendered(repository, 3, "new.png")
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

    result = collect(repository)

    assert result.returncode == 1
    assert "en/card.png comes from group 1 and group 2" in result.stderr


# The pull request of the screenshot bot ----------------------------------------------

BOT = workflow("screenshots.yml")["jobs"]["pull-request"]["steps"]

GH = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
case "$*" in
  "pr list "*) echo "${PR_LIST:-[]}" ;;
  "api --paginate repos/"*"/files "*) cat "$PR_FILES" ;;
  "api users/"*) echo 4242 ;;
  "api graphql "*)
    cp "${*: -3:1}" "$COMMITS/commit-$(ls "$COMMITS" | wc -l).json"
    echo "c0ffee"
    ;;
esac
"""


# The open pull request of the bot, as gh pr list shows it.
OWN = {
    "isCrossRepository": False,
    "author": {"login": "app/release-app", "is_bot": True},
}


def pulls(*numbers: int, **more: dict) -> str:
    """The open pull requests of the bot's branch: the bot's own ones by number,
    and others as given."""
    return json.dumps([*more.values(), *({"number": n, **OWN} for n in numbers)])


def step(name: str) -> str:
    (run,) = [item["run"] for item in BOT if item.get("name") == name]
    return run


def git(cwd: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, encoding="utf-8", check=True
    ).stdout


@pytest.fixture
def own_repositories(monkeypatch):
    """Git's variables that point it at another repository, such as GIT_DIR, which
    Git sets for its hooks in a worktree, are gone: the commits of the bot's tests
    land in their own repositories, never in the one that runs the tests."""
    for name in git(Path.cwd(), "rev-parse", "--local-env-vars").split():
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def bot(tmp_path, own_repositories):
    """main with images in both languages and the recording of the live demo, an
    open pull request of the bot that changed a German image, and the rendered
    English images of a run."""
    origin, clone = tmp_path / "origin.git", tmp_path / "clone"
    git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
    git(tmp_path, "clone", "--quiet", str(origin), str(clone))
    for command in (
        ("config", "user.name", "Test"),
        ("config", "user.email", "test@example.com"),
    ):
        git(clone, *command)
    picture(clone / "docs/images/en/card.png")
    picture(clone / "docs/images/de/card.png")
    picture(clone / "docs/images/de/other.png")
    (clone / "docs/demo").mkdir(parents=True)
    (clone / "docs/demo/timeline.json").write_text('{"steps":[]}\n')
    git(clone, "add", "--all")
    git(clone, "commit", "--quiet", "-m", "main")
    git(clone, "push", "--quiet", "origin", "main")
    # The earlier run of the bot changed a German image in its pull request.
    git(clone, "switch", "--quiet", "-c", "bot")
    picture(clone / "docs/images/de/card.png", colour=(1, 2, 3))
    git(clone, "commit", "--quiet", "-am", "earlier images")
    git(clone, "push", "--quiet", "origin", "bot:refs/heads/bot/screenshots")
    git(clone, "push", "--quiet", "origin", "bot:refs/pull/7/head")
    git(clone, "switch", "--quiet", "main")

    temp = tmp_path / "runner"
    picture(temp / "rendered/images-en/card.png", colour=(9, 9, 9))
    (temp / "rendered/report-en").mkdir(parents=True)
    (temp / "rendered/report-en/report.json").write_text(
        json.dumps(
            {"images": [{"path": "en/card.png", "status": "changed", "share": 1.0}]}
        )
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(GH, encoding="utf-8", newline="\n")
    gh.chmod(0o755)
    # The runners call Python 3 as python3.
    python3 = bin_dir / "python3"
    python3.write_text(
        f'#!/usr/bin/env bash\nexec "{Path(sys.executable).as_posix()}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    python3.chmod(0o755)
    (tmp_path / "commits").mkdir()
    files = tmp_path / "files"
    files.write_text("docs/images/de/card.png\n")
    for name in ("output", "calls"):
        (tmp_path / name).touch()
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "RUNNER_TEMP": str(temp),
        "GITHUB_OUTPUT": str(tmp_path / "output"),
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_RUN_ID": "99",
        "SHA": "abc1234",
        "APP_SLUG": "release-app",
        "CALLS": str(tmp_path / "calls"),
        "COMMITS": str(tmp_path / "commits"),
        "PR_FILES": str(files),
    }
    return clone, env


def run(
    clone: Path, script: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-e", "-c", script],
        cwd=clone,
        env=env,
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )


def place(
    clone: Path, env: dict[str, str]
) -> tuple[subprocess.CompletedProcess[str], str]:
    result = run(clone, step("Put the rendered images in place"), env)
    outputs = Path(env["GITHUB_OUTPUT"]).read_text(encoding="utf-8")
    return result, outputs


def publish(
    clone: Path, env: dict[str, str], **more: str
) -> tuple[subprocess.CompletedProcess[str], str]:
    result = run(
        clone, step("Open or update the pull request of the images"), {**env, **more}
    )
    return result, Path(env["CALLS"]).read_text(encoding="utf-8")


def commits(env: dict[str, str]) -> list[dict]:
    return [
        json.loads(path.read_text())["variables"]["input"]
        for path in sorted(Path(env["COMMITS"]).iterdir())
    ]


@needs_jq
def test_the_bot_puts_every_language_that_rendered_in_place(bot):
    clone, env = bot
    temp = Path(env["RUNNER_TEMP"]) / "rendered"
    picture(temp / "images-de/card.png", colour=(5, 5, 5))
    (temp / "report-de").mkdir()
    removed = [
        {"path": "de/other.png", "status": "removed", "share": 1.0},
        # Nothing but an image of its own language goes.
        {"path": "de/../../README.md", "status": "removed", "share": 1.0},
        {"path": "en/card.png", "status": "removed", "share": 1.0},
    ]
    (temp / "report-de/report.json").write_text(json.dumps({"images": removed}))
    # A diagram that main got after the images were rendered stays as it is.
    picture(clone / "docs/images/de/flow-dark.png")
    (clone / "README.md").write_text("Read me")

    result, outputs = place(clone, env)

    assert result.returncode == 0, result.stderr
    assert outputs == "missing=\n"
    assert Image.open(clone / "docs/images/de/card.png").getpixel((0, 0)) == (5, 5, 5)
    assert Image.open(clone / "docs/images/en/card.png").getpixel((0, 0)) == (9, 9, 9)
    assert not (clone / "docs/images/de/other.png").exists()
    assert (clone / "docs/images/de/flow-dark.png").exists()
    assert (clone / "README.md").exists()


@needs_jq
def test_a_language_that_did_not_render_stays_as_it_is(bot):
    clone, env = bot

    result, outputs = place(clone, env)

    assert result.returncode == 0, result.stderr
    assert outputs == "missing=de\n"
    assert "::warning::The images in de did not render" in result.stdout
    assert Image.open(clone / "docs/images/en/card.png").getpixel((0, 0)) == (9, 9, 9)
    assert git(clone, "status", "--short", "--", "docs/images/de") == ""


@needs_jq
def test_the_bot_brings_a_new_recording_of_the_live_demo(bot):
    clone, env = bot
    recording = Path(env["RUNNER_TEMP"]) / "rendered/timeline/timeline.json"
    recording.parent.mkdir(parents=True)
    recording.write_text('{"steps":[1]}\n')

    result, _ = place(clone, env)

    assert result.returncode == 0, result.stderr
    assert (clone / "docs/demo/timeline.json").read_text() == '{"steps":[1]}\n'
    result, _ = publish(clone, env, MISSING="de", PR_LIST=pulls(7))
    assert result.returncode == 0, result.stderr
    (commit,) = commits(env)
    added = {item["path"] for item in commit["fileChanges"]["additions"]}
    assert "docs/demo/timeline.json" in added
    body = (Path(env["RUNNER_TEMP"]) / "body.md").read_text(encoding="utf-8")
    assert "The games of the live demo were recorded anew, too" in body
    assert "The German images did not render in this run" in body


@needs_jq
def test_a_new_recording_alone_has_no_table_of_images(bot):
    clone, env = bot
    temp = Path(env["RUNNER_TEMP"])
    # The English images look as before, only the recording changed.
    picture(temp / "rendered/images-en/card.png")
    (temp / "rendered/report-en/report.json").write_text(json.dumps({"images": []}))
    recording = temp / "rendered/timeline/timeline.json"
    recording.parent.mkdir(parents=True)
    recording.write_text('{"steps":[1]}\n')

    result, _ = place(clone, env)
    assert result.returncode == 0, result.stderr
    result, _ = publish(clone, env, MISSING="de", PR_LIST=pulls(7))

    assert result.returncode == 0, result.stderr
    body = (temp / "body.md").read_text(encoding="utf-8")
    assert "No image changed." in body
    assert "These look different" not in body
    assert "| Image |" not in body
    assert "The games of the live demo were recorded anew, too" in body


@needs_jq
def test_the_live_demo_keeps_its_recording_when_none_was_made(bot):
    clone, env = bot

    result, _ = place(clone, env)

    assert result.returncode == 0, result.stderr
    assert "::warning::The games of the live demo were not recorded" in result.stdout
    assert git(clone, "status", "--short", "--", "docs/demo") == ""


def test_the_bot_stops_when_no_language_rendered(bot):
    clone, env = bot
    shutil.rmtree(Path(env["RUNNER_TEMP"]) / "rendered")

    result, outputs = place(clone, env)

    assert result.returncode == 1
    assert "::error::No language rendered" in result.stdout
    assert outputs == ""


@needs_jq
def test_the_pull_request_keeps_its_images_of_a_language_that_did_not_render(bot):
    clone, env = bot
    place(clone, env)

    result, calls = publish(clone, env, MISSING="de", PR_LIST=pulls(7))

    assert result.returncode == 0, result.stderr
    (commit,) = commits(env)
    changes = {item["path"] for item in commit["fileChanges"]["additions"]}
    assert changes == {"docs/images/en/card.png", "docs/images/de/card.png"}
    # The German image as the pull request had it, not as main has it.
    assert git(clone, "rev-parse", ":docs/images/de/card.png") == git(
        clone, "rev-parse", "FETCH_HEAD:docs/images/de/card.png"
    )
    assert git(clone, "rev-parse", ":docs/images/de/card.png") != git(
        clone, "rev-parse", "main:docs/images/de/card.png"
    )
    body = (Path(env["RUNNER_TEMP"]) / "body.md").read_text()
    assert "| `docs/images/en/card.png` | changed | 100 % |" in body
    assert "The German images did not render in this run" in body
    assert "pr edit 7 " in calls
    assert "pr close" not in calls


def fork(clone: Path, number: int) -> dict:
    """A pull request from a fork's branch of the same name, which changed every
    German image and added a page of its own to the website."""
    git(clone, "switch", "--quiet", "-c", "fork", "main")
    picture(clone / "docs/images/de/card.png", colour=(66, 66, 66))
    picture(clone / "docs/images/de/other.png", colour=(66, 66, 66))
    (clone / "docs/images/de/page.svg").write_text("<svg/>")
    git(clone, "add", "--all")
    git(clone, "commit", "--quiet", "-m", "a stranger's images")
    git(clone, "push", "--quiet", "origin", f"fork:refs/pull/{number}/head")
    git(clone, "switch", "--quiet", "main")
    return {
        "number": number,
        "isCrossRepository": True,
        "author": {"login": "stranger", "is_bot": False},
    }


@needs_jq
def test_the_pull_request_of_a_fork_gives_the_bot_nothing(bot):
    clone, env = bot
    stranger = fork(clone, 8)
    Path(env["PR_FILES"]).write_text(
        "docs/images/de/card.png\ndocs/images/de/other.png\ndocs/images/de/page.svg\n"
    )
    place(clone, env)

    # The fork's pull request is the newest; the bot has none of its own.
    result, calls = publish(clone, env, MISSING="de", PR_LIST=pulls(fork=stranger))

    assert result.returncode == 0, result.stderr
    (commit,) = commits(env)
    assert {item["path"] for item in commit["fileChanges"]["additions"]} == {
        "docs/images/en/card.png"
    }
    assert "/pulls/8/files" not in calls
    assert "pr edit" not in calls
    assert "pr create " in calls
    assert git(clone, "status", "--short", "--", "docs/images/de") == ""


@needs_jq
def test_the_bot_keeps_the_images_of_its_own_pull_request_not_of_a_fork(bot):
    clone, env = bot
    stranger = fork(clone, 8)
    place(clone, env)

    result, calls = publish(clone, env, MISSING="de", PR_LIST=pulls(7, fork=stranger))

    assert result.returncode == 0, result.stderr
    assert "api --paginate repos/owner/repo/pulls/7/files " in calls
    assert "pr edit 7 " in calls
    # The German image of the bot's own branch, not the fork's.
    assert Image.open(clone / "docs/images/de/card.png").getpixel((0, 0)) == (1, 2, 3)
    assert not (clone / "docs/images/de/page.svg").exists()


@needs_jq
def test_the_bot_keeps_only_rendered_images_of_its_pull_request(bot):
    clone, env = bot
    # main has a newer diagram than the pull request of the bot, which replaced
    # whole folders before it took only the rendered images.
    (clone / "docs/diagrams").mkdir(parents=True)
    (clone / "docs/diagrams/flow.de.mmd").write_text("flowchart TB\n")
    picture(clone / "docs/images/de/flow-dark.png", colour=(7, 7, 7))
    git(clone, "add", "--all")
    git(clone, "commit", "--quiet", "-m", "a newer diagram")
    git(clone, "switch", "--quiet", "bot")
    picture(clone / "docs/images/de/flow-dark.png", colour=(3, 3, 3))
    (clone / "docs/images/de/notes.html").write_text("<p>notes</p>")
    git(clone, "add", "--all")
    git(clone, "commit", "--quiet", "-m", "an older diagram and a page")
    git(clone, "push", "--quiet", "--force", "origin", "bot:refs/heads/bot/screenshots")
    git(clone, "switch", "--quiet", "main")
    Path(env["PR_FILES"]).write_text(
        "docs/images/de/card.png\ndocs/images/de/flow-dark.png\n"
        "docs/images/de/notes.html\ndocs/images/de/../../README.md\n"
    )
    place(clone, env)

    result, _ = publish(clone, env, MISSING="de", PR_LIST=pulls(7))

    assert result.returncode == 0, result.stderr
    (commit,) = commits(env)
    assert {item["path"] for item in commit["fileChanges"]["additions"]} == {
        "docs/images/en/card.png",
        "docs/images/de/card.png",
    }
    diagram = Image.open(clone / "docs/images/de/flow-dark.png")
    assert diagram.getpixel((0, 0)) == (7, 7, 7)
    assert not (clone / "docs/images/de/notes.html").exists()
    message = commit["message"]["body"]
    assert "in groups (tests/e2e/screenshots.sh, tests/e2e/collect.sh)" in message


@needs_jq
def test_a_pull_request_stays_open_while_a_language_did_not_render(bot):
    clone, env = bot
    shutil.rmtree(Path(env["RUNNER_TEMP"]) / "rendered/images-en")
    shutil.copytree(
        clone / "docs/images/en", Path(env["RUNNER_TEMP"]) / "rendered/images-en"
    )
    place(clone, env)
    Path(env["PR_FILES"]).write_text("")

    result, calls = publish(clone, env, MISSING="de", PR_LIST=pulls(7))

    assert result.returncode == 0, result.stderr
    assert (
        "did not render, so the pull request of the images stays as it is"
        in result.stdout
    )
    assert "pr close" not in calls
    assert commits(env) == []


@needs_jq
def test_a_pull_request_closes_when_every_language_looks_as_committed(bot):
    clone, env = bot
    temp = Path(env["RUNNER_TEMP"]) / "rendered"
    shutil.rmtree(temp / "images-en")
    for language in ("en", "de"):
        shutil.copytree(clone / "docs/images" / language, temp / f"images-{language}")
    (temp / "report-de").mkdir()
    (temp / "report-de/report.json").write_text('{"images": []}')
    place(clone, env)

    result, calls = publish(clone, env, MISSING="", PR_LIST=pulls(7))

    assert result.returncode == 0, result.stderr
    assert "pr close 7 " in calls
    assert commits(env) == []


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
