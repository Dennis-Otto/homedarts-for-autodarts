"""game_started and game_ended: a game on the board starts once and ends once,
whichever way it is set up and however it ends, also across a restart."""

import json
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.homedarts.errors import ActionRefused
from custom_components.homedarts.games import BoardGames
from custom_components.homedarts.lifecycle import GameLifecycle
from custom_components.homedarts.moments import parse_moment, stamp

from .local_helpers import (
    BULL,
    MISS,
    S20,
    T20,
    board,
    entity_id,
    record,
    setup_local,
)
from .test_games import NOW, Reports, play, takeout, visit

S1 = ("S1", 1, 1)
D20 = ("D20", 20, 2)
CHECKOUT_101 = (T20, S1, D20)
LIFECYCLE = ("game_started", "game_ended")


def new_games() -> BoardGames:
    """The games of a board as it stands between visits, with a session."""
    games = BoardGames(Reports(), NOW, random.Random(1))
    play(games, board())
    return games


def lifecycle(events) -> list[tuple[str, dict]]:
    """The game events among announcements or events, without their source."""
    return [(event[0], event[1]) for event in events if event[0] in LIFECYCLE]


def changed(games: BoardGames, action=None, events=()) -> list[tuple[str, dict]]:
    """A change made in Home Assistant, as the coordinator plays it: the game
    events it brings."""
    if action is not None:
        action()
    return lifecycle(games.changed(list(events), NOW))


def started(games: BoardGames, game, **setup) -> dict:
    """Set a game up with homedarts.start_game; what game_started told of it."""
    events = changed(games, lambda: games.start_game(game, **setup))
    assert [kind for kind, _ in events][-1:] == ["game_started"]
    return events[-1][1]


def ended(reason: str, game=101, names=("Alex", "Kim"), **result) -> dict:
    """What game_ended tells of a match of Alex and Kim."""
    return {
        "game": game,
        "mode": "match",
        "players": len(names),
        "names": list(names),
        "bot_player": None,
        "reason": reason,
        "winner": None,
        "player": None,
        "started": stamp(NOW),
        **result,
    }


def test_a_game_set_up_in_one_step_starts_once():
    games = new_games()
    details = started(
        games,
        501,
        names=["Alex", "Kim"],
        legs=3,
        sets=2,
        double_out=True,
        bull_off=False,
        start_scores=[301],
    )
    assert details == {
        "game": 501,
        "mode": "match",
        "players": 2,
        "names": ["Alex", "Kim"],
        "start_scores": [301, 501],
        "legs": 3,
        "sets": 2,
        "bot_player": None,
        "bot_level": None,
        "resumed": False,
    }
    # Further steps and the darts of the game start nothing.
    assert changed(games) == []
    assert lifecycle(visit(games, T20, T20, T20)) == []
    assert lifecycle(play(games, board(S20))[0]) == []


def test_every_kind_of_game_tells_its_mode():
    games = new_games()
    alone = started(games, 501, names=["Alex"])
    assert (alone["mode"], alone["players"], alone["start_scores"]) == (
        "practice",
        1,
        [501],
    )
    bot = started(games, 301, names=["Alex"], bot_level=60)
    assert (bot["mode"], bot["names"], bot["bot_player"], bot["bot_level"]) == (
        "match",
        ["Alex", None],
        2,
        60,
    )
    party = started(games, "shanghai", names=["Alex", "Kim", "Sam"], bot_level=0)
    assert (party["mode"], party["game"], party["players"]) == ("party", "shanghai", 3)
    assert party["start_scores"] is None
    training = started(games, "around_the_clock", names=["Alex", "Kim"])
    assert training == {
        "game": "around_the_clock",
        "mode": "training",
        "players": 1,
        "names": ["Alex"],
        "start_scores": None,
        "legs": None,
        "sets": None,
        "bot_player": None,
        "bot_level": None,
        "resumed": False,
    }


