#!/usr/bin/env bash

# Put together the images that the groups of the screenshot tool rendered on runners
# of their own, and compare them with the committed ones, as visual.sh does after it
# rendered every group itself. The visual check (visual.yml) and the screenshot bot
# (screenshots.yml) run it for each language after the jobs of its groups, which
# leave the images of group k in tests/e2e/artifacts/rendered-<language>-<k>-<key>/,
# with the key of what the images are rendered from (tests/e2e/render_key.py);
# visual.sh leaves them in tests/e2e/artifacts/rendered-<language>-<k>/.
#
# Afterwards docs/images holds the new images, tests/e2e/artifacts/visual/ the report
# of compare.py, as after visual.sh, and tests/e2e/artifacts/collected/ the rendered
# images alone, for the pull request of the screenshot bot. Every image in
# docs/images comes from the screenshot tool or, as a diagram, from
# scripts/render_diagrams.sh; one that neither makes any more goes, and the report
# lists it as removed. With RESTORE=1, an image whose pixels did not change keeps its
# committed file. A group without images, or an image that two groups rendered,
# fails it. LANGUAGES chooses the languages (en de), and PYTHON a Python with the
# packages of requirements-browser.txt (python3).

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
ARTIFACTS="${SCRIPT_DIR}/artifacts"
REFERENCE="${ARTIFACTS}/visual-reference"
OUTPUT="${ARTIFACTS}/visual"
COLLECTED="${ARTIFACTS}/collected"
IMAGES="${REPOSITORY_ROOT}/docs/images"
DIAGRAMS="${REPOSITORY_ROOT}/docs/diagrams"
# How many groups GROUPS in screenshots.py has.
GROUP_COUNT=3
LANGUAGES="${LANGUAGES:-en de}"

shopt -s nullglob
missing=()
for language in ${LANGUAGES}; do
	for ((group = 1; group <= GROUP_COUNT; group++)); do
		rendered=("${ARTIFACTS}/rendered-${language}-${group}"{,-*}"/${language}"/*)
		if ((${#rendered[@]} == 0)); then
			missing+=("group ${group} in ${language}")
		fi
	done
done
if ((${#missing[@]})); then
	printf 'No images of %s: the job of the group shows why.\n' "${missing[@]}" >&2
	exit 1
fi

rm -rf "${REFERENCE}" "${OUTPUT}" "${COLLECTED}"
mkdir -p "${REFERENCE}" "${OUTPUT}"
cp -R "${IMAGES}/." "${REFERENCE}/"

# The group of every image, and its file.
declare -A from file
for language in ${LANGUAGES}; do
	mkdir -p "${COLLECTED}/${language}"
	for ((group = 1; group <= GROUP_COUNT; group++)); do
		for image in "${ARTIFACTS}/rendered-${language}-${group}"{,-*}"/${language}"/*; do
			name="${language}/$(basename -- "${image}")"
			if [[ -n "${from[${name}]:-}" ]]; then
				echo "${name} comes from group ${from[${name}]} and group ${group}; each image belongs to one group." >&2
				exit 1
			fi
			from["${name}"]="${group}"
			file["${name}"]="${image}"
		done
	done
	declare -A diagram=()
	for source in "${DIAGRAMS}"/*."${language}".mmd; do
		name="$(basename -- "${source}" ".${language}.mmd")"
		diagram["${language}/${name}-light.png"]=1
		diagram["${language}/${name}-dark.png"]=1
	done
	for image in "${IMAGES}/${language}"/*.png "${IMAGES}/${language}"/*.webp; do
		name="${language}/$(basename -- "${image}")"
		if [[ -z "${from[${name}]:-}" && -z "${diagram[${name}]:-}" ]]; then
			echo "${name} comes from no group and no diagram any more; it goes."
			rm -- "${image}"
		fi
	done
	unset diagram
done
for name in "${!from[@]}"; do
	cp "${file[${name}]}" "${IMAGES}/${name}"
done
echo "Put together ${#from[@]} images of ${GROUP_COUNT} groups in ${LANGUAGES}."

options=(--languages "$(tr ' ' ',' <<<"${LANGUAGES}")")
if [[ -n "${RESTORE:-}" ]]; then
	options+=(--restore)
fi
"${PYTHON:-python3}" "${SCRIPT_DIR}/compare.py" "${REFERENCE}" "${IMAGES}" "${OUTPUT}" "${options[@]}"

# The images as they go into docs/images, with the committed file of every image
# whose pixels did not change.
for name in "${!from[@]}"; do
	cp "${IMAGES}/${name}" "${COLLECTED}/${name}"
done
