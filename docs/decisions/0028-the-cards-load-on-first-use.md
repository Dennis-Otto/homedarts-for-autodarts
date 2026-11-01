---
description: "Why every page gets only small stand-ins for the cards, and how a stand-in becomes its card when the card module has loaded."
---

# Load the cards on their first use, with stand-ins that become the cards

- Status: accepted
- Date: 2026-11-01

## Context

The integration gave Home Assistant two modules for every page with `add_extra_js_url`: the small strategy module and `homedarts-card.js`, more than half a megabyte. Home Assistant loads such modules on every page and on every start of its app, for every user, whether the page has a darts card or not. Compressed and cached, the module costs little to download, but the browser has to parse and compile it every time, and a phone feels that. `homedarts-strategy.js` had already shown that a small module can define an element at once and import the rest on first use.

Home Assistant makes a card synchronously: `document.createElement` for the name of the card, then `setConfig`, `hass` and the other properties, and it asks `getCardSize` and `getGridOptions` right away. It keeps its reference to that element, so the element of the small module has to go on working when the card module arrives. The registry of custom elements can't replace a class that is defined.

## Options

1. **Keep loading the card module on every page.** Nothing to change, and every page of every user keeps paying for it.
2. **A wrapper:** the element of the small module draws the real card, under another name, in its own shadow root and hands every property and question on to it. Nothing unusual happens to an element, but there is one more layer in every card, for its size, its events, its styles and everything that looks for it by name, also in the tests, and the wrapper stays for the whole life of the page.
3. **Rebuild:** the element of the small module fires `ll-rebuild` when the module is there, so that Home Assistant makes a new element. But that element would be of the same class of the small module again, as the registry keeps it, so this needs one of the other two options as well.
4. **Stand-ins that become their card:** the element takes the prototype of the card, and the constructors of the card run on it through a base class that returns the element instead of making a new one, as polyfills of custom elements upgrade an element.

## Decision

Option 4. `homedarts-strategy.js` is the only module that the frontend adds to every page and the only one that the integration keeps in the dashboard resources. It defines a stand-in for each of the seven cards and for the strategy and adds the entries of the card picker and of the "Add dashboard" dialog, in every language, from a table that `scripts/sync_translations.py` copies from the texts of the cards.

The first `setConfig`, `hass`, `connectedCallback`, `getStubConfig`, `getConfigForm` or call of the strategy imports `homedarts-card.js` from the same folder. A stand-in keeps what it is given until then, and answers `getCardSize` and `getGridOptions` with what its card answers for the default settings, so a dashboard keeps its layout when the cards arrive. A failed load tells the browser console once and is tried again by the next update of Home Assistant. Settings that the card refuses end in `ll-rebuild`, so Home Assistant shows the error as for any other card.

The address of the small module stays what it was, so a resource in YAML keeps working; the name now says less than the module does, which is a smaller cost than a move of every address.

## Consequences

- A dashboard without a darts card loads less than 20 KB of the integration and never requests `homedarts-card.js`. `tests/test_card.py` and the browser test *a page without cards* hold the integration to that.
- `homedarts-card.js` was a dashboard resource since [decision 0017](0017-modules-in-the-dashboard-resources-for-cast.md). It has to go there too, as every dashboard loads its resources: the integration removes it at its start, and Cast gets the cards through the small module, as a browser does.
- The first card on a page appears a moment later than the page, once the module has loaded; before, it was the page that waited. Nothing shows in its place until then.
- A browser reads `connectedCallback` and `disconnectedCallback` once, from the class that is defined, so those two stay on the stand-in and hand on to the card.
- The sizes and grid options of the cards and the texts of the pickers exist twice. `tests/frontend/strategy-loader.test.mjs` compares the answers of the stand-ins with those of the cards, and `tests/test_sync_translations.py` the table with the texts, whose fix the fix bot makes on its own.
- `homedarts-card.js` still registers everything when it is alone on a page, as in the demo of the website and in its tests, so it needs nothing of the small module.
