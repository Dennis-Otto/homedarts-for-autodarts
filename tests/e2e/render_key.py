"""The key of the images that a job of the visual check or of the screenshot bot
renders, and the images of an earlier run with the same key that it takes instead.

Two renders of the same files make the same images, byte for byte
(docs/development.md#the-same-images-in-every-run). So the key of a group of a
language is a SHA-256 over the Git objects of every file that the render reads, the
files below INPUTS other than SKIPPED, with the language and the group, and the job
keeps its images as the artifact rendered-<language>-<group>-<key>. Before it
renders, the job looks for that artifact among the earlier runs of this repository.
It takes the images of the newest one that a run of the visual check or of the
screenshot bot kept, from a branch of this repository: never one of a fork, whose
pull request runs the visual check with workflows and images of its own making.
So a pull request that "Update branches" brings up to date with main without a
change of what its images are rendered from renders nothing anew, and neither does
the screenshot bot after its merge: main takes only pull requests that are up to
date, so the merge has the files that the last visual check of the pull request
rendered.

    python3 tests/e2e/render_key.py key en 2    the key of the second group in English
    python3 tests/e2e/render_key.py find en 2   the name of the artifact and the run
                                               whose images the job takes, for the
                                               step outputs

find looks only with REUSE=true, which the workflows set for pull requests and
pushes: the weekly run and a run on demand render anew, and catch what changed
outside the repository, such as the icons from brands.home-assistant.io. When the
artifacts can't be looked up, the job renders anew as well.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
# Raise it when the same files render other images, such as when the step that
# renders them in the workflows changes (tests/test_render_key.py pins that step).
FORMAT = 1
# What the render reads: the integration with its cards and its manifest, the
# blueprints that the demo shows, the screenshot tool with the demo, the compose
# files with the digests of Home Assistant and Playwright, and the recordings of the
# simulated Board Manager.
INPUTS = (
    "blueprints/automation/homedarts",
    "custom_components/homedarts",
    "tests/e2e",
    "tests/fixtures/board_manager",
)
# The files below INPUTS that no render reads, as the paths of both workflows skip
# them: the browser test, the end-to-end test and their notes.
SKIPPED = frozenset(
    {
        "tests/e2e/README.md",
        "tests/e2e/accessibility-baseline.toml",
        "tests/e2e/browser.py",
        "tests/e2e/browser.sh",
        "tests/e2e/configuration.yaml",
        "tests/e2e/run.sh",
        "tests/e2e/shards.py",
        "tests/fixtures/board_manager/README.md",
    }
)
# The workflows whose images a job takes.
WORKFLOWS = frozenset(
    {".github/workflows/screenshots.yml", ".github/workflows/visual.yml"}
)
# How many artifacts with the key the job looks at, newest first, before it renders.
CANDIDATES = 5
# The seconds that one answer of the API may take.
TIMEOUT = 30
LANGUAGE = re.compile(r"[a-z]{2}")
GROUP = re.compile(r"[1-9][0-9]*")


def files(root: Path = ROOT) -> list[tuple[str, str, str]]:
    """Every file of the commit checked out that a render reads, as its path, its
    mode and its Git object, in the order of Git."""
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", "HEAD", "--", *INPUTS],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    found = []
    for entry in filter(None, listing.split("\0")):
        about, path = entry.split("\t", 1)
        mode, _, blob = about.split(" ")
        if path not in SKIPPED:
            found.append((path, mode, blob))
    return found


def key(language: str, group: str, root: Path = ROOT) -> str:
    """The key of the images of a group of a language, rendered from the commit
    checked out."""
    digest = hashlib.sha256(f"{FORMAT}\n{language}\n{group}\n".encode())
    for path, mode, blob in files(root):
        digest.update(f"{mode} {blob} {path}\n".encode())
    return digest.hexdigest()


def api(path: str) -> Any:
    """The answer of GitHub's API to a GET of a path, with the token of the job."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    with urlopen(Request(f"{base}/{path}", headers=headers), timeout=TIMEOUT) as answer:
        return json.load(answer)


