"""The jobs of the project's own workflows reach only the hosts that their steps need.

Harden-Runner, the first step of every job, blocks every other host: in the bots,
which may write, and in the tests and the images, which run the code of pull
requests. A job that starts no container also runs without sudo and Docker, so that
no step can lift the block, and a job that may write reaches GitHub alone. Such a
job ends only after Harden-Runner has removed Docker, or the runner hangs until the
timeout of the job (#463). A new job, a new host or a job back in audit mode fails
here until this list and the comment of the job say why
(docs/development.md#network-of-the-jobs). The workflows that the blueprint keeps
follow its own rules."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).parents[1] / ".github" / "workflows"
PROJECT_WORKFLOWS = (
    "e2e.yml",
    "screenshots.yml",
    "translations.yml",
    "visual-comment.yml",
    "visual.yml",
)

GITHUB = {"api.github.com", "github.com"}
# Home Assistant from GitHub's registry, Playwright from Microsoft's.
HOME_ASSISTANT = {"ghcr.io", "pkg-containers.githubusercontent.com"}
PLAYWRIGHT = {"mcr.microsoft.com", "*.data.mcr.microsoft.com"}
PYTHON_PACKAGES = {"pypi.org", "files.pythonhosted.org"}
BROWSER_TEST = {
    "github.com",
    *HOME_ASSISTANT,
    *PLAYWRIGHT,
    *PYTHON_PACKAGES,
    # axe-core of package-lock.json
    "registry.npmjs.org",
}
IMAGES = {
    "github.com",
    *HOME_ASSISTANT,
    *PLAYWRIGHT,
    *PYTHON_PACKAGES,
    # pngquant of tests/e2e/pngquant.sh
    "launchpad.net",
    "launchpadlibrarian.net",
    # the icons of Home Assistant's other integrations, which the images show
    "brands.home-assistant.io",
    # the images of an earlier run with the same key (tests/e2e/render_key.py)
    "api.github.com",
}
COMPARISON = {"github.com", *PYTHON_PACKAGES}

HOSTS = {
    ("e2e.yml", "changes"): {"api.github.com"},
    ("e2e.yml", "scenario"): {"github.com", *HOME_ASSISTANT},
    ("e2e.yml", "browser"): BROWSER_TEST,
    # The explanations of the PR coach, which the gate checks out after a failure.
    ("e2e.yml", "gate"): {"github.com"},
    ("e2e.yml", "live-demo"): {"github.com", *PLAYWRIGHT, *PYTHON_PACKAGES},
    ("e2e.yml", "beta"): BROWSER_TEST,
    ("screenshots.yml", "render"): IMAGES,
    ("screenshots.yml", "collect"): COMPARISON,
    ("screenshots.yml", "pull-request"): GITHUB,
    # The recording of the live demo, by the integration in the Home Assistant of
    # the tests, whose packages it installs.
    ("screenshots.yml", "timeline"): {"github.com", *PYTHON_PACKAGES},
    ("translations.yml", "issues"): GITHUB,
    ("visual-comment.yml", "comment"): {"api.github.com"},
    ("visual.yml", "render"): IMAGES,
    ("visual.yml", "compare"): COMPARISON,
}
# The scripts that start containers: Home Assistant, the simulated board, Playwright.
CONTAINERS = re.compile(
    r"\bbash tests/e2e/(run|browser|screenshots|visual|demo|live_demo)\.sh\b"
)


def jobs() -> dict[tuple[str, str], dict]:
    """Every job of the project's own workflows, by workflow and job."""
    found = {}
    for name in PROJECT_WORKFLOWS:
        workflow = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
        for job, definition in workflow["jobs"].items():
            found[(name, job)] = definition
    return found


JOBS = jobs()


def harden_runner(job: dict) -> dict:
    """The settings of Harden-Runner, the first step of the job."""
    first = job["steps"][0]
    assert first.get("uses", "").startswith("step-security/harden-runner@")
    return first.get("with", {})


def allowed(settings: dict) -> list[str]:
    """The hosts of allowed-endpoints, each of which must name port 443."""
    endpoints = settings.get("allowed-endpoints", "").split()
    assert all(endpoint.endswith(":443") for endpoint in endpoints), endpoints
    return [endpoint.removesuffix(":443") for endpoint in endpoints]


def test_every_job_has_its_hosts_here():
    assert set(JOBS) == set(HOSTS)


@pytest.mark.parametrize("key", sorted(HOSTS), ids="/".join)
def test_harden_runner_blocks_every_host_that_the_job_does_not_need(key):
    settings = harden_runner(JOBS[key])
    assert settings["egress-policy"] == "block"
    hosts = allowed(settings)
    assert len(hosts) == len(set(hosts)), f"{key} names a host twice: {hosts}"
    assert set(hosts) == HOSTS[key]


