"""The words of the callers and of the weekly report, in the language of Home
Assistant: what the board events bring for the blueprints."""

import pytest

from custom_components.homedarts.calls import Caller, speaks
from custom_components.homedarts.const import LANGUAGES

# The defaults of the blueprints before the board events brought the words: the
# calls in English stay what they were.
ENGLISH = [
    ("bust", {"player": 1, "players": 2}, "No score"),
    (
        "turn_changed",
        {
            "player": 2,
            "name": "Sam",
            "players": 2,
            "remaining": 81,
            "checkout": "T15 D18",
        },
        "Sam, you require 81",
    ),
    (
        "turn_changed",
        {"player": 1, "players": 1, "remaining": 40, "checkout": "D20"},
        "You require 40",
    ),
    (
        "turn_changed",
        {
            "player": 2,
            "players": 2,
            "bot": True,
            "remaining": 141,
            "checkout": "T20 T7 D20",
        },
        "Bot, you require 141",
    ),
    (
        "turn_changed",
        {"player": 2, "players": 3, "name": None, "remaining": 32, "checkout": "D16"},
        "Player 2, you require 32",
    ),
    (
        "leg_won",
        {"player": 2, "name": "Sam", "players": 2},
        "Game shot, and the leg, Sam!",
    ),
    ("leg_won", {"player": 1, "players": 1}, "Game shot, and the leg!"),
    (
        "leg_won",
        {"player": 1, "name": "Alex", "players": 4, "team_name": "Alex & Kim"},
        "Game shot, and the leg, Alex & Kim!",
    ),
    (
        "leg_won",
        {"player": 2, "name": "Lea", "players": 2, "rounds": 10, "remaining": 32},
        "Round limit, and the leg, Lea!",
    ),
    ("leg_won", {"player": 1, "players": 1, "rounds": 10}, "Round limit, and the leg!"),
    (
        "match_won",
        {"player": 2, "name": "Sam", "players": 2},
        "Game shot, and the match, Sam!",
    ),
    ("match_won", {"player": 1, "players": 1}, "Game shot, and the match!"),
    (
        "match_won",
        {"player": 2, "name": "Lea", "players": 2, "rounds": 1},
        "Round limit, and the match, Lea!",
    ),
    (
        "match_won",
        {"player": 1, "players": 1, "rounds": 1},
        "Round limit, and the match!",
    ),
    ("visit_thrown", {"score": 180, "darts": 3}, "One hundred and eighty!"),
    ("visit_completed", {"score": 125, "darts": 3}, "125"),
    ("visit_completed", {"score": 0, "darts": 3}, "No score"),
    ("dart_detected", {"segment": "T20", "score": 60}, "Treble 20"),
    ("dart_detected", {"segment": "D16", "score": 32}, "Double 16"),
    ("dart_detected", {"segment": "S5", "score": 5}, "5"),
    ("dart_detected", {"segment": "25", "score": 25}, "25"),
    ("dart_detected", {"segment": "Bull", "score": 50}, "Bull"),
    ("dart_detected", {"segment": "M", "score": 0}, "Miss"),
]


async def caller(hass, language: str) -> Caller:
    hass.config.language = language
    loaded = Caller()
    await loaded.async_load(hass)
    return loaded


@pytest.mark.parametrize(("kind", "attributes", "call"), ENGLISH)
async def test_the_english_calls_are_those_the_blueprints_said(
    hass, kind, attributes, call
):
    assert (await caller(hass, "en")).words(kind, attributes) == {"call": call}


async def test_a_turn_calls_the_next_player_as_a_caller_does(hass):
    english = await caller(hass, "en")
    match = {"player": 2, "name": "Sam", "players": 2, "remaining": 169}
    setup = {"route": "T20 T20 S17", "leave": 32}
    assert english.call("turn_changed", {**match, "setup": setup}) == (
        "Sam, leave yourself 32"
    )
    assert english.call(
        "turn_changed", {"player": 1, "players": 1, "remaining": 169, "setup": setup}
    ) == ("Leave yourself 32")
    # Without a checkout or a setup: who throws in a match, nothing alone.
    assert english.call("turn_changed", {**match, "setup": None}) == "Sam to throw."
    assert english.call("turn_changed", {"player": 1, "players": 1}) == ""
    assert english.call("turn_changed", {**match, "bull_off": True}) == (
        "Sam, throw for the bull"
    )
    assert english.call("bull_off_won", match) == "Sam to throw first. Game on!"


