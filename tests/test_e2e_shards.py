"""The browser test in shards, checked without a browser.

CI runs the steps of tests/e2e/browser.py in four shards side by side: three runners for
each Home Assistant version, one with two workers and two with one (BROWSER_SHARD and
BROWSER_WORKERS of browser.sh). shards.py decides which steps a shard runs. browser.py imports
Playwright, so its list of steps is read here from its source, and browser.sh runs
here with a stand-in for docker that only notes what it is asked to do.
"""

import ast
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
E2E = ROOT / "tests" / "e2e"
SPEC = importlib.util.spec_from_file_location("e2e_shards", E2E / "shards.py")
assert SPEC is not None and SPEC.loader is not None
shards = importlib.util.module_from_spec(SPEC)
# A dataclass looks up the module it is defined in.
sys.modules[SPEC.name] = shards
SPEC.loader.exec_module(shards)
Step = shards.Step
Choice = shards.Choice
choose = shards.choose
WATCHDOG_SPEC = importlib.util.spec_from_file_location(
    "e2e_watchdog", E2E / "watchdog.py"
)
assert WATCHDOG_SPEC is not None and WATCHDOG_SPEC.loader is not None
watchdog = importlib.util.module_from_spec(WATCHDOG_SPEC)
WATCHDOG_SPEC.loader.exec_module(watchdog)


def browser_steps() -> list:
    """The steps of browser.py in their order, as steps() returns them."""
    tree = ast.parse((E2E / "browser.py").read_text(encoding="utf-8"))
    (function,) = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "steps"
    ]
    (returned,) = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
    assert isinstance(returned.value, ast.List)
    found = []
    for call in returned.value.elts:
        assert isinstance(call, ast.Call), ast.unparse(call)
        assert isinstance(call.func, ast.Name) and call.func.id == "Step"
        name, group = (ast.literal_eval(argument) for argument in call.args[:2])
        keywords = {
            keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords
        }
        found.append(Step(name, group, lambda: None, **keywords))
    return found


STEPS = browser_steps()
NAMES = [step.name for step in STEPS]
# The steps that a run takes, without the drills.
RUN = [step for step in STEPS if not step.drill]


def names(steps) -> list[str]:
    return [step.name for step in steps]


def test_the_steps_are_read_from_browser_py():
    assert len(STEPS) > 20
    assert {"training card", "steady heights", "accessibility"} <= set(NAMES)


def test_every_step_can_be_asked_for_by_its_name():
    assert len(set(NAMES)) == len(NAMES), "two steps share a name"
    # BROWSER_STEPS separates the names with commas, and browser.sh puts a name that
    # failed in single quotes in the command that runs it alone.
    assert [name for name in NAMES if "," in name or "'" in name] == []
    for name in NAMES:
        assert names(choose(STEPS, name)) == [name]


def test_every_step_has_one_of_the_groups_and_every_group_has_steps():
    groups = {step.group for step in STEPS}
    assert groups == set(range(1, shards.GROUPS + 1))


def test_the_steps_that_read_the_demo_as_it_started_come_first():
    # Nothing is reset before them, so no step may change the board before them, in
    # the whole run, in any shard and with any BROWSER_STEPS.
    started = [step for step in STEPS if step.as_started]
    assert names(started) == ["training card", "live card"]
    assert STEPS[: len(started)] == started
    # Group 1 is in the first shard of any count of shards.
    assert {step.group for step in started} == {1}


def test_the_dartboard_without_autodarts_comes_last():
    # A second board would be the first of the cards without one.
    assert NAMES[-1] == "a dartboard without Autodarts"


@pytest.mark.parametrize("parts", range(1, shards.GROUPS + 1))
def test_every_count_of_shards_runs_every_step_once_in_its_order(parts):
    chosen = [choose(STEPS, "", f"{part}/{parts}") for part in range(1, parts + 1)]
    ran = [name for shard in chosen for name in names(shard)]
    assert sorted(ran) == sorted(names(RUN))
    for shard in chosen:
        assert shard, "a shard without steps"
        assert names(shard) == [name for name in NAMES if name in names(shard)]


