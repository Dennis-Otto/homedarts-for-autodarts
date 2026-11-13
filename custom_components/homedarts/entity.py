"""Base entities for the HomeDarts integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .games_coordinator import AutodartsGamesCoordinator
from .local_coordinator import AutodartsLocalCoordinator
from .runtime import AutodartsConfigEntry
from .topics import Topic


def camera_count(coordinator: AutodartsGamesCoordinator) -> int:
    """How many cameras the board has, as its settings report them; none
    before they are read."""
    count: int = (coordinator.data or {}).get("settings", {}).get("camera_count", 0)
    return count


@callback
def async_track_cameras(
    entry: AutodartsConfigEntry,
    coordinator: AutodartsLocalCoordinator,
    factory: Callable[[int], Entity],
    add: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the entities of every camera of the board, the factory's entity per
    camera index, now and whenever the board reports more cameras.

    A camera the board no longer reports keeps its entities, which become
    unavailable.
    """
    known: set[int] = set()

    @callback
    def discover() -> None:
        new = set(range(camera_count(coordinator))) - known
        if new:
            known.update(new)
            add([factory(index) for index in sorted(new)])

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class AutodartsLocalEntity[
    CoordinatorT: AutodartsGamesCoordinator = AutodartsGamesCoordinator
](CoordinatorEntity[CoordinatorT]):
    """An entity of a board, read from the board itself or kept in Home Assistant.

    An entity of the games works with every board, a dartboard without
    Autodarts as well. An entity of the Board Manager, an AutodartsBoardEntity,
    has the board's AutodartsLocalCoordinator.
    """

    _attr_has_entity_name = True
    # The readings the entity shows, see AutodartsLocalCoordinator.readings: a
    # change of them alone updates it without the other entities of the board.
    _topic: Topic | None = None

    def __init__(self, coordinator: CoordinatorT, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.board_id}_{key}"
        self._attr_translation_key = key
        if not isinstance(coordinator, AutodartsLocalCoordinator):
            # A dartboard of any make, without a Board Manager to open.
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, coordinator.board_id)},
                name=coordinator.device_name,
                model=coordinator.device_model,
            )
            return
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.board_id)},
            name=coordinator.device_name,
            manufacturer="Autodarts",
            model="Dart Board",
            configuration_url=coordinator.client.base_url,
            sw_version=(coordinator.data or {}).get("version"),
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        coordinator = self.coordinator
        # Only a Board Manager sends readings.
        if self._topic is not None and isinstance(
            coordinator, AutodartsLocalCoordinator
        ):
            self.async_on_remove(
                coordinator.topics.async_add_listener(
                    self._topic, self.async_write_ha_state
                )
            )


class AutodartsBoardEntity(AutodartsLocalEntity[AutodartsLocalCoordinator]):
    """An entity of the Board Manager, such as a camera, a control or a reading
    of the detection; a dartboard without Autodarts has none."""


class AutodartsStoredEntity[
    CoordinatorT: AutodartsGamesCoordinator = AutodartsGamesCoordinator
](AutodartsLocalEntity[CoordinatorT]):
    """An entity of what Home Assistant keeps itself, such as a setting, a game,
    a training session, a statistic or an online match: it stays available while
    the board is switched off or away."""

    @property
    def available(self) -> bool:
        return True
