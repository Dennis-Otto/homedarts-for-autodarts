#!/usr/bin/env bash

# Verify the dashboard card in a real browser against a fresh demo instance.
#
# BROWSER_SHARD=k/n runs the k-th of n parts of the steps (see shards.py), and
# BROWSER_WORKERS=W runs that part on W demo instances side by side, each with a
# browser and a shard of its own: worker w takes the shard (k - 1) * W + w of n * W.
# So BROWSER_WORKERS=4 runs every step on one machine in about a quarter of the time,
# and BROWSER_SHARD=1/2 with BROWSER_WORKERS=2, as on the first runner in CI, the
# shards 1/4 and 2/4.
# A shard that fails names the step that failed and the command that runs it alone,
# in GitHub Actions also as an annotation of the job and in its summary. So does a run
# that a signal stops, such as when its step in the workflow runs out of time.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
DOCKER_BIN="${DOCKER_BIN:-docker}"
PROJECT_NAME="${E2E_PROJECT_NAME:-homedarts_browser}"
# Keep the image version equal to playwright in requirements-browser.in.
PLAYWRIGHT_IMAGE="mcr.microsoft.com/playwright/python:v1.64.1-noble@sha256:330d401ae23c905896a0c26c66c36fc971b621519e7b11b435a8328d7bf6e031"

# The same default as demo.sh, so the checks expect the board the demo starts.
export BOARD_MANAGER="${BOARD_MANAGER:-2}"
PORT="${E2E_PORT:-18125}"
WORKERS="${BROWSER_WORKERS:-1}"
SHARD="${BROWSER_SHARD:-1/1}"
if [[ ! "${WORKERS}" =~ ^[1-9][0-9]*$ ]]; then
	echo "BROWSER_WORKERS is a number of at least 1, not '${WORKERS}'" >&2
	exit 2
fi
if [[ ! "${SHARD}" =~ ^([1-9][0-9]*)/([1-9][0-9]*)$ ]] || ((BASH_REMATCH[1] > BASH_REMATCH[2])); then
	echo "BROWSER_SHARD is k/n with 1 <= k <= n, such as 2/4, not '${SHARD}'" >&2
	exit 2
fi
PART="${BASH_REMATCH[1]}"
PARTS="${BASH_REMATCH[2]}"
# No more shards than groups of steps, before anything starts. STEP_GROUPS is GROUPS
# of shards.py, which tests/test_e2e_shards.py keeps equal.
STEP_GROUPS=4
if ((PARTS * WORKERS > STEP_GROUPS)); then
	echo "BROWSER_SHARD=${SHARD} with BROWSER_WORKERS=${WORKERS} makes $((PARTS * WORKERS)) shards, but the steps have only ${STEP_GROUPS} groups" >&2
	exit 2
fi
# Keep container paths unchanged and mount the Windows path when running from Git Bash.
export MSYS_NO_PATHCONV=1
ROOT_MOUNT="$(cd "${REPOSITORY_ROOT}" && (pwd -W 2>/dev/null || pwd))"
# Logs and screenshots of a failed run land here, with several workers in a folder per
# worker; CI uploads them.
ARTIFACTS="${E2E_ARTIFACTS:-${SCRIPT_DIR}/artifacts}"
mkdir -p "${ARTIFACTS}"

# The shard, Compose project and artifacts of a worker. One worker keeps the project,
# port and folder of a run without workers; the others take the next ports.
shard_of() { echo "$(((PART - 1) * WORKERS + $1))/$((PARTS * WORKERS))"; }
project_of() { if ((WORKERS == 1)); then echo "${PROJECT_NAME}"; else echo "${PROJECT_NAME}_$1"; fi; }
artifacts_of() {
	local shard
	shard="$(shard_of "$1")"
	if ((WORKERS == 1)); then echo "${ARTIFACTS}"; else echo "${ARTIFACTS}/shard-${shard/\//-of-}"; fi
}
compose_of() { "${DOCKER_BIN}" compose --project-name "$(project_of "$1")" --file compose.yaml "${@:2}"; }
# The container of the browser of a worker, beside its demo.
browser_of() { echo "$(project_of "$1")-playwright"; }

# diagnose, and a signal that stops the run as a failure.
# shellcheck source=tests/e2e/diagnose.sh
. "${SCRIPT_DIR}/diagnose.sh"

# The workers that failed, or the one worker while it runs, and those that passed.
FAILED=()
PASSED=()

