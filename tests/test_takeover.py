"""The takeover of the boards that the integration set up under its former name,
Autodarts: their entities, device, stores, media and dashboards come over, and the
old entry, the old cards and the old folder go."""

import asyncio
import json
import logging
import threading
from contextlib import suppress
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.dashboard import LovelaceStorage
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_IMPORT,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.core import CoreState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
    flush_store,
)

from custom_components.homedarts.const import DISCOVERY_URL
from custom_components.homedarts.storage import storage_key
from custom_components.homedarts.takeover import (
    CONF_TAKEOVER,
    ISSUE_REFERENCES,
    ISSUE_RESTART,
    OLD_DOMAIN,
    async_finish,
    async_take_over,
)

from .local_helpers import local_entry_data, mock_board_v2
from .test_discovery import LISTED, confirm_repair, zeroconf

DOMAIN = "homedarts"
BOARD_ID = "manual_0123456789abcdef0123456789abcdef"
DATA = {"board_id": BOARD_ID, "manual_board": True, "name": "Garage"}
# The store of the old board: a practice game of 301 instead of the 501 of a new one.
TRAINING = {"practice": {"game": 301, "manual_entry": True}}


def old_board(
    hass,
    hass_storage,
    board_id: str = BOARD_ID,
    entry_id: str = "old-entry",
    name: str = "Garage",
    **kwargs,
) -> MockConfigEntry:
    """A board of the integration under its former name, with its device, an entity
    and its stores, as the old integration left them."""
    data = kwargs.pop("data", {**DATA, "board_id": board_id, "name": name})
    entry = MockConfigEntry(
        domain=OLD_DOMAIN,
        version=2,
        unique_id=board_id,
        title=f"Autodarts ({name})",
        # A key of the cloud link that never came, which no entry keeps.
        data={**data, "local_only": True},
        entry_id=entry_id,
        **kwargs,
    )
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(OLD_DOMAIN, board_id)},
        name=name,
    )
    er.async_get(hass).async_get_or_create(
        "sensor",
        OLD_DOMAIN,
        f"{board_id}_practice_remaining",
        config_entry=entry,
        device_id=device.id,
        suggested_object_id=f"{name.lower()}_practice_remaining",
    )
    key = storage_key(entry.entry_id, OLD_DOMAIN)
    hass_storage[key] = {"version": 1, "minor_version": 3, "key": key, "data": TRAINING}
    report = f"{OLD_DOMAIN}.{entry.entry_id}.journal"
    hass_storage[report] = {"version": 1, "key": report, "data": {"days": {}}}
    return entry


