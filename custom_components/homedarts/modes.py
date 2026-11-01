"""The games of the practice game, each a mode that the match is played in.

PracticeGame keeps the match frame: the players and their seats, the teams,
the bot, the bull-off, legs and sets, the tallies of the match, undo and
storage. Its mode plays the game: it follows the darts of a visit and books
it, says what the player at the board needs next, shows the game, and adds
what the game counts to the records of a leg, of a match and of its summary.
A mode keeps what only its game has: the X01 start score, the numbers Random
Cricket drew, the party game, or the training game.

GameMode itself is no game, the practice game before one is chosen; its
defaults are what a game does that leaves a part out.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .checkout import checkout, setup
from .cricket import (
    BED,
    CRICKET_GAMES,
    CRICKET_NUMBERS,
    DRAWN_GAMES,
    HIDDEN_CRICKET,
    WILD_MOUSE,
    WILD_MOUSE_TARGETS,
    CricketVisit,
    draw_numbers,
    hidden_target,
    marks_per_round,
    next_target,
    play_visit,
    play_wild_mouse_visit,
    shown,
    valid_draw,
    wild_mouse_target,
)
from .doubles import aimed_at, hits
from .drills import CatchDrill, CheckoutDrill, Drill
from .party import Gotcha, PartyGame, Shanghai, Visit, inner_single
from .positions import x01_aims
from .scoring import (
    DOUBLE,
    STRAIGHT,
    VISIT_DARTS,
    evaluate_visit,
    fits,
    rate,
    score,
    visit_darts,
)
from .scoring import average as _average
from .training import hit_key

if TYPE_CHECKING:
    from .practice import Booking, Player, PracticeGame
    from .summary import Tally

# What a game announces: events by name, each with its data.
type Events = list[tuple[str, dict[str, Any]]]

# The statistics of X01 cover the last ten legs.
STATS_LEGS = 10
STATS_KEYS = ("first9_points", "first9_darts", "at_double", "checkouts")
# The rules of a party game that are not on or off, and the game each belongs to.
PARTY_RULES = {"round_the_world_order": "round_the_world", "gotcha_target": "gotcha"}
# The settings of the practice game that a game is made with, by game: a
# change starts the game anew while it is played.
GAME_SETTINGS: dict[int | str, tuple[str, ...]] = {
    WILD_MOUSE: ("three_in_a_bed",),
    "golf": ("golf_holes",),
    "count_up": ("count_up_rounds",),
    "bermuda": ("bermuda_halve_on_miss",),
    **{game: (rule,) for rule, game in PARTY_RULES.items()},
}


class VisitRefused(ValueError):
    """A visit entered as its score that the game cannot take: the key of the
    message that says why, and what the message names."""

    def __init__(self, key: str, **placeholders: str) -> None:
        super().__init__(key)
        self.key = key
        self.placeholders = placeholders


class GameMode:
    """No game, and the base of the games: what a mode tells the match frame."""

    # The game as events and storage name it: 501, cricket or killer; 0 for
    # no game and for the training games.
    kind: int | str = 0
    # The game as the entities read it: the X01 start score, 0 in the other
    # games, and the Cricket, party or training game being played, if any.
    game = 0
    cricket: str | None = None
    party: PartyGame | None = None
    drill: str | None = None
    # The numbers Random and Hidden Cricket drew for the leg.
    drawn: tuple[int, ...] | None = None
    # A match is played: players take turns, and legs make sets.
    playing = False
    # Eight players take part, as in a party game and before a game is
    # chosen; X01, the Cricket and the training games take four.
    party_seats = True
    # The bot plays the game, and four players can play it as two teams.
    bot = False
    team_play = False
    # Whether a match of it can move the ratings of its players.
    rated = False

    def __init__(self, match: PracticeGame) -> None:
        self.match = match

    @property
    def settings(self) -> tuple[str, ...]:
        """The settings the game is made with: a change starts it anew."""
        return GAME_SETTINGS.get(self.kind, ())

    @property
    def uses_out_mode(self) -> bool:
        """Whether the Out mode decides how a leg ends, so that a change of
        it waits for the next leg once darts count."""
        return False

    def start(self, index: int) -> int:
        """The score the player starts a leg from; only X01 counts down."""
        return 0

    def slots(self) -> int:
        """The marks every player keeps; only the Cricket games use them."""
        return len(CRICKET_NUMBERS)

    def new_leg(self) -> None:
        """A leg starts, once the players start it from their full score."""

    def restore(self, saved: dict[str, Any]) -> None:
        """What the game keeps of a store, once the players are back."""

    def out_mode_changed(self) -> None:
        """The Out mode of the leg changed."""

    def track(self) -> Events:
        """Follow the darts of the visit: what they announce."""
        return []

    def book(self, now: datetime) -> Events:
        """Book the visit whose darts were pulled: what it announces."""
        return []

    def passes(self) -> bool:
        """Whether a visit without darts can end, so the next player throws."""
        return False

    def score_visit(
        self, points: int, darts: int | None, at_double: int | None, checkout: bool
    ) -> list[dict[str, Any]]:
        """The darts of a visit entered as its score, which only X01 takes."""
        raise VisitRefused("visit_not_x01")

    def turn_details(self) -> dict[str, Any]:
        """What callers need to announce the player at the board next."""
        return {"remaining": None, "checkout": None, "setup": None}

    def snapshot(self, common: dict[str, Any]) -> dict[str, Any]:
        """The game as the cards show it, with the part the frame shows."""
        return {"game": None, **common}

    def booking(self, booking: Booking, thrown: list[dict[str, Any]]) -> None:
        """Whom the visit being booked counts for, and what its darts were
        aimed at, where the game knows it."""

    def book_leg(self, rounds: int | None) -> dict[str, Any]:
        """Count what the game counts of the leg that the player at the board
        won, and return the record of the leg for the history."""
        return {"darts": self.match._sum(self.match.current, "darts")}

    def leg_entry(
        self, index: int, player: Player, rounds: int | None
    ) -> dict[str, Any]:
        """What the game adds to the player's numbers of the leg that ended,
        for the profiles."""
        return {}

    def match_entry(self, index: int, player: Player) -> dict[str, Any]:
        """What the game adds to the player's result of the match that ended,
        for the history."""
        return {}

    def summary_entry(self, index: int, player: Player, tally: Tally) -> dict[str, Any]:
        """What the game adds to the player's numbers in the match summary."""
        return {}

    def stored(self) -> dict[str, Any]:
        """What the game keeps in the store of the practice game: the numbers
        Random and Hidden Cricket drew, and the state of a party game."""
        return {
            "drawn": None if self.drawn is None else list(self.drawn),
            "party": None,
        }

    def checkpoint(self) -> dict[str, Any]:
        """What the game keeps besides the store to undo the next visit."""
        return {}

    def rewind(self, checkpoint: dict[str, Any]) -> None:
        """Back to a checkpoint, once the store of it is restored."""