async def test_the_german_calls(hass):
    german = await caller(hass, "de")
    match = {"player": 2, "name": "Lea", "players": 2}
    said = [
        german.call(kind, attributes)
        for kind, attributes in [
            ("turn_changed", {**match, "remaining": 101, "checkout": "T20 S1 D20"}),
            (
                "turn_changed",
                {"player": 1, "players": 1, "remaining": 40, "checkout": "D20"},
            ),
            ("turn_changed", {**match, "setup": {"leave": 32, "route": "T20 T20 S17"}}),
            ("turn_changed", {**match, "bot": True}),
            ("turn_changed", {**match, "bull_off": True}),
            ("bull_off_won", match),
            ("bust", match),
            ("leg_won", {**match, "players": 3, "name": None, "player": 3}),
            ("match_won", match),
            ("match_won", {**match, "rounds": 1}),
            ("visit_thrown", {"score": 180}),
            ("visit_completed", {"score": 0}),
            ("dart_detected", {"segment": "T19", "score": 57}),
            ("dart_detected", {"segment": "D8", "score": 16}),
            ("dart_detected", {"segment": "M", "score": 0}),
        ]
    ]
    assert said == [
        "Lea, du brauchst 101",
        "Du brauchst 40",
        "Lea, stell dir die 32",
        "Bot ist dran.",
        "Lea, dein Wurf aufs Bull",
        "Lea beginnt. Game on!",
        "Überworfen",
        "Game shot, und das Leg, Spieler 3!",
        "Game shot, und das Match, Lea!",
        "Rundenlimit, und das Match, Lea!",
        "Einhundertachtzig!",
        "Keine Punkte",
        "Triple 19",
        "Doppel 8",
        "Fehlwurf",
    ]


@pytest.mark.parametrize(
    ("language", "spoken"),
    [
        ("en", "en"),
        ("en-GB", "en"),
        ("de-CH", "de"),
        ("es-419", "es"),
        ("fr_CA", "fr"),
        ("NL", "nl"),
        ("pt-BR", "en"),
    ],
)
async def test_a_regional_language_speaks_its_language(hass, language, spoken):
    assert speaks(language) == spoken
    assert (await caller(hass, language)).language == spoken


async def test_other_events_bring_no_words(hass):
    english = await caller(hass, "en")
    assert english.words("takeout_started", {}) == {}
    assert english.words("dart_corrected", {"segment": "T20", "score": 60}) == {}
    # Before the words are loaded, no event brings any; the blueprints then say
    # their own.
    assert Caller().words("bust", {"player": 1}) == {}
    assert Caller().words("weekly_report", {"darts": 3}) == {}


WEEK = {
    "darts": 312,
    "visits": 104,
    "sessions": 3,
    "training_minutes": 95,
    "average": 54.25,
    "average_change": 2.14,
    "highest_visit": 140,
    "scores_180": 1,
    "checkout_rate": 31.25,
    "streak": 4,
    "personal_bests": [{"record": "highest_visit"}, {"record": "fewest_darts_501"}],
}
QUIET = {
    **WEEK,
    "darts": 10,
    "sessions": 1,
    "training_minutes": 3,
    "average": 20.0,
    "average_change": -3.25,
    "highest_visit": None,
    "scores_180": 0,
    "checkout_rate": None,
    "streak": 1,
    "personal_bests": [],
}


async def test_the_english_summary_is_the_one_the_blueprint_wrote(hass):
    english = await caller(hass, "en")
    assert english.words("weekly_report", WEEK) == {
        "title": "Your darts week",
        "summary": "312 darts in 95 minutes at the board, 3 sessions. "
        "3-dart average 54.2 (+2.1 on the week before). Best visit 140, 1 × 180. "
        "Checkout rate 31.2 %. 4 days in a row. 2 new personal bests.",
    }
    assert english.summary(QUIET) == (
        "10 darts in 3 minutes at the board, 1 session. "
        "3-dart average 20.0 (-3.2 on the week before). 1 day in a row."
    )
    assert english.summary({**QUIET, "darts": 12, "average": None, "sessions": 0}) == (
        "12 darts in 3 minutes at the board. 1 day in a row."
    )
    assert english.summary(
        {
            **QUIET,
            "darts": 30,
            "training_minutes": 1,
            "average_change": None,
            "highest_visit": 60,
            "streak": 0,
            "personal_bests": [{"record": "doubles"}],
        }
    ) == (
        "30 darts in 1 minute at the board, 1 session. "
        "3-dart average 20.0. Best visit 60. 1 new personal best."
    )
    # A week of darts without a session, with every value missing.
    assert english.summary({"darts": 3, "sessions": 2, "average_change": 0}) == (
        "3 darts, 2 sessions."
    )