async def take_over(hass) -> dict:
    """Choose the takeover in the setup and confirm it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["menu_options"][0] == "takeover"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "takeover"}
    )
    assert result["step_id"] == "takeover"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    return result


async def test_the_setup_offers_the_takeover_only_with_old_boards(hass, hass_storage):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert "takeover" not in result["menu_options"]
    old_board(hass, hass_storage)
    # An ignored board, and one of the first version that the old integration
    # never migrated, are not taken over.
    MockConfigEntry(domain=OLD_DOMAIN, version=2, source=SOURCE_IGNORE).add_to_hass(
        hass
    )
    MockConfigEntry(domain=OLD_DOMAIN, version=1, unique_id="v1").add_to_hass(hass)
    # Neither is a board of another integration with the domain autodarts.
    MockConfigEntry(
        domain=OLD_DOMAIN, version=2, unique_id="cloud", data={"email": "a@example.com"}
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["menu_options"][0] == "takeover"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "takeover"}
    )
    assert result["description_placeholders"] == {"boards": "- Autodarts (Garage)"}


async def test_a_board_keeps_its_entities_device_and_stores(hass, hass_storage):
    old = old_board(hass, hass_storage, options={"weekly_report": True})
    result = await take_over(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == BOARD_ID
    assert entry.title == "Autodarts (Garage)"
    assert entry.data == DATA
    assert entry.options == {"weekly_report": True}
    assert hass.config_entries.async_get_entry(old.entry_id) is None
    # The entity keeps its ID, and so its history and statistics.
    item = er.async_get(hass).async_get("sensor.garage_practice_remaining")
    assert item.platform == DOMAIN
    assert item.config_entry_id == entry.entry_id
    assert hass.states.get("sensor.garage_practice_remaining").state == "301"
    device = dr.async_get(hass).async_get(item.device_id)
    assert device.identifiers == {(DOMAIN, BOARD_ID)}
    assert dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id) == [
        device
    ]
    assert hass_storage[storage_key(entry.entry_id)]["data"]["practice"]["game"] == 301
    assert f"{DOMAIN}.{entry.entry_id}.journal" in hass_storage


async def test_the_sensors_of_the_cloud_link_do_not_come_over(hass, hass_storage):
    old = old_board(hass, hass_storage)
    entities = er.async_get(hass)
    cloud = entities.async_get_or_create(
        "sensor", OLD_DOMAIN, f"{BOARD_ID}_board_status", config_entry=old
    )
    await take_over(hass)
    assert entities.async_get(cloud.entity_id) is None
    assert entities.async_get("sensor.garage_practice_remaining").platform == DOMAIN


async def test_every_board_is_taken_over_at_once(hass, hass_storage):
    old_board(hass, hass_storage)
    old_board(hass, hass_storage, "manual_other", "old-other", "Keller")
    await take_over(hass)
    assert not hass.config_entries.async_entries(OLD_DOMAIN)
    assert sorted(
        entry.title for entry in hass.config_entries.async_entries(DOMAIN)
    ) == [
        "Autodarts (Garage)",
        "Autodarts (Keller)",
    ]
    assert hass.states.get("sensor.keller_practice_remaining").state == "301"


async def test_a_discovered_board_of_the_old_integration_is_taken_over(
    hass, hass_storage, aioclient_mock
):
    mock_board_v2(aioclient_mock)
    old_board(hass, hass_storage, "manual_other", "old-other", "Keller")
    old_board(
        hass,
        hass_storage,
        "board-1",
        "old-board",
        "Wohnzimmer",
        data=local_entry_data(),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=zeroconf()
    )
    assert result["step_id"] == "takeover"
    # The discovered board comes first.
    assert result["description_placeholders"] == {
        "boards": "- Autodarts (Wohnzimmer)\n- Autodarts (Keller)"
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["result"].unique_id == "board-1"
    data = result["result"].data
    assert data["host"] == "192.0.2.10"
    assert "local_only" not in data
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def choose(hass, step: str) -> dict:
    """Choose a way to set up a board other than the takeover, which comes first."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["menu_options"][0] == "takeover"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


async def assert_taken_over(hass, result: dict) -> None:
    """The flow offers the takeover of the board, and confirmed, it takes it over
    with its entities instead of setting it up anew."""
    assert result["step_id"] == "takeover"
    assert result["description_placeholders"] == {"boards": "- Autodarts (Wohnzimmer)"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == "board-1"
    assert entry.data["host"] == "192.0.2.10"
    assert not hass.config_entries.async_entries(OLD_DOMAIN)
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    item = er.async_get(hass).async_get("sensor.wohnzimmer_practice_remaining")
    assert item.config_entry_id == entry.entry_id


async def test_a_board_of_the_old_integration_entered_by_address_is_taken_over(
    hass, hass_storage, aioclient_mock
):
    mock_board_v2(aioclient_mock)
    old_board(
        hass,
        hass_storage,
        "board-1",
        "old-board",
        "Wohnzimmer",
        data=local_entry_data(),
    )
    result = await choose(hass, "local")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.10", "port": 3180}
    )
    await assert_taken_over(hass, result)


