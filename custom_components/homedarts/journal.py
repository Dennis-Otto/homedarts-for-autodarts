"""A year of training sessions and practice matches, for the training calendar.

The training session keeps its last 20 sessions and the player profiles their
last 20 matches. The journal takes over every finished one and keeps it for
365 days in a compact form, bounded in size, so the calendar and exports reach
further back.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from homeassistant.util import dt as dt_util

from .cricket import CRICKET_GAMES
from .party import PARTY_GAMES
from .practice import PARTY_PLAYERS

JOURNAL_DAYS = 365
# At most this many sessions and as many matches, the newest.
JOURNAL_SIZE = 3000
SESSION_COUNTS = (
    "darts",
    "points",
    "visits",
    "highest_visit",
    "scores_100",
    "scores_140",
    "scores_180",
    "triples",
    "doubles",
    "bulls",
    "misses",
)
# A player's result of a match: the X01 average, Cricket MPR or party points.
RESULTS = ("average", "mpr", "points")
# Every Cricket and party game; X01 games are named by their start score.
GAME_NAMES = {
    "cricket": "Cricket",
    "cut_throat": "Cut-Throat",
    "tactics": "Tactics",
    "wild_mouse": "Wild Mouse",
    "random_cricket": "Random Cricket",
    "hidden_cricket": "Hidden Cricket",
    "shanghai": "Shanghai",
    "halve_it": "Halve-It",
    "killer": "Killer",
    "golf": "Golf",
    "baseball": "Baseball",
    "count_up": "Count-Up",
    "bermuda": "Bermuda",
    "round_the_world": "Round the World",
    "gotcha": "Gotcha",
}
GAME_KINDS = frozenset((*CRICKET_GAMES, *PARTY_GAMES))
# The bot of a practice match has no name of its own.
BOT_LABEL = "Bot"


class Locale(NamedTuple):
    """The calendar's words and decimal mark in a language."""

    training: str
    darts: str
    highest: str
    decimal: str


LOCALES = {
    "en": Locale("Training", "Darts", "Max", "."),
    "de": Locale("Training", "Darts", "Max", ","),
    "nl": Locale("Training", "darts", "Max", ","),
    "fr": Locale("Entraînement", "fléchettes", "Max", ","),
    "es": Locale("Entrenamiento", "dardos", "Máx.", ","),
}
# Calendar events last at least this long, also a session of one dart.
MINIMUM_LENGTH = timedelta(minutes=1)
NAME_LENGTH = 20


