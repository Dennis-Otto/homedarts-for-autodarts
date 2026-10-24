"""Play the games of a board in Home Assistant: their timers, store and events.

BoardGames knows nothing of Home Assistant. AutodartsGamesCoordinator brings it
the darts and the actions of Home Assistant, announces the board events it
returns, saves it after a change, and keeps the timers of the games: the end of
an idle session, the next match of a tournament, the bot's darts and the
players' aim models. Two coordinators extend it side by side:
AutodartsLocalCoordinator adds the Board Manager, and AutodartsManualCoordinator
is a dartboard without Autodarts, with no transport at all. Code that needs the
Board Manager asks for AutodartsLocalCoordinator by its type.

The boards of a tournament on several boards find each other by their entries:
the board holding the tournament keeps its timer, starts the matches that are
due on its boards and announces their results.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.core import Event as CoreEvent
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_utc_time,
    async_track_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .calls import Caller
from .const import DOMAIN, event_signal
from .errors import ActionRefused
from .games import Announcement, BoardGames, Event
from .positions import Aim
from .quality import RECALIBRATE_RATE, RECOVERED_RATE
from .report import BoardReports
from .storage import BoardStore
from .tournament import TournamentDirector

_LOGGER = logging.getLogger(__name__)
# A tournament match that is due waits this long before it looks again whether
# the board is clear and no other game is played.
FIXTURE_RETRY = timedelta(seconds=5)


def _work_out(jobs: list[Callable[[], Aim]]) -> list[Aim]:
    """Aim models, in an executor."""
    return [job() for job in jobs]


def board_of(hass: HomeAssistant, key: str) -> AutodartsGamesCoordinator | None:
    """The games of the board of an entry, while it is loaded."""
    entry = hass.config_entries.async_get_entry(key)
    board = getattr(getattr(entry, "runtime_data", None), "local", None)
    if isinstance(board, AutodartsGamesCoordinator) and board.loaded:
        return board
    return None


def _boards(hass: HomeAssistant) -> list[AutodartsGamesCoordinator]:
    """The games of every board that is loaded."""
    return _coordinators(
        hass, [entry.entry_id for entry in hass.config_entries.async_entries(DOMAIN)]
    )


@callback
def board_deleted(hass: HomeAssistant, key: str, stored: object) -> None:
    """A board deleted from Home Assistant leaves its tournaments on several
    boards for good: a board it played matches for gives its match back for
    another board, and the boards of the tournament it held, in `stored`, go
    back to their practice settings."""
    held = TournamentDirector()
    held.restore(stored.get("tournament") if isinstance(stored, dict) else None)
    guests = held.guests()
    for board in _boards(hass):
        games = board.games
        if key in games.tournament.guests():
            games.tournament.vacate(key)
            board._moved()
            board._schedule_fixture()
        elif (
            games.key in guests and games.host is None and not games.tournament.running
        ):
            held.release(games.practice, games.key)
            board._moved()


def _coordinators(
    hass: HomeAssistant, keys: Iterable[str]
) -> list[AutodartsGamesCoordinator]:
    """The games of the boards of these entries that are loaded."""
    return [board for key in keys if (board := board_of(hass, key)) is not None]


@contextmanager
def refusals() -> Iterator[None]:
    """An action the games refuse fails with the message that says why."""
    try:
        yield
    except ActionRefused as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=err.key,
            translation_placeholders=err.placeholders or None,
        ) from err


class AutodartsGamesCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The games of one board in Home Assistant, see the module."""

    # A dartboard without Autodarts, see AutodartsManualCoordinator.
    manual_board = False
    # The model its device shows, such as Granboard for a dartboard without
    # Autodarts that receives the darts of one.
    device_model = "Dart Board"

    def __init__(
        self,
        hass: HomeAssistant,
        board_id: str,
        entry: ConfigEntry,
        update_interval: timedelta | None,
        logger: logging.Logger = _LOGGER,
    ) -> None:
        # The board logs its updates under its own logger, the transport's of
        # AutodartsLocalCoordinator.
        super().__init__(
            hass,
            logger,
            name=f"{DOMAIN}_local",
            config_entry=entry,
            update_interval=update_interval,
            # A poll that changes nothing leaves the entities alone; the data
            # carries a revision that changes with the training and games.
            always_update=False,
            # Show the result of consecutive user actions without a long cooldown.
            request_refresh_debouncer=Debouncer(
                hass, logger, cooldown=1, immediate=True
            ),
        )
        self._entry: ConfigEntry = entry
        self.board_id = board_id
        self.device_name = "Autodarts Board"
        self.event_signal = event_signal(entry.entry_id)
        self.reports = BoardReports(hass, entry.entry_id, self)
        self.games = BoardGames(self.reports, dt_util.now())
        self.games.key = entry.entry_id
        # Set up and not shut down, for the other boards of a tournament.
        self.loaded = False
        # The words of the callers in the language of Home Assistant.
        self.caller = Caller()
        self.store = BoardStore(hass, entry.entry_id, self.reports, self._stored)
        # The players' aim models are worked out off the event loop; the count
        # rises when a best aim changed, for the attributes of the profiles.
        self._aim_task: asyncio.Task[None] | None = None
        self.aim_revision = 0
        self._fixture_unsub: CALLBACK_TYPE | None = None
        self._settle_task: asyncio.Task[None] | None = None
        self._midnight_unsub: CALLBACK_TYPE | None = None
        self._language_unsub: CALLBACK_TYPE | None = None
        self._idle_unsub: CALLBACK_TYPE | None = None
        self._bot_unsub: CALLBACK_TYPE | None = None
        self._game_error_logged = False

    # -- loading, starting and stopping ------------------------------------------

    async def async_load(self) -> None:
        """Restore the stored training, games and reports; before the first
        poll. See BoardStore.async_load."""
        await self.caller.async_load(self.hass)
        await self.store.async_load(self._restore)

    def _restore(self, saved: object) -> None:
        self.games.restore(saved, dt_util.now())

    def _stored(self) -> dict[str, Any]:
        """What the training store holds."""
        return self.games.stored()

    @callback
    def async_start(self) -> None:
        self.loaded = True
        self._join_boards()
        # Entities exist now, so an overdue idle end is announced, too.
        self._schedule_idle_end()
        self._schedule_fixture()
        self.reports.async_start()
        if self._midnight_unsub is None:
            # Darts today and the streak change with the date, not with a dart.
            self._midnight_unsub = async_track_time_change(
                self.hass, self._async_new_day, hour=0, minute=0, second=1
            )
        if self._language_unsub is None:
            # The callers speak a new language of Home Assistant at once.
            self._language_unsub = self.hass.bus.async_listen(
                EVENT_CORE_CONFIG_UPDATE, self._async_config_changed
            )
        # The bot goes on with its turn after a restart.
        self._schedule_bot()
        # The best aims of the restored darts.
        self._schedule_aim()

    async def async_shutdown(self) -> None:
        # From now on, no other board of a tournament changes these games.
        self.loaded = False
        if self._settle_task is not None:
            self._settle_task.cancel()
            self._settle_task = None
        left = self.games.leave()
        for board in _coordinators(self.hass, [games.key for games in left]):
            board.async_update_listeners()
        await super().async_shutdown()
        for unsub in (
            self._idle_unsub,
            self._fixture_unsub,
            self._midnight_unsub,
            self._language_unsub,
        ):
            if unsub:
                unsub()
        self._idle_unsub = self._fixture_unsub = self._midnight_unsub = None
        self._language_unsub = None
        self._cancel_bot()
        await self._async_settle()
        await self.store.async_shutdown()

    async def _async_settle(self) -> None:
        """Wait until nothing changes the games any more, before they are
        saved; a board waits for its reads, see AutodartsLocalCoordinator."""

    @callback
    def _async_new_day(self, _now: datetime) -> None:
        self.async_update_listeners()

    async def _async_config_changed(self, _event: CoreEvent) -> None:
        await self.caller.async_load(self.hass)
        # The summary of the training report speaks the new language, too.
        self.async_update_listeners()

    # -- events and changes of the games -----------------------------------------

    def _emit(self, kind: str, attributes: dict[str, Any], source: str) -> None:
        # The words of the callers come with the event, in the language of
        # Home Assistant, which translates no blueprint.
        words = self.caller.words(kind, attributes)
        # Publish the corresponding sensor states before event consumers run.
        self.hass.loop.call_soon(
            async_dispatcher_send,
            self.hass,
            self.event_signal,
            kind,
            {**attributes, **words, "source": source},
        )

    def _play(self, step: Callable[[], list[Announcement]]) -> None:
        """Run a step of the games and do what it asks of Home Assistant:
        announce its events, save a change, and move the timers it moved; a
        step that fails halfway still announces and saves what it did."""
        games = self.games
        revision, fixtures = games.revision, games.fixtures
        try:
            for kind, attributes, source in step():
                self._emit(kind, attributes, source)
        finally:
            for kind, attributes, source in games.drain():
                self._emit(kind, attributes, source)
            if games.revision != revision:
                self.store.save_later()
                self._schedule_idle_end()
                self._schedule_aim()
            if games.fixtures != fixtures:
                self._schedule_fixture()
            self._report_quality()

    def _guarded(self, action: Callable[[], None]) -> None:
        """A fault in the games must never cost the connection to the board."""
        try:
            action()
        except Exception:
            if self._game_error_logged:
                _LOGGER.debug("Training or practice game failed again", exc_info=True)
            else:
                self._game_error_logged = True
                _LOGGER.exception(
                    "Training or practice game failed; the board stays connected"
                )

    def _follow_visit(
        self, data: dict[str, Any], state: dict[str, Any], source: str
    ) -> None:
        """The games follow the visit, see BoardGames.follow_visit."""
        games = self.games
        if games.interrupts_bot(state):
            # The bot throws the rest of its visit at once.
            self._cancel_bot()
        self._play(lambda: games.follow_visit(data, state, source, dt_util.now()))
        self._schedule_bot()

    def _refresh(self, source: str) -> None:
        """Follow the visit again after a change made in Home Assistant."""
        data = dict(self.data or {})
        self._guarded(lambda: self._follow_visit(data, data.get("local") or {}, source))
        self.data = data
        self.async_update_listeners()

    async def _async_changed(self, events: list[Event] | None = None) -> None:
        """Save a change of the session or the game at once, then announce it."""
        announced = self.games.changed(events or [], dt_util.now())
        await self.store.async_save()
        for kind, attributes in announced:
            self._emit(kind, attributes, "training")
        self.data = {**(self.data or {}), **self.games.snapshots()}
        self._schedule_idle_end()
        self.async_update_listeners()
        self._after_change()

    @callback
    def _after_change(self) -> None:
        """A change of the game or the session ends a visit with darts of Home
        Assistant's, entered by hand, undone or the bot's; the bot's next turn
        waits anew."""
        self._cancel_bot()
        if self.games.manual.extras:
            self.games.manual.end_visit()
            self._refresh("manual")
        self._schedule_bot()

    # -- the players' aim models -------------------------------------------------

    @callback
    def _schedule_aim(self) -> None:
        """Work out the aim models of the players whose darts changed. A model
        takes some milliseconds and the search for its best aim some tens, which
        never run on the event loop. Home Assistant starts a task eagerly, so
        one may have ended before it is even returned and kept here."""
        running = self._aim_task is not None and not self._aim_task.done()
        if not running and self.games.progress.stale_aims():
            self._aim_task = self._entry.async_create_task(
                self.hass, self._async_players_aim(), f"{DOMAIN} aim"
            )

    async def _async_players_aim(self) -> None:
        """The players' aim models, until every one knows the newest darts; the
        profiles show a changed best aim."""
        try:
            while logs := self.games.progress.stale_aims():
                aims = await self.hass.async_add_executor_job(
                    _work_out, [log.aim_job() for log in logs]
                )
                changed = [
                    log.store_aim(aim) for log, aim in zip(logs, aims, strict=True)
                ]
                if any(changed):
                    self.aim_revision += 1
                    self.async_update_listeners()
        finally:
            self._aim_task = None

    async def async_aim(self, name: str | None = None) -> dict[str, Any]:
        """The aim model of a player's darts or the session's, for the cards;
        worked out off the event loop when darts came or went since the last."""
        log = self.games.progress.log(name)
        if log.aim_stale:
            log.store_aim(await self.hass.async_add_executor_job(log.aim_job()))
        return log.aim()

    # -- the detection quality ---------------------------------------------------

    def _issue_id(self, name: str) -> str:
        return f"{name}_{self._entry.entry_id}"

    @callback
    def _report_quality(self) -> None:
        """Suggest a calibration while many darts need corrections."""
        issue = self._issue_id("calibration")
        quality = self.games.quality
        rate = quality.rate
        if quality.enough and rate is not None and rate >= RECALIBRATE_RATE:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="calibration_recommended",
                translation_placeholders={"rate": f"{rate:.0f}"},
                data={"entry_id": self._entry.entry_id},
            )
        elif rate is None or rate < RECOVERED_RATE:
            ir.async_delete_issue(self.hass, DOMAIN, issue)

    # -- the training session ----------------------------------------------------

    async def async_start_session(self) -> None:
        started = self.games.training.start(dt_util.now())
        await self._async_changed([started] if started else [])

    async def async_end_session(self) -> None:
        ended = self.games.training.end("manual", dt_util.now())
        await self._async_changed([ended] if ended else [])

    async def async_new_session(self) -> None:
        await self._async_changed(self.games.training.new_session(dt_util.now()))

    async def async_set_auto_start(self, enabled: bool) -> None:
        self.games.training.auto_start = enabled
        await self._async_changed()

    async def async_set_daily_goal(self, darts: int) -> None:
        self.games.records.set_goal(darts, dt_util.now().date())
        await self._async_changed()

    async def async_set_idle_minutes(self, minutes: int) -> None:
        self.games.training.idle_minutes = minutes
        await self._async_changed()

    def _idle_due(self) -> datetime | None:
        """When a running session ends without darts, if the user wants that."""
        training = self.games.training
        last = dt_util.parse_datetime(training.last_activity or "")
        if not training.active or not training.idle_minutes or last is None:
            return None
        return last + timedelta(minutes=training.idle_minutes)

    @callback
    def _schedule_idle_end(self) -> None:
        if self._idle_unsub:
            self._idle_unsub()
            self._idle_unsub = None
        if (due := self._idle_due()) is not None:
            self._idle_unsub = async_track_point_in_utc_time(
                self.hass, self._async_end_idle, max(due, dt_util.utcnow())
            )

    async def _async_end_idle(self, _now: datetime) -> None:
        self._idle_unsub = None
        due = self._idle_due()
        if due is None or due > dt_util.utcnow():
            # A dart arrived in the meantime and rescheduled the end.
            self._schedule_idle_end()
            return
        # The session ended with its last dart, not when the pause ran out.
        training = self.games.training
        ended = training.end("idle", dt_util.now(), at=training.last_activity)
        await self._async_changed([ended] if ended else [])

    # -- the practice game and the players ---------------------------------------

    async def async_play(self, game: int | str) -> None:
        """Start an X01 match or a training game, or stop playing with 0."""
        self.games.practice.play(game)
        await self._async_changed()

    async def async_new_leg(self) -> None:
        self.games.practice.new_leg()
        await self._async_changed()

    async def async_delete_player(self, name: str) -> bool:
        """Forget a player profile, see BoardGames.delete_player; False when
        there is no profile by that name."""
        with refusals():
            deleted = self.games.delete_player(name)
        if deleted:
            await self._async_changed()
        return deleted

    async def async_link_player(self, name: str, person: str | None) -> bool:
        """Link a player to a person, or unlink with None; False when that fails."""
        profiles = self.games.practice.profiles
        changed = profiles.link(name, person) if person else profiles.unlink(name)
        if changed:
            await self._async_changed()
        return changed

    async def async_set_practice_option(self, option: str, enabled: bool) -> None:
        """See BoardGames.set_practice_option."""
        self.games.set_practice_option(option, enabled)
        await self._async_changed()

    async def async_set_x01_rule(self, rule: str, value: str | int) -> None:
        """See BoardGames.set_x01_rule."""
        self.games.set_x01_rule(rule, value)
        await self._async_changed()

    async def async_set_start_score(self, index: int, start: int) -> None:
        """A player's own X01 start score, 0 for the game's; a new match."""
        self.games.practice.set_start(index, start)
        await self._async_changed()

    async def async_set_party_rounds(
        self, golf_holes: int | None = None, count_up_rounds: int | None = None
    ) -> None:
        """Holes of Golf and rounds of Count-Up; the game being played starts anew."""
        self.games.practice.set_rounds(golf_holes, count_up_rounds)
        await self._async_changed()

    async def async_set_party_rule(self, rule: str, value: str | int) -> None:
        """The order of Round the World or the target score of Gotcha; the
        game being played starts anew."""
        self.games.practice.set_party_rule(rule, value)
        await self._async_changed()

    async def async_set_achievements(self, enabled: bool) -> None:
        """Achievements reached while they were off unlock quietly when on again."""
        games = self.games
        games.progress.enable(enabled, games.practice.profiles, dt_util.now())
        await self._async_changed()

    async def async_new_match(self) -> None:
        self.games.practice.new_match()
        await self._async_changed()

    async def async_set_players(self, count: int) -> None:
        """A different number of players starts a new match."""
        self.games.practice.set_players(count)
        await self._async_changed()

    async def async_set_match_format(
        self, legs: int | None = None, sets: int | None = None
    ) -> None:
        self.games.practice.set_format(legs, sets)
        await self._async_changed()

    async def async_set_player_name(self, index: int, name: str) -> bool:
        """Name a seat, see PracticeGame.rename; whether it took the name. A
        refused name changes nothing but the practice settings from before a
        tournament, which come back with any change of a setting."""
        practice = self.games.practice
        resumes = practice.resume is not None
        named = practice.rename(index, name)
        if named or resumes:
            await self._async_changed()
        return named

    async def async_start_game(self, game: int | str, **setup: Any) -> None:
        """Set up a practice game in one step, see BoardGames.start_game."""
        with refusals():
            self.games.start_game(game, **setup)
        await self._async_changed()

    async def async_set_bot(
        self, level: int | None = None, delay: float | None = None
    ) -> None:
        """The bot's level, 0 without the bot, and the seconds between its darts."""
        practice = self.games.practice
        if level is not None:
            practice.set_bot(level)
        if delay is not None:
            practice.bot_delay = delay
        await self._async_changed()

    # -- tournaments -------------------------------------------------------------

    def board_name(self) -> str:
        """The name of the board as Home Assistant shows it, for the cards and
        events of a tournament on several boards."""
        devices = dr.async_entries_for_config_entry(
            dr.async_get(self.hass), self._entry.entry_id
        )
        names = [
            device.name_by_user or device.name
            for device in devices
            if (DOMAIN, self.board_id) in device.identifiers
        ]
        return next((name for name in names if name), self.device_name)

    async def async_start_tournament(
        self,
        boards: list[AutodartsGamesCoordinator] | None = None,
        **options: Any,
    ) -> None:
        """Draw a tournament and start its first match, see
        TournamentDirector.start; with other boards, a tournament on several
        boards, each of which starts a match at once if one is ready for it."""
        others = [board for board in dict.fromkeys(boards or []) if board is not self]
        with refusals():
            events = self.games.start_tournament(
                dt_util.utcnow(),
                self.board_name(),
                [
                    (board.games.key, board.board_name(), board.games)
                    for board in others
                ],
                **options,
            )
        for board in others:
            board._moved()
        await self._async_tournament(events)

    async def async_stop_tournament(self) -> None:
        """Stop the tournament, on every board of a tournament on several boards."""
        if (host := self._tournament_host()) is not None:
            await host.async_stop_tournament()
            return
        with refusals():
            released = self.games.stop_tournament()
        for board in _coordinators(self.hass, [games.key for games in released]):
            board._moved()
        await self._async_tournament()

    async def async_next_tournament_match(self) -> None:
        """Start the next match without waiting for the pause to end."""
        with refusals():
            self.games.next_tournament_match(dt_util.utcnow())
        await self._async_tournament()

    async def async_set_tournament(self, **setup: Any) -> None:
        """A setting of the next tournament; a new pause applies at once."""
        self.games.tournament.configure(**setup)
        await self._async_tournament()

    async def _async_tournament(self, events: list[Event] | None = None) -> None:
        await self._async_changed(events)
        self._schedule_fixture()

    def _tournament_host(self) -> AutodartsGamesCoordinator | None:
        """The board holding the tournament on several boards this board plays
        matches of."""
        host = self.games.host
        return None if host is None else board_of(self.hass, host.key)

    @callback
    def _join_boards(self) -> None:
        """Link the board with the other boards of a tournament on several
        boards after a restart or a reload: the boards of its own tournament,
        and the board whose tournament it plays matches of. A board that was
        deleted meanwhile gives its match back."""
        games = self.games
        for other in _boards(self.hass):
            if games.attach(other.games):
                other._moved()
            elif other.games.attach(games):
                other._schedule_fixture()
        for key in games.tournament.guests():
            if self.hass.config_entries.async_get_entry(key) is None:
                games.tournament.vacate(key)

    @callback
    def _moved(self) -> None:
        """Another board of a tournament on several boards changed the games of
        this board: save and show them, and announce the game it started or
        ended."""
        for kind, attributes, source in self.games.follow_game(dt_util.now()):
            self._emit(kind, attributes, source)
        self.store.save_later()
        self.data = {**(self.data or {}), **self.games.snapshots()}
        self.async_update_listeners()
        self._after_change()

    @callback
    def _schedule_fixture(self) -> None:
        """Time the next match of the tournament. A board playing matches of a
        tournament on several boards leaves that to the board holding it."""
        if (host := self._tournament_host()) is not None:
            host._schedule_fixture()
            return
        if self.games.several_boards and self._settle_task is None:
            # After the step that asked for it, which must not see the games
            # of its board change halfway.
            self._settle_task = self._entry.async_create_task(
                self.hass,
                self._async_settle_boards(),
                f"{DOMAIN} boards",
                eager_start=False,
            )
        self._time_fixture()

    async def _async_settle_boards(self) -> None:
        self._settle_task = None
        self._settle_boards()
        self._time_fixture()

    @callback
    def _time_fixture(self, at: datetime | None = None) -> None:
        if self._fixture_unsub:
            self._fixture_unsub()
            self._fixture_unsub = None
        if at is None and (due := self.games.next_fixture()) is not None:
            at = max(due, dt_util.utcnow())
        if at is not None:
            self._fixture_unsub = async_track_point_in_utc_time(
                self.hass, self._async_fixture_due, at
            )

    @callback
    def _settle_boards(self) -> None:
        """A tournament on several boards that this board holds, after a change:
        the results of the other boards are announced here, every board whose
        next match is due starts it once it is clear, and after the last match
        every board goes back to its settings."""
        games = self.games
        for kind, attributes, source in games.take_board_events():
            self._emit(kind, attributes, source)
        changed = games.settle_boards(dt_util.now())
        others = [board.key for board in changed if board is not games]
        for board in _coordinators(self.hass, others):
            board._moved()
        # The other boards show the results of all of them in their tables.
        for board in _coordinators(self.hass, games.guests):
            board.async_update_listeners()
        if games in changed:
            self._moved()
            return
        self.store.save_later()
        self.data = {**(self.data or {}), **games.snapshots()}
        self.async_update_listeners()

    def _fixture_due(self) -> bool:
        due = self.games.next_fixture()
        return due is not None and due <= dt_util.utcnow()

    async def _async_fixture_due(self, _now: datetime) -> None:
        """The pause is over: the next match starts, or with the takeout of the
        darts still on the board, or once another game is decided. A board
        holding a tournament on several boards starts the matches of every
        board that is clear."""
        self._fixture_unsub = None
        if not self._fixture_due():
            # Woken early, or the pause changed meanwhile.
            self._schedule_fixture()
            return
        if self.games.several_boards:
            self._settle_boards()
            if not self._fixture_due():
                self._time_fixture()
                return
        elif self.games.board_free():
            await self.async_next_tournament_match()
            return
        # The takeout starts it at once; the end of another game is checked again.
        self._time_fixture(dt_util.utcnow() + FIXTURE_RETRY)

    # -- corrections, darts entered by hand and the bot --------------------------

    async def async_correct_dart(
        self,
        dart: int,
        segment: dict[str, Any],
        position: tuple[float, float] | None = None,
    ) -> None:
        """Put a dart of the current visit into another bed, see
        BoardGames.correct_dart."""
        with refusals():
            self.games.correct_dart(dart, segment, position)
        self._refresh("manual")

    async def async_throw_dart(
        self, segment: dict[str, Any], position: tuple[float, float] | None = None
    ) -> None:
        """A dart entered by hand, as if the board had detected it there."""
        with refusals():
            self.games.throw_dart(segment, position)
        self._refresh("manual")

    async def async_enter_visit(
        self,
        points: int,
        darts: int | None = None,
        at_double: int | None = None,
        checkout: bool = False,
    ) -> None:
        """An X01 visit entered as its score, or with `checkout` as the checkout
        of what is left: the darts entered by hand in the visit so far give way to
        it, and the next player throws."""
        state = (self.data or {}).get("local") or {}
        with refusals():
            self.games.enter_visit(state, points, darts, at_double, checkout)
        # Ended at once: without darts, the visit of a dartboard without
        # Autodarts would end before its score is in.
        self._refresh("manual")
        self.games.manual.end_visit()
        self._refresh("manual")

    async def async_next_player(self) -> None:
        """End the visit without pulling the darts; without darts, pass."""
        with refusals():
            self._play(lambda: self.games.next_player(dt_util.now()))
        self._refresh("manual")

    async def async_undo_visit(self) -> None:
        """Take the last visit of a player back, see BoardGames.undo_visit."""
        with refusals():
            self._play(lambda: self.games.undo_visit(dt_util.now()))
        self._cancel_bot()
        self._refresh("manual")

    @callback
    def _schedule_bot(self) -> None:
        """The bot's next dart, or the end of its visit, after its delay."""
        if not self.games.practice.bot_up:
            self._cancel_bot()
        elif self._bot_unsub is None:
            self._bot_unsub = async_call_later(
                self.hass, self.games.practice.bot_delay, self._bot_step
            )

    @callback
    def _cancel_bot(self) -> None:
        if self._bot_unsub:
            self._bot_unsub()
            self._bot_unsub = None

    @callback
    def _bot_step(self, _now: datetime) -> None:
        self._bot_unsub = None
        if not self.games.practice.bot_up:
            # A step that was due when the game changed.
            return
        self.games.bot_step()
        self._refresh("bot")
