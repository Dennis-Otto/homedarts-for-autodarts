### Fixed

- **No warning of Home Assistant 2026.10 when a tournament names its boards by their devices:** the tournament on several boards reads the config entry of a board's device the way Home Assistant 2026.10 keeps it, so Home Assistant no longer warns in its log that this stops working in Home Assistant 2027.10. The tests now fail on every such warning of Home Assistant about HomeDarts, also every night against its beta, so the next one is fixed before it reaches your log.
- **The cards keep finding their board's config entry after Home Assistant 2027.10:** the cards read the config entry of a board's device from the field Home Assistant 2026.10 keeps it in, so their actions still reach the right board once Home Assistant drops the two older fields.
