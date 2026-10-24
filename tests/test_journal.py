"""The training journal: a year of sessions and matches for the calendar."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.homedarts.cricket import CRICKET_GAMES
from custom_components.homedarts.journal import (
    GAME_NAMES,
    JournalEvent,
    TrainingJournal,
    game_name,
    match_description,
    match_entry,
    match_title,
    player_results,
    session_description,
    session_entry,
    session_title,
)
from custom_components.homedarts.party import PARTY_GAMES
from custom_components.homedarts.practice import PARTY_PLAYERS

NOW = datetime(2026, 9, 27, 20, 0, tzinfo=dt_util.UTC)


def at(minutes: float) -> str:
    """A moment relative to NOW, as the integration stores it."""
    return (NOW + timedelta(minutes=minutes)).isoformat()


def session(start: float, end: float, darts: int = 30, points: int = 540, **counts):
    return {
        "started": at(start),
        "ended": at(end),
        "duration_minutes": end - start,
        "darts": darts,
        "points": points,
        "average": 54.0,
        "visits": darts // 3,
        **counts,
    }


def match(end: float, game=501, players=None, **changes):
    return {
        "ended": at(end),
        "game": game,
        "legs_to_win": 3,
        "sets_to_win": 1,
        "winner": 1,
        "players": [
            {"name": "Alex", "legs": 0, "sets": 1, "average": 62.44},
            {"name": "Sam", "legs": 2, "sets": 0, "average": 55.1},
        ]
        if players is None
        else players,
        **changes,
    }


def test_sessions_keep_their_counts_and_drop_what_is_broken():
    entry = session_entry(session(-60, -15, scores_180=1, highest_visit=180))
    assert entry == {
        "started": at(-60),
        "ended": at(-15),
        "darts": 30,
        "points": 540,
        "visits": 10,
        "highest_visit": 180,
        "scores_100": 0,
        "scores_140": 0,
        "scores_180": 1,
        "triples": 0,
        "doubles": 0,
        "bulls": 0,
        "misses": 0,
    }
    for broken in (
        None,
        {"started": at(0)},
        {"started": "2026-09-27T20:00:00", "ended": at(5)},
        session(10, 5),
    ):
        assert session_entry(broken) is None


def test_matches_keep_players_results_and_a_plausible_start():
    entry = match_entry(
        match(
            0,
            started=at(5),
            winner=7,
            players=[
                {"name": "  Alexandra Konstantinopoulou  ", "legs": 1, "mpr": 2.456},
                {"name": "   ", "legs": True, "points": float("inf")},
                "Kim",
            ],
            game="cricket",
        )
    )
    assert entry["started"] is None
    assert entry["winner"] is None
    assert entry["players"] == [
        {"name": "Alexandra Konstantin", "legs": 1, "sets": 0, "mpr": 2.456},
        {"name": None, "legs": 0, "sets": 0},
        {"name": None, "legs": 0, "sets": 0},
    ]
    assert match_entry(match(0, started=at(-20)))["started"] == at(-20)
    for broken in (
        "501",
        match(0, ended="soon"),
        match(0, game="darts"),
        match(0, game=0),
        match(0, players="Alex"),
        match(0, players=[]),
        match(0, players=[{}] * (PARTY_PLAYERS + 1)),
    ):
        assert match_entry(broken) is None


def party(end: float, players: int = PARTY_PLAYERS) -> dict:
    """A Count-Up match of a party, which Alex wins."""
    names = ["Alex", "Sam", "Kim", "Lea", "Mia", "Leo", "Zoe", "Ben"][:players]
    return match(
        end,
        game="count_up",
        legs_to_win=1,
        players=[
            {"name": name, "legs": 0, "sets": 0, "points": 60 if name == "Alex" else 1}
            for name in names
        ],
    )


def test_a_party_match_keeps_all_of_its_eight_players():
    entry = match_entry(party(0))
    assert len(entry["players"]) == PARTY_PLAYERS
    assert match_title(entry) == (
        "Count-Up · Alex 1 · Sam 0 · Kim 0 · Lea 0 · Mia 0 · Leo 0 · Zoe 0 · Ben 0"
    )
    assert match_description(entry).splitlines()[-1] == "Ben: 1"


def test_the_winner_of_a_set_gets_the_legs_it_needed():
    entry = match_entry(match(0))
    assert [player["legs"] for player in player_results(entry)] == [3, 2]
    assert match_title(entry) == "501 · Alex 3:2 Sam"
    sets = match_entry(
        match(
            0,
            sets_to_win=2,
            winner=2,
            players=[{"name": "Alex", "legs": 1, "sets": 1}, {"name": None, "sets": 2}],
        )
    )
    assert match_title(sets) == "501 · Alex 1:2 #2"


def journal_with(*, sessions=(), matches=()) -> TrainingJournal:
    journal = TrainingJournal()
    journal.sync(list(sessions), list(matches), NOW)
    return journal


def test_calendar_titles_and_descriptions_read_the_same_in_every_language():
    journal = journal_with(
        sessions=[
            session(-60, -60, darts=0, points=0),
            session(
                -240, -180, darts=312, points=5642, scores_140=3, highest_visit=140
            ),
        ],
        matches=[
            match(
                -10,
                game="killer",
                winner=3,
                legs_to_win=1,
                players=[
                    {"name": "Alex", "legs": 0, "points": 1},
                    {"name": None, "legs": 0},
                    {"name": "Kim", "legs": 0, "points": 3},
                ],
            ),
            match(
                -100,
                game="cricket",
                players=[
                    {"name": "Alex", "legs": 0, "sets": 1, "mpr": 2.4},
                    {"name": "Sam", "legs": 1, "sets": 0, "mpr": 1.95},
                ],
            ),
            match(-120),
        ],
    )
    events = journal.events(NOW - timedelta(days=1), NOW)
    assert [(event.summary, event.description) for event in events] == [
        (
            "Training · 312 Darts · Ø 54.2",
            "180: 0 · 140+: 3 · 100+: 0 · Max: 140",
        ),
        ("501 · Alex 3:2 Sam", "Alex: Ø 62.4\nSam: Ø 55.1"),
        ("Cricket · Alex 3:1 Sam", "Alex: MPR 2.40\nSam: MPR 1.95"),
        ("Training · 0 Darts", "180: 0 · 140+: 0 · 100+: 0 · Max: 0"),
        ("Killer · Alex 0 · #2 0 · Kim 1", "Alex: 1\nKim: 3"),
    ]


@pytest.mark.parametrize("game", [*CRICKET_GAMES, *PARTY_GAMES])
def test_the_journal_knows_every_game_by_its_name(game):
    entry = match_entry(match(0, game=game))
    assert entry["game"] == game
    assert match_title(entry).startswith(f"{GAME_NAMES[game]} · ")
    assert set(GAME_NAMES) == {*CRICKET_GAMES, *PARTY_GAMES}
    assert game_name(501) == "501"


def test_the_bot_and_teams_keep_their_seats_in_the_calendar():
    bot = match_entry(
        match(
            0,
            winner=2,
            players=[
                {"name": "Alex", "legs": 1, "average": 50.0},
                {"name": None, "legs": 2, "bot": True, "average": 60.0},
            ],
        )
    )
    assert bot["players"][1]["bot"] is True
    assert match_title(bot) == "501 · Alex 1:3 Bot"
    assert match_description(bot) == "Alex: Ø 50.0\nBot: Ø 60.0"
    players = [
        {"name": "Alex", "legs": 1, "team": 1},
        {"name": "Sam", "legs": 0, "team": 2},
        {"name": "Kim", "legs": 1, "team": 1},
        {"name": None, "legs": 0, "team": 2, "bot": True},
    ]
    teams = match_entry(match(0, legs_to_win=1, players=players))
    assert [player["team"] for player in teams["players"]] == [1, 2, 1, 2]
    assert match_title(teams) == "501 · Alex & Kim 1:0 Sam & Bot"
    # Seats of anything but two teams of two read player by player.
    odd = match_entry(
        match(0, legs_to_win=1, players=[*players[:3], {"name": "Lea", "team": 3}])
    )
    assert "team" not in odd["players"][3]
    assert match_title(odd) == "501 · Alex 1 · Sam 0 · Kim 1 · Lea 0"


def test_calendar_entries_read_in_the_language_of_home_assistant():
    entry = session_entry(
        session(-60, 0, darts=312, points=5642, scores_140=3, highest_visit=140)
    )
    assert session_title(entry, "de") == "Training · 312 Darts · Ø 54,2"
    assert session_title(entry, "nl") == "Training · 312 darts · Ø 54,2"
    assert session_title(entry, "fr") == "Entraînement · 312 fléchettes · Ø 54,2"
    assert session_title(entry, "es-419") == "Entrenamiento · 312 dardos · Ø 54,2"
    assert session_title(entry, "en-GB") == session_title(entry, "pt")
    assert session_title(entry, "pt") == "Training · 312 Darts · Ø 54.2"
    assert session_description(entry, "es").endswith("Máx.: 140")
    cricket = match_entry(
        match(
            0, game="cricket", players=[{"name": "Alex", "mpr": 2.4}, {"name": "Sam"}]
        )
    )
    assert match_description(cricket, "fr") == "Alex: MPR 2,40"
    language = "en"
    journal = TrainingJournal(lambda: language)
    journal.sync([session(-60, -10, darts=3, points=100)], [], NOW)
    assert journal.latest().summary == "Training · 3 Darts · Ø 100.0"
    language = "de"
    assert journal.latest().summary == "Training · 3 Darts · Ø 100,0"


def test_an_undone_visit_takes_its_match_back_from_the_journal():
    journal = journal_with(matches=[match(-10)])
    assert journal.last_match() == at(-10)
    journal.sync([], [match(-2), match(-10)], NOW)
    assert journal.rewind(at(-10)) is True
    assert [entry["ended"] for entry in journal.matches] == [at(-10)]
    assert journal.rewind(at(-10)) is False
    assert journal.rewind(None) is True
    assert journal.matches == [] and journal.last_match() is None


def test_a_renamed_player_keeps_the_matches_of_the_calendar():
    players = [{"name": "Sammy", "legs": 2}, {"name": "sam", "legs": 0}]
    journal = journal_with(matches=[match(-2), match(-10, players=players)])
    assert journal.rename(" SAMMY ", "Sam") is True
    assert [
        [player["name"] for player in entry["players"]] for entry in journal.matches
    ] == [
        ["Sam", "Sam"],
        ["Alex", "Sam"],
    ]
    assert journal.rename("Nobody", "Kim") is False


def test_events_last_at_least_a_minute_and_matches_start_with_their_first_dart():
    journal = TrainingJournal()
    journal.sync(
        [session(-50, -50, darts=1, points=20)],
        [match(-5, game=301, started=at(-30))],
        NOW,
    )
    session_event, match_event = journal.events(NOW - timedelta(hours=1), NOW)
    assert session_event == JournalEvent(
        uid=f"session-{at(-50)}",
        start=NOW - timedelta(minutes=51),
        end=NOW - timedelta(minutes=50),
        summary="Training · 1 Darts · Ø 60.0",
        description="180: 0 · 140+: 0 · 100+: 0 · Max: 0",
    )
    assert (match_event.start, match_event.end) == (
        NOW - timedelta(minutes=30),
        NOW - timedelta(minutes=5),
    )
    # A match from before the journal knew its first dart lasts a minute.
    journal.sync([], [match(30, game=501, started=None)], NOW)
    assert journal.matches[-1]["started"] is None
    assert journal.latest().end == NOW + timedelta(minutes=30)
    assert journal.latest().start == NOW + timedelta(minutes=29)


def test_only_new_sessions_and_matches_are_taken_over():
    journal = TrainingJournal()
    assert journal.latest() is None
    history = [session(-30, -20), session(-90, -60)]
    assert journal.sync(history, [match(-40)], NOW) is True
    assert journal.sync(history, [match(-40)], NOW) is False
    history.insert(0, session(-10, -5))
    assert journal.sync(history, [match(-2), match(-40)], NOW) is True
    assert [entry["ended"] for entry in journal.sessions] == [at(-60), at(-20), at(-5)]
    assert [entry["ended"] for entry in journal.matches] == [at(-40), at(-2)]
    assert journal.latest().uid == f"match-{at(-2)}"
    # Broken entries of the sources are skipped.
    assert journal.sync([None, {"ended": "x"}], [{"game": 501}], NOW) is False


def test_the_first_look_takes_over_the_matches_the_journal_missed():
    """Up to version 1.12.2, the journal left out the party matches of more than
    four players. The profiles keep their last matches, which come back once."""
    year = 365 * 24 * 60
    journal = TrainingJournal()
    journal.restore({"matches": [match_entry(match(-40)), match_entry(match(-10))]})
    profiles = [match(-10), party(-20, players=5), match(-40), party(-year - 5)]
    assert journal.sync([], profiles, NOW) is True
    # In their place; a match older than a year stays out.
    assert [entry["ended"] for entry in journal.matches] == [at(-40), at(-20), at(-10)]
    assert journal.matches[1]["players"][4]["name"] == "Mia"
    assert journal.sync([], profiles, NOW) is False
    assert journal.sync([], [party(-5), *profiles], NOW) is True
    assert journal.matches[-1]["ended"] == at(-5)


def test_the_journal_keeps_a_year_and_a_bounded_number_of_entries():
    year = 365 * 24 * 60
    journal = journal_with(
        sessions=[session(-10, -5), session(-year - 60, -year - 30)],
        matches=[match(-year + 30)],
    )
    assert len(journal.sessions) == 1
    assert len(journal.matches) == 1
    assert journal.sync([], [], NOW + timedelta(hours=1)) is True
    assert journal.matches == []
    with patch("custom_components.homedarts.journal.JOURNAL_SIZE", 2):
        journal.sync([session(-3, -2), session(-4, -3.5)], [], NOW)
    assert [entry["ended"] for entry in journal.sessions] == [at(-3.5), at(-2)]


def test_events_of_a_period_overlap_it():
    journal = journal_with(sessions=[session(-30, -10), session(-120, -60)])

    def summaries(start, end):
        return [
            event.uid
            for event in journal.events(
                NOW + timedelta(minutes=start), NOW + timedelta(minutes=end)
            )
        ]

    assert summaries(-60, -30) == []
    assert summaries(-61, -30) == [f"session-{at(-60)}"]
    assert summaries(-20, 0) == [f"session-{at(-10)}"]
    assert summaries(-200, 0) == [f"session-{at(-60)}", f"session-{at(-10)}"]


def test_the_journal_survives_a_restart():
    journal = journal_with(sessions=[session(-30, -20)], matches=[match(-10)])
    restored = TrainingJournal()
    restored.restore(journal.stored())
    assert restored.stored() == journal.stored()


@pytest.mark.parametrize(
    "saved",
    [
        None,
        {"sessions": "all", "matches": None, "match_start": "now"},
        {
            "sessions": [session(-30, -20), session(-90, -60), None],
            "matches": [
                match(-10),
                match(-10),
                {"ended": at(0)},
                # Stored data may hold anything, even a list for a game.
                match(-5, game=["golf"]),
            ],
            "match_start": {"time": at(0), "game": "golf"},
        },
    ],
)
def test_broken_or_unordered_storage_keeps_what_is_valid(saved):
    journal = TrainingJournal()
    journal.restore(saved)
    stored = journal.stored()
    assert len(stored["sessions"]) <= 1
    assert len(stored["matches"]) <= 1
    assert "match_start" not in stored
