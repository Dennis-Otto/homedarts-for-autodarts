"""Turn the animations of the documentation into MP4 and GIF files for creators.

Reddit, Discord, forums and video editors do not all show animated WebP. This
script reads the animations from `docs/images/<language>/`, splits them into
frames with Pillow and writes `docs/media/<name>-<language>.mp4` and `.gif` with
ffmpeg. Run it after `tests/e2e/screenshots.sh`, which renders the animations;
it needs Pillow and ffmpeg. The tests read the length of each video with
`mp4_duration`, without ffmpeg, so they check the videos on every machine.
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

from PIL import Image, ImageSequence

ROOT = Path(__file__).parents[1]
IMAGES = ROOT / "docs" / "images"
MEDIA = ROOT / "docs" / "media"
ANIMATIONS = (
    "hero",
    "setup",
    "scoreboard",
    "celebration",
    "wild-mouse",
    "bot-match",
    "lobby",
    "tournament-bracket",
)
LANGUAGES = ("en", "de")
FPS = 30
BACKGROUND = (255, 255, 255)
# H.264 in yuv420p needs even dimensions.
MP4_FILTER = "pad=ceil(iw/2)*2:ceil(ih/2)*2:color=white,format=yuv420p"
# The GIF is made from the video, with one palette for the whole animation.
GIF_FILTER = (
    "fps=15,split[frames][copy];[copy]palettegen=stats_mode=diff[palette];"
    "[frames][palette]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
)


def frames(path: Path) -> Iterator[tuple[Image.Image, int]]:
    """Every frame of an animation on a white background, with its duration in ms."""
    with Image.open(path) as animation:
        for frame in ImageSequence.Iterator(animation):
            # The WebP plugin sets the duration of a frame only once it is loaded.
            frame.load()
            duration = int(frame.info.get("duration") or 100)
            rgba = frame.convert("RGBA")
            flat = Image.new("RGB", rgba.size, BACKGROUND)
            flat.paste(rgba, mask=rgba.getchannel("A"))
            yield flat, duration


def schedule(durations: list[int], fps: int = FPS) -> list[int]:
    """How many video frames each animation frame lasts.

    Each frame ends on the video frame nearest to its end in the animation, so
    rounding never adds up and the video is exactly as long as the animation.
    A frame shorter than one video frame may get none.
    """
    counts, elapsed, shown = [], 0, 0
    for duration in durations:
        elapsed += duration
        end = round(elapsed * fps / 1000)
        counts.append(end - shown)
        shown = end
    return counts


def _box(data: bytes, kind: bytes) -> bytes:
    """The content of the first box of a kind among the MP4 boxes of data.

    A box starts with its size in 32 bits and its type; the size 1 puts the real
    size in the 64 bits after the type, and the size 0 lets the box reach to the
    end, as the last box of a file may.
    """
    offset = 0
    while offset + 8 <= len(data):
        size, found = struct.unpack_from(">I4s", data, offset)
        start = offset + 8
        if size == 1 and start + 8 <= len(data):
            (size,) = struct.unpack_from(">Q", data, start)
            start += 8
        elif size == 0:
            size = len(data) - offset
        if size < start - offset:
            # Shorter than its own size and type: the file is broken here.
            break
        if found == kind:
            return data[start : offset + size]
        offset += size
    raise ValueError(f"not an MP4 video: no {kind.decode()} box")


def mp4_duration(path: Path) -> float:
    """Seconds of an MP4 video, as the header of its movie, the box mvhd, says.

    The header of version 0 has the times in 32 bits, that of version 1 in 64:
    after the version and the flags come the times of creation and of the last
    change, then the timescale, the units of a second, and the duration in them.
    """
    header = _box(_box(path.read_bytes(), b"moov"), b"mvhd")
    layout, offset = (">IQ", 20) if header[:1] == bytes([1]) else (">II", 12)
    if len(header) < offset + struct.calcsize(layout):
        raise ValueError("not an MP4 video: the movie header is too short")
    timescale, duration = struct.unpack_from(layout, header, offset)
    if not timescale:
        raise ValueError("not an MP4 video: the movie header has no timescale")
    return duration / timescale


def convert(source: Path, stem: Path) -> None:
    animation = list(frames(source))
    counts = schedule([duration for _, duration in animation])
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        index = 0
        for (image, _), count in zip(animation, counts, strict=True):
            if not count:
                continue
            first = work / f"frame-{index:05d}.png"
            image.save(first)
            for repeat in range(1, count):
                os.link(first, work / f"frame-{index + repeat:05d}.png")
            index += count
        video = stem.with_suffix(".mp4")
        ffmpeg = ["ffmpeg", "-loglevel", "error", "-y"]
        subprocess.run(
            [*ffmpeg, "-framerate", str(FPS), "-i", str(work / "frame-%05d.png"),
             "-vf", MP4_FILTER, "-c:v", "libx264", "-preset", "slow", "-crf", "20",
             "-movflags", "+faststart", "-an", str(video)],
            check=True,
        )  # fmt: skip
        subprocess.run(
            [*ffmpeg, "-i", str(video), "-vf", GIF_FILTER, "-loop", "0",
             str(stem.with_suffix(".gif"))],
            check=True,
        )  # fmt: skip


def main() -> int:
    MEDIA.mkdir(exist_ok=True)
    for language in LANGUAGES:
        for name in ANIMATIONS:
            convert(IMAGES / language / f"{name}.webp", MEDIA / f"{name}-{language}")
            print(f"{name}-{language}: mp4 and gif")
    return 0


if __name__ == "__main__":
    sys.exit(main())
