---
description: "Why a Granboard connects through Home Assistant's own Bluetooth, as a dartboard without Autodarts, with frames from MIT-licensed apps and an experimental label."
---

# Connect a Granboard through Home Assistant's Bluetooth, as a dartboard without Autodarts

- Status: accepted
- Date: 2026-10-18

## Context

A Granboard is a popular soft-tip dartboard with Bluetooth LE. A hit sends a few ASCII characters on a notify characteristic of the service `442f1570-8a00-9a28-cbe1-e1d4212d53eb`, such as `3.4@` for the treble 20, and the button beside the board sends `BTN@`. Its owners reach their darts through a userscript for Chrome or Edge, which iOS lacks, or a Windows app; no Home Assistant integration exists ([#386](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/386)). The dartboard without Autodarts already plays every game, the training and the statistics with darts that Home Assistant enters itself ([without Autodarts](../without-autodarts.md)).

Three questions shaped the support: how the integration reaches the board, where the darts go, and where the table of the frames comes from. The one specification of the frames, keenanlk/granboard-ble-codes, has no license; the apps gran-app by sobassy and granboard-app by bastiennoel93 read the same frames under the MIT license. Nobody of the project owns a Granboard yet.

## Options

1. **A bridge of its own,** such as an ESP32 at the board that talks MQTT. It needs hardware and firmware at every board, and a second way into Home Assistant beside the integration.
2. **Home Assistant's Bluetooth,** as a manifest matcher on the service, `async_step_bluetooth` and `bleak_retry_connector.establish_connection` with the device that Home Assistant's Bluetooth knows. Every adapter of Home Assistant and every ESPHome Bluetooth proxy reaches the board, Home Assistant finds it on its own, and nothing else is installed.
3. **The darts as a transport of their own,** a third coordinator beside the Board Manager's and the one without Autodarts.

## Decision

Option 2, with the darts on the path of a dartboard without Autodarts: a Granboard is set up as a dartboard without Autodarts whose entry also names the Bluetooth address of the board. `GranboardLink` in `granboard.py`, owned by `AutodartsManualCoordinator`, enters every hit as the action `throw_dart` does and the button as `next_player` does, so the games, the keypad, the corrections, the voice blueprint and the events stay one path.

- **Bluetooth is an after-dependency,** not a dependency: Home Assistant installs its packages with the integration and sets it up first where it is set up, but a home without Bluetooth loads the integration as before. A Granboard without Home Assistant's Bluetooth logs it and keeps the keypad.
- **The frames are those of the MIT-licensed apps,** written in a table of the integration's own, by number with its inner single, treble, outer single and double; nothing comes from the unlicensed specification.
- **Experimental,** in the setup, the documentation and the changelog, until a real board has passed every bed. The debug log names every frame with its bed, and the diagnostics keep the last unknown frames, so that a tester can report them without the Bluetooth address of the board.
- **The connection recovers on its own:** at once when Home Assistant sees the board again, otherwise after a wait that doubles from 2 to 300 seconds. Frames of the first two seconds after a connection are dropped, as the granboard-app does, because a board may repeat its last hit.

## Consequences

- The tests import Home Assistant's Bluetooth, which depends on its usb integration: `requirements-test.in` names the packages of that integration, which `pytest-homeassistant-custom-component` does not bring. Since [decision 0031](0031-the-tests-run-on-home-assistants-own-test-plugin.md), the `bluetooth` extra of `pytest-homeassistant` brings them. The tests replay recorded frames against stand-ins for Bleak and the Bluetooth of Home Assistant; no test needs an adapter.
- The lights of the board's ring stay off: no app documents how to set them reliably. Darts of a Granboard have no position, so the inner and the outer single count alike and the dart positions leave them out.
- The label *experimental* goes with a pull request that names the tester and the board, once every bed and the button are checked on a real Granboard.
