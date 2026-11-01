"""The blueprints that come with the integration: installed with it, kept current
while nobody changes them, and left alone once someone did."""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.components.blueprint import models
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import parse_yaml
from pytest_homeassistant_custom_component.common import async_capture_events
from yaml import safe_dump

from custom_components.homedarts import shipped_blueprints
from custom_components.homedarts.repairs import async_create_fix_flow
from custom_components.homedarts.shipped_blueprints import (
    SHIPPED,
    STORAGE_KEY,
    VERSIONS,
    State,
    async_install_blueprints,
    fingerprint,
    state,
)

from .local_helpers import BLUEPRINTS, setup_local
from .test_discovery import confirm_repair

ROOT = Path(__file__).parents[1]
NAMES = sorted(path.name for path in BLUEPRINTS.glob("*.yaml"))
SHIP = "python scripts/ship_blueprints.py"
TAKEOUT = "takeout.yaml"


def shipped_text(name: str = TAKEOUT) -> str:
    return (SHIPPED / name).read_text(encoding="utf-8")


def changed(
    text: str, before: str = "pause\n    music", after: str = "pause\n    the music"
) -> str:
    """Another version of a blueprint: a word of its description."""
    assert before in text
    return text.replace(before, after)


def imported(text: str, source: str = "https://github.com/Dennis-Otto/x.yaml") -> str:
    """The file that Home Assistant's import saves of a blueprint."""
    blueprint = models.Blueprint(
        parse_yaml(text), expected_domain="automation", schema=BLUEPRINT_SCHEMA
    )
    blueprint.update_metadata(source_url=source)
    return blueprint.yaml()


@pytest.fixture
def config(hass, tmp_path) -> Path:
    """The folder of the blueprints of this repository in Home Assistant."""
    hass.config.config_dir = str(tmp_path)
    return tmp_path / "blueprints" / "automation" / "Dennis-Otto"


@pytest.fixture
def known(tmp_path):
    """Lets the integration know more versions of a blueprint than main had."""

    def add(name: str, text: str) -> None:
        path = tmp_path / "versions.json"
        source = path if path.exists() else VERSIONS
        versions = json.loads(source.read_text(encoding="utf-8"))
        versions[name].append(fingerprint(parse_yaml(text)))
        path.write_text(json.dumps(versions), encoding="utf-8")
        patcher = patch.object(shipped_blueprints, "VERSIONS", path)
        patcher.start()
        added.append(patcher)

    added: list = []
    yield add
    for patcher in added:
        patcher.stop()


async def use_takeout(hass) -> None:
    """An automation made from the takeout blueprint of the configuration, also in
    its configuration.yaml, which a reload reads."""
    config = {
        "automation": [
            {
                "use_blueprint": {
                    "path": f"Dennis-Otto/{TAKEOUT}",
                    "input": {"board_events": "event.autodarts_board_events"},
                }
            }
        ]
    }
    await hass.async_add_executor_job(
        Path(hass.config.path("configuration.yaml")).write_text,
        safe_dump(config),
        "utf-8",
    )
    assert await async_setup_component(hass, "automation", config)
    await hass.async_block_till_done()
    assert [state.state for state in hass.states.async_all("automation")] == ["on"]


def reloads(calls) -> int:
    """How often the automations were reloaded."""
    return sum(
        (call.data["domain"], call.data["service"]) == ("automation", "reload")
        for call in calls
    )


def repairs(hass) -> dict[str, ir.IssueEntry]:
    return {
        issue_id: issue
        for (domain, issue_id), issue in ir.async_get(hass).issues.items()
        if domain == "homedarts" and issue_id.startswith("blueprint_edited_")
    }


# -- what the release carries ---------------------------------------------------


def test_the_release_carries_the_blueprints_of_the_repository():
    """The package of a release holds the integration's folder, so the blueprints
    of the repository are copied into it, byte for byte."""
    copies = sorted(path.name for path in SHIPPED.glob("*.yaml"))
    assert copies == NAMES, f"Run {SHIP}"
    for name in NAMES:
        assert (SHIPPED / name).read_bytes() == (BLUEPRINTS / name).read_bytes(), (
            f"{name} differs from its copy in the integration. Run {SHIP}"
        )
    assert {path.name for path in SHIPPED.parents[1].rglob("*")} == {
        "automation",
        "homedarts",
        *NAMES,
    }