def _count(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _number(value: object) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _moment(value: object) -> datetime | None:
    parsed = dt_util.parse_datetime(value) if isinstance(value, str) else None
    return dt_util.as_utc(parsed) if parsed and parsed.tzinfo else None


def _utc(value: str) -> datetime:
    """A timestamp the journal validated when it took the entry over."""
    return dt_util.as_utc(datetime.fromisoformat(value))


def _game(value: object) -> int | str | None:
    """An X01 start score, or a Cricket or party game; stored data may hold anything."""
    if type(value) is int and value > 0:
        return value
    return value if isinstance(value, str) and value in GAME_KINDS else None


def locale(language: str) -> Locale:
    """The calendar's words for a language such as de or en-GB; English otherwise."""
    return LOCALES.get(language.split("-")[0].lower(), LOCALES["en"])


def session_entry(saved: object) -> dict[str, Any] | None:
    """A finished session as the journal keeps it, or None if invalid."""
    if not isinstance(saved, dict):
        return None
    started, ended = _moment(saved.get("started")), _moment(saved.get("ended"))
    if started is None or ended is None or ended < started:
        return None
    return {
        "started": started.isoformat(),
        "ended": ended.isoformat(),
        **{key: _count(saved.get(key)) for key in SESSION_COUNTS},
    }


def _player(saved: object) -> dict[str, Any]:
    data = saved if isinstance(saved, dict) else {}
    name = data.get("name")
    if isinstance(name, str):
        name = name.strip()[:NAME_LENGTH] or None
    player: dict[str, Any] = {
        "name": name if isinstance(name, str) else None,
        "legs": _count(data.get("legs")),
        "sets": _count(data.get("sets")),
    }
    # The bot's seat, and the team of a player in a team match.
    if data.get("bot") is True:
        player["bot"] = True
    if (team := data.get("team")) in (1, 2) and type(team) is int:
        player["team"] = team
    # Legs won in the whole match; matches before version 1.6 do not know them.
    if type(data.get("match_legs")) is int:
        player["match_legs"] = _count(data["match_legs"])
    for key in RESULTS:
        if (value := _number(data.get(key))) is not None:
            player[key] = value
    return player


def match_entry(saved: object) -> dict[str, Any] | None:
    """A finished match as the journal keeps it, or None if invalid."""
    if not isinstance(saved, dict):
        return None
    ended, game, players = (
        _moment(saved.get("ended")),
        saved.get("game"),
        saved.get("players"),
    )
    if ended is None or _game(game) is None or not isinstance(players, list):
        return None
    # A party game seats the most players of any match.
    if not 1 <= len(players) <= PARTY_PLAYERS:
        return None
    started = _moment(saved.get("started"))
    winner = saved.get("winner")
    return {
        "started": started.isoformat() if started and started <= ended else None,
        "ended": ended.isoformat(),
        "game": game,
        "legs_to_win": max(_count(saved.get("legs_to_win")), 1),
        "sets_to_win": max(_count(saved.get("sets_to_win")), 1),
        "winner": winner
        if type(winner) is int and 1 <= winner <= len(players)
        else None,
        "players": [_player(player) for player in players],
    }


def average(entry: dict[str, Any]) -> float | None:
    """The 3-dart average of a session."""
    darts: int = entry["darts"]
    return round(entry["points"] * 3 / darts, 2) if darts else None


def duration_minutes(entry: dict[str, Any]) -> float:
    seconds = (_utc(entry["ended"]) - _utc(entry["started"])).total_seconds()
    return round(seconds / 60, 1)


def player_label(player: dict[str, Any], index: int) -> str:
    """A player's name, Bot for the bot, or the seat of a player without a name."""
    if player.get("bot"):
        return BOT_LABEL
    name: str | None = player["name"]
    return name or f"#{index + 1}"


def player_results(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Every player's result, with the legs each won in the deciding set.

    The practice game starts the winner's legs from zero with the set that
    decides the match; the winner won the legs that set needed.
    """
    return [
        {
            "player": index + 1,
            **player,
            "legs": entry["legs_to_win"]
            if index + 1 == entry["winner"]
            else player["legs"],
        }
        for index, player in enumerate(entry["players"])
    ]


def scores(entry: dict[str, Any]) -> list[int]:
    """Sets won, or legs won when one set decides the match."""
    key = "sets" if entry["sets_to_win"] > 1 else "legs"
    return [player[key] for player in player_results(entry)]


def game_name(game: int | str) -> str:
    return GAME_NAMES.get(str(game), str(game))


def _decimal(value: float | int, digits: int, language: str) -> str:
    """A number with the decimal mark of the language, such as 54,2 in German."""
    return f"{value:.{digits}f}".replace(".", locale(language).decimal)


def session_title(entry: dict[str, Any], language: str = "en") -> str:
    """For example "Training · 312 Darts · Ø 54.2", in German "Ø 54,2"."""
    words = locale(language)
    parts = [words.training, f"{entry['darts']} {words.darts}"]
    if (value := average(entry)) is not None:
        parts.append(f"Ø {_decimal(value, 1, language)}")
    return " · ".join(parts)


def session_description(entry: dict[str, Any], language: str = "en") -> str:
    return " · ".join(
        [
            f"180: {entry['scores_180']}",
            f"140+: {entry['scores_140']}",
            f"100+: {entry['scores_100']}",
            f"{locale(language).highest}: {entry['highest_visit']}",
        ]
    )


def _team_scores(entry: dict[str, Any]) -> list[tuple[str, int]] | None:
    """Both teams of a team match with their score, such as ("Alex & Kim", 1)."""
    players = entry["players"]
    if sorted(player.get("team", 0) for player in players) != [1, 1, 2, 2]:
        return None
    won = scores(entry)
    return [
        (
            " & ".join(
                player_label(player, index)
                for index, player in enumerate(players)
                if player["team"] == team
            ),
            next(
                score
                for player, score in zip(players, won, strict=True)
                if player["team"] == team
            ),
        )
        for team in (1, 2)
    ]


def match_title(entry: dict[str, Any]) -> str:
    """For example "501 · Alex 3:2 Sam", "501 · Alex & Kim 1:0 Sam & Lea" for
    two teams, or every player with their score."""
    game = game_name(entry["game"])
    if teams := _team_scores(entry):
        (first, first_score), (second, second_score) = teams
        return f"{game} · {first} {first_score}:{second_score} {second}"
    players = entry["players"]
    labels = [player_label(player, index) for index, player in enumerate(players)]
    won = scores(entry)
    if len(players) == 2:
        return f"{game} · {labels[0]} {won[0]}:{won[1]} {labels[1]}"
    return f"{game} · " + " · ".join(
        f"{label} {score}" for label, score in zip(labels, won, strict=True)
    )


def match_description(entry: dict[str, Any], language: str = "en") -> str:
    """Every player's result: the average, marks per round or points."""
    lines = []
    for index, player in enumerate(entry["players"]):
        label = player_label(player, index)
        if "average" in player:
            lines.append(f"{label}: Ø {_decimal(player['average'], 1, language)}")
        elif "mpr" in player:
            lines.append(f"{label}: MPR {_decimal(player['mpr'], 2, language)}")
        elif "points" in player:
            lines.append(f"{label}: {player['points']}")
    return "\n".join(lines)


@dataclass(frozen=True)
class JournalEvent:
    """A session or a match as the calendar shows it."""

    uid: str
    start: datetime
    end: datetime
    summary: str
    description: str


def _event(kind: str, entry: dict[str, Any], language: str) -> JournalEvent:
    end = _utc(entry["ended"])
    # Matches from before the journal did not keep their first dart. A short
    # event starts earlier instead of reaching past the moment it ended.
    start = _utc(entry["started"]) if entry["started"] else end
    start = min(start, end - MINIMUM_LENGTH)
    if kind == "session":
        summary = session_title(entry, language)
        description = session_description(entry, language)
    else:
        summary = match_title(entry)
        description = match_description(entry, language)
    return JournalEvent(
        uid=f"{kind}-{entry['ended']}",
        start=start,
        end=end,
        summary=summary,
        description=description,
    )


class TrainingJournal:
    """Finished sessions and matches of the last year, oldest first."""

    def __init__(self, language: Callable[[], str] = lambda: "en") -> None:
        self.sessions: list[dict[str, Any]] = []
        self.matches: list[dict[str, Any]] = []
        # The language of the calendar, as Home Assistant's may change.
        self._language = language
        # Whether the first look for matches the journal missed is done.
        self._caught_up = False

    def sync(
        self,
        history: list[dict[str, Any]],
        matches: list[dict[str, Any]],
        now: datetime,
    ) -> bool:
        """Take over sessions and matches that ended since the last entries.

        Both sources list the newest first; a match knows when its first dart
        landed. The first look also takes over the older matches of the source
        that the journal lacks: earlier versions left out the party matches of
        more than four players. Returns whether anything changed.
        """
        sessions = self._fresh(self.sessions, map(session_entry, history))
        new = self._fresh(self.matches, map(match_entry, matches))
        self.sessions.extend(sessions)
        self.matches.extend(new)
        missed = not self._caught_up and self._catch_up(matches, now)
        self._caught_up = True
        return self._prune(now) or bool(sessions or new or missed)

    def last_match(self) -> str | None:
        """When the newest match ended, to rewind to it."""
        return self.matches[-1]["ended"] if self.matches else None

    def rewind(self, last: str | None) -> bool:
        """Forget the matches that ended after this one, as after an undone
        visit that decided a match; whether any was forgotten."""
        before = len(self.matches)
        while self.matches and (
            last is None or _utc(self.matches[-1]["ended"]) > _utc(last)
        ):
            self.matches.pop()
        return len(self.matches) != before

    @staticmethod
    def _fresh(
        entries: list[dict[str, Any]],
        newest_first: Iterable[dict[str, Any] | None],
    ) -> list[dict[str, Any]]:
        """Entries that ended after the last one kept, oldest first."""
        last = _utc(entries[-1]["ended"]) if entries else None
        fresh = []
        for entry in newest_first:
            if entry is None:
                continue
            if last is not None and _utc(entry["ended"]) <= last:
                break
            fresh.append(entry)
        fresh.reverse()
        return fresh

    def _catch_up(self, matches: list[dict[str, Any]], now: datetime) -> bool:
        """Put the matches of the last year that the journal lacks in their
        place; whether there were any."""
        oldest = dt_util.as_utc(now) - timedelta(days=JOURNAL_DAYS)
        known = {_utc(entry["ended"]) for entry in self.matches}
        missed = []
        for entry in map(match_entry, matches):
            if (
                entry
                and oldest <= (ended := _utc(entry["ended"]))
                and ended not in known
            ):
                known.add(ended)
                missed.append(entry)
        if missed:
            self.matches = sorted(
                [*self.matches, *missed], key=lambda entry: _utc(entry["ended"])
            )
        return bool(missed)

    def _prune(self, now: datetime) -> bool:
        """Forget entries older than a year, and the oldest beyond the limit."""
        oldest = dt_util.as_utc(now) - timedelta(days=JOURNAL_DAYS)
        changed = False
        for entries in (self.sessions, self.matches):
            while entries and (
                len(entries) > JOURNAL_SIZE or _utc(entries[0]["ended"]) < oldest
            ):
                del entries[0]
                changed = True
        return changed

    # -- calendar ----------------------------------------------------------------

    def events(self, start: datetime, end: datetime) -> list[JournalEvent]:
        """Sessions and matches that overlap the period, in order."""
        begin, finish = dt_util.as_utc(start), dt_util.as_utc(end)
        found = [
            event for event in self._all() if event.start < finish and event.end > begin
        ]
        return sorted(found, key=lambda event: (event.start, event.uid))

    def latest(self) -> JournalEvent | None:
        """The session or match that ended last; both lists are in that order."""
        language = self._language()
        last = [
            _event(kind, entries[-1], language)
            for kind, entries in (("session", self.sessions), ("match", self.matches))
            if entries
        ]
        return max(last, key=lambda event: event.end, default=None)

    def _all(self) -> list[JournalEvent]:
        language = self._language()
        return [
            *(_event("session", entry, language) for entry in self.sessions),
            *(_event("match", entry, language) for entry in self.matches),
        ]

    # -- storage -------------------------------------------------------------------

    def merge(self, other: TrainingJournal) -> None:
        """Take over the sessions and matches of another board that this one
        does not have, in the order they ended; the newest stay."""
        for entries, theirs in (
            (self.sessions, other.sessions),
            (self.matches, other.matches),
        ):
            known = {json.dumps(entry, sort_keys=True) for entry in entries}
            for entry in theirs:
                if (key := json.dumps(entry, sort_keys=True)) not in known:
                    known.add(key)
                    entries.append(entry)
            entries.sort(key=lambda entry: _utc(entry["ended"]))
            del entries[:-JOURNAL_SIZE]

    def stored(self) -> dict[str, Any]:
        return {
            "sessions": [dict(entry) for entry in self.sessions],
            "matches": [
                {**entry, "players": [dict(player) for player in entry["players"]]}
                for entry in self.matches
            ],
        }

    def restore(self, saved: object) -> None:
        if not isinstance(saved, dict):
            return
        sessions, matches = saved.get("sessions"), saved.get("matches")
        self.sessions, self.matches = [], []
        for entries, stored, convert in (
            (self.sessions, sessions, session_entry),
            (self.matches, matches, match_entry),
        ):
            for entry in map(convert, stored if isinstance(stored, list) else []):
                # Entries stay in the order they ended; anything else is dropped.
                if entry and self._fresh(entries, [entry]):
                    entries.append(entry)
