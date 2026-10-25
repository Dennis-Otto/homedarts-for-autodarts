"""A job of the visual check or of the screenshot bot takes the images of an earlier
run when they were rendered from the same files, and only from a run of this
repository's own workflows on one of its own branches, never of a fork
(tests/e2e/render_key.py)."""

import importlib.util
import io
import json
import runpy
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
import yaml

ROOT = Path(__file__).parents[1]
E2E = ROOT / "tests" / "e2e"
SCRIPT = E2E / "render_key.py"
SPEC = importlib.util.spec_from_file_location("render_key", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
render_key = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_key)

REPOSITORY = "Dennis-Otto/homedarts-for-autodarts"
OWN = 1001
FORK = 2002
KEY = "c0ffee" * 10 + "c0de"
NAME = f"rendered-en-2-{KEY}"


def workflow(name: str) -> dict:
    return yaml.safe_load(
        (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
    )


# The key ---------------------------------------------------------------------------


def git(cwd: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, encoding="utf-8", check=True
    ).stdout


@pytest.fixture
def repository(tmp_path, monkeypatch):
    """A repository with a file in every input of the render, the files that the
    render skips, and files outside of them. Git's variables that point it at
    another repository, such as GIT_DIR, which Git sets for its hooks in a worktree,
    are gone, so its commits never land in the repository that runs the tests."""
    for name in git(Path.cwd(), "rev-parse", "--local-env-vars").split():
        monkeypatch.delenv(name, raising=False)
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.com")
    for path in [
        *(f"{folder}/file.txt" for folder in render_key.INPUTS),
        *render_key.SKIPPED,
        "custom_components/homedarts/frontend/cards.js",
        "custom_components/other/manifest.json",
        "docs/index.md",
        "tests/test_cards.py",
        ".github/workflows/visual.yml",
    ]:
        write(tmp_path, path, "first\n")
    commit(tmp_path, "first")
    return tmp_path


def write(root: Path, path: str, text: str) -> None:
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(text, encoding="utf-8")


def commit(root: Path, message: str) -> None:
    git(root, "add", "--all")
    git(root, "commit", "--quiet", "--allow-empty", "--message", message)


def test_the_key_is_a_sha256_of_its_language_and_group(repository):
    keys = {
        render_key.key(language, group, repository)
        for language in ("en", "de")
        for group in ("1", "2", "3")
    }
    assert len(keys) == 6
    assert all(len(key) == 64 and int(key, 16) >= 0 for key in keys)
    assert render_key.key("en", "1", repository) == render_key.key(
        "en", "1", repository
    )


@pytest.mark.parametrize(
    "path",
    [
        "blueprints/automation/homedarts/file.txt",
        "custom_components/homedarts/file.txt",
        "custom_components/homedarts/frontend/cards.js",
        "tests/e2e/file.txt",
        "tests/fixtures/board_manager/file.txt",
    ],
)
def test_a_change_of_what_the_render_reads_changes_the_key(repository, path):
    before = render_key.key("en", "1", repository)
    write(repository, path, "second\n")
    commit(repository, "second")
    assert render_key.key("en", "1", repository) != before


def test_a_new_file_of_an_input_changes_the_key(repository):
    before = render_key.key("en", "1", repository)
    write(repository, "tests/e2e/new.py", "new\n")
    commit(repository, "new")
    assert render_key.key("en", "1", repository) != before


@pytest.mark.parametrize(
    "path",
    [
        *sorted(render_key.SKIPPED),
        "custom_components/other/manifest.json",
        "docs/index.md",
        "tests/test_cards.py",
        ".github/workflows/visual.yml",
    ],
)
def test_a_change_of_what_no_render_reads_keeps_the_key(repository, path):
    before = render_key.key("en", "1", repository)
    write(repository, path, "second\n")
    commit(repository, "second")
    assert render_key.key("en", "1", repository) == before


def test_the_merge_of_a_pull_request_has_the_key_of_its_last_check(repository):
    # main takes only pull requests that are up to date with it, and squashes them:
    # the commit on main has the files of the merge that the visual check rendered.
    git(repository, "checkout", "--quiet", "-b", "feature")
    write(repository, "custom_components/homedarts/frontend/cards.js", "feature\n")
    commit(repository, "the change of the pull request")
    git(repository, "checkout", "--quiet", "main")
    write(repository, "docs/index.md", "main moved on\n")
    commit(repository, "main moves on")
    git(repository, "checkout", "--quiet", "feature")
    git(repository, "merge", "--quiet", "--no-edit", "main")
    checked = render_key.key("en", "1", repository)
    git(repository, "checkout", "--quiet", "main")
    git(repository, "merge", "--quiet", "--squash", "feature")
    commit(repository, "the squash merge")
    assert render_key.key("en", "1", repository) == checked


def test_only_the_files_of_the_commit_count(repository):
    # The runner checks the commit out, so the key reads it from Git.
    before = render_key.key("en", "1", repository)
    write(repository, "tests/e2e/file.txt", "not committed\n")
    assert render_key.key("en", "1", repository) == before


@pytest.mark.mutation_unsafe
def test_the_key_reads_the_render_inputs_of_this_repository():
    paths = {path for path, _, _ in render_key.files()}
    assert {
        "custom_components/homedarts/manifest.json",
        "custom_components/homedarts/frontend/homedarts-card.js",
        "tests/e2e/screenshots.py",
        "tests/e2e/screenshots.sh",
        "tests/e2e/compose.yaml",
        "tests/e2e/frozen/sitecustomize.py",
    } <= paths
    assert any(path.startswith("blueprints/automation/homedarts/") for path in paths)
    assert any(path.startswith("tests/fixtures/board_manager/") for path in paths)
    assert not paths & render_key.SKIPPED
    assert all(path.startswith(render_key.INPUTS) for path in paths)


# The earlier images ----------------------------------------------------------------


def artifact(
    number: int,
    *,
    name: str = NAME,
    head: int = OWN,
    repository: int = OWN,
    expired: bool = False,
    created: str = "2026-10-25T10:00:00Z",
) -> dict:
    return {
        "id": 500 + number,
        "name": name,
        "expired": expired,
        "created_at": created,
        "workflow_run": {
            "id": number,
            "repository_id": repository,
            "head_repository_id": head,
            "head_branch": "feat/cards",
        },
    }


def workflow_run(
    number: int,
    *,
    path: str = ".github/workflows/visual.yml",
    head: int | None = OWN,
    repository: int = OWN,
) -> dict:
    return {
        "id": number,
        "name": "Visual check",
        "run_number": 70 + number,
        "html_url": f"https://github.com/{REPOSITORY}/actions/runs/{number}",
        "head_branch": "feat/cards",
        "path": path,
        "repository": {"id": repository},
        "head_repository": None if head is None else {"id": head},
    }


def test_the_artifacts_of_a_fork_are_never_candidates():
    # A pull request from a fork runs the visual check with the workflow of its own
    # branch, and could keep any images under the key of main.
    assert render_key.candidates([artifact(1, head=FORK)], NAME, OWN) == []


@pytest.mark.parametrize(
    "found",
    [
        artifact(1, expired=True),
        artifact(1, name=f"rendered-de-2-{KEY}"),
        artifact(1, repository=FORK, head=FORK),
        {**artifact(1), "workflow_run": None},
        {key: value for key, value in artifact(1).items() if key != "expired"},
    ],
    ids=["expired", "another name", "another repository", "no run", "unknown"],
)
def test_only_live_artifacts_of_the_key_from_this_repository_are_candidates(found):
    assert render_key.candidates([found], NAME, OWN) == []


def test_the_newest_candidate_comes_first():
    older = artifact(1, created="2026-10-24T10:00:00Z")
    newer = artifact(2, created="2026-10-25T09:00:00Z")
    assert render_key.candidates([older, newer], NAME, OWN) == [newer, older]


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/visual.yml",
        ".github/workflows/screenshots.yml",
        ".github/workflows/screenshots.yml@refs/heads/main",
    ],
)
def test_a_run_of_the_visual_check_or_the_bot_on_an_own_branch_is_trusted(path):
    assert render_key.trusted(workflow_run(1, path=path), OWN)


