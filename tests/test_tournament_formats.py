"""Tournaments of up to 32 players: knockouts of 32, double elimination and groups
with a knockout, and the properties every draw keeps."""

import json
from collections import Counter
from itertools import combinations, permutations
from types import SimpleNamespace

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from custom_components.homedarts.brackets import (
    GRAND_FINAL,
    GRAND_FINAL_RESET,
    GROUP_ORDERS,
    LOSERS_FINAL,
    WINNERS_FINAL,
    bracket_size,
    double_knockout,
    group_seeds,
    group_stage,
    knockout,
    places,
    snake,
)
from custom_components.homedarts.errors import ActionRefused
from custom_components.homedarts.practice import PracticeGame
from custom_components.homedarts.tournament import (
    DOUBLE_KNOCKOUT,
    ENTRANTS,
    FINISHED,
    GROUPS_KNOCKOUT,
    KNOCKOUT,
    MAX_ADVANCE,
    MAX_ENTRANTS,
    MAX_GROUPS,
    MIN_GROUPS,
    PLAYING,
    WAITING,
    Tournament,
    TournamentDirector,
    auto_groups,
    fits_groups,
)

from .test_tournament import NOW, PLAYERS, director, play_out, stored, win

ENDED = NOW.isoformat()
# The first rounds of a double elimination, where byes can fall.
BYE_STAGES = {"winners_round_1", "losers_round_1", "losers_round_2"}


def result(side: int) -> SimpleNamespace:
    """A practice match that the player on this side won 1:0 with a 101 in three darts."""
    return SimpleNamespace(
        winner=side,
        players=[
            SimpleNamespace(
                match_legs=int(seat == side),
                sets=0,
                match_points=101 if seat == side else 60,
                match_marks=0,
                match_darts=3,
            )
            for seat in (0, 1)
        ],
    )


def drawn(fmt: str, count: int, **options) -> Tournament:
    return Tournament(
        format=fmt,
        game="101",
        players=PLAYERS[:count],
        legs=1,
        sets=1,
        rules={},
        **options,
    )


def decide(tournament: Tournament, sides) -> int:
    """Play every match, the winner on the side that sides gives for it; the number
    of matches played."""
    played = 0
    while (index := tournament.upcoming()) is not None:
        tournament.record(index, result(sides(tournament.matches[index])), ENDED)
        played += 1
    return played


def losses(tournament: Tournament) -> Counter:
    return Counter(
        match.loser
        for match in tournament.matches
        if match.played and match.stage != "third_place"
    )


# -- the draws -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "stages", "byes"),
    [
        (16, ["round_of_16"] * 8 + ["quarter_final"] * 4, 0),
        (17, ["round_of_32"] * 16 + ["round_of_16"] * 8, 15),
        (32, ["round_of_32"] * 16 + ["round_of_16"] * 8, 0),
    ],
)
def test_a_knockout_of_up_to_32_players(count, stages, byes):
    matches = knockout(count, third_place=False)
    assert [match.stage for match in matches][: len(stages)] == stages
    assert sum(match.bye for match in matches) == byes
    # Seed 1 meets the last seed, and the byes go to the top seeds.
    assert matches[0].players == [0, None if byes else count - 1]
    assert all(match.players[0] < byes for match in matches if match.bye)