class DrillMode(GameMode):
    """A training game for player 1, which keeps its own score."""

    drill: str
    party_seats = False

    def __init__(self, match: PracticeGame, kind: str) -> None:
        super().__init__(match)
        self.drill = kind

    @property
    def training(self) -> Drill:
        """The training game, with its results of every session."""
        return self.match.drills[self.drill]

    def new_leg(self) -> None:
        self.training.reset(len(self.match._visit))

    def track(self) -> Events:
        return self.training.track(self.match._visit)

    def book(self, now: datetime) -> Events:
        training = self.training
        self.match._record_doubles(training.double_attempts(), 0, now)
        return training.finish_visit(now)

    def snapshot(self, common: dict[str, Any]) -> dict[str, Any]:
        return {"game": None, **common, "drill": self.training.snapshot()}

    def booking(self, booking: Booking, thrown: list[dict[str, Any]]) -> None:
        """Training games are for player 1; most know the bed aimed at."""
        training = self.training
        booking.player, booking.game = 0, self.drill
        if isinstance(training, CheckoutDrill | CatchDrill):
            aims = x01_aims(training.start, thrown, DOUBLE, None, checkout)
            if evaluate_visit(training.start, thrown, DOUBLE)[1] == "won":
                booking.checkout = training.start
        else:
            doubles = [double for double, _ in training.double_attempts()]
            aims = [*doubles, *[None] * len(thrown)][: len(thrown)]
        booking.aims[booking.start : booking.end] = aims

    def checkpoint(self) -> dict[str, Any]:
        return {"drill_on_board": self.training.on_board}

    def rewind(self, checkpoint: dict[str, Any]) -> None:
        self.training.on_board = checkpoint.get("drill_on_board", 0)


class MatchMode(GameMode, ABC):
    """A game that players play as a match: X01, the Cricket games and the
    party games."""

    playing = True

    @abstractmethod
    def track(self) -> Events:
        """Follow the darts of the visit: a bust, or a won leg or match."""

    @abstractmethod
    def book(self, now: datetime) -> Events:
        """Book the visit; then the next player throws, or the leg is won."""

    @abstractmethod
    def snapshot(self, common: dict[str, Any]) -> dict[str, Any]:
        """The game as the cards show it, with the part the frame shows."""

    @abstractmethod
    def match_entry(self, index: int, player: Player) -> dict[str, Any]:
        """What the game adds to the player's result of the match that ended,
        for the history."""

    def passes(self) -> bool:
        """A visit without darts counts as one of three misses."""
        return True

    def booking(self, booking: Booking, thrown: list[dict[str, Any]]) -> None:
        """The visit counts for the player at the board."""
        booking.player, booking.game = self.match.current, self.kind


