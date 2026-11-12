---
description: "The integration Autodarts is now HomeDarts for Autodarts: why it has a new name, and how to take over your boards with entities, statistics and dashboards."
---

# From Autodarts to HomeDarts

[← Documentation](README.md) · [Deutsch](new-name.de.md)

Up to version 1.18 this integration was called *Autodarts*. Autodarts, the maker of the boards, asked the project to stop using its name and logo, which would make it look like an offer of theirs. So since version 2.0 it is **HomeDarts for Autodarts**, with an icon of its own, and it works as before: locally with your Autodarts board, a Granboard or any dartboard by hand.

The new name reaches into Home Assistant itself: the integration has the new domain `homedarts`, so its actions, its cards and its folders have new names too. When you update, HomeDarts takes over the boards you set up under the old name, with everything they have.

**On this page:** [What changes](#what-changes) · [Switch over](#switch-over) · [What the takeover keeps](#what-the-takeover-keeps) · [What you change yourself](#what-you-change-yourself) · [Questions](#questions)

## What changes

| Before | Now |
| --- | --- |
| Autodarts | HomeDarts for Autodarts |
| Actions such as `autodarts.start_game` | `homedarts.start_game` |
| Cards such as `custom:autodarts-scoreboard-card` | `custom:homedarts-scoreboard-card` |
| Dashboard strategy `custom:autodarts` | `custom:homedarts` |
| Board style `autodarts` of the live and heatmap cards | `flat` |
| Media folders `autodarts/highlights`, `autodarts/exports`, `autodarts/voices` | `homedarts/highlights`, `homedarts/exports`, `homedarts/voices` |
| github.com/Dennis-Otto/ha-autodarts | github.com/Dennis-Otto/homedarts-for-autodarts |

The entity IDs stay, and so do your history and statistics.

## Switch over

1. Update the integration in HACS and restart Home Assistant. HACS installs HomeDarts beside the old integration, which keeps running until the takeover. If HACS says *No manifest.json file found 'custom_components/autodarts/manifest.json'*, restart Home Assistant first and update again: HACS finds the new folder of the integration only when it starts.
2. Open **Settings → Devices & services**. A board with Board Manager 2 shows up as discovered: select **Add**. Otherwise select **Add integration → HomeDarts for Autodarts**.
3. Choose **Take over the boards of the integration Autodarts** and confirm. HomeDarts takes over every board at once.
4. Restart Home Assistant once more: the repair *Restart Home Assistant to finish the switch to HomeDarts* does it for you. The restart unloads the old integration, whose files the takeover removed.

## What the takeover keeps

- The settings and options of every board.
- The entities with their IDs, names, areas and customizations, and with them their history and long-term statistics.
- The device of every board.
- The training sessions, the practice games, the players, records and reports.
- The highlights, exports and voice packs in the media folder.
- The cards and the dashboard strategy in every dashboard that Home Assistant keeps: their types are renamed, and the board style `autodarts` becomes `flat`.
- The blueprints: Home Assistant gets those of the new version at the same place, so your automations made from them go on working.

## What you change yourself

The takeover cannot change what you wrote yourself. A repair, *Some automations, scripts or dashboards still use the old name*, lists it:

- **Automations and scripts** that call an action of the old integration: replace `autodarts.` with `homedarts.`, for example `homedarts.next_player`.
- **Dashboards in YAML**: replace `custom:autodarts` with `custom:homedarts` in the types of the cards and the strategy, and `board_style: autodarts` with `board_style: flat`.

The repair stays over the restarts and looks again at each start of Home Assistant: what you changed leaves the list, and once nothing is left, the repair goes by itself. If you would rather keep something as it is, ignore the repair.

## Questions

**Is HomeDarts an offer of Autodarts?** No. HomeDarts for Autodarts is an unofficial community project, not affiliated with Autodarts. It works with Autodarts boards through the interface that the Board Manager offers in your network.

**Do I need to set anything up again?** No. The takeover keeps every board with its entities and statistics. Only automations, scripts and YAML dashboards that use the old actions or cards need the new names.

**Will the cloud link come?** No: Autodarts issues no client IDs to third parties, so HomeDarts works locally. Online matches still reach Home Assistant through [Tools for Autodarts](online-matches.md).
