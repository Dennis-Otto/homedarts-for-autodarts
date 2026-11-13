"""Names of the practice and tournament players, for the scoreboard and events."""

from typing import Any

from homeassistant.components.text import TextEntity
from homeassistant.const import MAX_LENGTH_STATE_STATE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import AutodartsStoredEntity
from .games_coordinator import AutodartsGamesCoordinator, refusals
from .practice import PARTY_PLAYERS
from .profiles import NAME_LENGTH, clean_name
from .runtime import AutodartsConfigEntry
from .tournament import (
    MAX_ENTRANTS,
    MIN_ENTRANTS,
    check_names,
    parse_players,
    split_players,
)

PARALLEL_UPDATES = 0
# What a list of tournament players too long for the state ends with: the
# names that did not fit.
ELLIPSIS = "…"
MORE = f", {ELLIPSIS}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutodartsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.local
    async_add_entities(
        [
            *(
                AutodartsPlayerName(coordinator, index)
                for index in range(PARTY_PLAYERS)
            ),
            AutodartsTournamentPlayers(coordinator),
        ]
    )


class AutodartsPlayerName(AutodartsStoredEntity, TextEntity):
    """An empty name shows as "Player N" on the card."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "practice_player"
    _attr_native_min = 0
    _attr_native_max = NAME_LENGTH
    # The seat never changes, so the history needs it not.
    _unrecorded_attributes = frozenset({"seat"})

    def __init__(self, coordinator: AutodartsGamesCoordinator, index: int) -> None:
        super().__init__(coordinator, f"practice_player_{index + 1}")
        self._attr_translation_key = "practice_player"
        self._attr_translation_placeholders = {"number": str(index + 1)}
        # The card finds the seat of a name here, as a user may rename the entity ID.
        self._attr_extra_state_attributes = {"seat": index + 1}
        self._index = index

    @property
    def native_value(self) -> str:
        return self.coordinator.games.practice.names[self._index]

    async def async_set_value(self, value: str) -> None:
        """Every seat in play needs a name of its own, as in start_game and
        tournaments: two seats of one name would be one player, playing against
        themselves. A resting seat gives its name up, see PracticeGame.rename."""
        with refusals():
            check_names([value])
        if not await self.coordinator.async_set_player_name(self._index, value):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="duplicate_player",
                translation_placeholders={"name": clean_name(value)},
            )


class AutodartsTournamentPlayers(AutodartsStoredEntity, TextEntity):
    """The players of the next tournament, their names separated by commas.

    A state holds 255 characters, fewer than 32 long names take: a longer list
    shows the names that fit and an ellipsis, and the attribute players has
    them all. A list written with that ellipsis keeps the names it stands for
    where it stands, so that a long list can be changed here too.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min = 0
    _attr_native_max = MAX_LENGTH_STATE_STATE

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "tournament_players")

    @property
    def _players(self) -> list[str]:
        return self.coordinator.games.tournament.setup.players

    def _shown(self) -> int:
        """How many names the state shows: all of them, or those that fit
        before the ellipsis."""
        players = self._players
        count = len(players)
        while (
            len(", ".join(players[:count]))
            + (0 if count == len(players) else len(MORE))
            > self.native_max
        ):
            count -= 1
        return count

    @property
    def native_value(self) -> str:
        shown = self._shown()
        return ", ".join(self._players[:shown]) + (
            "" if shown == len(self._players) else MORE
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"players": list(self._players)}

    async def async_set_value(self, value: str) -> None:
        written = [name.strip() for name in split_players(value)]
        names = [name for name in written if name != ELLIPSIS]
        with refusals():
            check_names(names)
        players = parse_players(",".join(names))
        if ELLIPSIS in written:
            # The ellipsis stands for the names it hid, where it stands.
            before = parse_players(",".join(written[: written.index(ELLIPSIS)]))
            players[len(before) : len(before)] = self._players[self._shown() :]
        if len(players) > MAX_ENTRANTS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="tournament_players",
                translation_placeholders={
                    "count": str(len(players)),
                    "min": str(MIN_ENTRANTS),
                    "max": str(MAX_ENTRANTS),
                },
            )
        await self.coordinator.async_set_tournament(players=players)
