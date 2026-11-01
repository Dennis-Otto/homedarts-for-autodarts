"""scripts/reach.sh prints the month's row of the reach table in the roadmap.

The script asks the GitHub CLI and the analytics of Home Assistant; here a fake
gh and a fake curl on the PATH answer instead, so the row is known.
"""

import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "reach.sh"
BASH = shutil.which("bash")
# Two pages of releases, as gh --paginate --slurp prints them: the downloads of
# homedarts.zip, and of autodarts.zip up to 1.18, count on both, those of other
# files do not.
RELEASES = [
    [
        {
            "tag_name": "v2.0.0",
            "assets": [
                {"name": "homedarts.zip", "download_count": 30},
                {"name": "notes.txt", "download_count": 99},
            ],
        }
    ],
    [
        {
            "tag_name": "v1.18.0",
            "assets": [{"name": "autodarts.zip", "download_count": 12}],
        }
    ],
]
REFERRERS = [
    {"referrer": "Google", "count": 3, "uniques": 2},
    {"referrer": "github.com", "count": 9, "uniques": 5},
]
MONTHS = {
    "en": "January February March April May June July August September October November December",
    "de": "Januar Februar März April Mai Juni Juli August September Oktober November Dezember",
}

pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash")


def fake(
    tmp_path: Path, versions: dict[str, int], domain: str = "homedarts"
) -> dict[str, str]:
    tmp_path.mkdir(exist_ok=True)
    answers = {
        "releases": RELEASES,
        "views": {"count": 40, "uniques": 17},
        "referrers": REFERRERS,
        "repository": {"stargazers_count": 4},
        "analytics": {domain: {"total": sum(versions.values()), "versions": versions}},
    }
    for name, answer in answers.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(answer), encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(
        f"""#!/usr/bin/env bash
case "$*" in
  *"--paginate --slurp"*releases*) cat '{tmp_path}/releases.json' ;;
  *traffic/views*) cat '{tmp_path}/views.json' ;;
  *traffic/popular/referrers*) cat '{tmp_path}/referrers.json' ;;
  *) cat '{tmp_path}/repository.json' ;;
esac
""",
        encoding="utf-8",
    )
    (bin_dir / "curl").write_text(
        f"#!/usr/bin/env bash\ncat '{tmp_path}/analytics.json'\n", encoding="utf-8"
    )
    for tool in bin_dir.iterdir():
        tool.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


def row(
    tmp_path: Path, versions: dict[str, int], *arguments: str, domain: str = "homedarts"
) -> list[str]:
    result = subprocess.run(
        [BASH, str(SCRIPT), *arguments],
        env=fake(tmp_path, versions, domain),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    line = result.stdout.strip()
    assert line.startswith("| ") and line.endswith(" |")
    return [cell.strip() for cell in line.strip("|").split("|")]


def month(language: str) -> str:
    today = datetime.datetime.now().astimezone()
    return f"{MONTHS[language].split()[today.month - 1]} {today.year}"


def test_the_row_counts_the_downloads_of_every_page_and_google_in_any_case(tmp_path):
    assert row(tmp_path, {"2.0.0": 3}) == [month("en"), "42", "17", "2", "Yes", "4"]


def test_installations_of_the_former_domain_count(tmp_path):
    assert row(tmp_path, {"1.18.0": 2}, domain="autodarts")[4] == "Yes"


def test_another_integration_with_the_former_domain_does_not_count(tmp_path):
    assert row(tmp_path, {"0.4.2": 8}, domain="autodarts")[4] == "No"


def test_the_german_row_names_the_month_and_the_answer_in_german(tmp_path):
    assert row(tmp_path, {"2.0.0": 1}, "de") == [
        month("de"),
        "42",
        "17",
        "2",
        "Ja",
        "4",
    ]
    assert row(tmp_path / "none", {}, "de")[4] == "Nein"
