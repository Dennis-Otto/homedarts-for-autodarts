"""The games of the practice game as modes of its match frame: every game has
its mode, a store loads unchanged byte for byte, and a setting starts only the
game that is made with it anew."""

import json
import random
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.homedarts.cricket import CRICKET_GAMES, CRICKET_NUMBERS
from custom_components.homedarts.drills import DRILLS
from custom_components.homedarts.modes import (
    GAME_SETTINGS,
    CricketMode,
    DrillMode,
    GameMode,
    PartyMode,
    VisitRefused,
    X01Mode,
)
from custom_components.homedarts.party import PARTY_GAMES, make_party
from custom_components.homedarts.practice import GAMES, PracticeGame

from .local_helpers import NOW, dart, throw

KINDS = [*GAMES, *CRICKET_GAMES, *PARTY_GAMES, *DRILLS]
BEDS = ["T20", "T19", "S20", "S5", "D20", "D16", "D1", "BULL", "25", "MISS"]


def mode_of(kind: int | str) -> type[GameMode]:
    if kind in GAMES:
        return X01Mode
    if kind in CRICKET_GAMES:
        return CricketMode
    return PartyMode if kind in PARTY_GAMES else DrillMode


@pytest.mark.parametrize("kind", KINDS)
def test_every_game_plays_in_its_mode(kind):
    practice = PracticeGame()
    practice.play(kind, 2)
    mode = practice.mode
    assert type(mode) is mode_of(kind)
    assert mode.match is practice
    # What the entities read of the game comes from its mode.
    assert practice.game == (kind if kind in GAMES else 0)
    assert practice.cricket == (kind if kind in CRICKET_GAMES else None)
    assert (practice.party.kind if practice.party else None) == (
        kind if kind in PARTY_GAMES else None
    )
    assert practice.drill == (kind if kind in DRILLS else None)
    assert practice.kind == (None if kind in DRILLS else kind)
    assert practice.seats == (8 if kind in PARTY_GAMES else 4)


@pytest.mark.parametrize("kind", [0, 42, "501", "darts", None, True, [501]])
def test_anything_else_plays_no_game(kind):
    practice = PracticeGame()
    practice.play(kind)
    assert type(practice.mode) is GameMode
    assert practice.kind is None and practice.seats == 8
    assert practice.snapshot()["game"] is None


def test_no_game_counts_nothing():
    """The defaults of GameMode are what a game does that leaves a part out."""
    practice = PracticeGame()
    mode, player = practice.mode, practice.players[0]
    assert mode.track() == [] and mode.book(NOW) == [] and not mode.passes()
    assert mode.start(0) == 0 and mode.slots() == len(CRICKET_NUMBERS)
    assert mode.settings == () and not mode.uses_out_mode
    assert mode.turn_details() == {"remaining": None, "checkout": None, "setup": None}
    assert mode.book_leg(None) == {"darts": 0}
    assert mode.leg_entry(0, player, None) == {}
    assert mode.match_entry(0, player) == {}
    assert mode.summary_entry(0, player, practice.tallies[0]) == {}
    assert mode.stored() == {"drawn": None, "party": None}
    assert mode.checkpoint() == {}
    with pytest.raises(VisitRefused) as refused:
        mode.score_visit(60, None, None, False)
    assert refused.value.key == "visit_not_x01"


def text(practice: PracticeGame) -> str:
    """The store of the game as Home Assistant writes it."""
    return json.dumps(practice.stored())


@settings(max_examples=150, deadline=None)
@given(
    kind=st.sampled_from(KINDS),
    players=st.integers(1, 4),
    teams=st.booleans(),
    bot=st.sampled_from([0, 0, 60]),
    visits=st.lists(st.lists(st.sampled_from(BEDS), max_size=3), max_size=25),
    seed=st.integers(0, 2**16),
)
def test_a_stored_game_loads_unchanged_byte_for_byte(
    kind, players, teams, bot, visits, seed
):
    practice = PracticeGame()
    practice.rng = random.Random(seed)
    practice.teams, practice.bull_off = teams, seed % 3 == 0
    practice.set_bot(bot)
    practice.set_players(players)
    practice.set_format(2, 1)
    practice.play(kind)
    for visit in visits:
        if visit:
            throw(practice, *visit)
        else:
            practice.finish_visit(empty=True, now=NOW)
    saved = text(practice)
    restored = PracticeGame()
    restored.restore(json.loads(saved))
    assert text(restored) == saved
    assert type(restored.mode) is type(practice.mode)
    assert restored.snapshot() == practice.snapshot()


