"""Actions of the integration: start a practice game or a tournament with one call,
correct and enter darts, pass the turn, undo a visit, save a highlight photo,
record a voice pack for the caller, and more."""

from __future__ import annotations

import math
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import (
    async_get_config_entry,
    async_register_admin_service,
)
from homeassistant.helpers.translation import async_get_translations

from .backup import RESTORE_MODES, async_backup, async_restore
from .board import RADIUS_MM, bed_name, segment_at
from .bot import valid_level
from .calls import speaks
from .const import DOMAIN, LANGUAGES
from .cricket import CRICKET_GAMES
from .export import EXPORT_CONTENTS, EXPORT_FORMATS, async_export
from .games_coordinator import AutodartsGamesCoordinator
from .highlights import async_save_highlight
from .manual import parse_bed
from .party import GOLF_HOLES, GOTCHA_TARGETS, MAX_ROUNDS, PARTY_GAMES, WORLD_ORDERS
from .positions import MAX_DISTANCE
from .practice import (
    GAME_OPTIONS,
    MAX_LEGS,
    MAX_PLAYERS,
    MAX_SETS,
    MODE_ALIASES,
    PARTY_PLAYERS,
    ROUND_LIMIT,
    TEAM_PLAYERS,
    UNWINNABLE_START,
    PracticeGame,
    unwinnable_rules,
    valid_start,
)
from .profiles import NAME_LENGTH, valid_name
from .scoring import BULL_MODES, DOUBLE, MODES, STRAIGHT
from .tournament import (
    FORMATS,
    MAX_ADVANCE,
    MAX_BOARDS,
    MAX_ENTRANTS,
    MAX_GROUPS,
    MAX_PAUSE,
    MAX_SEED,
    MAX_SUMMARY,
    MIN_ENTRANTS,
    MIN_GROUPS,
    RULES,
    TOURNAMENT_GAMES,
)
from .voice import Turn, passed, refusal, spoken, undone
from .voice import dart as dart_said
from .voice import name as voice_name
from .voice import visit as visit_said
from .voices import PACK_LENGTH, async_generate_voice_pack, async_voice_sound

if TYPE_CHECKING:
    # Home Assistant 2026.10 validates with probatio and makes "voluptuous" an alias
    # of it, so the types are probatio's; older versions still use voluptuous.
    import probatio as vol
else:
    import voluptuous as vol

SERVICE_START_GAME = "start_game"
SERVICE_START_PLAN = "start_plan"
SERVICE_NEXT_PLAN_STEP = "next_plan_step"
SERVICE_STOP_PLAN = "stop_plan"
SERVICE_DELETE_PLAYER = "delete_player"
SERVICE_RENAME_PLAYER = "rename_player"
SERVICE_EXPORT = "export"
SERVICE_BACKUP = "backup"
SERVICE_RESTORE = "restore"
SERVICE_START_TOURNAMENT = "start_tournament"
SERVICE_STOP_TOURNAMENT = "stop_tournament"
SERVICE_NEXT_TOURNAMENT_MATCH = "next_tournament_match"
SERVICE_CORRECT_DART = "correct_dart"
SERVICE_THROW_DART = "throw_dart"
SERVICE_ENTER_VISIT = "enter_visit"
SERVICE_NEXT_PLAYER = "next_player"
SERVICE_UNDO_VISIT = "undo_visit"
SERVICE_SAVE_HIGHLIGHT = "save_highlight"
SERVICE_VOICE_SOUND = "voice_sound"
SERVICE_GENERATE_VOICE_PACK = "generate_voice_pack"


# The longest bed name an error message repeats.
BED_ECHO = 20
# Numbers and beds are checked in the handlers, which explain a wrong value in
# the language of the user; the schemas only make them numbers and texts.
START_SCORES = vol.All(cv.ensure_list, [vol.Coerce(int)])
BED = vol.All(cv.string, vol.Length(min=1, max=255))


# A game's name as a voice assistant hears it is never longer.
GAME_TEXT = 64