def test_the_integration_knows_every_version_of_each_blueprint():
    versions = json.loads(VERSIONS.read_text(encoding="utf-8"))
    assert list(versions) == NAMES, f"Run {SHIP}"
    for name in NAMES:
        current = fingerprint(parse_yaml((BLUEPRINTS / name).read_text("utf-8")))
        assert current in versions[name], f"{name} is a new version. Run {SHIP}"
        assert len(set(versions[name])) == len(versions[name]), name
    assert VERSIONS.read_text(encoding="utf-8") == json.dumps(versions, indent=2) + "\n"


@pytest.mark.parametrize("name", NAMES)
def test_an_imported_blueprint_is_the_one_of_the_release(name):
    """Home Assistant's import writes a blueprint anew, with the address it came
    from and every option of its selectors: still the same blueprint."""
    new = (SHIPPED / name).read_bytes()
    saved = imported(new.decode()).encode()
    assert saved != new
    assert state(saved, new, []) is State.CURRENT


def test_an_imported_earlier_version_is_known_by_its_fingerprint():
    new = (SHIPPED / TAKEOUT).read_bytes()
    old = changed(new.decode())
    saved = imported(old).encode()
    assert state(saved, new, []) is State.EDITED
    assert state(saved, new, [fingerprint(parse_yaml(old))]) is State.OUTDATED


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("min: 2\n", "min: 1\n"),
        ("- integration: homedarts\n                  domain", "- domain"),
    ],
)
def test_changed_selector_options_of_the_current_version_stay(before, after):
    """Another range or filter of the current version has its fingerprint, and is
    still a change of the user."""
    new = (SHIPPED / "light_show.yaml").read_bytes()
    old = changed(new.decode(), before, after).encode()
    versions = json.loads(VERSIONS.read_text(encoding="utf-8"))["light_show.yaml"]
    assert fingerprint(parse_yaml(old.decode())) in versions
    assert state(old, new, versions) is State.EDITED


def test_the_fingerprint_of_a_version():
    text = """
blueprint:
  name: Test
  source_url: https://example.com/a.yaml
  input:
    plain:
    bare:
      name: Without a selector
    section:
      input:
        number:
          selector:
            number: {min: 1, max: 9}
        free:
          selector: text
    other:
      selector:
        unknown_type: {}
action: !input number
"""
    # Neither the address nor the options of a selector make another version.
    options = text.replace("a.yaml", "b.yaml").replace("{min: 1, max: 9}", "{min: 2}")
    assert fingerprint(parse_yaml(text)) == fingerprint(parse_yaml(options))
    for other in (text.replace("Test", "Toast"), text.replace("t number", "t free")):
        assert fingerprint(parse_yaml(text)) != fingerprint(parse_yaml(other))
    # Selectors that Home Assistant does not know are compared as they are.
    moved = text.replace("a.yaml", "b.yaml")
    assert state(moved.encode(), text.encode(), []) is State.CURRENT
    assert state(options.encode(), text.encode(), []) is State.EDITED
    # Without a blueprint, or not even an object.
    assert fingerprint({"action": []}) != fingerprint({"action": [1]})
    assert fingerprint({"blueprint": {"name": "a"}}) != fingerprint({"blueprint": {}})
    assert state(b"- a list\n", text.encode(), []) is State.EDITED
    assert state(b"key: [unclosed\n", text.encode(), []) is State.EDITED
    assert state(b"\xff\xfe", text.encode(), []) is State.EDITED


# -- the installation -------------------------------------------------------------


@pytest.mark.installs_blueprints
async def test_a_new_home_gets_every_blueprint(
    hass, aioclient_mock, config, hass_storage
):
    await setup_local(hass, aioclient_mock)
    assert sorted(path.name for path in config.iterdir()) == NAMES
    for name in NAMES:
        assert (config / name).read_bytes() == (SHIPPED / name).read_bytes()
    assert hass_storage[STORAGE_KEY]["data"] == {"installed": NAMES}
    assert not repairs(hass)


