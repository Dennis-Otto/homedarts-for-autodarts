"""The jobs of the project's own workflows reach only the hosts that their steps need.

Harden-Runner, the first step of every job, blocks every other host: in the bots,
which may write, and in the tests and the images, which run the code of pull
requests. A job that starts no container also runs without sudo and Docker, so that
no step can lift the block, and a job that may write reaches GitHub alone. Such a
job ends only after Harden-Runner has removed Docker, or the runner hangs until the
timeout of the job (#463), a job with sudo first takes GitHub's DNS experiment out of
the way of Harden-Runner, and every job waits until Harden-Runner lets its hosts through
before a step needs them (#488). A new job, a new host or a job back in audit mode fails
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


# GitHub's DNS experiment on runners in westus2 sends the lookups past Harden-Runner,
# which then drops the addresses that it never saw: those of the hosts of the job, so
# that its steps fail, and those of the runner, so that the job hangs until its timeout.
# That was the cause of at least 33 of the 46 flaky jobs of #463. Harden-Runner undoes it
# since v2.22.3, when a single request for its feature flags answers within 3 s, and a
# job with sudo undoes it itself when that request didn't. A job without sudo can't: it
# has only the release of Harden-Runner, and the timeout of the job as the last resort.
SEE_LOOKUPS = "Let Harden-Runner see the DNS lookups"
WITH_SUDO = sorted(set(JOBS) - set(WITHOUT_DOCKER))
PINNED = re.compile(r"step-security/harden-runner@[0-9a-f]{40} # v(\d+)\.(\d+)\.(\d+)")


def see_lookups_step(key: tuple[str, str]) -> dict:
    """The step that takes the DNS experiment out of the way of Harden-Runner."""
    (step,) = [s for s in JOBS[key]["steps"] if s.get("name") == SEE_LOOKUPS]
    return step


@pytest.mark.parametrize("name", PROJECT_WORKFLOWS)
def test_harden_runner_is_a_release_that_undoes_the_dns_experiment(name):
    pinned = PINNED.findall((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert pinned
    assert all(tuple(map(int, version)) >= (2, 22, 3) for version in pinned), pinned


def test_the_jobs_that_keep_sudo_are_those_with_containers():
    assert {("e2e.yml", "browser"), ("visual.yml", "render")} <= set(WITH_SUDO)
    assert all(
        any(CONTAINERS.search(step.get("run", "")) for step in JOBS[key]["steps"])
        for key in WITH_SUDO
    )


@pytest.mark.parametrize("key", WITH_SUDO, ids="/".join)
def test_a_job_with_sudo_lets_harden_runner_see_the_lookups_before_any_other_step(key):
    assert JOBS[key]["steps"][1] == see_lookups_step(key)


def test_every_job_with_sudo_does_it_the_same_way():
    assert len({see_lookups_step(key)["run"] for key in WITH_SUDO}) == 1


# sudo runs the command; systemctl and resolvectl note what they are asked to do, and
# systemctl fails for what $FAILS names.
SUDO = """#!/usr/bin/env bash
exec "$@"
"""
NOTE = """#!/usr/bin/env bash
printf '%s %s\\n' "$(basename "$0")" "$*" >> "$CALLS"
if [[ -n "${FAILS:-}" && "$*" == *"$FAILS"* ]]; then
  exit 1