# The game, the players and their names are checked in the handler, as a voice
# assistant may hear anything: a schema would refuse the call before the action
# could say why, and Assist would answer "Done". Without names, as an empty list,
# the players stay as they are. Double in and double out are the In and Out mode
# double or straight, from before the modes; a call sets a mode one way.
START_GAME_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required("game"): vol.All(vol.Coerce(str), vol.Length(min=1)),
        vol.Optional("players"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("legs"): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_LEGS)),
        vol.Optional("sets"): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_SETS)),
        vol.Exclusive("in_mode", "in_mode"): vol.In(MODES),
        vol.Exclusive("double_in", "in_mode"): cv.boolean,
        vol.Exclusive("out_mode", "out_mode"): vol.In(MODES),
        vol.Exclusive("double_out", "out_mode"): cv.boolean,
        vol.Optional("bull_mode"): vol.In(BULL_MODES),
        vol.Optional("max_rounds"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=ROUND_LIMIT)
        ),
        vol.Optional("bull_off"): cv.boolean,
        vol.Optional("bull_off_distance"): cv.boolean,
        vol.Optional("teams"): cv.boolean,
        vol.Optional("three_in_a_bed"): cv.boolean,
        vol.Optional("start_scores"): START_SCORES,
        vol.Optional("holes"): vol.All(vol.Coerce(int), vol.In(GOLF_HOLES)),
        vol.Optional("rounds"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_ROUNDS)
        ),
        vol.Optional("halve_on_miss"): cv.boolean,
        vol.Optional("order"): vol.In(WORLD_ORDERS),
        vol.Optional("target_score"): vol.All(
            vol.Coerce(int), vol.Range(min=GOTCHA_TARGETS[0], max=GOTCHA_TARGETS[1])
        ),
        vol.Optional("bot_level"): vol.Coerce(int),
    }
)

# Where a dart is, as the board reports it: 1 is the outer edge of the double
# ring, and y points to the 20. The bed follows from it.
POSITION: dict[vol.Marker, Any] = {
    vol.Optional("x"): vol.Coerce(float),
    vol.Optional("y"): vol.Coerce(float),
}
CORRECT_DART_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required("dart"): vol.All(vol.Coerce(int), vol.Range(min=1, max=3)),
        vol.Optional("segment"): BED,
        **POSITION,
    }
)
# The player an entry is for, as a voice assistant names them: the action refuses
# the entry while another player is at the board, and a name longer than a
# player's in words to say.
TURN: dict[vol.Marker, Any] = {
    vol.Optional("player"): vol.All(cv.string, vol.Strip, vol.Length(min=1)),
}
THROW_DART_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional("segment"): BED,
        **POSITION,
        **TURN,
    }
)


# An X01 visit by its score, or as the checkout of what the player has left: the
# darts it took and those at a double.
ENTER_VISIT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional("score"): vol.All(vol.Coerce(int), vol.Range(min=0, max=180)),
        vol.Optional("checkout"): cv.boolean,
        **TURN,
        vol.Optional("darts"): vol.All(vol.Coerce(int), vol.Range(min=1, max=3)),
        vol.Optional("darts_at_double"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=3)
        ),
    }
)


START_TOURNAMENT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional("players"): vol.All(
            cv.ensure_list,
            [vol.All(cv.string, vol.Length(max=NAME_LENGTH))],
            vol.Length(min=MIN_ENTRANTS, max=MAX_ENTRANTS),
        ),
        vol.Optional("start_scores"): START_SCORES,
        vol.Optional("format"): vol.All(cv.string, vol.In(FORMATS)),
        vol.Optional("game"): vol.All(cv.string, vol.In(TOURNAMENT_GAMES)),
        vol.Optional("legs"): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_LEGS)),
        vol.Optional("sets"): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_SETS)),
        **{vol.Optional(rule): cv.boolean for rule in RULES},
        vol.Optional("third_place"): cv.boolean,
        # 0 makes groups of about four players; there is no single group.
        vol.Optional("groups"): vol.All(
            vol.Coerce(int),
            vol.Any(0, vol.Range(min=MIN_GROUPS, max=MAX_GROUPS)),
        ),
        vol.Optional("advance"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_ADVANCE)
        ),
        vol.Optional("random_draw"): cv.boolean,
        vol.Optional("seed"): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_SEED)),
        vol.Optional("pause"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=MAX_PAUSE)
        ),
        vol.Optional("summary"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=MAX_SUMMARY)
        ),
        # The boards of a tournament on several boards, by the IDs of their
        # entries or devices; the board of the action is always one of them.
        vol.Optional("boards"): vol.All(
            cv.ensure_list, [cv.string], vol.Length(max=MAX_BOARDS)
        ),
    }
)

