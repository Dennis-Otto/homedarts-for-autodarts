"""Highlight photos: the picture of a camera, saved for the highlight gallery.

homedarts.save_highlight saves what a camera sees as a file named by the
moment, the player and what the photo shows, by default in the folder
homedarts/highlights of the media folder, which the media browser shows under
Autodarts. It answers with the file and its address only once the file is
written: a camera that is disabled, unavailable or gives no picture, and a
folder Home Assistant does not allow writing to, fail the action. camera.snapshot
passes over a disabled or unavailable camera and a missing picture without an
error, so whoever relied on it announced photos that were never saved.

Home Assistant serves the folder www at /local/ without a login. A photo there
gets a random part at the end of its name, as an export does, so that its name
does not follow from the moment, the player and the score, and its /local/
address; the names in the gallery stay as they are, since the gallery reads them.

With a clip camera, a camera with a video stream, it also records the moment as a
clip beside the photo, under its name with .mp4, where the gallery plays it.
camera.record returns only when the recording has ended, so the clip records in
the background: the actions that send the photo do not wait for it, and a new
run of the highlight photo blueprint, whose mode is restart, does not cut it short.

The gallery has a bound, as the exports and the backups have: after a photo was
saved in it, the newest highlights stay, 1000 by default or as many as `keep` says,
and older ones are deleted, a photo with its clip. Only files with a name that
photo_stem writes go, never a file of the user's own, and never a folder the user
chose. Beyond 120 photos in an hour the action refuses, so that an automation that
loops cannot fill the disk.
"""

from __future__ import annotations

import logging
import re
import secrets
from collections import deque
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from homeassistant.components.camera import async_get_image
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.core_config import Config
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .export import ExportFolderError, export_folder, public_url
from .profiles import NAME_LENGTH

if TYPE_CHECKING:
    # Home Assistant 2026.10 validates with probatio and makes "voluptuous" an alias
    # of it, so the types are probatio's; older versions still use voluptuous.
    import probatio as vol
else:
    import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

# The folder of the highlight photos inside the media directory.
HIGHLIGHTS = Path("homedarts", "highlights")
# What a photo shows at the end of its name, such as 180 or checkout-121.
LABEL_LENGTH = 24
# Characters that file names and addresses do not allow, the separator _, the
# characters of a template, and ~ and .., for which Home Assistant serves no
# file of a media folder, leave the player and the label.
UNSAFE = re.compile(r'[\\/:*?"<>|_{}%#~]|\.{2,}')
# Photos of one second with one name get " (2)", " (3)" and so on, up to this.
COPIES = 100
# The pictures of most cameras are JPEG, which is also the suffix for any other kind.
SUFFIXES = {"image/png": ".png", "image/webp": ".webp"}
# The random bytes at the end of the name of a photo in www, as many as an export has.
RANDOM_BYTES = 8
# The newest highlights that the gallery keeps, each a photo with its clip, unless
# the action says otherwise; 0 keeps every one. Enough for years of play.
KEPT_HIGHLIGHTS = 1000
MAX_KEPT = 100_000
# No more photos than this in an hour, so that a looping automation cannot fill the
# disk; an evening of play with the highlight photo blueprint saves far fewer.
HIGHLIGHT_LIMIT = 120
HIGHLIGHT_WINDOW = 3600.0
HIGHLIGHT_TIMES: HassKey[deque[float]] = HassKey(f"{DOMAIN}_highlight_times")
# The files that photo_stem and _write make in the gallery, a photo or its clip,
# with " (2)" of a copy: the only files that pruning deletes. The player and the
# label have no _, which UNSAFE takes out.
SAVED = re.compile(
    r"(?P<stem>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:_[^_]+){0,2})"
    r"\.(?:jpg|png|webp|mp4)"
)


def media_folder(hass: HomeAssistant, folder: Path) -> tuple[str, Path] | None:
    """The media directory to serve from, and a folder in it."""
    media = hass.config.media_dirs
    if not media:
        return None
    source = "local" if "local" in media else next(iter(media))
    return source, Path(media[source]) / folder


def highlight_folder(hass: HomeAssistant) -> tuple[str, Path] | None:
    """The media directory to serve from, and the folder of the photos in it."""
    return media_folder(hass, HIGHLIGHTS)


def name_part(text: str, limit: int) -> str:
    """A player or a label as a part of a file name: without the characters
    above or control characters, with single spaces, at most limit long, and
    without a dot at the end, which would make .. with the suffix."""
    printable = "".join(char if char.isprintable() else " " for char in text)
    return " ".join(UNSAFE.sub(" ", printable).split())[:limit].rstrip(". ")


def photo_stem(taken: datetime, player: str, label: str) -> str:
    """2026-09-26_21-05-33_Alex_180, the name the gallery reads."""
    parts = (name_part(player, NAME_LENGTH), name_part(label, LABEL_LENGTH))
    return "_".join([taken.strftime("%Y-%m-%d_%H-%M-%S"), *filter(None, parts)])


def media_url(config: Config, path: Path) -> str:
    """The address of a file of a media folder, from which the media browser and
    the Home Assistant app load it, or "" outside them; runs in the executor."""
    for source, folder in config.media_dirs.items():
        root = Path(folder).resolve()
        if path.is_relative_to(root):
            return quote(f"/media/{source}/{path.relative_to(root).as_posix()}")
    return ""