fi
"""
RESTART = "systemctl restart systemd-resolved"
STOP = "systemctl stop egress-dns-resolver.service egress-outbound-proxy.service"
FLUSH = "resolvectl flush-caches"


def run_see_lookups(
    tmp_path: Path, *dropins: str, nameserver: str = "127.0.0.53", fails: str = ""
) -> tuple[subprocess.CompletedProcess[str], list[str], Path]:
    """Run the step on a copy of the files of a runner, with these drop-ins of the
    experiment under /etc or /run; the result, the calls and the root of the copy."""
    root = tmp_path / "root"
    for folder in ("etc", "run"):
        (root / folder / "systemd" / "resolved.conf.d").mkdir(parents=True)
    for dropin in dropins:
        (root / dropin).write_text("[Resolve]\nDNS=\n", encoding="utf-8")
    (root / "etc" / "resolv.conf").write_text(
        f"nameserver {nameserver}\n", encoding="utf-8"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, script in {"sudo": SUDO, "systemctl": NOTE, "resolvectl": NOTE}.items():
        (bin_dir / name).write_text(script, encoding="utf-8", newline="\n")
        (bin_dir / name).chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    script = see_lookups_step(("e2e.yml", "scenario"))["run"]
    for folder in ("/etc/", "/run/"):
        script = script.replace(folder, f"{root}{folder}")
    (tmp_path / "step.sh").write_text(script, encoding="utf-8", newline="\n")

    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "step.sh"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "CALLS": str(calls),
            "FAILS": fails,
        },
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    return result, calls.read_text(encoding="utf-8").splitlines(), root


DROPIN = "systemd/resolved.conf.d/90-egress-proxy.conf"


@pytest.mark.skipif(shutil.which("bash") is None, reason="the step runs in bash")
def test_a_runner_without_the_experiment_stays_as_it_is(tmp_path):
    result, calls, root = run_see_lookups(tmp_path)

    assert result.returncode == 0, result.stderr
    assert calls == []
    assert "::notice::" not in result.stdout
    assert (root / "etc" / "resolv.conf").is_file()
    assert not (root / "etc" / "resolv.conf").is_symlink()


@pytest.mark.skipif(shutil.which("bash") is None, reason="the step runs in bash")
@pytest.mark.parametrize(
    ("dropins", "nameserver"),
    [
        ([f"etc/{DROPIN}"], "127.0.0.100"),
        ([f"etc/{DROPIN}", f"run/{DROPIN}"], "127.0.0.100"),
        ([f"run/{DROPIN}"], "127.0.0.53"),
        # Its resolver alone is enough to tell.
        ([], "127.0.0.100"),
    ],
)
def test_the_experiment_goes_as_harden_runner_itself_takes_it_away(
    tmp_path, dropins, nameserver
):
    result, calls, root = run_see_lookups(tmp_path, *dropins, nameserver=nameserver)

    assert result.returncode == 0, result.stderr
    assert "::notice::" in result.stdout
    assert not (root / "etc" / DROPIN).exists()
    assert not (root / "run" / DROPIN).exists()
    # First systemd-resolved reads its settings again, with the address of Harden-Runner
    # alone, then the lookups go to it and only then its stand-in stops, so that a
    # failure on the way leaves the lookups working.
    assert calls == [RESTART, STOP, FLUSH]
    link = root / "etc" / "resolv.conf"
    assert link.is_symlink()
    assert os.readlink(link) == f"{root}/run/systemd/resolve/stub-resolv.conf"


@pytest.mark.skipif(shutil.which("bash") is None, reason="the step runs in bash")
def test_services_that_do_not_stop_do_not_matter_any_more(tmp_path):
    # They are out of the way of the lookups by then, and a runner may have only one.
    result, calls, _ = run_see_lookups(tmp_path, f"etc/{DROPIN}", fails="stop")

    assert result.returncode == 0, result.stderr
    assert calls == [RESTART, STOP, FLUSH]


@pytest.mark.skipif(shutil.which("bash") is None, reason="the step runs in bash")
def test_lookups_that_did_not_come_back_fail_the_step_at_once(tmp_path):
    # Every later step would only fail on a blocked host, with less to say about why.
    result, calls, _ = run_see_lookups(tmp_path, f"etc/{DROPIN}", fails="restart")

    assert result.returncode != 0
    assert calls == [RESTART]


# Harden-Runner lets through only the addresses of lookups that it saw. An address that
# the runner asked for past it, before its firewall stood or with GitHub's DNS experiment,
# stays in the cache of systemd-resolved for up to a minute, and a step that gets it fails
# within milliseconds on a host that its job allows (#488). So each job first asks its
# hosts until they answer, like the jobs of the blueprint's workflows.
WARM_UP = "Wait until Harden-Runner lets the hosts through"
WILDCARD_JOB = ("e2e.yml", "live-demo")


def warm_up_step(key: tuple[str, str]) -> dict:
    """The step that waits until Harden-Runner lets the hosts of the job through."""
    (step,) = [s for s in JOBS[key]["steps"] if s.get("name") == WARM_UP]
    return step


@pytest.mark.parametrize("key", sorted(HOSTS), ids="/".join)
def test_a_job_waits_for_its_hosts_before_any_step_that_could_need_them(key):
    # A job with sudo takes the experiment away first: until then, it would only wait
    # for hosts that stay blocked.
    place = 2 if key in WITH_SUDO else 1
    assert JOBS[key]["steps"][place] == warm_up_step(key)


@pytest.mark.parametrize("key", sorted(HOSTS), ids="/".join)
def test_a_job_waits_for_the_very_hosts_that_it_allows(key):
    # By the same words, so that they can't drift apart, and nothing else from outside.
    assert warm_up_step(key)["env"] == {
        "HOSTS": harden_runner(JOBS[key])["allowed-endpoints"]
    }


@pytest.mark.parametrize("key", sorted(HOSTS), ids="/".join)
def test_the_wait_for_the_hosts_ends_by_itself_well_before_its_limit(key):
    # Two minutes, and a last try of at most 5 s for each host. The limit of the step
    # leaves the job its other steps if the wait hangs after all.
    step = warm_up_step(key)
    hosts = allowed(harden_runner(JOBS[key]))
    assert 120 + 5 * len(hosts) < step["timeout-minutes"] * 60
    assert step["timeout-minutes"] < JOBS[key]["timeout-minutes"]


def test_every_job_waits_for_its_hosts_the_same_way():
    assert len({warm_up_step(key)["run"] for key in JOBS}) == 1


def test_the_job_of_the_stand_ins_has_a_wildcard():
    assert any(host.startswith("*.") for host in HOSTS[WILDCARD_JOB])


# curl notes what it is asked and fails the first BLOCKED times; each look at the clock
# takes 3 s, as the sleep does that returns at once.
CURL = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
count=$(($(wc -l < "$CALLS")))
((count > BLOCKED))
"""
DATE = """#!/usr/bin/env bash
now=$(cat "$CLOCK")
echo "$((now + 3))" > "$CLOCK"
echo "$now"
"""
PROBE = (
    "--silent --head --connect-timeout 3 --max-time 5 --output /dev/null https://{}/"
)