def test_four_shards_are_the_four_groups():
    for part in range(1, 5):
        assert {step.group for step in choose(STEPS, "", f"{part}/4")} == {part}


def test_two_shards_take_every_other_group():
    first, second = (choose(STEPS, "", f"{part}/2") for part in (1, 2))
    assert {step.group for step in first} == {1, 3}
    assert {step.group for step in second} == {2, 4}


def test_no_shard_is_the_whole_run():
    assert choose(STEPS) == RUN
    assert choose(STEPS, " ", " ") == RUN


def test_the_watchdog_checks_itself_in_every_run_and_its_drill_only_when_asked():
    # The step "the watchdog" checks on Playwright itself that a hung wait ends; the
    # drill "a hung step" hangs on purpose, to show what a hang leaves behind.
    assert "the watchdog" in names(RUN)
    assert [step.name for step in STEPS if step.drill] == ["a hung step"]
    assert names(choose(STEPS, "a hung step")) == ["a hung step"]
    # Its group runs it when asked: the drill runs on the runner of group 3 too.
    assert names(choose(STEPS, "a hung step", "3/4")) == ["a hung step"]


def test_every_step_has_a_budget_that_ends_well_before_its_job_step():
    # About three times the longest run of a step in CI and at least two minutes;
    # with the grace for its screenshots it ends before the step of the workflow
    # that runs browser.sh does (tests/test_e2e_workflow.py), so that the step that
    # hung names itself.
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "e2e.yml").read_text(encoding="utf-8")
    )
    limits = [
        step["timeout-minutes"] * 60
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "tests/e2e/browser.sh" in step.get("run", "")
    ]
    assert len(limits) == 2
    for step in RUN:
        assert step.budget >= shards.BUDGET, step.name
        assert step.budget + watchdog.GRACE < min(limits), step.name
    (drill,) = [step for step in STEPS if step.drill]
    assert drill.budget < shards.BUDGET


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", (1, 1)), ("1/1", (1, 1)), ("2/4", (2, 4)), (" 3 / 4 ", (3, 4))],
)
def test_a_shard_is_read_as_k_of_n(value, expected):
    assert shards.shard(value) == expected


@pytest.mark.parametrize(
    "value", ["0/4", "5/4", "2", "2/", "/4", "a/b", "1/2/3", "-1/4"]
)
def test_a_shard_outside_its_count_is_refused(value):
    with pytest.raises(Choice, match="BROWSER_SHARD is k/n with 1 <= k <= n"):
        shards.shard(value)


def test_more_shards_than_groups_are_refused():
    with pytest.raises(Choice, match="the steps have 4 groups, so there are at most 4"):
        shards.shard("1/5")


DEMO = [
    Step("training card", 1, lambda: None, as_started=True),
    Step("live card", 1, lambda: None, as_started=True),
    Step("scoreboard", 1, lambda: None),
    Step("tablet screen", 3, lambda: None),
    Step("steady heights", 2, lambda: None),
    Step("training card editor", 1, lambda: None),
    Step("scoreboard editor", 1, lambda: None),
]


def test_browser_steps_picks_a_step_by_its_name_alone():
    # Each step runs alone, as a shard runs it: after the board got between games.
    assert names(choose(DEMO, "training card")) == ["training card"]
    assert names(choose(DEMO, "scoreboard editor, tablet screen")) == [
        "tablet screen",
        "scoreboard editor",
    ]


def test_browser_steps_picks_every_step_that_a_beginning_begins():
    assert names(choose(DEMO, "training")) == ["training card", "training card editor"]
    assert names(choose(DEMO, "scoreboard ,tab")) == [
        "scoreboard",
        "tablet screen",
    ]
    assert names(choose(DEMO, "scoreboard e")) == ["scoreboard editor"]


