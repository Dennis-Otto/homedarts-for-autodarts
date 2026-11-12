"""A local session must count observations, not messages or camera jitter."""

import pytest

from custom_components.homedarts.training import COUNTERS, TrainingSession

from .local_helpers import BULL, MISS, NOW, OUTER_BULL, S20, T20, board


def test_visits_duplicates_coordinates_and_bulls():
    session = TrainingSession(NOW)
    assert session.observe(board(), now=NOW) == []
    events = []
    for i in range(1, 4):
        events.extend(session.observe(board(*([T20] * i)), now=NOW))
    assert [event[0] for event in events] == [*["dart_detected"] * 3, "visit_thrown"]
    repeated = board(T20, T20, T20)
    repeated["throws"][0]["coords"] = {"x": 0.1, "y": 0.2}
    assert session.observe(repeated, now=NOW) == []
    assert session.snapshot()["darts"] == 3
    assert session.snapshot()["triples"] == 3
    # A visit counts as a 180 once it is complete, when the darts are pulled.
    assert session.snapshot()["scores_180"] == 0
    session.observe(board(), now=NOW)
    assert session.snapshot()["scores_180"] == 1
    # A miss next to a number keeps its number: it is still a miss.
    session.observe(board(BULL, OUTER_BULL, ("M7", 7, 0)), now=NOW)
    assert {key: session.snapshot()[key] for key in COUNTERS} == {
        "darts": 6,
        "points": 255,
        "doubles": 0,
        "triples": 3,
        "bulls": 2,
        "misses": 1,
        "visits": 2,
        "scores_100": 0,
        "scores_140": 0,
        "scores_180": 1,
    }


def test_corrections_revise_score_and_180_without_adding_darts():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, T20, T20), now=NOW)
    events = session.observe(board(T20, S20, T20), now=NOW)
    assert events == [
        (
            "dart_corrected",
            {"dart_index": 2, "segment": "S20", "score": 20, "previous": "T20"},
        )
    ]
    assert session.snapshot()["darts"] == 3
    assert session.snapshot()["triples"] == 2
    assert session.snapshot()["points"] == 140
    session.observe(board(T20, T20, T20), now=NOW)
    assert session.snapshot()["points"] == 180
    session.observe(board(), now=NOW)
    assert session.snapshot()["scores_180"] == 1
    assert session.snapshot()["scores_140"] == 0


def test_a_visit_counts_for_one_score_band_only_once_complete():
    """Totals of the bands never go down within a visit: T20 T20 would be a
    100+ visit until the third T20 makes it a 180."""
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    for darts in ((T20,), (T20, T20), (T20, T20, T20)):
        session.observe(board(*darts), now=NOW)
        assert [session.snapshot()[key] for key in COUNTERS[-3:]] == [0, 0, 0]
    # A restart keeps the visit on the board with its score band.
    assert session.stored()["scores_180"] == 1
    session.observe(board(), now=NOW)
    assert [session.snapshot()[key] for key in COUNTERS[-3:]] == [0, 0, 1]


TAKEOUT = {"status": "Takeout in progress", "event": "Takeout started"}


def test_partial_takeout_never_counts_remaining_darts_again():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, S20, BULL), now=NOW)
    session.observe(board(S20, BULL, **TAKEOUT), now=NOW)
    session.observe(board(BULL, **TAKEOUT), now=NOW)
    session.observe(board(), now=NOW)
    assert session.snapshot()["darts"] == 3
    assert session.snapshot()["points"] == 130
    session.observe(board(S20), now=NOW)
    assert session.snapshot()["darts"] == 4


def test_darts_still_being_pulled_are_neither_announced_nor_counted():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, S20, BULL), now=NOW)
    session.observe(board(S20, BULL, **TAKEOUT), now=NOW)
    # The same darts again, and one of them read differently, while pulling.
    assert session.observe(board(S20, BULL, **TAKEOUT), now=NOW) == []
    assert session.observe(board(S1, BULL), now=NOW) == []
    assert session.snapshot()["darts"] == 3
    assert session.snapshot()["points"] == 130


