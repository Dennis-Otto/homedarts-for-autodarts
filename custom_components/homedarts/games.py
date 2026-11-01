"""The games of a board, without Home Assistant.

BoardGames follows the darts on one board: the training session, the practice
game with the players' progress and personal bests, the tournament, the darts
entered by hand and the bot's darts. The boards of a tournament on several
boards are linked: the board it was started on holds it, and the others play
their matches of it. It books the visits, keeps what an undo
needs and stores itself. Each step returns the board events it brings, in their
order, and takes the time as a parameter, so that the engine runs and is tested
without Home Assistant (tests/test_games.py). AutodartsGamesCoordinator plays it
in Home Assistant, with the timers, the store and the events of a board.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from .bot import BOT_DARTS, Bot
from .bot import aim as bot_aim
from .errors import ActionRefused
from .lifecycle import GameLifecycle
from .local_api import number
from .manual import ManualDarts
from .modes import VisitRefused
from .moments import stamp
from .practice import MAX_PLAYERS, TEAM_PLAYERS, PracticeGame
from .profiles import clean_name, valid_name
from .progress import Progress
from .quality import DetectionQuality
from .rating import fair_starts, team_averages
from .records import PersonalRecords
from .tournament import FINISHED, MAX_BOARDS, TournamentDirector
from .training import TrainingSession, hit_key, segments

# What a part of the games reports: the type of a board event and its attributes.
Event = tuple[str, dict[str, Any]]
# A board event to announce, with its source: the board ("websocket", "poll"),
# Home Assistant ("manual", "training") or the bot.
Announcement = tuple[str, dict[str, Any], str]

# Dart and visit events name the practice game being played, so that callers
# can leave the game to the practice caller.
PLAY_EVENTS = ("dart_detected", "dart_corrected", "visit_thrown", "visit_completed")
DART_EVENTS = ("dart_detected", "dart_corrected")
# Results announced with the dart that decides them, which a correction can
# take back; statistics take them from the booking instead.
RESULT_EVENTS = ("leg_won", "match_won")
# Options that start the match anew, see BoardGames.set_practice_option.
NEW_MATCH_OPTIONS = ("double_in", "bull_off", "teams")


def _throw_positions(state: dict[str, Any]) -> list[tuple[float, float] | None] | None:
    """Board positions of the darts on the board; None for a state training rejects."""
    if segments(state) is None:
        return None
    positions: list[tuple[float, float] | None] = []
    for dart in state.get("throws", []):
        coords = dart.get("coords")
        x, y = (
            number(coords.get(axis)) if isinstance(coords, dict) else None
            for axis in ("x", "y")
        )
        positions.append(None if x is None or y is None else (float(x), float(y)))
    return positions


def _aligned(
    positions: list[tuple[float, float] | None], count: int
) -> list[tuple[float, float] | None]:
    """The positions of the last darts, None for those without one."""
    known = positions[-count:] if count else []
    aligned: list[tuple[float, float] | None] = [None] * (count - len(known))
    aligned.extend(known)
    return aligned


class Reports(Protocol):
    """The weekly report and the training journal, which count what the games
    announce and take part in an undo; see BoardReports."""

    def observe(
        self,
        events: list[Event],
        now: datetime,
        booked: list[Event] | None = None,
    ) -> None: ...

    def checkpoint(self) -> dict[str, Any]: ...

    def rewind(self, checkpoint: dict[str, Any]) -> None: ...

    def forget(self, name: str) -> None: ...

    def rename(self, name: str, new_name: str) -> None: ...


@dataclass
class Checkpoint:
    """Everything a player's visit changes when it is booked, as it was before,
    to undo the visit: the practice game, where the visit's darts landed, the
    progress of the players at the board, the weekly report and the journal,
    and the personal bests."""

    practice: dict[str, Any]
    positions: list[tuple[float, float] | None]
    progress: dict[str, Any]
    reports: dict[str, Any]
    records: dict[str, Any]


class BoardGames:
    """The training, the games and the statistics of one board.

    The time `now` that steps take is that of Home Assistant's time zone, in
    which a day of training begins and ends.
    """

    def __init__(
        self, reports: Reports, now: datetime, rng: random.Random | None = None
    ) -> None:
        self.training = TrainingSession(now)
        self.practice = PracticeGame()
        self.quality = DetectionQuality()
        self.records = PersonalRecords()
        self.progress = Progress()
        self.tournament = TournamentDirector()
        # The start and the end of the games, for game_started and game_ended.
        self.life = GameLifecycle()
        # The key of the board, the ID of its entry in Home Assistant, by which
        # the boards of a tournament on several boards know each other.
        self.key = ""
        # A tournament on several boards: the other boards of the tournament
        # this board holds, by their key while they are loaded; the board that
        # holds the tournament this board plays matches of; and the events of
        # the matches on the other boards, which the holding board announces.
        self.guests: dict[str, BoardGames] = {}
        self.host: BoardGames | None = None
        self.board_events: list[Announcement] = []
        # Corrections, darts entered by hand and the bot's darts in the visit.
        self.manual = ManualDarts()
        # Its darts can be seeded, for tests and the recording of the demo.
        self.bot = Bot(rng)
        self._reports = reports
        # Raised with every change of the training or the games, which the
        # coordinator then saves; the entities' data carries it.
        self.revision = 0
        # Raised whenever the next match of a tournament is due at another time.
        self.fixtures = 0
        # Board positions of the darts in the last state the training took.
        self._positions: list[tuple[float, float] | None] = []
        # The game and the statistics before the last visit of a player was
        # booked, to undo the visit.
        self._undo: Checkpoint | None = None
        # The events of the step being taken, in order; a step returns them,
        # and they stay here for drain should the step fail halfway.
        self._announced: list[Announcement] = []

    # -- stored data -------------------------------------------------------------

    def restore(self, saved: object, now: datetime) -> None:
        """The games as stored; a part that is missing or broken starts anew."""
        stored = saved if isinstance(saved, dict) else {}
        self.training.restore(saved if isinstance(saved, dict) else None)
        self.practice.restore(stored.get("practice"))
        self.records.restore(stored.get("records"))
        self.progress.restore(stored.get("progress"), self.practice.profiles, now)
        self.tournament.restore(stored.get("tournament"))
        self.practice.hold = self.tournament.waiting
        self.life.restore(stored.get("lifecycle"))
        if isinstance(saved, dict) and "lifecycle" not in saved:
            self.life.adopt(
                self.practice,
                self.tournament.running and not self.tournament.waiting,
                stamp(now),
            )

    def stored(self) -> dict[str, Any]:
        """Training sessions, the practice game, personal bests, the players'
        progress and the tournament, saved together."""
        return {
            **self.training.stored(),
            "practice": self.practice.stored(),
            "records": self.records.stored(),
            "progress": self.progress.stored(),
            "tournament": self.tournament.stored(),
            "lifecycle": self.life.stored(),
        }

    # -- the darts on the board --------------------------------------------------

    def interrupts_bot(self, state: dict[str, Any]) -> bool:
        """Whether a player throws while the bot is at the board, which then
        throws the rest of its visit at once, see follow_visit."""
        return self.practice.bot_up and bool(self.manual.board_darts(state))

    def follow_visit(
        self, data: dict[str, Any], state: dict[str, Any], source: str, now: datetime
    ) -> list[Announcement]:
        """Follow the visit as Home Assistant knows it: the board's darts with
        the corrections, the darts entered by hand and the bot's darts.

        Writes them into data["throws"] with the snapshots of the games for
        the entities, and returns the events they bring.
        """
        # The board's darts show, should the games fail.
        data.pop("throws", None)
        if self.interrupts_bot(state):
            self._finish_bot(data, state, now)
        effective = self.manual.apply(state)
        self._track(data, effective, source, now)
        data["throws"] = self._visit_throws(effective)
        return self.drain()

    def drain(self) -> list[Announcement]:
        """The events announced since the last drain, in order: those of a
        step that failed halfway, too."""
        announced, self._announced = self._announced, []
        return announced

    def _track(
        self, data: dict[str, Any], state: dict[str, Any], source: str, now: datetime
    ) -> None:
        """Training, practice game and records follow the darts on the board."""
        announced = self._announced
        changed = False
        observed = self.training.observe(state, now)
        completed = any(kind == "visit_completed" for kind, _ in observed)
        # The weekly report and the personal bests before they count a
        # completed visit, to undo it.
        reports = self._reports.checkpoint() if completed else {}
        records = self.records.checkpoint() if completed else {}
        for kind, attributes in self._recorded(observed, now):
            changed = True
            self.quality.record(kind, attributes)
            if kind in DART_EVENTS and attributes.get("total"):
                # A visit entered as its score announces itself, not its made-up darts.
                continue
            if kind in PLAY_EVENTS:
                attributes = {
                    **attributes,
                    "game": self.practice.kind,
                    "name": self.practice.thrower,
                }
            announced.append((kind, attributes, source))
            if kind == "visit_completed":
                self._checkpoint(attributes, reports, records)
                self._book_visit(source, now, bot=attributes.get("bot") is True)
        if (positions := _throw_positions(state)) is not None:
            self._positions = positions
        # The visit is the last darts on the board; positions of rejected states
        # never shift onto them.
        visit = self.training.visit()
        aligned = _aligned(self._positions, len(visit))
        for kind, attributes in self._recorded(
            self.practice.track(visit, aligned, now=now), now
        ):
            changed = True
            announced.append((kind, attributes, source))
        darts = any(kind in DART_EVENTS for kind, _ in observed)
        for kind, attributes in self._game_events(now, darts=darts):
            changed = True
            announced.append((kind, attributes, source))
        self._publish(data, changed)

    def _book_visit(
        self, source: str, now: datetime, bot: bool = False, empty: bool = False
    ) -> None:
        """Book the pulled darts in the practice game and the players' progress;
        with empty, the player at the board passes, see PracticeGame.finish_visit."""
        pending = self.progress.before(self.practice)
        # The bot's darts are nobody's training.
        if self.training.active and not bot:
            self.progress.session_visit(pending.booking)
        decided = self.practice.winner is not None
        events = self.practice.finish_visit(empty, now=now)
        booked = self._booked(pending.legs_total, decided)
        events += self.progress.after(pending, self.practice, now)
        # A won game ends before a tournament starts its next match.
        ended = self._game_events(now)
        # A tournament takes the result once the practice game booked it; the
        # board holding a tournament on several boards announces its events.
        fixture = self._fixture(now)
        if self.host is not None:
            self.host.board_events += [
                (kind, details, source) for kind, details in fixture
            ]
        else:
            events += fixture
        self._announced += [
            (kind, details, source)
            for kind, details in [*self._recorded(events, now, booked), *ended]
        ]

    def _recorded(
        self, events: list[Event], now: datetime, booked: list[Event] | None = None
    ) -> list[Event]:
        """The events, each followed by the personal bests or daily goal it brings.

        Legs and matches count for the records and the weekly report once the
        practice game booked them, see _booked: a correction can take back the
        leg_won and match_won announced with a winning dart.
        """
        result: list[Event] = []
        for kind, attributes in events:
            if kind == "session_started":
                # The positions of a session start over with it, like its hits.
                self.progress.session_started()
            result.append((kind, attributes))
            # The bot sets no personal bests and throws no darts of the day.
            if not attributes.get("bot") and kind not in RESULT_EVENTS:
                result.extend(self.records.observe(kind, attributes, now))
        for kind, attributes in booked or []:
            if not attributes.get("bot"):
                result.extend(self.records.observe(kind, attributes, now))
        self._reports.observe(result, now, booked)
        return result

    def _booked(self, legs_total: int, decided: bool) -> list[Event]:
        """The leg and the match that booking a visit ended, if any."""
        practice = self.practice
        booked: list[Event] = []
        if practice.legs_total > legs_total and practice.legs:
            booked.append(("leg_won", practice.legs[0]))
        if practice.winner is not None and not decided:
            booked.append(("match_won", {"game": practice.kind}))
        return booked

    def _checkpoint(
        self, visit: dict[str, Any], reports: dict[str, Any], records: dict[str, Any]
    ) -> None:
        """The game before a player's visit is booked, to undo the visit; the
        bot's visits are undone together with the visit before them."""
        if visit.get("bot"):
            return
        self._undo = Checkpoint(
            practice=self.practice.checkpoint(),
            positions=_aligned(self._positions, visit["darts"]),
            # The visit, a leg it ends and training games book for these players.
            progress=self.progress.checkpoint(self.practice.names),
            reports=reports,
            records=records,
        )

    def _publish(self, data: dict[str, Any], announced: bool) -> None:
        """Snapshots for the entities; a change raises the revision."""
        training, practice = self.training.snapshot(), self.practice_snapshot()
        # The first snapshots only show what was restored.
        if announced or (
            "training" in data
            and (training != data["training"] or practice != data.get("practice"))
        ):
            self.revision += 1
        data.update(
            training=training,
            practice=practice,
            quality=self.quality.snapshot(),
            revision=self.revision,
        )

    def _visit_throws(self, state: dict[str, Any]) -> list[Any]:
        """The darts for the cards, each dart of the visit with its number."""
        throws = state.get("throws")
        numbers = {
            slot: number for number, slot in enumerate(self.training.visit_slots(), 1)
        }
        return [
            {**throw, "dart": numbers[slot]}
            if slot in numbers and isinstance(throw, dict)
            else throw
            for slot, throw in enumerate(throws if isinstance(throws, list) else [])
        ]

    def practice_snapshot(self) -> dict[str, Any]:
        """The practice game for the entities, and whether the last visit of a
        player can be undone now."""
        undo = self._undo is not None and self.training.can_undo()
        return {**self.practice.snapshot(), "undo": undo}

    def snapshots(self) -> dict[str, Any]:
        """The training session and the practice game for the entities, with
        the revision of the games."""
        return {
            "training": self.training.snapshot(),
            "practice": self.practice_snapshot(),
            "revision": self.revision,
        }

    def changed(self, events: list[Event], now: datetime) -> list[Event]:
        """A change of the session or the game, made in Home Assistant: the
        events it brings, with the personal bests they set. A change cannot
        be undone visit by visit."""
        recorded = self._recorded(events, now)
        idle = any(
            kind == "session_ended" and attributes.get("reason") == "idle"
            for kind, attributes in events
        )
        self._undo = None
        self.revision += 1
        return recorded + self._game_events(now, idle=idle)

    def _game_events(
        self, now: datetime, *, darts: bool = False, idle: bool = False
    ) -> list[Event]:
        """The start and the end of the games since the last step, see
        GameLifecycle.follow."""
        director, board = self._seat()
        return self.life.follow(
            self.practice,
            stamp(now),
            tournament=director.running and not director.waiting_at(board),
            darts=darts,
            idle=idle,
        )

    def follow_game(self, now: datetime) -> list[Announcement]:
        """The start and the end of the games after another board of a
        tournament on several boards changed them, see moved."""
        return [
            (kind, attributes, "training")
            for kind, attributes in self._game_events(now)
        ]

    # -- tournaments -------------------------------------------------------------

    def _seat(self) -> tuple[TournamentDirector, str | None]:
        """The tournament the board plays: its own, or that of the board holding
        a tournament on several boards, with the key of this board in it."""
        if self.host is not None:
            return self.host.tournament, self.key
        return self.tournament, None

    def tournament_state(self) -> str:
        """The stage of the tournament the board plays, see TournamentDirector.state."""
        director, board = self._seat()
        return director.state(board)

    def tournament_snapshot(self) -> dict[str, Any]:
        """The tournament the board plays, as the board sees it."""
        director, board = self._seat()
        return director.snapshot(board)

    @property
    def several_boards(self) -> bool:
        """Whether the board holds a tournament on several boards."""
        tournament = self.tournament.tournament
        return tournament is not None and tournament.several

    def board_free(self) -> bool:
        """Whether the next match of a tournament can start at the board: no
        darts are left on it and the practice game makes way."""
        director, board = self._seat()
        return not self.training.visit() and director.free(self.practice, board)

    def _fixture(self, now: datetime) -> list[Event]:
        """After a visit: the result of a tournament match, and the next match
        once the pause is over, no darts are left on the board and no other
        game is being played."""
        utc = now.astimezone(UTC)
        director, board = self._seat()
        events = director.booked(self.practice, utc, board)
        due = director.due(utc, board) and self.board_free()
        if due:
            director.next_match(self.practice, utc, board)
        if events or due:
            # A result the tournament took, or its next match, cannot be undone.
            self._undo = None
            self.fixtures += 1
        return events

    # -- tournaments on several boards -------------------------------------------

    def start_tournament(
        self,
        now: datetime,
        name: str = "",
        boards: list[tuple[str, str, BoardGames]] | None = None,
        **options: Any,
    ) -> list[Event]:
        """Draw a tournament, see TournamentDirector.start. With other boards,
        each with its key and name, a tournament on several boards that this
        board, called by `name`, holds: every board plays a match at once if
        one is ready for it."""
        if self.host is not None:
            raise ActionRefused(
                "board_in_tournament", board=self.host.tournament.name()
            )
        others: list[tuple[str, str, BoardGames]] = []
        for key, called, games in boards or []:
            if games is self or any(key == other for other, _, _ in others):
                continue
            if games.host is not None or games.tournament.running:
                raise ActionRefused("board_in_tournament", board=called)
            others.append((key, called, games))
        if len(others) >= MAX_BOARDS:
            raise ActionRefused("tournament_boards", max=str(MAX_BOARDS))
        seats = [(self.key, name), *((key, called) for key, called, _ in others)]
        director = self.tournament
        if not director.running:
            # The boards of a finished tournament go back to their settings first.
            self._release_guests()
        events = director.start(
            self.practice, now, boards=seats if others else None, **options
        )
        utc = now.astimezone(UTC)
        for key, _, games in others:
            # A tournament the board finished before gives way to this one.
            if games.tournament.tournament is not None:
                games.tournament.stop(games.practice)
            games.host = self
            self.guests[key] = games
            director.join(games.practice, key, utc)
            games.moved()
        return events

    def moved(self) -> None:
        """A change of the games made on another board of a tournament on several
        boards, which cannot be undone visit by visit."""
        self._undo = None
        self.revision += 1

    def stop_tournament(self) -> list[BoardGames]:
        """Stop the tournament this board holds, see TournamentDirector.stop:
        the other boards of a tournament on several boards go back to their
        practice settings too, and are returned."""
        director = self.tournament
        released = self._release_guests() if director.tournament else []
        director.stop(self.practice)
        return released

    def next_tournament_match(self, now: datetime) -> None:
        """Start the next match at this board now, see TournamentDirector.next_match."""
        director, board = self._seat()
        director.next_match(self.practice, now.astimezone(UTC), board)

    def _release_guests(self) -> list[BoardGames]:
        """The other boards go back to their practice settings and leave."""
        director = self.tournament
        released = list(self.guests.values())
        for key, games in self.guests.items():
            director.release(games.practice, key)
            games.host = None
            games.moved()
        self.guests.clear()
        return released

    def settle_boards(self, now: datetime) -> list[BoardGames]:
        """A tournament on several boards that this board holds, after a change
        on one of its boards: every board whose pause is over takes its next
        match once it is clear, and after the last match every board goes back
        to its practice settings. Returns the boards whose games changed, this
        one too."""
        director = self.tournament
        tournament = director.tournament
        if tournament is None or not tournament.several:
            return []
        if tournament.status == FINISHED:
            changed = [*self._release_guests()]
            if self.practice.hold or director.saved is not None:
                director.release(self.practice)
                self.moved()
                changed.insert(0, self)
            return changed
        utc = now.astimezone(UTC)
        changed = []
        for key in [None, *director.guests()]:
            games = self if key is None else self.guests.get(key)
            if games is None or not director.due(utc, key) or not games.board_free():
                continue
            director.next_match(games.practice, utc, key)
            games.moved()
            changed.append(games)
        return changed

    def next_fixture(self) -> datetime | None:
        """When the next match of the tournament this board holds is due at one
        of its boards that are loaded; None without one."""
        due = [
            at
            for board, at in self.tournament.due_boards()
            if board is None or board in self.guests
        ]
        return min(due, default=None)

    def attach(self, games: BoardGames) -> bool:
        """Another board of the tournament on several boards this board holds is
        back, after a restart or a reload: it plays its matches again. False for
        a board that is no part of it, or that plays a tournament of its own."""
        director = self.tournament
        if (
            games is self
            or games.key not in director.guests()
            or games.key in self.guests
        ):
            return False
        if games.tournament.running or games.host is not None:
            # The board left for a tournament of its own, or of another board:
            # others play its match.
            director.vacate(games.key)
            return False
        self.guests[games.key] = games
        games.host = self
        director.attach(games.practice, games.key)
        return True

    def leave(self) -> list[BoardGames]:
        """The board unloads: the boards of its tournament on several boards
        lose sight of it until it is back. Returns those boards."""
        others = list(self.guests.values())
        for games in others:
            games.host = None
        self.guests.clear()
        if (host := self.host) is not None:
            host.guests.pop(self.key, None)
            self.host = None
            others.append(host)
        return others

    def take_board_events(self) -> list[Announcement]:
        """The events of the matches on the other boards of the tournament this
        board holds, to announce."""
        events, self.board_events = self.board_events, []
        return events

    # -- settings and players ----------------------------------------------------

    def set_practice_option(self, option: str, enabled: bool) -> None:
        """Routes and the bull-off rule apply at once, and double out until the
        first dart of a leg, otherwise from the next leg; double in, the
        bull-off and teams start anew."""
        self.practice.set_option(option, enabled)
        if option in NEW_MATCH_OPTIONS:
            self.practice.new_match()

    def set_x01_rule(self, rule: str, value: str | int) -> None:
        """An X01 rule: the Out mode until the first dart of a leg, otherwise
        from the next leg; another In mode, bull mode or round limit starts
        the match anew."""
        if self.practice.set_rule(rule, value) and rule != "out_mode":
            self.practice.new_match()

    def delete_player(self, name: str) -> bool:
        """Forget a player profile, and the name in the records, the player
        slots and the next tournament; False when there is no profile by that
        name. A player of the tournament being played stays."""
        if self.host is not None:
            self.host.tournament.check(name)
        self.tournament.forget(name)
        deleted = self.practice.profiles.delete(name)
        if deleted:
            self.practice.forget(name)
            self.records.forget(name)
            self.progress.forget(name)
            self._reports.forget(name)
        return deleted

    def rename_player(self, name: str, new_name: str, now: datetime) -> dict[str, Any]:
        """Give a player profile a new name wherever the games keep a name: the
        profile, the progress and the badges, the records, the report and the
        calendar, the player slots and the tournaments. A name that another
        profile has already merges the two players into that profile, as if
        one name had thrown every dart. A player of the tournament being
        played keeps the name, and two names that both play the match being
        played cannot merge. The old and the new name, and whether the
        profiles merged, for the event player_renamed."""
        profiles = self.practice.profiles
        spelled, old = clean_name(new_name), profiles.spelled(name)
        if clean_name(name).casefold() not in profiles.players:
            raise ActionRefused("unknown_player", name=name.strip())
        if not spelled:
            raise ActionRefused("invalid_player_name")
        # The profile's own spelling, so every store finds the name the way
        # the profile keeps it, also for a name with characters no name has.
        if self.host is not None:
            self.host.tournament.check(old)
        self.tournament.check(old)
        if not self.practice.rename_player(old, spelled):
            raise ActionRefused(
                "merge_in_play", name=old, other=profiles.spelled(spelled)
            )
        merged = profiles.rename(old, spelled) is True
        self.tournament.rename(old, spelled)
        self.progress.rename(old, spelled, profiles, now)
        self.records.rename(old, spelled)
        self._reports.rename(old, spelled)
        return {"old": old, "new": spelled, "merged": merged}

    def start_game(
        self,
        game: int | str,
        names: list[str] | None = None,
        legs: int | None = None,
        sets: int | None = None,
        double_out: bool | None = None,
        double_in: bool | None = None,
        bull_off: bool | None = None,
        bull_off_distance: bool | None = None,
        teams: bool | None = None,
        three_in_a_bed: bool | None = None,
        start_scores: list[int] | None = None,
        fair_start: bool = False,
        holes: int | None = None,
        rounds: int | None = None,
        bot_level: int | None = None,
        in_mode: str | None = None,
        out_mode: str | None = None,
        bull_mode: str | None = None,
        max_rounds: int | None = None,
        halve_on_miss: bool | None = None,
        order: str | None = None,
        target_score: int | None = None,
    ) -> None:
        """Set up a practice game in one step; unset values stay as they are.
        Double in and double out set the In and Out mode to double or straight.
        A fair start sets the start scores of an X01 game from the averages."""
        practice = self.practice
        if names and not all(valid_name(name) for name in names):
            raise ActionRefused("invalid_player_name")
        for option, value in (
            ("double_out", double_out),
            ("double_in", double_in),
            ("bull_off", bull_off),
            ("bull_off_distance", bull_off_distance),
            ("teams", teams),
            ("three_in_a_bed", three_in_a_bed),
            ("bermuda_halve_on_miss", halve_on_miss),
        ):
            if value is not None:
                practice.set_option(option, value)
        for party_rule, chosen in (
            ("round_the_world_order", order),
            ("gotcha_target", target_score),
        ):
            if chosen is not None:
                practice.set_party_rule(party_rule, chosen)
        for rule, setting in (
            ("in_mode", in_mode),
            ("out_mode", out_mode),
            ("bull_mode", bull_mode),
            ("max_rounds", max_rounds),
        ):
            if setting is not None:
                practice.set_rule(rule, setting)
        if names:
            for index in range(len(practice.names)):
                practice.set_name(index, names[index] if index < len(names) else "")
        if fair_start and isinstance(game, int):
            start_scores = self._fair_starts(
                game,
                len(names) if names else practice.humans,
                practice.bot_level if bot_level is None else bot_level,
            )
        if start_scores is not None:
            # Players without a start score of their own play the game's.
            for index in range(len(practice.starts)):
                own = start_scores[index] if index < len(start_scores) else 0
                practice.set_start(index, own)
        practice.set_rounds(holes, rounds)
        practice.set_format(legs, sets)
        # The players besides the bot, counted before a new level of the bot
        # changes which seat is its own.
        humans = practice.humans
        if bot_level is not None:
            practice.bot_level = bot_level
        practice.play(game, len(names) if names else humans)

    def _fair_starts(self, game: int, humans: int, bot_level: int) -> list[int]:
        """The fair start score of each seat, or of each team: the players by
        their recent average, and the bot by its level, which is its average."""
        practice = self.practice
        # Players of a party game who get no seat here count for nobody.
        humans = min(humans, MAX_PLAYERS - bool(bot_level))
        averages: list[float | None] = [
            practice.profiles.recent_average(name) for name in practice.names[:humans]
        ]
        if bot_level:
            averages.append(float(bot_level))
        if practice.teams and len(averages) == TEAM_PLAYERS:
            averages = team_averages(averages)
        return fair_starts(game, averages)

    # -- corrections and darts entered by hand -----------------------------------

    def correct_dart(
        self,
        dart: int,
        segment: dict[str, Any],
        position: tuple[float, float] | None = None,
    ) -> None:
        """Put a dart of the current visit into another bed, at the position
        given; without one, the dart has no position. The bot's darts stay."""
        slots = self.training.visit_slots()
        if not 1 <= dart <= len(slots):
            raise ActionRefused("no_dart", dart=str(dart))
        place = slots[dart - 1]
        kind, index = self.manual.sources[place]
        if kind == "extra" and self.manual.extras[index].dart.get("bot"):
            raise ActionRefused("bot_dart")
        self.manual.correct(place, segment, position)

    def _check_entry(self) -> None:
        """Darts are entered by hand only with the keypad on, and never for the bot."""
        if not self.practice.manual_entry:
            raise ActionRefused("manual_entry_off")
        if self.practice.bot_up:
            raise ActionRefused("bot_turn")

    def throw_dart(
        self, segment: dict[str, Any], position: tuple[float, float] | None = None
    ) -> None:
        """A dart entered by hand, as if the board had detected it there."""
        self._check_entry()
        if len(self.training.visit()) >= BOT_DARTS:
            raise ActionRefused("visit_full")
        self.manual.add(segment, position, "manual")

    def enter_visit(
        self,
        state: dict[str, Any],
        points: int,
        darts: int | None = None,
        at_double: int | None = None,
        checkout: bool = False,
    ) -> None:
        """An X01 visit entered as its score, or with `checkout` as the checkout
        of what is left, while the board in `state` holds no darts of the visit:
        the darts entered by hand in the visit so far give way to it. The visit
        ends once it was followed, see AutodartsGamesCoordinator.async_enter_visit."""
        self._check_entry()
        if self.manual.board_darts(state):
            raise ActionRefused("visit_on_board")
        try:
            visit = self.practice.score_visit(points, darts, at_double, checkout)
        except VisitRefused as err:
            raise ActionRefused(err.key, **err.placeholders) from err
        self.manual.extras = []
        for dart in visit:
            self.manual.add(dart, None, "manual")

    def next_player(self, now: datetime) -> list[Announcement]:
        """End the visit without pulling the darts; without darts, pass."""
        if self.training.visit() or self.manual.extras:
            self.manual.end_visit()
            return []
        if self.practice.passes():
            # Booked like a visit: a pass can end a party game's last round.
            self._book_visit("manual", now, empty=True)
            return self.drain()
        raise ActionRefused("empty_visit")

    def undo_visit(self, now: datetime) -> list[Announcement]:
        """Take the last visit of a player back as the current visit, with the
        game as it was before; the bot's visits after it are undone, too."""
        darts = self.training.undo_visit() if self._undo else None
        if self._undo is None or darts is None:
            raise ActionRefused("undo_unavailable")
        checkpoint, self._undo = self._undo, None
        # Booked again once it ends, the visit must not count twice.
        self.progress.rewind(checkpoint.progress)
        self._reports.rewind(checkpoint.reports)
        self.records.rewind(checkpoint.records)
        self.practice.rewind(checkpoint.practice, darts, checkpoint.positions, now)
        self.manual.replay(darts, checkpoint.positions)
        undone = {
            "darts": len(darts),
            "score": sum(dart["number"] * dart["multiplier"] for dart in darts),
            "segments": [dart["name"] or hit_key(dart) for dart in darts],
            "game": self.practice.kind,
            "name": self.practice.thrower,
        }
        return [("visit_undone", undone, "manual")]

    # -- the bot -----------------------------------------------------------------

    def bot_step(self) -> None:
        """The bot's next dart, or the end of its visit once it is over."""
        if self._bot_done():
            self.manual.end_visit()
        else:
            self._bot_throw()

    def _bot_done(self) -> bool:
        """Whether the bot's visit is over: its darts thrown, a bust or a win."""
        snapshot = self.practice.snapshot()
        thrown = self.manual.bot_darts()
        if snapshot["bull_off"]:
            return thrown >= 1
        return bool(thrown >= BOT_DARTS or snapshot.get("bust") or snapshot["won"])

    def _bot_throw(self) -> None:
        dart, position = self.bot.throw(
            bot_aim(self.practice.snapshot()),
            self.practice.bot_level,
            cricket=self.practice.cricket is not None,
        )
        self.manual.add(dart, position, "bot")

    def _finish_bot(
        self, data: dict[str, Any], state: dict[str, Any], now: datetime
    ) -> None:
        """The bot throws the rest of its visit at once and ends it, before the
        new darts on the board count for the next player."""
        before = self.manual.held(state)
        while not self._bot_done():
            self._bot_throw()
            self._track(data, self.manual.apply(before), "bot", now)
        self.manual.end_visit()
        self._track(data, self.manual.apply(before), "bot", now)
