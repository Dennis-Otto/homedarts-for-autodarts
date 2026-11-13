"""Compare two folders of documentation images pixel by pixel.

visual.sh runs it after rendering the images anew, and collect.sh after putting
together the groups of images that rendered on runners of their own: the images
committed before the run against those rendered. It writes, into the output folder:

- report.json: every image whose pixels changed, was added or removed, with the
  share of its pixels that changed, for the screenshot bot and the comment of the
  visual check;
- summary.md: the same as a table, for the summary of the workflow run;
- for every changed image, the image before and after and, when both have the same
  size and frames, two pictures of the pair of frames with the most changed pixels,
  which the report names with the number of that frame, from 1, as `frame` of
  `frames`:
  - `comparison`: the place of the change before and after in one picture, of that
    same frame, in the colours of the image, with a red frame around each change on
    both sides, so that one look on a phone tells what changed;
  - `difference`: the image after in its own colours behind a light veil of its
    average colour, every changed pixel in red and a red frame around each place of
    change, which still shows a single changed pixel when a phone shows the picture
    scaled down to about 1000 pixels wide.
  They are the pictures that the blueprint's screenshot tool draws
  (.github/blueprint/screenshots.py), under the names of its report, so that the
  changes of every repository look alike, in the artifact, in the comment and in the
  pager.

Animated WebP images compare frame by frame, with the time each frame shows.
An image whose file changed but whose pixels did not counts as unchanged; with
--restore, its committed file comes back, so that only real changes remain.

With --twice, the folders hold two renders of the same code, as in twice.yml: it fails
when an image differs between them, or when they hold no image at all.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageSequence

# The blueprint's screenshot tool, which keeps the pictures of the screenshot bot of
# every repository made from the blueprint, draws the comparison and the difference;
# its package is next to the settings tool in .github/, which the blueprint keeps
# current.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github"))
from blueprint.screenshots import drawing, most_changed, side_by_side

SUFFIXES = (".png", ".webp")


@dataclass
class Picture:
    """The frames of an image, each with the milliseconds it shows."""

    size: tuple[int, int]
    frames: list[tuple[Image.Image, int]]

    @classmethod
    def open(cls, path: Path) -> Picture:
        with Image.open(path) as image:
            frames = [
                (frame.convert("RGBA"), int(frame.info.get("duration", 0)))
                for frame in ImageSequence.Iterator(image)
            ]
            return cls(image.size, frames)


def changed_mask(before: Image.Image, after: Image.Image) -> Image.Image:
    """White where two frames of the same size differ in any channel, else black."""
    channels = ImageChops.difference(before, after).split()
    mask = channels[0]
    for channel in channels[1:]:
        mask = ImageChops.lighter(mask, channel)
    return mask.point(lambda value: 255 if value else 0)


def compare(before: Picture, after: Picture) -> float:
    """The share of pixels that changed."""
    if before.size != after.size:
        return 1.0
    area = after.size[0] * after.size[1]
    changed = 0
    for (old, old_duration), (new, duration) in zip(
        before.frames, after.frames, strict=False
    ):
        count = changed_mask(old, new).histogram()[255]
        # The same picture, shown for another time, counts as one changed pixel.
        changed += count or int(duration != old_duration)
    # Frames that one image has and the other has not changed as a whole.
    changed += abs(len(before.frames) - len(after.frames)) * area
    return changed / (area * max(len(before.frames), len(after.frames)))


def images(folder: Path, languages: list[str]) -> dict[str, Path]:
    """The images of the folder by their path below it, in these languages."""
    found = {}
    for language in languages:
        for path in sorted((folder / language).glob("*")):
            if path.suffix in SUFFIXES and path.is_file():
                found[f"{language}/{path.name}"] = path
    return found


def keep(source: Path, output: Path, name: str, kind: str) -> str:
    """Copy an image into the output folder; its name there."""
    stem, suffix = name.rsplit(".", 1)
    kept = f"{stem}.{kind}.{suffix}"
    target = output / kept
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return kept


def drawings(old: bytes, new: bytes, output: Path, name: str) -> dict:
    """The comparison and the difference of an image that changed, drawn into the
    output folder, of the pair of frames with the most changed pixels, as its entry
    of the report names them: with the number of that frame, from 1, and how many
    frames the image has, as the blueprint's screenshot tool counts them. Nothing for
    another size or other frames, or when only the time that a frame shows changed:
    the pixels of each frame alone tell nothing then."""
    # Pillow reads both images once for both pictures; an animation has many frames.
    most = most_changed(old, new)
    if most is None:
        return {}
    stem = name.rsplit(".", 1)[0]
    entry = {
        "comparison": f"{stem}.comparison.png",
        "frame": most.frame,
        "frames": most.frames,
        "difference": f"{stem}.difference.png",
    }
    (output / entry["comparison"]).write_bytes(side_by_side(most))
    (output / entry["difference"]).write_bytes(drawing(most))
    return entry


def change(entry: dict) -> str:
    """How an image changed, for a table: for an animation, also the frame that its
    comparison shows."""
    if entry.get("frames", 1) > 1:
        return f"{entry['status']}, most in frame {entry['frame']} of {entry['frames']}"
    return entry["status"]


def run(
    before_folder: Path,
    after_folder: Path,
    output: Path,
    languages: list[str],
    restore: bool = False,
) -> dict:
    before, after = images(before_folder, languages), images(after_folder, languages)
    report: dict = {"languages": languages, "images": [], "unchanged": 0}
    output.mkdir(parents=True, exist_ok=True)
    for name in sorted(before.keys() | after.keys()):
        entry: dict = {"path": name}
        if name not in after:
            entry |= {"status": "removed", "share": 1.0}
        elif name not in before:
            entry |= {"status": "added", "share": 1.0}
            entry["after"] = keep(after[name], output, name, "after")
        else:
            old, new = before[name].read_bytes(), after[name].read_bytes()
            if old == new:
                report["unchanged"] += 1
                continue
            share = compare(Picture.open(before[name]), Picture.open(after[name]))
            if share == 0:
                if restore:
                    shutil.copyfile(before[name], after[name])
                report["unchanged"] += 1
                continue
            entry |= {"status": "changed", "share": share}
            entry["before"] = keep(before[name], output, name, "before")
            entry["after"] = keep(after[name], output, name, "after")
            entry |= drawings(old, new, output, name)
        report["images"].append(entry)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "summary.md").write_text(summary(report))
    return report


def percent(share: float) -> str:
    if share >= 1:
        return "100 %"
    if share < 0.0001:
        return "< 0.01 %"
    return f"{share * 100:.2f} %"


def summary(report: dict) -> str:
    """The report as Markdown, for the summary of a workflow run."""
    languages = ", ".join(report["languages"])
    entries = report["images"]
    if not entries:
        return (
            f"### Visual check ({languages})\n\n"
            f"All {report['unchanged']} images look as committed.\n"
        )
    lines = [
        f"### Visual check ({languages})",
        "",
        f"{len(entries)} of {len(entries) + report['unchanged']} images look different "
        "from the committed ones:",
        "",
        "| Image | Change | Pixels changed |",
        "| --- | --- | ---: |",
    ]
    for entry in entries:
        lines.append(
            f"| `{entry['path']}` | {change(entry)} | {percent(entry['share'])} |"
        )
    lines.append("")
    return "\n".join(lines)


# What the summary of two renders that differ says: which images differ and what to do
# about them, more than the explanation of the check can know. On the page of the run,
# only an absolute link leads to the repository.
TWICE_FIX = """Something in these pictures depends on the moment: a button that takes its \
hover colour, a field that gets its focus, a text that comes late, a dialog that goes \
one step further, or a step before them that changed the demo. An image that changes \
without a reason brings a pull request of the screenshot bot after every change of \
the integration, and each of them restarts the checks of the others.