def test_darts_thrown_before_the_takeout_ends_are_counted():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, S20, BULL), now=NOW)
    session.observe(board(BULL, **TAKEOUT), now=NOW)
    events = session.observe(board(BULL, S20), now=NOW)
    assert events == [
        ("dart_detected", {"dart_index": 2, "segment": "S20", "score": 20})
    ]
    assert session.snapshot()["darts"] == 4
    assert session.snapshot()["points"] == 150


def test_missed_empty_board_between_visits_keeps_counting():
    # A slow poll can miss the empty frame; the next visit must still count.
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, T20, T20), now=NOW)
    events = session.observe(board(S20), now=NOW)
    events += session.observe(board(S20, BULL), now=NOW)
    events += session.observe(board(S20, BULL, OUTER_BULL), now=NOW)
    assert events[0] == (
        "visit_completed",
        {"score": 180, "darts": 3, "segments": ["T20", "T20", "T20"], "thrown": True},
    )
    assert [event[1]["segment"] for event in events[1:-1]] == ["S20", "Bull", "25"]
    # The next visit is complete with its third dart, before the takeout.
    assert events[-1] == (
        "visit_thrown",
        {"score": 95, "darts": 3, "segments": ["S20", "Bull", "25"]},
    )
    snapshot = session.snapshot()
    assert {key: snapshot[key] for key in ("darts", "bulls", "points")} == {
        "darts": 6,
        "bulls": 2,
        "points": 275,
    }
    assert snapshot["visits"] == 2
    assert snapshot["scores_180"] == 1


def test_transient_shorter_frame_does_not_split_a_visit():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, T20), now=NOW)
    assert session.observe(board(T20), now=NOW) == []
    session.observe(board(T20, T20), now=NOW)
    session.observe(board(T20, T20, T20), now=NOW)
    session.observe(board(), now=NOW)
    assert session.snapshot()["darts"] == 3
    assert session.snapshot()["scores_180"] == 1
    assert session.snapshot()["points"] == 180


def test_withdrawn_detection_no_longer_counts():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, S20, MISS), now=NOW)
    session.observe(board(T20, S20), now=NOW)
    session.observe(board(), now=NOW)
    assert session.snapshot()["darts"] == 2
    assert session.snapshot()["points"] == 80


def test_reset_ignores_darts_already_on_the_board():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, T20), now=NOW)
    session.new_session(now=NOW)
    assert all(session.snapshot()[key] == 0 for key in COUNTERS)
    assert session.observe(board(T20, T20), now=NOW) == []
    session.observe(board(T20, T20, T20), now=NOW)
    assert session.snapshot()["darts"] == 1
    session.observe(board(), now=NOW)
    assert session.snapshot()["scores_180"] == 0
    session.observe(board(T20, T20, T20), now=NOW)
    session.observe(board(), now=NOW)
    assert session.snapshot()["darts"] == 4
    assert session.snapshot()["scores_180"] == 1


def test_reload_restores_totals_and_does_not_replay_current_visit():
    old = TrainingSession(NOW)
    old.observe(board(), now=NOW)
    old.observe(board(T20, T20, T20), now=NOW)
    restored = TrainingSession(NOW)
    restored.restore(old.snapshot())
    assert restored.observe(board(T20, T20, T20), now=NOW) == []
    assert restored.snapshot() == old.snapshot()
    restored.observe(board(), now=NOW)
    restored.observe(board(BULL), now=NOW)
    assert restored.snapshot()["darts"] == 4
    assert restored.snapshot()["bulls"] == 1


@pytest.mark.parametrize("status", ["Starting", "Calibrating", "Stopped", "Error"])
def test_inactive_states_do_not_create_training_darts(status):
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    assert session.observe(board(T20, status=status), now=NOW) == []
    assert session.snapshot()["darts"] == 0


