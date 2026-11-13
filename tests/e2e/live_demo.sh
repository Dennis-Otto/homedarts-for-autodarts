#!/usr/bin/env bash

# Play the live demo of the website (docs/demo/) in a real browser: in every language,
# on a desktop and a phone, without an error in the console (tests/e2e/live_demo.py).
# It needs Docker and nothing else: no Home Assistant, because the demo brings its own.
# Screenshots of a failure go to tests/e2e/artifacts/live-demo, or to E2E_ARTIFACTS.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
DOCKER_BIN="${DOCKER_BIN:-docker}"
# Keep the image version equal to playwright in requirements-browser.in.
PLAYWRIGHT_IMAGE="mcr.microsoft.com/playwright/python:v1.64.1-noble@sha256:330d401ae23c905896a0c26c66c36fc971b621519e7b11b435a8328d7bf6e031"

export MSYS_NO_PATHCONV=1
ROOT_MOUNT="$(cd "${REPOSITORY_ROOT}" && (pwd -W 2>/dev/null || pwd))"
ARTIFACTS="${E2E_ARTIFACTS:-${SCRIPT_DIR}/artifacts}/live-demo"
mkdir -p "${ARTIFACTS}"
ARTIFACTS_MOUNT="$(cd "${ARTIFACTS}" && (pwd -W 2>/dev/null || pwd))"

# pull_images, and a signal that stops the run at once: the pull and the browser run
# with in_background, and the trap on EXIT ends the one that a signal stopped.
# shellcheck source=tests/e2e/diagnose.sh
. "${SCRIPT_DIR}/diagnose.sh"

cleanup() {
	trap - EXIT
	keep_cleaning
	end_background
}
trap cleanup EXIT

# The image before the browser starts, as in browser.sh: inside "docker run", a pull
# that the registry cuts off, such as "connection reset by peer" from
# mcr.microsoft.com, would end the live demo at once.
if ! "${DOCKER_BIN}" image inspect "${PLAYWRIGHT_IMAGE}" >/dev/null 2>&1; then
	in_background pull_images "${DOCKER_BIN}" pull --quiet "${PLAYWRIGHT_IMAGE}" >/dev/null
fi

in_background "${DOCKER_BIN}" run --rm \
	--env "LIVE_DEMO_ARTIFACTS=/artifacts" \
	--volume "${ROOT_MOUNT}:/repo:ro" \
	--volume "${ARTIFACTS_MOUNT}:/artifacts" \
	--workdir /repo/tests/e2e \
	"${PLAYWRIGHT_IMAGE}" \
	sh -c "pip install --quiet --disable-pip-version-check --root-user-action=ignore --break-system-packages --require-hashes -r requirements-browser.txt && python live_demo.py"
