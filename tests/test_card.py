"""The dashboard card: dart details for the board view and automatic loading."""

import asyncio
import gzip
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from hypothesis import given
from hypothesis import strategies as st
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homedarts.card import (
    FRONTEND,
    _accepts_gzip,
    _load,
    async_add_card_resources,
    async_register_card,
    async_remove_card_resources,
)
from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.sensor import AutodartsVisitSensor

from .local_helpers import STATE, entity_id, setup_local

MANIFEST = Path(__file__).parents[1] / "custom_components/homedarts/manifest.json"


def dart(name, number, multiplier, bed, x=None, y=None):
    result = {
        "segment": {
            "name": name,
            "number": number,
            "multiplier": multiplier,
            "bed": bed,
        }
    }
    if x is not None:
        result["coords"] = {"x": x, "y": y}
    return result


def visit(*darts, **changes):
    return {
        **STATE,
        "running": True,
        "status": "Throw",
        "numThrows": len(darts),
        "throws": list(darts),
        **changes,
    }


def throws(hass):
    return hass.states.get(entity_id(hass, "sensor", "local_visit_score")).attributes[
        "throws"
    ]


async def test_visit_sensor_reports_beds_and_positions(hass, aioclient_mock):
    await setup_local(
        hass,
        aioclient_mock,
        state=visit(
            dart("T20", 20, 3, "Triple", 0.012345, 0.61239),
            dart("S5", 5, 1, "SingleOuter", -0.28, 0.7),
            dart("Bull", 25, 2, "Double"),
        ),
    )
    assert (
        hass.states.get(entity_id(hass, "sensor", "local_visit_score")).state == "115"
    )
    assert throws(hass) == [
        {
            "segment": "T20",
            "number": 20,
            "multiplier": 3,
            "score": 60,
            "bed": "Triple",
            "x": 0.012,
            "y": 0.612,
        },
        {
            "segment": "S5",
            "number": 5,
            "multiplier": 1,
            "score": 5,
            "bed": "SingleOuter",
            "x": -0.28,
            "y": 0.7,
        },
        {
            "segment": "Bull",
            "number": 25,
            "multiplier": 2,
            "score": 50,
            "bed": "Double",
        },
    ]


async def test_camera_jitter_keeps_positions_until_a_dart_changes(hass, aioclient_mock):
    entry = await setup_local(
        hass, aioclient_mock, state=visit(dart("T20", 20, 3, "Triple", 0.01, 0.6))
    )
    coordinator = entry.runtime_data.local
    first = hass.states.get(entity_id(hass, "sensor", "local_visit_score"))
    coordinator.async_receive(
        "state", visit(dart("T20", 20, 3, "Triple", 0.013, 0.602))
    )
    await hass.async_block_till_done()
    steady = hass.states.get(entity_id(hass, "sensor", "local_visit_score"))
    assert steady.attributes["throws"][0]["x"] == 0.01
    assert steady.last_updated == first.last_updated

    coordinator.async_receive(
        "state",
        visit(
            dart("S20", 20, 1, "SingleOuter", 0.02, 0.75),
            dart("D1", 1, 2, "Double", 0.3, 0.93),
        ),
    )
    await hass.async_block_till_done()
    assert [(item["segment"], item["x"]) for item in throws(hass)] == [
        ("S20", 0.02),
        ("D1", 0.3),
    ]


async def test_a_dart_that_moved_in_its_bed_is_drawn_at_its_new_spot(
    hass, aioclient_mock
):
    """Only camera jitter keeps a position: a reading farther away than about
    1.7 mm, or a dart that takes another dart's place, is drawn where it is."""
    first = dart("T20", 20, 3, "Triple", 0.01, 0.6)
    second = dart("T20", 20, 3, "Triple", 0.05, 0.62)
    entry = await setup_local(hass, aioclient_mock, state=visit(first, second))
    coordinator = entry.runtime_data.local
    # The board takes the first dart back; the second is now the first.
    coordinator.async_receive("state", visit(second))
    await hass.async_block_till_done()
    assert [(item["x"], item["y"]) for item in throws(hass)] == [(0.05, 0.62)]
    # The camera sees the dart 2 mm away: it moved.
    moved = dart("T20", 20, 3, "Triple", 0.05, 0.632)
    coordinator.async_receive("state", visit(moved))
    await hass.async_block_till_done()
    assert [(item["x"], item["y"]) for item in throws(hass)] == [(0.05, 0.632)]
    # A reading without a position shows none instead of the last one.
    coordinator.async_receive("state", visit(dart("T20", 20, 3, "Triple")))
    await hass.async_block_till_done()
    assert "x" not in throws(hass)[0]
    coordinator.async_receive("state", visit(second))
    await hass.async_block_till_done()
    assert [(item["x"], item["y"]) for item in throws(hass)] == [(0.05, 0.62)]


