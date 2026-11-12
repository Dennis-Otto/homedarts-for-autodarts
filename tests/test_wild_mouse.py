"""Wild Mouse: Cricket with doubles, triples and three in a bed to close."""

from hypothesis import given
from hypothesis import strategies as st

from custom_components.homedarts.bot import (
    Aim,
    _dart,
    _wild_mouse_bed,
    aim,
    aim_dart,
    wild_mouse_aim,
    wild_mouse_dart,
)
from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.cricket import (
    BED,
    CRICKET_NUMBERS,
    DOUBLES,
    TRIPLES,
    WILD_MOUSE_TARGETS,
    play_wild_mouse_visit,
    same_bed,
    wild_mouse_bed,
    wild_mouse_order,
    wild_mouse_target,
)
from custom_components.homedarts.practice import PracticeGame

from .local_helpers import NOW, board, dart, setup_local, state, throw

# Slots: 20 to 15 and the bull, then doubles, triples and three in a bed.
OPEN = [0] * 10
CLOSED = [3] * 10
D, T, B, BULL = 7, 8, 9, 6
NUMBERS = CRICKET_NUMBERS


def darts(*names: str) -> list[dict]:
    return [dart(name) for name in names]


def marks(*closed: int, **partial: int) -> list[int]:
    """Marks with these slots closed and, by name such as s20=2, some marks."""
    result = [3 if slot in closed else 0 for slot in range(10)]
    for name, count in partial.items():
        result[
            {"d": D, "t": T, "b": B, "bull": BULL}.get(name) or 20 - int(name[1:])
        ] = count
    return result


def visit(*names, own=OPEN, points=0, others=None, points_of=None, targets=None):
    others = others if others is not None else [OPEN]
    points_of = points_of if points_of is not None else [0] * len(others)
    return play_wild_mouse_visit(
        own,
        points,
        darts(*names),
        others,
        points_of,
        NUMBERS,
        WILD_MOUSE_TARGETS if targets is None else targets,
    )


def test_a_double_or_triple_marks_its_open_number_before_doubles_or_triples():
    result = visit("T20")
    assert result.marks[0] == 3 and result.marks[T] == 0 and result.counted == 3
    assert result.targets == ("20",) and not result.bed
    # With the 20 closed, the same triple marks triples, and a double on a
    # number no Cricket game knows marks doubles; a single there counts nothing.
    result = visit("T20", "D5", "S5", own=marks(0))
    assert (result.marks[T], result.marks[D]) == (1, 1)
    assert result.targets == ("triples", "doubles", None) and result.counted == 2


def test_closed_targets_score_while_another_player_has_them_open():
    # The 20 closed by the thrower and open for the other: a triple scores 60.
    result = visit("T20", own=marks(0, T))
    assert result.points == 60 and result.counted == 3 and result.targets == ("20",)
    # The 20 closed by both: triples score the dart's whole score instead.
    result = visit("T20", own=marks(0, T), others=[marks(0)])
    assert result.points == 60 and result.counted == 1
    assert result.targets == ("triples",)
    # Doubles on a number closed by everybody score the double's score.
    result = visit("D16", own=marks(4, D), others=[marks(4)])
    assert result.points == 32 and result.targets == ("doubles",)
    # Closed by everybody: nothing counts.
    result = visit("T20", "D16", own=marks(0, 4, D, T), others=[marks(0, 4, D, T)])
    assert result.points == 0 and result.counted == 0
    assert result.targets == (None, None)


def test_marks_beyond_closing_score_like_cricket():
    result = visit("T20", own=marks(s20=2))
    assert result.marks[0] == 3 and result.points == 40 and result.counted == 3
    # Nobody else needs the 20: only the closing mark counts.
    result = visit("T20", own=marks(s20=2), others=[marks(0)])
    assert result.points == 0 and result.counted == 1


def test_the_bulls_centre_is_a_double():
    result = visit("BULL")
    assert result.marks[BULL] == 2 and result.marks[D] == 0
    result = visit("BULL", own=marks(BULL))
    assert result.marks[D] == 1 and result.targets == ("doubles",)
    # Bull and doubles closed: the bull scores its 50 on the bull.
    result = visit("BULL", own=marks(BULL, D))
    assert result.points == 50 and result.targets == ("25",)
    assert visit("25", own=marks(BULL), others=[marks(BULL)]).targets == (None,)


def test_three_in_a_bed_closes_at_once_and_then_scores_the_visit():
    result = visit("S18", "S18", "S18")
    assert result.marks[2] == 3 and result.marks[B] == 3 and result.bed
    assert result.counted == 4
    # Closed, three triples in a bed score 180 while another player needs it,
    # even when the triples themselves count for nothing any more.
    full = marks(0, D, T, B)
    result = visit("T20", "T20", "T20", own=full, others=[marks(0, D, T)])
    assert result.points == 180 and result.bed and result.counted == 1
    result = visit("T20", "T20", "T20", own=full, others=[full])
    assert result.points == 0 and not result.bed and result.counted == 0
    # Misses make no bed, nor do two darts, nor does Wild Mouse without beds.
    assert not visit("MISS", "MISS", "MISS").bed
    assert not visit("S18", "S18").bed
    nine = visit(
        "S18", "S18", "S18", own=[0] * 9, others=[[0] * 9], targets=(DOUBLES, TRIPLES)
    )
    assert not nine.bed and len(nine.marks) == 9
    assert not same_bed(darts("S18", "D18", "S18"))