async def test_the_summary_writes_the_numbers_of_its_language(hass):
    german = await caller(hass, "de")
    assert german.words("weekly_report", WEEK) == {
        "title": "Deine Dartwoche",
        "summary": "312 Darts in 95 Minuten am Board, 3 Sessions. "
        "3-Dart-Average 54,2 (+2,1 zur Vorwoche). Beste Aufnahme 140, 1 × 180. "
        "Checkout-Quote 31,2 %. 4 Tage in Folge. 2 neue Bestleistungen.",
    }
    assert german.summary(QUIET) == (
        "10 Darts in 3 Minuten am Board, 1 Session. "
        "3-Dart-Average 20,0 (-3,2 zur Vorwoche). 1 Tag in Folge."
    )
    french = await caller(hass, "fr")
    assert french.summary({**QUIET, "personal_bests": [{}], "training_minutes": 0}) == (
        "10 fléchettes, 1 session. Moyenne 3 fléchettes 20,0 (-3,2 par rapport à la "
        "semaine précédente). 1 jour d'affilée. 1 nouveau record personnel."
    )


# A training session as the "Training darts" sensor holds it: its 3-dart average
# is 45.1538…, which its sensor shows as 45.15 and the training report rounds
# to 45.1.
SESSION = {"darts": 39, "points": 587, "highest_visit": 140, "scores_180": 1}


async def test_the_english_training_summary_is_the_one_the_blueprint_wrote(hass):
    english = await caller(hass, "en")
    assert english.training(SESSION) == (
        "39 darts, 3-dart average 45.1, highest visit 140, 1 × 180."
    )
    assert english.training({**SESSION, "darts": 3, "points": 60, "scores_180": 0}) == (
        "3 darts, 3-dart average 60.0, highest visit 140."
    )
    # A session without darts, as the blueprint reads the unknown average.
    assert english.training({"darts": 0, "points": 0}) == (
        "0 darts, 3-dart average 0.0, highest visit 0."
    )
    # Before the words are loaded, the blueprint says its own.
    assert Caller().training(SESSION) is None


@pytest.mark.parametrize(
    ("language", "summary"),
    [
        ("de", "39 Darts, 3-Dart-Average 45,1, höchste Aufnahme 140, 1 × 180."),
        ("de-CH", "39 Darts, 3-Dart-Average 45,1, höchste Aufnahme 140, 1 × 180."),
        (
            "es-419",
            "39 dardos, media de 3 dardos 45,1, tirada más alta 140, 1 × 180.",
        ),
        (
            "fr",
            "39 fléchettes, moyenne 3 fléchettes 45,1, meilleure volée 140, 1 × 180.",
        ),
        ("nl", "39 darts, 3-dart-gemiddelde 45,1, hoogste beurt 140, 1 × 180."),
    ],
)
async def test_the_training_summary_speaks_the_language(hass, language, summary):
    assert (await caller(hass, language)).training(SESSION) == summary


# Every turn a caller can call, beyond the cases of ENGLISH.
TURNS = [
    ("turn_changed", {"player": 2, "name": "Sam", "players": 2, "bull_off": True}),
    ("bull_off_won", {"player": 2, "name": "Sam", "players": 2}),
    (
        "turn_changed",
        {"player": 2, "name": "Sam", "players": 2, "setup": {"leave": 32}},
    ),
    ("turn_changed", {"player": 1, "players": 1, "setup": {"leave": 32}}),
    ("turn_changed", {"player": 2, "name": "Sam", "players": 2}),
]


@pytest.mark.parametrize("language", LANGUAGES)
async def test_every_language_formats_every_call_and_summary(hass, language):
    """A translation with a stray brace keeps its placeholders but fails to
    format: every message of every language is formatted here once."""
    spoken = await caller(hass, language)
    for kind, attributes, _ in ENGLISH:
        assert spoken.words(kind, attributes)["call"]
    for kind, attributes in TURNS:
        assert spoken.words(kind, attributes)["call"]
    singular = {
        **QUIET,
        "training_minutes": 1,
        "average_change": None,
        "highest_visit": 60,
        "personal_bests": [{}],
    }
    plural = {**WEEK, "streak": 2, "scores_180": 0}
    for report in (WEEK, QUIET, singular, plural, {"darts": 3}):
        words = spoken.words("weekly_report", report)
        assert words["title"]
        assert words["summary"]
    for session in (SESSION, {**SESSION, "scores_180": 0}):
        assert spoken.training(session)
    for records in (OPEN, {**OPEN, "darts_today": 9}):
        assert spoken.goal_reminder(records)
    for records in (OPEN, {**OPEN, "streak": 1}):
        assert spoken.streak_reminder(records)
    assert not spoken._failed


