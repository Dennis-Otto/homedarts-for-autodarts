### Features

- **The Board view no longer looks like settings, and its last chip says whose link it is:** the tab of the Board view of the HomeDarts dashboard shows a heart with a pulse line, the state of the board, instead of the cog that Home Assistant uses for its Settings. The board status card calls its last chip *Board cloud*, since it is the board's own link to Autodarts, which HomeDarts doesn't use. Each of its three chips tells in a tooltip, and to a screen reader, what it measures. The entities, their IDs and their names stay as they are, so automations and dashboards keep working.