class X01Mode(MatchMode):
    """X01: count down from the start score to 0, open and check out as the
    In and Out mode ask; a bust keeps the score of the visit start, and a
    round limit lets the lowest score win."""

    game: int
    party_seats = False
    bot = True
    team_play = True
    rated = True

    def __init__(self, match: PracticeGame, game: int) -> None:
        super().__init__(match)
        self.game = self.kind = game

    @property
    def uses_out_mode(self) -> bool:
        return True

    def start(self, index: int) -> int:
        """The player's own start score, or the game's; partners play from
        the start of the first player of their team."""
        match = self.match
        own = match.starts[index % 2 if match._teamed() else index]
        return own or self.game

    def restore(self, saved: dict[str, Any]) -> None:
        """A score above the start, or nothing left without a won match,
        starts the leg anew."""
        match = self.match
        for index, player in enumerate(match.players):
            start = self.start(index)
            # Only the winners of a finished match have nothing left to score.
            left = player.remaining or index in match._winners()
            if player.remaining > start or not left:
                player.new_leg(start, self.slots())

    def rules(self) -> dict[str, Any]:
        """The X01 rules of the leg, for its events."""
        match = self.match
        return {
            "double_out": match.double_out,
            "double_in": match.double_in,
            "out_mode": match.out_mode,
            "in_mode": match.in_mode,
            "bull_mode": match.bull_mode,
        }

    def _opening(self) -> int:
        """Darts of the visit before the dart that opens the leg with double or
        master in."""
        match = self.match
        player = match.players[match.current]
        thrown = match._scoring()
        if match.in_mode == STRAIGHT or player.opened:
            return 0
        return next(
            (index for index, dart in enumerate(thrown) if fits(dart, match.in_mode)),
            len(thrown),
        )

    def _evaluate(self) -> tuple[int, str | None, int]:
        """Remaining score, outcome and counted darts of the current visit."""
        match = self.match
        start = match.players[match.current].remaining
        opening = self._opening()
        remaining, outcome, darts = evaluate_visit(
            start, match._scoring()[opening:], match.out_mode, match.bull_mode
        )
        return remaining, outcome, opening + darts

    def _preferred(self) -> tuple[str, ...]:
        """The strongest doubles of the player at the board, if routes use
        them; the bot aims at the usual routes."""
        match = self.match
        if (
            not match.personal_routes
            or match.out_mode == STRAIGHT
            or (match.current == match.bot_seat)
        ):
            return ()
        return (
            match.profiles.preferred(match._name(match.current))
            or match.doubles.preferred()
        )

    def _route(self, remaining: int, darts: int) -> tuple[str, ...]:
        """The checkout route, over the player's strongest doubles if wanted."""
        match = self.match
        return checkout(
            remaining, darts, match.out_mode, self._preferred(), match.bull_mode
        )

    def _setup(self, remaining: int, darts: int) -> dict[str, Any] | None:
        """Where to aim when the darts in hand cannot finish with double or
        master out."""
        match = self.match
        plan = setup(
            remaining, darts, self._preferred(), match.out_mode, match.bull_mode
        )
        return {"route": " ".join(plan.route), "leave": plan.leave} if plan else None

    def track(self) -> Events:
        match = self.match
        current = match.current
        _, outcome, darts = self._evaluate()
        if outcome == match._announced:
            return []
        match._announced = outcome
        player = match.players[current]
        if outcome == "bust":
            return [("bust", {**match._who(current), "remaining": player.remaining})]
        if outcome != "won":
            return []
        leg_darts = match._sum(current, "darts") + darts
        start = self.start(current)
        return match._won(
            current,
            {
                "darts": leg_darts,
                "average": _average(start, leg_darts),
                "checkout": player.remaining,
                "start": start,
                **self.rules(),
            },
            {
                "average": _average(
                    match._sum(current, "match_points") + player.remaining,
                    match._sum(current, "match_darts") + darts,
                ),
            },
        )

    def score_visit(
        self, points: int, darts: int | None, at_double: int | None, checkout: bool
    ) -> list[dict[str, Any]]:
        """The darts of an X01 visit entered as its score, `points`.

        The darts are made up but for their score, and marked `total`; the last
        `at_double` of those that count were thrown at a double, by default the
        one that checks out. Without `darts`, the visit has three. A score that is
        more than the player has left, leaves 1 with double out, or is what is
        left where no double finishes it, busts; with `checkout`, the visit must
        check out instead.
        """
        match = self.match
        player = match.players[match.current]
        start = player.remaining
        count = VISIT_DARTS if darts is None else darts
        made = visit_darts(
            start,
            points,
            count,
            match.out_mode,
            opening=STRAIGHT if player.opened else match.in_mode,
            bull_mode=match.bull_mode,
        )
        rules = (match.out_mode, match.bull_mode)
        # Asked for as a checkout, what is left without a finish is no bust.
        if checkout and (
            made is None or evaluate_visit(start, made, *rules)[1] != "won"
        ):
            raise VisitRefused("checkout_impossible", remaining=str(start))
        if made is None:
            raise VisitRefused(
                "visit_impossible", score=str(points), remaining=str(start)
            )
        _, outcome, counted = evaluate_visit(start, made, *rules)
        won = outcome == "won"
        if at_double is None:
            at_double = int(won)
        if not match.double_out:
            at_double = 0
        elif at_double > count or (won and not at_double):
            raise VisitRefused("visit_at_double", darts=str(count))
        # The darts after a bust do not count, nor do their darts at a double.
        first = counted - min(at_double, counted)
        return [
            {
                **dart,
                "total": True,
                **({"at_double": True} if first <= index < counted else {}),
            }
            for index, dart in enumerate(made)
        ]

    def book(self, now: datetime) -> Events:
        match = self.match
        current = match.current
        opening = self._opening()
        remaining, outcome, darts = self._evaluate()
        player = match.players[current]
        match._record_doubles(
            self._count_visit(player, outcome, darts, opening), current, now
        )
        scored = player.remaining - remaining
        player.darts += darts
        player.points += scored
        player.match_darts += darts
        player.match_points += scored
        if match.in_mode != STRAIGHT and opening < darts and outcome != "bust":
            player.opened = True
        match.profiles.visit(match._name(current), scored, now)
        match.tallies[current].visit(scored)
        player.high_visit(scored)
        events: Events = []
        if outcome == "won":
            match._book_leg(now)
        else:
            player.remaining = remaining
            self._share(current)
            match.current = (current + 1) % len(match.players)
            match.leg_visits += 1
            events.extend(self._round_limit(now))
        if match.winner is None:
            # Also when playing alone: the next visit is up, for callers.
            events.append(match._turn())
        return events

    def _share(self, index: int) -> None:
        """Partners keep one score: the remaining score and the opening double."""
        match = self.match
        player = match.players[index]
        for other in match._side(index):
            partner = match.players[other]
            partner.remaining, partner.opened = player.remaining, player.opened

    def _count_visit(
        self, player: Player, outcome: str | None, darts: int, opening: int = 0
    ) -> list[tuple[str, bool]]:
        """First nine darts and darts at a double of the visit being booked.

        With double in, darts before the opening double score nothing. Returns
        every dart thrown at the double that finishes, and whether it hit.
        """
        match = self.match
        attempts: list[tuple[str, bool]] = []
        running = player.remaining
        for index, dart in enumerate(match._thrown()[:darts]):
            points = score(dart, match.bull_mode) if index >= opening else 0
            counts = match.double_out and index >= opening
            if dart.get("total"):
                # A visit entered as its score says itself which darts were
                # thrown at a double, though not at which.
                double, aimed = None, counts and dart.get("at_double") is True
            else:
                # A dart is thrown at a double when that double alone finishes.
                double = aimed_at(running) if counts else None
                aimed = double is not None
            if aimed:
                player.at_double += 1
            if double:
                attempts.append((double, hits(dart, double)))
            if player.first9_darts < 9:
                player.first9_darts += 1
                # A bust visit scores nothing, not even its early darts.
                player.first9_points += 0 if outcome == "bust" else points
            running -= points
        return attempts

    def _book_stats(self, checked_out: bool = True) -> None:
        """One record per leg for everybody at the board, then a fresh count.

        The bot's darts count for nobody, nor does a leg it checked out, nor a
        leg the round limit decided.
        """
        match = self.match
        seat = match.bot_seat
        players = [item for index, item in enumerate(match.players) if index != seat]
        match.leg_stats.insert(
            0,
            {
                "first9_points": sum(player.first9_points for player in players),
                "first9_darts": sum(player.first9_darts for player in players),
                "at_double": sum(player.at_double for player in players),
                "checkouts": int(
                    checked_out and match.double_out and match.current != seat
                ),
            },
        )
        del match.leg_stats[STATS_LEGS:]
        for player in match.players:
            player.first9_points, player.first9_darts, player.at_double = 0, 0, 0

    def _round_winner(self) -> int | None:
        """The seat that wins the leg on its round limit: once its last round
        is complete, the one side with the lowest score, its first player.
        After a tie, the leg goes on round by round until one side alone has
        the lowest score, or checks out."""
        match = self.match
        players = len(match.players)
        if not match.max_rounds or match.leg_visits < match.max_rounds * players:
            return None
        if match.leg_visits % players:
            return None
        lowest = min(player.remaining for player in match.players)
        seats = [
            index
            for index, player in enumerate(match.players)
            if player.remaining == lowest
        ]
        sides = {tuple(match._side(index)) for index in seats}
        return seats[0] if len(sides) == 1 else None

    def _round_limit(self, now: datetime) -> Events:
        """The leg, and maybe the match, that the round limit decides once the
        visit that completes a round is booked: announced then, with what the
        winner had left, as no dart checks it out."""
        match = self.match
        winner = self._round_winner()
        if winner is None:
            return []
        match.current = winner
        player = match.players[winner]
        darts = match._sum(winner, "darts")
        rounds = match.round - 1
        events = match._won(
            winner,
            {
                "darts": darts,
                "average": _average(match._sum(winner, "points"), darts),
                "checkout": None,
                "remaining": player.remaining,
                "rounds": rounds,
                "start": self.start(winner),
                **self.rules(),
            },
            {
                "average": _average(
                    match._sum(winner, "match_points"),
                    match._sum(winner, "match_darts"),
                ),
                "rounds": rounds,
            },
        )
        match._book_leg(now, rounds=rounds)
        return events

    def turn_details(self) -> dict[str, Any]:
        """The score left, and once the leg is open the checkout route, or
        where to aim when none is in reach."""
        match = self.match
        up = match.players[match.current]
        if not (up.opened or match.in_mode == STRAIGHT):
            return {**super().turn_details(), "remaining": up.remaining}
        route = self._route(up.remaining, 3)
        return {
            "remaining": up.remaining,
            "checkout": " ".join(route) or None,
            "setup": None if route else self._setup(up.remaining, 3),
        }

    def snapshot(self, common: dict[str, Any]) -> dict[str, Any]:
        match = self.match
        remaining, outcome, darts = self._evaluate()
        thrown = len(match._scoring())
        player = match.players[match.current]
        side = match._side(match.current)
        # A bust takes an opening double of the visit back.
        opened = (
            match.in_mode == STRAIGHT
            or player.opened
            or (self._opening() < thrown and outcome != "bust")
        )
        if outcome == "won" or match.winner is not None or not opened or match.bulling:
            # No route: a won leg, a double to open with, or the bull-off.
            left = 0
        elif outcome == "bust" or thrown >= 3:
            # The visit is over; the next one starts with three darts.
            left = 3
        else:
            left = 3 - thrown
        route = self._route(remaining, left) if left else ()
        scored = player.remaining - remaining
        leg_darts = match._sum(match.current, "darts") + darts
        return {
            "game": self.game,
            **common,
            "player": match.current + 1,
            "name": match._name(match.current),
            "winner": None if match.winner is None else match.winner + 1,
            "remaining": remaining,
            # What the player had before the visit, for its score entered on the cards.
            "visit_from": player.remaining,
            "checkout": " ".join(route) or None,
            "setup": self._setup(remaining, left) if left and not route else None,
            "bust": outcome == "bust",
            "won": outcome == "won",
            "visit": [hit_key(dart) for dart in match._scoring()],
            "darts": leg_darts,
            "average": _average(
                match._sum(match.current, "points") + scored, leg_darts
            ),
            "opened": opened,
            "start": self.start(match.current),
            "round": match.round,
            "scores": [
                {
                    "player": index + 1,
                    "name": match._name(index),
                    "remaining": remaining if index in side else item.remaining,
                    "opened": opened
                    if index in side
                    else item.opened or match.in_mode == STRAIGHT,
                    "start": self.start(index),
                    "legs": item.legs,
                    "sets": item.sets,
                    "match_legs": item.match_legs,
                    "average": _average(
                        item.match_points + (scored if index == match.current else 0),
                        item.match_darts + (darts if index == match.current else 0),
                    ),
                    **match._seat(index),
                }
                for index, item in enumerate(match.players)
            ],
        }

    def book_leg(self, rounds: int | None) -> dict[str, Any]:
        """The statistics count the leg; its record has the average and the
        checkout, or the rounds after which the round limit decided it."""
        match = self.match
        self._book_stats(checked_out=not rounds)
        record = super().book_leg(rounds)
        darts = record["darts"]
        start = self.start(match.current)
        return {
            **record,
            "average": _average(match._sum(match.current, "points"), darts)
            if rounds
            else _average(start, darts),
            "checkout": None if rounds else match.players[match.current].remaining,
            "start": start,
            "double_out": match.double_out,
            "double_in": match.double_in,
            **({"rounds": rounds} if rounds else {}),
        }

    def leg_entry(
        self, index: int, player: Player, rounds: int | None
    ) -> dict[str, Any]:
        """The points, first nine darts and darts at a double of the leg, its
        rules and start, and the checkout of the player who threw it; a leg
        the round limit decided was not checked out."""
        match = self.match
        return {
            "points": player.points,
            "first9_points": player.first9_points,
            "first9_darts": player.first9_darts,
            "at_double": player.at_double,
            "double_out": match.double_out,
            "double_in": match.double_in,
            "start": self.start(index),
            "checkout": player.remaining
            if index == match.current and not rounds
            else 0,
        }

    def match_entry(self, index: int, player: Player) -> dict[str, Any]:
        return {"average": _average(player.match_points, player.match_darts)}

    def summary_entry(self, index: int, player: Player, tally: Tally) -> dict[str, Any]:
        """The averages, checkouts, high visits and best leg of the match."""
        return {
            "average": _average(player.match_points, player.match_darts),
            "first_9_average": _average(tally.first9_points, tally.first9_darts),
            "checkouts": tally.checkouts,
            "darts_at_double": tally.at_double,
            "checkout_rate": rate(tally.checkouts, tally.at_double),
            "highest_checkout": tally.highest_checkout or None,
            "scores_100": tally.scores_100,
            "scores_140": tally.scores_140,
            "scores_180": tally.scores_180,
            "best_leg": tally.best_leg or None,
        }

    def booking(self, booking: Booking, thrown: list[dict[str, Any]]) -> None:
        """What the darts were aimed at along the route, and what they scored."""
        super().booking(booking, thrown)
        match = self.match
        player = match.players[match.current]
        opening = (
            None if player.opened or match.in_mode == STRAIGHT else self._opening()
        )
        aims = x01_aims(
            player.remaining,
            thrown,
            match.out_mode,
            opening,
            self._route,
            match.bull_mode,
        )
        booking.aims[booking.start : booking.end] = aims
        booking.scored = player.remaining - self._evaluate()[0]


