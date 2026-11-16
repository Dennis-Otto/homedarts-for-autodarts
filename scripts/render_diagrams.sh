#!/usr/bin/env bash

# Render the Mermaid diagrams in docs/diagrams as PNG images, once for light and
# once for dark themes. Markdown viewers without Mermaid, such as the GitHub app
# and HACS, show these images instead of raw diagram code.
#
#   bash scripts/render_diagrams.sh                       every diagram
#   bash scripts/render_diagrams.sh connection add-board  only these, in every language

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_BIN="${DOCKER_BIN:-docker}"
IMAGE="ghcr.io/mermaid-js/mermaid-cli/mermaid-cli:11.17.1@sha256:7b18341ab7398a0cfd290fdbf066243151c0adb4cbf5b81d8cf074f82019ec6f"
# Keep container paths unchanged and mount the Windows path when running from Git Bash.
export MSYS_NO_PATHCONV=1
MOUNT="$(cd "${ROOT}" && (pwd -W 2>/dev/null || pwd))"

# The diagrams named on the command line, or every diagram.
sources=()
if (($#)); then
	for diagram in "$@"; do
		matches=("${ROOT}/docs/diagrams/${diagram}".*.mmd)
		if [[ ! -e "${matches[0]}" ]]; then
			echo "No diagram ${diagram}: give the name of a source in docs/diagrams, such as architecture." >&2
			exit 2
		fi
		sources+=("${matches[@]}")
	done
else
	sources=("${ROOT}"/docs/diagrams/*.mmd)
fi

for source in "${sources[@]}"; do
	name="$(basename "${source}" .mmd)" # for example architecture.en
	diagram="${name%.*}"
	language="${name##*.}"
	for theme in light dark; do
		background="#ffffff"
		[[ "${theme}" == "dark" ]] && background="#0d1117"
		"${DOCKER_BIN}" run --rm --volume "${MOUNT}:/data" "${IMAGE}" \
			--input "/data/docs/diagrams/${name}.mmd" \
			--output "/data/docs/images/${language}/${diagram}-${theme}.png" \
			--configFile "/data/docs/diagrams/${theme}.json" \
			--backgroundColor "${background}" --scale 2 --width 900
		echo "rendered docs/images/${language}/${diagram}-${theme}.png"
	done
done