@pytest.mark.parametrize(
    "run",
    [
        workflow_run(1, head=FORK),
        workflow_run(1, head=None),
        workflow_run(1, repository=FORK),
        workflow_run(1, path=".github/workflows/e2e.yml"),
        workflow_run(1, path=".github/workflows/visual.yml.evil"),
        {**workflow_run(1), "path": None},
    ],
    ids=[
        "fork",
        "deleted fork",
        "other repository",
        "other workflow",
        "lookalike",
        "none",
    ],
)
def test_no_other_run_is_trusted(run):
    assert not render_key.trusted(run, OWN)


@pytest.fixture
def answers(monkeypatch):
    """GitHub's API, as a dictionary from each path to its answer."""
    known: dict[str, object] = {}
    asked: list[str] = []

    def api(path: str):
        asked.append(path)
        return known[path]

    monkeypatch.setattr(render_key, "api", api)
    return known, asked


LISTING = f"repos/{REPOSITORY}/actions/artifacts?name={NAME}&per_page=100"


def run_path(number: int) -> str:
    return f"repos/{REPOSITORY}/actions/runs/{number}"


def test_the_newest_trusted_run_gives_its_images(answers):
    known, asked = answers
    known[LISTING] = {
        "artifacts": [
            artifact(1, created="2026-10-24T08:00:00Z"),
            artifact(2, created="2026-10-25T08:00:00Z"),
        ]
    }
    known[run_path(2)] = workflow_run(2)
    known[run_path(1)] = workflow_run(1)
    assert render_key.earlier(NAME, REPOSITORY, OWN) == workflow_run(2)
    assert asked == [LISTING, run_path(2)]


