---
description: "Why the images and the recording of the live demo render with the screenshot bot of the blueprint, in shards, and what that gives up."
---

# Render the images with the screenshot bot of the blueprint, in shards

- Status: accepted
- Date: 2026-11-08

## Context

HomeDarts kept a screenshot bot of its own, `screenshots.yml`: eight jobs that rendered the [groups](0012-images-in-groups-from-fresh-demos.md) of both languages side by side, a job per language that put them together, a job that recorded the [live demo](0014-a-live-demo-from-a-recording-of-the-integration.md), and a job that wrote the pull request through GitHub's API with Bash and Python of its own, about 750 lines. The blueprint gives every repository a screenshot bot as well, `screenshot-bot.yml`, which it keeps current. Each fix of one, such as the comparison of an animation frame by frame, the sizes that the pages name for a picture, a render that starts anew when `main` changed a picture meanwhile, or the bot-health issue after a failed run, had to be built again in the other, or HomeDarts went without it. Since its release v1.12.0 (its decision 0120), the shared bot renders shards side by side, takes files besides pictures and blocks every host but those that the project names: what HomeDarts needed a workflow of its own for.

## Options

1. Keep the project's own workflow: it keeps everything it does, and every fix of the shared bot costs a second fix here.
2. Render with the shared bot: `scripts/screenshots.sh` renders the shard that `SCREENSHOTS_SHARD` names, and `.github/screenshots.toml` names the shards, the recording and the hosts.
3. Wait until the shared bot can do everything that the project's own did, such as taking a language that rendered while the other failed.

## Decision

Option 2. The shards are `en-1` to `en-4` and `de-1` to `de-4`, one group of one language each, from a fresh demo, and `timeline`, the recording in `docs/demo/timeline.json`, the one file besides pictures. A group renders into a folder of its own, as in the visual check, and its images then go over those of its language: the container of the browser owns the files it writes, and the bot gives each image whose pixels stayed the same its committed file back. The hosts are those of the jobs *render* of the visual check that the shared job doesn't bring itself: Home Assistant from GitHub's registry, Playwright from Microsoft's, pngquant from Launchpad and `brands.home-assistant.io`. `.github/screenshots-paths.txt` takes over the paths of the old workflow, with the test that records the live demo, and leaves out the manifest, whose version a release writes: the bot renders after every release on the workflow Release anyway, and the push of the release would render a second time. Since the shared step that renders has no time limit of its own, `scripts/screenshots.sh` keeps the 21 minutes of the old step for each group and stops the screenshot tool with SIGINT itself, so that it still prints the state of its containers.

## Consequences

The pictures come out the same, from the same commands of `tests/e2e/screenshots.sh` with the same settings; the project keeps no Bash or Python of its own for the pull request, and every fix of the shared bot reaches it with the next update of the blueprint. It gives up four things of its own bot:

- **Images rendered once.** A push to `main` no longer takes the images that the visual check of the pull request rendered from the same files (`tests/e2e/render_key.py`): every run of the bot renders all groups, about 70 runner minutes. The visual check still takes the images of its earlier runs.
- **One language at a time.** The bot takes every shard or none. When one group fails, the pull request stays as it is, and a rerun of the failed job renders only that shard; before, the pull request took the language that rendered.
- **Deleting an image.** No shard knows what the others render, so the bot deletes no image. The visual check of a pull request renders every group, so its comment names an image that no group renders any more and asks that pull request to delete it.
- **Diagnostics of a failed render.** The table of all groups of a language and the screenshots of a failed section stay in the visual check; a shard of the bot lists the seconds of its own sections in its summary.

The render jobs of the shared bot block hosts with Harden-Runner v2.22.3, the version of the blueprint's `screenshot-bot.yml`, and have no step that takes GitHub's DNS experiment out of the way of Harden-Runner, which the jobs of this project that start containers have ([decision 0013](0013-jobs-reach-only-the-hosts-they-need.md)). The project's own jobs need v2.22.4 or later: on v2.22.3, a job on a runner of the DNS experiment hung until its time limit when the API of StepSecurity answered 429. When a shard fails for either, the newer version and the step belong in the blueprint, for every job that blocks hosts. This changes parts of decisions 0012, 0013 and 0014, which named the project's own bot.

Update of 2026-11-08: since the blueprint 1.13.0, `.github/screenshots.toml` gives the step that renders a shard 21 minutes (`timeout_minutes`), as the visual check gives the step that renders a group, leaves `launchpad.net` out of the wait for the hosts (`skip_wait`), as the jobs of this project do, and has a shard that failed keep `tests/e2e/artifacts/` for seven days (`failure_folder`), so the screenshots of a failed section now come from the bot as well ([#629](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/629)). GitHub's SIGINT at the end of that step reaches `scripts/screenshots.sh` alone, not the screenshot tool, so the script still stops the tool with SIGINT itself, three minutes before its step ends, and gives it two minutes to print the state of its containers.