async def test_invalid_darts_are_not_exposed(hass, aioclient_mock):
    entry = await setup_local(
        hass,
        aioclient_mock,
        state=visit(
            dart("T20", 20, 3, "Unknown", float("nan"), 0.5),
            {"segment": {"name": "S5", "number": "5", "multiplier": 1}},
            {"segment": None},
            "garbage",
            {"segment": {"number": 5, "multiplier": 1}, "coords": {"x": True, "y": 1}},
        ),
    )
    assert throws(hass) == [
        {"segment": "T20", "number": 20, "multiplier": 3, "score": 60, "bed": None},
        {"segment": None, "number": 5, "multiplier": 1, "score": 5, "bed": None},
    ]
    # A bed that is no text, as a proxy might send it, is no bed either, and
    # the sensors keep updating without an error in the log.
    entry.runtime_data.local.async_receive(
        "state",
        visit(dart("S5", 5, 1, ["Single"]), dart("D1", 1, 2, {"bed": "Double"})),
    )
    await hass.async_block_till_done()
    assert [(item["segment"], item["bed"]) for item in throws(hass)] == [
        ("S5", None),
        ("D1", None),
    ]
    assert hass.states.get(entity_id(hass, "sensor", "last_throw")).state == "D1"
    assert hass.states.get(entity_id(hass, "sensor", "last_throw_score")).state == "2"


async def test_visit_without_darts_and_positions_stay_out_of_history(
    hass, aioclient_mock
):
    await setup_local(hass, aioclient_mock, state=deepcopy(STATE))
    assert throws(hass) == []
    # Live positions change with every dart and are not useful in the recorder.
    assert "throws" in AutodartsVisitSensor._unrecorded_attributes


# Every file of the cards by its path in their folder: both modules and the texts.
FILES = {
    path.relative_to(FRONTEND).as_posix(): path
    for path in sorted(FRONTEND.rglob("*.js"))
}
# The texts of one language, which the card module imports.
TEXT = "text/de.js"


def tag():
    """Version and digest of every file of the cards, as in their addresses."""
    version = json.loads(MANIFEST.read_text())["version"]
    content = b"".join(FILES[name].read_bytes() for name in sorted(FILES))
    return f"{version}-{hashlib.sha256(content).hexdigest()[:8]}"


def address(name):
    """A file of the cards in the folder of this version."""
    return f"/homedarts/{tag()}/{name}"


async def serve_card(hass, hass_client_no_auth):
    """Register the card as Home Assistant does and return a client without a login."""
    assert await async_setup_component(hass, "http", {})
    hass.config.components.add("frontend")
    with patch("custom_components.homedarts.card.add_extra_js_url") as add_js:
        await async_register_card(hass)
    return await hass_client_no_auth(), add_js


def assert_cached(response):
    # A month, as Home Assistant's own frontend files; the address changes with every
    # version and content.
    assert response.headers["Cache-Control"] == "public, max-age=2678400"
    assert response.headers["ETag"] == f'W/"{tag()}"'
    assert response.headers["Vary"] == "Accept-Encoding"


async def test_card_is_served_and_only_the_small_module_is_on_every_page(
    hass, hass_client_no_auth
):
    client, add_js = await serve_card(hass, hass_client_no_auth)
    # A page gets the card module, from the same folder, once it shows a card.
    assert [call.args for call in add_js.call_args_list] == [
        (hass, address("homedarts-strategy.js")),
    ]
    response = await client.get(address("homedarts-strategy.js"))
    assert response.status == 200
    # Home Assistant's own header for static files, which the card module copies.
    static_cache_control = response.headers["Cache-Control"]
    assert static_cache_control == "public, max-age=2678400"
    assert await response.read() == FILES["homedarts-strategy.js"].read_bytes()

    # Every browser accepts gzip, as the test client does: a quarter of the module.
    response = await client.get(address("homedarts-card.js"), auto_decompress=False)
    assert response.status == 200
    assert response.headers["Content-Type"] == "text/javascript; charset=utf-8"
    assert response.headers["Content-Encoding"] == "gzip"
    assert_cached(response)
    assert response.headers["Cache-Control"] == static_cache_control
    sent = await response.read()
    assert gzip.decompress(sent) == FILES["homedarts-card.js"].read_bytes()
    assert len(sent) < FILES["homedarts-card.js"].stat().st_size * 0.3