def test_a_run_that_is_not_trusted_gives_nothing(answers):
    # The listing says the branch is of this repository, its run says a fork.
    known, asked = answers
    known[LISTING] = {
        "artifacts": [artifact(2, created="2026-10-25T08:00:00Z"), artifact(1)]
    }
    known[run_path(2)] = workflow_run(2, head=FORK)
    known[run_path(1)] = workflow_run(1, path=".github/workflows/screenshots.yml")
    assert render_key.earlier(NAME, REPOSITORY, OWN) == workflow_run(
        1, path=".github/workflows/screenshots.yml"
    )


def test_it_asks_about_a_few_runs_at_most(answers):
    known, asked = answers
    found = [
        artifact(number, created=f"2026-10-{10 + number}T08:00:00Z")
        for number in range(1, 9)
    ]
    known[LISTING] = {"artifacts": found}
    for number in range(1, 9):
        known[run_path(number)] = workflow_run(number, head=FORK)
    assert render_key.earlier(NAME, REPOSITORY, OWN) is None
    assert len(asked) == 1 + render_key.CANDIDATES


def test_no_artifact_of_the_key_gives_nothing(answers):
    known, asked = answers
    known[LISTING] = {"total_count": 0, "artifacts": []}
    assert render_key.earlier(NAME, REPOSITORY, OWN) is None
    assert asked == [LISTING]


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