async def test_a_broken_translation_brings_no_words_and_stops_nothing(hass, caplog):
    spoken = await caller(hass, "fr")
    spoken.say["caller_bull_off"] = "{name} {"
    spoken.say["report_darts_time_sessions"] = "{0}"
    del spoken.say["caller_maximum"]
    sam = {"player": 2, "name": "Sam", "players": 2}
    assert spoken.words("bull_off_won", sam) == {}
    assert spoken.words("weekly_report", WEEK) == {}
    assert spoken.words("visit_thrown", {"score": 180}) == {}
    # The other messages still speak, and the failure is logged once.
    assert spoken.words("visit_completed", {"score": 60}) == {"call": "60"}
    assert caplog.text.count("cannot be formatted") == 1
    # Loading the language again takes its words afresh.
    await spoken.async_load(hass)
    assert spoken.words("bull_off_won", sam)["call"]
    assert not spoken._failed


async def test_a_broken_training_summary_leaves_the_blueprint_its_own(hass, caplog):
    spoken = await caller(hass, "nl")
    spoken.say["training_summary_180"] = "{darts} {"
    assert spoken.training(SESSION) is None
    assert spoken.training({**SESSION, "scores_180": 0})
    del spoken.say["training_summary"]
    assert spoken.training({**SESSION, "scores_180": 0}) is None
    assert caplog.text.count("cannot be formatted") == 1
    assert "the summary of the training report" in caplog.text


# The "Darts today" and "Training streak" sensors of a board on the evening of a
# day without darts: the daily goal is open, and the streak ends at midnight.
OPEN = {"darts_today": 0, "goal": 10, "goal_reached": False, "streak": 4}


async def test_the_english_training_reminder(hass):
    english = await caller(hass, "en")
    assert english.goal_reminder(OPEN) == "10 darts left to your daily goal of 10."
    assert english.goal_reminder({**OPEN, "darts_today": 9}) == (
        "1 dart left to your daily goal of 10."
    )
    assert english.streak_reminder(OPEN) == (
        "Throw a dart today to keep your streak of 4 days."
    )
    assert english.streak_reminder({**OPEN, "streak": 1}) == (
        "Throw a dart today to keep your streak of 1 day."
    )
    # Nothing to remind of: no goal, the goal reached or passed after it was
    # lowered, a dart today, no streak.
    for records in (
        {**OPEN, "goal": 0},
        {**OPEN, "goal_reached": True},
        {**OPEN, "darts_today": 12},
    ):
        assert english.goal_reminder(records) is None
    for records in ({**OPEN, "trained_today": True}, {**OPEN, "streak": 0}):
        assert english.streak_reminder(records) is None
    # Before the words are loaded, the blueprint says its own.
    assert Caller().goal_reminder(OPEN) is None
    assert Caller().streak_reminder(OPEN) is None


@pytest.mark.parametrize(
    ("language", "goal", "streak"),
    [
        (
            "de-CH",
            "Noch 10 Darts bis zu deinem Tagesziel von 10.",
            "Wirf heute einen Dart, um deine Serie von 4 Tagen zu halten.",
        ),
        (
            "es-419",
            "Te faltan 10 dardos para tu objetivo diario de 10.",
            "Lanza un dardo hoy para mantener tu racha de 4 días.",
        ),
        (
            "nl",
            "Nog 10 darts tot je dagdoel van 10.",
            "Gooi vandaag een dart om je reeks van 4 dagen te houden.",
        ),
    ],
)
async def test_the_training_reminder_speaks_the_language(hass, language, goal, streak):
    spoken = await caller(hass, language)
    assert (spoken.goal_reminder(OPEN), spoken.streak_reminder(OPEN)) == (goal, streak)


async def test_a_broken_training_reminder_leaves_the_blueprint_its_own(hass, caplog):
    spoken = await caller(hass, "es")
    spoken.say["reminder_goal_darts"] = "{count} {"
    del spoken.say["reminder_streak_days"]
    assert spoken.goal_reminder(OPEN) is None
    assert spoken.streak_reminder(OPEN) is None
    # The other messages still speak, and the failure is logged once.
    assert spoken.goal_reminder({**OPEN, "darts_today": 9})
    assert spoken.streak_reminder({**OPEN, "streak": 1})
    assert caplog.text.count("cannot be formatted") == 1
    assert "the goal of the training reminder" in caplog.text