@pytest.mark.parametrize(
    "invalid",
    [
        {"numThrows": 1, "throws": []},
        {"numThrows": "1"},
        {"numThrows": 1, "throws": [None]},
        {"numThrows": 1, "throws": [{"segment": {"number": "20", "multiplier": 3}}]},
        {"numThrows": 1, "throws": [{"segment": "T20"}]},
        {"numThrows": 1, "throws": [{"segment": {"number": 21, "multiplier": 1}}]},
        {"numThrows": 1, "throws": [{"segment": {"number": 20, "multiplier": 4}}]},
        # The bull has no treble, and only a miss has no number.
        {"numThrows": 1, "throws": [{"segment": {"number": 25, "multiplier": 3}}]},
        {"numThrows": 1, "throws": [{"segment": {"number": 0, "multiplier": 1}}]},
    ],
)
def test_incomplete_or_malformed_snapshot_does_not_reset_visit(invalid):
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20), now=NOW)
    assert session.observe(board(**invalid), now=NOW) == []
    session.observe(board(T20, S20), now=NOW)
    assert session.snapshot()["darts"] == 2


def test_malformed_storage_is_sanitized():
    session = TrainingSession(NOW)
    session.restore({"darts": "bad", "points": -3, "bulls": True, "started": "bad"})
    assert all(session.snapshot()[key] == 0 for key in COUNTERS)


D16 = ("D16", 16, 2)
S1 = ("S1", 1, 1)


def test_analytics_buckets_hits_and_highest_visit():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    for visit in ((T20, T20, S20), (T20, S20, S20), (D16, S1, MISS), (T20, T20, T20)):
        for count in range(1, len(visit) + 1):
            session.observe(board(*visit[:count]), now=NOW)
        session.observe(board(), now=NOW)
    snapshot = session.snapshot()
    assert snapshot["visits"] == 4
    assert snapshot["scores_100"] == 1  # 100
    assert snapshot["scores_140"] == 1  # 140
    assert snapshot["scores_180"] == 1
    assert snapshot["highest_visit"] == 180
    assert snapshot["doubles"] == 1
    assert snapshot["misses"] == 1
    assert snapshot["hits"] == {"D16": 1, "MISS": 1, "S1": 1, "S20": 3, "T20": 6}


def test_a_merged_visit_never_sets_the_highest_visit():
    # A missed takeout merges the next darts into one visit of more than
    # three darts: like the score bands, it sets no highest visit, while its
    # darts and points still count.
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    for count in range(1, 4):
        session.observe(board(*[S20] * count), now=NOW)
    session.observe(board(), now=NOW)
    for count in range(1, 7):
        session.observe(board(*[T20] * count), now=NOW)
    bands = ("scores_100", "scores_140", "scores_180")
    live = session.snapshot()
    assert live["highest_visit"] == 60
    assert live["darts"] == 9 and live["points"] == 420
    assert [live[band] for band in bands] == [0, 0, 0]
    events = session.observe(board(), now=NOW)
    assert events[-1][0] == "visit_completed"
    assert events[-1][1]["score"] == 360 and events[-1][1]["darts"] == 6
    pulled = session.snapshot()
    assert pulled["highest_visit"] == 60
    assert pulled["visits"] == 2 and pulled["points"] == 420
    assert [pulled[band] for band in bands] == [0, 0, 0]
    _, summary = session.end("manual", now=NOW)
    assert summary["highest_visit"] == 60
    assert summary["darts"] == 9 and summary["points"] == 420
    assert [summary[band] for band in bands] == [0, 0, 0]


def test_completed_visits_are_announced_once():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20), now=NOW)
    session.observe(board(T20, S20), now=NOW)
    assert session.observe(board(T20, **TAKEOUT), now=NOW) == [
        (
            "visit_completed",
            {"score": 80, "darts": 2, "segments": ["T20", "S20"], "thrown": False},
        )
    ]
    assert session.observe(board(), now=NOW) == []
    session.observe(board(BULL), now=NOW)
    # Stopping the detection also ends the visit.
    assert session.observe(board(BULL, status="Stopped", running=False), now=NOW) == [
        (
            "visit_completed",
            {"score": 50, "darts": 1, "segments": ["Bull"], "thrown": False},
        )
    ]


