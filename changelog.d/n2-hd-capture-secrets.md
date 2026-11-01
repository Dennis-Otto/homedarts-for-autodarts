### Fixed

- **A recording of a board on Board Manager 2.1 no longer holds its ID:** `scripts/capture_board.py` knew the board ID only as `board_id`, so the `boardId` of Board Manager 2.1 stayed in `config.json` and `system.json`. It now recognises a key in every spelling and also replaces the serial numbers of the cameras, the name of the link server and every UUID, e-mail address and MAC address. If you recorded a board on 2.1 before, look through the files again before you share them. Thanks to @mharmuth for the report (#521, #526).
