#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_BIN="${DOCKER_BIN:-docker}"
E2E_PORT="${E2E_PORT:-18123}"
PROJECT_NAME="${E2E_PROJECT_NAME:-homedarts_e2e}"
COMPOSE=("${DOCKER_BIN}" compose --project-name "${PROJECT_NAME}" --file compose.yaml)

export E2E_PORT
# Keep container paths such as /e2e unchanged when running from Git Bash on Windows.
export MSYS_NO_PATHCONV=1

# diagnose, and a signal that stops the run as a failure.
# shellcheck source=tests/e2e/diagnose.sh
. "${SCRIPT_DIR}/diagnose.sh"

cleanup() {
	status=$?
	trap - EXIT
	keep_cleaning
	if [[ "${status}" -ne 0 ]]; then
		# First what tells most about a run that hangs, before GitHub ends it.
		diagnose 300 "${COMPOSE[@]}"
		"${COMPOSE[@]}" logs --no-color --tail 300 || true
		# CI keeps the complete logs of a failed run as an artifact.
		if [[ -n "${E2E_ARTIFACTS:-}" ]]; then
			mkdir -p "${E2E_ARTIFACTS}"
			"${COMPOSE[@]}" exec -T homeassistant cat /config/home-assistant.log \
				>"${E2E_ARTIFACTS}/home-assistant-run.log" 2>/dev/null || true
			"${COMPOSE[@]}" logs --no-color board-mock >"${E2E_ARTIFACTS}/board-mock-run.log" 2>/dev/null || true
		fi
	fi
	if [[ "${KEEP_E2E:-0}" != "1" ]]; then
		"${COMPOSE[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
	else
		echo "E2E environment kept at http://127.0.0.1:${E2E_PORT} (project ${PROJECT_NAME})."
	fi
	exit "${status}"
}
trap cleanup EXIT

# The image of Home Assistant before anything starts, three times at most: a pull
# that the registry cuts off, such as "unexpected EOF" from ghcr.io, would otherwise
# fail inside "up", and the scenario only with "service homeassistant is not running".
PULL_ATTEMPTS=3
PULL_PAUSE="${E2E_PULL_PAUSE:-10}"
pull_images() {
	local attempt
	for ((attempt = 1; attempt <= PULL_ATTEMPTS; attempt++)); do
		if "${COMPOSE[@]}" pull --quiet --policy missing; then
			return 0
		fi
		if ((attempt < PULL_ATTEMPTS)); then
			echo "Pulling the images failed (attempt ${attempt} of ${PULL_ATTEMPTS}); trying again in ${PULL_PAUSE} s" >&2
			sleep "${PULL_PAUSE}"
		fi
	done
	echo "Pulling the images failed ${PULL_ATTEMPTS} times; the scenario did not start" >&2
	return 1
}

cd "${SCRIPT_DIR}"
"${COMPOSE[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
# In the background, so that a signal stops them at once.
in_background pull_images
in_background "${COMPOSE[@]}" up --detach --wait --wait-timeout 300
in_background "${COMPOSE[@]}" exec -T homeassistant python3 /e2e/scenario.py