def run_warm_up(
    tmp_path: Path, blocked: int
) -> tuple[subprocess.CompletedProcess[str], list[str], list[str]]:
    """Run the step with the hosts of its job, and curl failing the first times; the
    result, the calls of curl and the seconds of each sleep."""
    step = warm_up_step(WILDCARD_JOB)
    (tmp_path / "step.sh").write_text(step["run"], encoding="utf-8", newline="\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, script in {"curl": CURL, "date": DATE, "sleep": SLEEP}.items():
        (bin_dir / name).write_text(script, encoding="utf-8", newline="\n")
        (bin_dir / name).chmod(0o755)
    calls, sleeps, clock = tmp_path / "calls", tmp_path / "sleeps", tmp_path / "clock"
    calls.touch()
    sleeps.touch()
    clock.write_text("1000", encoding="utf-8")

    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "step.sh"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "HOSTS": step["env"]["HOSTS"],
            "CALLS": str(calls),
            "SLEEPS": str(sleeps),
            "CLOCK": str(clock),
            "BLOCKED": str(blocked),
        },
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    return (
        result,
        calls.read_text(encoding="utf-8").splitlines(),
        sleeps.read_text(encoding="utf-8").splitlines(),
    )


def hosts_to_ask() -> list[str]:
    """The hosts of the job that the stand-ins run, in its order, without its wildcard."""
    return [
        host
        for host in allowed(harden_runner(JOBS[WILDCARD_JOB]))
        if not host.startswith("*.")
    ]


@pytest.mark.skipif(shutil.which("bash") is None, reason="the step runs in bash")
def test_the_wait_asks_each_host_once_when_harden_runner_lets_it_through(tmp_path):
    result, calls, sleeps = run_warm_up(tmp_path, 0)

    assert result.returncode == 0, result.stderr
    # Only the question: no token, no data, and a wildcard names no host to ask.
    assert calls == [PROBE.format(host) for host in hosts_to_ask()]
    assert sleeps == []
    assert "Harden-Runner still blocks" not in result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="the step runs in bash")
def test_the_wait_asks_again_until_harden_runner_lets_the_host_through(tmp_path):
    result, calls, sleeps = run_warm_up(tmp_path, 3)

    first, *others = hosts_to_ask()
    assert result.returncode == 0, result.stderr
    assert calls == [PROBE.format(first)] * 4 + [PROBE.format(host) for host in others]
    assert sleeps == ["3"] * 3
    assert result.stdout.count(f"Harden-Runner still blocks {first}, waiting") == 3
    assert "::warning::" not in result.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="the step runs in bash")
def test_the_wait_warns_after_two_minutes_and_leaves_the_failure_to_the_step(tmp_path):
    # A host that doesn't answer may be one that this run doesn't need, so the job goes
    # on, and a step that needs it fails with its own message.
    result, calls, sleeps = run_warm_up(tmp_path, 100000)

    first, *others = hosts_to_ask()
    assert result.returncode == 0, result.stderr
    # 3 s for each look at the clock, so the first host takes the two minutes; each of
    # the others gets one last try.
    assert calls == [PROBE.format(first)] * 40 + [PROBE.format(host) for host in others]
    assert sleeps == ["3"] * 39
    for host in hosts_to_ask():
        assert (
            f"::warning::Harden-Runner still blocks {host} after two" in result.stdout
        )
