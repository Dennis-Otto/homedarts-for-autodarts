---
description: "Why the tests run on pytest-homeassistant, the test plugin that Home Assistant publishes with each release, in place of the old plugin."
---

# The tests run on Home Assistant's own test plugin

- Status: accepted
- Date: 2026-11-14

## Context

The tests of the integration ran on pytest-homeassistant-custom-component, which pins one release of Home Assistant exactly, and Home Assistant pins its Pillow exactly. Its last release, 0.13.375 of 2026-10-25, brings Home Assistant 2026.10.4 and with it Pillow 12.3.0, which has more than forty advisories, all fixed in Pillow 13.0.0. No update of `requirements-test.txt` could move Pillow, so `osv-scanner.toml` accepted every advisory of Pillow 12.3.0 until 2026-11-22, "until the next update of pytest-homeassistant-custom-component that brings Pillow 13" ([#727](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/727)).

That update doesn't come: on 2026-11-03 its maintainer marked the package as broken and pointed to `pytest-homeassistant`, the test plugin that Home Assistant now builds from its own tests and publishes with each of its releases, beside its betas. Its 2026.11.1 pins Home Assistant 2026.11.1, which pins Pillow 13.0.0.

## Options

1. Move `effectiveUntil` again: the reason of the acceptance, the next release of the old plugin, no longer holds, and the tests would stay on Home Assistant 2026.10 for good, while the integration runs on each new release.
2. Pin a newer Home Assistant beside the old plugin: the old plugin pins `homeassistant==2026.10.4`, so pip can't install both, and its fixtures follow the internals of that release.
3. Move to `pytest-homeassistant`, which comes with each release of Home Assistant, from the same sources as Home Assistant's own tests.

## Decision

Option 3. `requirements-test.in` names `pytest-homeassistant[bluetooth]`: its extra `bluetooth` brings the packages of Home Assistant's Bluetooth and of the usb integration that it depends on, which the Granboard link imports, so `aiousbwatcher` and `serialx` no longer need lines of their own. It brings fewer plugins of pytest than the old one: `pytest-cov`, `pytest-timeout` and `pytest-github-actions-annotate-failures`, which `scripts/check.sh`, the time limit in `pyproject.toml` and the annotations of the CI use, are lines of their own now. The tests import their helpers from `pytest_homeassistant`, and `pyproject.toml` starts pytest with `-p no:respx`, as its README asks: Home Assistant puts its `httpx2` in place of `httpx` as it is imported, which must come before the plugin of respx imports `httpx`. `osv-scanner.toml` accepts no Pillow any more, and `.github/renovate.json5` keeps the new plugin in a pull request of its own, as the blueprint's rule did for the old one.

## Consequences

- The tests run on Home Assistant 2026.11.1 and on each new release from now on, with Pillow 13.0.0.
- The old plugin gave each test a configuration folder inside its own package; the new one points every test at a folder `testing_config` beside the tests, in the repository, where the backups, media and blueprints of the integration would pile up. `tests/conftest.py` overrides its fixture `hass_config_dir`, as the plugin's README offers, with an empty temporary folder for each test, apart from the test's `tmp_path`, which many tests fill with folders of their own. Its fixture `hass` names `testing_config/media` as the media folder whatever the configuration folder is, so the override of `hass` in `tests/conftest.py` names the media folder inside the test's own configuration folder, where a removed board leaves its backup. `tests/test_harness.py` keeps both so.
- Home Assistant 2026.11 checks entity IDs to their end (`\Z` in place of `$`), and `tests/test_profiles.py` compares the check of a person in `profiles.py` with it: a person's entity ID with a line break at its end is no profile's person any more, as in Home Assistant. A test of `tests/test_storage.py` reads whether a store is private from the new place of Home Assistant's `Store`.
- `AGENTS.md`, `CONTRIBUTING.md` and `.github/renovate-blueprint.json5` come from the blueprint and still name the old plugin: they change with the blueprint, whose kind Home Assistant integration makes the same move.