def test_a_won_match_ends_once_the_darts_of_its_winning_visit_are_pulled():
    games = new_games()
    started(games, 101, names=["Alex", "Kim"], legs=1, sets=1, bull_off=False)
    darts = [board(*CHECKOUT_101[:count]) for count in (1, 2, 3)]
    announced, data = play(games, *darts)
    # The dart wins the match, but a correction could still take it back.
    assert "match_won" in [kind for kind, _, _ in announced]
    assert lifecycle(announced) == []
    announced, _ = play(games, takeout(), board(), data=data)
    assert lifecycle(announced) == [
        ("game_ended", ended("won", winner="Alex", player=1))
    ]
    kinds = [kind for kind, _, _ in announced]
    assert kinds.index("visit_completed") < kinds.index("game_ended")
    # The result stays; the first dart after it starts the next match.
    assert changed(games) == []
    announced, _ = play(games, board(S20))
    assert [(kind, details["resumed"]) for kind, details in lifecycle(announced)] == [
        ("game_started", False)
    ]


def test_the_winner_of_a_team_match_is_the_team():
    games = new_games()
    started(
        games,
        101,
        names=["Alex", "Kim", "Sam", "Lea"],
        legs=1,
        sets=1,
        teams=True,
        bull_off=False,
    )
    events = lifecycle(visit(games, *CHECKOUT_101))
    assert [(details["winner"], details["player"]) for _, details in events] == [
        ("Alex & Sam", 1)
    ]


def test_the_bot_wins_without_a_name():
    games = new_games()
    started(games, 101, names=["Alex"], legs=1, sets=1, bull_off=False, bot_level=60)
    practice = games.practice
    assert practice.victor() == {"winner": None, "player": None}
    practice.winner = 1
    assert practice.victor() == {"winner": None, "player": 2}


def test_a_game_ends_when_it_is_stopped_or_replaced():
    games = new_games()
    started(games, 101, names=["Alex", "Kim"])
    # A leg started anew stays in the same match.
    assert changed(games, games.practice.new_leg) == []
    # A setting that starts the match anew replaces the game.
    events = changed(games, lambda: games.practice.set_format(legs=2))
    assert [kind for kind, _ in events] == ["game_ended", "game_started"]
    assert events[0][1] == ended("replaced")
    assert events[1][1]["legs"] == 2
    events = changed(games, lambda: games.start_game("cricket"))
    assert [kind for kind, _ in events] == ["game_ended", "game_started"]
    assert events[1][1]["game"] == "cricket"
    events = changed(games, lambda: games.practice.play(0))
    assert events == [("game_ended", ended("stopped", game="cricket"))]
    assert changed(games, lambda: games.practice.play(0)) == []


def test_the_idle_end_of_the_session_ends_the_game_and_a_dart_resumes_it():
    games = new_games()
    started(games, 301, names=["Alex", "Kim"])
    visit(games, T20)
    # A session that ends by hand leaves the game alone.
    by_hand = games.training.end("manual", NOW)
    assert changed(games, events=[by_hand]) == []
    session = games.training.start(NOW)
    changed(games, events=[session])
    idle = games.training.end("idle", NOW)
    assert changed(games, events=[idle]) == [("game_ended", ended("idle", game=301))]
    # Nothing goes on without a dart, and nothing ends twice.
    assert changed(games) == []
    assert lifecycle(play(games, board())[0]) == []
    events = lifecycle(play(games, board(T20))[0])
    assert [(kind, details["resumed"]) for kind, details in events] == [
        ("game_started", True)
    ]
    assert events[0][1]["names"] == ["Alex", "Kim"]
    # The game keeps the time it started.
    stopped = changed(games, lambda: games.practice.play(0))
    assert stopped == [("game_ended", ended("stopped", game=301))]