@pytest.fixture
def opened(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        requests.append((request, timeout))
        return Answer(json.dumps({"artifacts": []}).encode())

    monkeypatch.setattr(render_key, "urlopen", urlopen)
    return requests


def test_the_api_asks_github_with_the_token_of_the_job(opened, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token-of-the-job")
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    assert render_key.api("repos/a/b/actions/artifacts") == {"artifacts": []}
    ((request, timeout),) = opened
    assert request.full_url == "https://api.github.com/repos/a/b/actions/artifacts"
    assert request.get_method() == "GET"
    assert request.get_header("Authorization") == "Bearer token-of-the-job"
    assert request.get_header("Accept") == "application/vnd.github+json"
    assert timeout == render_key.TIMEOUT


def test_the_api_of_another_server_and_without_a_token(opened, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_API_URL", "https://github.example/api/v3")
    render_key.api("repos/a/b")
    ((request, _),) = opened
    assert request.full_url == "https://github.example/api/v3/repos/a/b"
    assert request.get_header("Authorization") is None


# The step --------------------------------------------------------------------------


@pytest.fixture
def step(tmp_path, monkeypatch):
    """The environment of the step on the runner; the files of its outputs and its
    summary."""
    outputs, summary = tmp_path / "outputs", tmp_path / "summary"
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setenv("GITHUB_REPOSITORY_ID", str(OWN))
    monkeypatch.setenv("REUSE", "true")
    monkeypatch.setattr(render_key, "key", lambda language, group: KEY)
    return outputs, summary


def outputs_of(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines())


def test_the_step_names_the_run_whose_images_it_takes(step, answers, capsys):
    outputs, summary = step
    known, _ = answers
    known[LISTING] = {"artifacts": [artifact(42)]}
    known[run_path(42)] = workflow_run(42)

    render_key.find("en", "2")

    assert outputs_of(outputs) == {"name": NAME, "run-id": "42"}
    text = summary.read_text(encoding="utf-8")
    assert text.startswith("### The images of group 2 (en)\n")
    assert (
        f"Reused from run [Visual check #112](https://github.com/{REPOSITORY}"
        "/actions/runs/42)"
    ) in text
    assert "`feat/cards`" in text
    assert f"`{NAME}`" in text
    assert "::notice::Reused from run 42 (Visual check #112)" in capsys.readouterr().out


def test_the_step_never_takes_the_images_of_a_fork(step, answers):
    outputs, summary = step
    known, _ = answers
    known[LISTING] = {"artifacts": [artifact(42, head=FORK)]}

    render_key.find("en", "2")

    assert outputs_of(outputs) == {"name": NAME}
    assert "Rendered anew: no earlier run" in summary.read_text(encoding="utf-8")


@pytest.mark.parametrize("reuse", [None, "false", ""])
def test_a_run_on_a_schedule_or_on_demand_renders_anew(
    step, answers, monkeypatch, reuse
):
    outputs, summary = step
    if reuse is None:
        monkeypatch.delenv("REUSE")
    else:
        monkeypatch.setenv("REUSE", reuse)

    render_key.find("en", "2")

    assert outputs_of(outputs) == {"name": NAME}
    assert "Rendered anew, as every run on a schedule or on demand does" in (
        summary.read_text(encoding="utf-8")
    )
    assert answers[1] == []


@pytest.mark.parametrize(
    "error",
    [
        URLError("the host is blocked"),
        HTTPError(LISTING, 502, "Bad Gateway", {}, None),
        json.JSONDecodeError("Expecting value", "", 0),
    ],
    ids=["network", "http", "json"],
)
def test_without_the_api_the_job_renders_anew(step, monkeypatch, capsys, error):
    outputs, summary = step

    def fails(path):
        raise error

    monkeypatch.setattr(render_key, "api", fails)

    render_key.find("en", "2")

    assert outputs_of(outputs) == {"name": NAME}
    assert "::warning::The images of earlier runs can't be looked up" in (
        capsys.readouterr().out
    )
    assert "Rendered anew: the images of earlier runs can't be looked up" in (
        summary.read_text(encoding="utf-8")
    )


def test_without_the_files_of_the_runner_the_step_prints(step, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_OUTPUT")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY")
    monkeypatch.setenv("REUSE", "false")

    render_key.find("de", "1")

    printed = capsys.readouterr().out
    assert printed.startswith(f"name=rendered-de-1-{KEY}\n### The images of group 1")


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["key", "en"],
        ["show", "en", "1"],
        ["key", "EN", "1"],
        ["key", "en", "0"],
        ["find", "en", "1/3"],
        ["key", "en", "1", "extra"],
    ],
)
def test_the_command_line_refuses_what_it_does_not_know(arguments, capsys):
    assert render_key.main(arguments) == 2
    assert "Usage: python3 tests/e2e/render_key.py" in capsys.readouterr().err


def test_the_command_line_prints_the_key(monkeypatch, capsys):
    monkeypatch.setattr(render_key, "key", lambda language, group: f"{language}{group}")
    assert render_key.main(["key", "de", "3"]) == 0
    assert capsys.readouterr().out == "de3\n"


def test_the_command_line_looks_for_the_images(monkeypatch):
    found = []
    monkeypatch.setattr(render_key, "find", lambda *arguments: found.append(arguments))
    assert render_key.main(["find", "en", "2"]) == 0
    assert found == [("en", "2")]


@pytest.mark.mutation_unsafe
def test_the_script_runs_as_the_step_runs_it(tmp_path, monkeypatch, capsys):
    # As in the workflows: python3 tests/e2e/render_key.py key en 1.
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "key", "en", "1"])
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert stopped.value.code == 0
    assert capsys.readouterr().out == render_key.key("en", "1") + "\n"


# The workflows ---------------------------------------------------------------------