# Actions that only name the board.
BOARD_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})
# Which plan: by its name, by its steps, or with neither the plan of the day. The
# games check the steps, as they check those of the options.
START_PLAN_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Exclusive("plan", "plan"): vol.All(cv.string, vol.Length(min=1)),
        vol.Exclusive("steps", "plan"): vol.All(cv.ensure_list, [dict]),
        vol.Optional("name"): cv.string,
        vol.Optional("player"): cv.string,
    }
)


DELETE_PLAYER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required("name"): vol.All(cv.string, vol.Length(min=1, max=NAME_LENGTH)),
    }
)

# A player name as the profiles know it: trimmed, never empty.
PLAYER_NAME = vol.All(cv.string, vol.Strip, vol.Length(min=1, max=NAME_LENGTH))
SERVICE_LINK_PLAYER = "link_player"
SERVICE_UNLINK_PLAYER = "unlink_player"
LINK_PLAYER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required("player"): PLAYER_NAME,
        vol.Required("person"): cv.entity_domain("person"),
    }
)
UNLINK_PLAYER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required("player"): PLAYER_NAME,
    }
)
# The new name is checked in the handler, which says why a name cannot be one.
RENAME_PLAYER_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required("player"): PLAYER_NAME,
        vol.Required("new_name"): vol.All(cv.string, vol.Strip, vol.Length(min=1)),
    }
)


EXPORT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional("format", default="csv"): vol.In(EXPORT_FORMATS),
        vol.Optional("what", default="all"): vol.In(EXPORT_CONTENTS),
        # Without a folder, the export goes to homedarts/exports of the media folder.
        vol.Optional("folder"): vol.All(cv.string, vol.Length(min=1, max=255)),
    }
)


BACKUP_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})
RESTORE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        # A backup of a board, relative to the configuration folder or absolute.
        vol.Required("file"): vol.All(cv.string, vol.Length(min=1, max=4096)),
        vol.Optional("mode", default="replace"): vol.In(RESTORE_MODES),
    }
)


def _text(value: Any) -> str:
    """A player or a label as text: a template renders a name such as 180, None
    or [1] as a number, as nothing or as a list, which must not fail the call."""
    return "" if value is None else str(value)


# Any camera, also one that is no board camera. The player and the label become
# part of the file name, which leaves out what a file name cannot have; an empty
# folder, as the highlight photo blueprint passes its default, is the gallery.
SAVE_HIGHLIGHT_SCHEMA = vol.Schema(
    {
        vol.Required("camera"): cv.entity_domain("camera"),
        vol.Optional("folder"): vol.All(cv.string, vol.Strip, vol.Length(max=255)),
        vol.Optional("player"): _text,
        vol.Optional("label"): _text,
        # An empty clip camera, as the blueprint passes its default, is no clip.
        vol.Optional("clip_camera"): vol.Any("", cv.entity_domain("camera")),
        vol.Optional("clip_lookback"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=10)
        ),
        vol.Optional("clip_duration"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
    }
)


PACK = vol.All(cv.string, vol.Strip, vol.Length(min=1, max=PACK_LENGTH))
# The keys of the sound for a call, the first one the pack has is played: a
# template renders a score such as 180 as a number.
VOICE_SOUND_SCHEMA = vol.Schema(
    {
        vol.Required("pack"): PACK,
        vol.Required("keys"): vol.All(
            cv.ensure_list,
            [vol.All(vol.Coerce(str), vol.Length(min=1, max=PACK_LENGTH))],
            vol.Length(min=1, max=10),
        ),
    }
)
GENERATE_VOICE_PACK_SCHEMA = vol.Schema(
    {
        vol.Required("tts_entity"): cv.entity_domain("tts"),
        vol.Required("language"): vol.All(
            cv.string, vol.Strip, vol.Length(min=2, max=35)
        ),
        vol.Required("pack"): PACK,
        vol.Optional("voice"): vol.All(cv.string, vol.Strip, vol.Length(max=255)),
    }
)


def _coordinator(
    hass: HomeAssistant, entry_id: str | None
) -> AutodartsGamesCoordinator:
    """The board of the given entry, or the only local board there is."""
    if entry_id:
        # Home Assistant explains an unknown, foreign or unloaded entry itself.
        entries = [async_get_config_entry(hass, DOMAIN, entry_id)]
    else:
        # Entries that are not loaded are no candidates.
        entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state is ConfigEntryState.LOADED
        ]
    boards: list[AutodartsGamesCoordinator] = [
        entry.runtime_data.local for entry in entries
    ]
    if not boards:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_board"
        )
    if len(boards) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="several_boards"
        )
    return boards[0]