async def test_the_texts_of_every_language_are_served_beside_the_card(
    hass, hass_client_no_auth
):
    """The card module imports the texts from its folder, which keeps the version."""
    client, _ = await serve_card(hass, hass_client_no_auth)
    texts = sorted(name for name in FILES if name.startswith("text/"))
    assert texts == [
        f"text/{language}.js" for language in ("de", "en", "es", "fr", "nl")
    ]
    source = FILES["homedarts-card.js"].read_text(encoding="utf-8")
    for name in texts:
        assert f'from "./{name}";' in source
        response = await client.get(address(name), auto_decompress=False)
        assert response.status == 200
        assert response.headers["Content-Type"] == "text/javascript; charset=utf-8"
        assert response.headers["Content-Encoding"] == "gzip"
        assert_cached(response)
        assert gzip.decompress(await response.read()) == FILES[name].read_bytes()


async def test_only_the_files_of_the_cards_are_served(hass, hass_client_no_auth):
    client, _ = await serve_card(hass, hass_client_no_auth)
    for path in (
        address("text/xx.js"),
        address("card.py"),
        address("manifest.json"),
        f"/homedarts/{tag()}/frontend/homedarts-card.js",
        f"/homedarts/{tag()}/other/{tag()}/homedarts-card.js",
    ):
        response = await client.get(path)
        assert response.status == 404, path


def test_a_change_of_any_file_moves_every_address(tmp_path):
    """A new text in one language gives every file a new folder, so no browser
    mixes a cached card module with the texts of another version."""
    folder = tmp_path / "frontend"
    shutil.copytree(FRONTEND, folder)
    with patch("custom_components.homedarts.card.FRONTEND", folder):
        files, digest = _load()
        assert list(files) == sorted(FILES)
        assert files[TEXT][0] == FILES[TEXT].read_bytes()
        assert gzip.decompress(files[TEXT][1]) == files[TEXT][0]
        texts = folder / TEXT
        texts.write_text(texts.read_text("utf-8").replace("Aufnahme", "Runde"), "utf-8")
        assert _load()[1] != digest


@pytest.mark.parametrize(
    "headers",
    [
        {"Accept-Encoding": "identity"},
        {"Accept-Encoding": "br;q=1.0, gzip;q=0"},
        {},
    ],
    ids=["identity", "gzip refused", "no Accept-Encoding"],
)
async def test_card_is_plain_for_clients_without_gzip(
    hass, hass_client_no_auth, headers
):
    client, _ = await serve_card(hass, hass_client_no_auth)
    response = await client.get(
        address("homedarts-card.js"),
        headers=headers,
        skip_auto_headers=[] if headers else ["Accept-Encoding"],
        auto_decompress=False,
    )
    assert response.status == 200
    assert response.headers["Content-Type"] == "text/javascript; charset=utf-8"
    assert "Content-Encoding" not in response.headers
    assert_cached(response)
    assert await response.read() == FILES["homedarts-card.js"].read_bytes()


async def test_a_browser_keeps_its_copy_of_the_card(hass, hass_client_no_auth):
    client, _ = await serve_card(hass, hass_client_no_auth)
    # A browser asks again after a month, Safari also on every reload.
    url = address("homedarts-card.js")
    for known in (f'W/"{tag()}"', f'"{tag()}"', f'"0.1.0-00000000", W/"{tag()}"', "*"):
        response = await client.get(url, headers={"If-None-Match": known})
        assert response.status == 304
        assert_cached(response)
        assert await response.read() == b""
    # A copy of another version gets the module served now.
    response = await client.get(url, headers={"If-None-Match": 'W/"0.1.0-0"'})
    assert response.status == 200
    assert await response.read() == FILES["homedarts-card.js"].read_bytes()


@pytest.mark.parametrize(
    ("accept_encoding", "gzip_accepted"),
    [
        ("gzip, deflate, br, zstd", True),
        ("GZIP", True),
        ("br;q=1.0, gzip;q=0.8, *;q=0.1", True),
        ("gzip ; Q = 0.001", True),
        ("x-gzip", True),
        ("*", True),
        ("deflate, *;q=0.5", True),
        ("", False),
        ("identity", False),
        ("br, zstd", False),
        ("gzip;q=0", False),
        ("gzip;q=0.000, *", False),
        ("*;q=0", False),
        ("gzip;q=high", False),
        ("gzip;q=2", False),
        ("gzipped", False),
    ],
)
def test_accept_encoding_is_read_with_its_weights(accept_encoding, gzip_accepted):
    assert _accepts_gzip(accept_encoding) is gzip_accepted