# The step that failed in a worker, from the table of its steps that browser.py writes
# before and after each one, and how: the step that failed or took longer than its
# budget, or the one that still ran when a signal stopped the run; nothing when no step
# failed, such as when its demo didn't start. failed_step names it, step_end says how
# it ended: "failed", "took too long" or "running".
step_row() {
	local table line failed='^[|] (.+) [(](failed|took too long|running)[)] [|]'
	table="$(artifacts_of "$1")/browser-steps-table.md"
	if [[ -s "${table}" ]]; then
		while IFS= read -r line; do
			if [[ "${line}" =~ ${failed} ]]; then echo "${BASH_REMATCH[$2]}"; fi
		done <"${table}"
	fi
}
failed_step() { step_row "$1" 1; }
step_end() { step_row "$1" 2; }

# The command that runs what failed in a worker alone, on the same Home Assistant: the
# step that failed, which passes alone as every step does, or else the worker's shard.
alone() {
	local words=()
	if [[ -n "${HOME_ASSISTANT_IMAGE:-}" ]]; then words+=("HOME_ASSISTANT_IMAGE=${HOME_ASSISTANT_IMAGE}"); fi
	if [[ "${BOARD_MANAGER}" != 2 ]]; then words+=("BOARD_MANAGER=${BOARD_MANAGER}"); fi
	if [[ -n "$2" ]]; then
		words+=("BROWSER_STEPS='$2'")
	elif ((PARTS * WORKERS > 1)); then
		words+=("BROWSER_SHARD=$(shard_of "$1")")
	fi
	words+=(bash tests/e2e/browser.sh)
	echo "${words[*]}"
}

# A failed worker explains itself at the end: its shard, its step and the command that
# runs it alone. In GitHub Actions also as an annotation of the job and in its summary.
# An annotation has to begin its line, so it comes from here and not from the labelled
# lines of a worker.
explain() {
	local shard step command title what lines=""
	shard="$(shard_of "$1")"
	step="$(failed_step "$1")"
	command="$(alone "$1" "${step}")"
	title="Browser check failed"
	if ((PARTS * WORKERS > 1)); then title+=" in shard ${shard}"; fi
	what="The ${title,}"
	if [[ -n "${step}" ]]; then what+=" at the step \"${step}\""; fi
	if [[ -n "${STOPPED}" ]]; then what+=" when ${STOPPED} stopped it"; fi
	if ((WORKERS > 1)); then lines=" Its lines in the log begin with [${shard}]."; fi
	echo "${what}.${lines} Run it alone: ${command}"
	if [[ "${GITHUB_ACTIONS:-}" != true ]]; then return 0; fi
	local why="a card doesn't look or behave in a real browser as the test expects" end
	end="$(step_end "$1")"
	if [[ "${end}" == "took too long" ]]; then
		why="it took longer than its budget, and the log shows the line that it waited at"
	elif [[ -n "${STOPPED}" ]]; then
		why="the run took longer than its step in the workflow allows, and nothing in it ran out of time before"
	elif [[ "${end}" == running ]]; then
		why="the browser test ended in it without a result, such as when the watchdog ended a hang that no exception reached, and the log shows the stack of every thread"
	fi
	local kept="The artifact of this job keeps the screenshots and the logs."
	echo "::error title=${title}::${what}: ${why}.${lines} ${kept} Run it alone: ${command}"
	if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
		printf '\n### %s\n\nThat means %s.%s %s Run it alone:\n\n~~~sh\n%s\n~~~\n\n' \
			"${what}" "${why}" "${lines}" "${kept}" "${command}" >>"${GITHUB_STEP_SUMMARY}" || true
	fi
}