@pytest.mark.parametrize("key", sorted(HOSTS), ids="/".join)
def test_a_job_without_containers_runs_without_sudo_and_docker(key):
    job = JOBS[key]
    containers = any(CONTAINERS.search(step.get("run", "")) for step in job["steps"])
    # Docker needs both; every other job gives them up, so no step lifts the block.
    assert harden_runner(job).get("disable-sudo-and-containers", False) is (
        not containers
    )


def may_write(job: dict) -> bool:
    """Whether the job holds a token that writes or the secrets of an environment."""
    return "environment" in job or "write" in job.get("permissions", {}).values()


WRITING = sorted(key for key, job in JOBS.items() if may_write(job))


def test_the_bots_are_the_jobs_that_may_write():
    assert WRITING == [
        ("screenshots.yml", "pull-request"),
        ("translations.yml", "issues"),
        ("visual-comment.yml", "comment"),
    ]


@pytest.mark.parametrize("key", WRITING, ids="/".join)
def test_a_job_that_may_write_reaches_github_alone(key):
    settings = harden_runner(JOBS[key])
    assert set(allowed(settings)) <= GITHUB
    assert settings.get("disable-sudo-and-containers") is True


# Without sudo and Docker, Harden-Runner removes Docker with apt-get in the background
# while the first steps run. A job that ends before apt-get does leaves it behind, and
# the runner hangs in "Cleaning up orphan processes" until the timeout of the job:
# *changes* of the end-to-end tests, done in ten seconds, did so twice (#463).
WAIT = "Wait until Harden-Runner has removed Docker"
WITHOUT_DOCKER = sorted(
    key
    for key, job in JOBS.items()
    if harden_runner(job).get("disable-sudo-and-containers") is True
)


def wait_step(job: dict) -> tuple[dict, list[dict]]:
    """The step that waits for the removal of Docker, and the steps after it."""
    steps = job["steps"]
    (index,) = [i for i, step in enumerate(steps) if step.get("name") == WAIT]
    return steps[index], steps[index + 1 :]


def test_the_short_jobs_run_without_docker():
    # The jobs that finish in seconds, whose end can overtake apt-get.
    assert {("e2e.yml", "changes"), ("e2e.yml", "gate")} <= set(WITHOUT_DOCKER)


@pytest.mark.parametrize("key", WITHOUT_DOCKER, ids="/".join)
def test_a_job_without_docker_ends_only_after_harden_runner_removed_it(key):
    step, after = wait_step(JOBS[key])
    # Also after a failure or a cancel, which end a job sooner still.
    assert step["if"] == "always()"
    # Only the explanation of the PR coach follows, after a failure, when apt-get
    # is done.
    assert all(later.get("if") == "failure()" for later in after), after


def test_every_job_without_docker_waits_the_same_way():
    assert len({wait_step(JOBS[key])[0]["run"] for key in WITHOUT_DOCKER}) == 1


# pgrep finds apt-get or dpkg in the first RUNNING checks and none after them.
PGREP = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
count=$(($(wc -l < "$CALLS")))
((count <= RUNNING))
"""
# sleep notes its seconds and returns at once.
SLEEP = """#!/usr/bin/env bash
printf '%s\\n' "$1" >> "$SLEEPS"
"""


@pytest.mark.skipif(shutil.which("bash") is None, reason="the step runs in bash")
@pytest.mark.parametrize(
    ("running", "checks", "warned"),
    [
        # Harden-Runner was done before the job: the job ends at once.
        (0, 1, False),
        # apt-get still removes Docker: the job waits a second for each check.
        (3, 4, False),
        # It never ends: after two minutes the job gives up with a warning and
        # ends, so the timeout of the job remains the last resort.
        (1000, 120, True),
    ],
)
def test_the_job_waits_until_apt_get_has_removed_docker(
    tmp_path, running, checks, warned
):
    step, _ = wait_step(JOBS[("e2e.yml", "changes")])
    (tmp_path / "step.sh").write_text(step["run"], encoding="utf-8", newline="\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, script in {"pgrep": PGREP, "sleep": SLEEP}.items():
        (bin_dir / name).write_text(script, encoding="utf-8", newline="\n")
        (bin_dir / name).chmod(0o755)
    calls, sleeps = tmp_path / "calls", tmp_path / "sleeps"
    calls.touch()
    sleeps.touch()

    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "step.sh"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "CALLS": str(calls),
            "SLEEPS": str(sleeps),
            "RUNNING": str(running),
        },
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    # Exactly apt-get and dpkg, by the name of their process.
    checked = calls.read_text(encoding="utf-8").splitlines()
    assert checked == ["-x apt-get|dpkg"] * checks
    waited = sleeps.read_text(encoding="utf-8").splitlines()
    assert waited == ["1"] * min(running, 120)
    assert ("::warning::" in result.stdout) is warned