class CricketMode(MatchMode):
    """The Cricket games: close the numbers with three marks each and score on
    those the others left open. Cut-Throat gives the points to the others,
    Tactics plays 10 to 20 as well, Wild Mouse closes doubles, triples, a bed
    and the bull besides, and Random and Hidden Cricket draw their numbers for
    every leg."""

    cricket: str
    party_seats = False
    bot = True
    team_play = True
    rated = True

    def __init__(self, match: PracticeGame, kind: str) -> None:
        super().__init__(match)
        self.cricket = self.kind = kind
        # The numbers Random and Hidden Cricket drew for the leg, kept with the
        # game, so that an undone visit and a restart keep them.
        self.drawn = CRICKET_NUMBERS if kind in DRAWN_GAMES else None

    def numbers(self) -> tuple[int, ...]:
        """The numbers of the game: 20 to 15 and the bull, Tactics', or those
        Random and Hidden Cricket drew for the leg."""
        return CRICKET_GAMES[self.cricket] if self.drawn is None else self.drawn

    def targets(self) -> tuple[str, ...]:
        """What Wild Mouse closes besides the numbers; the others close nothing more."""
        if self.cricket != WILD_MOUSE:
            return ()
        if self.match.three_in_a_bed:
            return WILD_MOUSE_TARGETS
        return tuple(target for target in WILD_MOUSE_TARGETS if target != BED)

    def slots(self) -> int:
        """One mark per number and Wild Mouse target."""
        return len(self.numbers()) + len(self.targets())

    def draw(self) -> None:
        """New numbers for a leg of Random or Hidden Cricket, drawn without
        cryptographic randomness, which games need not."""
        hidden = self.cricket == HIDDEN_CRICKET
        self.drawn = draw_numbers(self.match.rng, hidden=hidden)

    def new_leg(self) -> None:
        if self.drawn is not None:
            self.draw()

    def restore(self, saved: dict[str, Any]) -> None:
        """A leg of Random or Hidden Cricket keeps the numbers it drew."""
        if self.drawn is None:
            return
        drawn = saved.get("drawn")
        if valid_draw(drawn):
            self.drawn = tuple(drawn)
            return
        # Marks of numbers that were not drawn, from a store without its
        # draw, start the leg again with new numbers.
        for player in self.match.players:
            player.new_leg(0, self.slots())
        self.draw()

    def _opponents(self) -> list[int]:
        match = self.match
        side = match._side(match.current)
        return [index for index in range(len(match.players)) if index not in side]

    def _play(self) -> CricketVisit:
        """What the darts of the visit do, without booking them."""
        match = self.match
        player = match.players[match.current]
        opponents = [match.players[index] for index in self._opponents()]
        if self.cricket == WILD_MOUSE:
            return play_wild_mouse_visit(
                player.marks,
                player.points,
                match._scoring(),
                [item.marks for item in opponents],
                [item.points for item in opponents],
                self.numbers(),
                self.targets(),
            )
        return play_visit(
            player.marks,
            player.points,
            match._scoring(),
            [item.marks for item in opponents],
            [item.points for item in opponents],
            self.numbers(),
            self.cricket == "cut_throat",
        )

    def _winner(self, visit: CricketVisit) -> int | None:
        """The seat the darts of the visit make the winner of the leg: the
        player at the board, or in Cut-Throat another player whom the points
        they gave left with everything closed and the fewest points."""
        if visit.won:
            return self.match.current
        if visit.other_won is not None:
            return self._opponents()[visit.other_won]
        return None

    def track(self) -> Events:
        match = self.match
        visit = self._play()
        winner = self._winner(visit)
        outcome = "won" if winner is not None else None
        if outcome == match._announced:
            return []
        match._announced = outcome
        if winner is None:
            return []
        # The darts of the visit count for the player who threw them.
        own = winner == match.current
        darts, marks = (visit.darts, visit.counted) if own else (0, 0)
        points = visit.points if own else visit.others[self._opponents().index(winner)]
        leg_darts = match._sum(winner, "darts") + darts
        return match._won(
            winner,
            {
                "darts": leg_darts,
                "points": points,
                "mpr": marks_per_round(
                    match._sum(winner, "marks_hit") + marks, leg_darts
                ),
            },
            {
                "mpr": marks_per_round(
                    match._sum(winner, "match_marks") + marks,
                    match._sum(winner, "match_darts") + darts,
                ),
            },
        )

    def book(self, now: datetime) -> Events:
        match = self.match
        visit = self._play()
        winner = self._winner(visit)
        player = match.players[match.current]
        player.marks, player.points = visit.marks, visit.points
        # Cut-Throat gives the points to the others.
        for index, points in zip(self._opponents(), visit.others, strict=True):
            match.players[index].points = points
        player.darts += visit.darts
        player.match_darts += visit.darts
        player.marks_hit += visit.counted
        player.match_marks += visit.counted
        self._share(match.current)
        if winner is not None:
            match.current = winner
            match._book_leg(now)
        else:
            match.current = (match.current + 1) % len(match.players)
        return [] if match.winner is not None else [match._turn()]

    def _share(self, index: int) -> None:
        """Partners keep one score: the marks and the points."""
        match = self.match
        player = match.players[index]
        for other in match._side(index):
            partner = match.players[other]
            partner.marks, partner.points = list(player.marks), player.points

    def turn_details(self) -> dict[str, Any]:
        match = self.match
        return {**super().turn_details(), "points": match.players[match.current].points}

    def snapshot(self, common: dict[str, Any]) -> dict[str, Any]:
        match = self.match
        visit = self._play()
        side, opponents = match._side(match.current), self._opponents()
        done = (
            self._winner(visit) is not None
            or match.winner is not None
            or match.bulling is not None
        )
        darts = match._sum(match.current, "darts") + visit.darts

        def points(index: int) -> int:
            if index in side:
                return visit.points
            return visit.others[opponents.index(index)]

        others = [match.players[index].marks for index in opponents]
        marks = [
            visit.marks if index in side else item.marks
            for index, item in enumerate(match.players)
        ]
        numbers = self._shown_numbers(marks)
        wild: dict[str, Any] = {}
        if self.cricket == HIDDEN_CRICKET:
            # Only the numbers that show are a target.
            target = hidden_target(visit.marks, numbers, others)
        elif self.cricket == WILD_MOUSE:
            # Where every dart of the visit counted, and the row to aim at with
            # its bed, as a triple counts for its number or for triples.
            row, target = wild_mouse_target(
                visit.marks, self.numbers(), self.targets(), others, match._scoring()
            ) or (None, None)
            wild = {
                "targets": list(self.targets()),
                "bed": visit.bed,
                "target_row": None if done else row,
            }
        else:
            # With everything closed, the target is a number to score on.
            target = next_target(
                visit.marks,
                self.numbers(),
                others,
                list(visit.others),
                self.cricket == "cut_throat",
            )

        return {
            "game": self.cricket,
            **common,
            "player": match.current + 1,
            "name": match._name(match.current),
            "winner": None if match.winner is None else match.winner + 1,
            "remaining": None,
            "checkout": None,
            "target": None if done else target,
            "bust": False,
            "won": visit.won,
            "visit": [hit_key(dart) for dart in match._scoring()],
            # What every dart of the visit counted for, None for nothing.
            "counted": list(visit.targets),
            "darts": darts,
            "average": None,
            "points": visit.points,
            "mpr": marks_per_round(
                match._sum(match.current, "marks_hit") + visit.counted, darts
            ),
            "numbers": numbers,
            "scores": [
                {
                    "player": index + 1,
                    "name": match._name(index),
                    "marks": list(marks[index]),
                    "points": points(index),
                    "legs": item.legs,
                    "sets": item.sets,
                    "match_legs": item.match_legs,
                    "mpr": marks_per_round(
                        item.match_marks
                        + (visit.counted if index == match.current else 0),
                        item.match_darts
                        + (visit.darts if index == match.current else 0),
                    ),
                    **match._seat(index),
                }
                for index, item in enumerate(match.players)
            ],
            **wild,
        }

    def _shown_numbers(self, marks: list[list[int]]) -> list[int | None]:
        """The numbers of the game as the players see them: in Hidden Cricket,
        None for a number no dart has marked yet."""
        numbers = self.numbers()
        if self.cricket != HIDDEN_CRICKET:
            return list(numbers)
        return [
            number if show else None
            for number, show in zip(numbers, shown(numbers, marks), strict=True)
        ]

    def book_leg(self, rounds: int | None) -> dict[str, Any]:
        """The record of the leg has the points and marks per round."""
        match = self.match
        record = super().book_leg(rounds)
        return {
            **record,
            "points": match.players[match.current].points,
            "mpr": marks_per_round(
                match._sum(match.current, "marks_hit"), record["darts"]
            ),
        }

    def leg_entry(
        self, index: int, player: Player, rounds: int | None
    ) -> dict[str, Any]:
        return {"marks": player.marks_hit}

    def match_entry(self, index: int, player: Player) -> dict[str, Any]:
        return {"mpr": marks_per_round(player.match_marks, player.match_darts)}

    def summary_entry(self, index: int, player: Player, tally: Tally) -> dict[str, Any]:
        """The marks of the match, per round, and the best leg."""
        return {
            "mpr": marks_per_round(player.match_marks, player.match_darts),
            "marks": player.match_marks,
            "best_leg": tally.best_leg or None,
        }

    def booking(self, booking: Booking, thrown: list[dict[str, Any]]) -> None:
        """The numbers of the game, which the darts count for."""
        super().booking(booking, thrown)
        booking.cricket = self.numbers()


