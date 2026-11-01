"""homedarts.save_highlight: a photo that is on disk, or an error that says why not."""

import asyncio
import io
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import pytest
import voluptuous as vol
from homeassistant.components.camera import Image
from homeassistant.core import Context
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.setup import async_setup_component

from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.highlights import name_part, photo_stem
from custom_components.homedarts.media_source import highlight
from custom_components.homedarts.services import SAVE_HIGHLIGHT_SCHEMA

from .local_helpers import BASE, JPEG, camera_picture, setup_cameras

# The moment of the photos, 21:05:33 in the time zone of the tests.
TAKEN = "2026-09-26 21:05:33-07:00"
STAMP = "2026-09-26_21-05-33"


def folders(hass, config: Path, media: Path) -> Path:
    """The configuration folder and a media folder that Home Assistant allows
    writing to, as it sets them up; returns the folder of the gallery."""
    hass.config.config_dir = str(config)
    hass.config.media_dirs = {"local": str(media)}
    hass.config.allowlist_external_dirs = {str(config / "www"), str(media)}
    return media / "homedarts" / "highlights"


async def save(hass, **data) -> dict:
    return await hass.services.async_call(
        DOMAIN, "save_highlight", data, blocking=True, return_response=True
    )


@pytest.mark.parametrize(
    "media",
    # /media on Home Assistant OS and in a container, the media folder in the
    # configuration folder elsewhere.
    ["media", "config/media"],
    ids=["home_assistant_os", "core"],
)
async def test_a_saved_photo_is_on_disk_and_opens_in_the_media_browser(
    hass, aioclient_mock, tmp_path, hass_client, media
):
    gallery = folders(hass, tmp_path / "config", tmp_path / media)
    camera, *_ = await setup_cameras(hass, aioclient_mock, 0)
    camera_picture(aioclient_mock, 0)
    saved = await save(hass, camera=camera, player="Alex Bee", label="180")
    file = Path(saved["photo"]).name
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_Alex Bee_180\.jpg", file)
    assert saved == {
        "photo": str((gallery / file).resolve()),
        "photo_url": f"/media/local/homedarts/highlights/{quote(file)}",
    }
    assert await hass.async_add_executor_job(Path(saved["photo"]).read_bytes) == JPEG
    # The gallery reads the player and the score from the name.
    photo = highlight(Path(saved["photo"]))
    assert (photo.player, photo.score, photo.checkout) == ("Alex Bee", 180, False)
    # The address is the one of Home Assistant's media folder, behind its login.
    assert await async_setup_component(hass, "media_source", {})
    response = await (await hass_client()).get(saved["photo_url"])
    assert response.status == 200
    assert await response.read() == JPEG


async def test_a_photo_in_another_allowed_folder_has_no_address(
    hass, aioclient_mock, tmp_path, freezer
):
    freezer.move_to(TAKEN)
    folders(hass, tmp_path / "config", tmp_path / "media")
    share = tmp_path / "share"
    hass.config.allowlist_external_dirs.add(str(share))
    camera, *_ = await setup_cameras(hass, aioclient_mock, 0)
    camera_picture(aioclient_mock, 0)
    saved = await save(hass, camera=camera, folder=f" {share}/darts/ ")
    assert saved == {
        "photo": str((share / "darts" / f"{STAMP}.jpg").resolve()),
        "photo_url": "",
    }
    # In a folder of the media folder, the media browser has it, too.
    darts = tmp_path / "media" / "darts"
    saved = await save(hass, camera=camera, folder=str(darts), label="checkout-121")
    file = f"{STAMP}_checkout-121.jpg"
    assert saved == {
        "photo": str((darts / file).resolve()),
        "photo_url": f"/media/local/darts/{file}",
    }