def candidates(artifacts: list[dict], name: str, repository_id: int) -> list[dict]:
    """The artifacts of a name that a run of this repository kept from a branch of
    this repository and that haven't expired, newest first."""
    found = []
    for artifact in artifacts:
        run = artifact.get("workflow_run") or {}
        if (
            artifact.get("name") == name
            and not artifact.get("expired", True)
            and run.get("repository_id") == repository_id
            and run.get("head_repository_id") == repository_id
        ):
            found.append(artifact)
    return sorted(found, key=lambda artifact: artifact["created_at"], reverse=True)


def trusted(run: dict, repository_id: int) -> bool:
    """Whether a run is one of the visual check or of the screenshot bot of this
    repository, for a branch of this repository and not of a fork."""
    # GitHub may add the ref that the workflow came from: path@ref.
    return (
        (run.get("path") or "").partition("@")[0] in WORKFLOWS
        and (run.get("repository") or {}).get("id") == repository_id
        and (run.get("head_repository") or {}).get("id") == repository_id
    )


def earlier(name: str, repository: str, repository_id: int) -> dict | None:
    """The newest run that kept images of the name and whose images a job takes."""
    listing = api(
        f"repos/{repository}/actions/artifacts?name={quote(name)}&per_page=100"
    )
    found = candidates(listing.get("artifacts", []), name, repository_id)
    for artifact in found[:CANDIDATES]:
        run = api(f"repos/{repository}/actions/runs/{artifact['workflow_run']['id']}")
        if trusted(run, repository_id):
            return run
    return None


def emit(variable: str, text: str) -> None:
    """Append text to the file that an environment variable of the runner names,
    such as the outputs of the step, or print it without one."""
    target = os.environ.get(variable)
    if target:
        with open(target, "a", encoding="utf-8") as file:
            file.write(text)
    else:
        print(text, end="")


def find(language: str, group: str) -> None:
    """The name of the artifact of the images, and the run whose images the job
    takes instead of rendering them, as the outputs name and run-id of the step,
    with a note in its summary."""
    name = f"rendered-{language}-{group}-{key(language, group)}"
    outputs = f"name={name}\n"
    if os.environ.get("REUSE") != "true":
        note = (
            "Rendered anew, as every run on a schedule or on demand does: it also"
            " catches what changed outside the repository, such as the icons of"
            " Home Assistant's other integrations."
        )
    else:
        repository = os.environ["GITHUB_REPOSITORY"]
        try:
            run = earlier(name, repository, int(os.environ["GITHUB_REPOSITORY_ID"]))
        # Any answer the lookup can't read, such as a connection that drops
        # mid-answer or an answer of an unexpected shape, ends in a fresh render.
        except (
            OSError,
            ValueError,
            http.client.HTTPException,
            KeyError,
            TypeError,
            AttributeError,
        ) as error:
            print(
                "::warning::The images of earlier runs can't be looked up"
                f" ({error}), so the job renders them anew."
            )
            note = f"Rendered anew: the images of earlier runs can't be looked up ({error})."
        else:
            if run is None:
                note = (
                    "Rendered anew: no earlier run of the visual check or of the"
                    " screenshot bot from a branch of this repository kept images"
                    " rendered from the same files."
                )
            else:
                outputs += f"run-id={run['id']}\n"
                link = f"[{run['name']} #{run['run_number']}]({run['html_url']})"
                print(
                    f"::notice::Reused from run {run['id']} ({run['name']}"
                    f" #{run['run_number']}): it rendered these images from the same"
                    " files."
                )
                note = (
                    f"Reused from run {link}, which rendered these images from the"
                    " same files on its branch"
                    f" `{run['head_branch']}`, so the job didn't render them anew."
                )
    emit("GITHUB_OUTPUT", outputs)
    emit(
        "GITHUB_STEP_SUMMARY",
        f"### The images of group {group} ({language})\n\n{note}\n\n"
        f"The artifact of these images, named by the key of their files: `{name}`.\n\n",
    )


def main(arguments: list[str]) -> int:
    if (
        len(arguments) != 3
        or arguments[0] not in ("key", "find")
        or not LANGUAGE.fullmatch(arguments[1])
        or not GROUP.fullmatch(arguments[2])
    ):
        print(
            "Usage: python3 tests/e2e/render_key.py key|find LANGUAGE GROUP,"
            " such as key en 2",
            file=sys.stderr,
        )
        return 2
    command, language, group = arguments
    if command == "key":
        print(key(language, group))
    else:
        find(language, group)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
