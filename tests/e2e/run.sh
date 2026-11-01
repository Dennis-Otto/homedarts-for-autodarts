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
	end_background
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

cd "${SCRIPT_DIR}"
"${COMPOSE[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
# In the background, so that a signal stops them at once. The image of Home Assistant
# before anything starts: inside "up", a failed pull would fail the scenario only with
# "service homeassistant is not running".
in_background pull_images "${COMPOSE[@]}" pull --quiet --policy missing
in_background "${COMPOSE[@]}" up --detach --wait --wait-timeout 300
in_background "${COMPOSE[@]}" exec -T homeassistant python3 /e2e/scenario.py