**To fix it,** look at the differences in the artifact of this run, find what they \
show and let the screenshot tool wait for that state, not for a fixed time; never let \
the comparison look away, which would hide real changes as well. `KEEP_RAW=1` keeps \
the images before compression, whose palettes make a small difference look large. \
See [the same images in every run](https://github.com/Dennis-Otto/\
homedarts-for-autodarts/blob/HEAD/docs/development.md#the-same-images-in-every-run), \
which also shows how to render them twice on your machine."""


def twice_summary(report: dict) -> str:
    """The report of two renders of the same code, as Markdown."""
    languages = ", ".join(report["languages"])
    entries = report["images"]
    if not entries and not report["unchanged"]:
        return (
            f"### Two renders of the same code ({languages})\n\n"
            "Neither render left an image in these languages, so the comparison proves "
            "nothing. The steps before it rendered nothing or wrote to another folder: "
            "look at the render steps and at `IMAGES` of this workflow.\n"
        )
    if not entries:
        return (
            f"### Two renders of the same code ({languages})\n\n"
            f"Both renders of all {report['unchanged']} images look the same.\n"
        )
    lines = [
        f"### Two renders of the same code ({languages})",
        "",
        f"{len(entries)} of {len(entries) + report['unchanged']} images came out "
        "differently, though nothing changed between the renders:",
        "",
        "| Image | Change | Pixels changed |",
        "| --- | --- | ---: |",
    ]
    for entry in entries:
        lines.append(
            f"| `{entry['path']}` | {change(entry)} | {percent(entry['share'])} |"
        )
    lines += ["", TWICE_FIX, ""]
    return "\n".join(lines)


def twice_annotation(report: dict) -> str | None:
    """The annotation of two renders that fail, which the bot-health bot quotes in its
    issue, or None when they look the same."""
    entries = report["images"]
    if entries:
        paths = ", ".join(entry["path"] for entry in entries)
        total = len(entries) + report["unchanged"]
        return (
            "::error title=Two renders differ::"
            f"{len(entries)} of {total} images came out differently: {paths}. "
            "See the summary of this run."
        )
    if report["unchanged"]:
        return None
    return (
        "::error title=No images to compare::"
        "Neither render left an image in these languages. Look at the render steps."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("before", type=Path, help="the committed images")
    parser.add_argument("after", type=Path, help="the images rendered anew")
    parser.add_argument("output", type=Path, help="where the report goes")
    parser.add_argument("--languages", default="en,de")
    parser.add_argument(
        "--restore",
        action="store_true",
        help="put back the committed file of an image whose pixels did not change",
    )
    parser.add_argument(
        "--twice",
        action="store_true",
        help="the folders hold two renders of the same code: fail when they differ",
    )
    arguments = parser.parse_args(argv)
    report = run(
        arguments.before,
        arguments.after,
        arguments.output,
        [language for language in arguments.languages.split(",") if language],
        arguments.restore,
    )
    if arguments.twice:
        text = twice_summary(report)
        (arguments.output / "summary.md").write_text(text)
        print(text)
        annotation = twice_annotation(report)
        if annotation is None:
            return 0
        print(annotation)
        return 1
    print(summary(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
