"""How tests/e2e/live_demo.sh starts the browser, checked without Docker.

live_demo.sh runs here with a stand-in for docker that only notes what it is asked to
do, and whose pull of the Playwright image fails as often as a test asks, as one does
that the registry cuts off with "connection reset by peer".
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

E2E = Path(__file__).parent / "e2e"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="live_demo.sh runs in bash"
)

# Notes every call; the image is there only with $PRESENT, and the first
# $PULL_FAILURES pulls fail.
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
"""


def live_demo_sh(
    tmp_path: Path, pull_failures: int, **env: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run live_demo.sh with the stand-in for docker; the result and the commands of
    docker, such as "pull" or "run", in their order."""
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
    if "PRESENT" not in env:
        environment.pop("PRESENT", None)
    result = subprocess.run(
        ["bash", str(E2E / "live_demo.sh")],
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=20,
    )
    lines = calls.read_text(encoding="utf-8").splitlines()
    return result, [line.split()[0] for line in lines]


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
