### Improved

- **On Board Manager 2.1, *Hand detected* shows at once:** it and the other motion sensors change the moment the board sees it, also for a takeout too short for the read every 2 seconds. The integration follows the second socket of the board, which sends the darts as well, and reads the board less often meanwhile. If that socket is missing or stops sending, it reads every 2 seconds as before. `scripts/capture_board.py` records this socket too. Thanks to @mharmuth, who recorded this socket (#521).