@pytest.mark.installs_blueprints
async def test_a_deleted_blueprint_stays_deleted(hass, config, hass_storage):
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": {"installed": [TAKEOUT]},
    }
    await async_install_blueprints(hass)
    assert not (config / TAKEOUT).exists()
    # The others came with this release, the first that brings them.
    assert sorted(path.name for path in config.iterdir()) == [
        name for name in NAMES if name != TAKEOUT
    ]
    assert hass_storage[STORAGE_KEY]["data"] == {"installed": NAMES}


@pytest.mark.installs_blueprints
async def test_nothing_to_do_once_every_blueprint_is_current(hass, config, caplog):
    caplog.set_level(logging.INFO)
    await async_install_blueprints(hass)
    assert f"Installed the blueprints {', '.join(NAMES)}" in caplog.text
    caplog.clear()
    with patch.object(shipped_blueprints.Store, "async_save") as save:
        await async_install_blueprints(hass)
    save.assert_not_called()
    assert "Installed the blueprints" not in caplog.text
    assert "Updated the unchanged blueprints" not in caplog.text


@pytest.mark.installs_blueprints
@pytest.mark.parametrize("form", ["release", "import"])
async def test_a_blueprint_nobody_changed_follows_the_integration(
    hass, config, known, form, caplog
):
    """An earlier version, as the integration brought it or as Home Assistant
    imported it from main, becomes the version of the release."""
    caplog.set_level(logging.INFO)
    old = changed(shipped_text())
    known(TAKEOUT, old)
    config.mkdir(parents=True)
    (config / TAKEOUT).write_text(old if form == "release" else imported(old), "utf-8")
    await async_install_blueprints(hass)
    assert (config / TAKEOUT).read_bytes() == (SHIPPED / TAKEOUT).read_bytes()
    assert f"Updated the unchanged blueprints {TAKEOUT}" in caplog.text
    assert not repairs(hass)


@pytest.mark.installs_blueprints
async def test_an_imported_current_blueprint_stays_as_it_was_saved(hass, config):
    config.mkdir(parents=True)
    saved = imported(shipped_text())
    (config / TAKEOUT).write_text(saved, "utf-8")
    await async_install_blueprints(hass)
    assert (config / TAKEOUT).read_text("utf-8") == saved
    assert not repairs(hass)


@pytest.mark.installs_blueprints
async def test_automations_follow_their_updated_blueprint(hass, config, known):
    old = changed(shipped_text())
    known(TAKEOUT, old)
    config.mkdir(parents=True)
    (config / TAKEOUT).write_text(old, "utf-8")
    await use_takeout(hass)
    calls = async_capture_events(hass, EVENT_CALL_SERVICE)
    await async_install_blueprints(hass)
    assert reloads(calls) == 1
    # Home Assistant reads the blueprint anew.
    blueprints = shipped_blueprints.async_get_blueprints(hass)
    blueprint = await blueprints.async_get_blueprint(f"Dennis-Otto/{TAKEOUT}")
    description = parse_yaml(shipped_text())["blueprint"]["description"]
    assert blueprint.metadata["description"] == description


@pytest.mark.installs_blueprints
async def test_an_update_without_automations_reloads_none(hass, config, known):
    old = changed(shipped_text())
    known(TAKEOUT, old)
    config.mkdir(parents=True)
    (config / TAKEOUT).write_text(old, "utf-8")
    assert await async_setup_component(hass, "automation", {})
    calls = async_capture_events(hass, EVENT_CALL_SERVICE)
    await async_install_blueprints(hass)
    assert not calls
    assert (config / TAKEOUT).read_bytes() == (SHIPPED / TAKEOUT).read_bytes()