def test_an_undone_winning_visit_resumes_the_game_until_it_is_won_again():
    games = new_games()
    started(games, 101, names=["Alex", "Kim"], legs=1, sets=1, bull_off=False)
    assert [kind for kind, _ in lifecycle(visit(games, *CHECKOUT_101))] == [
        "game_ended"
    ]
    games.undo_visit(NOW)
    announced, data = play(games, board())
    events = lifecycle(announced)
    assert [(kind, details["resumed"]) for kind, details in events] == [
        ("game_started", True)
    ]
    games.next_player(NOW)
    announced, _ = play(games, board(), data=data)
    assert lifecycle(announced) == [
        ("game_ended", ended("won", winner="Alex", player=1))
    ]


def test_a_match_of_a_tournament_is_a_game_of_its_own():
    games = new_games()
    events = games.changed(
        games.start_tournament(
            NOW,
            players=["Alex", "Kim", "Sam"],
            game="101",
            legs=1,
            sets=1,
            pause=0,
            rules={"bull_off": False},
        ),
        NOW,
    )
    first = lifecycle(events)
    assert [(kind, details["mode"]) for kind, details in first] == [
        ("game_started", "tournament")
    ]
    names = first[0][1]["names"]
    announced = visit(games, *CHECKOUT_101)
    if games.tournament.waiting:
        announced += [
            (kind, details, "training")
            for kind, details in changed(
                games, lambda: games.next_tournament_match(NOW)
            )
        ]
    events = lifecycle(announced)
    assert [(kind, details["mode"]) for kind, details in events] == [
        ("game_ended", "tournament"),
        ("game_started", "tournament"),
    ]
    assert (events[0][1]["reason"], events[0][1]["winner"]) == ("won", names[0])
    assert events[1][1]["names"] != names


def test_a_restart_announces_no_game_again():
    games = new_games()
    started(games, 301, names=["Alex", "Kim"])
    visit(games, T20)
    restored = new_games()
    restored.restore(json.loads(json.dumps(games.stored())), NOW)
    assert lifecycle(play(restored, board())[0]) == []
    assert changed(restored) == []
    # The game ends as it would have without the restart.
    events = changed(restored, lambda: restored.practice.play(0))
    assert events == [("game_ended", ended("stopped", game=301))]


def test_a_store_from_before_the_events_takes_its_game_as_started():
    games = new_games()
    started(games, 301, names=["Alex", "Kim"])
    saved = games.stored()
    del saved["lifecycle"]
    restored = new_games()
    restored.restore(saved, NOW)
    assert lifecycle(play(restored, board(T20))[0]) == []
    events = changed(restored, lambda: restored.practice.play(0))
    assert events == [("game_ended", ended("stopped", game=301))]
    # A won match of such a store ends nothing more, and the next one starts.
    won = new_games()
    started(won, 101, names=["Alex", "Kim"], legs=1, sets=1, bull_off=False)
    visit(won, *CHECKOUT_101)
    saved = won.stored()
    del saved["lifecycle"]
    restored = new_games()
    restored.restore(saved, NOW)
    assert changed(restored) == []
    events = changed(restored, restored.practice.new_match)
    assert [kind for kind, _ in events] == ["game_started"]


def test_a_broken_lifecycle_in_the_store_starts_anew():
    life = GameLifecycle()
    life.restore({"serial": -1, "ended": "lost", "game": ["501"]})
    assert (life.serial, life.ended, life.game, life.running) == (None, None, {}, False)
    life.restore({"serial": 3, "ended": "won", "game": {"game": 501, "other": 1}})
    assert life.stored() == {"serial": 3, "ended": "won", "game": {"game": 501}}


# Steps of a board: a change made in Home Assistant, or darts on the board.
STEPS = st.one_of(
    st.tuples(
        st.just("start"),
        st.sampled_from([101, 301, "cricket", "shanghai", "around_the_clock"]),
        st.integers(1, 3),
    ),
    st.tuples(
        st.sampled_from(["stop", "new_match", "new_leg", "undo", "pass", "idle"])
    ),
    st.tuples(
        st.just("visit"),
        st.lists(
            st.sampled_from([T20, S20, S1, D20, BULL, MISS]), min_size=1, max_size=3
        ),
    ),
)