def test_closing_everything_wins_without_fewer_points():
    almost = marks(*range(10), bull=2)
    assert not visit("25", own=almost, points_of=[10]).won
    result = visit("25", "T20", own=almost, points=10, points_of=[10])
    assert result.won and result.darts == 1
    # Alone, closing everything wins; the bed can be the last target.
    result = play_wild_mouse_visit(
        marks(*range(9)), 0, darts("S5", "S5", "S5"), [], [], NUMBERS
    )
    assert result.won and result.darts == 3 and result.bed


@given(
    st.lists(
        st.sampled_from(["T20", "D19", "S15", "BULL", "25", "D5", "T7", "MISS"]),
        max_size=3,
    )
)
def test_every_dart_counts_for_one_target_at_most(names):
    result = visit(*names)
    assert len(result.targets) == len(names)
    assert sum(result.marks) <= sum(3 if name[0] == "T" else 2 for name in names) + 3
    assert not result.won and result.counted <= sum(result.marks) + result.points


def test_targets_are_closed_in_order_with_the_bull_last():
    assert wild_mouse_order(NUMBERS, WILD_MOUSE_TARGETS) == [
        0,
        1,
        2,
        3,
        4,
        5,
        7,
        8,
        9,
        6,
    ]
    assert wild_mouse_order((20, 19), (DOUBLES,)) == [0, 1, 2]


def test_the_bed_to_aim_at_for_every_target():
    def bed(slot, *names):
        return wild_mouse_bed(slot, NUMBERS, WILD_MOUSE_TARGETS, darts(*names))

    assert (bed(0), bed(BULL), bed(D), bed(T)) == ("T20", "BULL", "D", "T")
    # Three in a bed: the big single 20 first, then the bed of the visit.
    assert (bed(B), bed(B, "S5"), bed(B, "25"), bed(B, "BULL", "BULL")) == (
        "S20",
        "S5",
        "25",
        "BULL",
    )
    assert bed(B, "T19") == "T19"
    # Once the darts differ, miss or are all thrown, no bed is left to make.
    assert bed(B, "S5", "S6") is None and bed(B, "MISS") is None
    assert bed(B, "S5", "S5", "S5") is None


def test_the_next_target_closes_in_order_and_then_scores():
    def target(own, others=(), visit=()):
        return wild_mouse_target(
            own, NUMBERS, WILD_MOUSE_TARGETS, list(others), darts(*visit)
        )

    assert target(OPEN) == ("20", "T20")
    assert target(marks(*range(6))) == ("doubles", "D")
    assert target(marks(*range(6), D, T)) == ("bed", "S20")
    # A bed the visit can no longer make: the bull, and with it closed a target
    # that scores, or nothing.
    assert target(marks(*range(6), D, T), visit=("S1", "S2")) == ("25", "BULL")
    almost = marks(*range(9))
    assert target(almost, [OPEN], ("S1", "S2")) == ("20", "T20")
    assert target(almost, [], ("S1", "S2")) is None
    assert target(CLOSED, [CLOSED]) is None


def game(players: int = 2, bot: int = 0) -> PracticeGame:
    practice = PracticeGame()
    practice.bot_level = bot
    practice.set_players(players)
    practice.play("wild_mouse")
    return practice


def test_a_wild_mouse_match_shows_its_targets_and_where_darts_counted():
    practice = game()
    snapshot = practice.snapshot()
    assert snapshot["game"] == "wild_mouse" and snapshot["numbers"] == list(NUMBERS)
    assert snapshot["targets"] == list(WILD_MOUSE_TARGETS)
    assert len(snapshot["scores"][0]["marks"]) == 10
    assert (snapshot["target"], snapshot["target_row"]) == ("T20", "20")
    practice.track(darts("T20", "T20", "T20"), now=NOW)
    snapshot = practice.snapshot()
    assert snapshot["counted"] == ["20", "triples", "triples"] and snapshot["bed"]
    assert snapshot["scores"][0]["marks"][T] == 2
    assert snapshot["scores"][0]["marks"][B] == 3
    assert (snapshot["target"], snapshot["target_row"]) == ("T19", "19")
    practice.finish_visit(now=NOW)
    practice.track([], now=NOW)
    assert practice.players[0].marks[B] == 3 and practice.current == 1
    # The other player closes everything but the bull and wins with it.
    practice.players[1].marks = marks(*range(10), bull=2)
    events = throw(practice, "25")
    assert events[0][0] == "leg_won" and events[0][1]["game"] == "wild_mouse"
    assert practice.legs[0]["game"] == "wild_mouse"
    snapshot = practice.snapshot()
    assert snapshot["target_row"] is None and snapshot["target"] is None