def test_the_places_of_a_bracket_keep_the_top_seeds_apart():
    seats = places(32)
    assert sorted(seats) == list(range(32))
    # The first round pairs seeds that add up to the last one.
    assert all(
        top + bottom == 31 for top, bottom in zip(seats[::2], seats[1::2], strict=True)
    )
    # Seeds 1 and 2 in different halves, 1 to 4 in different quarters.
    assert {seats.index(seed) // 16 for seed in (0, 1)} == {0, 1}
    assert {seats.index(seed) // 8 for seed in range(4)} == {0, 1, 2, 3}
    assert [bracket_size(count) for count in (3, 4, 5, 8, 9, 32)] == [
        4,
        4,
        8,
        8,
        16,
        32,
    ]


def test_the_double_elimination_of_three():
    matches = double_knockout(3)
    assert [(match.stage, match.players, match.bye) for match in matches] == [
        ("winners_round_1", [0, None], True),
        ("winners_round_1", [1, 2], False),
        # The loser of 2 against 3 waits for the loser of the winners' final.
        ("losers_round_1", [None, None], True),
        (WINNERS_FINAL, [None, None], False),
        (LOSERS_FINAL, [None, None], False),
        (GRAND_FINAL, [None, None], False),
        # The second grand final waits until it is needed.
        (GRAND_FINAL_RESET, [None, None], True),
    ]
    assert matches[2].seeds == [None, None]


def test_the_losers_bracket_takes_turns_and_crosses_the_players_who_drop():
    stages = [match.stage for match in double_knockout(8)]
    assert stages == [
        *["winners_round_1"] * 4,
        *["losers_round_1"] * 2,
        *["winners_round_2"] * 2,
        *["losers_round_2"] * 2,
        "losers_round_3",
        WINNERS_FINAL,
        LOSERS_FINAL,
        GRAND_FINAL,
        GRAND_FINAL_RESET,
    ]
    tournament = drawn(DOUBLE_KNOCKOUT, 8)
    # The top seed wins every match.
    decide(tournament, lambda match: int(match.players[1] < match.players[0]))
    second = [match for match in tournament.matches if match.stage == "losers_round_2"]
    # A loser of the second round meets a player of the other half: the one who
    # dropped first plays first, and nobody meets their first opponent again.
    assert [match.slot for match in second] == [1, 0]
    assert [match.players for match in second] == [[5, 3], [4, 2]]


def test_groups_are_drawn_like_a_snake_and_play_round_by_round():
    assert snake(8, 2) == [[0, 3, 4, 7], [1, 2, 5, 6]]
    assert snake(7, 2) == [[0, 3, 4], [1, 2, 5, 6]]
    assert [len(group) for group in snake(32, 8)] == [4] * 8
    matches = group_stage(snake(7, 2))
    assert [(match.round, match.group) for match in matches] == [
        (1, 0),
        (1, 1),
        (1, 1),
        (2, 0),
        (2, 1),
        (2, 1),
        (3, 0),
        (3, 1),
        (3, 1),
    ]
    assert {frozenset(match.players) for match in matches if match.group == 0} == {
        frozenset(pair) for pair in combinations([0, 3, 4], 2)
    }


@pytest.mark.parametrize(
    ("count", "groups", "advance", "fits"),
    [
        (6, 2, 2, True),
        (6, 2, 3, False),
        (5, 2, 1, False),
        (17, 2, 2, False),
        (16, 2, 2, True),
        (32, 8, 3, True),
        (32, 8, 4, False),
        (32, 4, 4, True),
        (32, 9, 1, False),
        (12, 1, 1, False),
        (12, 3, 0, False),
        (32, 4, 5, False),
    ],
)
def test_groups_need_three_to_eight_players_and_more_than_go_on(
    count, groups, advance, fits
):
    assert fits_groups(count, groups, advance) is fits


def test_without_a_number_groups_have_about_four_players():
    assert [auto_groups(count) for count in (6, 7, 8, 12, 15, 16, 20, 31, 32)] == [
        2,
        2,
        2,
        3,
        3,
        4,
        5,
        7,
        8,
    ]
    for count in range(ENTRANTS[GROUPS_KNOCKOUT][0], MAX_ENTRANTS + 1):
        assert fits_groups(count, auto_groups(count), 2)


def searched_orders(groups: int, advance: int) -> tuple[tuple[int, ...], ...]:
    """The orders of GROUP_ORDERS worked out anew: of every order of the groups
    for a place, the one whose players meet a player of their own group the
    latest, the fewest in the first round, then in the second, and so on; of
    equal orders, the first."""
    where = {
        seed: place for place, seed in enumerate(places(bracket_size(groups * advance)))
    }
    seeds = [(group, 0) for group in range(groups)]
    orders = []
    for rank in range(1, advance):
        tier = range(rank * groups, (rank + 1) * groups)
        meets = {
            (seed, group): min(
                (where[seed] ^ where[other]).bit_length()
                for other, (mate, _) in enumerate(seeds)
                if mate == group
            )
            for seed in tier
            for group in range(groups)
        }
        best = max(
            permutations(range(groups)),
            key=lambda order: sorted(
                meets[seed, group] for seed, group in zip(tier, order, strict=True)
            ),
        )
        seeds.extend((group, rank) for group in best)
        orders.append(best)
    return tuple(orders)


def test_the_orders_of_the_groups_are_the_best_draws():
    # Every number of groups and of players going on that some field allows.
    allowed = {
        (groups, advance)
        for count in range(ENTRANTS[GROUPS_KNOCKOUT][0], MAX_ENTRANTS + 1)
        for groups in range(MIN_GROUPS, MAX_GROUPS + 1)
        for advance in range(2, MAX_ADVANCE + 1)
        if fits_groups(count, groups, advance)
    }
    assert set(GROUP_ORDERS) == allowed
    for (groups, advance), orders in GROUP_ORDERS.items():
        assert orders == searched_orders(groups, advance)


def test_the_group_winners_get_the_top_seeds_and_meet_their_group_late():
    assert group_seeds(2, 2) == ((0, 0), (1, 0), (0, 1), (1, 1))
    tournament = drawn(GROUPS_KNOCKOUT, 16, groups=4, advance=2)
    # The top seed of every group wins every match.
    decide(tournament, lambda match: int(match.players[1] < match.players[0]))
    first = [match for match in tournament.matches if match.stage == "quarter_final"]
    group = {
        player: index
        for index, members in enumerate(tournament.groups)
        for player in members
    }
    # A group winner meets a runner-up of another group, and the two of a group
    # meet in the final at the earliest.
    assert [[group[player] for player in match.players] for match in first] == [
        [0, 2],
        [3, 1],
        [1, 3],
        [2, 0],
    ]


# -- the properties of every draw ----------------------------------------------------


@given(
    count=st.integers(ENTRANTS[KNOCKOUT][0], MAX_ENTRANTS),
    third_place=st.booleans(),
    outcomes=st.lists(st.booleans(), min_size=40, max_size=40),
)
def test_every_knockout_plays_every_player_to_one_champion(
    count, third_place, outcomes
):
    tournament = drawn(KNOCKOUT, count, third_place=third_place)
    choices = iter(outcomes)
    played = decide(tournament, lambda match: int(next(choices)))
    assert played == count - 1 + int(tournament.third_place)
    # Byes fall in the first round only; every player plays and loses once at most.
    assert all(match.round == 1 for match in tournament.matches if match.bye)
    playing = {
        player
        for match in tournament.matches
        if match.played
        for player in match.players
    }
    assert playing == set(range(count))
    champion = PLAYERS.index(tournament.podium()[0])
    assert losses(tournament) == Counter(set(range(count)) - {champion})


@given(
    count=st.integers(ENTRANTS[DOUBLE_KNOCKOUT][0], MAX_ENTRANTS),
    outcomes=st.lists(st.booleans(), min_size=64, max_size=64),
)
def test_in_a_double_elimination_only_a_second_defeat_puts_a_player_out(
    count, outcomes
):
    tournament = drawn(DOUBLE_KNOCKOUT, count)
    choices = iter(outcomes)
    played = decide(tournament, lambda match: int(next(choices)))
    champion, runner_up, third = tournament.podium()
    lost = losses(tournament)
    # Everyone but the champion lost twice; the champion once at most, and a
    # second grand final only when the champion of the losers' bracket won the first.
    assert all(
        lost[player] == 2 for player in range(count) if PLAYERS[player] != champion
    )
    assert lost[PLAYERS.index(champion)] <= 1
    reset = tournament.matches[-1]
    assert played == 2 * count - 2 + int(reset.played)
    assert len({champion, runner_up, third}) == 3
    assert all(
        match.stage in BYE_STAGES for match in tournament.matches[:-1] if match.bye
    )


@given(
    data=st.data(),
    third_place=st.booleans(),
    outcomes=st.lists(st.booleans(), min_size=150, max_size=150),
)
def test_groups_send_their_best_into_the_knockout(data, third_place, outcomes):
    count = data.draw(st.integers(ENTRANTS[GROUPS_KNOCKOUT][0], MAX_ENTRANTS))
    groups = data.draw(
        st.sampled_from(
            [
                (number, advance)
                for number in range(MIN_GROUPS, MAX_GROUPS + 1)
                for advance in range(1, MAX_ADVANCE + 1)
                if fits_groups(count, number, advance)
            ]
        )
    )
    tournament = drawn(
        GROUPS_KNOCKOUT,
        count,
        groups=groups[0],
        advance=groups[1],
        third_place=third_place,
    )
    knockout_players = groups[0] * groups[1]
    choices = iter(outcomes)
    played = decide(tournament, lambda match: int(next(choices)))
    in_groups = sum(
        len(members) * (len(members) - 1) // 2 for members in tournament.groups
    )
    assert played == in_groups + knockout_players - 1 + int(tournament.third_place)
    # The knockout takes the best of every group, as their tables rank them.
    entered = {
        player
        for match in tournament.matches
        if match.group is None and match.round == 1
        for player in match.players
        if player is not None
    }
    best = {
        PLAYERS.index(row["name"])
        for table in tournament.tables()
        for row in table["standings"][: groups[1]]
    }
    assert entered == best
    # Two of one group never meet in the first round of the knockout.
    group = {
        player: index
        for index, members in enumerate(tournament.groups)
        for player in members
    }
    for match in tournament.matches:
        if match.group is None and match.round == 1 and not match.bye:
            assert group[match.players[0]] != group[match.players[1]]
    assert tournament.podium()[0] is not None


# -- 32 players through the practice game ---------------------------------------------


@pytest.mark.parametrize(
    ("fmt", "options", "matches"),
    [
        # Eight groups of four, two of each into a knockout of 16, and its third place.
        (GROUPS_KNOCKOUT, {"third_place": True}, 8 * 6 + 15 + 1),
        # Every player but the champion loses twice: 62 matches, and the second
        # grand final that the champion of the losers' bracket forces.
        (DOUBLE_KNOCKOUT, {}, 63),
    ],
)
def test_32_players_play_to_a_champion(fmt, options, matches):
    tournament, practice = director(32, fmt=fmt, **options)
    sizes = [len(group) for group in tournament.tournament.groups]
    assert sizes == ([4] * 8 if fmt == GROUPS_KNOCKOUT else [])
    # The second player of every match wins: in a double elimination, the winner
    # of the losers' bracket wins the grand final too, and a second one decides.
    events = play_out(tournament, practice, winner=lambda names: 1)
    kinds = [kind for kind, _ in events]
    assert kinds.count("tournament_match_finished") == matches
    finished = events[-1][1]
    assert kinds[-1] == "tournament_finished" and finished["winner"]
    snapshot = tournament.snapshot()
    assert snapshot["status"] == FINISHED and snapshot["winner"] == finished["winner"]
    assert snapshot["matches_played"] == snapshot["matches_total"] == matches
    assert json.loads(json.dumps(snapshot)) == snapshot


# The big tournaments of the pictures of the documentation, with the options of the
# screenshot tool (big_tournament in tests/e2e/screenshots.py), which plays them only
# up to their pictures.
DEMO_TOURNAMENTS = [
    (GROUPS_KNOCKOUT, {"groups": 8, "advance": 2}),
    (DOUBLE_KNOCKOUT, {}),
]
# As the screenshot tool plays: the first player wins, every third match the second.
DEMO_WINNERS = [int(match % 3 == 2) for match in range(64)]


@settings(max_examples=30)
@given(
    big=st.sampled_from(DEMO_TOURNAMENTS),
    winners=st.lists(st.integers(0, 1), min_size=64, max_size=64),
)
@example(big=DEMO_TOURNAMENTS[0], winners=DEMO_WINNERS)
@example(big=DEMO_TOURNAMENTS[1], winners=DEMO_WINNERS)
def test_the_big_tournaments_of_the_demo_find_their_champion_whatever_the_results(
    big, winners
):
    fmt, options = big
    tournament, practice = director(32, fmt=fmt, **options)
    sides = iter(winners)
    events = play_out(tournament, practice, winner=lambda names: next(sides))
    kinds = [kind for kind, _ in events]
    played = kinds.count("tournament_match_finished")
    drawn = tournament.tournament
    if fmt == GROUPS_KNOCKOUT:
        # Eight groups of four, then a knockout of their best two.
        assert [len(group) for group in drawn.groups] == [4] * 8
        assert played == 8 * 6 + 15 + int(drawn.third_place)
    else:
        # Everyone but the champion loses twice, and a second grand final follows
        # when the champion of the losers' bracket wins the first.
        assert played == 62 + int(drawn.matches[-1].played)
    assert kinds[-1] == "tournament_finished"
    champion = events[-1][1]["winner"]
    assert champion in PLAYERS[:32]
    snapshot = tournament.snapshot()
    assert snapshot["status"] == FINISHED and snapshot["winner"] == champion
    assert snapshot["matches_played"] == snapshot["matches_total"] == played


def test_round_counts_within_its_part_of_the_tournament():
    # A double elimination: the rounds of each bracket, the grand finals one
    # round after the winners' final, and the losers' bracket the longest part.
    double = drawn(DOUBLE_KNOCKOUT, 32)
    stages = {match.stage: match.round for match in double.matches}
    assert stages["winners_final"] == 5 and stages["losers_final"] == 8
    assert stages[GRAND_FINAL] == stages[GRAND_FINAL_RESET] == 6
    assert double.rounds == 8
    # The knockout after the groups counts its rounds from 1 again.
    groups = drawn(GROUPS_KNOCKOUT, 32, groups=8, advance=2)
    stages = {match.stage: match.round for match in groups.matches}
    assert stages["round_3"] == 3 and stages["round_of_16"] == 1
    assert stages["final"] == groups.rounds == 4


def test_a_group_tournament_names_its_groups_in_events_and_the_sensor():
    tournament, practice = director(6, fmt=GROUPS_KNOCKOUT, advance=1)
    snapshot = tournament.snapshot()
    assert [group["group"] for group in snapshot["groups"]] == ["A", "B"]
    assert snapshot["advance"] == 1
    assert [row["name"] for row in snapshot["groups"][0]["standings"]] == [
        "Alex",
        "Lea",
        "Max",
    ]
    assert snapshot["current"]["group"] == "A" and "standings" not in snapshot
    # The final waits for the winners of the groups.
    assert snapshot["bracket"] == [
        {
            "stage": "final",
            "round": 1,
            "matches": [
                {
                    "match": 7,
                    "round": 1,
                    "stage": "final",
                    "players": [None, None],
                    "winner": None,
                    "bye": False,
                    "legs": [0, 0],
                    "sets": [0, 0],
                    "ended": None,
                }
            ],
        }
    ]
    started = tournament.stored()["tournament"]
    assert (started["groups"], started["advance"]) == (2, 1)
    win(practice)
    events = tournament.booked(practice, NOW)
    assert events[0][1]["group"] == "A"
    assert tournament.state() == "round_1" and tournament.waiting


def test_the_start_names_the_groups_and_who_goes_on():
    practice = PracticeGame()
    tournament = TournamentDirector()
    events = tournament.start(
        practice, NOW, players=PLAYERS[:12], format=GROUPS_KNOCKOUT, groups=3
    )
    assert events[0][1] | {"players": []} == {
        "format": GROUPS_KNOCKOUT,
        "game": 501,
        "matches": 3 * 6 + 5,
        "players": [],
        "start_scores": [0] * 12,
        "legs_to_win": 1,
        "sets_to_win": 1,
        "seed": None,
        "groups": 3,
        "advance": 2,
    }
    # The other formats name no groups.
    tournament.stop(practice)
    events = tournament.start(practice, NOW, players=PLAYERS[:12], format=KNOCKOUT)
    assert "groups" not in events[0][1]


@pytest.mark.parametrize(
    ("fmt", "players", "options", "key", "placeholders"),
    [
        (
            KNOCKOUT,
            33,
            {},
            "tournament_players",
            {"count": "33", "min": "3", "max": "32"},
        ),
        (
            DOUBLE_KNOCKOUT,
            2,
            {},
            "tournament_players",
            {"count": "2", "min": "3", "max": "32"},
        ),
        (
            GROUPS_KNOCKOUT,
            5,
            {},
            "tournament_players",
            {"count": "5", "min": "6", "max": "32"},
        ),
        (
            GROUPS_KNOCKOUT,
            8,
            {"groups": 3},
            "tournament_groups",
            {"count": "8", "groups": "3", "advance": "2"},
        ),
        (
            GROUPS_KNOCKOUT,
            8,
            {"advance": 4},
            "tournament_groups",
            {"count": "8", "groups": "2", "advance": "4"},
        ),
    ],
)
def test_every_format_checks_its_players_and_groups(
    fmt, players, options, key, placeholders
):
    tournament = TournamentDirector()
    with pytest.raises(ActionRefused) as error:
        tournament.start(
            PracticeGame(),
            NOW,
            players=[f"P{number}" for number in range(players)],
            format=fmt,
            **options,
        )
    assert error.value.key == key
    assert error.value.placeholders == placeholders
    assert tournament.tournament is None and tournament.setup.format != fmt


# -- the sensor and the restart ------------------------------------------------------


def test_the_second_grand_final_shows_once_it_is_needed():
    tournament = drawn(DOUBLE_KNOCKOUT, 4)
    # The winner of the winners' bracket wins the grand final, and the tournament.
    decide(tournament, lambda match: 0)
    assert [round_["stage"] for round_ in tournament.bracket()] == [
        "winners_round_1",
        WINNERS_FINAL,
        GRAND_FINAL,
    ]
    assert [round_["stage"] for round_ in tournament.bracket(losers=True)] == [
        "losers_round_1",
        LOSERS_FINAL,
    ]
    assert len(tournament.numbers()) == 6
    assert tournament.podium() == ["Alex", "Lea", "Sam"]
    forced = drawn(DOUBLE_KNOCKOUT, 4)
    decide(forced, lambda match: int(match.stage in (GRAND_FINAL, GRAND_FINAL_RESET)))
    assert [round_["stage"] for round_ in forced.bracket()][-2:] == [
        GRAND_FINAL,
        GRAND_FINAL_RESET,
    ]
    assert len(forced.numbers()) == 7
    # Alex won the winners' bracket and lost both grand finals to Lea.
    assert forced.podium() == ["Lea", "Alex", "Sam"]


@pytest.mark.parametrize(
    ("fmt", "count", "options"),
    [
        (DOUBLE_KNOCKOUT, 5, {}),
        (GROUPS_KNOCKOUT, 7, {"third_place": True, "advance": 2}),
    ],
)
def test_the_new_formats_survive_a_restart_at_every_stage(fmt, count, options):
    tournament, practice = director(count, fmt=fmt, **options)
    sides = iter([0, 1] * 20)
    while True:
        restored = TournamentDirector()
        restored.restore(stored(tournament))
        assert restored.stored() == tournament.stored()
        assert restored.snapshot() == tournament.snapshot()
        if tournament.tournament.status == FINISHED:
            break
        practice.current = next(sides)
        win(practice)
        tournament.booked(practice, NOW)
        if tournament.waiting:
            tournament.next_match(practice, NOW)
    assert tournament.tournament.status == FINISHED


@pytest.mark.parametrize(
    "change",
    [
        {"groups": 3},
        {"groups": "2"},
        {"advance": None},
        {"players": PLAYERS[:5]},
        {"format": GROUPS_KNOCKOUT, "groups": 0},
    ],
)
def test_a_broken_group_tournament_is_dropped(change):
    tournament, _ = director(8, fmt=GROUPS_KNOCKOUT)
    saved = stored(tournament)
    tournament.restore({**saved, "tournament": {**saved["tournament"], **change}})
    assert tournament.tournament is None


def test_a_stored_tournament_of_an_older_version_keeps_its_results():
    tournament, practice = director(5, fmt=KNOCKOUT)
    win(practice)
    tournament.booked(practice, NOW)
    saved = stored(tournament)["tournament"]
    # Older versions stored neither groups nor where players go on.
    del saved["groups"], saved["advance"]
    for match in saved["matches"]:
        del match["group"]
    restored = Tournament.restored(saved)
    assert restored.stored() == tournament.tournament.stored()
    assert restored.status in (PLAYING, WAITING)
