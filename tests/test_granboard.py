"""A Granboard over Home Assistant's Bluetooth: its frames, its setup, and its
darts on a dartboard without Autodarts.

The frames are recorded as the board sends them, bytes on the notify
characteristic of its service; the Bluetooth of Home Assistant and Bleak are
fakes, so the tests run without an adapter."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from bleak.exc import BleakError
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    SOURCE_BLUETOOTH,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.homedarts import granboard
from custom_components.homedarts.diagnostics import async_get_config_entry_diagnostics
from custom_components.homedarts.granboard import (
    BUTTON,
    FRAMES,
    RETRY_MAX_SECONDS,
    SERVICE_UUID,
    WARM_UP_SECONDS,
    FrameReader,
    Hit,
)
from custom_components.homedarts.manual import parse_bed

from .local_helpers import mock_board

ADDRESS = "AA:BB:CC:DD:EE:01"
BOARD_ID = "granboard_aabbccddee01"
DATA = {
    "board_id": BOARD_ID,
    "manual_board": True,
    "name": "Granboard",
    "granboard": ADDRESS,
}
# Frames as the board sends them, one notification each.
RECORDED = {
    b"3.4@": "T20",
    b"3.3@": "S20",
    b"3.5@": "S20",
    b"3.6@": "D20",
    b"2.3@": "S1",
    b"9.0@": "T2",
    b"8.2@": "D2",
    b"11.4@": "S7",
    b"10.0@": "T17",
    b"4.6@": "D5",
    b"8.0@": "25",
    b"4.0@": "BULL",
}


def service_info(
    address: str = ADDRESS, name: str = "GRANBOARD", uuids: list[str] | None = None
) -> BluetoothServiceInfoBleak:
    device = SimpleNamespace(address=address, name=name)
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[SERVICE_UUID.upper()] if uuids is None else uuids,
        source="local",
        device=device,
        advertisement=None,
        connectable=True,
        time=0,
        tx_power=None,
    )


class FakeClient:
    """A Bleak client of a Granboard: its service with a characteristic to write
    the lights and one that notifies the hits."""

    def __init__(self, notify: bool = True) -> None:
        properties = ["notify"] if notify else ["read"]
        self.characteristic = SimpleNamespace(properties=properties)
        service = SimpleNamespace(
            characteristics=[SimpleNamespace(properties=["write"]), self.characteristic]
        )
        self.services = SimpleNamespace(
            get_service=lambda uuid: service if uuid == SERVICE_UUID else None
        )
        self.notified = None
        self.disconnects = 0

    async def start_notify(self, characteristic, notified) -> None:
        assert characteristic is self.characteristic
        self.notified = notified

    async def disconnect(self) -> None:
        self.disconnects += 1


class FakeBluetooth:
    """Home Assistant's Bluetooth as GranboardLink uses it."""

    def __init__(self, hass) -> None:
        hass.config.components.add("bluetooth")
        self.device: object | None = SimpleNamespace(address=ADDRESS)
        self.seen = None
        self.clients: list[FakeClient] = []
        self.failures: list[BaseException] = []
        self.calls: list[dict] = []
        self.unregistered = 0

    def ble_device(self, hass, address, connectable=True):
        assert address == ADDRESS and connectable
        return self.device

    def register(self, hass, seen, matcher, mode):
        assert matcher["address"] == ADDRESS
        self.seen = seen

        def unregister() -> None:
            self.unregistered += 1

        return unregister

    async def connect(self, client_class, device, name, **kwargs):
        self.calls.append({"device": device, "name": name, **kwargs})
        if self.failures:
            raise self.failures.pop(0)
        client = FakeClient()
        self.clients.append(client)
        return client

    @property
    def client(self) -> FakeClient:
        return self.clients[-1]


@pytest.fixture
def ble(hass):
    fake = FakeBluetooth(hass)
    with (
        patch.object(
            granboard.bluetooth, "async_ble_device_from_address", fake.ble_device
        ),
        patch.object(granboard.bluetooth, "async_register_callback", fake.register),
        patch.object(granboard, "establish_connection", fake.connect),
    ):
        yield fake