def test_browser_steps_picks_within_the_shard():
    assert names(choose(DEMO, "training,steady", "1/2")) == [
        "training card",
        "training card editor",
    ]
    # A worker whose shard holds none of the steps asked for runs none.
    assert choose(DEMO, "steady", "1/2") == []


def test_browser_steps_that_name_no_step_are_refused():
    with pytest.raises(Choice, match=r"BROWSER_STEPS names no step: \['bowling'\]"):
        choose(DEMO, "scoreboard,bowling")


DRILL = [*DEMO, Step("scoreboard hangs", 1, lambda: None, drill=True)]


def test_a_drill_runs_only_when_its_whole_name_asks_for_it():
    assert "scoreboard hangs" not in names(choose(DRILL))
    for part in range(1, 5):
        assert "scoreboard hangs" not in names(choose(DRILL, "", f"{part}/4"))
    # A beginning of its name begins only the other steps.
    assert names(choose(DRILL, "scoreb")) == ["scoreboard", "scoreboard editor"]
    assert names(choose(DRILL, "scoreboard hangs")) == ["scoreboard hangs"]
    assert names(choose(DRILL, "scoreboard hangs,scoreboard editor")) == [
        "scoreboard editor",
        "scoreboard hangs",
    ]
    with pytest.raises(Choice, match=r"names no step: \['scoreboard h'\]"):
        choose(DRILL, "scoreboard h")


def test_a_step_outside_the_groups_is_refused():
    with pytest.raises(Choice, match="later: group 5 is not 1 to 4"):
        choose([*DEMO, Step("later", 5, lambda: None)])


# browser.sh -------------------------------------------------------------------------

needs_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="browser.sh runs in bash"
)

# Notes every call; a call whose words contain $FAIL fails, as a browser that finds
# a problem does, and notes $FAILED_STEP in the table of its steps as browser.py does,
# as failed or as $FAILED_END, such as "took too long".
# One whose words contain $HANG notes $FAILED_STEP as running, as browser.py does while
# a step runs, and hangs until its demo goes down a second time, after its start.
# The first call whose words contain $FAIL_ONCE fails, and Playwright's image is missing
# with it, so that it has to be pulled.
DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
if [[ -n "${FAIL_ONCE:-}" ]]; then
  if [[ "$*" == "image inspect "* ]]; then
    exit 1
  fi
  if [[ "$*" == *"$FAIL_ONCE"* && $(grep -cF -- "$FAIL_ONCE" "$CALLS") == 1 ]]; then
    echo "context deadline exceeded" >&2
    exit 1
  fi
fi
if [[ -n "${HANG:-}" && "$*" == *"$HANG"* ]]; then
  for word in "$@"; do
    if [[ "$word" == *:/artifacts ]]; then
      printf '| live card | 1.0 |\\n| %s (running) | – |\\n' "$FAILED_STEP" \\
        > "${word%:/artifacts}/browser-steps-table.md"
    fi
  done
  while (($(grep -c ' down ' "$CALLS") < 2)); do sleep 0.1; done
  exit 137
fi
if [[ -n "${FAIL:-}" && "$*" == *"$FAIL"* ]]; then
  for word in "$@"; do
    if [[ -n "${FAILED_STEP:-}" && "$word" == *:/artifacts ]]; then
      printf '| live card | 1.0 |\\n| %s (%s) | 2.0 |\\n' "$FAILED_STEP" \\
        "${FAILED_END:-failed}" > "${word%:/artifacts}/browser-steps-table.md"
    fi
  done
  echo "failed: $FAIL"
  exit 1
