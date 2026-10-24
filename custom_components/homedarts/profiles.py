"""Player profiles: statistics and personal bests per name, matches and head-to-head.

Profiles exist for named players only; a name is the same player regardless of
upper and lower case. Legs count in every game; X01 legs add the averages and
the checkout rate, Cricket legs the marks per round. The highest checkout and
the fewest darts come from X01 legs with double out only; the fewest darts
also only from legs a player played alone, from one of the X01 start scores.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .doubles import DoubleStats
from .moments import stamp

# The X01 start scores; a leg from another start sets no fewest darts.
GAMES = (101, 301, 501, 701, 901, 1001)
# The bests of a profile, the highest of which counts.
BESTS = ("highest_visit", "highest_checkout", "best_mpr")

MATCH_HISTORY = 20
NAME_LENGTH = 20
# The bests of a profile that a merge keeps the higher of; every other whole
# number of a profile is a count that a merge adds up.
HIGHEST = ("highest_visit", "highest_checkout")
# Characters no player name contains: Home Assistant would render curly
# brackets, percent and number signs as a template where a name goes into a
# file name or a message, and control characters break both.
NAME_EXCLUDED = re.compile(r"[{}%#\x00-\x1f\x7f-\x9f]")
# The entity ID of a person in Home Assistant, as Home Assistant checks entity
# IDs: slugs without a double underscore, none at either end.
PERSON = re.compile(r"^(?!.+__)person\.(?!_)[\da-z_]+(?<!_)$")


def valid_name(name: str) -> bool:
    """Whether a player name is free of the characters no name contains."""
    return NAME_EXCLUDED.search(name) is None


def clean_name(name: str) -> str:
    """A player name as the games keep it: without the characters no name
    contains, trimmed, and at most 20 characters long."""
    return NAME_EXCLUDED.sub("", name).strip()[:NAME_LENGTH]


def _key(name: str) -> str:
    return clean_name(name).casefold()


def renamed_seats(players: list[Any], names: Iterable[str], name: str) -> list[Any]:
    """The players of a stored match, with the new name for those named one of
    these names, in any upper and lower case."""
    keys = {_key(other) for other in names}
    return [
        {**player, "name": name}
        if isinstance(player, dict)
        and isinstance(player.get("name"), str)
        and _key(player["name"]) in keys
        else player
        for player in players
    ]


def _person(value: object) -> str | None:
    """A person entity ID such as person.alex, or None."""
    if not isinstance(value, str) or not PERSON.match(value):
        return None
    return value


def _ratio(part: int, whole: int, factor: int, digits: int) -> float | None:
    return round(part * factor / whole, digits) if whole else None


def _count(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


@dataclass
class Profile:
    """Lifetime numbers of one player."""

    name: str
    legs_played: int = 0
    legs_won: int = 0
    matches_played: int = 0
    matches_won: int = 0
    x01_darts: int = 0
    x01_points: int = 0
    first9_points: int = 0
    first9_darts: int = 0
    at_double: int = 0
    checkouts: int = 0
    cricket_darts: int = 0
    cricket_marks: int = 0
    highest_visit: int = 0
    highest_checkout: int = 0
    best_mpr: float = 0.0
    # Start score -> fewest darts for a won X01 leg.
    fewest_darts: dict[str, int] = field(default_factory=dict)
    # Double -> attempts and hits.
    doubles: dict[str, list[int]] = field(default_factory=dict)
    last_played: str | None = None
    # The Home Assistant person this player is, for the picture and presence.
    person: str | None = None

    def double_stats(self) -> DoubleStats:
        stats = DoubleStats()
        stats.counts = self.doubles
        return stats

    def merge(self, other: Profile) -> None:
        """Add the numbers the same player threw on another board: the counts
        add up, the bests are the better of both."""
        for key, value in asdict(other).items():
            if key in BESTS:
                setattr(self, key, max(getattr(self, key), value))
            elif type(value) is int:
                setattr(self, key, getattr(self, key) + value)
        for game, darts in other.fewest_darts.items():
            self.fewest_darts[game] = min(self.fewest_darts.get(game, darts), darts)
        for double, (attempts, hits) in other.doubles.items():
            count = self.doubles.setdefault(double, [0, 0])
            count[0] += attempts
            count[1] += hits
        self.last_played = max(self.last_played or "", other.last_played or "") or None

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "legs_played": self.legs_played,
            "legs_won": self.legs_won,
            "matches_played": self.matches_played,
            "matches_won": self.matches_won,
            "average": _ratio(self.x01_points, self.x01_darts, 3, 2),
            "first_9_average": _ratio(self.first9_points, self.first9_darts, 3, 2),
            "checkout_rate": _ratio(self.checkouts, self.at_double, 100, 1),
            "mpr": _ratio(self.cricket_marks, self.cricket_darts, 3, 2),
            "highest_visit": self.highest_visit or None,
            "highest_checkout": self.highest_checkout or None,
            "best_mpr": self.best_mpr or None,
            "fewest_darts": dict(self.fewest_darts),
            "doubles": self.double_stats().snapshot(),
            "last_played": self.last_played,
            "person": self.person,
        }

    def absorb(self, other: Profile) -> None:
        """Take over the numbers of another profile of the same player, as if
        one name had thrown every dart: the counts add up, the better bests
        stay, and the person is this profile's, or the other one's."""
        for key, value in asdict(other).items():
            if key in HIGHEST:
                setattr(self, key, max(getattr(self, key), value))
            elif type(value) is int:
                setattr(self, key, getattr(self, key) + value)
        self.best_mpr = max(self.best_mpr, other.best_mpr)
        for game, darts in other.fewest_darts.items():
            self.fewest_darts[game] = min(self.fewest_darts.get(game, darts), darts)
        for double, (attempts, hits) in other.doubles.items():
            mine = self.doubles.setdefault(double, [0, 0])
            mine[0] += attempts
            mine[1] += hits
        self.last_played = max(
            filter(None, (self.last_played, other.last_played)), default=None
        )
        self.person = self.person or other.person

    @classmethod
    def restored(cls, saved: dict[str, Any]) -> Profile | None:
        name = saved.get("name")
        name = clean_name(name) if isinstance(name, str) else ""
        if not name:
            return None
        profile = cls(name=name)
        for key, value in asdict(cls(name="")).items():
            if type(value) is int:
                setattr(profile, key, _count(saved.get(key)))
        mpr = saved.get("best_mpr")
        if isinstance(mpr, int | float) and not isinstance(mpr, bool) and mpr >= 0:
            profile.best_mpr = float(mpr)
        fewest = saved.get("fewest_darts")
        if isinstance(fewest, dict):
            profile.fewest_darts = {
                str(game): darts
                for game, darts in fewest.items()
                if str(game).isdigit() and type(darts) is int and darts > 0
            }
        doubles = DoubleStats()
        doubles.restore(saved.get("doubles"))
        profile.doubles = doubles.counts
        if isinstance(saved.get("last_played"), str):
            profile.last_played = saved["last_played"]
        profile.person = _person(saved.get("person"))
        return profile


class Profiles:
    """Every named player, the last matches and who beat whom."""

    def __init__(self) -> None:
        self.players: dict[str, Profile] = {}
        self.matches: list[dict[str, Any]] = []
        # "a\x00b" with names in a fixed order -> wins of a and of b.
        self.head_to_head: dict[str, list[int]] = {}

    def spelled(self, name: str) -> str:
        """A name as its player's profile spells it, such as Alex for alex; a new
        name as it is."""
        profile = self.players.get(_key(name))
        return profile.name if profile else name

    def rate(self, name: str, cricket: bool) -> float | None:
        """A player's 3-dart average, or marks per round in Cricket; None
        before the player's first darts of the game."""
        profile = self.players.get(_key(name))
        if profile is None:
            return None
        if cricket:
            return _ratio(profile.cricket_marks, profile.cricket_darts, 3, 2)
        return _ratio(profile.x01_points, profile.x01_darts, 3, 2)

    def _profile(self, name: str | None, now: datetime) -> Profile | None:
        name = clean_name(name) if name else ""
        if not name:
            return None
        key = _key(name)
        if key not in self.players:
            self.players[key] = Profile(name=name)
        profile = self.players[key]
        profile.last_played = stamp(now)
        return profile

    # -- recording -------------------------------------------------------------

    def visit(self, name: str | None, points: int, now: datetime) -> None:
        """The score of an X01 visit: nothing for a bust or before double in."""
        if profile := self._profile(name, now):
            profile.highest_visit = max(profile.highest_visit, points)

    def doubles(
        self, name: str | None, attempts: list[tuple[str, bool]], now: datetime
    ) -> None:
        """Darts a player threw at doubles."""
        if attempts and (profile := self._profile(name, now)):
            profile.double_stats().record(attempts)

    def preferred(self, name: str | None) -> tuple[str, ...]:
        """The doubles a named player hits best, strongest first."""
        profile = self.players.get(_key(name)) if name and name.strip() else None
        return profile.double_stats().preferred() if profile else ()

    def leg(
        self, game: int | str, players: list[dict[str, Any]], now: datetime
    ) -> None:
        """A finished leg, with every player's numbers of that leg."""
        for entry in players:
            profile = self._profile(entry.get("name"), now)
            if profile is None:
                continue
            won = entry.get("won") is True
            team = entry.get("team") is True
            profile.legs_played += 1
            profile.legs_won += int(won)
            darts = _count(entry.get("darts"))
            if isinstance(game, int):
                profile.x01_darts += darts
                profile.x01_points += _count(entry.get("points"))
                profile.first9_points += _count(entry.get("first9_points"))
                profile.first9_darts += _count(entry.get("first9_darts"))
                profile.at_double += _count(entry.get("at_double"))
                double_out = entry.get("double_out") is True
                # In a team, the checkout counts for the partner who threw it.
                checkout = _count(entry.get("checkout"))
                if won and double_out and checkout:
                    profile.checkouts += 1
                    profile.highest_checkout = max(profile.highest_checkout, checkout)
                # The fewest darts count for the score the player really started
                # from, only for a leg the player played alone, and not for a
                # leg the round limit decided.
                start = entry.get("start", game)
                alone = not team and entry.get("rounds") is None
                if won and darts and double_out and start in GAMES and alone:
                    best = profile.fewest_darts.get(str(start))
                    profile.fewest_darts[str(start)] = min(best or darts, darts)
            elif game == "cricket":
                marks = _count(entry.get("marks"))
                profile.cricket_darts += darts
                profile.cricket_marks += marks
                # Marks of a team leg are no one player's best.
                if won and darts and not team:
                    profile.best_mpr = max(
                        profile.best_mpr, round(marks * 3 / darts, 2)
                    )

    def match(
        self,
        game: int | str,
        players: list[dict[str, Any]],
        winner: int,
        legs_to_win: int,
        sets_to_win: int,
        winners: list[int] | None = None,
        started: str | None = None,
        *,
        now: datetime,
    ) -> None:
        """A finished match of several players: history and head-to-head.

        In a team match, both players of the winning team win it, and each of
        them beats both opponents; partners play no head-to-head. A player in
        two seats, by names kept from before each seat needed a name of its
        own, plays the match once and never against themselves. The match
        started with its first dart, for the training calendar.
        """
        side = winners or [winner]
        # Every named player, and whether one of their seats won.
        won: dict[str, bool] = {}
        for index, entry in enumerate(players):
            if profile := self._profile(entry.get("name"), now):
                key = _key(profile.name)
                won[key] = won.get(key, False) or index in side
        for key, victory in won.items():
            self.players[key].matches_played += 1
            self.players[key].matches_won += int(victory)
        match: dict[str, Any] = {
            "started": started,
            "ended": stamp(now),
            "game": game,
            "legs_to_win": legs_to_win,
            "sets_to_win": sets_to_win,
            "winner": winner + 1,
            "players": [dict(entry) for entry in players],
        }
        if len(side) > 1:
            match["winners"] = [index + 1 for index in side]
        self.matches.insert(0, match)
        del self.matches[MATCH_HISTORY:]
        losers = [key for key, victory in won.items() if not victory]
        for champion in [key for key, victory in won.items() if victory]:
            for other in losers:
                self._beat(champion, other)

    def _beat(self, champion: str, other: str) -> None:
        """A win of the champion over another player, both by their keys."""
        first, second = sorted((champion, other))
        wins = self.head_to_head.setdefault(f"{first}\x00{second}", [0, 0])
        wins[0 if first == champion else 1] += 1

    def delete(self, name: str) -> bool:
        """Forget a player and their head-to-head records; matches stay."""
        key = _key(name)
        if key not in self.players:
            return False
        del self.players[key]
        for pair in [pair for pair in self.head_to_head if key in pair.split("\x00")]:
            del self.head_to_head[pair]
        return True

    def rename(self, name: str, new_name: str) -> bool | None:
        """Give a player a new name in the profile, the head-to-head records
        and the matches of the history; a new spelling of the same name, such
        as Sam for sam, is a new name too.

        A name that another profile has already merges the player into that
        profile, see Profile.absorb, under the new spelling: the head-to-head
        records against the same players add up, and those of the two against
        each other go, as no player plays against themselves. Returns whether
        the profiles merged; None without a profile by that name or a new name.
        """
        old, spelled = _key(name), clean_name(new_name)
        new = spelled.casefold()
        if old not in self.players or not new:
            return None
        profile = self.players[old]
        target = self.players.get(new) if new != old else None
        kept = profile
        if target is not None:
            target.absorb(profile)
            kept = target
        kept.name = spelled
        # The player keeps the place of the name that played first.
        players: dict[str, Profile] = {}
        for key, other in self.players.items():
            if key in (old, new):
                players.setdefault(new, kept)
            else:
                players[key] = other
        self.players = players
        records, self.head_to_head = self.head_to_head, {}
        for pair, wins in records.items():
            keys = [new if key == old else key for key in pair.split("\x00")]
            if keys[0] == keys[1]:
                continue
            ordered = sorted(keys)
            counts = wins if ordered == keys else wins[::-1]
            merged = self.head_to_head.setdefault("\x00".join(ordered), [0, 0])
            merged[0] += counts[0]
            merged[1] += counts[1]
        for match in self.matches:
            match["players"] = renamed_seats(match["players"], (name, spelled), spelled)
        return target is not None

    def link(self, name: str, person: str) -> bool:
        """Make a player a Home Assistant person; a person is one player only.

        Linking creates the profile of a player who has not played yet, so the
        picture shows from the first game. False without a valid name or person.
        """
        name = clean_name(name)
        if not name or _person(person) is None:
            return False
        key = _key(name)
        for other in self.players.values():
            if other.person == person:
                other.person = None
        profile = self.players.setdefault(key, Profile(name=name))
        profile.person = person
        return True

    def unlink(self, name: str) -> bool:
        """Forget which person a player is; False when there is no such profile."""
        profile = self.players.get(_key(name))
        if profile is None:
            return False
        profile.person = None
        return True

    # -- storage ---------------------------------------------------------------

    def merge(self, other: Profiles) -> None:
        """Take over the players, matches and head-to-head records of another
        board. A name is the same player in any upper and lower case, and a
        person stays with the player linked to it here."""
        persons = {profile.person for profile in self.players.values()}
        for key, theirs in other.players.items():
            if theirs.person in persons:
                theirs.person = None
            if key in self.players:
                self.players[key].merge(theirs)
                self.players[key].person = self.players[key].person or theirs.person
            else:
                self.players[key] = theirs
        known = [*self.matches, *other.matches]
        self.matches = sorted(
            [match for index, match in enumerate(known) if match not in known[:index]],
            key=lambda match: match["ended"],
            reverse=True,
        )[:MATCH_HISTORY]
        for pair, (first, second) in other.head_to_head.items():
            wins = self.head_to_head.setdefault(pair, [0, 0])
            wins[0] += first
            wins[1] += second

    def stored(self) -> dict[str, Any]:
        return {
            "players": [asdict(profile) for profile in self.players.values()],
            "matches": [dict(match) for match in self.matches],
            "head_to_head": {
                pair: list(wins) for pair, wins in self.head_to_head.items()
            },
        }

    def restore(self, saved: object) -> None:
        if not isinstance(saved, dict):
            return
        players = saved.get("players")
        self.players = {}
        for entry in players if isinstance(players, list) else []:
            if isinstance(entry, dict) and (profile := Profile.restored(entry)):
                self.players[_key(profile.name)] = profile
        matches = saved.get("matches")
        self.matches = [
            dict(match)
            for match in (matches if isinstance(matches, list) else [])
            if isinstance(match, dict)
            and isinstance(match.get("ended"), str)
            and isinstance(match.get("players"), list)
        ][:MATCH_HISTORY]
        pairs = saved.get("head_to_head")
        # Earlier versions stored a player in two seats against themselves.
        self.head_to_head = {
            pair: list(wins)
            for pair, wins in (pairs if isinstance(pairs, dict) else {}).items()
            if isinstance(pair, str)
            and pair.count("\x00") == 1
            and len(set(pair.split("\x00"))) == 2
            and isinstance(wins, list)
            and len(wins) == 2
            and all(type(win) is int and win >= 0 for win in wins)
        }

    # -- state -----------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        names = {key: profile.name for key, profile in self.players.items()}
        return {
            "players": [
                profile.summary()
                for profile in sorted(
                    self.players.values(),
                    key=lambda profile: profile.last_played or "",
                    reverse=True,
                )
            ],
            "matches": [dict(match) for match in self.matches],
            "head_to_head": [
                {
                    "players": [names.get(key, key) for key in pair.split("\x00")],
                    "wins": list(wins),
                }
                for pair, wins in sorted(
                    self.head_to_head.items(), key=lambda item: -sum(item[1])
                )
            ],
        }
