"""When a game on the board starts and when it ends: game_started and game_ended.

A game is what the board plays: a match of X01, a Cricket or a party game, alone
or against others, a match of a tournament, or a training game. It starts once
it is set up, whichever way: the lobby of the card, a voice command, the action
homedarts.start_game, the Game select, New match, a tournament's next match, or
the first dart after a finished match. It ends once it is won, with the darts of
the winning visit pulled; once it is stopped; once another game replaces it; or
once the training session ends after its idle time. A game that goes on after
its end, because its winning visit was undone or a dart lands after the idle
end, starts again as resumed, so that every game_started has one game_ended.

The lifecycle compares the game after each step of the games with the one it
announced, by the number of its match (PracticeGame.serial): the many changes of
one step, such as those of homedarts.start_game, start a game once. It is stored
with the games, so a restart of Home Assistant announces no game again.
"""

from __future__ import annotations

from typing import Any

from .practice import PracticeGame

# A board event: its type and its attributes.
Event = tuple[str, dict[str, Any]]

# How a game is played, as game_started tells it.
MODES = ("practice", "match", "party", "training", "tournament")
# Why a game ended, as game_ended tells it.
REASONS = ("won", "stopped", "replaced", "idle")
# What the store keeps of the game that started last, for its game_ended.
KEPT = ("game", "mode", "players", "names", "bot_player", "started")


def mode(practice: PracticeGame, tournament: bool) -> str:
    """How the game set up on the board is played."""
    if practice.drill is not None:
        return "training"
    if tournament:
        return "tournament"
    if practice.party is not None:
        return "party"
    return "match" if len(practice.players) > 1 else "practice"


class GameLifecycle:
    """The game the board announced last, and whether it ended; see the module."""

    def __init__(self) -> None:
        # The number of the match that game_started announced last, None before
        # the first one.
        self.serial: int | None = None
        # What game_started told of that game, for its game_ended.
        self.game: dict[str, Any] = {}
        # Why the game ended, see REASONS; None while it is played.
        self.ended: str | None = None
        # A store from before the lifecycle: the game it has started then.
        self._adopt = False

    @property
    def running(self) -> bool:
        """Whether the game announced last has not ended yet."""
        return self.serial is not None and self.ended is None

    def restore(self, saved: object) -> None:
        """The lifecycle as stored. A store without one, from before it, takes
        the game on the board as announced, so the update announces nothing."""
        if not isinstance(saved, dict):
            self._adopt = True
            return
        serial, ended, game = saved.get("serial"), saved.get("ended"), saved.get("game")
        self.serial = serial if type(serial) is int and serial >= 0 else None
        self.ended = ended if ended in REASONS else None
        self.game = (
            {key: game[key] for key in KEPT if key in game}
            if isinstance(game, dict)
            else {}
        )

    def stored(self) -> dict[str, Any]:
        return {"serial": self.serial, "ended": self.ended, "game": dict(self.game)}

    def follow(
        self,
        practice: PracticeGame,
        now: str,
        *,
        tournament: bool = False,
        darts: bool = False,
        idle: bool = False,
    ) -> list[Event]:
        """The events that the game on the board brings since the last step:
        the end of the game announced last, and the start of the next one.

        `now` is the time of the step, `tournament` whether the board plays a
        match of a tournament, `darts` whether darts landed in the step, and
        `idle` whether the training session ended after its idle time.
        """
        set_up = practice.kind is not None or practice.drill is not None
        serial = practice.serial if set_up else None
        if self._adopt:
            self._adopt = False
            self.serial = serial
            self.ended = None if practice.winner is None else "won"
            self.game = self._details(practice, tournament, now) if set_up else {}
            return []
        same = serial is not None and serial == self.serial
        events: list[Event] = []
        if self.running:
            if not same:
                events.append(self._end("replaced" if set_up else "stopped"))
            elif practice.winner is not None:
                events.append(self._end("won", practice.victor()))
            elif idle:
                events.append(self._end("idle"))
        elif (
            same
            and practice.winner is None
            and (self.ended == "won" or (self.ended == "idle" and darts))
        ):
            # The winning visit was undone, or a dart came after the idle end.
            events.append(self._start(practice, tournament, now, resumed=True))
        if set_up and not same and practice.winner is None:
            events.append(self._start(practice, tournament, now))
        return events

    def _details(
        self, practice: PracticeGame, tournament: bool, now: str
    ) -> dict[str, Any]:
        lineup = practice.lineup()
        return {
            "game": lineup["game"],
            "mode": mode(practice, tournament),
            **{key: lineup[key] for key in ("players", "names", "bot_player")},
            "started": now,
        }

    def _start(
        self, practice: PracticeGame, tournament: bool, now: str, resumed: bool = False
    ) -> Event:
        details = self._details(practice, tournament, now)
        if resumed:
            # A game that goes on keeps the time it started.
            details["started"] = self.game.get("started") or now
        self.serial, self.ended, self.game = practice.serial, None, details
        # A lineup of its own: Home Assistant keeps the attributes of every
        # state it wrote.
        return (
            "game_started",
            {**practice.lineup(), "mode": details["mode"], "resumed": resumed},
        )

    def _end(self, reason: str, victor: dict[str, Any] | None = None) -> Event:
        self.ended = reason
        game = self.game
        return (
            "game_ended",
            {
                "game": game.get("game"),
                "mode": game.get("mode"),
                "players": game.get("players"),
                "names": list(game.get("names") or []),
                "bot_player": game.get("bot_player"),
                "reason": reason,
                **(victor or {"winner": None, "player": None}),
                "started": game.get("started"),
            },
        )
