"""The highlight gallery of the media browser: photos by month, safe by design."""

# The name of a photo holds the wall clock of the house without a zone, so a Highlight
# is naive by design, and these tests compare with what it parsed.
# ruff: noqa: DTZ001

import io
import os
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.components import media_source
from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import MediaSourceItem, Unresolvable
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from PIL import Image

from custom_components.homedarts import media_source as highlights
from custom_components.homedarts.highlights import highlight_folder
from custom_components.homedarts.media_source import (
    Highlight,
    async_get_media_source,
    highlight,
)

from .local_helpers import board, setup_local

PHOTOS = [
    "2026-09-26_21-05-33_Alex_180.jpg",
    "2026-09-26_21-07-10_Alex Bee_checkout-121.JPG",
    "2026-09-02_18-00_140.png",
    "2026-08-31_Sam.webp",
    "2026-08-30.jpeg",
]


@pytest.fixture
def gallery(hass, tmp_path) -> Path:
    """A media folder with the highlight photos and some files that are none."""
    hass.config.media_dirs = {"other": str(tmp_path / "other"), "local": str(tmp_path)}
    folder = tmp_path / "homedarts" / "highlights"
    folder.mkdir(parents=True)
    for name in PHOTOS:
        (folder / name).write_bytes(b"photo")
    (folder / "notes.txt").write_text("no photo")
    (folder / ".hidden.jpg").write_bytes(b"photo")
    (folder / "a folder.jpg").mkdir()
    # A photo saved by other means is sorted by the time it was written.
    other = folder / "kitchen.jpg"
    other.write_bytes(b"photo")
    written = datetime(2026, 7, 4, 12, 0, tzinfo=dt_util.get_default_time_zone())
    os.utime(other, (written.timestamp(), written.timestamp()))
    (tmp_path / "secret.jpg").write_bytes(b"secret")
    # A link that leads nowhere is no photo either.
    # Creating links needs rights Windows does not always grant.
    with suppress(OSError):
        (folder / "broken.jpg").symlink_to(tmp_path / "gone.jpg")
    return folder


def item(hass, identifier: str = "") -> MediaSourceItem:
    return MediaSourceItem(hass, "homedarts", identifier, None)


def test_names_tell_the_moment_the_player_and_the_score(tmp_path):
    def parsed(name: str) -> Highlight | None:
        path = tmp_path / name
        path.write_bytes(b"photo")
        return highlight(path)

    assert parsed("2026-09-26_21-05-33_Alex_180.jpg") == Highlight(
        file="2026-09-26_21-05-33_Alex_180.jpg",
        taken=datetime(2026, 9, 26, 21, 5, 33),
        player="Alex",
        score=180,
    )
    checkout = parsed("2026-09-26_Anna_Lena_checkout-121.jpg")
    assert (checkout.player, checkout.score, checkout.checkout) == (
        "Anna Lena",
        121,
        True,
    )
    assert checkout.taken == datetime(2026, 9, 26)
    assert parsed("2026-09-26_21-05_100.png").taken == datetime(2026, 9, 26, 21, 5)
    alone = parsed("2026-09-26_21-05-33_60.webp")
    assert (alone.player, alone.score) == (None, 60)
    assert parsed("2026-09-26_Kim.jpg").score is None
    # The second photo of a second with the same name, as homedarts.save_highlight
    # names it, is a photo like the first.
    copy = parsed("2026-09-26_21-05-33_Alex_checkout-121 (2).jpg")
    assert (copy.player, copy.score, copy.checkout, copy.label) == (
        "Alex",
        121,
        True,
        None,
    )
    assert parsed("2026-09-26_21-05-33 (3).jpg").taken == datetime(
        2026, 9, 26, 21, 5, 33
    )
    # A date that does not exist, or no date at all, falls back to the file time.
    for name in ("2026-13-40_Alex_180.jpg", "180.jpg"):
        fallback = parsed(name)
        assert (fallback.player, fallback.score, fallback.label) == (
            None,
            None,
            name[:-4],
        )
    assert parsed("notes.txt") is None
    assert parsed(".2026-09-26_Alex_180.jpg") is None

    photo = Highlight("x.jpg", datetime(2026, 9, 6), "Alex", 180)
    assert photo.title("de") == "180 · Alex · 06.09."
    assert photo.title("en") == "180 · Alex · Sep 6"
    assert Highlight("x.jpg", datetime(2026, 1, 1), None, 121, True).title("en") == (
        "Checkout 121 · Jan 1"
    )
    assert Highlight("x.jpg", datetime(2026, 12, 24)).title("de") == "24.12."
    # Dutch, French and Spanish write the day first, too.
    assert photo.title("nl") == "180 · Alex · 06-09"
    assert photo.title("fr") == photo.title("es") == "180 · Alex · 06/09"
    # A checkout, as the players of the language call it.
    checkout = Highlight("x.jpg", datetime(2026, 1, 1), None, 121, True)
    assert [checkout.title(language) for language in ("de", "nl", "fr", "es")] == [
        "Checkout 121 · 01.01.",
        "Uitgooi 121 · 01-01",
        "Finish 121 · 01/01",
        "Cierre 121 · 01/01",
    ]