async def test_only_administrators_and_automations_save_photos(
    hass, aioclient_mock, tmp_path, hass_read_only_user, hass_admin_user
):
    """It writes files, like an export: not for the user of a wall tablet."""
    gallery = folders(hass, tmp_path / "config", tmp_path / "media")
    camera, *_ = await setup_cameras(hass, aioclient_mock, 0)
    camera_picture(aioclient_mock, 0)
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "save_highlight",
            {"camera": camera},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    assert not gallery.exists()
    saved = await hass.services.async_call(
        DOMAIN,
        "save_highlight",
        {"camera": camera, "label": "180"},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
        return_response=True,
    )
    assert Path(saved["photo"]).parent == gallery.resolve()


async def test_photos_of_the_same_moment_keep_each_other(
    hass, aioclient_mock, tmp_path, freezer
):
    """Two cameras, one second, one name: the second photo becomes a copy."""
    freezer.move_to(TAKEN)
    gallery = folders(hass, tmp_path / "config", tmp_path / "media")
    first, second, _ = await setup_cameras(hass, aioclient_mock, 0, 1)
    camera_picture(aioclient_mock, 0)
    camera_picture(aioclient_mock, 1, b"\xff\xd8 the other camera \xff\xd9")
    with patch("custom_components.homedarts.highlights.COPIES", 2):
        saved = [
            Path((await save(hass, camera=camera, player="Lea", label="180"))["photo"])
            for camera in (first, second)
        ]
        assert [path.name for path in saved] == [
            f"{STAMP}_Lea_180.jpg",
            f"{STAMP}_Lea_180 (2).jpg",
        ]
        assert saved[1].read_bytes() == b"\xff\xd8 the other camera \xff\xd9"
        # The gallery shows the copy like the photo.
        copy = highlight(saved[1])
        assert (copy.player, copy.score) == ("Lea", 180)
        # More photos of one moment than that are refused, not written over.
        with pytest.raises(HomeAssistantError) as error:
            await save(hass, camera=first, player="Lea", label="180")
    assert error.value.translation_key == "highlight_failed"
    assert {path.name for path in gallery.iterdir()} == {path.name for path in saved}


async def test_a_camera_without_a_picture_saves_nothing(
    hass, aioclient_mock, tmp_path, freezer
):
    """Disabled, unknown, unavailable or failing: an error, and no file."""
    gallery = folders(hass, tmp_path / "config", tmp_path / "media")
    failing, unplugged, disabled = await setup_cameras(hass, aioclient_mock, 0, 1)
    aioclient_mock.get(f"{BASE}/api/img/cams/0", status=500, text="error")
    # The board has one camera less: the camera stays, unavailable.
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data.local
    with patch.object(
        coordinator.client, "get_config", return_value={"camera_count": 1}
    ):
        # The settings of Board Manager 1 are read again after 30 seconds.
        freezer.tick(timedelta(seconds=30))
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(unplugged).state == "unavailable"
    for camera, kind, key in (
        (disabled, ServiceValidationError, "highlight_camera_missing"),
        ("camera.kitchen", ServiceValidationError, "highlight_camera_missing"),
        (unplugged, HomeAssistantError, "highlight_camera_unavailable"),
        (failing, HomeAssistantError, "highlight_no_picture"),
    ):
        with pytest.raises(kind) as error:
            await save(hass, camera=camera, player="Alex", label="180")
        assert error.value.translation_domain == DOMAIN
        assert error.value.translation_key == key, camera
        assert error.value.translation_placeholders == {"camera": camera}
    assert not gallery.exists()


@pytest.mark.parametrize(
    ("folder", "shown"),
    [
        (".storage", ".storage"),
        ("/etc", "/etc"),
        ("custom_components/homedarts", "custom_components/homedarts"),
        ("media/a\x00b", "media/a?b"),
    ],
)
async def test_photos_go_only_where_home_assistant_allows_it(
    hass, aioclient_mock, tmp_path, folder, shown
):
    folders(hass, tmp_path / "config", tmp_path / "config" / "media")
    camera, *_ = await setup_cameras(hass, aioclient_mock, 0)
    camera_picture(aioclient_mock, 0)
    with pytest.raises(ServiceValidationError) as error:
        await save(hass, camera=camera, folder=folder)
    assert error.value.translation_key == "highlight_folder"
    assert error.value.translation_placeholders == {"folder": shown}
    assert not (tmp_path / "config" / "custom_components").exists()