fi
echo "ran: ${*: -1}"
"""


def browser_sh(
    tmp_path: Path, command: list[str] | None = None, **env: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run browser.sh with the stand-in for docker, or a command that runs it as
    $BROWSER_SH; the result and the calls of docker."""
    docker = tmp_path / "docker"
    docker.write_text(DOCKER, encoding="utf-8", newline="\n")
    docker.chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    environment = {
        **os.environ,
        "DOCKER_BIN": str(docker),
        "CALLS": str(calls),
        "E2E_ARTIFACTS": str(tmp_path / "artifacts"),
        "E2E_PULL_PAUSE": "0",
        "BROWSER_SH": str(E2E / "browser.sh"),
        **env,
    }
    # Only what a test asks for, also in CI: GitHub Actions with its annotations and
    # summary, another Home Assistant or board, shards and steps.
    for name in (
        "GITHUB_ACTIONS",
        "GITHUB_STEP_SUMMARY",
        "HOME_ASSISTANT_IMAGE",
        "BOARD_MANAGER",
        "BROWSER_SHARD",
        "BROWSER_WORKERS",
        "BROWSER_STEPS",
        "HANG",
    ):
        if name not in env:
            environment.pop(name, None)
    result = subprocess.run(
        command or ["bash", str(E2E / "browser.sh")],
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=20,
    )
    return result, calls.read_text(encoding="utf-8").splitlines()


def browsers(calls: list[str]) -> list[str]:
    """The shard and network of every browser that browser.sh started."""
    started = []
    for call in calls:
        if call.startswith("run --rm "):
            words = call.split()
            shard = next(word for word in words if word.startswith("BROWSER_SHARD="))
            started.append(f"{words[words.index('--network') + 1]} {shard}")
    return started


@needs_bash
def test_each_browser_has_a_name_that_the_cleanup_removes_it_by(tmp_path):
    # A browser that a signal stopped would keep running, so the cleanup removes it,
    # so that no container outlives the step.
    _, calls = browser_sh(tmp_path, BROWSER_WORKERS="2")

    names = sorted(
        call.split()[call.split().index("--name") + 1]
        for call in calls
        if call.startswith("run --rm ")
    )
    assert names == ["homedarts_browser_1-playwright", "homedarts_browser_2-playwright"]
    for name in names:
        assert f"rm --force {name}" in calls


@needs_bash
def test_one_worker_runs_its_shard_on_the_demo_of_a_run_without_workers(tmp_path):
    result, calls = browser_sh(tmp_path, BROWSER_SHARD="2/4")

    assert result.returncode == 0, result.stdout + result.stderr
    assert browsers(calls) == ["homedarts_browser_default BROWSER_SHARD=2/4"]
    # Its lines go out as they are, and the demo keeps its project.
    assert "\nran: " in result.stdout
    assert any(
        "--project-name homedarts_browser " in call and " up " in call for call in calls
    )


@needs_bash
def test_workers_split_the_shard_of_their_machine(tmp_path):
    result, calls = browser_sh(tmp_path, BROWSER_SHARD="2/2", BROWSER_WORKERS="2")

    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(browsers(calls)) == [
        "homedarts_browser_1_default BROWSER_SHARD=3/4",
        "homedarts_browser_2_default BROWSER_SHARD=4/4",
    ]
    # Each worker has its demo, its artifacts and its lines.
    for worker, shard in ((1, "3/4"), (2, "4/4")):
        project = f"--project-name homedarts_browser_{worker} "
        assert any(project in call and " up " in call for call in calls)
        assert any(project in call and " down " in call for call in calls)
        assert f"[{shard}] ran: " in result.stdout
    for folder in ("shard-3-of-4", "shard-4-of-4"):
        assert (tmp_path / "artifacts" / folder).is_dir()


@needs_bash
def test_four_workers_run_every_shard_on_one_machine(tmp_path):
    result, calls = browser_sh(tmp_path, BROWSER_WORKERS="4")

    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(shard.split()[1] for shard in browsers(calls)) == [
        f"BROWSER_SHARD={part}/4" for part in range(1, 5)
    ]