async def test_the_gallery_lists_the_months_and_their_photos(hass, gallery):
    source = await async_get_media_source(hass)
    assert source.name == "HomeDarts"
    root = await source.async_browse_media(item(hass))
    assert (root.title, root.media_class, root.can_expand, root.can_play) == (
        "HomeDarts",
        MediaClass.DIRECTORY,
        True,
        False,
    )
    # The newest month first, its newest photo as the cover.
    assert [(month.identifier, month.title) for month in root.children] == [
        ("2026-09", "September 2026"),
        ("2026-08", "August 2026"),
        ("2026-07", "July 2026"),
    ]
    # Thumbnails are small copies; the media browser embeds every one it shows.
    cover = "/api/homedarts/highlights/2026-09-26_21-07-10_Alex%20Bee_checkout-121.JPG"
    assert root.children[0].thumbnail == cover

    september = await source.async_browse_media(item(hass, "2026-09"))
    assert september.title == "September 2026"
    assert [
        (photo.identifier, photo.title, photo.media_content_type)
        for photo in september.children
    ] == [
        (
            "2026-09-26_21-07-10_Alex Bee_checkout-121.JPG",
            "Checkout 121 · Alex Bee · Sep 26",
            "image/jpeg",
        ),
        ("2026-09-26_21-05-33_Alex_180.jpg", "180 · Alex · Sep 26", "image/jpeg"),
        ("2026-09-02_18-00_140.png", "140 · Sep 2", "image/png"),
    ]
    photo = september.children[1]
    assert (photo.media_class, photo.can_play, photo.can_expand) == (
        MediaClass.IMAGE,
        True,
        False,
    )
    assert (
        photo.thumbnail == "/api/homedarts/highlights/2026-09-26_21-05-33_Alex_180.jpg"
    )
    july = await source.async_browse_media(item(hass, "2026-07"))
    assert [photo.title for photo in july.children] == ["kitchen · Jul 4"]

    hass.config.language = "de"
    august = await source.async_browse_media(item(hass, "2026-08"))
    assert august.title == "August 2026"
    assert [photo.title for photo in august.children] == ["Sam · 31.08.", "30.08."]
    assert (await source.async_browse_media(item(hass))).children[0].title == (
        "September 2026"
    )
    # Months in the other languages of the integration; a regional variant counts.
    for language, title, photo_title in (
        ("nl", "Augustus 2026", "Sam · 31-08"),
        ("fr", "Août 2026", "Sam · 31/08"),
        ("es-419", "Agosto de 2026", "Sam · 31/08"),
        ("it", "August 2026", "Sam · Aug 31"),
    ):
        hass.config.language = language
        august = await source.async_browse_media(item(hass, "2026-08"))
        assert (august.title, august.children[0].title) == (title, photo_title)
    with pytest.raises(BrowseError):
        await source.async_browse_media(item(hass, "../secret"))


async def test_only_photos_of_the_folder_resolve(hass, gallery):
    source = await async_get_media_source(hass)
    photo = await source.async_resolve_media(
        item(hass, "2026-09-26_21-05-33_Alex_180.jpg")
    )
    assert (
        photo.url
        == "/media/local/homedarts/highlights/2026-09-26_21-05-33_Alex_180.jpg"
    )
    assert photo.mime_type == "image/jpeg"
    assert photo.path == gallery / "2026-09-26_21-05-33_Alex_180.jpg"
    webp = await source.async_resolve_media(item(hass, "2026-08-31_Sam.webp"))
    assert webp.mime_type == "image/webp"

    link = gallery / "link.jpg"
    try:
        link.symlink_to(gallery.parents[1] / "secret.jpg")
    except OSError:
        link = None  # Creating links needs rights Windows does not always grant.
    for identifier in (
        "../../secret.jpg",
        "..",
        "homedarts/highlights/2026-08-30.jpeg",
        "2026-09",
        "notes.txt",
        ".hidden.jpg",
        "missing.jpg",
        "a folder.jpg",
        *(["link.jpg"] if link else []),
    ):
        with pytest.raises(Unresolvable):
            await source.async_resolve_media(item(hass, identifier))
    if link:
        listed = await source.async_browse_media(item(hass, "2026-09"))
        assert "link.jpg" not in [photo.identifier for photo in listed.children]


