### Fixed

- **Every dart position comes back after a restart:** a dart that the board measured at the far edge of the area it reports kept its place in the grouping and the aim map only until Home Assistant restarted, because the stored position, rounded to a tenth of a millimetre, lay just past that edge. Now every stored dart comes back, and new tests play each party game, the bull-off, the dart positions and the double rates on after a restart and check that nothing changes.
