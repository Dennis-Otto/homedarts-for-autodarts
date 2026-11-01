"""X01 visits entered as their score: the made-up darts, the rules they keep, the
statistics they count for, and the action with its refusals."""

import itertools

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.homedarts.doubles import DoubleHits
from custom_components.homedarts.practice import VisitRefused
from custom_components.homedarts.scoring import (
    DOUBLE,
    SCORE_BEDS,
    STRAIGHT,
    evaluate_visit,
    is_double,
    score,
    visit_darts,
)
from custom_components.homedarts.training import TrainingSession, dart_flags

from .local_helpers import (
    NOW,
    board,
    entity_id,
    match,
    playing,
    record,
    setup_local,
    state,
)
from .test_manual_board import act, entity, setup_manual, value


def names(darts) -> list[str]:
    return [dart["name"] for dart in darts]


def outcome(start: int, points: int, double_out: bool, finish: bool) -> str | None:
    """What a visit of these points does by the rules: what is left checks out where
    a finish exists and otherwise busts, as do more and, with double out, 1 left."""
    if points == start and finish:
        return "won"
    if points >= start or (double_out and start - points == 1):
        return "bust"
    return None


# -- the made-up darts -----------------------------------------------------------------


def test_a_score_becomes_the_darts_players_throw_for_it():
    assert names(visit_darts(501, 140, 3, DOUBLE)) == ["T20", "T20", "S20"]
    assert names(visit_darts(501, 100, 3, DOUBLE)) == ["T20", "S20", "S20"]
    assert names(visit_darts(501, 180, 3, DOUBLE)) == ["T20", "T20", "T20"]
    assert names(visit_darts(501, 0, 3, DOUBLE)) == ["MISS", "MISS", "MISS"]
    # A checkout ends with a double, or with any bed without double out.
    assert names(visit_darts(40, 40, 1, DOUBLE)) == ["D20"]
    assert names(visit_darts(100, 100, 2, DOUBLE)) == ["T20", "D20"]
    assert names(visit_darts(170, 170, 3, DOUBLE)) == ["T20", "T20", "BULL"]
    assert names(visit_darts(60, 60, 1, STRAIGHT)) == ["T20"]
    assert visit_darts(100, 100, 1, DOUBLE) is None
    # A bust ends with the dart that busts.
    assert evaluate_visit(32, visit_darts(32, 40, 3, DOUBLE), DOUBLE) == (32, "bust", 3)
    assert evaluate_visit(41, visit_darts(41, 40, 3, DOUBLE), DOUBLE) == (41, "bust", 3)
    # What is left busts where no double finishes it, with the last dart if it can.
    assert names(visit_darts(159, 159, 3, DOUBLE)) == ["T20", "T20", "T13"]
    assert evaluate_visit(159, visit_darts(159, 159, 3, DOUBLE), DOUBLE)[1:] == (
        "bust",
        3,
    )
    assert names(visit_darts(60, 60, 1, DOUBLE)) == ["T20"]
    # A bust that can't wait for the last dart comes as late as it can: from 32, the
    # first two darts of 100 leave 2 at most, and no third dart scores 70 or more.
    assert names(visit_darts(32, 100, 3, DOUBLE)) == ["S20", "T20", "S20"]
    assert evaluate_visit(32, visit_darts(32, 100, 3, DOUBLE), DOUBLE) == (
        32,
        "bust",
        2,
    )
    assert evaluate_visit(2, visit_darts(2, 180, 3, DOUBLE), DOUBLE) == (2, "bust", 1)
    assert visit_darts(32, 100, 1, DOUBLE) is None
    # A leg that still needs a double opens with the first dart that scores.
    opened = visit_darts(501, 60, 3, DOUBLE, opening=DOUBLE)
    assert is_double(opened[0])
    assert names(visit_darts(501, 0, 3, DOUBLE, opening=DOUBLE)) == ["MISS"] * 3
    assert visit_darts(501, 1, 3, DOUBLE, opening=DOUBLE) is None
    # No three darts make 179.
    assert visit_darts(501, 179, 3, DOUBLE) is None