# Each workflow takes earlier images for its own event: the visual check for a pull
# request, the screenshot bot for a push to main.
REUSED_FOR = {"visual.yml": "pull_request", "screenshots.yml": "push"}


def steps_of(name: str) -> dict[str, dict]:
    return {
        step.get("name", step.get("uses")): step
        for step in workflow(name)["jobs"]["render"]["steps"]
    }


@pytest.mark.parametrize("name", sorted(REUSED_FOR))
def test_the_job_looks_for_earlier_images_before_it_renders(name):
    steps = steps_of(name)
    order = list(steps)
    look = steps["Look for the same images in an earlier run"]
    take = steps["Take the images of the earlier run"]
    render = steps["Render the images of the group with the frozen clock"]
    keep = steps["Keep the images of the group"]
    assert (
        order.index(look.get("name"))
        < order.index(take["name"])
        < order.index(render["name"])
        < order.index(keep["name"])
    )
    assert look["id"] == "earlier"
    assert look["run"] == 'python3 tests/e2e/render_key.py find "$LANGUAGE" "$GROUP"'
    assert look["env"] == {
        "LANGUAGE": "${{ matrix.language }}",
        "GROUP": "${{ matrix.group }}",
        "REUSE": f"${{{{ github.event_name == '{REUSED_FOR[name]}' }}}}",
        "GITHUB_TOKEN": "${{ github.token }}",
    }
    # Only the run that the lookup trusted, and a failed download renders anew.
    assert take["id"] == "reused"
    assert take["if"] == "${{ steps.earlier.outputs.run-id != '' }}"
    assert take["continue-on-error"] is True
    assert take["uses"].startswith("actions/download-artifact@")
    assert take["with"] == {
        "name": "${{ steps.earlier.outputs.name }}",
        "run-id": "${{ steps.earlier.outputs.run-id }}",
        "github-token": "${{ github.token }}",
        "path": "tests/e2e/artifacts/rendered",
    }
    assert render["if"] == "${{ steps.reused.outcome != 'success' }}"
    # The next week's runs find the images under their key, also those taken.
    assert "if" not in keep
    assert keep["with"]["name"] == "${{ steps.earlier.outputs.name }}"
    assert keep["with"]["path"] == "tests/e2e/artifacts/rendered/"
    assert keep["with"]["retention-days"] == 7
    assert workflow(name)["jobs"]["render"]["permissions"] == {
        "actions": "read",
        "contents": "read",
    }


@pytest.mark.parametrize("name", sorted(REUSED_FOR))
def test_the_key_knows_everything_that_the_render_step_gets(name):
    # The images depend on the files of the key, the language and the group alone:
    # a new setting of the render step needs a new FORMAT of render_key.py and a
    # new line here.
    render = steps_of(name)["Render the images of the group with the frozen clock"]
    assert render["run"] == "exec bash tests/e2e/screenshots.sh"
    assert render["env"] == {
        "LANGUAGES": "${{ matrix.language }}",
        "SCREENSHOT_GROUP": "${{ matrix.group }}/3",
        "IMAGES": "tests/e2e/artifacts/rendered",
    }
    assert render_key.FORMAT == 1
    assert ".github/workflows/" + name in render_key.WORKFLOWS


def test_both_workflows_render_alike():
    # So the images of either one are those that the other would render.
    visual, bot = steps_of("visual.yml"), steps_of("screenshots.yml")
    for step in (
        "Look for the same images in an earlier run",
        "Take the images of the earlier run",
        "Render the images of the group with the frozen clock",
        "Keep the images of the group",
    ):
        if step == "Look for the same images in an earlier run":
            assert {**visual[step]["env"], "REUSE": ""} == {
                **bot[step]["env"],
                "REUSE": "",
            }
        else:
            assert visual[step] == bot[step], step


@pytest.mark.parametrize(
    ("name", "job"), [("visual.yml", "compare"), ("screenshots.yml", "collect")]
)
def test_the_job_of_a_language_takes_the_images_of_every_key(name, job):
    steps = workflow(name)["jobs"][job]["steps"]
    (take,) = [
        step for step in steps if step.get("name") == "Take the images of every group"
    ]
    assert take["with"] == {
        "pattern": "rendered-${{ matrix.language }}-*",
        "path": "tests/e2e/artifacts",
    }