def test_the_third_dart_announces_the_visit_once():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, T20), now=NOW)
    assert session.observe(board(T20, T20, S20), now=NOW) == [
        ("dart_detected", {"dart_index": 3, "segment": "S20", "score": 20}),
        (
            "visit_thrown",
            {"score": 140, "darts": 3, "segments": ["T20", "T20", "S20"]},
        ),
    ]
    # Neither a correction nor a withdrawn and detected dart announce it again.
    assert session.observe(board(T20, T20, T20), now=NOW) == [
        (
            "dart_corrected",
            {"dart_index": 3, "segment": "T20", "score": 60, "previous": "S20"},
        )
    ]
    assert session.observe(board(T20, T20), now=NOW) == []
    assert [kind for kind, _ in session.observe(board(T20, T20, T20), now=NOW)] == [
        "dart_detected"
    ]
    # The takeout completes it with the final score, marked as already thrown.
    assert session.observe(board(T20, **TAKEOUT), now=NOW) == [
        (
            "visit_completed",
            {"score": 180, "darts": 3, "segments": ["T20"] * 3, "thrown": True},
        )
    ]
    # The next visit is announced again.
    session.observe(board(), now=NOW)
    session.observe(board(BULL, BULL), now=NOW)
    assert session.observe(board(BULL, BULL, BULL), now=NOW)[-1] == (
        "visit_thrown",
        {"score": 150, "darts": 3, "segments": ["Bull"] * 3},
    )


def test_a_visit_without_three_announced_darts_is_not_thrown():
    session = TrainingSession(NOW)
    # A dart already in the board when Home Assistant starts is not announced.
    session.observe(board(T20), now=NOW)
    events = session.observe(board(T20, T20), now=NOW) + session.observe(
        board(T20, T20, T20), now=NOW
    )
    assert [kind for kind, _ in events] == ["dart_detected", "dart_detected"]
    assert session.observe(board(), now=NOW) == [
        (
            "visit_completed",
            {"score": 120, "darts": 2, "segments": ["T20", "T20"], "thrown": False},
        )
    ]
    # A detection withdrawn after the third dart leaves a thrown visit.
    session.observe(board(T20, T20, S20), now=NOW)
    session.observe(board(T20, T20), now=NOW)
    assert session.observe(board(), now=NOW) == [
        (
            "visit_completed",
            {"score": 120, "darts": 2, "segments": ["T20", "T20"], "thrown": True},
        )
    ]


def test_a_dart_without_a_name_is_named_by_its_bed():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    unnamed = board(T20, MISS)
    for dart in unnamed["throws"]:
        del dart["segment"]["name"]
    assert session.observe(unnamed, now=NOW) == [
        ("dart_detected", {"dart_index": 1, "segment": "T20", "score": 60}),
        ("dart_detected", {"dart_index": 2, "segment": "MISS", "score": 0}),
    ]


def test_average_inputs_and_restore_of_analytics():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, D16), now=NOW)
    session.observe(board(), now=NOW)
    restored = TrainingSession(NOW)
    restored.restore(session.snapshot())
    assert restored.snapshot() == session.snapshot()
    restored.restore(
        {**session.snapshot(), "highest_visit": -1, "hits": {"T20": "x", "S1": 2}}
    )
    assert restored.snapshot()["highest_visit"] == 0
    assert restored.snapshot()["hits"] == {"S1": 2}
    restored.restore({"darts": 3})
    assert restored.snapshot()["hits"] == {}
    restored.new_session(now=NOW)
    assert restored.snapshot()["highest_visit"] == 0
    assert restored.snapshot()["hits"] == {}


def ended_session(auto_start=False):
    session = TrainingSession(NOW)
    session.auto_start = auto_start
    session.observe(board(), now=NOW)
    session.observe(board(T20), now=NOW)
    session.observe(board(), now=NOW)
    kind, summary = session.end("manual", now=NOW)
    assert kind == "session_ended"
    assert summary["darts"] == 1 and summary["reason"] == "manual"
    return session


