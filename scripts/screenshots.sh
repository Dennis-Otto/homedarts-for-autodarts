#!/usr/bin/env bash

# The pictures of this project, rendered in place, for the screenshot bot of the
# blueprint (screenshot-bot.yml) and on your machine: the images of the
# documentation in docs/images, each group from a fresh demo with its frozen clock
# (tests/e2e/screenshots.sh), and the recording of the games that the live demo of
# the website plays, docs/demo/timeline.json (scripts/record_demo.py).
#
# SCREENSHOTS_SHARD names one shard of .github/screenshots.toml, which the bot
# renders side by side, each on a runner of its own: <language>-<group>, such as
# en-2, renders the second of the four groups of images (GROUPS in
# tests/e2e/screenshots.py) in English, and timeline the recording. Without it,
# every shard renders in turn. A group renders into a folder of its own,
# tests/e2e/artifacts/rendered-<language>-<group>, as the jobs of the visual check
# do, and its images then go over those of its language in docs/images: the
# container of the browser owns the files it writes, and the bot gives each image
# whose pixels stayed the same its committed file back. A shard deletes no image,
# since none knows what the other groups render: the visual check of the pull request
# that drops an image names it as removed, and that pull request deletes it. A group
# that outlasts SCREENSHOTS_LIMIT (21m) gets SIGINT, and its shard fails.
#
# The recording needs a Python with the packages of requirements-test.txt: PYTHON,
# or else one that uv makes for .python-version, outside the repository.
#
#   bash scripts/screenshots.sh                             everything, in turn
#   SCREENSHOTS_SHARD=de-3 bash scripts/screenshots.sh      the third group in German
#   SCREENSHOTS_SHARD=timeline bash scripts/screenshots.sh  the recording alone
#   python3 .github/blueprint.py screenshots restore        then, as the bot does

set -euo pipefail

REPOSITORY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# The languages of the images, and how many groups GROUPS in screenshots.py has.
LANGUAGES=(en de)
GROUP_COUNT=4
# The screenshot tool, the recorder and uv; tests run stand-ins of their own.
RENDER="${SCREENSHOTS_RENDER:-${REPOSITORY_ROOT}/tests/e2e/screenshots.sh}"
RECORD="${SCREENSHOTS_RECORD:-${REPOSITORY_ROOT}/scripts/record_demo.py}"
UV="${UV:-uv}"
# The time limit of a group, as the old render step had it: well within the hour of
# the job, and GNU timeout ends the screenshot tool with SIGINT, so that it ends its
# demo and prints the state of its containers before the shard fails. A tool that
# outlasts the signal by two minutes gets killed.
LIMIT="${SCREENSHOTS_LIMIT:-21m}"

# One group of one language: rendered into a folder of its own, then over the
# images of that language. The seconds of its sections go into the summary of the
# job, as in the visual check.
render_group() {
	local language="$1" group="$2"
	local folder="tests/e2e/artifacts/rendered-${language}-${group}"
	rm -rf "${REPOSITORY_ROOT:?}/${folder}"
	local status=0
	LANGUAGES="${language}" SCREENSHOT_GROUP="${group}/${GROUP_COUNT}" IMAGES="${folder}" \
		timeout --signal=INT --kill-after=2m "${LIMIT}" bash "${RENDER}" || status=$?
	if ((status == 124 || status == 137)); then
		echo "Group ${group} in ${language} took longer than ${LIMIT}; its log above shows where it waits." >&2
	fi
	if ((status)); then
		exit "${status}"
	fi
	local images=()
	shopt -s nullglob
	images=("${REPOSITORY_ROOT}/${folder}/${language}"/*.png "${REPOSITORY_ROOT}/${folder}/${language}"/*.webp)
	shopt -u nullglob
	if ((${#images[@]} == 0)); then
		echo "Group ${group} in ${language} rendered no image; its log above shows why." >&2
		exit 1
	fi
	mkdir -p "${REPOSITORY_ROOT}/docs/images/${language}"
	cp -- "${images[@]}" "${REPOSITORY_ROOT}/docs/images/${language}/"
	echo "Group ${group} of ${GROUP_COUNT} in ${language}: ${#images[@]} images in docs/images/${language}."
	local table="${REPOSITORY_ROOT}/tests/e2e/artifacts/screenshots-${language}-${group}.md"
	if [[ -n "${GITHUB_STEP_SUMMARY:-}" && -f "${table}" ]]; then
		cat -- "${table}" >>"${GITHUB_STEP_SUMMARY}"
	fi
}

# The Python of the tests, for the recording: PYTHON, or one that uv makes for the
# version of .python-version, with the packages of requirements-test.txt.
test_python() {
	if [[ -n "${PYTHON:-}" ]]; then
		echo "${PYTHON}"
		return
	fi
	if ! command -v "${UV}" >/dev/null 2>&1; then
		echo "The recording needs the packages of requirements-test.txt: set PYTHON to a Python that has them, or install uv." >&2
		exit 1
	fi
	local venv="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/homedarts-recording"
	rm -rf "${venv}"
	"${UV}" venv --quiet --python "$(tr -d '[:space:]' <"${REPOSITORY_ROOT}/.python-version")" "${venv}" >&2
	"${UV}" pip install --quiet --python "${venv}" --require-hashes -r "${REPOSITORY_ROOT}/requirements-test.txt" >&2
	if [[ -x "${venv}/bin/python" ]]; then
		echo "${venv}/bin/python"
	else
		echo "${venv}/Scripts/python"
	fi
}

record_timeline() {
	local python
	python="$(test_python)"
	"${python}" "${RECORD}"
}

shard="${SCREENSHOTS_SHARD:-}"
if [[ -z "${shard}" ]]; then
	for language in "${LANGUAGES[@]}"; do
		for ((group = 1; group <= GROUP_COUNT; group++)); do
			render_group "${language}" "${group}"
		done
	done
	record_timeline
elif [[ "${shard}" == timeline ]]; then
	record_timeline
elif [[ "${shard}" =~ ^([a-z]{2})-([1-9][0-9]*)$ && " ${LANGUAGES[*]} " == *" ${BASH_REMATCH[1]} "* ]] &&
	((BASH_REMATCH[2] <= GROUP_COUNT)); then
	render_group "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
else
	echo "SCREENSHOTS_SHARD=${shard}: choose timeline or a language of ${LANGUAGES[*]} and a group of 1 to ${GROUP_COUNT}, such as en-2." >&2
	exit 2
fi