class PartyMode(MatchMode):
    """A party game for up to eight players, whose rules PartyGame keeps."""

    party: PartyGame

    def __init__(self, match: PracticeGame, party: PartyGame) -> None:
        super().__init__(match)
        self.party = party
        self.kind = party.kind

    @property
    def uses_out_mode(self) -> bool:
        """Gotcha finishes as the Out mode of X01 asks."""
        return isinstance(self.party, Gotcha)

    def out_mode_changed(self) -> None:
        if isinstance(self.party, Gotcha):
            self.party.out_mode = self.match.out_mode

    @property
    def ready(self) -> bool:
        """Whether the game has its players: Killer needs at least two."""
        return len(self.match.players) >= self.party.min_players

    def passes(self) -> bool:
        """Not while the players of Killer choose their numbers."""
        return self.ready and not self.party.choosing

    def new_leg(self) -> None:
        self.party.new_leg(len(self.match.players), self.match.starter)

    def restore(self, saved: dict[str, Any]) -> None:
        self.party.restore(saved.get("party"))

    def stored(self) -> dict[str, Any]:
        return {**super().stored(), "party": self.party.stored()}

    def _darts(self) -> list[dict[str, Any]]:
        """The darts of the visit, with the single bed the board saw them in."""
        match = self.match
        return [
            {**dart, "inner": inner_single(match._position(index))}
            for index, dart in enumerate(match._thrown())
        ]

    def _play(self) -> Visit:
        """What the darts of the visit do, without booking them."""
        return self.party.visit(self.match.current, self._darts())

    def _won(self, winner: int, darts: int, result: Visit) -> Events:
        match = self.match
        return match._won(
            winner,
            {
                "darts": match.players[winner].darts + darts,
                **self.party.announced(winner, result),
            },
            {},
        )

    def track(self) -> Events:
        """Shanghai and Killer can be won with a single dart, and a dart of
        Gotcha can bust the visit."""
        match = self.match
        if not self.ready:
            return []
        result = self._play()
        won = result.won
        outcome = "won" if won is not None else "bust" if result.bust else None
        if outcome == match._announced:
            return []
        match._announced = outcome
        if outcome == "bust":
            party = self.party
            assert isinstance(party, Gotcha)
            remaining = party.left(party.points[match.current])
            return [("bust", {**match._who(match.current), "remaining": remaining})]
        if won is None:
            return []
        darts = result.darts if won == match.current else 0
        return self._won(won, darts, result)

    def book(self, now: datetime) -> Events:
        match = self.match
        if not self.ready:
            return []
        announced = match._announced == "won"
        result = self.party.book(match.current, self._darts())
        events: Events = []
        if result.won is not None and result.won >= 0 and not announced:
            # A win at the end of the last round is known only now.
            darts = result.darts if result.won == match.current else 0
            events = self._won(result.won, darts, result)
        # Darts after the one that decided the leg do not count.
        player = match.players[match.current]
        player.darts += result.darts
        player.match_darts += result.darts
        if result.won is not None and result.won >= 0:
            match.current = result.won
            match._book_leg(now)
        elif result.won is not None:
            # A tie in points and hits: the leg is played again.
            match.starter = (match.starter + 1) % len(match.players)
            match._next_leg()
        else:
            match.current = self.party.next(match.current)
        if match.winner is None:
            events.append(match._turn())
        return events

    def turn_details(self) -> dict[str, Any]:
        """The points, or Killer's lives, and what to aim at."""
        current = self.match.current
        return {
            **super().turn_details(),
            **self.party.announced(current),
            "target": self.party.target(current),
        }

    def snapshot(self, common: dict[str, Any]) -> dict[str, Any]:
        match = self.match
        party = self.party
        ready = self.ready
        live = ready and match.winner is None and match.bulling is None
        result = self._play() if live else None
        points = result.points if result else list(party.points)
        details = [
            party.live_details(index, result) if result else party.details(index)
            for index in range(len(match.players))
        ]
        won = bool(result and result.won is not None and result.won >= 0)
        target = (
            party.live_target(match.current, result) if result and not won else None
        )
        playoff = party.playoff()
        player = match.players[match.current]
        return {
            "game": party.kind,
            **common,
            "player": match.current + 1,
            "name": match._name(match.current),
            "winner": None if match.winner is None else match.winner + 1,
            "remaining": None,
            "checkout": None,
            "target": target,
            "bust": bool(result and result.bust),
            "won": won,
            "visit": [hit_key(dart) for dart in match._scoring()],
            # What the visit so far scored for the player at the board.
            "scored": (
                result.points[match.current] - party.points[match.current]
                if result
                else None
            ),
            "darts": player.darts + (result.darts if result else 0),
            "average": None,
            "points": points[match.current],
            "round": party.shown_round,
            "rounds": party.rounds,
            "playoff": None if playoff is None else [index + 1 for index in playoff],
            "phase": "choose" if party.choosing else "play",
            "needs_players": None if ready else party.min_players,
            "scores": [
                {
                    "player": index + 1,
                    "name": match._name(index),
                    "points": points[index],
                    "legs": item.legs,
                    "sets": item.sets,
                    "match_legs": item.match_legs,
                    **details[index],
                }
                for index, item in enumerate(match.players)
            ],
        }

    def book_leg(self, rounds: int | None) -> dict[str, Any]:
        """The record of the leg has the winner's points."""
        match = self.match
        return {**super().book_leg(rounds), "points": self.party.points[match.current]}

    def match_entry(self, index: int, player: Player) -> dict[str, Any]:
        return {"points": self.party.points[index]}

    def booking(self, booking: Booking, thrown: list[dict[str, Any]]) -> None:
        """A Shanghai: a single, double and treble of the round's number."""
        super().booking(booking, thrown)
        if isinstance(self.party, Shanghai):
            booking.shanghai = self._play().won == self.match.current
