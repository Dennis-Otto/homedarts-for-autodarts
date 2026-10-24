---
description: "Short answers about HomeDarts for Autodarts: account, devices, online play, privacy, several boards, screens, languages, updates, the new name and switching."
---

# Frequently asked questions

[← Documentation](README.md) · [Deutsch](faq.de.md)

Short answers, each with the page that has the details. Your question is missing? Ask it in [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions).

**Jump to:** [Before you start](#before-you-start) · [Playing](#playing) · [Screens and languages](#screens-and-languages) · [Privacy](#privacy) · [Updates and switching](#updates-and-switching)

## Before you start

### Do I need an Autodarts account or a subscription?

No. The integration talks to the Board Manager on your board PC over your own network, on TCP port 3180. It needs no Autodarts login, password or API key, and no subscription such as Autodarts Plus, and it never changes your board's registration with Autodarts. A dartboard without Autodarts needs nothing from Autodarts at all. [Requirements](installation.md#requirements)

### What do I need?

Home Assistant 2026.8 or newer with [HACS](https://hacs.xyz), and an Autodarts board in your network or any dartboard whose darts you enter on a keypad. New to Home Assistant? [From zero to the scoreboard](getting-started.md) takes you from nothing to the first game on the scoreboard.

### Does it work with Autodarts Desktop, Autodarts X or Lens?

The integration needs a Board Manager that Home Assistant reaches in your network. Board Manager 2 is tested up to 2.0.2, the classic Board Manager 1 works too, and a player reports that Autodarts Desktop 2.0.2 on Linux works. Autodarts Desktop on Windows and Autodarts X have not been tested yet. A [compatibility report](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) tells us how it goes with yours, whether it works or not. [Supported devices](README.md#supported-devices)

Lens scores with the camera of a phone or tablet inside the Autodarts app, without a Board Manager in your network, so the integration can't read its darts. Enter them on the keypad instead. A link through the Autodarts cloud won't come either: Autodarts issues no client IDs to third-party integrations ([decision 0025](decisions/0025-no-cloud-link.md)). [Play without Autodarts](without-autodarts.md)

### Does it cost anything?

No. The integration is free and open source under the [MIT license](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE), with nothing to pay for and no paid tier. [Sponsoring](https://github.com/sponsors/Dennis-Otto) helps the project and is entirely optional.

### Is this an official Autodarts integration?

No. HomeDarts for Autodarts is an unofficial community project, not affiliated with Autodarts, and maintained by [@Dennis-Otto](https://github.com/Dennis-Otto). It uses the local interface of the Board Manager, which the Autodarts team keeps open. Up to version 1.18 it was called Autodarts, until Autodarts asked for a name of its own. [From Autodarts to HomeDarts](new-name.md) · [Credits and license](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/README.md#credits-and-license)

## Playing

### I have no Autodarts board. Can I use it?

Yes. Set up a dartboard without Autodarts and enter every dart on the keypad of the scoreboard, or by voice. Every game, the training and the statistics work. When your dartboard gets Autodarts later, it keeps the games, players and statistics. [Play without Autodarts](without-autodarts.md)

### Can I play online matches?

Yes, on play.autodarts.io as before. The integration sees the darts on your own board then: `dart_detected`, `visit_thrown` and the takeout arrive as usual. Busts, won legs and matches happen in the browser; the optional online bridge brings them into Home Assistant with the browser extension Tools for Autodarts *(experimental)*. [Online matches](online-matches.md)

### The board read a dart wrong. How do I correct it?

Tap the dart on the scoreboard and choose where it landed, on the keys or on a picture of the board. In automations, `homedarts.correct_dart` does the same, and `homedarts.undo_visit` takes the last visit back. [Correct and enter darts](scoreboard.md#correct-and-enter-darts)

### Can I use several boards?

Yes. Every board is an entry and a device of its own, with its own entities, games and statistics, and the automatic dashboard gives every board its views, such as `/scoreboard-1` and `/scoreboard-2`. The actions of the integration then need the board's `config_entry_id`. [Several boards](without-autodarts.md#several-boards)

A club evening can also play [one tournament on several boards at once](games.md#a-tournament-on-several-boards), each board with a match of its own.

A player who throws on two boards has a profile on each. [`homedarts.restore`](entities.md#restore-a-backup-homedartsrestore) with `mode: merge` adds a backup of one board to the other, and the player's numbers add up. [Backups](statistics.md#backups)

## Screens and languages

### Can I show the scoreboard on a TV or a Fire tablet?

Yes: any screen whose browser opens your Home Assistant, such as a tablet on the wall, a Fire tablet among them, a TV with a browser, a small PC or an old phone. Nothing needs to be installed on it. Give the screen a Home Assistant user of its own and open the *Scoreboard* view of the automatic dashboard, in full screen or in a kiosk browser. A TV with a Chromecast or a Google Nest Hub shows it through Home Assistant Cast, without a browser of its own. [Set up the screen](scoreboard.md#set-up-the-screen) · [Home Assistant Cast](scoreboard.md#on-a-tv-with-home-assistant-cast)

### Which languages does it speak, and which voices does the caller have?

English, German, Dutch, French and Spanish, following the language of Home Assistant: setup, entities, cards and the caller. The caller of the scoreboard speaks with a voice of the screen's browser for that language, or with the recorded sounds of a voice pack, such as one of darts-caller or one you record with Piper. The dart caller and practice caller blueprints speak in the language of Home Assistant, through the text-to-speech and the speakers of your Home Assistant. [Languages](README.md#languages) · [Which caller?](automations.md#which-caller)

## Privacy

### What leaves my network?

Nothing, in local mode. Only what you choose talks to the internet: the board search asks the public Autodarts discovery service once, and the online bridge only receives the calls of Tools for Autodarts. Board secrets are never stored, and diagnostics redact board IDs, addresses and player names. Some browsers speak the scoreboard's calls with online voices; an offline voice of the device keeps them at home. [Privacy](how-it-works.md#privacy) · [Security design](security.md)

### Where are my statistics kept?

In Home Assistant's own storage, never in the cloud: the training sessions, the practice game, the personal bests, the player profiles with their matches, and the training calendar with a year of sessions and matches. Deleting the board deletes them after a [backup](statistics.md#backups) of them, and [`homedarts.export`](entities.md#export-training-data-homedartsexport) writes them out for a spreadsheet. [Stored data](how-it-works.md#stored-data)

### I deleted my board. Are my statistics gone?

No. Before a board is deleted, HomeDarts writes a backup of everything it stored to `homedarts/backups` in the media folder. Add the board again, and the repair *A backup of … is available* brings it all back; [`homedarts.restore`](entities.md#restore-a-backup-homedartsrestore) restores any backup. [Backups](statistics.md#backups)

## Updates and switching

### How do I update the Board Manager?

On the board PC, as Autodarts describes. Home Assistant tells you when an update is due: with Board Manager 2, the *Software* update entity shows the installed and the latest version, and a board on Board Manager 1 gets a repair notice for the step to Board Manager 2. The integration itself updates through HACS. [Update to Board Manager 2](installation.md#update-from-board-manager-1-to-board-manager-2) · [Health and connections](entities.md#health-and-connections)

### The integration was called Autodarts. What changes for me?

Since version 2.0 it is HomeDarts for Autodarts, with the domain `homedarts`. After the update, add **HomeDarts for Autodarts** and choose **Take over the boards of the integration Autodarts**: your boards keep their entities, history, statistics and dashboards. Automations and scripts that call the old actions, such as `autodarts.start_game`, need the new names, such as `homedarts.start_game`; a repair lists them. [From Autodarts to HomeDarts](new-name.md)

### I use the original HACSAutodarts. How do I switch?

Install HomeDarts beside it: the original has the domain `autodarts`, HomeDarts the domain `homedarts`, so both run at the same time. Add your board to HomeDarts, move your automations, then delete the entry of HACSAutodarts and remove it in HACS. HomeDarts doesn't take over that entry. [Switch from the original integration](installation.md#switch-from-the-original-integration)

### I use another Autodarts tool. How do I switch?

[Coming from another tool](coming-from.md) covers Autodarts Local, the other Home Assistant integrations, MQTT bridges, darts-caller and darts-wled, and Tools for Autodarts: what each one offers, the entities, events and blueprints that take its place, and how to switch while it stays installed. HomeDarts has a domain of its own, so none of them has to go first.

### Something doesn't work. Where do I get help?

[Troubleshooting](troubleshooting.md) explains the messages, repairs and diagnostics. Ask questions in [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions) and report bugs as an [issue](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose), with the diagnostics of your board; [SUPPORT.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SUPPORT.md) explains where to ask what.
