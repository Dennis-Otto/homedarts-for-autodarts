#!/usr/bin/env bash

# Render the documentation images anew with the frozen clock of the demo and compare
# them with the committed ones, pixel by pixel. Afterwards docs/images holds the new
# images, and tests/e2e/artifacts/visual/ the report of compare.py: report.json,
# summary.md and every changed image before and after, with its difference. With
# RESTORE=1, an image whose pixels did not change keeps its committed file.
# LANGUAGES chooses the languages and SCREENSHOT_GROUP one group of the images, as
# for screenshots.sh. The visual check of pull requests (visual.yml) and the
# screenshot bot (screenshots.yml) do the same with one runner per group and
# language: screenshots.sh renders each group, and collect.sh puts them together.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
DOCKER_BIN="${DOCKER_BIN:-docker}"
# Keep the image version equal to playwright in requirements-browser.in.
PLAYWRIGHT_IMAGE="mcr.microsoft.com/playwright/python:v1.64.1-noble@sha256:330d401ae23c905896a0c26c66c36fc971b621519e7b11b435a8328d7bf6e031"
REFERENCE="${SCRIPT_DIR}/artifacts/visual-reference"
OUTPUT="${SCRIPT_DIR}/artifacts/visual"
export LANGUAGES="${LANGUAGES:-en de}"
# Keep container paths unchanged and mount the Windows path when running from Git Bash.
export MSYS_NO_PATHCONV=1
ROOT_MOUNT="$(cd "${REPOSITORY_ROOT}" && (pwd -W 2>/dev/null || pwd))"

rm -rf "${REFERENCE}" "${OUTPUT}"
mkdir -p "${REFERENCE}" "${OUTPUT}"
cp -R "${REPOSITORY_ROOT}/docs/images/." "${REFERENCE}/"

bash "${SCRIPT_DIR}/screenshots.sh"

options=(--languages "$(tr ' ' ',' <<<"${LANGUAGES}")")
if [[ -n "${RESTORE:-}" ]]; then
	options+=(--restore)
fi
"${DOCKER_BIN}" run --rm \
	--volume "${ROOT_MOUNT}:/repo" \
	--workdir /repo/tests/e2e \
	"${PLAYWRIGHT_IMAGE}" \
	sh -c "pip install --quiet --disable-pip-version-check --root-user-action=ignore --break-system-packages --require-hashes -r requirements-browser.txt && python compare.py artifacts/visual-reference ../../docs/images artifacts/visual ${options[*]}"