async def test_clips_play_beside_their_photos_with_the_same_thumbnail(hass, gallery):
    """The clip camera of the highlight photo records the moment beside its photo,
    and the gallery lists a clip right before its photo."""
    for name in (
        "2026-09-26_21-05-33_Alex_180.mp4",
        # A clip whose photo was not saved, alone in its month.
        "2026-10-03_20-00-00_Kim_140.MP4",
        # A second photo of one second, as from a second camera, and its clip.
        "2026-09-26_21-05-33_Alex_180 (2).png",
        "2026-09-26_21-05-33_Alex_180 (2).mp4",
        # Other videos are no clips of the blueprint.
        "2026-09-26_21-05-33_Alex_180.mkv",
    ):
        (gallery / name).write_bytes(b"clip")
    source = await async_get_media_source(hass)
    root = await source.async_browse_media(item(hass))
    # A month of clips without photos has no cover; the others show their newest photo.
    assert [(month.identifier, month.thumbnail) for month in root.children[:2]] == [
        ("2026-10", None),
        (
            "2026-09",
            "/api/homedarts/highlights/2026-09-26_21-07-10_Alex%20Bee_checkout-121.JPG",
        ),
    ]
    thumbnail = "/api/homedarts/highlights/2026-09-26_21-05-33_Alex_180"
    september = await source.async_browse_media(item(hass, "2026-09"))
    assert [
        (child.identifier, child.title, child.media_class, child.thumbnail)
        for child in september.children[1:5]
    ] == [
        (
            "2026-09-26_21-05-33_Alex_180.mp4",
            "Clip · 180 · Alex · Sep 26",
            MediaClass.VIDEO,
            f"{thumbnail}.jpg",
        ),
        (
            "2026-09-26_21-05-33_Alex_180.jpg",
            "180 · Alex · Sep 26",
            MediaClass.IMAGE,
            f"{thumbnail}.jpg",
        ),
        (
            "2026-09-26_21-05-33_Alex_180 (2).mp4",
            "Clip · 180 · Alex · Sep 26",
            MediaClass.VIDEO,
            f"{thumbnail}%20%282%29.png",
        ),
        (
            "2026-09-26_21-05-33_Alex_180 (2).png",
            "180 · Alex · Sep 26",
            MediaClass.IMAGE,
            f"{thumbnail}%20%282%29.png",
        ),
    ]
    assert september.children[1].media_content_type == "video/mp4"
    assert "2026-09-26_21-05-33_Alex_180.mkv" not in [
        child.identifier for child in september.children
    ]
    october = await source.async_browse_media(item(hass, "2026-10"))
    assert [(child.title, child.thumbnail) for child in october.children] == [
        ("Clip · 140 · Kim · Oct 3", None)
    ]
    for language, title in (
        ("fr", "Vidéo · 140 · Kim · 03/10"),
        ("de", "Clip · 140 · Kim · 03.10."),
    ):
        hass.config.language = language
        october = await source.async_browse_media(item(hass, "2026-10"))
        assert october.children[0].title == title

    # The gallery plays a clip in the browser.
    clip = await source.async_resolve_media(
        item(hass, "2026-09-26_21-05-33_Alex_180.mp4")
    )
    assert (
        clip.url == "/media/local/homedarts/highlights/2026-09-26_21-05-33_Alex_180.mp4"
    )
    assert clip.mime_type == "video/mp4"
    with pytest.raises(Unresolvable):
        await source.async_resolve_media(item(hass, "2026-09-26_21-05-33_Alex_180.mkv"))


async def test_without_a_folder_the_gallery_is_empty(hass, tmp_path):
    source = await async_get_media_source(hass)
    hass.config.media_dirs = {"media": str(tmp_path)}
    assert highlight_folder(hass) == ("media", tmp_path / "homedarts" / "highlights")
    assert (await source.async_browse_media(item(hass))).children == []
    hass.config.media_dirs = {}
    assert highlight_folder(hass) is None
    assert (await source.async_browse_media(item(hass))).children == []
    with pytest.raises(Unresolvable):
        await source.async_resolve_media(item(hass, "2026-09-26_Alex_180.jpg"))


