#!/usr/bin/env bash
# The checks of this integration alone, which scripts/check.sh runs last: the license
# terms, every line and branch of the key of the rendered images tested, the rules
# of ESLint for the JavaScript (eslint.config.mjs), and the tests of the dashboard
# cards and of the translation bot with Node (100 % of lines, branches and functions
# covered).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

printf '\n== %s\n' "The license"
python3 - <<'PYTHON'
import hashlib
from pathlib import Path

for path in ("LICENSE", "custom_components/homedarts/LICENSE"):
	text = Path(path).read_text(encoding="utf-8")
	if not text.startswith("MIT License\n") or "Copyright (c)" not in text:
		raise SystemExit(f"{path}: the MIT license and its copyright must stay.")
	terms = text[text.index("Permission is hereby granted"):]
	digest = hashlib.sha256(" ".join(terms.split()).encode()).hexdigest()
	# The MIT grant and disclaimer, whatever the names and the wrapping.
	if digest != "fe2a9817987f862eaced948f0468c7f51d2fedfc48c5c505b246a49a3870e9a5":
		raise SystemExit(f"{path}: the terms differ from the MIT license.")
print("LICENSE and the copy in the integration carry the MIT terms.")
PYTHON

printf '\n== %s\n' "The key of the rendered images, with every line and branch tested"
# tests/e2e/render_key.py decides whether the visual check and the screenshot bot
# take the images of an earlier run instead of rendering them; the coverage of the
# integration leaves tests/e2e out.
coverage_data="$(mktemp)"
python3 -m coverage run --rcfile=/dev/null --data-file="${coverage_data}" --branch \
	--include=tests/e2e/render_key.py -m pytest --quiet -p no:cacheprovider tests/test_render_key.py
python3 -m coverage report --rcfile=/dev/null --data-file="${coverage_data}" --show-missing --fail-under=100
rm -f "${coverage_data}"

printf '\n== %s\n' "The cards and the translation bot"
if ! command -v node >/dev/null 2>&1 || [[ ! -d node_modules ]]; then
	# The CI sets up Node and runs npm ci, so there a missing one is an error.
	if [[ -n "${CI:-}" ]]; then
		echo "Node.js or the packages of npm ci are missing." >&2
		exit 1
	fi
	echo "Node.js or its packages (npm ci) are missing here; the CI tests the cards."
	exit 0
fi
for module in custom_components/homedarts/frontend/*.js custom_components/homedarts/frontend/text/*.js; do
	node --check "$module"
done
npx --no-install eslint .
npm test
