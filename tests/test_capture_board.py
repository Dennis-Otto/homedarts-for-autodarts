"""scripts/capture_board.py records what a Board Manager answers for
tests/fixtures/board_manager. It replaces the identity and the secrets of the board
and the addresses of its network by placeholders before it writes anything, and
writes nothing that still holds one. tests/test_board_contract.py records the double
of the end-to-end test with it."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "capture_board", ROOT / "scripts" / "capture_board.py"
)
capture_board = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture_board)
PLACEHOLDERS = capture_board.PLACEHOLDERS

# What a real board answers with: its ID, its keys, a token of a later version and
# the name and addresses of the board PC in its home network.
BOARD_ID = "5f0c2d8e-3b1a-4c6f-9e2d-7a8b9c0d1e2f"
API_KEY = "a1b2c3d4e5f6-board-api-key"
TLS_KEY = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg\n-----END PRIVATE KEY-----\n"
TLS_CERT = "-----BEGIN CERTIFICATE-----\nMIIC2jCCAcKgAw\n-----END CERTIFICATE-----\n"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.refresh"
HOSTNAME = "living-room-pc"
ADDRESS = "192.168.178.23"
SECRETS = (BOARD_ID, API_KEY, TLS_KEY, TLS_CERT, TOKEN, HOSTNAME, ADDRESS)


def answers():
    return {
        "version.txt": "v2.0.3\n",
        "config.json": {
            "auth": {"board_id": BOARD_ID, "api_key": API_KEY},
            "cam": {"cams": ["/dev/video0"]},
        },
        "system.json": {
            "config": {
                "host": {"port": "3180", "tls_key": TLS_KEY, "tls_cert": TLS_CERT}
            },
            "link": f"wss://api.autodarts.io/boards/{BOARD_ID}",
            "log": f"Listening on {ADDRESS}:3180 and 10.8.0.2, OpenCV 4.12.0.88",
            "cloud": {"refreshToken": TOKEN, "pin": "1234"},
            "legacy": {"api_key": "abc"},
            "note": "the abcde of darts",
            "docs": "192.0.2.10",
        },
        "host.json": {"hostname": HOSTNAME, "ip": ADDRESS, "model": "", "cpu2": None},
    }


FRAMES = [{"type": "state", "data": {"board": BOARD_ID, "from": f"{HOSTNAME}.lan"}}]

# What Board Manager 2.1 answers in place of that, with its keys in camelCase and
# the serial numbers of the cameras, the name of its link server and the name of the
# device it streams to. tests/fixtures/board_manager keeps none of these values.
SERIALS = ("A1B2C3D4E5", "F6A7B8C9D0", "E1F2A3B4C5")
LINK_SERVER = "kellerbar-board"
STREAMING_TO = "kitchen-tablet"
SECRETS_2_1 = (*SECRETS, *SERIALS, LINK_SERVER, STREAMING_TO)


def camera(port: int, serial: str) -> str:
    return (
        f"vid=1dfc&pid=8513&serial={serial}&location=pci-0000:00:14.0-usb-0:{port}:1.0"
    )


def answers_2_1():
    config = {
        "auth": {"apiKey": API_KEY, "boardId": BOARD_ID},
        "cam": {
            "autoCalibrateOnStart": False,
            "cams": [camera(port, serial) for port, serial in zip((3, 4, 8), SERIALS)],
        },
        "host": {"port": "3180", "tlsCert": TLS_CERT, "tlsKey": TLS_KEY, "tlsPort": ""},
        "linkServer": {"enabled": True, "interfaces": [ADDRESS], "name": LINK_SERVER},
    }
    return {
        "version.txt": "2.1.0\n",
        "config.json": config,
        "system.json": {
            "camStats": [{"fps": 30, "height": 1024, "id": 0, "width": 1280}],
            "config": config,
            "status": {
                "link": "connected",
                "linkServer": {
                    "error": f"board {BOARD_ID} lost camera {SERIALS[0]}",
                    "interfaces": [ADDRESS],
                    "streamingTo": STREAMING_TO,
                },
                "version": "2.1.0",
            },
            "vantage": {"motion": {"camStates": [{"camId": 0, "isHand": False}]}},
        },
        "host.json": {
            "cam1": {"name": "USB Camera", "pid": "8513", "vid": "1dfc"},
            "cpu": {"cores": 4, "model": "Intel(R) Core(TM) i3-9100T CPU @ 3.10GHz"},
            "hostname": HOSTNAME,
            "ip": ADDRESS,
        },
    }


FRAMES_2_1 = [{"type": "state", "data": {"board": BOARD_ID, "event": "throwDetected"}}]


def written(content: dict[str, str]) -> dict:
    return {
        name: text if name.endswith(".txt") else json.loads(text)
        for name, text in content.items()
        if name != capture_board.FRAMES
    }


def test_a_recording_says_placeholders_instead_of_the_secrets_of_the_board():
    version, content = capture_board.files(
        answers(), FRAMES, ["/api/state/motion"], ADDRESS, "2026-10-18"
    )

    assert version == "2.0.3"
    files = written(content)
    assert files["version.txt"] == "v2.0.3\n"
    assert files["config.json"]["auth"] == {
        "board_id": PLACEHOLDERS["board_id"],
        "api_key": PLACEHOLDERS["api_key"],
    }
    system = files["system.json"]
    assert system["config"]["host"] == {
        "port": "3180",
        "tls_key": PLACEHOLDERS["tls_key"],
        "tls_cert": PLACEHOLDERS["tls_cert"],
    }
    # Wherever the board names them, and also secrets of keys it doesn't have yet.
    assert system["link"] == "wss://api.autodarts.io/boards/board-1"
    assert system["log"] == (
        "Listening on 198.51.100.7:3180 and 198.51.100.7, OpenCV 4.12.0.88"
    )
    assert system["cloud"] == {"refreshToken": "private-refreshToken", "pin": "1234"}
    # A short secret only at its key, so that it can't change other texts.
    assert system["legacy"] == {"api_key": PLACEHOLDERS["api_key"]}
    assert system["note"] == "the abcde of darts"
    # Addresses for documentation stay, such as those of the placeholders.
    assert system["docs"] == "192.0.2.10"
    assert files["host.json"] == {
        "hostname": PLACEHOLDERS["hostname"],
        "ip": PLACEHOLDERS["ip"],
        "model": "",
        "cpu2": None,
    }
    assert content[capture_board.FRAMES] == (
        '{"type":"state","data":{"board":"board-1","from":"dartboard-pc.lan"}}\n'
    )
    assert files[capture_board.CAPTURE] == {
        "board_manager": "2.0.3",
        "captured": "2026-10-18",
        "source": "scripts/capture_board.py",
        "absent": ["/api/state/motion"],
    }
    for text in content.values():
        assert text.endswith("\n")
        for secret in SECRETS:
            # Neither as it is nor as JSON writes it, such as a key of several lines.
            assert secret not in text
            assert json.dumps(secret)[1:-1] not in text


def test_a_recording_of_board_manager_2_1_says_placeholders_too():
    version, content = capture_board.files(
        answers_2_1(), FRAMES_2_1, ["/api/state/motion"], ADDRESS, "2026-10-31"
    )

    assert version == "2.1.0"
    files = written(content)
    config = files["config.json"]
    assert config["auth"] == {
        "apiKey": PLACEHOLDERS["api_key"],
        "boardId": PLACEHOLDERS["board_id"],
    }
    assert config["host"] == {
        "port": "3180",
        "tlsCert": PLACEHOLDERS["tls_cert"],
        "tlsKey": PLACEHOLDERS["tls_key"],
        "tlsPort": "",
    }
    # The serial number goes; the port keeps three cameras of one model apart.
    assert config["cam"]["cams"] == [
        f"vid=1dfc&pid=8513&serial={PLACEHOLDERS['serial']}"
        f"&location=pci-0000:00:14.0-usb-0:{port}:1.0"
        for port in (3, 4, 8)
    ]
    assert config["linkServer"] == {
        "enabled": True,
        "interfaces": [PLACEHOLDERS["ip"]],
        "name": "private-linkServer-name",
    }
    system = files["system.json"]
    assert system["config"] == config
    assert system["status"]["linkServer"] == {
        "error": f"board board-1 lost camera {PLACEHOLDERS['serial']}",
        "interfaces": [PLACEHOLDERS["ip"]],
        "streamingTo": "private-streamingTo",
    }
    # What the tests of the contract read stays as the board said it.
    assert system["camStats"] == answers_2_1()["system.json"]["camStats"]
    assert system["vantage"] == answers_2_1()["system.json"]["vantage"]
    assert system["status"]["link"] == "connected"
    assert files["host.json"] == {
        **answers_2_1()["host.json"],
        "hostname": PLACEHOLDERS["hostname"],
        "ip": PLACEHOLDERS["ip"],
    }
    assert content[capture_board.FRAMES] == (
        '{"type":"state","data":{"board":"board-1","event":"throwDetected"}}\n'
    )
    for text in content.values():
        for secret in SECRETS_2_1:
            assert secret not in text
            assert json.dumps(secret)[1:-1] not in text


def test_nothing_is_written_that_still_holds_a_secret_of_board_manager_2_1(
    monkeypatch,
):
    monkeypatch.setattr(capture_board, "redact", lambda value, found: value)

    with pytest.raises(SystemExit) as stopped:
        capture_board.files(answers_2_1(), FRAMES_2_1, [], ADDRESS, "2026-10-31")

    # The check finds each of them by itself, not only the one that was found first.
    for what in (
        PLACEHOLDERS["board_id"],
        PLACEHOLDERS["api_key"],
        PLACEHOLDERS["tls_key"],
        PLACEHOLDERS["tls_cert"],
        PLACEHOLDERS["hostname"],
        PLACEHOLDERS["serial"],
        "private-linkServer-name",
        "private-streamingTo",
        "a private IPv4 address",
    ):
        assert what in str(stopped.value)


@pytest.mark.parametrize(
    ("spellings", "name"),
    [
        (("boardId", "board_id", "BoardID", "BOARD_ID", "board-id"), "board_id"),
        (("apiKey", "api_key", "ApiKey", "API_KEY", "api-key"), "api_key"),
        (("tlsKey", "tls_key", "TlsKey", "TLS_KEY", "tls-key"), "tls_key"),
        (("tlsCert", "tls_cert", "TLSCert", "TLS_CERT", "tls-cert"), "tls_cert"),
        (("hostname", "hostName", "host_name", "HOSTNAME"), "hostname"),
        (("ip", "IP", "Ip"), "ip"),
    ],
)
def test_a_key_is_the_same_key_in_every_spelling(spellings, name):
    for key in spellings:
        value = "zq-real-value-of-the-board"
        _, content = capture_board.files(
            {"version.txt": "2.2.0", "config.json": {key: value, "log": f"at {value}"}},
            [],
            [],
            "",
            None,
        )

        assert json.loads(content["config.json"]) == {
            key: PLACEHOLDERS[name],
            "log": f"at {PLACEHOLDERS[name]}",
        }


@pytest.mark.parametrize(
    "key",
    [
        # An ID of the board, of an account or of what belongs to them.
        "accountId",
        "account_id",
        "userId",
        "ownerId",
        "customer_id",
        "playerId",
        "dartboardId",
        "machineId",
        "hardware_id",
        "deviceId",
        "installationId",
        "sessionId",
        "boardUuid",
        "boardIds",
        "uuid",
        "GUID",
        # Names and how to reach someone.
        "boardName",
        "accountName",
        "userName",
        "username",
        "displayName",
        "first_name",
        "surname",
        "computerName",
        "email",
        "emailAddress",
        # What a device and its network go by.
        "serial",
        "serialNumber",
        "serial_no",
        "macAddress",
        # What a person or a host goes by, without "id" or "name".
        "user",
        "owner",
        "account",
        "login",
        "uid",
        "clientId",
        "hostId",
        "systemId",
        "serverName",
        "wifiSsid",
        "ipv6",
        "ipAddress",
        "publicIp",
        "localIpv4",
        "ipAddr",
        "ip_addr",
        "externalIp",
        "clientIp",
        # Secrets, also in the middle of a key and as a list.
        "privateKey",
        "tlsCertificate",
        "accessTokenHash",
        "clientSecretValue",
        "password",
        "passwd",
        "credentials",
        "apiKeys",
    ],
)
def test_a_key_of_a_later_board_manager_is_recognised(key):
    value = "zq-real-value-of-the-board"
    answer = {key: value, "list": {key: [value, value]}, "log": f"at {value}"}

    _, content = capture_board.files(
        {"version.txt": "2.2.0", "config.json": answer}, [], [], "", None
    )

    assert value not in content["config.json"]
    assert set(json.loads(content["config.json"])) == {key, "list", "log"}


@pytest.mark.parametrize(
    ("answer", "placeholder"),
    [
        ({"account": {"id": "zq-real-value"}}, "private-account"),
        ({"board": {"id": "zq-real-value"}}, PLACEHOLDERS["board_id"]),
        ({"boards": [{"id": "zq-real-value"}]}, "private-boards-id"),
        ({"user": {"name": "zq-real-value"}}, "private-user"),
        ({"linkServer": {"name": "zq-real-value"}}, "private-linkServer-name"),
        ({"link_server": {"name": "zq-real-value"}}, "private-link_server-name"),
        ({"token": {"value": "zq-real-value"}}, "private-token"),
        ({"credentials": [{"login": "zq-real-value"}]}, "private-credentials"),
    ],
)
def test_a_value_is_judged_by_the_key_above_it_where_its_own_says_little(
    answer, placeholder
):
    _, content = capture_board.files(
        {"version.txt": "2.2.0", "config.json": answer}, [], [], "", None
    )

    assert "zq-real-value" not in content["config.json"]
    assert placeholder in content["config.json"]


@pytest.mark.parametrize("key", ["boardId", "accountId", "user_id"])
def test_a_number_can_be_an_id_too(key):
    number = 48151623
    _, content = capture_board.files(
        {
            "version.txt": "2.2.0",
            "config.json": {
                key: number,
                "link": f"https://boards.example/{number}/live",
                "log": f"lost board {number}.",
                "url": f"{number}.boards.example",
                "serial": "000000",
                "fps": [29.0000005],
                "homography": [1.0000000000000002, 148151623.5],
            },
        },
        [],
        [],
        "",
        None,
    )

    config = json.loads(content["config.json"])
    assert config[key] == capture_board.placeholder(key)
    assert str(number) not in config["link"]
    assert str(number) not in config["log"]
    assert str(number) not in config["url"]
    # The digits of an ID or a serial number inside other numbers are no leftover.
    assert config["fps"] == [29.0000005]
    assert config["homography"] == [1.0000000000000002, 148151623.5]


def test_what_says_nothing_about_a_person_or_a_device_stays():
    answer = {
        # The index of a camera, of a dart or of a route is no identity.
        "camStats": [{"fps": 30, "id": 0, "width": 1280}],
        "camStates": [{"camId": 2, "isHand": False}],
        "deviceId": 1,
        "id": "throw-17",
        "name": "kept",
        "isBoard": True,
        "boardId": True,
        "cam1": {"name": "USB Camera", "pid": "8513", "vid": "1dfc"},
        "cpu": {"model": "Intel(R) Core(TM) i3-9100T CPU @ 3.10GHz"},
        # The words of the state and the settings of 2.1.
        "segmentName": "S3",
        "method": "UnanimousCam",
        "clientVersion": "2.1.0",
        "tlsPort": "",
        "zip": "kept",
        "clip": "kept",
        "pin": "1234",
        # Texts that look a little like an address or an ID.
        "kernelVersion": "6.12.107+deb13-amd64",
        "location": "pci-0000:00:14.0-usb-0:3:1.0",
        "time": "12:30:45",
        "symbol": "cv::Mat and ad::fade",
        "loopback": "::1 and ::",
        "docs": "2001:db8::1",
        "multicast": "ff02::1",
        "url": "wss://api.autodarts.io/ws",
        "note": "serial= and darts@home",
        "date": "2026-10-31T12:00:00Z",
        # Network interfaces whose names hold no MAC address.
        "interfaces": "eth0 enp3s0 wlp2s0 enx12345 renx00e04c680001 enx00e04c6800019",
        # A camera as a model, without the instance of one on one PC.
        "driver": r"USB\VID_1DFC&PID_8513&REV_0100&MI_00",
        "model": "vid_1dfc&pid_8513",
    }

    _, content = capture_board.files(
        {"version.txt": "2.1.0", "config.json": answer}, [], [], "", None
    )

    assert json.loads(content["config.json"]) == answer


@pytest.mark.parametrize(
    ("text", "replaced", "what"),
    [
        (
            "ref 5f0c2d8e-3b1a-4c6f-9e2d-7a8b9c0d1e2f.",
            f"ref {PLACEHOLDERS['uuid']}.",
            "a UUID",
        ),
        (
            "ref {5F0C2D8E-3B1A-4C6F-9E2D-7A8B9C0D1E2F}",
            "ref {" + PLACEHOLDERS["uuid"] + "}",
            "a UUID",
        ),
        (
            "wss://example.org/board-5f0c2d8e-3b1a-4c6f-9e2d-7a8b9c0d1e2f-live",
            f"wss://example.org/board-{PLACEHOLDERS['uuid']}-live",
            "a UUID",
        ),
        (
            "signed in as jane.doe+darts@mail.example.org",
            f"signed in as {PLACEHOLDERS['email']}",
            "an e-mail address",
        ),
        ("eth0 a4:b1:c2:d3:e4:f5", f"eth0 {PLACEHOLDERS['mac']}", "a MAC address"),
        ("eth0 A4-B1-C2-D3-E4-F5", f"eth0 {PLACEHOLDERS['mac']}", "a MAC address"),
        (
            "on fe80::1c2d:3eff:fe4f:5a6b%eth0",
            f"on {PLACEHOLDERS['ipv6']}%eth0",
            "an IPv6 address",
        ),
        ("on 2a02:8070:1234::5", f"on {PLACEHOLDERS['ipv6']}", "an IPv6 address"),
        ("on fd00:1:2:3:4:5:6:7", f"on {PLACEHOLDERS['ipv6']}", "an IPv6 address"),
        (
            "vid=1&serial=XY12&location=1",
            f"vid=1&serial={PLACEHOLDERS['serial']}&location=1",
            "a serial number",
        ),
        (
            "SerialNumber=XY12, port 3",
            f"SerialNumber={PLACEHOLDERS['serial']}, port 3",
            "a serial number",
        ),
        (
            "serial_number=XY12",
            f"serial_number={PLACEHOLDERS['serial']}",
            "a serial number",
        ),
        (
            "vid=1&serial=USB CAM 01&location=1",
            f"vid=1&serial={PLACEHOLDERS['serial']}&location=1",
            "a serial number",
        ),
        (
            "vid=1&serial=USB CAM 01",
            f"vid=1&serial={PLACEHOLDERS['serial']}",
            "a serial number",
        ),
        (
            "vid=1&SerialNumber=USB CAM 01 , port 3",
            f"vid=1&SerialNumber={PLACEHOLDERS['serial']}, port 3",
            "a serial number",
        ),
        # Without the "&" of a description, a serial number ends at a space.
        (
            "serial=XY12 lost",
            f"serial={PLACEHOLDERS['serial']} lost",
            "a serial number",
        ),
        ("link on enx00e04c680001", "link on enx00005e005307", "a MAC address"),
        ("wlx00e04c680001 is up", "wlx00005e005307 is up", "a MAC address"),
        (
            "/sys/class/net/wwx00E04C680001/address",
            "/sys/class/net/wwx00005e005307/address",
            "a MAC address",
        ),
        (
            r"USB\VID_1DFC&PID_8513&MI_00\7&2A1B3C4D&0&0000",
            rf"USB\VID_1DFC&PID_8513&MI_00\{PLACEHOLDERS['serial']}",
            "the instance of a camera",
        ),
        (
            r"USB\VID_1DFC&PID_8513\CAM123456",
            rf"USB\VID_1DFC&PID_8513\{PLACEHOLDERS['serial']}",
            "the instance of a camera",
        ),
        (
            r"\\?\usb#vid_1dfc&pid_8513&mi_00#7&2a1b3c4d&0&0000#{private-uuid}\global",
            rf"\\?\usb#vid_1dfc&pid_8513&mi_00#{PLACEHOLDERS['serial']}"
            r"#{private-uuid}\global",
            "the instance of a camera",
        ),
        (
            r"\\?\usb#vid_1dfc&pid_8513#CAM123456#{private-uuid}\global",
            rf"\\?\usb#vid_1dfc&pid_8513#{PLACEHOLDERS['serial']}"
            r"#{private-uuid}\global",
            "the instance of a camera",
        ),
    ],
)
def test_what_identifies_a_device_or_a_person_goes_under_any_key(text, replaced, what):
    assert capture_board.redact({"note": text}, {}) == {"note": replaced}
    # What it is replaced by counts as no leftover, the value itself does.
    assert capture_board.secrets({"note": replaced}) == {}
    assert capture_board.leftovers(replaced, {}) == []
    assert capture_board.leftovers(text, {}) == [what]


@pytest.mark.parametrize(
    ("text", "what"),
    [
        ("enx00e04c680001", "a MAC address"),
        (r"USB\VID_1DFC&PID_8513&MI_00\7&2A1B3C4D&0&0000", "the instance of a camera"),
        (
            r"\\?\usb#vid_1dfc&pid_8513#CAM123456#{private-uuid}",
            "the instance of a camera",
        ),
        ("vid=1&serial=USB CAM 01", "a serial number"),
    ],
)
def test_nothing_is_written_that_holds_them_as_json_writes_them(text, what):
    assert capture_board.leftovers(json.dumps({"note": text}), {}) == [what]
    answers = {"version.txt": "2.2.0", "config.json": {"note": text}}
    _, content = capture_board.files(answers, [text], [], "", None)
    # Each is replaced, and what stays of it is no leftover.
    assert all(capture_board.leftovers(file, {}) == [] for file in content.values())


@pytest.mark.parametrize(
    ("text", "replaced"),
    [
        ("vid=1&serial=SN12345 lost", f"vid=1&serial={PLACEHOLDERS['serial']}"),
        (
            "opened vid=1&pid=2&serial=SN12345 at port 3",
            f"opened vid=1&pid=2&serial={PLACEHOLDERS['serial']}",
        ),
        ("vid=1&serial=SN12345 ", f"vid=1&serial={PLACEHOLDERS['serial']}"),
        (
            "vid=1&serial=SN12345 &location=1",
            f"vid=1&serial={PLACEHOLDERS['serial']}&location=1",
        ),
        (
            r"cam (USB\VID_1DFC&PID_8513\SN12345) ok",
            rf"cam (USB\VID_1DFC&PID_8513\{PLACEHOLDERS['serial']}) ok",
        ),
        (
            r"[USB\VID_1DFC&PID_8513\SN12345] ok",
            rf"[USB\VID_1DFC&PID_8513\{PLACEHOLDERS['serial']}] ok",
        ),
    ],
)
def test_a_serial_number_goes_from_the_other_texts_as_well(text, replaced):
    # What follows a serial number in its text doesn't hide it where it stands alone.
    answers = {"a": text, "b": "lost SN12345"}
    found = capture_board.secrets(answers)
    redacted = capture_board.redact(answers, found)
    assert redacted == {"a": replaced, "b": f"lost {PLACEHOLDERS['serial']}"}
    assert capture_board.leftovers(json.dumps(redacted), found) == []


def test_a_line_break_ends_a_serial_number():
    text = "vid=1&serial=USB CAM 01\nvid=1&serial=USB CAM 02\n"
    found = capture_board.secrets({"note": text})
    assert found == {
        "USB CAM 01": PLACEHOLDERS["serial"],
        "USB CAM 02": PLACEHOLDERS["serial"],
    }
    redacted = capture_board.redact({"note": text}, found)
    assert redacted == {
        "note": f"vid=1&serial={PLACEHOLDERS['serial']}\n"
        f"vid=1&serial={PLACEHOLDERS['serial']}\n"
    }
    # As JSON writes it, the line break still ends the serial number.
    assert capture_board.leftovers(json.dumps(redacted), found) == []


def test_the_instance_of_a_camera_goes_wherever_the_board_names_it():
    path = r"USB\VID_1DFC&PID_8513\CAM123456"
    found = capture_board.secrets({"cam": path, "log": "opened CAM123456"})
    assert found == {"CAM123456": PLACEHOLDERS["serial"]}
    assert capture_board.redact({"log": "opened CAM123456"}, found) == {
        "log": f"opened {PLACEHOLDERS['serial']}"
    }


@pytest.mark.parametrize("escape", ["\n", "\r", "\t", "\b", "\f", "\\", "\x01"])
def test_the_escape_of_a_recording_is_no_part_of_what_follows_it(escape):
    # The placeholder after a line break is no leftover, as it would be with the "n".
    clean = json.dumps(f"signed in{escape}{PLACEHOLDERS['email']}")
    assert capture_board.leftovers(clean, {}) == []
    # And the letter of an escape doesn't hide an address behind it.
    for address, what in (
        ("fe80::1", "an IPv6 address"),
        ("b8:27:eb:12:34:56", "a MAC address"),
        ("192.168.1.50", "a private IPv4 address"),
    ):
        assert capture_board.leftovers(json.dumps(f"a{escape}{address}"), {}) == [what]


@pytest.mark.parametrize(
    ("answer", "secret"),
    [
        ({"sessionId": 123456, "bytes": 123456}, "123456"),
        (
            {"cam": "vid=1&serial=200901010001&location=1", "bytes": 200901010001},
            "200901010001",
        ),
    ],
)
def test_a_number_that_equals_a_secret_does_not_stop_the_recording(answer, secret):
    _, content = capture_board.files(
        {"version.txt": "2.2.0", "config.json": answer}, [], [], "", None
    )

    assert secret not in content["config.json"]


def test_a_serial_number_of_digits_goes_at_the_end_of_a_sentence():
    number = "200901010001"
    _, content = capture_board.files(
        {
            "version.txt": "2.2.0",
            "config.json": {
                "cam": f"vid=1&serial={number}&location=1",
                "log": f"lost camera {number}.",
            },
        },
        [],
        [],
        "",
        None,
    )

    assert number not in content["config.json"]


def test_a_serial_number_goes_wherever_the_board_names_it():
    found = capture_board.secrets(
        {"cams": [camera(3, SERIALS[0]), "serial=short"], "log": f"opened {SERIALS[0]}"}
    )

    # A short one only where it stands as a serial number: it can be a "pid" as well.
    assert found == {SERIALS[0]: PLACEHOLDERS["serial"]}
    assert capture_board.redact(
        {"log": f"opened {SERIALS[0]}", "cam": "serial=short", "pid": "short"}, found
    ) == {
        "log": f"opened {PLACEHOLDERS['serial']}",
        "cam": f"serial={PLACEHOLDERS['serial']}",
        "pid": "short",
    }


def test_the_name_of_the_board_pc_it_was_given_is_replaced_too():
    _, content = capture_board.files(
        {"version.txt": "1.0.7", "state.json": {"source": "dartboard.fritz.box"}},
        [],
        [],
        "dartboard.fritz.box",
        None,
    )

    assert json.loads(content["state.json"]) == {"source": "dartboard-pc"}
    assert content["version.txt"] == "1.0.7\n"
    assert content[capture_board.FRAMES] == ""


@pytest.mark.parametrize("host", ["dartboard.local", "192.168.1.50"])
@pytest.mark.parametrize("hostname", ["dartboard", "board-pc", "artboard"])
def test_a_board_pc_named_like_part_of_a_placeholder_is_recorded(host, hostname):
    # "dartboard" is part of the placeholder "dartboard-pc": it must neither be
    # replaced again inside it nor count as left in the recording.
    _, content = capture_board.files(
        {
            "version.txt": "2.0.2",
            "host.json": {"hostname": hostname, "ip": "192.168.1.50"},
            "state.json": {"source": f"reached as {host}, named {hostname}"},
        },
        [{"type": "state", "data": {"from": f"{hostname}.lan"}}],
        [],
        host,
        None,
    )

    assert json.loads(content["host.json"]) == {
        "hostname": PLACEHOLDERS["hostname"],
        "ip": PLACEHOLDERS["ip"],
    }
    placeholder = PLACEHOLDERS["ip" if host[0].isdigit() else "hostname"]
    assert json.loads(content["state.json"]) == {
        "source": f"reached as {placeholder}, named dartboard-pc"
    }
    assert "dartboard-pc-pc" not in "".join(content.values())
    assert content[capture_board.FRAMES] == (
        '{"type":"state","data":{"from":"dartboard-pc.lan"}}\n'
    )


def test_a_secret_is_found_next_to_a_placeholder():
    found = {"dartboard": PLACEHOLDERS["hostname"]}

    assert capture_board.leftovers("dartboard-pc", found) == []
    assert capture_board.leftovers("dartboard-pc and dartboard", found) == [
        PLACEHOLDERS["hostname"]
    ]
    assert capture_board.alternation([]).search("anything") is None


def test_nothing_is_written_that_still_holds_a_secret(monkeypatch):
    monkeypatch.setattr(capture_board, "redact", lambda value, found: value)

    with pytest.raises(SystemExit, match="Nothing written: the recording still holds"):
        capture_board.files(answers(), FRAMES, [], ADDRESS, "2026-10-18")
    # Also a key of several lines, which JSON writes with \n.
    found = {TLS_KEY: PLACEHOLDERS["tls_key"]}
    left = capture_board.leftovers(json.dumps({"tls_key": TLS_KEY}), found)
    assert left == [PLACEHOLDERS["tls_key"]]


def test_a_private_address_is_found_wherever_it_is():
    assert capture_board.leftovers("seen at 10.0.0.5", {}) == ["a private IPv4 address"]
    assert capture_board.leftovers("127.0.0.1 0.0.0.0 198.51.100.7 8.8.8.8", {}) == []
    assert capture_board.leftovers("version 999.1.1.1", {}) == []


@pytest.mark.parametrize(
    ("version", "folder"),
    [("1.0.7\n", "1.0.7"), ("v2.0.2", "2.0.2"), ("2.1.0-beta.1", "2.1.0-beta.1")],
)
def test_a_recording_goes_to_the_folder_of_its_version(version, folder):
    assert capture_board.folder_name(version) == folder


@pytest.mark.parametrize("version", [None, "", "../../etc", "<html>", 2])
def test_a_board_without_a_version_is_not_recorded(version):
    with pytest.raises(SystemExit, match="answers no version"):
        capture_board.folder_name(version)


def test_a_new_recording_replaces_the_files_of_the_one_before(tmp_path):
    old = tmp_path / "2.0.2"
    old.mkdir()
    (old / "system.json").write_text("{}\n", encoding="utf-8")
    (old / "notes.md").write_text("kept\n", encoding="utf-8")

    folder = capture_board.write(tmp_path, "2.0.2", {"state.json": "{}\n"})

    assert folder == old
    assert sorted(path.name for path in folder.iterdir()) == ["notes.md", "state.json"]


def test_the_address_of_the_board_takes_brackets_for_ipv6():
    assert capture_board.base_url("192.0.2.10", 3180) == "http://192.0.2.10:3180"
    assert capture_board.base_url("dartboard.local", 80) == "http://dartboard.local:80"
    assert capture_board.base_url("fe80::1", 3180) == "http://[fe80::1]:3180"


def board(frames, *, close: bool = True) -> web.Application:
    """A Board Manager 1 that knows only the routes of the setup."""
    app = web.Application()

    async def state(request):
        return web.json_response({"x": 1})

    async def version(request):
        return web.Response(text="1.0.7")

    app.router.add_get("/api/state", state)
    app.router.add_get("/api/version", version)

    async def events(request):
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        for frame in frames:
            if isinstance(frame, bytes):
                await socket.send_bytes(frame)
            else:
                await socket.send_str(frame)
        if close:
            await socket.close()
        else:
            await socket.receive()
        return socket

    app.router.add_get("/api/events", events)
    return app


async def record(app, tmp_path, **arguments):
    server = TestServer(app)
    await server.start_server()
    try:
        return await capture_board.capture(
            "127.0.0.1", server.port, out=tmp_path, **arguments
        )
    finally:
        await server.close()


@pytest.mark.usefixtures("socket_enabled")
async def test_a_capture_keeps_the_json_frames_and_lists_the_routes_it_lacks(
    tmp_path, capsys
):
    folder = await record(board(['{"type":"state"}', "no json", b"\x00"]), tmp_path)

    names = sorted(path.name for path in folder.iterdir())
    assert names == ["capture.json", "state.json", "version.txt", "ws-frames.jsonl"]
    assert (folder / "ws-frames.jsonl").read_text() == '{"type":"state"}\n'
    absent = json.loads((folder / "capture.json").read_text())["absent"]
    assert absent == [
        path
        for name, path in capture_board.ROUTES.items()
        if name not in ("state.json", "version.txt")
    ]
    assert "Skipped 1 frames that were no JSON." in capsys.readouterr().err


@pytest.mark.usefixtures("socket_enabled")
async def test_a_capture_records_the_socket_for_the_seconds_it_is_given(tmp_path):
    folder = await record(board(['{"a":1}'], close=False), tmp_path, seconds=0.2)

    assert (folder / "ws-frames.jsonl").read_text() == '{"a":1}\n'


@pytest.mark.usefixtures("socket_enabled")
async def test_a_capture_stops_after_the_frames_it_is_given(tmp_path):
    frames = ['{"a":1}', '{"a":2}', '{"a":3}']

    folder = await record(board(frames, close=False), tmp_path, limit=2)

    assert (folder / "ws-frames.jsonl").read_text() == '{"a":1}\n{"a":2}\n'


def test_the_command_line_records_the_board_it_names(tmp_path, monkeypatch, capsys):
    calls = []

    async def capture(host, port, seconds, out, limit, connected):
        calls.append((host, port, seconds, out, limit))
        connected()
        return out / "2.0.2"

    monkeypatch.setattr(capture_board, "capture", capture)

    status = capture_board.main(
        ["192.0.2.10", "--seconds", "5", "--frames", "40", "--out", str(tmp_path)]
    )

    assert status == 0
    assert calls == [("192.0.2.10", 3180, 5.0, tmp_path, 40)]
    output = capsys.readouterr()
    assert "Recording the socket for 5 s" in output.err
    assert f"Wrote {tmp_path / '2.0.2'}." in output.out


@pytest.mark.parametrize(
    "error", [aiohttp.ClientConnectionError("refused"), TimeoutError(), ValueError()]
)
def test_the_command_line_says_when_the_board_did_not_answer(
    monkeypatch, capsys, error
):
    async def capture(*arguments):
        raise error

    monkeypatch.setattr(capture_board, "capture", capture)

    assert capture_board.main(["192.0.2.10"]) == 1
    assert "The board did not answer as expected" in capsys.readouterr().err


# -- the second socket of Board Manager 2.1 -------------------------------------------


def second_socket_board(frames, second, close=True):
    """A board with its second socket, which sends the frames."""
    app = board(frames, close=close)

    async def system_events(request):
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        for frame in second:
            await socket.send_str(frame)
        if close:
            await socket.close()
        else:
            await socket.receive()
        return socket

    app.router.add_get(capture_board.SYSTEM_EVENTS, system_events)
    return app


def vantage_frame(**flags) -> dict:
    motion = {"seq": 1, "isHand": False, "isStable": True, **flags}
    return {"type": "vantage", "data": {"vantage": {"motion": motion, "seq": 1}}}


@pytest.mark.usefixtures("socket_enabled")
async def test_a_capture_records_the_second_socket_of_a_board(tmp_path):
    second = ['{"type":"state","data":{}}', '{"type":"board","data":{}}', "no json"]

    folder = await record(second_socket_board(['{"a":1}'], second), tmp_path)

    assert (folder / capture_board.SYSTEM_FRAMES).read_text() == (
        '{"type":"state","data":{}}\n{"type":"board","data":{}}\n'
    )
    assert (folder / "ws-frames.jsonl").read_text() == '{"a":1}\n'


@pytest.mark.usefixtures("socket_enabled")
async def test_the_first_socket_ends_the_recording_of_the_second(tmp_path):
    app = second_socket_board(['{"a":1}', '{"a":2}'], ['{"type":"state"}'], close=False)

    folder = await record(app, tmp_path, limit=2)

    assert (folder / "ws-frames.jsonl").read_text() == '{"a":1}\n{"a":2}\n'
    assert (folder / capture_board.SYSTEM_FRAMES).read_text() == '{"type":"state"}\n'


@pytest.mark.usefixtures("socket_enabled")
async def test_a_board_without_the_second_socket_gets_no_file_of_it(tmp_path):
    second = ['{"type":"state"}']
    folder = await record(second_socket_board(['{"a":1}'], second), tmp_path)
    assert (folder / capture_board.SYSTEM_FRAMES).exists()

    # A recording of the board after a rollback leaves nothing of the earlier one.
    await record(board(['{"a":1}']), tmp_path)

    assert not (folder / capture_board.SYSTEM_FRAMES).exists()


@pytest.mark.usefixtures("socket_enabled")
async def test_a_second_socket_that_breaks_ends_the_capture_with_its_error(tmp_path):
    real = capture_board.read_frames

    async def read_frames(session, base, seconds, *args, **kwargs):
        if kwargs.get("path") == capture_board.SYSTEM_EVENTS:
            raise aiohttp.ClientConnectionError("gone")
        return await real(session, base, seconds, *args, **kwargs)

    with patch.object(capture_board, "read_frames", read_frames):
        with pytest.raises(aiohttp.ClientConnectionError):
            await record(board(['{"a":1}']), tmp_path)


@pytest.mark.usefixtures("socket_enabled")
async def test_a_first_socket_that_breaks_also_ends_the_second(tmp_path):
    real = capture_board.read_frames
    second_ended = []

    async def read_frames(session, base, seconds, *args, **kwargs):
        if kwargs.get("path") == capture_board.SYSTEM_EVENTS:
            try:
                return await real(session, base, seconds, *args, **kwargs)
            finally:
                second_ended.append(True)
        raise aiohttp.ClientConnectionError("gone")

    app = second_socket_board([], ['{"type":"state"}'], close=False)
    with patch.object(capture_board, "read_frames", read_frames):
        with pytest.raises(aiohttp.ClientConnectionError):
            await record(app, tmp_path)
    assert second_ended


def test_a_recording_keeps_what_repeats_only_when_it_says_something_new(freezer):
    keep = capture_board.Repeats().keep
    still = vantage_frame()
    # The first of a kind, and not the same again within the ten seconds.
    assert keep(still)
    assert not keep(vantage_frame(frames=2))
    freezer.tick(9)
    assert not keep(still)
    # A flag that changed shows at once, and again when it changes back.
    assert keep(vantage_frame(isHand=True))
    assert not keep(vantage_frame(isHand=True))
    assert keep(still)
    # One every ten seconds, so that a recording shows what a quiet board sends.
    freezer.tick(capture_board.REPEATS_KEPT_SECONDS)
    assert keep(still)


def test_a_recording_keeps_the_load_every_ten_seconds_and_a_new_setting_at_once(
    freezer,
):
    keep = capture_board.Repeats().keep
    assert keep({"type": "stats", "data": {"stats": {"cpuPercent": 1.5}}})
    assert not keep({"type": "stats", "data": {"stats": {"cpuPercent": 2.5}}})
    settings = {"type": "vantageConfig", "data": {"fps": 30}}
    assert keep(settings)
    assert not keep(settings)
    assert keep({"type": "vantageConfig", "data": {"fps": 15}})
    freezer.tick(capture_board.REPEATS_KEPT_SECONDS)
    assert keep({"type": "stats", "data": {"stats": {"cpuPercent": 3.5}}})


@pytest.mark.parametrize(
    "frame",
    [
        {"type": "state", "data": {}},
        {"type": "board", "data": {}},
        {"type": "calibration", "data": {}},
        {"type": "something new"},
        {"no type": 1},
        [],
        "text",
        1,
    ],
)
def test_a_recording_keeps_everything_that_does_not_repeat(frame):
    keep = capture_board.Repeats().keep
    assert keep(frame)
    assert keep(frame)


@pytest.mark.parametrize(
    "frame",
    [
        {"type": "vantage"},
        {"type": "vantage", "data": []},
        {"type": "vantage", "data": {"vantage": None}},
        {"type": "vantage", "data": {"vantage": {"motion": None}}},
        {"type": "vantage", "data": {"vantage": {"motion": []}}},
    ],
)
def test_a_motion_frame_without_a_motion_says_no_flags(frame):
    assert capture_board.motion_flags(frame) == {}


def test_the_second_socket_is_redacted_like_everything_else():
    second = [
        {
            "type": "board",
            "data": {
                "status": {
                    "version": "2.1.0",
                    "boardId": BOARD_ID,
                    "linkServer": {
                        "name": "the server of my club",
                        "streamingTo": "192.168.1.77",
                        "interfaces": [{"mac": "aa:bb:cc:dd:ee:ff"}],
                    },
                }
            },
        },
        vantage_frame(hostname=f"{HOSTNAME}.lan", serial="SERIALNUMBER1"),
    ]

    _, content = capture_board.files(
        answers(), FRAMES, [], ADDRESS, "2026-11-01", second
    )

    text = content[capture_board.SYSTEM_FRAMES]
    for private in (
        BOARD_ID,
        HOSTNAME,
        "the server of my club",
        "192.168.1.77",
        "aa:bb:cc:dd:ee:ff",
        "SERIALNUMBER1",
    ):
        assert private not in text
    assert '"seq":1' in text
    assert capture_board.secrets(json.loads(line) for line in text.splitlines()) == {}


def test_a_secret_only_the_second_socket_knows_goes_from_every_file():
    second = [{"type": "board", "data": {"status": {"boardId": "second-only-id"}}}]
    frames = [{"type": "state", "data": {"note": "second-only-id"}}]

    _, content = capture_board.files(answers(), frames, [], ADDRESS, None, second)

    assert "second-only-id" not in "".join(content.values())
