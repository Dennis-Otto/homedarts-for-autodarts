"""The comparison of the documentation images, for the visual check and the bot.

tests/e2e/compare.py compares the images committed before a run of the screenshots
with those rendered: pixel by pixel, frame by frame, with the share of the pixels
that changed.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("compare", ROOT / "tests/e2e/compare.py")
compare = importlib.util.module_from_spec(SPEC)
# Its dataclass looks itself up by the name of its module.
sys.modules["compare"] = compare
SPEC.loader.exec_module(compare)


def picture(path: Path, colour=(20, 30, 40), size=(10, 10), dots=(), level=6) -> Path:
    """A plain PNG with red dots at the given places."""
    image = Image.new("RGB", size, colour)
    for dot in dots:
        image.putpixel(dot, (255, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, compress_level=level)
    return path


def animation(path: Path, durations=(100, 200), dots=()) -> Path:
    """An animated WebP of plain frames, the last with red dots."""
    frames = [
        Image.new("RGB", (8, 8), (0, 0, 80 + 40 * index))
        for index in range(len(durations))
    ]
    for dot in dots:
        frames[-1].putpixel(dot, (255, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=list(durations),
        lossless=True,
    )
    return path


@pytest.fixture
def folders(tmp_path):
    return tmp_path / "before", tmp_path / "after", tmp_path / "report"


def test_the_report_names_every_image_that_looks_different(folders):
    before, after, output = folders
    for folder in (before, after):
        picture(folder / "en" / "same.png")
        picture(folder / "de" / "same.png")
        (folder / "en" / "notes.txt").parent.mkdir(parents=True, exist_ok=True)
        (folder / "en" / "notes.txt").write_text("not an image")
    # The same pixels in another file: unchanged.
    picture(before / "en" / "recompressed.png", level=1)
    picture(after / "en" / "recompressed.png", level=9)
    # Five of a hundred pixels changed.
    picture(before / "en" / "card.png")
    picture(after / "en" / "card.png", dots=[(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)])
    picture(before / "de" / "grown.png")
    picture(after / "de" / "grown.png", size=(10, 12))
    picture(after / "de" / "new.png")
    picture(before / "de" / "gone.png")

    report = compare.run(before, after, output, ["en", "de"])

    assert report["unchanged"] == 3
    entries = {entry["path"]: entry for entry in report["images"]}
    assert set(entries) == {"en/card.png", "de/grown.png", "de/new.png", "de/gone.png"}
    card = entries["en/card.png"]
    assert card["status"] == "changed"
    assert card["share"] == pytest.approx(0.05)
    assert (output / card["before"]).read_bytes() == (
        before / "en/card.png"
    ).read_bytes()
    assert (output / card["after"]).read_bytes() == (after / "en/card.png").read_bytes()
    difference = Image.open(output / card["difference"])
    assert difference.getpixel((0, 0)) == compare.CHANGED
    assert difference.getpixel((9, 9)) != compare.CHANGED
    assert entries["de/grown.png"] | {"before": "", "after": ""} == {
        "path": "de/grown.png",
        "status": "changed",
        "share": 1.0,
        "before": "",
        "after": "",
    }
    assert entries["de/new.png"]["status"] == "added"
    assert (output / entries["de/new.png"]["after"]).exists()
    assert entries["de/gone.png"] == {
        "path": "de/gone.png",
        "status": "removed",
        "share": 1.0,
    }
    assert json.loads((output / "report.json").read_text()) == report
    summary = (output / "summary.md").read_text()
    assert "4 of 7 images look different" in summary
    assert "| `en/card.png` | changed | 5.00 % |" in summary
    assert "| `de/gone.png` | removed | 100 % |" in summary
    # Without --restore, the rendered file stays as it is.
    assert (after / "en/recompressed.png").read_bytes() != (
        before / "en/recompressed.png"
    ).read_bytes()


def test_restore_keeps_the_committed_file_of_an_image_that_did_not_change(folders):
    before, after, output = folders
    picture(before / "en" / "card.png", level=1)
    picture(after / "en" / "card.png", level=9)

    report = compare.run(before, after, output, ["en"], restore=True)

    assert report == {"languages": ["en"], "images": [], "unchanged": 1}
    assert (after / "en/card.png").read_bytes() == (before / "en/card.png").read_bytes()
    assert "All 1 images look as committed." in (output / "summary.md").read_text()


def test_animations_compare_frame_by_frame_with_their_times(folders):
    before, after, output = folders
    animation(before / "en" / "same.webp")
    animation(after / "en" / "same.webp")
    animation(before / "en" / "slower.webp")
    animation(after / "en" / "slower.webp", durations=(100, 300))
    animation(before / "en" / "dot.webp")
    animation(after / "en" / "dot.webp", dots=[(0, 0), (1, 0)])
    animation(before / "en" / "longer.webp")
    animation(after / "en" / "longer.webp", durations=(100, 200, 300))

    report = compare.run(before, after, output, ["en"])

    shares = {entry["path"]: entry["share"] for entry in report["images"]}
    assert set(shares) == {"en/slower.webp", "en/dot.webp", "en/longer.webp"}
    # A frame shown for another time counts as one pixel of two frames of 64.
    assert shares["en/slower.webp"] == pytest.approx(1 / 128)
    assert shares["en/dot.webp"] == pytest.approx(2 / 128)
    # The frame the image gained changed as a whole.
    assert shares["en/longer.webp"] == pytest.approx(1 / 3)
    entries = {entry["path"]: entry for entry in report["images"]}
    assert "difference" not in entries["en/slower.webp"]
    assert entries["en/dot.webp"]["difference"] == "en/dot.difference.png"


@pytest.mark.parametrize(
    ("share", "shown"),
    [(1.0, "100 %"), (0.00005, "< 0.01 %"), (0.12345, "12.35 %")],
)
def test_shares_read_as_percentages(share, shown):
    assert compare.percent(share) == shown


def test_two_renders_of_the_same_code_may_not_differ(folders, capsys):
    first, second, output = folders
    picture(first / "en" / "card.png")
    picture(second / "en" / "card.png", dots=[(5, 5)])
    picture(first / "en" / "same.png")
    picture(second / "en" / "same.png")

    arguments = [str(first), str(second), str(output), "--languages", "en", "--twice"]
    assert compare.main(arguments) == 1

    printed = capsys.readouterr().out
    assert "1 of 2 images came out differently" in printed
    assert "| `en/card.png` | changed | 1.00 % |" in printed
    # It explains itself: what it means and where to read on.
    assert "**To fix it,**" in printed
    assert "docs/development.md#the-same-images-in-every-run" in printed
    assert (output / "summary.md").read_text() == printed.removesuffix("\n")
    assert (output / "en" / "card.difference.png").is_file()


def test_two_renders_may_not_differ_by_a_single_pixel(folders):
    # A threshold would hide real changes along with the flapping ones.
    first, second, output = folders
    picture(first / "en" / "card.png", size=(1000, 1000))
    picture(second / "en" / "card.png", size=(1000, 1000), dots=[(5, 5)])

    arguments = [str(first), str(second), str(output), "--languages", "en", "--twice"]
    assert compare.main(arguments) == 1


def test_an_image_that_one_render_lacks_counts_as_a_difference(folders):
    first, second, output = folders
    picture(first / "en" / "card.png")
    picture(second / "en" / "card.png")
    picture(first / "en" / "gone.png")

    arguments = [str(first), str(second), str(output), "--languages", "en", "--twice"]
    assert compare.main(arguments) == 1


def test_two_renders_that_look_the_same_pass(folders, capsys):
    first, second, output = folders
    picture(first / "en" / "card.png", level=1)
    picture(second / "en" / "card.png", level=9)

    arguments = [str(first), str(second), str(output), "--languages", "en", "--twice"]
    assert compare.main(arguments) == 0

    assert "Both renders of all 1 images look the same." in capsys.readouterr().out


def test_two_renders_without_any_image_fail(folders, capsys):
    # A step that renders nothing shows no difference, and so proves nothing.
    first, second, output = folders

    arguments = [str(first), str(second), str(output), "--languages", "en", "--twice"]
    assert compare.main(arguments) == 1


def test_the_command_line(folders, capsys):
    before, after, output = folders
    picture(before / "de" / "card.png")
    picture(after / "de" / "card.png", dots=[(5, 5)])

    assert (
        compare.main([str(before), str(after), str(output), "--languages", "de"]) == 0
    )

    assert "| `de/card.png` | changed | 1.00 % |" in capsys.readouterr().out
    assert json.loads((output / "report.json").read_text())["languages"] == ["de"]
