"""Pin Assist's packages for the tests at the versions Home Assistant installs.

`tests/test_voice_blueprints.py` talks to Home Assistant's own Assist, whose
packages (hassil, home-assistant-intents, gazetteer-matcher) the conversation
manifest of Home Assistant names with exact versions. Renovate leaves them alone.
When pytest-homeassistant-custom-component brings a new Home Assistant, that test
fails, and this script writes the versions of its manifest into
`requirements-test.in` and compiles `requirements-test.txt` again with the
blueprint's `locks --compile --fix`: uv, which `requirements-test.txt` installs,
compiles it with the command in its header, for the Python named there, and keeps
every other pin of the file.

    python scripts/pin_assist.py

The fix bot runs it as well, by the autofix of the step of the tests in
`.github/checks.project.toml`: when the CI of a pull request fails, it runs it where
the `requirements-test.txt` of that pull request is installed, so the pull request of
Renovate for a new Home Assistant test base pins Assist by itself.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "requirements-test.in"
LOCK = ROOT / "requirements-test.txt"
# The blueprint's command that compiles each lock file of pip-compile again with the
# command in its header, on the versions that it pins.
COMPILE = (".github/blueprint.py", "locks", "--compile", "--fix")


def manifest_pins() -> dict[str, str]:
    """The packages and versions the installed Home Assistant installs for Assist."""
    spec = importlib.util.find_spec("homeassistant")
    if spec is None or spec.origin is None:
        raise SystemExit("Home Assistant is missing: install requirements-test.txt.")
    manifest = Path(spec.origin).parent / "components/conversation/manifest.json"
    requirements = json.loads(manifest.read_text(encoding="utf-8"))["requirements"]
    return dict(requirement.split("==", 1) for requirement in requirements)


def pin(text: str, wanted: dict[str, str]) -> str:
    """`requirements-test.in` with each package at its version; one it lacks at the
    end."""
    for name, version in sorted(wanted.items()):
        line = f"{name}=={version}"
        text, found = re.subn(rf"^{re.escape(name)}==\S+$", line, text, flags=re.M)
        if not found:
            text = f"{text.rstrip()}\n{line}\n"
    return text


def locked(lock: str, wanted: dict[str, str]) -> bool:
    """Whether `requirements-test.txt` holds each package at its version."""
    return all(
        re.search(rf"^{re.escape(f'{name}=={version}')}(?= |$)", lock, re.M)
        for name, version in wanted.items()
    )


def main() -> int:
    wanted = manifest_pins()
    text = SOURCE.read_text(encoding="utf-8")
    pinned = pin(text, wanted)
    if pinned == text and locked(LOCK.read_text(encoding="utf-8"), wanted):
        print(f"{SOURCE.name} and {LOCK.name} pin Assist as Home Assistant does.")
        return 0
    SOURCE.write_text(pinned, encoding="utf-8", newline="\n")
    print("Pinned", ", ".join(f"{n}=={v}" for n, v in sorted(wanted.items())))
    print("Compiling:", shlex.join(["python3", *COMPILE]), flush=True)
    subprocess.run([sys.executable, *COMPILE], cwd=ROOT, check=False)
    if locked(LOCK.read_text(encoding="utf-8"), wanted):
        return 0
    print(
        f"{LOCK.name} still pins other versions of them: install uv, which "
        f"{LOCK.name} names, then run: {shlex.join(['python3', *COMPILE])}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
