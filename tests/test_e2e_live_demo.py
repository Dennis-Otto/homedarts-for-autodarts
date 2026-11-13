"""How tests/e2e/live_demo.sh starts the browser, checked without Docker.

live_demo.sh runs here with a stand-in for docker that only notes what it is asked to
do, and whose pull of the Playwright image fails as often as a test asks, as one does
that the registry cuts off with "connection reset by peer".
"""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

E2E = Path(__file__).parent / "e2e"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="live_demo.sh runs in bash"
)

# Notes every call; the image is there only with $PRESENT, the first $PULL_FAILURES
# pulls fail, and with $SLOW the browser runs for a minute.
DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
if [[ "$1" == image ]]; then
  [[ -n "${PRESENT:-}" ]]
  exit
fi
if [[ "$1" == pull ]]; then
  failed=$(grep -c '^pull ' "$CALLS")
  if ((failed <= ${PULL_FAILURES:-0})); then
    echo "read: connection reset by peer" >&2
    exit 1
  fi
fi
if [[ "$1" == run && -n "${SLOW:-}" ]]; then
  exec sleep 60
fi
"""


def stand_in(tmp_path: Path, pull_failures: int, **env: str) -> dict[str, str]:
    """The environment of live_demo.sh with the stand-in for docker, which notes its
    calls in tmp_path / "calls"."""
    docker = tmp_path / "docker"
    docker.write_text(DOCKER, encoding="utf-8", newline="\n")
    docker.chmod(0o755)
    calls = tmp_path / "calls"
    calls.touch()
    environment = {
        **os.environ,
        "DOCKER_BIN": str(docker),
        "CALLS": str(calls),
        "PULL_FAILURES": str(pull_failures),
        "E2E_PULL_PAUSE": "0",
        "E2E_ARTIFACTS": str(tmp_path / "artifacts"),
        **env,
    }
    for name in ("PRESENT", "SLOW"):
        if name not in env:
            environment.pop(name, None)
    return environment


def docker_commands(tmp_path: Path) -> list[str]:
    """The commands of docker, such as "pull" or "run", in their order."""
    lines = (tmp_path / "calls").read_text(encoding="utf-8").splitlines()
    return [line.split()[0] for line in lines]


def live_demo_sh(
    tmp_path: Path, pull_failures: int, **env: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run live_demo.sh with the stand-in for docker; the result and the commands of
    docker, such as "pull" or "run", in their order."""
    result = subprocess.run(
        ["bash", str(E2E / "live_demo.sh")],
        env=stand_in(tmp_path, pull_failures, **env),
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=20,
    )
    return result, docker_commands(tmp_path)


@pytest.mark.parametrize("pull_failures", [0, 1, 2])
def test_the_browser_starts_once_the_image_is_pulled(tmp_path, pull_failures):
    # A pull that the registry cuts off ended the live demo at once, inside its
    # "docker run" (issue #701): it is tried again, as run.sh does with its images.
    result, commands = live_demo_sh(tmp_path, pull_failures)

    assert result.returncode == 0, result.stderr
    assert commands == ["image", *["pull"] * (pull_failures + 1), "run"]
    assert result.stderr.count("trying again in 0 s") == pull_failures


def test_an_image_that_fails_to_pull_three_times_starts_no_browser(tmp_path):
    result, commands = live_demo_sh(tmp_path, 3)

    assert result.returncode != 0
    assert commands == ["image", "pull", "pull", "pull"]
    assert "Pulling the images failed 3 times; nothing started" in result.stderr


def test_an_image_that_is_there_is_not_pulled_again(tmp_path):
    result, commands = live_demo_sh(tmp_path, 3, PRESENT="1")

    assert result.returncode == 0, result.stderr
    assert commands == ["image", "run"]


@pytest.mark.skipif(sys.platform == "win32", reason="signals reach bash on POSIX only")
def test_a_signal_stops_the_browser_at_once(tmp_path):
    # GitHub stops a step that runs out of time with SIGINT: the live demo ends then,
    # not only when its browser has ended (review of issue #701).
    process = subprocess.Popen(
        ["bash", str(E2E / "live_demo.sh")],
        env=stand_in(tmp_path, 0, PRESENT="1", SLOW="1"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        encoding="utf-8",
    )
    deadline = time.monotonic() + 10
    while docker_commands(tmp_path) != ["image", "run"] and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.2)

    process.send_signal(signal.SIGINT)
    started = time.monotonic()
    _, stderr = process.communicate(timeout=20)

    assert time.monotonic() - started < 5
    assert process.returncode == 130
    assert "Stopped by SIGINT" in stderr
