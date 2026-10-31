"""Explicit local Board Manager actions, also usable by HA automations."""

from functools import partial

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import (
    AutodartsBoardEntity,
    AutodartsStoredEntity,
    async_track_cameras,
    camera_count,
)
from .games_coordinator import AutodartsGamesCoordinator
from .local_coordinator import AutodartsLocalCoordinator
from .runtime import AutodartsConfigEntry

PARALLEL_UPDATES = 1

# Command -> enabled by default, entity category. Detection controls are used
# every session, so they appear on generated dashboards.
BUTTONS = {
    "start": (True, None),
    "stop": (True, None),
    "reset": (True, None),
    "restart": (True, EntityCategory.CONFIG),
    "calibrate": (True, EntityCategory.CONFIG),
    "connect": (False, EntityCategory.CONFIG),
    "disconnect": (False, EntityCategory.CONFIG),
    "start_streams": (False, EntityCategory.CONFIG),
    "stop_streams": (False, EntityCategory.CONFIG),
}
# Board Manager 2 has no routes to connect or disconnect its cloud link.
V1_BUTTONS = ("connect", "disconnect")
# Board Manager 2.1 has no routes to start or stop the streams of its cameras.
NOT_ON_2_1 = ("start_streams", "stop_streams")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutodartsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.local
    entities: list[ButtonEntity] = []
    # A dartboard without Autodarts has nothing to start, reset or calibrate.
    board = coordinator if isinstance(coordinator, AutodartsLocalCoordinator) else None
    if board:
        unsupported = V1_BUTTONS if board.board_manager_2 else ()
        entities.extend(
            AutodartsButton(board, key) for key in BUTTONS if key not in unsupported
        )
    entities.extend(
        (
            AutodartsTrainingReset(coordinator),
            AutodartsNewLeg(coordinator),
            AutodartsNewMatch(coordinator),
            *(
                AutodartsTournamentButton(coordinator, action)
                for action in ("start", "next_match", "stop")
            ),
        )
    )
    async_add_entities(entities)
    if board:
        async_track_cameras(
            entry,
            board,
            partial(AutodartsCameraCalibration, board),
            async_add_entities,
        )


class AutodartsButton(AutodartsBoardEntity, ButtonEntity):
    def __init__(self, coordinator: AutodartsLocalCoordinator, command: str) -> None:
        super().__init__(coordinator, command)
        self._command = command
        enabled, category = BUTTONS[command]
        self._attr_entity_registry_enabled_default = enabled
        self._attr_entity_category = category
        if command == "restart":
            self._attr_device_class = ButtonDeviceClass.RESTART

    @property
    def available(self) -> bool:
        return super().available and not (
            self._command in NOT_ON_2_1 and self.coordinator.client.interface_2_1
        )

    async def async_press(self) -> None:
        await self.coordinator.async_action(
            lambda: self.coordinator.client.command(self._command)
        )


class AutodartsCameraCalibration(AutodartsBoardEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: AutodartsLocalCoordinator, index: int) -> None:
        super().__init__(coordinator, f"calibrate_camera_{index}")
        self._index = index
        self._attr_translation_key = "calibrate_camera"
        self._attr_translation_placeholders = {"number": str(index + 1)}
        self._attr_extra_state_attributes = {"camera": index + 1}

    @property
    def available(self) -> bool:
        return super().available and self._index < camera_count(self.coordinator)

    async def async_press(self) -> None:
        await self.coordinator.async_action(
            lambda: self.coordinator.client.calibrate_camera(self._index)
        )


class AutodartsTrainingReset(AutodartsStoredEntity, ButtonEntity):
    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "reset_training")

    async def async_press(self) -> None:
        await self.coordinator.async_new_session()


class AutodartsNewLeg(AutodartsStoredEntity, ButtonEntity):
    """Start the practice leg again from the full score."""

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "practice_new_leg")

    async def async_press(self) -> None:
        await self.coordinator.async_new_leg()


class AutodartsNewMatch(AutodartsStoredEntity, ButtonEntity):
    """Start the practice match again from zero legs and sets."""

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "practice_new_match")

    async def async_press(self) -> None:
        await self.coordinator.async_new_match()


class AutodartsTournamentButton(AutodartsStoredEntity, ButtonEntity):
    """Start a tournament with its settings, start its next match or stop it."""

    def __init__(self, coordinator: AutodartsGamesCoordinator, action: str) -> None:
        super().__init__(coordinator, f"tournament_{action}")
        self._action = action

    async def async_press(self) -> None:
        if self._action == "start":
            await self.coordinator.async_start_tournament()
        elif self._action == "next_match":
            await self.coordinator.async_next_tournament_match()
        else:
            await self.coordinator.async_stop_tournament()