@pytest.mark.parametrize("start", [2, 3, 32, 41, 60, 99, 159, 170, 301])
@pytest.mark.parametrize("double_out", [True, False])
def test_every_score_has_darts_exactly_when_three_darts_can_throw_it(start, double_out):
    mode = DOUBLE if double_out else STRAIGHT
    """Every visit of three darts from the start, compared with the darts made up
    for its score: there are some exactly when one does what the rules say of the
    score, and they keep the rules. A checkout, and a bust where it can, ends
    with the last dart, so that every dart counts; any other bust comes as late
    as it can."""
    latest: dict[tuple[int, str | None], int] = {}
    for visit in itertools.product(SCORE_BEDS, repeat=3):
        points = sum(map(score, visit))
        result, counted = evaluate_visit(start, list(visit), mode)[1:]
        latest[points, result] = max(latest.get((points, result), 0), counted)
    for points in range(181):
        darts = visit_darts(start, points, 3, mode)
        wanted = outcome(start, points, double_out, (points, "won") in latest)
        assert (darts is not None) == ((points, wanted) in latest), points
        if darts:
            assert sum(map(score, darts)) == points
            assert evaluate_visit(start, darts, mode)[1:] == (
                wanted,
                latest[points, wanted],
            )


# -- the practice game -------------------------------------------------------------------


def test_a_score_visit_marks_its_darts_and_those_at_a_double():
    game = playing(501)
    darts = game.score_visit(140)
    assert [dart.get("total") for dart in darts] == [True] * 3
    assert not any(dart.get("at_double") for dart in darts)
    game = playing(501, remaining=40)
    darts = game.score_visit(40, darts=3, at_double=2)
    assert [bool(dart.get("at_double")) for dart in darts] == [False, True, True]
    # A checkout throws one dart at a double unless told otherwise.
    assert [bool(dart.get("at_double")) for dart in game.score_visit(40, 2)] == [
        False,
        True,
    ]
    # Without double out, no dart is at a double.
    game = playing(501, remaining=40, double_out=False)
    assert not any(dart.get("at_double") for dart in game.score_visit(40, 1, 1))


def test_the_darts_at_a_double_of_a_bust_are_darts_that_count():
    """The darts after a bust do not count, so a bust before the last dart has its
    darts at a double among those before."""
    game = playing(501, remaining=32)
    darts = game.score_visit(100, at_double=3)
    assert names(darts) == ["S20", "T20", "S20"]
    assert [bool(dart.get("at_double")) for dart in darts] == [True, True, False]
    assert [bool(dart.get("at_double")) for dart in game.score_visit(100, 3, 1)] == [
        False,
        True,
        False,
    ]
    # A bust throws no dart at a double unless told otherwise, nor does what is
    # left without a finish.
    assert not any(dart.get("at_double") for dart in game.score_visit(100))
    assert not any(dart.get("at_double") for dart in playing(501, 159).score_visit(159))
    for count in range(1, 4):
        game.track(darts[:count], now=NOW)
    game.finish_visit(now=NOW)
    player = game.players[0]
    assert (player.remaining, player.darts, player.at_double) == (32, 2, 2)


def test_a_checkout_asked_for_where_none_exists_is_refused():
    """What is left without a finish busts as a score, but is no checkout."""
    game = playing(501, remaining=159)
    with pytest.raises(VisitRefused) as error:
        game.score_visit(159, checkout=True)
    assert error.value.key == "checkout_impossible"
    assert error.value.placeholders == {"remaining": "159"}
    assert evaluate_visit(159, game.score_visit(159), DOUBLE)[1] == "bust"
    # Nor is a checkout that no darts score, or none of these darts.
    for start, darts in ((179, None), (100, 1)):
        with pytest.raises(VisitRefused) as error:
            playing(501, remaining=start).score_visit(start, darts, checkout=True)
        assert error.value.key == "checkout_impossible"
    darts = playing(501, remaining=40).score_visit(40, 2, checkout=True)
    assert evaluate_visit(40, darts, DOUBLE) == (0, "won", 2)


