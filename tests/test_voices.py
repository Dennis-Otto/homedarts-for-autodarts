"""Voice packs: the sounds of darts-caller's packs for the caller, and packs
recorded with a text-to-speech engine of Home Assistant."""

import asyncio
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote, unquote

import homeassistant.components
import pytest
from homeassistant.core import Context
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.setup import async_setup_component

from custom_components.homedarts import voices
from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.voices import pack_words, sound_key, valid_pack

from .local_helpers import until

ENGINE = "tts.piper"
MP3 = b"ID3 a recorded call"


def folders(hass, tmp_path: Path) -> Path:
    """A media folder that Home Assistant allows writing to, as it sets it up;
    returns the folder of the voice packs."""
    media = tmp_path / "media"
    hass.config.media_dirs = {"local": str(media)}
    hass.config.allowlist_external_dirs = {str(media)}
    return media / "homedarts" / "voices"


def recorded(folder: Path, *names: str) -> Path:
    """A voice pack copied to the folder, with one small file per name."""
    for name in names:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MP3 + name.encode())
    return folder


@pytest.fixture
async def integration(hass):
    assert await async_setup_component(hass, DOMAIN, {})


async def sound(hass, pack: str, *keys) -> dict:
    return await hass.services.async_call(
        DOMAIN,
        "voice_sound",
        {"pack": pack, "keys": list(keys)},
        blocking=True,
        return_response=True,
    )


async def pack_of(client, pack: str) -> dict:
    await client.send_json_auto_id({"type": "homedarts/voice_pack", "pack": pack})
    return await client.receive_json()


def test_the_file_names_of_darts_caller_are_the_keys():
    assert [
        sound_key(name)
        for name in (
            "180.mp3",
            "Gameshot+2.WAV",
            "yr_40+best.ogg",
            "alex bee.flac",
            # No sound, hidden, unnamed, or nothing Home Assistant serves.
            "readme.txt",
            ".180.mp3",
            "+1.mp3",
            "busted~.mp3",
            "busted..mp3",
        )
    ] == ["180", "gameshot", "yr_40", "alex bee", None, None, None, None, None]
    assert [
        valid_pack(name)
        for name in (
            "russ-bray",
            "en-gb Russ_Bray 2",
            "Stimme.de",
            "",
            ".hidden",
            "trailing.",
            "a/b",
            "..",
            "a..b",
            "x" * 65,
        )
    ] == [True, True, True, False, False, False, False, False, False, False]


async def test_a_pack_of_darts_caller_works_as_it_is(
    hass, tmp_path, hass_ws_client, hass_client, integration
):
    """Every sound of a pack by its key, also in folders of the pack and with
    several files for a key, with the address of Home Assistant's media folder;
    what is no sound stays out."""
    pack = recorded(
        folders(hass, tmp_path) / "russ-bray",
        "180.mp3",
        "Gameshot.wav",
        "gameshot+2.wav",
        "busted.mp3",
        "names/alex bee.mp3",
        "readme.txt",
        ".hidden/180.mp3",
        "old~/180.mp3",
    )
    outside = recorded(tmp_path / "elsewhere", "matchshot.mp3")
    (pack / "matchshot.mp3").symlink_to(outside / "matchshot.mp3")
    # The scoreboard loads them with its login; media_source registers its views
    # before the first client freezes the routes of Home Assistant 2026.10.
    assert await async_setup_component(hass, "media_source", {})
    client = await hass_ws_client(hass)
    answer = await pack_of(client, "russ-bray")
    base = "/media/local/homedarts/voices/russ-bray"
    assert answer["success"] is True
    assert answer["result"] == {
        "pack": "russ-bray",
        "sounds": {
            "180": [f"{base}/180.mp3"],
            "busted": [f"{base}/busted.mp3"],
            "gameshot": [f"{base}/Gameshot.wav", f"{base}/gameshot%2B2.wav"],
            "alex bee": [f"{base}/names/alex%20bee.mp3"],
        },
    }
    response = await (await hass_client()).get(f"{base}/names/alex%20bee.mp3")
    assert response.status == 200
    assert await response.read() == MP3 + b"names/alex bee.mp3"


async def test_an_unknown_pack_has_no_sounds(
    hass, tmp_path, hass_ws_client, integration
):
    client = await hass_ws_client(hass)
    # Without a media folder, there is no pack at all.
    hass.config.media_dirs = {}
    assert (await pack_of(client, "russ-bray"))["error"]["code"] == "not_found"
    voices_folder = folders(hass, tmp_path)
    recorded(voices_folder / "empty", "readme.txt")
    (voices_folder / "file.mp3").write_bytes(MP3)
    for pack in ("russ-bray", "empty", "file.mp3", "..", "../media"):
        answer = await pack_of(client, pack)
        assert (answer["success"], answer["error"]["code"]) == (False, "not_found")


