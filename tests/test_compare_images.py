"""The comparison of the documentation images, for the visual check and the bot.

tests/e2e/compare.py compares the images committed before a run of the screenshots
with those rendered: pixel by pixel, frame by frame, with the share of the pixels
that changed, and a picture of each difference that still shows on a phone.
"""

import importlib.util
import json
import os
import subprocess
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
# The red of a changed pixel and of the frames around the changes, as the blueprint's
# screenshot tool draws them in every repository.
RED = (220, 38, 38)
# About the width at which a phone, or Telegram, shows a picture.
PHONE = 1000


def is_red(pixel) -> bool:
    """Whether a pixel of a picture reads as the red of a difference, not as the pale
    grey around it."""
    red, green, blue = pixel[:3]
    return red > 150 and red - green > 100 and red - blue > 100


def red_pixels(image: Image.Image) -> int:
    image = image.convert("RGB")
    colours = image.getcolors(maxcolors=image.size[0] * image.size[1])
    return sum(count for count, colour in colours if is_red(colour))


def on_a_phone(image: Image.Image, method) -> Image.Image:
    """The picture as a phone shows it: scaled down to PHONE pixels at its longer
    side."""
    scale = PHONE / max(image.size)
    size = (round(image.size[0] * scale), round(image.size[1] * scale))
    return image.convert("RGB").resize(size, method)


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
    assert card["difference"] == "en/card.difference.png"
    with Image.open(output / card["difference"]) as drawn:
        assert drawn.format == "PNG"
        difference = drawn.convert("RGB")
    assert difference.getpixel((0, 0)) == RED
    assert not is_red(difference.getpixel((9, 9)))
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
    # Only the time of a frame changed, or the number of frames: no pair of frames
    # tells what changed.
    assert "difference" not in entries["en/slower.webp"]
    assert "difference" not in entries["en/longer.webp"]
    assert entries["en/dot.webp"]["difference"] == "en/dot.difference.png"
    with Image.open(output / "en/dot.difference.png") as drawn:
        assert drawn.size == (8, 8)
        assert drawn.convert("RGB").getpixel((1, 0)) == RED