@given(st.text())
def test_the_first_weight_of_gzip_counts(rest):
    assert _accepts_gzip(f"gzip, {rest}")
    assert not _accepts_gzip(f"gzip;q=0, {rest}")


async def test_card_is_skipped_without_web_frontend(hass):
    hass.http = Mock(async_register_static_paths=AsyncMock())
    with patch("custom_components.homedarts.card.add_extra_js_url") as add_js:
        assert await async_setup_component(hass, "homedarts", {})
    hass.http.async_register_static_paths.assert_not_called()
    hass.http.register_view.assert_not_called()
    add_js.assert_not_called()


@pytest.mark.parametrize("name", ["homedarts-strategy.js", "homedarts-card.js", TEXT])
@pytest.mark.parametrize(
    "folder",
    [
        "/homedarts/{name}",
        "/homedarts/{name}?v={tag}",
        "/homedarts/0.1.0-00000000/{name}",
    ],
    ids=["no version", "the query of earlier releases", "a version that has gone"],
)
async def test_an_address_of_no_or_another_version_never_goes_stale(
    hass, hass_client_no_auth, name, folder
):
    """A resource in YAML has no version in its address, and a page from before an
    update asks for the folder of its version: browsers revalidate both."""
    client, _ = await serve_card(hass, hass_client_no_auth)
    url = folder.format(name=name, tag=tag())
    response = await client.get(url)
    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-cache"
    assert await response.read() == FILES[name].read_bytes()
    # Every load asks again, and an unchanged file costs a few bytes.
    etag = response.headers["ETag"]
    response = await client.get(url, headers={"If-None-Match": etag})
    assert response.status == 304
    assert response.headers["Cache-Control"] == "no-cache"


def test_the_module_of_every_page_stays_small():
    """Every page of every user parses it, so it must not grow into a second card."""
    assert FILES["homedarts-strategy.js"].stat().st_size < 20_000


CAST = "https://cast.home-assistant.io"
OTHER = ("module", "/hacsfiles/button-card/button-card.js")
# A copy of the card module in the www folder, as people installed cards by hand.
COPY = "/local/homedarts/homedarts-card.js"


async def test_home_assistant_cast_may_load_both_modules(hass, hass_client_no_auth):
    """The Cast receiver runs on its own origin and loads the modules from there."""
    client, _ = await serve_card(hass, hass_client_no_auth)
    for name in ("homedarts-strategy.js", "homedarts-card.js", TEXT):
        response = await client.get(address(name), headers={"Origin": CAST})
        assert response.status == 200
        assert response.headers["Access-Control-Allow-Origin"] == CAST


def resources(hass):
    return hass.data[LOVELACE_DATA].resources


def listed(hass):
    """The dashboard resources as Settings, Dashboards, Resources lists them."""
    return [(item["type"], item["url"]) for item in resources(hass).async_items()]


def ours():
    """What the integration keeps there: the small module at its current address."""
    return [("module", address("homedarts-strategy.js"))]