async def test_a_board_of_the_old_integration_found_by_the_search_is_taken_over(
    hass, hass_storage, aioclient_mock
):
    aioclient_mock.get(DISCOVERY_URL, json=LISTED)
    mock_board_v2(aioclient_mock)
    old_board(
        hass,
        hass_storage,
        "board-1",
        "old-board",
        "Wohnzimmer",
        data=local_entry_data(),
    )
    result = await choose(hass, "discover")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"board_id": "board-1"}
    )
    await assert_taken_over(hass, result)


def fresh_board(hass) -> MockConfigEntry:
    """A board of this integration set up anew for the board of an old entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=BOARD_ID,
        title="Garage (new)",
        data=DATA,
        entry_id="fresh-entry",
    )
    entry.add_to_hass(hass)
    return entry


DUPLICATE = "takeover_duplicate_fresh-entry"


async def set_up_twice(hass, hass_storage) -> tuple[MockConfigEntry, MockConfigEntry]:
    """An old board, and a new entry set up for it beside the old one."""
    old = old_board(hass, hass_storage)
    fresh = fresh_board(hass)
    assert await hass.config_entries.async_setup(fresh.entry_id)
    await hass.async_block_till_done()
    return old, fresh


async def open_repair(hass, hass_client) -> tuple[object, dict]:
    """Open the repair of the board set up twice, as the user does in the UI."""
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    response = await client.post(
        "/api/repairs/issues/fix", json={"handler": DOMAIN, "issue_id": DUPLICATE}
    )
    return client, await response.json()


async def test_a_board_set_up_anew_beside_its_old_entry_is_reported(hass, hass_storage):
    # An ignored board and an entry that takes its old one over are not new.
    MockConfigEntry(
        domain=DOMAIN, unique_id="manual_other", source=SOURCE_IGNORE
    ).add_to_hass(hass)
    old_board(hass, hass_storage, "manual_other", "old-other", "Keller")
    MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="manual_third",
        data={**DATA, "board_id": "manual_third", CONF_TAKEOVER: "old-third"},
        # So that it waits, with its takeover not yet done.
        disabled_by=ConfigEntryDisabler.USER,
    ).add_to_hass(hass)
    old_board(hass, hass_storage, "manual_third", "old-third", "Dachboden")
    await set_up_twice(hass, hass_storage)
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(DOMAIN, DUPLICATE)
    assert issue.is_fixable
    assert issue.translation_key == "takeover_duplicate"
    assert issue.translation_placeholders == {
        "board": "Autodarts (Garage)",
        "entry": "Garage (new)",
    }
    assert issue.data == {
        "entry_id": "fresh-entry",
        "old_entry_id": "old-entry",
        "board": "Autodarts (Garage)",
        "entry": "Garage (new)",
    }
    assert [
        issue_id
        for domain, issue_id in issues.issues
        if issue_id.startswith("takeover")
    ] == [DUPLICATE]


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "nl"])
def test_the_report_tells_the_two_boards_apart_by_their_integration(language):
    # Both entries are usually called after their board, such as "Autodarts
    # (Garage)": the texts tell them apart by their integration, not by the titles.
    texts = json.loads(
        (
            Path(__file__).parents[1]
            / "custom_components/homedarts/translations"
            / f"{language}.json"
        ).read_text(encoding="utf-8")
    )["issues"]["takeover_duplicate"]
    confirm = texts["fix_flow"]["step"]["confirm"]
    for text in (texts["title"], confirm["title"], confirm["description"]):
        assert "{board}" in text
    for text in (texts["title"], confirm["description"]):
        assert "HomeDarts" in text.split("{entry}")[0].rsplit("{board}", 1)[-1]
        assert "Autodarts" in text.split("{board}")[0].rsplit("{entry}", 1)[-1]


async def test_the_report_follows_the_two_entries(hass, hass_storage):
    old, fresh = await set_up_twice(hass, hass_storage)
    # The entries of other integrations change nothing, and cost no look.
    other = MockConfigEntry(domain="sun")
    other.add_to_hass(hass)
    with patch(
        "custom_components.homedarts.takeover.async_report_duplicates"
    ) as report:
        hass.config_entries.async_update_entry(other, title="Sun")
    report.assert_not_called()
    # With the old entry deleted, nothing is left to take over.
    await hass.config_entries.async_remove(old.entry_id)
    assert ir.async_get(hass).async_get_issue(DOMAIN, DUPLICATE) is None
    old_board(hass, hass_storage)
    hass.config_entries.async_update_entry(fresh, title="Garage (renamed)")
    issue = ir.async_get(hass).async_get_issue(DOMAIN, DUPLICATE)
    assert issue.translation_placeholders["entry"] == "Garage (renamed)"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert "takeover" not in result["menu_options"]
    # With the new entry deleted instead, the takeover is offered again.
    await hass.config_entries.async_remove(fresh.entry_id)
    assert ir.async_get(hass).async_get_issue(DOMAIN, DUPLICATE) is None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["menu_options"][0] == "takeover"


@pytest.mark.parametrize("gone", [False, True])
async def test_the_repair_deletes_the_new_entry_and_takes_the_old_one_over(
    hass, hass_storage, hass_client, gone
):
    _, fresh = await set_up_twice(hass, hass_storage)
    client, flow = await open_repair(hass, hass_client)
    assert flow["step_id"] == "confirm"
    assert flow["description_placeholders"] == {
        "board": "Autodarts (Garage)",
        "entry": "Garage (new)",
    }
    if gone:
        # The user deleted the new entry meanwhile: the takeover still comes.
        await hass.config_entries.async_remove(fresh.entry_id)
    response = await client.post(f"/api/repairs/issues/fix/{flow['flow_id']}", json={})
    result = await response.json()
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert hass.config_entries.async_get_entry(fresh.entry_id) is None
    assert not hass.config_entries.async_entries(OLD_DOMAIN)
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.unique_id == BOARD_ID
    assert entry.title == "Autodarts (Garage)"
    # The old entities, with their IDs, and the old stores.
    assert hass.states.get("sensor.garage_practice_remaining").state == "301"
    assert ir.async_get(hass).async_get_issue(DOMAIN, DUPLICATE) is None


async def test_the_repair_keeps_the_new_entry_once_the_old_one_is_gone(
    hass, hass_storage, hass_client
):
    old, fresh = await set_up_twice(hass, hass_storage)
    client, flow = await open_repair(hass, hass_client)
    await hass.config_entries.async_remove(old.entry_id)
    response = await client.post(f"/api/repairs/issues/fix/{flow['flow_id']}", json={})
    result = await response.json()
    assert result["type"] == "abort"
    assert result["reason"] == "nothing_to_take_over"
    assert hass.config_entries.async_get_entry(fresh.entry_id) is fresh


async def test_a_board_taken_over_meanwhile_is_not_taken_over_again(hass, hass_storage):
    old = old_board(hass, hass_storage)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.config_entries.async_remove(old.entry_id)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "takeover"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "nothing_to_take_over"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_TAKEOVER: old.entry_id}
    )
    assert result["reason"] == "nothing_to_take_over"


async def test_a_loaded_old_board_is_unloaded_first(hass, hass_storage, caplog):
    old_board(hass, hass_storage)
    unload = AsyncMock(return_value=True)
    with (
        patch.object(hass.config_entries, "async_unload", unload),
        patch.object(
            er.EntityRegistry,
            "async_update_entity_platform",
            side_effect=ValueError("loaded"),
        ),
        caplog.at_level(logging.WARNING),
    ):
        await take_over(hass)
    # Before anything moves, and once more by the removal of the old entry.
    assert unload.await_args_list[0].args == ("old-entry",)
    # An entity still loaded stays with the old integration.
    assert (
        "sensor.garage_practice_remaining stays with the old integration" in caplog.text
    )


async def test_an_old_board_that_failed_to_unload_is_not_unloaded_again(
    hass, hass_storage
):
    old_board(hass, hass_storage, state=ConfigEntryState.FAILED_UNLOAD)
    unload = AsyncMock(return_value=True)
    with patch.object(hass.config_entries, "async_unload", unload):
        await take_over(hass)
    assert ("old-entry",) not in [call.args for call in unload.await_args_list]


async def test_an_entity_left_by_an_earlier_entry_gives_way(hass, hass_storage):
    old_board(hass, hass_storage)
    entities = er.async_get(hass)
    left = entities.async_get_or_create(
        "sensor", DOMAIN, f"{BOARD_ID}_practice_remaining", suggested_object_id="left"
    )
    await take_over(hass)
    assert entities.async_get(left.entity_id) is None
    assert entities.async_get("sensor.garage_practice_remaining").platform == DOMAIN


async def test_an_entry_whose_old_one_is_gone_still_sets_up(hass, hass_storage):
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=BOARD_ID,
        data={**DATA, CONF_TAKEOVER: "gone"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.data == DATA


@pytest.fixture
def config_dir(hass, tmp_path):
    """A configuration folder of its own, with a media folder."""
    hass.config.config_dir = str(tmp_path)
    media = tmp_path / "media"
    media.mkdir()
    hass.config.media_dirs = {"local": str(media)}
    return tmp_path


def old_folder(config_dir: Path, codeowner: str = "@Dennis-Otto") -> Path:
    folder = config_dir / "custom_components" / OLD_DOMAIN
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(
        json.dumps({"domain": OLD_DOMAIN, "codeowners": [codeowner]}), encoding="utf-8"
    )
    return folder


async def test_the_media_move_to_the_new_folders(hass, hass_storage, config_dir):
    media = config_dir / "media"
    pack = media / OLD_DOMAIN / "voices" / "Anna"
    pack.mkdir(parents=True)
    (pack / ".autodarts-voice-pack").touch()
    (media / OLD_DOMAIN / "highlights").mkdir()
    (media / OLD_DOMAIN / "highlights" / "180.jpg").write_bytes(b"jpg")
    # An export folder that the new integration already made stays where it is.
    (media / OLD_DOMAIN / "exports").mkdir()
    (media / DOMAIN / "exports").mkdir(parents=True)
    old_board(hass, hass_storage)
    await take_over(hass)
    assert (media / DOMAIN / "highlights" / "180.jpg").read_bytes() == b"jpg"
    assert (media / DOMAIN / "voices" / "Anna" / ".homedarts-voice-pack").exists()
    assert not (media / DOMAIN / "voices" / "Anna" / ".autodarts-voice-pack").exists()
    assert (media / OLD_DOMAIN / "exports").is_dir()


async def test_the_old_folder_stays_until_the_last_board_is_taken_over(
    hass, hass_storage, config_dir
):
    # One after the other, so that the first board surely finds the second left: boards
    # taken over at once may or may not (#463).
    folder = old_folder(config_dir)
    first = old_board(hass, hass_storage)
    second = old_board(hass, hass_storage, "manual_other", "old-other", "Keller")
    for old, left in ((first, True), (second, False)):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_TAKEOVER: old.entry_id},
        )
        await hass.async_block_till_done()
        assert folder.exists() is left
        assert (
            ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_RESTART) is None
        ) is left


async def test_boards_that_end_at_once_finish_one_after_the_other(hass):
    # Boards taken over at once can each find no old board left. Moved in two threads
    # at once, a file that the other thread took first fails the setup of a board.
    together = threading.Barrier(2, timeout=0.2)
    met = []

    def move_media(_roots: list[str]) -> None:
        with suppress(threading.BrokenBarrierError):
            together.wait()
            met.append(True)

    with patch("custom_components.homedarts.takeover._move_media", move_media):
        await asyncio.gather(async_finish(hass), async_finish(hass))

    assert not met


async def test_the_old_folder_goes_and_a_restart_is_offered(
    hass, hass_storage, hass_client, config_dir
):
    folder = old_folder(config_dir)
    old_board(hass, hass_storage)
    await take_over(hass)
    assert not folder.exists()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_RESTART)
    assert issue.is_fixable
    restart = async_mock_service(hass, "homeassistant", "restart")
    result = await confirm_repair(hass, hass_client, ISSUE_RESTART)
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert len(restart) == 1


@pytest.mark.parametrize(
    "manifest",
    [
        # The original integration of Trkal has the same domain.
        '{"domain": "autodarts", "codeowners": ["@Trkal"]}',
        '{"domain": "other", "codeowners": ["@Dennis-Otto"]}',
        "[]",
        "no JSON",
    ],
)
async def test_another_integration_named_autodarts_stays(
    hass, hass_storage, config_dir, manifest
):
    folder = old_folder(config_dir)
    (folder / "manifest.json").write_text(manifest, encoding="utf-8")
    old_board(hass, hass_storage)
    await take_over(hass)
    assert folder.exists()
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_RESTART) is None


async def test_a_file_that_cannot_move_stops_nothing_else(
    hass, hass_storage, config_dir, caplog
):
    media = config_dir / "media"
    (media / OLD_DOMAIN / "highlights").mkdir(parents=True)
    (media / OLD_DOMAIN / "exports").mkdir()
    pack = media / DOMAIN / "voices" / "Anna"
    pack.mkdir(parents=True)
    (pack / ".autodarts-voice-pack").touch()
    folder = old_folder(config_dir)
    rename = Path.rename

    def stuck(source: Path, target: Path) -> Path:
        # A file in use, or a folder without the right to write it.
        if source.name in {"highlights", ".autodarts-voice-pack"}:
            raise PermissionError(13, "Permission denied", str(source))
        return rename(source, target)

    old_board(hass, hass_storage)
    with patch.object(Path, "rename", stuck):
        await take_over(hass)
    assert (media / OLD_DOMAIN / "highlights").is_dir()
    assert (pack / ".autodarts-voice-pack").exists()
    assert (media / DOMAIN / "exports").is_dir()
    assert "highlights stays where it is" in caplog.text
    assert ".autodarts-voice-pack stays where it is" in caplog.text
    # The rest of the finish went on.
    assert not folder.exists()
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_RESTART)
    assert CONF_TAKEOVER not in hass.config_entries.async_entries(DOMAIN)[0].data


async def test_a_media_folder_without_room_for_the_new_folder_stays(
    hass, hass_storage, config_dir, caplog
):
    media = config_dir / "media"
    (media / OLD_DOMAIN / "highlights").mkdir(parents=True)
    # A file where the new folder belongs: the folder can't be made.
    (media / DOMAIN).write_bytes(b"")
    folder = old_folder(config_dir)
    old_board(hass, hass_storage)
    await take_over(hass)
    assert (media / OLD_DOMAIN / "highlights").is_dir()
    assert "stay where they are" in caplog.text
    assert not folder.exists()


@pytest.mark.expected_errors
async def test_a_finish_that_fails_runs_again_at_the_next_setup(
    hass, hass_storage, config_dir, caplog
):
    folder = old_folder(config_dir)
    old_board(hass, hass_storage)
    with patch(
        "custom_components.homedarts.takeover._async_update_dashboards",
        side_effect=OSError(28, "No space left on device"),
    ):
        await take_over(hass)
    # The board sets up all the same, and the takeover stays in its data.
    [entry] = hass.config_entries.async_entries(DOMAIN)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_TAKEOVER] == "old-entry"
    assert "is not finished" in caplog.text
    assert folder.exists()
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_RESTART) is None

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data == DATA
    assert not folder.exists()
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_RESTART)


async def test_a_finish_that_a_stop_interrupted_runs_at_the_next_start(
    hass, hass_storage, config_dir
):
    media = config_dir / "media"
    (media / OLD_DOMAIN / "highlights").mkdir(parents=True)
    folder = old_folder(config_dir)
    old_board(hass, hass_storage)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=BOARD_ID,
        data={**DATA, CONF_TAKEOVER: "old-entry"},
    )
    entry.add_to_hass(hass)
    # Home Assistant stops while the takeover is finishing: the old entry is gone,
    # but the takeover stays in the data of the new one.
    with (
        patch(
            "custom_components.homedarts.takeover._async_update_dashboards",
            side_effect=asyncio.CancelledError,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_take_over(hass, entry)
    assert hass.config_entries.async_get_entry("old-entry") is None
    assert entry.data[CONF_TAKEOVER] == "old-entry"

    # The next start finishes it.
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (media / DOMAIN / "highlights").is_dir()
    assert not folder.exists()
    assert entry.data == DATA


class YamlDashboard:
    """A dashboard in YAML, which Home Assistant does not let the integration save."""

    def __init__(self, config: dict) -> None:
        self.config = config

    async def async_load(self, force: bool) -> dict:
        return self.config


async def test_the_dashboards_get_the_new_cards(hass, hass_storage):
    assert await async_setup_component(hass, "lovelace", {})
    dashboards = hass.data[LOVELACE_DATA].dashboards
    darts = LovelaceStorage(
        hass, {"id": "darts", "url_path": "darts", "mode": "storage"}
    )
    dashboards["darts"] = darts
    await darts.async_save(
        {
            "strategy": {"type": "custom:autodarts"},
            "views": [
                {
                    "cards": [
                        {"type": "custom:autodarts-card", "board_style": "autodarts"},
                        {"type": "custom:autodarts-scoreboard-card"},
                        {"type": "entities", "entities": ["sensor.autodarts_board"]},
                    ]
                }
            ],
        }
    )
    other = LovelaceStorage(
        hass, {"id": "other", "url_path": "other", "mode": "storage"}
    )
    dashboards["other"] = other
    await other.async_save({"views": [{"cards": [{"type": "entities"}]}]})
    dashboards["yaml-darts"] = YamlDashboard({"views": [{"type": "custom:autodarts"}]})
    old_board(hass, hass_storage)
    await take_over(hass)
    assert await darts.async_load(False) == {
        "strategy": {"type": "custom:homedarts"},
        "views": [
            {
                "cards": [
                    {"type": "custom:homedarts-card", "board_style": "flat"},
                    {"type": "custom:homedarts-scoreboard-card"},
                    {"type": "entities", "entities": ["sensor.autodarts_board"]},
                ]
            }
        ],
    }
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_REFERENCES)
    assert issue.translation_placeholders == {"items": "- /yaml-darts"}


async def test_the_old_cards_leave_the_dashboard_resources(hass, hass_storage):
    hass_storage["lovelace_resources"] = {
        "version": 1,
        "key": "lovelace_resources",
        "data": {
            "items": [
                {
                    "id": "1",
                    "type": "module",
                    "url": "/autodarts/1.18.0-abc/autodarts-card.js",
                },
                {
                    "id": "2",
                    "type": "module",
                    "url": "/autodarts/autodarts-strategy.js?x",
                },
                {"id": "3", "type": "module", "url": "/local/other-card.js"},
            ]
        },
    }
    assert await async_setup_component(hass, "lovelace", {})
    old_board(hass, hass_storage)
    await take_over(hass)
    resources = hass.data[LOVELACE_DATA].resources
    assert (
        next(item["url"] for item in resources.async_items()) == "/local/other-card.js"
    )
    assert not any("/autodarts/" in item["url"] for item in resources.async_items())


async def test_automations_and_scripts_with_old_actions_are_listed(hass, hass_storage):
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "start",
                    "alias": "Start a game",
                    "triggers": [{"trigger": "event", "event_type": "start"}],
                    "actions": [{"action": "autodarts.start_game"}],
                },
                {
                    "id": "lights",
                    "alias": "Lights",
                    "triggers": [{"trigger": "event", "event_type": "lights"}],
                    # A host of Autodarts is no action.
                    "actions": [
                        {
                            "action": "notify.notify",
                            "data": {"message": "play.autodarts.io"},
                        }
                    ],
                },
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "script",
        {"script": {"next": {"sequence": [{"action": "autodarts.next_player"}]}}},
    )
    old_board(hass, hass_storage)
    await take_over(hass)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_REFERENCES)
    assert issue.translation_placeholders == {
        "items": "- automation.start_a_game\n- script.next"
    }


async def test_nothing_to_report_without_old_references(hass, hass_storage):
    old_board(hass, hass_storage)
    await take_over(hass)
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_REFERENCES) is None
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_RESTART) is None


async def automations(hass, *actions: str) -> None:
    """Automations, one with each action, named after it."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": action,
                    "alias": action.replace(".", " "),
                    "triggers": [{"trigger": "event", "event_type": action}],
                    "actions": [{"action": action}],
                }
                for action in actions
            ]
        },
    )