async def setup_granboard(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        unique_id=BOARD_ID,
        title="Autodarts (Granboard)",
        data=DATA,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def later(hass, seconds: float) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def connected(hass, ble) -> MockConfigEntry:
    """A Granboard set up, connected, and past its warm-up."""
    entry = await setup_granboard(hass)
    assert ble.clients
    await later(hass, WARM_UP_SECONDS + 0.1)
    return entry


async def notify(hass, client: FakeClient, *frames: bytes) -> None:
    for frame in frames:
        client.notified(client.characteristic, bytearray(frame))
    await hass.async_block_till_done()


def visit(entry) -> list[str]:
    return [dart["name"] for dart in entry.runtime_data.local.games.training.visit()]


def connectivity(hass) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", "homedarts", f"{BOARD_ID}_granboard_connected"
    )
    assert entity_id is not None
    return hass.states.get(entity_id).state


async def link_diagnostics(hass, entry) -> dict:
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    return diagnostics["connection"]["granboard"]


# -- the frames ----------------------------------------------------------------


def test_every_bed_of_the_board_has_one_frame():
    beds = [hit.bed for hit in FRAMES.values()]
    # Two singles per number, the inner and the outer one.
    assert len(FRAMES) == 20 * 4 + 2 + 1
    expected = sorted(
        [f"{ring}{number}" for number in range(1, 21) for ring in ("S", "S", "T", "D")]
        + ["25", "BULL", BUTTON]
    )
    assert sorted(beds) == expected
    for hit in FRAMES.values():
        assert hit.bed == BUTTON or parse_bed(hit.bed)["name"] == hit.bed
    # The inner and the outer single of a number tell themselves apart.
    singles = [hit for hit in FRAMES.values() if hit.bed == "S20"]
    assert sorted(hit.inner for hit in singles) == [False, True]
    assert all(
        hit.inner is None for hit in FRAMES.values() if not hit.bed.startswith("S")
    )


@pytest.mark.parametrize(("frame", "bed"), RECORDED.items())
def test_recorded_frames_name_their_beds(frame, bed):
    (text,) = FrameReader().feed(frame)
    assert FRAMES[text].bed == bed


def test_the_button_frame():
    assert FrameReader().feed(b"BTN@") == [BUTTON]
    assert FRAMES[BUTTON] == Hit(BUTTON)


def test_frames_split_or_joined_by_notifications_stay_whole():
    reader = FrameReader()
    assert reader.feed(b"3.") == []
    assert reader.feed(bytearray(b"4@8.0@4")) == ["3.4", "8.0"]
    assert reader.feed(b".0@") == ["4.0"]
    # Padding and empty frames are no frames.
    assert reader.feed(b"\x00BTN\r\n@@ @") == [BUTTON]


def test_noise_without_an_end_is_dropped():
    reader = FrameReader()
    assert reader.feed(b"x" * 17) == []
    assert reader.feed(b"3.4@") == ["3.4"]
    assert reader.feed(b"\xff\xfe@") == ["��"]


def test_the_board_id_is_the_address_without_separators():
    assert granboard.board_id(ADDRESS) == BOARD_ID
    # The addresses of macOS are UUIDs.
    assert (
        granboard.board_id("0F2E6C1A-1B2C-4D5E-8F90-0123456789AB")
        == "granboard_0f2e6c1a1b2c4d5e8f900123456789ab"
    )


async def test_the_granboards_that_bluetooth_sees(hass):
    found = [service_info(), service_info("AA:BB:CC:DD:EE:02", "Other", ["180f"])]
    with patch.object(
        granboard.bluetooth, "async_discovered_service_info", return_value=found
    ) as discovered:
        # Without Home Assistant's Bluetooth, nothing is asked.
        assert granboard.async_discovered(hass) == []
        discovered.assert_not_called()
        hass.config.components.add("bluetooth")
        assert granboard.async_discovered(hass) == found[:1]
    discovered.assert_called_once_with(hass, connectable=True)


# -- the setup -----------------------------------------------------------------