async def with_dashboards(hass, **lovelace):
    """Home Assistant with its frontend and its dashboard resources."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "lovelace", {"lovelace": lovelace})
    hass.config.components.add("frontend")


async def register(hass):
    with patch("custom_components.homedarts.card.add_extra_js_url"):
        await async_register_card(hass)


async def test_cast_finds_the_small_module_in_the_dashboard_resources(
    hass, hass_storage
):
    hass_storage["lovelace_resources"] = {
        "version": 1,
        "key": "lovelace_resources",
        "data": {
            "items": [
                {
                    "id": "old",
                    "type": "module",
                    "url": "/homedarts/homedarts-strategy.js?v=1.0.0-00000000",
                },
                {"id": "theirs", "type": OTHER[0], "url": OTHER[1]},
                {
                    "id": "by-hand",
                    "type": "js",
                    "url": "http://homeassistant.local:8123/homedarts/homedarts-card.js",
                },
                {
                    "id": "twice",
                    "type": "module",
                    "url": "/homedarts/homedarts-card.js?v=1.0.0-00000000",
                },
                {
                    "id": "folder",
                    "type": "module",
                    "url": "/homedarts/1.15.0-00000000/homedarts-strategy.js",
                },
                {"id": "copy", "type": "module", "url": COPY},
            ]
        },
    }
    await with_dashboards(hass)
    await register(hass)
    await async_add_card_resources(hass)
    # Brought to this version in its place, from the query of earlier releases or the
    # folder of another version. The card module of earlier releases goes, as every
    # dashboard would load it; the resources of other cards stay, as does a copy of
    # the card that is not served by the integration.
    assert listed(hass) == [*ours(), OTHER, ("module", COPY)]
    assert [item["id"] for item in resources(hass).async_items()] == [
        "old",
        "theirs",
        "copy",
    ]
    # Once up to date, a board set up later changes nothing.
    collection = resources(hass)
    with (
        patch.object(collection, "async_create_item") as create,
        patch.object(collection, "async_update_item") as update,
        patch.object(collection, "async_delete_item") as delete,
    ):
        await async_add_card_resources(hass)
    create.assert_not_called()
    update.assert_not_called()
    delete.assert_not_called()


async def test_a_resource_that_does_not_parse_stays_as_it_is(hass, hass_storage):
    broken = {"id": "typo", "type": "module", "url": "http://[broken"}
    hass_storage["lovelace_resources"] = {
        "version": 1,
        "key": "lovelace_resources",
        "data": {"items": [broken]},
    }
    await with_dashboards(hass)
    await register(hass)
    await async_add_card_resources(hass)
    assert listed(hass) == [("module", "http://[broken"), *ours()]
    await async_remove_card_resources(hass)
    assert listed(hass) == [("module", "http://[broken")]


async def test_boards_set_up_side_by_side_add_the_module_once(hass):
    await with_dashboards(hass)
    await register(hass)
    collection = resources(hass)
    create = collection.async_create_item

    async def told(data):
        # An open page of the settings hears of every new resource, which takes a
        # moment in which the next board looks at the resources.
        await asyncio.sleep(0)
        return await create(data)

    with patch.object(collection, "async_create_item", told):
        await asyncio.gather(*(async_add_card_resources(hass) for _ in range(3)))
    assert listed(hass) == ours()


async def manual_board(hass, digit, name):
    """A dartboard without Autodarts, which sets up without a network."""
    board_id = f"manual_{digit * 32}"
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=board_id,
        title=f"Autodarts ({name})",
        data={
            "board_id": board_id,
            "manual_board": True,
            "name": name,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_cast_gets_the_cards_until_the_last_board_is_deleted(hass):
    await with_dashboards(hass)
    await resources(hass).async_create_item({"res_type": OTHER[0], "url": OTHER[1]})
    with patch("custom_components.homedarts.card.add_extra_js_url"):
        garage = await manual_board(hass, "1", "Garage")
        cellar = await manual_board(hass, "2", "Cellar")
    assert listed(hass) == [OTHER, *ours()]
    await hass.config_entries.async_remove(garage.entry_id)
    assert listed(hass) == [OTHER, *ours()]
    # An ignored board loads nothing, so it keeps nothing either.
    MockConfigEntry(
        domain=DOMAIN, source=SOURCE_IGNORE, unique_id="ignored"
    ).add_to_hass(hass)
    await hass.config_entries.async_remove(cellar.entry_id)
    assert listed(hass) == [OTHER]
    # A board added again brings them back, without a restart.
    await manual_board(hass, "3", "Garage")
    assert listed(hass) == [OTHER, *ours()]


async def test_resources_in_yaml_stay_the_users_own(hass):
    yaml = [{"url": OTHER[1], "type": OTHER[0]}]
    await with_dashboards(hass, resource_mode="yaml", resources=yaml)
    await register(hass)
    await async_add_card_resources(hass)
    await async_remove_card_resources(hass)
    assert resources(hass).async_items() == yaml


async def test_without_dashboards_there_are_no_resources_to_keep(hass):
    assert await async_setup_component(hass, "http", {})
    hass.config.components.add("frontend")
    await register(hass)
    await async_add_card_resources(hass)
    await async_remove_card_resources(hass)
    assert LOVELACE_DATA not in hass.data


async def test_a_failure_of_the_resources_leaves_the_cards_in_browsers(hass, caplog):
    await with_dashboards(hass)
    await register(hass)
    collection = resources(hass)
    with patch.object(
        collection, "async_create_item", side_effect=HomeAssistantError("read-only")
    ):
        await async_add_card_resources(hass)
    assert "The cards are missing in the dashboard resources: read-only" in caplog.text
    await async_add_card_resources(hass)
    with patch.object(
        collection, "async_delete_item", side_effect=HomeAssistantError("read-only")
    ):
        await async_remove_card_resources(hass)
    assert "The cards stay in the dashboard resources: read-only" in caplog.text
    assert listed(hass) == ours()
