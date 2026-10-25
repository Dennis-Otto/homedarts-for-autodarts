"""The table of the groups that the job of a language writes into its summary: every
group of the screenshot tool with its seconds, and a mark on one that took much
longer than the shortest (tests/e2e/group_times.py)."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "tests" / "e2e" / "group_times.py"
SPEC = importlib.util.spec_from_file_location("group_times", SCRIPT)
group_times = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(group_times)


def times(folder: Path, language: str, group: int, sections: dict, groups: int = 3):
    """The file of one group as screenshots.py writes it."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"screenshots-{language}-{group}.json").write_text(
        json.dumps(
            {
                "language": language,
                "group": group,
                "groups": groups,
                "sections": [[name, seconds] for name, seconds in sections.items()],
            }
        ),
        encoding="utf-8",
    )


def downloaded(artifacts: Path, language: str, group: int, sections: dict) -> None:
    """The file of a group in the folder of its artifact, as a job downloads it."""
    times(artifacts / f"times-{language}-{group}", language, group, sections)


def test_only_a_group_more_than_one_and_a_half_times_the_shortest_is_slow():
    assert group_times.slow({}) == {}
    assert group_times.slow({1: 100.0, 2: 150.0}) == {}
    assert group_times.slow({1: 100.0, 2: 151.0, 3: 300.0}) == {
        2: pytest.approx(1.51),
        3: pytest.approx(3.0),
    }


def test_the_table_lists_every_group_of_the_language_in_order(tmp_path):
    downloaded(tmp_path, "en", 2, {"more games": 283.0, "people": 221.0})
    downloaded(tmp_path, "en", 1, {"cards": 45.0, "games": 300.0})
    downloaded(tmp_path, "en", 3, {"corrections": 52.0, "tournaments": 400.0})
    # The other language has a table of its own.
    downloaded(tmp_path, "de", 1, {"cards": 1000.0})

    assert group_times.table("en", tmp_path) == (
        "### Screenshots: the groups (en)\n\n"
        "| Group | Sections | Seconds | Against the shortest |\n"
        "| --- | --- | ---: | --- |\n"
        "| 1/3 | cards, games | 345.0 | 1.00 × |\n"
        "| 2/3 | more games, people | 504.0 | 1.46 × |\n"
        "| 3/3 | corrections, tournaments | 452.0 | 1.31 × |\n"
    )


def test_the_table_marks_a_slow_group_and_says_how_to_balance_it(tmp_path):
    downloaded(tmp_path, "de", 1, {"cards": 344.1})
    downloaded(tmp_path, "de", 2, {"more games": 282.7, "people": 220.6})
    downloaded(tmp_path, "de", 3, {"tournaments": 704.4})

    table = group_times.table("de", tmp_path)

    assert "| 2/3 | more games, people | 503.3 | 1.46 × |" in table
    assert "| 3/3 | tournaments | 704.4 | ⚠️ 2.05 × |" in table
    assert "more than 1.5 times as long as the shortest" in table
    assert "`GROUPS` of `tests/e2e/screenshots.py`" in table


def test_a_group_without_times_is_named_and_the_others_still_compare(tmp_path):
    downloaded(tmp_path, "en", 1, {"cards": 300.0})
    downloaded(tmp_path, "en", 3, {"manual": 400.0})

    table = group_times.table("en", tmp_path)

    assert "| 2/3 | – | – | no times: the group failed |" in table
    assert "| 3/3 | manual | 400.0 | 1.33 × |" in table
    assert "⚠️" not in table


def test_the_times_that_screenshots_sh_leaves_in_the_folder_count_too(tmp_path):
    # visual.sh on one machine: the files lie in the artifacts themselves.
    times(tmp_path, "en", 1, {"cards": 100.0}, groups=2)
    times(tmp_path, "en", 2, {"games": 200.0}, groups=2)

    table = group_times.table("en", tmp_path)

    assert "| 1/2 | cards | 100.0 | 1.00 × |" in table
    assert "| 2/2 | games | 200.0 | ⚠️ 2.00 × |" in table


def test_without_any_times_the_table_says_so(tmp_path):
    assert group_times.table("en", tmp_path) == (
        "### Screenshots: the groups (en)\n\nNo group of this language left its times.\n"
    )


def test_the_script_writes_the_table_for_the_summary(tmp_path):
    downloaded(tmp_path, "en", 1, {"cards": 45.0})

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "en", str(tmp_path)],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == group_times.table("en", tmp_path)


def test_the_script_asks_for_the_language_and_the_folder(capsys):
    assert group_times.main(["en"]) == 2
    assert "Usage: group_times.py <language> <folder>" in capsys.readouterr().err


def test_main_writes_the_table(tmp_path, capsys):
    downloaded(tmp_path, "de", 1, {"cards": 45.0})

    assert group_times.main(["de", str(tmp_path)]) == 0
    assert capsys.readouterr().out == group_times.table("de", tmp_path)
