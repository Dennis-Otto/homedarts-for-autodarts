#!/usr/bin/env bash

# Regenerate the documentation images in docs/images from fresh demo instances.
# The demo's clock stands still at DEMO_TIME and its random numbers are fixed, so
# that two runs render the same images, byte for byte.
#
# The images come in fixed groups (GROUPS in screenshots.py), and every group starts
# from a fresh demo. SCREENSHOT_GROUP=2/3 renders the second of three groups alone,
# as one job of the visual check and of the screenshot bot does; without it, every
# group renders in turn. LANGUAGES chooses the languages (en de), and IMAGES the
# folder below the repository root that the images go to (docs/images).

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
DOCKER_BIN="${DOCKER_BIN:-docker}"
PROJECT_NAME="${E2E_PROJECT_NAME:-autodarts_demo}"
# Keep the image version equal to playwright in requirements-browser.in.
PLAYWRIGHT_IMAGE="mcr.microsoft.com/playwright/python:v1.63.0-noble@sha256:72bd171a9ffc2b4b59532aaa6210e21014d07093120dc25528870c0b840da1f0"
# A Tuesday evening, three days after the highlight photos of the demo.
export DEMO_TIME="${DEMO_TIME:-2026-09-29T20:30:00+02:00}"
# How many groups GROUPS in screenshots.py has.
GROUP_COUNT=3
IMAGES="${IMAGES:-docs/images}"

if [[ -n "${SCREENSHOT_GROUP:-}" ]]; then
	if [[ ! "${SCREENSHOT_GROUP}" =~ ^([1-9][0-9]*)/${GROUP_COUNT}$ ]] ||
		((BASH_REMATCH[1] > GROUP_COUNT)); then
		echo "SCREENSHOT_GROUP=${SCREENSHOT_GROUP}: choose one of the ${GROUP_COUNT} groups, 1/${GROUP_COUNT} to ${GROUP_COUNT}/${GROUP_COUNT}." >&2
		exit 2
	fi
	groups=("${BASH_REMATCH[1]}")
else
	mapfile -t groups < <(seq 1 "${GROUP_COUNT}")
fi
if [[ "${IMAGES}" == /* || "${IMAGES}" == *..* ]]; then
	echo "IMAGES=${IMAGES}: give a folder below the repository root, such as docs/images." >&2
	exit 2
fi

export E2E_PROJECT_NAME="${PROJECT_NAME}"
# Keep container paths unchanged and mount the Windows path when running from Git Bash.
export MSYS_NO_PATHCONV=1
ROOT_MOUNT="$(cd "${REPOSITORY_ROOT}" && (pwd -W 2>/dev/null || pwd))"

# diagnose, and a signal that stops the run as a failure.
# shellcheck source=tests/e2e/diagnose.sh
. "${SCRIPT_DIR}/diagnose.sh"
COMPOSE=("${DOCKER_BIN}" compose --project-name "${PROJECT_NAME}" --file compose.yaml)
# The container of the browser, beside the demo.
BROWSER="${PROJECT_NAME}-playwright"

# The Playwright image comes while the first demo starts; if that fails, docker run
# fetches it itself and says why it can't.
"${DOCKER_BIN}" pull --quiet "${PLAYWRIGHT_IMAGE}" >/dev/null 2>&1 &
pulling=$!

cleanup() {
	status=$?
	trap - EXIT
	keep_cleaning
	kill "${pulling}" 2>/dev/null || true
	# A group that failed or was stopped shows its containers and the end of the log
	# of Home Assistant.
	if ((status != 0)); then
		diagnose 100 "${COMPOSE[@]}"
	fi
	# A browser that a signal stopped still runs, and its docker run keeps the output
	# of the step open, so that GitHub would wait for it to the end.
	"${DOCKER_BIN}" rm --force "${BROWSER}" >/dev/null 2>&1 || true
	"${COMPOSE[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
	exit "${status}"
}
trap cleanup EXIT

# Relative Compose paths also work with Git Bash on Windows.
cd "${SCRIPT_DIR}"

for language in ${LANGUAGES:-en de}; do
	for group in "${groups[@]}"; do
		echo "Group ${group} of ${GROUP_COUNT} in ${language}, from a fresh demo"
		# In the background, so that a signal stops them at once.
		in_background env DEMO_LANGUAGE="${language}" bash "${SCRIPT_DIR}/demo.sh"
		wait "${pulling}" 2>/dev/null || true
		# The config volume of the demo holds the file that moves its frozen clock on.
		in_background "${DOCKER_BIN}" run --rm --name "${BROWSER}" --network "${PROJECT_NAME}_default" \
			--env "DEMO_LANGUAGE=${language}" \
			--env "DEMO_TIME=${DEMO_TIME}" \
			--env "DEMO_CLOCK=/ha-config/.demo_clock" \
			--env "SCREENSHOT_GROUP=${group}/${GROUP_COUNT}" \
			--env "OUTPUT=/repo/${IMAGES}" \
			--env "KEEP_RAW=${KEEP_RAW:-}" \
			--volume "${ROOT_MOUNT}:/repo" \
			--volume "${PROJECT_NAME}_homeassistant_config:/ha-config" \
			--workdir /repo/tests/e2e \
			"${PLAYWRIGHT_IMAGE}" \
			sh -c "bash pngquant.sh && pip install --quiet --disable-pip-version-check --root-user-action=ignore --break-system-packages --require-hashes -r requirements-browser.txt && python screenshots.py"
	done
done
