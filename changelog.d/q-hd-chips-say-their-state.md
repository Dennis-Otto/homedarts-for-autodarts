### Bug fixes

- **The connection chips show and say their state, not only by the colour of their dot:** on the board status card and the live card, a chip keeps its filled green dot while its link is up, shows a grey ring while it is down, and a grey dash while it is unavailable or unknown, so the states read for colour-blind players and in grey too. A screen reader now says each chip's label and its state, such as *Realtime: Disconnected* or *Cameras: Running*, in the words that Home Assistant shows for the entity, in all five languages of the cards. The tooltips stay as they are.