def test_darts_without_a_session_are_announced_but_not_counted():
    session = ended_session()
    before = session.snapshot()
    assert [kind for kind, _ in session.observe(board(T20, S20), now=NOW)] == [
        "dart_detected",
        "dart_detected",
    ]
    assert session.observe(board(), now=NOW) == [
        (
            "visit_completed",
            {"score": 80, "darts": 2, "segments": ["T20", "S20"], "thrown": False},
        )
    ]
    assert session.snapshot() == before
    assert session.recent_visits[0]["score"] == 80
    assert session.start(now=NOW) == (
        "session_started",
        {"started": session.started, "reason": "manual"},
    )
    assert session.start(now=NOW) is None
    assert all(session.snapshot()[key] == 0 for key in COUNTERS)


def test_the_first_dart_starts_a_session_automatically():
    session = ended_session(auto_start=True)
    events = session.observe(board(BULL), now=NOW)
    assert [kind for kind, _ in events] == ["session_started", "dart_detected"]
    assert events[0][1]["reason"] == "first_dart"
    assert session.active and session.snapshot()["darts"] == 1
    assert session.snapshot()["bulls"] == 1


def test_a_session_ignores_darts_already_on_the_board_but_announces_the_visit():
    session = ended_session()
    session.observe(board(T20, T20), now=NOW)
    session.start(now=NOW)
    session.observe(board(T20, T20, T20), now=NOW)
    assert session.snapshot()["darts"] == 1
    assert session.observe(board(), now=NOW) == [
        (
            "visit_completed",
            {"score": 180, "darts": 3, "segments": ["T20"] * 3, "thrown": True},
        )
    ]
    assert session.snapshot()["scores_180"] == 0


def test_darts_on_the_board_stay_with_the_ended_session():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, T20), now=NOW)
    _, summary = session.end("manual", now=NOW)
    assert summary["darts"] == 2 and summary["points"] == 120
    assert summary["visits"] == 1 and summary["highest_visit"] == 120
    session.observe(board(), now=NOW)
    assert session.snapshot()["darts"] == 2
    assert session.new_session(now=NOW) == [
        ("session_started", {"started": session.started, "reason": "new_session"})
    ]
    assert session.end("manual", now=NOW)[1]["darts"] == 0
    assert len(session.history) == 1
    assert session.end("manual", now=NOW) is None


def test_new_session_ends_the_running_one_and_history_keeps_twenty():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    for _ in range(25):
        session.observe(board(T20, S20, S1), now=NOW)
        session.observe(board(), now=NOW)
        kinds = [kind for kind, _ in session.new_session(now=NOW)]
        assert kinds == ["session_ended", "session_started"]
    assert len(session.history) == 20
    summary = session.history[0]
    assert summary["darts"] == 3 and summary["points"] == 81
    assert summary["average"] == 81.0
    assert summary["duration_minutes"] >= 0
    assert session.recent_visits[0]["segments"] == ["T20", "S20", "S1"]
    assert len(session.recent_visits) == 10


def test_version_1_storage_keeps_counting_and_everything_round_trips():
    session = TrainingSession(NOW)
    session.restore({"darts": 3, "points": 60, "started": "2026-09-01T10:00:00+00:00"})
    assert session.active and session.auto_start and session.idle_minutes == 0
    session.observe(board(), now=NOW)
    session.observe(board(T20, S20), now=NOW)
    session.observe(board(), now=NOW)
    session.end("manual", now=NOW)
    session.auto_start, session.idle_minutes = False, 15
    restored = TrainingSession(NOW)
    restored.restore(session.stored())
    assert restored.stored() == session.stored()
    assert not restored.active and restored.ended == session.ended


