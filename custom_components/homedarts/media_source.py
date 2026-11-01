"""Highlight photos and clips of the board in the media browser of Home Assistant.

The highlight photo blueprint saves its pictures with homedarts.save_highlight
in the folder homedarts/highlights of the media directory, for example
/media/homedarts/highlights/2026-09-26_21-05-33_Alex_180.jpg, and with a clip
camera it records the moment as a clip of the same name with .mp4 beside it.
The media browser lists them by month, newest first, with titles like
"180 · Alex · 26.09." or "Clip · 180 · Alex · 26.09.". Only plain file names of
that folder resolve, so no identifier can reach anything outside it.

The media browser embeds every thumbnail it shows, so the thumbnails are small
copies of the photos, made once and kept while Home Assistant runs. A clip
shows the thumbnail of its photo.
"""

from __future__ import annotations

import io
import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util import raise_if_invalid_filename
from homeassistant.util.hass_dict import HassKey
from PIL import Image, ImageOps

from .const import DOMAIN
from .highlights import HIGHLIGHTS, highlight_folder

THUMBNAIL_URL = "/api/homedarts/highlights/{name}"
# The longer side of a thumbnail, in pixels; the media browser shows them
# smaller than this.
THUMBNAIL_SIZE = 320
KEPT_THUMBNAILS = 200
# Larger pictures are no snapshots of a board camera and get no thumbnail.
MAX_PIXELS = 40_000_000
THUMBNAIL_VIEW: HassKey[HighlightThumbnailView] = HassKey(f"{DOMAIN}_thumbnails")
PHOTO_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
# The clips that camera.record writes, which the browser plays as they are.
CLIP_TYPES = {".mp4": "video/mp4"}
MEDIA_TYPES = PHOTO_TYPES | CLIP_TYPES
# 2026-09-26_21-05-33_Alex_180 or 2026-09-26_Alex_checkout-121: the day, then
# optionally the time, the player and the score, and " (2)" for the second
# photo of one second with the same name.
PHOTO_NAME = re.compile(
    r"^(?P<day>\d{4}-\d{2}-\d{2})"
    r"(?:_(?P<time>\d{2}-\d{2}(?:-\d{2})?))?"
    r"(?:_(?P<player>.+?))??"
    r"(?:_(?P<checkout>checkout-)?(?P<score>\d{1,3}))?"
    r"(?: \(\d+\))?$"
)
MONTH = re.compile(r"^\d{4}-\d{2}$")
MONTHS = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "de": [
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ],
    "es": [
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    ],
    "fr": [
        "Janvier",
        "Février",
        "Mars",
        "Avril",
        "Mai",
        "Juin",
        "Juillet",
        "Août",
        "Septembre",
        "Octobre",
        "Novembre",
        "Décembre",
    ],
    "nl": [
        "Januari",
        "Februari",
        "Maart",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Augustus",
        "September",
        "Oktober",
        "November",
        "December",
    ],
}
# "September 2026", in Spanish "Septiembre de 2026".
MONTH_TITLES = {"es": "{month} de {year}"}
SHORT_MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
# Day and month as the language writes them: 26.09., 26/09 or 26-09.
SHORT_DATES = {
    "de": "{day:02d}.{month:02d}.",
    "es": "{day:02d}/{month:02d}",
    "fr": "{day:02d}/{month:02d}",
    "nl": "{day:02d}-{month:02d}",
}
# A checkout as the darts players of the language call it.
CHECKOUTS = {"es": "Cierre", "fr": "Finish", "nl": "Uitgooi"}
# A clip, in front of its title.
CLIPS = {"es": "Vídeo", "fr": "Vidéo"}


@dataclass(frozen=True)
class Highlight:
    """One photo and what its name tells about it."""

    file: str
    taken: datetime
    player: str | None = None
    score: int | None = None
    checkout: bool = False
    # The name of a photo that does not follow the convention.
    label: str | None = None

    @property
    def month(self) -> str:
        return self.taken.strftime("%Y-%m")

    @property
    def clip(self) -> bool:
        return Path(self.file).suffix.lower() in CLIP_TYPES

    @property
    def media_type(self) -> str:
        return MEDIA_TYPES[Path(self.file).suffix.lower()]

    def title(self, language: str) -> str:
        """180 · Alex · 26.09., Checkout 121 · Sep 26 or Clip · 180 · Sep 26."""
        parts = [CLIPS.get(language, "Clip")] if self.clip else []
        if self.label:
            parts.append(self.label)
        if self.score is not None and self.checkout:
            parts.append(f"{CHECKOUTS.get(language, 'Checkout')} {self.score}")
        elif self.score is not None:
            parts.append(str(self.score))
        if self.player:
            parts.append(self.player)
        parts.append(_short_date(self.taken.date(), language))
        return " · ".join(parts)


