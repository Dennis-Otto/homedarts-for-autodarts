"""The actions: which board they act on, and what they accept."""

import pytest
import voluptuous as vol
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homedarts.const import DOMAIN
from custom_components.homedarts.practice import MAX_LEGS, MAX_SETS
from custom_components.homedarts.profiles import NAME_LENGTH

from .local_helpers import board, setup_local

LONGEST = "x" * NAME_LENGTH
# The actions that forget or write out the data of the players.
ADMIN_ACTIONS = {
    "delete_player": {"name": "Alex"},
    "export": {"what": "profiles"},
    "link_player": {"player": "Alex", "person": "person.alex"},
    "unlink_player": {"player": "Alex"},
    "rename_player": {"player": "Alex", "new_name": "Al"},
}


async def call(hass, service: str, context: Context | None = None, **data) -> None:
    await hass.services.async_call(
        DOMAIN, service, data, blocking=True, context=context
    )


async def invalid(hass, service: str, **data) -> ServiceValidationError:
    """The translated error of a call that is refused before anything changes."""
    with pytest.raises(ServiceValidationError) as error:
        await call(hass, service, **data)
    assert error.value.translation_domain == DOMAIN
    return error.value


@pytest.mark.parametrize(
    "data",
    [
        {"game": "501", "legs": 0},
        {"game": "501", "legs": MAX_LEGS + 1},
        {"game": "501", "sets": 0},
        {"game": "501", "sets": MAX_SETS + 1},
        {"game": "501", "legs": "many"},
        {"game": "501", "double_out": "sometimes"},
        {"game": "501", "unknown": True},
        {},
    ],
)
async def test_start_game_rejects_values_beyond_its_limits(hass, aioclient_mock, data):
    entry = await setup_local(hass, aioclient_mock, state=board())
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "start_game", data, blocking=True)
    assert entry.runtime_data.local.games.practice.game == 0


@pytest.mark.parametrize(
    "data,check",
    [
        (
            {"game": "501", "players": ["A", "B", "C", LONGEST]},
            lambda practice: practice.names[:5] == ["A", "B", "C", LONGEST, ""],
        ),
        # One name is a list of one.
        (
            {"game": "301", "players": "Alex"},
            lambda practice: practice.names[0] == "Alex",
        ),
        # No names, as a cleared field of the action sends them, keep the players.
        (
            {"game": "301", "players": []},
            lambda practice: practice.names[:2] == ["", ""],
        ),
        (
            {"game": "501", "legs": MAX_LEGS, "sets": MAX_SETS},
            lambda practice: (
                (practice.legs_to_win, practice.sets_to_win) == (MAX_LEGS, MAX_SETS)
            ),
        ),
        (
            {"game": "501", "legs": "2", "double_in": "on"},
            lambda practice: practice.legs_to_win == 2 and practice.double_in,
        ),
    ],
)
async def test_start_game_accepts_values_at_its_limits(
    hass, aioclient_mock, data, check
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await hass.services.async_call(DOMAIN, "start_game", data, blocking=True)
    assert check(entry.runtime_data.local.games.practice)


@pytest.mark.parametrize(
    "data", [{}, {"name": ""}, {"name": LONGEST + "x"}, {"name": ["A", "B"]}]
)
async def test_delete_player_needs_one_name(hass, aioclient_mock, data):
    await setup_local(hass, aioclient_mock, state=board())
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "delete_player", data, blocking=True)


@pytest.mark.parametrize("service", ["start_game", "delete_player"])
async def test_an_action_names_the_board_problem(hass, aioclient_mock, service):
    """Home Assistant explains entries that are unknown, foreign or not loaded."""
    data = {"game": "501"} if service == "start_game" else {"name": "Alex"}
    entry = await setup_local(hass, aioclient_mock, state=board())
    other = MockConfigEntry(domain="demo", title="Demo")
    other.add_to_hass(hass)

    async def problem(entry_id: str) -> tuple[str | None, str | None]:
        with pytest.raises(ServiceValidationError) as error:
            await hass.services.async_call(
                DOMAIN,
                service,
                {**data, "config_entry_id": entry_id},
                blocking=True,
            )
        return error.value.translation_domain, error.value.translation_key

    assert await problem("nope") == (
        "homeassistant",
        "service_config_entry_not_found",
    )
    assert await problem(other.entry_id) == (
        "homeassistant",
        "service_config_entry_wrong_domain",
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await problem(entry.entry_id) == (
        "homeassistant",
        "service_config_entry_not_loaded",
    )
    # Without an entry, only a loaded board counts.
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)
    assert error.value.translation_key == "no_board"


# -- administrators ----------------------------------------------------------------


