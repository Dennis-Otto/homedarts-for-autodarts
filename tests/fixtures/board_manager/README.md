# Recorded Board Manager answers

What the Board Manager answers on its local port 3180, one folder per version. The
double of the Board Manager in the unit tests (`tests/local_helpers.py`) and that of
the [Docker end-to-end test](../../e2e/README.md) (`tests/e2e/board_mock.py`) answer
like these recordings, and `tests/test_board_contract.py` holds them to it: the test
fails when a double answers a route in another shape than its recording, when the
integration can't read a recording, or when a recording keeps a secret. A change of
the Board Manager becomes a change of a recording, and both test suites follow it.

| Version | Generation | Source |
| --- | --- | --- |
| [`1.0.7`](1.0.7/) | Board Manager 1, the classic app | Built from the shapes the integration was developed against |
| [`2.0.0`](2.0.0/) | Board Manager 2, headless | Built from the shapes the integration was developed against |
| [`2.0.2`](2.0.2/) | Board Manager 2, headless | Built from the shapes the integration was developed against, with the takeout that 2.0.2 sometimes never finishes |
| [`2.1.0`](2.1.0/) | Board Manager 2, headless, in the shape of 2.1 | A real board with its detection running; its socket while the detection stopped, started and stopped again |

No dart was thrown on the board of `2.1.0`. The frames of a real board of 2.1.0 with
real darts and takeouts, from another board, are in
[`board_manager_2.1.0_frames.jsonl`](../board_manager_2.1.0_frames.jsonl).

`capture.json` of each folder says where it comes from: `captured` is the day of a
capture of a real board, or `null` for a recording built from the documented shapes,
which a capture replaces.

## Files

| File | Route |
| --- | --- |
| `state.json` | `GET /api/state` |
| `config.json` | `GET /api/config` |
| `version.txt` | `GET /api/version` |
| `state-stats.json` | `GET /api/state/stats` |
| `state-motion.json` | `GET /api/state/motion` |
| `cams-stats.json` | `GET /api/cams/stats` |
| `cams-state.json` | `GET /api/cams/state` |
| `system.json` | `GET /api/system`, Board Manager 2 |
| `host.json` | `GET /api/host`, Board Manager 2 |
| `ws-frames.jsonl` | The frames of the socket `/api/events`, one per line, while darts are thrown and taken out |
| `capture.json` | The version, the day of the capture, its source and the routes the board doesn't have (`absent`) |

## Placeholders

A recording never holds the identity or a secret of a real board.
[`scripts/capture_board.py`](../../../scripts/capture_board.py) replaces them before
it writes anything, wherever they appear, and writes nothing if one is left:

| What | Placeholder |
| --- | --- |
| Board ID, `config.auth.board_id` | `board-1` |
| Board API key, `config.auth.api_key` | `private-board-api-key` |
| TLS key and certificate of Board Manager 2, `config.host` | `private-tls-key`, `private-tls-cert` |
| Name of the board PC, `host.hostname`, and the name it was reached by | `dartboard-pc` |
| Addresses of the board PC and of the home network: `host.ip` and every private IPv4 address | `198.51.100.7`, an address for documentation |
| Any other value of a key that ends in `key`, `token`, `secret`, `password` or `cert` | `private-<key>` |

The unit tests look for these placeholders in the states of the entities and in the
diagnostics, so a secret of the board can't leak there unnoticed.

## Record your board

With a clone of the repository and Python 3.13 or newer with aiohttp, which the test
environment of `requirements-test.txt` has:

```sh
python scripts/capture_board.py 192.168.1.50
```

It reads every route above, then records the socket for 60 seconds
(`--seconds`, or `--frames` for a number of frames): start the detection, throw a few
darts and take them out. It writes the folder of the version the board reports, such
as `tests/fixtures/board_manager/2.0.2/`, replacing the files of an earlier recording.
Look through the files before you share them, then attach the folder as a zip file to
a [board compatibility report](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml)
or open a pull request with it; `tests/test_board_contract.py` takes up a new folder
by itself.
