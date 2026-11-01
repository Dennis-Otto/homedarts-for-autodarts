"""Diagnostics contain local status only; never secrets, addresses or player names."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .games_coordinator import AutodartsGamesCoordinator
from .local_coordinator import AutodartsLocalCoordinator
from .manual_coordinator import AutodartsManualCoordinator
from .practice import OPTIONS, X01_RULES
from .runtime import AutodartsConfigEntry

# Identifiers, addresses, credentials and player names that must never leave a
# bug report; segment names of darts are redacted with the player names.
# The address of a Granboard as well, in the entry's data.
TO_REDACT = {
    "board_id",
    "host",
    # A token of the Board Manager, should one ever reach the board's data, and
    # its keys in the spelling of each version. The client keeps them to itself.
    "token",
    "boardId",
    "api_key",
    "apiKey",
    "tls_key",
    "tlsKey",
    "tls_cert",
    "tlsCert",
    "ip",
    "name",
    "team_name",
    "granboard",
    # Says nothing of the board, and changes with the day.
    "plan_of_the_day",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AutodartsConfigEntry
) -> dict[str, Any]:
    runtime = entry.runtime_data
    local = runtime.local
    # The Board Manager's connection; a dartboard without Autodarts has none.
    board = local if isinstance(local, AutodartsLocalCoordinator) else None
    return {
        "entry": {
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "local": async_redact_data(local.data, TO_REDACT),
        # The motion flags, the cameras' state, frame rates and the board PC's load.
        "local_readings": async_redact_data(
            board.readings if board else None, TO_REDACT
        ),
        "local_available": local.last_update_success,
        "realtime_connected": bool(board and board.stream_connected),
        "board_manager_generation": board.generation if board else None,
        "training_sessions": {
            "active": local.games.training.active,
            "auto_start": local.games.training.auto_start,
            "idle_minutes": local.games.training.idle_minutes,
            "stored_sessions": len(local.games.training.history),
        },
        "practice_game": _practice(local),
        "tournament": _tournament(local),
        # Counts only: the bests, profiles and matches carry the names of players.
        "records": {
            "stored_bests": len(local.games.records.bests),
            "streak": local.games.records.streak,
            "best_streak": local.games.records.best_streak,
            "daily_goal": local.games.records.goal,
            "player_profiles": len(local.games.practice.profiles.players),
            "stored_matches": len(local.games.practice.profiles.matches),
            "double_attempts": local.games.practice.doubles.snapshot()["attempts"],
        },
        # Counts only: the journal carries the names of players.
        "reports": {
            "weekday": local.reports.report.weekday,
            "time": local.reports.report.time.isoformat(timespec="minutes"),
            "journal_sessions": len(local.reports.journal.sessions),
            "journal_matches": len(local.reports.journal.matches),
        },
        # Counts only: progress is kept per player name.
        "progress": _progress(local),
        "poll_interval_seconds": (
            local.update_interval.total_seconds() if local.update_interval else None
        ),
        # Counts, kinds of errors and durations only; no addresses or messages.
        # A dartboard without Autodarts connects to nothing, or to its Granboard.
        "connection": (
            board.diagnostics()
            if board
            else local.diagnostics()
            if isinstance(local, AutodartsManualCoordinator)
            else None
        ),
        # Never the secret webhook address.
        "online_bridge": (
            runtime.bridge.diagnostics() if runtime.bridge else {"enabled": False}
        ),
    }


def _progress(local: AutodartsGamesCoordinator) -> dict[str, Any]:
    """Whether achievements unlock, and how much progress is kept."""
    progress = local.games.progress
    players = progress.players.values()
    return {
        "achievements": progress.enabled,
        "players": len(players),
        "badges": sum(
            len(dates) for player in players for dates in player.badges.values()
        ),
        "logged_positions": sum(len(player.log) for player in players),
        "session_positions": len(progress.session),
    }


def _tournament(local: AutodartsGamesCoordinator) -> dict[str, Any]:
    """The setup and the progress of the tournament; the players only as a number."""
    director = local.games.tournament
    setup = director.setup
    tournament = director.tournament
    return {
        "format": setup.format,
        "game": setup.game,
        "players": len(setup.players),
        "third_place": setup.third_place,
        "random_draw": setup.random_draw,
        "groups": setup.groups,
        "advance": setup.advance,
        "pause": setup.pause,
        "summary": setup.summary,
        "running": {
            "format": tournament.format,
            "game": tournament.game,
            "status": tournament.status,
            "players": len(tournament.players),
            "matches_played": sum(match.played for match in tournament.matches),
            "matches_total": len(tournament.numbers()),
        }
        if tournament
        else None,
    }


def _practice(local: AutodartsGamesCoordinator) -> dict[str, Any]:
    """The game, its rules and its progress; the players only as a number."""
    practice = local.games.practice
    return {
        # A training game, or 501, cricket or a party game such as killer.
        "game": practice.drill or practice.kind,
        **{option: getattr(practice, option) for option in OPTIONS},
        **{rule: getattr(practice, rule) for rule in X01_RULES},
        # The Out mode switched during a leg, for the next leg.
        "out_mode_next": practice.out_mode_next,
        "bull_off_running": practice.bulling is not None,
        "players": len(practice.players),
        "bot_level": practice.bot_level,
        "bot_delay": practice.bot_delay,
        "legs_to_win": practice.legs_to_win,
        "sets_to_win": practice.sets_to_win,
        "stored_legs": len(practice.legs),
        "legs_total": practice.legs_total,
    }