@pytest.mark.parametrize("service", ADMIN_ACTIONS)
async def test_actions_on_the_players_data_are_for_administrators(
    hass, aioclient_mock, tmp_path, hass_read_only_user, hass_admin_user, service
):
    """A wall tablet's user may play, but not delete or export the players."""
    hass.config.config_dir = str(tmp_path)
    hass.config.media_dirs = {"local": str(tmp_path / "media")}
    hass.config.allowlist_external_dirs = {str(tmp_path / "media")}
    hass.states.async_set("person.alex", "home")
    entry = await setup_local(hass, aioclient_mock, state=board())
    profiles = entry.runtime_data.local.games.practice.profiles
    await entry.runtime_data.local.async_link_player("Alex", "person.alex")
    before = profiles.snapshot()
    with pytest.raises(Unauthorized):
        await call(
            hass,
            service,
            Context(user_id=hass_read_only_user.id),
            **ADMIN_ACTIONS[service],
        )
    assert profiles.snapshot() == before
    assert not (tmp_path / "media").exists()
    await call(
        hass, service, Context(user_id=hass_admin_user.id), **ADMIN_ACTIONS[service]
    )
    # Playing stays open for every user.
    await call(hass, "start_game", Context(user_id=hass_read_only_user.id), game="301")
    assert entry.runtime_data.local.games.practice.game == 301


# -- translated errors --------------------------------------------------------------


@pytest.mark.parametrize(
    "data,key,placeholders",
    [
        ({"bot_level": 10}, "invalid_bot_level", None),
        ({"bot_level": 121}, "invalid_bot_level", None),
        # Lengths and counts are explained, so a voice assistant can say them.
        (
            {"players": ["A", "B", "C", "D", "E"]},
            "too_many_players",
            {"count": "4"},
        ),
        (
            {"players": [LONGEST + "x"]},
            "name_too_long",
            {"name": LONGEST + "…", "limit": str(NAME_LENGTH)},
        ),
        ({"start_scores": [501, 1]}, "invalid_start_score", None),
        ({"start_scores": ["1002"]}, "invalid_start_score", None),
        (
            {"players": ["A", "B"], "start_scores": [501, 301, 101]},
            "too_many_start_scores",
            {"scores": "3", "players": "2"},
        ),
        # The bot's seat after the players has a start score of its own.
        (
            {"players": ["A"], "bot_level": 60, "start_scores": [501, 301, 101]},
            "too_many_start_scores",
            {"scores": "3", "players": "2"},
        ),
        (
            {"players": ["A", "B", "C", "D"], "teams": True, "start_scores": [1, 2, 3]},
            "invalid_start_score",
            None,
        ),
        (
            {
                "players": ["A", "B", "C", "D"],
                "teams": True,
                "start_scores": [501, 301, 101],
            },
            "team_start_scores",
            None,
        ),
        (
            {"double_in": True, "double_out": True, "start_scores": [501, 3]},
            "unwinnable_start",
            None,
        ),
    ],
)
async def test_start_game_explains_a_wrong_value(
    hass, aioclient_mock, data, key, placeholders
):
    """A wrong value is refused before anything changes, with a translated reason
    that names it."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    await entry.runtime_data.local.async_set_players(2)
    error = await invalid(hass, "start_game", game="501", **data)
    assert (error.translation_key, error.translation_placeholders) == (
        key,
        placeholders,
    )
    assert entry.runtime_data.local.games.practice.game == 0


@pytest.mark.parametrize(
    "data,starts",
    [
        ({"players": ["A", "B"], "start_scores": ["501", 301]}, [501, 301, 0, 0]),
        (
            {"players": ["A"], "bot_level": 60, "start_scores": [501, 301]},
            [501, 301, 0, 0],
        ),
        (
            {
                "players": ["A", "B", "C", "D"],
                "teams": True,
                "start_scores": [501, 301],
            },
            [501, 301, 0, 0],
        ),
        # 3 is a fine start score with double out alone.
        ({"double_in": False, "double_out": True, "start_scores": [3]}, [3, 0, 0, 0]),
    ],
)
async def test_start_game_takes_one_start_score_per_seat(
    hass, aioclient_mock, data, starts
):
    entry = await setup_local(hass, aioclient_mock, state=board())
    await call(hass, "start_game", game="501", **data)
    assert entry.runtime_data.local.games.practice.starts == starts


async def test_start_game_checks_the_start_scores_it_keeps(hass, aioclient_mock):
    """Without start scores, those set on the board are checked."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    await coordinator.async_set_start_score(1, 3)
    error = await invalid(
        hass,
        "start_game",
        game="301",
        players=["A", "B"],
        double_in=True,
        double_out=True,
    )
    assert error.translation_key == "unwinnable_start"
    # A team plays from its first player's start score only.
    await coordinator.async_set_start_score(1, 0)
    await coordinator.async_set_start_score(2, 3)
    await call(
        hass,
        "start_game",
        game="301",
        players=["A", "B", "C", "D"],
        teams=True,
        double_in=True,
        double_out=True,
    )
    assert coordinator.games.practice.game == 301