async def test_without_a_media_folder_the_gallery_is_nowhere(
    hass, aioclient_mock, tmp_path
):
    folders(hass, tmp_path / "config", tmp_path / "media")
    hass.config.media_dirs = {}
    camera, *_ = await setup_cameras(hass, aioclient_mock, 0)
    camera_picture(aioclient_mock, 0)
    with pytest.raises(ServiceValidationError) as error:
        await save(hass, camera=camera)
    assert error.value.translation_placeholders == {"folder": "homedarts/highlights"}


async def test_a_photo_written_halfway_is_removed(hass, aioclient_mock, tmp_path):
    gallery = folders(hass, tmp_path / "config", tmp_path / "media")
    camera, *_ = await setup_cameras(hass, aioclient_mock, 0)
    camera_picture(aioclient_mock, 0)
    opened = Path.open

    class Full(io.BytesIO):
        def write(self, data) -> int:
            raise OSError(28, "No space left on device")

    def full_disk(path: Path, mode: str = "r", *args, **kwargs):
        if mode != "xb":
            return opened(path, mode, *args, **kwargs)
        # The file exists before the disk turns out to be full.
        opened(path, mode).close()
        return Full()

    with (
        patch.object(Path, "open", full_disk),
        pytest.raises(HomeAssistantError) as error,
    ):
        await save(hass, camera=camera, player="Sam")
    assert error.value.translation_key == "highlight_failed"
    assert "No space left on device" in error.value.translation_placeholders["error"]
    assert list(gallery.iterdir()) == []


async def test_the_suffix_follows_the_kind_of_picture(
    hass, aioclient_mock, tmp_path, freezer
):
    freezer.move_to(TAKEN)
    folders(hass, tmp_path / "config", tmp_path / "media")
    camera, *_ = await setup_cameras(hass, aioclient_mock, 0)
    for kind, suffix in (
        ("image/png", ".png"),
        ("image/webp; quality=90", ".webp"),
        ("image/gif", ".jpg"),
    ):
        with patch(
            "custom_components.homedarts.highlights.async_get_image",
            return_value=Image(kind, b"picture"),
        ):
            saved = await save(hass, camera=camera, label=kind[6:10])
        assert Path(saved["photo"]).suffix == suffix, kind


async def test_the_action_saves_without_being_asked_for_its_response(
    hass, aioclient_mock, tmp_path
):
    gallery = folders(hass, tmp_path / "config", tmp_path / "media")
    camera, *_ = await setup_cameras(hass, aioclient_mock, 0)
    camera_picture(aioclient_mock, 0)
    assert (
        await hass.services.async_call(
            DOMAIN, "save_highlight", {"camera": camera}, blocking=True
        )
        is None
    )
    assert [path.read_bytes() for path in gallery.iterdir()] == [JPEG]