@pytest.mark.parametrize(
    ("setup", "points", "darts", "at_double", "key"),
    [
        ({"game": 0}, 60, None, None, "visit_not_x01"),
        ({"winner": 0}, 60, None, None, "visit_not_x01"),
        ({"hold": True}, 60, None, None, "visit_not_x01"),
        ({}, 179, None, None, "visit_impossible"),
        ({"remaining": 32}, 179, None, None, "visit_impossible"),
        ({"remaining": 32}, 100, 1, None, "visit_impossible"),
        ({"remaining": 32}, 100, None, 4, "visit_at_double"),
        ({"remaining": 40}, 40, 3, 0, "visit_at_double"),
        ({}, 60, 2, 3, "visit_at_double"),
    ],
)
def test_a_score_visit_the_game_cannot_take_is_refused(
    setup, points, darts, at_double, key
):
    # A copy: the parameters stay the same for the next run in this process.
    setup = dict(setup)
    game = playing(301, remaining=setup.pop("remaining", None))
    for name, value_ in setup.items():
        setattr(game, name, value_)
    with pytest.raises(VisitRefused) as error:
        game.score_visit(points, darts, at_double)
    assert error.value.key == key


def test_a_score_visit_is_refused_in_the_bull_off():
    game = match(2)
    game.set_option("bull_off", True)
    game.new_match()
    assert game.bulling
    with pytest.raises(VisitRefused):
        game.score_visit(60)


def test_the_darts_at_a_double_count_for_the_checkout_rate():
    game = playing(501, remaining=40)
    darts = game.score_visit(40, 3, 3)
    for count in range(1, 4):
        game.track(darts[:count], now=NOW)
    game.finish_visit(now=NOW)
    assert game.statistics()["checkout_rate"] == pytest.approx(33.3)
    assert game.statistics()["darts_at_double"] == 3


def test_made_up_darts_hit_no_bed_of_the_statistics():
    doubles = DoubleHits()
    doubles.record([{"number": 20, "multiplier": 2, "name": "D20", "total": True}])
    assert doubles.counts == {}
    assert dart_flags([{"number": 20, "multiplier": 3, "total": True}]) == {
        "total": True
    }
    session = TrainingSession(NOW)
    darts = [{**dart, "manual": True} for dart in playing(501).score_visit(180)]
    session.observe(board(), now=NOW)
    session.observe(
        {
            **board(),
            "numThrows": 3,
            "throws": [
                {"segment": dict(dart), "manual": True, "total": True} for dart in darts
            ],
        },
        now=NOW,
    )
    snapshot = session.snapshot()
    assert snapshot["points"] == 180 and snapshot["darts"] == 3
    assert snapshot["triples"] == 0 and snapshot["hits"] == {}
    assert snapshot["total_darts"] == 3 and snapshot["manual_darts"] == 3


# -- the action --------------------------------------------------------------------------


async def test_a_visit_entered_as_its_score_counts_like_its_darts(hass):
    entry = await setup_manual(hass)
    coordinator = entry.runtime_data.local
    await act(hass, "start_game", game="501", players=["Alex", "Sam"])
    events = record(hass, coordinator)
    await act(hass, "enter_visit", score=140)
    assert value(hass, "sensor", "practice_remaining") == "501"
    practice = hass.states.get(entity(hass, "sensor", "practice_remaining"))
    assert practice.attributes["scores"][0]["remaining"] == 361
    assert practice.attributes["name"] == "Sam"
    assert value(hass, "sensor", "training_darts") == "3"
    assert value(hass, "sensor", "training_points") == "140"
    assert value(hass, "sensor", "training_scores_140") == "1"
    # The beds are made up, so they count for no bed.
    assert value(hass, "sensor", "training_triples") == "0"
    kinds = [kind for kind, _ in events]
    assert "dart_detected" not in kinds
    completed = next(item for kind, item in events if kind == "visit_completed")
    assert completed["score"] == 140 and completed["segments"] == []
    assert completed["total"] is True and completed["manual"] is True
    visit = hass.states.get(entity(hass, "sensor", "local_visit_score"))
    assert visit.attributes["recent_visits"][0]["total"] is True
    assert coordinator.games.training.snapshot()["total_darts"] == 3


async def test_a_score_visit_checks_out_and_busts(hass):
    entry = await setup_manual(hass)
    coordinator = entry.runtime_data.local
    await act(hass, "start_game", game="101", players=["Alex"])
    await act(hass, "enter_visit", score=61)
    # 40 is left: a score of more busts, and the visit scores nothing.
    events = record(hass, coordinator)
    await act(hass, "enter_visit", score=45, darts_at_double=2)
    assert [kind for kind, _ in events].count("bust") == 1
    assert value(hass, "sensor", "practice_remaining") == "40"
    await act(hass, "enter_visit", score=40, darts=2, darts_at_double=2)
    leg = next(item for kind, item in events if kind == "leg_won")
    assert leg["darts"] == 8 and leg["checkout"] == 40
    statistics = coordinator.games.practice.statistics()
    assert statistics["darts_at_double"] == 4
    assert statistics["checkout_rate"] == 25.0