def earlier_repair(hass, items: str) -> None:
    """The repair of the references as an earlier version made it: not kept over
    a restart, with what was left at the takeover."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_REFERENCES,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_REFERENCES,
        translation_placeholders={"items": items},
    )


async def test_the_list_of_references_outlasts_the_restart(hass, hass_storage):
    await automations(hass, "autodarts.start_game")
    old_board(hass, hass_storage)
    await take_over(hass)
    await flush_store(ir.async_get(hass)._store)
    # The restart that the takeover asks for loads the repairs anew.
    restarted = ir.IssueRegistry(hass)
    await restarted.async_load()
    issue = restarted.async_get_issue(DOMAIN, ISSUE_REFERENCES)
    assert issue.active
    assert issue.translation_placeholders == {
        "items": "- automation.autodarts_start_game"
    }


async def test_the_list_of_an_earlier_version_comes_back_after_its_restart(hass):
    earlier_repair(hass, "- automation.autodarts_start_game")
    await flush_store(ir.async_get(hass)._store)
    # The restart after a takeover with an earlier version kept only an inactive
    # entry of its repair, without the list.
    restarted = ir.IssueRegistry(hass)
    await restarted.async_load()
    hass.data[ir.DATA_REGISTRY] = restarted
    issue = restarted.async_get_issue(DOMAIN, ISSUE_REFERENCES)
    assert not issue.active
    assert issue.translation_placeholders is None
    await automations(hass, "autodarts.start_game")
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_REFERENCES)
    assert issue.active
    assert issue.is_persistent
    assert issue.translation_placeholders == {
        "items": "- automation.autodarts_start_game"
    }


async def test_the_list_follows_the_changes_at_the_next_start(hass):
    hass.set_state(CoreState.not_running)
    earlier_repair(
        hass, "- automation.autodarts_start_game\n- automation.autodarts_next_player"
    )
    assert await async_setup_component(hass, DOMAIN, {})
    # The automations load after the integration, and only one still has an old
    # action: the list waits for the start of Home Assistant.
    await automations(hass, "autodarts.start_game", "homedarts.next_player")
    await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_REFERENCES)
    assert issue.translation_placeholders["items"].count("\n") == 1
    await hass.async_start()
    await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_REFERENCES)
    assert issue.translation_placeholders == {
        "items": "- automation.autodarts_start_game"
    }
    assert issue.is_persistent
    assert issue.active


async def test_the_repair_goes_with_the_last_reference(hass):
    earlier_repair(hass, "- automation.autodarts_start_game")
    await automations(hass, "homedarts.start_game")
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_REFERENCES) is None


async def test_an_ignored_list_stays_ignored(hass):
    earlier_repair(
        hass, "- automation.autodarts_start_game\n- automation.autodarts_next_player"
    )
    ir.async_get(hass).async_ignore(DOMAIN, ISSUE_REFERENCES, True)
    await automations(hass, "autodarts.start_game")
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_REFERENCES)
    assert issue.translation_placeholders == {
        "items": "- automation.autodarts_start_game"
    }
    assert issue.dismissed_version is not None


async def test_without_the_repair_a_start_looks_at_nothing(hass):
    # An automation of another integration named autodarts, after no takeover.
    await automations(hass, "autodarts.start_game")
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_REFERENCES) is None
