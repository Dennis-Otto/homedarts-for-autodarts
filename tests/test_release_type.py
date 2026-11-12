"""scripts/release_type.py lets a title of the types feat, fix and perf, or one with a
`!`, through only when the pull request changes the package that HACS installs, so
that no release reaches users with an unchanged integration (#676)."""

import importlib.util
import io
import runpy
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "release_type.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release-type.yml"
SPEC = importlib.util.spec_from_file_location("release_type", SCRIPT)
release_type = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_type)

# What #651 changed, which made the release 2.3.1 with an unchanged integration.
WORKFLOWS_ONLY = [
    ".github/workflows/e2e.yml",
    ".github/checks.project.toml",
    "tests/test_workflow_network.py",
    "docs/development.md",
    "changelog.d/harden-runner-stops.md",
]


@pytest.mark.parametrize(
    ("title", "kind"),
    [
        ("feat: a dark mode", "feat"),
        ("fix(cards): keep the score", "fix"),
        ("perf: faster statistics", "perf"),
        ("feat!: drop the old Board Manager", "feat!"),
        ("ci!: a breaking change of any type releases", "ci!"),
        ("refactor(board)!: a new API", "refactor!"),
        ("ci: wait for Harden-Runner", None),
        ("docs: new pictures", None),
        ("chore: release 2.3.1", None),
        ("test: a slower clock", None),
        ("fixup: not a type that releases", None),
        ("no conventional title", None),
        ("fix:without a space", None),
    ],
)
def test_only_the_types_that_release_count(title, kind):
    assert release_type.releases(title) == kind


@pytest.mark.parametrize(
    "files",
    [
        ["custom_components/homedarts/sensor.py"],
        ["blueprints/automation/homedarts/checkout.yaml"],
        ["hacs.json"],
        # A file moved out of the integration changes it as well: the workflow passes
        # the old name of a renamed file too.
        ["tests/fixtures/old.json", "custom_components/homedarts/old.json"],
        [*WORKFLOWS_ONLY, "custom_components/homedarts/manifest.json"],
    ],
)
def test_a_release_that_changes_the_package_passes(files):
    passes, message = release_type.verdict("fix: keep the score", files, len(files))

    assert passes
    assert message.startswith("A fix changes the package that HACS installs: ")


def test_the_message_names_the_first_five_changed_files_of_the_package():
    files = [f"custom_components/homedarts/m{n}.py" for n in range(7)]

    _, message = release_type.verdict("feat: seven modules", files, len(files))

    assert message.endswith("m4.py and 2 more.")
    assert "m5.py" not in message


@pytest.mark.parametrize(
    "files",
    [
        WORKFLOWS_ONLY,
        ["scripts/screenshots.sh", "docs/images/en/card-light.png"],
        ["tests/test_board.py"],
        # Close to the package, but not in it.
        ["custom_components.md", "docs/blueprints/automation.md", "hacs.json.bak"],
        [],
    ],
)
def test_a_release_without_a_change_of_the_package_fails(files):
    passes, message = release_type.verdict(
        "fix(ci): the jobs stop when Harden-Runner doesn't block", files, len(files)
    )

    assert not passes
    assert "The type fix makes a release" in message
    assert "custom_components/, blueprints/ or hacs.json" in message


@pytest.mark.parametrize(
    ("files", "instead"),
    [
        (WORKFLOWS_ONLY, "Title it `test:` or `docs:` or `ci:` instead"),
        (["tests/test_board.py"], "Title it `test:` instead"),
        (["README.md", "docs/index.md"], "Title it `docs:` instead"),
        (["scripts/screenshots.sh"], "Title it `ci:` instead"),
        (["package.json", "eslint.config.mjs"], "Title it `chore:` instead"),
        ([], "Title it `ci:` instead"),
    ],
)
def test_the_failure_names_the_types_that_fit_the_files(files, instead):
    _, message = release_type.verdict("perf: fewer pictures", files, len(files))

    assert instead in message


def test_a_title_that_makes_no_release_passes_with_any_file():
    passes, message = release_type.verdict("ci: wait", WORKFLOWS_ONLY, 5)

    assert passes
    assert message.startswith("The title makes no release on its own")


def test_a_pull_request_with_more_files_than_the_api_lists_passes():
    passes, message = release_type.verdict("fix: everything", WORKFLOWS_ONLY, 3000)

    assert passes
    assert "3000 files, more than GitHub's API lists" in message


def test_main_reads_the_files_and_passes(capsys):
    stdin = io.StringIO("custom_components/homedarts/sensor.py\n\n")

    code = release_type.main(stdin, {"TITLE": "fix: keep the score", "CHANGED": "1"})

    assert code == 0
    assert "custom_components/homedarts/sensor.py" in capsys.readouterr().out


def test_main_fails_with_an_annotation_and_the_summary(tmp_path, capsys):
    summary = tmp_path / "summary.md"
    stdin = io.StringIO("".join(f"{name}\n" for name in WORKFLOWS_ONLY))
    environ = {
        "TITLE": "fix(ci): stop",
        "CHANGED": "5",
        "GITHUB_STEP_SUMMARY": str(summary),
    }

    code = release_type.main(stdin, environ)

    assert code == 1
    out = capsys.readouterr().out
    assert out.startswith("::error title=A release without a change of the package::")
    assert summary.read_text(encoding="utf-8").startswith(
        "The type fix makes a release"
    )


def test_main_fails_without_a_summary_on_your_machine(capsys):
    # No GITHUB_STEP_SUMMARY and no CHANGED outside of a run of GitHub.
    code = release_type.main(io.StringIO("docs/index.md\n"), {"TITLE": "feat: docs"})

    assert code == 1
    assert "Title it `docs:` instead" in capsys.readouterr().out


def test_the_script_runs_as_the_workflow_runs_it(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("hacs.json\n"))
    monkeypatch.setenv("TITLE", "feat!: a newer Home Assistant")
    monkeypatch.setenv("CHANGED", "1")

    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(SCRIPT), run_name="__main__")

    assert stopped.value.code == 0
    assert "A feat! changes the package that HACS installs: hacs.json." in (
        capsys.readouterr().out
    )


def test_main_requires_the_check_and_a_new_title_runs_it_again():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # YAML 1.1 reads the key on as true.
    triggers = workflow.get("on", workflow.get(True))
    assert "edited" in triggers["pull_request"]["types"]
    (job,) = workflow["jobs"].values()
    settings = tomllib.loads(
        (ROOT / ".github" / "repository.project.toml").read_text(encoding="utf-8")
    )
    assert job["name"] in settings["branch"]["required_checks"]
    (check,) = [
        step for step in job["steps"] if "release_type.py" in step.get("run", "")
    ]
    # The title as the pull request has it now, also in a run again, not that of the
    # event of the run.
    assert "TITLE" not in check["env"]
    assert '"repos/$GH_REPO/pulls/$NUMBER"' in check["run"]
    assert ".previous_filename" in check["run"]
