"""scripts/sync_translations.py brings the translation files in step with strings.json:
en.json becomes its copy, and every other language takes its order and loses the texts
that it no longer has. The table of the card picker in the small module of every page
becomes the copy of the texts of the cards. The fix bot runs it when a check fails, so
it changes nothing but what a command may change, and leaves a file that is right byte
for byte."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "sync_translations.py"
SPEC = importlib.util.spec_from_file_location("sync_translations", SCRIPT)
sync_translations = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_translations)

SOURCE = {
    "title": "Autodarts",
    "config": {
        "step": {"user": {"title": "Add a board", "description": "Where it is"}},
        "abort": {"no_board": "No board"},
    },
    "services": {"start": {"name": "Start"}},
}
# The small module of every page, as far as the script reads it.
STRATEGY = "custom_components/homedarts/frontend/homedarts-strategy.js"
MODULE = (
    "const STRATEGY_TYPE = 1;\n\n{table}\n\nconst CARDS = [];\nconst OTHER = {{}};\n"
)


def files(root: Path, translations: dict[str, str], source: object = SOURCE) -> Path:
    """A repository with strings.json and the translation files of the languages."""
    integration = root / "custom_components" / "homedarts"
    (integration / "translations").mkdir(parents=True)
    (integration / "frontend" / "text").mkdir(parents=True)
    (integration / "frontend" / "homedarts-strategy.js").write_text(
        MODULE.format(table="const PICKER_TEXT = {};"), encoding="utf-8", newline="\n"
    )
    (integration / "strings.json").write_text(
        json.dumps(source, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    for name, text in translations.items():
        (integration / "translations" / name).write_text(
            text, encoding="utf-8", newline="\n"
        )
    return integration / "translations"


def text_of(tree: object) -> str:
    return json.dumps(tree, indent=2, ensure_ascii=False) + "\n"


def test_english_becomes_the_copy_of_the_source(tmp_path):
    folder = files(tmp_path, {"en.json": text_of({"title": "Old"})})

    changed, remaining = sync_translations.sync(tmp_path)

    strings = (folder.parent / "strings.json").read_text(encoding="utf-8")
    assert (folder / "en.json").read_text(encoding="utf-8") == strings
    assert changed == ["custom_components/homedarts/translations/en.json"]
    assert remaining == []


def test_a_missing_english_file_is_written(tmp_path):
    folder = files(tmp_path, {})

    changed, _ = sync_translations.sync(tmp_path)

    assert json.loads((folder / "en.json").read_text(encoding="utf-8")) == SOURCE
    assert changed == ["custom_components/homedarts/translations/en.json"]


def test_a_translation_takes_the_order_of_the_source_and_loses_old_texts(tmp_path):
    german = {
        "services": {"start": {"name": "Starten"}},
        "config": {
            "abort": {"no_board": "Kein Board", "gone": "Nicht mehr in strings.json"},
            "step": {"user": {"description": "Wo es ist", "title": "Board hinzufügen"}},
        },
        "title": "Autodarts",
    }
    folder = files(tmp_path, {"en.json": text_of(SOURCE), "de.json": text_of(german)})

    changed, remaining = sync_translations.sync(tmp_path)

    text = (folder / "de.json").read_text(encoding="utf-8")
    result = json.loads(text)
    assert sync_translations.paths(result) == sync_translations.paths(SOURCE)
    assert result["config"]["step"]["user"]["title"] == "Board hinzufügen"
    assert "ü" in text
    assert changed == ["custom_components/homedarts/translations/de.json"]
    assert remaining == []


def test_a_file_that_is_right_keeps_every_byte(tmp_path):
    # Escaped and written no-break spaces mixed, as fr.json has them: the file is
    # right, so the script doesn't write it in its own way.
    french = text_of(SOURCE).replace('"No board"', '"Aucune cible\\u00a0!"')
    french = french.replace('"Start"', '"Démarrer !"')
    folder = files(tmp_path, {"en.json": text_of(SOURCE), "fr.json": french})

    changed, remaining = sync_translations.sync(tmp_path)

    assert (folder / "fr.json").read_text(encoding="utf-8") == french
    assert changed == []
    assert remaining == []


def test_a_written_file_shows_its_invisible_spaces_as_escapes():
    text = sync_translations.dumped({"a": "Cible : ici", "b": "10 %"})

    assert text == '{\n  "a": "Cible\\u00a0: ici",\n  "b": "10\\u202f%"\n}\n'


def test_a_missing_text_stays_missing_for_a_person(tmp_path):
    dutch = {"title": "Autodarts", "services": {"start": {"name": "Starten"}}}
    folder = files(tmp_path, {"en.json": text_of(SOURCE), "nl.json": text_of(dutch)})

    changed, remaining = sync_translations.sync(tmp_path)

    assert json.loads((folder / "nl.json").read_text(encoding="utf-8")) == {
        "title": "Autodarts",
        "services": {"start": {"name": "Starten"}},
    }
    assert "custom_components/homedarts/translations/nl.json" not in changed
    assert remaining == [
        "custom_components/homedarts/translations/nl.json misses 3 of the texts of "
        "strings.json, such as config.step.user.title: write them in the language, "
        "or ask in the pull request for a maintainer or a native speaker to add them "
        "before the merge (CONTRIBUTING.md#translations)."
    ]


def test_a_text_where_the_source_has_a_group_stays_for_a_person():
    source = {"config": {"step": {"user": "x"}}, "title": "T"}
    translated = {"title": "T", "config": "Konfiguration"}

    assert sync_translations.ordered(source, translated) == {
        "config": "Konfiguration",
        "title": "T",
    }
    assert sync_translations.ordered({"a": "x"}, {"a": {"b": "y"}}) == {"a": {"b": "y"}}


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ('{"title": ', "is no JSON ("),
        ('["a list"]\n', "holds no object of texts"),
    ],
)
def test_a_broken_file_is_left_to_a_person(tmp_path, text, said):
    folder = files(tmp_path, {"en.json": text_of(SOURCE), "es.json": text})

    changed, remaining = sync_translations.sync(tmp_path)

    assert (folder / "es.json").read_text(encoding="utf-8") == text
    assert "custom_components/homedarts/translations/es.json" not in changed
    (line,) = remaining
    assert line.startswith(f"custom_components/homedarts/translations/es.json {said}")
    assert line.endswith("fix it by hand.")


def test_main_says_what_it_changed_and_fails_for_what_remains(tmp_path, capsys):
    files(
        tmp_path,
        {"en.json": text_of({}), "de.json": text_of({"title": "Autodarts"})},
    )

    assert sync_translations.main([], tmp_path) == 1

    out, err = capsys.readouterr()
    assert (
        out
        == "custom_components/homedarts/translations/en.json: in step with strings.json now.\n"
    )
    assert "translations/de.json misses 4 of the texts" in err


def card_texts(folder: Path, **languages: dict[str, str]) -> Path:
    """The modules of the texts of the cards, as a translator edits them, beside the
    translation files in folder; the small module that takes their picker texts."""
    texts = folder.parent / "frontend" / "text"
    for language, lines in languages.items():
        (texts / f"{language}.js").write_text(
            "// The texts of the dashboard cards, with a { in this comment.\n"
            f"export default {json.dumps(lines, indent=2, ensure_ascii=False)};\n",
            encoding="utf-8",
            newline="\n",
        )
    return folder.parent / "frontend" / "homedarts-strategy.js"


def test_the_card_picker_gets_a_copy_of_the_texts_of_the_cards(tmp_path, capsys):
    strategy = card_texts(
        files(tmp_path, {}),
        en={"visit": "Visit", "picker_live": "Live", "picker_live_x": 'Say "hi"'},
        fr={"visit": "Volée", "picker_live": "En direct : été"},
    )

    sync_translations.main([], tmp_path)

    # In the order of the languages' names, without the texts of the cards themselves,
    # with the letters of the language as they are and the invisible spaces as escapes.
    table = (
        "const PICKER_TEXT = {\n"
        '  "en": {\n'
        '    "picker_live": "Live",\n'
        '    "picker_live_x": "Say \\"hi\\""\n'
        "  },\n"
        '  "fr": {\n'
        '    "picker_live": "En direct\\u00a0: été"\n'
        "  }\n"
        "};"
    )
    assert strategy.read_text(encoding="utf-8") == MODULE.format(table=table)
    assert f"{STRATEGY}: in step with the texts of the cards now." in (
        capsys.readouterr().out
    )

    # Once in step, the module keeps every byte, however often the bot runs.
    with patch.object(Path, "write_text") as write:
        assert sync_translations.sync_picker(tmp_path) == []
    write.assert_not_called()


def test_the_card_picker_of_this_repository_is_in_step():
    strategy = (ROOT / STRATEGY).read_text(encoding="utf-8")
    folder = ROOT / sync_translations.FRONTEND / "text"
    assert sync_translations.with_picker_table(strategy, folder) == strategy, (
        "python scripts/sync_translations.py copies the picker_* texts of "
        "frontend/text/ to the table of homedarts-strategy.js"
    )


def test_main_says_when_everything_is_in_step(tmp_path, capsys):
    folder = files(tmp_path, {})
    shutil.copyfile(folder.parent / "strings.json", folder / "en.json")
    card_texts(folder, en={"picker_live": "Live"})
    assert sync_translations.sync_picker(tmp_path)

    assert sync_translations.main([], tmp_path) == 0

    assert capsys.readouterr().out == (
        "Every translation file is in step with strings.json.\n"
    )


def test_the_script_runs_on_its_own_in_the_repository_it_lives_in(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copyfile(SCRIPT, tmp_path / "scripts" / SCRIPT.name)
    folder = files(tmp_path, {})

    result = subprocess.run(
        [sys.executable, str(tmp_path / "scripts" / SCRIPT.name)],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads((folder / "en.json").read_text(encoding="utf-8")) == SOURCE


def test_the_translations_of_the_repository_are_in_step(tmp_path):
    # As the fix bot would find them: the script changes nothing, and no language
    # misses a text.
    shutil.copytree(
        ROOT / "custom_components" / "homedarts" / "translations",
        tmp_path / "custom_components" / "homedarts" / "translations",
    )
    shutil.copyfile(
        ROOT / "custom_components" / "homedarts" / "strings.json",
        tmp_path / "custom_components" / "homedarts" / "strings.json",
    )

    assert sync_translations.sync(tmp_path) == ([], [])