async def test_start_tournament_explains_wrong_start_scores(hass, aioclient_mock):
    entry = await setup_local(hass, aioclient_mock, state=board())
    director = entry.runtime_data.local.games.tournament
    players = ["Alex", "Sam", "Kim"]
    error = await invalid(
        hass, "start_tournament", players=players, start_scores=[501, 501, 301, 101]
    )
    assert (error.translation_key, error.translation_placeholders) == (
        "too_many_start_scores",
        {"scores": "4", "players": "3"},
    )
    error = await invalid(hass, "start_tournament", players=players, start_scores=[1])
    assert error.translation_key == "invalid_start_score"
    error = await invalid(
        hass,
        "start_tournament",
        players=players,
        game="301",
        double_in=True,
        double_out=True,
        start_scores=[501, 3],
    )
    assert error.translation_key == "unwinnable_start"
    # Without names, the players of the setup count.
    await entry.runtime_data.local.async_set_tournament(players=[*players, "Lea"])
    error = await invalid(hass, "start_tournament", start_scores=[501] * 5)
    assert error.translation_placeholders == {"scores": "5", "players": "4"}
    assert director.tournament is None
    # Cricket has no start scores to win from.
    await call(
        hass,
        "start_tournament",
        players=players,
        game="cricket",
        double_in=True,
        double_out=True,
        start_scores=[3],
    )
    assert director.tournament is not None


async def test_a_wrong_bed_is_explained(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock, state=board())
    for service, data in (("correct_dart", {"dart": 1}), ("throw_dart", {})):
        error = await invalid(hass, service, segment=" T21 ", **data)
        assert (error.translation_key, error.translation_placeholders) == (
            "invalid_segment",
            {"segment": "T21"},
        )
    # Only the start of a long text is repeated.
    error = await invalid(hass, "throw_dart", segment="X" * 40)
    assert error.translation_placeholders == {"segment": "X" * 20 + "…"}
    error = await invalid(hass, "throw_dart", segment="T\x0020")
    assert error.translation_placeholders == {"segment": "T?20"}
    with pytest.raises(vol.Invalid):
        await call(hass, "throw_dart", segment="")


async def test_a_wrong_position_is_explained(hass, aioclient_mock):
    await setup_local(hass, aioclient_mock, state=board())
    for service, data in (("correct_dart", {"dart": 1}), ("throw_dart", {})):
        # Neither a bed nor a position.
        error = await invalid(hass, service, **data)
        assert error.translation_key == "no_bed"
        # Half a position, one far off the board, or one that is no number.
        for position in (
            {"x": 0.1},
            {"y": 0.1},
            {"x": 3.5, "y": 0},
            {"x": "nan", "y": 0},
        ):
            error = await invalid(hass, service, **data, **position)
            assert (error.translation_key, error.translation_placeholders) == (
                "invalid_position",
                {"limit": "3"},
            )
        # A bed that is not where the position says.
        error = await invalid(hass, service, **data, segment="d20", x=0.0, y=0.6)
        assert (error.translation_key, error.translation_placeholders) == (
            "bed_position",
            {"segment": "D20", "found": "T20"},
        )
        # A wrong bed is named as such, with a position or without.
        error = await invalid(hass, service, **data, segment="T21", x=0.0, y=0.6)
        assert error.translation_key == "invalid_segment"
    with pytest.raises(vol.Invalid):
        await call(hass, "throw_dart", x="left", y=0.5)


async def test_player_names_that_templates_would_run_are_refused(hass, aioclient_mock):
    """{ } % # in a name would run in the templates of automations."""
    entry = await setup_local(hass, aioclient_mock, state=board())
    coordinator = entry.runtime_data.local
    hass.states.async_set("person.alex", "home")
    for service, data in (
        ("start_game", {"game": "501", "players": ["Alex", "{{ 6*7 }}"]}),
        ("start_tournament", {"players": ["Alex", "Sam", "50%"]}),
        ("link_player", {"player": "#Kim", "person": "person.alex"}),
    ):
        error = await invalid(hass, service, **data)
        assert error.translation_key == "invalid_player_name"
    assert not coordinator.games.practice.profiles.snapshot()["players"]
    assert coordinator.games.tournament.tournament is None
    # The board checks the names of a game on its own, too.
    with pytest.raises(ServiceValidationError) as error:
        await coordinator.async_start_game(501, names=["Alex", "{x}"])
    assert error.value.translation_key == "invalid_player_name"
