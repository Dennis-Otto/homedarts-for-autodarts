"""Every check of this project explains itself when it fails, as those of the blueprint
do, also on a pull request from a fork (docs/development.md#when-a-check-of-this-project-fails).

Each job of the project's own workflows of pull requests ends with the step of the PR
coach, which explains the check by its name from .github/checks.project.toml, and the
report on the pull request follows each of these workflows. `coach verify` of the
blueprint finds every required check and every step of scripts/check.sh explained,
and every explanation saying how it fixes itself: with the commands of the fix bot, or
the reason why no command can."""

import fnmatch
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from .test_docs_links import slug
from .test_workflow_network import PROJECT_WORKFLOWS

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CATALOG = tomllib.loads(
    (ROOT / ".github" / "checks.project.toml").read_text(encoding="utf-8")
)
EXPLANATIONS = CATALOG.get("check", {})
STEP = "Explain the failure"
COMMAND = 'python3 .github/blueprint.py coach explain "$CHECK"'
EXPRESSION = re.compile(r"\$\{\{.*?\}\}")
# The scripts of the repository that a command runs, such as tests/e2e/run.sh.
SCRIPT = re.compile(r"\b(?:scripts|tests)/[\w/.-]+\.(?:sh|py|mjs)\b")
# Jobs without the step of the coach, each with its reason.
UNEXPLAINED = {
    # It asks GitHub's API which files the pull request changes, and reaches no other
    # host for a checkout, so it has no step that explains it; when the API fails, it
    # runs every test. Only a broken runner stops it, which [check.changes] explains in
    # the report of the coach, as it looks up the name of the check run.
    ("e2e.yml", "changes"),
}


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def triggers(workflow: dict) -> dict:
    # YAML 1.1 reads the key on as true.
    return workflow.get("on", workflow.get(True)) or {}


# The workflows of this project alone that check pull requests.
CHECKS = sorted(
    name for name in PROJECT_WORKFLOWS if "pull_request" in triggers(load(name))
)
JOBS = {(name, key): job for name in CHECKS for key, job in load(name)["jobs"].items()}
EXPLAINED = sorted(set(JOBS) - UNEXPLAINED)


def sample(name: str) -> str:
    """A name that GitHub shows for a job, with an x for each expression in it, such
    as scenario (x) for scenario (${{ matrix.name }})."""
    return EXPRESSION.sub("x", name)


def explanation(name: str) -> dict | None:
    """The explanation of a check of this project, as the coach finds it: by its
    name, or by a key whose * stands for any text."""
    if name in EXPLANATIONS:
        return EXPLANATIONS[name]
    for key, entry in EXPLANATIONS.items():
        if "*" in key and fnmatch.fnmatchcase(name, key):
            return entry
    return None


def test_the_end_to_end_tests_and_the_visual_check_are_the_checks_of_this_project():
    assert CHECKS == ["e2e.yml", "visual.yml"]
    assert set(UNEXPLAINED) <= set(JOBS)


@pytest.mark.parametrize("key", EXPLAINED, ids="/".join)
def test_every_job_has_its_explanation(key):
    name = JOBS[key]["name"]
    assert explanation(sample(name)), f"{name} needs an explanation"


@pytest.mark.parametrize("key", EXPLAINED, ids="/".join)
def test_every_job_ends_with_the_step_of_the_coach(key):
    job = JOBS[key]
    steps = job["steps"]
    last = steps[-1]
    assert last["name"] == STEP
    assert last["if"] == "failure()"
    # The name that GitHub shows, which the report of the coach looks up as well.
    assert last["env"] == {"CHECK": job["name"]}
    assert last["run"] == COMMAND
    # blueprint.py and the explanations come from a checkout before it.
    assert any(
        step.get("uses", "").startswith("actions/checkout@") for step in steps[:-1]
    )


def test_the_workflow_that_runs_after_the_merge_explains_itself_as_well():
    # Same images checks no pull request, but the bot-health bot quotes its annotation.
    job = load("twice.yml")["jobs"]["twice"]
    assert explanation(sample(job["name"]))
    last = job["steps"][-1]
    assert last["name"] == STEP
    assert last["if"] == "failure()"
    assert last["env"] == {"CHECK": job["name"]}
    assert last["run"] == COMMAND


def test_every_explanation_belongs_to_a_job():
    names = [sample(job["name"]) for job in JOBS.values()]
    names.append(sample(load("twice.yml")["jobs"]["twice"]["name"]))
    for key in EXPLANATIONS:
        assert any(fnmatch.fnmatchcase(name, key) for name in names), key


def test_every_step_that_this_project_explains_runs_in_scripts_check_sh():
    # Also a step inside an if, as the one that runs scripts/check-project.sh.
    steps = re.findall(
        r'^ *step "([^"]+)"$',
        (ROOT / "scripts" / "check.sh").read_text(encoding="utf-8"),
        re.M,
    )
    assert set(CATALOG.get("step", {})) <= set(steps)


def entries() -> list[tuple[str, dict]]:
    return [
        (f"{kind} {key}", entry)
        for kind in ("check", "step")
        for key, entry in CATALOG.get(kind, {}).items()
    ]


@pytest.mark.parametrize(("key", "entry"), entries(), ids=[key for key, _ in entries()])
def test_the_page_and_the_scripts_of_each_explanation_exist(key, entry):
    page, _, anchor = entry["docs"].partition("#")
    text = (ROOT / page).read_text(encoding="utf-8")
    headings = {
        slug(line.lstrip("#").strip())
        for line in text.splitlines()
        if line.startswith("#")
    }
    assert anchor in headings, key
    autofix = entry["autofix"] if isinstance(entry["autofix"], list) else []
    for command in [*entry.get("commands", []), *autofix]:
        for script in SCRIPT.findall(command):
            assert (ROOT / script).is_file(), f"{key}: {script}"


def test_the_report_on_the_pull_request_follows_every_check_of_this_project():
    # The answer test_workflows of .copier-answers.yml names the workflows of this
    # project beside the Docker E2E, so that the blueprint brings them in here.
    after = triggers(load("after-checks.yml"))["workflow_run"]["workflows"]
    for name in CHECKS:
        assert load(name)["name"] in after, name


def test_the_coach_finds_every_check_explained_and_every_fix_declared():
    result = subprocess.run(
        [sys.executable, ".github/blueprint.py", "coach", "verify"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