def remaining_scores(hass) -> list[int]:
    practice = hass.states.get(entity(hass, "sensor", "practice_remaining"))
    return [score["remaining"] for score in practice.attributes["scores"]]


async def test_every_busting_score_busts_and_passes_the_turn(hass):
    """More than is left busts, also where no visit throws all of it before the
    bust, and so does what is left where no double finishes it."""
    entry = await setup_manual(hass)
    coordinator = entry.runtime_data.local
    await act(hass, "start_game", game="301", players=["Alex", "Sam"])
    for points in (180, 60, 89, 82):
        await act(hass, "enter_visit", score=points)
    assert remaining_scores(hass) == [32, 159]
    events = record(hass, coordinator)
    await act(hass, "enter_visit", score=100)
    await act(hass, "enter_visit", score=159)
    assert remaining_scores(hass) == [32, 159]
    busts = [item for kind, item in events if kind == "bust"]
    assert [(item["name"], item["remaining"]) for item in busts] == [
        ("Alex", 32),
        ("Sam", 159),
    ]
    assert value(hass, "sensor", "practice_remaining") == "32"
    # Asked for as a checkout, it is refused: no visit checks out 159.
    await act(hass, "enter_visit", score=0)
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "enter_visit", checkout=True)
    assert error.value.translation_key == "checkout_impossible"
    assert remaining_scores(hass) == [32, 159]
    assert not any(kind == "leg_won" for kind, _ in events)


async def test_darts_entered_by_hand_give_way_to_the_visit_score(hass):
    entry = await setup_manual(hass)
    coordinator = entry.runtime_data.local
    await act(hass, "start_game", game="301", players=["Alex"])
    await act(hass, "throw_dart", segment="S1")
    await act(hass, "enter_visit", score=60)
    assert value(hass, "sensor", "practice_remaining") == "241"
    assert value(hass, "sensor", "training_darts") == "3"
    # The visit comes back with its undo, and another score takes its place.
    await act(hass, "undo_visit")
    assert value(hass, "sensor", "local_visit_score") == "60"
    await act(hass, "enter_visit", score=100)
    assert value(hass, "sensor", "practice_remaining") == "201"
    assert coordinator.games.training.snapshot()["points"] == 100


@pytest.mark.parametrize(
    ("data", "key"),
    [
        ({"score": 179}, "visit_impossible"),
        ({"score": 60, "darts": 1, "darts_at_double": 2}, "visit_at_double"),
    ],
)
async def test_a_wrong_visit_score_is_explained(hass, data, key):
    await setup_manual(hass)
    await act(hass, "start_game", game="501", players=["Alex"])
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "enter_visit", **data)
    assert error.value.translation_key == key
    assert value(hass, "sensor", "practice_remaining") == "501"


async def test_a_visit_score_waits_for_the_bot_and_the_game(hass):
    await setup_manual(hass)
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "enter_visit", score=60)
    assert error.value.translation_key == "visit_not_x01"
    await act(hass, "start_game", game="cricket", players=["Alex"])
    with pytest.raises(ServiceValidationError):
        await act(hass, "enter_visit", score=60)
    await act(hass, "start_game", game="301", players=["Alex"], bot_level=60)
    await act(hass, "enter_visit", score=60)
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "enter_visit", score=60)
    assert error.value.translation_key == "bot_turn"


async def test_a_board_with_homedarts_takes_a_visit_score_without_darts_on_it(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await act(hass, "start_game", game="301", players=["Alex"])
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "enter_visit", score=60)
    assert error.value.translation_key == "manual_entry_off"
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id(hass, "switch", "practice_manual_entry")},
        blocking=True,
    )
    coordinator.async_receive("state", board(("T20", 20, 3)))
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as error:
        await act(hass, "enter_visit", score=60)
    assert error.value.translation_key == "visit_on_board"
    coordinator.async_receive("state", board())
    await hass.async_block_till_done()
    # Pulled, the board's darts make a visit of their own; the score is the next.
    await act(hass, "enter_visit", score=60)
    assert state(hass, "sensor", "practice_remaining") == "181"