@needs_bash
def test_a_failed_worker_fails_the_run_and_keeps_its_logs_alone(tmp_path):
    result, calls = browser_sh(tmp_path, BROWSER_WORKERS="2", FAIL="BROWSER_SHARD=2/2")

    assert result.returncode == 1
    # The other worker ran to its end.
    assert "[1/2] ran: " in result.stdout
    assert "[2/2] failed: BROWSER_SHARD=2/2" in result.stdout
    # Last, what failed and how to run it alone: without a step that failed, such as
    # when its demo didn't start, the whole shard.
    assert result.stdout.endswith(
        "The browser check failed in shard 2/2. Its lines in the log begin with [2/2]."
        " Run it alone: BROWSER_SHARD=2/2 bash tests/e2e/browser.sh\n"
    )
    assert "failed in shard 1/2" not in result.stdout
    # Outside GitHub Actions, no annotation.
    assert "::error" not in result.stdout
    logs = [call for call in calls if " logs " in call]
    assert logs == [
        "compose --project-name homedarts_browser_2 --file compose.yaml logs "
        "--no-color --tail 200"
    ]


@needs_bash
def test_a_failed_shard_explains_itself_in_github_actions(tmp_path):
    summary = tmp_path / "summary.md"
    result, _ = browser_sh(
        tmp_path,
        BROWSER_SHARD="2/2",
        BROWSER_WORKERS="2",
        FAIL="BROWSER_SHARD=4/4",
        FAILED_STEP="steady heights",
        GITHUB_ACTIONS="true",
        GITHUB_STEP_SUMMARY=str(summary),
        HOME_ASSISTANT_IMAGE="example.org/home-assistant:2026.8.0",
    )

    assert result.returncode == 1
    command = (
        "HOME_ASSISTANT_IMAGE=example.org/home-assistant:2026.8.0"
        " BROWSER_STEPS='steady heights' bash tests/e2e/browser.sh"
    )
    # The annotation begins its line, unlike the labelled lines of the workers, and
    # only the shard that failed has one.
    annotations = [
        line for line in result.stdout.splitlines() if line.startswith("::error")
    ]
    assert annotations == [
        "::error title=Browser check failed in shard 4/4::The browser check failed"
        ' in shard 4/4 at the step "steady heights": a card doesn\'t look or behave'
        " in a real browser as the test expects. Its lines in the log begin with"
        " [4/4]. The artifact of this job keeps the screenshots and the logs."
        f" Run it alone: {command}"
    ]
    text = summary.read_text(encoding="utf-8")
    # The seconds of the steps, and then what failed and how to run it alone.
    assert "| steady heights (failed) | 2.0 |" in text
    assert text.endswith(
        '### The browser check failed in shard 4/4 at the step "steady heights"\n\n'
        "That means a card doesn't look or behave in a real browser as the test"
        " expects. Its lines in the log begin with [4/4]. The artifact of this job"
        " keeps the screenshots and the logs. Run it alone:\n\n"
        f"~~~sh\n{command}\n~~~\n\n"
    )


@needs_bash
def test_one_worker_names_the_step_that_failed(tmp_path):
    result, calls = browser_sh(
        tmp_path,
        BOARD_MANAGER="1",
        FAIL="BROWSER_SHARD=1/1",
        FAILED_STEP="live card editor",
    )

    assert result.returncode == 1
    # A run without shards names none, and its lines carry none.
    assert result.stdout.endswith(
        'The browser check failed at the step "live card editor".'
        " Run it alone: BOARD_MANAGER=1 BROWSER_STEPS='live card editor'"
        " bash tests/e2e/browser.sh\n"
    )
    assert any(" logs " in call for call in calls)