@pytest.mark.installs_blueprints
@pytest.mark.parametrize(
    "content",
    [
        changed(shipped_text(), "pause\n    music", "start\n    music").encode(),
        b"blueprint: [unclosed\n",
    ],
    ids=["changed", "broken"],
)
async def test_a_changed_blueprint_stays_with_a_repair(hass, config, content):
    config.mkdir(parents=True)
    (config / TAKEOUT).write_bytes(content)
    # A repair of an earlier version, and one of another kind.
    ir.async_create_issue(
        hass,
        "homedarts",
        "blueprint_edited_takeout_000000000000",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="blueprint_edited",
    )
    ir.async_create_issue(
        hass,
        "homedarts",
        "calibration_recommended_x",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="calibration_recommended",
    )
    ir.async_create_issue(
        hass,
        "other",
        "blueprint_edited_takeout_1",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="x",
    )
    await async_install_blueprints(hass)
    assert (config / TAKEOUT).read_bytes() == content
    version = fingerprint(parse_yaml(shipped_text()))[:12]
    ((issue_id, issue),) = repairs(hass).items()
    assert issue_id == f"blueprint_edited_takeout_{version}"
    assert issue.is_fixable
    assert issue.translation_placeholders == {
        "name": "HomeDarts: takeout actions",
        "path": f"blueprints/automation/Dennis-Otto/{TAKEOUT}",
    }
    assert issue.data == {"file": TAKEOUT}
    registry = ir.async_get(hass)
    assert registry.async_get_issue("homedarts", "calibration_recommended_x")
    assert registry.async_get_issue("other", "blueprint_edited_takeout_1")
    # The next start keeps it.
    await async_install_blueprints(hass)
    assert list(repairs(hass)) == [issue_id]
    # Once it is current again, by hand or by its repair, the repair goes.
    (config / TAKEOUT).write_bytes((SHIPPED / TAKEOUT).read_bytes())
    await async_install_blueprints(hass)
    assert not repairs(hass)


@pytest.mark.installs_blueprints
async def test_the_repair_replaces_a_changed_blueprint(
    hass, hass_client, aioclient_mock, config
):
    config.mkdir(parents=True)
    (config / TAKEOUT).write_text(
        changed(shipped_text(), "pause\n    music", "stop\n    music"), "utf-8"
    )
    await use_takeout(hass)
    await setup_local(hass, aioclient_mock)
    (issue_id,) = repairs(hass)
    calls = async_capture_events(hass, EVENT_CALL_SERVICE)
    result = await confirm_repair(hass, hass_client, issue_id)
    assert result["type"] == "create_entry"
    assert (config / TAKEOUT).read_bytes() == (SHIPPED / TAKEOUT).read_bytes()
    assert reloads(calls) == 1
    assert not repairs(hass)


async def start_repair(hass, data: dict | None) -> dict:
    flow = await async_create_fix_flow(hass, "blueprint_edited_takeout_1", data)
    flow.hass = hass
    flow.issue_id = "blueprint_edited_takeout_1"
    result = await flow.async_step_init()
    assert result["description_placeholders"] is None
    return await flow.async_step_confirm({})


@pytest.mark.installs_blueprints
async def test_the_repair_of_a_blueprint_the_release_no_longer_brings(hass, config):
    result = await start_repair(hass, {"file": "../configuration.yaml"})
    assert result["reason"] == "not_shipped"
    result = await start_repair(hass, None)
    assert result["reason"] == "not_shipped"
    assert not config.exists()


@pytest.mark.installs_blueprints
async def test_the_repair_of_a_blueprint_that_cannot_be_written(hass, config):
    (config / TAKEOUT).mkdir(parents=True)
    result = await start_repair(hass, {"file": TAKEOUT})
    assert result["reason"] == "write_failed"


@pytest.mark.installs_blueprints
async def test_a_folder_that_cannot_be_written_is_tried_again(
    hass, config, hass_storage, caplog
):
    (config / TAKEOUT).mkdir(parents=True)
    await async_install_blueprints(hass)
    assert f"Cannot install the blueprint {config / TAKEOUT}" in caplog.text
    assert TAKEOUT not in hass_storage[STORAGE_KEY]["data"]["installed"]
    assert (config / "dart_caller.yaml").is_file()
