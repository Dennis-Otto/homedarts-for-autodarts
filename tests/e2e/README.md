# Docker end-to-end test

The suite mounts `custom_components/homedarts` read-only into a real Home Assistant
container and connects it to a deterministic Board Manager double. The double runs
from the same pinned Home Assistant image, so it needs no additional image. It
answers like the [recorded Board Manager](../fixtures/board_manager/README.md) 1.0.7,
2.0.0 or 2.1.0, which `compose.yaml` mounts next to it, with the board ID and keys of the
test and the state of the board it simulates; `tests/test_board_contract.py` fails
when one of its answers takes another shape than its recording. CI runs
the scenario on every push to `main`, every night, and in every pull request that
changes what it runs or mounts: the integration, the blueprints, this folder, the
recordings, the npm packages or `e2e.yml`, in jobs of its own for each Board Manager and the oldest
supported Home Assistant, beside the browser test of the cards in four shards
(`browser.sh`, see [The browser test in shards](../../docs/development.md#the-browser-test-in-shards)).
The required check `e2e` passes once these tests pass, or at once when a pull request
changes none of these files; see
[Continuous integration](../../docs/development.md#continuous-integration).

Run locally with Docker and Compose:

```bash
bash tests/e2e/run.sh
```

The log shows the seconds of every phase of the scenario, such as
`Scenario phase: resilience (46.3 s)`. A phase, a step of the browser test or a
section of the screenshots that hangs fails after its budget of time with the line
that it waits at (`watchdog.py`), and a run that a signal stops, such as Ctrl+C or
GitHub at the time limit of its step, prints the state of its containers and the end
of the log of Home Assistant (`diagnose.sh`); see
[When a step hangs](../../docs/development.md#when-a-step-hangs).

The script pulls the image of Home Assistant before the containers start, up to
three times 10 seconds apart, so that a pull the registry cuts off doesn't fail the
scenario.

The scenario uses only Home Assistant's public REST and WebSocket APIs and verifies:

- onboarding and local config flow, including invalid-host, unreachable-board and
  duplicate-board handling
- entity and device registry contents, discovered per-camera entities and
  disabled-by-default entities
- buttons, switches and the standby select, compared with the exact Board Manager
  requests they send
- realtime darts, corrections and takeouts over the Board Manager WebSocket with
  polling disabled, including training counters and their persistence
- faults injected into the Board Manager double: a socket that drops in the middle
  of a visit, an outage while darts are pulled and thrown again, failing and slow
  reads, malformed frames and a restart; visits, practice scores and entities
  must come through them
- a takeout the board keeps on the empty board, as Board Manager 2.0.2 sometimes
  does, which the integration frees with one reset after ten seconds
- the online bridge: switched on in the options, calls of Tools for Autodarts
  become board events and the diagnostic sensor, and switched off it is gone
- the weekly report and its settings, the training calendar through
  `calendar.get_events`, and exports as JSON and CSV with their download, with and
  without a login, and a refused folder outside the configuration
- a practice match of two players that ends with its summary in the practice sensor
  and the `match_won` event, and double out switched during a leg, which applies
  from the next leg
- a round robin tournament of three players at 101, started by
  `homedarts.start_tournament` and played on the board: the order of play, the
  pause between the matches, the table, the tournament events and the profiles
- diagnostics without the board ID, API key, webhook address or player names, and
  logs without errors, tracebacks or secrets
- a Home Assistant that stays off the internet: its onboarding would set up Radio
  Browser, which looks up radio stations there as soon as it starts, so
  `offline/radio_browser` takes its place as a custom integration and turns the offer
  down, and no entry of Radio Browser exists; in CI, Harden-Runner also blocks every
  host that a job doesn't need (see
  [Network of the jobs](../../docs/development.md#network-of-the-jobs))
- removal of the entry, its entities, the realtime connection and the stored
  training session, weekly report and journal

Optional environment variables:

- `E2E_PORT`: host port for Home Assistant on `127.0.0.1`, default `18123`
- `DOCKER_BIN`: Docker CLI path, default `docker`
- `E2E_PROJECT_NAME`: Compose project name, default `homedarts_e2e`
- `HOME_ASSISTANT_IMAGE`: pinned Home Assistant image override
- `KEEP_E2E=1`: keep containers and the disposable volume after the suite
- `E2E_PULL_PAUSE`: seconds between the attempts to pull the images, default `10`

All users, passwords, board IDs and API keys are synthetic. Renovate keeps the
pinned Home Assistant image up to date.