def test_malformed_session_storage_is_sanitized():
    session = TrainingSession(NOW)
    valid = {
        "started": "2026-09-01T10:00:00+00:00",
        "ended": "2026-09-01T10:30:00+00:00",
        "darts": 3,
        "points": 60,
    }
    session.restore(
        {
            "active": "yes",
            "auto_start": 1,
            "idle_minutes": 999,
            "ended": "2026-09-01T10:30:00+00:00",
            "last_activity": "yesterday",
            "history": [valid, {"started": "bad", "ended": "bad"}, "junk"],
            "recent_visits": [
                {"time": "2026-09-01T10:10:00+00:00", "score": 60, "segments": ["T20"]},
                {"time": "2026-09-01T10:11:00+00:00", "segments": [1]},
                {"time": "bad", "segments": []},
                None,
            ],
        }
    )
    assert session.active and session.auto_start and session.idle_minutes == 0
    assert session.ended is None and session.last_activity is None
    assert len(session.history) == 1
    assert session.history[0]["average"] == 60.0
    assert session.history[0]["duration_minutes"] == 30.0
    assert session.recent_visits == [
        {
            "time": "2026-09-01T10:10:00+00:00",
            "score": 60,
            "darts": 0,
            "segments": ["T20"],
        }
    ]


def dart(name, number, multiplier):
    return {"number": number, "multiplier": multiplier, "name": name}


def test_gap_continues_a_visit_whose_darts_are_still_on_the_board():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20), now=NOW)
    session.suspend()
    events = session.observe(board(T20, S20), now=NOW)
    assert [kind for kind, _ in events] == ["dart_detected"]
    assert events[0][1]["dart_index"] == 2
    assert session.visit() == [dart(*T20), dart(*S20)]
    assert session.observe(board(), now=NOW) == [
        (
            "visit_completed",
            {"score": 80, "darts": 2, "segments": ["T20", "S20"], "thrown": False},
        )
    ]


def test_gap_completes_a_visit_that_was_pulled_meanwhile():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20, T20), now=NOW)
    session.suspend()
    # Pulled and thrown again while the board was out of sight.
    assert session.observe(board(S20), now=NOW) == [
        (
            "visit_completed",
            {"score": 120, "darts": 2, "segments": ["T20", "T20"], "thrown": False},
        )
    ]
    assert session.visit() == []
    assert session.snapshot()["darts"] == 2
    events = session.observe(board(S20, BULL), now=NOW)
    assert [(kind, details["dart_index"]) for kind, details in events] == [
        ("dart_detected", 2)
    ]


def test_gap_waits_for_a_valid_state():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.observe(board(T20), now=NOW)
    session.suspend()
    assert session.observe({"running": True, "numThrows": "?"}, now=NOW) == []
    assert session.observe(board(), now=NOW) == [
        (
            "visit_completed",
            {"score": 60, "darts": 1, "segments": ["T20"], "thrown": False},
        )
    ]


def test_gap_before_the_first_state_or_with_a_stopped_board():
    session = TrainingSession(NOW)
    session.suspend()
    # Darts found at the start are never counted.
    assert session.observe(board(T20), now=NOW) == []
    assert [kind for kind, _ in session.observe(board(T20, S20), now=NOW)] == [
        "dart_detected"
    ]
    session.suspend()
    events = session.observe(board(T20, S20, running=False), now=NOW)
    assert events == [
        (
            "visit_completed",
            {"score": 20, "darts": 1, "segments": ["S20"], "thrown": False},
        )
    ]
    # The stop settled the visit; the same darts after a restart count nothing.
    assert session.observe(board(T20, S20), now=NOW) == []


def test_the_bots_darts_never_start_a_session():
    session = TrainingSession(NOW)
    session.observe(board(), now=NOW)
    session.end("manual", now=NOW)
    bot = board(T20)
    bot["throws"][0]["bot"] = True
    assert [kind for kind, _ in session.observe(bot, now=NOW)] == ["dart_detected"]
    assert session.active is False
    # A player's dart after it does, and the bot's dart stays uncounted.
    both = board(T20, S20)
    both["throws"][0]["bot"] = True
    events = session.observe(both, now=NOW)
    assert [kind for kind, _ in events] == ["session_started", "dart_detected"]
    assert session.snapshot()["darts"] == 1