cleanup() {
	status=$?
	trap - EXIT
	keep_cleaning
	local worker folder
	# A signal stopped every worker that still ran.
	if [[ -n "${STOPPED}" ]]; then
		for ((worker = 1; worker <= WORKERS; worker++)); do
			if [[ " ${FAILED[*]} ${PASSED[*]} " != *" ${worker} "* ]]; then FAILED+=("${worker}"); fi
		done
	fi
	# First the browsers that a signal stopped, which still run, so that no container
	# outlives the step; they are not part of the Compose projects, and their lines are
	# already in the log.
	for ((worker = 1; worker <= WORKERS; worker++)); do
		"${DOCKER_BIN}" rm --force "$(browser_of "${worker}")" >/dev/null 2>&1 || true
	done
	# Then what tells most about a run that hangs, before GitHub ends it: the
	# containers of each failed worker, its logs and its explanation; the cleanup last.
	for ((worker = 1; worker <= WORKERS; worker++)); do
		folder="$(artifacts_of "${worker}")"
		# In CI, the summary of the job shows the seconds of every step, which
		# browser.py writes after each one, also after a failed step.
		if [[ -n "${GITHUB_STEP_SUMMARY:-}" && -s "${folder}/browser-steps-table.md" ]]; then
			cat "${folder}/browser-steps-table.md" >>"${GITHUB_STEP_SUMMARY}" || true
		fi
		if ((status != 0)) && [[ " ${FAILED[*]} " == *" ${worker} "* ]]; then
			diagnose 100 compose_of "${worker}"
			compose_of "${worker}" logs --no-color --tail 200 || true
			compose_of "${worker}" exec -T homeassistant cat /config/home-assistant.log \
				>"${folder}/home-assistant-browser.log" 2>/dev/null || true
		fi
	done
	if ((status != 0)); then
		for worker in "${FAILED[@]}"; do explain "${worker}" || true; done
	fi
	for ((worker = 1; worker <= WORKERS; worker++)); do
		compose_of "${worker}" down --volumes --remove-orphans >/dev/null 2>&1 || true
	done
	exit "${status}"
}
trap cleanup EXIT

# One worker: its demo instance, then its shard of the steps in the Playwright image.
worker() {
	local folder artifacts_mount
	folder="$(artifacts_of "$1")"
	mkdir -p "${folder}"
	rm -f "${folder}/browser-steps-table.md"
	artifacts_mount="$(cd "${folder}" && (pwd -W 2>/dev/null || pwd))"
	E2E_PROJECT_NAME="$(project_of "$1")" E2E_PORT="$((PORT + $1 - 1))" \
		bash "${SCRIPT_DIR}/demo.sh"
	"${DOCKER_BIN}" run --rm --name "$(browser_of "$1")" --network "$(project_of "$1")_default" \
		--env "BOARD_MANAGER=${BOARD_MANAGER}" \
		--env "BROWSER_ARTIFACTS=/artifacts" \
		--env "BROWSER_SHARD=$(shard_of "$1")" \
		--env "BROWSER_STEPS=${BROWSER_STEPS:-}" \
		--env "BROWSER_SCREENS=${BROWSER_SCREENS:-}" \
		--env "BROWSER_SCREENSHOTS=${BROWSER_SCREENSHOTS:-}" \
		--volume "${ROOT_MOUNT}:/repo:ro" \
		--volume "${artifacts_mount}:/artifacts" \
		--workdir /repo/tests/e2e \
		"${PLAYWRIGHT_IMAGE}" \
		sh -c "pip install --quiet --disable-pip-version-check --root-user-action=ignore --break-system-packages --require-hashes -r requirements-browser.txt && python browser.py"
}

# Every line of a worker, marked with its shard.
label() {
	local line
	while IFS= read -r line || [[ -n "${line}" ]]; do
		printf '[%s] %s\n' "$1" "${line}"
	done
}

# Relative Compose paths also work with Git Bash on Windows.
cd "${SCRIPT_DIR}"

# Both images at once, before the demo starts: Home Assistant's for the demo and its
# board, and Playwright's, which would otherwise wait for the demo.
started="${SECONDS}"
pull_images compose_of 1 pull --quiet --policy missing &
pulling=$!
if ! "${DOCKER_BIN}" image inspect "${PLAYWRIGHT_IMAGE}" >/dev/null 2>&1; then
	in_background pull_images "${DOCKER_BIN}" pull --quiet "${PLAYWRIGHT_IMAGE}" >/dev/null
fi
wait "${pulling}"
echo "Images ready in $((SECONDS - started)) s"

if ((WORKERS == 1)); then
	# Until it passes, a failure is the worker's, which cleanup explains.
	FAILED=(1)
	in_background worker 1
	exit 0
fi
workers=()
for ((w = 1; w <= WORKERS; w++)); do
	(worker "${w}" 2>&1 | label "$(shard_of "${w}")") &
	workers+=("$!")
done
# Every worker runs to its end, so that a run names all the shards that fail.
for ((w = 1; w <= WORKERS; w++)); do
	if wait "${workers[w - 1]}"; then PASSED+=("${w}"); else FAILED+=("${w}"); fi
done
# cleanup explains every shard that failed.
if ((${#FAILED[@]} > 0)); then exit 1; fi