def _language(hass: HomeAssistant) -> str:
    """The language of Home Assistant, such as "es" for "es-419"; others read English."""
    language = str(hass.config.language).split("-")[0].lower()
    return language if language in MONTHS else "en"


def _short_date(day: date, language: str) -> str:
    if language in SHORT_DATES:
        return SHORT_DATES[language].format(day=day.day, month=day.month)
    return f"{SHORT_MONTHS[day.month - 1]} {day.day}"


def _month_title(month: str, language: str) -> str:
    year, number = month.split("-")
    name = MONTHS[language][int(number) - 1]
    return MONTH_TITLES.get(language, "{month} {year}").format(month=name, year=year)


def _inside(folder: Path, path: Path) -> bool:
    """A file of the folder itself; a link out of it does not count."""
    return path.is_file() and path.resolve().parent == folder.resolve()


def highlight(path: Path) -> Highlight | None:
    """What a file of the folder shows, or None when it is no photo or clip."""
    if path.name.startswith(".") or path.suffix.lower() not in MEDIA_TYPES:
        return None
    match = PHOTO_NAME.match(path.stem)
    if match:
        clock = [*(match["time"] or "00-00-00").split("-"), "00"]
        try:
            taken = datetime.fromisoformat(
                f"{match['day']}T{clock[0]}:{clock[1]}:{clock[2]}"
            )
        except ValueError:
            match = None
    if match is None:
        # Files saved by other means are sorted by the time they were written.
        written = dt_util.as_local(dt_util.utc_from_timestamp(path.stat().st_mtime))
        return Highlight(
            file=path.name, taken=written.replace(tzinfo=None), label=path.stem
        )
    return Highlight(
        file=path.name,
        taken=taken,
        player=match["player"].replace("_", " ").strip() or None
        if match["player"]
        else None,
        score=int(match["score"]) if match["score"] else None,
        checkout=bool(match["checkout"]),
    )


def _media_name(name: str, types: dict[str, str] = MEDIA_TYPES) -> bool:
    """A plain, visible file name of a photo or a clip, nothing that leads
    elsewhere."""
    try:
        raise_if_invalid_filename(name)
    except ValueError:
        return False
    return not name.startswith(".") and Path(name).suffix.lower() in types


def _version(folder: Path, name: str) -> tuple[str, int, int] | None:
    """The photo's name, change time and size, or None when it is no photo of
    the folder; a new photo under the same name gets a new thumbnail."""
    path = folder / name
    try:
        if not _inside(folder, path):
            return None
        stat = path.stat()
    except OSError:
        # Removed or replaced while it was looked at.
        return None
    return name, stat.st_mtime_ns, stat.st_size


def thumbnail(path: Path) -> bytes | None:
    """A small JPEG of the photo, upright as it was taken; None if it is none."""
    try:
        with Image.open(path) as photo:
            if photo.width * photo.height > MAX_PIXELS:
                return None
            # JPEG photos decode at a fraction of their size, which is faster.
            photo.draft("RGB", (THUMBNAIL_SIZE, THUMBNAIL_SIZE))
            small = ImageOps.exif_transpose(photo)
            small.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
            output = io.BytesIO()
            small.convert("RGB").save(output, "JPEG", quality=80)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    return output.getvalue()


class HighlightThumbnailView(HomeAssistantView):
    """Thumbnails of the highlight photos, for logged-in users as the photos."""

    url = THUMBNAIL_URL
    name = "api:homedarts:highlights"

    def __init__(self) -> None:
        # (name, change time, size) -> thumbnail, the most recently used last.
        self.cache: OrderedDict[tuple[str, int, int], bytes] = OrderedDict()

    async def get(self, request: web.Request, name: str) -> web.StreamResponse:
        hass = request.app[KEY_HASS]
        found = highlight_folder(hass)
        if found is None or not _media_name(name, PHOTO_TYPES):
            return self.json_message("Highlight not found", 404)
        folder = found[1]
        key = await hass.async_add_executor_job(_version, folder, name)
        if key is None:
            return self.json_message("Highlight not found", 404)
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            body = await hass.async_add_executor_job(thumbnail, folder / name)
            if body is None:
                return self.json_message("Highlight not readable", 404)
            self.cache[key] = body
            while len(self.cache) > KEPT_THUMBNAILS:
                self.cache.popitem(last=False)
        return web.Response(
            body=self.cache[key],
            content_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )


async def async_get_media_source(hass: HomeAssistant) -> HighlightSource:
    if THUMBNAIL_VIEW not in hass.data and hass.http is not None:
        hass.data[THUMBNAIL_VIEW] = HighlightThumbnailView()
        hass.http.register_view(hass.data[THUMBNAIL_VIEW])
    return HighlightSource(hass)


class HighlightSource(MediaSource):
    """The highlight photos of the board, by month."""

    name: str = "HomeDarts"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass

    def _scan(self) -> list[Highlight]:
        """Every photo and clip of the folder, newest first."""
        found = highlight_folder(self.hass)
        if found is None or not found[1].is_dir():
            return []
        folder = found[1]
        photos = [
            photo
            for path in folder.iterdir()
            if _inside(folder, path) and (photo := highlight(path)) is not None
        ]
        # A clip comes right before its photo, whatever the kind of the picture;
        # the dot of the suffix keeps a photo before its copies, such as " (2)".
        return sorted(
            photos,
            key=lambda photo: (photo.taken, Path(photo.file).stem + ".", photo.clip),
            reverse=True,
        )

    def _url(self, source: str, file: str) -> str:
        """The address of Home Assistant's media view for a photo or a clip."""
        return quote(f"/media/{source}/{HIGHLIGHTS.as_posix()}/{file}")

    @staticmethod
    def _thumbnails(photos: list[Highlight]) -> dict[str, str]:
        """The thumbnail of every photo, and of every clip with a photo of the
        same name, which the highlight photo blueprint saves beside it."""
        posters = {
            Path(photo.file).stem: photo.file for photo in photos if not photo.clip
        }
        thumbnails = {}
        for photo in photos:
            poster = posters.get(Path(photo.file).stem) if photo.clip else photo.file
            if poster is not None:
                thumbnails[photo.file] = THUMBNAIL_URL.format(
                    name=quote(poster, safe="")
                )
        return thumbnails

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        photos = await self.hass.async_add_executor_job(self._scan)
        language = _language(self.hass)
        thumbnails = self._thumbnails(photos)
        if not item.identifier:
            covers: dict[str, str | None] = {}
            for photo in photos:
                # The newest picture of a month is its cover.
                covers[photo.month] = covers.get(photo.month) or thumbnails.get(
                    photo.file
                )
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=None,
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                title=self.name,
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.DIRECTORY,
                children=[
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=month,
                        media_class=MediaClass.DIRECTORY,
                        media_content_type="",
                        title=_month_title(month, language),
                        thumbnail=cover,
                        can_play=False,
                        can_expand=True,
                        children_media_class=MediaClass.IMAGE,
                    )
                    for month, cover in covers.items()
                ],
            )
        if not MONTH.match(item.identifier):
            raise BrowseError(f"Unknown highlight month: {item.identifier}")
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=item.identifier,
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=_month_title(item.identifier, language),
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.IMAGE,
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=photo.file,
                    media_class=MediaClass.VIDEO if photo.clip else MediaClass.IMAGE,
                    media_content_type=photo.media_type,
                    title=photo.title(language),
                    thumbnail=thumbnails.get(photo.file),
                    can_play=True,
                    can_expand=False,
                )
                for photo in photos
                if photo.month == item.identifier
            ],
        )

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """A photo or a clip by its plain file name; nothing outside the folder
        resolves."""
        name = item.identifier
        found = highlight_folder(self.hass)
        if found is None or not _media_name(name):
            raise Unresolvable(f"Invalid highlight: {name}")
        source, folder = found
        path = folder / name
        if not await self.hass.async_add_executor_job(_inside, folder, path):
            raise Unresolvable(f"Unknown highlight: {name}")
        suffix = Path(name).suffix.lower()
        return PlayMedia(self._url(source, name), MEDIA_TYPES[suffix], path=path)