def test_three_in_a_bed_can_be_left_out_and_restarts_wild_mouse():
    practice = game()
    throw(practice, "T20")
    practice.set_option("three_in_a_bed", True)
    assert practice.players[0].darts == 1
    practice.set_option("three_in_a_bed", False)
    assert practice.players[0].darts == 0
    snapshot = practice.snapshot()
    assert snapshot["targets"] == [DOUBLES, TRIPLES]
    assert len(snapshot["scores"][0]["marks"]) == 9
    restored = PracticeGame()
    restored.restore(practice.stored())
    assert restored.three_in_a_bed is False and len(restored.players[0].marks) == 9
    # In other games, the rule waits for Wild Mouse.
    practice.play("cricket")
    throw(practice, "T20")
    practice.set_option("three_in_a_bed", True)
    assert practice.players[0].darts == 1 and len(practice.players[0].marks) == 7
    assert "targets" not in practice.snapshot()


def test_the_bot_plays_wild_mouse_by_its_targets():
    practice = game(1, bot=60)
    assert practice.bot_seat == 1
    practice.current = 1
    assert aim(practice.snapshot()) == "T20"
    practice.players[1].marks = marks(*range(6))
    practice.track(darts("S5"), now=NOW)
    # The doubles go to a number the bot closed, here the 20.
    assert aim(practice.snapshot()) == "D20"
    assert aim_dart(practice.snapshot()) == Aim("D20", three_in_a_bed=False)
    # Three in a bed, at the bed of the visit's first dart: the bot throws
    # with its own scatter there.
    practice.players[1].marks = marks(*range(6), D, T)
    assert aim_dart(practice.snapshot()) == Aim("S5", three_in_a_bed=True)


def test_the_bot_knows_when_it_aims_at_three_in_a_bed():
    def bot(own, visit=(), targets=WILD_MOUSE_TARGETS):
        return wild_mouse_dart(
            own, 0, [OPEN[: len(own)]], [0], NUMBERS, targets, darts(*visit)
        )

    assert bot(marks(*range(6), D, T)) == Aim("S20", True)
    assert bot(marks(*range(6), D, T), visit=("S5", "S5")) == Aim("S5", True)
    # A bed the visit can no longer make: the bull, no bed.
    assert bot(marks(*range(6), D, T), visit=("S1", "S2")) == Aim("BULL", False)
    # Without three in a bed, no dart is one.
    assert bot(marks(*range(6))[:9], targets=(DOUBLES, TRIPLES)) == Aim("D20", False)
    assert bot(CLOSED) == Aim("T20", False)


def test_the_bot_closes_threats_first_and_scores_while_behind():
    def bot(own, others, points=0, points_of=(0,), visit=()):
        return wild_mouse_aim(
            own,
            points,
            others,
            list(points_of),
            NUMBERS,
            WILD_MOUSE_TARGETS,
            darts(*visit),
        )

    assert bot(OPEN, [OPEN]) == "T20"
    # The other scores on the 19: the bot closes it first.
    assert bot(marks(), [marks(1)]) == "T19"
    # Behind with a target to score on, the bot scores.
    assert bot(marks(0), [marks(1)], points_of=[50]) == "T20"
    assert bot(marks(0, 1), [marks()], points_of=[50]) == "T20"
    # Everything closed: score; nothing to score on: the triple 20.
    assert bot(marks(*range(9)), [marks(*range(8))]) == "S20"
    assert bot(CLOSED, [CLOSED]) == "T20"
    # Doubles on a number the bot still needs would mark the number: the
    # highest number it closed, or one no Cricket game counts, takes them.
    assert _wild_mouse_bed(D, marks(0), NUMBERS, WILD_MOUSE_TARGETS, []) == "D20"
    assert _wild_mouse_bed(T, OPEN, NUMBERS, WILD_MOUSE_TARGETS, []) == "T14"
    # A bed the visit can no longer make: the next target.
    assert bot(marks(*range(6), D, T), [OPEN], visit=("S1", "S2")) == "BULL"


def test_the_bot_reads_the_darts_of_the_visit():
    assert _dart("T20") == {"number": 20, "multiplier": 3}
    assert _dart("25") == {"number": 25, "multiplier": 1}
    assert _dart("BULL") == {"number": 25, "multiplier": 2}
    assert _dart("MISS") == {"number": 0, "multiplier": 0}
    assert BED in WILD_MOUSE_TARGETS


async def test_start_game_plays_wild_mouse_with_or_without_beds(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await hass.services.async_call(
        DOMAIN,
        "start_game",
        {"game": "Wild Mouse", "players": ["Alex", "Sam"], "three_in_a_bed": False},
        blocking=True,
    )
    await hass.async_block_till_done()
    practice = entry.runtime_data.local.games.practice
    assert practice.cricket == "wild_mouse" and practice.three_in_a_bed is False
    assert len(practice.players[0].marks) == 9
    assert state(hass, "select", "practice_game") == "wild_mouse"
    assert state(hass, "switch", "practice_three_in_a_bed") == "off"
    assert state(hass, "sensor", "practice_target") == "T20"
