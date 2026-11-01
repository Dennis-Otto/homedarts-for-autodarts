"""Bring the translation files of the integration in step with its English source.

custom_components/homedarts/strings.json holds the English texts, translations/en.json
is its copy, and every other file of translations/ has the same keys in the same order
(CONTRIBUTING.md#translations). This script makes what a command can make of that:

- en.json becomes the copy of strings.json;
- every other translation takes the order of strings.json and loses the texts that
  strings.json no longer has;
- the table of the card picker in homedarts-strategy.js becomes the copy of the texts
  picker_* of each language in frontend/text/, as that small module can't import them.

A text that a language misses stays missing, as only a person can write it: the
script names the first one, for the contributor or for a maintainer or a native
speaker who adds it before the merge (CONTRIBUTING.md#translations). A file that is right already keeps
every byte. tests/test_consistency.py checks the files; when a check fails, the fix
bot runs this script and commits what it changed (.github/checks.project.toml).

    python scripts/sync_translations.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = Path("custom_components", "homedarts")
ENGLISH = "en.json"
FRONTEND = INTEGRATION / "frontend"
STRATEGY = FRONTEND / "homedarts-strategy.js"
# The table of the card picker in that module, one object over many lines.
PICKER_TABLE = re.compile(r"^const PICKER_TEXT = \{.*?\};$", re.MULTILINE | re.DOTALL)
# Characters that look like a space but aren't, as escapes, so that a person sees them
# in the file: the no-break spaces of French before : ; ? and !.
INVISIBLE = {" ": "\\u00a0", " ": "\\u202f"}

type Tree = dict[str, object]


def ordered(source: Tree, translated: Tree) -> Tree:
    """The texts of a translation in the order of the source, without those that the
    source no longer has; a text where the source has a group of texts, or the other
    way round, stays as it is for a person to decide."""
    result: Tree = {}
    for key, value in source.items():
        if key not in translated:
            continue
        mine = translated[key]
        if isinstance(value, dict) and isinstance(mine, dict):
            result[key] = ordered(value, mine)
        else:
            result[key] = mine
    return result


def paths(tree: Tree, prefix: str = "") -> list[str]:
    """The path of every text of a tree, such as entity.sensor.round.name."""
    found: list[str] = []
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        found += paths(value, path) if isinstance(value, dict) else [path]
    return found


def dumped(tree: Tree) -> str:
    """A translation file as the others are written: two spaces of indent, the letters
    of the language as they are, and the invisible spaces as escapes."""
    text = json.dumps(tree, indent=2, ensure_ascii=False) + "\n"
    for character, escape in INVISIBLE.items():
        text = text.replace(character, escape)
    return text


def sync(root: Path) -> tuple[list[str], list[str]]:
    """Brings the translation files below root in step with strings.json: the files
    that it changed, and what remains for a person."""
    integration = root / INTEGRATION
    source_text = (integration / "strings.json").read_text(encoding="utf-8")
    source: Tree = json.loads(source_text)
    expected = paths(source)
    folder = integration / "translations"
    english = folder / ENGLISH
    changed: list[str] = []
    remaining: list[str] = []
    if not english.is_file() or english.read_text(encoding="utf-8") != source_text:
        english.write_text(source_text, encoding="utf-8", newline="\n")
        changed.append(english.relative_to(root).as_posix())
    for path in sorted(folder.glob("*.json")):
        if path.name == ENGLISH:
            continue
        name = path.relative_to(root).as_posix()
        try:
            tree = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            remaining.append(f"{name} is no JSON ({error}); fix it by hand.")
            continue
        if not isinstance(tree, dict):
            remaining.append(f"{name} holds no object of texts; fix it by hand.")
            continue
        result = ordered(source, tree)
        if json.dumps(result) != json.dumps(tree):
            path.write_text(dumped(result), encoding="utf-8", newline="\n")
            changed.append(name)
        present = set(paths(result))
        missing = [text for text in expected if text not in present]
        if missing:
            remaining.append(
                f"{name} misses {len(missing)} of the texts of strings.json, such as "
                f"{missing[0]}: write them in the language, or ask in the pull "
                "request for a maintainer or a native speaker to add them before "
                "the merge (CONTRIBUTING.md#translations)."
            )
    return changed, remaining


def picker_texts(module: str) -> dict[str, str]:
    """The texts of the card picker in a module of frontend/text/: JSON after "export
    default", with comments on lines of their own."""
    lines = (line for line in module.split("\n") if not line.lstrip().startswith("//"))
    code = "\n".join(lines)
    texts = json.loads(code[code.index("{") : code.rindex("}") + 1])
    return {key: text for key, text in texts.items() if key.startswith("picker_")}


def with_picker_table(strategy: str, folder: Path) -> str:
    """The strategy module with the table of the card picker of the modules in folder."""
    table = {
        path.stem: picker_texts(path.read_text(encoding="utf-8"))
        for path in sorted(folder.glob("*.js"))
    }
    written = dumped(table).rstrip("\n")
    # A function, so that the backslashes of the escapes stay as they are.
    return PICKER_TABLE.sub(lambda _: f"const PICKER_TEXT = {written};", strategy)


def sync_picker(root: Path) -> list[str]:
    """Brings the table of the card picker below root in step: the file it changed."""
    path = root / STRATEGY
    strategy = path.read_text(encoding="utf-8")
    result = with_picker_table(strategy, root / FRONTEND / "text")
    if result == strategy:
        return []
    path.write_text(result, encoding="utf-8", newline="\n")
    return [path.relative_to(root).as_posix()]


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.parse_args(argv)
    changed, remaining = sync(root)
    for name in changed:
        print(f"{name}: in step with strings.json now.")
    for name in sync_picker(root):
        print(f"{name}: in step with the texts of the cards now.")
    for line in remaining:
        print(line, file=sys.stderr)
    if not changed and not remaining:
        print("Every translation file is in step with strings.json.")
    return 1 if remaining else 0


if __name__ == "__main__":
    sys.exit(main())
