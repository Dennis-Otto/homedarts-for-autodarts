"""Camera standby of the Board Manager, the practice game, the X01 rules, Golf
holes, the report day and the tournament."""

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .cricket import CRICKET_GAMES
from .entity import AutodartsBoardEntity, AutodartsStoredEntity
from .games_coordinator import AutodartsGamesCoordinator
from .local_api import STANDBY_MINUTES
from .local_coordinator import AutodartsLocalCoordinator
from .party import GOLF_HOLES, WORLD_ORDERS
from .practice import GAME_OPTIONS, MAX_PLAYERS
from .report import WEEKDAYS
from .runtime import AutodartsConfigEntry
from .scoring import BULL_MODES, MODES
from .tournament import FORMATS, TOURNAMENT_GAMES

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutodartsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.local
    # A dartboard without Autodarts has no cameras to send to standby.
    standby = (
        [AutodartsStandbySelect(coordinator)]
        if isinstance(coordinator, AutodartsLocalCoordinator)
        else []
    )
    async_add_entities(
        [
            *standby,
            AutodartsPracticeGame(coordinator),
            *(
                AutodartsX01Rule(coordinator, rule)
                for rule in ("in_mode", "out_mode", "bull_mode")
            ),
            AutodartsGolfHoles(coordinator),
            AutodartsWorldOrder(coordinator),
            AutodartsReportDay(coordinator),
            AutodartsTournamentSelect(coordinator, "format"),
            AutodartsTournamentSelect(coordinator, "game"),
        ]
    )


class AutodartsStandbySelect(AutodartsBoardEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AutodartsLocalCoordinator) -> None:
        super().__init__(coordinator, "standby_minutes")
        self._attr_options = [str(value) for value in STANDBY_MINUTES]

    @property
    def available(self) -> bool:
        return super().available and self.current_option is not None

    @property
    def current_option(self) -> str | None:
        value = (self.coordinator.data or {}).get("settings", {}).get("standby_minutes")
        return str(value) if value in STANDBY_MINUTES else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_action(
            lambda: self.coordinator.client.set_standby_minutes(int(option))
        )


class AutodartsPracticeGame(AutodartsStoredEntity, SelectEntity):
    """X01, a Cricket, party or training game; a choice starts it anew."""

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "practice_game")
        self._attr_options = ["off", *GAME_OPTIONS]

    @property
    def current_option(self) -> str:
        practice = self.coordinator.games.practice
        if practice.drill:
            return practice.drill
        if practice.cricket:
            return practice.cricket
        if practice.party:
            return practice.party.kind
        return str(practice.game) if practice.game else "off"

    async def async_select_option(self, option: str) -> None:
        practice = self.coordinator.games.practice
        if (
            practice.bot_level
            and practice.humans >= MAX_PLAYERS
            and (option.isdigit() or option in CRICKET_GAMES)
        ):
            # The bot would take the seat of the fourth player.
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="bot_seat"
            )
        if option == "off":
            await self.coordinator.async_play(0)
        elif option.isdigit():
            await self.coordinator.async_play(int(option))
        else:
            await self.coordinator.async_play(option)


class AutodartsX01Rule(AutodartsStoredEntity, SelectEntity):
    """The In or Out mode of X01, straight, double or master, or its bull mode.

    The Out mode applies from the next leg once darts of a leg count; another
    In mode or bull mode starts the match anew.
    """

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AutodartsGamesCoordinator, rule: str) -> None:
        super().__init__(coordinator, f"practice_{rule}")
        self._rule = rule
        self._attr_options = list(BULL_MODES if rule == "bull_mode" else MODES)

    @property
    def current_option(self) -> str:
        return str(self.coordinator.games.practice.rule(self._rule))

    async def async_select_option(self, option: str) -> None:
        practice = self.coordinator.games.practice
        if self._rule != "bull_mode" and practice.unwinnable(
            rules={self._rule: option}
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unwinnable_start"
            )
        await self.coordinator.async_set_x01_rule(self._rule, option)


class AutodartsGolfHoles(AutodartsStoredEntity, SelectEntity):
    """Nine or 18 holes of Golf; a change starts a game of Golf anew."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "practice_golf_holes")
        self._attr_options = [str(holes) for holes in GOLF_HOLES]

    @property
    def current_option(self) -> str:
        return str(self.coordinator.games.practice.golf_holes)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_party_rounds(golf_holes=int(option))


class AutodartsWorldOrder(AutodartsStoredEntity, SelectEntity):
    """The order of Round the World before the bull; a change starts a game of
    Round the World anew."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "practice_round_the_world_order")
        self._attr_options = list(WORLD_ORDERS)

    @property
    def current_option(self) -> str:
        return self.coordinator.games.practice.round_the_world_order

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_party_rule("round_the_world_order", option)


class AutodartsReportDay(AutodartsStoredEntity, SelectEntity):
    """The weekday on which the weekly report ends the week."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "weekly_report_day")
        self._attr_options = list(WEEKDAYS)

    @property
    def current_option(self) -> str:
        return WEEKDAYS[self.coordinator.reports.report.weekday]

    async def async_select_option(self, option: str) -> None:
        reports = self.coordinator.reports
        await reports.async_set_schedule(WEEKDAYS.index(option), reports.report.time)


class AutodartsTournamentSelect(AutodartsStoredEntity, SelectEntity):
    """The format or the game of the next tournament."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AutodartsGamesCoordinator, key: str) -> None:
        super().__init__(coordinator, f"tournament_{key}")
        self._key = key
        self._attr_options = list(FORMATS if key == "format" else TOURNAMENT_GAMES)

    @property
    def current_option(self) -> str:
        value: str = getattr(self.coordinator.games.tournament.setup, self._key)
        return value

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_tournament(**{self._key: option})
