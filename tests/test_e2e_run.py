"""How tests/e2e/run.sh starts the scenario, checked without Docker.

run.sh runs here with a stand-in for docker that only notes what it is asked to do,
and whose pull of the images fails as often as a test asks, as one does that the
registry cuts off with "unexpected EOF", and whose scenario hangs when a test asks,
until the containers go down.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

E2E = Path(__file__).parent / "e2e"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="run.sh runs in bash"
)

# Notes every call; the first $PULL_FAILURES pulls fail, and with $HANG the scenario
# runs until the containers go down after it, as a "down" stops its "exec", or until
# it is ended, which notes in $CALLS.ended how many calls came before.
DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
if [[ -n "${HANG:-}" && "$*" == *scenario.py* ]]; then
  trap 'wc -l < "$CALLS" > "$CALLS.ended"; exit 143' TERM
  while (($(grep -c ' down ' "$CALLS") < 2)); do sleep 0.1 & wait "$!"; done
  exit 137
fi
if [[ "$*" == *" pull "* ]]; then
  failed=$(grep -c ' pull ' "$CALLS")
  if ((failed <= ${PULL_FAILURES:-0})); then
    echo "unexpected EOF" >&2
    exit 1
  fi
fi
"""


def run_sh(
    tmp_path: Path, pull_failures: int, command: list[str] | None = None, **env: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run run.sh with the stand-in for docker, or a command that runs it as $RUN_SH;
    the result and the calls of docker."""
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
        "RUN_SH": str(E2E / "run.sh"),
        **env,
    }
    for name in ("E2E_ARTIFACTS", "KEEP_E2E", "HANG"):
        if name not in env:
            environment.pop(name, None)
    result = subprocess.run(
        command or ["bash", str(E2E / "run.sh")],
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=20,
    )
    return result, calls.read_text(encoding="utf-8").splitlines()


def commands(calls: list[str]) -> list[str]:
    """What run.sh asked Compose to do, such as "pull" or "up", in its order."""
    return [call.split(" --file compose.yaml ", 1)[1].split()[0] for call in calls]


# What a failed run shows first: the containers, what they use of the CPU and the
# memory, and the end of the log of Home Assistant; then the logs of every container.
DIAGNOSIS = ["ps", "stats", "exec", "logs"]


@pytest.mark.parametrize("pull_failures", [0, 1, 2])
def test_the_scenario_starts_once_the_images_are_pulled(tmp_path, pull_failures):
    result, calls = run_sh(tmp_path, pull_failures)

    assert result.returncode == 0, result.stderr
    assert commands(calls) == [
        "down",
        *["pull"] * (pull_failures + 1),
        "up",
        "exec",
        "down",
    ]
    assert "pull --quiet --policy missing" in calls[1]
    assert result.stderr.count("trying again in 0 s") == pull_failures


def test_images_that_fail_to_pull_three_times_start_no_scenario(tmp_path):
    result, calls = run_sh(tmp_path, 3)

    assert result.returncode != 0
    # The logs of the failed run, as after any failure, and no scenario.
    assert commands(calls) == ["down", "pull", "pull", "pull", *DIAGNOSIS, "down"]
    assert calls[4].endswith(" ps --all")
    assert calls[5].endswith(" stats --no-stream")
    assert calls[6].endswith(" tail -n 300 /config/home-assistant.log")
    assert not any("scenario.py" in call for call in calls)
    assert result.stderr.count("trying again in 0 s") == 2
    assert "Pulling the images failed 3 times; nothing started" in result.stderr


def test_a_signal_stops_a_hung_scenario_with_the_logs_of_a_failed_run(tmp_path):
    # As GitHub stops a step of the workflow that runs out of time: the step runs
    # run.sh with exec, so that the signal reaches it, and run.sh shows its containers
    # while the scenario still hangs. Here SIGTERM, which GitHub sends 7.5 s after
    # SIGINT: bash starts a script in the background with SIGINT ignored.
    started = time.monotonic()
    result, calls = run_sh(
        tmp_path,
        0,
        [
            "bash",
            "-c",
            'bash "$RUN_SH" & run=$!\n'
            'until grep -q scenario.py "$CALLS"; do sleep 0.1; done\n'
            'kill -TERM "$run"\n'
            'wait "$run"',
        ],
        HANG="1",
    )

    assert result.returncode == 143, result.stderr
    assert time.monotonic() - started < 15
    assert "Stopped by SIGTERM; the state and the logs of the containers follow." in (
        result.stderr
    )
    assert commands(calls) == ["down", "pull", "up", "exec", *DIAGNOSIS, "down"]
    # The scenario that hung ended before the diagnosis, so nothing of the step
    # outlives it.
    ended = tmp_path / "calls.ended"
    assert int(ended.read_text(encoding="utf-8")) == 4
