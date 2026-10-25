---
description: "The decisions that shape Autodarts for Home Assistant, each with its context, the options and the reasons, from the local API of the board to the releases."
---

# Decisions

The decisions that shape this project, each with its reasons, so that a later change can see why things are as they are. A decision that changes an earlier one gets a new record, and the earlier one says which record replaces it.

Copy [the template](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/docs/decisions/0000-template.md) to the next free number and describe the decision in the pull request that makes it.

| Record | Decision | Status |
| --- | --- | --- |
| [0001](0001-record-decisions.md) | Record the decisions that shape the project | accepted |
| [0002](0002-local-api-of-the-board-manager.md) | Talk to the board through the local API of the Board Manager | accepted |
| [0003](0003-games-and-statistics-in-home-assistant.md) | Keep games, training and statistics in Home Assistant itself | accepted |
| [0004](0004-hacs-with-signed-packages.md) | Deliver through HACS, with signed release packages | accepted |
| [0005](0005-documentation-in-english-and-german.md) | Write the documentation in English, with a complete German translation | accepted |
| [0006](0006-a-protocol-library-later.md) | Keep the protocol of the Board Manager in the integration for now | accepted |
| [0007](0007-the-repository-blueprint.md) | Follow the repository blueprint | accepted |
| [0008](0008-betas-for-testers.md) | Give testers a beta after every change for users | accepted |
| [0009](0009-german-pages-next-to-the-english-ones.md) | Put each German page next to its English page, for the language switch of the website | accepted |
| [0010](0010-end-to-end-tests-behind-one-check.md) | Run the end-to-end tests only for the changes they test, behind one required check | accepted |
| [0011](0011-entities-by-topic-without-coordinator-internals.md) | Update the entities of fast readings by topic, without the internals of Home Assistant's coordinator | accepted |
| [0012](0012-images-in-groups-from-fresh-demos.md) | Render the images of the documentation in fixed groups, each from a fresh demo | accepted |
| [0013](0013-jobs-reach-only-the-hosts-they-need.md) | Let the jobs of the project's workflows reach only the hosts they need, and the Home Assistant under test none | accepted |
| [0014](0014-a-live-demo-from-a-recording-of-the-integration.md) | Replay a recording of the integration for the live demo of the website | accepted |
| [0015](0015-voice-packs-in-the-file-names-of-darts-caller.md) | Give the callers voice packs in the file names of darts-caller | accepted |
| [0016](0016-a-game-engine-without-home-assistant.md) | Run the games in an engine without Home Assistant, apart from the connection to the board | accepted |
| [0017](0017-modules-in-the-dashboard-resources-for-cast.md) | Keep the modules of the cards in the dashboard resources, for Home Assistant Cast | accepted |
| [0018](0018-a-dartboard-without-autodarts-beside-the-board.md) | Play a dartboard without Autodarts beside the board, without a transport | accepted |
| [0019](0019-card-texts-per-language.md) | Give each language of the cards a module of its own, in a folder of the version | accepted |
| [0020](0020-a-public-client-for-the-cloud-link.md) | Prepare the cloud link for a public client with the device grant | replaced by [0025](0025-no-cloud-link.md) |
| [0021](0021-games-as-modes-of-the-practice-game.md) | Play every game of the practice game as a mode of the match frame | accepted |
| [0022](0022-home-assistant-2026-8-as-the-oldest-release.md) | Keep Home Assistant 2026.8 as the oldest supported release | accepted |
| [0023](0023-blueprints-ship-with-the-integration.md) | Ship the blueprints with the integration and keep unchanged copies current | accepted |
| [0024](0024-granboard-over-home-assistant-bluetooth.md) | Connect a Granboard through Home Assistant's Bluetooth, as a dartboard without Autodarts | accepted |
| [0025](0025-no-cloud-link.md) | Remove the cloud link, since Autodarts issues no client IDs to third parties | accepted |
| [0026](0026-a-name-of-its-own.md) | A name of its own: HomeDarts for Autodarts, with the domain homedarts | accepted |
| [0027](0027-the-start-pages-in-dutch-french-and-spanish.md) | The start pages of the website in Dutch, French and Spanish, the rest in English with a note | accepted |
