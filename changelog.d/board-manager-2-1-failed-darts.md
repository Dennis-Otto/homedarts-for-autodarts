### Bug fixes

- **Board Manager 2.1:** a bouncer no longer counts as a dart in the centre of the bull. Board Manager 2.1 sends a dart it couldn't place at the position (0, 0), which went into the heatmap, the grouping and the aim map, and into the position of *Last dart*. Such a dart now has no position, as a miss had before.
