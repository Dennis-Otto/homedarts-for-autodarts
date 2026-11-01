"""What the callers say at a board event, and how the weekly report reads, in the
language of Home Assistant.

Home Assistant translates no blueprint, so the board events bring the words with
them: a `call` on the events that the dart caller and the practice caller speak,
and a `title` and a `summary` on the weekly report. The training report runs on a
timer that no event starts, so the "Training darts" sensor holds its `summary`.
Their blueprints say them by default. The words are those of the scoreboard's
caller and of the voice packs that the integration records; in English, they are
the words the blueprints said before they had these.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN, LANGUAGES

# How a language writes the decimals of an average or a rate: 54.2 or 54,2.
DECIMAL_MARKS = {"en": ".", "de": ",", "es": ",", "fr": ",", "nl": ","}
MAXIMUM = 180

_LOGGER = logging.getLogger(__name__)


def speaks(language: str) -> str:
    """The language of the integration for a language of Home Assistant or of a
    voice, such as German for de-CH, or English for one it does not speak."""
    words = re.split(r"[-_]", language, maxsplit=1)[0].lower()
    return words if words in LANGUAGES else "en"


async def phrases(hass: HomeAssistant, language: str) -> dict[str, str]:
    """The messages of the integration in a language, by their keys; English
    where the language lacks one."""
    texts = await async_get_translations(hass, speaks(language), "exceptions", {DOMAIN})
    prefix = f"component.{DOMAIN}.exceptions."
    return {
        key.removeprefix(prefix).removesuffix(".message"): text
        for key, text in texts.items()
        if key.startswith(prefix)
    }


def _number(value: Any) -> int:
    """A count of an event, 0 where it has none."""
    return value if isinstance(value, int) else 0


def _decimal(value: Any) -> float | None:
    """An average or a rate rounded as the report shows it, or None."""
    return None if value is None else round(float(value), 1)


class Caller:
    """The words of the callers and of the weekly report in one language, loaded
    before the board announces its first event; see the module."""

    def __init__(self) -> None:
        self.language = "en"
        # Empty until loaded: the events then carry no words, and the
        # blueprints say their own.
        self.say: dict[str, str] = {}
        # Whether a message of the language failed to format, logged once.
        self._failed = False

    async def async_load(self, hass: HomeAssistant) -> None:
        """Take the words of the language Home Assistant has now."""
        language = speaks(hass.config.language)
        self.say = await phrases(hass, language)
        self.language = language
        self._failed = False

    def words(self, kind: str, attributes: Mapping[str, Any]) -> dict[str, str]:
        """The words a board event brings for the blueprints: its `call`, or
        the `title` and `summary` of the weekly report; none for the others."""
        if not self.say:
            return {}
        try:
            if kind == "weekly_report":
                return {
                    "title": self.say["report_title"],
                    "summary": self.summary(attributes),
                }
            call = self.call(kind, attributes)
        except (KeyError, IndexError, ValueError) as error:
            # A broken translation must not stop the games: the event comes
            # without words, and the blueprints say their own.
            self._broken(f"the {kind} event", error)
            return {}
        return {} if call is None else {"call": call}

    def _broken(self, what: str, error: Exception) -> None:
        """Log once that a message of the language fails to format."""
        if not self._failed:
            self._failed = True
            _LOGGER.warning(
                "A message in %s cannot be formatted; %s and others come "
                "without words until the language reloads",
                self.language,
                what,
                exc_info=error,
            )

    # -- the callers -------------------------------------------------------------

    def call(self, kind: str, attributes: Mapping[str, Any]) -> str | None:
        """What a caller says at the event, as the default messages of the dart
        caller and the practice caller say it; None for an event they don't
        call. Empty for a turn that a caller lets pass in silence."""
        if kind in ("visit_thrown", "visit_completed"):
            return self._visit(attributes)
        if kind == "dart_detected":
            return self._dart(attributes)
        if kind == "turn_changed":
            return self._turn(attributes)
        if kind == "bust":
            return self.say["voice_pack_bust"]
        if kind == "leg_won":
            if attributes.get("rounds"):
                return self._named(
                    "caller_limit_leg", "caller_limit_leg_alone", self._side(attributes)
                )
            return self._named("voice_leg", "voice_pack_leg", self._side(attributes))
        if kind == "match_won":
            if attributes.get("rounds"):
                return self._named(
                    "caller_limit_match",
                    "caller_limit_match_alone",
                    self._side(attributes),
                )
            return self._named(
                "voice_match", "voice_pack_match", self._side(attributes)
            )
        if kind == "bull_off_won":
            return self.say["caller_bull_off"].format(name=self._who(attributes))
        return None

    def _who(self, attributes: Mapping[str, Any]) -> str:
        """The player as the callers name them: the bot, their name, their seat
        in a match without names, or nobody when they play alone."""
        if attributes.get("bot"):
            return self.say["caller_bot"]
        if name := attributes.get("name"):
            return str(name)
        if _number(attributes.get("players")) > 1:
            number = _number(attributes.get("player")) or 1
            return self.say["voice_player"].format(number=number)
        return ""

    def _side(self, attributes: Mapping[str, Any]) -> str:
        """The winner of a leg or a match: their team in a team match whose
        partners both have a name, otherwise the player."""
        return str(attributes.get("team_name") or "") or self._who(attributes)

    def _named(self, key: str, alone: str, who: str, **values: Any) -> str:
        """A call with the name of the player, or without one when nobody is
        named."""
        if who:
            return self.say[key].format(name=who, **values)
        return self.say[alone].format(**values)

    def _turn(self, attributes: Mapping[str, Any]) -> str:
        """The next player: their throw for the bull, what they require when a
        checkout is possible, the score a setup leaves without one, or who
        throws in a match."""
        who = self._who(attributes)
        if attributes.get("bull_off"):
            return self.say["caller_bull_off_turn"].format(name=who)
        remaining = attributes.get("remaining")
        if attributes.get("checkout"):
            return self._named(
                "caller_require", "voice_pack_require_score", who, remaining=remaining
            )
        setup = attributes.get("setup")
        if isinstance(setup, Mapping) and setup.get("leave") is not None:
            return self._named(
                "caller_setup", "caller_setup_alone", who, leave=setup["leave"]
            )
        return self.say["voice_next"].format(name=who) if who else ""

    def _visit(self, attributes: Mapping[str, Any]) -> str:
        """A visit as a caller says it: its score, "No score" or the 180."""
        score = _number(attributes.get("score"))
        if score == MAXIMUM:
            return self.say["caller_maximum"]
        return str(score) if score else self.say["voice_pack_no_score"]

    def _dart(self, attributes: Mapping[str, Any]) -> str:
        """A dart as a caller says its bed: "Treble 20", "Double 16", "5" for a
        single, "25", "Bull" or "Miss"."""
        bed = str(attributes.get("segment") or "")
        if not _number(attributes.get("score")):
            return self.say["voice_bed_miss"]
        if bed.upper() == "BULL":
            return self.say["voice_bed_bull"]
        number = bed[1:]
        if bed[:1] == "T":
            return self.say["caller_treble"].format(number=number)
        if bed[:1] == "D":
            return self.say["voice_bed_double"].format(number=number)
        return number if bed[:1] == "S" else bed

    # -- the weekly report -------------------------------------------------------

    def _shown(self, value: float) -> str:
        """An average or a rate with the decimal mark of the language."""
        return str(value).replace(".", DECIMAL_MARKS[self.language])

    def _counted(self, one: str, many: str, count: int) -> str:
        return self.say[one] if count == 1 else self.say[many].format(count=count)

    def summary(self, report: Mapping[str, Any]) -> str:
        """The week of the report in a few sentences, leaving out what it lacks,
        such as the checkout rate of a week without X01 legs."""
        darts = _number(report.get("darts"))
        minutes = _number(report.get("training_minutes"))
        sessions = _number(report.get("sessions"))
        time = self._counted("report_minute", "report_minutes", minutes)
        played = self._counted("report_session", "report_sessions", sessions)
        key = {
            (False, False): "report_darts",
            (True, False): "report_darts_time",
            (False, True): "report_darts_sessions",
            (True, True): "report_darts_time_sessions",
        }[bool(minutes), bool(sessions)]
        parts = [self.say[key].format(darts=darts, time=time, sessions=played)]
        if (average := _decimal(report.get("average"))) is not None:
            change = _decimal(report.get("average_change"))
            if change is None:
                parts.append(
                    self.say["report_average"].format(average=self._shown(average))
                )
            else:
                sign = "+" if change > 0 else ""
                parts.append(
                    self.say["report_average_change"].format(
                        average=self._shown(average), change=sign + self._shown(change)
                    )
                )
        if highest := _number(report.get("highest_visit")):
            maximums = _number(report.get("scores_180"))
            key = "report_best_visit_180" if maximums else "report_best_visit"
            parts.append(self.say[key].format(score=highest, count=maximums))
        if (rate := _decimal(report.get("checkout_rate"))) is not None:
            parts.append(
                self.say["report_checkout_rate"].format(rate=self._shown(rate))
            )
        if streak := _number(report.get("streak")):
            parts.append(
                self._counted("report_streak_day", "report_streak_days", streak)
            )
        bests = report.get("personal_bests")
        if count := (len(bests) if isinstance(bests, list) else 0):
            parts.append(self._counted("report_new_best", "report_new_bests", count))
        if plans := report.get("plans"):
            parts.append(self._counted("report_plan", "report_plans", plans))
        return " ".join(parts)

    # -- the training report -----------------------------------------------------

    def training(self, session: Mapping[str, Any]) -> str | None:
        """The session as the training report says it: its darts, its 3-dart
        average, its highest visit and its 180s, as the blueprint says them in
        English. None before the words are loaded, or where a message of the
        language fails to format: the blueprint then says its own."""
        if not self.say:
            return None
        darts = _number(session.get("darts"))
        # Rounded as the blueprint rounds the sensor of the 3-dart average,
        # which keeps two decimals: to one of them.
        points = _number(session.get("points"))
        average = round(round(points / darts * 3, 2), 1) if darts else 0.0
        maximums = _number(session.get("scores_180"))
        key = "training_summary_180" if maximums else "training_summary"
        try:
            return self.say[key].format(
                darts=darts,
                average=self._shown(average),
                highest=_number(session.get("highest_visit")),
                count=maximums,
            )
        except (KeyError, IndexError, ValueError) as error:
            self._broken("the summary of the training report", error)
            return None