async def test_a_discovered_granboard_is_set_up_as_a_dartboard(hass):
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "granboard_confirm"
    assert result["description_placeholders"] == {"address": ADDRESS}
    flow = hass.config_entries.flow.async_progress()[0]
    assert flow["context"]["title_placeholders"] == {"name": "GRANBOARD"}
    with patch.object(granboard.GranboardLink, "async_start"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": " Pub "}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pub"
    entry = result["result"]
    assert entry.unique_id == BOARD_ID
    assert entry.data == {**DATA, "name": "Pub"}
    # The same board, found again, is set up already.
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_a_granboard_is_chosen_from_those_bluetooth_sees(hass):
    configured = MockConfigEntry(
        domain="homedarts",
        version=2,
        unique_id=granboard.board_id("AA:BB:CC:DD:EE:09"),
        data={**DATA, "granboard": "AA:BB:CC:DD:EE:09"},
    )
    configured.add_to_hass(hass)
    seen = [service_info(), service_info("AA:BB:CC:DD:EE:09")]
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_USER}
    )
    assert "granboard" in result["menu_options"]
    with patch.object(granboard, "async_discovered", return_value=seen):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "granboard"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "granboard"
    # A board that is set up already is not offered again.
    schema = result["data_schema"].schema
    (field,) = schema
    assert schema[field].container == {ADDRESS: f"GRANBOARD ({ADDRESS})"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": ADDRESS}
    )
    assert result["step_id"] == "granboard_confirm"
    with patch.object(granboard.GranboardLink, "async_start"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "Granboard"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == DATA


async def test_a_granboard_set_up_meanwhile_is_not_set_up_twice(hass):
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_USER}
    )
    with patch.object(granboard, "async_discovered", return_value=[service_info()]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "granboard"}
        )
    MockConfigEntry(
        domain="homedarts", version=2, unique_id=BOARD_ID, data=DATA
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"address": ADDRESS}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_granboard_in_reach(hass):
    result = await hass.config_entries.flow.async_init(
        "homedarts", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "granboard"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_granboards"


# -- the darts -----------------------------------------------------------------


async def test_the_darts_of_the_board_are_entered_in_order(hass, ble):
    entry = await connected(hass, ble)
    call = ble.calls[0]
    assert call["name"] == "Granboard"
    assert connectivity(hass) == "on"
    await notify(hass, ble.client, b"3.4@", b"3.3@3.", b"6@")
    assert visit(entry) == ["T20", "S20", "D20"]
    # A fourth dart does not fit the visit, and the button passes it on.
    await notify(hass, ble.client, b"8.0@", b"BTN@")
    assert visit(entry) == []
    darts = er.async_get(hass).async_get_entity_id(
        "sensor", "homedarts", f"{BOARD_ID}_training_darts"
    )
    assert hass.states.get(darts).state == "3"
    await notify(hass, ble.client, b"4.0@", b"7.7@")
    assert visit(entry) == ["BULL"]
    stats = await link_diagnostics(hass, entry)
    assert stats == {
        "connected": True,
        "away": False,
        "connections": 1,
        "disconnects": 0,
        "failures": 0,
        "frames": 7,
        "darts": 5,
        "buttons": 1,
        "refused": 1,
        "warm_up": 0,
        "last_error": None,
        "unknown_frames": ["7.7"],
    }
    # The device of the dartboard is the Granboard.
    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert device.model == "Granboard"
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["entry"]["data"]["granboard"] == "**REDACTED**"


async def test_a_dart_the_board_repeats_as_it_connects_does_not_count(hass, ble):
    entry = await setup_granboard(hass)
    await notify(hass, ble.client, b"3.4@")
    assert visit(entry) == []
    await later(hass, WARM_UP_SECONDS + 0.1)
    await notify(hass, ble.client, b"3.4@")
    assert visit(entry) == ["T20"]
    assert (await link_diagnostics(hass, entry))["warm_up"] == 1


async def test_the_button_without_darts_while_no_pass_is_allowed(hass, ble):
    entry = await connected(hass, ble)
    await notify(hass, ble.client, b"BTN@")
    stats = await link_diagnostics(hass, entry)
    assert (stats["buttons"], stats["refused"]) == (1, 1)


# -- the connection --------------------------------------------------------------


async def test_a_board_that_disconnects_connects_again(hass, ble):
    entry = await connected(hass, ble)
    first = ble.client
    disconnected = ble.calls[0]["disconnected_callback"]
    # A device the Bluetooth sees no longer stays the one connected.
    ble.device = None
    assert ble.calls[0]["ble_device_callback"]() is ble.calls[0]["device"]
    ble.device = SimpleNamespace(address=ADDRESS)
    assert ble.calls[0]["ble_device_callback"]() is ble.device
    # A client that never connected is no disconnection.
    disconnected(FakeClient())
    assert connectivity(hass) == "on"
    disconnected(first)
    await hass.async_block_till_done()
    assert connectivity(hass) == "off"
    await later(hass, 2.1)
    assert len(ble.clients) == 2
    assert connectivity(hass) == "on"
    stats = await link_diagnostics(hass, entry)
    assert (stats["connections"], stats["disconnects"]) == (2, 1)
    # Disconnected during the warm-up, then the darts of the new connection count.
    ble.calls[1]["disconnected_callback"](ble.client)
    await later(hass, 2.1)
    await later(hass, WARM_UP_SECONDS + 0.1)
    await notify(hass, ble.client, b"3.4@")
    assert visit(entry) == ["T20"]


async def test_failed_attempts_wait_longer_up_to_five_minutes(hass, ble):
    ble.failures = [BleakError("out of slots"), TimeoutError()] + [
        BleakError("no answer")
    ] * 8
    waits = []
    call_later = granboard.async_call_later

    def recorded(hass, delay, action):
        waits.append(delay)
        return call_later(hass, delay, action)

    with patch.object(granboard, "async_call_later", recorded):
        entry = await setup_granboard(hass)
        assert connectivity(hass) == "off"
        for attempt in range(2, 11):
            await later(hass, waits[-1] + 1)
            assert len(ble.calls) == attempt
        await later(hass, waits[-1] + 1)
    # Each failed attempt doubles the wait, up to five minutes; the warm-up of
    # the connection that came last is two seconds.
    assert waits == [2, 4, 8, 16, 32, 64, 128, 256, 300, 300, WARM_UP_SECONDS]
    assert RETRY_MAX_SECONDS == 300
    stats = await link_diagnostics(hass, entry)
    assert (stats["failures"], stats["last_error"]) == (10, "BleakError")
    assert stats["connections"] == 1
    assert connectivity(hass) == "on"


async def test_a_board_out_of_reach_connects_when_bluetooth_sees_it(hass, ble):
    ble.device = None
    entry = await setup_granboard(hass)
    assert ble.calls == []
    assert (await link_diagnostics(hass, entry))["away"] is True
    ble.device = SimpleNamespace(address=ADDRESS)
    ble.seen(service_info(), None)
    await hass.async_block_till_done()
    assert len(ble.calls) == 1
    assert connectivity(hass) == "on"
    # Seen again while connected, nothing changes.
    ble.seen(service_info(), None)
    await hass.async_block_till_done()
    assert len(ble.calls) == 1
    # The timer of the attempt it took the place of is gone.
    await later(hass, 10)
    assert len(ble.calls) == 1


async def test_a_board_seen_while_it_fails_waits_for_its_turn(hass, ble):
    ble.failures = [BleakError("busy")]
    await setup_granboard(hass)
    ble.seen(service_info(), None)
    await hass.async_block_till_done()
    assert len(ble.calls) == 1
    await later(hass, 2.1)
    assert len(ble.calls) == 2


async def test_a_board_without_the_notify_characteristic(hass, ble):
    client = FakeClient(notify=False)

    async def connect(client_class, device, name, **kwargs):
        ble.calls.append(kwargs)
        return client

    with patch.object(granboard, "establish_connection", connect):
        entry = await setup_granboard(hass)
    assert client.disconnects == 1
    stats = await link_diagnostics(hass, entry)
    assert (stats["failures"], stats["last_error"]) == (1, "BleakError")


async def test_a_board_without_the_service(hass, ble):
    client = FakeClient()
    client.services = SimpleNamespace(get_service=lambda uuid: None)

    async def connect(client_class, device, name, **kwargs):
        return client

    with patch.object(granboard, "establish_connection", connect):
        entry = await setup_granboard(hass)
    assert (await link_diagnostics(hass, entry))["failures"] == 1


class StuckClient(FakeClient):
    """A client whose proxy is gone: it cannot even disconnect."""

    async def start_notify(self, characteristic, notified) -> None:
        raise BleakError("proxy gone")

    async def disconnect(self) -> None:
        self.disconnects += 1
        raise BleakError("proxy gone")


async def test_a_board_that_cannot_disconnect_is_tried_again(hass, ble):
    clients = [StuckClient()]

    async def connect(client_class, device, name, **kwargs):
        ble.calls.append(kwargs)
        return clients.pop(0) if clients else FakeClient()

    with patch.object(granboard, "establish_connection", connect):
        entry = await setup_granboard(hass)
        stats = await link_diagnostics(hass, entry)
        assert (stats["failures"], stats["last_error"]) == (1, "BleakError")
        await later(hass, 2.1)
    assert len(ble.calls) == 2
    assert connectivity(hass) == "on"


async def test_unloading_a_board_that_cannot_disconnect(hass, ble):
    entry = await connected(hass, ble)
    client = ble.client

    async def disconnect() -> None:
        client.disconnects += 1
        raise TimeoutError

    client.disconnect = disconnect
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert client.disconnects == 1
    assert ble.unregistered == 1


async def test_a_frame_cut_off_by_a_disconnect_is_dropped(hass, ble):
    entry = await connected(hass, ble)
    # Half a frame, then the board goes.
    await notify(hass, ble.client, b"3.")
    ble.calls[0]["disconnected_callback"](ble.client)
    await later(hass, 2.1)
    await later(hass, WARM_UP_SECONDS + 0.1)
    await notify(hass, ble.client, b"3.4@")
    assert visit(entry) == ["T20"]
    assert (await link_diagnostics(hass, entry))["unknown_frames"] == []


async def test_unloading_lets_the_board_go(hass, ble):
    entry = await connected(hass, ble)
    client = ble.client
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert client.disconnects == 1
    assert ble.unregistered == 1
    # The board's goodbye is no disconnection to recover from.
    ble.calls[0]["disconnected_callback"](client)
    await later(hass, RETRY_MAX_SECONDS)
    assert len(ble.calls) == 1


async def test_stopped_while_failing_to_connect(hass, ble):
    gate = asyncio.Event()

    async def connect(client_class, device, name, **kwargs):
        ble.calls.append(kwargs)
        await gate.wait()
        raise BleakError("gone")

    with patch.object(granboard, "establish_connection", connect):
        entry = await setup_granboard(hass)
        await entry.runtime_data.local.granboard.async_stop()
        gate.set()
        await hass.async_block_till_done()
        # A stopped link tries no more.
        await later(hass, RETRY_MAX_SECONDS)
    assert len(ble.calls) == 1


async def test_stopped_while_connecting(hass, ble):
    client = FakeClient()
    gate = asyncio.Event()

    async def connect(client_class, device, name, **kwargs):
        await gate.wait()
        return client

    with patch.object(granboard, "establish_connection", connect):
        entry = await setup_granboard(hass)
        link = entry.runtime_data.local.granboard
        await link.async_stop()
        # The board answers once the link was stopped, and is let go at once.
        gate.set()
        await hass.async_block_till_done()
    assert client.disconnects == 1
    assert not link.connected


async def test_unloading_a_board_that_never_connected(hass, ble):
    ble.failures = [BleakError("busy")]
    entry = await setup_granboard(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await later(hass, RETRY_MAX_SECONDS)
    assert len(ble.calls) == 1


async def test_without_home_assistant_s_bluetooth(hass, caplog):
    with patch.object(granboard, "establish_connection") as connect:
        entry = await setup_granboard(hass)
    connect.assert_not_called()
    assert "Bluetooth is not set up" in caplog.text
    assert connectivity(hass) == "off"
    # The darts are still entered on the keypad.
    await hass.services.async_call(
        "homedarts", "throw_dart", {"segment": "T20"}, blocking=True
    )
    assert visit(entry) == ["T20"]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_a_dartboard_without_a_granboard_has_no_link(hass):
    entry = MockConfigEntry(
        domain="homedarts",
        version=2,
        unique_id="manual_0123",
        data={key: value for key, value in DATA.items() if key != "granboard"}
        | {"board_id": "manual_0123"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.local.granboard is None
    assert entry.runtime_data.local.device_model == "Dart Board"
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["connection"] == {"manual_board": True}
    assert (
        er.async_get(hass).async_get_entity_id(
            "binary_sensor", "homedarts", "manual_0123_granboard_connected"
        )
        is None
    )


async def test_an_autodarts_board_takes_the_place_of_the_granboard(
    hass, ble, aioclient_mock
):
    entry = await connected(hass, ble)
    result = await hass.config_entries.flow.async_init(
        "homedarts",
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "local"}
    )
    mock_board(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.0.2.10", "port": 3180}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "board_connected"
    assert "granboard" not in entry.data
    assert "manual_board" not in entry.data
    assert ble.client.disconnects == 1
    # The board's detection has no Granboard, so no sensor of one is left behind.
    entities = er.async_get(hass)
    assert (
        entities.async_get_entity_id(
            "binary_sensor",
            "homedarts",
            f"{entry.data['board_id']}_granboard_connected",
        )
        is None
    )
    assert (
        entities.async_get_entity_id(
            "binary_sensor", "homedarts", f"{BOARD_ID}_granboard_connected"
        )
        is None
    )