async def test_the_media_browser_finds_the_gallery_of_the_integration(
    hass, aioclient_mock, gallery
):
    await setup_local(hass, aioclient_mock, state=board())
    assert await async_setup_component(hass, "media_source", {})
    root = await media_source.async_browse_media(hass, "media-source://")
    assert "HomeDarts" in [child.title for child in root.children]
    months = await media_source.async_browse_media(hass, "media-source://homedarts")
    assert months.children[0].title == "September 2026"
    resolved = await media_source.async_resolve_media(
        hass, "media-source://homedarts/2026-08-30.jpeg", None
    )
    assert resolved.url == "/media/local/homedarts/highlights/2026-08-30.jpeg"


def picture(path: Path, size: tuple[int, int], orientation: int | None = None) -> None:
    """A real photo; with an EXIF orientation, as a camera held sideways writes it."""
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    Image.new("RGB", size, "red").save(path, exif=exif)


async def test_thumbnails_are_small_copies_for_logged_in_users(
    hass, gallery, hass_client, hass_client_no_auth
):
    assert await async_setup_component(hass, "http", {})
    # The view is added once, however often the media browser asks.
    await async_get_media_source(hass)
    source = await async_get_media_source(hass)
    picture(gallery / "2026-09-27_Alex_180.jpg", (1600, 1200))
    picture(gallery / "2026-09-27_Kim_140.png", (200, 100), orientation=6)
    root = await source.async_browse_media(item(hass))
    client = await hass_client()
    alex = "/api/homedarts/highlights/2026-09-27_Alex_180.jpg"
    kim = "/api/homedarts/highlights/2026-09-27_Kim_140.png"

    response = await client.get(alex)
    assert response.status == 200
    assert response.content_type == "image/jpeg"
    assert "private" in response.headers["Cache-Control"]
    with Image.open(io.BytesIO(await response.read())) as small:
        assert small.size == (320, 240)
    # A photo taken sideways is shown upright, and never larger than it is.
    response = await client.get(kim)
    with Image.open(io.BytesIO(await response.read())) as small:
        assert small.size == (100, 200)

    # A thumbnail is made once, and again when the photo changes.
    with patch.object(highlights, "thumbnail", wraps=highlights.thumbnail) as made:
        for _ in range(2):
            await client.get(alex)
        assert made.call_count == 0
        picture(gallery / "2026-09-27_Alex_180.jpg", (800, 800))
        response = await client.get(alex)
        assert made.call_count == 1
    with Image.open(io.BytesIO(await response.read())) as small:
        assert small.size == (320, 320)
    # Only the most recently used thumbnails are kept.
    picture(gallery / "2026-09-27_Sam_100.jpg", (400, 300))
    with (
        patch.object(highlights, "KEPT_THUMBNAILS", 1),
        patch.object(highlights, "thumbnail", wraps=highlights.thumbnail) as made,
    ):
        await client.get("/api/homedarts/highlights/2026-09-27_Sam_100.jpg")
        await client.get(kim)
        await client.get(kim)
        assert made.call_count == 2
    # A huge picture is no snapshot of the board and gets no thumbnail.
    picture(gallery / "2026-09-27_Lea_60.jpg", (40, 40))
    with patch.object(highlights, "MAX_PIXELS", 1000):
        response = await client.get("/api/homedarts/highlights/2026-09-27_Lea_60.jpg")
    assert response.status == 404

    for name in (
        "notes.txt",
        ".hidden.jpg",
        "missing.jpg",
        "a folder.jpg",
        # Not a picture, although it is named like one.
        "2026-08-30.jpeg",
    ):
        response = await client.get(f"/api/homedarts/highlights/{name}")
        assert response.status == 404, name
    # Home Assistant refuses a way out of the folder before the integration does.
    response = await client.get("/api/homedarts/highlights/..%2F..%2Fsecret.jpg")
    assert response.status in (400, 404)
    anonymous = await hass_client_no_auth()
    response = await anonymous.get(root.children[0].thumbnail)
    assert response.status == 401
    hass.config.media_dirs = {}
    response = await client.get(root.children[0].thumbnail)
    assert response.status == 404


def test_a_photo_that_disappears_while_it_is_read_has_no_thumbnail(gallery):
    with patch.object(highlights, "_inside", side_effect=FileNotFoundError):
        assert highlights._version(gallery, "2026-08-30.jpeg") is None
