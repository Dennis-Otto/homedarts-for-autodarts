"""Check the local HTTP protocol, safe partial writes and command failures."""

from unittest.mock import Mock, patch

import aiohttp
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.homedarts.errors import AutodartsConnectionError
from custom_components.homedarts.local_api import (
    AutodartsLocalClient,
    AutodartsLocalCommandError,
)

from .local_helpers import BASE, STATE, mock_board, recorded


async def test_read_real_response_shapes_and_discard_secrets(client, aioclient_mock):
    mock_board(aioclient_mock)
    assert await client.get_state() == STATE
    assert await client.get_version() == "1.0.7"
    assert await client.get_config() == {
        "board_id": "board-1",
        "camera_count": 3,
        "auto_calibrate_on_start": True,
        "auto_calibrate": True,
        "auto_distortion": False,
        "standby_minutes": 15,
    }
    assert await client.get_stats() == {"fps": 12.5}
    assert await client.get_camera_stats() == {"fps": [29.9, 30, 29.8]}
    assert "private-board-api-key" not in repr(vars(client))


@pytest.mark.parametrize(
    "command,method,path",
    [
        ("start", "PUT", "/api/start"),
        ("stop", "PUT", "/api/stop"),
        ("reset", "POST", "/api/reset"),
        ("restart", "POST", "/api/restart"),
        ("calibrate", "POST", "/api/config/calibration/auto"),
        ("connect", "PUT", "/api/upstream/connect"),
        ("disconnect", "PUT", "/api/upstream/disconnect"),
        ("start_streams", "PUT", "/api/streams/start"),
        ("stop_streams", "PUT", "/api/streams/stop"),
    ],
)
async def test_commands_accept_empty_response(
    client, aioclient_mock, command, method, path
):
    getattr(aioclient_mock, method.lower())(BASE + path, status=204)
    await client.command(command)
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][0] == method
    assert str(aioclient_mock.mock_calls[0][1]) == BASE + path


@pytest.mark.parametrize("status", [404, 405])
@pytest.mark.parametrize("command", ["start", "stop"])
async def test_old_detection_route_fallback(client, aioclient_mock, status, command):
    aioclient_mock.put(f"{BASE}/api/{command}", status=status)
    aioclient_mock.put(f"{BASE}/api/detection/{command}", status=204)
    await client.command(command)
    assert len(aioclient_mock.mock_calls) == 2


@pytest.mark.parametrize("status", [401, 409, 500, 503])
async def test_rejected_command_not_retried(client, aioclient_mock, status):
    aioclient_mock.put(f"{BASE}/api/start", status=status, text="private response")
    with pytest.raises(AutodartsLocalCommandError, match=f"HTTP {status}") as error:
        await client.command("start")
    assert "private response" not in str(error.value)
    assert len(aioclient_mock.mock_calls) == 1


async def test_timeout_does_not_duplicate_command(client):
    with patch.object(client._session, "request", side_effect=TimeoutError) as request:
        with pytest.raises(AutodartsConnectionError):
            await client.command("start")
    assert request.call_count == 1


async def test_setting_changes_only_patch_requested_fields(client, aioclient_mock):
    aioclient_mock.get(f"{BASE}/api/config", json=recorded("2.0.2", "config.json"))
    aioclient_mock.patch(f"{BASE}/api/config", json={"auth": {"api_key": "private"}})
    await client.set_config_switch("auto_calibrate", False)
    await client.set_standby_minutes(30)
    assert [call[2] for call in aioclient_mock.mock_calls if call[0] == "PATCH"] == [
        {"cam": {"auto_calibrate": False}},
        {"motion": {"standby_minutes": 30}},
    ]
    calls = len(aioclient_mock.mock_calls)
    with pytest.raises(ValueError):
        await client.set_config_switch("api_key", True)
    with pytest.raises(ValueError):
        await client.set_standby_minutes(0)
    assert len(aioclient_mock.mock_calls) == calls


@pytest.mark.parametrize("body", [[], {}, {"running": "false"}])
async def test_non_board_response_rejected(client, aioclient_mock, body):
    aioclient_mock.get(f"{BASE}/api/state", json=body)
    with pytest.raises(AutodartsConnectionError):
        await client.get_state()


async def test_camera_snapshot_is_read_only(client, aioclient_mock):
    aioclient_mock.get(
        f"{BASE}/api/img/cams/1",
        content=b"jpeg",
        headers={"Content-Type": "image/jpeg"},
    )
    assert await client.get_camera_image(1) == b"jpeg"
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][0] == "GET"


async def test_stopped_camera_html_response_is_not_an_image(client, aioclient_mock):
    aioclient_mock.get(f"{BASE}/api/img/cams/0", text="<html>unavailable</html>")
    with pytest.raises(AutodartsConnectionError, match="No camera image"):
        await client.get_camera_image(0)


async def test_ipv6_url(hass):
    client = AutodartsLocalClient("2001:db8::1", 3180, async_get_clientsession(hass))
    assert client.base_url == "http://[2001:db8::1]:3180"


@pytest.mark.parametrize(
    "error",
    [aiohttp.ServerDisconnectedError(), aiohttp.ClientOSError(104, "reset by peer")],
)
async def test_restart_that_drops_the_connection_succeeds(
    client, aioclient_mock, error
):
    aioclient_mock.post(f"{BASE}/api/restart", exc=error)
    await client.command("restart")
    assert len(aioclient_mock.mock_calls) == 1


async def test_unreachable_board_cannot_restart(client, aioclient_mock):
    aioclient_mock.post(
        f"{BASE}/api/restart",
        exc=aiohttp.ClientConnectorError(Mock(), OSError(111, "refused")),
    )
    with pytest.raises(AutodartsConnectionError):
        await client.command("restart")


async def test_other_commands_still_report_a_dropped_connection(client, aioclient_mock):
    aioclient_mock.put(f"{BASE}/api/start", exc=aiohttp.ServerDisconnectedError())
    with pytest.raises(AutodartsConnectionError):
        await client.command("start")


async def test_requests_after_home_assistant_closed_its_session_are_lost_connections():
    """Home Assistant closes its shared session last when it stops (#107)."""
    session = aiohttp.ClientSession()
    await session.close()
    client = AutodartsLocalClient("192.0.2.10", 3180, session)
    with pytest.raises(AutodartsConnectionError, match="closed its HTTP session"):
        await client.get_state()
    with pytest.raises(AutodartsConnectionError, match="closed its HTTP session"):
        await client.open_camera_stream(1)