async def test_a_clip_records_beside_the_photo_without_holding_up_the_answer(
    hass, aioclient_mock, tmp_path, freezer, caplog
):
    """camera.record returns only when the recording has ended: the clip records
    in the background, and the answer names its file and address at once."""
    freezer.move_to(TAKEN)
    gallery = folders(hass, tmp_path / "config", tmp_path / "media")
    share = tmp_path / "share"
    hass.config.allowlist_external_dirs.add(str(share))
    camera, *_ = await setup_cameras(hass, aioclient_mock, 0)
    camera_picture(aioclient_mock, 0)
    started, done = asyncio.Event(), asyncio.Event()
    records = []

    async def record(call) -> None:
        records.append(dict(call.data))
        started.set()
        await done.wait()

    hass.services.async_register("camera", "record", record)
    saved = await save(hass, camera=camera, label="180", clip_camera="camera.room")
    clip = (gallery / f"{STAMP}_180.mp4").resolve()
    assert saved == {
        "photo": str(clip.with_suffix(".jpg")),
        "photo_url": f"/media/local/homedarts/highlights/{STAMP}_180.jpg",
        "clip": str(clip),
        "clip_url": f"/media/local/homedarts/highlights/{STAMP}_180.mp4",
    }
    await asyncio.wait_for(started.wait(), 1)
    assert records == [
        {
            "entity_id": "camera.room",
            "filename": str(clip),
            "lookback": 5,
            "duration": 8,
        }
    ]
    done.set()
    await hass.async_block_till_done()

    # A camera that cannot record, or records already, leaves only the photo,
    # and the log says why; a photo without an address has a clip without one.
    async def busy(call) -> None:
        raise HomeAssistantError("Stream already recording")

    hass.services.async_register("camera", "record", busy)
    saved = await save(
        hass,
        camera=camera,
        folder=str(share),
        clip_camera="camera.room",
        clip_lookback=2,
        clip_duration=20,
    )
    assert saved["clip"] == str((share / f"{STAMP}.mp4").resolve())
    assert saved["clip_url"] == ""
    await hass.async_block_till_done()
    assert f"No clip {STAMP}.mp4 from camera.room: Stream already recording" in (
        caplog.text
    )
    # An empty clip camera, as the blueprint passes its default, is no clip.
    saved = await save(hass, camera=camera, clip_camera="")
    assert "clip" not in saved


def test_names_and_labels_become_safe_parts_of_a_file_name():
    taken = datetime(2026, 9, 26, 21, 5, 33, tzinfo=UTC)
    assert photo_stem(taken, "", "") == STAMP
    assert photo_stem(taken, "Alex", "") == f"{STAMP}_Alex"
    assert photo_stem(taken, "", "checkout-121") == f"{STAMP}_checkout-121"
    # What a file name, an address or the media folder cannot have, and the
    # separator, leave a name; so do control characters and repeated spaces.
    for name, part in (
        ("Alex/Bee_2", "Alex Bee 2"),
        ('a\\b:c*d?e"f<g>h|i', "a b c d e f g h i"),
        ("{{ 6*7 }}", "6 7"),
        ("50% #1", "50 1"),
        ("J.R. ~ ..hidden", "J.R. hidden"),
        ("tab\there\x00and line", "tab here and line"),
        ("  Kim   Lee  ", "Kim Lee"),
        ("Zoë Ångström", "Zoë Ångström"),
        ("_/~", ""),
        # A dot at the end would make .. before the suffix or the next part.
        ("Alex.", "Alex"),
        ("J.R. .", "J.R"),
        (".", ""),
    ):
        assert name_part(name, 20) == part, name
    assert photo_stem(taken, "Alex.", "") == f"{STAMP}_Alex"
    assert photo_stem(taken, "", "180.") == f"{STAMP}_180"
    # Also when the name is cut right after a dot.
    assert name_part("Anna. Lena", 5) == "Anna"
    # A name is at most as long as a player name, a label a little longer.
    assert photo_stem(taken, "x" * 30, "y" * 30) == f"{STAMP}_{'x' * 20}_{'y' * 24}"
    assert name_part("Anna Lena Maria", 10) == "Anna Lena"


def test_the_player_and_the_label_are_text_whatever_a_template_made_of_them():
    """A template renders a name such as None, 180 or [1] as another type."""
    data = SAVE_HIGHLIGHT_SCHEMA(
        {"camera": "camera.dartroom", "player": None, "label": 180}
    )
    assert data == {"camera": "camera.dartroom", "player": "", "label": "180"}
    assert SAVE_HIGHLIGHT_SCHEMA({"camera": "camera.x", "player": [1]})["player"] == (
        "[1]"
    )
    for wrong in (
        {},
        {"camera": "light.dartroom"},
        {"camera": "camera.x", "folder": "x" * 256},
        {"camera": "camera.x", "clip_camera": "light.dartroom"},
        {"camera": "camera.x", "clip_lookback": 11},
        {"camera": "camera.x", "clip_duration": 0},
    ):
        with pytest.raises(vol.Invalid):
            SAVE_HIGHLIGHT_SCHEMA(wrong)