def _entry(hass: HomeAssistant, entry_id: str | None) -> ConfigEntry:
    """The given board, or the only one, loaded or not: a backup reads the
    stores of a board that does not start, and a restore writes them."""
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise _invalid("unknown_board", board=_echo(entry_id, 40))
        return entry
    entries = hass.config_entries.async_entries(DOMAIN, include_ignore=False)
    if not entries:
        raise _invalid("no_board")
    if len(entries) > 1:
        raise _invalid("several_boards")
    return entries[0]


def _board(hass: HomeAssistant, value: str) -> AutodartsGamesCoordinator:
    """A board of a tournament on several boards, by the ID of its entry, or
    of its device as the device picker of the action gives it."""
    if hass.config_entries.async_get_entry(value) is None:
        found = [
            entry_id
            for entry_id in _device_entries(dr.async_get(hass).async_get(value))
            if (entry := hass.config_entries.async_get_entry(entry_id))
            and entry.domain == DOMAIN
        ]
        if not found:
            raise _invalid("unknown_board", board=value)
        value = sorted(found)[0]
    return _coordinator(hass, value)


def _device_entries(device: dr.BaseDeviceEntry | None) -> set[str]:
    """The config entries of a device. Since Home Assistant 2026.10 a device has one,
    `config_entry_id`, and `config_entries` reports the integration, which 2027.10
    stops; only a device of several entries from before keeps them all there."""
    if device is None:
        return set()
    if getattr(device, "is_composite_device", True):
        # Home Assistant before 2026.10, or a device of several entries.
        return set(device.config_entries)
    return {device.config_entry_id}


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def _echo(value: str, limit: int) -> str:
    """A value as an error message repeats it: printable, and its beginning with an
    ellipsis where it is longer than the limit."""
    value = value.strip()
    shown = "".join(char if char.isprintable() else "?" for char in value[:limit])
    return f"{shown}\N{HORIZONTAL ELLIPSIS}" if len(value) > limit else shown


def _bed(value: str) -> dict[str, object]:
    """The dart in the named bed, or a translated error naming the bed."""
    dart = parse_bed(value)
    if dart is None:
        raise _invalid("invalid_segment", segment=_echo(value, BED_ECHO))
    return dart


def _position(data: Mapping[str, Any]) -> tuple[float, float] | None:
    """The position of an action, both coordinates or none, on the board or
    around it."""
    if "x" not in data and "y" not in data:
        return None
    x, y = data.get("x", math.nan), data.get("y", math.nan)
    if not all(math.isfinite(value) and abs(value) <= MAX_DISTANCE for value in (x, y)):
        raise _invalid("invalid_position", limit=f"{MAX_DISTANCE:g}")
    return x, y


def _dart_at(
    data: Mapping[str, Any],
) -> tuple[dict[str, object], tuple[float, float] | None]:
    """The dart of an action and where it is: the named bed, the bed at the
    position, or both when they agree."""
    position = _position(data)
    named = _bed(data["segment"]) if "segment" in data else None
    if position is None:
        if named is None:
            raise _invalid("no_bed")
        return named, None
    found = _bed(
        bed_name(*segment_at(position[0] * RADIUS_MM, position[1] * RADIUS_MM))
    )
    if named is not None and named["name"] != found["name"]:
        raise _invalid(
            "bed_position", segment=str(named["name"]), found=str(found["name"])
        )
    return found, position


def _plain(text: str) -> str:
    """A name as it is spoken: without case, spaces and punctuation."""
    return re.sub(r"[\W_]+", "", text.casefold())


async def _game_key(hass: HomeAssistant, game: str) -> str:
    """The game an action names: its key, such as 501 or around_the_clock, or its
    name in a language of the integration as a voice assistant hears it, such as
    "Around the Clock", "Bobs 27" or "Doppeltraining". The beginning of a name
    is enough where it fits one game alone, such as "Cut Throat"."""
    if game in GAME_OPTIONS:
        return game
    if len(game) > GAME_TEXT:
        raise _invalid("unknown_game", game=_echo(game, GAME_TEXT))
    names = {key: {_plain(key)} for key in GAME_OPTIONS}
    for language in LANGUAGES:
        texts = await async_get_translations(hass, language, "entity", {DOMAIN})
        for key in GAME_OPTIONS:
            # Home Assistant fills a missing translation with the English one.
            name = texts[f"component.{DOMAIN}.entity.select.practice_game.state.{key}"]
            names[key].add(_plain(name))
    wanted = _plain(game)
    same = {key for key, spoken in names.items() if wanted in spoken}
    begun = {
        key
        for key, spoken in names.items()
        if len(wanted) >= 3 and any(name.startswith(wanted) for name in spoken)
    }
    for found in (same, begun):
        if len(found) == 1:
            return found.pop()
    raise _invalid("unknown_game", game=_echo(game, GAME_TEXT))