async def test_a_huge_folder_is_read_only_so_far(
    hass, tmp_path, hass_ws_client, integration
):
    recorded(folders(hass, tmp_path) / "names", "a.mp3", "b.mp3", "c.mp3")
    client = await hass_ws_client(hass)
    with patch.object(voices, "MAX_SOUNDS", 2):
        answer = await pack_of(client, "names")
    assert list(answer["result"]["sounds"]) == ["a", "b"]


async def test_the_blueprints_get_the_sound_of_a_call(hass, tmp_path, integration):
    """The first key the pack has, as media for a media player, one of its files
    at random; empty when the pack has none of them, so the call is spoken."""
    recorded(
        folders(hass, tmp_path) / "russ-bray",
        "you_require.mp3",
        "40.mp3",
        "Gameshot.wav",
        "gameshot+2.wav",
    )
    assert await sound(hass, "russ-bray", "yr_40", "YOU_REQUIRE") == {
        "key": "YOU_REQUIRE",
        "media_content_id": "media-source://media_source/local/homedarts/voices/russ-bray/you_require.mp3",
        "media_content_type": "audio/mpeg",
    }
    # A template renders a score as a number.
    assert (await sound(hass, "russ-bray", 40))["key"] == "40"
    with patch.object(voices.random, "choice", side_effect=lambda files: files[-1]):
        assert (await sound(hass, "russ-bray", "gameshot")) == {
            "key": "gameshot",
            "media_content_id": "media-source://media_source/local/homedarts/voices/russ-bray/gameshot+2.wav",
            "media_content_type": "audio/wav",
        }
    empty = {"key": "", "media_content_id": "", "media_content_type": ""}
    assert await sound(hass, "russ-bray", "matchshot") == empty
    assert await sound(hass, "piper-en", "180") == empty
    with pytest.raises(ServiceValidationError) as error:
        await sound(hass, "../media", "180")
    assert error.value.translation_key == "voice_pack_name"
    assert error.value.translation_placeholders == {"pack": "../media"}


# -- generated packs -----------------------------------------------------------------


class Engine:
    """Text-to-speech as Home Assistant offers it, with an engine that renders
    each message as a small mp3."""

    def __init__(self, extension: str = "mp3") -> None:
        self.extension = extension
        self.asked: list[dict] = []
        self.rendered: list[str] = []
        self.refuse: str | None = None
        self.fail_at: int | None = None
        self.wait: asyncio.Event | None = None
        # Runs once the engine has spoken the first sound.
        self.meanwhile = None
        self.module = types.ModuleType("homeassistant.components.tts")
        self.module.generate_media_source_id = self.media_id
        self.module.async_get_media_source_audio = self.audio

    def media_id(self, hass, message, engine, language, options, cache=None):
        if self.refuse:
            raise HomeAssistantError(self.refuse)
        self.asked.append(
            {"engine": engine, "language": language, "options": options, "cache": cache}
        )
        return f"media-source://tts/{engine}?message={quote(message)}"

    async def audio(self, hass, media_id):
        if self.wait:
            await self.wait.wait()
        if len(self.rendered) == self.fail_at:
            raise HomeAssistantError("Piper is not running")
        message = unquote(media_id.split("message=", 1)[1])
        self.rendered.append(message)
        if self.meanwhile and len(self.rendered) == 1:
            self.meanwhile()
        return self.extension, b"ID3 " + message.encode()

    def __enter__(self):
        self._patches = [
            patch.dict(sys.modules, {"homeassistant.components.tts": self.module}),
            patch.object(homeassistant.components, "tts", self.module, create=True),
        ]
        for active in self._patches:
            active.start()
        return self

    def __exit__(self, *exc):
        for active in reversed(self._patches):
            active.stop()


async def generate(hass, context: Context | None = None, **data) -> dict:
    return await hass.services.async_call(
        DOMAIN,
        "generate_voice_pack",
        {"tts_entity": ENGINE, "language": "en-GB", "pack": "piper-en", **data},
        blocking=True,
        return_response=True,
        context=context,
    )


def words(pack: Path) -> dict[str, str]:
    """What each sound of a generated pack says."""
    return {
        path.stem: path.read_bytes().removeprefix(b"ID3 ").decode()
        for path in pack.iterdir()
        if not path.name.startswith(".")
    }


@pytest.fixture
def engine(hass):
    hass.states.async_set(ENGINE, "unknown")
    with Engine() as fake:
        yield fake