# Stores that the practice game wrote before its games became modes (main at
# ee15b7e), one of every game with three players after twenty visits, and a few
# more: X01 with double in and a round limit, X01 in teams, Killer while the
# numbers are chosen and after.
STORES_BEFORE_MODES = json.loads(
    (Path(__file__).parent / "fixtures" / "stores_before_modes.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("name", sorted(STORES_BEFORE_MODES))
def test_a_store_from_before_the_modes_loads_unchanged_byte_for_byte(name):
    saved = STORES_BEFORE_MODES[name]
    restored = PracticeGame()
    restored.restore(json.loads(saved))
    # The number of the match came after the modes, and starts at 0.
    stored = json.loads(text(restored))
    assert stored.pop("serial") == 0
    assert json.dumps(stored) == saved


def test_an_undone_visit_comes_back_to_the_game_of_its_checkpoint():
    practice = PracticeGame()
    practice.play("cricket", 2)
    checkpoint = practice.checkpoint()
    practice.play(501)
    practice.rewind(checkpoint, [dart("T20")], [], now=NOW)
    assert type(practice.mode) is CricketMode
    assert practice.snapshot()["visit"] == ["T20"]


def test_a_store_without_a_known_game_keeps_the_x01_game():
    practice = PracticeGame()
    practice.play(301, 2)
    practice.restore({"game": "darts", "players": [{}, {}]})
    assert type(practice.mode) is X01Mode and practice.game == 301
    practice.play("killer", 2)
    practice.restore({"game": "darts", "players": [{}, {}]})
    assert type(practice.mode) is GameMode


# How each setting of a game changes, and the game made with it.
CHANGES = {
    "three_in_a_bed": lambda game: game.set_option("three_in_a_bed", False),
    "golf_holes": lambda game: game.set_rounds(golf_holes=18),
    "count_up_rounds": lambda game: game.set_rounds(count_up_rounds=3),
    "bermuda_halve_on_miss": lambda game: game.set_option(
        "bermuda_halve_on_miss", False
    ),
    "round_the_world_order": lambda game: game.set_party_rule(
        "round_the_world_order", "descending"
    ),
    "gotcha_target": lambda game: game.set_party_rule("gotcha_target", 101),
}


@pytest.mark.parametrize(
    ("kind", "setting"),
    [(kind, setting) for kind, names in GAME_SETTINGS.items() for setting in names],
)
def test_a_setting_starts_only_the_game_made_with_it_anew(kind, setting):
    for played, restarts in ((kind, True), ("cricket", False), (501, False)):
        practice = PracticeGame()
        practice.play(played, 2)
        throw(practice, "S20", "S20", "S20")
        assert not practice.fresh
        CHANGES[setting](practice)
        assert practice.fresh is restarts
        assert practice.mode.kind == played


def test_a_party_game_announces_points_and_killer_its_lives():
    shanghai, killer = make_party("shanghai", 2), make_party("killer", 2)
    assert shanghai.min_players == 1 and killer.min_players == 2
    assert not shanghai.choosing and killer.choosing
    assert shanghai.announced(1) == {"points": 0}
    assert killer.announced(1) == {"lives": 3, "killer": False}
    result = killer.visit(0, [dart("S7")])
    result.lives[0], result.killers[0] = 2, True
    assert killer.announced(0, result) == {"lives": 2, "killer": True}
    result = shanghai.visit(0, [dart("S1")])
    assert shanghai.announced(0, result) == {"points": 1}