async def _game_on(hass: HomeAssistant, key: str, practice: PracticeGame) -> str:
    """What a voice assistant says when a game starts: the game and who plays it."""
    # The name of the game in the language of the answer, such as German for de-CH.
    language = speaks(hass.config.language)
    texts = await async_get_translations(hass, language, "entity", {DOMAIN})
    game = texts.get(f"component.{DOMAIN}.entity.select.practice_game.state.{key}", key)
    players = [name for name in practice.names[: practice.humans] if name]
    if practice.bot_seat is not None:
        players.append(await spoken(hass, "voice_bot"))
    if not players:
        return await spoken(hass, "voice_game_on_alone", game=game)
    conjunction = await spoken(hass, "voice_and")
    last = f" {conjunction} "
    together = last.join(
        [", ".join(players[:-1]), players[-1]] if len(players) > 1 else players
    )
    return await spoken(hass, "voice_game_on", game=game, players=together)


async def _check_turn(
    hass: HomeAssistant, practice: PracticeGame, player: str | None
) -> None:
    """An entry for a named player only while they are at the board, as a voice
    assistant may hear the wrong one; without a game, the entry says why itself."""
    if player is None:
        return
    _check_length(player)
    if practice.kind is None or practice.bot_up:
        return
    who = practice.thrower
    if who is None or _plain(who) != _plain(player):
        raise _invalid(
            "not_their_turn",
            player=player,
            name=await voice_name(hass, practice, practice.current),
        )


def _visit_score(data: Mapping[str, Any], practice: PracticeGame) -> int:
    """The score of a visit an action enters: its score, or for a checkout what the
    player has left."""
    score: int | None = data.get("score")
    if not data.get("checkout"):
        if score is None:
            raise _invalid("visit_no_score")
        return score
    player = practice.players[practice.current] if practice.players else None
    remaining = player.remaining if player is not None and practice.game else 0
    if score is not None and score != remaining:
        raise _invalid("checkout_score", score=str(score), remaining=str(remaining))
    return remaining


def _check_length(name: str) -> None:
    """A name no longer than a player's, which a voice assistant may hear in a
    sentence it took apart wrongly."""
    if len(name.strip()) > NAME_LENGTH:
        raise _invalid(
            "name_too_long", name=_echo(name, NAME_LENGTH), limit=str(NAME_LENGTH)
        )


def _check_names(names: list[str] | None) -> None:
    """Names without the characters no player name contains, such as { } % #,
    which templates of automations would run, and no longer than a player's."""
    if not all(valid_name(name) for name in names or []):
        raise _invalid("invalid_player_name")
    for name in names or []:
        _check_length(name)


def _check_level(level: int) -> None:
    if not valid_level(level):
        raise _invalid("invalid_bot_level")


def _check_starts(
    starts: list[int] | None,
    seats: int,
    teams: bool = False,
    x01: bool = False,
    unwinnable: bool = False,
    current: list[int] | None = None,
) -> None:
    """Start scores of 0 or 2 to 1001, one per seat or, for teams, one per team;
    with unwinnable In and Out modes, such as double in and double out, a start
    score of 3 cannot be won."""
    for start in starts or []:
        if not valid_start(start):
            raise _invalid("invalid_start_score")
    if starts is not None and teams and len(starts) > TEAM_PLAYERS // 2:
        raise _invalid("team_start_scores")
    if starts is not None and len(starts) > seats:
        raise _invalid(
            "too_many_start_scores", scores=str(len(starts)), players=str(seats)
        )
    # Unset start scores stay as they are; a team plays from its first player's.
    playing = (current or []) if starts is None else starts
    used = playing[: TEAM_PLAYERS // 2 if teams else seats]
    if x01 and unwinnable and UNWINNABLE_START in used:
        raise _invalid("unwinnable_start")


def _check_players(
    game: str,
    names: list[str] | None,
    players: int,
    teams: bool = False,
    bot: bool = False,
) -> None:
    """Every player needs a name of their own, party games take eight players
    and the others four, Killer needs two players and teams four players of X01
    or a Cricket game; the bot takes a seat of its own."""
    seen: set[str] = set()
    for name in names or []:
        key = name.strip().casefold()
        if key in seen:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="duplicate_player",
                translation_placeholders={"name": name.strip()},
            )
        if key:
            seen.add(key)
    seats = PARTY_PLAYERS if game in PARTY_GAMES else MAX_PLAYERS
    if names and len(names) > seats:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="too_many_players",
            translation_placeholders={"count": str(seats)},
        )
    count = len(names) if names else min(players, seats)
    if bot and (game.isdigit() or game in CRICKET_GAMES):
        if count >= MAX_PLAYERS:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="bot_seat"
            )
        count += 1
    if game == "killer" and count < 2:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="killer_players"
        )
    if teams and not (game.isdigit() or game in CRICKET_GAMES):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="team_game"
        )
    if teams and count != TEAM_PLAYERS:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="team_players"
        )