@needs_bash
@pytest.mark.parametrize(
    ("end", "why"),
    [
        # The watchdog of browser.py failed the step after its budget.
        (
            "took too long",
            "it took longer than its budget, and the log shows the line that it"
            " waited at",
        ),
        # browser.py ended while the step ran, such as when faulthandler ended a hang
        # two minutes after its budget.
        (
            "running",
            "the browser test ended in it without a result, such as when the watchdog"
            " ended a hang that no exception reached, and the log shows the stack of"
            " every thread",
        ),
    ],
)
def test_a_step_that_hung_explains_itself_so(tmp_path, end, why):
    result, _ = browser_sh(
        tmp_path,
        FAIL="BROWSER_SHARD=1/1",
        FAILED_STEP="a hung step",
        FAILED_END=end,
        GITHUB_ACTIONS="true",
    )

    assert result.returncode == 1
    assert result.stdout.endswith(
        '::error title=Browser check failed::The browser check failed at the step "a'
        f' hung step": {why}. The artifact of this job keeps the screenshots and the'
        " logs. Run it alone: BROWSER_STEPS='a hung step' bash tests/e2e/browser.sh\n"
    )


@needs_bash
def test_a_signal_stops_a_hung_run_and_names_the_step_that_still_ran(tmp_path):
    # As GitHub stops a step of the workflow that runs out of time, which runs
    # browser.sh with exec: the explanation names the step that browser.py noted as
    # running, after the containers of its demo. Here SIGTERM, which GitHub sends
    # 7.5 s after SIGINT: bash starts a script in the background with SIGINT ignored.
    summary = tmp_path / "summary.md"
    result, calls = browser_sh(
        tmp_path,
        [
            "bash",
            "-c",
            'bash "$BROWSER_SH" & run=$!\n'
            'until grep -q "^run --rm" "$CALLS"; do sleep 0.1; done\n'
            'kill -TERM "$run"\n'
            'wait "$run"',
        ],
        HANG="BROWSER_SHARD=1/1",
        FAILED_STEP="touch screens",
        GITHUB_ACTIONS="true",
        GITHUB_STEP_SUMMARY=str(summary),
    )

    assert result.returncode == 143, result.stdout + result.stderr
    assert "Stopped by SIGTERM" in result.stderr
    command = "BROWSER_STEPS='touch screens' bash tests/e2e/browser.sh"
    assert result.stdout.endswith(
        "::error title=Browser check failed::The browser check failed at the step"
        ' "touch screens" when SIGTERM stopped it: the run took longer than its step'
        " in the workflow allows, and nothing in it ran out of time before. The"
        f" artifact of this job keeps the screenshots and the logs. Run it alone: {command}\n"
    )
    assert "| touch screens (running) | – |" in summary.read_text(encoding="utf-8")
    project = "compose --project-name homedarts_browser --file compose.yaml "
    shown = [call.removeprefix(project) for call in calls if call.startswith(project)]
    # First the browser goes, which still runs, then the state of its containers and
    # its logs, last the cleanup.
    removed = calls.index("rm --force homedarts_browser-playwright")
    assert removed < calls.index(project + "ps --all")
    assert shown[-6:] == [
        "ps --all",
        "stats --no-stream",
        "exec -T homeassistant tail -n 100 /config/home-assistant.log",
        "logs --no-color --tail 200",
        "exec -T homeassistant cat /config/home-assistant.log",
        "down --volumes --remove-orphans",
    ]


@needs_bash
def test_images_that_fail_to_pull_are_no_failed_shard(tmp_path):
    result, calls = browser_sh(tmp_path, FAIL=" pull ")

    assert result.returncode != 0
    assert "The browser check failed" not in result.stdout
    assert not any(" up " in call for call in calls)
    assert sum(" pull " in call for call in calls) == 3
    assert "Pulling the images failed 3 times" in result.stderr


@needs_bash
@pytest.mark.parametrize("image", [" pull ", "pull --quiet mcr.microsoft.com"])
def test_a_pull_that_the_registry_cuts_off_is_tried_again(tmp_path, image):
    # As "context deadline exceeded" from mcr.microsoft.com ended a run (#463).
    result, calls = browser_sh(tmp_path, FAIL_ONCE=image)

    assert result.returncode == 0, result.stderr
    assert sum(image in call for call in calls) == 2
    assert "failed (attempt 1 of 3); trying again in 0 s" in result.stderr
    assert any(" up " in call for call in calls)


@needs_bash
@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"BROWSER_WORKERS": "0"}, "BROWSER_WORKERS is a number of at least 1"),
        ({"BROWSER_WORKERS": "two"}, "BROWSER_WORKERS is a number of at least 1"),
        ({"BROWSER_SHARD": "3/2"}, "BROWSER_SHARD is k/n with 1 <= k <= n"),
        ({"BROWSER_SHARD": "0/2"}, "BROWSER_SHARD is k/n with 1 <= k <= n"),
        ({"BROWSER_SHARD": "2"}, "BROWSER_SHARD is k/n with 1 <= k <= n"),
        # More shards than groups, which shards.py would refuse only in the browsers,
        # after the images and the demos.
        ({"BROWSER_SHARD": "1/5"}, "makes 5 shards, but the steps have only 4 groups"),
        (
            {"BROWSER_SHARD": "2/4", "BROWSER_WORKERS": "2"},
            "BROWSER_SHARD=2/4 with BROWSER_WORKERS=2 makes 8 shards",
        ),
        ({"BROWSER_WORKERS": "5"}, "makes 5 shards, but the steps have only 4 groups"),
    ],
)
def test_browser_sh_refuses_what_it_cannot_split(tmp_path, env, message):
    result, calls = browser_sh(tmp_path, **env)

    assert result.returncode == 2
    assert message in result.stderr
    assert calls == []


def test_browser_sh_knows_the_groups_of_shards_py():
    script = (E2E / "browser.sh").read_text(encoding="utf-8")
    (groups,) = re.findall(r"^STEP_GROUPS=(\d+)$", script, re.MULTILINE)
    assert int(groups) == shards.GROUPS


@needs_bash
def test_both_images_are_ready_before_the_demo_starts(tmp_path):
    _, calls = browser_sh(tmp_path)

    pulled = next(n for n, call in enumerate(calls) if " pull " in call)
    inspected = next(n for n, call in enumerate(calls) if call.startswith("image "))
    started = next(n for n, call in enumerate(calls) if " up " in call)
    assert max(pulled, inspected) < started


# e2e.yml ----------------------------------------------------------------------------

WORKFLOW = yaml.safe_load(
    (ROOT / ".github" / "workflows" / "e2e.yml").read_text(encoding="utf-8")
)


def groups_of(shard: str, workers: int) -> list[list[int]]:
    """The groups that each worker of a job runs, split as browser.sh splits them:
    worker w of BROWSER_SHARD=k/n takes the shard (k - 1) * W + w of n * W."""
    part, parts = shards.shard(shard)
    count = parts * workers
    return [
        [
            group
            for group in range(1, shards.GROUPS + 1)
            if (group - 1) % count == (part - 1) * workers + worker - 1
        ]
        for worker in range(1, workers + 1)
    ]


def browser_jobs() -> list[dict]:
    """The parts of the matrix of the jobs "browser", one runner of a version each."""
    job = WORKFLOW["jobs"]["browser"]
    assert job["env"]["BROWSER_SHARD"] == "${{ matrix.part.shard }}"
    assert job["env"]["BROWSER_WORKERS"] == "${{ matrix.part.workers }}"
    return job["strategy"]["matrix"]["part"]


def test_groups_of_follows_browser_sh():
    assert groups_of("1/1", 1) == [[1, 2, 3, 4]]
    assert groups_of("1/1", 2) == [[1, 3], [2, 4]]
    assert groups_of("1/2", 2) == [[1], [2]]
    assert groups_of("2/2", 2) == [[3], [4]]
    assert groups_of("3/4", 1) == [[3]]


