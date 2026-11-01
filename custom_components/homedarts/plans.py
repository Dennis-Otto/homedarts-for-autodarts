"""Training plans: several training games in a row, and a plan of the day.

A plan is a name and its steps in order. A step is a training game and what ends
it: the darts or the visits it may take, or the end of the game itself. Four
plans come with the integration, and own plans come from the options of a board
or with the action homedarts.start_plan. PlanRunner plays a plan on the practice
game: it starts the game of each step, counts its visits, and moves on once they
are over. It is stored with the games, so a plan goes on after a restart in the
middle of a step.

A plan ends in one of three ways, which plan_finished tells: it is finished, it
is stopped, or another game replaces the one on the board. A plan whose steps
were all skipped without a dart counts as stopped: nobody trained.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast

from .drills import DRILLS, CheckoutDrill
from .errors import ActionRefused
from .moments import stamp
from .practice import PracticeGame

# A board event: its type and its attributes.
Event = tuple[str, dict[str, Any]]

MAX_PLANS = 20
MAX_STEPS = 12
MAX_NAME = 40
MAX_DARTS = 1000
MAX_ROUNDS = 300
# What plan_finished tells of how a plan ended.
FINISHED, STOPPED, REPLACED = "finished", "stopped", "replaced"
# A step without a limit plays until its game ends, which these never do.
ENDLESS = ("checkout", "checkout_121")
LOWEST_CHECKOUT, HIGHEST_CHECKOUT = 2, 170
WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
STEP_KEYS = frozenset(("drill", "darts", "rounds", "until", "options"))
PLAN_KEYS = frozenset(("key", "name", "steps", "weekdays"))
# What a step's game tells of its result, where it knows it.
RESULT_KEYS = (
    "hits",
    "hit_rate",
    "score",
    "completed",
    "checkouts",
    "successes",
    "attempts",
    "rate",
    "parts",
)
# A plan given by its steps alone.
UNNAMED = "Training plan"


def _limit(value: object, highest: int) -> int | None:
    return value if type(value) is int and 1 <= value <= highest else None


@dataclass(frozen=True)
class Step:
    """A training game of a plan and what ends it; without a limit, its end.
    The checkout training can stay among the finishes from low to high."""

    drill: str
    darts: int | None = None
    rounds: int | None = None
    low: int = LOWEST_CHECKOUT
    high: int = HIGHEST_CHECKOUT

    def over(self, darts: int, visits: int) -> bool:
        """Whether this many darts and visits reach the limit of the step."""
        return (self.darts is not None and darts >= self.darts) or (
            self.rounds is not None and visits >= self.rounds
        )

    def stored(self) -> dict[str, Any]:
        step: dict[str, Any] = {"drill": self.drill}
        if self.darts is not None:
            step["darts"] = self.darts
        if self.rounds is not None:
            step["rounds"] = self.rounds
        if (self.low, self.high) != (LOWEST_CHECKOUT, HIGHEST_CHECKOUT):
            step["options"] = {"low": self.low, "high": self.high}
        return step


@dataclass(frozen=True)
class Plan:
    """A plan by its key, for an own plan its name. An own plan can name the
    weekdays, 0 for Monday, on which it is the plan of the day."""

    key: str
    name: str
    steps: tuple[Step, ...]
    weekdays: tuple[int, ...] = ()

    def stored(self) -> dict[str, Any]:
        plan: dict[str, Any] = {
            "key": self.key,
            "name": self.name,
            "steps": [step.stored() for step in self.steps],
        }
        if self.weekdays:
            plan["weekdays"] = [WEEKDAYS[day] for day in self.weekdays]
        return plan


PRESETS = {
    plan.key: plan
    for plan in (
        Plan(
            "warm_up",
            "Warm-up 15 minutes",
            (
                Step("around_the_clock", darts=45),
                Step("singles", rounds=10),
                Step("doubles", darts=30),
            ),
        ),
        Plan(
            "doubles_day",
            "Doubles day",
            (
                Step("doubles", darts=60),
                Step("bobs_27"),
                Step("checkout", rounds=10, high=40),
            ),
        ),
        Plan(
            "checkout_day",
            "Checkout day",
            (
                Step("checkout", rounds=12, low=41, high=100),
                Step("catch_40", rounds=20),
                Step("checkout_121", rounds=12),
            ),
        ),
        Plan(
            "jdc_week",
            "JDC week",
            (
                Step("around_the_clock", darts=30),
                Step("jdc_challenge"),
                Step("catch_40", rounds=10),
            ),
        ),
    )
}
# The names of the plans that come with the integration, for the calendar.
PRESET_NAMES = {
    "de": {
        "warm_up": "Aufwärmen 15 Minuten",
        "doubles_day": "Doppel-Tag",
        "checkout_day": "Checkout-Tag",
        "jdc_week": "JDC-Woche",
    },
    "nl": {
        "warm_up": "Opwarmen 15 minuten",
        "doubles_day": "Dubbelsdag",
        "checkout_day": "Checkoutdag",
        "jdc_week": "JDC-week",
    },
    "fr": {
        "warm_up": "Échauffement 15 minutes",
        "doubles_day": "Journée des doubles",
        "checkout_day": "Journée des checkouts",
        "jdc_week": "Semaine JDC",
    },
    "es": {
        "warm_up": "Calentamiento 15 minutos",
        "doubles_day": "Día de dobles",
        "checkout_day": "Día de checkouts",
        "jdc_week": "Semana JDC",
    },
}
# The plan of the day, from Monday to Sunday.
ROTATION = (
    "warm_up",
    "doubles_day",
    "checkout_day",
    "warm_up",
    "doubles_day",
    "jdc_week",
    "checkout_day",
)


def plan_name(key: str, name: str, language: str = "en") -> str:
    """The name of a plan in a language such as de or en-GB; an own plan keeps
    the name it was given, in the language it was given."""
    names = PRESET_NAMES.get(language.split("-")[0].lower(), {})
    return names.get(key, name)


def _checkout_range(options: object) -> tuple[int, int] | None:
    """The finishes a checkout training stays among, if the options make sense:
    the range holds at least one finish that three darts can reach."""
    if not isinstance(options, dict) or set(options) - {"low", "high"}:
        return None
    low = options.get("low", LOWEST_CHECKOUT)
    high = options.get("high", HIGHEST_CHECKOUT)
    if not (
        _limit(low, HIGHEST_CHECKOUT)
        and _limit(high, HIGHEST_CHECKOUT)
        and CheckoutDrill.finishes(low, high)
    ):
        return None
    return low, high


def parse_step(raw: object) -> Step | None:
    """A step as written in YAML, None if it is not valid. At most one of darts,
    rounds and until ends it; until: finished is the default, which a game
    that never ends cannot use."""
    if not isinstance(raw, dict) or set(raw) - STEP_KEYS:
        return None
    drill = raw.get("drill")
    if drill not in DRILLS:
        return None
    darts, rounds, until = raw.get("darts"), raw.get("rounds"), raw.get("until")
    ends = [end for end in (darts, rounds, until) if end is not None]
    if len(ends) > 1 or (until is not None and until != "finished"):
        return None
    if darts is not None and _limit(darts, MAX_DARTS) is None:
        return None
    if rounds is not None and _limit(rounds, MAX_ROUNDS) is None:
        return None
    if drill in ENDLESS and darts is None and rounds is None:
        return None
    low, high = LOWEST_CHECKOUT, HIGHEST_CHECKOUT
    if (options := raw.get("options")) is not None:
        checkout = _checkout_range(options) if drill == "checkout" else None
        if checkout is None:
            return None
        low, high = checkout
    return Step(drill, darts, rounds, low, high)


def parse_plan(raw: object) -> Plan | None:
    """A plan as written in YAML or as stored, None if it is not valid."""
    if not isinstance(raw, dict) or set(raw) - PLAN_KEYS:
        return None
    name, steps, days = raw.get("name"), raw.get("steps"), raw.get("weekdays", [])
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= MAX_NAME:
        return None
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        return None
    parsed = [parse_step(step) for step in steps]
    if not isinstance(days, list) or any(day not in WEEKDAYS for day in days):
        return None
    if None in parsed:
        return None
    key = raw.get("key", name.strip())
    if not isinstance(key, str):
        return None
    return Plan(
        key,
        name.strip(),
        tuple(cast("list[Step]", parsed)),
        tuple(sorted({WEEKDAYS.index(day) for day in days})),
    )


def own_plans(raw: object) -> tuple[Plan, ...] | None:
    """The own plans of a board as written in its options, None if one is not
    valid or takes the name of another plan."""
    if not isinstance(raw, list) or len(raw) > MAX_PLANS:
        return None
    plans = []
    taken = {key.casefold() for key in PRESETS}
    for item in raw:
        # The name is the key of an own plan, whatever else the YAML says.
        plan = (
            parse_plan({key: value for key, value in item.items() if key != "key"})
            if isinstance(item, dict)
            else None
        )
        if plan is None or plan.key.casefold() in taken:
            return None
        taken.add(plan.key.casefold())
        plans.append(plan)
    return tuple(plans)


class PlanRunner:
    """The plan on the board, see the module. Its games are those of the
    practice game, for player 1 like every training game."""

    def __init__(self, today: date) -> None:
        # The own plans of the board, from its options.
        self.custom: tuple[Plan, ...] = ()
        self.day = today
        self.plan: Plan | None = None
        self.index = 0
        # The darts and visits of the step being played.
        self.darts = 0
        self.visits = 0
        # A result per step played; the plan's results, in order.
        self.results: list[dict[str, Any]] = []
        self.started = ""
        # The plans finished on one day, for the offer of the plan of the day.
        self.done_day = ""
        self.done: list[str] = []

    # -- which plan --------------------------------------------------------------

    def today(self) -> Plan:
        """The plan of the day: an own plan that names this weekday, or else the
        rotation of the plans that come with the integration."""
        weekday = self.day.weekday()
        for plan in self.custom:
            if weekday in plan.weekdays:
                return plan
        return PRESETS[ROTATION[weekday]]

    def find(self, name: str) -> Plan | None:
        """A plan that comes with the integration by its key, or an own plan by
        its name in any case."""
        if name in PRESETS:
            return PRESETS[name]
        wanted = name.strip().casefold()
        return next(
            (plan for plan in self.custom if plan.key.casefold() == wanted), None
        )

    def choose(
        self, key: str | None, name: str | None, steps: list[Any] | None
    ) -> Plan:
        """The plan that start_plan asks for: given by its steps, by its key or
        name in either field, or with none of them the plan of the day."""
        if steps is not None:
            plan = parse_plan({"name": name or UNNAMED, "steps": steps})
            if plan is None:
                raise ActionRefused("invalid_plan")
            return plan
        key = key or name
        if key is None:
            return self.today()
        found = self.find(key)
        if found is None:
            raise ActionRefused("unknown_plan", plan=key)
        return found

    # -- playing -----------------------------------------------------------------

    @property
    def step(self) -> Step:
        """The step being played, while a plan is."""
        return cast(Plan, self.plan).steps[self.index]

    def start(self, plan: Plan, practice: PracticeGame, now: datetime) -> list[Event]:
        """Start a plan with its first step. One being played gives way."""
        events = self._end(practice, REPLACED, now, keep_game=True) if self.plan else []
        self.plan, self.index, self.results = plan, 0, []
        self.started = stamp(now)
        self._begin(practice)
        return events

    def _begin(self, practice: PracticeGame) -> None:
        step = self.step
        self._narrow(practice, step.low, step.high)
        self.darts, self.visits = 0, 0
        # One player: a training game is for player 1.
        practice.play(step.drill, 1)

    @staticmethod
    def _narrow(practice: PracticeGame, low: int, high: int) -> None:
        cast(CheckoutDrill, practice.drills["checkout"]).narrow(low, high)

    def booked(self, practice: PracticeGame, darts: int, now: datetime) -> list[Event]:
        """A visit with this many darts was booked; the step may be over."""
        if self.plan is None or not darts:
            return []
        self.darts += darts
        self.visits += 1
        step = self.step
        if practice.drills[step.drill].finished or step.over(self.darts, self.visits):
            return self._next(practice, now, skipped=False)
        return []

    def skip(self, practice: PracticeGame, now: datetime) -> list[Event]:
        """Leave the step being played for the next one."""
        return self._next(practice, now, skipped=True)

    def stop(self, practice: PracticeGame, now: datetime) -> list[Event]:
        """End the plan and the game on the board."""
        return self._end(practice, STOPPED, now)

    def follow(self, practice: PracticeGame, now: datetime) -> list[Event]:
        """A plan ends once another game takes the place of its step's, or no
        game does."""
        if self.plan is None or practice.drill == self.step.drill:
            return []
        reason = REPLACED if practice.kind is not None or practice.drill else STOPPED
        return self._end(practice, reason, now, keep_game=True)

    def _next(
        self, practice: PracticeGame, now: datetime, skipped: bool
    ) -> list[Event]:
        plan = cast(Plan, self.plan)
        result = self._result(practice, skipped)
        self.results.append(result)
        events: list[Event] = [
            (
                "plan_step_finished",
                {
                    **self._named(plan, practice),
                    "step": self.index + 1,
                    "steps": len(plan.steps),
                    **result,
                },
            )
        ]
        self.index += 1
        if self.index < len(plan.steps):
            self._begin(practice)
            return events
        return [*events, *self._end(practice, FINISHED, now)]

    def _result(self, practice: PracticeGame, skipped: bool) -> dict[str, Any]:
        """What a step brought, in the words of its game."""
        drill = practice.drills[self.step.drill]
        told = (
            drill.results[0] if drill.finished and drill.results else drill.snapshot()
        )
        return {
            "drill": drill.kind,
            "darts": self.darts,
            "visits": self.visits,
            "finished": drill.finished,
            "skipped": skipped,
            **{key: told[key] for key in RESULT_KEYS if key in told},
        }

    @staticmethod
    def _named(plan: Plan, practice: PracticeGame) -> dict[str, Any]:
        return {
            "plan": plan.key,
            "plan_name": plan.name,
            # As in the other events: who threw, and from which seat.
            "name": practice.names[0] or None,
            "player": 1,
        }

    def _end(
        self,
        practice: PracticeGame,
        reason: str,
        now: datetime,
        keep_game: bool = False,
    ) -> list[Event]:
        plan = cast(Plan, self.plan)
        results = list(self.results)
        if self.index < len(plan.steps) and self.darts:
            # The step being played counts with what it brought so far.
            results.append(self._result(practice, skipped=False))
        darts = sum(result["darts"] for result in results)
        if reason == FINISHED and not darts:
            reason = STOPPED
        event = {
            **self._named(plan, practice),
            "reason": reason,
            "completed": reason == FINISHED,
            "steps": len(plan.steps),
            "played": sum(not result["skipped"] for result in results),
            "darts": darts,
            "results": results,
            "started": self.started,
            "ended": stamp(now),
        }
        if reason == FINISHED:
            self._mark_done(plan, now.date())
        self._clear(practice)
        if not keep_game:
            practice.play(0)
        return [("plan_finished", event)]

    def _clear(self, practice: PracticeGame) -> None:
        self.plan, self.index, self.darts, self.visits = None, 0, 0, 0
        self.results, self.started = [], ""
        self._narrow(practice, LOWEST_CHECKOUT, HIGHEST_CHECKOUT)

    def _mark_done(self, plan: Plan, day: date) -> None:
        if self.done_day != day.isoformat():
            self.done_day, self.done = day.isoformat(), []
        if plan.key not in self.done:
            self.done.append(plan.key)

    # -- undo --------------------------------------------------------------------

    def checkpoint(self) -> dict[str, int]:
        """What a visit changes, to undo it. A visit that ended a step cannot be
        undone: the next game is on the board."""
        return {"darts": self.darts, "visits": self.visits}

    def rewind(self, checkpoint: dict[str, int]) -> None:
        self.darts, self.visits = checkpoint["darts"], checkpoint["visits"]

    # -- what shows and what stays -----------------------------------------------

    def snapshot(self) -> dict[str, Any] | None:
        """The plan being played, for the entities and the cards."""
        if self.plan is None:
            return None
        step = self.step
        return {
            "plan": self.plan.key,
            "name": self.plan.name,
            "step": self.index + 1,
            "steps": len(self.plan.steps),
            "drill": step.drill,
            "drills": [item.drill for item in self.plan.steps],
            "darts": self.darts,
            "visits": self.visits,
            "darts_limit": step.darts,
            "rounds_limit": step.rounds,
        }

    def offer(self) -> dict[str, Any]:
        """The plan of the day as the idle screen offers it."""
        plan = self.today()
        return {
            "plan": plan.key,
            "name": plan.name,
            "drills": [step.drill for step in plan.steps],
            "done": self.done_day == self.day.isoformat() and plan.key in self.done,
        }

    def stored(self) -> dict[str, Any]:
        return {
            "plan": self.plan.stored() if self.plan else None,
            "index": self.index,
            "darts": self.darts,
            "visits": self.visits,
            "results": [dict(result) for result in self.results],
            "started": self.started,
            "done_day": self.done_day,
            "done": list(self.done),
        }

    def restore(self, saved: object, practice: PracticeGame) -> None:
        """The plan as stored, with the game of its step on the board; anything
        else starts without a plan."""
        stored = saved if isinstance(saved, dict) else {}
        done, day = stored.get("done"), stored.get("done_day")
        if isinstance(done, list) and isinstance(day, str):
            self.done_day = day
            self.done = [key for key in done if isinstance(key, str)]
        plan, index = parse_plan(stored.get("plan")), stored.get("index")
        if (
            plan is None
            or type(index) is not int
            or not 0 <= index < len(plan.steps)
            or practice.drill != plan.steps[index].drill
        ):
            return
        self.plan, self.index = plan, index
        self.darts = _limit(stored.get("darts"), MAX_DARTS * MAX_STEPS) or 0
        self.visits = _limit(stored.get("visits"), MAX_DARTS * MAX_STEPS) or 0
        results = stored.get("results")
        self.results = [
            dict(result)
            for result in (results if isinstance(results, list) else [])
            if isinstance(result, dict)
            and type(result.get("darts")) is int
            and isinstance(result.get("skipped"), bool)
        ][:MAX_STEPS]
        started = stored.get("started")
        self.started = started if isinstance(started, str) else ""
        self._narrow(practice, self.step.low, self.step.high)