def take(games: BoardGames, step: tuple) -> list[tuple[str, dict]]:
    """Take a step as Home Assistant does; the game events it brings."""
    kind = step[0]
    if kind == "visit":
        return lifecycle(visit(games, *step[1]))
    if kind == "undo":
        try:
            games.undo_visit(NOW)
        except ActionRefused:
            return []
        return lifecycle(play(games, board())[0])
    if kind == "pass":
        try:
            games.next_player(NOW)
        except ActionRefused:
            return []
        return lifecycle([*games.drain(), *play(games, board())[0]])
    if kind == "idle":
        session = games.training.start(NOW)
        changed(games, events=[session] if session else [])
        return changed(games, events=[games.training.end("idle", NOW)])
    actions = {
        "start": lambda: games.start_game(
            step[1], names=["Alex", "Kim", "Sam"][: step[2]], legs=1, sets=1
        ),
        "stop": lambda: games.practice.play(0),
        "new_match": games.practice.new_match,
        "new_leg": games.practice.new_leg,
    }
    return changed(games, actions[kind])


@settings(max_examples=150, deadline=None)
@given(st.lists(STEPS, max_size=25))
def test_every_game_started_has_exactly_one_game_ended(steps):
    games = new_games()
    running: dict | None = None
    last_end: dict | None = None
    for step in steps:
        for kind, details in take(games, step):
            if kind == "game_started":
                assert running is None, step
                if details["resumed"]:
                    # Only a game that was won or idle goes on, and it is the same.
                    assert last_end is not None
                    assert last_end["reason"] in ("won", "idle")
                    assert details["names"] == last_end["names"]
                running, last_end = details, None
            else:
                assert running is not None, step
                assert details["names"] == running["names"]
                assert details["reason"] in ("won", "stopped", "replaced", "idle")
                assert (details["winner"] is None) or details["reason"] == "won"
                running, last_end = None, details
        # A game set up and not finished is running, unless the idle end ended it.
        practice = games.practice
        set_up = practice.kind is not None or practice.drill is not None
        playing = set_up and practice.winner is None and games.life.ended != "idle"
        assert (running is not None) == playing == games.life.running, step


async def test_the_events_reach_the_board_events_entity(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    events = record(hass, coordinator)
    await hass.services.async_call(
        "homedarts",
        "start_game",
        {"game": "301", "players": ["Alex", "Kim"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    entity = hass.states.get(entity_id(hass, "event", "board_events"))
    assert entity.attributes["event_type"] == "game_started"
    assert entity.attributes["mode"] == "match"
    assert entity.attributes["names"] == ["Alex", "Kim"]
    assert entity.attributes["source"] == "training"
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id(hass, "select", "practice_game"), "option": "off"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert [(kind, details.get("reason")) for kind, details in lifecycle(events)] == [
        ("game_started", None),
        ("game_ended", "stopped"),
    ]
    stopped = lifecycle(events)[1][1]
    assert (stopped["names"], stopped["source"]) == (["Alex", "Kim"], "training")
    assert parse_moment(stopped["started"]) is not None


async def test_a_restart_of_home_assistant_announces_no_game_again(
    hass, aioclient_mock
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await coordinator.async_start_game(301, names=["Alex", "Kim"])
    coordinator.async_receive("state", board(T20))
    await hass.async_block_till_done()
    events = record(hass, coordinator)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.local
    coordinator.async_receive("state", board(T20, S20))
    await hass.async_block_till_done()
    assert lifecycle(events) == []
    await coordinator.async_play(0)
    await hass.async_block_till_done()
    assert [(kind, details["reason"]) for kind, details in lifecycle(events)] == [
        ("game_ended", "stopped")
    ]