async def test_a_generated_pack_has_every_call_of_the_caller(
    hass, tmp_path, engine, integration
):
    voices_folder = folders(hass, tmp_path)
    answer = await generate(hass, language="de-DE", voice="de_DE-thorsten-medium")
    pack = voices_folder / "piper-en"
    assert answer == {"pack": "piper-en", "folder": str(pack.resolve()), "sounds": 419}
    said = words(pack)
    assert len(said) == 419
    assert {key: said[key] for key in ("0", "1", "180", "s20", "d20", "t20")} == {
        "0": "Keine Punkte",
        "1": "1",
        "180": "180",
        "s20": "20",
        "d20": "Doppel 20",
        "t20": "Triple 20",
    }
    assert [said[key] for key in ("bull", "bullseye", "outside")] == [
        "25",
        "Bull",
        "Fehlwurf",
    ]
    assert [said[key] for key in ("busted", "gameshot", "matchshot")] == [
        "Überworfen",
        "Game shot, und das Leg!",
        "Game shot, und das Match!",
    ]
    assert (said["you_require"], said["yr_2"], said["yr_170"]) == (
        "Du brauchst",
        "Du brauchst 2",
        "Du brauchst 170",
    )
    assert "yr_171" not in said and "yr_1" not in said
    # Every sound in the language and with the voice asked for, rendered anew.
    assert engine.asked[0] == {
        "engine": ENGINE,
        "language": "de-DE",
        "options": {"voice": "de_DE-thorsten-medium"},
        "cache": False,
    }
    assert json.loads((pack / voices.MARK).read_text()) == {
        "engine": ENGINE,
        "language": "de-DE",
        "voice": "de_DE-thorsten-medium",
    }
    # Nothing is left beside the pack.
    assert sorted(path.name for path in voices_folder.iterdir()) == ["piper-en"]


async def test_the_words_follow_the_language_of_the_voice(
    hass, tmp_path, engine, integration
):
    voices_folder = folders(hass, tmp_path)
    for language, require in (
        ("fr_FR", "Il vous reste 40"),
        ("nl-BE", "Je hebt nog 40 nodig"),
        ("es", "Te quedan 40"),
        # A language the integration does not speak gets English words.
        ("it-IT", "You require 40"),
    ):
        await generate(hass, language=language, pack=language)
        assert words(voices_folder / language)["yr_40"] == require, language
    assert engine.asked[-1]["options"] is None


async def test_a_generated_pack_replaces_the_one_before_and_nothing_else(
    hass, tmp_path, engine, integration
):
    voices_folder = folders(hass, tmp_path)
    await generate(hass)
    pack = voices_folder / "piper-en"
    (pack / "180.mp3").write_bytes(b"ID3 an old 180")
    (pack / "old.mp3").write_bytes(b"ID3 gone")
    await generate(hass)
    assert words(pack)["180"] == "180"
    assert not (pack / "old.mp3").exists()
    # An empty folder of that name is no recorded pack.
    (voices_folder / "fresh").mkdir()
    assert (await generate(hass, pack="fresh"))["sounds"] == 419
    # A pack someone copied there, or a file of that name, stays as it is.
    recorded(voices_folder / "russ-bray", "180.mp3")
    (voices_folder / "loose.mp3").write_bytes(MP3)
    for name in ("russ-bray", "loose.mp3"):
        with pytest.raises(ServiceValidationError) as error:
            await generate(hass, pack=name)
        assert error.value.translation_key == "voice_pack_recorded"
        assert error.value.translation_placeholders == {"pack": name}
    assert [path.name for path in (voices_folder / "russ-bray").iterdir()] == [
        "180.mp3"
    ]
    assert (voices_folder / "loose.mp3").read_bytes() == MP3


async def test_a_pack_copied_there_while_recording_stays_as_it_is(
    hass, tmp_path, engine, integration
):
    voices_folder = folders(hass, tmp_path)
    engine.meanwhile = lambda: recorded(voices_folder / "piper-en", "180.mp3")
    with pytest.raises(ServiceValidationError) as error:
        await generate(hass)
    assert error.value.translation_key == "voice_pack_recorded"
    assert error.value.translation_placeholders == {"pack": "piper-en"}
    pack = voices_folder / "piper-en"
    assert [path.name for path in pack.iterdir()] == ["180.mp3"]
    assert sorted(path.name for path in voices_folder.iterdir()) == ["piper-en"]


