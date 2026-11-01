### Performance

- **Pages without a darts card open faster:** every page of Home Assistant and every start of the companion app used to load and parse all the cards, more than half a megabyte of JavaScript, also without a darts card anywhere. A page now loads a small module of less than 20 KB, and the cards follow with the first darts card on a page. Cards, their editors, the card picker, the automatic dashboard and Home Assistant Cast work as before. If you keep your dashboard resources in YAML, the line for `homedarts-card.js` can go.