@pytest.mark.parametrize("size", [(3000, 1500), (1200, 2400)], ids=["wide", "tall"])
@pytest.mark.parametrize(
    "method",
    [Image.Resampling.LANCZOS, Image.Resampling.BICUBIC, Image.Resampling.BOX],
    ids=["lanczos", "bicubic", "box"],
)
def test_a_single_changed_pixel_stays_in_sight_on_a_phone(folders, size, method):
    # A change of a few pixels in a large picture is a few red dots, which vanish when
    # a phone or the pager shows the picture scaled down: a red frame around each
    # place of change keeps it in sight.
    before, after, output = folders
    spot = (size[0] // 2, size[1] // 3)
    picture(before / "en" / "card.png", size=size)
    picture(after / "en" / "card.png", size=size, dots=[spot])

    (entry,) = compare.run(before, after, output, ["en"])["images"]

    with Image.open(output / entry["difference"]) as drawn:
        assert drawn.size == size
        difference = drawn.convert("RGB")
    assert difference.getpixel(spot) == RED
    # The new picture in pale grey, so that only the changes are red.
    assert all(
        colour == RED or (colour[0] == colour[1] == colour[2] and colour[0] >= 191)
        for _, colour in difference.getcolors(maxcolors=257)
    )
    assert red_pixels(on_a_phone(difference, method)) > 0
    # The changed pixel alone, without its frame, vanishes there.
    alone = Image.new("RGB", size, difference.getpixel((0, 0)))
    alone.putpixel(spot, RED)
    assert red_pixels(on_a_phone(alone, method)) == 0


def test_a_frame_surrounds_each_place_of_change(folders):
    before, after, output = folders
    # Two places of change, far from each other, and a third next to the first.
    picture(before / "en" / "card.png", size=(1000, 500))
    picture(
        after / "en" / "card.png",
        size=(1000, 500),
        dots=[(100, 100), (110, 104), (800, 400)],
    )

    (entry,) = compare.run(before, after, output, ["en"])["images"]

    with Image.open(output / entry["difference"]) as drawn:
        difference = drawn.convert("RGB")
    # A frame 4 pixels wide, 6 away from the changes: the changes near each other
    # share one.
    for place in [(92, 100), (118, 104), (100, 92), (110, 112), (792, 400), (808, 400)]:
        assert is_red(difference.getpixel(place)), place
    for place in [(96, 100), (105, 102), (115, 104), (455, 250), (796, 400)]:
        assert not is_red(difference.getpixel(place)), place


def test_an_animation_shows_its_frame_with_the_most_changes(folders):
    before, after, output = folders
    colours = [(0, 0, 80), (0, 80, 0), (80, 0, 0)]
    changes = {before: [[], [], []], after: [[(0, 0)], [(5, 5), (6, 6)], []]}
    for folder, dots in changes.items():
        frames = [Image.new("RGB", (8, 8), colour) for colour in colours]
        for frame, changed in zip(frames, dots, strict=True):
            for dot in changed:
                frame.putpixel(dot, (255, 255, 255))
        path = folder / "en" / "clip.webp"
        path.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            path, save_all=True, append_images=frames[1:], duration=100, lossless=True
        )

    (entry,) = compare.run(before, after, output, ["en"])["images"]

    assert entry["share"] == pytest.approx(3 / 192)
    with Image.open(output / entry["difference"]) as drawn:
        difference = drawn.convert("RGB")
    assert difference.getpixel((5, 5)) == difference.getpixel((6, 6)) == RED
    # The first frame, with its one change, isn't the one shown.
    assert not is_red(difference.getpixel((0, 0)))


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
    # A relative link leads nowhere from the page of the run.
    assert (
        "(https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/HEAD/"
        "docs/development.md#the-same-images-in-every-run)" in printed
    )
    # The annotation, which the bot-health bot quotes in its issue, names the images.
    annotation = (
        "::error title=Two renders differ::1 of 2 images came out differently: "
        "en/card.png. See the summary of this run."
    )
    assert printed == f"{(output / 'summary.md').read_text()}\n{annotation}\n"
    # The artifact of the run shows where the renders differ.
    report = json.loads((output / "report.json").read_text())
    assert report["images"][0]["difference"] == "en/card.difference.png"
    with Image.open(output / "en" / "card.difference.png") as drawn:
        assert drawn.convert("RGB").getpixel((5, 5)) == RED


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

    printed = capsys.readouterr().out
    assert "Both renders of all 1 images look the same." in printed
    assert "::error" not in printed


def test_two_renders_without_any_image_fail(folders, capsys):
    # A step that renders nothing shows no difference, and so proves nothing.
    first, second, output = folders

    arguments = [str(first), str(second), str(output), "--languages", "en", "--twice"]
    assert compare.main(arguments) == 1

    printed = capsys.readouterr().out
    assert "Neither render left an image in these languages" in printed
    assert "look the same" not in printed
    assert "::error title=No images to compare::" in printed


def test_the_command_line(folders, capsys):
    before, after, output = folders
    picture(before / "de" / "card.png")
    picture(after / "de" / "card.png", dots=[(5, 5)])

    assert (
        compare.main([str(before), str(after), str(output), "--languages", "de"]) == 0
    )

    assert "| `de/card.png` | changed | 1.00 % |" in capsys.readouterr().out
    assert json.loads((output / "report.json").read_text())["languages"] == ["de"]


def test_the_script_finds_the_tool_of_the_blueprint_from_any_folder(folders, tmp_path):
    # visual.sh, collect.sh and twice.yml run it as a script, each from another folder.
    before, after, output = folders
    picture(before / "en" / "card.png")
    picture(after / "en" / "card.png", dots=[(5, 5)])
    environment = {
        key: value for key, value in os.environ.items() if key != "PYTHONPATH"
    }

    subprocess.run(
        [sys.executable, ROOT / "tests/e2e/compare.py", before, after, output],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
    )

    (entry,) = json.loads((output / "report.json").read_text())["images"]
    assert (output / entry["difference"]).is_file()