async def test_a_pack_that_fails_halfway_leaves_the_one_before(
    hass, tmp_path, engine, integration
):
    voices_folder = folders(hass, tmp_path)
    await generate(hass)
    engine.fail_at = 200
    engine.rendered.clear()
    with pytest.raises(HomeAssistantError) as error:
        await generate(hass)
    assert error.value.translation_key == "voice_pack_failed"
    assert error.value.translation_placeholders == {
        "pack": "piper-en",
        "error": "Piper is not running",
    }
    assert len(words(voices_folder / "piper-en")) == 419
    assert sorted(path.name for path in voices_folder.iterdir()) == ["piper-en"]
    # A sound no browser plays is no sound of a pack.
    engine.fail_at = None
    engine.extension = "pcm"
    with pytest.raises(HomeAssistantError) as error:
        await generate(hass, pack="raw")
    assert (
        error.value.translation_placeholders["error"] == "tts.piper speaks pcm, not mp3"
    )
    assert sorted(path.name for path in voices_folder.iterdir()) == ["piper-en"]


async def test_the_engine_must_speak_the_language(hass, tmp_path, engine, integration):
    folders(hass, tmp_path)
    engine.refuse = "Language 'xx' not supported"
    with pytest.raises(ServiceValidationError) as error:
        await generate(hass, language="xx\x00")
    assert error.value.translation_key == "voice_pack_engine"
    assert error.value.translation_placeholders == {
        "engine": ENGINE,
        "language": "xx?",
        "error": "Language 'xx' not supported",
    }
    hass.states.async_remove(ENGINE)
    with pytest.raises(ServiceValidationError) as error:
        await generate(hass)
    assert error.value.translation_key == "voice_pack_engine_missing"
    assert error.value.translation_placeholders == {"engine": ENGINE}


async def test_a_pack_goes_only_where_home_assistant_allows_it(
    hass, tmp_path, engine, integration
):
    voices_folder = folders(hass, tmp_path)
    for name in (".hidden", "a/b", "trailing."):
        with pytest.raises(ServiceValidationError) as error:
            await generate(hass, pack=name)
        assert error.value.translation_key == "voice_pack_name"
    hass.config.allowlist_external_dirs = set()
    with pytest.raises(ServiceValidationError) as error:
        await generate(hass)
    assert error.value.translation_key == "voice_pack_folder"
    assert error.value.translation_placeholders == {"folder": str(voices_folder)}
    hass.config.media_dirs = {}
    with pytest.raises(ServiceValidationError) as error:
        await generate(hass)
    assert error.value.translation_key == "voice_pack_no_media"
    assert engine.rendered == []


async def test_one_pack_at_a_time(hass, tmp_path, engine, integration):
    folders(hass, tmp_path)
    engine.wait = asyncio.Event()
    first = hass.async_create_task(generate(hass))
    await asyncio.sleep(0)
    await until(
        lambda: voices.GENERATING in hass.data and hass.data[voices.GENERATING].locked()
    )
    with pytest.raises(ServiceValidationError) as error:
        await generate(hass, pack="second")
    assert error.value.translation_key == "voice_pack_busy"
    engine.wait.set()
    assert (await first)["sounds"] == 419


async def test_only_administrators_and_automations_generate_packs(
    hass, tmp_path, engine, integration, hass_read_only_user, hass_admin_user
):
    voices_folder = folders(hass, tmp_path)
    with pytest.raises(Unauthorized):
        await generate(hass, Context(user_id=hass_read_only_user.id))
    assert not voices_folder.exists()
    await generate(hass, Context(user_id=hass_admin_user.id))
    # Asked without a response, it still records the pack.
    await hass.services.async_call(
        DOMAIN,
        "generate_voice_pack",
        {"tts_entity": ENGINE, "language": "en", "pack": "quiet"},
        blocking=True,
    )
    assert sorted(path.name for path in voices_folder.iterdir()) == [
        "piper-en",
        "quiet",
    ]


def test_every_call_has_its_words():
    say = {
        key: key
        for key in (
            "voice_pack_no_score",
            "voice_pack_bust",
            "voice_pack_leg",
            "voice_pack_match",
            "voice_pack_require",
            "voice_bed_outer",
            "voice_bed_bull",
            "voice_bed_miss",
            "voice_pack_target",
            "voice_pack_any_double",
        )
    }
    say |= {
        "voice_pack_require_score": "need {remaining}",
        "voice_bed_double": "D{number}",
        "voice_bed_triple": "T{number}",
    }
    said = pack_words(say)
    assert said["yr_99"] == "need 99" and said["t19"] == "T19" and said["s1"] == "1"
    assert said["bs_target_is"] == "voice_pack_target"
    assert said["bs_any_double"] == "voice_pack_any_double"
    assert len(said) == 419