def test_the_browser_jobs_of_each_home_assistant_run_every_group_once():
    ran = [
        group
        for part in browser_jobs()
        for worker in groups_of(part["shard"], int(part["workers"]))
        for group in worker
    ]
    assert sorted(ran) == list(range(1, shards.GROUPS + 1))
    # The names of the jobs say which groups they run.
    for part in browser_jobs():
        groups = sorted(
            group
            for worker in groups_of(part["shard"], int(part["workers"]))
            for group in worker
        )
        words = " and ".join(str(group) for group in groups)
        assert part["name"] == ("group " if len(groups) == 1 else "groups ") + words


def safari_group() -> int:
    (group,) = [step.group for step in STEPS if step.name == "Safari on an iPhone"]
    return group


def test_safari_shares_its_runner_with_no_other_browser():
    """WebKit failed to load Home Assistant's own scripts while a second browser opened
    nine screens beside it on the same four cores, so its job runs one worker."""
    (part,) = [
        part
        for part in browser_jobs()
        if any(
            safari_group() in worker
            for worker in groups_of(part["shard"], int(part["workers"]))
        )
    ]
    assert int(part["workers"]) == 1


def test_the_steps_launch_every_browser_that_home_assistant_supports():
    tree = ast.parse((E2E / "browser.py").read_text(encoding="utf-8"))
    launched = {
        node.func.value.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "launch"
        and isinstance(node.func.value, ast.Attribute)
    }
    assert launched == {"chromium", "webkit", "firefox"}


def test_firefox_is_a_step_of_a_job_with_no_browser_beside_it():
    """No job of its own: a step of a group that one browser job of each Home Assistant
    and the nightly beta run anyway, with the CPU of the runner for itself."""
    (step,) = [step for step in STEPS if step.name.startswith("Firefox")]
    assert not step.drill
    assert not step.as_started
    (part,) = [
        part
        for part in browser_jobs()
        if any(
            step.group in worker
            for worker in groups_of(part["shard"], int(part["workers"]))
        )
    ]
    assert int(part["workers"]) == 1


def test_firefox_comes_before_the_steps_with_the_long_names():
    # Its new game screen expects the players of the demo, in every shard and in the
    # whole run, as the step in Chromium does.
    firefox = NAMES.index("Firefox on a desktop")
    assert firefox < NAMES.index("touch screens")
    assert firefox < NAMES.index("every screen size")


def test_firefox_plays_the_cards_that_the_steps_in_chromium_check():
    """The same functions as the steps in Chromium, so that the same checks run."""
    tree = ast.parse((E2E / "browser.py").read_text(encoding="utf-8"))
    (firefox,) = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "firefox"
    ]
    called = {
        node.func.id
        for node in ast.walk(firefox)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert {"scoreboard", "lobby", "training_after_others", "editor"} <= called


@pytest.mark.parametrize("name", ["safari", "firefox"])
def test_a_browser_of_its_own_keeps_its_screenshots_when_a_wait_is_cancelled(name):
    """The budget of a step ends a wait in a page with a CancelledError, which is no
    Exception. main() sees only the pages of Chromium, so the step saves its own."""
    tree = ast.parse((E2E / "browser.py").read_text(encoding="utf-8"))
    (function,) = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    (handler,) = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.ExceptHandler)
        and any(
            isinstance(call, ast.Name) and call.id == "keep_screenshots"
            for call in ast.walk(node)
        )
    ]
    assert isinstance(handler.type, ast.Tuple)
    caught = {ast.unparse(item) for item in handler.type.elts}
    assert caught == {"Exception", "asyncio.CancelledError"}


def test_the_nightly_beta_runs_every_group_with_one_browser():
    job = WORKFLOW["jobs"]["beta"]
    browser = [step for step in job["steps"] if "browser.sh" in step.get("run", "")]
    (step,) = browser
    env = {**job.get("env", {}), **step.get("env", {})}
    assert "BROWSER_SHARD" not in env
    assert int(env.get("BROWSER_WORKERS", 1)) == 1
