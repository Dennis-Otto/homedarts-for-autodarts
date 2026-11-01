---
description: "Why the integration keeps both modules of its cards in the dashboard resources, so that Home Assistant Cast shows the cards on a TV."
---

# Keep the modules of the cards in the dashboard resources, for Home Assistant Cast

- Status: accepted; since [0028](0028-the-cards-load-on-first-use.md), only the small module is a resource
- Date: 2026-10-18

## Context

The integration loads its cards on every page of Home Assistant as extra modules of the frontend (`add_extra_js_url`), so nobody adds a dashboard resource, and the version in their address keeps browsers from an old card. Home Assistant Cast shows a dashboard on a TV through a Chromecast, or on a Google Nest Hub. Its receiver is a page of its own at cast.home-assistant.io: it loads the dashboard resources, never the extra modules (`cast/src/receiver/layout/hc-main.ts` of Home Assistant's frontend), and it defines `hc-main` instead of the app element `home-assistant`, which both modules waited for. The scoreboard, made for a TV at the board, said *Custom element doesn't exist* there, and the automatic dashboard was not built.

## Options

1. **Only document it:** whoever casts adds two resources by hand. Everyone who casts has to find this first, and a resource without the version kept an old card in the browser for a month after an update.
2. **Keep both modules in the resources that Home Assistant stores,** at the address with the version: added and brought up to date at every start, removed with the last board. Browsers load the same address once, so nothing changes for them.
3. **Only resources,** without extra modules: one way of loading, but resources load only with a dashboard, so the card picker and the strategy would come later, and resources in YAML would need two lines from everyone.

## Decision

Option 2. When Home Assistant keeps the dashboard resources, as it does by default, the integration keeps one module resource for `/autodarts/autodarts-strategy.js` and one for `/autodarts/autodarts-card.js`, each with the query of its version. It finds its own by their path, whatever their query, brings them to the current address in their place, removes duplicates and leaves every other resource alone; a lock lets boards that are set up side by side add each one once. Removing the last board removes both. Since [0019](0019-card-texts-per-language.md), the version is a folder of the address instead of its query, which the resources follow.

Resources in YAML stay the user's: the documentation names the two lines. An address without the current version is sent with `Cache-Control: no-cache`, so a browser revalidates it on every load and never keeps an old module there. Both modules wait for `home-assistant` or `hc-main`, and pictures that Home Assistant serves get its address through `hass.hassUrl`, because the receiver has an address of its own.

## Consequences

- The cards and the automatic dashboard work on Cast without a step by the user; *Settings → Dashboards → Resources* lists the two modules.
- A user who deletes the two resources gets them back at the next start; removing the last board removes them.
- Browsers load each module once, because the address of the extra module and of the resource is the same.
- With resources in YAML and the two lines, browsers load the cards a second time under the address without the version; only those who cast need the lines.
- Whatever the cards load later must not depend on the address of the page: on Cast, a relative address points to cast.home-assistant.io.