def _write(
    config: Config, folder: str, stem: str, suffix: str, image: bytes
) -> tuple[Path, str]:
    """Write the photo under a name no file has yet, and find its address in
    the media browser or, in www, at /local/; runs in the executor."""
    # The rules of the exports: not hidden, and where Home Assistant allows writing.
    target = export_folder(config, folder)
    target.mkdir(parents=True, exist_ok=True)
    if public_url(config.config_dir, target) is not None:
        # www needs no login: a name that follows from the moment, the player and
        # the score would let anyone who reaches Home Assistant find the photo.
        stem = f"{stem}-{secrets.token_hex(RANDOM_BYTES)}"
    for copy in range(1, COPIES + 1):
        path = target / (f"{stem} ({copy}){suffix}" if copy > 1 else stem + suffix)
        try:
            with path.open("xb") as file:
                file.write(image)
        except FileExistsError:
            continue
        except OSError:
            # Part of a photo is no photo, and the gallery would show it broken.
            path.unlink(missing_ok=True)
            raise
        url = media_url(config, path) or public_url(config.config_dir, path)
        return path, url or ""
    raise FileExistsError(f"{COPIES} photos named {stem}{suffix} exist already")


def _prune(photo: Path, keep: int) -> list[Path]:
    """Delete the highlights of the photo's folder beyond the newest keep, the
    photo counted among them and never deleted, each with its clip; runs in the
    executor and returns the files it deleted."""
    highlights: dict[str, list[Path]] = {}
    for path in photo.parent.iterdir():
        if (saved := SAVED.fullmatch(path.name)) and path.is_file():
            highlights.setdefault(saved["stem"], []).append(path)
    # The moment leads every name, so the names sort by it, a copy after its photo.
    older = sorted(highlights.keys() - {photo.stem}, reverse=True)[keep - 1 :]
    deleted = []
    for stem in older:
        for path in highlights[stem]:
            path.unlink(missing_ok=True)
            deleted.append(path)
    return deleted


def _recent_highlights(hass: HomeAssistant) -> deque[float]:
    """When the photos of the last hour were saved; refuses one too many."""
    times = hass.data.setdefault(HIGHLIGHT_TIMES, deque())
    now = monotonic()
    while times and now - times[0] >= HIGHLIGHT_WINDOW:
        times.popleft()
    if len(times) >= HIGHLIGHT_LIMIT:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="highlight_limit",
            translation_placeholders={"count": str(HIGHLIGHT_LIMIT)},
        )
    return times


def _shown(folder: str) -> str:
    """The folder for a message, with control characters as ?."""
    return "".join(char if char.isprintable() else "?" for char in folder)


async def _record_clip(
    hass: HomeAssistant, camera: str, clip: Path, lookback: int, duration: int
) -> None:
    """Record the clip with camera.record, which writes the file when the
    recording ends; a camera without a stream, or one that records already,
    leaves the photo without a clip and says why in the log."""
    try:
        await hass.services.async_call(
            "camera",
            "record",
            {
                "entity_id": camera,
                "filename": str(clip),
                "lookback": lookback,
                "duration": duration,
            },
            blocking=True,
        )
    except (HomeAssistantError, vol.Invalid) as err:
        _LOGGER.warning("No clip %s from %s: %s", clip.name, camera, err)


async def async_save_highlight(
    hass: HomeAssistant,
    camera: str,
    folder: str | None = None,
    player: str = "",
    label: str = "",
    clip_camera: str = "",
    clip_lookback: int = 5,
    clip_duration: int = 8,
    keep: int = KEPT_HIGHLIGHTS,
) -> dict[str, Any]:
    """Save the camera's picture as a highlight photo, by default in the gallery,
    and return the file and its address; fails when nothing was saved. With a
    clip camera, start the clip beside it and return its file and address too.
    In the gallery, keep the newest highlights and delete older ones."""
    saved_times = _recent_highlights(hass)
    state = hass.states.get(camera)
    if state is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="highlight_camera_missing",
            translation_placeholders={"camera": camera},
        )
    if state.state == STATE_UNAVAILABLE:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="highlight_camera_unavailable",
            translation_placeholders={"camera": camera},
        )
    try:
        image = await async_get_image(hass, camera)
    except HomeAssistantError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="highlight_no_picture",
            translation_placeholders={"camera": camera},
        ) from err
    # Only the gallery is pruned, never a folder the user chose.
    in_gallery = not folder
    if not folder:
        # Without a media folder, Home Assistant allows writing nowhere near it.
        gallery = highlight_folder(hass)
        folder = str(gallery[1]) if gallery else HIGHLIGHTS.as_posix()
    kind = image.content_type.partition(";")[0].strip().lower()
    try:
        path, url = await hass.async_add_executor_job(
            _write,
            hass.config,
            folder,
            photo_stem(dt_util.now(), player, label),
            SUFFIXES.get(kind, ".jpg"),
            image.content,
        )
    except ExportFolderError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="highlight_folder",
            translation_placeholders={"folder": _shown(folder)},
        ) from err
    except OSError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="highlight_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    saved_times.append(monotonic())
    if in_gallery and keep:
        try:
            await hass.async_add_executor_job(_prune, path, keep)
        except OSError as err:
            # The photo is saved; the next one prunes again.
            _LOGGER.warning("Older highlights not deleted: %s", err)
    saved = {"photo": str(path), "photo_url": url}
    if clip_camera:
        clip = path.with_suffix(".mp4")
        saved["clip"] = str(clip)
        saved["clip_url"] = url.removesuffix(path.suffix) + ".mp4" if url else ""
        hass.async_create_background_task(
            _record_clip(hass, clip_camera, clip, clip_lookback, clip_duration),
            f"homedarts clip {clip.name}",
        )
    return saved