def _modes(call: ServiceCall) -> dict[str, str]:
    """The In and Out mode as the call sets them, by name or as double in and
    double out."""
    modes = {
        rule: DOUBLE if call.data[alias] else STRAIGHT
        for alias, rule in MODE_ALIASES.items()
        if alias in call.data
    }
    return {
        **modes,
        **{
            rule: call.data[rule] for rule in MODE_ALIASES.values() if rule in call.data
        },
    }


def _unwinnable(call: ServiceCall, practice: PracticeGame) -> bool:
    """Whether the In and Out mode, as the call sets them or as they are,
    cannot win a start score of 3."""
    modes = {"in_mode": practice.rule("in_mode"), "out_mode": practice.rule("out_mode")}
    modes.update(_modes(call))
    return unwinnable_rules(modes["in_mode"], modes["out_mode"])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def start_game(call: ServiceCall) -> ServiceResponse:
        """Start a game. Asked for a response, as by a voice assistant, the action
        answers what started or what was wrong in words to say, instead of failing."""
        try:
            key = await _start_game(call)
        except ServiceValidationError as error:
            if not call.return_response:
                raise
            return {"started": False, "message": await refusal(hass, error)}
        if not call.return_response:
            return None
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        practice = coordinator.games.practice
        return {
            "started": True,
            "game": key,
            "players": [name for name in practice.names[: practice.humans] if name],
            "bot": practice.bot_seat is not None,
            "message": await _game_on(hass, key, practice),
        }

    async def _start_game(call: ServiceCall) -> str:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        game = await _game_key(hass, call.data["game"])
        practice = coordinator.games.practice
        said: list[str] = call.data.get("players", [])
        _check_names(said)
        # A name a player already has keeps its spelling, as a voice may lower it.
        names = [practice.profiles.spelled(name) for name in said] or None
        level: int = call.data.get("bot_level", practice.bot_level)
        _check_level(level)
        _check_players(
            game, names, practice.humans, call.data.get("teams") is True, level > 0
        )
        paired = game.isdigit() or game in CRICKET_GAMES
        # The bot's seat, after the players, has a start score, too.
        seats = (len(names) if names else practice.humans) + int(level > 0 and paired)
        _check_starts(
            call.data.get("start_scores"),
            seats,
            teams=paired
            and seats == TEAM_PLAYERS
            and bool(call.data.get("teams", practice.teams)),
            x01=game.isdigit(),
            current=list(practice.starts),
            unwinnable=_unwinnable(call, practice),
        )
        modes = _modes(call)
        await coordinator.async_start_game(
            int(game) if game.isdigit() else game,
            names=names,
            legs=call.data.get("legs"),
            sets=call.data.get("sets"),
            in_mode=modes.get("in_mode"),
            out_mode=modes.get("out_mode"),
            bull_mode=call.data.get("bull_mode"),
            max_rounds=call.data.get("max_rounds"),
            bull_off=call.data.get("bull_off"),
            bull_off_distance=call.data.get("bull_off_distance"),
            teams=call.data.get("teams"),
            three_in_a_bed=call.data.get("three_in_a_bed"),
            start_scores=call.data.get("start_scores"),
            holes=call.data.get("holes"),
            rounds=call.data.get("rounds"),
            bot_level=call.data.get("bot_level"),
            halve_on_miss=call.data.get("halve_on_miss"),
            order=call.data.get("order"),
            target_score=call.data.get("target_score"),
        )
        return game

    async def start_plan(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        await coordinator.async_start_plan(
            plan=call.data.get("plan"),
            name=call.data.get("name"),
            steps=call.data.get("steps"),
            player=call.data.get("player"),
        )

    async def next_plan_step(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        await coordinator.async_next_plan_step()

    async def stop_plan(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        await coordinator.async_stop_plan()

    hass.services.async_register(
        DOMAIN, SERVICE_START_PLAN, start_plan, schema=START_PLAN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_NEXT_PLAN_STEP, next_plan_step, schema=BOARD_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_PLAN, stop_plan, schema=BOARD_SCHEMA
    )

    async def delete_player(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        if not await coordinator.async_delete_player(call.data["name"]):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_player",
                translation_placeholders={"name": call.data["name"]},
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_GAME,
        start_game,
        schema=START_GAME_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def export(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        return await async_export(
            hass,
            coordinator,
            call.data["format"],
            call.data["what"],
            call.data.get("folder"),
        )

    # Actions that forget or write out the players' data are for administrators;
    # automations and scripts, which run without a user, still use them.
    async_register_admin_service(
        hass, DOMAIN, SERVICE_DELETE_PLAYER, delete_player, schema=DELETE_PLAYER_SCHEMA
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_EXPORT,
        export,
        schema=EXPORT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def backup(call: ServiceCall) -> ServiceResponse:
        return await async_backup(
            hass, _entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        )

    async def restore(call: ServiceCall) -> ServiceResponse:
        return await async_restore(
            hass,
            _entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID)),
            call.data["file"],
            call.data["mode"],
        )

    # A backup holds the players' data, and a restore replaces it.
    for service, handler, schema in (
        (SERVICE_BACKUP, backup, BACKUP_SCHEMA),
        (SERVICE_RESTORE, restore, RESTORE_SCHEMA),
    ):
        async_register_admin_service(
            hass,
            DOMAIN,
            service,
            handler,
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )

    async def link_player(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        person: str = call.data["person"]
        _check_names([call.data["player"]])
        if hass.states.get(person) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_person",
                translation_placeholders={"person": person},
            )
        await coordinator.async_link_player(call.data["player"], person)

    async def unlink_player(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        if not await coordinator.async_link_player(call.data["player"], None):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_player",
                translation_placeholders={"name": call.data["player"]},
            )

    async_register_admin_service(
        hass, DOMAIN, SERVICE_LINK_PLAYER, link_player, schema=LINK_PLAYER_SCHEMA
    )
    async_register_admin_service(
        hass, DOMAIN, SERVICE_UNLINK_PLAYER, unlink_player, schema=UNLINK_PLAYER_SCHEMA
    )

    async def rename_player(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        _check_names([call.data["new_name"]])
        await coordinator.async_rename_player(
            call.data["player"], call.data["new_name"]
        )

    async_register_admin_service(
        hass, DOMAIN, SERVICE_RENAME_PLAYER, rename_player, schema=RENAME_PLAYER_SCHEMA
    )

    async def start_tournament(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        setup = coordinator.games.tournament.setup
        _check_names(call.data.get("players"))
        _check_starts(
            call.data.get("start_scores"),
            len(call.data.get("players", setup.players)),
            x01=str(call.data.get("game", setup.game)).isdigit(),
            # A tournament plays double or straight in and out.
            unwinnable=all(
                call.data.get(
                    alias, coordinator.games.practice.tournament_setting(alias)
                )
                for alias in MODE_ALIASES
            ),
        )
        boards = [_board(hass, value) for value in call.data.get("boards", [])]
        options = {
            key: value
            for key, value in call.data.items()
            if key not in (ATTR_CONFIG_ENTRY_ID, "boards")
        }
        rules = {rule: options.pop(rule, None) for rule in RULES}
        await coordinator.async_start_tournament(boards=boards, rules=rules, **options)

    async def stop_tournament(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        await coordinator.async_stop_tournament()

    async def next_tournament_match(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        await coordinator.async_next_tournament_match()

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_TOURNAMENT,
        start_tournament,
        schema=START_TOURNAMENT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_TOURNAMENT, stop_tournament, schema=BOARD_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_NEXT_TOURNAMENT_MATCH,
        next_tournament_match,
        schema=BOARD_SCHEMA,
    )

    async def correct_dart(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        dart, position = _dart_at(call.data)
        await coordinator.async_correct_dart(call.data["dart"], dart, position)

    async def answered(
        call: ServiceCall, done: str, act: Callable[[bool], Awaitable[str | None]]
    ) -> ServiceResponse:
        """Run an action at the board. Asked for a response, as by a voice assistant,
        it answers what happened or what was wrong in words to say, instead of
        failing."""
        try:
            message = await act(call.return_response)
        except ServiceValidationError as error:
            if not call.return_response:
                raise
            return {done: False, "message": await refusal(hass, error)}
        return {done: True, "message": message} if call.return_response else None

    async def throw_dart(call: ServiceCall) -> ServiceResponse:
        async def act(answer: bool) -> str | None:
            coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
            practice = coordinator.games.practice
            await _check_turn(hass, practice, call.data.get("player"))
            bed, position = _dart_at(call.data)
            await coordinator.async_throw_dart(bed, position)
            return await dart_said(hass, practice, str(bed["name"])) if answer else None

        return await answered(call, "entered", act)

    async def enter_visit(call: ServiceCall) -> ServiceResponse:
        async def act(answer: bool) -> str | None:
            coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
            practice = coordinator.games.practice
            await _check_turn(hass, practice, call.data.get("player"))
            score = _visit_score(call.data, practice)
            turn = Turn.of(practice)
            await coordinator.async_enter_visit(
                score,
                call.data.get("darts"),
                call.data.get("darts_at_double"),
                checkout=call.data.get("checkout") is True,
            )
            return await visit_said(hass, practice, turn, score) if answer else None

        return await answered(call, "entered", act)

    async def next_player(call: ServiceCall) -> ServiceResponse:
        async def act(answer: bool) -> str | None:
            coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
            turn = Turn.of(coordinator.games.practice)
            await coordinator.async_next_player()
            return (
                await passed(hass, coordinator.games.practice, turn) if answer else None
            )

        return await answered(call, "passed", act)

    async def undo_visit(call: ServiceCall) -> ServiceResponse:
        async def act(answer: bool) -> str | None:
            coordinator = _coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
            await coordinator.async_undo_visit()
            if not answer:
                return None
            score = sum(
                dart["number"] * dart["multiplier"]
                for dart in coordinator.games.training.visit()
            )
            return await undone(hass, coordinator.games.practice, score)

        return await answered(call, "undone", act)

    async def save_highlight(call: ServiceCall) -> ServiceResponse:
        saved = await async_save_highlight(
            hass,
            call.data["camera"],
            call.data.get("folder"),
            call.data.get("player", ""),
            call.data.get("label", ""),
            call.data.get("clip_camera", ""),
            call.data.get("clip_lookback", 5),
            call.data.get("clip_duration", 8),
        )
        return saved if call.return_response else None

    # It writes files, like homedarts.export, so it is for administrators, too;
    # the highlight photo blueprint runs it as an automation, without a user.
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_SAVE_HIGHLIGHT,
        save_highlight,
        schema=SAVE_HIGHLIGHT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def voice_sound(call: ServiceCall) -> ServiceResponse:
        return await async_voice_sound(hass, call.data["pack"], call.data["keys"])

    # It only reads which sounds a pack has, as the media browser shows them, so the
    # caller blueprints and anyone may ask.
    hass.services.async_register(
        DOMAIN,
        SERVICE_VOICE_SOUND,
        voice_sound,
        schema=VOICE_SOUND_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    async def generate_voice_pack(call: ServiceCall) -> ServiceResponse:
        generated = await async_generate_voice_pack(
            hass,
            call.data["tts_entity"],
            call.data["language"],
            call.data["pack"],
            call.data.get("voice") or None,
        )
        return generated if call.return_response else None

    # It writes hundreds of files to the media folder, so it is for administrators.
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_GENERATE_VOICE_PACK,
        generate_voice_pack,
        schema=GENERATE_VOICE_PACK_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_CORRECT_DART, correct_dart, schema=CORRECT_DART_SCHEMA
    )
    for name, handler, schema in (
        (SERVICE_THROW_DART, throw_dart, THROW_DART_SCHEMA),
        (SERVICE_ENTER_VISIT, enter_visit, ENTER_VISIT_SCHEMA),
        (SERVICE_NEXT_PLAYER, next_player, BOARD_SCHEMA),
        (SERVICE_UNDO_VISIT, undo_visit, BOARD_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )
